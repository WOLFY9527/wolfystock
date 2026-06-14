# -*- coding: utf-8 -*-
"""Focused tests for deterministic homepage demo payload fixtures."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from src.services.homepage_demo_payload_service import (
    DEGRADED_EXAMPLE,
    HAPPY_PATH,
    HomepageDemoPayloadService,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = REPO_ROOT / "src" / "services" / "homepage_demo_payload_service.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "api.v1.endpoints",
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "src.auth",
    "src.services.market_cache",
    "src.services.dashboard_overview_service",
)
FORBIDDEN_TRADING_TERMS = (
    "buy now",
    "sell now",
    "place order",
    "submit order",
    "trade recommendation",
    "trading advice",
    "investment advice",
    "financial advice",
    "target price",
    "stop loss",
    "take profit",
    "guaranteed return",
    "guaranteed",
    "买入",
    "卖出",
    "下单",
    "立即交易",
    "投资建议",
    "交易指令",
    "目标价",
    "止损",
    "止盈",
    "保证收益",
)
FORBIDDEN_INTERNAL_MARKERS = (
    "traceback",
    "provider",
    "providerwired",
    "providerpayload",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "rawpayload",
    "token",
    "session",
    "secret",
    "api_key",
    "apikey",
    "debugref",
    "bearer ",
    "sk-",
    "/users/",
    "http://",
    "https://",
    "schemaversion",
    "proxymode",
)


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def _service_imports() -> set[str]:
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _assert_sample_marked(payload: dict[str, object], *, scenario: str, expected_status: str) -> None:
    assert payload["scenario"] == scenario
    assert payload["status"] == expected_status
    assert payload["sampleData"] is True
    assert payload["demoPayload"] is True
    assert payload["asOf"] == "2026-06-14T09:30:00Z"
    assert payload["demoDisclosure"] == "首页演示样例，仅用于界面联调与 UAT，不代表真实数据。"


def _assert_no_forbidden_terms(payload: dict[str, object]) -> None:
    serialized = _serialized(payload)
    advice_hits = [term for term in FORBIDDEN_TRADING_TERMS if term in serialized]
    leak_hits = [term for term in FORBIDDEN_INTERNAL_MARKERS if term in serialized]
    assert advice_hits == []
    assert leak_hits == []


def test_happy_path_payload_is_stable_and_sample_marked() -> None:
    service = HomepageDemoPayloadService()

    first = service.build_payload(HAPPY_PATH)
    second = service.build_payload(HAPPY_PATH)

    assert first == second
    assert set(first) == {
        "status",
        "scenario",
        "asOf",
        "sampleData",
        "demoPayload",
        "headline",
        "summary",
        "marketPulse",
        "moneyFlow",
        "eventRadar",
        "personalSummary",
        "researchQueue",
        "dataQuality",
        "demoDisclosure",
    }
    _assert_sample_marked(first, scenario=HAPPY_PATH, expected_status="ready")
    assert first["dataQuality"]["status"] == "ready"
    assert set(first["dataQuality"]["sections"].values()) == {"ready"}
    assert first["marketPulse"]["status"] == "ready"
    assert first["moneyFlow"]["status"] == "ready"
    assert first["eventRadar"]["freshness"] == "fresh"
    assert first["personalSummary"]["status"] == "ready"
    assert first["personalSummary"]["dataQuality"]["sampleData"] is True
    assert first["researchQueue"]["dataQuality"]["status"] == "ready"
    assert first["marketPulse"]["noAdviceDisclosure"] == first["demoDisclosure"]
    assert first["moneyFlow"]["noAdviceDisclosure"] == first["demoDisclosure"]


def test_degraded_example_payload_is_stable_and_sample_marked() -> None:
    service = HomepageDemoPayloadService()

    first = service.build_payload(DEGRADED_EXAMPLE)
    second = service.build_payload(DEGRADED_EXAMPLE)

    assert first == second
    _assert_sample_marked(first, scenario=DEGRADED_EXAMPLE, expected_status="partial")
    assert first["dataQuality"]["status"] == "delayed"
    assert first["dataQuality"]["sections"] == {
        "marketPulse": "delayed",
        "moneyFlow": "partial",
        "eventRadar": "delayed",
        "personalSummary": "partial",
        "researchQueue": "partial",
    }
    assert first["marketPulse"]["status"] == "partial"
    assert first["moneyFlow"]["status"] == "partial"
    assert first["eventRadar"]["freshness"] == "delayed"
    assert first["personalSummary"]["status"] == "partial"
    assert first["personalSummary"]["watchlistExceptions"]["items"]
    assert first["researchQueue"]["dataQuality"]["status"] == "partial"


def test_build_payloads_returns_both_scenarios_with_expected_defaults() -> None:
    payloads = HomepageDemoPayloadService().build_payloads()

    assert set(payloads) == {HAPPY_PATH, DEGRADED_EXAMPLE}
    assert payloads[HAPPY_PATH]["dataQuality"]["status"] == "ready"
    assert payloads[DEGRADED_EXAMPLE]["dataQuality"]["status"] != "ready"
    assert set(payloads[HAPPY_PATH]["dataQuality"]["sections"].values()) == {"ready"}
    assert "ready" not in set(payloads[DEGRADED_EXAMPLE]["dataQuality"]["sections"].values())


def test_payloads_avoid_forbidden_trading_language_and_internal_markers() -> None:
    service = HomepageDemoPayloadService()

    _assert_no_forbidden_terms(service.build_payload(HAPPY_PATH))
    _assert_no_forbidden_terms(service.build_payload(DEGRADED_EXAMPLE))


def test_service_stays_within_demo_only_backend_boundaries() -> None:
    imports = _service_imports()

    for forbidden_prefix in FORBIDDEN_IMPORT_PREFIXES:
        assert not any(
            module == forbidden_prefix or module.startswith(f"{forbidden_prefix}.")
            for module in imports
        )
