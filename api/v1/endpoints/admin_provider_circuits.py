# -*- coding: utf-8 -*-
"""Admin-only read APIs for provider circuit diagnostics."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func, select

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
    ProviderRecentErrorBucketItem,
    ProviderSlaReadinessItem,
    ProviderSlaReadinessResponse,
    ProviderSlaTrendSummaryItem,
)
from src.config import parse_env_bool
from src.services.options_market_data_provider import (
    LIVE_OPTIONS_PROVIDER_NAMES,
    OptionsLiveProviderConfig,
    build_options_provider_live_readiness_preflight,
)
from src.services.provider_circuit_observer import ProviderCircuitObserver
from src.storage import (
    DatabaseManager,
    ProviderCircuitEvent,
    ProviderCircuitState,
    ProviderProbeEvent,
    ProviderQuotaWindow,
    ExecutionLogSession,
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
_OPTIONS_PROVIDER_CATEGORY = "options"
_OPTIONS_ROUTE_FAMILY = "options_lab"
_STAGED_PROVIDER_CIRCUIT_CATEGORIES = (_OPTIONS_PROVIDER_CATEGORY,)
_STAGED_PROVIDER_CIRCUIT_ROUTE_FAMILIES = (_OPTIONS_ROUTE_FAMILY,)
_RUNTIME_PILOT_CONTRACT_VERSION = "provider_reliability_runtime_v1"
_RUNTIME_PILOT_DEFAULT_OFF_LABEL = "provider_reliability_runtime_pilot_default_off"
_RUNTIME_PILOT_ROLLBACK_LABEL = "provider_reliability_runtime_pilot_disable_flag"
_ADMIN_PROBE_PILOT_EVIDENCE_CONTRACT_VERSION = "provider_admin_probe_pilot_evidence_v1"
_ADMIN_PROBE_PILOT_ENABLED_ENV = "WOLFYSTOCK_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED"
_ADMIN_PROBE_PILOT_ROLLBACK_ENV = "WOLFYSTOCK_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENABLED"
_ADMIN_PROBE_PROVIDER_CATEGORY = "data_source_validation"
_ADMIN_PROBE_ROUTE_FAMILY = "admin_provider_probe"
_ADMIN_PROBE_SELECTED_BOUNDARY = "/config/data-source/test-builtin"
_ADMIN_PROBE_API_ROUTE = "/api/v1/system/config/data-source/test-builtin"
_ADMIN_PROBE_REMAINING_PUBLIC_LAUNCH_NO_GO_ITEMS = [
    "public_provider_circuit_enforcement_not_accepted",
    "target_environment_provider_sla_evidence_missing",
    "provider_entitlement_licensing_not_accepted",
]
_PROVIDER_FAILURE_SIGNAL_LOOKBACK_DAYS = 7
_SAFE_DIAGNOSTIC_REF_RE = re.compile(r"[^A-Za-z0-9_.:-]+")
_UNSAFE_DIAGNOSTIC_TEXT_RE = re.compile(
    r"(https?://|[?&][a-z0-9_.:-]+=|"
    r"\b(?:api[-_]?key|access[-_]?token|refresh[-_]?token|session[-_]?(?:id|token|cookie)?|"
    r"cookie|authorization|bearer|secret|password|credential|raw[-_]?(?:exception|payload|request|response)|"
    r"request[-_]?body|response[-_]?body|headers?|stack[-_]?trace|traceback)\b\s*[:=]|"
    r"\b(?:traceback|exception\(|providererror\())",
    re.IGNORECASE,
)


def _has_unsafe_diagnostic_text(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and _UNSAFE_DIAGNOSTIC_TEXT_RE.search(text))


def _safe_limit(value: int | None) -> int:
    try:
        parsed = int(value or _DEFAULT_LIMIT)
    except (TypeError, ValueError):
        parsed = _DEFAULT_LIMIT
    return max(1, min(parsed, _MAX_LIMIT))


def _safe_filter(value: str | None, *, limit: int = 64) -> str | None:
    raw_text = str(value or "").strip()
    if _has_unsafe_diagnostic_text(raw_text):
        return None
    text = sanitize_message(raw_text.lower())[:limit]
    return text or None


def _safe_diagnostic_ref(value: Any) -> str | None:
    raw_text = str(value or "").strip()
    if not raw_text:
        return None
    sanitized = sanitize_message(raw_text).strip()
    if _has_unsafe_diagnostic_text(raw_text) or _has_unsafe_diagnostic_text(sanitized):
        return "diagnostic_ref_redacted"
    ref = _SAFE_DIAGNOSTIC_REF_RE.sub("_", sanitized).strip("_.:-")[:128]
    return ref or "diagnostic_ref_redacted"


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


def _nested_int_at(payload: Any, path: tuple[str, ...]) -> int:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return 0
        current = current.get(key)
    try:
        return max(0, int(current or 0))
    except (TypeError, ValueError):
        return 0


def _metadata(*, table: str, limit: int, filters: dict[str, Any]) -> ProviderCircuitDiagnosticsMetadata:
    coverage = _provider_circuit_coverage_diagnostics()
    return ProviderCircuitDiagnosticsMetadata(
        limit=limit,
        dataSources=[table],
        redaction=_REDACTION_NOTES,
        filters={key: value for key, value in filters.items() if value not in (None, "")},
        **coverage,
    )


def _provider_circuit_coverage_diagnostics() -> dict[str, Any]:
    since_dt = datetime.now() - timedelta(days=_PROVIDER_FAILURE_SIGNAL_LOOKBACK_DAYS)
    db = DatabaseManager.get_instance()
    signal_sources: set[str] = set()
    with db.get_session() as session:
        circuit_state_count = int(session.execute(select(func.count(ProviderCircuitState.id))).scalar() or 0)
        circuit_event_count = int(session.execute(select(func.count(ProviderCircuitEvent.id))).scalar() or 0)
        probe_event_count = int(session.execute(select(func.count(ProviderProbeEvent.id))).scalar() or 0)

        quota_failure_count = int(
            session.execute(
                select(
                    func.coalesce(
                        func.sum(
                            ProviderQuotaWindow.failure_count
                            + ProviderQuotaWindow.timeout_count
                            + ProviderQuotaWindow.provider_429_count
                            + ProviderQuotaWindow.provider_403_count
                        ),
                        0,
                    )
                ).where(ProviderQuotaWindow.window_end >= since_dt)
            ).scalar()
            or 0
        )
        if quota_failure_count > 0:
            signal_sources.add("provider_quota_windows")

        recent_summaries = session.execute(
            select(ExecutionLogSession.summary_json)
            .where(
                ExecutionLogSession.started_at >= since_dt,
                ExecutionLogSession.summary_json.is_not(None),
            )
            .order_by(desc(ExecutionLogSession.started_at))
            .limit(200)
        ).scalars().all()

    execution_log_failure_count = 0
    for summary_json in recent_summaries:
        summary = DatabaseManager._safe_json_loads(summary_json, {})
        execution_log_failure_count += _nested_int_at(summary, ("scanner_run", "provider_failure_count"))
        execution_log_failure_count += _nested_int_at(
            summary,
            ("scanner_run", "provider_diagnostics", "provider_failure_count"),
        )
    if execution_log_failure_count > 0:
        signal_sources.add("execution_log_sessions")

    circuit_states_present = circuit_state_count > 0
    circuit_events_present = circuit_event_count > 0
    probe_events_present = probe_event_count > 0
    provider_failure_signals_present = bool(signal_sources)
    possible_unwired = provider_failure_signals_present and not circuit_states_present

    if circuit_states_present:
        coverage_status = "states_present"
        recommended_next_action = "review_existing_circuit_state_rows"
    elif possible_unwired:
        coverage_status = "possible_unwired"
        recommended_next_action = "provider_failures_observed_without_circuit_state_rows_review_circuit_wiring"
    else:
        coverage_status = "idle_no_signals"
        recommended_next_action = "no_action_provider_circuit_infrastructure_idle"

    return {
        "circuitStateCoverageStatus": coverage_status,
        "providerFailureSignalsPresent": provider_failure_signals_present,
        "circuitStatesPresent": circuit_states_present,
        "circuitEventsPresent": circuit_events_present,
        "probeEventsPresent": probe_events_present,
        "possibleUnwiredCircuitObservation": possible_unwired,
        "recommendedNextAction": recommended_next_action,
        "diagnosticSignalSources": sorted(signal_sources),
    }


def _state_item(row: ProviderCircuitState) -> ProviderCircuitStateItem:
    return ProviderCircuitStateItem(
        provider=str(row.provider or "unknown"),
        providerCategory=row.provider_category,
        routeFamily=row.route_family,
        state=str(row.state or "unknown"),
        reasonBucket=row.reason_bucket,
        cooldownUntil=row.cooldown_until.isoformat() if row.cooldown_until else None,
        operatorActionRef=_safe_diagnostic_ref(row.operator_action_ref),
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
        operatorActionRef=_safe_diagnostic_ref(row.operator_action_ref),
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


def _credential_state(preflight: dict[str, Any]) -> str:
    readiness_state = str(preflight.get("readinessState") or "unknown")
    if readiness_state in {
        "disabled",
        "missing_credentials",
        "malformed_credentials",
        "partial_credentials",
        "live_credentials_present_live_calls_disabled",
        "dry_run_enabled",
    }:
        return readiness_state
    if preflight.get("credentialsPresent") is True:
        return "credentials_present"
    return "unknown"


def _sla_item_from_diagnostics(
    diagnostics: dict[str, Any],
    *,
    preflight: dict[str, Any] | None = None,
    runtime_pilot: dict[str, Any] | None = None,
    admin_probe_pilot_evidence: dict[str, Any] | None = None,
) -> ProviderSlaReadinessItem:
    preflight = preflight or {}
    sla = dict(diagnostics.get("sla") or {})
    circuit = dict(diagnostics.get("circuitPreflight") or {})
    trend = dict(diagnostics.get("trendSummary") or {})
    recent_errors = [
        ProviderRecentErrorBucketItem(
            reasonBucket=str(item.get("reasonBucket") or "unknown"),
            countBucket=str(item.get("countBucket") or "1"),
            latestAt=item.get("latestAt"),
        )
        for item in diagnostics.get("recentErrors") or []
        if isinstance(item, dict)
    ]
    return ProviderSlaReadinessItem(
        provider=str(diagnostics.get("provider") or preflight.get("providerName") or "unknown"),
        providerCategory=diagnostics.get("providerCategory") or _OPTIONS_PROVIDER_CATEGORY,
        routeFamily=diagnostics.get("routeFamily") or _OPTIONS_ROUTE_FAMILY,
        observedSince=str(diagnostics.get("observedSince") or ""),
        readinessState=str(preflight.get("readinessState") or "observed"),
        reasonCode=str(preflight.get("reasonCode") or "stored_provider_observations"),
        credentialState=_credential_state(preflight),
        credentialContract=dict(preflight.get("credentialContract") or {}),
        liveProvidersEnabled=bool(preflight.get("liveProvidersEnabled") is True),
        providerEnabled=bool(preflight.get("providerEnabled") is True),
        credentialsPresent=bool(preflight.get("credentialsPresent") is True),
        dryRunEnabled=bool(preflight.get("dryRunEnabled") is True),
        liveHttpCallsEnabled=False,
        brokerOrderPathEnabled=False,
        portfolioMutationPathEnabled=False,
        tradeableData=False,
        latencyBucketMs=sla.get("latencyBucketMs"),
        latencyState=str(sla.get("latencyState") or "unknown"),
        errorRate=sla.get("errorRate"),
        errorState=str(sla.get("errorState") or "unknown"),
        freshnessSeconds=sla.get("freshnessSeconds"),
        freshnessState=str(sla.get("freshnessState") or "unknown"),
        recentErrors=recent_errors,
        trendSummary=ProviderSlaTrendSummaryItem(
            windowCountBucket=str(trend.get("windowCountBucket") or "0"),
            requestCountBucket=str(trend.get("requestCountBucket") or "0"),
            failureCountBucket=str(trend.get("failureCountBucket") or "0"),
            timeoutCountBucket=str(trend.get("timeoutCountBucket") or "0"),
            provider429CountBucket=str(trend.get("provider429CountBucket") or "0"),
            provider403CountBucket=str(trend.get("provider403CountBucket") or "0"),
            latestObservationAt=trend.get("latestObservationAt"),
        ),
        circuitAdvisoryState=str(circuit.get("preflight_state") or "healthy"),
        circuitStateCandidate=str(circuit.get("state_candidate") or "closed"),
        scopeMatched=bool(circuit.get("scope_matched") is True),
        liveEnforcement=False,
        wouldBlockCall=False,
        wouldBlockIfEnforced=bool(circuit.get("would_block_if_enforced") is True),
        enforcementBlockReasonCode=circuit.get("enforcement_block_reason_code"),
        wouldChangeProviderOrder=False,
        wouldChangeFallbackBehavior=False,
        noExternalCalls=True,
        providerBehaviorChanged=False,
        marketCacheBehaviorChanged=False,
        runtimePilot=runtime_pilot,
        adminProbePilotEvidence=admin_probe_pilot_evidence,
    )


def _runtime_pilot_projection(
    diagnostics: dict[str, Any],
    *,
    pilot_enabled: bool,
    fallback_evaluation_enabled: bool,
) -> dict[str, Any]:
    circuit = dict(diagnostics.get("circuitPreflight") or {})
    scope_matched = bool(circuit.get("scope_matched") is True)
    would_block_if_enforced = bool(circuit.get("would_block_if_enforced") is True)
    reason_code = circuit.get("enforcement_block_reason_code")
    if reason_code not in ProviderCircuitObserver.FAILURE_BUCKETS:
        reason_code = None
    return {
        "contractVersion": _RUNTIME_PILOT_CONTRACT_VERSION,
        "pilotEnabled": bool(pilot_enabled),
        "fallbackEvaluationEnabled": bool(fallback_evaluation_enabled),
        "scopeMatched": scope_matched,
        "advisoryOnly": True,
        "productionEnforcementEnabled": False,
        "liveEnforcement": False,
        "wouldBlockCall": False,
        "wouldBlockIfEnforced": would_block_if_enforced,
        "pilotWouldBlock": bool(pilot_enabled and scope_matched and would_block_if_enforced),
        "pilotWouldFallback": bool(fallback_evaluation_enabled and scope_matched and would_block_if_enforced),
        "enforcementBlockReasonCode": reason_code,
        "wouldChangeProviderOrder": False,
        "wouldChangeFallbackBehavior": False,
        "noExternalCalls": True,
        "providerBehaviorChanged": False,
        "marketCacheBehaviorChanged": False,
        "brokerOrderPathEnabled": False,
        "portfolioMutationPathEnabled": False,
        "tradeableData": False,
        "defaultOffLabel": _RUNTIME_PILOT_DEFAULT_OFF_LABEL,
        "rollbackLabel": _RUNTIME_PILOT_ROLLBACK_LABEL,
    }


def _admin_probe_pilot_evidence_projection(
    observer: ProviderCircuitObserver,
    *,
    provider: str,
    provider_category: str | None,
    route_family: str | None,
) -> dict[str, Any] | None:
    if provider_category != _ADMIN_PROBE_PROVIDER_CATEGORY or route_family != _ADMIN_PROBE_ROUTE_FAMILY:
        return None

    pilot_enabled = parse_env_bool(os.getenv(_ADMIN_PROBE_PILOT_ENABLED_ENV), default=False)
    rollback_enabled = parse_env_bool(os.getenv(_ADMIN_PROBE_PILOT_ROLLBACK_ENV), default=False)
    decision = observer.build_low_risk_enforcement_pilot_decision(
        provider=provider,
        provider_category=_ADMIN_PROBE_PROVIDER_CATEGORY,
        route_family=_ADMIN_PROBE_ROUTE_FAMILY,
        pilot_enabled=pilot_enabled,
        rollback_enabled=rollback_enabled,
        controlled_provider_categories=(_ADMIN_PROBE_PROVIDER_CATEGORY,),
        controlled_route_families=(_ADMIN_PROBE_ROUTE_FAMILY,),
    )
    reason_code = decision.get("enforcement_block_reason_code")
    if reason_code not in ProviderCircuitObserver.FAILURE_BUCKETS:
        reason_code = None

    return {
        "contractVersion": _ADMIN_PROBE_PILOT_EVIDENCE_CONTRACT_VERSION,
        "pilotEnabled": bool(decision.get("pilot_enabled") is True),
        "rollbackEnabled": bool(decision.get("rollback_enabled") is True),
        "selectedBoundary": _ADMIN_PROBE_SELECTED_BOUNDARY,
        "apiRoute": _ADMIN_PROBE_API_ROUTE,
        "selectedBoundaryOnly": True,
        "adminProbeOnly": True,
        "defaultOffPosture": True,
        "rollbackAvailable": True,
        "providerCategory": _ADMIN_PROBE_PROVIDER_CATEGORY,
        "routeFamily": _ADMIN_PROBE_ROUTE_FAMILY,
        "lastDecisionCategory": str(decision.get("pilot_status") or "unknown"),
        "scopeMatched": bool(decision.get("scope_matched") is True),
        "liveEnforcement": bool(decision.get("live_enforcement") is True),
        "wouldBlockCall": bool(decision.get("would_block_call") is True),
        "wouldBlockIfEnforced": bool(decision.get("would_block_if_enforced") is True),
        "enforcementBlockReasonCode": reason_code,
        "publicRuntimeProviderBlocking": False,
        "memberRuntimeProviderBlocking": False,
        "providerRuntimeEnforcement": False,
        "wouldChangeProviderOrder": False,
        "wouldChangeFallbackBehavior": False,
        "providerOrderFallbackCacheBehaviorChanged": False,
        "noExternalCalls": True,
        "adminProbeBehaviorChanged": bool(decision.get("provider_behavior_changed") is True),
        "globalProviderBehaviorChanged": False,
        "marketCacheBehaviorChanged": False,
        "quotaEnforcementChanged": False,
        "authRbacSessionChanged": False,
        "notificationSendEnabled": False,
        "sanitizedFieldsOnly": True,
        "acceptedOperatorEvidencePresent": False,
        "publicLaunchReady": False,
        "remainingPublicLaunchNoGoItems": list(_ADMIN_PROBE_REMAINING_PUBLIC_LAUNCH_NO_GO_ITEMS),
        "defaultOffLabel": str(
            decision.get("default_off_label") or ProviderCircuitObserver.LOW_RISK_ADMIN_PROBE_DEFAULT_OFF_LABEL
        ),
        "rollbackLabel": str(
            decision.get("rollback_label") or ProviderCircuitObserver.LOW_RISK_ADMIN_PROBE_ROLLBACK_LABEL
        ),
    }


def _observed_provider_dimensions(
    *,
    provider: str | None,
    route_family: str | None,
    since_dt: datetime,
    limit: int,
) -> list[tuple[str, str | None, str | None]]:
    query = select(ProviderQuotaWindow.provider, ProviderQuotaWindow.provider_category, ProviderQuotaWindow.route_family).where(
        ProviderQuotaWindow.window_end >= since_dt
    )
    if provider:
        query = query.where(ProviderQuotaWindow.provider == provider)
    if route_family:
        query = query.where(ProviderQuotaWindow.route_family == route_family)
    event_query = select(ProviderCircuitEvent.provider, ProviderCircuitEvent.provider_category, ProviderCircuitEvent.route_family).where(
        ProviderCircuitEvent.created_at >= since_dt
    )
    if provider:
        event_query = event_query.where(ProviderCircuitEvent.provider == provider)
    if route_family:
        event_query = event_query.where(ProviderCircuitEvent.route_family == route_family)

    db = DatabaseManager.get_instance()
    seen: set[tuple[str, str | None, str | None]] = set()
    with db.get_session() as session:
        for row in session.execute(query.limit(limit)).all() + session.execute(event_query.limit(limit)).all():
            provider_name = str(row[0] or "").strip()
            if provider_name:
                seen.add((provider_name, row[1], row[2]))
    return sorted(seen)


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


@router.get(
    "/providers/sla-readiness",
    response_model=ProviderSlaReadinessResponse,
    summary="Get read-only provider SLA and readiness diagnostics",
)
def get_provider_sla_readiness(
    provider: str | None = Query(default=None),
    routeFamily: str | None = Query(default=None),
    since: str | None = Query(default=None),
    limit: int = Query(default=50),
    runtime_pilot_enabled: bool = Query(default=False, alias="runtimePilotEnabled"),
    runtime_pilot_fallback_evaluation_enabled: bool = Query(
        default=False,
        alias="runtimePilotFallbackEvaluationEnabled",
    ),
    admin_probe_pilot_evidence: bool = Query(default=False, alias="adminProbePilotEvidence"),
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
) -> ProviderSlaReadinessResponse:
    safe_provider = _safe_filter(provider)
    safe_route = _safe_filter(routeFamily)
    since_dt = _parse_since(since) or (datetime.now() - timedelta(hours=24))
    safe_limit = _safe_limit(limit)
    observer = ProviderCircuitObserver()
    live_config = OptionsLiveProviderConfig.from_env()
    items: list[ProviderSlaReadinessItem] = []
    include_runtime_pilot = bool(runtime_pilot_enabled or runtime_pilot_fallback_evaluation_enabled)
    include_admin_probe_pilot_evidence = bool(admin_probe_pilot_evidence)

    include_options = safe_route in (None, _OPTIONS_ROUTE_FAMILY)
    option_providers = sorted(LIVE_OPTIONS_PROVIDER_NAMES)
    if safe_provider:
        option_providers = [name for name in option_providers if name == safe_provider]
    if include_options:
        for provider_name in option_providers:
            preflight = build_options_provider_live_readiness_preflight(provider_name, config=live_config)
            diagnostics = observer.build_sla_readiness_diagnostics(
                provider=provider_name,
                provider_category=_OPTIONS_PROVIDER_CATEGORY,
                route_family=_OPTIONS_ROUTE_FAMILY,
                observed_since=since_dt,
                limit=safe_limit,
                controlled_provider_categories=_STAGED_PROVIDER_CIRCUIT_CATEGORIES,
                controlled_route_families=_STAGED_PROVIDER_CIRCUIT_ROUTE_FAMILIES,
            )
            runtime_pilot = (
                _runtime_pilot_projection(
                    diagnostics,
                    pilot_enabled=runtime_pilot_enabled,
                    fallback_evaluation_enabled=runtime_pilot_fallback_evaluation_enabled,
                )
                if include_runtime_pilot
                else None
            )
            admin_probe_evidence = (
                _admin_probe_pilot_evidence_projection(
                    observer,
                    provider=provider_name,
                    provider_category=_OPTIONS_PROVIDER_CATEGORY,
                    route_family=_OPTIONS_ROUTE_FAMILY,
                )
                if include_admin_probe_pilot_evidence
                else None
            )
            items.append(
                _sla_item_from_diagnostics(
                    diagnostics,
                    preflight=preflight,
                    runtime_pilot=runtime_pilot,
                    admin_probe_pilot_evidence=admin_probe_evidence,
                )
            )

    for observed_provider, observed_category, observed_route in _observed_provider_dimensions(
        provider=safe_provider,
        route_family=safe_route,
        since_dt=since_dt,
        limit=safe_limit,
    ):
        if (observed_provider, observed_category, observed_route) in {
            (item.provider, item.provider_category, item.route_family) for item in items
        }:
            continue
        diagnostics = observer.build_sla_readiness_diagnostics(
            provider=observed_provider,
            provider_category=observed_category,
            route_family=observed_route,
            observed_since=since_dt,
            limit=safe_limit,
            controlled_provider_categories=_STAGED_PROVIDER_CIRCUIT_CATEGORIES,
            controlled_route_families=_STAGED_PROVIDER_CIRCUIT_ROUTE_FAMILIES,
        )
        runtime_pilot = (
            _runtime_pilot_projection(
                diagnostics,
                pilot_enabled=runtime_pilot_enabled,
                fallback_evaluation_enabled=runtime_pilot_fallback_evaluation_enabled,
            )
            if include_runtime_pilot
            else None
        )
        admin_probe_evidence = (
            _admin_probe_pilot_evidence_projection(
                observer,
                provider=observed_provider,
                provider_category=observed_category,
                route_family=observed_route,
            )
            if include_admin_probe_pilot_evidence
            else None
        )
        items.append(
            _sla_item_from_diagnostics(
                diagnostics,
                runtime_pilot=runtime_pilot,
                admin_probe_pilot_evidence=admin_probe_evidence,
            )
        )

    filters = {"provider": safe_provider, "routeFamily": safe_route, "since": since or since_dt.isoformat()}
    data_sources = "provider_quota_windows,provider_circuit_events,options_live_provider_preflight"
    if include_admin_probe_pilot_evidence:
        data_sources = f"{data_sources},provider_admin_probe_pilot_evidence"
    return ProviderSlaReadinessResponse(
        generatedAt=datetime.now().isoformat(),
        items=items[:safe_limit],
        metadata=_metadata(
            table=data_sources,
            limit=safe_limit,
            filters=filters,
        ),
    )
