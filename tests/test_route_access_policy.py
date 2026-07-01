# -*- coding: utf-8 -*-
"""Focused contracts for public baseline route matching."""

from api.route_access_policy import is_public_baseline_read, normalize_policy_path


def test_normalize_policy_path_trims_trailing_slash() -> None:
    assert normalize_policy_path("/api/v1/stocks/ORCL/quote/") == "/api/v1/stocks/ORCL/quote"
    assert normalize_policy_path("/") == "/"
    assert normalize_policy_path("") == "/"


def test_quote_routes_are_public_baseline_reads() -> None:
    assert is_public_baseline_read("GET", "/api/v1/stocks/ORCL/quote")
    assert is_public_baseline_read("get", "/api/v1/stocks/600519/quote/")


def test_market_overview_routes_are_public_baseline_reads() -> None:
    assert is_public_baseline_read("GET", "/api/v1/market-overview")
    assert is_public_baseline_read("GET", "/api/v1/market-overview/")
    assert is_public_baseline_read("GET", "/api/v1/market-overview/indices")
    assert is_public_baseline_read("GET", "/api/v1/market-overview/macro")


def test_adjacent_stock_research_routes_are_not_public_baseline_reads() -> None:
    assert not is_public_baseline_read("GET", "/api/v1/stocks/ORCL/evidence")
    assert not is_public_baseline_read("GET", "/api/v1/stocks/ORCL/structure-decision")
    assert not is_public_baseline_read("POST", "/api/v1/stocks/ORCL/quote")
    assert not is_public_baseline_read("GET", "/stocks/ORCL/quote")
