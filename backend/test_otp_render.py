import requests
import uuid

email = f"tester_{uuid.uuid4().hex[:6]}@gmail.com"
base_url = 'https://hostel-hunt-backend.onrender.com/api/v1'

print(f"Requesting OTP for {email} on Render...")
res = requests.post(f"{base_url}/auth/send-otp/", json={
    'identifier': email,
    'identifier_type': 'email',
    'purpose': 'signup'
})

print("Status:", res.status_code)
print("Response:", res.text)
