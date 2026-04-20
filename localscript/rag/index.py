from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from localscript.config import Settings
from localscript.rag.chunking import load_corpus_chunks
from localscript.rag.embeddings import embed_texts

logger = logging.getLogger("localscript.rag.index")


def _fingerprint_sources(root: Path) -> str:
    root = root.resolve()
    lines: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".lua", ".txt"}:
            continue
        if path.name.startswith("."):
            continue
        try:
            rel = path.relative_to(root).as_posix()
            st = path.stat()
            lines.append(f"{rel}\t{st.st_mtime_ns}\t{st.st_size}")
        except OSError:
            continue
    blob = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@dataclass
class RagIndex:
    embedding_model: str
    fingerprint: str
    chunk_ids: list[str]
    texts: list[str]
    sources: list[str]
    vectors: np.ndarray  # shape (n, dim), float32

    def to_serializable(self) -> dict[str, Any]:
        return {
            "embedding_model": self.embedding_model,
            "fingerprint": self.fingerprint,
            "chunk_ids": self.chunk_ids,
            "texts": self.texts,
            "sources": self.sources,
            "vectors": self.vectors.astype(float).tolist(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RagIndex:
        vecs = data.get("vectors")
        if not isinstance(vecs, list):
            raise ValueError("cache missing vectors")
        arr = np.asarray(vecs, dtype=np.float32)
        return cls(
            embedding_model=str(data.get("embedding_model", "")),
            fingerprint=str(data.get("fingerprint", "")),
            chunk_ids=list(data.get("chunk_ids") or []),
            texts=list(data.get("texts") or []),
            sources=list(data.get("sources") or []),
            vectors=arr,
        )


def save_index(path: Path, index: RagIndex) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(index.to_serializable(), ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    logger.info("rag_index_saved path=%s chunks=%s", path, len(index.chunk_ids))


def try_load_cache(
    settings: Settings,
    *,
    fingerprint: str,
) -> RagIndex | None:
    cache_path = settings.rag_index_cache_path
    if cache_path is None:
        return None
    if not cache_path.is_file():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        if data.get("fingerprint") != fingerprint:
            logger.info("rag_cache_fingerprint_mismatch")
            return None
        if data.get("embedding_model") != settings.embedding_model:
            logger.info("rag_cache_model_mismatch")
            return None
        idx = RagIndex.from_dict(data)
        if idx.vectors.ndim != 2 or idx.vectors.shape[0] != len(idx.texts):
            return None
        logger.info("rag_index_loaded_cache path=%s chunks=%s", cache_path, len(idx.texts))
        return idx
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.warning("rag_cache_load_failed err=%s", e)
        return None


async def build_index(
    settings: Settings,
    *,
    client: Any | None = None,
) -> RagIndex:
    root = settings.rag_sources_dir
    assert root is not None
    fp = _fingerprint_sources(root)
    cached = try_load_cache(settings, fingerprint=fp)
    if cached is not None:
        return cached

    chunks = load_corpus_chunks(
        root,
        max_chars=settings.rag_max_chunk_chars,
        overlap=settings.rag_chunk_overlap,
    )
    if not chunks:
        raise RuntimeError(f"no RAG chunks under {root}")

    texts = [c.text for c in chunks]
    batch = 32
    all_vecs: list[list[float]] = []
    for i in range(0, len(texts), batch):
        part = texts[i : i + batch]
        all_vecs.extend(await embed_texts(settings, part, client=client))

    arr = np.asarray(all_vecs, dtype=np.float32)
    index = RagIndex(
        embedding_model=settings.embedding_model,
        fingerprint=fp,
        chunk_ids=[c.chunk_id for c in chunks],
        texts=texts,
        sources=[c.source_relpath for c in chunks],
        vectors=arr,
    )
    if settings.rag_index_cache_path is not None:
        save_index(settings.rag_index_cache_path, index)
    return index
