# -*- coding: utf-8 -*-
"""Standalone Market Pulse snapshot scaffold.

This helper is intentionally inert. It only normalizes caller-supplied values
into a bounded consumer-safe contract and never fetches live data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

from api.v1.schemas.market_pulse import (
    MarketPulseDataQuality,
    MarketPulseMetricItem,
    MarketPulseSnapshot,
    MarketPulseStatus,
)


MARKET_PULSE_ALLOWED_COPY_VALUES = frozenset(
    {
        "正常",
        "中性",
        "走强",
        "走弱",
        "观察",
        "复核",
        "适合研究观察",
        "暂无证据",
        "暂不可用",
    }
)
MARKET_PULSE_ALLOWED_DATA_QUALITY_STATES = frozenset(MARKET_PULSE_ALLOWED_COPY_VALUES)
MARKET_PULSE_DEFAULT_DISCLOSURE = "仅供研究观察，不构成投资建议。"

_DEFAULT_INDEX_DEFINITIONS = (
    ("S&P 500", "pt"),
    ("Nasdaq", "pt"),
    ("Russell 2000", "pt"),
)
_DEFAULT_SINGLE_METRICS = {
    "volatility": ("VIX", "pt"),
    "rates": ("10Y Treasury yield", "%"),
    "dollar": ("Dollar index", "pt"),
    "breadth": ("Market breadth", "%"),
    "liquidity": ("Liquidity state", None),
}
_NO_EVIDENCE_COPY = "暂无证据"
_UNAVAILABLE_COPY = "暂不可用"
_OBSERVE_COPY = "观察"
_REVIEW_COPY = "复核"
_READY_COPY = "正常"
_FORBIDDEN_DETAIL_KEYS = {
    "traceback",
    "exception",
    "exceptionClass",
    "providerUrl",
    "token",
    "session",
    "sessionId",
    "apiKey",
    "secret",
    "trustLevel",
    "reasonCode",
    "reasonCodes",
    "sourceType",
    "fallback",
    "rawConfidence",
}


class MarketPulseService:
    """Build a reusable consumer-safe Market Pulse snapshot."""

    def build_snapshot(self, payload: Mapping[str, Any] | None = None) -> MarketPulseSnapshot:
        raw = self._mapping(payload)
        explicit_status = self._status(raw.get("status"))
        as_of = self._text(raw.get("asOf"))

        indices = self._build_indices(raw.get("indices"))
        volatility = self._build_metric("volatility", raw.get("volatility"))
        rates = self._build_metric("rates", raw.get("rates"))
        dollar = self._build_metric("dollar", raw.get("dollar"))
        breadth = self._build_metric("breadth", raw.get("breadth"))
        liquidity = self._build_metric("liquidity", raw.get("liquidity"))

        metrics = indices + [volatility, rates, dollar, breadth, liquidity]
        status = explicit_status or self._derive_status(metrics)
        data_quality = self._build_snapshot_data_quality(status)

        return MarketPulseSnapshot(
            status=status,
            asOf=as_of,
            indices=indices,
            volatility=volatility,
            rates=rates,
            dollar=dollar,
            breadth=breadth,
            liquidity=liquidity,
            dataQuality=data_quality,
            noAdviceDisclosure=MARKET_PULSE_DEFAULT_DISCLOSURE,
        )

    def _build_indices(self, value: Any) -> list[MarketPulseMetricItem]:
        rows = list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []
        metrics: list[MarketPulseMetricItem] = []
        for index, (label, unit) in enumerate(_DEFAULT_INDEX_DEFINITIONS):
            row = rows[index] if index < len(rows) else None
            metrics.append(self._metric_from_payload(label=label, unit=unit, payload=row))
        return metrics

    def _build_metric(self, section: str, value: Any) -> MarketPulseMetricItem:
        label, unit = _DEFAULT_SINGLE_METRICS[section]
        return self._metric_from_payload(label=label, unit=unit, payload=value)

    def _metric_from_payload(
        self,
        *,
        label: str,
        unit: str | None,
        payload: Mapping[str, Any] | Any | None,
    ) -> MarketPulseMetricItem:
        row = self._mapping(payload)
        clean_row = {key: item for key, item in row.items() if key not in _FORBIDDEN_DETAIL_KEYS}
        value = self._number(clean_row.get("value"))
        change = self._number(clean_row.get("change"))
        metric_unit = self._text(clean_row.get("unit")) or unit
        explicit_state = self._copy_value(clean_row.get("state"))
        explicit_interpretation = self._copy_value(clean_row.get("interpretation"))
        explicit_quality = self._copy_value(clean_row.get("dataQuality"))
        has_explicit_signal = any((explicit_state, explicit_interpretation, explicit_quality))

        if value is None and change is None and not has_explicit_signal:
            state = _NO_EVIDENCE_COPY
            interpretation = _NO_EVIDENCE_COPY
            quality = self._quality(_NO_EVIDENCE_COPY, available=False)
        else:
            state = explicit_state or _OBSERVE_COPY
            interpretation = explicit_interpretation or (
                "适合研究观察" if state in {"正常", "中性", "走强", "走弱"} else state
            )
            quality_state = explicit_quality or self._quality_state_from_state(state)
            quality = self._quality(quality_state, available=True)

        return MarketPulseMetricItem(
            label=label,
            value=value,
            unit=metric_unit,
            change=change,
            state=state,
            interpretation=interpretation,
            dataQuality=quality,
        )

    def _build_snapshot_data_quality(self, status: MarketPulseStatus) -> MarketPulseDataQuality:
        if status == "ready":
            return self._quality(_READY_COPY, available=True)
        if status == "partial":
            return self._quality(_REVIEW_COPY, available=True)
        if status == "unavailable":
            return self._quality(_UNAVAILABLE_COPY, available=False)
        return self._quality(_NO_EVIDENCE_COPY, available=False)

    def _derive_status(self, metrics: Sequence[MarketPulseMetricItem]) -> MarketPulseStatus:
        evidence_count = sum(1 for item in metrics if self._has_evidence(item))
        if evidence_count == 0:
            return "no_evidence"
        if evidence_count == len(metrics):
            return "ready"
        return "partial"

    def _has_evidence(self, item: MarketPulseMetricItem) -> bool:
        if item.value is not None or item.change is not None:
            return True
        return item.state not in {_NO_EVIDENCE_COPY, _UNAVAILABLE_COPY}

    def _quality_state_from_state(self, state: str) -> str:
        if state in {"正常", "中性", "走强", "走弱"}:
            return state
        if state in MARKET_PULSE_ALLOWED_DATA_QUALITY_STATES:
            return state
        return _OBSERVE_COPY

    def _quality(self, state: str, *, available: bool) -> MarketPulseDataQuality:
        safe_state = self._copy_value(state) or (_OBSERVE_COPY if available else _NO_EVIDENCE_COPY)
        return MarketPulseDataQuality(state=safe_state, label=safe_state, available=available)

    def _status(self, value: Any) -> MarketPulseStatus | None:
        normalized = self._text(value)
        if normalized in {"ready", "partial", "no_evidence", "unavailable"}:
            return normalized
        return None

    def _copy_value(self, value: Any) -> str | None:
        normalized = self._text(value)
        if normalized in MARKET_PULSE_ALLOWED_COPY_VALUES:
            return normalized
        return None

    def _number(self, value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            number = float(value)
            return number if math.isfinite(number) else None
        return None

    def _text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _mapping(self, value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        return {}
