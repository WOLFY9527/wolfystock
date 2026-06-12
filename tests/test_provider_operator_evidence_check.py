# -*- coding: utf-8 -*-
"""Offline provider operator evidence validator tests."""

from __future__ import annotations

from pathlib import Path

from tests.helpers.cli_validator import make_cli_validator, stdout_json as _stdout_json


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "provider_operator_evidence_check.py"
_write_json, _run_validator = make_cli_validator(
    SCRIPT,
    cwd=REPO_ROOT,
    artifact_name="provider-evidence.json",
)


def _artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "providerName": "tradier",
        "environment": "staging",
        "operator": "provider-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "probeMode": "manual_provider_probe",
        "networkCallsEnabled": False,
        "credentialPresence": "redacted",
        "circuitState": {"state": "closed", "summary": "No forced circuit override recorded."},
        "fallbackState": {"state": "unchanged", "summary": "Runtime fallback policy was observed only."},
        "outcome": "needs-review",
        "evidenceRedactionVersion": "provider_operator_redaction_v1",
        "notes": "Sanitized operator artifact for later review.",
    }
    payload.update(overrides)
    return payload


def test_accepts_sanitized_operator_artifact(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _artifact())

    result = _run_validator(path)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["advisoryOnly"] is True
    assert payload["networkCallsExecutedByValidator"] is False
    assert payload["artifact"]["providerName"] == "tradier"
    assert payload["artifact"]["outcome"] == "needs-review"


def test_missing_required_fields_are_rejected(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact.pop("observedAt")
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["status"] == "fail"
    assert {
        finding["field"]: finding["reasonCode"]
        for finding in payload["findings"]
        if finding["reasonCode"] == "missing_required_field"
    } == {"observedAt": "missing_required_field"}


def test_raw_credential_markers_are_rejected_without_echoing_values(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact["api_key"] = "should-not-appear"
    artifact["headers"] = {"Authorization": "Bearer redacted"}
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    assert "should-not-appear" not in result.stdout
    assert "should-not-appear" not in result.stderr
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "unsafe_marker" in reason_codes


def test_raw_response_request_and_debug_payloads_are_rejected(tmp_path: Path) -> None:
    artifact = _artifact(
        raw_response={"status": "ok"},
        raw_request_body={"symbol": "TEM"},
        debug_payload="Traceback stack trace redacted",
    )
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    unsafe_fields = {
        finding["field"]
        for finding in payload["findings"]
        if finding["reasonCode"] in {"unsafe_marker", "unsafe_debug_marker"}
    }
    assert {"raw_response", "raw_request_body", "debug_payload"}.issubset(unsafe_fields)


def test_outcome_cannot_claim_go_or_launch_approved(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _artifact(outcome="GO", notes="launch-approved by operator"))

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "invalid_outcome" in reason_codes
    assert "launch_approval_claim_forbidden" in reason_codes


def test_network_calls_enabled_requires_accepted_operator_outcome_but_remains_advisory(
    tmp_path: Path,
) -> None:
    needs_review_path = _write_json(
        tmp_path,
        _artifact(networkCallsEnabled=True, outcome="needs-review"),
    )

    needs_review_result = _run_validator(needs_review_path)

    assert needs_review_result.returncode == 1
    needs_review_payload = _stdout_json(needs_review_result)
    assert {
        finding["reasonCode"] for finding in needs_review_payload["findings"]
    } >= {"network_calls_enabled_requires_accepted_outcome"}

    accepted_path = _write_json(
        tmp_path,
        _artifact(networkCallsEnabled=True, outcome="accepted"),
    )

    accepted_result = _run_validator(accepted_path)

    assert accepted_result.returncode == 0
    accepted_payload = _stdout_json(accepted_result)
    assert accepted_payload["status"] == "pass"
    assert accepted_payload["advisoryOnly"] is True
    assert accepted_payload["networkCallsExecutedByValidator"] is False
    assert accepted_payload["checks"]["networkCallsEnabledAcceptedOutcome"] is True
