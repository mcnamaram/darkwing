# API Reference

> Last updated: 2026-08-15. Python API for the `darkwing` package.

## Package layout

```sh
darkwing/
├── __init__.py
├── agent.py             # VLM agent REST client (Gemini/OpenAI)
├── agent_payload.py    # keyframe extraction for REVIEW windows
├── cli.py              # command-line entry points
├── csv_io.py           # CSV and log I/O
├── detector.py         # MOG2 bg-sub motion detection
├── frames.py           # video frame source abstraction
├── windows.py          # observation window grouping & state
├── form_submit.py      # Playwright browser automation
└── schema.py           # Pydantic models + translation tables
```

---

## `darkwing.schema`

### Translation tables (dicts)

Used to expand CSV short codes into Google Form answer text.

```python
from darkwing.schema import (
    FLIGHTS_TRANSLATION,
    NESTING_STAGE_CODE_TO_TEXT,
    BILL_USE_CODE_TO_TEXT,
    AWAKE_CODE_TO_TEXT,
    NUM_NEAR_NEST_CODE_TO_TEXT,
)
```

| Table | Keys → Values |
| --- | --- |
| `FLIGHTS_TRANSLATION` | `in` → "Yes, at least one adult flew into the chimney", `out` → "Yes, at least one adult flew out…", `chg` → "…changed position…", `non` → "None of the above" |
| `NESTING_STAGE_CODE_TO_TEXT` | `no` → "No nest", `bld` → "Nest building", `egg` → "Egg(s) present but no nestlings", `nst` → "Nestling(s) present", `fld` → "Post-fledgling" |
| `BILL_USE_CODE_TO_TEXT` | `na` → "N/A or No", `mat` → "Yes, handling or placing a stick…", `fd` → "…feeding a bug…", `egg` → "…tending to eggs…", `nst` → "…nestling…", `ps` → "…preening itself", `po` → "…preening another adult", `oth` → "Other" |
| `NUM_NEAR_NEST_CODE_TO_TEXT` | `na` → "N/A or Zero", `oth` → "Other" |
| `AWAKE_CODE_TO_TEXT` | `y` → "Yes", `n` → "No", `mbe` → "Maybe", `nap` → "No adults present" |

### ObservationRecord (Pydantic model)

```python
from darkwing.schema import ObservationRecord

rec = ObservationRecord.model_validate({
    "tower": "3",
    "date_str": "6/15/2026",
    "hour": "6",
    "minutes_past_hour": "0",
    "num_adults": "2",
    "nesting_stage": "no",
    "bill_use": ["na"],
    "flights": "non",           # string or list of codes
    "num_near_nest": "1",
    "awake": "y",
    "notes": "test note",
})
```

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `tower` | `int` | Tower number (1-4) |
| `date_str` | `str` | `M/D/YYYY` |
| `hour` | `int` | 0-23 |
| `minutes_past_hour` | `int` | 0, 20, 40 (or 0-59) |
| `num_adults` | `int` | 0-5+ |
| `num_adults_other` | `str \| None` | "Other response" free text |
| `nesting_stage` | `str` | short code |
| `bill_use` | `list[str]` | short codes |
| `flights` | `list[str]` | short codes |
| `num_near_nest` | `int` | 0+ |
| `num_near_nest_other` | `str \| None` | — |
| `awake` | `str` | short code |
| `notes` | `str \| None` | optional |

Useful helpers:

- `rec.time_of_day` — "06:00" formatted from hour+minutes
- `rec.to_form_payload()` — dict of CSV codes (legacy; used by no current code)

---

## `darkwing/agent_payload`

```python
from darkwing.agent_payload import extract_motion_frames, DEFAULT_MAX_FRAMES, DEFAULT_TARGET_WIDTH
```

```python
jpegs: list[bytes] = extract_motion_frames(
    source_path=Path("clip.mp4"),
    frame_results=[FrameResult(...)],   # from detector.process_frame()
    fps=25.0,
    first_detection_ts=12.0,             # or None to auto-detect
    max_frames=15,
    target_width=640,
)
```

- Returns up to `max_frames` JPEG-encoded keyframes at 1 FPS covering the 60-second observation span starting at `first_detection_ts`.
- Frames are downscaled to `target_width` wide, preserving aspect ratio.
- Interval merging pads motion bursts by ±2s; contiguous/overlapping episodes merge into a single span.
- If no motion is found, returns `[]`.

---

## `darkwing/agent`

