# DarkWing Swift Detection — Deep Research Update (Nov 2026)

**Context:** This document updates the prior research in `00-index.md`, `01-summary.md`, `02-analysis.md`, `03-dossiers.md` (dated Oct 2025) with the current detector state (Nov 2026). The earlier issues (fixed dark_threshold, MOG2 priming, broken elif chains) have been addressed. The current pipeline achieves **P=0.54, R=0.70, F1=0.61, Exact=0.68** on 37 oracle windows. Remaining failures: **3 FNs** (MOG2 misses birds in 2–8 frames) and **6 FPs** (persistent static features: tower opening, wall shadows).

---

## 1. Current Pipeline Snapshot (what's already implemented)

| Component | Status | Key Parameters |
|-----------|--------|----------------|
| MOG2 background subtraction | ✅ | `history=500`, `detectShadows=True` |
| Shadow mask (fg==127) | ✅ | Used to separate `real` from `shadow` |
| Morphological opening | ✅ | `5×5` ellipse (MOG2), `3×3` (dark threshold) |
| Adaptive dark-threshold fallback | ✅ | `mean − 1.5·std` on ROI grayscale |
| Area-based classification | ✅ | `BIRD_MIN_AREA=400`, `GLARE_MAX_AREA` (config) |
| Aspect-ratio filter | ✅ | Reject if `max(w,h)/min(w,h) > 3.0` |
| Valid-bird size gate | ✅ | `area ≥ 500` |
| Stationary-blob rejection | ✅ | Centroid spread `< 8 px` across frames |
| Static-occupancy suppression | ❌ rejected | Per-pixel occupancy `> 0.30` — **tested, net negative**: FP 6→20, precision 0.54→0.26. "Persistent" FPs are moving glare sweeps (low per-pixel occupancy → survive) while perched real birds (high occupancy) are wrongly suppressed. |
| **Persistence gate** | ✅ | `min_bird_frames=2`, `min_persist_frac=0.40`, `glare_persist_frac=0.30` |
| Binary LLM bird-presence check | ✅ | Agent: `gpt-4o-mini`/`o3` for uncertain SKIP verdicts |
| ROI optimization | ✅ | Reduced border + multiplication-based build |

**Verdict logic (classify_window):**
- `max_area ≥ glare_max_area` & `large_blob_frames ≥ min_glare_persist` → **MANUAL** (glare/shadow sweep)
- `valid_bird_frames ≥ min_bird_persist` & `len(frames) ≥ 20` → **REVIEW** (bird-sized blob)
- Otherwise → **SKIP** (no candidate blobs at all)

---

## 2. Root-Cause Analysis of Remaining Failures

### 2.1 False Negatives (3 windows: v1/0800, v1/0820, v13/2100)

| Window | Oracle | Detector | Frames with Bird | Pattern |
|--------|--------|----------|------------------|---------|
| T3_06152026_0800 | REVIEW | SKIP | 2–8 (non-consecutive) | Sparse, low-contrast bird |
| T3_06152026_0820 | REVIEW | SKIP | 2–8 (non-consecutive) | Sparse, low-contrast bird |
| T3_06152026_2100 | REVIEW | SKIP | 2–8 (non-consecutive) | Sparse, low-contrast bird |

**Why MOG2 misses them:**
- Birds are dark silhouettes against a dark wall at dawn/dusk → low pixel delta
- Bird may be partially stationary (perched) for minutes → MOG2 absorbs into background
- Current persistence gate requires `0.40 × 121 ≈ 48` frames with valid bird blobs for full windows — sparse 2–8-frame detections never reach threshold
- Dark-threshold fallback triggers only when MOG2 finds **zero** blobs; if MOG2 finds *any* blob (even noise), fallback is skipped → birds in shadow-adjacent regions may not trigger dark threshold

### 2.2 False Positives (6 windows)

