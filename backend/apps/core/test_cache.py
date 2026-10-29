"""
Phase 3, Part 2: the shared cache.

  * apps/core/cache.py     get_or_set with jitter and single-flight, versioned keys, namespaced keys.
  * ResilientRedisCache    a Redis outage slows things down at most once per cool-down; it never raises.
  * the places lists       cached through the helpers, refreshed by a version bump.
  * DRF throttles          their counter lives in the configured default cache.

Most tests run on the default cache (LocMem locally, Redis when REDIS_URL is set, as in the CI step that sets it).
The outage tests point the cache at a closed port, so they need no Redis.
"""
import os
import threading
import time
from unittest import mock, skipUnless

from django.core.cache import cache, caches
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle

from apps.core import cache as shared
from apps.core import cache_backend
from apps.hostels.models import City, Hostel, Locality

ON_REDIS = bool(os.environ.get('REDIS_URL'))
DEAD_REDIS = {
    'default': {
        'BACKEND': 'apps.core.cache_backend.ResilientRedisCache',
        'LOCATION': 'redis://127.0.0.1:1/0',  # nothing listens on port 1: connection refused at once
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient', 'IGNORE_EXCEPTIONS': False,
            'SOCKET_CONNECT_TIMEOUT': 0.2, 'SOCKET_TIMEOUT': 0.2, 'BREAKER_SECONDS': 30,
        },
    }
}


class CacheCase(SimpleTestCase):
    def setUp(self):
        cache.clear()
        shared.reset_for_tests()
        self.addCleanup(cache.clear)


class KeyTests(CacheCase):
    def test_keys_are_namespaced_by_environment_name_and_version(self):
        with override_settings(APP_ENV='staging'):
            key = shared.make_key('places', 'x')
        self.assertRegex(key, r'^hh:staging:places:x:v\d+$')

    def test_a_per_user_key_must_carry_the_user_id(self):
        with self.assertRaises(ValueError):
            shared.get_or_set('profile', 10, lambda: 1, per_user=True)

    def test_a_per_user_key_contains_the_id_so_two_users_never_share_one(self):
        a = shared.make_key('profile', user_id='111')
        b = shared.make_key('profile', user_id='222')
        self.assertNotEqual(a, b)
        self.assertIn(':u111:', a)

    def test_users_get_their_own_cached_value(self):
        self.assertEqual(shared.get_or_set('profile', 30, lambda: 'for-a', user_id='a', per_user=True), 'for-a')
        self.assertEqual(shared.get_or_set('profile', 30, lambda: 'for-b', user_id='b', per_user=True), 'for-b')
        self.assertEqual(shared.get_or_set('profile', 30, lambda: 'never', user_id='a', per_user=True), 'for-a')


class GetOrSetTests(CacheCase):
    def test_the_builder_runs_once_and_the_value_is_reused(self):
        builder = mock.Mock(return_value={'n': 1})
        self.assertEqual(shared.get_or_set('thing', 60, builder, parts=('a',)), {'n': 1})
        self.assertEqual(shared.get_or_set('thing', 60, builder, parts=('a',)), {'n': 1})
        builder.assert_called_once()

    def test_different_parts_are_different_entries(self):
        self.assertEqual(shared.get_or_set('thing', 60, lambda: 1, parts=('a',)), 1)
        self.assertEqual(shared.get_or_set('thing', 60, lambda: 2, parts=('b',)), 2)

    def test_falsy_values_are_cached_too(self):
        builder = mock.Mock(return_value=[])
        shared.get_or_set('empty', 60, builder)
        shared.get_or_set('empty', 60, builder)
        builder.assert_called_once()

    def test_a_value_the_caller_refuses_is_not_stored(self):
        builder = mock.Mock(return_value=('bad', 500))
        shared.get_or_set('maybe', 60, builder, should_cache=lambda v: v[1] == 200)
        shared.get_or_set('maybe', 60, builder, should_cache=lambda v: v[1] == 200)
        self.assertEqual(builder.call_count, 2)

    def test_a_failing_builder_raises_and_leaves_no_lock_behind(self):
        with self.assertRaises(RuntimeError):
            shared.get_or_set('boom', 60, mock.Mock(side_effect=RuntimeError('x')))
        self.assertEqual(shared.get_or_set('boom', 60, lambda: 'ok'), 'ok')

    def test_the_ttl_is_jittered_within_ten_percent(self):
        values = [shared.jittered_ttl(100) for _ in range(300)]
        self.assertTrue(all(90 <= v <= 110 for v in values), (min(values), max(values)))
        self.assertGreater(len(set(values)), 5, 'the TTL should vary, not be a constant')
        self.assertEqual(shared.jittered_ttl(1), 1)  # never below one second

    def test_get_or_set_stores_with_the_jittered_ttl(self):
        with mock.patch.object(shared, 'jittered_ttl', return_value=7) as jitter:
            shared.get_or_set('jit', 100, lambda: 1)
        jitter.assert_called_once_with(100)

    def test_a_ttl_of_zero_or_less_bypasses_the_cache(self):
        builder = mock.Mock(return_value=1)
        shared.get_or_set('off', 0, builder)
        shared.get_or_set('off', 0, builder)
        self.assertEqual(builder.call_count, 2)


