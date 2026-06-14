# -*- coding: utf-8 -*-
"""Project backend data-quality signals into a public-facing calm summary."""

from __future__ import annotations

import re
from typing import Any, Mapping

from api.v1.schemas.public_data_quality import (
    PUBLIC_DATA_QUALITY_LABELS,
    PUBLIC_DATA_QUALITY_MESSAGES,
    PUBLIC_DATA_QUALITY_NO_ADVICE_DISCLOSURE,
    PublicDataQualityStatus,
    PublicDataQualitySummary,
    sanitize_public_module_names,
)

_READY_STATUSES = {"available", "complete", "completed", "fresh", "live", "ready", "updated"}
_PARTIAL_STATUSES = {"degraded", "limited", "partial"}
_DELAYED_STATUSES = {"delayed", "stale"}
_CACHED_STATUSES = {"cache_snapshot", "cached", "fallback", "local", "local_historical"}
_NO_EVIDENCE_STATUSES = {"insufficient", "missing", "no_data", "no_evidence", "unknown"}
_UNAVAILABLE_STATUSES = {"error", "failed", "mock", "provider_down", "provider_error", "synthetic", "unavailable"}
_SAFE_RESEARCH_STATUSES = {"ready", "partial", "delayed", "cached"}
_PUBLIC_MODULE_STATE_KEYS = ("publicModuleStates", "public_module_states", "moduleStates", "module_states")
_PUBLIC_MODULE_NAME_KEYS = ("module", "moduleName", "module_name", "name", "surface", "surfaceId", "surface_id")
_CONSERVATIVE_STATUS_ORDER: tuple[PublicDataQualityStatus, ...] = (
    "unavailable",
    "no_evidence",
    "partial",
    "delayed",
    "cached",
    "ready",
)
_FORBIDDEN_PUBLIC_TEXT_RE = re.compile(
    r"traceback|provider|reasoncode|trustlevel|sourcetype|fallback|exception|"
    r"https?://|api[_-]?key|secret|cookie|session|token",
    re.IGNORECASE,
)


def build_public_data_quality_summary(value: Mapping[str, Any] | None) -> PublicDataQualitySummary:
    payload = dict(value or {})
    module_states = _collect_public_module_states(payload)
    status = _resolve_public_status(payload, module_states=module_states)
    updated_modules, affected_modules = _project_modules(payload, status=status, module_states=module_states)
    return PublicDataQualitySummary(
        status=status,
        label=PUBLIC_DATA_QUALITY_LABELS[status],
        suitableForResearchObservation=status in _SAFE_RESEARCH_STATUSES,
        asOf=_safe_public_timestamp(payload),
        updatedModules=updated_modules,
        affectedModules=[] if status == "ready" else affected_modules,
        message=PUBLIC_DATA_QUALITY_MESSAGES[status],
        noAdviceDisclosure=PUBLIC_DATA_QUALITY_NO_ADVICE_DISCLOSURE,
    )


def _resolve_public_status(
    payload: Mapping[str, Any],
    *,
    module_states: tuple[tuple[str, PublicDataQualityStatus], ...] = (),
) -> PublicDataQualityStatus:
    explicit_status = _resolve_explicit_public_status(payload, default_ready=not module_states)
    aggregated_status = _aggregate_module_state_status(module_states)
    combined = tuple(status for status in (explicit_status, aggregated_status) if status is not None)
    if not combined:
        return "ready"
    return _most_conservative_status(combined)


def _resolve_explicit_public_status(
    payload: Mapping[str, Any],
    *,
    default_ready: bool,
) -> PublicDataQualityStatus | None:
    freshness = _status_token(
        payload.get("status"),
        payload.get("state"),
        payload.get("freshness"),
        payload.get("freshnessState"),
        payload.get("qualityState"),
    )
    if _truthy(payload.get("isUnavailable")) or freshness in _UNAVAILABLE_STATUSES:
        return "unavailable"
    if _truthy(payload.get("isPartial")) or freshness in _PARTIAL_STATUSES:
        return "partial"
    if _truthy(payload.get("isStale")) or freshness in _DELAYED_STATUSES:
        return "delayed"
    if _truthy(payload.get("isFallback")) or freshness in _CACHED_STATUSES:
        return "cached"
    if freshness in _READY_STATUSES:
        return "ready"
    if freshness in _NO_EVIDENCE_STATUSES:
        return "no_evidence"
    if _module_list_value(payload, "affectedModules", "affected_modules"):
        return "partial"
    if not freshness:
        return "ready" if default_ready else None
    return "no_evidence"


