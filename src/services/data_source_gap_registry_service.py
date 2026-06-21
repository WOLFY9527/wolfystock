# -*- coding: utf-8 -*-
"""Static data source gap registry projection.

The registry is intentionally inert: it does not read credentials, inspect the
environment, call provider runtimes, hydrate data, mutate cache, or write to
storage. It summarizes owned readiness facts and known integration blockers.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


DATA_SOURCE_GAP_REGISTRY_CONTRACT_VERSION = "data_source_gap_registry_v1"


@dataclass(frozen=True, slots=True)
class DataSourceGapRegistryFamily:
    family_key: str
    consumer_label: str
    status: str
    authority_state: str
    freshness_state: str
    entitlement_or_licensing_blocker: str | None
    integration_blocker: str | None
    source_evidence_state: str
    next_integration_step: str
    provider_hydration_allowed: bool
    score_trading_authority_allowed: bool
    consumer_safe_description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "familyKey": self.family_key,
            "consumerLabel": self.consumer_label,
            "status": self.status,
            "authorityState": self.authority_state,
            "freshnessState": self.freshness_state,
            "entitlementOrLicensingBlocker": self.entitlement_or_licensing_blocker,
            "integrationBlocker": self.integration_blocker,
            "sourceEvidenceState": self.source_evidence_state,
            "nextIntegrationStep": self.next_integration_step,
            "providerHydrationAllowed": self.provider_hydration_allowed,
            "scoreTradingAuthorityAllowed": self.score_trading_authority_allowed,
            "consumerSafeDescription": self.consumer_safe_description,
        }


_FAMILIES: tuple[DataSourceGapRegistryFamily, ...] = (
    DataSourceGapRegistryFamily(
        family_key="stock_quote_spine",
        consumer_label="Stock Quote Spine",
        status="partial",
        authority_state="blocked",
        freshness_state="delayed",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Durable quote/OHLCV snapshots and unified as-of lineage are still missing.",
        source_evidence_state="fragmented_runtime_evidence",
        next_integration_step="Land bounded quote and OHLCV snapshot storage with authority metadata.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Quote and OHLCV paths exist, but they are not yet a durable professional spine."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="fundamentals",
        consumer_label="Fundamentals",
        status="partial",
        authority_state="blocked",
        freshness_state="partial",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Point-in-time coverage and restatement-safe normalization are incomplete.",
        source_evidence_state="fragmented_runtime_evidence",
        next_integration_step="Normalize fundamentals, statements, and filing lineage by period and source.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Fundamental coverage exists in pieces, but period and lineage proof is incomplete."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="etf_index_coverage",
        consumer_label="ETF / Index Coverage",
        status="partial",
        authority_state="blocked",
        freshness_state="delayed",
        entitlement_or_licensing_blocker="Official membership and weight display rights are not yet proven.",
        integration_blocker="Membership, weights, benchmark, and breadth links are not unified.",
        source_evidence_state="fragmented_runtime_evidence",
        next_integration_step="Attach official ETF/index membership snapshots and benchmark mappings.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "ETF and index quotes are partially available, but membership authority is incomplete."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="macro_rates",
        consumer_label="Macro / Rates",
        status="observation-only",
        authority_state="observation-only",
        freshness_state="cached",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Durable official macro rows are not yet surfaced as a complete product bundle.",
        source_evidence_state="diagnostic_contract",
        next_integration_step="Persist official macro rows with freshness and coverage metadata.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Macro and rates readiness is available only as a diagnostic contract today."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="fed_liquidity",
        consumer_label="Fed Liquidity",
        status="observation-only",
        authority_state="observation-only",
        freshness_state="cached",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Weekly liquidity rows are not yet persisted as a complete bundle.",
        source_evidence_state="diagnostic_contract",
        next_integration_step="Persist the required liquidity series with coverage and stale-state markers.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Fed liquidity evidence is contract-shaped, but not yet a durable product spine."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="credit_stress",
        consumer_label="Credit Stress",
        status="observation-only",
        authority_state="observation-only",
        freshness_state="cached",
        entitlement_or_licensing_blocker=None,
        integration_blocker="A durable credit-stress series is not yet integrated.",
        source_evidence_state="diagnostic_contract",
        next_integration_step="Replace proxy-only context with stored credit-stress series evidence.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Credit stress is represented through bounded context, not score-grade evidence."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="vix_volatility",
        consumer_label="VIX / Volatility",
        status="partial",
        authority_state="blocked",
        freshness_state="delayed",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Official volatility rows and authority metadata are not unified.",
        source_evidence_state="fragmented_runtime_evidence",
        next_integration_step="Attach durable official volatility rows and fail-closed freshness gates.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Volatility evidence exists, but full professional source authority is still blocked."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="breadth_flows_positioning",
        consumer_label="Breadth / Flows / Positioning",
        status="partial",
        authority_state="blocked",
        freshness_state="partial",
        entitlement_or_licensing_blocker="Flow and positioning licensing are not yet proven.",
        integration_blocker="Breadth is partial; flow and positioning families remain incomplete.",
        source_evidence_state="fragmented_runtime_evidence",
        next_integration_step="Separate breadth proof from flow and positioning source reviews.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Breadth has partial evidence; flow and positioning remain review-bound."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="options_chains",
        consumer_label="Options Chains",
        status="unauthorized",
        authority_state="unauthorized",
        freshness_state="unavailable",
        entitlement_or_licensing_blocker=(
            "Options-chain access, display, storage, and decision-use rights are not proven."
        ),
        integration_blocker="No authorized live or delayed chain store is integrated.",
        source_evidence_state="rights_unproven",
        next_integration_step="Attach an entitlement proof bundle before chain promotion.",
        provider_hydration_allowed=False,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Options chains remain unavailable until authorized chain evidence exists."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="options_strategy_analytics",
        consumer_label="Options Strategy Analytics",
        status="blocked",
        authority_state="unauthorized",
        freshness_state="unavailable",
        entitlement_or_licensing_blocker=(
            "Authorized chain inputs and historical replay rights are not proven."
        ),
        integration_blocker="Strategy analytics cannot graduate before chain authority and history exist.",
        source_evidence_state="rights_unproven",
        next_integration_step="Prove authorized chain, history, and methodology inputs first.",
        provider_hydration_allowed=False,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Options strategy analytics remain blocked by missing authorized inputs."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="gamma_dealer_positioning",
        consumer_label="Gamma / Dealer Positioning",
        status="blocked",
        authority_state="unauthorized",
        freshness_state="unavailable",
        entitlement_or_licensing_blocker=(
            "Options rights, methodology approval, and positioning evidence are not proven."
        ),
        integration_blocker="No approved exposure methodology or rights-backed input set is integrated.",
        source_evidence_state="rights_unproven",
        next_integration_step="Approve rights, inputs, and methodology before exposing gamma-family outputs.",
        provider_hydration_allowed=False,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Gamma, GEX, vanna, charm, and dealer positioning remain blocked."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="backtest_dataset_lineage",
        consumer_label="Backtest Dataset Lineage",
        status="observation-only",
        authority_state="observation-only",
        freshness_state="unknown",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Dataset identity, adjusted basis, calendar, and PIT membership remain incomplete.",
        source_evidence_state="diagnostic_contract",
        next_integration_step="Persist dataset IDs, adjusted-basis evidence, and reproducibility manifests.",
        provider_hydration_allowed=False,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Backtest readback is research-useful, but professional dataset lineage is incomplete."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="scenario_baselines",
        consumer_label="Scenario Baselines",
        status="planned",
        authority_state="planned",
        freshness_state="unknown",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Durable baseline snapshot storage is not yet integrated.",
        source_evidence_state="not_integrated",
        next_integration_step="Store baseline snapshot IDs for market and portfolio scenario inputs.",
        provider_hydration_allowed=False,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Scenario baselines are planned, but stored baseline inputs are not integrated."
        ),
    ),
    DataSourceGapRegistryFamily(
        family_key="portfolio_valuation_lineage",
        consumer_label="Portfolio Valuation Lineage",
        status="partial",
        authority_state="blocked",
        freshness_state="partial",
        entitlement_or_licensing_blocker=None,
        integration_blocker="Price source, FX freshness, benchmark, and factor lineage remain incomplete.",
        source_evidence_state="fragmented_runtime_evidence",
        next_integration_step="Persist price, FX, valuation, benchmark, and factor lineage together.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=False,
        consumer_safe_description=(
            "Portfolio valuation is partially traced, but source lineage still needs hardening."
        ),
    ),
)


def _summary(families: tuple[DataSourceGapRegistryFamily, ...]) -> dict[str, int]:
    counts = Counter(family.status for family in families)
    return {
        "totalFamilies": len(families),
        "readyCount": counts.get("ready", 0),
        "partialCount": counts.get("partial", 0),
        "missingCount": counts.get("missing", 0),
        "blockedCount": counts.get("blocked", 0),
        "unauthorizedCount": counts.get("unauthorized", 0),
        "staleCount": counts.get("stale", 0),
        "observationOnlyCount": counts.get("observation-only", 0),
        "plannedCount": counts.get("planned", 0),
        "providerHydrationAllowedCount": sum(
            1 for family in families if family.provider_hydration_allowed
        ),
        "scoreTradingAuthorityAllowedCount": sum(
            1 for family in families if family.score_trading_authority_allowed
        ),
    }


def build_data_source_gap_registry() -> dict[str, Any]:
    """Return a deterministic, fail-closed data-family readiness registry."""

    families = _FAMILIES
    return {
        "contractVersion": DATA_SOURCE_GAP_REGISTRY_CONTRACT_VERSION,
        "diagnosticOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "scoreAuthorityAllowed": False,
        "summary": _summary(families),
        "families": [family.to_dict() for family in families],
        "metadata": {
            "source": "static_contract_registry",
            "readOnly": True,
            "noExternalCalls": True,
            "mutationEnabled": False,
            "credentialsRead": False,
            "rawProviderPayloadsIncluded": False,
        },
    }


__all__ = [
    "DATA_SOURCE_GAP_REGISTRY_CONTRACT_VERSION",
    "DataSourceGapRegistryFamily",
    "build_data_source_gap_registry",
]
