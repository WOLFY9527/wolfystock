# -*- coding: utf-8 -*-
"""Market Overview provider freshness and proxy truth contracts."""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone

from api.deps import CurrentUser
from api.v1.endpoints import market_overview
from src.services.market_overview_service import (
    MarketOverviewService,
    get_freshness_status,
)


CN_TZ = timezone(timedelta(hours=8))
ALLOWED_FRESHNESS_STATES = {
    "live",
    "delayed",
    "cached",
    "stale",
    "unavailable",
    "proxy",
}
CONSUMER_SAFE_FRESHNESS_KEYS = {
    "state",
    "label",
    "available",
    "sourceConfidence",
    "isProxy",
    "isStale",
    "isUnavailable",
    "asOf",
    "sourceLabel",
    "dataSource",
    "degradationReason",
    "proxyFor",
    "proxySymbol",
    "proxyLabel",
}
ENGINEERING_REASON_ALIASES = {
    "provider_missing",
    "fallback_source",
    "mock",
    "fallback",
}


def test_market_overview_optional_auth_transitional_user_projects_as_anonymous_actor() -> None:
    current_user = CurrentUser(
        user_id="bootstrap-admin",
        username="admin",
        display_name="Bootstrap Admin",
        role="admin",
        is_admin=True,
        is_authenticated=False,
        transitional=True,
        auth_enabled=False,
    )

    actor = market_overview._actor(current_user)

    assert actor == {"actor_type": "anonymous", "role": "anonymous", "display_name": "Anonymous"}
    assert "user_id" not in actor
    assert "session_id" not in actor


def test_freshness_helper_normalizes_core_states_without_silent_upgrade() -> None:
    now = datetime(2026, 5, 6, 10, 0, tzinfo=CN_TZ)

    live = get_freshness_status(
        now.isoformat(),
        "crypto",
        "binance",
        False,
        source_type="exchange_public",
        now=now,
    )
    delayed = get_freshness_status(
        (now - timedelta(minutes=30)).isoformat(),
        "fx_commodity",
        "yfinance_proxy",
        False,
        source_type="unofficial_proxy",
        now=now,
    )
    cached = get_freshness_status(
        (now - timedelta(minutes=90)).isoformat(),
        "macro_rate",
        "cached",
        False,
        source_type="cache",
        now=now,
    )
    stale = get_freshness_status(
        (now - timedelta(days=3)).isoformat(),
        "equity_index",
        "yfinance_proxy",
        False,
        source_type="unofficial_proxy",
        now=now,
    )
    unavailable = get_freshness_status(
        now.isoformat(),
        "equity_index",
        "unavailable",
        False,
        source_type="missing",
        now=now,
    )
    proxy = get_freshness_status(
        now.isoformat(),
        "equity_index",
        "yfinance_proxy",
        False,
        source_type="unofficial_proxy",
        now=now,
    )

    assert live["freshness"] == "live"
    assert delayed["freshness"] == "delayed"
    assert cached["freshness"] == "cached"
    assert stale["freshness"] == "stale"
    assert stale["isStale"] is True
    assert unavailable["freshness"] == "unavailable"
    assert unavailable["isUnavailable"] is True
    assert unavailable["isFallback"] is False
    assert proxy["freshness"] == "delayed"
    assert proxy["isProxy"] is True

    observation_time = importlib.import_module("src.services.market_observation_time")
    missing = observation_time.extract_authoritative_market_time(
        {
            "updatedAt": now.isoformat(),
            "attemptedAt": now.isoformat(),
            "receivedAt": now.isoformat(),
            "generatedAt": now.isoformat(),
            "cachedAt": now.isoformat(),
            "persistedAt": now.isoformat(),
        }
    )
    observed = observation_time.extract_authoritative_market_time(
        {"observedAt": "2026-05-06T09:30:00+08:00"}
    )
    effective = observation_time.extract_authoritative_market_time(
        {"observationDate": "2026-05-05"}
    )
    assert missing == (None, "missing")
    assert observed == ("2026-05-06T09:30:00+08:00", "provider_timestamp")
    assert effective == ("2026-05-05", "provider_effective_date")

    service = MarketOverviewService()
    panel = service._with_market_meta(
        {
            "source": "binance",
            "sourceType": "exchange_public",
            "updatedAt": now.isoformat(),
            "items": [],
        },
        "crypto",
    )
    item = service._with_item_meta(
        {
            "symbol": "BTC",
            "value": 100.0,
            "source": "binance",
            "sourceType": "exchange_public",
            "updatedAt": now.isoformat(),
        },
        "crypto",
        {**panel, "asOf": "2026-05-06T09:30:00+08:00"},
    )
    evidence = service._build_evidence_snapshot(panel, "crypto")
    assert panel["updatedAt"] == now.isoformat()
    assert panel["asOf"] is None
    assert panel["freshness"] == "unavailable"
    assert panel["providerFreshness"]["available"] is False
    assert item["asOf"] is None
    assert item["freshness"] == "unavailable"
    assert item["sourceAuthorityAllowed"] is False
    assert item["scoreContributionAllowed"] is False
    assert evidence["asOf"] is None
    assert service._sina_as_of("", "") is None
    assert service._sina_as_of("not-a-date", "not-a-time") is None


