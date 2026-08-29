# DarkWing AI Agent Observation Extraction

## 1. Product Requirements (Traceable)
* **REQ-1: Automated Data Entry (VLM Integration):** For `REVIEW` windows, VLM must output valid `ObservationRecord` proposal matching Pydantic schema (short-codes).
* **REQ-2: Frugal Frame Budget:** Limit visual payload (1 FPS, max 15 frames per window) to minimize API cost & network load.
* **REQ-3: Temporal Padding (Context Preservation):** Pad motion bursts with 2s safety buffer before/after to capture swift entry/exit.
* **REQ-4: Standardized Payload Resolution:** Downscale keyframes to ~640x360 while preserving source aspect ratio.
* **REQ-5: Idempotent Resume:** Re-runs skip already-processed windows in `review_index.jsonl`.
* **REQ-7: 1-Minute Observation Span:** To satisfy the observation protocol, the Agent must ONLY receive a fixed 60-second observation span starting at `first_detection_ts` (or the start of the window if detection is at minute 0). Discard all other motion activity.

## 2. Goal
Integrate an autonomous Vision AI Agent into the `darkwing detect` workflow to automate data entry for windows classified as `REVIEW`. Replace manual review with AI-generated `ObservationRecord` proposals.

### Plain-Language Summary for Product Management
* **The Manual Labor:** Currently, the research team manually reviews every motion burst in the video to type observation data into a form. This is tedious and error-prone.
* **Our Solution:** We are inserting an autonomous AI Agent into the review loop for `REVIEW`-classified windows. 
* **How it meets requirements:**
    * **Automated Data Entry:** The AI reads the video and produces a structured observation proposal automatically.
    * **Cost-Efficient:** It doesn't analyze the *whole* 20-minute video. It only looks at the first 60 seconds of motion (the "first visibility"), extracting 1 frame per second (max 15 total) at a lightweight resolution (~640x360).
    * **Reliable:** The AI’s output is enforced by our existing Pydantic data schema, ensuring it only provides data in the exact format the Google Form requires.
    * **Lean:** No heavy third-party AI SDKs are installed; the system uses a custom, lightweight Python client.

## 3. Implementation
### Phase 1: Payload Extraction (`src/darkwing/agent_payload.py`)
- Define `extract_motion_frames(frames_source, frame_results) -> List[bytes]`.
- Logic: Identify contiguous motion sequences starting strictly from `first_detection_ts` (padded +2s), extract JPEG keyframes up to max frame limit.

### Phase 2: Agent Client (`src/darkwing/agent.py`)
- Implement `AIObservationAgent` (REST client).
- System prompt: Map visual evidence to `ObservationRecord` fields (short-codes).
- Supports: `GEMINI_API_KEY` and `OPENAI_API_KEY`.

### Phase 3: CLI Integration (`src/darkwing/cli.py`)
- Add `--agent` flag to `darkwing detect`.
- If `REVIEW` window: Invoke agent, append proposal to `review_index.jsonl`.

## 4. Verification
- `tests/test_agent.py`: Mock API responses, verify schema compliance with synthetic frames.
