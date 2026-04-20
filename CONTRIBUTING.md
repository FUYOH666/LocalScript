# Contributing to LocalScript

Thank you for improving the project. Keep changes small, testable, and aligned with the local-first goal.

## Development Baseline

- Python **3.12+**
- package manager: [`uv`](https://github.com/astral-sh/uv)
- install: `uv sync --all-extras`
- lint: `uv run ruff check .`
- tests: `uv run pytest -q`
- E2E stand: `PYTHONPATH=. uv run python stands/run_e2e.py`

For the full verification path, use [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Change Rules

- Avoid unrelated refactors in the same change.
- New behavior should come with tests when practical.
- Keep the local-runtime promise intact: no new mandatory external AI vendor dependency.
- Reflect API or configuration changes in `README.md`, `.env.example`, and the relevant docs.

## Secrets And Hygiene

- Never commit `.env`, API keys, tokens, internal IPs, or private machine paths.
- Keep [`.env.example`](.env.example) sanitized with placeholders only.
- Before pushing, inspect `git diff --cached` for secrets and accidental environment leakage.

## License

By contributing, you agree that your changes are published under [`LICENSE`](LICENSE).

## Contacts

Project ownership and contacts: [`AUTHORS.md`](AUTHORS.md).
