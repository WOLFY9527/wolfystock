# -*- coding: utf-8 -*-
"""Deterministic factor definition seed registry.

This module is metadata only. It must not import runtime scanner/backtest/
portfolio/provider services, persist to storage, or alter existing behavior.
"""

from __future__ import annotations

from types import MappingProxyType

from api.v1.schemas.factors import FactorDefinition, FactorNeutralizationSpec, normalize_factor_id


_SEEDED_DEFINITIONS = tuple(
    sorted(
        (
            FactorDefinition(
                factor_id="trend.trend_strength_20d",
                family="trend",
                label="Trend Strength 20D",
                description="Normalized trend persistence over the trailing 20 trading days.",
                direction="higher_is_better",
                unit="normalized_score",
                default_lookback_days=20,
                expected_range_min=-1,
                expected_range_max=1,
                tags=["seed", "trend"],
            ),
            FactorDefinition(
                factor_id="momentum.momentum_21d",
                family="momentum",
                label="Momentum 21D",
                description="Short-horizon return continuation signal over roughly one trading month.",
                direction="higher_is_better",
                unit="normalized_score",
                default_lookback_days=21,
                expected_range_min=-1,
                expected_range_max=1,
                tags=["seed", "momentum"],
            ),
            FactorDefinition(
                factor_id="relative_strength.relative_strength_63d",
                family="relative_strength",
                label="Relative Strength 63D",
                description="Cross-sectional excess strength versus a peer group over one quarter.",
                direction="higher_is_better",
                unit="normalized_score",
                default_lookback_days=63,
                expected_range_min=-1,
                expected_range_max=1,
                neutralization=FactorNeutralizationSpec(
                    method="cross_sectional_rank",
                    axes=["sector", "market_cap_bucket"],
                    exposure_limit=0.35,
                ),
                tags=["seed", "relative_strength", "cross_sectional"],
            ),
            FactorDefinition(
                factor_id="volatility_quality.volatility_quality_21d",
                family="volatility_quality",
                label="Volatility Quality 21D",
                description="Preference for orderly realized volatility rather than unstable high-variance behavior.",
                direction="lower_is_better",
                unit="normalized_score",
                default_lookback_days=21,
                expected_range_min=-1,
                expected_range_max=1,
                tags=["seed", "volatility_quality"],
            ),
            FactorDefinition(
                factor_id="liquidity.liquidity_support_20d",
                family="liquidity",
                label="Liquidity Support 20D",
                description="Depth and turnover support proxy for executable participation quality.",
                direction="higher_is_better",
                unit="normalized_score",
                default_lookback_days=20,
                expected_range_min=0,
                expected_range_max=1,
                tags=["seed", "liquidity"],
            ),
            FactorDefinition(
                factor_id="activity.activity_burst_10d",
                family="activity",
                label="Activity Burst 10D",
                description="Abnormal attention and participation burst relative to a recent baseline.",
                direction="higher_is_better",
                unit="normalized_score",
                default_lookback_days=10,
                expected_range_min=0,
                expected_range_max=1,
                tags=["seed", "activity"],
            ),
            FactorDefinition(
                factor_id="sector_context.sector_relative_breadth_20d",
                family="sector_context",
                label="Sector Relative Breadth 20D",
                description="Sector backdrop strength used as context rather than a standalone directional edge.",
                direction="context_only",
                unit="normalized_score",
                default_lookback_days=20,
                expected_range_min=-1,
                expected_range_max=1,
                neutralization=FactorNeutralizationSpec(
                    method="sector_residual",
                    axes=["sector"],
                    exposure_limit=0.25,
                ),
                tags=["seed", "sector_context"],
            ),
        ),
        key=lambda item: item.factor_id,
    )
)
_DEFINITIONS_BY_ID = MappingProxyType({item.factor_id: item for item in _SEEDED_DEFINITIONS})


def list_factor_definitions() -> tuple[FactorDefinition, ...]:
    """Return the deterministic built-in factor seed."""
    return tuple(_SEEDED_DEFINITIONS)


def list_factor_families() -> tuple[str, ...]:
    """Return supported factor families in deterministic order."""
    return tuple(item.family for item in _SEEDED_DEFINITIONS)


def get_factor_definition(factor_id: str | None) -> FactorDefinition | None:
    """Look up a factor definition using normalized ids."""
    try:
        normalized = normalize_factor_id(factor_id)
    except ValueError:
        return None
    return _DEFINITIONS_BY_ID.get(normalized)


__all__ = [
    "get_factor_definition",
    "list_factor_definitions",
    "list_factor_families",
]
