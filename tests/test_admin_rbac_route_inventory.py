# -*- coding: utf-8 -*-
"""Tests for the static admin RBAC route inventory helper."""

from __future__ import annotations

import builtins
import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "admin_rbac_route_inventory.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("admin_rbac_route_inventory", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_fixture_repo(tmp_path: Path) -> Path:
    endpoints = tmp_path / "api" / "v1" / "endpoints"
    endpoints.mkdir(parents=True)
    (tmp_path / "api" / "v1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "api" / "v1" / "router.py").write_text(
        """
from fastapi import APIRouter
from api.v1.endpoints import fixture_admin, fixture_ops

router = APIRouter(prefix="/api/v1")
router.include_router(fixture_admin.router, prefix="/admin", tags=["FixtureAdmin"])
router.include_router(fixture_ops.router, prefix="/ops", tags=["FixtureOps"])
""".strip(),
        encoding="utf-8",
    )
    (endpoints / "fixture_admin.py").write_text(
        '''
from typing import Annotated
from fastapi import APIRouter, Depends
from api.deps import CurrentUser, require_admin_capability, require_admin_user, require_recent_admin_reauth

router = APIRouter()


def _require_security_write(
    current_user: CurrentUser = Depends(require_admin_capability("users:security:write")),
) -> CurrentUser:
    return require_recent_admin_reauth(current_user, max_age_minutes=5)


def unknown_admin_guard():
    return object()


@router.get("/users")
def list_users(_: CurrentUser = Depends(require_admin_user)):
    return {}


@router.post("/users/{user_id}/disable")
def disable_user(current_user: CurrentUser = Depends(_require_security_write)):
    return {}


@router.get("/unknown")
def unknown_admin(_: Annotated[object, Depends(unknown_admin_guard)]):
    return {}
'''.strip(),
        encoding="utf-8",
    )
    (endpoints / "fixture_ops.py").write_text(
        '''
from fastapi import APIRouter, Depends
from api.deps import CurrentUser, require_admin_capability, require_admin_capability_with_unlock

router = APIRouter()


@router.get("/logs", dependencies=[Depends(require_admin_capability("ops:logs:read"))])
def read_logs():
    return {}


@router.put("/config")
def update_config(
    _: CurrentUser = Depends(require_admin_capability_with_unlock(require_admin_capability("ops:system_config:write"))),
):
    return {}
'''.strip(),
        encoding="utf-8",
    )
    return tmp_path


def test_inventory_classifies_coarse_capability_and_mixed_families(tmp_path: Path):
    module = _load_script()
    root = _write_fixture_repo(tmp_path)

    inventory = module.build_inventory(repo_root=root)
    routes = {(tuple(item["methods"]), item["path"]): item for item in inventory["routes"]}

    coarse = routes[(("GET",), "/api/v1/admin/users")]
    assert coarse["routeFamily"] == "FixtureAdmin"
    assert coarse["guardStyle"] == "coarse_admin"
    assert coarse["classification"] == "coarse_admin_guarded"
    assert coarse["capabilityDependencies"] == []
    assert coarse["fallbackDependence"] == "direct_coarse_admin_guard"

    capability = routes[(("GET",), "/api/v1/ops/logs")]
    assert capability["routeFamily"] == "FixtureOps"
    assert capability["guardStyle"] == "capability"
    assert capability["classification"] == "capability_guarded"
    assert capability["capabilityDependencies"] == ["ops:logs:read"]
    assert capability["fallbackDependence"] == "capability_expansion_uses_coarse_fallback_when_enabled"

    sensitive = routes[(("POST",), "/api/v1/admin/users/{user_id}/disable")]
    assert sensitive["guardStyle"] == "capability_with_recent_reauth"
    assert sensitive["capabilityDependencies"] == ["users:security:write"]
    assert sensitive["reauthGuard"] is True

    unlock = routes[(("PUT",), "/api/v1/ops/config")]
    assert unlock["guardStyle"] == "capability_with_unlock_or_recent_reauth"
    assert unlock["capabilityDependencies"] == ["ops:system_config:write"]
    assert unlock["reauthGuard"] is True


def test_unknown_admin_guard_is_unclassified_not_false_safe(tmp_path: Path):
    module = _load_script()
    root = _write_fixture_repo(tmp_path)

    inventory = module.build_inventory(repo_root=root)
    unknown = next(item for item in inventory["routes"] if item["path"] == "/api/v1/admin/unknown")

    assert unknown["classification"] == "unclassified"
    assert unknown["guardStyle"] == "unclassified"
    assert unknown["capabilityDependencies"] == []
    assert "unknown_admin_guard" in unknown["unknownReasons"]


