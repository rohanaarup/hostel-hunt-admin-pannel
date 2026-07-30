import requests
import uuid

email = f"tester_{uuid.uuid4().hex[:6]}@gmail.com"
base_url = 'http://127.0.0.1:8000/api/v1'

print(f"Requesting OTP for {email} locally...")
res = requests.post(f"{base_url}/auth/send-otp/", json={
    'identifier': email,
    'identifier_type': 'email',
    'purpose': 'signup'
})

print("Status:", res.status_code)
print("Response:", res.text)
