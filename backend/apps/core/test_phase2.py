"""
Phase 2 (production foundation): alerts and scheduled-job monitoring.

  * L4-07  a payment flagged for a person (needs_review) raises ONE Sentry alert with no personal data.
  * F2-02  `ping_heartbeat` wraps a scheduled command and pings a heartbeat monitor (success or fail).
  * F2-08  the version tag Sentry receives is the GIT_COMMIT that render.yaml sets.
  * F3-09  render.yaml gives the cleanup cron what it needs and keeps the web start command's settings.
  * X-01   `ops/post_deploy_check.py`, the read-only production check.

Razorpay and Sentry are never called: their functions are patched.
"""
import importlib.util
import logging
import os
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
from pathlib import Path
from unittest import mock

import yaml
from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from apps.core import outbound, sentry_config
from apps.payments import test_f4_repro as repro
from apps.payments.models import Payment
from apps.payments.services import razorpay_client

BACKEND = Path(settings.BASE_DIR)
REPO = BACKEND.parent
HEARTBEAT = 'apps.core.management.commands.ping_heartbeat'
SECRET_URL = 'https://hc.example.test/ping/aaaa-secret-token-bbbb'
HAS_EMAIL_OR_PHONE = re.compile(r'@|\d{6,}')


class PaymentFlaggedAlertTests(repro.PaymentCase):
    """Payment code is not touched: a logging handler on `apps.payments` raises the alert."""

    def flag_by_wrong_amount(self):
        _, _, payment_id, order_id = repro.start_order(self.room, 1, 'student@example.test')
        repro.webhook('payment.captured', order_id, 'pay_short_1', 100)  # (no assertLogs: it would hide the handler)
        return payment_id

    def refund(self, payment_id, effect):
        with mock.patch(f'{repro.VIEWS}.initiate_refund', side_effect=effect):
            return repro.api(self.owner).post(reverse('payment-refund', args=[payment_id]), {}, format='json')

    def test_a_flagged_payment_calls_the_capture_helper_once(self):
        with mock.patch('apps.core.sentry_config.capture_payment_flagged') as helper:
            payment_id = self.flag_by_wrong_amount()
        self.assertTrue(Payment.objects.get(id=payment_id).needs_review)
        helper.assert_called_once_with('needs_review')

    def test_a_booking_rejected_while_paying_also_alerts_once(self):
        student, booking, payment_id, _ = repro.start_order(self.room, 1, 'student@example.test')
        type(booking).objects.filter(pk=booking.pk).update(status='rejected')
        with mock.patch('apps.core.sentry_config.capture_payment_flagged') as helper:
            repro.verify(student, payment_id, 'pay_rejected_1')
        helper.assert_called_once_with('needs_review')

    def test_a_refund_with_an_unknown_outcome_alerts_once(self):
        student, _, payment_id, _ = repro.start_order(self.room, 1, 'student@example.test')
        repro.verify(student, payment_id, 'pay_refundable')
        with mock.patch('apps.core.sentry_config.capture_payment_flagged') as helper:
            response = self.refund(payment_id, TimeoutError('read timed out'))
        self.assertEqual(response.status_code, 502)
        self.assertTrue(Payment.objects.get(id=payment_id).needs_review)
        helper.assert_called_once_with('refund_outcome_unknown')

    def test_a_refund_refused_by_razorpay_does_not_alert(self):
        student, _, payment_id, _ = repro.start_order(self.room, 1, 'student@example.test')
        repro.verify(student, payment_id, 'pay_refundable')
        with mock.patch('apps.core.sentry_config.capture_payment_flagged') as helper:
            self.refund(payment_id, razorpay_client.RefundRejected('no'))
        helper.assert_not_called()

    def test_ordinary_payment_errors_do_not_alert(self):
        with mock.patch('apps.core.sentry_config.capture_payment_flagged') as helper:
            logging.getLogger('apps.payments').error('Razorpay create_order failed: %s', 'timeout')
            logging.getLogger('apps.payments').info('Payment %s confirmed SUCCESS', 'x')
        helper.assert_not_called()

    def test_the_handler_is_registered_exactly_once(self):
        handlers = [h for h in logging.getLogger('apps.payments').handlers if type(h).__name__ == 'PaymentFlagHandler']
        self.assertEqual(len(handlers), 1)

    def test_the_real_event_carries_a_fixed_message_and_two_tags_and_nothing_personal(self):
        with mock.patch('sentry_sdk.capture_message') as capture:
            self.flag_by_wrong_amount()
        capture.assert_called_once()
        args, kwargs = capture.call_args
        self.assertEqual(args[0], 'Payment flagged for manual review')
        self.assertEqual(kwargs['level'], 'error')
        self.assertEqual(kwargs['tags'], {'alert': 'payment_flagged', 'kind': 'needs_review'})
        self.assertEqual(kwargs['fingerprint'], ['payment-flagged', 'needs_review'])
        self.assertEqual(set(kwargs), {'level', 'tags', 'fingerprint'})  # no extras, no user, no context
        self.assertIsNone(HAS_EMAIL_OR_PHONE.search(repr(capture.call_args)))


