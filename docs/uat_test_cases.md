# DarkWing UAT — User Acceptance Test Cases

> **Purpose:** Manual end-to-end scenarios for validating DarkWing as a human operator. No unit tests, no CI — these run on a real machine against the real Google Form and a real camera video. Each case covers pre-reqs, test data, step-by-step actions, and pass/fail criteria per step.
>
> **Audience:** Tester executing without code knowledge. **Reviewer** fills in actual results. **Defects** are filed separately from this document.

---

## Setup — One-Time Machine Preparation

Before any test case, verify the machine is ready.

### Pre-requisites

| Item | How to verify |
|---|---|
| Python 3.14+ | `.venv/bin/python --version` → `3.14.x` |
| Package installed | `.venv/bin/darkwing --help` → usage text |
| Playwright Chromium | `.venv/bin/playwright install chromium` (if not run before) |
| `.env` configured | `grep DARKWING_FORM_URL .env` + `grep DARKWING_SUBMITTER_NAME .env` return values |
| API key set (agent cases only) | `grep GEMINI_API_KEY .env` or `grep OPENAI_API_KEY .env` returns a value |
| Test video file | Copy `tests/fixtures/sample_video.avi` to `~/Desktop/` |
| Test CSV (validation case) | Create at `~/Desktop/test_uat.csv` per test case instructions |

---

## TC-01: First Run — Help and Version

**Purpose:** Confirm the CLI is installed and responsive.

### Pre-requisites
- Setup steps complete.

### Test Data
None required.

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Open a terminal, activate the venv: `source .venv/bin/activate` | Prompt updates to show `(darkwing)` or similar. No error. |
| 2 | Run `darkwing --help` | Prints usage showing: `detect`, `agent`, `submit`, `validate` commands. |
| 3 | Run `darkwing --version` | Prints a version string (e.g. `0.1.0`). |

### Pass Criteria
Steps 1–3 all produce expected results. No traceback.

---

## TC-02: Validate a Clean CSV

**Purpose:** Confirm the validator accepts a well-formed CSV and rejects malformed input.

### Pre-requisites
- TC-01 complete.
- Google Form is live and accessible.

### Test Data

Create `~/Desktop/test_uat_validate.csv`:
```csv
tower,date_str,hour,minutes_past_hour,num_adults,nesting_stage,bill_use,flights,num_near_nest,awake,notes
3,6/15/2026,6,0,2,no,na,in;chg,1,y,1 north, 1 west. west moved to north
3,6/15/2026,6,20,0,no,na,non,0,nap,
```

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Run `darkwing validate ~/Desktop/test_uat_validate.csv` | `2 record(s) validated successfully.` |
| 2 | Open the Google Form in a browser. Confirm both records would map to valid dropdowns: Tower 3, 2 adults, `in;chg` flight codes, etc. | Form fields match expected values. |

### Pass Criteria
Step 1 prints the success message. Step 2 — form is accessible and field options match the CSV column expectations.

---

## TC-03: Validate Catches a Bad CSV

**Purpose:** Confirm the validator fails loudly on invalid data rather than silently submitting bad records.

### Pre-requisites
- TC-02 complete.

### Test Data

Create `~/Desktop/test_uat_bad.csv`:
```csv
tower,date_str,hour,minutes_past_hour,num_adults,nesting_stage,bill_use,flights,num_near_nest,awake,notes
3,not-a-date,6,0,2,no,na,in,1,y,
```

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Run `darkwing validate ~/Desktop/test_uat_bad.csv` | Command exits non-zero. Error output identifies `date_str` as the problem field. |
| 2 | Confirm no `.jsonl` or submission log file was created. | Working directory is clean. |

### Pass Criteria
Step 1 exits with error and describes the bad field. Step 2 — no log file exists.

---

## TC-04: Dry-Run Submission

**Purpose:** Confirm `--dry-run` submits nothing but shows the full plan.

