# -*- coding: utf-8 -*-
"""Portfolio API schemas."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PortfolioAccountCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    broker: Optional[str] = Field(None, max_length=64)
    market: Literal["cn", "hk", "us", "global"] = "cn"
    base_currency: str = Field("CNY", min_length=3, max_length=8)
    owner_id: Optional[str] = Field(None, max_length=64)


class PortfolioAccountUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    broker: Optional[str] = Field(None, max_length=64)
    market: Optional[Literal["cn", "hk", "us", "global"]] = None
    base_currency: Optional[str] = Field(None, min_length=3, max_length=8)
    owner_id: Optional[str] = Field(None, max_length=64)
    is_active: Optional[bool] = None


class PortfolioAccountItem(BaseModel):
    id: int
    owner_id: Optional[str] = None
    name: str
    broker: Optional[str] = None
    market: str
    base_currency: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PortfolioAccountListResponse(BaseModel):
    accounts: List[PortfolioAccountItem] = Field(default_factory=list)


class PortfolioBrokerConnectionCreateRequest(BaseModel):
    portfolio_account_id: int
    broker_type: str = Field(..., min_length=2, max_length=32)
    broker_name: Optional[str] = Field(None, max_length=64)
    connection_name: str = Field(..., min_length=1, max_length=64)
    broker_account_ref: Optional[str] = Field(None, max_length=128)
    import_mode: str = Field("file", min_length=3, max_length=16)
    status: str = Field("active", min_length=3, max_length=16)
    sync_metadata: Dict[str, Any] = Field(default_factory=dict)


class PortfolioBrokerConnectionUpdateRequest(BaseModel):
    portfolio_account_id: Optional[int] = None
    broker_name: Optional[str] = Field(None, max_length=64)
    connection_name: Optional[str] = Field(None, min_length=1, max_length=64)
    broker_account_ref: Optional[str] = Field(None, max_length=128)
    import_mode: Optional[str] = Field(None, min_length=3, max_length=16)
    status: Optional[str] = Field(None, min_length=3, max_length=16)
    sync_metadata: Optional[Dict[str, Any]] = None


class PortfolioBrokerConnectionItem(BaseModel):
    id: int
    owner_id: Optional[str] = None
    portfolio_account_id: int
    portfolio_account_name: Optional[str] = None
    broker_type: str
    broker_name: Optional[str] = None
    connection_name: str
    broker_account_ref: Optional[str] = None
    import_mode: str
    status: str
    last_imported_at: Optional[str] = None
    last_import_source: Optional[str] = None
    last_import_fingerprint: Optional[str] = None
    sync_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PortfolioBrokerConnectionListResponse(BaseModel):
    connections: List[PortfolioBrokerConnectionItem] = Field(default_factory=list)


class PortfolioIbkrSyncRequest(BaseModel):
    account_id: int
    broker_connection_id: Optional[int] = None
    broker_account_ref: Optional[str] = Field(None, max_length=128)
    session_token: str = Field(..., min_length=1, max_length=512)
    api_base_url: Optional[str] = Field(None, max_length=255)
    verify_ssl: Optional[bool] = None


class PortfolioIbkrSyncResponse(BaseModel):
    account_id: int
    broker_connection_id: int
    broker_account_ref: str
    connection_name: str
    snapshot_date: str
    synced_at: str
    base_currency: str
    total_cash: float
    total_market_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    position_count: int
    cash_balance_count: int
    fx_stale: bool
    snapshot_overlay_active: bool
    used_existing_connection: bool
    api_base_url: str
    verify_ssl: bool
    warnings: List[str] = Field(default_factory=list)


class PortfolioTradeCreateRequest(BaseModel):
    account_id: int
    symbol: str = Field(..., min_length=1, max_length=16)
    trade_date: date
    side: Literal["buy", "sell"]
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    fee: float = Field(0.0, ge=0)
    tax: float = Field(0.0, ge=0)
    market: Optional[Literal["cn", "hk", "us"]] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=8)
    trade_uid: Optional[str] = Field(None, max_length=128)
    note: Optional[str] = Field(None, max_length=255)


class PortfolioTradeUpdateRequest(BaseModel):
    account_id: Optional[int] = None
    symbol: Optional[str] = Field(None, min_length=1, max_length=16)
    trade_date: Optional[date] = None
    side: Optional[Literal["buy", "sell"]] = None
    quantity: Optional[float] = Field(None, gt=0)
    price: Optional[float] = Field(None, gt=0)
    fee: Optional[float] = Field(None, ge=0)
    tax: Optional[float] = Field(None, ge=0)
    market: Optional[Literal["cn", "hk", "us"]] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=8)
    note: Optional[str] = Field(None, max_length=255)


class PortfolioCashLedgerCreateRequest(BaseModel):
    account_id: int
    event_date: date
    direction: Literal["in", "out"]
    amount: float = Field(..., gt=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=8)
    note: Optional[str] = Field(None, max_length=255)


class PortfolioCorporateActionCreateRequest(BaseModel):
    account_id: int
    symbol: str = Field(..., min_length=1, max_length=16)
    effective_date: date
    action_type: Literal["cash_dividend", "split_adjustment"]
    market: Optional[Literal["cn", "hk", "us"]] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=8)
    cash_dividend_per_share: Optional[float] = Field(None, ge=0)
    split_ratio: Optional[float] = Field(None, gt=0)
    note: Optional[str] = Field(None, max_length=255)


class PortfolioEventCreatedResponse(BaseModel):
    id: int


class PortfolioDeleteResponse(BaseModel):
    deleted: int
    delete_mode: Optional[Literal["soft", "hard"]] = None


class PortfolioAccountDeleteResponse(BaseModel):
    ok: bool
    deleted_account_id: int
    delete_mode: Literal["soft", "hard"]
    next_account_id: Optional[int] = None


class PortfolioTradeListItem(BaseModel):
    id: int
    account_id: int
    trade_uid: Optional[str] = None
    symbol: str
    market: str
    currency: str
    trade_date: str
    side: str
    quantity: float
    price: float
    fee: float
    tax: float
    note: Optional[str] = None
    is_active: bool = True
    voided_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PortfolioTradeListResponse(BaseModel):
    items: List[PortfolioTradeListItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class PortfolioCashLedgerListItem(BaseModel):
    id: int
    account_id: int
    event_date: str
    direction: str
    amount: float
    currency: str
    note: Optional[str] = None
    created_at: Optional[str] = None


class PortfolioCashLedgerListResponse(BaseModel):
    items: List[PortfolioCashLedgerListItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class PortfolioCorporateActionListItem(BaseModel):
    id: int
    account_id: int
    symbol: str
    market: str
    currency: str
    effective_date: str
    action_type: str
    cash_dividend_per_share: Optional[float] = None
    split_ratio: Optional[float] = None
    note: Optional[str] = None
    created_at: Optional[str] = None


class PortfolioCorporateActionListResponse(BaseModel):
    items: List[PortfolioCorporateActionListItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class PortfolioPositionItem(BaseModel):
    symbol: str
    market: str
    currency: str
    quantity: float
    avg_cost: float
    total_cost: float
    last_price: float
    price_source: Optional[str] = None
    price_source_label: Optional[str] = None
    price_as_of: Optional[str] = None
    is_price_fallback: Optional[bool] = None
    price_fallback_reason: Optional[str] = None
    valuation_confidence: Optional[float] = None
    market_value_base: float
    unrealized_pnl_base: float
    valuation_currency: str
    cost_basis_native: Optional[float] = None
    market_value_native: Optional[float] = None
    unrealized_pnl_native: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    display_market_value: Optional[float] = None
    display_unrealized_pnl: Optional[float] = None
    display_currency: Optional[str] = None
    display_fx_status: Optional[Literal["live", "stale", "unavailable"]] = None


class PortfolioAccountSnapshot(BaseModel):
    account_id: int
    account_name: str
    owner_id: Optional[str] = None
    broker: Optional[str] = None
    market: str
    base_currency: str
    as_of: str
    cost_method: str
    total_cash: float
    total_market_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    fee_total: float
    tax_total: float
    fx_stale: bool
    data_status: Optional[
        Literal[
            "no_positions",
            "provider_unavailable",
            "stale_or_cached",
            "ready",
        ]
    ] = None
    calculation_status: Optional[Literal["ready", "calculation_unavailable"]] = None
    availability: Optional[Dict[str, Any]] = None
    positions: List[PortfolioPositionItem] = Field(default_factory=list)


class PortfolioMarketBreakdownItem(BaseModel):
    market: str
    position_count: int
    total_market_value: float
    weight_pct: float


class PortfolioFxRateItem(BaseModel):
    from_currency: str
    to_currency: str
    rate: Optional[float] = None
    rate_date: Optional[str] = None
    source: str
    is_stale: bool
    updated_at: Optional[str] = None
    source_direction: str


class PortfolioPnlMetric(BaseModel):
    amount: float
    amount_display: Optional[str] = None
    percent: Optional[float] = None
    currency: str
    fx_status: Literal["live", "stale", "unavailable"] = "live"


class PortfolioPnlSummary(BaseModel):
    display_currency: str
    realized: PortfolioPnlMetric
    unrealized: PortfolioPnlMetric
    total: PortfolioPnlMetric


class PortfolioExposureItem(BaseModel):
    key: str
    label: str
    market_value: float
    display_value: float
    display_currency: str
    percent: float
    fx_status: Literal["live", "stale", "unavailable"] = "live"
    native_value: Optional[float] = None
    native_currency: Optional[str] = None
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    base_currency: Optional[str] = None
    currency: Optional[str] = None
    market: Optional[str] = None
    symbol: Optional[str] = None
    sector: Optional[str] = None
    holding_count: Optional[int] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None


class PortfolioExposureSummary(BaseModel):
    by_account: List[PortfolioExposureItem] = Field(default_factory=list)
    by_currency: List[PortfolioExposureItem] = Field(default_factory=list)
    by_market: List[PortfolioExposureItem] = Field(default_factory=list)
    by_symbol: List[PortfolioExposureItem] = Field(default_factory=list)
    by_sector: List[PortfolioExposureItem] = Field(default_factory=list)
    sector_status: Literal["available", "unavailable"] = "unavailable"


class PortfolioRiskSummary(BaseModel):
    largest_position: Optional[Dict[str, Any]] = None
    largest_currency: Optional[Dict[str, Any]] = None
    largest_market: Optional[Dict[str, Any]] = None
    holding_count: int = 0
    account_count: int = 0
    cash_percent: Optional[float] = None
    fx_unavailable: bool = False
    warnings: List[str] = Field(default_factory=list)


class PortfolioAnalyticsSummary(BaseModel):
    pnl: PortfolioPnlSummary
    exposure: PortfolioExposureSummary
    risk: PortfolioRiskSummary


class PortfolioSnapshotResponse(BaseModel):
    as_of: str
    cost_method: str
    currency: str
    account_count: int
    total_cash: float
    total_market_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    fee_total: float
    tax_total: float
    fx_stale: bool
    data_status: Optional[
        Literal[
            "no_account",
            "no_positions",
            "data_unavailable",
            "provider_unavailable",
            "calculation_unavailable",
            "stale_or_cached",
            "ready",
        ]
    ] = None
    calculation_status: Optional[Literal["ready", "calculation_unavailable"]] = None
    availability: Optional[Dict[str, Any]] = None
    market_breakdown: List[PortfolioMarketBreakdownItem] = Field(default_factory=list)
    fx_rates: List[PortfolioFxRateItem] = Field(default_factory=list)
    portfolio_attribution: Dict[str, Any] = Field(default_factory=dict)
    analytics: Optional[PortfolioAnalyticsSummary] = None
    riskDiagnostics: Optional[Dict[str, Any]] = None
    portfolioRiskEvidence: Optional[Dict[str, Any]] = None
    sourceAuthorityState: Optional[str] = None
    fxFreshnessState: Optional[str] = None
    valuationLineageState: Optional[str] = None
    holdingsLineageState: Optional[str] = None
    cashLedgerCompletenessState: Optional[str] = None
    benchmarkMappingState: Optional[str] = None
    factorMappingState: Optional[str] = None
    confidenceCap: Optional[Dict[str, Any]] = None
    accounts: List[PortfolioAccountSnapshot] = Field(default_factory=list)


class PortfolioHistorySnapshotItem(BaseModel):
    account_id: int
    snapshot_date: str
    cost_method: str
    base_currency: str
    total_cash: float
    total_market_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    fee_total: float
    tax_total: float
    fx_stale: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PortfolioHistoryCoverage(BaseModel):
    status: Literal["available", "insufficient_data"]
    point_count: int
    insufficient_data: bool
    sparse: bool
    warnings: List[str] = Field(default_factory=list)
    requested_date_from: Optional[str] = None
    requested_date_to: Optional[str] = None
    first_snapshot_date: Optional[str] = None
    last_snapshot_date: Optional[str] = None
    account_count: int = 0


class PortfolioHistoryMetadata(BaseModel):
    stored_snapshot_only: bool = True
    no_backfill: bool = True
    no_accounting_replay: bool = True
    no_provider_runtime: bool = True
    source_table: str = "portfolio_daily_snapshots"


class PortfolioHistoryResponse(BaseModel):
    read_model_type: str = "portfolio_history_readonly_v1"
    account_id: Optional[int] = None
    cost_method: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int
    total: int
    items: List[PortfolioHistorySnapshotItem] = Field(default_factory=list)
    coverage: PortfolioHistoryCoverage
    metadata: PortfolioHistoryMetadata = Field(default_factory=PortfolioHistoryMetadata)


class PortfolioStructureReviewHolding(BaseModel):
    ticker: str
    structureState: str
    confidence: Literal["high", "medium", "low"]
    evidenceQuality: Dict[str, Any]
    riskFlags: List[str] = Field(default_factory=list)
    researchNotes: Dict[str, List[str]] = Field(default_factory=dict)
    missingEvidence: List[Dict[str, str]] = Field(default_factory=list)
    consumerIssues: List[Dict[str, str]] = Field(default_factory=list)


class PortfolioStructureReviewLinkTarget(BaseModel):
    label: str
    route: str
    section: str
    reason: str


class PortfolioStructureReviewDegradedLinkage(BaseModel):
    surface: str
    status: Literal["degraded", "unavailable"]
    reason: str
    message: str


class PortfolioStructureReviewHoldingDrilldown(BaseModel):
    ticker: str
    structureLinks: List[PortfolioStructureReviewLinkTarget] = Field(default_factory=list)
    radarLinks: List[PortfolioStructureReviewLinkTarget] = Field(default_factory=list)
    watchlistLinks: List[PortfolioStructureReviewLinkTarget] = Field(default_factory=list)
    scenarioLinks: List[PortfolioStructureReviewLinkTarget] = Field(default_factory=list)
    evidenceLinkage: Literal["available", "degraded", "unavailable"]
    degradedLinkage: List[PortfolioStructureReviewDegradedLinkage] = Field(default_factory=list)


class PortfolioStructureReviewEvidenceLinkage(BaseModel):
    status: Literal["available", "degraded", "unavailable"]
    availableHoldings: int = 0
    degradedHoldings: int = 0
    unavailableHoldings: int = 0


class PortfolioStructureReviewResearchLinkage(BaseModel):
    status: Literal["available", "degraded", "unavailable"]
    holdingDrilldowns: List[PortfolioStructureReviewHoldingDrilldown] = Field(default_factory=list)
    structureLinks: List[PortfolioStructureReviewLinkTarget] = Field(default_factory=list)
    radarLinks: List[PortfolioStructureReviewLinkTarget] = Field(default_factory=list)
    watchlistLinks: List[PortfolioStructureReviewLinkTarget] = Field(default_factory=list)
    scenarioLinks: List[PortfolioStructureReviewLinkTarget] = Field(default_factory=list)
    evidenceLinkage: PortfolioStructureReviewEvidenceLinkage
    degradedLinkage: List[PortfolioStructureReviewDegradedLinkage] = Field(default_factory=list)


class PortfolioStructureReviewResponse(BaseModel):
    schemaVersion: str
    aggregateSummary: Dict[str, Any] = Field(default_factory=dict)
    exposureByThemeOrSector: List[Dict[str, Any]] = Field(default_factory=list)
    countsByStructureState: Dict[str, int] = Field(default_factory=dict)
    holdingsStructure: List[PortfolioStructureReviewHolding] = Field(default_factory=list)
    strongestStructures: List[Dict[str, Any]] = Field(default_factory=list)
    weakestEvidence: List[Dict[str, Any]] = Field(default_factory=list)
    commonRiskFlags: List[Dict[str, Any]] = Field(default_factory=list)
    missingEvidence: List[Dict[str, str]] = Field(default_factory=list)
    researchLinkage: PortfolioStructureReviewResearchLinkage
    readOnly: bool
    failClosed: bool
    consumerState: Literal["AVAILABLE", "PARTIAL", "UNAVAILABLE"]
    consumerSummary: str
    consumerMessage: str
    drilldownSymbols: List[str] = Field(default_factory=list)
    dataQuality: Dict[str, Any] = Field(default_factory=dict)
    consumerIssues: List[Dict[str, str]] = Field(default_factory=list)
    noAdviceDisclosure: str


class PortfolioImportTradeItem(BaseModel):
    trade_date: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    fee: float
    tax: float
    trade_uid: Optional[str] = None
    dedup_hash: str
    market: Optional[str] = None
    currency: Optional[str] = None
    note: Optional[str] = None


class PortfolioImportCashEntryItem(BaseModel):
    event_date: str
    direction: Literal["in", "out"]
    amount: float
    currency: str
    note: Optional[str] = None


class PortfolioImportCorporateActionItem(BaseModel):
    effective_date: str
    symbol: str
    market: str
    currency: str
    action_type: Literal["cash_dividend", "split_adjustment"]
    cash_dividend_per_share: Optional[float] = None
    split_ratio: Optional[float] = None
    note: Optional[str] = None


class PortfolioImportParseResponse(BaseModel):
    broker: str
    record_count: int
    skipped_count: int
    error_count: int
    records: List[PortfolioImportTradeItem] = Field(default_factory=list)
    cash_record_count: int = 0
    cash_entries: List[PortfolioImportCashEntryItem] = Field(default_factory=list)
    corporate_action_count: int = 0
    corporate_actions: List[PortfolioImportCorporateActionItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


class PortfolioImportCommitResponse(BaseModel):
    account_id: int
    record_count: int
    inserted_count: int
    duplicate_count: int
    failed_count: int
    cash_record_count: int = 0
    cash_inserted_count: int = 0
    cash_failed_count: int = 0
    corporate_action_count: int = 0
    corporate_action_inserted_count: int = 0
    corporate_action_failed_count: int = 0
    dry_run: bool
    duplicate_import: bool = False
    broker_connection_id: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


class PortfolioImportBrokerItem(BaseModel):
    broker: str
    aliases: List[str] = Field(default_factory=list)
    display_name: Optional[str] = None
    file_extensions: List[str] = Field(default_factory=list)


class PortfolioImportBrokerListResponse(BaseModel):
    brokers: List[PortfolioImportBrokerItem] = Field(default_factory=list)


class PortfolioFxRefreshResponse(BaseModel):
    as_of: str
    account_count: int
    refresh_enabled: bool
    disabled_reason: Optional[str] = None
    pair_count: int
    updated_count: int
    stale_count: int
    error_count: int


class PortfolioLiveFxRateResponse(BaseModel):
    base_currency: str
    quote_currency: str
    rate: float
    provider: str
    fetched_at: str
    cache_hit: bool
    stale: bool
    error: Optional[str] = None


class PortfolioRiskResponse(BaseModel):
    as_of: str
    account_id: Optional[int] = None
    cost_method: str
    currency: str
    data_status: Optional[
        Literal[
            "no_account",
            "no_positions",
            "data_unavailable",
            "provider_unavailable",
            "calculation_unavailable",
            "stale_or_cached",
            "ready",
        ]
    ] = None
    calculation_status: Optional[Literal["ready", "calculation_unavailable"]] = None
    availability: Optional[Dict[str, Any]] = None
    thresholds: Dict[str, Any] = Field(default_factory=dict)
    concentration: Dict[str, Any] = Field(default_factory=dict)
    sector_concentration: Dict[str, Any] = Field(default_factory=dict)
    industry_attribution: Dict[str, Any] = Field(default_factory=dict)
    sectorSourceProvenance: Optional[Dict[str, Any]] = None
    drawdown: Dict[str, Any] = Field(default_factory=dict)
    stop_loss: Dict[str, Any] = Field(default_factory=dict)
    account_attribution: Dict[str, Any] = Field(default_factory=dict)
    riskDiagnostics: Optional[Dict[str, Any]] = None
    portfolioRiskEvidence: Optional[Dict[str, Any]] = None
    sourceAuthorityState: Optional[str] = None
    fxFreshnessState: Optional[str] = None
    valuationLineageState: Optional[str] = None
    holdingsLineageState: Optional[str] = None
    cashLedgerCompletenessState: Optional[str] = None
    benchmarkMappingState: Optional[str] = None
    factorMappingState: Optional[str] = None
    confidenceCap: Optional[Dict[str, Any]] = None


class PortfolioScenarioRiskRequest(BaseModel):
    asOf: str = Field(..., min_length=1)
    positions: List[Dict[str, Any]] | Dict[str, Any]
    exposures: List[Dict[str, Any]] | Dict[str, Any]
    scenarioShocks: List[Dict[str, Any]] | Dict[str, Any]


class PortfolioScenarioRiskResponse(BaseModel):
    readModelType: str
    advisoryOnly: bool
    accountingMutation: bool = False
    brokerIntegration: bool = False
    tradeExecution: bool = False
    executionReadiness: str
    asOf: Optional[str] = None
    coverage: Dict[str, Any] = Field(default_factory=dict)
    scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    insufficientDataReasons: List[str] = Field(default_factory=list)
    missingDataWarnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
