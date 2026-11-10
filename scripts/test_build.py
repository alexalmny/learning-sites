import json
from pathlib import Path
import tempfile
import unittest

from build import build, load_courses, render_portal


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.courses = [
            dict(path='second', category='Algo', index=20, title='Second', description='Suite'),
            dict(path='first', category='Algo', index=10, title='<Premier>', description='A & B'),
            dict(path='other', category='Texte', index=10, title='Autre', description='Texte'),
        ]
        for course in self.courses:
            directory = self.root / course['path']
            directory.mkdir()
            (directory / 'index.html').write_text('<h1>Course</h1>')

    def load(self):
        (self.root / 'courses.json').write_text(json.dumps(self.courses))
        return load_courses(self.root)

    def test_group_sort_escape(self):
        courses = self.load()
        self.assertEqual([c['path'] for c in courses], ['first', 'second', 'other'])
        html = render_portal(courses)
        self.assertEqual(html.count('<section '), 2)
        self.assertLess(html.index('first/'), html.index('second/'))
        self.assertIn('&lt;Premier&gt;', html)
        self.assertIn('<h1>Learning Sites</h1>', html)
        self.assertNotIn('Étape', html)
        self.assertNotIn('<p>', html)
        self.assertNotIn('<footer>', html)
        self.assertNotIn('A &amp; B', html)
        self.courses[0]['category'] = 'Algo & structures'
        self.assertIn('Algo &amp; structures', render_portal(self.load()))

    def test_invalid_catalog(self):
        for field, value in [('path', '../private'), ('index', True), ('index', 0),
                             ('category', ''), ('index', 20), ('path', 'second')]:
            with self.subTest(field=field, value=value):
                old = self.courses[1][field]
                self.courses[1][field] = value
                with self.assertRaises(ValueError):
                    self.load()
                self.courses[1][field] = old

    def test_missing_or_unregistered_page(self):
        page = self.root / 'first/index.html'
        page.unlink()
        with self.assertRaises(ValueError):
            self.load()
        page.write_text('Course')
        self.courses.pop()
        with self.assertRaises(ValueError):
            self.load()

    def test_no_symlink_assets(self):
        (self.root / 'first/leak').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):
            self.load()

    def test_public_build_and_no_overwrite(self):
        output = self.root / 'public'
        build(output)
        self.assertTrue((output / 'index.html').is_file())
        self.assertTrue((output / 'styles.css').is_file())
        self.assertTrue((output / 'robots.txt').is_file())
        self.assertFalse((output / '.git').exists())
        self.assertFalse((output / 'courses.json').exists())
        self.assertFalse((output / 'scripts').exists())
        for course in load_courses():
            self.assertTrue((output / course['path'] / 'index.html').is_file())
        with self.assertRaises(FileExistsError):
            build(output)


if __name__ == '__main__':
    unittest.main()
