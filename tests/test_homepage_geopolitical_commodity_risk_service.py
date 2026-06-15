# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage geopolitical commodity risk contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_geopolitical_commodity_risk import (
    HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_DEFAULT_AS_OF,
    HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_SCHEMA_VERSION,
    HomepageGeopoliticalCommodityRiskSnapshot,
)
from src.services.homepage_geopolitical_commodity_risk_service import (
    HomepageGeopoliticalCommodityRiskService,
)


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "riskWindow",
    "geopoliticalRiskPremium",
    "oilRiskPremium",
    "safeHavenDemand",
    "shippingRisk",
    "commodityPressure",
    "affectedAssets",
    "affectedSectors",
    "affectedThemes",
    "confirmingSignals",
    "invalidatingSignals",
    "watchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
EXPECTED_VECTOR_KEYS = [
    "key",
    "label",
    "state",
    "summary",
    "monitoringScenarios",
    "confirmingSignals",
    "invalidatingSignals",
    "evidenceQuality",
    "dataQuality",
]
EXPECTED_SCENARIO_EXAMPLES = {
    "Oil/geopolitical risk premium rising",
    "Oil/geopolitical risk premium falling",
    "Safe-haven demand rising",
    "Shipping-route disruption risk",
    "Energy inflation pressure",
    "Gold/oil divergence",
}
ALLOWED_STATES = {
    "rising",
    "falling",
    "elevated",
    "divergent",
    "monitoring",
    "mixed",
    "unavailable",
}
ALLOWED_EVIDENCE_QUALITY = {
    "scenario_monitoring",
    "needs_confirmation",
    "limited",
    "unavailable",
}
ALLOWED_DATA_QUALITY_STATUS = {"sample_proxy", "no_evidence", "unavailable"}
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
    "src.services.homepage_intelligence_service",
    "src.services.dashboard_overview_service",
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_payload() -> dict[str, object]:
    return HomepageGeopoliticalCommodityRiskService().build_snapshot().model_dump(mode="json")


def _serialized_values(payload: object) -> str:
    values: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, str):
            values.append(value)
            return
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return json.dumps(values, ensure_ascii=False, sort_keys=True).lower()


def test_geopolitical_commodity_risk_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_DEFAULT_AS_OF
    assert payload["riskWindow"] == "next_1_to_4_weeks_scenario_monitoring"
    assert payload["noAdviceDisclosure"] == HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_NO_ADVICE_DISCLOSURE
    assert payload["evidenceQuality"] in ALLOWED_EVIDENCE_QUALITY
    assert payload["dataQuality"]["status"] in ALLOWED_DATA_QUALITY_STATUS
    assert HomepageGeopoliticalCommodityRiskSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_SCHEMA_VERSION
    )


def test_geopolitical_commodity_risk_contract_is_deterministic() -> None:
    service = HomepageGeopoliticalCommodityRiskService()

    first = service.build_snapshot().model_dump(mode="json")
    second = service.build_snapshot().model_dump(mode="json")

    assert first == second
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second,
        ensure_ascii=False,
        sort_keys=True,
    )


def test_geopolitical_commodity_risk_vectors_cover_required_examples() -> None:
    payload = _build_payload()
    vectors = [
        payload["geopoliticalRiskPremium"],
        payload["oilRiskPremium"],
        payload["safeHavenDemand"],
        payload["shippingRisk"],
        payload["commodityPressure"],
    ]
    scenario_names = {
        scenario["scenarioName"]
        for vector in vectors
        for scenario in vector["monitoringScenarios"]
    }

    assert scenario_names == EXPECTED_SCENARIO_EXAMPLES
    for vector in vectors:
        assert list(vector.keys()) == EXPECTED_VECTOR_KEYS
        assert vector["state"] in ALLOWED_STATES
        assert vector["confirmingSignals"]
        assert vector["invalidatingSignals"]
        assert vector["evidenceQuality"] in ALLOWED_EVIDENCE_QUALITY
        assert vector["dataQuality"] in ALLOWED_DATA_QUALITY_STATUS
        for scenario in vector["monitoringScenarios"]:
            assert scenario["scenarioName"] in EXPECTED_SCENARIO_EXAMPLES
            assert scenario["researchLanguage"]
            assert scenario["affectedAssets"]
            assert scenario["affectedSectors"]
            assert scenario["affectedThemes"]


def test_geopolitical_commodity_risk_represents_affected_market_areas() -> None:
    payload = _build_payload()

    assert set(payload["affectedAssets"]) >= {
        "crude oil",
        "gold",
        "US dollar",
        "shipping rates",
        "inflation-linked assets",
    }
    assert set(payload["affectedSectors"]) >= {
        "energy",
        "transportation",
        "materials",
        "consumer discretionary",
        "defense",
    }
    assert set(payload["affectedThemes"]) >= {
        "geopolitical risk premium",
        "safe-haven demand",
        "commodity input pressure",
        "shipping-route disruption",
        "energy inflation sensitivity",
    }
    assert payload["confirmingSignals"]
    assert payload["invalidatingSignals"]
    assert payload["watchPoints"]


def test_geopolitical_commodity_risk_uses_monitoring_not_prediction_language() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False)

    for expected_phrase in (
        "scenario monitoring",
        "research watch item",
        "would need confirmation",
        "sample proxy",
        "does not assert live geopolitical or commodity data",
        "does not forecast conflict, shipping, energy, or market outcomes",
    ):
        assert expected_phrase in serialized


def test_geopolitical_commodity_risk_excludes_advice_execution_diagnostics_and_urls() -> None:
    serialized = _serialized_values(_build_payload())
    leaked = [marker for marker in FORBIDDEN_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_geopolitical_commodity_risk_schema_rejects_forbidden_public_text() -> None:
    payload = _build_payload()
    payload["oilRiskPremium"]["summary"] = "debug provider raw payload"

    with pytest.raises(ValidationError):
        HomepageGeopoliticalCommodityRiskSnapshot.model_validate(payload)


def test_geopolitical_commodity_risk_schema_version_is_bounded() -> None:
    payload = _build_payload()
    payload["schemaVersion"] = "homepage_geopolitical_commodity_risk_v2"

    with pytest.raises(ValidationError):
        HomepageGeopoliticalCommodityRiskSnapshot.model_validate(payload)


def test_geopolitical_commodity_risk_service_has_no_live_provider_http_or_protected_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_geopolitical_commodity_risk_service.py"
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
