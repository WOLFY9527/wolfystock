# -*- coding: utf-8 -*-
"""Backtest endpoints."""

from __future__ import annotations

import logging
from typing import Callable, Optional, Type, TypeVar

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response

from api.deps import CurrentUser, get_current_user, get_current_user_id, get_database_manager
from api.v1.schemas.backtest import (
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestRunHistoryResponse,
    BacktestSampleStatusResponse,
    BacktestClearResponse,
    BacktestCodeRequest,
    BacktestResultItem,
    BacktestResultsResponse,
    PerformanceMetrics,
    PrepareBacktestSamplesRequest,
    PrepareBacktestSamplesResponse,
    RuleBacktestDetailResponse,
    RuleBacktestCompareRequest,
    RuleBacktestCompareResponse,
    RuleBacktestHistoryItem,
    RuleBacktestHistoryResponse,
    RuleBacktestStatusResponse,
    RuleBacktestCancelResponse,
    RuleBacktestExecutionTraceExportResponse,
    RuleBacktestRegimeAttributionReadinessExportResponse,
    RuleBacktestRobustnessEvidenceExportResponse,
    RuleBacktestSupportBundleManifestResponse,
    RuleBacktestSupportBundleReproducibilityManifestResponse,
    RuleBacktestSupportExportIndexResponse,
    RuleBacktestParseRequest,
    RuleBacktestParseResponse,
    RuleBacktestRunRequest,
    RuleBacktestRunResponse,
    RuleBacktestUniverseJobCreateRequest,
    RuleBacktestUniverseJobDiagnostics,
    RuleBacktestUniverseJobResponse,
    RuleBacktestUniverseResultsResponse,
)
from api.v1.schemas.common import ErrorResponse
from src.services.backtest_service import BacktestService
from src.services.rule_backtest_service import RuleBacktestService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)
router = APIRouter()
ResponseT = TypeVar("ResponseT")


def _build_backtest_service(
    db_manager: DatabaseManager,
    current_user: CurrentUser | object | None,
) -> BacktestService:
    return BacktestService(db_manager, owner_id=get_current_user_id(current_user))


def _build_rule_backtest_service(
    db_manager: DatabaseManager,
    current_user: CurrentUser | object | None,
) -> RuleBacktestService:
    return RuleBacktestService(db_manager, owner_id=get_current_user_id(current_user))


def _build_model(model_cls: Type[ResponseT], data: dict) -> ResponseT:
    return model_cls(**data)


def _build_models(model_cls: Type[ResponseT], items: list[dict]) -> list[ResponseT]:
    return [_build_model(model_cls, item) for item in items]


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


def _run_endpoint(
    action_label: str,
    operation: Callable[[], ResponseT],
    *,
    allow_validation_error: bool = False,
) -> ResponseT:
    try:
        return operation()
    except HTTPException:
        raise
    except ValueError as exc:
        if allow_validation_error:
            raise _validation_error(exc) from exc
        raise _internal_error(action_label, exc) from exc
    except Exception as exc:
        raise _internal_error(action_label, exc) from exc


def _requested_mode_for_code(code: Optional[str]) -> str:
    normalized_code = str(code or "").strip().upper()
    if normalized_code and normalized_code.isascii() and normalized_code.isalpha():
        return "local_first"
    return "auto"


