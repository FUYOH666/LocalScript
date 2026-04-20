#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROXY_PORT="${LOCALSCRIPT_GPU_PROXY_PORT:-16666}"

if curl -fsS "http://127.0.0.1:${PROXY_PORT}/v1/models" >/dev/null 2>&1; then
  echo "Demo proxy is already running on http://127.0.0.1:${PROXY_PORT}/v1"
  exit 0
fi

UPSTREAM_BASE_URL="$(
  cd "$REPO_ROOT"
  uv run python - <<'PY'
from urllib.parse import urlparse
from localscript.config import get_settings

host = urlparse(get_settings().llm_base_url_str).hostname
if not host:
    raise SystemExit("Could not determine GPU host from current configuration.")
print(f"http://{host}:6666")
PY
)"

echo "Starting local demo proxy:"
echo "  local  -> http://127.0.0.1:${PROXY_PORT}/v1"
echo "  remote -> ${UPSTREAM_BASE_URL}"

cd "$REPO_ROOT"
exec uv run python -m localscript.demo_proxy \
  --listen-port "$PROXY_PORT" \
  --upstream-base-url "$UPSTREAM_BASE_URL"
