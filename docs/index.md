# Welcome to DarkWing

**DarkWing** is a small, practical tool for submitting curated Chimney Swift observation data as a structured batch to a Google Form used by the Wild Bird Recovery research program.

The system is intentionally small:

- Read a curated CSV (one row per 20-minute observation window).
- Validate each row against a fixed Pydantic schema.
- Translate short codes into the form's long-form question text and answer text.
- Drive a real Chromium browser (Playwright) to fill and submit each row.
- Log every submission locally so the run is auditable.

## Where to start

| [Project Memory](./project_memory.md) | current status and what to read first if you are new. |
| [Setup Guide](./setup.md) | get a working environment. |
| [Tutorial 1: CSV Submission](./tutorial-1.md) | run the tool end-to-end against a small CSV. |
| [Tutorial 2: Automated Pipeline](./tutorial-2.md) | run the full detect → VLM → submit pipeline. |
| [Project Requirements](./prd.md) | what we're solving and why. |
| [System Architecture](./architecture.md) | the components, the data flow, the CSV schema and the short-code translation table. |
| [API Reference](./api_reference.md) | the Python API: schema, CSV I/O, form submission, CLI. |
| [Test Strategy](./test_strategy.md) | how the system is validated. |
| [Secrets Handling](./secrets_handling.md) | what to keep out of the repo and why. |
| [Deployment](./deployment.md) | the docs site is deployed to GitHub Pages; nothing else deploys. |
