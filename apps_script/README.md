# Google Apps Script — DarkWing Webhook

This directory contains the reference implementation of the Google Apps Script
`doPost` handler that the DarkWing Python package calls to submit observations
to a Google Form.

## What this does

When DarkWing submits an observation, it POSTs a JSON payload to this script's
webhook URL. The script reads the JSON, matches each field to the correct
Google Form question, and submits the response on your behalf.

**Read the full API contract:** [DarkWing API Reference](../docs/api_reference.md)

---

## Quick Start (One-Time Setup)

### 1. Create the Apps Script Project

1. Go to [script.google.com](https://script.google.com/)
2. Click **New project** (top left)
3. Open the project's script file (default: `Code.js`) and replace its contents with `Code.js` from this directory
4. **File → Project settings** → Scroll to **Script Properties**
5. Add a new property:
   - **Name:** `FORM_ID`
   - **Value:** The form ID from your Google Form URL

   Your form URL looks like:

   ```url
   https://docs.google.com/forms/d/e/YOUR_FORM_ID_HERE/viewform
   ```

6. Click **Save**

### 2. Deploy as Web App

1. **Deploy → New deployment**
2. Click the gear icon → **Web app**
3. Configure:
   - **Description:** `DarkWing webhook`
   - **Execute as:** `Me` (your Google account)
   - **Who has access:** `Anyone with Google account`
4. Click **Deploy**
5. **Authorize access** when prompted (this is normal — the script needs permission to submit forms on your behalf)
6. Copy the **Web app URL** — it looks like:

   ```url
   https://script.google.com/macros/s/AKfycbx.../exec
   ```

### 3. Connect to DarkWing

Add the webhook URL to your DarkWing project's `.env` file:

```env
DARKWING_APPS_SCRIPT_URL=https://script.google.com/macros/s/AKfycbx.../exec
```

You're done! Run `darkwing submit observations.csv` to test.

---

## CI/CD Deployment (Optional)

This project includes a GitHub Actions workflow that automatically deploys updates
when `Code.js` changes. See the [GitHub Actions guide](#github-actions-cicd) below.

---

## How the Script Works

### Title Mapping

The `TITLE_MAP` object at the top of `Code.js` maps clean payload keys to
actual Google Form question titles. If you rename a form question, just update
the mapping — no Python changes needed.

**Example:**

```javascript
var TITLE_MAP = {
  "tower_id": "Tower Number",
  "date": "Date of footage being analyzed (please input date in this format M/D/YYYY)",
  "time_of_day": "Approximate minutes after the hour..."
};
```

### Payload Format

The Python side sends JSON like this:

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
  "notes": "1 north, 1 west"
}
```

Short codes are expanded before sending (e.g., `"no"` → `"No nest"`).

### Supported Form Field Types

| Apps Script Type | Python Value | Example |
| ------------------ | -------------- | --------- |
| `TEXT` / `PARAGRAPH_TEXT` | string | `"No nest"` |
| `MULTIPLE_CHOICE` | string | `"Yes"` |
| `LIST` | string | `"Maybe"` |
| `CHECKBOX` | array of strings | `["in", "out"]` |
| `DATE` | string `M/D/YYYY` | `"06/15/2026"` |
| `TIME` | string `HH:MM` | `"06:00"` |
| `DATE_TIME` | string | Handled automatically |

---

## GitHub Actions CI/CD

### Overview

The workflow (`.github/workflows/deploy-apps-script.yml`) automatically deploys
the script when `Code.js` changes. It uses [clasp](https://github.com/google/clasp),
the official Google Apps Script CLI.

**Official docs:**

- [clasp CLI Guide](https://developers.google.com/apps-script/guides/clasp)
- [clasp GitHub Repo](https://github.com/google/clasp)

### Prerequisites

1. **Node.js 20+** — clasp requires Node.js
2. **Google Cloud Project** with Apps Script API enabled
3. **OAuth Credentials** for the script to deploy on your behalf

### Setup Steps

#### Step 1: Create Google Cloud Project

1. Go to [Google App Script](https://script.google.com/home)
2. Select the DarkWing project (from the Quick Setup above).
3. Enable the Google Apps Script API (Script API)
   - Navigate to Settings.
   - Click on Google Apps Script API.
   - Toggle it on.

#### Step 2: Install and Login with clasp

```bash
# Install clasp globally
npm install -g @google/clasp

# Login (opens browser for OAuth)
clasp login

# Link to your Apps Script project
clasp clone YOUR_SCRIPT_ID
# OR create new:
clasp create --title "DarkWing Webhook"
```

#### Step 3: Get Clasp Tokens

After `clasp login`, your credentials are stored in `~/.clasprc.json`:

```bash
cat ~/.clasprc.json
```

#### Step 4: Add GitHub Secrets

In your GitHub repository, go to **Settings → Secrets and variables → Actions** and add:

| Secret Name | Value |
| ------------- | ------- |
| `CLASPRC_JSON` | Full JSON from `~/.clasprc.json` |
| `CLASP_JSON` | Full JSON from `.clasp.json` |

**Ensure .clasp.json (and .clasprc.json) are in the .gitignore. They contain sensitive values.**

#### Step 5: Trigger Deployment

Push changes to `main`:

```bash
git add apps_script/Code.js
git commit -m "fix: update form mapping"
git push origin main
```

The workflow runs automatically when these files change:

- `apps_script/Code.js`
- `apps_script/appsscript.json`
- `.github/workflows/deploy-apps-script.yml`

### Troubleshooting

**"clasp login fails"**

- Make sure you've enabled the Apps Script API in Google Cloud Console
- Check that your OAuth consent screen is configured (for testing, set **Test app**)

**"Deploy fails with 403"**

- The script needs the `https://www.googleapis.com/auth/script.deployments` scope
- Re-authorize clasp: `clasp logout && clasp login`

**"Token expired"**

- Refresh tokens last indefinitely; access tokens expire every hour
- The workflow handles refresh automatically

---

## Debugging

### Enable Logging

The script logs to [Stackdriver Logging](https://console.cloud.google.com/logging).

1. Open your Apps Script project
2. **View → Stackdriver Logging**
3. Filter by `doPost` to see submission attempts

### Test Manually

```bash
# Test the webhook directly
curl -X POST "https://script.google.com/macros/s/YOUR_ID/exec" \
  -H "Content-Type: application/json" \
  -d '{"tower_id":"Tower 1","date":"6/15/2026","time_of_day":"06:00","adult_swallows_in_chimney":1,"nesting_stage":"No nest","bill_use":"N/A or No","adults_flew_in":[],"swallows_near_nest":0,"awake":"Yes","notes":"test"}'
```

---

## References

- [Google Apps Script Documentation](https://developers.google.com/apps-script)
- [clasp CLI Documentation](https://developers.google.com/apps-script/guides/clasp)
- [FormApp API Reference](https://developers.google.com/apps-script/reference/forms)
- [Apps Script REST API](https://developers.google.com/apps-script/api/reference/rest)
