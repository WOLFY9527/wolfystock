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


NO_ADVICE_DISCLOSURE = "仅用于观察资金轮动迹象，非买卖建议。"
RADAR_ENDPOINT = "/api/v1/market/rotation-radar"
BENCHMARK_SYMBOLS = ("QQQ", "SPY", "IWM")
STAGE_LABELS = {
    "early_rotation",
    "confirmed_rotation",
    "crowded_or_extended",
    "cooling",
    "weak_or_no_signal",
}


@dataclass(frozen=True)
class ThemeBasket:
    id: str
    name: str
    englishName: str
    benchmark: str
    members: Sequence[str]
    focus: str


THEME_BASKETS: Sequence[ThemeBasket] = (
    ThemeBasket(
        id="ai_applications",
        name="AI 应用",
        englishName="AI Applications",
        benchmark="QQQ",
        members=("APP", "PLTR", "CRM", "SNOW", "ADBE", "NOW", "DUOL", "MDB"),
        focus="应用层软件、数据工作流与企业 AI 落地",
    ),
    ThemeBasket(
        id="ai_infrastructure",
        name="AI 基建",
        englishName="AI Infrastructure",
        benchmark="QQQ",
        members=("NVDA", "AVGO", "AMD", "ANET", "SMCI", "DELL", "VRT", "ARM"),
        focus="GPU、网络、服务器与 AI 数据中心硬件",
    ),
    ThemeBasket(
        id="semiconductors",
        name="半导体",
        englishName="Semiconductors",
        benchmark="QQQ",
        members=("NVDA", "AMD", "AVGO", "TSM", "ASML", "MRVL", "MU", "LRCX"),
        focus="芯片、设备、存储与先进制程链条",
    ),
    ThemeBasket(
        id="cybersecurity",
        name="网络安全",
        englishName="Cybersecurity",
        benchmark="QQQ",
        members=("CRWD", "PANW", "ZS", "NET", "FTNT", "S", "OKTA", "TENB"),
        focus="云安全、零信任、终端防护与边缘安全",
    ),
    ThemeBasket(
        id="cloud_software",
        name="云软件",
        englishName="Cloud Software",
        benchmark="QQQ",
        members=("MSFT", "SNOW", "CRM", "NOW", "DDOG", "MDB", "TEAM", "WDAY"),
        focus="云基础软件、SaaS 工作流与数据平台",
    ),
    ThemeBasket(
        id="data_center_power",
        name="数据中心电力",
        englishName="Data Center Power",
        benchmark="SPY",
        members=("VRT", "ETN", "PWR", "GEV", "CEG", "NRG", "SMR", "AEP"),
        focus="电力设备、并网、发电与能源基础设施",
    ),
    ThemeBasket(
        id="liquid_cooling",
        name="液冷",
        englishName="Liquid Cooling",
        benchmark="QQQ",
        members=("VRT", "MOD", "SMCI", "DELL", "HPE", "ANET", "NVDA", "ETN"),
        focus="高密度机柜、液冷方案与数据中心热管理",
    ),
    ThemeBasket(
        id="robotics",
        name="机器人",
        englishName="Robotics",
        benchmark="IWM",
        members=("ISRG", "TER", "SYM", "PATH", "ROK", "ABBNY", "IRBT", "ZBRA"),
        focus="工业自动化、手术机器人、仓储机器人与机器视觉",
    ),
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

    def get_rotation_radar(self) -> Dict[str, Any]:
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
                "schemaVersion": "market_rotation_radar_mvp_v1",
                "noExternalCalls": True,
                "basketSource": "manual_static_baskets",
                "themeCount": len(THEME_BASKETS),
                "liveThemeCount": live_theme_count,
                "fallbackThemeCount": fallback_theme_count,
                "staleThemeCount": stale_theme_count,
                "scoreRange": "0-100",
                "confidenceRange": "0-1",
                "newslessRotationMeaning": "未配置新闻催化证据时，价格/量能/广度/同步性同时满足阈值的保守观察标记，不代表因果确认。",
            },
        }

    def _load_quotes(self) -> tuple[Dict[str, Dict[str, Any]], Optional[str]]:
        if self.quote_provider is None:
            return {}, "未配置实时 quote provider，返回降级主题篮子。"
        symbols = sorted({symbol for theme in THEME_BASKETS for symbol in theme.members} | set(BENCHMARK_SYMBOLS))
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
        source_state = self._source_state(observations, benchmarks, theme.benchmark)
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
        return {
            "id": theme.id,
            "name": theme.name,
            "englishName": theme.englishName,
            "focus": theme.focus,
            "benchmark": theme.benchmark,
            "membersConfigured": list(theme.members),
            "rotationScore": score,
            "confidence": confidence,
            "stage": stage,
            "riskLabels": risk_labels,
            "newslessRotation": newsless_rotation,
            "newslessRotationEvidence": (
                "无明显新闻的同步异动：未配置新闻催化证据，当前仅由价格、量能、广度和同步性共同触发。"
                if newsless_rotation else None
            ),
            "relativeStrength": {
                "benchmark": theme.benchmark,
                "benchmarkChangePercent": round(benchmark_change, 3) if benchmark_change is not None else None,
                "averageThemeChangePercent": round(average_change, 3),
                "averageRelativeStrengthPercent": round(average_relative_strength, 3),
                "vsBenchmarks": self._relative_vs_benchmarks(observed, benchmarks),
            },
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
                "label": self._synchronization_label(dominant_direction),
            },
            "leadership": {
                "leadershipConcentrationPercent": round(concentration * 100, 1),
                "broadParticipationPercent": round((1 - concentration) * 100, 1),
                "topMembers": leaders,
            },
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
        return {
            "id": theme.id,
            "name": theme.name,
            "englishName": theme.englishName,
            "focus": theme.focus,
            "benchmark": theme.benchmark,
            "membersConfigured": list(theme.members),
            "rotationScore": int(preset["score"]),
            "confidence": 0.12,
            "stage": "weak_or_no_signal",
            "riskLabels": ["fallback_data", "thin_breadth"],
            "newslessRotation": False,
            "newslessRotationEvidence": None,
            "relativeStrength": {
                "benchmark": theme.benchmark,
                "benchmarkChangePercent": None,
                "averageThemeChangePercent": None,
                "averageRelativeStrengthPercent": None,
                "vsBenchmarks": {symbol: None for symbol in BENCHMARK_SYMBOLS},
            },
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
                "label": "同步性证据不足",
            },
            "leadership": {
                "leadershipConcentrationPercent": 0,
                "broadParticipationPercent": 0,
                "topMembers": leaders,
            },
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
                "priceAboveVwap": None,
                "persistenceScore": None,
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
            "priceAboveVwap": bool(price >= vwap) if price is not None and vwap is not None else None,
            "persistenceScore": self._persistence_score(trend, change),
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
        return {
            "symbol": symbol,
            "name": str(raw_quote.get("name") or raw_quote.get("label") or symbol),
            "price": price,
            "changePercent": change,
            "volumeRatio": volume_ratio,
            "vwap": vwap,
            "trend": trend_values,
            "freshness": "fallback" if is_fallback else "stale" if is_stale else freshness,
            "isFallback": is_fallback,
            "isStale": is_stale,
            "source": source,
            "sourceLabel": str(raw_quote.get("sourceLabel") or raw_quote.get("source_label") or "主题篮子行情"),
            "asOf": str(raw_quote.get("asOf") or raw_quote.get("as_of") or raw_quote.get("updatedAt") or self._now_iso()),
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
        if source_state["isStale"]:
            labels.append("stale_data")
        if source_state["fallbackUsed"]:
            labels.append("fallback_data")
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
                return "crowded_or_extended"
            return "confirmed_rotation"
        if score >= 60 and confidence >= 0.45:
            if "single_name_driven" in risk_labels and percent_up < 65:
                return "crowded_or_extended"
            return "early_rotation"
        if average_relative_volume < 0.9 or percent_up < 50:
            return "cooling"
        return "weak_or_no_signal"

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
            if theme["stage"] in {"cooling", "weak_or_no_signal"}
        ][:3]
        return {
            "strongestThemes": strongest,
            "acceleratingThemes": accelerating,
            "fadingThemes": fading,
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
