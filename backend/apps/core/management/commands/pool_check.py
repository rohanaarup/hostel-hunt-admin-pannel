"""
Management command: pool_check

A small, safe script that proves the database connection works the way DB_POOL_MODE says it should. Run it on staging
after any change of pooler or mode (`python manage.py pool_check`). It reads and writes nothing of ours: it uses a
temporary table that vanishes with its transaction. It never prints the database address, user or password.

Checks:
  * select for update inside a transaction        works (a row lock inside one transaction block)
  * parameterised query, repeated 25 times         works (psycopg would prepare it after 5 uses; in transaction mode
                                                   that must be off or the pooler answers "prepared statement does
                                                   not exist")
  * statement_timeout inside a transaction         equals DB_STATEMENT_TIMEOUT_MS when one is configured (FAIL if not)
  * statement_timeout outside a transaction        informational in transaction mode: it is only in force there if
                                                   the database role carries it (docs/CAPACITY.md), reported as WARN
  * server connections across 6 transactions       how many different backend processes served them: 1 means a
                                                   session pooler or a direct connection, more means a transaction
                                                   pooler is handing out connections (informational)

Exit code 0 with RESULT: PASS, or 1 with RESULT: FAIL.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction


def _ms(show_value):
    """'25s' / '500ms' / '1min' / '0' as printed by SHOW statement_timeout, in milliseconds."""
    text = show_value.strip()
    units = (('ms', 1), ('min', 60000), ('s', 1000), ('h', 3600000), ('d', 86400000))
    for suffix, factor in units:
        if text.endswith(suffix):
            return int(float(text[: -len(suffix)]) * factor)
    return int(text) if text.isdigit() else -1


class Command(BaseCommand):
    help = "Prove the database connection works for DB_POOL_MODE (FOR UPDATE, prepared statements, statement timeout)."

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            self.stdout.write('pool_check needs PostgreSQL.')
            raise SystemExit(2)

        mode = getattr(settings, 'DB_POOL_MODE', 'session')
        wanted = int(getattr(settings, 'DB_STATEMENT_TIMEOUT_MS', 0))
        self.stdout.write(f'DB_POOL_MODE={mode}  DB_STATEMENT_TIMEOUT_MS={wanted}')
        results = []

        def record(name, status, detail=''):
            results.append(status)
            self.stdout.write(f'{status:5} {name}' + (f'  ({detail})' if detail else ''))

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('CREATE TEMP TABLE hh_pool_check (id int) ON COMMIT DROP')
                    cursor.execute('INSERT INTO hh_pool_check VALUES (1)')
                    cursor.execute('SELECT id FROM hh_pool_check FOR UPDATE')
                    ok = cursor.fetchone() == (1,)
            record('select for update inside a transaction', 'PASS' if ok else 'FAIL')
        except Exception as exc:  # noqa: BLE001
            record('select for update inside a transaction', 'FAIL', type(exc).__name__)

        try:
            with connection.cursor() as cursor:
                for number in range(25):
                    cursor.execute('SELECT %s::int + 1', [number])
                    if cursor.fetchone()[0] != number + 1:
                        raise ValueError('wrong answer')
            record('parameterised query repeated 25 times', 'PASS')
        except Exception as exc:  # noqa: BLE001
            record('parameterised query repeated 25 times', 'FAIL', type(exc).__name__)

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SHOW statement_timeout')
                inside = cursor.fetchone()[0]
        with connection.cursor() as cursor:
            cursor.execute('SHOW statement_timeout')
            outside = cursor.fetchone()[0]

        if wanted > 0:
            record('statement_timeout inside a transaction', 'PASS' if _ms(inside) == wanted else 'FAIL',
                   f'{inside}, wanted {wanted} ms')
            if _ms(outside) == wanted:
                record('statement_timeout outside a transaction', 'PASS', outside)
            elif mode == 'transaction':
                record('statement_timeout outside a transaction', 'WARN',
                       f'{outside}: only the role-level setting can cover single statements in transaction mode')
            else:
                record('statement_timeout outside a transaction', 'FAIL', f'{outside}, wanted {wanted} ms')
        else:
            record('statement_timeout inside a transaction', 'PASS', f'{inside}; none configured')
            record('statement_timeout outside a transaction', 'PASS', f'{outside}; none configured')

        pids = set()
        for _ in range(6):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()')
                    pids.add(cursor.fetchone()[0])
        self.stdout.write(f'INFO  server connections that served 6 transactions: {len(pids)}')

        passed = all(status in ('PASS', 'WARN') for status in results)
        self.stdout.write('RESULT: PASS' if passed else 'RESULT: FAIL')
        if not passed:
            raise SystemExit(1)
