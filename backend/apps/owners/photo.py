"""
POST /api/v1/auth/me/photo/  (multipart, field "profile_photo")

The image goes to Cloudinary using an *unsigned upload preset*, so the backend needs only the cloud
name and the preset name (CLOUDINARY_CLOUD_NAME, CLOUDINARY_UPLOAD_PRESET), no API secret. The
returned https URL is stored on the owner. Nothing is written to the server's disk, which is wiped on
every deploy.
"""
import logging

import requests
from django.conf import settings
from PIL import Image, UnidentifiedImageError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .serializers import OwnerProfileSerializer
from .views import error_response, success_response

logger = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024
ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
UPLOAD_TIMEOUT_SECONDS = 20


class OwnerPhotoView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        upload = request.FILES.get('profile_photo')
        if upload is None:
            return error_response({'profile_photo': 'No file was uploaded.'}, 'No file was uploaded.')
        if upload.size > MAX_BYTES:
            return error_response({'profile_photo': 'The image is too large (5 MB maximum).'}, 'The image is too large (5 MB maximum).')
        if upload.content_type not in ALLOWED_TYPES:
            return error_response({'profile_photo': 'Use a JPEG, PNG or WebP image.'}, 'Use a JPEG, PNG or WebP image.')
        try:
            Image.open(upload).verify()
        except (UnidentifiedImageError, OSError, SyntaxError):
            return error_response({'profile_photo': 'The file is not a valid image.'}, 'The file is not a valid image.')
        upload.seek(0)

        cloud, preset = settings.CLOUDINARY_CLOUD_NAME, settings.CLOUDINARY_UPLOAD_PRESET
        if not cloud or not preset:
            logger.error('Photo upload is not configured (CLOUDINARY_CLOUD_NAME / CLOUDINARY_UPLOAD_PRESET).')
            return error_response({'profile_photo': 'Photo upload is not configured.'}, 'Photo upload is not configured.', 503)

        failure = error_response({'profile_photo': 'Could not store the photo. Please try again.'}, 'Could not store the photo. Please try again.', 502)
        try:
            reply = requests.post(
                f'https://api.cloudinary.com/v1_1/{cloud}/image/upload',
                data={'upload_preset': preset, 'folder': 'profiles'},
                files={'file': (upload.name, upload.read(), upload.content_type)},
                timeout=UPLOAD_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            logger.error('Cloudinary upload failed: %s', type(exc).__name__)
            return failure
        if reply.status_code != 200:
            logger.error('Cloudinary upload failed: HTTP %s', reply.status_code)
            return failure
        try:
            url = reply.json().get('secure_url', '')
        except ValueError:
            url = ''
        if not url.startswith(f'https://res.cloudinary.com/{cloud}/'):
            logger.error('Cloudinary returned an unexpected URL')
            return failure

        user = request.user
        user.profile_photo_url = url
        user.save(update_fields=['profile_photo_url', 'updated_at'])
        return success_response(data=OwnerProfileSerializer(user).data, message='Profile photo updated.')
