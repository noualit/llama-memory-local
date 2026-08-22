# Contributing to llama-memory

Thanks for contributing. Keep it simple and testable.

## Local setup

- Python 3.11 (via Miniconda recommended)
- PostgreSQL with PGVector extension
- llama-server + nomic-embed-text running (or mock them for tests)

Steps:

- Clone the repo
- Install dependencies: pip install -e .
- Copy env: cp .env.example .env
- Configure DATABASE_URL and URLs in .env
- Run: python -m uvicorn app.main:app --reload

Run migrations when updating schema:

- alembic upgrade head

## Coding standards

- Python 3.11+ only
- Use type hints; prefer async where appropriate
- No print() in production code; use logging
- One responsibility per file; keep files under 600 lines

## Pull requests

- Include:
  - What you changed and why
  - Relevant screenshots/logs if it affects MCP behavior
- Ensure:
  - All tests pass (pytest)
  - No secrets or local configs committed
- Prefer small, focused changes over large monolithic PRs
