# -*- coding: utf-8 -*-
"""Pure contract tests for the leveraged ETF mapper service."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.services.leveraged_etf_mapper_service import (
    LeveragedEtfMapperInputError,
    LeveragedEtfMapperService,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = REPO_ROOT / "src/services/leveraged_etf_mapper_service.py"


def test_list_mappings_exposes_curated_positive_leverage_contract() -> None:
    mappings = LeveragedEtfMapperService().list_mappings()

    mapping_by_symbol = {item["etfSymbol"]: item for item in mappings}
    assert set(mapping_by_symbol) == {"TSLL", "NVDL", "MSTU", "CONL", "TQQQ", "SOXL"}
    assert mapping_by_symbol["TSLL"]["underlyingSymbol"] == "TSLA"
    assert mapping_by_symbol["TSLL"]["leverage"] == 2.0
    assert mapping_by_symbol["TSLL"]["referenceType"] == "single_stock"
    assert mapping_by_symbol["TQQQ"]["underlyingSymbol"] == "QQQ"
    assert mapping_by_symbol["TQQQ"]["leverage"] == 3.0
    assert mapping_by_symbol["TQQQ"]["referenceType"] == "proxy_etf"
    assert all(item["leverage"] > 0 for item in mappings)
    assert all(item["sourceLabel"] for item in mappings)


def test_forward_underlying_target_returns_etf_estimate() -> None:
    result = LeveragedEtfMapperService().calculate(
        etf_symbol="TSLL",
        underlying_symbol="TSLA",
        etf_ref_price=10.0,
        underlying_ref_price=100.0,
        underlying_target_price=110.0,
    )

    assert result["status"] == "ok"
    assert result["estimatedEtfPrice"] == pytest.approx(12.0)
    assert result["impliedUnderlyingPrice"] is None
    assert result["mapping"]["etfSymbol"] == "TSLL"
    assert result["mapping"]["underlyingSymbol"] == "TSLA"
    assert result["mapping"]["leverage"] == 2.0
    assert result["metadata"]["calculationOnly"] is True
    assert result["metadata"]["externalProviderCalls"] is False
    assert result["metadata"]["noOrderPlacement"] is True
    assert result["metadata"]["noPortfolioMutation"] is True
    assert result["metadata"]["notInvestmentAdvice"] is True


def test_reverse_etf_target_returns_implied_underlying() -> None:
    result = LeveragedEtfMapperService().calculate(
        etf_symbol="NVDL",
        underlying_symbol="NVDA",
        etf_ref_price=50.0,
        underlying_ref_price=100.0,
        etf_target_price=60.0,
    )

    assert result["status"] == "ok"
    assert result["estimatedEtfPrice"] is None
    assert result["impliedUnderlyingPrice"] == pytest.approx(110.0)


@pytest.mark.parametrize(
    "kwargs, code",
    [
        (
            {
                "etf_symbol": "TSLL",
                "underlying_symbol": "TSLA",
                "etf_ref_price": 0.0,
                "underlying_ref_price": 100.0,
                "underlying_target_price": 110.0,
            },
            "invalid_reference_price",
        ),
        (
            {
                "etf_symbol": "TSLL",
                "underlying_symbol": "TSLA",
                "etf_ref_price": 10.0,
                "underlying_ref_price": -1.0,
                "underlying_target_price": 110.0,
            },
            "invalid_reference_price",
        ),
        (
            {
                "etf_symbol": "TSLL",
                "underlying_symbol": "TSLA",
                "etf_ref_price": 10.0,
                "underlying_ref_price": 100.0,
            },
            "missing_target_input",
        ),
        (
            {
                "etf_symbol": "TSLL",
                "underlying_symbol": "NVDA",
                "etf_ref_price": 10.0,
                "underlying_ref_price": 100.0,
                "underlying_target_price": 110.0,
            },
            "unsupported_mapping_mismatch",
        ),
    ],
)
def test_invalid_inputs_fail_closed(kwargs: dict, code: str) -> None:
    with pytest.raises(LeveragedEtfMapperInputError) as exc_info:
        LeveragedEtfMapperService().calculate(**kwargs)

    assert exc_info.value.code == code


def test_extreme_non_positive_forward_output_returns_invalid_low_confidence() -> None:
    result = LeveragedEtfMapperService().calculate(
        etf_symbol="SOXL",
        underlying_symbol="SOXX",
        etf_ref_price=30.0,
        underlying_ref_price=100.0,
        underlying_target_price=60.0,
    )

    assert result["status"] == "invalid_low_confidence"
    assert result["estimatedEtfPrice"] is None
    assert result["invalidReason"] == "non_positive_estimated_etf_price"
    assert "non_positive_estimated_etf_price" in result["warningCodes"]


def test_limitations_and_warnings_are_always_present() -> None:
    result = LeveragedEtfMapperService().calculate(
        etf_symbol="CONL",
        underlying_symbol="COIN",
        etf_ref_price=20.0,
        underlying_ref_price=200.0,
        underlying_target_price=220.0,
    )

    assert {
        "same_day_reference_anchor_approximation",
        "daily_reset_path_dependency",
        "fees_financing_tracking_error_excluded",
        "overnight_multi_day_drift_not_modelled",
        "not_investment_advice",
        "no_order_placement",
        "no_portfolio_mutation",
    } <= set(result["limitationCodes"])
    warning_text = " ".join(result["warnings"]).lower()
    assert "same-day" in warning_text
    assert "daily reset" in warning_text
    assert "fees" in warning_text
    assert "overnight" in warning_text
    assert "not investment advice" in warning_text
    assert "order placement" in warning_text
    assert "portfolio mutation" in warning_text


def test_service_module_has_no_provider_cache_portfolio_or_trading_runtime_imports() -> None:
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden_prefixes = (
        "data_provider",
        "src.services.stock_service",
        "src.services.stock_service_provider_adapter",
        "src.services.market_cache",
        "src.services.portfolio_service",
        "src.services.market_scanner_service",
        "src.services.options",
        "src.services.backtest_service",
    )
    assert not [
        module
        for module in imported_modules
        if module == "MarketCache" or module.startswith(forbidden_prefixes)
    ]

    service_source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_runtime_tokens = (
        "get_realtime_quote",
        "get_daily_data",
        "MarketCache",
        "StockService",
        "DataFetcherManager",
        "PortfolioService",
        "place_order",
        "record_cash_ledger",
    )
    assert not [token for token in forbidden_runtime_tokens if token in service_source]
