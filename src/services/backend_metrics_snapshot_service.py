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
_PROVIDER_OPERATIONS_SOURCES = (
    "market_provider_operations_payload",
    "provider_diagnostics_projection",
)
_MARKET_CACHE_EVENT_SUMMARY_SOURCES = ("market_cache_event_summary",)
_BACKTEST_SUPPORT_EXPORT_INDEX_SOURCES = (
    "backtest_support_export_index",
    "stored_readiness_exports",
)
_RELEASE_GATE_SUMMARY_SOURCES = (
    "release_gate_summary",
    "foundation_evidence_summary",
)
_BACKTEST_EXPORT_KEY_TO_COUNT_NAME = {
    "support_bundle_manifest_json": "support_bundle_manifest_export_count",
    "robustness_evidence_json": "robustness_evidence_export_count",
    "regime_attribution_readiness_json": "regime_attribution_readiness_export_count",
    "execution_model_metadata_json": "execution_model_metadata_export_count",
    "oos_parameter_readiness_json": "oos_parameter_readiness_export_count",
}
_RELEASE_GATE_ACCEPTED_STATUSES = {
    "foundation_evidence_present",
    "completed_foundation_evidence_only",
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

    def from_provider_operations_payload(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        raw_payload = self._mapping(payload)
        return self.build_snapshot(
            {
                "groups": {
                    "provider_diagnostics": self._provider_operations_group_payload(raw_payload),
                    "market_cache_diagnostics": self._market_cache_event_summary_group_payload(
                        raw_payload.get("marketCacheEventSummary")
                    ),
                }
            }
        )

    def from_market_cache_event_summary(self, summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self.build_snapshot(
            {
                "groups": {
                    "market_cache_diagnostics": self._market_cache_event_summary_group_payload(summary)
                }
            }
        )

    def from_backtest_support_export_index(self, index_payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self.build_snapshot(
            {
                "groups": {
                    "backtest_diagnostics_readiness_exports": self._backtest_support_export_index_group_payload(
                        index_payload
                    )
                }
            }
        )

    def from_release_gate_summary(self, summary_payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self.build_snapshot(
            {
                "groups": {
                    "release_gate_foundation_evidence_diagnostics": self._release_gate_summary_group_payload(
                        summary_payload
                    )
                }
            }
        )

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

    def _provider_operations_group_payload(self, payload: Any) -> dict[str, Any]:
        raw_payload = self._mapping(payload)
        summary = self._mapping(raw_payload.get("summary"))
        provider_diagnostics = self._mapping(self._mapping(raw_payload.get("metadata")).get("providerDiagnostics"))
        diagnostic_entries = self._mapping_values(provider_diagnostics)

        if not summary and not diagnostic_entries:
            return {}

        return self._group_payload(
            _PROVIDER_OPERATIONS_SOURCES,
            {
                "configured_provider_count": len(diagnostic_entries),
                "missing_credential_count": sum(
                    1
                    for entry in diagnostic_entries
                    if self._text(entry.get("credentialState")) == "missing"
                    or self._text(entry.get("status")) == "key_missing"
                ),
                "permission_denied_count": sum(
                    1
                    for entry in diagnostic_entries
                    if self._text(entry.get("status")) == "permission_denied"
                    or self._text(entry.get("breadthEntitlementState")) == "permission_denied"
                    or "permission" in self._text(entry.get("reasonCode"))
                ),
                "timeout_count": sum(
                    1
                    for entry in diagnostic_entries
                    if self._text(entry.get("status")) == "timeout"
                    or self._text(entry.get("reachabilityState")) == "timeout"
                    or "timeout" in self._text(entry.get("reasonCode"))
                ),
                "fallback_served_count": self._normalize_count(summary.get("fallbackCount")),
                "stale_cache_count": self._normalize_count(summary.get("staleCount")),
                "budget_skip_count": self._normalize_count(summary.get("budgetSkipCount"))
                or sum(
                    1
                    for entry in diagnostic_entries
                    if "budget" in self._text(entry.get("reasonCode"))
                    or self._text(entry.get("status")) == "budget_skipped"
                ),
            },
        )

    def _market_cache_event_summary_group_payload(self, summary: Any) -> dict[str, Any]:
        raw_summary = self._mapping(summary)
        totals = self._mapping(raw_summary.get("totals"))

        if not raw_summary and not totals:
            return {}

        return self._group_payload(
            _MARKET_CACHE_EVENT_SUMMARY_SOURCES,
            {
                "hit_count": totals.get("hits"),
                "miss_count": totals.get("misses"),
                "stale_served_count": totals.get("staleServed"),
                "cold_fallback_count": totals.get("coldFallbacks"),
                "refresh_started_count": totals.get("refreshStarted"),
                "refresh_completed_count": totals.get("refreshCompleted"),
                "refresh_failed_count": totals.get("refreshFailed"),
            },
        )

    def _backtest_support_export_index_group_payload(self, index_payload: Any) -> dict[str, Any]:
        raw_payload = self._mapping(index_payload)
        exports = self._mapping_items(raw_payload.get("exports"))

        if not raw_payload and not exports:
            return {}

        available_export_keys = {
            self._text(item.get("key"))
            for item in exports
            if self._is_enabled_flag(item.get("available"))
        }
        has_run = bool(self._normalize_count(raw_payload.get("run_id")) or exports or self._text(raw_payload.get("status")))
        counts = {
            "rule_run_count": 1 if has_run else 0,
            "export_index_count": 1 if exports or raw_payload else 0,
            "execution_model_metadata_export_count": 0,
            "oos_parameter_readiness_export_count": 0,
            "regime_attribution_readiness_export_count": 0,
            "robustness_evidence_export_count": 0,
            "support_bundle_manifest_export_count": 0,
        }
        for export_key, count_name in _BACKTEST_EXPORT_KEY_TO_COUNT_NAME.items():
            counts[count_name] = 1 if export_key in available_export_keys else 0
        return self._group_payload(_BACKTEST_SUPPORT_EXPORT_INDEX_SOURCES, counts)

    def _release_gate_summary_group_payload(self, summary_payload: Any) -> dict[str, Any]:
        raw_payload = self._mapping(summary_payload)
        completed_evidence = self._mapping_items(raw_payload.get("completedFoundationEvidence"))
        hard_blockers = self._mapping_items(raw_payload.get("hardBlockers"))

        if not raw_payload and not completed_evidence and not hard_blockers:
            return {}

        statuses = [self._text(item.get("status")) for item in completed_evidence]
        return self._group_payload(
            _RELEASE_GATE_SUMMARY_SOURCES,
            {
                "foundation_evidence_category_count": len(completed_evidence),
                "accepted_evidence_count": sum(
                    1 for status in statuses if status in _RELEASE_GATE_ACCEPTED_STATUSES
                ),
                "review_required_evidence_count": sum(
                    1
                    for status in statuses
                    if "review_required" in status or status == "review_support_available"
                ),
                "missing_evidence_count": len(hard_blockers),
                "operator_validator_ready_count": sum(
                    1
                    for item in completed_evidence
                    if self._text(item.get("status")).startswith("offline_validator_available")
                    or "validator" in self._text(item.get("id"))
                ),
            },
        )

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

    def _group_payload(self, sources: Sequence[str], counts: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "sources": list(sources),
            "counts": {
                count_name: self._normalize_count(count_value)
                for count_name, count_value in counts.items()
            },
        }

    @staticmethod
    def _mapping_items(value: Any) -> list[Mapping[str, Any]]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return []
        return [item for item in value if isinstance(item, Mapping)]

    @staticmethod
    def _mapping_values(value: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        return [item for item in value.values() if isinstance(item, Mapping)]

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _is_enabled_flag(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value == 1
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "available"}
        return False

    def _normalize_provenance(self, value: Any) -> dict[str, str]:
        raw = self._mapping(value)
        normalized = dict(BACKEND_METRICS_PROVENANCE)
        for key, default in BACKEND_METRICS_PROVENANCE.items():
            candidate = str(raw.get(key, "") or "").strip().lower().replace(" ", "_")
            normalized[key] = _PROVENANCE_ALIASES.get(key, {}).get(candidate, default)
        return normalized
