# -*- coding: utf-8 -*-
"""Focused contracts for public baseline route matching."""

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middlewares.auth import _path_exempt, add_auth_middleware
from api.middlewares.public_abuse_limiter import _EXEMPT_PREFIXES
from api.route_access_policy import is_public_baseline_read, normalize_policy_path
from api.v1 import api_v1_router
from src import auth


PUBLIC_MARKET_SECONDARY_READS = (
    "/api/v1/market/cn-indices",
    "/api/v1/market/cn-breadth",
    "/api/v1/market/cn-flows",
    "/api/v1/market/cn-short-sentiment",
    "/api/v1/market/crypto",
    "/api/v1/market/crypto/stream",
    "/api/v1/market/daily-intelligence",
    "/api/v1/market/decision-cockpit",
    "/api/v1/market/futures",
    "/api/v1/market/fx-commodities",
    "/api/v1/market/liquidity-monitor",
    "/api/v1/market/market-briefing",
    "/api/v1/market/professional-data-capabilities",
    "/api/v1/market/rates",
    "/api/v1/market/regime-read-model",
    "/api/v1/market/regime-decision",
    "/api/v1/market/regime-evidence-pack",
    "/api/v1/market/rotation-radar",
    "/api/v1/market/sector-rotation",
    "/api/v1/market/sentiment",
    "/api/v1/market/temperature",
    "/api/v1/market/us-breadth",
)


def test_normalize_policy_path_trims_trailing_slash() -> None:
    assert normalize_policy_path("/api/v1/stocks/ORCL/quote/") == "/api/v1/stocks/ORCL/quote"
    assert normalize_policy_path("/") == "/"
    assert normalize_policy_path("") == "/"


def test_quote_routes_are_public_baseline_reads() -> None:
    assert is_public_baseline_read("GET", "/api/v1/stocks/ORCL/quote")
    assert is_public_baseline_read("get", "/api/v1/stocks/600519/quote/")
    assert is_public_baseline_read("POST", "/api/v1/analysis/preview")


def test_market_overview_routes_are_public_baseline_reads() -> None:
    assert is_public_baseline_read("GET", "/api/v1/market-overview")
    assert is_public_baseline_read("GET", "/api/v1/market-overview/")
    assert is_public_baseline_read("GET", "/api/v1/market-overview/indices")
    assert is_public_baseline_read("GET", "/api/v1/market-overview/macro")
    assert is_public_baseline_read("GET", "/api/v1/dashboard/market-intelligence-overview")
    assert is_public_baseline_read("GET", "/api/v1/homepage/intelligence")


def test_guest_market_secondary_reads_are_public_baseline_reads() -> None:
    for path in PUBLIC_MARKET_SECONDARY_READS:
        assert is_public_baseline_read("GET", path)
        assert is_public_baseline_read("get", f"{path}/")
        assert not is_public_baseline_read("POST", path)


def test_auth_middleware_keeps_only_guest_market_secondary_reads_public() -> None:
    app = FastAPI()
    add_auth_middleware(app)

    @app.get("/api/v1/{path:path}")
    def get_api_path(path: str) -> dict[str, str]:
        return {"path": path}

    with TestClient(app) as client, patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
        auth._auth_enabled = None
        for path in PUBLIC_MARKET_SECONDARY_READS:
            assert client.get(path).status_code == 200
        assert client.get("/api/v1/market/data-readiness").status_code == 401
        assert client.get("/api/v1/portfolio/accounts").status_code == 401
        assert client.get("/api/v1/scanner/themes").status_code == 401
        assert client.get("/api/v1/admin/users").status_code == 401

    with TestClient(app) as client, patch.object(auth, "_is_auth_enabled_from_env", return_value=False):
        auth._auth_enabled = None
        assert client.get("/api/v1/market/rotation-radar").status_code == 200
        assert client.get("/api/v1/portfolio/accounts").status_code == 200

    auth._auth_enabled = None

    direct_app = FastAPI()
    direct_app.include_router(api_v1_router)
    with TestClient(direct_app) as client, patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
        auth._auth_enabled = None
        assert client.get("/api/v1/options/lab").status_code == 401
        assert client.get("/api/v1/stocks/ORCL/evidence").status_code == 401
        assert client.get("/api/v1/leveraged-etf-mapper/mappings").status_code == 401
        assert client.post("/api/v1/market/scenario-lab", json={}).status_code == 401

    auth._auth_enabled = None


def test_adjacent_stock_research_routes_are_not_public_baseline_reads() -> None:
    assert not is_public_baseline_read("GET", "/api/v1/stocks/ORCL/evidence")
    assert not is_public_baseline_read("GET", "/api/v1/stocks/ORCL/structure-decision")
    assert not is_public_baseline_read("POST", "/api/v1/stocks/ORCL/quote")
    assert not is_public_baseline_read("GET", "/stocks/ORCL/quote")


def test_options_research_routes_are_not_public_baseline_reads() -> None:
    assert not is_public_baseline_read("GET", "/api/v1/options/lab")
    assert not is_public_baseline_read("GET", "/api/v1/options/underlyings/TEM/summary")
    assert not is_public_baseline_read("GET", "/api/v1/options/underlyings/TEM/chain")
    assert not is_public_baseline_read("POST", "/api/v1/options/decision/evaluate")


def test_unregistered_root_health_alias_is_not_claimed_by_exemption_policy() -> None:
    assert not _path_exempt("/health", "GET")
    assert "/health" not in _EXEMPT_PREFIXES
