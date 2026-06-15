# -*- coding: utf-8 -*-
"""Safe API-facing service for stock structure decisions."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from src.services.stock_service import StockService
from src.services.stock_structure_decision_engine import (
    MIN_REQUIRED_BARS,
    NO_ADVICE_DISCLOSURE,
    build_stock_structure_decision,
)


logger = logging.getLogger(__name__)

STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION = "stock_structure_decision_api_v1"
DEFAULT_STRUCTURE_DECISION_HISTORY_DAYS = 90
DEFAULT_STRUCTURE_DECISION_BATCH_MAX_ITEMS = 25
MAX_STRUCTURE_DECISION_BATCH_ITEMS = 50


class StockStructureDecisionService:
    """Build observation-only stock structure decisions from existing OHLCV access."""

    def __init__(self, history_service: Any | None = None) -> None:
        self.history_service = history_service or StockService()

    def get_structure_decision(self, ticker: str) -> dict[str, Any]:
        normalized_ticker = _normalize_ticker(ticker)
        return self._build_structure_decision(normalized_ticker)

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
        return payload

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
