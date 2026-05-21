# -*- coding: utf-8 -*-
"""Market Overview -> regime synthesis adapter.

This module only transforms already-normalized Market Overview / Market
Temperature snapshots into deterministic regime synthesis evidence. It does not
fetch providers, call networks, mutate cache state, or change scoring logic in
other Market Intelligence surfaces.
"""

from __future__ import annotations

import statistics
from typing import Any, Mapping, Sequence

from src.services.liquidity_impulse_synthesis_service import (
    LiquidityImpulseEvidenceItem,
    synthesize_liquidity_impulse,
)
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

    rotation_evidence = _rotation_leadership_evidence(inputs)
    if rotation_evidence is not None:
        evidence.append(rotation_evidence)

    liquidity_evidence = _liquidity_impulse_evidence(inputs)
    if liquidity_evidence is not None:
        evidence.append(liquidity_evidence)

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


def _rotation_leadership_evidence(inputs: Mapping[str, Any]) -> MarketRegimeEvidenceItem | None:
    panel = inputs.get("sectors")
    if not isinstance(panel, Mapping):
        return None
    items = panel.get("items")
    if not isinstance(items, Sequence):
        return None

    candidates = [item for item in items if isinstance(item, Mapping) and _rotation_item_allowed(item)]
    if candidates:
        return _rotation_leadership_from_items("sectors", panel, candidates, score_allowed=True)

    blocked = [item for item in items if isinstance(item, Mapping) and _rotation_item_relevant(item)]
    if not blocked:
        return None
    return _rotation_leadership_from_items("sectors", panel, blocked, score_allowed=False)


def _rotation_leadership_from_items(
    panel_key: str,
    panel: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
    *,
    score_allowed: bool,
) -> MarketRegimeEvidenceItem:
    avg_rotation_score = _average_float(
        _optional_float(item.get("rotationScore")) for item in items
    )
    avg_change = _average_float(
        _optional_float(item.get("changePercent") or item.get("change")) for item in items
    )
    primary = items[0]
    source_reason = _rotation_degradation_reason(primary, panel)
    if score_allowed:
        source_tier = _text(primary.get("sourceTier") or primary.get("sourceType") or primary.get("source"))
        trust_level = _text(primary.get("trustLevel")) or "usable"
        freshness = _text(primary.get("freshness") or panel.get("freshness")) or "unknown"
        direction = _direction_text(primary, change=avg_change, value=avg_rotation_score)
        source = _text(primary.get("source") or panel.get("source") or "rotation_radar_projection")
        degradation_reason = source_reason
        observation_only = _bool(primary.get("observationOnly"), panel.get("observationOnly"))
        score_contribution_allowed = True
    else:
        source_tier = _text(primary.get("sourceTier") or primary.get("sourceType") or primary.get("source"))
        trust_level = _text(primary.get("trustLevel")) or "unavailable"
        freshness = _text(primary.get("freshness") or panel.get("freshness")) or "unavailable"
        direction = _direction_text(primary, change=avg_change, value=avg_rotation_score)
        source = _text(primary.get("source") or panel.get("source") or "rotation_radar_projection")
        degradation_reason = (
            source_reason
            or _text(primary.get("sourceAuthorityReason"))
            or _first_text(primary.get("degradationReason"), primary.get("rankExclusionReason"))
            or "score_contribution_not_allowed"
        )
        observation_only = True
        score_contribution_allowed = False

    return MarketRegimeEvidenceItem(
        key="sectors:rotation_leadership",
        label="Rotation Leadership",
        category=panel_key,
        pillar="rotation_leadership",
        value=avg_rotation_score,
        percentile=avg_rotation_score,
        direction=direction,
        source=source,
        source_tier=source_tier,
        trust_level=trust_level,
        freshness=freshness,
        observation_only=observation_only,
        score_contribution_allowed=score_contribution_allowed,
        as_of=_text(primary.get("asOf") or panel.get("asOf")) or None,
        updated_at=_text(primary.get("updatedAt") or panel.get("updatedAt")) or None,
        degradation_reason=degradation_reason,
    )


