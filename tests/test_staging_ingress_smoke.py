from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "staging_ingress_smoke.py"


class _SyntheticIngressHandler(BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, dict | str, float]] = {}
    request_count = 0

    def log_message(self, _format: str, *_args) -> None:  # noqa: N802
        return

    def do_GET(self) -> None:  # noqa: N802
        self.__class__.request_count += 1
        status, body, delay = self.routes.get(
            self.path,
            (404, {"error": "not_found"}, 0.0),
        )
        if delay:
            time.sleep(delay)
        payload = body if isinstance(body, str) else json.dumps(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload.encode("utf-8"))


class _Server:
    def __init__(self, routes: dict[str, tuple[int, dict | str, float]]) -> None:
        handler = type("Handler", (_SyntheticIngressHandler,), {"routes": routes, "request_count": 0})
        self.handler = handler
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    @property
    def request_count(self) -> int:
        return int(self.handler.request_count)

    def __enter__(self) -> "_Server":
        self.thread.start()
        return self

    def __exit__(self, *_exc_info) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


def _run_smoke(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    command = ["python3", str(SCRIPT), *args]
    merged_env = {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        **(env or {}),
    }
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        env=merged_env,
        check=False,
    )


def _parse_evidence(stdout: str) -> dict:
    return json.loads(stdout)


def _operator_evidence_payload() -> dict:
    return {
        "schemaVersion": "wolfystock_staging_ingress_operator_evidence_v1",
        "mode": "operator_sanitized",
        "evidenceMode": "target-environment-https-ingress",
        "timestamp": "2026-05-08T03:04:05+00:00",
        "baseUrlHostLabel": "staging-ingress.example.com",
        "networkCallsEnabled": True,
        "liveOptInRecorded": True,
        "timeoutSeconds": 5,
        "httpsIngress": {
            "reverseProxyTlsObserved": True,
            "publicPorts": [80, 443],
            "onlyPublicPorts80And443": True,
            "backendPort8000Public": False,
            "httpRedirectsToHttps": True,
        },
        "syntheticDataPosture": {
            "syntheticUsersOnly": True,
            "customerDataUsed": False,
        },
        "manualReview": {
            "state": "ready-for-manual-review",
            "reviewRequired": True,
        },
        "releaseApproved": False,
        "publicLaunchReady": False,
        "resultSummary": {
            "health_ready": {"status": "pass", "statusCode": 200, "reasonCode": "ok"},
            "health_alias": {"status": "pass", "statusCode": 200, "reasonCode": "ok"},
            "health_live": {"status": "pass", "statusCode": 200, "reasonCode": "ok"},
            "admin_fail_closed": {
                "status": "pass",
                "statusCode": 401,
                "reasonCode": "unauthenticated_fail_closed",
            },
        },
        "reasonCodes": ["ok", "unauthenticated_fail_closed"],
        "sanitization": {
            "rawResponseBodiesIncluded": False,
            "tokensIncluded": False,
            "cookiesIncluded": False,
            "secretsIncluded": False,
            "dsnsIncluded": False,
            "apiKeysIncluded": False,
            "providerPayloadsIncluded": False,
            "debugTracesIncluded": False,
            "credentialBearingUrlsIncluded": False,
        },
    }


def test_staging_ingress_smoke_defaults_to_dry_run_without_network() -> None:
    with _Server({"/api/health": (500, {"status": "should_not_be_called"}, 0.0)}) as server:
        result = _run_smoke("--base-url", server.base_url)
        request_count = server.request_count

    assert result.returncode == 0
    evidence = _parse_evidence(result.stdout)
    assert evidence["mode"] == "dry_run"
    assert evidence["networkCallsEnabled"] is False
    assert request_count == 0
    assert evidence["baseUrls"][0]["displayUrl"] == server.base_url
    assert {scenario["status"] for scenario in evidence["scenarios"]} == {"skipped"}
    assert "WOLFYSTOCK_STAGING_INGRESS_SMOKE=1" in evidence["nextStep"]


def test_staging_ingress_smoke_live_mode_checks_health_admin_and_redaction() -> None:
    routes = {
        "/api/health": (200, {"status": "ok", "ready": True}, 0.0),
        "/api/health/ready": (200, {"status": "ok", "ready": True}, 0.0),
        "/api/health/live": (200, {"status": "ok", "ready": True}, 0.0),
        "/api/v1/admin/users": (401, {"error": "not_authenticated"}, 0.0),
    }
    with _Server(routes) as server:
        result = _run_smoke(
            "--base-url",
            server.base_url,
            env={"WOLFYSTOCK_STAGING_INGRESS_SMOKE": "1"},
        )

    assert result.returncode == 0
    evidence = _parse_evidence(result.stdout)
    assert evidence["mode"] == "live"
    assert evidence["networkCallsEnabled"] is True
    assert {scenario["name"]: scenario["status"] for scenario in evidence["scenarios"]} == {
        "health_ready": "pass",
        "health_alias": "pass",
        "health_live": "pass",
        "admin_fail_closed": "pass",
    }
    assert "not_authenticated" not in result.stdout


