# -*- coding: utf-8 -*-
"""Deterministic scaffold for homepage research queue prioritization."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence

from api.v1.schemas.research_queue import (
    ResearchQueueBuildInputs,
    ResearchQueueCategory,
    ResearchQueueDataQuality,
    ResearchQueueEvidenceStatus,
    ResearchQueueItem,
    ResearchQueueResponse,
    ResearchQueueSeedItem,
    ResearchQueueTopLevelStatus,
)


NO_ADVICE_DISCLOSURE = (
    "This queue is for research review only and offers no advice. It does not provide personalized investment guidance or trade instructions."
)
DEFAULT_AS_OF = "1970-01-01T00:00:00Z"
DOMAIN_ORDER: tuple[tuple[str, ResearchQueueCategory], ...] = (
    ("market", "market"),
    ("liquidity", "liquidity"),
    ("moneyFlow", "money_flow"),
    ("event", "event"),
    ("watchlist", "watchlist"),
    ("portfolio", "portfolio"),
    ("research", "research"),
    ("dataQuality", "data_quality"),
)
DEFAULT_TITLES: dict[ResearchQueueCategory, str] = {
    "market": "广度复核",
    "liquidity": "流动性观察",
    "money_flow": "资金流延续性观察",
    "event": "关键事件复核",
    "watchlist": "Watchlist 证据补齐",
    "portfolio": "组合集中度检查",
    "research": "轮动复核",
    "data_quality": "资料完整性检查",
}
DEFAULT_REASONS: dict[ResearchQueueCategory, str] = {
    "market": "市场观察信号需要复核后再继续研究。",
    "liquidity": "流动性线索需要维持观察，不形成交易动作。",
    "money_flow": "资金流线索需要延续性复核，仅保留研究队列。",
    "event": "事件线索需要二次复核，当前只保留研究观察。",
    "watchlist": "观察名单证据仍待补齐，先完成研究资料复核。",
    "portfolio": "组合暴露需要先复核，再决定后续研究顺序。",
    "research": "研究线索需要继续整理证据，当前只保留观察优先级。",
    "data_quality": "关键资料尚未完全接入，先补齐证据再继续研究。",
}
DEFAULT_REVIEW_MODULES: dict[ResearchQueueCategory, str] = {
    "market": "market_overview",
    "liquidity": "liquidity_monitor",
    "money_flow": "money_flow_review",
    "event": "event_review",
    "watchlist": "watchlist_review",
    "portfolio": "portfolio_review",
    "research": "research_review",
    "data_quality": "data_quality_review",
}
STATUS_RANK = {
    "high_attention": 0,
    "review": 1,
    "observe": 2,
    "no_evidence": 3,
    "unavailable": 4,
}
EVIDENCE_RANK = {
    "available": 0,
    "partial": 1,
    "no_evidence": 2,
    "unavailable": 3,
}
FORBIDDEN_TEXT_RE = re.compile(
    r"(buy|sell|add position|reduce position|clear position|stop[\s-]?loss|take[\s-]?profit|"
    r"target[\s-]?price|predicted[\s-]?return|ai recommendation|intelligent stock picking|"
    r"买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|预测收益|智能选股|"
    r"traceback|https?://|token|session|api[_-]?key|secret|reasoncode|trustlevel|sourcetype|fallback)",
    re.IGNORECASE,
)
SAFE_SYMBOL_RE = re.compile(r"^[A-Za-z0-9._-]{1,24}$")
SAFE_MODULE_RE = re.compile(r"^[a-z_]{3,40}$")


@dataclass(frozen=True)
class _PreparedItem:
    category: ResearchQueueCategory
    title: str
    reason: str
    review_module: str
    status: str
    evidence_status: str
    priority_hint: int | None
    related_symbols: tuple[str, ...]
    related_themes: tuple[str, ...]
    sequence: int
    proposed_id: str | None


class ResearchQueueService:
    """Build a reusable, read-only research queue contract without external IO."""

    def build_queue(
        self,
        inputs: ResearchQueueBuildInputs | Mapping[str, Any] | None = None,
    ) -> ResearchQueueResponse:
        build_inputs = self._coerce_inputs(inputs)
        prepared_items = self._prepare_items(build_inputs)
        ordered_items = sorted(prepared_items, key=self._sort_key)
        queue_items = [
            ResearchQueueItem(
                id=self._safe_identifier(item.category, item.proposed_id, index),
                priority=index,
                title=item.title,
                reason=item.reason,
                category=item.category,
                reviewModule=item.review_module,
                status=item.status,
                relatedSymbols=list(item.related_symbols),
                relatedThemes=list(item.related_themes),
                evidenceStatus=item.evidence_status,
                noAdviceDisclosure=NO_ADVICE_DISCLOSURE,
            )
            for index, item in enumerate(ordered_items, start=1)
        ]
        return ResearchQueueResponse(
            status=self._resolve_top_level_status(queue_items),
            asOf=self._resolve_as_of(build_inputs.asOf),
            items=queue_items,
            dataQuality=self._build_data_quality(queue_items),
            noAdviceDisclosure=NO_ADVICE_DISCLOSURE,
        )

    def _coerce_inputs(self, inputs: ResearchQueueBuildInputs | Mapping[str, Any] | None) -> ResearchQueueBuildInputs:
        if inputs is None:
            return ResearchQueueBuildInputs()
        if isinstance(inputs, ResearchQueueBuildInputs):
            return inputs
        return ResearchQueueBuildInputs.model_validate(inputs)

    def _prepare_items(self, build_inputs: ResearchQueueBuildInputs) -> list[_PreparedItem]:
        prepared: list[_PreparedItem] = []
        sequence = 0
        for field_name, category in DOMAIN_ORDER:
            seed_items: Sequence[ResearchQueueSeedItem] = getattr(build_inputs, field_name)
            for seed_item in seed_items:
                sequence += 1
                prepared.append(self._prepare_item(seed_item, category, sequence))
        return prepared

    def _prepare_item(
        self,
        item: ResearchQueueSeedItem,
        category: ResearchQueueCategory,
        sequence: int,
    ) -> _PreparedItem:
        return _PreparedItem(
            category=category,
            title=self._safe_text(item.title) or DEFAULT_TITLES[category],
            reason=self._safe_text(item.reason) or DEFAULT_REASONS[category],
            review_module=self._safe_review_module(category, item.reviewModule),
            status=item.status,
            evidence_status=item.evidenceStatus,
            priority_hint=item.priorityHint,
            related_symbols=self._safe_symbols(item.relatedSymbols),
            related_themes=self._safe_themes(item.relatedThemes),
            sequence=sequence,
            proposed_id=self._safe_identifier_text(item.id),
        )

    def _sort_key(self, item: _PreparedItem) -> tuple[int, int, int, int]:
        return (
            STATUS_RANK.get(item.status, 99),
            EVIDENCE_RANK.get(item.evidence_status, 99),
            item.priority_hint if item.priority_hint is not None else 999,
            item.sequence,
        )

    def _resolve_top_level_status(self, items: Sequence[ResearchQueueItem]) -> ResearchQueueTopLevelStatus:
        if not items:
            return "no_evidence"
        evidence_statuses = {item.evidenceStatus for item in items}
        if evidence_statuses == {"unavailable"}:
            return "unavailable"
        if evidence_statuses <= {"no_evidence", "unavailable"}:
            return "no_evidence"
        return "ready"

    def _build_data_quality(self, items: Sequence[ResearchQueueItem]) -> ResearchQueueDataQuality:
        available_domains = [
            item.category
            for item in items
            if item.evidenceStatus in {"available", "partial"}
        ]
        missing_domains = [
            item.category
            for item in items
            if item.evidenceStatus in {"no_evidence", "unavailable"}
        ]
        if not items:
            return ResearchQueueDataQuality(
                status="no_evidence",
                summary="首页研究队列输入尚未接入；当前返回安全占位，等待后续模块接线。",
                availableDomains=[],
                missingDomains=[category for _, category in DOMAIN_ORDER],
            )
        evidence_statuses = {item.evidenceStatus for item in items}
        if evidence_statuses == {"unavailable"}:
            status: ResearchQueueTopLevelStatus = "unavailable"
        elif evidence_statuses <= {"no_evidence", "unavailable"}:
            status = "no_evidence"
        elif "partial" in evidence_statuses or "no_evidence" in evidence_statuses or "unavailable" in evidence_statuses:
            status = "partial"
        else:
            status = "ready"
        if status == "ready":
            summary = "研究队列条目已生成，可按优先级继续复核。"
        elif status == "partial":
            summary = "研究队列已生成，但部分资料仍待补齐。"
        elif status == "unavailable":
            summary = "当前条目均不可用，需等待资料恢复后再继续研究。"
        else:
            summary = "当前条目缺少可用证据，先完成资料补齐。"
        return ResearchQueueDataQuality(
            status=status,
            summary=summary,
            availableDomains=self._dedupe_categories(available_domains),
            missingDomains=self._dedupe_categories(missing_domains),
        )

    def _dedupe_categories(self, categories: Sequence[ResearchQueueCategory]) -> list[ResearchQueueCategory]:
        seen: set[ResearchQueueCategory] = set()
        ordered: list[ResearchQueueCategory] = []
        for _, category in DOMAIN_ORDER:
            if category in categories and category not in seen:
                seen.add(category)
                ordered.append(category)
        return ordered

    def _resolve_as_of(self, value: str | None) -> str:
        text = str(value or "").strip()
        if text:
            return text
        return DEFAULT_AS_OF

    def _safe_text(self, value: str | None) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        if FORBIDDEN_TEXT_RE.search(text):
            return None
        return text[:160]

    def _safe_identifier_text(self, value: str | None) -> str | None:
        text = str(value or "").strip().lower()
        if not text:
            return None
        if FORBIDDEN_TEXT_RE.search(text):
            return None
        if not re.fullmatch(r"[a-z0-9._-]{1,48}", text):
            return None
        return text

    def _safe_identifier(self, category: ResearchQueueCategory, proposed: str | None, index: int) -> str:
        return proposed or f"{category}-{index}"

    def _safe_review_module(self, category: ResearchQueueCategory, proposed: str | None) -> str:
        text = str(proposed or "").strip().lower()
        if not text or FORBIDDEN_TEXT_RE.search(text) or not SAFE_MODULE_RE.fullmatch(text):
            return DEFAULT_REVIEW_MODULES[category]
        return text

    def _safe_symbols(self, values: Sequence[str]) -> tuple[str, ...]:
        safe_values: list[str] = []
        for value in values:
            text = str(value or "").strip().upper()
            if not text or FORBIDDEN_TEXT_RE.search(text):
                continue
            if not SAFE_SYMBOL_RE.fullmatch(text):
                continue
            safe_values.append(text)
        return tuple(safe_values[:6])

    def _safe_themes(self, values: Sequence[str]) -> tuple[str, ...]:
        safe_values: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if not text or FORBIDDEN_TEXT_RE.search(text):
                continue
            if len(text) > 32:
                continue
            safe_values.append(text)
        return tuple(safe_values[:6])


__all__ = ["NO_ADVICE_DISCLOSURE", "ResearchQueueService"]
