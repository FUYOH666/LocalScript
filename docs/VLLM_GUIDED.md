# vLLM / gateway: guided and structured output (spike)

This document records how to **verify** structured generation against **your** OpenAI-compatible gateway (for example instruct on port **8002** behind vLLM). Behavior differs by gateway version and flags; there is **no** portable guarantee until you run the checks below.

## 1. Discover models

```bash
curl -sS "${LOCALSCRIPT_LLM_BASE_URL%/}/models" | jq .
```

Use a model `id` that your stack actually serves.

## 2. Minimal spike: JSON object with a `code` field

Try `response_format` (OpenAI-style) first:

```bash
curl -sS "$LOCALSCRIPT_LLM_BASE_URL/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "YOUR_MODEL_ID",
    "messages": [{"role":"user","content":"Return minimal Lua that prints 1 as JSON with key code"}],
    "temperature": 0,
    "response_format": {"type": "json_object"}
  }' | jq .
```

If the server rejects the field or returns invalid JSON, try **extra body** keys your gateway documents (for example `guided_json`, grammar, or nested under `extra_body`). Map the working payload into:

- `LOCALSCRIPT_LLM_STRUCTURED_OUTPUT=true`
- `LOCALSCRIPT_LLM_STRUCTURED_RESPONSE_FORMAT_JSON='…'` (valid JSON object)
- and/or `LOCALSCRIPT_LLM_EXTRA_BODY_JSON='…'` (JSON object merged into the request body)

LocalScript will parse assistant `content` as JSON and use the **`code`** string when present; otherwise it falls back to ```lua fences.

## 3. Record the working snippet

When you find a combination that returns **parseable JSON** with `"code": "..."`, paste the **exact** request body fragment (without secrets) into this file under a dated heading, for your team.

## 4. Fallback

If structured mode fails at runtime (HTTP error or bad shape), disable `LOCALSCRIPT_LLM_STRUCTURED_OUTPUT` and rely on fenced Lua output.
