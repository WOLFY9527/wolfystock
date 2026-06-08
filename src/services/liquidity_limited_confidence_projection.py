# -*- coding: utf-8 -*-
"""Inert limited-confidence projection for Liquidity Monitor evidence.

The helper is intentionally standalone: it consumes caller-supplied mappings,
does not import provider/runtime/cache modules, does not call networks, and
does not mutate Liquidity Monitor scoring, regime, or authority fields.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping


LIQUIDITY_LIMITED_CONFIDENCE_PROJECTION_VERSION = "liquidity_limited_confidence_projection_v1"

_QUALIFIED_OBSERVATION_SOURCE_TYPES = {
    "official_public",
    "official",
    "cache_snapshot",
    "cached_snapshot",
    "local_cache",
}
_FRESHNESS_ALLOWED_FOR_MINIMUM = {"live", "fresh", "cached", "delayed"}
_DEGRADED_FRESHNESS = {
    "fallback",
    "stale",
    "partial",
    "synthetic",
    "mock",
    "unavailable",
    "error",
    "unknown",
}
_PROXY_SOURCE_TYPES = {"public_proxy", "proxy_public", "unofficial_proxy", "unofficial_public_api"}
_FALLBACK_SOURCE_TYPES = {"fallback_static", "static_fallback", "public_web_fallback"}
_SYNTHETIC_SOURCE_TYPES = {"synthetic", "synthetic_fixture", "mock", "fixture"}
_UNAVAILABLE_SOURCE_TYPES = {"unavailable", "missing", "disabled_live_stub", "malformed_fixture"}

_EXPANDING_DIRECTIONS = {
    "expanding",
    "expansion",
    "inflow",
    "inflows",
    "risk_on",
    "risk-on",
    "supportive",
    "easing",
    "positive",
    "up",
    "rising",
    "higher",
    "improving",
}
_CONTRACTING_DIRECTIONS = {
    "contracting",
    "contraction",
    "outflow",
    "outflows",
    "risk_off",
    "risk-off",
    "stress",
    "tightening",
    "negative",
    "down",
    "falling",
    "lower",
    "deteriorating",
}


def project_liquidity_limited_confidence(payload: Mapping[str, Any] | Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Project caller-supplied Liquidity evidence into a limited-confidence posture."""

    input_state = _input_state(payload)
    indicators = [_normalize_indicator(item) for item in _indicator_items(payload)]
    qualified_score_grade = [item for item in indicators if item["scoreGradeQualified"]]
    qualified_observations = [item for item in indicators if item["observationQualified"]]
    disqualified_count = sum(1 for item in indicators if item["disqualificationReasons"])

    score_by_pillar = _first_by_pillar(qualified_score_grade)
    observations_by_pillar = _first_by_pillar(qualified_observations)

    blocking_reasons = _blocking_reasons(
        indicators=indicators,
        score_by_pillar=score_by_pillar,
        observations_by_pillar=observations_by_pillar,
    )
    status, confidence, market_direction, evidence_rule, observation = _projection_decision(
        score_by_pillar=score_by_pillar,
        observations_by_pillar=observations_by_pillar,
        blocking_reasons=blocking_reasons,
    )

    return {
        "version": LIQUIDITY_LIMITED_CONFIDENCE_PROJECTION_VERSION,
        "diagnosticOnly": True,
        "observationOnly": True,
        "authorityGrant": False,
        "decisionGrade": False,
        "confidence": confidence,
        "status": status,
        "reasonCode": status,
        "marketDirection": market_direction,
        "evidenceRule": evidence_rule,
        "limitedConfidenceObservation": observation,
        "qualifiedScoreGradePillarCount": len(score_by_pillar),
        "qualifiedObservationPillarCount": len(observations_by_pillar),
        "disqualifiedEvidenceCount": disqualified_count,
        "blockingReasons": blocking_reasons,
        "inputState": input_state,
        "evidenceSummary": [
            {
                "key": item["key"],
                "pillar": item["pillar"],
                "direction": item["direction"],
                "scoreGradeQualified": item["scoreGradeQualified"],
                "observationQualified": item["observationQualified"],
                "disqualificationReasons": list(item["disqualificationReasons"]),
            }
            for item in indicators
        ],
    }


