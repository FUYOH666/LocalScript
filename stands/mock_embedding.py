#!/usr/bin/env python3
"""
Tiny OpenAI-compatible embeddings server for E2E / local tests.

Usage:
  uvicorn stands.mock_embedding:app --host 127.0.0.1 --port 19001
"""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import FastAPI

app = FastAPI(title="mock-embedding")

_DIM = 32


def _vec_for_text(text: str) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    return [float((h[i % len(h)] + i) % 97) / 97.0 for i in range(_DIM)]


@app.post("/v1/embeddings")
async def embeddings(body: dict[str, Any]) -> dict[str, Any]:
    inp = body.get("input")
    if isinstance(inp, str):
        texts = [inp]
    elif isinstance(inp, list):
        texts = [str(x) for x in inp]
    else:
        texts = [""]
    want_dense = bool(body.get("return_dense"))
    data: list[dict[str, Any]] = []
    for i, t in enumerate(texts):
        v = _vec_for_text(t)
        row: dict[str, Any] = {"object": "embedding", "index": i, "embedding": v}
        if want_dense:
            row["dense_embedding"] = v
        data.append(row)
    return {
        "object": "list",
        "data": data,
        "model": body.get("model", "mock-embedding"),
    }
