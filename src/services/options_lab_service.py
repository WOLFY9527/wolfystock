# -*- coding: utf-8 -*-
"""Fixture-backed Options Lab Phase 1 service.

Phase 1 deliberately avoids live providers, LLMs, broker execution, and
portfolio mutation. The service only normalizes the synthetic TEM fixture.
"""

from __future__ import annotations

import copy
from datetime import date, datetime
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from api.v1.schemas.options import (
    OptionChainResponse,
    OptionCandidateContract,
    OptionContract,
    OptionContractScoring,
    OptionExpirationItem,
    OptionExpirationsResponse,
    OptionGreeks,
    OptionScenarioPayoffRow,
    OptionScenarioRisk,
    OptionScoringSubScores,
    OptionsMetadata,
    OptionsAnalyzeRequest,
    OptionsAnalyzeResponse,
    OptionsDecisionAlternative,
    OptionsDecisionBreakeven,
    OptionsDecisionDataQuality,
    OptionsDecisionFreshness,
    OptionsDecisionIvGreeks,
    OptionsDecisionLeg,
    OptionsDecisionLiquidity,
    OptionsDecisionOptimizer,
    OptionsDecisionRequest,
    OptionsDecisionResponse,
    OptionsDecisionRiskReward,
    OptionsExpectedMove,
    OptionsOptimizerAlternative,
    OptionsScenarioRequest,
    OptionsScenarioResponse,
    OptionsStrategyCompareRequest,
    OptionsStrategyCompareResponse,
    OptionsStrategyComparison,
    OptionsStrategyLeg,
    OptionUnderlyingSummaryResponse,
)
from src.services.options_market_data_provider import (
    DEFAULT_OPTIONS_FIXTURE_PATH,
    DEFAULT_OPTIONS_PROVIDER_NAME,
    OptionsMarketDataProvider,
    OptionsProviderError,
    OptionsProviderUnavailable,
    OptionsProviderUnsupportedSymbol,
    create_options_market_data_provider,
)


DEFAULT_FIXTURE_PATH = DEFAULT_OPTIONS_FIXTURE_PATH
PHASE1_WARNING_CODES = [
    "synthetic_fixture_data",
    "options_are_high_risk",
    "long_options_can_lose_100_percent_premium",
    "data_may_be_delayed_or_stale",
    "analytical_only_not_investment_advice",
    "no_order_placement",
]
PHASE3_RISKS = [
    "options_are_high_risk",
    "long_options_can_lose_100_percent_premium",
    "bid_ask_spread_can_create_slippage",
    "iv_and_theta_can_reduce_long_premium_value",
    "scores_are_analytical_rankings_under_assumptions",
]
PHASE3_LIMITATIONS = [
    "synthetic_fixture_data_only",
    "long_call_and_long_put_only_in_phase3",
    "phase4_spreads_deferred",
    "pre_expiration_theoretical_pricing_unavailable",
    "no_live_provider_calls",
    "no_llm_calls",
    "no_broker_execution",
    "no_portfolio_mutation",
    "no_order_placement",
    "not_trading_advice",
]
PHASE4_LIMITATIONS = [
    "synthetic_fixture_data_only",
    "defined_risk_debit_structures_only",
    "naked_short_strategies_not_supported",
    "credit_spreads_not_supported_in_phase4",
    "pre_expiration_theoretical_pricing_unavailable",
    "no_live_provider_calls",
    "no_llm_calls",
    "no_broker_execution",
    "no_portfolio_mutation",
    "no_order_placement",
    "not_trading_advice",
]
CONTRACT_MULTIPLIER = 100
SCORING_MODEL_VERSION = "deterministic_fixture_scoring_v1"
SCENARIO_MODEL_VERSION = "expiration_payoff_v1"
STRATEGY_COMPARE_MODEL_VERSION = "defined_risk_strategy_compare_v1"
DECISION_ENGINE_MODEL_VERSION = "options_decision_engine_r2"
SUPPORTED_COMPARE_STRATEGIES = {"long_call", "long_put", "bull_call_spread", "bear_put_spread"}


class OptionsLabUnsupportedSymbol(ValueError):
    """Raised when Phase 1 has no safe fixture for the requested symbol."""

    def __init__(self, symbol: str, code: str = "unsupported_symbol_or_market") -> None:
        self.symbol = symbol
        self.code = code
        super().__init__("Options Lab Phase 1 supports fixture-backed US listed equity options only.")


class OptionsLabProviderUnavailable(ValueError):
    """Raised when a requested options market data provider is disabled."""

    def __init__(self, provider_name: str, code: str = "options_provider_not_implemented") -> None:
        self.provider_name = provider_name
        self.code = code
        super().__init__("Options provider is disabled or not implemented for Options Lab.")


