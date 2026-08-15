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

**Legend:** ⬜ not started · ✅ done · 🟡 in progress · 🟠 blocked

**Test coverage:** 84 tests, all green. See [Test Strategy](./test_strategy.md).

---

## What changed since the old code

| Before (broken) | Now (current) |
| --- | --- |
| Apps Script webhook via `requests` | Playwright browser automation |
| gcloud OAuth token flow | No auth needed — browser handles Google login |
| `requirements.txt` + `pyproject.toml` | `pyproject.toml` only |
| 92 tests | 84 tests (removed auth tests) |
| `auth.py` module | Removed |
| `playwright-stealth` | Removed (not needed) |
| `pytest-playwright-asyncio` | Removed (conflicts with `pytest-playwright`) |

---

## Files

```sh
src/darkwing/
├── __init__.py
├── cli.py           # darkwing validate/submit commands
├── csv_io.py        # read CSV, write submission log
├── form_submit.py   # Playwright browser automation
├── schema.py        # Pydantic models, short-code tables
└── tests/
    ├── test_cli.py
    ├── test_csv_io.py
    ├── test_form_submit.py
    ├── test_schema.py
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
└── deployment.md
```

---

## What's next

- **MVP2**: Video download epic — add ability to download and process video clips
- **MVP3**: Review UI — web interface to review submissions before they go out
- **MVP4**: Scheduled runs — cron job to submit daily CSV batches
