# Octapi stub reference (authoritative for generation)

## What `octapi` is

The fictional **`octapi`** API is available as **globals** inside the target runtime. It is **not** a Lua module: **do not** use `require("octapi")` or `require('octapi')`.

## API surface

- `octapi.connect(host)` — returns a handle with `:send(msg)` and `:close()`.
- `octapi.version()` — returns semantic version string `"1.0.0"`.

## Hard constraints (must follow)

1. **No `require` for octapi** — call `octapi.version()` directly.
2. **No `os.*`, no `io.*`, no `load`/`loadfile` of user paths** unless the user task explicitly requires it.
3. **Allowed without extra setup:** `print`, `type`, `tostring`, `math`, `string`, `table`, `pairs`, `error`, `assert`, and the `octapi` table above.

## Minimal example (valid pattern)

```lua
print(octapi.version())
```

## Invalid patterns (do not generate)

- `require("octapi")` — wrong integration style for this stub.
- `os.exit(...)` — not needed; script ends when main chunk finishes.
