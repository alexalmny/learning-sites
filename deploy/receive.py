#!/usr/bin/python3
"""Root-installed SSH forced command: receive static files, never execute repository code."""
import fcntl
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile
import tempfile
from urllib.request import urlopen

ROOT = Path('/var/www/learning-sites')
BASE = 'https://learning.141-145-214-196.nip.io'
RELEASE_ID = re.compile(r'[0-9a-f]{40}-[0-9]+-[0-9]+')


def extract(stream, destination):
    count = total = 0

    def public_file(member, path):
        nonlocal count, total
        count += 1
        total += member.size
        if member.size < 0 or count > 10000 or total > 50 * 1024 * 1024:
            raise ValueError('Release exceeds 10000 entries or 50 MiB')
        parts = PurePosixPath(member.name).parts
        if member.name.startswith('/') or any(p.startswith('.') for p in parts):
            raise ValueError('Absolute, hidden and parent paths are forbidden')
        if not (member.isdir() or member.isfile()):
            raise ValueError('Only regular files and directories are allowed')
        # Use the standard safe extraction filter, then discard archive permissions.
        safe = tarfile.data_filter(member, path)
        return safe.replace(mode=0o755 if member.isdir() else 0o644)

    with tarfile.open(fileobj=stream, mode='r|gz') as archive:
        archive.extractall(destination, filter=public_file)
    for name in ('index.html', 'styles.css', 'robots.txt'):
        if not (destination / name).is_file():
            raise ValueError(f'Missing public file: {name}')


def check_https(release):
    pages = [release / 'styles.css', release / 'robots.txt', *release.rglob('index.html')]
    for page in pages:
        path = page.relative_to(release).as_posix()
        if path.endswith('index.html'):
            path = path[:-len('index.html')]
        with urlopen(f'{BASE}/{path}', timeout=15) as response:
            if response.status != 200 or response.read() != page.read_bytes():
                raise RuntimeError(f'HTTPS content mismatch: {path}')


def activate(root, target):
    pending = root / 'current.next'
    pending.unlink(missing_ok=True)
    pending.symlink_to(target)
    pending.replace(root / 'current')


def publish(stream, release_id, root=ROOT, health_check=check_https):
    if not RELEASE_ID.fullmatch(release_id):
        raise ValueError('Invalid release ID')
    releases = root / 'releases'
    with (root / '.deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        release = releases / release_id
        if release.exists():
            raise FileExistsError(release)
        with tempfile.TemporaryDirectory(prefix='.incoming-', dir=releases) as staging:
            staging = Path(staging)
            extract(stream, staging)
            staging.chmod(0o755)
            staging.rename(release)
        previous = os.readlink(root / 'current') if (root / 'current').is_symlink() else None
        activate(root, release)
        try:
            health_check(release)
        except Exception:
            if previous is not None:
                activate(root, previous)
            else:
                (root / 'current').unlink()
            raise
        # Keep five CI releases; leave pre-existing administrator releases alone.
        history = sorted((p for p in releases.iterdir() if RELEASE_ID.fullmatch(p.name)),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        for old in history[5:]:
            if str(old) != previous and old != release:
                shutil.rmtree(old)
        print(f'Published {release_id}; HTTPS verified', flush=True)


if __name__ == '__main__':
    command = os.environ.get('SSH_ORIGINAL_COMMAND', '')
    if not command.startswith('deploy ') or not RELEASE_ID.fullmatch(command[7:]):
        sys.exit('Only deploy <commit>-<run>-<attempt> is permitted')
    os.umask(0o022)
    try:
        publish(sys.stdin.buffer, command[7:])
    except Exception as error:
        sys.exit(f'Deployment failed (previous version preserved): {error}')
