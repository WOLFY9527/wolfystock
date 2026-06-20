# -*- coding: utf-8 -*-
"""Shared symbol research packet projection for stock and watchlist APIs."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Optional

from src.services.agent_stock_evidence_service import StockEvidenceService
from src.services.stock_service import StockService
from src.services.stock_structure_decision_service import StockStructureDecisionService
from src.utils.symbol_validation import ConsumerSymbolPrecheck, validate_consumer_symbol_precheck

logger = logging.getLogger(__name__)

RESEARCH_PACKET_NO_ADVICE_DISCLOSURE = "Observation-only research packet; no personalized action instruction."
RESEARCH_PACKET_HISTORY_DAYS = 90


class _ReadOnlyEvidenceFetcherManager:
    """Fail-closed quote seam for read-only packet assembly."""

    def get_realtime_quote(self, symbol: str):
        return None


def consumer_safe_stock_name(value: object, symbol: str) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.upper() == str(symbol or "").strip().upper():
        return None
    if any(
        marker in text.lower()
        for marker in (
            "traceback",
            "http://",
            "https://",
            "api_key",
            "apikey",
            "secret",
            "cookie",
            "session",
            "token",
            "trustlevel",
            "reasoncode",
            "sourcetype",
            "fallback",
        )
    ):
        return None
    return text


def _get_nested(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _is_true(payload: Mapping[str, Any], *keys: str) -> bool:
    return any(bool(_get_nested(payload, key)) for key in keys)


def _quote_packet(quote: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _as_mapping(quote)
    price = _safe_float(_get_nested(payload, "current_price", "currentPrice", "price"))
    change_percent = _safe_float(_get_nested(payload, "change_percent", "changePercent"))
    market_timestamp = _safe_text(_get_nested(payload, "market_timestamp", "marketTimestamp"))
    observed_at = _safe_text(_get_nested(payload, "observed_at", "observedAt", "update_time", "updateTime"))
    freshness = str(_get_nested(payload, "freshness") or "").strip().lower()

    state = "missing"
    as_of = None
    if payload and price is not None and price > 0 and not _is_true(payload, "is_synthetic", "isSynthetic"):
        degraded = (
            _is_true(payload, "is_fallback", "isFallback", "is_stale", "isStale", "is_partial", "isPartial")
            or freshness in {"fallback", "stale", "synthetic", "unavailable", "cached", "delayed"}
            or not market_timestamp
        )
        state = "stale" if degraded else "available"
        as_of = market_timestamp or observed_at

    return {
        "state": state,
        "price": price if state in {"available", "stale"} else None,
        "changePercent": change_percent if state in {"available", "stale"} else None,
        "asOf": as_of,
    }


def _history_packet(history: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _as_mapping(history)
    rows = _as_list(payload.get("data"))
    period = _safe_text(payload.get("period")) or "daily"
    latest_row = _as_mapping(rows[-1]) if rows else {}
    diagnostics = _as_mapping(payload.get("diagnostics"))
    source_confidence = _as_mapping(_get_nested(payload, "sourceConfidence", "source_confidence"))
    diagnostic_status = str(diagnostics.get("status") or "").strip().lower()
    source = str(payload.get("source") or "").strip().lower()
    freshness = str(source_confidence.get("freshness") or "").strip().lower()

    state = "missing"
    if rows:
        unavailable = (
            source == "unavailable"
            or diagnostic_status == "unavailable"
            or _is_true(source_confidence, "isUnavailable", "is_unavailable", "isSynthetic", "is_synthetic")
            or freshness in {"unavailable", "synthetic"}
        )
        degraded = (
            diagnostic_status in {"degraded", "partial", "stale"}
            or _is_true(source_confidence, "isFallback", "is_fallback", "isStale", "is_stale", "isPartial", "is_partial")
            or freshness in {"fallback", "stale", "cached", "delayed", "partial"}
        )
        state = "missing" if unavailable else ("stale" if degraded else "available")

    return {
        "state": state,
        "bars": len(rows),
        "period": period,
        "asOf": _safe_text(latest_row.get("date")) if rows else None,
    }


def _structure_packet(structure: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _as_mapping(structure)
    data_quality = _as_mapping(_get_nested(payload, "dataQuality", "data_quality"))
    quality_status = str(data_quality.get("status") or "").strip().lower()
    if quality_status == "available":
        state = "available"
    elif quality_status in {"partial", "insufficient"}:
        state = "insufficient"
    elif quality_status == "unavailable":
        state = "missing"
    else:
        state = "unknown" if payload else "missing"

    return {
        "state": state,
        "label": _safe_text(_get_nested(payload, "structureState", "structure_state")) if state in {"available", "insufficient"} else None,
        "confidence": _safe_text(payload.get("confidence")) if state in {"available", "insufficient"} else None,
        "asOf": None,
    }


def _first_evidence_item(evidence: Mapping[str, Any] | None, symbol: str) -> dict[str, Any] | None:
    items = _as_list(_as_mapping(evidence).get("items"))
    for item in items:
        item_payload = _as_mapping(item)
        if str(item_payload.get("symbol") or "").strip().upper() == symbol.upper():
            return item_payload
    return _as_mapping(items[0]) if items else None


def _fundamentals_packet(item: Mapping[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {"state": "not_integrated", "fieldsAvailable": []}

    fundamental = _as_mapping(item.get("fundamental"))
    packet = _as_mapping(_get_nested(item, "stockEvidencePacket", "stock_evidence_packet"))
    summary = _as_mapping(_get_nested(packet, "fundamentalsSummary", "fundamentals_summary"))
    allowed_fields = (
        "marketCap",
        "peTtm",
        "pb",
        "beta",
        "revenueTtm",
        "netIncomeTtm",
        "fcfTtm",
        "grossMargin",
        "operatingMargin",
        "roe",
        "roa",
    )
    fields_available = [field for field in allowed_fields if summary.get(field) is not None]
    status = str(summary.get("status") or fundamental.get("status") or "").strip().lower()

    if fields_available:
        state = "available"
    elif not fundamental and not summary:
        state = "not_integrated"
    elif status in {"missing", "unavailable", "no_evidence", "insufficient"}:
        state = "missing"
    else:
        state = "unknown"
    return {"state": state, "fieldsAvailable": fields_available}


def _events_packet(item: Mapping[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {"state": "not_integrated", "latest": []}

    news = _as_mapping(item.get("news"))
    filing = _as_mapping(_get_nested(item, "secFilingEvidence", "sec_filing_evidence"))
    latest: list[dict[str, Any]] = []

    for record in _as_list(news.get("latest")):
        record_payload = _as_mapping(record)
        if record_payload:
            latest.append(record_payload)
    headline = _safe_text(_get_nested(news, "latestHeadline", "headline"))
    if headline:
        latest.append({"kind": "news", "headline": headline})
    for record in _as_list(filing.get("records")):
        record_payload = _as_mapping(record)
        if record_payload:
            latest.append(record_payload)

    statuses = {str(block.get("status") or "").strip().lower() for block in (news, filing) if block}
    if latest:
        state = "available"
    elif not news and not filing:
        state = "not_integrated"
    elif statuses.intersection({"missing", "unavailable", "no_evidence", "insufficient", "unknown"}):
        state = "missing"
    else:
        state = "unknown"
    return {"state": state, "latest": latest}


def _peer_packet(structure: Mapping[str, Any] | None) -> dict[str, Any]:
    snapshot = _as_mapping(_get_nested(_as_mapping(structure), "peerCorrelationSnapshot", "peer_correlation_snapshot"))
    peer_group = _as_mapping(_get_nested(snapshot, "peerGroup", "peer_group"))
    peer_evidence = _as_list(_get_nested(snapshot, "peerEvidence", "peer_evidence"))
    correlation_state = str(_get_nested(snapshot, "correlationState", "correlation_state") or "").strip().lower()
    benchmark = _safe_text(peer_group.get("label"))

    if correlation_state in {"aligned", "diverging"} and peer_evidence:
        state = "available"
    elif peer_group.get("status") == "available":
        state = "insufficient"
    elif snapshot:
        state = "missing"
    else:
        state = "unknown"
    return {"state": state, "benchmark": benchmark if state == "available" else None}


def _missing_data_families(
    *,
    quote: Mapping[str, Any],
    history: Mapping[str, Any],
    structure: Mapping[str, Any],
    fundamentals: Mapping[str, Any],
    events: Mapping[str, Any],
    peer: Mapping[str, Any],
) -> list[str]:
    missing: list[str] = []
    if quote.get("state") != "available":
        missing.append("quote")
    if history.get("state") != "available":
        missing.append("price_history")
    if structure.get("state") != "available":
        missing.append("structure_analysis")
    if fundamentals.get("state") != "available":
        missing.append("fundamentals")
    if events.get("state") != "available":
        missing.append("filing_event_catalyst")
    if peer.get("state") != "available":
        missing.append("peer_benchmark")
    return missing


def _research_status(packet_parts: Mapping[str, Mapping[str, Any]]) -> str:
    critical_states = {
        str(packet_parts["quote"].get("state")),
        str(packet_parts["history"].get("state")),
        str(packet_parts["structure"].get("state")),
    }
    if critical_states.intersection({"missing", "unknown"}):
        return "blocked"
    if any(part.get("state") != "available" for part in packet_parts.values()):
        return "partial"
    return "ready"


def _next_data_action(missing_data: list[str], research_status: str) -> str:
    if research_status == "ready":
        return "Refresh the packet before reusing this research context."
    if "quote" in missing_data or "price_history" in missing_data:
        return "Add quote and daily price history evidence before marking the packet ready."
    if "structure_analysis" in missing_data:
        return "Add enough daily price history to build the structure observation."
    labels = {
        "fundamentals": "fundamentals",
        "filing_event_catalyst": "filing, event, or catalyst evidence",
        "peer_benchmark": "peer or benchmark evidence",
    }
    families = [labels[key] for key in missing_data if key in labels]
    if families:
        return f"Add {', '.join(families)} before marking the packet ready."
    return "Review missing data before interpreting this packet."


def _fail_closed_research_packet(precheck: ConsumerSymbolPrecheck) -> dict[str, Any]:
    normalized_symbol = precheck.normalized_symbol or precheck.raw_symbol
    missing_data = ["quote", "price_history", "structure_analysis", "fundamentals", "filing_event_catalyst", "peer_benchmark"]
    return {
        "symbol": normalized_symbol,
        "market": precheck.market or "unknown",
        "identity": {"name": None, "exchange": None, "sector": None, "industry": None},
        "quote": {"state": "unknown", "price": None, "changePercent": None, "asOf": None},
        "history": {"state": "unknown", "bars": 0, "period": "daily", "asOf": None},
        "structure": {"state": "unknown", "label": None, "confidence": None, "asOf": None},
        "fundamentals": {"state": "unknown", "fieldsAvailable": []},
        "events": {"state": "unknown", "latest": []},
        "peer": {"state": "unknown", "benchmark": None},
        "missingData": missing_data,
        "researchStatus": "blocked",
        "nextDataAction": "Verify symbol format and market before requesting research data.",
        "observationOnly": True,
        "decisionGrade": False,
        "noAdviceDisclosure": RESEARCH_PACKET_NO_ADVICE_DISCLOSURE,
    }


def build_symbol_research_packet_from_parts(stock_code: str, *, market: Optional[str] = None) -> dict[str, Any]:
    """Build the contract shape without triggering quote/provider lookups."""

    precheck = validate_consumer_symbol_precheck(stock_code, market=market)
    if not precheck.can_lookup:
        return _fail_closed_research_packet(precheck)

    symbol = precheck.normalized_symbol
    quote = {"state": "missing", "price": None, "changePercent": None, "asOf": None}
    history = {"state": "missing", "bars": 0, "period": "daily", "asOf": None}
    structure = {"state": "missing", "label": None, "confidence": None, "asOf": None}
    fundamentals = {"state": "not_integrated", "fieldsAvailable": []}
    events = {"state": "not_integrated", "latest": []}
    peer = {"state": "missing", "benchmark": None}
    missing_data = _missing_data_families(
        quote=quote,
        history=history,
        structure=structure,
        fundamentals=fundamentals,
        events=events,
        peer=peer,
    )
    research_status = _research_status(
        {
            "quote": quote,
            "history": history,
            "structure": structure,
            "fundamentals": fundamentals,
            "events": events,
            "peer": peer,
        }
    )
    return {
        "symbol": symbol,
        "market": precheck.market or "unknown",
        "identity": {"name": None, "exchange": None, "sector": None, "industry": None},
        "quote": quote,
        "history": history,
        "structure": structure,
        "fundamentals": fundamentals,
        "events": events,
        "peer": peer,
        "missingData": missing_data,
        "researchStatus": research_status,
        "nextDataAction": _next_data_action(missing_data, research_status),
        "observationOnly": True,
        "decisionGrade": False,
        "noAdviceDisclosure": RESEARCH_PACKET_NO_ADVICE_DISCLOSURE,
    }


def build_symbol_research_packet(stock_code: str, *, market: Optional[str] = None) -> dict[str, Any]:
    precheck = validate_consumer_symbol_precheck(stock_code, market=market)
    if not precheck.can_lookup:
        return _fail_closed_research_packet(precheck)

    symbol = precheck.normalized_symbol
    stock_service = StockService()

    try:
        quote_payload = stock_service.get_realtime_quote(symbol)
    except Exception:
        logger.warning("Symbol research packet quote lookup failed for %s", symbol, exc_info=True)
        quote_payload = None

    try:
        history_payload = stock_service.get_history_data(
            stock_code=symbol,
            period="daily",
            days=RESEARCH_PACKET_HISTORY_DAYS,
        )
    except Exception:
        logger.warning("Symbol research packet history lookup failed for %s", symbol, exc_info=True)
        history_payload = {}

    try:
        structure_payload = StockStructureDecisionService().get_structure_decision(symbol)
    except Exception:
        logger.warning("Symbol research packet structure lookup failed for %s", symbol, exc_info=True)
        structure_payload = {}

    try:
        evidence_service = StockEvidenceService()
        if hasattr(evidence_service, "quote_adapter") and hasattr(evidence_service.quote_adapter, "fetcher_manager"):
            evidence_service.quote_adapter.fetcher_manager = _ReadOnlyEvidenceFetcherManager()
        if hasattr(evidence_service, "fetcher_manager"):
            evidence_service.fetcher_manager = _ReadOnlyEvidenceFetcherManager()
        evidence_payload = evidence_service.get_stock_evidence([symbol])
    except Exception:
        logger.warning("Symbol research packet evidence lookup failed for %s", symbol, exc_info=True)
        evidence_payload = {}

    quote = _quote_packet(_as_mapping(quote_payload))
    history = _history_packet(_as_mapping(history_payload))
    structure = _structure_packet(_as_mapping(structure_payload))
    evidence_item = _first_evidence_item(_as_mapping(evidence_payload), symbol)
    fundamentals = _fundamentals_packet(evidence_item)
    events = _events_packet(evidence_item)
    peer = _peer_packet(_as_mapping(structure_payload))
    missing_data = _missing_data_families(
        quote=quote,
        history=history,
        structure=structure,
        fundamentals=fundamentals,
        events=events,
        peer=peer,
    )
    packet_parts = {
        "quote": quote,
        "history": history,
        "structure": structure,
        "fundamentals": fundamentals,
        "events": events,
        "peer": peer,
    }
    research_status = _research_status(packet_parts)
    name = consumer_safe_stock_name(
        _get_nested(_as_mapping(quote_payload), "stock_name", "stockName")
        or _get_nested(_as_mapping(history_payload), "stock_name", "stockName"),
        symbol,
    )

    return {
        "symbol": symbol,
        "market": precheck.market or "unknown",
        "identity": {"name": name, "exchange": None, "sector": None, "industry": None},
        "quote": quote,
        "history": history,
        "structure": structure,
        "fundamentals": fundamentals,
        "events": events,
        "peer": peer,
        "missingData": missing_data,
        "researchStatus": research_status,
        "nextDataAction": _next_data_action(missing_data, research_status),
        "observationOnly": True,
        "decisionGrade": False,
        "noAdviceDisclosure": RESEARCH_PACKET_NO_ADVICE_DISCLOSURE,
    }
