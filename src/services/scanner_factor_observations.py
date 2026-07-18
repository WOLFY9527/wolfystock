# -*- coding: utf-8 -*-
"""Additive scanner-to-factor observation export helpers."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.factor_observations import coerce_factor_evidence, coerce_factor_observation
from src.services.market_data_source_registry import project_source_provenance


SCANNER_FACTOR_OBSERVATION_VERSION = "scanner_factor_observation_v1"

_COMPONENT_FACTOR_MAP: tuple[dict[str, str], ...] = (
    {"component": "trend", "factor_id": "trend.trend_strength_20d"},
    {"component": "momentum", "factor_id": "momentum.momentum_21d"},
    {"component": "breakout", "factor_id": "trend.breakout_readiness_20d"},
    {"component": "liquidity", "factor_id": "liquidity.liquidity_support_20d"},
    {"component": "activity", "factor_id": "activity.activity_burst_10d"},
    {"component": "volatility_quality", "factor_id": "volatility_quality.volatility_quality_21d"},
    {"component": "relative_strength", "factor_id": "relative_strength.relative_strength_63d"},
    {"component": "sector_bonus", "factor_id": "sector_context.sector_relative_breadth_20d"},
    {"component": "benchmark_relative", "factor_id": "relative_strength.benchmark_relative_20d"},
    {"component": "gap_context", "factor_id": "trend.gap_context_1d"},
)

_QUOTE_PRIMARY_COMPONENTS = {"gap_context"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool:
    return bool(value)


def _profile_key(diagnostics: Mapping[str, Any]) -> str:
    return _text(diagnostics.get("profile")).lower()


def _freshness_status(
    component: str,
    *,
    source_type: str,
    quote_available: bool,
    is_fallback: bool,
    is_stale: bool,
    is_partial: bool,
) -> str:
    if is_fallback:
        return "fallback"
    if is_stale:
        return "stale"
    if component in _QUOTE_PRIMARY_COMPONENTS and quote_available:
        return "live"
    if source_type == "cache_snapshot":
        return "cached"
    if is_partial:
        return "partial"
    if source_type in {"exchange_public", "official_public", "public_proxy", "unofficial_proxy"}:
        return "fresh"
    if source_type == "missing":
        return "unavailable"
    return "partial"


def _component_extra_evidence(component: str, candidate: Mapping[str, Any]) -> dict[str, Any] | None:
    metric_fields = {
        "trend": ("MA20 slope 5D", "ma20_slope_pct", candidate.get("ma20_slope_pct")),
        "momentum": ("Return 20D", "ret_20d", candidate.get("ret_20d")),
        "breakout": ("Distance To 20D High", "distance_to_20d_high_pct", candidate.get("distance_to_20d_high_pct")),
        "liquidity": ("Average Amount 20D", "avg_amount_20", candidate.get("avg_amount_20")),
        "activity": ("Volume Expansion 20D", "volume_expansion_20", candidate.get("volume_expansion_20")),
        "volatility_quality": ("ATR20%", "atr20_pct", candidate.get("atr20_pct")),
        "relative_strength": ("Relative Strength Percentile", "relative_strength_pct", candidate.get("_relative_strength_pct")),
        "benchmark_relative": ("Benchmark Relative 20D", "benchmark_relative_20d", candidate.get("benchmark_relative_20d")),
        "gap_context": ("Gap Percent", "gap_pct", candidate.get("gap_pct")),
    }
    if component == "sector_bonus":
        matched = ", ".join(str(item) for item in (candidate.get("_matched_sectors") or []) if _text(item))
        if matched:
            return {
                "evidence_type": "note",
                "title": "Matched sectors",
                "raw_value": matched,
                "summary": matched,
            }
        return None
    title, metric_name, raw_value = metric_fields.get(component, ("", "", None))
    numeric_value = _safe_float(raw_value)
    if numeric_value is None:
        return None
    if abs(numeric_value) > 1_000_000:
        return {
            "evidence_type": "note",
            "title": title,
            "metric_name": metric_name,
            "raw_value": str(raw_value),
            "summary": str(raw_value),
        }
    return {
        "evidence_type": "metric",
        "title": title,
        "metric_name": metric_name,
        "numeric_value": numeric_value,
    }


def _build_observation_record(
    *,
    component: str,
    factor_id: str,
    candidate: Mapping[str, Any],
    factor_evidence: Mapping[str, Any],
    market: str,
) -> dict[str, Any]:
    diagnostics = dict(candidate.get("_diagnostics") or {})
    explainability = dict(diagnostics.get("score_explainability") or {})
    source_confidence = dict(explainability.get("source_confidence") or {})
    quote_diag = dict(diagnostics.get("quote_context") or {})
    value = float(candidate["_component_scores"][component])
    as_of = _text(factor_evidence.get("asOf"))
    observed_at = _text(factor_evidence.get("observedAt"))
    profile = _profile_key(diagnostics)
    source_name = _text(factor_evidence.get("source"))
    candidate_is_partial = _bool(source_confidence.get("isPartial")) or bool(explainability.get("missing_evidence"))
    provenance = project_source_provenance(
        source=source_name,
        freshness="live" if quote_diag.get("available") else "cached",
        is_fallback=_bool(source_confidence.get("isFallback")),
        is_stale=_bool(source_confidence.get("isStale")),
        is_from_snapshot=source_name in {"local_db", "local_db_us_history", "local_db_hk_history", "snapshot"},
    )
    freshness_status = _freshness_status(
        component,
        source_type=str(provenance["sourceType"]),
        quote_available=_bool(quote_diag.get("available")),
        is_fallback=_bool(source_confidence.get("isFallback")),
        is_stale=_bool(source_confidence.get("isStale")),
        is_partial=candidate_is_partial,
    )

    evidence_items = [
        {
            "factor_id": factor_id,
            "evidence_type": "metric",
            "title": f"Scanner {component} component score",
            "metric_name": f"scanner_component_score.{component}",
            "numeric_value": value,
            "source_name": source_name,
            "source_type": provenance["sourceType"],
            "as_of": as_of,
            "observed_at": observed_at,
            "freshness_status": freshness_status,
            "confidence": float(source_confidence.get("confidenceWeight") or explainability.get("score_confidence") or 1.0),
            "is_fallback": _bool(source_confidence.get("isFallback")),
            "is_stale": _bool(source_confidence.get("isStale")),
            "is_partial": candidate_is_partial,
        }
    ]
    extra_evidence = _component_extra_evidence(component, candidate)
    if extra_evidence is not None:
        evidence_items.append(
            {
                **extra_evidence,
                "factor_id": factor_id,
                "source_name": source_name,
                "source_type": provenance["sourceType"],
                "as_of": as_of,
                "observed_at": observed_at,
                "freshness_status": freshness_status,
                "confidence": float(source_confidence.get("confidenceWeight") or explainability.get("score_confidence") or 1.0),
                "is_fallback": _bool(source_confidence.get("isFallback")),
                "is_stale": _bool(source_confidence.get("isStale")),
                "is_partial": candidate_is_partial,
            }
        )

    observation = coerce_factor_observation(
        {
            "factor_id": factor_id,
            "symbol": _text(candidate.get("symbol")).upper(),
            "value": value,
            "percentile": _safe_float(candidate.get("_relative_strength_pct")) if component == "relative_strength" else None,
            "basis": f"scanner_component_score:{component}",
            "evidences": [coerce_factor_evidence(item).model_dump() for item in evidence_items],
            "source_name": source_name,
            "source_type": provenance["sourceType"],
            "as_of": as_of,
            "observed_at": observed_at,
            "freshness_status": freshness_status,
            "confidence": float(source_confidence.get("confidenceWeight") or explainability.get("score_confidence") or 1.0),
            "is_fallback": _bool(source_confidence.get("isFallback")),
            "is_stale": _bool(source_confidence.get("isStale")),
            "is_partial": candidate_is_partial,
        }
    )
    observation_id = (
        f"scanner_factor_observation:{market.lower()}:{profile}:{_text(candidate.get('symbol')).lower()}:"
        f"{factor_id}:{component}:{as_of}"
    )
    return {
        "observation_id": observation_id,
        "component": component,
        "factor_id": factor_id,
        "market": market.lower(),
        "profile": profile,
        "degradation_reason": explainability.get("degradation_reason"),
        "missing_evidence": list(explainability.get("missing_evidence") or []),
        "source_confidence": source_confidence,
        "factor_evidence": dict(factor_evidence),
        "observation": observation.model_dump(),
    }


def build_scanner_factor_observations(
    candidate: Mapping[str, Any],
    *,
    market: str,
    observed_at: str,
) -> list[dict[str, Any]]:
    payload = dict(candidate or {})
    components = payload.get("_component_scores")
    if not isinstance(components, Mapping):
        return []
    diagnostics = payload.get("_diagnostics")
    factor_contract = diagnostics.get("factorEvidence") if isinstance(diagnostics, Mapping) else None
    factors = factor_contract.get("factors") if isinstance(factor_contract, Mapping) else None
    if not isinstance(factors, Sequence):
        return []
    factor_by_component = {
        str(item.get("component")): item
        for item in factors
        if isinstance(item, Mapping)
        and item.get("state") == "valid"
        and item.get("scoreContributionAllowed") is True
    }
    exported: list[dict[str, Any]] = []
    for item in _COMPONENT_FACTOR_MAP:
        component = item["component"]
        if component not in components:
            continue
        factor_evidence = factor_by_component.get(component)
        if factor_evidence is None:
            continue
        value = _safe_float(components.get(component))
        if value is None:
            continue
        exported.append(
            _build_observation_record(
                component=component,
                factor_id=item["factor_id"],
                candidate=payload,
                factor_evidence=factor_evidence,
                market=market,
            )
        )
    return exported


def attach_scanner_factor_observations(
    candidate: dict[str, Any],
    *,
    market: str,
    observed_at: str,
) -> list[dict[str, Any]]:
    diagnostics = dict(candidate.get("_diagnostics") or {})
    exported = build_scanner_factor_observations(candidate, market=market, observed_at=observed_at)
    diagnostics["factor_observation_version"] = SCANNER_FACTOR_OBSERVATION_VERSION
    diagnostics["factor_observations"] = exported
    candidate["_diagnostics"] = diagnostics
    return exported


__all__ = [
    "SCANNER_FACTOR_OBSERVATION_VERSION",
    "attach_scanner_factor_observations",
    "build_scanner_factor_observations",
]
