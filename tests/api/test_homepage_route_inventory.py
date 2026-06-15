# -*- coding: utf-8 -*-
"""Route inventory guard for homepage-facing API routes."""

from __future__ import annotations

import os
import re
import sys
import types
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute


HOMEPAGE_INTELLIGENCE_ROUTE = ("GET", "/api/v1/homepage/intelligence")
DASHBOARD_MARKET_INTELLIGENCE_ROUTE = (
    "GET",
    "/api/v1/dashboard/market-intelligence-overview",
)
FORBIDDEN_HOMEPAGE_PATH_FRAGMENT_RE = re.compile(
    r"(^|[-_/])(admin|debug|provider|raw)([-_/]|$)"
)
FORBIDDEN_HOMEPAGE_ROUTE_NAME_FRAGMENTS = (
    "broker",
    "order",
    "trade",
    "execution",
)
REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTER_PATH = REPO_ROOT / "api/v1/router.py"


@dataclass(frozen=True)
class RouteSignature:
    method: str
    path: str
    name: str


def _route_inventory() -> list[RouteSignature]:
    os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")
    sys.modules.setdefault("greenlet", None)
    if "orjson" not in sys.modules:
        import json

        sys.modules["orjson"] = types.SimpleNamespace(
            OPT_NON_STR_KEYS=0,
            OPT_SERIALIZE_NUMPY=0,
            dumps=lambda value, option=0: json.dumps(value).encode("utf-8"),
            loads=json.loads,
        )

    from api.v1.endpoints import dashboard_overview, homepage_intelligence

    app = FastAPI()
    app.include_router(homepage_intelligence.router, prefix="/api/v1/homepage")
    app.include_router(dashboard_overview.router, prefix="/api/v1/dashboard")

    routes: list[RouteSignature] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            routes.append(
                RouteSignature(method=method, path=route.path, name=route.name)
            )
    return routes


def _routes_for(path: str, routes: list[RouteSignature]) -> list[RouteSignature]:
    return [route for route in routes if route.path == path]


def _method_path_matches(
    method: str, path: str, routes: list[RouteSignature]
) -> list[RouteSignature]:
    return [route for route in routes if route.method == method and route.path == path]


def _router_source() -> str:
    return ROUTER_PATH.read_text(encoding="utf-8")


def test_v1_router_keeps_homepage_and_dashboard_route_registrations() -> None:
    router_source = _router_source()

    assert router_source.count("homepage_intelligence.router") == 1
    assert router_source.count('prefix="/homepage"') == 1
    assert router_source.count("dashboard_overview.router") == 1
    assert router_source.count('prefix="/dashboard"') == 1


def test_homepage_intelligence_route_is_registered_exactly_once() -> None:
    routes = _route_inventory()
    matches = _method_path_matches(*HOMEPAGE_INTELLIGENCE_ROUTE, routes)

    assert matches == [
        RouteSignature(
            method="GET",
            path="/api/v1/homepage/intelligence",
            name="get_homepage_intelligence",
        )
    ]


def test_homepage_routes_do_not_expose_admin_debug_provider_or_raw_paths() -> None:
    homepage_routes = [
        route for route in _route_inventory() if route.path.startswith("/api/v1/homepage/")
    ]

    assert homepage_routes
    for route in homepage_routes:
        assert not FORBIDDEN_HOMEPAGE_PATH_FRAGMENT_RE.search(
            route.path.lower()
        ), route


def test_homepage_route_names_do_not_use_execution_semantics() -> None:
    homepage_routes = [
        route for route in _route_inventory() if route.path.startswith("/api/v1/homepage/")
    ]

    assert homepage_routes
    for route in homepage_routes:
        normalized_name = route.name.lower()
        for fragment in FORBIDDEN_HOMEPAGE_ROUTE_NAME_FRAGMENTS:
            assert fragment not in normalized_name, route


def test_dashboard_market_intelligence_route_remains_present_and_separate() -> None:
    routes = _route_inventory()

    homepage_matches = _method_path_matches(*HOMEPAGE_INTELLIGENCE_ROUTE, routes)
    dashboard_matches = _method_path_matches(*DASHBOARD_MARKET_INTELLIGENCE_ROUTE, routes)

    assert len(homepage_matches) == 1
    assert dashboard_matches == [
        RouteSignature(
            method="GET",
            path="/api/v1/dashboard/market-intelligence-overview",
            name="get_market_intelligence_overview",
        )
    ]
    assert _routes_for(HOMEPAGE_INTELLIGENCE_ROUTE[1], routes) != _routes_for(
        DASHBOARD_MARKET_INTELLIGENCE_ROUTE[1], routes
    )
