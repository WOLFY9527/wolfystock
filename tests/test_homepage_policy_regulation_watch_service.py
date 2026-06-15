# -*- coding: utf-8 -*-
"""Focused tests for the standalone homepage Policy and Regulation Watch contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_policy_regulation_watch import (
    HOMEPAGE_POLICY_REGULATION_WATCH_DEFAULT_AS_OF,
    HOMEPAGE_POLICY_REGULATION_WATCH_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_POLICY_REGULATION_WATCH_SCHEMA_VERSION,
    HomepagePolicyRegulationWatchSnapshot,
)
from src.services.homepage_policy_regulation_watch_service import (
    HomepagePolicyRegulationWatchService,
)


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "policyWindow",
    "policyEvents",
    "regulationEvents",
    "monetaryPolicyContext",
    "fiscalPolicyContext",
    "industrialPolicyContext",
    "affectedAssets",
    "affectedSectors",
    "affectedThemes",
    "confidence",
    "missingEvidence",
    "watchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
EXPECTED_CATEGORIES = {
    "Fed communication",
    "Treasury issuance / auction pressure",
    "fiscal spending",
    "industrial policy",
    "AI regulation",
    "energy policy",
    "China policy support",
    "market-structure regulation",
}
EVENT_KEYS = [
    "category",
    "observation",
    "marketArea",
    "affectedAssets",
    "affectedSectors",
    "affectedThemes",
    "evidenceState",
]
CONTEXT_KEYS = [
    "label",
    "observation",
    "marketTransmission",
    "evidenceState",
]
ALLOWED_EVIDENCE_STATES = {"sample_proxy", "no_evidence", "unavailable"}
ALLOWED_CONFIDENCE_STATES = {"low", "medium", "unavailable"}
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
    "live news",
    "real-time",
    "realtime",
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
    "src.services.homepage_scenario_watchlist_service",
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_payload() -> dict[str, object]:
    return HomepagePolicyRegulationWatchService().build_snapshot().model_dump(mode="json")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_policy_regulation_watch_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_POLICY_REGULATION_WATCH_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_POLICY_REGULATION_WATCH_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_POLICY_REGULATION_WATCH_NO_ADVICE_DISCLOSURE
    assert HomepagePolicyRegulationWatchSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_POLICY_REGULATION_WATCH_SCHEMA_VERSION
    )


def test_policy_regulation_watch_output_is_deterministic() -> None:
    service = HomepagePolicyRegulationWatchService()

    first = service.build_snapshot().model_dump(mode="json")
    second = service.build_snapshot().model_dump(mode="json")

    assert first == second
    assert _serialized(first) == _serialized(second)


def test_policy_regulation_watch_covers_required_categories() -> None:
    payload = _build_payload()
    events = payload["policyEvents"] + payload["regulationEvents"]

    assert {event["category"] for event in events} == EXPECTED_CATEGORIES
    for event in events:
        assert list(event.keys()) == EVENT_KEYS
        assert event["evidenceState"] in ALLOWED_EVIDENCE_STATES
        assert event["observation"]
        assert event["marketArea"]
        assert event["affectedAssets"]
        assert event["affectedSectors"]
        assert event["affectedThemes"]


def test_policy_regulation_watch_contexts_are_marked_as_observation_only() -> None:
    payload = _build_payload()

    assert payload["policyWindow"]["evidenceState"] == "sample_proxy"
    for key in ("monetaryPolicyContext", "fiscalPolicyContext", "industrialPolicyContext"):
        context = payload[key]
        assert list(context.keys()) == CONTEXT_KEYS
        assert context["evidenceState"] in ALLOWED_EVIDENCE_STATES
        assert context["observation"]
        assert context["marketTransmission"]

    assert payload["confidence"] in ALLOWED_CONFIDENCE_STATES
    assert payload["confidence"] == "low"
    assert len(payload["missingEvidence"]) >= 4
    assert len(payload["watchPoints"]) >= 5


def test_policy_regulation_watch_public_output_uses_research_language() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False)

    for expected_phrase in (
        "observation-only",
        "sample proxy",
        "needs confirmation",
        "not connected to current policy releases",
        "affected market areas",
        "research context",
    ):
        assert expected_phrase in serialized


def test_policy_regulation_watch_excludes_advice_execution_and_internal_markers() -> None:
    serialized = _serialized(_build_payload())

    leaked = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_policy_regulation_watch_schema_rejects_forbidden_public_text() -> None:
    payload = _build_payload()
    payload["policyEvents"][0]["observation"] = "debug raw provider payload"

    with pytest.raises(ValidationError):
        HomepagePolicyRegulationWatchSnapshot.model_validate(payload)


def test_policy_regulation_watch_schema_rejects_unmarked_real_data_claims() -> None:
    payload = _build_payload()
    payload["policyEvents"][0]["evidenceState"] = "verified_current"

    with pytest.raises(ValidationError):
        HomepagePolicyRegulationWatchSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["schemaVersion"] = "homepage_policy_regulation_watch_v2"

    with pytest.raises(ValidationError):
        HomepagePolicyRegulationWatchSnapshot.model_validate(payload)


def test_policy_regulation_watch_service_has_no_live_provider_http_or_protected_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_policy_regulation_watch_service.py"
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
