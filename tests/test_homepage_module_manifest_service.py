# -*- coding: utf-8 -*-
"""Focused tests for the standalone homepage module manifest contract."""

from __future__ import annotations

import json

import pytest

from src.services.homepage_module_manifest_service import HomepageModuleManifestService


EXPECTED_MODULE_KEYS = [
    "market_pulse",
    "money_flow",
    "sector_theme_strength",
    "event_radar",
    "personal_summary",
    "research_queue",
    "public_data_quality",
    "dashboard_overview",
]
ALLOWED_TOP_LEVEL_STATUSES = {"ready", "partial", "no_evidence", "unavailable"}
ALLOWED_AVAILABILITY = {"ready", "scaffold", "no_evidence", "unavailable"}
ALLOWED_INTEGRATION = {"standalone", "wired", "pending", "unavailable"}
ALLOWED_PUBLIC_STATUS = {"public", "gated", "private_beta", "internal_only"}
ALLOWED_DATA_QUALITY_STATES = {"ready", "partial", "no_evidence", "unavailable"}


def _build_manifest_payload() -> dict[str, object]:
    service = HomepageModuleManifestService()
    return service.build_manifest(as_of="2026-06-14T09:30:00Z")


def _dump_manifest(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_default_manifest_serializes_all_expected_modules() -> None:
    payload = _build_manifest_payload()

    assert payload["status"] == "ready"
    assert payload["asOf"] == "2026-06-14T09:30:00Z"
    assert payload["noAdviceDisclosure"] == "仅供模块可用性与接入准备度观察，不构成投资建议或交易指令。"

    modules = payload["modules"]
    assert isinstance(modules, list)
    assert [module["key"] for module in modules] == EXPECTED_MODULE_KEYS

    by_key = {module["key"]: module for module in modules}
    assert by_key["market_pulse"]["integrationStatus"] == "standalone"
    assert by_key["money_flow"]["integrationStatus"] == "standalone"
    assert by_key["sector_theme_strength"]["integrationStatus"] == "standalone"
    assert by_key["event_radar"]["integrationStatus"] == "standalone"
    assert by_key["personal_summary"]["integrationStatus"] == "standalone"
    assert by_key["research_queue"]["integrationStatus"] == "standalone"
    assert by_key["public_data_quality"]["integrationStatus"] == "standalone"
    assert by_key["dashboard_overview"]["integrationStatus"] == "wired"
    assert by_key["personal_summary"]["publicStatus"] == "gated"

    data_quality = payload["dataQuality"]
    assert data_quality == {
        "state": "ready",
        "label": "正常",
        "summary": "当前模块 manifest 仅描述公开状态、接入状态与复核点，不包含交易建议或内部诊断。",
    }


def test_manifest_statuses_are_bounded() -> None:
    payload = _build_manifest_payload()

    assert payload["status"] in ALLOWED_TOP_LEVEL_STATUSES
    assert payload["dataQuality"]["state"] in ALLOWED_DATA_QUALITY_STATES
    for module in payload["modules"]:
        assert module["availability"] in ALLOWED_AVAILABILITY
        assert module["integrationStatus"] in ALLOWED_INTEGRATION
        assert module["publicStatus"] in ALLOWED_PUBLIC_STATUS
        assert module["dataQuality"]["state"] in ALLOWED_DATA_QUALITY_STATES


@pytest.mark.parametrize(
    "forbidden",
    [
        "买入",
        "卖出",
        "下单",
        "交易信号",
        "trading signal",
        "buy now",
        "sell now",
        "target price",
        "止损",
        "止盈",
    ],
)
def test_manifest_is_not_presented_as_trading_signal(forbidden: str) -> None:
    dumped = _dump_manifest(_build_manifest_payload()).lower()
    assert forbidden.lower() not in dumped


@pytest.mark.parametrize(
    "forbidden",
    [
        "traceback",
        "provider",
        "token",
        "session",
        "secret",
        "apiKey",
        "reasonCode",
        "trustLevel",
        "sourceType",
        "raw",
        "debug",
        "internal.example",
        "cookie",
        "/tmp/",
    ],
)
def test_manifest_does_not_leak_internal_diagnostics_or_secrets(forbidden: str) -> None:
    dumped = _dump_manifest(_build_manifest_payload()).lower()
    assert forbidden.lower() not in dumped


@pytest.mark.parametrize(
    "forbidden",
    [
        "打开",
        "进入",
        "跳转",
        "导航",
        "入口",
        "launch",
        "launcher",
        "navigate",
        "open module",
    ],
)
def test_manifest_avoids_navigation_or_launcher_semantics(forbidden: str) -> None:
    dumped = _dump_manifest(_build_manifest_payload()).lower()
    assert forbidden.lower() not in dumped
