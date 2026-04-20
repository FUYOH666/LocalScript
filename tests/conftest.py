import pytest

from localscript.config import get_settings

_RAG_ENV_KEYS = (
    "LOCALSCRIPT_EMBEDDING_BASE_URL",
    "LOCALSCRIPT_RAG_SOURCES_DIR",
    "LOCALSCRIPT_RAG_INDEX_CACHE_PATH",
    "LOCALSCRIPT_RAG_RERANKER_BASE_URL",
)


@pytest.fixture(autouse=True)
def _test_env_over_dotenv(monkeypatch):
    """
    Локальный .env может включать RAG и реальные хосты; в тестах — моки (respx),
    если конкретный тест не переопределит переменные через свой monkeypatch.
    """
    get_settings.cache_clear()
    monkeypatch.setenv("LOCALSCRIPT_RAG_ENABLED", "false")
    monkeypatch.setenv("LOCALSCRIPT_EMBEDDING_BGE_M3_COMPAT", "false")
    monkeypatch.setenv("LOCALSCRIPT_SANDBOX_EXECUTION_MODE", "luac_only")
    monkeypatch.setenv("LOCALSCRIPT_GENERATE_CANDIDATES_N", "1")
    monkeypatch.setenv("LOCALSCRIPT_GENERATE_CANDIDATES_MAX_PARALLEL", "1")
    for key in _RAG_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key in (
        "LOCALSCRIPT_QUALITY_POLICY_ENABLED",
        "LOCALSCRIPT_QUALITY_POLICY_PRESET",
        "LOCALSCRIPT_QUALITY_JUDGE_ENABLED",
        "LOCALSCRIPT_QUALITY_JUDGE_BASE_URL",
        "LOCALSCRIPT_QUALITY_JUDGE_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    yield
    get_settings.cache_clear()
