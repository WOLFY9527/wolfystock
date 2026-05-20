# -*- coding: utf-8 -*-
"""Market Overview -> regime synthesis adapter.

This module only transforms already-normalized Market Overview / Market
Temperature snapshots into deterministic regime synthesis evidence. It does not
fetch providers, call networks, mutate cache state, or change scoring logic in
other Market Intelligence surfaces.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.market_regime_synthesis_service import (
    MarketRegimeEvidenceItem,
    synthesize_market_regime,
)


_PANEL_SYMBOL_PILLARS: dict[str, dict[str, str]] = {
    "futures": {
        "ES": "risk_appetite",
        "NQ": "risk_appetite",
        "YM": "risk_appetite",
        "RTY": "risk_appetite",
        "RUT": "risk_appetite",
        "SPX": "risk_appetite",
        "NDX": "risk_appetite",
        "DJI": "risk_appetite",
        "CN00Y": "china_risk_appetite",
        "HSI_F": "china_risk_appetite",
    },
    "indices": {
        "HSI": "china_risk_appetite",
        "HSTECH": "china_risk_appetite",
        "HSI.HK": "china_risk_appetite",
        "HSTECH.HK": "china_risk_appetite",
        "CSI300": "china_risk_appetite",
        "000300.SH": "china_risk_appetite",
        "000300.SS": "china_risk_appetite",
        "000001.SH": "china_risk_appetite",
        "399001.SZ": "china_risk_appetite",
        "399006.SZ": "china_risk_appetite",
        "CN00Y": "china_risk_appetite",
    },
    "rates": {
        "VIX": "volatility_stress",
        "US10Y": "rates_pressure",
        "US30Y": "rates_pressure",
    },
    "fx": {
        "DXY": "dollar_pressure",
        "USDCNH": "dollar_pressure",
    },
    "crypto": {
        "BTC": "crypto_risk_beta",
        "ETH": "crypto_risk_beta",
    },
}


def build_market_regime_evidence_items(inputs: Mapping[str, Any]) -> tuple[MarketRegimeEvidenceItem, ...]:
    """Project normalized temperature inputs into regime synthesis evidence."""

    evidence: list[MarketRegimeEvidenceItem] = []

    for panel_key, symbol_map in _PANEL_SYMBOL_PILLARS.items():
        panel = inputs.get(panel_key)
        if not isinstance(panel, Mapping):
            continue
        items = panel.get("items")
        if not isinstance(items, Sequence):
            continue
        for raw_item in items:
            if not isinstance(raw_item, Mapping):
                continue
            symbol = _text(raw_item.get("symbol")).upper()
            if not symbol:
                continue
            pillar = symbol_map.get(symbol)
            if pillar is None:
                continue
            evidence.append(_change_driven_evidence(panel_key, panel, raw_item, pillar))

    breadth_panel = inputs.get("breadth")
    if isinstance(breadth_panel, Mapping):
        items = breadth_panel.get("items")
        if isinstance(items, Sequence):
            for raw_item in items:
                if not isinstance(raw_item, Mapping):
                    continue
                symbol = _text(raw_item.get("symbol")).upper()
                if symbol == "ADV_RATIO":
                    evidence.append(_breadth_percentile_evidence("breadth", breadth_panel, raw_item))

    return tuple(evidence)


def synthesize_market_regime_from_temperature_inputs(inputs: Mapping[str, Any]):
    """Run deterministic regime synthesis against normalized temperature inputs."""

    return synthesize_market_regime(build_market_regime_evidence_items(inputs))


def build_market_regime_synthesis_payload(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Return the camelCase payload that backend callers can surface later."""

    return synthesize_market_regime_from_temperature_inputs(inputs).to_dict()


def _change_driven_evidence(
    panel_key: str,
    panel: Mapping[str, Any],
    item: Mapping[str, Any],
    pillar: str,
) -> MarketRegimeEvidenceItem:
    change = _first_float(item.get("changePercent"), item.get("change_pct"), item.get("change"))
    return MarketRegimeEvidenceItem(
        key=_evidence_key(panel_key, item),
        label=_label(item),
        category=panel_key,
        pillar=pillar,
        change=change,
        direction=_direction_text(item, change=change),
        source=_text(item.get("source") or panel.get("source")),
        source_tier=_source_tier(item, panel),
        trust_level=_text(item.get("trustLevel") or panel.get("trustLevel")) or "unknown",
        freshness=_text(item.get("freshness") or panel.get("freshness")) or "unknown",
        observation_only=_bool(item.get("observationOnly"), item.get("observation_only"), panel.get("observationOnly")),
        score_contribution_allowed=_bool(
            item.get("scoreContributionAllowed"),
            item.get("score_contribution_allowed"),
            panel.get("scoreContributionAllowed"),
            default=True,
        ),
        as_of=_text(item.get("asOf") or panel.get("asOf")) or None,
        updated_at=_text(item.get("updatedAt") or panel.get("updatedAt")) or None,
        degradation_reason=_degradation_reason(item, panel),
    )


