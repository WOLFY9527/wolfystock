# -*- coding: utf-8 -*-
"""User watchlist service for scanner candidate tracking."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select

from data_provider.base import canonical_stock_code
from src.storage import DatabaseManager, UserWatchlistItem

class WatchlistService:
    """Business logic for user-owned candidate tracking."""

    _symbol_pattern = re.compile(r"[A-Z0-9][A-Z0-9.\-]*")

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or DatabaseManager.get_instance()

    @staticmethod
    def _normalize_market(market: str) -> str:
        normalized = str(market or "").strip().lower()
        if normalized not in {"cn", "hk", "us"}:
            raise ValueError("market must be one of: cn, hk, us")
        return normalized

    @classmethod
    def _normalize_symbol(cls, symbol: str) -> str:
        normalized = canonical_stock_code(symbol).strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        if len(normalized) > 16:
            raise ValueError("symbol must be at most 16 characters")
        if not cls._symbol_pattern.fullmatch(normalized):
            raise ValueError("symbol contains invalid characters")
        return normalized

    @staticmethod
    def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _row_to_dict(row: UserWatchlistItem) -> Dict[str, Any]:
        return {
            "id": int(row.id),
            "symbol": str(row.symbol),
            "market": str(row.market),
            "name": str(row.name) if row.name else None,
            "source": str(row.source),
            "scanner_run_id": int(row.scanner_run_id) if row.scanner_run_id is not None else None,
            "scanner_rank": int(row.scanner_rank) if row.scanner_rank is not None else None,
            "scanner_score": float(row.scanner_score) if row.scanner_score is not None else None,
            "theme_id": str(row.theme_id) if row.theme_id else None,
            "universe_type": str(row.universe_type) if row.universe_type else None,
            "notes": str(row.notes) if row.notes else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def list_items(self, owner_id: str) -> List[Dict[str, Any]]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            rows = session.execute(
                select(UserWatchlistItem)
                .where(UserWatchlistItem.owner_id == resolved_owner_id)
                .order_by(UserWatchlistItem.updated_at.desc(), UserWatchlistItem.id.desc())
            ).scalars().all()
            return [self._row_to_dict(row) for row in rows]

    def get_item_by_id(self, *, owner_id: str, item_id: int) -> Optional[Dict[str, Any]]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            row = session.execute(
                select(UserWatchlistItem).where(
                    and_(
                        UserWatchlistItem.id == int(item_id),
                        UserWatchlistItem.owner_id == resolved_owner_id,
                    )
                ).limit(1)
            ).scalar_one_or_none()
            return self._row_to_dict(row) if row is not None else None

    def get_item_by_symbol(
        self,
        *,
        owner_id: str,
        symbol: str,
        market: str,
    ) -> Optional[Dict[str, Any]]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_market = self._normalize_market(market)
        with self.db.get_session() as session:
            row = session.execute(
                select(UserWatchlistItem).where(
                    and_(
                        UserWatchlistItem.owner_id == resolved_owner_id,
                        UserWatchlistItem.symbol == normalized_symbol,
                        UserWatchlistItem.market == normalized_market,
                    )
                ).limit(1)
            ).scalar_one_or_none()
            return self._row_to_dict(row) if row is not None else None

    def add_item(
        self,
        *,
        owner_id: str,
        symbol: str,
        market: str,
        source: str = "scanner",
        name: Optional[str] = None,
        scanner_run_id: Optional[int] = None,
        scanner_rank: Optional[int] = None,
        scanner_score: Optional[float] = None,
        theme_id: Optional[str] = None,
        universe_type: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_market = self._normalize_market(market)
        normalized_source = str(source or "").strip().lower() or "scanner"
        if normalized_source != "scanner":
            raise ValueError("source must be scanner")
        normalized_name = self._normalize_optional_text(name)
        normalized_theme_id = self._normalize_optional_text(theme_id)
        normalized_universe_type = self._normalize_optional_text(universe_type)
        normalized_notes = self._normalize_optional_text(notes)

        with self.db.get_session() as session:
            row = session.execute(
                select(UserWatchlistItem).where(
                    and_(
                        UserWatchlistItem.owner_id == resolved_owner_id,
                        UserWatchlistItem.symbol == normalized_symbol,
                        UserWatchlistItem.market == normalized_market,
                    )
                ).limit(1)
            ).scalar_one_or_none()

            if row is None:
                row = UserWatchlistItem(
                    owner_id=resolved_owner_id,
                    symbol=normalized_symbol,
                    market=normalized_market,
                    source=normalized_source,
                )
                session.add(row)
            else:
                row.source = normalized_source

            if normalized_name is not None:
                row.name = normalized_name
            if scanner_run_id is not None:
                row.scanner_run_id = int(scanner_run_id)
            if scanner_rank is not None:
                row.scanner_rank = int(scanner_rank)
            if scanner_score is not None:
                row.scanner_score = float(scanner_score)
            if normalized_theme_id is not None:
                row.theme_id = normalized_theme_id
            if normalized_universe_type is not None:
                row.universe_type = normalized_universe_type
            if normalized_notes is not None:
                row.notes = normalized_notes
            row.updated_at = datetime.now()
            session.commit()
            session.refresh(row)
            return self._row_to_dict(row)

    def remove_item(self, *, owner_id: str, item_id: int) -> bool:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            row = session.execute(
                select(UserWatchlistItem).where(
                    and_(
                        UserWatchlistItem.id == int(item_id),
                        UserWatchlistItem.owner_id == resolved_owner_id,
                    )
                ).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
