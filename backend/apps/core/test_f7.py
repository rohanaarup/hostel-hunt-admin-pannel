"""
F7: the load-test tooling (tools/loadtest) and the staging-only data it needs.

The tools are plain Python modules outside the Django project, so they are loaded by path here.
"""
import importlib.util
import io
import json
import os
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.bookings.models import Booking
from apps.core.sample_data import SEED_NAMESPACE
from apps.hostels.models import Hostel
from apps.payments.models import Payment
from apps.rooms.models import Bed, Room

TOOLS = Path(settings.BASE_DIR).parent / 'tools' / 'loadtest'
PASSWORD = 'load-test-password-123'


def load(name):
    spec = importlib.util.spec_from_file_location(f'loadtest_{name}', TOOLS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard, rules, summarize = load('guard'), load('rules'), load('summarize_log')
STAGING = 'https://hostel-hunt-admin-pannel.onrender.com'
PRODUCTION = 'https://hostel-hunt-backend.onrender.com'


class GuardTests(SimpleTestCase):
    def check(self, url, env=None, reported=None):
        return guard.check_target(url, env or {}, reported)

    def test_production_is_refused_by_default(self):
        allowed, message = self.check(PRODUCTION + '/api/v1', reported='production')
        self.assertFalse(allowed)
        self.assertIn('PRODUCTION', message)

    def test_production_is_refused_whatever_it_claims_to_be(self):
        allowed, _ = self.check(PRODUCTION, reported='staging')
        self.assertFalse(allowed)

    def test_production_with_the_explicit_flag_runs_but_warns(self):
        allowed, message = self.check(PRODUCTION, {'HH_LOADTEST_ALLOW_PRODUCTION': 'yes'})
        self.assertTrue(allowed)
        self.assertIn('WARNING', message)

    def test_anything_but_the_word_yes_does_not_unlock_production(self):
        for value in ('', 'true', '1', 'no'):
            allowed, _ = self.check(PRODUCTION, {'HH_LOADTEST_ALLOW_PRODUCTION': value})
            self.assertFalse(allowed, value)

    def test_staging_that_says_it_is_staging_is_allowed(self):
        self.assertEqual(self.check(STAGING, reported='staging'), (True, ''))

    def test_staging_host_that_cannot_say_what_it_is_is_refused(self):
        for reported in (None, 'production', 'development'):
            allowed, _ = self.check(STAGING, reported=reported)
            self.assertFalse(allowed, reported)

    def test_unknown_hosts_are_refused_even_if_they_claim_staging(self):
        allowed, message = self.check('https://example.org', reported='staging')
        self.assertFalse(allowed)
        self.assertIn('HH_LOADTEST_STAGING_HOSTS', message)

    def test_a_host_can_be_added_to_the_staging_list(self):
        allowed, _ = self.check('https://my-staging.example.org', {'HH_LOADTEST_STAGING_HOSTS': 'my-staging.example.org'}, 'staging')
        self.assertTrue(allowed)

    def test_this_computer_is_allowed(self):
        self.assertTrue(self.check('http://localhost:8000')[0])
        self.assertTrue(self.check('http://127.0.0.1:8000')[0])

    def test_no_host_is_refused(self):
        self.assertFalse(self.check('')[0])

    def test_the_default_production_host_matches_the_apps_default_server(self):
        app_api = Path(settings.BASE_DIR).parent.parent / 'ROHIIs_hostel_hunt' / 'rohii_hostel_hunt' / 'lib' / 'core' / 'network' / 'api_service.dart'
        if app_api.exists():  # the app repo sits next to this one on the developer's computer
            self.assertIn(next(iter(guard.PRODUCTION_HOSTS)), app_api.read_text(encoding='utf-8'))


class LocustfileTests(SimpleTestCase):
    def test_locustfile_and_shape_are_valid_python(self):
        """Locust is not installed on the server or in CI, so the files cannot be imported here; they must at least compile."""
        for name in ('locustfile.py', 'stress_shape.py'):
            compile((TOOLS / name).read_text(encoding='utf-8'), name, 'exec')

    def test_the_locustfile_asks_the_guard_before_any_user_starts(self):
        source = (TOOLS / 'locustfile.py').read_text(encoding='utf-8')
        self.assertIn('events.init.add_listener', source)
        self.assertIn('guard.check_target', source)
        self.assertIn('sys.exit(2)', source)


class RulesTests(SimpleTestCase):
    thresholds = {
        'p95_ms': {'public': 800, 'write': 2000}, 'max_error_ratio': 0.01, 'max_5xx_ratio': 0.001,
        'max_throttled_ratio': 0.01, 'min_requests': 100,
    }

    def row(self, name, requests=1000, p95=100, failures=None):
        return {'name': name, 'requests': requests, 'p95': p95, 'failures': failures or {}}

    def test_a_healthy_run_passes(self):
        passed, lines = rules.evaluate([self.row('public: list'), self.row('write: create booking')], self.thresholds)
        self.assertTrue(passed, lines)

    def test_a_slow_endpoint_fails_and_is_named(self):
        passed, lines = rules.evaluate([self.row('public: list', p95=900)], self.thresholds)
        self.assertFalse(passed)
        self.assertTrue(any(line.startswith('FAIL') and 'public: list' in line for line in lines))

    def test_server_errors_fail_on_their_own_limit(self):
        passed, _ = rules.evaluate([self.row('public: list', failures={'HTTP 503': 5})], self.thresholds)
        self.assertFalse(passed)

    def test_throttling_is_counted_apart_from_errors(self):
        throttled = [self.row('public: list', failures={rules.THROTTLED: 600})]
        passed, lines = rules.evaluate(throttled, self.thresholds)
        self.assertFalse(passed)
        self.assertTrue(any('throttled' in line and line.startswith('FAIL') for line in lines))
        self.assertTrue(any(line.startswith('PASS') and 'errors' in line for line in lines), 'a 429 is not an error')

    def test_too_few_requests_proves_nothing(self):
        passed, lines = rules.evaluate([self.row('public: list', requests=10)], self.thresholds)
        self.assertFalse(passed)
        self.assertIn('proves nothing', lines[0])

    def test_groups_without_a_limit_are_not_judged(self):
        passed, _ = rules.evaluate([self.row('public: list'), self.row('auth: me', p95=99999)], self.thresholds)
        self.assertTrue(passed)

    def test_the_shipped_thresholds_file_is_valid_json_with_every_key(self):
        data = json.loads((TOOLS / 'thresholds.json').read_text(encoding='utf-8'))
        for key in ('p95_ms', 'max_error_ratio', 'max_5xx_ratio', 'max_throttled_ratio', 'min_requests'):
            self.assertIn(key, data)


class LogSummaryTests(SimpleTestCase):
    def line(self, route='/hostels/', ms=100, status=200, ts='2026-01-01T10:00:00.000Z', pid=1, **extra):
        record = {'ts': ts, 'event': 'request', 'method': 'GET', 'route': route, 'status': status, 'duration_ms': ms,
                  'db_queries': 3, 'db_ms': 20, 'inflight': 2, 'pid': pid, **extra}
        return 'Oct 19 10:00:00 hh.request ' + json.dumps(record)

    def test_it_groups_by_route_and_reports_percentiles(self):
        lines = [self.line(ms=m) for m in range(1, 101)] + ['not json {', 'plain text']
        rows = summarize.summarise(summarize.parse(lines))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['requests'], 100)
        self.assertAlmostEqual(rows[0]['p95'], 95, delta=1)
        self.assertEqual(rows[0]['queries'], 3)

    def test_the_time_window_is_honoured(self):
        lines = [self.line(ts='2026-01-01T09:00:00.000Z'), self.line(ts='2026-01-01T10:30:00.000Z')]
        found = list(summarize.parse(lines, start='2026-01-01T10:00:00Z', end='2026-01-01T11:00:00Z'))
        self.assertEqual(len(found), 1)

    def test_it_counts_status_classes_and_workers(self):
        rows = summarize.summarise(summarize.parse([self.line(status=200, pid=1), self.line(status=503, pid=2), self.line(status=200, pid=2)]))
        self.assertEqual(rows[0]['statuses'], {'2xx': 2, '5xx': 1})
        self.assertEqual(rows[0]['pids'], 2)
        self.assertIn('| GET /hostels/ |', summarize.render(rows))


