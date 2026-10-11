"""
Production-configuration tests.

Settings are evaluated at import time, so these run ``config.settings`` in a
subprocess with a controlled environment. Variables set in the environment
take precedence over backend/.env, so a developer's local .env cannot leak in.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Variables the tests control explicitly; everything else is inherited.
_CONTROLLED = (
    'SECRET_KEY', 'DEBUG', 'ALLOWED_HOSTS', 'DATABASE_URL', 'USE_DB',
    'CORS_ALLOWED_ORIGINS', 'CSRF_TRUSTED_ORIGINS', 'EXPOSE_DEV_OTP',
    'TRUST_PROXY_SSL_HEADER', 'SECURE_SSL_REDIRECT', 'SECURE_HSTS_SECONDS',
    'JWT_ACCESS_MINUTES', 'JWT_REFRESH_DAYS', 'DJANGO_LOG_LEVEL',
)
PROD_SECRET = 'prod-test-secret-' + 'x' * 40


def prod_env(**overrides):
    env = {k: v for k, v in os.environ.items() if k not in _CONTROLLED}
    env.update(
        DJANGO_SETTINGS_MODULE='config.settings',
        DEBUG='False',
        SECRET_KEY=PROD_SECRET,
        ALLOWED_HOSTS='api.example.com',
        DATABASE_URL='postgres://user:pw@db.invalid:5432/hh',
        USE_DB='supabase',
    )
    env.update(overrides)
    return env


def run_python(code, env, timeout=120):
    return subprocess.run(
        [sys.executable, '-c', code], cwd=BACKEND_DIR, env=env,
        capture_output=True, text=True, timeout=timeout,
    )


def run_manage(args, env, timeout=180):
    return subprocess.run(
        [sys.executable, 'manage.py', *args], cwd=BACKEND_DIR, env=env,
        capture_output=True, text=True, timeout=timeout,
    )


DUMP_SETTINGS = """
import json
from django.conf import settings
print(json.dumps({
    'DEBUG': settings.DEBUG,
    'ALLOWED_HOSTS': settings.ALLOWED_HOSTS,
    'CORS_ALLOWED_ORIGINS': list(getattr(settings, 'CORS_ALLOWED_ORIGINS', [])),
    'CORS_ALLOW_ALL_ORIGINS': getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False),
    'SECURE_SSL_REDIRECT': settings.SECURE_SSL_REDIRECT,
    'SESSION_COOKIE_SECURE': settings.SESSION_COOKIE_SECURE,
    'CSRF_COOKIE_SECURE': settings.CSRF_COOKIE_SECURE,
    'SECURE_PROXY_SSL_HEADER': list(settings.SECURE_PROXY_SSL_HEADER or []),
    'STATIC_ROOT': str(getattr(settings, 'STATIC_ROOT', None)),
    'HANDLERS': [h['class'] for h in settings.LOGGING['handlers'].values()],
    'MIDDLEWARE': settings.MIDDLEWARE,
    'ACCESS_SECONDS': settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds(),
    'REFRESH_DAYS': settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].days,
    'EXPOSE_DEV_OTP': getattr(settings, 'EXPOSE_DEV_OTP', None),
}))
"""


class SettingsBootTests(SimpleTestCase):
    def test_refuses_to_boot_without_secret_key_when_debug_off(self):
        proc = run_python('import config.settings', prod_env(SECRET_KEY=''))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('SECRET_KEY', proc.stderr)

    def test_error_lists_every_missing_variable_by_name(self):
        proc = run_python(
            'import config.settings',
            prod_env(SECRET_KEY='', ALLOWED_HOSTS='', DATABASE_URL=''),
        )
        self.assertNotEqual(proc.returncode, 0)
        for name in ('SECRET_KEY', 'ALLOWED_HOSTS', 'DATABASE_URL'):
            self.assertIn(name, proc.stderr)

    def test_boots_when_required_variables_are_set(self):
        proc = run_python('import config.settings', prod_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_debug_on_needs_no_required_variables(self):
        proc = run_python('import config.settings', prod_env(
            DEBUG='True', USE_DB='sqlite', SECRET_KEY='', ALLOWED_HOSTS='', DATABASE_URL='',
        ))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_cors_origin_without_scheme_is_rejected_at_boot(self):
        proc = run_python(
            'import config.settings',
            prod_env(CORS_ALLOWED_ORIGINS='admin.example.com'),
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('CORS_ALLOWED_ORIGINS', proc.stderr)

    def test_manage_check_deploy_has_no_errors_with_debug_off(self):
        proc = run_manage(['check', '--deploy'], prod_env(USE_DB='sqlite'))
        self.assertEqual(proc.returncode, 0, proc.stderr)


class SettingsValuesTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        proc = run_python(DUMP_SETTINGS, prod_env(
            CORS_ALLOWED_ORIGINS='https://admin.example.com,https://b.example.com',
        ))
        assert proc.returncode == 0, proc.stderr
        cls.s = json.loads(proc.stdout.strip().splitlines()[-1])

    def test_hosts_and_cors_come_from_environment(self):
        self.assertEqual(self.s['ALLOWED_HOSTS'], ['api.example.com'])
        self.assertEqual(
            self.s['CORS_ALLOWED_ORIGINS'],
            ['https://admin.example.com', 'https://b.example.com'],
        )
        self.assertFalse(self.s['CORS_ALLOW_ALL_ORIGINS'])

    def test_transport_security_is_on_when_debug_off(self):
        self.assertTrue(self.s['SECURE_SSL_REDIRECT'])
        self.assertTrue(self.s['SESSION_COOKIE_SECURE'])
        self.assertTrue(self.s['CSRF_COOKIE_SECURE'])
        self.assertEqual(self.s['SECURE_PROXY_SSL_HEADER'], ['HTTP_X_FORWARDED_PROTO', 'https'])

    def test_static_files_are_served_by_whitenoise(self):
        self.assertTrue(self.s['STATIC_ROOT'].endswith('staticfiles'))
        self.assertIn('whitenoise.middleware.WhiteNoiseMiddleware', self.s['MIDDLEWARE'])

    def test_logs_go_to_stdout_only(self):
        self.assertEqual(set(self.s['HANDLERS']), {'logging.StreamHandler'})

    def test_jwt_lifetimes(self):
        self.assertEqual(self.s['ACCESS_SECONDS'], 30 * 60)
        self.assertEqual(self.s['REFRESH_DAYS'], 30)

    def test_dev_otp_flag_defaults_off(self):
        self.assertIs(self.s['EXPOSE_DEV_OTP'], False)


PROBE = """
import json
import django
django.setup()
from django.test import Client

