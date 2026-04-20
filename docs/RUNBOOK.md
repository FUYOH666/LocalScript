# LocalScript Runbook

This is the single verification path for the repository. If you only need one operational document, use this one.

Goal: verify that the project is reproducible, that `/healthz` tells the truth, and that `/generate` behaves correctly in both mock and real local setups.

## 0. Runtime paths (two ways to run the same code)

The repository is **one codebase**. What changes is **how you run it**:

1. **Day-to-day development** (e.g. MacBook + **LM Studio** or another OpenAI-compatible server on localhost, often `http://127.0.0.1:1234/v1`). Use `uv run localscript-api` and edit `.env` from [`.env.example`](../.env.example). For a rich local profile (RAG, Docker sandbox, full validators), use the built-in drill profile **`qwen7b-local-benchmark`** via `stands/run_jury_drill.py` (see § 5). `LOCALSCRIPT_LLM_MODEL` must match the model id **your** server exposes; do not blindly paste Ollama tags if you are on LM Studio. Avoid Ollama-specific `LOCALSCRIPT_LLM_EXTRA_BODY_JSON` `options` when talking to non-Ollama servers.

2. **Reproducible stack** — **Docker Compose + Ollama** from [`../docker-compose.yml`](../docker-compose.yml), same API image and pinned-style env as in § 4 (`ollama-8gb` profile via drill). Use this for a clean-room check or when you want a containerized path instead of `uv run` on the host.

This is **not** a second product version or “API v2”; it is two **environment paths**.

Operational checks without a real LLM: § 1–2 below (lint, pytest, mock E2E).

## 1. Engineering Baseline

Run these first:

```bash
uv sync --all-extras
uv run ruff check .
uv run pytest -q
```

Expected result:

- lint is clean
- tests are green
- `/healthz`, `/generate`, strict 503 behavior, and request id handling are covered by tests

If you changed the local RAG corpus, clear the embedding cache before further checks:

```bash
rm -f .rag_index_cache.json
```

Or remove the path configured in `LOCALSCRIPT_RAG_INDEX_CACHE_PATH`.

## 2. Mock E2E Stand

Run the regression stand with the mock OpenAI-compatible LLM:

```bash
PYTHONPATH=. uv run python stands/run_e2e.py
```

Expected result:

- `core_ok: true`
- health reports an honest validator state
- happy-path generation succeeds
- optional Docker syntax check passes when Docker is available

Useful flags:

- `E2E_SKIP_DOCKER=1`
- `E2E_RAG=1`
- `E2E_MOCK_PORT`
- `E2E_APP_PORT`

See [`../stands/README.md`](../stands/README.md) for stand-only details.

### 2.1 Docker Compose (Ollama + API)

From the repo root, use [`../docker-compose.yml`](../docker-compose.yml): first-time `docker compose up -d ollama`, then `docker compose exec ollama ollama pull qwen2.5-coder:7b`, then `docker compose up --build -d` (see comments in the compose file). Use this when you want a containerized stack rather than `uv run` on the host.

### 2.2 Clean clone with Docker only (manual)

Simulate someone who has **no** project-specific `.env` and only Docker:

1. Create a fresh directory, clone the repo, `cd` into it (do **not** copy your home `.env`).
2. Follow § 2.1 above (Ollama pull once, then `docker compose up --build -d`).
3. Optional automated check: [`../scripts/jury_compose_smoke.sh`](../scripts/jury_compose_smoke.sh) from repo root (`bash scripts/jury_compose_smoke.sh`). First run pulls the model and may take many minutes; re-runs: `JURY_SMOKE_SKIP_PULL=1 bash scripts/jury_compose_smoke.sh`.

**FAQ — common mismatches vs a “warm” dev laptop**

| Symptom | Likely cause | Mitigation |
|---------|----------------|------------|
| `/healthz` shows `llm_ok: false` | Model not pulled into the Ollama volume | Run `docker compose exec ollama ollama pull qwen2.5-coder:7b` and wait until it finishes. |
| `validators_ready: false` in compose API | Unexpected: image ships `luac5.4` | Rebuild API: `docker compose build --no-cache api`. |
| Port 11434 / 8765 already in use | Another Ollama or API on host | Stop the other service or change published ports in a local override file (not committed). |
| Very slow first generation | CPU-only Ollama on a small machine | Expected; increase timeouts; wait until it completes. |
| `qwen7b-local-benchmark` fails on a clean box | Needs LM Studio / RAG / Docker on host | Use Docker stack + `ollama-8gb` profile (§ 4) for a self-contained reproduction. |
| `POST /generate` → 502, body says **model not found** after smoke with `JURY_SMOKE_SKIP_PULL=1` | Fresh empty Ollama volume, pull was skipped | First successful run **without** skip, or `docker compose exec ollama ollama pull qwen2.5-coder:7b` before relying on skip; see § 2.1–2.2. |

## 3. Real Local Demo Path

Prepare `.env`:

- set `LOCALSCRIPT_LLM_BASE_URL`
- set `LOCALSCRIPT_LLM_MODEL`
- ensure at least one validator is available on `PATH` or via `LOCALSCRIPT_PATH_EXTRA`
- for honest demo behavior, prefer `LOCALSCRIPT_REQUIRE_VALIDATORS=true`

Start the API:

```bash
uv run localscript-api
```

In another terminal:

