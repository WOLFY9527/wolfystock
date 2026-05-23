# -*- coding: utf-8 -*-
"""Contracts that freeze current /market/us-breadth proxy and fallback behavior."""

from __future__ import annotations

import json
import os
from unittest.mock import Mock, patch

from api.v1.endpoints import market
from src.services.market_data_source_registry import project_source_provenance
from src.services.market_cache import market_cache
from src.services.market_overview_service import MarketOverviewService


def setup_function() -> None:
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    os.environ.pop("POLYGON_API_KEY", None)


def teardown_function() -> None:
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()


def test_market_us_breadth_endpoint_delegates_to_market_overview_service() -> None:
    service = Mock()
    service.get_us_breadth.return_value = {"source": "yfinance_proxy", "items": [{"symbol": "SECTORS_UP"}]}

    with patch("api.v1.endpoints.market.MarketOverviewService", return_value=service):
        payload = market.get_us_breadth()

    assert payload["items"][0]["symbol"] == "SECTORS_UP"
    service.get_us_breadth.assert_called_once()


def test_market_us_breadth_current_proxy_snapshot_stays_proxy_not_exchange_breadth() -> None:
    service = MarketOverviewService()
    quotes = {
        "XLK": {"value": 220.0, "change_pct": 1.8, "trend": [216.0, 220.0], "volume": 10_000_000},
        "XLF": {"value": 44.0, "change_pct": -0.4, "trend": [44.2, 44.0], "volume": 8_000_000},
        "XLV": {"value": 146.0, "change_pct": 0.7, "trend": [144.8, 146.0], "volume": 7_000_000},
        "SPY": {"value": 520.0, "change_pct": 0.6, "trend": [516.0, 520.0], "volume": 60_000_000},
        "RSP": {"value": 168.0, "change_pct": 0.2, "trend": [167.0, 168.0], "volume": 4_000_000},
        "QQQ": {"value": 460.0, "change_pct": 1.1, "trend": [454.0, 460.0], "volume": 45_000_000},
        "IWM": {"value": 210.0, "change_pct": -0.3, "trend": [211.0, 210.0], "volume": 22_000_000},
    }

    with patch.object(service, "_latest_quote", side_effect=lambda ticker: quotes[ticker]):
        payload = service.get_us_breadth()

    symbols = {item["symbol"] for item in payload["items"]}
    assert payload["source"] == "yfinance_proxy"
    assert payload["sourceType"] == "unofficial_proxy"
    assert payload["isFallback"] is False
    assert payload["freshness"] in {"delayed", "cached", "stale"}
    assert payload["breadthClaimType"] == "representative_sample_breadth"
    assert payload["representativeSample"] is True
    assert payload["broadMarketClaimAllowed"] is False
    assert payload["sourceAuthorityAllowed"] is False
    assert payload["scoreContributionAllowed"] is False
    assert payload["sourceAuthorityReason"] == "representative_sample_not_full_market_breadth"
    assert "representative_sample_not_full_market_breadth" in payload["routeRejectedReasonCodes"]
    assert payload["authorityDiagnostics"]["reason"] == "authorized_us_market_breadth_feed_not_configured"
    assert "SECTORS_UP" in symbols
    assert "RSP_SPY" in symbols
    assert "ADVANCERS" not in symbols
    assert "NEW_HIGHS" not in symbols
    assert payload["items"][0]["sourceType"] == "unofficial_proxy"
    assert all(item["scoreContributionAllowed"] is False for item in payload["items"])
    assert all(item["broadMarketClaimAllowed"] is False for item in payload["items"])


