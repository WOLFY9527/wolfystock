# -*- coding: utf-8 -*-
"""Focused tests for inert reason-code vocabulary classification."""

from __future__ import annotations

from src.services.reason_code_vocabulary import (
    ReasonCodeClassification,
    classify_reason_code,
    classify_reason_codes,
)


def test_source_confidence_cap_codes_map_to_stable_families() -> None:
    assert classify_reason_code("unavailable_source") == ReasonCodeClassification(
        raw_code="unavailable_source",
        family="unavailable",
        scope="source_confidence",
    )
    assert classify_reason_code("synthetic_source") == ReasonCodeClassification(
        raw_code="synthetic_source",
        family="synthetic",
        scope="source_confidence",
    )
    assert classify_reason_code("fallback_source") == ReasonCodeClassification(
        raw_code="fallback_source",
        family="fallback",
        scope="source_confidence",
    )
    assert classify_reason_code("stale_source") == ReasonCodeClassification(
        raw_code="stale_source",
        family="stale",
        scope="source_confidence",
    )
    assert classify_reason_code("partial_coverage") == ReasonCodeClassification(
        raw_code="partial_coverage",
        family="partial",
        scope="source_confidence",
    )


def test_proxy_adjacent_codes_preserve_raw_code_and_scope() -> None:
    assert classify_reason_code("proxy_quote_source_capped") == ReasonCodeClassification(
        raw_code="proxy_quote_source_capped",
        family="source_confidence_cap",
        scope="scanner",
    )
    assert classify_reason_code("public_proxy_not_score_grade") == ReasonCodeClassification(
        raw_code="public_proxy_not_score_grade",
        family="source_confidence_cap",
        scope="scanner_evidence_packet",
    )
    assert classify_reason_code("proxy_context_only") == ReasonCodeClassification(
        raw_code="proxy_context_only",
        family="proxy",
        scope="market_overview",
    )
    assert classify_reason_code("proxy_only_missing_real_source") == ReasonCodeClassification(
        raw_code="proxy_only_missing_real_source",
        family="observation_only",
        scope="liquidity_monitor",
    )
    assert classify_reason_code("proxy_source_not_reproducible") == ReasonCodeClassification(
        raw_code="proxy_source_not_reproducible",
        family="reproducibility_degraded",
        scope="backtest_authority",
    )


def test_malformed_codes_do_not_collapse_into_unavailable() -> None:
    assert classify_reason_code("malformed_payload").family == "malformed"
    assert classify_reason_code("malformed_official_value").family == "malformed"
    assert classify_reason_code("parse_error").family == "malformed"
    assert classify_reason_code("unsupported_unit").family == "malformed"
    assert classify_reason_code("unsupported_value_format").family == "malformed"


def test_official_cache_readiness_codes_are_diagnostic_only() -> None:
    assert classify_reason_code("fed_liquidity_required_series_missing_or_stale") == ReasonCodeClassification(
        raw_code="fed_liquidity_required_series_missing_or_stale",
        family="observation_only",
        scope="official_cache_readiness",
    )
    assert classify_reason_code("cn_money_market_required_series_missing_or_stale") == ReasonCodeClassification(
        raw_code="cn_money_market_required_series_missing_or_stale",
        family="observation_only",
        scope="official_cache_readiness",
    )
    assert classify_reason_code("stale_official_release") == ReasonCodeClassification(
        raw_code="stale_official_release",
        family="stale",
        scope="official_cache_readiness",
    )
    assert classify_reason_code("missing_cache") == ReasonCodeClassification(
        raw_code="missing_cache",
        family="missing",
        scope="official_cache_readiness",
    )
    assert classify_reason_code("partial_official_coverage") == ReasonCodeClassification(
        raw_code="partial_official_coverage",
        family="partial",
        scope="official_cache_readiness",
    )


def test_backtest_authority_codes_remain_distinguishable() -> None:
    rejected = classify_reason_code("provider_forbidden_for_use_case")
    proxy_fill_only = classify_reason_code("proxy_source_not_reproducible")
    generic_degraded = classify_reason_code("source_not_reproducible_for_backtest")

    assert rejected == ReasonCodeClassification(
        raw_code="provider_forbidden_for_use_case",
        family="authority_rejected",
        scope="backtest_authority",
    )
    assert proxy_fill_only == ReasonCodeClassification(
        raw_code="proxy_source_not_reproducible",
        family="reproducibility_degraded",
        scope="backtest_authority",
    )
    assert generic_degraded == ReasonCodeClassification(
        raw_code="source_not_reproducible_for_backtest",
        family="reproducibility_degraded",
        scope="backtest_authority",
    )
    assert rejected.raw_code != proxy_fill_only.raw_code
    assert proxy_fill_only.raw_code != generic_degraded.raw_code


def test_unknown_codes_return_unclassified() -> None:
    assert classify_reason_code("totally_new_reason_code") == ReasonCodeClassification(
        raw_code="totally_new_reason_code",
        family="unclassified",
        scope=None,
    )


def test_none_reason_code_returns_missing() -> None:
    assert classify_reason_code(None) == ReasonCodeClassification(
        raw_code=None,
        family="missing",
        scope=None,
    )


def test_classify_reason_codes_preserves_input_order_and_duplicates() -> None:
    assert classify_reason_codes(
        [
            "fallback_source",
            "fallback_source",
            "proxy_context_only",
            "totally_new_reason_code",
        ]
    ) == [
        ReasonCodeClassification(
            raw_code="fallback_source",
            family="fallback",
            scope="source_confidence",
        ),
        ReasonCodeClassification(
            raw_code="fallback_source",
            family="fallback",
            scope="source_confidence",
        ),
        ReasonCodeClassification(
            raw_code="proxy_context_only",
            family="proxy",
            scope="market_overview",
        ),
        ReasonCodeClassification(
            raw_code="totally_new_reason_code",
            family="unclassified",
            scope=None,
        ),
    ]
