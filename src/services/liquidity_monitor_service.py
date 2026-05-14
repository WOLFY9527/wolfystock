# -*- coding: utf-8 -*-
"""Cache-only advisory liquidity monitor service."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from src.services.market_cache import MarketCache, market_cache
from src.services.market_data_source_registry import project_source_provenance
from src.services.market_overview_binance_transport import fetch_binance_funding_row
from src.services.market_overview_yfinance_transport import fetch_yfinance_quote_history_frame
from src.storage import DatabaseManager


CN_TZ = timezone(timedelta(hours=8))
ADVISORY_DISCLOSURE = "仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。"
FRESHNESS_ORDER = {"live": 0, "cached": 1, "delayed": 2, "stale": 3, "fallback": 4, "mock": 5, "error": 6, "unavailable": 7}
RELIABLE_FRESHNESS = {"live", "cached", "delayed"}
POSSIBLE_WEIGHT = 43


@dataclass(frozen=True)
class PanelState:
    key: str
    payload: Dict[str, Any]
    source: str
    freshness: str
    as_of: Optional[str]
    updated_at: Optional[str]
    is_fallback: bool
    is_stale: bool


class LiquidityMonitorService:
    """Build a removable advisory liquidity monitor from existing cached market surfaces."""

    def __init__(
        self,
        *,
        cache: MarketCache = market_cache,
        db: Optional[DatabaseManager] = None,
    ) -> None:
        self.cache = cache
        self.db = db or DatabaseManager.get_instance()
        self._external_provider_calls_used = False

    def get_liquidity_monitor(self) -> Dict[str, Any]:
        self._external_provider_calls_used = False
        panels = {
            key: self._read_panel(key)
            for key in ("crypto", "volatility", "rates", "macro", "fx_commodities", "funds_flow", "us_breadth", "cn_indices", "cn_breadth", "cn_flows", "futures")
        }
        indicators = [
            self._crypto_spot_indicator(panels["crypto"]),
            self._crypto_funding_indicator(panels["crypto"]),
            self._vix_indicator(panels["volatility"], panels["macro"]),
            self._usd_pressure_indicator(panels["fx_commodities"], panels["rates"]),
            self._us_rates_indicator(panels["rates"], panels["macro"]),
            self._us_etf_flow_indicator(panels["funds_flow"]),
            self._us_breadth_indicator(panels["us_breadth"]),
            self._cn_hk_index_indicator(panels["cn_indices"]),
            self._cn_hk_flows_indicator(panels["cn_flows"], panels["cn_breadth"]),
            self._cn_money_rates_indicator(panels["rates"]),
            self._futures_indicator(panels["futures"]),
        ]

        included = [item for item in indicators if item["includedInScore"]]
        included_weight = sum(int(item["scoreWeight"]) for item in included)
        confidence = min(0.95, round(included_weight / POSSIBLE_WEIGHT, 2)) if POSSIBLE_WEIGHT else 0.0
        score_value = 50 + sum(int(item["scoreContribution"]) for item in included)
        reliable_indicator_count = len(included)

        if reliable_indicator_count < 3 or confidence < 0.25:
            score_value = 50
            regime = "unavailable"
        else:
            regime = self._regime(score_value)

        available_freshness = [str(item["freshness"]) for item in indicators if item["status"] != "unavailable"]
        available_as_of = [str(item["updatedAt"] or "") for item in indicators if item["status"] != "unavailable" and item.get("updatedAt")]

        return {
            "endpoint": "/api/v1/market/liquidity-monitor",
            "generatedAt": self._now().isoformat(timespec="seconds"),
            "score": {
                "value": max(0, min(100, int(round(score_value)))),
                "regime": regime,
                "confidence": confidence,
                "includedIndicatorCount": reliable_indicator_count,
                "possibleIndicatorWeight": POSSIBLE_WEIGHT,
                "includedIndicatorWeight": included_weight,
            },
            "freshness": {
                "status": self._weakest_freshness(available_freshness) if available_freshness else "unavailable",
                "weakestIndicatorFreshness": self._weakest_freshness(available_freshness) if available_freshness else "unavailable",
                "latestAsOf": max(available_as_of) if available_as_of else None,
            },
            "indicators": indicators,
            "advisoryDisclosure": ADVISORY_DISCLOSURE,
            "sourceMetadata": {
                "externalProviderCalls": self._external_provider_calls_used,
                "providerRuntimeChanged": False,
                "marketCacheMutation": False,
            },
        }

    def _read_panel(self, key: str) -> PanelState:
        entry = self.cache.get(key)
        expired = bool(entry and entry.expires_at <= self._now())
        if entry and isinstance(entry.data, dict):
            payload = copy.deepcopy(entry.data)
        else:
            snapshot = self.db.get_market_overview_snapshot(f"market_overview:{key}")
            payload = copy.deepcopy(snapshot.get("payload") or {}) if isinstance(snapshot, dict) else {}
        payload = payload if isinstance(payload, dict) else {}
        source = str(payload.get("source") or "unavailable")
        freshness = str(payload.get("freshness") or ("fallback" if payload.get("isFallback") or payload.get("fallbackUsed") else "unavailable"))
        is_fallback = bool(payload.get("isFallback") or payload.get("fallbackUsed") or source in {"fallback", "mock", "unavailable"})
        if source == "mock":
            freshness = "mock"
        elif freshness == "mock":
            source = "mock"
        if expired:
            freshness = "stale"
        is_stale = freshness == "stale"
        updated_at = self._text(payload.get("updatedAt") or payload.get("last_update") or payload.get("last_refresh_at"))
        as_of = self._text(payload.get("asOf") or payload.get("last_update") or payload.get("last_refresh_at") or updated_at)
        return PanelState(
            key=key,
            payload=payload,
            source=source,
            freshness=freshness,
            as_of=as_of,
            updated_at=updated_at,
            is_fallback=is_fallback,
            is_stale=is_stale,
        )

    def _crypto_spot_indicator(self, panel: PanelState) -> Dict[str, Any]:
        breadth = self._extract_crypto_breadth(panel)
        if breadth is None:
            return self._indicator("crypto_spot_momentum", "Crypto 现货动量", panel, "unavailable", 0, 6, False, "BTC / ETH / BNB 缓存不足")
        signal = self._direction_from_counts(int(breadth["advancers"]), int(breadth["decliners"]))
        status = "live" if int(breadth["count"]) == 3 and breadth["freshness"] in {"live", "cached"} else "partial"
        return self._indicator(
            "crypto_spot_momentum",
            "Crypto 现货动量",
            panel,
            status,
            6 if signal > 0 else -6 if signal < 0 else 0,
            6,
            True,
            f"{int(breadth['advancers'])}/{int(breadth['count'])} 上涨 | 均值 {float(breadth['avg_change']):+.2f}%",
            freshness=str(breadth["freshness"]),
        )

    def _crypto_funding_indicator(self, panel: PanelState) -> Dict[str, Any]:
        items = [item for item in self._reliable_items(panel, None) if str(item.get("symbol") or "").endswith("_FUNDING") and self._numeric(item.get("value")) is not None]
        funding_panel = panel
        if not items:
            funding_panel = self._fetch_live_crypto_funding_panel(panel) or panel
            items = [
                item
                for item in self._reliable_items(funding_panel, None)
                if str(item.get("symbol") or "").endswith("_FUNDING") and self._numeric(item.get("value")) is not None
            ]
        if not items:
            message = "Binance Futures funding 暂不可用"
            if not self._has_live_crypto_context(panel):
                message = "缺少 BTC/ETH 现货上下文，未触发实时 funding 查询"
            return self._indicator(
                "crypto_funding",
                "Crypto Funding",
                panel,
                "unavailable",
                0,
                0,
                False,
                message,
                freshness="unavailable" if panel.freshness in RELIABLE_FRESHNESS else panel.freshness,
            )
        avg_value = sum(float(self._numeric(item.get("value")) or 0.0) for item in items) / len(items)
        freshness = self._weakest_freshness([self._item_freshness(item, funding_panel) for item in items])
        values = [
            f"{str(item.get('symbol') or '').replace('_FUNDING', '')} {float(self._numeric(item.get('value')) or 0.0):+.4f}%"
            for item in items
        ]
        source_meta = project_source_provenance(
            source=items[0].get("source") or funding_panel.source,
            source_type=items[0].get("sourceType"),
            source_label=items[0].get("sourceLabel"),
            freshness=freshness,
            is_fallback=bool(items[0].get("isFallback") or items[0].get("fallbackUsed") or funding_panel.is_fallback),
            is_stale=bool(items[0].get("isStale") or funding_panel.is_stale),
        )
        source_label = source_meta["sourceLabel"]
        source_type = source_meta["sourceType"]
        status = "live" if len(items) >= 2 and freshness == "live" else "partial"
        return self._indicator(
            "crypto_funding",
            "Crypto Funding",
            funding_panel,
            status,
            0,
            0,
            False,
            f"{' | '.join(values)} | 均值 {avg_value:+.4f}% | 来源 {source_label} | 类型 {source_type}",
            freshness=freshness,
        )

    def _vix_indicator(self, panel: PanelState, macro_panel: PanelState) -> Dict[str, Any]:
        selected = self._preferred_symbol_item((panel, macro_panel), {"VIX", "VIXCLS"})
        if selected is not None:
            panel, item = selected
        else:
            item = None
        if item is None:
            proxy_panel = self._fetch_macro_proxy_panel(
                "volatility_proxy",
                [{"symbol": "VIX", "label": "VIX", "ticker": "^VIX", "unit": "pts"}],
            )
            if proxy_panel is not None:
                panel = proxy_panel
                item = self._first_reliable_item(panel, {"VIX"})
        if item is None:
            return self._indicator(
                "vix_pressure",
                "VIX / 波动率压力",
                panel,
                "unavailable",
                0,
                8,
                False,
                self._summary_with_metadata(
                    "未读取到可靠 VIX",
                    source="yfinance_proxy",
                    source_label="Yahoo Finance",
                    source_type="proxy_public",
                    reason=self._panel_unavailable_reason(panel, "VIX 代理不可用"),
                ),
            )
        change = self._change_value(item)
        value = self._numeric(item.get("value") or item.get("price"))
        contribution = 0
        if change is not None and change < 0:
            contribution = 8
        elif change is not None and change > 0:
            contribution = -8
        elif value is not None and value <= 16:
            contribution = 8
        elif value is not None and value >= 25:
            contribution = -8
        freshness = self._item_freshness(item, panel)
        source_type = self._item_source_type(item, panel)
        status = (
            "live"
            if freshness in {"live", "cached"}
            and str(item.get("source") or panel.source) != "yfinance_proxy"
            and source_type != "official_public"
            else "partial"
        )
        return self._indicator(
            "vix_pressure",
            "VIX / 波动率压力",
            panel,
            status,
            contribution,
            8,
            True,
            self._summary_with_metadata(self._signed_percent_text(change), item=item, freshness=freshness),
            freshness=freshness,
        )

    def _usd_pressure_indicator(self, fx_panel: PanelState, rates_panel: PanelState) -> Dict[str, Any]:
        components = self._extract_usd_pressure_components(fx_panel, rates_panel)
        if not components:
            proxy_panel = self._fetch_macro_proxy_panel(
                "fx_commodities_proxy",
                [{"symbol": "DXY", "label": "DXY", "ticker": "DX-Y.NYB", "unit": "idx"}],
            )
            if proxy_panel is not None:
                fx_panel = proxy_panel
                components = self._extract_usd_pressure_components(fx_panel, rates_panel)
        if not components:
            return self._indicator(
                "usd_pressure",
                "DXY / 美元压力",
                fx_panel,
                "unavailable",
                0,
                6,
                False,
                self._summary_with_metadata(
                    "仅在可靠 FX / 宏观缓存存在时启用",
                    source="yfinance_proxy",
                    source_label="Yahoo Finance",
                    source_type="proxy_public",
                    reason=self._panel_unavailable_reason(fx_panel, "DXY 代理不可用"),
                ),
            )
        positive = sum(1 for component in components if float(component["signal"]) > 0)
        negative = sum(1 for component in components if float(component["signal"]) < 0)
        direction = self._direction_from_counts(positive, negative)
        base_panel = fx_panel if any(component["panel"] is fx_panel for component in components) else rates_panel
        summary = " | ".join(f"{component['label']} {self._signed_percent_text(float(component['change']))}" for component in components)
        freshness = self._weakest_freshness([str(component["freshness"]) for component in components])
        status = "live" if len(components) >= 2 and freshness in {"live", "cached"} else "partial"
        return self._indicator(
            "usd_pressure",
            "DXY / 美元压力",
            base_panel,
            status,
            -6 if direction > 0 else 6 if direction < 0 else 0,
            6,
            True,
            self._summary_with_metadata(summary, item=components[0], freshness=freshness),
            freshness=freshness,
        )

    def _us_rates_indicator(self, panel: PanelState, macro_panel: PanelState) -> Dict[str, Any]:
        components = self._extract_us_rates_components((panel, macro_panel))
        credit_observation = self._extract_credit_stress_observation(macro_panel)
        if not components:
            proxy_panel = self._fetch_macro_proxy_panel(
                "rates_proxy",
                [
                    {"symbol": "US10Y", "label": "10Y yield", "ticker": "^TNX", "unit": "%", "value_scale": 10.0, "market": "US"},
                    {"symbol": "US30Y", "label": "30Y yield", "ticker": "^TYX", "unit": "%", "value_scale": 10.0, "market": "US"},
                ],
            )
            if proxy_panel is not None:
                panel = proxy_panel
                components = self._extract_us_rates_components((panel,))
        if not components:
            return self._indicator(
                "us_rates_pressure",
                "US Rates / 利率压力",
                panel,
                "unavailable",
                0,
                6,
                False,
                self._summary_with_metadata(
                    "仅在可靠利率缓存存在时启用",
                    source="yfinance_proxy",
                    source_label="Yahoo Finance",
                    source_type="proxy_public",
                    reason=self._panel_unavailable_reason(panel, "US rates 代理不可用"),
                ),
            )
        positive = sum(1 for component in components if component["kind"] == "yield" and float(component["signal"]) > 0)
        negative = sum(1 for component in components if component["kind"] == "yield" and float(component["signal"]) < 0)
        direction = self._direction_from_counts(positive, negative)
        summary = " | ".join(
            f"{component['symbol']} {self._signed_percent_text(float(component['change']))}"
            for component in components
            if component["kind"] == "yield"
        )
        curve_parts = [
            f"{component['symbol']} {self._signed_number_text(float(component['value']))}{component['unit']}"
            for component in components
            if component["kind"] == "curve"
        ]
        observation_parts = [
            f"{component['symbol']} {self._signed_number_text(float(component['value']))}{component['unit']}"
            for component in components
            if component["kind"] == "observation"
        ]
        if curve_parts:
            summary = f"{summary} | {' | '.join(curve_parts)}" if summary else " | ".join(curve_parts)
        if observation_parts:
            summary = f"{summary} | {' | '.join(observation_parts)}" if summary else " | ".join(observation_parts)
        if credit_observation is not None:
            credit_summary = f"CREDIT {self._signed_number_text(float(credit_observation['value']))}{credit_observation['unit']}"
            summary = f"{summary} | {credit_summary}" if summary else credit_summary
        freshness = self._weakest_freshness([str(component["freshness"]) for component in components])
        yield_components = [component for component in components if component["kind"] == "yield"]
        status = (
            "live"
            if len(yield_components) >= 2
            and freshness in {"live", "cached"}
            and all(str(component.get("source") or "") != "yfinance_proxy" for component in yield_components)
            and all(str(component.get("sourceType") or "") != "official_public" for component in yield_components)
            else "partial"
        )
        return self._indicator(
            "us_rates_pressure",
            "US Rates / 利率压力",
            panel,
            status,
            6 if direction > 0 else -6 if direction < 0 else 0,
            6,
            True,
            self._summary_with_metadata(summary, item=components[0], freshness=freshness),
            freshness=freshness,
        )

    def _us_etf_flow_indicator(self, panel: PanelState) -> Dict[str, Any]:
        item = self._first_reliable_item(panel, {"ETF"})
        if item is None:
            return self._indicator("us_etf_flow_proxy", "US ETF 资金代理", panel, "unavailable", 0, 5, False, "仅在可靠 funds-flow 缓存存在时启用")
        value = self._numeric(item.get("value"))
        contribution = 5 if (value or 0) > 0 else -5 if (value or 0) < 0 else 0
        return self._indicator("us_etf_flow_proxy", "US ETF 资金代理", panel, "partial", contribution, 5, True, self._signed_number_text(value), freshness=self._item_freshness(item, panel))

    def _us_breadth_indicator(self, panel: PanelState) -> Dict[str, Any]:
        breadth = self._extract_us_breadth_components(panel)
        if breadth is None:
            return self._indicator("us_breadth_proxy", "US Broadth / 广度代理", panel, "unavailable", 0, 6, False, "仅在可靠 breadth 缓存存在时启用")
        direction = self._direction_from_counts(int(breadth["positive_votes"]), int(breadth["negative_votes"]))
        summary_parts = [f"{int(breadth['up_value'])}/{int(breadth['down_value'])}"]
        summary_parts.extend(
            f"{proxy['label']} {self._signed_percent_text(float(proxy['value']))}"
            for proxy in breadth["proxies"]
        )
        status = "live" if len(breadth["proxies"]) >= 2 and str(breadth["freshness"]) in {"live", "cached"} else "partial"
        return self._indicator(
            "us_breadth_proxy",
            "US 广度代理",
            panel,
            status,
            6 if direction > 0 else -6 if direction < 0 else 0,
            6,
            True,
            " | ".join(summary_parts),
            freshness=str(breadth["freshness"]),
        )

    def _cn_hk_index_indicator(self, panel: PanelState) -> Dict[str, Any]:
        items = [item for item in self._reliable_items(panel, None) if str(item.get("market") or "") in {"CN", "HK"} and self._change_value(item) is not None]
        if not items:
            return self._indicator("cn_hk_index_context", "CN/HK 指数环境", panel, "unavailable", 0, 0, False, "缺少可靠指数快照")
        avg_change = sum(float(self._change_value(item)) for item in items) / len(items)
        status = "live" if len(items) >= 4 and panel.source != "mixed" else "partial"
        freshness = self._weakest_freshness([self._item_freshness(item, panel) for item in items])
        return self._indicator("cn_hk_index_context", "CN/HK 指数环境", panel, status, 0, 0, False, f"均值 {avg_change:+.2f}%", freshness=freshness)

    def _cn_hk_flows_indicator(self, panel: PanelState, breadth_panel: PanelState) -> Dict[str, Any]:
        if panel.is_fallback or panel.freshness in {"fallback", "mock", "error", "unavailable"}:
            return self._indicator("cn_hk_flows", "CN/HK 资金流", panel, "unavailable", 0, 6, False, "Phase 1 仅在非 fallback 真实流量数据存在时启用")
        extracted = self._extract_cn_flow_components(panel, breadth_panel)
        if extracted is None:
            return self._indicator("cn_hk_flows", "CN/HK 资金流", panel, "unavailable", 0, 6, False, "缺少真实 northbound / ETF flow")
        direction = self._direction_from_counts(int(extracted["positive_votes"]), int(extracted["negative_votes"]))
        summary_parts = [
            f"{component['label']} {self._signed_number_text(float(component['value']))}"
            for component in extracted["flows"]
        ]
        if extracted["breadth_summary"]:
            summary_parts.append(str(extracted["breadth_summary"]))
        status = "live" if len(extracted["flows"]) >= 2 and str(extracted["freshness"]) in {"live", "cached"} else "partial"
        return self._indicator(
            "cn_hk_flows",
            "CN/HK 资金流",
            panel,
            status,
            6 if direction > 0 else -6 if direction < 0 else 0,
            6,
            True,
            " | ".join(summary_parts),
            freshness=str(extracted["freshness"]),
        )

    def _cn_money_rates_indicator(self, panel: PanelState) -> Dict[str, Any]:
        dr007 = self._first_reliable_item(panel, {"DR007"})
        shibor = self._first_reliable_item(panel, {"SHIBOR"})
        if dr007 is None and shibor is None:
            return self._indicator("cn_money_market_rates", "CN 货币市场利率", panel, "unavailable", 0, 0, False, "Phase 1 仅观察，不单独计分")
        available = [item for item in (dr007, shibor) if item is not None]
        avg_change = sum(float(self._change_value(item) or 0.0) for item in available) / len(available)
        freshness = self._weakest_freshness([self._item_freshness(item, panel) for item in available])
        return self._indicator("cn_money_market_rates", "CN 货币市场利率", panel, "partial", 0, 0, False, f"均值 {avg_change:+.2f}%", freshness=freshness)

    def _futures_indicator(self, panel: PanelState) -> Dict[str, Any]:
        if panel.is_fallback or panel.freshness in {"fallback", "mock", "error", "unavailable"}:
            return self._indicator("futures_premarket", "期货 / 盘前方向", panel, "unavailable", 0, 0, False, "Phase 1 fallback-only，不参与判断")
        items = self._reliable_items(panel, {"NQ", "ES", "YM", "RTY", "CN00Y", "HSI_F"})
        if not items:
            return self._indicator("futures_premarket", "期货 / 盘前方向", panel, "unavailable", 0, 0, False, "缺少可靠期货快照")
        avg_change = sum(float(self._change_value(item) or 0.0) for item in items) / len(items)
        freshness = self._weakest_freshness([self._item_freshness(item, panel) for item in items])
        return self._indicator("futures_premarket", "期货 / 盘前方向", panel, "partial", 0, 0, False, f"均值 {avg_change:+.2f}%", freshness=freshness)

    def _indicator(
        self,
        key: str,
        label: str,
        panel: PanelState,
        status: str,
        contribution: int,
        weight: int,
        included: bool,
        summary: str,
        *,
        freshness: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "key": key,
            "label": label,
            "status": status,
            "freshness": freshness or panel.freshness or "unavailable",
            "includedInScore": included,
            "scoreContribution": contribution if included else 0,
            "scoreWeight": weight,
            "summary": summary,
            "updatedAt": panel.as_of or panel.updated_at,
        }

    def _first_reliable_item(self, panel: PanelState, symbols: Optional[set[str]]) -> Optional[Dict[str, Any]]:
        items = self._reliable_items(panel, symbols)
        return items[0] if items else None

    def _preferred_symbol_item(
        self,
        panels: Iterable[PanelState],
        symbols: set[str],
    ) -> Optional[tuple[PanelState, Dict[str, Any]]]:
        candidates: List[tuple[tuple[int, int, int], PanelState, Dict[str, Any]]] = []
        for panel_index, panel in enumerate(panels):
            for item in self._reliable_items(panel, symbols):
                source_type = self._item_source_type(item, panel)
                source = str(item.get("source") or panel.source or "").lower()
                freshness = self._item_freshness(item, panel)
                candidates.append(
                    (
                        (
                            0 if source_type == "official_public" else 1,
                            FRESHNESS_ORDER.get(freshness, 99),
                            panel_index if source not in {"yahoo", "yfinance", "yfinance_proxy"} else panel_index + 1,
                        ),
                        panel,
                        item,
                    )
                )
        if not candidates:
            return None
        candidates.sort(key=lambda entry: entry[0])
        _, panel, item = candidates[0]
        return panel, item

    def _reliable_symbol_map(self, panel: PanelState, symbols: Optional[set[str]] = None) -> Dict[str, Dict[str, Any]]:
        return {
            str(item.get("symbol") or ""): item
            for item in self._reliable_items(panel, symbols)
            if str(item.get("symbol") or "")
        }

    def _extract_crypto_breadth(self, panel: PanelState) -> Optional[Dict[str, Any]]:
        symbols = self._reliable_symbol_map(panel, {"BTC", "ETH", "BNB"})
        entries = []
        for symbol in ("BTC", "ETH", "BNB"):
            item = symbols.get(symbol)
            if item is None:
                continue
            change = self._change_value(item)
            if change is None:
                continue
            entries.append((item, change))
        if len(entries) < 2:
            return None
        advancers = sum(1 for _, change in entries if change > 0)
        decliners = sum(1 for _, change in entries if change < 0)
        freshness = self._weakest_freshness([self._item_freshness(item, panel) for item, _ in entries])
        avg_change = sum(change for _, change in entries) / len(entries)
        return {
            "count": len(entries),
            "advancers": advancers,
            "decliners": decliners,
            "avg_change": avg_change,
            "freshness": freshness,
        }

    def _extract_usd_pressure_components(self, fx_panel: PanelState, rates_panel: PanelState) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        specs = [
            ("DXY", "DXY", fx_panel, False),
            ("DXY", "DXY", rates_panel, False),
            ("USDCNH", "USD/CNH", fx_panel, False),
            ("USDJPY", "USD/JPY", fx_panel, False),
            ("EURUSD", "EUR/USD", fx_panel, True),
        ]
        seen: set[str] = set()
        for symbol, label, panel, invert in specs:
            if symbol in seen:
                continue
            item = self._first_reliable_item(panel, {symbol})
            if item is None:
                continue
            change = self._change_value(item)
            if change is None:
                continue
            seen.add(symbol)
            items.append(
                {
                    "symbol": symbol,
                    "label": label,
                    "change": change,
                    "signal": -change if invert else change,
                    "freshness": self._item_freshness(item, panel),
                    "panel": panel,
                    "source": item.get("source") or panel.source,
                    "sourceLabel": item.get("sourceLabel") or panel.payload.get("sourceLabel"),
                    "sourceType": item.get("sourceType") or panel.payload.get("sourceType"),
                    "asOf": item.get("asOf") or item.get("updatedAt") or panel.as_of or panel.updated_at,
                }
            )
        return items

    def _extract_us_rates_components(self, panels: Iterable[PanelState]) -> List[Dict[str, Any]]:
        panels = tuple(panels)
        items: List[Dict[str, Any]] = []
        for symbol in ("US2Y", "US10Y", "US30Y"):
            selected = self._preferred_symbol_item(panels, {symbol})
            if selected is None:
                continue
            panel, item = selected
            change = self._change_value(item)
            if change is None:
                continue
            items.append(
                {
                    "symbol": symbol,
                    "kind": "yield",
                    "change": change,
                    "signal": -change,
                    "freshness": self._item_freshness(item, panel),
                    "source": item.get("source") or panel.source,
                    "sourceLabel": item.get("sourceLabel") or panel.payload.get("sourceLabel"),
                    "sourceType": item.get("sourceType") or panel.payload.get("sourceType"),
                    "asOf": item.get("asOf") or item.get("updatedAt") or panel.as_of or panel.updated_at,
                }
            )
        for symbol in ("SOFR",):
            selected = self._preferred_symbol_item(panels, {symbol})
            if selected is None:
                continue
            panel, item = selected
            value = self._numeric(item.get("value"))
            if value is None:
                continue
            items.append(
                {
                    "symbol": symbol,
                    "kind": "observation",
                    "value": value,
                    "unit": str(item.get("unit") or ""),
                    "freshness": self._item_freshness(item, panel),
                    "source": item.get("source") or panel.source,
                    "sourceLabel": item.get("sourceLabel") or panel.payload.get("sourceLabel"),
                    "sourceType": item.get("sourceType") or panel.payload.get("sourceType"),
                    "asOf": item.get("asOf") or item.get("updatedAt") or panel.as_of or panel.updated_at,
                }
            )
        for symbol in ("US10Y2Y", "US10Y3M"):
            selected = self._preferred_symbol_item(panels, {symbol})
            if selected is None:
                continue
            panel, item = selected
            value = self._numeric(item.get("value"))
            if value is None:
                continue
            items.append(
                {
                    "symbol": symbol,
                    "kind": "curve",
                    "value": value,
                    "unit": str(item.get("unit") or ""),
                    "freshness": self._item_freshness(item, panel),
                    "source": item.get("source") or panel.source,
                    "sourceLabel": item.get("sourceLabel") or panel.payload.get("sourceLabel"),
                    "sourceType": item.get("sourceType") or panel.payload.get("sourceType"),
                    "asOf": item.get("asOf") or item.get("updatedAt") or panel.as_of or panel.updated_at,
                }
            )
        return items

    def _extract_credit_stress_observation(self, panel: PanelState) -> Optional[Dict[str, Any]]:
        item = self._first_reliable_item(panel, {"CREDIT"})
        if item is None:
            return None
        if self._item_source_type(item, panel) != "official_public":
            return None
        source_id = str(item.get("sourceId") or "").upper()
        if source_id and "BAMLH0A0HYM2" not in source_id:
            return None
        value = self._numeric(item.get("value"))
        if value is None:
            return None
        return {
            "value": value,
            "unit": str(item.get("unit") or ""),
        }

    def _extract_us_breadth_components(self, panel: PanelState) -> Optional[Dict[str, Any]]:
        symbol_map = self._reliable_symbol_map(panel, {"SECTORS_UP", "SECTORS_DOWN", "RSP_SPY", "IWM_SPY", "QQQ_SPY"})
        up = symbol_map.get("SECTORS_UP")
        down = symbol_map.get("SECTORS_DOWN")
        proxies = []
        positive_votes = 0
        negative_votes = 0
        if up is not None and down is not None:
            up_value = self._numeric(up.get("value"))
            down_value = self._numeric(down.get("value"))
            if up_value is not None and down_value is not None:
                if up_value > down_value:
                    positive_votes += 1
                elif up_value < down_value:
                    negative_votes += 1
            else:
                up = None
                down = None
        if up is None or down is None:
            up_value = None
            down_value = None
        freshness_values = [self._item_freshness(item, panel) for item in (up, down) if item is not None]
        for symbol, label in (("RSP_SPY", "RSP/SPY"), ("IWM_SPY", "IWM/SPY"), ("QQQ_SPY", "QQQ/SPY")):
            item = symbol_map.get(symbol)
            if item is None:
                continue
            value = self._change_value(item)
            if value is None:
                value = self._numeric(item.get("value"))
            if value is None:
                continue
            if value > 0:
                positive_votes += 1
            elif value < 0:
                negative_votes += 1
            freshness_values.append(self._item_freshness(item, panel))
            proxies.append({"symbol": symbol, "label": label, "value": value})
        if up_value is None or down_value is None:
            if not proxies:
                return None
            up_value = 0.0
            down_value = 0.0
        return {
            "up_value": up_value,
            "down_value": down_value,
            "proxies": proxies,
            "positive_votes": positive_votes,
            "negative_votes": negative_votes,
            "freshness": self._weakest_freshness(freshness_values),
        }

    def _extract_cn_flow_components(self, panel: PanelState, breadth_panel: PanelState) -> Optional[Dict[str, Any]]:
        flow_labels = {
            "NORTHBOUND": "北向",
            "SOUTHBOUND": "南向",
            "CN_ETF": "ETF",
            "MARGIN_BALANCE": "融资",
            "MAINLAND_MAIN": "主力",
        }
        symbol_map = self._reliable_symbol_map(panel, set(flow_labels))
        flows = []
        positive_votes = 0
        negative_votes = 0
        freshness_values: List[str] = []
        for symbol in ("NORTHBOUND", "SOUTHBOUND", "CN_ETF", "MARGIN_BALANCE", "MAINLAND_MAIN"):
            item = symbol_map.get(symbol)
            if item is None:
                continue
            value = self._numeric(item.get("value"))
            if value is None:
                continue
            if value > 0:
                positive_votes += 1
            elif value < 0:
                negative_votes += 1
            freshness_values.append(self._item_freshness(item, panel))
            flows.append({"symbol": symbol, "label": flow_labels[symbol], "value": value})
        if not flows:
            return None
        breadth_summary = self._extract_cn_breadth_summary(breadth_panel)
        if breadth_summary is not None:
            freshness_values.append(str(breadth_summary["freshness"]))
        return {
            "flows": flows,
            "positive_votes": positive_votes,
            "negative_votes": negative_votes,
            "breadth_summary": breadth_summary["summary"] if breadth_summary is not None else None,
            "freshness": self._weakest_freshness(freshness_values),
        }

    def _extract_cn_breadth_summary(self, panel: PanelState) -> Optional[Dict[str, Any]]:
        symbol_map = self._reliable_symbol_map(panel, {"EFFECT", "ADV_RATIO"})
        effect = symbol_map.get("EFFECT")
        adv_ratio = symbol_map.get("ADV_RATIO")
        if effect is None and adv_ratio is None:
            return None
        parts = []
        freshness_values = []
        if effect is not None:
            value = self._numeric(effect.get("value"))
            if value is not None:
                parts.append(f"EFFECT {value:.0f}")
                freshness_values.append(self._item_freshness(effect, panel))
        if adv_ratio is not None:
            value = self._numeric(adv_ratio.get("value"))
            if value is not None:
                parts.append(f"ADV_RATIO {value:.1f}%")
                freshness_values.append(self._item_freshness(adv_ratio, panel))
        if not parts:
            return None
        return {
            "summary": f"宽度 {' / '.join(parts)}",
            "freshness": self._weakest_freshness(freshness_values),
        }

    def _has_live_crypto_context(self, panel: PanelState) -> bool:
        symbols = {"BTC", "ETH", "BNB", "SOL"}
        return any(
            isinstance(item, dict) and str(item.get("symbol") or "") in symbols
            for item in panel.payload.get("items", [])
        )

    def _fetch_live_crypto_funding_panel(self, panel: PanelState) -> Optional[PanelState]:
        if not self._has_live_crypto_context(panel):
            return None
        self._external_provider_calls_used = True
        items: List[Dict[str, Any]] = []
        updated_at = self._now().isoformat(timespec="seconds")
        provenance = project_source_provenance(source="binance", freshness="live")
        for futures_symbol, short_symbol in (("BTCUSDT", "BTC"), ("ETHUSDT", "ETH")):
            try:
                row = fetch_binance_funding_row(futures_symbol)
            except Exception:
                continue
            funding_rate = self._numeric(row.get("lastFundingRate"))
            if funding_rate is None:
                continue
            as_of = self._timestamp_millis_to_iso(row.get("time")) or updated_at
            funding_percent = round(funding_rate * 100, 4)
            items.append(
                {
                    "symbol": f"{short_symbol}_FUNDING",
                    "label": f"{short_symbol} Funding",
                    "value": funding_percent,
                    "change": funding_percent,
                    "changePercent": funding_percent,
                    "source": "binance",
                    "sourceLabel": provenance["sourceLabel"],
                    "sourceType": provenance["sourceType"],
                    "asOf": as_of,
                    "updatedAt": updated_at,
                    "freshness": "live",
                    "isFallback": False,
                    "fallbackUsed": False,
                }
            )
        if not items:
            return None
        latest_as_of = max(str(item.get("asOf") or updated_at) for item in items)
        payload = {
            "source": "binance",
            "sourceLabel": provenance["sourceLabel"],
            "sourceType": provenance["sourceType"],
            "freshness": "live",
            "asOf": latest_as_of,
            "updatedAt": updated_at,
            "isFallback": False,
            "fallbackUsed": False,
            "items": items,
        }
        return PanelState(
            key="crypto_funding_live",
            payload=payload,
            source="binance",
            freshness="live",
            as_of=latest_as_of,
            updated_at=updated_at,
            is_fallback=False,
            is_stale=False,
        )

    def _fetch_macro_proxy_panel(self, key: str, specs: List[Dict[str, Any]]) -> Optional[PanelState]:
        if not specs:
            return None
        self._external_provider_calls_used = True
        provenance = project_source_provenance(source="yfinance_proxy", source_type="proxy_public", freshness="delayed")
        items = []
        for spec in specs:
            item = self._fetch_macro_proxy_item(spec)
            if item is not None:
                items.append(item)
        if not items:
            return None
        as_of_values = [str(item.get("asOf") or "") for item in items if item.get("asOf")]
        latest_as_of = max(as_of_values) if as_of_values else self._now().isoformat(timespec="seconds")
        payload = {
            "source": "yfinance_proxy",
            "sourceLabel": provenance["sourceLabel"],
            "sourceType": provenance["sourceType"],
            "freshness": "delayed",
            "asOf": latest_as_of,
            "updatedAt": latest_as_of,
            "isFallback": False,
            "fallbackUsed": False,
            "items": items,
        }
        return PanelState(
            key=key,
            payload=payload,
            source="yfinance_proxy",
            freshness="delayed",
            as_of=latest_as_of,
            updated_at=latest_as_of,
            is_fallback=False,
            is_stale=False,
        )

    def _fetch_macro_proxy_item(self, spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ticker = str(spec.get("ticker") or "").strip()
        if not ticker:
            return None
        try:
            frame = fetch_yfinance_quote_history_frame(ticker)
        except Exception:
            return None
        closes = self._frame_column_values(frame, "Close")
        closes = [value for value in closes if value is not None]
        if not closes:
            return None
        latest_raw = closes[-1]
        previous_raw = closes[-2] if len(closes) > 1 else latest_raw
        value_scale = float(spec.get("value_scale") or 1.0)
        latest_value = latest_raw / value_scale if value_scale else latest_raw
        change_percent = ((latest_raw - previous_raw) / previous_raw * 100.0) if previous_raw else 0.0
        as_of = self._frame_last_as_of(frame) or self._now().isoformat(timespec="seconds")
        provenance = project_source_provenance(source="yfinance_proxy", source_type="proxy_public", freshness="delayed")
        item = {
            "symbol": spec["symbol"],
            "label": spec["label"],
            "value": round(latest_value, 3),
            "price": round(latest_value, 3),
            "unit": spec.get("unit"),
            "change": round(change_percent, 3),
            "changePercent": round(change_percent, 3),
            "source": "yfinance_proxy",
            "sourceLabel": provenance["sourceLabel"],
            "sourceType": provenance["sourceType"],
            "freshness": "delayed",
            "asOf": as_of,
            "updatedAt": as_of,
            "isFallback": False,
            "fallbackUsed": False,
        }
        market = self._text(spec.get("market"))
        if market:
            item["market"] = market
        return item

    @staticmethod
    def _direction_from_counts(positive: int, negative: int) -> int:
        if positive > negative:
            return 1
        if negative > positive:
            return -1
        return 0

    def _reliable_items(self, panel: PanelState, symbols: Optional[set[str]]) -> List[Dict[str, Any]]:
        if panel.freshness not in RELIABLE_FRESHNESS or panel.is_fallback or panel.is_stale:
            return []
        reliable: List[Dict[str, Any]] = []
        for raw in panel.payload.get("items", []):
            if not isinstance(raw, dict):
                continue
            symbol = str(raw.get("symbol") or "")
            if symbols and symbol not in symbols:
                continue
            if self._item_freshness(raw, panel) not in RELIABLE_FRESHNESS:
                continue
            reliable.append(raw)
        return reliable

    @staticmethod
    def _item_source_type(item: Dict[str, Any], panel: PanelState) -> str:
        return str(item.get("sourceType") or panel.payload.get("sourceType") or "").lower()

    def _item_freshness(self, item: Dict[str, Any], panel: PanelState) -> str:
        explicit = str(item.get("freshness") or "").lower()
        source = str(item.get("source") or panel.source or "").lower()
        is_fallback = bool(item.get("isFallback") or item.get("fallbackUsed") or panel.is_fallback or source in {"fallback", "mock", "unavailable"})
        if source == "mock" or explicit == "mock":
            return "mock"
        if explicit in FRESHNESS_ORDER:
            return explicit
        if is_fallback:
            return "fallback"
        if panel.is_stale:
            return "stale"
        if source == "yfinance_proxy":
            return "delayed"
        item_as_of = self._parse_time(item.get("asOf") or item.get("updatedAt"))
        panel_as_of = self._parse_time(panel.as_of or panel.updated_at)
        if item_as_of and panel_as_of:
            age_minutes = abs((panel_as_of - item_as_of).total_seconds()) / 60.0
            if age_minutes >= 240:
                return "stale"
            if age_minutes >= 10:
                return "delayed"
            if age_minutes >= 2:
                return "cached"
        return panel.freshness if panel.freshness in RELIABLE_FRESHNESS else "live"

    @staticmethod
    def _change_value(item: Dict[str, Any]) -> Optional[float]:
        for key in ("changePercent", "change_pct", "change"):
            if key in item:
                value = LiquidityMonitorService._numeric(item.get(key))
                if value is not None:
                    return value
        return None

    @staticmethod
    def _numeric(value: Any) -> Optional[float]:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value) if value == value else None
        if isinstance(value, str) and value.strip():
            try:
                return float(value.strip())
            except ValueError:
                return None
        return None

    @staticmethod
    def _text(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _parse_time(value: Any) -> Optional[datetime]:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=CN_TZ)
        return parsed.astimezone(CN_TZ)

    @staticmethod
    def _frame_column_values(frame: Any, column: str) -> List[Optional[float]]:
        if frame is None:
            return []
        try:
            values = frame[column].tolist()
        except Exception:
            return []
        return [LiquidityMonitorService._numeric(value) for value in values]

    @staticmethod
    def _frame_last_as_of(frame: Any) -> Optional[str]:
        index = getattr(frame, "index", None)
        if index is None:
            return None
        try:
            if len(index) == 0:
                return None
            value = index[-1]
        except Exception:
            return None
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        if isinstance(value, datetime):
            dt = value
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(CN_TZ).isoformat(timespec="seconds")
        parsed = LiquidityMonitorService._parse_time(value)
        return parsed.isoformat(timespec="seconds") if parsed else None

    def _summary_with_metadata(
        self,
        summary: str,
        *,
        item: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        source_label: Optional[str] = None,
        source_type: Optional[str] = None,
        as_of: Optional[str] = None,
        freshness: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> str:
        item = item or {}
        resolved_source = self._text(item.get("source")) or self._text(source)
        resolved_source_label = self._text(item.get("sourceLabel")) or self._text(source_label)
        resolved_source_type = self._text(item.get("sourceType")) or self._text(source_type)
        resolved_as_of = self._text(item.get("asOf") or item.get("updatedAt")) or self._text(as_of)
        resolved_freshness = self._text(item.get("freshness")) or self._text(freshness)
        parts = [summary]
        if resolved_source_label or resolved_source:
            label = resolved_source_label or resolved_source or ""
            if resolved_source and resolved_source != label:
                label = f"{label} ({resolved_source})"
            parts.append(f"来源 {label}")
        if resolved_source_type:
            parts.append(f"类型 {resolved_source_type}")
        if resolved_as_of:
            parts.append(f"截至 {resolved_as_of}")
        if resolved_freshness:
            parts.append(f"新鲜度 {resolved_freshness}")
        if reason:
            parts.append(f"原因 {reason}")
        return " | ".join(part for part in parts if part)

    def _panel_unavailable_reason(self, panel: PanelState, default: str) -> str:
        return self._text(panel.payload.get("warning")) or self._text(panel.payload.get("error")) or default

    @staticmethod
    def _timestamp_millis_to_iso(value: Any) -> Optional[str]:
        millis = LiquidityMonitorService._numeric(value)
        if millis is None:
            return None
        return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).astimezone(CN_TZ).isoformat(timespec="seconds")

    @staticmethod
    def _weakest_freshness(values: Iterable[str]) -> str:
        filtered = [value for value in values if value in FRESHNESS_ORDER]
        if not filtered:
            return "unavailable"
        return max(filtered, key=lambda value: FRESHNESS_ORDER.get(value, 99))

    @staticmethod
    def _regime(score: int) -> str:
        if score >= 70:
            return "abundant"
        if score >= 56:
            return "supportive"
        if score >= 45:
            return "neutral"
        if score >= 30:
            return "tight"
        return "stress"

    @staticmethod
    def _signed_percent_text(value: Optional[float]) -> str:
        if value is None:
            return "待确认"
        return f"{value:+.2f}%"

    @staticmethod
    def _signed_number_text(value: Optional[float]) -> str:
        if value is None:
            return "待确认"
        return f"{value:+.2f}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(CN_TZ)
