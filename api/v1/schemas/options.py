# -*- coding: utf-8 -*-
"""Safe normalized schemas for Options Lab Phase 1."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _OptionsModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class OptionChainLimitations(_OptionsModel):
    options_are_high_risk: bool = Field(default=True, alias="optionsAreHighRisk")
    long_options_can_lose_100_percent_premium: bool = Field(
        default=True,
        alias="longOptionsCanLose100PercentPremium",
    )
    data_may_be_delayed_or_stale: bool = Field(default=True, alias="dataMayBeDelayedOrStale")
    analytical_only_not_investment_advice: bool = Field(
        default=True,
        alias="analyticalOnlyNotInvestmentAdvice",
    )
    no_order_placement: bool = Field(default=True, alias="noOrderPlacement")
    no_broker_execution: bool = Field(default=True, alias="noBrokerExecution")


class OptionsMetadata(_OptionsModel):
    read_only: bool = Field(default=True, alias="readOnly")
    fixture_backed: bool = Field(default=True, alias="fixtureBacked")
    synthetic_data: bool = Field(default=True, alias="syntheticData")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    no_llm_calls: bool = Field(default=True, alias="noLlmCalls")
    no_order_placement: bool = Field(default=True, alias="noOrderPlacement")
    no_broker_connection: bool = Field(default=True, alias="noBrokerConnection")
    no_portfolio_mutation: bool = Field(default=True, alias="noPortfolioMutation")
    no_trading_recommendation: bool = Field(default=True, alias="noTradingRecommendation")
    scoring_engine: str = Field(default="not_implemented_until_scoring_phase", alias="scoringEngine")
    strategy_engine: str = Field(default="not_implemented_until_later_phase", alias="strategyEngine")
    force_refresh_ignored: bool = Field(default=False, alias="forceRefreshIgnored")


class OptionExpirationItem(_OptionsModel):
    date: str
    dte: int
    type: Literal["weekly", "monthly", "quarterly", "unknown"] = "unknown"
    chain_available: bool = Field(default=True, alias="chainAvailable")
    as_of: str = Field(alias="asOf")
    source: str = "synthetic_fixture"
    warnings: List[str] = Field(default_factory=list)


class OptionGreeks(_OptionsModel):
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None


class OptionContract(_OptionsModel):
    symbol: str
    contract_symbol: str = Field(alias="contractSymbol")
    side: Literal["call", "put"]
    expiration: str
    strike: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    mid: Optional[float] = None
    last: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = Field(default=None, alias="openInterest")
    implied_volatility: Optional[float] = Field(default=None, alias="impliedVolatility")
    greeks: Optional[OptionGreeks] = None
    dte: int
    moneyness: Literal["itm", "atm", "otm", "unknown"] = "unknown"
    spread_pct: Optional[float] = Field(default=None, alias="spreadPct")
    liquidity_bucket: Literal["tight", "moderate", "thin", "unknown"] = Field(
        default="unknown",
        alias="liquidityBucket",
    )
    as_of: str = Field(alias="asOf")
    source: str
    warnings: List[str] = Field(default_factory=list)


class OptionUnderlyingSummaryResponse(_OptionsModel):
    symbol: str
    market: str
    currency: str = "USD"
    underlying: Dict[str, Any]
    options_availability: Dict[str, Any] = Field(alias="optionsAvailability")
    as_of: str = Field(alias="asOf")
    source: str
    warnings: List[str] = Field(default_factory=list)
    limitations: OptionChainLimitations = Field(default_factory=OptionChainLimitations)
    metadata: OptionsMetadata = Field(default_factory=OptionsMetadata)


class OptionExpirationsResponse(_OptionsModel):
    symbol: str
    market: str
    expirations: List[OptionExpirationItem] = Field(default_factory=list)
    as_of: str = Field(alias="asOf")
    source: str
    warnings: List[str] = Field(default_factory=list)
    limitations: OptionChainLimitations = Field(default_factory=OptionChainLimitations)
    metadata: OptionsMetadata = Field(default_factory=OptionsMetadata)


class OptionChainResponse(_OptionsModel):
    symbol: str
    market: str
    underlying: Dict[str, Any]
    expiration: Optional[str] = None
    calls: List[OptionContract] = Field(default_factory=list)
    puts: List[OptionContract] = Field(default_factory=list)
    filters_applied: Dict[str, Any] = Field(default_factory=dict, alias="filtersApplied")
    chain_as_of: str = Field(alias="chainAsOf")
    source: str
    warnings: List[str] = Field(default_factory=list)
    limitations: OptionChainLimitations = Field(default_factory=OptionChainLimitations)
    metadata: OptionsMetadata = Field(default_factory=OptionsMetadata)


OptionDirection = Literal["bullish", "bearish", "neutral", "volatility"]
OptionRiskProfile = Literal["conservative", "balanced", "aggressive"]
OptionStrategy = Literal["long_call", "long_put", "bull_call_spread", "bear_put_spread"]
OptionsDataQualityTier = Literal["live_usable", "delayed_usable", "synthetic_demo_only", "insufficient"]
OptionsDecisionLabel = Literal["数据不足，禁止判断", "不建议", "仅观察", "有条件可交易", "高风险，仅小仓验证"]
OptionsOptimizerLabel = Literal["数据不足，禁止判断", "不建议交易", "仅观察", "可关注替代结构", "有条件可交易"]
OptionsIvRankStatus = Literal["unavailable", "available"]
OptionsExpectedMoveSource = Literal["straddle_mid", "iv_dte", "unavailable"]


class OptionsAnalyzeRequest(_OptionsModel):
    symbol: str
    direction: OptionDirection
    target_price: float = Field(alias="targetPrice", gt=0)
    target_date: str = Field(alias="targetDate")
    max_premium: Optional[float] = Field(default=None, alias="maxPremium", ge=0)
    risk_profile: OptionRiskProfile = Field(default="balanced", alias="riskProfile")
    strategies: List[OptionStrategy] = Field(default_factory=lambda: ["long_call", "long_put"])
    force_refresh: bool = Field(default=False, alias="forceRefresh")


class OptionScoringSubScores(_OptionsModel):
    directional_fit: float = Field(alias="directionalFit")
    delta_fit: float = Field(alias="deltaFit")
    breakeven_difficulty: float = Field(alias="breakevenDifficulty")
    premium_efficiency: float = Field(alias="premiumEfficiency")
    liquidity_score: float = Field(alias="liquidityScore")
    spread_penalty: float = Field(alias="spreadPenalty")
    iv_risk: float = Field(alias="ivRisk")
    theta_risk: float = Field(alias="thetaRisk")
    dte_fit: float = Field(alias="dteFit")
    target_scenario_payoff: float = Field(alias="targetScenarioPayoff")
    max_loss_budget_fit: float = Field(alias="maxLossBudgetFit")
    oi_volume_confidence: float = Field(alias="oiVolumeConfidence")
    data_freshness_confidence: float = Field(alias="dataFreshnessConfidence")


class OptionContractScoring(_OptionsModel):
    sub_scores: OptionScoringSubScores = Field(alias="subScores")
    grade_label: str = Field(alias="gradeLabel")
    top_positive_drivers: List[str] = Field(default_factory=list, alias="topPositiveDrivers")
    top_risk_drivers: List[str] = Field(default_factory=list, alias="topRiskDrivers")
    assumptions_used: Dict[str, Any] = Field(default_factory=dict, alias="assumptionsUsed")
    data_confidence: str = Field(alias="dataConfidence")
    not_advice_disclosure: str = Field(alias="notAdviceDisclosure")


class OptionCandidateContract(_OptionsModel):
    strategy: Literal["long_call", "long_put"]
    contract: OptionContract
    score: float
    grade_label: str = Field(alias="gradeLabel")
    premium_at_risk: float = Field(alias="premiumAtRisk")
    breakeven: float
    required_move_pct: float = Field(alias="requiredMovePct")
    target_payoff: float = Field(alias="targetPayoff")
    scoring: OptionContractScoring


class OptionsAnalyzeResponse(_OptionsModel):
    symbol: str
    underlying: Dict[str, Any]
    assumptions: Dict[str, Any]
    option_chain_summary: Dict[str, Any] = Field(alias="optionChainSummary")
    candidate_contracts: List[OptionCandidateContract] = Field(default_factory=list, alias="candidateContracts")
    risks: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    metadata: OptionsMetadata = Field(default_factory=OptionsMetadata)


class OptionsScenarioRequest(_OptionsModel):
    symbol: str
    strategy: Literal["long_call", "long_put"]
    contract_symbol: Optional[str] = Field(default=None, alias="contractSymbol")
    expiration: Optional[str] = None
    strike: Optional[float] = Field(default=None, gt=0)
    target_price: Optional[float] = Field(default=None, alias="targetPrice", gt=0)
    custom_prices: List[float] = Field(default_factory=list, alias="customPrices")
    force_refresh: bool = Field(default=False, alias="forceRefresh")


class OptionScenarioPayoffRow(_OptionsModel):
    label: str
    underlying_price: float = Field(alias="underlyingPrice")
    gross_payoff: float = Field(alias="grossPayoff")
    net_payoff: float = Field(alias="netPayoff")
    return_on_premium_pct: Optional[float] = Field(default=None, alias="returnOnPremiumPct")


class OptionScenarioRisk(_OptionsModel):
    premium_at_risk: float = Field(alias="premiumAtRisk")
    breakeven: float
    required_move_pct: float = Field(alias="requiredMovePct")
    max_loss: float = Field(alias="maxLoss")


class OptionsScenarioResponse(_OptionsModel):
    symbol: str
    underlying: Dict[str, Any]
    strategy: Literal["long_call", "long_put"]
    contract: OptionContract
    expiration_payoff_grid: List[OptionScenarioPayoffRow] = Field(alias="expirationPayoffGrid")
    risk: OptionScenarioRisk
    pre_expiration_theoretical_pricing: Dict[str, Any] = Field(alias="preExpirationTheoreticalPricing")
    limitations: List[str] = Field(default_factory=list)
    metadata: OptionsMetadata = Field(default_factory=OptionsMetadata)


class OptionsStrategyCompareRequest(_OptionsModel):
    symbol: str
    direction: OptionDirection
    target_price: float = Field(alias="targetPrice", gt=0)
    target_date: str = Field(alias="targetDate")
    max_premium: Optional[float] = Field(default=None, alias="maxPremium", ge=0)
    risk_profile: OptionRiskProfile = Field(default="balanced", alias="riskProfile")
    strategies: List[str] = Field(
        default_factory=lambda: ["long_call", "long_put", "bull_call_spread", "bear_put_spread"]
    )
    force_refresh: bool = Field(default=False, alias="forceRefresh")


class OptionsStrategyLeg(_OptionsModel):
    action: Literal["buy", "sell"]
    side: Literal["call", "put"]
    contract_symbol: str = Field(alias="contractSymbol")
    expiration: str
    strike: float
    mid: float
    quantity: int = 1


class OptionsStrategyComparison(_OptionsModel):
    strategy_type: OptionStrategy = Field(alias="strategyType")
    legs: List[OptionsStrategyLeg]
    net_debit: float = Field(alias="netDebit")
    max_loss: float = Field(alias="maxLoss")
    max_gain: Optional[float] = Field(default=None, alias="maxGain")
    breakeven: float
    required_move_pct: float = Field(alias="requiredMovePct")
    payoff_at_target: float = Field(alias="payoffAtTarget")
    risk_reward_ratio: Optional[float] = Field(default=None, alias="riskRewardRatio")
    liquidity_warnings: List[str] = Field(default_factory=list, alias="liquidityWarnings")
    iv_theta_notes: List[str] = Field(default_factory=list, alias="ivThetaNotes")
    suitability_notes: List[str] = Field(default_factory=list, alias="suitabilityNotes")
    limitations: List[str] = Field(default_factory=list)
    no_advice_disclosure: str = Field(alias="noAdviceDisclosure")


class OptionsStrategyCompareResponse(_OptionsModel):
    symbol: str
    underlying: Dict[str, Any]
    assumptions: Dict[str, Any]
    strategies: List[OptionsStrategyComparison] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    metadata: OptionsMetadata = Field(default_factory=OptionsMetadata)


class OptionsDecisionLeg(_OptionsModel):
    action: Literal["buy", "sell"] = "buy"
    side: Literal["call", "put"]
    contract_symbol: Optional[str] = Field(default=None, alias="contractSymbol")
    expiration: Optional[str] = None
    strike: Optional[float] = Field(default=None, gt=0)
    quantity: int = Field(default=1, ge=1)


class OptionsDecisionRequest(_OptionsModel):
    symbol: str
    strategy: OptionStrategy
    expiration: Optional[str] = None
    legs: List[OptionsDecisionLeg] = Field(default_factory=list)
    target_price: Optional[float] = Field(default=None, alias="targetPrice", gt=0)
    target_date: Optional[str] = Field(default=None, alias="targetDate")
    holding_horizon_days: Optional[int] = Field(default=None, alias="holdingHorizonDays", ge=1)
    risk_budget: Optional[float] = Field(default=None, alias="riskBudget", ge=0)
    scenario_assumptions: Dict[str, Any] = Field(default_factory=dict, alias="scenarioAssumptions")
    force_refresh: bool = Field(default=False, alias="forceRefresh")


class OptionsDecisionDataQuality(_OptionsModel):
    data_quality_score: float = Field(alias="dataQualityScore")
    data_quality_tier: OptionsDataQualityTier = Field(alias="dataQualityTier")
    source_type: str = Field(alias="sourceType")
    as_of_age_minutes: Optional[float] = Field(default=None, alias="asOfAgeMinutes")
    blocking_reasons: List[str] = Field(default_factory=list, alias="blockingReasons")
    warnings: List[str] = Field(default_factory=list)


class OptionsDecisionLiquidity(_OptionsModel):
    liquidity_score: float = Field(alias="liquidityScore")
    spread_pct: Optional[float] = Field(default=None, alias="spreadPct")
    liquidity_warnings: List[str] = Field(default_factory=list, alias="liquidityWarnings")


class OptionsDecisionIvGreeks(_OptionsModel):
    iv_readiness: float = Field(alias="ivReadiness")
    iv_rank_status: OptionsIvRankStatus = Field(alias="ivRankStatus")
    iv_rank: Optional[float] = Field(default=None, alias="ivRank")
    iv_percentile: Optional[float] = Field(default=None, alias="ivPercentile")
    iv_rank_source: Optional[str] = Field(default=None, alias="ivRankSource")
    iv_rank_confidence: Optional[str] = Field(default=None, alias="ivRankConfidence")
    warnings: List[str] = Field(default_factory=list)
    dte_bucket: str = Field(default="unknown", alias="dteBucket")


class OptionsDecisionBreakeven(_OptionsModel):
    breakeven: Optional[float] = None
    required_move_pct: Optional[float] = Field(default=None, alias="requiredMovePct")
    target_price_status: str = Field(default="not_supplied", alias="targetPriceStatus")
    score: float


class OptionsDecisionRiskReward(_OptionsModel):
    max_loss: Optional[float] = Field(default=None, alias="maxLoss")
    max_gain: Optional[float] = Field(default=None, alias="maxGain")
    risk_reward_ratio: Optional[float] = Field(default=None, alias="riskRewardRatio")
    score: float
    warnings: List[str] = Field(default_factory=list)


class OptionsDecisionAlternative(_OptionsModel):
    strategy_type: OptionStrategy = Field(alias="strategyType")
    reason: str
    max_loss: Optional[float] = Field(default=None, alias="maxLoss")
    risk_reward_ratio: Optional[float] = Field(default=None, alias="riskRewardRatio")


class OptionsDecisionFreshness(_OptionsModel):
    source: str
    freshness: str
    as_of: Optional[str] = Field(default=None, alias="asOf")


class OptionsExpectedMove(_OptionsModel):
    expected_move_abs: Optional[float] = Field(default=None, alias="expectedMoveAbs")
    expected_move_pct: Optional[float] = Field(default=None, alias="expectedMovePct")
    expected_move_source: OptionsExpectedMoveSource = Field(alias="expectedMoveSource")
    expected_move_warnings: List[str] = Field(default_factory=list, alias="expectedMoveWarnings")


class OptionsOptimizerAlternative(_OptionsModel):
    strategy_key: OptionStrategy = Field(alias="strategyKey")
    data_quality_tier: OptionsDataQualityTier = Field(alias="dataQualityTier")
    liquidity_score: float = Field(alias="liquidityScore")
    breakeven_pressure: Optional[float] = Field(default=None, alias="breakevenPressure")
    max_loss: Optional[float] = Field(default=None, alias="maxLoss")
    max_gain: Optional[float] = Field(default=None, alias="maxGain")
    risk_reward_ratio: Optional[float] = Field(default=None, alias="riskRewardRatio")
    expected_move_alignment: float = Field(alias="expectedMoveAlignment")
    iv_readiness: float = Field(alias="ivReadiness")
    trade_quality_score: float = Field(alias="tradeQualityScore")
    decision_label: OptionsDecisionLabel = Field(alias="decisionLabel")
    primary_reasons: List[str] = Field(default_factory=list, alias="primaryReasons")
    risk_warnings: List[str] = Field(default_factory=list, alias="riskWarnings")


class OptionsDecisionOptimizer(_OptionsModel):
    preferred_strategy_key: Optional[OptionStrategy] = Field(default=None, alias="preferredStrategyKey")
    optimizer_label: OptionsOptimizerLabel = Field(alias="optimizerLabel")
    alternatives: List[OptionsOptimizerAlternative] = Field(default_factory=list)
    no_trade_reason: Optional[str] = Field(default=None, alias="noTradeReason")


class OptionsDecisionResponse(_OptionsModel):
    symbol: str
    strategy: OptionStrategy
    data_quality: OptionsDecisionDataQuality = Field(alias="dataQuality")
    liquidity: OptionsDecisionLiquidity
    iv_greeks: OptionsDecisionIvGreeks = Field(alias="ivGreeks")
    iv_rank: Optional[float] = Field(default=None, alias="ivRank")
    iv_percentile: Optional[float] = Field(default=None, alias="ivPercentile")
    iv_rank_status: OptionsIvRankStatus = Field(alias="ivRankStatus")
    expected_move: OptionsExpectedMove = Field(alias="expectedMove")
    optimizer: OptionsDecisionOptimizer
    ranked_alternatives: List[OptionsOptimizerAlternative] = Field(default_factory=list, alias="rankedAlternatives")
    breakeven: OptionsDecisionBreakeven
    risk_reward: OptionsDecisionRiskReward = Field(alias="riskReward")
    trade_quality_score: float = Field(alias="tradeQualityScore")
    decision_label: OptionsDecisionLabel = Field(alias="decisionLabel")
    primary_reasons: List[str] = Field(default_factory=list, alias="primaryReasons")
    risk_warnings: List[str] = Field(default_factory=list, alias="riskWarnings")
    better_alternative: Optional[OptionsDecisionAlternative] = Field(default=None, alias="betterAlternative")
    no_advice_disclosure: str = Field(alias="noAdviceDisclosure")
    freshness: OptionsDecisionFreshness
    metadata: OptionsMetadata = Field(default_factory=OptionsMetadata)
