# Project Memory

> **This is the entry point for the project.** Read this first if you are a new session, a new agent, or returning after a break. It points you at the long-form docs and tells you where the work is.

## What this project is

**DarkWing** reads a curated CSV of Chimney Swift observations and submits each row, one at a time, to a Google Form operated by the Wild Bird Recovery research program. The "why" lives in the [Project Requirements](./prd.md); the "how" lives in the [System Architecture](./architecture.md); the contract with the form's submitter webhook lives in the [API Reference](./api_reference.md).

## Current status

| Phase | Status | Notes |
|---|---|---|
| Phase 0 — repo reset | ⬜ not started | Drop broken source tree, drop `site/` build artifacts, drop captured `googleforms` file from index. |
| Phase 0.5 — docs aligned | 🟡 in progress | Doc rewrite complete; this file is the final piece. Awaiting user sign-off. |
| Phase 1 — schema | ⬜ not started | `src/darkwing/schema.py` with Pydantic models, short-code translation table. |
| Phase 2 — CSV I/O | ⬜ not started | `src/darkwing/csv_io.py`, fixture CSVs. |
| Phase 3 — auth | ⬜ not started | `src/darkwing/auth.py`, `gcloud` shelled-out token retrieval. |
| Phase 4 — form submit | ⬜ not started | `src/darkwing/form_submit.py`, mocked-`requests` test suite. |
| Phase 5 — CLI + notebook | ⬜ not started | `src/darkwing/cli.py`, `notebooks/01_submit_existing_csv.ipynb`. |
| Phase 6 — Apps Script | ⬜ not started | `apps_script/doPost.gs` with all item types. Decision: Apps Script path (not Forms API — the form is a Classic Form). |
| Phase 7 — manual smoke | ⬜ not started | One human run against the live form. |

**Legend:** ⬜ not started · 🟡 in progress · ✅ done · 🟠 blocked

## What's working today

Nothing in the Python code is working. The `src/` directory contains a partial, broken sketch from earlier work (it does not even parse — see the [original review notes](https://chat.example.invalid/darkwing-state-review) if you have access to the conversation history). The docs describe the system as it should be, not as the code currently implements it.

The *only* working artifact is the MkDocs site, which builds and deploys via the GitHub Actions workflow.

## What's blocked on the user

1. **Sign-off on the doc set.** The [Project Requirements](./prd.md), [System Architecture](./architecture.md), [API Reference](./api_reference.md), [Setup](./setup.md), [Tutorial](./tutorial-1.md), [Test Strategy](./test_strategy.md), [Secrets Handling](./secrets_handling.md), and [Deployment](./deployment.md) have all been rewritten for the small, form-aware MVP1. Read them and tell me what to change.
2. **One-time Google auth.** When the user is ready to run the tutorial, they need to run `gcloud auth login` once. See [Setup](./setup.md#google-authentication).

## How to pick this up

1. Read this file (you're doing it).
2. Read the [Project Requirements](./prd.md) for the *why*.
3. Read the [System Architecture](./architecture.md) for the *how*.
4. Read the [API Reference](./api_reference.md) for the wire contract.
5. Read the [Setup](./setup.md) for environment setup.
6. Read the [Tutorial](./tutorial-1.md) for the end-to-end flow.
7. Read the [Test Strategy](./test_strategy.md) for the test layout.
8. Read the [Secrets Handling](./secrets_handling.md) for the policy on what must never be committed.
9. Read the [Deployment](./deployment.md) for what deploys and what doesn't.
10. Look at the plan file at `.hermes/plans/2026-08-06_152336-darkwing-rewrite.md` for the task-by-task execution plan.

## Conventions

- **Python:** 3.12 by default; 3.14 is available on the host if Phase 0 confirms `pydantic` and other deps have 3.14 wheels.
- **Dependency policy:** keep `requirements.txt` minimal. Only add a dep when code in this repo imports it. No transitive "for future use" entries.
- **Secret policy:** see [Secrets Handling](./secrets_handling.md). Nothing in `.env` ever gets committed. Captured auth headers (cookies, tokens) are treated as compromised the moment they exist on disk.
- **Test policy:** TDD. Every task in the plan file writes the failing test first, then the minimal code, then the commit.
- **Commit policy:** small, scoped, one logical change per commit. The plan file at `.hermes/plans/` is the source of truth for what commits are expected and in what order.

## Open questions

These are tracked in the plan file at `.hermes/plans/2026-08-06_152336-darkwing-rewrite.md#risks-tradeoffs-and-open-questions`. The currently unresolved ones are:

- Python 3.14 vs 3.12 — pending Phase 0 install test.
- The exact Apps Script item-type branches the user wants to handle (vs the minimum required to populate the form's 12 questions).
- The MVP4 review-UI deployment shape (notebook widget, TUI, or small web app).
