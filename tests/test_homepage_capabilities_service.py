# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage capabilities contract."""

from __future__ import annotations

import json

from api.v1.schemas.homepage_capabilities import HomepageCapabilitiesSnapshot
from src.services.homepage_capabilities_service import (
    HOMEPAGE_CAPABILITIES_CONTRACT_VERSION,
    HOMEPAGE_CAPABILITIES_NO_ADVICE_DISCLOSURE,
    HomepageCapabilitiesService,
)


EXPECTED_CAPABILITY_KEYS = (
    "marketPulse",
    "moneyFlowProxy",
    "eventRadar",
    "personalSummary",
    "researchQueue",
    "publicDataQuality",
    "sessionStatus",
    "eventWindows",
    "noAdviceBoundary",
)
EXPECTED_SECTION_KEYS = (
    "marketPulse",
    "moneyFlowProxy",
    "eventRadar",
    "personalSummary",
    "researchQueue",
)
FORBIDDEN_MARKERS = (
    "route",
    "router",
    "endpoint",
    "admin",
    "diagnostic",
    "debug",
    "provider",
    "traceback",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "rawpayload",
    "sessionid",
    "api_key",
    "secret",
    "buy",
    "sell",
    "place order",
    "trade execution",
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "交易建议",
    "投资建议",
)


def _build_payload() -> dict[str, object]:
    return HomepageCapabilitiesService().build_snapshot().model_dump(mode="json")


def test_homepage_capabilities_contract_serializes_stable_version_and_capabilities() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == [
        "schemaVersion",
        "status",
        "sections",
        "capabilities",
        "dataQuality",
        "noAdviceDisclosure",
    ]
    assert payload["schemaVersion"] == HOMEPAGE_CAPABILITIES_CONTRACT_VERSION
    assert payload["status"] == "ready"
    assert [section["key"] for section in payload["sections"]] == list(EXPECTED_SECTION_KEYS)
    assert list(payload["capabilities"].keys()) == list(EXPECTED_CAPABILITY_KEYS)
    assert payload["noAdviceDisclosure"] == HOMEPAGE_CAPABILITIES_NO_ADVICE_DISCLOSURE
    assert HomepageCapabilitiesSnapshot.model_validate(payload).schemaVersion == HOMEPAGE_CAPABILITIES_CONTRACT_VERSION


def test_homepage_capabilities_default_flags_are_bounded() -> None:
    payload = _build_payload()

    assert set(payload["capabilities"].keys()) == set(EXPECTED_CAPABILITY_KEYS)
    assert all(isinstance(value, bool) for value in payload["capabilities"].values())
    assert all(section["supported"] is True for section in payload["sections"])
    assert all(section["status"] == "ready" for section in payload["sections"])


def test_homepage_capabilities_response_has_no_internal_diagnostics_or_secrets() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False).lower()

    for marker in FORBIDDEN_MARKERS:
        assert marker.lower() not in serialized


def test_homepage_capabilities_response_has_no_trading_advice_language() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False).lower()

    assert "not personalized financial advice" in serialized
    for marker in ("buy", "sell", "place order", "trade execution", "买入", "卖出", "加仓", "减仓"):
        assert marker not in serialized
