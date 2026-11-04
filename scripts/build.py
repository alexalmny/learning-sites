"""Generate the static portal and a public-only deployment directory."""
import argparse
from html import escape
from itertools import groupby
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent.parent


def load_courses(root=ROOT):
    courses = json.loads((root / 'courses.json').read_text(encoding='utf-8'))
    if not isinstance(courses, list) or not courses:
        raise ValueError('courses.json must be a non-empty list')
    paths, positions = set(), set()
    for course in courses:
        if not isinstance(course, dict):
            raise ValueError('Each course must be an object')
        for field in ('path', 'category', 'title', 'description'):
            if not isinstance(course.get(field), str) or not course[field].strip():
                raise ValueError(f'Missing or empty course field: {field}')
        path = course['path']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', path):
            raise ValueError(f'Invalid course path: {path}')
        if type(course.get('index')) is not int or course['index'] <= 0:
            raise ValueError(f'Index must be a positive integer: {path}')
        position = (course['category'], course['index'])
        if path in paths or position in positions:
            raise ValueError(f'Duplicate path or index within a category: {path}')
        directory = root / path
        if directory.is_symlink() or any(p.is_symlink() for p in directory.rglob('*')):
            raise ValueError(f'Symlinks are not public assets: {path}')
        if not (directory / 'index.html').is_file():
            raise ValueError(f'Missing course page: {path}')
        paths.add(path)
        positions.add(position)
    discovered = {p.parent.name for p in root.glob('*/index.html') if p.parent.name != 'dist'}
    if discovered != paths:
        raise ValueError(f'Course directories and catalog differ: {discovered ^ paths}')
    return sorted(courses, key=lambda c: (c['category'].casefold(), c['index']))


def render_portal(courses):
    sections = []
    for number, (category, items) in enumerate(groupby(courses, key=lambda c: c['category'])):
        cards = []
        for course in items:
            cards.append(f'''<li><a class="card" href="{course['path']}/">
<span class="n">Étape {course['index']:02d}</span>
<h3>{escape(course['title'])}</h3><p>{escape(course['description'])}</p>
</a></li>''')
        sections.append(f'''<section aria-labelledby="category-{number}">
<h2 id="category-{number}">{escape(category)}</h2>
<ol class="grid">{''.join(cards)}</ol></section>''')
    return f'''<!doctype html>
<!-- Generated from courses.json by scripts/build.py; do not edit manually. -->
<html lang="fr" data-course="portal">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Des cours interactifs classés par matière et par ordre d’apprentissage.">
<title>Apprendre en explorant</title><link rel="stylesheet" href="styles.css"></head>
<body><main><header><span class="label">Cours interactifs</span>
<h1>Apprendre en explorant.</h1>
<p>Choisis une matière, puis suis les étapes dans l’ordre pour manipuler les concepts et tester ta compréhension.</p>
</header>{''.join(sections)}
<footer>Des exercices interactifs pour apprendre à son rythme.</footer></main></body></html>
'''


def build(output):
    courses = load_courses()
    # Refuse an existing destination rather than risk deleting source or a live release.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'index.html').write_text(render_portal(courses), encoding='utf-8')
    shutil.copy2(ROOT / 'styles.css', output)
    (output / 'robots.txt').write_text('User-agent: *\nDisallow: /\n', encoding='utf-8')
    for course in courses:
        shutil.copytree(ROOT / course['path'], output / course['path'],
                        ignore=shutil.ignore_patterns('.*'))
    print(f'Built {len(courses)} courses in {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--update-portal', action='store_true',
                        help='Regenerate the tracked index.html instead of building a release')
    args = parser.parse_args()
    if args.update_portal:
        (ROOT / 'index.html').write_text(render_portal(load_courses()), encoding='utf-8')
    else:
        build(args.output)
