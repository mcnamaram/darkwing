# Tutorial: Your First Submission

This tutorial walks a new user through submitting a small CSV of observation rows to the Google Form. By the end, you will have submitted records and seen them appear in the form's responses.

## Prerequisites

You have followed [Setup](./setup.md) and have:

- An active `.venv` with the package installed (`pip install -e .[dev]`).
- A `.env` file with `DARKWING_FORM_URL` and `DARKWING_SUBMITTER_NAME` set.
- Playwright browsers installed (`playwright install chromium`).

## 1. Create a test CSV

Create a file at `~/Desktop/test_observations.csv` with these contents:

```csv
tower,date_str,hour,minutes_past_hour,num_adults,nesting_stage,bill_use,flights,num_near_nest,awake,notes
3,6/15/2026,6,0,2,no,na,in;chg,1,y,1 north, 1 west. west moved to north
3,6/15/2026,6,20,0,no,na,non,0,nap,
```

The column names match the Pydantic schema. `flights` uses semicolon-delimited short codes (e.g. `in` or `in;out`).

## 2. Validate the CSV

```bash
.venv/bin/darkwing validate ~/Desktop/test_observations.csv
```

Expected output: `2 record(s) validated successfully.`

## 3. Dry-run the submission

```bash
.venv/bin/darkwing submit ~/Desktop/test_observations.csv --dry-run
```

Expected output: a summary showing 2 records would be submitted. No browser opens.

## 4. Submit for real

```bash
.venv/bin/darkwing submit ~/Desktop/test_observations.csv
```

A Chromium browser opens, navigates to the form, and fills and submits it automatically.

Expected output:

```sh
Submitting 2 record(s) to the form...
✓ 2/2 record(s) submitted.
```

Every attempt is appended to `submitted_log.jsonl` in the working directory.

If you re-run the same command, DarkWing skips rows already logged as successfully submitted:

```sh
Skipping 2 record(s) already submitted (per submitted_log.jsonl).
All record(s) were already submitted. Nothing to do.
```

Use `--no-resume` to submit all rows again regardless of the log.

## 5. Verify

Check the Google Form responses sheet — you should see 2 new entries.

## 6. Automated Detection (MVP2/MVP3)

For an end-to-end pipeline (detect motion → VLM analysis → form submission):

```bash
# Detect motion and identify review windows
.venv/bin/darkwing detect ~/Desktop/my_camera_footage.mp4
```

**What this does:**
1. Processes the video with MOG2 background-subtraction.
2. Groups frames into 10-minute observation windows.
3. Classifies each window as `SKIP` (no motion), `REVIEW` (motion detected), or `MANUAL` (high-glare/unreliable).
4. Writes results to `review_index.jsonl`.

For an end-to-end pipeline (detect + VLM analysis + form submission), see [Tutorial 2: Automated Pipeline](./tutorial-2.md).

## Troubleshooting

- **Browser doesn't open**: Ensure `DARKWING_FORM_URL` is set correctly in `.env`.
- **Timeout errors**: The form may be slow to load. Try `DARKWING_HEADLESS=false` to watch what's happening.
- **Selector errors**: The form may have changed. Check [architecture.md](./architecture.md) for current selectors.
