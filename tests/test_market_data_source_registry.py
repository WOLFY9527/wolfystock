# -*- coding: utf-8 -*-
"""Tests for market data source provenance registry helpers."""

from __future__ import annotations

from src.services.market_data_source_registry import (
    CANONICAL_SOURCE_TYPES,
    project_source_provenance,
    resolve_freshness_label,
    resolve_source_label,
    resolve_source_type,
)


def test_binance_remains_exchange_public() -> None:
    provenance = project_source_provenance(source="binance", freshness="live")

    assert provenance["sourceType"] == "exchange_public"
    assert provenance["sourceLabel"] == "Binance"
    assert provenance["freshnessLabel"] == "实时"


def test_yfinance_proxy_remains_delayed_unofficial_proxy() -> None:
    provenance = project_source_provenance(
        source="yfinance_proxy",
        source_type="proxy_public",
        freshness="delayed",
    )

    assert provenance["sourceType"] == "unofficial_proxy"
    assert provenance["sourceLabel"] == "Yahoo Finance"
    assert provenance["freshnessLabel"] == "延迟"


def test_visible_panel_proxy_fixture_and_snapshot_classes_never_promote_to_strong_live_sources() -> None:
    strong_cases = {
        "binance": project_source_provenance(source="binance", freshness="live"),
        "frankfurter": project_source_provenance(
            source="fx_frankfurter_public",
            freshness="live",
        ),
    }
    soft_cases = {
        "breadth_proxy": project_source_provenance(
            source="yfinance_proxy",
            source_type="proxy_public",
            freshness="delayed",
        ),
        "fallback_flow": project_source_provenance(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
        ),
        "options_fixture": project_source_provenance(
            source="synthetic_fixture",
            freshness="synthetic_delayed",
        ),
        "portfolio_snapshot": project_source_provenance(
            source="ledger_snapshot",
            freshness="cached",
        ),
    }

    assert strong_cases["binance"]["sourceType"] == "exchange_public"
    assert strong_cases["frankfurter"]["sourceType"] == "official_public"
    assert soft_cases["breadth_proxy"]["sourceType"] == "unofficial_proxy"
    assert soft_cases["fallback_flow"]["sourceType"] == "fallback_static"
    assert soft_cases["options_fixture"]["sourceType"] == "synthetic_fixture"
    assert soft_cases["portfolio_snapshot"]["sourceType"] == "cache_snapshot"
    assert all(
        payload["sourceType"] not in {"exchange_public", "official_public"}
        for payload in soft_cases.values()
    )


def test_tickflow_explicit_public_provider_label_does_not_collapse_into_official_or_cache() -> None:
    provenance = project_source_provenance(
        source="tickflow",
        source_type="public_api",
        freshness="delayed",
    )

    assert provenance["sourceType"] == "public_proxy"
    assert provenance["sourceLabel"] == "TickFlow"
    assert provenance["freshnessLabel"] == "延迟"


def test_yfinance_proxy_with_cached_freshness_stays_proxy_when_not_snapshot_marked() -> None:
    provenance = project_source_provenance(
        source="yfinance_proxy",
        freshness="cached",
        no_external_calls=True,
    )

    assert provenance["sourceType"] == "unofficial_proxy"
    assert provenance["sourceLabel"] == "Yahoo Finance"
    assert provenance["freshnessLabel"] == "缓存"


def test_fallback_static_never_claims_live_freshness() -> None:
    provenance = project_source_provenance(
        source="fallback",
        freshness="live",
        is_fallback=True,
    )

    assert provenance["sourceType"] == "fallback_static"
    assert provenance["sourceLabel"] == "备用数据"
    assert provenance["freshnessLabel"] == "备用/缺失"


def test_cache_snapshot_is_distinguishable_from_live_provider_data() -> None:
    provenance = project_source_provenance(
        source="yfinance_proxy",
        freshness="cached",
        is_from_snapshot=True,
        no_external_calls=True,
    )

    assert provenance["sourceType"] == "cache_snapshot"
    assert provenance["sourceLabel"] == "缓存快照"
    assert provenance["freshnessLabel"] == "缓存快照"


def test_unknown_catch_all_public_aliases_do_not_promote_to_official_or_live() -> None:
    provenance = project_source_provenance(
        source="mystery_public_feed",
        source_type="public_api",
        freshness="live",
    )

    assert provenance["sourceType"] == "missing"
    assert provenance["sourceLabel"] == "未接入"
    assert provenance["freshnessLabel"] == "不可用"


