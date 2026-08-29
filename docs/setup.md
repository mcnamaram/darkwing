# Setup Guide

## Prerequisites

- Python 3.14 or newer.
- A Google account with access to the Google Form.
- A local clone of this repository.

## 1. Clone and create a virtual environment

```bash
git clone https://github.com/mcnamaram/darkwing.git
cd darkwing
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Verify the install:

```bash
.venv/bin/python -c "import pydantic, playwright; print('ok')"
.venv/bin/pytest --collect-only
```

The second command should report 125 tests collected.

## 2. Install Playwright browsers

```bash
.venv/bin/playwright install chromium
```

## 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set:

```bash
DARKWING_FORM_URL="https://docs.google.com/forms/d/e/YOUR_FORM_ID/viewform"
DARKWING_SUBMITTER_NAME="Your Name"
DARKWING_HEADLESS=true  # set to "false" to watch the browser
```

## 4. Verify

```bash
darkwing validate tests/fixtures/sample_observation.csv
```

Expected: `4 record(s) validated successfully.`
