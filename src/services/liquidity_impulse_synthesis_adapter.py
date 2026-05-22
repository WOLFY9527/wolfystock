# -*- coding: utf-8 -*-
"""Liquidity Monitor -> liquidity impulse adapter.

This module only transforms already-built Liquidity Monitor indicator payloads
into deterministic liquidity impulse evidence. It does not fetch providers,
call networks, mutate caches, or change Liquidity Monitor scoring behavior.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from src.services.liquidity_impulse_synthesis_service import (
    LiquidityImpulseEvidenceItem,
    synthesize_liquidity_impulse,
)


_INDICATOR_PILLARS: dict[str, str] = {
    "usd_pressure": "dollar_pressure",
    "us_rates_pressure": "rates_pressure",
    "fed_liquidity": "fed_liquidity",
    "vix_pressure": "volatility_stress",
    "crypto_spot_momentum": "crypto_liquidity_beta",
    "crypto_funding": "funding_stress",
    "us_etf_flow_proxy": "equity_flow_proxy",
    "us_breadth_proxy": "breadth_confirmation",
    "cn_hk_index_context": "china_liquidity_context",
    "cn_hk_flows": "china_liquidity_context",
    "cn_money_market_rates": "china_liquidity_context",
    "futures_premarket": "risk_asset_demand",
}

_SIGNED_NUMBER_RE = re.compile(r"([+-]\d+(?:\.\d+)?)")


def build_liquidity_impulse_evidence_items(
    indicators: Sequence[Mapping[str, Any]],
) -> tuple[LiquidityImpulseEvidenceItem, ...]:
    """Project Liquidity Monitor indicators into synthesis evidence items."""

    evidence: list[LiquidityImpulseEvidenceItem] = []
    for raw_indicator in indicators:
        if not isinstance(raw_indicator, Mapping):
            continue
        key = _text(raw_indicator.get("key"))
        pillar = _INDICATOR_PILLARS.get(key)
        if pillar is None:
            continue
        evidence.append(_indicator_evidence(raw_indicator, pillar))
    return tuple(evidence)


def synthesize_liquidity_impulse_from_monitor_indicators(indicators: Sequence[Mapping[str, Any]]):
    """Run deterministic synthesis against existing Liquidity Monitor indicators."""

    return synthesize_liquidity_impulse(build_liquidity_impulse_evidence_items(indicators))


def build_liquidity_impulse_synthesis_payload(indicators: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return the additive camelCase synthesis payload for backend callers."""

    return synthesize_liquidity_impulse_from_monitor_indicators(indicators).to_dict()


