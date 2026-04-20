from __future__ import annotations

import pytest

from localscript.config import Settings
from localscript.quality_policy import evaluate_quality_policy, policy_selection_score


def test_octapi_stub_ok_version_call():
    r = evaluate_quality_policy('print(octapi.version())', preset="octapi_stub")
    assert r is not None
    assert r.passed is True
    assert policy_selection_score(r) == (0, 0)


def test_octapi_stub_errors_on_require():
    r = evaluate_quality_policy('require("octapi")\nprint(1)', preset="octapi_stub")
    assert r is not None
    assert r.passed is False
    assert any(i.code == "octapi_no_require" for i in r.issues)


def test_octapi_stub_error_os_exit():
    r = evaluate_quality_policy("os.exit(0)", preset="octapi_stub")
    assert r.passed is False
    assert any(i.code == "no_os_exit" for i in r.issues)


def test_octapi_stub_warns_os_io():
    r = evaluate_quality_policy("print(os.getenv('x'))", preset="octapi_stub")
    assert r.passed is True
    assert any(i.code == "os_used" for i in r.issues)


def test_unknown_preset():
    r = evaluate_quality_policy("print(1)", preset="nope")
    assert r is not None
    assert r.passed is False
    assert any(i.code == "unknown_preset" for i in r.issues)


def test_settings_rejects_policy_enabled_without_preset(monkeypatch):
    monkeypatch.setenv("LOCALSCRIPT_QUALITY_POLICY_ENABLED", "true")
    # Empty string overrides a preset from `.env` (delenv alone does not clear env_file values).
    monkeypatch.setenv("LOCALSCRIPT_QUALITY_POLICY_PRESET", "")
    with pytest.raises(ValueError, match="QUALITY_POLICY_PRESET"):
        Settings()
