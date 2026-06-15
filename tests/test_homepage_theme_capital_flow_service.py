# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage Theme Capital Flow contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_theme_capital_flow import (
    HOMEPAGE_THEME_CAPITAL_FLOW_DEFAULT_AS_OF,
    HOMEPAGE_THEME_CAPITAL_FLOW_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_THEME_CAPITAL_FLOW_SCHEMA_VERSION,
    HomepageThemeCapitalFlowSnapshot,
)
from src.services.homepage_theme_capital_flow_service import HomepageThemeCapitalFlowService


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "flowAuthority",
    "proxyOnly",
    "inflowThemes",
    "outflowThemes",
    "strengtheningThemes",
    "fadingThemes",
    "concentration",
    "breadth",
    "evidenceInputs",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
EXPECTED_THEMES = {
    "AI infrastructure",
    "semiconductors",
    "data centers",
    "power equipment",
    "liquid cooling",
    "software",
    "cybersecurity",
    "defense",
    "energy",
    "gold / precious metals",
    "biotech",
    "financials",
    "real estate",
    "consumer defensive",
    "small-cap growth",
}
AUTHORITY_STATES = {"authoritative", "proxy_only", "unavailable", "no_evidence"}
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
    "buy",
    "sell",
    "target price",
    "stop loss",
    "take profit",
    "provider",
    "diagnostic",
    "debug",
    "traceback",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "fallback",
    "raw",
    "http://",
    "https://",
    "/users/",
    "/tmp/",
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
    "src.services.dashboard_overview_service",
    "src.services.money_flow_service",
    "broker",
    "brokers",
    "order",
    "orders",
    "trade",
    "trades",
    "trading",
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_payload() -> dict[str, object]:
    return HomepageThemeCapitalFlowService().build_snapshot().model_dump(mode="json")


def _all_theme_items(payload: dict[str, object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for key in ("inflowThemes", "outflowThemes", "strengtheningThemes", "fadingThemes"):
        items.extend(payload[key])
    return items


def test_theme_capital_flow_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_THEME_CAPITAL_FLOW_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_THEME_CAPITAL_FLOW_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_THEME_CAPITAL_FLOW_NO_ADVICE_DISCLOSURE
    assert HomepageThemeCapitalFlowSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_THEME_CAPITAL_FLOW_SCHEMA_VERSION
    )


def test_theme_capital_flow_contract_is_deterministic() -> None:
    first = _build_payload()
    second = _build_payload()

    assert first == second
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second,
        ensure_ascii=False,
        sort_keys=True,
    )


def test_theme_capital_flow_covers_required_placeholder_themes() -> None:
    payload = _build_payload()
    theme_names = {str(item["theme"]) for item in _all_theme_items(payload)}

    assert theme_names == EXPECTED_THEMES
    assert len(_all_theme_items(payload)) == len(EXPECTED_THEMES)


def test_theme_capital_flow_distinguishes_authority_states_without_overclaiming() -> None:
    payload = _build_payload()
    flow_authority = payload["flowAuthority"]
    definitions = flow_authority["definitions"]
    evidence_inputs = payload["evidenceInputs"]

    assert payload["proxyOnly"] is True
    assert flow_authority["status"] == "proxy_only"
    assert flow_authority["authoritativeAvailable"] is False
    assert {definition["state"] for definition in definitions} == AUTHORITY_STATES
    assert {item["authority"] for item in evidence_inputs} == {
        "proxy_only",
        "unavailable",
        "no_evidence",
    }

    for item in _all_theme_items(payload):
        assert item["flowAuthority"] == "proxy_only"
        assert item["proxyOnly"] is True
        assert item["evidenceQuality"] in {
            "proxy_observation",
            "needs_confirmation",
            "mixed",
        }


def test_theme_capital_flow_exposes_concentration_breadth_and_quality() -> None:
    payload = _build_payload()

    assert payload["concentration"]["status"] == "concentrated"
    assert payload["breadth"]["status"] == "selective"
    assert payload["evidenceQuality"]["status"] == "proxy_observation"
    assert payload["dataQuality"]["status"] == "partial"
    assert payload["dataQuality"]["available"] is True


def test_theme_capital_flow_excludes_advice_execution_and_internal_markers() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False, sort_keys=True).lower()
    leaked = [marker for marker in FORBIDDEN_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_schema_rejects_forbidden_public_text_and_extra_debug_fields() -> None:
    payload = _build_payload()
    payload["dataQuality"]["summary"] = "debug provider raw payload"

    with pytest.raises(ValidationError):
        HomepageThemeCapitalFlowSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["debug"] = "internal"

    with pytest.raises(ValidationError):
        HomepageThemeCapitalFlowSnapshot.model_validate(payload)


def test_schema_rejects_authoritative_overclaim_when_proxy_only() -> None:
    payload = _build_payload()
    payload["inflowThemes"][0]["flowAuthority"] = "authoritative"

    with pytest.raises(ValidationError):
        HomepageThemeCapitalFlowSnapshot.model_validate(payload)


def test_service_has_no_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_theme_capital_flow_service.py"
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
