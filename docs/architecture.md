# System Architecture

> Last updated: 2026-08-15. Source of truth is `src/darkwing/`.

## Overview

DarkWing is a single-process Python package. It:

1. Reads a CSV of curated observations (one row per 20-minute window)
2. Validates each row against a Pydantic schema
3. Expands short codes into the form's long-form answer text
4. Opens the Google Form in a real Chromium browser (via Playwright)
5. Fills the form fields one record at a time and clicks **Clear form** between records

No apps, no webhooks, no API keys. The browser does the work.

## Component map

| Component | File | Role |
| --- | --- | --- |
| Schema | `src/darkwing/schema.py` | Pydantic models + short-code translation tables |
| CSV I/O | `src/darkwing/csv_io.py` | Read CSV, write `submitted_log.jsonl` |
| Form Submit | `src/darkwing/form_submit.py` | Playwright browser automation |
| CLI | `src/darkwing/cli.py` | `darkwing validate/submit` entry point |

## Data flow

```sh
CSV file → read_csv() → [ObservationRecord] → submit_csv_records()
                                              ├─ dry-run? → skip browser
                                              └─ launch Chromium (persistent context, google_profile/)
                                                 → goto form URL
                                                 → for each record:
                                                     → expand short codes
                                                     → fill fields by role/name
                                                     → [submit button commented out]
                                                     → Clear form
```

## Browser session (form_submit.py)

- **Persistent browser context** (`launch_persistent_context`) with a profile dir at `google_profile/` in the project root — the user logs into Google once and the session persists.
- **Anti-bot flags**: custom Chrome user agent, `--disable-blink-features=AutomationControlled`, `--enable-automation` removed from default args, `slow_mo=500`.
- **Headless mode** controlled by `DARKWING_HEADLESS` env var (default `true`). Set `false` to watch the browser.
- `load_form()` returns `(playwright, context)`; `unload_form()` closes both. The playwright object is kept alive for the whole batch.

## The form fields

| Field | Playwright interaction |
| --- | --- |
| "Record" checkbox | `get_by_role("checkbox", name="Record")` |
| "Name (first, last)" | `get_by_role("textbox", name=...)` |
| Tower | `get_by_role("radio", name=f"Tower {tower}")` |
| Date | `press_sequentially` (types date) |
| "Hour of footage" | `get_by_role("textbox", name=...)` |
| Minutes past hour | radio `name=f"{minutes:02d}"` |
| Adult Swifts | radiogroup named "How many adult Swifts are" |
| Nesting Cycle | radiogroup expanded from `NESTING_STAGE_CODE_TO_TEXT` |
| Bill use | checkbox group, expanded from `BILL_USE_CODE_TO_TEXT` |
| Flights | checkbox group, expanded from `FLIGHTS_TRANSLATION` |
| Near nest | radiogroup "two body-lengths" |
| Awake | `get_by_role("radio", name=awake_text)` |
| Notes | `get_by_role("textbox", name="Note any interesting")` |

## Why Playwright instead of the Apps Script webhook?

The old architecture POSTed to a Google Apps Script `doPost` webhook that constructed `FormApp.createResponse()`. It was removed because:

- Apps Script Web Apps sit behind a Google login wall; anonymous deploys return HTML, not JSON
- OAuth token scopes (`script.scriptapp`) required a custom OAuth client
- gcloud-minted tokens have insufficient scopes
- The cookie-based POST path was fragile

Playwright drives the real form UI directly — the same way a human would, tolerant of Google's anti-bot measures.

## Design decisions

- **One browser session per run.** The persistent context is loaded once, reused for all records, closed at the end.
- **Dry-run is pure.** No browser launched when `dry_run=True`.
- **Errors are captured per-record.** A failing record returns `{"status": "error", "error": msg}` and the loop continues.
- **`slow_mo=500`** makes the browser act human-likely (pauses between actions).
- **No auth module needed.** The browser handles Google login via the persistent profile.

## Design constraints

- Form changes to the order or wording of the fields require updating `form_submit.py` (the locators are hardcoded there).
- The `google_profile/` directory contains real Google session data — add it to `.gitignore` (it already is).

## FAQ

**Q: Why does a browser window pop up?** Because DarkWing drives a real Chromium instance. Set `DARKWING_HEADLESS=true` to keep it invisible.

**Q: Do I need Google API credentials?** No. The browser profile holds the Google session.

**Q: What if a record fails?** The error is recorded in the results list; the run continues. Nothing is retried automatically yet.