def test_staging_ingress_smoke_fails_on_secret_or_debug_payload_without_leaking_value() -> None:
    leaked_key = "sk-" + ("A" * 40)
    routes = {
        "/api/health": (200, {"status": "ok", "debug_payload": leaked_key}, 0.0),
        "/api/health/ready": (200, {"status": "ok", "ready": True}, 0.0),
        "/api/health/live": (200, {"status": "ok", "ready": True}, 0.0),
        "/api/v1/admin/users": (401, {"error": "not_authenticated"}, 0.0),
    }
    with _Server(routes) as server:
        result = _run_smoke(
            "--base-url",
            server.base_url,
            env={"WOLFYSTOCK_STAGING_INGRESS_SMOKE": "1"},
        )

    assert result.returncode == 1
    assert leaked_key not in result.stdout
    assert leaked_key not in result.stderr
    evidence = _parse_evidence(result.stdout)
    failed = [scenario for scenario in evidence["scenarios"] if scenario["status"] == "fail"]
    assert failed
    assert failed[0]["reasonCode"] == "sensitive_payload_pattern"


def test_staging_ingress_smoke_timeout_output_is_actionable_and_sanitized() -> None:
    leaked_query = "sk-" + ("B" * 40)
    routes = {
        "/api/health": (200, {"status": "ok", "ready": True}, 1.0),
        "/api/health/ready": (200, {"status": "ok", "ready": True}, 0.0),
        "/api/health/live": (200, {"status": "ok", "ready": True}, 0.0),
        "/api/v1/admin/users": (401, {"error": "not_authenticated"}, 0.0),
    }
    with _Server(routes) as server:
        result = _run_smoke(
            "--base-url",
            f"{server.base_url}?token={leaked_query}",
            "--timeout",
            "0.1",
            env={"WOLFYSTOCK_STAGING_INGRESS_SMOKE": "1"},
        )

    assert result.returncode == 1
    assert leaked_query not in result.stdout
    assert leaked_query not in result.stderr
    evidence = _parse_evidence(result.stdout)
    timeout = next(scenario for scenario in evidence["scenarios"] if scenario["name"] == "health_alias")
    assert timeout["status"] == "fail"
    assert timeout["reasonCode"] == "request_timeout"
    assert timeout["action"] == "Check ingress routing, upstream health, and timeout budget."
    assert timeout["url"].endswith("/api/health")


def test_staging_ingress_operator_evidence_accepts_sanitized_artifact(tmp_path: Path) -> None:
    evidence_path = tmp_path / "staging-ingress-operator-evidence.json"
    evidence_path.write_text(json.dumps(_operator_evidence_payload()), encoding="utf-8")

    result = _run_smoke(
        "--operator-evidence",
        str(evidence_path),
        env={"WOLFYSTOCK_STAGING_INGRESS_SMOKE": "1"},
    )

    assert result.returncode == 0
    evidence = _parse_evidence(result.stdout)
    assert evidence["mode"] == "operator_evidence"
    assert evidence["networkCallsEnabled"] is False
    assert evidence["checkerNetworkCallsEnabled"] is False
    assert evidence["operatorEvidence"]["networkCallsEnabled"] is True
    assert evidence["operatorEvidence"]["liveOptInRecorded"] is True
    assert evidence["operatorEvidence"]["baseUrlHostLabel"] == "staging-ingress.example.com"
    assert evidence["verdict"] == "pass"
    assert {check["id"]: check["status"] for check in evidence["checks"]} == {
        "operator_evidence_contains_no_unsafe_values": "pass",
        "operator_evidence_has_host_label_only": "pass",
        "operator_evidence_records_real_smoke_opt_in": "pass",
        "operator_evidence_has_timestamp": "pass",
        "operator_evidence_has_bounded_timeout": "pass",
        "operator_evidence_has_required_result_summary": "pass",
        "operator_evidence_records_admin_fail_closed": "pass",
        "operator_evidence_has_sanitized_reason_codes": "pass",
        "operator_evidence_declares_required_sanitization": "pass",
        "operator_evidence_records_target_https_ingress": "pass",
        "operator_evidence_preserves_launch_no_go": "pass",
    }


