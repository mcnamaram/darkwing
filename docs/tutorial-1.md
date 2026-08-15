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

A Chromium browser opens, navigates to the form, and fills it out automatically.

Expected output:

```sh
success: 3 06/16/2026 07:00
success: 3 06/16/2026 07:20
...
```

A `submitted_log.jsonl` file records each attempt.

## 5. Verify

Check the Google Form responses sheet — you should see 2 new entries.

## Troubleshooting

- **Browser doesn't open**: Ensure `DARKWING_FORM_URL` is set correctly in `.env`.
- **Timeout errors**: The form may be slow to load. Try `DARKWING_HEADLESS=false` to watch what's happening.
- **Selector errors**: The form may have changed. Check [architecture.md](./architecture.md) for current selectors.
