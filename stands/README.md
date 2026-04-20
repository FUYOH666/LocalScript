# E2E Stand

This stand is the fast regression path for LocalScript.

It starts:

- a mock OpenAI-compatible LLM
- the LocalScript API
- optional mock embeddings
- optional Docker-based syntax check

## Run

```bash
PYTHONPATH=. uv run python stands/run_e2e.py
```

Expected result: `core_ok: true`.

## Useful Flags

| Variable | Purpose |
|----------|---------|
| `E2E_MOCK_PORT` | mock LLM port |
| `E2E_APP_PORT` | LocalScript API port |
| `E2E_SKIP_DOCKER=1` | skip Docker syntax validation |
| `E2E_RAG=1` | start mock embeddings and enable RAG |

Mock LLM modes:

- `MOCK_LLM_MODE=happy`
- `MOCK_LLM_MODE=fix_loop`

## Related Docs

- main verification path: [`../docs/RUNBOOK.md`](../docs/RUNBOOK.md)
- scripted benchmark profiles: [`run_jury_drill.py`](run_jury_drill.py) (`--submission-profile`, `--compact`)
- GPU host / VRAM notes (template): [`REMOTE_GPU.example.md`](REMOTE_GPU.example.md) — copy to gitignored `stands/REMOTE_GPU.md` for private details
