"""
POST /api/v1/auth/me/photo/  (multipart, field "profile_photo")

The image goes to Cloudinary using an *unsigned upload preset*, so the backend needs only the cloud
name and the preset name (CLOUDINARY_CLOUD_NAME, CLOUDINARY_UPLOAD_PRESET), no API secret. The
returned https URL is stored on the owner. Nothing is written to the server's disk, which is wiped on
every deploy.

The upload holds one server thread while it talks to Cloudinary, so it is limited: 10 seconds to
Cloudinary, 5 MB, a pixel cap, and a per-user rate limit (the "photo" throttle scope).
"""
import logging

import requests
from django.conf import settings
from drf_spectacular.utils import extend_schema
from PIL import Image, UnidentifiedImageError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from .serializers import OwnerProfileSerializer
from .views import ERROR_ENVELOPE, PROFILE_ENVELOPE, error_response, success_response

logger = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024
# A multipart body is a little larger than the file inside it.
MAX_REQUEST_BYTES = MAX_BYTES + 512 * 1024
MAX_PIXELS = 25_000_000
ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
UPLOAD_TIMEOUT_SECONDS = 10

TOO_LARGE = 'The image is too large (5 MB maximum).'


class OwnerPhotoView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = 'photo'

    @extend_schema(
        request={'multipart/form-data': {
            'type': 'object',
            'properties': {'profile_photo': {'type': 'string', 'format': 'binary'}},
            'required': ['profile_photo'],
        }},
        responses={200: PROFILE_ENVELOPE, 400: ERROR_ENVELOPE, 413: ERROR_ENVELOPE, 502: ERROR_ENVELOPE, 503: ERROR_ENVELOPE},
        summary='Upload the signed-in user\'s profile photo (JPEG, PNG or WebP, up to 5 MB)',
    )
    def post(self, request):
        # Refuse an oversized request before reading its body.
        try:
            declared = int(request.META.get('CONTENT_LENGTH') or 0)
        except ValueError:
            declared = 0
        if declared > MAX_REQUEST_BYTES:
            return error_response({'profile_photo': TOO_LARGE}, TOO_LARGE, 413)

        upload = request.FILES.get('profile_photo')
        if upload is None:
            return error_response({'profile_photo': 'No file was uploaded.'}, 'No file was uploaded.')
        if upload.size > MAX_BYTES:
            return error_response({'profile_photo': TOO_LARGE}, TOO_LARGE)
        if upload.content_type not in ALLOWED_TYPES:
            return error_response({'profile_photo': 'Use a JPEG, PNG or WebP image.'}, 'Use a JPEG, PNG or WebP image.')
        try:
            image = Image.open(upload)
            width, height = image.size
            if width * height > MAX_PIXELS:
                message = 'The image dimensions are too large. Choose a smaller photo.'
                return error_response({'profile_photo': message}, message)
            image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
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
