# -*- coding: utf-8 -*-
"""Contract tests for offline factor research report scaffolding."""

from __future__ import annotations

import json
import random
import subprocess
import sys
from typing import Any

import pytest

from src.services.factor_exposure import (
    build_factor_exposure_report,
    build_long_short_factor_exposure_report,
)
from src.services.factor_metrics import build_factor_metrics_report
from src.services.factor_neutralization import build_sector_neutralization_report
from src.services.factor_research_report import build_factor_research_report, build_factor_research_report_pilot


_SYMBOL_METADATA = {
    "AAA": {"sector": "Technology", "market_cap": 100.0},
    "BBB": {"sector": "Technology", "market_cap": 300.0},
    "CCC": {"sector": "Finance", "market_cap": 200.0},
    "DDD": {"sector": "Finance", "market_cap": 400.0},
}


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


def _weight(symbol: str, weight: float) -> dict[str, object]:
    return {"symbol": symbol, "weight": weight}


def _complete_metric_observations() -> list[dict[str, Any]]:
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
            value=-value,
            returns=returns,
        )
        for as_of, symbol, value, returns in factor_a_rows
    )
    return rows


def _complete_observations() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _complete_metric_observations():
        observation = dict(item["observation"])
        metadata = _SYMBOL_METADATA[observation["symbol"]]
        rows.append(
            {
                "observation": observation,
                "sector": metadata["sector"],
                "market_cap": metadata["market_cap"],
            }
        )
    return rows


def _insufficient_observations() -> list[dict[str, Any]]:
    return [
        {
            "observation": {
                "factor_id": "relative_strength.relative_strength_63d",
                "symbol": "AAA",
                "value": 1.0,
                "source_name": "unit_fixture",
                "source_type": "synthetic_fixture",
                "as_of": "2026-05-16",
                "observed_at": "2026-05-16T15:00:00Z",
                "freshness_status": "partial",
                "confidence": 0.55,
                "is_partial": True,
            },
            "sector": "Technology",
            "market_cap": 100.0,
        },
        {
            "observation": {
                "factor_id": "relative_strength.relative_strength_63d",
                "symbol": "BBB",
                "value": 1.0,
                "source_name": "unit_fixture",
                "source_type": "synthetic_fixture",
                "as_of": "2026-05-16",
                "observed_at": "2026-05-16T15:00:00Z",
                "freshness_status": "partial",
                "confidence": 0.55,
                "is_partial": True,
            },
            "sector": "Technology",
            "market_cap": 300.0,
        },
    ]


def test_complete_factor_research_report_combines_metrics_neutralization_and_exposures() -> None:
    observations = _complete_observations()
    metrics_report = build_factor_metrics_report(_complete_metric_observations())
    neutralization_report = build_sector_neutralization_report(
        [item for item in observations if item["observation"]["factor_id"] == "momentum.momentum_21d"],
        min_group_size=2,
    )
    portfolio_exposure = build_factor_exposure_report(
        list(neutralization_report.values),
        [_weight("AAA", 2.0), _weight("BBB", 1.0), _weight("CCC", 1.0), _weight("DDD", 1.0)],
    )
    basket_exposure = build_long_short_factor_exposure_report(
        list(neutralization_report.values),
        long_weights=[_weight("AAA", 2.0), _weight("BBB", 1.0)],
        short_weights=[_weight("CCC", 1.0), _weight("DDD", 1.0)],
    )

    report = build_factor_research_report(
        observations,
        metrics_report=metrics_report,
        neutralization_reports=[neutralization_report],
        exposure_reports=[basket_exposure, portfolio_exposure],
    )

    assert report.window.as_of_start == "2026-05-01"
    assert report.window.as_of_end == "2026-05-03"
    assert report.window.as_of_count == 3
    assert report.window.observation_count == 24

    assert [(item.factor_id, item.observation_count, item.symbol_count) for item in report.factor_coverage] == [
        ("momentum.momentum_21d", 12, 4),
        ("trend.trend_strength_20d", 12, 4),
    ]

    assert [item.factor_id for item in report.metrics_summary] == [
        "momentum.momentum_21d",
        "trend.trend_strength_20d",
    ]
    momentum = report.metrics_summary[0]
    assert [item.horizon for item in momentum.ic] == ["1d", "5d"]
    assert momentum.ic[0].value == pytest.approx(1.0)
    assert momentum.rank_ic[1].value == pytest.approx(-1.0)
    assert momentum.decay[1].decay_ratio == pytest.approx(-1.0)
    assert momentum.turnover.value == pytest.approx(0.5)
    assert [(item.peer_factor_id, item.value) for item in momentum.factor_correlation] == [
        ("trend.trend_strength_20d", pytest.approx(-1.0)),
    ]

    assert [(item.factor_id, item.axis, item.sample_size, item.warnings) for item in report.neutralization_summary] == [
        ("momentum.momentum_21d", "sector", 12, ()),
    ]

    assert [(item.scope, item.factor_id, item.sample_size) for item in report.exposure_summary] == [
        ("long_short", "momentum.momentum_21d", 4),
        ("portfolio", "momentum.momentum_21d", 4),
    ]
    assert report.exposure_summary[0].long_exposure is not None
    assert report.exposure_summary[0].short_exposure is not None
    assert report.exposure_summary[1].long_exposure is None
    assert report.exposure_summary[1].short_exposure is None

    assert report.missing_data_reasons == ()
    assert report.warnings == ()


