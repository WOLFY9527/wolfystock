# -*- coding: utf-8 -*-
"""Market scanner endpoints."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Type, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import (
    CurrentUser,
    get_current_user,
    get_current_user_id,
    get_database_manager,
    is_admin_user,
    require_admin_capability,
)
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.scanner import (
    ScannerOperationalStatusResponse,
    ScannerRunDetailResponse,
    ScannerRunHistoryResponse,
    ScannerRunRequest,
    ScannerStrategySimulationResponse,
    ScannerThemeGenerateRequest,
    ScannerThemeGenerationResponse,
    ScannerThemesResponse,
)
from src.core.scanner_theme_registry import create_ai_scanner_theme, list_scanner_themes
from src.services.market_scanner_ops_service import MarketScannerOperationsService
from src.services.market_scanner_service import MarketScannerService
from src.multi_user import OWNERSHIP_SCOPE_SYSTEM, OWNERSHIP_SCOPE_USER
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)
router = APIRouter()
ResponseT = TypeVar("ResponseT")


def _public_theme_payload(theme: object) -> dict[str, Any]:
    payload = theme.to_dict()
    if payload.get("source") == "ai_generated":
        label = str(payload.get("label_zh") or payload.get("label_en") or "").strip()
        payload["description"] = "AI-generated custom scanner theme. Review selections before running scanner."
        payload["aliases"] = [label] if label else []
        payload["criteria_prompt"] = None
        payload["ai_metadata"] = {
            key: value
            for key, value in dict(payload.get("ai_metadata") or {}).items()
            if key in {"status", "method", "catalog_key", "message"}
        }
    return payload


def _build_scanner_service(
    db_manager: DatabaseManager,
    current_user: CurrentUser | object | None,
) -> MarketScannerService:
    return MarketScannerService(db_manager, owner_id=get_current_user_id(current_user))


def _build_scanner_ops_service(
    db_manager: DatabaseManager,
    current_user: CurrentUser | object | None,
) -> MarketScannerOperationsService:
    return MarketScannerOperationsService(
        db_manager=db_manager,
        scanner_service=_build_scanner_service(db_manager, current_user),
        actor=_actor(current_user),
    )


def _actor(current_user: CurrentUser | object | None) -> dict | None:
    if current_user is None or not getattr(current_user, "user_id", None):
        return {"actor_type": "system", "role": "system", "display_name": "System"}
    return {
        "user_id": str(getattr(current_user, "user_id")),
        "username": str(getattr(current_user, "username", "") or ""),
        "display_name": getattr(current_user, "display_name", None),
        "role": "admin" if bool(getattr(current_user, "is_admin", False)) else "user",
        "actor_type": "admin" if bool(getattr(current_user, "is_admin", False)) else "user",
        "session_id": getattr(current_user, "session_id", None),
    }


def _validation_error(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "validation_error", "message": str(exc)},
    )


def _not_found_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "not_found", "message": message},
    )


def _internal_error(action_label: str, exc: Exception) -> HTTPException:
    logger.error("%s: %s", action_label, exc, exc_info=True)
    return HTTPException(
        status_code=500,
        detail={"error": "internal_error", "message": f"{action_label}: {str(exc)}"},
    )


def _run_endpoint(action_label: str, operation: Callable[[], ResponseT]) -> ResponseT:
    try:
        return operation()
    except HTTPException:
        raise
    except ValueError as exc:
        raise _validation_error(exc) from exc
    except Exception as exc:
        raise _internal_error(action_label, exc) from exc


def _get_run_detail_payload(
    *,
    service: MarketScannerService,
    run_id: int,
    current_user: CurrentUser | object | None,
) -> dict | None:
    payload = service.get_run_detail(run_id, scope=OWNERSHIP_SCOPE_USER)
    if payload is not None:
        return payload
    if is_admin_user(current_user):
        return service.get_run_detail(run_id, scope=OWNERSHIP_SCOPE_SYSTEM)
    return None


@router.post(
    "/run",
    response_model=ScannerRunDetailResponse,
    responses={
        200: {"description": "扫描完成"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="运行市场扫描器",
    description="按当前市场配置执行一次规则型 Market Scanner，并返回已持久化的观察名单结果。",
)
def run_market_scan(
    request: ScannerRunRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> ScannerRunDetailResponse:
    def _operation() -> ScannerRunDetailResponse:
        service = _build_scanner_ops_service(db_manager, current_user)
        payload = service.run_manual_scan(
            market=request.market,
            profile=request.profile,
            shortlist_size=request.shortlist_size,
            universe_limit=request.universe_limit,
            detail_limit=request.detail_limit,
            universe_type=request.universe_type,
            theme_id=request.theme_id,
            symbols=request.symbols,
            request_source="api",
            notify=False,
        )
        return ScannerRunDetailResponse(**payload)

    return _run_endpoint("运行市场扫描失败", _operation)


@router.get(
    "/themes",
    response_model=ScannerThemesResponse,
    responses={
        200: {"description": "Scanner theme universes"},
    },
    summary="获取 Scanner 主题标的池",
)
def get_scanner_themes(
    market: Optional[str] = Query(None, description="市场过滤"),
) -> ScannerThemesResponse:
    normalized_market = (market.strip().lower() if isinstance(market, str) else "") or None
    return ScannerThemesResponse(
        items=[_public_theme_payload(theme) for theme in list_scanner_themes(market=normalized_market)]
    )


@router.post(
    "/themes",
    response_model=ScannerThemeGenerationResponse,
    responses={
        200: {"description": "AI-generated custom scanner theme"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="创建 AI Scanner 自定义主题",
    description="根据用户输入的主题 criteria 生成一个可复核的自定义 scanner 标的池，并注册到当前运行时 theme registry。",
)
def create_scanner_theme(
    request: ScannerThemeGenerateRequest,
) -> ScannerThemeGenerationResponse:
    def _operation() -> ScannerThemeGenerationResponse:
        theme, suggestions = create_ai_scanner_theme(
            theme_id=request.id,
            label=request.label,
            market=request.market,
            prompt=request.prompt,
            manual_symbols=request.manual_symbols,
        )
        return ScannerThemeGenerationResponse(
            theme=_public_theme_payload(theme),
            suggestions=[suggestion.to_dict() for suggestion in suggestions],
            message=(
                f"Generated {len(suggestions)} symbols from AI theme criteria and federal/sector "
                "matching heuristics. Review selections before running scanner."
            ),
        )

    return _run_endpoint("创建 AI scanner theme 失败", _operation)


@router.get(
    "/runs",
    response_model=ScannerRunHistoryResponse,
    responses={
        200: {"description": "扫描历史"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取扫描历史",
)
def get_market_scan_runs(
    market: Optional[str] = Query("cn", description="市场过滤"),
    profile: Optional[str] = Query(None, description="扫描配置过滤"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(10, ge=1, le=50, description="每页数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> ScannerRunHistoryResponse:
    def _operation() -> ScannerRunHistoryResponse:
        service = _build_scanner_service(db_manager, current_user)
        payload = service.list_runs(
            market=market,
            profile=profile,
            page=page,
            limit=limit,
            scope=OWNERSHIP_SCOPE_USER,
        )
        return ScannerRunHistoryResponse(**payload)

    return _run_endpoint("查询扫描历史失败", _operation)


@router.get(
    "/strategy-simulation",
    response_model=ScannerStrategySimulationResponse,
    responses={
        200: {"description": "Scanner strategy historical simulation"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="Scanner 策略历史模拟",
    description="基于已持久化 scanner runs 评估同一 theme/profile/market 的历史入选候选 forward return；Phase 1 不主动生成历史扫描。",
)
def get_scanner_strategy_simulation(
    theme: Optional[str] = Query(None, description="Scanner theme id；为空时按 default universe 匹配"),
    profile: str = Query(..., description="扫描配置 key"),
    market: str = Query(..., description="市场"),
    lookback_days: int = Query(90, ge=1, le=365, description="历史扫描回看天数"),
    forward_days: int = Query(5, description="Forward holding days: 1 / 5 / 10 / 20"),
    limit: int = Query(50, ge=1, le=100, description="最多读取的历史 runs"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> ScannerStrategySimulationResponse:
    def _operation() -> ScannerStrategySimulationResponse:
        service = _build_scanner_service(db_manager, current_user)
        payload = service.build_strategy_simulation(
            theme=theme,
            profile=profile,
            market=market,
            lookback_days=lookback_days,
            forward_days=forward_days,
            limit=limit,
            scope=OWNERSHIP_SCOPE_USER,
        )
        return ScannerStrategySimulationResponse(**payload)

    return _run_endpoint("查询 Scanner 策略历史模拟失败", _operation)


@router.get(
    "/watchlists/today",
    response_model=ScannerRunDetailResponse,
    responses={
        200: {"description": "今日观察名单"},
        404: {"description": "今日尚无观察名单", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取今日观察名单",
)
def get_today_watchlist(
    market: Optional[str] = Query("cn", description="市场过滤"),
    profile: Optional[str] = Query(None, description="扫描配置过滤"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    _: CurrentUser = Depends(require_admin_capability("scanner:admin:read")),
) -> ScannerRunDetailResponse:
    def _operation() -> ScannerRunDetailResponse:
        service = _build_scanner_service(db_manager, None)
        payload = service.get_today_watchlist(
            market=market or "cn",
            profile=profile,
        )
        if payload is None:
            raise _not_found_error("今日尚无可用 watchlist")
        return ScannerRunDetailResponse(**payload)

    return _run_endpoint("查询今日观察名单失败", _operation)


@router.get(
    "/watchlists/recent",
    response_model=ScannerRunHistoryResponse,
    responses={
        200: {"description": "近期每日观察名单"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取近期每日观察名单",
)
def get_recent_watchlists(
    market: Optional[str] = Query("cn", description="市场过滤"),
    profile: Optional[str] = Query(None, description="扫描配置过滤"),
    limit_days: int = Query(7, ge=1, le=30, description="最近天数"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    _: CurrentUser = Depends(require_admin_capability("scanner:admin:read")),
) -> ScannerRunHistoryResponse:
    def _operation() -> ScannerRunHistoryResponse:
        service = _build_scanner_service(db_manager, None)
        payload = service.list_recent_watchlists(
            market=market or "cn",
            profile=profile,
            limit_days=limit_days,
        )
        return ScannerRunHistoryResponse(**payload)

    return _run_endpoint("查询近期观察名单失败", _operation)


@router.get(
    "/status",
    response_model=ScannerOperationalStatusResponse,
    responses={
        200: {"description": "Scanner 运行状态"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取 Scanner 运营状态",
)
def get_scanner_operational_status(
    market: Optional[str] = Query("cn", description="市场过滤"),
    profile: Optional[str] = Query(None, description="扫描配置过滤"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    _: CurrentUser = Depends(require_admin_capability("scanner:admin:read")),
) -> ScannerOperationalStatusResponse:
    def _operation() -> ScannerOperationalStatusResponse:
        service = _build_scanner_ops_service(db_manager, None)
        payload = service.get_operational_status(
            market=market or "cn",
            profile=profile,
        )
        return ScannerOperationalStatusResponse(**payload)

    return _run_endpoint("查询 Scanner 运营状态失败", _operation)


@router.get(
    "/runs/{run_id}",
    response_model=ScannerRunDetailResponse,
    responses={
        200: {"description": "扫描详情"},
        404: {"description": "未找到记录", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取单次扫描详情",
)
def get_market_scan_run(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> ScannerRunDetailResponse:
    def _operation() -> ScannerRunDetailResponse:
        service = _build_scanner_service(db_manager, current_user)
        payload = _get_run_detail_payload(
            service=service,
            run_id=run_id,
            current_user=current_user,
        )
        if payload is None:
            raise _not_found_error(f"未找到扫描记录 {run_id}")
        return ScannerRunDetailResponse(**payload)

    return _run_endpoint("查询扫描详情失败", _operation)
