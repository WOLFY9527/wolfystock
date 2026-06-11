# -*- coding: utf-8 -*-
"""Guarded provider reliability runtime policy projection.

This module is intentionally evaluation-only. It does not call providers, mutate
storage, change provider order, alter fallback behavior, or touch MarketCache.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional

from src.utils.security import sanitize_message


CONTRACT_VERSION = "provider_reliability_runtime_v1"
DEFAULT_OFF_LABEL = "provider_reliability_runtime_pilot_default_off"
ROLLBACK_LABEL = "provider_reliability_runtime_pilot_disable_flag"

_BLOCKING_STATES = {
    "open",
    "degraded_cache_only",
    "disabled_by_operator",
    "provider_quota_depleted",
}
_QUOTA_REASON_BUCKETS = {"provider_429", "quota_policy_block"}
_OPERATOR_DISABLED_REASON_BUCKETS = {"provider_403", "auth_or_key_invalid", "operator_disabled"}
_SAFE_DIAGNOSTIC_REF_RE = re.compile(r"[^A-Za-z0-9_.:-]+")
_UNSAFE_DIAGNOSTIC_TEXT_RE = re.compile(
    r"(https?://|[?&][a-z0-9_.:-]+=|"
    r"\b(?:api[-_]?key|access[-_]?token|refresh[-_]?token|session[-_]?(?:id|token|cookie)?|"
    r"cookie|authorization|bearer|secret|password|credential|raw[-_]?(?:exception|payload|request|response)|"
    r"request[-_]?body|response[-_]?body|headers?|stack[-_]?trace|traceback)\b\s*[:=]|"
    r"\b(?:traceback|exception\(|providererror\())",
    re.IGNORECASE,
)


def build_provider_reliability_runtime_decision(
    *,
    provider: str,
    provider_category: Optional[str],
    route_family: Optional[str],
    circuit_state: Optional[Dict[str, Any]] = None,
    pilot_enabled: bool = False,
    fallback_evaluation_enabled: bool = False,
    pilot_provider_categories: Optional[set[str] | tuple[str, ...] | list[str]] = None,
    pilot_route_families: Optional[set[str] | tuple[str, ...] | list[str]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Return a policy-only runtime pilot decision from stored circuit state."""
    reference_time = now or datetime.now()
    state = dict(circuit_state or {})
    provider_label = _safe_label(provider, required=True) or "unknown"
    category = _safe_label(provider_category)
    route = _safe_label(route_family)
    circuit_state_name = _safe_label(state.get("state")) or "closed"
    reason_bucket = _safe_label(state.get("reason_bucket"))
    cooldown_until = _parse_datetime(state.get("cooldown_until"))
    cooldown_active = bool(cooldown_until and cooldown_until >= reference_time)
    sample_limit = max(0, int(state.get("half_open_sample_limit") or 0))
    sample_count = max(0, int(state.get("half_open_sample_count") or 0))
    sample_limit_reached = bool(sample_limit and sample_count >= sample_limit)
    half_open_sample_allowed = False

    if circuit_state_name == "closed":
        health_status = "healthy"
        degraded_status = "none"
        sufficiency_status = "sufficient"
        would_block_if_enforced = False
    elif circuit_state_name == "half_open":
        half_open_sample_allowed = not sample_limit_reached
        health_status = "half_open_sample_limited" if sample_limit_reached else "half_open_sampling"
        degraded_status = "fallback_advised" if sample_limit_reached else "recovery_sampling"
        sufficiency_status = "insufficient" if sample_limit_reached else "recovery_sampling"
        would_block_if_enforced = sample_limit_reached
    elif circuit_state_name == "open" and not cooldown_active and cooldown_until is not None:
        half_open_sample_allowed = True
        health_status = "half_open_ready"
        degraded_status = "recovery_sampling"
        sufficiency_status = "recovery_sampling"
        would_block_if_enforced = False
    else:
        health_status = _blocking_health_status(circuit_state_name, reason_bucket, cooldown_active=cooldown_active)
        degraded_status = _degraded_status(circuit_state_name, reason_bucket)
        sufficiency_status = "insufficient"
        would_block_if_enforced = circuit_state_name in _BLOCKING_STATES

    scope_matched = _scope_matches(
        provider_category=category,
        route_family=route,
        pilot_provider_categories=pilot_provider_categories,
        pilot_route_families=pilot_route_families,
    )
    pilot_would_block = bool(pilot_enabled and scope_matched and would_block_if_enforced)
    would_fallback_if_enforced = bool(would_block_if_enforced)
    pilot_would_fallback = bool(pilot_would_block and fallback_evaluation_enabled and would_fallback_if_enforced)

    if not pilot_enabled:
        decision_status = "disabled_by_default"
    elif not scope_matched:
        decision_status = "scope_not_enabled"
    elif pilot_would_block:
        decision_status = "pilot_would_block_if_promoted"
    elif half_open_sample_allowed:
        decision_status = "pilot_half_open_sample"
    else:
        decision_status = "pilot_allow"

    diagnostic_ref = _safe_diagnostic_ref(state.get("operator_action_ref"))
    return {
        "contract_version": CONTRACT_VERSION,
        "provider": provider_label,
        "provider_category": category,
        "route_family": route,
        "circuit_state": circuit_state_name,
        "health_status": health_status,
        "cooldown_active": cooldown_active,
        "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
        "half_open_sample_limit": sample_limit,
        "half_open_sample_count": sample_count,
        "half_open_sample_limit_reached": sample_limit_reached,
        "half_open_sample_allowed": half_open_sample_allowed,
        "fallback_evaluation_enabled": bool(fallback_evaluation_enabled),
        "would_fallback_if_enforced": would_fallback_if_enforced,
        "pilot_would_fallback": pilot_would_fallback,
        "sufficiency_status": sufficiency_status,
        "degraded_status": degraded_status,
        "pilot_enabled": bool(pilot_enabled),
        "scope_matched": scope_matched,
        "decision_status": decision_status,
        "production_enforcement_enabled": False,
        "live_enforcement": False,
        "would_block_call": False,
        "would_block_if_enforced": bool(would_block_if_enforced),
        "pilot_would_block": pilot_would_block,
        "enforcement_block_reason_code": reason_bucket if would_block_if_enforced else None,
        "would_change_provider_order": False,
        "would_change_fallback_behavior": False,
        "no_external_calls": True,
        "provider_behavior_changed": False,
        "market_cache_behavior_changed": False,
        "default_off_label": DEFAULT_OFF_LABEL,
        "rollback_label": ROLLBACK_LABEL,
        "diagnostic_ref": diagnostic_ref,
        "sanitized_diagnostics": {
            "provider": provider_label,
            "providerCategory": category,
            "routeFamily": route,
            "circuitState": circuit_state_name,
            "reasonBucket": reason_bucket,
            "healthStatus": health_status,
            "sufficiencyStatus": sufficiency_status,
            "degradedStatus": degraded_status,
            "cooldownActive": cooldown_active,
            "halfOpenSampleLimit": sample_limit,
            "halfOpenSampleCount": sample_count,
        },
    }


