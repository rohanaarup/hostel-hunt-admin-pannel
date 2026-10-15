"""Phase T3: the wishlist (saved hostels) routes, and search that understands other scripts."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient, APITestCase

from apps.bookings.models import Wishlist
from apps.hostels.locations import match_key
from apps.hostels.models import City, Hostel, Locality, LocalityAlias
from apps.rooms.models import Room

Owner = get_user_model()
WISHLIST = '/api/v1/wishlist/'
IDS = '/api/v1/wishlist/ids/'
LIST = '/api/v1/hostels/'


def by_hostel(hostel_id):
    return f'/api/v1/wishlist/hostel/{hostel_id}/'


class WishlistBase(APITestCase):
    def setUp(self):
        self.owner = Owner.objects.create_user(email='owner@example.test', display_name='Owner', password='pass12345')
        self.a = Owner.objects.create_user(email='a@example.test', display_name='A', password='pass12345')
        self.b = Owner.objects.create_user(email='b@example.test', display_name='B', password='pass12345')
        self.client_a = APIClient()
        self.client_a.force_authenticate(user=self.a)
        self.client_b = APIClient()
        self.client_b.force_authenticate(user=self.b)

    def hostel(self, name='H', active=True, **extra):
        return Hostel.objects.create(
            owner=self.owner, name=name, owner_name='Owner', contact_number='9999999999',
            email='owner@example.test', locality='Kondapur', address='1 Road', city='Hyderabad',
            state='Telangana', pincode='500084', gender_type='boys', is_active=active, **extra,
        )

    def save(self, client, hostel):
        return client.post(WISHLIST, {'hostel_id': str(hostel.pk)}, format='json')


class WishlistAccessTests(WishlistBase):
    def test_every_route_needs_a_login(self):
        anonymous = APIClient()
        h = self.hostel()
        item = Wishlist.objects.create(user=self.a, hostel=h)
        for response in (
            anonymous.get(WISHLIST),
            anonymous.post(WISHLIST, {'hostel_id': str(h.pk)}, format='json'),
            anonymous.get(IDS),
            anonymous.delete(by_hostel(h.pk)),
            anonymous.delete(f'{WISHLIST}{item.pk}/'),
        ):
            self.assertEqual(response.status_code, 401)
            self.assertIn('detail', response.json())
        self.assertEqual(Wishlist.objects.count(), 1)


class WishlistSaveTests(WishlistBase):
    def test_saving_twice_succeeds_and_keeps_one_row(self):
        h = self.hostel()
        first, second = self.save(self.client_a, h), self.save(self.client_a, h)
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.json()['id'], second.json()['id'])
        self.assertTrue(first.json()['saved'] and second.json()['saved'])
        self.assertEqual(Wishlist.objects.filter(user=self.a).count(), 1)

    def test_a_bad_id_is_a_400_not_a_500(self):
        response = self.client_a.post(WISHLIST, {'hostel_id': 'not-a-uuid'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('hostel_id', response.json())

    def test_a_missing_id_is_a_400_with_a_field_error(self):
        response = self.client_a.post(WISHLIST, {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('hostel_id', response.json())

    def test_an_unknown_hostel_is_a_404(self):
        response = self.client_a.post(WISHLIST, {'hostel_id': '00000000-0000-0000-0000-000000000000'}, format='json')
        self.assertEqual(response.status_code, 404)

    def test_an_inactive_hostel_cannot_be_saved(self):
        response = self.save(self.client_a, self.hostel(active=False))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Wishlist.objects.count(), 0)


class WishlistListTests(WishlistBase):
    def test_rows_carry_what_a_card_needs_and_keep_the_old_keys(self):
        h = self.hostel('Sunrise', amenities=['wifi', 'ac'])
        Room.objects.create(hostel=h, room_name='R', sharing_type='single', capacity=1, bed_count=1,
                            price_per_month='6500.00', available_beds=1)
        item_id = self.save(self.client_a, h).json()['id']

        body = self.client_a.get(WISHLIST).json()

        self.assertEqual(body['count'], 1)
        row = body['wishlist'][0]
        self.assertEqual(row['id'], item_id)  # the saved row's own id, as before
        self.assertEqual(row['hostel_id'], str(h.pk))
        self.assertEqual((row['hostel_name'], row['hostel_city'], row['hostel_locality']), ('Sunrise', 'Hyderabad', 'Kondapur'))
        self.assertEqual((row['name'], row['city'], row['locality']), ('Sunrise', 'Hyderabad', 'Kondapur'))
        self.assertEqual(float(row['price_from']), 6500.0)
        self.assertEqual(row['amenities'], ['wifi', 'ac'])
        self.assertIn('cover_image', row)
        self.assertIn('saved_at', row)
        self.assertIn('next', body)

    def test_it_is_paginated_newest_saved_first(self):
        hostels = [self.hostel(f'H{i}') for i in range(3)]
        for h in hostels:
            self.save(self.client_a, h)

        first = self.client_a.get(WISHLIST, {'page_size': 2}).json()
        second = self.client_a.get(WISHLIST, {'page_size': 2, 'page': 2}).json()

        self.assertEqual(first['count'], 3)
        self.assertEqual([r['name'] for r in first['wishlist']], ['H2', 'H1'])
        self.assertIsNotNone(first['next'])
        self.assertEqual([r['name'] for r in second['wishlist']], ['H0'])
        self.assertIsNone(second['next'])

    def test_hostels_that_were_deactivated_disappear(self):
        h = self.hostel()
        self.save(self.client_a, h)
        Hostel.objects.filter(pk=h.pk).update(is_active=False)

        body = self.client_a.get(WISHLIST).json()

        self.assertEqual((body['count'], body['wishlist']), (0, []))

    def test_students_only_ever_see_their_own(self):
        h = self.hostel()
        self.save(self.client_a, h)
        self.assertEqual(self.client_b.get(WISHLIST).json()['count'], 0)
        self.assertEqual(self.client_b.get(IDS).json()['ids'], [])

    def test_the_number_of_queries_does_not_grow_with_the_number_of_rows(self):
        for i in range(6):
            self.save(self.client_a, self.hostel(f'H{i}'))
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client_a.get(WISHLIST, {'page_size': 6}).status_code, 200)
        self.assertLess(len(queries), 12, [q['sql'][:80] for q in queries])


class WishlistIdsAndDeleteTests(WishlistBase):
    def test_ids_lists_my_saved_active_hostels(self):
        saved, gone, other = self.hostel('Saved'), self.hostel('Gone'), self.hostel('Other')
        self.save(self.client_a, saved)
        self.save(self.client_a, gone)
        self.save(self.client_b, other)
        Hostel.objects.filter(pk=gone.pk).update(is_active=False)

        body = self.client_a.get(IDS).json()

        self.assertEqual(body['ids'], [str(saved.pk)])
        self.assertEqual(body['count'], 1)

    def test_deleting_by_hostel_works_and_can_be_repeated(self):
        h = self.hostel()
        self.save(self.client_a, h)

        first = self.client_a.delete(by_hostel(h.pk))
        second = self.client_a.delete(by_hostel(h.pk))

        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertTrue(first.json()['deleted'])
        self.assertFalse(second.json()['deleted'])
        self.assertEqual(Wishlist.objects.count(), 0)

    def test_deleting_by_hostel_never_touches_someone_elses_row(self):
        h = self.hostel()
        self.save(self.client_a, h)
        self.save(self.client_b, h)

        self.client_a.delete(by_hostel(h.pk))

        self.assertEqual(list(Wishlist.objects.values_list('user_id', flat=True)), [self.b.pk])

    def test_deleting_an_unknown_hostel_is_still_a_success(self):
        response = self.client_a.delete(by_hostel('00000000-0000-0000-0000-000000000000'))
        self.assertEqual(response.status_code, 200)


class SearchOtherScriptsTests(WishlistBase):
    def setUp(self):
        super().setUp()
        self.city = City.objects.create(name='Hyderabad', state='Telangana')
        self.locality = Locality.objects.create(city=self.city, name='Kondapur')
        self.h = self.hostel('Plain Name')
        Hostel.objects.filter(pk=self.h.pk).update(city_ref=self.city, locality_ref=self.locality, locality='Kondapur')

    def test_match_key_keeps_working_for_latin_text(self):
        self.assertEqual(match_key('K.P.H.B  Colony'), match_key('kphb colony'))
        self.assertEqual(match_key('Café'), match_key('cafe'))

    def test_match_key_tells_telugu_and_hindi_words_apart_instead_of_emptying_them(self):
        self.assertTrue(match_key('కొండాపూర్'))
        self.assertTrue(match_key('कोंडापुर'))
        self.assertNotEqual(match_key('కొండాపూర్'), match_key('కూకట్‌పల్లి'))

    def test_staff_can_add_a_telugu_alias_and_search_finds_the_hostel(self):
        LocalityAlias.objects.create(locality=self.locality, alias_slug='కొండాపూర్')

        found = APIClient().get(LIST, {'search': 'కొండాపూర్'}).json()

        self.assertEqual([r['name'] for r in found['results']], ['Plain Name'])

    def test_an_alias_spelling_in_latin_letters_works_too(self):
        LocalityAlias.objects.create(locality=self.locality, alias_slug='Kondapoor')

        found = APIClient().get(LIST, {'search': 'kondapoor'}).json()

        self.assertEqual(found['count'], 1)

    def test_a_word_that_is_nobody_s_alias_finds_nothing(self):
        LocalityAlias.objects.create(locality=self.locality, alias_slug='కొండాపూర్')
        self.assertEqual(APIClient().get(LIST, {'search': 'కూకట్పల్లి'}).json()['count'], 0)
