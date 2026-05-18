# -*- coding: utf-8 -*-
"""Retention and storage-health helpers for the Admin Logs center."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, delete, func, select, text

from src.config import get_config
from src.postgres_control_plane_store import PhaseGExecutionEvent, PhaseGExecutionSession
from src.services.notification_service import NotificationService
from src.storage import ExecutionLogEvent, ExecutionLogSession, get_db
from src.utils.security import sanitize_message, sanitize_metadata

logger = logging.getLogger(__name__)

_MISSING_DOMAIN_BY_STEP = {
    "fetch_quote": "quote",
    "fetch_history": "history",
    "fetch_technical": "technical",
    "fetch_fundamentals": "fundamentals",
    "fetch_financials": "financials",
    "fetch_news": "news",
    "fetch_market_context": "market_context",
    "load_market_data": "market_data",
    "load_factor_data": "factor_data",
}
_DATA_RELEVANT_PHASE_PREFIXES = ("data_", "market")
_DATA_RELEVANT_CATEGORIES = {"data_source", "market", "analysis", "scanner"}
_DEGRADED_STATUSES = {"partial", "partial_success", "failed", "error", "timeout", "timed_out", "timeout_unknown", "switched_to_fallback"}
_FRESHNESS_SYNONYMS = {
    "fresh": "fresh",
    "live": "fresh",
    "current": "fresh",
    "stale": "stale",
    "stale_refreshing": "stale",
    "stale_or_fallback": "stale",
    "degraded": "degraded",
    "partial": "partial",
    "missing": "missing",
    "fallback": "fallback",
    "unknown": "unknown",
}
_SURFACE_ALIASES = {
    "market_overview": "market_overview",
    "marketoverview": "market_overview",
    "analysis": "analysis",
    "scanner": "scanner",
    "backtest": "backtest",
    "portfolio": "portfolio",
    "watchlist": "watchlist",
    "market": "market",
    "notification": "notification",
    "notifications": "notification",
    "admin_logs": "admin_logs",
}


class AdminDataMissingDrilldownService:
    """Read-only aggregation for missing or degraded data observability."""

    def __init__(self) -> None:
        self.db = get_db()

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _normalize_token(cls, value: Any) -> str:
        text_value = cls._text(value).lower().replace("-", "_").replace(".", "_").replace(" ", "_")
        return re.sub(r"[^a-z0-9_:/]+", "_", text_value).strip("_")

    @classmethod
    def _parse_since(cls, value: Optional[str]) -> Optional[datetime]:
        text_value = cls._text(value).lower()
        if not text_value:
            return None
        try:
            if text_value.endswith("m") and text_value[:-1].isdigit():
                return datetime.now() - timedelta(minutes=int(text_value[:-1]))
            if text_value.endswith("h") and text_value[:-1].isdigit():
                return datetime.now() - timedelta(hours=int(text_value[:-1]))
            if text_value.endswith("d") and text_value[:-1].isdigit():
                return datetime.now() - timedelta(days=int(text_value[:-1]))
            return datetime.fromisoformat(text_value.replace("z", "+00:00"))
        except Exception:
            return None

    @classmethod
    def _parse_iso(cls, value: Any) -> Optional[datetime]:
        text_value = cls._text(value)
        if not text_value:
            return None
        try:
            return datetime.fromisoformat(text_value.replace("Z", "+00:00"))
        except Exception:
            return None

    @classmethod
    def _normalize_surface(cls, value: Any) -> str:
        token = cls._normalize_token(value)
        if "market_overview" in token:
            return "market_overview"
        for raw, normalized in _SURFACE_ALIASES.items():
            if token == raw or token.startswith(f"{raw}_"):
                return normalized
        return token or "system"

    @classmethod
    def _affected_surface(cls, *, summary: Dict[str, Any], detail: Dict[str, Any], event_detail: Dict[str, Any]) -> str:
        business = summary.get("business_event") if isinstance(summary.get("business_event"), dict) else {}
        meta = summary.get("meta") if isinstance(summary.get("meta"), dict) else {}
        candidates = (
            business.get("feature"),
            business.get("component"),
            business.get("category"),
            event_detail.get("surface"),
            event_detail.get("feature"),
            event_detail.get("component"),
            event_detail.get("route_family"),
            meta.get("subsystem"),
            detail.get("name"),
        )
        for candidate in candidates:
            surface = cls._normalize_surface(candidate)
            if surface != "system":
                return surface
        return "system"

    @classmethod
    def _normalize_reason_code(cls, event: Dict[str, Any], detail: Dict[str, Any]) -> str:
        candidates = (
            event.get("error_code"),
            detail.get("reason_code"),
            detail.get("reason"),
            detail.get("error_code"),
            detail.get("event_name"),
        )
        for candidate in candidates:
            token = cls._normalize_token(candidate)
            if token and re.fullmatch(r"[a-z0-9_:/]{2,64}", token):
                return token
        text_blob = " ".join(cls._text(value).lower() for value in candidates if cls._text(value))
        if "missing api key" in text_blob or "missing_api_key" in text_blob:
            return "missing_api_key"
        if "empty result" in text_blob or "empty_result" in text_blob or "no data" in text_blob:
            return "empty_result"
        if "insufficient" in text_blob:
            return "insufficient_fields"
        if "timeout" in text_blob:
            return "timeout"
        if "fallback" in text_blob:
            return "fallback"
        if "stale" in text_blob:
            return "stale"
        return "unknown"

    @classmethod
    def _infer_missing_domain(cls, event: Dict[str, Any], detail: Dict[str, Any]) -> Optional[str]:
        direct_candidates = (
            detail.get("missing_domain"),
            detail.get("data_domain"),
            detail.get("domain"),
            detail.get("source_domain"),
        )
        for candidate in direct_candidates:
            token = cls._normalize_token(candidate)
            if token:
                return token
        step = cls._normalize_token(event.get("step"))
        if step in _MISSING_DOMAIN_BY_STEP:
            return _MISSING_DOMAIN_BY_STEP[step]
        phase = cls._normalize_token(event.get("phase"))
        if phase.startswith("data_"):
            phase_domain = phase[5:]
            if phase_domain:
                return phase_domain
        text_blob = " ".join(
            cls._text(value).lower()
            for value in (
                detail.get("event_name"),
                event.get("step"),
                event.get("phase"),
                event.get("target"),
                detail.get("reason"),
            )
            if cls._text(value)
        )
        for keyword, domain in (
            ("quote", "quote"),
            ("history", "history"),
            ("technical", "technical"),
            ("fundamental", "fundamentals"),
            ("financial", "financials"),
            ("news", "news"),
            ("market context", "market_context"),
        ):
            if keyword in text_blob:
                return domain
        return None

    @classmethod
    def _freshness_status(cls, event: Dict[str, Any], detail: Dict[str, Any], reason_code: str) -> str:
        candidates = (
            detail.get("freshness_status"),
            detail.get("freshness_state"),
            detail.get("freshness"),
            detail.get("cache_state"),
        )
        for candidate in candidates:
            token = cls._normalize_token(candidate)
            normalized = _FRESHNESS_SYNONYMS.get(token)
            if normalized:
                return normalized
        if cls._flag_value(detail, "stale", "is_stale"):
            return "stale"
        if cls._flag_value(detail, "fallback_used", "fallbackUse", "fallbackUsed", "isFallback", "is_fallback"):
            return "fallback"
        if reason_code in {"missing_api_key", "empty_result", "insufficient_fields"}:
            return "missing"
        if reason_code in {"stale", "stale_quote_served"}:
            return "stale"
        if cls._normalize_token(event.get("status")) in {"partial", "partial_success"}:
            return "partial"
        return "unknown"

    @classmethod
    def _flag_value(cls, payload: Dict[str, Any], *keys: str) -> bool:
        for key in keys:
            if key in payload:
                return bool(payload.get(key))
        return False

    @classmethod
    def _is_data_relevant(cls, event: Dict[str, Any], detail: Dict[str, Any], domain: Optional[str], reason_code: str, freshness_status: str) -> bool:
        phase = cls._normalize_token(event.get("phase"))
        category = cls._normalize_token(detail.get("category"))
        step = cls._normalize_token(event.get("step"))
        event_name = cls._normalize_token(detail.get("event_name"))
        status = cls._normalize_token(event.get("status"))
        text_blob = " ".join(part for part in (phase, category, step, event_name, reason_code, freshness_status, domain or "") if part)
        phase_related = any(phase.startswith(prefix) for prefix in _DATA_RELEVANT_PHASE_PREFIXES)
        category_related = category in _DATA_RELEVANT_CATEGORIES
        step_related = step in _MISSING_DOMAIN_BY_STEP
        keyword_related = any(keyword in text_blob for keyword in ("quote", "history", "technical", "news", "fundamental", "financial", "freshness", "stale", "fallback", "missing"))
        degraded = status in _DEGRADED_STATUSES or freshness_status not in {"fresh", "unknown"} or reason_code != "unknown"
        return degraded and (phase_related or category_related or step_related or keyword_related or domain is not None)

    @classmethod
    def _provider_source(cls, *, summary: Dict[str, Any], detail: Dict[str, Any], event: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        business = summary.get("business_event") if isinstance(summary.get("business_event"), dict) else {}
        provider = detail.get("provider") or detail.get("data_provider") or business.get("provider")
        source = detail.get("source") or detail.get("source_label") or business.get("source")
        sanitized_provider = sanitize_message(cls._text(provider))[:160] if cls._text(provider) else None
        sanitized_source = sanitize_message(cls._text(source))[:200] if cls._text(source) else None
        return sanitized_provider or None, sanitized_source or None

    def list_items(
        self,
        *,
        since: Optional[str] = "24h",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        effective_date_from = date_from or self._parse_since(since)
        session_limit = max(200, min(max(int(limit), 1) * 5, 1000))
        rows, _ = self.db.list_execution_log_sessions(
            task_id=None,
            stock_code=None,
            status=None,
            category=None,
            provider=None,
            model=None,
            channel=None,
            date_from=effective_date_from,
            date_to=date_to,
            limit=session_limit,
            offset=0,
        )
        session_ids = [self._text(row.get("session_id")) for row in rows if isinstance(row, dict) and self._text(row.get("session_id"))]
        if not session_ids:
            return {"total": 0, "items": []}
        detail_map = self.db.list_execution_log_session_details(session_ids)
        aggregates: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        for session_id in session_ids:
            session_detail = sanitize_metadata(detail_map.get(session_id) or {})
            summary = session_detail.get("summary") if isinstance(session_detail.get("summary"), dict) else {}
            business = summary.get("business_event") if isinstance(summary.get("business_event"), dict) else {}
            events = session_detail.get("events") if isinstance(session_detail.get("events"), list) else []
            for event in events:
                if not isinstance(event, dict):
                    continue
                safe_event = sanitize_metadata(event)
                event_detail = safe_event.get("detail") if isinstance(safe_event.get("detail"), dict) else {}
                reason_code = self._normalize_reason_code(safe_event, event_detail)
                domain = self._infer_missing_domain(safe_event, event_detail)
                freshness_status = self._freshness_status(safe_event, event_detail, reason_code)
                if not self._is_data_relevant(safe_event, event_detail, domain, reason_code, freshness_status):
                    continue
                affected_surface = self._affected_surface(summary=summary, detail=session_detail, event_detail=event_detail)
                provider, source = self._provider_source(summary=summary, detail=event_detail, event=safe_event)
                fallback_used = self._flag_value(event_detail, "fallback_used", "fallbackUsed", "isFallback", "is_fallback") or self._normalize_token(safe_event.get("status")) == "switched_to_fallback"
                stale = freshness_status == "stale" or self._flag_value(event_detail, "stale", "is_stale")
                partial = self._normalize_token(safe_event.get("status")) in {"partial", "partial_success", "timeout", "timed_out", "timeout_unknown", "switched_to_fallback"}
                event_time = self._parse_iso(safe_event.get("event_at"))
                event_time_text = event_time.isoformat() if event_time else self._text(safe_event.get("event_at")) or None
                symbol = self._text(business.get("symbol")) or self._text(session_detail.get("code")) or None
                market = self._text(business.get("market")) or None
                key = (
                    affected_surface,
                    domain or "unknown",
                    provider,
                    source,
                    freshness_status,
                    fallback_used,
                    stale,
                    partial,
                    reason_code,
                )
                bucket = aggregates.setdefault(
                    key,
                    {
                        "affected_surface": affected_surface,
                        "missing_domain": domain or "unknown",
                        "provider": provider,
                        "source": source,
                        "freshness_status": freshness_status,
                        "fallback_used": fallback_used,
                        "stale": stale,
                        "partial": partial,
                        "reason_code": reason_code,
                        "latest_seen_at": event_time_text,
                        "count": 0,
                        "sample_events": [],
                        "sample_sessions": [],
                        "sample_business_events": [],
                        "symbols": set(),
                        "markets": set(),
                    },
                )
                bucket["count"] += 1
                if symbol:
                    bucket["symbols"].add(symbol)
                if market:
                    bucket["markets"].add(market)
                if event_time_text and (not bucket["latest_seen_at"] or event_time_text > bucket["latest_seen_at"]):
                    bucket["latest_seen_at"] = event_time_text
                event_id = self._text(safe_event.get("id"))
                if event_id:
                    bucket["sample_events"].append((event_time or datetime.min, event_id))
                if session_id:
                    bucket["sample_sessions"].append((event_time or datetime.min, session_id))
                business_id = self._text(business.get("id")) or session_id
                if business_id:
                    bucket["sample_business_events"].append((event_time or datetime.min, business_id))

        items: List[Dict[str, Any]] = []
        for bucket in aggregates.values():
            sample_ids = [
                event_id
                for _, event_id in sorted(bucket["sample_events"], key=lambda entry: (entry[0], entry[1]))[:5]
            ]
            sample_session_ids = [
                sample_session_id
                for _, sample_session_id in sorted(bucket["sample_sessions"], key=lambda entry: (entry[0], entry[1]))[:5]
            ]
            sample_business_event_ids = [
                business_event_id
                for _, business_event_id in sorted(bucket["sample_business_events"], key=lambda entry: (entry[0], entry[1]))[:5]
            ]
            symbols = sorted(bucket["symbols"])
            markets = sorted(bucket["markets"])
            items.append(
                {
                    "affected_surface": bucket["affected_surface"],
                    "symbol": symbols[0] if len(symbols) == 1 else None,
                    "market": markets[0] if len(markets) == 1 else None,
                    "missing_domain": bucket["missing_domain"],
                    "provider": bucket["provider"],
                    "source": bucket["source"],
                    "freshness_status": bucket["freshness_status"],
                    "fallback_used": bool(bucket["fallback_used"]),
                    "stale": bool(bucket["stale"]),
                    "partial": bool(bucket["partial"]),
                    "reason_code": bucket["reason_code"],
                    "latest_seen_at": bucket["latest_seen_at"],
                    "count": int(bucket["count"]),
                    "sample_event_ids": sample_ids,
                    "sample_session_ids": sample_session_ids,
                    "sample_business_event_ids": sample_business_event_ids,
                }
            )
        items.sort(key=lambda item: ((-(int(item.get("count") or 0))), str(item.get("latest_seen_at") or ""), str(item.get("affected_surface") or ""), str(item.get("missing_domain") or "")), reverse=False)
        trimmed = items[: max(1, min(int(limit), 200))]
        return {
            "total": len(items),
            "items": trimmed,
        }


@dataclass(frozen=True)
class AdminLogRetentionPolicy:
    retention_days: int = 90
    min_retention_days: int = 7
    storage_soft_limit_bytes: int = 512 * 1024 * 1024
    storage_hard_limit_bytes: int = 1024 * 1024 * 1024
    cleanup_batch_size: int = 1000
    auto_cleanup_enabled: bool = True
    warning_threshold_count: int = 50_000
    critical_threshold_count: int = 100_000
    warning_threshold_storage_bytes: Optional[int] = None
    config_warnings: List[str] = field(default_factory=list)


class AdminLogsRetentionService:
    """Summarize and clean existing execution-log tables."""

    _last_auto_cleanup_at: Optional[datetime] = None
    _auto_cleanup_min_interval = timedelta(minutes=5)

    def __init__(self) -> None:
        self.db = get_db()

    @staticmethod
    def _emit_notification_event(**kwargs: Any) -> None:
        try:
            NotificationService().emit_event(**kwargs)
        except Exception as exc:
            logger.warning("admin logs notification event emit failed: %s", exc)

    @staticmethod
    def _policy() -> AdminLogRetentionPolicy:
        config = get_config()
        config_warnings: List[str] = []
        retention_days = max(1, int(getattr(config, "admin_logs_retention_days", 90) or 90))
        min_retention_days = max(0, int(getattr(config, "admin_logs_min_retention_days", 7) or 0))
        if min_retention_days > retention_days:
            min_retention_days = retention_days
            config_warnings.append("min_retention_days_clamped_to_retention_days")
        storage_soft_limit_bytes = max(
            1,
            int(getattr(config, "admin_logs_storage_soft_limit_mb", 512) or 512) * 1024 * 1024,
        )
        storage_hard_limit_bytes = max(
            1,
            int(getattr(config, "admin_logs_storage_hard_limit_mb", 1024) or 1024) * 1024 * 1024,
        )
        if storage_hard_limit_bytes <= storage_soft_limit_bytes:
            storage_hard_limit_bytes = storage_soft_limit_bytes * 2
            config_warnings.append("hard_limit_adjusted_above_soft_limit")
        cleanup_batch_size = max(1, min(int(getattr(config, "admin_logs_cleanup_batch_size", 1000) or 1000), 5000))
        return AdminLogRetentionPolicy(
            retention_days=retention_days,
            min_retention_days=min_retention_days,
            storage_soft_limit_bytes=storage_soft_limit_bytes,
            storage_hard_limit_bytes=storage_hard_limit_bytes,
            cleanup_batch_size=cleanup_batch_size,
            auto_cleanup_enabled=bool(getattr(config, "admin_logs_auto_cleanup_enabled", True)),
            warning_threshold_count=max(1, int(getattr(config, "admin_logs_warning_threshold_count", 50_000) or 50_000)),
            critical_threshold_count=max(1, int(getattr(config, "admin_logs_critical_threshold_count", 100_000) or 100_000)),
            warning_threshold_storage_bytes=getattr(config, "admin_logs_warning_threshold_storage_bytes", None),
            config_warnings=config_warnings,
        )

    @staticmethod
    def _iso(value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @staticmethod
    def _parse_cutoff(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        text_value = str(value).strip()
        if not text_value:
            return None
        try:
            return datetime.fromisoformat(text_value.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception as exc:
            raise ValueError(f"Invalid cleanup cutoff datetime: {value}") from exc

    def _storage_relation_scope(self) -> tuple[Optional[Any], Optional[str], Optional[str]]:
        phase_g_store = getattr(self.db, "_phase_g_store", None)
        phase_g_engine = getattr(phase_g_store, "_engine", None) if phase_g_store is not None else None
        if phase_g_engine is not None and getattr(phase_g_engine.dialect, "name", "") == "postgresql":
            return (
                phase_g_engine,
                PhaseGExecutionSession.__tablename__,
                PhaseGExecutionEvent.__tablename__,
            )

        engine = getattr(self.db, "_engine", None)
        if engine is not None and getattr(engine.dialect, "name", "") == "postgresql":
            return (
                engine,
                ExecutionLogSession.__tablename__,
                ExecutionLogEvent.__tablename__,
            )

        return None, None, None

    def _storage_measurement(self) -> Dict[str, Any]:
        engine, session_table, event_table = self._storage_relation_scope()
        if engine is not None and session_table and event_table:
            try:
                with engine.connect() as conn:
                    value = conn.execute(
                        text(
                            "SELECT "
                            "COALESCE(pg_total_relation_size(COALESCE(to_regclass(:session_table), to_regclass('public.' || :session_table))), 0) + "
                            "COALESCE(pg_total_relation_size(COALESCE(to_regclass(:event_table), to_regclass('public.' || :event_table))), 0)"
                        ),
                        {
                            "session_table": session_table,
                            "event_table": event_table,
                        },
                    ).scalar()
                return {
                    "size_bytes": int(value) if value is not None else None,
                    "measurement_scope": "postgres_tables",
                    "measurement_status": "available",
                    "measurement_reason": None,
                }
            except PermissionError:
                logger.warning("admin log PostgreSQL storage size lookup failed: permission denied")
                return {
                    "size_bytes": None,
                    "measurement_scope": "unavailable",
                    "measurement_status": "unavailable",
                    "measurement_reason": "permission denied",
                }
            except Exception as exc:
                logger.warning("admin log PostgreSQL storage size lookup failed: %s", exc)
                return {
                    "size_bytes": None,
                    "measurement_scope": "unavailable",
                    "measurement_status": "unavailable",
                    "measurement_reason": str(exc)[:160] or "postgres size lookup failed",
                }

        sqlite_engine = getattr(self.db, "_engine", None)
        if sqlite_engine is None:
            return {
                "size_bytes": None,
                "measurement_scope": "unavailable",
                "measurement_status": "unavailable",
                "measurement_reason": "database engine unavailable",
            }
        dialect = getattr(sqlite_engine.dialect, "name", "")
        if dialect != "sqlite":
            return {
                "size_bytes": None,
                "measurement_scope": "unavailable",
                "measurement_status": "unavailable",
                "measurement_reason": f"unsupported dialect: {dialect or 'unknown'}",
            }
        db_path = getattr(getattr(sqlite_engine, "url", None), "database", None)
        if not db_path or str(db_path) == ":memory:":
            return {
                "size_bytes": None,
                "measurement_scope": "unavailable",
                "measurement_status": "unavailable",
                "measurement_reason": "database path unavailable",
            }
        try:
            if not os.path.exists(str(db_path)):
                return {
                    "size_bytes": None,
                    "measurement_scope": "unavailable",
                    "measurement_status": "unavailable",
                    "measurement_reason": "database path unavailable",
                }
            return {
                "size_bytes": int(os.path.getsize(str(db_path))),
                "measurement_scope": "sqlite_database_file",
                "measurement_status": "available",
                "measurement_reason": None,
            }
        except PermissionError:
            return {
                "size_bytes": None,
                "measurement_scope": "unavailable",
                "measurement_status": "unavailable",
                "measurement_reason": "permission denied",
            }
        except Exception as exc:
            return {
                "size_bytes": None,
                "measurement_scope": "unavailable",
                "measurement_status": "unavailable",
                "measurement_reason": str(exc)[:160] or "sqlite file size lookup failed",
            }

    def _storage_bytes(self) -> Optional[int]:
        value = self._storage_measurement().get("size_bytes")
        return int(value) if value is not None else None

    @staticmethod
    def _format_bytes(value: Optional[int]) -> Optional[str]:
        if value is None:
            return None
        amount = float(value)
        for suffix in ("B", "KB", "MB", "GB", "TB"):
            if amount < 1024 or suffix == "TB":
                if suffix == "B":
                    return f"{int(amount)} B"
                return f"{amount:.1f} {suffix}"
            amount /= 1024
        return f"{int(value)} B"

    @staticmethod
    def _percentage(numerator: Optional[int], denominator: int) -> Optional[float]:
        if numerator is None or denominator <= 0:
            return None
        return round((float(numerator) / float(denominator)) * 100, 2)

    @staticmethod
    def _retention_tiers(policy: AdminLogRetentionPolicy) -> Dict[str, Any]:
        return {
            "admin_logs_standard": {
                "domain": "admin_logs",
                "retention_days": policy.retention_days,
                "cleanup_mode": "preview_first_retention_cleanup",
                "preview_required": True,
                "delete_requires_explicit_cleanup": True,
            },
            "admin_logs_minimum_protected": {
                "domain": "admin_logs",
                "retention_days": policy.min_retention_days,
                "cleanup_mode": "capacity_cleanup_floor",
                "preview_required": True,
                "delete_requires_explicit_cleanup": True,
            },
            "admin_logs_storage_pressure": {
                "domain": "admin_logs",
                "retention_days": policy.min_retention_days,
                "cleanup_mode": "capacity_cleanup",
                "preview_required": True,
                "delete_requires_explicit_cleanup": True,
                "soft_limit_bytes": policy.storage_soft_limit_bytes,
                "hard_limit_bytes": policy.storage_hard_limit_bytes,
            },
        }

    def _capacity_candidates(
        self,
        *,
        session,
        cutoff: datetime,
        batch_size: int,
    ) -> Dict[str, Any]:
        where_clause = ExecutionLogSession.started_at < cutoff
        session_ids = session.execute(
            select(ExecutionLogSession.session_id)
            .where(where_clause)
            .order_by(ExecutionLogSession.started_at.asc())
            .limit(batch_size)
        ).scalars().all()
        matched_log_count = int(session.execute(select(func.count(ExecutionLogSession.id)).where(where_clause)).scalar() or 0)
        matched_event_count = int(
            session.execute(select(func.count(ExecutionLogEvent.id)).where(ExecutionLogEvent.session_id.in_(session_ids))).scalar()
            if session_ids
            else 0
        )
        return {
            "session_ids": session_ids,
            "matched_log_count": matched_log_count,
            "matched_event_count": matched_event_count,
        }

    def capacity_cleanup_plan(self) -> Dict[str, Any]:
        policy = self._policy()
        now = datetime.now()
        min_retention_cutoff = now - timedelta(days=policy.min_retention_days)
        measurement = self._storage_measurement()
        storage_bytes = measurement.get("size_bytes")
        storage_available = storage_bytes is not None
        hard_limit_exceeded = bool(storage_available and storage_bytes >= policy.storage_hard_limit_bytes)
        with self.db.get_session() as session:
            total_logs = int(session.execute(select(func.count(ExecutionLogSession.id))).scalar() or 0)
            total_events = int(session.execute(select(func.count(ExecutionLogEvent.id))).scalar() or 0)
            candidates = self._capacity_candidates(
                session=session,
                cutoff=min_retention_cutoff,
                batch_size=policy.cleanup_batch_size,
            )
        cleanup_safe = storage_available and candidates["matched_log_count"] > 0
        reason = None
        if not storage_available:
            reason = "storage_size_unavailable"
        elif candidates["matched_log_count"] <= 0:
            reason = "no_logs_older_than_minimum_retention"
        elif not hard_limit_exceeded:
            reason = "hard_limit_not_exceeded"
        estimated_bytes_per_session = int(storage_bytes / total_logs) if storage_available and storage_bytes and total_logs > 0 else None
        estimated_reclaimable_bytes = (
            estimated_bytes_per_session * candidates["matched_log_count"]
            if estimated_bytes_per_session is not None
            else None
        )
        return {
            "mode": "capacity",
            "current_storage_bytes": storage_bytes,
            "target_storage_bytes": policy.storage_soft_limit_bytes,
            "soft_limit_bytes": policy.storage_soft_limit_bytes,
            "hard_limit_bytes": policy.storage_hard_limit_bytes,
            "hard_limit_exceeded": hard_limit_exceeded,
            "oldest_deletable_cutoff": self._iso(min_retention_cutoff),
            "estimated_candidate_sessions": candidates["matched_log_count"],
            "estimated_candidate_events": candidates["matched_event_count"],
            "cleanup_safe": cleanup_safe,
            "reason": reason,
            "storage_size_available": storage_available,
            "measurement_scope": measurement.get("measurement_scope"),
            "measurement_status": measurement.get("measurement_status"),
            "measurement_reason": measurement.get("measurement_reason"),
            "estimated_bytes_per_session": estimated_bytes_per_session,
            "estimated_reclaimable_bytes": estimated_reclaimable_bytes,
            "batch_size": policy.cleanup_batch_size,
        }

    def storage_summary(self) -> Dict[str, Any]:
        policy = self._policy()
        now = datetime.now()
        retention_cutoff = now - timedelta(days=policy.retention_days)
        with self.db.get_session() as session:
            total_logs = int(session.execute(select(func.count(ExecutionLogSession.id))).scalar() or 0)
            total_events = int(session.execute(select(func.count(ExecutionLogEvent.id))).scalar() or 0)
            oldest = session.execute(select(func.min(ExecutionLogSession.started_at))).scalar()
            newest = session.execute(select(func.max(ExecutionLogSession.started_at))).scalar()
            older_than_retention = int(
                session.execute(
                    select(func.count(ExecutionLogSession.id)).where(ExecutionLogSession.started_at < retention_cutoff)
                ).scalar()
                or 0
            )
        measurement = self._storage_measurement()
        storage_bytes = measurement.get("size_bytes")
        storage_available = storage_bytes is not None
        used_soft_pct = self._percentage(storage_bytes, policy.storage_soft_limit_bytes)
        used_hard_pct = self._percentage(storage_bytes, policy.storage_hard_limit_bytes)
        status = "ok"
        reasons = list(policy.config_warnings)
        if total_logs >= policy.critical_threshold_count:
            status = "critical"
            reasons.append("log_count_critical")
        elif total_logs >= policy.warning_threshold_count:
            status = "warning"
            reasons.append("log_count_warning")
        if older_than_retention > 0 and status == "ok":
            status = "warning"
        if older_than_retention > 0:
            reasons.append("older_than_retention")
        if storage_bytes is not None and storage_bytes >= policy.storage_hard_limit_bytes:
            status = "critical"
            reasons.append("storage_hard_limit_exceeded")
        elif storage_bytes is not None and storage_bytes >= policy.storage_soft_limit_bytes:
            status = "warning" if status == "ok" else status
            reasons.append("storage_soft_limit_exceeded")
        elif (
            storage_bytes is not None
            and policy.warning_threshold_storage_bytes is not None
            and storage_bytes >= policy.warning_threshold_storage_bytes
        ):
            status = "warning" if status == "ok" else status
            reasons.append("storage_warning")
        capacity_cleanup_recommended = bool(storage_bytes is not None and storage_bytes >= policy.storage_soft_limit_bytes)
        if status == "critical" and "storage_hard_limit_exceeded" in reasons:
            recommended = "Storage is over the hard limit. Run capacity cleanup; oldest eligible logs are protected by minimum retention."
        elif capacity_cleanup_recommended:
            recommended = "Storage is over the soft limit. Preview retention cleanup or capacity cleanup."
        elif older_than_retention > 0 or status in {"warning", "critical"}:
            recommended = "Preview cleanup, then delete logs older than retention."
        elif storage_bytes is None:
            recommended = "Storage size unavailable; retention and row-count checks are active."
        else:
            recommended = "No cleanup needed."
        capacity_plan = self.capacity_cleanup_plan()
        auto_cleanup_performed = False
        auto_cleanup_message = None
        auto_cleanup_recent = (
            self.__class__._last_auto_cleanup_at is not None
            and now - self.__class__._last_auto_cleanup_at < self.__class__._auto_cleanup_min_interval
        )
        cleanup_failed_message = None
        if (
            policy.auto_cleanup_enabled
            and storage_bytes is not None
            and storage_bytes >= policy.storage_hard_limit_bytes
            and capacity_plan["estimated_candidate_sessions"] > 0
            and not auto_cleanup_recent
        ):
            try:
                cleanup_result = self.cleanup(mode="capacity", dry_run=False, batch_size=policy.cleanup_batch_size)
                auto_cleanup_performed = cleanup_result["deleted_log_count"] > 0
                if auto_cleanup_performed:
                    self.__class__._last_auto_cleanup_at = now
                auto_cleanup_message = cleanup_result.get("message")
            except ValueError as exc:
                auto_cleanup_message = str(exc)
                cleanup_failed_message = str(exc)
        elif auto_cleanup_recent:
            auto_cleanup_message = "Automatic cleanup was recently attempted; waiting before the next batch."
        summary = {
            "total_log_count": total_logs,
            "session_count": total_logs,
            "total_event_count": total_events,
            "event_count": total_events,
            "oldest_log_timestamp": self._iso(oldest),
            "oldest_event_at": self._iso(oldest),
            "newest_log_timestamp": self._iso(newest),
            "newest_event_at": self._iso(newest),
            "retention_days": policy.retention_days,
            "minimum_retention_days": policy.min_retention_days,
            "retention_tiers": self._retention_tiers(policy),
            "retention_cutoff": self._iso(retention_cutoff),
            "logs_older_than_retention_count": older_than_retention,
            "estimated_storage_bytes": storage_bytes,
            "size_bytes": storage_bytes,
            "storage_size_bytes": storage_bytes,
            "size_label": self._format_bytes(storage_bytes),
            "storage_size_label": self._format_bytes(storage_bytes),
            "storage_size_available": storage_available,
            "measurement_scope": measurement.get("measurement_scope"),
            "measurement_status": measurement.get("measurement_status"),
            "measurement_reason": measurement.get("measurement_reason"),
            "soft_limit_bytes": policy.storage_soft_limit_bytes,
            "storage_soft_limit_bytes": policy.storage_soft_limit_bytes,
            "hard_limit_bytes": policy.storage_hard_limit_bytes,
            "storage_hard_limit_bytes": policy.storage_hard_limit_bytes,
            "used_percentage_of_soft_limit": used_soft_pct,
            "used_percentage_of_hard_limit": used_hard_pct,
            "capacity_cleanup_recommended": capacity_cleanup_recommended,
            "auto_cleanup_enabled": policy.auto_cleanup_enabled,
            "auto_cleanup_performed": auto_cleanup_performed,
            "auto_cleanup_message": auto_cleanup_message,
            "capacity_cleanup_plan": capacity_plan,
            "postgres_vacuum_note": (
                "Deleted rows may require PostgreSQL autovacuum to reclaim physical disk space."
                if storage_bytes is not None and (status in {"warning", "critical"} or auto_cleanup_performed)
                else None
            ),
            "warning_threshold_count": policy.warning_threshold_count,
            "critical_threshold_count": policy.critical_threshold_count,
            "warning_threshold_storage_bytes": policy.warning_threshold_storage_bytes,
            "status": status,
            "status_reasons": reasons,
            "recommended_cleanup_action": recommended,
            "last_cleanup_timestamp": None,
        }
        if status in {"warning", "critical"}:
            self._emit_notification_event(
                event_type="admin_logs.storage",
                severity=status,
                title=f"Admin Logs storage {status}",
                message=recommended,
                payload={
                    "status": status,
                    "status_reasons": reasons,
                    "total_log_count": total_logs,
                    "total_event_count": total_events,
                    "storage_size_bytes": storage_bytes,
                    "capacity_cleanup_recommended": capacity_cleanup_recommended,
                },
                fingerprint=f"admin_logs.storage:{status}:{','.join(sorted(set(reasons))) or 'health'}",
                dedupe_window=timedelta(minutes=30),
            )
        if auto_cleanup_performed:
            self._emit_notification_event(
                event_type="admin_logs.cleanup",
                severity="warning",
                title="Admin Logs capacity cleanup performed",
                message=auto_cleanup_message or "Automatic Admin Logs capacity cleanup deleted old sessions.",
                payload={"mode": "capacity", "status": status, "auto_cleanup_performed": True},
                fingerprint="admin_logs.cleanup:auto",
                dedupe_window=timedelta(minutes=30),
            )
        if cleanup_failed_message:
            self._emit_notification_event(
                event_type="admin_logs.cleanup",
                severity="critical",
                title="Admin Logs capacity cleanup failed",
                message=cleanup_failed_message,
                payload={"mode": "capacity", "status": status},
                fingerprint=f"admin_logs.cleanup:failed:{cleanup_failed_message}",
                dedupe_window=timedelta(minutes=30),
            )
        return summary

    def cleanup(
        self,
        *,
        mode: Optional[str] = None,
        use_retention: bool = False,
        older_than: Optional[str] = None,
        dry_run: bool = True,
        status: Optional[str] = None,
        category: Optional[str] = None,
        batch_size: int = 1000,
    ) -> Dict[str, Any]:
        policy = self._policy()
        normalized_mode = str(mode or "").strip().lower()
        if use_retention:
            normalized_mode = "retention"
        if older_than and normalized_mode in {"", "retention"} and not use_retention:
            normalized_mode = "before_date"
        if not normalized_mode:
            raise ValueError("Cleanup requires mode=retention, mode=capacity, use_retention=true, or a valid older_than cutoff.")
        if normalized_mode not in {"retention", "before_date", "capacity"}:
            raise ValueError("Cleanup mode must be retention, before_date, or capacity.")
        if normalized_mode == "capacity":
            return self._cleanup_capacity(dry_run=dry_run, batch_size=batch_size)

        cutoff = datetime.now() - timedelta(days=policy.retention_days) if normalized_mode == "retention" else self._parse_cutoff(older_than)
        if cutoff is None:
            raise ValueError("Cleanup requires use_retention=true or a valid older_than cutoff.")
        if cutoff >= datetime.now():
            raise ValueError("Cleanup cutoff must be in the past.")

        safe_batch_size = max(1, min(int(batch_size or 1000), 5000))
        with self.db.session_scope() as session:
            filters = [ExecutionLogSession.started_at < cutoff]
            if status:
                filters.append(ExecutionLogSession.overall_status == status)
            if category:
                matched_ids = session.execute(
                    select(ExecutionLogEvent.session_id)
                    .where(and_(ExecutionLogEvent.phase == category, ExecutionLogEvent.event_at < cutoff))
                    .distinct()
                ).scalars().all()
                if not matched_ids:
                    return self._cleanup_payload(mode=normalized_mode, cutoff=cutoff, dry_run=dry_run, status=status, category=category)
                filters.append(ExecutionLogSession.session_id.in_(matched_ids))

            where_clause = and_(*filters)
            matching_sessions = session.execute(
                select(ExecutionLogSession.session_id)
                .where(where_clause)
                .order_by(ExecutionLogSession.started_at.asc())
                .limit(safe_batch_size)
            ).scalars().all()
            matched_log_count = int(session.execute(select(func.count(ExecutionLogSession.id)).where(where_clause)).scalar() or 0)
            matched_event_count = int(
                session.execute(select(func.count(ExecutionLogEvent.id)).where(ExecutionLogEvent.session_id.in_(matching_sessions))).scalar()
                if matching_sessions
                else 0
            )
            if dry_run or not matching_sessions:
                return self._cleanup_payload(
                    mode=normalized_mode,
                    cutoff=cutoff,
                    dry_run=dry_run,
                    status=status,
                    category=category,
                    matched_log_count=matched_log_count,
                    matched_event_count=matched_event_count,
                )
            deleted_event_count = int(
                session.execute(delete(ExecutionLogEvent).where(ExecutionLogEvent.session_id.in_(matching_sessions))).rowcount
                or 0
            )
            deleted_log_count = int(
                session.execute(delete(ExecutionLogSession).where(ExecutionLogSession.session_id.in_(matching_sessions))).rowcount
                or 0
            )
            return self._cleanup_payload(
                mode=normalized_mode,
                cutoff=cutoff,
                dry_run=False,
                status=status,
                category=category,
                matched_log_count=matched_log_count,
                matched_event_count=matched_event_count,
                deleted_log_count=deleted_log_count,
                deleted_event_count=deleted_event_count,
            )

    def _cleanup_capacity(self, *, dry_run: bool, batch_size: int) -> Dict[str, Any]:
        policy = self._policy()
        storage_bytes = self._storage_bytes()
        if storage_bytes is None:
            raise ValueError("Capacity cleanup requires PostgreSQL storage size; storage size is unavailable for this database.")
        min_retention_cutoff = datetime.now() - timedelta(days=policy.min_retention_days)
        safe_batch_size = max(1, min(int(batch_size or policy.cleanup_batch_size), policy.cleanup_batch_size, 5000))
        with self.db.session_scope() as session:
            total_logs = int(session.execute(select(func.count(ExecutionLogSession.id))).scalar() or 0)
            candidates = self._capacity_candidates(
                session=session,
                cutoff=min_retention_cutoff,
                batch_size=safe_batch_size,
            )
            matching_sessions = candidates["session_ids"]
            matched_log_count = candidates["matched_log_count"]
            matched_event_count = candidates["matched_event_count"]
            hard_limit_exceeded = storage_bytes >= policy.storage_hard_limit_bytes
            if dry_run or not matching_sessions or not hard_limit_exceeded:
                return self._cleanup_payload(
                    mode="capacity",
                    cutoff=min_retention_cutoff,
                    dry_run=dry_run,
                    status=None,
                    category=None,
                    matched_log_count=matched_log_count if hard_limit_exceeded else 0,
                    matched_event_count=matched_event_count if hard_limit_exceeded else 0,
                    additional_cleanup_needed=hard_limit_exceeded and matched_log_count > len(matching_sessions),
                    message="Capacity cleanup not needed." if not hard_limit_exceeded else None,
                )
            deleted_event_count = int(
                session.execute(delete(ExecutionLogEvent).where(ExecutionLogEvent.session_id.in_(matching_sessions))).rowcount
                or 0
            )
            deleted_log_count = int(
                session.execute(delete(ExecutionLogSession).where(ExecutionLogSession.session_id.in_(matching_sessions))).rowcount
                or 0
            )
            estimated_bytes_per_session = int(storage_bytes / total_logs) if total_logs > 0 else 0
            estimated_remaining_bytes = max(0, storage_bytes - (estimated_bytes_per_session * deleted_log_count))
            additional_cleanup_needed = estimated_remaining_bytes > policy.storage_soft_limit_bytes and matched_log_count > deleted_log_count
            result = self._cleanup_payload(
                mode="capacity",
                cutoff=min_retention_cutoff,
                dry_run=False,
                status=None,
                category=None,
                matched_log_count=matched_log_count,
                matched_event_count=matched_event_count,
                deleted_log_count=deleted_log_count,
                deleted_event_count=deleted_event_count,
                additional_cleanup_needed=additional_cleanup_needed,
                message=(
                    "Deleted rows may require PostgreSQL autovacuum to reclaim physical disk space."
                    if deleted_log_count > 0
                    else None
                ),
            )
            self._emit_notification_event(
                event_type="admin_logs.cleanup",
                severity="warning",
                title="Admin Logs capacity cleanup performed",
                message=f"Capacity cleanup deleted {deleted_log_count} sessions and {deleted_event_count} events.",
                payload={
                    "mode": "capacity",
                    "deleted_log_count": deleted_log_count,
                    "deleted_event_count": deleted_event_count,
                    "additional_cleanup_needed": additional_cleanup_needed,
                },
                fingerprint=f"admin_logs.cleanup:capacity:{deleted_log_count}:{deleted_event_count}:{additional_cleanup_needed}",
                dedupe_window=timedelta(minutes=30),
            )
            return result

    def _cleanup_payload(
        self,
        *,
        mode: str = "retention",
        cutoff: Optional[datetime] = None,
        dry_run: bool,
        status: Optional[str],
        category: Optional[str],
        matched_log_count: int = 0,
        matched_event_count: int = 0,
        deleted_log_count: int = 0,
        deleted_event_count: int = 0,
        additional_cleanup_needed: bool = False,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "mode": mode,
            "dry_run": dry_run,
            "cutoff": self._iso(cutoff),
            "matched_log_count": matched_log_count,
            "matched_event_count": matched_event_count,
            "deleted_log_count": deleted_log_count,
            "deleted_event_count": deleted_event_count,
            "status_filter": status,
            "category_filter": category,
            "additional_cleanup_needed": additional_cleanup_needed,
            "message": message,
            "postgres_vacuum_note": (
                "Deleted rows may require PostgreSQL autovacuum to reclaim physical disk space."
                if deleted_log_count > 0 or mode == "capacity"
                else None
            ),
        }
