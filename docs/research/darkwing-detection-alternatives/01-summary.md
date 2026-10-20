# DarkWing Bird Detection - Research Report

## Overview
Analysis of the DarkWing project's bird detection system reveals three critical issues affecting Swift bird monitoring:

1. **Threshold Foreground Fallback Broken** – Fixed dark_threshold=85 incorrectly flags walls (~89 brightness) as foreground, producing massive false-positive blobs.
2. **MOG2 Produces No Blobs for Real Video** – The background model lacks sufficient priming (needs 500+ frames) but the detection loop only runs ~60 seconds after first detection, creating a chicken-and-egg problem.
3. **Core Tension** – MOG2 requires extensive history priming that conflicts with the rapid detection loop, while threshold_foreground and test logic bugs compound the reliability issues.

## Key Challenges
- **Still birds** (huddled swifts) are invisible to motion-based MOG2
- **Nest vs bird** confusion – nests are bird-sized but should be excluded
- **Shadow sweeps** cause false MANUAL classifications
- **Changing light patterns** (day/night cycles, weather) affect detection consistency
- **20-minute window constraint** – need earliest bird detection, not exhaustive scanning
- **Real-time requirement** – cannot afford lengthy background modeling

## Recommendations

### Immediate Fixes (High Priority)
1. **Fix threshold_foreground** – Replace fixed dark_threshold=85 with adaptive threshold based on ROI mean/std deviation. This prevents false positives from bright walls.
2. **Improve MOG2 priming** – Pre-compute background model from the first 30 seconds of each video before entering the detection loop. This reduces the chicken-and-egg problem.
3. **Correct test logic** – Fix elif chain breaks in has_bird validation to ensure proper test coverage.

### Medium-Term Enhancements (Medium Priority)
1. **Hybrid detection strategy** – Combine MOG2 (motion) with template matching (appearance) for stationary birds.
2. **Adaptive area thresholds** – Dynamically adjust BIRD_MIN_AREA based on recent blob statistics to handle varying lighting.
3. **Shadow-aware classification** – Use MOG2 shadow masks to filter out detections occurring primarily in shadow regions.

### Long-Term Solution (Low Priority)
1. **Lightweight classifier** – Train a MobileNetV3 or EfficientDet-Lite model for bird vs nest vs shadow classification.
2. **Daily model adaptation** – Continually refine background models with new footage to handle seasonal/lighting changes.

## Conclusion
The current system is fundamentally limited by its reliance on a single motion-based detector (MOG2) with inadequate background priming. A hybrid approach combining adaptive thresholding, pre-trained background models, and appearance-based detection will provide the reliability needed for continuous Swift monitoring while respecting the real-time constraints of the 20-minute window.
