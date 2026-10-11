"""Phase T2: profile edit rules, photo upload limits, error bodies, student stats scope, booking contact."""
import io
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import ScopedRateThrottle

from apps.bookings.models import Booking
from apps.hostels.models import Hostel

from .test_profile_and_photo import CLOUD, GOOD_URL, ME, PHOTO, cloudinary_reply, png_bytes

Owner = get_user_model()


def make_hostel(owner):
    return Hostel.objects.create(
        owner=owner, name='H', owner_name=owner.display_name, contact_number='9999999999',
        email=owner.email, locality='Loc', address='Addr', city='City', state='State',
        pincode='500000', gender_type='co_living',
    )


class ProfilePatchRulesTests(APITestCase):
    def setUp(self):
        self.user = Owner.objects.create_user(
            email='rules@example.test', display_name='Old', phone_number='9000000002', password='pass12345',
        )
        self.client.force_authenticate(user=self.user)

    def test_fields_outside_the_whitelist_are_refused_by_name(self):
        response = self.client.patch(
            ME, {'display_name': 'Sneaky', 'role': 'admin', 'is_staff': True, 'profile_photo_url': 'https://x.test/a.jpg'},
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.content)
        errors = response.json()['errors']
        self.assertEqual(set(errors), {'role', 'is_staff', 'profile_photo_url'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, 'Old', 'nothing may change when the request is refused')
        self.assertFalse(self.user.is_staff)

    def test_gender_and_date_of_birth_can_be_cleared_with_null(self):
        self.user.gender, self.user.date_of_birth = 'male', '2000-01-01'
        self.user.save()
        response = self.client.patch(ME, {'gender': None, 'date_of_birth': None}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()['data']
        self.assertIsNone(data['gender'])
        self.assertIsNone(data['date_of_birth'])

    def test_a_date_of_birth_in_the_future_is_refused(self):
        response = self.client.patch(ME, {'date_of_birth': '2999-01-01'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('date_of_birth', response.json()['errors'])

    def test_a_date_of_birth_before_1900_is_refused(self):
        response = self.client.patch(ME, {'date_of_birth': '1850-01-01'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_a_blank_name_is_refused_and_spaces_are_trimmed(self):
        self.assertEqual(self.client.patch(ME, {'display_name': '   '}, format='json').status_code, 400)
        response = self.client.patch(ME, {'display_name': '  Asha Rao  '}, format='json')
        self.assertEqual(response.json()['data']['display_name'], 'Asha Rao')


class ErrorBodyShapeTests(APITestCase):
    """The app's error reader depends on these shapes: keep them."""

    def setUp(self):
        cache.clear()
        self.user = Owner.objects.create_user(email='shape@example.test', display_name='S', password='pass12345')
        self.client.force_authenticate(user=self.user)

    def test_405_keeps_its_detail_field(self):
        response = self.client.delete(ME)
        self.assertEqual(response.status_code, 405)
        self.assertIn('detail', response.json())

    def test_401_keeps_its_detail_field(self):
        response = APIClient().get(ME)
        self.assertEqual(response.status_code, 401)
        self.assertIn('detail', response.json())

    @override_settings(**CLOUD)
    def test_429_keeps_detail_and_sends_retry_after(self):
        rates = {**ScopedRateThrottle.THROTTLE_RATES, 'photo': '2/hour'}
        with mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', rates), \
                mock.patch('requests.post', return_value=cloudinary_reply()):
            statuses = []
            for _ in range(3):
                statuses.append(self.client.post(
                    PHOTO, {'profile_photo': SimpleUploadedFile('a.png', png_bytes(), content_type='image/png')},
                    format='multipart',
                ))
        self.assertEqual([r.status_code for r in statuses], [200, 200, 429])
        self.assertIn('detail', statuses[2].json())
        self.assertTrue(int(statuses[2]['Retry-After']) > 0)


@override_settings(**CLOUD)
class PhotoLimitsTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = Owner.objects.create_user(email='limits@example.test', display_name='L', password='pass12345')
        self.client.force_authenticate(user=self.user)

    def upload(self, content, **extra):
        return self.client.post(
            PHOTO, {'profile_photo': SimpleUploadedFile('a.png', content, content_type='image/png')},
            format='multipart', **extra,
        )

    def test_the_outbound_call_has_a_10_second_timeout(self):
        with mock.patch('requests.post', return_value=cloudinary_reply()) as post:
            response = self.upload(png_bytes())
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(post.call_args.kwargs['timeout'], 10)
        self.assertEqual(response.json()['data']['profile_photo_url'], GOOD_URL)

    def test_a_timeout_is_a_502_with_a_reason(self):
        import requests
        with mock.patch('requests.post', side_effect=requests.Timeout()):
            response = self.upload(png_bytes())
        self.assertEqual(response.status_code, 502)
        self.assertIn('try again', response.json()['message'].lower())

    def test_an_oversized_request_is_refused_before_the_body_is_read(self):
        with mock.patch('requests.post') as post:
            response = self.upload(png_bytes(), CONTENT_LENGTH=str(50 * 1024 * 1024))
        self.assertEqual(response.status_code, 413)
        self.assertIn('too large', response.json()['message'].lower())
        post.assert_not_called()

    def test_an_image_with_too_many_pixels_is_refused(self):
        buffer = io.BytesIO()
        Image.new('L', (6000, 6000), 0).save(buffer, 'PNG')  # 36 megapixels, tiny file
        with mock.patch('requests.post') as post:
            response = self.upload(buffer.getvalue())
        self.assertEqual(response.status_code, 400)
        self.assertIn('dimensions', response.json()['message'].lower())
        post.assert_not_called()


class StudentStatsScopeTests(APITestCase):
    def setUp(self):
        self.owner = Owner.objects.create_user(email='own@example.test', display_name='Owner', password='pass12345')
        self.me = Owner.objects.create_user(email='me@example.test', display_name='Rahul', password='pass12345')
        self.hostel = make_hostel(self.owner)
        self.client.force_authenticate(user=self.me)

    def stats(self):
        response = self.client.get('/api/v1/dashboard/student/stats/')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_a_stranger_with_the_same_name_does_not_show_up_in_my_stats(self):
        Booking.objects.create(hostel=self.hostel, student_name='Rahul', status='pending')  # anonymous booking
        Booking.objects.create(hostel=self.hostel, student=self.me, student_name='Rahul', status='pending')
        data = self.stats()
        self.assertEqual(data['booking_stats']['total'], 1)
        self.assertEqual(len(data['recent_activity']), 1)

    def test_my_bookings_are_counted(self):
        for _ in range(3):
            Booking.objects.create(hostel=self.hostel, student=self.me, status='pending')
        self.assertEqual(self.stats()['booking_stats']['total'], 3)


class BookingContactTests(APITestCase):
    def setUp(self):
        self.owner = Owner.objects.create_user(email='o2@example.test', display_name='Owner', password='pass12345')
        self.student = Owner.objects.create_user(
            email='st@example.test', display_name='Asha Rao', phone_number='9000000003', password='pass12345',
        )
        self.hostel = make_hostel(self.owner)

    def post_booking(self, **extra):
        return self.client.post('/api/v1/bookings/', {'hostel': str(self.hostel.pk), **extra}, format='json')

    def test_a_logged_in_student_with_blank_contact_gets_it_from_the_profile(self):
        self.client.force_authenticate(user=self.student)
        response = self.post_booking(student_name='', student_phone='')
        self.assertEqual(response.status_code, 201, response.content)
        booking = Booking.objects.get(pk=response.json()['id'])
        self.assertEqual((booking.student_name, booking.student_phone), ('Asha Rao', '9000000003'))

    def test_contact_sent_by_the_app_is_kept(self):
        self.client.force_authenticate(user=self.student)
        response = self.post_booking(student_name='Typed Name', student_phone='9111111111')
        booking = Booking.objects.get(pk=response.json()['id'])
        self.assertEqual((booking.student_name, booking.student_phone), ('Typed Name', '9111111111'))
