# -*- coding: utf-8 -*-
"""Inventory contract tests for auth/RBAC route-capability boundaries."""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any

from fastapi.routing import APIRoute

from api.v1 import api_v1_router


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "auth"
APP_TSX = REPO_ROOT / "apps" / "dsa-web" / "src" / "App.tsx"
ADMIN_CAPABILITIES_TS = REPO_ROOT / "apps" / "dsa-web" / "src" / "utils" / "adminCapabilities.ts"
APP_ROUTES_TEST_TSX = REPO_ROOT / "apps" / "dsa-web" / "src" / "__tests__" / "AppRoutes.test.tsx"
AUTH_GUARD_TEST_TSX = REPO_ROOT / "apps" / "dsa-web" / "src" / "components" / "auth" / "__tests__" / "AuthGuardOverlay.test.tsx"
AUTH_ENDPOINT_TS = REPO_ROOT / "api" / "v1" / "endpoints" / "auth.py"
ADMIN_LOGS_ENDPOINT_TS = REPO_ROOT / "api" / "v1" / "endpoints" / "admin_logs.py"
ADMIN_USERS_ENDPOINT_TS = REPO_ROOT / "api" / "v1" / "endpoints" / "admin_users.py"
MARKET_PROVIDER_OPERATIONS_ENDPOINT_TS = REPO_ROOT / "api" / "v1" / "endpoints" / "market_provider_operations.py"

BACKEND_FIXTURE = FIXTURE_DIR / "backend_route_capability_inventory.json"
FRONTEND_FIXTURE = FIXTURE_DIR / "frontend_route_capability_inventory.json"

