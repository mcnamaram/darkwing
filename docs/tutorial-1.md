# Tutorial: Your First Submission

This tutorial walks a new user through submitting a small CSV of observation rows to the Google Form. By the end, you will have a `submitted_log.jsonl` file recording each attempt and (assuming the Apps Script `doPost` is in its extended form) two new entries in the form's responses sheet.

## Prerequisites

You have followed [Setup](./setup.md) and have:

- An active `.venv` with the package's dependencies installed.
- A `.env` file with the required `DARKWING_*` variables set.
- A working `gcloud auth print-access-token` (verified by running it in a shell).

## 1. Create a test CSV

Create a file at `~/Desktop/test_observations.csv` with these contents:

```csv
date_str,hour,minutes_past_hour,tower,num_adults,nesting_stage,bill_use,flights,num_near_nest,awake,notes
6/15/2026,6,0,Tower 3,2,No nest,N/A or No,"[Yes, at least one adult flew into the chimney,Yes, at least one adult changed position within the chimney but did not enter or exit]",1,Yes,Test row 1
6/15/2026,6,20,Tower 3,0,No nest,N/A or No,[None of the above],0,No adults present,No swifts in this window
```

The column names are exactly what `to_form_payload()` expects. `flights` is a JSON-encoded list; `num_adults` is an integer; `awake` accepts the four enum values exactly as the form spells them.

## 2. Validate the CSV

```bash
.venv/bin/python -m darkwing validate ~/Desktop/test_observations.csv
```

Expected output: `2 rows validated, 0 errors.` If you see schema errors, the message points at the offending row and column.

## 3. Dry-run the submission

```bash
.venv/bin/python -m darkwing submit ~/Desktop/test_observations.csv --dry-run
```

Expected output: a table of the two rows that *would* be submitted, with their target form fields. No network calls. No log file written.

## 4. Submit for real

```bash
.venv/bin/python -m darkwing submit ~/Desktop/test_observations.csv
```

Expected output:

```
[1/2] submitting uuid=… timestamp_utc=2026-06-15T10:00:00Z → 200
[2/2] submitting uuid=… timestamp_utc=2026-06-15T10:20:00Z → 200
done: 2 submitted, 0 skipped, 0 errors
log: ./submitted_log.jsonl
```

Open `submitted_log.jsonl` to see one JSON line per attempt.

## 5. Verify in the form

Open the target Google Form's responses sheet. You should see two new rows corresponding to your submission. The form's `Email`, `Name`, and `Tower Number` columns are filled from your `.env` configuration; the data columns are filled from the CSV.

## 6. Re-running safely

`submitted_log.jsonl` is the system's source of truth for "what has been sent." Re-running the same submit command without `--force` will skip the rows that are already in the log:

```bash
.venv/bin/python -m darkwing submit ~/Desktop/test_observations.csv
# → done: 0 submitted, 0 skipped, 0 errors
# → log: ./submitted_log.jsonl
```

To re-submit a row deliberately, edit it in the CSV and re-run with `--force`, or delete the corresponding line from `submitted_log.jsonl`.

## 7. The notebook alternative

If you prefer a notebook interface, open `notebooks/01_submit_existing_csv.ipynb`. It exposes the same five steps as cells: imports, validate, summarize, submit with progress, and final log location. The notebook is a thin wrapper around the same `darkwing.csv_io` and `darkwing.form_submit` modules that the CLI uses.
