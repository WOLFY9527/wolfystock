# -*- coding: utf-8 -*-
"""Safe API-facing service for stock structure decisions."""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from src.services.consumer_issue_labels import build_consumer_issues
from src.services.confidence_evidence_consistency import project_confidence_evidence_state
from src.services.stock_service import StockService
from src.services.stock_structure_decision_engine import (
    MIN_REQUIRED_BARS,
    NO_ADVICE_DISCLOSURE,
    build_stock_structure_decision,
)
from src.utils.symbol_validation import validate_consumer_symbol_precheck


logger = logging.getLogger(__name__)

STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION = "stock_structure_decision_api_v1"
SYMBOL_COMPARE_EVIDENCE_PACKET_VERSION = "symbol_compare_evidence_packet_v1"
DEFAULT_STRUCTURE_DECISION_HISTORY_DAYS = 90
DEFAULT_STRUCTURE_DECISION_TIMEOUT_SECONDS = 2.5
DEFAULT_STRUCTURE_DECISION_BATCH_MAX_ITEMS = 25
MAX_STRUCTURE_DECISION_BATCH_ITEMS = 50
PEER_CORRELATION_HISTORY_DAYS = 60
PEER_CORRELATION_MAX_PEERS = 5
PEER_CORRELATION_MIN_PEERS = 2
PEER_CORRELATION_MIN_OVERLAP_DAYS = 6
PEER_CORRELATION_ALIGNED_THRESHOLD = 0.6
PEER_CORRELATION_DIVERGENCE_THRESHOLD = 0.25
PEER_CORRELATION_SPREAD_DIVERGENCE_PCT = 8.0
PEER_OBSERVATION_BOUNDARY = "Observation-only peer movement context; no personalized action instruction."
_SOURCE_CONTEXT_SPECS = {
    "researchRadar": {
        "label": "Research Radar",
        "route": "/research/radar",
        "defaultSection": "topResearchPriorities",
        "defaultReason": "Research radar queue context.",
        "sectionReasons": {
            "topResearchPriorities": "Research radar queue context.",
            "scannerHighlights": "Scanner candidate context.",
        },
    },
    "watchlist": {
        "label": "Watchlist",
        "route": "/watchlist",
        "defaultSection": "watchlistHighlights",
        "defaultReason": "Watchlist research context.",
        "sectionReasons": {
            "watchlistHighlights": "Watchlist research context.",
        },
    },
    "portfolio": {
        "label": "Portfolio",
        "route": "/portfolio",
        "defaultSection": "portfolioStructureHighlights",
        "defaultReason": "Portfolio structure context.",
        "sectionReasons": {
            "portfolioStructureHighlights": "Portfolio structure context.",
        },
    },
}
_SOURCE_CONTEXT_ALIASES = {
    "researchradar": "researchRadar",
    "research_radar": "researchRadar",
    "research-radar": "researchRadar",
    "watchlist": "watchlist",
    "portfolio": "portfolio",
}
_SOURCE_CONTEXT_ERROR = {
    "label": "Research context unavailable",
    "message": "The requested research context could not be attached to this structure read.",
    "severity": "info",
    "category": "research",
}
_SYMBOL_REVIEW_ISSUE = {
    "label": "Symbol needs review",
    "message": "Review the symbol format before using this structure panel.",
    "severity": "warning",
    "category": "symbol",
}
_STRUCTURE_UNAVAILABLE_ISSUE = {
    "label": "Structure evidence unavailable",
    "message": "Daily structure evidence is not available for this symbol yet.",
    "severity": "warning",
    "category": "evidence",
}
_STRUCTURE_PARTIAL_ISSUE = {
    "label": "Structure evidence incomplete",
    "message": "Daily structure evidence is incomplete, so confidence remains bounded.",
    "severity": "info",
    "category": "evidence",
}
_STRUCTURE_DECISION_TIMEOUT_REASON = "structure_decision_timeout"
_STRUCTURE_DECISION_TIMEOUT_MESSAGE = (
    "Structure decision inputs did not return within the latency boundary."
)


