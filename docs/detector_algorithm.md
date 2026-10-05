# Swift Detector Pipeline & Algorithm

This document provides a comprehensive, step-by-step breakdown of how DarkWing's offline video detection pipeline works. The pipeline is designed specifically to optimize chimney swift monitoring by identifying active bird windows and eliminating empty footage scanning.

---

## High-Level Architecture: The Three-Bucket Design

To maximize reviewer efficiency while maintaining 100% scientific integrity, the detector aggregates per-frame computer vision signals into a **20-minute observation window** classified into one of three buckets:

1. **`SKIP` (Automatic Skip):** No movement matching bird criteria was detected. Safe to bypass. Saves up to **80%+** of review time.
2. **`REVIEW` (Targeted Spot-Check):** Motion matching bird size bounds was detected. The system records the first timestamp of motion so the reviewer can jump straight to it.
3. **`MANUAL` (Manual Fallback / Glare Block):** Implausibly massive movement or ambiguous-sized blobs are detected (typically from glare/shadow or tiny distant birds). The detector marks the window as unreliable and flags it for full manual review to prevent false-negative misses.

```sh
                  ┌──────────────────────┐
                  │   Input Video Frame  │
                  └──────────┬───────────┘
                             ▼
                  ┌──────────────────────┐
                  │    process_frame()   │
                  │   - ROI Mask         │
                  │   - MOG2 Bg Sub      │
                  │   - Shadow Filter    │
                  │   - Morph Open       │
                  │   - Contour Filter   │
                  └──────────┬───────────┘
                             ▼
                     [ FrameResult ]
                             │
                             ▼
                  ┌──────────────────────┐
                  │   classify_window()  │
                  └──────────┬───────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
     [ Glare/Noon? ]   [ Blobs Found? ]  [ No Blobs ]
            │                │                │
            ▼                ▼                ▼
       [ MANUAL ]        [ REVIEW ]        [ SKIP ]
```

---

## Phase 1: Per-Frame Processing (`process_frame`)

The `process_frame` method in `src/darkwing/detector.py` executes a classical computer vision pipeline using OpenCV. It is designed to be extremely fast and robust, executing without heavy machine learning dependencies.

### Step 1: Ensure Region of Interest (ROI) Mask

```python
self._ensure_roi(frame)
```

* **Why it matters:** Raw camera feeds contain extraneous details like trees blowing in the wind, horizon lines, or background foliage.
* **Mechanism:** A binary region of interest mask is computed matching the tower area. All computer vision calculations are confined to this masked area, ignoring peripheral noise.

### Step 2: Grayscale Conversion

```python
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
```

* **Why it matters:** Color is irrelevant for swift movement detection and adds unnecessary computational overhead. Grayscale simplifies the channels.

### Step 3: MOG2 Background Subtraction

```python
fg = self._fgbg.apply(gray)
```

* **Mechanism:** Uses OpenCV's Mixture of Gaussians (MOG2) algorithm (`cv2.createBackgroundSubtractorMOG2`). It models the background history of the frame over time, classifying changing pixels as foreground movement.
* **Shadow Detection:** MOG2 is configured with `detectShadows=True`. This allows it to distinguish between actual foreground objects and shadows cast on the wall.

### Step 4: Shadow Filtration

```python
shadow = (fg == 127) & (roi == 255)
real = (fg == 255) & (roi == 255)
```

* **Mechanism:** MOG2 labels background as `0`, shadows as `127`, and true moving foreground as `255`.
* **The Glare Solution:** By isolating true foreground (`fg == 255`) within the ROI, we prevent wind-driven light variations and faint shadow sweeps from being treated as birds.

### Step 5: Morphological Opening

```python
real = cv2.morphologyEx(real.astype(np.uint8), cv2.MORPH_OPEN, self._kernel)
```

* **Why it matters:** Camera noise, insects right in front of the lens, and tiny compression artifacts create single-pixel foreground noise.
* **Mechanism:** Morphological opening performs erosion followed by dilation using a structuring element (`_kernel`). This operation removes isolated, small white pixels (noise) while preserving larger, connected components (birds).

### Step 6: Contour Extraction & Area Filtering

