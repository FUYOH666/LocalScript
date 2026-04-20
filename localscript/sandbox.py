from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from localscript.config import Settings
from localscript.executil import command_argv, is_executable_available, subprocess_env

logger = logging.getLogger("localscript.sandbox")


async def run_luac_syntax_check(
    settings: Settings,
    lua_path: Path,
) -> tuple[bool, str]:
    """Run `luac -p` for parse-only check. Returns (ok, stderr_or_message)."""
    if not settings.enable_luac:
        return True, "skipped: disabled"
    ok, reason = is_executable_available(settings.luac_command, path_extra=settings.path_extra)
    if not ok:
        return True, f"skipped: {reason}"
    env = subprocess_env(path_extra=settings.path_extra)
    cmd = command_argv(
        settings.luac_command,
        settings.luac_extra_args,
        ["-p", str(lua_path.resolve())],
    )
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=lua_path.parent,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=settings.luac_timeout_s)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return False, "luac timeout"
    err = err_b.decode(errors="replace").strip()
    out = out_b.decode(errors="replace").strip()
    code = proc.returncode if proc.returncode is not None else -1
    if code == 0:
        return True, ""
    return False, err or out or f"luac exit {code}"


async def run_docker_lua_safe(settings: Settings, lua_path: Path) -> tuple[bool, str]:
    """Run user Lua inside Docker image with safe_run.lua (load in restricted env)."""
    parent = lua_path.parent.resolve()
    name = lua_path.name
    cmd: list[str] = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{parent}:/work:ro",
        "-w",
        "/work",
    ]
    if settings.sandbox_docker_network_disabled:
        cmd.extend(["--network", "none"])
    cmd.extend(
        [
            settings.sandbox_docker_image,
            "lua5.4",
            "/opt/sandbox/safe_run.lua",
            f"/work/{name}",
        ]
    )
    logger.info("docker_sandbox cmd=%s", " ".join(cmd[:6]) + " ...")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out_b, err_b = await asyncio.wait_for(
            proc.communicate(),
            timeout=settings.sandbox_docker_timeout_s,
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return False, "docker sandbox timeout"
    err = err_b.decode(errors="replace").strip()
    out = out_b.decode(errors="replace").strip()
    code = proc.returncode if proc.returncode is not None else -1
    if code == 0:
        return True, out
    return False, err or out or f"docker sandbox exit {code}"


async def run_sandbox(settings: Settings, lua_path: Path) -> tuple[bool, str]:
    mode = settings.sandbox_execution_mode
    if mode == "none":
        return True, "skipped: sandbox none"
    if mode == "luac_only":
        return await run_luac_syntax_check(settings, lua_path)
    if mode == "docker":
        return await run_docker_lua_safe(settings, lua_path)
    return False, f"unknown sandbox mode: {mode}"


async def probe_docker_available(*, timeout_s: float = 5.0) -> tuple[bool, str | None]:
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "version",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return False, "docker version timeout"
    if proc.returncode == 0:
        return True, None
    err = err_b.decode(errors="replace").strip() if err_b else ""
    return False, err[:500] or "docker version failed"
