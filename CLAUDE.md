# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

Commonly used commands for development:

```bash
# Install development dependencies
make install-dev

# Run tests
make test

# Run the full quality gate (coverage + mutation testing + quality report)
make quality

# Validate an observation CSV file
darkwing validate path/to/observations.csv

# Dry-run submission (no browser, no logging)
darkwing submit path/to/observations.csv --dry-run

# Submit observations to Google Form (opens visible browser)
darkwing submit path/to/observations.csv

# Run detection on footage (requires VLM configuration for AI proposals)
darkwing detect --date MM/DD/YYYY --tower N --source-path /path/to/footage.mp4
```

Environment variables for VLM configuration (optional):

- `VLM_BASE_URL`: OpenAI-compatible API endpoint (e.g., see .env file value for Ollama)
- `VLM_MODEL`: Model identifier (e.g., `swift-detector-v1`, `gpt-4o-mini`)
- `VLM_API_KEY`: API key (use `"ollama"` for local Ollama)
- `VLM_PROVIDER`: Human-readable label for logs/errors (e.g., `ollama`, `openrouter`)

Form submission requires:

- `DARKWING_FORM_URL`: Google Form URL
- `DARKWING_SUBMITTER_NAME`: Name to use for submissions (defaults to "darkwing-agent")

## Code Architecture

DarkWing follows a modular architecture with clear separation of concerns:

### Core Modules

- **`darkwing.schema`**: Pydantic models for `ObservationRecord` with validation and short-code to long-form translation
- **`darkwing.csv_io`**: CSV reading/writing with validation error collection and submission logging
- **`darkwing.form_submit`**: Playwright-based automation for filling and submitting Google Forms
- **`darkwing.detector`**: Classical computer vision detector using OpenCV MOG2 background subtraction
- **`darkwing.windows`**: 20-minute observation window segmentation and resume functionality
- **`darkwing.agent`**: VLM agent for AI-powered observation proposals (MVP3)
- **`darkwing.agent_payload`**: Frame extraction for VLM analysis
- **`darkwing.cli`**: Command-line interface orchestrating all functionality

### Data Flow

1. **Validation**: `csv_io.read_csv()` → List of validated `ObservationRecord` objects
2. **Submission**: `form_submit.submit_csv_records()` → Browser automation → Google Form
3. **Detection Pipeline**:
   - Frame iteration → `Detector.process_frame()` → FrameResults
   - Window aggregation → `classify_window()` → WindowResult (SKIP/REVIEW/MANUAL)
   - For REVIEW windows with VLM: `agent.AIObservationAgent.propose_observation()` → AI-enhanced ObservationRecord
4. **Resume Mechanism**: JSON-Lines logs (`submitted_log.jsonl`, `review_index.jsonl`) enable restarting from where left off

### Key Features

- **Short-code expansion**: CSV uses short codes (e.g., `in;out`, `bld`) that expand to Google Form's long-form text
- **Validation**: Strict Pydantic validation with helpful error messages
- **Resume support**: Skip already-processed records/windows via identity keys
- **Dry-run mode**: Test submission logic without browser automation
- **Quality gates**: Mutation testing and coverage reporting via `make quality`

### Entry Point

The CLI (`darkwing.cli:main`) provides three subcommands:

- `validate`: Check CSV correctness
- `submit`: Process and submit observations
- `detect`: Analyze footage for automated observation proposals

Tests are located in `tests/` with corresponding `test_*.py` files for each module.

If a command or file edit fails more than twice with the same outcome, do not retry it. Stop entirely, explain what failed, and ask me for guidance.
If the compiler/test suite throws an error, you are allowed to look at logs/ or use grep to find the root cause instead of just running the build command again.
