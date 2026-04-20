from __future__ import annotations

import ipaddress
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BeforeValidator, Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SandboxExecutionMode = Literal["none", "luac_only", "docker"]


def _empty_to_none(v: object) -> Path | None:
    if v is None:
        return None
    if isinstance(v, Path):
        return v.expanduser() if str(v) else None
    if isinstance(v, str) and not v.strip():
        return None
    return Path(str(v).strip()).expanduser()


OptionalPath = Annotated[Path | None, BeforeValidator(_empty_to_none)]
_TAILSCALE_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def _parse_allowed_hosts(raw: str) -> set[str]:
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _host_is_private_or_allowed(host: str, allowed_hosts: set[str]) -> bool:
    lowered = host.strip().lower()
    if not lowered:
        return False
    if lowered in {"localhost", "host.docker.internal"}:
        return True
    if lowered in allowed_hosts:
        return True
    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        if "." not in lowered:
            return True
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip in _TAILSCALE_CGNAT
    )


def _validate_private_endpoint_host(label: str, url: str, allowed_hosts: set[str]) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    if not parsed.scheme or not host:
        raise ValueError(f"{label} must be a valid URL when private host guard is enabled")
    if not _host_is_private_or_allowed(host, allowed_hosts):
        raise ValueError(
            f"{label} host '{host}' is public; set {label} to a private/loopback host "
            "or add it to LOCALSCRIPT_ALLOWED_HOSTS"
        )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOCALSCRIPT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- HTTP API (uvicorn entrypoint) ---
    api_host: str = Field(default="127.0.0.1", description="Bind host for localscript-api")
    api_port: int = Field(default=8765, ge=1, le=65535)
    log_level: str = Field(default="INFO", description="Logging level for uvicorn/root")

    # --- LLM (OpenAI-compatible) ---
    llm_base_url: HttpUrl = Field(
        default="http://127.0.0.1:11434/v1",
        description="Base URL including /v1 if the server uses OpenAI-style paths",
    )
    llm_api_key: str = Field(default="", description="Bearer token if required")
    llm_model: str = Field(default="qwen2.5-coder:7b")
    llm_timeout_s: float = Field(default=120.0, ge=1.0, description="chat/completions timeout")
    llm_probe_timeout_s: float = Field(
        default=10.0,
        ge=1.0,
        description="Timeout for GET .../models in healthz",
    )
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_max_tokens: int | None = Field(
        default=None,
        description="If set, passed as max_tokens to the API (must be >=1 if set)",
    )
    llm_structured_output: bool = Field(
        default=False,
        description="If true, send response_format / extra_body from structured settings; parse JSON code field",
    )
    llm_structured_response_format_json: str = Field(
        default="",
        description="JSON string merged into payload as response_format (OpenAI/vLLM style)",
    )
    llm_extra_body_json: str = Field(
        default="",
        description="JSON object merged into chat/completions request body (e.g. guided_json)",
    )
    enforce_private_hosts: bool = Field(
        default=False,
        description="Reject public endpoint hosts; allow loopback, private IPs, docker-style names, and allowlisted hosts",
    )
    allowed_hosts: str = Field(
        default="",
        description="Comma-separated extra endpoint hosts allowed when ENFORCE_PRIVATE_HOSTS=true",
    )

    # --- Agent loop ---
    agent_max_steps: int = Field(default=5, ge=1, le=20)
    diagnostics_prompt_max_items: int = Field(
        default=20,
        ge=1,
        le=200,
        description="Max diagnostics lines fed back into the model per step",
    )

    # --- Quality policy (deterministic checks on final Lua) ---
    quality_policy_enabled: bool = Field(
        default=False,
        description="If true, evaluate QUALITY_POLICY_PRESET on final code (and for candidate pick)",
    )
    quality_policy_preset: str = Field(
        default="",
        description="Preset name, e.g. octapi_stub (required when QUALITY_POLICY_ENABLED=true)",
    )

    # --- LLM-as-judge (optional second pass on successful code) ---
    quality_judge_enabled: bool = Field(default=False)
    quality_judge_base_url: str = Field(
        default="",
        description="OpenAI-compatible base URL including /v1; empty = same as LLM_BASE_URL",
    )
    quality_judge_model: str = Field(default="", description="Empty = LLM_MODEL")
    quality_judge_timeout_s: float = Field(default=90.0, ge=5.0)
    quality_judge_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    quality_judge_max_tokens: int | None = Field(
        default=512,
        description="Passed to judge chat/completions; omit from request if unset",
    )

    # --- Multi-candidate generation (best-of-K on local LLM) ---
    generate_candidates_n: int = Field(default=1, ge=1, le=8)
    generate_candidates_max_parallel: int = Field(default=2, ge=1, le=8)

    # --- Tool executables (full path or name on PATH; optional extra argv via *_EXTRA_ARGS) ---
    stylua_command: str = Field(default="stylua")
    selene_command: str = Field(default="selene")
    luals_command: str = Field(default="lua-language-server")
    luac_command: str = Field(default="luac")

    stylua_extra_args: str = Field(default="", description="Extra args for stylua (shlex)")
    selene_extra_args: str = Field(default="", description="Extra args for selene (shlex)")
    luals_extra_args: str = Field(default="", description="Extra args for lua-language-server (shlex)")
    luac_extra_args: str = Field(default="", description="Extra args for luac (shlex)")

    stylua_timeout_s: float = Field(default=30.0, ge=1.0)
    selene_timeout_s: float = Field(default=30.0, ge=1.0)
    luals_timeout_s: float = Field(default=120.0, ge=1.0)
    luac_timeout_s: float = Field(default=15.0, ge=1.0)

    path_extra: str = Field(
        default="",
        description="Prepended to PATH for tool subprocesses (os.pathsep-separated)",
    )

    enable_stylua: bool = Field(default=True)
    enable_selene: bool = Field(default=True)
    enable_luals: bool = Field(default=True)
    enable_luac: bool = Field(default=True)

    enable_luacheck: bool = Field(
        default=False,
        description="If true, run luacheck after Selene when executable is available",
    )
    luacheck_command: str = Field(default="luacheck")
    luacheck_extra_args: str = Field(default="", description="Extra args for luacheck (shlex)")
    luacheck_timeout_s: float = Field(default=60.0, ge=1.0)

    # --- RAG (local corpus + BGE embeddings) ---
    rag_enabled: bool = Field(default=False)
    embedding_base_url: str = Field(
        default="",
        description="OpenAI-compatible embeddings API base URL (include /v1 if your server uses it)",
    )
    embedding_api_key: str = Field(default="")
    embedding_model: str = Field(default="BAAI/bge-m3")
    embedding_timeout_s: float = Field(default=30.0, ge=1.0)
    embedding_bge_m3_compat: bool = Field(
        default=False,
        description=(
            "If true: send return_dense=true and omit model in POST body (internal BGE-M3 service); "
            "responses may use data[].dense_embedding instead of embedding"
        ),
    )
    rag_sources_dir: OptionalPath = Field(
        default=None,
        description="Directory of .md/.lua/.txt files to index when rag_enabled",
    )
    rag_top_k: int = Field(default=5, ge=1, le=50)
    rag_max_chunk_chars: int = Field(default=1500, ge=200, le=50_000)
    rag_chunk_overlap: int = Field(default=200, ge=0, le=10_000)
    rag_index_cache_path: OptionalPath = Field(
        default=None,
        description="Optional JSON cache path for chunk texts + embeddings",
    )
    rag_hybrid_bm25: bool = Field(
        default=True,
        description="Fuse dense cosine with BM25 when rank-bm25 is available",
    )
    rag_hybrid_alpha: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Weight for dense similarity in hybrid (1-alpha for BM25)",
    )
    rag_reranker_base_url: str = Field(default="")
    rag_reranker_api_key: str = Field(default="")
    rag_reranker_model: str = Field(default="")
    rag_reranker_top_n: int = Field(default=8, ge=1, le=50)
    rag_reranker_timeout_s: float = Field(default=30.0, ge=1.0)

    # --- Sandbox execution (after static validation passes) ---
    sandbox_execution_mode: SandboxExecutionMode = Field(
        default="luac_only",
        description="none: skip execution check; luac_only: host luac -p; docker: isolated Lua in container",
    )
    sandbox_docker_image: str = Field(
        default="localscript-sandbox:local",
        description="Image built from docker/Dockerfile.sandbox",
    )
    sandbox_docker_timeout_s: float = Field(default=30.0, ge=1.0)
    sandbox_docker_network_disabled: bool = Field(
        default=True,
        description="Pass --network none to docker run when true",
    )

    require_validators: bool = Field(
        default=False,
        description="If true, POST /generate returns 503 when no validation tool is enabled and on PATH",
    )

    validation_workspace_template: OptionalPath = Field(
        default=None,
        description=(
            "If set, contents of this directory are copied into each temp workspace "
            "before validation (selene.toml, .luarc.json, library stubs, etc.)"
        ),
    )

    @model_validator(mode="after")
    def _validate_template_and_tokens(self) -> Settings:
        if self.llm_max_tokens is not None and self.llm_max_tokens < 1:
            raise ValueError("LOCALSCRIPT_LLM_MAX_TOKENS must be >= 1 when set")
        if self.validation_workspace_template is not None and not self.validation_workspace_template.is_dir():
            raise ValueError(
                "LOCALSCRIPT_VALIDATION_WORKSPACE_TEMPLATE must be an existing directory when set"
            )
        if self.rag_enabled:
            if not (self.embedding_base_url or "").strip():
                raise ValueError("LOCALSCRIPT_EMBEDDING_BASE_URL is required when LOCALSCRIPT_RAG_ENABLED=true")
            if self.rag_sources_dir is None or not self.rag_sources_dir.is_dir():
                raise ValueError(
                    "LOCALSCRIPT_RAG_SOURCES_DIR must be an existing directory when LOCALSCRIPT_RAG_ENABLED=true"
                )
        if self.llm_structured_output:
            if not (self.llm_structured_response_format_json or "").strip() and not (
                self.llm_extra_body_json or ""
            ).strip():
                raise ValueError(
                    "When LOCALSCRIPT_LLM_STRUCTURED_OUTPUT=true, set "
                    "LOCALSCRIPT_LLM_STRUCTURED_RESPONSE_FORMAT_JSON and/or LOCALSCRIPT_LLM_EXTRA_BODY_JSON"
                )
        for label, raw in (
            ("LOCALSCRIPT_LLM_STRUCTURED_RESPONSE_FORMAT_JSON", self.llm_structured_response_format_json),
            ("LOCALSCRIPT_LLM_EXTRA_BODY_JSON", self.llm_extra_body_json),
        ):
            if (raw or "").strip():
                try:
                    json.loads(raw)
                except json.JSONDecodeError as e:
                    raise ValueError(f"{label} must be valid JSON") from e
        if self.quality_policy_enabled and not (self.quality_policy_preset or "").strip():
            raise ValueError(
                "LOCALSCRIPT_QUALITY_POLICY_PRESET is required when LOCALSCRIPT_QUALITY_POLICY_ENABLED=true"
            )
        if self.generate_candidates_max_parallel > self.generate_candidates_n:
            raise ValueError(
                "LOCALSCRIPT_GENERATE_CANDIDATES_MAX_PARALLEL must be <= LOCALSCRIPT_GENERATE_CANDIDATES_N"
            )
        if self.quality_judge_max_tokens is not None and self.quality_judge_max_tokens < 1:
            raise ValueError("LOCALSCRIPT_QUALITY_JUDGE_MAX_TOKENS must be >= 1 when set")
        if self.enforce_private_hosts:
            allowed_hosts = _parse_allowed_hosts(self.allowed_hosts)
            _validate_private_endpoint_host(
                "LOCALSCRIPT_LLM_BASE_URL",
                self.llm_base_url_str,
                allowed_hosts,
            )
            for label, raw in (
                ("LOCALSCRIPT_QUALITY_JUDGE_BASE_URL", self.quality_judge_base_url),
                ("LOCALSCRIPT_EMBEDDING_BASE_URL", self.embedding_base_url),
                ("LOCALSCRIPT_RAG_RERANKER_BASE_URL", self.rag_reranker_base_url),
            ):
                if (raw or "").strip():
                    _validate_private_endpoint_host(label, raw.strip(), allowed_hosts)
        return self

    @property
    def llm_base_url_str(self) -> str:
        return str(self.llm_base_url).rstrip("/")

    @property
    def embedding_base_url_str(self) -> str:
        u = (self.embedding_base_url or "").strip().rstrip("/")
        return u

    @property
    def rag_reranker_base_url_str(self) -> str:
        return (self.rag_reranker_base_url or "").strip().rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
