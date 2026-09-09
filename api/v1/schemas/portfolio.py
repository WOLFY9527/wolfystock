# -*- coding: utf-8 -*-
"""Portfolio API schemas."""

from __future__ import annotations

from decimal import Decimal
from datetime import date
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    field_serializer,
    model_validator,
)

from src.contracts.portfolio_truth import PortfolioTruth
from src.portfolio_exact_numeric import (
    parse_portfolio_decimal,
    parse_portfolio_decimal_transport,
    serialize_portfolio_decimal_value,
)


def _parse_portfolio_transport_decimal(value: Any) -> Decimal:
    """Preserve a public decimal token until its owner resolves precision."""

    return parse_portfolio_decimal_transport(value)


def _serialize_portfolio_decimal_wire(value: Decimal) -> str:
    """Render an already-resolved Decimal without exponent notation."""

    return format(value, "f")


def _serialize_portfolio_decimal_tree(value: Any) -> Any:
    """Preserve dynamic response values while rendering Decimal leaves as wire text."""

    if isinstance(value, Decimal):
        return _serialize_portfolio_decimal_wire(value)
    if isinstance(value, list):
        return [_serialize_portfolio_decimal_tree(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_portfolio_decimal_tree(item) for key, item in value.items()}
    return value


_PORTFOLIO_DECIMAL_TEXT_PATTERN = r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$"
_PORTFOLIO_EXACT_DECIMAL_INPUT_SCHEMA = {
    "anyOf": [
        {"type": "integer"},
        {"type": "string", "pattern": _PORTFOLIO_DECIMAL_TEXT_PATTERN},
    ]
}
_PORTFOLIO_EXACT_DECIMAL_OUTPUT_SCHEMA = {
    "type": "string",
    "pattern": _PORTFOLIO_DECIMAL_TEXT_PATTERN,
}


class _PortfolioTransportDecimalJsonSchema:
    def __get_pydantic_json_schema__(self, core_schema: Any, handler: Any) -> Dict[str, Any]:
        schema = handler(core_schema)
        if handler.mode == "serialization":
            return {**schema, **_PORTFOLIO_EXACT_DECIMAL_OUTPUT_SCHEMA}

        variants = schema.get("anyOf")
        if not isinstance(variants, list):
            return schema
        return {
            **schema,
            "anyOf": [
                {**variant, "type": "integer"}
                if isinstance(variant, dict) and variant.get("type") == "number"
                else variant
                for variant in variants
            ],
        }


PortfolioTransportDecimal = Annotated[
    Decimal,
    BeforeValidator(_parse_portfolio_transport_decimal),
    PlainSerializer(_serialize_portfolio_decimal_wire, return_type=str, when_used="json"),
    _PortfolioTransportDecimalJsonSchema(),
]

PortfolioContextualDecimal = Annotated[
    Decimal,
    WithJsonSchema(_PORTFOLIO_EXACT_DECIMAL_INPUT_SCHEMA, mode="validation"),
    WithJsonSchema(_PORTFOLIO_EXACT_DECIMAL_OUTPUT_SCHEMA, mode="serialization"),
]

_IBKR_SYNC_MONEY_FIELDS = (
    "total_cash",
    "total_market_value",
    "total_equity",
    "realized_pnl",
    "unrealized_pnl",
)


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
    total_cash: PortfolioContextualDecimal
    total_market_value: PortfolioContextualDecimal
    total_equity: PortfolioContextualDecimal
    realized_pnl: PortfolioContextualDecimal
    unrealized_pnl: PortfolioContextualDecimal
    position_count: int
    cash_balance_count: int
    fx_stale: bool
    snapshot_overlay_active: bool
    used_existing_connection: bool
    api_base_url: str
    verify_ssl: bool
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _validate_money_against_base_currency(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        for field_name in _IBKR_SYNC_MONEY_FIELDS:
            if field_name in payload:
                payload[field_name] = parse_portfolio_decimal(
                    payload[field_name],
                    kind="money",
                    currency=payload.get("base_currency"),
                )
        return payload


class PortfolioTradeCreateRequest(BaseModel):
    account_id: int
    symbol: str = Field(..., min_length=1, max_length=16)
    trade_date: date
    side: Literal["buy", "sell"]
    quantity: PortfolioTransportDecimal = Field(..., gt=0)
    price: PortfolioTransportDecimal = Field(..., gt=0)
    fee: PortfolioTransportDecimal = Field(Decimal("0"), ge=0)
    tax: PortfolioTransportDecimal = Field(Decimal("0"), ge=0)
    market: Optional[Literal["cn", "hk", "us"]] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=8)
    trade_uid: Optional[str] = Field(None, max_length=128)
    note: Optional[str] = Field(None, max_length=255)


class PortfolioTradeUpdateRequest(BaseModel):
    account_id: Optional[int] = None
    symbol: Optional[str] = Field(None, min_length=1, max_length=16)
    trade_date: Optional[date] = None
    side: Optional[Literal["buy", "sell"]] = None
    quantity: Optional[PortfolioTransportDecimal] = Field(None, gt=0)
    price: Optional[PortfolioTransportDecimal] = Field(None, gt=0)
    fee: Optional[PortfolioTransportDecimal] = Field(None, ge=0)
    tax: Optional[PortfolioTransportDecimal] = Field(None, ge=0)
    market: Optional[Literal["cn", "hk", "us"]] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=8)
    note: Optional[str] = Field(None, max_length=255)


