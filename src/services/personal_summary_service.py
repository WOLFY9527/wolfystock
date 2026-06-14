# -*- coding: utf-8 -*-
"""Pure projection service for a bounded personal summary contract."""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence

from api.v1.schemas.personal_summary import (
    PERSONAL_SUMMARY_NO_ADVICE_DISCLOSURE,
    PersonalSummaryDataQuality,
    PersonalSummaryPortfolioSnapshot,
    PersonalSummaryResearchCoverage,
    PersonalSummaryResponse,
    PersonalSummaryReviewQueue,
    PersonalSummaryReviewQueueItem,
    PersonalSummarySignalStatus,
    PersonalSummaryStatus,
    PersonalSummaryWatchlistException,
    PersonalSummaryWatchlistExceptions,
)


_SYMBOL_RE = re.compile(r"[A-Z0-9][A-Z0-9.\-]*")
_FORBIDDEN_TEXT_RE = re.compile(
    r"traceback|reasoncode|trustlevel|sourcetype|raw[_ ]?confidence|api[_ -]?key|"
    r"secret|token|session|provider error|/users/|buy now|sell now|place order|"
    r"broker execution|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|收益预测|ai推荐|智能选股|交易执行",
    re.IGNORECASE,
)
_NO_EVIDENCE_VALUES = {
    "",
    "missing",
    "missing_data",
    "missing_evidence",
    "no_data",
    "no_evidence",
    "insufficient",
    "insufficient_history",
    "unknown",
    "symbol_unknown",
}
_UNAVAILABLE_VALUES = {
    "data_failed",
    "error",
    "failed",
    "provider_down",
    "provider_error",
    "provider_unavailable",
    "calculation_unavailable",
    "unavailable",
}
_STALE_VALUES = {
    "cache_snapshot",
    "cached",
    "delayed",
    "expired",
    "partial",
    "stale",
    "stale_or_cached",
}
_REVIEW_VALUES = {"manual_review", "needs_review", "review"}
_OBSERVE_VALUES = {"observe", "observation", "watch"}
_NORMAL_VALUES = {"available", "complete", "completed", "fresh", "live", "normal", "ready"}
_SAMPLE_VALUES = {"example_data", "fixture", "sample", "sample_data"}
_MOVEMENT_VALUES = {"stronger", "weaker", "volume_expanded", "range_bound"}
_MAX_WATCHLIST_EXCEPTION_ITEMS = 5
_MAX_REVIEW_QUEUE_ITEMS = 5
_PRIORITY_ORDER = {
    "unavailable": 0,
    "no_evidence": 1,
    "stale": 2,
    "review": 3,
    "observe": 4,
    "weaker": 5,
    "stronger": 6,
    "volume_expanded": 7,
    "range_bound": 8,
    "sample_data": 9,
    "normal": 10,
}


