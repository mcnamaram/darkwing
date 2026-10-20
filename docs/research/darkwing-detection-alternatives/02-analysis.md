## 1. Threshold Foreground Fallback (Broken)

**Problem:** `threshold_foreground()` uses `dark_threshold=85`, but the wall in the footage has mean brightness ~89. This causes the entire wall to be flagged as "dark foreground," resulting in huge blobs covering the entire frame.

**Root Cause:** The hardcoded threshold does not account for variable scene brightness. When the wall brightness is slightly higher than the threshold, the entire wall is considered foreground.

**Impact:** Massive false-positive blobs that overwhelm the detection pipeline and consume CPU cycles.

**Proposed Fix:** Replace the fixed threshold with an adaptive threshold based on ROI statistics:
- Compute the mean and standard deviation of the ROI (tower area)
- Set threshold = mean - 1.5 × std (or a similar adaptive formula)
- This adapts to changing lighting conditions while still filtering out bright backgrounds

**Implementation Location:** `darkwing/detector.py` in the `threshold_foreground()` method.

## 2. MOG2 Produces No Blobs for Real Video

**Problem:** At every sample in real videos, MOG2 reports `contours=0 kept=00`. The detector isn't reliably catching birds that are still or partially obscured by the nest.

**Root Causes:**
1. **Insufficient background priming** – MOG2 needs 500+ frames of history to establish a reliable background model, but the detection loop only runs ~60 seconds after the first detection.
2. **Static background model** – The model is built from the beginning of the video, not adapted to the specific lighting conditions of each recording.
3. **Motion-only approach** – MOG2 is inherently motion-based; it struggles with stationary birds (huddled swifts) and partially occluded subjects.

**Proposed Fixes:**
1. **Pre-prime MOG2** – Build the background model from the first 30 seconds of each video before entering the detection loop. This ensures the model captures the specific lighting and scene characteristics.
2. **Increase priming buffer** – Allow the detection loop to run longer initially (e.g., 60 seconds) before switching to active detection, giving MOG2 time to stabilize.
3. **Combine with appearance-based detection** – Use template matching or HOG features for stationary birds to complement MOG2's motion detection.

**Implementation Locations:** `darkwing/detector.py` (MOG2 initialization), `darkwing/windows/` (window-level processing timing).

## 3. Core Tension: Chicken-and-Egg Problem

**Problem:** MOG2 needs a trained background model (500+ frames of history) before it works, but the detection loop only calls `process_frame` for ~60 seconds around the first detection. This creates a circular dependency.

**Root Cause:** The detection pipeline assumes the background model is already trained, but the model training requires observing the video long enough for MOG2 to converge.

**Proposed Solutions:**
1. **Two-stage warm-up** – Run a dedicated warm-up phase (first 30-60 seconds) where MOG2 builds its model without active detection. Once the model stabilizes, switch to active detection.
2. **Transfer learning** – Pre-train MOG2 on a diverse set of chimney swift footage (similar lighting, nesting behaviors) and fine-tune on the specific project videos.
3. **Hybrid approach** – Use a lightweight motion detector (e.g., optical flow) to identify potential bird locations first, then apply MOG2 only to those regions.

## 4. Additional Observations

### Shadow Sweep Problem
- At 0620/0640 in the 06/26 video, birds are missed because MOG2 cannot distinguish between birds and shadow sweeps.
- **Solution:** Use MOG2's shadow mask (`detectShadows=True`) combined with area filtering and temporal smoothing to avoid false negatives.

### Nest vs Bird Confusion
- Nests are roughly bird-sized but should be excluded from detection.
- **Solution:** Add a size filter (BIRD_MIN_AREA ≥ 400 px²) and consider morphological properties (circularity, aspect ratio) to differentiate nests from birds.

### Changing Light Patterns
- Videos span 06/15-2026 to 10/03/2026, with daylight transitions.
- **Solution:** Dynamic threshold adjustment based on scene statistics, plus daily model adaptation to handle gradual lighting changes.

### 20-Minute Window Constraint
- Need to detect the earliest bird presence within a 20-minute window.
- **Solution:** Once a bird is detected, record the first timestamp and stop processing the remainder of the window (as per current `classify_window()` logic).

## Summary of Recommendations

| Priority | Issue | Fix |
|----------|-------|------|
| Critical | Threshold foreground fallback | Adaptive threshold based on ROI stats |
| Critical | MOG2 no blobs | Pre-prime background model (first 30s) + longer warm-up |
| High | Chicken-and-egg priming | Two-stage warm-up or transfer learning |
| Medium | Shadow sweeps | Use shadow mask + temporal smoothing |
| Medium | Nest vs bird confusion | Size filter + morphological feature filtering |
| Low | Long-term robustness | Lightweight classifier (MobileNetV3) + daily model adaptation |
