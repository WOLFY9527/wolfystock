# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage earnings catalysts contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_earnings_catalysts import (
    HOMEPAGE_EARNINGS_CATALYSTS_DEFAULT_AS_OF,
    HOMEPAGE_EARNINGS_CATALYSTS_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_EARNINGS_CATALYSTS_SCHEMA_VERSION,
    HomepageEarningsCatalystsSnapshot,
)
from src.services.homepage_earnings_catalysts_service import HomepageEarningsCatalystsService


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "catalystWindow",
    "earningsCatalysts",
    "guidanceSensitivity",
    "megaCapImpact",
    "sectorReadThrough",
    "themeReadThrough",
    "affectedAssets",
    "affectedSectors",
    "affectedThemes",
    "confirmationSignals",
    "missingEvidence",
    "watchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
EXPECTED_EARNINGS_CATALYST_KEYS = {
    "large_platform_results_proxy",
    "industrial_guidance_proxy",
    "consumer_read_through_proxy",
    "ai_supply_chain_proxy",
}
QUALITY_STATES = {"sample_proxy", "no_evidence", "unavailable"}
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
    "execution",
    "trade execution",
    "trading advice",
    "investment advice",
    "financial advice",
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
    "/tmp/",
    "api_key",
    "apikey",
    "secret",
    "token",
    "cookie",
    "session_id",
)
FORBIDDEN_LIVE_DATA_FIELDS = {
    "url",
    "source",
    "provider",
    "headline",
    "publishedAt",
    "rawNews",
    "newsUrl",
    "reportedEps",
    "estimatedEps",
    "surprisePercent",
}
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
    return HomepageEarningsCatalystsService().build_snapshot().model_dump(mode="json")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_earnings_catalysts_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_EARNINGS_CATALYSTS_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_EARNINGS_CATALYSTS_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_EARNINGS_CATALYSTS_NO_ADVICE_DISCLOSURE
    assert payload["catalystWindow"]["basis"] == "sample_proxy"
    assert payload["evidenceQuality"]["state"] in QUALITY_STATES
    assert payload["dataQuality"]["state"] in QUALITY_STATES
    assert HomepageEarningsCatalystsSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_EARNINGS_CATALYSTS_SCHEMA_VERSION
    )


def test_earnings_catalysts_output_is_deterministic() -> None:
    service = HomepageEarningsCatalystsService()

    first = service.build_snapshot().model_dump(mode="json")
    second = service.build_snapshot().model_dump(mode="json")

    assert first == second
    assert _serialized(first) == _serialized(second)


def test_earnings_catalysts_represent_required_observation_sections() -> None:
    payload = _build_payload()

    assert {item["key"] for item in payload["earningsCatalysts"]} == (
        EXPECTED_EARNINGS_CATALYST_KEYS
    )
    assert payload["affectedAssets"]
    assert payload["affectedSectors"]
    assert payload["affectedThemes"]
    assert payload["confirmationSignals"]
    assert payload["missingEvidence"]
    assert payload["watchPoints"]

    for section_name in (
        "guidanceSensitivity",
        "megaCapImpact",
        "sectorReadThrough",
        "themeReadThrough",
    ):
        section = payload[section_name]
        assert section["state"] == "sample_proxy"
        assert section["summary"]
        assert section["observations"]
        for observation in section["observations"]:
            assert observation["basis"] in QUALITY_STATES
            assert observation["evidenceState"] in QUALITY_STATES
            assert observation["observation"]
            assert observation["researchContext"]
            assert observation["affectedAssets"]
            assert observation["affectedSectors"]
            assert observation["affectedThemes"]
            assert observation["confirmationSignals"]
            assert observation["missingEvidence"]
            assert observation["watchPoints"]


def test_earnings_catalysts_do_not_claim_real_earnings_or_news_data() -> None:
    payload = _build_payload()

    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden_field in FORBIDDEN_LIVE_DATA_FIELDS:
        assert f'"{forbidden_field}"' not in serialized

    for item in payload["earningsCatalysts"]:
        assert item["basis"] in QUALITY_STATES
        assert item["evidenceState"] in QUALITY_STATES
    assert payload["catalystWindow"]["basis"] == "sample_proxy"
    assert payload["dataQuality"]["state"] == "sample_proxy"
    serialized_lower = serialized.lower()
    assert "live earnings or news data" in serialized_lower
    assert "no live news evidence is attached" in serialized_lower


def test_earnings_catalysts_exclude_advice_execution_and_internal_markers() -> None:
    serialized = _serialized(_build_payload())

    leaked = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_earnings_catalysts_schema_rejects_forbidden_public_text_and_schema_drift() -> None:
    payload = _build_payload()
    payload["megaCapImpact"]["summary"] = "debug provider raw payload"

    with pytest.raises(ValidationError):
        HomepageEarningsCatalystsSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["schemaVersion"] = "homepage_earnings_catalysts_v2"

    with pytest.raises(ValidationError):
        HomepageEarningsCatalystsSnapshot.model_validate(payload)


def test_earnings_catalysts_service_has_no_live_provider_http_or_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_earnings_catalysts_service.py"
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