def test_public_and_proxy_source_type_aliases_stay_conservative_across_contracts() -> None:
    from src.services.market_intelligence_trust_gate import (
        evaluate_market_intelligence_trust,
        resolve_market_intelligence_source_tier,
    )

    expected_registry_types = {
        "public_api": "public_proxy",
        "proxy_public": "public_proxy",
        "public_proxy": "public_proxy",
        "unofficial_proxy": "unofficial_proxy",
        "unofficial_public_api": "unofficial_proxy",
    }

    for source_type, expected_registry_type in expected_registry_types.items():
        provenance = project_source_provenance(source_type=source_type, freshness="live")
        tier = resolve_market_intelligence_source_tier(source_type=source_type, freshness="live")
        trust = evaluate_market_intelligence_trust(
            {"sourceType": source_type, "freshness": "live", "coverage": 1.0}
        )

        assert resolve_source_type(source_type=source_type) == expected_registry_type
        assert provenance["sourceType"] == expected_registry_type
        assert tier.value == "unofficial_public_api"
        assert trust["sourceTier"] == "unofficial_public_api"
        assert trust["sourceTier"] not in {"official_public", "exchange_public", "broker_authorized"}
        assert trust["scoreCap"] < 1.0


def test_missing_source_defaults_to_missing_labels() -> None:
    assert resolve_source_type(source=None, source_type=None) == "missing"
    assert resolve_source_label(source=None, source_type=None) == "未接入"
    assert resolve_freshness_label("unavailable") == "不可用"


def test_provider_fit_source_aliases_are_additive_and_truthful_for_new_audited_ids() -> None:
    expected = {
        "authorized.us_etf_flow": ("missing", "未接入"),
        "authorized.cn_hk_connect_flow": ("missing", "未接入"),
        "authorized.real_sector_theme_flow": ("missing", "未接入"),
        "exchange_or_broker_authorized.index_futures": ("missing", "未接入"),
        "official_public.fed_liquidity": ("missing", "未接入"),
        "official_public.cn_money_market_rates": ("missing", "未接入"),
        "official_or_authorized.fx_dxy": ("missing", "未接入"),
        "sec_edgar": ("official_public", "SEC EDGAR"),
        "pandas_datareader_fred": ("official_public", "FRED"),
        "pandas_datareader_oecd": ("official_public", "OECD"),
        "pandas_datareader_world_bank": ("official_public", "World Bank"),
        "treasury_existing_baseline": ("official_public", "US Treasury"),
        "binance_public": ("exchange_public", "Binance"),
        "coinbase_public": ("exchange_public", "Coinbase"),
        "finnhub": ("public_proxy", "Finnhub"),
        "marketstack": ("public_proxy", "Marketstack"),
        "official_or_authorized.us_market_breadth": ("missing", "未接入"),
        "tushare_pro": ("public_proxy", "Tushare Pro"),
        "yahooquery": ("unofficial_proxy", "Yahoo Finance"),
        "yfinance_current_baseline": ("unofficial_proxy", "Yahoo Finance"),
        "openbb_reference_only": ("public_proxy", "OpenBB"),
        "pytdx_existing_baseline": ("public_proxy", "pytdx / 通达信"),
        "akshare_existing_baseline": ("public_proxy", "AkShare"),
    }

    for source, (source_type, source_label) in expected.items():
        provenance = project_source_provenance(source=source, freshness="delayed")
        assert provenance["sourceType"] == source_type
        assert provenance["sourceLabel"] == source_label


def test_future_authorized_us_flow_and_breadth_provider_classes_do_not_project_as_live_authority() -> None:
    for source in (
        "authorized.us_etf_flow",
        "authorized.cn_hk_connect_flow",
        "authorized.real_sector_theme_flow",
        "exchange_or_broker_authorized.index_futures",
        "official_or_authorized.us_market_breadth",
        "official_or_authorized.fx_dxy",
        "official_public.fed_liquidity",
        "official_public.cn_money_market_rates",
    ):
        provenance = project_source_provenance(
            source=source,
            source_type="official_public",
            freshness="live",
        )

        assert provenance["sourceType"] == "missing"
        assert provenance["sourceLabel"] == "未接入"
        assert provenance["freshnessLabel"] == "不可用"


def test_scanner_local_sources_keep_specific_cache_labels() -> None:
    expected = {
        "local_universe_cache": ("cache_snapshot", "本地候选缓存"),
        "local_us_parquet_dir": ("cache_snapshot", "本地 Parquet 历史"),
        "local_db": ("cache_snapshot", "本地数据库历史"),
        "local_db_us_history": ("cache_snapshot", "本地数据库历史"),
        "local_db_hk_history": ("cache_snapshot", "本地数据库历史"),
    }

    for source, (source_type, source_label) in expected.items():
        assert resolve_source_type(source=source) == source_type
        assert resolve_source_label(source=source, source_type=source_type) == source_label


def test_scanner_seed_and_degraded_sources_keep_fallback_labels() -> None:
    expected = {
        "curated_us_liquid_seed": ("fallback_static", "精选美股种子池"),
        "curated_hk_liquid_seed": ("fallback_static", "精选港股种子池"),
        "builtin_stock_mapping": ("fallback_static", "内置股票映射"),
        "local_history_degraded": ("fallback_static", "本地历史降级快照"),
    }

    for source, (source_type, source_label) in expected.items():
        assert resolve_source_type(source=source) == source_type
        assert resolve_source_label(source=source, source_type=source_type) == source_label


