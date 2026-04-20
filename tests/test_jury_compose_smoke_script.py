"""Jury Docker Compose smoke script is present and syntactically valid bash."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_jury_compose_smoke_script_exists_and_bash_n() -> None:
    path = ROOT / "scripts" / "jury_compose_smoke.sh"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "jury-smoke" in text
    assert "docker compose" in text
    assert "/healthz" in text
    proc = subprocess.run(
        ["bash", "-n", str(path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
