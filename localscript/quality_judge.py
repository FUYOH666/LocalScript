from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from pydantic import BaseModel, Field, model_validator

from localscript.config import Settings
from localscript.llm import LLMError, chat_completion_custom

logger = logging.getLogger("localscript.quality_judge")


class JudgeScores(BaseModel):
    """Structured LLM-as-judge output (1–5, higher is better)."""

    model_config = {"extra": "ignore"}

    overall: int = Field(ge=1, le=5)
    task_fit: int = Field(ge=1, le=5)
    lua_style: int = Field(ge=1, le=5)
    stub_compliance: int = Field(ge=1, le=5)
    rationale: str = Field(default="", max_length=2000)

    @model_validator(mode="before")
    @classmethod
    def _coerce_score_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        for k in ("overall", "task_fit", "lua_style", "stub_compliance"):
            if k in out and out[k] is not None:
                try:
                    out[k] = int(round(float(out[k])))
                except (TypeError, ValueError):
                    pass
        return out


_JUDGE_SYSTEM = """You are a strict code reviewer for Lua 5.4 snippets.
Respond with ONE JSON object only (no markdown fences). Keys and types:
- "overall": integer 1-5
- "task_fit": integer 1-5 (does the code plausibly do what the user asked)
- "lua_style": integer 1-5 (idiomatic Lua 5.4, clarity)
- "stub_compliance": integer 1-5 (if the task implies a fictional global API "octapi" without require, penalize require("octapi") or os.exit)
- "rationale": short string in English or Russian
"""


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}\s*$", text)
    if not m:
        m2 = re.search(r"\{[\s\S]*\}", text)
        if not m2:
            raise ValueError("no JSON object in judge response")
        blob = m2.group(0)
    else:
        blob = m.group(0)
    return json.loads(blob)


async def run_quality_judge(
    settings: Settings,
    *,
    user_task: str,
    code: str,
    client: httpx.AsyncClient | None = None,
) -> tuple[JudgeScores | None, str | None]:
    """
    Optional second LLM call. Returns (scores, error_message).
    """
    base = (settings.quality_judge_base_url or "").strip().rstrip("/")
    if not base:
        base = settings.llm_base_url_str
    model = (settings.quality_judge_model or "").strip() or settings.llm_model
    user_msg = f"User task:\n{user_task.strip()}\n\nLua code:\n```lua\n{code}\n```\n"
    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    try:
        raw = await chat_completion_custom(
            base_url_str=base,
            model=model,
            api_key=settings.llm_api_key,
            timeout_s=settings.quality_judge_timeout_s,
            messages=messages,
            temperature=settings.quality_judge_temperature,
            max_tokens=settings.quality_judge_max_tokens,
            client=client,
        )
        data = _extract_json_object(raw)
        scores = JudgeScores.model_validate(data)
        return scores, None
    except (LLMError, ValueError, json.JSONDecodeError) as e:
        err = str(e)
        logger.warning("quality_judge_failed err=%s", err)
        return None, err
    except Exception as e:
        err = str(e)
        logger.exception("quality_judge_unexpected")
        return None, err


def judge_to_dict(scores: JudgeScores) -> dict[str, Any]:
    return scores.model_dump()