def test_missing_metrics_report_is_recorded_without_dropping_other_sections() -> None:
    observations = _complete_observations()
    neutralization_report = build_sector_neutralization_report(
        [item for item in observations if item["observation"]["factor_id"] == "momentum.momentum_21d"],
        min_group_size=2,
    )
    portfolio_exposure = build_factor_exposure_report(
        list(neutralization_report.values),
        [_weight("AAA", 2.0), _weight("BBB", 1.0), _weight("CCC", 1.0), _weight("DDD", 1.0)],
    )

    report = build_factor_research_report(
        observations,
        neutralization_reports=[neutralization_report],
        exposure_reports=[portfolio_exposure],
    )

    assert report.metrics_summary == ()
    assert [(item.section, item.reason) for item in report.missing_data_reasons] == [
        ("metrics", "missing_metrics_report"),
    ]


def test_missing_neutralization_report_is_recorded() -> None:
    observations = _complete_observations()
    metrics_report = build_factor_metrics_report(_complete_metric_observations())
    portfolio_exposure = build_factor_exposure_report(
        [item for item in observations if item["observation"]["factor_id"] == "momentum.momentum_21d"],
        [_weight("AAA", 2.0), _weight("BBB", 1.0), _weight("CCC", 1.0), _weight("DDD", 1.0)],
    )

    report = build_factor_research_report(
        observations,
        metrics_report=metrics_report,
        exposure_reports=[portfolio_exposure],
    )

    assert report.neutralization_summary == ()
    assert ("neutralization", "missing_neutralization_report") in [
        (item.section, item.reason) for item in report.missing_data_reasons
    ]


def test_missing_exposure_report_is_recorded() -> None:
    observations = _complete_observations()
    metrics_report = build_factor_metrics_report(_complete_metric_observations())
    neutralization_report = build_sector_neutralization_report(
        [item for item in observations if item["observation"]["factor_id"] == "momentum.momentum_21d"],
        min_group_size=2,
    )

    report = build_factor_research_report(
        observations,
        metrics_report=metrics_report,
        neutralization_reports=[neutralization_report],
    )

    assert report.exposure_summary == ()
    assert ("exposure", "missing_exposure_report") in [
        (item.section, item.reason) for item in report.missing_data_reasons
    ]


