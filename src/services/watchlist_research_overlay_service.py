# -*- coding: utf-8 -*-
"""Read-only research overlay projection for user watchlists."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib.parse import quote

from src.services.consumer_issue_labels import build_consumer_issues
from src.services.watchlist_service import WatchlistService


WATCHLIST_RESEARCH_OVERLAY_SCHEMA_VERSION = "watchlist_research_overlay_v1"
WATCHLIST_RESEARCH_OVERLAY_NO_ADVICE_DISCLOSURE = (
    "Read-only research overlay for observation and evidence review; it does not create alerts "
    "or execution instructions."
)
WATCHLIST_RESEARCH_PRIORITY_QUEUE_LIMIT = 5

_FORBIDDEN_TEXT_RE = re.compile(
    r"\b(buy|sell|hold|recommendation|target|stop|position sizing)\b|"
    r"买入|卖出|持有|目标价|止损|仓位",
    re.IGNORECASE,
)
_LARGE_MOVE_TEXT_RE = re.compile(r"\b(large|sharp|big)\s+(price\s+)?move\b", re.IGNORECASE)
_DEGRADED_QUALITY = {"stale_or_cached", "no_evidence", "unavailable", "symbol_unknown", "unsupported_market"}


class WatchlistResearchOverlayService:
    """Build an owner-scoped watchlist research overlay without mutating state."""

    def __init__(self, watchlist_service: Optional[Any] = None) -> None:
        self.watchlist_service = watchlist_service or WatchlistService()

    def build_overlay(self, *, owner_id: str) -> Dict[str, Any]:
        try:
            watchlist_items = self.watchlist_service.list_items(owner_id=owner_id)
        except Exception:
            return self._fail_closed("watchlist_unavailable")

        items = [self._project_item(item) for item in watchlist_items]
        aggregate_summary = self._build_aggregate_summary(items)
        raw_missing_evidence = self._raw_missing_evidence(items)
        missing_evidence = self._issue_messages(raw_missing_evidence)
        data_quality = self._build_data_quality(items, watchlist_unavailable=False)
        research_priority_queue = self._build_research_priority_queue(items)
        overlay_state = self._overlay_state(
            has_items=bool(items),
            data_quality_state=self._text(data_quality.get("state")) or "no_evidence",
        )
        consumer_issues = build_consumer_issues(
            raw_missing_evidence,
            data_quality,
            [item.get("_rawRiskFlags") for item in items],
            [item.get("_rawEvidenceGaps") for item in items],
        )
        for item in items:
            item.pop("_rawEvidenceGaps", None)
            item.pop("_rawRiskFlags", None)
        return {
            "schemaVersion": WATCHLIST_RESEARCH_OVERLAY_SCHEMA_VERSION,
            "overlayState": overlay_state,
            "researchSummary": self._overlay_summary(
                overlay_state=overlay_state,
                item_count=len(items),
                missing_evidence=missing_evidence,
            ),
            "items": items,
            "researchPriorityQueue": research_priority_queue,
            "aggregateSummary": aggregate_summary,
            "missingEvidence": missing_evidence,
            "evidenceGaps": missing_evidence,
            "riskObservations": self._issue_messages(
                [
                    raw_missing_evidence,
                    [item.get("_rawRiskFlags") for item in items],
                    data_quality.get("state"),
                ]
            ),
            "drilldownTargets": self._dedupe_links(
                target
                for item in items
                for target in list(item.get("drilldownTargets") or [])
            ),
            "dataQuality": data_quality,
            "consumerIssues": consumer_issues,
            "noAdviceDisclosure": WATCHLIST_RESEARCH_OVERLAY_NO_ADVICE_DISCLOSURE,
            "observationOnly": True,
            "decisionGrade": False,
        }

    @classmethod
    def _fail_closed(cls, reason: str) -> Dict[str, Any]:
        missing_evidence = cls._issue_messages([reason])
        return {
            "schemaVersion": WATCHLIST_RESEARCH_OVERLAY_SCHEMA_VERSION,
            "overlayState": "unavailable",
            "researchSummary": "Watchlist research data is unavailable, so this overlay remains read-only.",
            "items": [],
            "researchPriorityQueue": [],
            "aggregateSummary": cls._empty_aggregate_summary(),
            "missingEvidence": missing_evidence,
            "evidenceGaps": missing_evidence,
            "riskObservations": cls._issue_messages([reason]),
            "drilldownTargets": [],
            "dataQuality": {
                "state": "unavailable",
                "itemCount": 0,
                "readyCount": 0,
                "degradedCount": 0,
                "unavailableCount": 1,
                "missingEvidenceCount": 1,
                "failClosed": True,
                "consumerIssues": build_consumer_issues([reason]),
            },
            "consumerIssues": build_consumer_issues([reason]),
            "noAdviceDisclosure": WATCHLIST_RESEARCH_OVERLAY_NO_ADVICE_DISCLOSURE,
            "observationOnly": True,
            "decisionGrade": False,
        }

    @classmethod
    def _project_item(cls, item: Mapping[str, Any]) -> Dict[str, Any]:
        ticker = cls._text(item.get("symbol")) or ""
        intelligence = item.get("intelligence") if isinstance(item.get("intelligence"), Mapping) else {}
        scanner = intelligence.get("scanner") if isinstance(intelligence.get("scanner"), Mapping) else {}
        lineage = scanner.get("scanner_lineage_v1") if isinstance(scanner.get("scanner_lineage_v1"), Mapping) else {}
        freshness_state = cls._quality_state(item)
        raw_evidence_gaps = cls._evidence_gaps(item, scanner, lineage)
        raw_risk_flags = cls._risk_flags(freshness_state, raw_evidence_gaps, scanner)
        structure_state = cls._structure_state(item, freshness_state, raw_evidence_gaps)
        research_priority = cls._research_priority(structure_state, freshness_state, raw_evidence_gaps)
        why_watching = cls._first_safe_text(
            lineage.get("research_reason"),
            item.get("score_reason"),
            scanner.get("reason"),
            item.get("notes"),
        )
        why_on_radar = cls._first_safe_text(item.get("score_reason"), lineage.get("research_reason"))
        what_to_verify = cls._what_to_verify(lineage, raw_evidence_gaps)
        consumer_issues = build_consumer_issues(raw_evidence_gaps, raw_risk_flags, freshness_state)
        evidence_gaps = cls._issue_messages(raw_evidence_gaps)
        risk_flags = cls._risk_messages(raw_risk_flags)
        overlay_state = cls._item_overlay_state(freshness_state)

        return {
            "ticker": ticker,
            "overlayState": overlay_state,
            "researchSummary": cls._research_summary(
                overlay_state=overlay_state,
                why_watching=why_watching,
                consumer_issues=consumer_issues,
            ),
            "structureState": structure_state,
            "researchPriority": research_priority,
            "whyWatching": why_watching,
            "whyOnRadar": why_on_radar,
            "whatToVerify": what_to_verify,
            "riskFlags": risk_flags,
            "riskObservations": risk_flags,
            "evidenceGaps": evidence_gaps,
            "drilldownTargets": cls._drilldown_targets(ticker),
            "consumerIssues": consumer_issues,
            "freshness": {
                "state": freshness_state,
                "lastReviewedAt": cls._text(item.get("last_reviewed_at")),
                "ohlcvState": cls._ohlcv_state(scanner),
            },
            "themeOrSector": cls._theme_or_sector(item, scanner),
            "_rawEvidenceGaps": raw_evidence_gaps,
            "_rawRiskFlags": raw_risk_flags,
        }

    @classmethod
    def _quality_state(cls, item: Mapping[str, Any]) -> str:
        for key in ("data_quality", "research_status", "evidence_status", "symbol_status"):
            value = cls._text(item.get(key))
            if value:
                return value
        return "no_evidence"

    @classmethod
    def _evidence_gaps(
        cls,
        item: Mapping[str, Any],
        scanner: Mapping[str, Any],
        lineage: Mapping[str, Any],
    ) -> List[str]:
        gaps: List[str] = []
        freshness_state = cls._quality_state(item)
        if freshness_state in {"no_evidence", "symbol_unknown"}:
            gaps.extend(["watchlist_research_context", "local_ohlcv_evidence"])
        if freshness_state == "unavailable":
            gaps.append("watchlist_data_unavailable")
        if freshness_state == "stale_or_cached":
            gaps.append("fresh_evidence")
        if not isinstance(scanner.get("ohlcv_provenance"), Mapping):
            gaps.append("local_ohlcv_evidence")
        if scanner.get("score_confidence") is None and item.get("scanner_score") is None:
            gaps.append("scanner_score_evidence")
        if lineage and lineage.get("data_state") not in {"ready"}:
            gaps.append("score_grade_not_allowed")
        return cls._unique(gaps)

    @classmethod
    def _risk_flags(
        cls,
        freshness_state: str,
        evidence_gaps: Iterable[str],
        scanner: Mapping[str, Any],
    ) -> List[str]:
        flags: List[str] = []
        if freshness_state == "stale_or_cached":
            flags.append("cached_or_stale_evidence")
        if freshness_state in {"no_evidence", "symbol_unknown", "unavailable"}:
            flags.append("insufficient_research_evidence")
        if "local_ohlcv_evidence" in set(evidence_gaps):
            flags.append("missing_local_ohlcv")
        if cls._text(scanner.get("status")) == "data_failed":
            flags.append("scanner_data_unavailable")
        return cls._unique(flags)

    @staticmethod
    def _structure_state(item: Mapping[str, Any], freshness_state: str, evidence_gaps: Iterable[str]) -> str:
        if freshness_state == "unavailable":
            return "unavailable"
        if "local_ohlcv_evidence" in set(evidence_gaps) and item.get("scanner_score") is None:
            return "missing_evidence"
        if item.get("scanner_run_id") is not None or item.get("scanner_score") is not None:
            return "structure_changed"
        return "watchlist_only"

    @staticmethod
    def _research_priority(
        structure_state: str,
        freshness_state: str,
        evidence_gaps: Iterable[str],
    ) -> Optional[str]:
        gaps = set(evidence_gaps)
        if structure_state in {"unavailable", "missing_evidence"}:
            return None
        if "local_ohlcv_evidence" in gaps:
            return None
        if freshness_state == "ready":
            return "high"
        if freshness_state == "stale_or_cached":
            return "medium"
        return None

    @classmethod
    def _what_to_verify(cls, lineage: Mapping[str, Any], evidence_gaps: Iterable[str]) -> List[str]:
        checks: List[str] = []
        next_step = cls._safe_text(lineage.get("research_next_step"))
        if next_step:
            checks.append(next_step)
        for gap in evidence_gaps:
            if gap == "local_ohlcv_evidence":
                checks.append("Verify local OHLCV coverage.")
            elif gap == "fresh_evidence":
                checks.append("Verify freshness of stored evidence.")
            elif gap == "score_grade_not_allowed":
                checks.append("Verify score evidence quality before further research.")
            elif gap == "scanner_score_evidence":
                checks.append("Verify scanner score evidence.")
            elif gap == "watchlist_research_context":
                checks.append("Add or refresh research context.")
        return cls._unique_text(checks)

    @staticmethod
    def _item_overlay_state(freshness_state: str) -> str:
        if freshness_state == "ready":
            return "available"
        if freshness_state == "unavailable":
            return "unavailable"
        return "degraded"

    @classmethod
    def _theme_or_sector(cls, item: Mapping[str, Any], scanner: Mapping[str, Any]) -> Optional[str]:
        return cls._safe_text(item.get("theme_id")) or cls._safe_text(scanner.get("theme_label")) or cls._safe_text(scanner.get("theme"))

    @classmethod
    def _ohlcv_state(cls, scanner: Mapping[str, Any]) -> str:
        provenance = scanner.get("ohlcv_provenance")
        if not isinstance(provenance, Mapping):
            return "no_evidence"
        return cls._text(provenance.get("data_quality")) or "no_evidence"

    @classmethod
    def _build_aggregate_summary(cls, items: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        by_structure = Counter(cls._text(item.get("structureState")) or "unknown" for item in items)
        by_theme = Counter(cls._text(item.get("themeOrSector")) or "unclassified" for item in items)
        by_quality = Counter(cls._text((item.get("freshness") or {}).get("state")) or "unknown" for item in items)
        by_priority = Counter(cls._text(item.get("researchPriority")) or "unassigned" for item in items)
        return {
            "byStructureState": dict(sorted(by_structure.items())),
            "byThemeOrSector": dict(sorted(by_theme.items())),
            "byEvidenceQuality": dict(sorted(by_quality.items())),
            "byResearchPriority": dict(sorted(by_priority.items())),
        }

    @staticmethod
    def _empty_aggregate_summary() -> Dict[str, Dict[str, int]]:
        return {
            "byStructureState": {},
            "byThemeOrSector": {},
            "byEvidenceQuality": {},
            "byResearchPriority": {},
        }

    @classmethod
    def _raw_missing_evidence(cls, items: List[Dict[str, Any]]) -> List[str]:
        gaps: List[str] = []
        for item in items:
            gaps.extend(str(gap) for gap in item.get("_rawEvidenceGaps") or [])
        return cls._unique(gaps)

    @classmethod
    def _build_data_quality(cls, items: List[Dict[str, Any]], *, watchlist_unavailable: bool) -> Dict[str, Any]:
        if watchlist_unavailable:
            state = "unavailable"
        elif not items:
            state = "no_evidence"
        else:
            states = [cls._text((item.get("freshness") or {}).get("state")) or "no_evidence" for item in items]
            if all(state == "ready" for state in states):
                state = "ready"
            elif any(state == "unavailable" for state in states):
                state = "unavailable"
            else:
                state = "partial" if any(value in _DEGRADED_QUALITY for value in states) else "ready"
        ready_count = sum(1 for item in items if (item.get("freshness") or {}).get("state") == "ready")
        unavailable_count = sum(1 for item in items if (item.get("freshness") or {}).get("state") == "unavailable")
        raw_missing_evidence = cls._raw_missing_evidence(items)
        missing_evidence_count = len(raw_missing_evidence)
        return {
            "state": state,
            "itemCount": len(items),
            "readyCount": ready_count,
            "degradedCount": max(len(items) - ready_count, 0),
            "unavailableCount": unavailable_count,
            "missingEvidenceCount": missing_evidence_count,
            "failClosed": state != "ready" or missing_evidence_count > 0,
            "consumerIssues": build_consumer_issues(raw_missing_evidence, state),
        }

    @classmethod
    def _build_research_priority_queue(cls, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        queue = [entry for item in items if (entry := cls._research_priority_queue_entry(item))]
        return [
            entry
            for _rank, entry in sorted(
                enumerate(queue),
                key=lambda pair: (
                    -cls._priority_score(pair[1]),
                    cls._text(pair[1].get("symbol")) or "",
                    pair[0],
                ),
            )
        ][:WATCHLIST_RESEARCH_PRIORITY_QUEUE_LIMIT]

    @classmethod
    def _research_priority_queue_entry(cls, item: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        symbol = cls._text(item.get("ticker"))
        if not symbol:
            return None
        freshness = item.get("freshness") if isinstance(item.get("freshness"), Mapping) else {}
        freshness_state = cls._text(freshness.get("state")) or "no_evidence"
        raw_evidence_gaps = [str(gap) for gap in item.get("_rawEvidenceGaps") or []]
        raw_risk_flags = [str(flag) for flag in item.get("_rawRiskFlags") or []]
        missing_evidence = cls._priority_missing_evidence_labels(raw_evidence_gaps)
        large_move_observed = cls._large_move_observed(item)
        priority_tier = cls._priority_tier(
            freshness_state=freshness_state,
            raw_evidence_gaps=raw_evidence_gaps,
            raw_risk_flags=raw_risk_flags,
            large_move_observed=large_move_observed,
        )
        return {
            "symbol": symbol,
            "priorityTier": priority_tier,
            "priorityReasonSafeLabel": cls._priority_reason_safe_label(
                priority_tier=priority_tier,
                freshness_state=freshness_state,
                missing_evidence=missing_evidence,
                large_move_observed=large_move_observed,
            ),
            "evidenceAge": {
                "state": freshness_state,
                "lastReviewedAt": cls._text(freshness.get("lastReviewedAt")),
            },
            "missingEvidence": missing_evidence,
            "suggestedResearchPath": cls._suggested_research_path(item, missing_evidence),
            "observationOnly": True,
        }

    @staticmethod
    def _priority_tier(
        *,
        freshness_state: str,
        raw_evidence_gaps: Iterable[str],
        raw_risk_flags: Iterable[str],
        large_move_observed: bool,
    ) -> str:
        gaps = set(raw_evidence_gaps)
        flags = set(raw_risk_flags)
        if freshness_state in {"no_evidence", "symbol_unknown", "unavailable", "unsupported_market"}:
            return "attention"
        if gaps.intersection({"watchlist_research_context", "local_ohlcv_evidence", "scanner_score_evidence"}):
            return "attention"
        if freshness_state == "stale_or_cached" or "fresh_evidence" in gaps:
            return "follow_up"
        if large_move_observed:
            return "follow_up"
        if flags:
            return "follow_up"
        return "monitor"

    @staticmethod
    def _priority_score(entry: Mapping[str, Any]) -> int:
        tier_score = {
            "attention": 300,
            "follow_up": 200,
            "monitor": 100,
        }.get(str(entry.get("priorityTier") or ""), 0)
        missing_count = len(entry.get("missingEvidence") or [])
        state = str((entry.get("evidenceAge") or {}).get("state") or "")
        stale_bonus = 20 if state == "stale_or_cached" else 0
        return tier_score + min(missing_count, 5) * 10 + stale_bonus

    @classmethod
    def _priority_reason_safe_label(
        cls,
        *,
        priority_tier: str,
        freshness_state: str,
        missing_evidence: List[str],
        large_move_observed: bool,
    ) -> str:
        if priority_tier == "attention":
            if missing_evidence:
                return "Missing evidence needs review."
            if freshness_state == "unavailable":
                return "Research context is temporarily unavailable."
            return "Research context needs attention."
        if priority_tier == "follow_up":
            if large_move_observed:
                return "Large move needs evidence review."
            if freshness_state == "stale_or_cached":
                return "Evidence needs refresh before confidence can improve."
            return "Research context has follow-up flags."
        return "Research context is ready for follow-up."

    @classmethod
    def _large_move_observed(cls, item: Mapping[str, Any]) -> bool:
        values = [
            item.get("researchSummary"),
            item.get("whyWatching"),
            item.get("whyOnRadar"),
            *list(item.get("whatToVerify") or []),
        ]
        return any(_LARGE_MOVE_TEXT_RE.search(text) for value in values if (text := cls._safe_text(value)))

    @classmethod
    def _priority_missing_evidence_labels(cls, raw_evidence_gaps: Iterable[str]) -> List[str]:
        labels: List[str] = []
        gaps = set(raw_evidence_gaps)
        if "watchlist_research_context" in gaps:
            labels.append("Research context")
        if "local_ohlcv_evidence" in gaps:
            labels.append("Price-history evidence")
        if "scanner_score_evidence" in gaps:
            labels.append("Scanner score evidence")
        if "fresh_evidence" in gaps:
            labels.append("Cached or delayed evidence")
        if "score_grade_not_allowed" in gaps:
            labels.append("Score-grade evidence")
        if "watchlist_data_unavailable" in gaps:
            labels.append("Watchlist research data")
        return cls._unique_text(labels)

    @classmethod
    def _suggested_research_path(
        cls,
        item: Mapping[str, Any],
        missing_evidence: List[str],
    ) -> List[Dict[str, str]]:
        symbol = cls._text(item.get("ticker")) or ""
        path: List[Dict[str, str]] = []
        if symbol:
            path.extend(cls._drilldown_targets(symbol))
        for label in missing_evidence[:2]:
            if label == "Price-history evidence":
                path.append(
                    {
                        "label": "Evidence Coverage",
                        "route": f"/stocks/{quote(symbol, safe='')}/structure-decision" if symbol else "/watchlist",
                        "section": "evidenceCoverage",
                        "reason": "Review price-history coverage before follow-up research.",
                    }
                )
            elif label == "Research context":
                path.append(
                    {
                        "label": "Watchlist Context",
                        "route": "/watchlist",
                        "section": "researchContext",
                        "reason": "Review why this symbol is on the watchlist.",
                    }
                )
        what_to_verify = next(
            (
                cls._safe_text(value)
                for value in list(item.get("whatToVerify") or [])
                if cls._safe_text(value)
            ),
            None,
        )
        if what_to_verify and symbol:
            path.append(
                {
                    "label": "Research Check",
                    "route": f"/stocks/{quote(symbol, safe='')}/structure-decision",
                    "section": "researchChecklist",
                    "reason": what_to_verify,
                }
            )
        return cls._dedupe_links(path)[:3]

    @classmethod
    def _overlay_state(cls, *, has_items: bool, data_quality_state: str) -> str:
        if not has_items:
            return "available"
        if data_quality_state == "ready":
            return "available"
        if data_quality_state == "unavailable":
            return "unavailable"
        return "degraded"

    @classmethod
    def _overlay_summary(
        cls,
        *,
        overlay_state: str,
        item_count: int,
        missing_evidence: List[str],
    ) -> str:
        if overlay_state == "unavailable":
            return "Watchlist research data is unavailable, so this overlay stays read-only."
        if item_count == 0:
            return "No saved watchlist symbols need follow-up research yet."
        if overlay_state == "degraded":
            if missing_evidence:
                return f"{item_count} watchlist entries remain observation-only because supporting evidence is incomplete."
            return "Watchlist entries remain observation-only until supporting evidence is refreshed."
        return f"{item_count} watchlist entries are ready for follow-up research review."

    @classmethod
    def _research_summary(
        cls,
        *,
        overlay_state: str,
        why_watching: Optional[str],
        consumer_issues: List[Dict[str, str]],
    ) -> str:
        if why_watching:
            return why_watching
        if overlay_state == "unavailable":
            return "This watchlist entry is unavailable for follow-up research right now."
        issue_message = next((issue.get("message") for issue in consumer_issues if cls._safe_text(issue.get("message"))), None)
        if issue_message:
            return str(issue_message)
        if overlay_state == "degraded":
            return "Supporting evidence still needs review before confidence can improve."
        return "Current watchlist evidence supports follow-up research review."

    @classmethod
    def _issue_messages(cls, values: Any) -> List[str]:
        return cls._unique_text(
            issue.get("message")
            for issue in build_consumer_issues(values)
            if cls._safe_text(issue.get("message"))
        )

    @classmethod
    def _risk_messages(cls, raw_flags: Iterable[str]) -> List[str]:
        return cls._issue_messages(list(raw_flags))

    @staticmethod
    def _drilldown_targets(ticker: str) -> List[Dict[str, str]]:
        symbol = str(ticker or "").strip()
        if not symbol:
            return []
        return [
            {
                "label": "Stock Structure",
                "route": f"/stocks/{quote(symbol, safe='')}/structure-decision",
                "section": "watchlistResearchOverlay",
                "reason": "Open symbol structure detail.",
            }
        ]

    @classmethod
    def _dedupe_links(cls, values: Iterable[Mapping[str, str]]) -> List[Dict[str, str]]:
        result: List[Dict[str, str]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for item in values:
            label = cls._text(item.get("label"))
            route = cls._text(item.get("route"))
            section = cls._text(item.get("section"))
            reason = cls._text(item.get("reason"))
            if not label or not route or not section:
                continue
            key = (label, route, section, reason or "")
            if key in seen:
                continue
            seen.add(key)
            result.append(
                {"label": label, "route": route, "section": section, "reason": reason or ""}
            )
        return result

    @classmethod
    def _first_safe_text(cls, *values: Any) -> Optional[str]:
        for value in values:
            safe = cls._safe_text(value)
            if safe:
                return safe
        return None

    @classmethod
    def _safe_text(cls, value: Any) -> Optional[str]:
        text = cls._text(value)
        if not text or _FORBIDDEN_TEXT_RE.search(text):
            return None
        return text

    @staticmethod
    def _text(value: Any) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _unique(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        result: List[str] = []
        for value in values:
            normalized = str(value or "").strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result

    @classmethod
    def _unique_text(cls, values: Iterable[str]) -> List[str]:
        return [value for value in cls._unique(values) if not _FORBIDDEN_TEXT_RE.search(value)]
