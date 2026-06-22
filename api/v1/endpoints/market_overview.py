# -*- coding: utf-8 -*-
"""Independent market overview APIs."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from api.deps import CurrentUser, get_optional_current_user
from src.services.consumer_issue_labels import sanitize_consumer_reason_payload
from src.services.consumer_api_diagnostic_redaction import project_consumer_api_payload
from src.services.market_overview_service import MarketOverviewService

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


def _consumer_safe_market_overview_payload(payload: Any, *, surface: str) -> Any:
    return project_consumer_api_payload(
        sanitize_consumer_reason_payload(payload),
        surface=surface,
    )


@router.get("/indices", summary="Get major US and CN index trends")
def get_indices(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_overview_payload(
        MarketOverviewService().get_indices(actor=_actor(current_user)),
        surface="market-overview-indices",
    )


@router.get("/volatility", summary="Get volatility indicators")
def get_volatility(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_overview_payload(
        MarketOverviewService().get_volatility(actor=_actor(current_user)),
        surface="market-overview-volatility",
    )


@router.get("/sentiment", summary="Get market sentiment indicators")
def get_sentiment(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_overview_payload(
        MarketOverviewService().get_sentiment(actor=_actor(current_user)),
        surface="market-overview-sentiment",
    )


@router.get("/funds-flow", summary="Get funds flow indicators")
def get_funds_flow(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_overview_payload(
        MarketOverviewService().get_funds_flow(actor=_actor(current_user)),
        surface="market-overview-funds-flow",
    )


@router.get("/macro", summary="Get macro indicators")
def get_macro(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_overview_payload(
        MarketOverviewService().get_macro(actor=_actor(current_user)),
        surface="market-overview-macro",
    )