| Window | Oracle | Detector | Likely Cause |
|--------|--------|----------|--------------|
| v2/0920 | SKIP | REVIEW | Tower opening (structural) |
| v7/1500 | SKIP | MANUAL | Wall shadow / glare sweep |
| v8/1620 | SKIP | MANUAL | Wall shadow / glare sweep |
| v9/1700 | SKIP | REVIEW | Wall shadow |
| v9/1720 | SKIP | MANUAL | Wall shadow / glare |
| v9/1740 | SKIP | REVIEW | Wall shadow |

**Why static-occupancy + stationary-blob + persistence don't eliminate them:**
- Tower opening: structural feature that *is* static, but occupancy suppression uses a single mask built from all frames → if the opening's illumination changes across the window (e.g., sun angle), occupancy < 0.30 in some frames, survives suppression
- Wall shadows: deep sun-induced shadows at noon move slowly (minutes-scale drift). `large_blob_frames` counts frames with `max_area ≥ glare_max_area`; if the shadow blob is large and persists ≥ `min_glare_persist` (0.30 × 121 ≈ 36 frames) it triggers MANUAL correctly — *but* some shadows are smaller or intermittent, falling into REVIEW
- Stationary-blob centroid spread (8 px) is tight, but a slow-drifting shadow can exceed 8 px over 20 min → not rejected as stationary

---

## 3. Alternative Algorithms NOT Yet Tried/Rejected

> **Selection criteria:** Lightweight (stdlib + OpenCV only), no new model weights, parameter-light, address specific FN/FP modes above.

### 3.1 For Detection Sensitivity (FN reduction)

| Algorithm | Why It Helps | Integration Effort | OpenCV Availability |
|-----------|---------------|-------------------|---------------------|
| **KNN Background Subtractor** (`cv2.createBackgroundSubtractorKNN`) | Nearest-neighbor pixel history; often more sensitive to slow/partial motion than MOG2's Gaussian mixture. Different failure mode → ensemble possible. | Drop-in replacement for MOG2 init; same API | ✅ Main (`cv2.bgsegm`) |
| **Temporal Median Background** | Per-pixel median of last N frames (e.g., 30–60) as background. Robust to lighting; shadows are static → subtracted out. Birds = outliers. Deterministic, no learning rate. | New helper: maintain ring buffer of frames, compute median on-the-fly (or update incrementally). ~30 lines. | ✅ Pure NumPy |
| **Frame Differencing + Adaptive Threshold** | `|I_t − I_{t−1}| > k·σ_noise`. Birds cause sharp delta; shadows drift slowly → low delta. Complements MOG2 (which is slow-adapting). | One extra frame buffer; simple threshold. Can run in parallel to MOG2. | ✅ Pure OpenCV/NumPy |
| **MOG2 Foreground Probability Map** | MOG2 internally computes per-pixel `fgProb` (0–255) before thresholding. Thresholding `fgProb > 128` instead of binary mask recovers sub-threshold birds. | `fgbg.apply(gray, learningRate=-1)` returns fgProb map in some builds; else use `getBackgroundImage` diff. | ⚠️ Version-dependent; test first |
| **Motion History Image (MHI)** | Accumulate motion: `MHI = max(MHI−Δt, timestamp) where motion`. Bird = fresh high values; static scene = decayed. Onset detection via MHI threshold. | `cv2.motempl.updateMotionHistory` + `cv2.motempl.calcMotionGradient` | ✅ `cv2.motempl` (contrib, usually bundled) |
| **ViBe / PBAS** | Sample-based (ViBe) or pixel-based adaptive segmentation (PBAS); known robust to illumination changes. External pure-Python implementations exist (`pyvisionbg`, `vibe-bg`). | `pip install pyvisionbg` or copy ~200-line implementation. More code than OpenCV native. | ❌ External dep (but pure Python) |

**Recommendation (FN path):** **KNN + Temporal Median ensemble** — both are OpenCV-native, parameter-light, and address different failure modes. Run both in parallel; if either produces a valid bird blob, count the frame as `valid_bird_frames`. This recovers sparse detections without lowering persistence gate.