FORBIDDEN_FIXTURE_TERMS = (
    "authorization",
    "bearer ",
    "cookie",
    "set-cookie",
    "session token",
    "session-token",
    "passwordhash",
    "password_hash",
    "api_key",
    "access_token",
    "refresh_token",
    "secret",
    "private_key",
    "webhook",
)
ADMIN_CAPABILITY_CASES = {
    "/settings/system": "canReadSystemConfig",
    "/admin/logs": "canReadOpsLogs",
    "/admin/evidence-workflow": "canReadOpsLogs",
    "/admin/notifications": "canReadNotifications",
    "/admin/market-providers": "canReadProviders",
    "/admin/provider-circuits": "canReadProviders",
    "/admin/cost-observability": "canReadCostObservability",
}
EXPLICIT_AUTHENTICATED_ROUTE_EXCEPTIONS = {
    ("GET", "/api/v1/backtest/rule/runs/{run_id}/robustness-evidence.json"): {
        "auth_dependency_label": "authenticated_user",
        "capability_label": None,
        "note": "Backtest robustness evidence is authenticated-user scoped outside the admin control-plane inventory.",
    },
}
EXPECTED_TRANSITIONAL_ADMIN_USER_ALLOWLIST = {
    "agent.admin_send": {
        "surface": "agent_admin_send",
        "note_fragment": "legacy admin-only route",
        "routes": [("POST", "/api/v1/agent/chat/send")],
    },
    "scanner.admin_watchlists_and_status": {
        "surface": "scanner_admin",
        "note_fragment": "legacy admin scanner endpoints",
        "routes": [
            ("GET", "/api/v1/scanner/status"),
            ("GET", "/api/v1/scanner/watchlists/recent"),
            ("GET", "/api/v1/scanner/watchlists/today"),
        ],
    },
    "usage.admin_summary": {
        "surface": "usage_admin",
        "note_fragment": "usage summary",
        "routes": [("GET", "/api/v1/usage/summary")],
    },
    "quant.duckdb.admin_surface": {
        "surface": "quant_duckdb_admin",
        "note_fragment": "duckdb admin routes",
        "routes": [
            ("GET", "/api/v1/quant/duckdb/coverage"),
            ("GET", "/api/v1/quant/duckdb/health"),
            ("POST", "/api/v1/quant/duckdb/benchmark"),
            ("POST", "/api/v1/quant/duckdb/build-factors"),
            ("POST", "/api/v1/quant/duckdb/compare-runtime-context"),
            ("POST", "/api/v1/quant/duckdb/factor-snapshot"),
            ("POST", "/api/v1/quant/duckdb/ingest-ohlcv"),
            ("POST", "/api/v1/quant/duckdb/init"),
            ("POST", "/api/v1/quant/duckdb/validate-factor-path"),
        ],
    },
}
EXPECTED_CONTROL_PLANE_GROUP_ROUTE_COUNTS = {
    "agent.admin_send": 1,
    "scanner.admin_watchlists_and_status": 3,
    "usage.admin_summary": 1,
    "quant.duckdb.admin_surface": 9,
    "admin.users.read": 2,
    "admin.users.activity_read": 1,
    "admin.users.portfolio_read": 4,
    "admin.users.security_write": 3,
    "admin.activity.read": 1,
    "admin.logs.read": 7,
    "admin.logs.write": 1,
    "admin.notifications.read": 2,
    "admin.notifications.write": 5,
    "admin.cost.read": 4,
    "admin.providers.read": 8,
    "system.config.read": 2,
    "system.config.validate": 1,
    "system.config.write": 3,
    "system.provider_tests.write": 3,
}
BACKEND_ONLY_WRITE_CAPABILITY_LABELS = {
    "ops:notifications:write",
    "ops:providers:write",
    "ops:system_config:write",
}
FRONTEND_ADMIN_READ_CAPABILITY_LABELS = {
    "ops:notifications:read",
    "ops:providers:read",
    "ops:system_config:read",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_strings(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
        return
    if isinstance(value, str):
        yield value


def _assert_secret_free_fixture(payload: Any) -> None:
    text = "\n".join(_iter_strings(payload)).lower()
    for forbidden in FORBIDDEN_FIXTURE_TERMS:
        assert forbidden not in text


def _extract_capability_from_call(call: object | None) -> str | None:
    if call is None:
        return None
    closure = getattr(call, "__closure__", None) or ()
    for cell in closure:
        value = getattr(cell, "cell_contents", None)
        if isinstance(value, str) and ":" in value:
            return value
    try:
        source = inspect.getsource(call)
    except (OSError, TypeError):
        return None
    match = re.search(r"require_admin_capability\(\s*[\"']([^\"']+)[\"']\s*\)", source)
    if match:
        return match.group(1)
    return None


def _route_auth_metadata(route: APIRoute) -> dict[str, str | None]:
    dependency_label: str | None = None
    capability_label: str | None = None

    for dependency in route.dependant.dependencies:
        call = getattr(dependency, "call", None)
        name = getattr(call, "__name__", "") or ""
        qualname = getattr(call, "__qualname__", "") or ""
        capability = _extract_capability_from_call(call)

        if capability:
            dependency_label = "admin_capability"
            capability_label = capability
            break
        if name == "require_admin_user":
            dependency_label = dependency_label or "admin_user"
            continue
        if name == "get_current_user":
            dependency_label = dependency_label or "authenticated_user"
            continue
        if name == "get_optional_current_user":
            dependency_label = dependency_label or "optional_current_user"
            continue
        if "require_admin_capability" in qualname:
            dependency_label = "admin_capability"
            capability_label = capability_label or capability
            break

    return {
        "auth_dependency_label": dependency_label,
        "capability_label": capability_label,
    }


def _collect_live_routes() -> dict[tuple[str, str], dict[str, str | None]]:
    collected: dict[tuple[str, str], dict[str, str | None]] = {}
    for route in api_v1_router.routes:
        if not isinstance(route, APIRoute):
            continue
        metadata = _route_auth_metadata(route)
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            collected[(method, route.path)] = {
                "method": method,
                "path": route.path,
                **metadata,
            }
    return collected


def _route_matches_group(route: dict[str, str | None], group: dict[str, Any]) -> bool:
    if route["auth_dependency_label"] != group["auth_dependency_label"]:
        return False
    if route["method"] not in set(group["methods"]):
        return False
    if group["capability_label"] != route["capability_label"]:
        return False
    return re.match(group["path_pattern"], route["path"] or "") is not None


def _matched_route_signatures(
    live_routes: dict[tuple[str, str], dict[str, str | None]],
    group: dict[str, Any],
) -> list[tuple[str, str]]:
    return sorted(
        (route["method"], route["path"] or "")
        for route in live_routes.values()
        if _route_matches_group(route, group)
    )


def _extract_route_block(source: str, marker: str, closing: str) -> str:
    start = source.index(marker)
    end = source.index(closing, start)
    return source[start:end]


def _collect_wrapped_route_paths(source: str, wrapper_name: str) -> set[str]:
    pattern = re.compile(rf'<Route path="([^"]+)" element={{<{wrapper_name}>', re.MULTILINE)
    return set(pattern.findall(source))


def _auth_route_source_guards(source: str) -> dict[str, str]:
    function_pattern = re.compile(
        r'@router\.(get|post|put|delete|patch)\(\s*\n\s*"(?P<path>[^"]+)"[\s\S]*?\)\nasync def [^(]+\([^)]*\):\n(?P<body>[\s\S]*?)(?=\n@router\.|\Z)',
        re.MULTILINE,
    )
    return {
        match.group("path"): match.group("body")
        for match in function_pattern.finditer(source)
    }


def _guest_restriction_markers(path: str) -> set[str]:
    base = path.split("/:")[0]
    parent = base.rsplit("/", 1)[0] if "/" in base[1:] else base
    return {
        path,
        base,
        base + "/",
        parent,
        parent + "/",
    }


def _is_control_plane_route(route: dict[str, str | None]) -> bool:
    path = route["path"] or ""
    if path.startswith("/api/v1/admin/") or path.startswith("/api/v1/system/"):
        return True
    return path in {
        "/api/v1/agent/chat/send",
        "/api/v1/scanner/status",
        "/api/v1/scanner/watchlists/today",
        "/api/v1/scanner/watchlists/recent",
        "/api/v1/usage/summary",
        "/api/v1/quant/duckdb/health",
        "/api/v1/quant/duckdb/init",
        "/api/v1/quant/duckdb/ingest-ohlcv",
        "/api/v1/quant/duckdb/build-factors",
        "/api/v1/quant/duckdb/factor-snapshot",
        "/api/v1/quant/duckdb/validate-factor-path",
        "/api/v1/quant/duckdb/compare-runtime-context",
        "/api/v1/quant/duckdb/coverage",
        "/api/v1/quant/duckdb/benchmark",
    }


def test_auth_route_inventory_fixtures_do_not_contain_secret_like_material() -> None:
    _assert_secret_free_fixture(_load_json(BACKEND_FIXTURE))
    _assert_secret_free_fixture(_load_json(FRONTEND_FIXTURE))


def test_backend_route_capability_inventory_covers_current_dependency_guarded_routes() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    live_routes = _collect_live_routes()
    protected_live_routes = [
        route
        for route in live_routes.values()
        if route["auth_dependency_label"] in {"authenticated_user", "admin_user", "admin_capability"}
    ]

    unmatched_routes = []
    for route in protected_live_routes:
        route_key = (route["method"], route["path"])
        if route_key in EXPLICIT_AUTHENTICATED_ROUTE_EXCEPTIONS:
            expected = EXPLICIT_AUTHENTICATED_ROUTE_EXCEPTIONS[route_key]
            assert route["auth_dependency_label"] == expected["auth_dependency_label"]
            assert route["capability_label"] == expected["capability_label"]
            continue
        matched_group = next((group for group in fixture["protected_groups"] if _route_matches_group(route, group)), None)
        if matched_group is None:
            unmatched_routes.append(route)
            continue
        if matched_group["auth_dependency_label"] == "admin_user":
            assert matched_group["transitional_note"], f"missing transitional note for {matched_group['route_id']}"
        if matched_group["auth_dependency_label"] == "admin_capability":
            assert matched_group["capability_label"], f"missing capability label for {matched_group['route_id']}"

    assert unmatched_routes == []

    for group in fixture["protected_groups"]:
        matches = [route for route in protected_live_routes if _route_matches_group(route, group)]
        assert matches, f"inventory group no longer matches any live route: {group['route_id']}"


def test_authenticated_route_exceptions_remain_explicit_and_narrow() -> None:
    live_routes = _collect_live_routes()

    for route_key, expected in EXPLICIT_AUTHENTICATED_ROUTE_EXCEPTIONS.items():
        live = live_routes[route_key]
        assert live["auth_dependency_label"] == expected["auth_dependency_label"]
        assert live["capability_label"] == expected["capability_label"]
        assert "admin control-plane" in expected["note"].lower()


def test_backend_public_and_optional_user_routes_are_not_mislabeled_as_admin_only() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    live_routes = _collect_live_routes()

    for sample in fixture["public_samples"]:
        live = live_routes[(sample["method"], sample["path"])]
        expected = sample["auth_dependency_label"]
        if expected == "public":
            assert live["auth_dependency_label"] is None
        else:
            assert live["auth_dependency_label"] == expected
        assert live["capability_label"] is None


def test_admin_observability_route_inventory_keeps_capabilities_and_transitional_gaps_explicit() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    groups = {group["route_id"]: group for group in fixture["protected_groups"]}

    admin_logs_read = groups["admin.logs.read"]
    admin_logs_write = groups["admin.logs.write"]
    admin_users_read = groups["admin.users.read"]
    admin_users_activity_read = groups["admin.users.activity_read"]
    admin_activity_read = groups["admin.activity.read"]
    provider_observability = groups["admin.providers.read"]

    assert admin_users_read["auth_dependency_label"] == "admin_capability"
    assert admin_users_read["capability_label"] == "users:read"
    assert admin_users_read["transitional_note"] is None
    assert admin_users_activity_read["auth_dependency_label"] == "admin_capability"
    assert admin_users_activity_read["capability_label"] == "users:activity:read"
    assert admin_users_activity_read["transitional_note"] is None
    assert admin_activity_read["auth_dependency_label"] == "admin_capability"
    assert admin_activity_read["capability_label"] == "users:activity:read"
    assert admin_activity_read["transitional_note"] is None
    assert admin_logs_read["auth_dependency_label"] == "admin_capability"
    assert admin_logs_read["capability_label"] == "ops:logs:read"
    assert admin_logs_write["auth_dependency_label"] == "admin_capability"
    assert admin_logs_write["capability_label"] == "ops:logs:write"
    assert provider_observability["auth_dependency_label"] == "admin_capability"
    assert provider_observability["capability_label"] == "ops:providers:read"
    assert provider_observability["transitional_note"] is None

    admin_users_source = ADMIN_USERS_ENDPOINT_TS.read_text(encoding="utf-8")
    admin_logs_source = ADMIN_LOGS_ENDPOINT_TS.read_text(encoding="utf-8")
    market_provider_source = MARKET_PROVIDER_OPERATIONS_ENDPOINT_TS.read_text(encoding="utf-8")

    assert 'require_admin_capability("users:read")' in admin_users_source
    assert 'require_admin_capability("users:activity:read")' in admin_users_source
    assert 'require_admin_capability("ops:logs:read")' in admin_logs_source
    assert 'require_admin_capability("ops:logs:write")' in admin_logs_source
    assert 'require_admin_capability("ops:providers:read")' in market_provider_source


def test_remaining_require_admin_user_route_groups_are_explicitly_allowlisted() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    live_routes = _collect_live_routes()
    coarse_admin_groups = {
        group["route_id"]: group
        for group in fixture["protected_groups"]
        if group["auth_dependency_label"] == "admin_user"
    }

    assert set(coarse_admin_groups) == set(EXPECTED_TRANSITIONAL_ADMIN_USER_ALLOWLIST)

    for route_id, expected in EXPECTED_TRANSITIONAL_ADMIN_USER_ALLOWLIST.items():
        group = coarse_admin_groups[route_id]
        assert group["surface"] == expected["surface"]
        assert group["capability_label"] is None
        assert group["transitional_note"]
        assert expected["note_fragment"] in group["transitional_note"].lower()
        assert _matched_route_signatures(live_routes, group) == expected["routes"]


def test_control_plane_route_inventory_fails_closed_without_explicit_classification() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    live_routes = _collect_live_routes()
    groups = {group["route_id"]: group for group in fixture["protected_groups"]}

    assert set(EXPECTED_CONTROL_PLANE_GROUP_ROUTE_COUNTS).issubset(groups)

    classified_route_signatures: set[tuple[str, str]] = set()
    for route_id, expected_count in EXPECTED_CONTROL_PLANE_GROUP_ROUTE_COUNTS.items():
        matches = _matched_route_signatures(live_routes, groups[route_id])
        assert len(matches) == expected_count, f"unexpected route count for {route_id}: {matches}"
        classified_route_signatures.update(matches)

    live_control_plane_signatures = {
        (route["method"], route["path"] or "")
        for route in live_routes.values()
        if route["auth_dependency_label"] in {"admin_user", "admin_capability"} and _is_control_plane_route(route)
    }

    assert classified_route_signatures == live_control_plane_signatures


def test_backend_write_only_capabilities_do_not_leak_into_frontend_read_route_flags() -> None:
    frontend_fixture = _load_json(FRONTEND_FIXTURE)
    frontend_capability_labels = {
        entry["capability_label"]
        for entry in frontend_fixture["admin_surface_routes"]
    }
    capability_source = ADMIN_CAPABILITIES_TS.read_text(encoding="utf-8")

    assert FRONTEND_ADMIN_READ_CAPABILITY_LABELS.issubset(frontend_capability_labels)
    assert frontend_capability_labels.isdisjoint(BACKEND_ONLY_WRITE_CAPABILITY_LABELS)
    for capability in BACKEND_ONLY_WRITE_CAPABILITY_LABELS:
        assert capability not in capability_source


def test_request_guarded_auth_routes_remain_explicit_in_auth_endpoint_source() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    auth_source = AUTH_ENDPOINT_TS.read_text(encoding="utf-8")
    route_bodies = _auth_route_source_guards(auth_source)

    for entry in fixture["request_guarded_auth_routes"]:
        guard_kind = entry["guard_kind"]
        methods = entry.get("methods") or [entry["method"]]
        if "path_pattern" in entry:
            pattern = re.compile(entry["path_pattern"])
            matched_paths = [path for path in route_bodies if pattern.match(f"/api/v1/auth{path}")]
            assert matched_paths, f"missing auth route pattern {entry['route_id']}"
            for path in matched_paths:
                body = route_bodies[path]
                if guard_kind == "request_current_user":
                    assert (
                        "resolve_current_user(request)" in body
                        or "_serialize_current_user(request)" in body
                        or "_require_admin_current_user(request)" in body
                    ), f"missing request guard in {path}"
        else:
            api_path = entry["path"].replace("/api/v1/auth", "")
            assert api_path in route_bodies, f"missing auth route {entry['route_id']}"
            body = route_bodies[api_path]
            if guard_kind == "request_current_user":
                assert (
                    "resolve_current_user(request)" in body
                    or "_serialize_current_user(request)" in body
                    or "_require_admin_current_user(request)" in body
                ), f"missing request guard in {entry['path']}"
            else:
                assert "resolve_current_user(request)" not in body and "_serialize_current_user(request)" not in body
        assert methods


def test_frontend_route_inventory_matches_admin_capability_map_and_wrapper_boundaries() -> None:
    fixture = _load_json(FRONTEND_FIXTURE)
    app_source = APP_TSX.read_text(encoding="utf-8")
    capability_source = ADMIN_CAPABILITIES_TS.read_text(encoding="utf-8")
    restricted_block = _extract_route_block(app_source, "const isGuestRestrictedPath = (", ");")

    admin_wrapped_paths = _collect_wrapped_route_paths(app_source, "AdminSurfaceRoute")
    registered_wrapped_paths = _collect_wrapped_route_paths(app_source, "RegisteredSurfaceRoute")

    for entry in fixture["admin_surface_routes"]:
        assert entry["path"] in admin_wrapped_paths
        assert entry["localized_path"] in admin_wrapped_paths
        assert any(marker in restricted_block for marker in _guest_restriction_markers(entry["path"]))
        expected_flag = entry["capability_flag"]
        route_prefix = entry["path"].replace("/:userId", "").replace("/:runId", "")
        if entry["route_id"] == "admin.user_activity":
            assert "pathname.endsWith('/activity') ? capabilityFlags.canReadUserActivity : capabilityFlags.canReadUsers" in capability_source
        elif route_prefix in ADMIN_CAPABILITY_CASES:
            assert ADMIN_CAPABILITY_CASES[route_prefix] == expected_flag
            assert route_prefix in capability_source
            assert expected_flag in capability_source

    for entry in fixture["registered_surface_routes"]:
        assert entry["path"] in registered_wrapped_paths
        assert entry["localized_path"] in registered_wrapped_paths

    for prefix in fixture["guest_redirect_prefixes"]:
        assert any(marker in restricted_block for marker in _guest_restriction_markers(prefix))

    for entry in fixture["public_routes"]:
        assert f'path="{entry["path"]}"' in app_source
        assert f'path="{entry["localized_path"]}"' in app_source or entry["localized_path"] == "guest"

    assert "/market/rotation-radar" not in registered_wrapped_paths
    assert "/market/rotation-radar" not in admin_wrapped_paths


def test_frontend_guest_paywall_and_admin_gate_boundaries_are_represented_in_existing_tests() -> None:
    fixture = _load_json(FRONTEND_FIXTURE)
    app_routes_test_source = APP_ROUTES_TEST_TSX.read_text(encoding="utf-8")
    auth_guard_test_source = AUTH_GUARD_TEST_TSX.read_text(encoding="utf-8")

    for entry in fixture["guest_paywall_routes"]:
        assert entry["test_probe"] in app_routes_test_source or entry["test_probe"] in auth_guard_test_source

    assert "/settings/system" in app_routes_test_source
    assert "/zh/admin/evidence-workflow" in app_routes_test_source
    assert "/zh/admin/cost-observability" in app_routes_test_source
    assert "Sign in to unlock Portfolio" in auth_guard_test_source
    assert "登录解锁 市场总览" in auth_guard_test_source