def test_market_us_breadth_uses_polygon_computed_ad_when_authority_gate_passes() -> None:
    service = MarketOverviewService()
    activation = {
        "credentialsPresent": True,
        "providerConstructed": True,
        "probePassed": True,
        "observationDate": "2026-05-21",
        "previousObservationDate": "2026-05-20",
        "comparisonBasis": "previous_close",
        "asOf": "2026-05-21",
        "freshnessValid": True,
        "coverageCount": 12000,
        "previousCoverageCount": 11950,
        "comparisonCoverageCount": 11950,
        "sourceMetadataValid": True,
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "fulfilledMetrics": [
            "ADVANCERS",
            "DECLINERS",
            "UNCHANGED",
            "ADVANCE_DECLINE_RATIO",
        ],
        "missingMetrics": ["NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO"],
        "reasonCodes": ["polygon_high_low_history_unavailable"],
        "metrics": {
            "advancers": 7000,
            "decliners": 4000,
            "unchanged": 1000,
            "advanceDeclineRatio": 1.75,
            "newHighs": None,
            "newLows": None,
            "highLowRatio": None,
        },
        "source": "polygon_us_grouped_daily",
        "sourceLabel": "Polygon grouped daily US equities (computed breadth)",
        "sourceType": "authorized_licensed_feed",
        "sourceTier": "official_or_authorized_licensed_feed",
        "trustLevel": "score_grade_for_computed_ad_metrics_when_fresh",
        "authorityBasis": "computed_from_authorized_polygon_history",
        "universe": "polygon_us_grouped_daily_ex_otc",
        "officialExchangePublishedBreadth": False,
        "fullBreadthAuthority": False,
    }

    with patch(
        "src.services.market_overview_service.run_polygon_us_breadth_activation",
        return_value=activation,
    ):
        payload = service._fetch_us_breadth_snapshot()

    by_symbol = {item["symbol"]: item for item in payload["items"]}
    assert payload["source"] == "polygon_us_grouped_daily"
    assert payload["sourceLabel"] == "Polygon grouped daily US equities (computed breadth)"
    assert payload["breadthClaimType"] == "computed_authorized_polygon_grouped_daily_breadth"
    assert payload["breadthClaimScope"] == "advance_decline_only"
    assert payload["breadthCompleteness"] == "partial_ad_only"
    assert payload["officialExchangePublishedBreadth"] is False
    assert payload["fullBreadthAuthority"] is False
    assert payload["representativeSample"] is False
    assert payload["sourceAuthorityAllowed"] is True
    assert payload["scoreContributionAllowed"] is True
    assert payload["broadMarketClaimAllowed"] is False
    assert payload["comparisonBasis"] == "previous_close"
    assert payload["previousObservationDate"] == "2026-05-20"
    assert payload["comparisonCoverageCount"] == 11950
    assert payload["isPartial"] is True
    assert payload["authorityDiagnostics"]["reasonCodes"] == ["polygon_high_low_history_unavailable"]
    assert payload["authorityDiagnostics"]["comparisonBasis"] == "previous_close"
    assert by_symbol["ADVANCERS"]["value"] == 7000
    assert by_symbol["ADVANCERS"]["broadMarketClaimAllowed"] is False
    assert by_symbol["ADVANCERS"]["comparisonBasis"] == "previous_close"
    assert by_symbol["DECLINERS"]["value"] == 4000
    assert by_symbol["UNCHANGED"]["value"] == 1000
    assert by_symbol["ADVANCE_DECLINE_RATIO"]["value"] == 1.75
    assert by_symbol["NEW_HIGHS"]["value"] is None
    assert by_symbol["NEW_HIGHS"]["scoreContributionAllowed"] is False
    assert by_symbol["NEW_HIGHS"]["sourceAuthorityReason"] == "polygon_high_low_history_unavailable"


def test_market_us_breadth_projects_polygon_high_low_when_history_gates_pass() -> None:
    service = MarketOverviewService()
    activation = {
        "credentialsPresent": True,
        "providerConstructed": True,
        "probePassed": True,
        "observationDate": "2026-05-21",
        "previousObservationDate": "2026-05-20",
        "comparisonBasis": "previous_close",
        "asOf": "2026-05-21",
        "freshnessValid": True,
        "coverageCount": 12000,
        "previousCoverageCount": 11950,
        "comparisonCoverageCount": 11950,
        "highLowLookbackSessions": 252,
        "highLowEligibleCount": 11250,
        "highLowEligibleThreshold": 9600,
        "sourceMetadataValid": True,
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "broadMarketClaimAllowed": False,
        "officialExchangePublishedBreadth": False,
        "fullBreadthAuthority": False,
        "fulfilledMetrics": [
            "ADVANCERS",
            "DECLINERS",
            "UNCHANGED",
            "ADVANCE_DECLINE_RATIO",
            "NEW_HIGHS",
            "NEW_LOWS",
            "HIGH_LOW_RATIO",
        ],
        "missingMetrics": [],
        "reasonCodes": [],
        "metrics": {
            "advancers": 7000,
            "decliners": 4000,
            "unchanged": 1000,
            "advanceDeclineRatio": 1.75,
            "newHighs": 318,
            "newLows": 42,
            "highLowRatio": 7.571,
        },
        "source": "polygon_us_grouped_daily",
        "sourceLabel": "Polygon grouped daily US equities (computed breadth)",
        "sourceType": "authorized_licensed_feed",
        "sourceTier": "official_or_authorized_licensed_feed",
        "trustLevel": "score_grade_for_computed_ad_metrics_when_fresh",
        "authorityBasis": "computed_from_authorized_polygon_history",
        "universe": "polygon_us_grouped_daily_ex_otc",
    }

    payload = service._polygon_us_breadth_snapshot(
        activation,
        service._polygon_us_breadth_authority_diagnostic(activation),
    )

    by_symbol = {item["symbol"]: item for item in payload["items"]}
    assert payload["breadthClaimScope"] == "computed_polygon_ad_high_low"
    assert payload["breadthCompleteness"] == "computed_high_low_available"
    assert payload["officialExchangePublishedBreadth"] is False
    assert payload["fullBreadthAuthority"] is False
    assert payload["broadMarketClaimAllowed"] is False
    assert payload["isPartial"] is False
    assert payload["fulfilledMetrics"] == activation["fulfilledMetrics"]
    assert payload["missingMetrics"] == []
    assert payload["highLowEligibleCount"] == 11250
    assert payload["highLowEligibleThreshold"] == 9600
    assert "unavailable" not in payload["warning"].lower()
    assert by_symbol["NEW_HIGHS"]["value"] == 318
    assert by_symbol["NEW_HIGHS"]["scoreContributionAllowed"] is True
    assert by_symbol["NEW_HIGHS"]["sourceAuthorityReason"] is None
    assert by_symbol["NEW_LOWS"]["value"] == 42
    assert by_symbol["HIGH_LOW_RATIO"]["value"] == 7.571