class StockStructureDecisionService:
    """Build observation-only stock structure decisions from existing OHLCV access."""

    def __init__(
        self,
        history_service: Any | None = None,
        stock_repo: Any | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> None:
        self.history_service = history_service or StockService()
        self.stock_repo = stock_repo
        self.timeout_seconds = _normalize_timeout_seconds(timeout_seconds)

    def get_structure_decision(
        self,
        ticker: str,
        *,
        context_source: str | None = None,
        context_section: str | None = None,
        context_reason: str | None = None,
    ) -> dict[str, Any]:
        precheck = validate_consumer_symbol_precheck(ticker)
        normalized_ticker = precheck.normalized_symbol or _normalize_ticker(ticker)
        if not precheck.can_lookup:
            return _finalize_structure_contract(
                _precheck_fail_closed_payload(normalized_ticker, precheck),
                source_context=None,
                source_context_issue=None,
                symbol_issue=precheck.message,
            )

        payload = self._build_structure_decision_with_latency_boundary(normalized_ticker)
        return _finalize_structure_contract(
            payload,
            source_context=_build_source_context(
                context_source=context_source,
                context_section=context_section,
                context_reason=context_reason,
            ),
            source_context_issue=_source_context_issue(context_source=context_source, context_section=context_section),
            symbol_issue=None,
        )

    def _build_structure_decision_with_latency_boundary(self, ticker: str) -> dict[str, Any]:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stock_structure_decision")
        future = executor.submit(self._build_structure_decision, ticker)
        timeout_triggered = False
        try:
            return future.result(timeout=self.timeout_seconds)
        except FuturesTimeoutError:
            timeout_triggered = True
            future.cancel()
            logger.warning(
                "Stock structure decision exceeded latency boundary for %s after %.3fs",
                ticker,
                self.timeout_seconds,
            )
            return _latency_boundary_payload(ticker)
        finally:
            executor.shutdown(wait=not timeout_triggered, cancel_futures=timeout_triggered)

    def get_structure_decisions_batch(
        self,
        tickers: Sequence[str],
        *,
        benchmark: str | None = None,
        max_items: int | None = None,
    ) -> dict[str, Any]:
        requested_tickers = list(tickers or [])
        normalized_tickers = _normalize_unique_tickers(requested_tickers)
        bounded_max_items = _bounded_batch_max_items(max_items)
        selected_tickers = normalized_tickers[:bounded_max_items]
        benchmark_ticker = _normalize_ticker(benchmark or "")
        history_cache: dict[str, tuple[Mapping[str, Any], list[Mapping[str, Any]], dict[str, Any]]] = {}

        benchmark_bars: list[Mapping[str, Any]] = []
        benchmark_available = False
        if benchmark_ticker:
            benchmark_history = self._load_daily_history(benchmark_ticker)
            benchmark_bars = _history_bars(benchmark_history)
            benchmark_quality = _build_data_quality(benchmark_history, benchmark_bars)
            history_cache[benchmark_ticker] = (benchmark_history, benchmark_bars, benchmark_quality)
            benchmark_available = _has_comparative_ohlcv(benchmark_quality)

        items = []
        for ticker in selected_tickers:
            cached = history_cache.get(ticker)
            if cached is None:
                history = self._load_daily_history(ticker)
                bars = _history_bars(history)
                data_quality = _build_data_quality(history, bars)
                history_cache[ticker] = (history, bars, data_quality)
            else:
                _history, bars, data_quality = cached
            items.append(
                self._build_structure_decision(
                    ticker,
                    bars=bars,
                    data_quality=data_quality,
                    benchmark_bars=benchmark_bars if benchmark_available else None,
                    benchmark_ticker=benchmark_ticker or None,
                    comparative_available=benchmark_available,
                    include_comparative_context=True,
                )
            )

        _apply_relative_strength_ranking(items, benchmark_ticker if benchmark_available else None)
        aggregate_summary = _build_aggregate_summary(
            items,
            requested_count=len(requested_tickers),
            max_items=bounded_max_items,
            truncated=len(normalized_tickers) > bounded_max_items,
            benchmark_ticker=benchmark_ticker if benchmark_available else None,
        )

        return {
            "schemaVersion": STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION,
            "items": items,
            "aggregateSummary": aggregate_summary,
            "missingEvidence": _batch_missing_evidence(items, benchmark_available),
            "dataQuality": _batch_data_quality(items),
            "symbolCompareEvidencePacket": _build_symbol_compare_evidence_packet(
                items,
                benchmark_ticker=benchmark_ticker if benchmark_available else None,
            ),
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        }

    def _build_structure_decision(
        self,
        ticker: str,
        *,
        bars: Sequence[Mapping[str, Any]] | None = None,
        data_quality: dict[str, Any] | None = None,
        benchmark_bars: Sequence[Mapping[str, Any]] | None = None,
        benchmark_ticker: str | None = None,
        comparative_available: bool = False,
        include_comparative_context: bool = False,
    ) -> dict[str, Any]:
        history = self._load_daily_history(ticker) if bars is None or data_quality is None else {}
        bars = _history_bars(history) if bars is None else list(bars)
        data_quality = _build_data_quality(history, bars) if data_quality is None else data_quality
        engine_result = build_stock_structure_decision(bars, benchmark_ohlcv=benchmark_bars)
        missing_evidence = _missing_evidence(
            data_quality,
            include_benchmark_missing=not (include_comparative_context and comparative_available),
        )

        payload = {
            "schemaVersion": STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION,
            "ticker": ticker,
            "structureState": engine_result.get("structureState", "lowConfidence"),
            "confidence": engine_result.get("confidence", "low"),
            "componentScores": engine_result.get("componentScores", {}),
            "explanation": engine_result.get("explanation", {}),
            "researchNotes": engine_result.get("researchNotes", {}),
            "dataQuality": data_quality,
            "missingEvidence": missing_evidence,
            "peerCorrelationSnapshot": self._build_peer_correlation_snapshot(ticker),
            "noAdviceDisclosure": engine_result.get("noAdviceDisclosure") or NO_ADVICE_DISCLOSURE,
        }
        if include_comparative_context:
            score = int(payload["componentScores"].get("relativeStrength") or 0)
            payload["comparativeContext"] = (
                {
                    "status": "available",
                    "benchmark": benchmark_ticker,
                    "relativeStrengthScore": score,
                    "rank": None,
                }
                if comparative_available and benchmark_ticker
                else {
                    "status": "unavailable",
                    "benchmark": benchmark_ticker,
                    "reason": "benchmark_ohlcv_unavailable",
                }
            )
        return _finalize_structure_contract(payload)

    def _load_daily_history(self, ticker: str) -> dict[str, Any]:
        try:
            payload = self.history_service.get_history_data(
                stock_code=ticker,
                period="daily",
                days=DEFAULT_STRUCTURE_DECISION_HISTORY_DAYS,
            )
        except Exception as exc:
            logger.warning("Stock structure decision history lookup failed for %s: %s", ticker, exc)
            return {
                "stock_code": ticker,
                "period": "daily",
                "data": [],
                "source": "unavailable",
                "diagnostics": {
                    "status": "unavailable",
                    "reason": "history_lookup_failed",
                },
            }
        return payload if isinstance(payload, dict) else {}

    def _build_peer_correlation_snapshot(self, ticker: str) -> dict[str, Any]:
        peer_group, group_missing = _load_local_peer_group(self.stock_repo, ticker)
        missing_inputs = list(group_missing)
        stale_inputs: list[str] = []
        if peer_group["status"] != "available":
            return _insufficient_peer_correlation_snapshot(
                ticker,
                peer_group=peer_group,
                missing_inputs=missing_inputs,
            )

        peer_symbols = [
            symbol
            for symbol in _normalize_unique_tickers(peer_group.get("symbols", []))
            if symbol != ticker
        ][:PEER_CORRELATION_MAX_PEERS]
        peer_group = {**peer_group, "symbols": peer_symbols}
        if len(peer_symbols) < PEER_CORRELATION_MIN_PEERS:
            missing_inputs.append("At least two locally verified peer symbols are needed for this snapshot.")
            return _insufficient_peer_correlation_snapshot(
                ticker,
                peer_group=peer_group,
                missing_inputs=missing_inputs,
            )

        target_series, target_latest = _load_local_close_series(self.stock_repo, ticker)
        if len(target_series) < PEER_CORRELATION_MIN_OVERLAP_DAYS:
            missing_inputs.append(f"Recent local daily OHLCV is incomplete for {ticker}.")
            return _insufficient_peer_correlation_snapshot(
                ticker,
                peer_group=peer_group,
                missing_inputs=missing_inputs,
            )

        peer_evidence: list[dict[str, Any]] = []
        divergence_evidence: list[dict[str, Any]] = []
        latest_by_symbol: dict[str, date | None] = {ticker: target_latest}
        for peer_symbol in peer_symbols:
            peer_series, peer_latest = _load_local_close_series(self.stock_repo, peer_symbol)
            latest_by_symbol[peer_symbol] = peer_latest
            evidence = _build_peer_evidence(
                symbol=ticker,
                peer_symbol=peer_symbol,
                symbol_series=target_series,
                peer_series=peer_series,
            )
            if evidence["state"] == "insufficient_evidence":
                missing_inputs.append(f"Recent local daily OHLCV is incomplete for {peer_symbol}.")
                continue
            peer_evidence.append(evidence)
            if evidence["state"] == "diverging":
                divergence_evidence.append(evidence)

        newest_date = max([value for value in latest_by_symbol.values() if value is not None], default=None)
        if newest_date is not None:
            stale_inputs.extend(
                _stale_peer_inputs(
                    ticker=ticker,
                    target_latest=target_latest,
                    peer_symbols=peer_symbols,
                    latest_by_symbol=latest_by_symbol,
                    newest_date=newest_date,
                )
            )

        correlation_state = _peer_correlation_state(peer_evidence)
        if not peer_evidence or correlation_state == "insufficient_evidence":
            missing_inputs.append("Enough overlapping local peer OHLCV was not available for a bounded comparison.")

        return {
            "symbol": ticker,
            "peerGroup": peer_group,
            "correlationState": correlation_state,
            "peerEvidence": peer_evidence,
            "divergenceEvidence": divergence_evidence,
            "staleInputs": _dedupe(stale_inputs),
            "missingInputs": _dedupe(missing_inputs),
            "confidenceCap": "medium" if correlation_state in {"aligned", "diverging"} else "low",
            "observationBoundary": PEER_OBSERVATION_BOUNDARY,
            "researchNextSteps": _peer_research_next_steps(correlation_state, missing_inputs),
        }


def _finalize_structure_contract(
    payload: Mapping[str, Any],
    *,
    source_context: Mapping[str, str] | None = None,
    source_context_issue: str | None = None,
    symbol_issue: str | None = None,
) -> dict[str, Any]:
    explanation = payload.get("explanation")
    explanation = explanation if isinstance(explanation, Mapping) else {}
    research_notes = payload.get("researchNotes")
    research_notes = research_notes if isinstance(research_notes, Mapping) else {}
    missing_evidence = payload.get("missingEvidence")
    missing_evidence = missing_evidence if isinstance(missing_evidence, list) else []
    data_quality = payload.get("dataQuality")
    data_quality = data_quality if isinstance(data_quality, Mapping) else {}

    evidence_notes = _safe_text_list(explanation.get("whatConfirmsIt"))
    key_levels = _safe_mapping_list(explanation.get("keyLevels"))
    risk_observations = _dedupe(
        [
            *_safe_text_list(research_notes.get("riskFlags")),
            *_safe_text_list(explanation.get("whatInvalidatesIt")),
        ]
    )
    evidence_gaps = _dedupe(
        [
            *[str(item.get("message") or "").strip() for item in missing_evidence if isinstance(item, Mapping)],
            *_safe_text_list(research_notes.get("needsMoreEvidence")),
        ]
    )
    degraded_inputs = _build_degraded_inputs(
        data_quality=data_quality,
        missing_evidence=missing_evidence,
        source_context_issue=source_context_issue,
        symbol_issue=symbol_issue,
    )
    consumer_issues = _build_detail_consumer_issues(
        data_quality=data_quality,
        missing_evidence=missing_evidence,
        risk_observations=risk_observations,
        needs_more_evidence=_safe_text_list(research_notes.get("needsMoreEvidence")),
        source_context_issue=source_context_issue,
        symbol_issue=symbol_issue,
    )

    peer_correlation_snapshot = payload.get("peerCorrelationSnapshot")
    if not isinstance(peer_correlation_snapshot, Mapping):
        peer_correlation_snapshot = _insufficient_peer_correlation_snapshot(
            str(payload.get("ticker") or ""),
            missing_inputs=["No verified local peer group metadata is available for this symbol."],
        )
    confidence_projection = project_confidence_evidence_state(
        payload={
            "confidence": payload.get("confidence"),
            "evidenceGaps": evidence_gaps,
            "missingEvidence": missing_evidence,
            "degradedInputs": degraded_inputs,
            "dataQuality": data_quality,
            "peerCorrelationSnapshot": peer_correlation_snapshot,
        }
    )

    result = dict(payload)
    result.update(
        {
            "symbol": str(payload.get("ticker") or ""),
            "rawConfidence": str(payload.get("confidence") or "low"),
            "confidence": confidence_projection["consumerConfidence"],
            "confidenceCap": confidence_projection["confidenceCap"],
            "confidenceState": confidence_projection["confidenceState"],
            "keyLevels": key_levels,
            "evidenceNotes": evidence_notes,
            "riskObservations": risk_observations,
            "evidenceGaps": evidence_gaps,
            "degradedInputs": degraded_inputs,
            "peerCorrelationSnapshot": dict(peer_correlation_snapshot),
            "consumerIssues": consumer_issues,
            "observationOnly": True,
            "decisionGrade": False,
            "drilldownLinks": [dict(source_context)] if source_context is not None else [],
        }
    )
    if source_context is not None:
        result["sourceContext"] = dict(source_context)
    return result


def _precheck_fail_closed_payload(ticker: str, precheck: Any) -> dict[str, Any]:
    engine_result = build_stock_structure_decision([])
    return {
        "schemaVersion": STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION,
        "ticker": ticker,
        "structureState": engine_result.get("structureState", "lowConfidence"),
        "confidence": engine_result.get("confidence", "low"),
        "componentScores": engine_result.get("componentScores", {}),
        "explanation": engine_result.get("explanation", {}),
        "researchNotes": engine_result.get("researchNotes", {}),
        "dataQuality": {
            "status": "unavailable",
            "source": "unavailable",
            "period": "daily",
            "requestedDays": DEFAULT_STRUCTURE_DECISION_HISTORY_DAYS,
            "observedBars": 0,
            "usableBars": 0,
            "reason": str(getattr(precheck, "status", "") or "symbol_review_required"),
        },
        "missingEvidence": [
            {
                "kind": "symbol_validation",
                "message": str(getattr(precheck, "message", "") or "Review the symbol before retrying this structure read."),
            }
        ],
        "noAdviceDisclosure": engine_result.get("noAdviceDisclosure") or NO_ADVICE_DISCLOSURE,
    }


def _latency_boundary_payload(ticker: str) -> dict[str, Any]:
    engine_result = build_stock_structure_decision([])
    return {
        "schemaVersion": STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION,
        "ticker": ticker,
        "structureState": engine_result.get("structureState", "lowConfidence"),
        "confidence": engine_result.get("confidence", "low"),
        "componentScores": engine_result.get("componentScores", {}),
        "explanation": engine_result.get("explanation", {}),
        "researchNotes": engine_result.get("researchNotes", {}),
        "dataQuality": {
            "status": "unavailable",
            "source": "unavailable",
            "period": "daily",
            "requestedDays": DEFAULT_STRUCTURE_DECISION_HISTORY_DAYS,
            "observedBars": 0,
            "usableBars": 0,
            "reason": _STRUCTURE_DECISION_TIMEOUT_REASON,
        },
        "missingEvidence": [
            {
                "kind": "daily_ohlcv",
                "message": _STRUCTURE_DECISION_TIMEOUT_MESSAGE,
            },
            {
                "kind": "benchmark_ohlcv",
                "message": "Benchmark OHLCV is not included in this endpoint yet, so relative-strength evidence is neutral.",
            },
        ],
        "peerCorrelationSnapshot": _insufficient_peer_correlation_snapshot(
            ticker,
            missing_inputs=["Peer correlation was not evaluated because structure evidence exceeded the latency boundary."],
        ),
        "noAdviceDisclosure": engine_result.get("noAdviceDisclosure") or NO_ADVICE_DISCLOSURE,
    }


def _insufficient_peer_correlation_snapshot(
    ticker: str,
    *,
    peer_group: Mapping[str, Any] | None = None,
    missing_inputs: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "symbol": ticker,
        "peerGroup": dict(peer_group or {"status": "unavailable", "label": None, "symbols": []}),
        "correlationState": "insufficient_evidence",
        "peerEvidence": [],
        "divergenceEvidence": [],
        "staleInputs": [],
        "missingInputs": _dedupe(list(missing_inputs or [])),
        "confidenceCap": "low",
        "observationBoundary": PEER_OBSERVATION_BOUNDARY,
        "researchNextSteps": _peer_research_next_steps("insufficient_evidence", list(missing_inputs or [])),
    }


def _load_local_peer_group(stock_repo: Any, ticker: str) -> tuple[dict[str, Any], list[str]]:
    getter = getattr(stock_repo, "get_local_peer_group", None)
    if not callable(getter):
        return _unavailable_peer_group(), [f"No verified local peer group metadata is available for {ticker}."]
    try:
        raw_group = getter(ticker)
    except Exception as exc:
        logger.warning("Local peer group lookup failed for %s: %s", ticker, exc)
        return _unavailable_peer_group(), [f"Verified local peer group metadata could not be read for {ticker}."]
    return _normalize_local_peer_group(raw_group, ticker)


def _unavailable_peer_group() -> dict[str, Any]:
    return {"status": "unavailable", "label": None, "symbols": []}


def _normalize_local_peer_group(raw_group: Any, ticker: str) -> tuple[dict[str, Any], list[str]]:
    label: str | None = None
    raw_symbols: Any = None
    if isinstance(raw_group, Mapping):
        label = _safe_text(raw_group.get("label") or raw_group.get("name") or raw_group.get("peerGroup")) or None
        raw_symbols = raw_group.get("symbols") or raw_group.get("peers")
    elif isinstance(raw_group, Sequence) and not isinstance(raw_group, (str, bytes, bytearray)):
        raw_symbols = raw_group

    symbols = [
        symbol
        for symbol in _normalize_unique_tickers(list(raw_symbols or []))
        if symbol != ticker
    ][:PEER_CORRELATION_MAX_PEERS]
    if not symbols:
        return _unavailable_peer_group(), [f"No verified local peer symbols are available for {ticker}."]
    return {"status": "available", "label": label, "symbols": symbols}, []


def _load_local_close_series(stock_repo: Any, symbol: str) -> tuple[dict[date, float], date | None]:
    getter = getattr(stock_repo, "get_recent_daily_rows", None)
    if not callable(getter):
        return {}, None
    try:
        rows = getter(code=symbol, limit=PEER_CORRELATION_HISTORY_DAYS)
    except Exception as exc:
        logger.warning("Local peer OHLCV lookup failed for %s: %s", symbol, exc)
        return {}, None
    series: dict[date, float] = {}
    for row in rows or []:
        row_date = _coerce_date(_row_value(row, "date"))
        close = _coerce_float(_row_value(row, "close"))
        if row_date is None or close is None or close <= 0:
            continue
        series[row_date] = close
    latest = max(series) if series else None
    return series, latest


def _build_peer_evidence(
    *,
    symbol: str,
    peer_symbol: str,
    symbol_series: Mapping[date, float],
    peer_series: Mapping[date, float],
) -> dict[str, Any]:
    overlap_dates = sorted(set(symbol_series).intersection(peer_series))
    if len(overlap_dates) < PEER_CORRELATION_MIN_OVERLAP_DAYS:
        return _insufficient_peer_evidence(peer_symbol, len(overlap_dates))

    symbol_returns, peer_returns = _paired_returns(overlap_dates, symbol_series, peer_series)
    if len(symbol_returns) < PEER_CORRELATION_MIN_OVERLAP_DAYS - 1:
        return _insufficient_peer_evidence(peer_symbol, len(overlap_dates))

    correlation = _pearson_correlation(symbol_returns, peer_returns)
    symbol_return_pct = _window_return_pct(overlap_dates, symbol_series)
    peer_return_pct = _window_return_pct(overlap_dates, peer_series)
    spread_pct = None
    if symbol_return_pct is not None and peer_return_pct is not None:
        spread_pct = round(symbol_return_pct - peer_return_pct, 2)

    state = _peer_evidence_state(correlation, spread_pct)
    summary = _peer_evidence_summary(symbol, peer_symbol, state)
    return {
        "symbol": peer_symbol,
        "correlation": round(correlation, 3) if correlation is not None else None,
        "overlapDays": len(overlap_dates),
        "symbolReturnPct": symbol_return_pct,
        "peerReturnPct": peer_return_pct,
        "spreadPct": spread_pct,
        "state": state,
        "summary": summary,
    }


def _insufficient_peer_evidence(peer_symbol: str, overlap_days: int) -> dict[str, Any]:
    return {
        "symbol": peer_symbol,
        "correlation": None,
        "overlapDays": overlap_days,
        "symbolReturnPct": None,
        "peerReturnPct": None,
        "spreadPct": None,
        "state": "insufficient_evidence",
        "summary": f"Local overlapping OHLCV is insufficient for {peer_symbol}.",
    }


def _paired_returns(
    overlap_dates: Sequence[date],
    symbol_series: Mapping[date, float],
    peer_series: Mapping[date, float],
) -> tuple[list[float], list[float]]:
    symbol_returns: list[float] = []
    peer_returns: list[float] = []
    for previous_date, current_date in zip(overlap_dates, overlap_dates[1:]):
        previous_symbol = symbol_series.get(previous_date)
        current_symbol = symbol_series.get(current_date)
        previous_peer = peer_series.get(previous_date)
        current_peer = peer_series.get(current_date)
        if not previous_symbol or not current_symbol or not previous_peer or not current_peer:
            continue
        symbol_returns.append((current_symbol / previous_symbol) - 1.0)
        peer_returns.append((current_peer / previous_peer) - 1.0)
    return symbol_returns, peer_returns


def _pearson_correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right)
    )
    left_variance = sum((value - left_mean) ** 2 for value in left)
    right_variance = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_variance * right_variance)
    if denominator == 0:
        return None
    return numerator / denominator


