from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx
import numpy as np
from rank_bm25 import BM25Okapi

from localscript.config import Settings
from localscript.rag.embeddings import embed_query
from localscript.rag.index import RagIndex, build_index

logger = logging.getLogger("localscript.rag.retrieve")


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    source_relpath: str
    text: str
    score: float


def _tokenize(s: str) -> list[str]:
    return [t for t in re.split(r"\W+", s.lower()) if t]


def _cosine_topk(
    query_vec: np.ndarray,
    matrix: np.ndarray,
    *,
    k: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (indices, scores) for top-k cosine similarity."""
    q = query_vec.astype(np.float32)
    m = matrix.astype(np.float32)
    qn = np.linalg.norm(q)
    mn = np.linalg.norm(m, axis=1)
    mn = np.where(mn == 0, 1e-9, mn)
    sims = (m @ q) / (mn * max(qn, 1e-9))
    k = min(k, sims.shape[0])
    idx = np.argpartition(-sims, kth=k - 1)[:k]
    idx = idx[np.argsort(-sims[idx])]
    return idx, sims[idx]


async def rerank(
    settings: Settings,
    query: str,
    candidates: list[RetrievedChunk],
    *,
    client: httpx.AsyncClient | None = None,
) -> list[RetrievedChunk]:
    base = settings.rag_reranker_base_url_str
    if not base or not candidates:
        return candidates
    b = base.rstrip("/")
    url = f"{b}/rerank" if b.endswith("/v1") else f"{b}/v1/rerank"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.rag_reranker_api_key:
        headers["Authorization"] = f"Bearer {settings.rag_reranker_api_key}"
    docs = [c.text for c in candidates]
    payload: dict[str, Any] = {
        "query": query,
        "documents": docs,
        "top_n": min(settings.rag_reranker_top_n, len(docs)),
    }
    rm = (settings.rag_reranker_model or "").strip()
    if rm:
        payload["model"] = rm
    own = client is None
    c = client or httpx.AsyncClient(timeout=settings.rag_reranker_timeout_s)
    try:
        r = await c.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("rag_rerank_failed err=%s", e)
        return candidates
    finally:
        if own:
            await c.aclose()
    results = data.get("results")
    if not isinstance(results, list):
        return candidates
    by_idx: dict[int, float] = {}
    doc_ordered: list[tuple[str, float]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        sc = item.get("relevance_score")
        if sc is None:
            sc = item.get("score")
        doc = item.get("document")
        if isinstance(idx, int) and isinstance(sc, (int, float)):
            by_idx[idx] = float(sc)
        elif isinstance(doc, str) and isinstance(sc, (int, float)):
            doc_ordered.append((doc, float(sc)))

    if by_idx:
        reranked: list[RetrievedChunk] = []
        for i, ch in enumerate(candidates):
            reranked.append(
                RetrievedChunk(
                    chunk_id=ch.chunk_id,
                    source_relpath=ch.source_relpath,
                    text=ch.text,
                    score=by_idx.get(i, ch.score),
                )
            )
        reranked.sort(key=lambda x: -x.score)
        return reranked[: settings.rag_top_k]

    if doc_ordered:
        by_text: dict[str, RetrievedChunk] = {}
        for ch in candidates:
            if ch.text not in by_text:
                by_text[ch.text] = ch
        out: list[RetrievedChunk] = []
        seen_ids: set[str] = set()
        for doc, sc in doc_ordered:
            ch = by_text.get(doc)
            if ch is None or ch.chunk_id in seen_ids:
                continue
            seen_ids.add(ch.chunk_id)
            out.append(
                RetrievedChunk(
                    chunk_id=ch.chunk_id,
                    source_relpath=ch.source_relpath,
                    text=ch.text,
                    score=sc,
                )
            )
        for ch in candidates:
            if ch.chunk_id not in seen_ids:
                out.append(ch)
        return out[: settings.rag_top_k]

    return candidates


async def retrieve(
    settings: Settings,
    query: str,
    *,
    index: RagIndex,
    client: httpx.AsyncClient | None = None,
) -> list[RetrievedChunk]:
    qvec = np.asarray(await embed_query(settings, query, client=client), dtype=np.float32)
    pre_k = max(settings.rag_top_k * 4, settings.rag_reranker_top_n)
    n = index.vectors.shape[0]
    pre_k = min(pre_k, n)
    idx_top, dense_scores = _cosine_topk(qvec, index.vectors, k=pre_k)

    indices = idx_top.tolist()
    dense_list = [float(dense_scores[j]) for j in range(len(indices))]

    if settings.rag_hybrid_bm25:
        tokenized = [_tokenize(t) for t in index.texts]
        bm25 = BM25Okapi(tokenized)
        bm25_full = np.asarray(bm25.get_scores(_tokenize(query)), dtype=np.float32)
        bm_list = [float(bm25_full[ii]) for ii in indices]
        d_arr = np.array(dense_list, dtype=np.float32)
        b_arr = np.array(bm_list, dtype=np.float32)
        d_n = (d_arr - d_arr.min()) / max(float(d_arr.max() - d_arr.min()), 1e-9)
        b_n = (b_arr - b_arr.min()) / max(float(b_arr.max() - b_arr.min()), 1e-9)
        hybrid = settings.rag_hybrid_alpha * d_n + (1.0 - settings.rag_hybrid_alpha) * b_n
        scored = [(indices[j], float(hybrid[j])) for j in range(len(indices))]
    else:
        scored = [(indices[j], dense_list[j]) for j in range(len(indices))]

    scored.sort(key=lambda x: -x[1])
    cap = max(settings.rag_reranker_top_n, settings.rag_top_k)
    top_pairs = scored[:cap]

    out = [
        RetrievedChunk(
            chunk_id=index.chunk_ids[ii],
            source_relpath=index.sources[ii],
            text=index.texts[ii],
            score=sc,
        )
        for ii, sc in top_pairs
    ]
    out = await rerank(settings, query, out, client=client)
    logger.info(
        "rag_retrieve top_ids=%s",
        [c.chunk_id for c in out[: settings.rag_top_k]],
    )
    return out[: settings.rag_top_k]


_index_singleton: RagIndex | None = None


async def get_or_build_index(settings: Settings, *, client: httpx.AsyncClient | None = None) -> RagIndex:
    global _index_singleton
    if not settings.rag_enabled:
        raise RuntimeError("RAG disabled")
    if _index_singleton is not None:
        return _index_singleton
    _index_singleton = await build_index(settings, client=client)
    return _index_singleton


def clear_index_cache() -> None:
    global _index_singleton
    _index_singleton = None


async def retrieve_for_task(
    settings: Settings,
    task: str,
    extra_context: str | None,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[RetrievedChunk]:
    if not settings.rag_enabled:
        return []
    q = task.strip()
    if extra_context:
        q = q + "\n" + extra_context.strip()
    index = await get_or_build_index(settings, client=client)
    return await retrieve(settings, q, index=index, client=client)


def format_rag_message(chunks: list[RetrievedChunk]) -> str:
    lines = []
    for c in chunks:
        lines.append(f"--- {c.source_relpath} ({c.chunk_id}) score={c.score:.4f} ---\n{c.text}")
    return "\n\n".join(lines)
