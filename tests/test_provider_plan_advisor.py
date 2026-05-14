# -*- coding: utf-8 -*-
"""Offline contracts for cache-first advisory provider plans."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess
import sys

from src.services.provider_capability_matrix import ProviderDomain
from src.services.provider_plan_advisor import (
    describe_provider_plan,
    plan_cache_first_candidates,
    plan_provider_candidates,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_MACRO_TRANSPORT_TEXT = (REPO_ROOT / "src/services/official_macro_transport.py").read_text(encoding="utf-8")


def _ids(candidates):
    return [candidate.provider_id for candidate in candidates]


def test_cache_first_candidates_precede_scarce_live_providers() -> None:
    candidates = plan_cache_first_candidates(ProviderDomain.NEWS, market="US", mode="standard")
    provider_ids = _ids(candidates)

    assert provider_ids[:2] == ["local_cache", "local_news_cache"]
    assert provider_ids.index("local_news_cache") < provider_ids.index("gnews")
    assert provider_ids.index("local_news_cache") < provider_ids.index("tavily")
    assert all(candidate.advisory_only for candidate in candidates)


def test_backtest_plan_contains_only_local_cache_or_inference_candidates() -> None:
    for domain in (ProviderDomain.OHLCV, ProviderDomain.NEWS, ProviderDomain.SENTIMENT, ProviderDomain.TECHNICALS):
        candidates = plan_provider_candidates(domain, market="US", mode="backtest")

        assert candidates
        assert all(candidate.quota_class == "local" for candidate in candidates)
        assert all(candidate.live_provider is False for candidate in candidates)


def test_scanner_plan_excludes_scanner_wide_expensive_research_providers() -> None:
    blocked = {"fmp", "alpha_vantage", "gnews", "tavily", "social_sentiment"}

    for domain in (ProviderDomain.QUOTE, ProviderDomain.OHLCV, ProviderDomain.NEWS, ProviderDomain.SENTIMENT):
        candidates = plan_provider_candidates(domain, market="US", mode="scanner")

        assert blocked.isdisjoint(_ids(candidates))
        assert all(candidate.scanner_usage == "local_only" for candidate in candidates)


def test_technical_indicators_prefer_local_ohlcv_and_local_computation() -> None:
    provider_ids = _ids(plan_provider_candidates(ProviderDomain.TECHNICALS, market="US", mode="standard"))
    deep_ids = _ids(plan_provider_candidates(ProviderDomain.TECHNICALS, market="US", mode="deep"))

    assert provider_ids[:2] == ["local_ohlcv", "local_cache"]
    assert provider_ids.index("local_ohlcv") < provider_ids.index("fmp")
    assert deep_ids.index("local_ohlcv") < deep_ids.index("alpha_vantage")


def test_alpha_vantage_is_deep_manual_last_resort_only() -> None:
    standard_ids = _ids(plan_provider_candidates(ProviderDomain.FUNDAMENTALS, market="US", mode="standard"))
    deep_ids = _ids(plan_provider_candidates(ProviderDomain.FUNDAMENTALS, market="US", mode="deep"))

    assert "alpha_vantage" not in standard_ids
    assert deep_ids[-1] == "alpha_vantage"


def test_fmp_is_fundamentals_and_statements_first_not_ohlcv_or_technicals_first() -> None:
    fundamentals_ids = _ids(plan_provider_candidates(ProviderDomain.FUNDAMENTALS, market="US", mode="standard"))
    statements_ids = _ids(plan_provider_candidates(ProviderDomain.STATEMENTS, market="US", mode="standard"))
    ohlcv_ids = _ids(plan_provider_candidates(ProviderDomain.OHLCV, market="US", mode="standard"))
    technical_ids = _ids(plan_provider_candidates(ProviderDomain.TECHNICALS, market="US", mode="standard"))

    assert fundamentals_ids[:2] == ["local_cache", "fmp"]
    assert statements_ids[:2] == ["local_cache", "fmp"]
    assert ohlcv_ids.index("fmp") > 2
    assert technical_ids.index("fmp") > 1


def test_advisory_helpers_are_deterministic_and_side_effect_free() -> None:
    first = plan_provider_candidates("news", market="US", mode="standard")
    second = plan_provider_candidates(ProviderDomain.NEWS, market="us", mode="standard")
    description = describe_provider_plan("news", market="US", mode="standard")

    assert first == second
    assert description == describe_provider_plan(ProviderDomain.NEWS, market="us", mode="standard")
    assert description["domain"] == "news"
    assert description["market"] == "US"
    assert description["mode"] == "standard"
    assert description["advisoryOnly"] is True
    assert description["runtimeBehaviorChanged"] is False
    assert description["candidates"] == [candidate.as_dict() for candidate in first]


def test_provider_plan_advisor_import_does_not_import_live_provider_clients() -> None:
    script = """
import json
import src.services.provider_plan_advisor
blocked = [
    "data_provider.alpaca_fetcher",
    "data_provider.twelve_data_fetcher",
    "data_provider.alphavantage_provider",
    "data_provider.us_fundamentals_provider",
    "data_provider.yfinance_fetcher",
    "src.services.market_cache",
    "src.core.pipeline",
]
print(json.dumps({name: name in __import__("sys").modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}


def test_provider_plan_advisor_import_has_no_runtime_planner_side_effect() -> None:
    planner = importlib.import_module("src.services.analysis_provider_planner")
    before = planner.build_analysis_provider_plan("AAPL", market="us").categories

    importlib.import_module("src.services.provider_plan_advisor")
    after = planner.build_analysis_provider_plan("AAPL", market="us").categories

    assert before == after


def test_provider_plan_advisor_does_not_advertise_runtime_only_or_public_transport_sources() -> None:
    blocked = {"tickflow", "tushare", "akshare", "efinance", "binance", "fred", "treasury", "ny_fed"}

    assert 'source_id=f"fred:{normalized_series}"' in OFFICIAL_MACRO_TRANSPORT_TEXT
    assert 'source_id="treasury:daily_treasury_yield_curve"' in OFFICIAL_MACRO_TRANSPORT_TEXT

    for domain in (
        ProviderDomain.QUOTE,
        ProviderDomain.OHLCV,
        ProviderDomain.FUNDAMENTALS,
        ProviderDomain.MACRO,
        ProviderDomain.CRYPTO,
        ProviderDomain.FOREX,
    ):
        for mode in ("quick", "standard", "deep", "scanner", "backtest"):
            candidate_ids = set(_ids(plan_provider_candidates(domain, market="US", mode=mode)))
            assert blocked.isdisjoint(candidate_ids)


def test_provider_plan_description_stays_presence_free_and_advisory_only() -> None:
    description = describe_provider_plan(ProviderDomain.MACRO, market="US", mode="standard")
    serialized = json.dumps(description, ensure_ascii=False, sort_keys=True).lower()

    assert description["advisoryOnly"] is True
    assert description["runtimeBehaviorChanged"] is False
    assert description["networkCallsEnabled"] is False
    for forbidden in ("api_key", "token", "secret", "credential", "masked"):
        assert forbidden not in serialized