def _window_return_pct(overlap_dates: Sequence[date], series: Mapping[date, float]) -> float | None:
    if len(overlap_dates) < 2:
        return None
    first = series.get(overlap_dates[0])
    last = series.get(overlap_dates[-1])
    if not first or not last:
        return None
    return round(((last / first) - 1.0) * 100.0, 2)


def _peer_evidence_state(correlation: float | None, spread_pct: float | None) -> str:
    if correlation is None:
        return "insufficient_evidence"
    spread_is_bounded = spread_pct is None or abs(spread_pct) < PEER_CORRELATION_SPREAD_DIVERGENCE_PCT
    if correlation >= PEER_CORRELATION_ALIGNED_THRESHOLD and spread_is_bounded:
        return "aligned"
    if correlation <= PEER_CORRELATION_DIVERGENCE_THRESHOLD or (
        spread_pct is not None and abs(spread_pct) >= PEER_CORRELATION_SPREAD_DIVERGENCE_PCT
    ):
        return "diverging"
    return "insufficient_evidence"


def _peer_evidence_summary(symbol: str, peer_symbol: str, state: str) -> str:
    if state == "aligned":
        return f"{symbol} moved with {peer_symbol} over the local overlap window."
    if state == "diverging":
        return f"{symbol} moved away from {peer_symbol} over the local overlap window."
    return f"Local overlap was not enough to compare {symbol} with {peer_symbol}."


