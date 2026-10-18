"""
F5: data path and payload. Each test here failed on the code before F5 (see docs/AFTER-F5.md).

  QueryCountTests      owner dashboard stats and activity do a fixed, small number of queries
  HttpHeaderTests      gzip, cache headers for anonymous public reads only, 304 on ETag, per-worker places cache
  ImageTests           Cloudinary URLs get width/format/quality; everything else is left alone
  HostelSaveTests      one transaction, bulk rooms, rooms with bookings deactivated and hidden, never deleted
  DatabaseOptionTests  connect and statement timeouts come from the environment
"""
import gzip
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.core import db_options, images
from apps.core.sample_data import ensure_sample_catalog
from apps.hostels.models import City, Hostel, Locality
from apps.media_uploads.models import MediaItem
from apps.payments.models import Payment
from apps.rooms.models import Room

CLOUD = 'https://res.cloudinary.com/democloud/image/upload/v1700000000/hostels/abc123.jpg'


def client(user=None, **extra):
    api = APIClient(**extra)
    api.raise_request_exception = False
    if user is not None:
        api.force_authenticate(user=user)
    return api


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = ensure_sample_catalog()
        self.hostel = Hostel.objects.filter(owner=self.owner).order_by('name').first()
        self.room = self.hostel.rooms.order_by('room_name').first()


