# LocalScript Docker images

## API image (`Dockerfile.api`)

OpenAPI + `/generate` + `/healthz` for containerized runs. Includes **Lua 5.4** (`luac5.4`) only; StyLua/Selene/LuaLS are turned off in the image defaults so `/generate` still has a real `luac` gate.

Важно: этот Docker API-образ соответствует **лёгкому профилю** (`ollama-8gb` в `stands/run_jury_drill.py`) и не претендует на полный validator stack. Полный путь с StyLua/Selene/LuaLS описан в [`../docs/RUNBOOK.md`](../docs/RUNBOOK.md) §5.

Build from the **repository root**:

```bash
docker build -f docker/Dockerfile.api -t localscript-api:local .
```

Full stack with Ollama: use the root [`docker-compose.yml`](../docker-compose.yml) (see comments there for the one-time model pull). Automated smoke from repo root: [`../scripts/jury_compose_smoke.sh`](../scripts/jury_compose_smoke.sh) (see [`../docs/RUNBOOK.md`](../docs/RUNBOOK.md) § 2.2).

## Sandbox image (`Dockerfile.sandbox`)

Isolated **Lua 5.4** run with `load(..., "t", safe_env)` and stub `octapi` (see `safe_run.lua`).

## Build

From the **repository root**:

```bash
docker build -f docker/Dockerfile.sandbox -t localscript-sandbox:local .
```

## Run (manual)

```bash
echo 'print("hi")' > /tmp/main.lua
docker run --rm -v /tmp:/work:ro -w /work --network none \
  localscript-sandbox:local lua5.4 /opt/sandbox/safe_run.lua /work/main.lua
```

Configure the app with `LOCALSCRIPT_SANDBOX_EXECUTION_MODE=docker` and `LOCALSCRIPT_SANDBOX_DOCKER_IMAGE=localscript-sandbox:local`.
