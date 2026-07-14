from __future__ import annotations

import builtins
import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from src.services.scanner_readiness_evaluator import (
    ScannerReadinessEvidence,
    evaluate_scanner_readiness,
    serialize_scanner_readiness,
)


EXPECTED_PAYLOAD_KEYS = {
    "state",
    "availabilityState",
    "executionState",
    "market",
    "profile",
    "universeAvailability",
    "universeSize",
    "quoteCoverage",
    "historyCoverage",
    "universeReadiness",
    "scannerUniverseReadiness",
    "quoteReadiness",
    "historyReadiness",
    "cacheReadiness",
    "benchmarkReadiness",
    "candidateGenerationState",
    "candidateGenerationBlockers",
    "candidateGenerationLimitations",
    "blockedStates",
    "primaryBlockedState",
    "freshness",
    "quoteFreshness",
    "quoteReadinessLimitation",
    "universeSource",
    "scannerLineage",
    "symbolsEvaluated",
    "symbolsWithSufficientData",
    "symbolsSkipped",
    "noExternalCalls",
    "providerCallsEnabled",
    "historicalOhlcvReadinessSummary",
    "requiredBars",
    "usableBars",
    "missingBars",
    "missingRequirements",
    "blockedSymbols",
    "degradedSymbols",
    "ohlcvReadiness",
    "candidateEvaluationCount",
    "selectedCount",
    "rejectedCount",
    "failedCount",
    "blockerBucket",
    "consumerSummary",
    "nextDataAction",
}


def _ohlcv(
    symbol: str,
    *,
    state: str = "ready",
    availability: str = "available",
    execution: str = "executable",
    requirements: tuple[str, ...] = (),
    required_bars: int = 60,
    usable_bars: int = 80,
    missing_bars: int = 0,
    provider_state: str = "available",
    freshness_state: str = "current",
) -> dict[str, Any]:
    return {
        "contractVersion": "scanner_ohlcv_readiness_v1",
        "market": "us" if symbol.isalpha() else "cn",
        "profile": "test",
        "availabilityState": availability,
        "executionState": execution,
        "overallState": state,
        "requiredBars": required_bars,
        "usableBars": usable_bars,
        "missingBars": missing_bars,
        "missingRequirements": list(requirements),
        "blockedSymbols": [symbol] if execution == "blocked" else [],
        "degradedSymbols": [symbol] if execution == "degraded" else [],
        "symbolStates": [
            {
                "symbol": symbol,
                "overallState": state,
                "providerState": provider_state,
                "freshnessState": freshness_state,
                "adjustmentState": "available",
                "benchmarkState": "available",
                "requiredBars": required_bars,
                "usableBars": usable_bars,
                "missingBars": missing_bars,
                "missingRequirements": list(requirements),
            }
        ],
        "consumerSafe": True,
    }


def _quote(
    symbol: str,
    *,
    state: str = "available",
) -> dict[str, Any]:
    available = [symbol] if state == "available" else []
    missing = [symbol] if state == "missing" else []
    stale = [symbol] if state == "stale" else []
    if state == "partial":
        available = [symbol]
        missing = ["MISSING"]
    return {
        "contractVersion": "quote_snapshot_readiness_v1",
        "availabilityState": state,
        "freshnessState": state,
        "providerState": "available" if state != "missing" else "provider_missing",
        "availableSymbols": available,
        "missingSymbols": missing,
        "staleSymbols": stale,
        "sourceFamilies": ["local_test_cache"],
        "missingRequirements": [] if state == "available" else ["quote_snapshot"],
        "consumerSafe": True,
    }


def _ready_evidence(market: str = "cn") -> ScannerReadinessEvidence:
    symbol = {"cn": "600001", "hk": "HK00700", "us": "AAPL"}[market]
    diagnostics = {
        "universe_selection": {
            "universe_type": "symbols",
            "accepted_symbols": [symbol],
        },
        "snapshot_source": "local_test_cache",
        "history_stats": {
            "local_hits": 1,
            "network_fetches": 0,
            "skipped_for_history": 0,
        },
        "candidate_diagnostics": {
            symbol: {
                "symbol": symbol,
                "status": "selected",
            }
        },
        "generatedAt": "2026-07-14T00:00:00+00:00",
        "universeSource": "deterministic_test_source",
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }
    return ScannerReadinessEvidence(
        market=market,
        profile=f"{market}_preopen_v1",
        status="completed",
        universe_size=1,
        evaluated_size=1,
        shortlist_size=1,
        diagnostics=diagnostics,
        summary={
            "selected_count": 1,
            "rejected_count": 0,
            "data_failed_count": 0,
            "error_count": 0,
            "evaluated_count": 1,
        },
        candidates=({"symbol": symbol, "status": "selected"},),
        cache_universe_readiness={
            "status": "available",
            "universeSize": 1,
            "lastUpdatedAt": "2026-07-14T00:00:00+00:00",
            "freshnessState": "fresh",
        },
        ohlcv_readiness=_ohlcv(symbol),
        quote_snapshot_readiness=_quote(symbol),
    )


