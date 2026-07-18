# -*- coding: utf-8 -*-
"""API contract tests for the CN provider health endpoint."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import market
from tests.api.route_table_helpers import iter_effective_api_routes
from src.services import cn_provider_health_service as health_service_module


EXPECTED_ENTRY_FIELDS = {
    "providerName",
    "providerId",
    "sourceType",
    "sourceTier",
    "trustLevel",
    "freshnessExpectation",
    "observationOnly",
    "scoreContributionAllowed",
    "dependencyInstalled",
    "providerAvailable",
    "healthStatus",
    "supportedCapabilities",
    "unsupportedCapabilities",
    "contractCapabilities",
    "keyRequired",
    "cacheRequired",
    "backgroundRefreshRecommended",
    "degradationReason",
    "missingProviderReason",
    "attemptedAt",
    "timeoutSeconds",
}
FORBIDDEN_PROVIDER_FIELDS = {
    "quotes",
    "quote",
    "kline",
    "klines",
    "symbols",
    "rawPayload",
    "score",
    "scoreContribution",
}


def _provider_read_admin() -> CurrentUser:
    return CurrentUser(
        user_id="provider-admin",
        username="provider-admin",
        display_name="Provider Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:providers:read",),
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="member-1",
        username="member",
        display_name="Member",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


def _unauthenticated_user() -> CurrentUser:
    raise HTTPException(
        status_code=401,
        detail={"error": "unauthorized", "message": "Login required"},
    )


def _client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pytdx_probe,
    akshare_probe,
    baostock_probe,
) -> TestClient:
    monkeypatch.setattr(
        market,
        "CNProviderHealthService",
        lambda: health_service_module.CNProviderHealthService(
            pytdx_probe=pytdx_probe,
            akshare_probe=akshare_probe,
            baostock_probe=baostock_probe,
        ),
    )
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.dependency_overrides[get_current_user] = _provider_read_admin
    return TestClient(app)


def test_cn_provider_health_route_is_exposed() -> None:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    routes = {
        (method, route.path)
        for route in iter_effective_api_routes(app.routes)
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }

    assert ("GET", "/api/v1/market/cn-provider-health") in routes


def test_cn_provider_health_route_returns_metadata_only_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(
        monkeypatch,
        pytdx_probe=lambda timeout_seconds: {
            "providerName": "pytdx",
            "providerId": "pytdx",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": [
                "cn_history_daily",
                "cn_name_lookup",
                "cn_quote",
                "cn_realtime_quote",
            ],
            "unsupportedCapabilities": ["hk_history_daily", "us_quote"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T02:03:04+00:00",
            "timeoutSeconds": timeout_seconds,
            "serverHealth": "reachable",
            "quotes": {"000001": {"price": 12.34}},
            "symbols": ["000001"],
            "score": {"value": 99},
        },
        akshare_probe=lambda timeout_seconds: {
            "providerName": "AKShare",
            "providerId": "akshare",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": [
                "cn_stock_list",
                "cn_realtime_snapshot",
                "cn_realtime_quote",
                "cn_history_daily",
                "cn_index_quote",
                "cn_market_stats",
                "cn_sector_rankings",
                "cn_etf_realtime_quote",
                "cn_etf_history_daily",
                "hk_realtime_quote",
                "hk_history_daily",
                "chip_distribution",
            ],
            "unsupportedCapabilities": ["hk_index_quote"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T02:03:05+00:00",
            "timeoutSeconds": timeout_seconds,
            "interfaceHealth": "ok",
            "rawPayload": {"market": "CN"},
            "kline": [{"close": 1.0}],
        },
        baostock_probe=lambda timeout_seconds: {
            "providerName": "BaoStock",
            "providerId": "baostock",
            "dependencyInstalled": True,
            "providerAvailable": False,
            "supportedCapabilities": [
                "cn_adjust_factor",
                "cn_basic_financials",
                "cn_history_daily",
                "cn_index_history_daily",
            ],
            "unsupportedCapabilities": ["cn_quote"],
            "degradationReason": "baostock_live_probe_disabled",
            "missingProviderReason": "baostock_live_probe_disabled",
            "attemptedAt": None,
            "timeoutSeconds": timeout_seconds,
            "interfaceHealth": "ready",
            "serverHealth": "probe_disabled",
            "healthStatus": "probe_disabled",
            "quotes": {"sh.000001": {"price": 12.34}},
            "symbols": ["sh.000001"],
        },
    )

    client.app.dependency_overrides[get_current_user] = _unauthenticated_user
    unauthenticated = client.get("/api/v1/market/cn-provider-health")
    assert unauthenticated.status_code == 401

    client.app.dependency_overrides[get_current_user] = _regular_user
    member = client.get("/api/v1/market/cn-provider-health")
    assert member.status_code == 403
    assert member.json()["detail"]["error"] == "admin_required"

    client.app.dependency_overrides[get_current_user] = _provider_read_admin
    response = client.get("/api/v1/market/cn-provider-health")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert [item["providerId"] for item in payload] == ["pytdx", "akshare", "baostock"]
    assert all(set(item) == EXPECTED_ENTRY_FIELDS for item in payload)
    assert all(not FORBIDDEN_PROVIDER_FIELDS.intersection(item) for item in payload)
    assert all(item["observationOnly"] is True for item in payload)
    assert all(item["scoreContributionAllowed"] is False for item in payload)
    assert all(item["keyRequired"] is False for item in payload)
    assert all(item["cacheRequired"] is True for item in payload)
    assert all(item["backgroundRefreshRecommended"] is True for item in payload)
    assert next(item for item in payload if item["providerId"] == "pytdx")["trustLevel"] == "usable_with_caution"
    assert next(item for item in payload if item["providerId"] == "akshare")["trustLevel"] == "weak"
    assert next(item for item in payload if item["providerId"] == "baostock")["trustLevel"] == "usable_with_caution"
    assert next(item for item in payload if item["providerId"] == "pytdx")["healthStatus"] == "healthy"
    assert next(item for item in payload if item["providerId"] == "akshare")["healthStatus"] == "healthy"
    assert next(item for item in payload if item["providerId"] == "baostock")["healthStatus"] == "probe_disabled"


def test_cn_provider_health_route_degrades_cleanly_when_dependency_missing_or_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(
        monkeypatch,
        pytdx_probe=lambda timeout_seconds: (_ for _ in ()).throw(ImportError("pytdx missing")),
        akshare_probe=lambda timeout_seconds: (_ for _ in ()).throw(RuntimeError("upstream page changed")),
        baostock_probe=lambda timeout_seconds: {
            "providerName": "baostock",
            "providerId": "baostock",
            "dependencyInstalled": False,
            "providerAvailable": False,
            "supportedCapabilities": [
                "cn_adjust_factor",
                "cn_basic_financials",
                "cn_history_daily",
                "cn_index_history_daily",
            ],
            "unsupportedCapabilities": ["cn_quote"],
            "degradationReason": "baostock_not_installed",
            "missingProviderReason": "baostock_not_installed",
            "attemptedAt": None,
            "timeoutSeconds": timeout_seconds,
            "serverHealth": "missing_dependency",
            "healthStatus": "missing_dependency",
        },
    )

    response = client.get("/api/v1/market/cn-provider-health")

    assert response.status_code == 200
    payload = {item["providerId"]: item for item in response.json()}

    pytdx = payload["pytdx"]
    assert pytdx["dependencyInstalled"] is False
    assert pytdx["providerAvailable"] is False
    assert pytdx["healthStatus"] == "missing_dependency"
    assert pytdx["missingProviderReason"] == "pytdx_not_installed"
    assert pytdx["observationOnly"] is True
    assert pytdx["scoreContributionAllowed"] is False

    akshare = payload["akshare"]
    assert akshare["dependencyInstalled"] is True
    assert akshare["providerAvailable"] is False
    assert akshare["healthStatus"] == "probe_failure"
    assert akshare["degradationReason"] == "akshare_probe_failed"
    assert akshare["missingProviderReason"] == "akshare_probe_failed"
    assert akshare["trustLevel"] == "weak"
    assert akshare["observationOnly"] is True
    assert akshare["scoreContributionAllowed"] is False

    baostock = payload["baostock"]
    assert baostock["dependencyInstalled"] is False
    assert baostock["providerAvailable"] is False
    assert baostock["healthStatus"] == "missing_dependency"
    assert baostock["degradationReason"] == "baostock_not_installed"
    assert baostock["missingProviderReason"] == "baostock_not_installed"
    assert baostock["observationOnly"] is True
    assert baostock["scoreContributionAllowed"] is False
    assert baostock["trustLevel"] == "usable_with_caution"


def test_cn_provider_health_route_reuses_cached_snapshot_by_default_and_supports_force_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    health_service_module.CNProviderHealthService.clear_snapshot_cache()
    calls = {"pytdx": 0, "akshare": 0, "baostock": 0}

    def pytdx_probe(timeout_seconds: float) -> dict:
        calls["pytdx"] += 1
        return {
            "providerName": "pytdx",
            "providerId": "pytdx",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": [
                "cn_history_daily",
                "cn_name_lookup",
                "cn_quote",
                "cn_realtime_quote",
            ],
            "unsupportedCapabilities": [],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": f"2026-05-19T02:03:0{calls['pytdx']}+00:00",
            "timeoutSeconds": timeout_seconds,
            "serverHealth": "reachable",
        }

    def akshare_probe(timeout_seconds: float) -> dict:
        calls["akshare"] += 1
        return {
            "providerName": "akshare",
            "providerId": "akshare",
            "dependencyInstalled": True,
            "providerAvailable": False,
            "supportedCapabilities": ["cn_stock_list"],
            "unsupportedCapabilities": ["hk_index_quote"],
            "degradationReason": "akshare_provider_unavailable",
            "missingProviderReason": "akshare_provider_unavailable",
            "attemptedAt": f"2026-05-19T02:03:1{calls['akshare']}+00:00",
            "timeoutSeconds": timeout_seconds,
            "interfaceHealth": "unavailable",
        }

    def baostock_probe(timeout_seconds: float) -> dict:
        calls["baostock"] += 1
        return {
            "providerName": "baostock",
            "providerId": "baostock",
            "dependencyInstalled": True,
            "providerAvailable": False,
            "supportedCapabilities": [
                "cn_adjust_factor",
                "cn_basic_financials",
                "cn_history_daily",
                "cn_index_history_daily",
            ],
            "unsupportedCapabilities": ["cn_quote"],
            "degradationReason": "baostock_live_probe_disabled",
            "missingProviderReason": "baostock_live_probe_disabled",
            "attemptedAt": None,
            "timeoutSeconds": timeout_seconds,
            "serverHealth": "probe_disabled",
            "healthStatus": "probe_disabled",
        }

    client = _client(
        monkeypatch,
        pytdx_probe=pytdx_probe,
        akshare_probe=akshare_probe,
        baostock_probe=baostock_probe,
    )

    first = {item["providerId"]: item for item in client.get("/api/v1/market/cn-provider-health").json()}
    second = {item["providerId"]: item for item in client.get("/api/v1/market/cn-provider-health").json()}
    refreshed = {
        item["providerId"]: item
        for item in client.get("/api/v1/market/cn-provider-health", params={"forceRefresh": "true"}).json()
    }

    assert calls == {"pytdx": 2, "akshare": 2, "baostock": 2}
    assert first["pytdx"]["attemptedAt"] == "2026-05-19T02:03:01+00:00"
    assert second["pytdx"]["attemptedAt"] == "2026-05-19T02:03:01+00:00"
    assert refreshed["pytdx"]["attemptedAt"] == "2026-05-19T02:03:02+00:00"
    assert first["akshare"]["healthStatus"] == "unavailable_provider"
    assert second["akshare"]["healthStatus"] == "unavailable_provider"
    assert refreshed["akshare"]["healthStatus"] == "unavailable_provider"
    assert first["baostock"]["healthStatus"] == "probe_disabled"
    assert second["baostock"]["healthStatus"] == "probe_disabled"
    assert refreshed["baostock"]["healthStatus"] == "probe_disabled"
    assert first["akshare"]["scoreContributionAllowed"] is False
    assert refreshed["akshare"]["scoreContributionAllowed"] is False
    assert first["baostock"]["scoreContributionAllowed"] is False
