# -*- coding: utf-8 -*-
"""Metadata-only provider-fit advisor snapshots.

This service aggregates inert provider-fit metadata and dry-run probe contracts
into a stable internal advisor DTO. It must not import provider clients, read
environment variables or secrets, call networks, or alter runtime behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from src.services.provider_capability_matrix import (
    ProviderDryRunProbeContract,
    ProviderFitMetadataContract,
    get_provider_dry_run_probe_contract,
    get_provider_fit_metadata,
    list_provider_dry_run_probe_contracts,
    list_provider_fit_metadata,
)


@dataclass(frozen=True, slots=True)
class ProviderFitAdvisorEntry:
    provider_name: str
    provider_id: str
    provider_category: str
    source_tier: str
    trust_level: str
    freshness_expectation: str
    observation_only: bool
    score_contribution_allowed: bool
    paid_data_likely_required: bool
    key_required: bool
    enabled_by_default: bool
    live_tests_avoided: bool
    cache_required: bool
    background_refresh_recommended: bool
    network_call_executed: bool
    no_default_live_http_calls: bool
    best_use_cases: tuple[str, ...]
    rejected_for: tuple[str, ...]
    not_recommended_for: tuple[str, ...]
    missing_provider_reason: str | None
    degradation_reason: str | None
    adoption_status: str
    recommended_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerName": self.provider_name,
            "providerId": self.provider_id,
            "providerCategory": self.provider_category,
            "sourceTier": self.source_tier,
            "trustLevel": self.trust_level,
            "freshnessExpectation": self.freshness_expectation,
            "observationOnly": self.observation_only,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "paidDataLikelyRequired": self.paid_data_likely_required,
            "keyRequired": self.key_required,
            "enabledByDefault": self.enabled_by_default,
            "liveTestsAvoided": self.live_tests_avoided,
            "cacheRequired": self.cache_required,
            "backgroundRefreshRecommended": self.background_refresh_recommended,
            "networkCallExecuted": self.network_call_executed,
            "noDefaultLiveHttpCalls": self.no_default_live_http_calls,
            "bestUseCases": list(self.best_use_cases),
            "rejectedFor": list(self.rejected_for),
            "notRecommendedFor": list(self.not_recommended_for),
            "missingProviderReason": self.missing_provider_reason,
            "degradationReason": self.degradation_reason,
            "adoptionStatus": self.adoption_status,
            "recommendedNextStep": self.recommended_next_step,
        }


@dataclass(frozen=True, slots=True)
class ProviderFitAdvisorSnapshot:
    entries: tuple[ProviderFitAdvisorEntry, ...]
    advisory_only: bool = True
    runtime_behavior_changed: bool = False
    network_calls_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "advisoryOnly": self.advisory_only,
            "runtimeBehaviorChanged": self.runtime_behavior_changed,
            "networkCallsEnabled": self.network_calls_enabled,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def _derive_adoption_status(metadata: ProviderFitMetadataContract) -> str:
    if metadata.provider_id.endswith("_existing_baseline"):
        return "existing_baseline"
    if metadata.trust_level == "reference_only" or metadata.source_tier == "reference_wrapper":
        return "reference_only"
    if metadata.paid_data_likely_required or metadata.plan_dependent or metadata.key_required:
        return "paid_required"
    if metadata.source_tier in {"official_public", "exchange_public"}:
        return "candidate"
    return "inert_metadata_only"


def _derive_recommended_next_step(
    metadata: ProviderFitMetadataContract,
    adoption_status: str,
) -> str:
    if adoption_status == "existing_baseline":
        return "keep_as_fallback"
    if adoption_status == "reference_only":
        return "do_not_integrate_runtime"
    if adoption_status == "paid_required":
        return "require_license_review"
    if metadata.provider_category in {
        "filings_reference",
        "macro_reference",
        "macro_baseline",
        "reference_dataset_api",
    }:
        return "add_fixture_parser"
    if adoption_status == "candidate":
        return "add_health_probe"
    return "do_not_integrate_runtime"


def _build_advisor_entry(
    metadata: ProviderFitMetadataContract,
    probe: ProviderDryRunProbeContract,
) -> ProviderFitAdvisorEntry:
    if metadata.provider_id != probe.provider_id:
        raise ValueError(f"provider-fit advisor contract mismatch for {metadata.provider_id}")
    adoption_status = _derive_adoption_status(metadata)
    return ProviderFitAdvisorEntry(
        provider_name=metadata.provider_name,
        provider_id=metadata.provider_id,
        provider_category=metadata.provider_category,
        source_tier=metadata.source_tier,
        trust_level=metadata.trust_level,
        freshness_expectation=metadata.freshness_expectation,
        observation_only=metadata.observation_only and probe.observation_only,
        score_contribution_allowed=metadata.score_contribution_allowed or probe.score_contribution_allowed,
        paid_data_likely_required=metadata.paid_data_likely_required,
        key_required=metadata.key_required,
        enabled_by_default=metadata.enabled_by_default or probe.enabled_by_default,
        live_tests_avoided=metadata.live_tests_avoided and probe.live_tests_avoided,
        cache_required=metadata.cache_required or probe.cache_required,
        background_refresh_recommended=(
            metadata.background_refresh_recommended or probe.background_refresh_recommended
        ),
        network_call_executed=probe.network_call_executed,
        no_default_live_http_calls=probe.no_default_live_http_calls,
        best_use_cases=metadata.best_use_cases,
        rejected_for=metadata.rejected_for,
        not_recommended_for=metadata.not_recommended_for,
        missing_provider_reason=probe.missing_provider_reason or metadata.missing_provider_reason,
        degradation_reason=probe.degradation_reason or metadata.degradation_reason,
        adoption_status=adoption_status,
        recommended_next_step=_derive_recommended_next_step(metadata, adoption_status),
    )


def list_provider_fit_advisor_entries(
    provider_id: str | None = None,
) -> tuple[ProviderFitAdvisorEntry, ...]:
    """Return metadata-only provider-fit advisor entries."""

    if provider_id is None:
        probes_by_id = {
            probe.provider_id: probe for probe in list_provider_dry_run_probe_contracts()
        }
        entries = [
            _build_advisor_entry(metadata, probes_by_id[metadata.provider_id])
            for metadata in list_provider_fit_metadata()
        ]
        return tuple(sorted(entries, key=lambda entry: entry.provider_id))

    entry = get_provider_fit_advisor_entry(provider_id)
    return (entry,) if entry is not None else ()


def get_provider_fit_advisor_entry(provider_id: str) -> Optional[ProviderFitAdvisorEntry]:
    """Return one metadata-only provider-fit advisor entry, or ``None`` when unknown."""

    metadata = get_provider_fit_metadata(provider_id)
    probe = get_provider_dry_run_probe_contract(provider_id)
    if metadata is None or probe is None:
        return None
    return _build_advisor_entry(metadata, probe)


def build_provider_fit_advisor_snapshot(
    provider_id: str | None = None,
) -> ProviderFitAdvisorSnapshot:
    """Return a stable metadata-only provider-fit advisor snapshot."""

    return ProviderFitAdvisorSnapshot(entries=list_provider_fit_advisor_entries(provider_id))


__all__ = [
    "ProviderFitAdvisorEntry",
    "ProviderFitAdvisorSnapshot",
    "build_provider_fit_advisor_snapshot",
    "get_provider_fit_advisor_entry",
    "list_provider_fit_advisor_entries",
]