class SingleFlightTests(CacheCase):
    def test_a_stampede_on_one_expired_key_runs_the_builder_once(self):
        calls, gate = [], threading.Event()

        def slow():
            calls.append(1)
            time.sleep(0.4)
            return 'v'

        results = []

        def worker():
            gate.wait()
            results.append(shared.get_or_set('hot', 60, slow))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        gate.set()
        for t in threads:
            t.join(10)
        self.assertEqual(results, ['v'] * 8)
        self.assertEqual(len(calls), 1, 'every waiter should reuse the first builder result')

    def test_waiters_give_up_and_build_themselves_if_the_lock_holder_never_finishes(self):
        key = shared.make_key('stuck')
        cache.add(key + ':lock', 1, 30)  # someone "holds" the lock and will never fill the value
        with mock.patch.object(shared, 'WAIT_SECONDS', 0.2):
            started = time.monotonic()
            self.assertEqual(shared.get_or_set('stuck', 60, lambda: 'mine'), 'mine')
        self.assertLess(time.monotonic() - started, 2)


class VersionTests(CacheCase):
    def test_bumping_a_version_makes_old_entries_unreachable(self):
        self.assertEqual(shared.get_or_set('list', 60, lambda: 'old'), 'old')
        before = shared.current_version('list')
        after = shared.bump_version('list')
        self.assertGreater(after, before)
        self.assertEqual(shared.get_or_set('list', 60, lambda: 'new'), 'new')

    def test_versions_are_per_name(self):
        shared.get_or_set('a', 60, lambda: 'a1')
        shared.bump_version('b')
        self.assertEqual(shared.get_or_set('a', 60, lambda: 'a2'), 'a1')

    def test_a_lost_version_counter_never_revives_old_entries(self):
        """If the cache evicts the counter, the next version must not equal an older one."""
        shared.get_or_set('list', 60, lambda: 'old')
        old = shared.current_version('list')
        cache.delete(shared.version_key('list'))
        self.assertNotEqual(shared.current_version('list'), old)
        self.assertEqual(shared.get_or_set('list', 60, lambda: 'fresh'), 'fresh')


