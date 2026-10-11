import json
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.hostels.location_backfill import display_name, link_hostels, unlink_hostels
from apps.hostels.locations import normalise_slug
from apps.hostels.models import City, Hostel, Locality, LocalityAlias
from apps.rooms.models import Room

Owner = get_user_model()
LIST = '/api/v1/hostels/'


def make_owner(email, **extra):
    return Owner.objects.create_user(email=email, display_name=email, password='pass12345', **extra)


def make_hostel(owner, name, city=None, locality=None, *, text_city=None, text_locality=None, **extra):
    fields = dict(
        owner=owner, name=name, owner_name='O', contact_number='9000000000', email=owner.email,
        locality=text_locality or (locality.name if locality else 'Somewhere'), address=f'{name} road',
        city=text_city or (city.name if city else 'Nowhere'), state='Telangana', pincode='500001',
        gender_type='boys', city_ref=city, locality_ref=locality,
    )
    fields.update(extra)
    return Hostel.objects.create(**fields)


def names(response):
    return [item['name'] for item in response.json()['results']]


class SlugTests(SimpleTestCase):
    def test_slug_ignores_case_spaces_and_punctuation(self):
        self.assertEqual(normalise_slug('  Dilsukhnagar '), 'dilsukhnagar')
        self.assertEqual(normalise_slug('K.P.H.B  Colony'), 'k-p-h-b-colony')
        self.assertEqual(normalise_slug('Café Road'), 'cafe-road')
        self.assertEqual(normalise_slug('  '), '')

    def test_display_names_fix_case_but_keep_spelling(self):
        self.assertEqual(display_name('kondapur'), 'Kondapur')
        self.assertEqual(display_name('kphb'), 'KPHB')
        self.assertEqual(display_name('white feild'), 'White Feild')
        self.assertEqual(display_name('Dilsuknagar'), 'Dilsuknagar')
        self.assertEqual(display_name('  hyderabad '), 'Hyderabad')


class LocationBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_owner('owner@example.test')
        cls.other_owner = make_owner('other@example.test')
        cls.student = make_owner('student@example.test')
        cls.hyd = City.objects.create(name='Hyderabad', slug='hyderabad', state='Telangana')
        cls.pune = City.objects.create(name='Pune', slug='pune', state='Maharashtra')
        cls.kondapur = Locality.objects.create(city=cls.hyd, name='Kondapur', slug='kondapur')
        cls.dilsukh = Locality.objects.create(city=cls.hyd, name='Dilsukhnagar', slug='dilsukhnagar')
        cls.kothrud = Locality.objects.create(city=cls.pune, name='Kothrud', slug='kothrud')
        LocalityAlias.objects.create(locality=cls.dilsukh, alias_slug='dilsuknagar')
        cls.h_kond = make_hostel(cls.owner, 'Kondapur Boys', cls.hyd, cls.kondapur, amenities=['wifi', 'ac'])
        cls.h_dils = make_hostel(cls.owner, 'Dilsukh Stay', cls.hyd, cls.dilsukh)
        cls.h_pune = make_hostel(cls.other_owner, 'Pune Place', cls.pune, cls.kothrud)

    def student_client(self):
        client = APIClient()
        client.force_authenticate(user=self.student)
        return client


