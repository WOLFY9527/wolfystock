# -*- coding: utf-8 -*-
"""Contract tests for offline factor metrics scaffolding."""

from __future__ import annotations

import math
import random
from typing import Any

import pytest

from src.services.factor_metrics import build_factor_metrics_report


def _metric_observation(
    *,
    factor_id: str,
    symbol: str,
    as_of: str,
    value: float,
    returns: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "observation": {
            "factor_id": factor_id,
            "symbol": symbol,
            "value": value,
            "source_name": "unit_fixture",
            "source_type": "synthetic_fixture",
            "as_of": as_of,
            "observed_at": f"{as_of}T15:00:00Z",
            "freshness_status": "partial",
            "confidence": 0.55,
            "is_partial": True,
        },
        "forward_returns": dict(returns or {}),
    }


def _normal_fixture_observations() -> list[dict[str, Any]]:
    factor_a_rows = [
        ("2026-05-01", "AAA", 4.0, {"1d": 0.04, "5d": 0.01}),
        ("2026-05-01", "BBB", 3.0, {"1d": 0.03, "5d": 0.02}),
        ("2026-05-01", "CCC", 2.0, {"1d": 0.02, "5d": 0.03}),
        ("2026-05-01", "DDD", 1.0, {"1d": 0.01, "5d": 0.04}),
        ("2026-05-02", "AAA", 1.0, {"1d": 0.01, "5d": 0.04}),
        ("2026-05-02", "BBB", 4.0, {"1d": 0.04, "5d": 0.01}),
        ("2026-05-02", "CCC", 3.0, {"1d": 0.03, "5d": 0.02}),
        ("2026-05-02", "DDD", 2.0, {"1d": 0.02, "5d": 0.03}),
        ("2026-05-03", "AAA", 2.0, {"1d": 0.02, "5d": 0.03}),
        ("2026-05-03", "BBB", 1.0, {"1d": 0.01, "5d": 0.04}),
        ("2026-05-03", "CCC", 4.0, {"1d": 0.04, "5d": 0.01}),
        ("2026-05-03", "DDD", 3.0, {"1d": 0.03, "5d": 0.02}),
    ]
    factor_b_rows = [
        (as_of, symbol, -value)
        for as_of, symbol, value, _returns in factor_a_rows
    ]
    rows = [
        _metric_observation(
            factor_id="momentum.momentum_21d",
            symbol=symbol,
            as_of=as_of,
            value=value,
            returns=returns,
        )
        for as_of, symbol, value, returns in factor_a_rows
    ]
    rows.extend(
        _metric_observation(
            factor_id="trend.trend_strength_20d",
            symbol=symbol,
            as_of=as_of,
            value=value,
            returns={},
        )
        for as_of, symbol, value in factor_b_rows
    )
    return rows


def test_factor_metrics_report_computes_ic_rank_ic_decay_turnover_and_correlation() -> None:
    report = build_factor_metrics_report(_normal_fixture_observations())

    assert [item.factor_id for item in report.factors] == [
        "momentum.momentum_21d",
        "trend.trend_strength_20d",
    ]

    momentum = report.factors[0]
    assert momentum.window.as_of_start == "2026-05-01"
    assert momentum.window.as_of_end == "2026-05-03"
    assert momentum.window.as_of_count == 3
    assert momentum.window.observation_count == 12

    assert [item.horizon for item in momentum.ic] == ["1d", "5d"]
    assert momentum.ic[0].sample_size == 3
    assert momentum.ic[0].value == pytest.approx(1.0)
    assert momentum.ic[0].insufficient_reason is None
    assert momentum.ic[1].value == pytest.approx(-1.0)

    assert [item.horizon for item in momentum.rank_ic] == ["1d", "5d"]
    assert momentum.rank_ic[0].value == pytest.approx(1.0)
    assert momentum.rank_ic[1].value == pytest.approx(-1.0)

    assert [item.horizon for item in momentum.decay] == ["1d", "5d"]
    assert momentum.decay[0].decay_ratio == pytest.approx(1.0)
    assert momentum.decay[1].decay_ratio == pytest.approx(-1.0)

    assert momentum.turnover.value == pytest.approx(0.5)
    assert momentum.turnover.sample_size == 2
    assert momentum.turnover.insufficient_reason is None

    assert [item.peer_factor_id for item in momentum.factor_correlation] == ["trend.trend_strength_20d"]
    assert momentum.factor_correlation[0].value == pytest.approx(-1.0)
    assert momentum.factor_correlation[0].sample_size == 3


