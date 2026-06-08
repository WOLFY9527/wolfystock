# -*- coding: utf-8 -*-
"""Observe-only readiness packet for Backtest + Factor Lab metadata."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


PACKET_KIND = "backtest_factor_lab_readiness_packet"
PACKET_VERSION = "backtest_factor_lab_readiness_v1"

_POSITIVE_VALUES = {
    "allowed",
    "available",
    "complete",
    "confirmed",
    "covered",
    "enabled",
    "explicit",
    "handled",
    "modeled",
    "modelled",
    "present",
    "ready",
    "supported",
    "true",
    "verified",
    "yes",
}
_NEGATIVE_VALUES = {
    "absent",
    "blocked",
    "deferred",
    "disabled",
    "false",
    "missing",
    "n",
    "no",
    "not_available",
    "not_modeled",
    "not_modelled",
    "not_present",
    "not_ready",
    "rejected",
    "unavailable",
    "unsupported",
}
_AMBIGUOUS_VALUES = {
    "",
    "ambiguous",
    "mixed",
    "n/a",
    "na",
    "none",
    "null",
    "partial",
    "unknown",
    "unknown_or_mixed",
}
_INPUT_SECTIONS = (
    "backtest_readiness",
    "factor_metrics_availability",
    "bridge_manifest",
    "data_lineage",
)
_DIMENSION_DEFINITIONS = (
    {
        "id": "pit_as_of",
        "priority": "P0",
        "label": "PIT and as-of coverage",
        "components": (
            {
                "id": "point_in_time_universe_membership",
                "label": "Point-in-time universe membership",
                "aliases": (
                    "point_in_time_universe_membership",
                    "pointInTimeUniverseMembership",
                    "pit_universe_membership",
                ),
            },
            {
                "id": "as_of_timestamp_policy",
                "label": "As-of timestamp policy",
                "aliases": (
                    "as_of_timestamp_policy",
                    "asOfTimestampPolicy",
                    "as_of",
                    "asOf",
                ),
            },
        ),
    },
    {
        "id": "survivorship_delisted",
        "priority": "P0",
        "label": "Survivorship and delisted-symbol coverage",
        "components": (
            {
                "id": "survivorship_bias_safe_universe_evidence",
                "label": "Survivorship-safe universe evidence",
                "aliases": (
                    "survivorship_bias_safe_universe_evidence",
                    "survivorshipBiasSafeUniverseEvidence",
                    "survivorship_bias_safe",
                ),
            },
            {
                "id": "delisting_inactive_symbol_handling",
                "label": "Delisted and inactive-symbol handling",
                "aliases": (
                    "delisting_inactive_symbol_handling",
                    "delistingInactiveSymbolHandling",
                    "delisted_symbol_handling",
                ),
            },
        ),
    },
    {
        "id": "corporate_actions",
        "priority": "P0",
        "label": "Corporate-action lineage",
        "components": (
            {
                "id": "corporate_action_adjusted_ohlc_lineage",
                "label": "Adjusted OHLC lineage",
                "aliases": (
                    "corporate_action_adjusted_ohlc_lineage",
                    "split_dividend_corporate_action_adjusted_ohlc_lineage",
                    "corporateActionAdjustedOhlcLineage",
                    "splitDividendCorporateActionAdjustedOhlcLineage",
                ),
            },
        ),
    },
    {
        "id": "calendar_session_halt_constraints",
        "priority": "P0",
        "label": "Exchange calendar, session, and halt constraints",
        "components": (
            {
                "id": "exchange_calendar_session_alignment",
                "label": "Exchange calendar alignment",
                "aliases": (
                    "exchange_calendar_session_alignment",
                    "exchangeCalendarSessionAlignment",
                    "trading_calendar",
                ),
            },
            {
                "id": "session_constraints",
                "label": "Session constraints",
                "aliases": (
                    "session_constraints",
                    "sessionConstraints",
                    "half_day_policy",
                ),
            },
            {
                "id": "halt_constraints",
                "label": "Halt constraints",
                "aliases": (
                    "halt_constraints",
                    "haltConstraints",
                    "halt_handling",
                    "limit_up_down_handling",
                ),
            },
        ),
    },
    {
        "id": "transaction_cost_realism",
        "priority": "P0",
        "label": "Transaction-cost, slippage, and impact realism",
        "components": (
            {
                "id": "transaction_cost_model",
                "label": "Transaction-cost model",
                "aliases": (
                    "transaction_cost_model",
                    "transactionCostModel",
                    "cost_model",
                    "costModelState",
                ),
            },
            {
                "id": "slippage_model",
                "label": "Slippage model",
                "aliases": (
                    "slippage_model",
                    "slippageModel",
                ),
            },
            {
                "id": "market_impact_model",
                "label": "Market-impact model",
                "aliases": (
                    "market_impact_model",
                    "marketImpactModel",
                ),
            },
        ),
    },
    {
        "id": "portfolio_rebalance_model",
        "priority": "P0",
        "label": "Portfolio rebalance model",
        "components": (
            {
                "id": "portfolio_rebalance_model",
                "label": "Portfolio rebalance model",
                "aliases": (
                    "portfolio_rebalance_model",
                    "portfolioRebalanceModel",
                    "rebalance_model",
                ),
            },
        ),
    },
    {
        "id": "dataset_snapshot_version_source_authority",
        "priority": "P0",
        "label": "Dataset snapshot, version, and source authority",
        "components": (
            {
                "id": "dataset_snapshot",
                "label": "Dataset snapshot",
                "aliases": (
                    "dataset_snapshot",
                    "datasetSnapshot",
                    "historical_snapshot_reproducibility",
                ),
            },
            {
                "id": "dataset_version",
                "label": "Dataset version",
                "aliases": (
                    "dataset_version",
                    "datasetVersion",
                ),
            },
            {
                "id": "source_authority",
                "label": "Source authority",
                "aliases": (
                    "source_authority",
                    "sourceAuthority",
                    "vendor_source_provenance",
                    "vendorSourceProvenance",
                    "authority_status",
                ),
            },
        ),
    },
    {
        "id": "decile_returns",
        "priority": "P1",
        "label": "Decile return coverage",
        "components": (
            {
                "id": "decile_returns",
                "label": "Decile returns",
                "aliases": (
                    "decile_returns",
                    "decileReturns",
                    "quantile_returns",
                ),
            },
        ),
    },
    {
        "id": "panel_contract",
        "priority": "P1",
        "label": "Factor panel contract",
        "components": (
            {
                "id": "panel_contract",
                "label": "Panel contract",
                "aliases": (
                    "panel_contract",
                    "panelContract",
                    "factor_panel_contract",
                ),
            },
        ),
    },
    {
        "id": "forward_return_generation",
        "priority": "P1",
        "label": "Forward return generation",
        "components": (
            {
                "id": "forward_return_generation",
                "label": "Forward return generation",
                "aliases": (
                    "forward_return_generation",
                    "forwardReturnGeneration",
                    "forward_returns",
                ),
            },
        ),
    },
    {
        "id": "neutralization",
        "priority": "P1",
        "label": "Neutralization coverage",
        "components": (
            {
                "id": "neutralization",
                "label": "Neutralization",
                "aliases": (
                    "neutralization",
                    "factor_neutralization",
                    "neutralized",
                ),
            },
        ),
    },
    {
        "id": "factor_correlation",
        "priority": "P1",
        "label": "Factor correlation coverage",
        "components": (
            {
                "id": "factor_correlation",
                "label": "Factor correlation",
                "aliases": (
                    "factor_correlation",
                    "factorCorrelation",
                    "peer_correlation",
                ),
            },
        ),
    },
    {
        "id": "multi_factor_composition",
        "priority": "P1",
        "label": "Multi-factor composition",
        "components": (
            {
                "id": "multi_factor_composition",
                "label": "Multi-factor composition",
                "aliases": (
                    "multi_factor_composition",
                    "multiFactorComposition",
                    "factor_composition",
                ),
            },
        ),
    },
    {
        "id": "oos_walk_forward",
        "priority": "P1",
        "label": "Out-of-sample and walk-forward coverage",
        "components": (
            {
                "id": "oos_walk_forward",
                "label": "Out-of-sample and walk-forward",
                "aliases": (
                    "oos_walk_forward",
                    "oosWalkForward",
                    "walk_forward",
                    "walkForward",
                ),
            },
        ),
    },
    {
        "id": "parameter_stability",
        "priority": "P1",
        "label": "Parameter stability",
        "components": (
            {
                "id": "parameter_stability",
                "label": "Parameter stability",
                "aliases": (
                    "parameter_stability",
                    "parameterStability",
                    "stability",
                ),
            },
        ),
    },
)


def build_backtest_factor_lab_readiness_packet(
    *,
    backtest_readiness: Mapping[str, Any] | None = None,
    factor_metrics_availability: Mapping[str, Any] | None = None,
    bridge_manifest: Mapping[str, Any] | None = None,
    data_lineage: Mapping[str, Any] | None = None,
    missing_professional_prerequisites: Mapping[str, Any] | Sequence[Any] | str | None = None,
) -> dict[str, Any]:
    """Aggregate caller-supplied metadata into an observe-only readiness packet."""

    sections = {
        "backtest_readiness": _mapping(backtest_readiness),
        "factor_metrics_availability": _mapping(factor_metrics_availability),
        "bridge_manifest": _mapping(bridge_manifest),
        "data_lineage": _mapping(data_lineage),
    }
    records = _collect_records(sections)
    explicit_missing = _normalize_missing_prerequisites(missing_professional_prerequisites)

    dimensions = {"p0": [], "p1": []}
    blocking_dimension_ids: list[str] = []
    counts = {
        "p0": {"available": 0, "missing": 0, "ambiguous": 0},
        "p1": {"available": 0, "missing": 0, "ambiguous": 0},
    }
    for definition in _DIMENSION_DEFINITIONS:
        dimension = _build_dimension(definition, records=records, explicit_missing=explicit_missing)
        priority_key = definition["priority"].lower()
        dimensions[priority_key].append(dimension)
        counts[priority_key][dimension["state"]] += 1
        if not dimension["ready"]:
            blocking_dimension_ids.append(dimension["id"])

    professional_ready = not blocking_dimension_ids
    product_state = (
        "observe_only_prerequisites_present"
        if professional_ready
        else "observe_only_not_professional_ready"
    )
    return {
        "packetKind": PACKET_KIND,
        "packetVersion": PACKET_VERSION,
        "observeOnly": True,
        "professionalReady": professional_ready,
        "productState": product_state,
        "summary": _build_summary(
            professional_ready=professional_ready,
            counts=counts,
        ),
        "inputObservations": {
            "callerSuppliedSections": [
                section_name
                for section_name in _INPUT_SECTIONS
                if sections[section_name]
            ],
            "explicitMissingPrerequisites": sorted(explicit_missing),
            "recognizedRecordCount": len(records),
        },
        "dimensionCounts": counts,
        "blockingPriority": "none" if professional_ready else ("P0" if counts["p0"]["available"] != len(dimensions["p0"]) else "P1"),
        "blockingDimensionIds": blocking_dimension_ids,
        "dimensions": dimensions,
    }


def _build_dimension(
    definition: Mapping[str, Any],
    *,
    records: Sequence[dict[str, Any]],
    explicit_missing: set[str],
) -> dict[str, Any]:
    component_views = [
        _build_component(component, records=records, explicit_missing=explicit_missing, dimension_id=str(definition["id"]))
        for component in definition["components"]
    ]
    states = {item["state"] for item in component_views}
    if states == {"available"}:
        state = "available"
        ready = True
        missing_reason_codes: list[str] = []
        summary = f'{definition["label"]} is explicit in caller-supplied metadata.'
    elif "missing" in states:
        state = "missing"
        ready = False
        missing_reason_codes = [f'{definition["id"]}_missing_or_ambiguous']
        summary = f'{definition["label"]} remains missing in caller-supplied metadata.'
    else:
        state = "ambiguous"
        ready = False
        missing_reason_codes = [f'{definition["id"]}_missing_or_ambiguous']
        summary = f'{definition["label"]} remains missing or ambiguous in caller-supplied metadata.'

    dimension_missing_token = _normalize_text(definition["id"])
    if dimension_missing_token in explicit_missing:
        state = "missing"
        ready = False
        summary = f'{definition["label"]} is listed as missing by the caller.'
        missing_reason_codes = [f'{definition["id"]}_listed_missing']

    return {
        "id": definition["id"],
        "priority": definition["priority"],
        "label": definition["label"],
        "state": state,
        "ready": ready,
        "summary": summary,
        "missingReasonCodes": missing_reason_codes,
        "components": component_views,
    }


def _build_component(
    component: Mapping[str, Any],
    *,
    records: Sequence[dict[str, Any]],
    explicit_missing: set[str],
    dimension_id: str,
) -> dict[str, Any]:
    aliases = {_normalize_text(alias) for alias in component["aliases"]}
    component_token = _normalize_text(component["id"])
    if component_token in explicit_missing or aliases & explicit_missing:
        return {
            "id": component["id"],
            "label": component["label"],
            "state": "missing",
            "ready": False,
            "summary": f'{component["label"]} is listed as missing by the caller.',
            "missingReasonCodes": [f'{component["id"]}_listed_missing'],
            "evidencePaths": [],
            "sourceSections": [],
        }

    matched = [record for record in records if _record_matches_aliases(record, aliases)]
    evidence_paths = sorted({record["path"] for record in matched})
    source_sections = sorted({record["section"] for record in matched})
    statuses = [_classify_signal(record["value"]) for record in matched]
    positives = sum(status == "available" for status in statuses)
    negatives = sum(status == "missing" for status in statuses)
    ambiguities = sum(status == "ambiguous" for status in statuses)

    if positives and not negatives and not ambiguities:
        state = "available"
        ready = True
        summary = f'{component["label"]} is explicit in caller-supplied metadata.'
        missing_reason_codes: list[str] = []
    elif negatives and not positives and not ambiguities:
        state = "missing"
        ready = False
        summary = f'{component["label"]} remains missing in caller-supplied metadata.'
        missing_reason_codes = [f'{component["id"]}_missing']
    elif positives and (negatives or ambiguities):
        state = "ambiguous"
        ready = False
        summary = f'{component["label"]} has mixed caller-supplied evidence.'
        missing_reason_codes = [f'{component["id"]}_conflicting_evidence']
    elif ambiguities:
        state = "ambiguous"
        ready = False
        summary = f'{component["label"]} remains ambiguous in caller-supplied metadata.'
        missing_reason_codes = [f'{component["id"]}_ambiguous']
    else:
        state = "ambiguous"
        ready = False
        summary = f'{component["label"]} has no explicit caller-supplied evidence.'
        missing_reason_codes = [f'{component["id"]}_evidence_missing']

    return {
        "id": component["id"],
        "label": component["label"],
        "state": state,
        "ready": ready,
        "summary": summary,
        "missingReasonCodes": missing_reason_codes,
        "evidencePaths": evidence_paths,
        "sourceSections": source_sections,
        "dimensionId": dimension_id,
    }


def _build_summary(*, professional_ready: bool, counts: Mapping[str, Mapping[str, int]]) -> str:
    if professional_ready:
        return (
            "Observe-only readiness packet. All tracked professional research prerequisites "
            "are explicit in caller-supplied metadata."
        )
    return (
        "Observe-only readiness packet. Professional research prerequisites remain "
        f"incomplete across {counts['p0']['missing'] + counts['p0']['ambiguous']} P0 dimensions "
        f"and {counts['p1']['missing'] + counts['p1']['ambiguous']} P1 dimensions."
    )


def _mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _collect_records(sections: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for section_name, payload in sections.items():
        if not payload:
            continue
        _walk_records(section_name, payload, records, (section_name,))
    return records


def _walk_records(
    section_name: str,
    value: Any,
    records: list[dict[str, Any]],
    path_parts: tuple[str, ...],
) -> None:
    records.append(
        {
            "section": section_name,
            "path": ".".join(path_parts),
            "segments": tuple(_normalize_text(part) for part in path_parts),
            "value": value,
        }
    )
    if isinstance(value, Mapping):
        for key, child in value.items():
            _walk_records(section_name, child, records, (*path_parts, str(key)))
        return
    if _is_iterable(value):
        for index, child in enumerate(value):
            _walk_records(section_name, child, records, (*path_parts, str(index)))


def _record_matches_aliases(record: Mapping[str, Any], aliases: set[str]) -> bool:
    segments = record["segments"]
    return any(segment in aliases for segment in segments)


def _classify_signal(value: Any) -> str:
    if isinstance(value, Mapping):
        nested_statuses = []
        for key in (
            "ready",
            "available",
            "present",
            "supported",
            "verified",
            "complete",
            "state",
            "status",
            "availability",
        ):
            if key in value:
                nested_statuses.append(_classify_signal(value[key]))
        if not nested_statuses:
            return "ambiguous"
        if "missing" in nested_statuses and "available" in nested_statuses:
            return "ambiguous"
        if "missing" in nested_statuses:
            return "missing"
        if "available" in nested_statuses:
            return "available"
        return "ambiguous"
    if isinstance(value, bool):
        return "available" if value else "missing"
    if _is_iterable(value):
        nested_statuses = [_classify_signal(item) for item in value]
        if "available" in nested_statuses and ("missing" in nested_statuses or "ambiguous" in nested_statuses):
            return "ambiguous"
        if "missing" in nested_statuses:
            return "missing"
        if "available" in nested_statuses:
            return "available"
        return "ambiguous"

    normalized = _normalize_text(value)
    if normalized in _POSITIVE_VALUES:
        return "available"
    if normalized in _NEGATIVE_VALUES:
        return "missing"
    if normalized in _AMBIGUOUS_VALUES:
        return "ambiguous"
    return "ambiguous"


def _normalize_missing_prerequisites(
    value: Mapping[str, Any] | Sequence[Any] | str | None,
) -> set[str]:
    tokens: set[str] = set()
    if value is None:
        return tokens
    if isinstance(value, str):
        normalized = _normalize_text(value)
        if normalized:
            tokens.add(normalized)
        return tokens
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_token = _normalize_text(key)
            status = _classify_signal(item)
            if key_token and status in {"missing", "ambiguous"}:
                tokens.add(key_token)
            tokens.update(_normalize_missing_prerequisites(item))
        return tokens
    if _is_iterable(value):
        for item in value:
            tokens.update(_normalize_missing_prerequisites(item))
    return tokens


def _is_iterable(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray))


def _normalize_text(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())
