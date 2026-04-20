# Octapi: сессия connect → send → close

`octapi` доступен как **глобальная таблица** (не через `require`).

## Шаги

1. Вызвать **`h = octapi.connect(host)`**, где `host` — строка (например `"relay"`).
2. Отправить данные: **`h:send(message)`** (метод объекта handle).
3. Закрыть сессию: **`h:close()`**.

## Мини-пример

```lua
local h = octapi.connect("relay")
h:send("ping")
h:close()
```

## Версия без сессии

Для только чтения версии API: **`print(octapi.version())`**.
