# -*- coding: utf-8 -*-
"""Helper-only Rotation provenance sidecar builder."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from src.services.source_provenance_contract import (
    SOURCE_PROVENANCE_CONTRACT_VERSION,
    build_fallback_proxy_source_provenance,
    build_observation_only_source_provenance,
    build_score_grade_source_provenance,
    build_source_provenance,
    build_unknown_source_provenance,
    summarize_source_provenance,
)


ROTATION_SOURCE_PROVENANCE_VERSION = "rotation_source_provenance_sidecar_v1"

_DOMAIN_SPECS = (
    ("rotation", "market_data", "rotation"),
    ("sectorTheme", "research", "sectortheme"),
    ("relativeStrength", "market_data", "relativestrength"),
    ("fundFlow", "portfolio", "fundflow"),
    ("breadth", "market_data", "breadth"),
    ("trend", "research", "trend"),
    ("taxonomy", "macro", "taxonomy"),
    ("marketUniverse", "macro", "marketuniverse"),
    ("freshness", "market_data", "freshness"),
)
_PROXY_MARKERS = ("proxy", "unofficial", "fallback", "taxonomy_only", "fixture", "demo", "synthetic")
_FAIL_CLOSED_MARKERS = (
    "taxonomy_only",
    "observation_only",
    "observe_only",
    "proxy",
    "fallback",
    "stale",
    "unknown",
    "demo",
    "fixture",
    "synthetic",
    "missing",
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _lower_text(value: Any) -> str:
    return _text(value).lower()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(value)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect_texts(*values: Any) -> list[str]:
    items: list[str] = []
    for value in values:
        if isinstance(value, Mapping):
            items.extend(_collect_texts(*value.values()))
        elif isinstance(value, (list, tuple, set, frozenset)):
            items.extend(_collect_texts(*value))
        else:
            text = _text(value)
            if text:
                items.append(text)
    return items


def _contains_any(values: Iterable[Any], markers: Iterable[str]) -> bool:
    lowered = " ".join(_lower_text(value) for value in values if value is not None)
    return any(marker in lowered for marker in markers)


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _normalized_source_tier(values: Iterable[Any]) -> str:
    lowered = " ".join(_lower_text(value) for value in values if value is not None)
    if any(marker in lowered for marker in ("fixture", "demo", "synthetic")):
        return "synthetic_fixture"
    if "proxy" in lowered or "unofficial" in lowered:
        return "unofficial_proxy"
    if "fallback" in lowered or "taxonomy_only" in lowered:
        return "fallback_static"
    if "cache" in lowered or "snapshot" in lowered:
        return "cache_snapshot"
    if any(marker in lowered for marker in ("authorized", "licensed", "live")):
        return "authorized_licensed_feed"
    if "official" in lowered:
        return "official_public"
    return "unknown"


def _normalized_freshness(values: Iterable[Any]) -> str:
    lowered = " ".join(_lower_text(value) for value in values if value is not None)
    if any(marker in lowered for marker in ("fixture", "demo", "synthetic")):
        return "synthetic"
    if "stale" in lowered:
        return "stale"
    if "fallback" in lowered:
        return "fallback"
    if "delay" in lowered:
        return "delayed"
    if "cache" in lowered or "cached" in lowered or "snapshot" in lowered:
        return "cached"
    if "fresh" in lowered or "live" in lowered:
        return "fresh"
    return "unknown"


def _source_context(
    *,
    theme: Mapping[str, Any],
    readiness: Mapping[str, Any],
    evidence_snapshot: Mapping[str, Any],
    market_context: Mapping[str, Any],
) -> dict[str, str]:
    source_id = _first_text(
        theme.get("sourceId"),
        theme.get("source"),
        evidence_snapshot.get("sourceId"),
        evidence_snapshot.get("source"),
        market_context.get("sourceId"),
        market_context.get("source"),
        "rotation_theme_projection",
    )
    source_label = _first_text(
        theme.get("sourceLabel"),
        evidence_snapshot.get("sourceLabel"),
        market_context.get("sourceLabel"),
        theme.get("themeId"),
        "Rotation Theme Projection",
    )
    freshness = _first_text(
        theme.get("freshness"),
        evidence_snapshot.get("freshness"),
        market_context.get("freshness"),
        readiness.get("status"),
    )
    return {
        "source_id": source_id,
        "source_label": source_label,
        "freshness": freshness or "unknown",
    }


def _base_signals(
    *,
    theme: Mapping[str, Any],
    readiness: Mapping[str, Any],
    evidence_snapshot: Mapping[str, Any],
    market_context: Mapping[str, Any],
) -> dict[str, Any]:
    relative_strength = _mapping(theme.get("relativeStrength"))
    breadth = _mapping(theme.get("breadth"))
    volume = _mapping(theme.get("volume"))
    proxy_quality = _mapping(theme.get("proxyQuality"))
    fund_flow = _mapping(evidence_snapshot.get("fundFlowEvidence"))
    texts = _collect_texts(theme, readiness, evidence_snapshot, market_context, fund_flow)
    context = _source_context(
        theme=theme,
        readiness=readiness,
        evidence_snapshot=evidence_snapshot,
        market_context=market_context,
    )
    source_tier = _normalized_source_tier(
        [
            theme.get("sourceTier"),
            theme.get("sourceType"),
            evidence_snapshot.get("sourceType"),
            market_context.get("sourceType"),
            context["source_id"],
            context["source_label"],
        ]
    )
    freshness_state = _normalized_freshness(
        [
            theme.get("freshness"),
            evidence_snapshot.get("freshness"),
            market_context.get("freshness"),
            context["freshness"],
        ]
    )
    state_markers = [
        theme.get("freshness"),
        theme.get("sourceType"),
        theme.get("sourceTier"),
        theme.get("source"),
        readiness.get("status"),
        readiness.get("missingReasonCodes"),
        proxy_quality.get("hasStaleProxy"),
    ]
    taxonomy_only = bool(theme.get("taxonomyOnly")) or bool(theme.get("staticThemeOnly")) or _contains_any(
        [theme.get("source"), theme.get("sourceType"), readiness.get("missingReasonCodes")],
        ("taxonomy_only", "local_taxonomy"),
    )
    observation_only = (
        _bool(theme.get("observationOnly"))
        or _bool(readiness.get("status") in {"observe_only", "blocked"})
        or freshness_state in {"stale", "fallback", "delayed", "synthetic", "unknown"}
        or _contains_any(state_markers, _FAIL_CLOSED_MARKERS)
    )
    fallback_or_proxy = (
        _bool(theme.get("fallbackUsed"))
        or _bool(theme.get("isFallback"))
        or _bool(proxy_quality.get("hasStaleProxy"))
        or _contains_any(
            [
                source_tier,
                theme.get("sourceType"),
                theme.get("sourceTier"),
                theme.get("source"),
                theme.get("freshness"),
                readiness.get("status"),
                readiness.get("missingReasonCodes"),
            ],
            _PROXY_MARKERS,
        )
    )
    structured_relative_strength = relative_strength if isinstance(relative_strength, Mapping) else {}
    has_relative_strength = _number(structured_relative_strength.get("averageRelativeStrengthPercent")) is not None
    has_breadth = _number(breadth.get("percentUp")) is not None and _number(breadth.get("percentOutperformingBenchmark")) is not None
    has_volume = _number(volume.get("averageRelativeVolume")) is not None
    has_trend = bool(_sequence(theme.get("trend")))
    return {
        "context": context,
        "source_tier": source_tier,
        "freshness_state": freshness_state,
        "taxonomy_only": taxonomy_only,
        "observation_only": observation_only,
        "fallback_or_proxy": fallback_or_proxy,
        "has_relative_strength": has_relative_strength,
        "has_breadth": has_breadth,
        "has_volume": has_volume,
        "has_trend": has_trend,
        "has_market_universe": bool(_first_text(market_context.get("marketUniverse"), theme.get("market"))),
        "has_fund_flow": bool(
            _first_text(
                fund_flow.get("source"),
                fund_flow.get("methodology"),
                fund_flow.get("freshness"),
            )
        ),
        "readiness_status": _first_text(readiness.get("status"), "unknown"),
    }


def _domain_limitations(domain_name: str, signals: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    limitations: list[str] = []
    next_evidence_needed: list[str] = []

    if _bool(signals.get("taxonomy_only")):
        limitations.append("taxonomy_only")
        next_evidence_needed.append("authoritative_rotation_runtime_evidence")
    if not _bool(signals.get("has_relative_strength")) and domain_name in {"rotation", "relativeStrength", "sectorTheme"}:
        limitations.append("relative_strength_missing")
        next_evidence_needed.append("structured_relative_strength")
    if not _bool(signals.get("has_breadth")) and domain_name in {"rotation", "breadth", "sectorTheme"}:
        limitations.append("breadth_missing")
        next_evidence_needed.append("breadth_confirmation")
    if not _bool(signals.get("has_volume")) and domain_name in {"rotation", "fundFlow", "trend"}:
        limitations.append("volume_missing")
        next_evidence_needed.append("volume_confirmation")
    if not _bool(signals.get("has_trend")) and domain_name == "trend":
        limitations.append("trend_missing")
        next_evidence_needed.append("trend_windows")
    if not _bool(signals.get("has_fund_flow")) and domain_name == "fundFlow":
        limitations.append("fund_flow_missing")
        next_evidence_needed.append("fund_flow_methodology")
    if not _bool(signals.get("has_market_universe")) and domain_name == "marketUniverse":
        limitations.append("market_universe_missing")
        next_evidence_needed.append("market_universe_mapping")
    if domain_name == "freshness" and signals.get("freshness_state") in {"stale", "fallback", "delayed", "synthetic", "unknown"}:
        limitations.append(f"{signals['freshness_state']}_source")
        next_evidence_needed.append("fresh_rotation_snapshot")
    if _bool(signals.get("fallback_or_proxy")):
        limitations.append("fallback_or_proxy_source")
    if _bool(signals.get("observation_only")):
        limitations.append("observation_only")

    return list(dict.fromkeys(limitations)), list(dict.fromkeys(next_evidence_needed))


def _entry_for_domain(
    *,
    domain_name: str,
    evidence_domain: str,
    debug_suffix: str,
    signals: Mapping[str, Any],
) -> dict[str, Any]:
    context = _mapping(signals.get("context"))
    source_id = context.get("source_id")
    source_label = context.get("source_label")
    freshness_state = _text(signals.get("freshness_state"))
    source_tier = _text(signals.get("source_tier"))
    debug_ref = f"source-provenance:rotation:{debug_suffix}"

    if not source_id or not source_label:
        return build_unknown_source_provenance(evidence_domain=evidence_domain, debug_ref=debug_ref)

    if domain_name in {"taxonomy", "marketUniverse"} and source_tier not in {
        "unofficial_proxy",
        "fallback_static",
        "synthetic_fixture",
    }:
        source_tier = "official_public" if source_tier != "unknown" else "unknown"
    if domain_name == "marketUniverse" and freshness_state == "fresh":
        freshness_state = "cached"

    limitations, next_evidence_needed = _domain_limitations(domain_name, signals)
    if limitations:
        return build_source_provenance(
            source_id=source_id,
            source_label=source_label,
            evidence_domain=evidence_domain,
            authority_tier="observation_only",
            freshness_state=freshness_state,
            source_tier=source_tier,
            fallback_or_proxy=_bool(signals.get("fallback_or_proxy")),
            observation_only=True,
            score_contribution_allowed=False,
            limitations=limitations,
            next_evidence_needed=next_evidence_needed,
            debug_ref=debug_ref,
        )

    if _bool(signals.get("observation_only")):
        if _bool(signals.get("fallback_or_proxy")):
            return build_fallback_proxy_source_provenance(
                source_id=source_id,
                source_label=source_label,
                evidence_domain=evidence_domain,
                freshness_state=freshness_state,
                source_tier=source_tier,
                debug_ref=debug_ref,
            )
        return build_observation_only_source_provenance(
            source_id=source_id,
            source_label=source_label,
            evidence_domain=evidence_domain,
            freshness_state=freshness_state if freshness_state != "unknown" else "cached",
            source_tier=source_tier,
            debug_ref=debug_ref,
        )

    return build_score_grade_source_provenance(
        source_id=source_id,
        source_label=source_label,
        evidence_domain=evidence_domain,
        freshness_state=freshness_state if freshness_state != "unknown" else "fresh",
        source_tier=source_tier,
        debug_ref=debug_ref,
    )


def build_rotation_source_provenance_sidecar(
    *,
    theme: Mapping[str, Any] | None = None,
    readiness: Mapping[str, Any] | None = None,
    evidence_snapshot: Mapping[str, Any] | None = None,
    market_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic helper-only Rotation provenance sidecar."""

    theme_map = _mapping(theme)
    readiness_map = _mapping(readiness)
    evidence_snapshot_map = _mapping(evidence_snapshot)
    market_context_map = _mapping(market_context)
    signals = _base_signals(
        theme=theme_map,
        readiness=readiness_map,
        evidence_snapshot=evidence_snapshot_map,
        market_context=market_context_map,
    )
    entries = sorted(
        [
            _entry_for_domain(
                domain_name=domain_name,
                evidence_domain=evidence_domain,
                debug_suffix=debug_suffix,
                signals=signals,
            )
            for domain_name, evidence_domain, debug_suffix in _DOMAIN_SPECS
        ],
        key=lambda item: (item["sourceId"], item["debugRef"], item["evidenceDomain"]),
    )
    summary = summarize_source_provenance(entries)
    return {
        "contractVersion": ROTATION_SOURCE_PROVENANCE_VERSION,
        "sourceProvenanceContractVersion": SOURCE_PROVENANCE_CONTRACT_VERSION,
        "entryCount": summary["entryCount"],
        "authorityTierCounts": summary["authorityTierCounts"],
        "freshnessStateCounts": summary["freshnessStateCounts"],
        "evidenceDomainCounts": summary["evidenceDomainCounts"],
        "fallbackOrProxyCount": summary["fallbackOrProxyCount"],
        "observationOnlyCount": summary["observationOnlyCount"],
        "scoreContributionAllowedCount": summary["scoreContributionAllowedCount"],
        "entries": entries,
    }


def summarize_rotation_source_provenance_sidecar(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return bounded summary for helper-only Rotation provenance entries."""

    return summarize_source_provenance(entries)


__all__ = [
    "ROTATION_SOURCE_PROVENANCE_VERSION",
    "build_rotation_source_provenance_sidecar",
    "summarize_rotation_source_provenance_sidecar",
]
