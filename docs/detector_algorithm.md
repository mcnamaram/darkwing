# Swift Detector Pipeline & Algorithm

This document provides a comprehensive, step-by-step breakdown of how DarkWing's offline video detection pipeline works. The pipeline is designed specifically to optimize chimney swift monitoring by identifying active bird windows and eliminating empty footage scanning.

---

## High-Level Architecture: The Three-Bucket Design

To maximize reviewer efficiency while maintaining 100% scientific integrity, the detector aggregates per-frame computer vision signals into a **10-minute observation window** classified into one of three buckets:

1. **`SKIP` (Automatic Skip):** No movement matching bird criteria was detected. Safe to bypass. Saves up to **80%+** of review time in low-glare morning/evening periods.
2. **`REVIEW` (Targeted Spot-Check):** Motion matching bird size bounds was detected. The system records the first timestamp of motion so the reviewer can jump straight to it.
3. **`MANUAL` (Manual Fallback / Glare Block):** High-glare hours (such as noon solar angles) or implausibly massive movement are detected. The detector marks the window as unreliable and flags it for full manual review to prevent false-negative misses.

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

## Phase 2: Window-Level Classification (`classify_window`)

Once all sampled frames for a 10-minute window are processed, the system aggregates the metrics to assign the final verdict.

### 1. Solar Glare Detection (Deterministic)

```python
if window.hour in set(glare_hours):
    glare_reason = f"configured glare hour {window.hour}"
```

* **Why:** Empirical validation proved that noon hours (12:00–12:59) cause extreme shadow-glare sweeps across the chimney wall as the sun passes overhead. Classifying these as `SKIP` is unsafe.
* **Action:** Automatically flags the window as `MANUAL`.

### 2. Large-Blob Glare Filter (Dynamic)

```python
if fr.max_blob_area >= glare_max_area and not glare_reason:
    glare_reason = f"implausible blob area {fr.max_blob_area}px^2"
```

* **Why:** A bird flying near the tower rarely exceeds a few thousand pixels. A blob exceeding `glare_max_area` (default: 15,000 pixels) represents a camera shift, a large bird landing on the lens, or a major lighting change.
* **Action:** Automatically escalates the window to `MANUAL`.

### 3. Review vs. Skip Assignment

```python
if glare_reason:
    verdict = Verdict.MANUAL
elif has_bird:
    verdict = Verdict.REVIEW
else:
    verdict = Verdict.SKIP
```

* **`REVIEW`:** If any frame contains a valid bird-sized blob, the window is marked for review. The timestamp of the first frame with motion is captured as `first_detection_ts` so the review tool can position the playback head instantly.
* **`SKIP`:** If no glare is present and zero frames contained candidate blobs, the window is skipped.
