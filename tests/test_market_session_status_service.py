# -*- coding: utf-8 -*-
"""Focused tests for the standalone market session status contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from api.v1.schemas.market_session_status import (
    MARKET_SESSION_NO_ADVICE_DISCLOSURE,
    MarketSessionStatusContract,
)
from src.services.market_session_status_service import MarketSessionStatusService


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = REPO_ROOT / "src/services/market_session_status_service.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "yfinance",
    "src.services.market_cache",
    "src.services.market_overview_service",
    "src.services.market_overview_",
    "src.services.official_macro",
)
FORBIDDEN_TERMS = (
    "buy",
    "sell",
    "trade",
    "order",
    "target-price",
    "stop-loss",
    "take-profit",
    "交易建议",
    "下单",
    "止损",
    "止盈",
    "traceback",
    "exception",
    "provider",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "token",
    "sessionid",
    "api key",
    "secret",
)


def _service_imports() -> set[str]:
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _dump_status(payload: dict[str, object] | None = None) -> str:
    contract = MarketSessionStatusService().build_status(payload)
    return json.dumps(contract.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


def test_market_session_status_defaults_to_safe_unknown_shape() -> None:
    payload = MarketSessionStatusService().build_status().model_dump(mode="json")

    assert list(payload.keys()) == [
        "status",
        "market",
        "sessionState",
        "label",
        "asOf",
        "timezone",
        "message",
        "dataQuality",
        "noAdviceDisclosure",
    ]
    assert payload == {
        "status": "unknown",
        "market": "unknown",
        "sessionState": "unknown",
        "label": "状态未知",
        "asOf": None,
        "timezone": "UTC",
        "message": "当前缺少可靠交易时段信号，仅展示安全未知状态",
        "dataQuality": "unknown",
        "noAdviceDisclosure": MARKET_SESSION_NO_ADVICE_DISCLOSURE,
    }
    assert MarketSessionStatusContract.model_validate(payload).sessionState == "unknown"


@pytest.mark.parametrize(
    ("raw_state", "expected_state", "expected_label"),
    [
        ("regular_open", "regular", "正常交易"),
        ("pre-market", "premarket", "盘前"),
        ("afterhours", "after_hours", "盘后"),
        ("market_closed", "closed", "休市"),
        ("holiday_like", "holiday", "非交易日"),
    ],
)
def test_market_session_status_normalizes_safe_session_states(
    raw_state: str,
    expected_state: str,
    expected_label: str,
) -> None:
    payload = MarketSessionStatusService().build_status(
        {
            "market": "nasdaq",
            "sessionState": raw_state,
            "asOf": "2026-06-14T09:30:00Z",
        }
    ).model_dump(mode="json")

    assert payload["status"] == "ready"
    assert payload["market"] == "US"
    assert payload["sessionState"] == expected_state
    assert payload["label"] == expected_label
    assert payload["asOf"] == "2026-06-14T09:30:00Z"
    assert payload["timezone"] == "US/Eastern"
    assert payload["dataQuality"] == "provided"


def test_market_session_status_sanitizes_dirty_labels_and_diagnostics() -> None:
    dumped = _dump_status(
        {
            "market": "us",
            "sessionState": "after-hours",
            "status": "provider_down",
            "label": "BUY NOW",
            "message": "traceback token=abc123",
            "providerUrl": "https://internal.example/provider",
            "reasonCode": "provider_timeout",
            "debugRef": "debug-secret",
            "sessionId": "session-123",
            "apiKey": "secret-key",
            "secret": "top-secret",
            "timezone": "America/New_York",
        }
    )

    assert '"sessionState": "after_hours"' in dumped
    assert '"label": "盘后"' in dumped
    assert '"message": "市场处于盘后时段，仅供状态展示"' in dumped
    assert '"status": "ready"' in dumped
    assert '"timezone": "US/Eastern"' in dumped
    for forbidden in (
        "BUY NOW",
        "traceback token=abc123",
        "internal.example",
        "provider_timeout",
        "debug-secret",
        "session-123",
        "secret-key",
        "top-secret",
    ):
        assert forbidden not in dumped


def test_market_session_status_output_avoids_trading_advice_terms() -> None:
    dumped = _dump_status({"market": "us", "sessionState": "regular"})
    dumped_lower = dumped.lower()

    for forbidden in FORBIDDEN_TERMS:
        assert forbidden.lower() not in dumped_lower


def test_market_session_status_does_not_leak_internal_diagnostics_or_secrets() -> None:
    dumped = _dump_status(
        {
            "market": "provider",
            "sessionState": "premarket",
            "asOf": "https://internal.example/as-of?token=abc123",
            "timezone": "token=abc123",
            "traceback": "Traceback: RuntimeError",
            "rawException": "provider timeout",
            "provider": "secret-provider",
            "filesystemPath": "/tmp/private/file.json",
            "cookie": "cookie-value",
        }
    )

    assert '"market": "unknown"' in dumped
    assert '"sessionState": "premarket"' in dumped
    assert '"asOf": null' in dumped
    assert '"timezone": "UTC"' in dumped
    for forbidden in (
        "internal.example",
        "abc123",
        "Traceback",
        "provider timeout",
        "secret-provider",
        "/tmp/private/file.json",
        "cookie-value",
    ):
        assert forbidden not in dumped


def test_market_session_status_service_is_inert_and_does_not_import_network_or_providers() -> None:
    imports = _service_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)