### Pre-requisites
- TC-02 complete (clean CSV exists at `~/Desktop/test_uat_validate.csv`).
- Google Form is accessible.

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Run `darkwing submit ~/Desktop/test_uat_validate.csv --dry-run` | Output shows `2 record(s) would be submitted (dry run).` No browser opens. |
| 2 | Confirm `submitted_log.jsonl` does **not** exist in the working directory. | File absent. |
| 3 | Open the Google Form in a browser. Submit a test response manually to confirm the form is accepting responses. | Form accepts manual submission. |

### Pass Criteria
All steps produce expected results. No browser automation fired.

---

## TC-05: Full Manual Submission — Happy Path

**Purpose:** Submit a CSV end-to-end. Verify records appear in the Google Form.

### Pre-requisites
- TC-04 complete.
- A fresh Google Form (or one you can reset) so responses are identifiable.
- `DARKWING_HEADLESS=false` in `.env` so you can watch the browser.

### Test Data
Reuse `~/Desktop/test_uat_validate.csv` from TC-02.

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Run `darkwing submit ~/Desktop/test_uat_validate.csv` | A Chromium window opens. The form loads, fields are filled, form submits. Final output: `✓ 2/2 record(s) submitted.` |
| 2 | Watch the browser. Confirm it navigates to the form URL from `.env`. | Form URL matches `DARKWING_FORM_URL`. |
| 3 | Watch the browser. Confirm Tower 3, 2 adults, flight codes, and notes appear in the submitted fields. | Submitted values match CSV row 1. |
| 4 | Open the Google Form responses view. | Both records appear in the spreadsheet/response view with correct values. |
| 5 | Confirm `submitted_log.jsonl` was created in the working directory. | File exists and contains 2 JSON lines (one per record). |

### Pass Criteria
All steps produce expected results. Both records confirmed in Google Form.

---

## TC-06: Resume — Retry Failed Records

**Purpose:** When a submission partially fails, re-running the command retries only the failed rows and skips the already-submitted ones.

### Pre-requisites
- TC-05 complete (working directory has `submitted_log.jsonl` with 2 records).
- A second CSV with partially-overlapping records.

### Test Data

Create `~/Desktop/test_uat_partial.csv`:
```csv
tower,date_str,hour,minutes_past_hour,num_adults,nesting_stage,bill_use,flights,num_near_nest,awake,notes
3,6/15/2026,6,0,2,no,na,in;chg,1,y,1 north, 1 west. west moved to north
3,6/15/2026,6,20,0,no,na,non,0,nap,
3,6/15/2026,6,40,1,no,na,out,0,n,
```

Row 1 and Row 2 are duplicates of TC-05 records. Row 3 is new.

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Run `darkwing submit ~/Desktop/test_uat_partial.csv`. While it is running, disconnect the network or close the browser. Force at least one failure. | At least one record fails. Output shows `X failed. Re-run to retry the failed rows.` |
| 2 | Restore network/browser. Run `darkwing submit ~/Desktop/test_uat_partial.csv` again. | Output shows `Submitting 1 record(s)` — only the new row (Row 3) is submitted. The duplicate rows (1 and 2) are skipped silently. |
| 3 | Confirm `submitted_log.jsonl` now has 3 entries (2 from TC-05 + 1 new). | 3 lines total. |

> **Alternative (simpler):** Skip the network disruption. Run `darkwing submit` twice in succession — the second run should skip all 3 rows silently and print `0 record(s) would be submitted (no new records)` or similar.

### Pass Criteria
Step 2 — only non-duplicate rows are submitted. Step 3 — log has correct count.

---

## TC-07: Detect — Motion Detection on Test Video

**Purpose:** Confirm `detect` runs MOG2 background subtraction, groups frames into 10-minute windows, and classifies each window as SKIP / REVIEW / MANUAL.

### Pre-requisites
- Test video at `~/Desktop/sample_video.avi` (or `tests/fixtures/sample_video.avi`).
- Sufficient disk space for extracted frames (~100 MB per run).

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Run `darkwing detect ~/Desktop/sample_video.avi` | Processing runs. Output ends with a summary table showing window classifications (e.g. `N SKIP, M REVIEW, K MANUAL`). |
| 2 | Confirm `review_index.jsonl` was created in the working directory. | File exists. |
| 3 | Open `review_index.jsonl`. Count lines where `verdict` is `REVIEW`. | Count matches the REVIEW number from Step 1's output. |
| 4 | Open `review_index.jsonl`. Confirm each REVIEW entry has a `first_motion_frame` field. | All REVIEW entries have a frame index. |

