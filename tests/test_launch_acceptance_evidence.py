from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "launch_acceptance_evidence.py"
ACCEPTED_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "release" / "launch_acceptance_evidence.accepted.json"
MISSING_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "release" / "launch_acceptance_evidence.missing.json"


def _run_checker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _json(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def test_launch_acceptance_evidence_missing_categories_remain_no_go() -> None:
    result = _run_checker("--evidence", str(MISSING_FIXTURE))

    assert result.returncode == 1
    evidence = _json(result)
    assert evidence["schemaVersion"] == "wolfystock_launch_acceptance_evidence_summary_v1"
    assert evidence["finalStatus"] == "NO-GO"
    assert evidence["releaseApproved"] is False
    assert evidence["sanitization"] == {
        "externalServicesCalled": False,
        "networkCallsEnabled": False,
        "realEnvFileRead": False,
        "secretValuesRead": False,
        "secretValuesIncluded": False,
        "rawPayloadsIncluded": False,
        "responseBodiesIncluded": False,
        "productionDataPathsRead": False,
        "runtimeDefaultsChanged": False,
    }
    assert evidence["summary"]["accepted"] == 0
    assert evidence["summary"]["blocking"] == 10
    blocker_ids = {item["id"] for item in evidence["hardBlockers"]}
    assert {
        "mfa_pilot_acceptance",
        "rbac_fallback_disable_switch",
        "provider_credential_staging_dry_run",
        "provider_circuit_controlled_enforcement",
        "quota_pilot_acceptance",
        "real_isolated_postgresql_restore_pitr",
        "staging_ingress_smoke",
        "public_api_frontend_no_secret_safety",
        "supply_chain_dependency_build_artifact_safety",
        "final_clean_full_ci_gate",
    } == blocker_ids


def test_launch_acceptance_evidence_allow_no_go_returns_zero_for_review_attachment() -> None:
    result = _run_checker("--evidence", str(MISSING_FIXTURE), "--allow-no-go")

    assert result.returncode == 0
    assert _json(result)["finalStatus"] == "NO-GO"


def test_launch_acceptance_evidence_all_accepted_is_go_review_required_not_approved() -> None:
    result = _run_checker("--evidence", str(ACCEPTED_FIXTURE))

    assert result.returncode == 0
    evidence = _json(result)
    assert evidence["finalStatus"] == "GO-REVIEW-REQUIRED"
    assert evidence["releaseApproved"] is False
    assert evidence["statusReason"] == "All hard blockers have accepted sanitized evidence; release approval remains manual."
    assert evidence["summary"]["accepted"] == 10
    assert evidence["summary"]["blocking"] == 0
    assert evidence["hardBlockers"] == []
    categories = {item["id"]: item for item in evidence["categories"]}
    assert categories["mfa_pilot_acceptance"]["requiredChecks"] == [
        "adminPilotPassed",
        "adminOnlyScopeRecorded",
        "unsupportedGlobalRolloutNoGo",
        "recoveryPathTested",
        "breakGlassDisabledByDefault",
        "rollbackPlanRecorded",
        "auditEvidenceSanitized",
        "secretEvidenceRedacted",
    ]
    assert categories["rbac_fallback_disable_switch"]["requiredChecks"] == [
        "disableSwitchExplicit",
        "routeInventoryComplete",
        "coarseFallbackDisabledOrExceptionAccepted",
        "explicitCapabilityPayloadsPassWithoutFallback",
        "legacyMissingCapabilityUsersFailClosed",
        "rollbackPlanRecorded",
        "auditEvidenceSanitized",
        "runtimeDefaultUnchanged",
    ]
    assert categories["provider_credential_staging_dry_run"]["requiredChecks"] == [
        "stagingDryRunPassed",
        "liveProbeOptInRecorded",
        "liveProbeTimeoutBounded",
        "credentialPresenceOnly",
        "noLiveCallsByChecker",
        "entitlementMatrixAttached",
    ]
    assert categories["provider_circuit_controlled_enforcement"]["status"] == "accepted"
    assert categories["provider_circuit_controlled_enforcement"]["requiredChecks"] == [
        "controlledEnforcementPilotPassed",
        "boundedRouteRecorded",
        "rollbackSwitchRecorded",
        "degradedEvidenceSanitized",
    ]
    assert categories["supply_chain_dependency_build_artifact_safety"]["requiredChecks"] == [
        "dependencyManifestsInspected",
        "manifestsSanitized",
        "buildArtifactsSanitized",
        "frontendBuildWarningsVisible",
        "noDependencyOrLockfileChanges",
        "missingEvidenceNoGoVerified",
    ]


def test_launch_acceptance_evidence_keeps_provider_circuit_required_when_missing(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"].pop("provider_circuit_controlled_enforcement")
    evidence_path = tmp_path / "missing-provider-circuit.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    assert evidence["finalStatus"] == "NO-GO"
    assert evidence["summary"]["blocking"] == 1
    assert evidence["hardBlockers"] == [
        {
            "id": "provider_circuit_controlled_enforcement",
            "status": "blocking",
            "requiredEvidence": "controlled provider-circuit enforcement pilot, bounded route, rollback switch, and sanitized degraded-state evidence",
        }
    ]


def test_launch_acceptance_evidence_rejects_secret_like_values_without_leaking(tmp_path: Path) -> None:
    secret = "sk-" + ("A" * 40)
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["provider_credential_staging_dry_run"]["evidenceRef"] = secret
    evidence_path = tmp_path / "unsafe-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert secret not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "provider_credential_staging_dry_run")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_rejects_mfa_secret_fields_without_leaking(tmp_path: Path) -> None:
    recovery_code = "RECOVERY-CODE-1234"
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["mfa_pilot_acceptance"]["operatorArtifact"] = {
        "totp_secret": "totp-secret",
        "mfa_recovery_code": recovery_code,
        "session_id": "raw-session-id",
    }
    evidence_path = tmp_path / "unsafe-mfa-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert recovery_code not in combined_output
    assert "totp-secret" not in combined_output
    assert "raw-session-id" not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "mfa_pilot_acceptance")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_requires_provider_live_probe_contract_checks(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    checks = payload["categories"]["provider_credential_staging_dry_run"]["checks"]
    checks.pop("liveProbeOptInRecorded")
    checks.pop("liveProbeTimeoutBounded")
    evidence_path = tmp_path / "missing-provider-live-probe-contract.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "provider_credential_staging_dry_run")
    assert category["status"] == "blocking"
    assert category["missingChecks"] == ["liveProbeOptInRecorded", "liveProbeTimeoutBounded"]
    assert category["reasonCodes"] == ["missing_required_checks"]


def test_launch_acceptance_evidence_rejects_build_artifact_secret_patterns_without_leaking(tmp_path: Path) -> None:
    secret = "postgresql://launch_user:secret-pass@example.test:5432/wolfy"
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    payload["categories"]["supply_chain_dependency_build_artifact_safety"]["artifactEvidence"] = {
        "file": "dist/assets/app.js",
        "dsn": secret,
    }
    evidence_path = tmp_path / "unsafe-artifact-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert secret not in combined_output
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "supply_chain_dependency_build_artifact_safety")
    assert category["status"] == "blocking"
    assert category["reasonCodes"] == ["sensitive_value_present"]


def test_launch_acceptance_evidence_requires_supply_chain_manifest_and_artifact_checks(tmp_path: Path) -> None:
    payload = json.loads(ACCEPTED_FIXTURE.read_text(encoding="utf-8"))
    checks = payload["categories"]["supply_chain_dependency_build_artifact_safety"]["checks"]
    checks.pop("dependencyManifestsInspected")
    checks.pop("buildArtifactsSanitized")
    evidence_path = tmp_path / "missing-supply-chain-checks.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_checker("--evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _json(result)
    category = next(item for item in evidence["categories"] if item["id"] == "supply_chain_dependency_build_artifact_safety")
    assert category["status"] == "blocking"
    assert category["missingChecks"] == ["dependencyManifestsInspected", "buildArtifactsSanitized"]
    assert category["reasonCodes"] == ["missing_required_checks"]
