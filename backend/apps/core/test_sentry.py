from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from apps.core.sentry_config import (
    init_sentry, mask_text, scrub_breadcrumb, scrub_event,
)


def sample_event():
    return {
        'message': 'Failed for person@example.com phone +91 98765 43210',
        'logentry': {'message': 'Failed for person@example.com', 'formatted': 'Failed for person@example.com'},
        'exception': {'values': [{'type': 'Exception', 'value': 'refused person@example.com'}]},
        'request': {
            'url': 'https://api.example.com/api/v1/hostels/?email=person@example.com',
            'query_string': 'email=person@example.com',
            'method': 'POST',
            'headers': {
                'Authorization': 'Bearer abc.def.ghi', 'cookie': 'sessionid=1', 'X-Forwarded-For': '1.2.3.4',
                'Content-Type': 'application/json', 'X-Request-ID': 'abc12345',
            },
            'cookies': {'sessionid': '1'},
            'data': {'otp': '123456', 'password': 'p', 'token': 't', 'identifier': 'person@example.com'},
        },
        'user': {'id': '5', 'email': 'person@example.com', 'ip_address': '1.2.3.4', 'username': 'x'},
        'extra': {'otp': '123456', 'nested': {'Password': 'p', 'Token': 'abc', 'safe': 'ok'}},
        'contexts': {'custom': {'verification_token': 'zzz', 'safe': 'ok'}},
        'breadcrumbs': {'values': [{'category': 'log', 'message': 'sent to person@example.com'}]},
    }


class ScrubEventTests(SimpleTestCase):
    def setUp(self):
        self.event = scrub_event(sample_event(), {})

    def test_authorization_cookie_and_forwarded_headers_are_removed(self):
        headers = {k.lower() for k in self.event['request']['headers']}
        self.assertNotIn('authorization', headers)
        self.assertNotIn('cookie', headers)
        self.assertNotIn('x-forwarded-for', headers)
        self.assertIn('content-type', headers)
        self.assertNotIn('cookies', self.event['request'])

    def test_request_body_and_query_string_are_removed(self):
        self.assertNotIn('data', self.event['request'])
        self.assertNotIn('query_string', self.event['request'])
        self.assertEqual(self.event['request']['url'], 'https://api.example.com/api/v1/hostels/')

    def test_sensitive_named_fields_are_filtered_everywhere(self):
        self.assertEqual(self.event['extra']['otp'], '[Filtered]')
        self.assertEqual(self.event['extra']['nested']['Password'], '[Filtered]')
        self.assertEqual(self.event['extra']['nested']['Token'], '[Filtered]')
        self.assertEqual(self.event['extra']['nested']['safe'], 'ok')
        self.assertEqual(self.event['contexts']['custom']['verification_token'], '[Filtered]')

    def test_emails_and_phone_numbers_are_masked_in_text(self):
        text = repr(self.event)
        self.assertNotIn('person@example.com', text)
        self.assertNotIn('98765', text)

    def test_user_keeps_only_the_id(self):
        self.assertEqual(self.event['user'], {'id': '5'})

    def test_noise_events_are_dropped(self):
        event = {'logger': 'django.security.DisallowedHost', 'message': 'Invalid HTTP_HOST header'}
        self.assertIsNone(scrub_event(event, {}))

    def test_http404_is_dropped(self):
        from django.http import Http404
        hint = {'exc_info': (Http404, Http404('x'), None)}
        self.assertIsNone(scrub_event({'message': 'x'}, hint))

    def test_breadcrumb_text_is_masked(self):
        crumb = scrub_breadcrumb({'category': 'log', 'message': 'sent to person@example.com'}, {})
        self.assertNotIn('person@example.com', repr(crumb))


class MaskTextTests(SimpleTestCase):
    def test_masks_emails_and_long_digit_runs(self):
        out = mask_text('a.b+c@Mail.example.co.in called 9876543210 and +919876543210 order 42')
        self.assertNotIn('@', out)
        self.assertNotIn('9876543210', out)
        self.assertIn('order 42', out)


class InitSentryTests(SimpleTestCase):
    def test_without_a_dsn_nothing_is_initialised(self):
        with mock.patch('sentry_sdk.init') as init:
            self.assertFalse(init_sentry(dsn='', environment='x', release='r', traces_sample_rate=0.0))
        init.assert_not_called()

    def test_privacy_options_are_set(self):
        with mock.patch('sentry_sdk.init') as init:
            self.assertTrue(init_sentry(dsn='https://k@o0.ingest.sentry.io/1', environment='production',
                                        release='abc1234', traces_sample_rate=0.0))
        kwargs = init.call_args.kwargs
        self.assertIs(kwargs['send_default_pii'], False)
        self.assertIs(kwargs['include_local_variables'], False)
        self.assertEqual(kwargs['max_request_body_size'], 'never')
        self.assertEqual(kwargs['release'], 'abc1234')
        self.assertEqual(kwargs['environment'], 'production')
        self.assertEqual(kwargs['traces_sample_rate'], 0.0)
        self.assertIs(kwargs['before_send'], scrub_event)
        self.assertIs(kwargs['before_breadcrumb'], scrub_breadcrumb)


class SentryTestCommandTests(SimpleTestCase):
    def test_refuses_without_a_dsn(self):
        with self.settings(SENTRY_DSN=''):
            with self.assertRaises(CommandError) as ctx:
                call_command('sentry_test', stdout=StringIO())
        self.assertIn('SENTRY_DSN', str(ctx.exception))

    def test_sends_one_synthetic_event(self):
        out = StringIO()
        with self.settings(SENTRY_DSN='https://k@o0.ingest.sentry.io/1'), \
                mock.patch('sentry_sdk.capture_exception') as capture, \
                mock.patch('sentry_sdk.flush'), \
                mock.patch('sentry_sdk.set_tag') as set_tag:
            call_command('sentry_test', stdout=out)
        capture.assert_called_once()
        set_tag.assert_any_call('synthetic', 'true')
