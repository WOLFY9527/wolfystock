# -*- coding: utf-8 -*-
"""
Execution log service for admin observability (D2).
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.multi_user import BOOTSTRAP_ADMIN_USER_ID, ROLE_ADMIN, ROLE_USER
from src.storage import get_db
from src.utils.security import sanitize_message, sanitize_metadata, sanitize_url

_SECRET_PATTERNS = [
    re.compile(r"([?&](?:api[-_]?key|token|access_token|secret|password|authorization)=)[^&#\s]+", re.IGNORECASE),
    re.compile(r"\b(token|secret|password|webhook|authorization|api[-_]?key)[=:]\s*([^\s,;]+)", re.IGNORECASE),
]

_NOTIFICATION_STATES = {"success", "partial_success", "timeout_unknown", "failed", "not_configured"}
_LOG_LEVELS = ("DEBUG", "INFO", "NOTICE", "WARNING", "ERROR", "CRITICAL")
_LOG_LEVEL_RANK = {level: index for index, level in enumerate(_LOG_LEVELS)}
_DEFAULT_LOG_CATEGORIES = {
    "system",
    "auth",
    "market",
    "cache",
    "data_source",
    "analysis",
    "scanner",
    "backtest",
    "trading",
    "portfolio",
    "scheduler",
    "notification",
    "api",
    "frontend",
    "security",
}
_NOISY_MARKET_EVENTS = {
    "MarketCacheHit",
    "MarketCacheMiss",
    "MarketPrewarmStarted",
    "MarketPrewarmCompleted",
    "MarketRefreshStarted",
    "MarketRefreshCompleted",
}
_ANALYSIS_STEP_LABELS = {
    "fetch_quote": "获取行情",
    "fetch_history": "获取历史行情",
    "fetch_technical": "获取技术指标",
    "fetch_fundamentals": "获取基本面",
    "fetch_news": "获取新闻",
    "fetch_financials": "获取财务数据",
    "fetch_market_context": "获取市场环境",
    "ai_analysis": "AI 分析",
    "validate_schema": "校验结构",
    "save_record": "保存分析记录",
    "notify_user": "通知用户",
    "load_universe": "加载股票池",
    "load_market_data": "加载行情数据",
    "load_factor_data": "加载因子/指标",
    "run_screen": "执行扫描",
    "rank_candidates": "候选排序",
    "save_scan_result": "保存扫描结果",
    "load_strategy": "加载策略",
    "load_price_data": "加载价格数据",
    "generate_signals": "生成信号",
    "simulate_orders": "撮合交易",
    "calculate_metrics": "计算指标",
    "save_backtest_report": "保存回测报告",
    "validate_key_format": "校验 Key 格式",
    "test_quote_endpoint": "测试行情接口",
    "test_history_endpoint": "测试历史接口",
    "test_news_endpoint": "测试新闻接口",
    "test_rate_limit": "测试限流",
    "save_provider_status": "保存数据源状态",
}
_CRITICAL_ANALYSIS_STEPS = {"fetch_quote", "ai_analysis"}
_STATUS_ALIASES = {
    "completed": "success",
    "succeeded": "success",
    "ok": "success",
    "partial_success": "partial",
    "partial fail": "partial",
    "fail": "failed",
    "error": "failed",
    "failed_runtime": "failed",
    "timed_out": "failed",
    "timeout": "failed",
}
_TRACE_SUCCESS_VALUES = {"succeeded", "success", "completed", "ok"}
_TRACE_FAILED_VALUES = {
    "failed",
    "error",
    "timeout",
    "timed_out",
    "forbidden",
    "unauthorized",
    "rate_limited",
    "invalid_payload",
    "empty_result",
    "invalid_response",
    "insufficient_fields",
}
_TRACE_SKIPPED_REASONS = {
    "previous_provider_succeeded",
    "previous_model_succeeded",
    "skipped_because_previous_succeeded",
    "not_needed",
    "not_configured",
    "missing_api_key",
    "provider_unhealthy",
    "circuit_open",
    "unsupported_market",
    "not_applicable",
    "disabled_by_strategy",
}
_TRACE_RUNNING_VALUES = {"attempting", "running", "started", "start", "processing", "in_progress"}
_TRACE_FAILED_HTTP_STATUSES = {401, 403, 429, 500, 502, 503, 504}


def _masked_message(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    masked = sanitize_message(str(text))
    return masked[:400] if masked else None


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _status_from_attempt_result(value: Any) -> str:
    status = _as_str(value).lower()
    if not status:
        return "unknown"
    if status in {"ok", "success"}:
        return "succeeded"
    if status in {"partial"}:
        return "partial_success"
    if status in {"failed", "error"}:
        return "failed"
    if status in {"timeout", "timed_out"}:
        return "timed_out"
    if status in {"succeeded", "failed", "empty_result", "invalid_response", "insufficient_fields", "skipped_because_previous_succeeded", "switched_to_fallback"}:
        return status
    return status


def _action_from_status(status: Any) -> str:
    normalized = _as_str(status).lower()
    if normalized in {"attempting", "waiting", "running"}:
        return "attempting"
    if normalized in {"succeeded", "success", "ok"}:
        return "succeeded"
    if normalized in {"failed", "error"}:
        return "failed"
    if normalized in {"timed_out", "timeout", "timeout_unknown"}:
        return "timeout"
    if normalized in {"switched_to_fallback", "switched"}:
        return "switched"
    if normalized in {"empty_result"}:
        return "empty_result"
    if normalized in {"invalid_response"}:
        return "invalid_response"
    if normalized in {"insufficient_fields"}:
        return "insufficient_fields"
    if normalized in {"skipped_because_previous_succeeded"}:
        return "skipped"
    if normalized in {"partial_success", "partial"}:
        return "completed"
    if normalized in {"not_configured"}:
        return "skipped"
    if normalized in {"selected", "configured"}:
        return "selected"
    if normalized in {"completed"}:
        return "completed"
    return "unknown"


def _outcome_from_status(status: Any) -> str:
    normalized = _as_str(status).lower()
    if normalized in {"succeeded", "success", "ok", "completed"}:
        return "ok"
    if normalized in {"partial", "partial_success"}:
        return "partial"
    if normalized in {"timeout", "timed_out", "timeout_unknown"}:
        return "timeout"
    if normalized in {"failed", "error", "empty_result", "invalid_response", "insufficient_fields"}:
        return "failed"
    if normalized in {"not_configured", "skipped", "skipped_because_previous_succeeded"}:
        return "ok"
    if normalized in {"switched_to_fallback", "switched"}:
        return "ok"
    return "unknown"


def _severity_from_status(status: Any) -> str:
    outcome = _outcome_from_status(status)
    if outcome == "failed":
        return "error"
    if outcome in {"partial", "timeout"}:
        return "warning"
    return "info"


def _normalize_log_level(value: Any, default: str = "INFO") -> str:
    normalized = _as_str(value).upper()
    return normalized if normalized in _LOG_LEVEL_RANK else default


def _level_from_status(status: Any) -> str:
    normalized = _as_str(status).lower()
    if normalized in {"critical", "fatal"}:
        return "CRITICAL"
    if normalized in {"failed", "failed_runtime", "error", "empty_result", "invalid_response", "insufficient_fields"}:
        return "ERROR"
    if normalized in {"partial", "partial_success", "timeout", "timed_out", "timeout_unknown", "switched_to_fallback"}:
        return "WARNING"
    return "INFO"


def _normalize_log_category(value: Any, fallback: str = "system") -> str:
    normalized = _as_str(value).lower().replace("-", "_").replace(".", "_")
    aliases = {
        "market_overview": "market",
        "data": "data_source",
        "data_market": "data_source",
        "data_fundamentals": "data_source",
        "data_news": "data_source",
        "data_sentiment": "data_source",
        "system_control": "system",
        "ai_model": "analysis",
        "ai_route": "analysis",
        "market_overview_refresh": "market",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in _DEFAULT_LOG_CATEGORIES else fallback


def _normalize_business_status(value: Any) -> str:
    normalized = _as_str(value).lower()
    if normalized in {"success", "failed", "partial", "running", "skipped", "unknown", "cancelled"}:
        return normalized
    if normalized in {"succeeded", "completed", "ok"}:
        return "success"
    if normalized in {"not_configured", "skipped_because_previous_succeeded"}:
        return "skipped"
    return _STATUS_ALIASES.get(normalized, normalized or "running")


def _sanitize_url(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = sanitize_url(str(value))
    return text[:500] if text else None


def _sanitize_metadata(value: Any) -> Any:
    return sanitize_metadata(value)


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    text = _as_str(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _duration_ms(started_at: Any, finished_at: Any) -> Optional[float]:
    start = _parse_iso_datetime(started_at)
    finish = _parse_iso_datetime(finished_at)
    if start is None or finish is None:
        return None
    return max(0.0, (finish - start).total_seconds() * 1000)


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        text = _as_str(value)
        if text:
            return text
    return None


def _compact_identifier(value: Any) -> Optional[str]:
    text = _as_str(value)
    if not text:
        return None
    return text if len(text) <= 80 else f"{text[:36]}...{text[-16:]}"


_BOUNDED_DIAGNOSTIC_HANDLE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_DROP_DIAGNOSTIC_HANDLE_RE = re.compile(
    r"(api[-_]?key|apikey|access[-_]?token|refresh[-_]?token|session[-_]?(?:token|cookie)|"
    r"cookie|token|authorization|bearer|credential|private[-_]?key|secret|password|dsn|"
    r"database[-_]?url|connection[-_]?string|reservation|idempotenc|reserve)",
    re.IGNORECASE,
)
_HASH_DIAGNOSTIC_HANDLE_RE = re.compile(r"(^|[-_.:])(guest|session|user|owner)([-_.:]|$)", re.IGNORECASE)
_HASHED_DIAGNOSTIC_HANDLE_SOURCES = {"provider_payload", "raw_payload", "event_detail"}


def _hashed_diagnostic_handle(value: str, kind: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{kind}:sha256:{digest}"


def _project_diagnostic_handle(value: Any, *, kind: str, source: str) -> Optional[str]:
    text = _as_str(value)
    if not text:
        return None
    if _masked_message(text) != text:
        return None
    if _DROP_DIAGNOSTIC_HANDLE_RE.search(text):
        return None
    if source in _HASHED_DIAGNOSTIC_HANDLE_SOURCES:
        return _hashed_diagnostic_handle(text, kind)
    if _HASH_DIAGNOSTIC_HANDLE_RE.search(text):
        return _hashed_diagnostic_handle(text, kind)
    if not _BOUNDED_DIAGNOSTIC_HANDLE_RE.fullmatch(text):
        return _hashed_diagnostic_handle(text, kind)
    return text


def _first_diagnostic_handle(kind: str, *candidates: Tuple[Any, str]) -> Optional[str]:
    for value, source in candidates:
        handle = _project_diagnostic_handle(value, kind=kind, source=source)
        if handle:
            return handle
    return None


def _reason_from_failure_text(*values: Any, failed: bool = False) -> Optional[str]:
    text = " ".join(_as_str(value) for value in values if _as_str(value)).lower()
    if not text:
        return "unknown" if failed else None
    if "timeout" in text or "timed out" in text or "time out" in text:
        return "timeout"
    if "missing_api_key" in text or "missing api key" in text or "api key not configured" in text or "not_configured" in text:
        return "missing_key"
    if "invalid_payload" in text or "invalid payload" in text or "schema" in text or "validation" in text:
        return "invalid_payload"
    if "empty_result" in text or "empty result" in text or "no rows" in text or "no data" in text:
        return "empty_result"
    if "rate_limited" in text or "rate limited" in text or "429" in text:
        return "rate_limited"
    if "unauthorized" in text or "forbidden" in text or "401" in text or "403" in text:
        return "unauthorized"
    if "provider" in text or "source" in text or "upstream" in text or "external" in text:
        return "provider_error"
    if "fallback" in text or "stale" in text:
        return "fallback"
    simple = _first_text(*values)
    if simple and re.fullmatch(r"[A-Za-z0-9_.:-]{2,48}", simple):
        return simple.lower()
    return "unknown" if failed else None


def _trace_reason_message(reason: Optional[str]) -> Optional[str]:
    normalized = _as_str(reason).lower()
    if not normalized:
        return None
    if normalized == "previous_model_succeeded":
        return "主模型已成功，无需调用备用模型"
    if normalized in {"previous_provider_succeeded", "skipped_because_previous_succeeded"}:
        return "主数据源已成功，无需调用备用源"
    if normalized in {"missing_api_key", "not_configured"}:
        return "未配置 API Key，已跳过"
    if normalized in {"circuit_open", "provider_unhealthy"}:
        return "数据源暂时不可用，已跳过"
    if normalized == "unsupported_market":
        return "当前市场不适用，已跳过"
    if normalized in {"not_applicable", "disabled_by_strategy", "not_needed"}:
        return "当前步骤无需执行，已跳过"
    return None


def normalize_trace_step_status(
    event_or_metadata: Dict[str, Any],
    *,
    execution_finished: bool = False,
    execution_status: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    payload = event_or_metadata if isinstance(event_or_metadata, dict) else {}
    detail = payload.get("detail") if isinstance(payload.get("detail"), dict) else {}
    started_at = detail.get("startedAt") or payload.get("startedAt") or payload.get("event_at")
    finished_at = detail.get("finishedAt") or payload.get("finishedAt")

    def token(value: Any) -> str:
        return _as_str(value).lower()

    action = token(detail.get("action") or payload.get("action"))
    result = token(detail.get("result") or payload.get("result") or payload.get("status"))
    outcome = token(detail.get("outcome") or payload.get("outcome"))
    status_token = token(detail.get("status") or payload.get("status"))
    reason = token(detail.get("reason") or payload.get("reason"))
    message = _masked_message(detail.get("message") or payload.get("message"))
    error_type = token(detail.get("errorType") or payload.get("error_type") or payload.get("error_code"))
    error_message = _masked_message(detail.get("errorMessage") or payload.get("errorMessage") or payload.get("message"))
    http_status_raw = detail.get("httpStatus") or detail.get("http_status") or payload.get("httpStatus")
    try:
        http_status = int(http_status_raw) if http_status_raw is not None else None
    except Exception:
        http_status = None
    text_blob = " ".join(
        part for part in [
            action,
            result,
            outcome,
            status_token,
            reason,
            token(message),
            error_type,
            token(error_message),
        ] if part
    )

    skipped = (
        action == "skipped"
        or result.startswith("skipped")
        or outcome == "skipped"
        or reason in _TRACE_SKIPPED_REASONS
        or "skipped because previous" in text_blob
        or "previous provider already succeeded" in text_blob
        or "previous model already succeeded" in text_blob
        or "not configured" in text_blob
        or "missing api key" in text_blob
        or "circuit open" in text_blob
        or "provider unhealthy" in text_blob
    )
    if skipped:
        normalized_reason = reason or ("skipped_because_previous_succeeded" if "previous" in text_blob else None)
        friendly_message = _trace_reason_message(normalized_reason)
        return {
            "status": "skipped",
            "reason": normalized_reason,
            "message": friendly_message if not message or message == normalized_reason else message,
        }

    failed_reason = None
    if action in {"failed", "error"} or result in _TRACE_FAILED_VALUES or outcome in {"failed", "error"}:
        failed_reason = reason or result or outcome or action
    elif http_status in _TRACE_FAILED_HTTP_STATUSES:
        if http_status == 401:
            failed_reason = "unauthorized"
        elif http_status == 403:
            failed_reason = "forbidden"
        elif http_status == 429:
            failed_reason = "rate_limited"
        else:
            failed_reason = "http_error"
    elif any(keyword in text_blob for keyword in ("timeout", "timed out")):
        failed_reason = reason or "timeout"
    elif any(keyword in text_blob for keyword in ("forbidden", "unauthorized", "rate limit", "rate_limited", "invalid payload")):
        failed_reason = reason or (
            "forbidden" if "forbidden" in text_blob else
            "unauthorized" if "unauthorized" in text_blob else
            "rate_limited" if "rate" in text_blob else
            "invalid_payload"
        )
    if failed_reason and failed_reason not in _TRACE_SKIPPED_REASONS:
        return {
            "status": "failed",
            "reason": failed_reason,
            "message": error_message or message,
        }

    success = (
        action in _TRACE_SUCCESS_VALUES
        or result in _TRACE_SUCCESS_VALUES
        or outcome in {"success", "succeeded", "ok"}
        or status_token in _TRACE_SUCCESS_VALUES
    )
    if success:
        return {
            "status": "success",
            "reason": reason or None,
            "message": message,
        }

    execution_still_running = _normalize_business_status(execution_status or "") == "running"
    running = (
        action in _TRACE_RUNNING_VALUES
        or result in _TRACE_RUNNING_VALUES
        or status_token in _TRACE_RUNNING_VALUES
    )
    if running and not finished_at:
        if execution_finished or not execution_still_running:
            return {
                "status": "unknown",
                "reason": reason or None,
                "message": message,
            }
        return {
            "status": "running",
            "reason": reason or None,
            "message": message,
        }

    if execution_finished and started_at and not finished_at:
        return {
            "status": "unknown",
            "reason": reason or None,
            "message": message,
        }

    return {
        "status": "unknown",
        "reason": reason or None,
        "message": message,
    }


def _event_name_from_event(event: Dict[str, Any]) -> str:
    detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
    return _as_str(detail.get("event_name")) or _as_str(detail.get("action")) or _as_str(event.get("step")) or "Event"


def _event_category(event: Dict[str, Any]) -> str:
    detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
    return _normalize_log_category(detail.get("category") or event.get("category") or event.get("phase"))


def _event_level(event: Dict[str, Any]) -> str:
    detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
    explicit = _as_str(detail.get("level") or event.get("level")).upper()
    if explicit in _LOG_LEVEL_RANK:
        return explicit
    event_name = _event_name_from_event(event)
    if event_name in _NOISY_MARKET_EVENTS:
        return "DEBUG" if event_name == "MarketCacheHit" else "INFO"
    return _level_from_status(event.get("status"))


def _parse_since(value: Optional[str]) -> Optional[datetime]:
    text = _as_str(value).lower()
    if not text:
        return None
    if text.endswith("m") and text[:-1].isdigit():
        return datetime.now() - timedelta(minutes=int(text[:-1]))
    if text.endswith("h") and text[:-1].isdigit():
        return datetime.now() - timedelta(hours=int(text[:-1]))
    if text.endswith("d") and text[:-1].isdigit():
        return datetime.now() - timedelta(days=int(text[:-1]))
    try:
        return datetime.fromisoformat(text.replace("z", "+00:00"))
    except Exception:
        return None


def _data_phase(key: str) -> str:
    mapping = {
        "market": "data_market",
        "fundamentals": "data_fundamentals",
        "news": "data_news",
        "sentiment": "data_sentiment",
    }
    return mapping.get(key, f"data_{key}")


def classify_notification_state(notification: Dict[str, Any]) -> str:
    attempted = bool(notification.get("attempted"))
    raw_status = _as_str(notification.get("status")).lower()
    success = notification.get("success")
    error = _as_str(notification.get("error")).lower()
    channels = notification.get("channels") or []

    if not attempted and raw_status in {"not_configured", "skipped"}:
        return "not_configured"
    if raw_status in {"partial", "partial_success"}:
        return "partial_success"
    if raw_status in {"ok", "success"} or success is True:
        return "success"
    if "timeout" in raw_status or "timeout" in error or "timed out" in error:
        return "timeout_unknown"
    if attempted and success is False and len(channels) > 1:
        return "partial_success"
    if attempted and (raw_status in {"failed", "error"} or success is False):
        return "failed"
    if not attempted and channels:
        return "not_configured"
    return "failed" if attempted else "not_configured"


class ExecutionLogService:
    """Write/read structured execution logs for admin-only observability."""

    def __init__(self):
        self.db = get_db()

    def start_execution(
        self,
        *,
        category: str,
        type: str,
        event: str,
        summary: str,
        subject: Optional[str] = None,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
        strategy_id: Optional[str] = None,
        scanner_id: Optional[str] = None,
        backtest_id: Optional[str] = None,
        record_id: Optional[str] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        actor: Optional[Dict[str, Any]] = None,
    ) -> str:
        execution_id = uuid.uuid4().hex
        started_at = datetime.now()
        normalized_category = _normalize_log_category(category)
        symbol_text = _as_str(symbol).upper() or None
        subject_text = _as_str(subject) or symbol_text or _as_str(event) or None
        business = {
            "id": execution_id,
            "event": _as_str(event) or subject_text or execution_id,
            "category": normalized_category,
            "type": _as_str(type) or normalized_category,
            "status": "running",
            "summary": _as_str(summary) or _as_str(event) or normalized_category,
            "subject": subject_text,
            "symbol": symbol_text,
            "market": _as_str(market).upper() or None,
            "strategyId": _as_str(strategy_id) or None,
            "scannerId": _as_str(scanner_id) or None,
            "backtestId": _as_str(backtest_id) or None,
            "recordId": _as_str(record_id) or None,
            "requestId": _as_str(request_id) or None,
            "userId": _as_str(user_id) or None,
            "startedAt": started_at.isoformat(),
            "finishedAt": None,
            "durationMs": None,
            "stepCount": 0,
            "successStepCount": 0,
            "failedStepCount": 0,
            "skippedStepCount": 0,
            "unknownStepCount": 0,
            "metadata": _sanitize_metadata(metadata or {}),
        }
        summary_payload = self._merge_summary(
            {"business_event": business},
            self._summary_meta(
                owner_id=user_id,
                actor=actor or ({"user_id": user_id} if user_id else None),
                session_kind="business_event",
                subsystem=normalized_category,
                action_name=business["type"],
            ),
        )
        self.db.create_execution_log_session(
            session_id=execution_id,
            task_id=request_id or f"{normalized_category}:{business['type']}",
            code=symbol_text,
            name=business["event"],
            overall_status="running",
            truth_level="actual",
            summary=summary_payload,
            started_at=started_at,
        )
        self.db.append_execution_log_event(
            session_id=execution_id,
            phase=normalized_category,
            step="execution_started",
            target=subject_text or business["event"],
            status="running",
            truth_level="actual",
            message=business["summary"],
            detail={
                "category": normalized_category,
                "event_name": "BusinessExecutionStarted",
                "business_event": True,
                "business_type": business["type"],
                "subject": subject_text,
                "symbol": symbol_text,
                "request_id": business["requestId"],
            },
            event_at=started_at,
        )
        return execution_id

    def start_step(
        self,
        execution_id: str,
        name: str,
        label: str,
        *,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        critical: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        step_id = uuid.uuid4().hex
        self._append_business_step(
            execution_id=execution_id,
            step_id=step_id,
            name=name,
            label=label,
            category=category,
            provider=provider,
            model=model,
            endpoint=endpoint,
            status="running",
            critical=critical,
            metadata=metadata,
        )
        return step_id

    def finish_step_success(
        self,
        execution_id: str,
        step_key_or_id: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> None:
        self._append_business_step_result(
            execution_id=execution_id,
            step_key_or_id=step_key_or_id,
            status="success",
            metadata=metadata,
            message=message,
            provider=provider,
            model=model,
            endpoint=endpoint,
        )

    def finish_step_failed(
        self,
        execution_id: str,
        step_key_or_id: str,
        *,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> None:
        self._append_business_step_result(
            execution_id=execution_id,
            step_key_or_id=step_key_or_id,
            status="failed",
            metadata=metadata,
            message=error_message,
            error_type=error_type,
            reason=reason,
            provider=provider,
            model=model,
            endpoint=endpoint,
        )

    def skip_step(
        self,
        execution_id: str,
        name: str,
        label: str,
        reason: str,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._append_business_step(
            execution_id=execution_id,
            step_id=uuid.uuid4().hex,
            name=name,
            label=label,
            provider=provider,
            model=model,
            endpoint=endpoint,
            status="skipped",
            reason=reason,
            message=reason,
            critical=False,
            metadata=metadata,
        )

    def finish_execution(
        self,
        execution_id: str,
        *,
        status: Optional[str] = None,
        record_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        detail = self.db.get_execution_log_session_detail(execution_id) or {}
        row_summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
        business = row_summary.get("business_event") if isinstance(row_summary.get("business_event"), dict) else {}
        finished_at = datetime.now()
        steps = self._build_business_steps_from_session({**detail, "ended_at": finished_at.isoformat()})
        success_count = sum(1 for step in steps if step.get("status") == "success")
        failed_count = sum(1 for step in steps if step.get("status") == "failed")
        skipped_count = sum(1 for step in steps if step.get("status") == "skipped")
        unknown_count = sum(1 for step in steps if step.get("status") == "unknown")
        resolved_status = _normalize_business_status(status) if status else self._infer_business_status(steps)
        started_at = business.get("startedAt") or detail.get("started_at")
        next_business = {
            **business,
            "id": execution_id,
            "status": resolved_status,
            "recordId": _as_str(record_id) or business.get("recordId"),
            "finishedAt": finished_at.isoformat(),
            "durationMs": _duration_ms(started_at, finished_at.isoformat()),
            "stepCount": len(steps),
            "successStepCount": success_count,
            "failedStepCount": failed_count,
            "skippedStepCount": skipped_count,
            "unknownStepCount": unknown_count,
            "metadata": _sanitize_metadata({
                **(business.get("metadata") if isinstance(business.get("metadata"), dict) else {}),
                **(metadata or {}),
            }),
        }
        next_summary = self._merge_summary(row_summary, {"business_event": next_business})
        self.db.finalize_execution_log_session(
            session_id=execution_id,
            overall_status=resolved_status,
            truth_level="actual",
            summary=next_summary,
            ended_at=finished_at,
        )
        self.db.append_execution_log_event(
            session_id=execution_id,
            phase=next_business.get("category") or "system",
            step="execution_finished",
            target=next_business.get("subject") or next_business.get("event"),
            status=resolved_status,
            truth_level="actual",
            message=next_business.get("summary"),
            detail={
                "category": next_business.get("category"),
                "event_name": "BusinessExecutionFinished",
                "business_event": True,
                "business_type": next_business.get("type"),
                "outcome": _outcome_from_status(resolved_status),
            },
            event_at=finished_at,
        )
        return next_business

    def start_analysis_execution(
        self,
        *,
        symbol: str,
        market: Optional[str] = None,
        analysis_type: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        task_id: Optional[str] = None,
        stock_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        actor: Optional[Dict[str, Any]] = None,
    ) -> str:
        execution_id = uuid.uuid4().hex
        started_at = datetime.now()
        symbol_text = _as_str(symbol).upper()
        business = {
            "id": execution_id,
            "event": symbol_text,
            "category": "analysis",
            "type": "stock_analysis",
            "status": "running",
            "summary": f"用户分析 {symbol_text}",
            "subject": symbol_text,
            "symbol": symbol_text,
            "market": _as_str(market).upper() or None,
            "analysisType": _as_str(analysis_type) or None,
            "userId": _as_str(user_id) or None,
            "requestId": _as_str(request_id) or None,
            "recordId": None,
            "startedAt": started_at.isoformat(),
            "finishedAt": None,
            "durationMs": None,
            "stepCount": 0,
            "successStepCount": 0,
            "failedStepCount": 0,
            "skippedStepCount": 0,
            "unknownStepCount": 0,
            "metadata": _sanitize_metadata(metadata or {}),
        }
        summary = self._merge_summary(
            {"business_event": business},
            self._summary_meta(
                owner_id=user_id,
                actor=actor or ({"user_id": user_id} if user_id else None),
                session_kind="business_event",
                subsystem="analysis",
                action_name="analysis_execution",
            ),
        )
        self.db.create_execution_log_session(
            session_id=execution_id,
            task_id=task_id or request_id or f"analysis:{symbol_text}",
            code=symbol_text,
            name=stock_name or symbol_text,
            overall_status="running",
            truth_level="actual",
            summary=summary,
            started_at=started_at,
        )
        self.db.append_execution_log_event(
            session_id=execution_id,
            phase="analysis",
            step="analysis_started",
            target=symbol_text,
            status="running",
            truth_level="actual",
            message=f"用户分析 {symbol_text}",
            detail={
                "category": "analysis",
                "event_name": "AnalysisExecutionStarted",
                "symbol": symbol_text,
                "market": business["market"],
                "analysis_type": business["analysisType"],
                "request_id": business["requestId"],
                "business_event": True,
            },
            event_at=started_at,
        )
        return execution_id

    def add_execution_step(
        self,
        *,
        execution_id: str,
        name: str,
        label: Optional[str] = None,
        provider: Optional[str] = None,
        api_path: Optional[str] = None,
        status: str,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
        duration_ms: Optional[float] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        record_id: Optional[str] = None,
        critical: Optional[bool] = None,
    ) -> None:
        now = datetime.now()
        step_started = started_at or finished_at or now
        step_finished = finished_at or now
        step_name = _as_str(name)
        normalized_status = _normalize_business_status(status)
        computed_duration = duration_ms
        if computed_duration is None:
            computed_duration = _duration_ms(step_started.isoformat(), step_finished.isoformat())
        detail = {
            "category": "analysis",
            "event_name": "AnalysisExecutionStep",
            "business_step": True,
            "id": uuid.uuid4().hex,
            "executionId": execution_id,
            "name": step_name,
            "label": label or _ANALYSIS_STEP_LABELS.get(step_name, step_name),
            "stepCategory": _data_phase(step_name.replace("fetch_", "")) if step_name.startswith("fetch_") else None,
            "provider": _as_str(provider) or None,
            "model": None,
            "endpoint": _as_str(api_path) or None,
            "apiPath": _as_str(api_path) or None,
            "status": normalized_status,
            "reason": None,
            "message": _masked_message(error_message) if error_message else None,
            "startedAt": step_started.isoformat(),
            "finishedAt": step_finished.isoformat(),
            "durationMs": computed_duration,
            "errorType": _as_str(error_type) or None,
            "errorMessage": _masked_message(error_message),
            "recordId": _as_str(record_id) or None,
            "critical": bool(critical) if critical is not None else step_name in _CRITICAL_ANALYSIS_STEPS,
            "metadata": _sanitize_metadata(metadata or {}),
            "outcome": _outcome_from_status(normalized_status),
        }
        self.db.append_execution_log_event(
            session_id=execution_id,
            phase="analysis",
            step=step_name,
            target=_as_str(provider) or step_name,
            status=normalized_status,
            truth_level="actual",
            message=_masked_message(error_message) if error_message else detail["label"],
            error_code=_as_str(error_type) or None,
            detail=detail,
            event_at=step_finished,
        )

    def finish_analysis_execution(
        self,
        *,
        execution_id: str,
        status: Optional[str] = None,
        record_id: Optional[str] = None,
        query_id: Optional[str] = None,
        analysis_history_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        detail = self.db.get_execution_log_session_detail(execution_id) or {}
        summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
        business = summary.get("business_event") if isinstance(summary.get("business_event"), dict) else {}
        steps = self._extract_business_steps(detail.get("events") if isinstance(detail.get("events"), list) else [])
        resolved_status = _normalize_business_status(status) if status else self._infer_analysis_status(steps, record_id=record_id)
        symbol = _as_str(business.get("symbol") or detail.get("code") or detail.get("name") or "analysis").upper()
        finished_at = datetime.now()
        started_at = business.get("startedAt") or detail.get("started_at")
        failed_count = sum(1 for step in steps if step["status"] == "failed")
        success_count = sum(1 for step in steps if step["status"] == "success")
        skipped_count = sum(1 for step in steps if step["status"] == "skipped")
        unknown_count = sum(1 for step in steps if step["status"] == "unknown")
        summary_text = f"用户分析 {symbol}"
        if resolved_status == "partial":
            summary_text = f"用户分析 {symbol}，部分数据源失败"
        elif resolved_status == "failed":
            summary_text = f"用户分析 {symbol}失败"
        next_business = {
            **business,
            "id": execution_id,
            "event": symbol,
            "category": "analysis",
            "status": resolved_status,
            "summary": summary_text,
            "symbol": symbol,
            "recordId": _as_str(record_id) or business.get("recordId"),
            "finishedAt": finished_at.isoformat(),
            "durationMs": _duration_ms(started_at, finished_at.isoformat()),
            "stepCount": len(steps),
            "successStepCount": success_count,
            "failedStepCount": failed_count,
            "skippedStepCount": skipped_count,
            "unknownStepCount": unknown_count,
            "metadata": {
                **(business.get("metadata") if isinstance(business.get("metadata"), dict) else {}),
                **_sanitize_metadata(metadata or {}),
            },
        }
        next_summary = self._merge_summary(summary, {"business_event": next_business})
        self.db.finalize_execution_log_session(
            session_id=execution_id,
            overall_status=resolved_status,
            truth_level="actual",
            query_id=query_id,
            analysis_history_id=analysis_history_id,
            summary=next_summary,
            ended_at=finished_at,
        )
        self.db.append_execution_log_event(
            session_id=execution_id,
            phase="analysis",
            step="analysis_finished",
            target=symbol,
            status=resolved_status,
            truth_level="actual",
            message=summary_text,
            detail={
                "category": "analysis",
                "event_name": "AnalysisExecutionFinished",
                "business_event": True,
                "symbol": symbol,
                "record_id": next_business.get("recordId"),
                "outcome": _outcome_from_status(resolved_status),
            },
            event_at=finished_at,
        )
        return next_business

    def start_session(
        self,
        *,
        task_id: str,
        stock_code: str,
        stock_name: Optional[str],
        configured_execution: Optional[Dict[str, Any]],
        owner_id: Optional[str] = None,
        actor: Optional[Dict[str, Any]] = None,
        subsystem: str = "analysis",
    ) -> str:
        session_id = uuid.uuid4().hex
        started_at = datetime.now()
        safe_configured_execution = _sanitize_metadata(configured_execution or {})
        summary = self._merge_summary(
            {
                "configured_execution": safe_configured_execution,
            },
            self._summary_meta(
                owner_id=owner_id,
                actor=actor,
                session_kind="user_activity",
                subsystem=subsystem,
            ),
        )
        self.db.create_execution_log_session(
            session_id=session_id,
            task_id=task_id,
            code=stock_code,
            name=stock_name,
            overall_status="running",
            truth_level="mixed",
            summary=summary,
            started_at=started_at,
        )
        self.db.append_execution_log_event(
            session_id=session_id,
            phase="system",
            step="task_started",
            target=stock_code,
            status="started",
            truth_level="actual",
            message=f"Task {task_id} started",
            detail={"configured_execution": safe_configured_execution},
            event_at=started_at,
        )
        self._append_configured_events(session_id, safe_configured_execution)
        return session_id

    def _resolve_actor(self, owner_id: Optional[str], actor: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        actor_payload = dict(actor or {})
        user_id = _as_str(actor_payload.get("user_id")) or _as_str(owner_id)
        username = _as_str(actor_payload.get("username"))
        display_name = _as_str(actor_payload.get("display_name"))
        role = _as_str(actor_payload.get("role")).lower()
        actor_type = _as_str(actor_payload.get("actor_type") or actor_payload.get("type")).lower()
        session_id = _as_str(actor_payload.get("session_id"))
        request_id = _as_str(actor_payload.get("request_id"))

        if user_id:
            user_row = self.db.get_app_user(user_id)
            if user_row is not None:
                username = username or _as_str(getattr(user_row, "username", None))
                display_name = display_name or _as_str(getattr(user_row, "display_name", None))
                role = role or _as_str(getattr(user_row, "role", None)).lower()

        if role not in {ROLE_ADMIN, ROLE_USER, "guest", "anonymous", "system"}:
            role = ROLE_ADMIN if user_id == BOOTSTRAP_ADMIN_USER_ID else ROLE_USER
        if actor_type not in {"admin", "user", "guest", "anonymous", "system"}:
            actor_type = role

        return {
            "user_id": user_id or None,
            "username": username or None,
            "display_name": display_name or username or user_id or actor_type or None,
            "role": role,
            "actor_type": actor_type,
            "session_id": session_id or None,
            "request_id": request_id or None,
        }

    def _summary_meta(
        self,
        *,
        owner_id: Optional[str] = None,
        actor: Optional[Dict[str, Any]] = None,
        session_kind: str,
        subsystem: str,
        action_name: Optional[str] = None,
        destructive: bool = False,
    ) -> Dict[str, Any]:
        actor_payload = self._resolve_actor(owner_id, actor)
        return {
            "meta": {
                "owner_user_id": _as_str(owner_id) or actor_payload.get("user_id"),
                "actor_user_id": actor_payload.get("user_id"),
                "actor_username": actor_payload.get("username"),
                "actor_display": actor_payload.get("display_name"),
                "actor_role": actor_payload.get("role"),
                "actor_type": actor_payload.get("actor_type"),
                "actor_session_id": actor_payload.get("session_id"),
                "actor_request_id": actor_payload.get("request_id"),
                "session_kind": session_kind,
                "subsystem": subsystem,
                "action_name": action_name,
                "destructive": bool(destructive),
            }
        }

    @staticmethod
    def _merge_summary(*parts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for part in parts:
            if not isinstance(part, dict):
                continue
            for key, value in part.items():
                if isinstance(value, dict) and isinstance(merged.get(key), dict):
                    merged[key] = {**merged[key], **value}
                else:
                    merged[key] = value
        return merged

    def record_admin_action(
        self,
        *,
        action: str,
        message: str,
        actor: Optional[Dict[str, Any]] = None,
        subsystem: str = "system_control",
        destructive: bool = False,
        detail: Optional[Dict[str, Any]] = None,
        overall_status: str = "completed",
        request: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> str:
        session_id = uuid.uuid4().hex
        started_at = datetime.now()
        actor_payload = self._resolve_actor(None, actor)
        safe_detail = _sanitize_metadata(detail or {})
        safe_request = _sanitize_metadata(request or {})
        safe_result = _sanitize_metadata(result if result is not None else safe_detail)
        summary = self._merge_summary(
            {"admin_action": safe_detail},
            self._summary_meta(
                actor=actor_payload,
                session_kind="admin_action",
                subsystem=subsystem,
                action_name=action,
                destructive=destructive,
            ),
        )
        self.db.create_execution_log_session(
            session_id=session_id,
            task_id=action,
            code=None,
            name=action,
            overall_status=overall_status,
            truth_level="actual",
            summary=summary,
            started_at=started_at,
        )
        self.db.append_execution_log_event(
            session_id=session_id,
            phase="system",
            step=action,
            target=subsystem,
            status=overall_status,
            truth_level="actual",
            message=_masked_message(message) or "",
            detail={
                "category": "system",
                "action": action,
                "outcome": _outcome_from_status(overall_status),
                "destructive": destructive,
                **safe_detail,
            },
            event_at=started_at,
        )
        self.db.finalize_execution_log_session(
            session_id=session_id,
            overall_status=overall_status,
            truth_level="actual",
            summary=summary,
            ended_at=started_at,
        )
        self.db.record_phase_g_admin_action(
            action_key=action,
            actor_user_id=actor_payload.get("user_id"),
            actor_role=actor_payload.get("role"),
            subsystem=subsystem,
            category="system",
            message=_masked_message(message) or "",
            detail_json={
                "category": "system",
                "action": action,
                "outcome": _outcome_from_status(overall_status),
                "destructive": destructive,
                **safe_detail,
            },
            related_session_key=session_id,
            destructive=destructive,
            status=overall_status,
            severity=_severity_from_status(overall_status),
            outcome=_outcome_from_status(overall_status),
            request_json=safe_request,
            result_json=safe_result,
            created_at=started_at,
        )
        return session_id

    def record_scanner_run(
        self,
        *,
        run_detail: Dict[str, Any],
        actor: Optional[Dict[str, Any]] = None,
        session_kind: str = "user_activity",
    ) -> str:
        session_id = uuid.uuid4().hex
        started_at = _parse_iso_datetime(run_detail.get("run_at")) or datetime.now()
        finished_at = _parse_iso_datetime(run_detail.get("completed_at")) or datetime.now()
        diagnostics = run_detail.get("diagnostics") if isinstance(run_detail.get("diagnostics"), dict) else {}
        coverage = diagnostics.get("coverage_summary") if isinstance(diagnostics.get("coverage_summary"), dict) else {}
        providers = diagnostics.get("provider_diagnostics") if isinstance(diagnostics.get("provider_diagnostics"), dict) else {}
        failure = diagnostics.get("failure") if isinstance(diagnostics.get("failure"), dict) else {}
        provider_list = [
            str(item)
            for item in (providers.get("providers_used") or [])
            if str(item).strip()
        ]
        provider_failure_count = int(providers.get("provider_failure_count") or 0)
        status_text = _normalize_business_status(run_detail.get("status") or "completed")
        failed_run = status_text == "failed"
        profile_label = _as_str(run_detail.get("profile_label") or run_detail.get("profile") or "scanner")
        universe_count = int(run_detail.get("universe_size") or coverage.get("input_universe_size") or 0)
        evaluated_count = int(run_detail.get("evaluated_size") or coverage.get("ranked_candidate_count") or 0)
        selected_count = int(run_detail.get("shortlist_size") or coverage.get("shortlisted_count") or 0)
        rejected_count = max(0, evaluated_count - selected_count)
        data_failed_count = int(providers.get("missing_data_symbol_count") or 0)
        skipped_count = int(coverage.get("excluded_total") or 0)
        duration_ms = int(max(0.0, (finished_at - started_at).total_seconds() * 1000))
        selected = run_detail.get("selected") if isinstance(run_detail.get("selected"), list) else run_detail.get("shortlist")
        top_symbol = None
        if isinstance(selected, list) and selected:
            first = selected[0] if isinstance(selected[0], dict) else {}
            top_symbol = _as_str(first.get("symbol") or first.get("code")) or None
        coverage_summary = (
            f"Scanned {universe_count} symbols, evaluated {evaluated_count}, shortlisted {selected_count}."
        )
        source_provider_summary = " / ".join(provider_list[:5]) or _as_str(run_detail.get("source_summary")) or None
        error_message = _masked_message(failure.get("message") or run_detail.get("failure_reason"))
        lifecycle_metadata = _sanitize_metadata({
            "route": "/scanner",
            "endpoint": "/api/v1/scanner/run",
            "market": run_detail.get("market"),
            "configName": profile_label,
            "profile": run_detail.get("profile"),
            "universeCount": universe_count,
            "evaluatedCount": evaluated_count,
            "selectedCount": selected_count,
            "rejectedCount": rejected_count,
            "dataFailedCount": data_failed_count,
            "skippedCount": skipped_count,
            "topSymbol": top_symbol,
            "durationMs": duration_ms,
            "scannerRunId": run_detail.get("id"),
            "scanner_run_id": run_detail.get("id"),
            "traceId": session_id,
            "trace_id": session_id,
            "shortlist_count": selected_count,
            "providers_used": provider_list,
            "sourceProviderSummary": source_provider_summary,
            "sourceSummary": run_detail.get("source_summary"),
            "errorMessage": error_message,
        })
        business_event = {
            "id": session_id,
            "event": f"Scanner: {profile_label}",
            "category": "scanner",
            "type": "scan_run",
            "status": "partial" if provider_failure_count else status_text,
            "summary": f"扫描器运行：{profile_label}",
            "subject": profile_label,
            "symbol": None,
            "market": _as_str(run_detail.get("market")) or None,
            "route": "/scanner",
            "endpoint": "/api/v1/scanner/run",
            "source": source_provider_summary,
            "scannerId": _as_str(run_detail.get("id")) or None,
            "strategyId": None,
            "backtestId": None,
            "recordId": _as_str(run_detail.get("id")) or None,
            "requestId": session_id,
            "userId": None,
            "startedAt": started_at.isoformat(),
            "finishedAt": finished_at.isoformat(),
            "durationMs": duration_ms,
            "stepCount": 3 if failed_run else 4,
            "successStepCount": 1 if failed_run else 4,
            "failedStepCount": 1 if failed_run else 0,
            "skippedStepCount": 0,
            "unknownStepCount": 0,
            "metadata": _sanitize_metadata({
                "eventNames": ["ScannerRunStarted", "ScannerRunFailed" if failed_run else "ScannerRunCompleted"],
                "universeCount": universe_count,
                "evaluatedCount": evaluated_count,
                "selectedCount": selected_count,
                "rejectedCount": rejected_count,
                "dataFailedCount": data_failed_count,
                "skippedCount": skipped_count,
                "topSymbol": top_symbol,
                "durationMs": duration_ms,
                "configName": profile_label,
                "providersUsed": provider_list,
                "providerFailureCount": provider_failure_count,
                "sourceProviderSummary": source_provider_summary,
            }),
        }
        summary = self._merge_summary(
            {
                "business_event": business_event,
                "scanner_run": {
                    "scanner_run_id": run_detail.get("id"),
                    "market": run_detail.get("market"),
                    "profile": run_detail.get("profile"),
                    "profile_label": run_detail.get("profile_label"),
                    "trigger_mode": run_detail.get("trigger_mode"),
                    "status": run_detail.get("status"),
                    "shortlist_count": run_detail.get("shortlist_size"),
                    "coverage_summary": coverage_summary,
                    "coverage": coverage,
                    "lifecycle": lifecycle_metadata,
                    "duration_ms": duration_ms,
                    "top_symbol": top_symbol,
                    "providers_used": provider_list,
                    "provider_diagnostics": providers,
                    "fallback_count": int(providers.get("fallback_count") or 0),
                    "provider_failure_count": provider_failure_count,
                    "warning_summary": list(providers.get("provider_warnings") or []),
                    "error_message": error_message,
                }
            },
            self._summary_meta(
                actor=actor,
                session_kind=session_kind,
                subsystem="scanner",
                action_name="scanner_run",
                destructive=False,
            ),
        )
        self.db.create_execution_log_session(
            session_id=session_id,
            task_id="scanner_run",
            code=str(run_detail.get("market") or "").strip() or None,
            name=business_event["event"],
            overall_status=business_event["status"],
            truth_level="actual",
            summary=summary,
            started_at=started_at,
        )
        self.db.append_execution_log_event(
            session_id=session_id,
            phase="scanner",
            step="ScannerRunStarted",
            target=profile_label,
            status="started",
            truth_level="actual",
            message=f"扫描器启动：{profile_label}",
            detail={
                "level": "INFO",
                "category": "scanner",
                "event_name": "ScannerRunStarted",
                "action": "scanner_run_started",
                "outcome": "unknown",
                **lifecycle_metadata,
            },
            event_at=started_at,
        )
        completion_event_name = "ScannerRunFailed" if failed_run else "ScannerRunCompleted"
        self.db.append_execution_log_event(
            session_id=session_id,
            phase="scanner",
            step=completion_event_name,
            target=profile_label,
            status="failed" if failed_run else "completed",
            truth_level="actual",
            message=error_message or coverage_summary,
            detail={
                "level": "ERROR" if failed_run else "INFO",
                "category": "scanner",
                "event_name": completion_event_name,
                "action": "scanner_run_failed" if failed_run else "scanner_run_completed",
                "outcome": "failed" if failed_run else "ok",
                **lifecycle_metadata,
            },
            event_at=finished_at,
        )
        for step_name, label, metadata in [
            ("load_universe", "加载股票池", {"universeCount": universe_count}),
            ("run_screen", "执行扫描", {"evaluatedCount": evaluated_count, "selectedCount": selected_count}),
            ("save_scan_result", "保存扫描结果", {"scannerRunId": run_detail.get("id")}),
        ]:
            self._append_business_step(
                execution_id=session_id,
                step_id=uuid.uuid4().hex,
                name=step_name,
                label=label,
                category="compute" if step_name != "save_scan_result" else "database",
                status="failed" if failed_run and step_name == "run_screen" else ("skipped" if failed_run and step_name == "save_scan_result" else "success"),
                critical=step_name != "save_scan_result",
                metadata=metadata,
                started_at=started_at,
                finished_at=finished_at,
            )
        self.db.finalize_execution_log_session(
            session_id=session_id,
            overall_status=business_event["status"],
            truth_level="actual",
            summary=summary,
            ended_at=finished_at,
        )
        return session_id

    def record_market_overview_fetch(
        self,
        *,
        panel_name: str,
        endpoint_url: str,
        status: str,
        fetch_timestamp: str,
        error_message: Optional[str] = None,
        raw_response: Optional[Dict[str, Any]] = None,
        actor: Optional[Dict[str, Any]] = None,
    ) -> str:
        raw = _sanitize_metadata(raw_response if isinstance(raw_response, dict) else {})
        event_name = _as_str(raw.get("event_name")) or panel_name
        normalized_status = "completed" if str(status).lower() == "success" else "failed"
        cache_state = _as_str(raw.get("cache")).lower()
        is_timeout = "timeout" in f"{event_name} {error_message or ''} {raw}".lower()
        is_slow = float(raw.get("duration_ms") or 0) >= 2000 if isinstance(raw.get("duration_ms"), (int, float)) else False
        fallback_used = bool(raw.get("fallback_used") or raw.get("fallbackUsed") or raw.get("isFallback"))
        stale_served = cache_state in {"stale_refreshing", "stale_or_fallback"} or bool(raw.get("stale") or raw.get("isStale"))
        if normalized_status == "completed" and event_name in _NOISY_MARKET_EVENTS and not fallback_used and not stale_served and not is_slow:
            return ""
        if normalized_status == "completed" and cache_state in {"hit", "hit_or_refreshed", "refreshed"} and not fallback_used and not stale_served and not is_slow:
            return ""

        if event_name in {"ExternalSourceTimeout", "ExternalDataSourceTimeout"} or is_timeout:
            level = "WARNING"
            category = "data_source"
        elif normalized_status == "failed":
            level = "ERROR" if "invalid" in event_name.lower() else "WARNING"
            category = "data_source" if "source" in event_name.lower() or is_timeout else "cache"
        elif is_slow:
            level = "WARNING"
            category = "api"
            event_name = "MarketCacheColdStartSlow"
        elif fallback_used:
            level = "WARNING"
            category = "data_source"
            event_name = "MarketDataFallbackUsed"
        elif stale_served:
            level = "NOTICE"
            category = "market"
            event_name = "MarketDataStaleServed"
        else:
            level = "INFO"
            category = "market"

        session_id = uuid.uuid4().hex
        started_at = datetime.now()
        detail = {
            "level": level,
            "category": category,
            "event_name": event_name,
            "action": "panel_fetch",
            "panel_name": panel_name,
            "fetch_timestamp": fetch_timestamp,
            "endpoint_url": _sanitize_url(endpoint_url),
            "status": status,
            "error_message": _masked_message(error_message),
            "raw_response": raw,
            "outcome": _outcome_from_status(normalized_status),
        }
        summary = self._merge_summary(
            {"market_overview": detail, "log": {"level": level, "category": category, "event_name": event_name}},
            self._summary_meta(
                actor=actor,
                session_kind="user_activity",
                subsystem=category,
                action_name=event_name,
                destructive=False,
            ),
        )
        emit_notification = getattr(self.db, "_emit_execution_log_notification", None)
        if emit_notification is not None:
            self.db._emit_execution_log_notification = lambda **_kwargs: None  # type: ignore[attr-defined]
        try:
            self.db.create_execution_log_session(
                session_id=session_id,
                task_id="market_overview_fetch",
                code=None,
                name=panel_name,
                overall_status=normalized_status,
                truth_level="actual",
                summary=summary,
                started_at=started_at,
            )
            self.db.append_execution_log_event(
                session_id=session_id,
                phase=category,
                step=event_name,
                target=panel_name,
                status=normalized_status,
                truth_level="actual",
                message=_masked_message(error_message) if error_message else f"{panel_name} refreshed via {_sanitize_url(endpoint_url)}",
                detail=detail,
                event_at=started_at,
            )
            self.db.finalize_execution_log_session(
                session_id=session_id,
                overall_status=normalized_status,
                truth_level="actual",
                summary=summary,
                ended_at=started_at,
            )
        finally:
            if emit_notification is not None:
                self.db._emit_execution_log_notification = emit_notification  # type: ignore[attr-defined]
        return session_id

    def record_portfolio_event(
        self,
        *,
        action: str,
        message: str,
        status: str = "success",
        actor: Optional[Dict[str, Any]] = None,
        account_id: Optional[Any] = None,
        symbol: Optional[str] = None,
        currency: Optional[str] = None,
        record_id: Optional[Any] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> str:
        session_id = uuid.uuid4().hex
        started_at = datetime.now()
        normalized_status = _normalize_business_status(status)
        action_name = _as_str(action) or "portfolio_event"
        symbol_text = _as_str(symbol).upper() or None
        safe_detail = _sanitize_metadata(
            {
                "category": "portfolio",
                "action": action_name,
                "account_id": account_id,
                "symbol": symbol_text,
                "currency": _as_str(currency).upper() or None,
                "record_id": _as_str(record_id) or None,
                "outcome": _outcome_from_status(normalized_status),
                **(detail or {}),
            }
        )
        business_event = {
            "id": session_id,
            "event": f"Portfolio: {action_name}",
            "category": "portfolio",
            "type": action_name,
            "status": normalized_status,
            "summary": _as_str(message) or f"Portfolio {action_name}",
            "subject": symbol_text or _as_str(account_id) or action_name,
            "symbol": symbol_text,
            "market": _as_str(safe_detail.get("market")).upper() or None if isinstance(safe_detail, dict) else None,
            "strategyId": None,
            "scannerId": None,
            "backtestId": None,
            "recordId": _as_str(record_id) or None,
            "requestId": None,
            "userId": None,
            "startedAt": started_at.isoformat(),
            "finishedAt": started_at.isoformat(),
            "durationMs": 0,
            "stepCount": 1,
            "successStepCount": 1 if normalized_status == "success" else 0,
            "failedStepCount": 1 if normalized_status == "failed" else 0,
            "skippedStepCount": 0,
            "unknownStepCount": 0,
            "metadata": safe_detail,
        }
        summary = self._merge_summary(
            {"business_event": business_event, "portfolio_event": safe_detail},
            self._summary_meta(
                actor=actor,
                session_kind="user_activity",
                subsystem="portfolio",
                action_name=action_name,
                destructive=action_name.startswith("delete_"),
            ),
        )
        self.db.create_execution_log_session(
            session_id=session_id,
            task_id=f"portfolio:{action_name}",
            code=symbol_text,
            name=business_event["event"],
            overall_status=normalized_status,
            truth_level="actual",
            summary=summary,
            started_at=started_at,
        )
        self.db.append_execution_log_event(
            session_id=session_id,
            phase="portfolio",
            step=action_name,
            target=symbol_text or _as_str(account_id) or "portfolio",
            status=normalized_status,
            truth_level="actual",
            message=_masked_message(message) or business_event["summary"],
            detail=safe_detail,
            event_at=started_at,
        )
        self.db.finalize_execution_log_session(
            session_id=session_id,
            overall_status=normalized_status,
            truth_level="actual",
            summary=summary,
            ended_at=started_at,
        )
        return session_id

    def record_api_request(
        self,
        *,
        route: str,
        method: str,
        status_code: int,
        duration_ms: float,
        request_id: Optional[str] = None,
        actor: Optional[Dict[str, Any]] = None,
    ) -> str:
        if int(status_code) < 400 and float(duration_ms) < 2000:
            return ""
        level = "ERROR" if int(status_code) >= 500 else "WARNING"
        event_name = "RequestFailed" if int(status_code) >= 400 else "SlowRequest"
        session_id = uuid.uuid4().hex
        started_at = datetime.now()
        safe_route = _sanitize_url(route)
        detail = {
            "level": level,
            "category": "api",
            "event_name": event_name,
            "route": safe_route,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "request_id": request_id,
            "outcome": "failed" if int(status_code) >= 400 else "partial",
        }
        summary = self._merge_summary(
            {"api_request": detail, "log": {"level": level, "category": "api", "event_name": event_name}},
            self._summary_meta(
                actor=actor,
                session_kind="system_event",
                subsystem="api",
                action_name=event_name,
                destructive=False,
            ),
        )
        self.db.create_execution_log_session(
            session_id=session_id,
            task_id=event_name,
            code=None,
            name=safe_route,
            overall_status="failed" if int(status_code) >= 400 else "partial_success",
            truth_level="actual",
            summary=summary,
            started_at=started_at,
        )
        self.db.append_execution_log_event(
            session_id=session_id,
            phase="api",
            step=event_name,
            target=safe_route,
            status="failed" if int(status_code) >= 400 else "partial_success",
            truth_level="actual",
            message=f"{method} {safe_route} took {duration_ms:.0f} ms",
            detail=detail,
            event_at=started_at,
        )
        self.db.finalize_execution_log_session(
            session_id=session_id,
            overall_status="failed" if int(status_code) >= 400 else "partial_success",
            truth_level="actual",
            summary=summary,
            ended_at=started_at,
        )
        return session_id

    def _business_summary_for_execution(self, execution_id: str) -> Dict[str, Any]:
        detail = self.db.get_execution_log_session_detail(execution_id) or {}
        summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
        business = summary.get("business_event") if isinstance(summary.get("business_event"), dict) else {}
        return business

    def _append_business_step(
        self,
        *,
        execution_id: str,
        step_id: str,
        name: str,
        label: Optional[str] = None,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        status: str,
        reason: Optional[str] = None,
        message: Optional[str] = None,
        error_type: Optional[str] = None,
        critical: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        record_id: Optional[str] = None,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        now = datetime.now()
        business = self._business_summary_for_execution(execution_id)
        step_started = started_at or now
        step_finished = finished_at if finished_at is not None else (now if status != "running" else None)
        normalized_status = _normalize_business_status(status)
        normalized_category = _as_str(category) or _data_phase(_as_str(name).replace("fetch_", "")) if _as_str(name).startswith("fetch_") else _as_str(category)
        computed_duration = duration_ms
        if computed_duration is None and step_finished is not None:
            computed_duration = _duration_ms(step_started.isoformat(), step_finished.isoformat())
        endpoint_text = _sanitize_url(_as_str(endpoint) or None)
        detail = {
            "category": business.get("category") or _normalize_log_category(category),
            "event_name": "BusinessExecutionStep",
            "business_step": True,
            "id": step_id,
            "executionId": execution_id,
            "name": _as_str(name),
            "label": _as_str(label) or _ANALYSIS_STEP_LABELS.get(_as_str(name), _as_str(name)),
            "stepCategory": _as_str(normalized_category) or None,
            "provider": _as_str(provider) or None,
            "model": _as_str(model) or None,
            "endpoint": endpoint_text,
            "apiPath": endpoint_text,
            "status": normalized_status,
            "reason": _as_str(reason) or None,
            "message": _masked_message(message) if message else None,
            "startedAt": step_started.isoformat(),
            "finishedAt": step_finished.isoformat() if step_finished else None,
            "durationMs": computed_duration,
            "errorType": _as_str(error_type) or None,
            "errorMessage": _masked_message(message) if normalized_status == "failed" and message else None,
            "recordId": _as_str(record_id) or None,
            "critical": bool(critical),
            "subject": business.get("subject"),
            "symbol": business.get("symbol"),
            "metadata": _sanitize_metadata(metadata or {}),
            "outcome": _outcome_from_status(normalized_status),
        }
        self.db.append_execution_log_event(
            session_id=execution_id,
            phase=business.get("category") or detail["category"] or "system",
            step=_as_str(name),
            target=_as_str(provider) or _as_str(model) or _as_str(endpoint) or _as_str(name),
            status=normalized_status,
            truth_level="actual",
            message=detail["message"] or detail["label"],
            error_code=_as_str(error_type) or None,
            detail=detail,
            event_at=step_finished or step_started,
        )

    def _append_business_step_result(
        self,
        *,
        execution_id: str,
        step_key_or_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None,
        error_type: Optional[str] = None,
        reason: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> None:
        detail = self.db.get_execution_log_session_detail(execution_id) or {}
        steps = self._extract_business_steps(detail.get("events") if isinstance(detail.get("events"), list) else [])
        step_name = _as_str(step_key_or_id)
        prior = None
        for step in reversed(steps):
            if _as_str(step.get("id")) == step_name:
                prior = step
                break
            if (
                _as_str(step.get("name")) == step_name
                and (not provider or _as_str(step.get("provider")) == _as_str(provider))
                and (not model or _as_str(step.get("model")) == _as_str(model))
                and (not endpoint or _as_str(step.get("endpoint") or step.get("apiPath")) == _as_str(endpoint))
                and step.get("status") == "running"
            ):
                prior = step
                break
        if prior is None:
            prior = {
                "id": uuid.uuid4().hex,
                "name": step_name,
                "label": _ANALYSIS_STEP_LABELS.get(step_name, step_name),
                "provider": provider,
                "model": model,
                "endpoint": endpoint,
                "critical": False,
                "metadata": {},
            }
        merged_metadata = {
            **(prior.get("metadata") if isinstance(prior.get("metadata"), dict) else {}),
            **(metadata or {}),
        }
        self._append_business_step(
            execution_id=execution_id,
            step_id=_as_str(prior.get("id")) or uuid.uuid4().hex,
            name=_as_str(prior.get("name") or step_name),
            label=_as_str(prior.get("label")) or None,
            category=_as_str(prior.get("category") or prior.get("stepCategory")) or None,
            provider=_as_str(provider or prior.get("provider")) or None,
            model=_as_str(model or prior.get("model")) or None,
            endpoint=_as_str(endpoint or prior.get("endpoint") or prior.get("apiPath")) or None,
            status=status,
            reason=reason,
            message=message,
            error_type=error_type,
            critical=bool(prior.get("critical")),
            metadata=merged_metadata,
            record_id=_as_str(prior.get("recordId")) or None,
            started_at=_parse_iso_datetime(prior.get("startedAt")) or None,
            finished_at=datetime.now(),
        )

    def _append_configured_events(self, session_id: str, configured: Dict[str, Any]) -> None:
        ai = configured.get("ai") if isinstance(configured, dict) else {}
        data = configured.get("data") if isinstance(configured, dict) else {}
        notification = configured.get("notification") if isinstance(configured, dict) else {}

        if isinstance(ai, dict):
            primary_gateway = _as_str(ai.get("configured_primary_gateway")) or _as_str(ai.get("gateway"))
            backup_gateway = _as_str(ai.get("configured_backup_gateway"))
            primary_model = _as_str(ai.get("configured_primary_model")) or _as_str(ai.get("model"))

            if primary_gateway:
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="ai_route",
                    step="primary_selected",
                    target=primary_gateway,
                    status="selected",
                    truth_level="inferred",
                    message=f"Primary AI gateway selected: {primary_gateway}",
                    detail={"category": "ai_route", "action": "selected"},
                )
            if backup_gateway:
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="ai_route",
                    step="backup_selected",
                    target=backup_gateway,
                    status="selected",
                    truth_level="inferred",
                    message=f"Backup AI gateway selected: {backup_gateway}",
                    detail={"category": "ai_route", "action": "selected"},
                )
            if primary_model:
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="ai_model",
                    step="primary_selected",
                    target=primary_model,
                    status="selected",
                    truth_level=str(ai.get("model_truth") or "inferred"),
                    message=f"Primary AI model selected: {primary_model}",
                    detail={
                        "category": "ai_model",
                        "action": "selected",
                        "configured_primary_model": ai.get("configured_primary_model"),
                    },
                )

            self.db.append_execution_log_event(
                session_id=session_id,
                phase="ai_model",
                step="configured",
                target=_as_str(ai.get("model")) or _as_str(ai.get("provider")) or "ai_route",
                status="attempting",
                truth_level=str(ai.get("model_truth") or "inferred"),
                detail={"category": "ai_model", "action": "attempting", "configured_primary_model": ai.get("configured_primary_model")},
            )

        for key in ("market", "fundamentals", "news", "sentiment"):
            phase = _data_phase(key)
            block = data.get(key) if isinstance(data, dict) else {}
            if not isinstance(block, dict):
                continue
            target = _as_str(block.get("source")) or phase
            source_chain = block.get("source_chain") or []
            status = _as_str(block.get("status")).lower() or ("attempting" if target else "not_configured")
            self.db.append_execution_log_event(
                session_id=session_id,
                phase=phase,
                step="configured",
                target=target,
                status=status,
                truth_level=str(block.get("truth") or "inferred"),
                message=f"{phase} route configured: {target}",
                detail={"category": phase, "action": "selected", "source_chain": source_chain},
            )

        if isinstance(notification, dict):
            channels = notification.get("channels") if isinstance(notification.get("channels"), list) else []
            status = "selected" if channels else "not_configured"
            self.db.append_execution_log_event(
                session_id=session_id,
                phase="notification",
                step="channel_selected",
                target=(channels[0] if channels else "notification"),
                status=status,
                truth_level=str(notification.get("truth") or "inferred"),
                message=f"Notification channels configured: {', '.join(channels) if channels else 'none'}",
                detail={"category": "notification", "action": "selected" if channels else "skipped", "channels": channels},
            )

    def append_runtime_result(
        self,
        *,
        session_id: str,
        runtime_execution: Optional[Dict[str, Any]],
        notification_result: Optional[Dict[str, Any]],
        query_id: Optional[str],
        overall_status: str,
    ) -> None:
        runtime = runtime_execution if isinstance(runtime_execution, dict) else {}
        ai = runtime.get("ai") if isinstance(runtime.get("ai"), dict) else {}
        data = runtime.get("data") if isinstance(runtime.get("data"), dict) else {}
        notification = notification_result if isinstance(notification_result, dict) else (
            runtime.get("notification") if isinstance(runtime.get("notification"), dict) else {}
        )

        if ai:
            primary_gateway = _as_str(ai.get("gateway")) or _as_str(ai.get("configured_primary_gateway"))
            backup_gateway = _as_str(ai.get("configured_backup_gateway"))
            final_model = _as_str(ai.get("model"))
            route_succeeded = bool(final_model)
            ai_attempt_chain = ai.get("attempt_chain") if isinstance(ai.get("attempt_chain"), list) else []

            if primary_gateway:
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="ai_route",
                    step="primary_invoked",
                    target=primary_gateway,
                    status="succeeded" if route_succeeded else "failed",
                    truth_level=str(ai.get("gateway_truth") or "actual"),
                    message=(
                        f"Primary AI gateway {primary_gateway} invoked successfully."
                        if route_succeeded
                        else f"Primary AI gateway {primary_gateway} invocation failed."
                    ),
                    detail={
                        "category": "ai_route",
                        "action": "succeeded" if route_succeeded else "failed",
                        "outcome": _outcome_from_status("succeeded" if route_succeeded else "failed"),
                    },
                )
            if bool(ai.get("fallback_occurred")) and backup_gateway:
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="ai_route",
                    step="fallback_switched",
                    target=backup_gateway,
                    status="switched_to_fallback",
                    truth_level="actual",
                    message=f"AI route switched to backup gateway {backup_gateway}",
                    detail={"category": "ai_route", "action": "switched", "outcome": "ok"},
                )
            if ai_attempt_chain:
                for idx, attempt in enumerate(ai_attempt_chain):
                    if not isinstance(attempt, dict):
                        continue
                    model_name = _as_str(attempt.get("model")) or final_model or "ai_model"
                    status = _status_from_attempt_result(
                        attempt.get("result") or attempt.get("status") or attempt.get("outcome")
                    )
                    message = _masked_message(
                        _as_str(attempt.get("message")) or _as_str(attempt.get("reason"))
                    )
                    reason = _masked_message(_as_str(attempt.get("reason")))
                    self.db.append_execution_log_event(
                        session_id=session_id,
                        phase="ai_model",
                        step=f"attempt_{idx + 1}",
                        target=model_name,
                        status=status,
                        truth_level=str(ai.get("model_truth") or "actual"),
                        message=message,
                        detail={
                            "category": "ai_model",
                            "action": _as_str(attempt.get("action")) or _action_from_status(status),
                            "outcome": _outcome_from_status(status),
                            "reason": reason,
                            "attempt": attempt,
                        },
                    )
                    if idx < len(ai_attempt_chain) - 1 and status in {
                        "failed",
                        "timed_out",
                        "timeout",
                        "empty_result",
                        "invalid_response",
                        "insufficient_fields",
                    }:
                        next_attempt = ai_attempt_chain[idx + 1] if isinstance(ai_attempt_chain[idx + 1], dict) else {}
                        next_model = _as_str(next_attempt.get("model")) or "fallback_model"
                        self.db.append_execution_log_event(
                            session_id=session_id,
                            phase="ai_model",
                            step="fallback",
                            target=next_model,
                            status="switched_to_fallback",
                            truth_level="actual",
                            message=f"Switched to fallback AI model: {next_model}",
                            detail={"category": "ai_model", "action": "switched", "outcome": "ok"},
                        )
            elif final_model:
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="ai_model",
                    step="attempt_1",
                    target=final_model,
                    status="attempting",
                    truth_level=str(ai.get("model_truth") or "actual"),
                    message=f"AI model attempt: {final_model}",
                    detail={"category": "ai_model", "action": "attempting", "outcome": "unknown"},
                )
            self.db.append_execution_log_event(
                session_id=session_id,
                phase="ai_model",
                step="final_success" if final_model else "final_failed",
                target=final_model or _as_str(ai.get("provider")) or "ai",
                status="succeeded" if final_model else "failed",
                truth_level=str(ai.get("model_truth") or "actual"),
                message=(
                    f"Final AI model succeeded: {final_model}"
                    if final_model
                    else "AI model failed to produce a final result."
                ),
                detail={
                    "category": "ai_model",
                    "action": "succeeded" if final_model else "failed",
                    "provider": ai.get("provider"),
                    "gateway": ai.get("gateway"),
                    "fallback_occurred": bool(ai.get("fallback_occurred")),
                    "outcome": _outcome_from_status("succeeded" if final_model else "failed"),
                },
            )

        self._append_data_events(session_id, data)
        self._append_notification_events(session_id, notification)

        existing_detail = self.db.get_execution_log_session_detail(session_id) or {}
        existing_summary = existing_detail.get("summary") if isinstance(existing_detail.get("summary"), dict) else {}
        self.db.finalize_execution_log_session(
            session_id=session_id,
            overall_status=overall_status,
            truth_level="mixed",
            query_id=query_id,
            summary=self._merge_summary(
                existing_summary,
                {
                    "runtime_execution": runtime,
                    "notification_result": notification,
                },
            ),
            ended_at=datetime.now(),
        )
        self.db.attach_execution_session_to_query(session_id=session_id, query_id=query_id)

    def _append_data_events(self, session_id: str, data: Dict[str, Any]) -> None:
        for key in ("market", "fundamentals", "news", "sentiment"):
            phase = _data_phase(key)
            block = data.get(key) if isinstance(data, dict) else {}
            if not isinstance(block, dict):
                continue

            source_chain = block.get("source_chain")
            if isinstance(source_chain, list) and source_chain:
                for idx, attempt in enumerate(source_chain):
                    if not isinstance(attempt, dict):
                        continue
                    explicit_action = _as_str(attempt.get("action")).lower()
                    if explicit_action == "selected":
                        continue
                    target = (
                        _as_str(attempt.get("provider"))
                        or _as_str(attempt.get("source"))
                        or _as_str(attempt.get("target"))
                        or f"{phase}-attempt-{idx + 1}"
                    )
                    status = _status_from_attempt_result(
                        attempt.get("result") or attempt.get("status") or attempt.get("outcome")
                    )
                    reason = _masked_message(_as_str(attempt.get("reason")))
                    message = _masked_message(
                        _as_str(attempt.get("message"))
                        or reason
                        or _as_str(attempt.get("note"))
                    )
                    self.db.append_execution_log_event(
                        session_id=session_id,
                        phase=phase,
                        step=f"attempt_{idx + 1}",
                        target=target,
                        status=status,
                        truth_level="actual",
                        message=message,
                        detail={
                            "category": phase,
                            "action": _as_str(attempt.get("action")) or _action_from_status(status),
                            "outcome": _outcome_from_status(status),
                            "reason": reason,
                            "attempt": attempt,
                        },
                    )
                    if idx < len(source_chain) - 1 and status in {
                        "failed",
                        "timed_out",
                        "timeout",
                        "empty_result",
                        "invalid_response",
                        "insufficient_fields",
                    }:
                        next_attempt = source_chain[idx + 1] if isinstance(source_chain[idx + 1], dict) else {}
                        next_target = (
                            _as_str(next_attempt.get("provider"))
                            or _as_str(next_attempt.get("source"))
                            or _as_str(next_attempt.get("target"))
                            or "fallback"
                        )
                        self.db.append_execution_log_event(
                            session_id=session_id,
                            phase=phase,
                            step="fallback",
                            target=next_target,
                            status="switched_to_fallback",
                            truth_level="actual",
                            message=f"Fallback switched from {target} to {next_target}",
                            detail={"category": phase, "action": "switched", "outcome": "ok"},
                        )
                final_target = _as_str(block.get("source")) or (
                    _as_str(source_chain[-1].get("provider")) if isinstance(source_chain[-1], dict) else ""
                ) or phase
                final_status = _as_str(block.get("status")).lower() or "succeeded"
                final_reason = _masked_message(_as_str(block.get("final_reason")))
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase=phase,
                    step="final",
                    target=final_target,
                    status=final_status,
                    truth_level=str(block.get("truth") or "actual"),
                    message=(
                        f"Final source selected: {final_target}. {final_reason}"
                        if final_reason
                        else f"Final source selected: {final_target}"
                    ),
                    detail={
                        "category": phase,
                        "action": _action_from_status(final_status),
                        "fallback_occurred": bool(block.get("fallback_occurred")),
                        "outcome": _outcome_from_status(final_status),
                        "reason": final_reason,
                    },
                )
            else:
                target = _as_str(block.get("source")) or phase
                status = _as_str(block.get("status")).lower() or "unknown"
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase=phase,
                    step="final",
                    target=target,
                    status=status,
                    truth_level=str(block.get("truth") or "inferred"),
                    message=f"Source result: {target} ({status})",
                    detail={
                        "category": phase,
                        "action": _action_from_status(status),
                        "fallback_occurred": bool(block.get("fallback_occurred")),
                        "outcome": _outcome_from_status(status),
                    },
                )

    def _append_notification_events(self, session_id: str, notification: Dict[str, Any]) -> None:
        if not isinstance(notification, dict):
            notification = {}
        channels = notification.get("channels") if isinstance(notification.get("channels"), list) else []
        attempt_chain = notification.get("attempts") if isinstance(notification.get("attempts"), list) else []
        final_state = _as_str(notification.get("delivery_classification")).lower() or classify_notification_state(notification)
        if final_state not in _NOTIFICATION_STATES:
            final_state = "failed"

        if not channels:
            self.db.append_execution_log_event(
                session_id=session_id,
                phase="notification",
                step="final",
                target="notification",
                status=final_state,
                truth_level=str(notification.get("truth") or "actual"),
                message=_masked_message(notification.get("error")),
                detail={
                    "category": "notification",
                    "action": _action_from_status(final_state),
                    "channels": [],
                    "outcome": _outcome_from_status(final_state),
                },
            )
            return

        if attempt_chain:
            for idx, attempt in enumerate(attempt_chain):
                if not isinstance(attempt, dict):
                    continue
                channel = _as_str(attempt.get("channel")) or _as_str(attempt.get("target")) or str(channels[0])
                status = _status_from_attempt_result(
                    attempt.get("result") or attempt.get("status") or attempt.get("outcome")
                )
                reason = _masked_message(_as_str(attempt.get("reason")))
                message = _masked_message(
                    _as_str(attempt.get("message"))
                    or reason
                    or f"Notification attempt on channel {channel}"
                )
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="notification",
                    step=f"attempt_{idx + 1}",
                    target=channel,
                    status=status,
                    truth_level=str(notification.get("truth") or "actual"),
                    message=message,
                    detail={
                        "category": "notification",
                        "action": _as_str(attempt.get("action")) or _action_from_status(status),
                        "channels": channels,
                        "reason": reason,
                        "outcome": _outcome_from_status(status),
                        "attempt": attempt,
                    },
                )
                if idx < len(attempt_chain) - 1 and status in {"failed", "timed_out", "timeout", "empty_result", "invalid_response"}:
                    next_attempt = attempt_chain[idx + 1] if isinstance(attempt_chain[idx + 1], dict) else {}
                    next_channel = _as_str(next_attempt.get("channel")) or _as_str(next_attempt.get("target")) or "backup_channel"
                    self.db.append_execution_log_event(
                        session_id=session_id,
                        phase="notification",
                        step="fallback",
                        target=next_channel,
                        status="switched_to_fallback",
                        truth_level="actual",
                        message=f"Notification fallback switched to {next_channel}",
                        detail={"category": "notification", "action": "switched", "outcome": "ok"},
                    )
        else:
            for idx, channel in enumerate(channels):
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="notification",
                    step=f"attempt_{idx + 1}",
                    target=str(channel),
                    status="attempting",
                    truth_level=str(notification.get("truth") or "actual"),
                    message=f"Attempt notification channel: {channel}",
                    detail={"category": "notification", "action": "attempting", "channels": channels, "outcome": "unknown"},
                )
        self.db.append_execution_log_event(
            session_id=session_id,
            phase="notification",
            step="final",
            target=str(channels[0]),
            status=final_state,
            truth_level=str(notification.get("truth") or "actual"),
            message=_masked_message(notification.get("error")),
            detail={
                "category": "notification",
                "action": _action_from_status(final_state),
                "raw_status": notification.get("status"),
                "success": notification.get("success"),
                "outcome": _outcome_from_status(final_state),
            },
        )

    def fail_session(self, *, session_id: str, error_message: str, query_id: Optional[str] = None) -> None:
        self.db.append_execution_log_event(
            session_id=session_id,
            phase="system",
            step="task_failed",
            target="analysis",
            status="failed",
            truth_level="actual",
            message=_masked_message(error_message),
        )
        self.db.finalize_execution_log_session(
            session_id=session_id,
            overall_status="failed",
            truth_level="actual",
            query_id=query_id,
            summary={"error": _masked_message(error_message)},
            ended_at=datetime.now(),
        )

    @staticmethod
    def _runtime_from_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(summary, dict):
            return {}
        runtime = summary.get("runtime_execution")
        if isinstance(runtime, dict):
            return runtime
        configured = summary.get("configured_execution")
        if isinstance(configured, dict):
            return configured
        return {}

    @staticmethod
    def _extract_final_sources(runtime: Dict[str, Any]) -> Dict[str, Optional[str]]:
        data = runtime.get("data") if isinstance(runtime.get("data"), dict) else {}
        def _source(key: str) -> Optional[str]:
            block = data.get(key) if isinstance(data, dict) else {}
            if not isinstance(block, dict):
                return None
            source = _as_str(block.get("source"))
            return source or None
        return {
            "market": _source("market"),
            "fundamentals": _source("fundamentals"),
            "news": _source("news"),
            "sentiment": _source("sentiment"),
        }

    @staticmethod
    def _event_attempt_count(events: List[Dict[str, Any]], phase: str) -> int:
        return sum(
            1
            for event in events
            if str(event.get("phase") or "").strip().lower() == phase
            and str(event.get("step") or "").strip().lower().startswith("attempt_")
        )

    @staticmethod
    def _event_has_fallback(events: List[Dict[str, Any]], phase_prefix: str) -> bool:
        for event in events:
            phase = str(event.get("phase") or "").strip().lower()
            step = str(event.get("step") or "").strip().lower()
            status = str(event.get("status") or "").strip().lower()
            if phase.startswith(phase_prefix) and (
                step == "fallback" or status == "switched_to_fallback"
            ):
                return True
        return False

    @staticmethod
    def _top_failure_reason(
        *,
        events: Optional[List[Dict[str, Any]]] = None,
        summary: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        for event in events or []:
            status = str(event.get("status") or "").strip().lower()
            if status in {"failed", "timed_out", "timeout_unknown"}:
                msg = _masked_message(_as_str(event.get("message")))
                if msg:
                    return msg
        if isinstance(summary, dict):
            msg = _masked_message(_as_str(summary.get("error")))
            if msg:
                return msg
        return None

    @staticmethod
    def _operation_status_label(status: Any) -> str:
        normalized = _as_str(status).lower()
        if normalized in {"completed", "success", "succeeded", "ok"}:
            return "success"
        if normalized in {"partial", "partial_success", "timeout_unknown", "timed_out", "timeout", "switched_to_fallback"}:
            return "partial fail"
        if normalized in {"failed", "failed_runtime", "error", "empty_result", "invalid_response", "insufficient_fields"}:
            return "fail"
        return normalized or "unknown"

    @staticmethod
    def _operation_kind(summary: Dict[str, Any], code: Optional[str], name: Optional[str], task_id: Optional[str]) -> Tuple[str, str]:
        meta = summary.get("meta") if isinstance(summary.get("meta"), dict) else {}
        subsystem = _as_str(meta.get("subsystem")).lower()
        task = _as_str(task_id).lower()
        label = f"{_as_str(name)} {_as_str(task_id)}".lower()
        if subsystem == "scanner" or "scanner" in task:
            return "market_scanning", "Market Scanning"
        if subsystem == "backtest" or "backtest" in task or "backtest" in label:
            return "backtesting", "Backtesting"
        if code or subsystem == "analysis":
            return "single_stock_analysis", "Single Stock Analysis"
        return "other", _as_str(meta.get("action_name")) or _as_str(name) or "System Operation"

    @staticmethod
    def _runtime_metric(runtime: Dict[str, Any]) -> Optional[str]:
        for key in ("score", "final_score", "rating_score", "total_score"):
            value = runtime.get(key)
            if value is not None and _as_str(value):
                return f"Score {value}"
        metrics = runtime.get("metrics") if isinstance(runtime.get("metrics"), dict) else {}
        for key in ("score", "total_return", "return_pct", "profit_loss", "pnl", "completion_status"):
            value = metrics.get(key)
            if value is not None and _as_str(value):
                label = key.replace("_", " ").title()
                suffix = "%" if key == "return_pct" and "%" not in _as_str(value) else ""
                return f"{label} {value}{suffix}"
        return None

    def _operation_summary_fields(
        self,
        *,
        overall_status: str,
        summary: Dict[str, Any],
        code: Optional[str] = None,
        name: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compatibility view for Admin Logs list rows.

        The persisted schema remains session/event based; these derived fields
        give the frontend a stable operation format across stock analysis,
        scanner runs, and backtests without migrating historical rows.
        """
        runtime = self._runtime_from_summary(summary)
        category, operation_type = self._operation_kind(summary, code, name, task_id)
        scanner_run = summary.get("scanner_run") if isinstance(summary.get("scanner_run"), dict) else {}
        backtest = summary.get("backtest") if isinstance(summary.get("backtest"), dict) else {}

        if category == "market_scanning":
            scan_label = _as_str(scanner_run.get("profile_label")) or _as_str(scanner_run.get("profile")) or _as_str(name) or "market scan"
            target = scan_label
            shortlist = scanner_run.get("shortlist_count")
            coverage = scanner_run.get("coverage") if isinstance(scanner_run.get("coverage"), dict) else {}
            success_rate = coverage.get("success_rate") or coverage.get("provider_success_rate")
            metric_parts = []
            if shortlist is not None:
                metric_parts.append(f"{shortlist} candidates")
            if success_rate is not None:
                metric_parts.append(f"{success_rate} success rate")
            key_metric = ", ".join(metric_parts) or _as_str(scanner_run.get("coverage_summary")) or None
        elif category == "backtesting":
            target = (
                _as_str(backtest.get("backtest_id"))
                or _as_str(backtest.get("strategy"))
                or _as_str(runtime.get("backtest_id"))
                or _as_str(runtime.get("strategy"))
                or _as_str(name)
                or _as_str(task_id)
                or "backtest"
            )
            key_metric = self._runtime_metric(runtime) or _as_str(backtest.get("key_metric")) or _as_str(backtest.get("status")) or None
        elif category == "single_stock_analysis":
            target = _as_str(code) or _as_str(name) or _as_str(task_id) or "stock"
            key_metric = self._runtime_metric(runtime)
        else:
            target = _as_str(code) or _as_str(name) or _as_str(task_id) or operation_type
            key_metric = self._runtime_metric(runtime)

        return {
            "operation_category": category,
            "operation_type": operation_type,
            "operation_target": target,
            "operation_status": self._operation_status_label(overall_status),
            "key_metric": key_metric,
        }

    @staticmethod
    def _status_for_operator(status: Any) -> str:
        normalized = _as_str(status).lower()
        if normalized in {"completed", "success", "succeeded", "ok", "selected"}:
            return "success"
        if normalized in {"switched_to_fallback", "partial", "partial_success", "timeout", "timed_out", "timeout_unknown", "insufficient_fields"}:
            return "fallback" if normalized == "switched_to_fallback" else "partial fail"
        if normalized in {"failed", "error", "empty_result", "invalid_response", "failed_runtime"}:
            return "fail"
        return normalized or "unknown"

    def _build_operation_detail(
        self,
        *,
        session: Dict[str, Any],
        summary: Dict[str, Any],
        events: List[Dict[str, Any]],
        readable: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the unified detail drawer payload from existing event rows."""
        ai_calls: List[Dict[str, Any]] = []
        data_calls: List[Dict[str, Any]] = []
        timeline: List[Dict[str, Any]] = []
        diagnostics: List[Dict[str, Any]] = []

        for event in events:
            phase = _as_str(event.get("phase")).lower()
            category = _as_str(event.get("category")).lower() or phase
            detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
            attempt = detail.get("attempt") if isinstance(detail.get("attempt"), dict) else {}
            status = self._status_for_operator(event.get("status"))
            target = _as_str(event.get("target"))
            message = _masked_message(_as_str(event.get("message"))) or _masked_message(_as_str(detail.get("reason"))) or ""
            fallback_chain = detail.get("fallback_chain") or attempt.get("fallback_chain")
            stack_trace = detail.get("stack_trace") or attempt.get("stack_trace") or attempt.get("traceback")
            response = detail.get("response") or attempt.get("response")

            if phase.startswith("ai_") or phase == "ai":
                ai_calls.append(
                    {
                        "model": target or _as_str(attempt.get("model")) or "AI model",
                        "version": _as_str(attempt.get("version")) or _as_str(attempt.get("model_version")) or _as_str(detail.get("version")) or None,
                        "status": status,
                        "notes": message or None,
                        "fallback_chain": fallback_chain,
                        "executed_at": event.get("event_at"),
                        "error": _masked_message(_as_str(detail.get("reason"))) or None,
                    }
                )
            if phase.startswith("data_") or category.startswith("data_") or category in {"scanner", "market_overview"}:
                data_calls.append(
                    {
                        "source": target or _as_str(attempt.get("source")) or _as_str(attempt.get("provider")) or category,
                        "status": status,
                        "error": _masked_message(_as_str(detail.get("reason"))) or (message if status in {"fail", "partial fail"} else None),
                        "retry_fallback": _as_str(fallback_chain) or ("fallback" if status == "fallback" else None),
                        "notes": message or None,
                        "executed_at": event.get("event_at"),
                        "response": response,
                    }
                )

            action = _as_str(event.get("action")) or _as_str(event.get("step")) or "event"
            label = f"{target} {action}".strip()
            if status == "fallback":
                label = f"Fallback triggered: {label}"
            elif status == "fail":
                label = f"{label} failed"
            timeline.append(
                {
                    "timestamp": event.get("event_at"),
                    "label": label,
                    "status": status,
                    "category": category or phase,
                    "message": message or None,
                }
            )
            if status in {"fail", "partial fail", "fallback"} or stack_trace or event.get("error_code"):
                diagnostics.append(
                    {
                        "severity": "error" if status == "fail" else "warning",
                        "source": target or category or phase,
                        "message": message or _masked_message(_as_str(event.get("error_code"))) or status,
                        "stack_trace": _masked_message(_as_str(stack_trace)) if stack_trace else None,
                        "error_code": event.get("error_code"),
                        "fallback_chain": fallback_chain,
                    }
                )

        scanner_run = summary.get("scanner_run") if isinstance(summary.get("scanner_run"), dict) else {}
        providers = scanner_run.get("providers_used") if isinstance(scanner_run.get("providers_used"), list) else []
        existing_sources = {_as_str(item.get("source")).lower() for item in data_calls if isinstance(item, dict)}
        for provider in providers:
            provider_name = _as_str(provider)
            if provider_name and provider_name.lower() not in existing_sources:
                data_calls.append(
                    {
                        "source": provider_name,
                        "status": "success",
                        "error": None,
                        "retry_fallback": None,
                        "notes": "Provider recorded by scanner diagnostics.",
                        "executed_at": session.get("started_at"),
                    }
                )

        return {
            "operation_category": readable.get("operation_category"),
            "operation_type": readable.get("operation_type"),
            "target": readable.get("operation_target"),
            "status": readable.get("operation_status"),
            "key_metric": readable.get("key_metric"),
            "ai_calls": ai_calls,
            "data_source_calls": data_calls,
            "timeline": timeline,
            "diagnostics": diagnostics,
        }

    @staticmethod
    def _phase_attempt_events(events: List[Dict[str, Any]], phase: str) -> List[Dict[str, Any]]:
        phase_key = str(phase or "").strip().lower()
        attempts: List[Dict[str, Any]] = []
        for event in events or []:
            current_phase = str(event.get("phase") or "").strip().lower()
            if current_phase != phase_key:
                continue
            step = str(event.get("step") or "").strip().lower()
            if step.startswith("attempt_"):
                attempts.append(event)
        return attempts

    @staticmethod
    def _build_chain_narrative(label: str, attempts: List[Dict[str, Any]], final_target: Optional[str]) -> Optional[str]:
        if not attempts:
            if final_target:
                return f"{label} final source accepted: {final_target}."
            return None
        first = attempts[0]
        first_target = _as_str(first.get("target")) or "unknown"
        first_status = _as_str(first.get("status")).lower()
        final = None
        for item in attempts:
            status = _as_str(item.get("status")).lower()
            if status in {"succeeded", "success", "ok", "partial_success", "completed"}:
                final = item
                break
        if final:
            final_target_name = _as_str(final.get("target")) or final_target or "unknown"
            if final_target_name != first_target:
                reason = _masked_message(_as_str(first.get("message"))) or _masked_message(_as_str(first.get("detail", {}).get("reason")))
                return (
                    f"{label} first attempted {first_target} ({first_status or 'failed'}), then switched and accepted {final_target_name}."
                    + (f" Reason: {reason}" if reason else "")
                )
            return f"{label} attempted {first_target} and succeeded without fallback."
        reason = _masked_message(_as_str(attempts[-1].get("message"))) or _masked_message(_as_str(attempts[-1].get("detail", {}).get("reason")))
        return f"{label} attempts failed; final source unresolved." + (f" Reason: {reason}" if reason else "")

    def build_readable_summary(
        self,
        *,
        overall_status: str,
        summary: Dict[str, Any],
        events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        meta = summary.get("meta") if isinstance(summary.get("meta"), dict) else {}
        runtime = self._runtime_from_summary(summary)
        ai = runtime.get("ai") if isinstance(runtime.get("ai"), dict) else {}
        final_ai_model = _as_str(ai.get("model")) or None
        ai_fallback_used = bool(ai.get("fallback_occurred")) or self._event_has_fallback(events or [], "ai_")
        ai_attempts_count = self._event_attempt_count(events or [], "ai_model") + self._event_attempt_count(events or [], "ai")
        if ai_attempts_count <= 0 and final_ai_model:
            ai_attempts_count = 1

        final_sources = self._extract_final_sources(runtime)
        data_fallback_used = bool(
            self._event_has_fallback(events or [], "data_")
            or any(
                bool(
                    ((runtime.get("data") or {}).get(key) or {}).get("fallback_occurred")
                )
                for key in ("market", "fundamentals", "news", "sentiment")
            )
        )

        notification = summary.get("notification_result") if isinstance(summary.get("notification_result"), dict) else (
            runtime.get("notification") if isinstance(runtime.get("notification"), dict) else {}
        )
        notification_classification = (
            _as_str(notification.get("delivery_classification")).lower()
            or classify_notification_state(notification if isinstance(notification, dict) else {})
        )
        if notification_classification not in _NOTIFICATION_STATES:
            notification_classification = "failed"

        failure_reason = self._top_failure_reason(events=events, summary=summary)
        scanner_run = summary.get("scanner_run") if isinstance(summary.get("scanner_run"), dict) else {}

        narrative_parts: List[str] = []
        ai_attempts = self._phase_attempt_events(events or [], "ai_model")
        ai_story = self._build_chain_narrative("AI", ai_attempts, final_ai_model)
        if ai_story:
            ai_gateway = _as_str(ai.get("gateway")) or _as_str(ai.get("configured_primary_gateway")) or None
            if ai_gateway:
                narrative_parts.append(f"{ai_story} Gateway: {ai_gateway}.")
            else:
                narrative_parts.append(ai_story)

        market_story = self._build_chain_narrative(
            "Market data",
            self._phase_attempt_events(events or [], "data_market"),
            final_sources.get("market"),
        )
        if market_story:
            narrative_parts.append(market_story)
        fundamental_story = self._build_chain_narrative(
            "Fundamentals",
            self._phase_attempt_events(events or [], "data_fundamentals"),
            final_sources.get("fundamentals"),
        )
        if fundamental_story:
            narrative_parts.append(fundamental_story)
        news_story = self._build_chain_narrative(
            "News",
            self._phase_attempt_events(events or [], "data_news"),
            final_sources.get("news"),
        )
        if news_story:
            narrative_parts.append(news_story)
        sentiment_story = self._build_chain_narrative(
            "Sentiment",
            self._phase_attempt_events(events or [], "data_sentiment"),
            final_sources.get("sentiment"),
        )
        if sentiment_story:
            narrative_parts.append(sentiment_story)

        if notification_classification == "timeout_unknown":
            narrative_parts.append("Notification timed out after send attempt; final delivery is unknown.")
        elif notification_classification == "partial_success":
            narrative_parts.append("Notification had partial success across channels.")
        elif notification_classification == "failed":
            narrative_parts.append("Notification failed.")
        elif notification_classification == "success":
            narrative_parts.append("Notification succeeded.")
        elif notification_classification == "not_configured":
            narrative_parts.append("Notification channel not configured for this run.")

        if failure_reason:
            narrative_parts.append(f"Top failure reason: {failure_reason}")
        scanner_coverage_summary = _as_str(scanner_run.get("coverage_summary")) or None
        if scanner_coverage_summary:
            narrative_parts.append(scanner_coverage_summary)
        scanner_warning_summary = scanner_run.get("warning_summary") if isinstance(scanner_run.get("warning_summary"), list) else []
        if scanner_warning_summary:
            narrative_parts.append(f"Scanner warnings: {'; '.join(str(item) for item in scanner_warning_summary[:3])}")

        summary_paragraph = " ".join(part for part in narrative_parts if part).strip()

        return {
            "actor_user_id": _as_str(meta.get("actor_user_id")) or None,
            "actor_username": _as_str(meta.get("actor_username")) or None,
            "actor_display": _as_str(meta.get("actor_display")) or None,
            "actor_role": _as_str(meta.get("actor_role")) or None,
            "actor_type": _as_str(meta.get("actor_type")) or _as_str(meta.get("actor_role")) or None,
            "actor_session_id": _as_str(meta.get("actor_session_id")) or None,
            "actor_request_id": _as_str(meta.get("actor_request_id")) or None,
            "session_kind": _as_str(meta.get("session_kind")) or "user_activity",
            "subsystem": _as_str(meta.get("subsystem")) or "analysis",
            "action_name": _as_str(meta.get("action_name")) or None,
            "destructive": bool(meta.get("destructive")),
            "final_ai_model": final_ai_model,
            "ai_attempts_count": ai_attempts_count,
            "ai_fallback_used": ai_fallback_used,
            "final_market_source": final_sources.get("market"),
            "final_fundamental_source": final_sources.get("fundamentals"),
            "final_news_source": final_sources.get("news"),
            "final_sentiment_source": final_sources.get("sentiment"),
            "data_fallback_used": data_fallback_used,
            "notification_classification": notification_classification,
            "top_failure_reason": failure_reason,
            "scanner_run_id": scanner_run.get("scanner_run_id"),
            "scanner_market": scanner_run.get("market"),
            "scanner_profile": scanner_run.get("profile"),
            "scanner_profile_label": scanner_run.get("profile_label"),
            "scanner_shortlist_count": scanner_run.get("shortlist_count"),
            "scanner_fallback_count": scanner_run.get("fallback_count"),
            "scanner_provider_failure_count": scanner_run.get("provider_failure_count"),
            "scanner_providers_used": scanner_run.get("providers_used") if isinstance(scanner_run.get("providers_used"), list) else [],
            "scanner_coverage_summary": scanner_coverage_summary,
            "summary_paragraph": summary_paragraph or None,
            "status": _as_str(overall_status) or "unknown",
            **self._operation_summary_fields(
                overall_status=overall_status,
                summary=summary,
            ),
        }

    @staticmethod
    def _extract_business_steps(events: List[Dict[str, Any]], *, execution_finished: bool = False) -> List[Dict[str, Any]]:
        merged: Dict[Tuple[str, str, str, str, str], Dict[str, Any]] = {}
        order: List[Tuple[str, str, str, str, str]] = []
        for event in events or []:
            if not isinstance(event, dict):
                continue
            detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
            if not bool(detail.get("business_step")):
                continue
            normalized = normalize_trace_step_status(
                {"detail": detail, **event},
                execution_finished=execution_finished,
                execution_status="success" if execution_finished else "running",
            )
            status = _as_str(normalized.get("status")) or "unknown"
            name = _as_str(detail.get("name") or event.get("step"))
            key = (
                name,
                _as_str(detail.get("provider")),
                _as_str(detail.get("model")),
                _as_str(detail.get("endpoint") or detail.get("apiPath")),
                _as_str(detail.get("subject") or detail.get("symbol")),
            )
            current = {
                "id": _as_str(detail.get("id")) or None,
                "executionId": _as_str(detail.get("executionId")) or None,
                "name": name,
                "label": _as_str(detail.get("label")) or _ANALYSIS_STEP_LABELS.get(name, name),
                "category": _as_str(detail.get("stepCategory") or detail.get("category")) or None,
                "provider": _as_str(detail.get("provider")) or None,
                "model": _as_str(detail.get("model")) or None,
                "endpoint": _sanitize_url(_as_str(detail.get("endpoint") or detail.get("apiPath")) or None),
                "apiPath": _sanitize_url(_as_str(detail.get("apiPath") or detail.get("endpoint")) or None),
                "status": status,
                "reason": _as_str(normalized.get("reason")) or None,
                "message": _masked_message(normalized.get("message")) if normalized.get("message") else None,
                "startedAt": detail.get("startedAt") or event.get("event_at"),
                "finishedAt": detail.get("finishedAt") or (event.get("event_at") if status != "running" else None),
                "durationMs": detail.get("durationMs"),
                "errorType": _as_str(detail.get("errorType") or event.get("error_code")) or None,
                "errorMessage": _masked_message(detail.get("errorMessage") or normalized.get("message")) if status == "failed" else None,
                "recordId": _as_str(detail.get("recordId")) or None,
                "critical": bool(detail.get("critical")),
                "metadata": _sanitize_metadata(detail.get("metadata") if isinstance(detail.get("metadata"), dict) else {}),
            }
            if key not in merged:
                merged[key] = current
                order.append(key)
                continue
            previous = merged[key]
            attempts = int(previous.get("attempts") or 1) + 1
            next_status = current["status"]
            previous_status = _as_str(previous.get("status"))
            if next_status == "running" and previous_status in {"success", "failed", "skipped", "unknown"}:
                next_status = previous_status
            merged[key] = {
                **previous,
                **{k: v for k, v in current.items() if v not in (None, "")},
                "status": next_status,
                "startedAt": previous.get("startedAt") or current.get("startedAt"),
                "finishedAt": current.get("finishedAt") or previous.get("finishedAt"),
                "metadata": {
                    **(previous.get("metadata") if isinstance(previous.get("metadata"), dict) else {}),
                    **(current.get("metadata") if isinstance(current.get("metadata"), dict) else {}),
                    "attempts": attempts,
                },
            }
            if merged[key]["status"] == "unknown" and previous_status in {"success", "failed", "skipped"}:
                merged[key]["status"] = previous_status
            merged[key]["metadata"] = _sanitize_metadata(merged[key]["metadata"])
        return [merged[key] for key in order]

    @staticmethod
    def _infer_analysis_status(steps: List[Dict[str, Any]], *, record_id: Optional[str] = None) -> str:
        if not steps:
            return "running"
        failed_steps = [step for step in steps if step.get("status") == "failed"]
        critical_failed = [
            step for step in failed_steps
            if bool(step.get("critical")) or _as_str(step.get("name")) in _CRITICAL_ANALYSIS_STEPS
        ]
        has_record = bool(_as_str(record_id) or any(_as_str(step.get("recordId")) for step in steps))
        if critical_failed:
            return "partial" if has_record and not any(_as_str(step.get("name")) == "ai_analysis" for step in critical_failed) else "failed"
        if failed_steps:
            return "partial"
        if any(step.get("status") == "running" for step in steps):
            return "running"
        return "success"

    @staticmethod
    def _infer_business_status(steps: List[Dict[str, Any]]) -> str:
        if not steps:
            return "success"
        failed_steps = [step for step in steps if step.get("status") == "failed"]
        if any(bool(step.get("critical")) for step in failed_steps):
            return "failed"
        if failed_steps:
            return "partial"
        if any(step.get("status") == "running" for step in steps):
            return "running"
        return "success"

    @staticmethod
    def _step_from_runtime_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        phase = _as_str(event.get("phase")).lower()
        step = _as_str(event.get("step")).lower()
        detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
        action = _as_str(detail.get("action")).lower()
        if phase == "ai_route":
            return None
        if step in {"analysis_started", "analysis_finished", "task_started", "task_failed", "configured", "primary_selected", "backup_selected", "channel_selected", "fallback"}:
            return None
        if action in {"selected", "switched"}:
            return None
        name = None
        label = None
        if phase == "data_market":
            name, label = "fetch_quote", _ANALYSIS_STEP_LABELS["fetch_quote"]
        elif phase == "data_fundamentals":
            name, label = "fetch_financials", _ANALYSIS_STEP_LABELS["fetch_financials"]
        elif phase == "data_news":
            name, label = "fetch_news", _ANALYSIS_STEP_LABELS["fetch_news"]
        elif phase == "data_sentiment":
            name, label = "fetch_market_context", _ANALYSIS_STEP_LABELS["fetch_market_context"]
        elif phase.startswith("ai_") or phase == "ai":
            name, label = "ai_analysis", _ANALYSIS_STEP_LABELS["ai_analysis"]
        elif phase == "report":
            name, label = "save_record", _ANALYSIS_STEP_LABELS["save_record"]
        if not name:
            return None
        normalized = normalize_trace_step_status(event)
        status = _as_str(normalized.get("status")) or "unknown"
        attempt = detail.get("attempt") if isinstance(detail.get("attempt"), dict) else {}
        provider = (
            _as_str(detail.get("provider"))
            or _as_str(attempt.get("provider"))
            or _as_str(attempt.get("source"))
            or _as_str(event.get("target"))
            or _as_str(detail.get("source"))
            or None
        )
        model = _as_str(attempt.get("model")) or None
        if phase.startswith("ai_"):
            provider = _as_str(detail.get("gateway")) or _as_str(detail.get("provider")) or provider
            model = model or _as_str(event.get("target")) or None
        message = _masked_message(normalized.get("message"))
        reason = _as_str(normalized.get("reason")) or None
        return {
            "name": name,
            "label": label,
            "provider": provider,
            "model": model,
            "apiPath": _as_str(detail.get("apiPath") or detail.get("api_path") or detail.get("endpoint_url")) or None,
            "status": status,
            "startedAt": event.get("event_at"),
            "finishedAt": event.get("event_at"),
            "durationMs": detail.get("durationMs") or detail.get("duration_ms"),
            "errorType": _as_str(event.get("error_code")) or None,
            "reason": reason,
            "message": message,
            "errorMessage": message if status == "failed" else None,
            "recordId": _as_str(detail.get("recordId") or detail.get("record_id")) or None,
            "critical": name in _CRITICAL_ANALYSIS_STEPS,
            "metadata": _sanitize_metadata(detail),
        }

    def _build_business_steps_from_session(self, detail: Dict[str, Any]) -> List[Dict[str, Any]]:
        events = detail.get("events") if isinstance(detail.get("events"), list) else []
        explicit = self._extract_business_steps(events, execution_finished=bool(detail.get("ended_at")))
        if explicit:
            return explicit
        derived: Dict[Tuple[str, str, str, str, str], Dict[str, Any]] = {}
        order: List[Tuple[str, str, str, str, str]] = []
        execution_finished = bool(detail.get("ended_at"))
        execution_status = _as_str(detail.get("overall_status")) or ("success" if execution_finished else "running")
        for event in events:
            if not isinstance(event, dict):
                continue
            step = self._step_from_runtime_event(event)
            if step is None:
                continue
            normalized = normalize_trace_step_status(
                {"detail": step.get("metadata"), **step},
                execution_finished=execution_finished,
                execution_status=execution_status,
            )
            step["status"] = _as_str(normalized.get("status")) or step.get("status") or "unknown"
            step["reason"] = _as_str(normalized.get("reason")) or step.get("reason")
            step["message"] = _masked_message(normalized.get("message")) if normalized.get("message") else step.get("message")
            if step["status"] == "failed" and not step.get("errorMessage"):
                step["errorMessage"] = step.get("message")
            if step["status"] != "running" and not step.get("finishedAt"):
                step["finishedAt"] = step.get("startedAt")
            identity = _as_str(step.get("model")) or _as_str(step.get("provider"))
            key = (
                _as_str(step.get("name")),
                identity,
                _as_str(step.get("apiPath") or step.get("endpoint")),
                _as_str(step.get("recordId")),
                _as_str(step.get("provider")) if not step.get("model") else "",
            )
            if key not in derived:
                derived[key] = step
                order.append(key)
                continue
            previous = derived[key]
            attempts = int((previous.get("metadata") or {}).get("attempts") or 1) + 1
            merged = {
                **previous,
                **{k: v for k, v in step.items() if v not in (None, "")},
                "startedAt": previous.get("startedAt") or step.get("startedAt"),
                "finishedAt": step.get("finishedAt") or previous.get("finishedAt"),
                "metadata": {
                    **(previous.get("metadata") if isinstance(previous.get("metadata"), dict) else {}),
                    **(step.get("metadata") if isinstance(step.get("metadata"), dict) else {}),
                    "attempts": attempts,
                },
            }
            if step.get("status") == "running" and previous.get("status") in {"success", "failed", "skipped", "unknown"}:
                merged["status"] = previous.get("status")
            elif step.get("status") == "unknown" and previous.get("status") in {"success", "failed", "skipped"}:
                merged["status"] = previous.get("status")
            else:
                merged["status"] = step.get("status")
            derived[key] = merged
        return [derived[key] for key in order]

    def _business_event_triage_fields(
        self,
        *,
        row: Dict[str, Any],
        summary: Dict[str, Any],
        business: Dict[str, Any],
        detail: Dict[str, Any],
        status: str,
        symbol: Optional[str],
        steps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        meta = summary.get("meta") if isinstance(summary.get("meta"), dict) else {}
        market_overview = summary.get("market_overview") if isinstance(summary.get("market_overview"), dict) else {}
        business_metadata = business.get("metadata") if isinstance(business.get("metadata"), dict) else {}
        events = detail.get("events") if isinstance(detail.get("events"), list) else []
        enriched_events = [
            _sanitize_metadata(self._enrich_event(event))
            for event in events
            if isinstance(event, dict)
        ]
        top_event = self._top_event(enriched_events) or {}
        top_detail = top_event.get("detail") if isinstance(top_event.get("detail"), dict) else {}
        raw_response = top_detail.get("raw_response") if isinstance(top_detail.get("raw_response"), dict) else (
            market_overview.get("raw_response") if isinstance(market_overview.get("raw_response"), dict) else {}
        )
        actor_type = _first_text(
            meta.get("actor_type"),
            meta.get("actor_role"),
            business_metadata.get("actor_type"),
            business_metadata.get("actorRole"),
        )
        actor_label = _first_text(
            meta.get("actor_display"),
            meta.get("actor_username"),
            meta.get("actor_user_id"),
            meta.get("actor_session_id"),
            business.get("userId"),
            actor_type,
        )
        component = _first_text(
            business.get("component"),
            business_metadata.get("component"),
            business_metadata.get("card"),
            business_metadata.get("cardName"),
            top_detail.get("component"),
            top_detail.get("card"),
            top_detail.get("panel_name"),
            market_overview.get("panel_name"),
            raw_response.get("component"),
            raw_response.get("card"),
        )
        route = _sanitize_url(_first_text(
            business.get("route"),
            business_metadata.get("route"),
            top_detail.get("route"),
            top_detail.get("path"),
            raw_response.get("route"),
        ))
        endpoint = _sanitize_url(_first_text(
            business.get("endpoint"),
            business_metadata.get("endpoint"),
            business_metadata.get("apiPath"),
            top_detail.get("endpoint"),
            top_detail.get("endpoint_url"),
            top_detail.get("apiPath"),
            raw_response.get("endpoint"),
            raw_response.get("endpoint_url"),
        ))
        provider = _first_text(
            business.get("provider"),
            business_metadata.get("provider"),
            top_detail.get("provider"),
            raw_response.get("provider"),
            raw_response.get("data_provider"),
            raw_response.get("source_provider"),
        )
        source = _first_text(
            business.get("source"),
            business_metadata.get("source"),
            top_detail.get("source"),
            raw_response.get("source"),
            raw_response.get("sourceLabel"),
            top_event.get("target"),
        )
        feature = _first_text(
            business.get("feature"),
            business_metadata.get("feature"),
            top_detail.get("feature"),
            market_overview.get("feature"),
            meta.get("subsystem"),
        )
        event_type = _first_text(
            business.get("eventType"),
            business.get("type"),
            top_detail.get("event_type"),
            top_detail.get("event_name"),
            top_event.get("event_name"),
        )
        first_failed_step = next((step for step in steps if step.get("status") == "failed"), {})
        request_id = _first_diagnostic_handle(
            "request",
            (business.get("requestId"), "business_event"),
            (top_detail.get("request_id"), "event_detail"),
            (top_detail.get("requestId"), "event_detail"),
            (raw_response.get("request_id"), "provider_payload"),
            (raw_response.get("requestId"), "provider_payload"),
            (meta.get("actor_request_id"), "actor_context"),
            (row.get("query_id"), "session_row"),
        )
        trace_id = _first_diagnostic_handle(
            "trace",
            (business.get("traceId"), "business_event"),
            (top_detail.get("trace_id"), "event_detail"),
            (top_detail.get("traceId"), "event_detail"),
            (raw_response.get("trace_id"), "provider_payload"),
            (raw_response.get("traceId"), "provider_payload"),
            (raw_response.get("x_trace_id"), "provider_payload"),
        )
        explicit_reason = _first_text(
            business.get("reason"),
            business_metadata.get("reason"),
            business_metadata.get("failureReason"),
            first_failed_step.get("reason") if isinstance(first_failed_step, dict) else None,
            first_failed_step.get("errorType") if isinstance(first_failed_step, dict) else None,
            top_detail.get("reason"),
            top_detail.get("error_type"),
            top_event.get("error_code"),
            raw_response.get("reason"),
            raw_response.get("error_code"),
        )
        error_summary = _masked_message(_first_text(
            business.get("errorSummary"),
            business_metadata.get("errorSummary"),
            business_metadata.get("error_message"),
            first_failed_step.get("errorMessage") if isinstance(first_failed_step, dict) else None,
            first_failed_step.get("message") if isinstance(first_failed_step, dict) else None,
            top_detail.get("error_summary"),
            top_detail.get("error_message"),
            top_detail.get("message"),
            top_event.get("message"),
            market_overview.get("error_message"),
            raw_response.get("error"),
            raw_response.get("message"),
            raw_response.get("detail"),
            summary.get("error"),
        ))
        failed = status in {"failed", "partial"}
        reason = _reason_from_failure_text(
            explicit_reason,
            error_summary,
            top_event.get("event_name"),
            top_event.get("status"),
            top_detail.get("status"),
            raw_response.get("status"),
            failed=failed,
        )
        context_label = _first_text(
            symbol,
            component,
            business.get("contextLabel"),
            business_metadata.get("contextLabel"),
            business.get("subject"),
            business.get("event"),
            row.get("name"),
            row.get("task_id"),
        )
        provider_source = provider or source
        root_cause = _first_text(
            error_summary,
            explicit_reason,
            f"{provider_source} {reason}" if provider_source and reason else None,
            reason,
        )
        return {
            "eventType": event_type,
            "actorType": actor_type or "unknown",
            "actorLabel": actor_label,
            "contextLabel": context_label,
            "route": route,
            "endpoint": endpoint,
            "provider": provider,
            "source": source,
            "component": component,
            "feature": feature,
            "reason": reason,
            "errorSummary": error_summary,
            "requestId": request_id,
            "traceId": trace_id,
            "rootCauseSummary": _masked_message(root_cause),
            "stepTraceAvailable": bool(steps),
        }

    def _load_session_details(self, rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        session_ids = [str(row.get("session_id") or "") for row in rows if isinstance(row, dict)]
        batch_loader = getattr(self.db, "list_execution_log_session_details", None)
        if callable(batch_loader):
            details = batch_loader(session_ids)
            return details if isinstance(details, dict) else {}
        return {
            session_id: self.db.get_execution_log_session_detail(session_id) or {}
            for session_id in session_ids
            if session_id
        }

    def _session_to_business_event(
        self,
        row: Dict[str, Any],
        *,
        include_steps: bool = False,
        detail: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if detail is None:
            detail = self.db.get_execution_log_session_detail(str(row.get("session_id") or "")) or {}
        summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else (row.get("summary") if isinstance(row.get("summary"), dict) else {})
        business = summary.get("business_event") if isinstance(summary.get("business_event"), dict) else {}
        meta = summary.get("meta") if isinstance(summary.get("meta"), dict) else {}
        category = _as_str(business.get("category")) or _normalize_log_category(meta.get("subsystem") or row.get("task_id"))
        operation_category, _ = self._operation_kind(summary, row.get("code"), row.get("name"), row.get("task_id"))
        if not business and category == "analysis" and operation_category != "single_stock_analysis":
            return None
        steps = self._build_business_steps_from_session(detail)
        failed_count = sum(1 for step in steps if step.get("status") == "failed")
        success_count = sum(1 for step in steps if step.get("status") == "success")
        skipped_count = sum(1 for step in steps if step.get("status") == "skipped")
        unknown_count = sum(1 for step in steps if step.get("status") == "unknown")
        record_id = _as_str(business.get("recordId")) or _as_str(row.get("analysis_history_id")) or None
        raw_status = _normalize_business_status(business.get("status") or row.get("overall_status"))
        status = raw_status
        if category == "analysis":
            inferred = self._infer_analysis_status(steps, record_id=record_id)
            status = inferred if inferred != "running" or raw_status == "running" else raw_status
            if raw_status == "success" and failed_count:
                status = "partial"
        symbol = _as_str(business.get("symbol") or row.get("code")) or None
        event_name = _as_str(business.get("event") or symbol or row.get("name") or row.get("task_id") or "系统事件")
        started_at = business.get("startedAt") or row.get("started_at")
        finished_at = business.get("finishedAt") or row.get("ended_at")
        summary_text = _as_str(business.get("summary")) or (f"用户分析 {event_name}" if category == "analysis" else event_name)
        if category == "analysis" and not business.get("summary"):
            if status == "partial":
                summary_text = f"用户分析 {event_name}，部分数据源失败"
            elif status == "failed":
                summary_text = f"用户分析 {event_name}失败"
        triage = self._business_event_triage_fields(
            row=row,
            summary=summary,
            business=business,
            detail=detail,
            status=status,
            symbol=symbol,
            steps=steps,
        )
        payload = {
            "id": _as_str(business.get("id") or row.get("session_id")),
            "event": event_name,
            "category": category,
            "type": _as_str(business.get("type")) or ("stock_analysis" if category == "analysis" else _as_str(row.get("task_id")) or category),
            "eventType": triage.get("eventType"),
            "status": status,
            "summary": summary_text,
            "subject": _as_str(business.get("subject") or symbol or event_name) or None,
            "symbol": symbol,
            "market": business.get("market"),
            "actorType": triage.get("actorType"),
            "actorLabel": triage.get("actorLabel"),
            "contextLabel": triage.get("contextLabel"),
            "route": triage.get("route"),
            "endpoint": triage.get("endpoint"),
            "provider": triage.get("provider"),
            "source": triage.get("source"),
            "component": triage.get("component"),
            "feature": triage.get("feature"),
            "reason": triage.get("reason"),
            "errorSummary": triage.get("errorSummary"),
            "traceId": triage.get("traceId"),
            "rootCauseSummary": triage.get("rootCauseSummary"),
            "stepTraceAvailable": triage.get("stepTraceAvailable"),
            "analysisType": business.get("analysisType"),
            "strategyId": business.get("strategyId"),
            "scannerId": business.get("scannerId"),
            "backtestId": business.get("backtestId"),
            "userId": business.get("userId") or meta.get("actor_user_id"),
            "requestId": triage.get("requestId"),
            "recordId": record_id,
            "startedAt": started_at,
            "finishedAt": finished_at,
            "durationMs": business.get("durationMs") if business.get("durationMs") is not None else _duration_ms(started_at, finished_at),
            "stepCount": int(business.get("stepCount") or len(steps)),
            "successStepCount": int(business.get("successStepCount") or success_count),
            "failedStepCount": int(business.get("failedStepCount") or failed_count),
            "skippedStepCount": int(business.get("skippedStepCount") or skipped_count),
            "unknownStepCount": int(business.get("unknownStepCount") or unknown_count),
            "metadata": _sanitize_metadata(business.get("metadata") if isinstance(business.get("metadata"), dict) else {}),
        }
        if include_steps:
            payload["steps"] = [
                {key: value for key, value in step.items() if key != "critical"}
                for step in steps
            ]
        return payload

    def list_business_events(
        self,
        *,
        category: Optional[str] = None,
        type: Optional[str] = None,
        subject: Optional[str] = None,
        symbol: Optional[str] = None,
        scanner_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        backtest_id: Optional[str] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        channel: Optional[str] = None,
        status: Optional[str] = None,
        query: Optional[str] = None,
        since: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        rows, _ = self.db.list_execution_log_sessions(
            stock_code=_as_str(symbol).upper() or None,
            date_from=date_from or _parse_since(since),
            date_to=date_to,
            limit=200,
            offset=0,
        )
        category_filter = _normalize_log_category(category, "") if category else None
        type_filter = _as_str(type)
        subject_filter = _as_str(subject).lower()
        scanner_filter = _as_str(scanner_id)
        strategy_filter = _as_str(strategy_id)
        backtest_filter = _as_str(backtest_id)
        request_filter = _as_str(request_id)
        user_filter = _as_str(user_id)
        provider_filter = _as_str(provider).lower()
        model_filter = _as_str(model).lower()
        channel_filter = _as_str(channel).lower()
        status_filter = _normalize_business_status(status) if status else None
        query_text = _as_str(query).lower()
        items: List[Dict[str, Any]] = []
        details_by_session = self._load_session_details(rows)
        for row in rows:
            session_id = str(row.get("session_id") or "")
            detail = details_by_session.get(session_id, {})
            event = self._session_to_business_event(row, detail=detail)
            if event is None:
                continue
            steps = self._build_business_steps_from_session(detail)
            if category_filter and event.get("category") != category_filter:
                continue
            if status_filter and event.get("status") != status_filter:
                continue
            if type_filter and event.get("type") != type_filter:
                continue
            if subject_filter and subject_filter not in _as_str(event.get("subject")).lower():
                continue
            if scanner_filter and event.get("scannerId") != scanner_filter:
                continue
            if strategy_filter and event.get("strategyId") != strategy_filter:
                continue
            if backtest_filter and event.get("backtestId") != backtest_filter:
                continue
            if request_filter and event.get("requestId") != request_filter:
                continue
            if user_filter and event.get("userId") != user_filter:
                continue
            if provider_filter and not self._business_event_matches_dimension(event, steps, provider_filter, "provider"):
                continue
            if model_filter and not self._business_event_matches_dimension(event, steps, model_filter, "model"):
                continue
            if channel_filter and not self._business_event_matches_dimension(event, steps, channel_filter, "channel"):
                continue
            if query_text:
                haystack = " ".join(
                    _as_str(event.get(key))
                    for key in (
                        "event",
                        "summary",
                        "subject",
                        "symbol",
                        "market",
                        "analysisType",
                        "type",
                        "eventType",
                        "actorType",
                        "actorLabel",
                        "contextLabel",
                        "route",
                        "endpoint",
                        "provider",
                        "source",
                        "component",
                        "feature",
                        "reason",
                        "errorSummary",
                        "requestId",
                        "traceId",
                        "recordId",
                        "scannerId",
                        "strategyId",
                        "backtestId",
                    )
                ).lower()
                if query_text not in haystack:
                    continue
            items.append(event)
        items.sort(key=lambda item: _as_str(item.get("startedAt")), reverse=True)
        total = len(items)
        self._last_business_health_summary = self.summarize_business_events(items)
        requested_limit = max(1, min(int(limit), 200))
        start = max(0, int(offset))
        return items[start:start + requested_limit], total

    @staticmethod
    def _business_event_matches_dimension(
        event: Dict[str, Any],
        steps: List[Dict[str, Any]],
        filter_text: str,
        dimension: str,
    ) -> bool:
        if not filter_text:
            return True

        def contains(value: Any) -> bool:
            return filter_text in _as_str(value).lower()

        if dimension == "provider":
            if contains(event.get("provider")) or contains(event.get("source")):
                return True
            return any(contains(step.get("provider")) for step in steps if isinstance(step, dict))
        if dimension == "model":
            if contains((event.get("metadata") or {}).get("model") if isinstance(event.get("metadata"), dict) else None):
                return True
            return any(contains(step.get("model")) for step in steps if isinstance(step, dict))
        if dimension == "channel":
            if event.get("category") == "notification" and (contains(event.get("provider")) or contains(event.get("source"))):
                return True
            return any(
                (
                    contains(step.get("provider"))
                    or contains(step.get("channel"))
                    or contains(step.get("name"))
                )
                for step in steps
                if isinstance(step, dict)
                and (
                    _as_str(step.get("category")).lower() == "notification"
                    or "notification" in _as_str(step.get("name")).lower()
                    or "send_notification" in _as_str(step.get("name")).lower()
                )
            )
        return False

    def get_business_event_detail(self, event_id: str) -> Optional[Dict[str, Any]]:
        row = self.db.get_execution_log_session_detail(event_id)
        if not row:
            return None
        return self._session_to_business_event(row, include_steps=True)

    def list_sessions(
        self,
        *,
        task_id: Optional[str] = None,
        stock_code: Optional[str] = None,
        status: Optional[str] = None,
        min_level: Optional[str] = None,
        level: Optional[str] = None,
        category: Optional[str] = None,
        query: Optional[str] = None,
        since: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        channel: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        effective_date_from = date_from or _parse_since(since)
        requested_limit = max(1, min(int(limit), 200))
        rows, total = self.db.list_execution_log_sessions(
            task_id=task_id,
            stock_code=stock_code,
            status=status,
            category=None,
            provider=provider,
            model=model,
            channel=channel,
            date_from=effective_date_from,
            date_to=date_to,
            limit=200,
            offset=0,
        )
        items: List[Dict[str, Any]] = []
        min_level_normalized = _normalize_log_level(min_level, "DEBUG") if min_level else None
        exact_level = _normalize_log_level(level, "") if level else None
        category_filter = _normalize_log_category(category, "") if category else None
        query_text = _as_str(query).lower()
        details_by_session = self._load_session_details(rows)
        for row in rows:
            row = _sanitize_metadata(row)
            summary = _sanitize_metadata(row.get("summary") if isinstance(row.get("summary"), dict) else {})
            detail = _sanitize_metadata(details_by_session.get(str(row.get("session_id") or ""), {}))
            events = detail.get("events") if isinstance(detail.get("events"), list) else []
            enriched_events = [_sanitize_metadata(self._enrich_event(event)) for event in events if isinstance(event, dict)]
            top_event = self._top_event(enriched_events)
            if min_level_normalized and not any(
                _LOG_LEVEL_RANK.get(_event_level(event), 0) >= _LOG_LEVEL_RANK[min_level_normalized]
                for event in enriched_events
            ):
                continue
            if exact_level and not any(_event_level(event) == exact_level for event in enriched_events):
                continue
            if category_filter and not any(_event_category(event) == category_filter for event in enriched_events):
                continue
            if query_text and not self._matches_query(row=row, events=enriched_events, query=query_text):
                continue

            row["readable_summary"] = self.build_readable_summary(
                overall_status=str(row.get("overall_status") or "unknown"),
                summary=summary,
                events=enriched_events,
            )
            row["readable_summary"].update(
                self._operation_summary_fields(
                    overall_status=str(row.get("overall_status") or "unknown"),
                    summary=summary,
                    code=row.get("code"),
                    name=row.get("name"),
                    task_id=row.get("task_id"),
                )
            )
            if top_event:
                row["readable_summary"].update(
                    {
                        "log_level": _event_level(top_event),
                        "log_category": _event_category(top_event),
                        "event_name": _event_name_from_event(top_event),
                        "event_message": top_event.get("message"),
                        "request_id": (top_event.get("detail") or {}).get("request_id") if isinstance(top_event.get("detail"), dict) else None,
                        "source": top_event.get("target"),
                    }
                )
            items.append(_sanitize_metadata(row))
        items.sort(
            key=lambda item: (
                str(item.get("started_at") or ""),
            ),
            reverse=True,
        )
        filtered_total = len(items)
        paged = items[max(0, int(offset)): max(0, int(offset)) + requested_limit]
        return paged, filtered_total

    @staticmethod
    def _enrich_event(event: Dict[str, Any]) -> Dict[str, Any]:
        next_event = dict(event)
        next_event["level"] = _event_level(next_event)
        next_event["category"] = _event_category(next_event)
        next_event["event_name"] = _event_name_from_event(next_event)
        return next_event

    @staticmethod
    def _top_event(events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not events:
            return None
        return sorted(
            events,
            key=lambda event: (
                _LOG_LEVEL_RANK.get(_event_level(event), 0),
                str(event.get("event_at") or ""),
                int(event.get("id") or 0),
            ),
            reverse=True,
        )[0]

    @staticmethod
    def _matches_query(*, row: Dict[str, Any], events: List[Dict[str, Any]], query: str) -> bool:
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        haystack: List[str] = [
            _as_str(row.get("task_id")),
            _as_str(row.get("code")),
            _as_str(row.get("name")),
            _as_str(row.get("session_id")),
            _as_str(summary.get("meta", {}).get("actor_username") if isinstance(summary.get("meta"), dict) else ""),
            _as_str(summary.get("meta", {}).get("actor_display") if isinstance(summary.get("meta"), dict) else ""),
            _as_str(summary.get("meta", {}).get("actor_role") if isinstance(summary.get("meta"), dict) else ""),
            _as_str(summary.get("meta", {}).get("actor_type") if isinstance(summary.get("meta"), dict) else ""),
            _as_str(summary.get("meta", {}).get("actor_session_id") if isinstance(summary.get("meta"), dict) else ""),
            _as_str(summary.get("meta", {}).get("actor_request_id") if isinstance(summary.get("meta"), dict) else ""),
        ]
        for event in events:
            detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
            haystack.extend(
                [
                    _event_name_from_event(event),
                    _as_str(event.get("message")),
                    _as_str(event.get("target")),
                    _as_str(detail.get("request_id")),
                    _as_str(detail.get("symbol")),
                    _as_str(detail.get("source")),
                    _as_str(detail.get("user")),
                ]
            )
        return query in " ".join(haystack).lower()

    @staticmethod
    def summarize_items(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        error_count = 0
        warning_count = 0
        data_source_failure_count = 0
        slow_request_count = 0
        latest_critical_at = None
        health_items: List[Dict[str, Any]] = []
        for item in items:
            readable_summary = item.get("readable_summary") if isinstance(item.get("readable_summary"), dict) else {}
            level = _normalize_log_level(readable_summary.get("log_level"), "INFO")
            category = _as_str(readable_summary.get("log_category"))
            event_name = _as_str(readable_summary.get("event_name"))
            if level in {"ERROR", "CRITICAL"}:
                error_count += 1
            if level == "WARNING":
                warning_count += 1
            if category == "data_source" and level in {"WARNING", "ERROR", "CRITICAL"}:
                data_source_failure_count += 1
            if event_name in {"SlowRequest", "MarketCacheColdStartSlow"}:
                slow_request_count += 1
            if level == "CRITICAL":
                current = _as_str(item.get("started_at"))
                if current and (latest_critical_at is None or current > latest_critical_at):
                    latest_critical_at = current
            health_items.append({
                "id": item.get("session_id"),
                "event": event_name or item.get("name") or item.get("task_id"),
                "category": category,
                "status": "failed" if level in {"ERROR", "CRITICAL"} else ("partial" if level == "WARNING" else "success"),
                "provider": readable_summary.get("provider"),
                "source": readable_summary.get("source"),
                "reason": readable_summary.get("reason") or readable_summary.get("top_failure_reason"),
                "errorSummary": readable_summary.get("error_summary") or readable_summary.get("event_message"),
                "actorType": readable_summary.get("actor_type") or readable_summary.get("actor_role"),
                "startedAt": item.get("started_at"),
                "durationMs": (item.get("summary") or {}).get("durationMs") if isinstance(item.get("summary"), dict) else None,
            })
        health_summary = ExecutionLogService.summarize_business_events(health_items)
        if latest_critical_at and not health_summary.get("latest_critical_error"):
            critical_item = next(
                (
                    health_item
                    for health_item in health_items
                    if health_item.get("status") == "failed" and health_item.get("startedAt") == latest_critical_at
                ),
                None,
            )
            if critical_item:
                health_summary["latest_critical_error"] = ExecutionLogService._top_error_payload(critical_item)
        return {
            "error_count": error_count,
            "warning_count": warning_count,
            "data_source_failure_count": data_source_failure_count,
            "slow_request_count": slow_request_count,
            "latest_critical_at": latest_critical_at,
            "health_summary": health_summary,
        }

    @staticmethod
    def summarize_business_events(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_events = len(items)
        failed_items = [item for item in items if ExecutionLogService._is_failed_business_event(item)]
        warning_items = [item for item in items if ExecutionLogService._is_warning_business_event(item)]
        slow_events = sum(1 for item in items if ExecutionLogService._is_slow_business_event(item))
        failure_rate = round(len(failed_items) / total_events, 4) if total_events else 0
        unhealthy_items = failed_items or warning_items
        status = "healthy"
        if failed_items and (failure_rate >= 0.5 or len(failed_items) >= 3):
            status = "failing"
        elif failed_items or warning_items:
            status = "degraded"
        latest_critical = next(
            (
                item
                for item in sorted(failed_items, key=lambda value: _as_str(value.get("startedAt")), reverse=True)
                if _as_str(item.get("status")).lower() in {"critical"} or _as_str(item.get("category")).lower() == "security"
            ),
            None,
        )
        return {
            "total_events": total_events,
            "failed_events": len(failed_items),
            "warning_events": len(warning_items),
            "slow_events": slow_events,
            "failure_rate": failure_rate,
            "status": status,
            "failures_by_category": ExecutionLogService._health_buckets(unhealthy_items, ["category", "feature"]),
            "failures_by_provider": ExecutionLogService._health_buckets(failed_items, ["provider", "source"]),
            "failures_by_reason": ExecutionLogService._health_buckets(unhealthy_items, ["reason"]),
            "top_recent_errors": [
                ExecutionLogService._top_error_payload(item)
                for item in sorted(unhealthy_items, key=lambda value: _as_str(value.get("startedAt")), reverse=True)[:5]
            ],
            "actor_breakdown": ExecutionLogService._health_buckets(items, ["actorType"]),
            "latest_critical_error": ExecutionLogService._top_error_payload(latest_critical) if latest_critical else None,
        }

    @staticmethod
    def _is_failed_business_event(item: Dict[str, Any]) -> bool:
        status = _as_str(item.get("status")).lower()
        return status in {"failed", "error", "critical"}

    @staticmethod
    def _is_warning_business_event(item: Dict[str, Any]) -> bool:
        status = _as_str(item.get("status")).lower()
        return status in {"partial", "warning", "timeout", "timed_out", "timeout_unknown"}

    @staticmethod
    def _is_slow_business_event(item: Dict[str, Any]) -> bool:
        event_type = _as_str(item.get("eventType") or item.get("event")).lower()
        if "slow" in event_type:
            return True
        try:
            return float(item.get("durationMs") or 0) >= 5000
        except Exception:
            return False

    @staticmethod
    def _health_buckets(items: List[Dict[str, Any]], keys: List[str], *, limit: int = 5) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}
        labels: Dict[str, str] = {}
        for item in items:
            value = None
            for key in keys:
                value = _as_str(item.get(key))
                if value:
                    break
            if not value:
                value = "unknown"
            bucket_key = value.lower()
            counts[bucket_key] = counts.get(bucket_key, 0) + 1
            labels.setdefault(bucket_key, _masked_message(value) or bucket_key)
        return [
            {"key": key, "label": labels.get(key) or key, "count": count}
            for key, count in sorted(counts.items(), key=lambda entry: (-entry[1], entry[0]))[:limit]
        ]

    @staticmethod
    def _top_error_payload(item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not item:
            return None
        return {
            "id": _as_str(item.get("id")),
            "event": _masked_message(_as_str(item.get("event"))) or None,
            "category": _masked_message(_as_str(item.get("category"))) or None,
            "provider": _masked_message(_as_str(item.get("provider"))) or None,
            "source": _masked_message(_as_str(item.get("source"))) or None,
            "reason": _masked_message(_as_str(item.get("reason"))) or None,
            "errorSummary": _masked_message(_as_str(item.get("errorSummary") or item.get("rootCauseSummary") or item.get("summary"))) or None,
            "startedAt": _as_str(item.get("startedAt")) or None,
            "status": _as_str(item.get("status")) or None,
        }

    def get_session_detail(self, session_id: str) -> Optional[Dict[str, Any]]:
        detail = self.db.get_execution_log_session_detail(session_id)
        if not detail:
            return None
        summary = _sanitize_metadata(detail.get("summary") if isinstance(detail.get("summary"), dict) else {})
        events = detail.get("events") if isinstance(detail.get("events"), list) else []
        enriched_events: List[Dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            event = self._enrich_event(_sanitize_metadata(event))
            detail_block = event.get("detail") if isinstance(event.get("detail"), dict) else {}
            category = _as_str(detail_block.get("category")) or _as_str(event.get("phase")) or "system"
            action = _as_str(detail_block.get("action")) or _action_from_status(event.get("status"))
            outcome = _as_str(detail_block.get("outcome")) or _outcome_from_status(event.get("status"))
            reason = _masked_message(_as_str(detail_block.get("reason")))
            next_event = _sanitize_metadata(dict(event))
            next_event["category"] = _normalize_log_category(category)
            next_event["action"] = action
            next_event["outcome"] = outcome
            next_event["reason"] = reason
            enriched_events.append(next_event)

        readable = self.build_readable_summary(
            overall_status=str(detail.get("overall_status") or "unknown"),
            summary=summary,
            events=enriched_events,
        )
        readable.update(
            self._operation_summary_fields(
                overall_status=str(detail.get("overall_status") or "unknown"),
                summary=summary,
                code=detail.get("code"),
                name=detail.get("name"),
                task_id=detail.get("task_id"),
            )
        )
        detail = _sanitize_metadata(detail)
        detail["summary"] = summary
        detail["readable_summary"] = _sanitize_metadata(readable)
        detail["events"] = enriched_events
        detail["operation_detail"] = _sanitize_metadata(self._build_operation_detail(
            session=detail,
            summary=summary,
            events=enriched_events,
            readable=readable,
        ))
        return detail
