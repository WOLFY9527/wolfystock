# -*- coding: utf-8 -*-
"""Realtime market data endpoints for crypto and sentiment panels."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse

from api.deps import CurrentUser, get_optional_current_user, require_admin_capability
from api.v1.consumer_safe_response import consumer_safe_json_response
from api.v1.schemas.daily_intelligence import DailyIntelligenceBriefingResponse
from api.v1.schemas.data_source_gap_registry import DataSourceGapRegistryResponse
from api.v1.errors import safe_api_error
from api.v1.schemas.market_briefing import MarketOverviewBriefingResponse
from api.v1.schemas.market_scenario_lab import MarketScenarioLabRequest, MarketScenarioLabResponse
from api.v1.schemas.market_rotation import MarketRotationRadarResponse
from api.v1.schemas.market_temperature import MarketTemperatureConsumedSubsetResponse
from api.v1.schemas.professional_data_capabilities import (
    ProfessionalDataCapabilityRegistryAdminResponse,
    ProfessionalDataCapabilityRegistryResponse,
)
from src.services.cn_provider_health_service import CNProviderHealthService
from src.services.consumer_api_diagnostic_redaction import (
    sanitize_consumer_field_reference,
)
from src.services.crypto_realtime_service import get_crypto_realtime_service
from src.services.consumer_issue_labels import sanitize_consumer_reason_payload
from src.services.data_source_gap_registry_service import build_data_source_gap_registry
from src.services.market_scenario_lab_engine import build_market_scenario_lab
from src.services.market_decision_cockpit_service import MarketDecisionCockpitService
from src.services.market_data_readiness_diagnostics import build_market_data_readiness_diagnostics
from src.services.market_overview_service import MarketOverviewService
from src.services.market_regime_evidence_service import (
    DEFAULT_BENCHMARK_SYMBOL,
    DEFAULT_GROWTH_PROXY_SYMBOL,
    DEFAULT_MARKET_REGIME_SYMBOLS,
    DEFAULT_REQUIRED_BARS,
    MARKET_REGIME_EVIDENCE_CONTRACT_VERSION,
)
from src.services.market_regime_read_model_service import (
    build_market_regime_read_model,
    build_market_regime_read_model_from_evidence,
)
from src.services.market_rotation_radar_service import MarketRotationRadarService
from src.services.professional_data_capability_registry_service import (
    build_professional_data_capability_registry,
)
from src.services.provider_fit_advisor_service import build_provider_fit_advisor_snapshot
from src.services.rotation_radar_quote_provider import get_rotation_radar_quote_provider
from src.services.daily_intelligence_service import DailyIntelligenceService
from src.services.us_history_helper import get_us_stock_parquet_dir

router = APIRouter()
_MAX_DATA_READINESS_SYMBOLS = 8
_MAX_DATA_READINESS_SYMBOL_LENGTH = 24
_MAX_REGIME_READ_MODEL_SYMBOLS = 8
_MAX_REGIME_READ_MODEL_SYMBOL_LENGTH = 16
_MARKET_CONSUMER_DIAGNOSTIC_KEYS = frozenset(
    {
        "activationhint",
        "admindiagnostics",
        "apikeypresent",
        "attemptedat",
        "cabundlesource",
        "cachekey",
        "calendarassumption",
        "credential",
        "credentialfieldsmissing",
        "credentialsource",
        "credentialspresent",
        "credentials",
        "diagnosticonly",
        "endpointhost",
        "exceptionchain",
        "exceptionclass",
        "freshnesspolicy",
        "maxacceptedbusinesslagdays",
        "maxacceptedlagdays",
        "officialoverlayfailuredetails",
        "providerattempted",
        "providerclass",
        "providerdiagnostics",
        "providername",
        "rawpayload",
        "rawproviderpayload",
        "requestid",
        "requestwindowresults",
        "requiredproviderclass",
        "requestedseries",
        "sourceauthorityrouter",
        "timeoutseconds",
        "traceid",
    }
)
_MARKET_SENSITIVE_TEXT_RE = re.compile(
    r"\b(?:providerName|providerClass|providerAttempted|requiredProviderClass|endpointHost|"
    r"apiKeyPresent|requestId|traceId|cacheKey|rawPayload|raw_provider_payload|missing[_-]?api[_-]?key|"
    r"api[_-]?key|credentials?|token|password|secret|private[_-]?key|\benv\b|traceback)\b",
    re.IGNORECASE,
)


def _actor(current_user: Optional[CurrentUser]) -> Optional[Dict[str, Any]]:
    if current_user is None or not hasattr(current_user, "user_id"):
        return {"actor_type": "anonymous", "role": "anonymous", "display_name": "Anonymous"}
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "role": current_user.role,
        "actor_type": "admin" if current_user.is_admin else "user",
        "session_id": current_user.session_id,
    }


def _parse_data_readiness_symbols(raw_symbols: Optional[str]) -> tuple[str, ...]:
    if not raw_symbols:
        return ()

    allowed_punctuation = {".", "-", "_"}
    normalized: list[str] = []
    for raw_symbol in raw_symbols.split(","):
        cleaned = "".join(
            character
            for character in raw_symbol.strip().upper()
            if character.isalnum() or character in allowed_punctuation
        )
        if not cleaned:
            continue
        normalized.append(cleaned[:_MAX_DATA_READINESS_SYMBOL_LENGTH])
        if len(normalized) >= _MAX_DATA_READINESS_SYMBOLS:
            break

    return tuple(dict.fromkeys(normalized))


def _parse_regime_read_model_symbols(raw_symbols: Optional[str]) -> list[str]:
    if not raw_symbols:
        return list(DEFAULT_MARKET_REGIME_SYMBOLS)

    allowed_punctuation = {".", "-", "_"}
    normalized: list[str] = []
    for raw_symbol in raw_symbols.split(","):
        cleaned = "".join(
            character
            for character in raw_symbol.strip().upper()
            if character.isalnum() or character in allowed_punctuation
        )
        if not cleaned:
            continue
        normalized.append(cleaned[:_MAX_REGIME_READ_MODEL_SYMBOL_LENGTH])
        if len(normalized) >= _MAX_REGIME_READ_MODEL_SYMBOLS:
            break

    return list(dict.fromkeys(normalized)) or list(DEFAULT_MARKET_REGIME_SYMBOLS)


def _safe_local_path(value: Optional[str], *, default: Path | None = None) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return default
    if "\x00" in raw or re.match(r"^[a-z][a-z0-9+.-]*://", raw, flags=re.IGNORECASE):
        return default
    return Path(raw).expanduser()


def _bounded_required_bars(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_REQUIRED_BARS
    return min(max(parsed, 20), 260)


def _failed_closed_regime_read_model(
    *,
    market: str,
    symbols: list[str],
    benchmark_symbol: str,
    growth_proxy_symbol: str,
    required_bars: int,
    require_adjusted: bool,
) -> dict[str, Any]:
    source = {
        "consumerSafe": True,
        "contractVersion": MARKET_REGIME_EVIDENCE_CONTRACT_VERSION,
        "status": "failed_closed",
        "market": "US" if str(market or "").strip().upper() == "US" else "UNKNOWN",
        "symbols": list(symbols),
        "benchmarkSymbol": benchmark_symbol,
        "growthProxySymbol": growth_proxy_symbol,
        "requiredBars": required_bars,
        "requireAdjusted": require_adjusted,
        "missingDataFamilies": ["historical_ohlcv"],
        "blockedProductSurfaces": ["Market Overview", "Research"],
        "nextOperatorAction": "Provide readable local evidence inputs, then rerun the read model.",
        "evidence": {},
        "regimeSummary": {"label": "insufficient_data", "status": "failed_closed"},
        "symbolEvidence": {},
        "quoteSnapshotEvidence": {},
        "dataQuality": {
            "missingBars": {},
            "missingAdjustedData": [],
            "missingQuoteSnapshot": list(symbols),
            "staleOrUnknownFreshness": list(symbols),
            "failClosedReasons": ["source_unavailable"],
        },
        "networkCallsEnabled": False,
        "mutationEnabled": False,
        "providerCallsEnabled": False,
    }
    return build_market_regime_read_model_from_evidence(source)


def _consumer_safe_market_payload(payload: Any, *, surface: str) -> Any:
    _ = surface
    return _redact_market_consumer_diagnostics(
        sanitize_consumer_reason_payload(payload)
    )


def _redact_market_consumer_diagnostics(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
            if normalized in _MARKET_CONSUMER_DIAGNOSTIC_KEYS:
                continue
            if normalized in {"sourcetype", "sourcetier"} and isinstance(child, str):
                redacted[str(key)] = child
                continue
            if normalized == "sourcefield" and isinstance(child, str):
                redacted[str(key)] = sanitize_consumer_field_reference(child)
                continue
            projected_child = _redact_market_consumer_diagnostics(child)
            if normalized == "sourcefield" and isinstance(projected_child, str):
                redacted[str(key)] = sanitize_consumer_field_reference(projected_child)
                continue
            redacted[str(key)] = projected_child
        return redacted
    if isinstance(value, list):
        return [_redact_market_consumer_diagnostics(item) for item in value]
    if isinstance(value, str):
        if _MARKET_SENSITIVE_TEXT_RE.search(value):
            return "configuration_required"
        return value
    return value


@router.get("/crypto", summary="Get realtime crypto market snapshot")
def get_crypto(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_payload(
        MarketOverviewService().get_crypto(actor=_actor(current_user)),
        surface="market-crypto",
    )


def _sse_event(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/crypto/stream", summary="Stream realtime crypto market snapshot")
async def stream_crypto(
    request: Request,
    once: bool = False,
    current_user: Optional[CurrentUser] = Depends(get_optional_current_user),
):
    actor = _actor(current_user)
    realtime_service = get_crypto_realtime_service()

    async def events():
        last_payload_json: Optional[str] = None
        initial_payload = _consumer_safe_market_payload(
            realtime_service.get_snapshot() or MarketOverviewService().get_crypto(actor=actor),
            surface="market-crypto-stream",
        )
        last_payload_json = json.dumps(initial_payload, ensure_ascii=False, sort_keys=True)
        yield _sse_event(initial_payload)
        if once:
            return
        while not await request.is_disconnected():
            try:
                payload = await realtime_service.wait_for_snapshot(timeout_seconds=1.0)
                if payload is None:
                    await asyncio.sleep(1.0)
                    continue
                payload = _consumer_safe_market_payload(payload, surface="market-crypto-stream")
                payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                if payload_json == last_payload_json:
                    yield ": heartbeat\n\n"
                    continue
                last_payload_json = payload_json
                yield _sse_event(payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                yield ": heartbeat\n\n"
                await asyncio.sleep(1.0)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/sentiment", summary="Get realtime market sentiment snapshot")
def get_sentiment(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_payload(
        MarketOverviewService().get_market_sentiment(actor=_actor(current_user)),
        surface="market-sentiment",
    )


@router.get("/cn-indices", summary="Get China and Hong Kong index snapshot")
def get_cn_indices(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_payload(
        MarketOverviewService().get_cn_indices(actor=_actor(current_user)),
        surface="market-cn-indices",
    )


@router.get("/cn-breadth", summary="Get China market breadth snapshot")
def get_cn_breadth(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_payload(
        MarketOverviewService().get_cn_breadth(actor=_actor(current_user)),
        surface="market-cn-breadth",
    )


@router.get("/cn-flows", summary="Get China and Hong Kong capital flow snapshot")
def get_cn_flows(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_payload(
        MarketOverviewService().get_cn_flows(actor=_actor(current_user)),
        surface="market-cn-flows",
    )


@router.get("/sector-rotation", summary="Get sector and theme rotation snapshot")
def get_sector_rotation(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_payload(
        MarketOverviewService().get_sector_rotation(actor=_actor(current_user)),
        surface="market-sector-rotation",
    )


@router.get("/rotation-radar", response_model=MarketRotationRadarResponse, summary="Get theme rotation radar")
def get_rotation_radar(
    market: str = Query("US", description="Rotation taxonomy market: US, CN, HK, or CRYPTO"),
    current_user: Optional[CurrentUser] = Depends(get_optional_current_user),
):
    payload = MarketRotationRadarService(
        quote_provider=get_rotation_radar_quote_provider(),
        use_shared_cache=True,
    ).get_rotation_radar(market=market)
    return JSONResponse(
        content=jsonable_encoder(_redact_market_consumer_diagnostics(payload))
    )


@router.get("/us-breadth", summary="Get US market breadth snapshot")
def get_us_breadth(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_payload(
        MarketOverviewService().get_us_breadth(actor=_actor(current_user)),
        surface="market-us-breadth",
    )


@router.get("/rates", summary="Get global rates and bond market snapshot")
def get_rates(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_payload(
        MarketOverviewService().get_rates(actor=_actor(current_user)),
        surface="market-rates",
    )


@router.get("/fx-commodities", summary="Get FX and commodities snapshot")
def get_fx_commodities(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_payload(
        MarketOverviewService().get_fx_commodities(actor=_actor(current_user)),
        surface="market-fx-commodities",
    )


@router.get(
    "/temperature",
    response_model=MarketTemperatureConsumedSubsetResponse,
    response_model_exclude_unset=True,
    summary="Get computed market temperature scores",
)
def get_temperature(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_market_temperature(actor=_actor(current_user))


@router.get("/regime-decision", summary="Get deterministic market regime decision")
def get_regime_decision(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_payload(
        MarketOverviewService().get_market_regime_decision(actor=_actor(current_user)),
        surface="market-regime-decision",
    )


@router.get("/regime-read-model", summary="Get read-only market regime evidence read model")
def get_regime_read_model(
    market: str = Query("US", description="Market code for the bounded read model universe."),
    symbols: Optional[str] = Query(
        default=None,
        description="Optional comma-separated symbols for local read-model evidence.",
    ),
    benchmark_symbol: str = Query(DEFAULT_BENCHMARK_SYMBOL, alias="benchmarkSymbol"),
    growth_proxy_symbol: str = Query(DEFAULT_GROWTH_PROXY_SYMBOL, alias="growthProxySymbol"),
    required_bars: int = Query(DEFAULT_REQUIRED_BARS, alias="requiredBars", ge=20, le=260),
    require_adjusted: bool = Query(True, alias="requireAdjusted"),
    ohlcv_cache_dir: Optional[str] = Query(
        default=None,
        alias="ohlcvCacheDir",
        description="Optional local OHLCV parquet cache directory. The resolved path is not returned.",
    ),
    quote_snapshot_cache_path: Optional[str] = Query(
        default=None,
        alias="quoteSnapshotCachePath",
        description="Optional local quote snapshot JSON path. The resolved path is not returned.",
    ),
    quote_max_age_seconds: int = Query(60 * 60 * 24, alias="quoteMaxAgeSeconds", ge=1, le=60 * 60 * 24 * 30),
) -> JSONResponse:
    requested_symbols = _parse_regime_read_model_symbols(symbols)
    benchmark = _parse_regime_read_model_symbols(benchmark_symbol)[0]
    growth_proxy = _parse_regime_read_model_symbols(growth_proxy_symbol)[0]
    bounded_required_bars = _bounded_required_bars(required_bars)
    try:
        payload = build_market_regime_read_model(
            market=market,
            symbols=requested_symbols,
            benchmark_symbol=benchmark,
            growth_proxy_symbol=growth_proxy,
            required_bars=bounded_required_bars,
            ohlcv_cache_dir=_safe_local_path(ohlcv_cache_dir, default=get_us_stock_parquet_dir()),
            quote_snapshot_cache_path=_safe_local_path(quote_snapshot_cache_path),
            require_adjusted=require_adjusted,
            quote_max_age_seconds=quote_max_age_seconds,
        )
    except Exception:
        payload = _failed_closed_regime_read_model(
            market=market,
            symbols=requested_symbols,
            benchmark_symbol=benchmark,
            growth_proxy_symbol=growth_proxy,
            required_bars=bounded_required_bars,
            require_adjusted=require_adjusted,
        )
    return JSONResponse(
        content=jsonable_encoder(_consumer_safe_market_payload(payload, surface="market-regime-read-model"))
    )


@router.get("/decision-cockpit", summary="Get market decision cockpit aggregate")
def get_decision_cockpit(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return consumer_safe_json_response(
        sanitize_consumer_reason_payload(
            MarketDecisionCockpitService().get_decision_cockpit(actor=_actor(current_user))
        ),
        surface="market-decision-cockpit",
    )


@router.get(
    "/daily-intelligence",
    response_model=DailyIntelligenceBriefingResponse,
    response_model_exclude_none=True,
    summary="Get daily intelligence briefing aggregate",
)
def get_daily_intelligence(
    market: Optional[str] = Query(None, description="Optional scanner market filter"),
    profile: Optional[str] = Query(None, description="Optional scanner profile filter"),
    current_user: Optional[CurrentUser] = Depends(get_optional_current_user),
):
    owner_id = current_user.user_id if current_user is not None and hasattr(current_user, "user_id") else None
    return DailyIntelligenceService().build_briefing(
        actor=_actor(current_user),
        owner_id=owner_id,
        market=market,
        profile=profile,
    )


@router.post(
    "/scenario-lab",
    response_model=MarketScenarioLabResponse,
    response_model_exclude_none=True,
    summary="Compare a market regime against bounded research-planning scenarios",
)
def post_scenario_lab(request: MarketScenarioLabRequest):
    try:
        return build_market_scenario_lab(
            base_decision=request.base_regime,
            driver_scores=request.driver_scores,
            scenario=request.to_engine_scenario(),
        )
    except ValueError as exc:
        raise safe_api_error(
            status_code=400,
            error="invalid_market_scenario_lab_request",
            message="Market scenario lab request could not be processed.",
        ) from exc


@router.get(
    "/market-briefing",
    response_model=MarketOverviewBriefingResponse,
    response_model_exclude_none=True,
    summary="Get rule-based market briefing",
)
def get_market_briefing(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    model = MarketOverviewBriefingResponse.model_validate(
        MarketOverviewService().get_market_briefing(actor=_actor(current_user))
    )
    return consumer_safe_json_response(model, surface="market-briefing", exclude_none=True)


@router.get("/futures", summary="Get futures and premarket direction")
def get_futures(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_payload(
        MarketOverviewService().get_futures(actor=_actor(current_user)),
        surface="market-futures",
    )


@router.get("/cn-short-sentiment", summary="Get China short-term sentiment snapshot")
def get_cn_short_sentiment(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_payload(
        MarketOverviewService().get_cn_short_sentiment(actor=_actor(current_user)),
        surface="market-cn-short-sentiment",
    )


@router.get("/cn-provider-health", summary="Get read-only CN provider health snapshot")
def get_cn_provider_health(
    force_refresh: bool = Query(default=False, alias="forceRefresh"),
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
) -> list[dict[str, Any]]:
    return [item.to_dict() for item in CNProviderHealthService().get_snapshot(force_refresh=force_refresh)]


@router.get(
    "/provider-fit-advisor",
    summary="Get deprecated admin-only provider-fit advisor snapshot",
    deprecated=True,
    include_in_schema=False,
)
def get_provider_fit_advisor(
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
) -> dict[str, Any]:
    return build_provider_fit_advisor_snapshot().to_dict()


@router.get("/data-readiness", summary="Get read-only local market data readiness diagnostics")
def get_market_data_readiness(
    symbols: Optional[str] = Query(
        default=None,
        description="Optional comma-separated representative symbols for local parquet file presence checks.",
    ),
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
) -> dict[str, Any]:
    return build_market_data_readiness_diagnostics(
        representative_symbols=_parse_data_readiness_symbols(symbols)
    ).to_dict()


@router.get(
    "/data-source-gap-registry",
    response_model=DataSourceGapRegistryResponse,
    summary="Get read-only data source gap registry",
)
def get_data_source_gap_registry(
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
) -> dict[str, Any]:
    return build_data_source_gap_registry()


@router.get(
    "/professional-data-capabilities",
    response_model=ProfessionalDataCapabilityRegistryResponse,
    summary="Get consumer-safe professional data capability registry",
)
def get_professional_data_capabilities() -> dict[str, Any]:
    return build_professional_data_capability_registry()


@router.get(
    "/professional-data-capabilities/admin",
    response_model=ProfessionalDataCapabilityRegistryAdminResponse,
    summary="Get admin-gated professional data capability diagnostics",
)
def get_professional_data_capabilities_admin(
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
) -> dict[str, Any]:
    return build_professional_data_capability_registry(
        include_admin_diagnostics=True
    )
