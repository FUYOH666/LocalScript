from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from localscript.config import Settings
from localscript.extract import extract_lua_code
from localscript.llm import LLMError, chat_completion
from localscript.quality_judge import judge_to_dict, run_quality_judge
from localscript.quality_policy import (
    evaluate_quality_policy,
    policy_selection_score,
)
from localscript.rag.retrieve import format_rag_message, retrieve_for_task
from localscript.sandbox import run_sandbox
from localscript.validation_report import build_validation_report
from localscript.validate import format_diagnostics_for_prompt, run_validation_chain

logger = logging.getLogger("localscript.orchestrator")

SYSTEM_PROMPT = """You are a coding agent that outputs Lua 5.4 code only when asked.
Respond with a single fenced code block ```lua ... ``` containing complete, runnable Lua.
Do not call os.execute, io.open, or load external files unless the user explicitly requires it.
If the conversation includes a "Retrieved reference" user message, treat it as authoritative for APIs and integration style (e.g. do not use require() for APIs described there as globals).
If previous attempt had validation errors, fix them and output the full corrected script."""


def _materialize_workspace_template(tmp: Path, template: Path | None) -> None:
    if template is None or not template.is_dir():
        return
    for item in sorted(template.iterdir()):
        dest = tmp / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)


@dataclass
class AgentStepLog:
    step: int
    assistant_preview: str
    validation_ok: bool
    sandbox_ok: bool | None
    diagnostics_summary: str


@dataclass
class GenerateResult:
    success: bool
    code: str | None
    steps: list[AgentStepLog] = field(default_factory=list)
    error: str | None = None
    validation_profile: str = "none"
    validation_tools: list[dict] = field(default_factory=list)
    quality_policy: dict | None = None
    quality_judge: dict | None = None
    quality_judge_error: str | None = None
    generate_candidates_n: int | None = None
    candidate_index: int | None = None


async def _build_initial_messages(
    settings: Settings,
    user_task: str,
    extra_context: str | None,
    client: httpx.AsyncClient | None,
    request_id: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    if extra_context:
        messages.append(
            {
                "role": "user",
                "content": "Context (API stubs / conventions):\n" + extra_context.strip(),
            }
        )
    if settings.rag_enabled:
        try:
            chunks = await retrieve_for_task(
                settings,
                user_task,
                extra_context,
                client=client,
            )
            if chunks:
                rag_text = format_rag_message(chunks)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Retrieved reference (do not invent APIs beyond this):\n" + rag_text
                        ),
                    }
                )
                logger.info(
                    "request_id=%s rag_injected chunks=%s",
                    request_id,
                    [c.chunk_id for c in chunks],
                )
        except Exception as e:
            logger.warning("request_id=%s rag_retrieve_failed err=%s", request_id, e)
    messages.append({"role": "user", "content": user_task.strip()})
    return messages


async def _generate_lua_fix_loop(
    settings: Settings,
    messages: list[dict[str, str]],
    *,
    client: httpx.AsyncClient | None,
    request_id: str,
) -> GenerateResult:
    steps_out: list[AgentStepLog] = []
    last_val = None
    last_sb_ok: bool | None = None
    last_sb_msg = ""
    code = ""

    def _report(
        val,
        sb_ok: bool | None,
        sb_msg: str,
        success: bool,
    ) -> tuple[str, list[dict]]:
        return build_validation_report(
            settings,
            val,
            sandbox_ok=sb_ok,
            sb_msg=sb_msg,
            overall_success=success,
        )

    for step in range(1, settings.agent_max_steps + 1):
        try:
            raw = await chat_completion(settings, messages, client=client)
        except LLMError as e:
            prof, tools = _report(last_val, last_sb_ok, last_sb_msg, False)
            return GenerateResult(
                success=False,
                code=None,
                steps=steps_out,
                error=str(e),
                validation_profile=prof,
                validation_tools=tools,
            )

        code = extract_lua_code(raw)
        preview = raw.strip()[:500] + ("…" if len(raw.strip()) > 500 else "")

        with tempfile.TemporaryDirectory(prefix="localscript_") as tmp:
            tmp_path = Path(tmp)
            _materialize_workspace_template(tmp_path, settings.validation_workspace_template)
            path = tmp_path / "main.lua"
            path.write_text(code, encoding="utf-8")

            val = await run_validation_chain(settings, path)
            diag_text = format_diagnostics_for_prompt(
                val.diagnostics,
                max_items=settings.diagnostics_prompt_max_items,
            )

            sandbox_ok: bool | None = None
            sb_msg = ""
            if val.ok:
                sandbox_ok, sb_msg = await run_sandbox(settings, path)
                if not sandbox_ok:
                    tag = "sandbox" if settings.sandbox_execution_mode == "docker" else "luac"
                    diag_text = (diag_text + "\n" if diag_text else "") + f"[{tag}] {sb_msg}"

            log = AgentStepLog(
                step=step,
                assistant_preview=preview,
                validation_ok=val.ok,
                sandbox_ok=sandbox_ok,
                diagnostics_summary=diag_text[:4000],
            )
            steps_out.append(log)
            last_val = val
            last_sb_ok = sandbox_ok
            last_sb_msg = sb_msg
            logger.info(
                "request_id=%s agent_step step=%s validation_ok=%s sandbox_ok=%s",
                request_id,
                step,
                val.ok,
                sandbox_ok,
            )

            if val.ok and sandbox_ok:
                prof, tools = _report(val, sandbox_ok, sb_msg, True)
                return GenerateResult(
                    success=True,
                    code=code,
                    steps=steps_out,
                    error=None,
                    validation_profile=prof,
                    validation_tools=tools,
                )

            feedback = (
                "Validation failed. Fix the Lua and reply with a full ```lua ... ``` block.\n"
                f"Diagnostics:\n{diag_text}\n"
            )
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": feedback})

    prof, tools = _report(last_val, last_sb_ok, last_sb_msg, False)
    return GenerateResult(
        success=False,
        code=code if steps_out else None,
        steps=steps_out,
        error="max agent steps exceeded without clean validation",
        validation_profile=prof,
        validation_tools=tools,
    )


