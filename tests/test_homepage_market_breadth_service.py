# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage market breadth contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_market_breadth import (
    HOMEPAGE_MARKET_BREADTH_DEFAULT_AS_OF,
    HOMEPAGE_MARKET_BREADTH_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_MARKET_BREADTH_SCHEMA_VERSION,
    HomepageMarketBreadthSnapshot,
)
from src.services.homepage_market_breadth_service import HomepageMarketBreadthService


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "breadthRegime",
    "participationSummary",
    "advancingVsDeclining",
    "leadershipConcentration",
    "themeConcentration",
    "largeCapVsSmallCap",
    "growthVsValue",
    "offensiveVsDefensive",
    "confirmationStatus",
    "missingEvidence",
    "watchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
PUBLIC_STATES = {
    "confirmed",
    "proxy",
    "needs_confirmation",
    "mixed",
    "conflicting",
    "no_evidence",
}
BREADTH_REGIMES = {
    "broadening",
    "narrowing",
    "concentrated",
    "mixed",
    "no_evidence",
}
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
    "buy now",
    "sell now",
    "add position",
    "reduce position",
    "clear position",
    "place order",
    "submit order",
    "trade execution",
    "trade recommendation",
    "trading advice",
    "investment advice",
    "financial advice",
    "target price",
    "stop loss",
    "take profit",
    "guaranteed",
    "provider",
    "fallback",
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
    "src.services.market_overview_tickflow_breadth_provider",
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
    return HomepageMarketBreadthService().build_snapshot().model_dump(mode="json")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_market_breadth_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_MARKET_BREADTH_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_MARKET_BREADTH_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_MARKET_BREADTH_NO_ADVICE_DISCLOSURE
    assert HomepageMarketBreadthSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_MARKET_BREADTH_SCHEMA_VERSION
    )


def test_market_breadth_contract_is_deterministic() -> None:
    first = _build_payload()
    second = _build_payload()

    assert first == second
    assert _serialized(first) == _serialized(second)


def test_market_breadth_distinguishes_regime_participation_and_confirmation_states() -> None:
    payload = _build_payload()

    assert payload["breadthRegime"]["status"] in BREADTH_REGIMES
    assert payload["participationSummary"]["status"] in PUBLIC_STATES
    assert payload["confirmationStatus"]["status"] in PUBLIC_STATES
    assert payload["confirmationStatus"]["status"] == "proxy"
    assert payload["breadthRegime"]["status"] == "concentrated"
    assert "代理线索" in payload["confirmationStatus"]["summary"]
    assert payload["missingEvidence"]

    for key in (
        "advancingVsDeclining",
        "leadershipConcentration",
        "themeConcentration",
        "largeCapVsSmallCap",
        "growthVsValue",
        "offensiveVsDefensive",
    ):
        section = payload[key]
        assert section["status"] in PUBLIC_STATES
        assert section["label"]
        assert section["summary"]
        assert section["evidenceState"] in PUBLIC_STATES


def test_market_breadth_represents_required_participation_axes() -> None:
    payload = _build_payload()

    assert payload["advancingVsDeclining"]["status"] == "no_evidence"
    assert payload["leadershipConcentration"]["status"] == "proxy"
    assert payload["themeConcentration"]["status"] == "proxy"
    assert payload["largeCapVsSmallCap"]["status"] == "proxy"
    assert payload["growthVsValue"]["status"] == "proxy"
    assert payload["offensiveVsDefensive"]["status"] == "needs_confirmation"
    assert payload["evidenceQuality"]["status"] == "proxy"
    assert payload["dataQuality"]["status"] == "partial"
    assert payload["dataQuality"]["available"] is True
    assert payload["watchPoints"]


def test_market_breadth_excludes_advice_execution_and_internal_markers() -> None:
    serialized = _serialized(_build_payload())
    leaked = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_schema_rejects_forbidden_public_text_extra_fields_and_unknown_states() -> None:
    payload = _build_payload()
    payload["participationSummary"]["summary"] = "debug provider raw payload"

    with pytest.raises(ValidationError):
        HomepageMarketBreadthSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["debug"] = "internal"

    with pytest.raises(ValidationError):
        HomepageMarketBreadthSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["confirmationStatus"]["status"] = "live_provider_confirmed"

    with pytest.raises(ValidationError):
        HomepageMarketBreadthSnapshot.model_validate(payload)


def test_service_has_no_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_market_breadth_service.py"
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
