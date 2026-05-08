from __future__ import annotations

import json
from pathlib import Path

import scripts.staging_integration_smoke as smoke


LOCAL_ROUTES = {
    ("GET", "/api/health"),
    ("GET", "/api/health/live"),
    ("GET", "/api/health/ready"),
    ("GET", "/api/v1/auth/status"),
    ("GET", "/api/v1/auth/me"),
    ("GET", "/api/v1/market-overview/indices"),
    ("GET", "/api/v1/scanner/themes"),
    ("GET", "/api/v1/scanner/runs"),
    ("GET", "/api/v1/agent/status"),
    ("GET", "/api/v1/agent/provider-health"),
    ("GET", "/api/v1/portfolio/accounts"),
    ("GET", "/api/v1/backtest/runs"),
    ("GET", "/api/v1/admin/logs/storage/summary"),
    ("GET", "/api/v1/admin/cost/duplicate-summary"),
    ("GET", "/api/v1/admin/providers/circuits"),
    ("GET", "/api/v1/admin/market-providers/operations"),
}


def _surface(summary: dict, surface_id: str) -> dict:
    for item in summary["checkedSurfaces"]:
        if item["id"] == surface_id:
            return item
    raise AssertionError(f"surface not checked: {surface_id}")


def test_local_mode_route_inventory_is_offline_safe(monkeypatch) -> None:
    monkeypatch.setattr(smoke, "load_route_inventory", lambda: set(LOCAL_ROUTES))
    monkeypatch.setattr(smoke, "is_ai_research_locally_available", lambda: False)

    summary = smoke.run_smoke(mode="local")

    assert summary["smokeStatus"] == "manual_review_required"
    assert summary["networkCallsExecuted"] is False
    assert summary["destructiveWritesExecuted"] is False
    assert _surface(summary, "public_health")["status"] == "pass"
    assert _surface(summary, "auth_session_status")["status"] == "pass"
    assert _surface(summary, "portfolio_accounts")["status"] == "pass"
    assert _surface(summary, "ai_research_provider_health")["status"] == "skipped"
    assert _surface(summary, "ai_research_provider_health")["reasonCode"] == "config_missing"
    assert "ai_research_provider_health" in summary["manualReviewRequired"]
    assert "portfolio_accounts" in summary["authRequiredSurfaces"]


def test_local_mode_distinguishes_missing_routes(monkeypatch) -> None:
    routes = set(LOCAL_ROUTES)
    routes.remove(("GET", "/api/v1/portfolio/accounts"))
    monkeypatch.setattr(smoke, "load_route_inventory", lambda: routes)
    monkeypatch.setattr(smoke, "is_ai_research_locally_available", lambda: True)

    summary = smoke.run_smoke(mode="local")

    assert summary["smokeStatus"] == "fail"
    portfolio = _surface(summary, "portfolio_accounts")
    assert portfolio["status"] == "fail"
    assert portfolio["reasonCode"] == "route_missing"


def test_network_mode_requires_explicit_opt_in(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_get(_base_url: str, path: str, _timeout: float) -> smoke.HttpProbeResult:
        calls.append(path)
        return smoke.HttpProbeResult(status_code=200, reason_code="ok")

    monkeypatch.setattr(smoke, "load_route_inventory", lambda: set(LOCAL_ROUTES))
    monkeypatch.setattr(smoke, "is_ai_research_locally_available", lambda: True)
    monkeypatch.setattr(smoke, "safe_http_get", _fake_get)

    summary = smoke.run_smoke(mode="local", base_url="http://127.0.0.1:8000", allow_network=False)

    assert calls == []
    assert summary["networkCallsExecuted"] is False
    assert all(item.get("networkProbe") is False for item in summary["checkedSurfaces"])


def test_network_mode_classifies_http_outcomes(monkeypatch) -> None:
    responses = {
        "/api/health": smoke.HttpProbeResult(status_code=200, reason_code="ok"),
        "/api/v1/auth/status": smoke.HttpProbeResult(status_code=200, reason_code="ok"),
        "/api/v1/market-overview/indices": smoke.HttpProbeResult(status_code=503, reason_code="dependency_unavailable"),
        "/api/v1/scanner/themes": smoke.HttpProbeResult(status_code=404, reason_code="not_found"),
        "/api/v1/portfolio/accounts": smoke.HttpProbeResult(status_code=401, reason_code="unauthorized"),
    }

    def _fake_get(_base_url: str, path: str, _timeout: float) -> smoke.HttpProbeResult:
        return responses.get(path, smoke.HttpProbeResult(status_code=200, reason_code="ok"))

    monkeypatch.setattr(smoke, "load_route_inventory", lambda: set(LOCAL_ROUTES))
    monkeypatch.setattr(smoke, "is_ai_research_locally_available", lambda: True)
    monkeypatch.setattr(smoke, "safe_http_get", _fake_get)

    summary = smoke.run_smoke(
        mode="local",
        base_url="http://127.0.0.1:8000",
        allow_network=True,
    )

    assert summary["networkCallsExecuted"] is True
    assert _surface(summary, "market_overview_indices")["reasonCode"] == "dependency_unavailable"
    assert _surface(summary, "scanner_themes")["reasonCode"] == "route_missing"
    assert _surface(summary, "portfolio_accounts")["reasonCode"] == "auth_required"


def test_main_writes_bounded_json_output(monkeypatch, tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "staging-smoke.json"
    monkeypatch.setattr(smoke, "load_route_inventory", lambda: set(LOCAL_ROUTES))
    monkeypatch.setattr(smoke, "is_ai_research_locally_available", lambda: True)

    exit_code = smoke.main(["--mode", "local", "--json-output", str(output_path)])

    assert exit_code == 0
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert set(stdout_payload) >= {
        "smokeStatus",
        "checkedSurfaces",
        "skippedSurfaces",
        "networkCallsExecuted",
        "destructiveWritesExecuted",
        "authRequiredSurfaces",
        "manualReviewRequired",
    }
