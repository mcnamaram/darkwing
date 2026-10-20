# Tutorial 2: Automated Detection & VLM Pipeline

This tutorial walks through the full automated pipeline: motion detection (MVP2) → VLM analysis of `REVIEW` windows (MVP3) → form submission.

By the end, you will have processed a camera video file into structured observation records submitted to the Google Form.

## Prerequisites

You have followed [Setup](./setup.md) and have:

- An active `.venv` with the package installed (`pip install -e ".[dev]"`).
- A `.env` file with `VLM_BASE_URL`, `VLM_MODEL`, `VLM_API_KEY`, and `VLM_PROVIDER` for VLM analysis.
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
| `--hours` `H1 H2` | all hours | Process only between hours H1 and H2, e.g. `--hours 19 19` for evening only. |
| `--out-dir` | `footage` | Directory where `review_index.jsonl` is written. |

This runs MOG2 background-subtraction on the video, grouping frames into 20-minute observation windows. Each window is classified:

- `SKIP` — no motion detected (safe to ignore).
- `REVIEW` — motion matching bird criteria (queued for VLM analysis).
- `MANUAL` — high-glare/unreliable (flagged for human review).

**Smart sampling:** The CLI automatically detects the video's native fps and samples at 2fps for high-speed footage (≥10fps) or 1fps for slower footage — no manual tuning required.

**Backfill detection:** For `REVIEW` windows, the system scans backward from the MOG2 detection time using a dark-threshold fallback (immune to MOG2 adaptation artifacts) to refine the first-detection timestamp. This fixes timing gaps such as the 4-second delay at 19:47:13 vs the bird's actual appearance at 19:47:09.

Expected output:

```
Starting frame loop: sample_every=5, offset=+6s, clip_start_hour=19, cutoff=1140s
[WINDOW REACHED] T3_06262026_1900 frame=2280 real_ts=3600.0s
[FIRST BIRD DETECTED] Window T3_06262026_1900: ts=19.0s, blobs=1, max_area=3152
...
[BACKFILL] Window T3_06262026_1940: refined first detection 19:47:09
[AI PROPOSAL] Window T3_06262026_1940: AI observation generated
Review index -> footage/06/26/2026/tower3/review_index.jsonl
  SKIP=12  REVIEW=3  MANUAL=1
```

## 2. VLM analysis (automatic)

When `VLM_PROVIDER` is set in your environment, `REVIEW` windows automatically get VLM analysis during detection. The VLM receives:

1. Up to 15 JPEG keyframes extracted over a **120-second span** (1 minute before + 1 minute after the refined first detection).
2. Context metadata (tower, date, hour, minute).
3. An optimized prompt for the gemma4:12b model that handles fast bird movements.

Each analyzed window gets an `ai_observation` field in the `review_index.jsonl`:

```json
{
  "ai_observation": {
    "tower": 3,
    "date_str": "06/26/2026",
    "hour": 19,
    "minutes_past_hour": 40,
    "num_adults": 1,
    "nesting_stage": "nst",
    "bill_use": ["na"],
    "flights": ["in"],
    "num_near_nest": 0,
    "awake": "y",
    "notes": null
  }
}
```

## 3. Review the generated records

Open `footage/06/26/2026/tower3/review_index.jsonl`. The review index contains one JSON object per observation window:

```json
{
  "window_id": "T3_06262026_1940",
  "tower": 3,
  "date": "06/26/2026",
  "hour": 19,
  "minute": 40,
  "verdict": "review",
  "first_detection_ts": 2829.5,
  "first_detection_wallclock": "19:47:09",
  "max_blob_area": 2096,
  "sample_count": 20,
  "spot_check_due": true,
  "detector_version": "detector-v1",
  "glare_reason": ""
}
```

**You are responsible for reviewing and approving the VLM's interpretation before submission.** Verify the detection time, adult count, flights, and nesting stage.

## 4. Export and submit

Generate a CSV from the reviewed observations:

```bash
.venv/bin/darkwing validate observations.csv   # check your own CSV
.venv/bin/darkwing submit observations.csv --dry-run  # verify without submitting
.venv/bin/darkwing submit observations.csv      # submit for real (opens browser)
```

## Common Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| `REVIEW=0` on a video you know has birds | No birds in the specified `--hours` range | Check hours; birds may be outside the range |
| `MANUAL=many` during midday | Sun/glare creates large shadow blobs, exceeding 6000px² threshold | Review the flagged windows in the review index |
| VLM analysis fails | API endpoint or model misconfigured | Verify `.env` has correct `VLM_BASE_URL`, `VLM_MODEL`, `VLM_API_KEY`, `VLM_PROVIDER` |
| `first_detection_ts` is 4s late | MOG2 adaptation delay | Already handled: backfill detection refines the timestamp automatically |