ADMIN = 'https://admin.example.com'
HTTPS = {'HTTP_HOST': 'api.example.com', 'HTTP_X_FORWARDED_PROTO': 'https'}
out = {}
out['https_ok'] = Client(**HTTPS).get('/api/v1/auth/me/').status_code
out['http_redirects'] = Client(HTTP_HOST='api.example.com').get('/api/v1/auth/me/').status_code
out['bad_host'] = Client(HTTP_HOST='evil.example', HTTP_X_FORWARDED_PROTO='https').get('/api/v1/auth/me/').status_code
out['healthz_plain_http_any_host'] = Client(HTTP_HOST='10.1.2.3').get('/healthz').status_code
out['static_css'] = Client(**HTTPS).get('/static/admin/css/base.css').status_code
def preflight(origin):
    r = Client(**HTTPS).options('/api/v1/auth/me/', HTTP_ORIGIN=origin,
                                HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET')
    return r.headers.get('access-control-allow-origin')
out['cors_listed'] = preflight(ADMIN)
out['cors_unlisted'] = preflight('https://other.example')
r = Client(**HTTPS).get('/admin/login/')
out['admin_login'] = r.status_code
out['csrf_cookie_secure'] = bool(r.cookies['csrftoken']['secure']) if 'csrftoken' in r.cookies else None
print(json.dumps(out))
"""


class ProductionRuntimeProbeTests(SimpleTestCase):
    """Exercises the real middleware stack with DEBUG off."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = prod_env(USE_DB='sqlite', CORS_ALLOWED_ORIGINS='https://admin.example.com')
        collect = run_manage(['collectstatic', '--noinput'], env)
        assert collect.returncode == 0, collect.stderr
        proc = run_python(PROBE, env)
        assert proc.returncode == 0, proc.stderr
        cls.r = json.loads(proc.stdout.strip().splitlines()[-1])

    def test_https_request_reaches_the_api(self):
        self.assertEqual(self.r['https_ok'], 401)

    def test_plain_http_is_redirected_to_https(self):
        self.assertEqual(self.r['http_redirects'], 301)

    def test_unknown_host_is_rejected(self):
        self.assertEqual(self.r['bad_host'], 400)

    def test_healthz_answers_on_plain_http_for_any_host(self):
        self.assertEqual(self.r['healthz_plain_http_any_host'], 200)

    def test_admin_static_files_are_served(self):
        self.assertEqual(self.r['static_css'], 200)

    def test_cors_allows_only_listed_origins(self):
        self.assertEqual(self.r['cors_listed'], 'https://admin.example.com')
        self.assertIsNone(self.r['cors_unlisted'])

    def test_admin_login_sets_a_secure_csrf_cookie(self):
        self.assertEqual(self.r['admin_login'], 200)
        self.assertTrue(self.r['csrf_cookie_secure'])


class DeploymentFilesTests(SimpleTestCase):
    def test_env_example_lists_every_variable_settings_reads(self):
        import re
        source = (BACKEND_DIR / 'config' / 'settings.py').read_text(encoding='utf-8')
        names = set(re.findall(r"config\(\s*'([A-Z0-9_]+)'", source))
        example = (BACKEND_DIR / '.env.example').read_text(encoding='utf-8')
        missing = sorted(n for n in names if not re.search(rf'^#?\s*{n}=', example, re.M))
        self.assertEqual(missing, [], f'.env.example is missing: {missing}')

    def test_env_example_contains_no_values(self):
        import re
        for line in (BACKEND_DIR / '.env.example').read_text(encoding='utf-8').splitlines():
            match = re.match(r'^#?\s*([A-Z0-9_]+)=(.*)$', line)
            if match and match.group(1) in ('SECRET_KEY', 'DATABASE_URL', 'EMAIL_HOST_PASSWORD',
                                            'RAZORPAY_KEY_SECRET', 'RAZORPAY_WEBHOOK_SECRET'):
                self.assertEqual(match.group(2).strip(), '', line)

    def test_gunicorn_conf_loads_and_binds_to_port(self):
        import runpy
        old = os.environ.get('PORT')
        os.environ['PORT'] = '9123'
        try:
            conf = runpy.run_path(str(BACKEND_DIR / 'gunicorn.conf.py'))
        finally:
            if old is None:
                os.environ.pop('PORT')
            else:
                os.environ['PORT'] = old
        self.assertEqual(conf['bind'], '0.0.0.0:9123')
        self.assertEqual(conf['worker_class'], 'gthread')
        self.assertGreaterEqual(conf['timeout'], 30)
        self.assertIsNone(conf['accesslog'])  # our request log replaces gunicorn's access log
        self.assertFalse(conf.get('preload_app', False))

    def test_requirements_are_exactly_pinned(self):
        import re
        bad = []
        for line in (BACKEND_DIR / 'requirements.txt').read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and not re.match(r'^[A-Za-z0-9_.\-\[\]]+==[0-9][^\s]*$', line):
                bad.append(line)
        self.assertEqual(bad, [], f'unpinned requirements: {bad}')
