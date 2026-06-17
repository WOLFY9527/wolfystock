# -*- coding: utf-8 -*-
"""Portfolio endpoints (P0 core account + snapshot workflow)."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from api.deps import CurrentUser, get_current_user
from api.v1.errors import safe_api_error
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.portfolio import (
    PortfolioAccountCreateRequest,
    PortfolioAccountDeleteResponse,
    PortfolioAccountItem,
    PortfolioAccountListResponse,
    PortfolioAccountUpdateRequest,
    PortfolioBrokerConnectionCreateRequest,
    PortfolioBrokerConnectionItem,
    PortfolioBrokerConnectionListResponse,
    PortfolioBrokerConnectionUpdateRequest,
    PortfolioCashLedgerListResponse,
    PortfolioCashLedgerCreateRequest,
    PortfolioCorporateActionListResponse,
    PortfolioCorporateActionCreateRequest,
    PortfolioDeleteResponse,
    PortfolioEventCreatedResponse,
    PortfolioFxRefreshResponse,
    PortfolioLiveFxRateResponse,
    PortfolioImportBrokerListResponse,
    PortfolioImportCommitResponse,
    PortfolioImportParseResponse,
    PortfolioImportTradeItem,
    PortfolioIbkrSyncRequest,
    PortfolioIbkrSyncResponse,
    PortfolioHistoryCoverage,
    PortfolioHistoryResponse,
    PortfolioHistorySnapshotItem,
    PortfolioRiskResponse,
    PortfolioScenarioRiskRequest,
    PortfolioScenarioRiskResponse,
    PortfolioSnapshotResponse,
    PortfolioStructureReviewResponse,
    PortfolioTradeCreateRequest,
    PortfolioTradeListItem,
    PortfolioTradeListResponse,
    PortfolioTradeUpdateRequest,
)
from src.services.fx_rate_service import default_fx_rate_service
from src.repositories.portfolio_repo import PortfolioRepository
from src.services.portfolio_import_service import PortfolioImportService
from src.services.portfolio_ibkr_sync_service import PortfolioIbkrSyncError, PortfolioIbkrSyncService
from src.services.portfolio_risk_service import PortfolioRiskService
from src.services.portfolio_scenario_risk import PortfolioScenarioRiskService
from src.services.portfolio_service import (
    PortfolioBusyError,
    PortfolioConflictError,
    PortfolioOversellError,
    PortfolioService,
)
from src.services.portfolio_structure_review_service import PortfolioStructureReviewService
from src.services.execution_log_service import ExecutionLogService
from src.utils.security import sanitize_message

logger = logging.getLogger(__name__)

router = APIRouter()

IMPORT_VALIDATION_ERROR_MESSAGE = "Portfolio import request could not be processed."
IMPORT_CONFLICT_ERROR_MESSAGE = "Portfolio import conflicts with existing records."
IMPORT_INTERNAL_ERROR_MESSAGE = "Portfolio import is temporarily unavailable. Please retry later."
PORTFOLIO_VALIDATION_ERROR_MESSAGE = "Portfolio request could not be processed."
PORTFOLIO_INTERNAL_ERROR_MESSAGE = "Portfolio data is temporarily unavailable. Please retry later."
IMPORT_ARTIFACT_REDACTED = "<redacted>"
_IMPORT_ARTIFACT_URL_RE = re.compile(r"\bhttps?://[^\s\"'<>]+", re.IGNORECASE)
_IMPORT_ARTIFACT_SENSITIVE_TEXT_RE = re.compile(
    r"\b(?:broker[-_\s]?account[-_\s]?(?:ref|id|label|name)|account[-_\s]?(?:ref|label)|"
    r"order[-_\s]?(?:id|ref)|request[-_\s]?id|exec(?:ution)?[-_\s]?id|trade[-_\s]?uid|"
    r"dedup[-_\s]?hash|file[-_\s]?fingerprint|import[-_\s]?fingerprint|raw[-_\s]?payload)\b"
    r"\s*[:=]?",
    re.IGNORECASE,
)
_IMPORT_ARTIFACT_SECRET_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "password",
    "private_key",
    "secret",
    "session_token",
    "sessiontoken",
    "token",
)
_ADMIN_DIAGNOSTIC_CAMEL_BOUNDARY_RE = re.compile(r"(?<!^)(?=[A-Z])")
PORTFOLIO_SNAPSHOT_CONSUMER_SCHEMA_VERSION = "portfolio_snapshot_consumer_v1"
PORTFOLIO_RISK_CONSUMER_SCHEMA_VERSION = "portfolio_risk_consumer_v1"
PORTFOLIO_CONSUMER_NO_ADVICE_DISCLOSURE = (
    "Observation-only portfolio research context; not personalized financial advice and not an instruction."
)


def _is_admin_only_diagnostic_key(key: Any) -> bool:
    text = str(key or "").strip()
    if not text:
        return False
    normalized = text.replace("-", "_")
    normalized_lower = normalized.lower()
    if normalized_lower == "admin_diagnostics" or normalized_lower.startswith("admin_"):
        return True
    snake_key = _ADMIN_DIAGNOSTIC_CAMEL_BOUNDARY_RE.sub("_", text).replace("-", "_").lower()
    return snake_key == "admin_diagnostics" or snake_key.startswith("admin_")


def _redact_consumer_admin_diagnostics(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact_consumer_admin_diagnostics(child)
            for key, child in value.items()
            if not _is_admin_only_diagnostic_key(key)
        }
    if isinstance(value, list):
        return [_redact_consumer_admin_diagnostics(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_consumer_admin_diagnostics(item) for item in value)
    return value


def _portfolio_consumer_safety_envelope(data: dict[str, Any], *, schema_version: str) -> dict[str, Any]:
    payload = dict(data or {})
    data_status = _safe_status(payload.get("data_status"), default="unknown")
    calculation_status = _safe_status(payload.get("calculation_status"), default="unknown")
    freshness_status = data_status
    availability = payload.get("availability") if isinstance(payload.get("availability"), dict) else {}
    metrics_ready = bool(availability.get("metrics_ready")) if availability else calculation_status == "ready"
    evidence_gaps = _portfolio_consumer_evidence_gaps(payload, data_status=data_status)
    degraded_inputs = _portfolio_consumer_degraded_inputs(
        payload,
        data_status=data_status,
        calculation_status=calculation_status,
        evidence_gaps=evidence_gaps,
    )
    payload.update(
        {
            "schemaVersion": schema_version,
            "noAdviceDisclosure": PORTFOLIO_CONSUMER_NO_ADVICE_DISCLOSURE,
            "observationOnly": True,
            "decisionGrade": False,
            "consumerIssues": _portfolio_consumer_issues(
                data_status=data_status,
                evidence_gaps=evidence_gaps,
                degraded_inputs=degraded_inputs,
            ),
            "evidenceGaps": evidence_gaps,
            "degradedInputs": degraded_inputs,
            "dataQuality": {
                "status": data_status,
                "freshnessStatus": freshness_status,
                "calculationStatus": calculation_status,
                "reason": _safe_status(availability.get("reason"), default=data_status),
                "metricsReady": metrics_ready,
                "accountCount": _safe_int(availability.get("account_count", payload.get("account_count"))),
                "positionCount": _safe_int(availability.get("position_count")),
                "evidenceGapCount": len(evidence_gaps),
                "degradedInputCount": len(degraded_inputs),
                "observationOnly": True,
                "decisionGrade": False,
                "sourceAuthorityState": _safe_status(payload.get("sourceAuthorityState"), default="unknown"),
                "fxFreshnessState": _safe_status(payload.get("fxFreshnessState"), default="unknown"),
                "confidenceCapValue": _confidence_cap_value(payload),
            },
            "freshnessStatus": freshness_status,
        }
    )
    return payload


def _safe_status(value: Any, *, default: str) -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    return text or default


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _confidence_cap_value(payload: dict[str, Any]) -> Optional[int]:
    confidence_cap = payload.get("confidenceCap")
    if not isinstance(confidence_cap, dict):
        return None
    try:
        return max(0, min(100, int(confidence_cap.get("value"))))
    except (TypeError, ValueError):
        return None


def _portfolio_consumer_evidence_gaps(payload: dict[str, Any], *, data_status: str) -> list[str]:
    gaps: list[str] = []
    if data_status == "no_account":
        _append_gap(gaps, "portfolio_account")
    elif data_status == "no_positions":
        _append_gap(gaps, "portfolio_positions")
    elif data_status == "provider_unavailable":
        _append_gap(gaps, "valuation_inputs")
    elif data_status == "stale_or_cached":
        _append_gap(gaps, "freshness")
    elif data_status in {"data_unavailable", "calculation_unavailable"}:
        _append_gap(gaps, "portfolio_metrics")

    if _safe_status(payload.get("fxFreshnessState"), default="unknown") in {"stale", "unavailable"}:
        _append_gap(gaps, "fx_freshness")
    if _safe_status(payload.get("holdingsLineageState"), default="unknown") in {"missing", "partial"}:
        _append_gap(gaps, "position_lineage")
    if _safe_status(payload.get("cashLedgerCompletenessState"), default="unknown") in {"missing", "partial"}:
        _append_gap(gaps, "cash_ledger")
    if _safe_status(payload.get("benchmarkMappingState"), default="unknown") == "unmapped":
        _append_gap(gaps, "benchmark_mapping")
    if _safe_status(payload.get("factorMappingState"), default="unknown") == "unmapped":
        _append_gap(gaps, "factor_mapping")
    return gaps


def _append_gap(gaps: list[str], value: str) -> None:
    if value and value not in gaps:
        gaps.append(value)


def _portfolio_consumer_degraded_inputs(
    payload: dict[str, Any],
    *,
    data_status: str,
    calculation_status: str,
    evidence_gaps: list[str],
) -> list[dict[str, str]]:
    degraded: list[dict[str, str]] = []
    availability = payload.get("availability") if isinstance(payload.get("availability"), dict) else {}
    reason = _safe_status(availability.get("reason"), default=data_status)
    if data_status != "ready":
        section, message = _portfolio_status_degraded_message(data_status)
        degraded.append(
            {
                "section": section,
                "status": data_status,
                "reason": reason,
                "message": message,
            }
        )
    if calculation_status == "calculation_unavailable" and data_status not in {"no_account", "no_positions"}:
        degraded.append(
            {
                "section": "calculation",
                "status": calculation_status,
                "reason": "metrics_unavailable",
                "message": "Portfolio metrics are unavailable for this observation.",
            }
        )
    for gap in evidence_gaps:
        if gap in {"benchmark_mapping", "factor_mapping"}:
            degraded.append(
                {
                    "section": gap,
                    "status": "limited",
                    "reason": "mapping_unavailable",
                    "message": "Comparative research context is not mapped for this observation.",
                }
            )
    return degraded


def _portfolio_status_degraded_message(data_status: str) -> tuple[str, str]:
    if data_status == "no_account":
        return "portfolio_account", "Portfolio account evidence is not available for this observation."
    if data_status == "no_positions":
        return "portfolio_positions", "Portfolio position evidence is not available for this observation."
    if data_status == "provider_unavailable":
        return "valuation_inputs", "Some valuation inputs use existing fallback metadata."
    if data_status == "stale_or_cached":
        return "freshness", "Snapshot freshness is limited by cached or stale inputs."
    return "portfolio_metrics", "Portfolio evidence is limited for this observation."


def _portfolio_consumer_issues(
    *,
    data_status: str,
    evidence_gaps: list[str],
    degraded_inputs: list[dict[str, str]],
) -> list[dict[str, str]]:
    if data_status in {"no_account", "no_positions", "data_unavailable", "calculation_unavailable"}:
        return [
            {
                "label": "Evidence unavailable",
                "message": "Portfolio evidence is not available for this observation.",
                "severity": "warning",
                "category": "evidence",
            }
        ]
    if data_status == "stale_or_cached":
        return [
            {
                "label": "Freshness is limited",
                "message": "Some portfolio inputs rely on cached or stale evidence.",
                "severity": "warning",
                "category": "freshness",
            }
        ]
    if data_status == "provider_unavailable":
        return [
            {
                "label": "Evidence needs review",
                "message": "Some valuation evidence is unavailable or uses fallback metadata.",
                "severity": "warning",
                "category": "evidence",
            }
        ]
    if degraded_inputs or evidence_gaps:
        return [
            {
                "label": "Research context limited",
                "message": "Some comparative or freshness evidence is not fully mapped.",
                "severity": "info",
                "category": "evidence",
            }
        ]
    return []


def _get_portfolio_service(current_user: CurrentUser) -> PortfolioService:
    return PortfolioService(owner_id=current_user.user_id)


def _get_portfolio_structure_review_service() -> PortfolioStructureReviewService:
    return PortfolioStructureReviewService()


def _actor(current_user: CurrentUser) -> dict:
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "role": "admin" if current_user.is_admin else "user",
        "actor_type": "admin" if current_user.is_admin else "user",
        "session_id": current_user.session_id,
    }


def _record_portfolio_audit(
    *,
    action: str,
    message: str,
    current_user: CurrentUser,
    account_id: Optional[int],
    symbol: Optional[str] = None,
    currency: Optional[str] = None,
    record_id: Optional[object] = None,
    detail: Optional[dict] = None,
) -> None:
    try:
        ExecutionLogService().record_portfolio_event(
            action=action,
            message=message,
            actor=_actor(current_user),
            account_id=account_id,
            symbol=symbol,
            currency=currency,
            record_id=record_id,
            detail=detail,
        )
    except Exception as exc:
        logger.warning("Record portfolio audit log failed: %s", exc)


def _record_user_write_audit(
    *,
    event_type: str,
    message: str,
    current_user: CurrentUser,
    target_type: str,
    target_id: Optional[object] = None,
    metadata: Optional[dict] = None,
) -> None:
    try:
        ExecutionLogService().record_user_write_action(
            event_type=event_type,
            message=message,
            actor=_actor(current_user),
            domain="portfolio",
            target_type=target_type,
            target_id=target_id,
            status="completed",
            metadata={"route_family": "portfolio", **(metadata or {})},
        )
    except Exception as exc:
        logger.warning("Record portfolio user action audit failed: %s", exc)


def _assert_owned_request(owner_id: Optional[str], current_user: CurrentUser) -> None:
    normalized_owner_id = str(owner_id or "").strip()
    if normalized_owner_id and normalized_owner_id != current_user.user_id:
        raise ValueError("owner_id must match the authenticated user")


def _bad_request(exc: Exception) -> HTTPException:
    return safe_api_error(
        status_code=400,
        error="validation_error",
        message=str(exc) or PORTFOLIO_VALIDATION_ERROR_MESSAGE,
        fallback_message=PORTFOLIO_VALIDATION_ERROR_MESSAGE,
    )


def _internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error(f"{message}: {exc}", exc_info=True)
    return safe_api_error(
        status_code=500,
        error="internal_error",
        message=PORTFOLIO_INTERNAL_ERROR_MESSAGE,
        retryable=True,
    )


def _conflict_error(*, error: str, message: str) -> HTTPException:
    return safe_api_error(
        status_code=409,
        error=error,
        message=message,
        fallback_message="Portfolio request conflicts with current portfolio state.",
    )


def _ibkr_sync_error(exc: PortfolioIbkrSyncError) -> HTTPException:
    return safe_api_error(
        status_code=max(400, int(exc.status_code or 400)),
        error=exc.code,
        message=sanitize_message(str(exc)),
        fallback_message="Portfolio broker sync could not be processed.",
    )


def _portfolio_display_handle(value: Any, *, prefix: str, namespace: Optional[str] = None) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    seed = f"{namespace or prefix}:{text}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:12]}"


def _normalized_import_artifact_key(key: Any) -> tuple[str, str]:
    normalized = str(key or "").strip().lower().replace("-", "_").replace(" ", "_")
    compact = normalized.replace("_", "")
    return normalized, compact


def _import_artifact_secret_key(key: Any) -> bool:
    normalized, compact = _normalized_import_artifact_key(key)
    return any(marker in normalized or marker in compact for marker in _IMPORT_ARTIFACT_SECRET_KEY_MARKERS)


def _import_artifact_handle_prefix_for_key(key: Any) -> Optional[str]:
    normalized, compact = _normalized_import_artifact_key(key)
    if any(marker in normalized or marker in compact for marker in ("provider_url", "api_base_url", "url")):
        return "url"
    if any(marker in normalized or marker in compact for marker in ("request_id", "requestid")):
        return "req"
    if any(marker in normalized or marker in compact for marker in ("raw_payload", "raw_payload_label", "payload")):
        return "payload"
    if any(marker in normalized or marker in compact for marker in ("import_file_label", "import_file_name", "file_label", "file_name")):
        return "file"
    if any(marker in normalized or marker in compact for marker in ("file_fingerprint", "filefingerprint")):
        return "file"
    if any(marker in normalized or marker in compact for marker in ("import_fingerprint", "fingerprint", "dedup_hash", "deduphash")):
        return "import"
    if any(marker in normalized or marker in compact for marker in ("trade_uid", "tradeuid")):
        return "trade"
    if any(marker in normalized or marker in compact for marker in ("execution_id", "executionid", "exec_id", "execid")):
        return "exec"
    if any(marker in normalized or marker in compact for marker in ("order_id", "order_ref", "orderid", "orderref")):
        return "order"
    if any(marker in normalized or marker in compact for marker in ("connection_name", "connectionname")):
        return "conn"
    if any(marker in normalized or marker in compact for marker in ("broker_name", "brokername")):
        return "broker"
    if any(
        marker in normalized or marker in compact
        for marker in (
            "account_label",
            "account_name",
            "account_ref",
            "accountlabel",
            "accountname",
            "accountref",
            "broker_account",
            "brokeraccount",
        )
    ):
        return "acct"
    return None


def _import_artifact_handle_prefix_for_text(value: str) -> Optional[str]:
    text = str(value or "")
    if _IMPORT_ARTIFACT_URL_RE.search(text):
        return "url"
    if _IMPORT_ARTIFACT_SENSITIVE_TEXT_RE.search(text):
        return "payload"
    return None


def _sanitize_import_artifact_text(value: str) -> str:
    text = sanitize_message(str(value or ""))
    handle_prefix = _import_artifact_handle_prefix_for_text(text)
    if handle_prefix:
        return _portfolio_display_handle(text, prefix=handle_prefix) or IMPORT_ARTIFACT_REDACTED
    return text


def _sanitize_import_artifact_value(
    value: Any,
    *,
    handle_prefix: Optional[str] = None,
    force_redact: bool = False,
) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            child_prefix = _import_artifact_handle_prefix_for_key(key_text)
            sanitized[key_text] = _sanitize_import_artifact_value(
                child,
                handle_prefix=handle_prefix or child_prefix,
                force_redact=force_redact or _import_artifact_secret_key(key_text),
            )
        return sanitized
    if isinstance(value, list):
        return [
            _sanitize_import_artifact_value(item, handle_prefix=handle_prefix, force_redact=force_redact)
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _sanitize_import_artifact_value(item, handle_prefix=handle_prefix, force_redact=force_redact)
            for item in value
        )
    if force_redact:
        return "***"
    if handle_prefix:
        handle = _portfolio_display_handle(value, prefix=handle_prefix)
        return handle if handle is not None else value
    if isinstance(value, str):
        return _sanitize_import_artifact_text(value)
    return value


def _build_broker_connection_item(row: dict) -> PortfolioBrokerConnectionItem:
    payload = dict(row)
    display_fields = {
        "portfolio_account_name": "acct",
        "broker_name": "broker",
        "connection_name": "conn",
        "broker_account_ref": "acct",
        "last_import_fingerprint": "import",
    }
    for field, prefix in display_fields.items():
        if payload.get(field):
            payload[field] = _portfolio_display_handle(payload[field], prefix=prefix)
    payload["sync_metadata"] = _sanitize_import_artifact_value(dict(payload.get("sync_metadata") or {}))
    return PortfolioBrokerConnectionItem(**payload)


def _build_ibkr_sync_response(data: dict) -> PortfolioIbkrSyncResponse:
    payload = dict(data)
    if payload.get("broker_account_ref"):
        payload["broker_account_ref"] = _portfolio_display_handle(payload["broker_account_ref"], prefix="acct")
    if payload.get("connection_name"):
        payload["connection_name"] = _portfolio_display_handle(payload["connection_name"], prefix="conn")
    if payload.get("api_base_url"):
        payload["api_base_url"] = _portfolio_display_handle(payload["api_base_url"], prefix="url")
    payload["warnings"] = _sanitize_import_artifact_value(list(payload.get("warnings", [])))
    return PortfolioIbkrSyncResponse(**payload)


def _raw_sync_request_value(value: Optional[str], *, handle_prefix: str) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(rf"{re.escape(handle_prefix)}_[a-f0-9]{{12}}", text):
        return None
    return text


def _import_bad_request() -> HTTPException:
    return safe_api_error(
        status_code=400,
        error="validation_error",
        message=IMPORT_VALIDATION_ERROR_MESSAGE,
    )


def _import_conflict_error() -> HTTPException:
    return safe_api_error(
        status_code=409,
        error="conflict",
        message=IMPORT_CONFLICT_ERROR_MESSAGE,
    )


def _import_internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error("%s: %s", message, exc, exc_info=True)
    return safe_api_error(
        status_code=500,
        error="internal_error",
        message=IMPORT_INTERNAL_ERROR_MESSAGE,
        retryable=True,
    )


def _serialize_import_record(item: dict) -> PortfolioImportTradeItem:
    payload = dict(item)
    trade_date = payload.get("trade_date")
    if isinstance(trade_date, date):
        payload["trade_date"] = trade_date.isoformat()
    else:
        payload["trade_date"] = str(trade_date)
    payload = _sanitize_import_artifact_value(payload)
    return PortfolioImportTradeItem(**payload)


def _serialize_import_cash_entry(item: dict) -> dict:
    payload = dict(item)
    event_date = payload.get("event_date")
    if isinstance(event_date, date):
        payload["event_date"] = event_date.isoformat()
    else:
        payload["event_date"] = str(event_date)
    return _sanitize_import_artifact_value(payload)


def _serialize_import_corporate_action(item: dict) -> dict:
    payload = dict(item)
    effective_date = payload.get("effective_date")
    if isinstance(effective_date, date):
        payload["effective_date"] = effective_date.isoformat()
    else:
        payload["effective_date"] = str(effective_date)
    return _sanitize_import_artifact_value(payload)


def _build_import_parse_response(parsed: dict) -> PortfolioImportParseResponse:
    return PortfolioImportParseResponse(
        broker=parsed["broker"],
        record_count=parsed["record_count"],
        skipped_count=parsed["skipped_count"],
        error_count=parsed["error_count"],
        records=[_serialize_import_record(item) for item in parsed.get("records", [])],
        cash_record_count=int(parsed.get("cash_record_count", 0)),
        cash_entries=[_serialize_import_cash_entry(item) for item in parsed.get("cash_entries", [])],
        corporate_action_count=int(parsed.get("corporate_action_count", 0)),
        corporate_actions=[
            _serialize_import_corporate_action(item) for item in parsed.get("corporate_actions", [])
        ],
        warnings=_sanitize_import_artifact_value(list(parsed.get("warnings", []))),
        metadata=_sanitize_import_artifact_value(dict(parsed.get("metadata", {}))),
        errors=_sanitize_import_artifact_value(list(parsed.get("errors", []))),
    )


def _build_import_commit_response(result: dict) -> PortfolioImportCommitResponse:
    payload = dict(result)
    payload["warnings"] = _sanitize_import_artifact_value(list(payload.get("warnings", [])))
    payload["metadata"] = _sanitize_import_artifact_value(dict(payload.get("metadata", {})))
    payload["errors"] = _sanitize_import_artifact_value(list(payload.get("errors", [])))
    return PortfolioImportCommitResponse(**payload)


def _normalize_cost_method(cost_method: str) -> str:
    method = str(cost_method or "").strip().lower()
    if method not in {"fifo", "avg"}:
        raise ValueError("cost_method must be fifo or avg")
    return method


def _date_to_str(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _datetime_to_str(value: object) -> Optional[str]:
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return str(value)


def _serialize_history_item(row: object) -> PortfolioHistorySnapshotItem:
    return PortfolioHistorySnapshotItem(
        account_id=int(getattr(row, "account_id")),
        snapshot_date=_date_to_str(getattr(row, "snapshot_date")),
        cost_method=str(getattr(row, "cost_method")),
        base_currency=str(getattr(row, "base_currency")),
        total_cash=float(getattr(row, "total_cash")),
        total_market_value=float(getattr(row, "total_market_value")),
        total_equity=float(getattr(row, "total_equity")),
        realized_pnl=float(getattr(row, "realized_pnl")),
        unrealized_pnl=float(getattr(row, "unrealized_pnl")),
        fee_total=float(getattr(row, "fee_total")),
        tax_total=float(getattr(row, "tax_total")),
        fx_stale=bool(getattr(row, "fx_stale")),
        created_at=_datetime_to_str(getattr(row, "created_at", None)),
        updated_at=_datetime_to_str(getattr(row, "updated_at", None)),
    )


def _build_history_coverage(
    *,
    items: list[PortfolioHistorySnapshotItem],
    date_from: Optional[date],
    date_to: Optional[date],
) -> PortfolioHistoryCoverage:
    point_count = len(items)
    warnings: list[str] = []
    if point_count == 0:
        warnings.append("history_no_stored_snapshots")
    elif point_count < 2:
        warnings.append("history_insufficient_points")

    insufficient_data = point_count < 2
    account_ids = {item.account_id for item in items}
    snapshot_dates = [item.snapshot_date for item in items]
    return PortfolioHistoryCoverage(
        status="insufficient_data" if insufficient_data else "available",
        point_count=point_count,
        insufficient_data=insufficient_data,
        sparse=insufficient_data,
        warnings=warnings,
        requested_date_from=_date_to_str(date_from),
        requested_date_to=_date_to_str(date_to),
        first_snapshot_date=snapshot_dates[0] if snapshot_dates else None,
        last_snapshot_date=snapshot_dates[-1] if snapshot_dates else None,
        account_count=len(account_ids),
    )


@router.post(
    "/accounts",
    response_model=PortfolioAccountItem,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Create portfolio account",
)
def create_account(
    request: PortfolioAccountCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioAccountItem:
    service = _get_portfolio_service(current_user)
    try:
        _assert_owned_request(request.owner_id, current_user)
        row = service.create_account(
            name=request.name,
            broker=request.broker,
            market=request.market,
            base_currency=request.base_currency,
            owner_id=current_user.user_id,
        )
        _record_user_write_audit(
            event_type="portfolio.account_created",
            message="Portfolio account created",
            current_user=current_user,
            target_type="portfolio_account",
            target_id=row.get("id"),
            metadata={
                "market": str(row.get("market") or "").upper() or None,
                "base_currency": str(row.get("base_currency") or "").upper() or None,
            },
        )
        return PortfolioAccountItem(**row)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create account failed", exc)


@router.get(
    "/accounts",
    response_model=PortfolioAccountListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="List portfolio accounts",
)
def list_accounts(
    include_inactive: bool = Query(False, description="Whether to include inactive accounts"),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioAccountListResponse:
    service = _get_portfolio_service(current_user)
    try:
        rows = service.list_accounts(include_inactive=include_inactive)
        return PortfolioAccountListResponse(accounts=[PortfolioAccountItem(**item) for item in rows])
    except Exception as exc:
        raise _internal_error("List accounts failed", exc)


@router.put(
    "/accounts/{account_id}",
    response_model=PortfolioAccountItem,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Update portfolio account",
)
def update_account(
    account_id: int,
    request: PortfolioAccountUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioAccountItem:
    service = _get_portfolio_service(current_user)
    try:
        _assert_owned_request(request.owner_id, current_user)
        updated = service.update_account(
            account_id,
            name=request.name,
            broker=request.broker,
            market=request.market,
            base_currency=request.base_currency,
            owner_id=current_user.user_id if request.owner_id is not None else None,
            is_active=request.is_active,
        )
        if updated is None:
            raise safe_api_error(
                status_code=404,
                error="not_found",
                message=f"Account not found: {account_id}",
            )
        _record_user_write_audit(
            event_type="portfolio.account_updated",
            message="Portfolio account updated",
            current_user=current_user,
            target_type="portfolio_account",
            target_id=account_id,
            metadata={
                "market": str(updated.get("market") or "").upper() or None,
                "base_currency": str(updated.get("base_currency") or "").upper() or None,
                "is_active": bool(updated.get("is_active")),
            },
        )
        return PortfolioAccountItem(**updated)
    except HTTPException:
        raise
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Update account failed", exc)


@router.delete(
    "/accounts/{account_id}",
    response_model=PortfolioAccountDeleteResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Deactivate portfolio account",
)
def delete_account(account_id: int, current_user: CurrentUser = Depends(get_current_user)) -> PortfolioAccountDeleteResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.delete_account(account_id)
        if data is None:
            raise safe_api_error(
                status_code=404,
                error="not_found",
                message=f"Account not found: {account_id}",
            )
        _record_portfolio_audit(
            action="account_archive",
            message="Portfolio account archived",
            current_user=current_user,
            account_id=account_id,
            detail={"delete_mode": data["delete_mode"], "next_account_id": data["next_account_id"]},
        )
        _record_user_write_audit(
            event_type="portfolio.account_deleted",
            message="Portfolio account archived",
            current_user=current_user,
            target_type="portfolio_account",
            target_id=account_id,
            metadata={"delete_mode": data["delete_mode"]},
        )
        return PortfolioAccountDeleteResponse(**data)
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("Deactivate account failed", exc)


@router.get(
    "/fx-rate",
    response_model=PortfolioLiveFxRateResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Fetch cached live FX rate",
)
def get_fx_rate(
    base: str = Query(..., min_length=3, max_length=8),
    quote: str = Query(..., min_length=3, max_length=8),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioLiveFxRateResponse:
    try:
        return PortfolioLiveFxRateResponse(**default_fx_rate_service.fetch_rate(base, quote))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Fetch FX rate failed", exc)


@router.post(
    "/fx-rate/refresh",
    response_model=PortfolioLiveFxRateResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Refresh one live FX pair",
)
def refresh_fx_rate(
    base: str = Query(..., min_length=3, max_length=8),
    quote: str = Query(..., min_length=3, max_length=8),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioLiveFxRateResponse:
    try:
        return PortfolioLiveFxRateResponse(
            **default_fx_rate_service.fetch_rate(base, quote, force_refresh=True)
        )
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Refresh FX rate failed", exc)


@router.post(
    "/broker-connections",
    response_model=PortfolioBrokerConnectionItem,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Create user-owned broker connection",
)
def create_broker_connection(
    request: PortfolioBrokerConnectionCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioBrokerConnectionItem:
    service = _get_portfolio_service(current_user)
    try:
        row = service.create_broker_connection(
            portfolio_account_id=request.portfolio_account_id,
            broker_type=request.broker_type,
            broker_name=request.broker_name,
            connection_name=request.connection_name,
            broker_account_ref=request.broker_account_ref,
            import_mode=request.import_mode,
            status=request.status,
            sync_metadata=request.sync_metadata,
            owner_id=current_user.user_id,
        )
        return _build_broker_connection_item(row)
    except PortfolioConflictError as exc:
        raise _conflict_error(error="conflict", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create broker connection failed", exc)


@router.get(
    "/broker-connections",
    response_model=PortfolioBrokerConnectionListResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List user-owned broker connections",
)
def list_broker_connections(
    portfolio_account_id: Optional[int] = Query(None, description="Optional account id"),
    broker_type: Optional[str] = Query(None, description="Optional broker type"),
    status: Optional[str] = Query(None, description="Optional status filter"),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioBrokerConnectionListResponse:
    service = _get_portfolio_service(current_user)
    try:
        rows = service.list_broker_connections(
            portfolio_account_id=portfolio_account_id,
            broker_type=broker_type,
            status=status,
        )
        return PortfolioBrokerConnectionListResponse(
            connections=[_build_broker_connection_item(item) for item in rows]
        )
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List broker connections failed", exc)


@router.put(
    "/broker-connections/{connection_id}",
    response_model=PortfolioBrokerConnectionItem,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Update user-owned broker connection",
)
def update_broker_connection(
    connection_id: int,
    request: PortfolioBrokerConnectionUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioBrokerConnectionItem:
    service = _get_portfolio_service(current_user)
    try:
        updated = service.update_broker_connection(
            connection_id,
            portfolio_account_id=request.portfolio_account_id,
            broker_name=request.broker_name,
            connection_name=request.connection_name,
            broker_account_ref=request.broker_account_ref,
            import_mode=request.import_mode,
            status=request.status,
            sync_metadata=request.sync_metadata,
        )
        if updated is None:
            raise safe_api_error(
                status_code=404,
                error="not_found",
                message=f"Broker connection not found: {connection_id}",
            )
        return _build_broker_connection_item(updated)
    except HTTPException:
        raise
    except PortfolioConflictError as exc:
        raise _conflict_error(error="conflict", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Update broker connection failed", exc)


@router.post(
    "/sync/ibkr",
    response_model=PortfolioIbkrSyncResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Trigger read-only IBKR portfolio sync into the current user's account",
)
def sync_ibkr_account_state(
    request: PortfolioIbkrSyncRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioIbkrSyncResponse:
    sync_service = PortfolioIbkrSyncService(portfolio_service=_get_portfolio_service(current_user))
    try:
        data = sync_service.sync_read_only_account_state(
            account_id=request.account_id,
            broker_connection_id=request.broker_connection_id,
            broker_account_ref=_raw_sync_request_value(request.broker_account_ref, handle_prefix="acct"),
            session_token=request.session_token,
            api_base_url=_raw_sync_request_value(request.api_base_url, handle_prefix="url"),
            verify_ssl=request.verify_ssl,
        )
        return _build_ibkr_sync_response(data)
    except PortfolioIbkrSyncError as exc:
        raise _ibkr_sync_error(exc)
    except PortfolioConflictError as exc:
        raise _conflict_error(error="conflict", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        logger.error("IBKR sync failed: %s", exc, exc_info=True)
        raise safe_api_error(
            status_code=500,
            error="ibkr_sync_internal_error",
            message="IBKR 同步暂时失败，请稍后重试。",
            retryable=True,
        )


@router.post(
    "/trades",
    response_model=PortfolioEventCreatedResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Record trade event",
)
def create_trade(
    request: PortfolioTradeCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioEventCreatedResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.record_trade(
            account_id=request.account_id,
            symbol=request.symbol,
            trade_date=request.trade_date,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            fee=request.fee,
            tax=request.tax,
            market=request.market,
            currency=request.currency,
            trade_uid=request.trade_uid,
            note=request.note,
        )
        _record_portfolio_audit(
            action=f"{request.side}_trade",
            message=f"Portfolio {request.side} trade recorded for {request.symbol}",
            current_user=current_user,
            account_id=request.account_id,
            symbol=request.symbol,
            currency=request.currency,
            record_id=data.get("id"),
            detail={"market": request.market, "quantity": request.quantity, "price": request.price},
        )
        return PortfolioEventCreatedResponse(**data)
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except PortfolioOversellError as exc:
        raise _conflict_error(error="portfolio_oversell", message=str(exc))
    except PortfolioConflictError as exc:
        raise _conflict_error(error="conflict", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create trade failed", exc)


@router.get(
    "/trades",
    response_model=PortfolioTradeListResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List trade events",
)
def list_trades(
    account_id: Optional[int] = Query(None, description="Optional account id"),
    date_from: Optional[date] = Query(None, description="Trade date from"),
    date_to: Optional[date] = Query(None, description="Trade date to"),
    symbol: Optional[str] = Query(None, description="Optional stock symbol filter"),
    side: Optional[str] = Query(None, description="Optional side filter: buy/sell"),
    include_voided: bool = Query(False, description="Whether to include voided trades"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioTradeListResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.list_trade_events(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            symbol=symbol,
            side=side,
            include_voided=include_voided,
            page=page,
            page_size=page_size,
        )
        return PortfolioTradeListResponse(**data)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List trade events failed", exc)


@router.delete(
    "/trades/{trade_id}",
    response_model=PortfolioDeleteResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Delete trade event",
)
def delete_trade(
    trade_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioDeleteResponse:
    service = _get_portfolio_service(current_user)
    try:
        ok = service.delete_trade_event(trade_id)
        if not ok:
            raise safe_api_error(
                status_code=404,
                error="not_found",
                message=f"Trade not found: {trade_id}",
            )
        _record_portfolio_audit(
            action="void_trade",
            message=f"Portfolio trade voided: {trade_id}",
            current_user=current_user,
            account_id=None,
            record_id=trade_id,
        )
        return PortfolioDeleteResponse(deleted=1, delete_mode="soft")
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("Delete trade event failed", exc)


@router.patch(
    "/trades/{trade_id}",
    response_model=PortfolioTradeListItem,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Update trade event",
)
def update_trade(
    trade_id: int,
    request: PortfolioTradeUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioTradeListItem:
    service = _get_portfolio_service(current_user)
    try:
        updated = service.update_trade_event(
            trade_id,
            account_id=request.account_id,
            symbol=request.symbol,
            trade_date=request.trade_date,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            fee=request.fee,
            tax=request.tax,
            market=request.market,
            currency=request.currency,
            note=request.note,
        )
        if updated is None:
            raise safe_api_error(
                status_code=404,
                error="not_found",
                message=f"Trade not found: {trade_id}",
            )
        _record_portfolio_audit(
            action="update_trade",
            message=f"Portfolio trade updated: {trade_id}",
            current_user=current_user,
            account_id=updated.get("account_id"),
            symbol=updated.get("symbol"),
            currency=updated.get("currency"),
            record_id=trade_id,
            detail={
                "side": updated.get("side"),
                "quantity": updated.get("quantity"),
                "price": updated.get("price"),
            },
        )
        return PortfolioTradeListItem(**updated)
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except PortfolioOversellError as exc:
        raise _conflict_error(error="portfolio_oversell", message=str(exc))
    except HTTPException:
        raise
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Update trade event failed", exc)


@router.post(
    "/cash-ledger",
    response_model=PortfolioEventCreatedResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Record cash event",
)
def create_cash_ledger(
    request: PortfolioCashLedgerCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioEventCreatedResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.record_cash_ledger(
            account_id=request.account_id,
            event_date=request.event_date,
            direction=request.direction,
            amount=request.amount,
            currency=request.currency,
            note=request.note,
        )
        _record_portfolio_audit(
            action="cash_ledger",
            message=f"Portfolio cash ledger {request.direction} recorded",
            current_user=current_user,
            account_id=request.account_id,
            currency=request.currency,
            record_id=data.get("id"),
            detail={"direction": request.direction, "amount": request.amount},
        )
        return PortfolioEventCreatedResponse(**data)
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create cash ledger event failed", exc)


@router.get(
    "/cash-ledger",
    response_model=PortfolioCashLedgerListResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List cash ledger events",
)
def list_cash_ledger(
    account_id: Optional[int] = Query(None, description="Optional account id"),
    date_from: Optional[date] = Query(None, description="Cash event date from"),
    date_to: Optional[date] = Query(None, description="Cash event date to"),
    direction: Optional[str] = Query(None, description="Optional direction filter: in/out"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioCashLedgerListResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.list_cash_ledger_events(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            direction=direction,
            page=page,
            page_size=page_size,
        )
        return PortfolioCashLedgerListResponse(**data)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List cash ledger events failed", exc)


@router.delete(
    "/cash-ledger/{entry_id}",
    response_model=PortfolioDeleteResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Delete cash ledger event",
)
def delete_cash_ledger(
    entry_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioDeleteResponse:
    service = _get_portfolio_service(current_user)
    try:
        ok = service.delete_cash_ledger_event(entry_id)
        if not ok:
            raise safe_api_error(
                status_code=404,
                error="not_found",
                message=f"Cash ledger entry not found: {entry_id}",
            )
        return PortfolioDeleteResponse(deleted=1)
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("Delete cash ledger event failed", exc)


@router.post(
    "/corporate-actions",
    response_model=PortfolioEventCreatedResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Record corporate action event",
)
def create_corporate_action(
    request: PortfolioCorporateActionCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioEventCreatedResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.record_corporate_action(
            account_id=request.account_id,
            symbol=request.symbol,
            effective_date=request.effective_date,
            action_type=request.action_type,
            market=request.market,
            currency=request.currency,
            cash_dividend_per_share=request.cash_dividend_per_share,
            split_ratio=request.split_ratio,
            note=request.note,
        )
        _record_portfolio_audit(
            action="corporate_action",
            message=f"Portfolio corporate action recorded for {request.symbol}",
            current_user=current_user,
            account_id=request.account_id,
            symbol=request.symbol,
            currency=request.currency,
            record_id=data.get("id"),
            detail={"market": request.market, "action_type": request.action_type},
        )
        return PortfolioEventCreatedResponse(**data)
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create corporate action event failed", exc)


@router.get(
    "/corporate-actions",
    response_model=PortfolioCorporateActionListResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List corporate action events",
)
def list_corporate_actions(
    account_id: Optional[int] = Query(None, description="Optional account id"),
    date_from: Optional[date] = Query(None, description="Corporate action effective date from"),
    date_to: Optional[date] = Query(None, description="Corporate action effective date to"),
    symbol: Optional[str] = Query(None, description="Optional stock symbol filter"),
    action_type: Optional[str] = Query(None, description="Optional action type filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioCorporateActionListResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.list_corporate_action_events(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            symbol=symbol,
            action_type=action_type,
            page=page,
            page_size=page_size,
        )
        return PortfolioCorporateActionListResponse(**data)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List corporate action events failed", exc)


@router.delete(
    "/corporate-actions/{action_id}",
    response_model=PortfolioDeleteResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Delete corporate action event",
)
def delete_corporate_action(
    action_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioDeleteResponse:
    service = _get_portfolio_service(current_user)
    try:
        ok = service.delete_corporate_action_event(action_id)
        if not ok:
            raise safe_api_error(
                status_code=404,
                error="not_found",
                message=f"Corporate action not found: {action_id}",
            )
        return PortfolioDeleteResponse(deleted=1)
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("Delete corporate action event failed", exc)


@router.get(
    "/snapshot",
    response_model=PortfolioSnapshotResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get portfolio snapshot",
)
def get_snapshot(
    account_id: Optional[int] = Query(None, description="Optional account id, default returns all accounts"),
    as_of: Optional[date] = Query(None, description="Snapshot date, default today"),
    cost_method: str = Query("fifo", description="Cost method: fifo or avg"),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioSnapshotResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.get_portfolio_snapshot(
            account_id=account_id,
            as_of=as_of,
            cost_method=cost_method,
        )
        return PortfolioSnapshotResponse(
            **_redact_consumer_admin_diagnostics(
                _portfolio_consumer_safety_envelope(
                    data,
                    schema_version=PORTFOLIO_SNAPSHOT_CONSUMER_SCHEMA_VERSION,
                )
            )
        )
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Get snapshot failed", exc)


@router.get(
    "/structure-review",
    response_model=PortfolioStructureReviewResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get read-only portfolio structure review",
)
def get_structure_review(
    account_id: Optional[int] = Query(None, description="Optional account id, default returns all accounts"),
    as_of: Optional[date] = Query(None, description="Cached snapshot date; default uses latest cached date"),
    cost_method: str = Query("fifo", description="Cost method: fifo or avg"),
    benchmark: Optional[str] = Query(None, description="Optional benchmark symbol for comparative structure context"),
    max_items: Optional[int] = Query(None, ge=1, le=50, description="Maximum holdings to evaluate"),
    current_user: CurrentUser = Depends(get_current_user),
    review_service: PortfolioStructureReviewService = Depends(_get_portfolio_structure_review_service),
) -> PortfolioStructureReviewResponse:
    try:
        payload = review_service.build_review(
            account_id=account_id,
            as_of=as_of,
            cost_method=cost_method,
            benchmark=benchmark,
            max_items=max_items,
            owner_id=current_user.user_id,
        )
        return PortfolioStructureReviewResponse(**payload)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Get portfolio structure review failed", exc)


@router.get(
    "/history",
    response_model=PortfolioHistoryResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List stored portfolio snapshot history",
)
def list_history(
    account_id: Optional[int] = Query(None, description="Optional account id"),
    date_from: Optional[date] = Query(None, description="Snapshot date from"),
    date_to: Optional[date] = Query(None, description="Snapshot date to"),
    cost_method: str = Query("fifo", description="Cost method: fifo or avg"),
    limit: int = Query(100, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioHistoryResponse:
    repo = PortfolioRepository()
    try:
        method = _normalize_cost_method(cost_method)
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("date_from must be earlier than or equal to date_to")
        if account_id is not None and repo.get_account(account_id, owner_id=current_user.user_id) is None:
            raise safe_api_error(
                status_code=404,
                error="not_found",
                message=f"Account not found: {account_id}",
            )
        rows = repo.list_daily_snapshot_history(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            cost_method=method,
            limit=limit,
            owner_id=current_user.user_id,
        )
        items = [_serialize_history_item(row) for row in rows]
        return PortfolioHistoryResponse(
            account_id=account_id,
            cost_method=method,
            date_from=_date_to_str(date_from),
            date_to=_date_to_str(date_to),
            limit=limit,
            total=len(items),
            items=items,
            coverage=_build_history_coverage(items=items, date_from=date_from, date_to=date_to),
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List portfolio history failed", exc)


@router.post(
    "/imports/parse",
    response_model=PortfolioImportParseResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Parse broker file import into normalized portfolio records",
)
def parse_broker_import(
    broker: str = Form(..., description="Broker id, for example huatai or ibkr"),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioImportParseResponse:
    importer = PortfolioImportService(portfolio_service=_get_portfolio_service(current_user))
    try:
        content = file.file.read()
        parsed = importer.parse_import_file(broker=broker, content=content)
        return _build_import_parse_response(parsed)
    except ValueError as exc:
        raise _import_bad_request() from exc
    except Exception as exc:
        raise _import_internal_error("Parse broker import failed", exc) from exc


@router.get(
    "/imports/brokers",
    response_model=PortfolioImportBrokerListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="List supported broker import parsers",
)
def list_import_brokers(
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioImportBrokerListResponse:
    importer = PortfolioImportService(portfolio_service=_get_portfolio_service(current_user))
    try:
        return PortfolioImportBrokerListResponse(brokers=importer.list_supported_brokers())
    except Exception as exc:
        raise _import_internal_error("List broker imports failed", exc) from exc


@router.post(
    "/imports/commit",
    response_model=PortfolioImportCommitResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Parse and commit broker file import",
)
def commit_broker_import(
    account_id: int = Form(...),
    broker: str = Form(..., description="Broker id, for example huatai or ibkr"),
    dry_run: bool = Form(False),
    broker_connection_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioImportCommitResponse:
    importer = PortfolioImportService(portfolio_service=_get_portfolio_service(current_user))
    try:
        content = file.file.read()
        parsed = importer.parse_import_file(broker=broker, content=content)
        result = importer.commit_import_records(
            account_id=account_id,
            broker=parsed["broker"],
            parsed_payload=parsed,
            dry_run=dry_run,
            broker_connection_id=broker_connection_id,
        )
        return _build_import_commit_response(result)
    except PortfolioConflictError as exc:
        raise _import_conflict_error() from exc
    except ValueError as exc:
        raise _import_bad_request() from exc
    except Exception as exc:
        raise _import_internal_error("Commit broker import failed", exc) from exc


@router.post(
    "/imports/csv/parse",
    response_model=PortfolioImportParseResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Parse broker CSV into normalized trade records",
)
def parse_csv_import(
    broker: str = Form(..., description="Broker id: huatai/citic/cmb"),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioImportParseResponse:
    importer = PortfolioImportService(portfolio_service=_get_portfolio_service(current_user))
    try:
        content = file.file.read()
        parsed = importer.parse_trade_csv(broker=broker, content=content)
        return _build_import_parse_response(parsed)
    except ValueError as exc:
        raise _import_bad_request() from exc
    except Exception as exc:
        raise _import_internal_error("Parse CSV import failed", exc) from exc


@router.get(
    "/imports/csv/brokers",
    response_model=PortfolioImportBrokerListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="List supported broker CSV parsers",
)
def list_csv_brokers(
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioImportBrokerListResponse:
    importer = PortfolioImportService(portfolio_service=_get_portfolio_service(current_user))
    try:
        return PortfolioImportBrokerListResponse(brokers=importer.list_supported_csv_brokers())
    except Exception as exc:
        raise _import_internal_error("List CSV brokers failed", exc) from exc


@router.post(
    "/imports/csv/commit",
    response_model=PortfolioImportCommitResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Parse and commit broker CSV with dedup",
)
def commit_csv_import(
    account_id: int = Form(...),
    broker: str = Form(..., description="Broker id: huatai/citic/cmb"),
    dry_run: bool = Form(False),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioImportCommitResponse:
    importer = PortfolioImportService(portfolio_service=_get_portfolio_service(current_user))
    try:
        content = file.file.read()
        parsed = importer.parse_trade_csv(broker=broker, content=content)
        result = importer.commit_import_records(
            account_id=account_id,
            broker=parsed["broker"],
            parsed_payload=parsed,
            dry_run=dry_run,
        )
        return _build_import_commit_response(result)
    except PortfolioConflictError as exc:
        raise _import_conflict_error() from exc
    except ValueError as exc:
        raise _import_bad_request() from exc
    except Exception as exc:
        raise _import_internal_error("Commit CSV import failed", exc) from exc


@router.post(
    "/fx/refresh",
    response_model=PortfolioFxRefreshResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Refresh FX cache online with stale fallback",
)
def refresh_fx_rates(
    account_id: Optional[int] = Query(None, description="Optional account id"),
    as_of: Optional[date] = Query(None, description="Rate date, default today"),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioFxRefreshResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.refresh_fx_rates(account_id=account_id, as_of=as_of)
        return PortfolioFxRefreshResponse(**data)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Refresh FX rates failed", exc)


@router.post(
    "/scenario-risk",
    response_model=PortfolioScenarioRiskResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Project caller-supplied portfolio scenario risk",
)
def project_scenario_risk(
    request: PortfolioScenarioRiskRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioScenarioRiskResponse:
    del current_user  # Auth convention only; the projection is caller-supplied and account-free.
    try:
        projection = PortfolioScenarioRiskService().build_projection(
            as_of=request.asOf,
            positions=request.positions,
            exposures=request.exposures,
            scenario_shocks=request.scenarioShocks,
        )
        return PortfolioScenarioRiskResponse.model_validate(projection.model_dump())
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Project scenario risk failed", exc)


@router.get(
    "/risk",
    response_model=PortfolioRiskResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get portfolio risk report",
)
def get_risk_report(
    account_id: Optional[int] = Query(None, description="Optional account id"),
    as_of: Optional[date] = Query(None, description="Risk report date, default today"),
    cost_method: str = Query("fifo", description="Cost method: fifo or avg"),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioRiskResponse:
    service = PortfolioRiskService(portfolio_service=_get_portfolio_service(current_user))
    try:
        data = service.get_risk_report(account_id=account_id, as_of=as_of, cost_method=cost_method)
        return PortfolioRiskResponse(
            **_redact_consumer_admin_diagnostics(
                _portfolio_consumer_safety_envelope(
                    data,
                    schema_version=PORTFOLIO_RISK_CONSUMER_SCHEMA_VERSION,
                )
            )
        )
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Get risk report failed", exc)
