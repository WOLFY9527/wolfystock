# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage AI capex infrastructure contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_ai_capex_infrastructure import (
    HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_DEFAULT_AS_OF,
    HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_SCHEMA_VERSION,
    HomepageAICapexInfrastructureSnapshot,
)
from src.services.homepage_ai_capex_infrastructure_service import (
    HomepageAICapexInfrastructureService,
)


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "monitorWindow",
    "capexSignal",
    "demandSignals",
    "supplyConstraints",
    "computeSupplyChain",
    "dataCenterDemand",
    "powerConstraint",
    "liquidCoolingConstraint",
    "gridConstraint",
    "affectedSectors",
    "affectedThemes",
    "confirmationSignals",
    "missingEvidence",
    "watchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
REQUIRED_THEMES = {
    "AI infrastructure",
    "semiconductors",
    "data centers",
    "power equipment",
    "liquid cooling",
    "grid infrastructure",
    "optical networking",
    "software infrastructure",
    "cybersecurity",
    "cloud / compute capacity",
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
    "session",
)
FORBIDDEN_REAL_DATA_FIELDS = {
    "url",
    "source",
    "provider",
    "headline",
    "publishedAt",
    "orderBacklog",
    "capexAmount",
    "revenueForecast",
    "newsUrl",
    "rawNews",
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
    return HomepageAICapexInfrastructureService().build_snapshot().model_dump(mode="json")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_ai_capex_infrastructure_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_NO_ADVICE_DISCLOSURE
    assert payload["evidenceQuality"]["state"] in QUALITY_STATES
    assert payload["dataQuality"]["state"] in QUALITY_STATES
    assert HomepageAICapexInfrastructureSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_SCHEMA_VERSION
    )


def test_ai_capex_infrastructure_output_is_deterministic() -> None:
    service = HomepageAICapexInfrastructureService()

    first = service.build_snapshot().model_dump(mode="json")
    second = service.build_snapshot().model_dump(mode="json")

    assert first == second
    assert _serialized(first) == _serialized(second)


def test_ai_capex_infrastructure_covers_required_monitoring_domains() -> None:
    payload = _build_payload()

    assert payload["monitorWindow"]["basis"] == "sample_proxy"
    assert payload["capexSignal"]["evidenceState"] == "sample_proxy"
    assert payload["demandSignals"]
    assert payload["supplyConstraints"]
    assert payload["computeSupplyChain"]
    assert set(payload["affectedThemes"]) == REQUIRED_THEMES

    for section_name in (
        "dataCenterDemand",
        "powerConstraint",
        "liquidCoolingConstraint",
        "gridConstraint",
    ):
        section = payload[section_name]
        assert section["state"] in QUALITY_STATES
        assert section["observation"]
        assert section["researchContext"]
        assert section["watchPoints"]

    for item in (
        payload["demandSignals"]
        + payload["supplyConstraints"]
        + payload["computeSupplyChain"]
        + payload["confirmationSignals"]
        + payload["missingEvidence"]
        + payload["watchPoints"]
    ):
        assert item["evidenceState"] in QUALITY_STATES
        assert item["observation"]
        assert item["researchContext"]


def test_ai_capex_infrastructure_uses_observation_language_without_real_data_claims() -> None:
    payload = _build_payload()
    serialized = json.dumps(payload, ensure_ascii=False)

    for expected_phrase in (
        "monitoring frame",
        "fixed sample",
        "does not claim",
        "would need confirmation",
        "research question",
    ):
        assert expected_phrase in serialized

    for forbidden_field in FORBIDDEN_REAL_DATA_FIELDS:
        assert f'"{forbidden_field}"' not in serialized

    assert "live" not in serialized.lower()
    assert "real-time" not in serialized.lower()
    assert "unconfirmed order" not in serialized.lower()


def test_ai_capex_infrastructure_excludes_advice_execution_and_internal_markers() -> None:
    serialized = _serialized(_build_payload())

    leaked = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_ai_capex_schema_rejects_forbidden_public_text_and_schema_drift() -> None:
    payload = _build_payload()
    payload["capexSignal"]["observation"] = "debug provider raw payload"

    with pytest.raises(ValidationError):
        HomepageAICapexInfrastructureSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["schemaVersion"] = "homepage_ai_capex_infrastructure_v2"

    with pytest.raises(ValidationError):
        HomepageAICapexInfrastructureSnapshot.model_validate(payload)


def test_ai_capex_service_has_no_live_provider_http_or_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_ai_capex_infrastructure_service.py"
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
