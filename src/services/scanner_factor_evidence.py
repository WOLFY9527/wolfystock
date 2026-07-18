# -*- coding: utf-8 -*-
"""Fail-closed factor evidence contract for scanner scoring and ranking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.services.market_data_source_registry import resolve_source_type


SCANNER_FACTOR_EVIDENCE_VERSION = "scanner_factor_evidence_v1"
_AUTHORIZED_SOURCE_TYPES = frozenset(
    {"authorized_licensed_feed", "exchange_public", "official_public", "cache_snapshot"}
)
_PROXY_SOURCE_TYPES = frozenset({"public_proxy", "unofficial_proxy"})


@dataclass(frozen=True)
class FactorRequirement:
    component: str
    factor_id: str
    fields: tuple[str, ...]
    required_bars: int
    source_kind: str
    required: bool = True


_COMMON_HISTORY = (
    FactorRequirement("trend", "trend.trend_strength_20d", ("price_or_close", "ma20", "ma60", "ma20_slope_pct"), 60, "history"),
    FactorRequirement("volatility_quality", "volatility_quality.volatility_quality_21d", ("atr20_pct",), 20, "history"),
    FactorRequirement("relative_strength", "relative_strength.relative_strength_63d", ("_relative_strength_pct",), 21, "history"),
)
_REQUIREMENTS = {
    "cn": (
        FactorRequirement("pre_rank", "scanner.pre_rank", ("pre_rank_score",), 0, "snapshot"),
        _COMMON_HISTORY[0],
        FactorRequirement("momentum", "momentum.momentum_21d", ("ret_5d", "ret_20d", "recent_up_days_10"), 21, "history"),
        FactorRequirement("breakout", "trend.breakout_readiness_20d", ("distance_to_20d_high_pct", "amount_ratio_20"), 21, "history"),
        FactorRequirement("liquidity", "liquidity.liquidity_support_20d", ("avg_amount_20", "amount"), 20, "snapshot"),
        FactorRequirement("activity", "activity.activity_burst_10d", ("turnover_rate", "volume_ratio", "volume_expansion_20"), 20, "snapshot"),
        _COMMON_HISTORY[1],
        _COMMON_HISTORY[2],
        FactorRequirement("sector_bonus", "sector_context.sector_relative_breadth_20d", ("_matched_sectors",), 0, "snapshot", False),
    ),
    "us": (
        FactorRequirement("pre_rank", "scanner.pre_rank", ("pre_rank_score",), 0, "history"),
        _COMMON_HISTORY[0],
        FactorRequirement("momentum", "momentum.momentum_21d", ("ret_5d", "ret_20d", "ret_60d", "recent_up_days_10"), 61, "history"),
        FactorRequirement("liquidity", "liquidity.liquidity_support_20d", ("avg_amount_20", "avg_volume_20"), 20, "history"),
        FactorRequirement("activity", "activity.activity_burst_10d", ("volume_expansion_20", "avg_amount_20"), 20, "history"),
        _COMMON_HISTORY[1],
        _COMMON_HISTORY[2],
        FactorRequirement("benchmark_relative", "relative_strength.benchmark_relative_20d", ("benchmark_relative_20d",), 21, "history"),
        FactorRequirement("gap_context", "trend.gap_context_1d", ("gap_pct",), 1, "quote"),
    ),
}
_REQUIREMENTS["hk"] = _REQUIREMENTS["us"]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _has_value(candidate: Mapping[str, Any], field: str) -> bool:
    if field == "price_or_close":
        return _has_value(candidate, "price") or _has_value(candidate, "close")
    value = candidate.get(field)
    if field == "_matched_sectors":
        return isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and bool(value)
    if value is None or (isinstance(value, str) and not value.strip()):
        return False
    try:
        number = float(value)
        return number == number and number not in {float("inf"), float("-inf")}
    except (TypeError, ValueError):
        return False


def _freshness(source: Mapping[str, Any]) -> str:
    readiness = _mapping(source.get("historicalOhlcvReadiness"))
    return _text(
        source.get("freshnessState")
        or source.get("freshness_state")
        or source.get("freshness")
        or readiness.get("freshnessState")
    ).lower()


def _source_context(candidate: Mapping[str, Any], kind: str) -> dict[str, Any]:
    diagnostics = _mapping(candidate.get("_diagnostics") or candidate.get("diagnostics"))
    history = _mapping(diagnostics.get("history"))
    quote = _mapping(diagnostics.get("quote_context"))
    observed_at = _text(diagnostics.get("scanner_observed_at")) or None
    if kind == "history":
        source = _text(history.get("source") or candidate.get("history_source"))
        return {
            "source": source,
            "sourceType": resolve_source_type(source) if source else "missing",
            "freshness": _freshness(history),
            "stale": bool(history.get("stale")) or _freshness(history) == "stale",
            "asOf": _text(history.get("latest_trade_date") or candidate.get("last_trade_date")) or None,
            "observedAt": _text(history.get("observed_at") or history.get("retrieved_at")) or observed_at,
        }
    if kind == "quote":
        source = _text(quote.get("source"))
        return {
            "source": source,
            "sourceType": resolve_source_type(source, source_type=quote.get("sourceType")) if source else "missing",
            "freshness": _freshness(quote),
            "stale": bool(quote.get("stale")) or _freshness(quote) == "stale",
            "asOf": _text(quote.get("as_of") or quote.get("asOf")) or observed_at,
            "observedAt": _text(quote.get("observed_at") or quote.get("observedAt")) or observed_at,
        }
    source = _text(candidate.get("snapshot_source") or diagnostics.get("snapshot_source"))
    return {
        "source": source,
        "sourceType": resolve_source_type(source) if source else "missing",
        "freshness": _text(diagnostics.get("snapshot_freshness")).lower(),
        "stale": _text(diagnostics.get("snapshot_freshness")).lower() == "stale",
        "asOf": _text(diagnostics.get("snapshot_as_of")) or observed_at,
        "observedAt": _text(diagnostics.get("snapshot_observed_at")) or observed_at,
    }


def _source_authority(source_type: str) -> str:
    if source_type == "authorized_licensed_feed":
        return "authorized"
    if source_type in {"exchange_public", "official_public"}:
        return "official"
    if source_type == "cache_snapshot":
        return "verified_cache"
    if source_type in _PROXY_SOURCE_TYPES:
        return "proxy"
    return "unavailable"


def _factor_state(
    requirement: FactorRequirement,
    *,
    candidate: Mapping[str, Any],
    usable_bars: int,
    source: Mapping[str, Any],
) -> tuple[str, list[str]]:
    missing_fields = [field for field in requirement.fields if not _has_value(candidate, field)]
    if source.get("sourceType") == "missing":
        return "unavailable", missing_fields
    if usable_bars < requirement.required_bars:
        return "insufficient", missing_fields
    if missing_fields:
        return "unavailable", missing_fields
    missing_timestamps = [field for field in ("source.asOf", "source.observedAt") if not source.get(field.split(".", 1)[1])]
    if missing_timestamps:
        return "unavailable", missing_timestamps
    if source.get("stale"):
        return "stale", []
    if source.get("sourceType") not in _AUTHORIZED_SOURCE_TYPES:
        return "rejected", []
    return "valid", []


def build_scanner_factor_evidence(candidate: Mapping[str, Any], *, market: str) -> dict[str, Any]:
    normalized_market = _text(market).lower()
    requirements = _REQUIREMENTS.get(normalized_market, ())
    diagnostics = _mapping(candidate.get("_diagnostics") or candidate.get("diagnostics"))
    history = _mapping(diagnostics.get("history"))
    usable_bars = max(0, int(history.get("rows") or candidate.get("history_rows") or 0))
    components = _mapping(candidate.get("_component_scores") or diagnostics.get("component_scores"))
    factors: list[dict[str, Any]] = []
    blockers: list[str] = []
    for requirement in requirements:
        source = _source_context(candidate, requirement.source_kind)
        state, missing_fields = _factor_state(
            requirement,
            candidate=candidate,
            usable_bars=usable_bars,
            source=source,
        )
        factor = {
            "component": requirement.component,
            "factorId": requirement.factor_id,
            "required": requirement.required,
            "state": state,
            "requiredBars": requirement.required_bars,
            "usableBars": usable_bars if requirement.required_bars else 0,
            "missingFields": missing_fields,
            "source": source["source"] or None,
            "sourceType": source["sourceType"],
            "sourceAuthority": _source_authority(str(source["sourceType"])),
            "freshness": source["freshness"] or "unknown",
            "asOf": source["asOf"],
            "observedAt": source["observedAt"],
            "rawComponentScore": components.get(requirement.component),
            "scoreContributionAllowed": state == "valid",
        }
        factors.append(factor)
        if requirement.required and state != "valid":
            blockers.append(f"{requirement.component}:{state}")
    state_counts = {state: sum(item["state"] == state for item in factors) for state in ("unavailable", "insufficient", "stale", "rejected", "valid")}
    return {
        "contractVersion": SCANNER_FACTOR_EVIDENCE_VERSION,
        "market": normalized_market or "unknown",
        "overallState": "valid" if requirements and not blockers else "blocked",
        "rankingEligible": bool(requirements) and not blockers,
        "requiredFactorCount": sum(item["required"] for item in factors),
        "validRequiredFactorCount": sum(item["required"] and item["state"] == "valid" for item in factors),
        "stateCounts": state_counts,
        "blockers": blockers,
        "factors": factors,
    }


def apply_scanner_factor_evidence(candidate: dict[str, Any], *, market: str) -> dict[str, Any]:
    contract = build_scanner_factor_evidence(candidate, market=market)
    components = candidate.get("_component_scores")
    if isinstance(components, dict):
        for factor in contract["factors"]:
            component = str(factor["component"])
            if factor["state"] != "valid" and component in components:
                components[component] = 0.0
    diagnostics = _mapping(candidate.get("_diagnostics"))
    diagnostics["factorEvidence"] = contract
    candidate["_diagnostics"] = diagnostics
    return contract


__all__ = [
    "SCANNER_FACTOR_EVIDENCE_VERSION",
    "apply_scanner_factor_evidence",
    "build_scanner_factor_evidence",
]
