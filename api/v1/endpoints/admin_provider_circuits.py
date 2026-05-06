# -*- coding: utf-8 -*-
"""Admin-only read APIs for provider circuit diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, select

from api.deps import CurrentUser, require_admin_capability
from api.v1.schemas.admin_provider_circuits import (
    ProviderCircuitDiagnosticsMetadata,
    ProviderCircuitEventItem,
    ProviderCircuitEventsResponse,
    ProviderCircuitStateItem,
    ProviderCircuitStatesResponse,
    ProviderProbeEventItem,
    ProviderProbeEventsResponse,
    ProviderQuotaWindowItem,
    ProviderQuotaWindowsResponse,
)
from src.storage import (
    DatabaseManager,
    ProviderCircuitEvent,
    ProviderCircuitState,
    ProviderProbeEvent,
    ProviderQuotaWindow,
)
from src.utils.security import sanitize_message

router = APIRouter()

_DEFAULT_LIMIT = 100
_MAX_LIMIT = 200
_REDACTION_NOTES = [
    "metadata_omitted",
    "owner_and_guest_identifiers_omitted",
    "raw_provider_payloads_omitted",
    "urls_query_strings_credentials_sessions_and_stack_traces_omitted",
]


def _safe_limit(value: int | None) -> int:
    try:
        parsed = int(value or _DEFAULT_LIMIT)
    except (TypeError, ValueError):
        parsed = _DEFAULT_LIMIT
    return max(1, min(parsed, _MAX_LIMIT))


def _safe_filter(value: str | None, *, limit: int = 64) -> str | None:
    text = sanitize_message(str(value or "").strip().lower())[:limit]
    return text or None


def _parse_since(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": "Invalid since timestamp"},
        ) from exc


def _metadata(*, table: str, limit: int, filters: dict[str, Any]) -> ProviderCircuitDiagnosticsMetadata:
    return ProviderCircuitDiagnosticsMetadata(
        limit=limit,
        dataSources=[table],
        redaction=_REDACTION_NOTES,
        filters={key: value for key, value in filters.items() if value not in (None, "")},
    )


def _state_item(row: ProviderCircuitState) -> ProviderCircuitStateItem:
    return ProviderCircuitStateItem(
        provider=str(row.provider or "unknown"),
        providerCategory=row.provider_category,
        routeFamily=row.route_family,
        state=str(row.state or "unknown"),
        reasonBucket=row.reason_bucket,
        cooldownUntil=row.cooldown_until.isoformat() if row.cooldown_until else None,
        operatorActionRef=row.operator_action_ref,
        createdAt=row.created_at.isoformat() if row.created_at else None,
        updatedAt=row.updated_at.isoformat() if row.updated_at else None,
    )


def _event_item(row: ProviderCircuitEvent) -> ProviderCircuitEventItem:
    return ProviderCircuitEventItem(
        provider=str(row.provider or "unknown"),
        providerCategory=row.provider_category,
        routeFamily=row.route_family,
        eventType=str(row.event_type or "unknown"),
        fromState=row.from_state,
        toState=row.to_state,
        reasonBucket=row.reason_bucket,
        requestCountBucket=row.request_count_bucket,
        durationBucketMs=row.duration_bucket_ms,
        failureCountBucket=row.failure_count_bucket,
        operatorActionRef=row.operator_action_ref,
        createdAt=row.created_at.isoformat() if row.created_at else None,
    )


def _quota_window_item(row: ProviderQuotaWindow) -> ProviderQuotaWindowItem:
    return ProviderQuotaWindowItem(
        provider=str(row.provider or "unknown"),
        providerCategory=row.provider_category,
        routeFamily=row.route_family,
        windowType=str(row.window_type or "custom"),
        windowStart=row.window_start.isoformat() if row.window_start else "",
        windowEnd=row.window_end.isoformat() if row.window_end else "",
        requestCount=int(row.request_count or 0),
        reservedUnits=int(row.reserved_units or 0),
        consumedUnits=int(row.consumed_units or 0),
        releasedUnits=int(row.released_units or 0),
        rejectedCount=int(row.rejected_count or 0),
        successCount=int(row.success_count or 0),
        failureCount=int(row.failure_count or 0),
        timeoutCount=int(row.timeout_count or 0),
        provider429Count=int(row.provider_429_count or 0),
        provider403Count=int(row.provider_403_count or 0),
        fallbackCount=int(row.fallback_count or 0),
        probeCount=int(row.probe_count or 0),
        cacheOnlyCount=int(row.cache_only_count or 0),
        staleServedCount=int(row.stale_served_count or 0),
        createdAt=row.created_at.isoformat() if row.created_at else None,
        updatedAt=row.updated_at.isoformat() if row.updated_at else None,
    )


def _probe_event_item(row: ProviderProbeEvent) -> ProviderProbeEventItem:
    return ProviderProbeEventItem(
        provider=str(row.provider or "unknown"),
        providerCategory=row.provider_category,
        routeFamily=row.route_family,
        probeType=str(row.probe_type or "unknown"),
        probeSource=str(row.probe_source or "unknown"),
        resultBucket=str(row.result_bucket or "unknown"),
        durationBucketMs=row.duration_bucket_ms,
        createdAt=row.created_at.isoformat() if row.created_at else None,
    )


@router.get(
    "/providers/circuits",
    response_model=ProviderCircuitStatesResponse,
    summary="Get read-only provider circuit states",
)
def get_provider_circuit_states(
    provider: str | None = Query(default=None),
    state: str | None = Query(default=None),
    routeFamily: str | None = Query(default=None),
    since: str | None = Query(default=None),
    limit: int = Query(default=_DEFAULT_LIMIT),
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
) -> ProviderCircuitStatesResponse:
    safe_provider = _safe_filter(provider)
    safe_state = _safe_filter(state, limit=32)
    safe_route = _safe_filter(routeFamily)
    since_dt = _parse_since(since)
    safe_limit = _safe_limit(limit)

    query = select(ProviderCircuitState)
    if safe_provider:
        query = query.where(ProviderCircuitState.provider == safe_provider)
    if safe_state:
        query = query.where(ProviderCircuitState.state == safe_state)
    if safe_route:
        query = query.where(ProviderCircuitState.route_family == safe_route)
    if since_dt:
        query = query.where(ProviderCircuitState.updated_at >= since_dt)
    query = query.order_by(desc(ProviderCircuitState.updated_at), asc(ProviderCircuitState.provider)).limit(safe_limit)

    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        rows = session.execute(query).scalars().all()

    filters = {"provider": safe_provider, "state": safe_state, "routeFamily": safe_route, "since": since}
    return ProviderCircuitStatesResponse(
        generatedAt=datetime.now().isoformat(),
        items=[_state_item(row) for row in rows],
        metadata=_metadata(table="provider_circuit_states", limit=safe_limit, filters=filters),
    )


@router.get(
    "/providers/circuits/events",
    response_model=ProviderCircuitEventsResponse,
    summary="Get read-only provider circuit events",
)
def get_provider_circuit_events(
    provider: str | None = Query(default=None),
    routeFamily: str | None = Query(default=None),
    eventType: str | None = Query(default=None),
    since: str | None = Query(default=None),
    limit: int = Query(default=_DEFAULT_LIMIT),
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
) -> ProviderCircuitEventsResponse:
    safe_provider = _safe_filter(provider)
    safe_route = _safe_filter(routeFamily)
    safe_event_type = _safe_filter(eventType, limit=32)
    since_dt = _parse_since(since)
    safe_limit = _safe_limit(limit)

    query = select(ProviderCircuitEvent)
    if safe_provider:
        query = query.where(ProviderCircuitEvent.provider == safe_provider)
    if safe_route:
        query = query.where(ProviderCircuitEvent.route_family == safe_route)
    if safe_event_type:
        query = query.where(ProviderCircuitEvent.event_type == safe_event_type)
    if since_dt:
        query = query.where(ProviderCircuitEvent.created_at >= since_dt)
    query = query.order_by(desc(ProviderCircuitEvent.created_at), asc(ProviderCircuitEvent.provider)).limit(safe_limit)

    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        rows = session.execute(query).scalars().all()

    filters = {"provider": safe_provider, "routeFamily": safe_route, "eventType": safe_event_type, "since": since}
    return ProviderCircuitEventsResponse(
        generatedAt=datetime.now().isoformat(),
        items=[_event_item(row) for row in rows],
        metadata=_metadata(table="provider_circuit_events", limit=safe_limit, filters=filters),
    )


@router.get(
    "/providers/quota-windows",
    response_model=ProviderQuotaWindowsResponse,
    summary="Get read-only provider quota windows",
)
def get_provider_quota_windows(
    provider: str | None = Query(default=None),
    routeFamily: str | None = Query(default=None),
    since: str | None = Query(default=None),
    limit: int = Query(default=_DEFAULT_LIMIT),
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
) -> ProviderQuotaWindowsResponse:
    safe_provider = _safe_filter(provider)
    safe_route = _safe_filter(routeFamily)
    since_dt = _parse_since(since)
    safe_limit = _safe_limit(limit)

    query = select(ProviderQuotaWindow)
    if safe_provider:
        query = query.where(ProviderQuotaWindow.provider == safe_provider)
    if safe_route:
        query = query.where(ProviderQuotaWindow.route_family == safe_route)
    if since_dt:
        query = query.where(ProviderQuotaWindow.window_start >= since_dt)
    query = query.order_by(desc(ProviderQuotaWindow.window_start), asc(ProviderQuotaWindow.provider)).limit(safe_limit)

    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        rows = session.execute(query).scalars().all()

    filters = {"provider": safe_provider, "routeFamily": safe_route, "since": since}
    return ProviderQuotaWindowsResponse(
        generatedAt=datetime.now().isoformat(),
        items=[_quota_window_item(row) for row in rows],
        metadata=_metadata(table="provider_quota_windows", limit=safe_limit, filters=filters),
    )


@router.get(
    "/providers/probe-events",
    response_model=ProviderProbeEventsResponse,
    summary="Get read-only provider probe events",
)
def get_provider_probe_events(
    provider: str | None = Query(default=None),
    routeFamily: str | None = Query(default=None),
    since: str | None = Query(default=None),
    limit: int = Query(default=_DEFAULT_LIMIT),
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
) -> ProviderProbeEventsResponse:
    safe_provider = _safe_filter(provider)
    safe_route = _safe_filter(routeFamily)
    since_dt = _parse_since(since)
    safe_limit = _safe_limit(limit)

    query = select(ProviderProbeEvent)
    if safe_provider:
        query = query.where(ProviderProbeEvent.provider == safe_provider)
    if safe_route:
        query = query.where(ProviderProbeEvent.route_family == safe_route)
    if since_dt:
        query = query.where(ProviderProbeEvent.created_at >= since_dt)
    query = query.order_by(desc(ProviderProbeEvent.created_at), asc(ProviderProbeEvent.provider)).limit(safe_limit)

    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        rows = session.execute(query).scalars().all()

    filters = {"provider": safe_provider, "routeFamily": safe_route, "since": since}
    return ProviderProbeEventsResponse(
        generatedAt=datetime.now().isoformat(),
        items=[_probe_event_item(row) for row in rows],
        metadata=_metadata(table="provider_probe_events", limit=safe_limit, filters=filters),
    )