class OutageTests(SimpleTestCase):
    """A dead Redis must slow things down at most once per cool-down, and never raise."""

    def setUp(self):
        cache_backend.reset_breaker()
        self.addCleanup(cache_backend.reset_breaker)

    @override_settings(CACHES=DEAD_REDIS)
    def test_every_operation_degrades_instead_of_raising(self):
        c = caches['default']
        self.assertIsNone(c.get('k'))
        self.assertEqual(c.get('k', 'fallback'), 'fallback')
        c.set('k', 1, 10)
        self.assertFalse(c.add('lock', 1, 10) is True)
        c.delete('k')
        self.assertIsNone(c.incr('n') if hasattr(c, 'incr') else None)
        self.assertEqual(c.get_many(['a', 'b']), {})

    @override_settings(CACHES=DEAD_REDIS)
    def test_after_the_first_failure_redis_is_not_contacted_again_during_the_cool_down(self):
        c = caches['default']
        c.get('first')  # the failure that opens the breaker
        self.assertTrue(cache_backend.breaker_open())
        with mock.patch('django_redis.cache.RedisCache._get') as network:
            for _ in range(50):
                self.assertEqual(c.get('later', 'x'), 'x')
        network.assert_not_called()  # nothing reached Redis while the breaker was open

    @override_settings(CACHES=DEAD_REDIS)
    def test_it_tries_again_when_the_cool_down_is_over(self):
        c = caches['default']
        c.get('first')
        with mock.patch.object(cache_backend, '_now', return_value=time.monotonic() + 3600), \
                mock.patch('django_redis.cache.RedisCache._get', return_value='back') as network:
            self.assertEqual(c.get('k'), 'back')
        network.assert_called_once()  # the cool-down is over, so Redis was asked again

    @override_settings(CACHES=DEAD_REDIS)
    def test_the_helpers_just_build_the_value_when_the_cache_is_down(self):
        shared.reset_for_tests()
        builder = mock.Mock(return_value='built')
        self.assertEqual(shared.get_or_set('x', 60, builder), 'built')
        self.assertEqual(shared.get_or_set('x', 60, builder), 'built')
        self.assertEqual(builder.call_count, 2)  # nothing could be stored, and nobody waited for a lock
        self.assertGreater(shared.bump_version('x'), 0)  # a bump is harmless too

    @override_settings(CACHES=DEAD_REDIS)
    def test_the_log_line_for_an_outage_has_no_address_or_password(self):
        with self.assertLogs('apps.core.cache', level='WARNING') as logs:
            caches['default'].get('k')
        text = ' '.join(logs.output)
        self.assertNotIn('127.0.0.1', text)
        self.assertNotIn('redis://', text)
        self.assertRegex(text, r'ConnectionError|Error')

    @override_settings(CACHES=DEAD_REDIS)
    def test_a_throttled_public_endpoint_still_answers_when_redis_is_down(self):
        factory = APIRequestFactory()
        throttle = AnonRateThrottle()
        request = Request(factory.get('/api/v1/hostels/'))
        for _ in range(5):
            self.assertTrue(throttle.allow_request(request, None))  # fail-open: nothing counted, nobody blocked


class PlacesCacheTests(TestCase):
    """The public city and locality lists, now cached through the shared helpers."""

    def setUp(self):
        cache.clear()
        shared.reset_for_tests()
        self.addCleanup(cache.clear)
        self.city = City.objects.create(name='Hyderabad', slug='hyderabad', is_active=True)
        self.locality = Locality.objects.create(city=self.city, name='Ameerpet', slug='ameerpet', is_active=True)

    def test_a_repeat_request_does_not_query_the_database(self):
        url = reverse('city-list')
        self.client.get(url)
        with self.assertNumQueries(0):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_saving_a_city_refreshes_the_list_at_once(self):
        url = reverse('city-list') + '?include_empty=true'
        self.assertEqual([c['name'] for c in self.client.get(url).json()], ['Hyderabad'])
        City.objects.create(name='Pune', slug='pune', is_active=True)
        self.assertEqual(sorted(c['name'] for c in self.client.get(url).json()), ['Hyderabad', 'Pune'])

    def test_the_places_version_is_bumped_by_a_locality_write(self):
        before = shared.current_version('places')
        Locality.objects.create(city=self.city, name='Kukatpally', slug='kukatpally', is_active=True)
        self.assertGreater(shared.current_version('places'), before)

    def test_room_writes_bump_the_places_version(self):
        from apps.core.sample_data import ensure_sample_catalog
        from apps.rooms.models import Room
        ensure_sample_catalog()
        room = Room.objects.first()
        before = shared.current_version('places')
        room.save()
        after_save = shared.current_version('places')
        self.assertGreater(after_save, before)
        room.delete()
        self.assertGreater(shared.current_version('places'), after_save)

    def test_hostel_writes_bump_the_places_version(self):
        from apps.core.sample_data import ensure_sample_catalog
        ensure_sample_catalog()
        hostel = Hostel.objects.first()
        before = shared.current_version('places')
        hostel.save()
        self.assertGreater(shared.current_version('places'), before)

    def test_the_cache_can_be_turned_off(self):
        url = reverse('city-list')
        with override_settings(PUBLIC_LIST_CACHE_SECONDS=0):
            self.client.get(url)
            with self.assertNumQueries(1):
                self.client.get(url)


