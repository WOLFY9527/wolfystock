# -*- coding: utf-8 -*-
"""Contract tests for offline factor neutralization scaffolding."""

from __future__ import annotations

import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

from src.services.factor_neutralization import (
    build_market_cap_bucket_neutralization_report,
    build_sector_neutralization_report,
)


def _fixture_rows() -> list[dict[str, object]]:
    path = Path(__file__).parent / "fixtures" / "factor_neutralization" / "alpha_factory_observations.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_sector_neutralization_returns_group_residuals_with_metadata_and_warnings() -> None:
    report = build_sector_neutralization_report(_fixture_rows(), min_group_size=2)

    assert report.factor_id == "relative_strength.relative_strength_63d"
    assert report.axis == "sector"
    assert report.neutralization_method == "sector_residual"
    assert report.sample_size == 5
    assert report.window.as_of_start == "2026-05-16"
    assert report.window.as_of_end == "2026-05-16"
    assert report.window.as_of_count == 1
    assert report.window.observation_count == 7
    assert report.coverage.total_observations == 7
    assert report.coverage.neutralized_observations == 5
    assert report.coverage.missing_group_metadata == 1
    assert report.coverage.insufficient_group_observations == 1
    assert report.warnings == (
        "missing_group_metadata",
        "insufficient_group_size",
    )

    by_symbol = {item.symbol: item for item in report.values}
    assert by_symbol["AAA"].neutralized_value == pytest.approx(-2.0)
    assert by_symbol["BBB"].neutralized_value == pytest.approx(0.0)
    assert by_symbol["CCC"].neutralized_value == pytest.approx(-1.0)
    assert by_symbol["DDD"].neutralized_value == pytest.approx(1.0)
    assert by_symbol["GGG"].neutralized_value == pytest.approx(2.0)
    assert by_symbol["EEE"].neutralized_value is None
    assert by_symbol["EEE"].insufficient_reason == "insufficient_group_size"
    assert by_symbol["FFF"].neutralized_value is None
    assert by_symbol["FFF"].insufficient_reason == "missing_group_metadata"

    assert [(item.as_of, item.group_key, item.sample_size) for item in report.group_coverage] == [
        ("2026-05-16", "Finance", 2),
        ("2026-05-16", "Healthcare", 1),
        ("2026-05-16", "Technology", 3),
    ]


def test_market_cap_bucket_neutralization_uses_deterministic_bucket_assignment() -> None:
    report = build_market_cap_bucket_neutralization_report(
        _fixture_rows(),
        bucket_count=3,
        min_group_size=2,
    )

    assert report.axis == "market_cap_bucket"
    assert report.neutralization_method == "market_cap_bucket_residual"
    assert report.sample_size == 6
    assert report.coverage.total_observations == 7
    assert report.coverage.neutralized_observations == 6
    assert report.coverage.missing_group_metadata == 1
    assert report.warnings == ("missing_group_metadata",)

    by_symbol = {item.symbol: item for item in report.values}
    assert by_symbol["AAA"].group_key == "bucket_1"
    assert by_symbol["CCC"].group_key == "bucket_1"
    assert by_symbol["BBB"].group_key == "bucket_2"
    assert by_symbol["DDD"].group_key == "bucket_2"
    assert by_symbol["EEE"].group_key == "bucket_3"
    assert by_symbol["FFF"].group_key == "bucket_3"
    assert by_symbol["AAA"].neutralized_value == pytest.approx(-0.5)
    assert by_symbol["CCC"].neutralized_value == pytest.approx(0.5)
    assert by_symbol["BBB"].neutralized_value == pytest.approx(-0.5)
    assert by_symbol["DDD"].neutralized_value == pytest.approx(0.5)
    assert by_symbol["EEE"].neutralized_value == pytest.approx(1.0)
    assert by_symbol["FFF"].neutralized_value == pytest.approx(-1.0)
    assert by_symbol["GGG"].neutralized_value is None
    assert by_symbol["GGG"].insufficient_reason == "missing_group_metadata"


def test_missing_group_metadata_is_reported_without_dropping_row_order() -> None:
    report = build_sector_neutralization_report(_fixture_rows(), min_group_size=2)

    assert [item.symbol for item in report.values] == [
        "AAA",
        "BBB",
        "CCC",
        "DDD",
        "EEE",
        "FFF",
        "GGG",
    ]
    assert [item.insufficient_reason for item in report.values if item.insufficient_reason] == [
        "insufficient_group_size",
        "missing_group_metadata",
    ]


def test_insufficient_group_size_marks_each_member_and_group_coverage() -> None:
    report = build_sector_neutralization_report(_fixture_rows(), min_group_size=2)

    insufficient_rows = [item for item in report.values if item.insufficient_reason == "insufficient_group_size"]
    assert [item.symbol for item in insufficient_rows] == ["EEE"]
    healthcare_group = next(item for item in report.group_coverage if item.group_key == "Healthcare")
    assert healthcare_group.sample_size == 1
    assert healthcare_group.neutralized_count == 0
    assert healthcare_group.insufficient_reason == "insufficient_group_size"


