"""
Phase 3, Part 3: DB_POOL_MODE=session|transaction.

Session mode (the default) behaves exactly as before. Transaction mode is for a pooler that hands a different server
connection to every transaction (Supabase's transaction pooler, pgbouncer in transaction mode). There:

  * server-side cursors are off (they live on one server connection) and psycopg's automatic prepared statements are
    off (a prepared statement belongs to one server connection) -- as docs/AFTER-F5.md describes;
  * a session-level `SET statement_timeout` made when the connection opens would land on some other client's server
    connection, so the timeout is applied with SET LOCAL at the start of every transaction instead.

Statements that run outside a transaction block (autocommit reads) cannot carry a SET LOCAL without extra round trips,
so in transaction mode they rely on a role-level setting (docs/CAPACITY.md, "Transaction mode"); the pool_check command
reports both cases.
"""
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest import mock, skipUnless

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from apps.core import db_options

BACKEND = Path(settings.BASE_DIR)
on_postgres = skipUnless(connection.vendor == 'postgresql', 'needs PostgreSQL')


class PoolSettingsTests(SimpleTestCase):
    def test_session_mode_changes_nothing(self):
        database = {'OPTIONS': {'connect_timeout': 5}}
        db_options.apply_pool_mode(database, 'session')
        self.assertEqual(database, {'OPTIONS': {'connect_timeout': 5}})

    def test_transaction_mode_turns_off_server_side_cursors_and_prepared_statements(self):
        database = {'OPTIONS': {'connect_timeout': 5}}
        db_options.apply_pool_mode(database, 'transaction')
        self.assertIs(database['DISABLE_SERVER_SIDE_CURSORS'], True)
        self.assertIsNone(database['OPTIONS']['prepare_threshold'])
        self.assertEqual(database['OPTIONS']['connect_timeout'], 5)  # what was there stays

    def test_an_unknown_mode_is_refused_with_a_clear_message(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            db_options.apply_pool_mode({}, 'statement')
        self.assertIn('DB_POOL_MODE', str(ctx.exception))

    def test_the_mode_is_read_case_insensitively_and_defaults_to_session(self):
        self.assertEqual(db_options.pool_mode_from(''), 'session')
        self.assertEqual(db_options.pool_mode_from('Transaction'), 'transaction')


class SettingsFromEnvironmentTests(SimpleTestCase):
    """The real settings module, started in a child process with each setting."""

    def database_after(self, **extra):
        env = {k: v for k, v in os.environ.items() if k in ('PATH', 'SYSTEMROOT', 'TEMP', 'TMP', 'HOME', 'USERPROFILE')}
        env.update({'SECRET_KEY': 'x' * 60, 'ALLOWED_HOSTS': 'localhost', 'DEBUG': 'False', 'GIT_COMMIT': '',
                    'DATABASE_URL': 'postgres://u:p@localhost:1/none', 'DJANGO_SETTINGS_MODULE': 'config.settings',
                    'DB_POOL_MODE': ''})
        env.update(extra)
        code = ('import config.settings as s; d = s.DATABASES["default"]; '
                'print("MODE=%s CURSORS=%s PREPARE=%s" % (s.DB_POOL_MODE, d.get("DISABLE_SERVER_SIDE_CURSORS"), '
                'd["OPTIONS"].get("prepare_threshold", "default")))')
        done = subprocess.run([sys.executable, '-c', code], cwd=BACKEND, env=env, capture_output=True, text=True,
                              timeout=120)
        return done

    def test_the_default_is_session_mode(self):
        out = self.database_after().stdout
        self.assertIn('MODE=session CURSORS=False PREPARE=default', out)

    def test_transaction_mode_reaches_the_database_settings(self):
        out = self.database_after(DB_POOL_MODE='transaction').stdout
        self.assertIn('MODE=transaction CURSORS=True PREPARE=None', out)

    def test_a_typo_stops_the_server_from_starting(self):
        done = self.database_after(DB_POOL_MODE='transacton')
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('DB_POOL_MODE', done.stderr)

    def test_it_is_listed_in_env_example(self):
        text = (BACKEND / '.env.example').read_text(encoding='utf-8')
        self.assertRegex(text, r'(?m)^#?\s*DB_POOL_MODE=')


@on_postgres
class TransactionModeTimeoutTests(TransactionTestCase):
    """SET LOCAL statement_timeout at the start of each transaction, only in transaction mode."""

    def setUp(self):
        self.wrapper = db_options.local_timeout_wrapper(25000)
        connection.execute_wrappers.append(self.wrapper)
        self.addCleanup(lambda: connection.execute_wrappers.remove(self.wrapper))

    def show(self):
        with connection.cursor() as cursor:
            cursor.execute('SHOW statement_timeout')
            return cursor.fetchone()[0]

    def test_inside_a_transaction_the_timeout_is_applied(self):
        from django.db import transaction
        with transaction.atomic():
            self.assertEqual(self.show(), '25s')

    def test_it_is_applied_to_every_transaction_not_just_the_first(self):
        from django.db import transaction
        for _ in range(3):
            with transaction.atomic():
                self.assertEqual(self.show(), '25s')

    def test_it_does_not_leak_out_of_the_transaction(self):
        from django.db import transaction
        with transaction.atomic():
            self.show()
        self.assertEqual(self.show(), '0')  # an autocommit statement outside a transaction is untouched

    def test_nested_atomic_blocks_do_not_repeat_it(self):
        from django.db import transaction
        with transaction.atomic():
            with transaction.atomic():
                self.assertEqual(self.show(), '25s')
            self.assertEqual(self.show(), '25s')  # still in force after the inner block ends

    def test_select_for_update_inside_atomic_works(self):
        from django.db import transaction
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('CREATE TEMP TABLE hh_pool_test (id int) ON COMMIT DROP')
                cursor.execute('INSERT INTO hh_pool_test VALUES (1)')
                cursor.execute('SELECT id FROM hh_pool_test FOR UPDATE')
                self.assertEqual(cursor.fetchone()[0], 1)


@on_postgres
class ReceiverTests(TransactionTestCase):
    """apply_statement_timeout picks the right strategy for the mode."""

    def fake_connection(self):
        conn = mock.MagicMock()
        conn.vendor = 'postgresql'
        conn.execute_wrappers = []
        return conn

    @override_settings(DB_POOL_MODE='session', DB_STATEMENT_TIMEOUT_MS=25000)
    def test_session_mode_sets_a_session_timeout_and_installs_no_wrapper(self):
        conn = self.fake_connection()
        db_options.apply_statement_timeout(sender=None, connection=conn)
        conn.cursor.return_value.__enter__.return_value.execute.assert_called_once_with('SET statement_timeout = 25000')
        self.assertEqual(conn.execute_wrappers, [])

    @override_settings(DB_POOL_MODE='transaction', DB_STATEMENT_TIMEOUT_MS=25000)
    def test_transaction_mode_sets_nothing_on_the_session_and_installs_the_wrapper(self):
        conn = self.fake_connection()
        db_options.apply_statement_timeout(sender=None, connection=conn)
        conn.cursor.assert_not_called()
        self.assertEqual(len(conn.execute_wrappers), 1)

    @override_settings(DB_POOL_MODE='transaction', DB_STATEMENT_TIMEOUT_MS=0)
    def test_no_timeout_configured_means_nothing_happens_in_either_mode(self):
        conn = self.fake_connection()
        db_options.apply_statement_timeout(sender=None, connection=conn)
        conn.cursor.assert_not_called()
        self.assertEqual(conn.execute_wrappers, [])


@on_postgres
class PoolCheckCommandTests(TransactionTestCase):
    def run_check(self, **settings_overrides):
        out = StringIO()
        connection.ensure_connection()  # opened BEFORE the override: its timeout hook has not seen the new value
        with override_settings(**settings_overrides):
            try:
                call_command('pool_check', stdout=out, stderr=out)
                code = 0
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue()

    def test_a_healthy_session_mode_database_passes(self):
        code, text = self.run_check(DB_POOL_MODE='session', DB_STATEMENT_TIMEOUT_MS=0)
        self.assertEqual(code, 0, text)
        self.assertIn('RESULT: PASS', text)
        self.assertIn('select for update inside a transaction', text.lower())

    def test_it_reports_the_statement_timeout_inside_and_outside_a_transaction(self):
        _, text = self.run_check(DB_POOL_MODE='session', DB_STATEMENT_TIMEOUT_MS=0)
        self.assertIn('statement_timeout inside a transaction', text)
        self.assertIn('statement_timeout outside a transaction', text)

    def test_it_fails_when_the_configured_timeout_is_not_in_force_inside_a_transaction(self):
        # configured 25 s but nothing applied it (no receiver ran for this connection): the check must say FAIL
        code, text = self.run_check(DB_POOL_MODE='session', DB_STATEMENT_TIMEOUT_MS=25000)
        self.assertNotEqual(code, 0, text)
        self.assertIn('RESULT: FAIL', text)

    def test_it_never_prints_the_database_address_or_password(self):
        _, text = self.run_check(DB_POOL_MODE='session', DB_STATEMENT_TIMEOUT_MS=0)
        db = settings.DATABASES['default']
        for secret in (db.get('PASSWORD'), db.get('HOST')):
            if secret and secret not in ('localhost', '127.0.0.1'):
                self.assertNotIn(secret, text)
        self.assertNotIn('postgres://', text)
