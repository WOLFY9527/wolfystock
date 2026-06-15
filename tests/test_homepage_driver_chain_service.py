# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage macro driver-chain contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_driver_chain import (
    HOMEPAGE_DRIVER_CHAIN_DEFAULT_AS_OF,
    HOMEPAGE_DRIVER_CHAIN_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_DRIVER_CHAIN_SCHEMA_VERSION,
    HomepageDriverChainSnapshot,
)
from src.services.homepage_driver_chain_service import HomepageDriverChainService


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "driverChains",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
EXPECTED_CHAIN_KEYS = [
    "key",
    "macroDriver",
    "marketMechanism",
    "riskRegimeImplication",
    "affectedAssets",
    "affectedSectors",
    "affectedThemes",
    "researchImplication",
    "confirmingEvidence",
    "missingEvidence",
    "contradiction",
    "evidenceQuality",
    "dataQuality",
]
EXPECTED_CHAIN_KEYS_BY_ID = {
    "lower_yields_growth_duration",
    "oil_risk_premium_falls",
    "stronger_dollar_liquidity_pressure",
    "vix_rises_defensive_review",
}
ALLOWED_EVIDENCE_QUALITY = {"confirmed", "needs_confirmation", "mixed", "unavailable"}
ALLOWED_DATA_QUALITY = {"deterministic", "partial", "no_evidence", "unavailable"}
FORBIDDEN_MARKERS = (
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
    "buy now",
    "sell now",
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
    "api_key",
    "secret",
    "token",
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
    "broker",
    "brokers",
    "order",
    "orders",
    "trade",
    "trades",
    "trading",
    "src.services.dashboard_overview_service",
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_payload() -> dict[str, object]:
    return HomepageDriverChainService().build_snapshot().model_dump(mode="json")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_driver_chain_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_DRIVER_CHAIN_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_DRIVER_CHAIN_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_DRIVER_CHAIN_NO_ADVICE_DISCLOSURE
    assert payload["evidenceQuality"] in ALLOWED_EVIDENCE_QUALITY
    assert payload["dataQuality"] in ALLOWED_DATA_QUALITY
    assert HomepageDriverChainSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_DRIVER_CHAIN_SCHEMA_VERSION
    )


def test_driver_chain_contract_is_deterministic() -> None:
    service = HomepageDriverChainService()

    first = service.build_snapshot().model_dump(mode="json")
    second = service.build_snapshot().model_dump(mode="json")

    assert first == second
    assert _serialized(first) == _serialized(second)


def test_driver_chain_items_cover_required_macro_causal_chains() -> None:
    payload = _build_payload()
    chains = payload["driverChains"]

    assert isinstance(chains, list)
    assert len(chains) == 4
    assert {chain["key"] for chain in chains} == EXPECTED_CHAIN_KEYS_BY_ID

    for chain in chains:
        assert list(chain.keys()) == EXPECTED_CHAIN_KEYS
        assert chain["macroDriver"]
        assert chain["marketMechanism"]
        assert chain["riskRegimeImplication"]
        assert chain["affectedAssets"]
        assert chain["affectedSectors"]
        assert chain["affectedThemes"]
        assert chain["researchImplication"]
        assert chain["confirmingEvidence"]
        assert chain["missingEvidence"]
        assert chain["contradiction"]
        assert chain["evidenceQuality"] in ALLOWED_EVIDENCE_QUALITY
        assert chain["dataQuality"] in ALLOWED_DATA_QUALITY


def test_driver_chain_output_contains_expected_research_observation_language() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False)

    for expected_phrase in (
        "Lower yields",
        "less pressure on growth valuation",
        "Nasdaq and growth assets improve",
        "semiconductors",
        "software",
        "AI infrastructure",
        "Oil-risk premium falls",
        "inflation pressure eases",
        "gold and energy safe-haven demand cools",
        "Dollar strengthens",
        "liquidity pressure rises",
        "small caps and emerging assets weaken",
        "VIX rises",
        "defensive sectors outperform",
        "growth exposure requires confirmation",
    ):
        assert expected_phrase in serialized


def test_driver_chain_contract_excludes_advice_execution_and_internal_markers() -> None:
    serialized = _serialized(_build_payload())

    leaked = [marker for marker in FORBIDDEN_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_driver_chain_schema_rejects_forbidden_public_text() -> None:
    payload = _build_payload()
    payload["driverChains"][0]["researchImplication"] = "debug provider raw payload"

    with pytest.raises(ValidationError):
        HomepageDriverChainSnapshot.model_validate(payload)


def test_driver_chain_schema_version_is_bounded() -> None:
    payload = _build_payload()
    payload["schemaVersion"] = "homepage_driver_chain_v2"

    with pytest.raises(ValidationError):
        HomepageDriverChainSnapshot.model_validate(payload)


def test_driver_chain_service_has_no_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_driver_chain_service.py"
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
