from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field

from localscript import __version__
from localscript.config import Settings, get_settings
from localscript.llm import probe_models
from localscript.orchestrator import generate_lua
from localscript.rag.embeddings import probe_embeddings
from localscript.sandbox import probe_docker_available
from localscript.validation_report import build_evidence_summary, summarize_validators_for_settings
from localscript.validate import tool_availability, validators_ready

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("localscript.app")

app = FastAPI(title="LocalScript", version=__version__)

_templates_dir = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


class ShowcaseGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str = Field(..., min_length=1, max_length=50_000)
    context: str | None = Field(default=None, max_length=100_000)


class SubmissionGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, max_length=50_000)


class EvidenceSummary(BaseModel):
    attempts: int
    correction_loop_used: bool
    final_status: Literal["passed", "failed"]
    validation_profile: str
    checks: list[dict] = Field(default_factory=list)
    passed_checks: list[str] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    skipped_checks: list[str] = Field(default_factory=list)
    trust_summary: str
    last_diagnostics: str | None = None
    error: str | None = None


class GenerateResponse(BaseModel):
    surface: Literal["showcase"] = "showcase"
    request_id: str = ""
    success: bool
    code: str | None = None
    error: str | None = None
    validation_profile: str = Field(
        default="none",
        description="none | partial | full — see validation_tools",
    )
    validation_tools: list[dict] = Field(default_factory=list)
    steps: list[dict] = Field(default_factory=list)
    quality_policy: dict | None = Field(
        default=None,
        description="Deterministic preset checks when LOCALSCRIPT_QUALITY_POLICY_ENABLED=true",
    )
    quality_judge: dict | None = Field(
        default=None,
        description="LLM judge scores when LOCALSCRIPT_QUALITY_JUDGE_ENABLED=true",
    )
    quality_judge_error: str | None = None
    generate_candidates_n: int | None = Field(
        default=None,
        description="How many parallel/sequential candidates were tried (best-of-K)",
    )
    candidate_index: int | None = Field(
        default=None,
        description="0-based index of the selected candidate among K runs",
    )
    evidence: EvidenceSummary | None = None


class SubmissionGenerateResponse(BaseModel):
    code: str


class HealthResponse(BaseModel):
    status: str
    llm_ok: bool
    llm_error: str | None = None
    rag_ok: bool = Field(default=True, description="False when RAG enabled and embedding probe fails")
    rag_error: str | None = None
    sandbox_docker_available: bool | None = Field(
        default=None,
        description="Set when SANDBOX_EXECUTION_MODE=docker: docker CLI reachable",
    )
    sandbox_docker_error: str | None = None
    validators_ready: bool = Field(
        default=False,
        description="True if at least one validation tool is enabled and on PATH",
    )
    tools: list[dict]


def settings_dep() -> Settings:
    return get_settings()


@app.get("/healthz", response_model=HealthResponse)
async def healthz(settings: Annotated[Settings, Depends(settings_dep)]) -> HealthResponse:
    llm_ok, llm_err = await probe_models(settings)
    rag_ok = True
    rag_err = None
    if settings.rag_enabled:
        rag_ok, rag_err = await probe_embeddings(settings)
    sandbox_docker_available: bool | None = None
    sandbox_docker_error: str | None = None
    if settings.sandbox_execution_mode == "docker":
        sandbox_docker_available, sandbox_docker_error = await probe_docker_available()
    checks = tool_availability(settings)
    vr = validators_ready(settings)
    docker_bad = settings.sandbox_execution_mode == "docker" and sandbox_docker_available is False
    overall = "ok" if (llm_ok and vr and rag_ok and not docker_bad) else "degraded"
    return HealthResponse(
        status=overall,
        llm_ok=llm_ok,
        llm_error=llm_err,
        rag_ok=rag_ok,
        rag_error=rag_err,
        sandbox_docker_available=sandbox_docker_available,
        sandbox_docker_error=sandbox_docker_error,
        validators_ready=vr,
        tools=[
            {
                "name": c.name,
                "enabled": c.enabled,
                "available": c.available,
                "reason": c.reason,
            }
            for c in checks
        ],
    )


@app.get("/ui")
async def ui(
    request: Request,
    settings: Annotated[Settings, Depends(settings_dep)],
):
    return templates.TemplateResponse(
        request,
        "ui.html",
        {"default_port": settings.api_port},
    )


@app.post("/generate", response_model=GenerateResponse | SubmissionGenerateResponse)
async def generate(
    request: Request,
    body: ShowcaseGenerateRequest | SubmissionGenerateRequest,
    settings: Annotated[Settings, Depends(settings_dep)],
) -> GenerateResponse | SubmissionGenerateResponse | JSONResponse:
    rid = getattr(request.state, "request_id", str(uuid.uuid4()))
    if isinstance(body, SubmissionGenerateRequest):
        user_task = body.prompt
        extra_context = None
        response_surface = "submission"
    else:
        user_task = body.task
        extra_context = body.context
        response_surface = "showcase"

    logger.info(
        "generate request_id=%s surface=%s task_bytes=%s require_validators=%s",
        rid,
        response_surface,
        len(user_task.encode("utf-8")),
        settings.require_validators,
    )
    vr = validators_ready(settings)
    if settings.require_validators and not vr:
        detail = summarize_validators_for_settings(settings)
        detail["validators_ready"] = vr
        detail["request_id"] = rid
        detail["detail"] = (
            "No validation tools are enabled and available on PATH; "
            "set LOCALSCRIPT_REQUIRE_VALIDATORS=false for dev or install stylua/selene/lua-language-server/luac."
        )
        return JSONResponse(status_code=503, content=detail)

    result = await generate_lua(
        settings,
        user_task,
        extra_context=extra_context,
        request_id=rid,
    )
    if response_surface == "submission":
        if result.success and result.code:
            return SubmissionGenerateResponse(code=result.code)
        return JSONResponse(
            status_code=502,
            content={"error": result.error or "generation failed", "request_id": rid},
        )

    steps = [
        {
            "step": s.step,
            "assistant_preview": s.assistant_preview,
            "validation_ok": s.validation_ok,
            "sandbox_ok": s.sandbox_ok,
            "diagnostics_summary": s.diagnostics_summary,
        }
        for s in result.steps
    ]
    evidence = build_evidence_summary(
        success=result.success,
        steps=steps,
        validation_profile=result.validation_profile,
        validation_tools=result.validation_tools,
        error=result.error,
    )
    return GenerateResponse(
        surface="showcase",
        request_id=rid,
        success=result.success,
        code=result.code,
        error=result.error,
        validation_profile=result.validation_profile,
        validation_tools=result.validation_tools,
        steps=steps,
        quality_policy=result.quality_policy,
        quality_judge=result.quality_judge,
        quality_judge_error=result.quality_judge_error,
        generate_candidates_n=result.generate_candidates_n,
        candidate_index=result.candidate_index,
        evidence=EvidenceSummary.model_validate(evidence),
    )


def run() -> None:
    import logging as std_logging

    import uvicorn

    s = get_settings()
    std_logging.getLogger().setLevel(s.log_level.upper())
    uvicorn.run(
        "localscript.app:app",
        host=s.api_host,
        port=s.api_port,
        log_level=s.log_level.lower(),
        reload=False,
    )
