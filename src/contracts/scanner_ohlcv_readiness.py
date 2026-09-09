"""Consumer-safe shared projection for Scanner OHLCV readiness evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


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
        "runtimeStatus",
        "overallState",
        "asOf",
        "missingRequirements",
        "consumerSafe",
    }
)


def sanitize_historical_ohlcv_readiness(
    readiness: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return only the consumer-safe readiness contract fields."""
    if not isinstance(readiness, Mapping) or not readiness:
        return {}
    sanitized = {
        key: value
        for key, value in readiness.items()
        if key in SAFE_HISTORICAL_OHLCV_READINESS_KEYS
    }
    if not sanitized:
        return {}
    sanitized["missingRequirements"] = _dedupe(
        _text_list(sanitized.get("missingRequirements"))
    )
    for key in ("requiredBars", "usableBars", "missingBars", "lookbackBars"):
        if key in sanitized:
            sanitized[key] = _safe_int(sanitized.get(key))
    sanitized["consumerSafe"] = True
    return sanitized


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
