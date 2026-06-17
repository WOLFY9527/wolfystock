# -*- coding: utf-8 -*-
"""Standalone composer for turning evidence gaps into research checklist items."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


ResearchChecklistPayload = dict[str, list[dict[str, object]]]

_CHECKLIST_ID_PREFIX = "research-checklist"
_MAX_CHECKLIST_ITEMS = 12
_FORBIDDEN_TEXT_RE = re.compile(
    r"\b("
    r"buy|sell|hold|recommend(?:ation|ed)?|target|stop|position\s+sizing|"
    r"provider|fallback|raw|debug|traceback|reasoncode|trustlevel|sourcetype|"
    r"internal|diagnostics?|api[_-]?key|secret|token|cookie"
    r")\b|"
    r"https?://|/users/|"
    r"买入|卖出|持有|推荐|目标|止损|仓位",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[^a-z0-9]+")


_GAP_TEMPLATES: dict[str, dict[str, str]] = {
    "fresh_evidence": {
        "slug": "evidence-freshness",
        "evidenceGap": "Evidence freshness is not confirmed.",
        "whyItMatters": "Delayed or stale context can make the next review less reliable.",
        "suggestedResearchStep": "Confirm the latest review time and compare it with the current research window.",
        "priorityTier": "medium",
        "blockingStatus": "non_blocking",
    },
    "provider_timeout": {
        "slug": "evidence-availability",
        "evidenceGap": "Evidence availability needs review.",
        "whyItMatters": "The research context cannot support higher confidence until this evidence path is checked.",
        "suggestedResearchStep": "Check the relevant evidence path and confirm whether the gap is resolved.",
        "priorityTier": "high",
        "blockingStatus": "blocking",
    },
    "local_ohlcv_evidence": {
        "slug": "price-history-evidence",
        "evidenceGap": "Price-history evidence needs review.",
        "whyItMatters": "Price-history context helps confirm whether the research record is complete enough for follow-up.",
        "suggestedResearchStep": "Review price-history coverage and confirm the latest usable review window.",
        "priorityTier": "high",
        "blockingStatus": "blocking",
    },
    "scanner_score_evidence": {
        "slug": "scoring-evidence",
        "evidenceGap": "Scoring evidence needs review.",
        "whyItMatters": "A scoring context gap can limit how confidently the research queue can be sorted.",
        "suggestedResearchStep": "Review the scoring evidence summary and confirm the missing input category.",
        "priorityTier": "medium",
        "blockingStatus": "non_blocking",
    },
    "watchlist_research_context": {
        "slug": "research-context",
        "evidenceGap": "Research context needs review.",
        "whyItMatters": "A missing context note can make it unclear why the item belongs in the research queue.",
        "suggestedResearchStep": "Review the attached research context and confirm the reason for continued review.",
        "priorityTier": "medium",
        "blockingStatus": "non_blocking",
    },
    "source_confidence": {
        "slug": "evidence-confidence",
        "evidenceGap": "Evidence confidence context needs review.",
        "whyItMatters": "The research context cannot support higher confidence until this evidence path is checked.",
        "suggestedResearchStep": "Check the relevant evidence path and confirm whether the gap is resolved.",
        "priorityTier": "high",
        "blockingStatus": "blocking",
    },
}

_GENERIC_TEMPLATE = {
    "slug": "evidence-gap",
    "evidenceGap": "Evidence gap needs review.",
    "whyItMatters": "The research context cannot support higher confidence until this evidence path is checked.",
    "suggestedResearchStep": "Check the relevant evidence path and confirm whether the gap is resolved.",
    "priorityTier": "medium",
    "blockingStatus": "non_blocking",
}

_PRIORITY_RANK = {"high": 300, "medium": 200, "low": 100}
_BLOCKING_RANK = {"blocking": 20, "non_blocking": 0}
_PRIORITY_ALIASES = {
    "critical": "high",
    "attention": "high",
    "high": "high",
    "follow_up": "medium",
    "medium": "medium",
    "monitor": "low",
    "low": "low",
}
_BLOCKING_ALIASES = {
    "blocking": "blocking",
    "blocked": "blocking",
    "hard_blocking": "blocking",
    "required": "blocking",
    "non_blocking": "non_blocking",
    "nonblocking": "non_blocking",
    "follow_up": "non_blocking",
    "monitor": "non_blocking",
}


def compose_research_checklist(evidence_gaps: Any = None) -> ResearchChecklistPayload:
    """Build an observation-only research checklist from evidence gap inputs."""

    items: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    entries = _iter_gap_entries(evidence_gaps)

    for order, entry in enumerate(entries):
        token = _gap_token(entry)
        template = _GAP_TEMPLATES.get(token, _generic_template(token))
        item = _build_item(entry, template)
        checklist_id = str(item["checklistItemId"])
        if checklist_id in seen_ids:
            continue
        seen_ids.add(checklist_id)
        item["_order"] = order
        items.append(item)
        if len(items) >= _MAX_CHECKLIST_ITEMS:
            break

    sorted_items = sorted(
        items,
        key=lambda item: (
            -_PRIORITY_RANK.get(str(item["priorityTier"]), 0),
            -_BLOCKING_RANK.get(str(item["blockingStatus"]), 0),
            str(item["checklistItemId"]),
            int(item["_order"]),
        ),
    )
    return {
        "researchChecklist": [
            {
                "checklistItemId": item["checklistItemId"],
                "evidenceGap": item["evidenceGap"],
                "whyItMatters": item["whyItMatters"],
                "suggestedResearchStep": item["suggestedResearchStep"],
                "priorityTier": item["priorityTier"],
                "blockingStatus": item["blockingStatus"],
                "observationOnly": True,
            }
            for item in sorted_items
        ]
    }


def _iter_gap_entries(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return [value]


def _gap_token(entry: Any) -> str:
    if isinstance(entry, Mapping):
        for key in ("evidenceGap", "evidence_gap", "gap", "code", "reason", "key"):
            token = _normalize_token(entry.get(key))
            if token:
                return token
        return ""
    return _normalize_token(entry)


def _build_item(entry: Any, template: Mapping[str, str]) -> dict[str, object]:
    priority_tier = _priority_tier(entry, default=template["priorityTier"])
    blocking_status = _blocking_status(entry, default=template["blockingStatus"])
    return {
        "checklistItemId": f"{_CHECKLIST_ID_PREFIX}-{template['slug']}",
        "evidenceGap": template["evidenceGap"],
        "whyItMatters": _safe_text_from_entry(entry, "whyItMatters", fallback=template["whyItMatters"]),
        "suggestedResearchStep": _safe_text_from_entry(
            entry,
            "suggestedResearchStep",
            fallback=template["suggestedResearchStep"],
        ),
        "priorityTier": _max_priority(priority_tier, template["priorityTier"]),
        "blockingStatus": _max_blocking(blocking_status, template["blockingStatus"]),
        "observationOnly": True,
    }


def _safe_text_from_entry(entry: Any, key: str, *, fallback: str) -> str:
    if not isinstance(entry, Mapping):
        return fallback
    text = str(entry.get(key) or "").strip()
    if not text or _FORBIDDEN_TEXT_RE.search(text):
        return fallback
    return re.sub(r"\s+", " ", text)[:160]


def _priority_tier(entry: Any, *, default: str) -> str:
    if not isinstance(entry, Mapping):
        return default
    token = _normalize_token(entry.get("priorityTier") or entry.get("priority_tier"))
    return _PRIORITY_ALIASES.get(token, default)


def _blocking_status(entry: Any, *, default: str) -> str:
    if not isinstance(entry, Mapping):
        return default
    token = _normalize_token(entry.get("blockingStatus") or entry.get("blocking_status"))
    return _BLOCKING_ALIASES.get(token, default)


def _max_priority(left: str, right: str) -> str:
    return left if _PRIORITY_RANK.get(left, 0) >= _PRIORITY_RANK.get(right, 0) else right


def _max_blocking(left: str, right: str) -> str:
    return left if _BLOCKING_RANK.get(left, 0) >= _BLOCKING_RANK.get(right, 0) else right


def _generic_template(token: str) -> dict[str, str]:
    if not token:
        return dict(_GENERIC_TEMPLATE)
    slug = _TOKEN_RE.sub("-", token).strip("-")[:48] or "evidence-gap"
    if _FORBIDDEN_TEXT_RE.search(slug):
        slug = "evidence-gap"
    return {**_GENERIC_TEMPLATE, "slug": slug}


def _normalize_token(value: Any) -> str:
    return _TOKEN_RE.sub("_", str(value or "").strip().lower()).strip("_")


__all__ = ["compose_research_checklist"]
