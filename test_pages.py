#!/usr/bin/env python3
import urllib.request, urllib.parse, re, http.cookiejar

cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
BASE = 'http://localhost:5001'

# Login
with opener.open(f'{BASE}/auth/login') as r:
    html = r.read().decode()
match = re.search(r'name="csrf_token" value="([^"]+)"', html)
csrf = match.group(1)
data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin', 'csrf_token': csrf}).encode()
with opener.open(f'{BASE}/auth/login', data) as r:
    pass
print("Login OK\n")

routes = [
    '/buchhaltung/kontenplan',
    '/buchhaltung/konto/neu',
    '/buchhaltung/journal',
    '/buchhaltung/journal?jahr=2026',
]

for route in routes:
    try:
        with opener.open(f'{BASE}{route}') as r:
            body = r.read().decode()
            print(f"  OK  {route} -> {r.status} ({len(body)} bytes)")
            # Check for key content
            if 'kontenplan' in route:
                has_konten = 'Kontonummer' in body or '0100' in body or 'Grundstücke' in body
                print(f"       Konten sichtbar: {has_konten}")
            if 'journal' in route:
                has_filter = 'name="jahr"' in body or 'name="konto"' in body
                print(f"       Filter-Formular: {has_filter}")
    except urllib.error.HTTPError as e:
        print(f"  FAIL {route} -> {e.code}")
        print(f"       {e.read().decode()[:300]}")
    except Exception as e:
        print(f"  ERR  {route} -> {e}")
