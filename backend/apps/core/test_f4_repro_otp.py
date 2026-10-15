"""
F4 Part 1: tests that REPRODUCE the OTP, email and throttling findings (G02, G04, G05). They assert the
correct behaviour, so they are expected to FAIL on today's code and to pass after F4 Part 2.

Part 2 will adapt the way the email is stubbed (the SMTP call is replaced by an HTTPS provider call),
but not what is asserted.
"""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.owners.models import OTPRecord
from apps.owners.services import OTPService

SEND = '/api/v1/auth/send-otp/'
VERIFY = '/api/v1/auth/verify-otp/'


def post(path, payload, forwarded_for):
    client = APIClient()
    client.raise_request_exception = False
    return client.post(path, payload, format='json', HTTP_X_FORWARDED_FOR=forwarded_for)


def send(email, forwarded_for):
    return post(SEND, {'identifier': email, 'identifier_type': 'email', 'purpose': 'signup'}, forwarded_for)


def verify(email, code, forwarded_for):
    return post(VERIFY, {'identifier': email, 'identifier_type': 'email', 'otp': code, 'purpose': 'signup'}, forwarded_for)


@override_settings(EMAIL_HOST_USER='mailer', EMAIL_HOST_PASSWORD='not-a-real-password')
class OtpTests(TestCase):
    def setUp(self):
        cache.clear()  # throttle counters live in the process-local cache and would leak between tests

    def test_otp_is_not_stored_with_the_slow_password_hash(self):
        # G04: 1,000,000 PBKDF2 rounds per OTP (about 0.6 s of CPU each on the dev machine) protect nothing,
        # because only 10^6 six-digit codes exist; an attempt cap is the real protection.
        _, record = OTPService.create_otp('hash@example.test', 'signup')
        self.assertFalse(record.otp_code.startswith('pbkdf2_'), 'OTP codes need a fast keyed hash, not PBKDF2')

    def test_otp_digits_do_not_come_from_the_random_module(self):
        with mock.patch('random.choices', side_effect=AssertionError('random.choices was used for an OTP')):
            OTPService.generate_otp_code()

    def test_a_second_send_for_the_same_address_is_refused_during_the_cooldown(self):
        # G05: nothing limits how often one victim's inbox can be mailed, except one counter per client address
        self.assertEqual(send('victim@example.test', '198.51.100.1').status_code, 200)
        again = send('victim@example.test', '198.51.100.2')
        self.assertEqual(again.status_code, 429)

    def test_a_spoofed_forwarded_for_header_does_not_get_a_fresh_allowance(self):
        # G05: behind exactly one trusted proxy the client address is the LAST forwarded-for entry; the
        # entries before it are written by the client. DRF without NUM_PROXIES keys on the whole header.
        codes = [send(f'bomb{i}@example.test', f'10.9.9.{i}, 203.0.113.9').status_code for i in range(25)]
        self.assertIn(429, codes, 'one real client sent 25 OTP emails in a minute and was never limited')

    def test_sending_and_verifying_do_not_share_one_limit(self):
        # G05: both views use throttle scope "otp" (5 a minute), so three sends plus three verifies lock a
        # user out of verifying, and a user who is verifying can be locked out of resending.
        for i in range(3):
            self.assertEqual(send(f'mix{i}@example.test', '203.0.113.7').status_code, 200)
        verify_codes = [verify(f'mix{i}@example.test', '000000', '203.0.113.7').status_code for i in range(3)]
        self.assertNotIn(429, verify_codes)

    def test_five_wrong_guesses_lock_the_code_even_if_the_client_address_changes(self):
        # G05: the OTP model has an attempt counter nobody reads; a six-digit code can be guessed by rotating addresses
        email = 'guess@example.test'
        code, _ = OTPService.create_otp(email, 'signup')
        wrong = '000000' if code != '000000' else '000001'
        for i in range(12):
            verify(email, wrong, f'198.51.100.{i + 10}')
        final = verify(email, code, '198.51.100.99')
        self.assertNotEqual(final.status_code, 200, 'the right code was accepted after 12 wrong guesses')

    def test_otp_record_counts_its_attempts(self):
        self.assertIn('attempts', [f.name for f in OTPRecord._meta.get_fields()])
