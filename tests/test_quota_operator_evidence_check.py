# -*- coding: utf-8 -*-
"""Offline quota/budget operator evidence validator tests."""

from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "quota_operator_evidence_check.py"


SECTION_IDS = (
    "quotaPilot",
    "budgetAlertDryRun",
    "ownerScopeSampling",
    "disabledPreferenceSuppression",
    "notificationNoOutboundProof",
)


def _section(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "environment": "staging-sanitized",
        "operator": "cost-ops-operator",
        "observedAt": "2026-05-08T10:30:00Z",
        "sampledOwnerLabels": ["owner-alpha", "owner-beta"],
        "thresholdPolicyVersion": "quota-budget-thresholds-v1",
        "dryRunOnly": True,
        "outboundSent": False,
        "outcome": "accepted",
        "evidenceRedactionVersion": "quota_budget_operator_redaction_v1",
        "notes": "Sanitized dry-run operator evidence.",
    }
    payload.update(overrides)
    return payload


def _artifact() -> dict[str, object]:
    return {
        "schemaVersion": "wolfystock_quota_operator_evidence_v1",
        "mode": "operator_sanitized",
        **{section_id: _section() for section_id in SECTION_IDS},
    }


def _write_json(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "quota-operator-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _stdout_json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout)


def test_accepts_sanitized_quota_budget_operator_artifact(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _artifact())

    result = _run_validator(path)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["finalStatus"] == "ACCEPTED"
    assert payload["advisoryOnly"] is True
    assert payload["launchAcceptanceIntegrated"] is False
    assert payload["networkCallsExecutedByValidator"] is False
    assert payload["outboundNotificationsSentByValidator"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert {section["id"] for section in payload["sections"]} == set(SECTION_IDS)


def test_missing_owner_scope_is_rejected(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact["ownerScopeSampling"] = _section(sampledOwnerLabels=[])
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["status"] == "fail"
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "owner_scope_missing" in reason_codes


def test_rejects_raw_contact_urls_and_secret_markers_without_echoing_values(tmp_path: Path) -> None:
    unsafe_email = "owner@example.com"
    unsafe_phone = "+1 415-555-0100"
    unsafe_webhook = "https://hooks.example.test/services/raw/path"
    unsafe_token = "sk-" + ("A" * 40)
    artifact = _artifact()
    artifact["budgetAlertDryRun"] = _section(
        sampledOwnerLabels=[unsafe_email],
        reviewerPhone=unsafe_phone,
        webhookUrl=unsafe_webhook,
        api_token=unsafe_token,
    )
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert unsafe_email not in combined_output
    assert unsafe_phone not in combined_output
    assert unsafe_webhook not in combined_output
    assert unsafe_token not in combined_output
    reason_codes = {finding["reasonCode"] for finding in _stdout_json(result)["findings"]}
    assert {"unsafe_contact_value", "unsafe_url_value", "unsafe_secret_marker"}.issubset(reason_codes)


def test_rejects_outbound_sent_and_launch_go_claims(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact["notificationNoOutboundProof"] = _section(
        outboundSent=True,
        rehearsalScope="launch_evidence",
        outcome="accepted",
        notes="launch-approved GO for public release",
    )
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "outbound_sent_forbidden" in reason_codes
    assert "launch_approval_claim_forbidden" in reason_codes


def test_non_launch_outbound_rehearsal_cannot_be_accepted_as_launch_evidence(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact["notificationNoOutboundProof"] = _section(
        outboundSent=True,
        rehearsalScope="separate_non_launch_rehearsal",
        outcome="needs-review",
    )
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "outbound_non_launch_rehearsal_not_launch_evidence" in reason_codes
    section = next(section for section in payload["sections"] if section["id"] == "notificationNoOutboundProof")
    assert section["status"] == "needs-review"


def test_rejects_threshold_enforcement_mutation_and_raw_debug_payloads(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact["quotaPilot"] = _section(
        thresholdMutation="threshold changed during pilot",
        enforcementMutation="live enforcement enabled for launch",
        rawRequestBody={"owner": "owner-alpha"},
        debugPayload="Traceback (most recent call last): hidden",
    )
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "threshold_or_enforcement_mutation_claim" in reason_codes
    assert "raw_payload_forbidden" in reason_codes
    assert "traceback_forbidden" in reason_codes


def test_missing_required_section_and_field_are_rejected(tmp_path: Path) -> None:
    artifact = deepcopy(_artifact())
    artifact.pop("disabledPreferenceSuppression")
    budget = deepcopy(artifact["budgetAlertDryRun"])
    assert isinstance(budget, dict)
    budget.pop("thresholdPolicyVersion")
    artifact["budgetAlertDryRun"] = budget
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    findings = {(finding["field"], finding["reasonCode"]) for finding in payload["findings"]}
    assert ("disabledPreferenceSuppression", "missing_required_section") in findings
    assert ("budgetAlertDryRun.thresholdPolicyVersion", "missing_required_field") in findings
