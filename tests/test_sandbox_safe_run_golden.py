"""
Golden expectations for stdout/stderr of docker/safe_run.lua (Lua 5.4 restricted env).

На CI и машинах без lua5.4 тесты пропускаются. Локально: brew install lua (или пакет с lua5.4 в PATH).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SAFE_RUN = _REPO_ROOT / "docker" / "safe_run.lua"

_LUA54 = shutil.which("lua5.4")


def _run_safe_run(lua_source: str) -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".lua",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(lua_source)
        path = Path(f.name)
    try:
        return subprocess.run(
            [_LUA54, str(_SAFE_RUN), str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.skipif(not _LUA54, reason="lua5.4 not on PATH (install Lua 5.4 to run golden tests)")
def test_golden_print_octapi_version_stdout():
    proc = _run_safe_run("print(octapi.version())")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "1.0.0"


@pytest.mark.skipif(not _LUA54, reason="lua5.4 not on PATH")
def test_golden_octapi_connect_flow_stdout():
    proc = _run_safe_run(
        'local h = octapi.connect("relay")\nh:send("ping")\nh:close()\n'
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln.strip() for ln in proc.stdout.strip().splitlines() if ln.strip()]
    assert lines == [
        "[octapi.connect stub] relay",
        "[octapi.send stub] ping",
        "[octapi.close stub]",
    ]


@pytest.mark.skipif(not _LUA54, reason="lua5.4 not on PATH")
def test_golden_require_octapi_fails():
    proc = _run_safe_run('require("octapi")')
    assert proc.returncode != 0
    combined = (proc.stderr + proc.stdout).lower()
    assert "require" in combined or "nil" in combined or "attempt to" in combined
