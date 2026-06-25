# -*- coding: utf-8 -*-
"""Tests for the provider-neutral earnings calendar readiness contract."""

from __future__ import annotations

import ast
import copy
import importlib
import json
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/earnings_calendar_readiness_contract.py"

FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.services.market_cache",
    "src.services.provider_capability_matrix",
)

REQUIRED_COMPONENTS = {
    "nextEarningsDate",
    "lastReport",
    "epsEstimate",
    "reportedEps",
    "companyGuidance",
    "callTranscript",
    "eventFreshness",
}

ALLOWED_STATES = {
    "available",
    "missing",
    "stale",
    "not_configured",
    "insufficient_permissions",
}

FORBIDDEN_CONSUMER_MARKERS = (
    "providerName",
    "providerClass",
    "providerAttempted",
    "apiKey",
    "token",
    "credential",
    "env",
    "requestId",
    "traceId",
    "cacheKey",
    "rawPayload",
    "raw_payload",
    "exceptionClass",
    "stack trace",
    "traceback",
)

FORBIDDEN_FAKE_DATA_MARKERS = (
    "2026-07-30",
    "1.23",
    "beat by",
    "raises guidance",
    "earnings source",
    "fake calendar",
)

FORBIDDEN_ADVICE_MARKERS = (
    "buy",
    "sell",
    "hold",
    "recommendation",
    "target",
    "stop",
    "position",
    "买入",
    "卖出",
    "持有",
    "目标价",
)


def _load_helper_module() -> Any:
    try:
        return importlib.import_module("src.services.earnings_calendar_readiness_contract")
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in RED run
        pytest.fail(f"earnings calendar readiness helper missing: {exc}")


def _helper_imports() -> set[str]:
    if not HELPER_PATH.exists():
        pytest.fail(f"helper file missing: {HELPER_PATH}")
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _unsafe_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "componentStates": {
            "nextEarningsDate": "available",
            "lastReport": "stale",
            "epsEstimate": "missing",
            "reportedEps": "available",
            "companyGuidance": "insufficient_permissions",
            "callTranscript": "not_configured",
            "eventFreshness": "stale",
        },
        "nextEarningsDate": "2026-07-30",
        "epsEstimate": 1.23,
        "reportedEps": 1.45,
        "eventSummary": "Fake calendar beat by 0.22 and raises guidance.",
        "source": "earnings source",
        "providerName": "UnsafeProvider",
        "providerClass": "UnsafeProviderClass",
        "providerAttempted": True,
        "apiKey": "secret",
        "token": "secret",
        "credential": "secret",
        "env": "PRIVATE_ENV",
        "requestId": "REQ-1",
        "traceId": "TRACE-1",
        "cacheKey": "cache:key",
        "rawPayload": {"stack trace": "Traceback: internal"},
        "recommendation": "buy",
        "target": "100",
        "position": "increase",
    }
    payload.update(overrides)
    return payload


def test_helper_is_pure_deterministic_and_json_safe() -> None:
    helper = _load_helper_module()
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    payload = _unsafe_payload()
    original = copy.deepcopy(payload)

    first = helper.build_earnings_calendar_readiness_v1(payload)
    second = helper.build_earnings_calendar_readiness_v1(payload)

    assert payload == original
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False)) == first
    assert first["contractVersion"] == helper.EARNINGS_CALENDAR_READINESS_CONTRACT_VERSION
    assert first["consumerSafe"] is True
    assert set(first["components"]) == REQUIRED_COMPONENTS


def test_default_contract_fails_closed_without_calendar_source_configuration() -> None:
    helper = _load_helper_module()

    contract = helper.build_earnings_calendar_readiness_v1({})

    assert contract["overallState"] == "not_configured"
    assert contract["safeNextDataAction"] == "Connect an authorized earnings calendar source before showing calendar fields."
    assert all(component["state"] == "not_configured" for component in contract["components"].values())
    assert all(component["valueAvailable"] is False for component in contract["components"].values())
    assert contract["noAdviceBoundary"] == {
        "state": "no_advice",
        "label": "Research calendar readiness only.",
    }


def test_component_states_separate_calendar_eps_guidance_transcript_and_freshness() -> None:
    helper = _load_helper_module()

    contract = helper.build_earnings_calendar_readiness_v1(_unsafe_payload())

    assert contract["overallState"] == "insufficient_permissions"
    assert {component["state"] for component in contract["components"].values()} <= ALLOWED_STATES
    assert contract["components"]["nextEarningsDate"]["state"] == "available"
    assert contract["components"]["lastReport"]["state"] == "stale"
    assert contract["components"]["epsEstimate"]["state"] == "missing"
    assert contract["components"]["reportedEps"]["state"] == "available"
    assert contract["components"]["companyGuidance"]["state"] == "insufficient_permissions"
    assert contract["components"]["callTranscript"]["state"] == "not_configured"
    assert contract["components"]["eventFreshness"]["state"] == "stale"
    assert contract["components"]["nextEarningsDate"]["valueAvailable"] is True
    assert contract["components"]["epsEstimate"]["valueAvailable"] is False
    assert "insufficient_permissions" in contract["blockingReasons"]
    assert "stale_event_readiness" in contract["blockingReasons"]


def test_contract_redacts_raw_provider_internals_fake_data_and_advice_copy() -> None:
    helper = _load_helper_module()

    contract = helper.build_earnings_calendar_readiness_v1(_unsafe_payload())

    serialized = json.dumps(contract, ensure_ascii=False)
    lowered = serialized.lower()
    for marker in FORBIDDEN_CONSUMER_MARKERS:
        assert marker not in serialized
        assert marker.lower() not in lowered
    for marker in FORBIDDEN_FAKE_DATA_MARKERS:
        assert marker.lower() not in lowered
    for marker in FORBIDDEN_ADVICE_MARKERS:
        assert marker.lower() not in lowered