def _rotation_item_allowed(item: Mapping[str, Any]) -> bool:
    if not _rotation_item_relevant(item):
        return False
    if not _bool(item.get("sourceAuthorityAllowed"), default=True):
        return False
    if not _bool(item.get("scoreContributionAllowed"), default=True):
        return False
    if "rankEligible" in item and not _bool(item.get("rankEligible")):
        return False
    if "headlineEligible" in item and not _bool(item.get("headlineEligible")):
        return False
    return True


def _rotation_item_relevant(item: Mapping[str, Any]) -> bool:
    return _text(item.get("symbol") or item.get("name") or item.get("id")) != ""


def _rotation_degradation_reason(item: Mapping[str, Any], panel: Mapping[str, Any]) -> str | None:
    return _first_text(
        item.get("sourceAuthorityReason"),
        item.get("degradationReason"),
        item.get("rankExclusionReason"),
        panel.get("degradationReason"),
    )


def _liquidity_impulse_evidence(inputs: Mapping[str, Any]) -> MarketRegimeEvidenceItem | None:
    projected = tuple(_projected_liquidity_evidence_items(inputs))
    if not projected:
        return None

    result = synthesize_liquidity_impulse(projected)
    freshness = _worst_freshness(item.freshness for item in projected)
    trust_level = _liquidity_trust_level(result.confidence_label)
    source_tier = "computed_from_real" if int(result.evidence_quality.get("realScoringEvidenceCount") or 0) > 0 and result.liquidity_impulse != "data_insufficient" else "computed_from_data_gap"
    source = "liquidity_monitor_projection"
    as_of = _first_text(*(item.as_of for item in projected)) or None
    updated_at = _first_text(*(item.updated_at for item in projected)) or None
    direction = "up" if result.direction_score > 0 else "down" if result.direction_score < 0 else None
    score_allowed = result.liquidity_impulse != "data_insufficient" and int(result.evidence_quality.get("realScoringEvidenceCount") or 0) > 0
    degradation_reason = None
    if not score_allowed:
        degradation_reason = _first_text(
            *(gap.get("reason") for gap in result.data_gaps if isinstance(gap, Mapping)),
            result.subtype,
        )

    return MarketRegimeEvidenceItem(
        key="liquidity_monitor:liquidity_impulse",
        label="Liquidity Impulse",
        category="liquidity_monitor",
        pillar="liquidity_impulse",
        value=result.direction_score,
        direction=direction,
        source=source,
        source_tier=source_tier,
        trust_level=trust_level,
        freshness=freshness,
        observation_only=any(item.observation_only for item in projected),
        score_contribution_allowed=score_allowed,
        as_of=as_of,
        updated_at=updated_at,
        degradation_reason=degradation_reason,
    )


