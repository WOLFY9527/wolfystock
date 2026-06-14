# -*- coding: utf-8 -*-
"""Consumer-safe contract tests for homepage dashboard market intelligence overview."""

from __future__ import annotations

import json
import os
import sys
import types
from dataclasses import dataclass
from importlib import util
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")
if "orjson" not in sys.modules:
    sys.modules["orjson"] = types.SimpleNamespace(
        OPT_NON_STR_KEYS=0,
        OPT_SERIALIZE_NUMPY=0,
        dumps=lambda value, option=0: json.dumps(value).encode("utf-8"),
        loads=json.loads,
    )
sys.modules.setdefault("greenlet", None)

from fastapi import FastAPI
from fastapi.testclient import TestClient

@dataclass(frozen=True)
class _CurrentUser:
    user_id: str = "anonymous"
    username: str = "anonymous"
    display_name: str | None = "Anonymous"
    role: str = "anonymous"
    is_admin: bool = False
    session_id: str | None = None


def _optional_current_user():
    return None


ENDPOINT_PATH = Path(__file__).resolve().parents[2] / "api/v1/endpoints/dashboard_overview.py"
sys.modules.setdefault(
    "api.deps",
    types.SimpleNamespace(CurrentUser=_CurrentUser, get_optional_current_user=_optional_current_user),
)
_endpoint_spec = util.spec_from_file_location("dashboard_overview_under_test", ENDPOINT_PATH)
assert _endpoint_spec is not None and _endpoint_spec.loader is not None
dashboard_overview = util.module_from_spec(_endpoint_spec)
_endpoint_spec.loader.exec_module(dashboard_overview)

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
    "provider_id",
    "providerId",
    "provider_payload",
    "provider_response",
    "raw_provider",
    "diagnostic",
    "diagnostics",
    "source_run_id",
    "external_run_id",
    "trade_id",
    "fill_reason_codes",
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
    assert payload["liquidityRisk"]["summary"]
    assert payload["sectorThemeRotation"]["summary"]
    assert isinstance(payload["moneyFlow"]["topInflows"], list)
    assert isinstance(payload["moneyFlow"]["topOutflows"], list)
    assert isinstance(payload["sectorThemeRotation"]["leadingThemes"], list)
    assert isinstance(payload["sectorThemeRotation"]["laggingThemes"], list)
    assert isinstance(payload["researchQueue"]["items"], list)
    assert payload["dataQuality"]["state"] in ALLOWED_DATA_QUALITY_STATES


