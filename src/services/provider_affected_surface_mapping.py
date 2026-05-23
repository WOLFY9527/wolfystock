# -*- coding: utf-8 -*-
"""Canonical product-surface mapping for provider diagnostics.

This layer projects internal affected-surface aliases into a narrow safe list
of product-facing surfaces for UI checklist usage. Unknown or purely internal
aliases fall back to Provider Ops / system diagnostics.
"""

from __future__ import annotations

from typing import Sequence


_CANONICAL_SURFACE_BY_ALIAS = {
    "backtest": "backtest",
    "liquidity_impulse": "liquidity_monitor",
    "liquidity_monitor": "liquidity_monitor",
    "market_overview": "market_overview",
    "options_lab": "options_lab",
    "portfolio": "portfolio",
    "provider_ops": "provider_ops",
    "rotation_radar": "rotation_radar",
    "scanner": "scanner",
    "scanner_diagnostics": "scanner",
    "stock_history": "provider_ops",
    "system_diagnostics": "provider_ops",
}
_EXPLICIT_PROVIDER_OPS_ALIASES = {"provider_ops", "stock_history", "system_diagnostics"}
_CANONICAL_SURFACE_ORDER = (
    "market_overview",
    "liquidity_monitor",
    "rotation_radar",
    "scanner",
    "portfolio",
    "options_lab",
    "backtest",
    "provider_ops",
)


def canonical_product_affected_surfaces(
    surfaces: Sequence[str] | None,
) -> tuple[str, ...]:
    """Return a deduplicated safe product-surface list.

    The output is intentionally narrow. Unknown aliases degrade to
    ``provider_ops`` rather than guessing at another user-facing surface.
    """

    resolved: list[str] = []
    explicit_provider_ops = False
    saw_unknown = False
    for surface in surfaces or ():
        alias = str(surface or "").strip().lower()
        if not alias:
            continue
        if alias not in _CANONICAL_SURFACE_BY_ALIAS:
            saw_unknown = True
            continue
        canonical = _CANONICAL_SURFACE_BY_ALIAS[alias]
        if alias in _EXPLICIT_PROVIDER_OPS_ALIASES:
            explicit_provider_ops = True
        if canonical not in resolved:
            resolved.append(canonical)
    if saw_unknown and not resolved:
        resolved.append("provider_ops")
    elif saw_unknown and explicit_provider_ops and "provider_ops" not in resolved:
        resolved.append("provider_ops")
    if not resolved:
        return ("provider_ops",)
    return tuple(
        surface for surface in _CANONICAL_SURFACE_ORDER if surface in resolved
    )


__all__ = ["canonical_product_affected_surfaces"]