class PortfolioCashLedgerCreateRequest(BaseModel):
    account_id: int
    event_date: date
    direction: Literal["in", "out"]
    amount: PortfolioTransportDecimal = Field(..., gt=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=8)
    note: Optional[str] = Field(None, max_length=255)


class PortfolioCorporateActionCreateRequest(BaseModel):
    account_id: int
    symbol: str = Field(..., min_length=1, max_length=16)
    effective_date: date
    action_type: Literal["cash_dividend", "split_adjustment"]
    market: Optional[Literal["cn", "hk", "us"]] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=8)
    cash_dividend_per_share: Optional[PortfolioTransportDecimal] = Field(None, ge=0)
    split_ratio: Optional[PortfolioTransportDecimal] = Field(None, gt=0)
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
    quantity: PortfolioTransportDecimal
    price: PortfolioTransportDecimal
    fee: PortfolioTransportDecimal
    tax: PortfolioTransportDecimal
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
    amount: PortfolioTransportDecimal
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
    cash_dividend_per_share: Optional[PortfolioTransportDecimal] = None
    split_ratio: Optional[PortfolioTransportDecimal] = None
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
    quantity: Decimal
    avg_cost: Decimal
    total_cost: Decimal
    last_price: Decimal
    price_source: Optional[str] = None
    price_source_label: Optional[str] = None
    price_as_of: Optional[str] = None
    is_price_fallback: Optional[bool] = None
    price_fallback_reason: Optional[str] = None
    valuation_confidence: Optional[float] = None
    market_value_base: Optional[PortfolioTransportDecimal] = None
    unrealized_pnl_base: Optional[PortfolioTransportDecimal] = None
    valuation_currency: str
    cost_basis_native: Optional[Decimal] = None
    market_value_native: Optional[Decimal] = None
    unrealized_pnl_native: Optional[Decimal] = None
    unrealized_pnl_pct: Optional[float] = None
    display_market_value: Optional[Decimal] = None
    display_unrealized_pnl: Optional[Decimal] = None
    display_currency: Optional[str] = None
    display_fx_status: Optional[Literal["live", "stale", "unavailable"]] = None
    valuation_status: Optional[Literal["available", "stale", "unavailable"]] = None
    valuation_unavailable_reason: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _validate_contextual_decimals(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        market = payload.get("market")
        currency = payload.get("currency")
        valuation_currency = payload.get("valuation_currency")
        display_currency = payload.get("display_currency")
        for field_name in ("quantity",):
            if payload.get(field_name) is not None:
                payload[field_name] = parse_portfolio_decimal(payload[field_name], kind="quantity", market=market)
        for field_name in ("avg_cost", "last_price"):
            if payload.get(field_name) is not None:
                payload[field_name] = parse_portfolio_decimal(payload[field_name], kind="price", market=market)
        for field_name in ("total_cost", "cost_basis_native", "market_value_native", "unrealized_pnl_native"):
            if payload.get(field_name) is not None:
                payload[field_name] = parse_portfolio_decimal(payload[field_name], kind="money", currency=currency)
        for field_name in ("market_value_base", "unrealized_pnl_base"):
            if payload.get(field_name) is not None:
                payload[field_name] = parse_portfolio_decimal(
                    payload[field_name], kind="money", currency=valuation_currency
                )
        for field_name in ("display_market_value", "display_unrealized_pnl"):
            if payload.get(field_name) is not None:
                payload[field_name] = parse_portfolio_decimal(
                    payload[field_name], kind="money", currency=display_currency
                )
        return payload


class PortfolioAccountSnapshot(BaseModel):
    account_id: int
    account_name: str
    owner_id: Optional[str] = None
    broker: Optional[str] = None
    market: str
    base_currency: str
    as_of: str
    cost_method: str
    total_cash: Optional[PortfolioTransportDecimal] = None
    total_market_value: Optional[PortfolioTransportDecimal] = None
    total_equity: Optional[PortfolioTransportDecimal] = None
    realized_pnl: Optional[PortfolioTransportDecimal] = None
    unrealized_pnl: Optional[PortfolioTransportDecimal] = None
    fee_total: Optional[PortfolioTransportDecimal] = None
    tax_total: Optional[PortfolioTransportDecimal] = None
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
    valuation_lineage: Optional[Dict[str, Any]] = None
    positions: List[PortfolioPositionItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _validate_base_money(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        for field_name in (
            "total_cash",
            "total_market_value",
            "total_equity",
            "realized_pnl",
            "unrealized_pnl",
            "fee_total",
            "tax_total",
        ):
            if payload.get(field_name) is not None:
                payload[field_name] = parse_portfolio_decimal(
                    payload[field_name], kind="money", currency=payload.get("base_currency")
                )
        return payload


class PortfolioMarketBreakdownItem(BaseModel):
    market: str
    position_count: int
    total_market_value: Optional[PortfolioTransportDecimal] = None
    weight_pct: Optional[float] = None


class PortfolioFxRateItem(BaseModel):
    from_currency: str
    to_currency: str
    rate: Optional[Decimal] = None
    rate_date: Optional[str] = None
    source: str
    is_stale: bool
    updated_at: Optional[str] = None
    source_direction: str

    @model_validator(mode="before")
    @classmethod
    def _validate_rate(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if payload.get("rate") is not None:
            payload["rate"] = parse_portfolio_decimal(
                payload["rate"],
                kind="fx_rate",
                from_currency=payload.get("from_currency"),
                to_currency=payload.get("to_currency"),
            )
        return payload


class PortfolioPnlMetric(BaseModel):
    amount: Optional[PortfolioTransportDecimal] = None
    amount_display: Optional[str] = None
    percent: Optional[float] = None
    currency: str
    fx_status: Literal["live", "stale", "unavailable"] = "live"

    @model_validator(mode="before")
    @classmethod
    def _validate_money(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if payload.get("amount") is not None:
            payload["amount"] = parse_portfolio_decimal(
                payload["amount"], kind="money", currency=payload.get("currency")
            )
        return payload


class PortfolioPnlSummary(BaseModel):
    display_currency: str
    realized: PortfolioPnlMetric
    unrealized: PortfolioPnlMetric
    total: PortfolioPnlMetric


class PortfolioExposureItem(BaseModel):
    key: str
    label: str
    market_value: Optional[PortfolioTransportDecimal] = None
    display_value: Optional[PortfolioTransportDecimal] = None
    display_currency: str
    percent: Optional[float] = None
    fx_status: Literal["live", "stale", "unavailable"] = "live"
    native_value: Optional[Decimal] = None
    native_currency: Optional[str] = None
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    base_currency: Optional[str] = None
    currency: Optional[str] = None
    market: Optional[str] = None
    symbol: Optional[str] = None
    sector: Optional[str] = None
    holding_count: Optional[int] = None
    unrealized_pnl: Optional[Decimal] = None
    unrealized_pnl_pct: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def _validate_money(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        for field_name in ("market_value", "display_value", "unrealized_pnl"):
            if payload.get(field_name) is not None:
                payload[field_name] = parse_portfolio_decimal(
                    payload[field_name], kind="money", currency=payload.get("display_currency")
                )
        if payload.get("native_value") is not None:
            payload["native_value"] = parse_portfolio_decimal(
                payload["native_value"], kind="money", currency=payload.get("native_currency")
            )
        return payload


class PortfolioExposureSummary(BaseModel):
    by_account: List[PortfolioExposureItem] = Field(default_factory=list)
    by_currency: List[PortfolioExposureItem] = Field(default_factory=list)
    by_market: List[PortfolioExposureItem] = Field(default_factory=list)
    by_symbol: List[PortfolioExposureItem] = Field(default_factory=list)
    by_sector: List[PortfolioExposureItem] = Field(default_factory=list)
    sector_status: Literal["available", "unavailable"] = "unavailable"


class PortfolioRiskSummary(BaseModel):
    largest_position: Optional[PortfolioExposureItem] = None
    largest_currency: Optional[PortfolioExposureItem] = None
    largest_market: Optional[PortfolioExposureItem] = None
    holding_count: int = 0
    account_count: int = 0
    cash_percent: Optional[float] = None
    fx_unavailable: bool = False
    warnings: List[str] = Field(default_factory=list)


class PortfolioAnalyticsSummary(BaseModel):
    pnl: PortfolioPnlSummary
    exposure: PortfolioExposureSummary
    risk: PortfolioRiskSummary


PortfolioRiskExposureReadinessState = Literal[
    "available",
    "missing",
    "stale",
    "not_configured",
    "broker_disabled",
    "manual_only",
]


class PortfolioRiskExposureReadinessItem(BaseModel):
    state: PortfolioRiskExposureReadinessState
    reason: str
    blockers: List[str] = Field(default_factory=list)
    asOf: Optional[str] = None


class PortfolioRiskExposureReadinessCategories(BaseModel):
    sectorExposure: PortfolioRiskExposureReadinessItem
    singleNameConcentration: PortfolioRiskExposureReadinessItem
    currencyExposure: PortfolioRiskExposureReadinessItem
    factorStyleExposure: PortfolioRiskExposureReadinessItem
    liquidityVolatilityExposure: PortfolioRiskExposureReadinessItem
    benchmarkComparison: PortfolioRiskExposureReadinessItem


class PortfolioRiskExposureReadiness(BaseModel):
    contractVersion: Literal["portfolio_risk_exposure_readiness_v1"] = "portfolio_risk_exposure_readiness_v1"
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False
    noAdviceDisclosure: str
    freshnessStatus: str
    holdings: PortfolioRiskExposureReadinessItem
    exposureCategories: PortfolioRiskExposureReadinessCategories
    benchmarkAvailability: PortfolioRiskExposureReadinessItem
    blockers: List[str] = Field(default_factory=list)


class PortfolioSnapshotResponse(BaseModel):
    schemaVersion: Literal["portfolio_snapshot_consumer_v1"] = "portfolio_snapshot_consumer_v1"
    noAdviceDisclosure: str = "Observation-only portfolio research context; not personalized financial advice and not an instruction."
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False
    consumerIssues: List[Dict[str, str]] = Field(default_factory=list)
    evidenceGaps: List[str] = Field(default_factory=list)
    degradedInputs: List[Dict[str, str]] = Field(default_factory=list)
    exposureResearchContext: Optional[Dict[str, Any]] = None
    riskExposureReadiness: Optional[PortfolioRiskExposureReadiness] = None
    dataQuality: Dict[str, Any] = Field(default_factory=dict)
    freshnessStatus: Optional[
        Literal[
            "no_account",
            "no_positions",
            "data_unavailable",
            "provider_unavailable",
            "calculation_unavailable",
            "stale_or_cached",
            "ready",
            "unknown",
        ]
    ] = None
    as_of: str
    cost_method: str
    currency: str
    account_count: int
    total_cash: Optional[PortfolioTransportDecimal] = None
    total_market_value: Optional[PortfolioTransportDecimal] = None
    total_equity: Optional[PortfolioTransportDecimal] = None
    realized_pnl: Optional[PortfolioTransportDecimal] = None
    unrealized_pnl: Optional[PortfolioTransportDecimal] = None
    fee_total: Optional[PortfolioTransportDecimal] = None
    tax_total: Optional[PortfolioTransportDecimal] = None
    fx_stale: bool
    portfolio_truth: PortfolioTruth
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
    price_lineage: Optional[Dict[str, Any]] = None
    fx_lineage: Optional[Dict[str, Any]] = None
    valuation_snapshot_lineage: Optional[Dict[str, Any]] = None
    valuation_lineage: Optional[Dict[str, Any]] = None
    analytics_readiness: Optional[Dict[str, Any]] = None
    holdingsLineageState: Optional[str] = None
    cashLedgerCompletenessState: Optional[str] = None
    benchmarkMappingState: Optional[str] = None
    factorMappingState: Optional[str] = None
    confidenceCap: Optional[Dict[str, Any]] = None
    accounts: List[PortfolioAccountSnapshot] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _validate_aggregate_money(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        for field_name in (
            "total_cash",
            "total_market_value",
            "total_equity",
            "realized_pnl",
            "unrealized_pnl",
            "fee_total",
            "tax_total",
        ):
            if payload.get(field_name) is not None:
                payload[field_name] = parse_portfolio_decimal(
                    payload[field_name], kind="money", currency=payload.get("currency")
                )
        portfolio_truth = payload.get("portfolio_truth")
        if isinstance(portfolio_truth, dict) and portfolio_truth.get("value_semantics") != "authoritative_total":
            for field_name in (
                "total_cash",
                "total_market_value",
                "total_equity",
                "realized_pnl",
                "unrealized_pnl",
                "fee_total",
                "tax_total",
            ):
                payload[field_name] = None

        accounts = payload.get("accounts")
        if isinstance(accounts, list):
            projected_accounts = []
            for account in accounts:
                if not isinstance(account, dict):
                    projected_accounts.append(account)
                    continue
                account_payload = dict(account)
                availability = account_payload.get("availability")
                availability = availability if isinstance(availability, dict) else {}
                valuation = account_payload.get("valuation")
                valuation = valuation if isinstance(valuation, dict) else {}
                valuation_state = valuation.get("state")
                if valuation_state is None and isinstance(availability.get("valuation"), dict):
                    valuation_state = availability["valuation"].get("state")
                if valuation_state is not None and str(valuation_state).lower() != "available":
                    for field_name in ("total_cash", "total_market_value", "total_equity"):
                        account_payload[field_name] = None

                performance = account_payload.get("performance")
                performance = performance if isinstance(performance, dict) else {}
                performance_state = performance.get("calculation_state")
                if performance_state is None and isinstance(availability.get("performance"), dict):
                    performance_state = availability["performance"].get("calculation_state")
                if performance_state is not None and str(performance_state).lower() != "available":
                    for field_name in ("realized_pnl", "unrealized_pnl", "fee_total", "tax_total"):
                        account_payload[field_name] = None
                projected_accounts.append(account_payload)
            payload["accounts"] = projected_accounts

        market_breakdown = payload.get("market_breakdown")
        if isinstance(market_breakdown, list):
            payload["market_breakdown"] = [
                {
                    **item,
                    "total_market_value": parse_portfolio_decimal(
                        item["total_market_value"], kind="money", currency=payload.get("currency")
                    ),
                }
                if isinstance(item, dict) and item.get("total_market_value") is not None
                else item
                for item in market_breakdown
            ]
        portfolio_truth = payload.get("portfolio_truth")
        if isinstance(portfolio_truth, dict):
            payload["portfolio_truth"] = {
                **portfolio_truth,
                **{
                    field_name: parse_portfolio_decimal(
                        portfolio_truth[field_name], kind="money", currency=payload.get("currency")
                    )
                    for field_name in ("authoritative_total", "covered_subtotal")
                    if portfolio_truth.get(field_name) is not None
                },
            }
        return payload


class PortfolioHistorySnapshotItem(BaseModel):
    account_id: int
    snapshot_date: str
    cost_method: str
    base_currency: str
    total_cash: Optional[PortfolioTransportDecimal] = None
    total_market_value: Optional[PortfolioTransportDecimal] = None
    total_equity: Optional[PortfolioTransportDecimal] = None
    realized_pnl: Optional[PortfolioTransportDecimal] = None
    unrealized_pnl: Optional[PortfolioTransportDecimal] = None
    fee_total: Optional[PortfolioTransportDecimal] = None
    tax_total: Optional[PortfolioTransportDecimal] = None
    fx_stale: bool
    valuation_lineage: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _validate_base_money(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        for field_name in (
            "total_cash",
            "total_market_value",
            "total_equity",
            "realized_pnl",
            "unrealized_pnl",
            "fee_total",
            "tax_total",
        ):
            if payload.get(field_name) is not None:
                payload[field_name] = parse_portfolio_decimal(
                    payload[field_name], kind="money", currency=payload.get("base_currency")
                )
        return payload


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


class PortfolioStructureReviewExposureItem(BaseModel):
    key: str
    label: str
    marketValue: str = Field(..., pattern=_PORTFOLIO_DECIMAL_TEXT_PATTERN)
    displayCurrency: str = Field(..., min_length=3, max_length=8)
    percent: float
    holdingCount: int = Field(..., ge=0)

    @model_validator(mode="before")
    @classmethod
    def _validate_exact_market_value(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        market_value = payload.get("marketValue")
        display_currency = payload.get("displayCurrency")
        if not isinstance(market_value, str):
            raise ValueError("structure review exposure market value must be an exact decimal string")
        if not isinstance(display_currency, str) or not display_currency.strip():
            raise ValueError("structure review exposure requires display currency")
        currency = display_currency.strip().upper()
        payload["marketValue"] = serialize_portfolio_decimal_value(
            market_value,
            kind="money",
            currency=currency,
        )
        payload["displayCurrency"] = currency
        return payload


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
    exposureByThemeOrSector: List[PortfolioStructureReviewExposureItem] = Field(default_factory=list)
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
    quantity: PortfolioTransportDecimal
    price: PortfolioTransportDecimal
    fee: PortfolioTransportDecimal
    tax: PortfolioTransportDecimal
    trade_uid: Optional[str] = None
    dedup_hash: str
    market: Optional[str] = None
    currency: Optional[str] = None
    note: Optional[str] = None


class PortfolioImportCashEntryItem(BaseModel):
    event_date: str
    direction: Literal["in", "out"]
    amount: PortfolioTransportDecimal
    currency: str
    note: Optional[str] = None


class PortfolioImportCorporateActionItem(BaseModel):
    effective_date: str
    symbol: str
    market: str
    currency: str
    action_type: Literal["cash_dividend", "split_adjustment"]
    cash_dividend_per_share: Optional[PortfolioTransportDecimal] = None
    split_ratio: Optional[PortfolioTransportDecimal] = None
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
    accepted_count: int = 0
    rejected_count: int = 0
    preview_only: bool = False
    requires_confirmation: bool = False
    duplicate_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    unknown_symbols: List[Dict[str, Any]] = Field(default_factory=list)
    currency_issues: List[Dict[str, Any]] = Field(default_factory=list)
    account_mapping: Dict[str, Any] = Field(default_factory=dict)
    validation_checks: List[Dict[str, Any]] = Field(default_factory=list)
    recovery_actions: List[str] = Field(default_factory=list)


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
    rate: Decimal
    provider: str
    fetched_at: str
    cache_hit: bool
    stale: bool
    error: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _validate_rate(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if payload.get("rate") is not None:
            payload["rate"] = parse_portfolio_decimal(
                payload["rate"],
                kind="fx_rate",
                from_currency=payload.get("base_currency"),
                to_currency=payload.get("quote_currency"),
            )
        return payload


class PortfolioRiskResponse(BaseModel):
    schemaVersion: Literal["portfolio_risk_consumer_v1"] = "portfolio_risk_consumer_v1"
    noAdviceDisclosure: str = "Observation-only portfolio research context; not personalized financial advice and not an instruction."
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False
    consumerIssues: List[Dict[str, str]] = Field(default_factory=list)
    evidenceGaps: List[str] = Field(default_factory=list)
    degradedInputs: List[Dict[str, str]] = Field(default_factory=list)
    exposureResearchContext: Optional[Dict[str, Any]] = None
    riskExposureReadiness: Optional[PortfolioRiskExposureReadiness] = None
    dataQuality: Dict[str, Any] = Field(default_factory=dict)
    freshnessStatus: Optional[
        Literal[
            "no_account",
            "no_positions",
            "data_unavailable",
            "provider_unavailable",
            "calculation_unavailable",
            "stale_or_cached",
            "ready",
            "unknown",
        ]
    ] = None
    as_of: str
    account_id: Optional[int] = None
    cost_method: str
    currency: str
    portfolio_truth: PortfolioTruth
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


class PortfolioScenarioRiskPositionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: Optional[str] = Field(None, min_length=1, max_length=64)
    weight: Optional[PortfolioTransportDecimal] = None
    weightPct: Optional[PortfolioTransportDecimal] = None
    marketValueBase: Optional[PortfolioTransportDecimal] = Field(
        None,
        validation_alias=AliasChoices("marketValueBase", "market_value_base"),
    )
    baseCurrency: Optional[str] = Field(
        None,
        min_length=3,
        max_length=8,
        validation_alias=AliasChoices("baseCurrency", "base_currency"),
    )
    bucket: Optional[str] = None
    bucketLabel: Optional[str] = None
    theme: Optional[str] = None
    factor: Optional[str] = None


class PortfolioScenarioRiskInputError(ValueError):
    """Raised when the caller-supplied scenario money context is incomplete."""


class PortfolioScenarioRiskRequest(BaseModel):
    asOf: str = Field(..., min_length=1)
    baseCurrency: str = Field(..., min_length=3, max_length=8)
    positions: List[PortfolioScenarioRiskPositionRequest] | PortfolioScenarioRiskPositionRequest
    exposures: List[Dict[str, Any]] | Dict[str, Any]
    scenarioShocks: List[Dict[str, Any]] | Dict[str, Any]

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_position_mapping(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        positions = payload.get("positions")
        if not isinstance(positions, dict):
            return payload
        if any(
            key in positions
            for key in (
                "symbol",
                "weight",
                "weightPct",
                "marketValueBase",
                "market_value_base",
                "baseCurrency",
                "base_currency",
            )
        ):
            return payload
        payload["positions"] = [
            ({**item, "symbol": symbol} if isinstance(item, dict) else {"symbol": symbol, "weight": item})
            for symbol, item in positions.items()
        ]
        return payload

    def validate_position_money_currency(self) -> None:
        positions = self.positions if isinstance(self.positions, list) else [self.positions]
        for position in positions:
            if position.marketValueBase is None:
                continue
            row_currency = position.baseCurrency.strip().upper() if position.baseCurrency else ""
            if not row_currency:
                raise PortfolioScenarioRiskInputError("marketValueBase requires baseCurrency")
            if row_currency != self.baseCurrency.strip().upper():
                raise PortfolioScenarioRiskInputError(
                    "marketValueBase baseCurrency must match request baseCurrency"
                )
            parse_portfolio_decimal(position.marketValueBase, kind="money", currency=row_currency)


class PortfolioScenarioRiskResponse(BaseModel):
    readModelType: str
    advisoryOnly: bool
    accountingMutation: bool = False
    brokerIntegration: bool = False
    tradeExecution: bool = False
    executionReadiness: str
    asOf: Optional[str] = None
    baseCurrency: str
    coverage: Dict[str, Any] = Field(default_factory=dict)
    scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    insufficientDataReasons: List[str] = Field(default_factory=list)
    missingDataWarnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_serializer("coverage", "scenarios", "metadata", when_used="json")
    def _serialize_dynamic_decimal_fields(self, value: Any) -> Any:
        return _serialize_portfolio_decimal_tree(value)
