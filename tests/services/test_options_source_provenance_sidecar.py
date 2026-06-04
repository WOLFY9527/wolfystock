# -*- coding: utf-8 -*-
"""Tests for helper-only Options provenance sidecar builder."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from src.services.options_source_provenance_sidecar import (
    build_options_source_provenance_sidecar,
    summarize_options_source_provenance_sidecar,
)
from src.services.source_provenance_contract import SOURCE_PROVENANCE_CONTRACT_VERSION


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/options_source_provenance_sidecar.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "bot",
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "src.services.market_cache",
    "src.services.options_market_data_provider",
    "src.settings",
)


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def test_readyish_scenario_builds_bounded_entries_for_options_domains() -> None:
    entries = build_options_source_provenance_sidecar(
        summary={
            "source": "polygon_options_live",
            "sourceLabel": "Polygon Options",
            "freshness": "fresh",
            "underlying": {
                "source": "polygon_options_live",
                "sourceLabel": "Polygon Options",
                "freshness": "fresh",
                "price": 182.4,
            },
        },
        chain={
            "source": "polygon_options_live",
            "sourceLabel": "Polygon Options",
            "chainAsOf": "2026-06-05T14:30:00Z",
            "contracts": [
                {
                    "contractSymbol": "AAPL260619C00180000",
                    "spreadPct": 9.5,
                    "impliedVolatility": 0.31,
                    "greeks": {"delta": 0.52, "theta": -0.06, "gamma": 0.02, "vega": 0.11},
                    "dataQuality": {"bidAskCoverage": "complete"},
                }
            ],
        },
        decision={
            "decisionLabel": "仅观察",
            "dataQuality": {
                "dataQualityTier": "live_usable",
                "sourceType": "live",
                "blockingReasons": [],
                "warnings": [],
            },
            "liquidity": {"spreadPct": 9.5, "liquidityWarnings": []},
            "ivGreeks": {
                "ivRankStatus": "available",
                "ivRankSource": "provider_reported_iv_rank",
                "warnings": [],
            },
            "expectedMove": {"expectedMoveSource": "straddle_mid", "expectedMoveWarnings": []},
            "freshness": {"source": "polygon_options_live", "freshness": "fresh"},
            "primaryReasons": ["数据质量、流动性与风险回报需同时复核"],
            "scenarioAssumptions": {"targetPrice": 190, "targetDate": "2026-06-19"},
        },
        scenario={"rows": [{"price": 190, "payoff": 210.0}]},
    )

    assert [entry["evidenceDomain"] for entry in entries] == [
        "market_data",
        "derivatives",
        "derivatives",
        "derivatives",
        "derivatives",
        "portfolio",
        "derivatives",
        "research",
        "research",
    ]
    assert {entry["sourceId"] for entry in entries} == {"polygon_options_live"}
    assert all(entry["contractVersion"] == SOURCE_PROVENANCE_CONTRACT_VERSION for entry in entries)
    assert all(entry["fallbackOrProxy"] is False for entry in entries)
    assert all(entry["sourceTier"] == "authorized_feed" for entry in entries)
    assert any(entry["debugRef"] == "source-provenance:options-scenario" for entry in entries)


def test_missing_chain_fails_closed_for_chain_and_related_domains() -> None:
    entries = build_options_source_provenance_sidecar(
        summary={"source": "polygon_options_live", "sourceLabel": "Polygon Options", "freshness": "fresh"},
        decision={
            "dataQuality": {
                "dataQualityTier": "insufficient",
                "sourceType": "unknown",
                "blockingReasons": ["missing_contract_legs"],
                "warnings": [],
            }
        },
    )

    by_ref = {entry["debugRef"]: entry for entry in entries}
    chain_entry = by_ref["source-provenance:options-options-chain"]

    assert chain_entry["observationOnly"] is True
    assert chain_entry["scoreContributionAllowed"] is False
    assert "missing_options_chain" in chain_entry["limitations"]
    assert "authorized_options_chain" in chain_entry["nextEvidenceNeeded"]


def test_missing_iv_and_greeks_fail_closed_to_observation_only() -> None:
    entries = build_options_source_provenance_sidecar(
        chain={
            "source": "polygon_options_live",
            "sourceLabel": "Polygon Options",
            "contracts": [{"contractSymbol": "AAPL260619C00180000"}],
        },
        decision={
            "dataQuality": {"dataQualityTier": "live_usable", "sourceType": "live", "blockingReasons": [], "warnings": []},
            "ivGreeks": {
                "ivRankStatus": "unavailable",
                "ivRankSource": "current_iv",
                "warnings": ["missing_iv", "missing_greeks"],
            },
        },
    )

    by_ref = {entry["debugRef"]: entry for entry in entries}
    iv_entry = by_ref["source-provenance:options-iv-greeks"]

    assert iv_entry["authorityTier"] == "observation_only"
    assert iv_entry["observationOnly"] is True
    assert iv_entry["scoreContributionAllowed"] is False
    assert "missing_iv_or_greeks" in iv_entry["limitations"]
    assert "authorized_iv_greeks" in iv_entry["nextEvidenceNeeded"]


def test_wide_spread_and_manual_review_fail_closed() -> None:
    entries = build_options_source_provenance_sidecar(
        chain={
            "source": "polygon_options_live",
            "sourceLabel": "Polygon Options",
            "contracts": [{"contractSymbol": "AAPL260619C00180000", "spreadPct": 31}],
        },
        decision={
            "decisionLabel": "仅观察",
            "dataQuality": {"dataQualityTier": "live_usable", "sourceType": "live", "blockingReasons": [], "warnings": []},
            "liquidity": {"spreadPct": 31, "liquidityWarnings": ["wide_bid_ask_spread"]},
            "gateIssues": [{"status": "manual_review", "code": "wide_bid_ask_spread"}],
        },
    )

    by_ref = {entry["debugRef"]: entry for entry in entries}
    spread_entry = by_ref["source-provenance:options-spread"]

    assert spread_entry["authorityTier"] == "observation_only"
    assert spread_entry["freshnessState"] == "partial"
    assert spread_entry["observationOnly"] is True
    assert "wide_spread_manual_review" in spread_entry["limitations"]


def test_delayed_fallback_observe_only_paths_stay_fail_closed() -> None:
    entries = build_options_source_provenance_sidecar(
        summary={
            "source": "yfinance_proxy_delayed",
            "sourceLabel": "Yahoo Finance",
            "freshness": "delayed",
            "warnings": ["data_may_be_delayed_or_stale"],
        },
        chain={
            "source": "yfinance_proxy_delayed",
            "sourceLabel": "Yahoo Finance",
            "contracts": [{"contractSymbol": "AAPL260619C00180000", "spreadPct": 12}],
        },
        decision={
            "decisionLabel": "仅观察",
            "dataQuality": {
                "dataQualityTier": "delayed_usable",
                "sourceType": "fallback",
                "blockingReasons": [],
                "warnings": [],
            },
            "ivGreeks": {"ivRankStatus": "available", "ivRankSource": "synthetic_fixture_proxy", "warnings": []},
        },
    )

    assert all(entry["observationOnly"] is True for entry in entries)
    assert all(entry["scoreContributionAllowed"] is False for entry in entries)
    assert any("fallback_or_proxy_source" in entry["limitations"] for entry in entries)
    assert any(entry["freshnessState"] == "delayed" for entry in entries)


def test_leakage_guardrails_and_json_stable_summary() -> None:
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    entries = build_options_source_provenance_sidecar(
        summary={
            "source": "provider_payload_session_cookie",
            "sourceLabel": "Internal raw payload token",
            "freshness": "live",
        },
        decision={
            "dataQuality": {
                "dataQualityTier": "synthetic_demo_only",
                "sourceType": "fixture",
                "blockingReasons": ["synthetic_or_fixture_data_not_decision_grade"],
                "warnings": [],
            },
            "ivGreeks": {
                "ivRankStatus": "unavailable",
                "ivRankSource": "provider_payload_token",
                "warnings": ["missing_iv"],
            },
            "scenarioAssumptions": {
                "requestPayload": "secret",
                "sessionToken": "abc",
                "targetPrice": 190,
            },
        },
    )
    summary = summarize_options_source_provenance_sidecar(entries)
    consumer_values = json.dumps(summary, ensure_ascii=False, sort_keys=True).lower()

    for blocked in ("token", "cookie", "session", "payload", "internal", "raw", "secret"):
        assert blocked not in consumer_values
    assert json.loads(json.dumps(summary, ensure_ascii=False, sort_keys=True)) == summary
    assert summary["entryCount"] == len(entries)
