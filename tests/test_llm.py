import json

import httpx
import pytest
import respx

from localscript.config import get_settings
from localscript.llm import chat_completion


@pytest.mark.asyncio
async def test_chat_completion_merges_extra_body_without_structured_output(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    monkeypatch.setenv("LOCALSCRIPT_LLM_STRUCTURED_OUTPUT", "false")
    monkeypatch.setenv(
        "LOCALSCRIPT_LLM_EXTRA_BODY_JSON",
        '{"options":{"num_ctx":4096,"num_batch":1}}',
    )
    get_settings.cache_clear()

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "```lua\nreturn 1\n```"}}]},
        )

    with respx.mock:
        respx.post("http://llm.test/v1/chat/completions").mock(side_effect=handler)
        result = await chat_completion(
            get_settings(),
            [{"role": "user", "content": "Return 1"}],
        )

    assert result == "```lua\nreturn 1\n```"
    assert captured["payload"]["options"] == {"num_ctx": 4096, "num_batch": 1}
    assert "response_format" not in captured["payload"]
