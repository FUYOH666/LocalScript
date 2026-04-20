# Сопоставление с внутренним стеком Local AI (Cursor skills)

Этот проект использует **свои** переменные с префиксом `LOCALSCRIPT_*`. Ниже — как сопоставить их с общими именами из skills (**`LOCAL_AI_*`**) и что проверить на практике.  
**В репозиторий не коммитьте** реальные внутренние IP и хосты; подставляйте свои значения только в локальный `.env`.

## LLM (instruct / vLLM за gateway)

| Skill / привычка | LocalScript |
|------------------|-------------|
| `LOCAL_AI_LLM_INSTRUCT_BASE_URL` (часто `http://…:8002` + путь `/v1`) | `LOCALSCRIPT_LLM_BASE_URL` — тот же базовый URL, **с суффиксом `/v1`**, если сервер отдаёт OpenAI-стиль под `/v1` |
| Модель из `GET /v1/models` | `LOCALSCRIPT_LLM_MODEL` |
| Таймаут длинной генерации | `LOCALSCRIPT_LLM_TIMEOUT_S` (при необходимости сотни секунд) |

Проверка: `GET {LLM_BASE_URL}/models` (как в `/healthz`).

## Embeddings (BGE-M3)

Сервис из skill **remote-embedding-service**:

- Живость: `GET /healthz`
- Векторы: `POST /v1/embeddings` с телом `input` (строка или список), для dense — **`return_dense: true`**
- В ответе элементы `data[]` могут содержать **`dense_embedding`**, а не поле `embedding` как у OpenAI

В LocalScript:

| Настройка | Значение для BGE-M3 |
|-----------|---------------------|
| `LOCALSCRIPT_EMBEDDING_BASE_URL` | База **без** лишнего дублирования: либо `http://host:9001`, либо `http://host:9001/v1` — клиент сам соберёт `…/v1/embeddings` |
| `LOCALSCRIPT_EMBEDDING_BGE_M3_COMPAT` | **`true`** — в запрос уйдёт `return_dense: true`, поле `model` в теле **не** отправляется (как в примере skill) |
| `LOCALSCRIPT_EMBEDDING_MODEL` | Для режима BGE compat не уходит в запрос; можно оставить для документации |

Парсер ответа всегда принимает и **`dense_embedding`**, и **`embedding`** (удобно для моков и OpenAI).

## Reranker (BGE-Reranker-v2-m3)

Сервис из skill **remote-reranker-service**:

- `GET /healthz`
- `POST /v1/rerank` — `query`, `documents`, `top_n`; в ответе **`results`** с полями **`document`** и **`relevance_score`** (без обязательного `index`)

В LocalScript:

| Настройка | Значение |
|-----------|----------|
| `LOCALSCRIPT_RAG_RERANKER_BASE_URL` | `http://host:9002` или `http://host:9002/v1` |
| `LOCALSCRIPT_RAG_RERANKER_MODEL` | Оставьте пустым, если серверу модель не нужна; иначе задайте id |

## RAG целиком

1. Каталог с `.md` / `.lua` / `.txt` → `LOCALSCRIPT_RAG_SOURCES_DIR` (например `examples/rag_corpus` или свой stub Octapi).
2. `LOCALSCRIPT_RAG_ENABLED=true`
3. Embeddings + опционально reranker как выше.
4. `GET /healthz` → `rag_ok: true` после успешного probe `POST …/embeddings`.

## Быстрая ручная проверка (без IP в логах репозитория)

Скрипты из skills (у вас локально):

- `bash ~/.cursor/skills/remote-embedding-service/scripts/test-connection.sh`
- `bash ~/.cursor/skills/remote-reranker-service/scripts/test-connection.sh`

Затем поднимите `localscript-api` с `.env` и пройдите сценарий **H** в [RUNBOOK.md](RUNBOOK.md).
