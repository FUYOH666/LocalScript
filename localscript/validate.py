from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from localscript.config import Settings
from localscript.executil import (
    command_argv,
    is_executable_available,
    subprocess_env,
)

logger = logging.getLogger("localscript.validate")


@dataclass
class ToolCheck:
    name: str
    enabled: bool
    available: bool
    reason: str | None = None


@dataclass
class Diagnostic:
    tool: str
    line: int | None
    message: str
    severity: str = "error"


@dataclass
class ValidationResult:
    ok: bool
    diagnostics: list[Diagnostic] = field(default_factory=list)
    raw_outputs: dict[str, str] = field(default_factory=dict)
    failure_tool: str | None = None


def validators_ready(settings: Settings) -> bool:
    """True if at least one validation tool is enabled and executable."""
    return any(c.enabled and c.available for c in tool_availability(settings))


def tool_availability(settings: Settings) -> list[ToolCheck]:
    checks: list[ToolCheck] = []
    specs: list[tuple[str, str, bool]] = [
        ("stylua", settings.stylua_command, settings.enable_stylua),
        ("selene", settings.selene_command, settings.enable_selene),
        ("luacheck", settings.luacheck_command, settings.enable_luacheck),
        ("lua-language-server", settings.luals_command, settings.enable_luals),
        ("luac", settings.luac_command, settings.enable_luac),
    ]
    for name, cmd, enabled in specs:
        if not enabled:
            checks.append(
                ToolCheck(name=name, enabled=False, available=False, reason="disabled in config")
            )
            continue
        ok, reason = is_executable_available(cmd, path_extra=settings.path_extra)
        checks.append(ToolCheck(name=name, enabled=True, available=ok, reason=reason))
    return checks


async def _run(
    cmd: list[str],
    cwd: Path,
    timeout: float,
    env: dict[str, str],
) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    out = out_b.decode(errors="replace")
    err = err_b.decode(errors="replace")
    code = proc.returncode if proc.returncode is not None else -1
    return code, out, err


async def run_stylua(settings: Settings, lua_path: Path) -> ValidationResult:
    if not settings.enable_stylua:
        return ValidationResult(ok=True, diagnostics=[], raw_outputs={"stylua": "skipped: disabled"})
    ok, reason = is_executable_available(settings.stylua_command, path_extra=settings.path_extra)
    if not ok:
        return ValidationResult(ok=True, diagnostics=[], raw_outputs={"stylua": f"skipped: {reason}"})
    env = subprocess_env(path_extra=settings.path_extra)
    cmd = command_argv(settings.stylua_command, settings.stylua_extra_args, [str(lua_path.name)])
    try:
        code, out, err = await _run(cmd, lua_path.parent, settings.stylua_timeout_s, env)
    except TimeoutError:
        return ValidationResult(
            ok=False,
            diagnostics=[Diagnostic("stylua", None, "stylua timeout", "error")],
        )
    text = (out + err).strip()
    diags: list[Diagnostic] = []
    success = code == 0
    if not success and text:
        diags.append(Diagnostic("stylua", None, text[:2000], "error"))
    return ValidationResult(ok=success, diagnostics=diags, raw_outputs={"stylua": text})


async def run_selene(settings: Settings, lua_path: Path) -> ValidationResult:
    if not settings.enable_selene:
        return ValidationResult(ok=True, diagnostics=[], raw_outputs={"selene": "skipped: disabled"})
    ok, reason = is_executable_available(settings.selene_command, path_extra=settings.path_extra)
    if not ok:
        return ValidationResult(ok=True, diagnostics=[], raw_outputs={"selene": f"skipped: {reason}"})
    env = subprocess_env(path_extra=settings.path_extra)
    cmd = command_argv(
        settings.selene_command,
        settings.selene_extra_args,
        ["--display-style", "json", str(lua_path.name)],
    )
    try:
        code, out, err = await _run(cmd, lua_path.parent, settings.selene_timeout_s, env)
    except TimeoutError:
        return ValidationResult(
            ok=False,
            diagnostics=[Diagnostic("selene", None, "selene timeout", "error")],
        )
    text = (out + err).strip()
    diags: list[Diagnostic] = []
    if text:
        try:
            data = json.loads(text)
            for item in data if isinstance(data, list) else data.get("diagnostics", []):
                if not isinstance(item, dict):
                    continue
                label = item.get("label") or item.get("code") or "selene"
                msg = item.get("message") or str(item)
                line = item.get("primary_label") or item.get("start")
                line_no = None
                if isinstance(line, dict) and "line" in line:
                    line_no = int(line["line"])
                elif isinstance(line, int):
                    line_no = line
                severity = "error" if code != 0 else "warning"
                diags.append(Diagnostic("selene", line_no, f"{label}: {msg}", severity))
        except json.JSONDecodeError:
            if code != 0:
                diags.append(Diagnostic("selene", None, text[:2000], "error"))
    success = code == 0 and not any(d.severity == "error" for d in diags)
    return ValidationResult(ok=success, diagnostics=diags, raw_outputs={"selene": text})


