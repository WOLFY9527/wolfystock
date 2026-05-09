# -*- coding: utf-8 -*-
"""Repository helpers for AI-assisted rule backtests."""

from __future__ import annotations

import json
from typing import Any, List, Optional, Tuple

from sqlalchemy import and_, delete, desc, func, select

from src.storage import (
    DatabaseManager,
    RuleBacktestRun,
    RuleBacktestTrade,
    RuleBacktestUniverseJob,
    RuleBacktestUniverseSymbolResult,
)


class RuleBacktestRepository:
    """Database access for rule backtest runs and trades."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def save_run(self, run: RuleBacktestRun) -> RuleBacktestRun:
        run.owner_id = self.db.require_user_id(getattr(run, "owner_id", None))
        with self.db.get_session() as session:
            session.add(run)
            session.commit()
            session.refresh(run)
        if getattr(run, "id", None) is not None:
            self.db.sync_phase_e_rule_backtest_shadow(int(run.id))
        return run

    def update_run(
        self,
        run_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
        **fields: Any,
    ) -> Optional[RuleBacktestRun]:
        with self.db.get_session() as session:
            conditions = [RuleBacktestRun.id == run_id]
            if not include_all_owners:
                conditions.append(RuleBacktestRun.owner_id == self.db.require_user_id(owner_id))
            row = session.execute(
                select(RuleBacktestRun).where(and_(*conditions)).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            for key, value in fields.items():
                setattr(row, key, value)
            session.commit()
            session.refresh(row)
        self.db.sync_phase_e_rule_backtest_shadow(int(run_id))
        return row

    def save_trades(self, trades: List[RuleBacktestTrade]) -> int:
        if not trades:
            return 0
        run_ids = sorted({int(trade.run_id) for trade in trades if getattr(trade, "run_id", None) is not None})
        with self.db.get_session() as session:
            session.add_all(trades)
            session.commit()
        for run_id in run_ids:
            self.db.sync_phase_e_rule_backtest_shadow(int(run_id))
        return len(trades)

    def get_run(
        self,
        run_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[RuleBacktestRun]:
        with self.db.get_session() as session:
            conditions = [RuleBacktestRun.id == run_id]
            if not include_all_owners:
                conditions.append(RuleBacktestRun.owner_id == self.db.require_user_id(owner_id))
            return session.execute(
                select(RuleBacktestRun).where(and_(*conditions)).limit(1)
            ).scalar_one_or_none()

    def get_runs_by_ids(
        self,
        run_ids: List[int],
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[RuleBacktestRun]:
        normalized_ids = [int(value) for value in run_ids if value is not None]
        if not normalized_ids:
            return []
        with self.db.get_session() as session:
            conditions = [RuleBacktestRun.id.in_(normalized_ids)]
            if not include_all_owners:
                conditions.append(RuleBacktestRun.owner_id == self.db.require_user_id(owner_id))
            rows = session.execute(
                select(RuleBacktestRun).where(and_(*conditions))
            ).scalars().all()
            return list(rows)

    def get_runs_paginated(
        self,
        *,
        code: Optional[str] = None,
        offset: int,
        limit: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Tuple[List[RuleBacktestRun], int]:
        with self.db.get_session() as session:
            conditions = []
            if not include_all_owners:
                conditions.append(RuleBacktestRun.owner_id == self.db.require_user_id(owner_id))
            if code:
                conditions.append(RuleBacktestRun.code == code)
            where_clause = and_(*conditions) if conditions else True

            total = session.execute(
                select(func.count(RuleBacktestRun.id)).where(where_clause)
            ).scalar() or 0
            rows = session.execute(
                select(RuleBacktestRun)
                .where(where_clause)
                .order_by(desc(RuleBacktestRun.run_at))
                .offset(offset)
                .limit(limit)
            ).scalars().all()
            return list(rows), int(total)

    def get_trades_by_run(self, run_id: int) -> List[RuleBacktestTrade]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(RuleBacktestTrade)
                .where(RuleBacktestTrade.run_id == run_id)
                .order_by(RuleBacktestTrade.trade_index.asc())
            ).scalars().all()
            return list(rows)

    def get_trade_run_ids(self, run_ids: List[int]) -> set[int]:
        normalized_ids = sorted({int(value) for value in run_ids if value is not None})
        if not normalized_ids:
            return set()
        with self.db.get_session() as session:
            rows = session.execute(
                select(RuleBacktestTrade.run_id)
                .where(RuleBacktestTrade.run_id.in_(normalized_ids))
                .group_by(RuleBacktestTrade.run_id)
            ).scalars().all()
            return {int(value) for value in rows if value is not None}

    def delete_runs_by_code(
        self,
        *,
        code: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        resolved_owner_id = None if include_all_owners else self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            conditions = [RuleBacktestRun.code == code]
            if not include_all_owners:
                conditions.append(RuleBacktestRun.owner_id == resolved_owner_id)
            deleted = session.execute(
                delete(RuleBacktestRun).where(and_(*conditions))
            ).rowcount or 0
            session.commit()
        self.db.delete_phase_e_rule_backtest_shadow_by_code(
            code=code,
            owner_id=resolved_owner_id,
            include_all_owners=include_all_owners,
        )
        return int(deleted)

    def delete_trades_by_run_ids(self, run_ids: List[int]) -> int:
        if not run_ids:
            return 0
        with self.db.get_session() as session:
            deleted = session.execute(
                delete(RuleBacktestTrade).where(RuleBacktestTrade.run_id.in_(run_ids))
            ).rowcount or 0
            session.commit()
        for run_id in sorted({int(value) for value in run_ids}):
            self.db.sync_phase_e_rule_backtest_shadow(int(run_id))
        return int(deleted)

    def save_universe_job(
        self,
        job: RuleBacktestUniverseJob,
        symbol_results: List[RuleBacktestUniverseSymbolResult],
    ) -> RuleBacktestUniverseJob:
        job.owner_id = self.db.require_user_id(getattr(job, "owner_id", None))
        for result in symbol_results:
            result.owner_id = job.owner_id
        with self.db.get_session() as session:
            session.add(job)
            session.flush()
            for result in symbol_results:
                result.job_id = int(job.id)
                session.add(result)
            session.commit()
            session.refresh(job)
        return job

    def get_universe_job(
        self,
        job_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[RuleBacktestUniverseJob]:
        with self.db.get_session() as session:
            conditions = [RuleBacktestUniverseJob.id == int(job_id)]
            if not include_all_owners:
                conditions.append(RuleBacktestUniverseJob.owner_id == self.db.require_user_id(owner_id))
            return session.execute(
                select(RuleBacktestUniverseJob).where(and_(*conditions)).limit(1)
            ).scalar_one_or_none()

    def get_universe_job_summary(
        self,
        job_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> dict[str, Any]:
        with self.db.get_session() as session:
            conditions = [RuleBacktestUniverseSymbolResult.job_id == int(job_id)]
            if not include_all_owners:
                conditions.append(RuleBacktestUniverseSymbolResult.owner_id == self.db.require_user_id(owner_id))
            where_clause = and_(*conditions)
            total = session.execute(
                select(func.count(RuleBacktestUniverseSymbolResult.id)).where(where_clause)
            ).scalar() or 0
            status_rows = session.execute(
                select(
                    RuleBacktestUniverseSymbolResult.status,
                    func.count(RuleBacktestUniverseSymbolResult.id),
                )
                .where(where_clause)
                .group_by(RuleBacktestUniverseSymbolResult.status)
            ).all()
            return {
                "total": int(total),
                "status_counts": {
                    str(status or "unknown"): int(count or 0)
                    for status, count in status_rows
                },
            }

    def get_universe_job_reason_summary(
        self,
        job_id: int,
        *,
        sample_limit: int = 5,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[dict[str, Any]]:
        with self.db.get_session() as session:
            conditions = [
                RuleBacktestUniverseSymbolResult.job_id == int(job_id),
                RuleBacktestUniverseSymbolResult.reason_code.is_not(None),
            ]
            if not include_all_owners:
                conditions.append(RuleBacktestUniverseSymbolResult.owner_id == self.db.require_user_id(owner_id))
            where_clause = and_(*conditions)
            grouped = session.execute(
                select(
                    RuleBacktestUniverseSymbolResult.reason_code,
                    func.count(RuleBacktestUniverseSymbolResult.id).label("reason_count"),
                )
                .where(where_clause)
                .group_by(RuleBacktestUniverseSymbolResult.reason_code)
                .order_by(desc("reason_count"), RuleBacktestUniverseSymbolResult.reason_code.asc())
            ).all()
            buckets: List[dict[str, Any]] = []
            for reason_code, count in grouped:
                sample_conditions = [
                    RuleBacktestUniverseSymbolResult.job_id == int(job_id),
                    RuleBacktestUniverseSymbolResult.reason_code == reason_code,
                ]
                if not include_all_owners:
                    sample_conditions.append(RuleBacktestUniverseSymbolResult.owner_id == self.db.require_user_id(owner_id))
                samples = session.execute(
                    select(RuleBacktestUniverseSymbolResult.symbol)
                    .where(and_(*sample_conditions))
                    .order_by(RuleBacktestUniverseSymbolResult.sequence_index.asc())
                    .limit(max(1, int(sample_limit or 5)))
                ).scalars().all()
                buckets.append(
                    {
                        "reason_code": str(reason_code or "unknown"),
                        "count": int(count or 0),
                        "sample_symbols": [str(symbol) for symbol in samples],
                    }
                )
            return buckets

    def get_universe_job_metric_extremes(
        self,
        job_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[RuleBacktestUniverseSymbolResult]:
        return self.get_universe_symbol_results(
            job_id,
            owner_id=owner_id,
            include_all_owners=include_all_owners,
        )

    def get_universe_symbol_results_paginated(
        self,
        job_id: int,
        *,
        offset: int,
        limit: int,
        status: Optional[str] = None,
        reason_code: Optional[str] = None,
        symbol: Optional[str] = None,
        sort: str = "sequence_index",
        order: str = "asc",
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Tuple[List[RuleBacktestUniverseSymbolResult], int]:
        normalized_sort = str(sort or "sequence_index").strip().lower()
        normalized_order = str(order or "asc").strip().lower()
        if normalized_order not in {"asc", "desc"}:
            raise ValueError("order must be asc or desc")
        sql_sort_columns = {
            "sequence_index": RuleBacktestUniverseSymbolResult.sequence_index,
            "elapsed_ms": RuleBacktestUniverseSymbolResult.runtime_ms,
            "runtime_ms": RuleBacktestUniverseSymbolResult.runtime_ms,
            "symbol": RuleBacktestUniverseSymbolResult.symbol,
            "status": RuleBacktestUniverseSymbolResult.status,
        }
        metric_sorts = {
            "total_return_pct",
            "max_drawdown_pct",
            "win_rate_pct",
            "trades_count",
        }
        if normalized_sort not in sql_sort_columns and normalized_sort not in metric_sorts:
            raise ValueError(f"unsupported universe result sort: {sort}")

        with self.db.get_session() as session:
            conditions = [RuleBacktestUniverseSymbolResult.job_id == int(job_id)]
            if not include_all_owners:
                conditions.append(RuleBacktestUniverseSymbolResult.owner_id == self.db.require_user_id(owner_id))
            if status:
                conditions.append(RuleBacktestUniverseSymbolResult.status == str(status).strip())
            if reason_code:
                conditions.append(RuleBacktestUniverseSymbolResult.reason_code == str(reason_code).strip())
            if symbol:
                pattern = f"{str(symbol).strip().upper()}%"
                conditions.append(RuleBacktestUniverseSymbolResult.symbol.like(pattern))
            where_clause = and_(*conditions)
            total = session.execute(
                select(func.count(RuleBacktestUniverseSymbolResult.id)).where(where_clause)
            ).scalar() or 0
            if normalized_sort in metric_sorts:
                rows = session.execute(
                    select(RuleBacktestUniverseSymbolResult)
                    .where(where_clause)
                    .order_by(RuleBacktestUniverseSymbolResult.sequence_index.asc())
                ).scalars().all()
                sorted_rows = sorted(
                    list(rows),
                    key=lambda row: (
                        self._metric_sort_value(row.metrics_json, normalized_sort, normalized_order),
                        int(row.sequence_index),
                    ),
                    reverse=normalized_order == "desc",
                )
                return sorted_rows[offset:offset + limit], int(total)

            sort_column = sql_sort_columns[normalized_sort]
            order_expr = sort_column.desc() if normalized_order == "desc" else sort_column.asc()
            rows = session.execute(
                select(RuleBacktestUniverseSymbolResult)
                .where(where_clause)
                .order_by(order_expr, RuleBacktestUniverseSymbolResult.sequence_index.asc())
                .offset(offset)
                .limit(limit)
            ).scalars().all()
            return list(rows), int(total)

    @staticmethod
    def _metric_sort_value(metrics_json: Optional[str], field_name: str, order: str) -> float:
        try:
            payload = json.loads(metrics_json or "{}")
        except (TypeError, ValueError):
            payload = {}
        value = payload.get(field_name) if isinstance(payload, dict) else None
        if value is None:
            return float("-inf") if order == "desc" else float("inf")
        try:
            return float(value)
        except (TypeError, ValueError):
            return float("-inf") if order == "desc" else float("inf")

    def get_universe_symbol_results(
        self,
        job_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[RuleBacktestUniverseSymbolResult]:
        with self.db.get_session() as session:
            conditions = [RuleBacktestUniverseSymbolResult.job_id == int(job_id)]
            if not include_all_owners:
                conditions.append(RuleBacktestUniverseSymbolResult.owner_id == self.db.require_user_id(owner_id))
            rows = session.execute(
                select(RuleBacktestUniverseSymbolResult)
                .where(and_(*conditions))
                .order_by(RuleBacktestUniverseSymbolResult.sequence_index.asc())
            ).scalars().all()
            return list(rows)

    def update_universe_job(
        self,
        job_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
        **fields: Any,
    ) -> Optional[RuleBacktestUniverseJob]:
        with self.db.get_session() as session:
            conditions = [RuleBacktestUniverseJob.id == int(job_id)]
            if not include_all_owners:
                conditions.append(RuleBacktestUniverseJob.owner_id == self.db.require_user_id(owner_id))
            row = session.execute(
                select(RuleBacktestUniverseJob).where(and_(*conditions)).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            for key, value in fields.items():
                setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return row

    def update_universe_symbol_result(
        self,
        result_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
        **fields: Any,
    ) -> Optional[RuleBacktestUniverseSymbolResult]:
        with self.db.get_session() as session:
            conditions = [RuleBacktestUniverseSymbolResult.id == int(result_id)]
            if not include_all_owners:
                conditions.append(RuleBacktestUniverseSymbolResult.owner_id == self.db.require_user_id(owner_id))
            row = session.execute(
                select(RuleBacktestUniverseSymbolResult).where(and_(*conditions)).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            for key, value in fields.items():
                setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return row