def _breadth_percentile_evidence(
    panel_key: str,
    panel: Mapping[str, Any],
    item: Mapping[str, Any],
) -> MarketRegimeEvidenceItem:
    percentile = _bounded_percentile(item.get("value"))
    return MarketRegimeEvidenceItem(
        key=_evidence_key(panel_key, item),
        label=_label(item),
        category=panel_key,
        pillar="breadth_health",
        percentile=percentile,
        direction=_breadth_direction(item, percentile),
        source=_text(item.get("source") or panel.get("source")),
        source_tier=_source_tier(item, panel),
        trust_level=_text(item.get("trustLevel") or panel.get("trustLevel")) or "unknown",
        freshness=_text(item.get("freshness") or panel.get("freshness")) or "unknown",
        observation_only=_bool(item.get("observationOnly"), item.get("observation_only"), panel.get("observationOnly")),
        score_contribution_allowed=_bool(
            item.get("scoreContributionAllowed"),
            item.get("score_contribution_allowed"),
            panel.get("scoreContributionAllowed"),
            default=True,
        ),
        as_of=_text(item.get("asOf") or panel.get("asOf")) or None,
        updated_at=_text(item.get("updatedAt") or panel.get("updatedAt")) or None,
        degradation_reason=_degradation_reason(item, panel),
    )


def _direction_text(
    item: Mapping[str, Any],
    *,
    change: float | None = None,
    value: float | None = None,
) -> str | None:
    raw_direction = _text(
        item.get("direction")
        or item.get("risk_direction")
        or item.get("trendDirection")
    ).lower()
    if raw_direction in {"up", "rising", "higher", "positive", "strong", "improving", "risk_on", "risk-on", "increasing"}:
        return "up"
    if raw_direction in {"down", "falling", "lower", "negative", "weak", "deteriorating", "risk_off", "risk-off", "decreasing"}:
        return "down"
    numeric = change
    if numeric is None:
        numeric = value
    if numeric is None:
        return None
    if numeric > 0:
        return "up"
    if numeric < 0:
        return "down"
    return None


def _breadth_direction(item: Mapping[str, Any], percentile: float | None) -> str | None:
    explicit = _direction_text(item)
    if explicit is not None:
        return explicit
    if percentile is None:
        return None
    if percentile > 50.0:
        return "up"
    if percentile < 50.0:
        return "down"
    return None


def _degradation_reason(item: Mapping[str, Any], panel: Mapping[str, Any]) -> str | None:
    return _text(
        item.get("degradationReason")
        or item.get("sourceAuthorityReason")
        or item.get("excludeReason")
        or item.get("proxyObservationOnlyReason")
        or panel.get("degradationReason")
    ) or None


def _source_tier(item: Mapping[str, Any], panel: Mapping[str, Any]) -> str:
    return (
        _text(item.get("sourceTier"))
        or _text(panel.get("sourceTier"))
        or _text(item.get("sourceType"))
        or _text(panel.get("sourceType"))
        or _text(item.get("source"))
        or _text(panel.get("source"))
    )


def _bounded_percentile(value: Any) -> float | None:
    numeric = _optional_float(value)
    if numeric is None:
        return None
    return max(0.0, min(100.0, float(numeric)))


def _first_float(*values: Any) -> float | None:
    for value in values:
        numeric = _optional_float(value)
        if numeric is not None:
            return numeric
    return None


def _optional_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _evidence_key(panel_key: str, item: Mapping[str, Any]) -> str:
    symbol = _text(item.get("symbol")) or _text(item.get("key")) or "unknown"
    return f"{panel_key}:{symbol}"


def _label(item: Mapping[str, Any]) -> str:
    return _text(item.get("label") or item.get("name") or item.get("symbol")) or "Unknown"


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _bool(*values: Any, default: bool = False) -> bool:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        text = _text(value).lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
    return default
