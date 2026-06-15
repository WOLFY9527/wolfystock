# -*- coding: utf-8 -*-
"""Contract tests for the bounded homepage intelligence metadata endpoint."""

from __future__ import annotations

import json
import os
import sys
import types
from dataclasses import dataclass
from importlib import util
from pathlib import Path

os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")
if "orjson" not in sys.modules:
    sys.modules["orjson"] = types.SimpleNamespace(
        OPT_NON_STR_KEYS=0,
        OPT_SERIALIZE_NUMPY=0,
        dumps=lambda value, option=0: json.dumps(value).encode("utf-8"),
        loads=json.loads,
    )
sys.modules.setdefault("greenlet", None)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.homepage_intelligence_service import HomepageIntelligenceService


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

FORBIDDEN_ADVICE_TERMS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "下单",
    "立即交易",
    "交易信号",
    "交易指令",
    "交易执行",
    "目标价",
    "止损",
    "止盈",
    "收益预测",
    "AI推荐",
    "智能选股",
    "recommendation",
    "buy now",
    "sell now",
    "place order",
    "target price",
)
FORBIDDEN_INTERNAL_MARKERS = (
    "provider",
    "fallback",
    "diagnostic",
    "debug",
    "traceback",
    "raw payload",
    "raw_provider",
    "raw",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "sourceType",
    "reasonCode",
    "trustLevel",
    "scaffold",
    "token",
    "secret",
    "cookie",
    "session_id",
    "api key",
    "http://",
    "https://",
    "/users/",
)
FORBIDDEN_LIVE_DATA_CLAIMS = (
    "live data",
    "实时数据",
    "real-time",
    "realtime",
)
DEMO_MARKER_KEYS = {"sampleData", "demoPayload"}


