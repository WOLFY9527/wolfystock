# -*- coding: utf-8 -*-
"""Contract tests for offline factor exposure and basket summaries."""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from src.services.factor_exposure import (
    build_factor_exposure_report,
    build_long_short_factor_exposure_report,
)
from src.services.factor_neutralization import build_sector_neutralization_report


def _observation(
    *,
    factor_id: str,
    symbol: str,
    as_of: str,
    value: float | None,
    neutralized_value: float | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
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
    }
    if neutralized_value is not None:
        payload["neutralized_value"] = neutralized_value
    return payload


def _weight(symbol: str, weight: object) -> dict[str, object]:
    return {"symbol": symbol, "weight": weight}


def _fixture_rows() -> list[dict[str, object]]:
    path = Path(__file__).parent / "fixtures" / "factor_neutralization" / "alpha_factory_observations.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_weighted_portfolio_exposure_aggregates_by_symbol_weight() -> None:
    report = build_factor_exposure_report(
        [
            _observation(factor_id="relative_strength.relative_strength_63d", symbol="AAA", as_of="2026-05-16", value=1.0),
            _observation(factor_id="relative_strength.relative_strength_63d", symbol="BBB", as_of="2026-05-16", value=3.0),
            _observation(factor_id="relative_strength.relative_strength_63d", symbol="CCC", as_of="2026-05-16", value=5.0),
        ],
        [_weight("AAA", 2.0), _weight("BBB", 1.0), _weight("CCC", 1.0)],
    )

    summary = report.factors[0]

    assert report.scope == "portfolio"
    assert summary.factor_id == "relative_strength.relative_strength_63d"
    assert summary.sample_size == 3
    assert summary.coverage == pytest.approx(1.0)
    assert summary.exposure == pytest.approx(2.5)
    assert summary.weighted_exposure == pytest.approx(10.0)
    assert summary.gross_exposure == pytest.approx(10.0)
    assert summary.net_exposure == pytest.approx(10.0)
    assert summary.missing_factor_count == 0
    assert summary.window.as_of_start == "2026-05-16"
    assert summary.window.as_of_end == "2026-05-16"
    assert summary.window.as_of_count == 1
    assert summary.warnings == ()


def test_missing_factor_observations_are_counted_without_breaking_report_order() -> None:
    report = build_factor_exposure_report(
        [
            _observation(factor_id="momentum.momentum_21d", symbol="AAA", as_of="2026-05-16", value=2.0),
            _observation(factor_id="momentum.momentum_21d", symbol="BBB", as_of="2026-05-16", value=4.0),
        ],
        [_weight("AAA", 2.0), _weight("BBB", 1.0), _weight("CCC", 1.0)],
    )

    summary = report.factors[0]

    assert summary.sample_size == 2
    assert summary.coverage == pytest.approx(2 / 3)
    assert summary.missing_factor_count == 1
    assert summary.warnings == ("missing_factor_observation",)


def test_zero_and_invalid_weights_are_reported_and_excluded() -> None:
    report = build_factor_exposure_report(
        [
            _observation(factor_id="trend.trend_strength_20d", symbol="AAA", as_of="2026-05-16", value=1.0),
            _observation(factor_id="trend.trend_strength_20d", symbol="BBB", as_of="2026-05-16", value=2.0),
        ],
        [_weight("AAA", 2.0), _weight("BBB", 0.0), _weight("CCC", "bad")],
    )

    summary = report.factors[0]

    assert report.coverage.total_positions == 3
    assert report.coverage.eligible_positions == 1
    assert report.coverage.zero_weight_count == 1
    assert report.coverage.invalid_weight_count == 1
    assert summary.sample_size == 1
    assert summary.exposure == pytest.approx(1.0)
    assert summary.weighted_exposure == pytest.approx(2.0)


def test_long_short_basket_exposure_reports_gross_and_net_exposure() -> None:
    report = build_long_short_factor_exposure_report(
        [
            _observation(factor_id="relative_strength.relative_strength_63d", symbol="AAA", as_of="2026-05-16", value=1.0),
            _observation(factor_id="relative_strength.relative_strength_63d", symbol="BBB", as_of="2026-05-16", value=3.0),
            _observation(factor_id="relative_strength.relative_strength_63d", symbol="CCC", as_of="2026-05-16", value=2.0),
            _observation(factor_id="relative_strength.relative_strength_63d", symbol="DDD", as_of="2026-05-16", value=4.0),
        ],
        long_weights=[_weight("AAA", 2.0), _weight("BBB", 1.0)],
        short_weights=[_weight("CCC", 3.0), _weight("DDD", 1.0)],
    )

    summary = report.factors[0]

    assert report.scope == "long_short"
    assert summary.long_exposure == pytest.approx(5.0)
    assert summary.short_exposure == pytest.approx(10.0)
    assert summary.gross_exposure == pytest.approx(15.0)
    assert summary.net_exposure == pytest.approx(-5.0)
    assert summary.weighted_exposure == pytest.approx(-5.0)
    assert summary.missing_factor_count == 0


def test_neutralized_factor_values_are_used_when_available() -> None:
    neutralized = build_sector_neutralization_report(_fixture_rows(), min_group_size=2)
    report = build_factor_exposure_report(
        [item for item in neutralized.values if item.symbol in {"AAA", "BBB", "CCC", "DDD"}],
        [_weight("AAA", 2.0), _weight("BBB", 1.0), _weight("CCC", 1.0), _weight("DDD", 1.0)],
    )

    summary = report.factors[0]

    assert summary.weighted_exposure == pytest.approx(-4.0)
    assert summary.exposure == pytest.approx(-0.8)


def test_output_order_is_deterministic_for_shuffled_inputs() -> None:
    observations = [
        _observation(factor_id="trend.trend_strength_20d", symbol="AAA", as_of="2026-05-16", value=1.0),
        _observation(factor_id="trend.trend_strength_20d", symbol="BBB", as_of="2026-05-16", value=2.0),
        _observation(factor_id="momentum.momentum_21d", symbol="AAA", as_of="2026-05-16", value=3.0),
        _observation(factor_id="momentum.momentum_21d", symbol="BBB", as_of="2026-05-16", value=4.0),
    ]
    weights = [_weight("AAA", 2.0), _weight("BBB", 1.0)]

    first_obs = list(observations)
    random.Random(7).shuffle(first_obs)
    first_weights = list(weights)
    random.Random(11).shuffle(first_weights)
    first = build_factor_exposure_report(first_obs, first_weights)

    second_obs = list(observations)
    random.Random(13).shuffle(second_obs)
    second_weights = list(weights)
    random.Random(17).shuffle(second_weights)
    second = build_factor_exposure_report(second_obs, second_weights)

    assert [item.factor_id for item in first.factors] == ["momentum.momentum_21d", "trend.trend_strength_20d"]
    assert [(item.factor_id, item.weighted_exposure, item.sample_size) for item in first.factors] == [
        (item.factor_id, item.weighted_exposure, item.sample_size) for item in second.factors
    ]


def test_factor_exposure_import_has_no_scanner_or_backtest_runtime_side_effects() -> None:
    script = """
import json
import src.services.factor_exposure
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
