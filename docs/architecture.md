# DarkWing Swift Reporter - System Architecture Design
## 🏗️ Overall Structure
The system implements a layered, modular architecture designed for resilience and maintainability. The core principle is to strictly separate **Timing Logic** (scheduling, time zone math) from **Physical I/O** (reading videos, API calls).

### I. Architectural Layers & Components
1.  **Client Layer / Orchestrator (`src/main_processor.py`):**
    *   **Role:** The single source of truth for the daily run. It coordinates the entire process flow.
    *   **Functionality:** Calls the `Scheduler` $\rightarrow$ Loops through required segments $\rightarrow$ Passes segment boundaries to the `Analysis Engine` $\rightarrow$ Collects results and feeds them into the `Logger`.
    *   **Key Component:** Manages error handling, retries (for API dependency), and ensures state persistence.

2.  **Scheduling Service (`src/scheduler.py`):**
    *   **Role:** Pure calculation layer. Takes date constraints and generates a complete list of required segments.
    *   **Functionality:** Must implement the $\mathbf{T_{\text{start}}}$ to $\mathbf{T_{\text{start}}+19\text{min}}$ rule precisely, handling time boundaries (e.g., crossing midnight or hour changes) correctly within the EDT timezone context.

3.  **Video Access & Processing Engine (`src/analysis_engine.py`):**
    *   **Role:** The complex 'Black Box' layer. It simulates/handles the interaction with external, variable resources.
    *   **Dependencies (Internal):** `reolinkapipy` and a proprietary AI Service API.
    *   **Functionality:** Takes timestamp boundaries, slices the video stream (using FFmpeg utility call or library function), performs object detection, and returns standardized sighting data points.

4.  **Data Persistence Layer (`src/logger.py - NEW CONCEPT`):**
    *   **Role:** Collects all discrete findings and formats them for output.
    *   **Functionality:** Receives `SwiftSighting` objects and writes them, guaranteeing the structure of the final CSV/JSON System Log used for Google Forms submission.

### II. Data Flow Diagram (Conceptual)
*   **Time Source** $\rightarrow$ **Scheduler** $\rightarrow$ *List of Segments* $\rightarrow$ **Orchestrator** $\rightarrow$ *(Segment)* $\rightarrow$ **Analysis Engine** $\rightarrow$ *Raw Sighting Objects* $\rightarrow$ **Data Logger** $\rightarrow$ ***Final System Log (CSV)***

### III. Key Non-Functional Requirements
*   **Resilience:** The orchestration layer must be designed to fail gracefully: failure on one segment does not stop the entire day's run.
*   **Idempotency:** Running the processing script multiple times for the same date/segment should yield the exact same result without warning or modification of the log.

This architecture pattern ensures that each component can be developed, unit-tested, and replaced (e.g., swapping out `reolinkapipy` for a cloud streaming service) without rewriting the entire data flow.