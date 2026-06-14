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
FORBIDDEN_PUBLIC_COPY = (
    "happy-path",
    "UAT",
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
    assert payload["demoDisclosure"] == "首页演示样例，仅用于公开界面联调，不代表真实数据。"


def _assert_demo_flags(payload: dict[str, object]) -> None:
    assert payload["sampleData"] is True
    assert payload["demoPayload"] is True


def _assert_no_forbidden_terms(payload: dict[str, object]) -> None:
    serialized = _serialized(payload)
    advice_hits = [term for term in FORBIDDEN_TRADING_TERMS if term in serialized]
    leak_hits = [term for term in FORBIDDEN_INTERNAL_MARKERS if term in serialized]
    public_copy_hits = [term.lower() for term in FORBIDDEN_PUBLIC_COPY if term.lower() in serialized]
    assert advice_hits == []
    assert leak_hits == []
    assert public_copy_hits == []


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
    for section in (
        first["marketPulse"],
        first["moneyFlow"],
        first["eventRadar"],
        first["personalSummary"],
        first["researchQueue"],
        first["dataQuality"],
    ):
        _assert_demo_flags(section)


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
    for section in (
        first["marketPulse"],
        first["moneyFlow"],
        first["eventRadar"],
        first["personalSummary"],
        first["researchQueue"],
        first["dataQuality"],
    ):
        _assert_demo_flags(section)


def test_build_payloads_returns_both_scenarios_with_expected_defaults() -> None:
    payloads = HomepageDemoPayloadService().build_payloads()

    assert set(payloads) == {HAPPY_PATH, DEGRADED_EXAMPLE}
    assert payloads[HAPPY_PATH]["dataQuality"]["status"] == "ready"
    assert payloads[DEGRADED_EXAMPLE]["dataQuality"]["status"] != "ready"
    assert set(payloads[HAPPY_PATH]["dataQuality"]["sections"].values()) == {"ready"}
    assert "ready" not in set(payloads[DEGRADED_EXAMPLE]["dataQuality"]["sections"].values())
    assert payloads[HAPPY_PATH]["moneyFlow"]["sourceStatus"]["status"] == "ready"
    assert payloads[DEGRADED_EXAMPLE]["moneyFlow"]["sourceStatus"]["status"] == "partial"


def test_happy_path_avoids_abnormal_default_states() -> None:
    payload = HomepageDemoPayloadService().build_payload(HAPPY_PATH)
    serialized = _serialized(payload)

    for forbidden_default in ("cached", "unavailable", "degraded", "sample_degraded"):
        assert forbidden_default not in serialized
    assert '"partial"' not in serialized
    assert '"no_evidence"' not in serialized


def test_nested_demo_contracts_are_consistently_demo_marked() -> None:
    service = HomepageDemoPayloadService()

    for scenario in (HAPPY_PATH, DEGRADED_EXAMPLE):
        payload = service.build_payload(scenario)
        for item in payload["eventRadar"]["items"]:
            _assert_demo_flags(item)
        for item in payload["researchQueue"]["items"]:
            _assert_demo_flags(item)

        personal_summary = payload["personalSummary"]
        _assert_demo_flags(personal_summary["portfolioSnapshot"])
        _assert_demo_flags(personal_summary["watchlistExceptions"])
        _assert_demo_flags(personal_summary["researchCoverage"])
        _assert_demo_flags(personal_summary["reviewQueue"])
        _assert_demo_flags(personal_summary["dataQuality"])
        for item in personal_summary["watchlistExceptions"]["items"]:
            _assert_demo_flags(item)
        for item in personal_summary["reviewQueue"]["items"]:
            _assert_demo_flags(item)

        money_flow = payload["moneyFlow"]
        _assert_demo_flags(money_flow["sourceStatus"])
        _assert_demo_flags(money_flow["dataQuality"])
        _assert_demo_flags(money_flow["styleBias"])
        _assert_demo_flags(money_flow["styleBias"]["dataQuality"])
        _assert_demo_flags(money_flow["offensiveDefensiveBias"])
        _assert_demo_flags(money_flow["offensiveDefensiveBias"]["dataQuality"])
        for item in money_flow["topInflows"]:
            _assert_demo_flags(item)
        for item in money_flow["topOutflows"]:
            _assert_demo_flags(item)


def test_money_flow_source_status_stays_public_and_demo_only() -> None:
    payloads = HomepageDemoPayloadService().build_payloads()

    happy_source_status = payloads[HAPPY_PATH]["moneyFlow"]["sourceStatus"]
    degraded_source_status = payloads[DEGRADED_EXAMPLE]["moneyFlow"]["sourceStatus"]

    assert set(happy_source_status) == {"status", "summary", "sampleData", "demoPayload"}
    assert set(degraded_source_status) == {"status", "summary", "sampleData", "demoPayload"}
    assert happy_source_status["status"] == "ready"
    assert degraded_source_status["status"] == "partial"
    assert "sample_ready" not in _serialized(payloads)
    assert "sample_degraded" not in _serialized(payloads)


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