def _projected_liquidity_evidence_items(inputs: Mapping[str, Any]) -> tuple[LiquidityImpulseEvidenceItem, ...]:
    evidence: list[LiquidityImpulseEvidenceItem] = []
    panels = {
        "rates": inputs.get("rates"),
        "fx": inputs.get("fx"),
        "futures": inputs.get("futures"),
        "crypto": inputs.get("crypto"),
        "breadth": inputs.get("breadth"),
        "flows": inputs.get("flows"),
    }
    if isinstance(panels["rates"], Mapping):
        items = panels["rates"].get("items")
        if isinstance(items, Sequence):
            for symbol, pillar in (("US10Y", "rates_pressure"), ("VIX", "volatility_stress")):
                raw_item = _first_mapping_item(items, symbol)
                if raw_item is not None:
                    evidence.append(_liquidity_evidence_from_item("rates", raw_item, pillar))
    if isinstance(panels["fx"], Mapping):
        items = panels["fx"].get("items")
        if isinstance(items, Sequence):
            for symbol in ("DXY", "USDCNH"):
                raw_item = _first_mapping_item(items, symbol)
                if raw_item is not None:
                    evidence.append(_liquidity_evidence_from_item("fx", raw_item, "dollar_pressure"))
    if isinstance(panels["futures"], Mapping):
        items = panels["futures"].get("items")
        if isinstance(items, Sequence):
            for symbol in ("ES", "NQ", "YM", "RTY"):
                raw_item = _first_mapping_item(items, symbol)
                if raw_item is not None:
                    evidence.append(_liquidity_evidence_from_item("futures", raw_item, "risk_asset_demand"))
    if isinstance(panels["crypto"], Mapping):
        items = panels["crypto"].get("items")
        if isinstance(items, Sequence):
            for symbol in ("BTC", "ETH", "BNB"):
                raw_item = _first_mapping_item(items, symbol)
                if raw_item is not None:
                    evidence.append(_liquidity_evidence_from_item("crypto", raw_item, "crypto_liquidity_beta"))
    if isinstance(panels["breadth"], Mapping):
        items = panels["breadth"].get("items")
        if isinstance(items, Sequence):
            raw_item = _first_mapping_item(items, "ADV_RATIO")
            if raw_item is not None:
                evidence.append(_liquidity_breadth_evidence(raw_item))
    if isinstance(panels["flows"], Mapping):
        items = panels["flows"].get("items")
        if isinstance(items, Sequence):
            for symbol, pillar in (("CN_ETF", "equity_flow_proxy"), ("NORTHBOUND", "china_liquidity_context")):
                raw_item = _first_mapping_item(items, symbol)
                if raw_item is not None:
                    evidence.append(_liquidity_evidence_from_item("flows", raw_item, pillar))
    return tuple(evidence)


def _liquidity_evidence_from_item(
    panel_key: str,
    item: Mapping[str, Any],
    pillar: str,
) -> LiquidityImpulseEvidenceItem:
    score_allowed = _liquidity_item_allowed(item)
    source = _text(item.get("source") or "liquidity_monitor_projection")
    source_tier = _text(item.get("sourceTier") or item.get("sourceType") or source)
    trust_level = _text(item.get("trustLevel")) or "unknown"
    freshness = _text(item.get("freshness")) or "unknown"
    observation_only = _bool(item.get("observationOnly"))
    proxy_only = not _bool(item.get("sourceAuthorityAllowed"), default=True) or source_tier in {"unofficial_proxy", "unofficial_public_api", "public_proxy"}
    included_in_score = score_allowed if score_allowed else False
    direction, magnitude = _liquidity_direction_and_magnitude(panel_key, item, pillar)
    degradation_reason = None if score_allowed else _first_text(
        item.get("sourceAuthorityReason"),
        item.get("degradationReason"),
        "score_contribution_not_allowed",
    )
    return LiquidityImpulseEvidenceItem(
        key=f"liquidity_bridge:{panel_key}:{_text(item.get('symbol') or item.get('key'))}",
        label=_label(item),
        category=panel_key,
        pillar=pillar,
        value=magnitude,
        change=magnitude,
        direction=direction,
        source=source,
        source_tier=source_tier,
        trust_level=trust_level,
        freshness=freshness,
        observation_only=observation_only,
        score_contribution_allowed=score_allowed,
        included_in_score=included_in_score,
        proxy_only=proxy_only,
        as_of=_text(item.get("asOf") or item.get("updatedAt")) or None,
        updated_at=_text(item.get("updatedAt") or item.get("asOf")) or None,
        degradation_reason=degradation_reason,
    )


