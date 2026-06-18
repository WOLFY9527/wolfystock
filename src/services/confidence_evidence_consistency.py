# -*- coding: utf-8 -*-
"""Pure confidence/evidence consistency projection helper.

The helper consumes already-built consumer payload fields. It does not import
provider, cache, storage, endpoint, or scoring-engine modules.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


CONFIDENCE_EVIDENCE_CONSISTENCY_VERSION = "confidence_evidence_consistency_v1"

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
_CRITICAL_EVIDENCE_TOKENS = (
    "benchmark",
    "peer",
    "quote",
    "price",
    "ohlcv",
    "daily history",
    "fundamental",
    "options",
    "gamma",
    "driver",
    "freshness",
    "source authority",
    "score contribution",
)
_BLOCKED_VALUES = {"blocked", "unavailable", "insufficient", "insufficient_evidence", "no_evidence"}
_DEGRADED_VALUES = {"degraded", "fallback", "partial", "synthetic", "proxy"}
_STALE_VALUES = {"stale", "delayed", "cached", "fallback", "unknown_freshness", "freshness_unknown"}


def project_confidence_evidence_state(
    *,
    payload: Mapping[str, Any] | None = None,
    raw_confidence_label: Any = None,
    raw_confidence_score: Any = None,
    evidence_completeness: Any = None,
    missing_inputs: Iterable[Any] | None = None,
    stale_inputs: Iterable[Any] | None = None,
    evidence_gaps: Iterable[Any] | None = None,
    degraded_inputs: Iterable[Any] | None = None,
    thesis_eligibility: Mapping[str, Any] | None = None,
    confidence_cap: Any = None,
    blocked_driver_states: Iterable[Any] | None = None,
    unavailable_driver_states: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Derive a consumer confidence state from confidence and evidence coverage."""

    source = dict(payload or {})
    nested = _nested_payload(source)
    raw_label = _confidence_label(
        _first_present(raw_confidence_label, source.get("confidenceLabel"), source.get("confidence")),
        _first_present(raw_confidence_score, source.get("confidenceScore"), source.get("score")),
    )
    explicit_cap = _confidence_cap_value(_first_present(confidence_cap, source.get("confidenceCap")))

    thesis = dict(thesis_eligibility or _mapping(source.get("thesisEligibility")))
    missing = _dedupe(
        [
            *_text_list(source.get("missingInputs")),
            *_missing_evidence_messages(source.get("missingEvidence")),
            *_text_list(nested.get("missingInputs")),
            *_text_list(missing_inputs),
        ]
    )
    gaps = _dedupe(
        [
            *_text_list(source.get("evidenceGaps")),
            *_text_list(nested.get("evidenceGaps")),
            *_text_list(evidence_gaps),
        ]
    )
    stale = _dedupe(
        [
            *_text_list(source.get("staleInputs")),
            *_text_list(nested.get("staleInputs")),
            *_text_list(stale_inputs),
        ]
    )
    degraded = _dedupe(
        [
            *_text_list(source.get("degradedInputs")),
            *_text_list(nested.get("degradedInputs")),
            *_text_list(degraded_inputs),
        ]
    )
    blocked_drivers = _dedupe(
        [
            *_text_list(source.get("blockedReasonCodes")),
            *_text_list(source.get("blockedDrivers")),
            *_text_list(blocked_driver_states),
            *_text_list(unavailable_driver_states),
        ]
    )

    reasons: list[str] = []
    cap_value = 100 if explicit_cap is None else explicit_cap

    thesis_blocked = _is_blocked(thesis.get("status"))
    if thesis_blocked:
        cap_value = min(cap_value, 35)
        _append_unique(reasons, "research thesis blocked")

    critical_missing = bool(missing) or _has_critical_gap(gaps)
    if critical_missing:
        cap_value = min(cap_value, 60)
        _append_unique(reasons, "critical evidence missing")

    freshness_constrained = bool(stale) or _freshness_constrained(source, nested)
    if freshness_constrained:
        cap_value = min(cap_value, 70)
        _append_unique(reasons, "freshness constrained")

    source_quality_limited = bool(degraded) or _source_quality_limited(source, nested, evidence_completeness)
    if source_quality_limited:
        cap_value = min(cap_value, 55)
        _append_unique(reasons, "source quality limited")

    if blocked_drivers:
        cap_value = min(cap_value, 35)
        _append_unique(reasons, "driver evidence unavailable")

    cap_value = max(0, min(100, int(cap_value)))
    cap_label = _label_from_cap(cap_value)
    consumer_confidence = _min_label(raw_label, cap_label)
    status = _state_status(
        thesis_blocked=thesis_blocked,
        critical_missing=critical_missing,
        blocked_drivers=bool(blocked_drivers),
        source_quality_limited=source_quality_limited,
        freshness_constrained=freshness_constrained,
    )

    return {
        "version": CONFIDENCE_EVIDENCE_CONSISTENCY_VERSION,
        "consumerConfidence": consumer_confidence,
        "confidenceCap": {
            "value": cap_value,
            "label": cap_label,
            "reasons": reasons,
            "policyVersion": CONFIDENCE_EVIDENCE_CONSISTENCY_VERSION,
        },
        "confidenceState": {
            "status": status,
            "label": consumer_confidence,
            "reasons": list(reasons),
            "freshnessConstrained": freshness_constrained,
            "sourceQualityLimited": source_quality_limited,
            "thesisBlocked": thesis_blocked,
        },
    }


