# -*- coding: utf-8 -*-
"""Provider-neutral earnings calendar readiness contract.

The contract is intentionally inert: it normalizes caller-supplied readiness
metadata and never calls providers, caches, or network transports.
"""

from __future__ import annotations

from typing import Any, Mapping


EARNINGS_CALENDAR_READINESS_CONTRACT_VERSION = "earnings_calendar_readiness_v1"

_COMPONENT_ORDER = (
    "nextEarningsDate",
    "lastReport",
    "epsEstimate",
    "reportedEps",
    "companyGuidance",
    "callTranscript",
    "eventFreshness",
)

_COMPONENT_LABELS = {
    "nextEarningsDate": "Next earnings date",
    "lastReport": "Last earnings report",
    "epsEstimate": "EPS estimate",
    "reportedEps": "Reported EPS",
    "companyGuidance": "Company guidance",
    "callTranscript": "Call transcript",
    "eventFreshness": "Event freshness",
}

_COMPONENT_VALUE_KEYS = {
    "nextEarningsDate": ("nextEarningsDate", "next_earnings_date"),
    "lastReport": ("lastReport", "last_report", "lastEarningsReport"),
    "epsEstimate": ("epsEstimate", "eps_estimate"),
    "reportedEps": ("reportedEps", "reported_eps", "reportedEPS"),
    "companyGuidance": ("companyGuidance", "company_guidance", "guidance"),
    "callTranscript": ("callTranscript", "call_transcript", "transcript"),
    "eventFreshness": ("eventFreshness", "event_freshness", "freshness"),
}

_ALLOWED_STATES = {
    "available",
    "missing",
    "stale",
    "not_configured",
    "insufficient_permissions",
}

_STATE_ALIASES = {
    "ready": "available",
    "live": "available",
    "fresh": "available",
    "ok": "available",
    "configured_missing": "missing",
    "unavailable": "missing",
    "unsupported": "not_configured",
    "not_supported": "not_configured",
    "unauthorized": "insufficient_permissions",
    "forbidden": "insufficient_permissions",
    "permission_denied": "insufficient_permissions",
    "entitlement_required": "insufficient_permissions",
}

_NEXT_ACTIONS = {
    "available": "Monitor calendar freshness before using earnings context.",
    "stale": "Refresh authorized earnings calendar evidence before showing event details.",
    "missing": "Add earnings calendar evidence before showing event details.",
    "not_configured": "Connect an authorized earnings calendar source before showing calendar fields.",
    "insufficient_permissions": "Confirm earnings data entitlement before showing restricted event fields.",
}


def build_earnings_calendar_readiness_v1(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a consumer-safe earnings calendar readiness projection."""

    payload = dict(value or {})
    component_states = _mapping(_first_present(payload.get("componentStates"), payload.get("component_states")))
    components = {
        component: _component_payload(component, payload, component_states)
        for component in _COMPONENT_ORDER
    }
    overall_state = _overall_state(components)
    return {
        "contractVersion": EARNINGS_CALENDAR_READINESS_CONTRACT_VERSION,
        "consumerSafe": True,
        "overallState": overall_state,
        "components": components,
        "blockingReasons": _blocking_reasons(components),
        "safeNextDataAction": _NEXT_ACTIONS[overall_state],
        "noAdviceBoundary": {
            "state": "no_advice",
            "label": "Research calendar readiness only.",
        },
    }


def _component_payload(
    component: str,
    payload: Mapping[str, Any],
    component_states: Mapping[str, Any],
) -> dict[str, Any]:
    state = _normalize_state(
        _first_present(
            component_states.get(component),
            component_states.get(_snake_case(component)),
            _mapping(payload.get(component)).get("state"),
            _mapping(payload.get(_snake_case(component))).get("state"),
            payload.get(f"{component}State"),
            payload.get(f"{_snake_case(component)}_state"),
        )
    )
    return {
        "state": state,
        "label": _COMPONENT_LABELS[component],
        "supported": state != "not_configured",
        "valueAvailable": bool(state == "available" and _has_any_value(payload, _COMPONENT_VALUE_KEYS[component])),
    }


def _normalize_state(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return "not_configured"
    normalized = _STATE_ALIASES.get(normalized, normalized)
    if normalized in _ALLOWED_STATES:
        return normalized
    return "not_configured"


def _overall_state(components: Mapping[str, Mapping[str, Any]]) -> str:
    states = [str(component.get("state") or "not_configured") for component in components.values()]
    if states and all(state == "available" for state in states):
        return "available"
    for state in ("insufficient_permissions", "stale", "missing", "not_configured"):
        if state in states:
            return state
    return "missing"


def _blocking_reasons(components: Mapping[str, Mapping[str, Any]]) -> list[str]:
    reasons: list[str] = []
    state_reasons = {
        "not_configured": "earnings_calendar_source_not_configured",
        "missing": "earnings_calendar_evidence_missing",
        "stale": "stale_event_readiness",
        "insufficient_permissions": "insufficient_permissions",
    }
    for component_key, component in components.items():
        state = str(component.get("state") or "")
        reason = state_reasons.get(state)
        if reason:
            _append_unique(reasons, reason)
            _append_unique(reasons, f"{_snake_case(component_key)}_{state}")
    return reasons


def _has_any_value(payload: Mapping[str, Any], keys: tuple[str, ...]) -> bool:
    for key in keys:
        value = payload.get(key)
        if value not in (None, "", [], {}):
            return True
        nested = _mapping(value)
        if nested.get("value") not in (None, "", [], {}):
            return True
    return False


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _snake_case(value: str) -> str:
    chars: list[str] = []
    for char in value:
        if char.isupper() and chars:
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


__all__ = [
    "EARNINGS_CALENDAR_READINESS_CONTRACT_VERSION",
    "build_earnings_calendar_readiness_v1",
]
