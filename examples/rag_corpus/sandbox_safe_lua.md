# Изолированное исполнение (Docker safe_run)

User-скрипт выполняется через **`load(src, "@user", "t", safe_env)`** — доступны только перечисленные глобалы.

## Разрешено в sandbox (safe_env)

- `print`, `error`, `assert`, `type`, `pairs`, `ipairs`, `next`, `select`
- `tonumber`, `tostring`
- Таблицы **`string`**, **`table`**, **`math`**, **`utf8`**
- Глобальная таблица **`octapi`** (как в стабе: `connect`, `version`, handle с `:send` / `:close`)

## Недоступно в sandbox

- **`require`**, **`package`**, **`load`/`loadfile`** пользовательских путей
- **`io.*`**, **`os.*`** (кроме внутренностей раннера, не видимых скрипту)
- Произвольные C-границы и сетевые вызовы

Скрипт, использующий `require("octapi")` или `os.exit`, **упадёт** или не пройдёт проверку в этой среде.
