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

    def log_message(self, _format: str, *_args) -> None:  # noqa: N802
        return

    def do_GET(self) -> None:  # noqa: N802
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
        handler = type("Handler", (_SyntheticIngressHandler,), {"routes": routes})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

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


def test_staging_ingress_smoke_defaults_to_dry_run_without_network() -> None:
    result = _run_smoke("--base-url", "https://staging.example.invalid")

    assert result.returncode == 0
    evidence = _parse_evidence(result.stdout)
    assert evidence["mode"] == "dry_run"
    assert evidence["networkCallsEnabled"] is False
    assert evidence["baseUrls"][0]["displayUrl"] == "https://staging.example.invalid"
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
