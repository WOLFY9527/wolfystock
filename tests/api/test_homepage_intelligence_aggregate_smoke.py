# -*- coding: utf-8 -*-
"""Aggregate smoke coverage for homepage contracts and intelligence metadata endpoint."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import os
import re
import sys
import types
from importlib import util
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")
if "orjson" not in sys.modules:
    sys.modules["orjson"] = types.SimpleNamespace(
        OPT_NON_STR_KEYS=0,
        OPT_SERIALIZE_NUMPY=0,
        dumps=lambda value, option=0: json.dumps(value).encode("utf-8"),
        loads=json.loads,
    )
sys.modules.setdefault("greenlet", None)


@dataclass(frozen=True)
class _CurrentUser:
    user_id: str = "anonymous"
    username: str = "anonymous"
    display_name: str | None = "Anonymous"
    role: str = "anonymous"
    is_admin: bool = False
    session_id: str | None = None


def _optional_current_user():
    return None


REPO_ROOT = Path(__file__).resolve().parents[2]
ENDPOINT_PATH = REPO_ROOT / "api/v1/endpoints/homepage_intelligence.py"
ROUTER_PATH = REPO_ROOT / "api/v1/router.py"
ROUTE_PATH = "/api/v1/homepage/intelligence"

sys.modules.setdefault(
    "api.deps",
    types.SimpleNamespace(CurrentUser=_CurrentUser, get_optional_current_user=_optional_current_user),
)
_endpoint_spec = util.spec_from_file_location("homepage_intelligence_under_test", ENDPOINT_PATH)
assert _endpoint_spec is not None and _endpoint_spec.loader is not None
homepage_intelligence = util.module_from_spec(_endpoint_spec)
_endpoint_spec.loader.exec_module(homepage_intelligence)


EXPECTED_TOP_LEVEL_KEYS = {
    "schemaVersion",
    "status",
    "scope",
    "asOf",
    "sampleOnly",
    "capabilities",
    "moduleManifest",
    "sessionStatus",
    "sourceFreshness",
    "demo",
    "noAdviceDisclosure",
}
EXPECTED_METADATA_SECTIONS = {
    "capabilities",
    "moduleManifest",
    "sessionStatus",
    "sourceFreshness",
    "demo",
}
SAMPLE_MARKER_KEYS = {"demoPayload", "sampleData", "scenario", "demoDisclosure"}
DISCLOSURE_KEYS = {"noAdviceDisclosure", "demoDisclosure"}
SAFE_NEGATED_BOUNDARY_PHRASES = (
    "不包含交易建议",
    "不包含投资建议",
    "不包含交易指令",
    "不提供交易判断",
    "不构成交易指令",
)
FORBIDDEN_LITERAL_TERMS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "下单",
    "立即交易",
    "交易建议",
    "交易指令",
    "投资建议",
    "止损",
    "止盈",
    "目标价",
    "收益预测",
)
FORBIDDEN_CASE_INSENSITIVE_PATTERNS = (
    re.compile(r"\bbuy\b"),
    re.compile(r"\bsell\b"),
    re.compile(r"\badd position\b"),
    re.compile(r"\breduce position\b"),
    re.compile(r"\bplace order\b"),
    re.compile(r"\bsubmit order\b"),
    re.compile(r"\btrade execution\b"),
    re.compile(r"\btrading advice\b"),
    re.compile(r"\binvestment advice\b"),
    re.compile(r"\bfinancial advice\b"),
    re.compile(r"\btarget price\b"),
    re.compile(r"\bstop[\s-]?loss\b"),
    re.compile(r"\btake[\s-]?profit\b"),
    re.compile(r"\btraceback\b"),
    re.compile(r"\btoken\b"),
    re.compile(r"\bsession[_ -]?id\b"),
    re.compile(r"\bapi[_ -]?key\b"),
    re.compile(r"\bsecret\b"),
    re.compile(r"\breason[_ -]?code\b"),
    re.compile(r"\btrust[_ -]?level\b"),
    re.compile(r"\bsource[_ -]?type\b"),
    re.compile(r"\bprovider\b"),
    re.compile(r"\binternal\b"),
    re.compile(r"\bdiagnostic(?:s)?\b"),
    re.compile(r"\bdebug\b"),
    re.compile(r"https?://"),
    re.compile(r"/users/"),
)
FORBIDDEN_LIVE_DEFAULT_PATTERNS = (
    re.compile(r"\blive data\b"),
    re.compile(r"\blive quote\b"),
    re.compile(r"\blive market\b"),
    re.compile(r"\breal[- ]time\b"),
    re.compile(r"实时数据"),
    re.compile(r"实时行情"),
)


def _route_only_client() -> TestClient:
    app = FastAPI()
    app.include_router(homepage_intelligence.router, prefix="/api/v1/homepage")
    return TestClient(app)


def _get_homepage_intelligence_payload() -> dict[str, object]:
    client = _route_only_client()
    try:
        response = client.get(ROUTE_PATH)
    finally:
        client.close()

    assert response.status_code == 200
    return response.json()


def _build_homepage_capabilities_payload() -> dict[str, object]:
    from src.services.homepage_capabilities_service import HomepageCapabilitiesService

    return HomepageCapabilitiesService().build_snapshot().model_dump(mode="json")


def _build_homepage_module_manifest_payload() -> dict[str, object]:
    from src.services.homepage_module_manifest_service import HomepageModuleManifestService

    return HomepageModuleManifestService().build_manifest(as_of="2026-06-14T09:30:00Z")


def _build_market_session_status_payload() -> dict[str, object]:
    from src.services.market_session_status_service import MarketSessionStatusService

    return MarketSessionStatusService().build_status(
        {
            "market": "US",
            "sessionState": "unknown",
            "asOf": "2026-06-14T09:30:00Z",
        }
    ).model_dump(mode="json")


def _build_source_freshness_summary_payload() -> dict[str, object]:
    from src.services.source_freshness_summary_service import build_source_freshness_summary

    return build_source_freshness_summary(
        {
            "asOf": "2026-06-14T09:30:00Z",
            "message": "固定来源新鲜度样例，仅用于界面状态联调。",
            "sources": [
                {
                    "key": "market_fixture",
                    "label": "市场样例",
                    "category": "market",
                    "freshness": "recent",
                    "asOf": "2026-06-14T09:30:00Z",
                    "publicMessage": "固定市场样例仍适合状态展示。",
                }
            ],
        }
    ).model_dump(by_alias=True)


def _build_homepage_demo_payloads() -> dict[str, dict[str, object]]:
    from src.services.homepage_demo_payload_service import HomepageDemoPayloadService

    return HomepageDemoPayloadService().build_payloads()


def _serialize(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _scrub_disclosures(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: "<disclosure>" if key in DISCLOSURE_KEYS else _scrub_disclosures(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_disclosures(item) for item in value]
    return value


def _assert_json_serializable_and_bounded(payload: object, *, max_chars: int) -> None:
    serialized = _serialize(payload)
    assert len(serialized) <= max_chars


def _assert_no_forbidden_terms(payload: object) -> None:
    scrubbed = _scrub_disclosures(payload)
    serialized = _serialize(scrubbed)
    for phrase in SAFE_NEGATED_BOUNDARY_PHRASES:
        serialized = serialized.replace(phrase, "<safe-boundary>")
    lowered = serialized.lower()

    leaked = [term for term in FORBIDDEN_LITERAL_TERMS if term in serialized]
    for pattern in FORBIDDEN_CASE_INSENSITIVE_PATTERNS:
        match = pattern.search(lowered)
        if match:
            leaked.append(match.group(0))

    assert leaked == []


def _assert_no_live_claim_markers(payload: object) -> None:
    scrubbed = _scrub_disclosures(payload)
    lowered = _serialize(scrubbed).lower()
    leaked = [pattern.pattern for pattern in FORBIDDEN_LIVE_DEFAULT_PATTERNS if pattern.search(lowered)]
    assert leaked == []


def _walk_key_paths(value: object, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    paths: list[tuple[str, ...]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_path = (*prefix, str(key))
            paths.append(key_path)
            paths.extend(_walk_key_paths(item, key_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_walk_key_paths(item, (*prefix, str(index))))
    return paths


AGGREGATE_CASES: tuple[tuple[str, Callable[[], object], int], ...] = (
    ("homepage_capabilities_service", _build_homepage_capabilities_payload, 12000),
    ("homepage_module_manifest_service", _build_homepage_module_manifest_payload, 12000),
    ("market_session_status_service", _build_market_session_status_payload, 8000),
    ("source_freshness_summary_service", _build_source_freshness_summary_payload, 8000),
    ("homepage_demo_payload_service", _build_homepage_demo_payloads, 30000),
    ("homepage_intelligence_endpoint", _get_homepage_intelligence_payload, 50000),
)


def test_homepage_contract_and_intelligence_endpoint_payloads_are_bounded_json_and_safe() -> None:
    for case_name, build_payload, max_chars in AGGREGATE_CASES:
        payload = build_payload()

        assert isinstance(payload, dict), case_name
        _assert_json_serializable_and_bounded(payload, max_chars=max_chars)
        _assert_no_forbidden_terms(payload)
        _assert_no_live_claim_markers(payload)


def test_homepage_intelligence_route_is_registered_and_route_only_safe() -> None:
    router_source = ROUTER_PATH.read_text(encoding="utf-8")
    endpoint_source = ENDPOINT_PATH.read_text(encoding="utf-8")

    assert "homepage_intelligence" in router_source
    assert "homepage_intelligence.router" in router_source
    assert 'prefix="/homepage"' in router_source
    assert "@router.get(" in endpoint_source
    assert '"/intelligence"' in endpoint_source
    assert "get_optional_current_user" in endpoint_source
    assert "Depends(get_optional_current_user)" in endpoint_source
    assert "data_provider" not in endpoint_source
    assert "requests" not in endpoint_source
    assert "httpx" not in endpoint_source


def test_homepage_intelligence_endpoint_exposes_expected_metadata_sections() -> None:
    payload = _get_homepage_intelligence_payload()

    assert set(payload) == EXPECTED_TOP_LEVEL_KEYS
    assert EXPECTED_METADATA_SECTIONS <= set(payload)
    assert payload["schemaVersion"] == "homepage_intelligence_v1"
    assert payload["scope"] == "homepage_ui_uat_metadata"
    assert payload["sampleOnly"] is True
    assert payload["asOf"] == "2026-06-14T09:30:00Z"
    assert payload["status"] in {"ready", "partial", "no_evidence", "unavailable"}
    assert isinstance(payload["capabilities"], dict)
    assert isinstance(payload["moduleManifest"], dict)
    assert isinstance(payload["sessionStatus"], dict)
    assert isinstance(payload["sourceFreshness"], dict)
    assert isinstance(payload["demo"], dict)
    assert payload["capabilities"]["schemaVersion"] == "homepage_capabilities_v1"
    assert payload["moduleManifest"]["asOf"] == payload["asOf"]
    assert payload["sessionStatus"]["asOf"] == payload["asOf"]
    assert payload["demo"]["defaultScenario"] == "happy_path"
    assert set(payload["demo"]["scenarios"]) == {"happy_path", "degraded_example"}


def test_homepage_intelligence_demo_sample_markers_stay_scoped_to_demo_payloads() -> None:
    payload = _get_homepage_intelligence_payload()
    marker_paths = [path for path in _walk_key_paths(payload) if path[-1] in SAMPLE_MARKER_KEYS]

    assert marker_paths
    for path in marker_paths:
        assert path[:2] == ("demo", "scenarios")

    for scenario_name, scenario_payload in payload["demo"]["scenarios"].items():
        assert scenario_payload["scenario"] == scenario_name
        assert scenario_payload["sampleData"] is True
        assert scenario_payload["demoPayload"] is True
        assert scenario_payload["asOf"] == payload["asOf"]
