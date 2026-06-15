# -*- coding: utf-8 -*-
"""Focused tests for the standalone homepage Rates Pricing contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_rates_pricing import (
    HOMEPAGE_RATES_PRICING_DEFAULT_AS_OF,
    HOMEPAGE_RATES_PRICING_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_RATES_PRICING_SCHEMA_VERSION,
    HomepageRatesPricingSnapshot,
)
from src.services.homepage_rates_pricing_service import HomepageRatesPricingService


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "pricingMode",
    "policyExpectation",
    "ratePathSummary",
    "curveSignal",
    "realYieldSignal",
    "inflationPressure",
    "equityImplication",
    "dollarImplication",
    "goldImplication",
    "watchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
SIGNAL_KEYS = {
    "ratePathSummary",
    "curveSignal",
    "realYieldSignal",
    "inflationPressure",
}
ASSET_IMPLICATION_KEYS = {
    "equityImplication",
    "dollarImplication",
    "goldImplication",
}
SIGNAL_STATES = {"supportive", "restrictive", "mixed", "watch", "unavailable", "no_evidence"}
EVIDENCE_STATES = {
    "proxy_observation",
    "needs_confirmation",
    "mixed",
    "unavailable",
    "no_evidence",
}
DATA_STATES = {"deterministic", "partial", "unavailable", "no_evidence"}
FORBIDDEN_PUBLIC_MARKERS = (
    "交易指令",
    "交易执行",
    "交易建议",
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "止损",
    "止盈",
    "目标价",
    "收益预测",
    "AI推荐",
    "智能选股",
    "provider",
    "fallback",
    "internal",
    "diagnostic",
    "debug",
    "traceback",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "raw",
    "http://",
    "https://",
    "/users/",
    "/tmp/",
    "api_key",
    "apikey",
    "secret",
    "token",
    "cookie",
    "session",
    "live pricing",
    "real-time",
    "realtime",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "src.providers",
    "aiohttp",
    "httpx",
    "requests",
    "urllib",
    "urllib3",
    "api.deps",
    "api.middlewares.auth",
    "src.auth",
    "src.auth_context",
    "src.admin_rbac",
    "src.services.dashboard_overview_service",
    "src.services.homepage_intelligence_service",
    "src.services.market_cache",
    "src.services.homepage_cross_asset_indicators_service",
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_payload() -> dict[str, object]:
    return HomepageRatesPricingService().build_snapshot().model_dump(mode="json")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_rates_pricing_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_RATES_PRICING_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_RATES_PRICING_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_RATES_PRICING_NO_ADVICE_DISCLOSURE
    assert HomepageRatesPricingSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_RATES_PRICING_SCHEMA_VERSION
    )


def test_rates_pricing_output_is_deterministic() -> None:
    service = HomepageRatesPricingService()

    first = service.build_snapshot().model_dump(mode="json")
    second = service.build_snapshot().model_dump(mode="json")

    assert first == second
    assert _serialized(first) == _serialized(second)


def test_rates_pricing_mode_discloses_unavailable_direct_policy_pricing() -> None:
    payload = _build_payload()
    pricing_mode = payload["pricingMode"]
    policy_expectation = payload["policyExpectation"]

    assert pricing_mode["mode"] == "proxy_only"
    assert pricing_mode["fedFuturesPricing"] == "unavailable"
    assert pricing_mode["oisPricing"] == "unavailable"
    assert policy_expectation["pricingAuthority"] == "proxy_only"
    assert policy_expectation["missingEvidence"] == [
        "Fed futures 曲线未接入",
        "OIS 曲线未接入",
        "会议概率分布未接入",
    ]


def test_rates_pricing_signals_cover_required_backdrop_dimensions() -> None:
    payload = _build_payload()

    for key in SIGNAL_KEYS:
        signal = payload[key]
        assert signal["state"] in SIGNAL_STATES
        assert signal["evidenceQuality"] in EVIDENCE_STATES
        assert signal["label"]
        assert signal["observation"]
        assert signal["marketBackdropImplication"]

    for key in ASSET_IMPLICATION_KEYS:
        implication = payload[key]
        assert implication["state"] in SIGNAL_STATES
        assert implication["label"]
        assert implication["observation"]
        assert implication["sensitivity"]


def test_rates_pricing_quality_summary_and_watch_points_are_public_safe() -> None:
    payload = _build_payload()

    assert payload["evidenceQuality"]["state"] in EVIDENCE_STATES
    assert payload["evidenceQuality"]["state"] == "proxy_observation"
    assert payload["dataQuality"]["state"] in DATA_STATES
    assert payload["dataQuality"]["state"] == "partial"
    assert len(payload["watchPoints"]) >= 5
    assert "利率背景观察" in str(payload["noAdviceDisclosure"])


def test_rates_pricing_excludes_advice_execution_and_internal_markers() -> None:
    serialized = _serialized(_build_payload())

    leaked = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_rates_pricing_schema_rejects_overclaiming_and_forbidden_text() -> None:
    payload = _build_payload()
    payload["pricingMode"]["fedFuturesPricing"] = "proxy_only"

    with pytest.raises(ValidationError):
        HomepageRatesPricingSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["policyExpectation"]["pricingAuthority"] = "unavailable"

    with pytest.raises(ValidationError):
        HomepageRatesPricingSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["dataQuality"]["summary"] = "debug raw provider payload"

    with pytest.raises(ValidationError):
        HomepageRatesPricingSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["debug"] = "internal"

    with pytest.raises(ValidationError):
        HomepageRatesPricingSnapshot.model_validate(payload)


def test_rates_pricing_service_has_no_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_rates_pricing_service.py"
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported_modules.add(node.module)
            imported_modules.update(
                f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*"
            )

    violations = sorted(
        module
        for module in imported_modules
        if any(
            module == prefix or module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        )
    )
    assert violations == []
