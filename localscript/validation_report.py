from __future__ import annotations

from typing import Literal

from localscript.config import Settings
from localscript.executil import is_executable_available
from localscript.validate import ValidationResult, tool_availability, validators_ready

ValidationProfile = Literal["none", "partial", "full"]


def build_validation_report(
    settings: Settings,
    val: ValidationResult | None,
    *,
    sandbox_ok: bool | None,
    sb_msg: str,
    overall_success: bool,
) -> tuple[ValidationProfile, list[dict]]:
    """
    Build validation_profile and per-tool rows for the last agent iteration.
    """
    rows: list[dict] = []
    raw = val.raw_outputs if val is not None else {}

    def add_linter_row(tool_id: str, raw_key: str) -> None:
        if tool_id == "stylua":
            en, cmd = settings.enable_stylua, settings.stylua_command
        elif tool_id == "selene":
            en, cmd = settings.enable_selene, settings.selene_command
        elif tool_id == "lua-language-server":
            en, cmd = settings.enable_luals, settings.luals_command
        elif tool_id == "luacheck":
            en, cmd = settings.enable_luacheck, settings.luacheck_command
        else:
            return
        if not en:
            rows.append({"tool": tool_id, "status": "disabled"})
            return
        avail, _ = is_executable_available(cmd, path_extra=settings.path_extra)
        if not avail:
            rows.append({"tool": tool_id, "status": "skipped", "reason": "not on PATH"})
            return
        if val is None:
            rows.append({"tool": tool_id, "status": "not_run"})
            return
        if raw_key not in raw:
            rows.append({"tool": tool_id, "status": "not_run"})
            return
        chunk = raw.get(raw_key) or ""
        low = chunk.strip().lower()
        if low.startswith("skipped:"):
            if "disabled" in low:
                rows.append({"tool": tool_id, "status": "disabled"})
            else:
                rows.append({"tool": tool_id, "status": "skipped", "reason": chunk[:200]})
            return
        if val.failure_tool == tool_id:
            rows.append({"tool": tool_id, "status": "failed"})
            return
        rows.append({"tool": tool_id, "status": "ok"})

    add_linter_row("stylua", "stylua")
    add_linter_row("selene", "selene")
    add_linter_row("luacheck", "luacheck")
    add_linter_row("lua-language-server", "lua-language-server")

    # host luac — not used when docker sandbox runs instead
    if settings.sandbox_execution_mode == "docker":
        rows.append({"tool": "luac", "status": "not_run", "reason": "docker sandbox mode"})
    elif not settings.enable_luac:
        rows.append({"tool": "luac", "status": "disabled"})
    else:
        la, _ = is_executable_available(settings.luac_command, path_extra=settings.path_extra)
        if not la:
            rows.append({"tool": "luac", "status": "skipped", "reason": "not on PATH"})
        elif val is None or not val.ok:
            rows.append({"tool": "luac", "status": "not_run"})
        elif "skipped" in (sb_msg or "").lower():
            rows.append({"tool": "luac", "status": "skipped", "reason": sb_msg[:200]})
        elif sandbox_ok is True:
            rows.append({"tool": "luac", "status": "ok"})
        elif sandbox_ok is False:
            rows.append({"tool": "luac", "status": "failed"})
        else:
            rows.append({"tool": "luac", "status": "not_run"})

    if settings.sandbox_execution_mode == "docker":
        if val is None or not val.ok:
            rows.append({"tool": "docker_sandbox", "status": "not_run"})
        elif sandbox_ok is True:
            rows.append({"tool": "docker_sandbox", "status": "ok"})
        elif sandbox_ok is False:
            rows.append({"tool": "docker_sandbox", "status": "failed"})
        else:
            rows.append({"tool": "docker_sandbox", "status": "not_run"})
    else:
        rows.append({"tool": "docker_sandbox", "status": "not_applicable"})

    ready = validators_ready(settings)
    if not ready:
        return "none", rows

    required_names = [c.name for c in tool_availability(settings) if c.enabled and c.available]
    if settings.sandbox_execution_mode == "docker":
        required_names = [n for n in required_names if n != "luac"]
        required_names.append("docker_sandbox")
    elif settings.sandbox_execution_mode == "none":
        required_names = [n for n in required_names if n != "luac"]
    by_tool = {r["tool"]: r for r in rows}
    all_ok = overall_success
    for name in required_names:
        st = by_tool.get(name, {}).get("status")
        if st != "ok":
            all_ok = False
            break

    if all_ok and overall_success:
        profile: ValidationProfile = "full"
    else:
        profile = "partial"

    return profile, rows


def summarize_validators_for_settings(settings: Settings) -> dict:
    """Structured summary for 503 / logs."""
    checks = tool_availability(settings)
    return {
        "validators_ready": validators_ready(settings),
        "tools": [
            {"name": c.name, "enabled": c.enabled, "available": c.available, "reason": c.reason}
            for c in checks
        ],
    }


def build_evidence_summary(
    *,
    success: bool,
    steps: list[dict],
    validation_profile: ValidationProfile,
    validation_tools: list[dict],
    error: str | None,
) -> dict:
    last_diagnostics = None
    if steps:
        last_diagnostics = (steps[-1].get("diagnostics_summary") or "").strip() or None

    passed_checks = [
        row["tool"] for row in validation_tools if row.get("status") == "ok" and row.get("tool")
    ]
    failed_checks = [
        row["tool"] for row in validation_tools if row.get("status") == "failed" and row.get("tool")
    ]
    skipped_checks = [
        row["tool"]
        for row in validation_tools
        if row.get("status") in {"skipped", "not_run"} and row.get("tool")
    ]

    trust_summary = (
        f"{len(passed_checks)} passed, {len(failed_checks)} failed, {len(skipped_checks)} skipped"
    )

    return {
        "attempts": len(steps),
        "correction_loop_used": len(steps) > 1,
        "final_status": "passed" if success else "failed",
        "validation_profile": validation_profile,
        "checks": validation_tools,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "skipped_checks": skipped_checks,
        "trust_summary": trust_summary,
        "last_diagnostics": last_diagnostics,
        "error": error,
    }