def _select_best_candidate(settings: Settings, results: list[GenerateResult]) -> tuple[int, GenerateResult]:
    successes = [(i, r) for i, r in enumerate(results) if r.success and r.code]
    if not successes:
        return (0, results[0])
    preset = (settings.quality_policy_preset or "").strip() if settings.quality_policy_enabled else ""

    def sort_key(item: tuple[int, GenerateResult]) -> tuple[int, int, int]:
        _i, r = item
        if preset:
            rep = evaluate_quality_policy(r.code, preset=preset)
            err, warn = policy_selection_score(rep)
        else:
            err, warn = (0, 0)
        return (err, warn, len(r.steps))

    best_i, best_r = min(successes, key=sort_key)
    return (best_i, best_r)


async def _apply_quality_layers(
    settings: Settings,
    result: GenerateResult,
    user_task: str,
    client: httpx.AsyncClient | None,
) -> GenerateResult:
    preset = (settings.quality_policy_preset or "").strip()
    if settings.quality_policy_enabled and preset:
        rep = evaluate_quality_policy(result.code, preset=preset)
        result.quality_policy = rep.to_dict() if rep else None
    if settings.quality_judge_enabled and result.success and result.code:
        scores, err = await run_quality_judge(
            settings,
            user_task=user_task,
            code=result.code,
            client=client,
        )
        if scores is not None:
            result.quality_judge = judge_to_dict(scores)
        if err:
            result.quality_judge_error = err
    return result


async def generate_lua(
    settings: Settings,
    user_task: str,
    *,
    extra_context: str | None = None,
    client: httpx.AsyncClient | None = None,
    request_id: str = "",
) -> GenerateResult:
    """
    Generate Lua with generate-validate-fix loop (StyLua -> Selene -> LuaLS -> luac -p).
    Optional best-of-K candidates (GENERATE_CANDIDATES_N) and quality policy / LLM judge.
    """
    n = settings.generate_candidates_n
    if n == 1:
        messages = await _build_initial_messages(
            settings, user_task, extra_context, client, request_id or "gen"
        )
        result = await _generate_lua_fix_loop(
            settings, messages, client=client, request_id=request_id or "gen"
        )
        result = await _apply_quality_layers(settings, result, user_task, client)
        result.generate_candidates_n = 1
        result.candidate_index = 0
        return result

    sem = asyncio.Semaphore(settings.generate_candidates_max_parallel)

    async def one(idx: int) -> GenerateResult:
        async with sem:
            rid = f"{request_id}-c{idx}" if request_id else f"c{idx}"
            msgs = await _build_initial_messages(settings, user_task, extra_context, client, rid)
            return await _generate_lua_fix_loop(settings, msgs, client=client, request_id=rid)

    results = await asyncio.gather(*[one(i) for i in range(n)])
    best_idx, best = _select_best_candidate(settings, list(results))
    best = await _apply_quality_layers(settings, best, user_task, client)
    best.generate_candidates_n = n
    best.candidate_index = best_idx
    return best
