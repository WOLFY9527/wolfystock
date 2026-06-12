# -*- coding: utf-8 -*-
"""Offline provider SLA/licensing evidence validator tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "provider_sla_licensing_evidence_check.py"


def _artifact(**overrides: object) -> dict[str, object]:
    runtime_enforcement: dict[str, object] = {
        "claim": "not-claimed",
        "liveEnforcement": False,
        "wouldBlockCall": False,
    }
    payload: dict[str, object] = {
        "artifactVersion": "provider-sla-licensing-evidence-v1",
        "environment": "staging",
        "operator": "provider-ops",
        "observedAt": "2026-06-10T10:30:00Z",
        "providerFamily": "market-data",
        "entitlementLicensingStatus": "accepted",
        "credentialPresence": "redacted",
        "allowedUsageScope": "staging-read-only",
        "stagingProbeResult": "accepted",
        "degradedFallbackPolicy": "fallback-documented",
        "runtimeEnforcement": runtime_enforcement,
        "publicReadinessClaim": "not-claimed",
        "evidenceRedactionVersion": "provider_sla_licensing_redaction_v1",
        "notes": "Sanitized provider SLA and licensing evidence for manual review.",
    }
    payload.update(overrides)
    return payload


def _write_json(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "provider-sla-licensing-evidence.json"
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


def test_valid_sanitized_artifact_passes(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _artifact())

    result = _run_validator(path)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["finalStatus"] == "EVIDENCE-READY"
    assert payload["advisoryOnly"] is True
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["networkCallsExecutedByValidator"] is False
    assert payload["launchApproved"] is False
    assert payload["artifact"] == {
        "artifactVersion": "provider-sla-licensing-evidence-v1",
        "environment": "staging",
        "providerFamily": "market-data",
        "entitlementLicensingStatus": "accepted",
        "credentialPresence": "redacted",
        "allowedUsageScope": "staging-read-only",
        "stagingProbeResult": "accepted",
        "degradedFallbackPolicy": "fallback-documented",
        "runtimeEnforcementClaim": "not-claimed",
        "publicReadinessClaim": "not-claimed",
        "evidenceRedactionVersion": "provider_sla_licensing_redaction_v1",
    }


def test_missing_licensing_status_fails(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact.pop("entitlementLicensingStatus")
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    findings = {(finding["field"], finding["reasonCode"]) for finding in payload["findings"]}
    assert ("entitlementLicensingStatus", "missing_required_field") in findings


def test_raw_credential_fails_without_echoing_value(tmp_path: Path) -> None:
    secret_value = "provider-api-key-value-should-not-print"
    path = _write_json(
        tmp_path,
        _artifact(
            api_key=secret_value,
            headers={"Authorization": f"Bearer {secret_value}"},
        ),
    )

    result = _run_validator(path)

    combined_output = result.stdout + result.stderr
    assert result.returncode == 1
    assert secret_value not in combined_output
    assert "api_key" not in combined_output
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "credential_leakage_forbidden" in reason_codes


def test_raw_provider_payload_fails_without_echoing_payload(tmp_path: Path) -> None:
    raw_body = "raw-provider-response-body-should-not-print"
    path = _write_json(
        tmp_path,
        _artifact(
            rawProviderPayload={"body": raw_body},
            provider_payload={"quote": raw_body},
            raw_response={"response": raw_body},
        ),
    )

    result = _run_validator(path)

    combined_output = result.stdout + result.stderr
    assert result.returncode == 1
    assert raw_body not in combined_output
    assert "rawProviderPayload" not in combined_output
    assert "provider_payload" not in combined_output
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "payload_content_forbidden" in reason_codes


def test_public_ready_claim_without_accepted_staging_evidence_fails(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path,
        _artifact(
            publicReadinessClaim="public-ready",
            stagingProbeResult="needs-review",
            publicReadinessEvidence={
                "stagingProbeAccepted": False,
                "licensingEvidenceAccepted": True,
                "manualReviewRequired": True,
            },
        ),
    )

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    findings = {(finding["field"], finding["reasonCode"]) for finding in payload["findings"]}
    assert (
        "publicReadinessClaim",
        "public_ready_claim_requires_accepted_staging_evidence",
    ) in findings
    assert payload["launchApproved"] is False


def test_dry_run_advisory_artifact_does_not_imply_enforcement(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path,
        _artifact(
            dryRunOnly=True,
            advisoryBlockCandidate=True,
            runtimeEnforcement={
                "claim": "not-claimed",
                "liveEnforcement": False,
                "wouldBlockCall": False,
            },
        ),
    )

    result = _run_validator(path)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["advisoryOnly"] is True
    assert payload["runtimeEnforcementAccepted"] is False
    assert payload["runtime"]["liveEnforcement"] is False
    assert payload["runtime"]["wouldBlockCall"] is False
    assert payload["runtimeBehaviorChanged"] is False


def test_admin_probe_pilot_evidence_rejects_public_runtime_or_launch_claims(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path,
        _artifact(
            adminProbePilotEvidence={
                "contractVersion": "provider_admin_probe_pilot_evidence_v1",
                "adminProbeOnly": True,
                "defaultOffPosture": True,
                "rollbackAvailable": True,
                "selectedBoundary": "/api/v1/system/config/data-source/test-builtin",
                "providerCategory": "data_source_validation",
                "routeFamily": "admin_provider_probe",
                "publicRuntimeProviderBlocking": True,
                "memberRuntimeProviderBlocking": True,
                "providerRuntimeEnforcement": True,
                "providerOrderFallbackCacheBehaviorChanged": True,
                "sanitizedFieldsOnly": True,
                "acceptedOperatorEvidencePresent": False,
                "publicLaunchReady": True,
                "remainingPublicLaunchNoGoItems": ["public_provider_circuit_enforcement_not_accepted"],
            },
        ),
    )

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    findings = {(finding["field"], finding["reasonCode"]) for finding in payload["findings"]}
    assert (
        "adminProbePilotEvidence.publicRuntimeProviderBlocking",
        "admin_probe_evidence_must_not_claim_public_runtime_blocking",
    ) in findings
    assert (
        "adminProbePilotEvidence.memberRuntimeProviderBlocking",
        "admin_probe_evidence_must_not_claim_member_runtime_blocking",
    ) in findings
    assert (
        "adminProbePilotEvidence.providerRuntimeEnforcement",
        "admin_probe_evidence_must_not_claim_provider_runtime_enforcement",
    ) in findings
    assert (
        "adminProbePilotEvidence.providerOrderFallbackCacheBehaviorChanged",
        "admin_probe_evidence_must_not_change_provider_order_fallback_or_cache",
    ) in findings
    assert (
        "adminProbePilotEvidence.publicLaunchReady",
        "public_ready_claim_requires_accepted_staging_evidence",
    ) in findings
    assert payload["launchApproved"] is False
    assert payload["releaseApproved"] is False


def test_admin_probe_pilot_evidence_accepts_safe_default_off_review_contract(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path,
        _artifact(
            adminProbePilotEvidence={
                "contractVersion": "provider_admin_probe_pilot_evidence_v1",
                "adminProbeOnly": True,
                "defaultOffPosture": True,
                "rollbackAvailable": True,
                "selectedBoundary": "/api/v1/system/config/data-source/test-builtin",
                "apiRoute": "/api/v1/system/config/data-source/test-builtin",
                "providerCategory": "data_source_validation",
                "routeFamily": "admin_provider_probe",
                "publicRuntimeProviderBlocking": False,
                "memberRuntimeProviderBlocking": False,
                "providerRuntimeEnforcement": False,
                "providerOrderFallbackCacheBehaviorChanged": False,
                "sanitizedFieldsOnly": True,
                "acceptedOperatorEvidencePresent": False,
                "publicLaunchReady": False,
                "remainingPublicLaunchNoGoItems": [
                    "public_provider_circuit_enforcement_not_accepted",
                    "target_environment_provider_sla_evidence_missing",
                ],
            },
        ),
    )

    result = _run_validator(path)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["launchApproved"] is False
    assert payload["releaseApproved"] is False
    assert payload["providerRuntimeBehaviorChanged"] is False
    assert payload["providerOrderChanged"] is False
    assert payload["providerFallbackBehaviorChanged"] is False
    assert payload["marketCacheBehaviorChanged"] is False


def test_admin_probe_pilot_evidence_rejects_unsafe_artifact_fields_without_echoing_values(tmp_path: Path) -> None:
    unsafe_values = {
        "providerUrl": "https://provider.example.invalid/probe?token=url-token-should-not-print",
        "requestId": "req-secret-should-not-print",
        "request_id": "req-snake-secret-should-not-print",
        "token": "token=provider-token-should-not-print",
        "rawPayload": {"body": "raw-payload-should-not-print"},
        "trace": "Traceback trace-value-should-not-print",
        "traceId": "trace-id-should-not-print",
        "credential": "credential=provider-credential-should-not-print",
        "cacheKey": "market:fmp:AAPL:cache-key-should-not-print",
        "cache_key": "market:fmp:AAPL:cache-key-snake-should-not-print",
    }
    path = _write_json(
        tmp_path,
        _artifact(
            adminProbePilotEvidence={
                "contractVersion": "provider_admin_probe_pilot_evidence_v1",
                "adminProbeOnly": True,
                "defaultOffPosture": True,
                "rollbackAvailable": True,
                "selectedBoundary": "/api/v1/system/config/data-source/test-builtin",
                "providerCategory": "data_source_validation",
                "routeFamily": "admin_provider_probe",
                "publicRuntimeProviderBlocking": False,
                "memberRuntimeProviderBlocking": False,
                "providerRuntimeEnforcement": False,
                "providerOrderFallbackCacheBehaviorChanged": False,
                "sanitizedFieldsOnly": True,
                "acceptedOperatorEvidencePresent": False,
                "publicLaunchReady": False,
                "remainingPublicLaunchNoGoItems": ["public_provider_circuit_enforcement_not_accepted"],
                **unsafe_values,
            },
        ),
    )

    result = _run_validator(path)

    combined_output = result.stdout + result.stderr
    assert result.returncode == 1
    for unsafe_text in unsafe_values.values():
        if isinstance(unsafe_text, str):
            assert unsafe_text not in combined_output
    assert "raw-payload-should-not-print" not in combined_output
    assert "providerUrl" not in combined_output
    assert "requestId" not in combined_output
    assert "adminProbePilotEvidence.request_id" not in combined_output
    assert "rawPayload" not in combined_output
    assert "traceId" not in combined_output
    assert "cacheKey" not in combined_output
    assert "adminProbePilotEvidence.cache_key" not in combined_output
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "url_query_string_forbidden" in reason_codes
    assert "request_id_forbidden" in reason_codes
    assert "credential_leakage_forbidden" in reason_codes
    assert "payload_content_forbidden" in reason_codes
    assert "exception_or_stack_trace_forbidden" in reason_codes
    assert "cache_key_forbidden" in reason_codes


def test_output_is_sanitized_for_failure_paths(tmp_path: Path) -> None:
    raw_url = "https://provider.example.invalid/query?token=url-token-should-not-print"
    raw_user = "user@example.invalid"
    path = _write_json(
        tmp_path,
        _artifact(
            publicReadinessClaim="public ready",
            notes=f"Provider says public ready for {raw_user}",
            raw_url=raw_url,
            sessionId="session-value-should-not-print",
            exceptionText="Traceback: provider timeout should-not-print",
        ),
    )

    result = _run_validator(path)

    combined_output = result.stdout + result.stderr
    assert result.returncode == 1
    for unsafe_text in (
        raw_url,
        raw_user,
        "session-value-should-not-print",
        "provider timeout should-not-print",
        "raw_url",
        "sessionId",
        "exceptionText",
    ):
        assert unsafe_text not in combined_output
    payload = _stdout_json(result)
    assert payload["rawArtifactBodiesIncluded"] is False
    assert payload["secretValuesPrintedByValidator"] is False