def test_dashboard_overview_uses_bounded_scaffold_compatible_subcontracts() -> None:
    client = _route_only_client()

    class FakeMarketPulseService:
        def build_snapshot(self):
            return {
                "status": "partial",
                "indices": [
                    {
                        "label": "S&P 500",
                        "value": 5123.45,
                        "unit": "pt",
                        "change": 0.12,
                        "state": "观察",
                        "interpretation": "适合研究观察",
                        "dataQuality": {"state": "正常", "label": "正常", "available": True},
                    },
                    {
                        "label": "Nasdaq",
                        "value": 17234.5,
                        "unit": "pt",
                        "change": -0.21,
                        "state": "复核",
                        "interpretation": "复核",
                        "dataQuality": {"state": "复核", "label": "复核", "available": True},
                    },
                    {
                        "label": "Russell 2000",
                        "value": None,
                        "unit": "pt",
                        "change": None,
                        "state": "暂无证据",
                        "interpretation": "暂无证据",
                        "dataQuality": {"state": "暂无证据", "label": "暂无证据", "available": False},
                    },
                ],
                "volatility": {
                    "label": "VIX",
                    "value": 14.2,
                    "unit": "pt",
                    "change": -0.3,
                    "state": "中性",
                    "interpretation": "适合研究观察",
                    "dataQuality": {"state": "正常", "label": "正常", "available": True},
                },
                "rates": {
                    "label": "10Y Treasury yield",
                    "value": 4.18,
                    "unit": "%",
                    "change": 0.01,
                    "state": "观察",
                    "interpretation": "观察",
                    "dataQuality": {"state": "观察", "label": "观察", "available": True},
                },
                "dollar": {
                    "label": "Dollar index",
                    "value": 104.3,
                    "unit": "pt",
                    "change": 0.05,
                    "state": "中性",
                    "interpretation": "适合研究观察",
                    "dataQuality": {"state": "正常", "label": "正常", "available": True},
                },
                "breadth": {
                    "label": "Market breadth",
                    "value": 52.0,
                    "unit": "%",
                    "change": 1.0,
                    "state": "观察",
                    "interpretation": "观察",
                    "dataQuality": {"state": "观察", "label": "观察", "available": True},
                },
                "liquidity": {
                    "label": "Liquidity state",
                    "value": None,
                    "unit": None,
                    "change": None,
                    "state": "中性",
                    "interpretation": "中性",
                    "dataQuality": {"state": "正常", "label": "正常", "available": True},
                },
                "dataQuality": {"state": "正常", "label": "正常", "available": True},
                "noAdviceDisclosure": "仅供研究观察，不构成投资建议。",
            }

    class FakeMoneyFlowService:
        def build_homepage_money_flow_proxy(self):
            return {
                "status": "partial",
                "topInflows": [
                    {
                        "name": "质量因子",
                        "category": "style",
                        "direction": "inflow",
                        "strength": "moderate",
                        "breadth": "mixed",
                        "relativeMove": "strengthening",
                        "interpretation": "观察相对强度变化。",
                        "dataQuality": "partial",
                    }
                ],
                "topOutflows": [],
                "styleBias": {
                    "bias": "quality",
                    "interpretation": "质量风格相对占优，继续观察。",
                    "dataQuality": {"state": "partial", "label": "部分数据缺失", "available": False},
                },
                "offensiveDefensiveBias": {
                    "bias": "defensive",
                    "interpretation": "防御风格相对占优，继续观察。",
                    "dataQuality": {"state": "partial", "label": "部分数据缺失", "available": False},
                },
                "sourceStatus": {
                    "providerWired": False,
                    "proxyMode": "observed_flow_proxy",
                    "observationOnly": True,
                    "summary": "未接入真实资金流提供方；当前仅保留 observed flow proxy contract scaffold。",
                },
                "dataQuality": {"state": "partial", "label": "部分数据缺失", "available": False},
                "noAdviceDisclosure": "仅用于观察昨日资金流向代理，不构成投资建议或交易指令。",
            }

    class FakeSectorThemeStrengthService:
        def build_summary(self):
            return {
                "status": "ready",
                "strongest": [
                    {
                        "name": "防御质量",
                        "category": "theme",
                        "relativeStrength": 0.7,
                        "breadth": 0.5,
                        "diffusionStatus": "diffusing",
                        "leadershipStatus": "stronger",
                        "observation": "强度扩散仅用于观察。",
                        "dataQuality": {"status": "ready", "observation": "安全观察口径。"},
                    }
                ],
                "weakest": [],
                "leadership": {
                    "status": "stronger",
                    "observation": "少数主题保持领先，继续复核。",
                    "dataQuality": {"status": "ready", "observation": "安全观察口径。"},
                },
                "diffusion": {
                    "status": "diffusing",
                    "observation": "扩散状态仅用于研究观察。",
                    "dataQuality": {"status": "ready", "observation": "安全观察口径。"},
                },
                "concentration": {
                    "status": "neutral",
                    "observation": "集中度中性。",
                    "dataQuality": {"status": "ready", "observation": "安全观察口径。"},
                },
                "dataQuality": {"status": "ready", "observation": "安全观察口径。"},
                "noAdviceDisclosure": "仅用于观察行业与主题强弱变化，非交易建议。",
            }

    class FakeResearchQueueService:
        def build_queue(self):
            return {
                "status": "ready",
                "items": [
                    {
                        "id": "market-1",
                        "priority": 1,
                        "title": "广度复核",
                        "reason": "市场观察信号需要复核后再继续研究。",
                        "category": "market",
                        "reviewModule": "market_overview",
                        "status": "review",
                        "relatedSymbols": [],
                        "relatedThemes": [],
                        "evidenceStatus": "available",
                        "noAdviceDisclosure": "This queue is for research review only and offers no advice.",
                    }
                ],
                "dataQuality": {
                    "status": "ready",
                    "summary": "研究队列条目已生成，可按优先级继续复核。",
                    "availableDomains": ["market"],
                    "missingDomains": [],
                },
                "noAdviceDisclosure": "This queue is for research review only and offers no advice.",
            }

    class FakePublicDataQualityService:
        def __call__(self, value):
            return {
                "status": "ready",
                "label": "正常",
                "suitableForResearchObservation": True,
                "message": "核心模块已更新，适合研究观察",
                "updatedModules": ["首页"],
                "affectedModules": [],
                "noAdviceDisclosure": "仅供研究观察，不构成投资建议",
            }

    with patch("src.services.dashboard_overview_service.MarketPulseService", FakeMarketPulseService):
        with patch("src.services.dashboard_overview_service.MoneyFlowService", FakeMoneyFlowService):
            with patch("src.services.dashboard_overview_service.SectorThemeStrengthService", FakeSectorThemeStrengthService):
                with patch("src.services.dashboard_overview_service.ResearchQueueService", FakeResearchQueueService):
                    with patch("src.services.dashboard_overview_service.build_public_data_quality_summary", FakePublicDataQualityService()):
                        try:
                            response = client.get(ROUTE_PATH)
                        finally:
                            client.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["marketPulse"]["sp500"] == {
        "label": "S&P 500",
        "value": "5123.45 pt",
        "change": "+0.12",
        "status": "ready",
    }
    assert payload["moneyFlow"]["topInflows"] == ["质量因子"]
    assert payload["moneyFlow"]["topOutflows"] == []
    assert payload["moneyFlow"]["styleBias"] == "quality"
    assert payload["moneyFlow"]["sourceStatus"] == "partial"
    assert payload["sectorThemeRotation"]["leadingThemes"] == ["防御质量"]
    assert payload["sectorThemeRotation"]["laggingThemes"] == []
    assert payload["sectorThemeRotation"]["diffusion"] == "diffusing"
    assert payload["researchQueue"]["items"][0] == {
        "title": "广度复核",
        "summary": "市场观察信号需要复核后再继续研究。",
        "action": "复核",
        "priority": "high",
    }
    assert payload["dataQuality"]["state"] == "ready"
    assert payload["dataQuality"]["label"] == "正常"
    assert payload["dataQuality"]["sections"]["marketPulse"] == "partial"
    assert payload["dataQuality"]["sections"]["moneyFlow"] == "partial"
    assert payload["dataQuality"]["sections"]["sectorThemeRotation"] == "ready"
    assert payload["dataQuality"]["sections"]["researchQueue"] == "ready"


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
    assert set(payload["dataQuality"]["sections"]) == {
        "marketPulse",
        "marketBrief",
        "moneyFlow",
        "liquidityRisk",
        "sectorThemeRotation",
        "researchQueue",
    }
    assert payload["dataQuality"]["sections"]["marketBrief"] == "ready"
    assert payload["dataQuality"]["sections"]["liquidityRisk"] == "ready"
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


def test_dashboard_overview_route_keeps_existing_optional_auth_dependency_shape() -> None:
    source = ENDPOINT_PATH.read_text(encoding="utf-8")

    assert "current_user: Optional[CurrentUser] = Depends(get_optional_current_user)" in source
    assert "DashboardOverviewService().get_market_intelligence_overview()" in source
