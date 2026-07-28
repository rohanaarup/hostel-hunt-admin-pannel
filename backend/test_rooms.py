import urllib.request, urllib.error
try:
    req = urllib.request.Request('http://127.0.0.1:8001/api/v1/hostels/70690875-eaae-43e7-ad54-3c1be67b1587/rooms/')
    resp = urllib.request.urlopen(req)
    print("STATUS:", resp.getcode())
    print("BODY:", resp.read().decode('utf-8')[:1000])
except urllib.error.HTTPError as e:
    print("STATUS:", e.code)
    print("ERROR BODY:", e.read().decode('utf-8'))
