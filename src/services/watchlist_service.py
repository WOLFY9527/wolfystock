# -*- coding: utf-8 -*-
"""User watchlist service for scanner candidate tracking."""

from __future__ import annotations

import re
import json
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, select

from src.repositories.scanner_repo import ScannerRepository
from src.services.catalyst_event_exposure import build_catalyst_event_exposures
from src.services.reason_code_vocabulary import classify_reason_code
from src.services.scanner_evidence_packet import build_scanner_investor_signal
from src.storage import AppUser, DatabaseManager, MarketScannerCandidate, MarketScannerRun, RuleBacktestRun, UserWatchlistItem
from src.utils.symbol_normalization import canonical_stock_code


_LOCAL_OHLCV_HISTORY_SOURCES = {"local_us_parquet", "local_us_parquet_dir"}
_SCORE_STATUS_CONTEXT = {
    "scope": "score_refresh_recency",
    "fresh_means": "persisted_scanner_score_refreshed",
    "source_freshness_implied": False,
    "source_authority_implied": False,
}
_LINEAGE_CONTRACT_VERSION = "scanner_watchlist_lineage_v1"
_LINEAGE_FORBIDDEN_TEXT_RE = re.compile(
    r"sourceauthorityallowed|scorecontributionallowed|reasonfamilies|reasoncode|"
    r"source_confidence|score_blocked|raw diagnostics?|json|provider|debug|"
    r"payload|trace|stack|buy|sell|recommend|stop|target|position|"
    r"买入|卖出|加仓|减仓|下单|交易|止损|止盈|目标价|仓位|必买|稳赚|保证收益",
    re.IGNORECASE,
)
class WatchlistService:
    """Business logic for user-owned candidate tracking."""

    _symbol_pattern = re.compile(r"[A-Z0-9][A-Z0-9.\-]*")
    _refresh_lock = threading.Lock()
    _refresh_running = False

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or DatabaseManager.get_instance()
        self.scanner_repo = ScannerRepository(self.db)

    @staticmethod
    def _normalize_market(market: str) -> str:
        normalized = str(market or "").strip().lower()
        if normalized not in {"cn", "hk", "us"}:
            raise ValueError("market must be one of: cn, hk, us")
        return normalized

    @classmethod
    def _normalize_symbol(cls, symbol: str) -> str:
        normalized = canonical_stock_code(symbol).strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        if len(normalized) > 16:
            raise ValueError("symbol must be at most 16 characters")
        if not cls._symbol_pattern.fullmatch(normalized):
            raise ValueError("symbol contains invalid characters")
        return normalized

    @staticmethod
    def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _row_to_dict(row: UserWatchlistItem) -> Dict[str, Any]:
        payload = {
            "id": int(row.id),
            "symbol": str(row.symbol),
            "market": str(row.market),
            "name": str(row.name) if row.name else None,
            "source": str(row.source),
            "scanner_run_id": int(row.scanner_run_id) if row.scanner_run_id is not None else None,
            "scanner_rank": int(row.scanner_rank) if row.scanner_rank is not None else None,
            "scanner_score": float(row.scanner_score) if row.scanner_score is not None else None,
            "last_scored_at": row.last_scored_at.isoformat() if row.last_scored_at else None,
            "score_source": str(row.score_source) if row.score_source else None,
            "score_profile": str(row.score_profile) if row.score_profile else None,
            "score_reason": str(row.score_reason) if row.score_reason else None,
            "score_status": str(row.score_status) if row.score_status else None,
            "score_status_context": dict(_SCORE_STATUS_CONTEXT),
            "score_error": str(row.score_error) if row.score_error else None,
            "theme_id": str(row.theme_id) if row.theme_id else None,
            "universe_type": str(row.universe_type) if row.universe_type else None,
            "notes": str(row.notes) if row.notes else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        payload["intelligence"] = WatchlistService._build_intelligence_payload(payload)
        return payload

    @staticmethod
    def _load_json_object(raw: Optional[str]) -> Dict[str, Any]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number == number else None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _scanner_candidate_key(item: Dict[str, Any]) -> Optional[tuple[int, str]]:
        scanner_run_id = item.get("scanner_run_id")
        if scanner_run_id is None:
            return None
        try:
            run_id = int(scanner_run_id)
        except (TypeError, ValueError):
            return None
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            return None
        return (run_id, symbol)

    @staticmethod
    def _project_local_ohlcv_provenance(diagnostics: Dict[str, Any]) -> Optional[Dict[str, str]]:
        history = diagnostics.get("history") if isinstance(diagnostics.get("history"), dict) else {}
        source = str(
            history.get("source")
            or diagnostics.get("history_source")
            or diagnostics.get("historySource")
            or ""
        ).strip().lower()
        if source not in _LOCAL_OHLCV_HISTORY_SOURCES:
            return None
        return {
            "data_quality": "cached",
            "label": "最近可用",
        }

    @staticmethod
    def _consumer_data_quality_label(*values: Any) -> str:
        tokens: List[str] = []
        for value in values:
            if isinstance(value, dict):
                tokens.extend(str(key) for key, flag in value.items() if flag is True)
                tokens.extend(str(item) for item in value.values() if isinstance(item, str))
            elif isinstance(value, (list, tuple, set)):
                tokens.extend(str(item) for item in value)
            elif value is not None:
                tokens.append(str(value))
        normalized = " ".join(tokens).strip().lower()
        if not normalized:
            return "no_evidence"
        if any(marker in normalized for marker in ("unavailable", "provider_down", "provider_error", "data_failed", "failed", "error")):
            return "unavailable"
        if any(marker in normalized for marker in ("missing", "insufficient", "no_data", "no evidence", "no_evidence", "updating")):
            return "no_evidence"
        if any(marker in normalized for marker in ("cached", "cache_snapshot", "local")):
            return "cached"
        if any(marker in normalized for marker in ("stale", "delayed")):
            return "delayed"
        if any(marker in normalized for marker in ("fallback", "partial", "synthetic", "proxy", "limited", "observation")):
            return "partial"
        if any(marker in normalized for marker in ("ready", "available", "complete", "fresh", "live", "selected", "score_grade")):
            return "ready"
        return "no_evidence"

    @staticmethod
    def _sanitize_investor_signal(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        allowed = {
            "contractVersion",
            "freshness",
            "confidenceLabel",
            "warningLabels",
            "dataQuality",
            "noAdviceBoundary",
        }
        projected = {key: value for key, value in payload.items() if key in allowed and value is not None}
        if "dataQuality" not in projected:
            projected["dataQuality"] = WatchlistService._consumer_data_quality_label(payload.get("freshness"))
        return projected or None

    @staticmethod
    def _optional_bool(value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        return None

    @staticmethod
    def _optional_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @classmethod
    def _optional_consumer_text(cls, value: Any) -> Optional[str]:
        normalized = cls._optional_str(value)
        if normalized is None:
            return None
        if _LINEAGE_FORBIDDEN_TEXT_RE.search(normalized):
            return None
        return normalized

    @staticmethod
    def _parse_iso_datetime(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _isoformat_datetime(value: Any) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        return WatchlistService._optional_str(value)

    @staticmethod
    def _optional_object(payload: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key not in payload:
                continue
            value = payload.get(key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, (list, tuple, dict)) and not value:
                continue
            return value
        return None

    @classmethod
    def _payload_has_any_value(cls, payload: Any, *keys: str) -> bool:
        if not isinstance(payload, dict):
            return False
        return any(cls._optional_object(payload, key) is not None for key in keys)

    @classmethod
    def _payload_has_any_text(cls, payload: Any, *keys: str) -> bool:
        if not isinstance(payload, dict):
            return False
        return any(cls._optional_str(payload.get(key)) is not None for key in keys)

    @classmethod
    def _eligible_catalyst_fundamental_snapshot(cls, diagnostics: Dict[str, Any]) -> Any:
        payload = cls._optional_object(
            diagnostics,
            "fundamentalSnapshot",
            "fundamental_snapshot",
            "earningsSnapshot",
            "earnings_snapshot",
            "earningsOutlook",
            "earnings_outlook",
        )
        if not isinstance(payload, dict):
            return None
        if cls._payload_has_any_value(
            payload,
            "reportedPeriod",
            "reported_period",
            "fiscalPeriod",
            "fiscal_period",
            "period",
            "quarter",
            "asOf",
            "as_of",
            "updatedAt",
            "updated_at",
            "freshness",
            "freshnessStatus",
            "freshness_status",
            "status",
            "stale",
            "isStale",
            "expired",
            "isExpired",
        ):
            return payload
        if cls._payload_has_any_text(payload, "summary", "earningsSummary", "fundamentalSummary", "outlook"):
            return payload
        return None

    @classmethod
    def _eligible_catalyst_news_items(cls, diagnostics: Dict[str, Any]) -> Any:
        payload = cls._optional_object(
            diagnostics,
            "storedNewsItems",
            "stored_news_items",
            "storedNews",
            "stored_news",
            "newsItems",
            "news_items",
        )
        if payload is None:
            return None
        if isinstance(payload, dict):
            items = cls._optional_object(payload, "items", "news", "articles", "headlines")
            if isinstance(items, (list, tuple)):
                for item in items:
                    if cls._payload_has_any_text(item, "headline", "title", "name", "summary", "description", "snippet", "abstract"):
                        return payload
                return None
            return payload if cls._payload_has_any_text(payload, "headline", "title", "name", "summary", "description", "snippet", "abstract") else None
        if isinstance(payload, (list, tuple)):
            for item in payload:
                if cls._payload_has_any_text(item, "headline", "title", "name", "summary", "description", "snippet", "abstract"):
                    return payload
        return None

    @classmethod
    def _eligible_catalyst_macro_status(cls, diagnostics: Dict[str, Any]) -> Any:
        payload = cls._optional_object(
            diagnostics,
            "officialMacroStatus",
            "official_macro_status",
            "macroStatus",
            "macro_status",
        )
        if not isinstance(payload, dict):
            return None
        if cls._payload_has_any_value(
            payload,
            "status",
            "freshness",
            "freshnessStatus",
            "freshness_status",
            "asOf",
            "as_of",
            "updatedAt",
            "updated_at",
            "series",
            "items",
            "observations",
            "stale",
            "isStale",
            "expired",
            "isExpired",
        ):
            return payload
        return None

    @classmethod
    def _project_catalyst_exposures(cls, item: Dict[str, Any], diagnostics: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        exposures = build_catalyst_event_exposures(
            symbol=str(item.get("symbol") or ""),
            market=str(item.get("market") or ""),
            as_of=item.get("last_scored_at") or item.get("updated_at") or item.get("created_at"),
            fundamental_snapshot=cls._eligible_catalyst_fundamental_snapshot(diagnostics),
            stored_news_items=cls._eligible_catalyst_news_items(diagnostics),
            official_macro_status=cls._eligible_catalyst_macro_status(diagnostics),
        )
        projected = [exposure.to_dict() for exposure in exposures]
        return projected or None

    @classmethod
    def _project_reason_family(cls, raw_code: Any) -> Optional[Dict[str, Any]]:
        normalized = cls._optional_str(raw_code)
        if normalized is None:
            return None
        classification = classify_reason_code(normalized)
        return {
            "raw_code": classification.raw_code,
            "family": classification.family,
            "scope": classification.scope,
        }

    @classmethod
    def _project_source_confidence_reason_families(cls, payload: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        projected = {
            "degradation_reason": cls._project_reason_family(payload.get("degradation_reason")),
            "cap_reason": cls._project_reason_family(payload.get("cap_reason")),
        }
        return projected if any(value is not None for value in projected.values()) else None

    @classmethod
    def _project_scanner_reason_families(cls, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        source_confidence = payload.get("source_confidence")
        projected = {
            "cap_reason": cls._project_reason_family(payload.get("cap_reason")),
            "degradation_reason": cls._project_reason_family(payload.get("degradation_reason")),
            "source_confidence": cls._project_source_confidence_reason_families(source_confidence),
        }
        return projected if any(value is not None for value in projected.values()) else None

    @classmethod
    def _project_source_confidence(cls, payload: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        projected = {
            "source": cls._optional_str(payload.get("source")),
            "source_label": cls._optional_str(payload.get("sourceLabel") or payload.get("source_label")),
            "source_type": cls._optional_str(payload.get("sourceType") or payload.get("source_type")),
            "as_of": cls._optional_str(payload.get("asOf") or payload.get("as_of")),
            "freshness": cls._optional_str(payload.get("freshness")),
            "is_fallback": cls._optional_bool(payload.get("isFallback", payload.get("is_fallback"))),
            "is_stale": cls._optional_bool(payload.get("isStale", payload.get("is_stale"))),
            "is_partial": cls._optional_bool(payload.get("isPartial", payload.get("is_partial"))),
            "is_synthetic": cls._optional_bool(payload.get("isSynthetic", payload.get("is_synthetic"))),
            "is_unavailable": cls._optional_bool(payload.get("isUnavailable", payload.get("is_unavailable"))),
            "coverage": cls._safe_float(payload.get("coverage")),
            "score_contribution_allowed": cls._optional_bool(
                payload.get("scoreContributionAllowed", payload.get("score_contribution_allowed"))
            ),
            "source_authority_allowed": cls._optional_bool(
                payload.get("sourceAuthorityAllowed", payload.get("source_authority_allowed"))
            ),
            "observation_only": cls._optional_bool(payload.get("observationOnly", payload.get("observation_only"))),
            "degradation_reason": cls._optional_str(
                payload.get("degradationReason") or payload.get("degradation_reason")
            ),
            "cap_reason": cls._optional_str(payload.get("capReason") or payload.get("cap_reason")),
        }
        return projected if any(value is not None for value in projected.values()) else None

    @classmethod
    def _project_scanner_score_disclosure_internal(cls, diagnostics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        explainability = diagnostics.get("score_explainability")
        if not isinstance(explainability, dict):
            return None
        projected = {
            "score_confidence": cls._safe_float(explainability.get("score_confidence")),
            "score_grade_allowed": cls._optional_bool(
                explainability.get("score_grade_allowed")
            ),
            "cap_reason": cls._optional_str(explainability.get("cap_reason")),
            "degradation_reason": cls._optional_str(explainability.get("degradation_reason")),
            "source_confidence": cls._project_source_confidence(explainability.get("source_confidence")),
        }
        projected["reason_families"] = cls._project_scanner_reason_families(projected)
        return projected if any(value is not None for value in projected.values()) else None

    @classmethod
    def _project_scanner_score_disclosure(cls, disclosure: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not isinstance(disclosure, dict):
            return None
        source_confidence = disclosure.get("source_confidence") if isinstance(disclosure.get("source_confidence"), dict) else {}
        projected = {
            "score_confidence": cls._safe_float(disclosure.get("score_confidence")),
            "data_quality": cls._consumer_data_quality_label(
                source_confidence,
                source_confidence.get("freshness"),
                disclosure.get("score_grade_allowed"),
                disclosure.get("cap_reason"),
                disclosure.get("degradation_reason"),
            ),
        }
        return projected if any(value is not None for value in projected.values()) else None

    @classmethod
    def _lineage_score_grade_allowed(cls, disclosure: Optional[Dict[str, Any]]) -> bool:
        if not isinstance(disclosure, dict):
            return False
        source_confidence = disclosure.get("source_confidence")
        if not isinstance(source_confidence, dict):
            return False
        if disclosure.get("score_grade_allowed") is not True:
            return False
        if source_confidence.get("source_authority_allowed") is not True:
            return False
        if source_confidence.get("score_contribution_allowed") is not True:
            return False
        if source_confidence.get("observation_only") is True:
            return False
        if any(
            source_confidence.get(flag) is True
            for flag in ("is_fallback", "is_stale", "is_partial", "is_synthetic", "is_unavailable")
        ):
            return False
        if disclosure.get("cap_reason") or disclosure.get("degradation_reason"):
            return False
        return True

    @classmethod
    def _lineage_data_state(
        cls,
        *,
        item: Dict[str, Any],
        disclosure: Optional[Dict[str, Any]],
        score_grade_allowed: bool,
    ) -> str:
        status = str(item.get("score_status") or "").strip().lower()
        source_confidence = disclosure.get("source_confidence") if isinstance(disclosure, dict) else None
        if status in {"data_failed", "provider_down", "provider_error", "failed", "error", "critical"}:
            return "unavailable"
        if isinstance(source_confidence, dict) and source_confidence.get("is_unavailable") is True:
            return "unavailable"
        if status in {"insufficient", "insufficient_history", "no_data", "missing_data"}:
            return "no_evidence"
        if status in {"", "unknown"} and item.get("scanner_score") is None:
            return "no_evidence"
        if score_grade_allowed:
            return "ready"
        if disclosure is None:
            return "no_evidence"
        return cls._consumer_data_quality_label(source_confidence, disclosure.get("cap_reason"), disclosure.get("degradation_reason"))

    @staticmethod
    def _lineage_freshness_label(data_state: str, disclosure: Optional[Dict[str, Any]]) -> str:
        if data_state == "ready":
            return "已更新"
        if data_state == "unavailable":
            return "暂不可用"
        if data_state == "no_evidence":
            return "数据不足"
        if data_state == "partial":
            return "部分可用"
        if data_state == "delayed":
            return "延迟可用"
        if data_state == "cached":
            return "最近可用"
        source_confidence = disclosure.get("source_confidence") if isinstance(disclosure, dict) else None
        freshness = str(source_confidence.get("freshness") or "").strip().lower() if isinstance(source_confidence, dict) else ""
        if freshness in {"live", "fresh"}:
            return "已更新"
        return "最近可用"

    @classmethod
    def _lineage_score_snapshot_kind(cls, item: Dict[str, Any]) -> str:
        last_scored_at = cls._parse_iso_datetime(item.get("last_scored_at"))
        created_at = cls._parse_iso_datetime(item.get("created_at"))
        if last_scored_at is not None and created_at is not None and last_scored_at > created_at + timedelta(minutes=1):
            return "post_add_refresh"
        return "saved_at_add"

    @classmethod
    def _extract_lineage_frame(cls, diagnostics: Dict[str, Any], *keys: str) -> Dict[str, Any]:
        for key in keys:
            value = diagnostics.get(key)
            if isinstance(value, dict):
                return value
        return {}

    @classmethod
    def _lineage_research_reason(
        cls,
        *,
        item: Dict[str, Any],
        candidate: MarketScannerCandidate,
        diagnostics: Dict[str, Any],
    ) -> str:
        summary_frame = cls._extract_lineage_frame(
            diagnostics,
            "candidateResearchSummaryFrame",
            "candidate_research_summary_frame",
        )
        consumer_diagnostics = cls._extract_lineage_frame(
            diagnostics,
            "consumerDiagnostics",
            "consumer_diagnostics",
        )
        label_values = consumer_diagnostics.get("userFacingLabels") or consumer_diagnostics.get("user_facing_labels")
        labels = label_values if isinstance(label_values, list) else []
        for value in (
            summary_frame.get("primaryResearchReason"),
            summary_frame.get("primary_research_reason"),
            summary_frame.get("researchReason"),
            summary_frame.get("research_reason"),
            *labels,
            getattr(candidate, "reason_summary", None),
            item.get("notes"),
        ):
            safe = cls._optional_consumer_text(value)
            if safe is not None:
                return safe
        return "研究观察"

    @classmethod
    def _lineage_research_next_step(cls, diagnostics: Dict[str, Any]) -> str:
        summary_frame = cls._extract_lineage_frame(
            diagnostics,
            "candidateResearchSummaryFrame",
            "candidate_research_summary_frame",
        )
        readiness_frame = cls._extract_lineage_frame(
            diagnostics,
            "candidateResearchReadiness",
            "candidate_research_readiness",
        )
        for value in (
            summary_frame.get("researchNextStep"),
            summary_frame.get("research_next_step"),
            summary_frame.get("nextStep"),
            summary_frame.get("next_step"),
            readiness_frame.get("researchNextStep"),
            readiness_frame.get("research_next_step"),
            readiness_frame.get("nextStep"),
            readiness_frame.get("next_step"),
        ):
            safe = cls._optional_consumer_text(value)
            if safe is not None:
                return safe
        return "补充证据后继续观察。"

    @classmethod
    def _project_scanner_lineage_v1(
        cls,
        *,
        item: Dict[str, Any],
        candidate: MarketScannerCandidate,
        run: MarketScannerRun,
        diagnostics: Dict[str, Any],
        disclosure: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        score_grade_allowed = cls._lineage_score_grade_allowed(disclosure)
        data_state = cls._lineage_data_state(
            item=item,
            disclosure=disclosure,
            score_grade_allowed=score_grade_allowed,
        )
        run_completed_at = (
            cls._isoformat_datetime(getattr(run, "completed_at", None))
            or cls._isoformat_datetime(getattr(run, "run_at", None))
            or cls._isoformat_datetime(getattr(candidate, "created_at", None))
        )
        return {
            "contract_version": _LINEAGE_CONTRACT_VERSION,
            "source": "scanner",
            "scanner_run_id": cls._safe_int(getattr(run, "id", None) or item.get("scanner_run_id")),
            "symbol": str(getattr(candidate, "symbol", None) or item.get("symbol") or "").strip().upper(),
            "market": str(getattr(run, "market", None) or item.get("market") or "").strip().lower(),
            "rank_at_scan": cls._safe_int(getattr(candidate, "rank", None) or item.get("scanner_rank")),
            "score_at_scan": cls._safe_float(getattr(candidate, "score", None) if getattr(candidate, "score", None) is not None else item.get("scanner_score")),
            "score_snapshot_kind": cls._lineage_score_snapshot_kind(item),
            "run_profile": cls._optional_str(getattr(run, "profile", None)),
            "run_completed_at": run_completed_at,
            "watchlist_added_at": cls._optional_str(item.get("created_at")),
            "theme_id": cls._optional_str(item.get("theme_id")),
            "universe_type": cls._optional_str(item.get("universe_type")),
            "research_reason": cls._lineage_research_reason(item=item, candidate=candidate, diagnostics=diagnostics),
            "research_next_step": cls._lineage_research_next_step(diagnostics),
            "data_state": data_state,
            "freshness_label": cls._lineage_freshness_label(data_state, disclosure),
            "no_advice_boundary": True,
        }

    def _scanner_intelligence_context_by_item(self, items: List[Dict[str, Any]]) -> Dict[tuple[int, str], Dict[str, Any]]:
        keys = {key for item in items if (key := self._scanner_candidate_key(item)) is not None}
        if not keys:
            return {}
        item_by_key = {
            key: item
            for item in items
            if (key := self._scanner_candidate_key(item)) is not None
        }
        run_ids = sorted({run_id for run_id, _symbol in keys})
        symbols = sorted({symbol for _run_id, symbol in keys})
        with self.db.get_session() as session:
            candidates = session.execute(
                select(MarketScannerCandidate, MarketScannerRun)
                .join(MarketScannerRun, MarketScannerRun.id == MarketScannerCandidate.run_id)
                .where(
                    and_(
                        MarketScannerCandidate.run_id.in_(run_ids),
                        MarketScannerCandidate.symbol.in_(symbols),
                    )
                )
            ).all()

        context_by_key: Dict[tuple[int, str], Dict[str, Any]] = {}
        for candidate, run in candidates:
            key = (int(candidate.run_id), str(candidate.symbol or "").upper())
            if key not in keys or key in context_by_key:
                continue
            diagnostics = self._load_json_object(getattr(candidate, "diagnostics_json", None))
            item = item_by_key.get(key, {})
            context: Dict[str, Any] = {}
            provenance = self._project_local_ohlcv_provenance(diagnostics)
            internal_disclosure = self._project_scanner_score_disclosure_internal(diagnostics)
            disclosure = self._project_scanner_score_disclosure(internal_disclosure)
            investor_signal = build_scanner_investor_signal(diagnostics)
            lineage = self._project_scanner_lineage_v1(
                item=item,
                candidate=candidate,
                run=run,
                diagnostics=diagnostics,
                disclosure=internal_disclosure,
            )
            catalyst_exposures = self._project_catalyst_exposures(item, diagnostics)
            if provenance is not None:
                context["ohlcv_provenance"] = provenance
            if disclosure is not None:
                context["score_disclosure"] = disclosure
            if investor_signal is not None:
                context["investor_signal"] = self._sanitize_investor_signal(investor_signal)
            context["scanner_lineage_v1"] = lineage
            if catalyst_exposures is not None:
                context["catalyst_exposures"] = catalyst_exposures
            if context:
                context_by_key[key] = context
        return context_by_key

    @staticmethod
    def _build_intelligence_payload(
        item: Dict[str, Any],
        *,
        backtest: Optional[RuleBacktestRun] = None,
        scanner_ohlcv_provenance: Optional[Dict[str, str]] = None,
        scanner_score_disclosure: Optional[Dict[str, Any]] = None,
        scanner_investor_signal: Optional[Dict[str, Any]] = None,
        scanner_lineage_v1: Optional[Dict[str, Any]] = None,
        catalyst_exposures: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        scanner_score = WatchlistService._safe_float(item.get("scanner_score"))
        scanner_status = "selected" if scanner_score is not None or item.get("scanner_run_id") else "unknown"
        if str(item.get("score_status") or "").strip().lower() == "data_failed":
            scanner_status = "data_failed"

        strategy_simulation = {
            "lookback_days": None,
            "forward_days": None,
            "avg_forward_return_pct": None,
            "hit_rate": None,
            "avg_excess_return_pct": None,
            "selection_count": None,
            "data_coverage": None,
            "status": "unknown",
        }

        backtest_payload = {
            "last_result_id": None,
            "total_return_pct": None,
            "max_drawdown_pct": None,
            "sharpe": None,
            "trade_count": None,
            "tested_at": None,
        }
        if backtest is not None:
            summary = WatchlistService._load_json_object(getattr(backtest, "summary_json", None))
            metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
            backtest_payload = {
                "last_result_id": int(backtest.id) if backtest.id is not None else None,
                "total_return_pct": WatchlistService._safe_float(backtest.total_return_pct),
                "max_drawdown_pct": WatchlistService._safe_float(backtest.max_drawdown_pct),
                "sharpe": WatchlistService._safe_float(
                    metrics.get("sharpe_ratio")
                    if isinstance(metrics, dict)
                    else None
                ),
                "trade_count": int(backtest.trade_count) if backtest.trade_count is not None else None,
                "tested_at": (
                    backtest.completed_at.isoformat()
                    if backtest.completed_at
                    else backtest.run_at.isoformat()
                    if backtest.run_at
                    else None
                ),
            }

        scanner_payload = {
            "last_score": scanner_score,
            "last_rank": int(item["scanner_rank"]) if item.get("scanner_rank") is not None else None,
            "status": scanner_status,
            "theme": item.get("theme_id"),
            "theme_label": None,
            "profile": item.get("score_profile"),
            "reason": item.get("score_reason") or item.get("notes"),
            "last_scanned_at": item.get("last_scored_at"),
        }
        if scanner_ohlcv_provenance is not None:
            scanner_payload["ohlcv_provenance"] = scanner_ohlcv_provenance
            scanner_payload["data_quality"] = scanner_ohlcv_provenance.get("data_quality")
        if scanner_score_disclosure is not None:
            scanner_payload.update(scanner_score_disclosure)
        if scanner_investor_signal is not None:
            scanner_payload["investor_signal"] = scanner_investor_signal
        if scanner_lineage_v1 is not None:
            scanner_payload["scanner_lineage_v1"] = scanner_lineage_v1

        intelligence = {
            "scanner": scanner_payload,
            "strategy_simulation": strategy_simulation,
            "backtest": backtest_payload,
        }
        if catalyst_exposures:
            intelligence["catalyst_exposures"] = catalyst_exposures
        return intelligence

    def _latest_backtests_by_symbol(
        self,
        *,
        owner_id: str,
        symbols: List[str],
    ) -> Dict[str, RuleBacktestRun]:
        normalized_symbols = sorted({self._normalize_symbol(symbol) for symbol in symbols if symbol})
        if not normalized_symbols:
            return {}
        with self.db.get_session() as session:
            rows = session.execute(
                select(RuleBacktestRun)
                .where(
                    and_(
                        RuleBacktestRun.owner_id == owner_id,
                        RuleBacktestRun.code.in_(normalized_symbols),
                        RuleBacktestRun.status == "completed",
                    )
                )
                .order_by(
                    RuleBacktestRun.code.asc(),
                    desc(RuleBacktestRun.completed_at),
                    desc(RuleBacktestRun.run_at),
                    desc(RuleBacktestRun.id),
                )
            ).scalars().all()
        latest: Dict[str, RuleBacktestRun] = {}
        for row in rows:
            symbol = str(row.code).upper()
            if symbol not in latest:
                latest[symbol] = row
        return latest

    def _attach_intelligence(
        self,
        *,
        owner_id: str,
        items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        backtests = self._latest_backtests_by_symbol(
            owner_id=owner_id,
            symbols=[str(item.get("symbol") or "") for item in items],
        )
        scanner_context = self._scanner_intelligence_context_by_item(items)
        for item in items:
            item_key = self._scanner_candidate_key(item)
            intelligence_context = scanner_context.get(item_key or (-1, "")) or {}
            item["intelligence"] = self._build_intelligence_payload(
                item,
                backtest=backtests.get(str(item.get("symbol") or "").upper()),
                scanner_ohlcv_provenance=intelligence_context.get("ohlcv_provenance"),
                scanner_score_disclosure=intelligence_context.get("score_disclosure"),
                scanner_investor_signal=intelligence_context.get("investor_signal"),
                scanner_lineage_v1=intelligence_context.get("scanner_lineage_v1"),
                catalyst_exposures=intelligence_context.get("catalyst_exposures"),
            )
        return items

    def list_items(self, owner_id: str) -> List[Dict[str, Any]]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            rows = session.execute(
                select(UserWatchlistItem)
                .where(UserWatchlistItem.owner_id == resolved_owner_id)
                .order_by(UserWatchlistItem.updated_at.desc(), UserWatchlistItem.id.desc())
            ).scalars().all()
            items = [self._row_to_dict(row) for row in rows]
        return self._attach_intelligence(owner_id=resolved_owner_id, items=items)

    def get_item_by_id(self, *, owner_id: str, item_id: int) -> Optional[Dict[str, Any]]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            row = session.execute(
                select(UserWatchlistItem).where(
                    and_(
                        UserWatchlistItem.id == int(item_id),
                        UserWatchlistItem.owner_id == resolved_owner_id,
                    )
                ).limit(1)
            ).scalar_one_or_none()
            return self._row_to_dict(row) if row is not None else None

    def get_item_by_symbol(
        self,
        *,
        owner_id: str,
        symbol: str,
        market: str,
    ) -> Optional[Dict[str, Any]]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_market = self._normalize_market(market)
        with self.db.get_session() as session:
            row = session.execute(
                select(UserWatchlistItem).where(
                    and_(
                        UserWatchlistItem.owner_id == resolved_owner_id,
                        UserWatchlistItem.symbol == normalized_symbol,
                        UserWatchlistItem.market == normalized_market,
                    )
                ).limit(1)
            ).scalar_one_or_none()
            return self._row_to_dict(row) if row is not None else None

    def add_item(
        self,
        *,
        owner_id: str,
        symbol: str,
        market: str,
        source: str = "scanner",
        name: Optional[str] = None,
        scanner_run_id: Optional[int] = None,
        scanner_rank: Optional[int] = None,
        scanner_score: Optional[float] = None,
        theme_id: Optional[str] = None,
        universe_type: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_market = self._normalize_market(market)
        normalized_source = str(source or "").strip().lower() or "scanner"
        if normalized_source != "scanner":
            raise ValueError("source must be scanner")
        normalized_name = self._normalize_optional_text(name)
        normalized_theme_id = self._normalize_optional_text(theme_id)
        normalized_universe_type = self._normalize_optional_text(universe_type)
        normalized_notes = self._normalize_optional_text(notes)

        with self.db.get_session() as session:
            row = session.execute(
                select(UserWatchlistItem).where(
                    and_(
                        UserWatchlistItem.owner_id == resolved_owner_id,
                        UserWatchlistItem.symbol == normalized_symbol,
                        UserWatchlistItem.market == normalized_market,
                    )
                ).limit(1)
            ).scalar_one_or_none()

            if row is None:
                row = UserWatchlistItem(
                    owner_id=resolved_owner_id,
                    symbol=normalized_symbol,
                    market=normalized_market,
                    source=normalized_source,
                )
                session.add(row)
            else:
                row.source = normalized_source

            if normalized_name is not None:
                row.name = normalized_name
            if scanner_run_id is not None:
                row.scanner_run_id = int(scanner_run_id)
            if scanner_rank is not None:
                row.scanner_rank = int(scanner_rank)
            if scanner_score is not None:
                row.scanner_score = float(scanner_score)
            if normalized_theme_id is not None:
                row.theme_id = normalized_theme_id
            if normalized_universe_type is not None:
                row.universe_type = normalized_universe_type
            if normalized_notes is not None:
                row.notes = normalized_notes
            row.updated_at = datetime.now()
            session.commit()
            session.refresh(row)
            return self._row_to_dict(row)

    def refresh_scores(
        self,
        *,
        owner_id: str,
        market: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        source: Optional[str] = None,
        theme: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Refresh saved candidate scores from persisted scanner candidate rows.

        This intentionally does not run full AI analysis. It reuses the latest
        scanner scoring already persisted for each symbol/market and marks rows
        stale when no scanner score is available.
        """
        del force
        normalized_source = str(source or "").strip().lower() or None
        if normalized_source and normalized_source != "scanner":
            raise ValueError("source must be scanner")
        resolved_owner_id = self.db.require_user_id(owner_id)
        normalized_market = self._normalize_market(market) if market else None
        normalized_theme = self._normalize_optional_text(theme)
        normalized_symbols = {
            self._normalize_symbol(symbol)
            for symbol in (symbols or [])
            if str(symbol or "").strip()
        }
        started_at = datetime.now()
        results: List[Dict[str, Any]] = []
        markets: set[str] = set()
        updated_count = 0
        failed_count = 0
        skipped_count = 0

        if not self.__class__._refresh_lock.acquire(blocking=False):
            return {
                "ok": False,
                "updated_count": 0,
                "failed_count": 1,
                "skipped_count": 0,
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now().isoformat(),
                "markets": [],
                "results": [{"symbol": "*", "market": normalized_market or "all", "status": "running", "message": "Watchlist score refresh is already running."}],
            }

        self.__class__._refresh_running = True
        try:
            with self.db.get_session() as session:
                conditions = [UserWatchlistItem.owner_id == resolved_owner_id]
                if normalized_market:
                    conditions.append(UserWatchlistItem.market == normalized_market)
                if normalized_source:
                    conditions.append(UserWatchlistItem.source == normalized_source)
                if normalized_theme:
                    conditions.append(UserWatchlistItem.theme_id == normalized_theme)
                if normalized_symbols:
                    conditions.append(UserWatchlistItem.symbol.in_(sorted(normalized_symbols)))

                rows = session.execute(
                    select(UserWatchlistItem)
                    .where(and_(*conditions))
                    .order_by(UserWatchlistItem.market.asc(), UserWatchlistItem.symbol.asc())
                ).scalars().all()
                latest_by_pair = self.scanner_repo.get_latest_completed_candidates_by_market_symbol(
                    [(str(row.market), str(row.symbol)) for row in rows]
                )

                for row in rows:
                    markets.add(str(row.market))
                    latest = latest_by_pair.get((str(row.market), str(row.symbol)))

                    if latest is None:
                        row.score_status = "stale"
                        row.score_error = "No scanner candidate score is available for this symbol."
                        row.last_scored_at = started_at
                        skipped_count += 1
                        results.append({
                            "symbol": row.symbol,
                            "market": row.market,
                            "status": "stale",
                            "message": row.score_error,
                        })
                        continue

                    candidate, run = latest
                    row.scanner_run_id = int(run.id)
                    row.scanner_rank = int(candidate.rank)
                    row.scanner_score = float(candidate.score)
                    row.score_source = "scanner_run"
                    row.score_profile = str(run.profile or "")
                    row.score_reason = str(candidate.reason_summary or "")
                    row.score_status = "fresh"
                    row.score_error = None
                    row.last_scored_at = started_at
                    row.updated_at = started_at
                    updated_count += 1
                    results.append({
                        "symbol": row.symbol,
                        "market": row.market,
                        "status": "fresh",
                        "score": row.scanner_score,
                        "rank": row.scanner_rank,
                        "scanner_run_id": row.scanner_run_id,
                    })

                session.commit()
        finally:
            self.__class__._refresh_running = False
            self.__class__._refresh_lock.release()

        completed_at = datetime.now()
        return {
            "ok": failed_count == 0,
            "updated_count": updated_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "markets": sorted(markets),
            "results": results,
        }

    @classmethod
    def is_refresh_running(cls) -> bool:
        return bool(cls._refresh_running)

    def refresh_scores_for_all_users(
        self,
        *,
        market: Optional[str] = None,
        max_symbols: int = 250,
    ) -> Dict[str, Any]:
        normalized_market = self._normalize_market(market) if market else None
        started_at = datetime.now()
        summaries: List[Dict[str, Any]] = []
        with self.db.get_session() as session:
            owner_rows = session.execute(
                select(UserWatchlistItem.owner_id)
                .join(AppUser, AppUser.id == UserWatchlistItem.owner_id)
                .where(
                    and_(
                        AppUser.is_active.is_(True),
                        *( [UserWatchlistItem.market == normalized_market] if normalized_market else [] ),
                    )
                )
                .group_by(UserWatchlistItem.owner_id)
                .limit(max(1, int(max_symbols)))
            ).scalars().all()

        updated_count = 0
        failed_count = 0
        skipped_count = 0
        for owner_id in owner_rows:
            try:
                result = self.refresh_scores(owner_id=str(owner_id), market=normalized_market)
                summaries.append(result)
                updated_count += int(result.get("updated_count") or 0)
                failed_count += int(result.get("failed_count") or 0)
                skipped_count += int(result.get("skipped_count") or 0)
            except Exception as exc:
                failed_count += 1
                summaries.append({
                    "ok": False,
                    "owner_id": str(owner_id),
                    "message": str(exc),
                })

        return {
            "ok": failed_count == 0,
            "updated_count": updated_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now().isoformat(),
            "markets": [normalized_market] if normalized_market else sorted({market for item in summaries for market in item.get("markets", [])}),
            "results": summaries,
        }

    def remove_item(self, *, owner_id: str, item_id: int) -> bool:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            row = session.execute(
                select(UserWatchlistItem).where(
                    and_(
                        UserWatchlistItem.id == int(item_id),
                        UserWatchlistItem.owner_id == resolved_owner_id,
                    )
                ).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
