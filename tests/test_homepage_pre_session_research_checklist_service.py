# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage pre-session research checklist."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_pre_session_research_checklist import (
    HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_DEFAULT_AS_OF,
    HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_SCHEMA_VERSION,
    HomepagePreSessionResearchChecklistSnapshot,
)
from src.services.homepage_pre_session_research_checklist_service import (
    HomepagePreSessionResearchChecklistService,
)


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "sessionContext",
    "checklistItems",
    "researchQuestions",
    "confirmationGates",
    "evidenceNeeded",
    "relatedSections",
    "relatedAssets",
    "relatedSectors",
    "relatedThemes",
    "reviewModules",
    "confidence",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
EXPECTED_CHECKLIST_IDS = {
    "rates_pressure_review",
    "breadth_participation_review",
    "ai_infrastructure_evidence_review",
    "oil_geopolitical_premium_review",
    "credit_liquidity_stress_review",
    "after_close_developments_review",
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
    "/tmp/",
    "api_key",
    "apikey",
    "secret",
    "token",
    "cookie",
    "session_id",
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
    return HomepagePreSessionResearchChecklistService().build_snapshot().model_dump(mode="json")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_pre_session_research_checklist_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == (
        HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_NO_ADVICE_DISCLOSURE
    )
    assert HomepagePreSessionResearchChecklistSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_SCHEMA_VERSION
    )


def test_pre_session_research_checklist_is_deterministic() -> None:
    service = HomepagePreSessionResearchChecklistService()

    first = service.build_snapshot().model_dump(mode="json")
    second = service.build_snapshot().model_dump(mode="json")

    assert first == second
    assert _serialized(first) == _serialized(second)


def test_pre_session_research_checklist_covers_required_review_examples() -> None:
    payload = _build_payload()
    items = payload["checklistItems"]

    assert isinstance(items, list)
    assert len(items) == 6
    assert {item["id"] for item in items} == EXPECTED_CHECKLIST_IDS

    serialized = json.dumps(payload, ensure_ascii=False)
    for expected_phrase in (
        "Confirm whether rates pressure is easing or rising.",
        "Confirm whether breadth is broadening or narrowing.",
        "Check whether AI infrastructure leadership is still supported by evidence.",
        "Review whether oil/geopolitical risk premium is falling or rising.",
        "Check whether credit/liquidity stress is visible.",
        "Review whether after-close developments change the research queue.",
    ):
        assert expected_phrase in serialized

    for item in items:
        assert item["researchQuestion"].endswith("?")
        assert item["confirmationGates"]
        assert item["evidenceNeeded"]
        assert item["relatedSections"]
        assert item["reviewModule"]


def test_pre_session_research_checklist_uses_review_confirmation_and_evidence_language() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False)

    for expected_phrase in (
        "review",
        "confirm",
        "evidence",
        "research question",
        "confirmation gate",
        "cross-check",
        "No conclusion until",
    ):
        assert expected_phrase in serialized


def test_pre_session_research_checklist_excludes_execution_diagnostics_and_urls() -> None:
    serialized = _serialized(_build_payload())

    leaked = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_pre_session_research_checklist_schema_rejects_forbidden_text_and_version_drift() -> None:
    payload = _build_payload()
    payload["checklistItems"][0]["reviewPrompt"] = "debug provider raw payload"

    with pytest.raises(ValidationError):
        HomepagePreSessionResearchChecklistSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["schemaVersion"] = "homepage_pre_session_research_checklist_v2"

    with pytest.raises(ValidationError):
        HomepagePreSessionResearchChecklistSnapshot.model_validate(payload)


def test_pre_session_research_checklist_service_has_no_live_provider_http_or_protected_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_pre_session_research_checklist_service.py"
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