def _build_rule_run_performance_fallback(
    *,
    rule_service: RuleBacktestService,
    scope: str,
    code: Optional[str],
    eval_window_days: Optional[int],
) -> dict | None:
    payload = rule_service.list_runs(code=code, page=1, limit=100)
    items = payload.get("items", []) if isinstance(payload, dict) else []
    completed_runs = [
        item for item in items
        if isinstance(item, dict) and str(item.get("status") or "").strip().lower() == "completed"
    ]
    if not completed_runs:
        return None

    total_returns = [
        float(item["total_return_pct"])
        for item in completed_runs
        if item.get("total_return_pct") is not None
    ]
    win_count = sum(1 for value in total_returns if value > 0)
    loss_count = sum(1 for value in total_returns if value < 0)
    neutral_count = sum(1 for value in total_returns if value == 0)
    completed_count = len(completed_runs)
    win_rate_pct = round((win_count / completed_count) * 100.0, 4) if completed_count else None
    avg_return_pct = round(sum(total_returns) / len(total_returns), 4) if total_returns else None
    computed_at = max(
        (
            str(item.get("completed_at") or item.get("run_at"))
            for item in completed_runs
            if item.get("completed_at") or item.get("run_at")
        ),
        default=None,
    )

    return {
        "scope": scope,
        "code": code,
        "eval_window_days": int(eval_window_days or 10),
        "evaluation_window_trading_bars": int(eval_window_days or 10),
        "engine_version": "rule_deterministic_v1",
        "computed_at": computed_at,
        "total_evaluations": completed_count,
        "completed_count": completed_count,
        "insufficient_count": 0,
        "long_count": completed_count,
        "cash_count": 0,
        "win_count": win_count,
        "loss_count": loss_count,
        "neutral_count": neutral_count,
        "direction_accuracy_pct": win_rate_pct,
        "win_rate_pct": win_rate_pct,
        "neutral_rate_pct": round((neutral_count / completed_count) * 100.0, 4) if completed_count else None,
        "avg_stock_return_pct": avg_return_pct,
        "avg_simulated_return_pct": avg_return_pct,
        "stop_loss_trigger_rate": None,
        "take_profit_trigger_rate": None,
        "ambiguous_rate": None,
        "avg_days_to_first_hit": None,
        "advice_breakdown": {
            "rule_runs_completed": completed_count,
            "rule_runs_positive": win_count,
            "rule_runs_negative": loss_count,
            "rule_runs_neutral": neutral_count,
        },
        "diagnostics": {
            "source": "rule_backtest_runs_fallback",
            "fallback_reason": "standard_backtest_summary_missing",
            "sample_run_ids": [item.get("id") for item in completed_runs[:10]],
        },
        "evaluation_mode": "rule_deterministic_fallback",
        "requested_mode": _requested_mode_for_code(code),
        "resolved_source": "stored_rule_backtest_runs",
        "fallback_used": False,
        "execution_assumptions": {
            "source": "rule_backtest_runs",
            "mode": "stored_result_aggregate",
        },
    }


def _build_empty_performance_payload(
    *,
    scope: str,
    code: Optional[str],
    eval_window_days: Optional[int],
) -> dict:
    resolved_window = int(eval_window_days or 10)
    return {
        "scope": scope,
        "code": code,
        "eval_window_days": resolved_window,
        "evaluation_window_trading_bars": resolved_window,
        "engine_version": "v1",
        "computed_at": None,
        "total_evaluations": 0,
        "completed_count": 0,
        "insufficient_count": 0,
        "long_count": 0,
        "cash_count": 0,
        "win_count": 0,
        "loss_count": 0,
        "neutral_count": 0,
        "direction_accuracy_pct": None,
        "win_rate_pct": None,
        "neutral_rate_pct": None,
        "avg_stock_return_pct": None,
        "avg_simulated_return_pct": None,
        "stop_loss_trigger_rate": None,
        "take_profit_trigger_rate": None,
        "ambiguous_rate": None,
        "avg_days_to_first_hit": None,
        "advice_breakdown": {},
        "diagnostics": {
            "source": "empty_state",
            "reason": "no_backtest_data_for_current_user",
        },
        "evaluation_mode": "empty_state",
        "requested_mode": _requested_mode_for_code(code),
        "resolved_source": "no_backtest_data",
        "fallback_used": False,
        "execution_assumptions": {},
    }


# ------------------ 普通回测接口，使用 BacktestService ------------------