def test_ties_nulls_and_nans_are_filtered_without_breaking_group_calculation() -> None:
    rows = [
        {
            "observation": {
                "factor_id": "relative_strength.relative_strength_63d",
                "symbol": "AAA",
                "value": 2.0,
                "source_name": "unit_fixture",
                "source_type": "synthetic_fixture",
                "as_of": "2026-05-16",
                "observed_at": "2026-05-16T15:00:00Z",
                "freshness_status": "partial",
                "confidence": 0.55,
                "is_partial": True,
            },
            "sector": "Technology",
        },
        {
            "observation": {
                "factor_id": "relative_strength.relative_strength_63d",
                "symbol": "BBB",
                "value": 2.0,
                "source_name": "unit_fixture",
                "source_type": "synthetic_fixture",
                "as_of": "2026-05-16",
                "observed_at": "2026-05-16T15:00:00Z",
                "freshness_status": "partial",
                "confidence": 0.55,
                "is_partial": True,
            },
            "sector": "Technology",
        },
        {
            "observation": {
                "factor_id": "relative_strength.relative_strength_63d",
                "symbol": "CCC",
                "value": math.nan,
                "source_name": "unit_fixture",
                "source_type": "synthetic_fixture",
                "as_of": "2026-05-16",
                "observed_at": "2026-05-16T15:00:00Z",
                "freshness_status": "partial",
                "confidence": 0.55,
                "is_partial": True,
            },
            "sector": "Technology",
        },
        {
            "observation": {
                "factor_id": "relative_strength.relative_strength_63d",
                "symbol": "DDD",
                "value": None,
                "source_name": "unit_fixture",
                "source_type": "synthetic_fixture",
                "as_of": "2026-05-16",
                "observed_at": "2026-05-16T15:00:00Z",
                "freshness_status": "partial",
                "confidence": 0.55,
                "is_partial": True,
            },
            "sector": "Technology",
        },
        {
            "observation": {
                "factor_id": "relative_strength.relative_strength_63d",
                "symbol": "EEE",
                "value": 1.0,
                "source_name": "unit_fixture",
                "source_type": "synthetic_fixture",
                "as_of": "2026-05-16",
                "observed_at": "2026-05-16T15:00:00Z",
                "freshness_status": "partial",
                "confidence": 0.55,
                "is_partial": True,
            },
            "sector": "Finance",
        },
        {
            "observation": {
                "factor_id": "relative_strength.relative_strength_63d",
                "symbol": "FFF",
                "value": 3.0,
                "source_name": "unit_fixture",
                "source_type": "synthetic_fixture",
                "as_of": "2026-05-16",
                "observed_at": "2026-05-16T15:00:00Z",
                "freshness_status": "partial",
                "confidence": 0.55,
                "is_partial": True,
            },
            "sector": "Finance",
        },
    ]

    report = build_sector_neutralization_report(rows, min_group_size=2)
    by_symbol = {item.symbol: item for item in report.values}

    assert by_symbol["AAA"].neutralized_value == pytest.approx(0.0)
    assert by_symbol["BBB"].neutralized_value == pytest.approx(0.0)
    assert by_symbol["EEE"].neutralized_value == pytest.approx(-1.0)
    assert by_symbol["FFF"].neutralized_value == pytest.approx(1.0)
    assert by_symbol["CCC"].neutralized_value is None
    assert by_symbol["CCC"].insufficient_reason == "invalid_observation_value"
    assert by_symbol["DDD"].neutralized_value is None
    assert by_symbol["DDD"].insufficient_reason == "invalid_observation_value"
    assert report.coverage.invalid_observation_values == 2
    assert report.warnings == ("invalid_observation_value",)


def test_output_order_is_deterministic_for_shuffled_inputs() -> None:
    rows = _fixture_rows()
    random.Random(7).shuffle(rows)

    first = build_market_cap_bucket_neutralization_report(rows, bucket_count=3, min_group_size=2)
    random.Random(11).shuffle(rows)
    second = build_market_cap_bucket_neutralization_report(rows, bucket_count=3, min_group_size=2)

    assert [(item.symbol, item.group_key, item.neutralized_value) for item in first.values] == [
        (item.symbol, item.group_key, item.neutralized_value) for item in second.values
    ]
    assert [item.symbol for item in first.values] == [
        "AAA",
        "BBB",
        "CCC",
        "DDD",
        "EEE",
        "FFF",
        "GGG",
    ]


def test_factor_neutralization_import_has_no_scanner_or_backtest_runtime_side_effects() -> None:
    script = """
import json
import src.services.factor_neutralization
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