class QueryCountTests(Base):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.student = User.objects.create_user(email='s@example.test', display_name='S', password='pass12345')
        self.bookings = []
        for i in range(12):
            booking = Booking.objects.create(
                hostel=self.hostel, student=self.student, student_name='S', room=self.room, bed_number=str(i + 1),
                payment_mode='online' if i % 3 else 'offline',
                status=['pending', 'confirmed', 'paid', 'cancelled', 'rejected'][i % 5], amount=Decimal('6500'),
            )
            self.bookings.append(booking)
            if booking.payment_mode == 'online' and booking.status == 'paid':
                Payment.objects.create(booking=booking, razorpay_order_id=f'order_q{i}', amount=Decimal('6500'), status='SUCCESS')

    def test_owner_stats_use_four_queries_and_the_same_numbers(self):
        api = client(self.owner)
        with CaptureQueriesContext(connection) as queries:
            response = api.get('/api/v1/dashboard/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 4, [q['sql'][:90] for q in queries])

        data = response.json()['data']
        mine = Booking.objects.filter(hostel__owner=self.owner)
        self.assertEqual(data['total_hostels'], Hostel.objects.filter(owner=self.owner).count())
        self.assertEqual(data['total_beds'], sum(h.total_beds for h in Hostel.objects.filter(owner=self.owner)))
        for status in ('pending', 'confirmed', 'paid', 'cancelled', 'rejected'):
            self.assertEqual(data['bookings_by_status'][status], mine.filter(status=status).count(), status)
        for mode in ('offline', 'online'):
            self.assertEqual(data['bookings_by_payment_mode'][mode], mine.filter(payment_mode=mode).count(), mode)
        self.assertEqual(data['pending_bookings'], mine.filter(status='pending').count())
        offline = sum(b.amount for b in mine if b.payment_mode == 'offline' and b.status == 'paid')
        online = sum(p.amount for p in Payment.objects.filter(booking__hostel__owner=self.owner, status='SUCCESS'))
        self.assertEqual(data['revenue_collected'], float(offline + online))
        self.assertEqual(data['revenue_pending'], float(sum(b.amount for b in mine if b.status in ('pending', 'confirmed'))))

    def test_owner_stats_with_no_data_are_zeros(self):
        other = get_user_model().objects.create_user(email='empty@example.test', display_name='E', password='pass12345')
        data = client(other).get('/api/v1/dashboard/stats/').json()['data']
        self.assertEqual((data['total_hostels'], data['total_beds'], data['revenue_collected']), (0, 0, 0.0))
        self.assertEqual(sum(data['bookings_by_status'].values()), 0)

    def test_owner_activity_uses_two_queries(self):
        api = client(self.owner)
        with CaptureQueriesContext(connection) as queries:
            response = api.get('/api/v1/dashboard/activity/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['data']), 10)
        self.assertLessEqual(len(queries), 2, [q['sql'][:90] for q in queries])

    def test_public_list_stays_at_two_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = client().get('/api/v1/hostels/?page_size=50')
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 2)


class HttpHeaderTests(Base):
    def test_responses_are_gzipped_when_the_client_accepts_it(self):
        response = client().get('/api/v1/hostels/?page_size=50', HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual(response.headers.get('Content-Encoding'), 'gzip')
        self.assertIn('count', json.loads(gzip.decompress(response.content)))

    def test_health_checks_are_not_compressed_or_cached(self):
        response = client().get('/healthz', HTTP_ACCEPT_ENCODING='gzip')
        self.assertNotIn('Content-Encoding', response.headers)
        self.assertNotIn('public', response.headers.get('Cache-Control', ''))

    def test_anonymous_public_reads_get_cache_headers_and_vary(self):
        for path, seconds in (('/api/v1/hostels/', 30), ('/api/v1/cities/', 120), ('/api/v1/hostels/localities/', 120)):
            response = client().get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertEqual(response.headers['Cache-Control'], f'public, max-age={seconds}', path)
            self.assertIn('Authorization', response.headers['Vary'], path)
            self.assertTrue(response.headers['ETag'].startswith('"'), path)

    def test_the_locality_list_of_a_city_is_cached_too(self):
        slug = City.objects.filter(is_active=True).first().slug
        response = client().get(f'/api/v1/cities/{slug}/localities/')
        self.assertEqual(response.headers['Cache-Control'], 'public, max-age=120')

    def test_a_request_with_a_token_is_never_publicly_cached(self):
        for path in ('/api/v1/hostels/', '/api/v1/cities/', '/api/v1/hostels/localities/'):
            response = client(self.owner).get(path, HTTP_AUTHORIZATION='Bearer abc')
            self.assertEqual(response.headers['Cache-Control'], 'private, no-store', path)
            self.assertNotIn('ETag', response.headers, path)

    def test_the_owner_list_and_the_detail_are_not_cached(self):
        owner_list = client(self.owner).get('/api/v1/hostels/?scope=mine')
        self.assertNotIn('public', owner_list.headers.get('Cache-Control', ''))
        detail = client().get(f'/api/v1/hostels/{self.hostel.id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn('Cache-Control', detail.headers, 'the detail carries bed availability and must not be cached')

    def test_a_matching_etag_answers_304_with_no_body(self):
        first = client().get('/api/v1/cities/')
        again = client().get('/api/v1/cities/', HTTP_IF_NONE_MATCH=first.headers['ETag'])
        self.assertEqual(again.status_code, 304)
        self.assertEqual(again.content, b'')
        self.assertEqual(again.headers['Cache-Control'], 'public, max-age=120')
        other = client().get('/api/v1/cities/', HTTP_IF_NONE_MATCH='"something-else"')
        self.assertEqual(other.status_code, 200)

    def test_errors_are_not_cached(self):
        response = client().get('/api/v1/cities/nowhere/localities/')
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('public', response.headers.get('Cache-Control', ''))

    def test_the_city_list_is_served_from_memory_and_a_change_shows_at_once(self):
        api = client()
        with CaptureQueriesContext(connection) as first:
            names = [c['name'] for c in api.get('/api/v1/cities/').json()]
        with CaptureQueriesContext(connection) as second:
            api.get('/api/v1/cities/')
        self.assertGreaterEqual(len(first), 1)
        self.assertEqual(len(second), 0, 'the second request must not touch the database')

        Hostel.objects.filter(owner=self.owner).update(is_active=False)  # no signal fires for bulk updates ...
        stale = [c['name'] for c in api.get('/api/v1/cities/').json()]
        self.assertEqual(stale, names, '... so a bulk change shows only when the short TTL ends')

        city = City.objects.create(name='Newtown', state='Telangana')
        hostel = Hostel.objects.create(
            owner=self.owner, name='New H', city='Newtown', state='Telangana', locality='Core', address='a',
            city_ref=city, locality_ref=Locality.objects.create(city=city, name='Core'), is_active=True,
        )
        self.assertIn('Newtown', [c['name'] for c in api.get('/api/v1/cities/').json()], 'a normal save is visible at once')
        hostel.delete()

    @override_settings(PUBLIC_LIST_CACHE_SECONDS=0)
    def test_the_places_cache_can_be_turned_off(self):
        api = client()
        api.get('/api/v1/cities/')
        with CaptureQueriesContext(connection) as queries:
            api.get('/api/v1/cities/')
        self.assertGreaterEqual(len(queries), 1)


class ImageTests(SimpleTestCase):
    def test_a_cloudinary_upload_url_gets_format_quality_and_width(self):
        self.assertEqual(
            images.sized_image_url(CLOUD, 640),
            'https://res.cloudinary.com/democloud/image/upload/f_auto,q_auto,c_limit,w_640/v1700000000/hostels/abc123.jpg',
        )

    def test_other_urls_are_left_alone(self):
        for url in (
            'https://example.test/seed/a.jpg',
            'https://res.cloudinary.com/democloud/video/upload/v1/clip.mp4',
            'https://res.cloudinary.com/democloud/image/fetch/https://x.test/a.jpg',
            '', None, 'not a url',
        ):
            self.assertEqual(images.sized_image_url(url, 640), url)

    def test_an_already_transformed_url_is_not_transformed_twice(self):
        once = images.sized_image_url(CLOUD, 640)
        self.assertEqual(images.sized_image_url(once, 1600), once)
        self.assertEqual(
            images.sized_image_url('https://res.cloudinary.com/democloud/image/upload/w_300,c_fill/v1/a.jpg', 640),
            'https://res.cloudinary.com/democloud/image/upload/w_300,c_fill/v1/a.jpg',
        )

    def test_a_url_without_a_version_still_works(self):
        self.assertEqual(
            images.sized_image_url('https://res.cloudinary.com/democloud/image/upload/hostels/a.jpg', 1600),
            'https://res.cloudinary.com/democloud/image/upload/f_auto,q_auto,c_limit,w_1600/hostels/a.jpg',
        )


class ImageSerializerTests(Base):
    def setUp(self):
        super().setUp()
        MediaItem.objects.filter(hostel=self.hostel).delete()
        MediaItem.objects.create(hostel=self.hostel, file_url=CLOUD, category='hostel', order_index=0)

    def test_the_public_list_cover_is_a_small_version(self):
        rows = client().get('/api/v1/hostels/').json()['results']
        row = next(r for r in rows if r['hostel_id'] == str(self.hostel.id))
        self.assertIn('/upload/f_auto,q_auto,c_limit,w_640/', row['cover_image'])

    def test_the_public_detail_photos_are_a_larger_version_under_both_keys(self):
        media = client().get(f'/api/v1/hostels/{self.hostel.id}/').json()['media']
        self.assertEqual(len(media), 1)
        for key in ('file_url', 'remote_url'):
            self.assertIn('/upload/f_auto,q_auto,c_limit,w_1600/', media[0][key], key)

    def test_the_owner_still_sees_the_original(self):
        rows = client(self.owner).get('/api/v1/hostels/?scope=mine').json()['results']
        row = next(r for r in rows if r['hostel_id'] == str(self.hostel.id))
        self.assertEqual(row['media'][0]['file_url'], CLOUD)
        detail = client(self.owner).get(f'/api/v1/hostels/{self.hostel.id}/').json()
        self.assertEqual(detail['media'][0]['file_url'], CLOUD)

    def test_the_saved_list_uses_the_small_version_too(self):
        student = get_user_model().objects.create_user(email='s@example.test', display_name='S', password='pass12345')
        api = client(student)
        api.post('/api/v1/wishlist/', {'hostel_id': str(self.hostel.id)}, format='json')
        row = api.get('/api/v1/wishlist/').json()['wishlist'][0]
        self.assertIn('w_640', row['cover_image'])


class HostelSaveTests(Base):
    def payload(self, rooms):
        return {
            'name': 'Atomic Test', 'city': 'Hyderabad', 'locality': 'Gachibowli', 'state': 'Telangana', 'address': 'a',
            'gender_type': 'boys', 'contact_number': '9000000000', 'owner_name': 'O', 'email': 'o@example.test',
            'pincode': '500032', 'rooms_data': rooms,
        }

    @staticmethod
    def room_data(n, **extra):
        data = {'room_name': f'R{n}', 'sharing_type': 'double', 'price_per_month': '6500', 'bed_count': 2,
                'capacity': 2, 'available_beds': 2, 'floor_number': 1, 'room_number': str(n)}
        data.update(extra)
        return data

    def test_create_makes_the_hostel_and_all_rooms_in_few_queries(self):
        api = client(self.owner)
        with CaptureQueriesContext(connection) as queries:
            response = api.post('/api/v1/hostels/', self.payload([self.room_data(i) for i in range(6)]), format='json')
        self.assertEqual(response.status_code, 201, response.content)
        hostel = Hostel.objects.get(name='Atomic Test')
        self.assertEqual(hostel.rooms.count(), 6)
        inserts = [q for q in queries if q['sql'].lstrip().upper().startswith('INSERT INTO "ROOMS"')]
        self.assertEqual(len(inserts), 1, 'rooms are inserted with one statement')

    def test_a_bad_room_leaves_nothing_behind_and_answers_400(self):
        api = client(self.owner)
        before = (Hostel.objects.count(), Room.objects.count())
        rooms = [self.room_data(1), self.room_data(2, no_such_field='x')]
        response = api.post('/api/v1/hostels/', self.payload(rooms), format='json')
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('rooms_data', response.json())
        self.assertEqual((Hostel.objects.count(), Room.objects.count()), before)

    def test_a_failure_while_saving_rooms_rolls_the_hostel_back(self):
        api = client(self.owner)
        before = (Hostel.objects.count(), Room.objects.count())
        with mock.patch('apps.hostels.serializers.Room.objects.bulk_create', side_effect=RuntimeError('boom')):
            response = api.post('/api/v1/hostels/', self.payload([self.room_data(1)]), format='json')
        self.assertEqual(response.status_code, 500)
        self.assertEqual((Hostel.objects.count(), Room.objects.count()), before)

    def update_payload(self, hostel, rooms):
        body = self.payload(rooms)
        body['name'] = hostel.name
        return body

    def test_update_keeps_rooms_that_have_bookings_but_hides_them(self):
        api = client(self.owner)
        created = api.post('/api/v1/hostels/', self.payload([self.room_data(1), self.room_data(2), self.room_data(3)]), format='json').json()
        hostel = Hostel.objects.get(pk=created['hostel_id'])
        rooms = {r.room_name: r for r in hostel.rooms.all()}
        student = get_user_model().objects.create_user(email='b@example.test', display_name='B', password='pass12345')
        booking = Booking.objects.create(hostel=hostel, student=student, student_name='B', room=rooms['R2'], bed_number='1')

        keep = [self.room_data(1, room_id=str(rooms['R1'].id))]  # R2 (has a booking) and R3 (none) are left out
        response = api.put(f'/api/v1/hostels/{hostel.id}/', self.update_payload(hostel, keep), format='json')
        self.assertEqual(response.status_code, 200, response.content)

        self.assertTrue(Room.objects.filter(pk=rooms['R2'].pk, is_active=False).exists(), 'a room with bookings is deactivated')
        self.assertFalse(Room.objects.filter(pk=rooms['R3'].pk).exists(), 'a room without bookings is removed')
        booking.refresh_from_db()
        self.assertEqual(booking.room_id, rooms['R2'].pk, 'the booking keeps its room')

        public = client().get(f'/api/v1/hostels/{hostel.id}/').json()
        self.assertEqual([r['room_name'] for r in public['rooms']], ['R1'])
        listed = next(r for r in client().get('/api/v1/hostels/?page_size=50').json()['results'] if r['hostel_id'] == str(hostel.id))
        self.assertEqual(listed['room_count'], 1)

    def test_an_inactive_room_comes_back_when_the_owner_sends_it_again(self):
        api = client(self.owner)
        created = api.post('/api/v1/hostels/', self.payload([self.room_data(1), self.room_data(2)]), format='json').json()
        hostel = Hostel.objects.get(pk=created['hostel_id'])
        rooms = {r.room_name: r for r in hostel.rooms.all()}
        Booking.objects.create(hostel=hostel, student_name='B', room=rooms['R2'], bed_number='1')
        api.put(f'/api/v1/hostels/{hostel.id}/', self.update_payload(hostel, [self.room_data(1, room_id=str(rooms['R1'].id))]), format='json')
        again = [self.room_data(1, room_id=str(rooms['R1'].id)), self.room_data(2, room_id=str(rooms['R2'].id))]
        api.put(f'/api/v1/hostels/{hostel.id}/', self.update_payload(hostel, again), format='json')
        self.assertTrue(Room.objects.get(pk=rooms['R2'].pk).is_active)

    def test_the_number_of_queries_does_not_grow_with_the_number_of_rooms(self):
        api = client(self.owner)

        def update_cost(count):
            created = api.post('/api/v1/hostels/', dict(self.payload([self.room_data(i) for i in range(count)]), name=f'Scale {count}'), format='json').json()
            hostel = Hostel.objects.get(pk=created['hostel_id'])
            rows = [self.room_data(i, room_id=str(r.id)) for i, r in enumerate(hostel.rooms.order_by('room_name'))]
            with CaptureQueriesContext(connection) as queries:
                response = api.put(f'/api/v1/hostels/{hostel.id}/', dict(self.update_payload(hostel, rows), name=hostel.name), format='json')
            self.assertEqual(response.status_code, 200, response.content)
            return len(queries)

        self.assertEqual(update_cost(3), update_cost(12), 'updating 12 rooms must cost the same queries as updating 3')

    def test_a_failed_update_changes_nothing(self):
        api = client(self.owner)
        created = api.post('/api/v1/hostels/', self.payload([self.room_data(1), self.room_data(2)]), format='json').json()
        hostel = Hostel.objects.get(pk=created['hostel_id'])
        names = sorted(hostel.rooms.values_list('room_name', flat=True))
        bad = [self.room_data(1, room_id=str(hostel.rooms.first().id), no_such_field='x')]
        response = api.put(f'/api/v1/hostels/{hostel.id}/', self.update_payload(hostel, bad), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(sorted(hostel.rooms.values_list('room_name', flat=True)), names)


class DatabaseOptionTests(SimpleTestCase):
    def test_options_come_from_the_environment_values(self):
        self.assertEqual(db_options.postgres_options({}, connect_timeout=7), {'connect_timeout': 7})
        self.assertEqual(
            db_options.postgres_options({'sslmode': 'require'}, connect_timeout=5),
            {'sslmode': 'require', 'connect_timeout': 5},
            'options already in the URL are kept',
        )
        self.assertEqual(
            db_options.postgres_options({'connect_timeout': 3}, connect_timeout=5)['connect_timeout'], 3,
            'a timeout written in the URL wins',
        )

    def test_the_statement_timeout_statement(self):
        self.assertEqual(db_options.statement_timeout_sql(25000), 'SET statement_timeout = 25000')
        self.assertIsNone(db_options.statement_timeout_sql(0))
        self.assertIsNone(db_options.statement_timeout_sql(-1))

    def test_a_non_number_is_never_put_into_sql(self):
        with self.assertRaises(ValueError):
            db_options.statement_timeout_sql('1; DROP TABLE x')

    def test_settings_read_the_variables(self):
        import subprocess, sys, os
        env = dict(os.environ, DB_CONNECT_TIMEOUT='9', DB_STATEMENT_TIMEOUT_MS='12345', USE_DB='sqlite', DEBUG='True')
        code = ('import django;django.setup();from django.conf import settings;'
                'print(settings.DB_CONNECT_TIMEOUT, settings.DB_STATEMENT_TIMEOUT_MS)')
        env['DJANGO_SETTINGS_MODULE'] = 'config.settings'
        out = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, cwd=str(__import__('django').conf.settings.BASE_DIR))
        self.assertEqual(out.stdout.strip().split('\n')[-1], '9 12345', out.stderr[-400:])


class StatementTimeoutAppliedTests(TestCase):
    def test_the_connection_hook_sets_the_timeout_on_postgres_only(self):
        if connection.vendor != 'postgresql':
            self.skipTest('statement_timeout exists only on PostgreSQL')
        with override_settings(DB_STATEMENT_TIMEOUT_MS=31000):
            db_options.apply_statement_timeout(sender=None, connection=connection)
        with connection.cursor() as cursor:
            cursor.execute('SHOW statement_timeout')
            self.assertEqual(cursor.fetchone()[0], '31s')