def test_market_meta_projects_consumer_safe_freshness_summary_and_specific_reason() -> None:
    service = MarketOverviewService()
    stale_as_of = (datetime.now(CN_TZ) - timedelta(days=3)).isoformat(timespec="seconds")

    payload = service._with_market_meta(
        {
            "source": "yfinance_proxy",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_proxy",
            "asOf": stale_as_of,
            "updatedAt": stale_as_of,
            "items": [{"symbol": "SPX", "value": 520.0}],
            "fallbackReason": "provider_missing",
        },
        "equity_index",
    )

    freshness = payload["providerFreshness"]
    assert payload["freshness"] == "stale"
    assert freshness["state"] == "stale"
    assert freshness["available"] is False
    assert freshness["isStale"] is True
    assert set(freshness) <= CONSUMER_SAFE_FRESHNESS_KEYS
    assert payload["degradationReason"] == "stale_source"
    assert payload["fallbackReason"] == "stale_source"
    assert payload["fallbackReason"] not in ENGINEERING_REASON_ALIASES


def test_spy_proxy_for_spx_is_explicit_and_never_official_index() -> None:
    service = MarketOverviewService()
    now = datetime.now(CN_TZ).isoformat(timespec="seconds")

    proxy_item = service._with_item_meta(
        {
            "symbol": "SPX",
            "label": "S&P 500 proxy (SPY ETF)",
            "value": 520.0,
            "source": "yfinance_proxy",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_proxy",
            "asOf": now,
            "updatedAt": now,
            "proxyFor": "SPX",
            "proxySymbol": "SPY",
            "proxyLabel": "S&P 500",
            "isProxy": True,
            "isFallback": False,
        },
        "equity_index",
        {"source": "yfinance_proxy", "sourceType": "unofficial_proxy", "asOf": now, "updatedAt": now},
    )

    freshness = proxy_item["providerFreshness"]
    assert proxy_item["freshness"] == "proxy"
    assert proxy_item["sourceType"] == "unofficial_proxy"
    assert proxy_item["isProxy"] is True
    assert proxy_item["sourceConfidence"] == "proxy"
    assert proxy_item["sourceAuthorityAllowed"] is False
    assert proxy_item["scoreContributionAllowed"] is False
    assert proxy_item["degradationReason"] == "etf_proxy_for_index"
    assert freshness["state"] == "proxy"
    assert freshness["isProxy"] is True
    assert freshness["proxyFor"] == "SPX"
    assert freshness["proxySymbol"] == "SPY"
    assert "official" not in proxy_item["label"].lower()