def test_insufficient_sample_sizes_are_summarized_as_missing_data_reasons() -> None:
    observations = _insufficient_observations()
    metrics_report = build_factor_metrics_report(
        [
            _metric_observation(
                factor_id="relative_strength.relative_strength_63d",
                symbol="AAA",
                as_of="2026-05-16",
                value=1.0,
                returns={"1d": 0.1},
            ),
            _metric_observation(
                factor_id="relative_strength.relative_strength_63d",
                symbol="BBB",
                as_of="2026-05-16",
                value=1.0,
                returns={"1d": 0.1},
            ),
        ]
    )
    neutralization_report = build_sector_neutralization_report(observations, min_group_size=3)
    exposure_report = build_factor_exposure_report(
        observations,
        [_weight("AAA", 1.0), _weight("BBB", 1.0)],
    )

    report = build_factor_research_report(
        observations,
        metrics_report=metrics_report,
        neutralization_reports=[neutralization_report],
        exposure_reports=[exposure_report],
    )

    reasons = {(item.section, item.reason, item.factor_id, item.context) for item in report.missing_data_reasons}
    assert ("metrics", "insufficient_cross_sections", "relative_strength.relative_strength_63d", "ic:1d") in reasons
    assert ("metrics", "insufficient_cross_sections", "relative_strength.relative_strength_63d", "rank_ic:1d") in reasons
    assert ("metrics", "requires_multiple_horizons", "relative_strength.relative_strength_63d", "decay") in reasons
    assert ("metrics", "insufficient_turnover_pairs", "relative_strength.relative_strength_63d", "turnover") in reasons
    assert ("neutralization", "insufficient_group_size", "relative_strength.relative_strength_63d", "sector") in reasons


def test_output_order_is_deterministic_for_shuffled_inputs() -> None:
    observations = _complete_observations()
    metric_observations = _complete_metric_observations()

    first_obs = list(observations)
    random.Random(7).shuffle(first_obs)
    first_metric_obs = list(metric_observations)
    random.Random(11).shuffle(first_metric_obs)
    first_report = build_factor_research_report(
        first_obs,
        metrics_report=build_factor_metrics_report(first_metric_obs),
    )

    second_obs = list(observations)
    random.Random(13).shuffle(second_obs)
    second_metric_obs = list(metric_observations)
    random.Random(17).shuffle(second_metric_obs)
    second_report = build_factor_research_report(
        second_obs,
        metrics_report=build_factor_metrics_report(second_metric_obs),
    )

    assert [(item.factor_id, item.observation_count, item.symbol_count) for item in first_report.factor_coverage] == [
        (item.factor_id, item.observation_count, item.symbol_count) for item in second_report.factor_coverage
    ]
    assert [(item.factor_id, item.turnover.value) for item in first_report.metrics_summary] == [
        (item.factor_id, item.turnover.value) for item in second_report.metrics_summary
    ]
    assert [(item.section, item.reason) for item in first_report.missing_data_reasons] == [
        (item.section, item.reason) for item in second_report.missing_data_reasons
    ]


