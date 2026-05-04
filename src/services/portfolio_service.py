# -*- coding: utf-8 -*-
"""Portfolio service for P0 account/events/snapshot workflow."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from data_provider.base import canonical_stock_code
from src.config import get_config
from src.repositories.portfolio_repo import (
    DuplicateBrokerConnectionRefError,
    DuplicateTradeDedupHashError,
    DuplicateTradeUidError,
    PortfolioBusyError as RepoPortfolioBusyError,
    PortfolioRepository,
)
from src.services.fx_rate_service import default_fx_rate_service

logger = logging.getLogger(__name__)

PortfolioBusyError = RepoPortfolioBusyError
_PHASE_F_CORPORATE_ACTIONS_SOURCE_UNAVAILABLE = "phase_f_corporate_actions_pg_source_unavailable"

EPS = 1e-8
VALID_ACCOUNT_MARKETS = {"cn", "hk", "us", "global"}
VALID_EVENT_MARKETS = {"cn", "hk", "us"}
VALID_COST_METHODS = {"fifo", "avg", "futu_diluted", "ths_pnl"}
VALID_SIDES = {"buy", "sell"}
VALID_CASH_DIRECTIONS = {"in", "out"}
VALID_CORPORATE_ACTIONS = {"cash_dividend", "split_adjustment"}
VALID_BROKER_CONNECTION_STATUSES = {"active", "disabled", "error"}
VALID_BROKER_IMPORT_MODES = {"file", "manual", "api"}
PORTFOLIO_FX_REFRESH_DISABLED_REASON = "portfolio_fx_update_disabled"


class PortfolioConflictError(Exception):
    """Raised when request conflicts with existing portfolio state."""


class PortfolioOversellError(ValueError):
    """Raised when a sell would exceed the available position quantity."""

    def __init__(
        self,
        *,
        symbol: str,
        trade_date: Optional[date],
        requested_quantity: float,
        available_quantity: float,
    ) -> None:
        self.symbol = symbol
        self.trade_date = trade_date
        self.requested_quantity = float(requested_quantity)
        self.available_quantity = max(0.0, float(available_quantity))
        date_hint = f" on {trade_date.isoformat()}" if trade_date is not None else ""
        super().__init__(
            "Oversell detected for "
            f"{symbol}{date_hint}: requested={round(self.requested_quantity, 8)}, "
            f"available={round(self.available_quantity, 8)}"
        )


@dataclass
class _AvgState:
    quantity: float = 0.0
    total_cost: float = 0.0


class PortfolioService:
    """Business logic for account CRUD, event writes, and snapshot replay."""

    _phase_f_trade_list_comparison_report_limit = 200
    _phase_f_trade_list_comparison_report_buffer: deque[Dict[str, Any]] = deque(
        maxlen=_phase_f_trade_list_comparison_report_limit
    )
    _phase_f_cash_ledger_comparison_report_limit = 200
    _phase_f_cash_ledger_comparison_report_buffer: deque[Dict[str, Any]] = deque(
        maxlen=_phase_f_cash_ledger_comparison_report_limit
    )
    _phase_f_corporate_actions_comparison_report_limit = 200
    _phase_f_corporate_actions_comparison_report_buffer: deque[Dict[str, Any]] = deque(
        maxlen=_phase_f_corporate_actions_comparison_report_limit
    )

    def __init__(
        self,
        repo: Optional[PortfolioRepository] = None,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ):
        self.repo = repo or PortfolioRepository()
        self.owner_id = owner_id
        self.include_all_owners = bool(include_all_owners)

    @classmethod
    def clear_phase_f_trade_list_comparison_reports(cls) -> None:
        cls._phase_f_trade_list_comparison_report_buffer.clear()

    @classmethod
    def get_phase_f_trade_list_comparison_reports(cls) -> List[Dict[str, Any]]:
        return [dict(report) for report in list(cls._phase_f_trade_list_comparison_report_buffer)]

    @classmethod
    def clear_phase_f_cash_ledger_comparison_reports(cls) -> None:
        cls._phase_f_cash_ledger_comparison_report_buffer.clear()

    @classmethod
    def get_phase_f_cash_ledger_comparison_reports(cls) -> List[Dict[str, Any]]:
        return [dict(report) for report in list(cls._phase_f_cash_ledger_comparison_report_buffer)]

    @classmethod
    def clear_phase_f_corporate_actions_comparison_reports(cls) -> None:
        cls._phase_f_corporate_actions_comparison_report_buffer.clear()

    @classmethod
    def get_phase_f_corporate_actions_comparison_reports(cls) -> List[Dict[str, Any]]:
        return [dict(report) for report in list(cls._phase_f_corporate_actions_comparison_report_buffer)]

    def _owner_kwargs(self) -> Dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "include_all_owners": self.include_all_owners,
        }

    def _resolve_owner_id(self, owner_id: Optional[str] = None) -> str:
        return self.repo.db.require_user_id(self.owner_id if owner_id is None else owner_id)

    # ------------------------------------------------------------------
    # Account CRUD
    # ------------------------------------------------------------------
    def create_account(
        self,
        *,
        name: str,
        broker: Optional[str],
        market: str,
        base_currency: str,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        name_norm = (name or "").strip()
        if not name_norm:
            raise ValueError("name is required")
        market_norm = self._normalize_account_market(market)
        base_currency_norm = self._normalize_currency(base_currency)
        row = self.repo.create_account(
            name=name_norm,
            broker=(broker or "").strip() or None,
            market=market_norm,
            base_currency=base_currency_norm,
            owner_id=self._resolve_owner_id(owner_id),
        )
        return self._account_to_dict(row)

    def list_accounts(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        phase_f_rows = self.repo.db.list_phase_f_portfolio_account_metadata_rows(
            include_inactive=include_inactive,
            **self._owner_kwargs(),
        )
        if phase_f_rows is not None:
            return [self._account_to_dict(r) for r in phase_f_rows]
        rows = self.repo.list_accounts(include_inactive=include_inactive, **self._owner_kwargs())
        return [self._account_to_dict(r) for r in rows]

    def get_account(self, account_id: int, *, include_inactive: bool = False) -> Optional[Dict[str, Any]]:
        row = self.repo.get_account(
            account_id,
            include_inactive=include_inactive,
            **self._owner_kwargs(),
        )
        if row is None:
            return None
        return self._account_to_dict(row)

    def update_account(
        self,
        account_id: int,
        *,
        name: Optional[str] = None,
        broker: Optional[str] = None,
        market: Optional[str] = None,
        base_currency: Optional[str] = None,
        owner_id: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {}
        if name is not None:
            name_norm = name.strip()
            if not name_norm:
                raise ValueError("name is required")
            fields["name"] = name_norm
        if broker is not None:
            fields["broker"] = broker.strip() or None
        if market is not None:
            fields["market"] = self._normalize_account_market(market)
        if base_currency is not None:
            fields["base_currency"] = self._normalize_currency(base_currency)
        if owner_id is not None:
            fields["owner_id"] = self._resolve_owner_id(owner_id)
        if is_active is not None:
            fields["is_active"] = bool(is_active)
        if not fields:
            raise ValueError("No fields provided for update")

        row = self.repo.update_account(account_id, fields, **self._owner_kwargs())
        if row is None:
            return None
        return self._account_to_dict(row)

    def deactivate_account(self, account_id: int) -> bool:
        return self.repo.deactivate_account(account_id, **self._owner_kwargs())

    def delete_account(self, account_id: int) -> Optional[Dict[str, Any]]:
        deleted = self.deactivate_account(account_id)
        if not deleted:
            return None
        active_accounts = self.list_accounts(include_inactive=False)
        return {
            "ok": True,
            "deleted_account_id": int(account_id),
            "delete_mode": "soft",
            "next_account_id": active_accounts[0]["id"] if active_accounts else None,
        }

    # ------------------------------------------------------------------
    # Broker connection CRUD
    # ------------------------------------------------------------------
    def create_broker_connection(
        self,
        *,
        portfolio_account_id: int,
        broker_type: str,
        connection_name: str,
        broker_name: Optional[str] = None,
        broker_account_ref: Optional[str] = None,
        import_mode: str = "file",
        status: str = "active",
        sync_metadata: Optional[Dict[str, Any]] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_owner_id = self._resolve_owner_id(owner_id)
        account = self.repo.get_account(
            portfolio_account_id,
            include_inactive=False,
            owner_id=resolved_owner_id,
            include_all_owners=self.include_all_owners,
        )
        if account is None:
            raise ValueError(f"Active account not found: {portfolio_account_id}")
        try:
            row = self.repo.create_broker_connection(
                portfolio_account_id=int(account.id),
                broker_type=self._normalize_broker_type(broker_type),
                broker_name=(broker_name or "").strip() or None,
                connection_name=self._normalize_connection_name(connection_name),
                broker_account_ref=self._normalize_broker_account_ref(broker_account_ref),
                import_mode=self._normalize_import_mode(import_mode),
                status=self._normalize_broker_connection_status(status),
                sync_metadata_json=self._serialize_sync_metadata(sync_metadata),
                owner_id=resolved_owner_id,
            )
        except DuplicateBrokerConnectionRefError as exc:
            raise PortfolioConflictError(str(exc)) from exc
        return self._broker_connection_to_dict(row, portfolio_account_name=account.name)

    def list_broker_connections(
        self,
        *,
        portfolio_account_id: Optional[int] = None,
        broker_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        broker_type_norm = self._normalize_broker_type(broker_type) if broker_type is not None else None
        status_norm = (
            self._normalize_broker_connection_status(status)
            if status is not None and str(status).strip()
            else None
        )
        phase_f_rows = self.repo.db.list_phase_f_portfolio_broker_connection_metadata_rows(
            portfolio_account_id=portfolio_account_id,
            broker_type=broker_type_norm,
            status=status_norm,
            **self._owner_kwargs(),
        )
        if phase_f_rows is not None:
            return [
                self._broker_connection_to_dict(
                    row,
                    portfolio_account_name=getattr(row, "portfolio_account_name", None),
                )
                for row in phase_f_rows
            ]
        if portfolio_account_id is not None:
            self.repo.get_account(
                portfolio_account_id,
                include_inactive=True,
                **self._owner_kwargs(),
            ) or self._raise_missing_account(portfolio_account_id)
        rows = self.repo.list_broker_connections(
            portfolio_account_id=portfolio_account_id,
            broker_type=broker_type_norm,
            status=status_norm,
            **self._owner_kwargs(),
        )
        account_lookup = self._account_name_lookup()
        return [
            self._broker_connection_to_dict(
                row,
                portfolio_account_name=account_lookup.get(int(row.portfolio_account_id)),
            )
            for row in rows
        ]

    def update_broker_connection(
        self,
        connection_id: int,
        *,
        portfolio_account_id: Optional[int] = None,
        connection_name: Optional[str] = None,
        broker_name: Optional[str] = None,
        broker_account_ref: Optional[str] = None,
        import_mode: Optional[str] = None,
        status: Optional[str] = None,
        sync_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {}
        portfolio_account_name: Optional[str] = None
        if portfolio_account_id is not None:
            account = self.repo.get_account(
                portfolio_account_id,
                include_inactive=False,
                **self._owner_kwargs(),
            )
            if account is None:
                raise ValueError(f"Active account not found: {portfolio_account_id}")
            fields["portfolio_account_id"] = int(account.id)
            portfolio_account_name = account.name
        if connection_name is not None:
            fields["connection_name"] = self._normalize_connection_name(connection_name)
        if broker_name is not None:
            fields["broker_name"] = broker_name.strip() or None
        if broker_account_ref is not None:
            fields["broker_account_ref"] = self._normalize_broker_account_ref(broker_account_ref)
        if import_mode is not None:
            fields["import_mode"] = self._normalize_import_mode(import_mode)
        if status is not None:
            fields["status"] = self._normalize_broker_connection_status(status)
        if sync_metadata is not None:
            fields["sync_metadata_json"] = self._serialize_sync_metadata(sync_metadata)
        if not fields:
            raise ValueError("No fields provided for update")

        try:
            row = self.repo.update_broker_connection(connection_id, fields, **self._owner_kwargs())
        except DuplicateBrokerConnectionRefError as exc:
            raise PortfolioConflictError(str(exc)) from exc
        if row is None:
            return None
        if portfolio_account_name is None:
            portfolio_account_name = self._account_name_lookup().get(int(row.portfolio_account_id))
        return self._broker_connection_to_dict(row, portfolio_account_name=portfolio_account_name)

    def get_broker_connection_by_ref(
        self,
        *,
        broker_type: str,
        broker_account_ref: str,
    ) -> Optional[Dict[str, Any]]:
        broker_type_norm = self._normalize_broker_type(broker_type)
        broker_account_ref_norm = self._normalize_broker_account_ref(broker_account_ref)
        if broker_account_ref_norm is None:
            raise ValueError("broker_account_ref is required")
        row = self.repo.get_broker_connection_by_ref(
            broker_type=broker_type_norm,
            broker_account_ref=broker_account_ref_norm,
            **self._owner_kwargs(),
        )
        if row is None:
            return None
        account_name = self._account_name_lookup().get(int(row.portfolio_account_id))
        return self._broker_connection_to_dict(row, portfolio_account_name=account_name)

    def get_broker_connection(self, connection_id: int) -> Optional[Dict[str, Any]]:
        row = self.repo.get_broker_connection(connection_id, **self._owner_kwargs())
        if row is None:
            return None
        account_name = self._account_name_lookup().get(int(row.portfolio_account_id))
        return self._broker_connection_to_dict(row, portfolio_account_name=account_name)

    def mark_broker_connection_imported(
        self,
        connection_id: int,
        *,
        import_source: str,
        import_fingerprint: Optional[str] = None,
        sync_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {
            "last_imported_at": datetime.now(),
            "last_import_source": (import_source or "").strip().lower() or "file",
            "last_import_fingerprint": (import_fingerprint or "").strip() or None,
            "status": "active",
        }
        if sync_metadata is not None:
            fields["sync_metadata_json"] = self._serialize_sync_metadata(sync_metadata)
        row = self.repo.update_broker_connection(connection_id, fields, **self._owner_kwargs())
        if row is None:
            return None
        account_name = self._account_name_lookup().get(int(row.portfolio_account_id))
        return self._broker_connection_to_dict(row, portfolio_account_name=account_name)

    def mark_broker_connection_synced(
        self,
        connection_id: int,
        *,
        sync_source: str,
        sync_status: str,
        sync_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        connection = self.get_broker_connection(connection_id)
        if connection is None:
            return None

        metadata = dict(connection.get("sync_metadata") or {})
        if sync_metadata:
            metadata.update(sync_metadata)
        metadata["last_sync_source"] = (sync_source or "").strip().lower() or "api"
        metadata["last_sync_status"] = (sync_status or "").strip().lower() or "success"
        metadata["last_sync_at"] = datetime.now().isoformat()

        row = self.repo.update_broker_connection(
            connection_id,
            {"sync_metadata_json": self._serialize_sync_metadata(metadata)},
            **self._owner_kwargs(),
        )
        if row is None:
            return None
        account_name = self._account_name_lookup().get(int(row.portfolio_account_id))
        return self._broker_connection_to_dict(row, portfolio_account_name=account_name)

    def replace_broker_sync_state(
        self,
        *,
        broker_connection_id: int,
        portfolio_account_id: int,
        broker_type: str,
        broker_account_ref: Optional[str],
        sync_source: str,
        sync_status: str,
        snapshot_date: date,
        synced_at: datetime,
        base_currency: str,
        total_cash: float,
        total_market_value: float,
        total_equity: float,
        realized_pnl: float,
        unrealized_pnl: float,
        fx_stale: bool,
        payload: Optional[Dict[str, Any]],
        positions: Iterable[Dict[str, Any]],
        cash_balances: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        connection = self.get_broker_connection(broker_connection_id)
        if connection is None:
            raise ValueError(f"Broker connection not found: {broker_connection_id}")
        if int(connection["portfolio_account_id"]) != int(portfolio_account_id):
            raise PortfolioConflictError(
                "Broker sync state cannot be written to a different portfolio account than the linked broker connection"
            )
        row = self.repo.replace_broker_sync_state(
            broker_connection_id=broker_connection_id,
            portfolio_account_id=portfolio_account_id,
            broker_type=self._normalize_broker_type(broker_type),
            broker_account_ref=self._normalize_broker_account_ref(broker_account_ref),
            sync_source=(sync_source or "").strip().lower() or "api",
            sync_status=(sync_status or "").strip().lower() or "success",
            snapshot_date=snapshot_date,
            synced_at=synced_at,
            base_currency=self._normalize_currency(base_currency),
            total_cash=float(total_cash),
            total_market_value=float(total_market_value),
            total_equity=float(total_equity),
            realized_pnl=float(realized_pnl),
            unrealized_pnl=float(unrealized_pnl),
            fx_stale=bool(fx_stale),
            payload_json=json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
            positions=list(positions),
            cash_balances=list(cash_balances),
            **self._owner_kwargs(),
        )
        return self._broker_sync_state_row_to_dict(row)

    def get_latest_broker_sync_state(self, *, portfolio_account_id: int) -> Optional[Dict[str, Any]]:
        phase_f_bundle = self.repo.db.get_phase_f_latest_broker_sync_state_bundle(
            portfolio_account_id=portfolio_account_id,
            **self._owner_kwargs(),
        )
        if phase_f_bundle is not None:
            row = phase_f_bundle.get("state_row")
            if row is None:
                return None
            return self._broker_sync_bundle_to_dict(
                row,
                positions=list(phase_f_bundle.get("positions") or []),
                cash_balances=list(phase_f_bundle.get("cash_balances") or []),
            )

        row = self.repo.get_latest_broker_sync_state_for_account(
            portfolio_account_id=portfolio_account_id,
            **self._owner_kwargs(),
        )
        if row is None:
            return None
        positions = self.repo.list_broker_sync_positions(
            broker_connection_id=int(row.broker_connection_id),
            **self._owner_kwargs(),
        )
        cash_balances = self.repo.list_broker_sync_cash_balances(
            broker_connection_id=int(row.broker_connection_id),
            **self._owner_kwargs(),
        )
        return self._broker_sync_bundle_to_dict(row, positions=positions, cash_balances=cash_balances)

    # ------------------------------------------------------------------
    # Event writes
    # ------------------------------------------------------------------
    def record_trade(
        self,
        *,
        account_id: int,
        symbol: str,
        trade_date: date,
        side: str,
        quantity: float,
        price: float,
        fee: float = 0.0,
        tax: float = 0.0,
        market: Optional[str] = None,
        currency: Optional[str] = None,
        trade_uid: Optional[str] = None,
        dedup_hash: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        side_norm = (side or "").strip().lower()
        if side_norm not in VALID_SIDES:
            raise ValueError("side must be buy or sell")
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity and price must be > 0")
        if fee < 0 or tax < 0:
            raise ValueError("fee and tax must be >= 0")
        symbol_norm = canonical_stock_code(symbol)
        if not symbol_norm:
            raise ValueError("symbol is required")
        trade_uid_norm = (trade_uid or "").strip() or None
        dedup_hash_norm = (dedup_hash or "").strip() or None
        try:
            with self.repo.portfolio_write_session() as session:
                account = self._require_active_account_in_session(session=session, account_id=account_id)
                market_hint = market
                if market_hint is None and str(account.market or "").strip().lower() == "global":
                    market_hint = self._infer_market_from_symbol(symbol_norm)
                market_norm = self._normalize_event_market(market_hint or account.market)
                currency_norm = self._normalize_currency(currency or self._default_currency_for_market(market_norm))
                self._validate_trade_identity(
                    account_id=account_id,
                    trade_uid=trade_uid_norm,
                    dedup_hash=dedup_hash_norm,
                    session=session,
                )
                if side_norm == "sell":
                    self._validate_sell_quantity(
                        account_id=account_id,
                        symbol=symbol_norm,
                        market=market_norm,
                        currency=currency_norm,
                        trade_date=trade_date,
                        quantity=float(quantity),
                        session=session,
                    )
                row = self.repo.add_trade_in_session(
                    session=session,
                    account_id=account_id,
                    trade_uid=trade_uid_norm,
                    symbol=symbol_norm,
                    market=market_norm,
                    currency=currency_norm,
                    trade_date=trade_date,
                    side=side_norm,
                    quantity=float(quantity),
                    price=float(price),
                    fee=float(fee),
                    tax=float(tax),
                    note=(note or "").strip() or None,
                    dedup_hash=dedup_hash_norm,
                )
                return {"id": int(row.id)}
        except (DuplicateTradeUidError, DuplicateTradeDedupHashError) as exc:
            raise PortfolioConflictError(str(exc)) from exc

    def record_cash_ledger(
        self,
        *,
        account_id: int,
        event_date: date,
        direction: str,
        amount: float,
        currency: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        direction_norm = (direction or "").strip().lower()
        if direction_norm not in VALID_CASH_DIRECTIONS:
            raise ValueError("direction must be in or out")
        if amount <= 0:
            raise ValueError("amount must be > 0")
        with self.repo.portfolio_write_session() as session:
            account = self._require_active_account_in_session(session=session, account_id=account_id)
            currency_norm = self._normalize_currency(currency or account.base_currency)
            row = self.repo.add_cash_ledger_in_session(
                session=session,
                account_id=account_id,
                event_date=event_date,
                direction=direction_norm,
                amount=float(amount),
                currency=currency_norm,
                note=(note or "").strip() or None,
            )
            return {"id": int(row.id)}

    def record_corporate_action(
        self,
        *,
        account_id: int,
        symbol: str,
        effective_date: date,
        action_type: str,
        market: Optional[str] = None,
        currency: Optional[str] = None,
        cash_dividend_per_share: Optional[float] = None,
        split_ratio: Optional[float] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        action_type_norm = (action_type or "").strip().lower()
        if action_type_norm not in VALID_CORPORATE_ACTIONS:
            raise ValueError("action_type must be cash_dividend or split_adjustment")

        if action_type_norm == "cash_dividend":
            if cash_dividend_per_share is None or cash_dividend_per_share < 0:
                raise ValueError("cash_dividend_per_share must be >= 0 for cash_dividend")
        if action_type_norm == "split_adjustment":
            if split_ratio is None or split_ratio <= 0:
                raise ValueError("split_ratio must be > 0 for split_adjustment")
        with self.repo.portfolio_write_session() as session:
            account = self._require_active_account_in_session(session=session, account_id=account_id)
            market_hint = market
            if market_hint is None and str(account.market or "").strip().lower() == "global":
                symbol_norm = canonical_stock_code(symbol)
                market_hint = self._infer_market_from_symbol(symbol_norm)
            market_norm = self._normalize_event_market(market_hint or account.market)
            currency_norm = self._normalize_currency(currency or self._default_currency_for_market(market_norm))
            symbol_norm = canonical_stock_code(symbol)
            if not symbol_norm:
                raise ValueError("symbol is required")
            row = self.repo.add_corporate_action_in_session(
                session=session,
                account_id=account_id,
                symbol=symbol_norm,
                market=market_norm,
                currency=currency_norm,
                effective_date=effective_date,
                action_type=action_type_norm,
                cash_dividend_per_share=cash_dividend_per_share,
                split_ratio=split_ratio,
                note=(note or "").strip() or None,
            )
            return {"id": int(row.id)}

    def delete_trade_event(self, trade_id: int) -> bool:
        with self.repo.portfolio_write_session() as session:
            return self.repo.delete_trade_in_session(
                session=session,
                trade_id=trade_id,
                **self._owner_kwargs(),
            )

    def update_trade_event(
        self,
        trade_id: int,
        *,
        account_id: Optional[int] = None,
        symbol: Optional[str] = None,
        trade_date: Optional[date] = None,
        side: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        fee: Optional[float] = None,
        tax: Optional[float] = None,
        market: Optional[str] = None,
        currency: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if all(
            value is None
            for value in (account_id, symbol, trade_date, side, quantity, price, fee, tax, market, currency, note)
        ):
            raise ValueError("No fields provided for update")
        with self.repo.portfolio_write_session() as session:
            row = self.repo.get_trade_in_session(
                session=session,
                trade_id=trade_id,
                include_voided=False,
                **self._owner_kwargs(),
            )
            if row is None:
                return None

            current_account_id = int(row.account_id)
            next_account_id = int(account_id) if account_id is not None else current_account_id
            account = self._require_active_account_in_session(session=session, account_id=next_account_id)

            side_norm = (side or row.side or "").strip().lower()
            if side_norm not in VALID_SIDES:
                raise ValueError("side must be buy or sell")

            quantity_value = float(row.quantity if quantity is None else quantity)
            if quantity_value <= 0:
                raise ValueError("quantity must be > 0")

            price_value = float(row.price if price is None else price)
            if price_value <= 0:
                raise ValueError("price must be > 0")

            fee_value = float(row.fee if fee is None else fee)
            tax_value = float(row.tax if tax is None else tax)
            if fee_value < 0 or tax_value < 0:
                raise ValueError("fee and tax must be >= 0")

            symbol_norm = canonical_stock_code(symbol if symbol is not None else row.symbol)
            if not symbol_norm:
                raise ValueError("symbol is required")

            trade_date_value = trade_date or row.trade_date
            market_hint = market if market is not None else row.market
            if str(account.market or "").strip().lower() == "global" and market is None and symbol is not None:
                market_hint = self._infer_market_from_symbol(symbol_norm)
            market_norm = self._normalize_event_market(market_hint or account.market)
            currency_norm = self._normalize_currency(currency or row.currency or self._default_currency_for_market(market_norm))

            original_trade_date = row.trade_date
            row.account_id = next_account_id
            row.symbol = symbol_norm
            row.trade_date = trade_date_value
            row.side = side_norm
            row.quantity = quantity_value
            row.price = price_value
            row.fee = fee_value
            row.tax = tax_value
            row.market = market_norm
            row.currency = currency_norm
            if note is not None:
                row.note = (note or "").strip() or None
            row.updated_at = datetime.now()

            self.repo._invalidate_account_cache_in_session(
                session=session,
                account_id=current_account_id,
                from_date=min(original_trade_date, trade_date_value),
            )
            self.repo._mark_phase_f_account_sync_in_session(session=session, account_id=current_account_id)
            if next_account_id != current_account_id:
                self.repo._invalidate_account_cache_in_session(
                    session=session,
                    account_id=next_account_id,
                    from_date=trade_date_value,
                )
                self.repo._mark_phase_f_account_sync_in_session(session=session, account_id=next_account_id)

            session.flush()
            self._validate_trade_sequence_in_session(session=session, account_id=current_account_id)
            if next_account_id != current_account_id:
                self._validate_trade_sequence_in_session(session=session, account_id=next_account_id)
            else:
                self._validate_trade_sequence_in_session(session=session, account_id=next_account_id)
            session.refresh(row)
            return self._trade_row_to_dict(row)

    def delete_cash_ledger_event(self, entry_id: int) -> bool:
        with self.repo.portfolio_write_session() as session:
            return self.repo.delete_cash_ledger_in_session(
                session=session,
                entry_id=entry_id,
                **self._owner_kwargs(),
            )

    def delete_corporate_action_event(self, action_id: int) -> bool:
        with self.repo.portfolio_write_session() as session:
            return self.repo.delete_corporate_action_in_session(
                session=session,
                action_id=action_id,
                **self._owner_kwargs(),
            )

    def list_trade_events(
        self,
        *,
        account_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        include_voided: bool = False,
    ) -> Dict[str, Any]:
        if account_id is not None:
            self._require_active_account(account_id)
        page, page_size = self._validate_paging(page=page, page_size=page_size)
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("date_from must be <= date_to")

        symbol_norm: Optional[str] = None
        if symbol is not None and symbol.strip():
            symbol_norm = canonical_stock_code(symbol)
            if not symbol_norm:
                raise ValueError("symbol is invalid")

        side_norm: Optional[str] = None
        if side is not None and side.strip():
            side_norm = side.strip().lower()
            if side_norm not in VALID_SIDES:
                raise ValueError("side must be buy or sell")

        rows, total = self.repo.query_trades(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            symbol=symbol_norm,
            side=side_norm,
            page=page,
            page_size=page_size,
            include_voided=include_voided,
            **self._owner_kwargs(),
        )
        result = {
            "items": [
                self._trade_row_to_dict(row) if include_voided else self._legacy_trade_row_to_dict(row)
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
        if self._phase_f_trade_list_comparison_enabled() and not include_voided:
            self._maybe_run_phase_f_trade_list_comparison(
                request_context={
                    "account_id": int(account_id) if account_id is not None else None,
                    "date_from": date_from.isoformat() if date_from is not None else None,
                    "date_to": date_to.isoformat() if date_to is not None else None,
                    "symbol": symbol_norm,
                    "side": side_norm,
                    "page": page,
                    "page_size": page_size,
                },
                legacy_rows=rows,
                legacy_result=result,
            )
        return result

    def _phase_f_trade_list_comparison_enabled(self) -> bool:
        return bool(getattr(get_config(), "enable_phase_f_trades_list_comparison", False))

    def _phase_f_trade_list_comparison_account_ids(self) -> Set[int]:
        raw_value = getattr(get_config(), "phase_f_trades_list_comparison_account_ids", [])
        return {int(item) for item in list(raw_value or []) if item is not None}

    def _phase_f_trade_list_comparison_rollout_decision(
        self,
        *,
        request_context: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        allowed_account_ids = self._phase_f_trade_list_comparison_account_ids()
        if not allowed_account_ids:
            return True, None

        account_id = request_context.get("account_id")
        if account_id is None:
            return False, "account_not_allowlisted"
        if int(account_id) not in allowed_account_ids:
            return False, "account_not_allowlisted"
        return True, None

    def _maybe_run_phase_f_trade_list_comparison(
        self,
        *,
        request_context: Dict[str, Any],
        legacy_rows: List[Any],
        legacy_result: Dict[str, Any],
    ) -> None:
        legacy_context = dict(request_context or {})
        _ = list(legacy_rows or [])
        legacy_view = {
            "request_context": legacy_context,
            "items": [dict(item) for item in (legacy_result or {}).get("items", [])],
            "total": int((legacy_result or {}).get("total", 0) or 0),
            "page": int((legacy_result or {}).get("page", legacy_context.get("page", 1)) or 1),
            "page_size": int((legacy_result or {}).get("page_size", legacy_context.get("page_size", 20)) or 20),
        }
        legacy_summary = self._summarize_phase_f_result_view(legacy_view)
        comparison_source = "phase_f_pg_trade_list_candidate"
        can_compare, skip_reason = self._phase_f_trade_list_comparison_rollout_decision(
            request_context=legacy_context,
        )
        if not can_compare:
            self._emit_phase_f_trade_list_comparison_report(
                self._build_phase_f_trade_list_comparison_report(
                    comparison_status="skipped",
                    comparison_attempted=False,
                    comparison_decision="legacy_served_without_comparison",
                    comparison_source=comparison_source,
                    comparison_skip_reason=skip_reason,
                    mismatch_class=None,
                    blocking_level="not_applicable",
                    fallback_decision="legacy_served_without_comparison",
                    request_context=legacy_context,
                    legacy_summary=legacy_summary,
                )
            )
            return None

        try:
            candidate = self._load_phase_f_trade_list_comparison_candidate(request_context=legacy_context)
        except Exception as exc:
            self._emit_phase_f_trade_list_comparison_report(
                self._build_phase_f_trade_list_comparison_report(
                    comparison_status="query_failure",
                    comparison_attempted=True,
                    comparison_decision="legacy_served_due_to_query_failure",
                    comparison_source=comparison_source,
                    comparison_skip_reason=None,
                    mismatch_class="query_failure",
                    blocking_level="hard_blocking",
                    fallback_decision="served_legacy_due_to_query_failure",
                    request_context=legacy_context,
                    legacy_summary=legacy_summary,
                    query_failure_detail=str(exc) or exc.__class__.__name__,
                )
            )
            return None

        candidate_summary = self._summarize_phase_f_result_view(candidate)
        mismatch = self._compare_phase_f_trade_list_results(legacy_view=legacy_view, candidate_view=candidate)
        if mismatch is None:
            self._emit_phase_f_trade_list_comparison_report(
                self._build_phase_f_trade_list_comparison_report(
                    comparison_status="matched",
                    comparison_attempted=True,
                    comparison_decision="legacy_served_after_match",
                    comparison_source=comparison_source,
                    comparison_skip_reason=None,
                    mismatch_class=None,
                    blocking_level="not_applicable",
                    fallback_decision="legacy_served_after_match",
                    request_context=legacy_context,
                    legacy_summary=legacy_summary,
                    pg_summary=candidate_summary,
                )
            )
            return None

        self._emit_phase_f_trade_list_comparison_report(
            self._build_phase_f_trade_list_comparison_report(
                comparison_status="mismatch",
                comparison_attempted=True,
                comparison_decision="legacy_served_due_to_mismatch",
                comparison_source=comparison_source,
                comparison_skip_reason=None,
                mismatch_class=mismatch["mismatch_class"],
                blocking_level=mismatch["blocking_level"],
                fallback_decision="served_legacy_due_to_mismatch",
                request_context=legacy_context,
                legacy_summary=legacy_summary,
                pg_summary=candidate_summary,
                first_mismatch_position=mismatch.get("first_mismatch_position"),
                first_mismatch_field=mismatch.get("first_mismatch_field"),
                first_legacy_value=mismatch.get("first_legacy_value"),
                first_pg_value=mismatch.get("first_pg_value"),
            )
        )
        return None

    def _load_phase_f_trade_list_comparison_candidate(
        self,
        *,
        request_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        date_from_raw = request_context.get("date_from")
        date_to_raw = request_context.get("date_to")
        date_from = date.fromisoformat(date_from_raw) if date_from_raw else None
        date_to = date.fromisoformat(date_to_raw) if date_to_raw else None

        candidate = self.repo.db.get_phase_f_trade_list_comparison_candidate(
            account_id=request_context.get("account_id"),
            date_from=date_from,
            date_to=date_to,
            symbol=request_context.get("symbol"),
            side=request_context.get("side"),
            page=int(request_context.get("page", 1) or 1),
            page_size=int(request_context.get("page_size", 20) or 20),
            **self._owner_kwargs(),
        )
        if candidate is None:
            raise RuntimeError("phase_f_trades_list_pg_source_unavailable")
        return {
            "request_context": dict(request_context or {}),
            "items": [dict(item) for item in (candidate.get("items") or [])],
            "total": int(candidate.get("total", 0) or 0),
            "page": int(candidate.get("page", request_context.get("page", 1)) or 1),
            "page_size": int(candidate.get("page_size", request_context.get("page_size", 20)) or 20),
        }

    def _compare_phase_f_trade_list_results(
        self,
        *,
        legacy_view: Dict[str, Any],
        candidate_view: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        legacy_request = dict((legacy_view or {}).get("request_context", {}) or {})
        candidate_request = dict((candidate_view or {}).get("request_context", {}) or {})
        if legacy_request != candidate_request:
            return {
                "mismatch_class": "request_shape_mismatch",
                "blocking_level": "hard_blocking",
                "first_mismatch_field": "request_context",
                "first_legacy_value": legacy_request,
                "first_pg_value": candidate_request,
            }

        legacy_total = int((legacy_view or {}).get("total", 0) or 0)
        candidate_total = int((candidate_view or {}).get("total", 0) or 0)
        if legacy_total != candidate_total:
            return {
                "mismatch_class": "count_mismatch",
                "blocking_level": "hard_blocking",
                "first_mismatch_field": "total",
                "first_legacy_value": legacy_total,
                "first_pg_value": candidate_total,
            }

        legacy_items = list((legacy_view or {}).get("items", []) or [])
        candidate_items = list((candidate_view or {}).get("items", []) or [])
        if len(legacy_items) != len(candidate_items):
            return {
                "mismatch_class": "pagination_mismatch",
                "blocking_level": "hard_blocking",
                "first_mismatch_field": "page_item_count",
                "first_legacy_value": len(legacy_items),
                "first_pg_value": len(candidate_items),
            }

        legacy_ids = [item.get("id") for item in legacy_items]
        candidate_ids = [item.get("id") for item in candidate_items]
        if legacy_ids != candidate_ids:
            first_position = next(
                (
                    index
                    for index, (legacy_id, candidate_id) in enumerate(zip(legacy_ids, candidate_ids))
                    if legacy_id != candidate_id
                ),
                None,
            )
            return {
                "mismatch_class": "ordering_mismatch",
                "blocking_level": "hard_blocking",
                "first_mismatch_position": first_position,
                "first_mismatch_field": "id",
                "first_legacy_value": legacy_ids[first_position] if first_position is not None else legacy_ids,
                "first_pg_value": candidate_ids[first_position] if first_position is not None else candidate_ids,
            }

        contract_fields = (
            "id",
            "account_id",
            "trade_uid",
            "symbol",
            "market",
            "currency",
            "trade_date",
            "side",
            "quantity",
            "price",
            "fee",
            "tax",
            "note",
            "created_at",
        )
        for index, (legacy_item, candidate_item) in enumerate(zip(legacy_items, candidate_items)):
            for field_name in contract_fields:
                legacy_value = legacy_item.get(field_name)
                candidate_value = candidate_item.get(field_name)
                if self._normalize_phase_f_compare_value(
                    field_name=field_name,
                    value=legacy_value,
                ) == self._normalize_phase_f_compare_value(
                    field_name=field_name,
                    value=candidate_value,
                ):
                    continue
                mismatch_class = "owner_scope_mismatch" if field_name == "account_id" else "payload_field_mismatch"
                return {
                    "mismatch_class": mismatch_class,
                    "blocking_level": "hard_blocking",
                    "first_mismatch_position": index,
                    "first_mismatch_field": field_name,
                    "first_legacy_value": legacy_value,
                    "first_pg_value": candidate_value,
                }
        return None

    @staticmethod
    def _normalize_phase_f_compare_value(
        *,
        field_name: str,
        value: Any,
    ) -> Any:
        """Normalize one Phase F comparison field before payload equality checks.

        Purpose:
            Keep comparison semantics aligned across the trade-list, cash-ledger,
            and corporate-actions migration surfaces. The helper only normalizes
            contract fields that are expected to drift in representation while
            remaining semantically identical.

        Parameters:
            field_name (str): Contract field currently being compared between the
                legacy payload and the Phase F candidate payload.
            value (Any): Raw field value from either side of the comparison.
                The helper accepts the original payload types and returns a value
                suitable for equality checks.

        Returns:
            Any: The original value for all fields except ``created_at``. For
            ``created_at``, the return value is a timezone-naive ISO-8601 string
            when the input is a parseable ``datetime`` or datetime-like string.
            Unparseable strings and unsupported objects are returned unchanged so
            real payload drift remains visible to the caller.

        Assumptions:
            - Only ``created_at`` is allowed to normalize away representation-only
              drift in this comparison contract.
            - Other fields must preserve their original values because a mismatch
              should remain blocking and visible in diagnostics.

        Edge cases:
            - ``None`` stays ``None``.
            - Empty datetime strings normalize to ``None``.
            - Timezone-aware datetimes drop ``tzinfo`` without converting clock
              time because Phase F diagnostics care about payload-shape drift, not
              cross-timezone instant equivalence.
            - Invalid datetime strings are returned unchanged and will still
              trigger a mismatch if the opposite side differs.

        Example:
            >>> PortfolioService._normalize_phase_f_compare_value(
            ...     field_name="created_at",
            ...     value="2026-04-21T00:49:23.107279+08:00",
            ... )
            '2026-04-21T00:49:23.107279'
            >>> PortfolioService._normalize_phase_f_compare_value(
            ...     field_name="symbol",
            ...     value="AAPL",
            ... )
            'AAPL'
        """
        if field_name != "created_at":
            return value
        return PortfolioService._normalize_phase_f_created_at_compare_value(value)

    @staticmethod
    def _normalize_phase_f_created_at_compare_value(value: Any) -> Any:
        if value is None:
            return None
        parsed: Optional[datetime] = None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                return None
            try:
                parsed = datetime.fromisoformat(raw_value)
            except ValueError:
                return value
        else:
            return value

        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed.isoformat()

    @staticmethod
    def _summarize_phase_f_result_view(result_view: Dict[str, Any]) -> Dict[str, Any]:
        """Build a bounded diagnostic summary for a paginated Phase F payload.

        Purpose:
            Produce the compact summary block embedded in Phase F comparison
            reports without leaking full payload rows into logs, evidence
            collectors, or review artifacts.

        Parameters:
            result_view (Dict[str, Any]): Legacy or Phase F response payload that
                may contain ``total``, ``page``, ``page_size``, and ``items``.
                Missing keys are tolerated and normalized to stable defaults.

        Returns:
            Dict[str, Any]: A compact summary with the following shape:
                - ``total`` (int): normalized total row count
                - ``page`` (int): normalized page number, default ``1``
                - ``page_size`` (int): normalized page size, default ``20``
                - ``page_item_count`` (int): number of rows present in ``items``
                - ``ordered_ids`` (List[Any]): ordered row identifiers preserved
                  exactly as they appear in the payload

        Assumptions:
            - The caller has already bounded ``items`` through the underlying API
              contract, so summarizing the ordered ids is safe for diagnostics.
            - Consumers want shape-level evidence only; they do not need the full
              row payload in comparison reports.

        Edge cases:
            - Non-numeric ``total`` / ``page`` / ``page_size`` values are coerced
              through ``int(...)`` with existing service semantics.
            - Missing or ``None`` pagination values fall back to ``0`` for
              ``total`` and ``1`` / ``20`` for ``page`` / ``page_size``.
            - Missing ``items`` behaves like an empty list.

        Example:
            >>> PortfolioService._summarize_phase_f_result_view(
            ...     {"total": 2, "page": 1, "page_size": 20, "items": [{"id": 21}, {"id": 20}]}
            ... )
            {'total': 2, 'page': 1, 'page_size': 20, 'page_item_count': 2, 'ordered_ids': [21, 20]}
        """
        items = list((result_view or {}).get("items", []) or [])
        return {
            "total": int((result_view or {}).get("total", 0) or 0),
            "page": int((result_view or {}).get("page", 1) or 1),
            "page_size": int((result_view or {}).get("page_size", 20) or 20),
            "page_item_count": len(items),
            "ordered_ids": [item.get("id") for item in items],
        }

    def _emit_phase_f_trade_list_comparison_report(self, report: Dict[str, Any]) -> None:
        self._collect_phase_f_trade_list_comparison_report(report)
        comparison_status = str((report or {}).get("comparison_status") or "").strip().lower()
        message = json.dumps(report, ensure_ascii=True, sort_keys=True, default=str)
        if comparison_status in {"mismatch", "query_failure"}:
            logger.warning("Phase F trades-list comparison diagnostic: %s", message)
            return
        logger.info("Phase F trades-list comparison diagnostic: %s", message)

    def _collect_phase_f_trade_list_comparison_report(self, report: Dict[str, Any]) -> None:
        if not isinstance(report, dict):
            return
        if str(report.get("candidate") or "").strip() != "portfolio_trades_list":
            return
        if not str(report.get("report_model") or "").strip().startswith("phase_f_trades_list_comparison_"):
            return
        self.__class__._phase_f_trade_list_comparison_report_buffer.append(dict(report))

    def _build_phase_f_trade_list_comparison_report(
        self,
        *,
        comparison_status: str,
        comparison_attempted: bool,
        comparison_decision: str,
        comparison_source: str,
        comparison_skip_reason: Optional[str],
        mismatch_class: str,
        blocking_level: str,
        fallback_decision: str,
        request_context: Dict[str, Any],
        legacy_summary: Dict[str, Any],
        pg_summary: Optional[Dict[str, Any]] = None,
        first_mismatch_position: Optional[int] = None,
        first_mismatch_field: Optional[str] = None,
        first_legacy_value: Any = None,
        first_pg_value: Any = None,
        query_failure_detail: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "report_model": "phase_f_trades_list_comparison_diagnostic_v2",
            "candidate": "portfolio_trades_list",
            "comparison_status": str(comparison_status or "").strip(),
            "comparison_attempted": bool(comparison_attempted),
            "comparison_decision": str(comparison_decision or "").strip(),
            "comparison_source": str(comparison_source or "").strip(),
            "comparison_skip_reason": str(comparison_skip_reason or "").strip() or None,
            "mismatch_class": str(mismatch_class or "").strip() or None,
            "blocking_level": str(blocking_level or "").strip(),
            "fallback_decision": str(fallback_decision or "").strip(),
            "request_context": dict(request_context or {}),
            "owner_context": {
                "owner_user_id": self._resolve_owner_id(self.owner_id),
                "include_all_owners": self.include_all_owners,
            },
            "legacy_summary": dict(legacy_summary or {}),
            "pg_summary": dict(pg_summary) if isinstance(pg_summary, dict) else None,
            "first_mismatch_position": first_mismatch_position,
            "first_mismatch_field": str(first_mismatch_field or "").strip() or None,
            "first_legacy_value": first_legacy_value,
            "first_pg_value": first_pg_value,
            "query_failure_detail": str(query_failure_detail or "").strip() or None,
        }

    def _build_phase_f_trade_list_mismatch_report(
        self,
        *,
        mismatch_class: str,
        blocking_level: str,
        fallback_decision: str,
        request_context: Dict[str, Any],
        legacy_summary: Dict[str, Any],
        pg_summary: Optional[Dict[str, Any]] = None,
        first_mismatch_position: Optional[int] = None,
        first_mismatch_field: Optional[str] = None,
        first_legacy_value: Any = None,
        first_pg_value: Any = None,
        query_failure_detail: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_mismatch_class = str(mismatch_class or "").strip()
        comparison_status = "query_failure" if normalized_mismatch_class == "query_failure" else "mismatch"
        comparison_decision = (
            "legacy_served_due_to_query_failure"
            if comparison_status == "query_failure"
            else "legacy_served_due_to_mismatch"
        )
        return self._build_phase_f_trade_list_comparison_report(
            comparison_status=comparison_status,
            comparison_attempted=True,
            comparison_decision=comparison_decision,
            comparison_source="phase_f_pg_trade_list_candidate",
            comparison_skip_reason=None,
            mismatch_class=normalized_mismatch_class,
            blocking_level=blocking_level,
            fallback_decision=fallback_decision,
            request_context=request_context,
            legacy_summary=legacy_summary,
            pg_summary=pg_summary,
            first_mismatch_position=first_mismatch_position,
            first_mismatch_field=first_mismatch_field,
            first_legacy_value=first_legacy_value,
            first_pg_value=first_pg_value,
            query_failure_detail=query_failure_detail,
        )

    def _build_phase_f_trade_list_comparison_evidence_summary(
        self,
        *,
        reports: List[Dict[str, Any]],
        allowlisted_account_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        relevant_reports: List[Dict[str, Any]] = []
        for report in list(reports or []):
            if not isinstance(report, dict):
                continue
            if str(report.get("candidate") or "").strip() != "portfolio_trades_list":
                continue
            if not str(report.get("report_model") or "").strip().startswith("phase_f_trades_list_comparison_"):
                continue
            relevant_reports.append(dict(report))

        status_counts = {
            "skipped": 0,
            "matched": 0,
            "mismatch": 0,
            "query_failure": 0,
        }
        mismatch_counts_by_class: Dict[str, int] = {}
        compared_account_ids: Set[int] = set()
        skipped_account_ids: Set[int] = set()
        hard_blocking_mismatch_classes: Set[str] = set()

        for report in relevant_reports:
            comparison_status = str(report.get("comparison_status") or "").strip().lower()
            if comparison_status in status_counts:
                status_counts[comparison_status] += 1

            request_context = dict(report.get("request_context") or {})
            account_id = request_context.get("account_id")
            resolved_account_id: Optional[int] = None
            if account_id is not None:
                try:
                    resolved_account_id = int(account_id)
                except (TypeError, ValueError):
                    resolved_account_id = None

            if bool(report.get("comparison_attempted")) and resolved_account_id is not None:
                compared_account_ids.add(resolved_account_id)
            if comparison_status == "skipped" and resolved_account_id is not None:
                skipped_account_ids.add(resolved_account_id)

            mismatch_class = str(report.get("mismatch_class") or "").strip()
            if comparison_status == "mismatch" and mismatch_class:
                mismatch_counts_by_class[mismatch_class] = mismatch_counts_by_class.get(mismatch_class, 0) + 1
                if str(report.get("blocking_level") or "").strip().lower() == "hard_blocking":
                    hard_blocking_mismatch_classes.add(mismatch_class)

        normalized_allowlisted_account_ids = sorted(
            {int(item) for item in list(allowlisted_account_ids or []) if item is not None}
        )
        uncovered_allowlisted_account_ids = sorted(
            set(normalized_allowlisted_account_ids) - set(compared_account_ids)
        )
        total_attempted = status_counts["matched"] + status_counts["mismatch"] + status_counts["query_failure"]
        evidence_is_thin = total_attempted == 0 or (
            bool(normalized_allowlisted_account_ids) and bool(uncovered_allowlisted_account_ids)
        )

        return {
            "summary_model": "phase_f_trades_list_comparison_evidence_summary_v1",
            "candidate": "portfolio_trades_list",
            "total_reports": len(relevant_reports),
            "total_attempted": total_attempted,
            "total_skipped": status_counts["skipped"],
            "total_matched": status_counts["matched"],
            "total_mismatched": status_counts["mismatch"],
            "total_query_failures": status_counts["query_failure"],
            "mismatch_counts_by_class": dict(sorted(mismatch_counts_by_class.items())),
            "query_failure_count": status_counts["query_failure"],
            "compared_account_ids": sorted(compared_account_ids),
            "skipped_account_ids": sorted(skipped_account_ids),
            "allowlisted_account_ids": normalized_allowlisted_account_ids,
            "uncovered_allowlisted_account_ids": uncovered_allowlisted_account_ids,
            "hard_blocking_mismatch_observed": bool(hard_blocking_mismatch_classes),
            "hard_blocking_mismatch_classes": sorted(hard_blocking_mismatch_classes),
            "evidence_is_thin": evidence_is_thin,
        }

    def _build_phase_f_trade_list_comparison_evidence_summary_from_collected_reports(
        self,
        *,
        allowlisted_account_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        return self._build_phase_f_trade_list_comparison_evidence_summary(
            reports=self.get_phase_f_trade_list_comparison_reports(),
            allowlisted_account_ids=allowlisted_account_ids,
        )

    def _build_phase_f_trade_list_promotion_readiness_review(
        self,
        *,
        evidence_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        summary = dict(evidence_summary or {})
        blocking_reasons: List[str] = []

        evidence_is_thin = bool(summary.get("evidence_is_thin"))
        if evidence_is_thin:
            blocking_reasons.append("evidence_still_thin")

        uncovered_allowlisted_account_ids = sorted(
            {int(item) for item in list(summary.get("uncovered_allowlisted_account_ids") or []) if item is not None}
        )
        if uncovered_allowlisted_account_ids:
            blocking_reasons.append("allowlisted_account_coverage_incomplete")

        hard_blocking_mismatch_observed = bool(summary.get("hard_blocking_mismatch_observed"))
        hard_blocking_mismatch_classes = sorted(
            {str(item).strip() for item in list(summary.get("hard_blocking_mismatch_classes") or []) if str(item).strip()}
        )
        if hard_blocking_mismatch_observed:
            blocking_reasons.append("hard_blocking_mismatches_observed")

        total_query_failures = int(summary.get("total_query_failures", 0) or 0)
        query_failures_observed = total_query_failures > 0
        if query_failures_observed:
            blocking_reasons.append("query_failures_observed")

        promotion_discussion_ready = not blocking_reasons
        review_status = "reviewable_for_promotion_discussion" if promotion_discussion_ready else "blocked"

        return {
            "review_model": "phase_f_trades_list_promotion_readiness_review_v1",
            "candidate": str(summary.get("candidate") or "portfolio_trades_list").strip() or "portfolio_trades_list",
            "evidence_summary_model": str(summary.get("summary_model") or "").strip() or None,
            "review_status": review_status,
            "promotion_discussion_ready": promotion_discussion_ready,
            "pg_serving_ready": False,
            "serving_readiness": "not_evaluated_by_this_review",
            "evidence_is_thin": evidence_is_thin,
            "allowlisted_account_coverage_incomplete": bool(uncovered_allowlisted_account_ids),
            "uncovered_allowlisted_account_ids": uncovered_allowlisted_account_ids,
            "hard_blocking_mismatch_observed": hard_blocking_mismatch_observed,
            "hard_blocking_mismatch_classes": hard_blocking_mismatch_classes,
            "query_failures_observed": query_failures_observed,
            "blocking_reasons": blocking_reasons,
            "summary_snapshot": {
                "total_reports": int(summary.get("total_reports", 0) or 0),
                "total_attempted": int(summary.get("total_attempted", 0) or 0),
                "total_skipped": int(summary.get("total_skipped", 0) or 0),
                "total_matched": int(summary.get("total_matched", 0) or 0),
                "total_mismatched": int(summary.get("total_mismatched", 0) or 0),
                "total_query_failures": total_query_failures,
                "mismatch_counts_by_class": dict(summary.get("mismatch_counts_by_class") or {}),
                "compared_account_ids": sorted(
                    {int(item) for item in list(summary.get("compared_account_ids") or []) if item is not None}
                ),
                "allowlisted_account_ids": sorted(
                    {int(item) for item in list(summary.get("allowlisted_account_ids") or []) if item is not None}
                ),
            },
        }

    def _build_phase_f_trade_list_promotion_readiness_review_from_collected_reports(
        self,
        *,
        allowlisted_account_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        return self._build_phase_f_trade_list_promotion_readiness_review(
            evidence_summary=self._build_phase_f_trade_list_comparison_evidence_summary_from_collected_reports(
                allowlisted_account_ids=allowlisted_account_ids,
            )
        )

    def list_cash_ledger_events(
        self,
        *,
        account_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        direction: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        if account_id is not None:
            self._require_active_account(account_id)
        page, page_size = self._validate_paging(page=page, page_size=page_size)
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("date_from must be <= date_to")

        direction_norm: Optional[str] = None
        if direction is not None and direction.strip():
            direction_norm = direction.strip().lower()
            if direction_norm not in VALID_CASH_DIRECTIONS:
                raise ValueError("direction must be in or out")

        rows, total = self.repo.query_cash_ledger(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            direction=direction_norm,
            page=page,
            page_size=page_size,
            **self._owner_kwargs(),
        )
        result = {
            "items": [self._cash_ledger_row_to_dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
        if self._phase_f_cash_ledger_comparison_enabled():
            self._maybe_run_phase_f_cash_ledger_comparison(
                request_context={
                    "account_id": int(account_id) if account_id is not None else None,
                    "date_from": date_from.isoformat() if date_from is not None else None,
                    "date_to": date_to.isoformat() if date_to is not None else None,
                    "direction": direction_norm,
                    "page": page,
                    "page_size": page_size,
                },
                legacy_rows=rows,
                legacy_result=result,
            )
        return result

    def _phase_f_cash_ledger_comparison_enabled(self) -> bool:
        return bool(getattr(get_config(), "enable_phase_f_cash_ledger_comparison", False))

    def _phase_f_cash_ledger_comparison_account_ids(self) -> Set[int]:
        raw_value = getattr(get_config(), "phase_f_cash_ledger_comparison_account_ids", [])
        return {int(item) for item in list(raw_value or []) if item is not None}

    def _phase_f_cash_ledger_comparison_rollout_decision(
        self,
        *,
        request_context: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        allowed_account_ids = self._phase_f_cash_ledger_comparison_account_ids()
        account_id = request_context.get("account_id")
        if account_id is None:
            return False, "account_not_allowlisted"
        if not allowed_account_ids:
            return False, "account_not_allowlisted"
        if int(account_id) not in allowed_account_ids:
            return False, "account_not_allowlisted"
        return True, None

    def _maybe_run_phase_f_cash_ledger_comparison(
        self,
        *,
        request_context: Dict[str, Any],
        legacy_rows: List[Any],
        legacy_result: Dict[str, Any],
    ) -> None:
        legacy_context = dict(request_context or {})
        _ = list(legacy_rows or [])
        legacy_view = {
            "request_context": legacy_context,
            "items": [dict(item) for item in (legacy_result or {}).get("items", [])],
            "total": int((legacy_result or {}).get("total", 0) or 0),
            "page": int((legacy_result or {}).get("page", legacy_context.get("page", 1)) or 1),
            "page_size": int((legacy_result or {}).get("page_size", legacy_context.get("page_size", 20)) or 20),
        }
        legacy_summary = self._summarize_phase_f_result_view(legacy_view)
        comparison_source = "phase_f_pg_cash_ledger_candidate"
        can_compare, skip_reason = self._phase_f_cash_ledger_comparison_rollout_decision(
            request_context=legacy_context,
        )
        if not can_compare:
            self._emit_phase_f_cash_ledger_comparison_report(
                self._build_phase_f_cash_ledger_comparison_report(
                    comparison_status="skipped",
                    comparison_attempted=False,
                    comparison_decision="legacy_served_without_comparison",
                    comparison_source=comparison_source,
                    comparison_skip_reason=skip_reason,
                    mismatch_class=None,
                    blocking_level="not_applicable",
                    fallback_decision="legacy_served_without_comparison",
                    request_context=legacy_context,
                    legacy_summary=legacy_summary,
                )
            )
            return None

        try:
            candidate = self._load_phase_f_cash_ledger_comparison_candidate(request_context=legacy_context)
        except Exception as exc:
            self._emit_phase_f_cash_ledger_comparison_report(
                self._build_phase_f_cash_ledger_comparison_report(
                    comparison_status="query_failure",
                    comparison_attempted=True,
                    comparison_decision="legacy_served_due_to_query_failure",
                    comparison_source=comparison_source,
                    comparison_skip_reason=None,
                    mismatch_class="query_failure",
                    blocking_level="hard_blocking",
                    fallback_decision="served_legacy_due_to_query_failure",
                    request_context=legacy_context,
                    legacy_summary=legacy_summary,
                    query_failure_detail=str(exc) or exc.__class__.__name__,
                )
            )
            return None

        candidate_summary = self._summarize_phase_f_result_view(candidate)
        mismatch = self._compare_phase_f_cash_ledger_results(legacy_view=legacy_view, candidate_view=candidate)
        if mismatch is None:
            self._emit_phase_f_cash_ledger_comparison_report(
                self._build_phase_f_cash_ledger_comparison_report(
                    comparison_status="matched",
                    comparison_attempted=True,
                    comparison_decision="legacy_served_after_match",
                    comparison_source=comparison_source,
                    comparison_skip_reason=None,
                    mismatch_class=None,
                    blocking_level="not_applicable",
                    fallback_decision="legacy_served_after_match",
                    request_context=legacy_context,
                    legacy_summary=legacy_summary,
                    pg_summary=candidate_summary,
                )
            )
            return None

        self._emit_phase_f_cash_ledger_comparison_report(
            self._build_phase_f_cash_ledger_comparison_report(
                comparison_status="mismatch",
                comparison_attempted=True,
                comparison_decision="legacy_served_due_to_mismatch",
                comparison_source=comparison_source,
                comparison_skip_reason=None,
                mismatch_class=mismatch["mismatch_class"],
                blocking_level=mismatch["blocking_level"],
                fallback_decision="served_legacy_due_to_mismatch",
                request_context=legacy_context,
                legacy_summary=legacy_summary,
                pg_summary=candidate_summary,
                first_mismatch_position=mismatch.get("first_mismatch_position"),
                first_mismatch_field=mismatch.get("first_mismatch_field"),
                first_legacy_value=mismatch.get("first_legacy_value"),
                first_pg_value=mismatch.get("first_pg_value"),
            )
        )
        return None

    def _load_phase_f_cash_ledger_comparison_candidate(
        self,
        *,
        request_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        date_from_raw = request_context.get("date_from")
        date_to_raw = request_context.get("date_to")
        date_from = date.fromisoformat(date_from_raw) if date_from_raw else None
        date_to = date.fromisoformat(date_to_raw) if date_to_raw else None

        candidate = self.repo.db.get_phase_f_cash_ledger_comparison_candidate(
            account_id=request_context.get("account_id"),
            date_from=date_from,
            date_to=date_to,
            direction=request_context.get("direction"),
            page=int(request_context.get("page", 1) or 1),
            page_size=int(request_context.get("page_size", 20) or 20),
            **self._owner_kwargs(),
        )
        if candidate is None:
            raise RuntimeError("phase_f_cash_ledger_pg_source_unavailable")
        return {
            "request_context": dict(request_context or {}),
            "items": [dict(item) for item in (candidate.get("items") or [])],
            "total": int(candidate.get("total", 0) or 0),
            "page": int(candidate.get("page", request_context.get("page", 1)) or 1),
            "page_size": int(candidate.get("page_size", request_context.get("page_size", 20)) or 20),
        }

    def _compare_phase_f_cash_ledger_results(
        self,
        *,
        legacy_view: Dict[str, Any],
        candidate_view: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        legacy_request = dict((legacy_view or {}).get("request_context", {}) or {})
        candidate_request = dict((candidate_view or {}).get("request_context", {}) or {})
        if legacy_request != candidate_request:
            return {
                "mismatch_class": "request_shape_mismatch",
                "blocking_level": "hard_blocking",
                "first_mismatch_field": "request_context",
                "first_legacy_value": legacy_request,
                "first_pg_value": candidate_request,
            }

        legacy_total = int((legacy_view or {}).get("total", 0) or 0)
        candidate_total = int((candidate_view or {}).get("total", 0) or 0)
        if legacy_total != candidate_total:
            return {
                "mismatch_class": "count_mismatch",
                "blocking_level": "hard_blocking",
                "first_mismatch_field": "total",
                "first_legacy_value": legacy_total,
                "first_pg_value": candidate_total,
            }

        legacy_items = list((legacy_view or {}).get("items", []) or [])
        candidate_items = list((candidate_view or {}).get("items", []) or [])
        if len(legacy_items) != len(candidate_items):
            return {
                "mismatch_class": "pagination_mismatch",
                "blocking_level": "hard_blocking",
                "first_mismatch_field": "page_item_count",
                "first_legacy_value": len(legacy_items),
                "first_pg_value": len(candidate_items),
            }

        legacy_ids = [item.get("id") for item in legacy_items]
        candidate_ids = [item.get("id") for item in candidate_items]
        if legacy_ids != candidate_ids:
            first_position = next(
                (
                    index
                    for index, (legacy_id, candidate_id) in enumerate(zip(legacy_ids, candidate_ids))
                    if legacy_id != candidate_id
                ),
                None,
            )
            return {
                "mismatch_class": "ordering_mismatch",
                "blocking_level": "hard_blocking",
                "first_mismatch_position": first_position,
                "first_mismatch_field": "id",
                "first_legacy_value": legacy_ids[first_position] if first_position is not None else legacy_ids,
                "first_pg_value": candidate_ids[first_position] if first_position is not None else candidate_ids,
            }

        contract_fields = ("id", "account_id", "event_date", "direction", "amount", "currency", "note", "created_at")
        for index, (legacy_item, candidate_item) in enumerate(zip(legacy_items, candidate_items)):
            for field_name in contract_fields:
                legacy_value = legacy_item.get(field_name)
                candidate_value = candidate_item.get(field_name)
                if self._normalize_phase_f_compare_value(
                    field_name=field_name,
                    value=legacy_value,
                ) == self._normalize_phase_f_compare_value(
                    field_name=field_name,
                    value=candidate_value,
                ):
                    continue
                mismatch_class = "owner_scope_mismatch" if field_name == "account_id" else "payload_field_mismatch"
                return {
                    "mismatch_class": mismatch_class,
                    "blocking_level": "hard_blocking",
                    "first_mismatch_position": index,
                    "first_mismatch_field": field_name,
                    "first_legacy_value": legacy_value,
                    "first_pg_value": candidate_value,
                }
        return None

    def _emit_phase_f_cash_ledger_comparison_report(self, report: Dict[str, Any]) -> None:
        self._collect_phase_f_cash_ledger_comparison_report(report)
        comparison_status = str((report or {}).get("comparison_status") or "").strip().lower()
        message = json.dumps(report, ensure_ascii=True, sort_keys=True, default=str)
        if comparison_status in {"mismatch", "query_failure"}:
            logger.warning("Phase F cash-ledger comparison diagnostic: %s", message)
            return
        logger.info("Phase F cash-ledger comparison diagnostic: %s", message)

    def _collect_phase_f_cash_ledger_comparison_report(self, report: Dict[str, Any]) -> None:
        if not isinstance(report, dict):
            return
        if str(report.get("candidate") or "").strip() != "portfolio_cash_ledger_list":
            return
        if not str(report.get("report_model") or "").strip().startswith("phase_f_cash_ledger_comparison_"):
            return
        self.__class__._phase_f_cash_ledger_comparison_report_buffer.append(dict(report))

    def _build_phase_f_cash_ledger_comparison_report(
        self,
        *,
        comparison_status: str,
        comparison_attempted: bool,
        comparison_decision: str,
        comparison_source: str,
        comparison_skip_reason: Optional[str],
        mismatch_class: Optional[str],
        blocking_level: str,
        fallback_decision: str,
        request_context: Dict[str, Any],
        legacy_summary: Dict[str, Any],
        pg_summary: Optional[Dict[str, Any]] = None,
        query_failure_detail: Optional[str] = None,
        first_mismatch_position: Optional[int] = None,
        first_mismatch_field: Optional[str] = None,
        first_legacy_value: Any = None,
        first_pg_value: Any = None,
    ) -> Dict[str, Any]:
        return {
            "report_model": "phase_f_cash_ledger_comparison_diagnostic_v1",
            "candidate": "portfolio_cash_ledger_list",
            "comparison_status": str(comparison_status or "").strip(),
            "comparison_attempted": bool(comparison_attempted),
            "comparison_decision": str(comparison_decision or "").strip(),
            "comparison_source": str(comparison_source or "").strip(),
            "comparison_skip_reason": str(comparison_skip_reason or "").strip() or None,
            "mismatch_class": str(mismatch_class or "").strip() or None,
            "blocking_level": str(blocking_level or "").strip(),
            "fallback_decision": str(fallback_decision or "").strip(),
            "request_context": dict(request_context or {}),
            "owner_context": {
                "owner_user_id": self._resolve_owner_id(self.owner_id),
                "include_all_owners": self.include_all_owners,
            },
            "legacy_summary": dict(legacy_summary or {}),
            "pg_summary": dict(pg_summary) if isinstance(pg_summary, dict) else None,
            "query_failure_detail": str(query_failure_detail or "").strip() or None,
            "first_mismatch_position": first_mismatch_position,
            "first_mismatch_field": str(first_mismatch_field or "").strip() or None,
            "first_legacy_value": first_legacy_value,
            "first_pg_value": first_pg_value,
        }

    def _build_phase_f_cash_ledger_comparison_evidence_summary(
        self,
        *,
        reports: List[Dict[str, Any]],
        allowlisted_account_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        relevant_reports = [
            dict(report)
            for report in list(reports or [])
            if str((report or {}).get("candidate") or "").strip() == "portfolio_cash_ledger_list"
            and str((report or {}).get("report_model") or "").strip().startswith("phase_f_cash_ledger_comparison_")
        ]
        status_counts = {"matched": 0, "mismatch": 0, "query_failure": 0, "skipped": 0}
        mismatch_counts_by_class: Dict[str, int] = {}
        compared_account_ids: Set[int] = set()
        skipped_account_ids: Set[int] = set()
        hard_blocking_issue_classes: Set[str] = set()
        matched_empty_reports = 0
        matched_non_empty_reports = 0

        for report in relevant_reports:
            comparison_status = str(report.get("comparison_status") or "").strip().lower()
            if comparison_status in status_counts:
                status_counts[comparison_status] += 1

            request_context = dict(report.get("request_context") or {})
            account_id = request_context.get("account_id")
            resolved_account_id: Optional[int] = None
            if account_id is not None:
                try:
                    resolved_account_id = int(account_id)
                except (TypeError, ValueError):
                    resolved_account_id = None

            if bool(report.get("comparison_attempted")) and resolved_account_id is not None:
                compared_account_ids.add(resolved_account_id)
            if comparison_status == "skipped" and resolved_account_id is not None:
                skipped_account_ids.add(resolved_account_id)

            if comparison_status == "matched":
                page_item_count = int(dict(report.get("legacy_summary") or {}).get("page_item_count", 0) or 0)
                if page_item_count > 0:
                    matched_non_empty_reports += 1
                else:
                    matched_empty_reports += 1

            mismatch_class = str(report.get("mismatch_class") or "").strip()
            if comparison_status == "mismatch" and mismatch_class:
                mismatch_counts_by_class[mismatch_class] = mismatch_counts_by_class.get(mismatch_class, 0) + 1
                if str(report.get("blocking_level") or "").strip().lower() == "hard_blocking":
                    hard_blocking_issue_classes.add(mismatch_class)
            if comparison_status == "query_failure":
                hard_blocking_issue_classes.add("query_failure")

        normalized_allowlisted_account_ids = sorted(
            {int(item) for item in list(allowlisted_account_ids or []) if item is not None}
        )
        uncovered_allowlisted_account_ids = sorted(
            set(normalized_allowlisted_account_ids) - set(compared_account_ids)
        )
        total_attempted = status_counts["matched"] + status_counts["mismatch"] + status_counts["query_failure"]
        non_empty_match_observed = matched_non_empty_reports > 0
        hard_blocking_issue_observed = bool(hard_blocking_issue_classes)

        if total_attempted == 0 or (
            bool(normalized_allowlisted_account_ids) and bool(uncovered_allowlisted_account_ids)
        ):
            evidence_strength = "thin"
        elif non_empty_match_observed:
            evidence_strength = "non_empty_sampled"
        elif matched_empty_reports > 0 and not hard_blocking_issue_observed:
            evidence_strength = "empty_only"
        else:
            evidence_strength = "mismatch_or_failure_only"

        evidence_is_thin = evidence_strength == "thin" or not non_empty_match_observed

        return {
            "summary_model": "phase_f_cash_ledger_comparison_evidence_summary_v1",
            "candidate": "portfolio_cash_ledger_list",
            "total_reports": len(relevant_reports),
            "total_attempted": total_attempted,
            "total_skipped": status_counts["skipped"],
            "total_matched": status_counts["matched"],
            "total_mismatched": status_counts["mismatch"],
            "total_query_failures": status_counts["query_failure"],
            "mismatch_counts_by_class": dict(sorted(mismatch_counts_by_class.items())),
            "query_failure_count": status_counts["query_failure"],
            "compared_account_ids": sorted(compared_account_ids),
            "skipped_account_ids": sorted(skipped_account_ids),
            "allowlisted_account_ids": normalized_allowlisted_account_ids,
            "uncovered_allowlisted_account_ids": uncovered_allowlisted_account_ids,
            "matched_empty_reports": matched_empty_reports,
            "matched_non_empty_reports": matched_non_empty_reports,
            "non_empty_match_observed": non_empty_match_observed,
            "hard_blocking_issue_observed": hard_blocking_issue_observed,
            "hard_blocking_issue_classes": sorted(hard_blocking_issue_classes),
            "evidence_strength": evidence_strength,
            "evidence_is_thin": evidence_is_thin,
        }

    def _build_phase_f_cash_ledger_comparison_evidence_summary_from_collected_reports(
        self,
        *,
        allowlisted_account_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        return self._build_phase_f_cash_ledger_comparison_evidence_summary(
            reports=self.get_phase_f_cash_ledger_comparison_reports(),
            allowlisted_account_ids=allowlisted_account_ids,
        )

    def list_corporate_action_events(
        self,
        *,
        account_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        symbol: Optional[str] = None,
        action_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        if account_id is not None:
            self._require_active_account(account_id)
        page, page_size = self._validate_paging(page=page, page_size=page_size)
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("date_from must be <= date_to")

        symbol_norm: Optional[str] = None
        if symbol is not None and symbol.strip():
            symbol_norm = canonical_stock_code(symbol)
            if not symbol_norm:
                raise ValueError("symbol is invalid")

        action_norm: Optional[str] = None
        if action_type is not None and action_type.strip():
            action_norm = action_type.strip().lower()
            if action_norm not in VALID_CORPORATE_ACTIONS:
                raise ValueError("action_type must be cash_dividend or split_adjustment")

        rows, total = self.repo.query_corporate_actions(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            symbol=symbol_norm,
            action_type=action_norm,
            page=page,
            page_size=page_size,
            **self._owner_kwargs(),
        )
        result = {
            "items": [self._corporate_action_row_to_dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
        if self._phase_f_corporate_actions_comparison_enabled():
            self._maybe_run_phase_f_corporate_actions_comparison(
                request_context={
                    "account_id": int(account_id) if account_id is not None else None,
                    "date_from": date_from.isoformat() if date_from is not None else None,
                    "date_to": date_to.isoformat() if date_to is not None else None,
                    "symbol": symbol_norm,
                    "action_type": action_norm,
                    "page": page,
                    "page_size": page_size,
                },
                legacy_rows=rows,
                legacy_result=result,
            )
        return result

    def _phase_f_corporate_actions_comparison_enabled(self) -> bool:
        return bool(getattr(get_config(), "enable_phase_f_corporate_actions_comparison", False))

    def _phase_f_corporate_actions_comparison_account_ids(self) -> Set[int]:
        raw_value = getattr(get_config(), "phase_f_corporate_actions_comparison_account_ids", [])
        return {int(item) for item in list(raw_value or []) if item is not None}

    def _phase_f_corporate_actions_comparison_rollout_decision(
        self,
        *,
        request_context: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        allowed_account_ids = self._phase_f_corporate_actions_comparison_account_ids()
        account_id = request_context.get("account_id")
        if account_id is None:
            return False, "account_not_allowlisted"
        if not allowed_account_ids:
            return False, "account_not_allowlisted"
        if int(account_id) not in allowed_account_ids:
            return False, "account_not_allowlisted"
        return True, None

    def _maybe_run_phase_f_corporate_actions_comparison(
        self,
        *,
        request_context: Dict[str, Any],
        legacy_rows: List[Any],
        legacy_result: Dict[str, Any],
    ) -> None:
        legacy_context = dict(request_context or {})
        _ = list(legacy_rows or [])
        legacy_view = {
            "request_context": legacy_context,
            "items": [dict(item) for item in (legacy_result or {}).get("items", [])],
            "total": int((legacy_result or {}).get("total", 0) or 0),
            "page": int((legacy_result or {}).get("page", legacy_context.get("page", 1)) or 1),
            "page_size": int((legacy_result or {}).get("page_size", legacy_context.get("page_size", 20)) or 20),
        }
        legacy_summary = self._summarize_phase_f_result_view(legacy_view)
        comparison_source = "phase_f_pg_corporate_actions_candidate"
        can_compare, skip_reason = self._phase_f_corporate_actions_comparison_rollout_decision(
            request_context=legacy_context,
        )
        if not can_compare:
            self._emit_phase_f_corporate_actions_comparison_report(
                self._build_phase_f_corporate_actions_comparison_report(
                    comparison_status="skipped",
                    comparison_attempted=False,
                    comparison_decision="legacy_served_without_comparison",
                    comparison_source=comparison_source,
                    comparison_skip_reason=skip_reason,
                    mismatch_class=None,
                    blocking_level="not_applicable",
                    fallback_decision="legacy_served_without_comparison",
                    request_context=legacy_context,
                    legacy_summary=legacy_summary,
                )
            )
            return None

        try:
            candidate = self._load_phase_f_corporate_actions_comparison_candidate(request_context=legacy_context)
        except RuntimeError as exc:
            if str(exc) != _PHASE_F_CORPORATE_ACTIONS_SOURCE_UNAVAILABLE:
                self._emit_phase_f_corporate_actions_comparison_report(
                    self._build_phase_f_corporate_actions_comparison_report(
                        comparison_status="query_failure",
                        comparison_attempted=True,
                        comparison_decision="legacy_served_due_to_query_failure",
                        comparison_source=comparison_source,
                        comparison_skip_reason=None,
                        mismatch_class="query_failure",
                        blocking_level="hard_blocking",
                        fallback_decision="served_legacy_due_to_query_failure",
                        request_context=legacy_context,
                        legacy_summary=legacy_summary,
                        pg_source_available=True,
                        query_failure_detail=str(exc) or exc.__class__.__name__,
                    )
                )
                return None

            self._emit_phase_f_corporate_actions_comparison_report(
                self._build_phase_f_corporate_actions_comparison_report(
                    comparison_status="source_unavailable",
                    comparison_attempted=True,
                    comparison_decision="legacy_served_due_to_source_unavailable",
                    comparison_source=comparison_source,
                    comparison_skip_reason=None,
                    mismatch_class="query_failure",
                    blocking_level="hard_blocking",
                    fallback_decision="served_legacy_due_to_source_unavailable",
                    request_context=legacy_context,
                    legacy_summary=legacy_summary,
                    pg_source_available=False,
                    source_unavailable_reason=_PHASE_F_CORPORATE_ACTIONS_SOURCE_UNAVAILABLE,
                )
            )
            return None
        except Exception as exc:
            self._emit_phase_f_corporate_actions_comparison_report(
                self._build_phase_f_corporate_actions_comparison_report(
                    comparison_status="query_failure",
                    comparison_attempted=True,
                    comparison_decision="legacy_served_due_to_query_failure",
                    comparison_source=comparison_source,
                    comparison_skip_reason=None,
                    mismatch_class="query_failure",
                    blocking_level="hard_blocking",
                    fallback_decision="served_legacy_due_to_query_failure",
                    request_context=legacy_context,
                    legacy_summary=legacy_summary,
                    pg_source_available=True,
                    query_failure_detail=str(exc) or exc.__class__.__name__,
                )
            )
            return None

        candidate_summary = self._summarize_phase_f_result_view(candidate)
        mismatch = self._compare_phase_f_corporate_actions_results(
            legacy_view=legacy_view,
            candidate_view=candidate,
        )
        if mismatch is None:
            self._emit_phase_f_corporate_actions_comparison_report(
                self._build_phase_f_corporate_actions_comparison_report(
                    comparison_status="matched",
                    comparison_attempted=True,
                    comparison_decision="legacy_served_after_match",
                    comparison_source=comparison_source,
                    comparison_skip_reason=None,
                    mismatch_class=None,
                    blocking_level="not_applicable",
                    fallback_decision="legacy_served_after_match",
                    request_context=legacy_context,
                    legacy_summary=legacy_summary,
                    pg_summary=candidate_summary,
                    pg_source_available=True,
                )
            )
            return None

        self._emit_phase_f_corporate_actions_comparison_report(
            self._build_phase_f_corporate_actions_comparison_report(
                comparison_status="mismatch",
                comparison_attempted=True,
                comparison_decision="legacy_served_due_to_mismatch",
                comparison_source=comparison_source,
                comparison_skip_reason=None,
                mismatch_class=mismatch["mismatch_class"],
                blocking_level=mismatch["blocking_level"],
                fallback_decision="served_legacy_due_to_mismatch",
                request_context=legacy_context,
                legacy_summary=legacy_summary,
                pg_summary=candidate_summary,
                pg_source_available=True,
                first_mismatch_position=mismatch.get("first_mismatch_position"),
                first_mismatch_field=mismatch.get("first_mismatch_field"),
                first_legacy_value=mismatch.get("first_legacy_value"),
                first_pg_value=mismatch.get("first_pg_value"),
            )
        )
        return None

    def _load_phase_f_corporate_actions_comparison_candidate(
        self,
        *,
        request_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        date_from_raw = request_context.get("date_from")
        date_to_raw = request_context.get("date_to")
        date_from = date.fromisoformat(date_from_raw) if date_from_raw else None
        date_to = date.fromisoformat(date_to_raw) if date_to_raw else None

        candidate = self.repo.db.get_phase_f_corporate_actions_comparison_candidate(
            account_id=request_context.get("account_id"),
            date_from=date_from,
            date_to=date_to,
            symbol=request_context.get("symbol"),
            action_type=request_context.get("action_type"),
            page=int(request_context.get("page", 1) or 1),
            page_size=int(request_context.get("page_size", 20) or 20),
            **self._owner_kwargs(),
        )
        if candidate is None:
            raise RuntimeError(_PHASE_F_CORPORATE_ACTIONS_SOURCE_UNAVAILABLE)
        return {
            "request_context": dict(request_context or {}),
            "items": [dict(item) for item in (candidate.get("items") or [])],
            "total": int(candidate.get("total", 0) or 0),
            "page": int(candidate.get("page", request_context.get("page", 1)) or 1),
            "page_size": int(candidate.get("page_size", request_context.get("page_size", 20)) or 20),
        }

    def _compare_phase_f_corporate_actions_results(
        self,
        *,
        legacy_view: Dict[str, Any],
        candidate_view: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        legacy_request = dict((legacy_view or {}).get("request_context", {}) or {})
        candidate_request = dict((candidate_view or {}).get("request_context", {}) or {})
        if legacy_request != candidate_request:
            return {
                "mismatch_class": "filter_mismatch",
                "blocking_level": "hard_blocking",
                "first_mismatch_field": "request_context",
                "first_legacy_value": legacy_request,
                "first_pg_value": candidate_request,
            }

        legacy_total = int((legacy_view or {}).get("total", 0) or 0)
        candidate_total = int((candidate_view or {}).get("total", 0) or 0)
        if legacy_total != candidate_total:
            return {
                "mismatch_class": "count_mismatch",
                "blocking_level": "hard_blocking",
                "first_mismatch_field": "total",
                "first_legacy_value": legacy_total,
                "first_pg_value": candidate_total,
            }

        legacy_items = list((legacy_view or {}).get("items", []) or [])
        candidate_items = list((candidate_view or {}).get("items", []) or [])
        if len(legacy_items) != len(candidate_items):
            return {
                "mismatch_class": "pagination_mismatch",
                "blocking_level": "hard_blocking",
                "first_mismatch_field": "page_item_count",
                "first_legacy_value": len(legacy_items),
                "first_pg_value": len(candidate_items),
            }

        legacy_ids = [item.get("id") for item in legacy_items]
        candidate_ids = [item.get("id") for item in candidate_items]
        if legacy_ids != candidate_ids:
            first_position = next(
                (
                    index
                    for index, (legacy_id, candidate_id) in enumerate(zip(legacy_ids, candidate_ids))
                    if legacy_id != candidate_id
                ),
                None,
            )
            return {
                "mismatch_class": "ordering_mismatch",
                "blocking_level": "hard_blocking",
                "first_mismatch_position": first_position,
                "first_mismatch_field": "id",
                "first_legacy_value": legacy_ids[first_position] if first_position is not None else legacy_ids,
                "first_pg_value": candidate_ids[first_position] if first_position is not None else candidate_ids,
            }

        contract_fields = (
            "id",
            "account_id",
            "symbol",
            "market",
            "currency",
            "effective_date",
            "action_type",
            "cash_dividend_per_share",
            "split_ratio",
            "note",
            "created_at",
        )
        for index, (legacy_item, candidate_item) in enumerate(zip(legacy_items, candidate_items)):
            for field_name in contract_fields:
                legacy_value = legacy_item.get(field_name)
                candidate_value = candidate_item.get(field_name)
                if self._normalize_phase_f_compare_value(
                    field_name=field_name,
                    value=legacy_value,
                ) == self._normalize_phase_f_compare_value(
                    field_name=field_name,
                    value=candidate_value,
                ):
                    continue
                mismatch_class = "owner_scope_mismatch" if field_name == "account_id" else "payload_field_mismatch"
                return {
                    "mismatch_class": mismatch_class,
                    "blocking_level": "hard_blocking",
                    "first_mismatch_position": index,
                    "first_mismatch_field": field_name,
                    "first_legacy_value": legacy_value,
                    "first_pg_value": candidate_value,
                }
        return None

    def _emit_phase_f_corporate_actions_comparison_report(self, report: Dict[str, Any]) -> None:
        self._collect_phase_f_corporate_actions_comparison_report(report)
        comparison_status = str((report or {}).get("comparison_status") or "").strip().lower()
        message = json.dumps(report, ensure_ascii=True, sort_keys=True, default=str)
        if comparison_status in {"mismatch", "query_failure", "source_unavailable"}:
            logger.warning("Phase F corporate-actions comparison diagnostic: %s", message)
            return
        logger.info("Phase F corporate-actions comparison diagnostic: %s", message)

    def _collect_phase_f_corporate_actions_comparison_report(self, report: Dict[str, Any]) -> None:
        if not isinstance(report, dict):
            return
        if str(report.get("candidate") or "").strip() != "portfolio_corporate_actions":
            return
        if not str(report.get("report_model") or "").strip().startswith("phase_f_corporate_actions_comparison_"):
            return
        self.__class__._phase_f_corporate_actions_comparison_report_buffer.append(dict(report))

    def _build_phase_f_corporate_actions_comparison_report(
        self,
        *,
        comparison_status: str,
        comparison_attempted: bool,
        comparison_decision: str,
        comparison_source: str,
        comparison_skip_reason: Optional[str],
        mismatch_class: Optional[str],
        blocking_level: str,
        fallback_decision: str,
        request_context: Dict[str, Any],
        legacy_summary: Dict[str, Any],
        pg_summary: Optional[Dict[str, Any]] = None,
        pg_source_available: bool = True,
        source_unavailable_reason: Optional[str] = None,
        query_failure_detail: Optional[str] = None,
        first_mismatch_position: Optional[int] = None,
        first_mismatch_field: Optional[str] = None,
        first_legacy_value: Any = None,
        first_pg_value: Any = None,
    ) -> Dict[str, Any]:
        return {
            "report_model": "phase_f_corporate_actions_comparison_diagnostic_v2",
            "candidate": "portfolio_corporate_actions",
            "comparison_status": str(comparison_status or "").strip(),
            "comparison_attempted": bool(comparison_attempted),
            "comparison_decision": str(comparison_decision or "").strip(),
            "comparison_source": str(comparison_source or "").strip(),
            "comparison_skip_reason": str(comparison_skip_reason or "").strip() or None,
            "mismatch_class": str(mismatch_class or "").strip() or None,
            "blocking_level": str(blocking_level or "").strip(),
            "fallback_decision": str(fallback_decision or "").strip(),
            "request_context": dict(request_context or {}),
            "owner_context": {
                "owner_user_id": self._resolve_owner_id(self.owner_id),
                "include_all_owners": self.include_all_owners,
            },
            "legacy_summary": dict(legacy_summary or {}),
            "pg_summary": dict(pg_summary) if isinstance(pg_summary, dict) else None,
            "pg_source_available": bool(pg_source_available),
            "source_unavailable_reason": str(source_unavailable_reason or "").strip() or None,
            "query_failure_detail": str(query_failure_detail or "").strip() or None,
            "first_mismatch_position": first_mismatch_position,
            "first_mismatch_field": str(first_mismatch_field or "").strip() or None,
            "first_legacy_value": first_legacy_value,
            "first_pg_value": first_pg_value,
        }

    # ------------------------------------------------------------------
    # Snapshot replay
    # ------------------------------------------------------------------
    def get_portfolio_snapshot(
        self,
        *,
        account_id: Optional[int] = None,
        as_of: Optional[date] = None,
        cost_method: str = "fifo",
    ) -> Dict[str, Any]:
        as_of_date = as_of or date.today()
        method = self._normalize_cost_method(cost_method)

        if account_id is not None:
            account = self._require_active_account(account_id)
            account_rows = [account]
        else:
            account_rows = self.repo.list_accounts(include_inactive=False, **self._owner_kwargs())

        accounts_payload: List[Dict[str, Any]] = []
        aggregate_currency = self._resolve_snapshot_currency(
            account_rows=account_rows,
            requested_account_id=account_id,
        )
        aggregate = {
            "total_cash": 0.0,
            "total_market_value": 0.0,
            "total_equity": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "fee_total": 0.0,
            "tax_total": 0.0,
            "fx_stale": False,
        }
        market_breakdown: Dict[str, Dict[str, float]] = {}

        for account in account_rows:
            account_snapshot = self._load_cached_account_snapshot(
                account=account,
                as_of_date=as_of_date,
                cost_method=method,
            )
            if account_snapshot is None:
                account_snapshot = self._build_account_snapshot(
                    account=account,
                    as_of_date=as_of_date,
                    cost_method=method,
                )

                self.repo.replace_positions_lots_and_snapshot(
                    account_id=account.id,
                    snapshot_date=as_of_date,
                    cost_method=method,
                    base_currency=account.base_currency,
                    total_cash=account_snapshot["total_cash"],
                    total_market_value=account_snapshot["total_market_value"],
                    total_equity=account_snapshot["total_equity"],
                    unrealized_pnl=account_snapshot["unrealized_pnl"],
                    realized_pnl=account_snapshot["realized_pnl"],
                    fee_total=account_snapshot["fee_total"],
                    tax_total=account_snapshot["tax_total"],
                    fx_stale=account_snapshot["fx_stale"],
                    payload=json.dumps(account_snapshot["payload"], ensure_ascii=False),
                    positions=account_snapshot["positions_cache"],
                    lots=account_snapshot["lots_cache"],
                    valuation_currency=account.base_currency,
                )

            accounts_payload.append(account_snapshot["public"])
            self._accumulate_market_breakdown(
                market_breakdown=market_breakdown,
                account_snapshot=account_snapshot["public"],
                aggregate_currency=aggregate_currency,
                as_of_date=as_of_date,
            )

            cash_cny, stale_cash, _ = self._convert_amount(
                amount=account_snapshot["total_cash"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            mv_cny, stale_mv, _ = self._convert_amount(
                amount=account_snapshot["total_market_value"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            eq_cny, stale_eq, _ = self._convert_amount(
                amount=account_snapshot["total_equity"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            realized_cny, stale_realized, _ = self._convert_amount(
                amount=account_snapshot["realized_pnl"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            unrealized_cny, stale_unrealized, _ = self._convert_amount(
                amount=account_snapshot["unrealized_pnl"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            fee_cny, stale_fee, _ = self._convert_amount(
                amount=account_snapshot["fee_total"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            tax_cny, stale_tax, _ = self._convert_amount(
                amount=account_snapshot["tax_total"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )

            aggregate["total_cash"] += cash_cny
            aggregate["total_market_value"] += mv_cny
            aggregate["total_equity"] += eq_cny
            aggregate["realized_pnl"] += realized_cny
            aggregate["unrealized_pnl"] += unrealized_cny
            aggregate["fee_total"] += fee_cny
            aggregate["tax_total"] += tax_cny
            aggregate["fx_stale"] = aggregate["fx_stale"] or any(
                [
                    stale_cash,
                    stale_mv,
                    stale_eq,
                    stale_realized,
                    stale_unrealized,
                    stale_fee,
                    stale_tax,
                ]
            )

        snapshot_payload = {
            "as_of": as_of_date.isoformat(),
            "cost_method": method,
            "currency": aggregate_currency,
            "account_count": len(account_rows),
            "total_cash": round(aggregate["total_cash"], 6),
            "total_market_value": round(aggregate["total_market_value"], 6),
            "total_equity": round(aggregate["total_equity"], 6),
            "realized_pnl": round(aggregate["realized_pnl"], 6),
            "unrealized_pnl": round(aggregate["unrealized_pnl"], 6),
            "fee_total": round(aggregate["fee_total"], 6),
            "tax_total": round(aggregate["tax_total"], 6),
            "fx_stale": aggregate["fx_stale"],
            "market_breakdown": self._build_market_breakdown_payload(
                market_breakdown=market_breakdown,
                total_market_value=aggregate["total_market_value"],
            ),
            "fx_rates": self._build_fx_rate_snapshot(
                account_rows=account_rows,
                aggregate_currency=aggregate_currency,
                as_of_date=as_of_date,
            ),
            "accounts": accounts_payload,
        }
        snapshot_payload["portfolio_attribution"] = self._build_portfolio_attribution(
            snapshot=snapshot_payload,
            as_of_date=as_of_date,
        )
        return snapshot_payload

    def _build_fx_rate_snapshot(
        self,
        *,
        account_rows: Iterable[Any],
        aggregate_currency: str,
        as_of_date: date,
    ) -> List[Dict[str, Any]]:
        pairs: Set[Tuple[str, str]] = set()
        aggregate_norm = self._normalize_currency(aggregate_currency)

        for account in account_rows:
            base_currency = self._normalize_currency(account.base_currency)
            if base_currency != aggregate_norm:
                pairs.add((base_currency, aggregate_norm))
            for currency in self._list_account_refresh_fx_currencies(
                account=account,
                as_of_date=as_of_date,
                strict=False,
            ):
                currency_norm = self._normalize_currency(currency)
                if currency_norm != base_currency:
                    pairs.add((currency_norm, base_currency))

        rows: List[Dict[str, Any]] = []
        for from_currency, to_currency in sorted(pairs):
            direct = self.repo.get_latest_fx_rate(
                from_currency=from_currency,
                to_currency=to_currency,
                as_of=as_of_date,
            )
            source_direction = "direct"
            row = direct
            rate_value: Optional[float] = float(direct.rate) if direct is not None and direct.rate > 0 else None

            if rate_value is None:
                inverse = self.repo.get_latest_fx_rate(
                    from_currency=to_currency,
                    to_currency=from_currency,
                    as_of=as_of_date,
                )
                if inverse is not None and inverse.rate > 0:
                    row = inverse
                    rate_value = 1.0 / float(inverse.rate)
                    source_direction = "inverse"

            rows.append({
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": round(rate_value, 8) if rate_value is not None else None,
                "rate_date": row.rate_date.isoformat() if row is not None and row.rate_date else None,
                "source": row.source if row is not None else "missing",
                "is_stale": True if row is None else bool(row.is_stale),
                "updated_at": row.updated_at.isoformat() if row is not None and row.updated_at else None,
                "source_direction": source_direction if row is not None else "missing",
            })
        return rows

    def refresh_fx_rates(
        self,
        *,
        account_id: Optional[int] = None,
        as_of: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Refresh account FX pairs online with stale fallback when fetch fails."""
        as_of_date = as_of or date.today()
        config = get_config()
        refresh_enabled = bool(getattr(config, "portfolio_fx_update_enabled", True))
        if account_id is not None:
            account_rows = [self._require_active_account(account_id)]
        else:
            account_rows = self.repo.list_accounts(include_inactive=False, **self._owner_kwargs())

        summary = {
            "as_of": as_of_date.isoformat(),
            "account_count": len(account_rows),
            "refresh_enabled": refresh_enabled,
            "disabled_reason": None if refresh_enabled else PORTFOLIO_FX_REFRESH_DISABLED_REASON,
            "pair_count": 0,
            "updated_count": 0,
            "stale_count": 0,
            "error_count": 0,
        }
        for account in account_rows:
            item = self._refresh_account_fx_rates(
                account=account,
                as_of_date=as_of_date,
                refresh_enabled=refresh_enabled,
            )
            summary["pair_count"] += item["pair_count"]
            summary["updated_count"] += item["updated_count"]
            summary["stale_count"] += item["stale_count"]
            summary["error_count"] += item["error_count"]
        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _validate_trade_identity(
        self,
        *,
        account_id: int,
        trade_uid: Optional[str],
        dedup_hash: Optional[str],
        session: Optional[Any] = None,
    ) -> None:
        if trade_uid and self._has_trade_uid(account_id=account_id, trade_uid=trade_uid, session=session):
            raise PortfolioConflictError(f"Duplicate trade_uid for account_id={account_id}: {trade_uid}")
        if dedup_hash and self._has_trade_dedup_hash(account_id=account_id, dedup_hash=dedup_hash, session=session):
            raise PortfolioConflictError(f"Duplicate dedup_hash for account_id={account_id}: {dedup_hash}")

    def _validate_sell_quantity(
        self,
        *,
        account_id: int,
        symbol: str,
        market: str,
        currency: str,
        trade_date: date,
        quantity: float,
        session: Optional[Any] = None,
    ) -> None:
        key = (
            canonical_stock_code(symbol),
            self._normalize_event_market(market),
            self._normalize_currency(currency),
        )
        available_quantity = self._calculate_available_quantity(
            account_id=account_id,
            key=key,
            as_of_date=trade_date,
            session=session,
        )
        if available_quantity + EPS < quantity:
            raise PortfolioOversellError(
                symbol=key[0],
                trade_date=trade_date,
                requested_quantity=quantity,
                available_quantity=available_quantity,
            )

    def _calculate_available_quantity(
        self,
        *,
        account_id: int,
        key: Tuple[str, str, str],
        as_of_date: date,
        session: Optional[Any] = None,
    ) -> float:
        if session is None:
            trades = self.repo.list_trades(account_id, as_of=as_of_date)
            corporate_actions = self.repo.list_corporate_actions(account_id, as_of=as_of_date)
        else:
            trades = self.repo.list_trades_in_session(session=session, account_id=account_id, as_of=as_of_date)
            corporate_actions = self.repo.list_corporate_actions_in_session(
                session=session,
                account_id=account_id,
                as_of=as_of_date,
            )

        events = []
        for row in corporate_actions:
            event_key = (
                canonical_stock_code(row.symbol),
                self._normalize_event_market(row.market),
                self._normalize_currency(row.currency),
            )
            if event_key == key:
                events.append(("corp", row.effective_date, row.id, row))
        for row in trades:
            event_key = (
                canonical_stock_code(row.symbol),
                self._normalize_event_market(row.market),
                self._normalize_currency(row.currency),
            )
            if event_key == key:
                events.append(("trade", row.trade_date, row.id, row))

        # Quantity validation only depends on position-changing events for one symbol.
        # Cash ledger entries do not affect shares held, so we keep the same corp->trade
        # ordering as full replay without pulling unrelated cash events into this path.
        event_priority = {"corp": 1, "trade": 2}
        events.sort(key=lambda item: (item[1], event_priority[item[0]], item[2]))

        quantity_held = 0.0
        for event_type, event_date, _, event in events:
            if event_type == "corp":
                action_type = (event.action_type or "").strip().lower()
                if action_type != "split_adjustment":
                    continue
                split_ratio = float(event.split_ratio or 0.0)
                if split_ratio <= 0:
                    raise ValueError(f"Invalid split_ratio for {key[0]}")
                if abs(split_ratio - 1.0) <= EPS:
                    continue
                quantity_held *= split_ratio
                continue

            qty = float(event.quantity or 0.0)
            if qty <= 0:
                raise ValueError(f"Invalid trade quantity for {key[0]}")
            side = (event.side or "").strip().lower()
            if side == "buy":
                quantity_held += qty
                continue
            if side != "sell":
                raise ValueError(f"Unsupported trade side: {event.side}")
            if quantity_held + EPS < qty:
                raise PortfolioOversellError(
                    symbol=key[0],
                    trade_date=event_date,
                    requested_quantity=qty,
                    available_quantity=quantity_held,
                )
            quantity_held -= qty
            if quantity_held <= EPS:
                quantity_held = 0.0

        return quantity_held

    def _validate_trade_sequence_in_session(self, *, session: Any, account_id: int) -> None:
        trades = self.repo.list_trades_in_session(
            session=session,
            account_id=account_id,
            as_of=date.max,
        )
        corporate_actions = self.repo.list_corporate_actions_in_session(
            session=session,
            account_id=account_id,
            as_of=date.max,
        )

        events = []
        for row in corporate_actions:
            events.append(("corp", row.effective_date, row.id, row))
        for row in trades:
            events.append(("trade", row.trade_date, row.id, row))

        event_priority = {"corp": 1, "trade": 2}
        events.sort(key=lambda item: (item[1], event_priority[item[0]], item[2]))

        quantity_held: Dict[Tuple[str, str, str], float] = defaultdict(float)
        for event_type, event_date, _, event in events:
            if event_type == "corp":
                action_type = (event.action_type or "").strip().lower()
                if action_type != "split_adjustment":
                    continue
                split_ratio = float(event.split_ratio or 0.0)
                if split_ratio <= 0:
                    raise ValueError(f"Invalid split_ratio for {event.symbol}")
                if abs(split_ratio - 1.0) <= EPS:
                    continue
                key = (
                    canonical_stock_code(event.symbol),
                    self._normalize_event_market(event.market),
                    self._normalize_currency(event.currency),
                )
                quantity_held[key] *= split_ratio
                continue

            key = (
                canonical_stock_code(event.symbol),
                self._normalize_event_market(event.market),
                self._normalize_currency(event.currency),
            )
            qty = float(event.quantity or 0.0)
            if qty <= 0:
                raise ValueError(f"Invalid trade quantity for {event.symbol}")
            side = (event.side or "").strip().lower()
            if side == "buy":
                quantity_held[key] += qty
                continue
            if side != "sell":
                raise ValueError(f"Unsupported trade side: {event.side}")
            available_quantity = quantity_held[key]
            if available_quantity + EPS < qty:
                raise PortfolioOversellError(
                    symbol=key[0],
                    trade_date=event_date,
                    requested_quantity=qty,
                    available_quantity=available_quantity,
                )
            quantity_held[key] -= qty
            if quantity_held[key] <= EPS:
                quantity_held[key] = 0.0

    def _replay_account(self, *, account: Any, as_of_date: date, cost_method: str) -> Dict[str, Any]:
        trades = self.repo.list_trades(account.id, as_of=as_of_date)
        cash_ledger = self.repo.list_cash_ledger(account.id, as_of=as_of_date)
        corporate_actions = self.repo.list_corporate_actions(account.id, as_of=as_of_date)

        events = []
        for row in cash_ledger:
            events.append(("cash", row.event_date, row.id, row))
        for row in trades:
            events.append(("trade", row.trade_date, row.id, row))
        for row in corporate_actions:
            events.append(("corp", row.effective_date, row.id, row))

        # Same-day deterministic ordering: cash -> corporate action -> trade.
        event_priority = {"cash": 0, "corp": 1, "trade": 2}
        events.sort(key=lambda item: (item[1], event_priority[item[0]], item[2]))

        cash_balances: Dict[str, float] = defaultdict(float)
        fees_total_base = 0.0
        taxes_total_base = 0.0
        realized_pnl_base = 0.0
        fx_stale = False
        fx_currencies_used: Set[str] = set()

        fifo_lots: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
        avg_state: Dict[Tuple[str, str, str], _AvgState] = defaultdict(_AvgState)

        for event_type, event_date, _, event in events:
            if event_type == "cash":
                currency = self._normalize_currency(event.currency)
                amount = float(event.amount or 0.0)
                if event.direction == "in":
                    cash_balances[currency] += amount
                elif event.direction == "out":
                    cash_balances[currency] -= amount
                else:
                    raise ValueError(f"Unsupported cash direction: {event.direction}")
                continue

            if event_type == "trade":
                key = (
                    canonical_stock_code(event.symbol),
                    self._normalize_event_market(event.market),
                    self._normalize_currency(event.currency),
                )
                qty = float(event.quantity or 0.0)
                price = float(event.price or 0.0)
                fee = float(event.fee or 0.0)
                tax = float(event.tax or 0.0)
                if qty <= 0 or price <= 0:
                    raise ValueError(f"Invalid trade quantity or price for {event.symbol}")

                gross = qty * price
                side = (event.side or "").lower().strip()
                if side == "buy":
                    cash_balances[key[2]] -= (gross + fee + tax)
                    if cost_method == "fifo":
                        unit_cost = (gross + fee + tax) / qty
                        fifo_lots[key].append(
                            {
                                "symbol": key[0],
                                "market": key[1],
                                "currency": key[2],
                                "open_date": event_date,
                                "remaining_quantity": qty,
                                "unit_cost": unit_cost,
                                "source_trade_id": event.id,
                            }
                        )
                    elif cost_method == "avg":
                        state = avg_state[key]
                        state.quantity += qty
                        state.total_cost += (gross + fee + tax)
                    elif cost_method == "futu_diluted":
                        state = avg_state[key]
                        state.quantity += qty
                        state.total_cost += gross
                    elif cost_method == "ths_pnl":
                        state = avg_state[key]
                        state.quantity += qty
                        state.total_cost += (gross + fee + tax)
                elif side == "sell":
                    cash_balances[key[2]] += (gross - fee - tax)
                    proceeds_net = gross - fee - tax
                    if cost_method == "fifo":
                        cost_basis = self._consume_fifo_lots(
                            fifo_lots[key],
                            qty,
                            key[0],
                            event_date,
                        )
                    elif cost_method == "avg":
                        cost_basis = self._consume_avg_position(
                            avg_state[key],
                            qty,
                            key[0],
                            event_date,
                        )
                    else:
                        state = avg_state[key]
                        cost_basis = self._consume_avg_position(
                            state,
                            qty,
                            key[0],
                            event_date,
                        )
                        if state.quantity > EPS and cost_method == "futu_diluted":
                            state.total_cost -= gross - cost_basis
                        elif state.quantity > EPS and cost_method == "ths_pnl":
                            state.total_cost -= proceeds_net - cost_basis
                    realized_local = proceeds_net - cost_basis
                    realized_base, stale_realized, _ = self._convert_amount(
                        amount=realized_local,
                        from_currency=key[2],
                        to_currency=account.base_currency,
                        as_of_date=event_date,
                    )
                    if self._normalize_currency(key[2]) != self._normalize_currency(account.base_currency):
                        fx_currencies_used.add(self._normalize_currency(key[2]))
                    realized_pnl_base += realized_base
                    fx_stale = fx_stale or stale_realized
                else:
                    raise ValueError(f"Unsupported trade side: {event.side}")

                fee_base, stale_fee, _ = self._convert_amount(
                    amount=fee,
                    from_currency=key[2],
                    to_currency=account.base_currency,
                    as_of_date=event_date,
                )
                tax_base, stale_tax, _ = self._convert_amount(
                    amount=tax,
                    from_currency=key[2],
                    to_currency=account.base_currency,
                    as_of_date=event_date,
                )
                if self._normalize_currency(key[2]) != self._normalize_currency(account.base_currency):
                    fx_currencies_used.add(self._normalize_currency(key[2]))
                fees_total_base += fee_base
                taxes_total_base += tax_base
                fx_stale = fx_stale or stale_fee or stale_tax
                continue

            if event_type == "corp":
                key = (
                    canonical_stock_code(event.symbol),
                    self._normalize_event_market(event.market),
                    self._normalize_currency(event.currency),
                )
                action_type = (event.action_type or "").strip().lower()
                if action_type == "cash_dividend":
                    per_share = float(event.cash_dividend_per_share or 0.0)
                    if per_share <= 0:
                        continue
                    qty_held = self._held_quantity(
                        key=key,
                        cost_method=cost_method,
                        fifo_lots=fifo_lots,
                        avg_state=avg_state,
                    )
                    if qty_held > EPS:
                        cash_balances[key[2]] += qty_held * per_share
                        if cost_method in {"futu_diluted", "ths_pnl"}:
                            avg_state[key].total_cost -= qty_held * per_share
                elif action_type == "split_adjustment":
                    split_ratio = float(event.split_ratio or 0.0)
                    if split_ratio <= 0:
                        raise ValueError(f"Invalid split_ratio for {event.symbol}")
                    if abs(split_ratio - 1.0) <= EPS:
                        continue
                    if cost_method == "fifo":
                        for lot in fifo_lots[key]:
                            lot["remaining_quantity"] *= split_ratio
                            lot["unit_cost"] /= split_ratio
                    else:
                        state = avg_state[key]
                        state.quantity *= split_ratio
                else:
                    raise ValueError(f"Unsupported corporate action type: {event.action_type}")

        position_rows, lot_rows, market_value_base, total_cost_base, stale_pos = self._build_positions(
            account=account,
            as_of_date=as_of_date,
            cost_method=cost_method,
            fifo_lots=fifo_lots,
            avg_state=avg_state,
            fx_currencies_used=fx_currencies_used,
        )
        fx_stale = fx_stale or stale_pos

        total_cash_base = 0.0
        for currency, amount in cash_balances.items():
            converted, stale, _ = self._convert_amount(
                amount=amount,
                from_currency=currency,
                to_currency=account.base_currency,
                as_of_date=as_of_date,
            )
            if self._normalize_currency(currency) != self._normalize_currency(account.base_currency):
                fx_currencies_used.add(self._normalize_currency(currency))
            total_cash_base += converted
            fx_stale = fx_stale or stale

        unrealized_pnl_base = market_value_base - total_cost_base
        total_equity_base = total_cash_base + market_value_base

        account_payload = {
            "account_id": account.id,
            "account_name": account.name,
            "owner_id": account.owner_id,
            "broker": account.broker,
            "market": account.market,
            "base_currency": account.base_currency,
            "as_of": as_of_date.isoformat(),
            "cost_method": cost_method,
            "total_cash": round(total_cash_base, 6),
            "total_market_value": round(market_value_base, 6),
            "total_equity": round(total_equity_base, 6),
            "realized_pnl": round(realized_pnl_base, 6),
            "unrealized_pnl": round(unrealized_pnl_base, 6),
            "fee_total": round(fees_total_base, 6),
            "tax_total": round(taxes_total_base, 6),
            "fx_stale": fx_stale,
            "positions": position_rows,
        }
        account_payload["industry_attribution"] = self._build_snapshot_industry_attribution(
            snapshot=self._wrap_account_snapshot_payload(account_payload),
            as_of_date=as_of_date,
        )

        cache_payload = dict(account_payload)
        cache_payload["_cache_meta"] = {
            "fx_currencies": sorted(fx_currencies_used),
        }

        return {
            "public": account_payload,
            "payload": cache_payload,
            "positions_cache": position_rows,
            "lots_cache": lot_rows,
            "total_cash": float(total_cash_base),
            "total_market_value": float(market_value_base),
            "total_equity": float(total_equity_base),
            "realized_pnl": float(realized_pnl_base),
            "unrealized_pnl": float(unrealized_pnl_base),
            "fee_total": float(fees_total_base),
            "tax_total": float(taxes_total_base),
            "fx_stale": fx_stale,
        }

    def _build_account_snapshot(self, *, account: Any, as_of_date: date, cost_method: str) -> Dict[str, Any]:
        sync_state = self.get_latest_broker_sync_state(portfolio_account_id=int(account.id))
        if sync_state is not None and self._should_use_broker_sync_state(sync_state=sync_state, as_of_date=as_of_date):
            return self._build_synced_account_snapshot(
                account=account,
                sync_state=sync_state,
                cost_method=cost_method,
                as_of_date=as_of_date,
            )
        return self._replay_account(account=account, as_of_date=as_of_date, cost_method=cost_method)

    @staticmethod
    def _should_use_broker_sync_state(*, sync_state: Dict[str, Any], as_of_date: date) -> bool:
        if str(sync_state.get("sync_status") or "").strip().lower() != "success":
            return False
        snapshot_date_raw = str(sync_state.get("snapshot_date") or "").strip()
        if not snapshot_date_raw:
            return False
        try:
            snapshot_date = date.fromisoformat(snapshot_date_raw)
        except ValueError:
            return False
        return snapshot_date == as_of_date

    def _build_synced_account_snapshot(
        self,
        *,
        account: Any,
        sync_state: Dict[str, Any],
        cost_method: str,
        as_of_date: date,
    ) -> Dict[str, Any]:
        positions = [
            {
                "symbol": item["symbol"],
                "market": item["market"],
                "currency": item["currency"],
                "quantity": float(item["quantity"]),
                "avg_cost": float(item["avg_cost"]),
                "total_cost": round(float(item["quantity"]) * float(item["avg_cost"]), 8),
                "last_price": float(item["last_price"]),
                "market_value_base": float(item["market_value_base"]),
                "unrealized_pnl_base": float(item["unrealized_pnl_base"]),
                "valuation_currency": item["valuation_currency"],
            }
            for item in list(sync_state.get("positions") or [])
        ]
        payload = {
            "account_id": account.id,
            "account_name": account.name,
            "owner_id": account.owner_id,
            "broker": account.broker,
            "market": account.market,
            "base_currency": sync_state.get("base_currency") or account.base_currency,
            "as_of": as_of_date.isoformat(),
            "cost_method": cost_method,
            "total_cash": round(float(sync_state.get("total_cash", 0.0) or 0.0), 6),
            "total_market_value": round(float(sync_state.get("total_market_value", 0.0) or 0.0), 6),
            "total_equity": round(float(sync_state.get("total_equity", 0.0) or 0.0), 6),
            "realized_pnl": round(float(sync_state.get("realized_pnl", 0.0) or 0.0), 6),
            "unrealized_pnl": round(float(sync_state.get("unrealized_pnl", 0.0) or 0.0), 6),
            "fee_total": 0.0,
            "tax_total": 0.0,
            "fx_stale": bool(sync_state.get("fx_stale")),
            "positions": positions,
        }
        payload["industry_attribution"] = self._build_snapshot_industry_attribution(
            snapshot=self._wrap_account_snapshot_payload(payload),
            as_of_date=as_of_date,
        )
        return {
            "public": payload,
            "payload": {
                **payload,
                "_cache_meta": {
                    "fx_currencies": [],
                },
            },
            "positions_cache": positions,
            "lots_cache": [],
            "total_cash": float(payload["total_cash"]),
            "total_market_value": float(payload["total_market_value"]),
            "total_equity": float(payload["total_equity"]),
            "realized_pnl": float(payload["realized_pnl"]),
            "unrealized_pnl": float(payload["unrealized_pnl"]),
            "fee_total": 0.0,
            "tax_total": 0.0,
            "fx_stale": bool(payload["fx_stale"]),
        }

    def _load_cached_account_snapshot(
        self,
        *,
        account: Any,
        as_of_date: date,
        cost_method: str,
    ) -> Optional[Dict[str, Any]]:
        latest_cached_snapshot_date = self.repo.get_latest_cached_snapshot_date(
            account_id=int(account.id),
            cost_method=cost_method,
        )
        if latest_cached_snapshot_date != as_of_date:
            return None

        cached = self.repo.get_cached_snapshot_bundle(
            account_id=int(account.id),
            snapshot_date=as_of_date,
            cost_method=cost_method,
        )
        if cached is None:
            return None

        snapshot_row = cached["snapshot"]
        snapshot_updated_at = getattr(snapshot_row, "updated_at", None)
        if snapshot_updated_at is None:
            return None

        payload_raw = self._parse_snapshot_payload(getattr(snapshot_row, "payload", None))
        positions_cache = [self._cached_position_row_to_dict(row) for row in cached["positions"]]
        latest_market_update = self.repo.get_latest_market_data_update(
            symbols=[item["symbol"] for item in positions_cache],
            as_of=as_of_date,
        )
        if latest_market_update is not None and latest_market_update > snapshot_updated_at:
            return None

        fx_currencies = self._extract_cached_fx_currencies(payload_raw)
        latest_fx_update = self.repo.get_latest_fx_rate_update(
            as_of=as_of_date,
            base_currency=snapshot_row.base_currency or account.base_currency,
            currencies=fx_currencies,
        )
        if latest_fx_update is None and payload_raw.get("_cache_meta") is None:
            latest_fx_update = self.repo.get_latest_fx_rate_update(as_of=as_of_date)
        if latest_fx_update is not None and latest_fx_update > snapshot_updated_at:
            return None

        lots_cache = [self._cached_lot_row_to_dict(row) for row in cached["lots"]]
        payload = self._cached_snapshot_public_payload(
            account=account,
            snapshot_row=snapshot_row,
            positions=positions_cache,
            as_of_date=as_of_date,
            cost_method=cost_method,
            payload=payload_raw,
        )
        return {
            "public": payload,
            "payload": payload,
            "positions_cache": positions_cache,
            "lots_cache": lots_cache,
            "total_cash": float(snapshot_row.total_cash or 0.0),
            "total_market_value": float(snapshot_row.total_market_value or 0.0),
            "total_equity": float(snapshot_row.total_equity or 0.0),
            "realized_pnl": float(snapshot_row.realized_pnl or 0.0),
            "unrealized_pnl": float(snapshot_row.unrealized_pnl or 0.0),
            "fee_total": float(snapshot_row.fee_total or 0.0),
            "tax_total": float(snapshot_row.tax_total or 0.0),
            "fx_stale": bool(snapshot_row.fx_stale),
        }

    def _build_positions(
        self,
        *,
        account: Any,
        as_of_date: date,
        cost_method: str,
        fifo_lots: Dict[Tuple[str, str, str], List[Dict[str, Any]]],
        avg_state: Dict[Tuple[str, str, str], _AvgState],
        fx_currencies_used: Optional[Set[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float, float, bool]:
        position_rows: List[Dict[str, Any]] = []
        lot_rows: List[Dict[str, Any]] = []
        market_value_base = 0.0
        total_cost_base = 0.0
        fx_stale = False

        keys: Iterable[Tuple[str, str, str]]
        if cost_method == "fifo":
            keys = list(fifo_lots.keys())
        else:
            keys = list(avg_state.keys())
        latest_closes = self.repo.get_latest_closes(
            symbols=[key[0] for key in keys],
            as_of=as_of_date,
        )

        for key in sorted(keys):
            symbol, market, currency = key

            if cost_method == "fifo":
                active_lots = [lot for lot in fifo_lots[key] if lot["remaining_quantity"] > EPS]
                qty = sum(float(lot["remaining_quantity"]) for lot in active_lots)
                if qty <= EPS:
                    continue
                total_cost = sum(float(lot["remaining_quantity"]) * float(lot["unit_cost"]) for lot in active_lots)
                avg_cost = total_cost / qty
                lot_rows.extend(active_lots)
            else:
                state = avg_state[key]
                qty = float(state.quantity)
                total_cost = float(state.total_cost)
                if qty <= EPS:
                    continue
                avg_cost = total_cost / qty
                lot_rows.append(
                    {
                        "symbol": symbol,
                        "market": market,
                        "currency": currency,
                        "open_date": as_of_date,
                        "remaining_quantity": qty,
                        "unit_cost": avg_cost,
                        "source_trade_id": None,
                    }
                )

            last_price = latest_closes.get(symbol)
            if last_price is None or last_price <= 0:
                last_price = avg_cost
            if (
                fx_currencies_used is not None
                and self._normalize_currency(currency) != self._normalize_currency(account.base_currency)
            ):
                fx_currencies_used.add(self._normalize_currency(currency))

            local_market_value = qty * float(last_price)
            market_base, stale_market, _ = self._convert_amount(
                amount=local_market_value,
                from_currency=currency,
                to_currency=account.base_currency,
                as_of_date=as_of_date,
            )
            cost_base, stale_cost, _ = self._convert_amount(
                amount=total_cost,
                from_currency=currency,
                to_currency=account.base_currency,
                as_of_date=as_of_date,
            )
            unrealized_base = market_base - cost_base
            fx_stale = fx_stale or stale_market or stale_cost

            position_rows.append(
                {
                    "symbol": symbol,
                    "market": market,
                    "currency": currency,
                    "quantity": round(qty, 8),
                    "avg_cost": round(avg_cost, 8),
                    "total_cost": round(total_cost, 8),
                    "last_price": round(float(last_price), 8),
                    "market_value_base": round(market_base, 8),
                    "unrealized_pnl_base": round(unrealized_base, 8),
                    "valuation_currency": account.base_currency,
                }
            )

            market_value_base += market_base
            total_cost_base += cost_base

        return position_rows, lot_rows, market_value_base, total_cost_base, fx_stale

    @staticmethod
    def _consume_fifo_lots(
        lots: List[Dict[str, Any]],
        quantity: float,
        symbol: str,
        trade_date: Optional[date] = None,
    ) -> float:
        remaining = quantity
        cost_basis = 0.0
        while remaining > EPS:
            if not lots:
                raise PortfolioOversellError(
                    symbol=symbol,
                    trade_date=trade_date,
                    requested_quantity=quantity,
                    available_quantity=quantity - remaining,
                )
            head = lots[0]
            take = min(remaining, float(head["remaining_quantity"]))
            cost_basis += take * float(head["unit_cost"])
            head["remaining_quantity"] = float(head["remaining_quantity"]) - take
            remaining -= take
            if head["remaining_quantity"] <= EPS:
                lots.pop(0)
        return cost_basis

    @staticmethod
    def _consume_avg_position(
        state: _AvgState,
        quantity: float,
        symbol: str,
        trade_date: Optional[date] = None,
    ) -> float:
        if state.quantity + EPS < quantity:
            raise PortfolioOversellError(
                symbol=symbol,
                trade_date=trade_date,
                requested_quantity=quantity,
                available_quantity=state.quantity,
            )
        if state.quantity <= EPS:
            raise PortfolioOversellError(
                symbol=symbol,
                trade_date=trade_date,
                requested_quantity=quantity,
                available_quantity=0.0,
            )
        avg_cost = state.total_cost / state.quantity
        cost_basis = avg_cost * quantity
        state.quantity -= quantity
        state.total_cost -= cost_basis
        if state.quantity <= EPS:
            state.quantity = 0.0
            state.total_cost = 0.0
        return cost_basis

    @staticmethod
    def _held_quantity(
        *,
        key: Tuple[str, str, str],
        cost_method: str,
        fifo_lots: Dict[Tuple[str, str, str], List[Dict[str, Any]]],
        avg_state: Dict[Tuple[str, str, str], _AvgState],
    ) -> float:
        if cost_method == "fifo":
            return sum(float(lot["remaining_quantity"]) for lot in fifo_lots.get(key, []))
        return float(avg_state.get(key, _AvgState()).quantity)

    def _convert_amount(
        self,
        *,
        amount: float,
        from_currency: str,
        to_currency: str,
        as_of_date: date,
    ) -> Tuple[float, bool, str]:
        from_norm = self._normalize_currency(from_currency)
        to_norm = self._normalize_currency(to_currency)
        if abs(amount) <= EPS:
            return 0.0, False, "zero"
        if from_norm == to_norm:
            return float(amount), False, "identity"

        direct = self.repo.get_latest_fx_rate(
            from_currency=from_norm,
            to_currency=to_norm,
            as_of=as_of_date,
        )
        if direct is not None and direct.rate > 0:
            return float(amount) * float(direct.rate), bool(direct.is_stale), "direct_rate"

        inverse = self.repo.get_latest_fx_rate(
            from_currency=to_norm,
            to_currency=from_norm,
            as_of=as_of_date,
        )
        if inverse is not None and inverse.rate > 0:
            return float(amount) / float(inverse.rate), bool(inverse.is_stale), "inverse_rate"

        # P0 fallback: keep pipeline available even when FX cache is missing.
        return float(amount), True, "fallback_1_to_1"

    def convert_amount(
        self,
        *,
        amount: float,
        from_currency: str,
        to_currency: str,
        as_of_date: date,
    ) -> Tuple[float, bool, str]:
        """Public conversion entry for cross-service consumers."""
        return self._convert_amount(
            amount=amount,
            from_currency=from_currency,
            to_currency=to_currency,
            as_of_date=as_of_date,
        )

    def _list_account_refresh_fx_currencies(
        self,
        *,
        account: Any,
        as_of_date: date,
        strict: bool = True,
    ) -> List[str]:
        """Return distinct non-base currencies participating in refresh for one account."""
        base_currency = self._normalize_currency(account.base_currency)
        currencies: Set[str] = set()
        rows = list(self.repo.list_trades(account.id, as_of=as_of_date))
        rows.extend(self.repo.list_cash_ledger(account.id, as_of=as_of_date))
        for row in rows:
            try:
                currency = self._normalize_currency(row.currency)
            except ValueError:
                if strict:
                    raise
                logger.warning(
                    "Skip invalid FX refresh currency for account %s on %s: %r",
                    account.id,
                    as_of_date.isoformat(),
                    getattr(row, "currency", None),
                )
                continue
            if currency != base_currency:
                currencies.add(currency)
        return sorted(currencies)

    def _refresh_account_fx_rates(
        self,
        *,
        account: Any,
        as_of_date: date,
        refresh_enabled: bool,
    ) -> Dict[str, int]:
        """Refresh FX pairs for one account and keep stale fallback on failures."""
        refresh_currencies = self._list_account_refresh_fx_currencies(
            account=account,
            as_of_date=as_of_date,
            strict=refresh_enabled,
        )
        if not refresh_enabled:
            return {
                "pair_count": len(refresh_currencies),
                "updated_count": 0,
                "stale_count": 0,
                "error_count": 0,
            }

        base_currency = self._normalize_currency(account.base_currency)
        summary = {
            "pair_count": len(refresh_currencies),
            "updated_count": 0,
            "stale_count": 0,
            "error_count": 0,
        }
        for from_currency in refresh_currencies:
            try:
                rate = self._fetch_fx_rate_from_yfinance(
                    from_currency=from_currency,
                    to_currency=base_currency,
                    as_of_date=as_of_date,
                )
                if rate is not None and rate > 0:
                    self.repo.save_fx_rate(
                        from_currency=from_currency,
                        to_currency=base_currency,
                        rate_date=as_of_date,
                        rate=rate,
                        source="frankfurter",
                        is_stale=False,
                    )
                    summary["updated_count"] += 1
                    continue
            except Exception as exc:
                logger.warning(
                    "FX online fetch failed for %s/%s on %s: %s",
                    from_currency,
                    base_currency,
                    as_of_date.isoformat(),
                    exc,
                )

            fallback = self.repo.get_latest_fx_rate(
                from_currency=from_currency,
                to_currency=base_currency,
                as_of=as_of_date,
            )
            if fallback is not None and float(fallback.rate or 0.0) > 0:
                self.repo.save_fx_rate(
                    from_currency=from_currency,
                    to_currency=base_currency,
                    rate_date=as_of_date,
                    rate=float(fallback.rate),
                    source=(fallback.source or "cache_fallback"),
                    is_stale=True,
                )
                summary["stale_count"] += 1
            else:
                summary["error_count"] += 1
        return summary

    @staticmethod
    def _fetch_fx_rate_from_yfinance(
        *,
        from_currency: str,
        to_currency: str,
        as_of_date: date,
    ) -> Optional[float]:
        """Fetch latest public FX rate.

        The method name is kept for older tests and patches; the provider is now
        Frankfurter rather than yfinance.
        """
        result = default_fx_rate_service.fetch_rate(from_currency, to_currency, force_refresh=True)
        value = float(result.get("rate") or 0.0)
        return value if value > 0 else None

    def _require_active_account(self, account_id: int) -> Any:
        account = self.repo.get_account(account_id, include_inactive=False, **self._owner_kwargs())
        if account is None:
            raise ValueError(f"Active account not found: {account_id}")
        return account

    def _require_active_account_in_session(self, *, session: Any, account_id: int) -> Any:
        account = self.repo.get_account_in_session(
            session=session,
            account_id=account_id,
            include_inactive=False,
            **self._owner_kwargs(),
        )
        if account is None:
            raise ValueError(f"Active account not found: {account_id}")
        return account

    def _has_trade_uid(self, *, account_id: int, trade_uid: str, session: Optional[Any] = None) -> bool:
        if session is None:
            return self.repo.has_trade_uid(account_id, trade_uid)
        return self.repo.has_trade_uid_in_session(session=session, account_id=account_id, trade_uid=trade_uid)

    def _has_trade_dedup_hash(
        self,
        *,
        account_id: int,
        dedup_hash: str,
        session: Optional[Any] = None,
    ) -> bool:
        if session is None:
            return self.repo.has_trade_dedup_hash(account_id, dedup_hash)
        return self.repo.has_trade_dedup_hash_in_session(
            session=session,
            account_id=account_id,
            dedup_hash=dedup_hash,
        )

    def _account_name_lookup(self) -> Dict[int, str]:
        rows = self.repo.list_accounts(include_inactive=True, **self._owner_kwargs())
        return {int(row.id): str(row.name) for row in rows}

    @staticmethod
    def _raise_missing_account(account_id: int) -> None:
        raise ValueError(f"Account not found: {account_id}")

    @staticmethod
    def _account_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "id": row.id,
            "owner_id": row.owner_id,
            "name": row.name,
            "broker": row.broker,
            "market": row.market,
            "base_currency": row.base_currency,
            "is_active": bool(row.is_active),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def _broker_connection_to_dict(row: Any, *, portfolio_account_name: Optional[str] = None) -> Dict[str, Any]:
        sync_metadata: Dict[str, Any] = {}
        if getattr(row, "sync_metadata_json", None):
            try:
                parsed = json.loads(row.sync_metadata_json)
                if isinstance(parsed, dict):
                    sync_metadata = parsed
            except Exception:
                sync_metadata = {}
        return {
            "id": int(row.id),
            "owner_id": row.owner_id,
            "portfolio_account_id": int(row.portfolio_account_id),
            "portfolio_account_name": portfolio_account_name,
            "broker_type": row.broker_type,
            "broker_name": row.broker_name,
            "connection_name": row.connection_name,
            "broker_account_ref": row.broker_account_ref,
            "import_mode": row.import_mode,
            "status": row.status,
            "last_imported_at": row.last_imported_at.isoformat() if row.last_imported_at else None,
            "last_import_source": row.last_import_source,
            "last_import_fingerprint": row.last_import_fingerprint,
            "sync_metadata": sync_metadata,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def _broker_sync_state_row_to_dict(row: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if getattr(row, "payload_json", None):
            try:
                parsed = json.loads(row.payload_json)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = {}
        return {
            "id": int(row.id),
            "owner_id": row.owner_id,
            "broker_connection_id": int(row.broker_connection_id),
            "portfolio_account_id": int(row.portfolio_account_id),
            "broker_type": row.broker_type,
            "broker_account_ref": row.broker_account_ref,
            "sync_source": row.sync_source,
            "sync_status": row.sync_status,
            "snapshot_date": row.snapshot_date.isoformat() if row.snapshot_date else None,
            "synced_at": row.synced_at.isoformat() if row.synced_at else None,
            "base_currency": row.base_currency,
            "total_cash": float(row.total_cash or 0.0),
            "total_market_value": float(row.total_market_value or 0.0),
            "total_equity": float(row.total_equity or 0.0),
            "realized_pnl": float(row.realized_pnl or 0.0),
            "unrealized_pnl": float(row.unrealized_pnl or 0.0),
            "fx_stale": bool(row.fx_stale),
            "payload": payload,
        }

    @staticmethod
    def _broker_sync_bundle_to_dict(
        row: Any,
        *,
        positions: Iterable[Any],
        cash_balances: Iterable[Any],
    ) -> Dict[str, Any]:
        data = PortfolioService._broker_sync_state_row_to_dict(row)
        data["positions"] = [
            {
                "broker_position_ref": item.broker_position_ref,
                "symbol": item.symbol,
                "market": item.market,
                "currency": item.currency,
                "quantity": float(item.quantity or 0.0),
                "avg_cost": float(item.avg_cost or 0.0),
                "last_price": float(item.last_price or 0.0),
                "market_value_base": float(item.market_value_base or 0.0),
                "unrealized_pnl_base": float(item.unrealized_pnl_base or 0.0),
                "valuation_currency": item.valuation_currency,
            }
            for item in positions
        ]
        data["cash_balances"] = [
            {
                "currency": item.currency,
                "amount": float(item.amount or 0.0),
                "amount_base": float(item.amount_base or 0.0),
            }
            for item in cash_balances
        ]
        return data

    @staticmethod
    def _cached_position_row_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "symbol": row.symbol,
            "market": row.market,
            "currency": row.currency,
            "quantity": round(float(row.quantity or 0.0), 8),
            "avg_cost": round(float(row.avg_cost or 0.0), 8),
            "total_cost": round(float(row.total_cost or 0.0), 8),
            "last_price": round(float(row.last_price or 0.0), 8),
            "market_value_base": round(float(row.market_value_base or 0.0), 8),
            "unrealized_pnl_base": round(float(row.unrealized_pnl_base or 0.0), 8),
            "valuation_currency": row.valuation_currency,
        }

    @staticmethod
    def _cached_lot_row_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "symbol": row.symbol,
            "market": row.market,
            "currency": row.currency,
            "open_date": row.open_date,
            "remaining_quantity": float(row.remaining_quantity or 0.0),
            "unit_cost": float(row.unit_cost or 0.0),
            "source_trade_id": row.source_trade_id,
        }

    @staticmethod
    def _parse_snapshot_payload(payload_raw: Optional[str]) -> Dict[str, Any]:
        if not payload_raw:
            return {}
        try:
            payload = json.loads(payload_raw)
        except Exception:
            return {}
        if isinstance(payload, dict):
            return payload
        return {}

    def _cached_snapshot_public_payload(
        self,
        *,
        account: Any,
        snapshot_row: Any,
        positions: List[Dict[str, Any]],
        as_of_date: date,
        cost_method: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        public_payload = dict(payload or self._parse_snapshot_payload(getattr(snapshot_row, "payload", None)))
        public_payload.pop("_cache_meta", None)
        public_payload.update(
            {
                "account_id": int(account.id),
                "account_name": account.name,
                "owner_id": account.owner_id,
                "broker": account.broker,
                "market": account.market,
                "base_currency": snapshot_row.base_currency or account.base_currency,
                "as_of": as_of_date.isoformat(),
                "cost_method": cost_method,
                "total_cash": round(float(snapshot_row.total_cash or 0.0), 6),
                "total_market_value": round(float(snapshot_row.total_market_value or 0.0), 6),
                "total_equity": round(float(snapshot_row.total_equity or 0.0), 6),
                "realized_pnl": round(float(snapshot_row.realized_pnl or 0.0), 6),
                "unrealized_pnl": round(float(snapshot_row.unrealized_pnl or 0.0), 6),
                "fee_total": round(float(snapshot_row.fee_total or 0.0), 6),
                "tax_total": round(float(snapshot_row.tax_total or 0.0), 6),
                "fx_stale": bool(snapshot_row.fx_stale),
                "positions": positions,
            }
        )
        return public_payload

    @staticmethod
    def _wrap_account_snapshot_payload(account_payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "currency": account_payload.get("base_currency") or "CNY",
            "total_market_value": account_payload.get("total_market_value", 0.0),
            "total_equity": account_payload.get("total_equity", 0.0),
            "accounts": [dict(account_payload)],
        }

    def _build_snapshot_industry_attribution(
        self,
        *,
        snapshot: Dict[str, Any],
        as_of_date: date,
    ) -> Dict[str, Any]:
        from src.services.portfolio_risk_service import PortfolioRiskService

        return PortfolioRiskService(repo=self.repo, portfolio_service=self)._build_industry_attribution(
            snapshot=snapshot,
            as_of_date=as_of_date,
        )

    def _build_portfolio_attribution(
        self,
        *,
        snapshot: Dict[str, Any],
        as_of_date: date,
    ) -> Dict[str, Any]:
        from src.services.portfolio_risk_service import PortfolioRiskService

        risk_service = PortfolioRiskService(repo=self.repo, portfolio_service=self)
        return {
            "account_attribution": risk_service._build_account_attribution(
                snapshot=snapshot,
                as_of_date=as_of_date,
            ),
            "industry_attribution": risk_service._build_industry_attribution(
                snapshot=snapshot,
                as_of_date=as_of_date,
            ),
        }

    @staticmethod
    def _extract_cached_fx_currencies(payload: Optional[Dict[str, Any]]) -> List[str]:
        if not isinstance(payload, dict):
            return []
        meta = payload.get("_cache_meta")
        if not isinstance(meta, dict):
            return []
        raw = meta.get("fx_currencies")
        if not isinstance(raw, list):
            return []
        return sorted({str(item or "").strip().upper() for item in raw if str(item or "").strip()})

    @staticmethod
    def _trade_row_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "id": int(row.id),
            "account_id": int(row.account_id),
            "trade_uid": row.trade_uid,
            "symbol": row.symbol,
            "market": row.market,
            "currency": row.currency,
            "trade_date": row.trade_date.isoformat() if row.trade_date else "",
            "side": row.side,
            "quantity": float(row.quantity),
            "price": float(row.price),
            "fee": float(row.fee),
            "tax": float(row.tax),
            "note": row.note,
            "is_active": bool(getattr(row, "is_active", True)),
            "voided_at": row.voided_at.isoformat() if getattr(row, "voided_at", None) else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }

    @staticmethod
    def _legacy_trade_row_to_dict(row: Any) -> Dict[str, Any]:
        payload = PortfolioService._trade_row_to_dict(row)
        payload.pop("is_active", None)
        payload.pop("voided_at", None)
        payload.pop("updated_at", None)
        return payload

    @staticmethod
    def _cash_ledger_row_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "id": int(row.id),
            "account_id": int(row.account_id),
            "event_date": row.event_date.isoformat() if row.event_date else "",
            "direction": row.direction,
            "amount": float(row.amount),
            "currency": row.currency,
            "note": row.note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _corporate_action_row_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "id": int(row.id),
            "account_id": int(row.account_id),
            "symbol": row.symbol,
            "market": row.market,
            "currency": row.currency,
            "effective_date": row.effective_date.isoformat() if row.effective_date else "",
            "action_type": row.action_type,
            "cash_dividend_per_share": (
                float(row.cash_dividend_per_share) if row.cash_dividend_per_share is not None else None
            ),
            "split_ratio": float(row.split_ratio) if row.split_ratio is not None else None,
            "note": row.note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _validate_paging(*, page: int, page_size: int) -> Tuple[int, int]:
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be in [1, 100]")
        return page, page_size

    @staticmethod
    def _normalize_account_market(value: str) -> str:
        market = (value or "").strip().lower()
        if market not in VALID_ACCOUNT_MARKETS:
            raise ValueError("market must be one of: cn, hk, us, global")
        return market

    @staticmethod
    def _normalize_event_market(value: str) -> str:
        market = (value or "").strip().lower()
        if market not in VALID_EVENT_MARKETS:
            raise ValueError("market must be one of: cn, hk, us")
        return market

    @staticmethod
    def _infer_market_from_symbol(symbol: str) -> str:
        normalized = canonical_stock_code(symbol)
        if normalized.startswith("HK"):
            return "hk"
        if normalized.isdigit():
            if len(normalized) <= 5:
                return "hk"
            return "cn"
        return "us"

    def _resolve_snapshot_currency(
        self,
        *,
        account_rows: List[Any],
        requested_account_id: Optional[int],
    ) -> str:
        if not account_rows:
            return "CNY"
        if requested_account_id is not None or len(account_rows) == 1:
            return self._normalize_currency(account_rows[0].base_currency)
        currencies = {self._normalize_currency(row.base_currency) for row in account_rows}
        if len(currencies) == 1:
            return next(iter(currencies))
        return "CNY"

    def _accumulate_market_breakdown(
        self,
        *,
        market_breakdown: Dict[str, Dict[str, float]],
        account_snapshot: Dict[str, Any],
        aggregate_currency: str,
        as_of_date: date,
    ) -> None:
        for position in list(account_snapshot.get("positions") or []):
            market = self._normalize_snapshot_position_market(
                position.get("market"),
                fallback_market=account_snapshot.get("market"),
            )
            if market is None:
                continue
            converted_market_value, _stale, _ = self._convert_amount(
                amount=float(position.get("market_value_base") or 0.0),
                from_currency=position.get("valuation_currency") or account_snapshot.get("base_currency"),
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            bucket = market_breakdown.setdefault(
                market,
                {
                    "position_count": 0.0,
                    "total_market_value": 0.0,
                },
            )
            bucket["position_count"] += 1.0
            bucket["total_market_value"] += float(converted_market_value)

    @staticmethod
    def _build_market_breakdown_payload(
        *,
        market_breakdown: Dict[str, Dict[str, float]],
        total_market_value: float,
    ) -> List[Dict[str, Any]]:
        if not market_breakdown:
            return []
        rows: List[Dict[str, Any]] = []
        denominator = float(total_market_value or 0.0)
        for market, bucket in market_breakdown.items():
            market_value = float(bucket.get("total_market_value") or 0.0)
            rows.append(
                {
                    "market": market,
                    "position_count": int(bucket.get("position_count") or 0),
                    "total_market_value": round(market_value, 6),
                    "weight_pct": round((market_value / denominator) * 100.0, 4) if denominator > 0 else 0.0,
                }
            )
        rows.sort(key=lambda item: (-float(item["total_market_value"]), str(item["market"])))
        return rows

    @staticmethod
    def _normalize_snapshot_position_market(value: Any, *, fallback_market: Any = None) -> Optional[str]:
        normalized = str(value or fallback_market or "").strip().lower()
        if normalized in VALID_EVENT_MARKETS:
            return normalized
        return None

    @staticmethod
    def _normalize_broker_type(value: str) -> str:
        broker_type = (value or "").strip().lower()
        if not broker_type or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,31}", broker_type):
            raise ValueError("broker_type must use 2-32 lowercase letters, numbers, _ or -")
        return broker_type

    @staticmethod
    def _normalize_connection_name(value: str) -> str:
        connection_name = (value or "").strip()
        if not connection_name:
            raise ValueError("connection_name is required")
        return connection_name[:64]

    @staticmethod
    def _normalize_broker_account_ref(value: Optional[str]) -> Optional[str]:
        broker_account_ref = (value or "").strip()
        return broker_account_ref[:128] or None

    @staticmethod
    def _normalize_broker_connection_status(value: str) -> str:
        status = (value or "").strip().lower()
        if status not in VALID_BROKER_CONNECTION_STATUSES:
            raise ValueError("status must be one of: active, disabled, error")
        return status

    @staticmethod
    def _normalize_import_mode(value: str) -> str:
        import_mode = (value or "").strip().lower()
        if import_mode not in VALID_BROKER_IMPORT_MODES:
            raise ValueError("import_mode must be one of: file, manual, api")
        return import_mode

    @staticmethod
    def _serialize_sync_metadata(value: Optional[Dict[str, Any]]) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("sync_metadata must be an object")
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _normalize_currency(value: str) -> str:
        currency = (value or "").strip().upper()
        if not currency:
            raise ValueError("currency is required")
        return currency

    @staticmethod
    def _normalize_cost_method(value: str) -> str:
        method = (value or "").strip().lower()
        if method not in VALID_COST_METHODS:
            raise ValueError("cost_method must be fifo, avg, futu_diluted, or ths_pnl")
        return method

    @staticmethod
    def _default_currency_for_market(market: str) -> str:
        if market == "hk":
            return "HKD"
        if market == "us":
            return "USD"
        return "CNY"
