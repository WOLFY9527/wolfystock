# -*- coding: utf-8 -*-
"""Tests for market data source provenance registry helpers."""

from __future__ import annotations

import json
from typing import Any

from src.services.options_authority_policy_matrix import (
    build_options_event_calendar_source_candidate_gap,
    build_options_expiration_source_candidate_gap,
    build_options_iv_rank_source_candidate_gap,
)
from src.services.options_event_calendar_source_candidate_evidence import (
    build_event_calendar_source_candidate_evidence,
)
from src.services.options_expiration_source_candidate_evidence import (
    build_expiration_calendar_source_candidate_evidence,
)
from src.services.market_data_source_registry import (
    CANONICAL_SOURCE_TYPES,
    project_source_registry_metadata,
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
        "polygon_us_grouped_daily": ("authorized_licensed_feed", "Polygon grouped daily US equities"),
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


def test_valid_cn_money_market_cache_diagnostic_projects_as_official_public_without_live_promotion() -> None:
    valid_cache = project_source_provenance(
        source="official_public.cn_money_market_rates",
        source_type="official_public",
        source_label="Official CN Money Market Rates diagnostic cache",
        freshness="delayed",
        no_external_calls=True,
    )
    unqualified_live = project_source_provenance(
        source="official_public.cn_money_market_rates",
        source_type="official_public",
        freshness="live",
    )

    assert valid_cache["sourceType"] == "official_public"
    assert valid_cache["sourceLabel"] == "Official CN Money Market Rates diagnostic cache"
    assert valid_cache["freshnessLabel"] == "延迟"
    assert unqualified_live["sourceType"] == "missing"
    assert unqualified_live["sourceLabel"] == "未接入"


def test_valid_fed_liquidity_bundle_diagnostic_projects_as_official_public_without_live_promotion() -> None:
    valid_bundle = project_source_provenance(
        source="official_public.fed_liquidity",
        source_type="official_public",
        source_label="Official Fed Liquidity bundle",
        freshness="delayed",
        no_external_calls=True,
    )
    unqualified_live = project_source_provenance(
        source="official_public.fed_liquidity",
        source_type="official_public",
        freshness="live",
    )

    assert valid_bundle["sourceType"] == "official_public"
    assert valid_bundle["sourceLabel"] == "Official Fed Liquidity bundle"
    assert valid_bundle["freshnessLabel"] == "延迟"
    assert unqualified_live["sourceType"] == "missing"
    assert unqualified_live["sourceLabel"] == "未接入"


def test_index_futures_proxy_and_fallback_placeholders_stay_conservative_in_registry() -> None:
    proxy = project_source_provenance(
        source="yfinance_proxy",
        source_type="proxy_public",
        freshness="delayed",
    )
    fallback = project_source_provenance(
        source="fallback",
        freshness="fallback",
        is_fallback=True,
    )
    inert_authorized = project_source_provenance(
        source="exchange_or_broker_authorized.index_futures",
        source_type="official_public",
        freshness="delayed",
    )

    assert proxy["sourceType"] == "unofficial_proxy"
    assert proxy["sourceLabel"] == "Yahoo Finance"
    assert fallback["sourceType"] == "fallback_static"
    assert fallback["sourceLabel"] == "备用数据"
    assert inert_authorized["sourceType"] == "missing"
    assert inert_authorized["sourceLabel"] == "未接入"


def test_polygon_grouped_daily_is_authorized_vendor_feed_not_official_exchange_breadth() -> None:
    provenance = project_source_provenance(
        source="polygon_us_grouped_daily",
        freshness="delayed",
    )

    assert provenance["sourceType"] == "authorized_licensed_feed"
    assert provenance["sourceLabel"] == "Polygon grouped daily US equities"
    assert provenance["sourceType"] not in {"official_public", "exchange_public", "unofficial_proxy"}


def test_scanner_local_sources_keep_specific_cache_labels() -> None:
    expected = {
        "local_universe_cache": ("cache_snapshot", "本地候选缓存"),
        "local_us_parquet": ("cache_snapshot", "本地 Parquet 历史"),
        "local_us_parquet_dir": ("cache_snapshot", "本地 Parquet 历史"),
        "local_db": ("cache_snapshot", "本地数据库历史"),
        "local_db_us_history": ("cache_snapshot", "本地数据库历史"),
        "local_db_hk_history": ("cache_snapshot", "本地数据库历史"),
    }

    for source, (source_type, source_label) in expected.items():
        assert resolve_source_type(source=source) == source_type
        assert resolve_source_label(source=source, source_type=source_type) == source_label


def test_local_us_parquet_alias_projects_as_cache_snapshot_not_live_or_provider_evidence() -> None:
    provenance = project_source_provenance(
        source="local_us_parquet",
        freshness="live",
    )
    directory_provenance = project_source_provenance(
        source="local_us_parquet_dir",
        freshness="cached",
    )

    assert provenance["sourceType"] == "cache_snapshot"
    assert provenance["sourceLabel"] == "本地 Parquet 历史"
    assert provenance["freshnessLabel"] == "缓存快照"
    assert provenance["sourceType"] not in {
        "exchange_public",
        "official_public",
        "public_proxy",
        "unofficial_proxy",
        "fallback_static",
        "synthetic_fixture",
        "authorized_licensed_feed",
    }
    assert directory_provenance["sourceType"] == "cache_snapshot"
    assert directory_provenance["sourceLabel"] == "本地 Parquet 历史"
    assert directory_provenance["freshnessLabel"] == "缓存快照"


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


def test_provider_ops_gap_metadata_ids_project_safe_inert_provenance() -> None:
    cases = {
        "portfolio.price_provenance": ("cached", "cache_snapshot", "缓存快照"),
        "portfolio.fx_provenance": ("cached", "cache_snapshot", "缓存快照"),
        "portfolio.sector_industry_exposure": ("cached", "cache_snapshot", "缓存快照"),
        "portfolio.factor_risk_metrics": ("cached", "cache_snapshot", "缓存快照"),
        "portfolio.benchmark_return_history": ("cached", "cache_snapshot", "缓存快照"),
        "watchlist.scanner_score_snapshot": ("cached", "cache_snapshot", "缓存快照"),
        "watchlist.score_refresh_freshness": ("cached", "cache_snapshot", "缓存快照"),
        "watchlist.no_score_stale_state": ("unavailable", "missing", "未接入"),
        "watchlist.source_confidence_preservation": ("cached", "cache_snapshot", "缓存快照"),
        "options_lab.synthetic_fixture_chain": (
            "synthetic_delayed",
            "synthetic_fixture",
            "Synthetic Fixture",
        ),
        "options_lab.disabled_live_provider_stubs": (
            "unavailable",
            "disabled_live_stub",
            "Disabled Live Stub",
        ),
        "options_lab.bid_ask_liquidity_gate": (
            "unavailable",
            "missing",
            "Offline Bid/Ask Liquidity Gate (no authorized live decision-grade evidence)",
        ),
        "options_lab.oi_volume_gate": (
            "unavailable",
            "missing",
            "Offline OI/Volume Gate (no authorized live decision-grade evidence)",
        ),
        "options_lab.iv_greeks_gate": (
            "unavailable",
            "missing",
            "Offline IV/Greeks Gate (no authorized live decision-grade evidence)",
        ),
        "options_lab.iv_rank_candidate_evidence": (
            "unavailable",
            "missing",
            "IV Rank Candidate Evidence (diagnostic only)",
        ),
        "options_lab.iv_rank_history": ("unavailable", "missing", "未接入"),
    }

    for source, (freshness, expected_type, expected_label) in cases.items():
        provenance = project_source_provenance(
            source=source,
            freshness=freshness,
        )

        assert provenance["sourceType"] == expected_type
        assert provenance["sourceLabel"] == expected_label
        assert provenance["freshnessLabel"] != "实时"


def test_options_lab_offline_gate_rows_stay_non_live_observation_only_metadata() -> None:
    expected_labels = {
        "options_lab.bid_ask_liquidity_gate": (
            "Offline Bid/Ask Liquidity Gate (no authorized live decision-grade evidence)"
        ),
        "options_lab.oi_volume_gate": (
            "Offline OI/Volume Gate (no authorized live decision-grade evidence)"
        ),
        "options_lab.iv_greeks_gate": (
            "Offline IV/Greeks Gate (no authorized live decision-grade evidence)"
        ),
    }

    for source, expected_label in expected_labels.items():
        unavailable = project_source_provenance(source=source, freshness="unavailable")
        live_hint = project_source_provenance(
            source=source,
            source_type="official_public",
            freshness="live",
            no_external_calls=True,
        )

        assert unavailable["sourceType"] == "missing"
        assert unavailable["sourceLabel"] == expected_label
        assert unavailable["sourceLabel"] != "未接入"
        assert unavailable["freshnessLabel"] == "不可用"
        assert "Offline" in unavailable["sourceLabel"]
        assert "no authorized live decision-grade evidence" in unavailable["sourceLabel"]
        assert live_hint == unavailable
        assert live_hint["sourceType"] not in {
            "authorized_licensed_feed",
            "exchange_public",
            "official_public",
            "public_proxy",
            "unofficial_proxy",
        }


def _payload_keys(payload: Any) -> set[str]:
    if isinstance(payload, dict):
        keys: set[str] = set()
        for key, value in payload.items():
            keys.add(str(key))
            keys.update(_payload_keys(value))
        return keys
    if isinstance(payload, (list, tuple)):
        keys = set()
        for item in payload:
            keys.update(_payload_keys(item))
        return keys
    return set()


def test_options_expiration_candidate_source_registry_metadata_is_diagnostic_only() -> None:
    source = "options_lab.expiration_calendar_candidate_evidence"

    provenance = project_source_provenance(source=source, freshness="unavailable")
    metadata = project_source_registry_metadata(source)

    assert provenance == {
        "sourceType": "missing",
        "sourceLabel": "Expiration Calendar Candidate Evidence (diagnostic only)",
        "freshnessLabel": "不可用",
    }
    assert metadata == {
        "diagnosticOnly": True,
        "candidateOnly": True,
        "surface": "expiration_calendar",
        "sourceType": "missing",
        "candidateSourceClass": "occ_opra_exchange_or_licensed_expiration_calendar",
        "provenanceFamily": [
            "occ",
            "opra",
            "exchange",
            "licensed_provider",
        ],
        "entitlementFamily": [
            "options_entitlement",
            "live_delayed_status",
            "environment",
            "decision_use_rights_evidence",
            "redistribution_rights",
            "audit_timestamp",
        ],
        "slaFreshnessFamily": [
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
            "freshness_state",
            "latency_or_error_state",
        ],
        "expirationTaxonomyFamily": [
            "weekly",
            "monthly",
            "quarterly",
            "standard",
            "leaps",
            "special_expirations",
            "classification_source",
        ],
        "adjustedDeliverableCorporateActionFamily": [
            "occ_memo_or_equivalent",
            "effective_date",
            "adjusted_root_or_class",
            "deliverable_components",
            "multiplier",
            "cash_in_lieu",
            "standard_or_non_standard",
            "contract_symbol_mapping",
            "corporate_action_evidence",
        ],
        "forbiddenAuthorityInputs": [
            "coverage_completeness",
            "provider_capabilities",
            "provider_self_claims",
            "current_provider_id",
            "fixture",
            "synthetic",
            "fallback",
            "dry_run",
            "adapter_contract",
            "request_shaped_evidence",
            "proxy",
        ],
        "nextSafeStep": "document_candidate_evidence_only_without_approval",
    }


def test_options_iv_rank_candidate_source_registry_metadata_is_diagnostic_only() -> None:
    source = "options_lab.iv_rank_candidate_evidence"

    provenance = project_source_provenance(source=source, freshness="unavailable")
    metadata = project_source_registry_metadata(source)

    assert provenance == {
        "sourceType": "missing",
        "sourceLabel": "IV Rank Candidate Evidence (diagnostic only)",
        "freshnessLabel": "不可用",
    }
    assert metadata == {
        "diagnosticOnly": True,
        "candidateOnly": True,
        "surface": "iv_rank",
        "sourceType": "missing",
        "candidateSourceClass": "provider_reported_iv_rank",
        "candidateSourceClasses": [
            "provider_reported_iv_rank",
            "approved_historical_option_iv_series",
        ],
        "provenanceFamily": [
            "approved_provider",
            "licensed_source",
            "approved_internal_derived_source",
        ],
        "entitlementFamily": [
            "options_iv_history_entitlement",
            "live_delayed_status",
            "environment",
            "sandbox_or_production",
            "decision_use_rights_evidence",
            "redistribution_rights",
            "audit_timestamp",
        ],
        "slaFreshnessFamily": [
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
            "freshness_state",
            "latency_or_error_state",
        ],
        "methodologyFamily": [
            "provider_reported_iv_rank_or_percentile",
            "deterministic_derived_iv_rank",
            "methodology_version",
            "percentile_or_rank_definition",
            "calculation_basis",
        ],
        "lookbackDateRangeFamily": [
            "lookback_window",
            "date_range_start",
            "date_range_end",
        ],
        "optionIvEvidenceFamily": [
            "approved_historical_option_iv_series_availability",
            "provider_reported_iv_rank",
            "provider_reported_iv_percentile",
        ],
        "coverageScopeFamily": [
            "symbol_or_underlying_coverage",
            "contract_universe_coverage",
            "moneyness_selection_rules",
            "expiry_selection_rules",
            "missing_data_policy",
            "coverage_metadata",
        ],
        "forbiddenAuthorityInputs": [
            "current_iv",
            "selected_contract_iv",
            "selected_contract_greeks",
            "greeks",
            "historicalIvProxy",
            "historical_iv_proxy",
            "underlying_realized_volatility",
            "realized_volatility_proxy",
            "coverage_completeness",
            "source_labels",
            "provider_capability_metadata",
            "provider_capabilities",
            "provider_self_claims",
            "current_provider_id",
            "docs_only_evidence",
            "fixture",
            "synthetic",
            "fallback",
            "dry_run",
            "stub",
            "adapter_contract",
            "request_shaped",
            "request_supplied",
            "request_shaped_evidence",
            "adapter_contract_evidence",
            "synthetic_fallback_dry_run_stub_evidence",
            "proxy",
            "candidate_gap_metadata",
        ],
        "nextSafeStep": "document_candidate_evidence_only_without_approval",
    }


def test_options_iv_rank_candidate_source_registry_payload_has_no_decision_or_gate_authority_fields() -> None:
    metadata = project_source_registry_metadata("options_lab.iv_rank_candidate_evidence")
    serialized = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    forbidden_keys = {
        "authorityGrant",
        "decisionGrade",
        "providerDecisionAuthority",
        "recommendationAuthority",
        "gateDecision",
        "sourceAuthorityAllowed",
        "providerAuthority",
        "providerRouting",
        "liveCallEnabled",
        "liveProviderEnabled",
        "sourceAuthority",
        "providerSelfClaimAuthority",
    }

    assert _payload_keys(metadata).isdisjoint(forbidden_keys)
    for forbidden in forbidden_keys:
        assert forbidden not in serialized
    assert "live-call" not in serialized
    assert "routing" not in serialized


def test_options_iv_rank_candidate_source_registry_metadata_stays_metadata_only_across_gap_contracts() -> None:
    source = "options_lab.iv_rank_candidate_evidence"
    provenance = project_source_provenance(source=source, freshness="unavailable")
    metadata = project_source_registry_metadata(source)

    assert provenance["sourceType"] == "missing"
    assert provenance["sourceLabel"] == "IV Rank Candidate Evidence (diagnostic only)"
    assert metadata["sourceType"] == "missing"
    assert metadata["diagnosticOnly"] is True
    assert metadata["candidateOnly"] is True
    assert metadata["nextSafeStep"] == "document_candidate_evidence_only_without_approval"
    assert metadata["candidateSourceClasses"] == [
        "provider_reported_iv_rank",
        "approved_historical_option_iv_series",
    ]
    assert "current_iv" in metadata["forbiddenAuthorityInputs"]
    assert "selected_contract_iv" in metadata["forbiddenAuthorityInputs"]
    assert "selected_contract_greeks" in metadata["forbiddenAuthorityInputs"]
    assert "greeks" in metadata["forbiddenAuthorityInputs"]
    assert "historicalIvProxy" in metadata["forbiddenAuthorityInputs"]
    assert "historical_iv_proxy" in metadata["forbiddenAuthorityInputs"]
    assert "underlying_realized_volatility" in metadata["forbiddenAuthorityInputs"]
    assert "provider_capability_metadata" in metadata["forbiddenAuthorityInputs"]
    assert "provider_capabilities" in metadata["forbiddenAuthorityInputs"]
    assert "provider_self_claims" in metadata["forbiddenAuthorityInputs"]
    assert "current_provider_id" in metadata["forbiddenAuthorityInputs"]
    assert "docs_only_evidence" in metadata["forbiddenAuthorityInputs"]
    assert "request_shaped" in metadata["forbiddenAuthorityInputs"]
    assert "request_supplied" in metadata["forbiddenAuthorityInputs"]
    assert "request_shaped_evidence" in metadata["forbiddenAuthorityInputs"]
    assert "adapter_contract_evidence" in metadata["forbiddenAuthorityInputs"]
    assert "synthetic_fallback_dry_run_stub_evidence" in metadata["forbiddenAuthorityInputs"]
    assert "proxy" in metadata["forbiddenAuthorityInputs"]
    assert "coverage_completeness" in metadata["forbiddenAuthorityInputs"]

    for source_class in metadata["candidateSourceClasses"]:
        gap = build_options_iv_rank_source_candidate_gap(source_class)
        assert gap["authorityGrant"] is False
        for forbidden_field in (
            "providerDecisionAuthority",
            "recommendationAuthority",
            "decisionGrade",
            "gateDecision",
            "sourceAuthorityAllowed",
            "providerRouting",
            "liveCallEnablement",
        ):
            assert forbidden_field not in metadata
            assert forbidden_field not in gap


def test_options_expiration_candidate_source_registry_payload_has_no_decision_or_gate_authority_fields() -> None:
    metadata = project_source_registry_metadata("options_lab.expiration_calendar_candidate_evidence")
    serialized = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    forbidden_keys = {
        "authorityGrant",
        "decisionGrade",
        "providerDecisionAuthority",
        "recommendationAuthority",
        "gateDecision",
        "sourceAuthorityAllowed",
        "providerAuthority",
        "providerRouting",
        "liveCallEnabled",
        "liveProviderEnabled",
        "sourceAuthority",
        "providerSelfClaimAuthority",
    }

    assert _payload_keys(metadata).isdisjoint(forbidden_keys)
    for forbidden in forbidden_keys:
        assert forbidden not in serialized
    assert "live-call" not in serialized
    assert "routing" not in serialized


def test_options_expiration_candidate_source_registry_metadata_stays_metadata_only_across_contracts() -> None:
    source = "options_lab.expiration_calendar_candidate_evidence"
    provenance = project_source_provenance(source=source, freshness="unavailable")
    metadata = project_source_registry_metadata(source)
    gap = build_options_expiration_source_candidate_gap(metadata["candidateSourceClass"])
    contract = build_expiration_calendar_source_candidate_evidence(
        {
            "providerId": "tradier",
            "providerDecisionAuthority": True,
            "recommendationAuthority": True,
            "decisionGrade": "tradeable",
            "gateDecision": "pass",
            "sourceAuthorityAllowed": True,
            "providerRouting": {"target": "tradier"},
            "liveCallEnablement": True,
            "expirationTaxonomy": {"specialExpirations": "partial"},
        }
    )

    assert provenance["sourceType"] == "missing"
    assert provenance["sourceLabel"] == "Expiration Calendar Candidate Evidence (diagnostic only)"
    assert metadata["sourceType"] == "missing"
    assert metadata["diagnosticOnly"] is True
    assert metadata["candidateOnly"] is True
    assert metadata["nextSafeStep"] == "document_candidate_evidence_only_without_approval"
    assert "provider_capabilities" in metadata["forbiddenAuthorityInputs"]
    assert "provider_self_claims" in metadata["forbiddenAuthorityInputs"]
    assert "current_provider_id" in metadata["forbiddenAuthorityInputs"]
    assert gap["authorityGrant"] is False
    assert contract["authorityGrant"] is False

    for forbidden_field in (
        "providerDecisionAuthority",
        "recommendationAuthority",
        "decisionGrade",
        "gateDecision",
        "sourceAuthorityAllowed",
        "providerRouting",
        "liveCallEnablement",
    ):
        assert forbidden_field not in metadata
        assert forbidden_field not in contract
        assert forbidden_field not in gap


def test_options_event_candidate_source_registry_metadata_is_diagnostic_only() -> None:
    source = "options_lab.event_calendar_candidate_evidence"

    provenance = project_source_provenance(source=source, freshness="unavailable")
    metadata = project_source_registry_metadata(source)

    assert provenance == {
        "sourceType": "missing",
        "sourceLabel": "Event Calendar Candidate Evidence (diagnostic only)",
        "freshnessLabel": "不可用",
    }
    assert metadata == {
        "diagnosticOnly": True,
        "candidateOnly": True,
        "surface": "event_calendar",
        "sourceType": "missing",
        "candidateSourceClass": "licensed_event_calendar_provider",
        "provenanceFamily": [
            "licensed_provider",
            "exchange",
            "issuer",
            "official_calendar",
            "approved_internal_source",
        ],
        "entitlementFamily": [
            "event_calendar_entitlement",
            "live_delayed_status",
            "environment",
            "sandbox_or_production",
            "decision_use_rights_evidence",
            "redistribution_rights",
            "audit_timestamp",
        ],
        "slaFreshnessFamily": [
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
            "freshness_state",
            "latency_or_error_state",
        ],
        "eventTaxonomyFamily": [
            "earnings",
            "dividends",
            "ex_dividend",
            "dividends_ex_dividend",
            "splits",
            "corporate_actions",
            "macro_context_relevance",
            "fomc_macro_context_policy_scope",
        ],
        "confirmationFamily": [
            "confirmed_or_estimated",
            "announcement_status",
        ],
        "eventIdentityFamily": [
            "provider_event_id",
            "event_identity",
        ],
        "timezoneSessionFamily": [
            "event_date",
            "event_time",
            "session",
            "timezone",
        ],
        "coverageScopeFamily": [
            "symbol_or_underlying_coverage",
            "lookahead_window_or_date_range",
            "coverage_metadata",
        ],
        "forbiddenAuthorityInputs": [
            "event_presence",
            "event_count",
            "event_type",
            "timeline_evidence",
            "generic_macro_context",
            "provider_capabilities",
            "provider_capability_metadata",
            "candidate_gap_metadata",
            "source_labels",
            "provider_self_claims",
            "current_provider_id",
            "fixture",
            "synthetic",
            "fallback",
            "dry_run",
            "stub",
            "adapter_contract",
            "request_shaped_evidence",
            "proxy",
        ],
        "nextSafeStep": "document_candidate_evidence_only_without_approval",
    }


def test_options_event_candidate_source_registry_payload_has_no_decision_or_gate_authority_fields() -> None:
    metadata = project_source_registry_metadata("options_lab.event_calendar_candidate_evidence")
    serialized = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    forbidden_keys = {
        "authorityGrant",
        "decisionGrade",
        "providerDecisionAuthority",
        "recommendationAuthority",
        "gateDecision",
        "sourceAuthorityAllowed",
        "providerAuthority",
        "providerRouting",
        "liveCallEnabled",
        "liveProviderEnabled",
        "sourceAuthority",
        "providerSelfClaimAuthority",
    }

    assert _payload_keys(metadata).isdisjoint(forbidden_keys)
    for forbidden in forbidden_keys:
        assert forbidden not in serialized
    assert "live-call" not in serialized
    assert "routing" not in serialized


def test_options_event_candidate_source_registry_metadata_stays_metadata_only_across_gap_contracts() -> None:
    source = "options_lab.event_calendar_candidate_evidence"
    provenance = project_source_provenance(source=source, freshness="unavailable")
    metadata = project_source_registry_metadata(source)
    gap = build_options_event_calendar_source_candidate_gap(metadata["candidateSourceClass"])
    contract = build_event_calendar_source_candidate_evidence(
        {
            "sourceClass": metadata["candidateSourceClass"],
            "providerId": "tradier",
            "providerName": "tradier",
            "coverageType": "issuer_event_calendar",
            "observedEventCount": 2,
            "eventDateRange": {"start": "2026-06-01", "end": "2026-06-30"},
            "timelineCoverageNotes": ["events_present"],
            "eventTaxonomy": {
                "earnings": "proven",
                "dividends": "partial",
                "exDividend": "partial",
                "fomcMacroContext": "proven",
            },
            "macroPolicyScope": "generic_macro_context_only",
            "providerDecisionAuthority": True,
            "recommendationAuthority": True,
            "decisionGrade": "tradeable",
            "gateDecision": "pass",
            "sourceAuthorityAllowed": True,
            "providerRouting": {"target": "tradier"},
            "liveCallEnablement": True,
        }
    )

    assert provenance["sourceType"] == "missing"
    assert provenance["sourceLabel"] == "Event Calendar Candidate Evidence (diagnostic only)"
    assert metadata["sourceType"] == "missing"
    assert metadata["diagnosticOnly"] is True
    assert metadata["candidateOnly"] is True
    assert metadata["nextSafeStep"] == "document_candidate_evidence_only_without_approval"
    assert "authorityGrant" not in metadata
    assert "event_presence" in metadata["forbiddenAuthorityInputs"]
    assert "event_count" in metadata["forbiddenAuthorityInputs"]
    assert "event_type" in metadata["forbiddenAuthorityInputs"]
    assert "timeline_evidence" in metadata["forbiddenAuthorityInputs"]
    assert "generic_macro_context" in metadata["forbiddenAuthorityInputs"]
    assert "provider_capability_metadata" in metadata["forbiddenAuthorityInputs"]
    assert "candidate_gap_metadata" in metadata["forbiddenAuthorityInputs"]
    assert "provider_self_claims" in metadata["forbiddenAuthorityInputs"]
    assert "current_provider_id" in metadata["forbiddenAuthorityInputs"]
    assert gap["authorityGrant"] is False
    assert contract["authorityGrant"] is False
    assert contract["diagnosticOnly"] is True
    assert contract["candidateOnly"] is True
    assert contract["sourceIdentity"]["sourceClass"] == metadata["candidateSourceClass"]

    for forbidden_field in (
        "providerDecisionAuthority",
        "recommendationAuthority",
        "decisionGrade",
        "gateDecision",
        "sourceAuthorityAllowed",
        "providerRouting",
        "liveCallEnablement",
    ):
        assert forbidden_field not in metadata
        assert forbidden_field not in contract
        assert forbidden_field not in gap


def test_source_registry_metadata_helper_preserves_existing_projection_contract() -> None:
    assert project_source_registry_metadata("binance") == {}

    provenance = project_source_provenance(source="binance", freshness="live")

    assert provenance == {
        "sourceType": "exchange_public",
        "sourceLabel": "Binance",
        "freshnessLabel": "实时",
    }