def _status_token(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip().lower()
        if text:
            return text
    return ""


def _safe_public_timestamp(payload: Mapping[str, Any]) -> str | None:
    for key in ("asOf", "updatedAt", "updated_at", "lastUpdated", "last_updated"):
        text = str(payload.get(key) or "").strip()
        if text and not _FORBIDDEN_PUBLIC_TEXT_RE.search(text):
            return text
    return None


def _project_modules(
    payload: Mapping[str, Any],
    *,
    status: PublicDataQualityStatus,
    module_states: tuple[tuple[str, PublicDataQualityStatus], ...] = (),
) -> tuple[list[str], list[str]]:
    updated_modules = sanitize_public_module_names(_module_list_value(payload, "updatedModules", "updated_modules"))
    affected_modules = sanitize_public_module_names(_module_list_value(payload, "affectedModules", "affected_modules"))
    if updated_modules or affected_modules:
        return updated_modules, affected_modules

    if not module_states:
        return updated_modules, affected_modules

    projected_updated: list[str] = []
    projected_affected: list[str] = []
    for label, module_status in module_states:
        if module_status == "ready":
            projected_updated.append(label)
        else:
            projected_affected.append(label)
    if status == "ready":
        projected_affected = []
    return projected_updated, projected_affected


def _module_list_value(payload: Mapping[str, Any], *keys: str) -> list[object]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (list, tuple, set)):
            return list(value)
    return []


def _collect_public_module_states(payload: Mapping[str, Any]) -> tuple[tuple[str, PublicDataQualityStatus], ...]:
    module_states = _module_list_value(payload, *_PUBLIC_MODULE_STATE_KEYS)
    if module_states:
        return _normalize_public_module_states(module_states)

    modules = payload.get("modules")
    if not isinstance(modules, Mapping):
        return ()

    normalized_modules: list[dict[str, Any]] = []
    for module_name, module_state in modules.items():
        entry = dict(module_state) if isinstance(module_state, Mapping) else {"status": module_state}
        entry.setdefault("module", module_name)
        normalized_modules.append(entry)
    return _normalize_public_module_states(normalized_modules)


def _normalize_public_module_states(values: list[object]) -> tuple[tuple[str, PublicDataQualityStatus], ...]:
    module_status_by_label: dict[str, PublicDataQualityStatus] = {}
    for item in values:
        if not isinstance(item, Mapping):
            continue
        label = _safe_public_module_label(item)
        if not label:
            continue
        module_status = _module_status_token(item)
        current_status = module_status_by_label.get(label)
        if current_status is None:
            module_status_by_label[label] = module_status
            continue
        module_status_by_label[label] = _most_conservative_status((current_status, module_status))
    return tuple(module_status_by_label.items())


def _safe_public_module_label(value: Mapping[str, Any]) -> str | None:
    for key in _PUBLIC_MODULE_NAME_KEYS:
        candidate = value.get(key)
        public_labels = sanitize_public_module_names([candidate])
        if public_labels:
            return public_labels[0]
    return None


def _module_status_token(value: Any) -> PublicDataQualityStatus:
    if isinstance(value, Mapping):
        return _resolve_explicit_public_status(value, default_ready=False) or "no_evidence"
    token = _status_token(value)
    if token in _READY_STATUSES:
        return "ready"
    if token in _PARTIAL_STATUSES:
        return "partial"
    if token in _DELAYED_STATUSES:
        return "delayed"
    if token in _CACHED_STATUSES:
        return "cached"
    if token in _UNAVAILABLE_STATUSES:
        return "unavailable"
    return "no_evidence"


def _aggregate_module_state_status(
    module_states: tuple[tuple[str, PublicDataQualityStatus], ...],
) -> PublicDataQualityStatus | None:
    if not module_states:
        return None
    return _most_conservative_status(tuple(status for _, status in module_states))


def _most_conservative_status(statuses: tuple[PublicDataQualityStatus, ...]) -> PublicDataQualityStatus:
    for candidate in _CONSERVATIVE_STATUS_ORDER:
        if candidate in statuses:
            return candidate
    return "ready"


def _truthy(value: Any) -> bool:
    return value is True
