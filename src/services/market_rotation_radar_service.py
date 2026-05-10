# -*- coding: utf-8 -*-
"""Theme-level market rotation radar.

The MVP intentionally does not fetch live provider data. It can score normalized
quote snapshots injected by a caller, and otherwise returns clearly degraded
static basket evidence for UI shape and public safety.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

from src.services.sector_rotation_taxonomy import (
    ROTATION_TAXONOMY_VERSION,
    SUPPORTED_ROTATION_MARKETS,
    RotationTaxonomyEntry,
    get_rotation_taxonomy_by_market,
    normalize_rotation_market,
)
from src.services.rotation_state_evidence import build_rotation_state_evidence


NO_ADVICE_DISCLOSURE = "仅用于观察资金轮动迹象，非买卖建议。"
RADAR_ENDPOINT = "/api/v1/market/rotation-radar"
TIME_WINDOW_KEYS = ("5m", "15m", "60m", "1d")
MARKET_BENCHMARK_SYMBOLS = ("QQQ", "SPY", "IWM")
SECTOR_BENCHMARK_SYMBOLS = ("IGV", "SMH", "CIBR", "CLOU", "PAVE", "BOTZ")
BENCHMARK_SYMBOLS = MARKET_BENCHMARK_SYMBOLS + SECTOR_BENCHMARK_SYMBOLS
TIME_WINDOW_LABELS = {
    "5m": "5分钟",
    "15m": "15分钟",
    "60m": "60分钟",
    "1d": "日内/日线",
}
STAGE_LABELS = {
    "early_watch",
    "confirmed_rotation",
    "extended_watch",
    "cooling_watch",
    "weak_or_no_signal",
}


@dataclass(frozen=True)
class ThemeBasket:
    id: str
    name: str
    englishName: str
    benchmark: str
    sectorBenchmark: str
    members: Sequence[str]
    focus: str
    market: str = "US"
    taxonomyType: str = "theme_cluster"
    aliases: Sequence[str] = ()
    proxySymbols: Sequence[str] = ()
    mappedConcepts: Sequence[str] = ()
    dataCoverage: str = "quote_backed"
    sourceClass: str = "custom"
    riskNote: str = ""
    operatorNote: str = ""


def _theme_basket_from_taxonomy(entry: RotationTaxonomyEntry) -> ThemeBasket:
    proxy_symbols = tuple(entry.proxySymbols)
    benchmark = "IWM" if entry.id.endswith("small_cap_growth") else "QQQ"
    sector_benchmark = next((symbol for symbol in proxy_symbols if symbol not in MARKET_BENCHMARK_SYMBOLS), "SPY")
    return ThemeBasket(
        id=entry.id.rsplit(":", 1)[-1],
        name=entry.displayName,
        englishName=entry.englishName,
        benchmark=benchmark,
        sectorBenchmark=sector_benchmark,
        members=tuple(entry.representativeSymbols or entry.representativeLabels),
        focus="、".join(entry.mappedConcepts[:4]) if entry.mappedConcepts else entry.operatorNote,
        market=entry.market,
        taxonomyType=entry.taxonomyType,
        aliases=tuple(entry.aliases),
        proxySymbols=proxy_symbols,
        mappedConcepts=tuple(entry.mappedConcepts),
        dataCoverage=entry.dataCoverage,
        sourceClass=entry.sourceClass,
        riskNote=entry.riskNote,
        operatorNote=entry.operatorNote,
    )


THEME_BASKETS: Sequence[ThemeBasket] = tuple(
    _theme_basket_from_taxonomy(entry)
    for entry in get_rotation_taxonomy_by_market("US")
)

FALLBACK_PRESETS: Dict[str, Dict[str, Any]] = {
    "ai_applications": {"score": 34, "leaders": ("APP", "PLTR", "CRM")},
    "ai_infrastructure": {"score": 32, "leaders": ("NVDA", "VRT", "AVGO")},
    "semiconductors": {"score": 30, "leaders": ("NVDA", "AVGO", "AMD")},
    "cybersecurity": {"score": 27, "leaders": ("CRWD", "PANW", "ZS")},
    "cloud_software": {"score": 26, "leaders": ("MSFT", "SNOW", "NOW")},
    "data_center_power": {"score": 25, "leaders": ("VRT", "ETN", "PWR")},
    "liquid_cooling": {"score": 24, "leaders": ("VRT", "MOD", "SMCI")},
    "robotics": {"score": 23, "leaders": ("ISRG", "TER", "SYM")},
}

QuoteProvider = Callable[[Iterable[str]], Mapping[str, Mapping[str, Any]]]
NowProvider = Callable[[], datetime]


class MarketRotationRadarService:
    """Score manual theme baskets from normalized quote snapshots."""

    def __init__(
        self,
        *,
        quote_provider: Optional[QuoteProvider] = None,
        now_provider: Optional[NowProvider] = None,
    ) -> None:
        self.quote_provider = quote_provider
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def get_rotation_radar(self, market: str = "US") -> Dict[str, Any]:
        normalized_market = normalize_rotation_market(market)
        if normalized_market != "US":
            return self._taxonomy_rotation_radar(normalized_market)
        generated_at = self._now_iso()
        quotes, quote_warning = self._load_quotes()
        benchmarks = self._build_benchmarks(quotes, generated_at)
        themes = [
            self._analyze_theme(theme, quotes, benchmarks, generated_at)
            for theme in THEME_BASKETS
        ]
        themes.sort(key=lambda item: (item["rotationScore"], item["confidence"]), reverse=True)
        live_theme_count = sum(1 for theme in themes if not theme["isFallback"] and not theme["isStale"])
        fallback_theme_count = sum(1 for theme in themes if theme["isFallback"])
        stale_theme_count = sum(1 for theme in themes if theme["isStale"])
        payload_fallback = live_theme_count == 0
        freshness = "fallback" if payload_fallback else "stale" if stale_theme_count else "delayed"
        warnings = [
            warning for warning in (
                quote_warning,
                "未接入实时主题资金流数据，当前不输出精确资金流入金额。",
                "Fallback/静态篮子仅用于结构展示，不代表当前行情。",
            ) if warning
        ]
        if not payload_fallback:
            warnings = [warning for warning in warnings if "Fallback/静态篮子" not in warning]
        return {
            "endpoint": RADAR_ENDPOINT,
            "market": "US",
            "supportedMarkets": list(SUPPORTED_ROTATION_MARKETS),
            "generatedAt": generated_at,
            "source": "fallback" if payload_fallback else "computed",
            "sourceLabel": "备用数据" if payload_fallback else "主题篮子计算",
            "freshness": freshness,
            "isFallback": payload_fallback,
            "isStale": bool(stale_theme_count and live_theme_count == 0),
            "warning": "；".join(warnings) if warnings else None,
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
            "benchmarks": benchmarks,
            "summary": self._build_summary(themes),
            "themes": themes,
            "metadata": {
                "schemaVersion": "market_rotation_radar_phase4_v1",
                "noExternalCalls": True,
                "alertsAreReadOnlyEvidence": True,
                "notificationDeliveryEnabled": False,
                "basketSource": "manual_static_baskets",
                "taxonomySource": "src.services.sector_rotation_taxonomy",
                "themeCount": len(THEME_BASKETS),
                "liveThemeCount": live_theme_count,
                "fallbackThemeCount": fallback_theme_count,
                "staleThemeCount": stale_theme_count,
                "scoreRange": "0-100",
                "confidenceRange": "0-1",
                "timeWindows": list(TIME_WINDOW_KEYS),
                "requiredPersistenceWindows": list(TIME_WINDOW_KEYS),
                "proxyQualityRequired": True,
                "benchmarkProxies": {
                    "market": list(MARKET_BENCHMARK_SYMBOLS),
                    "sector": list(SECTOR_BENCHMARK_SYMBOLS),
                },
                "newslessRotationMeaning": "未配置新闻催化证据时，价格/量能/广度/同步性同时满足阈值的保守观察标记，不代表因果确认。",
            },
        }

    def _taxonomy_rotation_radar(self, market: str) -> Dict[str, Any]:
        generated_at = self._now_iso()
        entries = get_rotation_taxonomy_by_market(market)
        themes = [
            self._taxonomy_only_theme(entry, generated_at, index)
            for index, entry in enumerate(entries)
        ]
        return {
            "endpoint": RADAR_ENDPOINT,
            "market": market,
            "supportedMarkets": list(SUPPORTED_ROTATION_MARKETS),
            "generatedAt": generated_at,
            "source": "local_taxonomy",
            "sourceLabel": "静态主题库",
            "freshness": "fallback",
            "isFallback": True,
            "isStale": False,
            "warning": "当前为静态主题库，本地行情覆盖后可计算轮动强度。不代表实时买卖信号。",
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
            "benchmarks": {},
            "summary": {
                "strongestThemes": [],
                "acceleratingThemes": [],
                "fadingThemes": [self._summary_item(theme) for theme in themes[:3]],
                "watchlistSignals": [],
                "watchlistSortingExplanation": "静态主题库仅作分类观察；待本地行情覆盖后才计算轮动强度，非买卖建议。",
                "safeWording": ["主题库已载入", "行情评分待本地数据覆盖", "仅作分类观察", "非买卖建议"],
            },
            "themes": themes,
            "metadata": {
                "schemaVersion": "market_rotation_radar_phase4_v1",
                "noExternalCalls": True,
                "alertsAreReadOnlyEvidence": True,
                "notificationDeliveryEnabled": False,
                "basketSource": "sector_rotation_taxonomy",
                "taxonomySource": "src.services.sector_rotation_taxonomy",
                "themeCount": len(themes),
                "taxonomyOnlyThemeCount": sum(1 for theme in themes if theme.get("staticThemeOnly")),
                "liveThemeCount": 0,
                "fallbackThemeCount": len(themes),
                "staleThemeCount": 0,
                "scoreRange": "0-100",
                "confidenceRange": "0-1",
                "timeWindows": list(TIME_WINDOW_KEYS),
                "proxyQualityRequired": False,
            },
        }

    def _taxonomy_only_theme(self, entry: RotationTaxonomyEntry, generated_at: str, index: int) -> Dict[str, Any]:
        representative = list(entry.representativeSymbols or entry.representativeLabels)
        mapped_concepts = list(entry.mappedConcepts or entry.aliases)
        score = 18 if entry.dataCoverage == "taxonomy_only" else 22
        payload = {
            "id": entry.id,
            "market": entry.market,
            "taxonomyType": entry.taxonomyType,
            "name": entry.displayName,
            "englishName": entry.englishName or entry.displayName,
            "focus": "、".join(mapped_concepts[:4]) if mapped_concepts else entry.operatorNote,
            "benchmark": f"{entry.market}_LOCAL_TAXONOMY",
            "sectorBenchmark": None,
            "membersConfigured": representative,
            "representativeLabels": list(entry.representativeLabels),
            "representativeSymbols": list(entry.representativeSymbols),
            "proxySymbols": list(entry.proxySymbols),
            "mappedConcepts": mapped_concepts,
            "aliases": list(entry.aliases),
            "rotationScore": score,
            "confidence": 0.12,
            "confidenceLabel": "待行情确认",
            "dataQuality": entry.dataCoverage,
            "dataCoverage": entry.dataCoverage,
            "sourceClass": entry.sourceClass,
            "staticThemeOnly": True,
            "stage": "weak_or_no_signal",
            "stageExplanation": "主题库已载入，行情评分待本地数据覆盖，仅作分类观察。",
            "riskLabels": ["stale_or_incomplete_windows"],
            "riskExplanations": ["行情评分待本地数据覆盖，不能确认实时轮动强度。"],
            "newslessRotation": False,
            "newslessRotationEvidence": None,
            "persistenceScore": 0.0,
            "persistenceEvidence": self._fallback_persistence_evidence(),
            "alertCandidates": [],
            "relativeStrength": {
                "benchmark": f"{entry.market}_LOCAL_TAXONOMY",
                "benchmarkChangePercent": None,
                "averageThemeChangePercent": None,
                "averageRelativeStrengthPercent": None,
                "vsBenchmarks": {},
            },
            "proxyQuality": {
                "label": "静态主题库",
                "coveragePercent": 0,
                "availableProxyCount": 0,
                "totalProxyCount": len(entry.proxySymbols),
                "requiredProxies": list(entry.proxySymbols),
                "freshness": "fallback",
                "hasMissingRequiredProxy": False,
                "hasStaleProxy": False,
                "missingReasons": {},
                "explanation": "当前为静态主题库，本地行情覆盖后可计算轮动强度。",
            },
            "benchmarkProxies": {},
            "timeWindows": self._empty_time_windows(),
            "volume": {
                "averageRelativeVolume": None,
                "availableMemberCount": 0,
                "label": "待接入本地行情",
            },
            "breadth": {
                "observedMembers": 0,
                "configuredMembers": len(representative),
                "coveragePercent": 0,
                "percentUp": None,
                "percentOutperformingBenchmark": None,
            },
            "synchronization": {
                "sameDirectionPercent": None,
                "aboveVwapPercent": None,
                "persistencePercent": None,
                "persistenceScore": 0.0,
                "label": "分类观察",
            },
            "leadership": {
                "leadershipConcentrationPercent": None,
                "broadParticipationPercent": None,
                "topMembers": [],
            },
            "themeDetail": {
                "watchlistLabel": "分类观察",
                "watchlistSafe": True,
                "safeActionLabel": "仅观察，不构成买卖建议",
                "leaderSectionLabel": "代表标签",
                "laggardSectionLabel": "待行情确认",
                "leaderExplanation": "代表标签仅用于理解主题范围，不代表实时强弱排序。",
                "laggardExplanation": "本地行情覆盖后才计算扩散与轮动强度。",
                "leadershipMembers": [],
                "laggardMembers": [],
                "memberEvidence": [],
                "freshnessLabel": "静态主题库",
                "asOf": generated_at,
                "disclosure": NO_ADVICE_DISCLOSURE,
                "mappedConcepts": mapped_concepts,
                "representativeLabels": representative,
                "dataStateLabel": "待接入本地行情",
                "nextStep": "本地行情覆盖后可计算轮动强度。",
                "notes": [entry.riskNote, entry.operatorNote],
            },
            "freshness": "fallback",
            "isFallback": True,
            "isStale": False,
            "source": "local_taxonomy",
            "sourceLabel": "静态主题库",
            "asOf": generated_at,
            "updatedAt": generated_at,
            "evidence": ["主题库已载入", "行情评分待本地数据覆盖", "仅作分类观察"],
            "members": [],
            "sortOrder": index,
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        }
        payload["rotationStateEvidence"] = self._rotation_state_evidence(payload, generated_at)
        return payload

    def _load_quotes(self) -> tuple[Dict[str, Dict[str, Any]], Optional[str]]:
        if self.quote_provider is None:
            return {}, "未配置实时 quote provider，返回降级主题篮子。"
        symbols = sorted(
            {symbol for theme in THEME_BASKETS for symbol in theme.members}
            | {theme.benchmark for theme in THEME_BASKETS}
            | {theme.sectorBenchmark for theme in THEME_BASKETS}
            | set(MARKET_BENCHMARK_SYMBOLS)
        )
        try:
            raw_quotes = self.quote_provider(symbols) or {}
        except Exception:
            return {}, "quote provider 暂不可用，已降级为静态篮子。"
        normalized: Dict[str, Dict[str, Any]] = {}
        for symbol in symbols:
            raw_quote = raw_quotes.get(symbol) if isinstance(raw_quotes, Mapping) else None
            if isinstance(raw_quote, Mapping):
                quote = self._normalize_quote(symbol, raw_quote)
                if quote:
                    normalized[symbol] = quote
        if not normalized:
            return {}, "quote provider 未返回可用行情，已降级为静态篮子。"
        return normalized, None

    def _build_benchmarks(self, quotes: Mapping[str, Dict[str, Any]], generated_at: str) -> Dict[str, Dict[str, Any]]:
        benchmarks: Dict[str, Dict[str, Any]] = {}
        for symbol in BENCHMARK_SYMBOLS:
            quote = quotes.get(symbol)
            if quote:
                benchmarks[symbol] = {
                    "symbol": symbol,
                    "changePercent": quote.get("changePercent"),
                    "timeWindows": quote.get("timeWindows") or self._empty_time_windows(),
                    "freshness": quote.get("freshness"),
                    "isFallback": bool(quote.get("isFallback")),
                    "isStale": bool(quote.get("isStale")),
                    "source": quote.get("source"),
                    "sourceLabel": quote.get("sourceLabel"),
                    "asOf": quote.get("asOf"),
                }
            else:
                benchmarks[symbol] = {
                    "symbol": symbol,
                    "changePercent": None,
                    "timeWindows": self._empty_time_windows(),
                    "freshness": "fallback",
                    "isFallback": True,
                    "isStale": False,
                    "source": "fallback",
                    "sourceLabel": "备用数据",
                    "asOf": generated_at,
                }
        return benchmarks

    def _analyze_theme(
        self,
        theme: ThemeBasket,
        quotes: Mapping[str, Dict[str, Any]],
        benchmarks: Mapping[str, Dict[str, Any]],
        generated_at: str,
    ) -> Dict[str, Any]:
        observations = [
            self._member_observation(symbol, quotes.get(symbol), theme, benchmarks)
            for symbol in theme.members
        ]
        observed = [item for item in observations if item["observed"]]
        if not observed:
            return self._fallback_theme(theme, observations, benchmarks, generated_at)

        benchmark_change = self._theme_benchmark_change(theme, benchmarks)
        changes = [float(item["changePercent"]) for item in observed if item["changePercent"] is not None]
        relative_values = [float(item["relativeStrengthVsBenchmark"]) for item in observed if item["relativeStrengthVsBenchmark"] is not None]
        volume_ratios = [float(item["volumeRatio"]) for item in observed if item["volumeRatio"] is not None]
        vwap_values = [bool(item["priceAboveVwap"]) for item in observed if item["priceAboveVwap"] is not None]
        persistence_values = [float(item["persistenceScore"]) for item in observed if item["persistenceScore"] is not None]
        observed_count = len(observed)
        member_count = len(theme.members)
        coverage = observed_count / member_count if member_count else 0.0
        percent_up = self._percent(sum(1 for value in changes if value > 0), observed_count)
        percent_outperforming = self._percent(sum(1 for value in relative_values if value > 0), observed_count)
        dominant_direction = max(percent_up, 100 - percent_up)
        average_change = self._avg(changes)
        average_relative_strength = self._avg(relative_values)
        average_relative_volume = self._avg(volume_ratios, default=1.0)
        above_vwap_pct = self._percent(sum(1 for value in vwap_values if value), len(vwap_values)) if vwap_values else 50.0
        persistence_pct = self._percent(sum(1 for value in persistence_values if value >= 0.6), len(persistence_values)) if persistence_values else 50.0
        concentration = self._leadership_concentration(changes)
        time_windows = self._aggregate_time_windows(observed)
        window_state = self._time_window_state(time_windows)
        persistence_evidence = self._persistence_evidence(time_windows)
        proxy_quality = self._proxy_quality(theme, benchmarks)
        source_state = self._source_state(observations, benchmarks, theme.benchmark)
        source_state["timeWindowState"] = window_state
        source_state["proxyQuality"] = proxy_quality
        score = self._score(
            average_relative_strength=average_relative_strength,
            average_relative_volume=average_relative_volume,
            percent_up=percent_up,
            percent_outperforming=percent_outperforming,
            synchronization_pct=dominant_direction,
            above_vwap_pct=above_vwap_pct,
            persistence_pct=persistence_pct,
            coverage=coverage,
            concentration=concentration,
            is_stale=source_state["isStale"],
            fallback_used=source_state["fallbackUsed"],
        )
        confidence = self._confidence(
            coverage=coverage,
            source_state=source_state,
            average_relative_volume=average_relative_volume,
            percent_up=percent_up,
            percent_outperforming=percent_outperforming,
        )
        risk_labels = self._risk_labels(
            source_state=source_state,
            coverage=coverage,
            percent_up=percent_up,
            percent_outperforming=percent_outperforming,
            average_change=average_change,
            average_relative_volume=average_relative_volume,
            above_vwap_pct=above_vwap_pct,
            concentration=concentration,
        )
        stage = self._stage(
            score=score,
            confidence=confidence,
            risk_labels=risk_labels,
            percent_up=percent_up,
            percent_outperforming=percent_outperforming,
            average_relative_volume=average_relative_volume,
        )
        newsless_rotation = self._newsless_rotation(
            score=score,
            confidence=confidence,
            percent_outperforming=percent_outperforming,
            synchronization_pct=dominant_direction,
            average_relative_volume=average_relative_volume,
            source_state=source_state,
        )
        leaders = self._leaders(observed)
        evidence = self._evidence(
            theme=theme,
            observed_count=observed_count,
            member_count=member_count,
            average_relative_strength=average_relative_strength,
            average_relative_volume=average_relative_volume,
            percent_up=percent_up,
            percent_outperforming=percent_outperforming,
            synchronization_pct=dominant_direction,
            above_vwap_pct=above_vwap_pct,
            concentration=concentration,
            newsless_rotation=newsless_rotation,
        )
        freshness = "stale" if source_state["isStale"] else "fallback" if source_state["fallbackUsed"] and coverage < 0.6 else "delayed"
        payload = {
            "id": theme.id,
            "market": theme.market,
            "taxonomyType": theme.taxonomyType,
            "name": theme.name,
            "englishName": theme.englishName,
            "focus": theme.focus,
            "benchmark": theme.benchmark,
            "sectorBenchmark": theme.sectorBenchmark,
            "membersConfigured": list(theme.members),
            "representativeLabels": list(theme.members),
            "representativeSymbols": list(theme.members),
            "proxySymbols": list(theme.proxySymbols),
            "mappedConcepts": list(theme.mappedConcepts),
            "aliases": list(theme.aliases),
            "rotationScore": score,
            "confidence": confidence,
            "confidenceLabel": "行情确认",
            "dataQuality": theme.dataCoverage,
            "dataCoverage": theme.dataCoverage,
            "sourceClass": theme.sourceClass,
            "staticThemeOnly": False,
            "stage": stage,
            "stageExplanation": self._stage_explanation(stage, confidence, source_state.get("timeWindowState", {})),
            "riskLabels": risk_labels,
            "riskExplanations": self._risk_explanations(risk_labels),
            "newslessRotation": newsless_rotation,
            "newslessRotationEvidence": (
                "无明显新闻的同步异动：未配置新闻催化证据，当前仅由价格、量能、广度和同步性共同触发。"
                if newsless_rotation else None
            ),
            "persistenceScore": persistence_evidence["score"],
            "persistenceEvidence": persistence_evidence,
            "alertCandidates": self._alert_candidates(
                theme=theme,
                leaders=leaders,
                stage=stage,
                confidence=confidence,
                persistence_evidence=persistence_evidence,
                risk_labels=risk_labels,
                source_state=source_state,
            ),
            "relativeStrength": {
                "benchmark": theme.benchmark,
                "benchmarkChangePercent": round(benchmark_change, 3) if benchmark_change is not None else None,
                "averageThemeChangePercent": round(average_change, 3),
                "averageRelativeStrengthPercent": round(average_relative_strength, 3),
                "vsBenchmarks": self._relative_vs_benchmarks(observed, benchmarks),
            },
            "proxyQuality": proxy_quality,
            "benchmarkProxies": self._benchmark_proxies(theme, benchmarks, observed),
            "timeWindows": time_windows,
            "volume": {
                "averageRelativeVolume": round(average_relative_volume, 2),
                "availableMemberCount": len(volume_ratios),
                "label": self._volume_label(average_relative_volume),
            },
            "breadth": {
                "observedMembers": observed_count,
                "configuredMembers": member_count,
                "coveragePercent": round(coverage * 100, 1),
                "percentUp": round(percent_up, 1),
                "percentOutperformingBenchmark": round(percent_outperforming, 1),
            },
            "synchronization": {
                "sameDirectionPercent": round(dominant_direction, 1),
                "aboveVwapPercent": round(above_vwap_pct, 1),
                "persistencePercent": round(persistence_pct, 1),
                "persistenceScore": persistence_evidence["score"],
                "label": self._synchronization_label(dominant_direction),
            },
            "leadership": {
                "leadershipConcentrationPercent": round(concentration * 100, 1),
                "broadParticipationPercent": round((1 - concentration) * 100, 1),
                "topMembers": leaders,
            },
            "themeDetail": self._theme_detail(
                theme=theme,
                observations=observations,
                leaders=leaders,
                generated_at=generated_at,
            ),
            "freshness": freshness,
            "isFallback": bool(source_state["fallbackUsed"] and coverage < 0.6),
            "isStale": bool(source_state["isStale"]),
            "source": "mixed" if source_state["fallbackUsed"] else "computed",
            "sourceLabel": "部分数据降级" if source_state["fallbackUsed"] else "主题篮子计算",
            "asOf": source_state["asOf"] or generated_at,
            "updatedAt": generated_at,
            "evidence": evidence,
            "members": observations,
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        }
        payload["rotationStateEvidence"] = self._rotation_state_evidence(payload, generated_at)
        return payload

    def _fallback_theme(
        self,
        theme: ThemeBasket,
        observations: Sequence[Dict[str, Any]],
        benchmarks: Mapping[str, Dict[str, Any]],
        generated_at: str,
    ) -> Dict[str, Any]:
        preset = FALLBACK_PRESETS.get(theme.id, {"score": 20, "leaders": theme.members[:3]})
        leaders = [
            {
                "symbol": symbol,
                "name": symbol,
                "changePercent": None,
                "relativeStrengthVsBenchmark": None,
                "volumeRatio": None,
                "freshness": "fallback",
                "isFallback": True,
            }
            for symbol in preset.get("leaders", theme.members[:3])
        ]
        payload = {
            "id": theme.id,
            "market": theme.market,
            "taxonomyType": theme.taxonomyType,
            "name": theme.name,
            "englishName": theme.englishName,
            "focus": theme.focus,
            "benchmark": theme.benchmark,
            "sectorBenchmark": theme.sectorBenchmark,
            "membersConfigured": list(theme.members),
            "representativeLabels": list(theme.members),
            "representativeSymbols": list(theme.members),
            "proxySymbols": list(theme.proxySymbols),
            "mappedConcepts": list(theme.mappedConcepts),
            "aliases": list(theme.aliases),
            "rotationScore": int(preset["score"]),
            "confidence": 0.12,
            "confidenceLabel": "待行情确认",
            "dataQuality": "fallback_static",
            "dataCoverage": theme.dataCoverage,
            "sourceClass": theme.sourceClass,
            "staticThemeOnly": True,
            "stage": "weak_or_no_signal",
            "stageExplanation": "备用篮子缺少可用行情与时窗证据，仅能标记为弱信号。",
            "riskLabels": ["stale_or_incomplete_windows", "thin_breadth"],
            "riskExplanations": self._risk_explanations(["stale_or_incomplete_windows", "thin_breadth"]),
            "newslessRotation": False,
            "newslessRotationEvidence": None,
            "persistenceScore": 0.0,
            "persistenceEvidence": self._fallback_persistence_evidence(),
            "alertCandidates": [],
            "relativeStrength": {
                "benchmark": theme.benchmark,
                "benchmarkChangePercent": None,
                "averageThemeChangePercent": None,
                "averageRelativeStrengthPercent": None,
                "vsBenchmarks": {symbol: None for symbol in BENCHMARK_SYMBOLS},
            },
            "proxyQuality": self._proxy_quality(theme, benchmarks),
            "benchmarkProxies": self._benchmark_proxies(theme, benchmarks, []),
            "timeWindows": self._empty_time_windows(),
            "volume": {
                "averageRelativeVolume": None,
                "availableMemberCount": 0,
                "label": "成交额扩张证据不足",
            },
            "breadth": {
                "observedMembers": 0,
                "configuredMembers": len(theme.members),
                "coveragePercent": 0,
                "percentUp": 0,
                "percentOutperformingBenchmark": 0,
            },
            "synchronization": {
                "sameDirectionPercent": 0,
                "aboveVwapPercent": 0,
                "persistencePercent": 0,
                "persistenceScore": 0.0,
                "label": "同步性证据不足",
            },
            "leadership": {
                "leadershipConcentrationPercent": 0,
                "broadParticipationPercent": 0,
                "topMembers": leaders,
            },
            "themeDetail": self._theme_detail(
                theme=theme,
                observations=observations,
                leaders=leaders,
                generated_at=generated_at,
            ),
            "freshness": "fallback",
            "isFallback": True,
            "isStale": False,
            "source": "fallback",
            "sourceLabel": "备用数据",
            "asOf": generated_at,
            "updatedAt": generated_at,
            "evidence": [
                "静态主题篮子示例，未接入行情快照。",
                "当前仅展示资金轮动迹象的计算框架，不输出实时资金流金额。",
                "需等待真实价格、成交额、广度与同步性数据。",
            ],
            "members": list(observations),
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        }
        payload["rotationStateEvidence"] = self._rotation_state_evidence(payload, generated_at)
        return payload

    def _rotation_state_evidence(self, theme: Mapping[str, Any], generated_at: str) -> Dict[str, Any]:
        return build_rotation_state_evidence(
            theme,
            {
                "market": theme.get("market"),
                "taxonomyVersion": ROTATION_TAXONOMY_VERSION,
                "computedAt": theme.get("updatedAt") or generated_at,
                "asOf": theme.get("asOf") or generated_at,
            },
        )

    def _member_observation(
        self,
        symbol: str,
        quote: Optional[Dict[str, Any]],
        theme: ThemeBasket,
        benchmarks: Mapping[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        benchmark_change = self._theme_benchmark_change(theme, benchmarks)
        if not quote:
            return {
                "symbol": symbol,
                "name": symbol,
                "observed": False,
                "changePercent": None,
                "relativeStrengthVsBenchmark": None,
                "volumeRatio": None,
                "timeWindows": self._empty_time_windows(),
                "priceAboveVwap": None,
                "persistenceScore": None,
                "leadershipLabel": "未观察",
                "freshnessLabel": "窗口数据待补齐",
                "freshness": "fallback",
                "isFallback": True,
                "isStale": False,
                "source": "fallback",
                "sourceLabel": "备用数据",
                "notes": ["quote_missing"],
            }
        change = quote.get("changePercent")
        relative_strength = change - benchmark_change if change is not None and benchmark_change is not None else None
        price = quote.get("price")
        vwap = quote.get("vwap")
        trend = quote.get("trend") if isinstance(quote.get("trend"), list) else []
        return {
            "symbol": symbol,
            "name": quote.get("name") or symbol,
            "observed": change is not None,
            "price": price,
            "changePercent": round(change, 3) if change is not None else None,
            "relativeStrengthVsBenchmark": round(relative_strength, 3) if relative_strength is not None else None,
            "volumeRatio": round(quote["volumeRatio"], 3) if quote.get("volumeRatio") is not None else None,
            "timeWindows": quote.get("timeWindows") or self._empty_time_windows(),
            "priceAboveVwap": bool(price >= vwap) if price is not None and vwap is not None else None,
            "persistenceScore": self._persistence_score(trend, change),
            "leadershipLabel": self._member_role_label(change, relative_strength, quote.get("volumeRatio")),
            "freshnessLabel": self._freshness_label(str(quote.get("freshness", "delayed")), bool(quote.get("isFallback")), bool(quote.get("isStale"))),
            "freshness": quote.get("freshness", "delayed"),
            "isFallback": bool(quote.get("isFallback")),
            "isStale": bool(quote.get("isStale")),
            "source": quote.get("source"),
            "sourceLabel": quote.get("sourceLabel"),
            "asOf": quote.get("asOf"),
            "notes": [],
        }

    def _normalize_quote(self, symbol: str, raw_quote: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        change = self._number(
            raw_quote.get("changePercent", raw_quote.get("change_pct", raw_quote.get("pct_change", raw_quote.get("change"))))
        )
        price = self._number(raw_quote.get("price", raw_quote.get("value", raw_quote.get("last"))))
        vwap = self._number(raw_quote.get("vwap", raw_quote.get("VWAP")))
        volume_ratio = self._number(raw_quote.get("volumeRatio", raw_quote.get("relativeVolume", raw_quote.get("relative_volume"))))
        volume = self._number(raw_quote.get("volume"))
        average_volume = self._number(
            raw_quote.get("averageVolume", raw_quote.get("avgVolume", raw_quote.get("avg_volume", raw_quote.get("avg_volume_20"))))
        )
        if volume_ratio is None and volume is not None and average_volume and average_volume > 0:
            volume_ratio = volume / average_volume
        if change is None and price is None:
            return None
        source = str(raw_quote.get("source") or "normalized_quote")
        freshness = str(raw_quote.get("freshness") or "delayed")
        is_fallback = bool(raw_quote.get("isFallback") or raw_quote.get("fallbackUsed") or freshness in {"fallback", "mock"})
        is_stale = bool(raw_quote.get("isStale") or freshness == "stale")
        trend = raw_quote.get("trend", raw_quote.get("sparkline"))
        trend_values = [value for value in (self._number(item) for item in trend or []) if value is not None] if isinstance(trend, list) else []
        as_of = str(raw_quote.get("asOf") or raw_quote.get("as_of") or raw_quote.get("updatedAt") or self._now_iso())
        source_label = str(raw_quote.get("sourceLabel") or raw_quote.get("source_label") or "主题篮子行情")
        normalized_freshness = "fallback" if is_fallback else "stale" if is_stale else freshness
        time_windows = self._normalize_time_windows(
            raw_quote=raw_quote,
            change=change,
            volume_ratio=volume_ratio,
            freshness=normalized_freshness,
            is_fallback=is_fallback,
            is_stale=is_stale,
            source=source,
            source_label=source_label,
            as_of=as_of,
        )
        return {
            "symbol": symbol,
            "name": str(raw_quote.get("name") or raw_quote.get("label") or symbol),
            "price": price,
            "changePercent": change,
            "volumeRatio": volume_ratio,
            "vwap": vwap,
            "trend": trend_values,
            "timeWindows": time_windows,
            "freshness": normalized_freshness,
            "isFallback": is_fallback,
            "isStale": is_stale,
            "source": source,
            "sourceLabel": source_label,
            "asOf": as_of,
        }

    def _source_state(
        self,
        observations: Sequence[Dict[str, Any]],
        benchmarks: Mapping[str, Dict[str, Any]],
        benchmark_symbol: str,
    ) -> Dict[str, Any]:
        fallback_used = any(item["observed"] and item["isFallback"] for item in observations)
        is_stale = any(item["isStale"] for item in observations)
        benchmark = benchmarks.get(benchmark_symbol, {})
        fallback_used = fallback_used or bool(benchmark.get("isFallback"))
        is_stale = is_stale or bool(benchmark.get("isStale"))
        as_of_candidates = [
            str(item.get("asOf"))
            for item in observations
            if item.get("asOf")
        ]
        if benchmark.get("asOf"):
            as_of_candidates.append(str(benchmark.get("asOf")))
        return {
            "fallbackUsed": fallback_used,
            "isStale": is_stale,
            "asOf": max(as_of_candidates) if as_of_candidates else None,
        }

    def _normalize_time_windows(
        self,
        *,
        raw_quote: Mapping[str, Any],
        change: Optional[float],
        volume_ratio: Optional[float],
        freshness: str,
        is_fallback: bool,
        is_stale: bool,
        source: str,
        source_label: str,
        as_of: str,
    ) -> Dict[str, Dict[str, Any]]:
        raw_windows = raw_quote.get("timeWindows") or raw_quote.get("time_windows") or raw_quote.get("windows")
        raw_windows = raw_windows if isinstance(raw_windows, Mapping) else {}
        windows: Dict[str, Dict[str, Any]] = {}
        for window in TIME_WINDOW_KEYS:
            raw_window = raw_windows.get(window)
            if isinstance(raw_window, Mapping):
                window_change = self._number(
                    raw_window.get("changePercent", raw_window.get("change_pct", raw_window.get("pct_change")))
                )
                window_volume_ratio = self._number(
                    raw_window.get("volumeRatio", raw_window.get("relativeVolume", raw_window.get("relative_volume")))
                )
                available = window_change is not None or window_volume_ratio is not None
                window_freshness = str(raw_window.get("freshness") or freshness)
                window_is_fallback = bool(raw_window.get("isFallback") or raw_window.get("fallbackUsed") or is_fallback)
                window_is_stale = bool(raw_window.get("isStale") or is_stale or window_freshness == "stale")
                windows[window] = {
                    "window": window,
                    "label": TIME_WINDOW_LABELS[window],
                    "available": available,
                    "changePercent": round(window_change, 3) if window_change is not None else None,
                    "relativeVolume": round(window_volume_ratio, 3) if window_volume_ratio is not None else None,
                    "freshness": "fallback" if window_is_fallback else "stale" if window_is_stale else window_freshness,
                    "isFallback": window_is_fallback,
                    "isStale": window_is_stale,
                    "source": str(raw_window.get("source") or source),
                    "sourceLabel": str(raw_window.get("sourceLabel") or raw_window.get("source_label") or source_label),
                    "asOf": str(raw_window.get("asOf") or raw_window.get("as_of") or as_of),
                    "reason": None if available else "window_unavailable",
                }
                continue
            if window == "1d" and change is not None:
                windows[window] = {
                    "window": window,
                    "label": TIME_WINDOW_LABELS[window],
                    "available": True,
                    "changePercent": round(change, 3),
                    "relativeVolume": round(volume_ratio, 3) if volume_ratio is not None else None,
                    "freshness": freshness,
                    "isFallback": is_fallback,
                    "isStale": is_stale,
                    "source": source,
                    "sourceLabel": source_label,
                    "asOf": as_of,
                    "reason": None,
                }
                continue
            windows[window] = self._empty_time_window(window)
        return windows

    def _aggregate_time_windows(self, observed: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
        windows: Dict[str, Dict[str, Any]] = {}
        for window in TIME_WINDOW_KEYS:
            slots = [
                item.get("timeWindows", {}).get(window, {})
                for item in observed
                if isinstance(item.get("timeWindows"), Mapping)
            ]
            available_slots = [slot for slot in slots if slot.get("available")]
            changes = [float(slot["changePercent"]) for slot in available_slots if slot.get("changePercent") is not None]
            volumes = [float(slot["relativeVolume"]) for slot in available_slots if slot.get("relativeVolume") is not None]
            is_stale = any(slot.get("isStale") for slot in available_slots)
            is_fallback = not available_slots or any(slot.get("isFallback") for slot in available_slots)
            windows[window] = {
                "window": window,
                "label": TIME_WINDOW_LABELS[window],
                "available": bool(available_slots),
                "observedMemberCount": len(available_slots),
                "configuredMemberCount": len(observed),
                "averageChangePercent": round(self._avg(changes), 3) if changes else None,
                "averageRelativeVolume": round(self._avg(volumes), 3) if volumes else None,
                "percentUp": round(self._percent(sum(1 for value in changes if value > 0), len(changes)), 1) if changes else None,
                "freshness": "fallback" if is_fallback else "stale" if is_stale else self._freshest_window_label(available_slots),
                "isFallback": is_fallback,
                "isStale": is_stale,
                "reason": None if available_slots else "window_unavailable",
            }
        return windows

    def _time_window_state(self, time_windows: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
        available = [window for window in TIME_WINDOW_KEYS if time_windows.get(window, {}).get("available")]
        intraday_available = [window for window in ("5m", "15m", "60m") if window in available]
        stale_or_fallback = [
            window for window in TIME_WINDOW_KEYS
            if time_windows.get(window, {}).get("isStale") or time_windows.get(window, {}).get("isFallback")
        ]
        return {
            "availableWindows": available,
            "availableWindowCount": len(available),
            "missingWindows": [window for window in TIME_WINDOW_KEYS if window not in available],
            "staleOrFallbackWindows": stale_or_fallback,
            "intradayAvailableCount": len(intraday_available),
            "hasDailyWindow": "1d" in available,
            "hasStaleWindow": any(time_windows.get(window, {}).get("isStale") for window in TIME_WINDOW_KEYS),
            "hasFallbackWindow": any(time_windows.get(window, {}).get("isFallback") for window in TIME_WINDOW_KEYS),
        }

    def _persistence_evidence(self, time_windows: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
        available_windows = [
            window for window in TIME_WINDOW_KEYS
            if time_windows.get(window, {}).get("available")
        ]
        missing_windows = [window for window in TIME_WINDOW_KEYS if window not in available_windows]
        stale_or_fallback_windows = [
            window for window in TIME_WINDOW_KEYS
            if time_windows.get(window, {}).get("isStale") or time_windows.get(window, {}).get("isFallback")
        ]
        changes = [
            float(time_windows[window]["averageChangePercent"])
            for window in available_windows
            if time_windows.get(window, {}).get("averageChangePercent") is not None
        ]
        positive_count = sum(1 for value in changes if value > 0)
        negative_count = sum(1 for value in changes if value < 0)
        same_direction_count = max(positive_count, negative_count)
        coverage_score = len(available_windows) / len(TIME_WINDOW_KEYS)
        direction_score = same_direction_count / len(changes) if changes else 0.0
        penalty = 0.2 if stale_or_fallback_windows else 0.0
        score = round(max(0.0, min(1.0, coverage_score * 0.55 + direction_score * 0.45 - penalty)), 2)
        if not available_windows:
            label = "跨时窗证据待补齐"
        elif score >= 0.78 and positive_count >= max(2, negative_count):
            label = "跨时窗延续"
        elif score >= 0.55:
            label = "跨时窗待确认"
        elif negative_count > positive_count and len(changes) >= 2:
            label = "跨时窗降温"
        else:
            label = "跨时窗证据不足"
        return {
            "score": score,
            "label": label,
            "availableWindows": available_windows,
            "missingWindows": missing_windows,
            "staleOrFallbackWindows": stale_or_fallback_windows,
            "positiveWindowCount": positive_count,
            "negativeWindowCount": negative_count,
            "sameDirectionWindowCount": same_direction_count,
            "requiredWindows": list(TIME_WINDOW_KEYS),
            "explanation": self._persistence_explanation(label, available_windows, missing_windows, stale_or_fallback_windows),
        }

    def _fallback_persistence_evidence(self) -> Dict[str, Any]:
        return {
            "score": 0.0,
            "label": "跨时窗证据待补齐",
            "availableWindows": [],
            "missingWindows": list(TIME_WINDOW_KEYS),
            "staleOrFallbackWindows": list(TIME_WINDOW_KEYS),
            "positiveWindowCount": 0,
            "negativeWindowCount": 0,
            "sameDirectionWindowCount": 0,
            "requiredWindows": list(TIME_WINDOW_KEYS),
            "explanation": "5m/15m/60m/1d 时窗均缺失或为备用状态，不能确认延续。",
        }

    @staticmethod
    def _persistence_explanation(
        label: str,
        available_windows: Sequence[str],
        missing_windows: Sequence[str],
        stale_or_fallback_windows: Sequence[str],
    ) -> str:
        available_text = "/".join(available_windows) if available_windows else "无"
        missing_text = "/".join(missing_windows) if missing_windows else "无"
        stale_text = "/".join(stale_or_fallback_windows) if stale_or_fallback_windows else "无"
        return f"{label}：可用 {available_text}，缺失 {missing_text}，备用/过期 {stale_text}。"

    def _empty_time_windows(self) -> Dict[str, Dict[str, Any]]:
        return {window: self._empty_time_window(window) for window in TIME_WINDOW_KEYS}

    @staticmethod
    def _empty_time_window(window: str) -> Dict[str, Any]:
        return {
            "window": window,
            "label": TIME_WINDOW_LABELS[window],
            "available": False,
            "changePercent": None,
            "relativeVolume": None,
            "freshness": "fallback",
            "isFallback": True,
            "isStale": False,
            "source": "fallback",
            "sourceLabel": "窗口数据待补齐",
            "asOf": None,
            "reason": "window_unavailable",
        }

    @staticmethod
    def _freshest_window_label(slots: Sequence[Mapping[str, Any]]) -> str:
        values = [str(slot.get("freshness")) for slot in slots if slot.get("freshness")]
        for candidate in ("live", "mock", "delayed", "cached", "stale", "fallback"):
            if candidate in values:
                return candidate
        return "fallback"

    def _score(
        self,
        *,
        average_relative_strength: float,
        average_relative_volume: float,
        percent_up: float,
        percent_outperforming: float,
        synchronization_pct: float,
        above_vwap_pct: float,
        persistence_pct: float,
        coverage: float,
        concentration: float,
        is_stale: bool,
        fallback_used: bool,
    ) -> int:
        relative_score = self._clamp(50 + average_relative_strength * 10)
        volume_score = self._clamp(50 + (average_relative_volume - 1.0) * 30)
        breadth_score = self._clamp(percent_up * 0.55 + percent_outperforming * 0.45)
        sync_score = self._clamp(synchronization_pct)
        vwap_score = self._clamp(above_vwap_pct)
        persistence_score = self._clamp(persistence_pct)
        raw_score = (
            relative_score * 0.28
            + breadth_score * 0.22
            + volume_score * 0.18
            + sync_score * 0.14
            + vwap_score * 0.10
            + persistence_score * 0.08
        )
        penalty = 0.0
        if coverage < 0.6:
            penalty += 12
        if fallback_used:
            penalty += 8
        if is_stale:
            penalty += 12
        if concentration > 0.48:
            penalty += 7
        return int(round(self._clamp(raw_score - penalty)))

    def _confidence(
        self,
        *,
        coverage: float,
        source_state: Mapping[str, Any],
        average_relative_volume: float,
        percent_up: float,
        percent_outperforming: float,
    ) -> float:
        structure = (
            min(1.0, average_relative_volume / 1.5) * 0.25
            + (percent_up / 100) * 0.25
            + (percent_outperforming / 100) * 0.25
            + coverage * 0.25
        )
        confidence = coverage * 0.55 + structure * 0.45
        if source_state["fallbackUsed"]:
            confidence = min(confidence, 0.5 if coverage >= 0.75 else 0.42)
        if source_state["isStale"]:
            confidence = min(confidence, 0.5)
        window_state = source_state.get("timeWindowState", {})
        if not window_state.get("hasDailyWindow"):
            confidence = min(confidence, 0.55)
        elif int(window_state.get("intradayAvailableCount") or 0) == 0:
            confidence = min(confidence, 0.6)
        if window_state.get("hasStaleWindow"):
            confidence = min(confidence, 0.5)
        if int(window_state.get("availableWindowCount") or 0) < len(TIME_WINDOW_KEYS):
            confidence = min(confidence, 0.68)
        if window_state.get("hasFallbackWindow") and int(window_state.get("intradayAvailableCount") or 0) < 2:
            confidence = min(confidence, 0.6)
        if window_state.get("staleOrFallbackWindows"):
            confidence = min(confidence, 0.68)
        proxy_quality = source_state.get("proxyQuality", {})
        proxy_coverage = float(proxy_quality.get("coveragePercent") or 0.0)
        if proxy_coverage < 100:
            confidence = min(confidence, 0.58 if proxy_coverage >= 75 else 0.5 if proxy_coverage >= 50 else 0.35)
        if proxy_quality.get("hasStaleProxy"):
            confidence = min(confidence, 0.5)
        return round(max(0.0, min(1.0, confidence)), 2)

    def _risk_labels(
        self,
        *,
        source_state: Mapping[str, Any],
        coverage: float,
        percent_up: float,
        percent_outperforming: float,
        average_change: float,
        average_relative_volume: float,
        above_vwap_pct: float,
        concentration: float,
    ) -> List[str]:
        labels: List[str] = []
        window_state = source_state.get("timeWindowState", {})
        if (
            source_state["isStale"]
            or source_state["fallbackUsed"]
            or bool(source_state.get("proxyQuality", {}).get("hasMissingRequiredProxy"))
            or bool(source_state.get("proxyQuality", {}).get("hasStaleProxy"))
            or int(window_state.get("availableWindowCount") or 0) < len(TIME_WINDOW_KEYS)
            or bool(window_state.get("staleOrFallbackWindows"))
        ):
            labels.append("stale_or_incomplete_windows")
        if coverage < 0.65 or percent_up < 55 or percent_outperforming < 55:
            labels.append("thin_breadth")
        if concentration > 0.48:
            labels.append("single_name_driven")
        if average_change >= 3.0 and (above_vwap_pct < 60 or average_relative_volume < 1.15 or percent_up < 70):
            labels.append("gap_fade_risk")
        return labels

    def _stage(
        self,
        *,
        score: int,
        confidence: float,
        risk_labels: Sequence[str],
        percent_up: float,
        percent_outperforming: float,
        average_relative_volume: float,
    ) -> str:
        if confidence < 0.35 or score < 45:
            return "weak_or_no_signal"
        if score >= 76 and confidence >= 0.65 and percent_up >= 65 and percent_outperforming >= 65:
            if "single_name_driven" in risk_labels or "gap_fade_risk" in risk_labels:
                return "extended_watch"
            return "confirmed_rotation"
        if score >= 60 and confidence >= 0.45:
            if "single_name_driven" in risk_labels and percent_up < 65:
                return "extended_watch"
            return "early_watch"
        if average_relative_volume < 0.9 or percent_up < 50:
            return "cooling_watch"
        return "weak_or_no_signal"

    @staticmethod
    def _stage_explanation(stage: str, confidence: float, window_state: Mapping[str, Any]) -> str:
        intraday_count = int(window_state.get("intradayAvailableCount") or 0)
        has_daily = bool(window_state.get("hasDailyWindow"))
        window_note = (
            f"{intraday_count} 个分钟级时窗可用"
            if intraday_count
            else "分钟级时窗待补齐"
        )
        if not has_daily:
            window_note = "日线与分钟级时窗均待补齐"
        stage_notes = {
            "confirmed_rotation": "价格、量能、广度和同步性同时满足阈值。",
            "early_watch": "已有相对强势或量能扩张，但仍需更多广度/时窗确认。",
            "extended_watch": "强度较高但存在集中或高开回落风险。",
            "cooling_watch": "量能或上涨广度转弱，轮动证据降温。",
            "weak_or_no_signal": "可用证据不足或分歧较大。",
        }
        return f"{stage_notes.get(stage, '阶段待识别')} 置信度 {confidence:.0%}，{window_note}。"

    @staticmethod
    def _risk_explanations(risk_labels: Sequence[str]) -> List[str]:
        explanations = {
            "gap_fade_risk": "涨幅较大但 VWAP、量能或广度确认不足，需防止冲高回落。",
            "thin_breadth": "可观察成员或跑赢成员偏少，主题扩散仍不充分。",
            "single_name_driven": "正贡献集中在少数成员，主题广泛参与度不足。",
            "stale_or_incomplete_windows": "部分 5m/15m/60m/1d 时窗缺失、备用或过期，置信度已封顶。",
        }
        return [explanations[label] for label in risk_labels if label in explanations]

    def _newsless_rotation(
        self,
        *,
        score: int,
        confidence: float,
        percent_outperforming: float,
        synchronization_pct: float,
        average_relative_volume: float,
        source_state: Mapping[str, Any],
    ) -> bool:
        return bool(
            not source_state["fallbackUsed"]
            and not source_state["isStale"]
            and score >= 68
            and confidence >= 0.55
            and percent_outperforming >= 65
            and synchronization_pct >= 65
            and average_relative_volume >= 1.15
        )

    def _evidence(
        self,
        *,
        theme: ThemeBasket,
        observed_count: int,
        member_count: int,
        average_relative_strength: float,
        average_relative_volume: float,
        percent_up: float,
        percent_outperforming: float,
        synchronization_pct: float,
        above_vwap_pct: float,
        concentration: float,
        newsless_rotation: bool,
    ) -> List[str]:
        items = [
            f"{observed_count}/{member_count} 成员有可用快照",
            f"相对 {theme.benchmark} 强弱 {average_relative_strength:+.2f}%",
            f"平均量比 {average_relative_volume:.2f}x，显示成交额扩张迹象",
            f"上涨广度 {percent_up:.0f}%，跑赢基准 {percent_outperforming:.0f}%",
            f"同步性 {synchronization_pct:.0f}%，站上 VWAP {above_vwap_pct:.0f}%",
            f"龙头集中度 {concentration * 100:.0f}%",
        ]
        if newsless_rotation:
            items.append("无明显新闻的同步异动")
        return items

    def _build_summary(self, themes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        strongest = [self._summary_item(theme) for theme in themes[:3]]
        accelerating = [
            self._summary_item(theme)
            for theme in themes
            if theme["rotationScore"] >= 55 and (theme["volume"]["averageRelativeVolume"] or 0) >= 1.1
        ][:3]
        fading = [
            self._summary_item(theme)
            for theme in reversed(themes)
            if theme["stage"] in {"cooling_watch", "weak_or_no_signal"}
        ][:3]
        watchlist_signals = []
        for theme in themes[:3]:
            candidates = theme.get("alertCandidates") or []
            if candidates:
                watchlist_signals.extend(candidates[:2])
        return {
            "strongestThemes": strongest,
            "acceleratingThemes": accelerating,
            "fadingThemes": fading,
            "watchlistSignals": watchlist_signals[:5],
            "watchlistSortingExplanation": (
                "关注候选按主题轮动强度、置信度、跨时窗持续证据和成员相对强弱排序；"
                "仅作为观察信号，非买卖建议。"
            ),
            "safeWording": [
                "资金轮动迹象",
                "成交额扩张",
                "相对强势扩散",
                "板块同步性增强",
                "非买卖建议",
            ],
        }

    @staticmethod
    def _summary_item(theme: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "id": theme["id"],
            "name": theme["name"],
            "rotationScore": theme["rotationScore"],
            "confidence": theme["confidence"],
            "stage": theme["stage"],
            "freshness": theme["freshness"],
            "isFallback": theme["isFallback"],
            "riskLabels": list(theme["riskLabels"]),
        }

    def _benchmark_proxies(
        self,
        theme: ThemeBasket,
        benchmarks: Mapping[str, Dict[str, Any]],
        observed: Sequence[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        average_change = self._avg(
            [float(item["changePercent"]) for item in observed if item.get("changePercent") is not None],
            default=0.0,
        ) if observed else None
        proxies: Dict[str, Any] = {}
        for symbol in (*MARKET_BENCHMARK_SYMBOLS, theme.sectorBenchmark):
            benchmark = benchmarks.get(symbol, {})
            change = benchmark.get("changePercent")
            proxy_status = self._proxy_status(symbol, benchmark)
            proxies[symbol] = {
                "symbol": symbol,
                "role": "sector_proxy" if symbol == theme.sectorBenchmark else "market_proxy",
                "changePercent": change,
                "relativeStrength": round(average_change - float(change), 3) if average_change is not None and change is not None else None,
                "timeWindows": benchmark.get("timeWindows") or self._empty_time_windows(),
                "freshness": benchmark.get("freshness", "fallback"),
                "isFallback": bool(benchmark.get("isFallback", True)),
                "isStale": bool(benchmark.get("isStale")),
                "sourceLabel": benchmark.get("sourceLabel"),
                "asOf": benchmark.get("asOf"),
                "quality": proxy_status,
            }
        return proxies

    def _proxy_quality(
        self,
        theme: ThemeBasket,
        benchmarks: Mapping[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        proxy_symbols = list(dict.fromkeys((*MARKET_BENCHMARK_SYMBOLS, theme.sectorBenchmark)))
        statuses = {
            symbol: self._proxy_status(symbol, benchmarks.get(symbol, {}))
            for symbol in proxy_symbols
        }
        available_count = sum(1 for status in statuses.values() if status["available"])
        stale_count = sum(1 for status in statuses.values() if status["isStale"])
        total_count = len(proxy_symbols)
        coverage = self._percent(available_count, total_count)
        missing_reasons = {
            symbol: status["missingReason"]
            for symbol, status in statuses.items()
            if status["missingReason"]
        }
        if coverage >= 100 and stale_count == 0:
            label = "ETF 代理完整"
            freshness = self._freshest_proxy_label([status["freshness"] for status in statuses.values()])
        elif coverage >= 75:
            label = "ETF 代理部分缺口"
            freshness = "stale" if stale_count else "delayed"
        elif coverage > 0:
            label = "ETF 代理覆盖不足"
            freshness = "stale" if stale_count else "fallback"
        else:
            label = "ETF 代理待补齐"
            freshness = "fallback"
        return {
            "label": label,
            "coveragePercent": round(coverage, 1),
            "availableProxyCount": available_count,
            "totalProxyCount": total_count,
            "requiredProxies": proxy_symbols,
            "freshness": freshness,
            "hasMissingRequiredProxy": available_count < total_count,
            "hasStaleProxy": stale_count > 0,
            "missingReasons": missing_reasons,
            "explanation": (
                f"{label}：ETF 代理覆盖 {available_count}/{total_count}，"
                f"缺口 {', '.join(missing_reasons) if missing_reasons else '无'}。"
            ),
        }

    def _proxy_status(self, symbol: str, benchmark: Mapping[str, Any]) -> Dict[str, Any]:
        change = benchmark.get("changePercent")
        is_fallback = bool(benchmark.get("isFallback", True))
        is_stale = bool(benchmark.get("isStale"))
        freshness = str(benchmark.get("freshness") or "fallback")
        time_windows = benchmark.get("timeWindows")
        has_window = False
        if isinstance(time_windows, Mapping):
            has_window = any(bool(slot.get("available")) for slot in time_windows.values() if isinstance(slot, Mapping))
        available = change is not None and not is_fallback and not is_stale
        missing_reason = None
        if change is None or is_fallback:
            missing_reason = "proxy_quote_missing"
        elif is_stale:
            missing_reason = "proxy_stale"
        elif not has_window:
            missing_reason = "proxy_windows_missing"
        return {
            "symbol": symbol,
            "available": available,
            "freshness": "fallback" if is_fallback else "stale" if is_stale else freshness,
            "isFallback": is_fallback,
            "isStale": is_stale,
            "hasRequiredWindows": has_window,
            "missingReason": missing_reason,
            "qualityLabel": "可用代理" if available and not missing_reason else "代理待补齐" if missing_reason == "proxy_quote_missing" else "代理需复核",
            "coverageContribution": 1 if available else 0,
        }

    @staticmethod
    def _freshest_proxy_label(freshness_values: Sequence[str]) -> str:
        for candidate in ("live", "mock", "delayed", "cached", "stale", "fallback"):
            if candidate in freshness_values:
                return candidate
        return "fallback"

    def _alert_candidates(
        self,
        *,
        theme: ThemeBasket,
        leaders: Sequence[Mapping[str, Any]],
        stage: str,
        confidence: float,
        persistence_evidence: Mapping[str, Any],
        risk_labels: Sequence[str],
        source_state: Mapping[str, Any],
    ) -> List[Dict[str, Any]]:
        if source_state["fallbackUsed"] or source_state["isStale"] or confidence < 0.45:
            return []
        if stage not in {"early_watch", "confirmed_rotation", "extended_watch", "cooling_watch"}:
            return []
        candidates: List[Dict[str, Any]] = []
        for leader in leaders[:3]:
            signal_label = self._alert_signal_label(stage)
            reasons = [
                f"{theme.name}：{signal_label}",
                str(persistence_evidence.get("explanation") or "跨时窗证据待补齐。"),
            ]
            if leader.get("relativeStrengthVsBenchmark") is not None:
                reasons.append(f"{leader.get('symbol')} 相对 {theme.benchmark} {float(leader['relativeStrengthVsBenchmark']):+.2f}%")
            if leader.get("volumeRatio") is not None:
                reasons.append(f"量比 {float(leader['volumeRatio']):.2f}x")
            sort_explanation = (
                "按主题轮动强度、置信度、跨时窗持续证据、成员相对强弱和量能扩张排序；"
                "仅用于观察信号排队，非买卖建议。"
            )
            candidates.append({
                "themeId": theme.id,
                "themeName": theme.name,
                "symbol": leader.get("symbol"),
                "name": leader.get("name") or leader.get("symbol"),
                "label": "关注候选",
                "signal": stage,
                "signalLabel": signal_label,
                "confidence": confidence,
                "persistenceScore": persistence_evidence.get("score"),
                "persistenceLabel": persistence_evidence.get("label"),
                "riskLabels": list(risk_labels),
                "reasons": reasons,
                "sortKey": {
                    "confidence": confidence,
                    "persistenceScore": persistence_evidence.get("score"),
                    "relativeStrengthVsBenchmark": leader.get("relativeStrengthVsBenchmark"),
                    "volumeRatio": leader.get("volumeRatio"),
                },
                "sortExplanation": sort_explanation,
                "readOnly": True,
                "deliveryEnabled": False,
                "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
            })
        return candidates

    @staticmethod
    def _alert_signal_label(stage: str) -> str:
        labels = {
            "early_watch": "早期观察",
            "confirmed_rotation": "确认轮动",
            "extended_watch": "延展观察",
            "cooling_watch": "降温观察",
        }
        return labels.get(stage, "观察信号")

    def _theme_detail(
        self,
        *,
        theme: ThemeBasket,
        observations: Sequence[Mapping[str, Any]],
        leaders: Sequence[Mapping[str, Any]],
        generated_at: str,
    ) -> Dict[str, Any]:
        leader_symbols = {str(item.get("symbol")) for item in leaders[:3]}
        sorted_leaders = [
            self._watchlist_member(item, "leader" if item.get("symbol") in leader_symbols else "participant")
            for item in sorted(
                observations,
                key=lambda item: float(item.get("relativeStrengthVsBenchmark") or item.get("changePercent") or -999),
                reverse=True,
            )
            if item.get("observed") and item.get("symbol") in leader_symbols
        ]
        laggards = sorted(
            [item for item in observations if item.get("observed") and item.get("changePercent") is not None],
            key=lambda item: float(item.get("relativeStrengthVsBenchmark") or item.get("changePercent") or 0),
        )[:3]
        return {
            "watchlistLabel": "观察清单证据",
            "watchlistSafe": True,
            "safeActionLabel": "仅观察，不构成买卖建议",
            "leaderSectionLabel": "领先成员",
            "laggardSectionLabel": "落后/待验证成员",
            "leaderExplanation": "领先成员按相对强弱和量能扩张排序，仅代表观察信号强弱。",
            "laggardExplanation": "落后/待验证成员用于观察扩散不足或分歧，不是买卖建议。",
            "leadershipMembers": sorted_leaders,
            "laggardMembers": [
                self._watchlist_member(item, "laggard")
                for item in laggards
            ],
            "memberEvidence": [
                self._watchlist_member(item, "missing" if not item.get("observed") else str(item.get("leadershipLabel") or "participant"))
                for item in observations
            ],
            "freshnessLabel": self._freshness_label(
                "fallback" if not any(item.get("observed") for item in observations) else str(observations[0].get("freshness") or "delayed"),
                all(bool(item.get("isFallback")) for item in observations),
                any(bool(item.get("isStale")) for item in observations),
            ),
            "asOf": max([str(item.get("asOf")) for item in observations if item.get("asOf")] or [generated_at]),
            "disclosure": NO_ADVICE_DISCLOSURE,
            "mappedConcepts": list(theme.mappedConcepts),
            "representativeLabels": list(theme.members),
            "dataStateLabel": "待行情确认" if not any(item.get("observed") for item in observations) else "行情证据已接入",
            "nextStep": "继续观察本地行情覆盖、广度和跨时窗延续。",
            "notes": [
                f"{theme.name} 使用 {theme.benchmark}/{theme.sectorBenchmark} 作为相对强弱代理。",
                "成员标签仅描述领先、落后、缺失或新鲜度，不输出买入/卖出动作。",
            ],
        }

    def _watchlist_member(self, item: Mapping[str, Any], role: str) -> Dict[str, Any]:
        return {
            "symbol": item.get("symbol"),
            "name": item.get("name") or item.get("symbol"),
            "role": role,
            "roleLabel": self._watchlist_role_label(role),
            "changePercent": item.get("changePercent"),
            "relativeStrengthVsBenchmark": item.get("relativeStrengthVsBenchmark"),
            "volumeRatio": item.get("volumeRatio"),
            "freshness": item.get("freshness", "fallback"),
            "freshnessLabel": item.get("freshnessLabel") or self._freshness_label(
                str(item.get("freshness") or "fallback"),
                bool(item.get("isFallback")),
                bool(item.get("isStale")),
            ),
            "observed": bool(item.get("observed")),
            "notes": list(item.get("notes") or []),
        }

    @staticmethod
    def _watchlist_role_label(role: str) -> str:
        labels = {
            "leader": "领先成员",
            "laggard": "落后成员",
            "participant": "参与成员",
            "missing": "待补齐",
            "未观察": "待补齐",
            "领先成员": "领先成员",
            "落后成员": "落后成员",
            "参与成员": "参与成员",
        }
        return labels.get(role, "观察成员")

    @staticmethod
    def _member_role_label(
        change: Optional[float],
        relative_strength: Optional[float],
        volume_ratio: Optional[float],
    ) -> str:
        if change is None:
            return "待补齐"
        if relative_strength is not None and relative_strength >= 1.0 and (volume_ratio or 0) >= 1.1:
            return "领先成员"
        if relative_strength is not None and relative_strength <= -1.0:
            return "落后成员"
        return "参与成员"

    @staticmethod
    def _freshness_label(freshness: str, is_fallback: bool, is_stale: bool) -> str:
        if is_fallback or freshness == "fallback":
            return "备用/缺失"
        if is_stale or freshness == "stale":
            return "过期"
        if freshness == "live":
            return "实时"
        if freshness == "mock":
            return "模拟"
        if freshness == "cached":
            return "缓存"
        return "延迟"

    def _leaders(self, observed: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sortable = [
            item for item in observed
            if item.get("changePercent") is not None
        ]
        sortable.sort(key=lambda item: (item.get("relativeStrengthVsBenchmark") or item.get("changePercent") or 0), reverse=True)
        return [
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "changePercent": item.get("changePercent"),
                "relativeStrengthVsBenchmark": item.get("relativeStrengthVsBenchmark"),
                "volumeRatio": item.get("volumeRatio"),
                "roleLabel": item.get("leadershipLabel"),
                "freshnessLabel": item.get("freshnessLabel"),
                "freshness": item.get("freshness"),
                "isFallback": bool(item.get("isFallback")),
            }
            for item in sortable[:3]
        ]

    def _relative_vs_benchmarks(
        self,
        observed: Sequence[Mapping[str, Any]],
        benchmarks: Mapping[str, Dict[str, Any]],
    ) -> Dict[str, Optional[float]]:
        changes = [float(item["changePercent"]) for item in observed if item.get("changePercent") is not None]
        average_change = self._avg(changes) if changes else None
        result: Dict[str, Optional[float]] = {}
        for symbol in BENCHMARK_SYMBOLS:
            benchmark_change = benchmarks.get(symbol, {}).get("changePercent")
            if average_change is None or benchmark_change is None:
                result[symbol] = None
            else:
                result[symbol] = round(average_change - float(benchmark_change), 3)
        return result

    def _theme_benchmark_change(
        self,
        theme: ThemeBasket,
        benchmarks: Mapping[str, Dict[str, Any]],
    ) -> Optional[float]:
        primary = benchmarks.get(theme.benchmark, {}).get("changePercent")
        if primary is not None:
            return float(primary)
        values = [
            float(item["changePercent"])
            for item in benchmarks.values()
            if item.get("changePercent") is not None
        ]
        return self._avg(values) if values else None

    @staticmethod
    def _leadership_concentration(changes: Sequence[float]) -> float:
        positive = [max(0.0, value) for value in changes]
        total = sum(positive)
        if total <= 0:
            absolute = [abs(value) for value in changes]
            total_abs = sum(absolute)
            return max(absolute) / total_abs if total_abs > 0 else 0.0
        return max(positive) / total

    @staticmethod
    def _persistence_score(trend: Sequence[float], change: Optional[float]) -> Optional[float]:
        if len(trend) >= 3:
            if trend[-1] > trend[0] and trend[-1] >= trend[-2]:
                return 1.0
            if trend[-1] < trend[0] and trend[-1] <= trend[-2]:
                return 0.0
            return 0.5
        if change is None:
            return None
        return 0.7 if change > 0 else 0.3 if change < 0 else 0.5

    @staticmethod
    def _volume_label(volume_ratio: Optional[float]) -> str:
        if volume_ratio is None:
            return "成交额扩张证据不足"
        if volume_ratio >= 1.5:
            return "成交额扩张明显"
        if volume_ratio >= 1.1:
            return "成交额温和扩张"
        if volume_ratio >= 0.9:
            return "成交额接近常态"
        return "成交额未扩张"

    @staticmethod
    def _synchronization_label(value: float) -> str:
        if value >= 75:
            return "板块同步性增强"
        if value >= 60:
            return "同步性温和改善"
        return "同步性证据不足"

    @staticmethod
    def _percent(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return numerator / denominator * 100

    @staticmethod
    def _avg(values: Sequence[float], default: float = 0.0) -> float:
        finite = [float(value) for value in values if math.isfinite(float(value))]
        return mean(finite) if finite else default

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        return number

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, value))

    def _now_iso(self) -> str:
        now = self.now_provider()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.isoformat(timespec="seconds")
