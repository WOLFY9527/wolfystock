# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage Style Leadership Rotation contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_style_leadership_rotation import (
    HOMEPAGE_STYLE_GROUPS,
    HOMEPAGE_STYLE_LEADERSHIP_ROTATION_DEFAULT_AS_OF,
    HOMEPAGE_STYLE_LEADERSHIP_ROTATION_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_STYLE_LEADERSHIP_ROTATION_SCHEMA_VERSION,
    HomepageStyleLeadershipRotationSnapshot,
)
from src.services.homepage_style_leadership_rotation_service import (
    HomepageStyleLeadershipRotationService,
)


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "rotationWindow",
    "leadershipRegime",
    "styleLeaders",
    "styleLaggards",
    "rotationSignals",
    "confirmationStatus",
    "breadthConfirmation",
    "volatilityConfirmation",
    "ratesSensitivity",
    "affectedSectors",
    "affectedThemes",
    "missingEvidence",
    "watchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
EXPECTED_STYLE_GROUPS = {
    "growth",
    "value",
    "quality",
    "momentum",
    "defensive",
    "cyclicals",
    "large_cap",
    "small_cap",
}
PUBLIC_STATES = {"confirmed", "proxy", "conflicting", "no_evidence", "unavailable"}
TREND_STATES = {"leading", "lagging", "mixed", "watch", "unavailable"}
DATA_QUALITY_STATES = {"deterministic", "static_sample", "partial", "unavailable"}
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
    "financial advice",
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
    "live data",
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
    "src.services.homepage_demo_payload_service",
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_payload() -> dict[str, object]:
    return HomepageStyleLeadershipRotationService().build_snapshot().model_dump(mode="json")


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


def test_style_leadership_rotation_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_STYLE_LEADERSHIP_ROTATION_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_STYLE_LEADERSHIP_ROTATION_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_STYLE_LEADERSHIP_ROTATION_NO_ADVICE_DISCLOSURE
    assert HomepageStyleLeadershipRotationSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_STYLE_LEADERSHIP_ROTATION_SCHEMA_VERSION
    )


def test_style_leadership_rotation_output_is_deterministic() -> None:
    service = HomepageStyleLeadershipRotationService()

    first = service.build_snapshot().model_dump(mode="json")
    second = service.build_snapshot().model_dump(mode="json")

    assert first == second
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second,
        ensure_ascii=False,
        sort_keys=True,
    )


def test_style_leadership_rotation_covers_required_style_groups_in_order() -> None:
    payload = _build_payload()
    signals = payload["rotationSignals"]

    assert tuple(signal["styleGroup"] for signal in signals) == HOMEPAGE_STYLE_GROUPS
    assert {signal["styleGroup"] for signal in signals} == EXPECTED_STYLE_GROUPS
    assert {signal["state"] for signal in signals} == PUBLIC_STATES

    covered_by_leaders_and_laggards = {
        item["styleGroup"] for item in payload["styleLeaders"] + payload["styleLaggards"]
    }
    assert {"growth", "quality", "large_cap", "small_cap", "cyclicals"}.issubset(
        covered_by_leaders_and_laggards
    )


def test_style_leadership_rotation_public_states_are_explicit_across_sections() -> None:
    payload = _build_payload()

    for signal in payload["rotationSignals"]:
        assert signal["state"] in PUBLIC_STATES
        assert signal["trend"] in TREND_STATES
        assert signal["signalLabel"]
        assert signal["observation"]

    for section_key in (
        "confirmationStatus",
        "breadthConfirmation",
        "volatilityConfirmation",
        "ratesSensitivity",
    ):
        section = payload[section_key]
        assert section["state"] in PUBLIC_STATES
        assert section["label"]
        assert section["summary"]

    for area in payload["affectedSectors"] + payload["affectedThemes"]:
        assert area["state"] in PUBLIC_STATES
        assert area["name"]
        assert area["relationship"]


def test_style_leadership_rotation_quality_and_missing_evidence_are_public_safe() -> None:
    payload = _build_payload()

    assert payload["evidenceQuality"]["state"] in PUBLIC_STATES
    assert payload["dataQuality"]["state"] in DATA_QUALITY_STATES
    assert payload["missingEvidence"]
    assert payload["watchPoints"]
    assert "观察" in str(payload["noAdviceDisclosure"])


def test_style_leadership_rotation_excludes_advice_execution_and_internal_markers() -> None:
    serialized = _serialized_values(_build_payload())

    leaked = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_style_leadership_rotation_schema_rejects_forbidden_text_and_extra_fields() -> None:
    payload = _build_payload()
    payload["rotationSignals"][0]["observation"] = "debug raw provider payload"

    with pytest.raises(ValidationError):
        HomepageStyleLeadershipRotationSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["debug"] = "internal"

    with pytest.raises(ValidationError):
        HomepageStyleLeadershipRotationSnapshot.model_validate(payload)


def test_style_leadership_rotation_schema_rejects_missing_state_or_group_coverage() -> None:
    payload = _build_payload()
    payload["rotationSignals"][7]["state"] = "proxy"

    with pytest.raises(ValidationError):
        HomepageStyleLeadershipRotationSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["rotationSignals"] = list(reversed(payload["rotationSignals"]))

    with pytest.raises(ValidationError):
        HomepageStyleLeadershipRotationSnapshot.model_validate(payload)


def test_style_leadership_rotation_service_has_no_live_http_or_protected_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_style_leadership_rotation_service.py"
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
