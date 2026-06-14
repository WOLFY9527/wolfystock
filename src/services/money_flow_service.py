# -*- coding: utf-8 -*-
"""Standalone homepage money flow proxy scaffold.

This service is contract-only. It does not wire external fund-flow providers,
make network calls, mutate caches, or change existing homepage/dashboard
runtime behavior.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from api.v1.schemas.money_flow import HomeMoneyFlowProxyResponse
from src.services.market_data_quality import build_consumer_data_quality_state


NO_ADVICE_DISCLOSURE = "仅用于观察昨日资金流向代理，不构成投资建议或交易指令。"
NO_EVIDENCE_INTERPRETATION = (
    "昨日 observed flow proxy 暂无证据；当前未接入真实资金流提供方，建议仅观察并复核。"
)
PARTIAL_INTERPRETATION = (
    "昨日 observed flow proxy 仅形成局部观察，当前只可用于相对强度与扩散/收敛复核。"
)
READY_INTERPRETATION = (
    "昨日 observed flow proxy 已整理为首页 contract，但仍属于观察型代理信号，需结合后续复核。"
)
SOURCE_STATUS_SUMMARY = (
    "未接入真实资金流提供方；当前仅保留 observed flow proxy contract scaffold。"
)
STYLE_NO_EVIDENCE_INTERPRETATION = (
    "成长/价值 observed flow proxy 暂无证据，当前只保留观察位并等待后续复核。"
)
OFFENSE_DEFENSE_NO_EVIDENCE_INTERPRETATION = (
    "进攻/防守 observed flow proxy 暂无证据，当前只保留观察位并等待后续复核。"
)
STYLE_PARTIAL_INTERPRETATION = "成长/价值 observed flow proxy 仅见局部相对强度变化，仍需观察并复核。"
OFFENSE_DEFENSE_PARTIAL_INTERPRETATION = "进攻/防守 observed flow proxy 仅见局部扩散线索，仍需观察并复核。"

_STATUS_ORDER = {"ready": 0, "partial": 1, "no_evidence": 2, "unavailable": 3}
_VALID_CATEGORIES = {"sector", "theme", "style", "asset_class", "other"}
_VALID_DIRECTIONS = {"inflow", "outflow", "neutral"}
_VALID_STRENGTH = {"strong", "moderate", "weak", "mixed", "unknown"}
_VALID_BREADTH = {"broadening", "converging", "mixed", "unknown"}
_VALID_RELATIVE_MOVE = {"strengthening", "weakening", "flat", "unknown"}


class MoneyFlowService:
    """Build a bounded consumer-safe money flow proxy contract."""

    def build_homepage_money_flow_proxy(
        self,
        *,
        as_of: str | None = None,
        top_inflows: Sequence[Mapping[str, Any]] | None = None,
        top_outflows: Sequence[Mapping[str, Any]] | None = None,
        style_bias: Mapping[str, Any] | None = None,
        offensive_defensive_bias: Mapping[str, Any] | None = None,
        interpretation: str | None = None,
    ) -> dict[str, Any]:
        inflows = [self._normalize_item(item, default_direction="inflow") for item in top_inflows or ()]
        outflows = [self._normalize_item(item, default_direction="outflow") for item in top_outflows or ()]
        status = self._derive_status(
            has_items=bool(inflows or outflows),
            style_bias=style_bias,
            offensive_defensive_bias=offensive_defensive_bias,
        )
        quality = build_consumer_data_quality_state(self._quality_seed(status))
        payload = HomeMoneyFlowProxyResponse(
            status=status,
            asOf=as_of if status != "no_evidence" else None,
            topInflows=inflows,
            topOutflows=outflows,
            styleBias=self._normalize_bias(
                style_bias,
                default_bias="unknown",
                default_interpretation=STYLE_NO_EVIDENCE_INTERPRETATION
                if status == "no_evidence"
                else STYLE_PARTIAL_INTERPRETATION,
                quality=quality,
            ),
            offensiveDefensiveBias=self._normalize_bias(
                offensive_defensive_bias,
                default_bias="unknown",
                default_interpretation=OFFENSE_DEFENSE_NO_EVIDENCE_INTERPRETATION
                if status == "no_evidence"
                else OFFENSE_DEFENSE_PARTIAL_INTERPRETATION,
                quality=quality,
            ),
            interpretation=interpretation or self._default_interpretation(status),
            sourceStatus={
                "providerWired": False,
                "proxyMode": "observed_flow_proxy",
                "observationOnly": True,
                "summary": SOURCE_STATUS_SUMMARY,
            },
            dataQuality=quality,
            noAdviceDisclosure=NO_ADVICE_DISCLOSURE,
        )
        return payload.model_dump(mode="json")

    def _derive_status(
        self,
        *,
        has_items: bool,
        style_bias: Mapping[str, Any] | None,
        offensive_defensive_bias: Mapping[str, Any] | None,
    ) -> str:
        if not has_items and not style_bias and not offensive_defensive_bias:
            return "no_evidence"
        if has_items and style_bias and offensive_defensive_bias:
            return "ready"
        return "partial"

    def _normalize_item(self, raw: Mapping[str, Any], *, default_direction: str) -> dict[str, Any]:
        name = self._text(raw.get("name")) or "未命名观察项"
        category = self._enum_value(raw.get("category"), _VALID_CATEGORIES, default="other")
        direction = self._enum_value(raw.get("direction"), _VALID_DIRECTIONS, default=default_direction)
        strength = self._enum_value(raw.get("strength"), _VALID_STRENGTH, default="unknown")
        breadth = self._enum_value(raw.get("breadth"), _VALID_BREADTH, default="unknown")
        relative_move = self._enum_value(raw.get("relativeMove"), _VALID_RELATIVE_MOVE, default="unknown")
        data_quality = self._quality_state(raw.get("dataQuality"))
        return {
            "name": name,
            "category": category,
            "direction": direction,
            "strength": strength,
            "breadth": breadth,
            "relativeMove": relative_move,
            "interpretation": self._text(raw.get("interpretation"))
            or self._default_item_interpretation(name=name, direction=direction),
            "dataQuality": data_quality,
        }

    def _normalize_bias(
        self,
        raw: Mapping[str, Any] | None,
        *,
        default_bias: str,
        default_interpretation: str,
        quality: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload = dict(raw or {})
        return {
            "bias": self._text(payload.get("bias")) or default_bias,
            "interpretation": self._text(payload.get("interpretation")) or default_interpretation,
            "dataQuality": build_consumer_data_quality_state(payload.get("dataQuality") or quality),
        }

    def _default_interpretation(self, status: str) -> str:
        if status == "ready":
            return READY_INTERPRETATION
        if status == "partial":
            return PARTIAL_INTERPRETATION
        if status == "unavailable":
            return "昨日 observed flow proxy 暂不可用；请等待后续复核。"
        return NO_EVIDENCE_INTERPRETATION

    def _default_item_interpretation(self, *, name: str, direction: str) -> str:
        if direction == "inflow":
            return f"昨日 observed flow proxy 显示{name}相对强度走强，仍需观察并复核。"
        if direction == "outflow":
            return f"昨日 observed flow proxy 显示{name}相对强度走弱，仍需观察并复核。"
        return f"昨日 observed flow proxy 对{name}暂无明确方向，建议继续观察并复核。"

    def _quality_seed(self, status: str) -> dict[str, Any]:
        if status == "ready":
            return {"status": "ready"}
        if status == "partial":
            return {"status": "partial", "isPartial": True}
        if status == "unavailable":
            return {"isUnavailable": True}
        return {}

    def _quality_state(self, value: Any) -> str:
        candidate = self._text(value).lower()
        if candidate in _STATUS_ORDER:
            return candidate
        return "no_evidence"

    def _enum_value(self, value: Any, allowed: set[str], *, default: str) -> str:
        candidate = self._text(value).lower()
        return candidate if candidate in allowed else default

    def _text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
