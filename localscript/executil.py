from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path


def subprocess_env(*, path_extra: str) -> dict[str, str]:
    """Copy of os.environ with optional PATH prefix (use os.pathsep)."""
    env = os.environ.copy()
    extra = path_extra.strip()
    if extra:
        sep = os.pathsep
        cur = env.get("PATH", "")
        env["PATH"] = f"{extra}{sep}{cur}" if cur else extra
    return env


def effective_path_string(env: dict[str, str]) -> str:
    return env.get("PATH", "")


def command_argv(command: str, extra_args: str, tail: list[str]) -> list[str]:
    """Split command + extra_args with shlex; append tail."""
    base = shlex.split(command) if command.strip() else []
    extra = shlex.split(extra_args) if extra_args.strip() else []
    return base + extra + tail


def first_token(command: str) -> str:
    parts = shlex.split(command.strip()) if command.strip() else []
    return parts[0] if parts else ""


def is_executable_available(command: str, *, path_extra: str) -> tuple[bool, str | None]:
    """
    True if command resolves to a runnable executable.
    Supports absolute paths; honors path_extra via a synthetic PATH for shutil.which.
    """
    if not command.strip():
        return False, "empty command"
    tok = first_token(command)
    expanded = str(Path(tok).expanduser())
    p = Path(expanded)
    if p.is_file() and os.access(p, os.X_OK):
        return True, None
    env = subprocess_env(path_extra=path_extra)
    path = effective_path_string(env)
    found = shutil.which(tok, path=path) if path else shutil.which(tok)
    if found:
        return True, None
    return False, f"command not found: {tok!r}"
