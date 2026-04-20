import httpx
import pytest
import respx

from localscript.config import Settings, get_settings
from localscript.orchestrator import generate_lua
from localscript.validate import Diagnostic, ValidationResult


@pytest.mark.asyncio
async def test_generate_success_one_round(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    get_settings.cache_clear()

    async def fake_chain(settings: Settings, lua_path):
        text = lua_path.read_text(encoding="utf-8")
        if "FIX" in text:
            return ValidationResult(ok=True, diagnostics=[], raw_outputs={})
        return ValidationResult(
            ok=False,
            diagnostics=[Diagnostic("test", 1, "need fix", "error")],
            raw_outputs={},
        )

    async def instant_luac(*args, **kwargs):
        return True, ""

    monkeypatch.setattr("localscript.orchestrator.run_validation_chain", fake_chain)
    monkeypatch.setattr("localscript.orchestrator.run_sandbox", instant_luac)

    settings = get_settings()
    with respx.mock:
        respx.post("http://llm.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": "```lua\nlocal FIX = 1\n```"}},
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as client:
            result = await generate_lua(settings, "write lua", client=client)

    assert result.success is True
    assert result.code is not None
    assert "FIX" in result.code


@pytest.mark.asyncio
async def test_generate_llm_error(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    get_settings.cache_clear()
    settings = get_settings()

    with respx.mock:
        respx.post("http://llm.test/v1/chat/completions").mock(return_value=httpx.Response(500, text="boom"))
        async with httpx.AsyncClient() as client:
            result = await generate_lua(settings, "task", client=client)

    assert result.success is False
    assert result.error


@pytest.mark.asyncio
async def test_generate_max_steps(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    monkeypatch.setenv("LOCALSCRIPT_AGENT_MAX_STEPS", "2")
    get_settings.cache_clear()

    async def always_bad(settings, lua_path):
        return ValidationResult(
            ok=False,
            diagnostics=[Diagnostic("t", 1, "e", "error")],
            raw_outputs={},
        )

    monkeypatch.setattr("localscript.orchestrator.run_validation_chain", always_bad)

    settings = get_settings()
    with respx.mock:
        respx.post("http://llm.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"content": "```lua\nbad\n```"}}]},
            )
        )
        async with httpx.AsyncClient() as client:
            result = await generate_lua(settings, "task", client=client)

    assert result.success is False
    assert len(result.steps) == 2


@pytest.mark.asyncio
async def test_generate_best_of_two_prefers_cleaner_policy(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    monkeypatch.setenv("LOCALSCRIPT_GENERATE_CANDIDATES_N", "2")
    monkeypatch.setenv("LOCALSCRIPT_GENERATE_CANDIDATES_MAX_PARALLEL", "1")
    monkeypatch.setenv("LOCALSCRIPT_QUALITY_POLICY_ENABLED", "true")
    monkeypatch.setenv("LOCALSCRIPT_QUALITY_POLICY_PRESET", "octapi_stub")
    get_settings.cache_clear()

    async def fake_chain(settings, lua_path):
        from localscript.validate import ValidationResult

        return ValidationResult(ok=True, diagnostics=[], raw_outputs={})

    async def instant_luac(*_a, **_k):
        return True, ""

    monkeypatch.setattr("localscript.orchestrator.run_validation_chain", fake_chain)
    monkeypatch.setattr("localscript.orchestrator.run_sandbox", instant_luac)

    payloads = [
        {"choices": [{"message": {"content": '```lua\nrequire("octapi")\nprint(1)\n```'}}]},
        {"choices": [{"message": {"content": "```lua\nprint(octapi.version())\n```"}}]},
    ]

    def side_effect(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payloads.pop(0))

    settings = get_settings()
    with respx.mock:
        respx.post("http://llm.test/v1/chat/completions").mock(side_effect=side_effect)
        async with httpx.AsyncClient() as client:
            result = await generate_lua(settings, "show octapi version", client=client)

    assert result.success is True
    assert result.generate_candidates_n == 2
    assert result.candidate_index == 1
    assert "octapi.version()" in (result.code or "")
    assert result.quality_policy is not None
    assert result.quality_policy.get("passed") is True
