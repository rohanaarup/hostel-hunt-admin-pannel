import requests
import json

base_url = 'https://hostel-hunt-backend.onrender.com/api/v1'

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

# Get hostels to get valid hostel/room IDs
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}
res_hostels = requests.get(f"{base_url}/hostels/", headers=headers)
if res_hostels.status_code != 200:
    print("Failed to get hostels:", res_hostels.status_code, res_hostels.text)
    exit(1)

hostels = res_hostels.json()
# The response might be raw DRF list or enveloped
hostels_list = hostels.get('data', {}).get('results', []) if isinstance(hostels, dict) else hostels
if not hostels_list:
    hostels_list = hostels

if not hostels_list:
    print("No hostels found to book.")
    exit(1)

hostel_id = 'de83e62b-ba85-4673-a3f7-aad0ef122d84'
room_id = '650726d2-7816-4af2-9e05-1d1d72b58c71'
room_name = '101'

booking_payload = {
    'hostel': hostel_id,
    'room': room_id,
    'room_name': room_name,
    'floor_number': '1',
    'room_number': '101',
    'bed_number': 'Bed 1',
    'check_in_date': '2026-07-15'
}

print("Sending POST request to /bookings/...")
res_booking = requests.post(f"{base_url}/bookings/", json=booking_payload, headers=headers)
print("Response Status:", res_booking.status_code)
with open('debug_booking.html', 'w', encoding='utf-8') as f:
    f.write(res_booking.text)
print("Saved debug_booking.html")
