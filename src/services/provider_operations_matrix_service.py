# -*- coding: utf-8 -*-
"""Read-only provider operations matrix aggregation.

This service composes static provider metadata and local diagnostics only. It
must not import provider SDKs, call live providers, force probes, mutate cache,
read secret values into responses, or change runtime provider order.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Sequence

from src.services.data_source_router import (
    DataSourceRouteRequest,
    DataSourceRouter,
)
from src.services.cn_hk_connect_flow_provider import (
    CN_HK_CONNECT_FLOW_CACHE_PATH_ENV,
    CN_HK_CONNECT_FLOW_PROVIDER_ENABLED_ENV,
)
from src.services.cn_hk_flow_contracts import AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID
from src.services.cn_money_market_rates_contracts import (
    OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV,
    OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
    CnMoneyMarketRatesProviderUnavailable,
    read_official_cn_money_market_rates_cache,
)
from src.services.official_macro_liquidity_cache_contracts import (
    OFFICIAL_FED_LIQUIDITY_PROVIDER_ID,
    build_official_fed_liquidity_cache_bundle,
)
from src.services.market_data_readiness_diagnostics import (
    MarketDataReadinessDiagnostics,
    build_market_data_readiness_diagnostics,
)
from src.services.provider_affected_surface_mapping import (
    canonical_product_affected_surfaces,
)
from src.services.market_data_source_registry import resolve_source_label, resolve_source_type
from src.services.polygon_us_breadth_provider import (
    POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
    POLYGON_US_BREADTH_AUTHORITY_BASIS,
    POLYGON_US_BREADTH_SOURCE,
    POLYGON_US_BREADTH_SOURCE_LABEL,
    POLYGON_US_BREADTH_SOURCE_TIER,
    POLYGON_US_BREADTH_SOURCE_TYPE,
    POLYGON_US_BREADTH_TRUST_LEVEL,
    POLYGON_US_BREADTH_UNIVERSE,
)
from src.services.provider_capability_matrix import (
    ProviderCapability,
    ProviderCapabilitySupportContract,
    ProviderFitMetadataContract,
    ProviderScoringContract,
    get_provider_dry_run_probe_contract,
    list_provider_capabilities,
    list_provider_capability_support_contracts,
    list_provider_fit_metadata,
    list_provider_scoring_contracts,
)
from src.services.provider_fit_advisor_service import list_provider_fit_advisor_entries


CN_TZ = timezone(timedelta(hours=8))
SpecFinder = Callable[[str], object | None]

_PROXY_OR_WEAK_SOURCE_TYPES = frozenset(
    {
        "public_proxy",
        "unofficial_proxy",
        "missing",
        "fallback_static",
        "synthetic_fixture",
        "delayed_fixture",
        "disabled_live_stub",
    }
)
_OPTIONAL_MODULE_BY_PROVIDER = {
    "akshare": "akshare",
    "akshare_existing_baseline": "akshare",
    "baostock": "baostock",
    "efinance": "efinance",
    "pytdx": "pytdx",
    "pytdx_existing_baseline": "pytdx",
    "tushare_pro": "tushare",
}
_CREDENTIAL_ENV_KEYS_BY_PROVIDER = {
    "alpha_vantage": ("ALPHA_VANTAGE_API_KEY", "ALPHAVANTAGE_API_KEY"),
    AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID: (CN_HK_CONNECT_FLOW_CACHE_PATH_ENV,),
    "finnhub": ("FINNHUB_API_KEY", "FINNHUB_TOKEN"),
    "marketstack": ("MARKETSTACK_API_KEY",),
    "nasdaq_data_link": ("NASDAQ_DATA_LINK_API_KEY", "QUANDL_API_KEY"),
    "polygon_us_grouped_daily": ("POLYGON_API_KEY",),
    "tushare_pro": ("TUSHARE_TOKEN",),
    "twelve_data": ("TWELVE_DATA_API_KEY",),
}
_MISSING_FEED_PROVIDER_IDS = frozenset(
    {
        "authorized.cn_hk_connect_flow",
        "authorized.real_sector_theme_flow",
        "authorized.us_etf_flow",
        "exchange_or_broker_authorized.index_futures",
        "official_public.cn_money_market_rates",
        "official_or_authorized.fx_dxy",
        "official_or_authorized.us_market_breadth",
    }
)
_NO_OPTIONAL_DEPENDENCY_PROVIDER_IDS = _MISSING_FEED_PROVIDER_IDS | {
    "official_public.fed_liquidity",
    "polygon_us_grouped_daily",
}
_OFFICIAL_FED_LIQUIDITY_PROVIDER_ID = OFFICIAL_FED_LIQUIDITY_PROVIDER_ID
_POLYGON_US_BREADTH_AD_METRICS = (
    "ADVANCERS",
    "DECLINERS",
    "UNCHANGED",
    "ADVANCE_DECLINE_RATIO",
)
_POLYGON_US_BREADTH_HIGH_LOW_METRICS = ("NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO")


@dataclass
class _ProviderAccumulator:
    provider_id: str
    provider_name: str | None = None
    provider_category: str | None = None
    source_type: str | None = None
    source_tier: str | None = None
    trust_level: str | None = None
    freshness_expectation: str | None = None
    runtime_state: str | None = None
    enabled_by_default: bool = False
    observation_only: bool = False
    score_contribution_allowed: bool = False
    inert_metadata_only: bool = False
    paid_data_likely_required: bool = False
    key_required: bool = False
    no_default_live_http_calls: bool = True
    cache_required: bool | None = None
    supported_capabilities: set[str] = field(default_factory=set)
    affected_surfaces: set[str] = field(default_factory=set)
    router_reason_codes: set[str] = field(default_factory=set)
    reason_codes: list[str] = field(default_factory=list)
    contract_coverage_universes: set[str] = field(default_factory=set)
    contract_cadences: set[str] = field(default_factory=set)
    contract_freshness_floors: set[str] = field(default_factory=set)
    contract_required_symbols: list[str] = field(default_factory=list)
    contract_sessions: list[str] = field(default_factory=list)
    required_source_tiers: set[str] = field(default_factory=set)
    score_eligibility_gates: set[str] = field(default_factory=set)
    contract_coverage_ratio_floor: float | None = None
    missing_provider_reason: str | None = None
    degradation_reason: str | None = None
    remediation_hint: str | None = None
    source_label: str | None = None
    source_authority_allowed: bool | None = None
    fulfilled_metrics: list[str] = field(default_factory=list)
    missing_metrics: list[str] = field(default_factory=list)
    authority_basis: str | None = None
    universe: str | None = None
    coverage_count: int | None = None
    source_freshness_evidence: dict[str, Any] | None = None
    official_exchange_published_breadth: bool | None = None
    full_breadth_authority: bool | None = None
    capability_metadata_present: bool = False
    fit_metadata_present: bool = False
    support_contract_present: bool = False


class ProviderOperationsMatrixService:
    """Build an operator-facing provider inventory without side effects."""

    _router = DataSourceRouter

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        spec_finder: SpecFinder = importlib.util.find_spec,
    ) -> None:
        self.env = env if env is not None else os.environ
        self.spec_finder = spec_finder

    def build_matrix(self) -> dict[str, Any]:
        readiness = build_market_data_readiness_diagnostics(
            env=self.env,
            spec_finder=self.spec_finder,
        )
        rows_by_id = self._collect_rows(readiness)
        rows = [self._row_to_dict(row, readiness) for row in rows_by_id.values()]
        rows.sort(key=lambda item: item["providerId"])
        return {
            "generatedAt": datetime.now(CN_TZ).isoformat(timespec="seconds"),
            "diagnosticOnly": True,
            "rows": rows,
            "summary": self._summary(rows),
            "metadata": {
                "source": "provider_fit_capability_readiness_router_contracts",
                "readOnly": True,
                "diagnosticOnly": True,
                "externalProviderCalls": False,
                "providerProbesForced": False,
                "networkCallsEnabled": False,
                "cacheMutation": False,
                "providerOrderChanged": False,
                "dataFetcherManagerChanged": False,
                "frontendChanged": False,
                "dbChanged": False,
                "secretValuesIncluded": False,
                "rawProviderPayloadsIncluded": False,
                "readinessStatus": readiness.readiness_status,
                "rowCount": len(rows),
            },
        }

    def _collect_rows(
        self,
        readiness: MarketDataReadinessDiagnostics,
    ) -> dict[str, _ProviderAccumulator]:
        rows: dict[str, _ProviderAccumulator] = {}

        for capability in list_provider_capabilities():
            self._merge_capability(rows, capability)
        for support in list_provider_capability_support_contracts():
            self._merge_support_contract(rows, support)
        for scoring_contract in list_provider_scoring_contracts():
            self._merge_scoring_contract(rows, scoring_contract)
        for metadata in list_provider_fit_metadata():
            self._merge_fit_metadata(rows, metadata)
        for advisor in list_provider_fit_advisor_entries():
            row = self._row(rows, advisor.provider_id)
            row.affected_surfaces.update(advisor.best_use_cases)
            row.no_default_live_http_calls = (
                row.no_default_live_http_calls and advisor.no_default_live_http_calls
            )

        self._merge_router_reason_codes(rows)
        self._merge_authorized_cn_hk_connect_flow_projection(rows)
        self._merge_official_fed_liquidity_projection(rows)
        self._merge_official_cn_money_market_rates_projection(rows)
        self._merge_polygon_us_breadth_projection(rows)
        self._merge_readiness(readiness, rows)
        return rows

    def _merge_capability(
        self,
        rows: dict[str, _ProviderAccumulator],
        capability: ProviderCapability,
    ) -> None:
        row = self._row(rows, capability.provider_id)
        row.capability_metadata_present = True
        row.provider_name = row.provider_name or capability.display_name
        row.provider_category = row.provider_category or "runtime_capability"
        row.source_type = row.source_type or self._source_type_for_runtime(capability)
        row.source_tier = row.source_tier or self._source_tier_for_runtime(capability)
        row.trust_level = row.trust_level or self._trust_for_runtime(capability)
        row.freshness_expectation = row.freshness_expectation or capability.freshness_class.value
        row.runtime_state = row.runtime_state or "runtime_metadata"
        row.enabled_by_default = True
        row.score_contribution_allowed = True
        row.supported_capabilities.update(domain.value for domain in capability.domains)
        row.affected_surfaces.update(
            surface
            for surface, allowed in (
                ("scanner", capability.scanner_allowed),
                ("backtest", capability.backtest_allowed),
                ("quick_analysis", capability.quick_analysis_allowed),
                ("standard_analysis", capability.standard_analysis_allowed),
                ("deep_research", capability.deep_research_allowed),
            )
            if allowed
        )

    def _merge_support_contract(
        self,
        rows: dict[str, _ProviderAccumulator],
        support: ProviderCapabilitySupportContract,
    ) -> None:
        row = self._row(rows, support.provider_id)
        row.support_contract_present = True
        row.provider_name = row.provider_name or support.provider_name
        row.provider_category = row.provider_category or "capability_support_contract"
        row.source_type = self._prefer_specific(row.source_type, support.source_type)
        row.source_tier = self._prefer_specific(row.source_tier, support.source_tier)
        row.trust_level = self._prefer_specific(row.trust_level, support.trust_level)
        row.freshness_expectation = self._prefer_specific(
            row.freshness_expectation,
            support.freshness_expectation,
        )
        row.observation_only = row.observation_only or support.observation_only
        row.score_contribution_allowed = (
            row.score_contribution_allowed and support.score_contribution_allowed
        )
        row.paid_data_likely_required = (
            row.paid_data_likely_required or support.paid_data_likely_required
        )
        row.key_required = row.key_required or support.key_required
        row.supported_capabilities.add(support.capability)
        row.missing_provider_reason = row.missing_provider_reason or support.missing_provider_reason
        row.degradation_reason = row.degradation_reason or support.degradation_reason

    def _merge_fit_metadata(
        self,
        rows: dict[str, _ProviderAccumulator],
        metadata: ProviderFitMetadataContract,
    ) -> None:
        row = self._row(rows, metadata.provider_id)
        row.fit_metadata_present = True
        row.provider_name = metadata.provider_name
        row.provider_category = metadata.provider_category
        row.source_type = self._prefer_specific(
            row.source_type,
            resolve_source_type(source=metadata.provider_id),
        )
        row.source_tier = metadata.source_tier
        row.trust_level = metadata.trust_level
        row.freshness_expectation = metadata.freshness_expectation
        row.enabled_by_default = row.enabled_by_default or metadata.enabled_by_default
        row.observation_only = row.observation_only or metadata.observation_only
        row.score_contribution_allowed = (
            row.score_contribution_allowed and metadata.score_contribution_allowed
        )
        row.inert_metadata_only = True
        row.paid_data_likely_required = (
            row.paid_data_likely_required or metadata.paid_data_likely_required
        )
        row.key_required = row.key_required or metadata.key_required
        row.affected_surfaces.update(metadata.best_use_cases)
        row.router_reason_codes.update(metadata.rejected_for)
        row.missing_provider_reason = row.missing_provider_reason or metadata.missing_provider_reason
        row.degradation_reason = row.degradation_reason or metadata.degradation_reason
        row.runtime_state = row.runtime_state or "metadata_only"
        probe = get_provider_dry_run_probe_contract(metadata.provider_id)
        if probe is not None:
            row.no_default_live_http_calls = (
                row.no_default_live_http_calls and probe.no_default_live_http_calls
            )

    def _merge_scoring_contract(
        self,
        rows: dict[str, _ProviderAccumulator],
        scoring_contract: ProviderScoringContract,
    ) -> None:
        row = self._row(rows, scoring_contract.provider_id)
        row.supported_capabilities.add(scoring_contract.capability)
        row.contract_coverage_universes.add(scoring_contract.coverage_universe)
        row.contract_cadences.add(scoring_contract.cadence)
        row.contract_freshness_floors.add(scoring_contract.freshness_floor)
        for symbol in scoring_contract.required_symbols:
            if symbol not in row.contract_required_symbols:
                row.contract_required_symbols.append(symbol)
        if scoring_contract.session and scoring_contract.session not in row.contract_sessions:
            row.contract_sessions.append(scoring_contract.session)
        row.required_source_tiers.add(scoring_contract.required_source_tier)
        row.score_eligibility_gates.add(scoring_contract.score_eligibility_gate)
        floor = float(scoring_contract.coverage_ratio_floor)
        row.contract_coverage_ratio_floor = (
            floor
            if row.contract_coverage_ratio_floor is None
            else min(row.contract_coverage_ratio_floor, floor)
        )

    def _merge_router_reason_codes(
        self,
        rows: dict[str, _ProviderAccumulator],
    ) -> None:
        for use_case, capability, market, asset_type in self._router_diagnostic_requests():
            plan = self._router.resolve(
                DataSourceRouteRequest(
                    market=market,
                    asset_type=asset_type,
                    use_case=use_case,
                    capability=capability,
                    freshness_need="live" if capability == "quote" else "daily",
                    scoring_allowed=capability == "quote",
                    allow_network=False,
                    reproducibility_required=use_case == "backtest",
                )
            )
            for candidate in (
                plan.primary_candidates
                + plan.observation_candidates
                + plan.forbidden_providers
            ):
                row = self._row(rows, candidate.provider_id)
                row.provider_name = row.provider_name or candidate.provider_name
                row.provider_category = row.provider_category or "router_candidate"
                row.source_type = row.source_type or candidate.source_type
                row.source_tier = row.source_tier or candidate.source_tier
                row.trust_level = row.trust_level or candidate.trust_level
                row.freshness_expectation = (
                    row.freshness_expectation or candidate.freshness_expectation
                )
                row.supported_capabilities.add(candidate.capability)
                row.affected_surfaces.add(use_case)
                row.missing_provider_reason = (
                    row.missing_provider_reason or candidate.missing_provider_reason
                )
                row.no_default_live_http_calls = (
                    row.no_default_live_http_calls and candidate.no_default_live_http_calls
                )
            for provider_id, codes in plan.reason_codes.items():
                if provider_id == "plan":
                    for row in rows.values():
                        if capability in row.supported_capabilities:
                            row.router_reason_codes.update(codes)
                            row.affected_surfaces.add(use_case)
                    continue
                row = self._row(rows, provider_id)
                row.router_reason_codes.update(codes)
                row.affected_surfaces.add(use_case)

    def _merge_polygon_us_breadth_projection(
        self,
        rows: dict[str, _ProviderAccumulator],
    ) -> None:
        row = self._row(rows, POLYGON_US_BREADTH_SOURCE)
        row.provider_name = POLYGON_US_BREADTH_SOURCE_LABEL
        row.source_label = POLYGON_US_BREADTH_SOURCE_LABEL
        row.provider_category = "computed_breadth_projection"
        row.source_type = POLYGON_US_BREADTH_SOURCE_TYPE
        row.source_tier = POLYGON_US_BREADTH_SOURCE_TIER
        row.trust_level = POLYGON_US_BREADTH_TRUST_LEVEL
        row.freshness_expectation = "polygon_grouped_daily_eod_recent_completed_us_weekday"
        row.runtime_state = "read_only_projection"
        row.observation_only = False
        row.score_contribution_allowed = True
        row.source_authority_allowed = True
        row.inert_metadata_only = True
        row.paid_data_likely_required = True
        row.key_required = True
        row.cache_required = True
        row.no_default_live_http_calls = True
        row.supported_capabilities.update(
            {
                "us_advancers_decliners",
                "us_market_breadth_eod_ad",
            }
        )
        row.affected_surfaces.update({"market_overview", "liquidity_impulse"})
        row.fulfilled_metrics = list(_POLYGON_US_BREADTH_AD_METRICS)
        row.missing_metrics = list(_POLYGON_US_BREADTH_HIGH_LOW_METRICS)
        row.reason_codes = [POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON]
        row.authority_basis = POLYGON_US_BREADTH_AUTHORITY_BASIS
        row.universe = POLYGON_US_BREADTH_UNIVERSE
        row.coverage_count = None
        row.source_freshness_evidence = {
            "freshness": "delayed",
            "freshnessPolicy": "polygon_grouped_daily_eod_recent_completed_us_weekday",
            "isFallback": False,
            "isPartial": True,
            "isUnavailable": False,
        }
        row.official_exchange_published_breadth = False
        row.full_breadth_authority = False

    def _merge_authorized_cn_hk_connect_flow_projection(
        self,
        rows: dict[str, _ProviderAccumulator],
    ) -> None:
        row = self._row(rows, AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID)
        row.no_default_live_http_calls = True
        row.cache_required = True
        row.observation_only = True
        row.score_contribution_allowed = False
        enabled_raw = _text(self.env.get(CN_HK_CONNECT_FLOW_PROVIDER_ENABLED_ENV))
        cache_path_present = bool(_text(self.env.get(CN_HK_CONNECT_FLOW_CACHE_PATH_ENV)))
        if enabled_raw and not _env_bool(enabled_raw, default=False) and cache_path_present:
            row.reason_codes = ["provider_disabled"]
        elif enabled_raw and _env_bool(enabled_raw, default=False) and cache_path_present:
            row.reason_codes = ["cache_only_diagnostic", "score_contribution_disabled"]

    def _merge_official_cn_money_market_rates_projection(
        self,
        rows: dict[str, _ProviderAccumulator],
    ) -> None:
        row = self._row(rows, OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID)
        row.no_default_live_http_calls = True
        row.cache_required = True
        row.observation_only = True
        row.score_contribution_allowed = False
        row.key_required = False
        row.paid_data_likely_required = False

        if not _text(self.env.get(OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV)):
            return

        try:
            snapshot = read_official_cn_money_market_rates_cache(env=self.env)
        except CnMoneyMarketRatesProviderUnavailable as exc:
            row.runtime_state = "configured_cache_diagnostic_unavailable"
            row.source_type = "missing"
            row.source_authority_allowed = False
            row.reason_codes = list(exc.reason_codes)
            row.degradation_reason = exc.reason_codes[0] if exc.reason_codes else "malformed_payload"
            row.source_freshness_evidence = {
                "providerId": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
                "cacheOnly": True,
                "externalProviderCalls": False,
                "isUnavailable": True,
                "reasonCodes": list(exc.reason_codes),
            }
            return

        row.provider_name = str(snapshot.get("providerName") or row.provider_name or "")
        row.source_label = str(snapshot.get("sourceLabel") or row.provider_name or "")
        row.provider_category = row.provider_category or "official_macro_liquidity_contract"
        row.source_type = str(snapshot.get("sourceType") or "official_public")
        row.source_tier = str(snapshot.get("sourceTier") or "official_public")
        row.trust_level = str(snapshot.get("trustLevel") or "score_grade_when_configured")
        row.freshness_expectation = (
            row.freshness_expectation or "session_delayed_or_daily_official_fixing"
        )
        row.runtime_state = "configured_cache_only_diagnostic"
        row.source_authority_allowed = True
        row.reason_codes = [str(code) for code in snapshot.get("reasonCodes") or []]
        row.fulfilled_metrics = [str(item) for item in snapshot.get("fulfilledMetrics") or []]
        row.missing_metrics = [str(item) for item in snapshot.get("missingMetrics") or []]
        row.coverage_count = len(row.fulfilled_metrics)
        evidence = snapshot.get("sourceFreshnessEvidence")
        row.source_freshness_evidence = dict(evidence) if isinstance(evidence, Mapping) else None
        row.missing_provider_reason = None
        row.degradation_reason = None
        row.inert_metadata_only = True

    def _merge_official_fed_liquidity_projection(
        self,
        rows: dict[str, _ProviderAccumulator],
    ) -> None:
        row = self._row(rows, _OFFICIAL_FED_LIQUIDITY_PROVIDER_ID)
        projection = self._project_official_fed_liquidity_runtime_bundle()
        row.provider_name = row.provider_name or "Official Fed Liquidity"
        row.source_label = row.source_label or row.provider_name
        row.provider_category = row.provider_category or "official_macro_liquidity_contract"
        row.source_type = "official_public"
        row.source_tier = "official_public"
        row.trust_level = str(
            projection.get("trustLevel") or row.trust_level or "score_grade_when_configured"
        )
        row.freshness_expectation = row.freshness_expectation or "daily_or_weekly_public_release_lag"
        row.runtime_state = str(projection["runtimeState"])
        row.observation_only = bool(projection["observationOnly"])
        row.source_authority_allowed = bool(projection["sourceAuthorityAllowed"])
        row.score_contribution_allowed = bool(projection["scoreContributionAllowed"])
        row.key_required = False
        row.paid_data_likely_required = False
        row.cache_required = True
        row.no_default_live_http_calls = True
        row.reason_codes = [str(code) for code in projection["reasonCodes"]]
        row.fulfilled_metrics = [str(item) for item in projection["fulfilledMetrics"]]
        row.missing_metrics = [str(item) for item in projection["missingMetrics"]]
        row.coverage_count = int(projection["coverageCount"])
        row.source_freshness_evidence = dict(projection["sourceFreshnessEvidence"])
        row.missing_provider_reason = None
        row.degradation_reason = (
            str(projection["degradationReason"])
            if projection.get("degradationReason") is not None
            else None
        )
        row.inert_metadata_only = True

    def _merge_readiness(
        self,
        readiness: MarketDataReadinessDiagnostics,
        rows: dict[str, _ProviderAccumulator],
    ) -> None:
        checks_by_id = {check.id: check for check in readiness.checks}
        token_check = checks_by_id.get("tushare_token")
        if token_check is not None:
            row = rows.get("tushare_pro")
            if row is not None and token_check.status != "ready":
                row.router_reason_codes.add("credential_missing")
                row.affected_surfaces.update(token_check.affects_surfaces)
                row.degradation_reason = row.degradation_reason or "credential_missing"
                row.remediation_hint = row.remediation_hint or token_check.remediation_hint

        dependency_check = checks_by_id.get("optional_provider_dependencies")
        details = dependency_check.details if dependency_check is not None else {}
        for module in details.get("missingModules", []) if isinstance(details, dict) else []:
            for row in rows.values():
                if _OPTIONAL_MODULE_BY_PROVIDER.get(row.provider_id) == module:
                    row.router_reason_codes.add("dependency_missing")
                    row.affected_surfaces.update(dependency_check.affects_surfaces)
                    row.degradation_reason = row.degradation_reason or "dependency_missing"
                    row.remediation_hint = row.remediation_hint or dependency_check.remediation_hint

    def _row_to_dict(
        self,
        row: _ProviderAccumulator,
        readiness: MarketDataReadinessDiagnostics,
    ) -> dict[str, Any]:
        source_type = row.source_type or resolve_source_type(source=row.provider_id)
        credential_state = self._credential_state(row)
        dependency_state = self._dependency_state(row)
        runtime_state = self._runtime_state(row, credential_state, dependency_state)
        score_eligible = self._score_eligible(row, source_type)
        remediation_hint = row.remediation_hint or self._remediation_hint(
            row,
            credential_state,
            dependency_state,
            runtime_state,
        )
        payload = {
            "providerId": row.provider_id,
            "providerName": row.provider_name
            or resolve_source_label(source=row.provider_id, source_type=source_type),
            "sourceLabel": row.source_label
            or row.provider_name
            or resolve_source_label(source=row.provider_id, source_type=source_type),
            "providerCategory": row.provider_category or "metadata",
            "sourceType": source_type,
            "sourceTier": row.source_tier or source_type,
            "trustLevel": row.trust_level or "unknown",
            "freshnessExpectation": row.freshness_expectation or "unknown",
            "runtimeState": runtime_state,
            "credentialState": credential_state,
            "dependencyState": dependency_state,
            "enabledByDefault": row.enabled_by_default,
            "observationOnly": row.observation_only,
            "sourceAuthorityAllowed": row.source_authority_allowed,
            "scoreContributionAllowed": row.score_contribution_allowed,
            "scoreEligible": score_eligible,
            "inertMetadataOnly": row.inert_metadata_only and not row.capability_metadata_present,
            "paidDataLikelyRequired": row.paid_data_likely_required,
            "keyRequired": row.key_required,
            "noDefaultLiveHttpCalls": row.no_default_live_http_calls,
            "cacheRequired": row.cache_required,
            "contractCoverageUniverses": sorted(row.contract_coverage_universes),
            "contractCadences": sorted(row.contract_cadences),
            "contractFreshnessFloors": sorted(row.contract_freshness_floors),
            "contractCoverageRatioFloor": row.contract_coverage_ratio_floor,
            "requiredSourceTiers": sorted(row.required_source_tiers),
            "scoreEligibilityGates": sorted(row.score_eligibility_gates),
            "supportedCapabilities": sorted(row.supported_capabilities),
            "affectedSurfaces": sorted(row.affected_surfaces),
            "productAffectedSurfaces": self._canonical_product_affected_surfaces(
                sorted(row.affected_surfaces)
            ),
            "routerReasonCodes": sorted(row.router_reason_codes),
            "reasonCodes": list(row.reason_codes),
            "fulfilledMetrics": list(row.fulfilled_metrics),
            "missingMetrics": list(row.missing_metrics),
            "authorityBasis": row.authority_basis,
            "universe": row.universe,
            "coverageCount": row.coverage_count,
            "sourceFreshnessEvidence": row.source_freshness_evidence,
            "officialExchangePublishedBreadth": row.official_exchange_published_breadth,
            "fullBreadthAuthority": row.full_breadth_authority,
            "missingProviderReason": row.missing_provider_reason,
            "degradationReason": row.degradation_reason,
            "remediationHint": remediation_hint,
            "diagnosticOnly": True,
        }
        if row.contract_required_symbols:
            payload["contractRequiredSymbols"] = list(row.contract_required_symbols)
        if row.contract_sessions:
            payload["contractSessions"] = list(row.contract_sessions)
        return payload

    @staticmethod
    def _row(
        rows: dict[str, _ProviderAccumulator],
        provider_id: str,
    ) -> _ProviderAccumulator:
        normalized = str(provider_id or "").strip().lower()
        if normalized not in rows:
            rows[normalized] = _ProviderAccumulator(provider_id=normalized)
        return rows[normalized]

    @staticmethod
    def _prefer_specific(current: str | None, incoming: str | None) -> str | None:
        if incoming and (not current or current in {"unknown", "runtime_metadata"}):
            return incoming
        return current or incoming

    @staticmethod
    def _canonical_product_affected_surfaces(
        surfaces: Sequence[str] | None,
    ) -> list[str]:
        return list(canonical_product_affected_surfaces(surfaces))

    @staticmethod
    def _router_diagnostic_requests() -> tuple[tuple[str, str, str, str], ...]:
        return (
            ("market_overview", "quote", "US", "equity"),
            ("scanner_diagnostics", "cn_history_daily", "CN", "equity"),
            ("market_observation", "cn_market_stats", "CN", "equity"),
            ("venue_observation", "venue_ticker", "crypto", "crypto"),
            ("market_overview", "fed_liquidity", "US", "macro"),
            ("liquidity_impulse", "fed_liquidity", "US", "macro"),
            ("market_overview", "fx_dxy", "forex", "forex"),
            ("liquidity_impulse", "fx_dxy", "forex", "forex"),
            ("market_overview", "us_etf_flow_daily", "US", "etf"),
            ("liquidity_impulse", "us_etf_creation_redemption", "US", "etf"),
            ("market_overview", "cn_money_market_rates", "CN", "macro"),
            ("liquidity_impulse", "cn_money_market_rates", "CN", "macro"),
            ("market_overview", "cn_hk_connect_flow", "CN", "equity"),
            ("liquidity_impulse", "cn_hk_connect_flow", "CN", "equity"),
            ("market_overview", "index_futures", "US", "futures"),
            ("liquidity_impulse", "index_futures", "US", "futures"),
            ("rotation_radar", "us_sector_etf_flow", "US", "etf"),
            ("rotation_radar", "real_sector_theme_flow_evidence", "US", "equity"),
            ("market_overview", "us_market_breadth_constituents", "US", "equity"),
            ("liquidity_impulse", "us_market_breadth_constituents", "US", "equity"),
        )

    @staticmethod
    def _source_type_for_runtime(capability: ProviderCapability) -> str:
        if capability.provider_id.startswith("local_") or capability.provider_id == "local_cache":
            return "cache_snapshot"
        return resolve_source_type(source=capability.provider_id)

    @staticmethod
    def _source_tier_for_runtime(capability: ProviderCapability) -> str:
        if capability.provider_id.startswith("local_") or capability.provider_id == "local_cache":
            return "local_cache"
        return "runtime_metadata"

    @staticmethod
    def _trust_for_runtime(capability: ProviderCapability) -> str:
        if capability.provider_id.startswith("local_") or capability.provider_id == "local_cache":
            return "reproducible_local_or_stored"
        return "runtime_metadata"

    def _credential_state(self, row: _ProviderAccumulator) -> str:
        if not row.key_required:
            return "not_required"
        keys = _CREDENTIAL_ENV_KEYS_BY_PROVIDER.get(row.provider_id)
        if not keys:
            if row.provider_id in _MISSING_FEED_PROVIDER_IDS:
                return "missing"
            return "unknown"
        return "present" if any(str(self.env.get(key, "") or "").strip() for key in keys) else "missing"

    def _dependency_state(self, row: _ProviderAccumulator) -> str:
        module_name = _OPTIONAL_MODULE_BY_PROVIDER.get(row.provider_id)
        if not module_name:
            return (
                "not_required"
                if row.provider_id in _NO_OPTIONAL_DEPENDENCY_PROVIDER_IDS
                else "unknown"
            )
        try:
            return "installed" if self.spec_finder(module_name) is not None else "missing"
        except (ImportError, ModuleNotFoundError, ValueError):
            return "missing"

    def _runtime_state(
        self,
        row: _ProviderAccumulator,
        credential_state: str,
        dependency_state: str,
    ) -> str:
        if row.provider_id == AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID:
            configured_state = self._cn_hk_connect_flow_runtime_state(credential_state)
            if configured_state is not None:
                return configured_state
        if row.provider_id == _OFFICIAL_FED_LIQUIDITY_PROVIDER_ID and row.runtime_state:
            return row.runtime_state
        if row.provider_id == OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID:
            configured_state = self._cn_money_market_rates_runtime_state(row)
            if configured_state is not None:
                return configured_state
        if row.provider_id in _MISSING_FEED_PROVIDER_IDS:
            return "missing_provider_configuration"
        if credential_state == "missing":
            return "credential_missing"
        if dependency_state == "missing":
            return "dependency_missing"
        if row.capability_metadata_present:
            return row.runtime_state or "runtime_metadata"
        if row.observation_only:
            return "observation_only"
        return row.runtime_state or "metadata_only"

    def _cn_hk_connect_flow_runtime_state(self, credential_state: str) -> str | None:
        enabled_raw = _text(self.env.get(CN_HK_CONNECT_FLOW_PROVIDER_ENABLED_ENV))
        enabled_configured = bool(enabled_raw)
        enabled = _env_bool(enabled_raw, default=False)
        cache_path_present = credential_state == "present"
        if enabled_configured and not enabled and cache_path_present:
            return "disabled"
        if enabled and cache_path_present:
            return "configured_cache_only_diagnostic"
        return None

    def _cn_money_market_rates_runtime_state(self, row: _ProviderAccumulator) -> str | None:
        cache_path_present = bool(_text(self.env.get(OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV)))
        if not cache_path_present:
            return None
        if row.runtime_state in {
            "configured_cache_only_diagnostic",
            "configured_cache_diagnostic_unavailable",
        }:
            return row.runtime_state
        return "configured_cache_diagnostic_unavailable"

    @staticmethod
    def _score_eligible(row: _ProviderAccumulator, source_type: str) -> bool:
        if row.observation_only or not row.score_contribution_allowed:
            return False
        if source_type in _PROXY_OR_WEAK_SOURCE_TYPES:
            return False
        if row.trust_level in {"weak", "usable_with_caution", "reference_only", "observation_only"}:
            return False
        if row.trust_level not in {"reproducible_local_or_stored", "score_grade"}:
            return False
        return True

    @staticmethod
    def _remediation_hint(
        row: _ProviderAccumulator,
        credential_state: str,
        dependency_state: str,
        runtime_state: str,
    ) -> str | None:
        if runtime_state == "missing_provider_configuration":
            return "Configure and audit an approved licensed feed before enabling runtime or scoring use."
        if credential_state == "missing":
            return "Configure provider credentials in the runtime environment before enabling this provider."
        if dependency_state == "missing":
            return "Install the optional provider dependency only if this environment needs the provider."
        if row.observation_only or row.source_type in _PROXY_OR_WEAK_SOURCE_TYPES:
            return (
                "Keep this provider diagnostic or observation-only unless explicit "
                "source-confidence gates approve promotion."
            )
        return None

    @staticmethod
    def _project_official_fed_liquidity_runtime_bundle(
        runtime_rows: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return build_official_fed_liquidity_cache_bundle(runtime_rows)

    @staticmethod
    def _summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        return {
            "totalRows": len(rows),
            "observationOnlyRows": sum(1 for row in rows if row["observationOnly"]),
            "inertMetadataOnlyRows": sum(1 for row in rows if row["inertMetadataOnly"]),
            "missingProviderRows": sum(
                1 for row in rows if row["runtimeState"] == "missing_provider_configuration"
            ),
            "scoreEligibleRows": sum(1 for row in rows if row["scoreEligible"]),
            "paidDataLikelyRequiredRows": sum(
                1 for row in rows if row["paidDataLikelyRequired"]
            ),
        }


def _env_bool(value: str, *, default: bool) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _text(value: Any) -> str:
    return str(value or "").strip()


__all__ = ["ProviderOperationsMatrixService"]
