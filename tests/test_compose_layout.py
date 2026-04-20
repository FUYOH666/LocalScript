"""Sanity check that the jury docker-compose entrypoint stays present."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docker_compose_declares_api_and_ollama() -> None:
    compose = ROOT / "docker-compose.yml"
    assert compose.is_file(), "root docker-compose.yml is required for hackathon submission"
    text = compose.read_text(encoding="utf-8")
    assert "services:" in text
    assert "ollama:" in text
    assert "api:" in text
    assert "LOCALSCRIPT_LLM_BASE_URL" in text
    assert "ollama/ollama" in text


def test_dockerfile_api_exists() -> None:
    df = ROOT / "docker" / "Dockerfile.api"
    assert df.is_file()
    body = df.read_text(encoding="utf-8")
    assert "localscript-api" in body
    assert "luac5.4" in body
