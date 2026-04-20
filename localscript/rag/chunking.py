from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("localscript.rag.chunking")

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    source_relpath: str
    text: str
    start_char: int


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _chunk_text(
    text: str,
    *,
    max_chars: int,
    overlap: int,
    base_id: str,
) -> list[TextChunk]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [TextChunk(chunk_id=f"{base_id}::0", source_relpath="", text=text, start_char=0)]

    chunks: list[TextChunk] = []
    start = 0
    idx = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        piece = text[start:end].strip()
        if piece:
            chunks.append(
                TextChunk(
                    chunk_id=f"{base_id}::{idx}",
                    source_relpath="",
                    text=piece,
                    start_char=start,
                )
            )
            idx += 1
        if end >= n:
            break
        start = max(0, end - overlap)
        if start <= chunks[-1].start_char if chunks else -1:
            start = end
    return chunks


def chunk_markdown_like(
    raw: str,
    *,
    source_relpath: str,
    max_chars: int,
    overlap: int,
) -> list[TextChunk]:
    """Split by markdown headings when present; otherwise paragraphs and length."""
    raw = raw.strip()
    if not raw:
        return []

    headings = list(_MD_HEADING.finditer(raw))
    if not headings:
        return _chunk_text(
            raw,
            max_chars=max_chars,
            overlap=overlap,
            base_id=source_relpath.replace("/", "_"),
        )

    sections: list[tuple[str, str]] = []
    for i, m in enumerate(headings):
        title = m.group(2).strip()
        sec_start = m.start()
        sec_end = headings[i + 1].start() if i + 1 < len(headings) else len(raw)
        body = raw[sec_start:sec_end].strip()
        sections.append((title, body if body else title))

    out: list[TextChunk] = []
    for si, (_title, body) in enumerate(sections):
        base_id = f"{source_relpath.replace('/', '_')}::h{si}"
        for c in _chunk_text(body, max_chars=max_chars, overlap=overlap, base_id=base_id):
            out.append(
                TextChunk(
                    chunk_id=c.chunk_id,
                    source_relpath=source_relpath,
                    text=c.text,
                    start_char=c.start_char,
                )
            )
    return out


def chunk_plain_file(
    raw: str,
    *,
    source_relpath: str,
    max_chars: int,
    overlap: int,
) -> list[TextChunk]:
    ext = Path(source_relpath).suffix.lower()
    if ext == ".md":
        return chunk_markdown_like(
            raw,
            source_relpath=source_relpath,
            max_chars=max_chars,
            overlap=overlap,
        )
    paras = _split_paragraphs(raw)
    if not paras:
        paras = [raw.strip()] if raw.strip() else []
    out: list[TextChunk] = []
    for pi, p in enumerate(paras):
        base_id = f"{source_relpath.replace('/', '_')}::p{pi}"
        for c in _chunk_text(p, max_chars=max_chars, overlap=overlap, base_id=base_id):
            out.append(
                TextChunk(
                    chunk_id=c.chunk_id,
                    source_relpath=source_relpath,
                    text=c.text,
                    start_char=c.start_char,
                )
            )
    return out


def load_corpus_chunks(
    root: Path,
    *,
    max_chars: int,
    overlap: int,
) -> list[TextChunk]:
    root = root.resolve()
    exts = {".md", ".lua", ".txt"}
    chunks: list[TextChunk] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in exts:
            continue
        if path.name.startswith("."):
            continue
        try:
            rel = path.relative_to(root).as_posix()
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("rag_skip_file path=%s err=%s", path, e)
            continue
        for c in chunk_plain_file(
            raw,
            source_relpath=rel,
            max_chars=max_chars,
            overlap=overlap,
        ):
            chunks.append(c)
    logger.info("rag_corpus_loaded root=%s chunks=%s", root, len(chunks))
    return chunks
