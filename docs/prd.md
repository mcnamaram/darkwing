# Project Requirements

## Vision
The DarkWing research project automates chimney swift observation data ingestion from Reolink camera footage into Google Forms. It transitions from manual CSV data entry to a fully automated pipeline: motion detection → VLM frame analysis → structured form submission.

## MVP Phases & Scope
- **MVP1: Manual Submission (Complete)**
    - Validate observation CSVs against Pydantic schema.
    - Automated submission via Playwright to authenticated Google Forms.
    - Resumable submission via `submitted_log.jsonl`.
- **MVP2: Motion Detection (Complete)**
    - Offline background-subtraction (MOG2) detector.
    - Aggregation into 10-minute observation windows.
    - Classification: `SKIP` (no motion), `REVIEW` (motion detected), `MANUAL` (high-glare/unreliable).
- **MVP3: VLM Agent Integration (Complete)**
    - VLM (Gemini/OpenAI) analysis of keyframes from `REVIEW` windows.
    - Automated generation of `ObservationRecord` JSON from visual data.

## Business Rules
1. **Data Integrity:** Every observation must be validated against the Pydantic schema (`src/darkwing/schema.py`) before persistence or submission.
2. **Deterministic Resumability:** Any interrupted process must be restartable from the last successful record/window without duplicating work.
3. **Transparency:** All automated actions (detection classification, agent-proposed observations, form submission) must be logged for auditability.
4. **Human-in-the-Loop:** `MANUAL` detection windows MUST be flagged for manual review and never automatically processed by the VLM agent.

## Acceptance Criteria
- **MVP1:** Submission command succeeds for valid CSV; logs successful submissions; skips already-submitted rows.
- **MVP2:** Detector identifies empty windows; classifies windows accurately (SKIP/REVIEW/MANUAL); logs per-window classification.
- **MVP3:** Agent successfully processes `REVIEW` windows; generates valid observation JSON; form submission succeeds for generated records.

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
