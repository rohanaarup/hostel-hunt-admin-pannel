import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.owners.serializers import SignupSerializer
from apps.owners.models import OTPRecord
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.hashers import make_password
import uuid

# 1. Setup mock OTP record as if verified
email = 'tester99@example.com'
v_token = uuid.uuid4()
OTPRecord.objects.create(
    identifier=email,
    otp_code=make_password('123456'),
    purpose='signup',
    expires_at=timezone.now() + timedelta(minutes=10),
    is_used=True,
    verification_token=v_token
)

# 2. Test the serializer
data = {
    'identifier': email,
    'identifier_type': 'email',
    'display_name': 'Owner',
    'password': 'Password123!',
    'verification_token': str(v_token)
}

serializer = SignupSerializer(data=data)
if serializer.is_valid():
    print("Valid!")
    try:
        user = serializer.save()
        print("Saved user:", user)
        # Try getting tokens
        from apps.owners.views import get_tokens_for_user
        tokens = get_tokens_for_user(user)
        print("Tokens:", tokens)
    except Exception as e:
        import traceback
        traceback.print_exc()
else:
    print("Serializer invalid:", serializer.errors)
