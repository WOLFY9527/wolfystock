from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_bundle_check.py"


def _provider_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "providerName": "tradier",
        "environment": "staging",
        "operator": "provider-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "probeMode": "manual_provider_probe",
        "networkCallsEnabled": True,
        "credentialPresence": "redacted",
        "circuitState": {"state": "closed", "summary": "No forced circuit override recorded."},
        "fallbackState": {"state": "unchanged", "summary": "Runtime fallback policy was observed only."},
        "outcome": "accepted",
        "evidenceRedactionVersion": "provider_operator_redaction_v1",
        "notes": "Sanitized operator artifact for later review.",
    }
    payload.update(overrides)
    return payload


def _restore_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schemaVersion": "wolfystock_restore_pitr_operator_evidence_input_v1",
        "drillId": "restore-pitr-2026-05-08-001",
        "environment": "isolated-restore",
        "operator": "ops-oncall-sanitized",
        "startedAt": "2026-05-08T09:00:00Z",
        "completedAt": "2026-05-08T09:37:00Z",
        "backupArtifactRef": "backup-ref:sha256-0123456789abcdef",
        "restoreTarget": "restore-target:sandbox-pg-20260508",
        "restoreCommandExecuted": True,
        "destructiveProductionCommandExecuted": False,
        "pitrTargetTimestamp": "2026-05-08T08:45:00Z",
        "verificationQueries": [
            {
                "label": "auth-row-count",
                "resultKind": "count",
                "observedCount": 12,
                "expectedCount": 12,
                "checksum": "sha256:auth-count-fixture",
            }
        ],
        "rpoObservedSeconds": 420,
        "rtoObservedSeconds": 2220,
        "outcome": "accepted",
        "evidenceRedactionVersion": "restore-pitr-redaction-v1",
        "localGeneration": {
            "checkerRanRestoreCommands": False,
            "networkCallsEnabled": False,
            "productionStorageTouched": False,
            "productionSecretsRead": False,
            "rawLogsIncluded": False,
            "runtimeBehaviorChanged": False,
        },
    }
    payload.update(overrides)
    return payload


def _security_artifact() -> dict[str, object]:
    base_section: dict[str, object] = {
        "sanitizedOperator": "staging-operator-a",
        "timestamp": "2026-05-08T10:00:00Z",
        "environment": "staging",
        "outcome": "accepted",
        "sampledControls": ["control-review", "redaction-check"],
        "evidenceRedactionVersion": "operator-redaction-v1",
    }
    return {
        "schemaVersion": "wolfystock_security_operator_acceptance_artifact_v1",
        "mfaAdminPilot": {
            **base_section,
            "testAccountRoleLabels": ["admin_mfa_pilot", "support_admin"],
            "runtimeBehaviorChanged": False,
        },
        "rbacFallbackDisable": {
            **base_section,
            "fallbackDisabled": True,
            "legacyAdminDenied": True,
            "explicitCapabilitiesAccepted": True,
            "runtimeBehaviorChanged": False,
        },
        "breakGlassRecovery": {
            **base_section,
            "breakGlassDefaultOff": True,
            "recoveryFallbackSampled": True,
            "runtimeBehaviorChanged": False,
        },
        "adminRouteSampling": {
            **base_section,
            "sampledRoutes": ["/zh/admin/cost-observability", "/zh/settings/system"],
            "runtimeBehaviorChanged": False,
        },
    }


QUOTA_SECTIONS = (
    "quotaPilot",
    "budgetAlertDryRun",
    "ownerScopeSampling",
    "disabledPreferenceSuppression",
    "notificationNoOutboundProof",
)


def _quota_section(**overrides: object) -> dict[str, object]:
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


def _quota_artifact() -> dict[str, object]:
    return {
        "schemaVersion": "wolfystock_quota_operator_evidence_v1",
        "mode": "operator_sanitized",
        **{section_id: _quota_section() for section_id in QUOTA_SECTIONS},
    }


def _ingress_artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifactVersion": "wolfystock_staging_ingress_operator_evidence_v1",
        "environment": "staging",
        "operator": "staging-ingress-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "baseUrlLabel": "staging-ingress-primary",
        "networkCallsEnabled": True,
        "checkedRoutes": [
            {
                "routeLabel": "health-ready",
                "method": "GET",
                "pathPattern": "/api/health/ready",
                "statusClass": "2xx",
                "summary": "Public readiness route returned bounded health metadata.",
            }
        ],
        "authBoundaryResult": {
            "status": "accepted",
            "summary": "Protected routes failed closed for unauthenticated access.",
        },
        "securityHeaderSummary": {
            "status": "accepted",
            "summary": "Expected security header names were observed without header values.",
        },
        "csrfOrStateMutationSummary": {
            "status": "accepted",
            "summary": "No state-changing operation was attempted during evidence collection.",
        },
        "publicSurfaceSummary": {
            "status": "accepted",
            "summary": "Only bounded public health surfaces were sampled.",
        },
        "rateLimitOrAbuseSummary": {
            "status": "accepted",
            "summary": "Abuse-control posture was summarized with counters only.",
        },
        "outcome": "accepted",
        "evidenceRedactionVersion": "staging_ingress_operator_redaction_v1",
        "notes": "Sanitized staging ingress operator artifact for later launch review.",
    }
    payload.update(overrides)
    return payload


