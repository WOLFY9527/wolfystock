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


def test_public_data_quality_summary_aggregates_all_ready_module_states() -> None:
    summary = build_public_data_quality_summary(
        {
            "moduleStates": [
                {"module": "home", "status": "ready"},
                {"moduleName": "market_overview", "state": "fresh"},
                {"name": "scanner", "qualityState": "updated"},
            ]
        }
    )

    assert summary.status == "ready"
    assert summary.label == "正常"
    assert summary.suitable_for_research_observation is True
    assert summary.updated_modules == ["首页", "市场总览", "扫描观察"]
    assert summary.affected_modules == []


def test_public_data_quality_summary_aggregates_bounded_abnormal_module_states() -> None:
    summary = build_public_data_quality_summary(
        {
            "moduleStates": [
                {"module": "home", "status": "ready"},
                {"module": "scanner", "status": "cached"},
                {"module": "rotation_radar", "status": "delayed"},
            ]
        }
    )

    assert summary.status == "delayed"
    assert summary.label == "数据延迟"
    assert summary.suitable_for_research_observation is True
    assert summary.updated_modules == ["首页"]
    assert summary.affected_modules == ["扫描观察", "轮动观察"]


@pytest.mark.parametrize(
    ("payload", "expected_status", "expected_modules"),
    [
        (
            {
                "moduleStates": [
                    {"module": "home", "status": "ready"},
                    {"module": "scanner", "status": "no_evidence"},
                ]
            },
            "no_evidence",
            ["扫描观察"],
        ),
        (
            {
                "status": "ready",
                "moduleStates": [
                    {"module": "home", "status": "ready"},
                    {"module": "scanner", "status": "unavailable"},
                ],
            },
            "unavailable",
            ["扫描观察"],
        ),
    ],
)
def test_public_data_quality_summary_uses_conservative_module_state_status(
    payload: dict[str, object],
    expected_status: str,
    expected_modules: list[str],
) -> None:
    summary = build_public_data_quality_summary(payload)

    assert summary.status == expected_status
    assert summary.suitable_for_research_observation is False
    assert summary.affected_modules == expected_modules


def test_public_data_quality_summary_sanitizes_affected_modules_from_module_states() -> None:
    summary = build_public_data_quality_summary(
        {
            "moduleStates": [
                {"module": "scanner", "status": "cached"},
                {"module": "rotation_radar", "status": "delayed"},
                {"module": "https://internal.example/private", "status": "unavailable"},
                {"module": "provider_token", "status": "no_evidence"},
                {"module": "rotation radar", "status": "cached"},
            ]
        }
    )

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


def test_public_data_quality_summary_module_states_do_not_leak_internal_diagnostics() -> None:
    dumped = _dump_summary(
        {
            "moduleStates": [
                {
                    "module": "scanner",
                    "status": "cached",
                    "provider": "secret-provider",
                    "providerUrl": "https://internal.example/provider",
                    "traceback": "Traceback: secret stack",
                    "rawException": "provider timeout",
                    "token": "abc123",
                    "sessionId": "session-123",
                },
                {
                    "module": "home",
                    "status": "ready",
                    "apiKey": "secret-key",
                    "filesystemPath": "/tmp/private/file.json",
                },
            ]
        }
    )

    for forbidden in (
        "secret-provider",
        "internal.example",
        "Traceback",
        "provider timeout",
        "abc123",
        "session-123",
        "secret-key",
        "/tmp/private/file.json",
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
