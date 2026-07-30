import requests

base_url = 'https://hostel-hunt-backend.onrender.com/api/v1'
print("Checking live version...")
try:
    res = requests.get(f"{base_url}/debug-version/")
    print("Status:", res.status_code)
    print("Response:", res.text)
except Exception as e:
    print("Error:", e)