def test_market_us_breadth_proxy_snapshot_projects_to_unofficial_proxy_not_exchange_public() -> None:
    service = MarketOverviewService()
    quotes = {
        "XLK": {"value": 220.0, "change_pct": 1.8, "trend": [216.0, 220.0], "volume": 10_000_000},
        "XLF": {"value": 44.0, "change_pct": -0.4, "trend": [44.2, 44.0], "volume": 8_000_000},
        "XLV": {"value": 146.0, "change_pct": 0.7, "trend": [144.8, 146.0], "volume": 7_000_000},
        "SPY": {"value": 520.0, "change_pct": 0.6, "trend": [516.0, 520.0], "volume": 60_000_000},
        "RSP": {"value": 168.0, "change_pct": 0.2, "trend": [167.0, 168.0], "volume": 4_000_000},
        "QQQ": {"value": 460.0, "change_pct": 1.1, "trend": [454.0, 460.0], "volume": 45_000_000},
        "IWM": {"value": 210.0, "change_pct": -0.3, "trend": [211.0, 210.0], "volume": 22_000_000},
    }

    with patch.object(service, "_latest_quote", side_effect=lambda ticker: quotes[ticker]):
        payload = service.get_us_breadth()

    provenance = project_source_provenance(
        source=payload.get("source"),
        source_type=payload.get("sourceType"),
        source_label=payload.get("sourceLabel"),
        freshness=payload.get("freshness"),
        is_fallback=bool(payload.get("isFallback") or payload.get("fallbackUsed")),
        is_stale=bool(payload.get("isStale")),
    )
    assert provenance["sourceType"] == "unofficial_proxy"
    assert provenance["sourceLabel"] == "Yahoo Finance"
    assert provenance["sourceType"] not in {"exchange_public", "official_public"}
    assert all(
        project_source_provenance(
            source=item.get("source"),
            source_type=item.get("sourceType"),
            source_label=item.get("sourceLabel"),
            freshness=item.get("freshness"),
            is_fallback=bool(item.get("isFallback") or item.get("fallbackUsed")),
            is_stale=bool(item.get("isStale")),
        )["sourceType"]
        == "unofficial_proxy"
        for item in payload["items"]
    )


def test_market_us_breadth_fallback_stays_non_live_and_sanitized() -> None:
    service = MarketOverviewService()

    with patch.object(
        service,
        "_latest_quote",
        side_effect=RuntimeError(
            "403 forbidden token=SECRET url=https://api.exchange.test/raw providerPayload=ExchangeStatsCo"
        ),
    ):
        payload = service.get_us_breadth()

    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    provenance = project_source_provenance(
        source=payload.get("source"),
        source_type=payload.get("sourceType"),
        source_label=payload.get("sourceLabel"),
        freshness=payload.get("freshness"),
        is_fallback=bool(payload.get("isFallback") or payload.get("fallbackUsed")),
        is_stale=bool(payload.get("isStale")),
    )
    assert payload["source"] == "unavailable"
    assert payload["sourceType"] == "missing"
    assert payload["freshness"] == "unavailable"
    assert payload["isFallback"] is True
    assert payload["sourceAuthorityAllowed"] is False
    assert payload["scoreContributionAllowed"] is False
    assert payload["sourceAuthorityReason"] == "authorized_us_market_breadth_feed_not_configured"
    assert "US breadth missing/unavailable" in payload["warning"]
    assert payload["providerHealth"]["status"] == "unavailable"
    assert payload["providerHealth"]["status"] != "live"
    assert provenance["sourceType"] == "fallback_static"
    assert provenance["freshnessLabel"] != "实时"
    assert "SECRET" not in serialized
    assert "https://api.exchange.test/raw" not in serialized
    assert "providerPayload" not in serialized
    assert "ExchangeStatsCo" not in serialized
