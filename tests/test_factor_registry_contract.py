# -*- coding: utf-8 -*-
"""Contract tests for the inert factor definition registry."""

from __future__ import annotations

import json
import subprocess
import sys

from api.v1.schemas.factors import FactorDefinition
from src.services.factor_registry import get_factor_definition, list_factor_definitions, list_factor_families


EXPECTED_FACTOR_IDS = (
    "activity.activity_burst_10d",
    "liquidity.liquidity_support_20d",
    "momentum.momentum_21d",
    "relative_strength.relative_strength_63d",
    "sector_context.sector_relative_breadth_20d",
    "trend.trend_strength_20d",
    "volatility_quality.volatility_quality_21d",
)


def test_registry_contains_expected_seed_families_in_deterministic_order() -> None:
    definitions = list_factor_definitions()

    assert tuple(item.factor_id for item in definitions) == EXPECTED_FACTOR_IDS
    assert list_factor_families() == tuple(item.family for item in definitions)


def test_registry_lookup_uses_normalized_factor_ids() -> None:
    definition = get_factor_definition(" Relative-Strength.Relative-Strength 63D ")

    assert definition is not None
    assert definition.factor_id == "relative_strength.relative_strength_63d"
    assert definition.family == "relative_strength"


def test_definition_normalizes_factor_id_and_matches_family_prefix() -> None:
    definition = FactorDefinition(
        factor_id="Trend.Trend-Strength 20D",
        family="trend",
        label="Trend Strength 20D",
        description="Test factor",
        direction="higher_is_better",
    )

    assert definition.factor_id == "trend.trend_strength_20d"


def test_registry_import_has_no_runtime_side_effects() -> None:
    script = """
import json
import src.services.factor_registry
blocked = [
    "src.services.market_scanner_service",
    "src.services.backtest_service",
    "src.services.portfolio_service",
    "src.services.market_cache",
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
