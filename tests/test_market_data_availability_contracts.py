# -*- coding: utf-8 -*-
"""Data availability contracts for visible market, liquidity, and rotation surfaces."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from src.services.liquidity_monitor_service import LiquidityMonitorService
from src.services.market_cache import MarketCache
from src.services.market_data_source_registry import project_source_provenance
from src.services.market_overview_service import (
    MarketOverviewService,
    classify_market_payload_reliability,
    get_freshness_status,
)
from src.storage import DatabaseManager


CN_TZ = timezone(timedelta(hours=8))


@pytest.fixture(autouse=True)
def _clear_market_overview_state() -> None:
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    yield
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()


class _FrameColumn:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def tolist(self) -> list[float]:
        return list(self._values)


class _HistoryFrame:
    def __init__(self, closes: list[float], *, as_of: datetime) -> None:
        self.empty = False
        self.index = [as_of - timedelta(days=1), as_of]
        self._columns = {
            "Close": _FrameColumn(closes),
        }

    def __getitem__(self, key: str) -> _FrameColumn:
        return self._columns[key]

    def __contains__(self, key: str) -> bool:
        return key in self._columns


@pytest.fixture()
def isolated_db(tmp_path: Path):
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 't101-data-availability.sqlite'}")
    yield DatabaseManager.get_instance()
    DatabaseManager.reset_instance()


def _cache_entry(
    *,
    source: str,
    freshness: str,
    items: list[dict[str, Any]],
    updated_at: str,
    as_of: str,
    is_fallback: bool = False,
    warning: str | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "freshness": freshness,
        "items": items,
        "updatedAt": updated_at,
        "asOf": as_of,
        "isFallback": is_fallback,
        "fallbackUsed": is_fallback,
        "warning": warning,
    }


def _make_service() -> LiquidityMonitorService:
    return LiquidityMonitorService(
        cache=MarketCache(max_workers=1),
        db=DatabaseManager.get_instance(),
    )


def _payload_provenance(payload: dict[str, Any]) -> dict[str, str]:
    return project_source_provenance(
        source=payload.get("source"),
        source_type=payload.get("sourceType"),
        source_label=payload.get("sourceLabel"),
        freshness=payload.get("freshness"),
        is_fallback=bool(payload.get("isFallback")),
        is_stale=bool(payload.get("isStale")),
        is_from_snapshot=bool(payload.get("isFromSnapshot")),
        no_external_calls=bool(payload.get("noExternalCalls")),
    )


def test_non_live_and_proxy_provenance_never_projects_as_official_or_live() -> None:
    cases = {
        "fallback_static": project_source_provenance(
            source="fallback",
            freshness="live",
            is_fallback=True,
        ),
        "synthetic_fixture": project_source_provenance(
            source="synthetic_fixture",
            freshness="synthetic_delayed",
        ),
        "missing": project_source_provenance(
            source="unavailable",
            freshness="unavailable",
        ),
        "yfinance_proxy": project_source_provenance(
            source="yfinance_proxy",
            source_type="proxy_public",
            freshness="delayed",
        ),
        "tickflow_proxy": project_source_provenance(
            source="tickflow",
            source_type="public_api",
            freshness="delayed",
        ),
    }

    assert cases["fallback_static"]["sourceType"] == "fallback_static"
    assert cases["synthetic_fixture"]["sourceType"] == "synthetic_fixture"
    assert cases["missing"]["sourceType"] == "missing"
    assert cases["yfinance_proxy"]["sourceType"] == "unofficial_proxy"
    assert cases["tickflow_proxy"]["sourceType"] == "public_proxy"
    assert all(
        payload["sourceType"] not in {"official_public", "exchange_public"}
        for payload in cases.values()
    )
    assert all(payload["freshnessLabel"] != "实时" for payload in cases.values())


def test_us_breadth_future_stub_proxy_and_fallback_never_project_as_official_or_live() -> None:
    cases = {
        "future_stub": project_source_provenance(
            source="disabled_live_stub",
            source_type="disabled_live_stub",
            freshness="fallback",
        ),
        "yfinance_proxy": project_source_provenance(
            source="yfinance_proxy",
            source_type="proxy_public",
            freshness="delayed",
        ),
        "fallback_static": project_source_provenance(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
        ),
    }

    assert cases["future_stub"]["sourceType"] == "fallback_static"
    assert cases["yfinance_proxy"]["sourceType"] == "unofficial_proxy"
    assert cases["fallback_static"]["sourceType"] == "fallback_static"
    assert all(
        payload["sourceType"] not in {"official_public", "exchange_public"}
        for payload in cases.values()
    )
    assert all(payload["freshnessLabel"] != "实时" for payload in cases.values())


def test_fx_commodities_and_futures_proxy_or_stub_provenance_never_projects_as_official_or_live() -> None:
    cases = {
        "fx_fallback_static": project_source_provenance(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
        ),
        "fx_yfinance_proxy": project_source_provenance(
            source="yfinance_proxy",
            source_type="proxy_public",
            freshness="delayed",
        ),
        "futures_delayed_stub": project_source_provenance(
            source="disabled_live_stub",
            source_type="disabled_live_stub",
            freshness="delayed",
        ),
        "futures_yfinance_proxy": project_source_provenance(
            source="yfinance_proxy",
            source_type="proxy_public",
            freshness="delayed",
        ),
    }

    assert cases["fx_fallback_static"]["sourceType"] == "fallback_static"
    assert cases["fx_yfinance_proxy"]["sourceType"] == "unofficial_proxy"
    assert cases["futures_delayed_stub"]["sourceType"] == "disabled_live_stub"
    assert cases["futures_yfinance_proxy"]["sourceType"] == "unofficial_proxy"
    assert all(
        payload["sourceType"] not in {"official_public", "exchange_public"}
        for payload in cases.values()
    )
    assert all(payload["freshnessLabel"] != "实时" for payload in cases.values())


def test_sentiment_proxy_fallback_and_synthetic_payloads_never_project_as_live_or_official() -> None:
    cases = {
        "sentiment_fallback": project_source_provenance(
            source="fallback",
            freshness="live",
            is_fallback=True,
        ),
        "sentiment_snapshot": project_source_provenance(
            source="cached",
            freshness="stale",
            is_from_snapshot=True,
        ),
        "sentiment_proxy": project_source_provenance(
            source="yfinance_proxy",
            source_type="proxy_public",
            freshness="delayed",
        ),
        "sentiment_synthetic": project_source_provenance(
            source="synthetic_fixture",
            freshness="synthetic_delayed",
        ),
    }

    assert cases["sentiment_fallback"]["sourceType"] == "fallback_static"
    assert cases["sentiment_snapshot"]["freshnessLabel"] != "实时"
    assert cases["sentiment_proxy"]["sourceType"] == "unofficial_proxy"
    assert cases["sentiment_synthetic"]["sourceType"] == "synthetic_fixture"
    assert all(
        payload["sourceType"] not in {"official_public", "exchange_public"}
        for payload in cases.values()
    )
    assert all(payload["freshnessLabel"] != "实时" for payload in cases.values())


def test_market_reliability_classifier_excludes_fallback_static_synthetic_missing_and_stale_inputs() -> None:
    cases = [
        (
            "fallback_static",
            {"source": "fallback", "freshness": "fallback", "isFallback": True, "value": 1.0},
            "fallback",
        ),
        (
            "synthetic_fixture",
            {"source": "synthetic_fixture", "freshness": "delayed", "value": 1.0},
            "fallback",
        ),
        (
            "missing",
            {"source": "unavailable", "freshness": "unavailable", "value": None},
            "error",
        ),
        (
            "stale_proxy",
            {"source": "yfinance_proxy", "freshness": "stale", "isStale": True, "value": 1.0},
            "stale",
        ),
    ]

    for _, payload, expected_kind in cases:
        reliability = classify_market_payload_reliability(payload, category="macro_rate")

        assert reliability["kind"] == expected_kind
        assert reliability["isReliable"] is False
        assert reliability["excluded"] is True
        assert reliability["confidenceWeight"] == 0.0


def test_official_daily_macro_observations_stay_delayed_or_stale_not_live() -> None:
    delayed = get_freshness_status(
        "2026-05-14T15:00:00+08:00",
        "macro_rate",
        "treasury",
        False,
        source_type="official_public",
        now=datetime(2026, 5, 14, 16, 0, tzinfo=timezone.utc),
    )
    stale = get_freshness_status(
        "2026-05-10T15:00:00+08:00",
        "macro_rate",
        "treasury",
        False,
        source_type="official_public",
        now=datetime(2026, 5, 14, 16, 0, tzinfo=timezone.utc),
    )

    assert delayed["freshness"] == "delayed"
    assert delayed["isFallback"] is False
    assert delayed["isStale"] is False
    assert delayed["freshness"] != "live"
    assert stale["freshness"] == "stale"
    assert stale["isFallback"] is False
    assert stale["isStale"] is True
    assert stale["warning"]


def test_market_overview_fallback_only_panels_preserve_unavailable_and_fallback_states() -> None:
    service = MarketOverviewService()

    cn_flows = service._fallback_cn_flows_snapshot()
    cn_flows_provenance = _payload_provenance(cn_flows)

    assert cn_flows["source"] == "unavailable"
    assert cn_flows["isFallback"] is False
    assert cn_flows["isUnavailable"] is True
    assert cn_flows["freshness"] == "unavailable"
    assert cn_flows_provenance["sourceType"] == "missing"
    assert cn_flows_provenance["sourceLabel"] == "未接入"
    assert cn_flows_provenance["freshnessLabel"] == "不可用"
    assert all(item["source"] == "unavailable" for item in cn_flows["items"])
    assert all(item["isUnavailable"] is True for item in cn_flows["items"])
    assert all(item["value"] is None for item in cn_flows["items"])
    assert all(item["changePercent"] is None for item in cn_flows["items"])

    rates = service._fallback_rates_snapshot()
    rates_provenance = _payload_provenance(rates)

    assert rates["source"] == "fallback"
    assert rates["isFallback"] is True
    assert rates["fallbackUsed"] is True
    assert "isUnavailable" not in rates
    assert rates["sourceLabel"] == "备用数据"
    assert rates_provenance["sourceType"] == "fallback_static"
    assert rates_provenance["sourceLabel"] == "备用数据"
    assert rates_provenance["freshnessLabel"] == "备用/缺失"
    assert all("isUnavailable" not in item for item in rates["items"])
    assert all(item["value"] is not None for item in rates["items"])


def test_sector_rotation_projection_stays_proxy_computed_not_official_or_live() -> None:
    service = MarketOverviewService()
    as_of = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(timespec="seconds")
    updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    radar_payload = {
        "source": "computed",
        "sourceLabel": "主题篮子计算",
        "updatedAt": updated_at,
        "asOf": as_of,
        "freshness": "delayed",
        "isFallback": False,
        "themes": [
            {
                "id": "ai_applications",
                "name": "AI 应用",
                "market": "US",
                "rotationScore": 73,
                "relativeStrength": 4.0,
                "source": "computed",
                "sourceLabel": "主题篮子计算",
                "freshness": "delayed",
                "isFallback": False,
                "isStale": False,
                "updatedAt": updated_at,
                "asOf": as_of,
                "stageExplanation": "已有相对强势，但仍需更多广度确认。",
                "proxyQuality": {"coveragePercent": 100, "explanation": "代理覆盖完整。"},
                "themeDetail": {"dataStateLabel": "行情证据已接入"},
                "timeWindows": {"1d": {"available": True, "averageChangePercent": 4.0}},
                "evidence": ["相对强弱领先"],
            }
        ],
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(service, "_cached_payload", lambda _key, fetcher, _fallback: fetcher())
        mp.setattr("src.services.market_overview_service.get_rotation_radar_quote_provider", lambda: None, raising=False)

        class _RadarService:
            def __init__(self, quote_provider=None, **_: Any) -> None:
                self.quote_provider = quote_provider

            def get_rotation_radar(self) -> dict[str, Any]:
                return radar_payload

        mp.setattr("src.services.market_overview_service.MarketRotationRadarService", _RadarService, raising=False)
        payload = service.get_sector_rotation()

    payload_provenance = _payload_provenance(payload)
    item_provenance = _payload_provenance(payload["items"][0])

    assert payload["source"] == "computed"
    assert payload["freshness"] == "delayed"
    assert payload_provenance["sourceType"] not in {"official_public", "exchange_public"}
    assert payload_provenance["freshnessLabel"] != "实时"
    assert item_provenance["sourceType"] not in {"official_public", "exchange_public"}
    assert item_provenance["freshnessLabel"] != "实时"


def test_sector_rotation_projection_preserves_explicit_source_freshness_state() -> None:
    service = MarketOverviewService()
    source_as_of = "2026-05-13T09:30:00+00:00"
    updated_at = "2026-05-13T09:45:00+00:00"
    radar_payload = {
        "source": "computed",
        "sourceLabel": "主题篮子计算",
        "updatedAt": updated_at,
        "asOf": source_as_of,
        "freshness": "stale",
        "isFallback": False,
        "isStale": True,
        "isPartial": True,
        "isUnavailable": False,
        "sourceFreshnessEvidence": {
            "source": "computed",
            "sourceLabel": "主题篮子计算",
            "asOf": source_as_of,
            "freshness": "stale",
            "isFallback": False,
            "isStale": True,
            "isPartial": True,
            "isUnavailable": False,
        },
        "radarSnapshot": {
            "source": "computed",
            "sourceLabel": "主题篮子计算",
            "updatedAt": updated_at,
            "asOf": source_as_of,
            "freshness": "stale",
            "isFallback": False,
            "isStale": True,
            "isPartial": True,
            "isUnavailable": False,
        },
        "themes": [
            {
                "id": "ai_applications",
                "name": "AI 应用",
                "market": "US",
                "rotationScore": 73,
                "relativeStrength": {
                    "averageRelativeStrengthPercent": 4.0,
                },
                "source": "computed",
                "sourceLabel": "主题篮子计算",
                "freshness": "stale",
                "isFallback": False,
                "isStale": True,
                "isPartial": True,
                "isUnavailable": False,
                "updatedAt": updated_at,
                "asOf": source_as_of,
                "stageExplanation": "已有相对强势，但仍需更多广度确认。",
                "proxyQuality": {"coveragePercent": 100, "explanation": "代理覆盖完整。"},
                "themeDetail": {"dataStateLabel": "行情证据已接入"},
                "timeWindows": {"1d": {"available": True, "averageChangePercent": 4.0}},
                "evidence": ["相对强弱领先"],
                "rotationStateEvidence": {
                    "source": "computed",
                    "sourceLabel": "主题篮子计算",
                    "freshness": "stale",
                    "isFallback": False,
                    "isStale": True,
                    "isPartial": True,
                    "isUnavailable": False,
                    "sourceConfidence": {
                        "source": "computed.snapshot",
                        "sourceLabel": "主题篮子计算 快照",
                        "asOf": source_as_of,
                        "freshness": "stale",
                        "isFallback": False,
                        "isStale": True,
                        "isPartial": True,
                        "isUnavailable": False,
                        "confidenceWeight": 1.0,
                        "coverage": 1.0,
                        "degradationReason": "stale_source",
                        "capReason": "stale_source",
                    },
                    "evidenceSnapshot": {
                        "contractVersion": "source_confidence_contract_v1",
                        "computedAt": updated_at,
                        "asOf": source_as_of,
                        "source": "computed",
                        "sourceLabel": "主题篮子计算",
                        "freshness": "stale",
                        "isFallback": False,
                        "isStale": True,
                        "isPartial": True,
                        "isUnavailable": False,
                        "signalCount": 1,
                        "degradedSignalCount": 1,
                        "unavailableSignalCount": 0,
                        "coveragePercent": 100.0,
                        "coverageRatio": 1.0,
                        "signalOrder": ["relativeStrength"],
                        "sourceConfidence": {
                            "source": "computed.snapshot",
                            "sourceLabel": "主题篮子计算 快照",
                            "asOf": source_as_of,
                            "freshness": "stale",
                            "isFallback": False,
                            "isStale": True,
                            "isPartial": True,
                            "isUnavailable": False,
                            "confidenceWeight": 1.0,
                            "coverage": 1.0,
                            "degradationReason": "stale_source",
                            "capReason": "stale_source",
                        },
                        "signals": {
                            "relativeStrength": {
                                "key": "relativeStrength",
                                "label": "代理强度",
                                "status": "strong",
                                "value": 4.0,
                                "available": True,
                                "degraded": True,
                                "coveragePercent": 100.0,
                                "coverageRatio": 1.0,
                                "source": "computed.relativeStrength",
                                "sourceLabel": "主题篮子计算 代理强度",
                                "asOf": source_as_of,
                                "freshness": "stale",
                                "isFallback": False,
                                "isStale": True,
                                "isPartial": True,
                                "isUnavailable": False,
                                "degradationReason": "stale_source",
                                "capReason": "stale_source",
                                "sourceConfidence": {
                                    "source": "computed.relativeStrength",
                                    "sourceLabel": "主题篮子计算 代理强度",
                                    "asOf": source_as_of,
                                    "freshness": "stale",
                                    "isFallback": False,
                                    "isStale": True,
                                    "isPartial": True,
                                    "isUnavailable": False,
                                    "confidenceWeight": 1.0,
                                    "coverage": 1.0,
                                    "degradationReason": "stale_source",
                                    "capReason": "stale_source",
                                },
                            }
                        },
                    },
                },
            }
        ],
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(service, "_cached_payload", lambda _key, fetcher, _fallback: fetcher())
        mp.setattr("src.services.market_overview_service.get_rotation_radar_quote_provider", lambda: None, raising=False)

        class _RadarService:
            def __init__(self, quote_provider=None, **_: Any) -> None:
                self.quote_provider = quote_provider

            def get_rotation_radar(self) -> dict[str, Any]:
                return radar_payload

        mp.setattr("src.services.market_overview_service.MarketRotationRadarService", _RadarService, raising=False)
        payload = service.get_sector_rotation()

    assert payload["freshness"] == "stale"
    assert payload["isStale"] is True
    assert payload["isPartial"] is True
    assert payload["freshness"] not in {"live", "fresh"}
    assert payload["sourceFreshnessEvidence"]["freshness"] == "stale"
    assert payload["sourceFreshnessEvidence"]["freshness"] not in {"live", "fresh"}
    assert payload["radarSnapshot"]["freshness"] == "stale"
    assert payload["items"][0]["freshness"] == "stale"
    assert payload["items"][0]["isStale"] is True
    assert payload["items"][0]["isPartial"] is True
    assert payload["items"][0]["sourceFreshnessEvidence"]["freshness"] == "stale"
    assert payload["items"][0]["rotationStateEvidence"]["sourceConfidence"]["freshness"] == "stale"
    assert payload["providerHealth"]["isStale"] is True


def test_sector_rotation_taxonomy_only_projection_stays_fallback_local_taxonomy_non_live() -> None:
    service = MarketOverviewService()
    radar_payload = {
        "source": "local_taxonomy",
        "sourceLabel": "静态主题库",
        "updatedAt": "2026-05-13T10:00:00+00:00",
        "asOf": "2026-05-13T09:30:00+00:00",
        "freshness": "fallback",
        "isFallback": True,
        "warning": "当前为静态主题库。",
        "themes": [
            {
                "id": "cn_ai_compute",
                "name": "AI算力",
                "market": "CN",
                "rotationScore": 24,
                "relativeStrength": None,
                "source": "local_taxonomy",
                "sourceLabel": "静态主题库",
                "freshness": "fallback",
                "isFallback": True,
                "isStale": False,
                "updatedAt": "2026-05-13T10:00:00+00:00",
                "asOf": "2026-05-13T09:30:00+00:00",
                "stageExplanation": "静态主题待行情确认。",
                "proxyQuality": {"coveragePercent": 0, "explanation": "仅静态主题。"},
                "themeDetail": {"dataStateLabel": "静态主题"},
                "timeWindows": {},
                "evidence": ["静态主题库"],
            }
        ],
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(service, "_cached_payload", lambda _key, fetcher, _fallback: fetcher())
        mp.setattr("src.services.market_overview_service.get_rotation_radar_quote_provider", lambda: None, raising=False)

        class _RadarService:
            def __init__(self, quote_provider=None, **_: Any) -> None:
                self.quote_provider = quote_provider

            def get_rotation_radar(self) -> dict[str, Any]:
                return radar_payload

        mp.setattr("src.services.market_overview_service.MarketRotationRadarService", _RadarService, raising=False)
        payload = service.get_sector_rotation()

    payload_provenance = _payload_provenance(payload)
    item_provenance = _payload_provenance(payload["items"][0])

    assert payload["source"] == "local_taxonomy"
    assert payload["freshness"] == "fallback"
    assert payload["isFallback"] is True
    assert payload_provenance["sourceType"] == "fallback_static"
    assert payload_provenance["freshnessLabel"] != "实时"
    assert payload["items"][0]["source"] == "local_taxonomy"
    assert payload["items"][0]["freshness"] == "fallback"
    assert item_provenance["sourceType"] == "fallback_static"
    assert item_provenance["freshnessLabel"] != "实时"


def test_market_overview_fx_commodities_proxy_payload_projects_to_unofficial_proxy_not_live() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ) - timedelta(minutes=30)
    frames = {
        "DX-Y.NYB": _HistoryFrame([104.0, 104.3], as_of=as_of),
        "CNH=X": _HistoryFrame([7.20, 7.24], as_of=as_of),
        "JPY=X": _HistoryFrame([155.3, 156.4], as_of=as_of),
        "EURUSD=X": _HistoryFrame([1.071, 1.066], as_of=as_of),
        "GC=F": _HistoryFrame([2350.0, 2368.7], as_of=as_of),
        "CL=F": _HistoryFrame([79.1, 78.4], as_of=as_of),
        "BZ=F": _HistoryFrame([82.7, 82.1], as_of=as_of),
        "HG=F": _HistoryFrame([4.58, 4.63], as_of=as_of),
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.services.market_overview_service.fetch_yfinance_quote_history_frame",
            lambda ticker, **_: frames[ticker],
        )
        with pytest.MonkeyPatch.context() as log_mp:
            class _LogService:
                def record_market_overview_fetch(self, **_: Any) -> str:
                    return "log-3"

            log_mp.setattr("src.services.market_overview_service.ExecutionLogService", _LogService)
            payload = service.get_fx_commodities()

    provenance = _payload_provenance(payload)
    dxy_provenance = _payload_provenance(next(item for item in payload["items"] if item["symbol"] == "DXY"))

    assert payload["source"] == "yfinance_proxy"
    assert payload["freshness"] == "delayed"
    assert payload["providerHealth"]["status"] == "cache"
    assert provenance["sourceType"] == "unofficial_proxy"
    assert dxy_provenance["sourceType"] == "unofficial_proxy"
    assert provenance["freshnessLabel"] != "实时"
    assert dxy_provenance["freshnessLabel"] != "实时"


def test_market_overview_futures_proxy_payload_preserves_proxy_and_fail_closed_freshness() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ) - timedelta(minutes=20)
    frames = {
        "NQ=F": _HistoryFrame([18380.0, 18420.5], as_of=as_of),
        "ES=F": _HistoryFrame([5220.0, 5238.25], as_of=as_of),
        "YM=F": _HistoryFrame([38908.0, 38980.0], as_of=as_of),
        "RTY=F": _HistoryFrame([2098.4, 2094.6], as_of=as_of),
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.services.market_overview_service.fetch_yfinance_quote_history_frame",
            lambda ticker, **_: frames[ticker],
        )
        payload = service.get_futures()

    payload_provenance = _payload_provenance(payload)
    nq = next(item for item in payload["items"] if item["symbol"] == "NQ")
    fallback = next(item for item in payload["items"] if item["symbol"] == "HSI_F")
    nq_provenance = _payload_provenance(nq)
    fallback_provenance = _payload_provenance(fallback)

    assert payload["source"] == "mixed"
    assert payload["sourceType"] == "unofficial_proxy"
    assert payload["freshness"] == "delayed"
    assert payload_provenance["sourceType"] == "unofficial_proxy"
    assert payload_provenance["freshnessLabel"] == "延迟"
    assert nq["source"] == "yfinance_proxy"
    assert nq["sourceType"] == "unofficial_proxy"
    assert nq["freshness"] == "delayed"
    assert nq["isProxy"] is True
    assert nq["isUnavailable"] is False
    assert nq["value"] == 18420.5
    assert nq["sourceAuthorityState"] == "proxy"
    assert nq["sourceAuthorityAllowed"] is False
    assert nq["scoreContributionAllowed"] is False
    assert nq["scoreAuthorityEligible"] is False
    assert nq_provenance["sourceType"] == "unofficial_proxy"
    assert nq_provenance["freshnessLabel"] == "延迟"
    assert fallback["source"] == "fallback"
    assert fallback["freshness"] == "fallback"
    assert fallback["isFallback"] is True
    assert fallback_provenance["sourceType"] == "fallback_static"
    assert fallback_provenance["freshnessLabel"] == "备用/缺失"


def test_liquidity_monitor_only_scores_reliable_non_fallback_signals(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")

    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "VIX", "label": "VIX", "changePercent": -2.5, "value": 15.2}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "cn_flows",
        _cache_entry(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
            items=[{"symbol": "NORTHBOUND", "label": "北向资金", "value": 88.8}],
            updated_at=now,
            as_of=now,
            warning="备用快照",
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "futures",
        _cache_entry(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
            items=[{"symbol": "NQ", "label": "纳指期货", "changePercent": 1.5, "value": 18420.0}],
            updated_at=now,
            as_of=now,
            warning="备用快照",
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["score"]["includedIndicatorCount"] == 0
    assert indicators["vix_pressure"]["includedInScore"] is False
    assert indicators["vix_pressure"]["scoreContribution"] == 0
    assert indicators["us_etf_flow_proxy"]["includedInScore"] is False
    assert indicators["us_etf_flow_proxy"]["scoreContribution"] == 0
    assert indicators["us_etf_flow_proxy"]["label"] == "US ETF 资金代理"
    assert indicators["us_etf_flow_proxy"]["status"] == "partial"
    assert indicators["us_breadth_proxy"]["includedInScore"] is False
    assert indicators["us_breadth_proxy"]["scoreContribution"] == 0
    assert indicators["us_breadth_proxy"]["label"] == "US 广度代理"
    assert indicators["us_breadth_proxy"]["status"] == "partial"
    assert indicators["cn_hk_flows"]["includedInScore"] is False
    assert indicators["cn_hk_flows"]["status"] == "unavailable"
    assert indicators["cn_hk_flows"]["freshness"] == "fallback"
    assert indicators["futures_premarket"]["includedInScore"] is False
    assert indicators["futures_premarket"]["status"] == "unavailable"
    assert indicators["futures_premarket"]["freshness"] == "fallback"


def test_liquidity_monitor_ignores_sentiment_cache_shape_variants(
    isolated_db: DatabaseManager,
) -> None:
    def seed_panels(service: LiquidityMonitorService) -> None:
        now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
        service.cache.set(
            "volatility",
            _cache_entry(
                source="yfinance_proxy",
                freshness="live",
                items=[{"symbol": "VIX", "label": "VIX", "changePercent": -2.5, "value": 15.2}],
                updated_at=now,
                as_of=now,
            ),
            ttl_seconds=30,
        )
        service.cache.set(
            "us_breadth",
            _cache_entry(
                source="yfinance_proxy",
                freshness="live",
                items=[
                    {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8},
                    {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3},
                ],
                updated_at=now,
                as_of=now,
            ),
            ttl_seconds=30,
        )
        service.cache.set(
            "funds_flow",
            _cache_entry(
                source="yfinance_proxy",
                freshness="live",
                items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2}],
                updated_at=now,
                as_of=now,
            ),
            ttl_seconds=30,
        )
        service.cache.set(
            "cn_flows",
            _cache_entry(
                source="fallback",
                freshness="fallback",
                is_fallback=True,
                items=[{"symbol": "NORTHBOUND", "label": "北向资金", "value": 88.8}],
                updated_at=now,
                as_of=now,
                warning="备用快照",
            ),
            ttl_seconds=30,
        )
        service.cache.set(
            "futures",
            _cache_entry(
                source="fallback",
                freshness="fallback",
                is_fallback=True,
                items=[{"symbol": "NQ", "label": "纳指期货", "changePercent": 1.5, "value": 18420.0}],
                updated_at=now,
                as_of=now,
                warning="备用快照",
            ),
            ttl_seconds=30,
        )

    baseline = _make_service()
    seed_panels(baseline)
    baseline_payload = baseline.get_liquidity_monitor()

    poisoned = _make_service()
    seed_panels(poisoned)
    poisoned.cache.set(
        "sentiment",
        {
            "source": "computed",
            "updatedAt": "2026-05-15T10:00:00+08:00",
            "scores": {"overall": {"value": 90, "label": "过热"}},
        },
        ttl_seconds=1800,
    )
    poisoned_payload = poisoned.get_liquidity_monitor()

    assert baseline_payload["score"] == poisoned_payload["score"]
    assert baseline_payload["freshness"] == poisoned_payload["freshness"]
    assert [item["key"] for item in baseline_payload["indicators"]] == [
        item["key"] for item in poisoned_payload["indicators"]
    ]
    assert all("sentiment" not in item["key"] for item in poisoned_payload["indicators"])