@router.post(
    "/run",
    response_model=BacktestRunResponse,
    responses={
        200: {"description": "历史分析评估执行完成"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="运行历史分析评估",
    description="对历史分析记录做事后信号评估，并写入 backtest_results/backtest_summaries",
)
def run_backtest(
    request: BacktestRunRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> BacktestRunResponse:
    def _operation() -> BacktestRunResponse:
        service = _build_backtest_service(db_manager, current_user)
        stats = service.run_backtest(
            code=request.code,
            force=request.force,
            eval_window_days=request.eval_window_days,
            min_age_days=request.min_age_days,
            limit=request.limit,
        )
        return BacktestRunResponse(**stats)
    return _run_endpoint("回测执行失败", _operation)


@router.post(
    "/prepare-samples",
    response_model=PrepareBacktestSamplesResponse,
    responses={
        200: {"description": "历史分析评估样本准备完成"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="准备历史分析评估样本",
    description="按股票代码准备可用于历史分析评估的分析样本，并持久化到 analysis_history。",
)
def prepare_backtest_samples(
    request: PrepareBacktestSamplesRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> PrepareBacktestSamplesResponse:
    def _operation() -> PrepareBacktestSamplesResponse:
        service = _build_backtest_service(db_manager, current_user)
        stats = service.prepare_backtest_samples(
            code=request.code,
            sample_count=request.sample_count,
            eval_window_days=request.eval_window_days,
            min_age_days=request.min_age_days,
            force_refresh=request.force_refresh,
        )
        return PrepareBacktestSamplesResponse(**stats)
    return _run_endpoint("准备回测样本失败", _operation, allow_validation_error=True)


@router.get(
    "/sample-status",
    response_model=BacktestSampleStatusResponse,
    responses={
        200: {"description": "样本状态"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取历史分析评估样本状态",
)
def get_sample_status(
    code: str = Query(..., description="股票代码"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> BacktestSampleStatusResponse:
    def _operation() -> BacktestSampleStatusResponse:
        service = _build_backtest_service(db_manager, current_user)
        data = service.get_sample_status(code=code)
        return BacktestSampleStatusResponse(**data)
    return _run_endpoint("查询回测样本状态失败", _operation, allow_validation_error=True)


@router.get(
    "/runs",
    response_model=BacktestRunHistoryResponse,
    responses={
        200: {"description": "回测历史"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取历史分析评估历史",
)
def get_backtest_runs(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> BacktestRunHistoryResponse:
    def _operation() -> BacktestRunHistoryResponse:
        service = _build_backtest_service(db_manager, current_user)
        data = service.list_backtest_runs(code=code, page=page, limit=limit)
        return BacktestRunHistoryResponse(**data)
    return _run_endpoint("查询回测历史失败", _operation)


@router.get(
    "/results",
    response_model=BacktestResultsResponse,
    responses={
        200: {"description": "回测结果列表"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取历史分析评估结果",
    description="分页获取历史分析评估结果，支持按股票代码过滤",
)
def get_backtest_results(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="评估窗口过滤"),
    run_id: Optional[int] = Query(None, ge=1, description="回测运行ID"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=200, description="每页数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> BacktestResultsResponse:
    def _operation() -> BacktestResultsResponse:
        service = _build_backtest_service(db_manager, current_user)
        if run_id is not None:
            data = service.get_run_results(run_id=run_id, limit=limit, page=page)
            if data is None:
                raise _not_found_error("回测记录不存在")
        else:
            data = service.get_recent_evaluations(code=code, eval_window_days=eval_window_days, limit=limit, page=page)
        items = [BacktestResultItem(**item) for item in data.get("items", [])]
        return BacktestResultsResponse(total=int(data.get("total", 0)), page=page, limit=limit, items=items)
    return _run_endpoint("查询回测结果失败", _operation)


@router.get(
    "/performance",
    response_model=PerformanceMetrics,
    responses={
        200: {"description": "总体表现指标"},
        404: {"description": "暂无可用统计", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取历史分析评估总体表现",
)
def get_backtest_performance(
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="评估窗口过滤"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> PerformanceMetrics:
    def _operation() -> PerformanceMetrics:
        service = _build_backtest_service(db_manager, current_user)
        data = service.get_global_summary(eval_window_days=eval_window_days)
        if data is None:
            rule_service = _build_rule_backtest_service(db_manager, current_user)
            data = _build_rule_run_performance_fallback(
                rule_service=rule_service,
                scope="overall",
                code=None,
                eval_window_days=eval_window_days,
            )
        if data is None:
            data = _build_empty_performance_payload(
                scope="overall",
                code=None,
                eval_window_days=eval_window_days,
            )
        return PerformanceMetrics(**data)
    return _run_endpoint("查询总体回测表现失败", _operation)


@router.get(
    "/performance/{code}",
    response_model=PerformanceMetrics,
    responses={
        200: {"description": "个股表现指标"},
        404: {"description": "暂无可用统计", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取单只股票的历史分析评估表现",
)
def get_backtest_stock_performance(
    code: str,
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="评估窗口过滤"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> PerformanceMetrics:
    def _operation() -> PerformanceMetrics:
        service = _build_backtest_service(db_manager, current_user)
        data = service.get_stock_summary(code, eval_window_days=eval_window_days)
        if data is None:
            rule_service = _build_rule_backtest_service(db_manager, current_user)
            data = _build_rule_run_performance_fallback(
                rule_service=rule_service,
                scope="stock",
                code=code,
                eval_window_days=eval_window_days,
            )
        if data is None:
            data = _build_empty_performance_payload(
                scope="stock",
                code=code,
                eval_window_days=eval_window_days,
            )
        return PerformanceMetrics(**data)
    return _run_endpoint("查询个股回测表现失败", _operation)


@router.post(
    "/samples/clear",
    response_model=BacktestClearResponse,
    responses={
        200: {"description": "回测样本已清理"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="清理历史分析评估样本",
)
def clear_backtest_samples(
    request: BacktestCodeRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> BacktestClearResponse:
    def _operation() -> BacktestClearResponse:
        service = _build_backtest_service(db_manager, current_user)
        data = service.clear_backtest_samples(code=request.code or "")
        data["message"] = "回测样本已清理"
        return BacktestClearResponse(**data)
    return _run_endpoint("清理回测样本失败", _operation, allow_validation_error=True)


@router.post(
    "/results/clear",
    response_model=BacktestClearResponse,
    responses={
        200: {"description": "回测结果已清理"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="清理历史分析评估结果",
)
def clear_backtest_results(
    request: BacktestCodeRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> BacktestClearResponse:
    def _operation() -> BacktestClearResponse:
        service = _build_backtest_service(db_manager, current_user)
        data = service.clear_backtest_results(code=request.code or "")
        data["message"] = "回测结果已清理"
        return BacktestClearResponse(**data)
    return _run_endpoint("清理回测结果失败", _operation, allow_validation_error=True)


# ------------------ /rule/* 路由，使用 RuleBacktestService ------------------

@router.post(
    "/rule/parse",
    response_model=RuleBacktestParseResponse,
    responses={
        200: {"description": "策略解析完成"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="解析规则策略",
)
def parse_rule_strategy(
    request: RuleBacktestParseRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestParseResponse:
    def _operation() -> RuleBacktestParseResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        parsed = service.parse_strategy(
            request.strategy_text,
            code=request.code,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
        )
        strategy_spec = parsed.get("strategy_spec") if isinstance(parsed.get("strategy_spec"), dict) else {}
        return RuleBacktestParseResponse(
            code=(strategy_spec.get("symbol") or request.code),
            strategy_text=request.strategy_text,
            parsed_strategy=dict(parsed),
            normalized_strategy_family=str(strategy_spec.get("strategy_type") or parsed.get("strategy_kind") or ""),
            detected_strategy_family=(str(parsed.get("detected_strategy_family")) if parsed.get("detected_strategy_family") else None),
            executable=bool(parsed.get("executable", False)),
            normalization_state=str(parsed.get("normalization_state") or "pending"),
            assumptions=list(parsed.get("assumptions") or []),
            assumption_groups=list(parsed.get("assumption_groups") or []),
            unsupported_reason=(str(parsed.get("unsupported_reason")) if parsed.get("unsupported_reason") else None),
            unsupported_details=list(parsed.get("unsupported_details") or []),
            unsupported_extensions=list(parsed.get("unsupported_extensions") or []),
            core_intent_summary=(str(parsed.get("core_intent_summary")) if parsed.get("core_intent_summary") else None),
            interpretation_confidence=float(parsed.get("interpretation_confidence") or 0.0),
            supported_portion_summary=(str(parsed.get("supported_portion_summary")) if parsed.get("supported_portion_summary") else None),
            rewrite_suggestions=list(parsed.get("rewrite_suggestions") or []),
            parse_warnings=list(parsed.get("parse_warnings") or []),
            confidence=float(parsed.get("confidence") or 0.0),
            needs_confirmation=bool(parsed.get("needs_confirmation") or False),
            ambiguities=list(parsed.get("ambiguities") or []),
            summary=dict(parsed.get("summary") or {}),
            max_lookback=int(parsed.get("max_lookback") or 1),
        )
    return _run_endpoint("解析规则策略失败", _operation, allow_validation_error=True)


@router.post(
    "/rule/run",
    response_model=RuleBacktestRunResponse,
    responses={
        200: {"description": "规则回测已提交或已完成"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="运行确定性规则策略回测",
    description="默认异步提交规则回测任务并快速返回运行 ID；传入 wait_for_completion=true 时阻塞至完成。",
)
def run_rule_backtest(
    request: RuleBacktestRunRequest,
    background_tasks: BackgroundTasks,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestRunResponse:
    def _operation() -> RuleBacktestRunResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        robustness_config = request.robustness_config.model_dump(exclude_none=True) if request.robustness_config is not None else None
        if request.wait_for_completion:
            data = service.run_backtest(
                code=request.code,
                strategy_text=request.strategy_text,
                parsed_strategy=request.parsed_strategy,
                start_date=request.start_date,
                end_date=request.end_date,
                lookback_bars=request.lookback_bars,
                initial_capital=request.initial_capital,
                fee_bps=request.fee_bps,
                slippage_bps=request.slippage_bps,
                benchmark_mode=request.benchmark_mode,
                benchmark_code=request.benchmark_code,
                robustness_config=robustness_config,
                confirmed=request.confirmed,
            )
            return _build_model(RuleBacktestRunResponse, data)

        data = service.submit_backtest(
            code=request.code,
            strategy_text=request.strategy_text,
            parsed_strategy=request.parsed_strategy,
            start_date=request.start_date,
            end_date=request.end_date,
            lookback_bars=request.lookback_bars,
            initial_capital=request.initial_capital,
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
            benchmark_mode=request.benchmark_mode,
            benchmark_code=request.benchmark_code,
            robustness_config=robustness_config,
            confirmed=request.confirmed,
        )
        background_tasks.add_task(service.process_submitted_run, int(data["id"]))
        return _build_model(RuleBacktestRunResponse, data)
    return _run_endpoint("规则回测失败", _operation, allow_validation_error=True)


@router.post(
    "/rule/universe-jobs",
    response_model=RuleBacktestUniverseJobResponse,
    responses={
        200: {"description": "本地宇宙回测预检任务已创建"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="创建本地规则回测宇宙预检任务",
    description="创建 stored local-only universe job scaffold；仅检查本地日线数据可用性，不执行单标的回测，不触发 provider 拉取。",
)
def create_rule_backtest_universe_job(
    request: RuleBacktestUniverseJobCreateRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestUniverseJobResponse:
    def _operation() -> RuleBacktestUniverseJobResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        data = service.create_universe_job(
            symbols=request.symbols,
            strategy_text=request.strategy_text,
            parsed_strategy=request.parsed_strategy,
            start_date=request.start_date,
            end_date=request.end_date,
            lookback_bars=request.lookback_bars,
            initial_capital=request.initial_capital,
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
            benchmark_mode=request.benchmark_mode,
            benchmark_code=request.benchmark_code,
            request_label=request.request_label,
        )
        return _build_model(RuleBacktestUniverseJobResponse, data)
    return _run_endpoint("创建规则回测宇宙预检任务失败", _operation, allow_validation_error=True)


@router.post(
    "/rule/universe-jobs/{job_id}/run",
    response_model=RuleBacktestUniverseJobResponse,
    responses={
        200: {"description": "本地宇宙规则回测顺序执行完成"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="顺序执行本地规则回测宇宙任务",
    description="同步顺序执行 stored local-only universe job；仅读取本地日线数据，不触发 provider 拉取，不启用并发 worker。",
)
def run_rule_backtest_universe_job(
    job_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestUniverseJobResponse:
    def _operation() -> RuleBacktestUniverseJobResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        data = service.run_universe_job_sequential(job_id)
        if data is None:
            raise _not_found_error("规则回测宇宙任务不存在")
        return _build_model(RuleBacktestUniverseJobResponse, data)
    return _run_endpoint("执行规则回测宇宙任务失败", _operation, allow_validation_error=True)


@router.get(
    "/rule/universe-jobs/{job_id}/status",
    response_model=RuleBacktestUniverseJobResponse,
    responses={
        200: {"description": "本地宇宙回测预检任务状态"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取本地规则回测宇宙任务状态",
)
def get_rule_backtest_universe_job_status(
    job_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestUniverseJobResponse:
    def _operation() -> RuleBacktestUniverseJobResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        data = service.get_universe_job_status(job_id)
        if data is None:
            raise _not_found_error("规则回测宇宙任务不存在")
        return _build_model(RuleBacktestUniverseJobResponse, data)
    return _run_endpoint("查询规则回测宇宙任务状态失败", _operation)


@router.get(
    "/rule/universe-jobs/{job_id}/diagnostics",
    response_model=RuleBacktestUniverseJobDiagnostics,
    responses={
        200: {"description": "本地宇宙回测任务紧凑诊断摘要"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取本地规则回测宇宙任务诊断摘要",
    description="只读返回 job-level 聚合、原因桶、metric leader 与本地数据覆盖摘要；不包含 raw trace 或逐标的大载荷。",
)
def get_rule_backtest_universe_job_diagnostics(
    job_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestUniverseJobDiagnostics:
    def _operation() -> RuleBacktestUniverseJobDiagnostics:
        service = _build_rule_backtest_service(db_manager, current_user)
        data = service.get_universe_job_diagnostics(job_id)
        if data is None:
            raise _not_found_error("规则回测宇宙任务不存在")
        return _build_model(RuleBacktestUniverseJobDiagnostics, data)
    return _run_endpoint("查询规则回测宇宙任务诊断失败", _operation)


@router.get(
    "/rule/universe-jobs/{job_id}/results",
    response_model=RuleBacktestUniverseResultsResponse,
    responses={
        200: {"description": "本地宇宙回测预检任务标的结果"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="分页获取本地规则回测宇宙标的结果",
)
def list_rule_backtest_universe_job_results(
    job_id: int,
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(50, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="按 compact symbol status 过滤"),
    reason_code: Optional[str] = Query(None, alias="reasonCode", description="按 reason_code 过滤"),
    symbol: Optional[str] = Query(None, description="按标的代码前缀过滤"),
    market: Optional[str] = Query(None, description="按推断市场过滤：cn/hk/us"),
    sort: str = Query("sequence_index", description="排序字段"),
    order: str = Query("asc", description="排序方向：asc/desc"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestUniverseResultsResponse:
    def _operation() -> RuleBacktestUniverseResultsResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        if service.get_universe_job_status(job_id) is None:
            raise _not_found_error("规则回测宇宙任务不存在")
        data = service.list_universe_job_results(
            job_id,
            page=page,
            limit=limit,
            status=status,
            reason_code=reason_code,
            symbol=symbol,
            market=market,
            sort=sort,
            order=order,
        )
        return _build_model(RuleBacktestUniverseResultsResponse, data)
    return _run_endpoint("查询规则回测宇宙任务结果失败", _operation, allow_validation_error=True)


@router.get(
    "/rule/runs",
    response_model=RuleBacktestHistoryResponse,
    responses={
        200: {"description": "规则回测历史"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测历史",
)
def get_rule_backtest_runs(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestHistoryResponse:
    def _operation() -> RuleBacktestHistoryResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        data = service.list_runs(code=code, page=page, limit=limit)
        items = _build_models(RuleBacktestHistoryItem, data.get("items", []))
        return RuleBacktestHistoryResponse(total=int(data.get("total", 0)), page=page, limit=limit, items=items)
    return _run_endpoint("查询规则回测历史失败", _operation)


@router.post(
    "/rule/compare",
    response_model=RuleBacktestCompareResponse,
    responses={
        200: {"description": "规则回测对比结果"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="对比已完成的规则回测运行",
    description="基于已持久化的规则回测结果做 stored-first compare，不会重新执行回测。",
)
def compare_rule_backtest_runs(
    request: RuleBacktestCompareRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestCompareResponse:
    def _operation() -> RuleBacktestCompareResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        data = service.compare_runs(request.run_ids)
        return _build_model(RuleBacktestCompareResponse, data)
    return _run_endpoint("规则回测对比失败", _operation, allow_validation_error=True)


@router.get(
    "/rule/runs/{run_id}",
    response_model=RuleBacktestDetailResponse,
    responses={
        200: {"description": "规则回测详情"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测详情",
)
def get_rule_backtest_run(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestDetailResponse:
    def _operation() -> RuleBacktestDetailResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        data = service.get_run(run_id)
        if data is None:
            raise _not_found_error("规则回测记录不存在")
        return _build_model(RuleBacktestDetailResponse, data)
    return _run_endpoint("查询规则回测详情失败", _operation)


@router.get(
    "/rule/runs/{run_id}/status",
    response_model=RuleBacktestStatusResponse,
    responses={
        200: {"description": "规则回测状态"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测状态",
)
def get_rule_backtest_run_status(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestStatusResponse:
    def _operation() -> RuleBacktestStatusResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        data = service.get_run_status(run_id)
        if data is None:
            raise _not_found_error("规则回测记录不存在")
        return _build_model(RuleBacktestStatusResponse, data)
    return _run_endpoint("查询规则回测状态失败", _operation)


@router.get(
    "/rule/runs/{run_id}/support-bundle-manifest",
    response_model=RuleBacktestSupportBundleManifestResponse,
    responses={
        200: {"description": "规则回测 support bundle manifest"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测 support bundle manifest",
    description="返回单条规则回测的紧凑 stored-first support bundle manifest，供 backend handoff、AI 调试与自动化脚本读取。",
)
def get_rule_backtest_support_bundle_manifest(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestSupportBundleManifestResponse:
    def _operation() -> RuleBacktestSupportBundleManifestResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        try:
            data = service.get_support_bundle_manifest(run_id)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                raise _not_found_error("规则回测记录不存在") from exc
            raise
        return _build_model(RuleBacktestSupportBundleManifestResponse, data)
    return _run_endpoint("查询规则回测 support bundle manifest 失败", _operation)


@router.get(
    "/rule/runs/{run_id}/export-index",
    response_model=RuleBacktestSupportExportIndexResponse,
    responses={
        200: {"description": "规则回测 export index"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测 export index",
    description="返回单条规则回测当前可发现的导出项索引，帮助 backend handoff、自动化脚本与 AI 调试先判断哪些 compact/heavy exports 可用。",
)
def get_rule_backtest_support_export_index(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestSupportExportIndexResponse:
    def _operation() -> RuleBacktestSupportExportIndexResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        try:
            data = service.get_support_export_index(run_id)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                raise _not_found_error("规则回测记录不存在") from exc
            raise
        return _build_model(RuleBacktestSupportExportIndexResponse, data)
    return _run_endpoint("查询规则回测 export index 失败", _operation)


@router.get(
    "/rule/runs/{run_id}/support-bundle-reproducibility-manifest",
    response_model=RuleBacktestSupportBundleReproducibilityManifestResponse,
    responses={
        200: {"description": "规则回测 support bundle reproducibility manifest"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测 reproducibility manifest",
    description="返回单条规则回测的紧凑 reproducibility manifest，供 AI 调试、server handoff 与迁移检查读取。",
)
def get_rule_backtest_support_bundle_reproducibility_manifest(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestSupportBundleReproducibilityManifestResponse:
    def _operation() -> RuleBacktestSupportBundleReproducibilityManifestResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        try:
            data = service.get_support_bundle_reproducibility_manifest(run_id)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                raise _not_found_error("规则回测记录不存在") from exc
            raise
        return _build_model(RuleBacktestSupportBundleReproducibilityManifestResponse, data)

    return _run_endpoint("查询规则回测 reproducibility manifest 失败", _operation)


@router.get(
    "/rule/runs/{run_id}/execution-trace.json",
    response_model=RuleBacktestExecutionTraceExportResponse,
    responses={
        200: {"description": "规则回测 execution-trace JSON export"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        409: {"description": "导出当前不可用", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测 execution-trace JSON export",
    description="返回单条规则回测的 execution-trace JSON 导出载荷，供 AI 调试、自动化脚本与 backend handoff 使用。",
)
def get_rule_backtest_execution_trace_json(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestExecutionTraceExportResponse:
    def _operation() -> RuleBacktestExecutionTraceExportResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        try:
            data = service.get_execution_trace_export_json(run_id)
        except ValueError as exc:
            message = str(exc)
            if "not found" in message.lower():
                raise _not_found_error("规则回测记录不存在") from exc
            if "no audit rows to export" in message.lower():
                raise HTTPException(
                    status_code=409,
                    detail={"error": "export_unavailable", "message": "当前回测没有可导出的 execution-trace rows"},
                ) from exc
            raise
        return _build_model(RuleBacktestExecutionTraceExportResponse, data)

    return _run_endpoint("查询规则回测 execution-trace JSON export 失败", _operation)


@router.get(
    "/rule/runs/{run_id}/robustness-evidence.json",
    response_model=RuleBacktestRobustnessEvidenceExportResponse,
    responses={
        200: {"description": "规则回测 robustness evidence JSON export"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        409: {"description": "导出当前不可用", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测 robustness evidence JSON export",
    description="只读返回单条规则回测已存储的 robustness evidence JSON 载荷；不会重新执行 walk-forward、Monte Carlo、stress 或其他 robustness 计算。",
)
def get_rule_backtest_robustness_evidence_json(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestRobustnessEvidenceExportResponse:
    def _operation() -> RuleBacktestRobustnessEvidenceExportResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        try:
            data = service.get_robustness_evidence_export_json(run_id)
        except ValueError as exc:
            message = str(exc)
            if "not found" in message.lower():
                raise _not_found_error("规则回测记录不存在") from exc
            if "no stored robustness evidence to export" in message.lower():
                raise HTTPException(
                    status_code=409,
                    detail={"error": "export_unavailable", "message": "当前回测没有可导出的 robustness evidence"},
                ) from exc
            raise
        return _build_model(RuleBacktestRobustnessEvidenceExportResponse, data)

    return _run_endpoint("查询规则回测 robustness evidence JSON export 失败", _operation)


@router.get(
    "/rule/runs/{run_id}/regime-attribution-readiness.json",
    response_model=RuleBacktestRegimeAttributionReadinessExportResponse,
    responses={
        200: {"description": "规则回测 regime attribution readiness JSON export"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测 regime attribution readiness JSON export",
    description="只读返回单条规则回测已存储证据的 regime attribution readiness 诊断；不会重新执行回测引擎，也不是运行时 attribution engine。",
)
def get_rule_backtest_regime_attribution_readiness_json(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestRegimeAttributionReadinessExportResponse:
    def _operation() -> RuleBacktestRegimeAttributionReadinessExportResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        try:
            data = service.get_regime_attribution_readiness_export(run_id)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                raise _not_found_error("规则回测记录不存在") from exc
            raise
        return _build_model(RuleBacktestRegimeAttributionReadinessExportResponse, data)

    return _run_endpoint("查询规则回测 regime attribution readiness JSON export 失败", _operation)


@router.get(
    "/rule/runs/{run_id}/execution-trace.csv",
    responses={
        200: {
            "description": "规则回测 execution-trace CSV export",
            "content": {"text/csv": {}},
        },
        404: {"description": "记录不存在", "model": ErrorResponse},
        409: {"description": "导出当前不可用", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测 execution-trace CSV export",
    description="返回单条规则回测的 execution-trace CSV 导出载荷，供 operator、表格检查与自动化脚本使用。",
)
def get_rule_backtest_execution_trace_csv(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    def _operation() -> Response:
        service = _build_rule_backtest_service(db_manager, current_user)
        try:
            csv_text = service.get_execution_trace_export_csv_text(run_id)
        except ValueError as exc:
            message = str(exc)
            if "not found" in message.lower():
                raise _not_found_error("规则回测记录不存在") from exc
            if "no audit rows to export" in message.lower():
                raise HTTPException(
                    status_code=409,
                    detail={"error": "export_unavailable", "message": "当前回测没有可导出的 execution-trace rows"},
                ) from exc
            raise
        return Response(
            content=csv_text,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="rule-backtest-{run_id}-execution-trace.csv"',
            },
        )

    return _run_endpoint("查询规则回测 execution-trace CSV export 失败", _operation)


@router.post(
    "/rule/runs/{run_id}/cancel",
    response_model=RuleBacktestCancelResponse,
    responses={
        200: {"description": "规则回测取消结果"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="取消规则回测",
    description="对尚未完成的异步规则回测执行 best-effort cancel；若任务已结束，则返回当前最终状态。",
)
def cancel_rule_backtest_run(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> RuleBacktestCancelResponse:
    def _operation() -> RuleBacktestCancelResponse:
        service = _build_rule_backtest_service(db_manager, current_user)
        data = service.cancel_run(run_id)
        if data is None:
            raise _not_found_error("规则回测记录不存在")
        return _build_model(RuleBacktestCancelResponse, data)
    return _run_endpoint("取消规则回测失败", _operation)
