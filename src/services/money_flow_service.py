# -*- coding: utf-8 -*-
"""Standalone homepage money flow proxy scaffold.

This service is contract-only. It does not wire external fund-flow providers,
make network calls, mutate caches, or change existing homepage/dashboard
runtime behavior.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from api.v1.schemas.money_flow import MAX_TOP_MONEY_FLOW_ITEMS, HomeMoneyFlowProxyResponse
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
    "未接入真实资金流提供方；当前仅输出 observed flow proxy，不能代表实时或权威资金流。"
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
_VALID_STYLE_BIAS = {"growth", "value", "balanced", "mixed", "unknown"}
_VALID_OFFENSE_DEFENSE_BIAS = {"offensive", "defensive", "balanced", "mixed", "unknown"}

_STRENGTH_ALIASES = {
    "strong": "strong",
    "high": "strong",
    "leading": "strong",
    "moderate": "moderate",
    "medium": "moderate",
    "neutral": "mixed",
    "mixed": "mixed",
    "weak": "weak",
    "low": "weak",
}
_BREADTH_ALIASES = {
    "broadening": "broadening",
    "broad": "broadening",
    "expanding": "broadening",
    "wide": "broadening",
    "converging": "converging",
    "narrowing": "converging",
    "contracting": "converging",
    "mixed": "mixed",
    "neutral": "mixed",
}
_RELATIVE_MOVE_ALIASES = {
    "strengthening": "strengthening",
    "stronger": "strengthening",
    "improving": "strengthening",
    "rising": "strengthening",
    "weakening": "weakening",
    "weaker": "weakening",
    "softening": "weakening",
    "falling": "weakening",
    "flat": "flat",
    "stable": "flat",
    "neutral": "flat",
}
_STYLE_BIAS_ALIASES = {
    "growth": "growth",
    "growthtilt": "growth",
    "value": "value",
    "valuetilt": "value",
    "balanced": "balanced",
    "balance": "balanced",
    "mixed": "mixed",
    "neutral": "balanced",
}
_OFFENSE_DEFENSE_BIAS_ALIASES = {
    "offensive": "offensive",
    "riskon": "offensive",
    "cyclical": "offensive",
    "defensive": "defensive",
    "riskoff": "defensive",
    "balanced": "balanced",
    "balance": "balanced",
    "mixed": "mixed",
    "neutral": "balanced",
}

_FORBIDDEN_TEXT_RE = re.compile(
    r"traceback|token|session|api[_-]?key|secret|reasoncodes?|sourcetype|trustlevel|schema"
    r"|provider|fallback|confidence|debug|real[- ]?time|authoritative|https?://|cookie",
    re.IGNORECASE,
)
_FORBIDDEN_ADVICE_RE = re.compile(
    r"\b(buy now|sell now|place order|submit order|trade recommendation|trading advice|investment advice|"
    r"ai recommends you buy|guaranteed return|target price|stop loss|take profit)\b|"
    r"买入|卖出|下单|立即交易|投资建议|交易指令|保证收益|目标价|止损|止盈",
    re.IGNORECASE,
)
_UNSAFE_TEXT_CHARS_RE = re.compile(r"[{}\[\]<>]")
_SAFE_TEXT_RE = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff _./()%-]+")

_STRENGTH_SCORE = {"strong": 3, "moderate": 2, "weak": 1, "mixed": 0, "unknown": -1}
_INTENSITY_SCORE = {"broadening": 2, "converging": 2, "strengthening": 2, "weakening": 2, "mixed": 1, "flat": 1, "unknown": 0}
_DATA_QUALITY_SCORE = {"ready": 2, "delayed": 1, "cached": 1, "partial": 1, "no_evidence": 0, "unavailable": -1}


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
        inflows = self._normalize_ranked_items(top_inflows, section_direction="inflow")
        outflows = self._normalize_ranked_items(top_outflows, section_direction="outflow")
        style_payload = self._normalize_style_bias(style_bias)
        offense_defense_payload = self._normalize_offensive_defensive_bias(offensive_defensive_bias)
        status = self._derive_status(
            has_items=bool(inflows or outflows),
            style_bias=style_payload,
            offensive_defensive_bias=offense_defense_payload,
        )
        quality = build_consumer_data_quality_state(self._quality_seed(status))
        payload = HomeMoneyFlowProxyResponse(
            status=status,
            asOf=self._safe_text(as_of, max_length=40) if status != "no_evidence" else None,
            topInflows=inflows,
            topOutflows=outflows,
            styleBias=self._finalize_style_bias(style_payload, status=status, quality=quality),
            offensiveDefensiveBias=self._finalize_offense_defense_bias(
                offense_defense_payload,
                status=status,
                quality=quality,
            ),
            interpretation=self._safe_text(interpretation) or self._default_interpretation(status),
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
        style_bias: Mapping[str, Any],
        offensive_defensive_bias: Mapping[str, Any],
    ) -> str:
        has_style_evidence = bool(style_bias.get("_hasEvidence"))
        has_offense_defense_evidence = bool(offensive_defensive_bias.get("_hasEvidence"))
        if not has_items and not has_style_evidence and not has_offense_defense_evidence:
            return "no_evidence"
        if has_items and has_style_evidence and has_offense_defense_evidence:
            return "ready"
        return "partial"

    def _normalize_ranked_items(
        self,
        raw_items: Sequence[Mapping[str, Any]] | None,
        *,
        section_direction: str,
    ) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for raw in raw_items or ():
            item = self._normalize_item(raw, section_direction=section_direction)
            if item is not None:
                ranked.append(item)

        ranked.sort(
            key=lambda item: (
                -int(item["_rankScore"]),
                str(item["name"]).lower(),
                str(item["category"]),
            )
        )

        result: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for item in ranked:
            normalized_name = str(item["name"]).strip().lower()
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            result.append({key: value for key, value in item.items() if not key.startswith("_")})
            if len(result) >= MAX_TOP_MONEY_FLOW_ITEMS:
                break
        return result

    def _normalize_item(self, raw: Mapping[str, Any], *, section_direction: str) -> dict[str, Any] | None:
        if not isinstance(raw, Mapping):
            return None

        name = self._safe_text(raw.get("name"), max_length=32)
        if not name:
            return None
        category = self._enum_value(raw.get("category"), _VALID_CATEGORIES, default="other")
        direction = section_direction
        strength = self._normalize_strength(raw.get("strength"))
        breadth = self._normalize_breadth(raw.get("breadth"))
        relative_move = self._normalize_relative_move(raw.get("relativeMove"))
        data_quality = self._quality_state(raw.get("dataQuality"))
        interpretation = self._safe_text(raw.get("interpretation")) or self._default_item_interpretation(
            name=name,
            direction=direction,
        )
        return {
            "name": name,
            "category": category,
            "direction": direction,
            "strength": strength,
            "breadth": breadth,
            "relativeMove": relative_move,
            "interpretation": interpretation,
            "dataQuality": data_quality,
            "_rankScore": self._rank_score(
                strength=strength,
                breadth=breadth,
                relative_move=relative_move,
                data_quality=data_quality,
            ),
        }

    def _normalize_style_bias(
        self,
        raw: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        payload = dict(raw) if isinstance(raw, Mapping) else {}
        bias = self._normalize_bias_token(
            payload.get("bias"),
            aliases=_STYLE_BIAS_ALIASES,
            allowed=_VALID_STYLE_BIAS,
        )
        return {
            "bias": bias,
            "interpretation": self._safe_text(payload.get("interpretation")),
            "dataQuality": self._bias_quality(payload.get("dataQuality"), has_evidence=bias != "unknown"),
            "_hasEvidence": bias != "unknown",
        }

    def _normalize_offensive_defensive_bias(
        self,
        raw: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        payload = dict(raw) if isinstance(raw, Mapping) else {}
        bias = self._normalize_bias_token(
            payload.get("bias"),
            aliases=_OFFENSE_DEFENSE_BIAS_ALIASES,
            allowed=_VALID_OFFENSE_DEFENSE_BIAS,
        )
        return {
            "bias": bias,
            "interpretation": self._safe_text(payload.get("interpretation")),
            "dataQuality": self._bias_quality(payload.get("dataQuality"), has_evidence=bias != "unknown"),
            "_hasEvidence": bias != "unknown",
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

    def _finalize_style_bias(self, payload: Mapping[str, Any], *, status: str, quality: Mapping[str, Any]) -> dict[str, Any]:
        bias = str(payload.get("bias") or "unknown")
        default_interpretation = STYLE_NO_EVIDENCE_INTERPRETATION if status == "no_evidence" else STYLE_PARTIAL_INTERPRETATION
        if bias == "growth":
            default_interpretation = "成长 observed flow proxy 相对更强，但仍仅供观察并复核。"
        elif bias == "value":
            default_interpretation = "价值 observed flow proxy 相对更强，但仍仅供观察并复核。"
        elif bias in {"balanced", "mixed"}:
            default_interpretation = "成长/价值 observed flow proxy 未形成单侧偏向，仍需观察并复核。"
        return {
            "bias": bias,
            "interpretation": str(payload.get("interpretation") or default_interpretation),
            "dataQuality": payload.get("dataQuality") or quality,
        }

    def _finalize_offense_defense_bias(
        self,
        payload: Mapping[str, Any],
        *,
        status: str,
        quality: Mapping[str, Any],
    ) -> dict[str, Any]:
        bias = str(payload.get("bias") or "unknown")
        default_interpretation = (
            OFFENSE_DEFENSE_NO_EVIDENCE_INTERPRETATION
            if status == "no_evidence"
            else OFFENSE_DEFENSE_PARTIAL_INTERPRETATION
        )
        if bias == "offensive":
            default_interpretation = "进攻 observed flow proxy 相对更强，但仍仅供观察并复核。"
        elif bias == "defensive":
            default_interpretation = "防守 observed flow proxy 相对更强，但仍仅供观察并复核。"
        elif bias in {"balanced", "mixed"}:
            default_interpretation = "进攻/防守 observed flow proxy 未形成单侧偏向，仍需观察并复核。"
        return {
            "bias": bias,
            "interpretation": str(payload.get("interpretation") or default_interpretation),
            "dataQuality": payload.get("dataQuality") or quality,
        }

    def _quality_seed(self, status: str) -> dict[str, Any]:
        if status == "ready":
            return {"status": "ready"}
        if status == "partial":
            return {"status": "partial", "isPartial": True}
        if status == "unavailable":
            return {"isUnavailable": True}
        return {}

    def _quality_state(self, value: Any) -> str:
        if isinstance(value, Mapping):
            return str(build_consumer_data_quality_state(value).get("state") or "no_evidence")
        candidate = self._text(value).lower()
        if candidate in _STATUS_ORDER:
            return candidate
        return "no_evidence"

    def _enum_value(self, value: Any, allowed: set[str], *, default: str) -> str:
        candidate = self._text(value).lower()
        return candidate if candidate in allowed else default

    def _normalize_strength(self, value: Any) -> str:
        return self._normalize_scored_token(value, aliases=_STRENGTH_ALIASES, allowed=_VALID_STRENGTH)

    def _normalize_breadth(self, value: Any) -> str:
        return self._normalize_scored_token(value, aliases=_BREADTH_ALIASES, allowed=_VALID_BREADTH)

    def _normalize_relative_move(self, value: Any) -> str:
        return self._normalize_scored_token(value, aliases=_RELATIVE_MOVE_ALIASES, allowed=_VALID_RELATIVE_MOVE)

    def _normalize_scored_token(self, value: Any, *, aliases: Mapping[str, str], allowed: set[str]) -> str:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return self._numeric_bucket(float(value), allowed=allowed)
        candidate = self._slug(value)
        if candidate in aliases:
            normalized = aliases[candidate]
            return normalized if normalized in allowed else "unknown"
        return "unknown"

    def _normalize_bias_token(self, value: Any, *, aliases: Mapping[str, str], allowed: set[str]) -> str:
        candidate = self._slug(value)
        if candidate in aliases:
            normalized = aliases[candidate]
            return normalized if normalized in allowed else "unknown"
        return "unknown"

    def _numeric_bucket(self, value: float, *, allowed: set[str]) -> str:
        if "strong" in allowed:
            magnitude = abs(value)
            if magnitude >= 0.67:
                return "strong"
            if magnitude >= 0.34:
                return "moderate"
            return "weak"
        if "broadening" in allowed:
            if value >= 0.25:
                return "broadening"
            if value <= -0.25:
                return "converging"
            return "mixed"
        if "strengthening" in allowed:
            if value >= 0.25:
                return "strengthening"
            if value <= -0.25:
                return "weakening"
            return "flat"
        return "unknown"

    def _bias_quality(self, value: Any, *, has_evidence: bool) -> dict[str, Any]:
        if not has_evidence:
            return build_consumer_data_quality_state({})
        if isinstance(value, Mapping):
            return build_consumer_data_quality_state(value)
        return build_consumer_data_quality_state({"status": self._quality_state(value)})

    def _rank_score(self, *, strength: str, breadth: str, relative_move: str, data_quality: str) -> int:
        return (
            _STRENGTH_SCORE.get(strength, -1) * 100
            + _INTENSITY_SCORE.get(breadth, 0) * 10
            + _INTENSITY_SCORE.get(relative_move, 0) * 3
            + _DATA_QUALITY_SCORE.get(data_quality, -1)
        )

    def _safe_text(self, value: Any, *, max_length: int = 120) -> str:
        text = self._text(value)
        if not text:
            return ""
        lowered = text.lower()
        if len(text) > max_length:
            return ""
        if _FORBIDDEN_TEXT_RE.search(lowered) or _FORBIDDEN_ADVICE_RE.search(text) or _UNSAFE_TEXT_CHARS_RE.search(text):
            return ""
        return _SAFE_TEXT_RE.sub("", text).strip()

    def _slug(self, value: Any) -> str:
        return re.sub(r"[^0-9a-z]+", "", self._text(value).lower())

    def _text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