> **UPDATE (tested Nov 2026):** KNN+MOG2 union was implemented and ablated. Result was **net negative**: TP 7→4, FP 6→3, FN 3→6, F1 0.61→0.47 (exact match 0.68→0.70, but recall collapsed 0.70→0.40). KNN did not recover the sparse FN birds and cost real detections. **KNN reverted.** The remaining FN path should focus on temporal median and/or frame differencing instead, or accept the ceiling.

### 3.2 For Static-Feature False Positives (FP reduction)

| Algorithm | Why It Helps | Integration Effort |
|-----------|---------------|-------------------|
| **Chromaticity / HSV Shadow Detection** | Shadows preserve chromaticity (r=R/(R+G+B), g=G/(R+G+B)); birds are near-achromatic. Convert to HSV: shadow `V` drops, `S` ~constant; bird `V` drops, `S` may differ. Illumination-invariant color (Finlayson) separates shadow from object. | Convert frame to HSV; compute chromaticity; mask pixels where `S < thresh` AND `V < thresh` as shadow. ~20 lines. |
| **Dense Optical Flow (Farnebäck)** | Bird motion = rapid, directional, high magnitude. Shadow drift = slow, smooth, coherent field. Compute flow magnitude histogram per blob; reject blobs with median flow mag < threshold. | `cv2.calcOpticalFlowFarneback` (dense) — heavier (~30 ms/frame at 640×360). Can run on downsampled ROI only. |
| **Sparse Optical Flow (Lucas-Kanade)** | Track goodFeaturesToTrack corners; bird = clustered high-displacement tracks; shadow = sparse/slow. Lighter than dense flow. | `cv2.calcOpticalFlowPyrLK` on ROI corners. ~10 ms/frame. |
| **Per-Blob Temporal Tracking** | Current suppression is per-pixel. Track blobs across frames (IoU/centroid matching); compute per-blob `persistence = frames_present / total_frames`. Static features → persistence ≈ 1.0 but zero motion. Birds → persistence < 1.0 + motion. Reject high-persistence zero-motion blobs. | Extend `_extract_blobs_from_mask` to return tracked IDs; add Kalman/centroid tracker. ~50 lines. |
| **Blob Shape Descriptors Beyond Solidity/Aspect** | - **Perimeter-Area Ratio (PAR)** = P²/(4πA): circle=1, sticks>>1. Nest sticks = high PAR; bird = low PAR. - **Fill Factor** = A / (w×h): bird ~0.6–0.8; nest debris lower. - **Hu Moments** (7 invariants): rotation/scale/translation invariant; can train a tiny linear separator. | All from `cv2.contourArea`, `cv2.arcLength`, `cv2.boundingRect`, `cv2.HuMoments`. Zero new deps. |
| **Local Binary Pattern (LBP) / Texture** | Nest = high-frequency texture (sticks); bird silhouette = smooth. LBP histogram on blob ROI; simple threshold on uniformity. | `cv2.LBP` or custom 3×3 LBP. ~15 lines. |

**Recommendation (FP path):** **Per-blob temporal tracking + PAR + Chromaticity shadow mask** — all lightweight, address distinct FP modes (tower opening = high PAR + static; wall shadow = chromaticity signature + slow drift).

---

## 4. Hybrid Ensemble Proposal (Immediate Implementation)

Run three detectors in parallel per frame; a frame counts as `valid_bird_frame` if **any** detector produces a blob passing the existing filters (area ≥ 500, aspect ≤ 3.0, not stationary, not in static mask, not chromaticity-shadow).

