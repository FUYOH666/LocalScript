from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from localscript.config import Settings

logger = logging.getLogger("localscript.llm")


class LLMError(Exception):
    pass


async def chat_completion(
    settings: Settings,
    messages: list[dict[str, str]],
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Call OpenAI-compatible chat completions; return assistant message content."""
    url = f"{settings.llm_base_url_str}/chat/completions"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    payload: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": settings.llm_temperature,
    }
    if settings.llm_max_tokens is not None:
        payload["max_tokens"] = settings.llm_max_tokens
    extra_raw = (settings.llm_extra_body_json or "").strip()
    if extra_raw:
        extra = json.loads(extra_raw)
        if not isinstance(extra, dict):
            raise LLMError("LLM_EXTRA_BODY_JSON must be a JSON object")
        for k, v in extra.items():
            payload[k] = v
    if settings.llm_structured_output:
        rf_raw = (settings.llm_structured_response_format_json or "").strip()
        if rf_raw:
            payload["response_format"] = json.loads(rf_raw)
    own_client = client is None
    c = client or httpx.AsyncClient(timeout=settings.llm_timeout_s)
    try:
        r = await c.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPStatusError as e:
        body = e.response.text[:2000] if e.response is not None else ""
        logger.exception("llm_http_error status=%s body=%s", e.response.status_code if e.response else None, body)
        raise LLMError(f"LLM HTTP {e.response.status_code if e.response else '?'}: {body}") from e
    except httpx.RequestError as e:
        logger.exception("llm_request_error")
        raise LLMError(f"LLM request failed: {e}") from e
    finally:
        if own_client:
            await c.aclose()
    try:
        choice = data["choices"][0]
        msg = choice["message"]
        content = msg.get("content") or ""
        if not isinstance(content, str):
            raise LLMError("LLM returned non-string content")
        return content
    except (KeyError, IndexError, TypeError) as e:
        logger.error("llm_bad_shape data_keys=%s", list(data) if isinstance(data, dict) else type(data))
        raise LLMError(f"Unexpected LLM response shape: {e}") from e


async def chat_completion_custom(
    *,
    base_url_str: str,
    model: str,
    api_key: str,
    timeout_s: float,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    """OpenAI-compatible chat/completions at an explicit base URL (e.g. dedicated judge endpoint)."""
    base = base_url_str.rstrip("/")
    url = f"{base}/chat/completions"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    own_client = client is None
    c = client or httpx.AsyncClient(timeout=timeout_s)
    try:
        r = await c.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPStatusError as e:
        body = e.response.text[:2000] if e.response is not None else ""
        logger.exception(
            "llm_custom_http_error status=%s body=%s",
            e.response.status_code if e.response else None,
            body,
        )
        raise LLMError(f"LLM HTTP {e.response.status_code if e.response else '?'}: {body}") from e
    except httpx.RequestError as e:
        logger.exception("llm_custom_request_error")
        raise LLMError(f"LLM request failed: {e}") from e
    finally:
        if own_client:
            await c.aclose()
    try:
        choice = data["choices"][0]
        msg = choice["message"]
        content = msg.get("content") or ""
        if not isinstance(content, str):
            raise LLMError("LLM returned non-string content")
        return content
    except (KeyError, IndexError, TypeError) as e:
        logger.error("llm_custom_bad_shape data_keys=%s", list(data) if isinstance(data, dict) else type(data))
        raise LLMError(f"Unexpected LLM response shape: {e}") from e


async def probe_models(settings: Settings, client: httpx.AsyncClient | None = None) -> tuple[bool, str | None]:
    """Return (ok, error_message)."""
    url = f"{settings.llm_base_url_str}/models"
    headers: dict[str, str] = {}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    own = client is None
    c = client or httpx.AsyncClient(timeout=settings.llm_probe_timeout_s)
    try:
        r = await c.get(url, headers=headers)
        if r.status_code >= 400:
            return False, f"GET /models -> {r.status_code}"
        return True, None
    except httpx.RequestError as e:
        return False, str(e)
    finally:
        if own:
            await c.aclose()
