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
_FORBIDDEN_PUBLIC_TEXT_RE = re.compile(
    r"traceback|provider|reasoncode|trustlevel|sourcetype|fallback|exception|"
    r"https?://|api[_-]?key|secret|cookie|session|token",
    re.IGNORECASE,
)


def build_public_data_quality_summary(value: Mapping[str, Any] | None) -> PublicDataQualitySummary:
    payload = dict(value or {})
    status = _resolve_public_status(payload)
    updated_modules, affected_modules = _project_modules(payload, status=status)
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


def _resolve_public_status(payload: Mapping[str, Any]) -> PublicDataQualityStatus:
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
        return "ready"
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
) -> tuple[list[str], list[str]]:
    updated_modules = sanitize_public_module_names(_module_list_value(payload, "updatedModules", "updated_modules"))
    affected_modules = sanitize_public_module_names(_module_list_value(payload, "affectedModules", "affected_modules"))
    if updated_modules or affected_modules:
        return updated_modules, affected_modules

    modules = payload.get("modules")
    if not isinstance(modules, Mapping):
        return updated_modules, affected_modules

    projected_updated: list[str] = []
    projected_affected: list[str] = []
    for module_name, module_state in modules.items():
        public_labels = sanitize_public_module_names([module_name])
        if not public_labels:
            continue
        label = public_labels[0]
        module_status = _module_status_token(module_state)
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


def _module_status_token(value: Any) -> PublicDataQualityStatus:
    if isinstance(value, Mapping):
        return _resolve_public_status(value)
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


def _truthy(value: Any) -> bool:
    return value is True
