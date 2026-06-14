# -*- coding: utf-8 -*-
"""Contract tests for the AI Stock Research endpoint scaffold."""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import agent as agent_endpoint


FORBIDDEN_RESPONSE_TERMS = (
    "buy",
    "sell",
    "add position",
    "加仓",
    "reduce position",
    "减仓",
    "full position",
    "满仓",
    "clear position",
    "清仓",
    "take profit",
    "stop loss",
    "止盈",
    "止损",
    "target price",
    "目标价",
    "predicted return",
    "预测收益",
    "ai recommendation",
    "ai 推荐",
    "smart stock picking",
    "智能选股",
)


def _user() -> CurrentUser:
    return CurrentUser(
        user_id="user-research",
        username="researcher",
        display_name="Researcher",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="session-research",
    )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(agent_endpoint.router, prefix="/api/v1/agent")
    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_stock_research_endpoint_returns_structured_unavailable_contract() -> None:
    response = _client().get(
        "/api/v1/agent/stock-research",
        params={"ticker": "AAPL", "market": "US", "research_window": "30d"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["ticker"] == "AAPL"
    assert payload["market"] == "US"
    assert payload["research_window"] == "30d"
    assert payload["generated_at"]
    assert payload["as_of"] == payload["generated_at"]
    assert payload["evidence_status"] == "unavailable"
    assert payload["data_quality"]["status"] == "unavailable"
    assert payload["summary"]["status"] == "unavailable"
    assert payload["bullish_factors"] == []
    assert payload["bearish_factors"] == []
    assert payload["neutral_or_uncertain_factors"]
    assert payload["technical_state"] is None
    assert payload["portfolio_watchlist_relevance"] is None
    assert payload["sources"] == []
    assert payload["freshness"]["status"] == "unavailable"
    assert payload["risk_disclosure"]
    assert payload["no_advice_disclosure"]
    assert payload["unavailable"]["reason"] == "evidence_missing"


def test_stock_research_serialized_response_excludes_trading_advice_terms() -> None:
    response = _client().get(
        "/api/v1/agent/stock-research",
        params={"ticker": "MSFT", "market": "US"},
    )

    assert response.status_code == 200
    serialized = _json_text(response.json())
    leaked = [term for term in FORBIDDEN_RESPONSE_TERMS if term.lower() in serialized]
    assert leaked == []
