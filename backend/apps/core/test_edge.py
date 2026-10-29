"""
Phase 3, Part 4: behind an edge (Cloudflare in front of Render).

  * the request log carries a masked client identifier, so the two-phone test in docs/EDGE_SETUP.md can prove the
    hop count (TRUSTED_PROXY_COUNT) is right;
  * EDGE_SHARED_SECRET rejects requests that bypass the edge, except the health checks;
  * Cache-Control: s-maxage on the public lists, private + no-store on everything else.
"""
import json
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest
from django.test import Client, SimpleTestCase, TestCase, override_settings

from apps.core import observability

PHONE_A = '198.51.100.7'
PHONE_B = '203.0.113.50'
CLOUDFLARE_1 = '172.70.1.1'
CLOUDFLARE_2 = '172.71.9.9'
RATES = {'anon': '60/min', 'user': '120/min', 'otp_send': '20/min', 'otp_verify': '30/min', 'photo': '10/hour'}


def drf_settings(proxies):
    config = dict(settings.REST_FRAMEWORK)
    config['NUM_PROXIES'] = proxies
    return config


def request_with(xff=None, remote='10.0.0.1'):
    request = HttpRequest()
    request.META['REMOTE_ADDR'] = remote
    if xff is not None:
        request.META['HTTP_X_FORWARDED_FOR'] = xff
    return request


class ClientIdentifierTests(SimpleTestCase):
    """The identifier is the same address DRF's rate limits see, hashed with a daily key."""

    def ident(self, xff, proxies):
        with override_settings(REST_FRAMEWORK=drf_settings(proxies)):
            return observability.client_hash(request_with(xff))

    def test_it_is_eight_hex_characters_and_never_the_address(self):
        value = self.ident(PHONE_A, 1)
        self.assertRegex(value, r'^[0-9a-f]{8}$')
        self.assertNotIn(PHONE_A, value)

    def test_render_only_two_phones_are_two_identifiers(self):
        self.assertNotEqual(self.ident(PHONE_A, 1), self.ident(PHONE_B, 1))

    def test_cloudflare_plus_render_with_two_proxies_counted_two_phones_are_two_identifiers(self):
        a = self.ident(f'{PHONE_A}, {CLOUDFLARE_1}', 2)
        b = self.ident(f'{PHONE_B}, {CLOUDFLARE_1}', 2)  # same Cloudflare data centre, different phone
        self.assertNotEqual(a, b)

    def test_the_same_phone_through_two_cloudflare_servers_stays_one_identifier(self):
        a = self.ident(f'{PHONE_A}, {CLOUDFLARE_1}', 2)
        b = self.ident(f'{PHONE_A}, {CLOUDFLARE_2}', 2)
        self.assertEqual(a, b)

    def test_the_wrong_hop_count_makes_different_phones_look_identical(self):
        """This is what the two-phone test in EDGE_SETUP.md catches: Cloudflare in front but TRUSTED_PROXY_COUNT=1."""
        a = self.ident(f'{PHONE_A}, {CLOUDFLARE_1}', 1)
        b = self.ident(f'{PHONE_B}, {CLOUDFLARE_1}', 1)
        self.assertEqual(a, b)

    def test_the_identifier_changes_from_one_day_to_the_next(self):
        request = request_with(PHONE_A)
        with override_settings(REST_FRAMEWORK=drf_settings(1)):
            with mock.patch.object(observability, '_today', return_value='2026-10-29'):
                today = observability.client_hash(request)
            with mock.patch.object(observability, '_today', return_value='2026-10-30'):
                tomorrow = observability.client_hash(request)
        self.assertNotEqual(today, tomorrow)

    def test_it_depends_on_the_secret_key(self):
        with override_settings(REST_FRAMEWORK=drf_settings(1)):
            first = observability.client_hash(request_with(PHONE_A))
            with override_settings(SECRET_KEY='another-secret-key-' + 'y' * 40):
                second = observability.client_hash(request_with(PHONE_A))
        self.assertNotEqual(first, second)

    def test_a_request_with_no_address_gets_a_stable_placeholder_not_an_error(self):
        request = HttpRequest()
        self.assertRegex(observability.client_hash(request), r'^[0-9a-f]{8}$|^-$')


