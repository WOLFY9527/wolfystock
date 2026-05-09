# -*- coding: utf-8 -*-
"""Read-only safe projections for admin portfolio visibility APIs."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import and_, desc, func, or_, select

from api.v1.schemas.admin_portfolio import (
    AdminBrokerSyncSummary,
    AdminHoldingListResponse,
    AdminHoldingItem,
    AdminLedgerCounts,
    AdminMoneyAmount,
    AdminPortfolioAccountDetailResponse,
    AdminPortfolioAccountItem,
    AdminPortfolioActivityItem,
    AdminPortfolioActivityResponse,
    AdminPortfolioBrokerConnectionItem,
    AdminPortfolioSummaryResponse,
    AdminPortfolioSyncState,
)
from src.repositories.auth_repo import AuthRepository
from src.storage import (
    DatabaseManager,
    PortfolioAccount,
    PortfolioBrokerConnection,
    PortfolioBrokerSyncPosition,
    PortfolioBrokerSyncState,
    PortfolioCashLedger,
    PortfolioCorporateAction,
    PortfolioDailySnapshot,
    PortfolioPosition,
    PortfolioTrade,
)


def _iso(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return None


def _float(value: Any) -> float:
    return float(value or 0.0)


def _hash_ref(value: Any, *, prefix: str = "sha256") -> str:
    digest = hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:16]}"


def _broker_account_handle(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    digest = hashlib.sha256(f"broker-account:{text}".encode("utf-8")).hexdigest()
    return f"acct_{digest[:12]}"


class AdminPortfolioService:
    """Build admin portfolio projections without mutating portfolio state."""

    def __init__(
        self,
        *,
        db_manager: DatabaseManager | None = None,
        auth_repo: AuthRepository | None = None,
    ):
        self.db = db_manager or DatabaseManager.get_instance()
        self.auth_repo = auth_repo or AuthRepository(self.db)

    def target_user_exists(self, user_id: str) -> bool:
        return self.auth_repo.get_app_user(str(user_id or "").strip()) is not None

    def get_summary(self, *, user_id: str, include_inactive: bool = False) -> AdminPortfolioSummaryResponse:
        user_id = str(user_id or "").strip()
        with self.db.get_session() as session:
            accounts = self._accounts(session, user_id=user_id, include_inactive=include_inactive)
            account_ids = [int(row.id) for row in accounts]
            connections = self._connections(session, user_id=user_id, account_ids=account_ids)
            connections_by_account = self._connections_by_account(connections)
            latest_sync_by_account = self._latest_sync_by_account(session, user_id=user_id, account_ids=account_ids)
            latest_snapshot_by_account = self._latest_snapshot_by_account(session, account_ids=account_ids)
            ledger_counts = self._ledger_counts(session, account_ids=account_ids)

            base_currency = self._dominant_currency(accounts, latest_sync_by_account, latest_snapshot_by_account)
            total_cash = total_market_value = total_equity = realized_pnl = unrealized_pnl = 0.0
            fx_stale = False
            last_sync_at: datetime | None = None
            statuses: dict[str, int] = {}
            for account_id in account_ids:
                sync_state = latest_sync_by_account.get(account_id)
                snapshot = latest_snapshot_by_account.get(account_id)
                source = sync_state or snapshot
                if source is not None:
                    total_cash += _float(getattr(source, "total_cash", 0.0))
                    total_market_value += _float(getattr(source, "total_market_value", 0.0))
                    total_equity += _float(getattr(source, "total_equity", 0.0))
                    realized_pnl += _float(getattr(source, "realized_pnl", getattr(source, "realized_pnl", 0.0)))
                    unrealized_pnl += _float(getattr(source, "unrealized_pnl", getattr(source, "unrealized_pnl", 0.0)))
                    fx_stale = fx_stale or bool(getattr(source, "fx_stale", False))
                if sync_state is not None:
                    status = str(getattr(sync_state, "sync_status", "unknown") or "unknown")
                    statuses[status] = statuses.get(status, 0) + 1
                    synced_at = getattr(sync_state, "synced_at", None)
                    if isinstance(synced_at, datetime) and (last_sync_at is None or synced_at > last_sync_at):
                        last_sync_at = synced_at

            return AdminPortfolioSummaryResponse(
                userId=user_id,
                accountCount=len(accounts),
                activeAccountCount=sum(1 for row in accounts if bool(row.is_active)),
                baseCurrencies=sorted({str(row.base_currency).upper() for row in accounts if str(row.base_currency or "").strip()}),
                accounts=[self._account_item(row, connections_by_account.get(int(row.id), [])) for row in accounts],
                totalCash=AdminMoneyAmount(amount=round(total_cash, 6), currency=base_currency),
                totalMarketValue=AdminMoneyAmount(amount=round(total_market_value, 6), currency=base_currency),
                totalEquity=AdminMoneyAmount(amount=round(total_equity, 6), currency=base_currency),
                realizedPnl=AdminMoneyAmount(amount=round(realized_pnl, 6), currency=base_currency),
                unrealizedPnl=AdminMoneyAmount(amount=round(unrealized_pnl, 6), currency=base_currency),
                ledgerCounts=ledger_counts,
                brokerSyncSummary=AdminBrokerSyncSummary(
                    connections=len(connections),
                    statuses=dict(sorted(statuses.items())),
                    lastSyncAt=_iso(last_sync_at),
                    fxStale=fx_stale,
                ),
                limitations=[
                    "read_only_projection",
                    "raw_broker_payloads_excluded",
                    "raw_broker_refs_masked",
                ],
            )

    def list_holdings(
        self,
        *,
        user_id: str,
        account_id: int | None = None,
        symbol: str | None = None,
        market: str | None = None,
        include_zero: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AdminHoldingItem], int]:
        user_id = str(user_id or "").strip()
        with self.db.get_session() as session:
            accounts = self._accounts(session, user_id=user_id, include_inactive=True)
            if account_id is not None and int(account_id) not in {int(row.id) for row in accounts}:
                return [], -1
            account_ids = [int(account_id)] if account_id is not None else [int(row.id) for row in accounts]
            account_by_id = {int(row.id): row for row in accounts if int(row.id) in set(account_ids)}
            connections = self._connections(session, user_id=user_id, account_ids=account_ids)
            connection_by_account = self._connections_by_account(connections)
            items = self._synced_holding_items(
                session,
                user_id=user_id,
                account_ids=account_ids,
                account_by_id=account_by_id,
                connection_by_account=connection_by_account,
            )
            if not items:
                items = self._cached_holding_items(
                    session,
                    account_ids=account_ids,
                    account_by_id=account_by_id,
                    connection_by_account=connection_by_account,
                )
            filtered = [
                item
                for item in items
                if (include_zero or abs(float(item.quantity or 0.0)) > 0)
                and (not symbol or item.symbol.upper() == symbol.upper())
                and (not market or str(item.market or "").lower() == market.lower())
            ]
            filtered.sort(key=lambda item: (item.account_id, item.symbol, item.market or "", item.currency or ""))
            total = len(filtered)
            start = max(0, int(offset))
            return filtered[start:start + max(1, int(limit))], total

    def list_activity(
        self,
        *,
        user_id: str,
        account_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AdminPortfolioActivityItem], int, AdminLedgerCounts]:
        user_id = str(user_id or "").strip()
        with self.db.get_session() as session:
            accounts = self._accounts(session, user_id=user_id, include_inactive=True)
            if account_id is not None and int(account_id) not in {int(row.id) for row in accounts}:
                return [], -1, AdminLedgerCounts()
            account_ids = [int(account_id)] if account_id is not None else [int(row.id) for row in accounts]
            account_name = {int(row.id): str(row.name) for row in accounts}
            summary = self._ledger_counts(session, account_ids=account_ids)
            window_size = max(0, int(offset)) + max(1, int(limit))
            items: list[AdminPortfolioActivityItem] = []
            for row in self._bounded_activity_rows(
                session,
                model=PortfolioTrade,
                account_ids=account_ids,
                date_column=PortfolioTrade.trade_date,
                window_size=window_size,
                extra_filter=or_(PortfolioTrade.is_active.is_(True), PortfolioTrade.is_active.is_(None)),
            ):
                items.append(
                    AdminPortfolioActivityItem(
                        idHash=_hash_ref(f"trade:{row.id}"),
                        type="trade",
                        accountId=int(row.account_id),
                        accountName=account_name.get(int(row.account_id), ""),
                        eventDate=_iso(row.trade_date) or "",
                        symbol=row.symbol,
                        market=row.market,
                        currency=row.currency,
                        side=row.side,
                        quantity=_float(row.quantity),
                        price=_float(row.price),
                        createdAt=_iso(row.created_at),
                    )
                )
            for row in self._bounded_activity_rows(
                session,
                model=PortfolioCashLedger,
                account_ids=account_ids,
                date_column=PortfolioCashLedger.event_date,
                window_size=window_size,
            ):
                items.append(
                    AdminPortfolioActivityItem(
                        idHash=_hash_ref(f"cash:{row.id}"),
                        type="cash",
                        accountId=int(row.account_id),
                        accountName=account_name.get(int(row.account_id), ""),
                        eventDate=_iso(row.event_date) or "",
                        currency=row.currency,
                        direction=row.direction,
                        amount=_float(row.amount),
                        createdAt=_iso(row.created_at),
                    )
                )
            for row in self._bounded_activity_rows(
                session,
                model=PortfolioCorporateAction,
                account_ids=account_ids,
                date_column=PortfolioCorporateAction.effective_date,
                window_size=window_size,
            ):
                items.append(
                    AdminPortfolioActivityItem(
                        idHash=_hash_ref(f"corporate_action:{row.id}"),
                        type="corporate_action",
                        accountId=int(row.account_id),
                        accountName=account_name.get(int(row.account_id), ""),
                        eventDate=_iso(row.effective_date) or "",
                        symbol=row.symbol,
                        market=row.market,
                        currency=row.currency,
                        actionType=row.action_type,
                        amount=_float(row.cash_dividend_per_share) if row.cash_dividend_per_share is not None else None,
                        createdAt=_iso(row.created_at),
                    )
                )
            items.sort(key=lambda item: (item.event_date, item.id_hash), reverse=True)
            total = summary.trades + summary.cash_events + summary.corporate_actions
            start = max(0, int(offset))
            return items[start:start + max(1, int(limit))], total, summary

    def get_account_detail(self, *, user_id: str, account_id: int) -> Optional[AdminPortfolioAccountDetailResponse]:
        user_id = str(user_id or "").strip()
        with self.db.get_session() as session:
            account = session.execute(
                select(PortfolioAccount)
                .where(and_(PortfolioAccount.owner_id == user_id, PortfolioAccount.id == int(account_id)))
                .limit(1)
            ).scalar_one_or_none()
            if account is None:
                return None
            connections = self._connections(session, user_id=user_id, account_ids=[int(account.id)])
            sync_by_account = self._latest_sync_by_account(session, user_id=user_id, account_ids=[int(account.id)])
            holding_items, holding_total = self.list_holdings(user_id=user_id, account_id=int(account.id), limit=200, offset=0)
            activity_items, activity_total, activity_summary = self.list_activity(
                user_id=user_id,
                account_id=int(account.id),
                limit=200,
                offset=0,
            )
            return AdminPortfolioAccountDetailResponse(
                userId=user_id,
                account=self._account_item(account, connections),
                brokerConnections=[self._connection_item(row) for row in connections],
                syncState=self._sync_state_item(sync_by_account.get(int(account.id))),
                holdings=AdminHoldingListResponse(
                    items=holding_items,
                    total=holding_total,
                    limit=200,
                    offset=0,
                    hasMore=False,
                    limitations=["raw_broker_payloads_excluded", "raw_broker_refs_masked"],
                ),
                activity=AdminPortfolioActivityResponse(
                    items=activity_items,
                    total=activity_total,
                    limit=200,
                    offset=0,
                    hasMore=False,
                    summary=activity_summary,
                    limitations=["notes_and_raw_import_rows_excluded"],
                ),
                limitations=["read_only_projection", "raw_broker_payloads_excluded", "raw_broker_refs_masked"],
            )

    @staticmethod
    def _accounts(session: Any, *, user_id: str, include_inactive: bool) -> list[Any]:
        query = select(PortfolioAccount).where(PortfolioAccount.owner_id == user_id)
        if not include_inactive:
            query = query.where(PortfolioAccount.is_active.is_(True))
        return list(session.execute(query.order_by(PortfolioAccount.id.asc())).scalars().all())

    @staticmethod
    def _bounded_activity_rows(
        session: Any,
        *,
        model: Any,
        account_ids: list[int],
        date_column: Any,
        window_size: int,
        extra_filter: Any | None = None,
    ) -> list[Any]:
        if not account_ids:
            return []
        filters = [model.account_id.in_(account_ids)]
        if extra_filter is not None:
            filters.append(extra_filter)
        base_filter = and_(*filters)
        limited_rows = list(
            session.execute(
                select(model)
                .where(base_filter)
                .order_by(desc(date_column), desc(model.id))
                .limit(max(1, int(window_size)))
            ).scalars().all()
        )
        if len(limited_rows) < max(1, int(window_size)):
            return limited_rows
        boundary_date = getattr(limited_rows[-1], getattr(date_column, "key", ""), None)
        if boundary_date is None:
            return limited_rows
        return list(
            session.execute(
                select(model)
                .where(and_(base_filter, date_column >= boundary_date))
                .order_by(desc(date_column), desc(model.id))
            ).scalars().all()
        )

    @staticmethod
    def _connections(session: Any, *, user_id: str, account_ids: list[int]) -> list[Any]:
        if not account_ids:
            return []
        return list(
            session.execute(
                select(PortfolioBrokerConnection)
                .where(
                    and_(
                        PortfolioBrokerConnection.owner_id == user_id,
                        PortfolioBrokerConnection.portfolio_account_id.in_(account_ids),
                    )
                )
                .order_by(PortfolioBrokerConnection.id.asc())
            ).scalars().all()
        )

    @staticmethod
    def _connections_by_account(connections: list[Any]) -> dict[int, list[Any]]:
        grouped: dict[int, list[Any]] = {}
        for row in connections:
            grouped.setdefault(int(row.portfolio_account_id), []).append(row)
        return grouped

    @staticmethod
    def _latest_sync_by_account(session: Any, *, user_id: str, account_ids: list[int]) -> dict[int, Any]:
        latest: dict[int, Any] = {}
        if not account_ids:
            return latest
        rows = session.execute(
            select(PortfolioBrokerSyncState)
            .where(and_(PortfolioBrokerSyncState.owner_id == user_id, PortfolioBrokerSyncState.portfolio_account_id.in_(account_ids)))
            .order_by(PortfolioBrokerSyncState.portfolio_account_id.asc(), desc(PortfolioBrokerSyncState.synced_at), desc(PortfolioBrokerSyncState.id))
        ).scalars().all()
        for row in rows:
            latest.setdefault(int(row.portfolio_account_id), row)
        return latest

    @staticmethod
    def _latest_snapshot_by_account(session: Any, *, account_ids: list[int]) -> dict[int, Any]:
        latest: dict[int, Any] = {}
        if not account_ids:
            return latest
        rows = session.execute(
            select(PortfolioDailySnapshot)
            .where(PortfolioDailySnapshot.account_id.in_(account_ids))
            .order_by(PortfolioDailySnapshot.account_id.asc(), desc(PortfolioDailySnapshot.snapshot_date), desc(PortfolioDailySnapshot.id))
        ).scalars().all()
        for row in rows:
            latest.setdefault(int(row.account_id), row)
        return latest

    @staticmethod
    def _ledger_counts(session: Any, *, account_ids: list[int]) -> AdminLedgerCounts:
        if not account_ids:
            return AdminLedgerCounts()
        active_trade = and_(
            PortfolioTrade.account_id.in_(account_ids),
            or_(PortfolioTrade.is_active.is_(True), PortfolioTrade.is_active.is_(None)),
        )
        return AdminLedgerCounts(
            trades=int(session.execute(select(func.count()).select_from(PortfolioTrade).where(active_trade)).scalar() or 0),
            cashEvents=int(session.execute(select(func.count()).select_from(PortfolioCashLedger).where(PortfolioCashLedger.account_id.in_(account_ids))).scalar() or 0),
            corporateActions=int(session.execute(select(func.count()).select_from(PortfolioCorporateAction).where(PortfolioCorporateAction.account_id.in_(account_ids))).scalar() or 0),
        )

    @staticmethod
    def _dominant_currency(accounts: list[Any], sync_by_account: dict[int, Any], snapshots_by_account: dict[int, Any]) -> Optional[str]:
        for row in sync_by_account.values():
            currency = str(getattr(row, "base_currency", "") or "").upper()
            if currency:
                return currency
        for row in snapshots_by_account.values():
            currency = str(getattr(row, "base_currency", "") or "").upper()
            if currency:
                return currency
        for row in accounts:
            currency = str(getattr(row, "base_currency", "") or "").upper()
            if currency:
                return currency
        return None

    @staticmethod
    def _account_item(row: Any, connections: list[Any]) -> AdminPortfolioAccountItem:
        handle = _broker_account_handle(getattr(connections[0], "broker_account_ref", None)) if connections else None
        return AdminPortfolioAccountItem(
            id=int(row.id),
            name=str(row.name),
            broker=row.broker,
            market=row.market,
            baseCurrency=row.base_currency,
            isActive=bool(row.is_active),
            brokerAccountHandle=handle,
            createdAt=_iso(row.created_at),
            updatedAt=_iso(row.updated_at),
        )

    @staticmethod
    def _connection_item(row: Any) -> AdminPortfolioBrokerConnectionItem:
        return AdminPortfolioBrokerConnectionItem(
            id=int(row.id),
            accountId=int(row.portfolio_account_id),
            brokerType=str(row.broker_type),
            brokerName=row.broker_name,
            connectionName=str(row.connection_name),
            brokerAccountHandle=_broker_account_handle(row.broker_account_ref),
            importMode=row.import_mode,
            status=str(row.status),
            lastImportedAt=_iso(row.last_imported_at),
            lastImportSource=row.last_import_source,
            createdAt=_iso(row.created_at),
            updatedAt=_iso(row.updated_at),
        )

    @staticmethod
    def _sync_state_item(row: Any | None) -> AdminPortfolioSyncState | None:
        if row is None:
            return None
        currency = str(getattr(row, "base_currency", "") or "").upper() or None
        return AdminPortfolioSyncState(
            status=row.sync_status,
            source=row.sync_source,
            snapshotDate=_iso(row.snapshot_date),
            syncedAt=_iso(row.synced_at),
            baseCurrency=currency,
            totalCash=AdminMoneyAmount(amount=_float(row.total_cash), currency=currency),
            totalMarketValue=AdminMoneyAmount(amount=_float(row.total_market_value), currency=currency),
            totalEquity=AdminMoneyAmount(amount=_float(row.total_equity), currency=currency),
            realizedPnl=AdminMoneyAmount(amount=_float(row.realized_pnl), currency=currency),
            unrealizedPnl=AdminMoneyAmount(amount=_float(row.unrealized_pnl), currency=currency),
            fxStale=bool(row.fx_stale),
        )

    @staticmethod
    def _synced_holding_items(
        session: Any,
        *,
        user_id: str,
        account_ids: list[int],
        account_by_id: dict[int, Any],
        connection_by_account: dict[int, list[Any]],
    ) -> list[AdminHoldingItem]:
        if not account_ids:
            return []
        rows = session.execute(
            select(PortfolioBrokerSyncPosition)
            .where(
                and_(
                    PortfolioBrokerSyncPosition.owner_id == user_id,
                    PortfolioBrokerSyncPosition.portfolio_account_id.in_(account_ids),
                )
            )
        ).scalars().all()
        items: list[AdminHoldingItem] = []
        for row in rows:
            account = account_by_id.get(int(row.portfolio_account_id))
            if account is None:
                continue
            connections = connection_by_account.get(int(row.portfolio_account_id), [])
            handle = _broker_account_handle(getattr(connections[0], "broker_account_ref", None)) if connections else None
            items.append(
                AdminHoldingItem(
                    accountId=int(row.portfolio_account_id),
                    accountName=str(account.name),
                    broker=getattr(account, "broker", None),
                    brokerAccountHandle=handle,
                    symbol=str(row.symbol),
                    market=row.market,
                    currency=row.currency,
                    quantity=_float(row.quantity),
                    avgCost=_float(row.avg_cost),
                    lastPrice=_float(row.last_price),
                    marketValueBase=_float(row.market_value_base),
                    unrealizedPnlBase=_float(row.unrealized_pnl_base),
                    valuationCurrency=row.valuation_currency,
                    fxStatus="stale" if False else "current",
                    updatedAt=_iso(row.updated_at),
                )
            )
        return items

    @staticmethod
    def _cached_holding_items(
        session: Any,
        *,
        account_ids: list[int],
        account_by_id: dict[int, Any],
        connection_by_account: dict[int, list[Any]],
    ) -> list[AdminHoldingItem]:
        if not account_ids:
            return []
        rows = session.execute(
            select(PortfolioPosition).where(PortfolioPosition.account_id.in_(account_ids))
        ).scalars().all()
        items: list[AdminHoldingItem] = []
        for row in rows:
            account = account_by_id.get(int(row.account_id))
            if account is None:
                continue
            connections = connection_by_account.get(int(row.account_id), [])
            handle = _broker_account_handle(getattr(connections[0], "broker_account_ref", None)) if connections else None
            items.append(
                AdminHoldingItem(
                    accountId=int(row.account_id),
                    accountName=str(account.name),
                    broker=getattr(account, "broker", None),
                    brokerAccountHandle=handle,
                    symbol=str(row.symbol),
                    market=row.market,
                    currency=row.currency,
                    quantity=_float(row.quantity),
                    avgCost=_float(row.avg_cost),
                    lastPrice=_float(row.last_price),
                    marketValueBase=_float(row.market_value_base),
                    unrealizedPnlBase=_float(row.unrealized_pnl_base),
                    valuationCurrency=row.valuation_currency,
                    fxStatus="current",
                    updatedAt=_iso(row.updated_at),
                )
            )
        return items