```python
cnts, _ = cv2.findContours(real, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
```

* **Mechanism:** Extracts contours (boundaries) of the remaining foreground blobs.
* **The Size Filter:** We calculate each contour's area (`cv2.contourArea`). If the area is smaller than `min_area` (default: 250 pixels), it is discarded as negligible movement.
* **Result Payload:** Validated blobs are packaged into a `FrameResult` containing bounding boxes, maximum blob size, and foreground/shadow fractions.

---

## Phase 2: Window-Level Processing (`cmd_detect`)

The detection CLI orchestrates window-level processing by:

1. Iterating frames via `iter_frames()` (1 FPS sampling based on video fps, with time-offset alignment from OCR-extracted video start time)
2. For each 20-minute window, tracking per-window state during frame iteration:
   * **`bird_first_seen`**: Timestamp of first frame with bird detection in this window
   * **`span_end_ts`**: Set to `bird_first_seen + 60s` when first detection occurs
   * **`windows_reached`**: Set of window IDs that appeared in the video (for coverage warnings)
3. Frame collection policy:
   * **Before first detection**: Process each sampled frame for blobs; collect nothing
   * **After first detection**: Collect all frames within the 60-second observation span (`[first_detection_ts, first_detection_ts + 60s]`)
4. Cutoff logic: If no bird is detected by `WINDOW_CUTOFF_SEC` (1140 seconds = 19:00/39:00/59:00 within the hour) into the 20-minute window, sampling stops for that window. A 60-second observation span would not fit before the next window starts.
5. Post-processing: For each window, call `classify_window()` to determine the verdict.

After per-window processing, the system aggregates the metrics to assign the final verdict.

### 1. Area-Based Classification (Pure Threshold)

```python
# During per-frame processing, accumulate the maximum blob area across all
# frames in the window and set glare_reason if it exceeds glare_max_area (6000).
# Then during classification, the final verdict is determined purely by area:
#   - max_blob_area >= glare_max_area → MANUAL (implausible glare/shadow)
#   - max_blob_area >= 400   → REVIEW  (bird-sized blob)
#   - otherwise           → SKIP    (no reliable detection)
```

* **Why:** The system now uses area thresholds exclusively, eliminating the legacy distinction between "glare hours" (configuration) and "implausible blobs" (dynamic detection).

* **Action:** For reliable bird detection, the window must contain at least 20 frames. Smaller windows (e.g., end-of-clip fragments) are marked SKIP with an "insufficient samples" reason.

* **Thresholds:**
  * `glare_max_area = 6000` — blobs exceeding this are implausibly large for a bird at 640×360 resolution.
  * `BIRD_MAX_AREA = 400` — a bird-sized blob should be at least 400 pixels² (a ≈22px circle) to distinguish from noise.

* **Advantages:**
  * **Simpler logic** — removes the need for static glare-hour configuration
  * **More robust** — area thresholds work consistently across lighting conditions
  * **Better diagnostics** — distinguishing between truly large glare blobs and bird detections
  * **Deterministic behavior** — same input always produces the same verdict

### 2. Classification Logic

```python
# Three-bucket verdict assignment based on accumulated metrics
if max_blob_area >= glare_max_area:
    verdict = Verdict.MANUAL   # Glare/shadow detected
elif has_bird and len(frames) >= 20:
    verdict = Verdict.REVIEW    # Bird detected with sufficient samples
else:
    verdict = Verdict.SKIP      # Ambiguous/small/no detection
```

* **`MANUAL`:** An implausibly large blob (≥6000px²) is detected. This is typically glare, shadow, or a camera shift — the window is marked for manual review.

* **`REVIEW`:** A bird-sized blob (≥400px²) is detected and the window has enough samples (20+). The detector reliably identifies a bird and the reviewer can focus on just these verified windows.

* **`SKIP`:** No bird-sized blob or insufficient samples. If no frames are collected (video doesn't cover this window), a warning is emitted instead of SKIP.

* **Cutoff enforcement:** Even if a bird-sized blob is found, if the window has fewer than 20 frames (typical at the start or end of a clip), the verdict is SKIP to prevent false positives from incomplete data.
