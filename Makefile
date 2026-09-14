.PHONY: test coverage coverage-html coverage-xml coverage-term install-dev clean mutate mutate-report mutate-html mutate-badge

# Default target
all: test

# Install dev dependencies
install-dev:
	uv pip install -e ".[dev]"

# Run tests
test:
	uv run pytest

# Coverage targets
coverage:
	uv run pytest --cov=darkwing --cov-report=term-missing --cov-report=html --cov-report=xml

coverage-html:
	uv run pytest --cov=darkwing --cov-report=html

coverage-xml:
	uv run pytest --cov=darkwing --cov-report=xml

coverage-term:
	uv run pytest --cov=darkwing --cov-report=term-missing

# Mutation testing targets
mutate:
	rm -f cosmic-ray-session.json
	uv run cosmic-ray init cosmic-ray.toml cosmic-ray-session.json
	uv run cosmic-ray baseline --session-file cosmic-ray-session.json cosmic-ray.toml
	uv run cosmic-ray exec cosmic-ray.toml cosmic-ray-session.json

mutate-report:
	uv run cr-report cosmic-ray-session.json --show-pending

mutate-html:
	uv run cr-html cosmic-ray-session.json > cosmic-ray-report.html

mutate-badge:
	uv run cr-badge cosmic-ray.toml cosmic-ray-badge.svg cosmic-ray-session.json

# Clean up coverage artifacts
clean:
	rm -rf htmlcov .coverage coverage.xml .pytest_cache __pycache__ src/darkwing.egg-info cosmic-ray-session.json cosmic-ray-report.html cosmic-ray-badge.svg