# -*- coding: utf-8 -*-
"""Focused tests for the standalone homepage daily market brief contract."""

from __future__ import annotations

import json

from src.services.homepage_daily_market_brief_service import (
    DAILY_MARKET_BRIEF_SCHEMA_VERSION,
    HomepageDailyMarketBriefService,
)


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "sessionLabel",
    "headline",
    "marketNarrative",
    "keyDrivers",
    "riskTone",
    "indexSummary",
    "breadthSummary",
    "liquiditySummary",
    "volatilitySummary",
    "ratesSummary",
    "dollarSummary",
    "crossAssetSummary",
    "todayWatchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]

ALLOWED_EVIDENCE_QUALITY = {"证据整理", "需要复核", "证据增强", "证据不足"}
ALLOWED_DATA_QUALITY = {"研究支持", "需要复核", "证据增强", "证据不足"}

FORBIDDEN_COPY_MARKERS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "止损",
    "止盈",
    "目标价",
    "收益预测",
    "交易指令",
    "交易建议",
    "AI推荐",
    "智能选股",
    "broker",
    "order",
    "trade execution",
    "buy now",
    "sell now",
    "target price",
    "stop loss",
    "take profit",
)

FORBIDDEN_DIAGNOSTIC_MARKERS = (
    "traceback",
    "provider",
    "token",
    "session_id",
    "secret",
    "api_key",
    "apikey",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "raw",
    "debug",
    "http://",
    "https://",
    "/users/",
    "/tmp/",
)


def _build_payload() -> dict[str, object]:
    return HomepageDailyMarketBriefService().build_daily_market_brief(
        as_of="2026-06-15T09:30:00Z",
    )


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_daily_market_brief_returns_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == DAILY_MARKET_BRIEF_SCHEMA_VERSION
    assert payload["asOf"] == "2026-06-15T09:30:00Z"
    assert payload["sessionLabel"] == "今日重点观察"
    assert payload["evidenceQuality"] == "证据整理"
    assert payload["dataQuality"] == "研究支持"


def test_daily_market_brief_output_is_deterministic() -> None:
    service = HomepageDailyMarketBriefService()

    first = service.build_daily_market_brief(as_of="2026-06-15T09:30:00Z")
    second = service.build_daily_market_brief(as_of="2026-06-15T09:30:00Z")

    assert first == second


def test_daily_market_brief_required_fields_are_present_and_non_empty() -> None:
    payload = _build_payload()

    for key in EXPECTED_TOP_LEVEL_KEYS:
        assert key in payload
        assert payload[key] not in ("", [], None)

    assert isinstance(payload["keyDrivers"], list)
    assert len(payload["keyDrivers"]) == 4
    assert isinstance(payload["todayWatchPoints"], list)
    assert len(payload["todayWatchPoints"]) == 4
    assert isinstance(payload["indexSummary"], list)
    assert len(payload["indexSummary"]) == 3


def test_daily_market_brief_uses_safe_chinese_no_advice_disclosure() -> None:
    payload = _build_payload()

    disclosure = str(payload["noAdviceDisclosure"])
    assert "市场观察" in disclosure
    assert "证据整理" in disclosure
    assert "研究支持" in disclosure
    assert "个性化决策" in disclosure


def test_daily_market_brief_excludes_forbidden_copy_markers() -> None:
    serialized = _serialized(_build_payload())

    leaked = [marker for marker in FORBIDDEN_COPY_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_daily_market_brief_excludes_internal_diagnostics_and_raw_urls() -> None:
    serialized = _serialized(_build_payload())

    leaked = [marker for marker in FORBIDDEN_DIAGNOSTIC_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_daily_market_brief_quality_fields_are_bounded_enums() -> None:
    payload = _build_payload()

    assert payload["evidenceQuality"] in ALLOWED_EVIDENCE_QUALITY
    assert payload["dataQuality"] in ALLOWED_DATA_QUALITY