def _write_bundle(tmp_path: Path, artifacts: dict[str, object]) -> Path:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for filename, payload in artifacts.items():
        (bundle / filename).write_text(json.dumps(payload), encoding="utf-8")
    return bundle


def _accepted_artifacts() -> dict[str, object]:
    return {
        "provider_operator_evidence.json": _provider_artifact(),
        "restore_pitr_operator_evidence.json": _restore_artifact(),
        "security_operator_acceptance.json": _security_artifact(),
        "quota_budget_operator_evidence.json": _quota_artifact(),
        "staging_ingress_operator_evidence.json": _ingress_artifact(),
    }


def _run_checker(bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(bundle)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _stdout_json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout)


def test_all_sanitized_accepted_artifacts_require_manual_review(tmp_path: Path) -> None:
    result = _run_checker(_write_bundle(tmp_path, _accepted_artifacts()))

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["bundleStatus"] == "complete-review-required"
    assert {artifact["status"] for artifact in payload["artifacts"]} == {"accepted"}
    assert all(Path(artifact["pathLabel"]).name == artifact["pathLabel"] for artifact in payload["artifacts"])
    assert "launch-approved" not in result.stdout.lower()
    assert "production-ready" not in result.stdout.lower()
    assert "release-approved" not in result.stdout.lower()


def test_missing_required_artifact_is_incomplete_no_go(tmp_path: Path) -> None:
    artifacts = _accepted_artifacts()
    artifacts.pop("quota_budget_operator_evidence.json")

    result = _run_checker(_write_bundle(tmp_path, artifacts))

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["bundleStatus"] == "incomplete-no-go"
    quota = next(artifact for artifact in payload["artifacts"] if artifact["category"] == "quota-budget")
    assert quota["status"] == "missing"
    assert quota["blockingReasonSummaries"] == ["required_artifact_missing"]


def test_rejected_artifact_is_rejected_no_go(tmp_path: Path) -> None:
    artifacts = _accepted_artifacts()
    rejected_restore = deepcopy(artifacts["restore_pitr_operator_evidence.json"])
    assert isinstance(rejected_restore, dict)
    rejected_restore["outcome"] = "rejected"
    artifacts["restore_pitr_operator_evidence.json"] = rejected_restore

    result = _run_checker(_write_bundle(tmp_path, artifacts))

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["bundleStatus"] == "rejected-no-go"
    restore = next(artifact for artifact in payload["artifacts"] if artifact["category"] == "restore-pitr")
    assert restore["status"] == "rejected"
    assert "operator_outcome_is_accepted:fail" in restore["blockingReasonSummaries"]


def test_unsafe_marker_does_not_leak_into_summary_output(tmp_path: Path) -> None:
    unsafe_value = "raw-secret-value-should-not-leak"
    artifacts = _accepted_artifacts()
    artifacts["provider_operator_evidence.json"] = _provider_artifact(api_key=unsafe_value)

    result = _run_checker(_write_bundle(tmp_path, artifacts))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert unsafe_value not in combined_output
    assert "api_key" not in combined_output
    payload = _stdout_json(result)
    provider = next(artifact for artifact in payload["artifacts"] if artifact["category"] == "provider")
    assert provider["status"] == "rejected"
    assert provider["blockingReasonSummaries"] == ["unsafe_marker"]


def test_unknown_extra_artifact_is_reported_as_advisory_only(tmp_path: Path) -> None:
    artifacts = _accepted_artifacts()
    artifacts["unexpected_operator_dump.json"] = {"raw": "ignored"}

    result = _run_checker(_write_bundle(tmp_path, artifacts))

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["bundleStatus"] == "complete-review-required"
    assert payload["advisories"] == [
        {
            "category": "unknown-extra-artifact",
            "pathLabel": "unexpected_operator_dump.json",
            "status": "needs-review",
            "validatorName": "operator_evidence_bundle_check.py",
            "blockingReasonSummaries": ["unknown_artifact_not_validated"],
        }
    ]