```bash
curl -sS "http://127.0.0.1:${LOCALSCRIPT_API_PORT:-8765}/healthz" | jq .
curl -sS -X POST "http://127.0.0.1:${LOCALSCRIPT_API_PORT:-8765}/generate" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: demo-1" \
  -d '{"prompt":"Write a Lua 5.4 function twice(x) that returns x * 2"}' | jq .
curl -sS -X POST "http://127.0.0.1:${LOCALSCRIPT_API_PORT:-8765}/generate" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: demo-2" \
  -d '{"task":"Lua 5.4: функция twice(x), которая возвращает x * 2","context":null}' | jq .
```

Expected result:

- `/healthz` shows real model status and validator availability
- submission mode returns a compact code-only response on success
- submission mode returns non-200 JSON with `error` and `request_id` on backend failure
- showcase mode returns code plus validation metadata and step trace
- `X-Request-ID` is preserved

## 4. Lightweight Ollama profile (`ollama-8gb`)

Fixed lightweight settings aligned with a small-GPU Ollama setup:

```bash
ollama pull qwen2.5-coder:7b
export OLLAMA_NUM_PARALLEL=1
ollama serve
```

Then run LocalScript with the fixed profile:

```bash
LOCALSCRIPT_LLM_BASE_URL=http://127.0.0.1:11434/v1 \
LOCALSCRIPT_LLM_MODEL=qwen2.5-coder:7b \
LOCALSCRIPT_LLM_MAX_TOKENS=256 \
LOCALSCRIPT_LLM_EXTRA_BODY_JSON='{"options":{"num_ctx":4096,"num_batch":1}}' \
LOCALSCRIPT_GENERATE_CANDIDATES_N=1 \
LOCALSCRIPT_GENERATE_CANDIDATES_MAX_PARALLEL=1 \
LOCALSCRIPT_RAG_ENABLED=false \
LOCALSCRIPT_QUALITY_POLICY_ENABLED=false \
LOCALSCRIPT_QUALITY_JUDGE_ENABLED=false \
uv run localscript-api
```

Parameter mapping:

- `num_ctx=4096`
- `num_predict=256` → `LOCALSCRIPT_LLM_MAX_TOKENS=256`
- `batch=1` → `options.num_batch` in `LOCALSCRIPT_LLM_EXTRA_BODY_JSON`
- `parallel=1` → `LOCALSCRIPT_GENERATE_CANDIDATES_N=1` and `LOCALSCRIPT_GENERATE_CANDIDATES_MAX_PARALLEL=1`

Or run the same profile via drill (see § 5): `PYTHONPATH=. uv run python stands/run_jury_drill.py --submission-profile ollama-8gb --compact --timeout 600`.

## 5. Benchmark drill profiles

Built-in profiles in `stands/run_jury_drill.py` include:

- **`ollama-8gb`** — lightweight path (§ 4); good for Compose + Ollama.
- **`qwen7b-local-benchmark`** — stronger local path: LM Studio on `:1234`, RAG, Docker sandbox, StyLua + Selene + LuaLS; Selene uses `examples/validation_workspace_template/localscript_jury.yml` so Homebrew `selene` without builtin `lua54` still runs.
- **`instruct-research`** — optional research-oriented profile for a stronger OpenAI-compatible endpoint (configure URL/model in your `.env`).

Example:

```bash
PYTHONPATH=. uv run python stands/run_jury_drill.py --submission-profile qwen7b-local-benchmark --compact --timeout 180
```

Frozen compact JSON snapshots live under `stands/results/*.compact.json`.

## 6. Strict Validator Gate

When `LOCALSCRIPT_REQUIRE_VALIDATORS=true` and no enabled validators are available, `POST /generate` must fail with `503`.

This protects demos from fake green runs where the model succeeds only because nothing actually checked the code.

The behavior is covered by automated tests, but it is still worth understanding before demo day.

## 7. Optional Stronger Modes

### Docker Sandbox

Use when you want a stronger runtime gate than host `luac -p`.

- build the image from [`../docker/README.md`](../docker/README.md)
- set `LOCALSCRIPT_SANDBOX_EXECUTION_MODE=docker`
- confirm `/healthz` reports `sandbox_docker_available: true`

### Local RAG

Use when you want domain hints, stubs, or task patterns from a local corpus.

- point `LOCALSCRIPT_RAG_SOURCES_DIR` at a local corpus
- set `LOCALSCRIPT_EMBEDDING_BASE_URL`
- optionally enable reranking
- verify `/healthz` reports `rag_ok: true`

For scripted runs against your stack, use `stands/run_jury_drill.py` with the appropriate `--submission-profile`.

## 8. Demo Checklist

| Check | Target |
|-------|--------|
| Lint | `uv run ruff check .` |
| Tests | `uv run pytest -q` |
| Mock E2E | `PYTHONPATH=. uv run python stands/run_e2e.py` |
| Health | `status=ok` or an intentional, explained degraded state |
| Submission request | compact `{"code": ...}` path works |
| Showcase request | rich response with steps and validation metadata works |
| Docs | root [`README.md`](../README.md), this runbook (§ 2.1–2.2), [`README.md`](README.md), [`ARCHITECTURE_C4.md`](ARCHITECTURE_C4.md) are consistent |

## 9. Known Limits

- `lua-language-server --check` behavior may vary by installed version
- `luac_only` is lighter but weaker than Docker sandbox
- optional RAG and judge layers are not the same as the minimal core path
- if validators are missing and strict mode is off, a model answer may look successful without a real static gate