def _walk(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, (*path, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, (*path, str(index)))


def _path_text(path: tuple[str, ...]) -> str:
    return ".".join(path)


def _is_demo_fixture_path(path: tuple[str, ...]) -> bool:
    return len(path) >= 4 and path[0] == "demo" and path[1] == "scenarios"


def _build_payload() -> dict:
    return HomepageIntelligenceService().build_bundle()


def _route_only_client() -> TestClient:
    app = FastAPI()
    app.include_router(homepage_intelligence.router, prefix="/api/v1/homepage")
    return TestClient(app)


def test_homepage_intelligence_endpoint_returns_stable_top_level_shape() -> None:
    client = _route_only_client()
    try:
        response = client.get(ROUTE_PATH)
    finally:
        client.close()

    assert response.status_code == 200
    payload = response.json()

    assert set(payload) == {
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
    assert payload["schemaVersion"] == "homepage_intelligence_v1"
    assert payload["status"] in {"ready", "partial", "no_evidence", "unavailable"}
    assert payload["scope"] == "homepage_ui_uat_metadata"
    assert payload["sampleOnly"] is True
    assert payload["asOf"] == "2026-06-14T09:30:00Z"
    assert payload["capabilities"]["schemaVersion"] == "homepage_capabilities_v1"
    assert payload["moduleManifest"]["asOf"] == "2026-06-14T09:30:00Z"
    assert payload["sessionStatus"]["asOf"] == "2026-06-14T09:30:00Z"
    assert set(payload["capabilities"]) == {
        "schemaVersion",
        "status",
        "sections",
        "capabilities",
        "dataQuality",
        "noAdviceDisclosure",
    }
    assert set(payload["moduleManifest"]) == {
        "status",
        "asOf",
        "modules",
        "dataQuality",
        "noAdviceDisclosure",
    }
    assert set(payload["sessionStatus"]) == {
        "status",
        "market",
        "sessionState",
        "label",
        "asOf",
        "timezone",
        "message",
        "dataQuality",
        "noAdviceDisclosure",
    }
    assert set(payload["sourceFreshness"]) == {
        "status",
        "asOf",
        "sources",
        "overallFreshness",
        "staleCount",
        "unavailableCount",
        "message",
        "noAdviceDisclosure",
    }
    assert payload["demo"]["defaultScenario"] == "happy_path"
    assert set(payload["demo"]["scenarios"]) == {"happy_path", "degraded_example"}


def test_homepage_intelligence_endpoint_is_anonymous_safe_and_optional_auth() -> None:
    client = _route_only_client()
    try:
        response = client.get(ROUTE_PATH)
    finally:
        client.close()

    assert response.status_code == 200
    endpoint_source = ENDPOINT_PATH.read_text(encoding="utf-8")
    assert "get_optional_current_user" in endpoint_source
    assert "Depends(get_optional_current_user)" in endpoint_source
    assert '"/intelligence"' in endpoint_source
    assert "response_model=HomepageIntelligenceResponse" in endpoint_source


def test_homepage_intelligence_service_build_bundle_validates_and_serializes() -> None:
    payload = HomepageIntelligenceService().build_bundle()
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    assert payload["schemaVersion"] == "homepage_intelligence_v1"
    assert payload["capabilities"]["schemaVersion"] == "homepage_capabilities_v1"
    for marker in FORBIDDEN_ADVICE_TERMS:
        assert marker.lower() not in serialized


def test_homepage_intelligence_route_is_registered_in_v1_router() -> None:
    router_source = ROUTER_PATH.read_text(encoding="utf-8")

    assert "homepage_intelligence" in router_source
    assert "homepage_intelligence.router" in router_source
    assert 'prefix="/homepage"' in router_source


def test_homepage_intelligence_payload_avoids_advice_diagnostics_and_live_claims() -> None:
    client = _route_only_client()
    try:
        response = client.get(ROUTE_PATH)
    finally:
        client.close()

    assert response.status_code == 200
    serialized = json.dumps(response.json(), ensure_ascii=False).lower()

    for marker in FORBIDDEN_ADVICE_TERMS:
        assert marker.lower() not in serialized
    for marker in FORBIDDEN_INTERNAL_MARKERS:
        assert marker.lower() not in serialized
    for marker in FORBIDDEN_LIVE_DATA_CLAIMS:
        assert marker.lower() not in serialized


def test_homepage_intelligence_demo_markers_are_scoped_to_demo_fixtures() -> None:
    payload = _build_payload()
    marker_paths = [
        (*path, key)
        for path, value in _walk(payload)
        if isinstance(value, dict)
        for key in value
        if key in DEMO_MARKER_KEYS
    ]

    assert marker_paths
    assert all(_is_demo_fixture_path(path) for path in marker_paths), [
        _path_text(path) for path in marker_paths
    ]


def test_homepage_intelligence_metadata_sections_do_not_claim_live_data() -> None:
    payload = _build_payload()
    metadata = {
        key: payload[key]
        for key in ("capabilities", "moduleManifest", "sessionStatus", "sourceFreshness")
    }
    serialized = json.dumps(metadata, ensure_ascii=False).lower()

    for marker in FORBIDDEN_LIVE_DATA_CLAIMS:
        assert marker.lower() not in serialized
    assert "sampledata" not in serialized
    assert "demopayload" not in serialized


def test_homepage_intelligence_payload_has_no_internal_keys_or_urls() -> None:
    payload = _build_payload()
    key_paths = [
        _path_text((*path, key))
        for path, value in _walk(payload)
        if isinstance(value, dict)
        for key in value
        for marker in FORBIDDEN_INTERNAL_MARKERS
        if marker.lower().replace("_", "") in key.lower().replace("_", "")
    ]
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    assert key_paths == []
    for marker in FORBIDDEN_INTERNAL_MARKERS:
        assert marker.lower() not in serialized


def test_homepage_intelligence_response_remains_json_serializable() -> None:
    payload = _build_payload()
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert json.loads(encoded) == payload