def _liquidity_breadth_evidence(item: Mapping[str, Any]) -> LiquidityImpulseEvidenceItem:
    score_allowed = _liquidity_item_allowed(item)
    source = _text(item.get("source") or "liquidity_monitor_projection")
    source_tier = _text(item.get("sourceTier") or item.get("sourceType") or source)
    trust_level = _text(item.get("trustLevel")) or "unknown"
    freshness = _text(item.get("freshness")) or "unknown"
    observation_only = _bool(item.get("observationOnly"))
    proxy_only = not _bool(item.get("sourceAuthorityAllowed"), default=True) or source_tier in {"unofficial_proxy", "unofficial_public_api", "public_proxy"}
    percentile = _bounded_percentile(item.get("value"))
    direction = _breadth_direction(item, percentile)
    degradation_reason = None if score_allowed else _first_text(
        item.get("sourceAuthorityReason"),
        item.get("degradationReason"),
        "score_contribution_not_allowed",
    )
    return LiquidityImpulseEvidenceItem(
        key=f"liquidity_bridge:breadth:{_text(item.get('symbol') or item.get('key'))}",
        label=_label(item),
        category="breadth",
        pillar="breadth_confirmation",
        value=percentile,
        percentile=percentile,
        direction=direction,
        source=source,
        source_tier=source_tier,
        trust_level=trust_level,
        freshness=freshness,
        observation_only=observation_only,
        score_contribution_allowed=score_allowed,
        included_in_score=score_allowed if score_allowed else False,
        proxy_only=proxy_only,
        as_of=_text(item.get("asOf") or item.get("updatedAt")) or None,
        updated_at=_text(item.get("updatedAt") or item.get("asOf")) or None,
        degradation_reason=degradation_reason,
    )


def _liquidity_item_allowed(item: Mapping[str, Any]) -> bool:
    if not _bool(item.get("scoreContributionAllowed"), default=True):
        return False
    if "sourceAuthorityAllowed" in item and not _bool(item.get("sourceAuthorityAllowed")):
        return False
    if _text(item.get("sourceAuthorityReason")) in {"proxy_context_only", "source_authority_router_rejected", "provider_absent"}:
        return False
    if _text(item.get("sourceTier") or item.get("sourceType")) in {"unofficial_proxy", "public_proxy", "unofficial_public_api"}:
        return False
    if _bool(item.get("observationOnly")):
        return False
    return True


def _liquidity_direction_and_magnitude(
    panel_key: str,
    item: Mapping[str, Any],
    pillar: str,
) -> tuple[str | None, float | None]:
    change = _first_float(item.get("changePercent"), item.get("change"))
    value = _first_float(item.get("value"), item.get("price"))
    if pillar == "breadth_confirmation":
        percentile = _bounded_percentile(item.get("value"))
        return _breadth_direction(item, percentile), percentile
    if change is not None:
        return _direction_text(item, change=change, value=value), change
    if value is not None:
        return _direction_text(item, change=None, value=value), value
    return None, None


def _first_mapping_item(items: Sequence[Any], symbol: str) -> Mapping[str, Any] | None:
    for raw_item in items:
        if isinstance(raw_item, Mapping) and _text(raw_item.get("symbol")).upper() == symbol.upper():
            return raw_item
    return None


def _average_float(values: Sequence[float | None]) -> float | None:
    finite = [float(value) for value in values if value is not None]
    return round(statistics.fmean(finite), 3) if finite else None


def _worst_freshness(values: Sequence[str]) -> str:
    order = {
        "live": 0,
        "fresh": 0,
        "cached": 1,
        "delayed": 2,
        "stale": 3,
        "partial": 4,
        "fallback": 5,
        "mock": 6,
        "unavailable": 7,
        "error": 8,
    }
    normalized = [(_text(value).lower() or "unknown") for value in values if _text(value)]
    if not normalized:
        return "unknown"
    return max(normalized, key=lambda value: order.get(value, 9))


def _liquidity_trust_level(confidence_label: str) -> str:
    if confidence_label in {"high", "medium"}:
        return "usable"
    if confidence_label == "low":
        return "usable_with_caution"
    return "unavailable"


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


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


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
