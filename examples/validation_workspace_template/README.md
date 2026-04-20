# Шаблон воркспейса для валидации (Selene + LuaLS)

Скопируйте содержимое этой папки в свой каталог или укажите его в **`LOCALSCRIPT_VALIDATION_WORKSPACE_TEMPLATE`** (абсолютный путь). Перед каждым прогоном линтеров файлы **копируются** во временный каталог вместе с генерируемым `main.lua`.

## Что править под хакатон

- **`selene.toml`** — указывает `std = "localscript_jury"` (YAML рядом в этом каталоге), а не встроенный `lua54`: у многих установок `selene` из Homebrew **нет** упакованного builtin `lua54`, из‑за чего падает валидация.
- **`localscript_jury.yml`** — vendored std: `base: lua51` + глобал `octapi` (`any`), чтобы Selene не ругался на сценарии Octapi; синтаксис 5.4 сверх возможностей std по-прежнему ловят **LuaLS** и **`luac -p`**.
- **`.luarc.json`** — `Lua.workspace.library`: добавьте пути к **stub-файлам** API платформы (Octapi и т.д.), чтобы LuaLS видел глобальные символы.
- Подкаталог **`stubs/`** — в репозитории уже есть **`stubs/octapi.lua`** для глобала `octapi` (LuaLS); при своём API добавляйте сюда же `*.lua` с `---@` аннотациями.

## Selene и кастомные глобалы (`octapi`)

**LuaLS** (через `stubs/octapi.lua`) понимает глобал `octapi` для подсказок и проверок типов.

**Selene** использует **`localscript_jury.yml`**: доменный `octapi` объявлен явно; база — встроенный `lua51` из бинарника Selene (он есть даже в урезанных сборках).

Если нужен другой набор глобалов — расширьте YAML по [документации Selene](https://kampfkarren.github.io/selene/usage/std.html) или временно отключите линтер (`LOCALSCRIPT_ENABLE_SELENE=false`).

Песочница **`docker/safe_run.lua`** задаёт `octapi` в **runtime**; это **не связано** с тем, видит ли Selene тот же символ на этапе линтинга.

## Проверка

```bash
export LOCALSCRIPT_VALIDATION_WORKSPACE_TEMPLATE="$(pwd)/examples/validation_workspace_template"
uv run localscript-api
```

Затем `POST /generate` — в ответе смотрите `validation_tools` и `validation_profile`.