def test_scanner_fetcher_and_manager_sources_keep_provider_labels() -> None:
    expected = {
        "TushareFetcher": ("official_public", "Tushare"),
        "AkshareFetcher": ("public_proxy", "AkShare"),
        "EfinanceFetcher": ("public_proxy", "Efinance"),
        "DataFetcherManager": ("public_proxy", "DataFetcherManager"),
    }

    for source, (source_type, source_label) in expected.items():
        assert resolve_source_type(source=source) == source_type
        assert resolve_source_label(source=source, source_type=source_type) == source_label


def test_tickflow_source_token_keeps_stable_non_official_provenance() -> None:
    provenance = project_source_provenance(
        source="tickflow",
        source_type="public_api",
        freshness="delayed",
    )

    assert provenance["sourceType"] == "public_proxy"
    assert provenance["sourceLabel"] == "TickFlow"
    assert provenance["freshnessLabel"] == "延迟"


def test_sina_and_proxy_cn_fetchers_remain_non_official_primary_sources() -> None:
    expected = {
        "sina": ("public_proxy", "新浪财经"),
        "AkshareFetcher": ("public_proxy", "AkShare"),
        "EfinanceFetcher": ("public_proxy", "Efinance"),
    }

    for source, (source_type, source_label) in expected.items():
        provenance = project_source_provenance(
            source=source,
            source_type="official_public",
            freshness="live",
        )

        assert provenance["sourceType"] == source_type
        assert provenance["sourceLabel"] == source_label


def test_options_lab_fixture_and_stub_sources_have_inert_provenance_labels() -> None:
    assert {
        "synthetic_fixture",
        "delayed_fixture",
        "malformed_fixture",
        "disabled_live_stub",
        "missing",
    }.issubset(CANONICAL_SOURCE_TYPES)

    synthetic = project_source_provenance(source="synthetic_fixture", freshness="synthetic_delayed")
    assert synthetic["sourceType"] == "synthetic_fixture"
    assert synthetic["sourceLabel"] == "Synthetic Fixture"
    assert synthetic["freshnessLabel"] != "实时"

    delayed = project_source_provenance(source="delayed_fixture", freshness="delayed")
    assert delayed["sourceType"] == "delayed_fixture"
    assert delayed["sourceLabel"] == "Delayed Fixture"
    assert delayed["freshnessLabel"] == "延迟"

    delayed_alias = project_source_provenance(source="real_shaped_delayed_fixture", freshness="delayed")
    assert delayed_alias["sourceType"] == "delayed_fixture"
    assert delayed_alias["sourceLabel"] == "Delayed Fixture"
    assert delayed_alias["freshnessLabel"] == "延迟"

    malformed = project_source_provenance(source="malformed_fixture", freshness="error")
    assert malformed["sourceType"] == "malformed_fixture"
    assert malformed["sourceLabel"] == "Malformed Fixture"
    assert malformed["freshnessLabel"] == "不可用"

    disabled_live_stub = project_source_provenance(source="disabled_live_stub", freshness="unavailable")
    assert disabled_live_stub["sourceType"] == "disabled_live_stub"
    assert disabled_live_stub["sourceLabel"] == "Disabled Live Stub"
    assert disabled_live_stub["freshnessLabel"] == "不可用"


def test_portfolio_risk_provenance_aliases_remain_inert_and_non_live() -> None:
    cases = {
        "ledger_snapshot": {
            "freshness": "cached",
            "expected": {
                "sourceType": "cache_snapshot",
                "sourceLabel": "缓存快照",
                "freshnessLabel": "缓存快照",
            },
        },
        "projection_cache": {
            "freshness": "cached",
            "expected": {
                "sourceType": "cache_snapshot",
                "sourceLabel": "缓存快照",
                "freshnessLabel": "缓存快照",
            },
        },
        "fx_frankfurter_public": {
            "freshness": "live",
            "expected": {
                "sourceType": "official_public",
                "sourceLabel": "Frankfurter",
                "freshnessLabel": "实时",
            },
        },
        "fx_fallback": {
            "freshness": "live",
            "expected": {
                "sourceType": "fallback_static",
                "sourceLabel": "备用数据",
                "freshnessLabel": "备用/缺失",
            },
        },
        "board_lookup_provider": {
            "freshness": "delayed",
            "expected": {
                "sourceType": "public_proxy",
                "sourceLabel": "Board Lookup Provider",
                "freshnessLabel": "延迟",
            },
        },
        "board_lookup_missing": {
            "freshness": "unavailable",
            "expected": {
                "sourceType": "missing",
                "sourceLabel": "未接入",
                "freshnessLabel": "不可用",
            },
        },
        "risk_diagnostics_sanitized": {
            "freshness": "cached",
            "expected": {
                "sourceType": "cache_snapshot",
                "sourceLabel": "缓存快照",
                "freshnessLabel": "缓存快照",
            },
        },
    }

    for source, case in cases.items():
        provenance = project_source_provenance(
            source=source,
            freshness=case["freshness"],
        )

        assert provenance == case["expected"]
