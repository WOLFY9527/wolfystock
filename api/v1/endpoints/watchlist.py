# -*- coding: utf-8 -*-
"""User-owned watchlist endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.deps import CurrentUser, get_current_user
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.watchlist import (
    WatchlistDeleteResponse,
    WatchlistItemCreateRequest,
    WatchlistItemListResponse,
    WatchlistItemResponse,
    WatchlistScoreRefreshRequest,
    WatchlistScoreRefreshResponse,
    WatchlistScoreRefreshStatusResponse,
)
from src.config import get_config
from src.services.execution_log_service import ExecutionLogService
from src.services.watchlist_service import WatchlistService

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_watchlist_service() -> WatchlistService:
    return WatchlistService()


def service_refresh_running() -> bool:
    return WatchlistService.is_refresh_running()


def _actor(current_user: CurrentUser) -> dict:
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "role": "admin" if current_user.is_admin else "user",
        "actor_type": "admin" if current_user.is_admin else "user",
        "session_id": current_user.session_id,
    }


def _record_audit(
    *,
    action: str,
    message: str,
    current_user: CurrentUser,
    item: dict,
) -> None:
    try:
        ExecutionLogService().record_portfolio_event(
            action=action,
            message=message,
            actor=_actor(current_user),
            account_id=None,
            symbol=item.get("symbol"),
            currency=None,
            record_id=item.get("id"),
            detail={
                "category": "watchlist",
                "market": item.get("market"),
                "source": item.get("source"),
                "scanner_run_id": item.get("scanner_run_id"),
                "scanner_rank": item.get("scanner_rank"),
                "scanner_score": item.get("scanner_score"),
                "theme_id": item.get("theme_id"),
                "universe_type": item.get("universe_type"),
            },
        )
    except Exception as exc:  # pragma: no cover - logging must not break writes
        logger.warning("Record watchlist audit log failed: %s", exc)


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "validation_error", "message": str(exc)},
    )


def _not_found(message: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "not_found", "message": message},
    )


def _internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error("%s: %s", message, exc, exc_info=True)
    return HTTPException(
        status_code=500,
        detail={"error": "internal_error", "message": f"{message}: {str(exc)}"},
    )


@router.get(
    "/items",
    response_model=WatchlistItemListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="List user watchlist items",
)
def list_watchlist_items(
    current_user: CurrentUser = Depends(get_current_user),
) -> WatchlistItemListResponse:
    service = _get_watchlist_service()
    try:
        items = service.list_items(owner_id=current_user.user_id)
        return WatchlistItemListResponse(
            items=[WatchlistItemResponse(**item) for item in items],
        )
    except Exception as exc:
        raise _internal_error("List watchlist items failed", exc) from exc


@router.post(
    "/refresh-scores",
    response_model=WatchlistScoreRefreshResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Refresh user watchlist scores",
)
def refresh_watchlist_scores(
    request: WatchlistScoreRefreshRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> WatchlistScoreRefreshResponse:
    service = _get_watchlist_service()
    try:
        result = service.refresh_scores(
            owner_id=current_user.user_id,
            market=request.market,
            symbols=request.symbols,
            source=request.source,
            theme=request.theme,
            force=request.force,
        )
        return WatchlistScoreRefreshResponse(**result)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except Exception as exc:
        raise _internal_error("Refresh watchlist scores failed", exc) from exc


@router.get(
    "/refresh-status",
    response_model=WatchlistScoreRefreshStatusResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Get watchlist score refresh status",
)
def get_watchlist_refresh_status(
    current_user: CurrentUser = Depends(get_current_user),
) -> WatchlistScoreRefreshStatusResponse:
    del current_user
    try:
        config = get_config()
        return WatchlistScoreRefreshStatusResponse(
            enabled=bool(getattr(config, "watchlist_score_refresh_enabled", True)),
            us_time=str(getattr(config, "watchlist_score_refresh_us_time", "08:45")),
            cn_time=str(getattr(config, "watchlist_score_refresh_cn_time", "09:00")),
            hk_time=str(getattr(config, "watchlist_score_refresh_hk_time", "09:00")),
            max_symbols=int(getattr(config, "watchlist_score_refresh_max_symbols", 250)),
            running=service_refresh_running(),
        )
    except Exception as exc:
        raise _internal_error("Get watchlist refresh status failed", exc) from exc


@router.post(
    "/items",
    response_model=WatchlistItemResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Add or update a watchlist item",
)
def add_watchlist_item(
    request: WatchlistItemCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> WatchlistItemResponse:
    service = _get_watchlist_service()
    try:
        item = service.add_item(
            owner_id=current_user.user_id,
            symbol=request.symbol,
            market=request.market,
            source=request.source,
            name=request.name,
            scanner_run_id=request.scanner_run_id,
            scanner_rank=request.scanner_rank,
            scanner_score=request.scanner_score,
            theme_id=request.theme_id,
            universe_type=request.universe_type,
            notes=request.notes,
        )
        _record_audit(
            action="watchlist_add",
            message=f"Scanner candidate saved to watchlist: {item['symbol']}",
            current_user=current_user,
            item=item,
        )
        return WatchlistItemResponse(**item)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except Exception as exc:
        raise _internal_error("Add watchlist item failed", exc) from exc


@router.delete(
    "/items/{item_id}",
    response_model=WatchlistDeleteResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Remove a watchlist item",
)
def delete_watchlist_item(
    item_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> WatchlistDeleteResponse:
    service = _get_watchlist_service()
    try:
        item = service.get_item_by_id(owner_id=current_user.user_id, item_id=item_id)
        deleted = service.remove_item(owner_id=current_user.user_id, item_id=item_id)
        if not deleted:
            raise _not_found(f"Watchlist item not found: {item_id}")
        _record_audit(
            action="watchlist_remove",
            message=f"Scanner candidate removed from watchlist: {item_id}",
            current_user=current_user,
            item=item or {"id": item_id, "symbol": None, "market": None, "source": "scanner"},
        )
        return WatchlistDeleteResponse(deleted=1)
    except HTTPException:
        raise
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except Exception as exc:
        raise _internal_error("Delete watchlist item failed", exc) from exc
