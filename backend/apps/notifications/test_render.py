"""The two Phase 8 cron services in render.yaml: schedules, wrapping, and the environment each needs."""
from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase

REPO = Path(settings.BASE_DIR).parent


def service(name):
    data = yaml.safe_load((REPO / 'render.yaml').read_text(encoding='utf-8'))
    return next(s for s in data['services'] if s['name'] == name)


def env(svc):
    return {e['key']: e.get('value') for e in svc['envVars']}


class EngineCrons(SimpleTestCase):
    def test_process_outbox_runs_every_five_minutes_wrapped_by_the_heartbeat(self):
        svc = service('hostel-hunt-outbox')
        self.assertEqual(svc['type'], 'cron')
        self.assertEqual(svc['schedule'], '*/5 * * * *')
        self.assertIn('ping_heartbeat process_outbox', svc['startCommand'])
        self.assertIn('GIT_COMMIT=$RENDER_GIT_COMMIT', svc['startCommand'])
        self.assertNotIn('DB_STATEMENT_TIMEOUT_MS', svc['startCommand'])

    def test_stays_daily_runs_at_0330_utc_which_is_0900_ist(self):
        svc = service('hostel-hunt-daily')
        self.assertEqual(svc['schedule'], '30 3 * * *')
        self.assertIn('ping_heartbeat stays_daily', svc['startCommand'])
        self.assertIn('GIT_COMMIT=$RENDER_GIT_COMMIT', svc['startCommand'])

    def test_each_cron_has_its_own_environment_and_needs_no_razorpay(self):
        for name, extra in (('hostel-hunt-outbox', {'EMAIL_API_PROVIDER', 'EMAIL_API_KEY', 'DEFAULT_FROM_EMAIL',
                                                    'EMAIL_DAILY_CAP', 'OUTBOX_MAX_ATTEMPTS', 'QUIET_HOURS_START',
                                                    'QUIET_HOURS_END'}),
                            ('hostel-hunt-daily', {'RECONCILE_STAYS_MAX_AGE_DAYS'})):
            names = set(env(service(name)))
            for needed in {'PYTHON_VERSION', 'SECRET_KEY', 'ALLOWED_HOSTS', 'DATABASE_URL', 'SENTRY_DSN',
                           'SENTRY_ENVIRONMENT', 'HEARTBEAT_URL'} | extra:
                self.assertIn(needed, names, (name, needed))
            self.assertFalse([n for n in names if n.startswith('RAZORPAY')], name)
            self.assertEqual(env(service(name))['SENTRY_ENVIRONMENT'], 'production')

    def test_every_new_variable_is_listed_in_env_example(self):
        text = (Path(settings.BASE_DIR) / '.env.example').read_text(encoding='utf-8')
        for name in ('EMAIL_DAILY_CAP', 'OUTBOX_MAX_ATTEMPTS', 'QUIET_HOURS_START', 'QUIET_HOURS_END',
                     'RECONCILE_STAYS_MAX_AGE_DAYS', 'NOTIFICATION_RETENTION_DAYS'):
            self.assertIn(name, text)

    def test_the_move_to_a_background_worker_is_documented(self):
        text = (REPO / 'render.yaml').read_text(encoding='utf-8')
        self.assertIn('process_outbox --loop', text)
