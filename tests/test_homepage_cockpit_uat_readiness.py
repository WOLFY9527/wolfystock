# -*- coding: utf-8 -*-
"""Focused tests for the full homepage cockpit UAT readiness contract."""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

import pytest

from src.services.homepage_uat_readiness_service import HomepageUatReadinessService


FIXED_AS_OF = "2026-06-15T09:30:00Z"
EXPECTED_TOP_LEVEL_KEYS = [
    "status",
    "asOf",
    "checks",
    "cockpitModules",
    "moduleSummary",
    "summary",
    "noAdviceDisclosure",
    "dataQuality",
]
EXPECTED_CHECK_KEYS = [
    "contract_shape",
    "cockpit_module_coverage",
    "sample_proxy_boundary",
    "public_copy_boundary",
    "serialization_readiness",
    "public_display_readiness",
    "data_integration_readiness",
    "missing_evidence_categories",
    "uat_checklist_items",
    "qa_evidence_record",
]
EXPECTED_MODULES = [
    ("T-1589", "daily_market_brief"),
    ("T-1590", "risk_regime"),
    ("T-1591", "cross_asset_indicators"),
    ("T-1592", "event_impact_map"),
    ("T-1593", "driver_chain"),
    ("T-1594", "theme_capital_flow"),
    ("T-1595", "research_priorities"),
    ("T-1596", "evidence_quality"),
    ("T-1597", "rates_pricing"),
    ("T-1598", "volatility_positioning"),
    ("T-1599", "liquidity_credit"),
    ("T-1600", "market_breadth"),
    ("T-1601", "after_close_developments"),
    ("T-1602", "scenario_watchlist"),
    ("T-1603", "earnings_catalysts"),
    ("T-1604", "geopolitical_commodity_risk"),
    ("T-1605", "ai_capex_infrastructure"),
    ("T-1606", "policy_regulation_watch"),
    ("T-1607", "style_leadership_rotation"),
    ("T-1608", "pre_session_research_checklist"),
]
ALLOWED_CHECK_STATUSES = {"pass", "review", "blocked", "no_evidence"}
ALLOWED_OWNER_AREAS = {"contract", "frontend_ui", "data_quality", "copy", "qa", "integration"}
ALLOWED_MODULE_READINESS = {"ready", "review", "blocked", "no_evidence"}
ALLOWED_DATA_INTEGRATION = {
    "not_wired_current_data",
    "static_contract_only",
    "proxy_only",
    "no_evidence",
}


def _build_payload() -> dict[str, Any]:
    return HomepageUatReadinessService().build_checklist(as_of=FIXED_AS_OF)


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        found: list[str] = []
        for item in value.values():
            found.extend(_string_values(item))
        return found
    if isinstance(value, list):
        found = []
        for item in value:
            found.extend(_string_values(item))
        return found
    return []


def test_cockpit_readiness_contract_serializes_full_module_set() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["status"] == "review"
    assert payload["asOf"] == FIXED_AS_OF
    assert payload["noAdviceDisclosure"] == "本清单仅用于首页模块验收与公开观察边界复核，不作为个性化决策依据。"

    checks = payload["checks"]
    assert [check["key"] for check in checks] == EXPECTED_CHECK_KEYS
    assert all(set(check) == {"key", "label", "status", "publicMessage", "ownerArea", "required"} for check in checks)

    modules = payload["cockpitModules"]
    assert [(module["taskId"], module["key"]) for module in modules] == EXPECTED_MODULES
    assert all(module["uatReviewable"] is True for module in modules)
    assert all(module["serializationReadiness"] == "ready" for module in modules)
    assert all(module["publicDisplayReadiness"] == "review" for module in modules)
    assert all(module["dataIntegrationReadiness"] == "not_wired_current_data" for module in modules)