class LocationFilterTests(LocationBase):
    def test_locality_filter_returns_only_that_locality_for_anonymous(self):
        self.assertEqual(names(APIClient().get(LIST, {'city': 'hyderabad', 'locality': 'kondapur'})), ['Kondapur Boys'])

    def test_locality_filter_is_the_same_for_a_logged_in_student(self):
        response = self.student_client().get(LIST, {'city': 'hyderabad', 'locality': 'kondapur'})
        self.assertEqual(names(response), ['Kondapur Boys'])

    def test_a_spelling_variant_resolves_to_the_one_locality(self):
        client = APIClient()
        a = names(client.get(LIST, {'city': 'Hyderabad', 'locality': 'Dilsuknagar'}))
        b = names(client.get(LIST, {'city': 'Hyderabad', 'locality': 'Dilsukhnagar'}))
        c = names(client.get(LIST, {'city': 'Hyderabad', 'locality': ' DILSUKH-nagar '}))
        self.assertEqual(a, ['Dilsukh Stay'])
        self.assertEqual(a, b)
        self.assertEqual(b, c)

    def test_no_locality_means_the_whole_city(self):
        self.assertEqual(sorted(names(APIClient().get(LIST, {'city': 'Hyderabad'}))), ['Dilsukh Stay', 'Kondapur Boys'])

    def test_city_matches_by_slug_name_and_case(self):
        client = APIClient()
        for value in ('hyderabad', 'HYDERABAD', 'Hyderabad ', 'Hyderabad'):
            self.assertEqual(len(names(client.get(LIST, {'city': value}))), 2, value)

    def test_a_hostel_without_links_is_found_by_its_legacy_text(self):
        make_hostel(self.owner, 'Legacy Row', text_city='hyderabad', text_locality='kphb colony')
        client = APIClient()
        self.assertIn('Legacy Row', names(client.get(LIST, {'city': 'Hyderabad', 'locality': 'kphb'})))
        make_hostel(self.owner, 'Odd City Row', text_city='Atlantis', text_locality='Deep End')
        self.assertEqual(names(client.get(LIST, {'city': 'atlantis'})), ['Odd City Row'])

    def test_inactive_hostels_and_hostels_in_inactive_cities_are_hidden(self):
        Hostel.objects.filter(pk=self.h_kond.pk).update(is_active=False)
        City.objects.filter(pk=self.pune.pk).update(is_active=False)
        self.assertEqual(names(APIClient().get(LIST)), ['Dilsukh Stay'])

    def test_gender_type_still_filters(self):
        make_hostel(self.owner, 'Girls Place', self.hyd, self.kondapur, gender_type='girls')
        self.assertEqual(names(APIClient().get(LIST, {'gender_type': 'girls'})), ['Girls Place'])


class SearchAndAmenityTests(LocationBase):
    def test_search_finds_by_name_locality_and_address_ignoring_case(self):
        client = APIClient()
        self.assertEqual(names(client.get(LIST, {'search': 'kondapur boys'})), ['Kondapur Boys'])
        self.assertEqual(sorted(names(client.get(LIST, {'search': 'DILSUKH'}))), ['Dilsukh Stay'])
        self.assertEqual(names(client.get(LIST, {'search': 'pune place road'})), ['Pune Place'])

    def test_a_one_character_search_is_ignored(self):
        self.assertEqual(len(names(APIClient().get(LIST, {'search': 'k'}))), 3)

    def test_search_respects_the_selected_city(self):
        self.assertEqual(names(APIClient().get(LIST, {'search': 'place', 'city': 'hyderabad'})), [])

    def test_amenity_matches_one_item_of_the_list(self):
        client = APIClient()
        self.assertEqual(names(client.get(LIST, {'amenity': 'AC'})), ['Kondapur Boys'])
        self.assertEqual(names(client.get(LIST, {'amenity': 'a'})), [])