def test_factor_research_report_import_has_no_scanner_or_backtest_runtime_side_effects() -> None:
    script = """
import json
import src.services.factor_research_report
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


def test_factor_research_report_pilot_adds_metadata_boundary_and_reproducibility() -> None:
    payload = build_factor_research_report_pilot(
        observations=_complete_observations(),
        metric_observations=_complete_metric_observations(),
        portfolio_weights=[_weight("AAA", 2.0), _weight("BBB", 1.0), _weight("CCC", 1.0), _weight("DDD", 1.0)],
        long_weights=[_weight("AAA", 2.0), _weight("BBB", 1.0)],
        short_weights=[_weight("CCC", 1.0), _weight("DDD", 1.0)],
        neutralization_axes=["sector"],
    )

    assert payload["status"] == "ready"
    assert payload["boundary"]["purpose"] == "diagnostic factor report"
    assert payload["boundary"]["research_only"] is True
    assert payload["boundary"]["diagnostic_only"] is True
    assert payload["boundary"]["supplied_observations_only"] is True
    assert payload["boundary"]["portfolio_optimizer"] is False
    assert payload["boundary"]["professional_readiness_claimed"] is False
    assert payload["boundary"]["external_data_hydration_executed"] is False
    assert payload["boundary"]["live_quote_hydration_executed"] is False
    assert payload["boundary"]["forward_returns_computed"] is False
    assert payload["boundary"]["forward_returns_required_for_performance"] is True
    assert [item["factor_id"] for item in payload["factor_metadata"]] == [
        "momentum.momentum_21d",
        "trend.trend_strength_20d",
    ]
    assert payload["input_shape"]["observation_count"] == 24
    assert payload["input_shape"]["metric_observation_count"] == 24
    assert payload["input_shape"]["forward_return_observation_count"] == 24
    assert payload["input_shape"]["portfolio_weight_count"] == 4
    assert payload["input_shape"]["long_weight_count"] == 2
    assert payload["input_shape"]["short_weight_count"] == 2
    assert payload["input_shape"]["neutralization_axes"] == ["sector"]
    assert payload["input_shape"]["hash_algorithm"] == "sha256"
    assert len(payload["input_shape"]["input_content_hash"]) == 64

    momentum = payload["report"]["metrics_summary"][0]
    assert momentum["factor_id"] == "momentum.momentum_21d"
    assert momentum["ic"][0]["value"] == pytest.approx(1.0)
    assert momentum["rank_ic"][1]["value"] == pytest.approx(-1.0)

    assert {item["scope"] for item in payload["report"]["exposure_summary"]} == {"long_short", "portfolio"}
    portfolio_momentum = next(
        item
        for item in payload["report"]["exposure_summary"]
        if item["scope"] == "portfolio" and item["factor_id"] == "momentum.momentum_21d"
    )
    assert portfolio_momentum["weighted_exposure"] == pytest.approx(12.0)
    assert portfolio_momentum["exposure"] == pytest.approx(2.4)
    assert payload["missing_data_reasons"] == []
    assert payload["warnings"] == []


def test_factor_research_report_pilot_does_not_invent_performance_without_forward_returns() -> None:
    metric_observations = [
        _metric_observation(
            factor_id="momentum.momentum_21d",
            symbol=symbol,
            as_of="2026-05-01",
            value=value,
            returns={},
        )
        for symbol, value in (("AAA", 4.0), ("BBB", 3.0), ("CCC", 2.0), ("DDD", 1.0))
    ]

    payload = build_factor_research_report_pilot(
        observations=[{"observation": item["observation"], "sector": "Technology", "market_cap": 100.0} for item in metric_observations],
        metric_observations=metric_observations,
    )

    assert payload["status"] == "partial"
    reasons = {(item["section"], item["reason"], item.get("factor_id")) for item in payload["missing_data_reasons"]}
    assert ("metrics", "missing_forward_returns", "momentum.momentum_21d") in reasons
    assert payload["report"]["metrics_summary"][0]["ic"] == []
    assert payload["report"]["metrics_summary"][0]["rank_ic"] == []


def test_factor_research_report_pilot_uses_supplied_metadata_for_neutralization_only() -> None:
    observations = _insufficient_observations()

    payload = build_factor_research_report_pilot(
        observations=observations,
        metric_observations=[
            _metric_observation(
                factor_id="relative_strength.relative_strength_63d",
                symbol="AAA",
                as_of="2026-05-16",
                value=1.0,
                returns={"1d": 0.1},
            ),
            _metric_observation(
                factor_id="relative_strength.relative_strength_63d",
                symbol="BBB",
                as_of="2026-05-16",
                value=1.0,
                returns={"1d": 0.1},
            ),
        ],
        neutralization_axes=["sector"],
        min_group_size=3,
    )

    assert payload["status"] == "partial"
    summary = payload["report"]["neutralization_summary"][0]
    assert summary["axis"] == "sector"
    assert summary["sample_size"] == 0
    assert summary["insufficient_group_observations"] == 2
    reasons = {(item["section"], item["reason"], item.get("context")) for item in payload["missing_data_reasons"]}
    assert ("neutralization", "insufficient_group_size", "sector") in reasons
