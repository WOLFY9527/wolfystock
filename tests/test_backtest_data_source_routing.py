# -*- coding: utf-8 -*-
"""Focused contracts for backtest data-source routing eligibility."""

from __future__ import annotations

import pytest

from src.services.backtest_data_source_guard import assess_backtest_data_source_eligibility


@pytest.mark.parametrize("source", ["", "   ", None])
def test_blank_or_missing_source_is_degraded_fill_only_unknown_authority(source: str | None) -> None:
    result = assess_backtest_data_source_eligibility(code="AAPL", source=source)

    assert result.authority_status == "degraded_fill_only"
    assert result.authority_allowed is False
    assert result.degraded_fill_only is True
    assert result.rejected is False
    assert result.source_type == "missing"
    assert result.reason_codes == ("source_authority_unknown",)


def test_unknown_source_is_degraded_fill_only_unknown_authority() -> None:
    result = assess_backtest_data_source_eligibility(code="AAPL", source="unknown")

    assert result.source == "unknown"
    assert result.authority_status == "degraded_fill_only"
    assert result.authority_allowed is False
    assert result.degraded_fill_only is True
    assert result.rejected is False
    assert result.source_type == "missing"
    assert result.reason_codes == ("source_authority_unknown",)


@pytest.mark.parametrize(
    "source",
    [
        "local_us_parquet",
        "local_us_parquet_dir",
        "local_db",
        "local_db_hk_history",
        "local_db_us_history",
        "cache",
        "cached",
        "snapshot",
        "database_cache",
    ],
)
def test_explicit_local_and_cache_sources_remain_allowed_for_backtest_authority(source: str) -> None:
    result = assess_backtest_data_source_eligibility(code="AAPL", source=source)

    assert result.authority_status == "allowed"
    assert result.authority_allowed is True
    assert result.degraded_fill_only is False
    assert result.rejected is False
    assert result.source_type == "cache_snapshot"
    assert result.reason_codes == ()


def test_local_stored_ohlcv_route_is_allowed_for_backtest_authority() -> None:
    result = assess_backtest_data_source_eligibility(code="AAPL", source="local_us_parquet")

    assert result.request.market == "US"
    assert result.request.asset_type == "equity"
    assert result.request.use_case == "backtest"
    assert result.request.capability == "ohlcv"
    assert result.request.allow_network is False
    assert result.request.reproducibility_required is True
    assert result.authority_status == "allowed"
    assert result.authority_allowed is True
    assert result.degraded_fill_only is False
    assert result.rejected is False
    assert result.source_type == "cache_snapshot"
    assert "local_cache" in {candidate.provider_id for candidate in result.plan.primary_candidates}
    assert "local_ohlcv" in {candidate.provider_id for candidate in result.plan.primary_candidates}


def test_sec_edgar_is_rejected_for_ohlcv_backtest_authority() -> None:
    result = assess_backtest_data_source_eligibility(code="AAPL", source="sec_edgar")

    assert result.authority_status == "rejected"
    assert result.authority_allowed is False
    assert result.rejected is True
    assert "provider_forbidden_for_use_case" in result.reason_codes
    assert "provider_observation_only" in result.reason_codes
    assert "score_inputs" in result.reason_codes


def test_coinbase_public_is_rejected_for_ohlcv_backtest_authority() -> None:
    result = assess_backtest_data_source_eligibility(code="BTC-USD", source="coinbase_public")

    assert result.request.market == "crypto"
    assert result.request.capability == "ohlcv"
    assert result.authority_status == "rejected"
    assert result.authority_allowed is False
    assert "provider_forbidden_for_use_case" in result.reason_codes
    assert "provider_observation_only" in result.reason_codes


def test_baostock_observation_only_cn_history_is_rejected_as_metric_authority() -> None:
    result = assess_backtest_data_source_eligibility(code="600519", source="baostock")

    assert result.request.market == "CN"
    assert result.request.capability == "cn_history_daily"
    assert result.authority_status == "rejected"
    assert result.authority_allowed is False
    assert "provider_forbidden_for_use_case" in result.reason_codes
    assert "provider_observation_only" in result.reason_codes
    assert "scoring_not_allowed" in result.reason_codes


def test_yfinance_proxy_is_degraded_fill_only_not_reproducible_authority() -> None:
    result = assess_backtest_data_source_eligibility(code="AAPL", source="yfinance")

    assert result.authority_status == "degraded_fill_only"
    assert result.authority_allowed is False
    assert result.degraded_fill_only is True
    assert result.rejected is False
    assert result.source_type == "unofficial_proxy"
    assert "proxy_source_not_reproducible" in result.reason_codes
