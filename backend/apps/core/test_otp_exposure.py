from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

CODE = '482915'
URL = '/api/v1/auth/send-otp/'
EMAIL = {'identifier': 'new.user@example.com', 'identifier_type': 'email', 'purpose': 'signup'}
PHONE = {'identifier': '9876543210', 'identifier_type': 'phone', 'purpose': 'signup'}


def fixed_code():
    return mock.patch('apps.owners.services.OTPService.generate_otp_code', return_value=CODE)


class OtpExposureTests(APITestCase):
    def setUp(self):
        cache.clear()  # the 'otp' throttle uses the per-process cache

    @override_settings(DEBUG=False, EXPOSE_DEV_OTP=False, EMAIL_HOST_USER='')
    def test_otp_is_not_returned_when_email_is_not_configured(self):
        with fixed_code():
            response = self.client.post(URL, EMAIL, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(CODE.encode(), response.content)

    @override_settings(DEBUG=True, EXPOSE_DEV_OTP=False, EMAIL_HOST_USER='')
    def test_debug_alone_does_not_expose_the_otp(self):
        with fixed_code():
            response = self.client.post(URL, EMAIL, format='json')
        self.assertNotIn(CODE.encode(), response.content)

    @override_settings(DEBUG=True, EXPOSE_DEV_OTP=True, EMAIL_HOST_USER='')
    def test_otp_is_returned_only_with_debug_and_the_explicit_flag(self):
        with fixed_code():
            response = self.client.post(URL, EMAIL, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(CODE.encode(), response.content)

    @override_settings(DEBUG=False, EXPOSE_DEV_OTP=False, EMAIL_HOST_USER='')
    def test_otp_is_not_written_to_the_logs(self):
        with fixed_code(), self.assertLogs('apps.owners.services', level='INFO') as logs:
            self.client.post(URL, EMAIL, format='json')
        self.assertFalse([line for line in logs.output if CODE in line])

    @override_settings(DEBUG=False, EMAIL_HOST_USER='u', EMAIL_HOST_PASSWORD='p')
    def test_smtp_error_text_is_not_returned_to_the_client(self):
        boom = Exception('auth failed for smtp.secret-host.example')
        with fixed_code(), mock.patch('apps.owners.services.send_mail', side_effect=boom):
            response = self.client.post(URL, EMAIL, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'secret-host', response.content)

    @override_settings(DEBUG=False, TWILIO_ACCOUNT_SID='AC1', TWILIO_AUTH_TOKEN='t', TWILIO_FROM_NUMBER='+1')
    def test_sms_provider_error_text_is_not_returned_to_the_client(self):
        provider = mock.Mock(status_code=500, text='twilio internal detail')
        with fixed_code(), mock.patch('requests.post', return_value=provider):
            response = self.client.post(URL, PHONE, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'twilio internal detail', response.content)

    def test_unexpected_error_returns_no_traceback(self):
        with mock.patch('apps.owners.services.OTPService.create_otp', side_effect=Exception('boom internal')):
            response = self.client.post(URL, EMAIL, format='json')
        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertNotIn('traceback', body)
        self.assertNotIn(b'boom internal', response.content)
        self.assertTrue(body.get('message'))
