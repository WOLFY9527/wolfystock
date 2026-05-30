# -*- coding: utf-8 -*-
"""Inert provider evidence snapshot normalization helper."""

from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping

from src.contracts.source_confidence import (
    coerce_source_confidence_contract,
    evaluate_market_intelligence_trust_from_sources,
)


FRESHNESS_ORDER = {
    "live": 0,
    "fresh": 1,
    "cached": 2,
    "delayed": 3,
    "stale": 4,
    "partial": 5,
    "fallback": 6,
    "synthetic": 7,
    "mock": 7,
    "error": 8,
    "unavailable": 9,
    "unknown": 10,
}
PROXY_SOURCE_TYPES = {"public_proxy", "proxy_public", "unofficial_proxy"}
PROXY_SOURCES = {"yfinance_proxy", "yahoo", "yfinance"}


def build_provider_evidence_snapshot(
    indicator_evidence: Iterable[Mapping[str, Any]] | Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Normalize evidence-like input into a diagnostic-only snapshot."""

    normalized_items = [_normalize_indicator_evidence(item) for item in indicator_evidence if isinstance(item, Mapping)]
    aggregate = _aggregate_snapshot(normalized_items)
    aggregate["indicatorEvidence"] = normalized_items
    return aggregate


def _normalize_indicator_evidence(item: Mapping[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(dict(item))
    inputs = [copy.deepcopy(entry) for entry in payload.get("inputs", []) if isinstance(entry, dict)]
    missing_inputs = _string_list(payload.get("missingInputs"))
    warnings = _dedupe(_string_list(payload.get("warnings")))

    proxy_count = _int_value(payload.get("proxyInputCount"))
    if proxy_count is None:
        proxy_count = sum(1 for entry in inputs if _input_is_proxy(entry))

    fallback_count = _int_value(payload.get("fallbackInputCount"))
    if fallback_count is None:
        fallback_count = sum(1 for entry in inputs if _bool(entry.get("isFallback")))

    stale_count = _int_value(payload.get("staleInputCount"))
    if stale_count is None:
        stale_count = sum(1 for entry in inputs if _bool(entry.get("isStale")))

    partial_count = _int_value(payload.get("partialInputCount"))
    if partial_count is None:
        partial_count = sum(1 for entry in inputs if _bool(entry.get("isPartial")))
        if partial_count == 0 and _is_partial(payload):
            partial_count = 1

    synthetic_count = _int_value(payload.get("syntheticInputCount"))
    if synthetic_count is None:
        synthetic_count = sum(1 for entry in inputs if _input_is_synthetic(entry))

    unavailable_count = _int_value(payload.get("unavailableInputCount"))
    if unavailable_count is None:
        unavailable_count = sum(1 for entry in inputs if _input_is_unavailable(entry))

    missing_count = _int_value(payload.get("missingInputCount"))
    if missing_count is None:
        missing_count = len(missing_inputs) if missing_inputs else unavailable_count

    return {
        "key": _text(payload.get("key")),
        "label": _text(payload.get("label")),
        "status": _text(payload.get("status")) or "unavailable",
        "freshness": _text(payload.get("freshness")) or "unavailable",
        "asOf": payload.get("asOf"),
        "source": payload.get("source"),
        "sourceLabel": payload.get("sourceLabel"),
        "diagnosticOnly": True,
        "observationOnly": True,
        "authorityGrant": False,
        "decisionGrade": False,
        "scoreContributionAllowed": bool(payload.get("scoreContributionAllowed")),
        "requiredRealSourceForScore": bool(payload.get("requiredRealSourceForScore")),
        "proxyOnly": bool(payload.get("proxyOnly")),
        "coverageObservationOnly": bool(payload.get("coverageObservationOnly")),
        "degradationReason": _optional_text(payload.get("degradationReason")),
        "capReason": _optional_text(payload.get("capReason")),
        "proxyInputCount": proxy_count,
        "fallbackInputCount": fallback_count,
        "staleInputCount": stale_count,
        "partialInputCount": partial_count,
        "syntheticInputCount": synthetic_count,
        "unavailableInputCount": unavailable_count,
        "missingInputCount": missing_count,
        "missingInputs": missing_inputs,
        "inputs": inputs,
        "warnings": warnings,
    }


def _aggregate_snapshot(indicator_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    inputs = [copy.deepcopy(entry) for item in indicator_evidence for entry in item["inputs"] if isinstance(entry, dict)]
    indicator_count = len(indicator_evidence)
    available_indicator_count = sum(1 for item in indicator_evidence if item["status"] != "unavailable")
    coverage = round(available_indicator_count / indicator_count, 2) if indicator_count else 0.0

    summary_sources = inputs or [
        {
            "source": item.get("source"),
            "sourceLabel": item.get("sourceLabel"),
            "asOf": item.get("asOf"),
            "freshness": item.get("freshness"),
            "isFallback": item.get("fallbackInputCount", 0) > 0,
            "isStale": item.get("staleInputCount", 0) > 0,
            "isPartial": item.get("partialInputCount", 0) > 0,
            "isSynthetic": item.get("syntheticInputCount", 0) > 0,
            "isUnavailable": item.get("unavailableInputCount", 0) > 0 or item.get("status") == "unavailable",
            "confidenceWeight": 0.0,
            "coverage": 0.0 if item.get("status") == "unavailable" else 1.0,
        }
        for item in indicator_evidence
    ]
    freshest = _weakest_freshness([_text(item.get("freshness")) for item in indicator_evidence] or ["unavailable"])
    source = _join_unique((item.get("source") for item in summary_sources))
    source_label = _join_unique((item.get("sourceLabel") for item in summary_sources), default="未接入")
    as_of = _max_text(item.get("asOf") for item in summary_sources)

    confidence_values = [_bounded_float(item.get("confidenceWeight")) for item in summary_sources if item.get("confidenceWeight") is not None]
    confidence_weight = round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else 0.0

    fallback_count = sum(int(item["fallbackInputCount"]) for item in indicator_evidence)
    stale_count = sum(int(item["staleInputCount"]) for item in indicator_evidence)
    partial_count = sum(int(item["partialInputCount"]) for item in indicator_evidence)
    synthetic_count = sum(int(item["syntheticInputCount"]) for item in indicator_evidence)
    unavailable_count = sum(int(item["unavailableInputCount"]) for item in indicator_evidence)
    missing_count = sum(int(item["missingInputCount"]) for item in indicator_evidence)

    contract = coerce_source_confidence_contract(
        {
            "source": source,
            "sourceLabel": source_label,
            "asOf": as_of,
            "freshness": freshest,
            "isFallback": fallback_count > 0,
            "isStale": stale_count > 0,
            "isPartial": partial_count > 0,
            "isSynthetic": synthetic_count > 0,
            "isUnavailable": unavailable_count > 0 or indicator_count == 0,
            "confidenceWeight": confidence_weight,
            "coverage": coverage,
        }
    ).to_dict()
    source_confidence = evaluate_market_intelligence_trust_from_sources(
        summary_sources,
        coverage=contract["coverage"],
        degradation_reasons=_aggregate_degradation_reasons(indicator_evidence),
    )

    return {
        "diagnosticOnly": True,
        "observationOnly": True,
        "authorityGrant": False,
        "decisionGrade": False,
        "externalProviderCalls": False,
        "providerRuntimeChanged": False,
        "marketCacheMutation": False,
        "indicatorCount": indicator_count,
        "proxyInputCount": sum(int(item["proxyInputCount"]) for item in indicator_evidence),
        "fallbackInputCount": fallback_count,
        "staleInputCount": stale_count,
        "partialInputCount": partial_count,
        "syntheticInputCount": synthetic_count,
        "unavailableInputCount": unavailable_count,
        "missingInputCount": missing_count,
        "source": contract["source"] or "unavailable",
        "sourceLabel": contract["sourceLabel"] or "未接入",
        "asOf": contract["asOf"],
        "freshness": contract["freshness"],
        "isFallback": bool(contract["isFallback"]),
        "isStale": bool(contract["isStale"]),
        "isPartial": bool(contract["isPartial"]),
        "isSynthetic": bool(contract["isSynthetic"]),
        "isUnavailable": bool(contract["isUnavailable"]),
        "coverage": contract["coverage"],
        "confidenceWeight": contract["confidenceWeight"],
        "degradationReason": contract["degradationReason"],
        "capReason": contract["capReason"],
        "missingInputs": _dedupe(name for item in indicator_evidence for name in item["missingInputs"]),
        "warnings": _dedupe(code for item in indicator_evidence for code in item["warnings"]),
        "sourceConfidence": source_confidence,
    }


def _aggregate_degradation_reasons(indicator_evidence: list[dict[str, Any]]) -> list[str]:
    return _dedupe(
        code
        for item in indicator_evidence
        for code in [
            item.get("degradationReason"),
            item.get("capReason"),
            *item.get("warnings", []),
        ]
        if _optional_text(code)
    )


def _input_is_proxy(item: Mapping[str, Any]) -> bool:
    source_type = _text(item.get("sourceType")).lower()
    source = _text(item.get("source")).lower()
    return source_type in PROXY_SOURCE_TYPES or source in PROXY_SOURCES


def _input_is_synthetic(item: Mapping[str, Any]) -> bool:
    source_type = _text(item.get("sourceType")).lower()
    freshness = _text(item.get("freshness")).lower()
    return bool(item.get("isSynthetic")) or freshness in {"synthetic", "mock"} or source_type == "synthetic_fixture"


def _input_is_unavailable(item: Mapping[str, Any]) -> bool:
    freshness = _text(item.get("freshness")).lower()
    return _bool(item.get("isUnavailable")) or freshness in {"unavailable", "error"}


def _is_partial(item: Mapping[str, Any]) -> bool:
    freshness = _text(item.get("freshness")).lower()
    return _bool(item.get("isPartial")) or freshness == "partial" or _text(item.get("status")).lower() == "partial"


def _weakest_freshness(values: Iterable[str]) -> str:
    normalized = [_text(value).lower() or "unknown" for value in values]
    if not normalized:
        return "unavailable"
    return max(normalized, key=lambda value: FRESHNESS_ORDER.get(value, FRESHNESS_ORDER["unknown"]))


def _join_unique(values: Iterable[Any], *, default: str = "unavailable") -> str:
    unique = _dedupe(_optional_text(value) for value in values if _optional_text(value))
    if not unique:
        return default
    if len(unique) == 1:
        return unique[0]
    return "mixed"


def _max_text(values: Iterable[Any]) -> str | None:
    normalized = [_optional_text(value) for value in values if _optional_text(value)]
    return max(normalized) if normalized else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [text for text in (_optional_text(item) for item in value) if text]


def _dedupe(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _optional_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _bounded_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(1.0, number)), 2)


def _int_value(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


__all__ = ["build_provider_evidence_snapshot"]