def _blocking_health_status(circuit_state_name: str, reason_bucket: Optional[str], *, cooldown_active: bool) -> str:
    if circuit_state_name == "provider_quota_depleted" or reason_bucket in _QUOTA_REASON_BUCKETS:
        return "quota_depleted"
    if circuit_state_name == "disabled_by_operator" or reason_bucket in _OPERATOR_DISABLED_REASON_BUCKETS:
        return "operator_disabled"
    if circuit_state_name == "degraded_cache_only":
        return "degraded"
    if cooldown_active:
        return "cooldown_active"
    return "degraded"


def _degraded_status(circuit_state_name: str, reason_bucket: Optional[str]) -> str:
    if circuit_state_name == "provider_quota_depleted" or reason_bucket in _QUOTA_REASON_BUCKETS:
        return "quota_depleted"
    if circuit_state_name == "disabled_by_operator" or reason_bucket in _OPERATOR_DISABLED_REASON_BUCKETS:
        return "operator_disabled"
    if circuit_state_name == "degraded_cache_only":
        return "cache_only_advised"
    if circuit_state_name in _BLOCKING_STATES:
        return "fallback_advised"
    return "none"


def _scope_matches(
    *,
    provider_category: Optional[str],
    route_family: Optional[str],
    pilot_provider_categories: Optional[set[str] | tuple[str, ...] | list[str]],
    pilot_route_families: Optional[set[str] | tuple[str, ...] | list[str]],
) -> bool:
    categories = {_safe_label(item) for item in pilot_provider_categories or []}
    routes = {_safe_label(item) for item in pilot_route_families or []}
    categories.discard(None)
    routes.discard(None)
    if not categories or not routes:
        return False
    return provider_category in categories and route_family in routes


def _safe_label(value: Any, *, required: bool = False) -> Optional[str]:
    text = sanitize_message(str(value or "").strip().lower())[:64]
    if required and not text:
        return "unknown"
    return text or None


def _safe_diagnostic_ref(value: Any) -> Optional[str]:
    raw_text = str(value or "").strip()
    if not raw_text:
        return None
    sanitized = sanitize_message(raw_text).strip()
    if _has_unsafe_diagnostic_text(raw_text) or _has_unsafe_diagnostic_text(sanitized):
        return "diagnostic_ref_redacted"
    ref = _SAFE_DIAGNOSTIC_REF_RE.sub("_", sanitized).strip("_.:-")[:128]
    return ref or "diagnostic_ref_redacted"


def _has_unsafe_diagnostic_text(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and _UNSAFE_DIAGNOSTIC_TEXT_RE.search(text))


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
