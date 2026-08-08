# Google Apps Script — DarkWing Webhook

This directory contains the reference implementation of the Google Apps Script
`doPost` handler that the DarkWing Python package calls to submit observations
to a Google Form.

## Deployment

1. Open [script.google.com](https://script.google.com/) and create a new project.
2. Paste the contents of `doPost.gs` into the editor.
3. Set the `FORM_ID` script property:
   - **File → Project settings → Script properties**
   - Add `FORM_ID` = the form's ID (the long string in the form URL)
4. Click **Deploy → New deployment** → select **Web app**:
   - Execute as: **Me** (your Google account)
   - Who has access: **Anyone with Google account** (or stricter, as needed)
5. Copy the `/exec` URL and add it to your `.env`:

   ```env
   DARKWING_APPS_SCRIPT_URL=https://script.google.com/macros/s/.../exec
   ```

## What the script does

- Receives a flat JSON object from the Python package.
- Matches each JSON key to a Google Form item by title (case-insensitive, spaces → underscores).
- Handles all common form item types: `TEXT`, `PARAGRAPH_TEXT`, `MULTIPLE_CHOICE`,
  `CHECKBOX`, `LIST`, `DATE`, `TIME`, `DATE_TIME`.
- Submits the response using the deployer's authenticated session.
- Returns `{"status": "success", "response": {...}}` or `{"status": "error", "message": "..."}`.

## Payload shape

The Python side sends the output of `ObservationRecord.to_form_payload()`:

```json
{
  "tower_id": "Tower 3",
  "date": "06/15/2026",
  "time_of_day": "06:00",
  "adult_swallows_in_chimney": 2,
  "nesting_stage": "No nest",
  "bill_use": "N/A or No",
  "adults_flew_in": ["Yes, at least one adult flew into the chimney"],
  "swallows_near_nest": 1,
  "awake": "Yes",
  "notes": "1 north, 1 west."
}
```

The script matches these keys to form item titles. If a form item title doesn't
match any key, it's skipped (no error). If a value doesn't match any choice for
a multiple-choice/checkbox/list item, the submission fails with a clear error.

## Security

- The script runs as the deployer, so the form submission is authenticated.
- The Python side sends a `Bearer` token in the `Authorization` header, but the
  script does **not** validate it — that's the Python side's job.
- The script is a thin pass-through. All business logic (validation, translation)
  lives in the Python package.
