from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["error", "warning"]

_KNOWN_PRESETS = frozenset({"octapi_stub"})


@dataclass
class PolicyIssue:
    severity: Severity
    code: str
    message: str


@dataclass
class QualityReport:
    """Deterministic checks on final Lua source (domain / stub rules)."""

    preset: str
    passed: bool
    issues: list[PolicyIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "passed": self.passed,
            "issues": [
                {"severity": i.severity, "code": i.code, "message": i.message} for i in self.issues
            ],
        }


_OCTAPI_REQUIRE_RE = re.compile(
    r"\brequire\s*\(\s*['\"]octapi['\"]\s*\)",
    re.IGNORECASE,
)


def _eval_octapi_stub(code: str) -> list[PolicyIssue]:
    issues: list[PolicyIssue] = []
    if _OCTAPI_REQUIRE_RE.search(code):
        issues.append(
            PolicyIssue(
                severity="error",
                code="octapi_no_require",
                message='Do not use require("octapi"); octapi is a global API.',
            )
        )
    if re.search(r"\bos\.exit\s*\(", code):
        issues.append(
            PolicyIssue(
                severity="error",
                code="no_os_exit",
                message="Avoid os.exit; let the main chunk finish.",
            )
        )
    if re.search(r"\bloadfile\s*\(", code) or re.search(
        r"\bload\s*\(\s*[^\"']", code
    ):
        issues.append(
            PolicyIssue(
                severity="warning",
                code="dynamic_load",
                message="load/loadfile of dynamic paths is discouraged for this stub runtime.",
            )
        )
    # Heuristic: flag standard library I/O surfaces (not exhaustive).
    if "os." in code:
        issues.append(
            PolicyIssue(
                severity="warning",
                code="os_used",
                message="os.* usage — verify task allows it (stub prefers minimal surface).",
            )
        )
    if "io." in code:
        issues.append(
            PolicyIssue(
                severity="warning",
                code="io_used",
                message="io.* usage — verify task allows it.",
            )
        )
    return issues


def evaluate_quality_policy(code: str | None, *, preset: str) -> QualityReport | None:
    """
    Run preset rules on extracted Lua. Returns None if preset is empty/disabled at caller.
    """
    name = (preset or "").strip()
    if not name:
        return None
    if name not in _KNOWN_PRESETS:
        return QualityReport(
            preset=name,
            passed=False,
            issues=[
                PolicyIssue(
                    severity="error",
                    code="unknown_preset",
                    message=f"Unknown quality policy preset: {name!r}",
                )
            ],
        )
    if code is None:
        return QualityReport(
            preset=name,
            passed=False,
            issues=[
                PolicyIssue(severity="error", code="no_code", message="No Lua code to evaluate.")
            ],
        )
    if name == "octapi_stub":
        issues = _eval_octapi_stub(code)
        errors = [i for i in issues if i.severity == "error"]
        return QualityReport(preset=name, passed=len(errors) == 0, issues=issues)
    return QualityReport(preset=name, passed=True, issues=[])


def policy_selection_score(report: QualityReport | None) -> tuple[int, int]:
    """
    Lower is better. (error_count, warning_count) for lexicographic compare among candidates.
    """
    if report is None:
        return (0, 0)
    err = sum(1 for i in report.issues if i.severity == "error")
    warn = sum(1 for i in report.issues if i.severity == "warning")
    return (err, warn)
