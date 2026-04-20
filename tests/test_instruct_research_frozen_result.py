"""Frozen instruct-research drill artifact (no URLs inside JSON)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_instruct_research_frozen_compact_all_passed() -> None:
    path = ROOT / "stands" / "results" / "instruct_research_gemma26_awq_2026-04-03.compact.json"
    assert path.is_file(), "expected frozen instruct-research compact JSON in stands/results"
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(rows, list) and len(rows) == 8
    assert all(r.get("success") is True for r in rows)
    assert all(r.get("steps") == 1 for r in rows)
    raw = path.read_text(encoding="utf-8")
    assert "http://" not in raw and "https://" not in raw