def test_staging_ingress_operator_evidence_rejects_raw_bodies_and_secret_values(tmp_path: Path) -> None:
    leaked_token = "sk-" + ("C" * 40)
    payload = _operator_evidence_payload()
    payload["rawResponseBody"] = {"token": leaked_token}
    payload["providerPayload"] = {"quote": {"symbol": "AAPL"}}
    payload["debugTrace"] = "Traceback (most recent call last): token=" + leaked_token
    payload["adminFailClosedRawBody"] = "{\"error\":\"not_authenticated\"}"
    payload["sanitization"]["rawResponseBodiesIncluded"] = True
    evidence_path = tmp_path / "unsafe-staging-ingress-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_smoke("--operator-evidence", str(evidence_path))

    assert result.returncode == 1
    assert leaked_token not in result.stdout
    assert leaked_token not in result.stderr
    evidence = _parse_evidence(result.stdout)
    unsafe_check = next(
        check for check in evidence["checks"] if check["id"] == "operator_evidence_contains_no_unsafe_values"
    )
    sanitization_check = next(
        check for check in evidence["checks"] if check["id"] == "operator_evidence_declares_required_sanitization"
    )
    reason_codes = {finding["reasonCode"] for finding in unsafe_check["evidence"]["findings"]}
    assert unsafe_check["status"] == "fail"
    assert sanitization_check["status"] == "fail"
    assert "sensitive_key_contains_value" in reason_codes


def test_staging_ingress_operator_evidence_rejects_credential_urls_and_raw_host_urls(tmp_path: Path) -> None:
    leaked_token = "sk-" + ("D" * 40)
    payload = _operator_evidence_payload()
    payload["baseUrlHostLabel"] = "https://staging.example.com"
    payload["probeUrl"] = f"https://staging.example.com/api/health?token={leaked_token}"
    evidence_path = tmp_path / "credential-url-staging-ingress-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_smoke("--operator-evidence", str(evidence_path))

    assert result.returncode == 1
    assert leaked_token not in result.stdout
    assert leaked_token not in result.stderr
    evidence = _parse_evidence(result.stdout)
    assert evidence["operatorEvidence"]["baseUrlHostLabel"] == "<invalid>"
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["operator_evidence_has_host_label_only"]["status"] == "fail"
    reason_codes = {
        finding["reasonCode"]
        for finding in checks["operator_evidence_contains_no_unsafe_values"]["evidence"]["findings"]
    }
    assert "credential_bearing_url" in reason_codes


def test_staging_ingress_operator_evidence_requires_admin_fail_closed(tmp_path: Path) -> None:
    payload = _operator_evidence_payload()
    payload["resultSummary"]["admin_fail_closed"] = {
        "status": "fail",
        "statusCode": 200,
        "reasonCode": "admin_route_open",
    }
    evidence_path = tmp_path / "open-admin-staging-ingress-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_smoke("--operator-evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _parse_evidence(result.stdout)
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["operator_evidence_records_admin_fail_closed"]["status"] == "fail"


def test_staging_ingress_operator_evidence_rejects_local_dry_run_and_launch_flags(tmp_path: Path) -> None:
    payload = _operator_evidence_payload()
    payload["evidenceMode"] = "local-dry-run-preflight"
    payload["networkCallsEnabled"] = False
    payload["liveOptInRecorded"] = False
    payload["releaseApproved"] = True
    payload["publicLaunchReady"] = True
    payload["httpsIngress"]["reverseProxyTlsObserved"] = False
    payload["httpsIngress"]["publicPorts"] = [8000]
    payload["httpsIngress"]["onlyPublicPorts80And443"] = False
    payload["httpsIngress"]["backendPort8000Public"] = True
    payload["httpsIngress"]["httpRedirectsToHttps"] = False
    payload["syntheticDataPosture"]["syntheticUsersOnly"] = False
    payload["manualReview"]["state"] = "draft"
    payload["manualReview"]["reviewRequired"] = False
    evidence_path = tmp_path / "local-dry-run-staging-ingress-evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_smoke("--operator-evidence", str(evidence_path))

    assert result.returncode == 1
    evidence = _parse_evidence(result.stdout)
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["operator_evidence_records_real_smoke_opt_in"]["status"] == "fail"
    assert checks["operator_evidence_records_target_https_ingress"]["status"] == "fail"
    assert checks["operator_evidence_preserves_launch_no_go"]["status"] == "fail"