def _peer_correlation_state(peer_evidence: Sequence[Mapping[str, Any]]) -> str:
    if len(peer_evidence) < PEER_CORRELATION_MIN_PEERS:
        return "insufficient_evidence"
    aligned_count = sum(1 for item in peer_evidence if item.get("state") == "aligned")
    diverging_count = sum(1 for item in peer_evidence if item.get("state") == "diverging")
    majority = (len(peer_evidence) // 2) + 1
    if diverging_count >= majority:
        return "diverging"
    if aligned_count >= majority:
        return "aligned"
    return "insufficient_evidence"


def _stale_peer_inputs(
    *,
    ticker: str,
    target_latest: date | None,
    peer_symbols: Sequence[str],
    latest_by_symbol: Mapping[str, date | None],
    newest_date: date,
) -> list[str]:
    stale: list[str] = []
    if target_latest is not None and target_latest < newest_date:
        stale.append(f"Local daily OHLCV for {ticker} does not reach the newest peer date.")
    for peer_symbol in peer_symbols:
        peer_latest = latest_by_symbol.get(peer_symbol)
        if peer_latest is not None and peer_latest < newest_date:
            stale.append(f"Local daily OHLCV for {peer_symbol} does not reach the newest peer date.")
    return stale


def _peer_research_next_steps(correlation_state: str, missing_inputs: Sequence[str]) -> list[str]:
    if missing_inputs or correlation_state == "insufficient_evidence":
        return [
            "Add verified local peer group metadata before interpreting peer movement.",
            "Load recent local daily OHLCV for the symbol and at least two verified peers.",
        ]
    if correlation_state == "aligned":
        return [
            "Compare company-specific evidence against the peer movement context.",
            "Refresh local peer OHLCV before reusing this observation window.",
        ]
    return [
        "Check whether company-specific evidence explains the peer divergence.",
        "Refresh local peer OHLCV before reusing this observation window.",
    ]


def _row_value(row: Any, key: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(key)
    return getattr(row, key, None)


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = _safe_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _coerce_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _normalize_context_source(value: str | None) -> str | None:
    text = _safe_text(value)
    if not text:
        return None
    return _SOURCE_CONTEXT_ALIASES.get(text.lower())


def _build_source_context(
    *,
    context_source: str | None,
    context_section: str | None,
    context_reason: str | None,
) -> dict[str, str] | None:
    normalized_source = _normalize_context_source(context_source)
    if normalized_source is None:
        return None
    spec = _SOURCE_CONTEXT_SPECS.get(normalized_source)
    if spec is None:
        return None
    normalized_section = _safe_text(context_section) or str(spec["defaultSection"])
    section_reasons = spec["sectionReasons"]
    if normalized_section not in section_reasons:
        return None
    del context_reason
    return {
        "source": normalized_source,
        "label": str(spec["label"]),
        "route": str(spec["route"]),
        "section": normalized_section,
        "reason": str(section_reasons[normalized_section]),
    }


def _source_context_issue(*, context_source: str | None, context_section: str | None) -> str | None:
    if not _safe_text(context_source):
        return None
    normalized_source = _normalize_context_source(context_source)
    if normalized_source is None:
        return "source_context_unsupported"
    spec = _SOURCE_CONTEXT_SPECS.get(normalized_source)
    if spec is None:
        return "source_context_unsupported"
    normalized_section = _safe_text(context_section) or str(spec["defaultSection"])
    if normalized_section not in spec["sectionReasons"]:
        return "source_context_unsupported"
    return None


def _safe_text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = _safe_text(value)
        return [text] if text else []
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        return []
    items: list[str] = []
    for item in value:
        text = _safe_text(item)
        if text:
            items.append(text)
    return _dedupe(items)


def _safe_mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            items.append(dict(item))
    return items


def _build_degraded_inputs(
    *,
    data_quality: Mapping[str, Any],
    missing_evidence: Sequence[Mapping[str, Any]],
    source_context_issue: str | None,
    symbol_issue: str | None,
) -> list[dict[str, str]]:
    degraded: list[dict[str, str]] = []
    if symbol_issue:
        degraded.append(
            {
                "section": "symbol",
                "status": "unavailable",
                "reason": "symbol_review_required",
            }
        )
    status = str(data_quality.get("status") or "")
    reason = str(data_quality.get("reason") or "")
    if status == "unavailable" and not symbol_issue:
        degraded.append({"section": "structureEvidence", "status": "unavailable", "reason": reason or "history_unavailable"})
    elif status in {"partial", "insufficient"} and not symbol_issue:
        degraded.append({"section": "structureEvidence", "status": "degraded", "reason": reason or "history_partial"})

    if any(str(item.get("kind") or "") == "benchmark_ohlcv" for item in missing_evidence):
        degraded.append(
            {
                "section": "comparativeContext",
                "status": "degraded",
                "reason": "benchmark_ohlcv_unavailable",
            }
        )

    if source_context_issue:
        degraded.append(
            {
                "section": "sourceContext",
                "status": "degraded",
                "reason": source_context_issue,
            }
        )

    return degraded


def _build_detail_consumer_issues(
    *,
    data_quality: Mapping[str, Any],
    missing_evidence: Sequence[Mapping[str, Any]],
    risk_observations: Sequence[str],
    needs_more_evidence: Sequence[str],
    source_context_issue: str | None,
    symbol_issue: str | None,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    status = str(data_quality.get("status") or "")
    if symbol_issue:
        issues.append(dict(_SYMBOL_REVIEW_ISSUE))
        issues[-1]["message"] = symbol_issue
    elif status == "unavailable":
        issues.append(dict(_STRUCTURE_UNAVAILABLE_ISSUE))
    elif status in {"partial", "insufficient"}:
        issues.append(dict(_STRUCTURE_PARTIAL_ISSUE))

    if source_context_issue:
        issues.append(dict(_SOURCE_CONTEXT_ERROR))

    issue_codes = [str(item.get("kind") or "") for item in missing_evidence if isinstance(item, Mapping)]
    issue_codes.extend(_normalise_issue_codes(risk_observations))
    issue_codes.extend(_normalise_issue_codes(needs_more_evidence))
    if issue_codes:
        issues.extend(build_consumer_issues(issue_codes))
    return _dedupe_issues(issues)


def _normalise_issue_codes(values: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = _safe_text(value)
        if not text:
            continue
        normalized.append(text)
    return normalized


def _dedupe(values: Sequence[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = _safe_text(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _append_unique(values: list[str], value: str) -> None:
    text = _safe_text(value)
    if text and text not in values:
        values.append(text)


def _dedupe_issues(issues: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for issue in issues:
        item = {
            "label": str(issue.get("label") or ""),
            "message": str(issue.get("message") or ""),
            "severity": str(issue.get("severity") or ""),
            "category": str(issue.get("category") or ""),
        }
        key = (item["label"], item["message"], item["severity"], item["category"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _normalize_ticker(ticker: str) -> str:
    return str(ticker or "").strip().upper()


def _normalize_unique_tickers(tickers: Sequence[str]) -> list[str]:
    normalized = []
    seen = set()
    for ticker in tickers:
        value = _normalize_ticker(ticker)
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _bounded_batch_max_items(value: int | None) -> int:
    if value is None:
        return DEFAULT_STRUCTURE_DECISION_BATCH_MAX_ITEMS
    try:
        requested = int(value)
    except (TypeError, ValueError):
        return DEFAULT_STRUCTURE_DECISION_BATCH_MAX_ITEMS
    return max(1, min(requested, MAX_STRUCTURE_DECISION_BATCH_ITEMS))


def _normalize_timeout_seconds(value: float | None) -> float:
    if value is None:
        return DEFAULT_STRUCTURE_DECISION_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_STRUCTURE_DECISION_TIMEOUT_SECONDS
    if not math.isfinite(parsed) or parsed <= 0:
        return DEFAULT_STRUCTURE_DECISION_TIMEOUT_SECONDS
    return parsed


def _history_bars(history: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    data = history.get("data")
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, Mapping)]


def _build_data_quality(history: Mapping[str, Any], bars: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    diagnostics = history.get("diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    source = _safe_text(history.get("source")) or "unavailable"
    reason = _safe_text(diagnostics.get("reason")) or _default_reason(source, bars)
    observed_bars = len(bars)
    usable_bars = _count_usable_ohlcv_bars(bars)
    status = _data_quality_status(
        source=source,
        diagnostic_status=_safe_text(diagnostics.get("status")),
        observed_bars=observed_bars,
        usable_bars=usable_bars,
    )
    return {
        "status": status,
        "source": source,
        "period": "daily",
        "requestedDays": DEFAULT_STRUCTURE_DECISION_HISTORY_DAYS,
        "observedBars": observed_bars,
        "usableBars": usable_bars,
        "reason": reason,
    }


def _data_quality_status(
    *,
    source: str,
    diagnostic_status: str,
    observed_bars: int,
    usable_bars: int,
) -> str:
    normalized_status = diagnostic_status.lower()
    if source == "unavailable" or normalized_status == "unavailable":
        return "unavailable"
    if observed_bars == 0:
        return "unavailable"
    if usable_bars < MIN_REQUIRED_BARS:
        return "insufficient"
    if usable_bars < observed_bars:
        return "partial"
    return "available"


def _default_reason(source: str, bars: Sequence[Mapping[str, Any]]) -> str:
    if source == "unavailable" or not bars:
        return "history_unavailable"
    return "history_available"


def _missing_evidence(
    data_quality: Mapping[str, Any],
    *,
    include_benchmark_missing: bool = True,
) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    status = str(data_quality.get("status") or "")
    usable_bars = int(data_quality.get("usableBars") or 0)
    observed_bars = int(data_quality.get("observedBars") or 0)

    if status == "unavailable":
        missing.append(
            {
                "kind": "daily_ohlcv",
                "message": "Daily OHLCV history is unavailable, so the structure state is low confidence.",
            }
        )
    elif usable_bars < MIN_REQUIRED_BARS:
        missing.append(
            {
                "kind": "sufficient_daily_ohlcv_history",
                "message": "More valid daily OHLCV rows are needed before the structure can be described with confidence.",
            }
        )
    elif usable_bars < observed_bars:
        missing.append(
            {
                "kind": "valid_daily_ohlcv_rows",
                "message": "Some daily OHLCV rows are incomplete or invalid and were not usable.",
            }
        )

    if include_benchmark_missing:
        missing.append(
            {
                "kind": "benchmark_ohlcv",
                "message": "Benchmark OHLCV is not included in this endpoint yet, so relative-strength evidence is neutral.",
            }
        )
    return missing


def _has_comparative_ohlcv(data_quality: Mapping[str, Any]) -> bool:
    status = str(data_quality.get("status") or "")
    usable_bars = int(data_quality.get("usableBars") or 0)
    return status in {"available", "partial"} and usable_bars >= MIN_REQUIRED_BARS


def _apply_relative_strength_ranking(
    items: Sequence[dict[str, Any]],
    benchmark_ticker: str | None,
) -> None:
    if not benchmark_ticker:
        return
    ranked = sorted(
        items,
        key=lambda item: (
            -int(item.get("componentScores", {}).get("relativeStrength") or 0),
            str(item.get("ticker") or ""),
        ),
    )
    for rank, item in enumerate(ranked, start=1):
        context = item.get("comparativeContext")
        if isinstance(context, dict) and context.get("status") == "available":
            context["rank"] = rank


def _build_aggregate_summary(
    items: Sequence[Mapping[str, Any]],
    *,
    requested_count: int,
    max_items: int,
    truncated: bool,
    benchmark_ticker: str | None,
) -> dict[str, Any]:
    return {
        "requestedCount": requested_count,
        "evaluatedCount": len(items),
        "maxItems": max_items,
        "truncated": truncated,
        "structureStateCounts": _structure_state_counts(items),
        "strongestStructures": _strongest_structures(items),
        "weakestEvidence": _weakest_evidence(items),
        "commonRiskFlags": _common_risk_flags(items),
        "relativeStrength": _relative_strength_summary(items, benchmark_ticker),
    }


def _structure_state_counts(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        state = str(item.get("structureState") or "lowConfidence")
        counts[state] = counts.get(state, 0) + 1
    return dict(sorted(counts.items(), key=lambda entry: entry[0]))


def _strongest_structures(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        items,
        key=lambda item: (-_dominant_observation_score(item), str(item.get("ticker") or "")),
    )
    return [
        {
            "ticker": str(item.get("ticker") or ""),
            "structureState": str(item.get("structureState") or "lowConfidence"),
            "score": _dominant_observation_score(item),
            "confidence": str(item.get("confidence") or "low"),
        }
        for item in ranked[:3]
    ]


def _weakest_evidence(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        items,
        key=lambda item: (
            int(item.get("dataQuality", {}).get("usableBars") or 0),
            int(item.get("componentScores", {}).get("evidenceQuality") or 0),
            str(item.get("ticker") or ""),
        ),
    )
    return [
        {
            "ticker": str(item.get("ticker") or ""),
            "status": str(item.get("dataQuality", {}).get("status") or "unavailable"),
            "usableBars": int(item.get("dataQuality", {}).get("usableBars") or 0),
            "evidenceQuality": int(item.get("componentScores", {}).get("evidenceQuality") or 0),
        }
        for item in ranked[:3]
    ]


def _common_risk_flags(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for item in items:
        ticker = str(item.get("ticker") or "")
        risk_flags = item.get("researchNotes", {}).get("riskFlags", [])
        if not isinstance(risk_flags, list):
            continue
        for flag in risk_flags:
            text = _safe_text(flag)
            if not text or text.startswith("No dominant"):
                continue
            record = counts.setdefault(text, {"flag": text, "count": 0, "tickers": []})
            record["count"] += 1
            record["tickers"].append(ticker)
    return sorted(counts.values(), key=lambda item: (-int(item["count"]), str(item["flag"])))[:5]


def _relative_strength_summary(
    items: Sequence[Mapping[str, Any]],
    benchmark_ticker: str | None,
) -> dict[str, Any]:
    if not benchmark_ticker:
        return {
            "status": "unavailable",
            "benchmark": None,
            "ranking": [],
            "reason": "benchmark_ohlcv_unavailable",
        }
    ranked = sorted(
        items,
        key=lambda item: (
            -int(item.get("componentScores", {}).get("relativeStrength") or 0),
            str(item.get("ticker") or ""),
        ),
    )
    return {
        "status": "available",
        "benchmark": benchmark_ticker,
        "ranking": [
            {
                "rank": index,
                "ticker": str(item.get("ticker") or ""),
                "relativeStrengthScore": int(item.get("componentScores", {}).get("relativeStrength") or 0),
                "structureState": str(item.get("structureState") or "lowConfidence"),
            }
            for index, item in enumerate(ranked, start=1)
        ],
    }


def _build_symbol_compare_evidence_packet(
    items: Sequence[Mapping[str, Any]],
    *,
    benchmark_ticker: str | None,
) -> dict[str, Any]:
    compared_symbols = [str(item.get("ticker") or "") for item in items if str(item.get("ticker") or "")]
    missing_by_symbol = {
        symbol: _symbol_compare_missing_evidence(item, benchmark_ticker)
        for symbol, item in zip(compared_symbols, items)
    }
    packet = {
        "comparedSymbols": compared_symbols,
        "sharedEvidence": _symbol_compare_shared_evidence(items, compared_symbols, benchmark_ticker),
        "divergentEvidence": _symbol_compare_divergent_evidence(items, compared_symbols),
        "missingEvidenceBySymbol": missing_by_symbol,
        "freshnessBySymbol": {
            symbol: _symbol_compare_freshness(item)
            for symbol, item in zip(compared_symbols, items)
        },
        "confidenceCap": _symbol_compare_confidence_cap(items, benchmark_ticker),
        "observationBoundary": {
            "observationOnly": True,
            "decisionGrade": False,
            "rankingAllowed": False,
            "adviceAllowed": False,
        },
        "researchNextSteps": _symbol_compare_next_steps(items, compared_symbols, benchmark_ticker, missing_by_symbol),
    }
    return packet


def _symbol_compare_shared_evidence(
    items: Sequence[Mapping[str, Any]],
    compared_symbols: Sequence[str],
    benchmark_ticker: str | None,
) -> list[dict[str, Any]]:
    if not items:
        return []

    shared: list[dict[str, Any]] = []
    data_qualities = [_mapping(item.get("dataQuality")) for item in items]
    if all(
        str(quality.get("status") or "") in {"available", "partial"}
        and int(quality.get("usableBars") or 0) >= MIN_REQUIRED_BARS
        for quality in data_qualities
    ):
        sources = {str(quality.get("source") or "unavailable") for quality in data_qualities}
        shared.append(
            {
                "kind": "daily_ohlcv",
                "symbols": list(compared_symbols),
                "status": "available",
                "period": "daily",
                "source": sources.pop() if len(sources) == 1 else "mixed",
                "usableBarsMin": min(int(quality.get("usableBars") or 0) for quality in data_qualities),
                "usableBarsMax": max(int(quality.get("usableBars") or 0) for quality in data_qualities),
            }
        )

    if benchmark_ticker:
        shared.append(
            {
                "kind": "benchmark_ohlcv",
                "symbols": list(compared_symbols),
                "status": "available",
                "benchmark": benchmark_ticker,
            }
        )
    return shared


def _symbol_compare_divergent_evidence(
    items: Sequence[Mapping[str, Any]],
    compared_symbols: Sequence[str],
) -> list[dict[str, Any]]:
    divergent: list[dict[str, Any]] = []
    _append_divergence(
        divergent,
        kind="structure_state",
        symbols=compared_symbols,
        values={str(item.get("ticker") or ""): str(item.get("structureState") or "lowConfidence") for item in items},
    )
    _append_divergence(
        divergent,
        kind="confidence",
        symbols=compared_symbols,
        values={str(item.get("ticker") or ""): str(item.get("confidence") or "low") for item in items},
    )
    _append_divergence(
        divergent,
        kind="data_quality_status",
        symbols=compared_symbols,
        values={
            str(item.get("ticker") or ""): str(_mapping(item.get("dataQuality")).get("status") or "unavailable")
            for item in items
        },
    )
    risk_values: dict[str, list[str]] = {}
    for item in items:
        symbol = str(item.get("ticker") or "")
        risk_values[symbol] = _safe_text_list(_mapping(item.get("researchNotes")).get("riskFlags"))
    if len({_stable_value(value) for value in risk_values.values()}) > 1:
        divergent.append({"kind": "risk_observations", "symbols": list(compared_symbols), "values": risk_values})
    return divergent


def _append_divergence(
    divergent: list[dict[str, Any]],
    *,
    kind: str,
    symbols: Sequence[str],
    values: Mapping[str, Any],
) -> None:
    if len({_stable_value(value) for value in values.values()}) <= 1:
        return
    divergent.append({"kind": kind, "symbols": list(symbols), "values": dict(values)})


def _symbol_compare_missing_evidence(
    item: Mapping[str, Any],
    benchmark_ticker: str | None,
) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    data_quality = _mapping(item.get("dataQuality"))
    status = str(data_quality.get("status") or "unavailable")
    usable_bars = int(data_quality.get("usableBars") or 0)
    observed_bars = int(data_quality.get("observedBars") or 0)
    if status == "unavailable":
        missing.append(
            {
                "kind": "daily_ohlcv",
                "message": "Daily OHLCV history is unavailable, so this symbol cannot contribute complete comparison evidence.",
            }
        )
    elif usable_bars < MIN_REQUIRED_BARS:
        missing.append(
            {
                "kind": "sufficient_daily_ohlcv_history",
                "message": "More valid daily OHLCV rows are needed before this symbol can be compared with confidence.",
            }
        )
    elif usable_bars < observed_bars:
        missing.append(
            {
                "kind": "valid_daily_ohlcv_rows",
                "message": "Some daily OHLCV rows are incomplete or invalid for this symbol.",
            }
        )

    if not benchmark_ticker:
        missing.append(
            {
                "kind": "benchmark_ohlcv",
                "message": "Benchmark OHLCV is unavailable, so cross-symbol relative evidence is not available.",
            }
        )
    return missing


def _symbol_compare_freshness(item: Mapping[str, Any]) -> dict[str, Any]:
    data_quality = _mapping(item.get("dataQuality"))
    return {
        "status": str(data_quality.get("status") or "unavailable"),
        "source": str(data_quality.get("source") or "unavailable"),
        "period": str(data_quality.get("period") or "daily"),
        "usableBars": int(data_quality.get("usableBars") or 0),
    }


def _symbol_compare_confidence_cap(
    items: Sequence[Mapping[str, Any]],
    benchmark_ticker: str | None,
) -> dict[str, Any]:
    value = 100
    reasons: list[str] = []
    if not items:
        value = min(value, 35)
        _append_unique(reasons, "comparison_symbols_missing")

    for item in items:
        data_quality = _mapping(item.get("dataQuality"))
        status = str(data_quality.get("status") or "unavailable")
        usable_bars = int(data_quality.get("usableBars") or 0)
        if status == "unavailable":
            value = min(value, 35)
            _append_unique(reasons, "symbol_evidence_unavailable")
        elif usable_bars < MIN_REQUIRED_BARS:
            value = min(value, 45)
            _append_unique(reasons, "symbol_evidence_insufficient")
        elif status == "partial":
            value = min(value, 70)
            _append_unique(reasons, "symbol_evidence_partial")
    if not benchmark_ticker:
        value = min(value, 75)
        _append_unique(reasons, "benchmark_ohlcv_unavailable")
    return {
        "value": value,
        "reasonCodes": reasons,
        "policyVersion": SYMBOL_COMPARE_EVIDENCE_PACKET_VERSION,
    }


def _symbol_compare_next_steps(
    items: Sequence[Mapping[str, Any]],
    compared_symbols: Sequence[str],
    benchmark_ticker: str | None,
    missing_by_symbol: Mapping[str, Sequence[Mapping[str, str]]],
) -> list[str]:
    steps: list[str] = []
    for symbol, item in zip(compared_symbols, items):
        data_quality = _mapping(item.get("dataQuality"))
        status = str(data_quality.get("status") or "unavailable")
        usable_bars = int(data_quality.get("usableBars") or 0)
        if status == "unavailable":
            _append_unique(steps, f"Add daily OHLCV evidence for {symbol} before using divergence observations.")
        elif usable_bars < MIN_REQUIRED_BARS:
            _append_unique(steps, f"Add more valid daily OHLCV rows for {symbol}.")
        elif any(str(item.get("kind") or "") == "valid_daily_ohlcv_rows" for item in missing_by_symbol.get(symbol, [])):
            _append_unique(steps, f"Review incomplete daily OHLCV rows for {symbol}.")
    if not benchmark_ticker:
        _append_unique(steps, "Add benchmark OHLCV evidence to enable cross-symbol relative context.")
    return steps


def _dominant_observation_score(item: Mapping[str, Any]) -> int:
    scores = item.get("componentScores")
    scores = scores if isinstance(scores, Mapping) else {}
    state = str(item.get("structureState") or "lowConfidence")
    score_key_by_state = {
        "uptrend": "trend",
        "breakout": "breakoutQuality",
        "pullback": "pullbackHealth",
        "consolidation": "volatilityCompression",
        "extended": "riskExtension",
        "distribution": "volumePressure",
        "breakdown": "volumePressure",
        "mixed": "evidenceQuality",
        "lowConfidence": "evidenceQuality",
    }
    key = score_key_by_state.get(state, "evidenceQuality")
    return int(scores.get(key) or 0)


def _batch_missing_evidence(
    items: Sequence[Mapping[str, Any]],
    benchmark_available: bool,
) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    statuses = {str(item.get("dataQuality", {}).get("status") or "") for item in items}
    if not benchmark_available:
        missing.append(
            {
                "kind": "benchmark_ohlcv",
                "message": "Benchmark OHLCV is unavailable, so relative-strength ranking is unavailable.",
            }
        )
    if "unavailable" in statuses:
        missing.append(
            {
                "kind": "daily_ohlcv",
                "message": "At least one symbol has unavailable daily OHLCV evidence.",
            }
        )
    if "insufficient" in statuses:
        missing.append(
            {
                "kind": "sufficient_daily_ohlcv_history",
                "message": "At least one symbol needs more valid daily OHLCV rows.",
            }
        )
    if "partial" in statuses:
        missing.append(
            {
                "kind": "valid_daily_ohlcv_rows",
                "message": "At least one symbol has incomplete or invalid daily OHLCV rows.",
            }
        )
    return missing


def _batch_data_quality(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = {
        "availableCount": 0,
        "partialCount": 0,
        "insufficientCount": 0,
        "unavailableCount": 0,
    }
    for item in items:
        status = str(item.get("dataQuality", {}).get("status") or "unavailable")
        if status == "available":
            counts["availableCount"] += 1
        elif status == "partial":
            counts["partialCount"] += 1
        elif status == "insufficient":
            counts["insufficientCount"] += 1
        else:
            counts["unavailableCount"] += 1
    if not items or counts["unavailableCount"] == len(items):
        status = "unavailable"
    elif counts["partialCount"] or counts["insufficientCount"] or counts["unavailableCount"]:
        status = "partial"
    else:
        status = "available"
    return {"status": status, **counts}


def _count_usable_ohlcv_bars(bars: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for bar in bars:
        open_value = _to_float(bar.get("open"))
        high_value = _to_float(bar.get("high"))
        low_value = _to_float(bar.get("low"))
        close_value = _to_float(bar.get("close"))
        volume_value = _to_float(bar.get("volume"))
        if None in (open_value, high_value, low_value, close_value, volume_value):
            continue
        if min(open_value, high_value, low_value, close_value) <= 0 or volume_value < 0:
            continue
        if high_value < max(open_value, close_value) or low_value > min(open_value, close_value):
            continue
        count += 1
    return count


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _stable_value(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(sorted((str(key), _stable_value(item)) for key, item in value.items()))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return str([_stable_value(item) for item in value])
    return str(value)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in {float("inf"), float("-inf")}:
        return None
    return result


def _safe_text(value: Any) -> str:
    return str(value or "").strip()