def test_cockpit_readiness_declares_sample_proxy_no_evidence_boundaries() -> None:
    payload = _build_payload()
    modules = payload["cockpitModules"]
    by_key = {module["key"]: module for module in modules}
    evidence_boundaries = {module["evidenceBoundary"] for module in modules}

    assert {"sample_proxy", "proxy_only", "proxy_no_evidence_mix", "static_contract", "placeholder"} <= evidence_boundaries
    assert by_key["theme_capital_flow"]["evidenceBoundary"] == "proxy_only"
    assert by_key["rates_pricing"]["evidenceBoundary"] == "proxy_only"
    assert by_key["market_breadth"]["evidenceBoundary"] == "proxy_no_evidence_mix"
    assert by_key["after_close_developments"]["evidenceBoundary"] == "sample_proxy"
    assert by_key["earnings_catalysts"]["evidenceBoundary"] == "sample_proxy"
    assert by_key["ai_capex_infrastructure"]["evidenceBoundary"] == "sample_proxy"
    assert by_key["event_impact_map"]["evidenceBoundary"] == "placeholder"

    for module in modules:
        assert module["missingEvidenceCategories"], module["key"]
        assert module["uatChecklistItems"], module["key"]
        assert "current_data_feed" in module["missingEvidenceCategories"]
        assert "confirm_boundary_labels_visible" in module["uatChecklistItems"]


def test_cockpit_readiness_statuses_and_summary_are_bounded() -> None:
    payload = _build_payload()

    assert payload["status"] in ALLOWED_CHECK_STATUSES
    assert payload["moduleSummary"] == {
        "totalModules": 20,
        "reviewableModules": 20,
        "notWiredDataModules": 20,
        "sampleProxyOrNoEvidenceModules": 20,
        "publicMessage": "20 个首页 cockpit 模块可做公开验收复核；所有模块仍停留在静态、样本、代理或暂无证据边界。",
    }
    assert payload["dataQuality"] == {
        "status": "review",
        "label": "需人工复核",
        "publicMessage": "清单为静态合同，只描述验收边界、缺口类别与数据接入准备度。",
    }

    for check in payload["checks"]:
        assert check["status"] in ALLOWED_CHECK_STATUSES
        assert check["ownerArea"] in ALLOWED_OWNER_AREAS
        assert isinstance(check["required"], bool)

    for module in payload["cockpitModules"]:
        assert module["serializationReadiness"] in ALLOWED_MODULE_READINESS
        assert module["publicDisplayReadiness"] in ALLOWED_MODULE_READINESS
        assert module["dataIntegrationReadiness"] in ALLOWED_DATA_INTEGRATION


def test_cockpit_readiness_json_round_trips_without_internal_or_action_copy() -> None:
    payload = _build_payload()

    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert json.loads(serialized) == payload

    all_public_values = "\n".join(_string_values(payload)).lower()
    for forbidden in [
        "买入",
        "卖出",
        "下单",
        "立即交易",
        "交易信号",
        "交易指令",
        "交易建议",
        "交易执行",
        "投资建议",
        "止损",
        "止盈",
        "目标价",
        "收益预测",
        "buy now",
        "sell now",
        "place order",
        "trading signal",
        "trading advice",
        "trade execution",
        "investment advice",
        "target price",
        "recommendation",
        "traceback",
        "provider",
        "fallback",
        "cache",
        "reasoncode",
        "trustlevel",
        "sourcetype",
        "token",
        "sessionid",
        "session id",
        "apikey",
        "secret",
        "cookie",
        "debug",
        "raw",
        "internal.example",
        "/tmp/",
    ]:
        assert forbidden.lower() not in all_public_values


def test_cockpit_readiness_is_deterministic_with_fixed_timestamp() -> None:
    service = HomepageUatReadinessService()

    first = service.build_checklist(as_of=FIXED_AS_OF)
    second = service.build_checklist(as_of=FIXED_AS_OF)

    assert first == second


@pytest.mark.parametrize(
    "module_key",
    [key for _, key in EXPECTED_MODULES],
)
def test_each_cockpit_module_has_public_uat_review_items(module_key: str) -> None:
    module = {item["key"]: item for item in _build_payload()["cockpitModules"]}[module_key]

    assert module["reviewScope"] == [
        "public_serialization",
        "public_copy_boundary",
        "display_state_labels",
        "missing_evidence_disclosure",
    ]
    assert module["uatChecklistItems"] == [
        "confirm_public_fields_render",
        "confirm_boundary_labels_visible",
        "confirm_missing_evidence_copy",
        "record_uat_evidence",
    ]