@pytest.mark.parametrize("market", ["cn", "hk", "us"])
def test_fully_ready_markets_share_one_canonical_result(market: str) -> None:
    result = evaluate_scanner_readiness(_ready_evidence(market))
    payload = serialize_scanner_readiness(result)

    assert result.state == "ready"
    assert result.candidate_generation_state == "ready"
    assert payload["market"] == market
    assert payload["availabilityState"] == "available"
    assert payload["executionState"] == "executable"
    assert payload["universeReadiness"]["state"] == payload["universeAvailability"] == "available"
    assert payload["quoteReadiness"]["state"] == payload["quoteCoverage"] == "available"
    assert payload["historyReadiness"]["state"] == payload["historyCoverage"] == "available"
    assert set(payload) == EXPECTED_PAYLOAD_KEYS


def test_missing_universe_evidence_fails_closed() -> None:
    evidence = replace(
        _ready_evidence(),
        universe_size=None,
        cache_universe_readiness={},
    )

    result = evaluate_scanner_readiness(evidence)

    assert result.state == "blocked"
    assert result.universe_availability == "missing"
    assert "universe_missing" in result.candidate_generation_blockers


def test_missing_historical_ohlcv_blocks_readiness() -> None:
    evidence = replace(
        _ready_evidence(),
        ohlcv_readiness=_ohlcv(
            "600001",
            state="blocked",
            availability="not_available",
            execution="blocked",
            requirements=("provider_missing", "insufficient_history"),
            usable_bars=0,
            missing_bars=60,
            provider_state="provider_missing",
        ),
    )

    result = evaluate_scanner_readiness(evidence)

    assert result.state == "blocked"
    assert result.history_coverage == "missing"
    assert "provider_missing" in result.candidate_generation_blockers
    assert result.usable_bars == 0
    assert result.missing_bars == 60


def test_partial_ohlcv_coverage_is_not_ready() -> None:
    evidence = replace(
        _ready_evidence(),
        diagnostics={
            **dict(_ready_evidence().diagnostics),
            "history_stats": {
                "local_hits": 1,
                "network_fetches": 0,
                "skipped_for_history": 1,
            },
        },
    )

    result = evaluate_scanner_readiness(evidence)

    assert result.state == "partial"
    assert result.history_coverage == "partial"
    assert result.candidate_generation_state == "degraded"


def test_stale_historical_evidence_stays_stale() -> None:
    evidence = replace(
        _ready_evidence(),
        ohlcv_readiness=_ohlcv(
            "600001",
            state="degraded",
            availability="degraded",
            execution="degraded",
            requirements=("stale_data",),
            freshness_state="stale",
        ),
    )

    result = evaluate_scanner_readiness(evidence)

    assert result.state == "partial"
    assert result.freshness == "stale"
    assert result.history_coverage == "partial"
    assert result.candidate_generation_state != "ready"


def test_missing_quote_evidence_does_not_become_available() -> None:
    evidence = replace(
        _ready_evidence(),
        diagnostics={
            key: value
            for key, value in dict(_ready_evidence().diagnostics).items()
            if key != "snapshot_source"
        },
        quote_snapshot_readiness=_quote("600001", state="missing"),
    )

    result = evaluate_scanner_readiness(evidence)

    assert result.quote_coverage == "missing"
    assert result.state == "partial"
    assert result.candidate_generation_state == "blocked"
    assert "missing_quote_snapshot" in result.candidate_generation_blockers


def test_partial_quote_coverage_is_not_ready() -> None:
    evidence = replace(
        _ready_evidence(),
        quote_snapshot_readiness=_quote("600001", state="partial"),
    )

    result = evaluate_scanner_readiness(evidence)

    assert result.quote_coverage == "partial"
    assert result.state == "partial"
    assert result.candidate_generation_state == "degraded"


def test_stale_quote_evidence_stays_stale() -> None:
    evidence = replace(
        _ready_evidence("us"),
        quote_snapshot_readiness=_quote("AAPL", state="stale"),
    )

    result = evaluate_scanner_readiness(evidence)

    assert result.quote_coverage == "stale"
    assert result.freshness == "stale"
    assert result.state == "partial"
    assert result.candidate_generation_state == "degraded"
    assert "quote_unavailable_or_stale" in result.candidate_generation_limitations


