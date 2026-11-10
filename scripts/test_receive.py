import importlib.util
import io
import json
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

    def test_https_check_requires_explicit_configuration(self):
        from unittest.mock import patch
        with patch.object(receive, 'BASE', None), patch.object(receive, 'urlopen') as request:
            with self.assertRaisesRegex(ValueError, 'public base origin'):
                receive.check_https(self.root)
            request.assert_not_called()

    def test_publish_and_permissions(self):
        receive.publish(archive(), RELEASE, self.root, lambda release: None)
        self.assertEqual((self.root / 'current').resolve(), self.root / 'releases' / RELEASE)
        self.assertEqual((self.root / 'current/index.html').read_bytes(), b'new')
        self.assertEqual((self.root / 'current/index.html').stat().st_mode & 0o777, 0o644)
        receive.finish(RELEASE, 'confirm', self.root)
        self.assertFalse((self.root / '.pending.json').exists())
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
            release_id = 'a' * 40 + f'-{number}-1'
            receive.publish(archive(), release_id, self.root, lambda release: None)
            receive.finish(release_id, 'confirm', self.root)
        history = [p for p in (self.root / 'releases').iterdir() if receive.RELEASE_ID.fullmatch(p.name)]
        self.assertEqual(len(history), 5)
        self.assertTrue(self.previous.is_dir())
        self.assertTrue((self.root / 'current/index.html').is_file())

    def test_no_shell_or_arbitrary_command(self):
        config = self.root / 'config.json'
        config.write_text(json.dumps(dict(root=str(self.root), base=receive.BASE, required=['index.html'])))
        for command in ('', 'id', 'deploy ../escape', 'deploy ' + RELEASE + '; id'):
            result = subprocess.run([sys.executable, str(SPEC.origin), '--config', str(config)],
                                    env={'SSH_ORIGINAL_COMMAND': command}, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Only deploy', result.stderr)

    def test_external_failure_rolls_back(self):
        receive.publish(archive(), RELEASE, self.root, lambda release: None)
        receive.finish(RELEASE, 'rollback', self.root)
        self.assertEqual((self.root / 'current').resolve(), self.previous)
        receive.finish(RELEASE, 'rollback', self.root)  # Safe after local rollback too.

    def test_runner_loss_expires_and_cannot_be_confirmed(self):
        receive.publish(archive(), RELEASE, self.root, lambda release: None)
        state = receive.read_pending(self.root)
        self.assertFalse(receive.expire(self.root, state['deadline'] - 1))
        self.assertTrue(receive.expire(self.root, state['deadline']))
        self.assertEqual((self.root / 'current').resolve(), self.previous)
        with self.assertRaises(ValueError):
            receive.finish(RELEASE, 'confirm', self.root)

    def test_stale_run_cannot_undo_new_release(self):
        receive.publish(archive(), RELEASE, self.root, lambda release: None)
        receive.finish(RELEASE, 'confirm', self.root)
        newer = 'b' * 40 + '-124-1'
        receive.publish(archive(), newer, self.root, lambda release: None)
        receive.finish(RELEASE, 'rollback', self.root)
        self.assertEqual((self.root / 'current').resolve().name, newer)
        with self.assertRaises(ValueError):
            receive.finish(RELEASE, 'confirm', self.root)
        receive.finish(newer, 'rollback', self.root)
        self.assertEqual((self.root / 'current').resolve().name, RELEASE)

    def test_pending_release_blocks_another_deployment(self):
        receive.publish(archive(), RELEASE, self.root, lambda release: None)
        with self.assertRaises(ValueError):
            receive.publish(archive(), 'b' * 40 + '-124-1', self.root, lambda release: None)

    def test_first_release_failure_leaves_no_current(self):
        (self.root / 'current').unlink()
        def fail(release):
            raise RuntimeError('HTTPS failed')
        with self.assertRaises(RuntimeError):
            receive.publish(archive(), RELEASE, self.root, fail)
        self.assertFalse((self.root / 'current').exists())
        self.assertFalse((self.root / '.pending.json').exists())

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
