# -*- coding: utf-8 -*-
"""Metadata-only diagnostic snapshots for the pure data source router.

This module must remain inert. It serializes router requests and route plans
for inspection and tests without calling provider runtimes, networks, env, or
other business services.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.services.data_source_router import (
    DataSourceRoutePlan,
    DataSourceRouteRequest,
    DataSourceRouter,
    ProviderRouteCandidate,
)


def _candidate_to_dict(candidate: ProviderRouteCandidate) -> dict[str, Any]:
    return {
        "providerId": candidate.provider_id,
        "providerName": candidate.provider_name,
        "capability": candidate.capability,
        "sourceType": candidate.source_type,
        "sourceTier": candidate.source_tier,
        "trustLevel": candidate.trust_level,
        "freshnessExpectation": candidate.freshness_expectation,
        "observationOnly": candidate.observation_only,
        "scoreContributionAllowed": candidate.score_contribution_allowed,
        "paidDataLikelyRequired": candidate.paid_data_likely_required,
        "keyRequired": candidate.key_required,
        "enabledByDefault": candidate.enabled_by_default,
        "noDefaultLiveHttpCalls": candidate.no_default_live_http_calls,
        "missingProviderReason": candidate.missing_provider_reason,
    }


def _request_to_dict(request: DataSourceRouteRequest) -> dict[str, Any]:
    return {
        "market": request.market,
        "assetType": request.asset_type,
        "useCase": request.use_case,
        "capability": request.capability,
        "freshnessNeed": request.freshness_need,
        "scoringAllowed": request.scoring_allowed,
        "symbol": request.symbol,
        "productId": request.product_id,
        "cik": request.cik,
        "asOf": request.as_of,
        "allowNetwork": request.allow_network,
        "reproducibilityRequired": request.reproducibility_required,
    }


def _plan_to_dict(plan: DataSourceRoutePlan) -> dict[str, Any]:
    payload = {
        "primaryCandidates": [_candidate_to_dict(candidate) for candidate in plan.primary_candidates],
        "observationCandidates": [_candidate_to_dict(candidate) for candidate in plan.observation_candidates],
        "forbiddenProviders": [_candidate_to_dict(candidate) for candidate in plan.forbidden_providers],
        "cacheRequired": plan.cache_required,
        "backgroundRefreshRequired": plan.background_refresh_required,
        "scoreContributionAllowed": plan.score_contribution_allowed,
        "degradationPolicy": plan.degradation_policy,
        "requiredSourceTypes": list(plan.required_source_types),
        "freshnessFloor": plan.freshness_floor,
        "trustFloor": plan.trust_floor,
        "reasonCodes": {provider_id: list(codes) for provider_id, codes in plan.reason_codes.items()},
    }
    if plan.required_symbols:
        payload["requiredSymbols"] = list(plan.required_symbols)
    if plan.session:
        payload["session"] = plan.session
    return payload


@dataclass(frozen=True, slots=True)
class DataSourceRouteDiagnosticSnapshot:
    request: DataSourceRouteRequest
    plan: DataSourceRoutePlan
    diagnostic_only: bool = True
    provider_runtime_called: bool = False
    network_calls_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "diagnosticOnly": self.diagnostic_only,
            "providerRuntimeCalled": self.provider_runtime_called,
            "networkCallsEnabled": self.network_calls_enabled,
            "request": _request_to_dict(self.request),
        }
        payload.update(_plan_to_dict(self.plan))
        return payload


def build_data_source_route_diagnostic_snapshot(
    request: DataSourceRouteRequest,
) -> DataSourceRouteDiagnosticSnapshot:
    """Return a metadata-only route-plan snapshot for diagnostics/tests."""

    return DataSourceRouteDiagnosticSnapshot(
        request=request,
        plan=DataSourceRouter.resolve(request),
    )


__all__ = [
    "DataSourceRouteDiagnosticSnapshot",
    "build_data_source_route_diagnostic_snapshot",
]
