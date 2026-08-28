# 🐦 DarkWing Swift Reporter

Automated, structured observation reporting for Chimney Swifts.

## Overview

DarkWing reads a CSV of curated observations, validates each row, expands short codes into the Google Form's long-form text, and submits them one at a time via Playwright browser automation. A local JSON-Lines log file (`submitted_log.jsonl`) records every attempt.

**What this is:** A batch-submission tool for volunteer chimney swift observers who fill out a Google Form many times per day. One CSV row = one form response.

**What this is not:** A video-analysis system. It does not connect to cameras or run detection models. It works with data that a human has already curated.

## Quick start

```bash
# Install
git clone https://github.com/mcnamaram/darkwing.git
cd darkwing
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env   # edit with your values
playwright install chromium

# Validate a CSV
darkwing validate observations.csv

# Dry-run submit (no browser)
darkwing submit observations.csv --dry-run

# Submit for real (opens visible browser)
darkwing submit observations.csv
```

## CLI

```sh
darkwing {validate,submit,detect} path/to/file.csv [options]
```

### Commands

| Command | What it does |
| --- | --- |
| `validate <csv>` | Reads and validates every row against the Pydantic schema. Prints summary. Exit 0 = clean, 1 = errors. |
| `submit <csv> [--dry-run]` | Validates, expands short codes, prints what *would* be submitted. With `--dry-run` no browser launched, no log written. Without `--dry-run` opens browser, fills Google Form for each row. Appends every attempt to `submitted_log.jsonl`. |
| `detect <options>` | Run detection over local footage and emit a review index (JSONL). Offline-first: reads from local mp4 via `--source-path`. Produces a window-level verdict (SKIP, REVIEW, MANUAL) for each observation window. See `darkwing detect --help` for details. |

See [docs/setup.md](docs/setup.md) for full setup. See [docs/tutorial-1.md](docs/tutorial-1.md) for an end-to-end walkthrough.