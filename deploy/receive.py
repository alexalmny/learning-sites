#!/usr/bin/python3
"""Root-installed forced SSH command for transactional static-site releases."""
import argparse
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile
import tempfile
import time
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path('/var/www/learning-sites')
BASE = None
RELEASE_ID = re.compile(r'[0-9a-f]{40}-[0-9]+-[0-9]+')
CONFIRM_SECONDS = 300


def extract(stream, destination, required=('index.html', 'styles.css', 'robots.txt'), max_bytes=50 * 1024 * 1024):
    count = total = 0
    seen = set()

    def public_file(member, path):
        nonlocal count, total
        count += 1
        total += member.size
        if member.size < 0 or count > 10000 or total > max_bytes:
            raise ValueError('Release exceeds entry or size limit')
        parts = PurePosixPath(member.name).parts
        if member.name.startswith('/') or any(p.startswith('.') for p in parts):
            raise ValueError('Absolute, hidden and parent paths are forbidden')
        if not (member.isdir() or member.isfile()):
            raise ValueError('Only regular files and directories are allowed')
        if member.isfile():
            if parts in seen:
                raise ValueError('Duplicate public file')
            seen.add(parts)
        safe = tarfile.data_filter(member, path)
        return safe.replace(mode=0o755 if member.isdir() else 0o644)

    with tarfile.open(fileobj=stream, mode='r|gz') as archive:
        archive.extractall(destination, filter=public_file)
    for name in required:
        if not (destination / name).is_file():
            raise ValueError(f'Missing public file: {name}')


def check_https(release):
    if not BASE:
        raise ValueError('A public base origin is required in the protected site configuration')
    for page in sorted(release.rglob('*')):
        if not page.is_file():
            continue
        path = page.relative_to(release).as_posix()
        if path.endswith('index.html'):
            path = path[:-len('index.html')]
        with urlopen(f'{BASE}/{quote(path)}?release={release.name}', timeout=15) as response:
            if response.status != 200 or response.read() != page.read_bytes():
                raise RuntimeError(f'HTTPS content mismatch: {path}')


def activate(root, target):
    pending = root / 'current.next'
    pending.unlink(missing_ok=True)
    pending.symlink_to(target)
    pending.replace(root / 'current')


def read_pending(root):
    path = root / '.pending.json'
    return json.loads(path.read_text()) if path.exists() else None


def rollback(root, state):
    # Compare-and-swap: an old CI run must never undo a newer release.
    if (root / 'current').is_symlink() and os.readlink(root / 'current') == state['release']:
        if state['previous'] is None:
            (root / 'current').unlink()
        else:
            activate(root, state['previous'])
    (root / '.pending.json').unlink(missing_ok=True)
    print(f"Rolled back {state['id']}", flush=True)


def expire(root, now=None):
    state = read_pending(root)
    if state and (time.time() if now is None else now) >= state['deadline']:
        rollback(root, state)
        return True
    return False


def prune(root, previous):
    history = sorted((p for p in (root / 'releases').iterdir() if RELEASE_ID.fullmatch(p.name)),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    current = (root / 'current').resolve()
    for old in history[5:]:
        if str(old) != previous and old != current:
            shutil.rmtree(old)


def finish(release_id, action, root=ROOT):
    with (root / '.deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        expired = expire(root)
        state = read_pending(root)
        if not state or state['id'] != release_id:
            if action == 'rollback':
                return
            raise ValueError('Release is not awaiting confirmation (possibly expired)')
        if action == 'rollback':
            rollback(root, state)
        elif action == 'confirm' and not expired:
            if not (root / 'current').is_symlink() or os.readlink(root / 'current') != state['release']:
                raise ValueError('Current release changed before confirmation')
            prune(root, state['previous'])
            (root / '.pending.json').unlink()
            print(f'Confirmed {release_id}', flush=True)
        else:
            raise ValueError('Invalid release action')


def publish(stream, release_id, root=ROOT, health_check=check_https,
            required=('index.html', 'styles.css', 'robots.txt'), max_bytes=50 * 1024 * 1024):
    if not RELEASE_ID.fullmatch(release_id):
        raise ValueError('Invalid release ID')
    releases = root / 'releases'
    with (root / '.deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        expire(root)
        if read_pending(root):
            raise ValueError('Another release is awaiting confirmation')
        release = releases / release_id
        if release.exists():
            raise FileExistsError(release)
        with tempfile.TemporaryDirectory(prefix='.incoming-', dir=releases) as staging:
            staging = Path(staging)
            extract(stream, staging, required, max_bytes)
            staging.chmod(0o755)
            staging.rename(release)
        previous = os.readlink(root / 'current') if (root / 'current').is_symlink() else None
        if (root / 'current').exists() and previous is None:
            raise ValueError('Bootstrap current as a release symlink before deploying')
        state = dict(id=release_id, release=str(release), previous=previous,
                     deadline=time.time() + CONFIRM_SECONDS)
        pending = root / '.pending.next'
        pending.write_text(json.dumps(state))
        pending.replace(root / '.pending.json')
        try:
            activate(root, release)
            health_check(release)
        except BaseException:
            rollback(root, state)
            raise
        print(f'Published {release_id}; awaiting confirmation within {CONFIRM_SECONDS}s', flush=True)


def main():
    global BASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True,
                        help='Root-owned per-site configuration, fixed by authorized_keys')
    parser.add_argument('--expire', action='store_true', help='Used by the server watchdog only')
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    root = Path(config['root'])
    BASE = config['base']
    os.umask(0o022)
    if args.expire:
        with (root / '.deploy.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            expire(root)
        return
    command = os.environ.get('SSH_ORIGINAL_COMMAND', '').split()
    if len(command) != 2 or command[0] not in ('deploy', 'confirm', 'rollback') or not RELEASE_ID.fullmatch(command[1]):
        sys.exit('Only deploy, confirm or rollback <commit>-<run>-<attempt> is permitted')
    if command[0] == 'deploy':
        publish(sys.stdin.buffer, command[1], root, required=config['required'],
                max_bytes=config.get('max_bytes', 50 * 1024 * 1024))
    else:
        finish(command[1], command[0], root)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        sys.exit(f'Deployment failed: {error}')
