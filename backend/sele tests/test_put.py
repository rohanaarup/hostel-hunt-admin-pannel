import requests

# 1. Login to get JWT
res = requests.post('http://127.0.0.1:8001/api/v1/auth/login/', json={'identifier': 'rudraarupa22@gmail.com', 'password': 'password', 'identifier_type': 'email'})
print('Login:', res.status_code, res.text[:200])

if res.status_code == 200:
    token = res.json()['access']
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    # 2. Get hostels
    res = requests.get('http://127.0.0.1:8001/api/v1/hostels/', headers=headers)
    print('GET hostels:', res.status_code)
    hostels = res.json()
    if hostels:
        h = hostels[0]
        # 3. PUT hostel
        url = f"http://127.0.0.1:8001/api/v1/hostels/{h['hostel_id']}/"
        res = requests.put(url, headers=headers, json=h)
        print('PUT hostel:', res.status_code, res.text[:200])
