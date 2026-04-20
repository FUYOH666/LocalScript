from localscript.validation_report import build_evidence_summary


def test_build_evidence_summary_groups_checks_and_builds_trust_summary():
    summary = build_evidence_summary(
        success=False,
        steps=[
            {
                "step": 2,
                "diagnostics_summary": "[selene] undefined global",
            }
        ],
        validation_profile="partial",
        validation_tools=[
            {"tool": "stylua", "status": "ok"},
            {"tool": "selene", "status": "failed"},
            {"tool": "luac", "status": "skipped", "reason": "not on PATH"},
            {"tool": "docker_sandbox", "status": "not_applicable"},
        ],
        error="generation failed",
    )

    assert summary["passed_checks"] == ["stylua"]
    assert summary["failed_checks"] == ["selene"]
    assert summary["skipped_checks"] == ["luac"]
    assert summary["trust_summary"] == "1 passed, 1 failed, 1 skipped"
    assert summary["last_diagnostics"] == "[selene] undefined global"
