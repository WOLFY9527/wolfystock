# -*- coding: utf-8 -*-
"""Focused tests for the standalone homepage cross-asset indicators contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_cross_asset_indicators import (
    HOMEPAGE_CROSS_ASSET_INDICATORS_SCHEMA_VERSION,
    HomepageCrossAssetIndicatorsSnapshot,
)
from src.services.homepage_cross_asset_indicators_service import (
    HomepageCrossAssetIndicatorsService,
)


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "indicators",
    "assetGroups",
    "volatility",
    "rates",
    "dollar",
    "commodities",
    "crypto",
    "creditProxy",
    "equityStyle",
    "summary",
    "contradictions",
    "watchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
REQUIRED_INDICATOR_KEYS = {
    "vix",
    "move",
    "us_10y_yield",
    "us_2y_yield",
    "dollar_index",
    "gold",
    "oil",
    "btc",
    "eth",
    "high_yield_credit_proxy",
    "growth_vs_value",
    "large_cap_vs_small_cap",
}
REQUIRED_GROUP_KEYS = {
    "volatility",
    "rates",
    "dollar",
    "commodities",
    "crypto",
    "creditProxy",
    "equityStyle",
}
PUBLIC_STATES = {"ready", "partial", "delayed", "cached", "no_evidence", "unavailable"}
EVIDENCE_STATES = {"strong", "medium", "weak", "needs_confirmation", "conflicting"}
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
    return HomepageCrossAssetIndicatorsService().build_snapshot().model_dump(mode="json")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_cross_asset_indicators_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_CROSS_ASSET_INDICATORS_SCHEMA_VERSION
    assert payload["asOf"] == "2026-06-15T09:30:00Z"
    assert HomepageCrossAssetIndicatorsSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_CROSS_ASSET_INDICATORS_SCHEMA_VERSION
    )


def test_cross_asset_indicators_output_is_deterministic() -> None:
    service = HomepageCrossAssetIndicatorsService()

    first = service.build_snapshot().model_dump(mode="json")
    second = service.build_snapshot().model_dump(mode="json")

    assert first == second
    assert _serialized(first) == _serialized(second)


def test_cross_asset_indicators_cover_required_indicator_set() -> None:
    payload = _build_payload()
    indicators = payload["indicators"]

    assert {item["key"] for item in indicators} == REQUIRED_INDICATOR_KEYS
    assert len(indicators) == len(REQUIRED_INDICATOR_KEYS)
    for item in indicators:
        assert item["state"] in PUBLIC_STATES
        assert item["evidenceState"] in EVIDENCE_STATES
        assert item["label"]
        assert item["description"]
        assert item["interpretation"]
        assert "valueLabel" in item

    move = next(item for item in indicators if item["key"] == "move")
    assert move["state"] == "unavailable"
    assert move["valueLabel"] == "unavailable"
    assert move["evidenceState"] == "needs_confirmation"


def test_cross_asset_groups_and_sections_are_bounded() -> None:
    payload = _build_payload()

    assert {group["key"] for group in payload["assetGroups"]} == REQUIRED_GROUP_KEYS
    for group in payload["assetGroups"]:
        assert group["state"] in PUBLIC_STATES
        assert group["evidenceState"] in EVIDENCE_STATES
        assert group["indicatorKeys"]
        assert set(group["indicatorKeys"]).issubset(REQUIRED_INDICATOR_KEYS)

    for key in REQUIRED_GROUP_KEYS:
        section = payload[key]
        assert section["state"] in PUBLIC_STATES
        assert section["evidenceState"] in EVIDENCE_STATES
        assert section["indicatorKeys"]
        assert set(section["indicatorKeys"]).issubset(REQUIRED_INDICATOR_KEYS)
        assert section["summary"]


def test_cross_asset_quality_summary_and_watch_points_are_public_safe() -> None:
    payload = _build_payload()

    assert payload["evidenceQuality"]["state"] in EVIDENCE_STATES
    assert payload["dataQuality"]["state"] in PUBLIC_STATES
    assert payload["dataQuality"]["state"] == "partial"
    assert payload["contradictions"]
    assert payload["watchPoints"]
    assert "市场背景观察" in str(payload["noAdviceDisclosure"])


def test_cross_asset_indicators_exclude_advice_execution_and_internal_markers() -> None:
    serialized = _serialized(_build_payload())

    leaked = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_cross_asset_schema_rejects_unbounded_state_and_forbidden_text() -> None:
    payload = _build_payload()
    payload["indicators"][0]["state"] = "live"

    with pytest.raises(ValidationError):
        HomepageCrossAssetIndicatorsSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["summary"] = "debug raw provider payload"

    with pytest.raises(ValidationError):
        HomepageCrossAssetIndicatorsSnapshot.model_validate(payload)


def test_cross_asset_service_has_no_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_cross_asset_indicators_service.py"
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
