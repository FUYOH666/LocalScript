#!/usr/bin/env python3
"""
E2E stand: starts mock LLM + LocalScript API, runs HTTP scenarios, optional Docker luac check.

Usage (from repo root):
  PYTHONPATH=. uv run python stands/run_e2e.py

Env:
  E2E_MOCK_PORT=18081
  E2E_APP_PORT=18766
  E2E_SKIP_DOCKER=1  — do not run docker luac verification
  E2E_RAG=1  — enable RAG against stands.mock_embedding (starts extra uvicorn on E2E_EMBED_PORT)
  E2E_EMBED_PORT=19001
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("e2e")

ROOT = Path(__file__).resolve().parent.parent


def _wait_tcp(host: str, port: int, timeout_s: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _verify_lua_docker(lua_code: str) -> tuple[str, str | None]:
    if os.environ.get("E2E_SKIP_DOCKER", "").strip().lower() in ("1", "true", "yes"):
        return "skip", "E2E_SKIP_DOCKER set"
    if not shutil.which("docker"):
        return "skip", "docker not in PATH"
    import tempfile

    with tempfile.TemporaryDirectory(prefix="localscript_e2e_") as tmp:
        p = Path(tmp) / "chunk.lua"
        p.write_text(lua_code, encoding="utf-8")
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{tmp}:/w",
            "-w",
            "/w",
            "alpine:3.19",
            "sh",
            "-c",
            "apk add --no-cache lua5.4 >/dev/null && luac5.4 -p chunk.lua",
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return "fail", "docker luac timeout"
        if r.returncode == 0:
            return "pass", None
        return "fail", (r.stderr or r.stdout or "luac failed")[:500]


def _popen(args: list[str], env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        args,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def _terminate(p: subprocess.Popen[str] | None) -> None:
    if p is None or p.poll() is not None:
        return
    p.send_signal(signal.SIGTERM)
    try:
        p.wait(timeout=8)
    except subprocess.TimeoutExpired:
        p.kill()


def _build_env_base() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "").strip(os.pathsep)
    return env


def _isolate_app_env_from_dotenv(env_app: dict[str, str]) -> None:
    """Стабильный E2E не должен тянуть judge/policy/candidates/steps из корневого `.env`."""
    env_app["LOCALSCRIPT_QUALITY_POLICY_ENABLED"] = "false"
    env_app["LOCALSCRIPT_QUALITY_POLICY_PRESET"] = ""
    env_app["LOCALSCRIPT_QUALITY_JUDGE_ENABLED"] = "false"
    env_app["LOCALSCRIPT_GENERATE_CANDIDATES_N"] = "1"
    env_app["LOCALSCRIPT_AGENT_MAX_STEPS"] = "5"
    env_app["LOCALSCRIPT_SANDBOX_EXECUTION_MODE"] = "luac_only"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    mock_port = int(os.environ.get("E2E_MOCK_PORT", "18081"))
    app_port = int(os.environ.get("E2E_APP_PORT", "18766"))
    mock_base = f"http://127.0.0.1:{mock_port}"
    app_base = f"http://127.0.0.1:{app_port}"

    results: list[dict[str, Any]] = []
    mock_proc: subprocess.Popen[str] | None = None
    embed_proc: subprocess.Popen[str] | None = None
    app_proc: subprocess.Popen[str] | None = None

    def cleanup() -> None:
        _terminate(app_proc)
        _terminate(mock_proc)
        _terminate(embed_proc)

    env_base = _build_env_base()
    rag_on = os.environ.get("E2E_RAG", "").strip().lower() in ("1", "true", "yes")
    embed_port = int(os.environ.get("E2E_EMBED_PORT", "19001"))
    embed_base = f"http://127.0.0.1:{embed_port}"

    try:
        # --- Phase 1: happy mock ---
        env_mock = env_base.copy()
        env_mock["MOCK_LLM_MODE"] = "happy"
        mock_proc = _popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "stands.mock_llm:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(mock_port),
            ],
            env_mock,
        )
        env_app = env_base.copy()
        env_app["LOCALSCRIPT_LLM_BASE_URL"] = f"{mock_base}/v1"
        env_app["LOCALSCRIPT_LLM_MODEL"] = "mock-coder"
        env_app["LOCALSCRIPT_LLM_PROBE_TIMEOUT_S"] = "5"
        env_app["LOCALSCRIPT_LLM_TIMEOUT_S"] = "60"
        _isolate_app_env_from_dotenv(env_app)
        if rag_on:
            embed_proc = _popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "stands.mock_embedding:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(embed_port),
                ],
                env_base,
            )
            if not _wait_tcp("127.0.0.1", embed_port):
                results.append({"id": "embed_up", "ok": False, "detail": "mock embedding TCP timeout"})
                print(json.dumps({"results": results}, indent=2, ensure_ascii=False))
                return 1
            env_app["LOCALSCRIPT_RAG_ENABLED"] = "true"
            env_app["LOCALSCRIPT_EMBEDDING_BASE_URL"] = f"{embed_base}/v1"
            env_app["LOCALSCRIPT_EMBEDDING_MODEL"] = "mock-bge"
            env_app["LOCALSCRIPT_RAG_SOURCES_DIR"] = str(ROOT / "examples" / "rag_corpus")
            env_app["LOCALSCRIPT_RAG_TOP_K"] = "3"
            env_app["LOCALSCRIPT_RAG_HYBRID_BM25"] = "true"
        app_proc = _popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "localscript.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(app_port),
            ],
            env_app,
        )

        if not _wait_tcp("127.0.0.1", mock_port):
            results.append({"id": "mock_up", "ok": False, "detail": "mock LLM TCP timeout"})
            print(json.dumps({"results": results}, indent=2, ensure_ascii=False))
            return 1
        if not _wait_tcp("127.0.0.1", app_port):
            err = app_proc.stderr.read() if app_proc.stderr else ""
            results.append({"id": "app_up", "ok": False, "detail": "app TCP timeout", "stderr": err[-2000:]})
            print(json.dumps({"results": results}, indent=2, ensure_ascii=False))
            return 1

        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{app_base}/healthz")
            hz = r.json() if "application/json" in r.headers.get("content-type", "") else {}
            llm_ok = hz.get("llm_ok") if isinstance(hz, dict) else None
            vr = hz.get("validators_ready") if isinstance(hz, dict) else None
            st = hz.get("status") if isinstance(hz, dict) else None
            rag_ok = hz.get("rag_ok") if isinstance(hz, dict) else None
            hz_ok = r.status_code == 200 and llm_ok is True
            if rag_on:
                hz_ok = hz_ok and rag_ok is True
            results.append(
                {
                    "id": "healthz",
                    "ok": hz_ok,
                    "status_code": r.status_code,
                    "llm_ok": llm_ok,
                    "rag_ok": rag_ok,
                    "validators_ready": vr,
                    "health_status": st,
                    "tools": hz.get("tools") if isinstance(hz, dict) else [],
                }
            )

            r2 = client.post(
                f"{app_base}/generate",
                json={"task": "Напиши Lua 5.4: функция add(a,b) и print(add(1,2)).", "context": None},
            )
            g2 = r2.json() if "application/json" in r2.headers.get("content-type", "") else {}
            ok_gen = r2.status_code == 200 and isinstance(g2, dict) and g2.get("success") is True
            code = g2.get("code") if isinstance(g2, dict) else None
            docker_st, docker_msg = _verify_lua_docker(code or "")
            results.append(
                {
                    "id": "generate_happy",
                    "ok": ok_gen,
                    "status_code": r2.status_code,
                    "success": g2.get("success") if isinstance(g2, dict) else None,
                    "steps": len(g2.get("steps") or []) if isinstance(g2, dict) else 0,
                    "docker_luac": docker_st,
                    "docker_detail": docker_msg,
                }
            )

        cleanup()
        mock_proc, app_proc, embed_proc = None, None, None
        time.sleep(0.4)

        if rag_on:
            embed_proc = _popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "stands.mock_embedding:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(embed_port),
                ],
                env_base,
            )
            if not _wait_tcp("127.0.0.1", embed_port):
                results.append(
                    {"id": "embed_up_phase2", "ok": False, "detail": "mock embedding TCP timeout (phase 2)"}
                )
                print(json.dumps({"results": results}, indent=2, ensure_ascii=False))
                return 1

        # --- Phase 2: fix_loop (new mock process, call counter resets) ---
        env_mock2 = env_base.copy()
        env_mock2["MOCK_LLM_MODE"] = "fix_loop"
        mock_proc = _popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "stands.mock_llm:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(mock_port),
            ],
            env_mock2,
        )
        app_proc = _popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "localscript.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(app_port),
            ],
            env_app,
        )

        if not _wait_tcp("127.0.0.1", mock_port) or not _wait_tcp("127.0.0.1", app_port):
            results.append({"id": "fix_loop_up", "ok": False, "detail": "TCP timeout after restart"})
        else:
            with httpx.Client(timeout=120.0) as client:
                r3 = client.post(
                    f"{app_base}/generate",
                    json={"task": "Минимальный валидный Lua.", "context": None},
                )
                g3 = r3.json() if "application/json" in r3.headers.get("content-type", "") else {}
                steps = g3.get("steps") if isinstance(g3, dict) else []
                n = len(steps) if isinstance(steps, list) else 0
                success = g3.get("success") if isinstance(g3, dict) else None
                results.append(
                    {
                        "id": "generate_fix_loop",
                        "ok": r3.status_code == 200,
                        "success": success,
                        "steps": n,
                        "interpretation": (
                            "Expected: 2+ steps if host has luac/stylua/selene/luals catching bad Lua; "
                            "1 step + success means validators skipped (see EVALUATION.md)."
                        ),
                    }
                )

        core_ok = all(
            x.get("ok") for x in results if x.get("id") in ("healthz", "generate_happy")
        )
        print(json.dumps({"results": results, "core_ok": core_ok}, indent=2, ensure_ascii=False))
        return 0 if core_ok else 1

    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
