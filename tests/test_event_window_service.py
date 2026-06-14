# -*- coding: utf-8 -*-
"""Focused tests for the standalone homepage event-window summary contract."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = REPO_ROOT / "src/services/event_window_service.py"
SCHEMA_PATH = REPO_ROOT / "api/v1/schemas/event_window.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "yfinance",
    "src.services.event_radar_service",
    "src.services.dashboard_overview_service",
    "src.services.official_macro",
    "src.services.search_service",
    "src.services.analysis_service",
)
FORBIDDEN_ADVICE_TERMS = (
    "buy now",
    "sell now",
    "add position",
    "reduce position",
    "clear position",
    "place order",
    "submit order",
    "trade execution",
    "stop-loss",
    "stop loss",
    "take-profit",
    "take profit",
    "target price",
    "predicted return",
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "下单",
    "立即交易",
    "止损",
    "止盈",
    "目标价",
)
FORBIDDEN_LEAK_TERMS = (
    "traceback",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "rawpayload",
    "providerpayload",
    "providerroute",
    "provider_url",
    "token",
    "session",
    "api_key",
    "apikey",
    "secret",
    "http://",
    "https://",
    "/users/",
)


def _schema_module():
    if importlib.util.find_spec("api.v1.schemas.event_window") is None:
        pytest.fail("api.v1.schemas.event_window is missing")
    return importlib.import_module("api.v1.schemas.event_window")


def _service_module():
    if importlib.util.find_spec("src.services.event_window_service") is None:
        pytest.fail("src.services.event_window_service is missing")
    return importlib.import_module("src.services.event_window_service")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_event_window_default_summary_is_no_evidence_and_safe() -> None:
    service_module = _service_module()

    snapshot = service_module.EventWindowService().build_summary().model_dump(mode="json")

    assert list(snapshot.keys()) == [
        "status",
        "asOf",
        "windows",
        "sourceStatus",
        "dataQuality",
        "noAdviceDisclosure",
    ]
    assert snapshot["status"] == "no_evidence"
    assert snapshot["asOf"] is None
    assert snapshot["windows"] == []
    assert snapshot["sourceStatus"] == "no_evidence"
    assert snapshot["dataQuality"] == {
        "state": "no_evidence",
        "label": "暂无证据",
        "available": False,
    }
    assert "not personalized financial advice" in snapshot["noAdviceDisclosure"].lower()


def test_safe_event_windows_normalize_correctly() -> None:
    schema_module = _schema_module()
    service_module = _service_module()

    snapshot = service_module.EventWindowService().build_summary(
        {
            "asOf": "2026-06-14T09:30:00Z",
            "windows": [
                {
                    "id": " earnings-nvda-q2 ",
                    "title": "NVDA earnings review window",
                    "category": "EARNINGS",
                    "windowState": "starts soon",
                    "startsAt": "2026-08-21T20:00:00Z",
                    "endsAt": "2026-08-22T20:00:00Z",
                    "relatedSymbols": [" nvda ", "NVDA", "aapl", "msft", "googl"],
                    "relatedThemes": [" AI ", "earnings cluster", "AI", "semiconductor cycle", "overflow"],
                    "reviewReason": "Earnings window requires research review before and after the release.",
                    "dataQuality": "available",
                }
            ],
        }
    ).model_dump(mode="json")

    assert snapshot["status"] == "ready"
    assert snapshot["sourceStatus"] == "ready"
    assert snapshot["asOf"] == "2026-06-14T09:30:00Z"
    assert snapshot["dataQuality"] == {
        "state": "ready",
        "label": "正常",
        "available": True,
    }
    assert snapshot["windows"][0] == {
        "id": "earnings-nvda-q2",
        "title": "NVDA earnings review window",
        "category": schema_module.EventWindowCategory.EARNINGS.value,
        "windowState": schema_module.EventWindowState.UPCOMING.value,
        "startsAt": "2026-08-21T20:00:00Z",
        "endsAt": "2026-08-22T20:00:00Z",
        "relatedSymbols": ["NVDA", "AAPL", "MSFT", "GOOGL"],
        "relatedThemes": ["ai", "earnings_cluster", "semiconductor_cycle", "overflow"],
        "reviewReason": "Earnings window requires research review before and after the release.",
        "dataQuality": {
            "state": "ready",
            "label": "正常",
            "available": True,
        },
    }


def test_unsafe_titles_and_reasons_are_sanitized() -> None:
    service_module = _service_module()

    snapshot = service_module.EventWindowService().build_summary(
        {
            "asOf": "2026-06-14T09:30:00Z",
            "windows": [
                {
                    "id": "fomc-window",
                    "title": "Buy NVDA now",
                    "category": "policy",
                    "windowState": "active",
                    "startsAt": "2026-06-18T18:00:00Z",
                    "endsAt": "2026-06-19T18:00:00Z",
                    "relatedSymbols": ["NVDA", "token"],
                    "relatedThemes": ["policy", "https://internal.example"],
                    "reviewReason": "Traceback: api_key=123, session=abc, immediate trade execution.",
                    "dataQuality": "trusted_source",
                }
            ],
        }
    ).model_dump(mode="json")

    window = snapshot["windows"][0]
    assert window["title"] == "Event window needs review."
    assert window["reviewReason"] == "Review event window context."
    assert window["relatedSymbols"] == ["NVDA"]
    assert window["relatedThemes"] == ["policy"]
    assert window["dataQuality"] == {
        "state": "review",
        "label": "复核",
        "available": True,
    }


def test_related_symbols_and_themes_are_bounded() -> None:
    service_module = _service_module()

    snapshot = service_module.EventWindowService().build_summary(
        {
            "windows": [
                {
                    "id": "macro-window",
                    "title": "Macro event window",
                    "category": "macro",
                    "windowState": "upcoming",
                    "startsAt": "2026-07-01T12:30:00Z",
                    "endsAt": "2026-07-01T13:30:00Z",
                    "relatedSymbols": ["SPY", "QQQ", "IWM", "DIA", "TLT", "QQQ"],
                    "relatedThemes": ["rates", "usd", "liquidity", "inflation", "breadth", "rates"],
                    "reviewReason": "Macro release may require cross-asset review.",
                    "dataQuality": "ready",
                }
            ]
        }
    ).model_dump(mode="json")

    assert snapshot["windows"][0]["relatedSymbols"] == ["SPY", "QQQ", "IWM", "DIA"]
    assert snapshot["windows"][0]["relatedThemes"] == ["rates", "usd", "liquidity", "inflation"]


def test_event_window_output_does_not_leak_internal_diagnostics_or_secrets() -> None:
    service_module = _service_module()

    snapshot = service_module.EventWindowService().build_summary(
        {
            "asOf": "2026-06-14T09:30:00Z",
            "sourceStatus": {"summary": "providerroute leaked"},
            "providerUrl": "https://internal.example/provider",
            "token": "secret-token",
            "windows": [
                {
                    "id": "macro-window",
                    "title": "FOMC review window",
                    "category": "policy",
                    "windowState": "active",
                    "startsAt": "2026-06-18T18:00:00Z",
                    "endsAt": "2026-06-19T18:00:00Z",
                    "relatedSymbols": ["QQQ", "session-unsafe"],
                    "relatedThemes": ["rates", "fallback"],
                    "reviewReason": "Review event window context.",
                    "dataQuality": "provider_timeout",
                    "rawPayload": {"api_key": "123"},
                }
            ],
        }
    ).model_dump(mode="json")

    serialized = _serialized(snapshot)
    for term in FORBIDDEN_LEAK_TERMS:
        assert term not in serialized


def test_event_window_output_does_not_ship_trading_advice_terms() -> None:
    service_module = _service_module()

    snapshot = service_module.EventWindowService().build_summary(
        {
            "windows": [
                {
                    "id": "watchlist-window",
                    "title": "Sell now before CPI",
                    "category": "watchlist",
                    "windowState": "upcoming",
                    "startsAt": "2026-06-20T12:30:00Z",
                    "endsAt": "2026-06-20T14:00:00Z",
                    "relatedSymbols": ["TSLA"],
                    "relatedThemes": ["watchlist"],
                    "reviewReason": "Add position before the release and place order immediately.",
                    "dataQuality": "ready",
                }
            ]
        }
    ).model_dump(mode="json")

    serialized = _serialized(snapshot)
    for term in FORBIDDEN_ADVICE_TERMS:
        assert term not in serialized


def test_service_has_no_external_or_provider_imports() -> None:
    if not SERVICE_PATH.exists():
        pytest.fail("src/services/event_window_service.py is missing")
    if not SCHEMA_PATH.exists():
        pytest.fail("api/v1/schemas/event_window.py is missing")

    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    for module_name in imported_modules:
        assert not module_name.startswith(FORBIDDEN_IMPORT_PREFIXES)
