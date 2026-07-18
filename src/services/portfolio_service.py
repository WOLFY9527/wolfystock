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

from src.config import get_config
from src.repositories.portfolio_repo import (
    DuplicateBrokerConnectionRefError,
    DuplicateTradeDedupHashError,
    DuplicateTradeUidError,
    PORTFOLIO_PERFORMANCE_CONTRACT_VERSION,
    PortfolioBusyError as RepoPortfolioBusyError,
    PortfolioRepository,
)
from src.services.fx_rate_service import default_fx_rate_service
from src.services._persisted_json import PersistedJsonState, decode_persisted_json
from src.services.portfolio_risk_diagnostics import build_portfolio_risk_diagnostics
from src.utils.symbol_normalization import canonical_stock_code
from src.utils.security import sanitize_metadata

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
FX_STATUS_LIVE = "live"
FX_STATUS_STALE = "stale"
FX_STATUS_UNAVAILABLE = "unavailable"
PORTFOLIO_DATA_STATUS_NO_ACCOUNT = "no_account"
PORTFOLIO_DATA_STATUS_NO_POSITIONS = "no_positions"
PORTFOLIO_DATA_STATUS_PROVIDER_UNAVAILABLE = "provider_unavailable"
PORTFOLIO_DATA_STATUS_STALE_OR_CACHED = "stale_or_cached"
PORTFOLIO_DATA_STATUS_READY = "ready"
PORTFOLIO_CALCULATION_STATUS_UNAVAILABLE = "calculation_unavailable"
PORTFOLIO_CALCULATION_STATUS_READY = "ready"
PORTFOLIO_PRICE_SOURCE_DAILY_CLOSE = "daily_close_quote"
PORTFOLIO_PRICE_SOURCE_BROKER_SYNC_SNAPSHOT = "broker_sync_snapshot"
PORTFOLIO_PRICE_SOURCE_AVG_COST_FALLBACK = "avg_cost_fallback"
PORTFOLIO_PRICE_FALLBACK_REASON_CURRENT_QUOTE_UNAVAILABLE = "current_quote_unavailable"
PORTFOLIO_PRICE_CONFIDENCE_LIVE = 1.0
PORTFOLIO_PRICE_CONFIDENCE_SYNC = 0.85
PORTFOLIO_PRICE_CONFIDENCE_FALLBACK = 0.25
PORTFOLIO_VALUATION_LINEAGE_SIDECAR_VERSION = "portfolio_valuation_lineage_sidecar_v1"
_PHASE_F_QUERY_FAILURE_DETAIL = "comparison_query_failed"
_PHASE_F_QUERY_FAILURE_REASON_CODES = frozenset(
    {
        "query_connection_failure",
        "query_database_failure",
        "query_execution_failure",
        "query_permission_failure",
        "query_timeout",
    }
)


def _phase_f_query_failure_reason_code(exc: BaseException) -> str:
    class_names = {cls.__name__.lower() for cls in exc.__class__.__mro__}
    if any("timeout" in name for name in class_names):
        return "query_timeout"
    if "connectionerror" in class_names:
        return "query_connection_failure"
    if "permissionerror" in class_names:
        return "query_permission_failure"
    if class_names.intersection(
        {
            "dataerror",
            "databaseerror",
            "dbapierror",
            "integrityerror",
            "interfaceerror",
            "operationalerror",
            "statementerror",
        }
    ):
        return "query_database_failure"
    return "query_execution_failure"


def _safe_phase_f_query_failure_reason_code(value: Any) -> Optional[str]:
    normalized = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    if not normalized:
        return None
    if normalized in _PHASE_F_QUERY_FAILURE_REASON_CODES:
        return normalized
    return "query_execution_failure"


