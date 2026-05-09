from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import scripts.local_soak_performance_smoke as smoke


LOCAL_ROUTES = {
    ("GET", "/api/health"),
    ("GET", "/api/v1/auth/status"),
    ("GET", "/api/v1/market-overview/indices"),
    ("GET", "/api/v1/market-overview/volatility"),
    ("GET", "/api/v1/market-overview/macro"),
    ("GET", "/api/v1/market-overview/sentiment"),
    ("GET", "/api/v1/scanner/themes"),
    ("GET", "/api/v1/admin/logs/storage/summary"),
    ("GET", "/api/v1/admin/cost/duplicate-summary"),
    ("GET", "/api/v1/admin/providers/circuits"),
    ("GET", "/api/v1/admin/market-providers/operations"),
}


def _route(summary: dict, route_id: str) -> dict:
    for item in summary["routes"]:
        if item["id"] == route_id:
            return item
    raise AssertionError(f"route not checked: {route_id}")


def test_default_run_uses_route_inventory_without_network(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_get(_base_url: str, path: str, _timeout: float):
        calls.append(path)
        raise AssertionError("default smoke must not execute HTTP probes")

    monkeypatch.setattr(smoke, "load_route_inventory", lambda: set(LOCAL_ROUTES))
    monkeypatch.setattr(smoke, "safe_http_get", _fake_get)

    summary = smoke.run_smoke()

    assert calls == []
    assert summary["smokeStatus"] == "manual-review-required"
    assert summary["networkCallsExecuted"] is False
    assert summary["authAttempted"] is False
    assert summary["authSucceeded"] is False
    assert summary["authReasonCode"] == "not_requested"
    assert summary["destructiveWritesExecuted"] is False
    assert _route(summary, "public_health")["classification"] == "manual-review-required"
    assert _route(summary, "public_health")["statusCode"] is None
    assert _route(summary, "public_health")["networkCallsExecuted"] is False
    assert _route(summary, "public_health")["destructiveWritesExecuted"] is False
    assert isinstance(_route(summary, "public_health")["elapsed_ms"], float)


def test_http_classification_keeps_auth_manual_and_slow_warning() -> None:
    assert smoke.classify_http_probe(smoke.HttpProbeResult(status_code=200, reason_code="ok"), elapsed_ms=42.0) == (
        "pass",
        False,
        "ok",
    )
    assert smoke.classify_http_probe(smoke.HttpProbeResult(status_code=200, reason_code="ok"), elapsed_ms=1500.0) == (
        "warn",
        False,
        "slow_response",
    )
    assert smoke.classify_http_probe(
        smoke.HttpProbeResult(status_code=401, reason_code="unauthorized"), elapsed_ms=12.0
    ) == ("manual-review-required", True, "auth_required")
    assert smoke.classify_http_probe(smoke.HttpProbeResult(status_code=404, reason_code="not_found"), elapsed_ms=12.0) == (
        "fail",
        False,
        "route_missing",
    )


def test_network_opt_in_records_status_and_elapsed(monkeypatch) -> None:
    responses = {
        "/api/health": smoke.HttpProbeResult(status_code=200, reason_code="ok"),
        "/api/v1/auth/status": smoke.HttpProbeResult(status_code=200, reason_code="ok"),
        "/api/v1/market-overview/indices": smoke.HttpProbeResult(status_code=503, reason_code="dependency_unavailable"),
    }

    def _fake_get(_base_url: str, path: str, _timeout: float) -> smoke.HttpProbeResult:
        return responses.get(path, smoke.HttpProbeResult(status_code=200, reason_code="ok"))

    monkeypatch.setattr(smoke, "load_route_inventory", lambda: set(LOCAL_ROUTES))
    monkeypatch.setattr(smoke, "safe_http_get", _fake_get)

    summary = smoke.run_smoke(base_url="http://127.0.0.1:8000", allow_network=True)

    assert summary["networkCallsExecuted"] is True
    assert _route(summary, "public_health")["statusCode"] == 200
    assert _route(summary, "public_health")["classification"] == "pass"
    assert _route(summary, "market_overview_indices")["statusCode"] == 503
    assert _route(summary, "market_overview_indices")["classification"] == "fail"
    assert _route(summary, "market_overview_indices")["reasonCode"] == "dependency_unavailable"


def test_main_writes_json_output(monkeypatch, tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "perf-smoke.json"
    monkeypatch.setattr(smoke, "load_route_inventory", lambda: set(LOCAL_ROUTES))

    exit_code = smoke.main(["--json-output", str(output_path)])

    assert exit_code == 0
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert set(stdout_payload) >= {
        "smokeStatus",
        "routes",
        "networkCallsExecuted",
        "destructiveWritesExecuted",
        "manualReviewRequired",
    }


def test_script_help_runs_when_executed_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/local_soak_performance_smoke.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--allow-network" in result.stdout


def test_authenticated_mode_missing_env_reports_auth_env_required_without_probes(monkeypatch) -> None:
    monkeypatch.delenv("WOLFYSTOCK_TEST_USERNAME", raising=False)
    monkeypatch.delenv("WOLFYSTOCK_TEST_PASSWORD", raising=False)
    monkeypatch.setattr(smoke, "load_route_inventory", lambda: set(LOCAL_ROUTES))

    def _unexpected_login(*_args, **_kwargs):
        raise AssertionError("login must not run when auth env is missing")

    def _unexpected_get(*_args, **_kwargs):
        raise AssertionError("protected probes must not run when auth env is missing")

    monkeypatch.setattr(smoke, "safe_auth_login", _unexpected_login)
    monkeypatch.setattr(smoke, "safe_session_get", _unexpected_get)

    summary = smoke.run_smoke(
        base_url="http://127.0.0.1:8000",
        allow_network=True,
        authenticated=True,
    )

    assert summary["smokeStatus"] == "fail"
    assert summary["authAttempted"] is True
    assert summary["authSucceeded"] is False
    assert summary["authReasonCode"] == "AUTH_ENV_REQUIRED"
    assert summary["networkCallsExecuted"] is False
    assert summary["safety"]["authenticatedUnsafePostExecuted"] is False
    assert all(route["networkCallsExecuted"] is False for route in summary["routes"])


def test_authenticated_login_success_reuses_session_for_protected_gets(monkeypatch) -> None:
    monkeypatch.setenv("WOLFYSTOCK_TEST_USERNAME", "admin")
    monkeypatch.setenv("WOLFYSTOCK_TEST_PASSWORD", "super-secret")
    monkeypatch.setattr(smoke, "load_route_inventory", lambda: set(LOCAL_ROUTES))
    session = object()
    calls: list[tuple[object, str]] = []

    def _fake_login(*, base_url: str, username: str, password: str, timeout: float) -> smoke.AuthLoginResult:
        assert base_url == "http://127.0.0.1:8000"
        assert username == "admin"
        assert password == "super-secret"
        assert timeout == smoke.DEFAULT_TIMEOUT_SECONDS
        return smoke.AuthLoginResult(
            status_code=200,
            reason_code="ok",
            succeeded=True,
            session=session,
            username_label="admin",
            role="admin",
        )

    def _fake_get(session_arg: object, _base_url: str, path: str, _timeout: float) -> smoke.HttpProbeResult:
        calls.append((session_arg, path))
        return smoke.HttpProbeResult(status_code=200, reason_code="ok")

    monkeypatch.setattr(smoke, "safe_auth_login", _fake_login)
    monkeypatch.setattr(smoke, "safe_session_get", _fake_get)

    summary = smoke.run_smoke(
        base_url="http://127.0.0.1:8000",
        allow_network=True,
        authenticated=True,
    )

    assert summary["authAttempted"] is True
    assert summary["authSucceeded"] is True
    assert summary["authReasonCode"] == "ok"
    assert summary["usernameLabel"] == "admin"
    assert summary["role"] == "admin"
    assert summary["safety"]["authenticatedUnsafePostExecuted"] == "login_only"
    assert summary["businessMutationsExecuted"] is False
    assert summary["notificationsSent"] is False
    assert {path for _, path in calls} == {route.path for route in smoke.AUTHENTICATED_ROUTES}
    assert {session_arg for session_arg, _ in calls} == {session}
    assert _route(summary, "admin_logs_storage_summary")["classification"] == "pass"


def test_authenticated_password_never_appears_in_output(monkeypatch) -> None:
    password = "literal-password-must-not-leak"
    monkeypatch.setenv("WOLFYSTOCK_TEST_USERNAME", "admin@example.com")
    monkeypatch.setenv("WOLFYSTOCK_TEST_PASSWORD", password)
    monkeypatch.setattr(smoke, "load_route_inventory", lambda: set(LOCAL_ROUTES))
    monkeypatch.setattr(
        smoke,
        "safe_auth_login",
        lambda **_kwargs: smoke.AuthLoginResult(
            status_code=200,
            reason_code="ok",
            succeeded=True,
            session=object(),
            username_label="redacted",
            role="admin",
        ),
    )
    monkeypatch.setattr(
        smoke,
        "safe_session_get",
        lambda *_args, **_kwargs: smoke.HttpProbeResult(status_code=200, reason_code="ok"),
    )

    summary = smoke.run_smoke(
        base_url="http://127.0.0.1:8000",
        allow_network=True,
        authenticated=True,
    )

    assert password not in json.dumps(summary, ensure_ascii=False)
    assert summary["usernameLabel"] == "redacted"


def test_authenticated_login_failure_does_not_run_protected_gets(monkeypatch) -> None:
    monkeypatch.setenv("WOLFYSTOCK_TEST_USERNAME", "admin")
    monkeypatch.setenv("WOLFYSTOCK_TEST_PASSWORD", "wrong-password")
    monkeypatch.setattr(smoke, "load_route_inventory", lambda: set(LOCAL_ROUTES))

    monkeypatch.setattr(
        smoke,
        "safe_auth_login",
        lambda **_kwargs: smoke.AuthLoginResult(
            status_code=401,
            reason_code="invalid_login",
            succeeded=False,
            session=None,
            username_label="admin",
            role=None,
        ),
    )

    def _unexpected_get(*_args, **_kwargs):
        raise AssertionError("protected probes must not run after failed login")

    monkeypatch.setattr(smoke, "safe_session_get", _unexpected_get)

    summary = smoke.run_smoke(
        base_url="http://127.0.0.1:8000",
        allow_network=True,
        authenticated=True,
    )

    assert summary["smokeStatus"] == "fail"
    assert summary["authAttempted"] is True
    assert summary["authSucceeded"] is False
    assert summary["authReasonCode"] == "invalid_login"
    assert summary["networkCallsExecuted"] is False
    assert all(route["reasonCode"] == "auth_failed" for route in summary["routes"])


def test_authenticated_route_set_rejects_unsafe_non_login_methods(monkeypatch) -> None:
    monkeypatch.setenv("WOLFYSTOCK_TEST_USERNAME", "admin")
    monkeypatch.setenv("WOLFYSTOCK_TEST_PASSWORD", "secret")
    monkeypatch.setattr(
        smoke,
        "AUTHENTICATED_ROUTES",
        (
            smoke.RouteProbe("bad_post", "POST", "/api/v1/bad", "Bad POST"),
        ),
    )

    try:
        smoke.run_smoke(
            base_url="http://127.0.0.1:8000",
            allow_network=True,
            authenticated=True,
        )
    except ValueError as exc:
        assert str(exc) == "unsafe_authenticated_route_method"
    else:
        raise AssertionError("authenticated route set must reject non-GET probes")


def test_authenticated_output_does_not_capture_raw_response_bodies(monkeypatch) -> None:
    monkeypatch.setenv("WOLFYSTOCK_TEST_USERNAME", "admin")
    monkeypatch.setenv("WOLFYSTOCK_TEST_PASSWORD", "secret")
    monkeypatch.setattr(smoke, "load_route_inventory", lambda: set(LOCAL_ROUTES))
    monkeypatch.setattr(
        smoke,
        "safe_auth_login",
        lambda **_kwargs: smoke.AuthLoginResult(
            status_code=200,
            reason_code="ok",
            succeeded=True,
            session=object(),
            username_label="admin",
            role="admin",
        ),
    )
    monkeypatch.setattr(
        smoke,
        "safe_session_get",
        lambda *_args, **_kwargs: smoke.HttpProbeResult(status_code=200, reason_code="ok"),
    )

    summary = smoke.run_smoke(
        base_url="http://127.0.0.1:8000",
        allow_network=True,
        authenticated=True,
    )
    serialized = json.dumps(summary, ensure_ascii=False).lower()

    assert "rawresponsebody" not in serialized
    assert "responsebody" not in serialized
    assert '"body"' not in serialized
    assert summary["rawResponseBodiesCaptured"] is False
    assert summary["safety"]["rawResponseBodiesCaptured"] is False
