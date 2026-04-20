import tempfile
from pathlib import Path

import pytest

from localscript.config import get_settings
from localscript.sandbox import run_sandbox


@pytest.mark.asyncio
async def test_run_sandbox_none_mode(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_SANDBOX_EXECUTION_MODE", "none")
    get_settings.cache_clear()
    settings = get_settings()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".lua", delete=False, encoding="utf-8") as f:
        f.write("local x = 1\n")
        p = Path(f.name)
    try:
        ok, msg = await run_sandbox(settings, p)
    finally:
        p.unlink(missing_ok=True)
    assert ok is True
    assert "none" in msg.lower()


@pytest.mark.asyncio
async def test_run_docker_invokes_docker_cli(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_SANDBOX_EXECUTION_MODE", "docker")
    monkeypatch.setenv("LOCALSCRIPT_SANDBOX_DOCKER_IMAGE", "testimg:tag")
    get_settings.cache_clear()
    settings = get_settings()

    calls: list[list[str]] = []

    class _P:
        returncode = 0

        async def communicate(self):
            return b"out", b""

        async def wait(self):
            return 0

        def kill(self) -> None:
            pass

    async def fake_exec(*cmd: str, **_kw):
        calls.append(list(cmd))
        return _P()

    monkeypatch.setattr("localscript.sandbox.asyncio.create_subprocess_exec", fake_exec)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".lua", delete=False, encoding="utf-8") as f:
        f.write("print(1)\n")
        p = Path(f.name)
    try:
        ok, msg = await run_sandbox(settings, p)
    finally:
        p.unlink(missing_ok=True)

    assert ok is True
    assert calls and calls[0][0] == "docker"
    assert "testimg:tag" in calls[0]
    assert "--network" in calls[0] and "none" in calls[0]
