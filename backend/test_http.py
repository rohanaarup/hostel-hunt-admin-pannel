import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.test import Client
import json
from apps.owners.models import OTPRecord
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.hashers import make_password
import uuid

c = Client()
email = 'tester_http@example.com'
v_token = uuid.uuid4()
OTPRecord.objects.create(
    identifier=email,
    otp_code=make_password('123456'),
    purpose='signup',
    expires_at=timezone.now() + timedelta(minutes=10),
    is_used=True,
    verification_token=v_token
)

res = c.post('/api/v1/auth/register/', json.dumps({
    'identifier': email,
    'identifier_type': 'email',
    'display_name': 'Owner Http',
    'password': 'Password123!',
    'verification_token': str(v_token)
}), content_type='application/json')

print("STATUS:", res.status_code)
print("CONTENT:", res.content.decode('utf-8'))
