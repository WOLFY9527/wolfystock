from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import pandas as pd

from src.core.scanner_profile import ScannerMarketProfile
from src.services.historical_ohlcv_readiness import (
    HistoricalOhlcvAcquisitionResult,
    HistoricalOhlcvProvider,
    HistoricalOhlcvReadinessRequest,
    HistoricalOhlcvReadinessService,
)


SCANNER_OHLCV_READINESS_CONTRACT_VERSION = "scanner_ohlcv_readiness_v1"
SCANNER_OHLCV_BLOCKING_REQUIREMENTS = frozenset(
    {
        "provider_missing",
        "provider_unavailable",
        "entitlement_required",
        "insufficient_history",
    }
)
SCANNER_OHLCV_DEGRADED_REQUIREMENTS = frozenset(
    {
        "stale_data",
        "missing_adjustments",
        "missing_benchmark",
        "missing_market_context",
        "missing_factor_inputs",
    }
)
SAFE_HISTORICAL_OHLCV_READINESS_KEYS = frozenset(
    {
        "contractVersion",
        "symbol",
        "market",
        "timeframe",
        "requestedRange",
        "lookbackBars",
        "requiredBars",
        "usableBars",
        "missingBars",
        "freshnessState",
        "adjustmentState",
        "benchmarkState",
        "providerState",
        "overallState",
        "missingRequirements",
        "consumerSafe",
    }
)


def build_scanner_historical_ohlcv_readiness(
    *,
    symbol: str,
    profile: ScannerMarketProfile,
    history_df: pd.DataFrame,
    history_diag: Mapping[str, Any],
    readiness_service: HistoricalOhlcvReadinessService,
    historical_ohlcv_provider: HistoricalOhlcvProvider | None = None,
    require_adjusted: bool = False,
) -> HistoricalOhlcvAcquisitionResult:
    request = HistoricalOhlcvReadinessRequest(
        symbol=symbol,
        market=profile.market,
        timeframe="1d",
        lookback_bars=int(profile.history_days or 0),
        required_bars=int(profile.min_history_bars or 0),
        end=date.today() if historical_ohlcv_provider is not None else None,
        require_adjusted=bool(require_adjusted),
    )
    if historical_ohlcv_provider is not None:
        return readiness_service.fetch(request)

    return readiness_service.assess_supplied_history(
        request,
        _history_frame_records(history_df),
        source_available=_history_source_available(history_df, history_diag),
        unavailable_reason=_safe_unavailable_reason(history_diag),
        adjustments_available=_adjustments_available(history_diag),
        freshness_state=_freshness_state(history_diag),
    )


def historical_ohlcv_readiness_blocks_scanner(readiness: Mapping[str, Any]) -> bool:
    missing_requirements = _text_list(readiness.get("missingRequirements"))
    if any(item in SCANNER_OHLCV_BLOCKING_REQUIREMENTS for item in missing_requirements):
        return True
    return _text(readiness.get("overallState")).lower() == "blocked"


