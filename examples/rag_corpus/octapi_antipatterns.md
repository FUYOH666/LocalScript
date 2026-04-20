# Octapi: типичные ошибки генерации (антипаттерны)

Используйте в RAG вместе с [octapi_stub.md](octapi_stub.md). Цель — сместить retrieval и ответ модели **от неверных шаблонов**.

## Неверно

- `require("octapi")` или `require('octapi')` — в стабе **octapi глобальный**, не модуль.
- `os.exit(...)` — скрипт должен завершаться естественно; `os.*` / `io.*` только если задача явно требует.
- Вымышленные методы на `octapi`, которых нет в стабе (`octapi.fetch`, `OctapiClient.new`, …).

## Верно

- `print(octapi.version())`
- `local h = octapi.connect("host")` затем `h:send("...")`, `h:close()`

## Почему модель ошибается

Частый prior в весах LLM — «всё через `require`». Блок **Retrieved reference** и этот файл должны перебивать prior при настройке RAG.
