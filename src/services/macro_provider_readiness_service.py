# -*- coding: utf-8 -*-
"""Provider-neutral macro readiness contract.

The contract intentionally models FRED as an expected provider category without
performing provider calls or exposing credential values.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from typing import Any


MACRO_PROVIDER_READINESS_CONTRACT_VERSION = "macro_provider_readiness_v1"
FRED_MACRO_PROVIDER_FLAG = "FRED_MACRO_PROVIDER_ENABLED"
FRED_API_KEY_ENV = "FRED_API_KEY"

_READINESS_STATES = {
    "available",
    "missing",
    "stale",
    "not_configured",
    "disabled_by_flag",
    "missing_env",
}


@dataclass(frozen=True, slots=True)
class _MacroCategorySpec:
    key: str
    label: str
    series_ids: tuple[str, ...]
    product_surfaces: tuple[str, ...]


_MACRO_CATEGORY_SPECS: tuple[_MacroCategorySpec, ...] = (
    _MacroCategorySpec(
        key="rates",
        label="Rates and policy rates",
        series_ids=("DGS2", "DGS10", "DGS30", "DFF", "SOFR", "T10Y2Y", "T10Y3M"),
        product_surfaces=("market_regime_readiness", "cross_asset_context"),
    ),
    _MacroCategorySpec(
        key="inflation",
        label="Inflation",
        series_ids=("CPIAUCSL", "PPIACO"),
        product_surfaces=("market_regime_readiness", "macro_context"),
    ),
    _MacroCategorySpec(
        key="labor",
        label="Labor market",
        series_ids=(),
        product_surfaces=("market_regime_readiness", "macro_context"),
    ),
    _MacroCategorySpec(
        key="growth",
        label="Growth",
        series_ids=(),
        product_surfaces=("market_regime_readiness", "macro_context"),
    ),
    _MacroCategorySpec(
        key="liquidity",
        label="Liquidity",
        series_ids=("WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"),
        product_surfaces=("market_regime_readiness", "liquidity_context"),
    ),
    _MacroCategorySpec(
        key="credit",
        label="Credit",
        series_ids=("BAMLH0A0HYM2",),
        product_surfaces=("market_regime_readiness", "credit_stress_context"),
    ),
    _MacroCategorySpec(
        key="usd_currency",
        label="USD and currency",
        series_ids=("DTWEXBGS",),
        product_surfaces=("market_regime_readiness", "cross_asset_context"),
    ),
    _MacroCategorySpec(
        key="recession",
        label="Recession indicators",
        series_ids=(),
        product_surfaces=("market_regime_readiness", "recession_context"),
    ),
)


def _truthy_env(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _has_env_value(env: Mapping[str, Any], name: str) -> bool:
    return bool(str(env.get(name) or "").strip())


def _normalize_series_state(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"available", "missing", "stale"} else "missing"


def _category_state(
    spec: _MacroCategorySpec,
    *,
    provider_state: str,
    series_states: Mapping[str, str],
) -> str:
    if provider_state in {"disabled_by_flag", "missing_env"}:
        return provider_state
    if not spec.series_ids:
        return "not_configured"
    states = [
        _normalize_series_state(series_states[series_id])
        for series_id in spec.series_ids
        if series_id in series_states
    ]
    if not states:
        return "not_configured"
    if "stale" in states:
        return "stale"
    if all(state == "available" for state in states) and len(states) == len(spec.series_ids):
        return "available"
    if all(state == "missing" for state in states):
        return "missing"
    return "missing"


def _provider_state(category_states: list[str]) -> str:
    if "disabled_by_flag" in category_states:
        return "disabled_by_flag"
    if "missing_env" in category_states:
        return "missing_env"
    if "stale" in category_states:
        return "stale"
    if any(state in {"missing", "not_configured"} for state in category_states):
        if any(state == "available" for state in category_states):
            return "stale"
        return "not_configured"
    if category_states and all(state == "available" for state in category_states):
        return "available"
    return "not_configured"


def _next_action(state: str) -> str:
    if state == "disabled_by_flag":
        return f"Enable {FRED_MACRO_PROVIDER_FLAG} before macro data can unlock product surfaces."
    if state == "missing_env":
        return f"Configure {FRED_API_KEY_ENV} for the disabled-by-default FRED macro provider category."
    if state == "not_configured":
        return "Map supported official macro series before using this category for conclusions."
    if state == "missing":
        return "Backfill or verify the required macro series before showing conclusions."
    if state == "stale":
        return "Refresh official macro observations before using this category for conclusions."
    return "No action required for readiness; keep freshness evidence current."


def _consumer_reason(state: str) -> str:
    if state == "available":
        return "Macro category is available for readiness gating only; no macro conclusion is generated by this contract."
    if state == "stale":
        return "Official macro evidence is stale, so no macro conclusion is generated."
    if state == "missing":
        return "Official macro evidence is missing, so no macro conclusion is generated."
    if state == "missing_env":
        return "Macro provider credentials are not configured, so no macro conclusion is generated."
    if state == "disabled_by_flag":
        return "Macro provider category is disabled by flag, so no macro conclusion is generated."
    return "Macro series are not configured, so no macro conclusion is generated."


def build_macro_provider_readiness_contract(
    *,
    env: Mapping[str, Any] | None = None,
    series_states: Mapping[str, str] | None = None,
    include_admin_diagnostics: bool = False,
) -> dict[str, Any]:
    """Return a safe macro provider readiness contract without provider calls."""

    runtime_env: Mapping[str, Any] = os.environ if env is None else env
    states = series_states or {}
    enabled = _truthy_env(runtime_env.get(FRED_MACRO_PROVIDER_FLAG))
    configured = _has_env_value(runtime_env, FRED_API_KEY_ENV)
    base_provider_state = (
        "disabled_by_flag"
        if not enabled
        else ("not_configured" if configured else "missing_env")
    )

    categories: list[dict[str, Any]] = []
    for spec in _MACRO_CATEGORY_SPECS:
        state = _category_state(
            spec,
            provider_state=base_provider_state,
            series_states=states,
        )
        item: dict[str, Any] = {
            "categoryKey": spec.key,
            "label": spec.label,
            "state": state,
            "seriesIds": list(spec.series_ids),
            "productSurfacesUnlocked": list(spec.product_surfaces) if state == "available" else [],
            "reason": _consumer_reason(state),
        }
        if include_admin_diagnostics:
            item["nextAction"] = _next_action(state)
        categories.append(item)

    provider_state = _provider_state([str(item["state"]) for item in categories])
    payload: dict[str, Any] = {
        "contractVersion": MACRO_PROVIDER_READINESS_CONTRACT_VERSION,
        "provider": {
            "providerKey": "fred",
            "providerLabel": "FRED macro provider category",
            "state": provider_state,
            "configured": configured,
            "enabled": bool(enabled and configured),
        },
        "networkCallsEnabled": False,
        "runtimeProviderCalls": False,
        "categories": categories,
    }
    if include_admin_diagnostics:
        payload["admin"] = {
            "requiredEnvVars": [FRED_API_KEY_ENV],
            "requiredFlags": [FRED_MACRO_PROVIDER_FLAG],
            "nextActions": sorted({str(item["nextAction"]) for item in categories}),
        }
    return payload


__all__ = [
    "FRED_API_KEY_ENV",
    "FRED_MACRO_PROVIDER_FLAG",
    "MACRO_PROVIDER_READINESS_CONTRACT_VERSION",
    "build_macro_provider_readiness_contract",
]
