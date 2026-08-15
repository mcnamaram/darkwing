# Secrets Handling

> Last updated: 2026-08-15. Now that DarkWing drives a real browser (Playwright), the secret surface is much smaller than the old gcloud/Apps Script era.

## What is sensitive

- **The Google Form URL / Form ID.** The long string in the form's URL (e.g. `1FAIpQLSd…O4delw`) identifies a live form. It's not a credential per se — volunteers are given the form link — but treat it as internal.
- **`DARKWING_SUBMITTER_NAME`.** The name that appears in every submitted response. Personal data of the observer.
- **The browser profile directory (`google_profile/`).** Contains the user's **real Google session cookies** (`__Secure-1PSID`, `__Secure-OSID`, `NID`, …) after they log in once. This is live-session data: whoever holds it can act as the Google account in a browser. **Never commit it.**
- **`.env`** — holds `DARKWING_FORM_URL`, `DARKWING_SUBMITTER_NAME`. Gitignored.

## What is NOT sensitive anymore

| Gone | Why |
| --- | --- |
| `gcloud auth print-access-token` | No API calls; the browser handles auth |
| Custom OAuth client & refresh tokens | No `script.scriptapp` scope needed |
| Apps Script `/exec` URL | No webhook |
| Google session cookies in curl captures | Browser profile replaces them |

## How the project keeps secrets out

1. **`.gitignore` blocks:**
   - `.env`, `.env.*`
   - `google_profile/` — the browser session
   - `camera.cfg`, `*.cfg` — reserved for MVP2 camera credentials
   - `.venv/`, `__pycache__/`, `site/`, etc.

2. **No secret is ever read from a file that could be committed.** `DARKWING_*` values come from environment variables loaded via `python-dotenv` from `.env` (gitignored).

3. **The submission log never contains secrets.** `submitted_log.jsonl` records only the record, status, error, and timestamp — no form URL, no profile path, no cookie data.

## What to do if a secret is committed

1. **Rotate it immediately.** For a Google session: use the Google account's security page to revoke sessions / sign out everywhere. For a form URL: the form ID can't be rotated, but you can close the form and recreate it.
2. **Remove the secret from history.** Use `git filter-repo` (recommended) or `git filter-branch`, then force-push and notify anyone who has cloned.
3. **Audit access.** Check the Google account's security log for unfamiliar activity.
4. **Add a regression test.** A test that fails when a secret pattern is detected in tracked files is a cheap safeguard.

## Operational note

The `google_profile/` directory is created **at runtime** in the project root by `launch_persistent_context`. If you delete it, the user simply logs into Google again on the next `submit` run. If your machine is shared, delete it after each session (`rm -rf google_profile/`).
