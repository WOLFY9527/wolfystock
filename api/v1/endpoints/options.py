# -*- coding: utf-8 -*-
"""Read-only Options Lab Phase 1 endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.options import (
    OptionChainResponse,
    OptionCandidateContract,
    OptionContractScoring,
    OptionExpirationItem,
    OptionExpirationsResponse,
    OptionScenarioPayoffRow,
    OptionScenarioRisk,
    OptionScoringSubScores,
    OptionsAnalyzeRequest,
    OptionsAnalyzeResponse,
    OptionsDecisionAlternative,
    OptionsDecisionBreakeven,
    OptionsDecisionDataQuality,
    OptionsDecisionFreshness,
    OptionsDecisionIvGreeks,
    OptionsDecisionLiquidity,
    OptionsDecisionOptimizer,
    OptionsDecisionRequest,
    OptionsDecisionResponse,
    OptionsDecisionRiskReward,
    OptionsExpectedMove,
    OptionsGateIssue,
    OptionsOptimizerAlternative,
    OptionsScenarioRequest,
    OptionsScenarioResponse,
    OptionsStrategyComparison,
    OptionsStrategyGateSummary,
    OptionsStrategyCompareRequest,
    OptionsStrategyCompareResponse,
    OptionsStrategyLeg,
    OptionUnderlyingSummaryResponse,
)
from src.services.options_lab_domain_models import (
    AnalyzeCandidateModel,
    AnalyzeResultModel,
    AnalyzeSubScoresModel,
    BreakevenAssessment,
    DecisionAlternativeModel,
    DecisionDataQualityAssessment,
    DecisionEvaluationResult,
    ExpectedMoveEstimate,
    IvGreeksAssessment,
    LiquidityAssessment,
    OptionChainResultModel,
    OptionExpirationModel,
    OptionExpirationsResultModel,
    OptionUnderlyingSummaryResultModel,
    OptimizerCandidate,
    OptimizerResult,
    RiskRewardAssessment,
    ScenarioPayoffRowModel,
    ScenarioResultModel,
    ScenarioRiskModel,
    StrategyCompareResultModel,
    StrategyComparisonModel,
    StrategyLegModel,
)
from src.services.options_lab_service import (
    OptionsLabProviderUnavailable,
    OptionsLabService,
    OptionsLabUnsupportedSymbol,
)

router = APIRouter()


def _service() -> OptionsLabService:
    return OptionsLabService()


def _unsupported_response(exc: OptionsLabUnsupportedSymbol) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "error": exc.code,
            "message": "Options Lab Phase 1 supports fixture-backed US listed equity options only.",
        },
    )


def _provider_unavailable_response(exc: OptionsLabProviderUnavailable) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "error": exc.code,
            "message": "Requested Options Lab provider is fixture-only, disabled, or not implemented.",
        },
    )


def _map_decision_data_quality(data_quality: DecisionDataQualityAssessment) -> OptionsDecisionDataQuality:
    return OptionsDecisionDataQuality(
        dataQualityScore=data_quality.data_quality_score,
        dataQualityTier=data_quality.data_quality_tier,
        sourceType=data_quality.source_type,
        asOfAgeMinutes=data_quality.as_of_age_minutes,
        blockingReasons=list(data_quality.blocking_reasons),
        warnings=list(data_quality.warnings),
    )


def _map_underlying_summary_response(result: OptionUnderlyingSummaryResultModel) -> OptionUnderlyingSummaryResponse:
    return OptionUnderlyingSummaryResponse(
        symbol=result.symbol,
        market=result.market,
        currency=result.currency,
        underlying=dict(result.underlying),
        optionsAvailability=dict(result.options_availability),
        asOf=result.as_of,
        source=result.source,
        warnings=list(result.warnings),
        metadata=result.metadata,
    )


def _map_expiration_item(expiration: OptionExpirationModel) -> OptionExpirationItem:
    return OptionExpirationItem(
        date=expiration.date,
        dte=expiration.dte,
        type=expiration.type,
        chainAvailable=expiration.chain_available,
        asOf=expiration.as_of,
        source=expiration.source,
        warnings=list(expiration.warnings),
    )


def _map_expirations_response(result: OptionExpirationsResultModel) -> OptionExpirationsResponse:
    return OptionExpirationsResponse(
        symbol=result.symbol,
        market=result.market,
        expirations=[_map_expiration_item(item) for item in result.expirations],
        asOf=result.as_of,
        source=result.source,
        warnings=list(result.warnings),
        metadata=result.metadata,
    )


def _map_chain_response(result: OptionChainResultModel) -> OptionChainResponse:
    return OptionChainResponse(
        symbol=result.symbol,
        market=result.market,
        underlying=dict(result.underlying),
        expiration=result.expiration,
        calls=list(result.calls),
        puts=list(result.puts),
        filtersApplied=dict(result.filters_applied),
        chainAsOf=result.chain_as_of,
        source=result.source,
        warnings=list(result.warnings),
        metadata=result.metadata,
    )


def _map_analyze_sub_scores(sub_scores: AnalyzeSubScoresModel) -> OptionScoringSubScores:
    return OptionScoringSubScores(
        directionalFit=sub_scores.directional_fit,
        deltaFit=sub_scores.delta_fit,
        breakevenDifficulty=sub_scores.breakeven_difficulty,
        premiumEfficiency=sub_scores.premium_efficiency,
        liquidityScore=sub_scores.liquidity_score,
        spreadPenalty=sub_scores.spread_penalty,
        ivRisk=sub_scores.iv_risk,
        thetaRisk=sub_scores.theta_risk,
        dteFit=sub_scores.dte_fit,
        targetScenarioPayoff=sub_scores.target_scenario_payoff,
        maxLossBudgetFit=sub_scores.max_loss_budget_fit,
        oiVolumeConfidence=sub_scores.oi_volume_confidence,
        dataFreshnessConfidence=sub_scores.data_freshness_confidence,
    )


def _map_contract_scoring(candidate: AnalyzeCandidateModel) -> OptionContractScoring:
    return OptionContractScoring(
        subScores=_map_analyze_sub_scores(candidate.sub_scores),
        gradeLabel=candidate.grade_label,
        topPositiveDrivers=list(candidate.top_positive_drivers),
        topRiskDrivers=list(candidate.top_risk_drivers),
        assumptionsUsed=dict(candidate.assumptions_used),
        dataConfidence=candidate.data_confidence,
        notAdviceDisclosure=candidate.not_advice_disclosure,
    )


def _map_analyze_candidate(candidate: AnalyzeCandidateModel) -> OptionCandidateContract:
    return OptionCandidateContract(
        strategy=candidate.strategy,
        contract=candidate.contract,
        score=candidate.score,
        gradeLabel=candidate.grade_label,
        premiumAtRisk=candidate.premium_at_risk,
        breakeven=candidate.breakeven,
        requiredMovePct=candidate.required_move_pct,
        targetPayoff=candidate.target_payoff,
        scoring=_map_contract_scoring(candidate),
    )


def _map_analyze_response(result: AnalyzeResultModel) -> OptionsAnalyzeResponse:
    return OptionsAnalyzeResponse(
        symbol=result.symbol,
        underlying=result.underlying,
        assumptions=dict(result.assumptions),
        optionChainSummary=dict(result.option_chain_summary),
        candidateContracts=[_map_analyze_candidate(candidate) for candidate in result.candidate_contracts],
        risks=list(result.risks),
        limitations=list(result.limitations),
        metadata=result.metadata,
    )


def _map_scenario_payoff_row(row: ScenarioPayoffRowModel) -> OptionScenarioPayoffRow:
    return OptionScenarioPayoffRow(
        label=row.label,
        underlyingPrice=row.underlying_price,
        grossPayoff=row.gross_payoff,
        netPayoff=row.net_payoff,
        returnOnPremiumPct=row.return_on_premium_pct,
    )


def _map_scenario_risk(risk: ScenarioRiskModel) -> OptionScenarioRisk:
    return OptionScenarioRisk(
        premiumAtRisk=risk.premium_at_risk,
        breakeven=risk.breakeven,
        requiredMovePct=risk.required_move_pct,
        maxLoss=risk.max_loss,
    )


def _map_scenario_response(result: ScenarioResultModel) -> OptionsScenarioResponse:
    return OptionsScenarioResponse(
        symbol=result.symbol,
        underlying=result.underlying,
        strategy=result.strategy,
        contract=result.contract,
        expirationPayoffGrid=[_map_scenario_payoff_row(row) for row in result.expiration_payoff_grid],
        risk=_map_scenario_risk(result.risk),
        preExpirationTheoreticalPricing=dict(result.pre_expiration_theoretical_pricing),
        limitations=list(result.limitations),
        metadata=result.metadata,
    )


def _map_strategy_leg(leg: StrategyLegModel) -> OptionsStrategyLeg:
    return OptionsStrategyLeg(
        action=leg.action,
        side=leg.side,
        contractSymbol=leg.contract_symbol,
        expiration=leg.expiration,
        strike=leg.strike,
        mid=leg.mid,
        quantity=leg.quantity,
    )


def _map_strategy_comparison(comparison: StrategyComparisonModel) -> OptionsStrategyComparison:
    return OptionsStrategyComparison(
        strategyType=comparison.strategy_type,
        legs=[_map_strategy_leg(leg) for leg in comparison.legs],
        netDebit=comparison.net_debit,
        maxLoss=comparison.max_loss,
        maxGain=comparison.max_gain,
        breakeven=comparison.breakeven,
        requiredMovePct=comparison.required_move_pct,
        payoffAtTarget=comparison.payoff_at_target,
        riskRewardRatio=comparison.risk_reward_ratio,
        liquidityWarnings=list(comparison.liquidity_warnings),
        ivThetaNotes=list(comparison.iv_theta_notes),
        suitabilityNotes=list(comparison.suitability_notes),
        limitations=list(comparison.limitations),
        noAdviceDisclosure=comparison.no_advice_disclosure,
    )


def _map_strategy_compare_response(result: StrategyCompareResultModel) -> OptionsStrategyCompareResponse:
    return OptionsStrategyCompareResponse(
        symbol=result.symbol,
        underlying=result.underlying,
        assumptions=dict(result.assumptions),
        strategies=[_map_strategy_comparison(item) for item in result.strategies],
        limitations=list(result.limitations),
        metadata=result.metadata,
    )


def _map_decision_liquidity(liquidity: LiquidityAssessment) -> OptionsDecisionLiquidity:
    return OptionsDecisionLiquidity(
        liquidityScore=liquidity.liquidity_score,
        spreadPct=liquidity.spread_pct,
        liquidityWarnings=list(liquidity.liquidity_warnings),
    )


def _map_decision_iv_greeks(iv_greeks: IvGreeksAssessment) -> OptionsDecisionIvGreeks:
    return OptionsDecisionIvGreeks(
        ivReadiness=iv_greeks.iv_readiness,
        ivRankStatus=iv_greeks.iv_rank_status,
        ivRank=iv_greeks.iv_rank,
        ivPercentile=iv_greeks.iv_percentile,
        ivRankSource=iv_greeks.iv_rank_source,
        ivRankConfidence=iv_greeks.iv_rank_confidence,
        warnings=list(iv_greeks.warnings),
        dteBucket=iv_greeks.dte_bucket,
    )


def _map_decision_breakeven(breakeven: BreakevenAssessment) -> OptionsDecisionBreakeven:
    return OptionsDecisionBreakeven(
        breakeven=breakeven.breakeven,
        requiredMovePct=breakeven.required_move_pct,
        targetPriceStatus=breakeven.target_price_status,
        score=breakeven.score,
    )


def _map_decision_risk_reward(risk_reward: RiskRewardAssessment) -> OptionsDecisionRiskReward:
    return OptionsDecisionRiskReward(
        maxLoss=risk_reward.max_loss,
        maxGain=risk_reward.max_gain,
        riskRewardRatio=risk_reward.risk_reward_ratio,
        score=risk_reward.score,
        warnings=list(risk_reward.warnings),
    )


def _map_expected_move(expected_move: ExpectedMoveEstimate) -> OptionsExpectedMove:
    return OptionsExpectedMove(
        expectedMoveAbs=expected_move.expected_move_abs,
        expectedMovePct=expected_move.expected_move_pct,
        expectedMoveSource=expected_move.expected_move_source,
        expectedMoveWarnings=list(expected_move.expected_move_warnings),
    )


def _map_optimizer_candidate(candidate: OptimizerCandidate) -> OptionsOptimizerAlternative:
    return OptionsOptimizerAlternative(
        strategyKey=candidate.strategy_key,
        dataQualityTier=candidate.data_quality_tier,
        liquidityScore=candidate.liquidity_score,
        breakevenPressure=candidate.breakeven_pressure,
        maxLoss=candidate.max_loss,
        maxGain=candidate.max_gain,
        riskRewardRatio=candidate.risk_reward_ratio,
        expectedMoveAlignment=candidate.expected_move_alignment,
        ivReadiness=candidate.iv_readiness,
        tradeQualityScore=candidate.trade_quality_score,
        decisionLabel=candidate.decision_label,
        primaryReasons=list(candidate.primary_reasons),
        riskWarnings=list(candidate.risk_warnings),
    )


def _map_decision_optimizer(optimizer: OptimizerResult) -> OptionsDecisionOptimizer:
    return OptionsDecisionOptimizer(
        preferredStrategyKey=optimizer.preferred_strategy_key,
        optimizerLabel=optimizer.optimizer_label,
        alternatives=[_map_optimizer_candidate(item) for item in optimizer.alternatives],
        noTradeReason=optimizer.no_trade_reason,
    )


def _map_decision_alternative(
    alternative: DecisionAlternativeModel | None,
) -> OptionsDecisionAlternative | None:
    if alternative is None:
        return None
    return OptionsDecisionAlternative(
        strategyType=alternative.strategy_type,
        reason=alternative.reason,
        maxLoss=alternative.max_loss,
        riskRewardRatio=alternative.risk_reward_ratio,
    )


def _map_decision_response(result: DecisionEvaluationResult) -> OptionsDecisionResponse:
    optimizer = _map_decision_optimizer(result.optimizer)
    return OptionsDecisionResponse(
        symbol=result.symbol,
        strategy=result.strategy,
        dataQuality=_map_decision_data_quality(result.data_quality),
        liquidity=_map_decision_liquidity(result.liquidity),
        ivGreeks=_map_decision_iv_greeks(result.iv_greeks),
        ivRank=result.iv_greeks.iv_rank,
        ivPercentile=result.iv_greeks.iv_percentile,
        ivRankStatus=result.iv_greeks.iv_rank_status,
        expectedMove=_map_expected_move(result.expected_move),
        optimizer=optimizer,
        rankedAlternatives=list(optimizer.alternatives),
        breakeven=_map_decision_breakeven(result.breakeven),
        riskReward=_map_decision_risk_reward(result.risk_reward),
        tradeQualityScore=result.trade_quality_score,
        decisionLabel=result.decision_label,
        primaryReasons=list(result.primary_reasons),
        riskWarnings=list(result.risk_warnings),
        dataQualityGates=(
            OptionsStrategyGateSummary.model_validate(result.data_quality_gates)
            if result.data_quality_gates is not None
            else None
        ),
        liquidityGates=(
            OptionsStrategyGateSummary.model_validate(result.liquidity_gates)
            if result.liquidity_gates is not None
            else None
        ),
        gateDecision=result.gate_decision,
        gateIssues=[OptionsGateIssue.model_validate(item) for item in result.gate_issues],
        decisionGrade=result.decision_grade,
        failClosedReasonCodes=list(result.fail_closed_reason_codes),
        betterAlternative=_map_decision_alternative(result.better_alternative),
        noAdviceDisclosure=result.no_advice_disclosure,
        freshness=OptionsDecisionFreshness(
            source=result.freshness.source if result.freshness is not None else "unknown",
            freshness=result.freshness.freshness if result.freshness is not None else "unknown",
            asOf=result.freshness.as_of if result.freshness is not None else None,
        ),
        metadata=result.metadata,
    )


@router.get(
    "/underlyings/{symbol}/summary",
    response_model=OptionUnderlyingSummaryResponse,
    summary="Get fixture-backed Options Lab underlying summary",
)
def get_options_underlying_summary(
    symbol: str,
    force_refresh: bool = Query(default=False, alias="forceRefresh"),
    market_data_provider: str = Query(default="synthetic_fixture", alias="marketDataProvider"),
) -> OptionUnderlyingSummaryResponse:
    try:
        return _map_underlying_summary_response(
            _service().get_summary(
                symbol,
                force_refresh=force_refresh,
                market_data_provider=market_data_provider,
            )
        )
    except OptionsLabUnsupportedSymbol as exc:
        raise _unsupported_response(exc) from exc
    except OptionsLabProviderUnavailable as exc:
        raise _provider_unavailable_response(exc) from exc


@router.get(
    "/underlyings/{symbol}/expirations",
    response_model=OptionExpirationsResponse,
    summary="Get fixture-backed Options Lab expirations",
)
def get_options_expirations(
    symbol: str,
    force_refresh: bool = Query(default=False, alias="forceRefresh"),
    market_data_provider: str = Query(default="synthetic_fixture", alias="marketDataProvider"),
) -> OptionExpirationsResponse:
    try:
        return _map_expirations_response(
            _service().get_expirations(
                symbol,
                force_refresh=force_refresh,
                market_data_provider=market_data_provider,
            )
        )
    except OptionsLabUnsupportedSymbol as exc:
        raise _unsupported_response(exc) from exc
    except OptionsLabProviderUnavailable as exc:
        raise _provider_unavailable_response(exc) from exc


@router.get(
    "/underlyings/{symbol}/chain",
    response_model=OptionChainResponse,
    summary="Get fixture-backed normalized option chain",
)
def get_options_chain(
    symbol: str,
    expiration: str | None = Query(default=None),
    side: str = Query(default="both", pattern="^(call|put|both)$"),
    min_open_interest: int | None = Query(default=None, alias="minOpenInterest", ge=0),
    max_spread_pct: float | None = Query(default=None, alias="maxSpreadPct", ge=0),
    include_greeks: bool = Query(default=True, alias="includeGreeks"),
    force_refresh: bool = Query(default=False, alias="forceRefresh"),
    market_data_provider: str = Query(default="synthetic_fixture", alias="marketDataProvider"),
) -> OptionChainResponse:
    try:
        return _map_chain_response(
            _service().get_chain(
                symbol,
                expiration=expiration,
                side=side,
                min_open_interest=min_open_interest,
                max_spread_pct=max_spread_pct,
                include_greeks=include_greeks,
                force_refresh=force_refresh,
                market_data_provider=market_data_provider,
            )
        )
    except OptionsLabUnsupportedSymbol as exc:
        raise _unsupported_response(exc) from exc
    except OptionsLabProviderUnavailable as exc:
        raise _provider_unavailable_response(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(exc)}) from exc


@router.post(
    "/analyze",
    response_model=OptionsAnalyzeResponse,
    summary="Analyze fixture-backed Options Lab candidate contracts",
)
def analyze_options(request: OptionsAnalyzeRequest) -> OptionsAnalyzeResponse:
    try:
        return _map_analyze_response(_service().analyze(request))
    except OptionsLabUnsupportedSymbol as exc:
        raise _unsupported_response(exc) from exc
    except OptionsLabProviderUnavailable as exc:
        raise _provider_unavailable_response(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(exc)}) from exc


@router.post(
    "/decision/evaluate",
    response_model=OptionsDecisionResponse,
    summary="Evaluate fixture-backed Options Lab trade quality",
)
def evaluate_options_decision(request: OptionsDecisionRequest) -> OptionsDecisionResponse:
    try:
        return _map_decision_response(_service().evaluate_decision(request))
    except OptionsLabUnsupportedSymbol as exc:
        raise _unsupported_response(exc) from exc
    except OptionsLabProviderUnavailable as exc:
        raise _provider_unavailable_response(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(exc)}) from exc


@router.post(
    "/scenario",
    response_model=OptionsScenarioResponse,
    summary="Compute deterministic fixture-backed Options Lab expiration payoff scenarios",
)
def analyze_options_scenario(request: OptionsScenarioRequest) -> OptionsScenarioResponse:
    try:
        return _map_scenario_response(_service().scenario(request))
    except OptionsLabUnsupportedSymbol as exc:
        raise _unsupported_response(exc) from exc
    except OptionsLabProviderUnavailable as exc:
        raise _provider_unavailable_response(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(exc)}) from exc


@router.post(
    "/strategies/compare",
    response_model=OptionsStrategyCompareResponse,
    summary="Compare fixture-backed defined-risk Options Lab strategies",
)
def compare_options_strategies(request: OptionsStrategyCompareRequest) -> OptionsStrategyCompareResponse:
    try:
        return _map_strategy_compare_response(_service().compare_strategies(request))
    except OptionsLabUnsupportedSymbol as exc:
        raise _unsupported_response(exc) from exc
    except OptionsLabProviderUnavailable as exc:
        raise _provider_unavailable_response(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(exc)}) from exc