def sanitize_historical_ohlcv_readiness(readiness: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(readiness, Mapping) or not readiness:
        return {}
    sanitized = {
        key: value
        for key, value in readiness.items()
        if key in SAFE_HISTORICAL_OHLCV_READINESS_KEYS
    }
    if not sanitized:
        return {}
    sanitized["missingRequirements"] = _dedupe(_text_list(sanitized.get("missingRequirements")))
    for key in ("requiredBars", "usableBars", "missingBars", "lookbackBars"):
        if key in sanitized:
            sanitized[key] = _safe_int(sanitized.get(key))
    sanitized["consumerSafe"] = True
    return sanitized


def summarize_scanner_ohlcv_readiness(
    *,
    market: str,
    profile: str,
    diagnostics: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    readiness_items = _collect_readiness_items(diagnostics=diagnostics, candidates=candidates)
    benchmark_missing = _benchmark_missing(diagnostics)
    if not readiness_items:
        missing_requirements = ["missing_benchmark"] if benchmark_missing else []
        availability_state = "degraded" if benchmark_missing else "unknown"
        execution_state = "degraded" if benchmark_missing else "unknown"
        overall_state = "degraded" if benchmark_missing else "unknown"
        return {
            "contractVersion": SCANNER_OHLCV_READINESS_CONTRACT_VERSION,
            "market": _text(market).lower() or "unknown",
            "profile": _text(profile) or "unknown",
            "availabilityState": availability_state,
            "executionState": execution_state,
            "overallState": overall_state,
            "requiredBars": 0,
            "usableBars": 0,
            "missingBars": 0,
            "missingRequirements": missing_requirements,
            "blockedSymbols": [],
            "degradedSymbols": [],
            "symbolStates": [],
            "consumerSafe": True,
        }

    missing_requirements: list[str] = []
    blocked_symbols: list[str] = []
    degraded_symbols: list[str] = []
    symbol_states: list[dict[str, Any]] = []
    required_bars = 0
    usable_bars_values: list[int] = []
    missing_bars = 0

    for readiness in readiness_items:
        symbol = _text(readiness.get("symbol")).upper()
        requirements = _text_list(readiness.get("missingRequirements"))
        missing_requirements.extend(requirements)
        required_bars = max(required_bars, _safe_int(readiness.get("requiredBars")))
        usable_bars_values.append(_safe_int(readiness.get("usableBars")))
        missing_bars = max(missing_bars, _safe_int(readiness.get("missingBars")))
        overall_state = _text(readiness.get("overallState")).lower() or "unknown"
        symbol_state = {
            "symbol": symbol,
            "overallState": overall_state,
            "providerState": _text(readiness.get("providerState")).lower() or "unknown",
            "freshnessState": _text(readiness.get("freshnessState")).lower() or "unknown",
            "adjustmentState": _text(readiness.get("adjustmentState")).lower() or "unknown",
            "benchmarkState": _text(readiness.get("benchmarkState")).lower() or "unknown",
            "requiredBars": _safe_int(readiness.get("requiredBars")),
            "usableBars": _safe_int(readiness.get("usableBars")),
            "missingBars": _safe_int(readiness.get("missingBars")),
            "missingRequirements": requirements,
        }
        symbol_states.append(symbol_state)
        if any(item in SCANNER_OHLCV_BLOCKING_REQUIREMENTS for item in requirements) or overall_state == "blocked":
            if symbol:
                blocked_symbols.append(symbol)
        elif requirements or overall_state == "degraded":
            if symbol:
                degraded_symbols.append(symbol)

    if benchmark_missing:
        missing_requirements.append("missing_benchmark")
    missing_requirements = _dedupe(missing_requirements)
    if any(item in SCANNER_OHLCV_BLOCKING_REQUIREMENTS for item in missing_requirements) or blocked_symbols:
        availability_state = "not_available"
        execution_state = "blocked"
        overall_state = "blocked"
    elif any(item in SCANNER_OHLCV_DEGRADED_REQUIREMENTS for item in missing_requirements) or degraded_symbols:
        availability_state = "degraded"
        execution_state = "degraded"
        overall_state = "degraded"
    else:
        availability_state = "available"
        execution_state = "executable"
        overall_state = "ready"

    return {
        "contractVersion": SCANNER_OHLCV_READINESS_CONTRACT_VERSION,
        "market": _text(market).lower() or "unknown",
        "profile": _text(profile) or "unknown",
        "availabilityState": availability_state,
        "executionState": execution_state,
        "overallState": overall_state,
        "requiredBars": int(required_bars),
        "usableBars": int(min(usable_bars_values) if usable_bars_values else 0),
        "missingBars": int(missing_bars),
        "missingRequirements": missing_requirements,
        "blockedSymbols": _dedupe(blocked_symbols)[:20],
        "degradedSymbols": _dedupe(degraded_symbols)[:20],
        "symbolStates": symbol_states[:50],
        "consumerSafe": True,
    }


def _collect_readiness_items(
    *,
    diagnostics: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for candidate in candidates or []:
        readiness = sanitize_historical_ohlcv_readiness(
            candidate.get("historicalOhlcvReadiness")
            or candidate.get("historical_ohlcv_readiness")
            or candidate.get("ohlcvReadiness")
        )
        if readiness:
            items.append(readiness)

    candidate_diagnostics = diagnostics.get("candidate_diagnostics")
    if isinstance(candidate_diagnostics, Mapping):
        known_symbols = {_text(item.get("symbol")).upper() for item in items}
        for symbol, payload in candidate_diagnostics.items():
            if not isinstance(payload, Mapping):
                continue
            readiness = sanitize_historical_ohlcv_readiness(
                payload.get("historicalOhlcvReadiness")
                or payload.get("historical_ohlcv_readiness")
                or payload.get("ohlcvReadiness")
            )
            if readiness and _text(readiness.get("symbol")).upper() not in known_symbols:
                if not readiness.get("symbol"):
                    readiness["symbol"] = _text(symbol).upper()
                items.append(readiness)
                known_symbols.add(_text(readiness.get("symbol")).upper())
    return items


def _benchmark_missing(diagnostics: Mapping[str, Any]) -> bool:
    benchmark_context = diagnostics.get("benchmark_context")
    if not isinstance(benchmark_context, Mapping):
        return False
    benchmark_code = _text(benchmark_context.get("benchmark_code"))
    if not benchmark_code:
        return False
    return benchmark_context.get("available") is not True


def _history_frame_records(history_df: pd.DataFrame) -> list[Mapping[str, Any]]:
    if history_df is None or history_df.empty:
        return []
    records = history_df.to_dict("records")
    result: list[Mapping[str, Any]] = []
    for row in records:
        if not isinstance(row, Mapping):
            continue
        payload = dict(row)
        raw_date = payload.get("date")
        if hasattr(raw_date, "date"):
            payload["date"] = raw_date.date().isoformat()
        result.append(payload)
    return result


def _history_source_available(history_df: pd.DataFrame, history_diag: Mapping[str, Any]) -> bool:
    source = _text(history_diag.get("source")).lower()
    if source in {"", "unavailable", "provider_missing", "provider_unavailable"}:
        return False
    return history_df is not None and not history_df.empty


def _safe_unavailable_reason(history_diag: Mapping[str, Any]) -> str | None:
    reason = _text(history_diag.get("unavailable_reason") or history_diag.get("reason")).lower()
    if reason in {"provider_missing", "entitlement_required"}:
        return reason
    source = _text(history_diag.get("source")).lower()
    if source in {"", "unavailable", "provider_missing"}:
        return "provider_missing"
    if source == "provider_unavailable":
        return "provider_unavailable"
    return None


def _freshness_state(history_diag: Mapping[str, Any]) -> str | None:
    for key in ("freshnessState", "freshness_state", "freshness"):
        value = _text(history_diag.get(key)).lower()
        if value in {"stale", "current"}:
            return value
    return None


def _adjustments_available(history_diag: Mapping[str, Any]) -> bool | None:
    for key in ("adjustmentsAvailable", "adjustments_available", "adjusted", "isAdjusted"):
        if key in history_diag:
            return bool(history_diag.get(key))
    return None


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_text(item).lower() for item in value if _text(item)]


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = _text(value).lower()
        if normalized and normalized not in result:
            result.append(normalized)
    return result
