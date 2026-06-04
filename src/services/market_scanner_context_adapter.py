# -*- coding: utf-8 -*-
"""Bounded scanner top-down context adapter.

This module only projects already-available in-process market metadata into the
scanner diagnostics envelope. It does not call scanner providers, mutate
caches, or change ranking/scoring semantics.
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from src.services.liquidity_monitor_service import LiquidityMonitorService
from src.services.market_cache import market_cache
from src.services.market_regime_synthesis_adapter import build_market_regime_synthesis_payload
from src.services.market_rotation_radar_service import (
    MarketRotationRadarService,
    _get_shared_rotation_radar_snapshot,
)
from src.services.rotation_radar_quote_provider import get_rotation_radar_quote_provider


TEMPERATURE_INPUT_SNAPSHOT_CACHE_KEY = "temperature_input_snapshot"
_FRESHNESS_PRIORITY = {
    "fresh": 0,
    "live": 0,
    "cached": 1,
    "delayed": 2,
    "partial": 3,
    "stale": 4,
    "fallback": 5,
    "synthetic": 6,
    "mock": 6,
    "unavailable": 7,
    "error": 8,
    "unknown": 9,
}

MarketTemperatureReader = Callable[[], Optional[Mapping[str, Any]]]
LiquidityContextReader = Callable[[], Optional[Mapping[str, Any]]]
RotationContextReader = Callable[[str], Optional[Mapping[str, Any]]]


def adapt_scanner_topdown_context_diagnostics(
    diagnostics: Optional[Mapping[str, Any]],
    *,
    market: str,
    read_market_temperature: MarketTemperatureReader | None = None,
    read_liquidity_context: LiquidityContextReader | None = None,
    read_rotation_context: RotationContextReader | None = None,
) -> Dict[str, Any]:
    """Additive-only top-down metadata merge for scanner diagnostics."""

    merged = copy.deepcopy(dict(diagnostics or {}))
    market_context = _mapping(
        merged.get("market_temperature")
        or merged.get("marketTemperature")
        or merged.get("market_overview")
        or merged.get("marketOverview")
        or merged.get("market_context")
        or merged.get("marketContext")
    )
    liquidity_context = _mapping(
        merged.get("liquidity_context")
        or merged.get("liquidityContext")
        or merged.get("liquidity_monitor")
        or merged.get("liquidityMonitor")
    )
    rotation_context = _mapping(
        merged.get("rotation_context")
        or merged.get("rotationContext")
        or merged.get("rotation_radar")
        or merged.get("rotationRadar")
    )

    if not _has_market_context(market_context):
        market_reader = read_market_temperature or _read_cached_market_temperature_context
        projected_market = _mapping(market_reader())
        if projected_market:
            merged["market_temperature"] = projected_market
            market_context = projected_market

    if not _has_liquidity_context(liquidity_context):
        liquidity_reader = read_liquidity_context or _read_cache_only_liquidity_context
        projected_liquidity = _mapping(liquidity_reader())
        if projected_liquidity:
            merged["liquidity_context"] = projected_liquidity
            liquidity_context = projected_liquidity

    if not _has_rotation_context(rotation_context):
        rotation_reader = read_rotation_context or _read_cached_rotation_context
        projected_rotation = _mapping(rotation_reader(str(market or "").lower()))
        if projected_rotation:
            merged["rotation_context"] = projected_rotation

    return merged


def _read_cached_market_temperature_context() -> Optional[Mapping[str, Any]]:
    entry = market_cache.get(TEMPERATURE_INPUT_SNAPSHOT_CACHE_KEY)
    if entry is None or not isinstance(entry.data, Mapping):
        return None

    raw_payload = copy.deepcopy(dict(entry.data))
    context = _normalize_market_temperature_context(raw_payload)
    if not context:
        return None

    if entry.expires_at <= datetime.now(entry.expires_at.tzinfo):
        freshness = _text(context.get("freshness")).lower()
        if freshness in {"", "cached", "delayed", "unknown"}:
            context["freshness"] = "stale"
    return context


def _normalize_market_temperature_context(value: Mapping[str, Any]) -> Dict[str, Any]:
    payload = copy.deepcopy(dict(value or {}))
    regime = _mapping(payload.get("marketRegimeSynthesis") or payload.get("regimeSummary"))
    if not regime:
        try:
            regime = _mapping(build_market_regime_synthesis_payload(payload))
        except Exception:
            regime = {}

    liquidity = _mapping(
        payload.get("capitalFlowSignal")
        or _mapping(payload.get("flows")).get("capitalFlowSignal")
        or _mapping(payload.get("liquidityContext")).get("capitalFlowSignal")
    )
    rotation = _sequence(
        payload.get("rotationFamilyRollup")
        or _mapping(payload.get("sectors")).get("rotationFamilyRollup")
    )
    if not any((regime, liquidity, rotation)):
        return {}

    freshness = _worst_freshness(
        [
            payload.get("freshness"),
            regime.get("freshness"),
            liquidity.get("freshness"),
            *[
                _mapping(item.get("themeFlowSignal")).get("freshness")
                for item in rotation
            ],
        ]
    )
    context: Dict[str, Any] = {
        "source": _infer_market_source(payload=payload, regime=regime, liquidity=liquidity),
        "freshness": freshness,
        "marketRegimeSynthesis": regime,
    }
    if liquidity:
        context["capitalFlowSignal"] = liquidity
    if rotation:
        context["rotationFamilyRollup"] = rotation
    return context


def _read_cache_only_liquidity_context() -> Optional[Mapping[str, Any]]:
    try:
        payload = LiquidityMonitorService(allow_external_provider_calls=False).get_liquidity_monitor()
    except Exception:
        return None

    if not isinstance(payload, Mapping):
        return None

    signal = _mapping(payload.get("capitalFlowSignal"))
    synthesis = _mapping(payload.get("liquidityImpulseSynthesis"))
    if not signal and not synthesis:
        return None
    if not _has_usable_liquidity_context(signal=signal, synthesis=synthesis):
        return None

    context: Dict[str, Any] = {
        "source": _text(signal.get("source") or synthesis.get("source") or "liquidity_monitor"),
        "freshness": _worst_freshness([signal.get("freshness"), synthesis.get("freshness"), _mapping(payload.get("freshness")).get("status")]),
    }
    if signal:
        context["capitalFlowSignal"] = signal
    if synthesis:
        context["liquidityImpulseSynthesis"] = synthesis
    return context


def _read_cached_rotation_context(market: str) -> Optional[Mapping[str, Any]]:
    if market != "us":
        return None
    service = MarketRotationRadarService(
        quote_provider=get_rotation_radar_quote_provider(),
        use_shared_cache=True,
    )
    cache_key = service._shared_snapshot_cache_key("US")
    if not cache_key:
        return None
    payload = _get_shared_rotation_radar_snapshot(cache_key)
    if not isinstance(payload, Mapping):
        return None
    consumer_snapshot = _mapping(payload.get("consumerEvidenceSnapshot"))
    if consumer_snapshot:
        return consumer_snapshot
    summary = _mapping(payload.get("summary"))
    if summary:
        return summary
    return None


def _has_market_context(value: Mapping[str, Any]) -> bool:
    payload = _mapping(value)
    return bool(
        payload.get("marketRegimeSynthesis")
        or payload.get("regimeSummary")
        or payload.get("capitalFlowSignal")
        or payload.get("rotationFamilyRollup")
    )


def _has_liquidity_context(value: Mapping[str, Any]) -> bool:
    payload = _mapping(value)
    return bool(payload.get("capitalFlowSignal") or payload.get("liquidityImpulseSynthesis"))


def _has_rotation_context(value: Mapping[str, Any]) -> bool:
    payload = _mapping(value)
    return bool(payload.get("rotationFamilyRollup") or payload.get("families"))


def _infer_market_source(
    *,
    payload: Mapping[str, Any],
    regime: Mapping[str, Any],
    liquidity: Mapping[str, Any],
) -> str:
    explicit = _text(payload.get("source"))
    if explicit:
        return explicit
    source_authority_allowed = bool(regime.get("sourceAuthorityAllowed")) and bool(liquidity.get("sourceAuthorityAllowed"))
    score_allowed = bool(regime.get("scoreContributionAllowed")) and bool(liquidity.get("scoreContributionAllowed"))
    freshness = _worst_freshness([payload.get("freshness"), regime.get("freshness"), liquidity.get("freshness")])
    if source_authority_allowed and score_allowed and freshness not in {"fallback", "stale", "unavailable", "unknown"}:
        return "computed"
    if freshness == "fallback":
        return "fallback"
    return "mixed"


def _has_usable_liquidity_context(
    *,
    signal: Mapping[str, Any],
    synthesis: Mapping[str, Any],
) -> bool:
    signal_freshness = _text(signal.get("freshness")).lower()
    signal_destination = _text(signal.get("likelyDestination")).lower()
    signal_regime = _text(signal.get("marketRegime")).lower()
    if _sequence(signal.get("sourceAssetPressure")):
        return True
    if signal_freshness in {"live", "fresh", "cached", "delayed", "partial", "stale", "fallback"}:
        return True
    if signal_destination not in {"", "no_clear_edge"}:
        return True
    if signal_regime not in {"", "insufficient_evidence", "mixed"}:
        return True

    impulse = _text(synthesis.get("liquidityImpulse")).lower()
    return impulse not in {"", "data_insufficient"}


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _worst_freshness(values: Sequence[Any]) -> str:
    resolved = [
        _text(value).lower()
        for value in values
        if _text(value).lower() in _FRESHNESS_PRIORITY
    ]
    if not resolved:
        return "unknown"
    return max(resolved, key=lambda item: _FRESHNESS_PRIORITY.get(item, 99))