@pytest.mark.parametrize(
    ("source_marker", "limitation"),
    [("synthetic", "synthetic_evidence"), ("fixture", "fixture_evidence")],
)
def test_non_production_evidence_never_becomes_real_or_ready(
    source_marker: str,
    limitation: str,
) -> None:
    evidence = replace(
        _ready_evidence(),
        source_markers=(source_marker,),
    )

    result = evaluate_scanner_readiness(evidence)
    payload = serialize_scanner_readiness(result)

    assert result.state == "partial"
    assert result.availability_state == "degraded"
    assert result.execution_state == "degraded"
    assert result.candidate_generation_state == "degraded"
    assert limitation in result.candidate_generation_limitations
    assert payload["state"] != "ready"


def test_conflicting_component_states_fail_closed() -> None:
    ready = _ready_evidence()
    evidence = replace(
        ready,
        status="failed",
        shortlist_size=0,
        evaluated_size=0,
        summary={"selected_count": 0, "data_failed_count": 1},
        diagnostics={
            **dict(ready.diagnostics),
            "reason_code": "missing_quote_or_snapshot",
        },
    )

    result = evaluate_scanner_readiness(evidence)

    assert result.quote_coverage == "available"
    assert result.state == "blocked"
    assert result.candidate_generation_state == "blocked"
    assert "missing_quote_snapshot" in result.candidate_generation_blockers


def test_unavailable_component_blocks_readiness() -> None:
    evidence = replace(
        _ready_evidence("hk"),
        ohlcv_readiness=_ohlcv(
            "HK00700",
            state="blocked",
            availability="not_available",
            execution="blocked",
            requirements=("provider_unavailable",),
            usable_bars=0,
            missing_bars=60,
            provider_state="provider_unavailable",
        ),
    )

    result = evaluate_scanner_readiness(evidence)

    assert result.state == "blocked"
    assert result.availability_state == "not_available"
    assert result.execution_state == "blocked"
    assert "provider_unavailable" in result.candidate_generation_blockers


def test_empty_evidence_is_unknown_and_preserves_missing_counts() -> None:
    result = evaluate_scanner_readiness(ScannerReadinessEvidence())

    assert result.state == "unknown"
    assert result.selected_count is None
    assert result.candidate_evaluation_count is None
    assert result.universe_size is None
    assert result.state != "ready"


def test_zero_valued_evidence_remains_explicit_and_not_ready() -> None:
    evidence = ScannerReadinessEvidence(
        market="cn",
        profile="cn_preopen_v1",
        status="completed",
        universe_size=0,
        evaluated_size=0,
        shortlist_size=0,
        summary={
            "selected_count": 0,
            "rejected_count": 0,
            "data_failed_count": 0,
            "error_count": 0,
            "evaluated_count": 0,
        },
        cache_universe_readiness={"status": "missing", "universeSize": 0},
    )

    result = evaluate_scanner_readiness(evidence)

    assert result.selected_count == 0
    assert result.candidate_evaluation_count == 0
    assert result.universe_size == 0
    assert result.state == "blocked"


def test_repeated_evaluation_is_deterministic() -> None:
    evidence = _ready_evidence("us")

    first = evaluate_scanner_readiness(evidence)
    second = evaluate_scanner_readiness(evidence)

    assert first == second
    assert serialize_scanner_readiness(first) == serialize_scanner_readiness(second)


def test_evaluator_performs_no_io_or_dependency_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    class DependencyProbe:
        def __init__(self) -> None:
            self.calls = 0

        def __getattr__(self, _name: str):
            self.calls += 1
            raise AssertionError("dependency method accessed")

    probes = {
        "provider": DependencyProbe(),
        "cache": DependencyProbe(),
        "database": DependencyProbe(),
    }
    ready = _ready_evidence()
    evidence = replace(
        ready,
        diagnostics={**dict(ready.diagnostics), "dependency_probes": probes},
    )

    def fail(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("I/O or ambient lookup attempted")

    monkeypatch.setattr(builtins, "open", fail)
    monkeypatch.setattr(os, "getenv", fail)
    monkeypatch.setattr(time, "time", fail)
    monkeypatch.setattr(Path, "exists", fail)
    monkeypatch.setattr(Path, "read_text", fail)

    result = evaluate_scanner_readiness(evidence)

    assert result.state == "ready"
    assert all(probe.calls == 0 for probe in probes.values())
