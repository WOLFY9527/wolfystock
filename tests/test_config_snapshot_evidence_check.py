# -*- coding: utf-8 -*-
"""Offline production/staging config snapshot evidence validator tests."""

from __future__ import annotations

from pathlib import Path

from tests.helpers.cli_validator import make_cli_validator, stdout_json as _stdout_json


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "config_snapshot_evidence_check.py"
_write_json, _run_validator = make_cli_validator(
    SCRIPT,
    cwd=REPO_ROOT,
    artifact_name="config-snapshot-evidence.json",
)


def _artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifactVersion": "config-snapshot-evidence-v1",
        "environment": "production-like-staging",
        "operator": "release-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "authConfigSummary": "Admin auth enabled; MFA rollout mode reviewed; RBAC posture documented.",
        "providerConfigSummary": "Primary and fallback provider presence documented with redacted-only credential posture.",
        "quotaConfigSummary": "Quota mode and alert posture documented without thresholds or owner identifiers.",
        "notificationConfigSummary": "Notification routing posture documented without webhook URLs or tokens.",
        "databaseConfigSummary": "Database storage and backup posture documented without DSNs.",
        "loggingRetentionSummary": "Retention window and audit logging posture documented without raw logs.",
        "rollbackConfigSummary": "Rollback switches and restore expectations documented without command output.",
        "secretPresenceSummary": "redacted only",
        "unsafeDefaultsSummary": "Operator reviewed unsafe defaults; no raw config values included.",
        "outcome": "accepted",
        "evidenceRedactionVersion": "config_snapshot_redaction_v1",
    }
    payload.update(overrides)
    return payload


def test_accepts_sanitized_config_snapshot(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _artifact())

    result = _run_validator(path)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["advisoryOnly"] is True
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["launchAcceptanceIntegrated"] is False
    assert payload["networkCallsExecutedByValidator"] is False
    assert payload["realEnvReadByValidator"] is False
    assert payload["artifact"]["environment"] == "production-like-staging"
    assert payload["artifact"]["outcome"] == "accepted"


def test_actual_secret_markers_are_rejected_without_echoing_values(tmp_path: Path) -> None:
    secret_value = "raw-password-value-should-not-print"
    dsn_value = f"postgresql://app_user:{secret_value}@db.example.invalid/wolfystock"
    path = _write_json(
        tmp_path,
        _artifact(databaseConfigSummary=f"Primary database uses {dsn_value}"),
    )

    result = _run_validator(path)

    combined_output = result.stdout + result.stderr
    assert result.returncode == 1
    assert secret_value not in combined_output
    assert dsn_value not in combined_output
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "secret_like_value_detected" in reason_codes


def test_raw_env_or_config_dump_is_rejected(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path,
        _artifact(
            rawEnvDump={
                "APP_ENV": "production",
                "ADMIN_AUTH_ENABLED": "true",
            },
            unsafeDefaultsSummary="Captured .env dump and config dump for reviewer convenience.",
        ),
    )

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "raw_config_dump_forbidden" in reason_codes


def test_accepted_outcome_missing_critical_summary_is_rejected(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact.pop("providerConfigSummary")
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    findings = {(finding["field"], finding["reasonCode"]) for finding in payload["findings"]}
    assert ("providerConfigSummary", "missing_required_field") in findings
    assert ("outcome", "accepted_missing_critical_summary") in findings


def test_launch_approved_claim_is_rejected(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path,
        _artifact(
            outcome="accepted",
            rollbackConfigSummary="Operator says launch-approved GO for production-ready release.",
        ),
    )

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "launch_approval_claim_forbidden" in reason_codes
