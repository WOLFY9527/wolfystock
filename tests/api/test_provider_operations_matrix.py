# -*- coding: utf-8 -*-
"""Admin provider operations matrix API tests."""

from __future__ import annotations

import builtins
import json
import os
from datetime import datetime, timedelta, timezone
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
    assert fed["sourceType"] == "missing"
    assert fed["sourceTier"] == "official_public"
    assert fed["runtimeState"] == "missing_provider_configuration"
    assert fed["credentialState"] == "not_required"
    assert fed["dependencyState"] == "not_required"
    assert fed["missingProviderReason"] == "official_fed_liquidity_contract_not_configured"
    assert fed["paidDataLikelyRequired"] is False
    assert fed["keyRequired"] is False
    assert fed["scoreContributionAllowed"] is False
    assert fed["scoreEligible"] is False
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
    assert futures["requiredSourceTiers"] == ["exchange_or_broker_authorized_feed"]
    assert futures["scoreEligibilityGates"] == [
        "configured_authorized_index_futures_bundle_and_extended_hours_freshness"
    ]
    assert futures["contractCoverageUniverses"] == ["nq_es_ym_rty_extended_hours_bundle"]
    assert {"market_overview", "liquidity_impulse"}.issubset(set(futures["affectedSurfaces"]))
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
    assert {
        "missing_provider_configuration",
        "cache_required",
        "authorization_required",
        "taxonomy_to_real_flow_mapping_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(rotation_flow["routerReasonCodes"]))


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


def test_weak_and_proxy_providers_remain_non_score_grade() -> None:
    payload = ProviderOperationsMatrixService(env={}, spec_finder=lambda _: None).build_matrix()

    for provider_id in (
        "akshare",
        "akshare_existing_baseline",
        "yfinance_current_baseline",
        "yahooquery",
    ):
        row = _row_by_id(payload, provider_id)
        assert row["scoreEligible"] is False
        assert row["scoreContributionAllowed"] is False
        assert row["sourceType"] in {"public_proxy", "unofficial_proxy"}
        assert row["trustLevel"] in {"weak", "usable_with_caution"}


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
