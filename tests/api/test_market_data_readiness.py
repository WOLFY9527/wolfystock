# -*- coding: utf-8 -*-
"""API contract tests for the market data readiness diagnostics endpoint."""

from __future__ import annotations

import json
import socket
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
import requests

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import market
from src.services.market_data_readiness_diagnostics import build_market_data_readiness_diagnostics


EXPECTED_CHECK_FIELDS = {
    "id",
    "status",
    "severity",
    "userFacingMessage",
    "remediationHint",
    "affectsSurfaces",
}
EXPECTED_CONSUMER_READINESS_FIELDS = {
    "surface",
    "evidenceFamily",
    "requiredInputs",
    "fulfilledInputs",
    "missingInputs",
    "staleInputs",
    "blockedInputs",
    "observationOnlyInputs",
    "scoreGradeInputs",
    "readinessState",
    "confidenceCapReason",
    "sourceAuthorityReason",
    "freshnessReason",
    "nextDiagnostic",
    "consumerSafeSummary",
}
FORBIDDEN_CONSUMER_READINESS_TERMS = {
    "provider",
    "cache",
    "runtime",
    "raw",
    "debug",
    "requestid",
    "traceid",
    "schema",
    "marketcache",
    "fred",
    "yfinance",
    "providerclass",
    "officialoverlay",
    "cache_miss",
    "stale_official_row",
    "token",
    "cookie",
    "buy",
    "sell",
    "hold",
    "recommend",
    "target price",
    "stop loss",
    "position sizing",
    "买入",
    "卖出",
    "持有",
    "投资建议",
    "交易建议",
    "目标价",
    "止损",
    "仓位建议",
}
EXPECTED_OFFICIAL_RISK_READINESS_FIELDS = {
    "contractVersion",
    "diagnosticOnly",
    "networkCallsEnabled",
    "externalProviderCalls",
    "mutationEnabled",
    "vix",
    "rates",
    "fedLiquidity",
    "bundleState",
    "consumerSummary",
    "nextDataAction",
}
EXPECTED_OFFICIAL_RISK_FAMILY_FIELDS = {
    "state",
    "series",
    "source",
    "latestDate",
    "asOf",
    "freshness",
    "blocker",
}
EXPECTED_OFFICIAL_RATES_FIELDS = EXPECTED_OFFICIAL_RISK_FAMILY_FIELDS | {"coveredSeriesCount"}


class _Payload:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def to_dict(self) -> dict:
        return dict(self._payload)


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


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.dependency_overrides[get_current_user] = _provider_read_admin
    return TestClient(app)


def _spec_finder_with(available_modules: set[str]):
    def _finder(module_name: str):
        return object() if module_name in available_modules else None

    return _finder


def test_market_data_readiness_route_is_exposed() -> None:
    with _client() as client:
        client.app.dependency_overrides[get_current_user] = _unauthenticated_user
        unauthenticated = client.get("/api/v1/market/data-readiness")
        assert unauthenticated.status_code == 401

        client.app.dependency_overrides[get_current_user] = _regular_user
        member = client.get("/api/v1/market/data-readiness")
        assert member.status_code == 403
        assert member.json()["detail"]["error"] == "admin_required"

        client.app.dependency_overrides[get_current_user] = _provider_read_admin
        response = client.get("/api/v1/market/data-readiness")

    assert response.status_code == 200
    assert response.json()["diagnosticOnly"] is True


