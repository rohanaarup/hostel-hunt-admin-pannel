import io
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient, APITestCase

Owner = get_user_model()
ME = '/api/v1/auth/me/'
PHOTO = '/api/v1/auth/me/photo/'
CLOUD = {'CLOUDINARY_CLOUD_NAME': 'democloud', 'CLOUDINARY_UPLOAD_PRESET': 'preset1'}
GOOD_URL = 'https://res.cloudinary.com/democloud/image/upload/v1/profiles/me.jpg'


def png_bytes(size=(8, 8)):
    buffer = io.BytesIO()
    Image.new('RGB', size, 'red').save(buffer, 'PNG')
    return buffer.getvalue()


def cloudinary_reply(status=200, url=GOOD_URL, text='ok'):
    reply = mock.Mock(status_code=status, text=text)
    reply.json.return_value = {'secure_url': url}
    return reply


class ProfileUpdateTests(APITestCase):
    def setUp(self):
        self.user = Owner.objects.create_user(
            email='student@example.test', display_name='Old Name', phone_number='9000000001', password='pass12345',
        )
        self.client.force_authenticate(user=self.user)

    def test_patch_updates_name_gender_and_date_of_birth(self):
        response = self.client.patch(ME, {'display_name': 'New Name', 'gender': 'female', 'date_of_birth': '2001-02-03'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()['data']
        self.assertEqual((data['display_name'], data['gender'], data['date_of_birth']), ('New Name', 'female', '2001-02-03'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, 'New Name')
        self.assertEqual(self.client.get(ME).json()['data']['gender'], 'female')

    def test_sending_the_current_email_or_phone_is_a_no_op(self):
        response = self.client.patch(ME, {'email': 'STUDENT@example.test', 'phone_number': '9000000001', 'display_name': 'Same'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)

    def test_changing_the_email_is_refused_with_a_reason(self):
        response = self.client.patch(ME, {'email': 'other@example.test'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('verification', str(response.json()['errors']['email']))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'student@example.test')

    def test_changing_the_phone_is_refused_with_a_reason(self):
        response = self.client.patch(ME, {'phone_number': '9111111111'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('verification', str(response.json()['errors']['phone_number']))

    def test_invalid_gender_is_rejected(self):
        self.assertEqual(self.client.patch(ME, {'gender': 'robot'}, format='json').status_code, 400)

    def test_requires_login(self):
        self.assertEqual(APIClient().patch(ME, {'display_name': 'x'}, format='json').status_code, 401)


@override_settings(**CLOUD)
class ProfilePhotoTests(APITestCase):
    def setUp(self):
        self.user = Owner.objects.create_user(email='photo@example.test', display_name='P', password='pass12345')
        self.client.force_authenticate(user=self.user)

    def upload(self, content=None, name='me.png', content_type='image/png'):
        content = png_bytes() if content is None else content
        return self.client.post(PHOTO, {'profile_photo': SimpleUploadedFile(name, content, content_type=content_type)}, format='multipart')

    def test_upload_stores_the_cloudinary_url(self):
        with mock.patch('requests.post', return_value=cloudinary_reply()) as post:
            response = self.upload()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['data']['profile_photo_url'], GOOD_URL)
        self.assertEqual(self.client.get(ME).json()['data']['profile_photo_url'], GOOD_URL)
        args, kwargs = post.call_args
        self.assertIn('democloud', args[0])
        self.assertEqual(kwargs['data']['upload_preset'], 'preset1')
        self.assertNotIn('api_secret', str(kwargs))

    def test_a_file_that_is_not_an_image_is_refused_without_calling_cloudinary(self):
        with mock.patch('requests.post') as post:
            response = self.upload(content=b'not an image at all', name='me.png')
        self.assertEqual(response.status_code, 400)
        post.assert_not_called()

    def test_a_wrong_content_type_is_refused(self):
        with mock.patch('requests.post') as post:
            response = self.upload(content_type='application/pdf', name='me.pdf')
        self.assertEqual(response.status_code, 400)
        post.assert_not_called()

    def test_a_file_over_5_mb_is_refused(self):
        with mock.patch('requests.post') as post:
            response = self.upload(content=b'x' * (5 * 1024 * 1024 + 1))
        self.assertEqual(response.status_code, 400)
        self.assertIn('too large', str(response.json()).lower())
        post.assert_not_called()

    def test_no_file_is_a_400(self):
        self.assertEqual(self.client.post(PHOTO, {}, format='multipart').status_code, 400)

    @override_settings(CLOUDINARY_CLOUD_NAME='', CLOUDINARY_UPLOAD_PRESET='')
    def test_unconfigured_is_503_with_a_reason(self):
        with mock.patch('requests.post') as post:
            response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertIn('not configured', str(response.json()).lower())
        post.assert_not_called()

    def test_provider_error_is_502_and_its_text_is_not_leaked(self):
        with mock.patch('requests.post', return_value=cloudinary_reply(status=500, text='internal cloudinary detail')):
            response = self.upload()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('internal cloudinary detail', response.content.decode())

    def test_a_url_from_another_host_is_not_stored(self):
        with mock.patch('requests.post', return_value=cloudinary_reply(url='https://evil.example/x.jpg')):
            response = self.upload()
        self.assertEqual(response.status_code, 502)
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile_photo_url)

    def test_requires_login(self):
        self.assertEqual(APIClient().post(PHOTO, {}, format='multipart').status_code, 401)
