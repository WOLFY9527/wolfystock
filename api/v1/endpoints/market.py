# -*- coding: utf-8 -*-
"""Realtime market data endpoints for crypto and sentiment panels."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from api.deps import CurrentUser, get_optional_current_user
from api.v1.schemas.market_rotation import MarketRotationRadarResponse
from src.services.crypto_realtime_service import get_crypto_realtime_service
from src.services.market_overview_service import MarketOverviewService
from src.services.market_rotation_radar_service import MarketRotationRadarService
from src.services.rotation_radar_quote_provider import get_rotation_radar_quote_provider

router = APIRouter()


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


@router.get("/crypto", summary="Get realtime crypto market snapshot")
def get_crypto(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_crypto(actor=_actor(current_user))


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
        initial_payload = realtime_service.get_snapshot() or MarketOverviewService().get_crypto(actor=actor)
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
    return MarketOverviewService().get_market_sentiment(actor=_actor(current_user))


@router.get("/cn-indices", summary="Get China and Hong Kong index snapshot")
def get_cn_indices(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_cn_indices(actor=_actor(current_user))


@router.get("/cn-breadth", summary="Get China market breadth snapshot")
def get_cn_breadth(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_cn_breadth(actor=_actor(current_user))


@router.get("/cn-flows", summary="Get China and Hong Kong capital flow snapshot")
def get_cn_flows(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_cn_flows(actor=_actor(current_user))


@router.get("/sector-rotation", summary="Get sector and theme rotation snapshot")
def get_sector_rotation(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_sector_rotation(actor=_actor(current_user))


@router.get("/rotation-radar", response_model=MarketRotationRadarResponse, summary="Get theme rotation radar")
def get_rotation_radar(
    market: str = Query("US", description="Rotation taxonomy market: US, CN, HK, or CRYPTO"),
    current_user: Optional[CurrentUser] = Depends(get_optional_current_user),
):
    return MarketRotationRadarService(
        quote_provider=get_rotation_radar_quote_provider(),
    ).get_rotation_radar(market=market)


@router.get("/us-breadth", summary="Get US sector ETF breadth proxy snapshot")
def get_us_breadth(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_us_breadth(actor=_actor(current_user))


@router.get("/rates", summary="Get global rates and bond market snapshot")
def get_rates(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_rates(actor=_actor(current_user))


@router.get("/fx-commodities", summary="Get FX and commodities snapshot")
def get_fx_commodities(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_fx_commodities(actor=_actor(current_user))


@router.get("/temperature", summary="Get computed market temperature scores")
def get_temperature(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_market_temperature(actor=_actor(current_user))


@router.get("/market-briefing", summary="Get rule-based market briefing")
def get_market_briefing(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_market_briefing(actor=_actor(current_user))


@router.get("/futures", summary="Get futures and premarket direction")
def get_futures(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_futures(actor=_actor(current_user))


@router.get("/cn-short-sentiment", summary="Get China short-term sentiment snapshot")
def get_cn_short_sentiment(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return MarketOverviewService().get_cn_short_sentiment(actor=_actor(current_user))