class RequestLogClientFieldTests(TestCase):
    def setUp(self):
        cache.clear()

    def line(self, **headers):
        with self.assertLogs('hh.request', level='INFO') as logs:
            Client().get('/api/v1/hostels/', **headers)
        return json.loads(logs.records[0].getMessage())

    def test_the_log_line_has_a_client_field_and_no_address(self):
        line = self.line(HTTP_X_FORWARDED_FOR=f'{PHONE_A}, {CLOUDFLARE_1}')
        self.assertRegex(line['client'], r'^[0-9a-f]{8}$')
        text = json.dumps(line)
        self.assertNotIn(PHONE_A, text)
        self.assertNotIn(CLOUDFLARE_1, text)

    @override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': 2})
    def test_two_phones_behind_the_edge_appear_as_two_clients(self):
        a = self.line(HTTP_X_FORWARDED_FOR=f'{PHONE_A}, {CLOUDFLARE_1}')
        b = self.line(HTTP_X_FORWARDED_FOR=f'{PHONE_B}, {CLOUDFLARE_1}')
        self.assertNotEqual(a['client'], b['client'])
        self.assertEqual(a['xff_hops'], 2)

    @override_settings(LOG_CLIENT_ID=False)
    def test_it_can_be_switched_off(self):
        self.assertNotIn('client', self.line(HTTP_X_FORWARDED_FOR=PHONE_A))


class EdgeSecretTests(TestCase):
    SECRET = 'edge-secret-for-tests-0123456789'

    def setUp(self):
        cache.clear()

    def test_without_a_configured_secret_everything_passes(self):
        self.assertEqual(Client().get('/api/v1/hostels/').status_code, 200)

    @override_settings(EDGE_SHARED_SECRET=SECRET)
    def test_a_request_without_the_header_is_refused(self):
        response = Client().get('/api/v1/hostels/')
        self.assertEqual(response.status_code, 403)

    @override_settings(EDGE_SHARED_SECRET=SECRET)
    def test_a_wrong_or_empty_header_is_refused(self):
        self.assertEqual(Client().get('/api/v1/hostels/', HTTP_X_EDGE_SECRET='nope').status_code, 403)
        self.assertEqual(Client().get('/api/v1/hostels/', HTTP_X_EDGE_SECRET='').status_code, 403)

    @override_settings(EDGE_SHARED_SECRET=SECRET)
    def test_the_right_header_passes(self):
        self.assertEqual(Client().get('/api/v1/hostels/', HTTP_X_EDGE_SECRET=self.SECRET).status_code, 200)

    @override_settings(EDGE_SHARED_SECRET=SECRET)
    def test_the_health_checks_are_exempt_so_render_can_still_check_the_service(self):
        self.assertEqual(Client().get('/healthz').status_code, 200)
        self.assertEqual(Client().get('/readyz').status_code, 200)

    @override_settings(EDGE_SHARED_SECRET=SECRET)
    def test_other_methods_and_paths_are_refused_too(self):
        self.assertEqual(Client().post('/api/v1/payments/webhook/', '{}', content_type='application/json').status_code, 403)
        self.assertEqual(Client().get('/admin/login/').status_code, 403)

    @override_settings(EDGE_SHARED_SECRET=SECRET)
    def test_the_refusal_reveals_nothing_about_the_secret(self):
        response = Client().get('/api/v1/hostels/', HTTP_X_EDGE_SECRET='wrong')
        body = response.content.decode()
        self.assertNotIn(self.SECRET, body)
        self.assertNotIn('X-Edge-Secret', body)
        self.assertNotIn(self.SECRET, str(dict(response.headers)))

    @override_settings(EDGE_SHARED_SECRET=SECRET)
    def test_the_secret_never_reaches_the_request_log(self):
        with self.assertLogs('hh.request', level='INFO') as logs:
            Client().get('/api/v1/hostels/', HTTP_X_EDGE_SECRET=self.SECRET)
            Client().get('/api/v1/hostels/', HTTP_X_EDGE_SECRET='wrong-guess')
        text = ' '.join(r.getMessage() for r in logs.records)
        self.assertNotIn(self.SECRET, text)
        self.assertNotIn('wrong-guess', text)
        statuses = [json.loads(r.getMessage())['status'] for r in logs.records]
        self.assertEqual(statuses, [200, 403])  # the rejection is in the log, with its status

    def test_the_comparison_is_constant_time(self):
        from pathlib import Path
        source = (Path(settings.BASE_DIR) / 'apps' / 'core' / 'edge.py').read_text(encoding='utf-8')
        self.assertIn('compare_digest', source)

    def test_it_sits_right_after_the_health_check(self):
        middleware = settings.MIDDLEWARE
        self.assertEqual(middleware.index('apps.core.edge.EdgeSecretMiddleware'),
                         middleware.index('apps.core.health.HealthzMiddleware') + 1)

    def test_the_variable_is_documented(self):
        from pathlib import Path
        text = (Path(settings.BASE_DIR) / '.env.example').read_text(encoding='utf-8')
        self.assertRegex(text, r'(?m)^#?\s*EDGE_SHARED_SECRET=\s*$')


class CacheControlTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_the_anonymous_public_list_gets_max_age_and_s_maxage(self):
        header = Client().get('/api/v1/hostels/')['Cache-Control']
        self.assertIn('public', header)
        self.assertIn('max-age=30', header)
        self.assertIn('s-maxage=30', header)

    def test_the_city_list_gets_the_longer_lifetime(self):
        header = Client().get('/api/v1/cities/')['Cache-Control']
        self.assertIn('s-maxage=120', header)

    def test_a_request_with_a_token_is_private_and_never_stored(self):
        header = Client().get('/api/v1/hostels/', HTTP_AUTHORIZATION='Bearer abc')['Cache-Control']
        self.assertIn('private', header)
        self.assertIn('no-store', header)
        self.assertNotIn('s-maxage', header)
        self.assertNotIn('public', header)

    def test_every_other_api_answer_is_private_and_no_store(self):
        for path in ('/api/v1/auth/me/', '/api/v1/payments/list/', '/api/v1/bookings/my/', '/api/v1/dashboard/stats/'):
            response = Client().get(path)  # 401 for an anonymous caller: errors must not be cacheable either
            header = response['Cache-Control']
            self.assertIn('private', header, path)
            self.assertIn('no-store', header, path)
            self.assertNotIn('public', header, path)

    def test_a_write_is_private_and_no_store(self):
        response = Client().post('/api/v1/auth/login/', '{}', content_type='application/json')
        self.assertIn('no-store', response['Cache-Control'])

    def test_an_unknown_path_is_no_store(self):
        self.assertIn('no-store', Client().get('/api/v1/no-such-route/')['Cache-Control'])

    def test_a_header_a_view_already_set_is_left_alone(self):
        self.assertEqual(Client().get('/readyz')['Cache-Control'], 'no-store')

    def test_the_hostel_detail_is_never_public(self):
        """It carries bed availability, which changes with every payment."""
        from apps.core.sample_data import ensure_sample_catalog
        from apps.hostels.models import Hostel
        ensure_sample_catalog()
        hostel = Hostel.objects.first()
        header = Client().get(f'/api/v1/hostels/{hostel.pk}/')['Cache-Control']
        self.assertIn('no-store', header)
        self.assertNotIn('public', header)

    def test_the_webhook_answer_is_no_store(self):
        response = Client().post('/api/v1/payments/webhook/', '{}', content_type='application/json')
        self.assertIn('no-store', response['Cache-Control'])
