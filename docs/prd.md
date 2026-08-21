# Project Requirements

## Why this project exists

The Wild Bird Recovery research program operates Reolink cameras pointed at Chimney Swift nesting towers. A researcher (or volunteer) needs to watch each day's footage and record structured observations at three points in every hour from 6:00 AM to 9:00 PM. Today, that work is done by hand against a Google Form, one response per observation, and the data is tedious to type: the form's questions are long-form, the response values are long-form, and there are 45 observations per day per tower. The form itself lives behind an organization that requires authenticated submission, which means a plain `curl` against the form's `formResponse` endpoint returns 404.

**What success looks like.** A researcher can produce a CSV (by hand, from a spreadsheet, or eventually from automated video detection) and submit all of its rows to the form, with the work checked in and resumable, with each row validated before it leaves the local machine, and without manually typing the form's long-form question text or long-form answer text on every row.

## What we're solving

1. **The form's question text is long and repetitive.** Manually transcribing each row is slow and error-prone.
2. **The form's answer values are long and repetitive.** Each answer is a full sentence ("Yes, at least one adult flew into the chimney"). For a single day at a single tower, that's 45 rows × 5–6 form fields × a sentence per field — too many keystrokes for a volunteer workflow.
3. **The form requires authenticated submission.** Direct POSTs to the form's public endpoint do not work; the user must go through an authenticated path.
4. **Submission is currently one form-response at a time, in a browser.** There is no way to submit a batch.
5. **There is no way to review before submitting.** Once a row is in the form's responses sheet, the only way to fix it is to edit the sheet directly.

## The approach

A small Python package reads a curated CSV (one row per observation) and submits each row, one at a time, to a Google Form using Playwright browser automation. The Python code:

- accepts **short codes** (2–3 characters) in the CSV for any answer that has a fixed set of values,
- expands those codes into the form's full answer text before sending,
- validates every row against a fixed schema before any network call,
- logs every submission attempt locally so the work is auditable and resumable,
- handles auth via a persistent browser profile — the user logs into Google once, and the session is reused.

## What data is collected

One row per observation. An "observation" is one of three checkpoints in an hour, 6:00 AM to 9:00 PM, 45 rows per day per tower. For each row the system captures:

- **When**: the date and the hour, plus which of the three checkpoints (00, 20, or 40 minutes past the hour).
- **Where**: the tower number (e.g. `3`).
- **What was seen**: the count of adult swifts inside the chimney, the stage in the nesting cycle, what the swifts were doing with their bills, what flight activity was observed, how many adults were near the nest, and whether any adults were awake.
- **Free-form notes**: anything the researcher noticed that the form's questions don't already cover.

The exact fields and their values are defined in the [Architecture document](./architecture.md); the schema, the validation rules, and the code-side translation table live there. This document is intentionally not specific about the data shape — it's specific about the *why*.

## What is in scope for MVP1

- A hand-curated CSV (one row per observation) is read by the system.
- Each row is validated against the schema defined in [Architecture](./architecture.md).
- Each validated row is filled into the Google Form in a real Chromium browser (via Playwright), which submits it through the form's authenticated path.
- A local JSON-Lines log file records every submission attempt.
- The work is resumable: re-running a submission skips rows that have already been logged as successful.

## What is out of scope (planned for later epics)

- **Video playback download** from the Reolink camera (MVP2). A researcher still curates the CSV by hand in MVP1.
- **Automated detection of adult swifts in video** (MVP3). Today, a human watches the video and decides what to put in the CSV.
- **A human-review UI before submission** (MVP4). Today, the CSV is the review layer; the user edits the CSV before running the submit.
- **Multi-user support.** MVP1 is single-submitter; the submitter's name and email come from a local config file.

## Acceptance criteria for MVP1

The system is considered done when, given a CSV of valid rows, an authenticated user can:

1. Run one command and have every valid row appear in the form's responses sheet.
2. Re-run the same command after a partial failure and have only the previously-uncaught rows submitted.
3. See a clear error (and no network call) for any row that fails validation.
4. See a clear error and a partial-batch state if the browser session or Google login expires mid-batch.
5. Have no row of the CSV persisted to a remote system that the form did not accept.

## Acknowledgements

The project depends on the [Reolink Camera API Python client](https://github.com/ReolinkCameraAPI/reolinkapipy) maintained by Oleaintueri and the Reolink community, which provides the playback-download primitives that the MVP2 epic will use.
