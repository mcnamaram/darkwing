# DarkWing MVP3: Payload Extraction Detailed Technical Spec

This document defines the exact architecture, data structures, and algorithms for extracting visual payload keyframes from motion-reviewed windows to supply to the VLM Agent.

## 1. Objectives

- Minimize VLM cost and latency by aggressively reducing the frame rate of active motion segments to **1 FPS**, capped at **15 keyframes max per 20-minute window**.
- Ensure reliable frame retrieval from local video sources without flaky seek operations.
- Avoid memory bloat by performing a lazy second-pass extraction on `REVIEW` windows only.
- Downscale frames to a lightweight resolution (~640x360, preserving aspect ratio) and convert to highly compressed JPEG bytes.

## 2. API Signature & Location

The code lives in `src/darkwing/agent_payload.py`:

```python
from pathlib import Path
from typing import List, Tuple
from darkwing.detector import FrameResult

def extract_motion_frames(
    source_path: Path,
    frame_results: List[FrameResult],
    fps: float,
    first_detection_ts: Optional[float] = None,
    max_frames: int = 15,
    target_width: int = 640,
) -> List[bytes]:
    """
    Extracts up to `max_frames` keyframes as JPEG bytes from `source_path` 
    matching motion intervals in `frame_results`.
    """
```

## 3. Detailed Algorithmic Steps

### Step A: Identify Motion Intervals (Episodes)

**Constraint (REQ-7):** We ONLY care about a 60-second observation span starting at `first_detection_ts`.
To convert isolated frame hits into robust temporal intervals, we use **Interval Union Merging**:

1. Filter `FrameResult`s where `start_ts <= fr.ts_sec <= start_ts + 60.0`, where `start_ts = first_detection_ts` (or window start if `first_detection_ts` is None).
2. For the filtered `FrameResult`s with motion, define interval $I = [t - 2.0, t + 2.0]$.
3. Merge overlapping/contiguous intervals within this 60s window.
4. The output is the merged active motion episode(s) *within* that 60s span.

### Step B: Generate Candidate Keyframe Timestamps

Within each merged episode $(start_i, end_i)$, we want to sample at **1 FPS**:

1. For each episode, generate target timestamps $T_{candidate} = \{start_i, start_i + 1.0, start_i + 2.0, \dots\}$ until $\ge end_i$.
2. Combine all candidates from all episodes into a single sorted list $T_{all}$.

### Step C: Uniformly Downsample to `max_frames` Limit

If the size of $T_{all}$ exceeds `max_frames` (15):

1. Compute a step size $k = \text{len}(T_{all}) / \text{max\_frames}$.
2. Select indices using a systematic floating-point stride to maximize temporal spread:
   - $\text{selected} = [T_{all}[\text{int}(i \times k)] \text{ for } i \in [0, \dots, \text{max\_frames}-1]]$.
3. If $T_{all} \le 15$, we keep all candidate timestamps.

### Step D: Extract & Downscale Target Frames

To prevent flaky OpenCV seeks, we perform a single sequential read pass over the video file:

1. Convert each selected target timestamp $ts$ into its absolute frame index: $idx = \text{round}(ts \times fps)$. Store these as a set of target frame indices.
2. Open the video file using standard OpenCV `VideoCapture` or `LocalVideoSource`.
3. Loop through frames sequentially. Keep a counter of the current frame index.
4. If the current index is in the target set:
   - Preserve aspect ratio: calculate new height $H_{target} = \text{round}(H_{orig} \times (W_{target} / W_{orig}))$.
   - Resize frame using `cv2.resize(frame, (W_{target}, H_{target}), interpolation=cv2.INTER_AREA)`.
   - Encode to JPEG: `_, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])`.
   - Append `buf.tobytes()` to the output list.
5. Stop early if all target frames have been extracted.
6. Return `List[bytes]`.

## 4. Verification & Edge Cases

- **No Motion**: If `frame_results` has no motion frames, immediately return an empty list `[]`.
- **Short Clip**: If a motion episode starts near 0 or ends near clip limit, clamp times to $[0, \text{total\_duration}]$.
- **Aspect Ratio Safeguard**: Ensures non-standard video streams are resized cleanly without distortion.
- **Unit Testing**: Verified in `tests/test_payload.py` using synthetic clips to assert exact interval merging/sampling properties.