class PersonalSummaryService:
    """Build a consumer-safe summary from existing safe portfolio/watchlist context."""

    def build_summary(
        self,
        *,
        portfolio_snapshot: Optional[Mapping[str, Any]] = None,
        watchlist_items: Optional[Sequence[Mapping[str, Any]]] = None,
        portfolio_connected: Optional[bool] = None,
        sample_data: bool = False,
        portfolio_status: Optional[str] = None,
        watchlist_status: Optional[str] = None,
    ) -> PersonalSummaryResponse:
        raw_watchlist = [item for item in (watchlist_items or []) if isinstance(item, Mapping)]
        ranked_watchlist_exceptions = self._collect_watchlist_exceptions(raw_watchlist)
        portfolio_component_status = self._portfolio_component_status(
            portfolio_snapshot=portfolio_snapshot,
            portfolio_connected=portfolio_connected,
            sample_data=sample_data,
            portfolio_status=portfolio_status,
        )
        portfolio_model = self._build_portfolio_snapshot(
            portfolio_snapshot=portfolio_snapshot,
            portfolio_connected=portfolio_connected,
            sample_data=sample_data,
        )
        watchlist_model = self._build_watchlist_exceptions(
            ranked_watchlist_exceptions,
            items_present=bool(raw_watchlist),
            watchlist_status=watchlist_status,
        )
        research_model = self._build_research_coverage(raw_watchlist)
        review_queue = self._build_review_queue(
            ranked_watchlist_exceptions,
            watchlist_status=watchlist_model.status,
        )
        data_quality = self._build_data_quality(
            portfolio_status=portfolio_component_status,
            watchlist_status=watchlist_model.status,
            research_status=research_model.status,
            sample_data=sample_data or portfolio_model.sampleData,
            connected=portfolio_model.connected,
        )
        return PersonalSummaryResponse(
            status=self._combine_component_statuses(
                portfolio_component_status,
                watchlist_model.status,
                research_model.status,
            ),
            portfolioSnapshot=portfolio_model,
            watchlistExceptions=watchlist_model,
            researchCoverage=research_model,
            reviewQueue=review_queue,
            dataQuality=data_quality,
            noAdviceDisclosure=PERSONAL_SUMMARY_NO_ADVICE_DISCLOSURE,
        )

    def _collect_watchlist_exceptions(
        self,
        items: Sequence[Mapping[str, Any]],
    ) -> list[PersonalSummaryWatchlistException]:
        deduped: dict[str, list[PersonalSummaryWatchlistException]] = {}
        for item in items:
            projected_item = self._project_watchlist_exception(item)
            if projected_item is None:
                continue
            deduped.setdefault(projected_item.symbol, []).append(projected_item)

        ranked_items = [self._merge_watchlist_exception_group(group) for group in deduped.values()]
        ranked_items.sort(key=self._exception_sort_key)
        return ranked_items

    def _build_portfolio_snapshot(
        self,
        *,
        portfolio_snapshot: Optional[Mapping[str, Any]],
        portfolio_connected: Optional[bool],
        sample_data: bool,
    ) -> PersonalSummaryPortfolioSnapshot:
        snapshot = portfolio_snapshot if isinstance(portfolio_snapshot, Mapping) else {}
        connected = self._resolve_connected(snapshot, explicit=portfolio_connected)
        snapshot_sample_data = bool(sample_data or self._bool_value(self._lookup(snapshot, "sampleData", "sample_data")))
        risk_status = self._normalize_signal_status(
            self._lookup(snapshot, "riskStatus", "risk_status"),
            default="sample_data" if snapshot_sample_data else "no_evidence",
        )
        concentration_status = self._normalize_signal_status(
            self._lookup(snapshot, "concentrationStatus", "concentration_status"),
            default="sample_data" if snapshot_sample_data else "no_evidence",
        )
        return PersonalSummaryPortfolioSnapshot(
            totalValue=self._float_value(
                self._lookup(snapshot, "totalValue", "total_equity", "totalEquity", "total_market_value", "totalMarketValue")
            ),
            dailyChange=self._float_value(self._lookup(snapshot, "dailyChange", "daily_change")),
            cashPercent=self._portfolio_cash_percent(snapshot),
            largestExposure=self._portfolio_largest_exposure(snapshot),
            beta=self._float_value(self._lookup(snapshot, "beta")),
            riskScore=self._float_value(self._lookup(snapshot, "riskScore", "risk_score")),
            riskStatus=risk_status,
            concentrationStatus=concentration_status,
            connected=connected,
            sampleData=snapshot_sample_data,
        )

    def _build_watchlist_exceptions(
        self,
        items: Sequence[PersonalSummaryWatchlistException],
        *,
        items_present: bool,
        watchlist_status: Optional[str],
    ) -> PersonalSummaryWatchlistExceptions:
        stale_count = 0
        no_evidence_count = 0
        for item in items:
            if "stale" in {
                item.symbolStatus,
                item.evidenceStatus,
                item.researchStatus,
            }:
                stale_count += 1
            if "no_evidence" in {
                item.symbolStatus,
                item.evidenceStatus,
                item.researchStatus,
            }:
                no_evidence_count += 1

        if watchlist_status:
            status = self._normalize_component_status(watchlist_status, default="no_evidence")
        elif items:
            status = self._watchlist_items_status(items)
        elif items_present:
            status = "ready"
        else:
            status = "no_evidence"

        return PersonalSummaryWatchlistExceptions(
            status=status,
            items=list(items[:_MAX_WATCHLIST_EXCEPTION_ITEMS]),
            staleCount=stale_count,
            noEvidenceCount=no_evidence_count,
        )

    def _project_watchlist_exception(
        self,
        item: Mapping[str, Any],
    ) -> Optional[PersonalSummaryWatchlistException]:
        symbol = self._sanitize_symbol(self._lookup(item, "symbol"))
        if symbol is None:
            return None
        display_name = self._sanitize_display_name(self._lookup(item, "displayName", "display_name", "name"), symbol)
        symbol_status = self._normalize_signal_status(
            self._lookup(item, "symbolStatus", "symbol_status"),
            default="normal",
        )
        movement_status = self._normalize_signal_status(
            self._lookup(item, "movementStatus", "movement_status"),
            default="normal",
        )
        relative_strength_status = self._normalize_signal_status(
            self._lookup(item, "relativeStrengthStatus", "relative_strength_status"),
            default="normal",
        )
        volume_status = self._normalize_signal_status(
            self._lookup(item, "volumeStatus", "volume_status"),
            default="normal",
        )
        evidence_status = self._normalize_signal_status(
            self._lookup(item, "evidenceStatus", "evidence_status", "data_quality", "dataQuality"),
            default="normal",
        )
        research_status = self._normalize_signal_status(
            self._lookup(item, "researchStatus", "research_status"),
            default="normal",
        )
        review_reason = self._sanitize_reason(
            self._lookup(item, "reviewReason", "review_reason", "score_reason"),
            default=self._default_review_reason(
                symbol_status=symbol_status,
                movement_status=movement_status,
                relative_strength_status=relative_strength_status,
                volume_status=volume_status,
                evidence_status=evidence_status,
                research_status=research_status,
            ),
        )
        projected = PersonalSummaryWatchlistException(
            symbol=symbol,
            displayName=display_name,
            symbolStatus=symbol_status,
            movementStatus=movement_status,
            relativeStrengthStatus=relative_strength_status,
            volumeStatus=volume_status,
            evidenceStatus=evidence_status,
            researchStatus=research_status,
            lastReviewedAt=self._sanitize_metadata_text(self._lookup(item, "lastReviewedAt", "last_reviewed_at")),
            reviewReason=review_reason,
        )
        return projected if self._is_exception(projected) else None

    def _build_research_coverage(
        self,
        items: Sequence[Mapping[str, Any]],
    ) -> PersonalSummaryResearchCoverage:
        missing_symbols: list[str] = []
        stale_symbols: list[str] = []
        covered_symbols: list[str] = []

        for item in items:
            symbol = self._sanitize_symbol(self._lookup(item, "symbol"))
            if symbol is None:
                continue
            research_status = self._normalize_signal_status(
                self._lookup(item, "researchStatus", "research_status"),
                default="no_evidence",
            )
            evidence_status = self._normalize_signal_status(
                self._lookup(item, "evidenceStatus", "evidence_status", "data_quality", "dataQuality"),
                default="no_evidence",
            )
            if "no_evidence" in {research_status, evidence_status}:
                missing_symbols.append(symbol)
                continue
            if "stale" in {research_status, evidence_status}:
                stale_symbols.append(symbol)
                continue
            if "unavailable" not in {research_status, evidence_status}:
                covered_symbols.append(symbol)

        status = self._coverage_status(
            items_present=bool(items),
            missing_symbols=missing_symbols,
            stale_symbols=stale_symbols,
            covered_symbols=covered_symbols,
        )
        return PersonalSummaryResearchCoverage(
            status=status,
            missingSymbols=missing_symbols,
            staleSymbols=stale_symbols,
            coveredSymbols=covered_symbols,
        )

    def _build_review_queue(
        self,
        items: Sequence[PersonalSummaryWatchlistException],
        *,
        watchlist_status: PersonalSummaryStatus,
    ) -> PersonalSummaryReviewQueue:
        queue_items = [
            PersonalSummaryReviewQueueItem(
                symbol=item.symbol,
                displayName=item.displayName,
                priorityStatus=self._priority_status(item),
                evidenceStatus=item.evidenceStatus,
                researchStatus=item.researchStatus,
                lastReviewedAt=item.lastReviewedAt,
                reviewReason=item.reviewReason,
            )
            for item in items
        ]
        queue_items.sort(key=lambda item: (_PRIORITY_ORDER.get(item.priorityStatus, 99), item.symbol))
        queue_items = queue_items[:_MAX_REVIEW_QUEUE_ITEMS]
        if queue_items:
            status: PersonalSummaryStatus = "partial"
        elif watchlist_status == "ready":
            status = "ready"
        else:
            status = watchlist_status
        return PersonalSummaryReviewQueue(status=status, items=queue_items)

    def _build_data_quality(
        self,
        *,
        portfolio_status: PersonalSummaryStatus,
        watchlist_status: PersonalSummaryStatus,
        research_status: PersonalSummaryStatus,
        sample_data: bool,
        connected: bool,
    ) -> PersonalSummaryDataQuality:
        overall_status = self._combine_component_statuses(portfolio_status, watchlist_status, research_status)
        return PersonalSummaryDataQuality(
            status=overall_status,
            portfolioStatus=portfolio_status,
            watchlistStatus=watchlist_status,
            researchStatus=research_status,
            sampleData=sample_data,
            connected=connected,
        )

    def _portfolio_component_status(
        self,
        *,
        portfolio_snapshot: Optional[Mapping[str, Any]],
        portfolio_connected: Optional[bool],
        sample_data: bool,
        portfolio_status: Optional[str],
    ) -> PersonalSummaryStatus:
        if portfolio_status:
            return self._normalize_component_status(portfolio_status, default="no_evidence")
        snapshot = portfolio_snapshot if isinstance(portfolio_snapshot, Mapping) else {}
        if sample_data or self._bool_value(self._lookup(snapshot, "sampleData", "sample_data")):
            return "no_evidence"
        data_status = self._text_value(self._lookup(snapshot, "data_status", "dataStatus"))
        if data_status in _UNAVAILABLE_VALUES:
            return "unavailable"
        if data_status in _STALE_VALUES:
            return "partial"
        connected = self._resolve_connected(snapshot, explicit=portfolio_connected)
        if not connected:
            return "no_evidence"
        if snapshot:
            return "ready"
        return "no_evidence"

    def _watchlist_items_status(
        self,
        items: Sequence[PersonalSummaryWatchlistException],
    ) -> PersonalSummaryStatus:
        severity = {
            status
            for item in items
            for status in (
                item.symbolStatus,
                item.movementStatus,
                item.relativeStrengthStatus,
                item.volumeStatus,
                item.evidenceStatus,
                item.researchStatus,
            )
        }
        if "unavailable" in severity and len(severity) == 1:
            return "unavailable"
        if "no_evidence" in severity and severity <= {"no_evidence", "normal"}:
            return "no_evidence"
        if severity & {"review", "observe", "stale", "stronger", "weaker", "volume_expanded", "range_bound", "sample_data", "no_evidence", "unavailable"}:
            return "partial"
        return "ready"

    def _coverage_status(
        self,
        *,
        items_present: bool,
        missing_symbols: Sequence[str],
        stale_symbols: Sequence[str],
        covered_symbols: Sequence[str],
    ) -> PersonalSummaryStatus:
        if not items_present:
            return "no_evidence"
        if missing_symbols and not stale_symbols and not covered_symbols:
            return "no_evidence"
        if stale_symbols or (missing_symbols and covered_symbols):
            return "partial"
        if covered_symbols:
            return "ready"
        return "unavailable" if items_present else "no_evidence"

    @staticmethod
    def _combine_component_statuses(*statuses: PersonalSummaryStatus) -> PersonalSummaryStatus:
        normalized = [status for status in statuses if status]
        if not normalized:
            return "no_evidence"
        if any(status == "partial" for status in normalized):
            return "partial"
        if any(status == "ready" for status in normalized) and any(status in {"no_evidence", "unavailable"} for status in normalized):
            return "partial"
        if all(status == "ready" for status in normalized):
            return "ready"
        if any(status == "no_evidence" for status in normalized):
            return "no_evidence"
        return "unavailable"

    @staticmethod
    def _lookup(payload: Mapping[str, Any], *keys: str) -> Any:
        for key in keys:
            if not isinstance(payload, Mapping):
                return None
            if key in payload:
                return payload.get(key)
        return None

    @classmethod
    def _portfolio_cash_percent(cls, snapshot: Mapping[str, Any]) -> Optional[float]:
        direct = cls._float_value(cls._lookup(snapshot, "cashPercent", "cash_percent"))
        if direct is not None:
            return direct
        analytics = snapshot.get("analytics")
        if isinstance(analytics, Mapping):
            risk = analytics.get("risk")
            if isinstance(risk, Mapping):
                return cls._float_value(cls._lookup(risk, "cashPercent", "cash_percent"))
        return None

    @classmethod
    def _portfolio_largest_exposure(cls, snapshot: Mapping[str, Any]) -> Optional[float]:
        direct = cls._float_value(cls._lookup(snapshot, "largestExposure", "largest_exposure"))
        if direct is not None:
            return direct
        analytics = snapshot.get("analytics")
        if isinstance(analytics, Mapping):
            risk = analytics.get("risk")
            if isinstance(risk, Mapping):
                largest_position = risk.get("largest_position") or risk.get("largestPosition")
                if isinstance(largest_position, Mapping):
                    return cls._float_value(cls._lookup(largest_position, "percent", "weight_pct", "weightPct"))
        return None

    @classmethod
    def _resolve_connected(cls, snapshot: Mapping[str, Any], *, explicit: Optional[bool]) -> bool:
        if explicit is not None:
            return bool(explicit)
        availability = snapshot.get("availability")
        if isinstance(availability, Mapping) and availability.get("connected") is not None:
            return bool(availability.get("connected"))
        account_count = cls._float_value(cls._lookup(snapshot, "account_count", "accountCount"))
        if account_count is not None:
            return account_count > 0
        data_status = cls._text_value(cls._lookup(snapshot, "data_status", "dataStatus"))
        return data_status not in {"no_account", "provider_unavailable", "data_unavailable"}

    @classmethod
    def _normalize_signal_status(cls, value: Any, *, default: PersonalSummarySignalStatus) -> PersonalSummarySignalStatus:
        text = cls._text_value(value)
        if not text:
            return default
        if text in _SAMPLE_VALUES:
            return "sample_data"
        if text in _MOVEMENT_VALUES:
            return text  # type: ignore[return-value]
        if text in _REVIEW_VALUES:
            return "review"
        if text in _OBSERVE_VALUES:
            return "observe"
        if text in _UNAVAILABLE_VALUES:
            return "unavailable"
        if text in _STALE_VALUES:
            return "stale"
        if text in _NO_EVIDENCE_VALUES:
            return "no_evidence"
        if text in _NORMAL_VALUES:
            return "normal"
        return default

    @classmethod
    def _normalize_component_status(cls, value: Any, *, default: PersonalSummaryStatus) -> PersonalSummaryStatus:
        text = cls._text_value(value)
        if text == "ready":
            return "ready"
        if text == "partial":
            return "partial"
        if text == "unavailable":
            return "unavailable"
        if text == "no_evidence":
            return "no_evidence"
        if text in _UNAVAILABLE_VALUES:
            return "unavailable"
        if text in _STALE_VALUES:
            return "partial"
        if text in _NO_EVIDENCE_VALUES | _SAMPLE_VALUES:
            return "no_evidence"
        if text in _NORMAL_VALUES:
            return "ready"
        return default

    @classmethod
    def _priority_status(cls, item: PersonalSummaryWatchlistException) -> PersonalSummarySignalStatus:
        statuses = [
            item.symbolStatus,
            item.evidenceStatus,
            item.researchStatus,
            item.movementStatus,
            item.relativeStrengthStatus,
            item.volumeStatus,
        ]
        return min(statuses, key=lambda status: _PRIORITY_ORDER.get(status, 99))

    @classmethod
    def _exception_sort_key(cls, item: PersonalSummaryWatchlistException) -> tuple[Any, ...]:
        return (
            _PRIORITY_ORDER.get(cls._priority_status(item), 99),
            _PRIORITY_ORDER.get(item.symbolStatus, 99),
            _PRIORITY_ORDER.get(item.evidenceStatus, 99),
            _PRIORITY_ORDER.get(item.researchStatus, 99),
            _PRIORITY_ORDER.get(item.movementStatus, 99),
            _PRIORITY_ORDER.get(item.relativeStrengthStatus, 99),
            _PRIORITY_ORDER.get(item.volumeStatus, 99),
            item.symbol,
            item.reviewReason or "",
        )

    @staticmethod
    def _is_exception(item: PersonalSummaryWatchlistException) -> bool:
        return any(
            status != "normal"
            for status in (
                item.symbolStatus,
                item.movementStatus,
                item.relativeStrengthStatus,
                item.volumeStatus,
                item.evidenceStatus,
                item.researchStatus,
            )
        ) or bool(item.reviewReason)

    @classmethod
    def _merge_watchlist_exception_group(
        cls,
        items: Sequence[PersonalSummaryWatchlistException],
    ) -> PersonalSummaryWatchlistException:
        ordered_items = sorted(items, key=cls._exception_sort_key)
        primary_item = ordered_items[0]
        symbol_status = cls._worst_status(item.symbolStatus for item in items)
        movement_status = cls._worst_status(item.movementStatus for item in items)
        relative_strength_status = cls._worst_status(item.relativeStrengthStatus for item in items)
        volume_status = cls._worst_status(item.volumeStatus for item in items)
        evidence_status = cls._worst_status(item.evidenceStatus for item in items)
        research_status = cls._worst_status(item.researchStatus for item in items)
        default_reason = cls._default_review_reason(
            symbol_status=symbol_status,
            movement_status=movement_status,
            relative_strength_status=relative_strength_status,
            volume_status=volume_status,
            evidence_status=evidence_status,
            research_status=research_status,
        )
        return PersonalSummaryWatchlistException(
            symbol=primary_item.symbol,
            displayName=cls._preferred_display_name(ordered_items),
            symbolStatus=symbol_status,
            movementStatus=movement_status,
            relativeStrengthStatus=relative_strength_status,
            volumeStatus=volume_status,
            evidenceStatus=evidence_status,
            researchStatus=research_status,
            lastReviewedAt=cls._preferred_last_reviewed_at(ordered_items),
            reviewReason=cls._merge_review_reasons(ordered_items, default=default_reason),
        )

    @classmethod
    def _worst_status(
        cls,
        statuses: Sequence[PersonalSummarySignalStatus] | Any,
    ) -> PersonalSummarySignalStatus:
        return min(statuses, key=lambda status: _PRIORITY_ORDER.get(status, 99))

    @staticmethod
    def _default_review_reason(
        *,
        symbol_status: PersonalSummarySignalStatus,
        movement_status: PersonalSummarySignalStatus,
        relative_strength_status: PersonalSummarySignalStatus,
        volume_status: PersonalSummarySignalStatus,
        evidence_status: PersonalSummarySignalStatus,
        research_status: PersonalSummarySignalStatus,
    ) -> Optional[str]:
        statuses = {
            symbol_status,
            movement_status,
            relative_strength_status,
            volume_status,
            evidence_status,
            research_status,
        }
        if "unavailable" in statuses:
            return "Research context unavailable."
        if "no_evidence" in statuses:
            return "Research evidence missing."
        if "stale" in statuses:
            return "Research evidence is stale."
        if "review" in statuses:
            return "Review evidence changed."
        if statuses & {"observe", "stronger", "weaker", "volume_expanded", "range_bound"}:
            return "Watchlist item needs observation."
        if "sample_data" in statuses:
            return "Sample data only."
        return None

    @classmethod
    def _preferred_display_name(
        cls,
        items: Sequence[PersonalSummaryWatchlistException],
    ) -> Optional[str]:
        for item in items:
            if item.displayName and item.displayName != item.symbol:
                return item.displayName
        return items[0].displayName if items else None

    @classmethod
    def _preferred_last_reviewed_at(
        cls,
        items: Sequence[PersonalSummaryWatchlistException],
    ) -> Optional[str]:
        values = [item.lastReviewedAt for item in items if item.lastReviewedAt]
        return max(values) if values else None

    @classmethod
    def _merge_review_reasons(
        cls,
        items: Sequence[PersonalSummaryWatchlistException],
        *,
        default: Optional[str],
    ) -> Optional[str]:
        deduped_reasons: list[str] = []
        seen: set[str] = set()
        for item in items:
            reason = cls._sanitize_reason(item.reviewReason, default=None)
            if reason is None:
                continue
            reason_key = reason.casefold()
            if reason_key in seen:
                continue
            deduped_reasons.append(reason)
            seen.add(reason_key)
        if deduped_reasons:
            return "; ".join(deduped_reasons[:2])
        return default

    @classmethod
    def _sanitize_symbol(cls, value: Any) -> Optional[str]:
        text = cls._safe_text(value)
        if text is None:
            return None
        normalized = text.strip().upper()
        return normalized if _SYMBOL_RE.fullmatch(normalized) else None

    @classmethod
    def _sanitize_display_name(cls, value: Any, symbol: str) -> Optional[str]:
        text = cls._safe_text(value)
        if text is None:
            return symbol
        if _FORBIDDEN_TEXT_RE.search(text):
            return symbol
        return text

    @classmethod
    def _sanitize_reason(cls, value: Any, *, default: Optional[str]) -> Optional[str]:
        text = cls._safe_text(value)
        if text is None:
            return default
        if _FORBIDDEN_TEXT_RE.search(text):
            return default
        return text

    @staticmethod
    def _text_value(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _safe_text(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        return text or None

    @classmethod
    def _sanitize_metadata_text(cls, value: Any) -> Optional[str]:
        text = cls._safe_text(value)
        if text is None:
            return None
        if _FORBIDDEN_TEXT_RE.search(text):
            return None
        return text

    @staticmethod
    def _float_value(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number == number else None

    @staticmethod
    def _bool_value(value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes"}:
            return True
        if text in {"0", "false", "no"}:
            return False
        return None
