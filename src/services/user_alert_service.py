# -*- coding: utf-8 -*-
"""Owner-scoped in-app user alert contract service."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, delete, desc, func, select

from src.storage import DatabaseManager, UserAlertEvent, UserAlertRule
from src.utils.symbol_normalization import canonical_stock_code


CONTRACT_VERSION = "user_alert_contract_v1"
RULE_TYPE_WATCHLIST_PRICE_THRESHOLD = "watchlist_price_threshold"
DELIVERY_MODE_IN_APP = "in_app"
_UNSET = object()


class UserAlertService:
    """Business logic for current-user in-app alert rules and events."""

    _symbol_pattern = re.compile(r"[A-Z0-9][A-Z0-9.\-]*")
    _directions = {"above", "below"}

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or DatabaseManager.get_instance()

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

    @classmethod
    def _normalize_direction(cls, direction: str) -> str:
        normalized = str(direction or "").strip().lower()
        if normalized not in cls._directions:
            raise ValueError("direction must be above or below")
        return normalized

    @staticmethod
    def _normalize_threshold(threshold_price: Any) -> Decimal:
        try:
            price = Decimal(str(threshold_price))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("threshold_price must be a positive number") from exc
        if not price.is_finite() or price <= 0:
            raise ValueError("threshold_price must be greater than 0")
        return price

    @staticmethod
    def _normalize_optional_text(value: Optional[str], *, max_length: int) -> Optional[str]:
        normalized = str(value or "").strip()
        if not normalized:
            return None
        if len(normalized) > max_length:
            raise ValueError(f"text must be at most {max_length} characters")
        return normalized

    @staticmethod
    def _decimal_to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _isoformat(value: Any) -> Optional[str]:
        return value.isoformat() if value else None

    @classmethod
    def _rule_to_dict(cls, row: UserAlertRule) -> Dict[str, Any]:
        return {
            "id": int(row.id),
            "contract_version": CONTRACT_VERSION,
            "rule_type": RULE_TYPE_WATCHLIST_PRICE_THRESHOLD,
            "symbol": str(row.symbol),
            "direction": str(row.direction),
            "threshold_price": cls._decimal_to_float(row.threshold_price),
            "enabled": bool(row.enabled),
            "note": str(row.note) if row.note else None,
            "delivery_mode": DELIVERY_MODE_IN_APP,
            "in_app_only": True,
            "owner_scoped": True,
            "created_at": cls._isoformat(row.created_at),
            "updated_at": cls._isoformat(row.updated_at),
        }

    @classmethod
    def _event_to_dict(cls, row: UserAlertEvent) -> Dict[str, Any]:
        return {
            "id": int(row.id),
            "contract_version": CONTRACT_VERSION,
            "event_type": str(row.event_type),
            "rule_id": int(row.rule_id) if row.rule_id is not None else None,
            "symbol": str(row.symbol) if row.symbol else None,
            "direction": str(row.direction) if row.direction else None,
            "threshold_price": cls._decimal_to_float(row.threshold_price),
            "title": str(row.title or ""),
            "message": str(row.message or ""),
            "delivery_mode": DELIVERY_MODE_IN_APP,
            "in_app_only": True,
            "owner_scoped": True,
            "read_at": cls._isoformat(row.read_at),
            "created_at": cls._isoformat(row.created_at),
        }

    def list_rules(self, *, owner_id: str) -> List[Dict[str, Any]]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            rows = session.execute(
                select(UserAlertRule)
                .where(UserAlertRule.owner_id == resolved_owner_id)
                .order_by(UserAlertRule.updated_at.desc(), UserAlertRule.id.desc())
            ).scalars().all()
            return [self._rule_to_dict(row) for row in rows]

    def get_rule(self, *, owner_id: str, rule_id: int) -> Optional[Dict[str, Any]]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            row = session.execute(
                select(UserAlertRule).where(
                    and_(
                        UserAlertRule.id == int(rule_id),
                        UserAlertRule.owner_id == resolved_owner_id,
                    )
                ).limit(1)
            ).scalar_one_or_none()
            return self._rule_to_dict(row) if row is not None else None

    def create_rule(
        self,
        *,
        owner_id: str,
        symbol: str,
        direction: str,
        threshold_price: Any,
        enabled: bool = True,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_direction = self._normalize_direction(direction)
        normalized_threshold = self._normalize_threshold(threshold_price)
        normalized_note = self._normalize_optional_text(note, max_length=500)

        with self.db.get_session() as session:
            row = UserAlertRule(
                owner_id=resolved_owner_id,
                rule_type=RULE_TYPE_WATCHLIST_PRICE_THRESHOLD,
                symbol=normalized_symbol,
                direction=normalized_direction,
                threshold_price=normalized_threshold,
                enabled=bool(enabled),
                note=normalized_note,
                delivery_mode=DELIVERY_MODE_IN_APP,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._rule_to_dict(row)

    def update_rule(
        self,
        *,
        owner_id: str,
        rule_id: int,
        symbol: Optional[str] = None,
        direction: Optional[str] = None,
        threshold_price: Any = None,
        enabled: Optional[bool] = None,
        note: Any = _UNSET,
    ) -> Optional[Dict[str, Any]]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            row = session.execute(
                select(UserAlertRule).where(
                    and_(
                        UserAlertRule.id == int(rule_id),
                        UserAlertRule.owner_id == resolved_owner_id,
                    )
                ).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None

            if symbol is not None:
                row.symbol = self._normalize_symbol(symbol)
            if direction is not None:
                row.direction = self._normalize_direction(direction)
            if threshold_price is not None:
                row.threshold_price = self._normalize_threshold(threshold_price)
            if enabled is not None:
                row.enabled = bool(enabled)
            if note is not _UNSET:
                row.note = self._normalize_optional_text(note, max_length=500)
            row.delivery_mode = DELIVERY_MODE_IN_APP
            row.updated_at = datetime.now()
            session.commit()
            session.refresh(row)
            return self._rule_to_dict(row)

    def delete_rule(self, *, owner_id: str, rule_id: int) -> bool:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            row = session.execute(
                select(UserAlertRule).where(
                    and_(
                        UserAlertRule.id == int(rule_id),
                        UserAlertRule.owner_id == resolved_owner_id,
                    )
                ).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return False
            session.execute(
                delete(UserAlertEvent).where(
                    and_(
                        UserAlertEvent.owner_id == resolved_owner_id,
                        UserAlertEvent.rule_id == int(rule_id),
                    )
                )
            )
            session.delete(row)
            session.commit()
            return True

    def list_events(self, *, owner_id: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        resolved_limit = max(1, min(int(limit), 200))
        resolved_offset = max(0, int(offset))
        with self.db.get_session() as session:
            total = session.execute(
                select(func.count()).select_from(UserAlertEvent).where(UserAlertEvent.owner_id == resolved_owner_id)
            ).scalar_one()
            rows = session.execute(
                select(UserAlertEvent)
                .where(UserAlertEvent.owner_id == resolved_owner_id)
                .order_by(desc(UserAlertEvent.created_at), desc(UserAlertEvent.id))
                .limit(resolved_limit)
                .offset(resolved_offset)
            ).scalars().all()
            return {
                "contract_version": CONTRACT_VERSION,
                "delivery_mode": DELIVERY_MODE_IN_APP,
                "in_app_only": True,
                "owner_scoped": True,
                "total": int(total),
                "limit": resolved_limit,
                "offset": resolved_offset,
                "items": [self._event_to_dict(row) for row in rows],
            }

    def record_in_app_event(
        self,
        *,
        owner_id: str,
        rule_id: int,
        title: str,
        message: str = "",
    ) -> Dict[str, Any]:
        resolved_owner_id = self.db.require_user_id(owner_id)
        normalized_title = self._normalize_optional_text(title, max_length=160) or "Alert condition recorded"
        normalized_message = self._normalize_optional_text(message, max_length=500) or ""
        with self.db.get_session() as session:
            rule = session.execute(
                select(UserAlertRule).where(
                    and_(
                        UserAlertRule.id == int(rule_id),
                        UserAlertRule.owner_id == resolved_owner_id,
                    )
                ).limit(1)
            ).scalar_one_or_none()
            if rule is None:
                raise ValueError("rule_id is not available for the current owner")
            row = UserAlertEvent(
                owner_id=resolved_owner_id,
                rule_id=int(rule.id),
                event_type=RULE_TYPE_WATCHLIST_PRICE_THRESHOLD,
                symbol=str(rule.symbol),
                direction=str(rule.direction),
                threshold_price=rule.threshold_price,
                title=normalized_title,
                message=normalized_message,
                delivery_mode=DELIVERY_MODE_IN_APP,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._event_to_dict(row)
