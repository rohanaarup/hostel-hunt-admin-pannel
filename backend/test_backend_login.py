import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.owners.models import Owner
from rest_framework_simplejwt.tokens import RefreshToken
import requests

# Find or create a test owner
email = 'rudraarupa22@gmail.com'
try:
    user = Owner.objects.get(email=email)
    print(f"Found user {email}")
except Owner.DoesNotExist:
    user = Owner.objects.create_user(email=email, password='Password123!', display_name='Test Admin')
    print(f"Created user {email}")

# Generate JWT Token directly without HTTP request
refresh = RefreshToken.for_user(user)
access_token = str(refresh.access_token)
print("Access token generated.")

# Test endpoints
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

print("Fetching hostels...")
resp = requests.get('http://127.0.0.1:8001/api/v1/hostels/', headers=headers)
print("GET hostels:", resp.status_code)
if resp.status_code == 200:
    hostels = resp.json()
    if hostels:
        h = hostels[0]
        url = f"http://127.0.0.1:8001/api/v1/hostels/{h['hostel_id']}/"
        print(f"PUTing to {url}")
        resp = requests.put(url, headers=headers, json=h)
        print("PUT hostel:", resp.status_code, resp.text[:300])
    else:
        print("No hostels found for this user.")

