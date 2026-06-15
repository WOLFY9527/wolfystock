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


class StockStructureDecisionService:
    """Build observation-only stock structure decisions from existing OHLCV access."""

    def __init__(self, history_service: Any | None = None) -> None:
        self.history_service = history_service or StockService()

    def get_structure_decision(self, ticker: str) -> dict[str, Any]:
        normalized_ticker = _normalize_ticker(ticker)
        history = self._load_daily_history(normalized_ticker)
        bars = _history_bars(history)
        data_quality = _build_data_quality(history, bars)
        engine_result = build_stock_structure_decision(bars)
        missing_evidence = _missing_evidence(data_quality)

        return {
            "schemaVersion": STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION,
            "ticker": normalized_ticker,
            "structureState": engine_result.get("structureState", "lowConfidence"),
            "confidence": engine_result.get("confidence", "low"),
            "componentScores": engine_result.get("componentScores", {}),
            "explanation": engine_result.get("explanation", {}),
            "researchNotes": engine_result.get("researchNotes", {}),
            "dataQuality": data_quality,
            "missingEvidence": missing_evidence,
            "noAdviceDisclosure": engine_result.get("noAdviceDisclosure") or NO_ADVICE_DISCLOSURE,
        }

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


def _missing_evidence(data_quality: Mapping[str, Any]) -> list[dict[str, str]]:
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

    missing.append(
        {
            "kind": "benchmark_ohlcv",
            "message": "Benchmark OHLCV is not included in this endpoint yet, so relative-strength evidence is neutral.",
        }
    )
    return missing


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
