# Tutorial 2: Automated Detection & VLM Pipeline

This tutorial walks through the full automated pipeline: motion detection (MVP2) → VLM analysis of `REVIEW` windows (MVP3) → form submission.

By the end, you will have processed a camera video file into structured observation records submitted to the Google Form.

## Prerequisites

You have followed [Setup](./setup.md) and have:

- An active `.venv` with the package installed (`pip install -e ".[dev]"`).
- A `.env` file with `DARKWING_FORM_URL`, `DARKWING_SUBMITTER_NAME`, and an API key (`GEMINI_API_KEY` or `OPENAI_API_KEY`).
- Playwright browsers installed (`playwright install chromium`).
- A local camera video file (MP4 or AVI) on your machine.
- The tower number and observation date for the footage.

## 1. Run detection

```bash
.venv/bin/darkwing detect --date 06/15/2026 --tower 3 --source local --source-path ~/Desktop/my_camera_footage.mp4
```

Required flags:

| Flag | Value | Example |
|---|---|---|
| `--date` | Date in `MM/DD/YYYY` | `--date 06/15/2026` |
| `--tower` | Tower identifier (1–4) | `--tower 3` |
| `--source-path` | Path to your video file | `--source-path ~/Desktop/my_camera_footage.mp4` |

Optional flags:

| Flag | Default | Description |
|---|---|---|
| `--source` | `local` | Frame source kind. Use `local` for MP4/AVI files. |
| `--sample-every` | `25` | Process every Nth frame (25 ≈ 1 fps on a 25 fps camera). Increase for faster processing, decrease for higher sensitivity. |
| `--fps` | auto-detected | Override the detected FPS if timestamp derivation is wrong. |
| `--hours` `H1 H2` | all hours | Process only between hours H1 and H2, e.g. `--hours 6 21` to skip daytime. |
| `--glare-hours` `H1 H2 ...` | `11 12 13` | Hours to force a `MANUAL` verdict (direct sun causes false positives). |
| `--out-dir` | `footage` | Directory where `review_index.jsonl` and keyframes are written. |

This runs MOG2 background-subtraction on the video, grouping frames into 10-minute observation windows. Each window is classified:

- `SKIP` — no motion detected (safe to ignore).
- `REVIEW` — motion matching bird criteria (queued for VLM analysis).
- `MANUAL` — high-glare/unreliable (flagged for human review).

Expected output:

```
Processing ~/Desktop/my_camera_footage.mp4...
  SKIP=12  REVIEW=3  MANUAL=1
Review index -> footage/review_index.jsonl
```

## 2. Analyze `REVIEW` windows with VLM

The agent is invoked with the `--agent` flag on the same `detect` command. Run it again on the same footage:

```bash
.venv/bin/darkwing detect --date 06/15/2026 --tower 3 --source local --source-path ~/Desktop/my_camera_footage.mp4 --agent
```

This re-reads `review_index.jsonl` and processes every `REVIEW` window that does not yet have an `analysis` field:

1. Extracts up to 15 JPEG keyframes at 1 fps (60-second span around the first detected motion frame).
2. Sends the keyframes to the configured VLM (Gemini or OpenAI).
3. Receives a structured `ObservationRecord` proposal (adult count, nesting stage, flight codes, etc.).
4. Writes the analysis back into `review_index.jsonl` alongside the detection result.

If no API key is set, this command exits with a clear error before making any VLM calls.

Expected output:

```
Analyzing window 1/3 (06:00–06:10)...
  num_adults=2, flights=in;out, nesting=no, confidence=high
Analyzing window 2/3 (06:20–06:30)...
  num_adults=0, flights=non, nesting=no, confidence=high
...
  SKIP=12  REVIEW=3  MANUAL=1
Review index -> footage/review_index.jsonl
```

## 3. Review the generated records

Open `footage/review_index.jsonl`. Each analyzed `REVIEW` window has this structure:

```json
{
  "verdict": "REVIEW",
  "first_motion_frame": 542,
  "analysis": {
    "num_adults": 2,
    "nesting_stage": "no",
    "flights": "in;out",
    "num_near_nest": 1,
    "awake": "y",
    "notes": "Two adults circling above the chimney..."
  },
  "keyframe_paths": [
    "footage/frames/window_0001_000542.jpg",
    "footage/frames/window_0001_000567.jpg"
  ],
  "confidence": "high",
  "raw_vlm_response": "..."
}
```

**You are responsible for reviewing and approving the VLM's interpretation before submission.** Adjust `num_adults`, `nesting_stage`, `notes`, or any other field by editing this JSON directly.

## 4. Export analyzed records to a submission-ready CSV

```bash
.venv/bin/darkwing agent ~/Desktop/my_camera_footage.mp4
```

This reads `review_index.jsonl`, extracts all `REVIEW` entries that have an `analysis` field, and writes a CSV to `footage/generated_observations.csv` with one row per window. The CSV uses the exact column schema DarkWing expects for submission.

Expected output:

```
Exported 3 observation(s) to footage/generated_observations.csv
```

## 5. Submit the generated records

```bash
.venv/bin/darkwing submit footage/generated_observations.csv
```

The generated CSV is validated and submitted to the Google Form. The submission log (`submitted_log.jsonl`) ensures resumability — if the submission is interrupted, re-running picks up where it left off.

Expected output:

```
Submitting 3 record(s) to the form...
✓ 3/3 record(s) submitted.
```

## 6. End-to-end shortcut

All three steps (detect → agent → submit) can be chained with `--agent` and `--submit`:

```bash
.venv/bin/darkwing detect --date 06/15/2026 --tower 3 --source local --source-path ~/Desktop/my_camera_footage.mp4 --agent --submit
```

> **Important:** This shortcut submits automatically without human review of the VLM output. Review the `review_index.jsonl` before using `--submit` to ensure the agent's interpretations are accurate.

## What to do with MANUAL windows

Windows classified as `MANUAL` are excluded from VLM analysis. They are listed in `review_index.jsonl` but need one of two actions:

1. **Watch the footage segment manually.** If chimney swifts are present, create a CSV row by hand and submit it.
2. **If no swifts were present**, no action is needed — the window is already excluded from submission.

## Common Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| `REVIEW=0` on a video you know has birds | `--sample-every` too high, or dawn/dusk lighting | Lower `--sample-every` to 10 or 15 |
| `MANUAL=many` during midday | Direct sunlight causes MOG2 false positives | Use `--glare-hours 10 11 12 13 14` |
| Agent exits with "no API key" | `GEMINI_API_KEY` or `OPENAI_API_KEY` not in `.env` | Add the key to `.env` and source it |
| CSV has wrong time stamps | FPS not auto-detected correctly | Pass `--fps 30` (or actual camera fps) |