class SentryDuplicateTests(SimpleTestCase):
    """The ERROR log line that flags a payment also reaches Sentry; only the clean alert should."""

    def event(self, message, logger='apps.payments'):
        return {'logger': logger, 'logentry': {'message': message, 'formatted': message}}

    def test_the_flag_log_event_is_dropped(self):
        message = 'Payment 6f1c2d3e needs a manual refund or review: Razorpay reported 100 INR but the order is for 650000 INR.'
        self.assertIsNone(sentry_config.scrub_event(self.event(message), {}))

    def test_other_payment_errors_are_kept(self):
        self.assertIsNotNone(sentry_config.scrub_event(self.event('Razorpay create_order failed: timeout'), {}))
        self.assertIsNotNone(sentry_config.scrub_event(
            self.event('Razorpay refund 1 for payment 2: outcome unknown'), {}))  # keeps its traceback

    def test_the_same_words_from_another_logger_are_kept(self):
        message = 'Payment 6f1c2d3e needs a manual refund or review: x'
        self.assertIsNotNone(sentry_config.scrub_event(self.event(message, logger='apps.other'), {}))


class OutboundGetTests(SimpleTestCase):
    def test_get_uses_the_short_timeout_by_default(self):
        with mock.patch('apps.core.outbound.requests.get') as get:
            outbound.get('https://example.test/x')
        get.assert_called_once_with('https://example.test/x', timeout=outbound.SHORT)

    def test_a_timeout_above_the_ceiling_is_refused(self):
        with self.assertRaises(ValueError):
            outbound.get('https://example.test/x', timeout=(2.0, 30.0))