class ThrottleCounterTests(SimpleTestCase):
    """DRF's rate limits count in the default cache, so with Redis configured they are shared by every worker."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_drf_throttles_use_the_default_cache(self):
        self.assertIs(SimpleRateThrottle.cache, __import__('django.core.cache', fromlist=['cache']).cache)

    def test_the_counter_lives_in_the_configured_cache_and_a_second_worker_sees_it(self):
        factory = APIRequestFactory()
        request = Request(factory.get('/api/v1/hostels/', REMOTE_ADDR='203.0.113.9'))
        first = AnonRateThrottle()
        self.assertTrue(first.allow_request(request, None))
        self.assertEqual(len(cache.get(first.key)), 1, 'the hit must be stored in the default cache')

        worker_two = caches.create_connection('default')  # what another gunicorn worker would hold
        self.assertEqual(len(worker_two.get(first.key)), 1, 'a second worker must see the first worker\'s hit')

        second = AnonRateThrottle()
        self.assertTrue(second.allow_request(request, None))
        self.assertEqual(len(worker_two.get(first.key)), 2)

    @skipUnless(ON_REDIS, 'needs REDIS_URL (the CI step that runs these tests against Redis sets it)')
    def test_with_redis_configured_the_counter_is_really_in_redis(self):
        import redis
        factory = APIRequestFactory()
        request = Request(factory.get('/api/v1/hostels/', REMOTE_ADDR='203.0.113.77'))
        throttle = AnonRateThrottle()
        throttle.allow_request(request, None)
        client = redis.Redis.from_url(os.environ['REDIS_URL'])
        keys = [k.decode() for k in client.keys('*throttle_anon*')]
        self.assertTrue(keys, 'the throttle key should exist in Redis itself')

    def test_the_rates_are_unchanged(self):
        from django.conf import settings
        rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
        self.assertEqual((rates['anon'], rates['user'], rates['otp_send'], rates['otp_verify']),
                         ('60/min', '120/min', '20/min', '30/min'))


@skipUnless(ON_REDIS, 'needs REDIS_URL')
class RedisBackendTests(SimpleTestCase):
    def test_the_default_cache_is_the_resilient_redis_backend(self):
        self.assertIsInstance(caches['default'], cache_backend.ResilientRedisCache)

    def test_cache_stats_reports_counters_and_never_the_address(self):
        from io import StringIO

        from django.core.management import call_command
        cache.set('hh:test:stats', 1, 5)
        cache.get('hh:test:stats')
        out = StringIO()
        call_command('cache_stats', stdout=out)
        text = out.getvalue()
        for name in ('keyspace_hits=', 'keyspace_misses=', 'hit_rate=', 'used_memory=', 'keys=', 'evicted_keys='):
            self.assertIn(name, text)
        self.assertNotIn('redis://', text)
        self.assertNotIn(os.environ['REDIS_URL'], text)
        cache.clear()

    def test_round_trip_and_atomic_add(self):
        cache.clear()
        self.assertTrue(cache.add('hh:test:lock', 1, 5))
        self.assertFalse(cache.add('hh:test:lock', 1, 5))  # False = someone holds it (None would mean an outage)
        cache.set('hh:test:v', {'a': [1, 2]}, 5)
        self.assertEqual(cache.get('hh:test:v'), {'a': [1, 2]})
        cache.clear()
