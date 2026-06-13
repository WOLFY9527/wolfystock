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
        "evidenceMode": "target-environment-https-ingress",
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
        "reverseProxyTlsSummary": {
            "status": "accepted",
            "summary": "HTTPS reverse proxy terminated TLS for the public ingress using sanitized target-environment evidence.",
            "httpsObserved": True,
        },
        "publicPortExposureSummary": {
            "status": "accepted",
            "summary": "Public ingress exposed only ports 80 and 443.",
            "publicPorts": [80, 443],
            "onlyPublicPorts80And443": True,
        },
        "backendExposureSummary": {
            "status": "accepted",
            "summary": "Backend API port 8000 was reachable only through the private reverse-proxy path.",
            "backendPort8000Public": False,
        },
        "httpToHttpsRedirectSummary": {
            "status": "accepted",
            "summary": "HTTP public ingress redirected to HTTPS without exposing backend internals.",
            "redirectsToHttps": True,
        },
        "healthEndpointSummary": {
            "status": "accepted",
            "summary": "The /api/health endpoint returned bounded health metadata through HTTPS ingress.",
        },
        "readinessEndpointSummary": {
            "status": "accepted",
            "summary": "The /api/health/ready endpoint returned bounded readiness metadata through HTTPS ingress.",
        },
        "liveEndpointSummary": {
            "status": "accepted",
            "summary": "The /api/health/live endpoint returned bounded liveness metadata through HTTPS ingress.",
        },
        "adminFailClosedSummary": {
            "status": "accepted",
            "summary": "Protected admin sample returned 401 or 403 for unauthenticated access.",
            "unauthenticatedStatusClass": "401-or-403",
        },
        "sensitivePayloadRedaction": {
            "status": "accepted",
            "summary": "Operator artifact contains only bounded reason-code summaries and sanitized labels.",
            "rawBodiesIncluded": False,
            "debugPayloadsIncluded": False,
            "credentialsIncluded": False,
        },
        "syntheticDataPosture": {
            "status": "accepted",
            "summary": "Ingress smoke used synthetic users and sanitized data labels only.",
            "syntheticUsersOnly": True,
            "customerDataUsed": False,
        },
        "ownerIsolationSummary": {
            "status": "accepted",
            "summary": "Owner isolation posture was summarized with labels only.",
            "ownerIsolationChecked": True,
            "crossOwnerAccessBlocked": True,
        },
        "rollbackNote": {
            "status": "accepted",
            "summary": "Rollback owner and ingress rollback reference were recorded with sanitized labels.",
        },
        "manualReview": {
            "state": "ready-for-manual-review",
            "reviewRequired": True,
            "reviewTicketRef": "staging-ingress-review-ticket",
        },
        "releaseApproved": False,
        "publicLaunchReady": False,
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


def test_accepted_outcome_requires_target_environment_https_evidence_not_local_dry_run(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path,
        _artifact(
            evidenceMode="local-dry-run-preflight",
            networkCallsEnabled=False,
            reverseProxyTlsSummary={"summary": "Local dry-run placeholder only.", "httpsObserved": False},
            publicPortExposureSummary={"summary": "Not checked.", "publicPorts": [], "onlyPublicPorts80And443": False},
            backendExposureSummary={"summary": "Not checked.", "backendPort8000Public": True},
            httpToHttpsRedirectSummary={"summary": "Not checked.", "redirectsToHttps": False},
            syntheticDataPosture={"summary": "Not checked.", "syntheticUsersOnly": False, "customerDataUsed": True},
            manualReview={"state": "draft", "reviewRequired": False, "reviewTicketRef": "review-ticket-label"},
        ),
    )

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert {
        "accepted_outcome_requires_target_environment_https_ingress",
        "accepted_outcome_requires_network_calls_enabled",
        "accepted_outcome_requires_https_reverse_proxy",
        "accepted_outcome_requires_public_ports_80_443_only",
        "accepted_outcome_requires_backend_8000_not_public",
        "accepted_outcome_requires_http_to_https_redirect",
        "accepted_outcome_requires_synthetic_user_data_posture",
        "accepted_outcome_requires_manual_review_ready",
    }.issubset(reason_codes)


def test_release_or_public_launch_approval_flags_are_rejected(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _artifact(releaseApproved=True, publicLaunchReady=True))

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert {"release_approved_flag_forbidden", "public_launch_ready_flag_forbidden"}.issubset(reason_codes)


def test_raw_urls_ips_and_private_hostnames_are_rejected_without_echoing_values(tmp_path: Path) -> None:
    raw_url = "https://staging.example.invalid/api/health"
    private_host = "internal-api.private.local"
    ip_address = "10.10.0.5"
    path = _write_json(
        tmp_path,
        _artifact(
            notes=f"Raw probe URL {raw_url} from {private_host} at {ip_address}",
            rollbackNote={"summary": f"Rollback reference should not include {private_host}"},
        ),
    )

    result = _run_validator(path)

    assert result.returncode == 1
    assert raw_url not in result.stdout
    assert private_host not in result.stdout
    assert ip_address not in result.stdout
    payload = _stdout_json(result)
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert {"raw_url_forbidden", "private_host_or_ip_forbidden"}.issubset(reason_codes)


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
