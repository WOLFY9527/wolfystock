# -*- coding: utf-8 -*-
"""Safe admin portfolio visibility schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _AdminPortfolioModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AdminMoneyAmount(_AdminPortfolioModel):
    amount: float = 0.0
    currency: Optional[str] = None


class AdminPortfolioAccountItem(_AdminPortfolioModel):
    id: int
    name: str
    broker: Optional[str] = None
    market: Optional[str] = None
    base_currency: Optional[str] = Field(default=None, alias="baseCurrency")
    is_active: bool = Field(alias="isActive")
    broker_account_handle: Optional[str] = Field(default=None, alias="brokerAccountHandle")
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")


class AdminPortfolioBrokerConnectionItem(_AdminPortfolioModel):
    id: int
    account_id: int = Field(alias="accountId")
    broker_type: str = Field(alias="brokerType")
    broker_name: Optional[str] = Field(default=None, alias="brokerName")
    connection_name: str = Field(alias="connectionName")
    broker_account_handle: Optional[str] = Field(default=None, alias="brokerAccountHandle")
    import_mode: Optional[str] = Field(default=None, alias="importMode")
    status: str
    last_imported_at: Optional[str] = Field(default=None, alias="lastImportedAt")
    last_import_source: Optional[str] = Field(default=None, alias="lastImportSource")
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")


class AdminBrokerSyncSummary(_AdminPortfolioModel):
    connections: int = 0
    statuses: dict[str, int] = Field(default_factory=dict)
    last_sync_at: Optional[str] = Field(default=None, alias="lastSyncAt")
    fx_stale: bool = Field(default=False, alias="fxStale")


class AdminLedgerCounts(_AdminPortfolioModel):
    trades: int = 0
    cash_events: int = Field(default=0, alias="cashEvents")
    corporate_actions: int = Field(default=0, alias="corporateActions")


class AdminPortfolioSummaryResponse(_AdminPortfolioModel):
    user_id: str = Field(alias="userId")
    account_count: int = Field(alias="accountCount")
    active_account_count: int = Field(alias="activeAccountCount")
    base_currencies: list[str] = Field(default_factory=list, alias="baseCurrencies")
    accounts: list[AdminPortfolioAccountItem] = Field(default_factory=list)
    total_cash: AdminMoneyAmount = Field(alias="totalCash")
    total_market_value: AdminMoneyAmount = Field(alias="totalMarketValue")
    total_equity: AdminMoneyAmount = Field(alias="totalEquity")
    realized_pnl: AdminMoneyAmount = Field(alias="realizedPnl")
    unrealized_pnl: AdminMoneyAmount = Field(alias="unrealizedPnl")
    ledger_counts: AdminLedgerCounts = Field(alias="ledgerCounts")
    broker_sync_summary: AdminBrokerSyncSummary = Field(alias="brokerSyncSummary")
    limitations: list[str] = Field(default_factory=list)


class AdminHoldingItem(_AdminPortfolioModel):
    account_id: int = Field(alias="accountId")
    account_name: str = Field(alias="accountName")
    broker: Optional[str] = None
    broker_account_handle: Optional[str] = Field(default=None, alias="brokerAccountHandle")
    symbol: str
    market: Optional[str] = None
    currency: Optional[str] = None
    quantity: float
    avg_cost: float = Field(alias="avgCost")
    last_price: float = Field(alias="lastPrice")
    market_value_base: float = Field(alias="marketValueBase")
    unrealized_pnl_base: float = Field(alias="unrealizedPnlBase")
    valuation_currency: Optional[str] = Field(default=None, alias="valuationCurrency")
    fx_status: str = Field(alias="fxStatus")
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")


class AdminHoldingListResponse(_AdminPortfolioModel):
    items: list[AdminHoldingItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    has_more: bool = Field(default=False, alias="hasMore")
    limitations: list[str] = Field(default_factory=list)


class AdminPortfolioActivityItem(_AdminPortfolioModel):
    id_hash: str = Field(alias="idHash")
    type: str
    account_id: int = Field(alias="accountId")
    account_name: str = Field(alias="accountName")
    event_date: str = Field(alias="eventDate")
    symbol: Optional[str] = None
    market: Optional[str] = None
    currency: Optional[str] = None
    side: Optional[str] = None
    direction: Optional[str] = None
    action_type: Optional[str] = Field(default=None, alias="actionType")
    quantity: Optional[float] = None
    price: Optional[float] = None
    amount: Optional[float] = None
    created_at: Optional[str] = Field(default=None, alias="createdAt")


class AdminPortfolioActivityResponse(_AdminPortfolioModel):
    items: list[AdminPortfolioActivityItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    has_more: bool = Field(default=False, alias="hasMore")
    summary: AdminLedgerCounts
    limitations: list[str] = Field(default_factory=list)


class AdminPortfolioSyncState(_AdminPortfolioModel):
    status: Optional[str] = None
    source: Optional[str] = None
    snapshot_date: Optional[str] = Field(default=None, alias="snapshotDate")
    synced_at: Optional[str] = Field(default=None, alias="syncedAt")
    base_currency: Optional[str] = Field(default=None, alias="baseCurrency")
    total_cash: AdminMoneyAmount = Field(alias="totalCash")
    total_market_value: AdminMoneyAmount = Field(alias="totalMarketValue")
    total_equity: AdminMoneyAmount = Field(alias="totalEquity")
    realized_pnl: AdminMoneyAmount = Field(alias="realizedPnl")
    unrealized_pnl: AdminMoneyAmount = Field(alias="unrealizedPnl")
    fx_stale: bool = Field(default=False, alias="fxStale")


class AdminPortfolioAccountDetailResponse(_AdminPortfolioModel):
    user_id: str = Field(alias="userId")
    account: AdminPortfolioAccountItem
    broker_connections: list[AdminPortfolioBrokerConnectionItem] = Field(default_factory=list, alias="brokerConnections")
    sync_state: Optional[AdminPortfolioSyncState] = Field(default=None, alias="syncState")
    holdings: AdminHoldingListResponse
    activity: AdminPortfolioActivityResponse
    limitations: list[str] = Field(default_factory=list)
