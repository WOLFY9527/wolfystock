# -*- coding: utf-8 -*-
"""Professional data capability readiness registry.

This registry is a consumer-safe projection over the existing static data source
gap registry. It does not inspect local configuration, call external data
runtimes, or hydrate provider/cache state.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from src.services.earnings_calendar_readiness_contract import (
    build_earnings_calendar_readiness_v1,
)
from src.services.macro_provider_readiness_service import (
    build_macro_provider_readiness_contract,
)
from src.services.market_breadth_readiness_service import (
    build_market_breadth_readiness_contract,
)
from src.services.cross_asset_driver_readiness import (
    build_cross_asset_driver_readiness,
)
from src.services.data_source_gap_registry_service import build_data_source_gap_registry


PROFESSIONAL_DATA_CAPABILITY_CONTRACT_VERSION = (
    "professional_data_capability_registry_v1"
)

_ALLOWED_STATUS = {
    "live",
    "degraded",
    "entitlement_required",
    "configured_missing",
    "not_implemented",
}


@dataclass(frozen=True, slots=True)
class _CapabilitySpec:
    capability_id: str
    label: str
    category: str
    source_family_key: str
    freshness: str
    source_label: str
    reason: str
    status_override: str | None = None
    readiness: dict[str, Any] | None = None


def _spec(
    capability_id: str,
    label: str,
    category: str,
    source_family_key: str,
    freshness: str,
    source_label: str,
    reason: str,
    *,
    status: str | None = None,
    readiness: dict[str, Any] | None = None,
) -> _CapabilitySpec:
    return _CapabilitySpec(
        capability_id=capability_id,
        label=label,
        category=category,
        source_family_key=source_family_key,
        freshness=freshness,
        source_label=source_label,
        reason=reason,
        status_override=status,
        readiness=readiness,
    )


_CAPABILITY_SPECS: tuple[_CapabilitySpec, ...] = (
    _spec(
        "options.chain",
        "Options chain",
        "options_structure",
        "options_chains",
        "Unavailable until chain rights, redisplay, and completeness evidence are proven.",
        "Options Lab readiness boundary",
        "Options chain display is blocked until entitlement and display rights are verified.",
    ),
    _spec(
        "options.greeks",
        "Option Greeks",
        "options_structure",
        "options_chains",
        "Unavailable until Greek methodology and chain completeness evidence are proven.",
        "Options Lab readiness boundary",
        "Greeks depend on authorized chain, IV, and methodology evidence that is not proven yet.",
    ),
    _spec(
        "options.gex",
        "Gamma exposure",
        "options_structure",
        "gamma_dealer_positioning",
        "Unavailable until chain, open interest, and dealer-positioning evidence are proven.",
        "Options Lab readiness boundary",
        "GEX is blocked because the underlying options evidence and rights are not proven.",
    ),
    _spec(
        "options.gamma_flip",
        "Gamma flip",
        "options_structure",
        "gamma_dealer_positioning",
        "Contract skeleton exists; production provider and methodology integration are not implemented.",
        "Options Lab roadmap",
        "Gamma flip remains unavailable until authorized GEX inputs and methodology evidence are connected.",
        status="not_implemented",
    ),
    _spec(
        "options.vanna_charm",
        "Vanna and charm",
        "options_structure",
        "options_strategy_analytics",
        "Contract skeleton exists; production provider and methodology integration are not implemented.",
        "Options Lab roadmap",
        "Vanna and charm remain unavailable until authorized Greeks and methodology evidence are connected.",
        status="not_implemented",
    ),
    _spec(
        "options.0dte",
        "0DTE options structure",
        "options_structure",
        "options_strategy_analytics",
        "Unavailable until intraday options completeness and display rights are proven.",
        "Options Lab readiness boundary",
        "0DTE structure can be represented by the contract, but live views remain blocked by rights, completeness, and freshness evidence gaps.",
    ),
    _spec(
        "market.breadth_flows",
        "Market breadth and flows",
        "market_breadth_flows",
        "breadth_flows_positioning",
        "Partial and delayed; live-grade participation, flow, and positioning lineage is incomplete.",
        "Market readiness registry",
        "Breadth and flow context exists, but source authority and coverage are not strong enough for live-grade claims.",
    ),
    _spec(
        "market.sector_rotation",
        "Sector rotation",
        "sector_rotation",
        "etf_index_coverage",
        "Partial and delayed; ETF quote and membership evidence is not fully authoritative.",
        "Market rotation readiness registry",
        "Rotation views are useful for context, but membership and quote authority remain incomplete.",
    ),
    _spec(
        "macro.cross_asset_regime",
        "Macro and cross-asset regime",
        "macro_cross_asset_regime",
        "macro_rates",
        "Stored or delayed observations; official macro freshness is not uniformly proven.",
        "Macro readiness registry",
        "Macro regime context is degraded until official rates, volatility, and liquidity evidence is complete.",
    ),
    _spec(
        "macro.fred.rates",
        "FRED rates",
        "macro_cross_asset_regime",
        "macro_rates",
        "Not configured; no macro conclusion is generated without official rates readiness.",
        "Macro/FRED readiness contract",
        "FRED rates readiness gates market-regime surfaces; no macro conclusion is generated by this contract.",
        status="configured_missing",
    ),
    _spec(
        "macro.fred.inflation",
        "FRED inflation",
        "macro_cross_asset_regime",
        "macro_rates",
        "Not configured; no macro conclusion is generated without official inflation readiness.",
        "Macro/FRED readiness contract",
        "FRED inflation readiness gates market-regime surfaces; no macro conclusion is generated by this contract.",
        status="configured_missing",
    ),
    _spec(
        "macro.fred.labor",
        "FRED labor",
        "macro_cross_asset_regime",
        "macro_rates",
        "Not configured; no macro conclusion is generated without official labor readiness.",
        "Macro/FRED readiness contract",
        "FRED labor readiness gates market-regime surfaces; no macro conclusion is generated by this contract.",
        status="configured_missing",
    ),
    _spec(
        "macro.fred.growth",
        "FRED growth",
        "macro_cross_asset_regime",
        "macro_rates",
        "Not configured; no macro conclusion is generated without official growth readiness.",
        "Macro/FRED readiness contract",
        "FRED growth readiness gates market-regime surfaces; no macro conclusion is generated by this contract.",
        status="configured_missing",
    ),
    _spec(
        "macro.fred.liquidity",
        "FRED liquidity",
        "macro_cross_asset_regime",
        "macro_rates",
        "Not configured; no macro conclusion is generated without official liquidity readiness.",
        "Macro/FRED readiness contract",
        "FRED liquidity readiness gates market-regime surfaces; no macro conclusion is generated by this contract.",
        status="configured_missing",
    ),
    _spec(
        "macro.fred.credit",
        "FRED credit",
        "macro_cross_asset_regime",
        "macro_rates",
        "Not configured; no macro conclusion is generated without official credit readiness.",
        "Macro/FRED readiness contract",
        "FRED credit readiness gates market-regime surfaces; no macro conclusion is generated by this contract.",
        status="configured_missing",
    ),
    _spec(
        "macro.fred.usd_currency",
        "FRED USD/currency",
        "macro_cross_asset_regime",
        "macro_rates",
        "Not configured; no macro conclusion is generated without official USD/currency readiness.",
        "Macro/FRED readiness contract",
        "FRED USD/currency readiness gates market-regime surfaces; no macro conclusion is generated by this contract.",
        status="configured_missing",
    ),
    _spec(
        "macro.fred.recession",
        "FRED recession",
        "macro_cross_asset_regime",
        "macro_rates",
        "Not configured; no macro conclusion is generated without official recession readiness.",
        "Macro/FRED readiness contract",
        "FRED recession readiness gates market-regime surfaces; no macro conclusion is generated by this contract.",
        status="configured_missing",
    ),
    _spec(
        "macro.volatility_liquidity_credit",
        "Volatility, liquidity, and credit stress",
        "macro_cross_asset_regime",
        "vix_volatility",
        "Partial and delayed; volatility is available with capped freshness confidence.",
        "Macro readiness registry",
        "Volatility and stress inputs exist, but live-grade official coverage is still incomplete.",
    ),
    _spec(
        "stock.fundamentals",
        "Stock fundamentals",
        "stock_research_data",
        "fundamentals",
        "Partial; coverage and as-of evidence vary by market and symbol.",
        "Single-stock readiness registry",
        "Fundamental context is supported, but coverage and lineage remain fragmented.",
    ),
    _spec(
        "stock.earnings_calendar",
        "Earnings calendar readiness",
        "stock_research_data",
        "fundamentals",
        "Not configured; earnings calendar, EPS, guidance, and transcript fields must stay hidden until evidence exists.",
        "Single-stock earnings calendar readiness",
        "Earnings calendar readiness is exposed as a contract only; no provider is configured and no dates or estimates are inferred.",
        status="configured_missing",
    ),
    _spec(
        "stock.technicals",
        "Stock technicals",
        "stock_research_data",
        "stock_quote_spine",
        "Partial and delayed; technicals depend on the quote and history spine.",
        "Single-stock readiness registry",
        "Technical analysis is supported, but the underlying quote/history spine is still degraded.",
    ),
    _spec(
        "stock.news",
        "Stock news and catalysts",
        "stock_research_data",
        "fundamentals",
        "Missing or inconsistent across symbols; do not assume current catalyst coverage.",
        "Single-stock readiness registry",
        "News and catalyst evidence is supported in research packets but is not consistently configured.",
        status="configured_missing",
    ),
    _spec(
        "backtest.data_availability",
        "Backtest data availability",
        "backtest_data_availability",
        "backtest_dataset_lineage",
        "Research-useful, but adjusted basis, calendar, and point-in-time lineage are incomplete.",
        "Backtest readiness registry",
        "Backtest execution is available for research, while professional dataset lineage remains degraded.",
    ),
    _spec(
        "market.breadth_readiness",
        "Market breadth readiness",
        "market_breadth_flows",
        "breadth_flows_positioning",
        "Readiness-only contract; no breadth score is emitted until supported measures and market coverage are proven.",
        "Market breadth readiness contract",
        "Advance/decline, highs/lows, percent-above-MA, sector participation, volume breadth, and equal-weight/cap-weight proxy readiness are reported separately by market.",
        status="configured_missing",
        readiness=build_market_breadth_readiness_contract(),
    ),
)

_MACRO_FRED_CAPABILITY_TO_CATEGORY = {
    "macro.fred.rates": "rates",
    "macro.fred.inflation": "inflation",
    "macro.fred.labor": "labor",
    "macro.fred.growth": "growth",
    "macro.fred.liquidity": "liquidity",
    "macro.fred.credit": "credit",
    "macro.fred.usd_currency": "usd_currency",
    "macro.fred.recession": "recession",
}


def _status_from_macro_state(state: str) -> str:
    if state == "available":
        return "live"
    if state == "stale":
        return "degraded"
    if state in {
        "missing",
        "missing_env",
        "not_configured",
        "disabled_by_flag",
    }:
        return "configured_missing"
    return "degraded"


def _status_from_family(family: dict[str, Any]) -> str:
    status = str(family.get("status") or "").strip().lower()
    has_entitlement_blocker = bool(family.get("entitlementOrLicensingBlocker"))

    if status == "ready":
        return "live"
    if status == "missing":
        return "configured_missing"
    if status in {"unauthorized", "blocked"} and has_entitlement_blocker:
        return "entitlement_required"
    if status in {"planned", "blocked"}:
        return "not_implemented"
    return "degraded"


def _family_index() -> dict[str, dict[str, Any]]:
    registry = build_data_source_gap_registry()
    return {
        str(family.get("familyKey")): family
        for family in registry.get("families", [])
        if family.get("familyKey")
    }


def _capability_to_dict(
    spec: _CapabilitySpec,
    family: dict[str, Any],
    *,
    include_admin_diagnostics: bool,
    macro_category: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = (
        _status_from_macro_state(str(macro_category.get("state") or ""))
        if macro_category is not None
        else spec.status_override or _status_from_family(family)
    )
    if status not in _ALLOWED_STATUS:
        status = "degraded"

    item: dict[str, Any] = {
        "capabilityId": spec.capability_id,
        "label": spec.label,
        "category": spec.category,
        "status": status,
        "freshness": str(macro_category.get("state")) if macro_category is not None else spec.freshness,
        "sourceLabel": spec.source_label,
        "reason": str(macro_category.get("reason")) if macro_category is not None else spec.reason,
    }
    if spec.capability_id == "stock.earnings_calendar":
        item["earningsCalendarReadiness"] = build_earnings_calendar_readiness_v1(
            {}
        )
    if include_admin_diagnostics:
        item["adminDiagnostics"] = {
            "sourceFamilyKey": spec.source_family_key,
            "sourceFamilyLabel": family.get("consumerLabel"),
            "sourceReadinessState": family.get("status"),
            "sourceAuthorityState": family.get("authorityState"),
            "sourceFreshnessState": family.get("freshnessState"),
            "sourceEvidenceState": family.get("sourceEvidenceState"),
            "nextEvidenceStep": family.get("nextIntegrationStep"),
            "scoreUseAllowed": bool(family.get("scoreTradingAuthorityAllowed")),
            "staticRegistryOnly": True,
            "runtimeCalled": False,
            "networkCallsEnabled": False,
        }
        if macro_category is not None:
            item["adminDiagnostics"].update(
                {
                    "macroReadinessState": macro_category.get("state"),
                    "nextAction": macro_category.get("nextAction"),
                }
            )
    if spec.readiness is not None:
        item["readiness"] = spec.readiness
    return item


def _summary(capabilities: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("status") or "") for item in capabilities)
    return {
        "totalCapabilities": len(capabilities),
        "liveCount": counts.get("live", 0),
        "degradedCount": counts.get("degraded", 0),
        "entitlementRequiredCount": counts.get("entitlement_required", 0),
        "configuredMissingCount": counts.get("configured_missing", 0),
        "notImplementedCount": counts.get("not_implemented", 0),
    }


def build_professional_data_capability_registry(
    *,
    include_admin_diagnostics: bool = False,
    macro_env: dict[str, Any] | None = None,
    macro_series_states: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return the normalized professional data capability registry."""

    families = _family_index()
    macro_readiness = build_macro_provider_readiness_contract(
        env=macro_env,
        series_states=macro_series_states,
        include_admin_diagnostics=include_admin_diagnostics,
    )
    macro_categories = {
        str(category.get("categoryKey")): category
        for category in macro_readiness.get("categories", [])
        if isinstance(category, dict) and category.get("categoryKey")
    }
    capabilities = [
        _capability_to_dict(
            spec,
            families.get(spec.source_family_key, {}),
            include_admin_diagnostics=include_admin_diagnostics,
            macro_category=macro_categories.get(
                _MACRO_FRED_CAPABILITY_TO_CATEGORY.get(spec.capability_id, "")
            ),
        )
        for spec in _CAPABILITY_SPECS
    ]
    categories = list(dict.fromkeys(spec.category for spec in _CAPABILITY_SPECS))
    payload = {
        "contractVersion": PROFESSIONAL_DATA_CAPABILITY_CONTRACT_VERSION,
        "consumerSafe": not include_admin_diagnostics,
        "summary": _summary(capabilities),
        "categories": categories,
        "capabilities": capabilities,
        "crossAssetDriverReadiness": build_cross_asset_driver_readiness().to_dict(),
    }
    if include_admin_diagnostics:
        payload["macroReadiness"] = macro_readiness
    return payload


__all__ = [
    "PROFESSIONAL_DATA_CAPABILITY_CONTRACT_VERSION",
    "build_professional_data_capability_registry",
]
