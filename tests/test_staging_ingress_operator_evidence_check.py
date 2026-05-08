from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "staging_ingress_operator_evidence_check.py"


def _artifact(**overrides: object) -> dict[str, object]:
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
            },
            {
                "routeLabel": "admin-boundary",
                "method": "GET",
                "pathPattern": "/api/v1/admin/users",
                "statusClass": "401-or-403",
                "summary": "Protected admin route failed closed for unauthenticated access.",
            },
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


def _write_json(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "staging-ingress-operator-evidence.json"
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


def test_accepts_sanitized_operator_artifact(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _artifact())

    result = _run_validator(path)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["advisoryOnly"] is True
    assert payload["launchAcceptanceIntegrated"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["networkCallsExecutedByValidator"] is False
    assert payload["artifact"]["environment"] == "staging"
    assert payload["artifact"]["outcome"] == "accepted"


def test_missing_required_fields_are_rejected(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact.pop("observedAt")
    artifact.pop("checkedRoutes")
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["status"] == "fail"
    missing_fields = {
        finding["field"]
        for finding in payload["findings"]
        if finding["reasonCode"] == "missing_required_field"
    }
    assert {"observedAt", "checkedRoutes"}.issubset(missing_fields)


def test_secret_header_and_cookie_markers_are_rejected_without_echoing_values(tmp_path: Path) -> None:
    secret_value = "Be" + "arer " + "should-not-appear-in-output"
    artifact = _artifact(
        headers={"Auth" + "orization": secret_value, "Set-" + "Cookie": "sid=should-not-appear"},
        notes="operator included cookie and api_key markers by mistake",
    )
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    assert "should-not-appear" not in result.stdout
    assert "should-not-appear" not in result.stderr
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "secret_or_header_marker_forbidden" in reason_codes


def test_raw_request_response_and_debug_payloads_are_rejected(tmp_path: Path) -> None:
    artifact = _artifact(
        rawRequestBody={"symbol": "AAPL"},
        rawResponseBody={"status": "ok"},
        debugPayload={"trace": "Traceback (most recent call last): sanitized"},
    )
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    raw_fields = {
        finding["field"]
        for finding in payload["findings"]
        if finding["reasonCode"] in {"raw_payload_forbidden", "debug_trace_forbidden"}
    }
    assert {"rawRequestBody", "rawResponseBody", "debugPayload"}.issubset(raw_fields)


def test_credential_url_is_rejected_without_echoing_url(tmp_path: Path) -> None:
    credential_url = "https://" + "operator" + ":" + "secret" + "@example.invalid/api/health"
    path = _write_json(tmp_path, _artifact(baseUrlLabel=credential_url))

    result = _run_validator(path)

    assert result.returncode == 1
    assert credential_url not in result.stdout
    assert credential_url not in result.stderr
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "invalid_base_url_label" in reason_codes
    assert "credential_url_forbidden" in reason_codes


def test_launch_approval_or_go_claims_are_rejected(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _artifact(notes="Launch-approved. GO for public launch."))

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert {
        finding["reasonCode"] for finding in payload["findings"]
    } >= {"launch_approval_claim_forbidden"}


def test_accepted_outcome_requires_staging_environment_and_required_summaries(tmp_path: Path) -> None:
    production_path = _write_json(tmp_path, _artifact(environment="production"))

    production_result = _run_validator(production_path)

    assert production_result.returncode == 1
    production_payload = _stdout_json(production_result)
    assert {
        finding["reasonCode"] for finding in production_payload["findings"]
    } >= {"invalid_environment", "accepted_outcome_requires_staging_or_sandbox_environment"}

    missing_summary_path = _write_json(
        tmp_path,
        _artifact(authBoundaryResult="", securityHeaderSummary={}),
    )

    missing_summary_result = _run_validator(missing_summary_path)

    assert missing_summary_result.returncode == 1
    missing_summary_payload = _stdout_json(missing_summary_result)
    assert {
        finding["reasonCode"] for finding in missing_summary_payload["findings"]
    } >= {"accepted_outcome_requires_auth_boundary_summary", "accepted_outcome_requires_security_header_summary"}


def test_production_mutation_or_destructive_commands_are_rejected(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path,
        _artifact(notes="Operator ran kubectl delete deployment in production to validate ingress."),
    )

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert {
        finding["reasonCode"] for finding in payload["findings"]
    } >= {"production_mutation_or_destructive_command_forbidden"}
