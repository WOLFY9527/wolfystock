# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage volatility positioning contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_volatility_positioning import (
    HOMEPAGE_VOLATILITY_POSITIONING_DEFAULT_AS_OF,
    HOMEPAGE_VOLATILITY_POSITIONING_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_VOLATILITY_POSITIONING_SCHEMA_VERSION,
    HomepageVolatilityPositioningSnapshot,
)
from src.services.homepage_volatility_positioning_service import (
    HomepageVolatilityPositioningService,
)


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "volatilityRegime",
    "equityVolatility",
    "rateVolatility",
    "skewOrTailRisk",
    "optionsDemandProxy",
    "riskAppetiteImplication",
    "contradictionSignals",
    "watchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
REGIME_STATES = {"calm", "elevated", "stressed", "mixed", "unavailable"}
PRESSURE_STATES = {"low", "moderate", "elevated", "stressed", "mixed", "unavailable"}
AUTHORITY_STATES = {"proxy_only", "unavailable", "no_evidence"}
QUALITY_STATES = {
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
    "buy",
    "sell",
    "add position",
    "reduce position",
    "clear position",
    "broker",
    "order",
    "trade execution",
    "trading advice",
    "target price",
    "stop loss",
    "take profit",
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
    "/api/v",
    "api_key",
    "apikey",
    "secret",
    "token",
    "cookie",
    "session",
    "live option chain",
    "live options chain",
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
    "src.services.options",
    "api.v1.endpoints",
    "broker",
    "brokers",
    "order",
    "orders",
    "trade",
    "trades",
    "trading",
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_payload() -> dict[str, object]:
    return HomepageVolatilityPositioningService().build_snapshot().model_dump(mode="json")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_volatility_positioning_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_VOLATILITY_POSITIONING_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_VOLATILITY_POSITIONING_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_VOLATILITY_POSITIONING_NO_ADVICE_DISCLOSURE
    assert HomepageVolatilityPositioningSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_VOLATILITY_POSITIONING_SCHEMA_VERSION
    )


def test_volatility_positioning_output_is_deterministic() -> None:
    first = _build_payload()
    second = _build_payload()

    assert first == second
    assert _serialized(first) == _serialized(second)


def test_volatility_positioning_represents_required_volatility_and_options_context() -> None:
    payload = _build_payload()

    assert payload["volatilityRegime"]["state"] in REGIME_STATES
    assert payload["volatilityRegime"]["state"] == "mixed"
    assert payload["equityVolatility"]["pressure"] in PRESSURE_STATES
    assert payload["rateVolatility"]["pressure"] in PRESSURE_STATES
    assert payload["skewOrTailRisk"]["pressure"] in PRESSURE_STATES
    assert payload["optionsDemandProxy"]["authority"] == "proxy_only"
    assert payload["optionsDemandProxy"]["optionChainAuthority"] == "unavailable"
    assert payload["optionsDemandProxy"]["missingEvidence"] == [
        "authoritative option-chain evidence unavailable",
        "dealer positioning evidence unavailable",
        "intraday options-flow evidence unavailable",
    ]
    assert payload["riskAppetiteImplication"]["state"] == "mixed"
    assert payload["riskAppetiteImplication"]["evidenceQuality"] in QUALITY_STATES
    assert payload["watchPoints"]


def test_volatility_positioning_quality_and_contradictions_are_public_safe() -> None:
    payload = _build_payload()

    assert payload["evidenceQuality"]["state"] == "proxy_observation"
    assert payload["dataQuality"]["state"] == "partial"
    assert payload["dataQuality"]["available"] is True
    assert len(payload["contradictionSignals"]) >= 1
    for signal in payload["contradictionSignals"]:
        assert signal["evidenceQuality"] in QUALITY_STATES
        assert signal["label"]
        assert signal["observation"]
        assert signal["whyItMatters"]


def test_volatility_positioning_excludes_advice_execution_internal_and_live_claim_markers() -> None:
    serialized = _serialized(_build_payload())
    leaked = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_volatility_positioning_schema_rejects_overclaiming_forbidden_text_and_extras() -> None:
    payload = _build_payload()
    payload["optionsDemandProxy"]["optionChainAuthority"] = "proxy_only"

    with pytest.raises(ValidationError):
        HomepageVolatilityPositioningSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["optionsDemandProxy"]["authority"] = "unavailable"

    with pytest.raises(ValidationError):
        HomepageVolatilityPositioningSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["equityVolatility"]["observation"] = "debug raw provider payload"

    with pytest.raises(ValidationError):
        HomepageVolatilityPositioningSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["debug"] = "internal"

    with pytest.raises(ValidationError):
        HomepageVolatilityPositioningSnapshot.model_validate(payload)


def test_volatility_positioning_service_has_no_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_volatility_positioning_service.py"
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
