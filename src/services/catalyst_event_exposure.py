# -*- coding: utf-8 -*-
"""Pure catalyst exposure projection from already-available evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence


MAX_NEWS_PROXY_ITEMS = 3
_SUMMARY_LIMIT = 220
_TITLE_LIMIT = 120


@dataclass(frozen=True)
class CatalystEventExposureItem:
    id: str
    symbol: str
    market: str
    category: str
    title: str
    summary: str
    evidence_status: str
    evidence_labels: tuple[str, ...]
    source: str
    as_of: str | None
    reason_codes: tuple[str, ...]
    timeframe: str | None = None
    published_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "symbol": self.symbol,
            "market": self.market,
            "category": self.category,
            "title": self.title,
            "summary": self.summary,
            "evidenceStatus": self.evidence_status,
            "evidenceLabels": list(self.evidence_labels),
            "source": self.source,
            "observationOnly": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "decisionGrade": False,
            "calendarClaimAllowed": False,
            "investmentAdviceAllowed": False,
            "reasonCodes": list(self.reason_codes),
        }
        if self.as_of:
            payload["asOf"] = self.as_of
        if self.timeframe:
            payload["timeframe"] = self.timeframe
        if self.published_at:
            payload["publishedAt"] = self.published_at
        return payload


def build_catalyst_event_exposures(
    *,
    symbol: str,
    market: str,
    as_of: datetime | date | str | None = None,
    fundamental_snapshot: object | None = None,
    stored_news_items: object | None = None,
    official_macro_status: object | None = None,
) -> tuple[CatalystEventExposureItem, ...]:
    items: list[CatalystEventExposureItem] = []
    normalized_symbol = _normalize_symbol(symbol)
    normalized_market = _normalize_market(market)
    fallback_as_of = _as_text_time(as_of)

    fundamental_item = _fundamental_exposure(
        symbol=normalized_symbol,
        market=normalized_market,
        fallback_as_of=fallback_as_of,
        payload=fundamental_snapshot,
    )
    if fundamental_item is not None:
        items.append(fundamental_item)

    items.extend(
        _news_proxy_exposures(
            symbol=normalized_symbol,
            market=normalized_market,
            fallback_as_of=fallback_as_of,
            payload=stored_news_items,
        )
    )

    macro_item = _macro_status_exposure(
        symbol=normalized_symbol,
        market=normalized_market,
        fallback_as_of=fallback_as_of,
        payload=official_macro_status,
    )
    if macro_item is not None:
        items.append(macro_item)

    return tuple(items)


def _fundamental_exposure(
    *,
    symbol: str,
    market: str,
    fallback_as_of: str | None,
    payload: object | None,
) -> CatalystEventExposureItem | None:
    snapshot = _nested_mapping(
        payload,
        "earnings",
        "earningsSnapshot",
        "earnings_outlook",
        "earningsOutlook",
        "fundamental",
        "fundamentalSnapshot",
    )
    if snapshot is None:
        return None

    stale = _is_stale(snapshot)
    labels = ("stale", "unverified") if stale else ("delayed",)
    reason_codes = _reason_codes(
        "observation_only",
        "fundamental_snapshot_present",
        "not_earnings_calendar",
        "stale_evidence" if stale else "delayed_evidence",
    )
    timeframe = _first_text(
        snapshot,
        "reportedPeriod",
        "reported_period",
        "fiscalPeriod",
        "fiscal_period",
        "period",
        "quarter",
    )
    source_summary = _first_text(snapshot, "summary", "earningsSummary", "fundamentalSummary", "outlook")
    summary_parts = []
    if timeframe:
        summary_parts.append(f"Snapshot period: {timeframe}.")
    if source_summary:
        summary_parts.append(source_summary)
    if not summary_parts:
        summary_parts.append("Fundamental snapshot evidence is present for catalyst context only.")

    return CatalystEventExposureItem(
        id=f"catalyst:{symbol}:{market}:fundamental",
        symbol=symbol,
        market=market,
        category="earnings_fundamental_snapshot",
        title="Fundamental snapshot exposure",
        summary=_safe_text(" ".join(summary_parts), limit=_SUMMARY_LIMIT),
        evidence_status="stale" if stale else "delayed",
        evidence_labels=labels,
        source="fundamental_snapshot",
        as_of=_first_time(snapshot, "asOf", "as_of", "updatedAt", "updated_at") or fallback_as_of,
        reason_codes=reason_codes,
        timeframe=timeframe,
    )


def _news_proxy_exposures(
    *,
    symbol: str,
    market: str,
    fallback_as_of: str | None,
    payload: object | None,
) -> tuple[CatalystEventExposureItem, ...]:
    news_items = _news_sequence(payload)
    exposures: list[CatalystEventExposureItem] = []
    for index, news_item in enumerate(news_items[:MAX_NEWS_PROXY_ITEMS], start=1):
        headline = _first_text(news_item, "headline", "title", "name")
        summary = _first_text(news_item, "summary", "description", "snippet", "abstract")
        if not headline and not summary:
            continue

        stale = _is_stale(news_item)
        labels = ("stale", "proxy", "unverified") if stale else ("proxy", "unverified")
        reason_codes = _reason_codes(
            "observation_only",
            "stored_news_catalyst_proxy",
            "proxy_evidence_not_authoritative",
            "stale_evidence" if stale else None,
        )
        title = headline or "Stored news catalyst proxy"
        body = summary or "Stored news evidence is available as a catalyst proxy only."

        exposures.append(
            CatalystEventExposureItem(
                id=f"catalyst:{symbol}:{market}:news:{index}",
                symbol=symbol,
                market=market,
                category="stored_news_catalyst_proxy",
                title=_safe_text(title, limit=_TITLE_LIMIT),
                summary=_safe_text(body, limit=_SUMMARY_LIMIT),
                evidence_status="stale" if stale else "proxy",
                evidence_labels=labels,
                source="stored_news_cache_proxy",
                as_of=_first_time(news_item, "asOf", "as_of", "updatedAt", "updated_at") or fallback_as_of,
                reason_codes=reason_codes,
                published_at=_first_time(news_item, "publishedAt", "published_at", "date", "datetime"),
            )
        )
    return tuple(exposures)


def _macro_status_exposure(
    *,
    symbol: str,
    market: str,
    fallback_as_of: str | None,
    payload: object | None,
) -> CatalystEventExposureItem | None:
    status_payload = _as_mapping_like(payload)
    if status_payload is None or not status_payload:
        return None

    stale = _is_stale(status_payload)
    labels = ("stale",) if stale else ("delayed",)
    reason_codes = _reason_codes(
        "observation_only",
        "official_macro_cache_status_present",
        "stale_evidence" if stale else "delayed_evidence",
    )
    status_text = _first_text(status_payload, "status", "freshness", "freshnessStatus") or "available"
    observed_series = _macro_series_labels(status_payload)
    series_clause = f" Observed cached signals: {', '.join(observed_series)}." if observed_series else ""

    return CatalystEventExposureItem(
        id=f"catalyst:{symbol}:{market}:macro",
        symbol=symbol,
        market=market,
        category="official_macro_cache_status",
        title="Official macro cache/status exposure",
        summary=_safe_text(
            f"Official macro cache/status is {status_text} as diagnostic context only;"
            f" no scheduled macro calendar authority is inferred.{series_clause}",
            limit=_SUMMARY_LIMIT,
        ),
        evidence_status="stale" if stale else "delayed",
        evidence_labels=labels,
        source="official_macro_cache_status",
        as_of=_first_time(status_payload, "asOf", "as_of", "updatedAt", "updated_at") or fallback_as_of,
        reason_codes=reason_codes,
    )


def _nested_mapping(payload: object | None, *candidate_keys: str) -> object | None:
    if _has_observable_content(payload):
        for key in candidate_keys:
            candidate = _get_value(payload, key)
            if _has_observable_content(candidate):
                return candidate
        return payload
    return None


def _news_sequence(payload: object | None) -> tuple[object, ...]:
    if payload is None:
        return ()
    for key in ("items", "news", "articles", "headlines"):
        candidate = _get_value(payload, key)
        sequence = _as_non_text_sequence(candidate)
        if sequence:
            return sequence
    sequence = _as_non_text_sequence(payload)
    if sequence:
        return sequence
    return (payload,) if _has_observable_content(payload) else ()


def _macro_series_labels(payload: object) -> tuple[str, ...]:
    series_payload = None
    for key in ("series", "items", "observations"):
        candidate = _get_value(payload, key)
        if _as_non_text_sequence(candidate):
            series_payload = candidate
            break
    labels: list[str] = []
    for item in _as_non_text_sequence(series_payload)[:5]:
        label = _first_text(item, "symbol", "name", "label")
        if label and label not in labels:
            labels.append(label)
    return tuple(labels)


def _is_stale(payload: object) -> bool:
    for key in ("stale", "isStale", "expired", "isExpired"):
        value = _get_value(payload, key)
        if isinstance(value, bool) and value:
            return True
    for key in ("freshness", "freshnessStatus", "freshness_status", "status", "label"):
        value = _safe_text(_get_value(payload, key), limit=40).casefold()
        if any(token in value for token in ("stale", "expired", "fallback", "unavailable")):
            return True
    reason_codes = _as_non_text_sequence(_get_value(payload, "reasonCodes") or _get_value(payload, "reason_codes"))
    return any("stale" in _safe_text(reason, limit=80).casefold() for reason in reason_codes)


def _reason_codes(*codes: str | None) -> tuple[str, ...]:
    deduped: list[str] = []
    for code in codes:
        if not code or code in deduped:
            continue
        deduped.append(code)
    return tuple(deduped)


def _first_text(payload: object, *keys: str) -> str | None:
    for key in keys:
        value = _safe_text(_get_value(payload, key))
        if value:
            return value
    return None


def _first_time(payload: object, *keys: str) -> str | None:
    for key in keys:
        value = _as_text_time(_get_value(payload, key))
        if value:
            return value
    return None


def _as_text_time(value: object | None) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return _safe_text(value, limit=80)


def _safe_text(value: object | None, *, limit: int = _SUMMARY_LIMIT) -> str:
    if value is None or isinstance(value, (Mapping, list, tuple, set)):
        return ""
    text = " ".join(str(value).strip().split())
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _normalize_symbol(value: object) -> str:
    normalized = _safe_text(value, limit=32).upper()
    return normalized or "UNKNOWN"


def _normalize_market(value: object) -> str:
    normalized = _safe_text(value, limit=32).lower()
    return normalized or "unknown"


def _has_observable_content(payload: object | None) -> bool:
    if payload is None:
        return False
    mapping = _as_mapping_like(payload)
    if mapping is not None:
        return any(value is not None and value != "" and value != [] and value != {} for value in mapping.values())
    sequence = _as_non_text_sequence(payload)
    if sequence:
        return True
    return bool(_safe_text(payload))


def _as_mapping_like(payload: object | None) -> Mapping[str, Any] | None:
    if isinstance(payload, Mapping):
        return payload
    if payload is None or isinstance(payload, (str, bytes, bytearray)):
        return None
    attrs = getattr(payload, "__dict__", None)
    if isinstance(attrs, Mapping):
        return attrs
    return None


def _as_non_text_sequence(payload: object | None) -> tuple[object, ...]:
    if payload is None or isinstance(payload, (str, bytes, bytearray, Mapping)):
        return ()
    if isinstance(payload, Sequence):
        return tuple(payload)
    return ()


def _get_value(payload: object | None, key: str) -> object | None:
    if isinstance(payload, Mapping):
        if key in payload:
            return payload[key]
        return None
    if payload is None or isinstance(payload, (str, bytes, bytearray)):
        return None
    return getattr(payload, key, None)


__all__ = [
    "CatalystEventExposureItem",
    "MAX_NEWS_PROXY_ITEMS",
    "build_catalyst_event_exposures",
]
