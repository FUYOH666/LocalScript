from __future__ import annotations

import pytest

from localscript.config import get_settings


def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def test_private_host_guard_rejects_public_llm_host(monkeypatch) -> None:
    monkeypatch.setenv("LOCALSCRIPT_ENFORCE_PRIVATE_HOSTS", "true")
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://example.com/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    _clear_settings_cache()

    with pytest.raises(ValueError, match="LOCALSCRIPT_LLM_BASE_URL"):
        get_settings()


def test_private_host_guard_allows_docker_service_name(monkeypatch) -> None:
    monkeypatch.setenv("LOCALSCRIPT_ENFORCE_PRIVATE_HOSTS", "true")
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    _clear_settings_cache()

    settings = get_settings()

    assert settings.llm_base_url_str == "http://ollama:11434/v1"


def test_private_host_guard_allows_allowlisted_fqdn(monkeypatch) -> None:
    monkeypatch.setenv("LOCALSCRIPT_ENFORCE_PRIVATE_HOSTS", "true")
    monkeypatch.setenv("LOCALSCRIPT_ALLOWED_HOSTS", "llm.example.com")
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://llm.example.com/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    _clear_settings_cache()

    settings = get_settings()

    assert settings.llm_base_url_str == "http://llm.example.com/v1"


def test_private_host_guard_allows_tailscale_cgnat_ip(monkeypatch) -> None:
    monkeypatch.setenv("LOCALSCRIPT_ENFORCE_PRIVATE_HOSTS", "true")
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://100.64.0.1:11434/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    _clear_settings_cache()

    settings = get_settings()

    assert settings.llm_base_url_str == "http://100.64.0.1:11434/v1"


def test_private_host_guard_rejects_public_ipv6_host(monkeypatch) -> None:
    monkeypatch.setenv("LOCALSCRIPT_ENFORCE_PRIVATE_HOSTS", "true")
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://[2001:4860:4860::8888]:443/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    _clear_settings_cache()

    with pytest.raises(ValueError, match="LOCALSCRIPT_LLM_BASE_URL"):
        get_settings()


def test_private_host_guard_rejects_public_quality_judge_host(monkeypatch) -> None:
    monkeypatch.setenv("LOCALSCRIPT_ENFORCE_PRIVATE_HOSTS", "true")
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    monkeypatch.setenv("LOCALSCRIPT_QUALITY_JUDGE_BASE_URL", "http://judge.example.com/v1")
    _clear_settings_cache()

    with pytest.raises(ValueError, match="LOCALSCRIPT_QUALITY_JUDGE_BASE_URL"):
        get_settings()
