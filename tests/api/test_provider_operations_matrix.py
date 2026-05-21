# -*- coding: utf-8 -*-
"""Admin provider operations matrix API tests."""

from __future__ import annotations

import builtins
import json
import os
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import admin_provider_operations_matrix
from src.services.provider_operations_matrix_service import (
    ProviderOperationsMatrixService,
)


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
