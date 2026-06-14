# -*- coding: utf-8 -*-
"""Consumer-safe contract tests for homepage dashboard market intelligence overview."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.auth as auth
from api.middlewares.auth import add_auth_middleware
from api.v1 import api_v1_router
import api.v1.endpoints.dashboard_overview as dashboard_overview


ROUTE_PATH = "/api/v1/dashboard/market-intelligence-overview"
FORBIDDEN_ADVICE_TERMS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "止损",
    "止盈",
    "目标价",
    "收益预测",
    "AI推荐",
    "智能选股",
    "交易执行",
    "broker execution",
)
FORBIDDEN_INTERNAL_MARKERS = (
    "fallback",
    "trustLevel",
    "reasonCode",
    "confidence",
    "sourceType",
    "provider URL",
    "traceback",
    "raw exception",
    "/Users/",
    "api key",
    "session_id",
    "token",
    "secret",
)
ALLOWED_RESEARCH_ACTIONS = {
    "观察",
    "复核",
    "研究",
    "证据",
    "走强",
    "走弱",
    "扩散",
    "收敛",
    "分歧",
    "暂无证据",
    "适合研究观察",
}
ALLOWED_DATA_QUALITY_STATES = {
    "ready",
    "delayed",
    "cached",
    "partial",
    "no_evidence",
    "unavailable",
}


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}


def _full_client() -> TestClient:
    app = FastAPI()
    add_auth_middleware(app)
    app.include_router(api_v1_router)
    return TestClient(app)


def _route_only_client() -> TestClient:
    app = FastAPI()
    app.include_router(dashboard_overview.router, prefix="/api/v1/dashboard")
    return TestClient(app)


def test_dashboard_overview_endpoint_returns_stable_top_level_sections() -> None:
    client = _route_only_client()
    try:
        response = client.get(ROUTE_PATH)
    finally:
        client.close()

    assert response.status_code == 200
    payload = response.json()

    assert set(payload) == {
        "status",
        "asOf",
        "marketPulse",
        "marketBrief",
        "moneyFlow",
        "liquidityRisk",
        "sectorThemeRotation",
        "researchQueue",
        "dataQuality",
        "noAdviceDisclosure",
    }
    assert payload["status"] in {"ready", "partial", "no_evidence", "unavailable"}
    assert payload["asOf"]
    assert payload["marketPulse"]["sp500"]["label"] == "S&P 500"
    assert payload["marketPulse"]["marketBreadth"]["summary"]
    assert payload["marketBrief"]["headline"]
    assert payload["moneyFlow"]["topInflows"]
    assert payload["liquidityRisk"]["summary"]
    assert payload["sectorThemeRotation"]["summary"]
    assert payload["researchQueue"]["items"]
    assert payload["dataQuality"]["state"] in ALLOWED_DATA_QUALITY_STATES


def test_dashboard_overview_default_response_is_consumer_safe_and_no_advice() -> None:
    client = _route_only_client()
    try:
        response = client.get(ROUTE_PATH)
    finally:
        client.close()

    assert response.status_code == 200
    payload = response.json()
    dumped = json.dumps(payload, ensure_ascii=False)

    assert "不构成投资建议" in payload["noAdviceDisclosure"]
    for term in FORBIDDEN_ADVICE_TERMS:
        assert term not in dumped


def test_dashboard_overview_research_queue_uses_safe_language_only() -> None:
    client = _route_only_client()
    try:
        response = client.get(ROUTE_PATH)
    finally:
        client.close()

    assert response.status_code == 200
    items = response.json()["researchQueue"]["items"]
    assert items
    for item in items:
        assert item["action"] in ALLOWED_RESEARCH_ACTIONS
        for field in ("title", "summary", "action"):
            for term in FORBIDDEN_ADVICE_TERMS:
                assert term not in str(item[field])


def test_dashboard_overview_data_quality_fields_are_bounded() -> None:
    client = _route_only_client()
    try:
        response = client.get(ROUTE_PATH)
    finally:
        client.close()

    assert response.status_code == 200
    payload = response.json()

    assert payload["dataQuality"]["state"] == "ready"
    assert payload["moneyFlow"]["sourceStatus"] in ALLOWED_DATA_QUALITY_STATES
    for section_state in payload["dataQuality"]["sections"].values():
        assert section_state in ALLOWED_DATA_QUALITY_STATES


def test_dashboard_overview_response_does_not_leak_internal_markers_or_secret_like_strings() -> None:
    client = _route_only_client()
    try:
        response = client.get(ROUTE_PATH)
    finally:
        client.close()

    assert response.status_code == 200
    dumped = json.dumps(response.json(), ensure_ascii=False)
    for marker in FORBIDDEN_INTERNAL_MARKERS:
        assert marker not in dumped


def test_dashboard_overview_route_follows_existing_consumer_auth_boundary() -> None:
    _reset_auth_globals()
    client = _full_client()
    service = MagicMock()
    service.get_market_intelligence_overview.return_value = {
        "status": "ready",
        "asOf": "2026-06-14T09:30:00Z",
        "marketPulse": {
            "sp500": {"label": "S&P 500", "value": "观察中", "change": "0.0%", "status": "ready"},
            "nasdaq": {"label": "Nasdaq", "value": "观察中", "change": "0.0%", "status": "ready"},
            "russell2000": {"label": "Russell 2000", "value": "观察中", "change": "0.0%", "status": "ready"},
            "vix": {"label": "VIX", "value": "中性", "change": "0.0", "status": "ready"},
            "tenYearYield": {"label": "10Y Yield", "value": "中性", "change": "0bp", "status": "ready"},
            "dollarIndex": {"label": "Dollar Index", "value": "中性", "change": "0.0%", "status": "ready"},
            "marketBreadth": {"summary": "广度中性，适合继续观察。", "status": "ready"},
            "liquidityState": "流动性中性观察",
        },
        "marketBrief": {
            "headline": "市场状态以观察为主",
            "summary": "当前概览仅用于研究观察，不用于交易判断。",
            "status": "ready",
        },
        "moneyFlow": {
            "topInflows": ["大型股指数"],
            "topOutflows": ["高波动题材"],
            "styleBias": "均衡",
            "offensiveDefensiveBias": "中性",
            "sourceStatus": "ready",
            "status": "ready",
        },
        "liquidityRisk": {"summary": "流动性与风险偏好暂处中性。", "volatilityTone": "平稳", "fundingStress": "可控", "dollarRatePressure": "中性", "status": "ready"},
        "sectorThemeRotation": {"leadingThemes": ["防御质量"], "laggingThemes": ["高波动题材"], "diffusion": "分歧", "summary": "主题轮动仍以分歧为主。", "status": "ready"},
        "researchQueue": {"status": "ready", "items": [{"title": "指数广度复核", "summary": "观察广度是否继续扩散。", "action": "复核", "priority": "high"}]},
        "dataQuality": {"state": "ready", "label": "正常", "summary": "接口合同正常。", "sections": {"marketPulse": "ready", "marketBrief": "ready", "moneyFlow": "ready", "liquidityRisk": "ready", "sectorThemeRotation": "ready", "researchQueue": "ready"}},
        "noAdviceDisclosure": "本概览仅用于市场研究观察，不构成投资建议或交易指令。",
    }

    with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
        with patch("api.v1.endpoints.dashboard_overview.DashboardOverviewService", return_value=service):
            response = client.get(ROUTE_PATH)

    try:
        assert response.status_code == 401
        assert response.json() == {"error": "unauthorized", "message": "Login required"}
        service.get_market_intelligence_overview.assert_not_called()
    finally:
        client.close()
        _reset_auth_globals()
