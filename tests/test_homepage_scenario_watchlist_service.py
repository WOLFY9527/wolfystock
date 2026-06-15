# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage scenario watchlist contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_scenario_watchlist import (
    HOMEPAGE_SCENARIO_WATCHLIST_DEFAULT_AS_OF,
    HOMEPAGE_SCENARIO_WATCHLIST_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_SCENARIO_WATCHLIST_SCHEMA_VERSION,
    HomepageScenarioWatchlistSnapshot,
)
from src.services.homepage_scenario_watchlist_service import HomepageScenarioWatchlistService


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "scenarios",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
EXPECTED_SCENARIO_KEYS = [
    "scenarioName",
    "description",
    "affectedAssets",
    "affectedSectors",
    "affectedThemes",
    "triggerConditions",
    "confirmingSignals",
    "invalidatingSignals",
    "evidenceQuality",
    "dataQuality",
]
EXPECTED_SCENARIO_NAMES = {
    "Rates repricing pressure",
    "AI capex continuation",
    "Oil/geopolitical risk premium falling or rising",
    "Defensive rotation",
    "Liquidity or credit stress",
    "Breadth expansion or narrowing",
}
ALLOWED_EVIDENCE_QUALITY = {"scenario_monitoring", "needs_confirmation", "mixed", "limited"}
ALLOWED_DATA_QUALITY = {"deterministic", "static_sample", "partial", "unavailable"}
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
    return HomepageScenarioWatchlistService().build_snapshot().model_dump(mode="json")


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


def test_scenario_watchlist_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_SCENARIO_WATCHLIST_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_SCENARIO_WATCHLIST_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_SCENARIO_WATCHLIST_NO_ADVICE_DISCLOSURE
    assert payload["evidenceQuality"] in ALLOWED_EVIDENCE_QUALITY
    assert payload["dataQuality"] in ALLOWED_DATA_QUALITY
    assert HomepageScenarioWatchlistSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_SCENARIO_WATCHLIST_SCHEMA_VERSION
    )


def test_scenario_watchlist_contract_is_deterministic() -> None:
    service = HomepageScenarioWatchlistService()

    first = service.build_snapshot().model_dump(mode="json")
    second = service.build_snapshot().model_dump(mode="json")

    assert first == second
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second,
        ensure_ascii=False,
        sort_keys=True,
    )


def test_scenario_watchlist_covers_required_monitoring_examples() -> None:
    payload = _build_payload()
    scenarios = payload["scenarios"]

    assert isinstance(scenarios, list)
    assert len(scenarios) == 6
    assert {scenario["scenarioName"] for scenario in scenarios} == EXPECTED_SCENARIO_NAMES

    for scenario in scenarios:
        assert list(scenario.keys()) == EXPECTED_SCENARIO_KEYS
        assert scenario["description"]
        assert scenario["affectedAssets"]
        assert scenario["affectedSectors"]
        assert scenario["affectedThemes"]
        assert scenario["triggerConditions"]
        assert scenario["confirmingSignals"]
        assert scenario["invalidatingSignals"]
        assert scenario["evidenceQuality"] in ALLOWED_EVIDENCE_QUALITY
        assert scenario["dataQuality"] in ALLOWED_DATA_QUALITY


def test_scenario_watchlist_uses_monitoring_not_prediction_language() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False)

    for expected_phrase in (
        "monitoring frame",
        "watch whether",
        "would need confirmation",
        "would weaken this monitoring case",
        "rates repricing",
        "AI infrastructure spend",
        "oil risk premium",
        "defensive sectors",
        "credit spreads",
        "market breadth",
    ):
        assert expected_phrase in serialized


def test_scenario_watchlist_excludes_advice_execution_diagnostics_and_urls() -> None:
    serialized = _serialized_values(_build_payload())

    leaked = [marker for marker in FORBIDDEN_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_scenario_watchlist_schema_rejects_forbidden_public_text() -> None:
    payload = _build_payload()
    payload["scenarios"][0]["description"] = "debug provider raw payload"

    with pytest.raises(ValidationError):
        HomepageScenarioWatchlistSnapshot.model_validate(payload)


def test_scenario_watchlist_schema_version_is_bounded() -> None:
    payload = _build_payload()
    payload["schemaVersion"] = "homepage_scenario_watchlist_v2"

    with pytest.raises(ValidationError):
        HomepageScenarioWatchlistSnapshot.model_validate(payload)


def test_scenario_watchlist_service_has_no_live_provider_http_or_protected_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_scenario_watchlist_service.py"
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
