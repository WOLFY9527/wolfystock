# -*- coding: utf-8 -*-
"""Focused tests for the public-facing data quality summary contract."""

from __future__ import annotations

import json

import pytest

from src.services.public_data_quality_service import build_public_data_quality_summary


def _dump_summary(payload: dict[str, object]) -> str:
    summary = build_public_data_quality_summary(payload)
    return json.dumps(summary.model_dump(by_alias=True), ensure_ascii=False, sort_keys=True)


def test_public_data_quality_summary_defaults_to_normal_ready_state() -> None:
    summary = build_public_data_quality_summary({})

    assert summary.model_dump(by_alias=True) == {
        "status": "ready",
        "label": "正常",
        "suitableForResearchObservation": True,
        "asOf": None,
        "updatedModules": [],
        "affectedModules": [],
        "message": "核心模块已更新，适合研究观察",
        "noAdviceDisclosure": "仅供研究观察，不构成投资建议",
    }


@pytest.mark.parametrize(
    ("payload", "expected_status", "expected_label", "expected_suitable"),
    [
        ({"status": "delayed"}, "delayed", "数据延迟", True),
        ({"status": "cached"}, "cached", "使用缓存", True),
        ({"status": "partial"}, "partial", "部分缺失", True),
        ({"status": "no_evidence"}, "no_evidence", "暂无证据", False),
        ({"status": "unavailable"}, "unavailable", "暂不可用", False),
    ],
)
def test_public_data_quality_summary_uses_bounded_abnormal_labels(
    payload: dict[str, object],
    expected_status: str,
    expected_label: str,
    expected_suitable: bool,
) -> None:
    summary = build_public_data_quality_summary(payload)

    assert summary.status == expected_status
    assert summary.label == expected_label
    assert summary.suitable_for_research_observation is expected_suitable


def test_public_data_quality_summary_sanitizes_module_names_for_consumers() -> None:
    summary = build_public_data_quality_summary(
        {
            "status": "partial",
            "updatedModules": ["home", "market_overview", "provider_url"],
            "affectedModules": ["scanner", "sourceType", "https://internal.example", "rotation_radar"],
        }
    )

    assert summary.updated_modules == ["首页", "市场总览"]
    assert summary.affected_modules == ["扫描观察", "轮动观察"]


def test_public_data_quality_summary_does_not_leak_internal_diagnostics() -> None:
    dumped = _dump_summary(
        {
            "status": "cached",
            "asOf": "2026-06-14T09:30:00Z",
            "updatedModules": ["home"],
            "affectedModules": ["provider_error", "scanner"],
            "provider": "secret-provider",
            "providerUrl": "https://internal.example/provider",
            "traceback": "Traceback: secret stack",
            "rawException": "provider timeout",
            "fallbackFlag": True,
            "trustLevel": "high",
            "reasonCode": "internal_reason",
            "sourceType": "official_public",
            "rawConfidence": 0.91,
            "filesystemPath": "/tmp/private/file.json",
            "token": "abc123",
            "sessionId": "session-123",
            "apiKey": "secret-key",
        }
    )

    for forbidden in (
        "secret-provider",
        "internal.example",
        "Traceback",
        "provider timeout",
        "trustLevel",
        "reasonCode",
        "sourceType",
        "rawConfidence",
        "/tmp/private/file.json",
        "abc123",
        "session-123",
        "secret-key",
        "provider_error",
    ):
        assert forbidden not in dumped


def test_public_data_quality_summary_avoids_trading_advice_terms() -> None:
    dumped = _dump_summary(
        {
            "status": "ready",
            "updatedModules": ["home", "scanner"],
        }
    )

    for forbidden in ("买入", "卖出", "下单", "交易指令", "目标价", "止损", "止盈", "仓位", "保证收益"):
        assert forbidden not in dumped
