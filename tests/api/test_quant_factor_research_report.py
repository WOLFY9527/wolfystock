# -*- coding: utf-8 -*-
"""API contract tests for the supplied-input factor research report pilot."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import quant


def _admin_user(*, admin_capabilities: tuple[str, ...] = ()) -> CurrentUser:
    return CurrentUser(
        user_id="admin",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=admin_capabilities,
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
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


def _client(*, user_factory) -> TestClient:
    app = FastAPI()
    app.include_router(quant.router, prefix="/api/v1/quant")
    app.dependency_overrides[get_current_user] = user_factory
    app.dependency_overrides[quant.get_quant_duckdb_service] = lambda: (_ for _ in ()).throw(
        AssertionError("factor report must not hydrate DuckDB or provider-backed services")
    )
    return TestClient(app)


def _metric_observation(
    *,
    factor_id: str,
    symbol: str,
    as_of: str,
    value: float,
    returns: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "observation": {
            "factor_id": factor_id,
            "symbol": symbol,
            "value": value,
            "source_name": "unit_fixture",
            "source_type": "synthetic_fixture",
            "as_of": as_of,
            "observed_at": f"{as_of}T15:00:00Z",
            "freshness_status": "partial",
            "confidence": 0.55,
            "is_partial": True,
        },
        "forwardReturns": dict(returns or {}),
    }


def _factor_report_payload() -> dict[str, Any]:
    rows = [
        ("2026-05-01", "AAA", 4.0, {"1d": 0.04, "5d": 0.01}, "Technology", 100.0),
        ("2026-05-01", "BBB", 3.0, {"1d": 0.03, "5d": 0.02}, "Technology", 300.0),
        ("2026-05-01", "CCC", 2.0, {"1d": 0.02, "5d": 0.03}, "Finance", 200.0),
        ("2026-05-01", "DDD", 1.0, {"1d": 0.01, "5d": 0.04}, "Finance", 400.0),
        ("2026-05-02", "AAA", 1.0, {"1d": 0.01, "5d": 0.04}, "Technology", 100.0),
        ("2026-05-02", "BBB", 4.0, {"1d": 0.04, "5d": 0.01}, "Technology", 300.0),
        ("2026-05-02", "CCC", 3.0, {"1d": 0.03, "5d": 0.02}, "Finance", 200.0),
        ("2026-05-02", "DDD", 2.0, {"1d": 0.02, "5d": 0.03}, "Finance", 400.0),
        ("2026-05-03", "AAA", 2.0, {"1d": 0.02, "5d": 0.03}, "Technology", 100.0),
        ("2026-05-03", "BBB", 1.0, {"1d": 0.01, "5d": 0.04}, "Technology", 300.0),
        ("2026-05-03", "CCC", 4.0, {"1d": 0.04, "5d": 0.01}, "Finance", 200.0),
        ("2026-05-03", "DDD", 3.0, {"1d": 0.03, "5d": 0.02}, "Finance", 400.0),
    ]
    metric_observations = [
        _metric_observation(
            factor_id="momentum.momentum_21d",
            symbol=symbol,
            as_of=as_of,
            value=value,
            returns=returns,
        )
        for as_of, symbol, value, returns, _sector, _market_cap in rows
    ]
    metric_observations.extend(
        _metric_observation(
            factor_id="trend.trend_strength_20d",
            symbol=symbol,
            as_of=as_of,
            value=-value,
            returns=returns,
        )
        for as_of, symbol, value, returns, _sector, _market_cap in rows
    )
    observations = [
        {
            "observation": item["observation"],
            "sector": sector,
            "marketCap": market_cap,
        }
        for item, (_as_of, _symbol, _value, _returns, sector, market_cap) in zip(
            metric_observations[: len(rows)],
            rows,
        )
    ]
    observations.extend(
        {
            "observation": item["observation"],
            "sector": sector,
            "marketCap": market_cap,
        }
        for item, (_as_of, _symbol, _value, _returns, sector, market_cap) in zip(
            metric_observations[len(rows) :],
            rows,
        )
    )
    return {
        "observations": observations,
        "metricObservations": metric_observations,
        "portfolioWeights": [
            {"symbol": "AAA", "weight": 2.0},
            {"symbol": "BBB", "weight": 1.0},
            {"symbol": "CCC", "weight": 1.0},
            {"symbol": "DDD", "weight": 1.0},
        ],
        "longWeights": [{"symbol": "AAA", "weight": 2.0}, {"symbol": "BBB", "weight": 1.0}],
        "shortWeights": [{"symbol": "CCC", "weight": 1.0}, {"symbol": "DDD", "weight": 1.0}],
        "neutralizationAxes": ["sector"],
    }


def test_factor_research_report_endpoint_requires_quant_admin_read_capability() -> None:
    unauthenticated = _client(user_factory=_unauthenticated_user).post(
        "/api/v1/quant/factor-research/report",
        json=_factor_report_payload(),
    )
    assert unauthenticated.status_code == 401

    forbidden = _client(user_factory=_regular_user).post(
        "/api/v1/quant/factor-research/report",
        json=_factor_report_payload(),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["error"] == "admin_required"

    missing_capability = _client(user_factory=lambda: _admin_user()).post(
        "/api/v1/quant/factor-research/report",
        json=_factor_report_payload(),
    )
    assert missing_capability.status_code == 403
    assert missing_capability.json()["detail"]["error"] == "admin_capability_required"


def test_factor_research_report_endpoint_builds_supplied_input_report_without_hydration() -> None:
    response = _client(
        user_factory=lambda: _admin_user(admin_capabilities=("quant:admin:read",)),
    ).post("/api/v1/quant/factor-research/report", json=_factor_report_payload())

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ready"
    assert payload["boundary"]["purpose"] == "diagnostic factor report"
    assert payload["boundary"]["researchOnly"] is True
    assert payload["boundary"]["diagnosticOnly"] is True
    assert payload["boundary"]["suppliedObservationsOnly"] is True
    assert payload["boundary"]["portfolioOptimizer"] is False
    assert payload["boundary"]["externalDataHydrationExecuted"] is False
    assert payload["boundary"]["liveQuoteHydrationExecuted"] is False
    assert payload["boundary"]["forwardReturnsComputed"] is False

    assert payload["inputShape"]["observationCount"] == 24
    assert payload["inputShape"]["metricObservationCount"] == 24
    assert payload["inputShape"]["forwardReturnObservationCount"] == 24
    assert payload["inputShape"]["neutralizationAxes"] == ["sector"]
    assert len(payload["inputShape"]["inputContentHash"]) == 64

    assert [item["factorId"] for item in payload["factorMetadata"]] == [
        "momentum.momentum_21d",
        "trend.trend_strength_20d",
    ]
    momentum = payload["report"]["metricsSummary"][0]
    assert momentum["factorId"] == "momentum.momentum_21d"
    assert momentum["ic"][0]["value"] == 1.0
    assert momentum["rankIc"][1]["value"] == -1.0
    assert {item["scope"] for item in payload["report"]["exposureSummary"]} == {"long_short", "portfolio"}
    assert payload["missingDataReasons"] == []

    text = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in (
        "re" + "commended",
        "should " + "trade",
        "target " + "price",
        "stop " + "loss",
        "买" + "入建议",
        "卖" + "出建议",
        "目标" + "价",
        "止" + "损",
        "交易" + "建议",
    ):
        assert forbidden not in text


def test_factor_research_report_endpoint_fails_closed_without_forward_returns() -> None:
    metric_observations = [
        _metric_observation(
            factor_id="momentum.momentum_21d",
            symbol=symbol,
            as_of="2026-05-01",
            value=value,
            returns={},
        )
        for symbol, value in (("AAA", 4.0), ("BBB", 3.0), ("CCC", 2.0), ("DDD", 1.0))
    ]
    response = _client(
        user_factory=lambda: _admin_user(admin_capabilities=("quant:admin:read",)),
    ).post(
        "/api/v1/quant/factor-research/report",
        json={
            "observations": [{"observation": item["observation"]} for item in metric_observations],
            "metricObservations": metric_observations,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["report"]["metricsSummary"][0]["ic"] == []
    assert {
        (item["section"], item["reason"], item.get("factorId"))
        for item in payload["missingDataReasons"]
    } >= {("metrics", "missing_forward_returns", "momentum.momentum_21d")}
