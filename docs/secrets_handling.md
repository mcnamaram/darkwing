# Secrets Handling

This project is hosted in a public Git repository. Anything that lands on the `main` branch is, by default, public. This document enumerates what must never be committed and what the operational safeguards are.

## What is sensitive

- **The Google Apps Script `/exec` URL.** Identifies the user's Apps Script deployment. Compromising it lets an attacker submit forms as the user.
- **The Google Form ID** (the long string in the form's URL, e.g. `1FAIpQLSd…O4delw`). Identifies the form. Compromising it lets an attacker target the form.
- **The `gcloud` OAuth access token** (the value of `gcloud auth print-access-token`). Authorizes any API the token's user can call. Compromising it lets an attacker act as the user for the token's lifetime (≤ 60 minutes).
- **Google session cookies** (`__Secure-1PSID`, `__Secure-OSID`, `NID`, `SID`, etc.) — the kind captured by browser DevTools or by `curl -b`. Compromising them lets an attacker impersonate the user's Google account in a browser, until the cookies are rotated.
- **Camera credentials** (IP, username, password) for the Reolink cameras. The MVP2+ video-download epic will introduce these. They are *not* yet in the repo; when they are, they go in a `camera.cfg` (per the upstream `reolinkapipy` example) that is gitignored.

## How the project keeps secrets out

1. **`.gitignore` patterns** explicitly block:
   - `.env`, `.env.*` — the user's environment file with `DARKWING_APPS_SCRIPT_URL`, `DARKWING_FORM_ID`, `DARKWING_SUBMITTER_EMAIL`, etc.
   - `camera.cfg`, `*.cfg` — the camera credential file (added in MVP2; the pattern is in place now to prevent future mistakes).
   - `googleforms` — a legacy filename for curl captures that have contained live session cookies in the past.
   - `PROGRESS_LOG.md` — kept out of the repo because it documents features that never existed; replaced by commit messages and the live docs.
   - `.hermes/`, `.vscode/`, `.venv/`, `__pycache__/`, `site/`, `*.local`, `*.swp` — local-only and build artifacts.

2. **No secret is ever read from a file that could be committed.** The `DARKWING_*` values come from environment variables loaded via `python-dotenv` from a `.env` file in the project root. The `.env` file is gitignored. The CI workflow does not have access to these variables; the docs site deploys without them.

3. **No captured auth headers are pasted into source files or commit messages.** A `curl -H 'Cookie: ...'` capture has no business in a `.py` file, a Markdown doc, a test fixture, or a commit message. The legitimate path is to retrieve the token at runtime via `gcloud auth print-access-token`.

4. **The submission log never contains tokens.** `submitted_log.jsonl` records `uuid`, `timestamp_utc`, `http_status`, `attempt_count`, and (for failed rows) the error message. It does not record the bearer token, the request body, or the Apps Script URL.

## What to do if a secret is committed

1. **Rotate the secret immediately.** For a Google account, sign out of all sessions and let cookies expire (or use Google's security page to revoke them). For a `gcloud` token, run `gcloud auth revoke` to invalidate it.
2. **Remove the secret from history.** If the secret landed in a commit, use `git filter-repo` (recommended) or `git filter-branch` to scrub it. This requires a force-push and a notification to anyone who has cloned the repo.
3. **Audit access.** If the secret was a Google session cookie, check the Google account's security log for unfamiliar activity. If it was a camera credential, check the camera's web UI for unfamiliar logins.
4. **Add a regression test.** A test that fails when the secret pattern is detected in tracked files is a cheap, durable safeguard. The pattern of `.gitignore` plus a CI check is the standard "shift left" answer.

## If a captured header file lands in your local working tree

Captures from `curl -v` or browser DevTools frequently contain live session cookies. They are dangerous even when they don't leave the local machine — disk snapshots, sync clients, and `git add .` habits can move them unexpectedly. If a capture file lands in the repo:

1. `git restore --staged <file>` to remove it from the index.
2. `rm <file>` to remove it from the working tree.
3. Verify with `git status` that the file is no longer present.
4. Rotate the session cookies (sign out of the Google session).
5. Verify the blob is not in any commit with `git log --all --oneline -- <file>` and `git rev-list --all --objects | grep <hash>`.
6. The blob may still exist in `.git/objects/` for up to 90 days as an unreachable object. If the local environment is shared or backed up offsite, consider a more thorough purge (`rm -rf .git && git init && git remote add origin … && git fetch origin && git reset --hard origin/main`). The decision depends on your threat model.

The default project policy is **"if it was never pushed, no purge needed, but the secret is still considered compromised"** — because the file existed on disk in a known location for an unknown duration.