```python
# detectors.py (new module)
class EnsembleDetector:
    def __init__(self, roi, min_area=400):
        self.roi = roi
        self.min_area = min_area
        # 1. MOG2 (existing)
        self.mog2 = cv2.createBackgroundSubtractorMOG2(history=500, detectShadows=True)
        # 2. KNN (new)
        self.knn = cv2.createBackgroundSubtractorKNN(history=500, detectShadows=True)
        # 3. Temporal Median (new)
        self.median_buffer = deque(maxlen=60)  # ~1 min at 1 fps
        # 4. Chromaticity shadow mask (new)
        self.chroma_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))

    def process(self, frame) -> List[Blob]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # --- Chromaticity shadow mask (applied to all detectors) ---
        shadow_mask = self._chromaticity_shadow_mask(hsv)

        # --- Detector 1: MOG2 ---
        fg_mog2 = self.mog2.apply(gray)
        real_mog2 = ((fg_mog2 == 255) & (self.roi == 255) & ~shadow_mask).astype(np.uint8) * 255

        # --- Detector 2: KNN ---
        fg_knn = self.knn.apply(gray)
        real_knn = ((fg_knn == 255) & (self.roi == 255) & ~shadow_mask).astype(np.uint8) * 255

        # --- Detector 3: Temporal Median ---
        self.median_buffer.append(gray)
        if len(self.median_buffer) >= 10:
            median_bg = np.median(np.stack(self.median_buffer), axis=0).astype(np.uint8)
            diff = cv2.absdiff(gray, median_bg)
            _, real_median = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
            real_median = (real_median & (self.roi == 255) & ~shadow_mask).astype(np.uint8) * 255
        else:
            real_median = np.zeros_like(gray, dtype=np.uint8)

        # --- Union of all foreground masks ---
        union = cv2.bitwise_or(cv2.bitwise_or(real_mog2, real_knn), real_median)
        union = cv2.morphologyEx(union, cv2.MORPH_OPEN, self.mog2_kernel)

        # --- Extract blobs + filters ---
        blobs = _extract_blobs_from_mask(union, self.min_area)
        filtered = []
        for x,y,w,h,area in blobs:
            if area < 500: continue
            if max(w,h)/max(min(w,h),1) > 3.0: continue
            if self._is_stationary(x,y): continue
            if self._in_static_mask(x,y,w,h): continue
            if self._is_chromaticity_shadow(hsv, x,y,w,h): continue
            filtered.append((x,y,w,h,area))
        return filtered
```

**Expected impact:**
- FN reduction: KNN + median catch birds MOG2 absorbs; union recovers sparse frames → `valid_bird_frames` increases without lowering persistence gate
- FP reduction: Chromaticity mask removes sun-shadow blobs; PAR filter removes stick-like tower opening; per-blob tracking removes zero-motion persistent artifacts
- Cost: ~2–3× current per-frame CPU (still < 50 ms/frame at 640×360 on modern CPU); no GPU, no weights

---

## 5. VLM Utility Assessment

### 5.1 Current VLM Integration (agent.py)

| Aspect | Status |
|--------|--------|
| **Trigger** | Uncertain SKIP verdicts (windows with 0 candidate blobs but low confidence) |
| **Model** | OpenAI-compatible: `gpt-4o-mini` (default), `o3` (optional) |
| **Prompt** | Binary bird-presence: "Is there an adult chimney swift in this keyframe? yes/no" |
| **Timeout** | 120 s (increased from 60 s) |
| **Output** | If VLM says "yes" → upgrade SKIP to REVIEW |
| **Reachability** | Requires network + API key; currently unreachable locally (offline env) |

### 5.2 Should We Rely on VLM More?

| Use Case | Verdict | Rationale |
|----------|---------|-----------|
| **Primary detector (every frame)** | ❌ No | Latency (1–5 s/call), cost ($0.15–1.50/1k images), network dependency, overkill for clear frames |
| **REVIEW/MANUAL demotion** | ✅ Wired in | VLM demotes residual FP windows (persistent static features / shadows) to SKIP. Fails closed — VLM unavailable/uncertain → keep REVIEW/MANUAL. Requires higher confidence (0.8) than promotion. |
| **Uncertain SKIP promotion** | ✅ Wired in | Phase 0: SKIP→REVIEW when VLM confirms sparse bird (catches residual FNs). Fails closed to SKIP. |
| **Adult vs juvenile / perched vs flying** | ⚠️ Future | Requires fine-grained prompt + validation; not needed for earliest-detection goal. |

