from pathlib import Path

import pytest

from localscript.config import get_settings
from localscript.validate import run_luals, run_stylua


@pytest.mark.asyncio
async def test_run_stylua_formats_in_place_before_other_validators(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALSCRIPT_STYLUA_COMMAND", "stylua")
    get_settings.cache_clear()
    settings = get_settings()

    lua_path = tmp_path / "main.lua"
    lua_path.write_text('print( "jury-smoke-ok" )\n', encoding="utf-8")

    monkeypatch.setattr("localscript.validate.is_executable_available", lambda *_a, **_k: (True, None))

    captured = {}

    async def fake_run(cmd: list[str], cwd: Path, timeout: float, env: dict[str, str]):
        captured["cmd"] = cmd
        target = cwd / cmd[-1]
        if "--check" in cmd:
            return 1, "", "would reformat main.lua"
        target.write_text('print("jury-smoke-ok")\n', encoding="utf-8")
        return 0, "", ""

    monkeypatch.setattr("localscript.validate._run", fake_run)

    result = await run_stylua(settings, lua_path)

    assert result.ok is True
    assert "--check" not in captured["cmd"]
    assert lua_path.read_text(encoding="utf-8") == 'print("jury-smoke-ok")\n'


@pytest.mark.asyncio
async def test_run_luals_accepts_human_readable_success_output(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALSCRIPT_LUALS_COMMAND", "lua-language-server")
    get_settings.cache_clear()
    settings = get_settings()

    lua_path = tmp_path / "main.lua"
    lua_path.write_text('print("jury-smoke-ok")\n', encoding="utf-8")

    monkeypatch.setattr("localscript.validate.is_executable_available", lambda *_a, **_k: (True, None))

    async def fake_run(cmd: list[str], cwd: Path, timeout: float, env: dict[str, str]):
        return 0, "Initializing ...\nDiagnosis completed, no problems found\n", ""

    monkeypatch.setattr("localscript.validate._run", fake_run)

    result = await run_luals(settings, lua_path)

    assert result.ok is True
    assert result.diagnostics == []