async def run_luacheck(settings: Settings, lua_path: Path) -> ValidationResult:
    if not settings.enable_luacheck:
        return ValidationResult(ok=True, diagnostics=[], raw_outputs={"luacheck": "skipped: disabled"})
    ok, reason = is_executable_available(settings.luacheck_command, path_extra=settings.path_extra)
    if not ok:
        return ValidationResult(ok=True, diagnostics=[], raw_outputs={"luacheck": f"skipped: {reason}"})
    env = subprocess_env(path_extra=settings.path_extra)
    cmd = command_argv(
        settings.luacheck_command,
        settings.luacheck_extra_args,
        [str(lua_path.name)],
    )
    try:
        code, out, err = await _run(cmd, lua_path.parent, settings.luacheck_timeout_s, env)
    except TimeoutError:
        return ValidationResult(
            ok=False,
            diagnostics=[Diagnostic("luacheck", None, "luacheck timeout", "error")],
        )
    text = (out + err).strip()
    diags: list[Diagnostic] = []
    if code != 0 and text:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            diags.append(Diagnostic("luacheck", None, line[:2000], "error"))
    if not diags and code != 0:
        diags.append(Diagnostic("luacheck", None, text[:2000] or f"exit {code}", "error"))
    success = code == 0
    return ValidationResult(ok=success, diagnostics=diags, raw_outputs={"luacheck": text})


async def run_luals(settings: Settings, lua_path: Path) -> ValidationResult:
    if not settings.enable_luals:
        return ValidationResult(ok=True, diagnostics=[], raw_outputs={"lua-language-server": "skipped: disabled"})
    ok, reason = is_executable_available(settings.luals_command, path_extra=settings.path_extra)
    if not ok:
        return ValidationResult(
            ok=True,
            diagnostics=[],
            raw_outputs={"lua-language-server": f"skipped: {reason}"},
        )
    env = subprocess_env(path_extra=settings.path_extra)
    cmd = command_argv(
        settings.luals_command,
        settings.luals_extra_args,
        ["--check", str(lua_path.resolve())],
    )
    try:
        code, out, err = await _run(cmd, lua_path.parent, settings.luals_timeout_s, env)
    except TimeoutError:
        return ValidationResult(
            ok=False,
            diagnostics=[Diagnostic("lua-language-server", None, "lua-language-server timeout", "error")],
        )
    text = (out + err).strip()
    diags: list[Diagnostic] = []
    if not text and code != 0:
        diags.append(Diagnostic("lua-language-server", None, f"exit {code}", "error"))
    elif text:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    msg = obj.get("message") or str(obj)
                    rng = obj.get("range") or {}
                    start = rng.get("start") or {}
                    ln = start.get("line")
                    diags.append(
                        Diagnostic(
                            "lua-language-server",
                            int(ln) + 1 if isinstance(ln, int) else None,
                            msg,
                            obj.get("severity", "error"),
                        )
                    )
            except json.JSONDecodeError:
                if code != 0:
                    diags.append(Diagnostic("lua-language-server", None, line[:500], "error"))
    success = code == 0 and not any(d.severity == "error" for d in diags)
    return ValidationResult(ok=success, diagnostics=diags, raw_outputs={"lua-language-server": text})


async def run_validation_chain(settings: Settings, lua_path: Path) -> ValidationResult:
    """StyLua -> Selene -> LuaLS; aggregate diagnostics."""
    all_diags: list[Diagnostic] = []
    raw: dict[str, str] = {}
    for runner, tool_name in (
        (run_stylua, "stylua"),
        (run_selene, "selene"),
        (run_luacheck, "luacheck"),
        (run_luals, "lua-language-server"),
    ):
        part = await runner(settings, lua_path)
        raw.update(part.raw_outputs)
        all_diags.extend(part.diagnostics)
        if not part.ok:
            return ValidationResult(
                ok=False,
                diagnostics=all_diags,
                raw_outputs=raw,
                failure_tool=tool_name,
            )
    return ValidationResult(ok=True, diagnostics=all_diags, raw_outputs=raw)


def format_diagnostics_for_prompt(
    diagnostics: list[Diagnostic],
    *,
    max_items: int = 20,
) -> str:
    lines = []
    for d in diagnostics[:max_items]:
        loc = f"L{d.line}" if d.line is not None else "L?"
        lines.append(f"- [{d.tool}] {loc} ({d.severity}): {d.message}")
    if len(diagnostics) > max_items:
        lines.append(f"... ({len(diagnostics) - max_items} more)")
    return "\n".join(lines) if lines else "(no diagnostics)"
