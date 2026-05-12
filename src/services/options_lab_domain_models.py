# -*- coding: utf-8 -*-
"""Internal Options Lab decision assessment models.

These dataclasses intentionally cover only the evaluate_decision intermediate
assessment layer. Public API DTOs remain defined in api.v1.schemas.options.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DecisionDataQualityAssessment:
    data_quality_score: float
    data_quality_tier: str
    source_type: str
    as_of_age_minutes: Optional[float] = None
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class LiquidityAssessment:
    liquidity_score: float
    spread_pct: Optional[float] = None
    liquidity_warnings: list[str] = field(default_factory=list)


@dataclass
class IvGreeksAssessment:
    iv_readiness: float
    iv_rank_status: str
    iv_rank: Optional[float] = None
    iv_percentile: Optional[float] = None
    iv_rank_source: Optional[str] = None
    iv_rank_confidence: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    dte_bucket: str = "unknown"


@dataclass
class BreakevenAssessment:
    breakeven: Optional[float]
    required_move_pct: Optional[float]
    target_price_status: str
    score: float


@dataclass
class RiskRewardAssessment:
    max_loss: Optional[float]
    max_gain: Optional[float]
    risk_reward_ratio: Optional[float]
    score: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExpectedMoveEstimate:
    expected_move_abs: Optional[float]
    expected_move_pct: Optional[float]
    expected_move_source: str
    expected_move_warnings: list[str] = field(default_factory=list)


@dataclass
class OptimizerCandidate:
    strategy_key: str
    data_quality_tier: str
    liquidity_score: float
    breakeven_pressure: Optional[float]
    max_loss: Optional[float]
    max_gain: Optional[float]
    risk_reward_ratio: Optional[float]
    expected_move_alignment: float
    iv_readiness: float
    trade_quality_score: float
    decision_label: str
    primary_reasons: list[str] = field(default_factory=list)
    risk_warnings: list[str] = field(default_factory=list)


@dataclass
class OptimizerResult:
    preferred_strategy_key: Optional[str]
    optimizer_label: str
    alternatives: list[OptimizerCandidate] = field(default_factory=list)
    no_trade_reason: Optional[str] = None


@dataclass
class DecisionAlternativeModel:
    strategy_type: str
    reason: str
    max_loss: Optional[float]
    risk_reward_ratio: Optional[float]
