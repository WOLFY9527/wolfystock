from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_manifest_check.py"
EXPECTED_MANIFEST_CATEGORIES = {
    "api-abuse-request-safety",
    "provider",
    "provider-sla-licensing",
    "notification-delivery-rehearsal",
    "restore-pitr",
    "security",
    "quota-budget",
    "staging-ingress",
    "ws2-target-environment",
    "ws2-sse",
    "config-snapshot",
    "manual-release-approval",
}


def _write_artifact_dir(tmp_path: Path, *, unsafe_value: str = "raw-body-value-never-output") -> Path:
    artifact_dir = tmp_path / "sanitized-bundle"
    artifact_dir.mkdir()
    artifacts = {
        "api_abuse_safety_evidence.json": {
            "artifactVersion": "wolfystock_api_abuse_request_safety_evidence_v1",
            "outcome": "accepted",
            "evidenceRedactionVersion": "api-abuse-request-safety-redaction-v1",
        },
        "provider_operator_evidence.json": {
            "providerName": "tradier",
            "operator": "provider-ops",
            "outcome": "accepted",
            "evidenceRedactionVersion": "provider_operator_redaction_v1",
            "notes": unsafe_value,
        },
        "provider_sla_licensing_evidence.json": {
            "artifactVersion": "wolfystock_provider_sla_licensing_evidence_v1",
            "environment": "staging",
            "operator": "provider-ops",
            "outcome": "accepted",
            "evidenceRedactionVersion": "provider-sla-licensing-redaction-v1",
        },
        "notification_delivery_rehearsal_evidence.json": {
            "schemaVersion": "wolfystock_notification_delivery_rehearsal_evidence_v1",
            "outcome": "accepted",
            "evidenceRedactionVersion": "notification_delivery_rehearsal_redaction_v1",
        },
        "restore_pitr_operator_evidence.json": {
            "schemaVersion": "wolfystock_restore_pitr_operator_evidence_input_v1",
            "outcome": "accepted",
            "evidenceRedactionVersion": "restore-pitr-redaction-v1",
        },
        "security_operator_acceptance.json": {
            "schemaVersion": "wolfystock_security_operator_acceptance_artifact_v1",
            "mfaAdminPilot": {
                "outcome": "accepted",
                "evidenceRedactionVersion": "operator-redaction-v1",
            },
        },
        "quota_budget_operator_evidence.json": {
            "schemaVersion": "wolfystock_quota_operator_evidence_v1",
            "quotaPilot": {
                "outcome": "accepted",
                "evidenceRedactionVersion": "quota_budget_operator_redaction_v1",
            },
        },
        "staging_ingress_operator_evidence.json": {
            "artifactVersion": "wolfystock_staging_ingress_operator_evidence_v1",
            "outcome": "accepted",
            "evidenceRedactionVersion": "staging_ingress_operator_redaction_v1",
        },
        "ws2_target_environment_evidence.json": {
            "artifactVersion": "wolfystock_ws2_target_environment_evidence_v1",
            "evidenceRedactionVersion": "ws2_target_environment_evidence_redaction_v1",
        },
        "ws2_sse_operator_decision_evidence.json": {
            "artifactVersion": "wolfystock_ws2_sse_operator_decision_evidence_v1",
            "outcome": "accepted",
            "evidenceRedactionVersion": "ws2_sse_operator_decision_redaction_v1",
        },
        "config_snapshot_evidence.json": {
            "artifactVersion": "wolfystock_config_snapshot_evidence_v1",
            "environment": "production-like-staging",
            "operator": "release-ops",
            "observedAt": "2026-05-08T10:30:00Z",
            "authConfigSummary": "Admin auth enabled; MFA rollout mode reviewed; RBAC posture documented.",
            "providerConfigSummary": "Provider presence documented with redacted-only credential posture.",
            "quotaConfigSummary": "Quota mode documented without owner identifiers.",
            "notificationConfigSummary": "Notification routing posture documented without webhook URLs or tokens.",
            "databaseConfigSummary": "Database storage and backup posture documented without DSNs.",
            "loggingRetentionSummary": "Retention window documented without raw logs.",
            "rollbackConfigSummary": "Rollback switches documented without command output.",
            "secretPresenceSummary": "redacted only",
            "unsafeDefaultsSummary": "Unsafe defaults reviewed without raw config values.",
            "postureEvidence": {
                "targetEnvironmentLabel": "production-review-label",
                "productionMode": "production",
                "authEnabled": "enabled",
                "corsPosture": "restricted-origins",
                "csrfPosture": "trusted-origins-configured",
                "trustedProxyPosture": "explicit",
                "mfaEnforcementScope": "admin-only",
                "rbacFallbackPosture": "disabled",
                "quotaMode": "pilot",
                "backupPitrOptIn": "disabled",
                "stagingIngressOptIn": "disabled",
                "publicSearxngInstancePosture": "disabled",
                "cryptoRealtimeDecisionPosture": "disabled",
                "providerCredentialPresenceStates": {
                    "llmProvider": "configured",
                    "marketDataProvider": "configured",
                    "optionsLiveProvider": "missing",
                },
            },
            "manualReview": {
                "status": "accepted",
                "reviewTicketRef": "review-ticket-label",
                "targetEnvironmentEvidenceRequired": True,
            },
            "releaseApproved": False,
            "publicLaunchReady": False,
            "outcome": "accepted",
            "evidenceRedactionVersion": "config_snapshot_redaction_v1",
        },
        "manual_release_approval_review_record.json": {
            "artifactVersion": "wolfystock_manual_release_approval_review_record_v1",
            "goNoGoDecision": "approved-for-manual-release-review",
            "evidenceRedactionVersion": "manual-release-review-redaction-v1",
        },
    }
    for filename, payload in artifacts.items():
        (artifact_dir / filename).write_text(json.dumps(payload), encoding="utf-8")
    return artifact_dir


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _create_manifest(artifact_dir: Path, manifest: Path) -> subprocess.CompletedProcess[str]:
    return _run("create", "--artifact-dir", artifact_dir, "--output", manifest)