def _nested_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    nested: dict[str, Any] = {}
    for key in ("peerCorrelationSnapshot", "dataQuality", "evidenceState", "readiness"):
        value = _mapping(payload.get(key))
        for nested_key in ("missingInputs", "staleInputs", "degradedInputs", "evidenceGaps"):
            if nested_key in value:
                nested.setdefault(nested_key, [])
                nested[nested_key].extend(_text_list(value.get(nested_key)))
    return nested


def _state_status(
    *,
    thesis_blocked: bool,
    critical_missing: bool,
    blocked_drivers: bool,
    source_quality_limited: bool,
    freshness_constrained: bool,
) -> str:
    if thesis_blocked or critical_missing or blocked_drivers:
        return "evidence limited"
    if source_quality_limited:
        return "source quality limited"
    if freshness_constrained:
        return "freshness constrained"
    return "ready"


def _confidence_label(label: Any, score: Any) -> str:
    text = _text(label).lower()
    if text in {"high", "higher", "strong"}:
        return "high"
    if text in {"medium", "moderate", "limited", "evidence_limited"}:
        return "medium"
    if text in {"low", "insufficient", "blocked", "unavailable"}:
        return "low"
    value = _number(score)
    if value is None:
        return "low"
    if value > 1:
        value = value / 100
    if value >= 0.75:
        return "high"
    if value >= 0.45:
        return "medium"
    return "low"


def _confidence_cap_value(value: Any) -> int | None:
    if isinstance(value, Mapping):
        number = _number(_first_present(value.get("value"), value.get("cap"), value.get("score")))
        if number is not None:
            return int(number if number > 1 else number * 100)
        return _cap_from_label(_text(value.get("label") or value.get("confidence")))
    number = _number(value)
    if number is not None:
        return int(number if number > 1 else number * 100)
    return _cap_from_label(_text(value))


def _cap_from_label(value: str) -> int | None:
    text = value.lower()
    if text == "high":
        return 100
    if text in {"medium", "moderate", "limited", "evidence_limited"}:
        return 60
    if text in {"low", "blocked", "insufficient", "unavailable"}:
        return 35
    return None


def _label_from_cap(value: int) -> str:
    if value >= 80:
        return "high"
    if value >= 60:
        return "medium"
    return "low"


def _min_label(left: str, right: str) -> str:
    return left if _CONFIDENCE_RANK[left] <= _CONFIDENCE_RANK[right] else right


def _is_blocked(value: Any) -> bool:
    return _text(value).lower() in _BLOCKED_VALUES


def _has_critical_gap(values: Iterable[str]) -> bool:
    for value in values:
        normalized = value.lower().replace("_", " ")
        if any(token in normalized for token in _CRITICAL_EVIDENCE_TOKENS):
            return True
    return False


def _freshness_constrained(payload: Mapping[str, Any], nested: Mapping[str, Any]) -> bool:
    values = [
        payload.get("freshness"),
        payload.get("freshnessState"),
        _mapping(payload.get("dataQuality")).get("freshness"),
        _mapping(payload.get("dataQuality")).get("freshnessState"),
        *nested.get("staleInputs", []),
    ]
    return any(_text(value).lower() in _STALE_VALUES or "stale" in _text(value).lower() for value in values)


def _source_quality_limited(payload: Mapping[str, Any], nested: Mapping[str, Any], evidence_completeness: Any) -> bool:
    values = [
        evidence_completeness,
        payload.get("sourceQuality"),
        payload.get("dataQualityState"),
        _mapping(payload.get("dataQuality")).get("status"),
        _mapping(payload.get("dataQuality")).get("state"),
        *nested.get("degradedInputs", []),
    ]
    normalized = [_text(value).lower() for value in values if _text(value)]
    return any(value in _DEGRADED_VALUES or value in _BLOCKED_VALUES for value in normalized)


def _missing_evidence_messages(value: Any) -> list[str]:
    messages: list[str] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, Mapping):
            messages.extend(_text_list([item.get("message"), item.get("kind")]))
        else:
            messages.extend(_text_list([item]))
    return messages


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, bytearray)):
        text = _text(value)
        return [text] if text else []
    if isinstance(value, Mapping):
        return _text_list([value.get("reason"), value.get("message"), value.get("status"), value.get("kind")])
    if isinstance(value, Iterable):
        result: list[str] = []
        for item in value:
            result.extend(_text_list(item))
        return result
    text = _text(value)
    return [text] if text else []


def _dedupe(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in result:
            result.append(text)
    return result


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "CONFIDENCE_EVIDENCE_CONSISTENCY_VERSION",
    "project_confidence_evidence_state",
]
