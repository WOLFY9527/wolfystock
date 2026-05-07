# -*- coding: utf-8 -*-
"""Broker and order execution absence evidence for launch-exposed APIs."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute

from api.v1 import api_v1_router


MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PUBLIC_ADMIN_LAUNCH_PREFIXES = (
    "/api/v1/analysis",
    "/api/v1/scanner",
    "/api/v1/options",
    "/api/v1/backtest",
    "/api/v1/admin",
)
FORBIDDEN_EXACT_EXECUTION_ROUTES = (
    "/api/v1/orders",
    "/api/v1/broker/orders",
    "/api/v1/trade",
    "/api/v1/execute",
    "/api/v1/submit-order",
)
FORBIDDEN_ROUTE_NAME_FRAGMENTS = (
    "place_order",
    "submit_order",
    "execute_order",
    "broker_order",
    "order_execution",
)
FORBIDDEN_MUTATION_SEGMENT_RE = re.compile(
    r"(^|/)(orders?|trade|execute|place[-_]order|submit[-_]order)(/|$)"
)
FORBIDDEN_IMPORT_MODULE_FRAGMENTS = (
    "broker_execution",
    "order_execution",
    "order_placement",
    "broker_order",
)
FORBIDDEN_CALL_NAMES = (
    "place_order",
    "submit_order",
    "execute_order",
    "create_order",
)


@dataclass(frozen=True)
class RouteSignature:
    method: str
    path: str
    name: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _route_inventory() -> list[RouteSignature]:
    app = FastAPI()
    app.include_router(api_v1_router)
    routes: list[RouteSignature] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            routes.append(RouteSignature(method=method, path=route.path, name=route.name))
    return routes


def _is_public_admin_launch_route(path: str) -> bool:
    return path.startswith(PUBLIC_ADMIN_LAUNCH_PREFIXES)


def _import_targets(tree: ast.AST) -> list[str]:
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets.append(node.module)
    return targets


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def test_launch_exposed_api_routes_do_not_register_broker_order_execution_mutations() -> None:
    routes = _route_inventory()
    mutation_routes = [route for route in routes if route.method in MUTATION_METHODS]
    registered_mutation_paths = {route.path for route in mutation_routes}

    for forbidden_path in FORBIDDEN_EXACT_EXECUTION_ROUTES:
        assert forbidden_path not in registered_mutation_paths
        assert not any(path.startswith(f"{forbidden_path}/") for path in registered_mutation_paths)

    launch_mutations = [route for route in mutation_routes if _is_public_admin_launch_route(route.path)]
    for route in launch_mutations:
        normalized_path = route.path.lower()
        normalized_name = route.name.lower()
        assert not FORBIDDEN_MUTATION_SEGMENT_RE.search(normalized_path), route
        for fragment in FORBIDDEN_ROUTE_NAME_FRAGMENTS:
            assert fragment not in normalized_name, route


def test_launch_exposed_analysis_scanner_options_backtest_apis_do_not_import_order_mutation_paths() -> None:
    repo_root = _repo_root()
    launch_runtime_files = (
        repo_root / "api/v1/endpoints/analysis.py",
        repo_root / "api/v1/endpoints/scanner.py",
        repo_root / "api/v1/endpoints/options.py",
        repo_root / "api/v1/endpoints/backtest.py",
        repo_root / "src/services/analysis_service.py",
        repo_root / "src/services/market_scanner_service.py",
        repo_root / "src/services/market_scanner_ops_service.py",
        repo_root / "src/services/scanner_ai_service.py",
        repo_root / "src/services/options_lab_service.py",
        repo_root / "src/services/backtest_service.py",
        repo_root / "src/services/rule_backtest_service.py",
    )

    for path in launch_runtime_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = _import_targets(tree)
        for imported in imports:
            normalized = imported.lower()
            for fragment in FORBIDDEN_IMPORT_MODULE_FRAGMENTS:
                assert fragment not in normalized, f"{imported!r} imported by {path}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = _call_name(node)
                assert call_name not in FORBIDDEN_CALL_NAMES, f"{call_name!r} called by {path}"


def test_portfolio_backtest_runtime_files_do_not_import_order_execution_modules() -> None:
    repo_root = _repo_root()
    runtime_files = (
        repo_root / "api/v1/endpoints/backtest.py",
        repo_root / "api/v1/endpoints/portfolio.py",
        repo_root / "src/repositories/backtest_repo.py",
        repo_root / "src/repositories/portfolio_repo.py",
        repo_root / "src/repositories/rule_backtest_repo.py",
        repo_root / "src/services/backtest_service.py",
        repo_root / "src/services/portfolio_service.py",
        repo_root / "src/services/rule_backtest_service.py",
    )

    for path in runtime_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = _import_targets(tree)
        for imported in imports:
            normalized = imported.lower()
            for fragment in FORBIDDEN_IMPORT_MODULE_FRAGMENTS:
                assert fragment not in normalized, f"{imported!r} imported by {path}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = _call_name(node)
                assert call_name not in FORBIDDEN_CALL_NAMES, f"{call_name!r} called by {path}"


def test_admin_provider_broker_placeholder_remains_disabled_read_only_and_non_executable() -> None:
    source = (_repo_root() / "api/v1/endpoints/admin_provider_circuits.py").read_text(encoding="utf-8")

    assert "liveHttpCallsEnabled=False" in source
    assert "brokerOrderPathEnabled=False" in source
    assert "portfolioMutationPathEnabled=False" in source
    assert "tradeableData=False" in source
    assert "brokerOrderPathEnabled=True" not in source
    assert "portfolioMutationPathEnabled=True" not in source
    assert "tradeableData=True" not in source
