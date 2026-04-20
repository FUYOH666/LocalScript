#!/usr/bin/env bash
# Smoke-test Docker Compose stack (Ollama + LocalScript API) as a jury might run it.
# From repo root (or any cwd): bash scripts/jury_compose_smoke.sh
#
# Env:
#   JURY_SMOKE_BASE_URL      default http://127.0.0.1:8765
#   JURY_SMOKE_SKIP_PULL=1   skip ollama pull (model already in volume)
#   JURY_SMOKE_TEARDOWN=1    docker compose down --remove-orphans after success
#   JURY_SMOKE_HEALTH_WAIT_S max seconds waiting for llm_ok (default 300)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE="${JURY_SMOKE_BASE_URL:-http://127.0.0.1:8765}"
MAX_WAIT="${JURY_SMOKE_HEALTH_WAIT_S:-300}"
DC=(docker compose)

echo "[jury-smoke] repo root: $ROOT"
"${DC[@]}" config -q
echo "[jury-smoke] compose config OK"

echo "[jury-smoke] building api image..."
"${DC[@]}" build api

echo "[jury-smoke] starting ollama..."
"${DC[@]}" up -d ollama

echo "[jury-smoke] waiting for Ollama HTTP..."
ollama_deadline=$((SECONDS + 60))
while true; do
  if curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    break
  fi
  if (( SECONDS > ollama_deadline )); then
    echo "[jury-smoke] ERROR: Ollama did not become ready on :11434 within 60s" >&2
    exit 1
  fi
  sleep 1
done

if [[ "${JURY_SMOKE_SKIP_PULL:-0}" != "1" ]]; then
  echo "[jury-smoke] pulling qwen2.5-coder:7b (first run can take several minutes)..."
  "${DC[@]}" exec -T ollama ollama pull qwen2.5-coder:7b
else
  echo "[jury-smoke] skipping ollama pull (JURY_SMOKE_SKIP_PULL=1)"
fi

echo "[jury-smoke] starting full stack..."
"${DC[@]}" up --build -d

echo "[jury-smoke] waiting for /healthz (llm_ok + validators_ready)..."
deadline=$((SECONDS + MAX_WAIT))
last_body=""
while true; do
  if ! last_body=$(curl -sf "$BASE/healthz" 2>/dev/null); then
    last_body=""
  fi
  if echo "$last_body" | grep -qE '"llm_ok"[[:space:]]*:[[:space:]]*true' \
    && echo "$last_body" | grep -qE '"validators_ready"[[:space:]]*:[[:space:]]*true'; then
    echo "[jury-smoke] /healthz OK"
    break
  fi
  if (( SECONDS > deadline )); then
    echo "[jury-smoke] ERROR: /healthz did not report llm_ok+validators_ready within ${MAX_WAIT}s" >&2
    echo "$last_body" >&2
    exit 1
  fi
  sleep 3
done

echo "[jury-smoke] POST /generate (submission surface)..."
gen_path="${TMPDIR:-/tmp}/localscript_jury_gen_$$.json"
http_code=$(curl -sS -o "$gen_path" -w "%{http_code}" -X POST "$BASE/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Lua 5.4 one line: print(42)"}' || true)

if [[ "$http_code" != "200" ]]; then
  echo "[jury-smoke] ERROR: POST /generate HTTP $http_code" >&2
  cat "$gen_path" >&2 || true
  exit 1
fi
if ! grep -q '"code"' "$gen_path"; then
  echo "[jury-smoke] ERROR: response JSON missing \"code\" field" >&2
  cat "$gen_path" >&2
  exit 1
fi

rm -f "$gen_path"
echo "[jury-smoke] SUCCESS: compose stack responds; /generate returned 200 with code."

if [[ "${JURY_SMOKE_TEARDOWN:-0}" == "1" ]]; then
  echo "[jury-smoke] tearing down..."
  "${DC[@]}" down --remove-orphans
fi
