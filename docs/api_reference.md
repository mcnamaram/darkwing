# API Reference

The Python package talks to one external endpoint: the Google Apps Script `doPost` webhook. This document specifies that contract.

## Apps Script `doPost`

The script is hosted in the user's Google Apps Script editor and deployed as a *Web app* executing as the user, accessible to *Anyone in the organization with the link* (or stricter). The deployment's `/exec` URL is the value of `DARKWING_APPS_SCRIPT_URL` in the user's `.env` file. The script's project ID and the form ID it references are sensitive values; see [Secrets Handling](./secrets_handling.md).

### Request

```
POST <DARKWING_APPS_SCRIPT_URL>
Content-Type: application/json
Authorization: Bearer <gcloud access token>

{ ... JSON payload, see below ... }
```

### Response (success)

```
HTTP/1.1 200 OK
Content-Type: application/json

{"status": "success", "response": {"matched": <N>}}
```

### Response (script error)

```
HTTP/1.1 200 OK
Content-Type: application/json

{"status": "error", "message": "<error string from Apps Script>"}
```

### The script's role

The script is a thin pass-through wrapper. It receives a flat JSON object, walks the form's items, and for each item it finds a matching key in the JSON (by `getTitle()`), it sets the appropriate `FormApp.ItemResponse` based on the item's `getType()`. The script handles `TEXT`, `PARAGRAPH_TEXT`, `MULTIPLE_CHOICE`, `CHECKBOX`, `LIST`, and the date/time item sub-shapes. The Python side does all the title lookup, all the type coercion, all the translation-table expansion. The script does not contain a translation table of its own.

A reference implementation lives at `apps_script/doPost.gs` in this repository.

## JSON payload shape

The Python package sends a flat JSON object with one key per form question, where each key is the form question's title exactly as displayed. The full key list, with example values, is:

```json
{
  "Email": "submitter@example.org",
  "Name (first, last) of Individual Collecting Data": "Submitting Volunteer",
  "Tower Number": "Tower 3",
  "Date of footage being analyzed (please input date in this format M/D/YYYY)": "6/15/2026",
  "Hour of footage being analyzed. Enter numbers in 24-hr time, i.e., 0 = 12am, 1 = 1am, 12 = 1pm, 13 = 1pm": 13,
  "Approximate minutes after the hour. There should be three entries per hour. If no bird is in the chimney at 00, 20, or 40 then scan ahead, minute-by-minute to the next time when a bird is present.": 40,
  "How many adult Swifts are inside the chimney? Give your best guess.": 2,
  "Stage in the Nesting Cycle": "No nest",
  "Do any of the adults have something in their bill, or are using their bill?": "N/A or No",
  "Did you observe any flight(s) going in or out of the chimney during the 1-minute video segment you watched? Did you observe any flights of Swifts inside the chimney, such as when they are changing position inside? (Please select at most 3 options.)": [
    "Yes, at least one adult flew into the chimney",
    "Yes, at least one adult changed position within the chimney but did not enter or exit"
  ],
  "How many adults are within two body-lengths of the nest? Examples include sitting on nest, perched next to it, perched underneath it, or perched above it. If a group of Swifts are perched next to one another, include all of them in your count.": 1,
  "Are there any adults awake with eyes open?": "Yes",
  "Note any interesting behaviors not already included on this form. Include social interactions that could be characterized as courtship or aggressive. Do not try to interpret the behaviors; just state what happened, giving as much detail as possible.": "1 north, 1 west. west moved to north"
}
```

These exact titles live in the form definition; changing the form changes these strings and requires a matching change in `to_form_payload()`. The package's tests assert the title strings so a form change is caught at test time, not at submission time.

The short codes that the user types in the CSV are translated into the form's full text by the `to_form_payload()` method on the `ObservationRecord` class. The translation table is documented in the [Architecture document](./architecture.md#csv-schema-and-translation-table).

## Sub-fields (Date, Time)

The form's *Date of footage being analyzed* question accepts a date string in the format the user has prefilled in the form's example field: `M/D/YYYY`. The Python code sends it as a single string; the form's `DateItem` accepts that string directly.

The form's *Hour* and *Minutes past hour* questions are sent as integers. The form's `TimeItem` accepts integers in the `0–23` and `{0, 20, 40}` ranges respectively.

## Authentication

The bearer token is retrieved by shelling out to `gcloud auth print-access-token`. The token is short-lived (60 minutes); the package caches it for 50 minutes. On a 401 response, the package refreshes the token once and retries; a second 401 stops the batch with a clear error.

See [Setup](./setup.md#google-authentication) for the one-time authentication flow.

## Why the Apps Script, not the Google Forms API

The Google Forms API (the `forms.responses` collection) targets the new Google Forms product, whose form IDs are short opaque strings (e.g. `1abcXYZ…`). The form in this project is a Classic Google Form, whose URL contains the longer `1FAIpQLS…` prefix. The Forms API does not support submitting responses to Classic Forms.

Two alternative paths were considered and rejected:
- **Migrate the form to the new product.** A one-time effort, but disruptive to any existing responses and to any other consumer of the form.
- **POST directly to the form's `formResponse` endpoint.** Fragile — the endpoint requires fresh CSRF tokens and session cookies, and breaks whenever Google changes the form UI. This is what the `googleforms` curl capture was attempting.

The Apps Script `doPost` path is the lowest-risk option that works with the existing form and the user's existing authenticated session.
