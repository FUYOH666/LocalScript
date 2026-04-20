"""docs/README.md stays a minimal public documentation index."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docs_readme_index_exists() -> None:
    assert (ROOT / "stands" / "REMOTE_GPU.example.md").is_file()
    assert (ROOT / "docs" / "RUNBOOK.md").is_file()
    assert (ROOT / "docs" / "ARCHITECTURE_C4.md").is_file()
    assert (ROOT / "docs" / "c4" / "README.md").is_file()
    path = ROOT / "docs" / "README.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "RUNBOOK.md" in text
    assert "ARCHITECTURE_C4.md" in text
    assert "c4/README.md" in text
    assert "../README.md" in text
    assert "REMOTE_GPU.example.md" in text
