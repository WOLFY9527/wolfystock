# -*- coding: utf-8 -*-
"""Admin-only market provider operations APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from api.deps import CurrentUser, require_admin_capability
from api.v1.schemas.market_provider_operations import MarketProviderOperationsResponse
from src.services.historical_ohlcv_cache_preflight import HistoricalOhlcvCachePreflightService
from src.services.market_provider_operations_service import MarketProviderOperationsService
from src.services.provider_activation_verifier import ProviderActivationVerifierService

router = APIRouter()


def _project_market_provider_operations_compatibility_payload(value: Any, *, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        projected: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            normalized_key = key_text.replace("_", "").lower()
            if normalized_key in {"cachekey", "rawcachekey"}:
                continue
            if parent_key == "summaryCache" and key_text == "key":
                continue
            if key_text == "providerDiagnostics":
                continue
            projected[key_text] = _project_market_provider_operations_compatibility_payload(
                item,
                parent_key=key_text,
            )
        return projected
    if isinstance(value, list):
        return [_project_market_provider_operations_compatibility_payload(item, parent_key=parent_key) for item in value]
    return value


@router.get(
    "/market-providers/operations",
    response_model=MarketProviderOperationsResponse,
    summary="Get read-only market provider operations status",
)
def get_market_provider_operations(
    window: str = Query(default="24h", description="Relative window: 15m, 1h, 24h, or 7d"),
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
):
    return MarketProviderOperationsService().get_operations(window=window)


@router.get(
    "/market-provider-operations",
    summary="Get read-only market provider operations status",
)
def get_market_provider_operations_compatibility(
    window: str = Query(default="24h", description="Relative window: 15m, 1h, 24h, or 7d"),
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
):
    return _project_market_provider_operations_compatibility_payload(
        MarketProviderOperationsService().get_operations(window=window)
    )


@router.get(
    "/provider-activation-verifier",
    summary="Get operator-only provider activation readiness verifier",
)
def get_provider_activation_verifier(
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
):
    return ProviderActivationVerifierService().verify()


def get_historical_ohlcv_cache_preflight_service() -> HistoricalOhlcvCachePreflightService:
    return HistoricalOhlcvCachePreflightService()


@router.get(
    "/historical-ohlcv/cache-preflight",
    summary="Get dry-run historical OHLCV cache preflight",
)
def get_historical_ohlcv_cache_preflight(
    cn_symbols: str | None = Query(default=None, description="Comma-separated CN representative symbols."),
    us_symbols: str | None = Query(default=None, description="Comma-separated US representative symbols."),
    required_bars: int = Query(default=60, ge=1, le=500),
    require_adjusted: bool = Query(default=True),
    service: HistoricalOhlcvCachePreflightService = Depends(get_historical_ohlcv_cache_preflight_service),
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
):
    return service.preflight(
        symbols_by_market=_parse_query_symbols_by_market(cn_symbols=cn_symbols, us_symbols=us_symbols),
        required_bars=required_bars,
        require_adjusted=require_adjusted,
        dry_run=True,
    )


@router.post(
    "/historical-ohlcv/cache-preflight/seed",
    summary="Run historical OHLCV cache seed preflight or explicit seed",
)
def seed_historical_ohlcv_cache(
    body: dict[str, Any],
    service: HistoricalOhlcvCachePreflightService = Depends(get_historical_ohlcv_cache_preflight_service),
    read_user: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
):
    dry_run = bool(body.get("dryRun", True))
    if not dry_run:
        require_admin_capability("ops:providers:write")(read_user)
    return service.seed(
        symbols_by_market={
            "cn": _parse_body_symbols(body, "cnSymbols"),
            "us": _parse_body_symbols(body, "usSymbols"),
        },
        required_bars=_bounded_int(body.get("requiredBars"), default=60, minimum=1, maximum=500),
        require_adjusted=bool(body.get("requireAdjusted", True)),
        dry_run=dry_run,
    )


def _parse_body_symbols(body: dict[str, Any], key: str) -> list[str]:
    value = body.get(key)
    if isinstance(value, str):
        return _parse_symbol_list(value)
    if isinstance(value, list):
        return [str(item or "").strip().upper() for item in value if str(item or "").strip()]
    return []


def _parse_query_symbols_by_market(*, cn_symbols: str | None, us_symbols: str | None) -> dict[str, list[str]] | None:
    if cn_symbols is None and us_symbols is None:
        return None
    return {
        "cn": _parse_symbol_list(cn_symbols) if cn_symbols is not None else [],
        "us": _parse_symbol_list(us_symbols) if us_symbols is not None else [],
    }


def _parse_symbol_list(value: str | None) -> list[str]:
    if not value:
        return []
    symbols = []
    for item in value.split(","):
        symbol = str(item or "").strip().upper()
        if symbol:
            symbols.append(symbol)
    return list(dict.fromkeys(symbols))


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(maximum, max(minimum, parsed))