class ThrottleSettingTests(SimpleTestCase):
    def test_default_rates_are_the_launch_values(self):
        rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
        if 'THROTTLE_ANON' not in os.environ:
            self.assertEqual(rates['anon'], '60/min')
        if 'THROTTLE_USER' not in os.environ:
            self.assertEqual(rates['user'], '120/min')

    def test_healthz_names_the_environment(self):
        with override_settings(APP_ENV='staging'):
            self.assertEqual(self.client.get('/healthz').json(), {'status': 'ok', 'env': 'staging'})


@override_settings(APP_ENV='staging')
class SeedLoadTestTests(TestCase):
    def run_seed(self, **options):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {'LOADTEST_PASSWORD': PASSWORD}):
            call_command('seed_loadtest', stdout=out, students=5, hostels=4, payments=3, **options)
        return out.getvalue()

    def test_it_creates_students_hostels_beds_and_settled_payments(self):
        output = self.run_seed()
        Owner = get_user_model()
        self.assertEqual(Owner.objects.filter(email__startswith='load').count(), 5)
        self.assertTrue(Owner.objects.get(email=rules.student_email(1)).check_password(PASSWORD))
        self.assertGreaterEqual(Hostel.objects.filter(name__startswith='Load Test Hostel').count(), 4)
        self.assertEqual(Room.objects.filter(hostel__name='Load Test Hostel 1').count(), 9)
        self.assertGreater(Bed.objects.count(), 20)
        self.assertEqual(Payment.objects.filter(status='SUCCESS').count(), 3)
        self.assertNotIn(PASSWORD, output)

    def test_running_it_twice_changes_nothing(self):
        self.run_seed()
        before = (get_user_model().objects.count(), Hostel.objects.count(), Room.objects.count(), Bed.objects.count(), Payment.objects.count())
        self.run_seed()
        after = (get_user_model().objects.count(), Hostel.objects.count(), Room.objects.count(), Bed.objects.count(), Payment.objects.count())
        self.assertEqual(before, after)

    def test_the_load_test_computes_the_same_payment_ids_the_seed_creates(self):
        self.run_seed()
        for n in (1, 2, 3):
            payment = Payment.objects.get(booking__student__email=rules.student_email(n))
            self.assertEqual(str(payment.id), rules.payment_id_for(n))
        self.assertEqual(rules.SEED_NAMESPACE, SEED_NAMESPACE)

    def test_reset_activity_removes_bookings_made_during_a_run(self):
        self.run_seed()
        student = get_user_model().objects.get(email=rules.student_email(5))
        room = Room.objects.first()
        Booking.objects.create(hostel=room.hostel, room=room, student=student, student_name='x', status='pending')
        self.run_seed(reset_activity=True)
        self.assertFalse(Booking.objects.filter(student=student, status='pending').exists())
        self.assertEqual(Payment.objects.filter(status='SUCCESS').count(), 3, 'the settled payments are put back')

    def test_the_password_comes_from_the_environment_and_must_be_long(self):
        with mock.patch.dict(os.environ, {'LOADTEST_PASSWORD': 'short'}):
            with self.assertRaises(CommandError):
                call_command('seed_loadtest', stdout=io.StringIO())
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('LOADTEST_PASSWORD', None)
            with self.assertRaises(CommandError):
                call_command('seed_loadtest', stdout=io.StringIO())

    def test_it_refuses_a_database_with_real_users(self):
        get_user_model().objects.create_user(email='someone@gmail.com', display_name='Real', password='x' * 12)
        with mock.patch.dict(os.environ, {'LOADTEST_PASSWORD': PASSWORD}):
            with self.assertRaises(CommandError):
                call_command('seed_loadtest', stdout=io.StringIO())