@override_settings(HEARTBEAT_URL=SECRET_URL, HEARTBEAT_FAIL_URL='')
class PingHeartbeatTests(SimpleTestCase):
    def run_command(self, *args, inner=None):
        out, err = StringIO(), StringIO()
        with mock.patch(f'{HEARTBEAT}.call_command', **({'side_effect': inner} if inner else {})) as inner_call, \
                mock.patch('apps.core.outbound.requests.get') as get:
            try:
                call_command('ping_heartbeat', *args, stdout=out, stderr=err)
                error = None
            except BaseException as exc:  # SystemExit must be visible to the test too
                error = exc
        return inner_call, get, error, out.getvalue() + err.getvalue()

    def test_success_runs_the_command_with_its_arguments_then_pings_the_success_url(self):
        inner, get, error, _ = self.run_command('cleanup_expired', '--dry-run')
        self.assertIsNone(error)
        inner.assert_called_once_with('cleanup_expired', '--dry-run')
        get.assert_called_once_with(SECRET_URL, timeout=outbound.SHORT)

    def test_failure_pings_the_fail_url_and_still_fails(self):
        inner, get, error, _ = self.run_command('cleanup_expired', inner=CommandError('boom'))
        self.assertIsInstance(error, CommandError)
        get.assert_called_once_with(SECRET_URL + '/fail', timeout=outbound.SHORT)

    def test_a_job_that_ends_with_system_exit_counts_as_failed(self):
        """cleanup_expired signals a failed step with SystemExit, which is not an Exception."""
        inner, get, error, _ = self.run_command('cleanup_expired', inner=SystemExit('steps failed'))
        self.assertIsInstance(error, SystemExit)
        get.assert_called_once_with(SECRET_URL + '/fail', timeout=outbound.SHORT)

    def test_a_clean_system_exit_zero_counts_as_success(self):
        inner, get, error, _ = self.run_command('cleanup_expired', inner=SystemExit(0))
        self.assertIsNone(error)
        get.assert_called_once_with(SECRET_URL, timeout=outbound.SHORT)

    @override_settings(HEARTBEAT_FAIL_URL='https://hc.example.test/ping/other-fail-token')
    def test_an_explicit_fail_url_is_used(self):
        _, get, _, _ = self.run_command('cleanup_expired', inner=CommandError('boom'))
        get.assert_called_once_with('https://hc.example.test/ping/other-fail-token', timeout=outbound.SHORT)

    @override_settings(HEARTBEAT_URL='')
    def test_without_a_url_the_command_still_runs_and_nothing_is_called(self):
        inner, get, error, _ = self.run_command('cleanup_expired', '--dry-run')
        self.assertIsNone(error)
        inner.assert_called_once_with('cleanup_expired', '--dry-run')
        get.assert_not_called()

    @override_settings(HEARTBEAT_URL='')
    def test_without_a_url_a_failure_is_still_raised(self):
        _, get, error, _ = self.run_command('cleanup_expired', inner=CommandError('boom'))
        self.assertIsInstance(error, CommandError)
        get.assert_not_called()

    def test_an_unreachable_monitor_never_fails_the_job_and_never_leaks_the_url(self):
        out = StringIO()
        with mock.patch(f'{HEARTBEAT}.call_command'), \
                mock.patch('apps.core.outbound.requests.get', side_effect=ConnectionError(f'cannot reach {SECRET_URL}')), \
                self.assertLogs('apps.core', level='WARNING') as logs:
            call_command('ping_heartbeat', 'cleanup_expired', stdout=out, stderr=out)
        everything = out.getvalue() + ' '.join(logs.output)
        self.assertNotIn('secret-token', everything)
        self.assertNotIn('hc.example.test', everything)
        self.assertIn('ConnectionError', everything)

    def test_the_url_is_never_printed(self):
        _, _, _, printed = self.run_command('cleanup_expired')
        self.assertNotIn('secret-token', printed)

    def test_an_unknown_command_is_a_failure(self):
        out = StringIO()
        with mock.patch('apps.core.outbound.requests.get') as get:
            with self.assertRaises(CommandError):
                call_command('ping_heartbeat', 'no_such_command_xyz', stdout=out, stderr=out)
        get.assert_called_once_with(SECRET_URL + '/fail', timeout=outbound.SHORT)

    def test_a_command_name_is_required(self):
        with self.assertRaises(CommandError):
            call_command('ping_heartbeat', stdout=StringIO(), stderr=StringIO())


