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
