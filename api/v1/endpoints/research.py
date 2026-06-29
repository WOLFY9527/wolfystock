# -*- coding: utf-8 -*-
"""Research Radar read-only endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import CurrentUser, get_current_user, get_current_user_id, get_database_manager
from api.v1.consumer_safe_response import consumer_safe_json_response
from api.v1.schemas.research_queue import UnifiedResearchQueueResponse
from api.v1.schemas.research_radar import ResearchRadarResponse
from api.v1.schemas.scanner import ScannerRunDetailResponse, sanitize_scanner_consumer_payload
from src.multi_user import OWNERSHIP_SCOPE_USER
from src.repositories.scanner_repo import ScannerRepository
from src.services.market_scanner_service import MarketScannerService
from src.services.backtest_service import BacktestService
from src.services.market_regime_evidence_service import (
    DEFAULT_BENCHMARK_SYMBOL,
    DEFAULT_GROWTH_PROXY_SYMBOL,
    DEFAULT_MARKET_REGIME_SYMBOLS,
    DEFAULT_REQUIRED_BARS,
)
from src.services.market_regime_read_model_service import build_market_regime_read_model
from src.services.research_queue_aggregator_service import ResearchQueueAggregatorService
from src.services.research_radar_service import ResearchRadarService
from src.services.quote_snapshot_config import get_configured_us_quote_snapshot_cache_path
from src.services.us_history_helper import get_configured_us_stock_parquet_dir
from src.services.watchlist_research_overlay_service import WatchlistResearchOverlayService
from src.storage import DatabaseManager


router = APIRouter()


def _latest_scanner_research_payload(
    *,
    db_manager: DatabaseManager,
    current_user: CurrentUser,
    market: str | None,
    profile: str | None,
    limit: int,
) -> dict[str, object] | None:
    owner_id = get_current_user_id(current_user)
    if not owner_id:
        return None
    try:
        scanner_service = MarketScannerService(db_manager, data_manager=object(), owner_id=owner_id)
        runs = scanner_service.repo.get_recent_runs(
            market=_optional_query_token(market),
            profile=_optional_query_token(profile),
            limit=max(1, min(int(limit or 20), 20)),
            scope=OWNERSHIP_SCOPE_USER,
            owner_id=str(owner_id),
            include_all_owners=False,
        )
        for run in runs:
            if str(getattr(run, "status", "") or "").lower() != "completed":
                continue
            payload = scanner_service.get_run_detail(
                int(getattr(run, "id")),
                scope=OWNERSHIP_SCOPE_USER,
                owner_id=str(owner_id),
                include_all_owners=False,
            )
            if payload is None:
                continue
            typed_payload = ScannerRunDetailResponse(**payload).model_dump()
            return sanitize_scanner_consumer_payload(typed_payload)
    except Exception:
        return None
    return None


def _watchlist_research_overlay_payload(*, owner_id: str | None) -> dict[str, object] | None:
    if not owner_id:
        return None
    try:
        return WatchlistResearchOverlayService().build_overlay(owner_id=owner_id)
    except Exception:
        return None


def _optional_query_token(value: object) -> str | None:
    token = str(value or "").strip()
    return token or None


def _market_regime_read_model_payload() -> dict[str, object] | None:
    try:
        return build_market_regime_read_model(
            market="US",
            symbols=list(DEFAULT_MARKET_REGIME_SYMBOLS),
            benchmark_symbol=DEFAULT_BENCHMARK_SYMBOL,
            growth_proxy_symbol=DEFAULT_GROWTH_PROXY_SYMBOL,
            required_bars=DEFAULT_REQUIRED_BARS,
            ohlcv_cache_dir=get_configured_us_stock_parquet_dir(),
            quote_snapshot_cache_path=get_configured_us_quote_snapshot_cache_path(),
            require_adjusted=True,
        )
    except Exception:
        return None


@router.get(
    "/radar",
    response_model=ResearchRadarResponse,
    summary="Get research radar queue",
    description=(
        "Build a research-only radar queue from the latest available scanner candidate evidence. "
        "The endpoint is read-only and does not run scanners or mutate watchlists."
    ),
)
def get_research_radar(
    market: Optional[str] = Query(None, description="Optional scanner market filter"),
    profile: Optional[str] = Query(None, description="Optional scanner profile filter"),
    limit: int = Query(20, ge=1, le=100, description="Recent scanner runs to inspect"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> ResearchRadarResponse:
    bounded_limit = max(1, min(int(limit or 20), 20))
    owner_id = get_current_user_id(current_user)
    backtest_service = (
        BacktestService(db_manager, owner_id=owner_id, include_all_owners=False)
        if owner_id
        else None
    )

    def _backtest_sample_status(symbol: str) -> dict[str, object] | None:
        if backtest_service is None:
            return None
        return backtest_service.get_sample_status(code=symbol)

    service = ResearchRadarService(
        scanner_repository=ScannerRepository(db_manager),
        backtest_sample_reader=_backtest_sample_status if backtest_service is not None else None,
    )
    payload = service.build_from_latest_scanner_run(
        market=market,
        profile=profile,
        owner_id=owner_id,
        limit=bounded_limit,
        market_regime_read_model=_market_regime_read_model_payload(),
    )
    return consumer_safe_json_response(
        ResearchRadarResponse.model_validate(payload),
        surface="research-radar",
    )


@router.get(
    "/queue",
    response_model=UnifiedResearchQueueResponse,
    summary="Get unified research queue",
    description=(
        "Build a bounded, observation-only research queue from already available scanner "
        "candidate packets and watchlist priority signals. The endpoint does not run scanners, "
        "create jobs, mutate watchlists, or call external data sources."
    ),
)
def get_research_queue(
    market: Optional[str] = Query(None, description="Optional scanner market filter"),
    profile: Optional[str] = Query(None, description="Optional scanner profile filter"),
    scanner_limit: int = Query(20, ge=1, le=20, description="Recent scanner runs to inspect"),
    queue_limit: int = Query(10, ge=1, le=10, description="Maximum queue items to return"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> UnifiedResearchQueueResponse:
    owner_id = get_current_user_id(current_user)
    scanner_payload = _latest_scanner_research_payload(
        db_manager=db_manager,
        current_user=current_user,
        market=market,
        profile=profile,
        limit=scanner_limit,
    )
    watchlist_overlay = _watchlist_research_overlay_payload(owner_id=owner_id)
    payload = ResearchQueueAggregatorService().build_queue(
        scanner_payload=scanner_payload,
        watchlist_overlay=watchlist_overlay,
        limit=queue_limit,
    )
    return consumer_safe_json_response(
        UnifiedResearchQueueResponse.model_validate(payload),
        surface="research-queue",
    )
