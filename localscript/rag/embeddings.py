from __future__ import annotations

import logging
from typing import Any

import httpx

from localscript.config import Settings

logger = logging.getLogger("localscript.rag.embeddings")


def embeddings_url(settings: Settings) -> str:
    base = settings.embedding_base_url_str
    if base.endswith("/v1"):
        return f"{base}/embeddings"
    return f"{base}/v1/embeddings"


async def embed_texts(
    settings: Settings,
    texts: list[str],
    *,
    client: httpx.AsyncClient | None = None,
) -> list[list[float]]:
    if not texts:
        return []
    url = embeddings_url(settings)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.embedding_api_key:
        headers["Authorization"] = f"Bearer {settings.embedding_api_key}"
    payload: dict[str, Any] = {"input": texts}
    if settings.embedding_bge_m3_compat:
        payload["return_dense"] = True
    if not settings.embedding_bge_m3_compat:
        payload["model"] = settings.embedding_model
    own = client is None
    c = client or httpx.AsyncClient(timeout=settings.embedding_timeout_s)
    try:
        r = await c.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPStatusError as e:
        body = e.response.text[:2000] if e.response is not None else ""
        logger.exception(
            "embeddings_http_error status=%s body=%s",
            e.response.status_code if e.response else None,
            body,
        )
        raise RuntimeError(f"embeddings HTTP {e.response.status_code if e.response else '?'}: {body}") from e
    except httpx.RequestError as e:
        logger.exception("embeddings_request_error")
        raise RuntimeError(f"embeddings request failed: {e}") from e
    finally:
        if own:
            await c.aclose()

    out: list[list[float]] = []
    emb_data = data.get("data")
    if not isinstance(emb_data, list):
        raise RuntimeError("embeddings response missing data[]")
    for item in sorted(emb_data, key=lambda x: x.get("index", 0) if isinstance(x, dict) else 0):
        if not isinstance(item, dict):
            continue
        vec = item.get("dense_embedding")
        if not isinstance(vec, list):
            vec = item.get("embedding")
        if not isinstance(vec, list):
            continue
        out.append([float(x) for x in vec])
    if len(out) != len(texts):
        raise RuntimeError(f"embeddings count mismatch: got {len(out)} expected {len(texts)}")
    return out


async def embed_query(
    settings: Settings,
    query: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[float]:
    vecs = await embed_texts(settings, [query], client=client)
    return vecs[0]


async def probe_embeddings(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[bool, str | None]:
    """Light probe: single embedding call. Used from /healthz when RAG is enabled."""
    try:
        await embed_texts(settings, ["localscript_healthz"], client=client)
        return True, None
    except RuntimeError as e:
        return False, str(e)
