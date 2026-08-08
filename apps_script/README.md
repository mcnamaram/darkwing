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
- Matches each JSON key to a Google Form item by **exact title** (no normalization needed).
- Handles all common form item types: `TEXT`, `PARAGRAPH_TEXT`, `MULTIPLE_CHOICE`,
  `CHECKBOX`, `LIST`, `DATE`, `TIME`, `DATE_TIME`.
- Submits the response using the deployer's authenticated session.
- Returns `{"status": "success", "response": {...}}` or `{"status": "error", "message": "..."}`.

## Payload shape

The Python side sends the output of `ObservationRecord.to_form_payload()`. Keys are the **exact** Google Form item titles — no normalization is performed in the Apps Script:

```json
{
  "Tower Number": "Tower 3",
  "Date of footage being analyzed (please input date in this format M/D/YYYY)": "06/15/2026",
  "Approximate minutes after the hour. There should be three entries per hour. If no bird is in the chimney at 00, 20, or 40 then scan ahead, minute-by-minute to the next time when a bird is present.": "06:00",
  "How many adult Swifts are inside the chimney? Give your best guess.": 2,
  "Stage in the Nesting Cycle": "No nest",
  "Do any of the adults have something in their bill, or are using their bill?": "N/A or No",
  "Did you observe any flight(s) going in or out of the chimney during the 1-minute video segment you watched? Did you observe any flights of Swifts inside the chimney, such as when they are changing position inside?": ["Yes, at least one adult flew into the chimney"],
  "How many adults are within two body-lengths of the nest? Examples include sitting on nest, perched next to it, perched underneath it, or perched above it. If a group of Swifts are perched next to one another, include all of them in your count.": 1,
  "Are there any adults awake with eyes open?": "Yes",
  "Note any interesting behaviors not already included on this form. Include social interactions that could be characterized as courtship or aggressive. Do not try to interpret the behaviors; just state what you observed.": "1 north, 1 west"
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
