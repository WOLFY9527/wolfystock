# -*- coding: utf-8 -*-
"""Local-only OHLCV coverage preflight helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from data_provider.base import normalize_stock_code
from src.repositories.stock_repo import StockRepository


class LocalDataPreflightService:
    """Inspect StockDaily coverage without provider hydration or live calls."""

    def __init__(self, stock_repo: StockRepository):
        self.stock_repo = stock_repo

    def preflight_coverage(
        self,
        *,
        symbols: List[str],
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
        minimum_required_bars: int = 1,
        minimum_coverage_ratio: float = 1.0,
    ) -> Dict[str, Any]:
        normalized_symbols = self.normalize_symbols(symbols)
        normalized_start, normalized_end = self._normalize_date_range(start_date=start_date, end_date=end_date)
        required_bars = max(1, int(minimum_required_bars or 1))
        coverage_threshold = min(1.0, max(0.0, float(minimum_coverage_ratio)))

        items = [
            self._inspect_symbol(
                sequence_index=index,
                symbol=symbol,
                start_date=normalized_start,
                end_date=normalized_end,
                required_bars=required_bars,
                coverage_threshold=coverage_threshold,
            )
            for index, symbol in enumerate(normalized_symbols)
        ]
        summary = {
            "total": len(items),
            "ready": sum(1 for item in items if item["state"] == "ready"),
            "partial": sum(1 for item in items if item["state"] == "partial"),
            "missing": sum(1 for item in items if item["state"] == "missing"),
            "insufficient_data": sum(1 for item in items if item["state"] == "insufficient_data"),
        }
        return {
            "local_data_only": True,
            "overall_state": self._resolve_overall_state(summary),
            "symbols": normalized_symbols,
            "start_date": normalized_start.isoformat() if normalized_start else None,
            "end_date": normalized_end.isoformat() if normalized_end else None,
            "minimum_required_bars": required_bars,
            "minimum_coverage_ratio": coverage_threshold,
            "summary": summary,
            "items": items,
        }

    @staticmethod
    def normalize_symbols(symbols: List[str]) -> List[str]:
        normalized: set[str] = set()
        for symbol in symbols or []:
            code = normalize_stock_code(str(symbol or "").strip()).upper()
            if code:
                normalized.add(code)
        return sorted(normalized)

    def _inspect_symbol(
        self,
        *,
        sequence_index: int,
        symbol: str,
        start_date: Optional[date],
        end_date: Optional[date],
        required_bars: int,
        coverage_threshold: float,
    ) -> Dict[str, Any]:
        rows = self._load_rows(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            required_bars=required_bars,
        )
        bar_count = len(rows)
        first_date = self._row_date(rows[0]) if rows else None
        last_date = self._row_date(rows[-1]) if rows else None
        coverage_ratio = min(1.0, float(bar_count) / float(required_bars)) if required_bars else 0.0
        range_partial = bool(
            start_date is not None
            and end_date is not None
            and (
                first_date is None
                or last_date is None
                or first_date > start_date
                or last_date < end_date
            )
        )
        state, reason_code, reason_message = self._classify(
            bar_count=bar_count,
            coverage_ratio=coverage_ratio,
            coverage_threshold=coverage_threshold,
            range_partial=range_partial,
        )
        return {
            "sequence_index": sequence_index,
            "symbol": symbol,
            "state": state,
            "reason_code": reason_code,
            "reason_message": reason_message,
            "bar_count": bar_count,
            "required_bars": required_bars,
            "coverage_ratio": round(coverage_ratio, 6),
            "first_date": first_date.isoformat() if first_date else None,
            "last_date": last_date.isoformat() if last_date else None,
        }

    def _load_rows(
        self,
        *,
        symbol: str,
        start_date: Optional[date],
        end_date: Optional[date],
        required_bars: int,
    ) -> List[Any]:
        if start_date is not None and end_date is not None:
            return self.stock_repo.get_range(symbol, start_date, end_date)
        return list(reversed(self.stock_repo.get_latest(symbol, days=required_bars)))

    @staticmethod
    def _classify(
        *,
        bar_count: int,
        coverage_ratio: float,
        coverage_threshold: float,
        range_partial: bool,
    ) -> tuple[str, Optional[str], Optional[str]]:
        if bar_count <= 0:
            return "missing", "blocked_missing_local_data", "No local daily bars found for requested window."
        if coverage_ratio < coverage_threshold:
            return "insufficient_data", "insufficient_data", "Local daily bars are below the required coverage threshold."
        if range_partial:
            return "partial", "partial_local_data", "Local daily bars do not cover the full requested date range."
        return "ready", None, None

    @staticmethod
    def _resolve_overall_state(summary: Dict[str, int]) -> str:
        total = int(summary.get("total") or 0)
        if total <= 0:
            return "blocked_missing_local_data"
        if int(summary.get("ready") or 0) == total:
            return "ready"
        if int(summary.get("missing") or 0) == total:
            return "blocked_missing_local_data"
        if int(summary.get("ready") or 0) == 0 and int(summary.get("partial") or 0) == 0:
            return "insufficient_data"
        return "partial"

    @classmethod
    def _normalize_date_range(cls, *, start_date: Optional[Any], end_date: Optional[Any]) -> tuple[Optional[date], Optional[date]]:
        normalized_start = cls._parse_optional_date(start_date)
        normalized_end = cls._parse_optional_date(end_date)
        if normalized_start is None and normalized_end is None:
            return None, None
        if normalized_start is None or normalized_end is None:
            raise ValueError("start_date and end_date must be provided together")
        if normalized_start > normalized_end:
            raise ValueError("start_date must be earlier than or equal to end_date")
        return normalized_start, normalized_end

    @staticmethod
    def _parse_optional_date(value: Optional[Any]) -> Optional[date]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return datetime.fromisoformat(str(value)).date()
        except ValueError as exc:
            raise ValueError("start_date/end_date must use YYYY-MM-DD format") from exc

    @staticmethod
    def _row_date(row: Any) -> Optional[date]:
        value = getattr(row, "date", None)
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return None
