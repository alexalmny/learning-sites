# Shared static releases

This directory is the source of truth for the host's static release receiver and
watchdog. Runtime/backend deployment and database migrations are not covered.

## Application contract

1. Test and build on a GitHub-hosted runner. Upload `site.tar.gz` as artifact
   `static-site`, containing only public files (no hidden files or links).
2. On `main` only, call `alexalmny/learning-sites/.github/workflows/deploy-static.yml`
   pinned to a reviewed commit, after the build succeeds. Pass `origin`, `user`,
   optionally `verify-command` (which can read `$ORIGIN`), and the two production-environment secrets
   `STATIC_DEPLOY_KEY` / `STATIC_DEPLOY_KNOWN_HOSTS`.
3. The shared workflow publishes, checks every file over public HTTPS, runs any
   application-specific check, and confirms. Failure/cancellation requests rollback.
   The server independently expires unconfirmed releases after 300 seconds,
   checked every 30 seconds. Its lock serializes publish/confirm/rollback/expiry.

Keep each caller's actual HTTPS origin and deployment user in GitHub repository
variables (`STATIC_ORIGIN` / `STATIC_DEPLOY_USER`), not workflow source. Match
these values to the protected server-side JSON. Never put authentication values
in repository variables; use the environment secrets below.

Each website has its own deployment user and SSH key. A key can change that
website's public content, but cannot run a shell, use sudo or change other sites.
The key is not the old EgoDrive backend credential.

## Host provisioning (administrator only)

Install `receive.py` as root-owned executable
`/usr/local/libexec/static-release-receive`, and install `static-release@.service`
and `.timer` under `/etc/systemd/system/`.

Create `/etc/static-release/<user>.json` (root-owned, mode 0644), for example:

```json
{
  "root": "/var/www/dropcheck",
  "base": "https://dropcheck.example.com",
  "required": ["index.html"],
  "max_bytes": 52428800
}
```

The deployment user owns only its site's release root and `releases/` directory.
SSH home, `.ssh/` and `authorized_keys` remain root-owned. The authorized key is:

```text
restrict,command="/usr/local/libexec/static-release-receive --config /etc/static-release/<user>.json" ssh-ed25519 <public key>
```

Bootstrap existing content into a preserved administrator release and point
`current` to it. Nginx must serve `<root>/current`, never the development repo.
Use atomic symlink replacement; preserve the old content until verified. For
existing roots that already use a release symlink, retain that release unchanged.

Enable `static-release@<user>.timer` after `systemctl daemon-reload`.
Configure the GitHub `production` environment to allow `main` deployments only.
Generate a dedicated Ed25519 key, install its public key as above, upload its
private key to `STATIC_DEPLOY_KEY` via stdin and securely remove the temporary
local key. Set `STATIC_DEPLOY_KNOWN_HOSTS` from the host's actual public host key.
Never put private keys into Git, logs or workflow arguments.

## Failure and recovery

- Invalid/incomplete uploads never activate.
- A failed server or GitHub content/application check restores the prior symlink.
- A lost runner/connection or cancelled job expires unless already confirmed.
- Confirmation after expiry is refused. A stale run cannot roll back a newer run.
- Five CI releases are retained; the immediate predecessor and administrator
  releases are protected. Retention happens only on confirmation.
- Watchdogs are persistent systemd timers, including after reboot. Check with
  `systemctl list-timers 'static-release@*'` and inspect the instance's journal.
- For manual rollback, ensure no pending deployment or concurrent CI run, then
  atomically point `current` at a retained release. There is no database to restore.

Test with `python3 -m unittest discover -s scripts -p 'test_*.py'` from the repo
root. Failure tests cover bad archives, local/external failures, missing runner
confirmation, stale commands, first-release failure and retention.

This is release verification, not a browser/functional test or an off-host backup.
Changes to this receiver/watchdog require an administrator review and installation;
application CI cannot replace its own deployment receiver.
