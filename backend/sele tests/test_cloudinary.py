import urllib.request, urllib.error
import json

cloud_name = 'rdarhdth'
upload_preset = 'admin_pannel_img2'
url = f'https://api.cloudinary.com/v1_1/{cloud_name}/image/upload'

# A tiny 1x1 transparent PNG as base64
dummy_png = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
    b'\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
    b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)

boundary = '----Boundary'
data = []
data.append(f'--{boundary}')
data.append('Content-Disposition: form-data; name="upload_preset"')
data.append('')
data.append(upload_preset)
data.append(f'--{boundary}')
data.append('Content-Disposition: form-data; name="file"; filename="test.png"')
data.append('Content-Type: image/png')
data.append('')
data.append(dummy_png)
data.append(f'--{boundary}--')
data.append('')

body = b''
for item in data:
    if isinstance(item, str):
        body += item.encode('utf-8') + b'\r\n'
    else:
        body += item + b'\r\n'

headers = {
    'Content-Type': f'multipart/form-data; boundary={boundary}',
    'Content-Length': str(len(body))
}

req = urllib.request.Request(url, data=body, headers=headers, method='POST')

try:
    resp = urllib.request.urlopen(req)
    print("STATUS:", resp.getcode())
    print("RESPONSE:", resp.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("STATUS:", e.code)
    print("ERROR RESPONSE:", e.read().decode('utf-8'))
except Exception as e:
    print("UNEXPECTED ERROR:", e)
