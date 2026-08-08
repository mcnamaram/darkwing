# Tutorial: Your First Submission

This tutorial walks a new user through submitting a small CSV of observation rows to the Google Form. By the end, you will have a `submitted_log.jsonl` file recording each attempt and (assuming the Apps Script `doPost` is deployed) new entries in the form's responses sheet.

## Prerequisites

You have followed [Setup](./setup.md) and have:

- An active `.venv` with the package installed (`pip install -e .`).
- A `.env` file with the required `DARKWING_*` variables set.
- A working `gcloud auth print-access-token` (verified by running it in a shell).

## 1. Create a test CSV

Create a file at `~/Desktop/test_observations.csv` with these contents:

```csv
tower,date_str,hour,minutes_past_hour,num_adults,nesting_stage,bill_use,flights,num_near_nest,awake,notes
3,6/15/2026,6,0,2,no,na,in;chg,1,y,1 north, 1 west. west moved to north
3,6/15/2026,6,20,0,no,na,non,0,nap,
```

The column names are exactly what `to_form_payload()` expects. `flights` uses semicolon-delimited short codes (e.g. `in` or `in;out`); `num_adults` is an integer; `awake` accepts the four enum values exactly as the form spells them.

## 2. Validate the CSV

```bash
.venv/bin/darkwing validate ~/Desktop/test_observations.csv
```

Expected output: `2 row(s) validated successfully.` If you see schema errors, the message points at the offending row and column.

## 3. Dry-run the submission

```bash
.venv/bin/darkwing submit ~/Desktop/test_observations.csv --dry-run
```

Expected output: a table of the two rows that *would* be submitted, with their target form fields. No network calls. No log file written.

## 4. Submit for real

```bash
.venv/bin/darkwing submit ~/Desktop/test_observations.csv
```

Expected output:

```
Submitting 2 record(s) to the form...
[1/2] uuid=… status=200
[2/2] uuid=… status=200
✓ 2/2 record(s) submitted.
```

Each row is posted individually. A `submitted_log.jsonl` file is created in the repo root with one JSON line per attempt.

## 5. Inspect the log

```bash
cat submitted_log.jsonl | head
```

Each line is a JSON object: `{uuid, timestamp_utc, tower, time_of_day, http_status, attempt_count, error?}`.

## Troubleshooting

**"DARKWING_APPS_SCRIPT_URL not set"** — Check that `.env` exists and contains the variable. Run `gcloud auth print-access-token` to verify your token is fresh.

**401/403 from the webhook** — Your Google account may not have access to the form or the Apps Script deployment. Re-run `gcloud auth login` and verify the account matches the one that deployed the script.

**Schema errors** — The CSV column names must match exactly (case-sensitive). The `flights` column accepts semicolons (`in;out`) or JSON arrays (`["in","out"]`) for backwards compatibility.
