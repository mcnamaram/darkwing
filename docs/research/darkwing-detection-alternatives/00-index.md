# Bird Detection Research - DarkWing Project Alternatives

**SOURCES:**
- /Users/mikemcnamara/dev/darkwing/docs/detector_algorithm.md (Detector pipeline documentation)
- /Users/mikemcnamara/dev/darkwing/detect_debug_full.txt (Debug logs showing MOG2 issues)
- /Users/mikemcnamara/dev/darkwing/detect_debug_output.txt (Additional detection output)
- /Users/mikemcnamara/dev/darkwing/obs-2.csv / /Users/mikemcnamara/dev/darkwing/obs-1.csv (Observation data)
- /Users/mikemcnamara/dev/darkwing/tests/test_detector.py (Unit tests for detector)
- /Users/mikemcnamara/dev/darkwing/README.md (Project overview)
- /Users/mikemcnamara/dev/darkwing/Makefile (Build commands)
- /Users/mikemcnamara/dev/darkwing/pyproject.toml (Dependencies)

## Summary
The DarkWing bird detection system currently relies on classical computer vision (MOG2 background subtraction with shadow filtering) but faces three critical issues: 1) The threshold_foreground fallback is broken due to incorrect dark_threshold (85 vs wall brightness ~89) causing false positives, 2) MOG2 produces zero blobs in real video due to insufficient background model priming (requires 500+ frames but only runs ~60s post-first-detection), and 3) Test logic bugs skip has_bird checks. Given the operational constraints (still birds, nest vs bird discrimination, changing light patterns, 20-min windows requiring earliest detection), the optimal solution combines three approaches: (a) Fix threshold_foreground with adaptive dark thresholding based on ROI statistics, (b) Implement MOG2 background priming using pre-frame history or transfer learning from similar lighting conditions, and (c) Add template matching or Haar cascades for stationary bird detection to complement motion-based approaches. This hybrid approach addresses the core tension between motion detection (MOG2) and appearance-based detection while maintaining real-time performance.

## Analysis

### Current State & Issues
- **Detector Pipeline:** MOG2 background subtraction → shadow filtration → morphological opening → contour filtering → area-based classification (SKIP/REVIEW/MANUAL)
- **Primary Issue:** MOG2 requires extensive history (500+ frames) but detection loop only processes frames for ~60 seconds after first detection → chicken-and-egg problem
- **Secondary Issue:** threshold_foreground fallback uses fixed dark_threshold=85, but wall brightness ~89 causes entire frame to be flagged as foreground
- **Tertiary Issue:** Test pass logic breaks elif chains, skipping has_bird validation
- **Operational Reality:** Need to detect earliest bird presence in 20-min windows; birds can be still for minutes; nest resembles bird-sized blob; shadows cause false MANUAL; changing light over months

### Alternatives Evaluated
1. **Pure MOG2 Improvements:** 
   - Pros: Leverages existing pipeline, proven for motion detection
   - Cons: Still fails for stationary birds, requires history priming
   - Verdict: Necessary but insufficient alone

2. **Fixed threshold_foreground:**
   - Pros: Simple fix for dark threshold, complementary to MOG2
   - Cons: Still appearance-only, struggles with varying illumination
   - Verdict: Should fix but needs combination

3. **Template Matching/Haar Cascades:**
   - Pros: Detects stationary birds, works without extensive history
   - Cons: Requires training data, may false positive on nest/shadows
   - Verdict: Strong complement for stationary detection

4. **Background Model Transfer:**
   - Pros: Pre-train MOG2 on similar lighting, reduce priming time
   - Cons: Requires storing/loading models, may not adapt to day-to-day changes
   - Verdict: Viable with daily adaptation

5. **Optical Flow + Appearance:**
   - Pros: Detects subtle motion, works with still birds via texture
   - Cons: Computationally heavier, parameter tuning complex
   - Verdict: Good but may overcomplicate

### Recommended Hybrid Approach
**Short-term (Immediate Fix):**
1. Fix threshold_foreground: Replace fixed dark_threshold=85 with adaptive threshold using ROI mean/std (e.g., mean - 1.5*std)
2. Improve MOG2 priming: Pre-process first 30 seconds of video to build background model before detection loop
3. Add temporal smoothing: Require detection in 2+ consecutive frames to reduce noise

**Medium-term (Robust Solution):**
1. Add template matching: Create swift templates from verified detections, match using normalized cross-correlation
2. Implement appearance-based detection: Use simple CNN or HOG features for bird vs nest classification
3. Adaptive thresholding: Dynamically adjust BIRD_MIN_AREA based on recent blob statistics
4. Shadow-aware classification: Use MOG2 shadow mask to reject detections occurring primarily in shadow regions

**Long-term (Learning-Based):**
1. Collect labeled dataset of swift vs nest vs shadow vs glare
2. Train lightweight classifier (MobileNetV3 or EfficientDet-Lite) for frame-level classification
3. Use detector as region proposal network, classifier for final decision

This hybrid approach leverages motion detection for active birds, appearance/template matching for stationary birds, and adaptive thresholding to handle changing conditions while maintaining the real-time performance requirements of the existing pipeline.