def _projection_decision(
    *,
    score_by_pillar: Mapping[str, dict[str, Any]],
    observations_by_pillar: Mapping[str, dict[str, Any]],
    blocking_reasons: list[str],
) -> tuple[str, str, str | None, str | None, dict[str, Any] | None]:
    score_items = list(score_by_pillar.values())
    observation_items = list(observations_by_pillar.values())
    score_directions = _directions(score_items)
    observation_directions = _directions(observation_items)

    if len(score_items) == 1:
        score_direction = next(iter(score_directions), None)
        confirming_observations = [
            item
            for item in observation_items
            if item["pillar"] != score_items[0]["pillar"] and item["direction"] == score_direction
        ]
        if score_direction and confirming_observations:
            return (
                "market_direction_limited",
                "limited",
                score_direction,
                "score_grade_plus_official_or_cache_observation",
                _market_observation(
                    market_direction=score_direction,
                    evidence_rule="score_grade_plus_official_or_cache_observation",
                    supporting_items=[score_items[0], confirming_observations[0]],
                ),
            )
        return (
            "single_indicator_limited",
            "limited",
            None,
            "single_score_grade_pillar_only",
            {
                "type": "single_indicator_limited",
                "marketDirection": None,
                "supportingPillars": [score_items[0]["pillar"]],
            },
        )

    if not score_items and len(observation_items) >= 2 and len(observation_directions) == 1:
        market_direction = next(iter(observation_directions))
        return (
            "market_direction_limited",
            "limited",
            market_direction,
            "two_independent_official_or_cache_observations",
            _market_observation(
                market_direction=market_direction,
                evidence_rule="two_independent_official_or_cache_observations",
                supporting_items=observation_items[:2],
            ),
        )

    if not blocking_reasons:
        blocking_reasons.append("minimum_evidence_not_satisfied")
    return "insufficient_evidence", "low", None, None, None


def _market_observation(
    *,
    market_direction: str,
    evidence_rule: str,
    supporting_items: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "type": "market_direction_limited",
        "marketDirection": market_direction,
        "evidenceRule": evidence_rule,
        "supportingPillars": [str(item["pillar"]) for item in supporting_items],
    }


def _blocking_reasons(
    *,
    indicators: list[dict[str, Any]],
    score_by_pillar: Mapping[str, dict[str, Any]],
    observations_by_pillar: Mapping[str, dict[str, Any]],
) -> list[str]:
    reasons: list[str] = []
    score_directions = _directions(score_by_pillar.values())
    observation_directions = _directions(observations_by_pillar.values())
    qualified_observation_rows = [item for item in indicators if item["observationQualified"]]

    if len(score_directions) > 1:
        reasons.append("conflicting_score_grade_evidence")
    if len(observation_directions) > 1:
        reasons.append("conflicting_official_or_cache_observation")
    if (
        len(score_directions) == 1
        and len(observation_directions) >= 1
        and not observation_directions.issubset(score_directions)
    ):
        reasons.append("conflicting_official_or_cache_observation")
    if len(qualified_observation_rows) >= 2 and len(observations_by_pillar) < 2:
        reasons.append("independent_pillar_count_below_minimum")
    if not score_by_pillar and len(observations_by_pillar) < 2:
        reasons.append("independent_pillar_count_below_minimum")
    if not score_by_pillar and not observations_by_pillar:
        reasons.append("no_qualified_minimum_evidence")

    return _dedupe(reasons)


