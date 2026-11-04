#!/bin/sh
# Publish a validated static release; Nginx/TLS provisioning is documented in README.md.
set -eu
cd "$(dirname "$0")/.."
python3 scripts/check.py
python3 -m unittest discover -s scripts -p 'test_*.py'
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT HUP INT TERM
python3 scripts/build.py --output "$staging/public"
release="/var/www/learning-sites/releases/$(date -u +%Y%m%dT%H%M%S)-$(git rev-parse --short HEAD)"
sudo install -d -m 755 /var/www/learning-sites/releases
# A collision must fail, never overwrite an existing release.
sudo mkdir -m 755 "$release"
sudo cp -R "$staging/public/." "$release/"
sudo chown -R root:root "$release"
sudo chmod -R u=rwX,go=rX "$release"
sudo ln -s "$release" /var/www/learning-sites/current.next
sudo mv -Tf /var/www/learning-sites/current.next /var/www/learning-sites/current
printf 'Published %s\n' "$release"
