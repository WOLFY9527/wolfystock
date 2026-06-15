# -*- coding: utf-8 -*-
"""Focused tests for the standalone homepage liquidity and credit stress contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_liquidity_credit import (
    HOMEPAGE_LIQUIDITY_CREDIT_DEFAULT_AS_OF,
    HOMEPAGE_LIQUIDITY_CREDIT_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_LIQUIDITY_CREDIT_SCHEMA_VERSION,
    HomepageLiquidityCreditSnapshot,
)
from src.services.homepage_liquidity_credit_service import HomepageLiquidityCreditService


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "liquidityCondition",
    "creditStressCondition",
    "fundingPressure",
    "highYieldProxy",
    "treasuryLiquidityProxy",
    "dollarLiquidity",
    "riskAssetImplication",
    "evidenceSummary",
    "missingEvidence",
    "watchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
CONDITION_STATES = {"supportive", "neutral", "stressful"}
PUBLIC_STATES = {"ready", "partial", "no_evidence", "unavailable"}
EVIDENCE_STATES = {"strong", "medium", "weak", "needs_confirmation", "proxy_only"}
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
    "broker",
    "order",
    "trade execution",
    "trading advice",
    "investment advice",
    "buy now",
    "sell now",
    "target price",
    "stop loss",
    "take profit",
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
    "api_key",
    "apikey",
    "secret",
    "token",
    "cookie",
    "session",
)
FORBIDDEN_AUTHORITY_MARKERS = (
    "authoritative credit spread",
    "actual credit spread",
    "live credit spread",
    "official credit spread",
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
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_payload() -> dict[str, object]:
    return HomepageLiquidityCreditService().build_snapshot().model_dump(mode="json")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_liquidity_credit_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_LIQUIDITY_CREDIT_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_LIQUIDITY_CREDIT_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_LIQUIDITY_CREDIT_NO_ADVICE_DISCLOSURE
    assert HomepageLiquidityCreditSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_LIQUIDITY_CREDIT_SCHEMA_VERSION
    )


def test_liquidity_credit_output_is_deterministic() -> None:
    service = HomepageLiquidityCreditService()

    first = service.build_snapshot().model_dump(mode="json")
    second = service.build_snapshot().model_dump(mode="json")

    assert first == second
    assert _serialized(first) == _serialized(second)


def test_liquidity_credit_conditions_are_bounded_to_risk_asset_regime_states() -> None:
    payload = _build_payload()

    assert payload["liquidityCondition"]["state"] in CONDITION_STATES
    assert payload["creditStressCondition"]["state"] in CONDITION_STATES
    assert payload["riskAssetImplication"]["state"] in CONDITION_STATES
    assert payload["riskAssetImplication"]["summary"]

    for key in (
        "fundingPressure",
        "highYieldProxy",
        "treasuryLiquidityProxy",
        "dollarLiquidity",
    ):
        section = payload[key]
        assert section["state"] in CONDITION_STATES
        assert section["evidenceState"] in EVIDENCE_STATES
        assert section["dataQuality"] in PUBLIC_STATES
        assert section["summary"]
        assert section["interpretation"]


def test_liquidity_credit_proxy_contract_does_not_claim_authoritative_credit_spreads() -> None:
    payload = _build_payload()
    serialized = _serialized(payload)

    assert payload["highYieldProxy"]["isProxy"] is True
    assert payload["highYieldProxy"]["dataQuality"] == "no_evidence"
    assert payload["creditStressCondition"]["evidenceState"] == "proxy_only"
    assert payload["evidenceQuality"]["state"] == "proxy_only"
    assert any("信用利差" in item for item in payload["missingEvidence"])
    assert "代理线索" in payload["evidenceSummary"]
    assert "权威" not in serialized
    assert [marker for marker in FORBIDDEN_AUTHORITY_MARKERS if marker in serialized] == []


def test_liquidity_credit_quality_and_watch_points_are_public_safe() -> None:
    payload = _build_payload()

    assert payload["evidenceQuality"]["state"] in EVIDENCE_STATES
    assert payload["dataQuality"]["state"] in PUBLIC_STATES
    assert payload["dataQuality"]["available"] is False
    assert payload["missingEvidence"]
    assert payload["watchPoints"]
    assert "观察" in str(payload["noAdviceDisclosure"])


def test_liquidity_credit_output_excludes_advice_execution_and_internal_markers() -> None:
    serialized = _serialized(_build_payload())

    leaked = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_liquidity_credit_schema_rejects_unbounded_state_and_forbidden_text() -> None:
    payload = _build_payload()
    payload["liquidityCondition"]["state"] = "risk_on"

    with pytest.raises(ValidationError):
        HomepageLiquidityCreditSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["evidenceSummary"] = "debug provider raw payload"

    with pytest.raises(ValidationError):
        HomepageLiquidityCreditSnapshot.model_validate(payload)


def test_liquidity_credit_schema_version_is_bounded() -> None:
    payload = _build_payload()
    payload["schemaVersion"] = "homepage_liquidity_credit_v2"

    with pytest.raises(ValidationError):
        HomepageLiquidityCreditSnapshot.model_validate(payload)


def test_liquidity_credit_service_has_no_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_liquidity_credit_service.py"
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
