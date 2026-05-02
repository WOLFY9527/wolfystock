# -*- coding: utf-8 -*-
"""Admin-only execution log center APIs (D2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import CurrentUser, require_admin_user
from api.v1.schemas.admin_logs import (
    AdminLogCleanupRequest,
    AdminLogCleanupResponse,
    AdminLogStorageSummaryModel,
    BusinessEventDetailModel,
    BusinessEventListResponse,
    ExecutionLogSessionDetailModel,
    ExecutionLogSessionListResponse,
)
from src.services.admin_logs_service import AdminLogsRetentionService
from src.services.execution_log_service import ExecutionLogService

router = APIRouter()


def _parse_optional_datetime(value: Optional[str]) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": f"Invalid datetime format: {value}",
            },
        ) from None


def _since_to_date_from(value: Optional[str]) -> Optional[datetime]:
    if not isinstance(value, str):
        value = "24h"
    text = str(value or "").strip().lower()
    if not text:
        return None
    try:
        if text.endswith("m") and text[:-1].isdigit():
            return datetime.now() - timedelta(minutes=int(text[:-1]))
        if text.endswith("h") and text[:-1].isdigit():
            return datetime.now() - timedelta(hours=int(text[:-1]))
        if text.endswith("d") and text[:-1].isdigit():
            return datetime.now() - timedelta(days=int(text[:-1]))
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": f"Invalid since value: {value}",
            },
        ) from None


def _query_text(value: Optional[str], default: Optional[str] = None) -> Optional[str]:
    if not isinstance(value, str):
        return default
    return value.strip() or default


def _query_int(value: int, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _coalesce_query_text(*values: Optional[str], default: Optional[str] = None) -> Optional[str]:
    for value in values:
        text = _query_text(value)
        if text is not None:
            return text
    return default


def _effective_offset(
    *,
    offset: int,
    page: Optional[int],
    cursor: Optional[str],
    limit: int,
) -> int:
    if cursor is not None:
        try:
            return max(0, int(str(cursor).strip()))
        except Exception:
            return 0
    if page is not None:
        try:
            page_number = max(1, int(page))
            return (page_number - 1) * max(1, int(limit))
        except Exception:
            return 0
    return _query_int(offset, 0)


def _list_execution_logs(
    *,
    task_id: Optional[str],
    stock: Optional[str],
    status: Optional[str],
    min_level: Optional[str],
    level: Optional[str],
    category: Optional[str],
    query: Optional[str],
    provider: Optional[str],
    model: Optional[str],
    channel: Optional[str],
    since: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    limit: int,
    offset: int,
    page: Optional[int] = None,
    cursor: Optional[str] = None,
) -> ExecutionLogSessionListResponse:
    service = ExecutionLogService()
    effective_date_from = _parse_optional_datetime(date_from) or _since_to_date_from(since)
    effective_limit = _query_int(limit, 100)
    effective_level = _query_text(level)
    items, total = service.list_sessions(
        task_id=_query_text(task_id),
        stock_code=_query_text(stock),
        status=_query_text(status),
        min_level=None if effective_level else _query_text(min_level, "WARNING"),
        level=effective_level,
        category=_query_text(category),
        query=_query_text(query),
        provider=_query_text(provider),
        model=_query_text(model),
        channel=_query_text(channel),
        date_from=effective_date_from,
        date_to=_parse_optional_datetime(date_to),
        limit=effective_limit,
        offset=_effective_offset(offset=offset, page=page, cursor=cursor, limit=effective_limit),
    )
    return ExecutionLogSessionListResponse(
        total=total,
        items=items,
        summary=service.summarize_items(items),
    )


@router.get(
    "/storage/summary",
    response_model=AdminLogStorageSummaryModel,
    summary="Summarize admin log storage health",
)
def get_log_storage_summary(
    _: CurrentUser = Depends(require_admin_user),
):
    service = AdminLogsRetentionService()
    return AdminLogStorageSummaryModel(**service.storage_summary())


@router.post(
    "/cleanup",
    response_model=AdminLogCleanupResponse,
    summary="Preview or clean old admin logs",
)
def cleanup_admin_logs(
    request: AdminLogCleanupRequest,
    _: CurrentUser = Depends(require_admin_user),
):
    service = AdminLogsRetentionService()
    try:
        result = service.cleanup(
            mode=request.mode,
            use_retention=request.use_retention,
            older_than=request.older_than,
            dry_run=request.dry_run,
            status=request.status,
            category=request.category,
            batch_size=request.batch_size,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": str(exc),
            },
        ) from exc
    return AdminLogCleanupResponse(**result)


@router.get(
    "",
    response_model=BusinessEventListResponse,
    summary="List admin business events",
)
def list_execution_logs_root(
    task_id: Optional[str] = Query(default=None, description="Filter by task ID"),
    task_id_alias: Optional[str] = Query(default=None, alias="taskId", description="Camel-case alias for task_id"),
    stock: Optional[str] = Query(default=None, description="Filter by stock code"),
    status: Optional[str] = Query(default=None, description="Filter by overall status"),
    min_level: str = Query(default="WARNING", description="Minimum log level"),
    min_level_alias: Optional[str] = Query(default=None, alias="minLevel", description="Camel-case alias for min_level"),
    level: Optional[str] = Query(default=None, description="Exact log level"),
    category: Optional[str] = Query(default=None, description="Filter by log category"),
    type: Optional[str] = Query(default=None, description="Filter by business execution type"),
    subject: Optional[str] = Query(default=None, description="Filter by business subject"),
    symbol: Optional[str] = Query(default=None, description="Filter by stock symbol"),
    scanner_id: Optional[str] = Query(default=None, description="Filter by scanner id"),
    strategy_id: Optional[str] = Query(default=None, description="Filter by strategy id"),
    backtest_id: Optional[str] = Query(default=None, description="Filter by backtest id"),
    request_id: Optional[str] = Query(default=None, description="Filter by request id"),
    user_id: Optional[str] = Query(default=None, description="Filter by user id"),
    query: Optional[str] = Query(default=None, description="Search event/message/request/source/user fields"),
    provider: Optional[str] = Query(default=None, description="Filter by provider target"),
    model: Optional[str] = Query(default=None, description="Filter by AI model"),
    channel: Optional[str] = Query(default=None, description="Filter by notification channel"),
    since: str = Query(default="24h", description="Relative window, for example 15m, 1h, 24h, 7d"),
    date_from: Optional[str] = Query(default=None, description="ISO datetime start"),
    date_to: Optional[str] = Query(default=None, description="ISO datetime end"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    page: Optional[int] = Query(default=None, ge=1),
    cursor: Optional[str] = Query(default=None),
    _: CurrentUser = Depends(require_admin_user),
):
    del task_id, task_id_alias, min_level, min_level_alias, level, provider, model, channel
    service = ExecutionLogService()
    effective_limit = _query_int(limit, 50)
    effective_offset = _effective_offset(offset=offset, page=page, cursor=cursor, limit=effective_limit)
    items, total = service.list_business_events(
        category=_query_text(category),
        type=_query_text(type),
        subject=_query_text(subject),
        symbol=_coalesce_query_text(symbol, stock),
        scanner_id=_query_text(scanner_id),
        strategy_id=_query_text(strategy_id),
        backtest_id=_query_text(backtest_id),
        request_id=_query_text(request_id),
        user_id=_query_text(user_id),
        status=_query_text(status),
        query=_query_text(query),
        date_from=_parse_optional_datetime(date_from) or _since_to_date_from(since),
        date_to=_parse_optional_datetime(date_to),
        limit=effective_limit,
        offset=effective_offset,
    )
    return BusinessEventListResponse(
        items=items,
        total=total,
        limit=effective_limit,
        offset=effective_offset,
        hasMore=effective_offset + effective_limit < total,
        health_summary=getattr(service, "_last_business_health_summary", service.summarize_business_events(items)),
    )


@router.get(
    "/sessions",
    response_model=ExecutionLogSessionListResponse,
    summary="List admin execution log sessions",
)
def list_execution_log_sessions(
    task_id: Optional[str] = Query(default=None, description="Filter by task ID"),
    task_id_alias: Optional[str] = Query(default=None, alias="taskId", description="Camel-case alias for task_id"),
    stock: Optional[str] = Query(default=None, description="Filter by stock code"),
    status: Optional[str] = Query(default=None, description="Filter by overall status"),
    min_level: str = Query(default="WARNING", description="Minimum log level"),
    min_level_alias: Optional[str] = Query(default=None, alias="minLevel", description="Camel-case alias for min_level"),
    level: Optional[str] = Query(default=None, description="Exact log level"),
    category: Optional[str] = Query(default=None, description="Filter by log category"),
    query: Optional[str] = Query(default=None, description="Search event/message/request/source/user fields"),
    provider: Optional[str] = Query(default=None, description="Filter by provider target"),
    model: Optional[str] = Query(default=None, description="Filter by AI model"),
    channel: Optional[str] = Query(default=None, description="Filter by notification channel"),
    since: str = Query(default="24h", description="Relative window, for example 15m, 1h, 24h, 7d"),
    date_from: Optional[str] = Query(default=None, description="ISO datetime start"),
    date_to: Optional[str] = Query(default=None, description="ISO datetime end"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    page: Optional[int] = Query(default=None, ge=1),
    cursor: Optional[str] = Query(default=None),
    _: CurrentUser = Depends(require_admin_user),
):
    return _list_execution_logs(
        task_id=_coalesce_query_text(task_id, task_id_alias),
        stock=stock,
        status=status,
        min_level=_coalesce_query_text(min_level_alias, min_level, default="WARNING"),
        level=level,
        category=category,
        query=query,
        provider=provider,
        model=model,
        channel=channel,
        since=since,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        page=page,
        cursor=cursor,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=ExecutionLogSessionDetailModel,
    summary="Get one admin execution log session detail",
)
def get_execution_log_session_detail(
    session_id: str,
    _: CurrentUser = Depends(require_admin_user),
):
    service = ExecutionLogService()
    detail = service.get_session_detail(session_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"Execution log session not found: {session_id}",
            },
        )
    return ExecutionLogSessionDetailModel(**detail)


@router.get(
    "/{event_id}",
    response_model=BusinessEventDetailModel,
    summary="Get one admin business event detail",
)
def get_business_event_detail(
    event_id: str,
    _: CurrentUser = Depends(require_admin_user),
):
    service = ExecutionLogService()
    detail = service.get_business_event_detail(event_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"Business event not found: {event_id}",
            },
        )
    return BusinessEventDetailModel(**detail)
