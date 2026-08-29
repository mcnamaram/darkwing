# DarkWing — Project Roadmap

> **Read this first.** It tells you where the project is, what's been done, what's next, and where the work lives.

## What this project is

**DarkWing** reads a curated CSV of Chimney Swift observations and submits each row, one at a time, to a Google Form operated by the Wild Bird Recovery research program. The "why" lives in the [Project Requirements](./prd.md); the "how" lives in the [System Architecture](./architecture.md).

---

## Current status

| Phase | Name | Status | What it delivers |
| --- | --- | --- | --- |
| 0 | Repo reset | ✅ done | Clean tree, no broken source or build artifacts |
| 1 | Schema | ✅ done | `src/darkwing/schema.py` — Pydantic models, short-code translation table |
| 2 | CSV I/O | ✅ done | `src/darkwing/csv_io.py` — read CSV, write submission log |
| 3 | Form submit | ✅ done | `src/darkwing/form_submit.py` — Playwright browser automation |
| 4 | CLI | ✅ done | `src/darkwing/cli.py` — `darkwing validate/submit` |
| 5 | Docs | ✅ done | MkDocs site at <https://mcnamaram.github.io/darkwing/> |
| 6 | Manual smoke | 🟠 blocked | One real run against the live form |
| **MVP3-1** | Payload Extraction | ✅ done | `src/darkwing/agent_payload.py` — extract 1-FPS keyframes from REVIEW windows (max 15, 640px wide, 60s span) |
| **MVP3-2** | VLM Agent Client | ✅ done | `src/darkwing/agent.py` — lightweight REST client (Gemini/OpenAI) returning validated `ObservationRecord` |
| **MVP3-3** | CLI Integration | ✅ done | `darkwing detect --agent` — async bridge, appends AI proposals to `review_index.jsonl` |

**Legend:** ⬜ not started · ✅ done · 🟡 in progress · 🟠 blocked

**Test coverage:** 125 tests, all green. See [Test Strategy](./test_strategy.md).

---

## What changed since the old code

| Before (broken) | Now (current) |
| --- | --- |
| Apps Script webhook via `requests` | Playwright browser automation |
| gcloud OAuth token flow | No auth needed — browser handles Google login |
| `requirements.txt` + `pyproject.toml` | `pyproject.toml` only |
| 92 tests | 125 tests (added detector, agent, payload, windowing tests) |
| `auth.py` module | Removed |
| `playwright-stealth` | Removed (not needed) |
| `pytest-playwright` | `pytest-playwright-asyncio` (async variant) |

---

## Files

```sh
src/darkwing/
├── __init__.py
├── agent.py             # VLM agent REST client (Gemini/OpenAI)
├── agent_payload.py     # Phase 1: keyframe extraction for REVIEW windows
├── cli.py               # darkwing validate/submit/detect commands
├── csv_io.py            # read CSV, write submission log
├── detector.py          # motion detection (MOG2 background subtraction)
├── frames.py            # video frame source abstraction
├── form_submit.py       # Playwright browser automation
├── schema.py            # Pydantic models, short-code tables
├── windows.py           # observation window grouping & state
└── tests/
    ├── conftest.py
    ├── test_agent.py
    ├── test_agent_payload.py
    ├── test_cli.py
    ├── test_cli_detect.py
    ├── test_csv_io.py
    ├── test_detector.py
    ├── test_form_submit.py
    ├── test_schema.py
    ├── test_windows.py
    └── fixtures/
        └── sample_observation.csv
docs/
├── index.md
├── setup.md
├── tutorial-1.md
├── architecture.md
├── prd.md
├── api_reference.md
├── test_strategy.md
├── secrets_handling.md
├── deployment.md
├── detector_algorithm.md
├── ai_integration.md
└── payload_extraction_spec.md
```

---

## What's next

Epics are numbered as defined in [Project Requirements](./prd.md):

- **MVP2**: Video download epic — download footage from the Reolink cameras for review
- **MVP4**: Review UI — web interface to review submissions before they go out