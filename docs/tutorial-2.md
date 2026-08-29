# Tutorial 2: Automated Detection & VLM Pipeline

This tutorial walks through the full automated pipeline: motion detection (MVP2) → VLM analysis of `REVIEW` windows (MVP3) → form submission.

By the end, you will have processed a camera video file into structured observation records submitted to the Google Form.

## Prerequisites

You have followed [Setup](./setup.md) and have:

- An active `.venv` with the package installed (`pip install -e .[dev]`).
- A `.env` file with `DARKWING_FORM_URL`, `DARKWING_SUBMITTER_NAME`, and an API key (`GEMINI_API_KEY` or `OPENAI_API_KEY`).
- Playwright browsers installed (`playwright install chromium`).

## 1. Run detection

```bash
.venv/bin/darkwing detect ~/Desktop/my_camera_footage.mp4
```

This runs MOG2 background-subtraction on the video, grouping frames into 10-minute observation windows. Each window is classified:

- `SKIP` — no motion detected (safe to ignore)
- `REVIEW` — motion matching bird criteria (queued for VLM analysis)
- `MANUAL` — high-glare/unreliable (flagged for human review)

Results are written to `review_index.jsonl`.

## 2. Analyze `REVIEW` windows with VLM

```bash
.venv/bin/darkwing agent ~/Desktop/my_camera_footage.mp4
```

For each `REVIEW` window, the agent:

1. Extracts up to 15 keyframes at 1 FPS (60-second span around first motion).
2. Sends JPEG keyframes to the configured VLM (Gemini/OpenAI).
3. Receives a structured `ObservationRecord` proposal.
4. Appends results to `review_index.jsonl`.

If no API key is set, this command exits with an error.

## 3. Submit the generated records

```bash
.venv/bin/darkwing submit ~/Desktop/generated_observations.csv
```

The generated CSV (from `agent` output) is validated and submitted to the form like any manual CSV. The submission log (`submitted_log.jsonl`) ensures resumability.

## 4. End-to-end shortcut

```bash
.venv/bin/darkwing detect-and-submit ~/Desktop/my_camera_footage.mp4
```

Runs all three steps in sequence.

## Troubleshooting

- **Agent errors**: Verify `GEMINI_API_KEY` or `OPENAI_API_KEY` is set in `.env`.
- **No `REVIEW` windows**: The video may have no bird motion, or detection parameters need tuning (see [detector_algorithm.md](./detector_algorithm.md)).
- **Browser doesn't open**: Ensure `DARKWING_FORM_URL` is set correctly.
