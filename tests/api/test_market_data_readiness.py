# -*- coding: utf-8 -*-
"""API contract tests for the market data readiness diagnostics endpoint."""

from __future__ import annotations

import json
import socket
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import requests

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


class _Payload:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def to_dict(self) -> dict:
        return dict(self._payload)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    return TestClient(app)


def _spec_finder_with(available_modules: set[str]):
    def _finder(module_name: str):
        return object() if module_name in available_modules else None

    return _finder


def test_market_data_readiness_route_is_exposed() -> None:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }

    assert ("GET", "/api/v1/market/data-readiness") in routes


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
    assert isinstance(checks, list)
    assert all(set(check) >= EXPECTED_CHECK_FIELDS for check in checks)
    assert any(check["id"] == "tushare_token" and check["secretConfigured"] is True for check in checks)
    assert all(
        "secretConfigured" not in check
        for check in checks
        if check["id"] != "tushare_token"
    )
    assert all(check["status"] in {"ready", "missing", "partial", "misconfigured"} for check in checks)
    assert all(check["affectsSurfaces"] for check in checks)

    serialized = json.dumps(payload, ensure_ascii=False)
    assert secret not in serialized


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