**Implemented VLM policy (cli.py):**
1. **Phase 0** — SKIP→REVIEW promotion: when detector returns SKIP but collected blobs exist (uncertain detection), ask binary VLM. Promote only if `bird_present=True` AND `confidence >= 0.6`. Fails closed to SKIP.
2. **Phase 1** — REVIEW/MANUAL→SKIP demotion: when detector returns REVIEW/MANUAL but blobs exist, ask binary VLM. Demote only if `bird_present=False` AND `confidence >= 0.8` (higher bar — wrong demotion loses data). Fails closed to REVIEW/MANUAL. Wired in, inactive until `VLM_PROVIDER` is set.
3. **Batch keyframes**: 3 frames per window via `agent_payload.extract_motion_frames` (observation span).
4. **Structured output**: `BirdDetection` model `{bird_present: bool, confidence: float}` via `pydantic-ai` `NativeOutput` with output validator.
5. **Fail-closed defaults**: any exception/timeout/uncertainty keeps the classical verdict (never silently drops a detection).

**Next empirical step:** with `VLM_PROVIDER` configured, run `darkwing detect` against the 9 residual-error windows (v1/0800, v1/0820, v13/2100 FNs; v2/0920, v7/1500, v8/1620, v9/1700, v9/1720, v9/1740 FPs) and compare VLM decisions against oracle. Target: recover ≥2/3 FNs via promotion, remove ≥4/6 FPs via demotion.

### 5.3 Cost/Latency Estimates (OpenAI API, 2025 pricing)

| Model | Cost/1k images | Latency (p50) | Quality (bird detection) |
|-------|----------------|---------------|--------------------------|
| `gpt-4o-mini` | $0.15 | ~1.5 s | Good for binary presence |
| `gpt-4o` | $1.50 | ~3 s | Better at subtle/occluded |
| `o3` | $5–10 | ~10 s | Overkill |

At ~10 REVIEW windows/day × 5 keyframes = 50 calls/day → **$0.0075/day (gpt-4o-mini)** — negligible. Latency is the real constraint; batch + async.

### 5.4 Local VLM Options (offline-first)

| Model | Size (GGUF) | RAM | Speed (CPU) | License |
|-------|-------------|-----|-------------|---------|
| Moondream2 | 1.8 GB (q4) | ~2.5 GB | ~1.5 s/img | Apache-2.0 |
| LLaVA-1.5-7B | 4.5 GB (q4) | ~6 GB | ~3 s/img | Apache-2.0 |
| MiniCPM-V 2.6 | 3.2 GB (q4) | ~4 GB | ~2 s/img | Apache-2.0 |

**Recommendation:** Add Moondream2 as local fallback; use `llama-cpp-python` with `mmproj` for vision. Keep OpenAI as primary for quality; fail over to local on network error.

---

## 6. Prioritized Action Plan

| Priority | Task | Effort | Expected Δ (FN/FP) | Status |
|----------|------|--------|-------------------|--------|
| **P0** | Add KNN detector + union with MOG2 | 2–4 hrs | −2 to −3 FN | ❌ Tested, net negative (F1 0.61→0.47), reverted |
| **P0** | Add temporal median background (ring buffer) | 1–2 hrs | −1 to −2 FN | ⬜ Not started |
| **P0** | Chromaticity shadow mask (HSV) | 1–2 hrs | −2 to −3 FP | ⬜ Not started |
| **P1** | Per-blob temporal tracker (centroid + IoU) | 3–5 hrs | −1 to −2 FP | ⬜ Not started |
| **P1** | PAR / fill-factor blob filters | 1–2 hrs | −1 FP | ⬜ Not started |
| **P1** | VLM on REVIEW/MANUAL only (batch 3–5 keyframes) | ~1 hr | Human review ↓ 50–70% | ✅ Wired in |
| **P1** | Empirical VLM validation against oracle | 1–2 hrs | Confirm demotion/promotion accuracy | ⬜ Needs VLM configured |
| **P2** | Local Moondream2 fallback for VLM | 2–4 hrs | Offline capability | ⬜ Not started |
| **P2** | Sparse optical flow (LK) for motion characterization | 2–3 hrs | Additional FP/ FN signal | ⬜ Not started |