class ReleaseTagTests(SimpleTestCase):
    """GIT_COMMIT (set by render.yaml) -> settings.RELEASE -> the options Sentry was started with."""

    def release_seen_by_sentry(self, **extra):
        env = {k: v for k, v in os.environ.items() if k in ('PATH', 'SYSTEMROOT', 'TEMP', 'TMP', 'HOME', 'USERPROFILE')}
        env.update({
            'SECRET_KEY': 'x' * 60, 'ALLOWED_HOSTS': 'localhost', 'DEBUG': 'False',
            'DATABASE_URL': 'postgres://u:p@localhost:1/none', 'SENTRY_DSN': 'https://k@o0.ingest.sentry.io/1',
            'SENTRY_RELEASE': '', 'GIT_COMMIT': '', 'DJANGO_SETTINGS_MODULE': 'config.settings',
        })
        env.update(extra)
        code = ('import config.settings, sentry_sdk; print("RELEASE=" + str(sentry_sdk.get_client().options["release"]))')
        done = subprocess.run([sys.executable, '-c', code], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120)
        match = re.search(r'^RELEASE=(.*)$', done.stdout, re.M)
        self.assertIsNotNone(match, done.stderr[-500:])
        return match.group(1)

    def test_sentry_receives_the_git_commit(self):
        self.assertEqual(self.release_seen_by_sentry(GIT_COMMIT='abc1234def5678'), 'abc1234def5678')

    def test_an_explicit_release_wins(self):
        self.assertEqual(self.release_seen_by_sentry(GIT_COMMIT='abc1234', SENTRY_RELEASE='v9'), 'v9')

    def test_render_sets_git_commit_on_every_service_that_can_report_errors(self):
        for service in load_render()['services']:
            self.assertIn('GIT_COMMIT=$RENDER_GIT_COMMIT', service['startCommand'], service['name'])


def load_render():
    return yaml.safe_load((REPO / 'render.yaml').read_text(encoding='utf-8'))


def service(name):
    return next(s for s in load_render()['services'] if s['name'] == name)


def env_names(svc):
    return {e['key'] for e in svc['envVars']}


class RenderYamlTests(SimpleTestCase):
    def test_the_cleanup_cron_is_wrapped_so_a_stopped_cron_alerts(self):
        cron = service('hostel-hunt-cleanup')
        self.assertIn('ping_heartbeat cleanup_expired', cron['startCommand'])

    def test_the_cleanup_cron_has_what_it_needs(self):
        names = env_names(service('hostel-hunt-cleanup'))
        for needed in ('PYTHON_VERSION', 'SECRET_KEY', 'ALLOWED_HOSTS', 'DATABASE_URL',
                       'SENTRY_DSN', 'SENTRY_ENVIRONMENT', 'HEARTBEAT_URL'):
            self.assertIn(needed, names)

    def test_the_cron_reports_to_the_production_sentry_environment(self):
        values = {e['key']: e.get('value') for e in service('hostel-hunt-cleanup')['envVars']}
        self.assertEqual(values['SENTRY_ENVIRONMENT'], 'production')

    def test_the_web_start_command_keeps_the_statement_timeout(self):
        for name in ('hostel-hunt-backend', 'hostel-hunt-backend-staging'):
            self.assertIn('DB_STATEMENT_TIMEOUT_MS=25000', service(name)['startCommand'])

    def test_the_cron_start_command_has_no_statement_timeout(self):
        self.assertNotIn('DB_STATEMENT_TIMEOUT_MS', service('hostel-hunt-cleanup')['startCommand'])

    def test_staging_keeps_its_do_not_monitor_comment(self):
        text = (REPO / 'render.yaml').read_text(encoding='utf-8')
        self.assertRegex(text, r'(?i)do not point an uptime monitor at it')

    def test_plans_and_instance_counts_are_unchanged(self):
        plans = {s['name']: s['plan'] for s in load_render()['services']}
        self.assertEqual(plans, {'hostel-hunt-backend': 'free', 'hostel-hunt-backend-staging': 'free',
                                 'hostel-hunt-cleanup': 'starter'})
        self.assertFalse(any('numInstances' in s for s in load_render()['services']))


