# -*- coding: utf-8 -*-
"""Helper-only Options provenance sidecar builder.

This module is intentionally inert. It consumes only passed-in mappings/lists
and converts Options readiness/scenario evidence-like inputs into bounded
`SourceProvenanceV1` entries. It does not call providers, caches, env/settings,
runtime DTOs, storage, or network APIs.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from src.services.source_provenance_contract import (
    build_fallback_proxy_source_provenance,
    build_observation_only_source_provenance,
    build_score_grade_source_provenance,
    build_source_provenance,
    build_unknown_source_provenance,
    summarize_source_provenance,
)


_DOMAIN_SPECS = (
    ("underlyingPrice", "market_data", "options-underlying-price"),
    ("optionsChain", "derivatives", "options-options-chain"),
    ("liquidity", "derivatives", "options-liquidity"),
    ("ivGreeks", "derivatives", "options-iv-greeks"),
    ("spread", "derivatives", "options-spread"),
    ("payoff", "portfolio", "options-payoff"),
    ("risk", "derivatives", "options-risk"),
    ("scenario", "research", "options-scenario"),
    ("assumptions", "research", "options-assumptions"),
)

_FAIL_CLOSED_MARKERS = (
    "delayed",
    "fallback",
    "proxy",
    "demo",
    "fixture",
    "synthetic",
    "manual_review",
    "observe_only",
    "observation_only",
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


def _contains_any(values: Iterable[Any], markers: Iterable[str]) -> bool:
    lowered = " ".join(_lower_text(value) for value in values if value is not None)
    return any(marker in lowered for marker in markers)


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


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


def _extract_contracts(chain: Mapping[str, Any]) -> list[dict[str, Any]]:
    contracts = chain.get("contracts")
    if isinstance(contracts, list):
        return [_mapping(item) for item in contracts]
    merged: list[dict[str, Any]] = []
    for side in ("calls", "puts"):
        merged.extend(_mapping(item) for item in _sequence(chain.get(side)))
    return merged


def _source_context(
    *,
    summary: Mapping[str, Any],
    chain: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, str]:
    underlying = _mapping(summary.get("underlying"))
    freshness = _first_text(
        _mapping(decision.get("freshness")).get("freshness"),
        underlying.get("freshness"),
        summary.get("freshness"),
        chain.get("freshness"),
        _mapping(decision.get("dataQuality")).get("sourceType"),
    )
    source_id = _first_text(
        chain.get("sourceId"),
        chain.get("source"),
        underlying.get("sourceId"),
        underlying.get("source"),
        summary.get("sourceId"),
        summary.get("source"),
        _mapping(decision.get("freshness")).get("source"),
    )
    source_label = _first_text(
        chain.get("sourceLabel"),
        summary.get("sourceLabel"),
        underlying.get("sourceLabel"),
        chain.get("providerName"),
        summary.get("providerName"),
        source_id,
    )
    return {
        "source_id": source_id,
        "source_label": source_label,
        "freshness": freshness or "unknown",
    }


def _source_tier(source_texts: Iterable[Any]) -> str:
    if _contains_any(source_texts, ("proxy",)):
        return "public_proxy"
    if _contains_any(source_texts, ("fallback",)):
        return "fallback_static"
    if _contains_any(source_texts, ("fixture", "demo", "synthetic")):
        return "synthetic_fixture"
    if _contains_any(source_texts, ("cached", "snapshot")):
        return "cache_snapshot"
    if _contains_any(source_texts, ("polygon", "tradier", "ibkr", "live", "authorized")):
        return "authorized_licensed_feed"
    return "official_public"


def _freshness_state(source_texts: Iterable[Any], explicit: str) -> str:
    if explicit:
        explicit_lower = explicit.lower()
        if "delay" in explicit_lower:
            return "delayed"
        if any(marker in explicit_lower for marker in ("fallback",)):
            return "fallback"
        if any(marker in explicit_lower for marker in ("fixture", "demo", "synthetic")):
            return "synthetic"
        if "cache" in explicit_lower:
            return "cached"
        if "stale" in explicit_lower:
            return "stale"
        if "fresh" in explicit_lower or "live" in explicit_lower:
            return "fresh"
    if _contains_any(source_texts, ("delay",)):
        return "delayed"
    if _contains_any(source_texts, ("fallback",)):
        return "fallback"
    if _contains_any(source_texts, ("fixture", "demo", "synthetic")):
        return "synthetic"
    if _contains_any(source_texts, ("cache", "snapshot")):
        return "cached"
    if _contains_any(source_texts, ("stale",)):
        return "stale"
    if _contains_any(source_texts, ("live", "fresh", "polygon", "tradier", "ibkr")):
        return "fresh"
    return "unknown"


def _base_signals(
    *,
    summary: Mapping[str, Any],
    chain: Mapping[str, Any],
    decision: Mapping[str, Any],
    scenario: Mapping[str, Any],
    assumptions: Mapping[str, Any],
) -> dict[str, Any]:
    contracts = _extract_contracts(chain)
    data_quality = _mapping(decision.get("dataQuality"))
    liquidity = _mapping(decision.get("liquidity"))
    iv_greeks = _mapping(decision.get("ivGreeks"))
    expected_move = _mapping(decision.get("expectedMove"))
    texts = _collect_texts(
        summary,
        chain,
        decision.get("decisionLabel"),
        data_quality,
        liquidity,
        iv_greeks,
        decision.get("gateDecision"),
        decision.get("gateIssues"),
        decision.get("failClosedReasonCodes"),
        expected_move,
    )
    context = _source_context(summary=summary, chain=chain, decision=decision)
    source_tier = _source_tier([context["source_id"], context["source_label"], *texts])
    freshness_state = _freshness_state([context["freshness"], *texts], context["freshness"])
    missing_chain = not contracts or "missing_contract_legs" in _sequence(data_quality.get("blockingReasons"))
    missing_iv = any(contract.get("impliedVolatility") is None for contract in contracts) or "missing_iv" in _sequence(
        iv_greeks.get("warnings")
    )
    missing_greeks = any(not _mapping(contract.get("greeks")) for contract in contracts) or "missing_greeks" in _sequence(
        iv_greeks.get("warnings")
    )
    spread_pct = liquidity.get("spreadPct")
    if spread_pct is None:
        spreads = [item.get("spreadPct") for item in contracts if item.get("spreadPct") is not None]
        spread_pct = max(spreads) if spreads else None
    wide_spread = spread_pct is not None and float(spread_pct) > 25
    manual_review = any(_lower_text(_mapping(issue).get("status")) == "manual_review" for issue in _sequence(decision.get("gateIssues")))
    observe_only = (
        freshness_state in {"delayed", "fallback", "synthetic", "stale", "unknown"}
        or source_tier in {"proxy", "fallback", "fixture", "unknown"}
        or data_quality.get("dataQualityTier") in {"delayed_usable", "synthetic_demo_only", "insufficient"}
        or _contains_any(texts, _FAIL_CLOSED_MARKERS)
    )
    return {
        "context": context,
        "source_tier": source_tier,
        "freshness_state": freshness_state,
        "missing_chain": missing_chain,
        "missing_iv_or_greeks": missing_iv or missing_greeks,
        "wide_spread_manual_review": wide_spread or manual_review,
        "observe_only": observe_only,
        "has_payoff": bool(_sequence(scenario.get("rows")) or _sequence(scenario.get("payoffRows"))),
        "has_assumptions": bool(assumptions or _mapping(decision.get("scenarioAssumptions"))),
        "has_expected_move": _lower_text(expected_move.get("expectedMoveSource")) not in {"", "unavailable"},
    }


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
    debug_ref = f"source-provenance:{debug_suffix}"

    if not source_id or not source_label:
        return build_unknown_source_provenance(evidence_domain=evidence_domain, debug_ref=debug_ref)

    limitations: list[str] = []
    next_evidence_needed: list[str] = []

    if domain_name == "underlyingPrice" and freshness_state == "unknown":
        limitations.append("underlying_price_freshness_unknown")
        next_evidence_needed.append("fresh_underlying_price")
    if domain_name == "optionsChain" and _bool(signals.get("missing_chain")):
        limitations.append("missing_options_chain")
        next_evidence_needed.append("authorized_options_chain")
    if domain_name == "ivGreeks" and _bool(signals.get("missing_iv_or_greeks")):
        limitations.append("missing_iv_or_greeks")
        next_evidence_needed.append("authorized_iv_greeks")
    if domain_name == "spread" and _bool(signals.get("wide_spread_manual_review")):
        limitations.append("wide_spread_manual_review")
        next_evidence_needed.append("narrow_spread_decision_grade_quote")
    if domain_name == "liquidity" and _bool(signals.get("wide_spread_manual_review")):
        limitations.append("manual_review_liquidity")
        next_evidence_needed.append("decision_grade_liquidity")
    if domain_name == "payoff" and not _bool(signals.get("has_payoff")):
        limitations.append("missing_payoff_scenario")
        next_evidence_needed.append("scenario_payoff_grid")
    if domain_name == "risk" and not _bool(signals.get("has_expected_move")):
        limitations.append("risk_context_partial")
        next_evidence_needed.append("expected_move_evidence")
    if domain_name == "scenario":
        limitations.append("scenario_output_not_runtime_integrated")
        next_evidence_needed.append("runtime_sidecar_adoption_review")
    if domain_name == "assumptions":
        if not _bool(signals.get("has_assumptions")):
            limitations.append("scenario_assumptions_missing")
            next_evidence_needed.append("scenario_assumptions")
        else:
            limitations.append("scenario_assumptions_user_supplied")
            next_evidence_needed.append("assumption_validation_context")

    if limitations:
        return build_source_provenance(
            source_id=source_id,
            source_label=source_label,
            evidence_domain=evidence_domain,
            authority_tier="observation_only",
            freshness_state="partial" if "wide_spread_manual_review" in limitations else freshness_state,
            source_tier=source_tier,
            fallback_or_proxy=source_tier in {"public_proxy", "fallback_static", "synthetic_fixture"},
            observation_only=True,
            score_contribution_allowed=False,
            limitations=limitations,
            next_evidence_needed=next_evidence_needed,
            debug_ref=debug_ref,
        )

    if _bool(signals.get("observe_only")):
        if source_tier in {"public_proxy", "fallback_static", "synthetic_fixture"} or freshness_state in {
            "fallback",
            "delayed",
            "synthetic",
        }:
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


def build_options_source_provenance_sidecar(
    *,
    summary: Mapping[str, Any] | None = None,
    chain: Mapping[str, Any] | None = None,
    decision: Mapping[str, Any] | None = None,
    scenario: Mapping[str, Any] | None = None,
    assumptions: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic helper-only Options source provenance entries."""

    summary_map = _mapping(summary)
    chain_map = _mapping(chain)
    decision_map = _mapping(decision)
    scenario_map = _mapping(scenario)
    assumptions_map = _mapping(assumptions) or _mapping(decision_map.get("scenarioAssumptions"))
    signals = _base_signals(
        summary=summary_map,
        chain=chain_map,
        decision=decision_map,
        scenario=scenario_map,
        assumptions=assumptions_map,
    )
    return [
        _entry_for_domain(
            domain_name=domain_name,
            evidence_domain=evidence_domain,
            debug_suffix=debug_suffix,
            signals=signals,
        )
        for domain_name, evidence_domain, debug_suffix in _DOMAIN_SPECS
    ]


def summarize_options_source_provenance_sidecar(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return the bounded summary for the helper-only Options sidecar entries."""

    return summarize_source_provenance(entries)
