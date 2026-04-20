"""
Minimal OpenAI-compatible mock for E2E stands.

Env:
  MOCK_LLM_MODE=happy   — every completion returns valid Lua (default)
  MOCK_LLM_MODE=fix_loop — first completion invalid Lua, then valid (tests agent retry)
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request

from localscript import __version__

GOOD_LUA = """```lua
local function add(a, b)
  return a + b
end
print(add(1, 2))
```"""

BAD_LUA = """```lua
local x =
```"""

app = FastAPI(title="LocalScript Mock LLM", version=__version__)
_calls = 0


@app.get("/v1/models")
def models() -> dict:
    return {"data": [{"id": "mock-coder", "object": "model"}]}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict:
    global _calls
    _calls += 1
    await request.json()  # consume body
    mode = os.environ.get("MOCK_LLM_MODE", "happy").strip().lower()
    if mode == "fix_loop" and _calls == 1:
        content = BAD_LUA
    else:
        content = GOOD_LUA
    return {
        "id": "mock-chunk",
        "object": "chat.completion",
        "model": "mock-coder",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }


@app.post("/internal/reset")
def reset() -> dict:
    global _calls
    _calls = 0
    return {"ok": True, "calls": 0}
