# -*- coding: utf-8 -*-
"""Contract tests for the pure symbol normalization boundary."""

from __future__ import annotations

import pytest

from data_provider.base import (
    canonical_stock_code as provider_canonical_stock_code,
)
from data_provider.base import (
    normalize_stock_code as provider_normalize_stock_code,
)
from data_provider.akshare_fetcher import is_hk_stock_code
from src.utils.symbol_normalization import (
    canonical_symbol_storage_values,
    is_us_index_code,
    is_us_stock_code,
    canonical_stock_code,
    normalize_stock_code,
    parse_canonical_symbol,
)


def test_canonical_identity_preserves_cn_venue_and_asset_type() -> None:
    sh = parse_canonical_symbol("600519.SH")
    sz = parse_canonical_symbol("000858.SZ")
    bj = parse_canonical_symbol("920748.BJ")

    assert sh is not None
    assert (sh.symbol, sh.market, sh.venue, sh.asset_type, sh.ambiguous) == (
        "600519",
        "cn",
        "XSHG",
        "stock",
        False,
    )
    assert sz is not None
    assert (sz.symbol, sz.market, sz.venue, sz.asset_type) == ("000858", "cn", "XSHE", "stock")
    assert bj is not None
    assert (bj.symbol, bj.market, bj.venue, bj.asset_type) == ("920748", "cn", "XBSE", "stock")
    assert parse_canonical_symbol("600519.BJ") is None


def test_explicit_cn_identity_has_venue_bearing_transport_spelling() -> None:
    assert parse_canonical_symbol("000001.SH").transport_symbol == "000001.SH"
    assert parse_canonical_symbol("SZ000001").transport_symbol == "000001.SZ"
    assert parse_canonical_symbol("600519").transport_symbol == "600519"


def test_cn_index_requires_explicit_identity_when_bare_code_is_ambiguous() -> None:
    explicit = parse_canonical_symbol("sh000300")
    bare = parse_canonical_symbol("000300")

    assert explicit is not None
    assert (explicit.symbol, explicit.market, explicit.venue, explicit.asset_type, explicit.ambiguous) == (
        "000300",
        "cn",
        "XSHG",
        "index",
        False,
    )
    assert bare is not None
    assert bare.ambiguous is True
    assert bare.market == "cn"
    assert bare.asset_type is None
    assert bare.venue is None


def test_us_index_and_equity_identities_remain_distinct() -> None:
    stock = parse_canonical_symbol("AAPL")
    index = parse_canonical_symbol("SPX")

    assert stock is not None and index is not None
    assert stock.asset_type == "stock"
    assert index.asset_type == "index"
    assert stock.venue == "UNRESOLVED"
    assert index.venue == "UNRESOLVED"


def test_us_provider_suffix_is_not_a_listing_venue_or_generic_dot_rewrite() -> None:
    aapl = parse_canonical_symbol("AAPL")
    aapl_us = parse_canonical_symbol("AAPL.US")
    brk_b = parse_canonical_symbol("BRK.B")
    nvda = parse_canonical_symbol("NVDA")
    spx = parse_canonical_symbol("SPX")
    ndx = parse_canonical_symbol("NDX")

    assert all(identity is not None for identity in (aapl, aapl_us, brk_b, nvda, spx, ndx))
    assert aapl_us.symbol == aapl.symbol == "AAPL"
    assert aapl_us.identity_key == aapl.identity_key
    assert brk_b.symbol == "BRK.B"
    assert {identity.venue for identity in (aapl, aapl_us, brk_b, nvda, spx, ndx)} == {"UNRESOLVED"}
    assert canonical_stock_code("AAPL.US") == "AAPL"
    assert canonical_stock_code("BRK.B") == "BRK.B"
    assert is_us_index_code("SPX.US") is True
    assert is_us_index_code("NDX.US") is True
    assert is_us_stock_code("SPX.US") is False
    assert is_us_stock_code("NDX.US") is False


def test_provider_normalization_exports_delegate_to_pure_utils() -> None:
    assert provider_normalize_stock_code is normalize_stock_code
    assert provider_canonical_stock_code is canonical_stock_code
    assert parse_canonical_symbol("0700") is None
    assert parse_canonical_symbol("0700", market="hk").symbol == "HK00700"
    assert parse_canonical_symbol("1234", market="hk").symbol == "HK01234"
    assert canonical_symbol_storage_values("HK00700", market="hk") == (
        "HK00700",
        "HK700",
        "HK0700",
        "700",
        "00700",
        "700.HK",
        "0700.HK",
        "00700.HK",
    )
    assert canonical_symbol_storage_values("00700", market="hk") == (
        "HK00700",
        "HK700",
        "HK0700",
        "700",
        "00700",
        "700.HK",
        "0700.HK",
        "00700.HK",
    )
    assert canonical_symbol_storage_values("600519", market="cn") == (
        "600519",
        "SH600519",
        "SS600519",
        "600519.SH",
        "600519.SS",
    )
    assert canonical_symbol_storage_values("000001.SZ", market="cn") == (
        "000001",
        "SZ000001",
        "000001.SZ",
    )
    assert canonical_symbol_storage_values("000001.SH", market="cn") == (
        "000001",
        "SH000001",
        "SS000001",
        "000001.SH",
        "000001.SS",
    )
    assert canonical_symbol_storage_values(
        "000300",
        market="cn",
        venue="XSHG",
        asset_type="index",
    ) == (
        "000300",
        "SH000300",
        "SS000300",
        "000300.SH",
        "000300.SS",
    )
    assert canonical_symbol_storage_values("00700") == ()
    assert canonical_symbol_storage_values("HK00700", market="cn") == ()
    assert is_hk_stock_code("0700.HK") is True
    assert is_hk_stock_code("00700") is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("600519", "600519"),
        (" SH600519 ", "600519"),
        ("000001.SZ", "000001"),
        ("600000.SS", "600000"),
        ("BJ920748", "920748"),
        ("920748.BJ", "920748"),
        ("HK00700", "HK00700"),
        ("hk700", "HK00700"),
        ("1810.HK", "HK01810"),
        ("AAPL", "AAPL"),
        ("brk.b", "brk.b"),
        ("", ""),
    ],
)
def test_normalize_stock_code_matches_provider_runtime_semantics(
    raw: str,
    expected: str,
) -> None:
    assert normalize_stock_code(raw) == expected
    assert normalize_stock_code(raw) == provider_normalize_stock_code(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("aapl", "AAPL"),
        (" 600519 ", "600519"),
        ("hk00700", "HK00700"),
        ("0700.HK", "HK00700"),
        ("", ""),
        (None, ""),
    ],
)
def test_canonical_stock_code_matches_provider_runtime_semantics(
    raw: str | None,
    expected: str,
) -> None:
    assert canonical_stock_code(raw) == expected
    assert canonical_stock_code(raw) == provider_canonical_stock_code(raw)