def _normalize_indicator(item: Mapping[str, Any]) -> dict[str, Any]:
    nested = _nested_sources(item)
    source = _first_text(
        item.get("source"),
        _mapping(item.get("evidence")).get("source"),
        _mapping(item.get("coverageDiagnostics")).get("source"),
        *(entry.get("source") for entry in nested),
    )
    source_type = _first_text(
        item.get("sourceType"),
        item.get("sourceTier"),
        _mapping(item.get("evidence")).get("sourceType"),
        _mapping(item.get("coverageDiagnostics")).get("sourceType"),
        _mapping(item.get("coverageDiagnostics")).get("sourceTier"),
        *(entry.get("sourceType") or entry.get("sourceTier") for entry in nested),
    )
    freshness = _first_text(
        item.get("freshness"),
        _mapping(item.get("evidence")).get("freshness"),
        _mapping(item.get("coverageDiagnostics")).get("freshness"),
        *(entry.get("freshness") for entry in nested),
    )
    direction = _normalize_direction(_first_text(item.get("direction"), item.get("marketDirection")))
    pillar = _first_text(item.get("pillar"), _mapping(item.get("coverageDiagnostics")).get("pillar"), item.get("category"))
    score_allowed = _bool_from_any(
        _first_existing(
            item.get("scoreContributionAllowed"),
            _mapping(item.get("coverageDiagnostics")).get("scoreContributionAllowed"),
            *(entry.get("scoreContributionAllowed") for entry in nested),
        )
    )
    source_authority_allowed = _bool_from_any(
        _first_existing(
            item.get("sourceAuthorityAllowed"),
            _mapping(item.get("coverageDiagnostics")).get("sourceAuthorityAllowed"),
            *(entry.get("sourceAuthorityAllowed") for entry in nested),
        ),
        default=False,
    )
    included_in_score = _bool_from_any(
        _first_existing(
            item.get("includedInScore"),
            item.get("contributesToScore"),
            item.get("scoreGradeAllowed"),
            item.get("scoreGradeEvidenceAllowed"),
            _mapping(item.get("coverageDiagnostics")).get("contributesToScore"),
            _mapping(item.get("coverageDiagnostics")).get("scoreGradeAllowed"),
            _mapping(item.get("coverageDiagnostics")).get("scoreGradeEvidenceAllowed"),
        )
    )
    reasons = _minimum_evidence_disqualification_reasons(
        item,
        nested_sources=nested,
        source=source,
        source_type=source_type,
        freshness=freshness,
        source_authority_allowed=source_authority_allowed,
    )

    has_minimum_quality = bool(pillar and direction and not reasons)
    score_grade_qualified = bool(
        has_minimum_quality
        and included_in_score
        and score_allowed
        and source_authority_allowed
    )
    observation_qualified = bool(
        has_minimum_quality
        and not score_grade_qualified
        and _is_qualified_observation_source(source_type)
        and source_authority_allowed
    )

    if not pillar:
        reasons.append("missing_pillar")
    if not direction:
        reasons.append("missing_direction")
    if not score_grade_qualified and not observation_qualified and _is_unqualified_observation_source(source_type):
        reasons.append("source_not_allowed_for_minimum_evidence")

    return {
        "key": _first_text(item.get("key"), item.get("id")) or "unknown",
        "pillar": pillar or "unknown",
        "direction": direction,
        "scoreGradeQualified": score_grade_qualified,
        "observationQualified": observation_qualified,
        "disqualificationReasons": tuple(_dedupe(reasons)),
    }


