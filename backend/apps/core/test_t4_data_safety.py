"""Phase T4: data safety (students never see each other's bookings, media linking, legacy bookings)
and the numbers the admin dashboard shows."""
import io
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from apps.bookings.models import Booking
from apps.hostels.models import Hostel
from apps.media_uploads.models import MediaItem
from apps.rooms.models import Room

Owner = get_user_model()
CLOUD_URL = 'https://res.cloudinary.com/democloud/image/upload/v1/hostels/a.jpg'


def make_hostel(owner, name='H'):
    return Hostel.objects.create(
        owner=owner, name=name, owner_name='Owner', contact_number='9999999999', email='o@example.test',
        locality='Kondapur', address='1 Road', city='Hyderabad', state='Telangana',
        pincode='500084', gender_type='boys',
    )


class SharedDisplayNameTests(APITestCase):
    """Two students with the same display name must never see each other's bookings."""

    def setUp(self):
        self.owner = Owner.objects.create_user(email='owner@example.test', display_name='Owner', password='pass12345')
        self.a = Owner.objects.create_user(email='a@example.test', display_name='Rahul Kumar', password='pass12345')
        self.b = Owner.objects.create_user(email='b@example.test', display_name='Rahul Kumar', password='pass12345')
        self.hostel = make_hostel(self.owner)
        Booking.objects.create(hostel=self.hostel, student=self.a, student_name='Rahul Kumar', status='pending')
        Booking.objects.create(hostel=self.hostel, student=self.b, student_name='Rahul Kumar', status='confirmed')
        Booking.objects.create(hostel=self.hostel, student=self.b, student_name='Rahul Kumar', status='paid')
        Booking.objects.create(hostel=self.hostel, student_name='Rahul Kumar', status='pending')  # anonymous, same name

    def as_student(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_the_student_dashboard_counts_only_my_bookings(self):
        for user, expected in ((self.a, 1), (self.b, 2)):
            data = self.as_student(user).get('/api/v1/dashboard/student/stats/').json()
            self.assertEqual(data['booking_stats']['total'], expected)
            self.assertEqual(len(data['recent_activity']), expected)

    def test_my_bookings_list_matches(self):
        for user, expected in ((self.a, 1), (self.b, 2)):
            self.assertEqual(self.as_student(user).get('/api/v1/bookings/my/').json()['count'], expected)

    def test_the_active_booking_is_never_the_other_students(self):
        data = self.as_student(self.a).get('/api/v1/dashboard/student/stats/').json()
        self.assertIsNone(data['active_booking'], 'student A has only a pending booking; B\'s paid one is not theirs')

    def test_the_anonymous_booking_shows_to_the_hostel_owner_only(self):
        owner = APIClient()
        owner.force_authenticate(user=self.owner)
        self.assertEqual(owner.get('/api/v1/bookings/').json()['count'], 4)


class OwnerDashboardNumbersTests(APITestCase):
    def setUp(self):
        self.owner = Owner.objects.create_user(email='owner@example.test', display_name='Owner', password='pass12345')
        self.other = Owner.objects.create_user(email='other@example.test', display_name='Other', password='pass12345')
        self.hostel = make_hostel(self.owner)
        Hostel.objects.filter(pk=self.hostel.pk).update(total_beds=5)  # the number the occupancy rate already uses
        other_hostel = make_hostel(self.other, 'Not mine')
        Room.objects.create(hostel=self.hostel, room_name='R1', sharing_type='double', capacity=2, bed_count=2,
                            price_per_month='6000.00', available_beds=2)
        Room.objects.create(hostel=self.hostel, room_name='R2', sharing_type='triple', capacity=3, bed_count=3,
                            price_per_month='5000.00', available_beds=3)
        for status, mode in [('pending', 'offline'), ('pending', 'online'), ('confirmed', 'offline'),
                             ('paid', 'online'), ('rejected', 'offline')]:
            Booking.objects.create(hostel=self.hostel, student_name='S', status=status, payment_mode=mode)
        Booking.objects.create(hostel=other_hostel, student_name='S', status='pending', payment_mode='online')
        self.client.force_authenticate(user=self.owner)

    def data(self):
        response = self.client.get('/api/v1/dashboard/stats/')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['data']

    def test_bookings_are_counted_by_status_across_all_of_them(self):
        self.assertEqual(
            self.data()['bookings_by_status'],
            {'pending': 2, 'confirmed': 1, 'paid': 1, 'cancelled': 0, 'rejected': 1},
        )

    def test_bookings_are_counted_by_payment_mode(self):
        self.assertEqual(self.data()['bookings_by_payment_mode'], {'offline': 3, 'online': 2})

    def test_beds_and_the_old_numbers_are_there(self):
        data = self.data()
        self.assertEqual(data['total_beds'], 5)
        for key in ('total_hostels', 'total_residents', 'occupancy_rate', 'revenue_collected', 'revenue_pending', 'pending_bookings'):
            self.assertIn(key, data)
        self.assertEqual(data['pending_bookings'], 2)

    def test_the_pending_filter_the_dashboard_uses_works(self):
        response = self.client.get('/api/v1/bookings/', {'status': 'pending', 'page_size': 10}).json()
        self.assertEqual(response['count'], 2)


@override_settings(CLOUDINARY_CLOUD_NAME='democloud')
class MediaSafetyTests(APITestCase):
    def setUp(self):
        self.a = Owner.objects.create_user(email='a@example.test', display_name='A', password='pass12345')
        self.b = Owner.objects.create_user(email='b@example.test', display_name='B', password='pass12345')
        self.hostel_a = make_hostel(self.a, 'A hostel')
        self.client_a = APIClient()
        self.client_a.force_authenticate(user=self.a)
        self.client_b = APIClient()
        self.client_b.force_authenticate(user=self.b)

    def upload(self, client, url=CLOUD_URL, hostel=None):
        return client.post('/api/v1/media/upload/', {
            'hostel': str(hostel.pk) if hostel else None, 'category': 'hostel', 'file_url': url,
            'mime_type': 'image/jpeg', 'file_name': 'a.jpg',
        }, format='json')

    def new_hostel_payload(self, media_ids):
        return {'name': 'B new', 'owner_name': 'B', 'contact_number': '9999999999', 'email': 'b@example.test',
                'locality': 'Kondapur', 'address': '1 Road', 'city': 'Hyderabad', 'state': 'Telangana',
                'pincode': '500084', 'gender_type': 'boys', 'media_ids': media_ids}

    def test_an_address_that_is_not_https_on_cloudinary_is_refused(self):
        for bad in ('http://res.cloudinary.com/democloud/image/upload/a.jpg',
                    'https://evil.example/a.jpg',
                    'https://res.cloudinary.com/othercloud/image/upload/a.jpg',
                    'javascript:alert(1)'):
            response = self.upload(self.client_a, url=bad)
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn('file_url', response.json())
        self.assertEqual(MediaItem.objects.count(), 0)

    def test_a_cloudinary_address_is_accepted(self):
        self.assertEqual(self.upload(self.client_a).status_code, 201)

    def test_another_owner_cannot_attach_my_media_to_their_hostel(self):
        mine = MediaItem.objects.create(hostel=self.hostel_a, category='hostel', file_url=CLOUD_URL)

        response = self.client_b.post('/api/v1/hostels/', self.new_hostel_payload([str(mine.pk)]), format='json')

        self.assertEqual(response.status_code, 201, response.content)
        mine.refresh_from_db()
        self.assertEqual(mine.hostel_id, self.hostel_a.pk, 'the media must stay on its real hostel')

    def test_unclaimed_media_is_linked_to_the_new_hostel(self):
        pending = self.upload(self.client_b).json()['id']

        response = self.client_b.post('/api/v1/hostels/', self.new_hostel_payload([pending]), format='json')

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(MediaItem.objects.get(pk=pending).hostel_id, Hostel.objects.get(name='B new').pk)

    def test_a_temporary_id_is_a_clear_400_naming_the_field(self):
        response = self.client_b.post('/api/v1/hostels/', self.new_hostel_payload(['k3j2h1x9']), format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('media_ids', response.json())
        self.assertFalse(Hostel.objects.filter(name='B new').exists())

    def test_updating_my_hostel_cannot_pull_in_someone_elses_media(self):
        hostel_b = make_hostel(self.b, 'B hostel')
        theirs = MediaItem.objects.create(hostel=hostel_b, category='hostel', file_url=CLOUD_URL)

        response = self.client_a.patch(f'/api/v1/hostels/{self.hostel_a.pk}/', {'media_ids': [str(theirs.pk)]}, format='json')

        self.assertEqual(response.status_code, 200, response.content)
        theirs.refresh_from_db()
        self.assertEqual(theirs.hostel_id, hostel_b.pk)


@override_settings(APP_ENV='staging')
class LinkLegacyBookingsTests(APITestCase):
    def setUp(self):
        self.owner = Owner.objects.create_user(email='owner@example.test', display_name='Owner', password='pass12345')
        self.hostel = make_hostel(self.owner)
        self.alice = Owner.objects.create_user(
            email='alice@example.test', display_name='Alice', phone_number='+919000000001', password='pass12345')
        self.alice.is_verified = True
        self.alice.save()
        # two verified accounts with the same number stored in different formats: ambiguous
        for email, phone in (('x@example.test', '+919000000002'), ('y@example.test', '9000000002')):
            user = Owner.objects.create_user(email=email, display_name=email, phone_number=phone, password='pass12345')
            user.is_verified = True
            user.save()
        # a verified-looking number on an account that was never verified
        self.unverified = Owner.objects.create_user(
            email='u@example.test', display_name='Unverified', phone_number='+919000000004', password='pass12345')

        def booking(phone, **kw):
            return Booking.objects.create(hostel=self.hostel, student_name='Typed Name', student_phone=phone, **kw)

        self.exact = booking('90000 00001')           # one verified account (typed with a space)
        self.exact_with_prefix = booking('+91-9000000001')
        self.several = booking('9000000002')           # two verified accounts
        self.nobody = booking('9000000099')            # no account
        self.not_verified = booking('9000000004')      # only an unverified account has it
        self.no_phone = booking('')                    # nothing typed
        self.short = booking('12345')                  # not a phone number
        self.already_linked = Booking.objects.create(hostel=self.hostel, student=self.alice, student_name='x', student_phone='9000000001')

    def run_command(self, *args):
        out = io.StringIO()
        call_command('link_legacy_bookings', *args, stdout=out)
        return out.getvalue()

    def student_of(self, booking):
        return Booking.objects.get(pk=booking.pk).student_id

    def test_it_refuses_to_run_anywhere_but_staging(self):
        with override_settings(APP_ENV='production'):
            with self.assertRaises(CommandError):
                self.run_command()

    def test_a_dry_run_changes_nothing_and_prints_counts_only(self):
        output = self.run_command()

        self.assertIn('DRY RUN', output)
        self.assertEqual(Booking.objects.filter(student__isnull=True).count(), 7)
        for secret in ('9000000001', '90000 00001', 'Typed Name', 'alice', 'Alice', '@example.test'):
            self.assertNotIn(secret, output, 'the command must never print names, emails or phone numbers')
        self.assertRegex(output, r'exactly one[^\n]*: 2')
        self.assertRegex(output, r'several[^\n]*: 1')

    def test_an_explicit_dry_run_flag_is_the_same_as_the_default(self):
        self.run_command('--dry-run')
        self.assertEqual(Booking.objects.filter(student__isnull=True).count(), 7)

    def test_apply_links_only_where_exactly_one_verified_account_matches(self):
        undo = Path(tempfile.mkdtemp()) / 'undo.json'

        output = self.run_command('--apply', '--undo-file', str(undo))

        self.assertEqual(self.student_of(self.exact), self.alice.pk)
        self.assertEqual(self.student_of(self.exact_with_prefix), self.alice.pk)
        for left_alone in (self.several, self.nobody, self.not_verified, self.no_phone, self.short):
            self.assertIsNone(self.student_of(left_alone))
        self.assertEqual(self.student_of(self.already_linked), self.alice.pk)
        self.assertNotIn('9000000001', output)
        self.assertEqual(len(json.loads(undo.read_text())['booking_ids']), 2)

    def test_restore_unlinks_exactly_what_apply_linked(self):
        undo = Path(tempfile.mkdtemp()) / 'undo.json'
        self.run_command('--apply', '--undo-file', str(undo))

        self.run_command('--restore', str(undo))

        self.assertIsNone(self.student_of(self.exact))
        self.assertIsNone(self.student_of(self.exact_with_prefix))
        self.assertEqual(self.student_of(self.already_linked), self.alice.pk, 'a booking that was linked before is untouched')

    def test_running_it_twice_changes_nothing_the_second_time(self):
        self.run_command('--apply', '--undo-file', str(Path(tempfile.mkdtemp()) / 'u.json'))
        output = self.run_command('--apply', '--undo-file', str(Path(tempfile.mkdtemp()) / 'u2.json'))
        self.assertRegex(output, r'exactly one[^\n]*: 0')

    def test_after_linking_the_student_sees_it_and_a_stranger_does_not(self):
        self.run_command('--apply', '--undo-file', str(Path(tempfile.mkdtemp()) / 'u.json'))
        client = APIClient()
        client.force_authenticate(user=self.alice)
        self.assertEqual(client.get('/api/v1/bookings/my/').json()['count'], 3)
        stranger = Owner.objects.create_user(email='s@example.test', display_name='Alice', password='pass12345')
        client.force_authenticate(user=stranger)
        self.assertEqual(client.get('/api/v1/bookings/my/').json()['count'], 0)
