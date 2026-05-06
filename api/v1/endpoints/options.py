# -*- coding: utf-8 -*-
"""Read-only Options Lab Phase 1 endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.options import (
    OptionChainResponse,
    OptionExpirationsResponse,
    OptionsAnalyzeRequest,
    OptionsAnalyzeResponse,
    OptionsDecisionRequest,
    OptionsDecisionResponse,
    OptionsScenarioRequest,
    OptionsScenarioResponse,
    OptionsStrategyCompareRequest,
    OptionsStrategyCompareResponse,
    OptionUnderlyingSummaryResponse,
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
        return _service().get_summary(
            symbol,
            force_refresh=force_refresh,
            market_data_provider=market_data_provider,
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
        return _service().get_expirations(
            symbol,
            force_refresh=force_refresh,
            market_data_provider=market_data_provider,
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
        return _service().get_chain(
            symbol,
            expiration=expiration,
            side=side,
            min_open_interest=min_open_interest,
            max_spread_pct=max_spread_pct,
            include_greeks=include_greeks,
            force_refresh=force_refresh,
            market_data_provider=market_data_provider,
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
        return _service().analyze(request)
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
        return _service().evaluate_decision(request)
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
        return _service().scenario(request)
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
        return _service().compare_strategies(request)
    except OptionsLabUnsupportedSymbol as exc:
        raise _unsupported_response(exc) from exc
    except OptionsLabProviderUnavailable as exc:
        raise _provider_unavailable_response(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(exc)}) from exc
