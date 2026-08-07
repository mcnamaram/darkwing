# 🐦 DarkWing Swift Reporter

Automated, structured observation reporting for Chimney Swifts.

## 📋 Overview

**DarkWing Swift Reporter** is an automated data collection system designed to monitor multiple towers and generate structured reports on Chimney Swift behavior.

**Note:** The primary purpose of this system is to produce a **System Log (CSV/JSON)** that captures vital research metrics. It is *not* intended for high-level video production or social media clipping; it is built as an automated "field assistant" to ensure data consistency and completeness during the observation window.

## ✨ Key Features

- **Automated Sampling:** Automatically schedules checks at 10:00, 20:00, and 40:00 minutes past every hour from 6:00 AM to 9:00 PM EDT.
- **Strict Observation Windows:** Enforces a precise 19-minute analysis window for every sampling event ($T_{start}$ to $T_{start} + 19$ mins).
- **Complex Data Extraction:** Implements advanced logic to track nest_cycle stages, bill activity, and movement types.
- **Structured Reporting:** Generates automated data logs ready for import into research databases.

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Access to Reolink camera feeds via `reolinkapipy`
- Valid API credentials for the vision analysis engine

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-org/darkwing-swift-reporter.git
   cd darkwing-swift-reporter
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   # On macOS/Linux:
   source .venv/bin/activate
   # On Windows:
   .\venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

### Configuration

Update your local environment variables or configuration file with camera credentials and site-specific IDs (e.g., `T1`). Reference `docs/prd.md` for the full list of required fields and configuration options.

## 🏗️ System Architecture

The project is modularly designed for reliability:

- **Orchestrator (`src/main_processor.py`):** The central coordinator managing the daily execution loop.
- **Scheduler (`src/scheduler.py`):** A precision logic engine that calculates observation windows based on the 19-minute protocol.
- **Core Engine (`src/analysis_engine.py`):** Handles real-time video processing, `reolinkapipy` integration, and AI inference for data point extraction.
- **Logger:** Aggregates results into a finalized CSV log.

## 📜 The Protocol (Research Requirements)

To comply with research standards, the system's logic is bound by the following rules:

1. **Timezone:** All systems operate in **EDT**.
2. **Sampling Logic:** Checks are performed at three intervals per hour (XX:00, XX:20, and XX:40).
3. **Data Integrity:** Each observation must be pulled over exactly a 19-minute window to ensure sufficient visual data for the AI processing layer.

## 📊 Data Schema

The output logs will include:

- `TOWER_ID`, `DATE`, `SAMPLE_TIME`
- `FIRST_DETECTION_TS`, `CONFIDENCE`
- `ADULT_COUNT`, `NESTING_STAGE`
- `BILL_ACTIVITY`, `FLIGHT_EVENTS`
- `PROXIMMITY_COUNT`, `AWAKE_STATUS`
- `BEHAVIORAL_FLAG` (Customer notes)

---
*Developed for automated avian research and habitat analysis.*