```python
from darkwing.agent import AIObservationAgent

agent = AIObservationAgent()   # reads GEMINI_API_KEY or OPENAI_API_KEY
rec = agent.propose_observation(jpeg_frames: list[bytes], context_metadata: dict)
```

- `propose_observation` is `async` — call with `asyncio.run()` or from an async context.
- Returns an `ObservationRecord` validated against the Pydantic schema.
- Provider auto-selected from env: `GEMINI_API_KEY` → Gemini, `OPENAI_API_KEY` → OpenAI.
- Gemini enforces JSON schema on response; OpenAI uses `response_format=json_schema`.

---

## `darkwing/detector`

```python
from darkwing.detector import process_frame, classify_window, WindowResult, FrameResult
```

```python
# Per-frame
result: FrameResult = process_frame(frame, frame_idx, fps, roi_mask)

# Per-window (after processing all frames in a window)
classification: WindowResult = classify_window(frame_results, window, glare_hours, version="v1")
# classification.verdict in {"skip", "review", "manual"}
```

---

## `darkwing/frames`

```python
from darkwing.frames import LocalVideoSource

with LocalVideoSource(Path("clip.mp4")) as src:
    for frame, idx, ts_sec in src:
        ...
```

- `LocalVideoSource` wraps `cv2.VideoCapture`, auto-detects FPS, handles zero-duration clips.
- All frame sources implement the same `__iter__` protocol for detector testing.

---

## `darkwing/windows`

```python
from darkwing.windows import build_windows, read_review_index, append_review_window
```

```python
windows = build_windows(Path("clip.mp4"), fps, hours=[6, 7, 8])
review_index = read_review_index(Path("review_index.jsonl"))
append_review_window(Path("review_index.jsonl"), window, window_result)
```

---

## `darkwing/csv_io`

```python
from darkwing.csv_io import (
    read_csv,
    write_submission_log,
    get_submission_log,
    load_completed_keys,
)

records = read_csv(Path("observations.csv"))       # -> list[ObservationRecord]
write_submission_log(results, log_path)            # -> appends JSONL
entries = get_submission_log(log_path)             # -> list[dict]
done_keys = load_completed_keys(log_path)          # -> set[str] of submitted keys
```

- `read_csv(path)` — parses CSV, validates each row, returns records. Raises on bad rows.
- `write_submission_log(results, log_path=...)` — appends ONE JSON line per SUCCESSFUL result only (`status == 'success'`). Failed/error results are silently skipped. Takes the results list returned by `submit_csv_records()`. Creates the file if it doesn't exist; appends if it does. Does nothing if no successful records are present.
- `get_submission_log(log_path)` — reads the log back into a list of dicts.
- `load_completed_keys(log_path)` — identity keys (`tower|date|time_of_day`) of records logged as `"success"`. Malformed lines are ignored. Used by the CLI's resume filter.

---

## `darkwing/form_submit`

```python
from darkwing.form_submit import submit_csv_records

results = asyncio.run(submit_csv_records(records, dry_run=True))
# or, from the CLI:
#   darkwing submit obs.csv --dry-run
```

### `submit_csv_records(records, dry_run=False) -> list[dict]`

Submit a list of records. Returns one dict per record:

```python
{
    "record": ObservationRecord,
    "status": "success" | "dry-run" | "error",
    "error": None | str,
}
```

`dry_run=True` never launches a browser.

### `load_form() -> (playwright, context)`

Launches Chromium with a **persistent context**:

- profile dir: `google_profile/` (project root)
- user agent: Chrome/126 macOS
- anti-bot: `--disable-blink-features=AutomationControlled`, `--enable-automation` removed
- `slow_mo=500`
- headless from `DARKWING_HEADLESS` (default `true`)

### `unload_form(p, context)`

Closes the context and stops Playwright. Call in a `finally` block.

### `submit_observation(...) -> bool`

Low-level: fill one record into an already-open page. Returns `True` on success. Parameters mirror `ObservationRecord` fields (expanded text via translation tables).

---

## `darkwing/cli`

```sh
darkwing validate <csv>
darkwing submit   <csv> [--dry-run] [--no-resume]
```

| Command | Exit codes |
| --- | --- |
| `validate` | 0 = valid, 1 = errors |
| `submit` | 0 = all records ok (or nothing left after resume), 1 = any record failed or fatal error |

`submit` appends every attempt to `submitted_log.jsonl` in the working directory and skips already-submitted rows by default (`--no-resume` to disable).
