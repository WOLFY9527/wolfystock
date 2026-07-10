# -*- coding: utf-8 -*-
"""Historical analysis evaluation orchestration service."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select

from src.config import get_config
from src.core.backtest_engine import OVERALL_SENTINEL_CODE, BacktestEngine, EvaluationConfig
from src.repositories.backtest_repo import BacktestRepository
from src.repositories.stock_repo import StockRepository
from src.services.backtest_response_contract import (
    build_execution_readiness_contract,
    build_performance_contract,
    build_standard_result_contract,
    build_standard_run_contract,
)
from src.services.backtest_data_sufficiency import assess_backtest_data_sufficiency
from src.services.backtest_data_source_guard import assess_backtest_data_source_eligibility
from src.services.historical_ohlcv_readiness import (
    HistoricalOhlcvReadinessRequest,
    HistoricalOhlcvReadinessService,
)
from src.services.product_read_model import build_backtest_readiness_read_model
from src.services.us_ohlcv_coverage_readiness import (
    build_us_ohlcv_coverage_readiness,
    resolve_us_ohlcv_coverage_universe,
    starter_us_ohlcv_coverage_symbols,
)
from src.services.us_history_helper import fetch_daily_history_with_local_us_fallback
from src.services.yfinance_us_ohlcv_cache_provider import build_readonly_local_us_ohlcv_cache_provider_from_env
from src.storage import AnalysisHistory, BacktestResult, BacktestRun, BacktestSummary, DatabaseManager, StockDaily

logger = logging.getLogger(__name__)
LOCAL_BACKTEST_STARTER_SYMBOLS = starter_us_ohlcv_coverage_symbols()
AGGREGATE_RUNTIME_PROBE_SKIPPED_REASON = "aggregate_side_effect_boundary"
SINGLE_SYMBOL_RUNTIME_PROBE_MODE = "bounded_provider_observation"


@dataclass(frozen=True)
class BacktestRuntimeSettings:
    """Normalized backtest config shared by evaluation and sample-prep flows."""

    eval_window_days: int
    min_age_days: int
    engine_version: str
    neutral_band_pct: float


@dataclass(frozen=True)
class BacktestSourceMetadata:
    requested_mode: str
    resolved_source: str
    fallback_used: bool


class BacktestService:
    """Service layer for historical analysis evaluation and sample preparation."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ):
        self.db = db_manager or DatabaseManager.get_instance()
        self.repo = BacktestRepository(self.db)
        self.stock_repo = StockRepository(self.db)
        self.owner_id = owner_id
        self.include_all_owners = bool(include_all_owners)

    def _owner_kwargs(self) -> Dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "include_all_owners": self.include_all_owners,
        }

    def run_backtest(
        self,
        *,
        code: Optional[str] = None,
        force: bool = False,
        eval_window_days: Optional[int] = None,
        min_age_days: Optional[int] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """Evaluate historical analysis snapshots against later market bars."""
        config = get_config()
        settings = self._resolve_runtime_settings(
            config,
            eval_window_days=eval_window_days,
            min_age_days=min_age_days,
        )
        if not bool(getattr(config, "backtest_enabled", True)):
            return self._engine_disabled_run_payload(
                code=code,
                force=force,
                settings=settings,
            )
        cutoff_dt = datetime.now() - timedelta(days=settings.min_age_days)
        run_at = datetime.now()
        resolved_owner_id = self.db.require_user_id(self.owner_id)

        eval_config = EvaluationConfig(
            eval_window_days=settings.eval_window_days,
            neutral_band_pct=settings.neutral_band_pct,
            engine_version=settings.engine_version,
        )

        total_history_count = self.repo.count_analysis_history(code=code, **self._owner_kwargs())
        normalized_code = str(code or "").strip()
        if normalized_code and total_history_count == 0:
            self._ensure_cached_backtest_samples(
                code=normalized_code,
                settings=settings,
                sample_count=max(1, min(int(limit or 1), 20)),
            )
            total_history_count = self.repo.count_analysis_history(code=code, **self._owner_kwargs())
        age_eligible_count = self.repo.count_analysis_history(
            code=code,
            created_before=cutoff_dt,
            **self._owner_kwargs(),
        )

        candidates = self.repo.get_candidates(
            code=code,
            min_age_days=settings.min_age_days,
            limit=int(limit),
            eval_window_days=settings.eval_window_days,
            engine_version=settings.engine_version,
            force=force,
            **self._owner_kwargs(),
        )
        sample_observability = self._build_sample_observability(
            code=code,
            settings=settings,
            candidates=candidates,
        )

        processed = 0
        completed = 0
        insufficient = 0
        errors = 0
        touched_codes: set[str] = set()

        results_to_save: List[BacktestResult] = []
        run_runtime_sources: List[str] = []
        run_fallback_used = False

        for analysis in candidates:
            processed += 1
            touched_codes.add(analysis.code)
            analysis_runtime_source = "DatabaseCache"
            analysis_fallback_used = False

            try:
                analysis_date = self._resolve_analysis_date(analysis)
                if analysis_date is None:
                    errors += 1
                    results_to_save.append(
                        BacktestResult(
                            owner_id=resolved_owner_id,
                            analysis_history_id=analysis.id,
                            code=analysis.code,
                            eval_window_days=settings.eval_window_days,
                            engine_version=settings.engine_version,
                            eval_status="error",
                            evaluated_at=run_at,
                            operation_advice=analysis.operation_advice,
                        )
                    )
                    continue
                start_daily = self.stock_repo.get_start_daily(code=analysis.code, analysis_date=analysis_date)

                if start_daily is None or start_daily.close is None:
                    fill_source_meta = self._try_fill_daily_data(
                        code=analysis.code,
                        analysis_date=analysis_date,
                        eval_window_days=settings.eval_window_days,
                    )
                    if fill_source_meta is not None:
                        analysis_runtime_source = fill_source_meta.resolved_source
                        analysis_fallback_used = analysis_fallback_used or fill_source_meta.fallback_used
                    start_daily = self.stock_repo.get_start_daily(code=analysis.code, analysis_date=analysis_date)

                if start_daily is None or start_daily.close is None:
                    insufficient += 1
                    run_runtime_sources.append(analysis_runtime_source)
                    run_fallback_used = run_fallback_used or analysis_fallback_used
                    results_to_save.append(
                        BacktestResult(
                            owner_id=resolved_owner_id,
                            analysis_history_id=analysis.id,
                            code=analysis.code,
                            analysis_date=analysis_date,
                            eval_window_days=settings.eval_window_days,
                            engine_version=settings.engine_version,
                            eval_status="insufficient_data",
                            evaluated_at=run_at,
                            operation_advice=analysis.operation_advice,
                        )
                    )
                    continue

                forward_bars = self.stock_repo.get_forward_bars(
                    code=analysis.code,
                    analysis_date=start_daily.date,
                    eval_window_days=settings.eval_window_days,
                )

                if len(forward_bars) < settings.eval_window_days:
                    fill_source_meta = self._try_fill_daily_data(
                        code=analysis.code,
                        analysis_date=start_daily.date,
                        eval_window_days=settings.eval_window_days,
                    )
                    if fill_source_meta is not None:
                        analysis_runtime_source = fill_source_meta.resolved_source
                        analysis_fallback_used = analysis_fallback_used or fill_source_meta.fallback_used
                    forward_bars = self.stock_repo.get_forward_bars(
                        code=analysis.code,
                        analysis_date=start_daily.date,
                        eval_window_days=settings.eval_window_days,
                    )

                evaluation = BacktestEngine.evaluate_single(
                    operation_advice=analysis.operation_advice,
                    analysis_date=start_daily.date,
                    start_price=float(start_daily.close),
                    forward_bars=forward_bars,
                    stop_loss=analysis.stop_loss,
                    take_profit=analysis.take_profit,
                    config=eval_config,
                )

                status = evaluation.get("eval_status")
                if status == "insufficient_data":
                    insufficient += 1
                elif status == "completed":
                    completed += 1
                else:
                    errors += 1
                run_runtime_sources.append(analysis_runtime_source)
                run_fallback_used = run_fallback_used or analysis_fallback_used

                results_to_save.append(
                    BacktestResult(
                        owner_id=resolved_owner_id,
                        analysis_history_id=analysis.id,
                        code=analysis.code,
                        analysis_date=evaluation.get("analysis_date"),
                        eval_window_days=int(evaluation.get("eval_window_days") or settings.eval_window_days),
                        engine_version=str(evaluation.get("engine_version") or settings.engine_version),
                        eval_status=str(evaluation.get("eval_status") or "error"),
                        evaluated_at=run_at,
                        operation_advice=evaluation.get("operation_advice"),
                        position_recommendation=evaluation.get("position_recommendation"),
                        start_price=evaluation.get("start_price"),
                        end_close=evaluation.get("end_close"),
                        max_high=evaluation.get("max_high"),
                        min_low=evaluation.get("min_low"),
                        stock_return_pct=evaluation.get("stock_return_pct"),
                        direction_expected=evaluation.get("direction_expected"),
                        direction_correct=evaluation.get("direction_correct"),
                        outcome=evaluation.get("outcome"),
                        stop_loss=evaluation.get("stop_loss"),
                        take_profit=evaluation.get("take_profit"),
                        hit_stop_loss=evaluation.get("hit_stop_loss"),
                        hit_take_profit=evaluation.get("hit_take_profit"),
                        first_hit=evaluation.get("first_hit"),
                        first_hit_date=evaluation.get("first_hit_date"),
                        first_hit_trading_days=evaluation.get("first_hit_trading_days"),
                        simulated_entry_price=evaluation.get("simulated_entry_price"),
                        simulated_exit_price=evaluation.get("simulated_exit_price"),
                        simulated_exit_reason=evaluation.get("simulated_exit_reason"),
                        simulated_return_pct=evaluation.get("simulated_return_pct"),
                    )
                )

            except Exception as exc:
                errors += 1
                logger.error(f"历史分析评估失败: {analysis.code}#{analysis.id}: {exc}")
                run_runtime_sources.append(analysis_runtime_source)
                run_fallback_used = run_fallback_used or analysis_fallback_used
                results_to_save.append(
                    BacktestResult(
                        owner_id=resolved_owner_id,
                        analysis_history_id=analysis.id,
                        code=analysis.code,
                        analysis_date=self._resolve_analysis_date(analysis),
                        eval_window_days=settings.eval_window_days,
                        engine_version=settings.engine_version,
                        eval_status="error",
                        evaluated_at=run_at,
                        operation_advice=analysis.operation_advice,
                    )
                )

        no_result_reason: Optional[str] = None
        no_result_message: Optional[str] = None
        summary_snapshot: Dict[str, Any] = {}
        if results_to_save:
            summary_snapshot = BacktestEngine.compute_summary(
                results=results_to_save,
                scope="stock" if code else "overall",
                code=code or OVERALL_SENTINEL_CODE,
                eval_window_days=settings.eval_window_days,
                engine_version=settings.engine_version,
            )
            run_source_metadata = self._build_source_metadata_from_runtime_sources(
                code=code,
                runtime_sources=run_runtime_sources,
                fallback_used=run_fallback_used,
            )
            summary_snapshot.update({
                "requested_mode": run_source_metadata.requested_mode,
                "resolved_source": run_source_metadata.resolved_source,
                "fallback_used": run_source_metadata.fallback_used,
            })

        saved = 0
        if results_to_save:
            saved = self.repo.save_results_batch(results_to_save, replace_existing=force)

        if saved:
            self._recompute_summaries(
                touched_codes=sorted(touched_codes),
                eval_window_days=settings.eval_window_days,
                engine_version=settings.engine_version,
            )

        if saved == 0:
            no_result_reason, no_result_message = self._resolve_run_no_result(
                code=code,
                processed=processed,
                completed=completed,
                insufficient=insufficient,
                errors=errors,
                total_history_count=total_history_count,
                age_eligible_count=age_eligible_count,
                force=force,
                min_age_days=settings.min_age_days,
            )

        run_record = BacktestRun(
            owner_id=resolved_owner_id,
            code=code,
            eval_window_days=settings.eval_window_days,
            min_age_days=settings.min_age_days,
            force=force,
            run_at=run_at,
            completed_at=run_at,
            processed=processed,
            saved=saved,
            completed=completed,
            insufficient=insufficient,
            errors=errors,
            candidate_count=len(candidates),
            result_count=saved,
            no_result_reason=no_result_reason,
            no_result_message=no_result_message,
            status="completed" if errors == 0 else "error",
            total_evaluations=summary_snapshot.get("total_evaluations") or 0,
            completed_count=summary_snapshot.get("completed_count") or 0,
            insufficient_count=summary_snapshot.get("insufficient_count") or 0,
            long_count=summary_snapshot.get("long_count") or 0,
            cash_count=summary_snapshot.get("cash_count") or 0,
            win_count=summary_snapshot.get("win_count") or 0,
            loss_count=summary_snapshot.get("loss_count") or 0,
            neutral_count=summary_snapshot.get("neutral_count") or 0,
            win_rate_pct=summary_snapshot.get("win_rate_pct"),
            avg_stock_return_pct=summary_snapshot.get("avg_stock_return_pct"),
            avg_simulated_return_pct=summary_snapshot.get("avg_simulated_return_pct"),
            direction_accuracy_pct=summary_snapshot.get("direction_accuracy_pct"),
            summary_json=json.dumps(summary_snapshot or {}, ensure_ascii=False),
        )
        run_record = self.repo.save_run(run_record)

        run_source_metadata = self._build_source_metadata_from_runtime_sources(
            code=code,
            runtime_sources=run_runtime_sources,
            fallback_used=run_fallback_used,
        )

        payload = {
            "run_id": run_record.id,
            "run_at": run_record.run_at.isoformat() if run_record.run_at else None,
            "processed": processed,
            "saved": saved,
            "completed": completed,
            "insufficient": insufficient,
            "errors": errors,
            "candidate_count": len(candidates),
            "no_result_reason": no_result_reason,
            "no_result_message": no_result_message,
            "latest_prepared_sample_date": sample_observability.get("latest_prepared_sample_date"),
            "latest_eligible_sample_date": sample_observability.get("latest_eligible_sample_date"),
            "excluded_recent_reason": sample_observability.get("excluded_recent_reason"),
            "excluded_recent_message": sample_observability.get("excluded_recent_message"),
            "evaluation_mode": "historical_analysis_evaluation",
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
            "requested_mode": run_source_metadata.requested_mode,
            "resolved_source": run_source_metadata.resolved_source,
            "fallback_used": run_source_metadata.fallback_used,
            "pricing_resolved_source": run_source_metadata.resolved_source,
            "pricing_fallback_used": run_source_metadata.fallback_used,
            "execution_assumptions": self._signal_evaluation_assumptions(),
        }
        payload.update(build_standard_run_contract(payload))
        return payload

    def list_backtest_runs(self, *, code: Optional[str] = None, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        offset = max(page - 1, 0) * limit
        rows, total = self.repo.get_runs_paginated(
            code=code,
            offset=offset,
            limit=limit,
            **self._owner_kwargs(),
        )
        items = [self._run_to_dict(row) for row in rows]
        return {"total": total, "page": page, "limit": limit, "items": items}

    def get_run_results(self, *, run_id: int, page: int = 1, limit: int = 20) -> Optional[Dict[str, Any]]:
        run = self.repo.get_run(run_id, **self._owner_kwargs())
        if run is None:
            return None
        offset = max(page - 1, 0) * limit
        rows, total = self.repo.get_results_paginated(
            code=None,
            eval_window_days=None,
            run_id=run_id,
            days=None,
            offset=offset,
            limit=limit,
            **self._owner_kwargs(),
        )
        items = [self._result_to_dict(r) for r in rows]
        return {"total": total, "page": page, "limit": limit, "items": items}

    def get_sample_status(self, *, code: Optional[str]) -> Dict[str, Any]:
        settings = self._resolve_runtime_settings()
        if not self._backtest_engine_enabled():
            return self._engine_disabled_sample_status(code=code, settings=settings)
        if not str(code or "").strip():
            return self._get_aggregate_sample_status(settings=settings)
        rows = self.repo.get_sample_rows(code=code, **self._owner_kwargs())
        parsed_dates: List[date] = []
        latest_created_at: Optional[datetime] = None
        for row in rows:
            parsed = self.repo.parse_analysis_date_from_snapshot(row.context_snapshot)
            if parsed:
                parsed_dates.append(parsed)
            if row.created_at and (latest_created_at is None or row.created_at > latest_created_at):
                latest_created_at = row.created_at
        source_metadata = self._build_source_metadata_for_samples(code=code, sample_rows=rows)
        sample_observability = self._build_sample_observability(
            code=code,
            settings=settings,
            sample_rows=rows,
        )

        stock_rows = self._load_stock_daily_rows(code)
        ohlcv_readiness, ohlcv_source_metadata = self._build_historical_ohlcv_readiness_with_metadata(
            code=code,
            rows=stock_rows,
            required_bars=settings.eval_window_days,
            allow_runtime_probe=True,
        )
        source_metadata = self._prefer_more_truthful_source_metadata(
            primary=source_metadata,
            fallback=ohlcv_source_metadata,
        )
        probe_policy = self._single_symbol_probe_policy()
        write_policy = self._single_symbol_write_policy()
        sample_state, sample_reasons = self._sample_readiness_from_inputs(
            prepared_count=len(rows),
            ohlcv_readiness=ohlcv_readiness,
            sample_observability=sample_observability,
        )

        return {
            "code": code,
            "scope": "single",
            "prepared_count": len(rows),
            "prepared_start_date": min(parsed_dates).isoformat() if parsed_dates else None,
            "prepared_end_date": max(parsed_dates).isoformat() if parsed_dates else None,
            "latest_prepared_at": latest_created_at.isoformat() if latest_created_at else None,
            "latest_prepared_sample_date": sample_observability.get("latest_prepared_sample_date"),
            "latest_eligible_sample_date": sample_observability.get("latest_eligible_sample_date"),
            "excluded_recent_reason": sample_observability.get("excluded_recent_reason"),
            "excluded_recent_message": sample_observability.get("excluded_recent_message"),
            "eval_window_days": settings.eval_window_days,
            "min_age_days": settings.min_age_days,
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
            "requested_mode": source_metadata.requested_mode,
            "resolved_source": source_metadata.resolved_source,
            "fallback_used": source_metadata.fallback_used,
            "pricing_resolved_source": source_metadata.resolved_source,
            "pricing_fallback_used": source_metadata.fallback_used,
            "sample_readiness_state": sample_state,
            "sample_blocking_reasons": sample_reasons,
            "execution_readiness": self._sample_execution_readiness(
                sample_state=sample_state,
                sample_reasons=sample_reasons,
                ohlcv_readiness=ohlcv_readiness,
            ),
            "productReadModel": build_backtest_readiness_read_model(
                {
                    **ohlcv_readiness,
                    "preparedCount": len(rows),
                    "sampleReadinessState": sample_state,
                    "samplesInitializing": len(rows) <= 0 and sample_state == "no_samples",
                }
            ),
            "probePolicy": probe_policy,
            "writePolicy": write_policy,
            "historicalOhlcvReadiness": ohlcv_readiness,
        }

    def clear_backtest_samples(self, *, code: str) -> Dict[str, Any]:
        return self._clear_backtest_artifacts(code=code, include_samples=True)

    def clear_backtest_results(self, *, code: str) -> Dict[str, Any]:
        return self._clear_backtest_artifacts(code=code, include_samples=False)

    def get_recent_evaluations(self, *, code: Optional[str], eval_window_days: Optional[int] = None, limit: int = 50, page: int = 1) -> Dict[str, Any]:
        offset = max(page - 1, 0) * limit
        rows, total = self.repo.get_results_paginated(
            code=code,
            eval_window_days=eval_window_days,
            days=None,
            offset=offset,
            limit=limit,
            **self._owner_kwargs(),
        )
        items = [self._result_to_dict(r) for r in rows]
        return {"total": total, "page": page, "limit": limit, "items": items}

    def get_summary(self, *, scope: str, code: Optional[str], eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        config = get_config()
        engine_version = str(getattr(config, "backtest_engine_version", "v1"))
        lookup_code = OVERALL_SENTINEL_CODE if scope == "overall" else code
        summary = self.repo.get_summary(
            scope=scope,
            code=lookup_code,
            eval_window_days=eval_window_days,
            engine_version=engine_version,
            **self._owner_kwargs(),
        )
        if summary is None:
            return None
        return self._summary_to_dict(summary)

    def get_global_summary(self, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Return overall backtest metrics normalized for Agent memory consumers."""
        return self._normalize_learning_summary(
            self.get_summary(scope="overall", code=None, eval_window_days=eval_window_days)
        )

    def get_stock_summary(self, code: str, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Return per-stock backtest metrics normalized for Agent memory consumers."""
        return self._normalize_learning_summary(
            self.get_summary(scope="stock", code=code, eval_window_days=eval_window_days)
        )

    def get_skill_summary(self, skill_id: str, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Return skill-like summary metrics for Agent memory consumers.

        The current backtest storage layer only persists overall / per-stock rollups.
        Re-using the overall rollup here would fabricate skill-specific performance
        and mislead auto-weighting. Until real skill-tagged summaries exist, return
        ``None`` so downstream callers fall back to neutral weighting.
        """
        return None

    def get_strategy_summary(self, strategy_id: str, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Compatibility wrapper for legacy strategy-based callers."""
        summary = self.get_skill_summary(strategy_id, eval_window_days=eval_window_days)
        if summary is None:
            return None
        normalized = dict(summary)
        normalized["strategy_id"] = strategy_id
        return normalized

    def prepare_backtest_samples(
        self,
        *,
        code: str,
        sample_count: int = 20,
        eval_window_days: Optional[int] = None,
        min_age_days: Optional[int] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Generate historical analysis snapshots that can be consumed by evaluation."""
        normalized_code = self._require_code(code)
        settings = self._resolve_runtime_settings(
            eval_window_days=eval_window_days,
            min_age_days=min_age_days,
        )
        if not self._backtest_engine_enabled():
            return self._engine_disabled_prepare_payload(
                code=normalized_code,
                sample_count=sample_count,
                settings=settings,
            )
        sample_count = max(1, int(sample_count))

        market_rows_saved, warmup_source_metadata = self._ensure_market_history(
            code=normalized_code,
            min_age_days=settings.min_age_days,
            eval_window_days=settings.eval_window_days,
            sample_count=sample_count,
            force_refresh=force_refresh,
            allow_provider_fallback=False,
        )

        rows = self._load_stock_daily_rows(normalized_code)
        candidate_rows = self._select_preparable_rows(rows, eval_window_days=settings.eval_window_days)
        if not candidate_rows:
            source_metadata = warmup_source_metadata or self._build_source_metadata_from_runtime_sources(
                code=normalized_code,
                runtime_sources=["DatabaseCache"] if rows else [],
                fallback_used=False,
            )
            ohlcv_readiness = self._build_historical_ohlcv_readiness(
                code=normalized_code,
                rows=rows,
                required_bars=settings.eval_window_days,
                allow_runtime_probe=False,
            )
            sample_state, sample_reasons = self._sample_readiness_from_inputs(
                prepared_count=0,
                ohlcv_readiness=ohlcv_readiness,
                sample_observability={},
            )
            return {
                "code": normalized_code,
                "sample_count": sample_count,
                "prepared": 0,
                "skipped_existing": 0,
                "market_rows_saved": market_rows_saved,
                "candidate_rows": 0,
                "eval_window_days": settings.eval_window_days,
                "min_age_days": settings.min_age_days,
                "no_result_reason": "missing_market_history",
                "no_result_message": "当前没有足够的历史行情数据，无法生成历史分析评估样本。",
                "requested_mode": source_metadata.requested_mode,
                "resolved_source": source_metadata.resolved_source,
                "fallback_used": source_metadata.fallback_used,
                "pricing_resolved_source": source_metadata.resolved_source,
                "pricing_fallback_used": source_metadata.fallback_used,
                "execution_readiness": self._sample_execution_readiness(
                    sample_state=sample_state,
                    sample_reasons=sample_reasons,
                    ohlcv_readiness=ohlcv_readiness,
                ),
            }

        selected_rows = candidate_rows[-sample_count:]
        prepared = 0
        skipped_existing = 0
        now = datetime.now()

        resolved_owner_id = self.db.require_user_id(self.owner_id)
        with self.db.get_session() as session:
            for index, row_index in enumerate(selected_rows):
                row = rows[row_index]
                query_id = self._prepare_sample_query_id(normalized_code, row.date, settings.eval_window_days)
                existing = session.execute(
                    select(AnalysisHistory).where(
                        and_(
                            AnalysisHistory.query_id == query_id,
                            AnalysisHistory.owner_id == resolved_owner_id,
                        )
                    ).limit(1)
                ).scalar_one_or_none()
                if existing is not None and not force_refresh:
                    skipped_existing += 1
                    continue
                if existing is not None and force_refresh:
                    sample = self._build_prepared_analysis_sample(
                        code=normalized_code,
                        row=row,
                        previous_close=rows[row_index - 1].close if row_index > 0 else None,
                        average_close=self._moving_average(rows, row_index, window=3),
                        min_age_days=settings.min_age_days,
                        eval_window_days=settings.eval_window_days,
                        created_at=now - timedelta(days=settings.min_age_days + 1 + index),
                        query_id=query_id,
                        owner_id=resolved_owner_id,
                    )
                    existing.name = sample.name
                    existing.report_type = sample.report_type
                    existing.sentiment_score = sample.sentiment_score
                    existing.operation_advice = sample.operation_advice
                    existing.trend_prediction = sample.trend_prediction
                    existing.analysis_summary = sample.analysis_summary
                    existing.raw_result = sample.raw_result
                    existing.news_content = sample.news_content
                    existing.context_snapshot = sample.context_snapshot
                    existing.ideal_buy = sample.ideal_buy
                    existing.secondary_buy = sample.secondary_buy
                    existing.stop_loss = sample.stop_loss
                    existing.take_profit = sample.take_profit
                    existing.created_at = sample.created_at
                    prepared += 1
                    continue

                sample = self._build_prepared_analysis_sample(
                    code=normalized_code,
                    row=row,
                    previous_close=rows[row_index - 1].close if row_index > 0 else None,
                    average_close=self._moving_average(rows, row_index, window=3),
                    min_age_days=settings.min_age_days,
                    eval_window_days=settings.eval_window_days,
                    created_at=now - timedelta(days=settings.min_age_days + 1 + index),
                    query_id=query_id,
                    owner_id=resolved_owner_id,
                )
                session.add(sample)
                prepared += 1

            session.commit()

        source_metadata = warmup_source_metadata or self._build_source_metadata_for_stock_rows(
            code=normalized_code,
            rows=rows,
            default_to_cache=bool(rows),
        )
        sample_observability = self._build_sample_observability(
            code=normalized_code,
            settings=settings,
            sample_rows=self.repo.get_sample_rows(code=normalized_code, **self._owner_kwargs()),
            stock_rows=rows,
        )
        ohlcv_readiness = self._build_historical_ohlcv_readiness(
            code=normalized_code,
            rows=rows,
            required_bars=settings.eval_window_days,
            allow_runtime_probe=False,
        )
        sample_state, sample_reasons = self._sample_readiness_from_inputs(
            prepared_count=prepared + skipped_existing,
            ohlcv_readiness=ohlcv_readiness,
            sample_observability=sample_observability,
        )

        return {
            "code": normalized_code,
            "sample_count": sample_count,
            "prepared": prepared,
            "skipped_existing": skipped_existing,
            "market_rows_saved": market_rows_saved,
            "candidate_rows": len(candidate_rows),
            "eval_window_days": settings.eval_window_days,
            "min_age_days": settings.min_age_days,
            "prepared_start_date": self._prepared_sample_start_date(normalized_code),
            "prepared_end_date": self._prepared_sample_end_date(normalized_code),
            "latest_prepared_at": self._latest_prepared_at(normalized_code),
            "latest_prepared_sample_date": sample_observability.get("latest_prepared_sample_date"),
            "latest_eligible_sample_date": sample_observability.get("latest_eligible_sample_date"),
            "excluded_recent_reason": sample_observability.get("excluded_recent_reason"),
            "excluded_recent_message": sample_observability.get("excluded_recent_message"),
            "no_result_reason": None if prepared > 0 else "no_samples_prepared",
            "no_result_message": (
                f"已准备 {prepared} 条历史分析评估样本，可重新运行评估。"
                if prepared > 0
                else "没有生成新的历史分析评估样本。"
            ),
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
            "requested_mode": source_metadata.requested_mode,
            "resolved_source": source_metadata.resolved_source,
            "fallback_used": source_metadata.fallback_used,
            "pricing_resolved_source": source_metadata.resolved_source,
            "pricing_fallback_used": source_metadata.fallback_used,
            "execution_readiness": self._sample_execution_readiness(
                sample_state=sample_state,
                sample_reasons=sample_reasons,
                ohlcv_readiness=ohlcv_readiness,
            ),
        }

    @staticmethod
    def _require_code(code: str) -> str:
        normalized_code = str(code or "").strip()
        if not normalized_code:
            raise ValueError("code is required")
        return normalized_code

    @staticmethod
    def _resolve_runtime_settings(
        config: Optional[Any] = None,
        *,
        eval_window_days: Optional[int] = None,
        min_age_days: Optional[int] = None,
    ) -> BacktestRuntimeSettings:
        resolved_config = config or get_config()
        resolved_eval_window_days = int(
            eval_window_days
            if eval_window_days is not None
            else getattr(resolved_config, "backtest_eval_window_days", 10)
        )
        resolved_min_age_days = int(
            min_age_days
            if min_age_days is not None
            else getattr(resolved_config, "backtest_min_age_days", 14)
        )
        return BacktestRuntimeSettings(
            eval_window_days=max(1, resolved_eval_window_days),
            min_age_days=max(0, resolved_min_age_days),
            engine_version=str(getattr(resolved_config, "backtest_engine_version", "v1")),
            neutral_band_pct=float(getattr(resolved_config, "backtest_neutral_band_pct", 2.0)),
        )

    @staticmethod
    def _backtest_engine_enabled() -> bool:
        return bool(getattr(get_config(), "backtest_enabled", True))

    def _engine_disabled_run_payload(
        self,
        *,
        code: Optional[str],
        force: bool,
        settings: BacktestRuntimeSettings,
    ) -> Dict[str, Any]:
        payload = {
            "run_id": None,
            "run_at": datetime.now().isoformat(),
            "processed": 0,
            "saved": 0,
            "completed": 0,
            "insufficient": 0,
            "errors": 0,
            "candidate_count": 0,
            "no_result_reason": "engine_disabled",
            "no_result_message": "Backtest engine is disabled by configuration; no samples or results were evaluated.",
            "latest_prepared_sample_date": None,
            "latest_eligible_sample_date": None,
            "excluded_recent_reason": None,
            "excluded_recent_message": None,
            "evaluation_mode": "engine_disabled",
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
            "requested_mode": self._requested_mode_for_code(code),
            "resolved_source": "engine_disabled",
            "fallback_used": False,
            "pricing_resolved_source": "engine_disabled",
            "pricing_fallback_used": False,
            "execution_assumptions": self._signal_evaluation_assumptions(),
            "engine_state": "disabled",
            "force": bool(force),
        }
        payload.update(build_standard_run_contract(payload))
        return payload

    def _engine_disabled_prepare_payload(
        self,
        *,
        code: str,
        sample_count: int,
        settings: BacktestRuntimeSettings,
    ) -> Dict[str, Any]:
        return {
            "code": code,
            "sample_count": max(1, int(sample_count)),
            "prepared": 0,
            "skipped_existing": 0,
            "market_rows_saved": 0,
            "candidate_rows": 0,
            "eval_window_days": settings.eval_window_days,
            "min_age_days": settings.min_age_days,
            "no_result_reason": "engine_disabled",
            "no_result_message": "Backtest engine is disabled by configuration; no samples were prepared.",
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
            "requested_mode": self._requested_mode_for_code(code),
            "resolved_source": "engine_disabled",
            "fallback_used": False,
            "pricing_resolved_source": "engine_disabled",
            "pricing_fallback_used": False,
            "execution_readiness": build_execution_readiness_contract(
                {"engine_state": "disabled", "no_result_reason": "engine_disabled"},
                data_status="engine_disabled",
                calculation_status="engine_disabled",
                sample_status="engine_disabled",
            ),
        }

    def _engine_disabled_sample_status(
        self,
        *,
        code: Optional[str],
        settings: BacktestRuntimeSettings,
    ) -> Dict[str, Any]:
        normalized_code = str(code or "").strip()
        scope = "single" if normalized_code else "aggregate"
        display_code = normalized_code or "__all__"
        readiness = HistoricalOhlcvReadinessService().assess_supplied_history(
            HistoricalOhlcvReadinessRequest(
                symbol=display_code,
                market="unknown",
                timeframe="1d",
                lookback_bars=settings.eval_window_days,
                required_bars=settings.eval_window_days,
            ),
            [],
            source_available=False,
            unavailable_reason="provider_missing",
        ).readiness
        return {
            "code": display_code,
            "scope": scope,
            "prepared_count": 0,
            "prepared_start_date": None,
            "prepared_end_date": None,
            "latest_prepared_at": None,
            "latest_prepared_sample_date": None,
            "latest_eligible_sample_date": None,
            "excluded_recent_reason": "engine_disabled",
            "excluded_recent_message": "Backtest engine is disabled by configuration.",
            "eval_window_days": settings.eval_window_days,
            "min_age_days": settings.min_age_days,
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
            "requested_mode": self._requested_mode_for_code(normalized_code),
            "resolved_source": "engine_disabled",
            "fallback_used": False,
            "pricing_resolved_source": "engine_disabled",
            "pricing_fallback_used": False,
            "sample_readiness_state": "engine_disabled",
            "sample_blocking_reasons": ["engine_disabled"],
            "execution_readiness": build_execution_readiness_contract(
                {"engine_state": "disabled", "no_result_reason": "engine_disabled"},
                data_status="engine_disabled",
                calculation_status="engine_disabled",
                sample_status="engine_disabled",
            ),
            "productReadModel": build_backtest_readiness_read_model(
                {
                    **readiness,
                    "preparedCount": 0,
                    "sampleReadinessState": "engine_disabled",
                }
            ),
            "historicalOhlcvReadiness": readiness,
        }

    @staticmethod
    def _resolve_run_no_result(
        *,
        code: Optional[str],
        processed: int,
        completed: int,
        insufficient: int,
        errors: int,
        total_history_count: int,
        age_eligible_count: int,
        force: bool,
        min_age_days: int,
    ) -> tuple[str, str]:
        if processed == 0:
            if total_history_count == 0:
                return "no_analysis_history", "没有找到可评估的历史分析记录。"
            if age_eligible_count == 0:
                scope_label = f"股票 {code}" if code else "当前筛选条件"
                return (
                    "insufficient_historical_data",
                    f"{scope_label} 下没有满足 {min_age_days} 天成熟窗口的分析记录，因此本次历史分析评估未生成结果。",
                )
            if not force:
                return (
                    "already_backtested",
                    "符合条件的分析记录已经有相同窗口的历史分析评估结果，因此没有写入新结果。",
                )
            return "no_eligible_candidates", "没有可执行的历史分析评估候选记录。"
        if completed == 0 and insufficient > 0:
            return (
                "insufficient_forward_data",
                "候选记录都缺少足够的前向行情窗口，因此未生成可完成的历史分析评估结果。",
            )
        if completed == 0 and errors > 0:
            return "execution_failed", f"{errors} 条候选记录在历史分析评估执行中出错。"
        return "persistence_noop", "历史分析评估已执行，但没有写入新的结果。"

    def _clear_backtest_artifacts(self, *, code: str, include_samples: bool) -> Dict[str, Any]:
        normalized_code = self._require_code(code)
        deleted_runs = self.repo.delete_runs_by_code(code=normalized_code, **self._owner_kwargs())
        deleted_results = self.repo.delete_results_by_code(code=normalized_code, **self._owner_kwargs())
        deleted_samples = self.repo.delete_sample_rows(code=normalized_code, **self._owner_kwargs()) if include_samples else 0
        deleted_summaries = self.repo.delete_summaries_by_code(code=normalized_code, **self._owner_kwargs())
        self._recompute_global_summaries_if_needed()
        return {
            "code": normalized_code,
            "deleted_runs": deleted_runs,
            "deleted_results": deleted_results,
            "deleted_samples": deleted_samples,
            "deleted_summaries": deleted_summaries,
        }

    def _resolve_analysis_date(self, analysis) -> Optional[date]:
        parsed = self.repo.parse_analysis_date_from_snapshot(analysis.context_snapshot)
        if parsed:
            return parsed
        if getattr(analysis, "created_at", None):
            return analysis.created_at.date()
        logger.warning(f"无法确定分析日期，跳过记录: {analysis.code}#{getattr(analysis, 'id', '?')}")
        return None

    @staticmethod
    def _signal_evaluation_assumptions() -> Dict[str, Any]:
        return {
            "module_type": "historical_analysis_evaluation",
            "evaluation_window_unit": "trading_bars",
            "maturity_unit": "calendar_days",
            "price_basis": "close",
            "analysis_signal_timing": "analysis snapshot on analysis_date",
            "simulated_entry_timing": "analysis_date close",
            "simulated_exit_timing": "first forward bar target touch or evaluation-window end close",
            "position_sizing": "binary long_or_cash; simulated long leg uses 100% notional exposure",
            "fees_slippage": "not applied",
        }

    def _collect_market_data_sources(self, *, code: str, analysis_date: Optional[date], eval_window_days: int) -> List[str]:
        if analysis_date is None:
            return []
        sources: List[str] = []
        start_daily = self.stock_repo.get_start_daily(code=code, analysis_date=analysis_date)
        if start_daily and start_daily.data_source:
            sources.append(str(start_daily.data_source))
        for bar in self.stock_repo.get_forward_bars(code=code, analysis_date=analysis_date, eval_window_days=eval_window_days):
            if bar.data_source:
                sources.append(str(bar.data_source))
        deduped: List[str] = []
        for item in sources:
            if item not in deduped:
                deduped.append(item)
        return deduped

    def _standard_result_ohlcv_rows(
        self,
        *,
        code: str,
        analysis_date: Optional[date],
        eval_window_days: int,
    ) -> List[StockDaily]:
        if analysis_date is None:
            return []
        rows: List[StockDaily] = []
        start_daily = self.stock_repo.get_start_daily(code=code, analysis_date=analysis_date)
        if start_daily is not None:
            rows.append(start_daily)
        rows.extend(
            self.stock_repo.get_forward_bars(
                code=code,
                analysis_date=analysis_date,
                eval_window_days=eval_window_days,
            )
        )
        return rows

    @staticmethod
    def _standard_result_data_quality(
        *,
        code: str,
        analysis_date: Optional[date],
        eval_window_days: int,
        market_data_sources: List[str],
    ) -> Dict[str, Any]:
        source = market_data_sources[0] if market_data_sources else "database_cache"
        authority = assess_backtest_data_source_eligibility(code=code, source=source)
        requested_end = analysis_date + timedelta(days=max(eval_window_days * 2, eval_window_days)) if analysis_date else None
        warnings = [
            {
                "code": "adjustment_status_unknown",
                "severity": "info",
                "message": "Adjustment status is unknown for historical analysis evaluation results.",
            },
            {
                "code": "dividends_splits_unknown",
                "severity": "info",
                "message": "Dividend and split handling is unknown for historical analysis evaluation results.",
            },
        ]
        if not market_data_sources:
            warnings.append(
                {
                    "code": "source_metadata_incomplete",
                    "severity": "info",
                    "message": "Stored bars do not expose a concrete upstream provider.",
                }
            )
        if authority.authority_status != "allowed":
            warnings.append(
                {
                    "code": "backtest_authority_rejected" if authority.rejected else "backtest_authority_degraded",
                    "severity": "warning",
                    "message": (
                        f"Backtest authority source {source} is rejected for reproducible authority."
                        if authority.rejected
                        else f"Backtest authority source {source} is fill-only and not reproducible authority."
                    ),
                }
            )
        return {
            "symbol": code,
            "provider": source,
            "source": source,
            "authority_status": authority.authority_status,
            "authority_source_type": authority.source_type,
            "authority_reason_codes": list(authority.reason_codes),
            "frequency": "1d",
            "requested_start": analysis_date.isoformat() if analysis_date else None,
            "requested_end": requested_end.isoformat() if requested_end else None,
            "bar_count": None,
            "expected_bar_count": eval_window_days,
            "missing_bar_count": None,
            "adjustment_mode": "unknown",
            "dividends_handled": "unknown",
            "splits_handled": "unknown",
            "warnings": warnings,
        }

    def _build_historical_ohlcv_readiness(
        self,
        *,
        code: str,
        rows: List[StockDaily],
        required_bars: int,
        benchmark_required: bool = False,
        benchmark_symbol: Optional[str] = None,
        allow_runtime_probe: bool = False,
    ) -> Dict[str, Any]:
        readiness, _ = self._build_historical_ohlcv_readiness_with_metadata(
            code=code,
            rows=rows,
            required_bars=required_bars,
            benchmark_required=benchmark_required,
            benchmark_symbol=benchmark_symbol,
            allow_runtime_probe=allow_runtime_probe,
        )
        return readiness

    def _build_historical_ohlcv_readiness_with_metadata(
        self,
        *,
        code: str,
        rows: List[StockDaily],
        required_bars: int,
        benchmark_required: bool = False,
        benchmark_symbol: Optional[str] = None,
        allow_runtime_probe: bool = False,
    ) -> tuple[Dict[str, Any], BacktestSourceMetadata]:
        if rows:
            start = rows[0].date
            end = rows[-1].date
            source_available = True
        else:
            start = None
            end = None
            source_available = False
        request = HistoricalOhlcvReadinessRequest(
            symbol=code,
            market="US" if self._requested_mode_for_code(code) == "local_first" else "unknown",
            timeframe="1d",
            start=start,
            end=end,
            lookback_bars=required_bars,
            required_bars=max(0, int(required_bars or 0)),
            require_adjusted=False,
            benchmark_symbol=benchmark_symbol,
            benchmark_required=benchmark_required,
        )
        stock_source_metadata = self._build_source_metadata_for_stock_rows(
            code=code,
            rows=rows,
            default_to_cache=bool(rows),
        )
        provider = build_readonly_local_us_ohlcv_cache_provider_from_env()
        cached_readiness: Optional[Dict[str, Any]] = None
        if provider is not None and (not source_available or benchmark_required):
            result = HistoricalOhlcvReadinessService(provider=provider).fetch(request)
            cached_readiness = result.readiness
            if result.readiness.get("providerState") == "available":
                return result.readiness, self._build_source_metadata_from_fetch_source(
                    code=code,
                    source="local_us_parquet",
                )
        if not source_available and allow_runtime_probe:
            runtime_probe = self._probe_runtime_historical_ohlcv_readiness(
                request=request,
                code=code,
            )
            if runtime_probe is not None:
                return runtime_probe
            if cached_readiness is not None:
                return cached_readiness, stock_source_metadata
        result = HistoricalOhlcvReadinessService().assess_supplied_history(
            request,
            [self._stock_daily_to_ohlcv_bar(row) for row in rows],
            source_available=source_available,
            adjustments_available=None,
            unavailable_reason="provider_missing" if not source_available else None,
        )
        return result.readiness, stock_source_metadata

    def _probe_runtime_historical_ohlcv_readiness(
        self,
        *,
        request: HistoricalOhlcvReadinessRequest,
        code: str,
    ) -> tuple[Dict[str, Any], BacktestSourceMetadata] | None:
        days = max(1, int(request.lookback_bars or request.required_bars or 1))
        frame, source = fetch_daily_history_with_local_us_fallback(
            code,
            start_date=request.start,
            end_date=request.end,
            days=days,
            log_context="[backtest readiness]",
            allow_provider_fallback=True,
        )
        if frame is None or getattr(frame, "empty", True):
            return None
        benchmark_rows = None
        benchmark_source_available = None
        if request.benchmark_required and request.benchmark_symbol:
            benchmark_frame, _ = fetch_daily_history_with_local_us_fallback(
                request.benchmark_symbol,
                start_date=request.start,
                end_date=request.end,
                days=days,
                log_context="[backtest readiness benchmark]",
                allow_provider_fallback=True,
            )
            if benchmark_frame is None or getattr(benchmark_frame, "empty", True):
                benchmark_rows = []
                benchmark_source_available = False
            else:
                benchmark_rows = benchmark_frame.to_dict("records")
                benchmark_source_available = True
        readiness = HistoricalOhlcvReadinessService().assess_supplied_history(
            request,
            frame.to_dict("records"),
            benchmark_bars=benchmark_rows,
            benchmark_source_available=benchmark_source_available,
            source_available=True,
            adjustments_available=None,
        ).readiness
        return readiness, self._build_source_metadata_from_fetch_source(code=code, source=source)

    @staticmethod
    def _stock_daily_to_ohlcv_bar(row: StockDaily) -> Dict[str, Any]:
        return {
            "date": row.date,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume if row.volume is not None else 0.0,
        }

    @staticmethod
    def _sample_readiness_from_inputs(
        *,
        prepared_count: int,
        ohlcv_readiness: Dict[str, Any],
        sample_observability: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        reasons = [
            str(item)
            for item in (ohlcv_readiness.get("missingRequirements") or [])
            if str(item or "").strip()
        ]
        if prepared_count <= 0:
            reasons.append("samples_missing")
        deduped: List[str] = []
        for reason in reasons:
            if reason not in deduped:
                deduped.append(reason)
        if "provider_missing" in deduped:
            if "missing_cache" not in deduped:
                deduped.insert(0, "missing_cache")
            return "missing_cache", deduped
        if "insufficient_history" in deduped:
            return "insufficient_history", deduped
        if "entitlement_required" in deduped:
            return "blocked", deduped
        if "samples_missing" in deduped:
            if "no_samples" not in deduped:
                deduped.insert(0, "no_samples")
            return "no_samples", deduped
        if any(reason in deduped for reason in ("stale_data", "missing_benchmark", "missing_adjustments", "stale_or_incomplete_sample_window")):
            return "stale" if "stale_data" in deduped or "stale_or_incomplete_sample_window" in deduped else "blocked", deduped
        return "ready", deduped

    @staticmethod
    def _sample_execution_readiness(
        *,
        sample_state: str,
        sample_reasons: List[str],
        ohlcv_readiness: Dict[str, Any],
    ) -> Dict[str, Any]:
        reasons = [str(item) for item in sample_reasons if str(item or "").strip()]
        no_result_reason = None
        if "insufficient_history" in reasons:
            no_result_reason = "insufficient_history"
        elif "no_samples" in reasons or (
            "samples_missing" in reasons
            and not any(item in reasons for item in ("provider_missing", "entitlement_required"))
        ):
            no_result_reason = "no_samples"
        data_sufficiency = assess_backtest_data_sufficiency(
            {
                "no_result_reason": no_result_reason,
                "data_quality": {"historicalOhlcvReadiness": ohlcv_readiness},
            }
        )
        if sample_state == "ready":
            data_status = "ready"
            calculation_status = "ready"
            sample_status = "ready"
        elif any(item in reasons for item in ("provider_missing", "entitlement_required")):
            data_status = "provider_missing" if "provider_missing" in reasons else "entitlement_required"
            calculation_status = "calculation_unavailable"
            sample_status = data_status
        elif "insufficient_history" in reasons:
            data_status = "data_unavailable"
            calculation_status = "insufficient_sample"
            sample_status = "insufficient_sample"
        elif sample_state == "missing":
            data_status = "data_unavailable"
            calculation_status = "calculation_unavailable"
            sample_status = "data_unavailable"
        else:
            data_status = sample_state or "unknown"
            calculation_status = "degraded"
            sample_status = sample_state or "unknown"
        return build_execution_readiness_contract(
            {
                "no_result_reason": no_result_reason,
                "data_sufficiency": data_sufficiency,
            },
            data_status=data_status,
            calculation_status=calculation_status,
            sample_status=sample_status,
        )

    @staticmethod
    def _prefer_more_truthful_source_metadata(
        *,
        primary: BacktestSourceMetadata,
        fallback: BacktestSourceMetadata,
    ) -> BacktestSourceMetadata:
        if primary.resolved_source != "Unknown":
            return primary
        return fallback

    def _get_aggregate_sample_status(self, *, settings: BacktestRuntimeSettings) -> Dict[str, Any]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(AnalysisHistory).where(
                    and_(
                        AnalysisHistory.owner_id == self.db.require_user_id(self.owner_id),
                        AnalysisHistory.report_type == "backtest_sample",
                    )
                )
            ).scalars().all()
        parsed_dates: List[date] = []
        latest_created_at: Optional[datetime] = None
        for row in rows:
            parsed = self.repo.parse_analysis_date_from_snapshot(row.context_snapshot)
            if parsed:
                parsed_dates.append(parsed)
            if row.created_at and (latest_created_at is None or row.created_at > latest_created_at):
                latest_created_at = row.created_at
        symbol_specific_readiness = self._aggregate_symbol_readiness(settings=settings)
        readiness = self._build_aggregate_historical_ohlcv_readiness(
            settings=settings,
            symbol_specific_readiness=symbol_specific_readiness,
        )
        probe_policy = self._aggregate_probe_policy(symbol_specific_readiness=symbol_specific_readiness)
        write_policy = self._aggregate_write_policy()
        readiness["probePolicy"] = probe_policy
        readiness["writePolicy"] = write_policy
        state, reasons = self._aggregate_sample_readiness_from_inputs(
            prepared_count=len(rows),
            aggregate_readiness=readiness,
        )
        resolved_sources = [
            str(item.get("resolvedSource") or "")
            for item in symbol_specific_readiness
            if str(item.get("resolvedSource") or "").strip()
            and str(item.get("resolvedSource") or "").strip().lower() != "unknown"
        ]
        source_metadata = self._build_source_metadata_from_runtime_sources(
            code=None,
            runtime_sources=resolved_sources,
            fallback_used=len(set(resolved_sources)) > 1,
        )
        return {
            "code": "__all__",
            "scope": "aggregate",
            "prepared_count": len(rows),
            "prepared_start_date": min(parsed_dates).isoformat() if parsed_dates else None,
            "prepared_end_date": max(parsed_dates).isoformat() if parsed_dates else None,
            "latest_prepared_at": latest_created_at.isoformat() if latest_created_at else None,
            "latest_prepared_sample_date": max(parsed_dates).isoformat() if parsed_dates else None,
            "latest_eligible_sample_date": None,
            "excluded_recent_reason": "aggregate_status_without_symbol",
            "excluded_recent_message": "Aggregate sample status is safe for admin overview; pass code for symbol-specific readiness.",
            "eval_window_days": settings.eval_window_days,
            "min_age_days": settings.min_age_days,
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
            "requested_mode": "aggregate",
            "resolved_source": source_metadata.resolved_source,
            "fallback_used": source_metadata.fallback_used,
            "pricing_resolved_source": source_metadata.resolved_source,
            "pricing_fallback_used": source_metadata.fallback_used,
            "sample_readiness_state": state,
            "sample_blocking_reasons": reasons,
            "execution_readiness": self._sample_execution_readiness(
                sample_state=state,
                sample_reasons=reasons,
                ohlcv_readiness=readiness,
            ),
            "productReadModel": build_backtest_readiness_read_model(
                {
                    **readiness,
                    "preparedCount": len(rows),
                    "sampleReadinessState": state,
                    "samplesInitializing": len(rows) <= 0 and state == "no_samples",
                }
            ),
            "probePolicy": probe_policy,
            "writePolicy": write_policy,
            "historicalOhlcvReadiness": readiness,
            "symbolSpecificReadiness": symbol_specific_readiness,
        }

    def _aggregate_symbol_readiness(self, *, settings: BacktestRuntimeSettings) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        tier1_universe = resolve_us_ohlcv_coverage_universe(tier="tier1")
        symbols = (
            tuple(tier1_universe["symbols"])
            if tier1_universe.get("configured") is True
            else LOCAL_BACKTEST_STARTER_SYMBOLS
        )
        local_coverage = build_us_ohlcv_coverage_readiness(
            symbols=symbols,
            required_bars=settings.eval_window_days,
        )
        local_by_symbol = {
            str(item.get("symbol") or "").strip().upper(): item
            for item in local_coverage.get("symbols", [])
            if str(item.get("symbol") or "").strip()
        }
        for symbol in symbols:
            stock_rows = self._load_stock_daily_rows(symbol)
            readiness, source_metadata = self._build_historical_ohlcv_readiness_with_metadata(
                code=symbol,
                rows=stock_rows,
                required_bars=settings.eval_window_days,
                allow_runtime_probe=False,
            )
            normalized_state = self._normalize_symbol_readiness_state(
                readiness,
                local_coverage=local_by_symbol.get(symbol),
            )
            rows.append(
                {
                    "symbol": symbol,
                    "historicalOhlcvState": normalized_state,
                    "overallState": str(readiness.get("overallState") or "unknown"),
                    "providerState": str(readiness.get("providerState") or "unknown"),
                    "runtimeStatus": str(readiness.get("runtimeStatus") or "unknown"),
                    "resolvedSource": source_metadata.resolved_source,
                    "usableBars": int(readiness.get("usableBars") or 0),
                    "missingBars": int(readiness.get("missingBars") or 0),
                    "missingRequirements": list(readiness.get("missingRequirements") or []),
                    "runtimeProbeAllowed": False,
                    "runtimeProbeMode": "disabled_by_default",
                    "runtimeProbeSkippedReason": AGGREGATE_RUNTIME_PROBE_SKIPPED_REASON,
                    "cacheWritesAllowed": False,
                    "databaseWritesAllowed": False,
                    "consumerSafe": True,
                }
            )
        return rows

    @staticmethod
    def _aggregate_probe_policy(*, symbol_specific_readiness: List[Dict[str, Any]]) -> Dict[str, Any]:
        symbol_count = len(symbol_specific_readiness)
        return {
            "scope": "aggregate",
            "runtimeProbeMode": "disabled_by_default",
            "liveProviderProbingAllowed": False,
            "maxRuntimeProbeSymbols": 0,
            "evaluatedSymbols": symbol_count,
            "runtimeProbedSymbols": 0,
            "runtimeProbeSkippedSymbols": symbol_count,
            "runtimeProbeSkippedReason": AGGREGATE_RUNTIME_PROBE_SKIPPED_REASON,
            "readinessSources": ["existing_database_rows", "local_us_parquet_cache"],
            "consumerSafe": True,
        }

    @staticmethod
    def _single_symbol_probe_policy() -> Dict[str, Any]:
        return {
            "scope": "single",
            "runtimeProbeMode": SINGLE_SYMBOL_RUNTIME_PROBE_MODE,
            "liveProviderProbingAllowed": True,
            "maxRuntimeProbeSymbols": 1,
            "activeHydrationAllowed": False,
            "samplePreparationAllowed": False,
            "backtestExecutionAllowed": False,
            "readinessSources": [
                "existing_database_rows",
                "local_us_parquet_cache",
                SINGLE_SYMBOL_RUNTIME_PROBE_MODE,
            ],
            "consumerSafe": True,
        }

    @staticmethod
    def _single_symbol_write_policy() -> Dict[str, Any]:
        return {
            "scope": "single",
            "mode": "read_only",
            "cacheWritesAllowed": False,
            "databaseWritesAllowed": False,
            "consumerSafe": True,
        }

    @staticmethod
    def _aggregate_write_policy() -> Dict[str, Any]:
        return {
            "scope": "aggregate",
            "mode": "read_only",
            "cacheWritesAllowed": False,
            "databaseWritesAllowed": False,
            "consumerSafe": True,
        }

    def _build_aggregate_historical_ohlcv_readiness(
        self,
        *,
        settings: BacktestRuntimeSettings,
        symbol_specific_readiness: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        states = {
            "ready": [],
            "insufficient_history": [],
            "missing_cache": [],
            "provider_unavailable": [],
            "blocked": [],
        }
        missing_requirements: List[str] = []
        total_usable_bars = 0
        total_missing_bars = 0
        for item in symbol_specific_readiness:
            state = str(item.get("historicalOhlcvState") or "blocked")
            states.setdefault(state, []).append(str(item.get("symbol") or ""))
            total_usable_bars += int(item.get("usableBars") or 0)
            total_missing_bars += int(item.get("missingBars") or 0)
            for reason in item.get("missingRequirements") or []:
                normalized = str(reason or "").strip()
                if normalized and normalized not in missing_requirements:
                    missing_requirements.append(normalized)

        ready_count = len(states["ready"])
        insufficient_count = len(states["insufficient_history"])
        missing_count = len(states["missing_cache"])
        unavailable_count = len(states["provider_unavailable"])
        total = len(symbol_specific_readiness)

        if total > 0 and ready_count == total:
            overall_state = "all_available"
            provider_state = "available"
            runtime_status = "available"
        elif ready_count > 0:
            overall_state = "partial"
            provider_state = "partial"
            runtime_status = "available"
        elif unavailable_count > 0:
            overall_state = "provider_unavailable"
            provider_state = "provider_unavailable"
            runtime_status = "unavailable"
        elif missing_count == total and total > 0:
            overall_state = "missing_cache"
            provider_state = "missing_cache"
            runtime_status = "missing"
        elif insufficient_count == total and total > 0:
            overall_state = "insufficient_history"
            provider_state = "available"
            runtime_status = "insufficient_coverage"
        else:
            overall_state = "blocked"
            provider_state = "blocked"
            runtime_status = "unavailable"
        adjustment_state = "missing" if "missing_adjustments" in missing_requirements else "not_required"

        return {
            "contractVersion": "historical_ohlcv_readiness_v1",
            "symbol": "__ALL__",
            "market": "mixed",
            "timeframe": "1d",
            "requestedRange": {"start": None, "end": None},
            "lookbackBars": settings.eval_window_days,
            "requiredBars": settings.eval_window_days,
            "usableBars": total_usable_bars,
            "missingBars": total_missing_bars,
            "providerState": provider_state,
            "runtimeStatus": runtime_status,
            "overallState": overall_state,
            "adjustmentState": adjustment_state,
            "missingRequirements": missing_requirements,
            "symbolCount": total,
            "availableSymbols": states["ready"],
            "insufficientHistorySymbols": states["insufficient_history"],
            "missingCacheSymbols": states["missing_cache"],
            "providerUnavailableSymbols": states["provider_unavailable"],
            "consumerSafe": True,
        }

    @staticmethod
    def _aggregate_sample_readiness_from_inputs(
        *,
        prepared_count: int,
        aggregate_readiness: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        overall_state = str(aggregate_readiness.get("overallState") or "blocked")
        reasons = [
            str(item)
            for item in (aggregate_readiness.get("missingRequirements") or [])
            if str(item or "").strip()
        ]
        if prepared_count <= 0 and overall_state in {"all_available", "partial"} and "no_samples" not in reasons:
            reasons.insert(0, "no_samples")
        if overall_state == "all_available":
            return ("ready" if prepared_count > 0 else "no_samples"), reasons
        if overall_state == "partial":
            return ("partial" if prepared_count > 0 else "no_samples"), reasons
        if overall_state == "missing_cache":
            return "missing_cache", reasons
        if overall_state == "insufficient_history":
            return "insufficient_history", reasons
        return "blocked", reasons

    @staticmethod
    def _normalize_symbol_readiness_state(
        readiness: Dict[str, Any],
        *,
        local_coverage: Optional[Dict[str, Any]] = None,
    ) -> str:
        provider_state = str(readiness.get("providerState") or "").strip().lower()
        runtime_status = str(readiness.get("runtimeStatus") or "").strip().lower()
        missing_bars = int(readiness.get("missingBars") or 0)
        missing_requirements = {
            str(item or "").strip().lower()
            for item in (readiness.get("missingRequirements") or [])
            if str(item or "").strip()
        }
        if provider_state in {"provider_unavailable", "entitlement_required"}:
            return "provider_unavailable"
        if provider_state == "available" and missing_bars <= 0 and not missing_requirements:
            return "ready"
        if provider_state == "available" and (missing_bars > 0 or "insufficient_history" in missing_requirements):
            return "insufficient_history"
        if provider_state == "provider_missing":
            local_state = str((local_coverage or {}).get("overallState") or "").strip().lower()
            if runtime_status in {"missing", "not_configured"} or local_state == "missing_cache":
                return "missing_cache"
        if "insufficient_history" in missing_requirements:
            return "insufficient_history"
        return "blocked"

    def _try_fill_daily_data(self, *, code: str, analysis_date: date, eval_window_days: int) -> Optional[BacktestSourceMetadata]:
        try:
            # Fetch a window that covers the analysis bar plus the forward evaluation bars.
            end_date = analysis_date + timedelta(days=max(eval_window_days * 2, 30))
            df, source = fetch_daily_history_with_local_us_fallback(
                code,
                start_date=analysis_date,
                end_date=end_date,
                days=eval_window_days * 2,
                log_context="[historical-eval fill]",
                allow_provider_fallback=False,
            )
            if df is None or df.empty:
                return None
            authority = assess_backtest_data_source_eligibility(code=code, source=source)
            if authority.rejected:
                logger.warning(
                    "Rejected historical backtest fill source for %s: %s (%s)",
                    code,
                    source,
                    ",".join(authority.reason_codes),
                )
                return None
            self.db.save_daily_data(df, code=code, data_source=source)
            return self._build_source_metadata_from_fetch_source(code=code, source=source)
        except Exception as exc:
            logger.warning(f"补全历史分析评估日线数据失败({code}): {exc}")
            return None

    def _ensure_market_history(
        self,
        *,
        code: str,
        min_age_days: int,
        eval_window_days: int,
        sample_count: int,
        force_refresh: bool,
        allow_provider_fallback: bool,
    ) -> tuple[int, Optional[BacktestSourceMetadata]]:
        """Ensure enough market history exists for sample generation."""
        lookback_days = max(min_age_days + eval_window_days + sample_count + 30, 90)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=lookback_days)

        rows = self._load_stock_daily_rows(code)
        if force_refresh:
            rows = []

        if rows:
            earliest = rows[0].date
            latest = rows[-1].date
            if earliest <= start_date and latest >= end_date - timedelta(days=1):
                return 0, self._build_source_metadata_for_stock_rows(code=code, rows=rows, default_to_cache=True)

        try:
            df, source = fetch_daily_history_with_local_us_fallback(
                code,
                start_date=start_date,
                end_date=end_date,
                days=lookback_days,
                log_context="[historical-eval warmup]",
                allow_provider_fallback=allow_provider_fallback,
            )
            if df is None or df.empty:
                return 0, None
            authority = assess_backtest_data_source_eligibility(code=code, source=source)
            if authority.rejected:
                logger.warning(
                    "Rejected historical backtest warmup source for %s: %s (%s)",
                    code,
                    source,
                    ",".join(authority.reason_codes),
                )
                return 0, None
            saved_count = self.db.save_daily_data(df, code=code, data_source=source)
            return saved_count, self._build_source_metadata_from_fetch_source(code=code, source=source)
        except Exception as exc:
            logger.warning(f"准备历史分析评估样本时补全日线数据失败({code}): {exc}")
            return 0, None

    def _ensure_cached_backtest_samples(
        self,
        *,
        code: str,
        settings: BacktestRuntimeSettings,
        sample_count: int,
    ) -> Dict[str, Any]:
        """Create deterministic research-only samples from already cached bars."""
        normalized_code = self._require_code(code)
        existing_rows = self.repo.get_sample_rows(code=normalized_code, **self._owner_kwargs())
        if existing_rows:
            return {"prepared": 0, "skipped_existing": len(existing_rows), "candidate_rows": 0}

        rows = self._load_stock_daily_rows(normalized_code)
        candidate_rows = self._select_preparable_rows(rows, eval_window_days=settings.eval_window_days)
        if not candidate_rows:
            return {"prepared": 0, "skipped_existing": 0, "candidate_rows": 0}

        selected_rows = candidate_rows[-max(1, int(sample_count or 1)):]
        prepared = 0
        skipped_existing = 0
        now = datetime.now()
        resolved_owner_id = self.db.require_user_id(self.owner_id)
        with self.db.get_session() as session:
            for index, row_index in enumerate(selected_rows):
                row = rows[row_index]
                query_id = self._prepare_sample_query_id(normalized_code, row.date, settings.eval_window_days)
                existing = session.execute(
                    select(AnalysisHistory).where(
                        and_(
                            AnalysisHistory.query_id == query_id,
                            AnalysisHistory.owner_id == resolved_owner_id,
                        )
                    ).limit(1)
                ).scalar_one_or_none()
                if existing is not None:
                    skipped_existing += 1
                    continue
                sample = self._build_prepared_analysis_sample(
                    code=normalized_code,
                    row=row,
                    previous_close=rows[row_index - 1].close if row_index > 0 else None,
                    average_close=self._moving_average(rows, row_index, window=3),
                    min_age_days=settings.min_age_days,
                    eval_window_days=settings.eval_window_days,
                    created_at=now - timedelta(days=settings.min_age_days + 1 + index),
                    query_id=query_id,
                    owner_id=resolved_owner_id,
                )
                session.add(sample)
                prepared += 1
            session.commit()
        return {
            "prepared": prepared,
            "skipped_existing": skipped_existing,
            "candidate_rows": len(candidate_rows),
        }

    def _load_stock_daily_rows(self, code: str) -> List[StockDaily]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(StockDaily)
                .where(StockDaily.code == code)
                .order_by(StockDaily.date)
            ).scalars().all()
            return list(rows)

    @staticmethod
    def _select_preparable_rows(rows: List[StockDaily], *, eval_window_days: int) -> List[int]:
        if not rows:
            return []
        cutoff = max(0, len(rows) - int(eval_window_days))
        return [idx for idx in range(0, cutoff) if rows[idx].close is not None]

    @staticmethod
    def _prepare_sample_query_id(code: str, sample_date: date, eval_window_days: int) -> str:
        return f"bt-sample:{code}:{sample_date.isoformat()}:w{int(eval_window_days)}"

    def _build_prepared_analysis_sample(
        self,
        *,
        code: str,
        row: StockDaily,
        previous_close: Optional[float],
        average_close: Optional[float],
        min_age_days: int,
        eval_window_days: int,
        created_at: datetime,
        query_id: str,
        owner_id: str,
    ) -> AnalysisHistory:
        if row.close is None:
            operation_advice = "rule_simulation_flat"
            trend_prediction = "rule_simulation_flat"
            sentiment_score = 50
        else:
            trend_gap = 0.0
            if previous_close:
                trend_gap = (float(row.close) - float(previous_close)) / float(previous_close) * 100.0
            ma_gap = 0.0
            if average_close:
                ma_gap = (float(row.close) - float(average_close)) / float(average_close) * 100.0
            if trend_gap >= 1.5 or ma_gap >= 1.0:
                operation_advice = "rule_simulation_up"
                trend_prediction = "rule_momentum_up"
                sentiment_score = 72
            elif trend_gap <= -1.5 or ma_gap <= -1.0:
                operation_advice = "rule_simulation_down"
                trend_prediction = "rule_momentum_down"
                sentiment_score = 28
            else:
                operation_advice = "rule_simulation_flat"
                trend_prediction = "rule_momentum_flat"
                sentiment_score = 50

        stop_loss = None
        take_profit = None

        context_snapshot = {
            "enhanced_context": {
                "date": row.date.isoformat(),
                "market_session_date": row.date.isoformat(),
            }
        }

        raw_result = {
            "generated_for": "backtest_sample",
            "code": code,
            "analysis_date": row.date.isoformat(),
            "operation_advice": operation_advice,
            "trend_prediction": trend_prediction,
            "sentiment_score": sentiment_score,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "sample_source": "local_preparation",
            "sample_purpose": "rule_simulation_historical_sample_review",
            "market_data_source": row.data_source,
            "eval_window_days": eval_window_days,
            "evaluation_window_unit": "trading_bars",
            "min_age_days": min_age_days,
            "maturity_unit": "calendar_days",
        }

        return AnalysisHistory(
            owner_id=owner_id,
            query_id=query_id,
            code=code,
            name=code,
            report_type="backtest_sample",
            sentiment_score=sentiment_score,
            operation_advice=operation_advice,
            trend_prediction=trend_prediction,
            analysis_summary=(
                f"本地准备的规则模拟历史样本，基于 {row.date.isoformat()} 的缓存行情生成，仅用于研究复核。"
            ),
            raw_result=json.dumps(raw_result, ensure_ascii=False),
            news_content=None,
            context_snapshot=json.dumps(context_snapshot, ensure_ascii=False),
            ideal_buy=None,
            secondary_buy=None,
            stop_loss=stop_loss,
            take_profit=take_profit,
            created_at=created_at,
        )

    @staticmethod
    def _moving_average(rows: List[StockDaily], index: int, *, window: int = 3) -> Optional[float]:
        if index <= 0:
            return None
        start = max(0, index - window)
        closes = [float(row.close) for row in rows[start:index] if row.close is not None]
        if not closes:
            return None
        return sum(closes) / len(closes)

    def _prepared_sample_start_date(self, code: str) -> Optional[str]:
        rows = self.repo.get_sample_rows(code=code, **self._owner_kwargs())
        dates = [self.repo.parse_analysis_date_from_snapshot(row.context_snapshot) for row in rows]
        dates = [d for d in dates if d is not None]
        return min(dates).isoformat() if dates else None

    def _prepared_sample_end_date(self, code: str) -> Optional[str]:
        rows = self.repo.get_sample_rows(code=code, **self._owner_kwargs())
        dates = [self.repo.parse_analysis_date_from_snapshot(row.context_snapshot) for row in rows]
        dates = [d for d in dates if d is not None]
        return max(dates).isoformat() if dates else None

    def _latest_prepared_at(self, code: str) -> Optional[str]:
        rows = self.repo.get_sample_rows(code=code, **self._owner_kwargs())
        latest = None
        for row in rows:
            if row.created_at and (latest is None or row.created_at > latest):
                latest = row.created_at
        return latest.isoformat() if latest else None

    def _build_sample_observability(
        self,
        *,
        code: Optional[str],
        settings: BacktestRuntimeSettings,
        candidates: Optional[List[AnalysisHistory]] = None,
        sample_rows: Optional[List[AnalysisHistory]] = None,
        stock_rows: Optional[List[StockDaily]] = None,
    ) -> Dict[str, Any]:
        normalized_code = str(code or "").strip()
        if not normalized_code:
            return {
                "latest_prepared_sample_date": None,
                "latest_eligible_sample_date": None,
                "excluded_recent_reason": None,
                "excluded_recent_message": None,
            }

        sample_rows = sample_rows if sample_rows is not None else self.repo.get_sample_rows(
            code=normalized_code,
            **self._owner_kwargs(),
        )
        stock_rows = stock_rows if stock_rows is not None else self._load_stock_daily_rows(normalized_code)
        candidates = candidates if candidates is not None else self.repo.get_candidates(
            code=normalized_code,
            min_age_days=settings.min_age_days,
            limit=max(self.repo.count_analysis_history(code=normalized_code, **self._owner_kwargs()), 1),
            eval_window_days=settings.eval_window_days,
            engine_version=settings.engine_version,
            force=True,
            **self._owner_kwargs(),
        )

        prepared_dates = [
            parsed for parsed in
            (self.repo.parse_analysis_date_from_snapshot(row.context_snapshot) for row in sample_rows)
            if parsed is not None
        ]
        latest_prepared_sample_date = max(prepared_dates).isoformat() if prepared_dates else None

        eligible_dates = [
            parsed for parsed in
            (self._resolve_analysis_date(candidate) for candidate in candidates)
            if parsed is not None
        ]
        latest_eligible_sample_date = max(eligible_dates).isoformat() if eligible_dates else None

        latest_market_date = stock_rows[-1].date if stock_rows else None
        preparable_indexes = self._select_preparable_rows(stock_rows, eval_window_days=settings.eval_window_days)
        latest_preparable_market_date = stock_rows[preparable_indexes[-1]].date if preparable_indexes else None

        excluded_recent_reason: Optional[str] = None
        excluded_recent_message: Optional[str] = None
        if latest_prepared_sample_date and latest_eligible_sample_date and latest_prepared_sample_date > latest_eligible_sample_date:
            excluded_recent_reason = "maturity_window_not_satisfied"
            excluded_recent_message = (
                f"最新已准备样本到 {latest_prepared_sample_date}，但最近样本尚未满足 {settings.min_age_days} 天成熟期，"
                f"因此本次最新可评估日期只到 {latest_eligible_sample_date}。"
            )
        elif latest_market_date and latest_preparable_market_date and latest_market_date > latest_preparable_market_date:
            excluded_recent_reason = "evaluation_window_not_satisfied"
            excluded_recent_message = (
                f"最新行情到 {latest_market_date.isoformat()}，但评估需要完整的 {settings.eval_window_days} 根未来窗口，"
                f"所以最新可用于样本生成的日期只到 {latest_preparable_market_date.isoformat()}。"
            )
        elif latest_market_date and latest_prepared_sample_date and latest_market_date.isoformat() > latest_prepared_sample_date:
            excluded_recent_reason = "no_newer_analysis_samples"
            excluded_recent_message = (
                f"最新行情到 {latest_market_date.isoformat()}，但没有更晚日期的历史分析样本，"
                f"所以当前已准备样本只到 {latest_prepared_sample_date}。"
            )

        return {
            "latest_prepared_sample_date": latest_prepared_sample_date,
            "latest_eligible_sample_date": latest_eligible_sample_date,
            "excluded_recent_reason": excluded_recent_reason,
            "excluded_recent_message": excluded_recent_message,
        }

    def _recompute_global_summaries_if_needed(self) -> None:
        config = get_config()
        eval_window_days = int(getattr(config, "backtest_eval_window_days", 10))
        engine_version = str(getattr(config, "backtest_engine_version", "v1"))
        self._recompute_summaries_for_window(eval_window_days=eval_window_days, engine_version=engine_version)

    def _recompute_summaries_for_window(self, *, eval_window_days: int, engine_version: str) -> None:
        resolved_owner_id = self.db.require_user_id(self.owner_id)
        with self.db.get_session() as session:
            overall_rows = session.execute(
                select(BacktestResult).where(
                    and_(
                        BacktestResult.owner_id == resolved_owner_id,
                        BacktestResult.eval_window_days == eval_window_days,
                        BacktestResult.engine_version == engine_version,
                    )
                )
            ).scalars().all()
            if not overall_rows:
                self.repo.delete_all_summaries_for_window(
                    eval_window_days=eval_window_days,
                    engine_version=engine_version,
                    owner_id=resolved_owner_id,
                )
                return
            overall_data = BacktestEngine.compute_summary(
                results=overall_rows,
                scope="overall",
                code=OVERALL_SENTINEL_CODE,
                eval_window_days=eval_window_days,
                engine_version=engine_version,
            )
            overall_data.update(self._build_source_metadata_for_result_rows(overall_rows, code=None))
            overall_summary = self._build_summary_model(overall_data, owner_id=resolved_owner_id)
            self.repo.upsert_summary(overall_summary)

            codes = self.repo.list_backtest_codes(
                eval_window_days=eval_window_days,
                engine_version=engine_version,
                owner_id=resolved_owner_id,
            )
            for code in codes:
                rows = session.execute(
                    select(BacktestResult).where(
                        and_(
                            BacktestResult.owner_id == resolved_owner_id,
                            BacktestResult.code == code,
                            BacktestResult.eval_window_days == eval_window_days,
                            BacktestResult.engine_version == engine_version,
                        )
                    )
                ).scalars().all()
                data = BacktestEngine.compute_summary(
                    results=rows,
                    scope="stock",
                    code=code,
                    eval_window_days=eval_window_days,
                    engine_version=engine_version,
                )
                data.update(self._build_source_metadata_for_result_rows(rows, code=code))
                summary = self._build_summary_model(data, owner_id=resolved_owner_id)
                self.repo.upsert_summary(summary)

    def _recompute_summaries(self, *, touched_codes: List[str], eval_window_days: int, engine_version: str) -> None:
        resolved_owner_id = self.db.require_user_id(self.owner_id)
        with self.db.get_session() as session:
            # overall
            overall_rows = session.execute(
                select(BacktestResult).where(
                    and_(
                        BacktestResult.owner_id == resolved_owner_id,
                        BacktestResult.eval_window_days == eval_window_days,
                        BacktestResult.engine_version == engine_version,
                    )
                )
            ).scalars().all()
            overall_data = BacktestEngine.compute_summary(
                results=overall_rows,
                scope="overall",
                code=OVERALL_SENTINEL_CODE,
                eval_window_days=eval_window_days,
                engine_version=engine_version,
            )
            overall_data.update(self._build_source_metadata_for_result_rows(overall_rows, code=None))
            overall_summary = self._build_summary_model(overall_data, owner_id=resolved_owner_id)
            self.repo.upsert_summary(overall_summary)

            for code in touched_codes:
                rows = session.execute(
                    select(BacktestResult).where(
                        and_(
                            BacktestResult.owner_id == resolved_owner_id,
                            BacktestResult.code == code,
                            BacktestResult.eval_window_days == eval_window_days,
                            BacktestResult.engine_version == engine_version,
                        )
                    )
                ).scalars().all()
                data = BacktestEngine.compute_summary(
                    results=rows,
                    scope="stock",
                    code=code,
                    eval_window_days=eval_window_days,
                    engine_version=engine_version,
                )
                data.update(self._build_source_metadata_for_result_rows(rows, code=code))
                summary = self._build_summary_model(data, owner_id=resolved_owner_id)
                self.repo.upsert_summary(summary)

    @staticmethod
    def _build_summary_model(summary_data: Dict[str, Any], *, owner_id: str) -> BacktestSummary:
        diagnostics = dict(summary_data.get("diagnostics") or {})
        for key in ("requested_mode", "resolved_source", "fallback_used"):
            if key in summary_data:
                diagnostics[key] = summary_data.get(key)
        return BacktestSummary(
            owner_id=owner_id,
            scope=summary_data.get("scope"),
            code=summary_data.get("code"),
            eval_window_days=summary_data.get("eval_window_days"),
            engine_version=summary_data.get("engine_version"),
            computed_at=datetime.now(),
            total_evaluations=summary_data.get("total_evaluations") or 0,
            completed_count=summary_data.get("completed_count") or 0,
            insufficient_count=summary_data.get("insufficient_count") or 0,
            long_count=summary_data.get("long_count") or 0,
            cash_count=summary_data.get("cash_count") or 0,
            win_count=summary_data.get("win_count") or 0,
            loss_count=summary_data.get("loss_count") or 0,
            neutral_count=summary_data.get("neutral_count") or 0,
            direction_accuracy_pct=summary_data.get("direction_accuracy_pct"),
            win_rate_pct=summary_data.get("win_rate_pct"),
            neutral_rate_pct=summary_data.get("neutral_rate_pct"),
            avg_stock_return_pct=summary_data.get("avg_stock_return_pct"),
            avg_simulated_return_pct=summary_data.get("avg_simulated_return_pct"),
            stop_loss_trigger_rate=summary_data.get("stop_loss_trigger_rate"),
            take_profit_trigger_rate=summary_data.get("take_profit_trigger_rate"),
            ambiguous_rate=summary_data.get("ambiguous_rate"),
            avg_days_to_first_hit=summary_data.get("avg_days_to_first_hit"),
            advice_breakdown_json=json.dumps(summary_data.get("advice_breakdown") or {}, ensure_ascii=False),
            diagnostics_json=json.dumps(diagnostics, ensure_ascii=False),
        )

    def _result_to_dict(self, row: BacktestResult) -> Dict[str, Any]:
        assumptions = self._signal_evaluation_assumptions()
        market_data_sources = self._collect_market_data_sources(
            code=row.code,
            analysis_date=row.analysis_date,
            eval_window_days=row.eval_window_days,
        )
        data_quality = self._standard_result_data_quality(
            code=row.code,
            analysis_date=row.analysis_date,
            eval_window_days=row.eval_window_days,
            market_data_sources=market_data_sources,
        )
        historical_ohlcv_readiness = self._build_historical_ohlcv_readiness(
            code=row.code,
            rows=self._standard_result_ohlcv_rows(
                code=row.code,
                analysis_date=row.analysis_date,
                eval_window_days=row.eval_window_days,
            ),
            required_bars=row.eval_window_days,
            allow_runtime_probe=False,
        )
        data_quality["historicalOhlcvReadiness"] = historical_ohlcv_readiness
        data_sufficiency = assess_backtest_data_sufficiency(
            {
                "status": row.eval_status,
                "no_result_reason": (
                    "insufficient_history"
                    if str(row.eval_status or "").strip().lower() == "insufficient_data"
                    else None
                ),
                "data_quality": data_quality,
            }
        )
        payload = {
            "analysis_history_id": row.analysis_history_id,
            "code": row.code,
            "analysis_date": row.analysis_date.isoformat() if row.analysis_date else None,
            "eval_window_days": row.eval_window_days,
            "evaluation_window_trading_bars": row.eval_window_days,
            "engine_version": row.engine_version,
            "eval_status": row.eval_status,
            "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
            "operation_advice": row.operation_advice,
            "position_recommendation": row.position_recommendation,
            "start_price": row.start_price,
            "end_close": row.end_close,
            "max_high": row.max_high,
            "min_low": row.min_low,
            "stock_return_pct": row.stock_return_pct,
            "direction_expected": row.direction_expected,
            "direction_correct": row.direction_correct,
            "outcome": row.outcome,
            "stop_loss": row.stop_loss,
            "take_profit": row.take_profit,
            "hit_stop_loss": row.hit_stop_loss,
            "hit_take_profit": row.hit_take_profit,
            "first_hit": row.first_hit,
            "first_hit_date": row.first_hit_date.isoformat() if row.first_hit_date else None,
            "first_hit_trading_days": row.first_hit_trading_days,
            "simulated_entry_price": row.simulated_entry_price,
            "simulated_exit_price": row.simulated_exit_price,
            "simulated_exit_reason": row.simulated_exit_reason,
            "simulated_return_pct": row.simulated_return_pct,
            "market_data_sources": market_data_sources,
            "data_quality": data_quality,
            "data_sufficiency": data_sufficiency,
            "historicalOhlcvReadiness": historical_ohlcv_readiness,
            "execution_assumptions": assumptions,
        }
        payload.update(build_standard_result_contract(payload))
        return payload

    def _run_to_dict(self, row: BacktestRun) -> Dict[str, Any]:
        summary = {}
        if getattr(row, "summary_json", None):
            try:
                summary = json.loads(row.summary_json)
            except Exception:
                summary = {}
        payload = {
            "id": row.id,
            "code": row.code,
            "eval_window_days": row.eval_window_days,
            "evaluation_window_trading_bars": row.eval_window_days,
            "min_age_days": row.min_age_days,
            "maturity_calendar_days": row.min_age_days,
            "force": bool(row.force),
            "run_at": row.run_at.isoformat() if row.run_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "processed": row.processed,
            "saved": row.saved,
            "completed": row.completed,
            "insufficient": row.insufficient,
            "errors": row.errors,
            "candidate_count": row.candidate_count,
            "result_count": row.result_count,
            "no_result_reason": row.no_result_reason,
            "no_result_message": row.no_result_message,
            "status": row.status,
            "total_evaluations": row.total_evaluations,
            "completed_count": row.completed_count,
            "insufficient_count": row.insufficient_count,
            "long_count": row.long_count,
            "cash_count": row.cash_count,
            "win_count": row.win_count,
            "loss_count": row.loss_count,
            "neutral_count": row.neutral_count,
            "win_rate_pct": row.win_rate_pct,
            "avg_stock_return_pct": row.avg_stock_return_pct,
            "avg_simulated_return_pct": row.avg_simulated_return_pct,
            "direction_accuracy_pct": row.direction_accuracy_pct,
            "summary": summary,
            "evaluation_mode": "historical_analysis_evaluation",
            "requested_mode": summary.get("requested_mode"),
            "resolved_source": summary.get("resolved_source"),
            "fallback_used": summary.get("fallback_used"),
            "execution_assumptions": self._signal_evaluation_assumptions(),
        }
        payload.update(build_standard_run_contract(payload))
        return payload

    def _summary_to_dict(self, row: BacktestSummary) -> Dict[str, Any]:
        diagnostics = json.loads(row.diagnostics_json) if row.diagnostics_json else {}
        payload = {
            "scope": row.scope,
            "code": None if row.code == OVERALL_SENTINEL_CODE else row.code,
            "eval_window_days": row.eval_window_days,
            "evaluation_window_trading_bars": row.eval_window_days,
            "engine_version": row.engine_version,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
            "total_evaluations": row.total_evaluations,
            "completed_count": row.completed_count,
            "insufficient_count": row.insufficient_count,
            "long_count": row.long_count,
            "cash_count": row.cash_count,
            "win_count": row.win_count,
            "loss_count": row.loss_count,
            "neutral_count": row.neutral_count,
            "direction_accuracy_pct": row.direction_accuracy_pct,
            "win_rate_pct": row.win_rate_pct,
            "neutral_rate_pct": row.neutral_rate_pct,
            "avg_stock_return_pct": row.avg_stock_return_pct,
            "avg_simulated_return_pct": row.avg_simulated_return_pct,
            "stop_loss_trigger_rate": row.stop_loss_trigger_rate,
            "take_profit_trigger_rate": row.take_profit_trigger_rate,
            "ambiguous_rate": row.ambiguous_rate,
            "avg_days_to_first_hit": row.avg_days_to_first_hit,
            "advice_breakdown": json.loads(row.advice_breakdown_json) if row.advice_breakdown_json else {},
            "diagnostics": diagnostics,
            "evaluation_mode": "historical_analysis_evaluation",
            "requested_mode": diagnostics.get("requested_mode"),
            "resolved_source": diagnostics.get("resolved_source"),
            "fallback_used": diagnostics.get("fallback_used"),
            "execution_assumptions": self._signal_evaluation_assumptions(),
        }
        payload.update(build_performance_contract(payload))
        return payload

    @staticmethod
    def _requested_mode_for_code(code: Optional[str]) -> str:
        normalized_code = str(code or "").strip().upper()
        if normalized_code and normalized_code.isascii() and normalized_code.isalpha():
            return "local_first"
        return "auto"

    @staticmethod
    def _normalize_resolved_source_label(source: Optional[str]) -> Optional[str]:
        normalized = str(source or "").strip()
        if not normalized:
            return None
        lower = normalized.lower()
        if lower == "alpacafetcher":
            return "AlpacaFetcher"
        if lower == "databasecache":
            return "DatabaseCache"
        if lower in {"local_us_parquet", "localparquet"} or "parquet" in lower or "stooq" in lower:
            return "LocalParquet"
        if "yfinance" in lower:
            return "YfinanceFetcher"
        if "cache" in lower or lower.startswith("db_") or lower == "db":
            return "DatabaseCache"
        return "ProviderAPI"

    def _build_source_metadata_from_fetch_source(self, *, code: str, source: Optional[str]) -> BacktestSourceMetadata:
        requested_mode = self._requested_mode_for_code(code)
        normalized_source = self._normalize_resolved_source_label(source) or "Unknown"
        fallback_used = requested_mode == "local_first" and normalized_source != "LocalParquet"
        return BacktestSourceMetadata(
            requested_mode=requested_mode,
            resolved_source=normalized_source,
            fallback_used=fallback_used,
        )

    def _build_source_metadata_from_runtime_sources(
        self,
        *,
        code: Optional[str],
        runtime_sources: List[str],
        fallback_used: bool,
    ) -> BacktestSourceMetadata:
        requested_mode = self._requested_mode_for_code(code)
        unique_sources: List[str] = []
        for source in runtime_sources:
            normalized = self._normalize_resolved_source_label(source) or source
            if normalized and normalized not in unique_sources:
                unique_sources.append(normalized)
        if not unique_sources:
            resolved_source = "Unknown"
        elif len(unique_sources) == 1:
            resolved_source = unique_sources[0]
        else:
            resolved_source = "MixedFallback"
            fallback_used = True
        return BacktestSourceMetadata(
            requested_mode=requested_mode,
            resolved_source=resolved_source,
            fallback_used=bool(fallback_used),
        )

    def _build_source_metadata_for_stock_rows(
        self,
        *,
        code: str,
        rows: List[StockDaily],
        default_to_cache: bool,
    ) -> BacktestSourceMetadata:
        sources = [str(row.data_source) for row in rows if getattr(row, "data_source", None)]
        if default_to_cache and not sources:
            return self._build_source_metadata_from_runtime_sources(
                code=code,
                runtime_sources=["DatabaseCache"],
                fallback_used=False,
            )
        return self._build_source_metadata_from_runtime_sources(
            code=code,
            runtime_sources=sources,
            fallback_used=len(set(sources)) > 1,
        )

    def _build_source_metadata_for_samples(
        self,
        *,
        code: str,
        sample_rows: List[AnalysisHistory],
    ) -> BacktestSourceMetadata:
        sources: List[str] = []
        for row in sample_rows:
            try:
                raw = json.loads(row.raw_result) if row.raw_result else {}
            except Exception:
                raw = {}
            value = raw.get("market_data_source")
            if value:
                sources.append(str(value))
        if sample_rows and not sources:
            return self._build_source_metadata_from_runtime_sources(
                code=code,
                runtime_sources=["DatabaseCache"],
                fallback_used=False,
            )
        return self._build_source_metadata_from_runtime_sources(
            code=code,
            runtime_sources=sources,
            fallback_used=len(set(sources)) > 1,
        )

    def _build_source_metadata_for_result_rows(
        self,
        rows: List[BacktestResult],
        *,
        code: Optional[str],
    ) -> Dict[str, Any]:
        runtime_sources: List[str] = []
        for row in rows:
            runtime_sources.extend(
                self._collect_market_data_sources(
                    code=row.code,
                    analysis_date=row.analysis_date,
                    eval_window_days=row.eval_window_days,
                )
            )
        metadata = self._build_source_metadata_from_runtime_sources(
            code=code,
            runtime_sources=runtime_sources if runtime_sources else (["DatabaseCache"] if rows else []),
            fallback_used=len(set(runtime_sources)) > 1,
        )
        return {
            "requested_mode": metadata.requested_mode,
            "resolved_source": metadata.resolved_source,
            "fallback_used": metadata.fallback_used,
        }

    @staticmethod
    def _normalize_learning_summary(summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Normalize summary metrics to the ratio-based shape expected by Agent memory."""
        if summary is None:
            return None

        normalized = dict(summary)
        normalized["win_rate"] = BacktestService._pct_to_ratio(summary.get("win_rate_pct"), default=0.5)
        normalized["direction_accuracy"] = BacktestService._pct_to_ratio(
            summary.get("direction_accuracy_pct"),
            default=0.5,
        )

        avg_return_pct = summary.get("avg_simulated_return_pct")
        if avg_return_pct is None:
            avg_return_pct = summary.get("avg_stock_return_pct")
        normalized["avg_return"] = BacktestService._pct_to_ratio(avg_return_pct, default=0.0)
        return normalized

    @staticmethod
    def _pct_to_ratio(value: Optional[float], default: float = 0.0) -> float:
        try:
            return float(value) / 100.0
        except (TypeError, ValueError):
            return default
