import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from localscript import __version__
from localscript.app import app
from localscript.config import get_settings
from localscript.orchestrator import AgentStepLog, GenerateResult


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LOCALSCRIPT_LLM_MODEL", "dummy")
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_ui_page_renders(client):
    r = client.get("/ui")
    assert r.status_code == 200
    assert b"LocalScript" in r.content
    assert b"Submission mode" in r.content
    assert b"Showcase mode" in r.content
    assert b"Trust summary" in r.content


def test_openapi_version_matches_package(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["version"] == __version__
    assert __version__ != "0.0.0"


def test_healthz_degraded_without_llm(client):
    with respx.mock:
        respx.get("http://llm.test/v1/models").mock(return_value=httpx.Response(503))
        r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["llm_ok"] is False
    assert body["status"] == "degraded"


def test_healthz_ok_when_models_reachable(client):
    with respx.mock:
        respx.get("http://llm.test/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["llm_ok"] is True
    assert body.get("rag_ok", True) is True
    assert "validators_ready" in body
    assert body["status"] == ("ok" if body["validators_ready"] else "degraded")


def _patch_successful_generation(monkeypatch):
    async def fake_chain(settings, lua_path):
        from localscript.validate import ValidationResult

        return ValidationResult(ok=True, diagnostics=[], raw_outputs={})

    async def instant_luac(*_a, **_k):
        return True, ""

    monkeypatch.setattr("localscript.orchestrator.run_validation_chain", fake_chain)
    monkeypatch.setattr("localscript.orchestrator.run_sandbox", instant_luac)


def test_generate_endpoint_mocked(client, monkeypatch):
    _patch_successful_generation(monkeypatch)

    with respx.mock:
        respx.post("http://llm.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"content": "```lua\nlocal x = 1\n```"}}]},
            )
        )
        r = client.post(
            "/generate",
            json={"task": "hello"},
            headers={"X-Request-ID": "demo-req-1"},
        )
    assert r.status_code == 200
    assert r.headers.get("x-request-id") == "demo-req-1"
    data = r.json()
    assert data["success"] is True
    assert "local x" in (data.get("code") or "")
    assert data.get("request_id") == "demo-req-1"
    assert "validation_profile" in data
    assert "validation_tools" in data


def test_generate_endpoint_submission_prompt_returns_compact_response(client, monkeypatch):
    _patch_successful_generation(monkeypatch)

    with respx.mock:
        respx.post("http://llm.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"content": "```lua\nreturn 42\n```"}}]},
            )
        )
        r = client.post("/generate", json={"prompt": "Return 42 in Lua"})

    assert r.status_code == 200
    assert r.json() == {"code": "return 42"}


def test_generate_endpoint_showcase_response_includes_evidence(client, monkeypatch):
    _patch_successful_generation(monkeypatch)

    with respx.mock:
        respx.post("http://llm.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"content": "```lua\nlocal x = 1\n```"}}]},
            )
        )
        r = client.post("/generate", json={"task": "hello"})

    assert r.status_code == 200
    data = r.json()
    assert data["surface"] == "showcase"
    assert data["evidence"]["attempts"] == 1
    assert data["evidence"]["final_status"] == "passed"
    assert isinstance(data["evidence"]["checks"], list)


def test_generate_endpoint_rejects_prompt_and_task_together(client):
    r = client.post("/generate", json={"prompt": "hello", "task": "hello"})
    assert r.status_code == 422


def test_generate_endpoint_submission_failure_returns_backend_error(client, monkeypatch):
    async def fake_generate(*_args, **_kwargs):
        return GenerateResult(
            success=False,
            code=None,
            steps=[],
            error="generation failed",
            validation_profile="none",
            validation_tools=[],
        )

    monkeypatch.setattr("localscript.app.generate_lua", fake_generate)
    r = client.post("/generate", json={"prompt": "hello"}, headers={"X-Request-ID": "sub-fail-1"})
    assert r.status_code == 502
    assert r.json() == {"error": "generation failed", "request_id": "sub-fail-1"}


def test_generate_endpoint_showcase_failure_keeps_evidence(client, monkeypatch):
    async def fake_generate(*_args, **_kwargs):
        return GenerateResult(
            success=False,
            code=None,
            steps=[
                AgentStepLog(
                    step=1,
                    assistant_preview="```lua\nbad\n```",
                    validation_ok=False,
                    sandbox_ok=None,
                    diagnostics_summary="[selene] undefined global",
                )
            ],
            error="generation failed",
            validation_profile="partial",
            validation_tools=[
                {"tool": "selene", "status": "failed"},
                {"tool": "luac", "status": "not_run"},
            ],
        )

    monkeypatch.setattr("localscript.app.generate_lua", fake_generate)
    r = client.post("/generate", json={"task": "hello"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert data["evidence"]["final_status"] == "failed"
    assert data["evidence"]["trust_summary"] == "0 passed, 1 failed, 1 skipped"
    assert data["evidence"]["last_diagnostics"] == "[selene] undefined global"


def test_generate_503_when_require_validators_and_none_on_path(client, monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_REQUIRE_VALIDATORS", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("localscript.app.validators_ready", lambda _s: False)
    r = client.post("/generate", json={"task": "hello"})
    assert r.status_code == 503
    body = r.json()
    assert body.get("validators_ready") is False
    assert "detail" in body
    assert body.get("request_id")
