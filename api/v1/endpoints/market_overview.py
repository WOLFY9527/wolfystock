# -*- coding: utf-8 -*-
"""Independent market overview APIs."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from api.deps import CurrentUser, get_optional_current_user
from src.services.consumer_issue_labels import sanitize_consumer_reason_payload
from src.services.consumer_api_diagnostic_redaction import project_consumer_api_payload
from src.services.market_overview_service import MarketOverviewService
from src.services.market_regime_read_model_service import (
    build_market_regime_read_model,
    project_market_regime_evidence,
)
from src.services.quote_snapshot_config import get_configured_us_quote_snapshot_cache_path
from src.services.us_history_helper import get_configured_us_stock_parquet_dir

router = APIRouter()
_DEFAULT_MARKET_OVERVIEW_PANEL_ORDER = (
    ("indices", "get_indices"),
    ("volatility", "get_volatility"),
    ("sentiment", "get_sentiment"),
    ("fundsFlow", "get_funds_flow"),
    ("macro", "get_macro"),
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


def _consumer_safe_market_overview_payload(payload: Any, *, surface: str) -> Any:
    return project_consumer_api_payload(
        sanitize_consumer_reason_payload(payload),
        surface=surface,
    )


def _aggregate_market_overview_status(panels: Dict[str, Any]) -> str:
    statuses = {
        str(panel.get("status") or "").strip().lower()
        for panel in panels.values()
        if isinstance(panel, dict)
    }
    if not statuses:
        return "unavailable"
    if statuses <= {"success"}:
        return "success"
    if statuses & {"success", "partial"}:
        return "partial"
    if statuses & {"failure", "unavailable", "error"}:
        return "unavailable"
    return "partial"


def _build_market_overview_payload(
    service: MarketOverviewService,
    *,
    actor: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    panels: Dict[str, Any] = {}
    for payload_key, method_name in _DEFAULT_MARKET_OVERVIEW_PANEL_ORDER:
        panels[payload_key] = getattr(service, method_name)(actor=actor)
    return {
        "status": _aggregate_market_overview_status(panels),
        "regimeEvidenceProjection": _build_market_regime_evidence_projection(),
        "panels": panels,
        **panels,
    }


def _build_market_regime_evidence_projection() -> Dict[str, Any]:
    try:
        read_model = build_market_regime_read_model(
            market="US",
            ohlcv_cache_dir=get_configured_us_stock_parquet_dir(),
            quote_snapshot_cache_path=get_configured_us_quote_snapshot_cache_path(),
        )
        projection = read_model.get("regimeEvidenceProjection")
        if isinstance(projection, dict):
            return projection
    except Exception:
        pass
    return project_market_regime_evidence(None)


@router.get("", summary="Get aggregate market overview")
def get_market_overview(current_user: Optional[CurrentUser] = Depends(get_optional_current_user)):
    return _consumer_safe_market_overview_payload(
        _build_market_overview_payload(
            MarketOverviewService(),
            actor=_actor(current_user),
        ),
        surface="market-overview",
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
