import os
import django
import requests
import uuid
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.hashers import make_password

# Setup local Django settings pointing to Railway Postgres
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.owners.models import OTPRecord
from apps.owners.models import Owner

# Generate a fresh email and token
email = f"tester_{uuid.uuid4().hex[:6]}@example.com"
v_token = uuid.uuid4()

print(f"Creating OTPRecord in Railway DB for {email}...")
OTPRecord.objects.create(
    identifier=email,
    otp_code=make_password('123456'),
    purpose='signup',
    expires_at=timezone.now() + timedelta(minutes=10),
    is_used=False,
    is_verified=True,
    verification_token=v_token
)

print("Making signup request to live Render API...")
base_url = 'https://hostel-hunt-backend.onrender.com/api/v1'
payload = {
    'identifier': email,
    'identifier_type': 'email',
    'display_name': 'Test User Render',
    'password': 'Password123!',
    'verification_token': str(v_token)
}

res = requests.post(f"{base_url}/auth/register/", json=payload)
print("Response Status:", res.status_code)
print("Response JSON:", res.text)
