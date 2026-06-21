# -*- coding: utf-8 -*-
"""API contracts for the bounded supplied-input backtest parameter sweep."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from api.deps import CurrentUser, get_current_user, get_database_manager  # noqa: E402
from api.v1.endpoints import backtest  # noqa: E402
from tests.test_backtest_parameter_sweep_pilot import (  # noqa: E402
    FORBIDDEN_PUBLIC_TERMS,
    _parsed_strategy_payload,
)


def _user() -> CurrentUser:
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


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(backtest.router, prefix="/api/v1/backtest")
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_database_manager] = lambda: object()
    return TestClient(app)


def _supplied_bars(*, code: str = "600519", days: int = 60) -> list[dict[str, Any]]:
    closes = [
        10.0,
        10.2,
        10.1,
        10.5,
        11.0,
        11.6,
        11.8,
        11.2,
        10.8,
        10.2,
        9.9,
        10.3,
        10.9,
        11.4,
        11.9,
        12.1,
        11.7,
        11.1,
        10.7,
        10.4,
    ]
    start = date(2024, 1, 1)
    bars: list[dict[str, Any]] = []
    for index in range(days):
        close = closes[index % len(closes)] + float(index // len(closes)) * 0.15
        bars.append(
            {
                "code": code,
                "date": (start + timedelta(days=index)).isoformat(),
                "open": close - 0.1,
                "high": close + 0.2,
                "low": max(0.01, close - 0.3),
                "close": close,
                "volume": 1000.0 + index,
            }
        )
    return bars


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": "600519",
        "strategy_text": "MA diagnostic comparison",
        "parsed_strategy": _parsed_strategy_payload(),
        "start_date": "2024-01-01",
        "end_date": "2024-02-20",
        "lookback_bars": 20,
        "initial_capital": 100000.0,
        "fee_bps": 0.0,
        "slippage_bps": 0.0,
        "execution_model": {"version": "v1"},
        "confirmed": True,
        "parameter_grid": {
            "strategy_spec.signal.fast_period": [2, 3],
            "strategy_spec.signal.slow_period": [5],
        },
        "max_combinations": 10,
        "total_timeout_seconds": 30.0,
        "bars": _supplied_bars(),
    }
    payload.update(overrides)
    return payload


def test_supplied_input_parameter_sweep_returns_results_and_lineage_readiness() -> None:
    client = _client()

    response = client.post("/api/v1/backtest/rule/parameter-sweep", json=_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "completed"
    assert data["diagnosticOnly"] is True
    assert data["researchOnly"] is True
    assert data["notOptimizer"] is True
    assert data["winnerPromotion"] is False
    assert data["decisionGrade"] is False
    assert data["summary"]["runCount"] == 2
    assert data["summary"]["skippedCount"] == 0
    assert data["summary"]["blockedCount"] == 0
    assert len(data["parameterRows"]) == 2
    lineage = data["datasetLineageReadiness"]
    assert lineage["contractKind"] == "rule_backtest_parameter_sweep_dataset_lineage_readiness"
    assert lineage["readinessState"] == "diagnostic-only"
    assert lineage["professionalReadinessApproved"] is False
    assert lineage["barBoundary"]["suppliedBarsToRunner"] is True
    assert lineage["barBoundary"]["providerCallsExecuted"] is False
    assert lineage["sourceAuthority"]["authorityAllowed"] is False
    assert lineage["reproducibility"]["gridDescriptorHashSha256"] == data["reproducibilityMetadata"][
        "gridDescriptorHashSha256"
    ]


def test_supplied_input_parameter_sweep_rejects_oversized_grid_fail_closed() -> None:
    client = _client()

    response = client.post(
        "/api/v1/backtest/rule/parameter-sweep",
        json=_payload(
            parameter_grid={
                "strategy_spec.signal.fast_period": list(range(1, 12)),
                "strategy_spec.signal.slow_period": [20],
            }
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "rejected"
    assert data["failClosedReasonCode"] == "max_combinations_rejected"
    assert data["summary"]["runCount"] == 0
    assert data["datasetLineageReadiness"]["readinessState"] == "blocked"
    assert data["datasetLineageReadiness"]["barBoundary"]["providerCallsExecuted"] is False


def test_supplied_input_parameter_sweep_missing_bars_fails_closed() -> None:
    client = _client()

    response = client.post("/api/v1/backtest/rule/parameter-sweep", json=_payload(bars=[]))

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "rejected"
    assert data["failClosedReasonCode"] == "blocked_missing_supplied_bars"
    assert data["summary"]["runCount"] == 0
    assert data["summary"]["skippedCount"] == 2
    lineage = data["datasetLineageReadiness"]
    assert lineage["readinessState"] == "blocked"
    assert lineage["barBoundary"]["localBars"] is False
    assert lineage["barBoundary"]["suppliedBarsToRunner"] is False
    assert lineage["barBoundary"]["providerCallsExecuted"] is False


def test_supplied_input_parameter_sweep_does_not_hydrate_or_create_stored_run_identity() -> None:
    client = _client()

    response = client.post("/api/v1/backtest/rule/parameter-sweep", json=_payload())

    assert response.status_code == 200
    data = response.json()
    assert "id" not in data
    assert "runId" not in data
    assert data["storage"] == {"mode": "response_only", "storedReadbackAvailable": False}
    assert data["executionAssumptions"]["providerCallsExecuted"] is False
    assert data["executionAssumptions"]["marketCacheAccessed"] is False
    assert data["executionAssumptions"]["storageMutation"] is False
    assert data["datasetLineageReadiness"]["provenanceStatus"]["providerHydrationExecuted"] is False


def test_supplied_input_parameter_sweep_does_not_promote_winner_or_strategy_advice() -> None:
    client = _client()

    response = client.post("/api/v1/backtest/rule/parameter-sweep", json=_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["winnerPromotion"] is False
    assert data["executionAssumptions"]["optimizerExecuted"] is False
    assert data["executionAssumptions"]["winnerPromotion"] is False
    assert data["executionAssumptions"]["decisionGrade"] is False
    serialized = json.dumps(data, ensure_ascii=False).lower()
    for term in FORBIDDEN_PUBLIC_TERMS:
        assert term.lower() not in serialized
    for phrase in (
        "best strategy",
        "optimal strategy",
        "recommended strategy",
        "winner strategy",
        "strategy recommendation",
    ):
        assert phrase not in serialized
