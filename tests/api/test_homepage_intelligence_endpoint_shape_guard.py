# -*- coding: utf-8 -*-
"""Shape guard for the homepage intelligence public endpoint."""

from __future__ import annotations

import json
import os
import sys
import types
from dataclasses import dataclass
from importlib import util
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute
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
ROUTE_PATH = "/api/v1/homepage/intelligence"


def _load_homepage_intelligence_module():
    original_api_deps = sys.modules.get("api.deps")
    sys.modules["api.deps"] = types.SimpleNamespace(
        CurrentUser=_CurrentUser,
        get_optional_current_user=_optional_current_user,
    )
    try:
        endpoint_spec = util.spec_from_file_location(
            "homepage_intelligence_under_test",
            ENDPOINT_PATH,
        )
        assert endpoint_spec is not None and endpoint_spec.loader is not None
        module = util.module_from_spec(endpoint_spec)
        endpoint_spec.loader.exec_module(module)
        return module
    finally:
        if original_api_deps is None:
            sys.modules.pop("api.deps", None)
        else:
            sys.modules["api.deps"] = original_api_deps


homepage_intelligence = _load_homepage_intelligence_module()


LEGACY_TOP_LEVEL_KEYS = {
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
ADDITIVE_TOP_LEVEL_KEYS = {
    "intelligenceCockpit",
    "sectionLayout",
    "uatReadiness",
    "cockpitModules",
}
EXPECTED_TOP_LEVEL_KEYS = LEGACY_TOP_LEVEL_KEYS | ADDITIVE_TOP_LEVEL_KEYS
EXPECTED_COCKPIT_MODULE_KEYS = (
    "dailyMarketBrief",
    "riskRegime",
    "crossAssetIndicators",
    "eventImpactMap",
    "driverChain",
    "themeCapitalFlow",
    "researchPriorities",
    "evidenceQuality",
    "ratesPricing",
    "volatilityPositioning",
    "liquidityCredit",
    "marketBreadth",
    "afterCloseDevelopments",
    "scenarioWatchlist",
    "earningsCatalysts",
    "geopoliticalCommodityRisk",
    "aiCapexInfrastructure",
    "policyRegulationWatch",
    "styleLeadershipRotation",
    "preSessionResearchChecklist",
)
FORBIDDEN_PUBLIC_MARKERS = (
    "provider",
    "cache",
    "fallback",
    "runtime",
    "debug",
    "raw",
    "internal",
    "diagnostic",
    "token",
    "secret",
    "cookie",
    "traceback",
)
EXPECTED_COCKPIT_MODULE_FIELDS = {
    "key",
    "label",
    "status",
    "asOf",
    "summary",
    "dataQuality",
    "evidenceQuality",
    "sampleOnly",
    "observationOnly",
    "noLiveAvailabilityClaim",
}


def _route_only_client() -> TestClient:
    app = FastAPI()
    app.include_router(homepage_intelligence.router, prefix="/api/v1/homepage")
    return TestClient(app)


def _payload() -> dict[str, object]:
    client = _route_only_client()
    try:
        response = client.get(ROUTE_PATH)
    finally:
        client.close()

    assert response.status_code == 200
    return response.json()


def _walk(value: object, path: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    paths: list[tuple[str, ...]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = (*path, str(key))
            paths.append(child_path)
            paths.extend(_walk(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_walk(item, (*path, str(index))))
    return paths


def _serialized(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).lower()


def test_homepage_intelligence_endpoint_keeps_legacy_shape_and_additive_public_keys() -> None:
    payload = _payload()

    assert set(payload) == EXPECTED_TOP_LEVEL_KEYS
    assert LEGACY_TOP_LEVEL_KEYS <= set(payload)
    assert ADDITIVE_TOP_LEVEL_KEYS <= set(payload)
    assert payload["sampleOnly"] is True
    assert payload["noAdviceDisclosure"]
    assert isinstance(payload["sectionLayout"], dict)
    assert isinstance(payload["uatReadiness"], dict)
    assert isinstance(payload["cockpitModules"], dict)
    assert payload["cockpitModules"]["schemaVersion"] == "homepage_cockpit_modules_v1"
    assert payload["cockpitModules"]["sampleOnly"] is True
    assert payload["cockpitModules"]["moduleOrder"] == list(EXPECTED_COCKPIT_MODULE_KEYS)
    assert payload["cockpitModules"]["moduleCount"] == len(EXPECTED_COCKPIT_MODULE_KEYS)
    assert [module["key"] for module in payload["cockpitModules"]["modules"]] == list(
        EXPECTED_COCKPIT_MODULE_KEYS
    )


def test_homepage_intelligence_cockpit_modules_are_public_safe_projections() -> None:
    cockpit_modules = _payload()["cockpitModules"]
    leaked_paths = [
        ".".join(path)
        for path in _walk(cockpit_modules)
        if any(marker in path[-1].lower().replace("_", "").replace("-", "") for marker in FORBIDDEN_PUBLIC_MARKERS)
    ]
    serialized = _serialized(cockpit_modules)

    assert leaked_paths == []
    for marker in FORBIDDEN_PUBLIC_MARKERS:
        assert marker not in serialized
    for module in cockpit_modules["modules"]:
        assert set(module) == EXPECTED_COCKPIT_MODULE_FIELDS
        assert module["sampleOnly"] is True
        assert module["observationOnly"] is True
        assert module["noLiveAvailabilityClaim"] is True


def test_homepage_intelligence_response_remains_json_serializable() -> None:
    payload = _payload()

    assert json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True)) == payload


def test_homepage_intelligence_route_inventory_has_one_homepage_intelligence_route() -> None:
    app = FastAPI()
    app.include_router(homepage_intelligence.router, prefix="/api/v1/homepage")
    routes = [
        (method, route.path, route.name)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in sorted(route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    ]

    assert routes == [("GET", "/api/v1/homepage/intelligence", "get_homepage_intelligence")]
