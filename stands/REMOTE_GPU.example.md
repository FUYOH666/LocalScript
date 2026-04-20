# Remote GPU host — example operator notes (template)

**This file is safe to commit:** it uses placeholders only. Copy to `stands/REMOTE_GPU.md` (gitignored) and fill in your real hosts, users, and VPN layout — **never** commit IPs, tokens, or home paths.

## SSH

Configure a host block in `~/.ssh/config` on your workstation, then:

```bash
ssh YOUR_SSH_HOST
```

Non-interactive check:

```bash
ssh -o BatchMode=yes YOUR_SSH_HOST 'whoami && hostname'
```

## Docker on the server

If Docker requires elevated rights:

```bash
ssh YOUR_SSH_HOST 'sudo -n docker ps'
```

Adjust `YOUR_SSH_HOST` and `sudo` policy to match your environment.

## VRAM for Ollama only

On a shared GPU, prefer **per-process** memory from compute apps, not only `memory.used` for the whole card:

```bash
ssh YOUR_SSH_HOST 'nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv,noheader'
```

Pick the row for your **`ollama`** (or container) process. Do not merge unrelated tenants into the same budget unless you intend a whole-GPU report.

## Text artifacts instead of screenshots

Prefer `nvidia-smi --query-*` output to **files** (CSV/XML) for reproducibility.

### GPU identity (one block)

Run on the GPU machine (local session or SSH):

```bash
nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv
```

Optional XML snapshot:

```bash
nvidia-smi -q -x > "gpu-state-$(date -u +%Y%m%dT%H%M%SZ).xml"
```

### Time series: compute apps (CSV)

Run on the GPU host during a load test:

```bash
OUT="compute-apps-$(date -u +%Y%m%dT%H%M%SZ).csv"
: >"$OUT"
for _ in $(seq 1 120); do
  printf '%s,' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$OUT"
  nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv,noheader | paste -sd ';' - >>"$OUT"
  echo >>"$OUT"
  sleep 1
done
```

### Optional: whole-GPU memory context

Not a substitute for per-process lines when the budget is **model-only**:

```bash
OUT="gpu-mem-$(date -u +%Y%m%dT%H%M%SZ).csv"
: >"$OUT"
for _ in $(seq 1 120); do
  printf '%s,' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$OUT"
  nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader >>"$OUT"
  sleep 1
done
```

## With LocalScript benchmark drill

From a machine with the repo and `uv` (point `LOCALSCRIPT_LLM_BASE_URL` at your inference endpoint):

```bash
export LOCALSCRIPT_LLM_BASE_URL=http://YOUR_LLM_HOST:YOUR_PORT/v1
PYTHONPATH=. uv run python stands/run_jury_drill.py --submission-profile ollama-8gb --compact --timeout 600
```

While that runs, capture `nvidia-smi` samples on the GPU host as above.

---

## English summary

Use **SSH placeholders**, commit **no** real hostnames. Prefer **`nvidia-smi --query-compute-apps`** CSV/XML for VRAM evidence. For an **Ollama-only** line item, use the **`ollama` process `used_gpu_memory`**. Operational verification for the stack: [docs/RUNBOOK.md](../docs/RUNBOOK.md).
