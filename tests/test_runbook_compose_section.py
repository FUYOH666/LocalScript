"""RUNBOOK keeps Docker compose smoke instructions."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runbook_has_compose_smoke() -> None:
    text = (ROOT / "docs" / "RUNBOOK.md").read_text(encoding="utf-8")
    assert "Clean clone with Docker only" in text
    assert "jury_compose_smoke.sh" in text
    assert "docker compose" in text.lower()
