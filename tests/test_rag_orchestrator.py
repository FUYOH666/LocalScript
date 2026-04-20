import httpx
import pytest
import respx

from localscript.config import Settings, get_settings
from localscript.orchestrator import generate_lua
from localscript.rag.retrieve import RetrievedChunk


@pytest.mark.asyncio
async def test_rag_injects_retrieved_block(monkeypatch, tmp_path):
    (tmp_path / "placeholder.txt").write_text("corpus", encoding="utf-8")
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    monkeypatch.setenv("LOCALSCRIPT_RAG_ENABLED", "true")
    monkeypatch.setenv("LOCALSCRIPT_EMBEDDING_BASE_URL", "http://emb.test/v1")
    monkeypatch.setenv("LOCALSCRIPT_RAG_SOURCES_DIR", str(tmp_path))
    get_settings.cache_clear()

    async def fake_retrieve(settings: Settings, task: str, extra_context, *, client=None):
        return [
            RetrievedChunk(
                chunk_id="t1",
                source_relpath="stub.md",
                text="octapi.connect is documented here for RAG test",
                score=0.42,
            )
        ]

    async def fake_chain(settings: Settings, lua_path):
        from localscript.validate import ValidationResult

        return ValidationResult(ok=True, diagnostics=[], raw_outputs={})

    async def instant_sandbox(*_a, **_k):
        return True, ""

    captured: list[list[dict[str, str]]] = []

    async def spy_chat(settings: Settings, messages: list[dict[str, str]], *, client=None):
        captured.append(list(messages))
        return "```lua\nlocal RAG_OK = 1\n```"

    monkeypatch.setattr("localscript.orchestrator.retrieve_for_task", fake_retrieve)
    monkeypatch.setattr("localscript.orchestrator.run_validation_chain", fake_chain)
    monkeypatch.setattr("localscript.orchestrator.run_sandbox", instant_sandbox)
    monkeypatch.setattr("localscript.orchestrator.chat_completion", spy_chat)

    settings = get_settings()
    async with httpx.AsyncClient() as client:
        result = await generate_lua(settings, "task about octapi", client=client)

    assert result.success is True
    assert captured
    flat = "\n".join(m.get("content", "") for m in captured[0])
    assert "Retrieved reference" in flat
    assert "octapi.connect" in flat


@pytest.mark.asyncio
async def test_embeddings_probe_mocked(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_RAG_ENABLED", "true")
    monkeypatch.setenv("LOCALSCRIPT_EMBEDDING_BASE_URL", "http://emb.test/v1")
    monkeypatch.setenv("LOCALSCRIPT_RAG_SOURCES_DIR", "/nope")
    get_settings.cache_clear()
    # invalid dir would fail Settings() — use real tmp
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("LOCALSCRIPT_RAG_SOURCES_DIR", tmp)
        get_settings.cache_clear()
        from localscript.rag.embeddings import probe_embeddings

        settings = get_settings()
        with respx.mock:
            respx.post("http://emb.test/v1/embeddings").mock(
                return_value=httpx.Response(
                    200,
                    json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]},
                )
            )
            ok, err = await probe_embeddings(settings)
        assert ok is True
        assert err is None
