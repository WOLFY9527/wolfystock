# -*- coding: utf-8 -*-
"""Focused regression coverage for Market Overview evidence snapshots."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.services.market_overview_service import MarketOverviewService


CN_TZ = timezone(timedelta(hours=8))


def _iso_now() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="seconds")


EVIDENCE_SNAPSHOT_PUBLIC_KEYS = {
    "contractVersion",
    "diagnosticOnly",
    "scoreReliabilityAllowed",
    "cardKey",
    "endpoint",
    "source",
    "sourceLabel",
    "asOf",
    "updatedAt",
    "freshness",
    "isFallback",
    "isStale",
    "isPartial",
    "isSynthetic",
    "isUnavailable",
    "isFromSnapshot",
    "isRefreshing",
    "providerHealth",
    "confidenceWeight",
    "coverage",
    "degradationReason",
    "capReason",
    "sourceType",
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "observationOnly",
    "reasonFamilies",
}


class MarketOverviewEvidenceSnapshotTestCase(unittest.TestCase):
    def setUp(self) -> None:
        MarketOverviewService._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

    def test_live_panel_projects_evidence_snapshot(self) -> None:
        service = MarketOverviewService()
        as_of = _iso_now()

        with patch.object(
            service,
            "_fetch_indices",
            return_value={
                "source": "yfinance",
                "sourceLabel": "Yahoo Finance",
                "updatedAt": as_of,
                "asOf": as_of,
                "items": [
                    {
                        "symbol": "SPX",
                        "label": "S&P 500",
                        "value": 5200.12,
                        "changePercent": 0.42,
                        "trend": [5180.0, 5200.12],
                        "source": "yfinance",
                        "sourceLabel": "Yahoo Finance",
                        "updatedAt": as_of,
                        "asOf": as_of,
                    }
                ],
            },
        ):
            payload = service.get_indices()

        assert payload["evidenceSnapshot"] == {
            "contractVersion": "market_overview_evidence.v1",
            "diagnosticOnly": True,
            "scoreReliabilityAllowed": False,
            "cardKey": "indices",
            "endpoint": "/api/v1/market-overview/indices",
            "source": "yfinance",
            "sourceLabel": "Yahoo Finance",
            "asOf": as_of,
            "updatedAt": as_of,
            "freshness": "live",
            "isFallback": False,
            "isStale": False,
            "isPartial": False,
            "isSynthetic": False,
            "isUnavailable": False,
            "isFromSnapshot": False,
            "isRefreshing": False,
            "providerHealth": {"status": "live"},
            "confidenceWeight": 0.7,
            "coverage": 1.0,
            "degradationReason": None,
            "capReason": None,
            "sourceType": "unofficial_public_api",
            "sourceAuthorityAllowed": None,
            "scoreContributionAllowed": None,
            "observationOnly": True,
            "reasonFamilies": [],
        }

    def test_fallback_panel_projects_evidence_snapshot(self) -> None:
        service = MarketOverviewService()

        with patch.object(service, "_fetch_cn_breadth_snapshot", side_effect=RuntimeError("provider down")):
            payload = service.get_cn_breadth()

        evidence = payload["evidenceSnapshot"]
        assert evidence["source"] == "fallback"
        assert evidence["freshness"] == "fallback"
        assert evidence["isFallback"] is True
        assert evidence["isStale"] is False
        assert evidence["isPartial"] is False
        assert evidence["isUnavailable"] is False
        assert evidence["coverage"] == 0.0
        assert evidence["confidenceWeight"] == 0.0
        assert evidence["degradationReason"] == "provider_unavailable"
        assert evidence["capReason"] == "fallback_source"
        assert evidence["reasonFamilies"] == [
            {
                "rawCode": "provider_unavailable",
                "family": "unclassified",
                "scope": None,
                "sourceField": "degradationReason",
            },
            {
                "rawCode": "fallback_source",
                "family": "fallback",
                "scope": "source_confidence",
                "sourceField": "capReason",
            },
        ]

    def test_stale_panel_projects_evidence_snapshot(self) -> None:
        service = MarketOverviewService()
        as_of = (datetime.now(CN_TZ) - timedelta(days=2)).isoformat(timespec="seconds")

        with patch.object(
            service,
            "_fetch_indices",
            return_value={
                "source": "yfinance",
                "sourceLabel": "Yahoo Finance",
                "updatedAt": as_of,
                "asOf": as_of,
                "items": [
                    {
                        "symbol": "SPX",
                        "label": "S&P 500",
                        "value": 5200.12,
                        "changePercent": 0.42,
                        "trend": [5180.0, 5200.12],
                        "source": "yfinance",
                        "sourceLabel": "Yahoo Finance",
                        "updatedAt": as_of,
                        "asOf": as_of,
                    }
                ],
            },
        ):
            payload = service.get_indices()

        evidence = payload["evidenceSnapshot"]
        assert evidence["source"] == "yfinance"
        assert evidence["asOf"] == as_of
        assert evidence["freshness"] == "stale"
        assert evidence["isFallback"] is False
        assert evidence["isStale"] is True
        assert evidence["isPartial"] is False
        assert evidence["isUnavailable"] is False
        assert evidence["coverage"] == 1.0
        assert evidence["confidenceWeight"] == 0.6
        assert evidence["degradationReason"] == "stale_source"
        assert evidence["capReason"] == "stale_source"

    def test_partial_panel_projects_evidence_snapshot(self) -> None:
        service = MarketOverviewService()
        as_of = _iso_now()

        with patch.object(
            service,
            "_fetch_cn_indices_snapshot",
            return_value={
                "source": "mixed",
                "sourceLabel": "多来源",
                "updatedAt": as_of,
                "asOf": as_of,
                "fallbackUsed": True,
                "items": [
                    {
                        "name": "上证指数",
                        "symbol": "000001.SH",
                        "value": 4107.51,
                        "change": 28.88,
                        "changePercent": 0.71,
                        "sparkline": [4078.63, 4107.51],
                        "source": "sina",
                        "sourceLabel": "新浪财经",
                        "updatedAt": as_of,
                        "asOf": as_of,
                    },
                    {
                        "name": "深证成指",
                        "symbol": "399001.SZ",
                        "value": 9820.42,
                        "change": 52.18,
                        "changePercent": 0.53,
                        "sparkline": [9722.0, 9820.42],
                        "source": "fallback",
                        "sourceLabel": "备用数据",
                        "updatedAt": as_of,
                        "asOf": as_of,
                        "freshness": "fallback",
                        "isFallback": True,
                    },
                ],
            },
        ):
            payload = service.get_cn_indices()

        evidence = payload["evidenceSnapshot"]
        assert evidence["source"] == "mixed"
        assert evidence["asOf"] == as_of
        assert evidence["freshness"] == "partial"
        assert evidence["isFallback"] is False
        assert evidence["isStale"] is False
        assert evidence["isPartial"] is True
        assert evidence["isUnavailable"] is False
        assert evidence["coverage"] == 0.5
        assert evidence["confidenceWeight"] == 0.45
        assert evidence["degradationReason"] == "partial_coverage"
        assert evidence["capReason"] == "partial_coverage"
        assert evidence["observationOnly"] is True
        assert json.loads(json.dumps(evidence, ensure_ascii=False)) == evidence

    def test_unavailable_panel_projects_evidence_snapshot(self) -> None:
        service = MarketOverviewService()

        with patch.object(service, "_latest_quote", side_effect=RuntimeError("provider down")):
            payload = service.get_us_breadth()

        evidence = payload["evidenceSnapshot"]
        assert evidence["source"] == "unavailable"
        assert evidence["freshness"] == "unavailable"
        assert evidence["isFallback"] is True
        assert evidence["isStale"] is False
        assert evidence["isPartial"] is False
        assert evidence["isUnavailable"] is True
        assert evidence["coverage"] == 0.0
        assert evidence["confidenceWeight"] == 0.0
        assert evidence["degradationReason"] == "authorized_us_market_breadth_feed_not_configured"
        assert evidence["capReason"] == "unavailable_source"
        assert evidence["sourceType"] == "missing"
        assert evidence["sourceAuthorityAllowed"] is False
        assert evidence["scoreContributionAllowed"] is False
        assert evidence["observationOnly"] is True
        assert evidence["reasonFamilies"] == [
            {
                "rawCode": "authorized_us_market_breadth_feed_not_configured",
                "family": "unclassified",
                "scope": None,
                "sourceField": "degradationReason",
            },
            {
                "rawCode": "unavailable_source",
                "family": "unavailable",
                "scope": "source_confidence",
                "sourceField": "capReason",
            },
        ]
        assert all(item["family"] != "malformed" for item in evidence["reasonFamilies"])

    def test_evidence_snapshot_reuses_shared_provider_helper_without_widening_contract(self) -> None:
        service = MarketOverviewService()
        as_of = _iso_now()

        normalized_payload = service._with_market_meta(
            {
                "source": "mixed",
                "sourceLabel": "多来源",
                "updatedAt": as_of,
                "asOf": as_of,
                "items": [
                    {
                        "symbol": "000001.SH",
                        "label": "上证指数",
                        "value": 3100.12,
                        "source": "sina",
                        "sourceLabel": "新浪财经",
                        "updatedAt": as_of,
                        "asOf": as_of,
                    },
                    {
                        "symbol": "399001.SZ",
                        "label": "深证成指",
                        "value": 10020.55,
                        "source": "fallback",
                        "sourceLabel": "备用数据",
                        "updatedAt": as_of,
                        "asOf": as_of,
                        "freshness": "fallback",
                        "isFallback": True,
                    },
                ],
            },
            "indices",
        )

        with patch(
            "src.services.market_overview_service.build_provider_evidence_snapshot",
            return_value={
                "diagnosticOnly": True,
                "observationOnly": True,
                "authorityGrant": False,
                "decisionGrade": False,
                "source": "mixed",
                "sourceLabel": "多来源",
                "asOf": as_of,
                "freshness": "partial",
                "isFallback": False,
                "isStale": False,
                "isPartial": True,
                "isSynthetic": False,
                "isUnavailable": False,
            },
        ) as helper_mock:
            payload = service._with_evidence_snapshot(normalized_payload, "indices")

        helper_mock.assert_called_once()
        evidence = payload["evidenceSnapshot"]
        assert set(evidence.keys()) == EVIDENCE_SNAPSHOT_PUBLIC_KEYS
        assert evidence["diagnosticOnly"] is True
        assert evidence["observationOnly"] is True
        assert evidence["source"] == "mixed"
        assert evidence["freshness"] == "partial"
        assert evidence["isPartial"] is True
        assert "authorityGrant" not in evidence
        assert "decisionGrade" not in evidence
        assert "authorityGrant" not in payload
        assert "decisionGrade" not in payload

    def test_evidence_snapshot_normalization_does_not_change_scores_or_regime_payloads(self) -> None:
        service = MarketOverviewService()
        as_of = _iso_now()
        scores = {
            "overall": {"value": 48, "label": "中性", "description": "风险偏好中性。"},
            "macroPressure": {"value": 63, "label": "偏高", "description": "宏观压力偏高。"},
        }
        market_regime_synthesis = {
            "regime": "rangebound",
            "summary": "等待更多方向确认。",
            "reasonFamilies": ["macro_pressure", "breadth_mixed"],
        }

        payload = service._with_evidence_snapshot(
            service._with_market_meta(
                {
                    "source": "yfinance",
                    "sourceLabel": "Yahoo Finance",
                    "updatedAt": as_of,
                    "asOf": as_of,
                    "scores": scores,
                    "marketRegimeSynthesis": market_regime_synthesis,
                    "items": [
                        {
                            "symbol": "SPX",
                            "label": "S&P 500",
                            "value": 5200.12,
                            "source": "yfinance",
                            "sourceLabel": "Yahoo Finance",
                            "updatedAt": as_of,
                            "asOf": as_of,
                        }
                    ],
                },
                "temperature",
            ),
            "temperature",
        )

        assert payload["scores"] == scores
        assert payload["marketRegimeSynthesis"] == market_regime_synthesis
        assert "evidenceSnapshot" in payload

    def test_evidence_snapshot_exposes_score_grade_gate_flags_for_official_fed_bundle(self) -> None:
        service = MarketOverviewService()
        as_of = _iso_now()
        items = [
            {
                "symbol": "FED_ASSETS",
                "label": "Fed total assets",
                "value": 7485000.0,
                "changePercent": 0.12,
                "source": "fred",
                "sourceLabel": "FRED",
                "sourceType": "official_public",
                "updatedAt": as_of,
                "asOf": as_of,
                "freshness": "cached",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "observationOnly": False,
                "cacheBundleDiagnostics": {
                    "sourceType": "official_public",
                    "scoreContributionAllowed": True,
                    "observationOnly": False,
                },
            }
        ]

        payload = service._with_evidence_snapshot(
            service._with_market_meta(
                {
                    "source": "mixed",
                    "sourceLabel": "多来源",
                    "updatedAt": as_of,
                    "asOf": as_of,
                    "items": items,
                },
                "rates",
            ),
            "rates",
        )

        evidence = payload["evidenceSnapshot"]
        assert evidence["sourceType"] == "official_public"
        assert evidence["sourceAuthorityAllowed"] is True
        assert evidence["scoreContributionAllowed"] is True
        assert evidence["observationOnly"] is False
        assert evidence["diagnosticOnly"] is True
        assert evidence["scoreReliabilityAllowed"] is False
        assert evidence["degradationReason"] is None
        assert evidence["capReason"] is None
        assert evidence["reasonFamilies"] == [
            {
                "rawCode": "cached",
                "family": "cached_delayed_only",
                "scope": "freshness",
                "sourceField": "freshness",
            }
        ]

    def test_evidence_snapshot_exposes_observation_only_blocked_flags_for_cn_money_market_gate(self) -> None:
        service = MarketOverviewService()
        as_of = _iso_now()
        guarded_rows = service._with_cn_money_market_readiness_items(
            [
                {
                    "symbol": "DR007",
                    "label": "DR007",
                    "officialSeriesId": "DR007",
                    "value": 1.86,
                    "source": "official_cn_money_market_rates",
                    "sourceLabel": "全国银行间同业拆借中心",
                    "sourceType": "official_public",
                    "updatedAt": as_of,
                    "asOf": as_of,
                    "freshness": "delayed",
                    "confidenceWeight": 1.0,
                    "isFallback": False,
                    "isUnavailable": False,
                }
            ]
        )

        payload = service._with_evidence_snapshot(
            service._with_market_meta(
                {
                    "source": "mixed",
                    "sourceLabel": "多来源",
                    "updatedAt": as_of,
                    "asOf": as_of,
                    "items": guarded_rows,
                },
                "rates",
            ),
            "rates",
        )

        evidence = payload["evidenceSnapshot"]
        assert evidence["sourceType"] == "official_public"
        assert evidence["sourceAuthorityAllowed"] is False
        assert evidence["scoreContributionAllowed"] is False
        assert evidence["observationOnly"] is True
        assert evidence["diagnosticOnly"] is True
        assert evidence["scoreReliabilityAllowed"] is False
        assert evidence["degradationReason"] == "cn_money_market_required_series_missing_or_stale"
        assert evidence["capReason"] is None
        assert evidence["reasonFamilies"] == [
            {
                "rawCode": "cn_money_market_required_series_missing_or_stale",
                "family": "observation_only",
                "scope": "official_cache_readiness",
                "sourceField": "degradationReason",
            },
            {
                "rawCode": "delayed",
                "family": "cached_delayed_only",
                "scope": "freshness",
                "sourceField": "freshness",
            },
            {
                "rawCode": "source_authority_blocked",
                "family": "source_authority_blocked",
                "scope": "score_gate",
                "sourceField": "sourceAuthorityAllowed",
            },
            {
                "rawCode": "observation_only_source",
                "family": "observation_only_source",
                "scope": "score_gate",
                "sourceField": "observationOnly",
            },
        ]

    def test_evidence_snapshot_requires_explicit_gate_not_health_timestamps_or_weights(self) -> None:
        service = MarketOverviewService()
        as_of = _iso_now()

        payload = service._with_evidence_snapshot(
            {
                "source": "yfinance",
                "sourceLabel": "Yahoo Finance",
                "sourceType": "official_public",
                "updatedAt": as_of,
                "asOf": as_of,
                "freshness": "live",
                "confidenceWeight": 1.0,
                "coverage": 1.0,
                "providerHealth": {
                    "status": "live",
                    "card": "rates",
                },
                "items": [
                    {
                        "symbol": "SPX",
                        "label": "S&P 500",
                        "value": 5200.12,
                        "source": "yfinance",
                        "updatedAt": as_of,
                        "asOf": as_of,
                    }
                ],
            },
            "rates",
        )

        evidence = payload["evidenceSnapshot"]
        assert evidence["diagnosticOnly"] is True
        assert evidence["scoreReliabilityAllowed"] is False
        assert evidence["sourceAuthorityAllowed"] is None
        assert evidence["scoreContributionAllowed"] is None
        assert evidence["confidenceWeight"] == 1.0
        assert evidence["coverage"] == 1.0

    def test_evidence_snapshot_marks_snapshot_refreshing_data_non_reliable(self) -> None:
        service = MarketOverviewService()
        as_of = _iso_now()

        payload = service._with_evidence_snapshot(
            {
                "source": "yfinance",
                "sourceLabel": "Yahoo Finance",
                "updatedAt": as_of,
                "asOf": as_of,
                "freshness": "stale",
                "isStale": True,
                "isFromSnapshot": True,
                "isRefreshing": True,
                "providerHealth": {
                    "status": "refreshing",
                    "card": "indices",
                },
                "items": [
                    {
                        "symbol": "SPX",
                        "label": "S&P 500",
                        "value": 5200.12,
                        "source": "yfinance",
                        "updatedAt": as_of,
                        "asOf": as_of,
                        "freshness": "stale",
                        "isStale": True,
                    }
                ],
            },
            "equity_index",
        )

        evidence = payload["evidenceSnapshot"]
        assert evidence["isFromSnapshot"] is True
        assert evidence["isRefreshing"] is True
        assert evidence["providerHealth"] == {"status": "refreshing"}
        assert evidence["scoreReliabilityAllowed"] is False
        assert any(item["family"] == "stale" for item in evidence["reasonFamilies"])
        assert any(item["family"] == "source_authority_blocked" for item in evidence["reasonFamilies"]) is False

    def test_evidence_snapshot_unknown_reason_code_maps_to_unclassified_sidecar(self) -> None:
        service = MarketOverviewService()
        as_of = _iso_now()

        payload = service._with_evidence_snapshot(
            service._with_market_meta(
                {
                    "source": "yfinance",
                    "sourceLabel": "Yahoo Finance",
                    "updatedAt": as_of,
                    "asOf": as_of,
                    "degradationReason": "totally_new_reason_code",
                    "items": [
                        {
                            "symbol": "SPX",
                            "label": "S&P 500",
                            "value": 5200.12,
                            "changePercent": 0.42,
                            "trend": [5180.0, 5200.12],
                            "source": "yfinance",
                            "sourceLabel": "Yahoo Finance",
                            "updatedAt": as_of,
                            "asOf": as_of,
                        }
                    ],
                },
                "indices",
            ),
            "indices",
        )

        evidence = payload["evidenceSnapshot"]
        assert evidence["degradationReason"] == "totally_new_reason_code"
        assert evidence["capReason"] is None
        assert evidence["reasonFamilies"] == [
            {
                "rawCode": "totally_new_reason_code",
                "family": "unclassified",
                "scope": None,
                "sourceField": "degradationReason",
            }
        ]
