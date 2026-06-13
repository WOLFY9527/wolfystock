#!/usr/bin/env python3
"""Static admin RBAC route inventory.

The helper reads repository source files with ``ast`` only. It does not import
the FastAPI app, route modules, database code, provider code, or environment
configuration, and it does not change runtime/auth behavior.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTER_PATH = Path("api/v1/router.py")
ENDPOINTS_DIR = Path("api/v1/endpoints")
FRONTEND_APP_PATH = Path("apps/dsa-web/src/App.tsx")
FRONTEND_ADMIN_CAPABILITIES_PATH = Path("apps/dsa-web/src/utils/adminCapabilities.ts")
ROUTE_DECORATOR_METHODS = {
    "get": ("GET",),
    "post": ("POST",),
    "put": ("PUT",),
    "patch": ("PATCH",),
    "delete": ("DELETE",),
    "options": ("OPTIONS",),
    "head": ("HEAD",),
}
IGNORED_DEPENDENCY_NAMES = {
    "get_current_user",
    "get_optional_current_user",
    "get_database_manager",
    "get_config_dep",
    "get_system_config_service",
    "get_quant_duckdb_service",
}


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_source(path: Path) -> ast.Module:
    return ast.parse(_read_source(path), filename=str(path))


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _literal_bool(node: ast.AST | None) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def _literal_string_sequence(node: ast.AST | None) -> list[str]:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: list[str] = []
        for item in node.elts:
            value = _literal_string(item)
            if value is not None:
                values.append(value)
        return values
    value = _literal_string(node)
    return [value] if value else []


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _call_name(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _expr_label(node: ast.AST | None) -> str:
    if node is None:
        return "unknown"
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Call):
        return _call_name(node.func) or "call"
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        current: ast.AST | None = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts)) if parts else "attribute"
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _join_paths(*parts: str) -> str:
    result = ""
    for raw in parts:
        if not raw:
            continue
        text = str(raw)
        if not result:
            result = text if text.startswith("/") else f"/{text}"
            continue
        if result.endswith("/"):
            result = result.rstrip("/")
        result = f"{result}/{text.lstrip('/')}"
    if not result:
        return "/"
    return result if result.startswith("/") else f"/{result}"


def _relative_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _new_guard_info() -> dict[str, Any]:
    return {
        "coarse": False,
        "manual_admin": False,
        "capabilities": set(),
        "reauth": False,
        "unlock": False,
        "mfa": False,
        "unknown": set(),
    }


def _merge_guard_info(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    target["coarse"] = bool(target["coarse"] or source["coarse"])
    target["manual_admin"] = bool(target["manual_admin"] or source["manual_admin"])
    target["reauth"] = bool(target["reauth"] or source["reauth"])
    target["unlock"] = bool(target["unlock"] or source["unlock"])
    target["mfa"] = bool(target["mfa"] or source["mfa"])
    target["capabilities"].update(source["capabilities"])
    target["unknown"].update(source["unknown"])
    return target


def _is_ignored_dependency(name: str) -> bool:
    return name in IGNORED_DEPENDENCY_NAMES or name.startswith("get_")


def _has_guard_info(info: dict[str, Any]) -> bool:
    return bool(
        info["coarse"]
        or info["manual_admin"]
        or info["capabilities"]
        or info["reauth"]
        or info["unlock"]
        or info["mfa"]
        or info["unknown"]
    )


def _admin_path(path: str) -> bool:
    return path == "/api/v1/admin" or path.startswith("/api/v1/admin/")


def _mfa_related_name(name: str | None) -> bool:
    lowered = str(name or "").lower()
    return "mfa" in lowered and any(marker in lowered for marker in ("require", "verify", "enroll", "recovery"))


def _collect_endpoint_aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "api.v1.endpoints":
            for alias in node.names:
                aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("api.v1.endpoints."):
                    module_name = alias.name.rsplit(".", 1)[-1]
                    aliases[alias.asname or module_name] = module_name
    return aliases


def _router_base_prefix(tree: ast.Module) -> str:
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "router":
                prefix = _literal_string(_keyword(node.value, "prefix"))
                if prefix is not None:
                    return prefix
    return ""


def _include_router_module(call: ast.Call) -> str | None:
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Attribute) and first.attr == "router":
        if isinstance(first.value, ast.Name):
            return first.value.id
    return None


def _collect_router_includes(repo_root: Path) -> list[dict[str, str]]:
    router_path = repo_root / ROUTER_PATH
    tree = _parse_source(router_path)
    aliases = _collect_endpoint_aliases(tree)
    base_prefix = _router_base_prefix(tree)
    includes: list[dict[str, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_name(node.func) != "include_router":
            continue
        alias = _include_router_module(node)
        if not alias:
            continue
        module_name = aliases.get(alias, alias)
        tags = _literal_string_sequence(_keyword(node, "tags"))
        family = tags[0] if tags else module_name
        includes.append(
            {
                "module": module_name,
                "prefix": _join_paths(base_prefix, _literal_string(_keyword(node, "prefix")) or ""),
                "routeFamily": family,
                "file": (ENDPOINTS_DIR / f"{module_name}.py").as_posix(),
            }
        )
    return includes


def _route_decorator_metadata(decorator: ast.AST) -> dict[str, Any] | None:
    if not isinstance(decorator, ast.Call):
        return None
    method_name = _call_name(decorator.func)
    if method_name not in ROUTE_DECORATOR_METHODS and method_name != "api_route":
        return None

    route_path = _literal_string(decorator.args[0]) if decorator.args else _literal_string(_keyword(decorator, "path"))
    if route_path is None:
        route_path = ""

    if method_name == "api_route":
        methods = tuple(method.upper() for method in _literal_string_sequence(_keyword(decorator, "methods")))
    else:
        methods = ROUTE_DECORATOR_METHODS[method_name]

    return {
        "path": route_path,
        "methods": sorted(methods),
        "line": getattr(decorator, "lineno", None),
        "includeInSchema": _literal_bool(_keyword(decorator, "include_in_schema")),
        "deprecated": _literal_bool(_keyword(decorator, "deprecated")),
        "dependencies": _keyword(decorator, "dependencies"),
    }


def _iter_route_functions(tree: ast.Module) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, dict[str, Any]]]:
    routes: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, dict[str, Any]]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            metadata = _route_decorator_metadata(decorator)
            if metadata is not None:
                routes.append((node, metadata))
    return routes


def _collect_function_nodes(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _analyze_dependency_target(
    node: ast.AST | None,
    function_nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    helper_cache: dict[str, dict[str, Any]],
    stack: set[str],
) -> dict[str, Any]:
    info = _new_guard_info()
    if node is None:
        return info
    if isinstance(node, ast.Name):
        if node.id == "require_admin_user":
            info["coarse"] = True
            return info
        if node.id == "_require_admin_current_user":
            info["manual_admin"] = True
            return info
        if node.id in {
            "require_recent_admin_reauth",
            "_require_recent_admin_reauth_response",
            "require_admin_unlock_or_recent_reauth",
        }:
            info["reauth"] = True
            if node.id == "require_admin_unlock_or_recent_reauth":
                info["unlock"] = True
            return info
        if node.id in function_nodes:
            helper_info = _analyze_function(function_nodes[node.id], function_nodes, helper_cache, stack)
            if not _has_guard_info(helper_info):
                helper_info["unknown"].add(node.id)
            return helper_info
        if not _is_ignored_dependency(node.id):
            info["unknown"].add(node.id)
        return info
    if isinstance(node, ast.Call):
        return _analyze_expr(node, function_nodes, helper_cache, stack)
    label = _expr_label(node)
    if label and not _is_ignored_dependency(label):
        info["unknown"].add(label)
    return info


def _extract_depends_target(call: ast.Call) -> ast.AST | None:
    if call.args:
        return call.args[0]
    return _keyword(call, "dependency")


def _extract_capabilities_from_call(call: ast.Call) -> set[str]:
    if not call.args:
        return set()
    first = call.args[0]
    return {value for value in _literal_string_sequence(first) if ":" in value}


def _analyze_expr(
    node: ast.AST,
    function_nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    helper_cache: dict[str, dict[str, Any]],
    stack: set[str],
) -> dict[str, Any]:
    info = _new_guard_info()
    if not isinstance(node, ast.Call):
        return info

    name = _call_name(node.func)
    if name == "Depends":
        return _analyze_dependency_target(_extract_depends_target(node), function_nodes, helper_cache, stack)
    if name == "require_admin_user":
        info["coarse"] = True
        return info
    if name == "_require_admin_current_user":
        info["manual_admin"] = True
        return info
    if name == "require_admin_capability":
        capabilities = _extract_capabilities_from_call(node)
        if capabilities:
            info["capabilities"].update(capabilities)
        else:
            info["unknown"].add("require_admin_capability")
        return info
    if name == "require_any_admin_capability":
        capabilities = _extract_capabilities_from_call(node)
        if capabilities:
            info["capabilities"].update(capabilities)
        else:
            info["unknown"].add("require_any_admin_capability")
        return info
    if name == "require_admin_capability_with_unlock":
        info["unlock"] = True
        info["reauth"] = True
        for arg in node.args:
            _merge_guard_info(info, _analyze_expr(arg, function_nodes, helper_cache, stack))
        return info
    if name in {
        "require_recent_admin_reauth",
        "_require_recent_admin_reauth_response",
        "require_admin_unlock_or_recent_reauth",
    }:
        info["reauth"] = True
        if name == "require_admin_unlock_or_recent_reauth":
            info["unlock"] = True
        return info
    if _mfa_related_name(name):
        info["mfa"] = True

    for arg in node.args:
        if isinstance(arg, ast.Call):
            _merge_guard_info(info, _analyze_expr(arg, function_nodes, helper_cache, stack))
    for keyword in node.keywords:
        if isinstance(keyword.value, ast.Call):
            _merge_guard_info(info, _analyze_expr(keyword.value, function_nodes, helper_cache, stack))
    return info


def _depends_calls_from_annotation(node: ast.AST | None) -> list[ast.Call]:
    if node is None:
        return []
    calls: list[ast.Call] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and _call_name(child.func) == "Depends":
            calls.append(child)
    return calls


def _depends_calls_from_dependencies_kw(node: ast.AST | None) -> list[ast.Call]:
    if isinstance(node, ast.Call) and _call_name(node.func) == "Depends":
        return [node]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        calls: list[ast.Call] = []
        for item in node.elts:
            calls.extend(_depends_calls_from_dependencies_kw(item))
        return calls
    return []


def _analyze_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    function_nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    helper_cache: dict[str, dict[str, Any]],
    stack: set[str],
) -> dict[str, Any]:
    if node.name in helper_cache:
        return helper_cache[node.name]
    if node.name in stack:
        return _new_guard_info()

    stack = set(stack)
    stack.add(node.name)
    info = _new_guard_info()
    args = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
    defaults = [None] * (len(node.args.posonlyargs) + len(node.args.args) - len(node.args.defaults)) + list(node.args.defaults)
    defaults.extend(node.args.kw_defaults)

    for arg, default in zip(args, defaults):
        if isinstance(default, ast.Call) and _call_name(default.func) == "Depends":
            _merge_guard_info(info, _analyze_expr(default, function_nodes, helper_cache, stack))
        for depends_call in _depends_calls_from_annotation(arg.annotation):
            _merge_guard_info(info, _analyze_expr(depends_call, function_nodes, helper_cache, stack))

    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            _merge_guard_info(info, _analyze_expr(child, function_nodes, helper_cache, stack))

    helper_cache[node.name] = info
    return info


def _guard_style(info: dict[str, Any]) -> str:
    has_capability = bool(info["capabilities"])
    if has_capability and info["unlock"]:
        return "capability_with_unlock_or_recent_reauth"
    if has_capability and info["reauth"]:
        return "capability_with_recent_reauth"
    if has_capability:
        return "capability"
    if info["coarse"]:
        return "coarse_admin"
    if info["manual_admin"] and info["reauth"]:
        return "manual_admin_with_recent_reauth"
    if info["manual_admin"]:
        return "manual_admin"
    return "unclassified"


def _classification(guard_style: str) -> str:
    if guard_style == "coarse_admin":
        return "coarse_admin_guarded"
    if guard_style.startswith("capability"):
        return "capability_guarded"
    if guard_style.startswith("manual_admin"):
        return "manual_admin_guarded"
    return "unclassified"


def _fallback_dependence(info: dict[str, Any], guard_style: str) -> str:
    if guard_style == "coarse_admin":
        return "direct_coarse_admin_guard"
    if info["capabilities"]:
        return "capability_expansion_uses_coarse_fallback_when_enabled"
    if guard_style.startswith("manual_admin"):
        return "manual_admin_current_user_guard"
    return "unknown"


def _route_entry(
    *,
    repo_root: Path,
    source_path: Path,
    include: dict[str, str],
    route_func: ast.FunctionDef | ast.AsyncFunctionDef,
    route_meta: dict[str, Any],
    function_nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    helper_cache: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    info = _new_guard_info()
    for depends_call in _depends_calls_from_dependencies_kw(route_meta.get("dependencies")):
        _merge_guard_info(info, _analyze_expr(depends_call, function_nodes, helper_cache, set()))
    _merge_guard_info(info, _analyze_function(route_func, function_nodes, helper_cache, set()))

    full_path = _join_paths(include["prefix"], route_meta["path"])
    guard_style = _guard_style(info)
    route_is_admin_candidate = (
        guard_style != "unclassified"
        or _admin_path(full_path)
        or route_func.name.startswith("admin_")
        or route_func.name.endswith("_admin")
    )
    if not route_is_admin_candidate:
        return None

    unknown = sorted(str(item) for item in info["unknown"] if str(item))
    if guard_style != "unclassified":
        unknown = []
    elif not unknown and _admin_path(full_path):
        unknown = ["admin_prefix_without_recognized_guard"]

    classification = _classification(guard_style)
    return {
        "file": _relative_path(source_path, repo_root),
        "function": route_func.name,
        "line": int(route_meta.get("line") or route_func.lineno),
        "routeFamily": include["routeFamily"],
        "methods": route_meta["methods"],
        "path": full_path,
        "guardStyle": guard_style,
        "classification": classification,
        "capabilityDependencies": sorted(info["capabilities"]),
        "reauthGuard": bool(info["reauth"]),
        "mfaGuard": bool(info["mfa"] or "mfa" in full_path.lower() or "mfa" in route_func.name.lower()),
        "fallbackDependence": _fallback_dependence(info, guard_style),
        "unknownReasons": unknown,
        "includeInSchema": route_meta.get("includeInSchema"),
        "deprecated": route_meta.get("deprecated"),
    }


def _summary(routes: list[dict[str, Any]]) -> dict[str, Any]:
    by_guard = Counter(route["guardStyle"] for route in routes)
    by_classification = Counter(route["classification"] for route in routes)
    return {
        "routeCount": len(routes),
        "byGuardStyle": dict(sorted(by_guard.items())),
        "byClassification": dict(sorted(by_classification.items())),
        "coarseAdminRouteCount": by_guard.get("coarse_admin", 0),
        "capabilityRouteCount": sum(count for guard, count in by_guard.items() if guard.startswith("capability")),
        "manualAdminRouteCount": sum(count for guard, count in by_guard.items() if guard.startswith("manual_admin")),
        "recentReauthRouteCount": sum(1 for route in routes if route["reauthGuard"]),
        "mfaRouteCount": sum(1 for route in routes if route["mfaGuard"]),
        "unclassifiedRouteCount": by_guard.get("unclassified", 0),
        "coarseFallbackDependentRouteCount": sum(
            1 for route in routes if route["fallbackDependence"] != "unknown"
        ),
    }


def _read_optional_source(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _frontend_route_id(path: str) -> str:
    normalized = path.strip("/").replace("/", ".").replace(":", "")
    return normalized.replace("-", "_") or "root"


def _collect_admin_surface_paths(app_source: str) -> list[str]:
    paths = {
        match.group(1)
        for match in re.finditer(r'<Route\s+path="([^"]+)"\s+element=\{<AdminSurfaceRoute>', app_source)
    }
    return sorted(path for path in paths if path.startswith("/"))


def _collect_flag_capability_map(capability_source: str) -> dict[str, str]:
    map_match = re.search(
        r"const\s+capabilityByFlag:[^{]+=\s*\{(?P<body>.*?)\};",
        capability_source,
        flags=re.DOTALL,
    )
    if not map_match:
        return {}
    return {
        match.group("flag"): match.group("capability")
        for match in re.finditer(
            r"(?P<flag>can[A-Za-z0-9_]+):\s*'(?P<capability>[^']+)'",
            map_match.group("body"),
        )
    }


def _collect_frontend_gate_rules(capability_source: str) -> tuple[dict[str, dict[str, Any]], set[str]]:
    rules: dict[str, dict[str, Any]] = {}
    feature_flagged_paths: set[str] = set()

    for match in re.finditer(
        r"if\s*\(\s*pathname\s*===\s*'(?P<path>[^']+)'\s*\|\|\s*pathname\.startsWith\('(?P=path)/'\)\s*\)"
        r"\s*\{\s*return\s+capabilityFlags\.(?P<flag>can[A-Za-z0-9_]+);",
        capability_source,
        flags=re.DOTALL,
    ):
        rules[match.group("path")] = {
            "capabilityFlag": match.group("flag"),
            "gateSource": "canAccessAdminPath",
            "featureFlagDependency": None,
        }

    for function_name, feature_dependency in (
        ("isAdminLaunchCockpitPath", None),
        ("isAdminMissionControlPath", "VITE_WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED"),
    ):
        path_match = re.search(
            rf"function\s+{function_name}\([^)]*\):\s*boolean\s*\{{\s*return\s+pathname\s*===\s*'(?P<path>[^']+)'",
            capability_source,
            flags=re.DOTALL,
        )
        gate_match = re.search(
            rf"if\s*\(\s*{function_name}\(pathname\)\s*\)\s*\{{\s*return\s+(?:isAdminMissionControlPrototypeEnabled\(\)\s*&&\s*)?capabilityFlags\.(?P<flag>can[A-Za-z0-9_]+);",
            capability_source,
            flags=re.DOTALL,
        )
        if path_match and gate_match:
            path = path_match.group("path")
            rules[path] = {
                "capabilityFlag": gate_match.group("flag"),
                "gateSource": f"canAccessAdminPath:{function_name}",
                "featureFlagDependency": feature_dependency,
            }
            if feature_dependency:
                feature_flagged_paths.add(path)

    if "pathname === '/admin/users'" in capability_source and "pathname.endsWith('/activity')" in capability_source:
        rules["/admin/users"] = {
            "capabilityFlag": "canReadUsers",
            "gateSource": "canAccessAdminPath:user_routes",
            "featureFlagDependency": None,
        }
        rules["/admin/users/:userId"] = {
            "capabilityFlag": "canReadUsers",
            "gateSource": "canAccessAdminPath:user_routes",
            "featureFlagDependency": None,
        }
        rules["/admin/users/:userId/activity"] = {
            "capabilityFlag": "canReadUserActivity",
            "gateSource": "canAccessAdminPath:user_routes",
            "featureFlagDependency": None,
        }

    return rules, feature_flagged_paths


def _collect_frontend_admin_routes(repo_root: Path) -> list[dict[str, Any]]:
    app_source = _read_optional_source(repo_root / FRONTEND_APP_PATH)
    capability_source = _read_optional_source(repo_root / FRONTEND_ADMIN_CAPABILITIES_PATH)
    if not app_source or not capability_source:
        return []

    flag_capabilities = _collect_flag_capability_map(capability_source)
    gate_rules, feature_flagged_paths = _collect_frontend_gate_rules(capability_source)
    routes: list[dict[str, Any]] = []

    for path in _collect_admin_surface_paths(app_source):
        rule = gate_rules.get(path)
        capability_flag = str(rule.get("capabilityFlag")) if rule else None
        capability_label = flag_capabilities.get(capability_flag or "")
        feature_flag_dependency = rule.get("featureFlagDependency") if rule else None
        classification = "frontend_admin_capability_gate" if capability_flag and capability_label else "frontend_unknown_admin_gate"
        gate_style = "admin_surface_capability"
        if path in feature_flagged_paths:
            gate_style = "admin_surface_capability_with_feature_flag"
        elif classification == "frontend_unknown_admin_gate":
            gate_style = "unknown"

        routes.append(
            {
                "file": FRONTEND_APP_PATH.as_posix(),
                "helperFile": FRONTEND_ADMIN_CAPABILITIES_PATH.as_posix(),
                "routeId": _frontend_route_id(path),
                "path": path,
                "localizedPath": path.lstrip("/"),
                "gateStyle": gate_style,
                "classification": classification,
                "capabilityFlag": capability_flag,
                "capabilityLabel": capability_label,
                "fallbackDependence": "frontend_requires_current_user_isAdmin_and_capability_payload"
                if capability_flag
                else "unknown",
                "missingPayloadBehavior": "fail_closed_when_capability_payload_missing"
                if capability_flag
                else "unknown",
                "gateSource": rule.get("gateSource") if rule else None,
                "featureFlagDependency": feature_flag_dependency,
                "unknownReasons": [] if classification != "frontend_unknown_admin_gate" else ["admin_route_without_known_capability_gate"],
            }
        )

    routes.sort(key=lambda item: item["path"])
    return routes


def _frontend_summary(frontend_routes: list[dict[str, Any]]) -> dict[str, Any]:
    by_classification = Counter(route["classification"] for route in frontend_routes)
    by_capability = Counter(route["capabilityLabel"] or "unknown" for route in frontend_routes)
    return {
        "frontendAdminRouteCount": len(frontend_routes),
        "frontendFailClosedRouteCount": sum(
            1
            for route in frontend_routes
            if route["missingPayloadBehavior"] == "fail_closed_when_capability_payload_missing"
        ),
        "frontendUnknownGateCount": by_classification.get("frontend_unknown_admin_gate", 0),
        "byFrontendClassification": dict(sorted(by_classification.items())),
        "byFrontendCapability": dict(sorted(by_capability.items())),
    }


def _fallback_surfaces(routes: list[dict[str, Any]], frontend_routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    backend_by_fallback = Counter(route["fallbackDependence"] for route in routes)
    surfaces = [
        {
            "surface": "backend_capability_route_expansion",
            "classification": "coarse_fallback_remaining",
            "fallbackDependencyLabel": "capability_expansion_uses_coarse_fallback_when_enabled",
            "routeCount": backend_by_fallback.get("capability_expansion_uses_coarse_fallback_when_enabled", 0),
            "sourceLabels": [
                "api.deps.require_admin_capability",
                "src.admin_rbac.expand_admin_capabilities",
                "WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED",
            ],
        },
        {
            "surface": "backend_direct_coarse_admin_routes",
            "classification": "direct_coarse_admin_guard",
            "fallbackDependencyLabel": "direct_coarse_admin_guard",
            "routeCount": backend_by_fallback.get("direct_coarse_admin_guard", 0),
            "sourceLabels": ["api.deps.require_admin_user"],
        },
        {
            "surface": "backend_manual_admin_request_guards",
            "classification": "manual_admin_guard",
            "fallbackDependencyLabel": "manual_admin_current_user_guard",
            "routeCount": backend_by_fallback.get("manual_admin_current_user_guard", 0),
            "sourceLabels": ["api.v1.endpoints.auth._require_admin_current_user"],
        },
        {
            "surface": "frontend_admin_surface_routes",
            "classification": "fail_closed_frontend_gate",
            "fallbackDependencyLabel": "frontend_requires_current_user_isAdmin_and_capability_payload",
            "routeCount": sum(
                1
                for route in frontend_routes
                if route["fallbackDependence"] == "frontend_requires_current_user_isAdmin_and_capability_payload"
            ),
            "sourceLabels": [
                "apps/dsa-web/src/App.tsx.AdminSurfaceRoute",
                "apps/dsa-web/src/utils/adminCapabilities.resolveAdminCapabilityFlags",
                "apps/dsa-web/src/utils/adminCapabilities.canAccessAdminPath",
            ],
        },
    ]
    return sorted(surfaces, key=lambda item: item["surface"])


def build_inventory(repo_root: Path | str = REPO_ROOT) -> dict[str, Any]:
    """Build a sanitized static inventory from source files only."""
    root = Path(repo_root)
    routes: list[dict[str, Any]] = []
    for include in _collect_router_includes(root):
        source_path = root / include["file"]
        if not source_path.exists():
            continue
        tree = _parse_source(source_path)
        function_nodes = _collect_function_nodes(tree)
        helper_cache: dict[str, dict[str, Any]] = {}
        for route_func, route_meta in _iter_route_functions(tree):
            entry = _route_entry(
                repo_root=root,
                source_path=source_path,
                include=include,
                route_func=route_func,
                route_meta=route_meta,
                function_nodes=function_nodes,
                helper_cache=helper_cache,
            )
            if entry is not None:
                routes.append(entry)

    routes.sort(key=lambda item: (item["file"], item["line"], item["path"], tuple(item["methods"])))
    frontend_routes = _collect_frontend_admin_routes(root)
    summary = _summary(routes)
    summary.update(_frontend_summary(frontend_routes))
    return {
        "tool": "admin_rbac_route_inventory",
        "schemaVersion": 2,
        "readOnly": True,
        "runtimeBehaviorChanged": False,
        "authBehaviorChanged": False,
        "runtimeImportsRequired": False,
        "inspectionMethod": "python_ast_and_frontend_source_scan",
        "summary": summary,
        "routes": routes,
        "frontendAdminRoutes": frontend_routes,
        "fallbackSurfaces": _fallback_surfaces(routes, frontend_routes),
        "unknowns": [route for route in routes if route["classification"] == "unclassified"],
        "frontendUnknowns": [
            route for route in frontend_routes if route["classification"] == "frontend_unknown_admin_gate"
        ],
        "limitations": [
            "Static source inspection only; dynamic runtime router mutation is not evaluated.",
            "Local dependency wrappers are resolved only when their source is in the inspected endpoint file.",
            "Capability fallback dependence is reported from known helper semantics; this helper does not evaluate configuration values.",
            "Frontend admin gate inventory is a bounded source scan of App.tsx and adminCapabilities.ts; it does not execute React routing.",
        ],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit a static admin RBAC route inventory as JSON.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root to inspect.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    payload = build_inventory(repo_root=args.repo_root)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
