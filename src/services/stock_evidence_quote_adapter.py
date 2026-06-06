# -*- coding: utf-8 -*-
"""Evidence-only adapter for realtime quote access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from data_provider.base import DataFetcherManager
from data_provider.realtime_types import UnifiedRealtimeQuote
from src.services.source_confidence_contract import (
    SourceConfidenceContract,
    SourceFreshness,
    coerce_source_confidence_contract,
)


_FRESHNESS_NOT_PROVEN_REASON = "freshness_not_proven"


def _quote_source_token(source: Any) -> str:
    value = str(source or "").strip()
    return value or "realtime_quote"


def _quote_source_label(source: str) -> str:
    return source or "realtime_quote"


def _quote_diagnostic_freshness(
    *,
    source: str,
    is_partial: bool,
    is_unavailable: bool,
) -> SourceFreshness:
    source_token = source.lower()
    if is_unavailable:
        return SourceFreshness.UNAVAILABLE
    if source_token == "fallback" or source_token.endswith("_fallback"):
        return SourceFreshness.FALLBACK
    if "synthetic" in source_token or source_token in {"mock", "fixture", "unit_fixture"}:
        return SourceFreshness.SYNTHETIC
    if is_partial:
        return SourceFreshness.PARTIAL
    return SourceFreshness.UNKNOWN


def _quote_source_type(*, source: str, freshness: SourceFreshness) -> str:
    if freshness is SourceFreshness.UNAVAILABLE:
        return "missing"
    if freshness is SourceFreshness.FALLBACK:
        return "fallback"
    if freshness is SourceFreshness.SYNTHETIC:
        return "synthetic"
    return "local_or_reported"


def build_quote_diagnostic_source_metadata(
    *,
    source: Any,
    as_of: Optional[str],
    is_partial: bool = False,
    is_unavailable: bool = False,
) -> Dict[str, Any]:
    """Project quote provenance into diagnostic-only source-confidence metadata."""

    source_token = _quote_source_token(source)
    freshness = _quote_diagnostic_freshness(
        source=source_token,
        is_partial=is_partial,
        is_unavailable=is_unavailable,
    )
    unknown_reason = _FRESHNESS_NOT_PROVEN_REASON if freshness is SourceFreshness.UNKNOWN else None
    source_confidence = coerce_source_confidence_contract(
        SourceConfidenceContract(
            source=source_token,
            source_label=_quote_source_label(source_token),
            as_of=as_of,
            freshness=freshness,
            is_partial=is_partial,
            is_unavailable=is_unavailable,
            confidence_weight=0.0 if is_unavailable else 0.4 if freshness is SourceFreshness.FALLBACK else 0.3,
            coverage=0.0 if is_unavailable else 1.0,
            degradation_reason=unknown_reason,
            cap_reason=unknown_reason,
        )
    )
    confidence_payload = source_confidence.to_dict()
    metadata: Dict[str, Any] = {
        "source": source_token,
        "sourceType": _quote_source_type(source=source_token, freshness=source_confidence.freshness),
        "freshness": source_confidence.freshness.value,
        "asOf": source_confidence.as_of,
        "degradationReason": source_confidence.degradation_reason,
        "isFallback": source_confidence.is_fallback,
        "isStale": source_confidence.is_stale,
        "isPartial": source_confidence.is_partial,
        "isSynthetic": source_confidence.is_synthetic,
        "isUnavailable": source_confidence.is_unavailable,
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "sourceAuthorityAllowed": False,
        "rawPayloadStored": False,
        "sourceConfidence": confidence_payload,
    }
    return {key: value for key, value in metadata.items() if value is not None}


@dataclass(frozen=True)
class StockEvidenceQuoteSnapshot:
    source: str
    price: Optional[float]
    change_pct: Optional[float]
    total_mv: Optional[float]
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    market_timestamp: Optional[str]
    source_metadata: Dict[str, Any]


class StockEvidenceQuoteAdapter:
    """Tiny boundary that isolates provider-runtime quote types for stock evidence."""

    def __init__(self, *, fetcher_manager: Any = None) -> None:
        self.fetcher_manager = fetcher_manager or DataFetcherManager()

    def get_quote_snapshot(self, symbol: str) -> Optional[StockEvidenceQuoteSnapshot]:
        quote = self.fetcher_manager.get_realtime_quote(symbol)
        if not isinstance(quote, UnifiedRealtimeQuote) or not quote.has_basic_data():
            return None
        source = getattr(getattr(quote, "source", None), "value", None) or str(getattr(quote, "source", "") or "")
        return StockEvidenceQuoteSnapshot(
            source=source or "realtime_quote",
            price=quote.price,
            change_pct=quote.change_pct,
            total_mv=quote.total_mv,
            pe_ratio=quote.pe_ratio,
            pb_ratio=quote.pb_ratio,
            market_timestamp=quote.market_timestamp,
            source_metadata=build_quote_diagnostic_source_metadata(
                source=source or "realtime_quote",
                as_of=quote.market_timestamp,
                is_partial=not bool(quote.market_timestamp),
            ),
        )
