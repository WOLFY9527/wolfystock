# -*- coding: utf-8 -*-
"""Internal Options Lab decision assessment models.

These dataclasses intentionally cover only the evaluate_decision intermediate
assessment layer. Public API DTOs remain defined in api.v1.schemas.options.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class OptionGreeksSnapshot:
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None


@dataclass
class OptionContractSnapshot:
    symbol: str
    contract_symbol: str
    side: str
    expiration: str
    strike: float
    multiplier: int = 100
    bid: Optional[float] = None
    ask: Optional[float] = None
    mid: Optional[float] = None
    last: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    implied_volatility: Optional[float] = None
    greeks: Optional[OptionGreeksSnapshot] = None
    dte: int = 0
    moneyness: str = "unknown"
    spread_pct: Optional[float] = None
    liquidity_bucket: str = "unknown"
    as_of: str = ""
    source: str = ""
    freshness: str = "unknown"
    provider_quality: Optional[str] = None
    data_quality: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class OptionUnderlyingSummaryResultModel:
    symbol: str
    market: str
    currency: str = "USD"
    underlying: dict[str, Any] = field(default_factory=dict)
    options_availability: dict[str, Any] = field(default_factory=dict)
    as_of: str = ""
    source: str = ""
    warnings: list[str] = field(default_factory=list)
    metadata: Any = None


@dataclass
class OptionExpirationModel:
    date: str
    dte: int
    type: str = "unknown"
    chain_available: bool = True
    as_of: str = ""
    source: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class OptionExpirationsResultModel:
    symbol: str
    market: str
    expirations: list[OptionExpirationModel] = field(default_factory=list)
    as_of: str = ""
    source: str = ""
    warnings: list[str] = field(default_factory=list)
    metadata: Any = None


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


@dataclass
class DecisionFreshnessModel:
    source: str
    freshness: str
    as_of: Optional[str] = None


@dataclass
class DecisionEvaluationResult:
    symbol: str
    strategy: str
    data_quality: DecisionDataQualityAssessment
    liquidity: LiquidityAssessment
    iv_greeks: IvGreeksAssessment
    expected_move: ExpectedMoveEstimate
    optimizer: OptimizerResult
    breakeven: BreakevenAssessment
    risk_reward: RiskRewardAssessment
    trade_quality_score: float
    decision_label: str
    primary_reasons: list[str] = field(default_factory=list)
    risk_warnings: list[str] = field(default_factory=list)
    data_quality_gates: Optional[dict[str, Any]] = None
    liquidity_gates: Optional[dict[str, Any]] = None
    gate_decision: Optional[str] = None
    gate_issues: list[dict[str, Any]] = field(default_factory=list)
    decision_grade: Optional[bool] = None
    fail_closed_reason_codes: list[str] = field(default_factory=list)
    better_alternative: Optional[DecisionAlternativeModel] = None
    no_advice_disclosure: str = ""
    freshness: Optional[DecisionFreshnessModel] = None
    metadata: Any = None

    @property
    def iv_rank(self) -> Optional[float]:
        return self.iv_greeks.iv_rank

    @property
    def iv_percentile(self) -> Optional[float]:
        return self.iv_greeks.iv_percentile

    @property
    def iv_rank_status(self) -> str:
        return self.iv_greeks.iv_rank_status

    @property
    def ranked_alternatives(self) -> list[OptimizerCandidate]:
        return self.optimizer.alternatives


@dataclass
class AnalyzeSubScoresModel:
    directional_fit: float
    delta_fit: float
    breakeven_difficulty: float
    premium_efficiency: float
    liquidity_score: float
    spread_penalty: float
    iv_risk: float
    theta_risk: float
    dte_fit: float
    target_scenario_payoff: float
    max_loss_budget_fit: float
    oi_volume_confidence: float
    data_freshness_confidence: float


@dataclass
class AnalyzeCandidateModel:
    strategy: str
    contract: Any
    score: float
    grade_label: str
    premium_at_risk: float
    breakeven: float
    required_move_pct: float
    target_payoff: float
    sub_scores: AnalyzeSubScoresModel
    top_positive_drivers: list[str] = field(default_factory=list)
    top_risk_drivers: list[str] = field(default_factory=list)
    assumptions_used: dict[str, Any] = field(default_factory=dict)
    data_confidence: str = "low"
    not_advice_disclosure: str = ""


@dataclass
class AnalyzeResultModel:
    symbol: str
    underlying: dict[str, Any]
    assumptions: dict[str, Any]
    option_chain_summary: dict[str, Any]
    candidate_contracts: list[AnalyzeCandidateModel] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    metadata: Any = None


@dataclass
class ScenarioPayoffRowModel:
    label: str
    underlying_price: float
    gross_payoff: float
    net_payoff: float
    return_on_premium_pct: Optional[float] = None


@dataclass
class ScenarioRiskModel:
    premium_at_risk: float
    breakeven: float
    required_move_pct: float
    max_loss: float


@dataclass
class ScenarioResultModel:
    symbol: str
    underlying: dict[str, Any]
    strategy: str
    contract: Any
    expiration_payoff_grid: list[ScenarioPayoffRowModel] = field(default_factory=list)
    risk: ScenarioRiskModel | None = None
    pre_expiration_theoretical_pricing: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    metadata: Any = None


@dataclass
class StrategyLegModel:
    action: str
    side: str
    contract_symbol: str
    expiration: str
    strike: float
    mid: float
    quantity: int = 1


@dataclass
class StrategyComparisonModel:
    strategy_type: str
    legs: list[StrategyLegModel] = field(default_factory=list)
    net_debit: float = 0.0
    max_loss: float = 0.0
    max_gain: Optional[float] = None
    breakeven: float = 0.0
    required_move_pct: float = 0.0
    payoff_at_target: float = 0.0
    risk_reward_ratio: Optional[float] = None
    liquidity_warnings: list[str] = field(default_factory=list)
    iv_theta_notes: list[str] = field(default_factory=list)
    suitability_notes: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    no_advice_disclosure: str = ""


@dataclass
class StrategyCompareResultModel:
    symbol: str
    underlying: dict[str, Any]
    assumptions: dict[str, Any]
    strategies: list[StrategyComparisonModel] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    metadata: Any = None
