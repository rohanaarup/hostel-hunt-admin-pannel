import json
import re
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.owners.models import Owner

REQUIRED_FIELDS = {
    'ts', 'level', 'event', 'request_id', 'method', 'route', 'view', 'status',
    'duration_ms', 'db_queries', 'db_ms', 'resp_bytes', 'inflight', 'user_id',
    'release', 'pid',
}
EMAIL = 'private.person@example.com'


def request_lines(logs):
    return [json.loads(record.getMessage()) for record in logs.records]


class RequestLogTests(TestCase):
    def setUp(self):
        cache.clear()

    def one_line(self, do_request):
        with self.assertLogs('hh.request', level='INFO') as logs:
            response = do_request()
        lines = request_lines(logs)
        self.assertEqual(len(lines), 1, lines)
        return response, lines[0]

    def test_middleware_is_first(self):
        self.assertEqual(settings.MIDDLEWARE[0], 'apps.core.observability.RequestLogMiddleware')

    def test_line_has_every_required_field(self):
        _, line = self.one_line(lambda: Client().get('/api/v1/hostels/'))
        self.assertTrue(REQUIRED_FIELDS <= set(line), REQUIRED_FIELDS - set(line))
        self.assertEqual(line['event'], 'request')
        self.assertEqual(line['method'], 'GET')
        self.assertEqual(line['status'], 200)
        self.assertEqual(line['level'], 'info')
        self.assertIsInstance(line['duration_ms'], (int, float))
        self.assertGreaterEqual(line['duration_ms'], 0)
        self.assertGreaterEqual(line['db_queries'], 1)
        self.assertGreaterEqual(line['inflight'], 1)
        self.assertRegex(line['ts'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d')
        self.assertIsNone(line['user_id'])

    def test_route_is_a_template_never_the_real_path(self):
        _, line = self.one_line(lambda: Client().get('/api/v1/hostels/123456/'))
        self.assertEqual(line['route'], 'api/v1/hostels/<pk>/')
        self.assertNotIn('123456', json.dumps(line))

    def test_unmatched_path_is_labelled_and_not_logged(self):
        _, line = self.one_line(lambda: Client().get('/nope/secret-token-xyz'))
        self.assertEqual(line['route'], 'unmatched')
        self.assertEqual(line['status'], 404)
        self.assertEqual(line['level'], 'warning')
        self.assertNotIn('secret-token-xyz', json.dumps(line))

    def test_no_personal_data_in_the_line(self):
        def do():
            return APIClient().post(
                f'/api/v1/auth/send-otp/?email={EMAIL}',
                {'identifier': EMAIL, 'identifier_type': 'email', 'purpose': 'signup', 'password': 'hunter2hunter2'},
                format='json',
                HTTP_AUTHORIZATION='Bearer aaa.bbb.ccc',
                HTTP_USER_AGENT='SecretAgent/1.0',
                HTTP_X_FORWARDED_FOR='203.0.113.9',
                REMOTE_ADDR='198.51.100.7',
            )
        _, line = self.one_line(do)
        text = json.dumps(line)
        for secret in (EMAIL, 'private.person', 'hunter2', 'aaa.bbb.ccc', 'SecretAgent',
                       '203.0.113.9', '198.51.100.7', 'send-otp/?'):
            self.assertNotIn(secret, text)

    def test_healthz_is_not_logged(self):
        with self.assertNoLogs('hh.request', level='INFO'):
            self.assertEqual(Client().get('/healthz').status_code, 200)

    def test_request_id_is_echoed_and_logged(self):
        response, line = self.one_line(lambda: Client().get('/api/v1/hostels/'))
        self.assertEqual(response['X-Request-ID'], line['request_id'])
        self.assertRegex(line['request_id'], r'^[a-f0-9]{32}$')

    def test_valid_incoming_request_id_is_kept(self):
        response, line = self.one_line(
            lambda: Client().get('/api/v1/hostels/', HTTP_X_REQUEST_ID='abc-123_DEF.456'))
        self.assertEqual(response['X-Request-ID'], 'abc-123_DEF.456')
        self.assertEqual(line['request_id'], 'abc-123_DEF.456')

    def test_unsafe_incoming_request_id_is_replaced(self):
        response, line = self.one_line(
            lambda: Client().get('/api/v1/hostels/', HTTP_X_REQUEST_ID='bad id\twith spaces'))
        self.assertNotEqual(response['X-Request-ID'], 'bad id\twith spaces')
        self.assertRegex(line['request_id'], r'^[a-f0-9]{32}$')

    def test_server_error_logs_level_and_exception_class_only(self):
        client = Client(raise_request_exception=False)
        with mock.patch('apps.hostels.views.HostelViewSet.list', side_effect=RuntimeError('boom secret detail')):
            _, line = self.one_line(lambda: client.get('/api/v1/hostels/'))
        self.assertEqual(line['status'], 500)
        self.assertEqual(line['level'], 'error')
        self.assertEqual(line['exc'], 'RuntimeError')
        self.assertNotIn('boom secret detail', json.dumps(line))

    def test_query_count_matches_the_database(self):
        with CaptureQueriesContext(connection) as ctx:
            _, line = self.one_line(lambda: Client().get('/api/v1/hostels/'))
        self.assertEqual(line['db_queries'], len(ctx.captured_queries))
        self.assertGreaterEqual(line['db_ms'], 0)

    def test_user_id_is_logged_for_an_authenticated_request(self):
        owner = Owner.objects.create_user(email='logged.in@example.com', display_name='L', password='pass12345')
        token = str(RefreshToken.for_user(owner).access_token)
        _, line = self.one_line(
            lambda: APIClient().get('/api/v1/auth/me/', HTTP_AUTHORIZATION=f'Bearer {token}'))
        self.assertEqual(line['status'], 200)
        self.assertEqual(line['user_id'], str(owner.pk))
        self.assertNotIn('logged.in@example.com', json.dumps(line))
        self.assertNotIn(token, json.dumps(line))


class RequestIdInOtherLogsTests(TestCase):
    def test_request_id_is_available_to_other_log_records(self):
        from apps.core.observability import RequestIdFilter, current_request_id
        record = mock.Mock()
        self.assertEqual(current_request_id(), '-')
        self.assertTrue(RequestIdFilter().filter(record))
        self.assertEqual(record.request_id, '-')


class OtpLogLinesHoldNoIdentifierTests(TestCase):
    def test_owner_otp_logs_do_not_contain_the_recipient(self):
        from django.test import override_settings
        from apps.owners.services import OTPService
        with override_settings(EMAIL_HOST_USER='u', EMAIL_HOST_PASSWORD='p'), \
                mock.patch('apps.owners.services.send_mail'), \
                self.assertLogs('apps.owners.services', level='INFO') as logs:
            OTPService.send_otp(EMAIL, '123456', 'signup', 'email')
        self.assertFalse([line for line in logs.output if EMAIL in line], logs.output)

    def test_owner_sms_logs_do_not_contain_the_number(self):
        from django.test import override_settings
        from apps.owners.services import OTPService
        ok = mock.Mock(status_code=201, text='')
        with override_settings(TWILIO_ACCOUNT_SID='ACx', TWILIO_AUTH_TOKEN='t', TWILIO_FROM_NUMBER='+1'), \
                mock.patch('requests.post', return_value=ok), \
                self.assertLogs('apps.owners.services', level='INFO') as logs:
            OTPService.send_otp('+919876543210', '123456', 'signup', 'phone')
        self.assertFalse([line for line in logs.output if '9876543210' in line], logs.output)

    def test_email_otp_service_logs_do_not_contain_the_recipient(self):
        from django.test import override_settings
        from apps.otp_auth.services import OTPService
        with override_settings(EMAIL_HOST_USER='u', EMAIL_HOST_PASSWORD='p'), \
                mock.patch('apps.otp_auth.services.send_mail'), \
                self.assertLogs('apps.otp_auth.services', level='INFO') as logs:
            OTPService._send_email(EMAIL, '123456')
        self.assertFalse([line for line in logs.output if EMAIL in line], logs.output)

    def test_email_otp_failure_log_does_not_contain_the_recipient(self):
        from django.test import override_settings
        from apps.otp_auth.services import OTPService
        boom = Exception(f'refused recipient {EMAIL}')
        with override_settings(EMAIL_HOST_USER='u', EMAIL_HOST_PASSWORD='p'), \
                mock.patch('apps.otp_auth.services.send_mail', side_effect=boom), \
                self.assertLogs('apps.otp_auth.services', level='INFO') as logs, \
                self.assertRaises(Exception):
            OTPService._send_email(EMAIL, '123456')
        self.assertFalse([line for line in logs.output if re.search(r'private\.person|@example', line)], logs.output)


class PiiMaskFilterTests(TestCase):
    def make_record(self, msg, args=(), exc=None):
        import logging
        import sys
        exc_info = None
        if exc is not None:
            try:
                raise exc
            except Exception:
                exc_info = sys.exc_info()
        return logging.LogRecord('apps.x', logging.ERROR, __file__, 1, msg, args, exc_info)

    def test_message_args_and_traceback_are_masked(self):
        from apps.core.observability import PiiMaskFilter
        record = self.make_record('sent to %s ok', (EMAIL,), exc=Exception(f'refused {EMAIL} +919876543210'))
        self.assertTrue(PiiMaskFilter().filter(record))
        rendered = record.getMessage() + (record.exc_text or '')
        self.assertNotIn(EMAIL, rendered)
        self.assertNotIn('9876543210', rendered)
        self.assertIn('ok', rendered)

    def test_the_console_handler_uses_the_filter(self):
        import logging
        handler = logging.getLogger('apps').handlers[0]
        names = {type(f).__name__ for f in handler.filters}
        self.assertEqual(names, {'RequestIdFilter', 'PiiMaskFilter'})
