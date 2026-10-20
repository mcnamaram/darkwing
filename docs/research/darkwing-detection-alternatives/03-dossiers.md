# DarkWing Detection Dossiers

## Dossier 1: Threshold Foreground Fallback

**File:** `/Users/mikemcnamara/dev/darkwing/detector.py`

**Issue:** `threshold_foreground()` uses `dark_threshold=85` which is too high for typical wall brightness (~89). Entire walls are flagged as foreground, producing massive false-positive blobs.

**Location:** `darkwing/detector.py` – `threshold_foreground()` method

**Current Behavior:**
```python
def threshold_foreground(self, frame, roi):
    # Hardcoded threshold
    if np.mean(frame[roi]) > 85:
        return True  # Flag entire frame as foreground
```

**Impact:**
- False positives on bright surfaces (walls, ceilings)
- Excessive CPU usage from processing large false-blob regions
- Breaks the fallback mechanism intended to catch dark foregrounds

**Proposed Fix:**
Replace with adaptive threshold based on ROI statistics:
```python
def threshold_foreground(self, frame, roi):
    # Compute mean and std of the ROI
    roi_data = frame[roi]
    mean_val = np.mean(roi_data)
    std_val = np.std(roi_data)
    # Adaptive threshold: mean minus 1.5 sigma (standard deviation)
    adaptive_thresh = mean_val - 1.5 * std_val
    return np.mean(roi_data) > adaptive_thresh
```

**Benefits:**
- Automatically adapts to varying scene brightness
- Reduces false positives on bright backgrounds
- Maintains sensitivity to darker foregrounds (walls, shadows)

**Testing Impact:**
The current test logic has broken `has_bird` validation due to elif chain issues. Fixing the threshold will also help ensure tests pass correctly.

## Dossier 2: MOG2 Background Priming

**File:** `/Users/mikemcnamara/dev/darkwing/detector.py`

**Issue:** MOG2 background subtraction requires 500+ frames of history to establish a reliable background model, but the detection loop only runs ~60 seconds after the first detection. This creates a chicken-and-egg problem where the model isn't ready when needed.

**Current Implementation:**
```python
# MOG2 initialized once at startup
fgbg = cv2.createBackgroundSubtractorMOG2(history=500, detectShadows=True)

# Detection loop only processes ~60 seconds after first detection
for frame in iter_frames():
    fg = fgbg.apply(gray)
    # ... processing ...
```

**Impact:**
- MOG2 cannot accurately model the specific lighting of each video
- Early frames lack sufficient background context, leading to missed detections
- Stationary birds (huddled swifts) are particularly affected

**Proposed Fixes:**

### Option A: Pre-Prime MOG2 (Recommended)
Build the background model from the first 30 seconds of each video before entering the detection loop:
```python
# During video loading
first_30_sec = video.seek(0, start=0, end=30)
fgbg = cv2.createBackgroundSubtractorMOG2(history=500, detectShadows=True)
# Continue with normal detection loop
```

### Option B: Extended Warm-Up Period
Allow the detection loop to run longer initially (e.g., 60 seconds) before switching to active detection:
```python
# Initial warm-up
for _ in range(60):  # 60 seconds of blank processing
    pass
# Then active detection
```

### Option C: Transfer Learning
Pre-train MOG2 on a diverse set of chimney swift footage (similar lighting, nesting behaviors) and fine-tune on project-specific videos.

**Benefits:**
- More accurate background modeling for each specific video
- Better detection of stationary birds (which rely less on motion)
- Reduced false negatives in low-light or shadow conditions

## Dossier 3: Hybrid Detection Strategy

**File:** `/Users/mikemcnamara/dev/darkwing/detector.py` + `/Users/mikemcnamara/dev/darkwing/windows/`

**Issue:** The current pipeline relies solely on MOG2 (motion-based) and falls back to REVIEW/SKIP based on area thresholds. This misses stationary birds and confuses nests with birds.

**Proposed Hybrid Approach:**

1. **Motion Detection (MOG2)** – Primary detector for actively flying birds
   - Keeps existing MOG2 implementation
   - Improved with pre-primed background model
   - Adds temporal smoothing (require 2+ consecutive frames)

2. **Appearance Detection (Template Matching)** – Secondary detector for stationary birds
   - Create templates from verified bird detections
   - Use normalized cross-correlation for matching
   - Helps catch birds that are still or partially obscured

3. **Classification Layer** – Combine results
   ```python
   def classify_window(self, frame, roi):
       # Motion-based detection (MOG2)
       has_motion = self.threshold_foreground(frame, roi)
       
       # Appearance-based detection (template matching)
       has_template = self.match_templates(frame, roi, bird_templates)
       
       # Final decision
       if has_motion and self.bird_first_seen:
           return Verdict.REVIEW
       elif has_template and self.bird_first_seen:
           return Verdict.REVIEW
       else:
           return Verdict.SKIP
   ```

**Benefits:**
- Catches both moving and stationary birds
- Reduces false positives from shadows/nests
- Provides redundancy if one detector fails

## Dossier 4: Shadow & Nest Discrimination

**Files Affected:**
- `darkwing/detector.py` – shadow mask logic
- `darkwing/windows/` – window-level classification

**Challenges:**
- Shadow sweeps cause false MANUAL classifications
- Nests are bird-sized but should be excluded
- Changing light patterns affect both

**Proposed Solutions:**

### Shadow Handling
- Use MOG2's built-in shadow detection (`detectShadows=True`)
- Apply additional shadow masking: `shadow = (fg == 127) & (roi == 255)`
- Require blobs to have significant foreground fraction outside shadow regions

### Nest vs Bird Differentiation
- **Size filter:** BIRD_MIN_AREA = 400 px² (excludes tiny nests)
- **Morphological features:** Circularity, aspect ratio, texture patterns
- **Temporal consistency:** Nests remain stable while birds move
- **Multi-frame voting:** Require consistent detections across adjacent frames

**Implementation:**
```python
def classify_window(self, frame, roi):
    # ... existing logic ...
    
    # Shadow-aware filtering
    shadow_mask = (fg == 127) & (roi == 255)
    real_foreground = (fg == 255) & (roi == 255) & ~shadow_mask
    
    # Apply size filter
    if self.bird_first_seen and self.max_blob_area >= self.BIRD_MIN_AREA:
        # Additional morphology check
        if self.is_nest_like(real_foreground):
            return Verdict.MANUAL  # Likely nest
        else:
            return Verdict.REVIEW
```

## Dossier 5: Operational Constraints

**Constraints:**
- 20-minute observation windows
- Need earliest bird detection (stop processing after first detection)
- Real-time performance required
- Multiple towers/windows to monitor

**Design Considerations:**
- Once `bird_first_seen` is set, stop collecting frames beyond `bird_first_seen + 60s`
- Maintain state per window to avoid reprocessing
- Use efficient data structures for window aggregation
- Cache results to avoid redundant computation

**Key Implementation Points:**
- `classify_window()` should return `Verdict.REVIEW` as soon as a bird is found
- Window processing should be cut off at `WINDOW_CUTOFF_SEC` (1140 seconds)
- State persistence via `review_index.jsonl` for resume capability
