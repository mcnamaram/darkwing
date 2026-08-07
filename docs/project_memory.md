# DarkWing — Project Roadmap

> **Read this first.** It tells you where the project is, what's been done, what's next, and where the work lives.

## What this project is

**DarkWing** reads a curated CSV of Chimney Swift observations and submits each row, one at a time, to a Google Form operated by the Wild Bird Recovery research program. The "why" lives in the [Project Requirements](./prd.md); the "how" lives in the [System Architecture](./architecture.md); the contract with the webhook lives in the [API Reference](./api_reference.md).

---

## Current status

| Phase | Name | Status | What it delivers |
| --- | --- | --- | --- |
| 0 | Repo reset | ✅ done | Clean tree, no broken source or build artifacts |
| 0.5 | Docs aligned | ✅ done | All docs rewritten to match MVP1 design |
| 1 | Schema | ✅ done | `src/darkwing/schema.py` — Pydantic models, short-code translation table |
| 2 | CSV I/O | ✅ done | `src/darkwing/csv_io.py` — read CSV, write submission log |
| 3 | Auth | ✅ done | `src/darkwing/auth.py` — gcloud token retrieval with 50-min cache |
| 4 | Form submit | ✅ done | `src/darkwing/form_submit.py` — POST to Apps Script webhook |
| 5 | CLI + notebook | ✅ done (CLI) | `src/darkwing/cli.py` — `darkwing validate/submit`. Notebook TBD |
| 6 | Apps Script | ✅ done | `apps_script/doPost.gs` — reference handler for all form item types |
| 7 | Manual smoke | 🟠 blocked | One real run against the live form (needs user to deploy Apps Script) |

**Legend:** ⬜ not started · ✅ done · 🟡 in progress · 🟠 blocked

**Test coverage:** 81 tests, all green. See [Test Strategy](./test_strategy.md).

---

## What changed (and what didn't) since the old code

| Before (broken) | Now (MVP1) |
| --- | --- |
| `src/analysis_engine.py`, `main_processor.py`, `scheduler.py`, `camera_client.py`, `config.py`, `data_types.py` | All deleted |
| Video detection logic (MVP2+) | Deferred — not in scope |
| `site/` build artifacts in repo | Gone; `.gitignore` covers them |
| `googleforms` captured-header file | Removed from index |
| `requirements.txt` had `reolinkapi`, `opencv-python`, `dotenv` | Now: `pydantic`, `requests`, `pytest`, `python-dotenv` |

---

## Source tree (what you'll find)

```ascii
src/darkwing/
  schema.py      Pydantic ObservationRecord + translation tables
  csv_io.py      read_csv(), write_submission_log(), get_submission_log()
  auth.py        get_token() — gcloud token with 50-min cache
  form_submit.py submit_record(), submit_csv_records()
  cli.py         darkwing validate|submit <csv> [--dry-run]

tests/
  conftest.py    Shared fixtures (sample CSV, apps_script payload)
  test_schema.py 46 tests — all validation rules
  test_csv_io.py 13 tests — read, errors, log I/O
  test_auth.py    8 tests — gcloud mock, cache behaviour
  test_form_submit.py 7 tests — POST, error, dry-run
  test_cli.py     7 tests — validate, submit, help
  fixtures/
    sample_observation.csv  4-row sample (realistic data)

apps_script/
  doPost.gs      Reference Apps Script handler (all item types)
  README.md      Deployment instructions
```

---

## What's next

### Immediate — Phase 7: manual smoke test

Deploy `apps_script/doPost.gs` to your Google Apps Script editor, set `FORM_ID` in script properties, and run:

```bash
.venv/bin/python -m darkwing.cli submit tests/fixtures/sample_observation.csv --dry-run
.venv/bin/python -m darkwing.cli submit tests/fixtures/sample_observation.csv
```

One human-verified submission against the live form closes MVP1.

### Planned — Phase 5 (remainder): Jupyter notebook

`notebooks/01_submit_existing_csv.ipynb` — a five-cell notebook that wraps the CLI for non-technical users. Skipped for now because the CLI works and the notebook can be added in a future commit.

### Future — MVP2: video detection

Automated observation generation from Reolink camera footage. Would reintroduce `reolinkapi`, `opencv-python`, and the video-processing pipeline. Not started; the architecture in [architecture.md](./architecture.md) leaves a clean extension point.

---

## How to run

```bash
# Install
pip install -r requirements.txt

# Run tests
pytest -v

# Validate a CSV (no submission)
python -m darkwing.cli validate path/to/observations.csv

# Submit a CSV (real)
python -m darkwing.cli submit path/to/observations.csv

# Submit with dry-run (preview only)
python -m darkwing.cli submit path/to/observations.csv --dry-run

# Build docs
mkdocs build && mkdocs serve
```

Requires `DARKWING_APPS_SCRIPT_URL` in your `.env` or environment. See [Secrets Handling](./secrets_handling.md).