def test_vix_proxy_item_projects_consistent_authority_and_freshness() -> None:
    service = MarketOverviewService()
    now = datetime.now(CN_TZ).isoformat(timespec="seconds")

    proxy_item = service._with_item_meta(
        {
            "symbol": "VIX",
            "label": "VIX",
            "value": 17.1,
            "source": "yfinance",
            "sourceId": "yfinance:^VIX",
            "sourceType": "public_proxy",
            "asOf": now,
            "updatedAt": now,
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        },
        "volatility",
        {"source": "yfinance", "sourceType": "public_proxy", "asOf": now, "updatedAt": now},
    )

    freshness = proxy_item["providerFreshness"]
    snapshot = proxy_item["volatilityAuthoritySnapshot"]

    assert proxy_item["freshness"] == "delayed"
    assert proxy_item["freshnessState"] == "delayed"
    assert freshness["state"] == "delayed"
    assert freshness["isProxy"] is True
    assert freshness["sourceConfidence"] == "proxy"
    assert proxy_item["sourceAuthorityState"] == "proxy"
    assert proxy_item["sourceAuthorityAllowed"] is False
    assert proxy_item["scoreContributionAllowed"] is False
    assert proxy_item["consumerEligibility"]["marketOverview"] is True
    assert proxy_item["consumerEligibility"]["liquidity"] is False
    assert proxy_item["scoreAuthorityEligible"] is False
    assert snapshot["authorityState"] == "proxy"
    assert snapshot["freshnessState"] == "delayed"
    assert snapshot["scoreEligibility"]["allowed"] is False


def test_mixed_provider_bundle_uses_worst_truthful_freshness_without_generic_missing() -> None:
    service = MarketOverviewService()
    now = datetime.now(CN_TZ).isoformat(timespec="seconds")

    payload = service._with_market_meta(
        {
            "source": "mixed",
            "sourceLabel": "Mixed",
            "sourceType": "mixed",
            "asOf": now,
            "updatedAt": now,
            "fallbackUsed": True,
            "items": [
                {"symbol": "US10Y", "value": 4.2, "source": "treasury", "sourceType": "official_public", "freshness": "delayed"},
                {"symbol": "DXY", "value": 104.1, "source": "yfinance_proxy", "sourceType": "unofficial_proxy", "isProxy": True},
                {"symbol": "DR007", "value": None, "source": "unavailable", "sourceType": "missing", "freshness": "unavailable", "isUnavailable": True},
            ],
        },
        "macro_rate",
    )

    assert payload["freshness"] == "unavailable"
    assert payload["isPartial"] is True
    assert payload["isUnavailable"] is False
    assert payload["providerFreshness"]["state"] == "unavailable"
    assert payload["degradationReason"] == "partial_unavailable_inputs"
    assert payload.get("fallbackReason") != "provider_missing"


def test_crypto_fallback_contains_no_static_prices_or_fake_changes() -> None:
    payload = MarketOverviewService()._fallback_crypto_market_snapshot()

    assert payload["source"] == "unavailable"
    assert payload["freshness"] == "unavailable"
    assert payload["isUnavailable"] is True
    assert payload["providerFreshness"]["state"] == "unavailable"
    assert payload["updatedAt"]
    assert payload["asOf"] is None
    for item in payload["items"]:
        assert item["source"] == "unavailable"
        assert item["sourceFreshnessEvidence"]["freshness"] == "unavailable"
        assert item["value"] is None
        assert item["price"] is None
        assert item["trend"] == []
        assert item["updatedAt"]
        assert item["asOf"] is None


def test_cn_hk_flow_fallback_contains_no_static_flow_values_or_score_authority() -> None:
    payload = MarketOverviewService()._fallback_cn_flows_snapshot()

    assert payload["source"] == "unavailable"
    assert payload["sourceClass"] == "disabled_live_stub"
    assert payload["freshness"] == "unavailable"
    assert payload["freshnessState"] == "unavailable"
    assert payload["isUnavailable"] is True
    assert payload["fallbackUsed"] is False
    assert payload["sourceAuthorityAllowed"] is False
    assert payload["sourceAuthorityState"] == "unavailable"
    assert payload["scoreContributionAllowed"] is False
    assert payload["scoreAuthorityEligible"] is False
    assert payload["updatedAt"]
    assert payload["asOf"] is None
    for item in payload["items"]:
        assert item["source"] == "unavailable"
        assert item["sourceClass"] == "disabled_live_stub"
        assert item["sourceFreshnessEvidence"]["freshness"] == "unavailable"
        assert item["value"] is None
        assert item["price"] is None
        assert item["trend"] == []
        assert item["change"] is None
        assert item["changePercent"] is None
        assert item["sourceAuthorityAllowed"] is False
        assert item["scoreAuthorityEligible"] is False
        assert item["updatedAt"]
        assert item["asOf"] is None