def test_market_data_readiness_route_returns_read_only_diagnostic_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()
    (parquet_dir / "AAPL.parquet").touch()
    (parquet_dir / "SPY.parquet").touch()
    captured: dict[str, tuple[str, ...]] = {}
    secret = "super-secret-token"

    def fake_builder(*, representative_symbols=None):
        captured["representative_symbols"] = tuple(representative_symbols or ())
        return build_market_data_readiness_diagnostics(
            representative_symbols=representative_symbols,
            env={
                "LOCAL_US_PARQUET_DIR": str(parquet_dir),
                "TUSHARE_TOKEN": secret,
            },
            spec_finder=_spec_finder_with({"pyarrow", "tushare", "pytdx", "akshare", "efinance"}),
        )

    monkeypatch.setattr(market, "build_market_data_readiness_diagnostics", fake_builder)
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network call attempted")),
    )
    monkeypatch.setattr(
        requests.sessions.Session,
        "request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("http request attempted")),
    )

    with _client() as client:
        response = client.get("/api/v1/market/data-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["diagnosticOnly"] is True
    assert payload["providerRuntimeCalled"] is False
    assert payload["networkCallsEnabled"] is False
    assert payload["representativeSymbols"] == []
    assert captured["representative_symbols"] == ()

    checks = payload["checks"]
    matrix = payload["consumerEvidenceReadinessMatrix"]
    official_risk = payload["officialRiskSourceReadiness"]
    cross_asset = payload["crossAssetDriverReadiness"]
    rows = matrix["items"]

    assert matrix["contractVersion"] == "consumer_evidence_readiness_matrix_v1"
    assert matrix["diagnosticOnly"] is True
    assert matrix["networkCallsEnabled"] is False
    assert matrix["mutationEnabled"] is False
    assert set(official_risk) == EXPECTED_OFFICIAL_RISK_READINESS_FIELDS
    assert official_risk["contractVersion"] == "official_risk_source_readiness_v1"
    assert official_risk["diagnosticOnly"] is True
    assert official_risk["networkCallsEnabled"] is False
    assert official_risk["externalProviderCalls"] is False
    assert official_risk["mutationEnabled"] is False
    assert official_risk["bundleState"] in {"ready", "partial", "blocked", "unknown"}
    assert set(official_risk["vix"]) == EXPECTED_OFFICIAL_RISK_FAMILY_FIELDS
    assert set(official_risk["rates"]) == EXPECTED_OFFICIAL_RATES_FIELDS
    assert set(official_risk["fedLiquidity"]) == EXPECTED_OFFICIAL_RISK_FAMILY_FIELDS
    assert official_risk["vix"]["series"] == "VIXCLS"
    assert official_risk["rates"]["coveredSeriesCount"] == 0
    assert isinstance(official_risk["consumerSummary"], str)
    assert isinstance(official_risk["nextDataAction"], str)
    assert cross_asset["contractVersion"] == "cross_asset_driver_readiness_v1"
    assert cross_asset["consumerSafe"] is True
    assert cross_asset["diagnosticOnly"] is True
    assert cross_asset["networkCallsEnabled"] is False
    assert cross_asset["externalProviderCalls"] is False
    assert cross_asset["mutationEnabled"] is False
    assert {
        "equities_index",
        "rates",
        "usd",
        "oil_energy",
        "gold",
        "volatility",
        "credit",
        "crypto",
        "sectors",
    } == {item["category"] for item in cross_asset["drivers"]}
    assert all(item["state"] in cross_asset["supportedStates"] for item in cross_asset["drivers"])
    assert next(item for item in cross_asset["drivers"] if item["category"] == "credit")["state"] == "not_configured"
    assert "no market conclusion is inferred" in cross_asset["consumerSummary"]
    assert {
        "market_overview",
        "liquidity_monitor",
        "rotation_radar",
        "decision_cockpit",
        "home_briefing",
        "research_radar",
    } <= {row["surface"] for row in rows}
    assert {
        ("market_overview", "official_vix_volatility"),
        ("liquidity_monitor", "vix_pressure"),
        ("market_overview", "official_macro_rates_liquidity_bundle"),
        ("liquidity_monitor", "macro_rates_fed_liquidity_bundle"),
    } <= {
        (row["surface"], row["evidenceFamily"])
        for row in rows
    }
    assert all(set(row) == EXPECTED_CONSUMER_READINESS_FIELDS for row in rows)

    readiness_rows = {
        (row["surface"], row["evidenceFamily"]): row
        for row in rows
    }
    vix_overview = readiness_rows[("market_overview", "official_vix_volatility")]
    assert vix_overview["requiredInputs"] == ["VIXCLS official volatility close"]
    assert vix_overview["scoreGradeInputs"] == []
    assert vix_overview["readinessState"] == "missing"
    macro_bundle = readiness_rows[("liquidity_monitor", "macro_rates_fed_liquidity_bundle")]
    assert macro_bundle["requiredInputs"] == [
        "Treasury daily rates",
        "policy-rate daily rows",
        "credit and USD pressure rows",
        "Fed liquidity weekly rows",
    ]
    assert macro_bundle["scoreGradeInputs"] == []
    assert macro_bundle["readinessState"] == "observation_only"

    assert isinstance(checks, list)
    assert all(set(check) >= EXPECTED_CHECK_FIELDS for check in checks)
    assert any(check["id"] == "tushare_token" and check["secretConfigured"] is True for check in checks)
    assert all(
        "secretConfigured" not in check
        for check in checks
        if check["id"] != "tushare_token"
    )
    assert all(
        check["status"]
        in {
            "ready",
            "available",
            "disabled",
            "missing",
            "partial",
            "misconfigured",
            "dependency_missing",
            "runtime_unavailable",
        }
        for check in checks
    )
    assert all(check["affectsSurfaces"] for check in checks)

    serialized = json.dumps(payload, ensure_ascii=False)
    assert secret not in serialized
    assert str(parquet_dir) not in serialized
    assert str(tmp_path) not in serialized

    serialized_matrix = json.dumps(matrix, ensure_ascii=False).lower()
    for term in FORBIDDEN_CONSUMER_READINESS_TERMS:
        assert term not in serialized_matrix

    serialized_official_risk_consumer = json.dumps(
        {
            "consumerSummary": official_risk["consumerSummary"],
            "nextDataAction": official_risk["nextDataAction"],
        },
        ensure_ascii=False,
    ).lower()
    for term in FORBIDDEN_CONSUMER_READINESS_TERMS | {"credential", "secret", "api_key"}:
        assert term not in serialized_official_risk_consumer
    serialized_cross_asset = json.dumps(cross_asset, ensure_ascii=False).lower()
    cross_asset_forbidden_terms = (
        (FORBIDDEN_CONSUMER_READINESS_TERMS - {"cache", "cache_miss", "provider"})
        | {"credential", "secret", "api_key", "liquidity", "inflation", "recession"}
    )
    for term in cross_asset_forbidden_terms:
        assert term not in serialized_cross_asset

    parquet_check = next(check for check in checks if check["id"] == "local_us_parquet_dir")
    assert parquet_check["details"]["pathConfigured"] is True
    assert parquet_check["details"]["pathBasename"] == "us-parquet"
    assert parquet_check["details"]["storageKind"] == "local_filesystem"


def test_market_data_readiness_symbols_query_is_bounded_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, tuple[str, ...]] = {}

    def fake_builder(*, representative_symbols=None):
        captured["representative_symbols"] = tuple(representative_symbols or ())
        return _Payload(
            {
                "readinessStatus": "ready",
                "diagnosticOnly": True,
                "providerRuntimeCalled": False,
                "networkCallsEnabled": False,
                "representativeSymbols": list(representative_symbols or ()),
                "checks": [],
            }
        )

    monkeypatch.setattr(market, "build_market_data_readiness_diagnostics", fake_builder)

    with _client() as client:
        response = client.get(
            "/api/v1/market/data-readiness",
            params={"symbols": " orcl,, aapl , spy , brk.b , btc-usd , qqq_1 , x1 , y2 , z3 , ignored "},
        )

    assert response.status_code == 200
    assert captured["representative_symbols"] == ("ORCL", "AAPL", "SPY", "BRK.B", "BTC-USD", "QQQ_1", "X1", "Y2")
    assert response.json()["representativeSymbols"] == ["ORCL", "AAPL", "SPY", "BRK.B", "BTC-USD", "QQQ_1", "X1", "Y2"]