class OptionsLabService:
    """Read-only normalizer for synthetic Options Lab fixtures."""

    def __init__(
        self,
        fixture_path: Optional[Path] = None,
        market_data_provider: Optional[OptionsMarketDataProvider] = None,
        provider_name: str = DEFAULT_OPTIONS_PROVIDER_NAME,
    ) -> None:
        self.fixture_path = fixture_path or DEFAULT_FIXTURE_PATH
        self.provider_name = provider_name
        if market_data_provider is not None:
            self.market_data_provider = market_data_provider
        else:
            try:
                self.market_data_provider = create_options_market_data_provider(
                    provider_name=provider_name,
                    fixture_path=self.fixture_path,
                )
            except OptionsProviderUnavailable as exc:
                raise OptionsLabProviderUnavailable(exc.provider_name, code=exc.code) from exc

    def get_summary(
        self,
        symbol: str,
        force_refresh: bool = False,
        market_data_provider: Optional[str] = None,
    ) -> OptionUnderlyingSummaryResponse:
        fixture = self._fixture_for_symbol(symbol, market_data_provider=market_data_provider)
        metadata = self._metadata(force_refresh=force_refresh, fixture=fixture)
        underlying = self._safe_underlying(fixture)
        return OptionUnderlyingSummaryResponse(
            symbol=fixture["symbol"],
            market=fixture["market"],
            currency=fixture.get("currency", "USD"),
            underlying=underlying,
            optionsAvailability={
                "supported": True,
                "provider": fixture.get("providerName") or fixture.get("source") or "unknown",
                "providerCapabilities": fixture.get("providerCapabilities") or {},
                "limitations": ["fixture_only", "provider_validation_required_later"],
            },
            asOf=fixture["chainAsOf"],
            source=fixture["source"],
            warnings=list(PHASE1_WARNING_CODES),
            metadata=metadata,
        )

    def get_expirations(
        self,
        symbol: str,
        force_refresh: bool = False,
        market_data_provider: Optional[str] = None,
    ) -> OptionExpirationsResponse:
        fixture = self._fixture_for_symbol(symbol, market_data_provider=market_data_provider)
        expirations = [
            OptionExpirationItem(
                date=str(item["date"]),
                dte=int(item["dte"]),
                type=str(item.get("type") or "unknown"),
                chainAvailable=bool(item.get("chainAvailable", True)),
                asOf=str(item.get("asOf") or fixture["chainAsOf"]),
                source=str(item.get("source") or fixture["source"]),
                warnings=list(item.get("warnings") or []),
            )
            for item in sorted(fixture.get("expirations") or [], key=lambda row: str(row.get("date") or ""))
        ]
        return OptionExpirationsResponse(
            symbol=fixture["symbol"],
            market=fixture["market"],
            expirations=expirations,
            asOf=fixture["chainAsOf"],
            source=fixture["source"],
            warnings=list(PHASE1_WARNING_CODES),
            metadata=self._metadata(force_refresh=force_refresh, fixture=fixture),
        )

    def get_chain(
        self,
        symbol: str,
        expiration: Optional[str] = None,
        side: str = "both",
        min_open_interest: Optional[int] = None,
        max_spread_pct: Optional[float] = None,
        include_greeks: bool = True,
        force_refresh: bool = False,
        market_data_provider: Optional[str] = None,
    ) -> OptionChainResponse:
        fixture = self._fixture_for_symbol(symbol, market_data_provider=market_data_provider)
        normalized_side = (side or "both").strip().lower()
        if normalized_side not in {"call", "put", "both"}:
            raise ValueError("side must be call, put, or both")

        contracts = list(self._contracts_for_fixture(fixture, include_greeks=include_greeks))
        if expiration:
            contracts = [contract for contract in contracts if contract.expiration == expiration]
        if min_open_interest is not None:
            contracts = [
                contract
                for contract in contracts
                if contract.open_interest is not None and contract.open_interest >= min_open_interest
            ]
        if max_spread_pct is not None:
            contracts = [
                contract
                for contract in contracts
                if contract.spread_pct is not None and contract.spread_pct <= max_spread_pct
            ]

        calls = [contract for contract in contracts if contract.side == "call" and normalized_side in {"call", "both"}]
        puts = [contract for contract in contracts if contract.side == "put" and normalized_side in {"put", "both"}]
        return OptionChainResponse(
            symbol=fixture["symbol"],
            market=fixture["market"],
            underlying=self._safe_underlying(fixture),
            expiration=expiration,
            calls=calls,
            puts=puts,
            filtersApplied={
                "expiration": expiration,
                "side": normalized_side,
                "minOpenInterest": min_open_interest,
                "maxSpreadPct": max_spread_pct,
                "includeGreeks": include_greeks,
                "forceRefresh": force_refresh,
            },
            chainAsOf=fixture["chainAsOf"],
            source=fixture["source"],
            warnings=list(PHASE1_WARNING_CODES),
            metadata=self._metadata(force_refresh=force_refresh, fixture=fixture),
        )

    def analyze(self, request: OptionsAnalyzeRequest | Dict[str, Any]) -> OptionsAnalyzeResponse:
        parsed = self._parse_analyze_request(request)
        fixture = self._fixture_for_symbol(parsed.symbol, market_data_provider=parsed.market_data_provider)
        contracts = list(self._contracts_for_fixture(fixture, include_greeks=True))
        target_date = self._parse_date(parsed.target_date)
        strategies = self._supported_strategies(parsed.strategies)
        candidate_sides = self._candidate_sides(parsed.direction, strategies)
        candidates: List[OptionCandidateContract] = []

        for contract in contracts:
            strategy = "long_call" if contract.side == "call" else "long_put"
            if contract.side not in candidate_sides or strategy not in strategies:
                continue
            premium_at_risk = self._premium_at_risk(contract)
            if parsed.max_premium is not None and premium_at_risk > parsed.max_premium:
                continue
            candidates.append(
                self._score_contract(
                    contract=contract,
                    strategy=strategy,
                    direction=parsed.direction,
                    target_price=parsed.target_price,
                    target_date=target_date,
                    max_premium=parsed.max_premium,
                    risk_profile=parsed.risk_profile,
                    underlying_price=float((fixture.get("underlying") or {}).get("price") or 0),
                )
            )

        candidates.sort(
            key=lambda candidate: (-candidate.score, candidate.contract.expiration, candidate.contract.strike)
        )
        calls = [contract for contract in contracts if contract.side == "call"]
        puts = [contract for contract in contracts if contract.side == "put"]
        return OptionsAnalyzeResponse(
            symbol=fixture["symbol"],
            underlying=self._safe_underlying(fixture),
            assumptions={
                "direction": parsed.direction,
                "targetPrice": parsed.target_price,
                "targetDate": parsed.target_date,
                "maxPremium": parsed.max_premium,
                "riskProfile": parsed.risk_profile,
                "strategies": list(parsed.strategies),
                "contractMultiplier": CONTRACT_MULTIPLIER,
            },
            optionChainSummary={
                "source": fixture["source"],
                "chainAsOf": fixture["chainAsOf"],
                "expirationCount": len(fixture.get("expirations") or []),
                "callCount": len(calls),
                "putCount": len(puts),
                "candidateCount": len(candidates),
            },
            candidateContracts=candidates,
            risks=list(PHASE3_RISKS),
            limitations=list(PHASE3_LIMITATIONS),
            metadata=self._metadata(
                force_refresh=parsed.force_refresh,
                fixture=fixture,
                scoring_engine=SCORING_MODEL_VERSION,
                strategy_engine=SCENARIO_MODEL_VERSION,
            ),
        )

    def scenario(self, request: OptionsScenarioRequest | Dict[str, Any]) -> OptionsScenarioResponse:
        parsed = self._parse_scenario_request(request)
        fixture = self._fixture_for_symbol(parsed.symbol, market_data_provider=parsed.market_data_provider)
        contracts = list(self._contracts_for_fixture(fixture, include_greeks=True))
        side = "call" if parsed.strategy == "long_call" else "put"
        contract = self._select_contract(
            contracts,
            side=side,
            contract_symbol=parsed.contract_symbol,
            expiration=parsed.expiration,
            strike=parsed.strike,
        )
        underlying_price = float((fixture.get("underlying") or {}).get("price") or 0)
        premium_at_risk = self._premium_at_risk(contract)
        breakeven = self._breakeven(contract)
        grid_prices = self._scenario_prices(underlying_price, parsed.target_price, parsed.custom_prices)
        rows = [
            self._payoff_row(
                label=label,
                terminal_price=price,
                contract=contract,
                premium_at_risk=premium_at_risk,
            )
            for label, price in grid_prices
        ]
        return OptionsScenarioResponse(
            symbol=fixture["symbol"],
            underlying=self._safe_underlying(fixture),
            strategy=parsed.strategy,
            contract=contract,
            expirationPayoffGrid=rows,
            risk=OptionScenarioRisk(
                premiumAtRisk=premium_at_risk,
                breakeven=breakeven,
                requiredMovePct=self._required_move_pct(underlying_price, breakeven),
                maxLoss=premium_at_risk,
            ),
            preExpirationTheoreticalPricing={
                "available": False,
                "reason": "phase3_expiration_payoff_only",
                "requiredInputs": ["pricing_model", "risk_free_rate", "dividends", "iv_surface", "time_to_expiration"],
            },
            limitations=list(PHASE3_LIMITATIONS),
            metadata=self._metadata(
                force_refresh=parsed.force_refresh,
                fixture=fixture,
                scoring_engine=SCORING_MODEL_VERSION,
                strategy_engine=SCENARIO_MODEL_VERSION,
            ),
        )

    def compare_strategies(
        self, request: OptionsStrategyCompareRequest | Dict[str, Any]
    ) -> OptionsStrategyCompareResponse:
        parsed = self._parse_strategy_compare_request(request)
        requested = self._validate_compare_strategies(parsed.strategies)
        fixture = self._fixture_for_symbol(parsed.symbol, market_data_provider=parsed.market_data_provider)
        contracts = list(self._contracts_for_fixture(fixture, include_greeks=True))
        underlying_price = float((fixture.get("underlying") or {}).get("price") or 0)
        target_date = self._parse_date(parsed.target_date)
        comparisons: List[OptionsStrategyComparison] = []

        for strategy in parsed.strategies:
            if strategy not in requested:
                continue
            comparison = self._build_strategy_comparison(
                strategy=strategy,
                contracts=contracts,
                direction=parsed.direction,
                target_price=parsed.target_price,
                target_date=target_date,
                max_premium=parsed.max_premium,
                risk_profile=parsed.risk_profile,
                underlying_price=underlying_price,
            )
            if comparison is not None:
                comparisons.append(comparison)

        return OptionsStrategyCompareResponse(
            symbol=fixture["symbol"],
            underlying=self._safe_underlying(fixture),
            assumptions={
                "direction": parsed.direction,
                "targetPrice": parsed.target_price,
                "targetDate": parsed.target_date,
                "maxPremium": parsed.max_premium,
                "riskProfile": parsed.risk_profile,
                "strategies": list(parsed.strategies),
                "contractMultiplier": CONTRACT_MULTIPLIER,
                "pricingMode": "expiration_intrinsic_minus_mid_debit",
            },
            strategies=comparisons,
            limitations=list(PHASE4_LIMITATIONS),
            metadata=self._metadata(
                force_refresh=parsed.force_refresh,
                fixture=fixture,
                scoring_engine=SCORING_MODEL_VERSION,
                strategy_engine=STRATEGY_COMPARE_MODEL_VERSION,
            ),
        )

    def evaluate_decision(self, request: OptionsDecisionRequest | Dict[str, Any]) -> OptionsDecisionResponse:
        parsed = self._parse_decision_request(request)
        fixture = self._fixture_for_symbol(parsed.symbol, market_data_provider=parsed.market_data_provider)
        contracts = list(self._contracts_for_fixture(fixture, include_greeks=True))
        if parsed.scenario_assumptions.get("omitGreeks"):
            contracts = [contract.model_copy(update={"greeks": None}) for contract in contracts]
        underlying_price = float((fixture.get("underlying") or {}).get("price") or 0)
        target_date = self._parse_date(parsed.target_date or parsed.expiration or str(date.today()))
        comparison = self._comparison_for_decision(
            parsed=parsed,
            contracts=contracts,
            underlying_price=underlying_price,
            target_date=target_date,
        )
        decision_contracts = self._contracts_for_decision(parsed, contracts, comparison)
        data_quality = self._decision_data_quality(fixture, decision_contracts)
        liquidity = self._decision_liquidity(decision_contracts)
        iv_greeks = self._decision_iv_greeks(fixture, decision_contracts)
        breakeven = self._decision_breakeven(
            strategy=parsed.strategy,
            comparison=comparison,
            contracts=decision_contracts,
            underlying_price=underlying_price,
            target_price=parsed.target_price,
        )
        risk_reward = self._decision_risk_reward(comparison, decision_contracts, parsed.risk_budget)
        expected_move = self._expected_move(fixture, contracts, decision_contracts, underlying_price)
        raw_score = (
            data_quality.data_quality_score * 0.25
            + liquidity.liquidity_score * 0.20
            + iv_greeks.iv_readiness * 0.20
            + breakeven.score * 0.15
            + risk_reward.score * 0.15
            + self._expected_move_score(expected_move, breakeven) * 0.05
        )
        score = self._apply_decision_caps(
            raw_score=raw_score,
            data_quality=data_quality,
            liquidity=liquidity,
            iv_greeks=iv_greeks,
            expected_move=expected_move,
            contracts=decision_contracts,
        )
        label = self._decision_label(score, data_quality)
        reasons, warnings = self._decision_reasons(
            data_quality,
            liquidity,
            iv_greeks,
            breakeven,
            risk_reward,
            expected_move,
        )
        alternative = self._decision_alternative(parsed, comparison, fixture, underlying_price, target_date)
        optimizer = self._strategy_optimizer(
            parsed=parsed,
            fixture=fixture,
            contracts=contracts,
            underlying_price=underlying_price,
            target_date=target_date,
            expected_move=expected_move,
        )
        underlying = self._safe_underlying(fixture)
        return OptionsDecisionResponse(
            symbol=fixture["symbol"],
            strategy=parsed.strategy,
            dataQuality=data_quality,
            liquidity=liquidity,
            ivGreeks=iv_greeks,
            ivRank=iv_greeks.iv_rank,
            ivPercentile=iv_greeks.iv_percentile,
            ivRankStatus=iv_greeks.iv_rank_status,
            expectedMove=expected_move,
            optimizer=optimizer,
            rankedAlternatives=optimizer.alternatives,
            breakeven=breakeven,
            riskReward=risk_reward,
            tradeQualityScore=score,
            decisionLabel=label,
            primaryReasons=reasons,
            riskWarnings=warnings,
            betterAlternative=alternative,
            noAdviceDisclosure=(
                "Analytical output under explicit assumptions only; not personalized financial advice "
                "and not an instruction to trade."
            ),
            freshness=OptionsDecisionFreshness(
                source=str(fixture.get("source") or "unknown"),
                freshness=str(underlying.get("freshness") or "unknown"),
                asOf=str(fixture.get("chainAsOf") or underlying.get("asOf") or ""),
            ),
            metadata=self._metadata(
                force_refresh=parsed.force_refresh,
                fixture=fixture,
                scoring_engine=DECISION_ENGINE_MODEL_VERSION,
                strategy_engine=DECISION_ENGINE_MODEL_VERSION,
            ),
        )

    def _comparison_for_decision(
        self,
        parsed: OptionsDecisionRequest,
        contracts: Sequence[OptionContract],
        underlying_price: float,
        target_date: date,
    ) -> OptionsStrategyComparison:
        if parsed.legs:
            selected = self._contracts_for_legs(parsed.legs, contracts, parsed.expiration)
            return self._comparison_from_selected_legs(parsed, selected, underlying_price)
        comparison = self._build_strategy_comparison(
            strategy=parsed.strategy,
            contracts=contracts,
            direction="bullish" if "call" in parsed.strategy else "bearish",
            target_price=float(parsed.target_price or underlying_price),
            target_date=target_date,
            max_premium=parsed.risk_budget,
            risk_profile="balanced",
            underlying_price=underlying_price,
        )
        if comparison is None:
            raise ValueError("No supported fixture contract matched the decision request.")
        return comparison

    def _comparison_from_selected_legs(
        self,
        parsed: OptionsDecisionRequest,
        contracts: Sequence[OptionContract],
        underlying_price: float,
    ) -> OptionsStrategyComparison:
        target_price = float(parsed.target_price or underlying_price)
        if parsed.strategy in {"long_call", "long_put"}:
            contract = contracts[0]
            net_debit = self._premium_at_risk(contract)
            breakeven = self._breakeven(contract)
            return OptionsStrategyComparison(
                strategyType=parsed.strategy,
                legs=[self._strategy_leg("buy", contract)],
                netDebit=net_debit,
                maxLoss=net_debit,
                maxGain=None,
                breakeven=breakeven,
                requiredMovePct=self._required_move_pct(underlying_price, breakeven),
                payoffAtTarget=round(self._expiration_net_payoff(contract, target_price, net_debit), 2),
                riskRewardRatio=None,
                liquidityWarnings=self._strategy_liquidity_warnings([contract]),
                ivThetaNotes=self._strategy_iv_theta_notes([contract]),
                suitabilityNotes=self._strategy_suitability_notes(parsed.strategy, "", ""),
                limitations=list(PHASE4_LIMITATIONS),
                noAdviceDisclosure=self._no_advice_disclosure(),
            )
        if len(contracts) < 2:
            raise ValueError("Defined-risk spread decision requires two supported legs.")
        long_leg = next((contract for leg, contract in zip(parsed.legs, contracts) if leg.action == "buy"), contracts[0])
        short_leg = next((contract for leg, contract in zip(parsed.legs, contracts) if leg.action == "sell"), contracts[1])
        long_mid = float(long_leg.mid if long_leg.mid is not None else long_leg.last or 0)
        short_mid = float(short_leg.mid if short_leg.mid is not None else short_leg.last or 0)
        net_debit = round((long_mid - short_mid) * CONTRACT_MULTIPLIER, 2)
        width = abs(long_leg.strike - short_leg.strike) * CONTRACT_MULTIPLIER
        max_gain = round(width - net_debit, 2)
        breakeven = (
            round(long_leg.strike + net_debit / CONTRACT_MULTIPLIER, 2)
            if long_leg.side == "call"
            else round(long_leg.strike - net_debit / CONTRACT_MULTIPLIER, 2)
        )
        return OptionsStrategyComparison(
            strategyType=parsed.strategy,
            legs=[self._strategy_leg("buy", long_leg), self._strategy_leg("sell", short_leg)],
            netDebit=net_debit,
            maxLoss=net_debit,
            maxGain=max_gain,
            breakeven=breakeven,
            requiredMovePct=self._required_move_pct(underlying_price, breakeven),
            payoffAtTarget=self._debit_spread_payoff(long_leg.side, long_leg, short_leg, target_price, net_debit),
            riskRewardRatio=round(max_gain / net_debit, 2) if net_debit > 0 and max_gain > 0 else None,
            liquidityWarnings=self._strategy_liquidity_warnings([long_leg, short_leg]),
            ivThetaNotes=self._strategy_iv_theta_notes([long_leg, short_leg]),
            suitabilityNotes=self._strategy_suitability_notes(parsed.strategy, "", ""),
            limitations=list(PHASE4_LIMITATIONS),
            noAdviceDisclosure=self._no_advice_disclosure(),
        )

    def _contracts_for_decision(
        self,
        parsed: OptionsDecisionRequest,
        contracts: Sequence[OptionContract],
        comparison: OptionsStrategyComparison,
    ) -> List[OptionContract]:
        if parsed.legs:
            return self._contracts_for_legs(parsed.legs, contracts, parsed.expiration)
        selected = []
        for leg in comparison.legs:
            match = next(
                (
                    contract
                    for contract in contracts
                    if contract.contract_symbol == leg.contract_symbol
                    and contract.side == leg.side
                    and contract.expiration == leg.expiration
                    and contract.strike == leg.strike
                ),
                None,
            )
            if match is not None:
                selected.append(match)
        if not selected:
            raise ValueError("No supported fixture contract matched the decision request.")
        return selected

    def _contracts_for_legs(
        self,
        legs: Sequence[OptionsDecisionLeg],
        contracts: Sequence[OptionContract],
        expiration: Optional[str],
    ) -> List[OptionContract]:
        selected = []
        for leg in legs:
            matches = [contract for contract in contracts if contract.side == leg.side]
            if leg.contract_symbol:
                matches = [contract for contract in matches if contract.contract_symbol == leg.contract_symbol]
            if leg.expiration or expiration:
                target_expiration = leg.expiration or expiration
                matches = [contract for contract in matches if contract.expiration == target_expiration]
            if leg.strike is not None:
                matches = [contract for contract in matches if contract.strike == leg.strike]
            if not matches:
                raise ValueError("No supported fixture contract matched the decision request.")
            selected.append(sorted(matches, key=lambda contract: (contract.expiration, contract.strike))[0])
        return selected

    def _decision_data_quality(
        self,
        fixture: Dict[str, Any],
        contracts: Sequence[OptionContract],
    ) -> OptionsDecisionDataQuality:
        underlying = self._safe_underlying(fixture)
        source_text = f"{fixture.get('source') or ''} {underlying.get('freshness') or ''}".lower()
        source_type = self._source_type(source_text)
        if source_type == "live":
            score = 90.0
            tier = "live_usable"
        elif source_type == "delayed":
            score = 70.0
            tier = "delayed_usable"
        elif source_type in {"synthetic", "fixture", "fallback"}:
            score = 25.0
            tier = "synthetic_demo_only"
        else:
            score = 45.0
            tier = "insufficient"
        blocking: List[str] = []
        warnings: List[str] = []
        if tier == "synthetic_demo_only":
            blocking.append("synthetic_or_fixture_data_not_decision_grade")
        if any(contract.bid is None or contract.ask is None for contract in contracts):
            blocking.append("missing_bid_ask")
            score -= 25
        if any(contract.implied_volatility is None for contract in contracts):
            warnings.append("missing_iv")
            score -= 12
        if any(contract.greeks is None for contract in contracts):
            warnings.append("missing_greeks")
            score -= 18
        if any(contract.volume is None for contract in contracts):
            warnings.append("missing_volume")
            score -= 10
        if any(contract.open_interest is None for contract in contracts):
            warnings.append("missing_open_interest")
            score -= 10
        if any(contract.strike <= 0 or contract.dte <= 0 or contract.expiration == "" for contract in contracts):
            blocking.append("invalid_strike_expiration_or_dte")
            score -= 25
        if not contracts:
            blocking.append("missing_contract_legs")
            score = 0
        if blocking and tier != "synthetic_demo_only":
            tier = "insufficient"
        return OptionsDecisionDataQuality(
            dataQualityScore=self._bounded(score),
            dataQualityTier=tier,
            sourceType=source_type,
            asOfAgeMinutes=self._as_of_age_minutes(str(fixture.get("chainAsOf") or "")),
            blockingReasons=blocking,
            warnings=warnings,
        )

    @staticmethod
    def _source_type(source_text: str) -> str:
        if "synthetic" in source_text:
            return "synthetic"
        if "fallback" in source_text:
            return "fallback"
        if "delayed" in source_text:
            return "delayed"
        if "fixture" in source_text or "mock" in source_text:
            return "fixture"
        if "live" in source_text:
            return "live"
        return "unknown"

    @staticmethod
    def _as_of_age_minutes(as_of: str) -> Optional[float]:
        if not as_of:
            return None
        try:
            parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            now = datetime.now(tz=parsed.tzinfo)
            return round(max(0.0, (now - parsed).total_seconds() / 60), 2)
        except ValueError:
            return None

    def _decision_liquidity(self, contracts: Sequence[OptionContract]) -> OptionsDecisionLiquidity:
        scores = [self._liquidity_score(contract) for contract in contracts]
        spread_values = [float(contract.spread_pct) for contract in contracts if contract.spread_pct is not None]
        spread_pct = round(max(spread_values), 2) if spread_values else None
        warnings: List[str] = []
        if spread_pct is None:
            warnings.append("missing_bid_ask_spread")
        elif spread_pct > 25:
            warnings.append("wide_bid_ask_spread")
        if any((contract.volume is None or contract.volume < 50) for contract in contracts):
            warnings.append("low_or_missing_volume")
        if any((contract.open_interest is None or contract.open_interest < 100) for contract in contracts):
            warnings.append("low_or_missing_open_interest")
        if any(contract.mid is None or contract.mid <= 0 for contract in contracts):
            warnings.append("invalid_mid_price")
        score = round(sum(scores) / len(scores), 2) if scores else 0
        if "wide_bid_ask_spread" in warnings:
            score = min(score, 55)
        return OptionsDecisionLiquidity(
            liquidityScore=self._bounded(score),
            spreadPct=spread_pct,
            liquidityWarnings=warnings,
        )

    def _decision_iv_greeks(self, fixture: Dict[str, Any], contracts: Sequence[OptionContract]) -> OptionsDecisionIvGreeks:
        iv_rank, iv_percentile, iv_rank_status, iv_rank_source, iv_rank_confidence, iv_warnings = self._iv_rank_snapshot(
            fixture,
            contracts,
        )
        warnings: List[str] = list(iv_warnings)
        iv_scores = []
        for contract in contracts:
            if contract.implied_volatility is None:
                warnings.append("missing_iv")
                iv_scores.append(25.0)
            elif not (0.01 <= float(contract.implied_volatility) <= 3.0):
                warnings.append("implausible_iv")
                iv_scores.append(35.0)
            else:
                iv_scores.append(self._iv_score(contract.implied_volatility))
            if contract.greeks is None:
                warnings.append("missing_greeks")
            else:
                missing = [
                    name
                    for name in ("delta", "theta", "gamma", "vega")
                    if getattr(contract.greeks, name) is None
                ]
                if missing:
                    warnings.append("missing_greeks")
                if abs(float(contract.greeks.theta or 0)) * CONTRACT_MULTIPLIER > 8:
                    warnings.append("high_theta_decay")
        if any(contract.greeks is None for contract in contracts):
            readiness = min(sum(iv_scores) / len(iv_scores) if iv_scores else 0, 45)
        else:
            readiness = sum(iv_scores) / len(iv_scores) if iv_scores else 0
        dte = min((contract.dte for contract in contracts), default=0)
        if dte <= 14:
            dte_bucket = "short"
        elif dte <= 60:
            dte_bucket = "standard"
        else:
            dte_bucket = "long"
        return OptionsDecisionIvGreeks(
            ivReadiness=self._bounded(readiness),
            ivRankStatus=iv_rank_status,
            ivRank=iv_rank,
            ivPercentile=iv_percentile,
            ivRankSource=iv_rank_source,
            ivRankConfidence=iv_rank_confidence,
            warnings=sorted(set(warnings)),
            dteBucket=dte_bucket,
        )

    def _iv_rank_snapshot(
        self,
        fixture: Dict[str, Any],
        contracts: Sequence[OptionContract],
    ) -> tuple[Optional[float], Optional[float], str, Optional[str], Optional[str], List[str]]:
        history = self._historical_iv_proxy(fixture)
        current_values = [
            float(contract.implied_volatility)
            for contract in contracts
            if contract.implied_volatility is not None and 0.01 <= float(contract.implied_volatility) <= 3.0
        ]
        if not history or not current_values:
            return None, None, "unavailable", None, None, ["iv_rank_unavailable"]
        current_iv = sum(current_values) / len(current_values)
        low = min(history)
        high = max(history)
        if high <= low:
            return None, None, "unavailable", "synthetic_fixture_proxy", "low", ["iv_rank_unavailable"]
        rank = self._bounded(((current_iv - low) / (high - low)) * 100)
        percentile = self._bounded((sum(1 for value in history if value <= current_iv) / len(history)) * 100)
        return (
            rank,
            percentile,
            "available",
            "synthetic_fixture_proxy",
            "test_only_low_confidence",
            ["iv_rank_proxy_fixture_only"],
        )

    @staticmethod
    def _historical_iv_proxy(fixture: Dict[str, Any]) -> List[float]:
        raw = fixture.get("historicalIvProxy") or fixture.get("historical_iv_proxy") or []
        values = []
        for item in raw:
            value = item.get("iv") if isinstance(item, dict) else item
            try:
                iv = float(value)
            except (TypeError, ValueError):
                continue
            if 0.01 <= iv <= 3.0:
                values.append(iv)
        return values

    def _decision_breakeven(
        self,
        strategy: str,
        comparison: OptionsStrategyComparison,
        contracts: Sequence[OptionContract],
        underlying_price: float,
        target_price: Optional[float],
    ) -> OptionsDecisionBreakeven:
        breakeven = comparison.breakeven
        required_move = self._required_move_pct(underlying_price, breakeven)
        status = "not_supplied"
        if target_price is not None:
            if strategy in {"long_call", "bull_call_spread"}:
                status = "target_above_breakeven" if target_price >= breakeven else "target_below_breakeven"
            else:
                status = "target_below_breakeven" if target_price <= breakeven else "target_above_breakeven"
        pressure = abs(required_move)
        score = self._bounded(100 - pressure * 2.8)
        if target_price is not None and status in {"target_below_breakeven"} and strategy in {"long_call", "bull_call_spread"}:
            score = min(score, 45)
        if target_price is not None and status == "target_above_breakeven" and strategy in {"long_put", "bear_put_spread"}:
            score = min(score, 45)
        return OptionsDecisionBreakeven(
            breakeven=breakeven,
            requiredMovePct=required_move,
            targetPriceStatus=status,
            score=score,
        )

    def _decision_risk_reward(
        self,
        comparison: OptionsStrategyComparison,
        contracts: Sequence[OptionContract],
        risk_budget: Optional[float],
    ) -> OptionsDecisionRiskReward:
        warnings: List[str] = []
        max_loss = comparison.max_loss
        max_gain = comparison.max_gain
        ratio = comparison.risk_reward_ratio
        if max_gain is None:
            warnings.append("max_gain_not_defined_for_long_option")
            score = 55.0
        else:
            score = self._bounded(45 + float(ratio or 0) * 22)
        if risk_budget is not None and max_loss > risk_budget:
            warnings.append("max_loss_exceeds_risk_budget")
            score = min(score, 40)
        if any(contract.mid is None or contract.mid <= 0 for contract in contracts):
            warnings.append("invalid_mid_price")
            score = min(score, 25)
        return OptionsDecisionRiskReward(
            maxLoss=max_loss,
            maxGain=max_gain,
            riskRewardRatio=ratio,
            score=score,
            warnings=warnings,
        )

    def _expected_move(
        self,
        fixture: Dict[str, Any],
        contracts: Sequence[OptionContract],
        decision_contracts: Sequence[OptionContract],
        underlying_price: float,
    ) -> OptionsExpectedMove:
        dte = min((contract.dte for contract in decision_contracts if contract.dte > 0), default=0)
        expiration = next((contract.expiration for contract in decision_contracts if contract.expiration), None)
        if underlying_price > 0 and expiration:
            same_expiration = [contract for contract in contracts if contract.expiration == expiration]
            atm_call = self._nearest_atm_contract(same_expiration, "call", underlying_price)
            atm_put = self._nearest_atm_contract(same_expiration, "put", underlying_price)
            if atm_call is not None and atm_put is not None:
                call_mid = float(atm_call.mid or 0)
                put_mid = float(atm_put.mid or 0)
                if call_mid > 0 and put_mid > 0:
                    move = round(call_mid + put_mid, 2)
                    return OptionsExpectedMove(
                        expectedMoveAbs=move,
                        expectedMovePct=self._expected_move_pct(move, underlying_price),
                        expectedMoveSource="straddle_mid",
                        expectedMoveWarnings=["expected_move_uses_fixture_mid_prices"],
                    )
        iv_values = [
            float(contract.implied_volatility)
            for contract in decision_contracts
            if contract.implied_volatility is not None and 0.01 <= float(contract.implied_volatility) <= 3.0
        ]
        if underlying_price > 0 and dte > 0 and iv_values:
            avg_iv = sum(iv_values) / len(iv_values)
            move = round(underlying_price * avg_iv * math.sqrt(dte / 365), 2)
            return OptionsExpectedMove(
                expectedMoveAbs=move,
                expectedMovePct=self._expected_move_pct(move, underlying_price),
                expectedMoveSource="iv_dte",
                expectedMoveWarnings=["expected_move_uses_iv_dte_estimate"],
            )
        return OptionsExpectedMove(
            expectedMoveAbs=None,
            expectedMovePct=None,
            expectedMoveSource="unavailable",
            expectedMoveWarnings=["expected_move_unavailable", "confidence_reduced_without_expected_move"],
        )

    @staticmethod
    def _nearest_atm_contract(
        contracts: Sequence[OptionContract],
        side: str,
        underlying_price: float,
    ) -> Optional[OptionContract]:
        candidates = [contract for contract in contracts if contract.side == side]
        if not candidates:
            return None
        return sorted(candidates, key=lambda contract: (abs(contract.strike - underlying_price), contract.strike))[0]

    @staticmethod
    def _expected_move_pct(expected_move_abs: float, underlying_price: float) -> Optional[float]:
        if underlying_price <= 0:
            return None
        return round((expected_move_abs / underlying_price) * 100, 2)

    def _expected_move_score(
        self,
        expected_move: OptionsExpectedMove,
        breakeven: OptionsDecisionBreakeven,
    ) -> float:
        if expected_move.expected_move_source == "unavailable" or expected_move.expected_move_pct is None:
            return 35.0
        pressure = abs(float(breakeven.required_move_pct or 0))
        if pressure <= float(expected_move.expected_move_pct):
            return self._bounded(75 + (float(expected_move.expected_move_pct) - pressure) * 1.4)
        return self._bounded(70 - (pressure - float(expected_move.expected_move_pct)) * 3.2)

    def _strategy_optimizer(
        self,
        parsed: OptionsDecisionRequest,
        fixture: Dict[str, Any],
        contracts: Sequence[OptionContract],
        underlying_price: float,
        target_date: date,
        expected_move: OptionsExpectedMove,
    ) -> OptionsDecisionOptimizer:
        candidates: List[OptionsOptimizerAlternative] = []
        for strategy in ("long_call", "long_put", "bull_call_spread", "bear_put_spread"):
            comparison = self._build_strategy_comparison(
                strategy=strategy,
                contracts=contracts,
                direction="bullish" if "call" in strategy else "bearish",
                target_price=float(parsed.target_price or underlying_price),
                target_date=target_date,
                max_premium=parsed.risk_budget,
                risk_profile="balanced",
                underlying_price=underlying_price,
            )
            if comparison is None:
                continue
            candidate_contracts = self._contracts_for_decision(
                parsed.model_copy(update={"strategy": strategy, "legs": []}),
                contracts,
                comparison,
            )
            candidate = self._optimizer_candidate(
                strategy=strategy,
                fixture=fixture,
                contracts=candidate_contracts,
                comparison=comparison,
                underlying_price=underlying_price,
                target_price=parsed.target_price,
                risk_budget=parsed.risk_budget,
                expected_move=expected_move,
            )
            candidates.append(candidate)

        ranked = sorted(
            candidates,
            key=lambda item: (
                -item.trade_quality_score,
                item.max_loss if item.max_loss is not None else 999999,
                item.strategy_key,
            ),
        )
        viable = [item for item in ranked if item.trade_quality_score >= 55 and item.decision_label not in {"数据不足，禁止判断", "不建议"}]
        preferred = viable[0] if viable else None
        label = self._optimizer_label(ranked, preferred)
        no_trade_reason = None if preferred else self._no_trade_reason(ranked)
        return OptionsDecisionOptimizer(
            preferredStrategyKey=preferred.strategy_key if preferred and label != "不建议交易" else None,
            optimizerLabel=label,
            alternatives=ranked,
            noTradeReason=no_trade_reason,
        )

    def _optimizer_candidate(
        self,
        strategy: str,
        fixture: Dict[str, Any],
        contracts: Sequence[OptionContract],
        comparison: OptionsStrategyComparison,
        underlying_price: float,
        target_price: Optional[float],
        risk_budget: Optional[float],
        expected_move: OptionsExpectedMove,
    ) -> OptionsOptimizerAlternative:
        data_quality = self._decision_data_quality(fixture, contracts)
        liquidity = self._decision_liquidity(contracts)
        iv_greeks = self._decision_iv_greeks(fixture, contracts)
        breakeven = self._decision_breakeven(strategy, comparison, contracts, underlying_price, target_price)
        risk_reward = self._decision_risk_reward(comparison, contracts, risk_budget)
        alignment = self._expected_move_score(expected_move, breakeven)
        raw_score = (
            data_quality.data_quality_score * 0.23
            + liquidity.liquidity_score * 0.18
            + iv_greeks.iv_readiness * 0.17
            + breakeven.score * 0.14
            + risk_reward.score * 0.20
            + alignment * 0.08
        )
        score = self._apply_decision_caps(raw_score, data_quality, liquidity, iv_greeks, expected_move, contracts)
        label = self._decision_label(score, data_quality)
        reasons, warnings = self._decision_reasons(
            data_quality,
            liquidity,
            iv_greeks,
            breakeven,
            risk_reward,
            expected_move,
        )
        if alignment < 45:
            warnings.append("expected_move_does_not_cover_breakeven_pressure")
        return OptionsOptimizerAlternative(
            strategyKey=strategy,
            dataQualityTier=data_quality.data_quality_tier,
            liquidityScore=liquidity.liquidity_score,
            breakevenPressure=abs(breakeven.required_move_pct) if breakeven.required_move_pct is not None else None,
            maxLoss=risk_reward.max_loss,
            maxGain=risk_reward.max_gain,
            riskRewardRatio=risk_reward.risk_reward_ratio,
            expectedMoveAlignment=alignment,
            ivReadiness=iv_greeks.iv_readiness,
            tradeQualityScore=score,
            decisionLabel=label,
            primaryReasons=reasons,
            riskWarnings=list(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _optimizer_label(
        ranked: Sequence[OptionsOptimizerAlternative],
        preferred: Optional[OptionsOptimizerAlternative],
    ) -> str:
        if not ranked or all(item.decision_label == "数据不足，禁止判断" for item in ranked):
            return "数据不足，禁止判断"
        if preferred is None:
            best_score = max((item.trade_quality_score for item in ranked), default=0)
            return "仅观察" if best_score >= 45 else "不建议交易"
        if preferred.decision_label == "有条件可交易":
            return "有条件可交易"
        return "可关注替代结构"

    @staticmethod
    def _no_trade_reason(ranked: Sequence[OptionsOptimizerAlternative]) -> str:
        if not ranked:
            return "no_supported_strategy_candidates"
        if all(item.decision_label == "数据不足，禁止判断" for item in ranked):
            return "data_quality_not_decision_grade"
        return "all_candidates_have_weak_edge_or_unfavorable_risk_reward"

    def _apply_decision_caps(
        self,
        raw_score: float,
        data_quality: OptionsDecisionDataQuality,
        liquidity: OptionsDecisionLiquidity,
        iv_greeks: OptionsDecisionIvGreeks,
        expected_move: OptionsExpectedMove,
        contracts: Sequence[OptionContract],
    ) -> float:
        score = self._bounded(raw_score)
        if data_quality.data_quality_tier == "insufficient":
            score = min(score, 40)
        if data_quality.data_quality_tier == "synthetic_demo_only":
            score = min(score, 35)
        if data_quality.data_quality_tier == "delayed_usable":
            score = min(score, 75)
        if (liquidity.spread_pct or 0) > 25:
            score = min(score, 60)
        if "missing_greeks" in iv_greeks.warnings:
            score = min(score, 65)
        if iv_greeks.iv_rank_status == "unavailable":
            score = min(score, 72)
        if expected_move.expected_move_source == "unavailable":
            score = min(score, 68)
        if any(contract.volume is None or contract.open_interest is None for contract in contracts):
            score = min(score, 60)
        return round(score, 2)

    @staticmethod
    def _decision_label(score: float, data_quality: OptionsDecisionDataQuality) -> str:
        if data_quality.data_quality_tier in {"insufficient", "synthetic_demo_only"}:
            return "数据不足，禁止判断"
        if score < 45:
            return "不建议"
        if score < 65:
            return "仅观察"
        if data_quality.data_quality_tier == "delayed_usable":
            return "高风险，仅小仓验证"
        if score < 78:
            return "高风险，仅小仓验证"
        return "有条件可交易"

    @staticmethod
    def _decision_reasons(
        data_quality: OptionsDecisionDataQuality,
        liquidity: OptionsDecisionLiquidity,
        iv_greeks: OptionsDecisionIvGreeks,
        breakeven: OptionsDecisionBreakeven,
        risk_reward: OptionsDecisionRiskReward,
        expected_move: OptionsExpectedMove,
    ) -> tuple[List[str], List[str]]:
        reasons: List[str] = []
        warnings: List[str] = []
        if data_quality.data_quality_tier == "synthetic_demo_only":
            reasons.append("当前为 synthetic delayed / 演示数据")
            warnings.append("不可用于真实交易判断")
        if data_quality.blocking_reasons:
            reasons.extend(data_quality.blocking_reasons)
        if "wide_bid_ask_spread" in liquidity.liquidity_warnings:
            warnings.append("wide_bid_ask_spread")
        if "missing_greeks" in iv_greeks.warnings:
            reasons.append("Greeks 缺失，无法评估时间价值与敏感度")
            warnings.append("missing_greeks_degrade_confidence")
        if iv_greeks.iv_rank_status == "unavailable":
            reasons.append("IV Rank 不可用，波动率位置置信度不足")
            warnings.append("iv_rank_unavailable_degrade_confidence")
        if expected_move.expected_move_source == "unavailable":
            warnings.append("expected_move_unavailable_degrade_confidence")
        if breakeven.required_move_pct is not None and abs(breakeven.required_move_pct) > 12:
            warnings.append("breakeven_requires_large_underlying_move")
        warnings.extend(risk_reward.warnings)
        return list(dict.fromkeys(reasons or ["数据质量、流动性与风险回报需同时复核"])), list(dict.fromkeys(warnings))

    def _decision_alternative(
        self,
        parsed: OptionsDecisionRequest,
        current: OptionsStrategyComparison,
        fixture: Dict[str, Any],
        underlying_price: float,
        target_date: date,
    ) -> Optional[OptionsDecisionAlternative]:
        contracts = list(self._contracts_for_fixture(fixture, include_greeks=True))
        alternatives = []
        for strategy in SUPPORTED_COMPARE_STRATEGIES - {parsed.strategy}:
            comparison = self._build_strategy_comparison(
                strategy=strategy,
                contracts=contracts,
                direction="bullish" if "call" in strategy else "bearish",
                target_price=float(parsed.target_price or underlying_price),
                target_date=target_date,
                max_premium=parsed.risk_budget,
                risk_profile="balanced",
                underlying_price=underlying_price,
            )
            if comparison is None:
                continue
            lower_loss = comparison.max_loss < current.max_loss
            defined_gain = comparison.max_gain is not None and current.max_gain is None
            better_ratio = (
                comparison.risk_reward_ratio is not None
                and (current.risk_reward_ratio is None or comparison.risk_reward_ratio > current.risk_reward_ratio)
            )
            if lower_loss or defined_gain or better_ratio:
                alternatives.append(comparison)
        if not alternatives:
            return None
        best = sorted(alternatives, key=lambda item: (item.max_loss, -(item.risk_reward_ratio or 0)))[0]
        return OptionsDecisionAlternative(
            strategyType=best.strategy_type,
            reason="定义风险结构或更低权利金暴露可能降低单合约风险",
            maxLoss=best.max_loss,
            riskRewardRatio=best.risk_reward_ratio,
        )

    def _fixture_for_symbol(self, symbol: str, market_data_provider: Optional[str] = None) -> Dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        if not self._is_us_equity_symbol(normalized):
            raise OptionsLabUnsupportedSymbol(normalized)
        provider = self._provider_for_request(market_data_provider)
        try:
            fixture = provider.get_chain(normalized)
        except OptionsProviderUnsupportedSymbol as exc:
            raise OptionsLabUnsupportedSymbol(exc.symbol, code=exc.code) from exc
        except OptionsProviderUnavailable as exc:
            raise OptionsLabProviderUnavailable(exc.provider_name, code=exc.code) from exc
        except OptionsProviderError as exc:
            raise OptionsLabProviderUnavailable(market_data_provider or self.provider_name, code=exc.code) from exc
        if str(fixture.get("symbol") or "").upper() != normalized:
            raise OptionsLabUnsupportedSymbol(normalized)
        return fixture

    def _provider_for_request(self, market_data_provider: Optional[str]) -> OptionsMarketDataProvider:
        if not market_data_provider or market_data_provider == self.market_data_provider.provider_name:
            return self.market_data_provider
        try:
            return create_options_market_data_provider(
                provider_name=market_data_provider,
                fixture_path=self.fixture_path,
            )
        except OptionsProviderUnavailable as exc:
            raise OptionsLabProviderUnavailable(exc.provider_name, code=exc.code) from exc

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return re.sub(r"\s+", "", str(symbol or "")).upper()

    @staticmethod
    def _is_us_equity_symbol(symbol: str) -> bool:
        return bool(re.fullmatch(r"[A-Z]{1,5}", symbol))

    @staticmethod
    def _metadata(
        force_refresh: bool = False,
        fixture: Optional[Dict[str, Any]] = None,
        scoring_engine: str = "not_implemented_until_scoring_phase",
        strategy_engine: str = "not_implemented_until_later_phase",
    ) -> OptionsMetadata:
        capabilities = dict((fixture or {}).get("providerCapabilities") or {})
        provider_name = str((fixture or {}).get("providerName") or DEFAULT_OPTIONS_PROVIDER_NAME)
        return OptionsMetadata(
            forceRefreshIgnored=bool(force_refresh),
            scoringEngine=scoring_engine,
            strategyEngine=strategy_engine,
            providerName=provider_name,
            providerCapabilities=capabilities,
            liveProviderEnabled=bool(capabilities.get("liveEnabled", False)),
        )

    @staticmethod
    def _safe_underlying(fixture: Dict[str, Any]) -> Dict[str, Any]:
        underlying = copy.deepcopy(fixture.get("underlying") or {})
        return {
            "price": underlying.get("price"),
            "changePct": underlying.get("changePct"),
            "source": underlying.get("source") or fixture.get("source") or "unknown",
            "asOf": underlying.get("asOf") or fixture.get("chainAsOf"),
            "freshness": underlying.get("freshness") or "synthetic_delayed",
            "providerQuality": underlying.get("providerQuality") or fixture.get("providerQuality"),
        }

    def _contracts_for_fixture(self, fixture: Dict[str, Any], include_greeks: bool) -> Iterable[OptionContract]:
        expiration_dte = {str(item["date"]): int(item["dte"]) for item in fixture.get("expirations") or []}
        underlying_price = float((fixture.get("underlying") or {}).get("price") or 0)
        for item in sorted(
            fixture.get("contracts") or [],
            key=lambda row: (
                str(row.get("expiration") or ""),
                str(row.get("side") or ""),
                float(row.get("strike") or 0),
            ),
        ):
            bid = self._float_or_none(item.get("bid"))
            ask = self._float_or_none(item.get("ask"))
            mid = self._mid(bid, ask)
            spread_pct = self._spread_pct(bid, ask, mid)
            expiration = str(item.get("expiration") or "")
            yield OptionContract(
                symbol=fixture["symbol"],
                contractSymbol=str(item.get("contractSymbol") or ""),
                side=str(item.get("side") or "").lower(),
                expiration=expiration,
                strike=float(item.get("strike") or 0),
                multiplier=int(item.get("multiplier") or fixture.get("multiplier") or CONTRACT_MULTIPLIER),
                bid=bid,
                ask=ask,
                mid=mid,
                last=self._float_or_none(item.get("last")),
                volume=self._int_or_none(item.get("volume")),
                openInterest=self._int_or_none(item.get("openInterest")),
                impliedVolatility=self._float_or_none(item.get("impliedVolatility")),
                greeks=(
                    OptionGreeks(**dict(item.get("greeks") or {}))
                    if include_greeks and item.get("greeks")
                    else None
                ),
                dte=expiration_dte.get(expiration, 0),
                moneyness=self._moneyness(
                    str(item.get("side") or ""),
                    float(item.get("strike") or 0),
                    underlying_price,
                ),
                spreadPct=spread_pct,
                liquidityBucket=self._liquidity_bucket(spread_pct, self._int_or_none(item.get("openInterest"))),
                asOf=fixture["chainAsOf"],
                source=str(item.get("source") or fixture["source"]),
                freshness=str(item.get("freshness") or (fixture.get("underlying") or {}).get("freshness") or "unknown"),
                providerQuality=item.get("providerQuality") or fixture.get("providerQuality"),
                dataQuality=dict(item.get("dataQuality") or fixture.get("dataQuality") or {}),
                warnings=list(
                    dict.fromkeys(
                        list(item.get("warnings") or [])
                        + [
                            "delayed_or_stale_data_possible",
                        ]
                    )
                ),
            )

    @staticmethod
    def _float_or_none(value: Any) -> Optional[float]:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _int_or_none(value: Any) -> Optional[int]:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _mid(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
        if bid is None or ask is None:
            return None
        return round((bid + ask) / 2, 4)

    @staticmethod
    def _spread_pct(bid: Optional[float], ask: Optional[float], mid: Optional[float]) -> Optional[float]:
        if bid is None or ask is None or mid in (None, 0):
            return None
        return round(((ask - bid) / mid) * 100, 2)

    @staticmethod
    def _moneyness(side: str, strike: float, underlying_price: float) -> str:
        if not strike or not underlying_price:
            return "unknown"
        if abs(strike - underlying_price) / underlying_price <= 0.03:
            return "atm"
        normalized_side = side.lower()
        if normalized_side == "call":
            return "itm" if strike < underlying_price else "otm"
        if normalized_side == "put":
            return "itm" if strike > underlying_price else "otm"
        return "unknown"

    @staticmethod
    def _liquidity_bucket(spread_pct: Optional[float], open_interest: Optional[int]) -> str:
        if spread_pct is None or open_interest is None:
            return "unknown"
        if spread_pct <= 10 and open_interest >= 500:
            return "tight"
        if spread_pct <= 25 and open_interest >= 100:
            return "moderate"
        return "thin"

    @staticmethod
    def _parse_analyze_request(request: OptionsAnalyzeRequest | Dict[str, Any]) -> OptionsAnalyzeRequest:
        if isinstance(request, OptionsAnalyzeRequest):
            return request
        return OptionsAnalyzeRequest.model_validate(request)

    @staticmethod
    def _parse_scenario_request(request: OptionsScenarioRequest | Dict[str, Any]) -> OptionsScenarioRequest:
        if isinstance(request, OptionsScenarioRequest):
            return request
        return OptionsScenarioRequest.model_validate(request)

    @staticmethod
    def _parse_strategy_compare_request(
        request: OptionsStrategyCompareRequest | Dict[str, Any]
    ) -> OptionsStrategyCompareRequest:
        if isinstance(request, OptionsStrategyCompareRequest):
            return request
        return OptionsStrategyCompareRequest.model_validate(request)

    @staticmethod
    def _parse_decision_request(request: OptionsDecisionRequest | Dict[str, Any]) -> OptionsDecisionRequest:
        if isinstance(request, OptionsDecisionRequest):
            return request
        return OptionsDecisionRequest.model_validate(request)

    @staticmethod
    def _validate_compare_strategies(strategies: Sequence[str]) -> set[str]:
        requested = set(strategies or ["long_call", "long_put", "bull_call_spread", "bear_put_spread"])
        if not requested or requested - SUPPORTED_COMPARE_STRATEGIES:
            raise ValueError("Unsupported strategy requested for Options Lab Phase 4.")
        return requested

    @staticmethod
    def _supported_strategies(strategies: Sequence[str]) -> set[str]:
        requested = set(strategies or ["long_call", "long_put"])
        return requested & {"long_call", "long_put"}

    @staticmethod
    def _candidate_sides(direction: str, strategies: set[str]) -> set[str]:
        if direction == "bullish":
            return {"call"} if "long_call" in strategies else set()
        if direction == "bearish":
            return {"put"} if "long_put" in strategies else set()
        if direction == "volatility":
            sides = set()
            if "long_call" in strategies:
                sides.add("call")
            if "long_put" in strategies:
                sides.add("put")
            return sides
        return set()

    @staticmethod
    def _parse_date(value: str) -> date:
        return datetime.strptime(str(value), "%Y-%m-%d").date()

    def _score_contract(
        self,
        contract: OptionContract,
        strategy: str,
        direction: str,
        target_price: float,
        target_date: date,
        max_premium: Optional[float],
        risk_profile: str,
        underlying_price: float,
    ) -> OptionCandidateContract:
        premium_at_risk = self._premium_at_risk(contract)
        breakeven = self._breakeven(contract)
        target_payoff = self._expiration_net_payoff(contract, target_price, premium_at_risk)
        required_move_pct = self._required_move_pct(underlying_price, breakeven)
        sub_scores = OptionScoringSubScores(
            directionalFit=self._directional_fit(contract.side, direction),
            deltaFit=self._delta_fit(contract, risk_profile),
            breakevenDifficulty=self._breakeven_score(contract, target_price, breakeven),
            premiumEfficiency=self._premium_efficiency(target_payoff, premium_at_risk),
            liquidityScore=self._liquidity_score(contract),
            spreadPenalty=self._spread_score(contract.spread_pct),
            ivRisk=self._iv_score(contract.implied_volatility),
            thetaRisk=self._theta_score(contract, premium_at_risk),
            dteFit=self._dte_fit(contract, target_date),
            targetScenarioPayoff=self._target_payoff_score(target_payoff, premium_at_risk),
            maxLossBudgetFit=self._budget_fit(premium_at_risk, max_premium),
            oiVolumeConfidence=self._oi_volume_confidence(contract),
            dataFreshnessConfidence=100,
        )
        score = self._weighted_score(sub_scores)
        grade = self._grade_label(score)
        return OptionCandidateContract(
            strategy=strategy,
            contract=contract,
            score=score,
            gradeLabel=grade,
            premiumAtRisk=premium_at_risk,
            breakeven=breakeven,
            requiredMovePct=required_move_pct,
            targetPayoff=round(target_payoff, 2),
            scoring=OptionContractScoring(
                subScores=sub_scores,
                gradeLabel=grade,
                topPositiveDrivers=self._positive_drivers(sub_scores),
                topRiskDrivers=self._risk_drivers(sub_scores),
                assumptionsUsed={
                    "direction": direction,
                    "targetPrice": target_price,
                    "targetDate": target_date.isoformat(),
                    "riskProfile": risk_profile,
                    "contractMultiplier": CONTRACT_MULTIPLIER,
                    "pricingMode": "expiration_intrinsic_minus_mid_premium",
                },
                dataConfidence=self._data_confidence(sub_scores),
                notAdviceDisclosure=(
                    "Analytical ranking under explicit assumptions only; "
                    "not investment advice or an instruction."
                ),
            ),
        )

    @staticmethod
    def _premium_at_risk(contract: OptionContract) -> float:
        mid = contract.mid if contract.mid is not None else contract.last
        return round(float(mid or 0) * CONTRACT_MULTIPLIER, 2)

    @staticmethod
    def _breakeven(contract: OptionContract) -> float:
        mid = float(contract.mid if contract.mid is not None else contract.last or 0)
        if contract.side == "call":
            return round(contract.strike + mid, 2)
        return round(contract.strike - mid, 2)

    @staticmethod
    def _required_move_pct(underlying_price: float, breakeven: float) -> float:
        if not underlying_price:
            return 0
        return round(((breakeven - underlying_price) / underlying_price) * 100, 2)

    @staticmethod
    def _expiration_net_payoff(contract: OptionContract, terminal_price: float, premium_at_risk: float) -> float:
        if contract.side == "call":
            gross = max(0.0, terminal_price - contract.strike) * CONTRACT_MULTIPLIER
        else:
            gross = max(0.0, contract.strike - terminal_price) * CONTRACT_MULTIPLIER
        return gross - premium_at_risk

    @staticmethod
    def _directional_fit(side: str, direction: str) -> float:
        if (direction == "bullish" and side == "call") or (direction == "bearish" and side == "put"):
            return 100
        if direction == "volatility":
            return 70
        return 40

    @classmethod
    def _delta_fit(cls, contract: OptionContract, risk_profile: str) -> float:
        delta = abs((contract.greeks.delta if contract.greeks else 0) or 0)
        ideal = {"conservative": 0.55, "balanced": 0.42, "aggressive": 0.28}.get(risk_profile, 0.42)
        return cls._bounded(100 - abs(delta - ideal) * 180)

    @classmethod
    def _breakeven_score(cls, contract: OptionContract, target_price: float, breakeven: float) -> float:
        if contract.side == "call":
            if target_price >= breakeven:
                return cls._bounded(75 + min((target_price - breakeven) * 4, 25))
            return cls._bounded(75 - (breakeven - target_price) * 8)
        if target_price <= breakeven:
            return cls._bounded(75 + min((breakeven - target_price) * 4, 25))
        return cls._bounded(75 - (target_price - breakeven) * 8)

    @classmethod
    def _premium_efficiency(cls, target_payoff: float, premium_at_risk: float) -> float:
        if premium_at_risk <= 0:
            return 0
        return cls._bounded(45 + (target_payoff / premium_at_risk) * 25)

    @classmethod
    def _liquidity_score(cls, contract: OptionContract) -> float:
        spread = cls._spread_score(contract.spread_pct)
        oi = min(float(contract.open_interest or 0) / 1000 * 100, 100)
        volume = min(float(contract.volume or 0) / 300 * 100, 100)
        return round(spread * 0.45 + oi * 0.35 + volume * 0.2, 2)

    @classmethod
    def _spread_score(cls, spread_pct: Optional[float]) -> float:
        if spread_pct is None:
            return 35
        return cls._bounded(100 - float(spread_pct) * 2)

    @classmethod
    def _iv_score(cls, iv: Optional[float]) -> float:
        if iv is None:
            return 55
        return cls._bounded(100 - max(0.0, float(iv) - 0.45) * 130)

    @classmethod
    def _theta_score(cls, contract: OptionContract, premium_at_risk: float) -> float:
        theta = abs((contract.greeks.theta if contract.greeks else 0) or 0) * CONTRACT_MULTIPLIER
        if premium_at_risk <= 0:
            return 50
        daily_decay_pct = theta / premium_at_risk * 100
        return cls._bounded(100 - daily_decay_pct * 16)

    @classmethod
    def _dte_fit(cls, contract: OptionContract, target_date: date) -> float:
        expiration = cls._parse_date(contract.expiration)
        if expiration < target_date:
            days_short = (target_date - expiration).days
            return cls._bounded(35 - days_short * 0.5)
        buffer_days = (expiration - target_date).days
        return cls._bounded(100 - buffer_days * 0.35)

    @classmethod
    def _target_payoff_score(cls, target_payoff: float, premium_at_risk: float) -> float:
        if premium_at_risk <= 0:
            return 0
        return cls._bounded(50 + (target_payoff / premium_at_risk) * 22)

    @classmethod
    def _budget_fit(cls, premium_at_risk: float, max_premium: Optional[float]) -> float:
        if max_premium is None:
            return 100
        if max_premium <= 0:
            return 0
        return cls._bounded(100 - max(0.0, premium_at_risk - max_premium) / max_premium * 100)

    @classmethod
    def _oi_volume_confidence(cls, contract: OptionContract) -> float:
        oi = min(float(contract.open_interest or 0) / 750 * 100, 100)
        volume = min(float(contract.volume or 0) / 200 * 100, 100)
        return round(oi * 0.6 + volume * 0.4, 2)

    @staticmethod
    def _weighted_score(sub_scores: OptionScoringSubScores) -> float:
        weights = {
            "directional_fit": 0.12,
            "delta_fit": 0.08,
            "breakeven_difficulty": 0.10,
            "premium_efficiency": 0.10,
            "liquidity_score": 0.12,
            "spread_penalty": 0.08,
            "iv_risk": 0.06,
            "theta_risk": 0.06,
            "dte_fit": 0.08,
            "target_scenario_payoff": 0.12,
            "max_loss_budget_fit": 0.04,
            "oi_volume_confidence": 0.03,
            "data_freshness_confidence": 0.01,
        }
        raw = sum(float(getattr(sub_scores, key)) * weight for key, weight in weights.items())
        return round(max(0.0, min(100.0, raw)), 2)

    @staticmethod
    def _grade_label(score: float) -> str:
        if score >= 80:
            return "A"
        if score >= 65:
            return "B"
        if score >= 50:
            return "C"
        return "D"

    @staticmethod
    def _positive_drivers(sub_scores: OptionScoringSubScores) -> List[str]:
        rows = [
            ("directional_fit", sub_scores.directional_fit),
            ("target_scenario_payoff", sub_scores.target_scenario_payoff),
            ("liquidity_score", sub_scores.liquidity_score),
            ("premium_efficiency", sub_scores.premium_efficiency),
            ("dte_fit", sub_scores.dte_fit),
        ]
        return [name for name, _score in sorted(rows, key=lambda row: row[1], reverse=True)[:3]]

    @staticmethod
    def _risk_drivers(sub_scores: OptionScoringSubScores) -> List[str]:
        rows = [
            ("breakeven_difficulty", sub_scores.breakeven_difficulty),
            ("spread_penalty", sub_scores.spread_penalty),
            ("iv_risk", sub_scores.iv_risk),
            ("theta_risk", sub_scores.theta_risk),
            ("oi_volume_confidence", sub_scores.oi_volume_confidence),
            ("dte_fit", sub_scores.dte_fit),
        ]
        return [name for name, _score in sorted(rows, key=lambda row: row[1])[:3]]

    @staticmethod
    def _data_confidence(sub_scores: OptionScoringSubScores) -> str:
        average = (
            sub_scores.liquidity_score
            + sub_scores.oi_volume_confidence
            + sub_scores.data_freshness_confidence
        ) / 3
        if average >= 75:
            return "high"
        if average >= 50:
            return "moderate"
        return "low"

    @staticmethod
    def _bounded(value: float) -> float:
        return round(max(0.0, min(100.0, value)), 2)

    @staticmethod
    def _select_contract(
        contracts: Sequence[OptionContract],
        side: str,
        contract_symbol: Optional[str],
        expiration: Optional[str],
        strike: Optional[float],
    ) -> OptionContract:
        filtered = [contract for contract in contracts if contract.side == side]
        if contract_symbol:
            filtered = [contract for contract in filtered if contract.contract_symbol == contract_symbol]
        if expiration:
            filtered = [contract for contract in filtered if contract.expiration == expiration]
        if strike is not None:
            filtered = [contract for contract in filtered if contract.strike == strike]
        if not filtered:
            raise ValueError("No supported fixture contract matched the scenario request.")
        return sorted(filtered, key=lambda contract: (contract.expiration, contract.strike))[0]

    def _build_strategy_comparison(
        self,
        strategy: str,
        contracts: Sequence[OptionContract],
        direction: str,
        target_price: float,
        target_date: date,
        max_premium: Optional[float],
        risk_profile: str,
        underlying_price: float,
    ) -> Optional[OptionsStrategyComparison]:
        if strategy == "long_call":
            return self._long_option_comparison(
                strategy=strategy,
                side="call",
                contracts=contracts,
                direction=direction,
                target_price=target_price,
                target_date=target_date,
                max_premium=max_premium,
                risk_profile=risk_profile,
                underlying_price=underlying_price,
            )
        if strategy == "long_put":
            return self._long_option_comparison(
                strategy=strategy,
                side="put",
                contracts=contracts,
                direction=direction,
                target_price=target_price,
                target_date=target_date,
                max_premium=max_premium,
                risk_profile=risk_profile,
                underlying_price=underlying_price,
            )
        if strategy == "bull_call_spread":
            return self._debit_spread_comparison(
                strategy=strategy,
                side="call",
                contracts=contracts,
                target_price=target_price,
                max_premium=max_premium,
                underlying_price=underlying_price,
            )
        if strategy == "bear_put_spread":
            return self._debit_spread_comparison(
                strategy=strategy,
                side="put",
                contracts=contracts,
                target_price=target_price,
                max_premium=max_premium,
                underlying_price=underlying_price,
            )
        raise ValueError("Unsupported strategy requested for Options Lab Phase 4.")

    def _long_option_comparison(
        self,
        strategy: str,
        side: str,
        contracts: Sequence[OptionContract],
        direction: str,
        target_price: float,
        target_date: date,
        max_premium: Optional[float],
        risk_profile: str,
        underlying_price: float,
    ) -> Optional[OptionsStrategyComparison]:
        candidates = [contract for contract in contracts if contract.side == side]
        if max_premium is not None:
            candidates = [contract for contract in candidates if self._premium_at_risk(contract) <= max_premium]
        if not candidates:
            return None
        scored = [
            self._score_contract(
                contract=contract,
                strategy=strategy,
                direction=direction,
                target_price=target_price,
                target_date=target_date,
                max_premium=max_premium,
                risk_profile=risk_profile,
                underlying_price=underlying_price,
            )
            for contract in candidates
        ]
        best = sorted(scored, key=lambda candidate: (-candidate.score, candidate.contract.expiration, candidate.contract.strike))[0]
        contract = best.contract
        net_debit = self._premium_at_risk(contract)
        breakeven = self._breakeven(contract)
        payoff = round(self._expiration_net_payoff(contract, target_price, net_debit), 2)
        return OptionsStrategyComparison(
            strategyType=strategy,
            legs=[self._strategy_leg("buy", contract)],
            netDebit=net_debit,
            maxLoss=net_debit,
            maxGain=None,
            breakeven=breakeven,
            requiredMovePct=self._required_move_pct(underlying_price, breakeven),
            payoffAtTarget=payoff,
            riskRewardRatio=None,
            liquidityWarnings=self._strategy_liquidity_warnings([contract]),
            ivThetaNotes=self._strategy_iv_theta_notes([contract]),
            suitabilityNotes=self._strategy_suitability_notes(strategy, direction, risk_profile),
            limitations=list(PHASE4_LIMITATIONS),
            noAdviceDisclosure=self._no_advice_disclosure(),
        )

    def _debit_spread_comparison(
        self,
        strategy: str,
        side: str,
        contracts: Sequence[OptionContract],
        target_price: float,
        max_premium: Optional[float],
        underlying_price: float,
    ) -> Optional[OptionsStrategyComparison]:
        pairs = self._debit_spread_pairs(strategy, side, contracts)
        comparisons = []
        for long_leg, short_leg in pairs:
            long_mid = float(long_leg.mid if long_leg.mid is not None else long_leg.last or 0)
            short_mid = float(short_leg.mid if short_leg.mid is not None else short_leg.last or 0)
            net_debit = round((long_mid - short_mid) * CONTRACT_MULTIPLIER, 2)
            if net_debit <= 0:
                continue
            if max_premium is not None and net_debit > max_premium:
                continue
            width = abs(long_leg.strike - short_leg.strike) * CONTRACT_MULTIPLIER
            max_gain = round(width - net_debit, 2)
            if max_gain <= 0:
                continue
            breakeven = (
                round(long_leg.strike + net_debit / CONTRACT_MULTIPLIER, 2)
                if side == "call"
                else round(long_leg.strike - net_debit / CONTRACT_MULTIPLIER, 2)
            )
            payoff = self._debit_spread_payoff(side, long_leg, short_leg, target_price, net_debit)
            comparisons.append(
                OptionsStrategyComparison(
                    strategyType=strategy,
                    legs=[self._strategy_leg("buy", long_leg), self._strategy_leg("sell", short_leg)],
                    netDebit=net_debit,
                    maxLoss=net_debit,
                    maxGain=max_gain,
                    breakeven=breakeven,
                    requiredMovePct=self._required_move_pct(underlying_price, breakeven),
                    payoffAtTarget=payoff,
                    riskRewardRatio=round(max_gain / net_debit, 2),
                    liquidityWarnings=self._strategy_liquidity_warnings([long_leg, short_leg]),
                    ivThetaNotes=self._strategy_iv_theta_notes([long_leg, short_leg]),
                    suitabilityNotes=self._strategy_suitability_notes(strategy, "", ""),
                    limitations=list(PHASE4_LIMITATIONS),
                    noAdviceDisclosure=self._no_advice_disclosure(),
                )
            )
        if not comparisons:
            return None
        return sorted(comparisons, key=lambda item: (len(item.liquidity_warnings), item.net_debit, -float(item.max_gain or 0)))[0]

    @staticmethod
    def _debit_spread_pairs(
        strategy: str,
        side: str,
        contracts: Sequence[OptionContract],
    ) -> List[tuple[OptionContract, OptionContract]]:
        by_expiration: Dict[str, List[OptionContract]] = {}
        for contract in contracts:
            if contract.side == side:
                by_expiration.setdefault(contract.expiration, []).append(contract)
        pairs: List[tuple[OptionContract, OptionContract]] = []
        for expiration_contracts in by_expiration.values():
            ordered = sorted(expiration_contracts, key=lambda contract: contract.strike)
            for index, lower in enumerate(ordered[:-1]):
                higher = ordered[index + 1]
                if strategy == "bull_call_spread":
                    pairs.append((lower, higher))
                elif strategy == "bear_put_spread":
                    pairs.append((higher, lower))
        return pairs

    @staticmethod
    def _strategy_leg(action: str, contract: OptionContract) -> OptionsStrategyLeg:
        mid = float(contract.mid if contract.mid is not None else contract.last or 0)
        return OptionsStrategyLeg(
            action=action,
            side=contract.side,
            contractSymbol=contract.contract_symbol,
            expiration=contract.expiration,
            strike=contract.strike,
            mid=round(mid, 4),
            quantity=1,
        )

    @staticmethod
    def _debit_spread_payoff(
        side: str,
        long_leg: OptionContract,
        short_leg: OptionContract,
        terminal_price: float,
        net_debit: float,
    ) -> float:
        if side == "call":
            gross = (
                max(0.0, terminal_price - long_leg.strike)
                - max(0.0, terminal_price - short_leg.strike)
            ) * CONTRACT_MULTIPLIER
        else:
            gross = (
                max(0.0, long_leg.strike - terminal_price)
                - max(0.0, short_leg.strike - terminal_price)
            ) * CONTRACT_MULTIPLIER
        return round(gross - net_debit, 2)

    @staticmethod
    def _strategy_liquidity_warnings(contracts: Sequence[OptionContract]) -> List[str]:
        warnings = []
        if any(contract.liquidity_bucket == "thin" for contract in contracts):
            warnings.append("thin_liquidity_in_one_or_more_legs")
        if any((contract.spread_pct or 0) > 20 for contract in contracts):
            warnings.append("wide_bid_ask_spread_in_one_or_more_legs")
        return warnings

    @staticmethod
    def _strategy_iv_theta_notes(contracts: Sequence[OptionContract]) -> List[str]:
        notes = ["iv_and_theta_can_change_strategy_value_before_expiration"]
        if any((contract.implied_volatility or 0) >= 0.7 for contract in contracts):
            notes.append("high_implied_volatility_in_one_or_more_legs")
        return notes

    @staticmethod
    def _strategy_suitability_notes(strategy: str, direction: str, risk_profile: str) -> List[str]:
        notes = ["comparison_uses_user_assumptions_and_fixture_mid_prices"]
        if strategy in {"bull_call_spread", "bear_put_spread"}:
            notes.append("defined_risk_debit_spread_caps_loss_and_gain")
        if direction:
            notes.append(f"direction_assumption_{direction}")
        if risk_profile:
            notes.append(f"risk_profile_{risk_profile}")
        return notes

    @staticmethod
    def _no_advice_disclosure() -> str:
        return "Analytical comparison under explicit assumptions only; not investment advice or an instruction."

    @classmethod
    def _scenario_prices(
        cls,
        underlying_price: float,
        target_price: Optional[float],
        custom_prices: Sequence[float],
    ) -> List[tuple[str, float]]:
        rows = [
            ("down_20_pct", underlying_price * 0.8),
            ("down_10_pct", underlying_price * 0.9),
            ("flat", underlying_price),
            ("up_10_pct", underlying_price * 1.1),
            ("up_20_pct", underlying_price * 1.2),
        ]
        if target_price is not None:
            rows.append(("custom_target", target_price))
        for index, price in enumerate(custom_prices):
            rows.append((f"custom_{index + 1}", float(price)))
        seen = set()
        unique_rows = []
        for label, price in rows:
            rounded = round(float(price), 2)
            key = (label, rounded)
            if key not in seen:
                unique_rows.append((label, rounded))
                seen.add(key)
        return unique_rows

    def _payoff_row(
        self,
        label: str,
        terminal_price: float,
        contract: OptionContract,
        premium_at_risk: float,
    ) -> OptionScenarioPayoffRow:
        if contract.side == "call":
            gross = max(0.0, terminal_price - contract.strike) * CONTRACT_MULTIPLIER
        else:
            gross = max(0.0, contract.strike - terminal_price) * CONTRACT_MULTIPLIER
        net = gross - premium_at_risk
        return_pct = (net / premium_at_risk * 100) if premium_at_risk else None
        return OptionScenarioPayoffRow(
            label=label,
            underlyingPrice=round(terminal_price, 2),
            grossPayoff=round(gross, 2),
            netPayoff=round(net, 2),
            returnOnPremiumPct=round(return_pct, 2) if return_pct is not None else None,
        )
