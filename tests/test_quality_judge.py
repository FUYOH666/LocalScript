from __future__ import annotations

import httpx
import pytest
import respx

from localscript.config import get_settings
from localscript.quality_judge import run_quality_judge


@pytest.mark.asyncio
async def test_run_quality_judge_parses_json(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    get_settings.cache_clear()
    settings = get_settings()

    body = (
        '{"overall": 4, "task_fit": 5, "lua_style": 4, '
        '"stub_compliance": 5, "rationale": "ok"}'
    )
    with respx.mock:
        respx.post("http://llm.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"content": body}}]},
            )
        )
        async with httpx.AsyncClient() as client:
            scores, err = await run_quality_judge(
                settings,
                user_task="print version",
                code="print(octapi.version())",
                client=client,
            )
    assert err is None
    assert scores is not None
    assert scores.overall == 4
    assert scores.stub_compliance == 5
