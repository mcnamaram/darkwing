# Welcome to DarkWing

**DarkWing** is a small, practical tool for submitting curated Chimney Swift observation data as a structured batch to a Google Form used by the Wild Bird Recovery research program.

The system is intentionally small:

- Read a curated CSV (one row per 20-minute observation window).
- Translate short codes into the form's long-form question text and answer text.
- Validate each row against a fixed schema.
- POST each row to a Google Apps Script webhook, which constructs and submits a Google Form response.
- Log every submission locally so the run is auditable and resumable.

## Where to start

- **[Project Memory](./project_memory.md)** — current status and what to read first if you are new.
- **[Setup Guide](./setup.md)** — get a working environment and authenticate with Google.
- **[Tutorial](./tutorial-1.md)** — run the tool end-to-end against a small CSV.
- **[Project Requirements](./prd.md)** — what we're solving and why.
- **[System Architecture](./architecture.md)** — the components, the data flow, the CSV schema and the short-code translation table.
- **[API Reference](./api_reference.md)** — the Apps Script `doPost` contract and the JSON payload shape.
- **[Test Strategy](./test_strategy.md)** — how the system is validated.
- **[Secrets Handling](./secrets_handling.md)** — what to keep out of the repo and why.
- **[Deployment](./deployment.md)** — the docs site is deployed to GitHub Pages; nothing else deploys.