def _indicator_evidence(indicator: Mapping[str, Any], pillar: str) -> LiquidityImpulseEvidenceItem:
    diagnostics = indicator.get("coverageDiagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    evidence = indicator.get("evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    direction, magnitude = _direction_and_magnitude(_text(indicator.get("key")), indicator)
    as_of = _text(evidence.get("asOf")) or _text(indicator.get("updatedAt")) or None
    updated_at = _text(indicator.get("updatedAt")) or _text(evidence.get("asOf")) or None

    return LiquidityImpulseEvidenceItem(
        key=f"liquidity_monitor:{_text(indicator.get('key')) or 'unknown'}",
        label=_label(indicator),
        category="liquidity_monitor",
        pillar=pillar,
        change=magnitude,
        direction=direction,
        source=_text(evidence.get("source")) or "unavailable",
        source_tier=_source_tier(diagnostics, evidence),
        trust_level=_text(diagnostics.get("trustLevel")) or "unknown",
        freshness=_text(diagnostics.get("freshness")) or _text(evidence.get("freshness")) or _text(indicator.get("freshness")) or "unknown",
        observation_only=_bool(diagnostics.get("observationOnly")),
        score_contribution_allowed=_bool(diagnostics.get("scoreContributionAllowed"), default=True),
        included_in_score=_optional_bool(indicator.get("includedInScore")),
        proxy_only=_bool(diagnostics.get("proxyOnly")),
        as_of=as_of,
        updated_at=updated_at,
        degradation_reason=_degradation_reason(diagnostics, evidence),
    )


def _direction_and_magnitude(key: str, indicator: Mapping[str, Any]) -> tuple[str | None, float | None]:
    summary = _summary_core(indicator)
    score_contribution = _optional_float(indicator.get("scoreContribution"))

    if key == "crypto_spot_momentum":
        direction = _advancer_ratio_direction(summary)
        return direction or _score_direction(key, score_contribution), _first_signed_metric(summary)
    if key == "crypto_funding":
        metric = _first_signed_metric(summary)
        return _metric_direction(metric), metric
    if key == "vix_pressure":
        metric = _first_signed_metric(summary)
        return _metric_direction(metric) or _score_direction(key, score_contribution), metric
    if key == "usd_pressure":
        direction = _vote_direction(
            _labeled_metric(summary, "DXY"),
            _labeled_metric(summary, "USD/CNH"),
            _labeled_metric(summary, "USD/JPY"),
            _scaled_metric(_labeled_metric(summary, "EUR/USD"), -1.0),
        )
        return direction or _score_direction(key, score_contribution), _mean_abs(
            _labeled_metric(summary, "DXY"),
            _labeled_metric(summary, "USD/CNH"),
            _labeled_metric(summary, "USD/JPY"),
            _labeled_metric(summary, "EUR/USD"),
        )
    if key == "us_rates_pressure":
        direction = _vote_direction(
            _labeled_metric(summary, "US2Y"),
            _labeled_metric(summary, "US10Y"),
            _labeled_metric(summary, "US30Y"),
        )
        return direction or _score_direction(key, score_contribution), _mean_abs(
            _labeled_metric(summary, "US2Y"),
            _labeled_metric(summary, "US10Y"),
            _labeled_metric(summary, "US30Y"),
        )
    if key == "fed_liquidity":
        direction = _vote_direction(
            _labeled_metric(summary, "FED_ASSETS"),
            _scaled_metric(_labeled_metric(summary, "FED_RRP"), -1.0),
            _scaled_metric(_labeled_metric(summary, "TGA"), -1.0),
            _labeled_metric(summary, "RESERVES"),
        )
        return direction or _score_direction(key, score_contribution), _mean_abs(
            _labeled_metric(summary, "FED_ASSETS"),
            _labeled_metric(summary, "FED_RRP"),
            _labeled_metric(summary, "TGA"),
            _labeled_metric(summary, "RESERVES"),
        )
    if key == "us_etf_flow_proxy":
        metric = _first_signed_metric(summary)
        return _metric_direction(metric) or _score_direction(key, score_contribution), metric
    if key == "us_breadth_proxy":
        direction = _ratio_direction(summary) or _vote_direction(
            _labeled_metric(summary, "RSP/SPY"),
            _labeled_metric(summary, "IWM/SPY"),
            _labeled_metric(summary, "QQQ/SPY"),
        )
        return direction or _score_direction(key, score_contribution), _breadth_magnitude(summary)
    if key == "cn_hk_index_context":
        metric = _first_signed_metric(summary)
        return _metric_direction(metric), metric
    if key == "cn_hk_flows":
        metrics = _signed_metrics(summary)
        return _vote_direction(*metrics), _mean_abs(*metrics)
    if key == "cn_money_market_rates":
        metric = _first_signed_metric(summary)
        direction = _invert_direction(_metric_direction(metric))
        return direction, metric
    if key == "futures_premarket":
        metric = _first_signed_metric(summary)
        return _metric_direction(metric), metric
    return _score_direction(key, score_contribution), _first_signed_metric(summary)


def _score_direction(key: str, score_contribution: float | None) -> str | None:
    if score_contribution is None or score_contribution == 0:
        return None
    if key in {"vix_pressure", "usd_pressure"}:
        return "down" if score_contribution > 0 else "up"
    return "up" if score_contribution > 0 else "down"


def _summary_core(indicator: Mapping[str, Any]) -> str:
    summary = _text(indicator.get("summary"))
    if " | 来源 " in summary:
        summary = summary.split(" | 来源 ", 1)[0]
    return summary


def _signed_metrics(summary: str) -> tuple[float, ...]:
    return tuple(float(match) for match in _SIGNED_NUMBER_RE.findall(summary))


def _first_signed_metric(summary: str) -> float | None:
    metrics = _signed_metrics(summary)
    return metrics[0] if metrics else None


def _labeled_metric(summary: str, label: str) -> float | None:
    match = re.search(rf"{re.escape(label)}\s*([+-]\d+(?:\.\d+)?)", summary)
    if match is None:
        return None
    return _optional_float(match.group(1))


def _metric_direction(metric: float | None) -> str | None:
    if metric is None:
        return None
    if metric > 0:
        return "up"
    if metric < 0:
        return "down"
    return None


def _invert_direction(direction: str | None) -> str | None:
    if direction == "up":
        return "down"
    if direction == "down":
        return "up"
    return None


def _vote_direction(*metrics: float | None) -> str | None:
    positive = 0
    negative = 0
    for metric in metrics:
        if metric is None:
            continue
        if metric > 0:
            positive += 1
        elif metric < 0:
            negative += 1
    if positive > negative:
        return "up"
    if negative > positive:
        return "down"
    return None


def _ratio_direction(summary: str) -> str | None:
    match = re.search(r"(\d+)\s*/\s*(\d+)", summary)
    if match is None:
        return None
    left = int(match.group(1))
    right = int(match.group(2))
    if left > right:
        return "up"
    if left < right:
        return "down"
    return None


def _advancer_ratio_direction(summary: str) -> str | None:
    match = re.search(r"(\d+)\s*/\s*(\d+)\s*上涨", summary)
    if match is None:
        return _ratio_direction(summary)
    advancers = int(match.group(1))
    total = int(match.group(2))
    decliners = max(0, total - advancers)
    if advancers > decliners:
        return "up"
    if advancers < decliners:
        return "down"
    return None


def _breadth_magnitude(summary: str) -> float | None:
    match = re.search(r"(\d+)\s*/\s*(\d+)", summary)
    if match is not None:
        left = int(match.group(1))
        right = int(match.group(2))
        total = left + right
        if total > 0:
            return abs((left - right) / total * 3.0)
    return _mean_abs(
        _labeled_metric(summary, "RSP/SPY"),
        _labeled_metric(summary, "IWM/SPY"),
        _labeled_metric(summary, "QQQ/SPY"),
    )


def _mean_abs(*metrics: float | None) -> float | None:
    values = [abs(metric) for metric in metrics if metric is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _scaled_metric(metric: float | None, scale: float) -> float | None:
    if metric is None:
        return None
    return metric * scale


def _source_tier(diagnostics: Mapping[str, Any], evidence: Mapping[str, Any]) -> str:
    if _text(diagnostics.get("sourceTier")):
        return _text(diagnostics.get("sourceTier"))
    inputs = evidence.get("inputs")
    if isinstance(inputs, Sequence):
        for raw_input in inputs:
            if not isinstance(raw_input, Mapping):
                continue
            if _text(raw_input.get("sourceType")):
                return _text(raw_input.get("sourceType"))
    return _text(evidence.get("source")) or "unknown"


def _degradation_reason(diagnostics: Mapping[str, Any], evidence: Mapping[str, Any]) -> str | None:
    return (
        _text(diagnostics.get("degradationReason"))
        or _text(evidence.get("degradationReason"))
        or _text(diagnostics.get("scoreExclusionReason"))
        or _text(diagnostics.get("proxyObservationOnlyReason"))
        or None
    )


def _label(indicator: Mapping[str, Any]) -> str:
    return _text(indicator.get("label")) or _text(indicator.get("key")) or "Unknown"


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = _text(value).lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return default


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = _text(value).lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _optional_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
