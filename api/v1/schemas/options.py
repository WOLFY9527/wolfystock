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
