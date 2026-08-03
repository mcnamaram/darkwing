# DarkWing Swift Reporter - Testing Strategy
## 🧪 Objective
To define a rigorous, tiered testing suite that verifies both the **deterministic logic** (scheduling, data formatting) and the **non-deterministic components** (API calls, ML detections). The goal is robust validation before any physical camera connection.

## 🔬 Test Tiers & Coverage Goals
We must approach testing in increasing order of complexity and dependency level:

### Tier 1: Unit Tests (Pure Logic - No Dependencies)
*   **Target:** `src/scheduler.py`
*   **Goal:** Verify the calculation engine is flawless. Must pass for all boundary conditions:
    *   Day rollover (e.g., last day of month).
    *   Hour rollovers and time-arithmetic across midnight *if applicable*.
    *   Verification that $T_{\text{start}} \to T_{\text{end}}$ is always exactly 19 minutes, regardless of the start minute.
*   **Tools:** `unittest` or `pytest`.

### Tier 2: Service/Mock Tests (Behavioral Validation)
*   **Target:** `src/analysis_engine.py` and `src/main_processor.py`
*   **Goal:** Verify that the data flow works even when the actual video service is swapped out for a predictable mock/stub.
*   **Strategy:** Use Python's built-in mocking libraries (`unittest.mock`) to replace:
    1.  The call to `reolinkapipy` with a function that returns pre-recorded, known 'Success' or 'Failure' video stream data objects.
    2.  The ML Service call with a predetermined list of bounding boxes/timestamps.
*   **Validation:** Ensure the logging and scheduling components correctly process both **Maximum Sighting Density** (many detections) and **Zero Detections** (the primary fail-safe).

### Tier 3: Integration Tests (Hybrid Validation)
*   **Target:** Full pipeline execution with real dependencies used in a controlled environment.
*   **Setup Requirement:** Must use credentials for the development Reolink test feed or another developer stream, running within a protected test network segment.
*   **Sequence:** $\text{T1} \rightarrow$ `Scheduler` (real call) $\rightarrow$ `Analysis Engine` (real API input/output simulation) $\rightarrow$ `Logger` (writes artifact).

### IV. Failure Testing & Observability
Every component must be tested for failure states and gracefully handle them:
*   **API Timeout:** The Orchestrator must retry with backoff logic but continue the overall schedule loop (`fail fast` decision is wrong; we aim to $\text{continue}$).
*   **Format Mismatch:** If the incoming data from the API deviates (e.g., Confidence score is a string instead of float), the system must log a **Schema Error** internally and skip that record, rather than crashing.

---
***End of Testing Strategy***