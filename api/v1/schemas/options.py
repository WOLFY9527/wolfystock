# -*- coding: utf-8 -*-
"""Safe normalized schemas for Options Lab Phase 1."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    provider_name: str = Field(default="synthetic_fixture", alias="providerName")
    provider_capabilities: Dict[str, Any] = Field(default_factory=dict, alias="providerCapabilities")
    live_provider_enabled: bool = Field(default=False, alias="liveProviderEnabled")


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
    multiplier: int = 100
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
    freshness: str = "unknown"
    provider_quality: Optional[str] = Field(default=None, alias="providerQuality")
    data_quality: Dict[str, Any] = Field(default_factory=dict, alias="dataQuality")
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
    options_readiness: Optional[OptionsResearchReadiness] = Field(default=None, alias="optionsReadiness")
    options_research_readiness: Optional[OptionsResearchReadiness] = Field(
        default=None,
        alias="optionsResearchReadiness",
    )

    @model_validator(mode="after")
    def _populate_options_readiness(self) -> "OptionUnderlyingSummaryResponse":
        computed = _build_contract_response_readiness(
            metadata=self.metadata,
            contracts=[],
            scenario_coverage="missing_chain_data",
            source_hint=self.source,
            freshness_hint=str(self.underlying.get("freshness") or ""),
        )
        self.options_readiness, self.options_research_readiness = _ensure_readiness_aliases(
            existing_readiness=self.options_readiness,
            existing_alias=self.options_research_readiness,
            computed=computed,
        )
        return self


class OptionExpirationsResponse(_OptionsModel):
    symbol: str
    market: str
    expirations: List[OptionExpirationItem] = Field(default_factory=list)
    as_of: str = Field(alias="asOf")
    source: str
    warnings: List[str] = Field(default_factory=list)
    limitations: OptionChainLimitations = Field(default_factory=OptionChainLimitations)
    metadata: OptionsMetadata = Field(default_factory=OptionsMetadata)
    options_readiness: Optional[OptionsResearchReadiness] = Field(default=None, alias="optionsReadiness")
    options_research_readiness: Optional[OptionsResearchReadiness] = Field(
        default=None,
        alias="optionsResearchReadiness",
    )

    @model_validator(mode="after")
    def _populate_options_readiness(self) -> "OptionExpirationsResponse":
        computed = _build_contract_response_readiness(
            metadata=self.metadata,
            contracts=[],
            scenario_coverage="missing_chain_data",
            source_hint=self.source,
            freshness_hint="",
        )
        self.options_readiness, self.options_research_readiness = _ensure_readiness_aliases(
            existing_readiness=self.options_readiness,
            existing_alias=self.options_research_readiness,
            computed=computed,
        )
        return self


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
    options_readiness: Optional[OptionsResearchReadiness] = Field(default=None, alias="optionsReadiness")
    options_research_readiness: Optional[OptionsResearchReadiness] = Field(
        default=None,
        alias="optionsResearchReadiness",
    )

    @model_validator(mode="after")
    def _populate_options_readiness(self) -> "OptionChainResponse":
        contracts = [*self.calls, *self.puts]
        computed = _build_contract_response_readiness(
            metadata=self.metadata,
            contracts=contracts,
            scenario_coverage="single_contract",
            source_hint=self.source,
            freshness_hint=str(self.underlying.get("freshness") or ""),
        )
        self.options_readiness, self.options_research_readiness = _ensure_readiness_aliases(
            existing_readiness=self.options_readiness,
            existing_alias=self.options_research_readiness,
            computed=computed,
        )
        return self


OptionDirection = Literal["bullish", "bearish", "neutral", "volatility"]
OptionRiskProfile = Literal["conservative", "balanced", "aggressive"]
OptionStrategy = Literal["long_call", "long_put", "bull_call_spread", "bear_put_spread"]
OptionsDataQualityTier = Literal["live_usable", "delayed_usable", "synthetic_demo_only", "insufficient"]
OptionsDecisionLabel = Literal["数据不足，禁止判断", "不建议", "仅观察", "有条件可交易", "高风险，仅小仓验证"]
OptionsOptimizerLabel = Literal["数据不足，禁止判断", "不建议交易", "仅观察", "可关注替代结构", "有条件可交易"]
OptionsGateStatus = Literal["clear", "blocked", "observe_only", "manual_review"]
OptionsGateDecision = Literal["数据不足，禁止判断", "仅观察", "需人工复核"]
OptionsIvRankStatus = Literal["unavailable", "available"]
OptionsExpectedMoveSource = Literal["straddle_mid", "iv_dte", "unavailable"]
OptionsReadinessState = Literal["live_usable", "delayed_usable", "insufficient", "blocked"]
OptionsProviderAuthority = Literal["scoreGradeAllowed", "observationOnly", "unavailable"]
OptionsScenarioCoverage = Literal["missing_chain_data", "single_contract", "strategy_compare_ready"]

_READY_FRESHNESS_VALUES = {"fresh", "live", "realtime", "real_time", "real-time"}
_DELAYED_FRESHNESS_VALUES = {"delayed", "cached", "stale", "delayed_usable"}
_FIXTURE_SOURCE_MARKERS = ("fixture", "synthetic", "mock")
_PROVIDER_BLOCKING_CODES = {
    "provider_adapter_contract_not_decision_grade",
    "provider_dry_run_not_decision_grade",
    "provider_fixture_not_decision_grade",
    "provider_synthetic_not_decision_grade",
    "provider_live_disabled",
    "provider_tradeable_data_false",
    "provider_authority_tier_missing",
    "provider_authority_tier_observation_only",
    "provider_authority_tier_analysis_only",
    "provider_authority_policy_not_granted",
}


class OptionsNoTradingBoundary(_OptionsModel):
    analytical_only: bool = Field(default=True, alias="analyticalOnly")
    no_broker_execution: bool = Field(default=True, alias="noBrokerExecution")
    no_order_placement: bool = Field(default=True, alias="noOrderPlacement")
    no_portfolio_mutation: bool = Field(default=True, alias="noPortfolioMutation")
    no_trading_recommendation: bool = Field(default=True, alias="noTradingRecommendation")


class OptionsResearchReadiness(_OptionsModel):
    options_research_ready: bool = Field(alias="optionsResearchReady")
    readiness_state: OptionsReadinessState = Field(alias="readinessState")
    data_quality_tier: OptionsDataQualityTier = Field(alias="dataQualityTier")
    decision_grade: bool = Field(alias="decisionGrade")
    provider_authority: OptionsProviderAuthority = Field(alias="providerAuthority")
    liquidity_gate: OptionsGateStatus = Field(alias="liquidityGate")
    iv_greeks_gate: OptionsGateStatus = Field(alias="ivGreeksGate")
    spread_gate: OptionsGateStatus = Field(alias="spreadGate")
    scenario_coverage: OptionsScenarioCoverage = Field(alias="scenarioCoverage")
    no_trading_boundary: OptionsNoTradingBoundary = Field(alias="noTradingBoundary")
    blocking_reasons: List[str] = Field(default_factory=list, alias="blockingReasons")
    next_evidence_needed: List[str] = Field(default_factory=list, alias="nextEvidenceNeeded")


def _dedupe_codes(values: List[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _source_text(*values: Any) -> str:
    return " ".join(str(value or "") for value in values).lower()


def _provider_caps(metadata: Optional["OptionsMetadata"]) -> Dict[str, Any]:
    if metadata is None:
        return {}
    return dict(metadata.provider_capabilities or {})


def _provider_authority_from_metadata(
    metadata: Optional["OptionsMetadata"],
    source_hint: str = "",
) -> OptionsProviderAuthority:
    caps = _provider_caps(metadata)
    tier = str(caps.get("authorityTier") or "").strip().lower()
    source_type = _source_text(caps.get("sourceType"), source_hint)
    live_enabled = bool(caps.get("liveEnabled", metadata.live_provider_enabled if metadata else False))
    tradeable = caps.get("tradeableData")
    if tier == "decision_grade" and live_enabled and tradeable is True:
        return "scoreGradeAllowed"
    if (
        (metadata is not None and (metadata.fixture_backed or metadata.synthetic_data))
        or tier in {"live_observation_only", "live_analysis_grade"}
        or any(marker in source_type for marker in ("fixture", "synthetic", "adapter_contract", "dry_run", "fallback"))
    ):
        return "observationOnly"
    return "unavailable"


def _provider_blocking_reasons(
    metadata: Optional["OptionsMetadata"],
    source_hint: str = "",
) -> List[str]:
    caps = _provider_caps(metadata)
    issues: List[str] = []
    tier = str(caps.get("authorityTier") or "").strip().lower()
    source_type = _source_text(caps.get("sourceType"), source_hint)
    live_enabled = bool(caps.get("liveEnabled", metadata.live_provider_enabled if metadata else False))
    tradeable = caps.get("tradeableData")
    if "adapter_contract" in source_type:
        issues.append("provider_adapter_contract_not_decision_grade")
    elif "dry_run" in source_type:
        issues.append("provider_dry_run_not_decision_grade")
    elif metadata is not None and metadata.fixture_backed:
        issues.append("provider_fixture_not_decision_grade")
    elif metadata is not None and metadata.synthetic_data:
        issues.append("provider_synthetic_not_decision_grade")
    if not live_enabled:
        issues.append("provider_live_disabled")
    if tradeable is not True:
        issues.append("provider_tradeable_data_false")
    if tier == "live_observation_only" or ((metadata is not None and metadata.fixture_backed) and not tier):
        issues.append("provider_authority_tier_observation_only")
    elif tier == "live_analysis_grade":
        issues.append("provider_authority_tier_analysis_only")
    elif not tier:
        issues.append("provider_authority_tier_missing")
    elif tier != "decision_grade":
        issues.append("provider_authority_policy_not_granted")
    return _dedupe_codes(issues)


def _infer_data_quality_tier(
    *,
    explicit_tier: Optional[str] = None,
    metadata: Optional["OptionsMetadata"] = None,
    source_hint: str = "",
    freshness_hint: str = "",
) -> OptionsDataQualityTier:
    if explicit_tier in {"live_usable", "delayed_usable", "synthetic_demo_only", "insufficient"}:
        return explicit_tier
    text = _source_text(source_hint, freshness_hint, getattr(metadata, "provider_name", ""))
    if metadata is not None and (metadata.fixture_backed or metadata.synthetic_data):
        return "synthetic_demo_only"
    if any(marker in text for marker in _FIXTURE_SOURCE_MARKERS):
        return "synthetic_demo_only"
    if any(marker in text for marker in _READY_FRESHNESS_VALUES):
        return "live_usable"
    if any(marker in text for marker in _DELAYED_FRESHNESS_VALUES):
        return "delayed_usable"
    return "insufficient"


def _status_from_value(value: Any, fallback: OptionsGateStatus = "clear") -> OptionsGateStatus:
    text = str(value or "").strip().lower()
    if text in {"clear", "blocked", "observe_only", "manual_review"}:
        return text
    return fallback


def _liquidity_gate_from_contracts(contracts: List["OptionContract"]) -> OptionsGateStatus:
    if not contracts:
        return "blocked"
    if any(contract.bid is None or contract.ask is None or contract.mid in {None, 0} for contract in contracts):
        return "blocked"
    if any(contract.spread_pct is not None and float(contract.spread_pct) > 25 for contract in contracts):
        return "blocked"
    if any(contract.spread_pct is None for contract in contracts):
        return "manual_review"
    if any(
        (contract.volume is None or int(contract.volume) < 50)
        or (contract.open_interest is None or int(contract.open_interest) < 100)
        for contract in contracts
    ):
        return "manual_review"
    return "clear"


def _iv_greeks_gate_from_contracts(contracts: List["OptionContract"]) -> OptionsGateStatus:
    if not contracts:
        return "blocked"
    if any(contract.implied_volatility is None or contract.greeks is None for contract in contracts):
        return "blocked"
    return "clear"


def _spread_gate_from_contracts(contracts: List["OptionContract"]) -> OptionsGateStatus:
    if not contracts:
        return "blocked"
    if any(contract.bid is None or contract.ask is None or contract.spread_pct is None for contract in contracts):
        return "blocked"
    if any(float(contract.spread_pct) > 25 for contract in contracts):
        return "blocked"
    if any(float(contract.spread_pct) > 12 for contract in contracts):
        return "manual_review"
    return "clear"


def _contract_blocking_reasons(contracts: List["OptionContract"]) -> List[str]:
    reasons: List[str] = []
    if not contracts:
        reasons.append("missing_contract_legs")
        return reasons
    if any(contract.bid is None or contract.ask is None for contract in contracts):
        reasons.append("missing_bid_ask")
    if any(contract.spread_pct is not None and float(contract.spread_pct) > 25 for contract in contracts):
        reasons.append("wide_bid_ask_spread")
    if any(contract.implied_volatility is None for contract in contracts):
        reasons.append("missing_iv")
    if any(contract.greeks is None for contract in contracts):
        reasons.append("missing_greeks")
    if any(contract.volume is None for contract in contracts):
        reasons.append("missing_volume")
    if any(contract.open_interest is None for contract in contracts):
        reasons.append("missing_open_interest")
    return _dedupe_codes(reasons)


def _no_trading_boundary(metadata: Optional["OptionsMetadata"]) -> OptionsNoTradingBoundary:
    return OptionsNoTradingBoundary(
        analyticalOnly=True,
        noBrokerExecution=metadata.no_broker_connection if metadata is not None else True,
        noOrderPlacement=metadata.no_order_placement if metadata is not None else True,
        noPortfolioMutation=metadata.no_portfolio_mutation if metadata is not None else True,
        noTradingRecommendation=metadata.no_trading_recommendation if metadata is not None else True,
    )


def _next_evidence_needed(
    *,
    readiness_state: OptionsReadinessState,
    blocking_reasons: List[str],
    data_quality_tier: OptionsDataQualityTier,
) -> List[str]:
    if readiness_state == "live_usable":
        return []
    if readiness_state == "delayed_usable":
        return ["等待更高新鲜度链路"]
    items: List[str] = []
    if any(code in _PROVIDER_BLOCKING_CODES for code in blocking_reasons):
        items.append("补充 provider authority 与 live chain 证据")
    if any(code in {"missing_bid_ask", "missing_contract_legs"} for code in blocking_reasons):
        items.append("补充完整期权链路与 bid/ask")
    if any(code in {"missing_iv", "missing_greeks"} for code in blocking_reasons):
        items.append("补充 Greeks 与 IV 证据")
    if any(
        code
        in {
            "missing_volume",
            "missing_open_interest",
            "wide_bid_ask_spread",
            "low_or_missing_volume",
            "low_or_missing_open_interest",
        }
        for code in blocking_reasons
    ):
        items.append("补充 OI/成交量与更紧价差证据")
    if not items and data_quality_tier in {"synthetic_demo_only", "insufficient"}:
        items.append("补充 provider authority 与 live chain 证据")
    return _dedupe_codes(items)


def _readiness_state(
    *,
    data_quality_tier: OptionsDataQualityTier,
    provider_authority: OptionsProviderAuthority,
    decision_grade: bool,
    liquidity_gate: OptionsGateStatus,
    iv_greeks_gate: OptionsGateStatus,
    spread_gate: OptionsGateStatus,
    blocking_reasons: List[str],
    freshness_hint: str = "",
) -> OptionsReadinessState:
    if provider_authority == "unavailable":
        return "blocked"
    if data_quality_tier in {"synthetic_demo_only", "insufficient"}:
        return "blocked" if blocking_reasons else "insufficient"
    if any(gate == "blocked" for gate in (liquidity_gate, iv_greeks_gate, spread_gate)):
        return "blocked"
    freshness = str(freshness_hint or "").strip().lower()
    if data_quality_tier == "live_usable" and decision_grade and freshness in _READY_FRESHNESS_VALUES:
        return "live_usable"
    if data_quality_tier == "delayed_usable" and not blocking_reasons:
        return "delayed_usable"
    if data_quality_tier == "live_usable" and not blocking_reasons:
        return "live_usable"
    return "insufficient"


def _build_research_readiness(
    *,
    metadata: Optional["OptionsMetadata"],
    data_quality_tier: OptionsDataQualityTier,
    decision_grade: bool,
    liquidity_gate: OptionsGateStatus,
    iv_greeks_gate: OptionsGateStatus,
    spread_gate: OptionsGateStatus,
    scenario_coverage: OptionsScenarioCoverage,
    blocking_reasons: List[str],
    source_hint: str = "",
    freshness_hint: str = "",
) -> OptionsResearchReadiness:
    provider_authority = _provider_authority_from_metadata(metadata, source_hint=source_hint)
    deduped_blockers = _dedupe_codes(
        [*_provider_blocking_reasons(metadata, source_hint=source_hint), *blocking_reasons]
    )
    readiness_state = _readiness_state(
        data_quality_tier=data_quality_tier,
        provider_authority=provider_authority,
        decision_grade=decision_grade,
        liquidity_gate=liquidity_gate,
        iv_greeks_gate=iv_greeks_gate,
        spread_gate=spread_gate,
        blocking_reasons=deduped_blockers,
        freshness_hint=freshness_hint,
    )
    return OptionsResearchReadiness(
        optionsResearchReady=readiness_state in {"delayed_usable", "live_usable"},
        readinessState=readiness_state,
        dataQualityTier=data_quality_tier,
        decisionGrade=decision_grade,
        providerAuthority=provider_authority,
        liquidityGate=liquidity_gate,
        ivGreeksGate=iv_greeks_gate,
        spreadGate=spread_gate,
        scenarioCoverage=scenario_coverage,
        noTradingBoundary=_no_trading_boundary(metadata),
        blockingReasons=deduped_blockers,
        nextEvidenceNeeded=_next_evidence_needed(
            readiness_state=readiness_state,
            blocking_reasons=deduped_blockers,
            data_quality_tier=data_quality_tier,
        ),
    )


def _default_decision_grade(
    *,
    data_quality_tier: OptionsDataQualityTier,
    provider_authority: OptionsProviderAuthority,
    liquidity_gate: OptionsGateStatus,
    iv_greeks_gate: OptionsGateStatus,
    spread_gate: OptionsGateStatus,
) -> bool:
    return (
        data_quality_tier == "live_usable"
        and provider_authority == "scoreGradeAllowed"
        and liquidity_gate == "clear"
        and iv_greeks_gate == "clear"
        and spread_gate == "clear"
    )


def _ensure_readiness_aliases(
    *,
    existing_readiness: Optional[OptionsResearchReadiness],
    existing_alias: Optional[OptionsResearchReadiness],
    computed: OptionsResearchReadiness,
) -> tuple[OptionsResearchReadiness, OptionsResearchReadiness]:
    readiness = existing_readiness or existing_alias or computed
    return readiness, readiness


def _build_contract_response_readiness(
    *,
    metadata: Optional["OptionsMetadata"],
    contracts: List["OptionContract"],
    scenario_coverage: OptionsScenarioCoverage,
    source_hint: str = "",
    freshness_hint: str = "",
    explicit_tier: Optional[str] = None,
) -> OptionsResearchReadiness:
    data_quality_tier = _infer_data_quality_tier(
        explicit_tier=explicit_tier,
        metadata=metadata,
        source_hint=source_hint,
        freshness_hint=freshness_hint,
    )
    liquidity_gate = _liquidity_gate_from_contracts(contracts) if contracts else "manual_review"
    iv_greeks_gate = _iv_greeks_gate_from_contracts(contracts) if contracts else "manual_review"
    spread_gate = _spread_gate_from_contracts(contracts) if contracts else "manual_review"
    provider_authority = _provider_authority_from_metadata(metadata, source_hint=source_hint)
    decision_grade = _default_decision_grade(
        data_quality_tier=data_quality_tier,
        provider_authority=provider_authority,
        liquidity_gate=liquidity_gate,
        iv_greeks_gate=iv_greeks_gate,
        spread_gate=spread_gate,
    )
    return _build_research_readiness(
        metadata=metadata,
        data_quality_tier=data_quality_tier,
        decision_grade=decision_grade,
        liquidity_gate=liquidity_gate,
        iv_greeks_gate=iv_greeks_gate,
        spread_gate=spread_gate,
        scenario_coverage=scenario_coverage,
        blocking_reasons=_contract_blocking_reasons(contracts),
        source_hint=source_hint,
        freshness_hint=freshness_hint,
    )


class OptionsAnalyzeRequest(_OptionsModel):
    symbol: str
    market_data_provider: str = Field(default="synthetic_fixture", alias="marketDataProvider")
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
    options_readiness: Optional[OptionsResearchReadiness] = Field(default=None, alias="optionsReadiness")
    options_research_readiness: Optional[OptionsResearchReadiness] = Field(
        default=None,
        alias="optionsResearchReadiness",
    )

    @model_validator(mode="after")
    def _populate_options_readiness(self) -> "OptionsAnalyzeResponse":
        contracts = [item.contract for item in self.candidate_contracts]
        computed = _build_contract_response_readiness(
            metadata=self.metadata,
            contracts=contracts,
            scenario_coverage="single_contract",
            source_hint=str(self.option_chain_summary.get("source") or ""),
            freshness_hint=str(self.underlying.get("freshness") or ""),
        )
        self.options_readiness, self.options_research_readiness = _ensure_readiness_aliases(
            existing_readiness=self.options_readiness,
            existing_alias=self.options_research_readiness,
            computed=computed,
        )
        return self


class OptionsScenarioRequest(_OptionsModel):
    symbol: str
    market_data_provider: str = Field(default="synthetic_fixture", alias="marketDataProvider")
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
    options_readiness: Optional[OptionsResearchReadiness] = Field(default=None, alias="optionsReadiness")
    options_research_readiness: Optional[OptionsResearchReadiness] = Field(
        default=None,
        alias="optionsResearchReadiness",
    )

    @model_validator(mode="after")
    def _populate_options_readiness(self) -> "OptionsScenarioResponse":
        computed = _build_contract_response_readiness(
            metadata=self.metadata,
            contracts=[self.contract],
            scenario_coverage="single_contract",
            source_hint=self.contract.source,
            freshness_hint=self.contract.freshness,
        )
        self.options_readiness, self.options_research_readiness = _ensure_readiness_aliases(
            existing_readiness=self.options_readiness,
            existing_alias=self.options_research_readiness,
            computed=computed,
        )
        return self


class OptionsStrategyCompareRequest(_OptionsModel):
    symbol: str
    market_data_provider: str = Field(default="synthetic_fixture", alias="marketDataProvider")
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
    options_readiness: Optional[OptionsResearchReadiness] = Field(default=None, alias="optionsReadiness")
    options_research_readiness: Optional[OptionsResearchReadiness] = Field(
        default=None,
        alias="optionsResearchReadiness",
    )

    @model_validator(mode="after")
    def _populate_options_readiness(self) -> "OptionsStrategyCompareResponse":
        contracts: List[OptionContract] = []
        computed = _build_contract_response_readiness(
            metadata=self.metadata,
            contracts=contracts,
            scenario_coverage="strategy_compare_ready",
            source_hint="",
            freshness_hint=str(self.underlying.get("freshness") or ""),
        )
        self.options_readiness, self.options_research_readiness = _ensure_readiness_aliases(
            existing_readiness=self.options_readiness,
            existing_alias=self.options_research_readiness,
            computed=computed,
        )
        return self


class OptionsDecisionLeg(_OptionsModel):
    action: Literal["buy", "sell"] = "buy"
    side: Literal["call", "put"]
    contract_symbol: Optional[str] = Field(default=None, alias="contractSymbol")
    expiration: Optional[str] = None
    strike: Optional[float] = Field(default=None, gt=0)
    quantity: int = Field(default=1, ge=1)


class OptionsDecisionRequest(_OptionsModel):
    symbol: str
    market_data_provider: str = Field(default="synthetic_fixture", alias="marketDataProvider")
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


class OptionsGateIssue(_OptionsModel):
    code: str
    category: str
    status: OptionsGateStatus
    label: str
    decision_grade: bool = Field(default=False, alias="decisionGrade")
    leg_index: Optional[int] = Field(default=None, alias="legIndex")
    contract_symbol: Optional[str] = Field(default=None, alias="contractSymbol")


class OptionsLegGateDiagnostics(_OptionsModel):
    leg_index: int = Field(alias="legIndex")
    contract_symbol: Optional[str] = Field(default=None, alias="contractSymbol")
    data_quality_status: OptionsGateStatus = Field(alias="dataQualityStatus")
    liquidity_status: OptionsGateStatus = Field(alias="liquidityStatus")
    issue_codes: List[str] = Field(default_factory=list, alias="issueCodes")
    decision_grade: bool = Field(default=False, alias="decisionGrade")


class OptionsStrategyGateSummary(_OptionsModel):
    status: OptionsGateStatus
    issue_codes: List[str] = Field(default_factory=list, alias="issueCodes")
    decision_grade: bool = Field(default=False, alias="decisionGrade")
    leg_diagnostics: List[OptionsLegGateDiagnostics] = Field(default_factory=list, alias="legDiagnostics")


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
    data_quality_gates: Optional[OptionsStrategyGateSummary] = Field(default=None, alias="dataQualityGates")
    liquidity_gates: Optional[OptionsStrategyGateSummary] = Field(default=None, alias="liquidityGates")
    gate_decision: Optional[OptionsGateDecision] = Field(default=None, alias="gateDecision")
    gate_issues: List[OptionsGateIssue] = Field(default_factory=list, alias="gateIssues")
    decision_grade: Optional[bool] = Field(default=None, alias="decisionGrade")
    fail_closed_reason_codes: List[str] = Field(default_factory=list, alias="failClosedReasonCodes")
    better_alternative: Optional[OptionsDecisionAlternative] = Field(default=None, alias="betterAlternative")
    no_advice_disclosure: str = Field(alias="noAdviceDisclosure")
    freshness: OptionsDecisionFreshness
    metadata: OptionsMetadata = Field(default_factory=OptionsMetadata)
    options_readiness: Optional[OptionsResearchReadiness] = Field(default=None, alias="optionsReadiness")
    options_research_readiness: Optional[OptionsResearchReadiness] = Field(
        default=None,
        alias="optionsResearchReadiness",
    )

    @model_validator(mode="after")
    def _populate_options_readiness(self) -> "OptionsDecisionResponse":
        provider_authority = _provider_authority_from_metadata(
            self.metadata,
            source_hint=self.freshness.source if self.freshness is not None else "",
        )
        liquidity_gate = (
            _status_from_value(self.liquidity_gates.status, fallback="clear")
            if self.liquidity_gates is not None
            else "clear"
        )
        iv_greeks_gate = (
            _status_from_value(self.data_quality_gates.status, fallback="clear")
            if self.data_quality_gates is not None
            else ("blocked" if self.iv_greeks.iv_rank_status == "unavailable" else "clear")
        )
        spread_gate = (
            "blocked"
            if any(code == "missing_bid_ask" for code in self.fail_closed_reason_codes)
            else "manual_review"
            if "wide_bid_ask_spread" in {
                *list(self.fail_closed_reason_codes),
                *list(self.liquidity.liquidity_warnings),
            }
            else "blocked"
            if self.liquidity.spread_pct is None or float(self.liquidity.spread_pct) > 25
            else "manual_review"
            if float(self.liquidity.spread_pct) > 12
            else "clear"
        )
        scenario_coverage: OptionsScenarioCoverage = (
            "strategy_compare_ready"
            if self.strategy in {"bull_call_spread", "bear_put_spread"}
            else "missing_chain_data"
            if any(code in {"missing_bid_ask", "missing_contract_legs"} for code in self.fail_closed_reason_codes)
            else "single_contract"
        )
        data_quality_tier = _infer_data_quality_tier(
            explicit_tier=self.data_quality.data_quality_tier,
            metadata=self.metadata,
            source_hint=self.freshness.source if self.freshness is not None else "",
            freshness_hint=self.freshness.freshness if self.freshness is not None else "",
        )
        blocking_reasons = _dedupe_codes(
            [
                *_provider_blocking_reasons(
                    self.metadata,
                    source_hint=self.freshness.source if self.freshness is not None else "",
                ),
                *list(self.data_quality.blocking_reasons),
                *list(self.fail_closed_reason_codes),
                *[
                    warning
                    for warning in (
                        *list(self.data_quality.warnings),
                        *list(self.iv_greeks.warnings),
                        *list(self.liquidity.liquidity_warnings),
                    )
                    if warning
                    in {
                        "missing_iv",
                        "missing_greeks",
                        "missing_volume",
                        "missing_open_interest",
                        "wide_bid_ask_spread",
                        "low_or_missing_volume",
                        "low_or_missing_open_interest",
                    }
                ],
            ]
        )
        decision_grade = (
            bool(self.decision_grade)
            if self.decision_grade is not None
            else _default_decision_grade(
                data_quality_tier=data_quality_tier,
                provider_authority=provider_authority,
                liquidity_gate=liquidity_gate,
                iv_greeks_gate=iv_greeks_gate,
                spread_gate=spread_gate,
            )
        )
        computed = _build_research_readiness(
            metadata=self.metadata,
            data_quality_tier=data_quality_tier,
            decision_grade=decision_grade,
            liquidity_gate=liquidity_gate,
            iv_greeks_gate=iv_greeks_gate,
            spread_gate=spread_gate,
            scenario_coverage=scenario_coverage,
            blocking_reasons=blocking_reasons,
            source_hint=self.freshness.source if self.freshness is not None else "",
            freshness_hint=self.freshness.freshness if self.freshness is not None else "",
        )
        self.options_readiness, self.options_research_readiness = _ensure_readiness_aliases(
            existing_readiness=self.options_readiness,
            existing_alias=self.options_research_readiness,
            computed=computed,
        )
        return self
