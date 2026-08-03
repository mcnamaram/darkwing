# DarkWing Swift Reporter - Technical Implementation Plan
## 💻 Goal
To translate the PRD and Architecture into a set of verifiable, implemented code modules within the `src` directory structure.

## 🚀 Phased Roadmap (Our Action Plan)
The plan follows the structured development life cycle template defined in the Architecture Design document. Each phase must pass its unit tests before proceeding.

### Phase 1: Infrastructure & Setup (CURRENTLY COMPLETE)
*   **Task:** Establish project shell (`requirements.txt`, virtual environment).
*   **Dependencies Confirmed:** Must include `reolinkapipy`, `opencv-python`.
*   **Status:** Logical structure complete. *Execution blocked by Env error.*

### Phase 2: Scheduling Backbone (COMPLETED)
*   **Target File:** `src/scheduler.py`
*   **Test Focus:** Unit testing to ensure perfect adherence to the $\mathbf{T_{\text{start}}} \to \mathbf{T_{\text{start}}+19\text{min}}$ rule across all times, especially hour boundaries (e.g., 23:50 -> 00:89:00 next day).
*   **Deliverable:** A list of correctly parameterized time windows for a given date range and tower ID.

### Phase 3: Core Analysis Engine (MOCK STUB COMPLETE)
*   **Target File:** `src/analysis_engine.py`
*   **Action Item:** Replace the mock logic in `process_video_segment()` with real API calls. This requires reliable video slicing using actual library functions.
*   **Test Depth:** Edge case testing (e.g., what happens when detection is requested at $\text{T}_{\text{start}} - 15\text{min}$ vs. $\text{T}_{\text{end}})$ and handling zero return values safely.

### Phase 4: Logging & Aggregation (NEXT CODE FOCUS)
*   **Target File:** `src/main_processor.py`
*   **Function:** This module coordinates Phases 2 and 3, collects results into the structured list (`all_sighting_records`), and manages the final output writing. It acts as the "Glue Code."

### Phase 5: Review and Iteration (Future State)
*   **Goal:** Final deployment to a test pipeline using real data/credentials.
*   **Deliverable:** A runnable script that produces the System Log CSV artifact.

## ☑️ Key Dev Principles
*   Use logging/print statements extensively within the stubbed code to signal when execution hits an API boundary, allowing targeted debugging when dependencies are fixed.
*   All core logic must be isolated in distinct classes or functions (e.g., `SchedulerClass`, `AnalyticsService`).