### Pass Criteria
All steps produce expected results.

---

## TC-08: Agent — VLM Analysis of REVIEW Windows

**Purpose:** Confirm `agent` extracts keyframes from REVIEW windows, sends them to the configured VLM, and produces structured observation records.

### Pre-requisites
- TC-07 complete (REVIEW windows exist in `review_index.jsonl`).
- `GEMINI_API_KEY` or `OPENAI_API_KEY` set in `.env`.
- Disk space for JPEG keyframes (~10–50 MB).

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Run `darkwing agent ~/Desktop/sample_video.avi` | Agent processes each REVIEW window. Output shows progress (e.g. `Analyzing window N/N...`). |
| 2 | Watch the output. Confirm each REVIEW window is described: window time range, motion frame count, VLM call result. | Progress is visible per window. |
| 3 | Open `review_index.jsonl`. Confirm each REVIEW entry now has an `analysis` field with structured data (num_adults, nesting_stage, etc.). | Analysis data present for all REVIEW windows. |
| 4 | Open `review_index.jsonl`. Confirm each REVIEW entry has a `keyframe_paths` list pointing to JPEG files. | Keyframe files referenced and exist on disk. |
| 5 | Open one of the keyframe JPEG files. Confirm it shows a frame from the camera footage (not a blank/corrupt image). | Image opens and shows real video frame. |

### Pass Criteria
All steps produce expected results.

---

## TC-09: Agent — No API Key Handling

**Purpose:** Confirm the agent fails gracefully when no API key is configured.

### Pre-requisites
- TC-07 complete.
- **Temporarily** unset the API key in `.env` (comment out `GEMINI_API_KEY` and `OPENAI_API_KEY`).

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Run `darkwing agent ~/Desktop/sample_video.avi` | Command exits immediately with a clear error: no API key found. No VLM calls attempted. |
| 2 | Confirm `review_index.jsonl` is unchanged from TC-07 (no analysis field added to REVIEW windows). | File unchanged. |

### Cleanup
Restore the API key in `.env` after this test.

### Pass Criteria
Step 1 exits with a clear error. Step 2 — file is unmodified.

---

## TC-10: Detect-and-Submit Shortcut

**Purpose:** Confirm the end-to-end shortcut `darkwing detect-and-submit` chains detect → agent → submit without manual intervention between stages.

### Pre-requisites
- TC-07 and TC-08 pre-conditions met (video, API key).
- A clean working directory (no prior `review_index.jsonl` or `submitted_log.jsonl`).

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Run `darkwing detect-and-submit ~/Desktop/sample_video.avi` | Chained execution runs. Detection completes first, then agent, then submit. Final output shows form submission results. |
| 2 | Confirm `review_index.jsonl` exists and has analysis data. | File has both detection verdicts and VLM analysis. |
| 3 | Confirm `submitted_log.jsonl` exists and has entries. | File has submission results. |
| 4 | Open the Google Form responses. | Any new REVIEW windows analyzed by the agent appear as form submissions. |

### Pass Criteria
All steps produce expected results.

---

## TC-11: Submission Log Accuracy

**Purpose:** Confirm `submitted_log.jsonl` records only successful submissions — failed attempts must not appear.

### Pre-requisites
- TC-05 complete (`submitted_log.jsonl` exists with 2 entries).
- A CSV with at least one known-good row.

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Open `submitted_log.jsonl`. | Every line has `"status": "success"`. No `"status": "error"` lines exist. |
| 2 | Confirm each line has `timestamp`, `record`, and `error: null`. | All expected fields present. |
| 3 | Create a CSV with 1 valid row. Run `darkwing submit` with network disabled to force failure. | Output shows failure. `submitted_log.jsonl` is **not created** or remains empty. |
| 4 | Re-enable network. Run `darkwing submit` again and confirm it succeeds. | Log now has 1 new `"status": "success"` line. No error lines. |