class PagingTests(LocationBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for number in range(27):
            make_hostel(cls.owner, f'Bulk {number:02d}', cls.hyd, cls.kondapur)

    def collect(self, **params):
        client, seen, page = APIClient(), [], 1
        while True:
            body = client.get(LIST, {**params, 'page': page}).json()
            seen += [item['hostel_id'] for item in body['results']]
            if not body['next']:
                return seen, body['count']
            page += 1

    def test_pages_never_overlap_or_skip(self):
        seen, count = self.collect(city='Hyderabad')
        self.assertEqual(count, 29)
        self.assertEqual(len(seen), 29)
        self.assertEqual(len(set(seen)), 29)

    def test_the_order_is_stable_between_requests(self):
        client = APIClient()
        first = [i['hostel_id'] for i in client.get(LIST, {'page': 2}).json()['results']]
        again = [i['hostel_id'] for i in client.get(LIST, {'page': 2}).json()['results']]
        self.assertEqual(first, again)

    def test_default_page_size_is_10_and_the_maximum_is_50(self):
        client = APIClient()
        self.assertEqual(len(client.get(LIST).json()['results']), 10)
        self.assertEqual(len(client.get(LIST, {'page_size': 500}).json()['results']), 30)
        self.assertLessEqual(len(client.get(LIST, {'page_size': 500}).json()['results']), 50)
        self.assertEqual(len(client.get(LIST, {'page_size': 5}).json()['results']), 5)

    def test_the_count_query_does_not_join_rooms(self):
        Room.objects.create(
            hostel=self.h_kond, room_name='R', sharing_type='single', capacity=1, bed_count=1,
            price_per_month='5000.00', available_beds=1,
        )
        with CaptureQueriesContext(connection) as queries:
            APIClient().get(LIST, {'city': 'Hyderabad'})
        counts = [q['sql'] for q in queries.captured_queries if q['sql'].upper().startswith('SELECT COUNT(')]
        self.assertTrue(counts, 'the pagination count query was not found')
        for sql in counts:
            self.assertNotIn('"rooms"', sql)
            self.assertNotIn('GROUP BY', sql.upper())

    def test_price_and_counts_are_still_returned(self):
        Room.objects.create(
            hostel=self.h_kond, room_name='R1', sharing_type='single', capacity=1, bed_count=2,
            price_per_month='7000.00', available_beds=1,
        )
        Room.objects.create(
            hostel=self.h_kond, room_name='R2', sharing_type='double', capacity=2, bed_count=3,
            price_per_month='5000.00', available_beds=2,
        )
        item = APIClient().get(LIST, {'search': 'Kondapur Boys'}).json()['results'][0]
        self.assertEqual((item['price_from'], item['price_to'], item['room_count'], item['bed_count']), (5000.0, 7000.0, 2, 5))
        self.assertEqual(item['amenities'], ['wifi', 'ac'])


class ScopeTests(LocationBase):
    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_a_token_does_not_change_the_public_list(self):
        self.assertEqual(sorted(names(self.as_user(self.other_owner).get(LIST))),
                         sorted(names(APIClient().get(LIST))))

    def test_scope_mine_returns_only_the_owners_hostels_including_inactive(self):
        Hostel.objects.filter(pk=self.h_dils.pk).update(is_active=False)
        response = self.as_user(self.owner).get(LIST, {'scope': 'mine'})
        self.assertEqual(sorted(names(response)), ['Dilsukh Stay', 'Kondapur Boys'])
        self.assertIn('owner_id', response.json()['results'][0])

    def test_scope_mine_needs_a_login(self):
        self.assertEqual(APIClient().get(LIST, {'scope': 'mine'}).status_code, 401)

    def test_scope_all_is_for_staff_only(self):
        self.assertEqual(self.as_user(self.owner).get(LIST, {'scope': 'all'}).status_code, 403)
        staff = make_owner('staff@example.test', is_staff=True)
        Hostel.objects.filter(pk=self.h_pune.pk).update(is_active=False)
        self.assertEqual(len(names(self.as_user(staff).get(LIST, {'scope': 'all'}))), 3)

    def test_a_student_sees_another_owners_active_hostel_without_owner_fields(self):
        response = self.student_client().get(f'{LIST}{self.h_kond.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('owner_id', response.json())
        self.assertEqual(response.json()['name'], 'Kondapur Boys')

    def test_an_owner_can_open_their_own_inactive_hostel_but_a_student_cannot(self):
        Hostel.objects.filter(pk=self.h_kond.pk).update(is_active=False)
        self.assertEqual(self.as_user(self.owner).get(f'{LIST}{self.h_kond.pk}/').status_code, 200)
        self.assertEqual(self.student_client().get(f'{LIST}{self.h_kond.pk}/').status_code, 404)

    def test_writes_stay_owner_scoped(self):
        response = self.as_user(self.other_owner).patch(f'{LIST}{self.h_kond.pk}/', {'name': 'Hijack'}, format='json')
        self.assertIn(response.status_code, (403, 404))


class HostelWriteTests(LocationBase):
    def post(self, **extra):
        client = APIClient()
        client.force_authenticate(user=self.owner)
        body = dict(name='New One', owner_name='O', contact_number='9000000000', email='o@example.test',
                    address='1 road', pincode='500001', gender_type='boys', rooms_data=[], **extra)
        return client.post(LIST, body, format='json')

    def test_ids_from_the_lists_set_the_links_and_the_names(self):
        response = self.post(city_id=str(self.hyd.pk), locality_id=str(self.kondapur.pk))
        self.assertEqual(response.status_code, 201, response.content)
        hostel = Hostel.objects.get(name='New One')
        self.assertEqual((hostel.city_ref, hostel.locality_ref), (self.hyd, self.kondapur))
        self.assertEqual((hostel.city, hostel.locality, hostel.state), ('Hyderabad', 'Kondapur', 'Telangana'))

    def test_legacy_text_is_resolved_to_the_canonical_entry(self):
        response = self.post(city='HYDERABAD ', locality='dilsuknagar', state='Telangana')
        self.assertEqual(response.status_code, 201, response.content)
        hostel = Hostel.objects.get(name='New One')
        self.assertEqual((hostel.city_ref, hostel.locality_ref), (self.hyd, self.dilsukh))
        self.assertEqual((hostel.city, hostel.locality), ('Hyderabad', 'Dilsukhnagar'))

    def test_a_locality_from_another_city_is_refused(self):
        response = self.post(city_id=str(self.hyd.pk), locality_id=str(self.kothrud.pk))
        self.assertEqual(response.status_code, 400)

    def test_an_unknown_id_is_refused(self):
        response = self.post(city_id='00000000-0000-0000-0000-000000000009')
        self.assertEqual(response.status_code, 400)


class CityEndpointTests(LocationBase):
    def test_cities_lists_active_cities_that_have_active_hostels_with_counts(self):
        City.objects.create(name='Empty City', slug='empty-city')
        City.objects.create(name='Ghost', slug='ghost', is_active=False)
        body = APIClient().get('/api/v1/cities/').json()
        got = {c['slug']: c['hostel_count'] for c in body}
        self.assertEqual(got, {'hyderabad': 2, 'pune': 1})
        self.assertEqual({'id', 'name', 'slug', 'state', 'hostel_count'}, set(body[0]))

    def test_include_empty_lists_every_active_city_for_the_admin_wizard(self):
        City.objects.create(name='Empty City', slug='empty-city')
        City.objects.create(name='Ghost', slug='ghost', is_active=False)
        slugs = [c['slug'] for c in APIClient().get('/api/v1/cities/', {'include_empty': 'true'}).json()]
        self.assertEqual(sorted(slugs), ['empty-city', 'hyderabad', 'pune'])

    def test_localities_of_a_city_have_counts_and_hide_empty_ones(self):
        Locality.objects.create(city=self.hyd, name='Nobody Here', slug='nobody-here')
        body = APIClient().get('/api/v1/cities/hyderabad/localities/').json()
        self.assertEqual({row['slug']: row['hostel_count'] for row in body}, {'kondapur': 1, 'dilsukhnagar': 1})
        full = APIClient().get('/api/v1/cities/hyderabad/localities/', {'include_empty': 'true'}).json()
        self.assertEqual(len(full), 3)

    def test_unknown_city_is_404(self):
        self.assertEqual(APIClient().get('/api/v1/cities/atlantis/localities/').status_code, 404)

    def test_the_legacy_localities_endpoint_still_answers_in_its_old_shape(self):
        body = APIClient().get(f'{LIST}localities/', {'city': 'hyderabad'}).json()
        self.assertEqual({row['locality']: row['count'] for row in body}, {'Kondapur': 1, 'Dilsukhnagar': 1})

    def test_the_two_spellings_never_become_two_localities(self):
        with self.assertRaises(ValidationError):
            LocalityAlias(locality=self.kondapur, alias_slug='dilsuknagar').full_clean()
        with self.assertRaises(ValidationError):
            LocalityAlias(locality=self.kondapur, alias_slug='dilsukhnagar').full_clean()


class BackfillTests(TestCase):
    def test_existing_text_is_linked_without_inventing_corrections(self):
        owner = make_owner('o@example.test')
        rows = {
            'a': make_hostel(owner, 'A', text_city='hyderabad', text_locality='kondapur'),
            'b': make_hostel(owner, 'B', text_city='Hyderabad', text_locality='Kondapur '),
            'c': make_hostel(owner, 'C', text_city='hyderabad', text_locality='kphb'),
            'd': make_hostel(owner, 'D', text_city='Test City', text_locality='kondapur'),
            'e': make_hostel(owner, 'E', text_city='Pune', text_locality='Unknown'),
            'f': make_hostel(owner, 'F', text_city='Pune'),
        }
        Hostel.objects.filter(pk=rows['f'].pk).update(locality='')
        link_hostels(Hostel, City, Locality)
        refreshed = {key: Hostel.objects.get(pk=h.pk) for key, h in rows.items()}
        self.assertEqual(refreshed['a'].locality_ref, refreshed['b'].locality_ref)
        self.assertEqual(refreshed['a'].city_ref.name, 'Hyderabad')
        self.assertEqual(refreshed['c'].locality_ref.name, 'KPHB')
        self.assertFalse(refreshed['d'].city_ref.is_active)
        self.assertEqual(refreshed['e'].city_ref.name, 'Pune')
        self.assertIsNone(refreshed['e'].locality_ref)
        self.assertIsNone(refreshed['f'].locality_ref)
        self.assertEqual(City.objects.count(), 3)
        self.assertEqual(Locality.objects.filter(city__slug='hyderabad').count(), 2)
        self.assertEqual(Hostel.objects.get(pk=rows['a'].pk).locality, 'kondapur')  # text untouched

    def test_it_can_run_twice_and_be_reversed(self):
        owner = make_owner('o@example.test')
        hostel = make_hostel(owner, 'A', text_city='hyderabad', text_locality='kondapur')
        link_hostels(Hostel, City, Locality)
        link_hostels(Hostel, City, Locality)
        self.assertEqual((City.objects.count(), Locality.objects.count()), (1, 1))
        unlink_hostels(Hostel, City, Locality)
        hostel.refresh_from_db()
        self.assertEqual((hostel.city_ref, hostel.locality_ref), (None, None))
        self.assertEqual((City.objects.count(), Locality.objects.count()), (0, 0))
        self.assertEqual((hostel.city, hostel.locality), ('hyderabad', 'kondapur'))


@override_settings(APP_ENV='staging')
class DeactivateTestHostelsTests(TestCase):
    def setUp(self):
        owner = make_owner('o@example.test')
        self.real = make_hostel(owner, 'Real', text_city='Hyderabad', text_locality='Kondapur')
        self.test_state = make_hostel(owner, 'Trancula', text_city='Bengaluru', text_locality='x', state='Test State')
        test_city = City.objects.create(name='Test City', slug='test-city', is_active=False)
        self.test_city = make_hostel(owner, 'Tarun', text_city='Test City', city_ref=test_city)
        self.undo = Path(tempfile.mkdtemp()) / 'undo.json'

    def run_command(self, *args):
        out = StringIO()
        call_command('deactivate_test_hostels', *args, stdout=out)
        return out.getvalue()

    def active(self):
        return set(Hostel.objects.filter(is_active=True).values_list('name', flat=True))

    def test_default_is_a_dry_run_that_lists_but_changes_nothing(self):
        out = self.run_command()
        self.assertIn('Trancula', out)
        self.assertIn('DRY RUN', out)
        self.assertEqual(self.active(), {'Real', 'Trancula', 'Tarun'})

    def test_apply_deactivates_only_test_looking_hostels_and_writes_an_undo_file(self):
        self.run_command('--apply', '--undo-file', str(self.undo))
        self.assertEqual(self.active(), {'Real'})
        self.assertEqual(len(json.loads(self.undo.read_text())['hostel_ids']), 2)

    def test_restore_reverses_it(self):
        self.run_command('--apply', '--undo-file', str(self.undo))
        self.run_command('--restore', str(self.undo))
        self.assertEqual(self.active(), {'Real', 'Trancula', 'Tarun'})

    def test_explicit_ids_are_honoured(self):
        self.run_command('--apply', '--undo-file', str(self.undo), '--ids', str(self.real.pk))
        self.assertEqual(self.active(), {'Trancula', 'Tarun'} | set())

    @override_settings(APP_ENV='production')
    def test_refuses_outside_staging(self):
        with self.assertRaises(CommandError) as ctx:
            self.run_command('--apply')
        self.assertIn('staging', str(ctx.exception))
        self.assertEqual(self.active(), {'Real', 'Trancula', 'Tarun'})
