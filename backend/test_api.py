import requests
import json

base_url = 'http://127.0.0.1:8001/api/v1'

# 1. Login
print("Logging in...")
res = requests.post(f"{base_url}/auth/login/", json={
    'identifier': 'rohandharlapally22@gmail.com',
    'identifier_type': 'email',
    'password': 'adminpassword123'
})

if res.status_code != 200:
    print("Login failed:", res.status_code, res.text)
    exit(1)

tokens = res.json()
access_token = tokens.get('data', {}).get('tokens', {}).get('access')

if not access_token:
    print("No access token found:", tokens)
    exit(1)

print("Logged in successfully.")

# 2. Create Hostel
payload = {
    'name': 'Test Hostel Subagent',
    'owner_name': 'Rohan Owner',
    'contact_number': '1234567890',
    'email': 'rohan@testhostel.com',
    'address': '123 Test Street',
    'city': 'Hyderabad',
    'state': 'Telangana',
    'pincode': '500001',
    'google_maps_url': 'http://maps.google.com/?q=test',
    'landmark': 'Near Charminar',
    'latitude': '17.3850',
    'longitude': '78.4867',
    'gender_type': 'boys',
    'total_floors': 3,
    'total_rooms': 10,
    'total_beds': 30,
    'occupancy_types': ['single', 'double'],
    'description': 'A very nice test hostel.',
    'rules': 'No smoking.',
    'check_in_policy': '12:00 PM',
    'check_out_policy': '11:00 AM',
    'amenities': ['wifi', 'ac']
}

print("Payload:", json.dumps(payload, indent=2))

print("Sending POST request to /hostels/...")
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}
res_hostel = requests.post(f"{base_url}/hostels/", json=payload, headers=headers)

print("Response Status:", res_hostel.status_code)
with open('response.html', 'w', encoding='utf-8') as f:
    f.write(res_hostel.text)
print("Response JSON saved to response.html")
