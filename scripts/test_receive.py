import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('receive', Path(__file__).resolve().parent.parent / 'deploy/receive.py')
receive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(receive)
RELEASE = 'a' * 40 + '-123-1'


def archive(extra=None):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as tar:
        for name in ('index.html', 'styles.css', 'robots.txt'):
            member = tarfile.TarInfo('./' + name)
            member.size = 3
            member.mode = 0o777
            tar.addfile(member, io.BytesIO(b'new'))
        if extra is not None:
            tar.addfile(extra, io.BytesIO(b''))
    output.seek(0)
    return output


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'releases').mkdir()
        self.previous = self.root / 'releases/old'
        self.previous.mkdir()
        (self.root / 'current').symlink_to(self.previous)

    def test_publish_and_permissions(self):
        receive.publish(archive(), RELEASE, self.root, lambda release: None)
        self.assertEqual((self.root / 'current').resolve(), self.root / 'releases' / RELEASE)
        self.assertEqual((self.root / 'current/index.html').read_bytes(), b'new')
        self.assertEqual((self.root / 'current/index.html').stat().st_mode & 0o777, 0o644)
        with self.assertRaises(FileExistsError):
            receive.publish(archive(), RELEASE, self.root, lambda release: None)

    def test_rollback(self):
        def fail(release):
            raise RuntimeError('HTTPS failed')
        with self.assertRaises(RuntimeError):
            receive.publish(archive(), RELEASE, self.root, fail)
        self.assertEqual((self.root / 'current').resolve(), self.previous)

    def test_reject_paths_links_and_special_files(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('/tmp/escape', tarfile.REGTYPE),
                           ('.ssh/authorized_keys', tarfile.REGTYPE), ('course/link', tarfile.SYMTYPE),
                           ('course/hardlink', tarfile.LNKTYPE), ('pipe', tarfile.FIFOTYPE)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = '/etc/passwd'
                with self.assertRaises((ValueError, tarfile.FilterError)):
                    receive.extract(archive(member), Path(directory))
        self.assertEqual((self.root / 'current').resolve(), self.previous)

    def test_bad_or_incomplete_upload_preserves_current(self):
        with self.assertRaises(tarfile.TarError):
            receive.publish(io.BytesIO(b'not a tarball'), RELEASE, self.root)
        empty = io.BytesIO()
        with tarfile.open(fileobj=empty, mode='w:gz'):
            pass
        empty.seek(0)
        with self.assertRaises(ValueError):
            receive.publish(empty, RELEASE, self.root)
        self.assertEqual((self.root / 'current').resolve(), self.previous)
        self.assertEqual(list((self.root / 'releases').glob('.incoming-*')), [])

    def test_invalid_release_id(self):
        with self.assertRaises(ValueError):
            receive.publish(archive(), '../escape', self.root)

    def test_retention(self):
        for number in range(7):
            receive.publish(archive(), 'a' * 40 + f'-{number}-1', self.root, lambda release: None)
        history = [p for p in (self.root / 'releases').iterdir() if receive.RELEASE_ID.fullmatch(p.name)]
        self.assertEqual(len(history), 5)
        self.assertTrue(self.previous.is_dir())
        self.assertTrue((self.root / 'current/index.html').is_file())

    def test_no_shell_or_arbitrary_command(self):
        for command in ('', 'id', 'deploy ../escape', 'deploy ' + RELEASE + '; id'):
            result = subprocess.run([sys.executable, str(SPEC.origin)],
                                    env={'SSH_ORIGINAL_COMMAND': command}, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Only deploy', result.stderr)

    def test_size_limit(self):
        member = tarfile.TarInfo('huge')
        member.size = 51 * 1024 * 1024
        # A header is enough: the filter must reject it before reading its body.
        data = io.BytesIO()
        import gzip
        with gzip.GzipFile(fileobj=data, mode='wb') as compressed:
            compressed.write(member.tobuf())
        data.seek(0)
        with self.assertRaises(ValueError), tempfile.TemporaryDirectory() as directory:
            receive.extract(data, Path(directory))


if __name__ == '__main__':
    unittest.main()