class BackupWorkflowTests(SimpleTestCase):
    """G1-01: the workflow file must parse, and a run must not look green when no backup was made."""

    def setUp(self):
        self.text = (REPO / '.github' / 'workflows' / 'backup.yml').read_text(encoding='utf-8')
        self.workflow = yaml.safe_load(self.text)

    def test_the_workflow_parses_and_has_a_schedule_and_a_manual_trigger(self):
        triggers = self.workflow.get('on') or self.workflow.get(True)  # PyYAML reads the key `on` as True
        self.assertIn('schedule', triggers)
        self.assertIn('workflow_dispatch', triggers)

    def test_missing_secrets_fail_the_run_instead_of_passing_it(self):
        steps = self.workflow['jobs']['dump']['steps']
        warning = next(s for s in steps if 'secrets' in s.get('name', '').lower() and 'missing' in s.get('name', '').lower())
        self.assertIn('exit 1', warning['run'])


class PostDeployCheckTests(SimpleTestCase):
    """ops/post_deploy_check.py against a throwaway local server that plays production."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        spec = importlib.util.spec_from_file_location('post_deploy_check', BACKEND / 'ops' / 'post_deploy_check.py')
        cls.check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.check)

    def serve(self, routes):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                status, body = routes.get(self.path, (404, '{}'))
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(body.encode())

            def log_message(self, *args):
                pass

        server = HTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f'http://127.0.0.1:{server.server_port}'

    GOOD = {
        '/healthz': (200, '{"status": "ok", "env": "production"}'),
        '/readyz': (200, '{"status": "ok"}'),
        '/api/v1/debug-logs/': (404, '{"detail": "Not found."}'),
    }

    def results(self, routes, expect_env='production'):
        return {name: ok for name, ok, _ in self.check.run_checks(self.serve(routes), expect_env=expect_env)}

    def test_a_healthy_production_passes_every_check(self):
        self.assertTrue(all(self.results(self.GOOD).values()))

    def test_a_live_debug_route_fails(self):
        routes = dict(self.GOOD, **{'/api/v1/debug-logs/': (200, '{}')})
        self.assertFalse(self.results(routes)['debug route is gone (404)'])

    def test_an_unready_database_fails(self):
        routes = dict(self.GOOD, **{'/readyz': (503, '{"status": "unavailable"}')})
        self.assertFalse(self.results(routes)['/readyz answers ok'])

    def test_an_old_build_without_health_routes_fails(self):
        routes = {'/api/v1/debug-logs/': (200, '{}')}
        result = self.results(routes)
        self.assertFalse(result['/healthz answers ok'])
        self.assertFalse(result['/readyz answers ok'])

    def test_the_wrong_environment_fails(self):
        routes = dict(self.GOOD, **{'/healthz': (200, '{"status": "ok", "env": "staging"}')})
        self.assertFalse(self.results(routes)['/healthz says env=production'])
        self.assertTrue(self.results(routes, expect_env='staging')['/healthz says env=staging'])

    def test_the_exit_code_and_the_printout(self):
        base = self.serve(self.GOOD)
        out = StringIO()
        with mock.patch('sys.stdout', out):
            code = self.check.main(['post_deploy_check.py', base, '--expect-env', 'production'])
        self.assertEqual(code, 0)
        self.assertIn('RESULT: PASS', out.getvalue())
        bad = self.serve(dict(self.GOOD, **{'/api/v1/debug-logs/': (200, '{}')}))
        out = StringIO()
        with mock.patch('sys.stdout', out):
            code = self.check.main(['post_deploy_check.py', bad, '--expect-env', 'production'])
        self.assertEqual(code, 1)
        self.assertIn('RESULT: FAIL', out.getvalue())

    def test_only_get_requests_are_made(self):
        source = (BACKEND / 'ops' / 'post_deploy_check.py').read_text(encoding='utf-8')
        self.assertNotRegex(source, r'(?i)method\s*=\s*[\'"](POST|PUT|PATCH|DELETE)')
