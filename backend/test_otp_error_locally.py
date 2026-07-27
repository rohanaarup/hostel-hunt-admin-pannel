import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
# Force DEBUG=False and ALLOWED_HOSTS for testing
settings.DEBUG = False
settings.ALLOWED_HOSTS = ['*']

# Force invalid email password to trigger SMTP failure
settings.EMAIL_HOST_PASSWORD = 'wrong_password_to_force_failure'

from rest_framework.test import APIClient
client = APIClient()

print("Sending request to /api/v1/auth/send-otp/ with DEBUG=False...")
try:
    response = client.post('/api/v1/auth/send-otp/', {
        'identifier': 'tester_error@gmail.com',
        'identifier_type': 'email',
        'purpose': 'signup'
    }, format='json')
    print("Status:", response.status_code)
    print("Content:", response.content)
except Exception as e:
    import traceback
    traceback.print_exc()