def _verify_manifest(artifact_dir: Path, manifest: Path) -> subprocess.CompletedProcess[str]:
    return _run("verify", "--artifact-dir", artifact_dir, "--manifest", manifest)


def _read_manifest(manifest: Path) -> dict[str, object]:
    return json.loads(manifest.read_text(encoding="utf-8"))


def test_create_manifest_for_sanitized_fixture_directory(tmp_path: Path) -> None:
    artifact_dir = _write_artifact_dir(tmp_path)
    manifest = tmp_path / "manifest.json"

    result = _create_manifest(artifact_dir, manifest)

    assert result.returncode == 0
    payload = _read_manifest(manifest)
    entries = payload["entries"]
    assert isinstance(entries, list)
    assert len(entries) == 12
    assert {entry["category"] for entry in entries} == EXPECTED_MANIFEST_CATEGORIES
    assert all(Path(entry["fileLabel"]).name == entry["fileLabel"] for entry in entries)
    assert all(set(entry) <= {"category", "fileLabel", "sha256", "byteSize", "generatedAt", "validatorName", "redactionVersion"} for entry in entries)
    assert all(entry["sha256"] for entry in entries)
    assert all(entry["byteSize"] > 0 for entry in entries)


def test_verify_unchanged_manifest_passes(tmp_path: Path) -> None:
    artifact_dir = _write_artifact_dir(tmp_path)
    manifest = tmp_path / "manifest.json"
    assert _create_manifest(artifact_dir, manifest).returncode == 0

    result = _verify_manifest(artifact_dir, manifest)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["verificationStatus"] == "pass"
    assert payload["rawArtifactBodiesIncluded"] is False
    assert payload["findings"] == []


def test_modified_artifact_fails_verification(tmp_path: Path) -> None:
    artifact_dir = _write_artifact_dir(tmp_path)
    manifest = tmp_path / "manifest.json"
    assert _create_manifest(artifact_dir, manifest).returncode == 0
    (artifact_dir / "provider_operator_evidence.json").write_text('{"changed": true}', encoding="utf-8")

    result = _verify_manifest(artifact_dir, manifest)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["verificationStatus"] == "fail"
    assert {
        "category": "provider",
        "fileLabel": "provider_operator_evidence.json",
        "reasonCode": "checksum_changed",
    } in payload["findings"]


def test_missing_artifact_fails_verification(tmp_path: Path) -> None:
    artifact_dir = _write_artifact_dir(tmp_path)
    manifest = tmp_path / "manifest.json"
    assert _create_manifest(artifact_dir, manifest).returncode == 0
    (artifact_dir / "quota_budget_operator_evidence.json").unlink()

    result = _verify_manifest(artifact_dir, manifest)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert {
        "category": "quota-budget",
        "fileLabel": "quota_budget_operator_evidence.json",
        "reasonCode": "missing_file",
    } in payload["findings"]


def test_path_traversal_rejected(tmp_path: Path) -> None:
    artifact_dir = _write_artifact_dir(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": "wolfystock_operator_evidence_manifest_v1",
                "generatedAt": "2026-05-08T00:00:00+00:00",
                "entries": [
                    {
                        "category": "provider",
                        "fileLabel": "../provider_operator_evidence.json",
                        "sha256": "0" * 64,
                        "byteSize": 1,
                        "generatedAt": "2026-05-08T00:00:00+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = _verify_manifest(artifact_dir, manifest)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert {
        "category": "provider",
        "fileLabel": "[redacted]",
        "reasonCode": "path_traversal_rejected",
    } in payload["findings"]


def test_manifest_output_does_not_leak_raw_artifact_body_values(tmp_path: Path) -> None:
    unsafe_value = "raw-body-secret-value-should-not-leak"
    artifact_dir = _write_artifact_dir(tmp_path, unsafe_value=unsafe_value)
    manifest = tmp_path / "manifest.json"

    result = _create_manifest(artifact_dir, manifest)

    assert result.returncode == 0
    combined_output = result.stdout + result.stderr + manifest.read_text(encoding="utf-8")
    assert unsafe_value not in combined_output
    assert "notes" not in combined_output


def test_unsafe_manifest_fields_and_unknown_required_artifacts_fail(tmp_path: Path) -> None:
    artifact_dir = _write_artifact_dir(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": "wolfystock_operator_evidence_manifest_v1",
                "generatedAt": "2026-05-08T00:00:00+00:00",
                "rawBody": {"secret": "do-not-print"},
                "entries": [
                    {
                        "category": "unexpected",
                        "fileLabel": "unexpected_operator_dump.json",
                        "sha256": "0" * 64,
                        "byteSize": 1,
                        "generatedAt": "2026-05-08T00:00:00+00:00",
                        "rawBody": "do-not-print",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = _verify_manifest(artifact_dir, manifest)

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert "do-not-print" not in combined_output
    payload = json.loads(result.stdout)
    assert {"category": "manifest", "fileLabel": "manifest.json", "reasonCode": "unsafe_manifest_field"} in payload["findings"]
    assert {
        "category": "unexpected",
        "fileLabel": "unexpected_operator_dump.json",
        "reasonCode": "unknown_required_artifact",
    } in payload["findings"]
