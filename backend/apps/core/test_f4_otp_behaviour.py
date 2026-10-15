"""
F4 Part 2: behaviour of the email provider, the OTP rules and the outbound-call helper.
No real email, SMS or gateway call is ever made.
"""
from datetime import timedelta
from unittest import mock

import requests
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.core import mailer, outbound
from apps.owners.models import OTPRecord
from apps.owners.services import OTPRateLimited, OTPService
from apps.core.test_f4_repro_otp import SEND, post, send, verify

BREVO = dict(EMAIL_API_PROVIDER='brevo', EMAIL_API_KEY='key-not-real', DEFAULT_FROM_EMAIL='Hostel Hunt <sender@example.test>')


def provider_reply(status=201):
    return mock.Mock(status_code=status, text='')


class MailerTests(SimpleTestCase):
    @override_settings(**BREVO)
    def test_brevo_request_shape_and_timeout(self):
        with mock.patch('requests.post', return_value=provider_reply()) as sent:
            mailer.send_email('student@example.test', 'Code', 'Your code is 123456')
        url = sent.call_args.args[0]
        kwargs = sent.call_args.kwargs
        self.assertEqual(url, 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(kwargs['headers']['api-key'], 'key-not-real')
        body = kwargs['json']
        self.assertEqual(body['sender'], {'name': 'Hostel Hunt', 'email': 'sender@example.test'})
        self.assertEqual(body['to'], [{'email': 'student@example.test'}])
        self.assertIn('123456', body['textContent'])
        self.assertTrue(body['htmlContent'])
        connect, read = kwargs['timeout']
        self.assertLessEqual(connect + read, 6)

    @override_settings(EMAIL_API_PROVIDER='resend', EMAIL_API_KEY='key-not-real', DEFAULT_FROM_EMAIL='Hostel Hunt <sender@example.test>')
    def test_resend_request_shape(self):
        with mock.patch('requests.post', return_value=provider_reply(200)) as sent:
            mailer.send_email('student@example.test', 'Code', 'Your code is 123456')
        self.assertEqual(sent.call_args.args[0], 'https://api.resend.com/emails')
        self.assertEqual(sent.call_args.kwargs['headers']['Authorization'], 'Bearer key-not-real')
        self.assertEqual(sent.call_args.kwargs['json']['to'], ['student@example.test'])

    @override_settings(**BREVO)
    def test_failures_are_mapped_and_never_leak_detail(self):
        cases = [
            (requests.Timeout(), mailer.EmailError.TIMEOUT),
            (requests.ConnectionError(), mailer.EmailError.UNREACHABLE),
            (provider_reply(401), mailer.EmailError.CREDENTIALS),
            (provider_reply(403), mailer.EmailError.CREDENTIALS),
            (provider_reply(429), mailer.EmailError.PROVIDER_DOWN),
            (provider_reply(503), mailer.EmailError.PROVIDER_DOWN),
            (provider_reply(400), mailer.EmailError.REJECTED),
        ]
        for outcome, kind in cases:
            effect = {'side_effect': outcome} if isinstance(outcome, Exception) else {'return_value': outcome}
            with mock.patch('requests.post', **effect), self.assertRaises(mailer.EmailError) as caught:
                mailer.send_email('student@example.test', 'Code', 'Your code is 123456')
            self.assertEqual(caught.exception.kind, kind)

    @override_settings(EMAIL_API_PROVIDER='', EMAIL_API_KEY='', EMAIL_HOST_USER='')
    def test_nothing_configured_is_reported(self):
        self.assertFalse(mailer.is_configured())
        with self.assertRaises(mailer.EmailError) as caught:
            mailer.send_email('student@example.test', 'Code', 'x')
        self.assertEqual(caught.exception.kind, mailer.EmailError.NOT_CONFIGURED)

    @override_settings(EMAIL_API_PROVIDER='nope', EMAIL_API_KEY='k')
    def test_unknown_provider_is_a_configuration_error(self):
        with self.assertRaises(mailer.EmailError) as caught:
            mailer.send_email('student@example.test', 'Code', 'x')
        self.assertEqual(caught.exception.kind, mailer.EmailError.NOT_CONFIGURED)

    @override_settings(EMAIL_API_PROVIDER='', EMAIL_API_KEY='', EMAIL_HOST_USER='u', EMAIL_HOST_PASSWORD='p')
    def test_smtp_fallback_and_its_timeout(self):
        with mock.patch('apps.core.mailer.send_mail') as smtp:
            mailer.send_email('student@example.test', 'Code', 'x')
        smtp.assert_called_once()
        with mock.patch('apps.core.mailer.send_mail', side_effect=TimeoutError()), self.assertRaises(mailer.EmailError) as caught:
            mailer.send_email('student@example.test', 'Code', 'x')
        self.assertEqual(caught.exception.kind, mailer.EmailError.TIMEOUT)


class OutboundTests(SimpleTestCase):
    def test_a_missing_or_huge_timeout_is_refused(self):
        for bad in (0, -1, 11, (2, 60), (None, 3)):
            with self.assertRaises(ValueError, msg=repr(bad)):
                outbound.post('https://example.test', timeout=bad)

    def test_the_default_timeout_is_applied(self):
        with mock.patch('requests.post') as sent:
            outbound.post('https://example.test')
        self.assertEqual(sent.call_args.kwargs['timeout'], outbound.SHORT)

    def test_a_session_applies_its_default_timeout_to_every_request(self):
        session = outbound.TimeoutSession((3, 10))
        with mock.patch('requests.Session.request') as base:
            session.post('https://example.test', data={})
        self.assertEqual(base.call_args.kwargs['timeout'], (3, 10))

    def test_the_razorpay_client_uses_the_timeout_session(self):
        from apps.payments.services import razorpay_client
        self.assertIs(razorpay_client._get_client().session, outbound.gateway_session())
        self.assertIsInstance(outbound.gateway_session(), outbound.TimeoutSession)


@override_settings(**BREVO)
class OtpFlowTests(TestCase):
    def setUp(self):
        cache.clear()

    def send_ok(self, email='new@example.test', ip='198.51.100.1'):
        with mock.patch('requests.post', return_value=provider_reply()):
            return send(email, ip)

    def test_provider_down_gives_a_clean_503_and_does_not_burn_the_senders_allowance(self):
        with mock.patch('requests.post', side_effect=requests.Timeout()):
            response = send('new@example.test', '198.51.100.1')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'brevo', response.content.lower())
        self.assertFalse(OTPRecord.objects.filter(identifier='new@example.test').exists())
        self.assertEqual(self.send_ok().status_code, 200)  # an immediate retry is not blocked by the cooldown

    def test_cooldown_answers_429_with_retry_after_and_keeps_the_first_code_valid(self):
        self.assertEqual(self.send_ok().status_code, 200)
        code_row = OTPRecord.objects.get(identifier='new@example.test')
        again = self.send_ok(ip='198.51.100.2')
        self.assertEqual(again.status_code, 429)
        self.assertTrue(1 <= int(again['Retry-After']) <= 61)
        code_row.refresh_from_db()
        self.assertFalse(code_row.is_used)

    def test_five_sends_per_hour_then_a_wait(self):
        for n in range(5):
            OTPRecord.objects.create(
                identifier='new@example.test', otp_code='x', purpose='signup', is_used=True,
                expires_at=timezone.now() + timedelta(minutes=5),
            )
            OTPRecord.objects.filter(identifier='new@example.test').update(created_at=timezone.now() - timedelta(minutes=10 + n))
        response = self.send_ok()
        self.assertEqual(response.status_code, 429)

    def test_the_cooldown_is_per_address_and_purpose(self):
        self.send_ok('one@example.test')
        self.assertEqual(self.send_ok('two@example.test', '198.51.100.3').status_code, 200)

    def test_right_code_after_wrong_ones_still_works_below_the_cap(self):
        code, _ = OTPService.create_otp('flow@example.test', 'signup')
        for i in range(OTPService.MAX_ATTEMPTS - 1):
            self.assertEqual(verify('flow@example.test', '000000' if code != '000000' else '111111', f'198.51.100.{i + 20}').status_code, 400)
        self.assertEqual(verify('flow@example.test', code, '198.51.100.90').status_code, 200)

    def test_the_cap_locks_even_the_right_code_and_says_to_ask_again(self):
        code, record = OTPService.create_otp('lock@example.test', 'signup')
        wrong = '000000' if code != '000000' else '111111'
        last = None
        for i in range(OTPService.MAX_ATTEMPTS):
            last = verify('lock@example.test', wrong, f'198.51.100.{i + 30}')
        self.assertIn('Too many wrong attempts', last.json()['errors']['otp'])
        record.refresh_from_db()
        self.assertTrue(record.is_used)
        self.assertEqual(verify('lock@example.test', code, '198.51.100.99').status_code, 400)

    def test_a_code_issued_before_the_release_still_verifies_once(self):
        OTPRecord.objects.create(
            identifier='legacy@example.test', otp_code=make_password('424242'), purpose='signup',
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        self.assertEqual(verify('legacy@example.test', '424242', '198.51.100.7').status_code, 200)

    def test_the_hash_depends_on_the_address_and_purpose(self):
        a = OTPService.hash_code('a@example.test', 'signup', '123456')
        self.assertNotEqual(a, OTPService.hash_code('b@example.test', 'signup', '123456'))
        self.assertNotEqual(a, OTPService.hash_code('a@example.test', 'forgot_password', '123456'))
        self.assertEqual(len(a), 64)

    def test_codes_are_six_digits(self):
        for _ in range(50):
            self.assertRegex(OTPService.generate_otp_code(), r'^\d{6}$')

    def test_create_otp_raises_a_typed_error_when_rate_limited(self):
        OTPService.create_otp('typed@example.test', 'signup')
        with self.assertRaises(OTPRateLimited) as caught:
            OTPService.create_otp('typed@example.test', 'signup')
        self.assertGreater(caught.exception.retry_after, 0)

    def test_verify_has_its_own_ip_limit_separate_from_send(self):
        codes = [verify('x@example.test', '000000', '203.0.113.50').status_code for _ in range(31)]
        self.assertEqual(codes[:30].count(429), 0)
        self.assertEqual(codes[30], 429)
        self.assertEqual(self.send_ok('y@example.test', '203.0.113.50').status_code, 200)
