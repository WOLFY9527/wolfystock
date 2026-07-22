"""Truthful, history-backed stock technical-indicator read service."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from types import MappingProxyType
from typing import Any

from src.services.historical_market_data_foundation import (
    HistoricalBarQualityOutcome,
    normalize_provider_historical_bars,
    resolve_historical_symbol_identity,
)
from src.services.rule_backtest_service import (
    build_rule_indicator_bollinger,
    build_rule_indicator_ema,
    build_rule_indicator_rsi,
    build_rule_indicator_sma,
)
from src.services.stock_service import StockService


STOCK_TECHNICAL_INDICATORS_CONTRACT_VERSION = "stock_technical_indicators_v1"
STOCK_TECHNICAL_INDICATORS_SCHEMA_VERSION = "stock_technical_indicators_v1"
TECHNICAL_INDICATOR_TIMEFRAME = "daily"
TECHNICAL_HISTORY_LOOKBACK_DAYS = 260

# This is the single minimum-window authority for the public indicator map.
INDICATOR_MINIMUM_BARS = MappingProxyType(
    {
        "sma20": 20,
        "sma50": 50,
        "sma200": 200,
        "ema12": 12,
        "ema26": 26,
        "rsi14": 15,
        "macd": 26,
        "macdSignal": 34,
        "macdHistogram": 34,
        "bollingerUpper": 20,
        "bollingerMiddle": 20,
        "bollingerLower": 20,
    }
)

NO_ADVICE_DISCLOSURE = (
    "Observation-only technical indicator context; no personalized action instruction."
)
_INDICATOR_KEYS = tuple(INDICATOR_MINIMUM_BARS)
_PROVIDER_FAILURE_REASONS = {
    "provider_missing",
    "provider_unavailable",
    "history_lookup_failed",
    "history_request_failed",
    "provider_runtime_unavailable",
}


class StockTechnicalIndicatorsService:
    """Calculate only indicators qualified by validated adjusted history."""

    def __init__(self, history_service: Any | None = None) -> None:
        self.history_service = history_service if history_service is not None else StockService()

    def get_technical_indicators(self, stock_code: str) -> dict[str, Any]:
        requested_symbol = str(stock_code or "").strip()
        symbol = resolve_historical_symbol_identity(symbol=requested_symbol)["canonical_symbol"]
        if not symbol:
            return self._empty_payload(
                symbol,
                status="unavailable",
                reason="invalid_symbol",
                source="unavailable",
                source_label="History unavailable",
            )

        # The existing StockService remains the sole history/provider authority.
        history = self.history_service.get_history_data(
            stock_code=symbol,
            period=TECHNICAL_INDICATOR_TIMEFRAME,
            days=TECHNICAL_HISTORY_LOOKBACK_DAYS,
        )
        if not isinstance(history, Mapping):
            return self._empty_payload(
                symbol,
                status="provider_unavailable",
                reason="history_response_invalid",
                source="unavailable",
                source_label="History unavailable",
            )

        metadata = self._lineage(history)
        rows = history.get("data")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            rows = []

        diagnostics = history.get("diagnostics")
        diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
        readiness = history.get("historicalOhlcvReadiness")
        readiness = readiness if isinstance(readiness, Mapping) else {}
        source_reason = self._first_text(
            diagnostics.get("reason"),
            history.get("unavailableReason"),
            readiness.get("providerState") if readiness.get("providerState") in _PROVIDER_FAILURE_REASONS else None,
        )
        source_state = str(diagnostics.get("status") or "").strip().lower()
        provider_state = str(readiness.get("providerState") or "").strip().lower()
        runtime_state = str(readiness.get("runtimeStatus") or "").strip().lower()
        if (
            metadata["isUnavailable"]
            or metadata["source"] == "unavailable"
            or source_state in {"unavailable", "error", "failed", "failure"}
            or provider_state in _PROVIDER_FAILURE_REASONS
            or runtime_state in {"unavailable", "error", "failed", "failure"}
            or source_reason in _PROVIDER_FAILURE_REASONS
        ):
            return self._empty_payload(
                symbol,
                status="provider_unavailable",
                reason=source_reason or "provider_unavailable",
                source=metadata["source"],
                provider=metadata["provider"],
                source_label=metadata["sourceLabel"],
                as_of=metadata["asOf"],
                freshness=metadata["freshness"],
                adjustment_status=metadata["adjustmentStatus"],
                observed_bars=len(rows),
            )
        if metadata["isStale"] or metadata["freshness"] == "stale" or readiness.get("freshnessState") == "stale":
            return self._empty_payload(
                symbol,
                status="unavailable",
                reason="stale_history",
                source=metadata["source"],
                provider=metadata["provider"],
                source_label=metadata["sourceLabel"],
                as_of=metadata["asOf"],
                freshness=metadata["freshness"],
                adjustment_status=metadata["adjustmentStatus"],
                observed_bars=len(rows),
            )
        if not rows:
            return self._empty_payload(
                symbol,
                status="unavailable",
                reason=(
                    source_reason
                    if source_state in {"unavailable", "error", "failed", "failure"}
                    or source_reason in _PROVIDER_FAILURE_REASONS
                    else "history_unavailable"
                ),
                source=metadata["source"] or "unavailable",
                provider=metadata["provider"],
                source_label=metadata["sourceLabel"],
                as_of=metadata["asOf"],
                freshness=metadata["freshness"],
                adjustment_status=metadata["adjustmentStatus"],
            )

        bars, invalid_reason = self._validated_bars(symbol, rows, history)
        if invalid_reason is not None:
            return self._empty_payload(
                symbol,
                status="invalid_history",
                reason=invalid_reason,
                source=metadata["source"],
                provider=metadata["provider"],
                source_label=metadata["sourceLabel"],
                as_of=metadata["asOf"],
                freshness=metadata["freshness"],
                observed_bars=len(rows),
                adjustment_status=metadata["adjustmentStatus"],
            )

        adjusted_closes = [float(bar.adjustment_metadata["adjustedClose"]) for bar in bars]
        as_of = metadata["asOf"] or bars[-1].session_date.isoformat()
        indicator_series = self._calculate_series(adjusted_closes)
        indicators: dict[str, dict[str, Any]] = {}
        available_count = 0
        non_finite_result = False
        for key in _INDICATOR_KEYS:
            series = indicator_series[key]
            required = INDICATOR_MINIMUM_BARS[key]
            value = series[-1] if len(adjusted_closes) >= required and series else None
            if value is not None and self._is_finite(value):
                available_count += 1
                indicators[key] = self._indicator_value(
                    value=float(value),
                    status="available",
                    required=required,
                    available=len(adjusted_closes),
                    as_of=as_of,
                )
            else:
                if len(adjusted_closes) >= required:
                    non_finite_result = True
                indicators[key] = self._indicator_value(
                    value=None,
                    status="unavailable",
                    required=required,
                    available=len(adjusted_closes),
                    reason="non_finite_result" if len(adjusted_closes) >= required else "insufficient_history",
                    as_of=as_of,
                )

        if non_finite_result:
            status = "invalid_history"
            reason = "non_finite_result"
        elif available_count == len(_INDICATOR_KEYS):
            status = "available"
            reason = "history_sufficient"
        elif available_count:
            status = "partial"
            reason = "partial_indicator_coverage"
        else:
            status = "insufficient_history"
            reason = "insufficient_history"

        return self._payload(
            symbol=symbol,
            status=status,
            reason=reason,
            source=metadata["source"],
            provider=metadata["provider"],
            source_label=metadata["sourceLabel"],
            as_of=as_of,
            freshness=metadata["freshness"],
            adjustment_status="adjusted",
            observed_bars=len(rows),
            valid_bars=len(bars),
            indicators=indicators,
            usable_range={
                "start": bars[0].session_date.isoformat(),
                "end": bars[-1].session_date.isoformat(),
            },
        )

    @staticmethod
    def _lineage(history: Mapping[str, Any]) -> dict[str, Any]:
        confidence = history.get("sourceConfidence")
        confidence = confidence if isinstance(confidence, Mapping) else {}
        source = str(confidence.get("source") or history.get("source") or "unknown").strip() or "unknown"
        source_label = str(confidence.get("sourceLabel") or "").strip() or source.replace("_", " ").title()
        freshness = str(confidence.get("freshness") or "").strip() or None
        as_of = StockTechnicalIndicatorsService._first_text(
            confidence.get("asOf"),
            history.get("asOf"),
        )
        return {
            "source": source,
            "provider": str(confidence.get("provider") or history.get("provider") or "").strip() or None,
            "sourceLabel": source_label,
            "asOf": as_of,
            "freshness": freshness,
            "isStale": bool(confidence.get("isStale")),
            "isUnavailable": bool(confidence.get("isUnavailable"))
            or freshness == "unavailable",
            "adjustmentStatus": StockTechnicalIndicatorsService._adjustment_status(history),
        }

    @staticmethod
    def _adjustment_status(history: Mapping[str, Any]) -> str:
        readiness = history.get("historicalOhlcvReadiness")
        readiness = readiness if isinstance(readiness, Mapping) else {}
        raw = history.get("adjustmentStatus") or readiness.get("adjustmentState")
        status = str(raw or "").strip().lower()
        if status in {"available", "adjusted"}:
            return "adjusted"
        if status in {"unadjusted", "raw"}:
            return "unadjusted"
        if status in {"missing", "unknown", "not_required"}:
            return status
        return "unknown"

    @staticmethod
    def _validated_bars(
        symbol: str,
        rows: Sequence[Any],
        history: Mapping[str, Any],
    ) -> tuple[list[Any], str | None]:
        source = str(history.get("source") or "unknown")
        confidence = history.get("sourceConfidence")
        confidence = confidence if isinstance(confidence, Mapping) else {}
        as_of = confidence.get("asOf") or history.get("asOf")
        observed_at = confidence.get("observedAt") or as_of
        normalized_rows = list(rows)
        if any(not isinstance(row, Mapping) for row in normalized_rows):
            return [], "malformed_history_row"
        canonical = normalize_provider_historical_bars(
            {
                "provider": confidence.get("provider") or source,
                "source": source,
                "symbol": symbol,
                "market": "US" if symbol.isalpha() else None,
                "interval": "1d",
                "asOf": as_of,
                "observedAt": observed_at,
                "rows": normalized_rows,
            },
            preserve_provider_order=True,
        )
        if len(canonical) != len(normalized_rows):
            return [], "malformed_history_row"
        quality = HistoricalBarQualityOutcome.evaluate(canonical)
        if "non_monotonic_ordering" in quality.reason_codes:
            return [], "non_monotonic_ordering"
        if "conflicting_duplicate_bar" in quality.reason_codes or "duplicate_bar" in quality.reason_codes:
            return [], "duplicate_bar"
        previous_date: date | None = None
        for bar in canonical:
            if previous_date is not None and bar.session_date <= previous_date:
                return [], "duplicate_bar" if bar.session_date == previous_date else "non_monotonic_ordering"
            previous_date = bar.session_date
            if bar.session_date == date.min:
                return [], "malformed_timestamp"
            if any(not StockTechnicalIndicatorsService._is_finite(getattr(bar, field)) for field in ("open", "high", "low", "close", "volume")):
                return [], "non_finite_bar_value"
            if any(getattr(bar, field) <= 0 for field in ("open", "high", "low", "close")) or bar.volume < 0:
                return [], "invalid_bar_value"
            adjusted = bar.adjustment_metadata.get("adjustedClose")
            if not StockTechnicalIndicatorsService._is_finite(adjusted) or float(adjusted) <= 0:
                return [], "missing_adjusted_close"
        if quality.state == "rejected":
            return [], quality.reason_codes[0] if quality.reason_codes else "invalid_history"
        return canonical, None

    @staticmethod
    def _calculate_series(closes: Sequence[float]) -> dict[str, list[float | None]]:
        sma20 = build_rule_indicator_sma(closes, 20)
        sma50 = build_rule_indicator_sma(closes, 50)
        sma200 = build_rule_indicator_sma(closes, 200)
        ema12 = build_rule_indicator_ema(closes, 12)
        ema26 = build_rule_indicator_ema(closes, 26)
        rsi14 = build_rule_indicator_rsi(closes, 14)
        macd = [
            (fast - slow) if fast is not None and slow is not None else None
            for fast, slow in zip(ema12, ema26)
        ]
        macd_signal = build_rule_indicator_ema(macd, 9)
        macd_histogram = [
            (line - signal) if line is not None and signal is not None else None
            for line, signal in zip(macd, macd_signal)
        ]
        bollinger_middle, bollinger_upper, bollinger_lower = build_rule_indicator_bollinger(
            closes,
            20,
            2.0,
        )
        return {
            "sma20": sma20,
            "sma50": sma50,
            "sma200": sma200,
            "ema12": ema12,
            "ema26": ema26,
            "rsi14": rsi14,
            "macd": macd,
            "macdSignal": macd_signal,
            "macdHistogram": macd_histogram,
            "bollingerUpper": bollinger_upper,
            "bollingerMiddle": bollinger_middle,
            "bollingerLower": bollinger_lower,
        }

    @staticmethod
    def _indicator_value(
        *,
        value: float | None,
        status: str,
        required: int,
        available: int,
        reason: str | None = None,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        return {
            "value": value,
            "status": status,
            "requiredBars": required,
            "availableBars": available,
            "reason": reason,
            "asOf": as_of,
        }

    @classmethod
    def _empty_payload(cls, symbol: str, *, status: str, reason: str, **kwargs: Any) -> dict[str, Any]:
        observed_bars = int(kwargs.pop("observed_bars", 0) or 0)
        adjustment_status = str(kwargs.pop("adjustment_status", "missing") or "missing")
        return cls._payload(
            symbol=symbol,
            status=status,
            reason=reason,
            observed_bars=observed_bars,
            valid_bars=0,
            indicators={
                key: cls._indicator_value(
                    value=None,
                    status="unavailable",
                    required=required,
                    available=0,
                    reason=reason,
                    as_of=kwargs.get("as_of"),
                )
                for key, required in INDICATOR_MINIMUM_BARS.items()
            },
            adjustment_status=adjustment_status,
            usable_range={"start": None, "end": None},
            **kwargs,
        )

    @staticmethod
    def _payload(
        *,
        symbol: str,
        status: str,
        reason: str,
        observed_bars: int,
        valid_bars: int,
        indicators: Mapping[str, Any],
        adjustment_status: str,
        usable_range: Mapping[str, Any],
        source: str | None = None,
        provider: str | None = None,
        source_label: str | None = None,
        as_of: str | None = None,
        freshness: str | None = None,
    ) -> dict[str, Any]:
        required_bars = max(INDICATOR_MINIMUM_BARS.values())
        return {
            "contractVersion": STOCK_TECHNICAL_INDICATORS_CONTRACT_VERSION,
            "schemaVersion": STOCK_TECHNICAL_INDICATORS_SCHEMA_VERSION,
            "symbol": symbol,
            "status": status,
            "timeframe": TECHNICAL_INDICATOR_TIMEFRAME,
            "source": source,
            "provider": provider,
            "sourceLabel": source_label,
            "asOf": as_of,
            "freshness": freshness,
            "adjustmentStatus": adjustment_status,
            "validBars": valid_bars,
            "requiredBars": required_bars,
            "dataQuality": {
                "status": status,
                "reason": reason,
                "requiredBars": required_bars,
                "observedBars": observed_bars,
                "validBars": valid_bars,
                "usableBars": valid_bars,
                "missingBars": max(required_bars - valid_bars, 0),
                "adjustmentStatus": adjustment_status,
                "freshness": freshness,
                "freshnessState": freshness,
                "usableRange": dict(usable_range),
            },
            "indicators": dict(indicators),
            "reason": reason,
            "message": _status_message(status),
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        }

    @staticmethod
    def _is_finite(value: Any) -> bool:
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError, OverflowError):
            return False

    @staticmethod
    def _first_text(*values: Any) -> str | None:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return None


def _status_message(status: str) -> str:
    return {
        "available": "Technical indicators are available from qualified adjusted history.",
        "partial": "Some technical indicators are available; the remaining windows are insufficient.",
        "unavailable": "Technical indicators are unavailable because qualified history is absent or stale.",
        "insufficient_history": "Technical indicators are unavailable because history is insufficient.",
        "invalid_history": "Technical indicators are unavailable because history failed validation.",
        "provider_unavailable": "Technical indicators are unavailable because the history source failed.",
    }.get(status, "Technical indicators are unavailable.")


__all__ = [
    "INDICATOR_MINIMUM_BARS",
    "NO_ADVICE_DISCLOSURE",
    "STOCK_TECHNICAL_INDICATORS_CONTRACT_VERSION",
    "STOCK_TECHNICAL_INDICATORS_SCHEMA_VERSION",
    "StockTechnicalIndicatorsService",
]
