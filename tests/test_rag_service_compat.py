"""BGE-M3 / reranker response shapes (internal stack from Cursor skills)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from localscript.config import get_settings
from localscript.rag.embeddings import embed_texts
from localscript.rag.retrieve import RetrievedChunk, rerank


@pytest.mark.asyncio
async def test_embed_accepts_dense_embedding_only(monkeypatch, tmp_path):
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    monkeypatch.setenv("LOCALSCRIPT_RAG_ENABLED", "true")
    monkeypatch.setenv("LOCALSCRIPT_EMBEDDING_BASE_URL", "http://emb.test")
    monkeypatch.setenv("LOCALSCRIPT_RAG_SOURCES_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()
    with respx.mock:
        respx.post("http://emb.test/v1/embeddings").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"index": 0, "dense_embedding": [0.0, 1.0, 0.5]}]},
            )
        )
        out = await embed_texts(settings, ["hello"])
    assert out == [[0.0, 1.0, 0.5]]


@pytest.mark.asyncio
async def test_embed_bge_compat_sends_return_dense_no_model(monkeypatch, tmp_path):
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    monkeypatch.setenv("LOCALSCRIPT_RAG_ENABLED", "true")
    monkeypatch.setenv("LOCALSCRIPT_EMBEDDING_BASE_URL", "http://emb.test")
    monkeypatch.setenv("LOCALSCRIPT_EMBEDDING_BGE_M3_COMPAT", "true")
    monkeypatch.setenv("LOCALSCRIPT_RAG_SOURCES_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()
    captured: dict = {}

    def real_handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"data": [{"index": 0, "dense_embedding": [1.0, 0.0]}]})

    with respx.mock:
        respx.post("http://emb.test/v1/embeddings").mock(side_effect=real_handler)
        await embed_texts(settings, ["a"])

    assert captured["body"].get("return_dense") is True
    assert "model" not in captured["body"]


@pytest.mark.asyncio
async def test_rerank_bge_document_order(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_RAG_RERANKER_BASE_URL", "http://rr.test")
    monkeypatch.setenv("LOCALSCRIPT_RAG_TOP_K", "3")
    get_settings.cache_clear()
    settings = get_settings()
    candidates = [
        RetrievedChunk("1", "a.md", "second", 0.1),
        RetrievedChunk("2", "b.md", "first", 0.2),
    ]
    with respx.mock:
        respx.post("http://rr.test/v1/rerank").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"document": "first", "relevance_score": 0.99},
                        {"document": "second", "relevance_score": 0.5},
                    ]
                },
            )
        )
        out = await rerank(settings, "q", candidates)
    assert [c.text for c in out] == ["first", "second"]
