#!/usr/bin/env python3
"""
Benchmark drill: full generate_lua orchestrator with the current .env
(real LLM, RAG if enabled). Does not start HTTP — Python API only.

From repo root:
  PYTHONPATH=. uv run python stands/run_jury_drill.py
  PYTHONPATH=. uv run python stands/run_jury_drill.py --scenarios stands/jury_scenarios.yaml

Profiles:
  --submission-profile ollama-8gb           # lightweight Ollama path (LLM URL: env first, else localhost Ollama)
  --submission-profile qwen7b-local-benchmark  # rich local profile (LM Studio, RAG, docker sandbox, validators)
  --submission-profile instruct-research      # stronger OpenAI-compat: set LOCALSCRIPT_LLM_BASE_URL + LOCALSCRIPT_LLM_MODEL

See docs/RUNBOOK.md §5.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import yaml

from localscript.config import get_settings
from localscript.orchestrator import generate_lua

_ROOT = Path(__file__).resolve().parent
_DEFAULT_SCENARIO_FILE = _ROOT / "jury_scenarios.yaml"

# Fallback если YAML отсутствует
_BUILTIN_SCENARIOS: list[dict[str, str | None]] = [
    {
        "id": "J1_smoke",
        "task": "Lua 5.4: одна строка — вывести в stdout строку 'jury-smoke-ok'.",
        "context": None,
    },
]


def profile_env(profile_name: str) -> dict[str, str]:
    if profile_name == "ollama-8gb":
        # Respect pre-set URL (e.g. remote Ollama on non-default port) — do not hardcode host in .env only flows.
        llm_base = os.environ.get(
            "LOCALSCRIPT_LLM_BASE_URL",
            "http://127.0.0.1:11434/v1",
        )
        return {
            "LOCALSCRIPT_LLM_BASE_URL": llm_base,
            "LOCALSCRIPT_LLM_MODEL": "qwen2.5-coder:7b",
            "LOCALSCRIPT_LLM_MAX_TOKENS": "256",
            "LOCALSCRIPT_LLM_STRUCTURED_OUTPUT": "false",
            "LOCALSCRIPT_LLM_EXTRA_BODY_JSON": json.dumps(
                {"options": {"num_ctx": 4096, "num_batch": 1}},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "LOCALSCRIPT_GENERATE_CANDIDATES_N": "1",
            "LOCALSCRIPT_GENERATE_CANDIDATES_MAX_PARALLEL": "1",
            "LOCALSCRIPT_RAG_ENABLED": "false",
            "LOCALSCRIPT_QUALITY_POLICY_ENABLED": "false",
            "LOCALSCRIPT_QUALITY_JUDGE_ENABLED": "false",
            "LOCALSCRIPT_SANDBOX_EXECUTION_MODE": "luac_only",
            # Workspace template ships selene.toml + localscript_jury.yml (vendored std) so Selene works on Homebrew selene without builtin lua54.
            "LOCALSCRIPT_VALIDATION_WORKSPACE_TEMPLATE": str(
                (_ROOT.parent / "examples" / "validation_workspace_template").resolve()
            ),
        }
    if profile_name == "instruct-research":
        # Same validation/RAG/candidate envelope as ollama-8gb, but no Ollama-specific extra_body.
        # Caller must set base URL and model id from GET /v1/models on the instruct gateway (e.g. vLLM).
        llm_base = (os.environ.get("LOCALSCRIPT_LLM_BASE_URL") or "").strip()
        if not llm_base:
            raise ValueError(
                "instruct-research: set LOCALSCRIPT_LLM_BASE_URL to the OpenAI-compatible "
                "base URL including /v1 (e.g. http://your-host:8002/v1)"
            )
        llm_model = (os.environ.get("LOCALSCRIPT_LLM_MODEL") or "").strip()
        if not llm_model:
            raise ValueError(
                "instruct-research: set LOCALSCRIPT_LLM_MODEL to the served model id "
                "(from GET …/v1/models on that host)"
            )
        extra = (os.environ.get("LOCALSCRIPT_LLM_EXTRA_BODY_JSON") or "").strip()
        timeout_s = (os.environ.get("LOCALSCRIPT_LLM_TIMEOUT_S") or "600").strip()
        return {
            "LOCALSCRIPT_LLM_BASE_URL": llm_base,
            "LOCALSCRIPT_LLM_MODEL": llm_model,
            "LOCALSCRIPT_LLM_MAX_TOKENS": "256",
            "LOCALSCRIPT_LLM_TIMEOUT_S": timeout_s,
            "LOCALSCRIPT_LLM_STRUCTURED_OUTPUT": "false",
            "LOCALSCRIPT_LLM_EXTRA_BODY_JSON": extra,
            "LOCALSCRIPT_GENERATE_CANDIDATES_N": "1",
            "LOCALSCRIPT_GENERATE_CANDIDATES_MAX_PARALLEL": "1",
            "LOCALSCRIPT_RAG_ENABLED": "false",
            "LOCALSCRIPT_QUALITY_POLICY_ENABLED": "false",
            "LOCALSCRIPT_QUALITY_JUDGE_ENABLED": "false",
            "LOCALSCRIPT_SANDBOX_EXECUTION_MODE": "luac_only",
            "LOCALSCRIPT_VALIDATION_WORKSPACE_TEMPLATE": str(
                (_ROOT.parent / "examples" / "validation_workspace_template").resolve()
            ),
        }
    if profile_name == "qwen7b-local-benchmark":
        repo_root = _ROOT.parent.resolve()
        return {
            "LOCALSCRIPT_LLM_BASE_URL": "http://127.0.0.1:1234/v1",
            "LOCALSCRIPT_LLM_MODEL": "qwen2.5-coder-7b-instruct-mlx",
            "LOCALSCRIPT_LLM_MAX_TOKENS": "256",
            "LOCALSCRIPT_LLM_STRUCTURED_OUTPUT": "false",
            "LOCALSCRIPT_LLM_EXTRA_BODY_JSON": "",
            "LOCALSCRIPT_GENERATE_CANDIDATES_N": "1",
            "LOCALSCRIPT_GENERATE_CANDIDATES_MAX_PARALLEL": "1",
            "LOCALSCRIPT_RAG_ENABLED": "true",
            "LOCALSCRIPT_EMBEDDING_BASE_URL": "http://127.0.0.1:1234/v1",
            "LOCALSCRIPT_EMBEDDING_MODEL": "text-embedding-nomic-embed-text-v1.5",
            "LOCALSCRIPT_RAG_SOURCES_DIR": str((repo_root / "examples" / "rag_corpus").resolve()),
            "LOCALSCRIPT_VALIDATION_WORKSPACE_TEMPLATE": str(
                (repo_root / "examples" / "validation_workspace_template").resolve()
            ),
            "LOCALSCRIPT_REQUIRE_VALIDATORS": "true",
            "LOCALSCRIPT_QUALITY_POLICY_ENABLED": "false",
            "LOCALSCRIPT_QUALITY_JUDGE_ENABLED": "false",
            "LOCALSCRIPT_SANDBOX_EXECUTION_MODE": "docker",
        }
    raise ValueError(f"Unknown profile: {profile_name}")


def submission_profile_env(profile_name: str) -> dict[str, str]:
    return profile_env(profile_name)


def load_scenarios(path: Path) -> list[dict[str, str | None]]:
    if not path.is_file():
        return list(_BUILTIN_SCENARIOS)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "scenarios" not in raw:
        raise ValueError(f"YAML must contain top-level 'scenarios' list: {path}")
    items = raw["scenarios"]
    if not isinstance(items, list):
        raise ValueError(f"'scenarios' must be a list: {path}")
    out: list[dict[str, str | None]] = []
    for i, row in enumerate(items):
        if not isinstance(row, dict):
            raise ValueError(f"scenario[{i}] must be a mapping")
        sid = row.get("id")
        task = row.get("task")
        if not isinstance(sid, str) or not isinstance(task, str):
            raise ValueError(f"scenario[{i}] needs string id and task")
        ctx = row.get("context")
        if ctx is not None and not isinstance(ctx, str):
            raise ValueError(f"scenario[{i}] context must be string or null")
        out.append({"id": sid, "task": task, "context": ctx})
    return out


async def run_all(
    scenarios: list[dict[str, str | None]],
    timeout_s: float,
) -> list[dict[str, Any]]:
    get_settings.cache_clear()
    settings = get_settings()
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        for sc in scenarios:
            rid = str(sc["id"])
            t0 = time.perf_counter()
            r = await generate_lua(
                settings,
                str(sc["task"]),
                extra_context=sc["context"],
                client=client,
                request_id=rid,
            )
            dt = time.perf_counter() - t0
            last = r.steps[-1] if r.steps else None
            results.append(
                {
                    "id": rid,
                    "success": r.success,
                    "error": r.error,
                    "seconds": round(dt, 2),
                    "steps": len(r.steps),
                    "validation_profile": r.validation_profile,
                    "last_validation_ok": last.validation_ok if last else None,
                    "last_sandbox_ok": last.sandbox_ok if last else None,
                    "validation_tools": r.validation_tools,
                    "code": r.code,
                    "quality_policy": r.quality_policy,
                    "quality_judge": r.quality_judge,
                    "quality_judge_error": r.quality_judge_error,
                    "generate_candidates_n": r.generate_candidates_n,
                    "candidate_index": r.candidate_index,
                }
            )
    return results


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--scenarios",
        type=Path,
        default=_DEFAULT_SCENARIO_FILE,
        help="YAML with top-level 'scenarios' list (id, task, context?)",
    )
    p.add_argument("--timeout", type=float, default=600.0, help="httpx timeout per process")
    p.add_argument("--compact", action="store_true", help="omit full code in JSON")
    p.add_argument(
        "--submission-profile",
        choices=["ollama-8gb", "qwen7b-local-benchmark", "instruct-research"],
        help=(
            "Apply built-in environment overrides before running scenarios. "
            "For ollama-8gb: set LOCALSCRIPT_LLM_BASE_URL before run to point at a remote "
            "OpenAI-compatible endpoint (non-default port); otherwise defaults to 127.0.0.1:11434. "
            "For instruct-research: set LOCALSCRIPT_LLM_BASE_URL and LOCALSCRIPT_LLM_MODEL "
            "(vLLM/instruct gateway; no Ollama options in extra body unless you set "
            "LOCALSCRIPT_LLM_EXTRA_BODY_JSON yourself)."
        ),
    )
    p.add_argument(
        "--policy",
        action="store_true",
        help="Set LOCALSCRIPT_QUALITY_POLICY_ENABLED=true (use --policy-preset)",
    )
    p.add_argument(
        "--policy-preset",
        type=str,
        default="octapi_stub",
        metavar="NAME",
        help="With --policy: LOCALSCRIPT_QUALITY_POLICY_PRESET (default octapi_stub)",
    )
    p.add_argument(
        "--judge",
        action="store_true",
        help="Set LOCALSCRIPT_QUALITY_JUDGE_ENABLED=true (extra LLM call per successful scenario)",
    )
    args = p.parse_args()
    if args.submission_profile:
        try:
            overrides = profile_env(args.submission_profile)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        for key, value in overrides.items():
            os.environ[key] = value
    if args.policy:
        os.environ["LOCALSCRIPT_QUALITY_POLICY_ENABLED"] = "true"
        os.environ["LOCALSCRIPT_QUALITY_POLICY_PRESET"] = args.policy_preset
    if args.judge:
        os.environ["LOCALSCRIPT_QUALITY_JUDGE_ENABLED"] = "true"
    scenarios = load_scenarios(args.scenarios)
    results = asyncio.run(run_all(scenarios, args.timeout))
    if args.compact:
        for row in results:
            code = row.get("code") or ""
            row["code_lines"] = len(code.splitlines())
            row["code_preview"] = code[:400]
            del row["code"]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    all_ok = all(x.get("success") for x in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
