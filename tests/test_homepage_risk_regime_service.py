# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage risk-regime contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_risk_regime import (
    HOMEPAGE_RISK_REGIME_DEFAULT_AS_OF,
    HOMEPAGE_RISK_REGIME_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_RISK_REGIME_SCHEMA_VERSION,
    HomepageRiskRegimeSnapshot,
)
from src.services.homepage_risk_regime_service import HomepageRiskRegimeService


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "regime",
    "regimeLabel",
    "summary",
    "evidence",
    "contradictions",
    "marketPricing",
    "ratesPricing",
    "volatilitySignal",
    "dollarSignal",
    "creditSignal",
    "commoditySignal",
    "cryptoSignal",
    "equityStyleSignal",
    "defensiveVsOffensiveSignal",
    "watchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
EXPECTED_MARKET_PRICING_KEYS = {
    "fed_policy_path",
    "treasury_curve",
    "inflation_pressure",
    "dollar_direction",
    "oil_risk_premium",
    "gold_safe_haven",
    "equity_volatility",
    "risk_asset_support",
    "defensive_demand",
}
ALLOWED_REGIMES = {"risk_on", "neutral", "risk_off", "mixed", "unavailable"}
FORBIDDEN_MARKERS = (
    "buy",
    "sell",
    "add",
    "reduce",
    "target price",
    "broker",
    "order",
    "execution",
    "provider",
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
    "api_key",
    "secret",
    "token",
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "下单",
    "交易指令",
    "交易执行",
    "交易建议",
    "投资建议",
    "目标价",
    "止损",
    "止盈",
    "个性化配置",
)
REPO_ROOT = Path(__file__).resolve().parents[1]
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
    "broker",
    "brokers",
    "order",
    "orders",
    "trade",
    "trades",
    "trading",
    "src.services.dashboard_overview_service",
)


def _build_payload() -> dict[str, object]:
    return HomepageRiskRegimeService().build_snapshot().model_dump(mode="json")


def test_risk_regime_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_RISK_REGIME_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_RISK_REGIME_DEFAULT_AS_OF
    assert payload["regime"] in ALLOWED_REGIMES
    assert payload["noAdviceDisclosure"] == HOMEPAGE_RISK_REGIME_NO_ADVICE_DISCLOSURE
    assert HomepageRiskRegimeSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_RISK_REGIME_SCHEMA_VERSION
    )


def test_risk_regime_contract_is_deterministic() -> None:
    first = _build_payload()
    second = _build_payload()

    assert first == second
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second,
        ensure_ascii=False,
        sort_keys=True,
    )


def test_risk_regime_enum_is_bounded() -> None:
    payload = _build_payload()
    payload["regime"] = "bullish"

    with pytest.raises(ValidationError):
        HomepageRiskRegimeSnapshot.model_validate(payload)


def test_market_pricing_items_cover_required_variables_and_quality() -> None:
    payload = _build_payload()
    market_pricing = payload["marketPricing"]

    assert {item["key"] for item in market_pricing} == EXPECTED_MARKET_PRICING_KEYS
    for item in market_pricing:
        assert item["affectedVariables"]
        assert item["implication"]
        assert item["evidenceQuality"] in {"confirmed", "needs_confirmation", "mixed", "unavailable"}
        assert item["watchPoints"]

    serialized = json.dumps(market_pricing, ensure_ascii=False)
    for expected_phrase in (
        "降息预期",
        "加息风险",
        "曲线移动",
        "通胀压力",
        "美元方向",
        "油价包含一定地缘风险溢价",
        "黄金需求偏强",
        "权益波动",
        "风险资产支持",
        "防御需求没有完全消退",
    ):
        assert expected_phrase in serialized


def test_cross_asset_signals_are_present_and_bounded() -> None:
    payload = _build_payload()

    assert payload["summary"] == "风险资产环境偏有利，但防御需求上升，证据仍需确认。"
    assert payload["evidenceQuality"]["label"] == "证据仍需确认"
    assert payload["dataQuality"]["status"] == "partial"
    for key in (
        "ratesPricing",
        "volatilitySignal",
        "dollarSignal",
        "creditSignal",
        "commoditySignal",
        "cryptoSignal",
        "equityStyleSignal",
        "defensiveVsOffensiveSignal",
    ):
        signal = payload[key]
        assert signal["state"] in {"supportive", "neutral", "pressure", "mixed", "unavailable"}
        assert signal["affectedVariables"]
        assert signal["watchPoints"]
        assert signal["evidenceQuality"] in {
            "confirmed",
            "needs_confirmation",
            "mixed",
            "unavailable",
        }


def test_risk_regime_contract_excludes_advice_execution_and_internal_markers() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False).lower()

    for marker in FORBIDDEN_MARKERS:
        assert marker.lower() not in serialized


def test_schema_rejects_forbidden_public_text() -> None:
    payload = _build_payload()
    payload["summary"] = "debug provider raw payload"

    with pytest.raises(ValidationError):
        HomepageRiskRegimeSnapshot.model_validate(payload)


def test_service_has_no_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_risk_regime_service.py"
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
        if any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    assert violations == []
