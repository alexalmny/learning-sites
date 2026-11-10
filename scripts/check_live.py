"""Smoke test the deployed HTTPS portal and every catalogued course."""
import os
from urllib.error import HTTPError
from urllib.request import urlopen

from build import ROOT, load_courses, render_portal

BASE = os.environ['ORIGIN'].rstrip('/')
if not BASE.startswith('https://'):
    raise ValueError('ORIGIN must be an HTTPS origin')
courses = load_courses()
for path in ['/', '/styles.css', '/robots.txt', *(f"/{c['path']}/" for c in courses)]:
    with urlopen(BASE + path, timeout=20) as response:
        assert response.status == 200, path
        assert 'noindex' in response.headers['X-Robots-Tag'], path
        assert 'nosniff' == response.headers['X-Content-Type-Options'], path
        body = response.read()
        if path == '/':
            expected = render_portal(courses).encode('utf-8')
        elif path == '/robots.txt':
            expected = b'User-agent: *\nDisallow: /\n'
        else:
            local = ROOT / path.strip('/')
            expected = (local / 'index.html' if path.endswith('/') else local).read_bytes()
        assert body == expected, f'Deployed content is stale: {path}'
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