def test_missing_returns_and_single_horizon_produce_insufficient_reasons() -> None:
    observations = [
        _metric_observation(
            factor_id="activity.activity_burst_10d",
            symbol="AAA",
            as_of="2026-05-01",
            value=3.0,
            returns={"1d": None},
        ),
        _metric_observation(
            factor_id="activity.activity_burst_10d",
            symbol="BBB",
            as_of="2026-05-01",
            value=2.0,
            returns={"1d": float("nan")},
        ),
        _metric_observation(
            factor_id="activity.activity_burst_10d",
            symbol="CCC",
            as_of="2026-05-02",
            value=1.0,
            returns={},
        ),
        _metric_observation(
            factor_id="activity.activity_burst_10d",
            symbol="DDD",
            as_of="2026-05-02",
            value=0.0,
            returns={"1d": None},
        ),
    ]

    report = build_factor_metrics_report(observations)
    activity = report.factors[0]

    assert activity.ic[0].value is None
    assert activity.ic[0].sample_size == 0
    assert activity.ic[0].insufficient_reason == "insufficient_cross_sections"
    assert activity.rank_ic[0].insufficient_reason == "insufficient_cross_sections"
    assert activity.decay[0].decay_ratio is None
    assert activity.decay[0].insufficient_reason == "requires_multiple_horizons"
    assert activity.factor_correlation == []


def test_insufficient_observations_and_missing_turnover_pairs_are_reported() -> None:
    observations = [
        _metric_observation(
            factor_id="liquidity.liquidity_support_20d",
            symbol="AAA",
            as_of="2026-05-01",
            value=1.0,
            returns={"1d": 0.1},
        ),
        _metric_observation(
            factor_id="liquidity.liquidity_support_20d",
            symbol="BBB",
            as_of="2026-05-01",
            value=1.0,
            returns={"1d": 0.1},
        ),
    ]

    report = build_factor_metrics_report(observations)
    liquidity = report.factors[0]

    assert liquidity.ic[0].value is None
    assert liquidity.ic[0].insufficient_reason == "insufficient_cross_sections"
    assert liquidity.turnover.value is None
    assert liquidity.turnover.sample_size == 0
    assert liquidity.turnover.insufficient_reason == "insufficient_turnover_pairs"


def test_rank_ic_handles_ties_with_average_ranks() -> None:
    observations = [
        _metric_observation(
            factor_id="relative_strength.relative_strength_63d",
            symbol="AAA",
            as_of="2026-05-01",
            value=1.0,
            returns={"1d": 0.1},
        ),
        _metric_observation(
            factor_id="relative_strength.relative_strength_63d",
            symbol="BBB",
            as_of="2026-05-01",
            value=1.0,
            returns={"1d": 0.1},
        ),
        _metric_observation(
            factor_id="relative_strength.relative_strength_63d",
            symbol="CCC",
            as_of="2026-05-01",
            value=2.0,
            returns={"1d": 0.2},
        ),
        _metric_observation(
            factor_id="relative_strength.relative_strength_63d",
            symbol="DDD",
            as_of="2026-05-01",
            value=2.0,
            returns={"1d": 0.2},
        ),
        _metric_observation(
            factor_id="relative_strength.relative_strength_63d",
            symbol="AAA",
            as_of="2026-05-02",
            value=2.0,
            returns={"1d": 0.2},
        ),
        _metric_observation(
            factor_id="relative_strength.relative_strength_63d",
            symbol="BBB",
            as_of="2026-05-02",
            value=2.0,
            returns={"1d": 0.2},
        ),
        _metric_observation(
            factor_id="relative_strength.relative_strength_63d",
            symbol="CCC",
            as_of="2026-05-02",
            value=1.0,
            returns={"1d": 0.1},
        ),
        _metric_observation(
            factor_id="relative_strength.relative_strength_63d",
            symbol="DDD",
            as_of="2026-05-02",
            value=1.0,
            returns={"1d": 0.1},
        ),
    ]

    report = build_factor_metrics_report(observations)
    relative_strength = report.factors[0]

    assert relative_strength.rank_ic[0].value == pytest.approx(1.0)
    assert relative_strength.rank_ic[0].sample_size == 2


def test_nan_and_null_returns_are_filtered_without_breaking_deterministic_output() -> None:
    observations = _normal_fixture_observations()
    observations.append(
        _metric_observation(
            factor_id="momentum.momentum_21d",
            symbol="EEE",
            as_of="2026-05-01",
            value=99.0,
            returns={"1d": None, "5d": math.nan},
        )
    )
    random.Random(7).shuffle(observations)

    report = build_factor_metrics_report(observations)
    momentum = report.factors[0]

    assert [item.factor_id for item in report.factors] == [
        "momentum.momentum_21d",
        "trend.trend_strength_20d",
    ]
    assert [item.horizon for item in momentum.ic] == ["1d", "5d"]
    assert [item.peer_factor_id for item in momentum.factor_correlation] == ["trend.trend_strength_20d"]
    assert momentum.window.observation_count == 13
    assert momentum.ic[0].value == pytest.approx(1.0)
    assert momentum.ic[1].value == pytest.approx(-1.0)


def test_factor_metrics_import_has_no_scanner_or_backtest_runtime_side_effects() -> None:
    import json
    import subprocess
    import sys

    script = """
import json
import src.services.factor_metrics
blocked = [
    "src.services.market_scanner_service",
    "src.services.rule_backtest_service",
    "src.services.backtest_service",
    "api.v1.endpoints.scanner",
]
print(json.dumps({name: name in __import__('sys').modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}
