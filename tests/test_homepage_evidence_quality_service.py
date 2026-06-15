# -*- coding: utf-8 -*-
"""Focused tests for the standalone homepage evidence quality contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_evidence_quality import (
    HOMEPAGE_EVIDENCE_QUALITY_DEFAULT_AS_OF,
    HOMEPAGE_EVIDENCE_QUALITY_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_EVIDENCE_QUALITY_SCHEMA_VERSION,
    HomepageEvidenceQualityProjection,
)
from src.services.homepage_evidence_quality_service import HomepageEvidenceQualityService


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "sections",
    "dataQuality",
    "noAdviceDisclosure",
]
EXPECTED_SECTION_KEYS = [
    "sectionKey",
    "sectionLabel",
    "conclusionAllowed",
    "evidenceQuality",
    "evidenceSummary",
    "supportingEvidence",
    "missingEvidence",
    "conflictingEvidence",
    "dataFreshness",
    "publicConfidenceLabel",
]
ALLOWED_EVIDENCE_STATES = {
    "strong",
    "medium",
    "weak",
    "needs_confirmation",
    "conflicting",
    "unavailable",
}
ALLOWED_DATA_STATES = {
    "ready",
    "partial",
    "delayed",
    "cached",
    "no_evidence",
    "unavailable",
}
EXPECTED_SECTION_KEYS_IN_ORDER = [
    "market_structure",
    "breadth_confirmation",
    "news_catalyst",
    "cross_asset_context",
    "flow_confirmation",
]
FORBIDDEN_PUBLIC_TERMS = (
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
    "place order",
    "submit order",
    "trade recommendation",
    "trading advice",
    "investment advice",
    "financial advice",
    "guaranteed",
    "target price",
    "stop loss",
    "take profit",
    "fallback",
    "fallback_used",
    "trustLevel",
    "sourceType",
    "sourceTier",
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "reasonCode",
    "reason_code",
    "reasonFamilies",
    "debugRef",
    "rawDiagnostics",
    "rawProviderPayload",
    "coverageDiagnostics",
    "adminDiagnostics",
    "sourceMetadata",
    "routeRejected",
    "cache_key",
    "synthetic_",
    "provider",
    "providerId",
    "providerLabel",
    "providerRuntime",
    "providerRoute",
    "raw",
    "traceback",
    "stack trace",
    "exception",
    "http://",
    "https://",
    "/users/",
    "/tmp/",
    "/api/v",
    "api_key",
    "bearer",
    "sk-",
    "secret",
    "token",
    "session",
    "session_id",
    "cookie",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "urllib3",
    "api.deps",
    "api.middlewares.auth",
    "src.auth",
    "src.auth_context",
    "src.admin_rbac",
    "src.services.homepage_intelligence_service",
    "src.services.dashboard_overview_service",
    "src.services.market_cache",
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_payload() -> dict[str, object]:
    return HomepageEvidenceQualityService().build_projection().model_dump(mode="json")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_evidence_quality_projection_has_stable_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_EVIDENCE_QUALITY_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_EVIDENCE_QUALITY_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_EVIDENCE_QUALITY_NO_ADVICE_DISCLOSURE
    assert HomepageEvidenceQualityProjection.model_validate(payload).schemaVersion == (
        HOMEPAGE_EVIDENCE_QUALITY_SCHEMA_VERSION
    )


def test_sections_explain_public_evidence_quality_in_human_terms() -> None:
    payload = _build_payload()
    sections = payload["sections"]

    assert [section["sectionKey"] for section in sections] == EXPECTED_SECTION_KEYS_IN_ORDER
    for section in sections:
        assert list(section.keys()) == EXPECTED_SECTION_KEYS
        assert section["evidenceQuality"]["state"] in ALLOWED_EVIDENCE_STATES
        assert section["dataFreshness"]["state"] in ALLOWED_DATA_STATES
        assert section["supportingEvidence"] or section["missingEvidence"] or section["conflictingEvidence"]
        assert section["publicConfidenceLabel"]

    serialized = _serialized(payload)
    for expected_phrase in (
        "价格、成交量与市场广度相互确认",
        "价格线索存在，但市场广度尚未确认",
        "新闻催化存在，资金流向尚未确认",
        "跨资产信号存在分歧",
    ):
        assert expected_phrase in serialized


def test_projection_is_deterministic() -> None:
    service = HomepageEvidenceQualityService()

    first = service.build_projection()
    second = service.build_projection()

    assert first == second
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_public_states_are_bounded_and_schema_rejects_unknown_values() -> None:
    payload = _build_payload()
    payload["sections"][0]["evidenceQuality"]["state"] = "provider_debug"

    with pytest.raises(ValidationError):
        HomepageEvidenceQualityProjection.model_validate(payload)

    payload = _build_payload()
    payload["sections"][0]["dataFreshness"]["state"] = "live_fallback"

    with pytest.raises(ValidationError):
        HomepageEvidenceQualityProjection.model_validate(payload)


def test_projection_excludes_advice_execution_internal_names_and_urls() -> None:
    serialized = _serialized(_build_payload()).lower()

    leaked = [term for term in FORBIDDEN_PUBLIC_TERMS if term.lower() in serialized]

    assert leaked == []


def test_schema_rejects_forbidden_public_text() -> None:
    payload = _build_payload()
    payload["sections"][0]["evidenceSummary"] = "provider raw traceback"

    with pytest.raises(ValidationError):
        HomepageEvidenceQualityProjection.model_validate(payload)


def test_service_has_no_runtime_provider_network_auth_or_homepage_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_evidence_quality_service.py"
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
