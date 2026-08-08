# Setup Guide

## Prerequisites

- Python 3.14 or newer.
- A Google account with access to the Google Form and the Google Apps Script deployment.
- The `gcloud` CLI installed.
- A local clone of this repository.

## 1. Clone and create a virtual environment

```bash
git clone https://github.com/mcnamaram/darkwing.git
cd darkwing
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Verify the install:

```bash
.venv/bin/python -c "import pydantic, requests; print('ok')"
.venv/bin/pytest --collect-only
```

The second command should report 92 tests collected. If it reports `errors during collection`, your `src/darkwing/` package is not on the Python path — re-check that you are in the repo root and that the `src/` directory contains a `darkwing/` subdirectory with an `__init__.py`.

<a id="google-authentication"></a>

## 2. Google authentication

### Install the gcloud CLI

The submission flow needs a short-lived Google OAuth bearer token. The simplest path uses the `gcloud` CLI.

If you don't already have it:

- macOS: `brew install --cask google-cloud-sdk`
- Linux: see <https://cloud.google.com/sdk/docs/install>
- Windows: see <https://cloud.google.com/sdk/docs/install>

Verify with `gcloud --version`.

### Log in

```bash
gcloud auth login
```

This opens a browser window for the OAuth consent flow. The account you log in with must have access to the target Google Form and the target Apps Script deployment. A personal Gmail account is fine; the form does not need a Google Cloud project for this MVP.

### Verify the token retrieval works

```bash
gcloud auth print-access-token
```

A successful run prints a long string (the access token) and exits 0. The token is valid for 60 minutes; the package will cache it for 50 minutes and refresh on demand.

## 3. Local configuration

Create a `.env` file in the repo root:

```bash
cp .env.example .env
# Edit .env with your real values
```

Required variables:

| Variable | Purpose |
| --- | --- |
| `DARKWING_APPS_SCRIPT_URL` | The `/exec` URL of the deployed Apps Script `doPost` |
| `DARKWING_FORM_ID` | The form ID (the long string in the form's URL) |
| `DARKWING_SUBMITTER_EMAIL` | The email the form will record for each submission |
| `DARKWING_SUBMITTER_NAME` | The name the form will record for each submission |

Optional variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DARKWING_DEFAULT_TOWER` | `3` | The tower number to default to if a row's `tower` field is empty |

The `.env` file is gitignored. **Do not commit it.** See [Secrets Handling](./secrets_handling.md) for the full policy.

## 4. Run the test suite

```bash
.venv/bin/pytest -v
```

A clean install reports 92 tests passing. The test suite covers schema validation, CSV I/O, auth, submission, and the CLI.

## 5. Try a dry run

```bash
.venv/bin/darkwing submit tests/fixtures/sample_observation.csv --dry-run
```

Expected output: a list of the rows that *would* be submitted, no actual POSTs to the Apps Script, and a `submitted_log.jsonl` either not created or empty.

## 6. Run the tutorial

See [Tutorial](./tutorial-1.md) for an end-to-end smoke test that submits a real (small) CSV against the real Apps Script.
