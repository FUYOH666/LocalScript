import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from stands.run_jury_drill import profile_env

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_submission_profile_env_ollama_8gb_sets_expected_overrides(monkeypatch):
    monkeypatch.delenv("LOCALSCRIPT_LLM_BASE_URL", raising=False)
    env = profile_env("ollama-8gb")

    assert env["LOCALSCRIPT_LLM_BASE_URL"] == "http://127.0.0.1:11434/v1"
    assert env["LOCALSCRIPT_LLM_MODEL"] == "qwen2.5-coder:7b"
    assert env["LOCALSCRIPT_LLM_MAX_TOKENS"] == "256"
    assert env["LOCALSCRIPT_GENERATE_CANDIDATES_N"] == "1"
    assert env["LOCALSCRIPT_GENERATE_CANDIDATES_MAX_PARALLEL"] == "1"
    assert env["LOCALSCRIPT_RAG_ENABLED"] == "false"
    assert env["LOCALSCRIPT_QUALITY_POLICY_ENABLED"] == "false"
    assert env["LOCALSCRIPT_QUALITY_JUDGE_ENABLED"] == "false"
    assert env["LOCALSCRIPT_LLM_STRUCTURED_OUTPUT"] == "false"
    assert env["LOCALSCRIPT_SANDBOX_EXECUTION_MODE"] == "luac_only"
    assert env["LOCALSCRIPT_VALIDATION_WORKSPACE_TEMPLATE"].endswith(
        "/examples/validation_workspace_template"
    )
    assert "LOCALSCRIPT_ENABLE_SELENE" not in env

    extra = json.loads(env["LOCALSCRIPT_LLM_EXTRA_BODY_JSON"])
    assert extra["options"]["num_ctx"] == 4096
    assert extra["options"]["num_batch"] == 1


def test_submission_profile_env_ollama_8gb_respects_preset_llm_base_url(monkeypatch):
    monkeypatch.setenv(
        "LOCALSCRIPT_LLM_BASE_URL",
        "http://example.test:6666/v1",
    )
    env = profile_env("ollama-8gb")
    assert env["LOCALSCRIPT_LLM_BASE_URL"] == "http://example.test:6666/v1"
    assert env["LOCALSCRIPT_LLM_MODEL"] == "qwen2.5-coder:7b"


def test_profile_env_qwen7b_local_benchmark_sets_rag_and_docker_path():
    env = profile_env("qwen7b-local-benchmark")

    assert env["LOCALSCRIPT_LLM_BASE_URL"] == "http://127.0.0.1:1234/v1"
    assert env["LOCALSCRIPT_LLM_MODEL"] == "qwen2.5-coder-7b-instruct-mlx"
    assert env["LOCALSCRIPT_LLM_STRUCTURED_OUTPUT"] == "false"
    assert env["LOCALSCRIPT_LLM_EXTRA_BODY_JSON"] == ""
    assert env["LOCALSCRIPT_RAG_ENABLED"] == "true"
    assert env["LOCALSCRIPT_EMBEDDING_BASE_URL"] == "http://127.0.0.1:1234/v1"
    assert env["LOCALSCRIPT_EMBEDDING_MODEL"] == "text-embedding-nomic-embed-text-v1.5"
    assert env["LOCALSCRIPT_SANDBOX_EXECUTION_MODE"] == "docker"
    assert "LOCALSCRIPT_ENABLE_SELENE" not in env
    assert env["LOCALSCRIPT_REQUIRE_VALIDATORS"] == "true"
    assert env["LOCALSCRIPT_GENERATE_CANDIDATES_N"] == "1"
    assert env["LOCALSCRIPT_GENERATE_CANDIDATES_MAX_PARALLEL"] == "1"
    assert env["LOCALSCRIPT_QUALITY_POLICY_ENABLED"] == "false"
    assert env["LOCALSCRIPT_QUALITY_JUDGE_ENABLED"] == "false"
    assert env["LOCALSCRIPT_RAG_SOURCES_DIR"].endswith("/examples/rag_corpus")
    assert env["LOCALSCRIPT_VALIDATION_WORKSPACE_TEMPLATE"].endswith(
        "/examples/validation_workspace_template"
    )


def test_profile_env_rejects_unknown_profile():
    with pytest.raises(ValueError, match="Unknown profile"):
        profile_env("nope")


def test_profile_env_instruct_research_requires_base_url(monkeypatch):
    monkeypatch.delenv("LOCALSCRIPT_LLM_BASE_URL", raising=False)
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "some-model")
    with pytest.raises(ValueError, match="LOCALSCRIPT_LLM_BASE_URL"):
        profile_env("instruct-research")


def test_profile_env_instruct_research_requires_model(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://example.test:8002/v1")
    monkeypatch.delenv("LOCALSCRIPT_LLM_MODEL", raising=False)
    with pytest.raises(ValueError, match="LOCALSCRIPT_LLM_MODEL"):
        profile_env("instruct-research")


def test_profile_env_instruct_research_defaults(monkeypatch):
    monkeypatch.setenv(
        "LOCALSCRIPT_LLM_BASE_URL",
        "http://example.test:8002/v1",
    )
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "gemma-test-awq")
    monkeypatch.delenv("LOCALSCRIPT_LLM_EXTRA_BODY_JSON", raising=False)
    monkeypatch.delenv("LOCALSCRIPT_LLM_TIMEOUT_S", raising=False)
    env = profile_env("instruct-research")

    assert env["LOCALSCRIPT_LLM_BASE_URL"] == "http://example.test:8002/v1"
    assert env["LOCALSCRIPT_LLM_MODEL"] == "gemma-test-awq"
    assert env["LOCALSCRIPT_LLM_MAX_TOKENS"] == "256"
    assert env["LOCALSCRIPT_LLM_TIMEOUT_S"] == "600"
    assert env["LOCALSCRIPT_LLM_EXTRA_BODY_JSON"] == ""
    assert env["LOCALSCRIPT_RAG_ENABLED"] == "false"
    assert env["LOCALSCRIPT_SANDBOX_EXECUTION_MODE"] == "luac_only"
    assert env["LOCALSCRIPT_VALIDATION_WORKSPACE_TEMPLATE"].endswith(
        "/examples/validation_workspace_template"
    )


def test_profile_env_instruct_research_respects_extra_body_and_timeout(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://example.test:8002/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "m")
    monkeypatch.setenv("LOCALSCRIPT_LLM_EXTRA_BODY_JSON", '{"top_p":0.9}')
    monkeypatch.setenv("LOCALSCRIPT_LLM_TIMEOUT_S", "90")
    env = profile_env("instruct-research")
    assert env["LOCALSCRIPT_LLM_EXTRA_BODY_JSON"] == '{"top_p":0.9}'
    assert env["LOCALSCRIPT_LLM_TIMEOUT_S"] == "90"


def test_cli_instruct_research_exits_2_when_model_missing():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_REPO_ROOT)
    env["LOCALSCRIPT_LLM_BASE_URL"] = "http://example.test:8002/v1"
    env.pop("LOCALSCRIPT_LLM_MODEL", None)
    proc = subprocess.run(
        [sys.executable, str(_REPO_ROOT / "stands" / "run_jury_drill.py"), "--submission-profile", "instruct-research"],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 2
    assert "LOCALSCRIPT_LLM_MODEL" in proc.stderr
