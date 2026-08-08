# 🐦 DarkWing Swift Reporter

Automated, structured observation reporting for Chimney Swifts.

## Overview

DarkWing reads a CSV of curated observations, validates each row, expands short codes into the Google Form's long-form text, and submits them one at a time via a Google Apps Script `doPost` webhook. The webhook constructs and submits the form responses on your behalf. A local JSON-Lines log file (`submitted_log.jsonl`) records every attempt.

**What this is:** A batch-submission tool for volunteer chimney swift observers who fill out a Google Form many times per day. One CSV row = one form response.

**What this is not:** A video-analysis system. It does not connect to cameras or run detection models. It works with data that a human has already curated.

## Quick start

```bash
# Install
git clone https://github.com/mcnamaram/darkwing.git
cd darkwing
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Configure — see docs/setup.md for full instructions
cp .env.example .env   # (create manually; see docs)
gcloud auth login

# Validate a CSV
darkwing validate observations.csv

# Dry-run submit
darkwing submit observations.csv --dry-run

# Submit for real
darkwing submit observations.csv
```

See [docs/setup.md](docs/setup.md) for full setup. See [docs/tutorial-1.md](docs/tutorial-1.md) for an end-to-end walkthrough.

## CLI

```
darkwing {validate,submit} path/to/file.csv [--dry-run]
```

| Command | What it does |
|---|---|
| `validate <csv>` | Reads and validates every row against the Pydantic schema. Prints summary. Exit 0 = clean, 1 = errors. |
| `submit <csv> --dry-run` | Validates, expands short codes, prints what *would* be submitted. No network calls. |
| `submit <csv>` | Validates, expands short codes, POSTs each row to the Apps Script webhook. Logs every attempt to `submitted_log.jsonl`. |

## CSV format

The `flights` column uses semicolon-delimited short codes (no quoting needed):

```csv
tower,date_str,hour,minutes_past_hour,num_adults,nesting_stage,bill_use,flights,num_near_nest,awake,notes
3,6/15/2026,6,0,2,no,na,in;chg,1,y,1 north, 1 west
```

| Column | Example | Notes |
|---|---|---|
| `tower` | `3` | Maps to "Tower 3" on the form |
| `date_str` | `6/15/2026` | M/D/YYYY or MM/DD/YYYY — auto-normalised |
| `hour` | `6` | 0–23 |
| `minutes_past_hour` | `0` | Any integer 0–59 |
| `num_adults` | `2` | ≥ 0 |
| `nesting_stage` | `no` | Short code → "No nest", "Nest building", etc. |
| `bill_use` | `na` | Short code → "N/A or No", "Yes, handling a stick", etc. |
| `flights` | `in;chg` | Semicolon-delimited short codes: `in`, `out`, `chg`, `non`. Empty = no flights. Legacy JSON arrays like `["in"]` still parse. |
| `num_near_nest` | `1` | ≥ 0 |
| `awake` | `y` | `y`, `n`, `mbe`, `nap` |
| `notes` | `1 north, 1 west` | Free text |

Translation tables are in `src/darkwing/schema.py`.

## Project structure

```
src/darkwing/
  schema.py       # Pydantic models + short-code → form-text tables
  csv_io.py       # CSV read (DictReader) + JSON-Lines submission log
  form_submit.py  # HTTP POST to Apps Script webhook
  auth.py         # gcloud OAuth token retrieval + 50-min cache
  cli.py          # argparse CLI (validate / submit)
tests/
  fixtures/sample_observation.csv   # tiny live CSV for tests
  test_schema.py, test_csv_io.py,
  test_form_submit.py, test_auth.py, test_cli.py
docs/          # MkDocs (Material) site, deployed to GitHub Pages
```

## Tech

- **Python 3.14** (pinned in `.python-version`)
- **pydantic v2** — row validation and short-code expansion
- **requests** — HTTP POST to the Apps Script webhook
- **python-dotenv** — reads `.env` for config
- **pytest** — 92 tests covering schema, CSV I/O, auth, submission, and CLI

## Docs site

Built with MkDocs (Material theme) and auto-deployed to GitHub Pages on every push to `main`. Local preview:

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

Navigate to <http://localhost:8000>.

## Testing

```bash
.venv/bin/pytest -v
```

92 tests, all passing.
