# -*- coding: utf-8 -*-
"""Internal read-only backend metrics snapshot normalization service."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


BACKEND_METRICS_PROVENANCE = {
    "data_origin": "repo_local",
    "source_class": "synthetic",
    "aggregation_scope": "process_local",
}
BACKEND_METRICS_NORMALIZATION = {
    "count_names_stable": True,
    "count_value_type": "non_negative_integer",
    "percentile_claims": False,
    "rate_claims": False,
    "sla_claims": False,
    "durable_time_series": False,
    "multi_process_aggregation": False,
}
BACKEND_METRICS_SANITIZATION_RULES = [
    "no_external_calls",
    "no_live_calls",
    "credential_values_omitted",
    "payload_content_removed",
    "production_paths_omitted",
    "bounded_counts_only",
]
BACKEND_METRICS_GROUP_COUNT_ORDER = {
    "provider_diagnostics": (
        "configured_provider_count",
        "missing_credential_count",
        "permission_denied_count",
        "timeout_count",
        "fallback_served_count",
        "stale_cache_count",
        "budget_skip_count",
    ),
    "market_cache_diagnostics": (
        "hit_count",
        "miss_count",
        "stale_served_count",
        "cold_fallback_count",
        "refresh_started_count",
        "refresh_completed_count",
        "refresh_failed_count",
    ),
    "backtest_diagnostics_readiness_exports": (
        "rule_run_count",
        "export_index_count",
        "execution_model_metadata_export_count",
        "oos_parameter_readiness_export_count",
        "regime_attribution_readiness_export_count",
        "robustness_evidence_export_count",
        "support_bundle_manifest_export_count",
    ),
    "release_gate_foundation_evidence_diagnostics": (
        "foundation_evidence_category_count",
        "accepted_evidence_count",
        "review_required_evidence_count",
        "missing_evidence_count",
        "operator_validator_ready_count",
    ),
}
BACKEND_METRICS_GROUP_COUNT_NAMES = {
    group_name: set(count_names)
    for group_name, count_names in BACKEND_METRICS_GROUP_COUNT_ORDER.items()
}
BACKEND_METRICS_GROUP_ORDER = tuple(BACKEND_METRICS_GROUP_COUNT_ORDER)
BACKEND_METRICS_DEFERRED_STACK_FIELDS = (
    "open_telemetry",
    "prometheus",
    "grafana",
    "sentry",
    "exporters",
    "scrape_endpoints",
    "alerts",
    "durable_storage",
    "multi_process_aggregation",
)
_PROVENANCE_ALIASES = {
    "data_origin": {
        "repo": "repo_local",
        "repo_local": "repo_local",
        "repo-local": "repo_local",
        "repository_local": "repo_local",
    },
    "source_class": {
        "fixture": "synthetic",
        "synthetic": "synthetic",
        "synthetic_fixture": "synthetic",
    },
    "aggregation_scope": {
        "local_process": "process_local",
        "process_local": "process_local",
        "process-local": "process_local",
        "single_process": "process_local",
    },
}


class BackendMetricsSnapshotService:
    """Normalize caller-supplied diagnostics into a stable count-only snapshot."""

    def build_snapshot(self, payloads: Mapping[str, Any] | None = None) -> dict[str, Any]:
        raw_payloads = self._mapping(payloads)
        raw_groups = self._mapping(raw_payloads.get("groups")) or raw_payloads

        groups = {
            group_name: self._normalize_group(group_name, self._mapping(raw_groups.get(group_name)))
            for group_name in BACKEND_METRICS_GROUP_ORDER
        }
        return {
            "snapshot_meta": {
                "surface": "backend_metrics_snapshot",
                "read_only": True,
                **BACKEND_METRICS_PROVENANCE,
            },
            "normalization": dict(BACKEND_METRICS_NORMALIZATION),
            "groups": groups,
            "sanitization_rules": list(BACKEND_METRICS_SANITIZATION_RULES),
            "deferred_production_metrics_stack": {
                field: {"status": "deferred", "implemented": False}
                for field in BACKEND_METRICS_DEFERRED_STACK_FIELDS
            },
        }

    def _normalize_group(self, group_name: str, group_payload: Mapping[str, Any]) -> dict[str, Any]:
        counts_payload = self._mapping(group_payload.get("counts")) or group_payload
        count_names = BACKEND_METRICS_GROUP_COUNT_ORDER[group_name]
        counts = {
            count_name: self._normalize_count(counts_payload.get(count_name))
            for count_name in count_names
        }
        return {
            "provenance": self._normalize_provenance(group_payload.get("provenance")),
            "sources": self._normalize_sources(group_payload.get("sources")),
            "counts": counts,
        }

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        if isinstance(value, Mapping):
            return value
        return {}

    @staticmethod
    def _normalize_count(value: Any) -> int:
        if value is None or isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return max(0, value)
        if isinstance(value, float):
            if value.is_integer():
                return max(0, int(value))
            return 0
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit():
                return int(text)
        return 0

    @staticmethod
    def _normalize_sources(value: Any) -> list[str]:
        raw_items: Sequence[Any]
        if isinstance(value, str):
            raw_items = [value]
        elif isinstance(value, Sequence):
            raw_items = value
        else:
            raw_items = []

        normalized: list[str] = []
        for item in raw_items:
            text = str(item or "").strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized or ["unavailable"]

    def _normalize_provenance(self, value: Any) -> dict[str, str]:
        raw = self._mapping(value)
        normalized = dict(BACKEND_METRICS_PROVENANCE)
        for key, default in BACKEND_METRICS_PROVENANCE.items():
            candidate = str(raw.get(key, "") or "").strip().lower().replace(" ", "_")
            normalized[key] = _PROVENANCE_ALIASES.get(key, {}).get(candidate, default)
        return normalized
