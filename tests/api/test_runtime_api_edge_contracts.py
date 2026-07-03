# -*- coding: utf-8 -*-
"""Runtime API edge hardening smoke tests for consumer routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import CurrentUser, get_current_user, get_database_manager, get_optional_current_user


FORBIDDEN_CONSUMER_MARKERS = (
    "<html",
    "<!doctype html",
    "traceback",
    "provider error",
    "provider_error",
    "debug",
    "dry-run",
    "pipeline",
    "universe",
    "historical ohlcv",
    "historical_ohlcv",
    "quote snapshot",
    "quote_snapshot",
    "runtimeerror",
    "raw exception",
    "token",
    "api_key",
    "secret",
)


def _user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="session-1",
        admin_capabilities=("scanner:admin:read", "ops:providers:read"),
    )


def _panel(name: str) -> dict[str, Any]:
    return {
        "panel_name": name,
        "last_refresh_at": "2026-07-03T00:00:00Z",
        "updated_at": "2026-07-03T00:00:00Z",
        "status": "unavailable",
        "freshness": "unavailable",
        "warning": "数据不足，暂不形成结论。",
        "items": [],
        "noAdviceDisclosure": "Observation-only market research; not investment advice.",
    }


class _MarketOverviewService:
    def get_indices(self, *, actor=None) -> dict[str, Any]:
        return _panel("Indices")

    def get_volatility(self, *, actor=None) -> dict[str, Any]:
        return _panel("Volatility")

    def get_sentiment(self, *, actor=None) -> dict[str, Any]:
        return _panel("Sentiment")

    def get_funds_flow(self, *, actor=None) -> dict[str, Any]:
        return _panel("FundsFlow")

    def get_macro(self, *, actor=None) -> dict[str, Any]:
        return _panel("Macro")


class _ScannerOpsService:
    def get_operational_status(self, **_: Any) -> dict[str, Any]:
        return {
            "market": "us",
            "profile": "us_preopen_v1",
            "profile_label": "US Pre-open",
            "watchlist_date": "2026-07-03",
            "today_trading_day": True,
            "schedule_enabled": False,
            "schedule_time": None,
            "schedule_run_immediately": False,
            "notification_enabled": False,
            "quality_summary": {"available": False},
            "dataReadiness": {
                "state": "blocked",
                "consumerSafeMessage": "Scanner evidence is unavailable; candidates are not generated.",
                "blockingModules": ["scanner"],
                "freshness": "unavailable",
            },
        }


class _ScannerService:
    def list_runs(self, **_: Any) -> dict[str, Any]:
        return {"total": 0, "page": 1, "limit": 10, "items": []}


class _WatchlistService:
    def list_items(self, *, owner_id: str) -> list[dict[str, Any]]:
        return []


class _BacktestService:
    def get_sample_status(self, *, code: str | None) -> dict[str, Any]:
        return {
            "code": code or "ALL",
            "scope": "aggregate" if code is None else "single",
            "prepared_count": 0,
            "eval_window_days": 10,
            "min_age_days": 0,
            "sample_readiness_state": "data_unavailable",
            "sample_blocking_reasons": ["local_samples_missing"],
            "execution_readiness": {
                "status": "blocked",
                "reason": "local_samples_missing",
                "consumerSafeMessage": "Backtest samples are unavailable.",
                "blockingModules": ["backtest"],
            },
            "probePolicy": {"liveProviderProbes": False},
            "writePolicy": {"cacheWrites": False},
        }


class _FailingBacktestService:
    def get_sample_status(self, *, code: str | None) -> dict[str, Any]:
        raise RuntimeError(
            "Traceback RuntimeError provider error debug dry-run pipeline universe "
            "historical ohlcv quote snapshot token marker api_key marker"
        )


def _research_radar_payload() -> dict[str, Any]:
    def hub_item(key: str, label: str, status: str) -> dict[str, Any]:
        return {
            "key": key,
            "label": label,
            "status": status,
            "summary": f"{label} readiness is {status}.",
            "blocker": None if status == "available" else f"{label} evidence is unavailable.",
            "nextDataAction": "Review local evidence readiness.",
            "evidenceCount": 0,
            "totalCount": 1,
            "symbols": [],
            "details": [],
            "observationOnly": True,
            "decisionGrade": False,
        }

    return {
        "schemaVersion": "research_radar_api_v1",
        "generatedAt": "2026-07-03T00:00:00Z",
        "researchQueue": [],
        "aggregateSummary": {
            "candidateCount": 0,
            "queueCount": 0,
            "priorityCounts": {},
            "dominantThemes": [],
            "queueQuality": "empty",
            "duplicateEvidenceMerged": 0,
            "queueDiversity": {},
            "source": {},
        },
        "evidenceGaps": ["Scanner candidates are unavailable."],
        "marketContextFit": "unknown",
        "drilldownTargets": [],
        "consumerIssues": [],
        "onboardingGuidance": None,
        "emptyStateActions": [],
        "starterResearchWorkflow": [],
        "firstRunChecklist": [],
        "suggestedResearchEntrypoints": [],
        "noAdviceDisclosure": "Research-only queue; not investment advice.",
        "dataQuality": {
            "status": "blocked",
            "availableCandidateCount": 0,
            "reliableCandidateCount": 0,
            "missingEvidence": ["Scanner candidates are unavailable."],
            "missingEvidenceRaw": [],
            "consumerIssues": [],
        },
        "evidenceHub": {
            "scannerCandidates": hub_item("scanner", "Scanner candidates", "blocked"),
            "backtestSamples": hub_item("backtest", "Backtest samples", "blocked"),
            "stockReadiness": hub_item("stock", "Stock readiness", "blocked"),
            "dataActivation": hub_item("data", "Data activation", "blocked"),
            "missingEvidenceStates": [hub_item("scanner", "Scanner candidates", "blocked")],
        },
        "marketLevelFallback": None,
        "observationOnly": True,
        "decisionGrade": False,
    }


class _ResearchRadarService:
    def __init__(self, **_: Any) -> None:
        pass

    def build_from_latest_scanner_run(self, **_: Any) -> dict[str, Any]:
        return _research_radar_payload()


def _assert_json_response(response, *, expected_status: int = 200) -> dict[str, Any]:
    assert response.status_code == expected_status, response.text
    assert response.headers.get("content-type", "").startswith("application/json")
    payload = response.json()
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for marker in FORBIDDEN_CONSUMER_MARKERS:
        assert marker not in serialized
    return payload


@pytest.fixture()
def runtime_edge_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from api.v1.endpoints import backtest, market, market_overview, research, scanner, watchlist
    from tests.api.test_market_decision_cockpit_endpoint import _payload as cockpit_payload

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><html><body>SPA shell</body></html>", encoding="utf-8")

    monkeypatch.setattr(market_overview, "MarketOverviewService", _MarketOverviewService)
    monkeypatch.setattr(market_overview, "_build_market_regime_evidence_projection", lambda: {
        "status": "failed_closed",
        "consumerSafeMessage": "Market regime evidence is unavailable.",
    })
    monkeypatch.setattr(market, "MarketDecisionCockpitService", lambda: type(
        "_CockpitService",
        (),
        {"get_decision_cockpit": lambda self, **_: cockpit_payload()},
    )())
    monkeypatch.setattr(market, "build_market_regime_evidence_pack", lambda **_: {
        "status": "failed_closed",
        "readiness": "failed_closed",
        "consumerSafeMessage": "Market regime evidence is unavailable.",
        "blockingModules": ["market_regime"],
        "asOf": None,
        "freshness": "unavailable",
        "missingDataFamilies": ["local_market_evidence"],
        "blockedProductSurfaces": ["Market Overview", "Research Radar"],
        "noAdviceDisclosure": "Observation-only market structure evidence; not investment advice.",
    })
    monkeypatch.setattr(scanner, "_build_scanner_ops_service", lambda *_: _ScannerOpsService())
    monkeypatch.setattr(scanner, "_build_scanner_service", lambda *_: _ScannerService())
    monkeypatch.setattr(watchlist, "_get_watchlist_service", lambda: _WatchlistService())
    monkeypatch.setattr(research, "ResearchRadarService", _ResearchRadarService)
    monkeypatch.setattr(research, "BacktestService", lambda *_args, **_kwargs: _BacktestService())
    monkeypatch.setattr(research, "build_market_regime_read_model", lambda **_: None)
    monkeypatch.setattr(backtest, "_build_backtest_service", lambda *_: _BacktestService())

    app = create_app(static_dir=static_dir)
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_optional_current_user] = lambda: None
    app.dependency_overrides[get_database_manager] = lambda: object()
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "path, required_keys",
    [
        ("/api/v1/market-overview", {"status", "panels"}),
        ("/api/v1/market/decision-cockpit", {"marketRegimeDecision", "researchQueuePreview"}),
        ("/api/v1/market/regime-evidence-pack", {"status", "consumerSafeMessage", "blockingModules"}),
        ("/api/v1/scanner/status", {"market", "profile", "dataReadiness"}),
        ("/api/v1/scanner/runs", {"total", "items"}),
        ("/api/v1/watchlist/items", {"items"}),
        ("/api/v1/research/radar", {"researchQueue", "evidenceHub", "dataQuality"}),
        ("/api/v1/backtest/sample-status", {"code", "sample_readiness_state", "execution_readiness"}),
    ],
)
def test_consumer_runtime_api_routes_return_json_contracts(
    runtime_edge_client: TestClient,
    path: str,
    required_keys: set[str],
) -> None:
    payload = _assert_json_response(runtime_edge_client.get(path))

    assert required_keys <= set(payload)
    assert payload != {}


def test_unknown_api_route_remains_json_not_found(runtime_edge_client: TestClient) -> None:
    response = runtime_edge_client.get("/api/v1/runtime-edge/does-not-exist")

    payload = _assert_json_response(response, expected_status=404)
    assert payload["error"] in {"not_found", "http_error"}
    assert "not found" in json.dumps(payload, ensure_ascii=False).lower()


def test_backtest_internal_error_suppresses_raw_runtime_detail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.v1.endpoints import backtest

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><html><body>SPA shell</body></html>", encoding="utf-8")
    monkeypatch.setattr(backtest, "_build_backtest_service", lambda *_: _FailingBacktestService())

    app = create_app(static_dir=static_dir)
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_database_manager] = lambda: object()

    with TestClient(app) as client:
        payload = _assert_json_response(client.get("/api/v1/backtest/sample-status"), expected_status=500)

    assert payload["error"] == "internal_error"
    assert payload["reason"] == "internal_error"
    assert payload["consumerSafeMessage"] == "Backtest data is temporarily unavailable. Please retry later."
    assert payload["retryable"] is True
