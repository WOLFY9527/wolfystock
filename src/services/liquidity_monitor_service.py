# -*- coding: utf-8 -*-
"""Cache-only advisory liquidity monitor service."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from src.services.market_cache import MarketCache, market_cache
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

    def get_liquidity_monitor(self) -> Dict[str, Any]:
        panels = {key: self._read_panel(key) for key in ("crypto", "volatility", "rates", "fx_commodities", "funds_flow", "us_breadth", "cn_indices", "cn_flows", "futures")}
        indicators = [
            self._crypto_spot_indicator(panels["crypto"]),
            self._crypto_funding_indicator(panels["crypto"]),
            self._vix_indicator(panels["volatility"]),
            self._usd_pressure_indicator(panels["fx_commodities"], panels["rates"]),
            self._us_rates_indicator(panels["rates"]),
            self._us_etf_flow_indicator(panels["funds_flow"]),
            self._us_breadth_indicator(panels["us_breadth"]),
            self._cn_hk_index_indicator(panels["cn_indices"]),
            self._cn_hk_flows_indicator(panels["cn_flows"]),
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
                "externalProviderCalls": False,
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
        items = [item for item in self._reliable_items(panel, {"BTC", "ETH", "BNB"}) if self._change_value(item) is not None]
        if len(items) < 2:
            return self._indicator("crypto_spot_momentum", "Crypto 现货动量", panel, "unavailable", 0, 6, False, "BTC / ETH / BNB 缓存不足")
        avg_change = sum(float(self._change_value(item)) for item in items) / len(items)
        freshness = self._weakest_freshness([self._item_freshness(item, panel) for item in items])
        status = "live" if len(items) == 3 and freshness in {"live", "cached"} else "partial"
        return self._indicator(
            "crypto_spot_momentum",
            "Crypto 现货动量",
            panel,
            status,
            6 if avg_change > 0 else -6 if avg_change < 0 else 0,
            6,
            True,
            f"均值 {avg_change:+.2f}%",
            freshness=freshness,
        )

    def _crypto_funding_indicator(self, panel: PanelState) -> Dict[str, Any]:
        items = [item for item in self._reliable_items(panel, None) if str(item.get("symbol") or "").endswith("_FUNDING") and self._numeric(item.get("value")) is not None]
        if not items:
            return self._indicator("crypto_funding", "Crypto Funding", panel, "unavailable", 0, 0, False, "仅在真实 funding 快照存在时显示")
        avg_value = sum(float(self._numeric(item.get("value")) or 0.0) for item in items) / len(items)
        freshness = self._weakest_freshness([self._item_freshness(item, panel) for item in items])
        return self._indicator("crypto_funding", "Crypto Funding", panel, "partial", 0, 0, False, f"均值 {avg_value:+.4f}", freshness=freshness)

    def _vix_indicator(self, panel: PanelState) -> Dict[str, Any]:
        item = self._first_reliable_item(panel, {"VIX"})
        if item is None:
            return self._indicator("vix_pressure", "VIX / 波动率压力", panel, "unavailable", 0, 8, False, "未读取到可靠 VIX")
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
        return self._indicator("vix_pressure", "VIX / 波动率压力", panel, "live", contribution, 8, True, self._signed_percent_text(change), freshness=self._item_freshness(item, panel))

    def _usd_pressure_indicator(self, fx_panel: PanelState, rates_panel: PanelState) -> Dict[str, Any]:
        item = self._first_reliable_item(fx_panel, {"DXY"}) or self._first_reliable_item(rates_panel, {"DXY"})
        base_panel = fx_panel if self._first_reliable_item(fx_panel, {"DXY"}) is not None else rates_panel
        if item is None:
            return self._indicator("usd_pressure", "DXY / 美元压力", fx_panel, "unavailable", 0, 6, False, "仅在可靠 FX / 宏观缓存存在时启用")
        change = self._change_value(item)
        contribution = 6 if (change or 0) < 0 else -6 if (change or 0) > 0 else 0
        return self._indicator("usd_pressure", "DXY / 美元压力", base_panel, "partial", contribution, 6, True, self._signed_percent_text(change), freshness=self._item_freshness(item, base_panel))

    def _us_rates_indicator(self, panel: PanelState) -> Dict[str, Any]:
        item = self._first_reliable_item(panel, {"US10Y"})
        if item is None:
            return self._indicator("us_rates_pressure", "US Rates / 利率压力", panel, "unavailable", 0, 6, False, "仅在可靠利率缓存存在时启用")
        change = self._change_value(item)
        contribution = 6 if (change or 0) < 0 else -6 if (change or 0) > 0 else 0
        return self._indicator("us_rates_pressure", "US Rates / 利率压力", panel, "partial", contribution, 6, True, self._signed_percent_text(change), freshness=self._item_freshness(item, panel))

    def _us_etf_flow_indicator(self, panel: PanelState) -> Dict[str, Any]:
        item = self._first_reliable_item(panel, {"ETF"})
        if item is None:
            return self._indicator("us_etf_flow_proxy", "US ETF 资金代理", panel, "unavailable", 0, 5, False, "仅在可靠 funds-flow 缓存存在时启用")
        value = self._numeric(item.get("value"))
        contribution = 5 if (value or 0) > 0 else -5 if (value or 0) < 0 else 0
        return self._indicator("us_etf_flow_proxy", "US ETF 资金代理", panel, "partial", contribution, 5, True, self._signed_number_text(value), freshness=self._item_freshness(item, panel))

    def _us_breadth_indicator(self, panel: PanelState) -> Dict[str, Any]:
        up = self._first_reliable_item(panel, {"SECTORS_UP"})
        down = self._first_reliable_item(panel, {"SECTORS_DOWN"})
        if up is None or down is None:
            return self._indicator("us_breadth_proxy", "US Broadth / 广度代理", panel, "unavailable", 0, 6, False, "仅在可靠 breadth 缓存存在时启用")
        up_value = self._numeric(up.get("value"))
        down_value = self._numeric(down.get("value"))
        contribution = 6 if (up_value or 0) > (down_value or 0) else -6 if (up_value or 0) < (down_value or 0) else 0
        freshness = self._weakest_freshness([self._item_freshness(up, panel), self._item_freshness(down, panel)])
        return self._indicator("us_breadth_proxy", "US 广度代理", panel, "partial", contribution, 6, True, f"{int(up_value or 0)} / {int(down_value or 0)}", freshness=freshness)

    def _cn_hk_index_indicator(self, panel: PanelState) -> Dict[str, Any]:
        items = [item for item in self._reliable_items(panel, None) if str(item.get("market") or "") in {"CN", "HK"} and self._change_value(item) is not None]
        if not items:
            return self._indicator("cn_hk_index_context", "CN/HK 指数环境", panel, "unavailable", 0, 0, False, "缺少可靠指数快照")
        avg_change = sum(float(self._change_value(item)) for item in items) / len(items)
        status = "live" if len(items) >= 4 and panel.source != "mixed" else "partial"
        freshness = self._weakest_freshness([self._item_freshness(item, panel) for item in items])
        return self._indicator("cn_hk_index_context", "CN/HK 指数环境", panel, status, 0, 0, False, f"均值 {avg_change:+.2f}%", freshness=freshness)

    def _cn_hk_flows_indicator(self, panel: PanelState) -> Dict[str, Any]:
        if panel.is_fallback or panel.freshness in {"fallback", "mock", "error", "unavailable"}:
            return self._indicator("cn_hk_flows", "CN/HK 资金流", panel, "unavailable", 0, 6, False, "Phase 1 仅在非 fallback 真实流量数据存在时启用")
        northbound = self._first_reliable_item(panel, {"NORTHBOUND", "CN_ETF"})
        if northbound is None:
            return self._indicator("cn_hk_flows", "CN/HK 资金流", panel, "unavailable", 0, 6, False, "缺少真实 northbound / ETF flow")
        value = self._numeric(northbound.get("value"))
        contribution = 6 if (value or 0) > 0 else -6 if (value or 0) < 0 else 0
        return self._indicator("cn_hk_flows", "CN/HK 资金流", panel, "partial", contribution, 6, True, self._signed_number_text(value), freshness=self._item_freshness(northbound, panel))

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
        return LiquidityMonitorService._numeric(item.get("changePercent") or item.get("change_pct") or item.get("change"))

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
