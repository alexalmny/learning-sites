"""Smoke test the deployed HTTPS portal and every catalogued course."""
from urllib.error import HTTPError
from urllib.request import urlopen

from build import load_courses, render_portal

BASE = 'https://learning.141-145-214-196.nip.io'
courses = load_courses()
for path in ['/', '/styles.css', '/robots.txt', *(f"/{c['path']}/" for c in courses)]:
    with urlopen(BASE + path, timeout=20) as response:
        assert response.status == 200, path
        assert 'noindex' in response.headers['X-Robots-Tag'], path
        assert 'nosniff' == response.headers['X-Content-Type-Options'], path
        if path == '/':
            assert response.read().decode('utf-8') == render_portal(courses), 'Deployed portal is stale'
        print(f'OK {BASE}{path}')
with urlopen(BASE.replace('https:', 'http:') + '/', timeout=20) as response:
    assert response.url == BASE + '/', 'Missing HTTPS redirect'
for path in ['/courses.json', '/scripts/build.py', '/.git/config', '/unknown-course/']:
    try:
        urlopen(BASE + path, timeout=20).close()
    except HTTPError as error:
        assert error.code in (403, 404), (path, error.code)
    else:
        raise AssertionError(f'Unexpected public path: {path}')
print('HTTPS, catalog, static files and private paths: OK')