**Done this session:** Persistence gate (0.40/0.30) shipped — P 0.29→0.54, exact 0.38→0.68. VLM demotion (REVIEW/MANUAL→SKIP) wired in cli.py, fails closed, inactive until VLM_PROVIDER set. Shape metrics instrumented (diagnostic only). Static-occupancy suppression + short-burst rules + KNN ensemble all tested and rejected.

**Total remaining estimate: ~2–4 hrs for empirical VLM validation** (requires VLM_PROVIDER configured). All classical-CV tasks exhausted at plateau (F1=0.61).

---

## 7. Validation Methodology

1. **Unit tests** for each new detector component (mock frames with known blobs).
2. **Regression suite**: Re-run `scripts/evaluate_detector_accuracy.py` against the 37-window oracle after each P0/P1 change.
3. **Ablation study**: Run with `{MOG2 only}`, `{MOG2+KNN}`, `{MOG2+KNN+Median}`, `{+Chroma}`, `{+PAR}`, `{+Tracker}` to quantify marginal gains.
4. **VLM eval**: On the 6 FP + 3 FN windows, measure VLM accuracy vs oracle (requires API access).
5. **Performance gate**: Ensure per-frame latency < 100 ms (ensemble) and VLM batch < 30 s on CI hardware.

---

## 8. Appendix: What Was Already Tried & Rejected (per prior research + recent commits)

| Approach | Status | Reason |
|----------|--------|--------|
| Fixed dark_threshold (85) | ❌ Rejected | Caused wall false positives; replaced by adaptive `mean−1.5σ` |
| MOG2-only with longer warm-up | ❌ Rejected | Still misses stationary birds; 500-frame history unrealistic for 20-min windows |
| Template matching / Haar cascades | ❌ Rejected | Requires training data; false positives on nest/shadows |
| Background model transfer | ❌ Rejected | Day-to-day lighting variation breaks transfer |
| Optical flow + appearance (dense) | ❌ Rejected | Too heavy; parameter tuning complex |
| DNN classifier (MobileNet/EfficientDet) | ❌ Deferred | Needs labeled dataset; long-term only |
| Short-burst rules (2–8 frame birds) | ❌ Rejected | Admitted persistent static-feature FPs; net negative |
| Occupancy suppression alone | ❌ Rejected | Per-pixel mask doesn't catch slow-drifting shadows; suppressed perched birds, FP 6→20 |
| KNN + MOG2 union ensemble | ❌ Rejected | Ablation: TP 7→4, FN 3→6, F1 0.61→0.47; KNN didn't recover sparse FNs, cost real birds |
| Lower persistence gate (0.30/0.20) | ❌ Rejected | FNs (2–8 frames) stay below threshold; admits persistent static FPs |
| Shape metrics (solidity/circularity) | ❌ Rejected | Heavy overlap: real-bird solidity 0.40–0.83 vs FP 0.45–0.92 |

---

## 9. References

- OpenCV Background Subtraction: MOG2, KNN, GSOC (contrib)
- Finlayson et al., "Illuminant-Invariant Colour Spaces" (chromaticity shadows)
- ViBe: Barnich & Van Droogenbroeck, "ViBe: A Universal Background Subtraction Algorithm" (2011)
- PBAS: Hofmann et al., "PBAS: Pixel-Based Adaptive Segmenter" (2012)
- Motion History Image: Davis & Bobick, "The Representation and Recognition of Human Movement Using Temporal Templates" (1997)
- Moondream2: https://github.com/vikhyat/moondream
- `llama-cpp-python` vision support: https://github.com/abetlen/llama-cpp-python

---

*End of deep research update. Next step: implement P0 tasks in a feature branch, run ablation, then merge.*