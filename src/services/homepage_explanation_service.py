# -*- coding: utf-8 -*-
"""Standalone builder for homepage why-it-matters explanation bullets."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from api.v1.schemas.homepage_explanation import (
    HomepageExplanationItemModel,
    HomepageExplanationResponseModel,
    contains_unsafe_text,
    contains_unsafe_token,
    normalize_identifier,
    normalize_token,
)
from src.services.market_data_quality import build_consumer_data_quality_state


NO_ADVICE_DISCLOSURE = "仅供研究观察，不构成交易指令。"
DEFAULT_TITLE = "市场信号说明"
DEFAULT_REVIEW_POINT = "复核相关信号与研究证据。"
DEFAULT_GENERIC_EXPLANATION = "该信号提示当前市场线索值得继续观察，适合复核相关研究证据。"
DEFAULT_BREADTH_EXPLANATION = "广度走弱说明上涨参与率不足，适合复核市场内部扩散。"
DEFAULT_MONEY_FLOW_EXPLANATION = "资金流向集中说明主线较明确，但需要观察扩散是否改善。"
DEFAULT_EVENT_EXPLANATION = "关键事件窗口可能提高波动，适合复核相关研究证据。"

SAFE_SOURCE_MODULES = {
    "market_pulse",
    "money_flow",
    "event_radar",
    "sector_theme_strength",
    "research_queue",
    "dashboard_overview",
    "other",
}
SAFE_RELATED_SIGNAL_LIMIT = 4
SAFE_EXPLANATION_LIMIT = 6
ITEM_STATUS_VALUES = {"ready", "review", "no_evidence", "unavailable"}
TOP_LEVEL_STATUS_VALUES = {"ready", "no_evidence", "unavailable"}


class HomepageExplanationService:
    """Build short, bounded, non-advisory explanation bullets for homepage cards."""

    def build_explanations(
        self,
        payload: Mapping[str, Any] | None = None,
    ) -> HomepageExplanationResponseModel:
        mapping = payload if isinstance(payload, Mapping) else {}
        sanitized = False
        explanations: list[HomepageExplanationItemModel] = []

        raw_explanations = mapping.get("explanations")
        if isinstance(raw_explanations, Sequence) and not isinstance(raw_explanations, (str, bytes, bytearray)):
            for index, raw_item in enumerate(raw_explanations, start=1):
                if not isinstance(raw_item, Mapping):
                    sanitized = True
                    continue
                item, item_sanitized = self._build_item(raw_item, index=index)
                sanitized = sanitized or item_sanitized
                if item is not None:
                    explanations.append(item)
                if len(explanations) >= SAFE_EXPLANATION_LIMIT:
                    break

        as_of = self._safe_optional_text(mapping.get("asOf"), max_length=40)
        if as_of is None and mapping.get("asOf") not in (None, ""):
            sanitized = True

        if not explanations:
            return HomepageExplanationResponseModel(
                status=self._top_level_status(mapping.get("status"), has_items=False),
                asOf=as_of,
                explanations=[],
                noAdviceDisclosure=NO_ADVICE_DISCLOSURE,
                dataQuality=build_consumer_data_quality_state({"status": "no_evidence"}),
            )

        return HomepageExplanationResponseModel(
            status=self._top_level_status(mapping.get("status"), has_items=True),
            asOf=as_of,
            explanations=explanations,
            noAdviceDisclosure=NO_ADVICE_DISCLOSURE,
            dataQuality=self._data_quality(mapping.get("dataQuality"), sanitized=sanitized),
        )

    def _build_item(
        self,
        raw_item: Mapping[str, Any],
        *,
        index: int,
    ) -> tuple[HomepageExplanationItemModel | None, bool]:
        sanitized = False
        source_module = self._safe_source_module(raw_item.get("sourceModule"))
        if source_module != normalize_token(raw_item.get("sourceModule")):
            sanitized = True

        fallback_id = f"{source_module}-{index}"
        item_id = self._safe_identifier(raw_item.get("id"), fallback=fallback_id)
        if item_id != normalize_identifier(raw_item.get("id")):
            sanitized = True

        title = self._safe_text(raw_item.get("title"), fallback=DEFAULT_TITLE, max_length=32)
        if title != str(raw_item.get("title") or "").strip():
            sanitized = sanitized or bool(raw_item.get("title"))

        why_it_matters, generated = self._why_it_matters(raw_item, source_module=source_module)
        sanitized = sanitized or generated

        related_signals = self._safe_related_signals(raw_item.get("relatedSignals"))
        original_related = raw_item.get("relatedSignals")
        if isinstance(original_related, Sequence) and not isinstance(original_related, (str, bytes, bytearray)):
            original_related_tokens = [normalize_token(value) for value in original_related]
            if related_signals != [token for token in original_related_tokens if token]:
                sanitized = True
        elif original_related not in (None, ""):
            sanitized = True

        review_point = self._safe_text(
            raw_item.get("reviewPoint"),
            fallback=DEFAULT_REVIEW_POINT,
            max_length=48,
        )
        if review_point != str(raw_item.get("reviewPoint") or "").strip():
            sanitized = sanitized or bool(raw_item.get("reviewPoint"))

        status = self._item_status(raw_item.get("status"))
        if status != str(raw_item.get("status") or "").strip().lower():
            sanitized = sanitized or raw_item.get("status") not in (None, "")

        return (
            HomepageExplanationItemModel(
                id=item_id,
                sourceModule=source_module,
                title=title,
                whyItMatters=why_it_matters,
                relatedSignals=related_signals,
                reviewPoint=review_point,
                status=status,
            ),
            sanitized,
        )

    def _why_it_matters(
        self,
        raw_item: Mapping[str, Any],
        *,
        source_module: str,
    ) -> tuple[str, bool]:
        raw_text = raw_item.get("whyItMatters")
        safe_text = self._safe_text(raw_text, fallback=None, max_length=80)
        if safe_text is not None:
            return safe_text, False

        signal = self._safe_text(raw_item.get("signal"), fallback=None, max_length=32)
        title = self._safe_text(raw_item.get("title"), fallback=None, max_length=32)
        combined = " ".join(part for part in (signal, title, source_module) if part).lower()
        if "广度" in combined and any(token in combined for token in ("走弱", "偏弱", "收窄", "不足")):
            return DEFAULT_BREADTH_EXPLANATION, True
        if source_module == "money_flow" or "资金流" in combined or "主线" in combined:
            return DEFAULT_MONEY_FLOW_EXPLANATION, True
        if source_module == "event_radar" or "事件" in combined or "窗口" in combined or "波动" in combined:
            return DEFAULT_EVENT_EXPLANATION, True
        return DEFAULT_GENERIC_EXPLANATION, True

    def _data_quality(self, raw_value: Any, *, sanitized: bool) -> dict[str, Any]:
        if sanitized:
            return build_consumer_data_quality_state({"status": "ready"})
        if isinstance(raw_value, Mapping):
            state = str(raw_value.get("state") or raw_value.get("status") or "").strip().lower()
            if state in {"ready", "delayed", "cached", "partial", "no_evidence", "unavailable"}:
                return build_consumer_data_quality_state({"status": state})
        return build_consumer_data_quality_state({"status": "ready"})

    def _top_level_status(self, raw_status: Any, *, has_items: bool) -> str:
        token = str(raw_status or "").strip().lower()
        if not has_items:
            return "unavailable" if token == "unavailable" else "no_evidence"
        return token if token in TOP_LEVEL_STATUS_VALUES and token != "no_evidence" else "ready"

    def _item_status(self, raw_status: Any) -> str:
        token = str(raw_status or "").strip().lower()
        return token if token in ITEM_STATUS_VALUES else "ready"

    def _safe_source_module(self, value: Any) -> str:
        token = normalize_token(value)
        if token in SAFE_SOURCE_MODULES:
            return token
        if token and not contains_unsafe_text(token) and not contains_unsafe_token(token):
            return token[:32]
        return "other"

    def _safe_identifier(self, value: Any, *, fallback: str) -> str:
        token = normalize_identifier(value)
        if token and not contains_unsafe_text(token) and not contains_unsafe_token(token):
            return token[:40]
        return fallback

    def _safe_related_signals(self, value: Any) -> list[str]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return []
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            token = normalize_token(item)
            if not token or contains_unsafe_text(token) or contains_unsafe_token(token):
                continue
            if token in seen:
                continue
            seen.add(token)
            result.append(token[:32])
            if len(result) >= SAFE_RELATED_SIGNAL_LIMIT:
                break
        return result

    def _safe_optional_text(self, value: Any, *, max_length: int) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or contains_unsafe_text(text) or len(text) > max_length:
            return None
        return text

    def _safe_text(
        self,
        value: Any,
        *,
        fallback: str | None,
        max_length: int,
    ) -> str | None:
        if value is None:
            return fallback
        text = str(value).strip()
        if not text:
            return fallback
        if contains_unsafe_text(text) or len(text) > max_length:
            return fallback
        return text


__all__ = [
    "HomepageExplanationService",
    "NO_ADVICE_DISCLOSURE",
]
