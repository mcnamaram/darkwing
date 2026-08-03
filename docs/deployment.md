# Deployment

## What gets deployed

The only thing this project deploys today is the documentation site. The Python package is run locally by the user (or invoked by a human or an agent skill on a host that has the user's Google credentials). There is no scheduled job.

In a future revision, the review UI (MVP4) may be deployed as a Docker image.

## Docs site (GitHub Pages)

The `docs/` directory is built with MkDocs (Material theme) and deployed to GitHub Pages by a GitHub Actions workflow. The workflow:

1. Triggers on every push to `main` and on every pull request.
2. On a `pull_request` event, builds the site and reports the build status; it does not deploy.
3. On a `push` to `main`, builds the site, uploads the build artifact, and deploys it to the `gh-pages` branch.

The workflow file lives at `.github/workflows/deploy-docs.yml` in this repository.

### Required secrets

- `GITHUB_TOKEN` is provided automatically by GitHub Actions. The workflow needs `contents: write` to push to the `gh-pages` branch; this is set in the workflow's `permissions:` block.

### Why no other deployments

The Python package is not deployed to PyPI. The submission flow is interactive (the user runs `python -m darkwing submit …`) and is not yet containerized. The video-download epic (MVP2) does not introduce a deployment; it adds a new module that the user runs locally. The review-UI epic (MVP4) may introduce a Docker deployment; that is a future plan.

## How to update the docs site

1. Edit the relevant file under `docs/`.
2. Update `mkdocs.yml` if the navigation needs to change.
3. Locally preview with `mkdocs serve` (from the repo root, in an active `.venv` with `mkdocs` and `mkdocs-material` installed).
4. Commit and push. The workflow deploys on the merge to `main`.

## How to roll back

The `gh-pages` branch is the deployed site. Reverting a commit on `main` will redeploy the prior content on the next push. For an emergency revert, force-push the `gh-pages` branch to a known-good commit.
