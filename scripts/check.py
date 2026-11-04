from html.parser import HTMLParser
from pathlib import Path
import subprocess
import tempfile

from build import load_courses, render_portal

ROOT = Path(__file__).resolve().parent.parent
assert (ROOT / 'styles.css').is_file(), 'Shared stylesheet missing'
COURSES = load_courses()
PAGES = ['index.html', *(f"{course['path']}/index.html" for course in COURSES)]
assert (ROOT / 'index.html').read_text(encoding='utf-8') == render_portal(COURSES), 'Regenerate the portal: python3 scripts/build.py --update-portal'

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []
        self.scripts = []
        self.links = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])
        if tag == 'script':
            self.active = 'src' not in attrs and attrs.get('type', '') in ('', 'text/javascript', 'application/javascript', 'module')
            self.parts = []
    def handle_data(self, data):
        if self.active:
            self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.scripts.append(''.join(self.parts))
            self.active = False

with tempfile.TemporaryDirectory() as temp:
    for page in PAGES:
        path = ROOT / page
        assert path.is_file(), f'Page missing: {page}'
        parsed = Page()
        parsed.feed(path.read_text(encoding='utf-8'))
        if page == 'index.html':
            for target in parsed.links:
                if target.endswith('/'):
                    assert (ROOT / target / 'index.html').is_file(), f'Broken portal link: {target}'
        else:
            assert parsed.scripts, f'No inline JavaScript in {page}'
            assert 'href="../styles.css"' in path.read_text(encoding='utf-8'), f'Shared stylesheet missing in {page}'
        for i, script in enumerate(parsed.scripts):
            js = Path(temp) / f'{path.parent.name}-{i}.mjs'
            js.write_text(script, encoding='utf-8')
            subprocess.run(['node', '--check', str(js)], check=True)
        print(f'OK {page}: {len(parsed.scripts)} scripts')
