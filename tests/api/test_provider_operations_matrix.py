# -*- coding: utf-8 -*-
"""Admin provider operations matrix API tests."""

from __future__ import annotations

import builtins
import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import admin_provider_operations_matrix
from src.services.cn_money_market_rates_contracts import (
    OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV,
    OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
)
from src.services.provider_operations_matrix_service import (
    ProviderOperationsMatrixService,
)

CN_TZ = timezone(timedelta(hours=8))


def _provider_read_admin() -> CurrentUser:
    return CurrentUser(
        user_id="bootstrap-admin",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:providers:read",),
    )


def _admin_without_provider_read() -> CurrentUser:
    return CurrentUser(
        user_id="bootstrap-admin",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("users:read",),
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


def _client_for(user_factory) -> TestClient:
    app = FastAPI()
    app.include_router(admin_provider_operations_matrix.router, prefix="/api/v1/admin")
    app.dependency_overrides[get_current_user] = user_factory
    return TestClient(app)


def _row_by_id(payload: dict, provider_id: str) -> dict:
    return next(row for row in payload["rows"] if row["providerId"] == provider_id)


def _cn_money_market_cache_payload() -> dict:
    now = datetime.now(CN_TZ).replace(microsecond=0)
    date_text = now.date().isoformat()
    return {
        "providerId": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "source": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "sourceType": "official_public",
        "sourceTier": "official_public",
        "asOf": now.isoformat(timespec="seconds"),
        "publicationDate": date_text,
        "tradingDate": date_text,
        "holidayCalendarQualified": True,
        "freshness": "delayed",
        "observations": [
            {"symbol": "DR007", "value": 1.86, "unit": "%"},
            {"symbol": "SHIBOR", "officialSeriesId": "SHIBOR_ON", "value": 1.72, "unit": "%"},
        ],
    }


def _fed_liquidity_runtime_row(
    series_id: str,
    *,
    value: float = 1.0,
    freshness: str = "delayed",
    freshness_policy: str | None = None,
    source_authority_allowed: bool = True,
    score_contribution_allowed: bool = True,
    is_fallback: bool = False,
    is_unavailable: bool = False,
    is_stale: bool = False,
) -> dict:
    policy = freshness_policy
    if policy is None:
        policy = (
            "official_daily_us_weekday_t_plus_1"
            if series_id == "RRPONTSYD"
            else "official_weekly_fed_liquidity_t_plus_7"
        )
    return {
        "officialSeriesId": series_id,
        "value": value,
        "sourceType": "official_public",
        "sourceTier": "official_public",
        "freshness": freshness,
        "isFallback": is_fallback,
        "isUnavailable": is_unavailable,
        "isStale": is_stale,
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "sourceFreshnessEvidence": {
            "freshness": freshness,
            "freshnessPolicy": policy,
            "isFallback": is_fallback,
            "isUnavailable": is_unavailable,
            "isStale": is_stale,
        },
    }


def test_endpoint_requires_admin_provider_read_capability() -> None:
    user_client = _client_for(_regular_user)
    user_response = user_client.get("/api/v1/admin/providers/operations-matrix")
    assert user_response.status_code == 403
    assert user_response.json()["detail"]["error"] == "admin_required"

    no_capability_client = _client_for(_admin_without_provider_read)
    no_capability_response = no_capability_client.get("/api/v1/admin/providers/operations-matrix")
    assert no_capability_response.status_code == 403
    assert no_capability_response.json()["detail"]["error"] == "admin_capability_required"
    assert "ops:providers:read" not in no_capability_response.text

    admin_client = _client_for(_provider_read_admin)
    admin_response = admin_client.get("/api/v1/admin/providers/operations-matrix")
    assert admin_response.status_code == 200
    assert admin_response.json()["metadata"]["readOnly"] is True


def test_matrix_rows_are_diagnostic_only_and_include_missing_authorized_feeds() -> None:
    payload = ProviderOperationsMatrixService(
        env={},
        spec_finder=lambda _: None,
    ).build_matrix()

    assert payload["diagnosticOnly"] is True
    assert payload["metadata"]["readOnly"] is True
    assert payload["metadata"]["externalProviderCalls"] is False
    assert payload["metadata"]["cacheMutation"] is False
    assert payload["metadata"]["providerOrderChanged"] is False

    assert payload["rows"]
    for row in payload["rows"]:
        assert row["diagnosticOnly"] is True
        assert row["credentialState"] in {"missing", "present", "not_required", "unknown"}
        assert row["dependencyState"] in {"installed", "missing", "unknown", "not_required"}
        assert "rawPayload" not in row
        assert "providerPayload" not in row

    etf_flow = _row_by_id(payload, "authorized.us_etf_flow")
    assert etf_flow["sourceType"] == "missing"
    assert etf_flow["runtimeState"] == "missing_provider_configuration"
    assert etf_flow["missingProviderReason"] == "authorized_us_etf_flow_feed_not_configured"
    assert etf_flow["paidDataLikelyRequired"] is True
    assert etf_flow["keyRequired"] is True
    assert etf_flow["scoreContributionAllowed"] is False
    assert etf_flow["scoreEligible"] is False
    assert {
        "us_etf_flow_daily",
        "us_etf_creation_redemption",
        "us_sector_etf_flow",
    }.issubset(set(etf_flow["supportedCapabilities"]))
    assert etf_flow["contractCadences"] == ["daily"]
    assert etf_flow["contractFreshnessFloors"] == ["daily"]
    assert etf_flow["contractCoverageRatioFloor"] == 0.8
    assert etf_flow["requiredSourceTiers"] == ["authorized_licensed_feed"]
    assert etf_flow["scoreEligibilityGates"] == [
        "configured_authorized_feed_and_daily_freshness_and_min_coverage"
    ]
    assert {
        "licensed_us_listed_etf_universe",
        "licensed_us_primary_etf_basket",
        "licensed_us_sector_etf_universe",
    }.issubset(set(etf_flow["contractCoverageUniverses"]))
    assert {
        "missing_provider_configuration",
        "authorization_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(etf_flow["routerReasonCodes"]))

    breadth = _row_by_id(payload, "official_or_authorized.us_market_breadth")
    assert breadth["sourceType"] == "missing"
    assert breadth["runtimeState"] == "missing_provider_configuration"
    assert breadth["missingProviderReason"] == "authorized_us_market_breadth_feed_not_configured"
    assert breadth["paidDataLikelyRequired"] is True
    assert breadth["keyRequired"] is True
    assert breadth["scoreContributionAllowed"] is False
    assert breadth["scoreEligible"] is False
    assert {
        "us_market_breadth_constituents",
        "us_advancers_decliners",
        "us_new_highs_lows",
        "us_above_ma_breadth",
        "us_sector_breadth",
    }.issubset(set(breadth["supportedCapabilities"]))
    assert breadth["contractCadences"] == ["daily"]
    assert breadth["contractFreshnessFloors"] == ["daily"]
    assert breadth["contractCoverageRatioFloor"] == 0.8
    assert breadth["requiredSourceTiers"] == ["official_or_authorized_licensed_feed"]
    assert breadth["scoreEligibilityGates"] == [
        "configured_official_or_authorized_feed_and_daily_freshness_and_min_coverage"
    ]
    assert {
        "nyse_nasdaq_listed_equity_universe",
        "configured_index_or_exchange_breadth_universe",
        "licensed_us_sector_breadth_basket",
    }.issubset(set(breadth["contractCoverageUniverses"]))
    assert {
        "missing_provider_configuration",
        "authorization_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(breadth["routerReasonCodes"]))

    fed = _row_by_id(payload, "official_public.fed_liquidity")
    assert fed["sourceType"] == "official_public"
    assert fed["sourceTier"] == "official_public"
    assert fed["runtimeState"] == "aggregate_supported_runtime_evidence_missing"
    assert fed["credentialState"] == "not_required"
    assert fed["dependencyState"] == "not_required"
    assert fed["missingProviderReason"] is None
    assert fed["paidDataLikelyRequired"] is False
    assert fed["keyRequired"] is False
    assert fed["scoreContributionAllowed"] is False
    assert fed["scoreEligible"] is False
    assert fed["observationOnly"] is True
    assert fed["sourceAuthorityAllowed"] is False
    assert fed["supportedCapabilities"] == ["fed_liquidity"]
    assert fed["contractCadences"] == ["daily_weekly"]
    assert fed["contractFreshnessFloors"] == ["delayed"]
    assert fed["contractCoverageRatioFloor"] == 1.0
    assert fed["requiredSourceTiers"] == ["official_public"]
    assert fed["scoreEligibilityGates"] == [
        "configured_official_release_ids_and_cache_freshness_and_full_component_coverage"
    ]
    assert fed["contractCoverageUniverses"] == ["rrp_tga_reserve_balances_release_bundle"]
    assert {"market_overview", "liquidity_impulse"}.issubset(set(fed["affectedSurfaces"]))
    assert fed["productAffectedSurfaces"] == ["market_overview", "liquidity_monitor"]
    assert fed["fulfilledMetrics"] == []
    assert fed["missingMetrics"] == ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert fed["coverageCount"] == 0
    assert fed["reasonCodes"] == [
        "official_macro_transport_supported",
        "missing_official_macro_row",
    ]
    assert fed["sourceFreshnessEvidence"] == {
        "aggregateSupported": True,
        "externalProviderCalls": False,
        "freshness": "unavailable",
        "freshnessPolicies": {
            "RRPONTSYD": "official_daily_us_weekday_t_plus_1",
            "WALCL": "official_weekly_fed_liquidity_t_plus_7",
            "WRESBAL": "official_weekly_fed_liquidity_t_plus_7",
            "WTREGEN": "official_weekly_fed_liquidity_t_plus_7",
        },
        "isFallback": False,
        "isPartial": False,
        "isUnavailable": True,
        "requiredSeries": ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"],
        "supportedSourceIds": [
            "FRED_WALCL",
            "FRED_RRPONTSYD",
            "FRED_WTREGEN",
            "FRED_WRESBAL",
        ],
        "runtimeEvidence": "missing",
        "coverageThreshold": 1.0,
        "coverageThresholdPassed": False,
        "coverageThresholdFailure": True,
    }
    assert {
        "missing_provider_configuration",
        "cache_required",
        "release_schedule_required",
        "release_lag_expected",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(fed["routerReasonCodes"]))

    cn_money = _row_by_id(payload, "official_public.cn_money_market_rates")
    assert cn_money["sourceType"] == "missing"
    assert cn_money["sourceTier"] == "official_public"
    assert cn_money["runtimeState"] == "missing_provider_configuration"
    assert cn_money["credentialState"] == "not_required"
    assert cn_money["dependencyState"] == "not_required"
    assert cn_money["missingProviderReason"] == "official_cn_money_market_rates_contract_not_configured"
    assert cn_money["paidDataLikelyRequired"] is False
    assert cn_money["keyRequired"] is False
    assert cn_money["scoreContributionAllowed"] is False
    assert cn_money["scoreEligible"] is False
    assert cn_money["supportedCapabilities"] == ["cn_money_market_rates"]
    assert cn_money["contractCadences"] == ["session_daily"]
    assert cn_money["contractFreshnessFloors"] == ["delayed"]
    assert cn_money["contractCoverageRatioFloor"] == 1.0
    assert cn_money["requiredSourceTiers"] == ["official_public"]
    assert cn_money["scoreEligibilityGates"] == [
        "configured_official_rates_and_session_freshness_and_full_component_coverage"
    ]
    assert cn_money["contractCoverageUniverses"] == ["dr007_shibor_repo_liquidity_rate_bundle"]
    assert {"market_overview", "liquidity_impulse"}.issubset(set(cn_money["affectedSurfaces"]))
    assert cn_money["productAffectedSurfaces"] == ["market_overview", "liquidity_monitor"]
    assert {
        "missing_provider_configuration",
        "cache_required",
        "session_calendar_required",
        "holiday_calendar_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(cn_money["routerReasonCodes"]))

    dxy = _row_by_id(payload, "official_or_authorized.fx_dxy")
    assert dxy["sourceType"] == "missing"
    assert dxy["sourceTier"] == "official_or_authorized_fx_feed"
    assert dxy["runtimeState"] == "missing_provider_configuration"
    assert dxy["credentialState"] == "missing"
    assert dxy["dependencyState"] == "not_required"
    assert dxy["missingProviderReason"] == "authorized_dxy_feed_not_configured"
    assert dxy["paidDataLikelyRequired"] is True
    assert dxy["keyRequired"] is True
    assert dxy["scoreContributionAllowed"] is False
    assert dxy["scoreEligible"] is False
    assert dxy["supportedCapabilities"] == ["fx_dxy"]
    assert dxy["contractCadences"] == ["continuous_session"]
    assert dxy["contractFreshnessFloors"] == ["delayed"]
    assert dxy["contractCoverageRatioFloor"] == 1.0
    assert dxy["requiredSourceTiers"] == ["official_or_authorized_fx_feed"]
    assert dxy["scoreEligibilityGates"] == [
        "configured_official_or_authorized_dxy_authority_and_pair_context"
    ]
    assert dxy["contractCoverageUniverses"] == ["dxy_reference_pair_bundle"]
    assert {"market_overview", "liquidity_impulse"}.issubset(set(dxy["affectedSurfaces"]))
    assert dxy["productAffectedSurfaces"] == ["market_overview", "liquidity_monitor"]
    assert {
        "missing_provider_configuration",
        "cache_required",
        "authorization_required",
        "session_market_hours_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(dxy["routerReasonCodes"]))

    cn_hk_flow = _row_by_id(payload, "authorized.cn_hk_connect_flow")
    assert cn_hk_flow["sourceType"] == "missing"
    assert cn_hk_flow["sourceTier"] == "authorized_licensed_feed"
    assert cn_hk_flow["runtimeState"] == "missing_provider_configuration"
    assert cn_hk_flow["credentialState"] == "missing"
    assert cn_hk_flow["dependencyState"] == "not_required"
    assert cn_hk_flow["missingProviderReason"] == "authorized_cn_hk_connect_flow_feed_not_configured"
    assert cn_hk_flow["paidDataLikelyRequired"] is True
    assert cn_hk_flow["keyRequired"] is True
    assert cn_hk_flow["scoreContributionAllowed"] is False
    assert cn_hk_flow["scoreEligible"] is False
    assert cn_hk_flow["supportedCapabilities"] == ["cn_hk_connect_flow"]
    assert cn_hk_flow["contractCadences"] == ["session_daily"]
    assert cn_hk_flow["contractFreshnessFloors"] == ["delayed"]
    assert cn_hk_flow["contractCoverageRatioFloor"] == 0.8
    assert cn_hk_flow["requiredSourceTiers"] == ["authorized_licensed_feed"]
    assert cn_hk_flow["scoreEligibilityGates"] == [
        "configured_cn_hk_connect_bundle_and_session_freshness_and_min_coverage"
    ]
    assert cn_hk_flow["contractCoverageUniverses"] == [
        "northbound_southbound_mainland_flow_bundle"
    ]
    assert {"market_overview", "liquidity_impulse"}.issubset(set(cn_hk_flow["affectedSurfaces"]))
    assert cn_hk_flow["productAffectedSurfaces"] == ["market_overview", "liquidity_monitor"]
    assert {
        "missing_provider_configuration",
        "cache_required",
        "authorization_required",
        "session_calendar_required",
        "coverage_floor_required",
    }.issubset(set(cn_hk_flow["routerReasonCodes"]))

    futures = _row_by_id(payload, "exchange_or_broker_authorized.index_futures")
    assert futures["sourceType"] == "missing"
    assert futures["sourceTier"] == "exchange_or_broker_authorized_feed"
    assert futures["runtimeState"] == "missing_provider_configuration"
    assert futures["credentialState"] == "missing"
    assert futures["dependencyState"] == "not_required"
    assert futures["missingProviderReason"] == "authorized_index_futures_feed_not_configured"
    assert futures["paidDataLikelyRequired"] is True
    assert futures["keyRequired"] is True
    assert futures["scoreContributionAllowed"] is False
    assert futures["scoreEligible"] is False
    assert futures["supportedCapabilities"] == ["index_futures"]
    assert futures["contractCadences"] == ["extended_hours"]
    assert futures["contractFreshnessFloors"] == ["delayed"]
    assert futures["contractCoverageRatioFloor"] == 1.0
    assert futures["contractRequiredSymbols"] == ["NQ", "ES", "YM", "RTY"]
    assert futures["contractSessions"] == ["extended_hours"]
    assert futures["requiredSourceTiers"] == ["exchange_or_broker_authorized_feed"]
    assert futures["scoreEligibilityGates"] == [
        "configured_authorized_index_futures_bundle_and_extended_hours_freshness"
    ]
    assert futures["contractCoverageUniverses"] == ["nq_es_ym_rty_extended_hours_bundle"]
    assert {"market_overview", "liquidity_impulse"}.issubset(set(futures["affectedSurfaces"]))
    assert futures["productAffectedSurfaces"] == ["market_overview", "liquidity_monitor"]
    assert {
        "missing_provider_configuration",
        "cache_required",
        "authorization_required",
        "extended_hours_session_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(futures["routerReasonCodes"]))

    rotation_flow = _row_by_id(payload, "authorized.real_sector_theme_flow")
    assert rotation_flow["sourceType"] == "missing"
    assert rotation_flow["sourceTier"] == "authorized_licensed_feed"
    assert rotation_flow["runtimeState"] == "missing_provider_configuration"
    assert rotation_flow["credentialState"] == "missing"
    assert rotation_flow["dependencyState"] == "not_required"
    assert rotation_flow["missingProviderReason"] == "authorized_real_sector_theme_flow_not_configured"
    assert rotation_flow["paidDataLikelyRequired"] is True
    assert rotation_flow["keyRequired"] is True
    assert rotation_flow["scoreContributionAllowed"] is False
    assert rotation_flow["scoreEligible"] is False
    assert rotation_flow["supportedCapabilities"] == ["real_sector_theme_flow_evidence"]
    assert rotation_flow["contractCadences"] == ["daily_intraday"]
    assert rotation_flow["contractFreshnessFloors"] == ["delayed"]
    assert rotation_flow["contractCoverageRatioFloor"] == 0.7
    assert rotation_flow["requiredSourceTiers"] == ["authorized_licensed_feed"]
    assert rotation_flow["scoreEligibilityGates"] == [
        "configured_sector_theme_flow_and_taxonomy_mapping_and_min_coverage"
    ]
    assert rotation_flow["contractCoverageUniverses"] == ["licensed_sector_theme_flow_universe"]
    assert "rotation_radar" in rotation_flow["affectedSurfaces"]
    assert rotation_flow["productAffectedSurfaces"] == ["rotation_radar"]
    assert {
        "missing_provider_configuration",
        "cache_required",
        "authorization_required",
        "taxonomy_to_real_flow_mapping_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(rotation_flow["routerReasonCodes"]))


def test_provider_operations_matrix_payload_shape_keeps_score_authority_fields_stable() -> None:
    payload = ProviderOperationsMatrixService(env={}, spec_finder=lambda _: None).build_matrix()

    assert set(payload) == {"generatedAt", "diagnosticOnly", "rows", "summary", "metadata"}
    assert {
        "readOnly",
        "externalProviderCalls",
        "providerOrderChanged",
        "secretValuesIncluded",
        "rawProviderPayloadsIncluded",
        "rowCount",
    }.issubset(payload["metadata"])

    row = _row_by_id(payload, "local_cache")
    assert {
        "providerId",
        "sourceType",
        "sourceTier",
        "trustLevel",
        "runtimeState",
        "sourceAuthorityAllowed",
        "scoreContributionAllowed",
        "scoreEligible",
        "reasonCodes",
        "routerReasonCodes",
        "sourceFreshnessEvidence",
        "diagnosticOnly",
    }.issubset(row)
    assert "scoreAuthorityReasonCodes" not in row
    assert "sourceAuthorityReasonCodes" not in row
    assert "scoreEligibilityReasonCodes" not in row


def test_unknown_surface_aliases_fall_back_to_provider_ops_product_surface() -> None:
    assert ProviderOperationsMatrixService._canonical_product_affected_surfaces(
        ["mystery_surface"]
    ) == ["provider_ops"]
    assert ProviderOperationsMatrixService._canonical_product_affected_surfaces(
        ["stock_history", "system_diagnostics", "unknown_surface"]
    ) == ["provider_ops"]


def test_watchlist_surface_alias_is_canonicalized_independently_from_scanner() -> None:
    assert ProviderOperationsMatrixService._canonical_product_affected_surfaces(
        ["scanner_diagnostics", "watchlist", "watchlist.score_refresh_freshness"]
    ) == ["scanner", "watchlist"]


def test_portfolio_watchlist_and_options_gap_rows_are_inert_and_surface_scoped() -> None:
    payload = ProviderOperationsMatrixService(
        env={},
        spec_finder=lambda _: None,
    ).build_matrix()

    expected = {
        "portfolio.price_provenance": {
            "sourceType": "cache_snapshot",
            "runtimeState": "configured_cache_only_diagnostic",
            "providerCategory": "portfolio_diagnostic_gap",
            "surface": "portfolio",
            "cacheRequired": True,
            "keyRequired": False,
            "paidDataLikelyRequired": False,
            "hint": ("stored", "freshness", "lineage", "non-fallback"),
        },
        "portfolio.fx_provenance": {
            "sourceType": "cache_snapshot",
            "runtimeState": "configured_cache_only_diagnostic",
            "providerCategory": "portfolio_diagnostic_gap",
            "surface": "portfolio",
            "cacheRequired": True,
            "keyRequired": False,
            "paidDataLikelyRequired": False,
            "hint": ("stored", "freshness", "lineage", "non-fallback"),
        },
        "portfolio.sector_industry_exposure": {
            "sourceType": "cache_snapshot",
            "runtimeState": "configured_cache_only_diagnostic",
            "providerCategory": "portfolio_diagnostic_gap",
            "surface": "portfolio",
            "cacheRequired": True,
            "keyRequired": False,
            "paidDataLikelyRequired": False,
            "hint": ("stored", "freshness", "lineage", "non-fallback"),
        },
        "portfolio.factor_risk_metrics": {
            "sourceType": "cache_snapshot",
            "runtimeState": "configured_cache_only_diagnostic",
            "providerCategory": "portfolio_diagnostic_gap",
            "surface": "portfolio",
            "cacheRequired": True,
            "keyRequired": False,
            "paidDataLikelyRequired": False,
            "hint": ("stored", "freshness", "lineage", "non-fallback"),
        },
        "portfolio.benchmark_return_history": {
            "sourceType": "cache_snapshot",
            "runtimeState": "configured_cache_only_diagnostic",
            "providerCategory": "portfolio_diagnostic_gap",
            "surface": "portfolio",
            "cacheRequired": True,
            "keyRequired": False,
            "paidDataLikelyRequired": False,
            "hint": ("stored", "freshness", "lineage", "non-fallback"),
        },
        "watchlist.scanner_score_snapshot": {
            "sourceType": "cache_snapshot",
            "runtimeState": "configured_cache_only_diagnostic",
            "providerCategory": "watchlist_diagnostic_gap",
            "surface": "watchlist",
            "cacheRequired": True,
            "keyRequired": False,
            "paidDataLikelyRequired": False,
            "hint": ("watchlist", "score-grade", "never"),
        },
        "watchlist.score_refresh_freshness": {
            "sourceType": "cache_snapshot",
            "runtimeState": "configured_cache_only_diagnostic",
            "providerCategory": "watchlist_diagnostic_gap",
            "surface": "watchlist",
            "cacheRequired": True,
            "keyRequired": False,
            "paidDataLikelyRequired": False,
            "hint": ("watchlist", "score-grade", "never"),
        },
        "watchlist.no_score_stale_state": {
            "sourceType": "missing",
            "runtimeState": "missing_provider_configuration",
            "providerCategory": "watchlist_diagnostic_gap",
            "surface": "watchlist",
            "cacheRequired": True,
            "keyRequired": False,
            "paidDataLikelyRequired": False,
            "hint": ("watchlist", "score-grade", "never"),
        },
        "watchlist.source_confidence_preservation": {
            "sourceType": "cache_snapshot",
            "runtimeState": "configured_cache_only_diagnostic",
            "providerCategory": "watchlist_diagnostic_gap",
            "surface": "watchlist",
            "cacheRequired": True,
            "keyRequired": False,
            "paidDataLikelyRequired": False,
            "hint": ("watchlist", "score-grade", "never"),
        },
        "options_lab.synthetic_fixture_chain": {
            "sourceType": "synthetic_fixture",
            "runtimeState": "synthetic_fixture_only_diagnostic",
            "providerCategory": "options_lab_diagnostic_gap",
            "surface": "options_lab",
            "cacheRequired": True,
            "keyRequired": False,
            "paidDataLikelyRequired": False,
            "hint": ("diagnostic-only", "never", "score-grade"),
        },
        "options_lab.disabled_live_provider_stubs": {
            "sourceType": "disabled_live_stub",
            "runtimeState": "disabled_live_stub_diagnostic",
            "providerCategory": "options_lab_diagnostic_gap",
            "surface": "options_lab",
            "cacheRequired": False,
            "keyRequired": False,
            "paidDataLikelyRequired": False,
            "hint": ("diagnostic-only", "never", "score-grade"),
        },
        "options_lab.bid_ask_liquidity_gate": {
            "sourceType": "missing",
            "runtimeState": "missing_provider_configuration",
            "providerCategory": "options_lab_diagnostic_gap",
            "surface": "options_lab",
            "cacheRequired": True,
            "keyRequired": True,
            "paidDataLikelyRequired": True,
            "hint": ("bid/ask", "OI/volume", "IV/Greeks", "IV rank/history"),
        },
        "options_lab.oi_volume_gate": {
            "sourceType": "missing",
            "runtimeState": "missing_provider_configuration",
            "providerCategory": "options_lab_diagnostic_gap",
            "surface": "options_lab",
            "cacheRequired": True,
            "keyRequired": True,
            "paidDataLikelyRequired": True,
            "hint": ("bid/ask", "OI/volume", "IV/Greeks", "IV rank/history"),
        },
        "options_lab.iv_greeks_gate": {
            "sourceType": "missing",
            "runtimeState": "missing_provider_configuration",
            "providerCategory": "options_lab_diagnostic_gap",
            "surface": "options_lab",
            "cacheRequired": True,
            "keyRequired": True,
            "paidDataLikelyRequired": True,
            "hint": ("bid/ask", "OI/volume", "IV/Greeks", "IV rank/history"),
        },
        "options_lab.iv_rank_history": {
            "sourceType": "missing",
            "runtimeState": "missing_provider_configuration",
            "providerCategory": "options_lab_diagnostic_gap",
            "surface": "options_lab",
            "cacheRequired": True,
            "keyRequired": True,
            "paidDataLikelyRequired": True,
            "hint": ("bid/ask", "OI/volume", "IV/Greeks", "IV rank/history"),
        },
    }

    for provider_id, entry in expected.items():
        row = _row_by_id(payload, provider_id)
        hint = row["remediationHint"] or ""

        assert row["providerCategory"] == entry["providerCategory"]
        assert row["sourceType"] == entry["sourceType"]
        assert row["runtimeState"] == entry["runtimeState"]
        assert row["productAffectedSurfaces"] == [entry["surface"]]
        assert row["supportedCapabilities"] == [provider_id]
        assert row["diagnosticOnly"] is True
        assert row["inertMetadataOnly"] is True
        assert row["observationOnly"] is True
        assert row["scoreContributionAllowed"] is False
        assert row["scoreEligible"] is False
        assert row["noDefaultLiveHttpCalls"] is True
        assert row["cacheRequired"] is entry["cacheRequired"]
        assert row["keyRequired"] is entry["keyRequired"]
        assert row["paidDataLikelyRequired"] is entry["paidDataLikelyRequired"]
        assert hint
        assert all(token in hint for token in entry["hint"])


def test_cn_hk_connect_flow_provider_ops_reports_cache_only_config_without_secret_values() -> None:
    payload = ProviderOperationsMatrixService(
        env={
            "CN_HK_CONNECT_FLOW_PROVIDER_ENABLED": "true",
            "CN_HK_CONNECT_FLOW_CACHE_PATH": "/tmp/private-cn-hk-flow-cache.json",
            "CN_HK_CONNECT_FLOW_API_KEY": "super-secret-token-value",
        },
        spec_finder=lambda _: None,
    ).build_matrix()

    cn_hk_flow = _row_by_id(payload, "authorized.cn_hk_connect_flow")

    assert payload["diagnosticOnly"] is True
    assert payload["metadata"]["secretValuesIncluded"] is False
    assert cn_hk_flow["runtimeState"] == "configured_cache_only_diagnostic"
    assert cn_hk_flow["credentialState"] == "present"
    assert cn_hk_flow["dependencyState"] == "not_required"
    assert cn_hk_flow["observationOnly"] is True
    assert cn_hk_flow["scoreContributionAllowed"] is False
    assert cn_hk_flow["scoreEligible"] is False
    assert cn_hk_flow["noDefaultLiveHttpCalls"] is True
    assert cn_hk_flow["diagnosticOnly"] is True
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert "super-secret-token-value" not in serialized
    assert "/tmp/private-cn-hk-flow-cache.json" not in serialized


def test_cn_hk_connect_flow_provider_ops_reports_explicit_disabled_cache_config() -> None:
    payload = ProviderOperationsMatrixService(
        env={
            "CN_HK_CONNECT_FLOW_PROVIDER_ENABLED": "false",
            "CN_HK_CONNECT_FLOW_CACHE_PATH": "/tmp/private-cn-hk-flow-cache.json",
        },
        spec_finder=lambda _: None,
    ).build_matrix()

    cn_hk_flow = _row_by_id(payload, "authorized.cn_hk_connect_flow")

    assert cn_hk_flow["runtimeState"] == "disabled"
    assert cn_hk_flow["credentialState"] == "present"
    assert cn_hk_flow["scoreContributionAllowed"] is False
    assert cn_hk_flow["scoreEligible"] is False
    assert "provider_disabled" in cn_hk_flow["reasonCodes"]


def test_fed_liquidity_provider_ops_projects_aggregate_bundle_without_key_or_secret_exposure() -> None:
    payload = ProviderOperationsMatrixService(
        env={"FRED_API_KEY": "super-secret-token-value"},
        spec_finder=lambda _: None,
    ).build_matrix()

    fed = _row_by_id(payload, "official_public.fed_liquidity")

    assert fed["sourceType"] == "official_public"
    assert fed["credentialState"] == "not_required"
    assert fed["keyRequired"] is False
    assert fed["reasonCodes"][0] == "official_macro_transport_supported"
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert "super-secret-token-value" not in serialized
    assert "FRED_API_KEY" not in serialized


def test_fed_liquidity_provider_ops_projection_remains_non_scoring_for_partial_or_stale_rows() -> None:
    projection = ProviderOperationsMatrixService._project_official_fed_liquidity_runtime_bundle(
        [
            _fed_liquidity_runtime_row("WALCL"),
            _fed_liquidity_runtime_row("RRPONTSYD"),
            _fed_liquidity_runtime_row(
                "WTREGEN",
                freshness="stale",
                score_contribution_allowed=False,
                is_stale=True,
            ),
        ]
    )

    assert projection["runtimeState"] == "aggregate_supported_runtime_evidence_partial"
    assert projection["observationOnly"] is True
    assert projection["sourceAuthorityAllowed"] is False
    assert projection["scoreContributionAllowed"] is False
    assert projection["fulfilledMetrics"] == ["WALCL", "RRPONTSYD"]
    assert projection["missingMetrics"] == ["WTREGEN", "WRESBAL"]
    assert projection["degradationReason"] == "fed_liquidity_required_series_missing_or_stale"
    assert "stale_official_macro_evidence" in projection["reasonCodes"]
    assert "missing_official_macro_row" in projection["reasonCodes"]


def test_fed_liquidity_provider_ops_projection_allows_score_only_for_full_existing_gated_rows() -> None:
    projection = ProviderOperationsMatrixService._project_official_fed_liquidity_runtime_bundle(
        [
            _fed_liquidity_runtime_row("WALCL"),
            _fed_liquidity_runtime_row("RRPONTSYD"),
            _fed_liquidity_runtime_row("WTREGEN"),
            _fed_liquidity_runtime_row("WRESBAL"),
        ]
    )

    assert projection["runtimeState"] == "aggregate_supported_runtime_evidence_ready"
    assert projection["observationOnly"] is False
    assert projection["sourceAuthorityAllowed"] is True
    assert projection["scoreContributionAllowed"] is True
    assert projection["trustLevel"] == "score_grade"
    assert projection["fulfilledMetrics"] == ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert projection["missingMetrics"] == []
    assert projection["coverageCount"] == 4
    assert projection["degradationReason"] is None


def test_cn_money_market_provider_ops_surfaces_valid_cache_diagnostic_without_paths_or_scoring(tmp_path) -> None:
    cache_path = tmp_path / "private-cn-money-market-cache.json"
    cache_path.write_text(
        json.dumps(_cn_money_market_cache_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    payload = ProviderOperationsMatrixService(
        env={
            OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV: str(cache_path),
            "CN_MONEY_MARKET_RATES_API_KEY": "super-secret-token-value",
        },
        spec_finder=lambda _: None,
    ).build_matrix()

    cn_money = _row_by_id(payload, OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID)

    assert payload["diagnosticOnly"] is True
    assert payload["metadata"]["externalProviderCalls"] is False
    assert payload["metadata"]["secretValuesIncluded"] is False
    assert cn_money["sourceType"] == "official_public"
    assert cn_money["sourceTier"] == "official_public"
    assert cn_money["runtimeState"] == "configured_cache_only_diagnostic"
    assert cn_money["credentialState"] == "not_required"
    assert cn_money["dependencyState"] == "not_required"
    assert cn_money["keyRequired"] is False
    assert cn_money["paidDataLikelyRequired"] is False
    assert cn_money["observationOnly"] is True
    assert cn_money["sourceAuthorityAllowed"] is True
    assert cn_money["scoreContributionAllowed"] is False
    assert cn_money["scoreEligible"] is False
    assert cn_money["fulfilledMetrics"] == ["DR007", "SHIBOR_ON"]
    assert cn_money["missingMetrics"] == []
    assert cn_money["coverageCount"] == 2
    assert cn_money["sourceFreshnessEvidence"]["externalProviderCalls"] is False
    assert cn_money["sourceFreshnessEvidence"]["coverageRatio"] == 1.0
    assert cn_money["reasonCodes"] == ["official_cn_money_market_rates_cache_valid_diagnostic_only"]
    assert cn_money["missingProviderReason"] is None
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert "super-secret-token-value" not in serialized
    assert str(cache_path) not in serialized
    assert cache_path.name not in serialized


def test_cn_money_market_provider_ops_reports_invalid_cache_diagnostic_without_raw_path(tmp_path) -> None:
    cache_path = tmp_path / "private-cn-money-market-cache.json"
    cache_path.write_text("{not-json", encoding="utf-8")
    payload = ProviderOperationsMatrixService(
        env={OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV: str(cache_path)},
        spec_finder=lambda _: None,
    ).build_matrix()

    cn_money = _row_by_id(payload, OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID)

    assert cn_money["runtimeState"] == "configured_cache_diagnostic_unavailable"
    assert cn_money["sourceType"] == "missing"
    assert cn_money["sourceAuthorityAllowed"] is False
    assert cn_money["scoreContributionAllowed"] is False
    assert cn_money["scoreEligible"] is False
    assert "malformed_payload" in cn_money["reasonCodes"]
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert str(cache_path) not in serialized
    assert cache_path.name not in serialized


def test_polygon_us_grouped_daily_projection_is_visible_without_secret_or_official_overclaim(
    monkeypatch,
) -> None:
    monkeypatch.setenv("POLYGON_API_KEY", "polygon-secret-token-value")

    payload = ProviderOperationsMatrixService(
        env=os.environ,
        spec_finder=lambda _: None,
    ).build_matrix()
    text = json.dumps(payload, sort_keys=True)

    assert "polygon-secret-token-value" not in text
    assert "POLYGON_API_KEY" not in text

    polygon = _row_by_id(payload, "polygon_us_grouped_daily")
    assert polygon["sourceLabel"] == "Polygon grouped daily US equities (computed breadth)"
    assert polygon["authorityBasis"] == "computed_from_authorized_polygon_history"
    assert polygon["universe"] == "polygon_us_grouped_daily_ex_otc"
    assert polygon["sourceType"] == "authorized_licensed_feed"
    assert polygon["sourceTier"] == "official_or_authorized_licensed_feed"
    assert polygon["credentialState"] == "present"
    assert polygon["keyRequired"] is True
    assert polygon["diagnosticOnly"] is True
    assert polygon["officialExchangePublishedBreadth"] is False
    assert polygon["fullBreadthAuthority"] is False
    assert polygon["sourceAuthorityAllowed"] is True
    assert polygon["scoreContributionAllowed"] is True
    assert polygon["scoreEligible"] is False
    assert polygon["fulfilledMetrics"] == [
        "ADVANCERS",
        "DECLINERS",
        "UNCHANGED",
        "ADVANCE_DECLINE_RATIO",
    ]
    assert polygon["missingMetrics"] == ["NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO"]
    assert polygon["reasonCodes"] == ["polygon_high_low_history_unavailable"]
    assert polygon["coverageCount"] is None
    assert polygon["sourceFreshnessEvidence"] == {
        "freshness": "delayed",
        "freshnessPolicy": "polygon_grouped_daily_eod_recent_completed_us_weekday",
        "isFallback": False,
        "isPartial": True,
        "isUnavailable": False,
    }

    full_breadth = _row_by_id(payload, "official_or_authorized.us_market_breadth")
    assert full_breadth["sourceType"] == "missing"
    assert full_breadth["runtimeState"] == "missing_provider_configuration"
    assert full_breadth["missingProviderReason"] == "authorized_us_market_breadth_feed_not_configured"
    assert full_breadth["scoreContributionAllowed"] is False
    assert full_breadth["scoreEligible"] is False


def test_blocked_provider_rows_remain_non_score_grade() -> None:
    payload = ProviderOperationsMatrixService(env={}, spec_finder=lambda _: None).build_matrix()

    expected_source_types = {
        "akshare": "public_proxy",
        "akshare_existing_baseline": "public_proxy",
        "yfinance_current_baseline": "unofficial_proxy",
        "yahooquery": "unofficial_proxy",
        "authorized.us_etf_flow": "missing",
        "options_lab.synthetic_fixture_chain": "synthetic_fixture",
        "options_lab.disabled_live_provider_stubs": "disabled_live_stub",
    }
    for provider_id, source_type in expected_source_types.items():
        row = _row_by_id(payload, provider_id)
        assert row["scoreEligible"] is False
        assert row["scoreContributionAllowed"] is False
        assert row["sourceType"] == source_type


def test_score_authority_helper_keeps_fallback_rows_fail_closed() -> None:
    row = SimpleNamespace(
        source_tier="fallback_static",
        trust_level="score_grade",
        observation_only=False,
        source_authority_allowed=True,
        score_contribution_allowed=True,
        source_freshness_evidence={"freshness": "fallback", "isFallback": True},
    )

    assert ProviderOperationsMatrixService._score_eligible(row, "fallback_static") is False


def test_score_authority_helper_fails_closed_without_freshness_evidence() -> None:
    row = SimpleNamespace(
        source_tier="local_cache",
        trust_level="reproducible_local_or_stored",
        observation_only=False,
        source_authority_allowed=True,
        score_contribution_allowed=True,
        source_freshness_evidence=None,
    )

    assert ProviderOperationsMatrixService._score_eligible(row, "cache_snapshot") is False


def test_score_authority_helper_fails_closed_for_partial_freshness_evidence() -> None:
    row = SimpleNamespace(
        source_tier="official_or_authorized_licensed_feed",
        trust_level="score_grade",
        observation_only=False,
        source_authority_allowed=True,
        score_contribution_allowed=True,
        source_freshness_evidence={
            "freshness": "delayed",
            "isFallback": False,
            "isPartial": True,
            "isUnavailable": False,
        },
    )

    assert ProviderOperationsMatrixService._score_eligible(
        row,
        "authorized_licensed_feed",
    ) is False


def test_generic_runtime_capability_score_permission_fails_closed_without_explicit_gate() -> None:
    assert ProviderOperationsMatrixService._generic_runtime_score_contribution_allowed(
        "cache_snapshot"
    ) is False
    for source_type in (
        "public_proxy",
        "unofficial_proxy",
        "fallback_static",
        "synthetic_fixture",
        "missing",
        "disabled_live_stub",
        "official_public",
        "authorized_licensed_feed",
    ):
        assert (
            ProviderOperationsMatrixService._generic_runtime_score_contribution_allowed(source_type)
            is False
        )


def test_runtime_metadata_rows_do_not_claim_score_contribution_without_explicit_projection() -> None:
    payload = ProviderOperationsMatrixService(env={}, spec_finder=lambda _: None).build_matrix()

    for provider_id in ("alpaca", "fmp", "gnews", "social_sentiment", "tavily", "yahoo_yfinance"):
        row = _row_by_id(payload, provider_id)
        assert row["runtimeState"] == "runtime_metadata"
        assert row["scoreContributionAllowed"] is False
        assert row["scoreEligible"] is False

    for provider_id in ("local_cache", "local_inference", "local_news_cache", "local_ohlcv"):
        row = _row_by_id(payload, provider_id)
        assert row["sourceType"] == "cache_snapshot"
        assert row["runtimeState"] == "runtime_metadata"
        assert row["sourceFreshnessEvidence"] is None
        assert row["scoreContributionAllowed"] is False
        assert row["scoreEligible"] is False
        assert "capability_metadata_only" in row["reasonCodes"]
        assert "activation_not_verified" in row["reasonCodes"]
        assert "freshness_not_evaluated" in row["reasonCodes"]


def test_secret_values_are_not_emitted_from_readiness_or_credentials(monkeypatch) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "super-secret-token-value")

    payload = ProviderOperationsMatrixService(
        env=os.environ,
        spec_finder=lambda name: object() if name == "tushare" else None,
    ).build_matrix()
    text = json.dumps(payload, sort_keys=True)

    assert "super-secret-token-value" not in text
    assert "TUSHARE_TOKEN" not in text
    tushare = _row_by_id(payload, "tushare_pro")
    assert tushare["credentialState"] == "present"
    assert tushare["dependencyState"] == "installed"


def test_matrix_does_not_call_provider_runtime_probes_or_cache_refresh() -> None:
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("data_provider") or name == "src.services.market_cache":
            raise AssertionError(f"runtime import blocked: {name}")
        return original_import(name, globals, locals, fromlist, level)

    with (
        patch("builtins.__import__", side_effect=guarded_import),
        patch(
            "src.services.provider_operations_matrix_service.DataSourceRouter.resolve",
            wraps=ProviderOperationsMatrixService._router.resolve,
        ) as router_resolve,
    ):
        payload = ProviderOperationsMatrixService(env={}, spec_finder=lambda _: None).build_matrix()

    assert payload["metadata"]["externalProviderCalls"] is False
    assert payload["metadata"]["providerProbesForced"] is False
    assert payload["metadata"]["cacheMutation"] is False
    assert router_resolve.call_count > 0