class PortfolioConflictError(Exception):
    """Raised when request conflicts with existing portfolio state."""

    def __init__(
        self,
        message: str = "Portfolio request conflicts with current portfolio state.",
        *,
        reason_code: str = "portfolio_conflict",
        identifier_name: Optional[str] = None,
        identifier_value: Optional[Any] = None,
    ) -> None:
        self.reason_code = str(reason_code or "portfolio_conflict")
        self.identifier_name = identifier_name
        self.identifier_value = identifier_value
        super().__init__(message)


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
    price_cost: float = 0.0


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
            raise PortfolioConflictError(
                str(exc),
                reason_code="broker_connection_conflict",
            ) from exc
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
            raise PortfolioConflictError(
                str(exc),
                reason_code="broker_connection_conflict",
            ) from exc
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
                "Broker sync state cannot be written to a different portfolio account than the linked broker connection",
                reason_code="broker_sync_mapping_conflict",
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
        trade_uid_norm = (trade_uid or "").strip() or None
        side_norm = (side or "").strip().lower()
        try:
            with self.repo.portfolio_write_session() as session:
                return self._record_trade_in_session(
                    session=session,
                    account_id=account_id,
                    symbol=symbol,
                    trade_date=trade_date,
                    side=side_norm,
                    quantity=quantity,
                    price=price,
                    fee=fee,
                    tax=tax,
                    market=market,
                    currency=currency,
                    trade_uid=trade_uid_norm,
                    dedup_hash=dedup_hash,
                    note=note,
                )
        except DuplicateTradeUidError as exc:
            raise PortfolioConflictError(
                str(exc),
                reason_code="duplicate_trade_uid",
                identifier_name="tradeUid",
                identifier_value=trade_uid_norm,
            ) from exc
        except DuplicateTradeDedupHashError as exc:
            raise PortfolioConflictError(
                str(exc),
                reason_code="duplicate_trade_dedup_hash",
            ) from exc

    def _record_trade_in_session(
        self,
        *,
        session: Any,
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
        account = self._require_active_account_in_session(
            session=session,
            account_id=account_id,
        )
        market_hint = market
        if market_hint is None and str(account.market or "").strip().lower() == "global":
            market_hint = self._infer_market_from_symbol(symbol_norm)
        market_norm = self._normalize_event_market(market_hint or account.market)
        currency_norm = self._normalize_currency(
            currency or self._default_currency_for_market(market_norm)
        )
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
        with self.repo.portfolio_write_session() as session:
            return self._record_cash_ledger_in_session(
                session=session,
                account_id=account_id,
                event_date=event_date,
                direction=direction,
                amount=amount,
                currency=currency,
                note=note,
            )

    def _record_cash_ledger_in_session(
        self,
        *,
        session: Any,
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
        account = self._require_active_account_in_session(
            session=session,
            account_id=account_id,
        )
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
        with self.repo.portfolio_write_session() as session:
            return self._record_corporate_action_in_session(
                session=session,
                account_id=account_id,
                symbol=symbol,
                effective_date=effective_date,
                action_type=action_type,
                market=market,
                currency=currency,
                cash_dividend_per_share=cash_dividend_per_share,
                split_ratio=split_ratio,
                note=note,
            )

    def _record_corporate_action_in_session(
        self,
        *,
        session: Any,
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
        account = self._require_active_account_in_session(
            session=session,
            account_id=account_id,
        )
        market_hint = market
        if market_hint is None and str(account.market or "").strip().lower() == "global":
            symbol_norm = canonical_stock_code(symbol)
            market_hint = self._infer_market_from_symbol(symbol_norm)
        market_norm = self._normalize_event_market(market_hint or account.market)
        currency_norm = self._normalize_currency(
            currency or self._default_currency_for_market(market_norm)
        )
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
                    query_failure_reason_code=_phase_f_query_failure_reason_code(exc),
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
        query_failure_reason_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_comparison_status = str(comparison_status or "").strip()
        safe_query_failure_reason_code = _safe_phase_f_query_failure_reason_code(query_failure_reason_code)
        if normalized_comparison_status == "query_failure" and safe_query_failure_reason_code is None:
            safe_query_failure_reason_code = "query_execution_failure"
        return {
            "report_model": "phase_f_trades_list_comparison_diagnostic_v2",
            "candidate": "portfolio_trades_list",
            "comparison_status": normalized_comparison_status,
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
            "query_failure_detail": (
                _PHASE_F_QUERY_FAILURE_DETAIL if safe_query_failure_reason_code is not None else None
            ),
            "query_failure_reason_code": safe_query_failure_reason_code,
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
        query_failure_reason_code: Optional[str] = None,
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
            query_failure_reason_code=query_failure_reason_code,
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
                    query_failure_reason_code=_phase_f_query_failure_reason_code(exc),
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
        query_failure_reason_code: Optional[str] = None,
        first_mismatch_position: Optional[int] = None,
        first_mismatch_field: Optional[str] = None,
        first_legacy_value: Any = None,
        first_pg_value: Any = None,
    ) -> Dict[str, Any]:
        normalized_comparison_status = str(comparison_status or "").strip()
        safe_query_failure_reason_code = _safe_phase_f_query_failure_reason_code(query_failure_reason_code)
        if normalized_comparison_status == "query_failure" and safe_query_failure_reason_code is None:
            safe_query_failure_reason_code = "query_execution_failure"
        return {
            "report_model": "phase_f_cash_ledger_comparison_diagnostic_v1",
            "candidate": "portfolio_cash_ledger_list",
            "comparison_status": normalized_comparison_status,
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
            "query_failure_detail": (
                _PHASE_F_QUERY_FAILURE_DETAIL if safe_query_failure_reason_code is not None else None
            ),
            "query_failure_reason_code": safe_query_failure_reason_code,
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
                        query_failure_reason_code=_phase_f_query_failure_reason_code(exc),
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
                    query_failure_reason_code=_phase_f_query_failure_reason_code(exc),
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
        query_failure_reason_code: Optional[str] = None,
        first_mismatch_position: Optional[int] = None,
        first_mismatch_field: Optional[str] = None,
        first_legacy_value: Any = None,
        first_pg_value: Any = None,
    ) -> Dict[str, Any]:
        normalized_comparison_status = str(comparison_status or "").strip()
        safe_query_failure_reason_code = _safe_phase_f_query_failure_reason_code(query_failure_reason_code)
        if normalized_comparison_status == "query_failure" and safe_query_failure_reason_code is None:
            safe_query_failure_reason_code = "query_execution_failure"
        return {
            "report_model": "phase_f_corporate_actions_comparison_diagnostic_v2",
            "candidate": "portfolio_corporate_actions",
            "comparison_status": normalized_comparison_status,
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
            "query_failure_detail": (
                _PHASE_F_QUERY_FAILURE_DETAIL if safe_query_failure_reason_code is not None else None
            ),
            "query_failure_reason_code": safe_query_failure_reason_code,
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
        aggregate_valuation_coverage = self._new_conversion_coverage()

        for account in account_rows:
            account_fx_rates = self._build_fx_rate_snapshot(
                account_rows=[account],
                aggregate_currency=account.base_currency,
                as_of_date=as_of_date,
            )
            account_snapshot = self._load_cached_account_snapshot(
                account=account,
                as_of_date=as_of_date,
                cost_method=method,
            )
            loaded_from_cache = account_snapshot is not None
            if account_snapshot is None:
                account_snapshot = self._build_account_snapshot(
                    account=account,
                    as_of_date=as_of_date,
                    cost_method=method,
                )
                account_lineage = self._build_account_valuation_lineage_sidecar(
                    account_payload=account_snapshot["public"],
                    fx_rates=account_fx_rates,
                )
                account_snapshot["public"]["valuation_lineage"] = account_lineage
                account_snapshot["payload"]["valuation_lineage"] = account_lineage
                self._attach_account_availability(account_snapshot["public"], loaded_from_cache=False)
                for key in ("data_status", "calculation_status", "availability"):
                    account_snapshot["payload"][key] = account_snapshot["public"].get(key)

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

            public_snapshot = self._ensure_position_analytics_fields(
                account_payload=account_snapshot["public"],
                display_currency=account.base_currency,
            )
            self._attach_account_availability(public_snapshot, loaded_from_cache=loaded_from_cache)
            if not isinstance(public_snapshot.get("valuation_lineage"), dict):
                public_snapshot["valuation_lineage"] = self._build_account_valuation_lineage_sidecar(
                    account_payload=public_snapshot,
                    fx_rates=account_fx_rates,
                )
            accounts_payload.append(public_snapshot)
            self._merge_coverage_payload(
                aggregate_valuation_coverage,
                dict(public_snapshot.get("valuation") or {}),
                prefix=f"account:{account.id}",
            )
            self._accumulate_market_breakdown(
                market_breakdown=market_breakdown,
                account_snapshot=public_snapshot,
                aggregate_currency=aggregate_currency,
                as_of_date=as_of_date,
            )

            cash_cny, stale_cash, cash_source = self._convert_amount(
                amount=account_snapshot["total_cash"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            mv_cny, stale_mv, mv_source = self._convert_amount(
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
            self._record_conversion_coverage(
                aggregate_valuation_coverage,
                component=f"account:{account.id}:cash",
                amount=account_snapshot["total_cash"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                source=cash_source,
            )
            self._record_conversion_coverage(
                aggregate_valuation_coverage,
                component=f"account:{account.id}:market_value",
                amount=account_snapshot["total_market_value"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                source=mv_source,
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

        valuation = self._conversion_coverage_payload(aggregate_valuation_coverage)
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
            "valuation": valuation,
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
        snapshot_payload["performance"] = self._build_portfolio_performance(
            snapshot=snapshot_payload,
            aggregate_currency=aggregate_currency,
            as_of_date=as_of_date,
        )
        self._attach_snapshot_availability(snapshot_payload)
        snapshot_payload["portfolio_attribution"] = self._build_portfolio_attribution(
            snapshot=snapshot_payload,
            as_of_date=as_of_date,
        )
        snapshot_payload["analytics"] = self._build_snapshot_analytics(
            snapshot=snapshot_payload,
            account_rows=account_rows,
            aggregate_currency=aggregate_currency,
            as_of_date=as_of_date,
        )
        snapshot_payload.update(
            build_portfolio_risk_diagnostics(
                portfolio_service=self,
                snapshot=snapshot_payload,
                account_id=account_id,
                as_of=as_of_date,
                cost_method=method,
            )
        )
        snapshot_payload.update(self._build_portfolio_lineage_summary(snapshot=snapshot_payload))
        snapshot_payload["valuation_lineage"] = self._build_portfolio_valuation_lineage_sidecar(
            snapshot=snapshot_payload
        )
        return snapshot_payload

    def _attach_account_availability(self, account_payload: Dict[str, Any], *, loaded_from_cache: bool) -> None:
        position_count = len(account_payload.get("positions") or [])
        valuation = dict(account_payload.get("valuation") or {})
        if position_count == 0:
            data_status = PORTFOLIO_DATA_STATUS_NO_POSITIONS
        elif self._account_has_unavailable_provider_data(account_payload):
            data_status = PORTFOLIO_DATA_STATUS_PROVIDER_UNAVAILABLE
        elif loaded_from_cache or bool(account_payload.get("fx_stale")):
            data_status = PORTFOLIO_DATA_STATUS_STALE_OR_CACHED
        else:
            data_status = PORTFOLIO_DATA_STATUS_READY

        calculation_status = (
            PORTFOLIO_CALCULATION_STATUS_UNAVAILABLE
            if data_status == PORTFOLIO_DATA_STATUS_NO_POSITIONS
            else PORTFOLIO_CALCULATION_STATUS_READY
        )
        account_payload["data_status"] = data_status
        account_payload["calculation_status"] = calculation_status
        account_payload["availability"] = {
            "status": data_status,
            "reason": data_status,
            "metrics_ready": calculation_status == PORTFOLIO_CALCULATION_STATUS_READY,
            "account_count": 1,
            "position_count": position_count,
            "valuation": valuation,
            "performance": self._performance_availability(account_payload.get("performance")),
        }

    def _attach_snapshot_availability(self, snapshot_payload: Dict[str, Any]) -> None:
        accounts = list(snapshot_payload.get("accounts") or [])
        position_count = sum(len(account.get("positions") or []) for account in accounts)
        valuation = dict(snapshot_payload.get("valuation") or {})
        if not accounts:
            data_status = PORTFOLIO_DATA_STATUS_NO_ACCOUNT
        elif position_count == 0:
            data_status = PORTFOLIO_DATA_STATUS_NO_POSITIONS
        elif any(account.get("data_status") == PORTFOLIO_DATA_STATUS_PROVIDER_UNAVAILABLE for account in accounts):
            data_status = PORTFOLIO_DATA_STATUS_PROVIDER_UNAVAILABLE
        elif any(account.get("data_status") == PORTFOLIO_DATA_STATUS_STALE_OR_CACHED for account in accounts):
            data_status = PORTFOLIO_DATA_STATUS_STALE_OR_CACHED
        else:
            data_status = PORTFOLIO_DATA_STATUS_READY

        calculation_status = (
            PORTFOLIO_CALCULATION_STATUS_UNAVAILABLE
            if data_status in {PORTFOLIO_DATA_STATUS_NO_ACCOUNT, PORTFOLIO_DATA_STATUS_NO_POSITIONS}
            else PORTFOLIO_CALCULATION_STATUS_READY
        )
        snapshot_payload["data_status"] = data_status
        snapshot_payload["calculation_status"] = calculation_status
        snapshot_payload["availability"] = {
            "status": data_status,
            "reason": data_status,
            "metrics_ready": calculation_status == PORTFOLIO_CALCULATION_STATUS_READY,
            "account_count": len(accounts),
            "position_count": position_count,
            "valuation": valuation,
            "performance": self._performance_availability(snapshot_payload.get("performance")),
        }

    @staticmethod
    def _performance_availability(value: Any) -> Dict[str, Any]:
        performance = value if isinstance(value, dict) else {}
        return_contract = performance.get("return") if isinstance(performance.get("return"), dict) else {}
        return {
            "calculation_state": str(performance.get("calculation_state") or "unavailable"),
            "return_status": str(return_contract.get("status") or "unavailable"),
            "return_reason": return_contract.get("reason"),
        }

    @staticmethod
    def _account_has_unavailable_provider_data(account_payload: Dict[str, Any]) -> bool:
        for position in list(account_payload.get("positions") or []):
            if position.get("display_fx_status") == FX_STATUS_UNAVAILABLE:
                return True
            if position.get("is_price_fallback") is True:
                return True
        return False

    def _build_portfolio_lineage_summary(self, *, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        price_lineage = self._build_price_lineage(snapshot=snapshot)
        fx_lineage = self._build_fx_lineage(snapshot=snapshot)
        valuation_snapshot_lineage = self._build_valuation_snapshot_lineage(
            snapshot=snapshot,
            price_lineage=price_lineage,
            fx_lineage=fx_lineage,
        )
        analytics_readiness = self._build_analytics_readiness(
            snapshot=snapshot,
            valuation_snapshot_lineage=valuation_snapshot_lineage,
        )
        return {
            "price_lineage": price_lineage,
            "fx_lineage": fx_lineage,
            "valuation_snapshot_lineage": valuation_snapshot_lineage,
            "analytics_readiness": analytics_readiness,
        }

    def _build_account_valuation_lineage_sidecar(
        self,
        *,
        account_payload: Dict[str, Any],
        fx_rates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        positions = [dict(item) for item in list(account_payload.get("positions") or []) if isinstance(item, dict)]
        as_of_value = str(account_payload.get("as_of") or "").strip()
        cost_method = str(account_payload.get("cost_method") or "").strip()
        account_id = int(account_payload.get("account_id") or 0)
        owner_id = str(account_payload.get("owner_id") or "").strip()
        base_currency = self._normalize_currency(account_payload.get("base_currency") or "CNY")
        snapshot_id = self._valuation_snapshot_id(
            owner_id=owner_id,
            account_id=account_id,
            as_of=as_of_value,
            cost_method=cost_method,
        )

        price_refs: List[Dict[str, Any]] = []
        missing_evidence: List[str] = []
        degraded_evidence: List[str] = []
        confidence_values: List[float] = []
        for position in positions:
            symbol = str(position.get("symbol") or "").strip().upper()
            market = str(position.get("market") or "").strip().lower()
            currency = self._normalize_currency(position.get("currency") or base_currency)
            price_source = str(position.get("price_source") or "missing").strip() or "missing"
            price_as_of = str(position.get("price_as_of") or "").strip() or None
            is_fallback = bool(position.get("is_price_fallback")) or price_source == PORTFOLIO_PRICE_SOURCE_AVG_COST_FALLBACK
            freshness = "fresh"
            if is_fallback or price_source == "missing":
                freshness = "missing"
                self._append_lineage_evidence(missing_evidence, "price_missing")
                self._append_lineage_evidence(degraded_evidence, f"price_fallback:{symbol}" if symbol else "price_fallback")
            elif price_as_of and as_of_value and price_as_of < as_of_value:
                freshness = "stale"
                self._append_lineage_evidence(missing_evidence, "price_stale")
                self._append_lineage_evidence(degraded_evidence, f"price_stale:{symbol}" if symbol else "price_stale")
            elif price_source == PORTFOLIO_PRICE_SOURCE_BROKER_SYNC_SNAPSHOT:
                freshness = "delayed"
                self._append_lineage_evidence(degraded_evidence, f"price_delayed:{symbol}" if symbol else "price_delayed")
            confidence = position.get("valuation_confidence")
            try:
                if confidence is not None:
                    confidence_values.append(float(confidence))
            except (TypeError, ValueError):
                pass
            price_refs.append(
                {
                    "ref_id": f"price:{symbol or 'UNKNOWN'}:{market or 'unknown'}:{price_as_of or 'missing'}:{price_source}",
                    "symbol": symbol or None,
                    "market": market or None,
                    "currency": currency,
                    "source": price_source,
                    "as_of": price_as_of,
                    "freshness": freshness,
                    "is_fallback": is_fallback,
                    "fallback_reason": position.get("price_fallback_reason"),
                    "valuation_confidence": position.get("valuation_confidence"),
                }
            )

        fx_refs: List[Dict[str, Any]] = []
        for position in positions:
            currency = self._normalize_currency(position.get("currency") or base_currency)
            if currency == base_currency:
                pair = f"{currency}/{base_currency}"
                fx_refs.append(
                    {
                        "ref_id": f"fx:{pair}:identity",
                        "pair": pair,
                        "from_currency": currency,
                        "to_currency": base_currency,
                        "rate_date": as_of_value or None,
                        "source": "identity",
                        "source_direction": "identity",
                        "freshness": "fresh",
                        "is_stale": False,
                        "rate_available": True,
                    }
                )

        for row in fx_rates:
            from_currency = self._normalize_currency(row.get("from_currency") or "")
            to_currency = self._normalize_currency(row.get("to_currency") or "")
            pair = f"{from_currency}/{to_currency}"
            source = str(row.get("source") or "missing").strip() or "missing"
            source_direction = str(row.get("source_direction") or "missing").strip() or "missing"
            rate_available = row.get("rate") not in (None, "") and source != "missing" and source_direction != "missing"
            if not rate_available:
                freshness = "missing"
                self._append_lineage_evidence(missing_evidence, "fx_missing")
                self._append_lineage_evidence(degraded_evidence, f"fx_missing:{pair}")
            elif bool(row.get("is_stale")):
                freshness = "stale"
                self._append_lineage_evidence(missing_evidence, "fx_stale")
                self._append_lineage_evidence(degraded_evidence, f"fx_stale:{pair}")
            else:
                freshness = "fresh"
            fx_refs.append(
                {
                    "ref_id": f"fx:{pair}:{row.get('rate_date') or 'missing'}:{source_direction}",
                    "pair": pair,
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "rate_date": row.get("rate_date"),
                    "source": source,
                    "source_direction": source_direction,
                    "freshness": freshness,
                    "is_stale": bool(row.get("is_stale")),
                    "rate_available": rate_available,
                }
            )

        if not positions:
            state = "blocked"
            self._append_lineage_evidence(missing_evidence, "positions_missing")
        elif any(item["freshness"] == "missing" for item in price_refs + fx_refs):
            state = "partial"
        elif any(item["freshness"] in {"stale", "delayed"} for item in price_refs + fx_refs):
            state = "partial"
        else:
            state = "complete"

        freshness = self._lineage_sidecar_freshness(price_refs=price_refs, fx_refs=fx_refs)
        confidence = round(min(confidence_values), 2) if confidence_values else (0.0 if positions else None)
        return {
            "read_model_type": PORTFOLIO_VALUATION_LINEAGE_SIDECAR_VERSION,
            "accounting_truth": {
                "authority": "portfolio_ledger",
                "scope": "account",
                "owner_id": owner_id or None,
                "account_id": account_id,
                "cost_method": cost_method,
                "not_recalculated": True,
                "protected_fields": [
                    "holdings",
                    "cash",
                    "transactions",
                    "cost_basis",
                    "realized_pnl",
                    "unrealized_pnl",
                    "fx_conversion",
                ],
            },
            "valuation_snapshot": {
                "snapshot_id": snapshot_id,
                "owner_id": owner_id or None,
                "account_id": account_id,
                "as_of": as_of_value or None,
                "cost_method": cost_method,
                "base_currency": base_currency,
                "valuation_currency": base_currency,
            },
            "price_evidence": {
                "status": self._lineage_ref_status(price_refs),
                "refs": price_refs,
            },
            "fx_evidence": {
                "status": self._lineage_ref_status(fx_refs),
                "refs": fx_refs,
            },
            "benchmark_lineage": {
                "status": "unmapped",
                "refs": [],
                "missing_evidence": ["benchmark_mapping"],
            },
            "factor_risk_lineage": {
                "status": "unmapped",
                "refs": [],
                "missing_evidence": ["factor_mapping"],
            },
            "readiness": {
                "state": state,
                "freshness": freshness,
                "confidence": confidence,
                "confidence_source": "position_valuation_confidence_min",
                "missing_evidence": missing_evidence,
                "degraded_evidence": degraded_evidence,
                "partial": state == "partial",
                "degraded": bool(degraded_evidence),
            },
        }

    def _build_portfolio_valuation_lineage_sidecar(self, *, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        account_lineages = [
            dict(account.get("valuation_lineage") or {})
            for account in list(snapshot.get("accounts") or [])
            if isinstance(account, dict) and isinstance(account.get("valuation_lineage"), dict)
        ]
        price_refs: List[Dict[str, Any]] = []
        fx_refs: List[Dict[str, Any]] = []
        missing_evidence: List[str] = []
        degraded_evidence: List[str] = []
        owner_ids: Set[str] = set()
        account_ids: Set[int] = set()
        for lineage in account_lineages:
            valuation_snapshot = lineage.get("valuation_snapshot") if isinstance(lineage.get("valuation_snapshot"), dict) else {}
            owner_id = str(valuation_snapshot.get("owner_id") or "").strip()
            if owner_id:
                owner_ids.add(owner_id)
            try:
                account_ids.add(int(valuation_snapshot.get("account_id")))
            except (TypeError, ValueError):
                pass
            price_section = lineage.get("price_evidence") if isinstance(lineage.get("price_evidence"), dict) else {}
            fx_section = lineage.get("fx_evidence") if isinstance(lineage.get("fx_evidence"), dict) else {}
            price_refs.extend([dict(item) for item in list(price_section.get("refs") or []) if isinstance(item, dict)])
            fx_refs.extend([dict(item) for item in list(fx_section.get("refs") or []) if isinstance(item, dict)])
            readiness = lineage.get("readiness") if isinstance(lineage.get("readiness"), dict) else {}
            for item in list(readiness.get("missing_evidence") or []):
                self._append_lineage_evidence(missing_evidence, str(item))
            for item in list(readiness.get("degraded_evidence") or []):
                self._append_lineage_evidence(degraded_evidence, str(item))

        aggregate_fx_refs = self._aggregate_fx_lineage_refs(snapshot=snapshot)
        existing_fx_ref_ids = {str(item.get("ref_id") or "") for item in fx_refs}
        for ref in aggregate_fx_refs:
            ref_id = str(ref.get("ref_id") or "")
            if ref_id and ref_id not in existing_fx_ref_ids:
                fx_refs.append(ref)
                existing_fx_ref_ids.add(ref_id)
            freshness = str(ref.get("freshness") or "").strip().lower()
            pair = str(ref.get("pair") or "unknown").strip()
            if freshness == "missing":
                self._append_lineage_evidence(missing_evidence, "fx_missing")
                self._append_lineage_evidence(degraded_evidence, f"fx_missing:{pair}")
            elif freshness == "stale":
                self._append_lineage_evidence(missing_evidence, "fx_stale")
                self._append_lineage_evidence(degraded_evidence, f"fx_stale:{pair}")

        benchmark_state = str(snapshot.get("benchmarkMappingState") or "unmapped")
        factor_state = str(snapshot.get("factorMappingState") or "unmapped")
        valuation_state = str(dict(snapshot.get("valuation_snapshot_lineage") or {}).get("status") or "blocked")
        return {
            "read_model_type": PORTFOLIO_VALUATION_LINEAGE_SIDECAR_VERSION,
            "accounting_truth": {
                "authority": "portfolio_ledger",
                "scope": "portfolio",
                "owner_ids": sorted(owner_ids),
                "account_ids": sorted(account_ids),
                "not_recalculated": True,
            },
            "valuation_snapshot": {
                "snapshot_id": self._valuation_snapshot_id(
                    owner_id=",".join(sorted(owner_ids)) or "unknown",
                    account_id=0,
                    as_of=str(snapshot.get("as_of") or ""),
                    cost_method=str(snapshot.get("cost_method") or ""),
                ),
                "owner_ids": sorted(owner_ids),
                "account_ids": sorted(account_ids),
                "as_of": snapshot.get("as_of"),
                "cost_method": snapshot.get("cost_method"),
                "valuation_currency": snapshot.get("currency"),
            },
            "price_evidence": {
                "status": str(dict(snapshot.get("price_lineage") or {}).get("status") or self._lineage_ref_status(price_refs)),
                "refs": price_refs,
            },
            "fx_evidence": {
                "status": str(dict(snapshot.get("fx_lineage") or {}).get("status") or self._lineage_ref_status(fx_refs)),
                "refs": fx_refs,
            },
            "benchmark_lineage": {
                "status": benchmark_state,
                "refs": [],
                "missing_evidence": ["benchmark_mapping"] if benchmark_state in {"unmapped", "not_configured"} else [],
            },
            "factor_risk_lineage": {
                "status": factor_state,
                "refs": self._portfolio_risk_source_refs(snapshot=snapshot),
                "missing_evidence": ["factor_mapping"] if factor_state in {"unmapped", "not_configured"} else [],
            },
            "readiness": {
                "state": valuation_state,
                "freshness": self._lineage_sidecar_freshness(price_refs=price_refs, fx_refs=fx_refs),
                "missing_evidence": missing_evidence,
                "degraded_evidence": degraded_evidence,
                "partial": valuation_state == "partial",
                "degraded": bool(degraded_evidence),
            },
        }

    @staticmethod
    def _aggregate_fx_lineage_refs(*, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        refs: List[Dict[str, Any]] = []
        for row in list(snapshot.get("fx_rates") or []):
            if not isinstance(row, dict):
                continue
            from_currency = str(row.get("from_currency") or "").strip().upper()
            to_currency = str(row.get("to_currency") or "").strip().upper()
            if not from_currency or not to_currency:
                continue
            pair = f"{from_currency}/{to_currency}"
            source = str(row.get("source") or "missing").strip() or "missing"
            source_direction = str(row.get("source_direction") or "missing").strip() or "missing"
            rate_available = row.get("rate") not in (None, "") and source != "missing" and source_direction != "missing"
            if not rate_available:
                freshness = "missing"
            elif bool(row.get("is_stale")):
                freshness = "stale"
            else:
                freshness = "fresh"
            refs.append(
                {
                    "ref_id": f"fx:{pair}:{row.get('rate_date') or 'missing'}:{source_direction}",
                    "pair": pair,
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "rate_date": row.get("rate_date"),
                    "source": source,
                    "source_direction": source_direction,
                    "freshness": freshness,
                    "is_stale": bool(row.get("is_stale")),
                    "rate_available": rate_available,
                    "scope": "portfolio_aggregate",
                }
            )
        return refs

    @staticmethod
    def _valuation_snapshot_id(*, owner_id: str, account_id: int, as_of: str, cost_method: str) -> str:
        owner_part = str(owner_id or "unknown").strip() or "unknown"
        as_of_part = str(as_of or "unknown").strip() or "unknown"
        method_part = str(cost_method or "unknown").strip() or "unknown"
        return f"portfolio_valuation:{owner_part}:{int(account_id)}:{as_of_part}:{method_part}"

    @staticmethod
    def _append_lineage_evidence(target: List[str], value: str) -> None:
        text = str(value or "").strip()
        if text and text not in target:
            target.append(text)

    @staticmethod
    def _lineage_ref_status(refs: List[Dict[str, Any]]) -> str:
        if not refs:
            return "missing"
        freshness_values = {str(item.get("freshness") or "").strip().lower() for item in refs}
        if freshness_values == {"missing"}:
            return "missing"
        if "missing" in freshness_values:
            return "partial"
        if freshness_values & {"stale", "delayed"}:
            return "stale"
        return "available"

    @staticmethod
    def _lineage_sidecar_freshness(*, price_refs: List[Dict[str, Any]], fx_refs: List[Dict[str, Any]]) -> str:
        freshness_values = {
            str(item.get("freshness") or "").strip().lower()
            for item in list(price_refs or []) + list(fx_refs or [])
            if isinstance(item, dict)
        }
        if not freshness_values:
            return "missing"
        if "missing" in freshness_values:
            return "missing"
        if "stale" in freshness_values:
            return "stale"
        if "delayed" in freshness_values:
            return "delayed"
        return "fresh"

    @staticmethod
    def _portfolio_risk_source_refs(*, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        evidence = snapshot.get("portfolioRiskEvidence") if isinstance(snapshot.get("portfolioRiskEvidence"), dict) else {}
        refs: List[Dict[str, Any]] = []
        for item in list(evidence.get("source_refs") or []):
            if not isinstance(item, dict):
                continue
            refs.append(
                {
                    "ref_id": item.get("source_ref_id"),
                    "provider": item.get("provider"),
                    "source_class": item.get("source_class"),
                    "raw_payload_stored": bool(item.get("raw_payload_stored")),
                }
            )
        return refs

    def _build_price_lineage(self, *, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        positions = self._snapshot_positions(snapshot)
        counts = {
            "total": len(positions),
            "available": 0,
            "missing": 0,
            "stale": 0,
            "delayed": 0,
            "fallback": 0,
        }
        affected_symbols: Dict[str, Set[str]] = {
            "available": set(),
            "missing": set(),
            "stale": set(),
            "delayed": set(),
            "fallback": set(),
        }
        last_updated_at: Optional[str] = None
        snapshot_as_of = str(snapshot.get("as_of") or "").strip()

        for position in positions:
            symbol = str(position.get("symbol") or "").strip().upper()
            price_source = str(position.get("price_source") or "").strip()
            price_as_of = str(position.get("price_as_of") or "").strip() or None
            is_fallback = bool(position.get("is_price_fallback")) or price_source == PORTFOLIO_PRICE_SOURCE_AVG_COST_FALLBACK
            if price_as_of and (last_updated_at is None or price_as_of > last_updated_at):
                last_updated_at = price_as_of

            if is_fallback:
                counts["missing"] += 1
                counts["fallback"] += 1
                if symbol:
                    affected_symbols["missing"].add(symbol)
                    affected_symbols["fallback"].add(symbol)
                continue
            if price_source == PORTFOLIO_PRICE_SOURCE_BROKER_SYNC_SNAPSHOT:
                counts["available"] += 1
                counts["delayed"] += 1
                if symbol:
                    affected_symbols["available"].add(symbol)
                    affected_symbols["delayed"].add(symbol)
                continue
            if price_as_of and snapshot_as_of and price_as_of < snapshot_as_of:
                counts["available"] += 1
                counts["stale"] += 1
                if symbol:
                    affected_symbols["available"].add(symbol)
                    affected_symbols["stale"].add(symbol)
                continue
            counts["available"] += 1
            if symbol:
                affected_symbols["available"].add(symbol)

        status = self._lineage_status(
            total=counts["total"],
            missing=counts["missing"],
            stale=counts["stale"],
            delayed=counts["delayed"],
            fallback=counts["fallback"],
        )
        return {
            "status": status,
            "score_authority": "authoritative" if status == "available" else "observation_only",
            "counts": counts,
            "affected_symbols": self._sorted_set_map(affected_symbols),
            "last_updated_at": last_updated_at,
        }

    def _build_fx_lineage(self, *, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        positions = self._snapshot_positions(snapshot)
        rows = [dict(item) for item in list(snapshot.get("fx_rates") or []) if isinstance(item, dict)]
        counts = {
            "total": len(rows),
            "available": 0,
            "missing": 0,
            "stale": 0,
            "fallback": 0,
            "identity": 0,
        }
        affected_currencies: Dict[str, Set[str]] = {
            "available": set(),
            "missing": set(),
            "stale": set(),
            "fallback": set(),
            "identity": set(),
        }
        affected_pairs: Dict[str, Set[str]] = {
            "available": set(),
            "missing": set(),
            "stale": set(),
            "fallback": set(),
            "identity": set(),
        }
        last_updated_at: Optional[str] = None

        for account in list(snapshot.get("accounts") or []):
            if not isinstance(account, dict):
                continue
            base_currency = self._normalize_currency(account.get("base_currency") or snapshot.get("currency") or "CNY")
            for position in list(account.get("positions") or []):
                if not isinstance(position, dict):
                    continue
                currency = self._normalize_currency(position.get("currency") or base_currency)
                if currency == base_currency:
                    counts["identity"] += 1
                    affected_currencies["identity"].add(currency)
                    affected_pairs["identity"].add(f"{currency}/{base_currency}")

        for row in rows:
            from_currency = self._normalize_currency(row.get("from_currency") or "")
            to_currency = self._normalize_currency(row.get("to_currency") or "")
            pair = f"{from_currency}/{to_currency}"
            updated_at = str(row.get("updated_at") or row.get("rate_date") or "").strip() or None
            if updated_at and (last_updated_at is None or updated_at > last_updated_at):
                last_updated_at = updated_at
            source = str(row.get("source") or "").strip().lower()
            source_direction = str(row.get("source_direction") or "").strip().lower()
            rate = row.get("rate")
            if rate in (None, "") or source == "missing" or source_direction == "missing":
                counts["missing"] += 1
                counts["fallback"] += 1
                affected_currencies["missing"].add(from_currency)
                affected_currencies["fallback"].add(from_currency)
                affected_pairs["missing"].add(pair)
                affected_pairs["fallback"].add(pair)
                continue
            if bool(row.get("is_stale")):
                counts["stale"] += 1
                affected_currencies["stale"].add(from_currency)
                affected_pairs["stale"].add(pair)
                continue
            counts["available"] += 1
            affected_currencies["available"].add(from_currency)
            affected_pairs["available"].add(pair)

        if rows:
            status = self._lineage_status(
                total=len(rows),
                missing=counts["missing"],
                stale=counts["stale"],
                delayed=0,
                fallback=counts["fallback"],
            )
        elif positions:
            status = "available" if counts["identity"] > 0 else "missing"
        else:
            status = "missing"
        return {
            "status": status,
            "score_authority": "authoritative" if status == "available" else "observation_only",
            "counts": counts,
            "affected_currencies": self._sorted_set_map(affected_currencies),
            "affected_pairs": self._sorted_set_map(affected_pairs),
            "last_updated_at": last_updated_at,
        }

    def _build_valuation_snapshot_lineage(
        self,
        *,
        snapshot: Dict[str, Any],
        price_lineage: Dict[str, Any],
        fx_lineage: Dict[str, Any],
    ) -> Dict[str, Any]:
        availability = snapshot.get("availability") if isinstance(snapshot.get("availability"), dict) else {}
        metrics_ready = bool(availability.get("metrics_ready"))
        data_status = str(snapshot.get("data_status") or "").strip().lower()
        calculation_status = str(snapshot.get("calculation_status") or "").strip().lower()
        position_count = int(dict(price_lineage.get("counts") or {}).get("total", 0) or 0)
        price_status = str(price_lineage.get("status") or "").strip().lower()
        fx_status = str(fx_lineage.get("status") or "").strip().lower()

        blocked = (
            not metrics_ready
            or position_count == 0
            or calculation_status == PORTFOLIO_CALCULATION_STATUS_UNAVAILABLE
            or data_status in {PORTFOLIO_DATA_STATUS_NO_ACCOUNT, PORTFOLIO_DATA_STATUS_NO_POSITIONS}
        )
        if blocked:
            status = "blocked"
        elif price_status == "available" and fx_status == "available" and data_status == PORTFOLIO_DATA_STATUS_READY:
            status = "complete"
        else:
            status = "partial"

        price_symbols = dict(price_lineage.get("affected_symbols") or {})
        fx_pairs = dict(fx_lineage.get("affected_pairs") or {})
        fx_currencies = dict(fx_lineage.get("affected_currencies") or {})
        blocked_by = {
            "price_symbols": sorted(
                set(price_symbols.get("missing") or [])
                | set(price_symbols.get("stale") or [])
                | set(price_symbols.get("delayed") or [])
                | set(price_symbols.get("fallback") or [])
            ),
            "fx_pairs": sorted(
                set(fx_pairs.get("missing") or []) | set(fx_pairs.get("stale") or []) | set(fx_pairs.get("fallback") or [])
            ),
            "fx_currencies": sorted(
                set(fx_currencies.get("missing") or [])
                | set(fx_currencies.get("stale") or [])
                | set(fx_currencies.get("fallback") or [])
            ),
        }
        last_candidates = [
            str(value)
            for value in (price_lineage.get("last_updated_at"), fx_lineage.get("last_updated_at"), snapshot.get("as_of"))
            if value
        ]
        return {
            "status": status,
            "score_authority": "authoritative" if status == "complete" else "observation_only",
            "snapshot_state": "cached_or_stale" if data_status == PORTFOLIO_DATA_STATUS_STALE_OR_CACHED else data_status,
            "metrics_ready": metrics_ready,
            "position_count": position_count,
            "complete_position_count": position_count if status == "complete" else 0,
            "partial_position_count": position_count if status == "partial" else 0,
            "blocked_position_count": position_count if status == "blocked" else 0,
            "blocked_by": blocked_by,
            "last_updated_at": max(last_candidates) if last_candidates else None,
        }

    @staticmethod
    def _build_analytics_readiness(
        *,
        snapshot: Dict[str, Any],
        valuation_snapshot_lineage: Dict[str, Any],
    ) -> Dict[str, Any]:
        valuation_status = str(valuation_snapshot_lineage.get("status") or "blocked")
        analytics = snapshot.get("analytics") if isinstance(snapshot.get("analytics"), dict) else {}
        risk = analytics.get("risk") if isinstance(analytics.get("risk"), dict) else {}
        if valuation_status == "blocked":
            risk_status = "blocked"
        elif bool(risk.get("fx_unavailable")) or valuation_status == "partial":
            risk_status = "partial"
        else:
            risk_status = "available"
        score_authority = "authoritative" if valuation_status == "complete" and risk_status == "available" else "observation_only"
        return {
            "valuation": valuation_status,
            "risk": risk_status,
            "score_authority": score_authority,
            "observation_only": score_authority != "authoritative",
            "read_model_boundary": "no_advice",
            "affected_symbols": dict(valuation_snapshot_lineage.get("blocked_by") or {}).get("price_symbols", []),
            "affected_currencies": dict(valuation_snapshot_lineage.get("blocked_by") or {}).get("fx_currencies", []),
            "warning_codes": list(risk.get("warnings") or []) if isinstance(risk.get("warnings"), list) else [],
        }

    @staticmethod
    def _lineage_status(*, total: int, missing: int, stale: int, delayed: int, fallback: int) -> str:
        if total <= 0:
            return "missing"
        if missing > 0 and missing >= total:
            return "missing"
        if missing > 0 or fallback > 0:
            return "partial"
        if stale > 0 or delayed > 0:
            return "stale"
        return "available"

    @staticmethod
    def _sorted_set_map(value: Dict[str, Set[str]]) -> Dict[str, List[str]]:
        return {key: sorted(items) for key, items in value.items()}

    @staticmethod
    def _snapshot_positions(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        positions: List[Dict[str, Any]] = []
        for account in list(snapshot.get("accounts") or []):
            if not isinstance(account, dict):
                continue
            for position in list(account.get("positions") or []):
                if isinstance(position, dict):
                    positions.append(position)
        return positions

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
            raise PortfolioConflictError(
                f"Duplicate trade_uid for account_id={account_id}: {trade_uid}",
                reason_code="duplicate_trade_uid",
                identifier_name="tradeUid",
                identifier_value=trade_uid,
            )
        if dedup_hash and self._has_trade_dedup_hash(account_id=account_id, dedup_hash=dedup_hash, session=session):
            raise PortfolioConflictError(
                f"Duplicate dedup_hash for account_id={account_id}: {dedup_hash}",
                reason_code="duplicate_trade_dedup_hash",
            )

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
        realized_price_pnl_base = 0.0
        income_pnl_base = 0.0
        deposits_base = 0.0
        withdrawals_base = 0.0
        external_cash_flows: List[Tuple[date, float]] = []
        realized_pnl_by_symbol: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        fx_stale = False
        fx_currencies_used: Set[str] = set()
        valuation_coverage = self._new_conversion_coverage()
        performance_coverage = self._new_conversion_coverage()

        fifo_lots: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
        avg_state: Dict[Tuple[str, str, str], _AvgState] = defaultdict(_AvgState)

        for event_type, event_date, _, event in events:
            if event_type == "cash":
                currency = self._normalize_currency(event.currency)
                amount = float(event.amount or 0.0)
                converted_flow, stale_flow, flow_source = self._convert_amount(
                    amount=amount,
                    from_currency=currency,
                    to_currency=account.base_currency,
                    as_of_date=event_date,
                )
                self._record_conversion_coverage(
                    performance_coverage,
                    component=f"cash_flow:{event.id}",
                    amount=amount,
                    from_currency=currency,
                    to_currency=account.base_currency,
                    source=flow_source,
                )
                fx_stale = fx_stale or stale_flow
                if event.direction == "in":
                    cash_balances[currency] += amount
                    deposits_base += converted_flow
                    external_cash_flows.append((event_date, converted_flow))
                elif event.direction == "out":
                    cash_balances[currency] -= amount
                    withdrawals_base += converted_flow
                    external_cash_flows.append((event_date, -converted_flow))
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
                                "unit_price_cost": price,
                                "source_trade_id": event.id,
                            }
                        )
                    elif cost_method == "avg":
                        state = avg_state[key]
                        state.quantity += qty
                        state.total_cost += (gross + fee + tax)
                        state.price_cost += gross
                    elif cost_method == "futu_diluted":
                        state = avg_state[key]
                        state.quantity += qty
                        state.total_cost += gross
                        state.price_cost += gross
                    elif cost_method == "ths_pnl":
                        state = avg_state[key]
                        state.quantity += qty
                        state.total_cost += (gross + fee + tax)
                        state.price_cost += gross
                elif side == "sell":
                    cash_balances[key[2]] += (gross - fee - tax)
                    proceeds_net = gross - fee - tax
                    if cost_method == "fifo":
                        cost_basis, price_cost_basis = self._consume_fifo_lots(
                            fifo_lots[key],
                            qty,
                            key[0],
                            event_date,
                        )
                    elif cost_method == "avg":
                        cost_basis, price_cost_basis = self._consume_avg_position(
                            avg_state[key],
                            qty,
                            key[0],
                            event_date,
                        )
                    else:
                        state = avg_state[key]
                        cost_basis, price_cost_basis = self._consume_avg_position(
                            state,
                            qty,
                            key[0],
                            event_date,
                        )
                        if state.quantity > EPS and cost_method == "futu_diluted":
                            state.total_cost -= gross - cost_basis
                        elif state.quantity > EPS and cost_method == "ths_pnl":
                            state.total_cost -= proceeds_net - cost_basis
                    realized_price_local = gross - price_cost_basis
                    realized_price_base, stale_price, price_source = self._convert_amount(
                        amount=realized_price_local,
                        from_currency=key[2],
                        to_currency=account.base_currency,
                        as_of_date=event_date,
                    )
                    self._record_conversion_coverage(
                        performance_coverage,
                        component=f"realized_price_pnl:{event.id}",
                        amount=realized_price_local,
                        from_currency=key[2],
                        to_currency=account.base_currency,
                        source=price_source,
                    )
                    realized_price_pnl_base += realized_price_base
                    realized_local = proceeds_net - cost_basis
                    realized_base, stale_realized, realized_source = self._convert_amount(
                        amount=realized_local,
                        from_currency=key[2],
                        to_currency=account.base_currency,
                        as_of_date=event_date,
                    )
                    if self._normalize_currency(key[2]) != self._normalize_currency(account.base_currency):
                        fx_currencies_used.add(self._normalize_currency(key[2]))
                    realized_pnl_base += realized_base
                    realized_bucket = realized_pnl_by_symbol.setdefault(
                        key,
                        {
                            "symbol": key[0],
                            "market": key[1],
                            "currency": key[2],
                            "amount_native": 0.0,
                            "amount_base": 0.0,
                            "quantity_sold": 0.0,
                            "fx_status": FX_STATUS_LIVE,
                        },
                    )
                    realized_bucket["amount_native"] += realized_local
                    realized_bucket["amount_base"] += realized_base
                    realized_bucket["quantity_sold"] += qty
                    realized_bucket["fx_status"] = self._combine_fx_statuses(
                        realized_bucket["fx_status"],
                        self._fx_status(stale_realized, realized_source),
                    )
                    fx_stale = fx_stale or stale_realized
                    fx_stale = fx_stale or stale_price
                else:
                    raise ValueError(f"Unsupported trade side: {event.side}")

                fee_base, stale_fee, fee_source = self._convert_amount(
                    amount=fee,
                    from_currency=key[2],
                    to_currency=account.base_currency,
                    as_of_date=event_date,
                )
                tax_base, stale_tax, tax_source = self._convert_amount(
                    amount=tax,
                    from_currency=key[2],
                    to_currency=account.base_currency,
                    as_of_date=event_date,
                )
                if self._normalize_currency(key[2]) != self._normalize_currency(account.base_currency):
                    fx_currencies_used.add(self._normalize_currency(key[2]))
                fees_total_base += fee_base
                taxes_total_base += tax_base
                self._record_conversion_coverage(
                    performance_coverage,
                    component=f"fee:{event.id}",
                    amount=fee,
                    from_currency=key[2],
                    to_currency=account.base_currency,
                    source=fee_source,
                )
                self._record_conversion_coverage(
                    performance_coverage,
                    component=f"tax:{event.id}",
                    amount=tax,
                    from_currency=key[2],
                    to_currency=account.base_currency,
                    source=tax_source,
                )
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
                        income_native = qty_held * per_share
                        cash_balances[key[2]] += income_native
                        income_base, stale_income, income_source = self._convert_amount(
                            amount=income_native,
                            from_currency=key[2],
                            to_currency=account.base_currency,
                            as_of_date=event_date,
                        )
                        self._record_conversion_coverage(
                            performance_coverage,
                            component=f"income:{event.id}",
                            amount=income_native,
                            from_currency=key[2],
                            to_currency=account.base_currency,
                            source=income_source,
                        )
                        income_pnl_base += income_base
                        fx_stale = fx_stale or stale_income
                        if cost_method in {"futu_diluted", "ths_pnl"}:
                            avg_state[key].total_cost -= income_native
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
                            lot["unit_price_cost"] /= split_ratio
                    else:
                        state = avg_state[key]
                        state.quantity *= split_ratio
                else:
                    raise ValueError(f"Unsupported corporate action type: {event.action_type}")

        (
            position_rows,
            lot_rows,
            market_value_base,
            total_cost_base,
            unrealized_price_pnl_base,
            stale_pos,
            position_valuation_coverage,
            position_performance_coverage,
        ) = self._build_positions(
            account=account,
            as_of_date=as_of_date,
            cost_method=cost_method,
            fifo_lots=fifo_lots,
            avg_state=avg_state,
            fx_currencies_used=fx_currencies_used,
        )
        fx_stale = fx_stale or stale_pos
        self._merge_conversion_coverage(valuation_coverage, position_valuation_coverage)
        self._merge_conversion_coverage(performance_coverage, position_performance_coverage)

        total_cash_base = 0.0
        for currency, amount in cash_balances.items():
            converted, stale, source = self._convert_amount(
                amount=amount,
                from_currency=currency,
                to_currency=account.base_currency,
                as_of_date=as_of_date,
            )
            self._record_conversion_coverage(
                valuation_coverage,
                component=f"cash:{currency}",
                amount=amount,
                from_currency=currency,
                to_currency=account.base_currency,
                source=source,
            )
            if self._normalize_currency(currency) != self._normalize_currency(account.base_currency):
                fx_currencies_used.add(self._normalize_currency(currency))
            total_cash_base += converted
            fx_stale = fx_stale or stale

        unrealized_pnl_base = market_value_base - total_cost_base
        total_equity_base = total_cash_base + market_value_base
        valuation = self._conversion_coverage_payload(valuation_coverage)
        performance = self._build_account_performance(
            as_of_date=as_of_date,
            currency=account.base_currency,
            total_equity=total_equity_base,
            realized_price_pnl=realized_price_pnl_base,
            unrealized_price_pnl=unrealized_price_pnl_base,
            income_pnl=income_pnl_base,
            fees=fees_total_base,
            taxes=taxes_total_base,
            deposits=deposits_base,
            withdrawals=withdrawals_base,
            external_cash_flows=external_cash_flows,
            valuation=valuation,
            conversion_coverage=performance_coverage,
        )

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
            "valuation": valuation,
            "performance": performance,
            "positions": position_rows,
            "realized_pnl_by_symbol": self._realized_symbol_payload(realized_pnl_by_symbol),
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
        snapshot_date = str(sync_state.get("snapshot_date") or "").strip() or as_of_date.isoformat()
        positions = []
        for item in list(sync_state.get("positions") or []):
            positions.append(
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
                    **self._build_position_price_metadata(
                        price_source=PORTFOLIO_PRICE_SOURCE_BROKER_SYNC_SNAPSHOT,
                        price_as_of=snapshot_date,
                        is_price_fallback=False,
                        price_fallback_reason=None,
                        valuation_confidence=PORTFOLIO_PRICE_CONFIDENCE_SYNC,
                    ),
                }
            )
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
        valuation_components = [f"broker_position:{item['symbol']}" for item in positions]
        if abs(float(payload["total_cash"])) > EPS:
            valuation_components.append("broker_cash")
        payload["valuation"] = {
            "state": "available",
            "value_semantics": "covered_subtotal",
            "covered_component_count": len(valuation_components),
            "unavailable_component_count": 0,
            "covered_components": valuation_components,
            "unavailable_components": [],
            "missing_fx_pairs": [],
        }
        payload["performance"] = self._unavailable_performance(
            currency=str(payload["base_currency"]),
            valuation=payload["valuation"],
            reason="broker_sync_performance_components_unavailable",
        )
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

        positions_cache = [self._cached_position_row_to_dict(row) for row in cached["positions"]]
        decoded_payload = decode_persisted_json(
            getattr(snapshot_row, "payload", None),
            expected_type=dict,
            validator=lambda payload: self._cached_snapshot_payload_is_compatible(
                payload,
                account=account,
                snapshot_row=snapshot_row,
                as_of_date=as_of_date,
                cost_method=cost_method,
            ),
        )
        if not decoded_payload.is_valid or decoded_payload.state is PersistedJsonState.VALID_EMPTY:
            return None
        payload_raw = dict(decoded_payload.value)
        if positions_cache and self._snapshot_payload_missing_price_disclosure(payload_raw):
            return None
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
    ) -> Tuple[
        List[Dict[str, Any]],
        List[Dict[str, Any]],
        float,
        float,
        float,
        bool,
        Dict[str, Any],
        Dict[str, Any],
    ]:
        position_rows: List[Dict[str, Any]] = []
        lot_rows: List[Dict[str, Any]] = []
        market_value_base = 0.0
        total_cost_base = 0.0
        unrealized_price_pnl_base = 0.0
        fx_stale = False
        valuation_coverage = self._new_conversion_coverage()
        performance_coverage = self._new_conversion_coverage()

        keys: Iterable[Tuple[str, str, str]]
        if cost_method == "fifo":
            keys = list(fifo_lots.keys())
        else:
            keys = list(avg_state.keys())
        latest_closes = self.repo.get_latest_closes_with_dates(
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
                price_cost = sum(
                    float(lot["remaining_quantity"]) * float(lot["unit_price_cost"])
                    for lot in active_lots
                )
                avg_cost = total_cost / qty
                lot_rows.extend(active_lots)
            else:
                state = avg_state[key]
                qty = float(state.quantity)
                total_cost = float(state.total_cost)
                price_cost = float(state.price_cost)
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
                        "unit_price_cost": price_cost / qty,
                        "source_trade_id": None,
                    }
                )

            latest_close = latest_closes.get(symbol)
            raw_last_price = latest_close[0] if latest_close is not None else None
            latest_close_date = latest_close[1] if latest_close is not None else None
            is_price_fallback = raw_last_price is None or raw_last_price <= 0
            last_price = avg_cost if is_price_fallback else float(raw_last_price)
            price_metadata = self._build_position_price_metadata(
                price_source=(
                    PORTFOLIO_PRICE_SOURCE_AVG_COST_FALLBACK
                    if is_price_fallback
                    else PORTFOLIO_PRICE_SOURCE_DAILY_CLOSE
                ),
                price_as_of=(
                    None
                    if is_price_fallback
                    else (latest_close_date or as_of_date).isoformat()
                ),
                is_price_fallback=is_price_fallback,
                price_fallback_reason=(
                    PORTFOLIO_PRICE_FALLBACK_REASON_CURRENT_QUOTE_UNAVAILABLE
                    if is_price_fallback
                    else None
                ),
                valuation_confidence=(
                    PORTFOLIO_PRICE_CONFIDENCE_FALLBACK
                    if is_price_fallback
                    else PORTFOLIO_PRICE_CONFIDENCE_LIVE
                ),
            )
            if (
                fx_currencies_used is not None
                and self._normalize_currency(currency) != self._normalize_currency(account.base_currency)
            ):
                fx_currencies_used.add(self._normalize_currency(currency))

            local_market_value = qty * float(last_price)
            market_base, stale_market, market_source = self._convert_amount(
                amount=local_market_value,
                from_currency=currency,
                to_currency=account.base_currency,
                as_of_date=as_of_date,
            )
            cost_base, stale_cost, cost_source = self._convert_amount(
                amount=total_cost,
                from_currency=currency,
                to_currency=account.base_currency,
                as_of_date=as_of_date,
            )
            unrealized_price_native = local_market_value - price_cost
            unrealized_price_base, stale_price, price_source = self._convert_amount(
                amount=unrealized_price_native,
                from_currency=currency,
                to_currency=account.base_currency,
                as_of_date=as_of_date,
            )
            self._record_conversion_coverage(
                valuation_coverage,
                component=f"position:{symbol}:{market}:{currency}",
                amount=local_market_value,
                from_currency=currency,
                to_currency=account.base_currency,
                source=market_source,
            )
            self._record_conversion_coverage(
                performance_coverage,
                component=f"unrealized_price_pnl:{symbol}:{market}:{currency}",
                amount=unrealized_price_native,
                from_currency=currency,
                to_currency=account.base_currency,
                source=price_source,
            )
            unrealized_base = market_base - cost_base
            unrealized_native = local_market_value - total_cost
            unrealized_pct = (unrealized_native / abs(total_cost)) * 100.0 if abs(total_cost) > EPS else None
            fx_stale = fx_stale or stale_market or stale_cost or stale_price
            display_fx_status = self._combine_fx_statuses(
                self._fx_status(stale_market, market_source),
                self._fx_status(stale_cost, cost_source),
            )

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
                    "cost_basis_native": round(total_cost, 8),
                    "price_cost_basis_native": round(price_cost, 8),
                    "market_value_native": round(local_market_value, 8),
                    "price_pnl_native": round(unrealized_price_native, 8),
                    "unrealized_pnl_native": round(unrealized_native, 8),
                    "unrealized_pnl_pct": round(unrealized_pct, 6) if unrealized_pct is not None else None,
                    "display_market_value": round(market_base, 8),
                    "display_unrealized_pnl": round(unrealized_base, 8),
                    "display_currency": account.base_currency,
                    "display_fx_status": display_fx_status,
                    **price_metadata,
                }
            )

            market_value_base += market_base
            total_cost_base += cost_base
            unrealized_price_pnl_base += unrealized_price_base

        return (
            position_rows,
            lot_rows,
            market_value_base,
            total_cost_base,
            unrealized_price_pnl_base,
            fx_stale,
            valuation_coverage,
            performance_coverage,
        )

    @staticmethod
    def _build_position_price_metadata(
        *,
        price_source: str,
        price_as_of: Optional[str],
        is_price_fallback: bool,
        price_fallback_reason: Optional[str],
        valuation_confidence: Optional[float],
    ) -> Dict[str, Any]:
        source_labels = {
            PORTFOLIO_PRICE_SOURCE_DAILY_CLOSE: "Daily close quote",
            PORTFOLIO_PRICE_SOURCE_BROKER_SYNC_SNAPSHOT: "Broker sync snapshot",
            PORTFOLIO_PRICE_SOURCE_AVG_COST_FALLBACK: "Average cost fallback",
        }
        confidence = None if valuation_confidence is None else round(float(valuation_confidence), 2)
        return {
            "price_source": price_source,
            "price_source_label": source_labels.get(price_source, price_source),
            "price_as_of": price_as_of,
            "is_price_fallback": bool(is_price_fallback),
            "price_fallback_reason": price_fallback_reason,
            "valuation_confidence": confidence,
        }

    @staticmethod
    def _snapshot_payload_missing_price_disclosure(payload: Dict[str, Any]) -> bool:
        positions = list((payload or {}).get("positions") or [])
        if not positions:
            return False
        required_fields = ("price_source", "price_source_label", "is_price_fallback")
        return any(
            not isinstance(position, dict) or any(field not in position for field in required_fields)
            for position in positions
        )

    @staticmethod
    def _consume_fifo_lots(
        lots: List[Dict[str, Any]],
        quantity: float,
        symbol: str,
        trade_date: Optional[date] = None,
    ) -> Tuple[float, float]:
        remaining = quantity
        cost_basis = 0.0
        price_cost_basis = 0.0
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
            price_cost_basis += take * float(head["unit_price_cost"])
            head["remaining_quantity"] = float(head["remaining_quantity"]) - take
            remaining -= take
            if head["remaining_quantity"] <= EPS:
                lots.pop(0)
        return cost_basis, price_cost_basis

    @staticmethod
    def _consume_avg_position(
        state: _AvgState,
        quantity: float,
        symbol: str,
        trade_date: Optional[date] = None,
    ) -> Tuple[float, float]:
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
        avg_price_cost = state.price_cost / state.quantity
        cost_basis = avg_cost * quantity
        price_cost_basis = avg_price_cost * quantity
        state.quantity -= quantity
        state.total_cost -= cost_basis
        state.price_cost -= price_cost_basis
        if state.quantity <= EPS:
            state.quantity = 0.0
            state.total_cost = 0.0
            state.price_cost = 0.0
        return cost_basis, price_cost_basis

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

    @staticmethod
    def _new_conversion_coverage() -> Dict[str, Any]:
        return {
            "covered_components": set(),
            "unavailable_components": set(),
            "missing_fx_pairs": set(),
            "unavailable_native_values": {},
        }

    @classmethod
    def _record_conversion_coverage(
        cls,
        coverage: Dict[str, Any],
        *,
        component: str,
        amount: float,
        from_currency: str,
        to_currency: str,
        source: str,
    ) -> None:
        if abs(float(amount)) <= EPS:
            return
        component_key = str(component)
        if source == "missing_rate":
            coverage["unavailable_components"].add(component_key)
            from_norm = cls._normalize_currency(from_currency)
            to_norm = cls._normalize_currency(to_currency)
            coverage["missing_fx_pairs"].add(f"{from_norm}/{to_norm}")
            coverage["unavailable_native_values"][component_key] = {
                "component": component_key,
                "amount": round(float(amount), 8),
                "currency": from_norm,
            }
            return
        coverage["covered_components"].add(component_key)

    @staticmethod
    def _merge_conversion_coverage(
        target: Dict[str, Any],
        source: Dict[str, Any],
    ) -> None:
        for key in ("covered_components", "unavailable_components", "missing_fx_pairs"):
            target[key].update(source.get(key) or set())
        target["unavailable_native_values"].update(source.get("unavailable_native_values") or {})

    @staticmethod
    def _merge_coverage_payload(
        target: Dict[str, Any],
        payload: Dict[str, Any],
        *,
        prefix: str,
    ) -> None:
        for key in ("covered_components", "unavailable_components"):
            for component in list(payload.get(key) or []):
                target[key].add(f"{prefix}:{component}")
        target["missing_fx_pairs"].update(str(item) for item in list(payload.get("missing_fx_pairs") or []))
        for item in list(payload.get("unavailable_native_values") or []):
            if not isinstance(item, dict) or not str(item.get("component") or ""):
                continue
            component = f"{prefix}:{item['component']}"
            target["unavailable_native_values"][component] = {
                **item,
                "component": component,
            }

    @staticmethod
    def _conversion_coverage_payload(coverage: Dict[str, Any]) -> Dict[str, Any]:
        covered = sorted(coverage.get("covered_components") or set())
        unavailable = sorted(coverage.get("unavailable_components") or set())
        native_values = sorted(
            list((coverage.get("unavailable_native_values") or {}).values()),
            key=lambda item: str(item.get("component") or ""),
        )
        if unavailable and covered:
            state = "partial"
        elif unavailable:
            state = "unavailable"
        else:
            state = "available"
        return {
            "state": state,
            "value_semantics": "covered_subtotal",
            "covered_component_count": len(covered),
            "unavailable_component_count": len(unavailable),
            "covered_components": covered,
            "unavailable_components": unavailable,
            "missing_fx_pairs": sorted(coverage.get("missing_fx_pairs") or set()),
            "unavailable_native_values": native_values,
        }

    @staticmethod
    def _modified_dietz_denominator(
        *,
        external_cash_flows: List[Tuple[date, float]],
        as_of_date: date,
    ) -> Optional[float]:
        if not external_cash_flows:
            return None
        first_date = min(flow_date for flow_date, _ in external_cash_flows)
        span_days = (as_of_date - first_date).days
        denominator = 0.0
        for flow_date, signed_amount in external_cash_flows:
            if span_days <= 0:
                weight = 1.0
            else:
                weight = max(0.0, min(1.0, (as_of_date - flow_date).days / span_days))
            denominator += float(signed_amount) * weight
        return denominator if denominator > EPS else None

    def _build_account_performance(
        self,
        *,
        as_of_date: date,
        currency: str,
        total_equity: float,
        realized_price_pnl: float,
        unrealized_price_pnl: float,
        income_pnl: float,
        fees: float,
        taxes: float,
        deposits: float,
        withdrawals: float,
        external_cash_flows: List[Tuple[date, float]],
        valuation: Dict[str, Any],
        conversion_coverage: Dict[str, Any],
    ) -> Dict[str, Any]:
        component_coverage = self._conversion_coverage_payload(conversion_coverage)
        valuation_state = str(valuation.get("state") or "unavailable")
        component_state = str(component_coverage.get("state") or "unavailable")
        if valuation_state == "unavailable" or component_state == "unavailable":
            calculation_state = "unavailable"
        elif valuation_state == "partial" or component_state == "partial":
            calculation_state = "partial"
        else:
            calculation_state = "available"

        net_cash_flow = deposits - withdrawals
        denominator = None
        net_pnl = None
        gross_pnl = None
        price_pnl = None
        fx_pnl = None
        if calculation_state == "available":
            net_pnl = total_equity - net_cash_flow
            gross_pnl = net_pnl + fees + taxes
            price_pnl = realized_price_pnl + unrealized_price_pnl
            fx_pnl = gross_pnl - price_pnl - income_pnl
            denominator = self._modified_dietz_denominator(
                external_cash_flows=external_cash_flows,
                as_of_date=as_of_date,
            )

        return_status = "available" if denominator is not None and net_pnl is not None else "unavailable"
        return_percent = (net_pnl / denominator) * 100.0 if return_status == "available" else None
        if calculation_state != "available":
            return_reason = "partial_or_unavailable_valuation"
        elif denominator is None:
            return_reason = "non_positive_denominator"
        else:
            return_reason = None

        def rounded(value: Optional[float]) -> Optional[float]:
            return round(float(value), 6) if value is not None else None

        return {
            "contract_version": PORTFOLIO_PERFORMANCE_CONTRACT_VERSION,
            "calculation_state": calculation_state,
            "currency": self._normalize_currency(currency),
            "price_basis": "snapshot_valuation_price_not_executable",
            "cash_flows": {
                "deposits": rounded(deposits) if calculation_state == "available" else None,
                "withdrawals": rounded(withdrawals) if calculation_state == "available" else None,
                "net": rounded(net_cash_flow) if calculation_state == "available" else None,
                "performance_treatment": "excluded_from_investment_pnl",
            },
            "pnl": {
                "price": rounded(price_pnl),
                "income": rounded(income_pnl) if calculation_state == "available" else None,
                "fx": rounded(fx_pnl),
                "fees": rounded(fees) if calculation_state == "available" else None,
                "taxes": rounded(taxes) if calculation_state == "available" else None,
                "gross": rounded(gross_pnl),
                "net": rounded(net_pnl),
            },
            "return": {
                "status": return_status,
                "method": "modified_dietz",
                "numerator": rounded(net_pnl),
                "denominator": rounded(denominator),
                "denominator_semantics": "time_weighted_external_cash_flows",
                "cash_flow_timing": "end_of_day",
                "percent": rounded(return_percent),
                "reason": return_reason,
            },
            "valuation": dict(valuation),
            "component_coverage": component_coverage,
        }

    def _unavailable_performance(
        self,
        *,
        currency: str,
        valuation: Dict[str, Any],
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "contract_version": PORTFOLIO_PERFORMANCE_CONTRACT_VERSION,
            "calculation_state": "unavailable",
            "currency": self._normalize_currency(currency),
            "price_basis": "snapshot_valuation_price_not_executable",
            "cash_flows": {
                "deposits": None,
                "withdrawals": None,
                "net": None,
                "performance_treatment": "excluded_from_investment_pnl",
            },
            "pnl": {
                "price": None,
                "income": None,
                "fx": None,
                "fees": None,
                "taxes": None,
                "gross": None,
                "net": None,
            },
            "return": {
                "status": "unavailable",
                "method": "modified_dietz",
                "numerator": None,
                "denominator": None,
                "denominator_semantics": "time_weighted_external_cash_flows",
                "cash_flow_timing": "end_of_day",
                "percent": None,
                "reason": reason,
            },
            "valuation": dict(valuation),
            "component_coverage": {
                "state": "unavailable",
                "value_semantics": "covered_subtotal",
                "covered_component_count": 0,
                "unavailable_component_count": 1,
                "covered_components": [],
                "unavailable_components": [reason],
                "missing_fx_pairs": [],
                "unavailable_native_values": [],
            },
        }

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

        return 0.0, True, "missing_rate"

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
                    sanitized = sanitize_metadata(parsed)
                    sync_metadata = sanitized if isinstance(sanitized, dict) else {}
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
    def _parse_snapshot_payload(payload_raw: Optional[str]) -> Optional[Dict[str, Any]]:
        result = decode_persisted_json(payload_raw, expected_type=dict)
        if not result.is_valid or result.state is PersistedJsonState.VALID_EMPTY:
            return None
        return dict(result.value)

    @staticmethod
    def _cached_snapshot_payload_is_compatible(
        payload: Dict[str, Any],
        *,
        account: Any,
        snapshot_row: Any,
        as_of_date: date,
        cost_method: str,
    ) -> bool:
        required_numeric_fields = (
            "total_cash",
            "total_market_value",
            "total_equity",
            "realized_pnl",
            "unrealized_pnl",
            "fee_total",
            "tax_total",
        )
        if any(field not in payload or isinstance(payload.get(field), bool) for field in required_numeric_fields):
            return False
        try:
            for field in required_numeric_fields:
                float(payload[field])
        except (TypeError, ValueError):
            return False
        if any(
            abs(float(payload[field]) - float(getattr(snapshot_row, field) or 0.0)) > 1e-6
            for field in required_numeric_fields
        ):
            return False
        if not isinstance(payload.get("fx_stale"), bool) or payload["fx_stale"] is not bool(snapshot_row.fx_stale):
            return False
        positions = payload.get("positions")
        if not isinstance(positions, list) or not all(isinstance(item, dict) for item in positions):
            return False
        performance = payload.get("performance")
        if (
            not isinstance(performance, dict)
            or performance.get("contract_version") != PORTFOLIO_PERFORMANCE_CONTRACT_VERSION
        ):
            return False
        valuation = payload.get("valuation")
        if not isinstance(valuation, dict) or valuation.get("state") not in {"available", "partial", "unavailable"}:
            return False
        return (
            payload.get("account_id") == int(account.id)
            and str(payload.get("as_of") or "") == as_of_date.isoformat()
            and str(payload.get("cost_method") or "") == cost_method
            and str(payload.get("base_currency") or "")
            == str(snapshot_row.base_currency or account.base_currency)
        )

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
        resolved_payload = payload
        if resolved_payload is None:
            resolved_payload = self._parse_snapshot_payload(getattr(snapshot_row, "payload", None))
        if resolved_payload is None:
            raise ValueError("cached portfolio snapshot payload is unavailable")
        public_payload = dict(resolved_payload)
        public_payload.pop("_cache_meta", None)
        payload_positions = list(public_payload.get("positions") or [])
        resolved_positions = payload_positions if payload_positions else positions
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
                "positions": resolved_positions,
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

    def _build_portfolio_performance(
        self,
        *,
        snapshot: Dict[str, Any],
        aggregate_currency: str,
        as_of_date: date,
    ) -> Dict[str, Any]:
        coverage = self._new_conversion_coverage()
        totals = {
            "deposits": 0.0,
            "withdrawals": 0.0,
            "price": 0.0,
            "income": 0.0,
            "fx": 0.0,
            "fees": 0.0,
            "taxes": 0.0,
            "gross": 0.0,
            "net": 0.0,
            "denominator": 0.0,
        }
        denominator_count = 0
        unavailable_accounts = 0
        covered_accounts = 0
        display_currency = self._normalize_currency(aggregate_currency)

        for account in list(snapshot.get("accounts") or []):
            account_id = int(account.get("account_id") or 0)
            performance = account.get("performance") if isinstance(account.get("performance"), dict) else {}
            if str(performance.get("calculation_state") or "unavailable") != "available":
                unavailable_accounts += 1
                coverage["unavailable_components"].add(f"account:{account_id}:performance")
                continue
            covered_accounts += 1
            account_currency = self._normalize_currency(performance.get("currency") or account.get("base_currency"))
            values = {
                "deposits": dict(performance.get("cash_flows") or {}).get("deposits"),
                "withdrawals": dict(performance.get("cash_flows") or {}).get("withdrawals"),
                "price": dict(performance.get("pnl") or {}).get("price"),
                "income": dict(performance.get("pnl") or {}).get("income"),
                "fx": dict(performance.get("pnl") or {}).get("fx"),
                "fees": dict(performance.get("pnl") or {}).get("fees"),
                "taxes": dict(performance.get("pnl") or {}).get("taxes"),
                "gross": dict(performance.get("pnl") or {}).get("gross"),
                "net": dict(performance.get("pnl") or {}).get("net"),
            }
            for component, raw_value in values.items():
                amount = float(raw_value or 0.0)
                converted, _stale, source = self._convert_amount(
                    amount=amount,
                    from_currency=account_currency,
                    to_currency=display_currency,
                    as_of_date=as_of_date,
                )
                self._record_conversion_coverage(
                    coverage,
                    component=f"account:{account_id}:{component}",
                    amount=amount,
                    from_currency=account_currency,
                    to_currency=display_currency,
                    source=source,
                )
                totals[component] += converted

            denominator = dict(performance.get("return") or {}).get("denominator")
            if denominator is not None:
                converted, _stale, source = self._convert_amount(
                    amount=float(denominator),
                    from_currency=account_currency,
                    to_currency=display_currency,
                    as_of_date=as_of_date,
                )
                self._record_conversion_coverage(
                    coverage,
                    component=f"account:{account_id}:return_denominator",
                    amount=float(denominator),
                    from_currency=account_currency,
                    to_currency=display_currency,
                    source=source,
                )
                totals["denominator"] += converted
                denominator_count += 1

        component_coverage = self._conversion_coverage_payload(coverage)
        valuation = dict(snapshot.get("valuation") or {})
        if unavailable_accounts and covered_accounts:
            calculation_state = "partial"
        elif unavailable_accounts or not list(snapshot.get("accounts") or []):
            calculation_state = "unavailable"
        elif str(component_coverage.get("state")) != "available":
            calculation_state = str(component_coverage.get("state"))
        elif str(valuation.get("state") or "unavailable") != "available":
            calculation_state = str(valuation.get("state") or "unavailable")
        else:
            calculation_state = "available"

        denominator = totals["denominator"] if denominator_count > 0 and totals["denominator"] > EPS else None
        return_available = calculation_state == "available" and denominator is not None
        return_percent = (totals["net"] / denominator) * 100.0 if return_available else None
        if calculation_state != "available":
            return_reason = "partial_or_unavailable_valuation"
        elif denominator is None:
            return_reason = "non_positive_denominator"
        else:
            return_reason = None

        def rounded(value: Optional[float]) -> Optional[float]:
            return round(float(value), 6) if value is not None else None

        values_available = calculation_state == "available"
        return {
            "contract_version": PORTFOLIO_PERFORMANCE_CONTRACT_VERSION,
            "calculation_state": calculation_state,
            "currency": display_currency,
            "price_basis": "snapshot_valuation_price_not_executable",
            "cash_flows": {
                "deposits": rounded(totals["deposits"]) if values_available else None,
                "withdrawals": rounded(totals["withdrawals"]) if values_available else None,
                "net": rounded(totals["deposits"] - totals["withdrawals"]) if values_available else None,
                "performance_treatment": "excluded_from_investment_pnl",
            },
            "pnl": {
                key: rounded(totals[key]) if values_available else None
                for key in ("price", "income", "fx", "fees", "taxes", "gross", "net")
            },
            "return": {
                "status": "available" if return_available else "unavailable",
                "method": "modified_dietz",
                "numerator": rounded(totals["net"]) if values_available else None,
                "denominator": rounded(denominator),
                "denominator_semantics": "time_weighted_external_cash_flows",
                "cash_flow_timing": "end_of_day",
                "percent": rounded(return_percent),
                "reason": return_reason,
            },
            "valuation": valuation,
            "component_coverage": component_coverage,
        }

    def _build_portfolio_attribution(
        self,
        *,
        snapshot: Dict[str, Any],
        as_of_date: date,
    ) -> Dict[str, Any]:
        from src.services.portfolio_risk_service import PortfolioRiskService

        risk_service = PortfolioRiskService(repo=self.repo, portfolio_service=self)
        return {
            "performance": dict(snapshot.get("performance") or {}),
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

    def _build_snapshot_analytics(
        self,
        *,
        snapshot: Dict[str, Any],
        account_rows: Iterable[Any],
        aggregate_currency: str,
        as_of_date: date,
    ) -> Dict[str, Any]:
        account_lookup = {int(account.id): account for account in account_rows}
        display_currency = self._normalize_currency(aggregate_currency)
        total_market_value = float(snapshot.get("total_market_value") or 0.0)
        total_cash = float(snapshot.get("total_cash") or 0.0)
        realized_amount = float(snapshot.get("realized_pnl") or 0.0)
        unrealized_amount = float(snapshot.get("unrealized_pnl") or 0.0)
        performance = snapshot.get("performance") if isinstance(snapshot.get("performance"), dict) else {}
        performance_pnl = performance.get("pnl") if isinstance(performance.get("pnl"), dict) else {}
        performance_return = performance.get("return") if isinstance(performance.get("return"), dict) else {}
        total_pnl = float(performance_pnl.get("net") or 0.0)
        cost_basis = total_market_value - unrealized_amount
        pnl_percent_raw = performance_return.get("percent")
        pnl_percent = float(pnl_percent_raw) if pnl_percent_raw is not None else None
        if str(performance.get("calculation_state") or "unavailable") != "available":
            fx_status = FX_STATUS_UNAVAILABLE
        else:
            fx_status = FX_STATUS_STALE if snapshot.get("fx_stale") else FX_STATUS_LIVE

        by_account: List[Dict[str, Any]] = []
        by_currency: Dict[str, Dict[str, Any]] = {}
        by_market: Dict[str, Dict[str, Any]] = {}
        by_symbol: Dict[str, Dict[str, Any]] = {}
        any_fx_unavailable = False

        for account_snapshot in list(snapshot.get("accounts") or []):
            account_id = int(account_snapshot.get("account_id") or 0)
            account = account_lookup.get(account_id)
            base_currency = self._normalize_currency(
                account_snapshot.get("base_currency") or getattr(account, "base_currency", display_currency)
            )
            account_market_value, account_stale, account_source = self._convert_amount(
                amount=float(account_snapshot.get("total_market_value") or 0.0),
                from_currency=base_currency,
                to_currency=display_currency,
                as_of_date=as_of_date,
            )
            account_fx_status = self._fx_status(account_stale, account_source)
            any_fx_unavailable = any_fx_unavailable or account_fx_status == FX_STATUS_UNAVAILABLE
            by_account.append(
                self._exposure_row(
                    key=str(account_id),
                    label=str(account_snapshot.get("account_name") or account_id),
                    market_value=account_market_value,
                    total_market_value=total_market_value,
                    display_currency=display_currency,
                    fx_status=account_fx_status,
                    native_value=float(account_snapshot.get("total_market_value") or 0.0),
                    native_currency=base_currency,
                    account_id=account_id,
                    account_name=account_snapshot.get("account_name"),
                    base_currency=base_currency,
                    holding_count=len(account_snapshot.get("positions") or []),
                )
            )

            for position in list(account_snapshot.get("positions") or []):
                position = self._ensure_position_analytics_fields(
                    account_payload={"positions": [position]},
                    display_currency=base_currency,
                )["positions"][0]
                symbol = str(position.get("symbol") or "").strip().upper()
                market = self._normalize_snapshot_position_market(
                    position.get("market"),
                    fallback_market=account_snapshot.get("market"),
                ) or "unknown"
                native_currency = self._normalize_currency(position.get("currency") or base_currency)
                native_value = float(position.get("market_value_native") or 0.0)
                display_value, display_stale, display_source = self._convert_amount(
                    amount=native_value,
                    from_currency=native_currency,
                    to_currency=display_currency,
                    as_of_date=as_of_date,
                )
                position_fx_status = self._fx_status(display_stale, display_source)
                any_fx_unavailable = any_fx_unavailable or position_fx_status == FX_STATUS_UNAVAILABLE

                currency_bucket = by_currency.setdefault(
                    native_currency,
                    {
                        "key": native_currency,
                        "label": native_currency,
                        "currency": native_currency,
                        "native_currency": native_currency,
                        "native_value": 0.0,
                        "display_value": 0.0,
                        "fx_status": FX_STATUS_LIVE,
                        "holding_count": 0,
                    },
                )
                currency_bucket["native_value"] += native_value
                currency_bucket["display_value"] += display_value
                currency_bucket["holding_count"] += 1
                currency_bucket["fx_status"] = self._combine_fx_statuses(currency_bucket["fx_status"], position_fx_status)

                market_bucket = by_market.setdefault(
                    market,
                    {
                        "key": market,
                        "label": market.upper(),
                        "market": market,
                        "display_value": 0.0,
                        "fx_status": FX_STATUS_LIVE,
                        "holding_count": 0,
                    },
                )
                market_bucket["display_value"] += display_value
                market_bucket["holding_count"] += 1
                market_bucket["fx_status"] = self._combine_fx_statuses(market_bucket["fx_status"], position_fx_status)

                symbol_bucket = by_symbol.setdefault(
                    symbol,
                    {
                        "key": symbol,
                        "label": symbol,
                        "symbol": symbol,
                        "market": market,
                        "currency": native_currency,
                        "display_value": 0.0,
                        "fx_status": FX_STATUS_LIVE,
                        "unrealized_pnl": 0.0,
                        "unrealized_pnl_pct": position.get("unrealized_pnl_pct"),
                        "holding_count": 0,
                    },
                )
                symbol_bucket["display_value"] += display_value
                symbol_bucket["unrealized_pnl"] += float(position.get("display_unrealized_pnl") or 0.0)
                symbol_bucket["holding_count"] += 1
                symbol_bucket["fx_status"] = self._combine_fx_statuses(symbol_bucket["fx_status"], position_fx_status)

        by_account.sort(key=lambda item: (-float(item["market_value"]), str(item["label"])))
        currency_rows = [
            self._exposure_row(
                key=item["key"],
                label=item["label"],
                market_value=float(item["display_value"]),
                total_market_value=total_market_value,
                display_currency=display_currency,
                fx_status=item["fx_status"],
                native_value=round(float(item["native_value"]), 6),
                native_currency=item["native_currency"],
                currency=item["currency"],
                holding_count=int(item["holding_count"]),
            )
            for item in by_currency.values()
        ]
        market_rows = [
            self._exposure_row(
                key=item["key"],
                label=item["label"],
                market_value=float(item["display_value"]),
                total_market_value=total_market_value,
                display_currency=display_currency,
                fx_status=item["fx_status"],
                market=item["market"],
                holding_count=int(item["holding_count"]),
            )
            for item in by_market.values()
        ]
        symbol_rows = [
            self._exposure_row(
                key=item["key"],
                label=item["label"],
                market_value=float(item["display_value"]),
                total_market_value=total_market_value,
                display_currency=display_currency,
                fx_status=item["fx_status"],
                symbol=item["symbol"],
                market=item["market"],
                currency=item["currency"],
                unrealized_pnl=round(float(item["unrealized_pnl"]), 6),
                unrealized_pnl_pct=item.get("unrealized_pnl_pct"),
                holding_count=int(item["holding_count"]),
            )
            for item in by_symbol.values()
        ]
        for rows in (currency_rows, market_rows, symbol_rows):
            rows.sort(key=lambda item: (-float(item["market_value"]), str(item["label"])))

        largest_position = symbol_rows[0] if symbol_rows else None
        largest_currency = currency_rows[0] if currency_rows else None
        largest_market = market_rows[0] if market_rows else None
        warnings: List[str] = []
        if not symbol_rows:
            warnings.append("no_holdings")
        if largest_position and float(largest_position.get("percent") or 0.0) > 30.0:
            warnings.append("single_position_gt_30")
        if largest_currency and float(largest_currency.get("percent") or 0.0) > 80.0:
            warnings.append("single_currency_gt_80")
        if largest_market and float(largest_market.get("percent") or 0.0) > 80.0:
            warnings.append("single_market_gt_80")
        if any_fx_unavailable:
            warnings.append("fx_conversion_unavailable")

        return {
            "pnl": {
                "display_currency": display_currency,
                "realized": self._pnl_metric(
                    amount=realized_amount,
                    percent=None,
                    currency=display_currency,
                    fx_status=fx_status,
                ),
                "unrealized": self._pnl_metric(
                    amount=unrealized_amount,
                    percent=(unrealized_amount / abs(cost_basis)) * 100.0 if abs(cost_basis) > EPS else None,
                    currency=display_currency,
                    fx_status=FX_STATUS_UNAVAILABLE if any_fx_unavailable else fx_status,
                ),
                "total": self._pnl_metric(
                    amount=total_pnl,
                    percent=pnl_percent,
                    currency=display_currency,
                    fx_status=FX_STATUS_UNAVAILABLE if any_fx_unavailable else fx_status,
                ),
            },
            "exposure": {
                "by_account": by_account,
                "by_currency": currency_rows,
                "by_market": market_rows,
                "by_symbol": symbol_rows[:10],
                "by_sector": [],
                "sector_status": "unavailable",
            },
            "risk": {
                "largest_position": largest_position,
                "largest_currency": largest_currency,
                "largest_market": largest_market,
                "holding_count": len(symbol_rows),
                "account_count": int(snapshot.get("account_count") or 0),
                "cash_percent": round((total_cash / float(snapshot.get("total_equity") or 0.0)) * 100.0, 4)
                if abs(float(snapshot.get("total_equity") or 0.0)) > EPS
                else None,
                "fx_unavailable": any_fx_unavailable,
                "warnings": warnings,
            },
        }

    def _ensure_position_analytics_fields(
        self,
        *,
        account_payload: Dict[str, Any],
        display_currency: str,
    ) -> Dict[str, Any]:
        payload = dict(account_payload)
        positions = []
        for raw_position in list(payload.get("positions") or []):
            position = dict(raw_position)
            currency = self._normalize_currency(position.get("currency") or display_currency)
            total_cost = float(position.get("total_cost") or 0.0)
            market_value = float(position.get("market_value_native", position.get("market_value_base") or 0.0) or 0.0)
            unrealized = float(
                position.get(
                    "unrealized_pnl_native",
                    position.get("unrealized_pnl_base") or (market_value - total_cost),
                )
                or 0.0
            )
            position.setdefault("cost_basis_native", round(total_cost, 8))
            position.setdefault("market_value_native", round(market_value, 8))
            position.setdefault("unrealized_pnl_native", round(unrealized, 8))
            if position.get("unrealized_pnl_pct") is None:
                position["unrealized_pnl_pct"] = round((unrealized / abs(total_cost)) * 100.0, 6) if abs(total_cost) > EPS else None
            position.setdefault("display_market_value", position.get("market_value_base", market_value))
            position.setdefault("display_unrealized_pnl", position.get("unrealized_pnl_base", unrealized))
            position.setdefault("display_currency", display_currency)
            position.setdefault(
                "display_fx_status",
                FX_STATUS_LIVE if currency == self._normalize_currency(display_currency) else FX_STATUS_STALE,
            )
            positions.append(position)
        payload["positions"] = positions
        return payload

    @staticmethod
    def _pnl_metric(
        *,
        amount: float,
        percent: Optional[float],
        currency: str,
        fx_status: str,
    ) -> Dict[str, Any]:
        return {
            "amount": round(float(amount), 6),
            "amount_display": f"{currency} {float(amount):,.2f}",
            "percent": round(float(percent), 6) if percent is not None else None,
            "currency": currency,
            "fx_status": fx_status,
        }

    @staticmethod
    def _exposure_row(
        *,
        key: str,
        label: str,
        market_value: float,
        total_market_value: float,
        display_currency: str,
        fx_status: str,
        **extra: Any,
    ) -> Dict[str, Any]:
        row = {
            "key": key,
            "label": label,
            "market_value": round(float(market_value), 6),
            "display_value": round(float(market_value), 6),
            "display_currency": display_currency,
            "percent": round((float(market_value) / total_market_value) * 100.0, 4)
            if abs(total_market_value) > EPS
            else 0.0,
            "fx_status": fx_status,
        }
        row.update(extra)
        return row

    @staticmethod
    def _fx_status(stale: bool, source: str) -> str:
        if source == "missing_rate":
            return FX_STATUS_UNAVAILABLE
        if stale:
            return FX_STATUS_STALE
        return FX_STATUS_LIVE

    @staticmethod
    def _combine_fx_statuses(*statuses: str) -> str:
        if FX_STATUS_UNAVAILABLE in statuses:
            return FX_STATUS_UNAVAILABLE
        if FX_STATUS_STALE in statuses:
            return FX_STATUS_STALE
        return FX_STATUS_LIVE

    @staticmethod
    def _realized_symbol_payload(realized_pnl_by_symbol: Dict[Tuple[str, str, str], Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = []
        for item in realized_pnl_by_symbol.values():
            rows.append(
                {
                    "symbol": item["symbol"],
                    "market": item["market"],
                    "currency": item["currency"],
                    "amount_native": round(float(item["amount_native"]), 8),
                    "amount_base": round(float(item["amount_base"]), 8),
                    "quantity_sold": round(float(item["quantity_sold"]), 8),
                    "fx_status": item["fx_status"],
                }
            )
        rows.sort(key=lambda item: (-abs(float(item["amount_base"])), str(item["symbol"])))
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