### Pass Criteria
Steps 1–4 all produce expected results.

---

## TC-12: Headless vs. Watched Browser

**Purpose:** Confirm `DARKWING_HEADLESS=false` and `true` produce the expected behavior.

### Pre-requisites
- TC-05 pre-conditions met.

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Set `DARKWING_HEADLESS=false` in `.env`. Run `darkwing submit ~/Desktop/test_uat_validate.csv --dry-run`. | No browser opens (dry run). |
| 2 | Run `darkwing submit ~/Desktop/test_uat_validate.csv`. | Chromium window opens visibly. You can see fields being filled. |
| 3 | Set `DARKWING_HEADLESS=true` in `.env`. Run `darkwing submit ~/Desktop/test_uat_validate.csv`. | Chromium runs in background. No visible window. |
| 4 | Confirm both runs produced identical submission results in the Google Form. | Form shows records from both runs. |

### Pass Criteria
Step 2 — browser visible. Step 3 — no browser window. Step 4 — both submissions succeeded.

---

## TC-13: End-to-End — Complete Observation Session (Full Manual Path)

**Purpose:** Walk through an entire real-world session: manual observation → CSV creation → validation → submission → form confirmation.

### Pre-requisites
- A real chimney swift roost you are monitoring.
- Paper notebook or camera to record observations.
- Setup complete.

### Test Data
Real observations from the field. Minimum 3 rows.

### Steps

| # | Action | Expected Result |
|---|---|---|
| 1 | Conduct field observation. Record for each 20-minute window: tower, date/time, adult count, nesting stage, flight codes, near-nest count, awake status, notes. | Notes taken in consistent format matching CSV column names. |
| 2 | Create `~/Desktop/field_session_YYYYMMDD.csv` from your notes. | File created. Column names match schema exactly. |
| 3 | Run `darkwing validate ~/Desktop/field_session_YYYYMMDD.csv`. | All rows validated. |
| 4 | Run `darkwing submit ~/Desktop/field_session_YYYYMMDD.csv --dry-run`. | Plan shown, no browser. |
| 5 | Run `darkwing submit ~/Desktop/field_session_YYYYMMDD.csv`. | Browser opens. Records submitted. |
| 6 | Open the Google Form responses. Confirm all field observations appear with correct values. | All rows match field notes exactly. |
| 7 | File the `field_session_YYYYMMDD.csv` and `submitted_log.jsonl` in your project records. | Both files saved for audit trail. |

### Pass Criteria
All steps produce expected results.

---

## Test Case Summary

| ID | Title | Priority | Estimated Time |
|---|---|---|---|
| TC-01 | First Run — Help and Version | P0 | 2 min |
| TC-02 | Validate a Clean CSV | P0 | 5 min |
| TC-03 | Validate Catches a Bad CSV | P0 | 2 min |
| TC-04 | Dry-Run Submission | P0 | 3 min |
| TC-05 | Full Manual Submission — Happy Path | P0 | 10 min |
| TC-06 | Resume — Retry Failed Records | P1 | 10 min |
| TC-07 | Detect — Motion Detection on Test Video | P1 | 15 min |
| TC-08 | Agent — VLM Analysis of REVIEW Windows | P1 | 20 min |
| TC-09 | Agent — No API Key Handling | P1 | 2 min |
| TC-10 | Detect-and-Submit Shortcut | P2 | 25 min |
| TC-11 | Submission Log Accuracy | P1 | 5 min |
| TC-12 | Headless vs. Watched Browser | P2 | 5 min |
| TC-13 | Complete Observation Session (Full Manual) | P0 | 45 min |

**P0 = must pass before any release. P1 = must pass before MVP is considered complete. P2 = nice to have before release.**

---

## Defect Log

| Defect # | TC # | Description | Severity | Filed Date | Status |
|---|---|---|---|---|---|
| | | | | | |

---

## Sign-Off

| Role | Name | Date | Signature |
|---|---|---|---|
| Tester | | | |
| Reviewer | | | |
| Product Owner | | | |
