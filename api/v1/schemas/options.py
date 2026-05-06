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