def _minimum_evidence_disqualification_reasons(
    item: Mapping[str, Any],
    *,
    nested_sources: list[Mapping[str, Any]],
    source: str,
    source_type: str,
    freshness: str,
    source_authority_allowed: bool,
) -> list[str]:
    reasons: list[str] = []
    diagnostics = _mapping(item.get("coverageDiagnostics"))
    evidence = _mapping(item.get("evidence"))

    source_l = source.lower()
    source_type_l = source_type.lower()
    freshness_l = freshness.lower() or "unknown"

    if "yfinance" in source_l or "yahoo" in source_l:
        reasons.append("proxy_or_yfinance_source")
    if source_type_l in _PROXY_SOURCE_TYPES:
        reasons.append("proxy_source")
    if source_type_l in _FALLBACK_SOURCE_TYPES:
        reasons.append("fallback_source")
    if source_type_l in _SYNTHETIC_SOURCE_TYPES:
        reasons.append("synthetic_source")
    if source_type_l in _UNAVAILABLE_SOURCE_TYPES:
        reasons.append("unavailable_source")
    if not source_type_l:
        reasons.append("missing_source_type")
    if freshness_l in _DEGRADED_FRESHNESS or freshness_l not in _FRESHNESS_ALLOWED_FOR_MINIMUM:
        reasons.append(f"{freshness_l or 'unknown'}_freshness")
    if _any_truthy_flag(item, diagnostics, evidence, nested_sources, "proxyOnly"):
        reasons.append("proxy_only")
    if _any_truthy_flag(item, diagnostics, evidence, nested_sources, "isFallback"):
        reasons.append("fallback_source")
    if _any_truthy_flag(item, diagnostics, evidence, nested_sources, "isStale"):
        reasons.append("stale_source")
    if _any_truthy_flag(item, diagnostics, evidence, nested_sources, "isSynthetic"):
        reasons.append("synthetic_source")
    if _any_truthy_flag(item, diagnostics, evidence, nested_sources, "isUnavailable"):
        reasons.append("unavailable_source")
    if source_authority_allowed is False:
        reasons.append("source_authority_not_allowed")
    return _dedupe(reasons)


def _input_state(payload: Mapping[str, Any] | Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {
            "score": None,
            "regime": None,
            "scoreContributionAllowed": None,
            "sourceAuthorityAllowed": None,
        }
    score = copy.deepcopy(payload.get("score")) if isinstance(payload.get("score"), Mapping) else payload.get("score")
    regime = payload.get("regime")
    if isinstance(score, Mapping):
        regime = score.get("regime", regime)
    return {
        "score": score,
        "regime": regime,
        "scoreContributionAllowed": payload.get("scoreContributionAllowed"),
        "sourceAuthorityAllowed": payload.get("sourceAuthorityAllowed"),
    }


def _indicator_items(payload: Mapping[str, Any] | Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        for key in ("indicators", "indicatorEvidence", "evidence", "pillars"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, Mapping)]
        if any(key in payload for key in ("pillar", "direction", "coverageDiagnostics")):
            return [payload]
        return []
    return [item for item in payload if isinstance(item, Mapping)]


def _nested_sources(item: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    evidence = _mapping(item.get("evidence"))
    inputs = evidence.get("inputs")
    if isinstance(inputs, list):
        return [entry for entry in inputs if isinstance(entry, Mapping)]
    return []


def _first_by_pillar(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        pillar = str(item["pillar"])
        result.setdefault(pillar, item)
    return result


def _directions(items: Iterable[Mapping[str, Any]]) -> set[str]:
    return {str(item["direction"]) for item in items if item.get("direction")}


def _is_qualified_observation_source(source_type: str) -> bool:
    return source_type.lower() in _QUALIFIED_OBSERVATION_SOURCE_TYPES


def _is_unqualified_observation_source(source_type: str) -> bool:
    return bool(source_type) and not _is_qualified_observation_source(source_type)


def _normalize_direction(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized in _EXPANDING_DIRECTIONS:
        return "expanding"
    if normalized in _CONTRACTING_DIRECTIONS:
        return "contracting"
    return None


def _any_truthy_flag(
    item: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    evidence: Mapping[str, Any],
    nested_sources: Iterable[Mapping[str, Any]],
    key: str,
) -> bool:
    return any(
        _bool_from_any(value)
        for value in (
            item.get(key),
            diagnostics.get(key),
            evidence.get(key),
            *(entry.get(key) for entry in nested_sources),
        )
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_existing(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _bool_from_any(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "allowed"}
    return bool(value)


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        result.append(text)
        seen.add(text)
    return result


__all__ = [
    "LIQUIDITY_LIMITED_CONFIDENCE_PROJECTION_VERSION",
    "project_liquidity_limited_confidence",
]
