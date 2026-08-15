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

See [docs/setup.md](docs/setup.md) for full setup. See [docs/tutorial-1.md](docs/tutorial-1.md) for an end-to-end walkthrough.

## CLI

```sh
darkwing {validate,submit} path/to/file.csv [--dry-run]
```

| Command | What it does |
| --- | --- |
| `validate <csv>` | Reads and validates every row against the Pydantic schema. Prints summary. Exit 0 = clean, 1 = errors. |
| `submit <csv> --dry-run` | Validates, expands short codes, prints what *would* be submitted. No browser launched. |
| `submit <csv>` | Validates, expands short codes, opens browser, fills Google Form for each row. |

## CSV Format

One row per 20-minute observation window:

```csv
tower,date_str,hour,minutes_past_hour,num_adults,nesting_stage,bill_use,flights,num_near_nest,awake,notes
3,6/15/2026,6,0,2,no,na,in;chg,1,y,1 north, 1 west
3,6/15/2026,6,20,0,no,na,non,0,nap,
```

**Short codes used:**

| Column | Codes | Meaning |
| --- | --- | --- |
| `nesting_stage` | `no`, `bld`, `egg`, `nst`, `fld` | No nest / Nest building / Egg(s) / Nestling(s) / Post-fledgling |
| `bill_use` | `na`, `mat`, `fd`, `egg`, `nst`, `ps`, `po`, `oth` | N/A / Material / Feeding / Egg tending / Nestling tending / Self-preening / Other-preening / Other |
| `flights` | `in`, `out`, `chg`, `non` | Flew in / Flew out / Changed position / None |
| `awake` | `y`, `n`, `mbe`, `nap` | Yes / No / Maybe / No adults present |

Semicolon-delimited for multi-select fields (e.g., `in;chg`).

## Environment Variables

Copy `.env.example` to `.env` and set:

| Variable | Required | Description |
| --- | --- | --- |
| `DARKWING_FORM_URL` | Yes | Full URL of the Google Form |
| `DARKWING_SUBMITTER_NAME` | Yes | Name to fill in the "Name" field |
| `DARKWING_HEADLESS` | No | `true` (default) or `false` for visible browser |

## Architecture

See [docs/architecture.md](docs/architecture.md) for component details.

## Testing

```bash
.venv/bin/pytest tests/
```

84 tests covering schema validation, CSV I/O, CLI, and form submission.

## License

MIT