class SeedLoadTestProductionGuardTests(TestCase):
    def test_it_refuses_to_run_outside_staging(self):
        for env in ('production', 'development'):
            with override_settings(APP_ENV=env), mock.patch.dict(os.environ, {'LOADTEST_PASSWORD': PASSWORD}):
                with self.assertRaises(CommandError):
                    call_command('seed_loadtest', stdout=io.StringIO())
        self.assertFalse(get_user_model().objects.exists())


class OpsScriptTests(SimpleTestCase):
    """The backup and restore scripts must refuse to run half-configured. (Needs bash; skipped where there is none.)"""
    ops = Path(settings.BASE_DIR) / 'ops'

    def run_script(self, name, *args, env=None):
        import shutil
        import subprocess
        bash = shutil.which('bash')
        if bash is None:
            self.skipTest('bash is not available')
        clean = {k: v for k, v in os.environ.items() if k not in ('BACKUP_DATABASE_URL', 'BACKUP_AGE_PUBLIC_KEY', 'AGE_IDENTITY_FILE', 'RESTORE_CONFIRM')}
        clean.update(env or {})
        return subprocess.run([bash, str(self.ops / name), *args], capture_output=True, text=True, env=clean, timeout=60)

    def test_backup_needs_both_values(self):
        result = self.run_script('backup.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('BACKUP_DATABASE_URL', result.stderr)
        result = self.run_script('backup.sh', env={'BACKUP_DATABASE_URL': 'postgres://x', 'BACKUP_AGE_PUBLIC_KEY': 'not-a-key'})
        self.assertEqual(result.returncode, 2)

    def test_restore_refuses_without_the_not_production_confirmation(self):
        result = self.run_script('restore.sh', 'dump.age', 'postgres://x', env={'AGE_IDENTITY_FILE': 'key.txt'})
        self.assertEqual(result.returncode, 2)
        self.assertIn('not-production', result.stderr)

    def test_verify_restore_finds_missing_tables_and_row_differences(self):
        spec = importlib.util.spec_from_file_location('verify_restore', self.ops / 'verify_restore.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.compare({'a': 3, 'b': 0}, {'a': 3, 'b': 0, 'extra': 9}), [])
        self.assertEqual(module.compare({'a': 3}, {}), ['MISSING table a'])
        self.assertEqual(module.compare({'a': 3}, {'a': 2}), ['DIFFERENT a: source 3, restored 2'])