def test_inventory_output_is_sanitized_and_uses_relative_paths(tmp_path: Path):
    module = _load_script()
    root = _write_fixture_repo(tmp_path)

    payload = module.build_inventory(repo_root=root)
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert payload["readOnly"] is True
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["authBehaviorChanged"] is False
    assert payload["runtimeImportsRequired"] is False
    assert str(root) not in rendered
    assert all(not item["file"].startswith("/") for item in payload["routes"])
    assert "token" not in rendered.lower()
    assert "session id" not in rendered.lower()
    assert "password_hash" not in rendered.lower()


def test_build_inventory_does_not_import_runtime_app_db_or_provider_modules(tmp_path: Path):
    module = _load_script()
    root = _write_fixture_repo(tmp_path)
    original_import = builtins.__import__
    forbidden_prefixes = ("api", "src", "data_provider", "server")

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name.startswith(forbidden_prefixes):
            raise AssertionError(f"runtime import attempted: {name}")
        return original_import(name, globals, locals, fromlist, level)

    builtins.__import__ = guarded_import
    try:
        inventory = module.build_inventory(repo_root=root)
    finally:
        builtins.__import__ = original_import

    assert inventory["summary"]["routeCount"] == 5


def test_current_inventory_reports_frontend_admin_fail_closed_dimensions():
    module = _load_script()

    inventory = module.build_inventory(repo_root=REPO_ROOT)
    frontend_routes = {route["path"]: route for route in inventory["frontendAdminRoutes"]}

    assert inventory["schemaVersion"] == 2
    assert inventory["inspectionMethod"] == "python_ast_and_frontend_source_scan"
    assert inventory["summary"]["frontendAdminRouteCount"] == 12
    assert inventory["summary"]["frontendFailClosedRouteCount"] == 12
    assert inventory["summary"]["frontendUnknownGateCount"] == 0
    assert inventory["frontendUnknowns"] == []
    assert set(frontend_routes) == {
        "/settings/system",
        "/admin/launch-cockpit",
        "/admin/mission-control",
        "/admin/logs",
        "/admin/evidence-workflow",
        "/admin/notifications",
        "/admin/market-providers",
        "/admin/provider-circuits",
        "/admin/users",
        "/admin/users/:userId",
        "/admin/users/:userId/activity",
        "/admin/cost-observability",
    }

    for route in frontend_routes.values():
        assert route["classification"] == "frontend_admin_capability_gate"
        assert route["fallbackDependence"] == "frontend_requires_current_user_isAdmin_and_capability_payload"
        assert route["missingPayloadBehavior"] == "fail_closed_when_capability_payload_missing"
        assert route["capabilityFlag"]
        assert route["capabilityLabel"]
        assert route["unknownReasons"] == []

    assert frontend_routes["/admin/mission-control"]["gateStyle"] == "admin_surface_capability_with_feature_flag"
    assert (
        frontend_routes["/admin/mission-control"]["featureFlagDependency"]
        == "VITE_WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED"
    )
    assert frontend_routes["/admin/users/:userId/activity"]["capabilityLabel"] == "users:activity:read"
    assert frontend_routes["/admin/users/:userId"]["capabilityLabel"] == "users:read"


def test_current_inventory_reports_backend_and_frontend_fallback_surfaces():
    module = _load_script()

    inventory = module.build_inventory(repo_root=REPO_ROOT)
    surfaces = {surface["surface"]: surface for surface in inventory["fallbackSurfaces"]}

    assert set(surfaces) == {
        "backend_capability_route_expansion",
        "backend_direct_coarse_admin_routes",
        "backend_manual_admin_request_guards",
        "frontend_admin_surface_routes",
    }
    assert surfaces["backend_capability_route_expansion"]["classification"] == "coarse_fallback_remaining"
    assert (
        surfaces["backend_capability_route_expansion"]["fallbackDependencyLabel"]
        == "capability_expansion_uses_coarse_fallback_when_enabled"
    )
    assert surfaces["backend_capability_route_expansion"]["routeCount"] == inventory["summary"]["capabilityRouteCount"]
    assert "WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED" in surfaces["backend_capability_route_expansion"]["sourceLabels"]
    assert surfaces["backend_direct_coarse_admin_routes"]["routeCount"] == inventory["summary"]["coarseAdminRouteCount"]
    assert surfaces["backend_direct_coarse_admin_routes"]["routeCount"] == 0
    assert surfaces["backend_manual_admin_request_guards"]["routeCount"] == inventory["summary"]["manualAdminRouteCount"]
    assert surfaces["frontend_admin_surface_routes"]["classification"] == "fail_closed_frontend_gate"
    assert surfaces["frontend_admin_surface_routes"]["routeCount"] == inventory["summary"]["frontendFailClosedRouteCount"]
