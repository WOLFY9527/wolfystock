# -*- coding: utf-8 -*-
"""Read-only incident timeline aggregation for Admin observability."""

from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any, Dict, Iterable, List, Optional

from src.storage import get_db
from src.utils.security import sanitize_message


_DEGRADED_STATUSES = {
    "failed",
    "failure",
    "error",
    "partial",
    "partial_success",
    "skipped",
    "timeout",
    "timed_out",
    "timeout_unknown",
    "switched_to_fallback",
}
_SUCCESS_STATUSES = {"success", "succeeded", "completed", "ok"}
_SENSITIVE_LABELS = ("api_key", "apikey", "raw_prompt", "prompt", "token", "secret", "password")


class AdminIncidentTimelineService:
    """Build a sanitized support timeline from existing read models only."""

    def __init__(self) -> None:
        self.db = get_db()

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _safe_text(cls, value: Any, *, limit: int = 240) -> Optional[str]:
        text = sanitize_message(cls._text(value))[:limit].strip()
        if not text:
            return None
        lowered = text.lower()
        for label in _SENSITIVE_LABELS:
            lowered = lowered.replace(label, "credential")
        if lowered != text.lower():
            text = re.sub("|".join(re.escape(label) for label in _SENSITIVE_LABELS), "credential", text, flags=re.IGNORECASE)
        return text or None

    @classmethod
    def _normalize(cls, value: Any) -> str:
        text = cls._text(value).lower().replace("-", "_").replace(".", "_").replace(" ", "_")
        return re.sub(r"[^a-z0-9_:/]+", "_", text).strip("_")

    @classmethod
    def _compact_identifier(cls, value: Any, *, limit: int = 128) -> Optional[str]:
        text = sanitize_message(cls._text(value))[:limit].strip()
        if not text:
            return None
        return text

    @classmethod
    def _parse_since(cls, value: Optional[str]) -> Optional[datetime]:
        text = cls._text(value).lower()
        if not text:
            return None
        try:
            if text.endswith("m") and text[:-1].isdigit():
                return datetime.now() - timedelta(minutes=int(text[:-1]))
            if text.endswith("h") and text[:-1].isdigit():
                return datetime.now() - timedelta(hours=int(text[:-1]))
            if text.endswith("d") and text[:-1].isdigit():
                return datetime.now() - timedelta(days=int(text[:-1]))
            return datetime.fromisoformat(text.replace("z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None

    @classmethod
    def _parse_iso(cls, value: Any) -> Optional[datetime]:
        text = cls._text(value)
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None

    def build_timeline(
        self,
        *,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        query_id: Optional[str] = None,
        symbol: Optional[str] = None,
        since: Optional[str] = "24h",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        effective_date_from = date_from or self._parse_since(since)
        bounded_limit = max(1, min(int(limit or 100), 200))
        details = self._matching_session_details(
            session_id=session_id,
            request_id=request_id,
            query_id=query_id,
            symbol=symbol,
            date_from=effective_date_from,
            date_to=date_to,
            limit=max(200, min(bounded_limit * 5, 1000)),
        )

        items: List[Dict[str, Any]] = []
        for detail in details:
            business_item = self._business_event_item(detail)
            if business_item:
                items.append(business_item)
            for event in detail.get("events") if isinstance(detail.get("events"), list) else []:
                event_item = self._event_item(detail, event)
                if event_item:
                    items.append(event_item)

        items.sort(key=lambda item: (self._text(item.get("timestamp")), self._text(item.get("id"))))
        trimmed = items[:bounded_limit]
        return {
            "lookup": {
                "session_id": self._compact_identifier(session_id),
                "request_id": self._compact_identifier(request_id),
                "query_id": self._compact_identifier(query_id),
                "symbol": self._compact_identifier(symbol, limit=32),
                "date_from": effective_date_from.isoformat() if effective_date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "limit": bounded_limit,
            },
            "total": len(items),
            "items": trimmed,
            "hooks": self._hooks(trimmed, details, date_from=effective_date_from, date_to=date_to),
            "empty_state": {
                "reason": "no_matching_read_models" if not items else None,
                "read_only": True,
                "message": "No matching execution logs or read-model hints were found for the requested lookup." if not items else None,
            },
            "metadata": {
                "read_only": True,
                "data_sources": [
                    "execution_log_sessions",
                    "execution_log_events",
                    "provider_circuit_states",
                    "llm_cost_ledger_summary",
                ],
                "redaction": [
                    "credentials_omitted",
                    "prompts_omitted",
                    "provider_payloads_omitted",
                    "request_response_bodies_omitted",
                ],
                "mutation_paths": [],
            },
        }

    def _matching_session_details(
        self,
        *,
        session_id: Optional[str],
        request_id: Optional[str],
        query_id: Optional[str],
        symbol: Optional[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        limit: int,
    ) -> List[Dict[str, Any]]:
        exact_session_id = self._text(session_id)
        if exact_session_id:
            detail = self.db.get_execution_log_session_detail(exact_session_id) or {}
            candidates = [detail] if detail else []
        else:
            rows, _ = self.db.list_execution_log_sessions(
                stock_code=self._text(symbol).upper() or None,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=0,
            )
            session_ids = [self._text(row.get("session_id")) for row in rows if isinstance(row, dict) and self._text(row.get("session_id"))]
            candidates = list((self.db.list_execution_log_session_details(session_ids) or {}).values())

        matched: List[Dict[str, Any]] = []
        for detail in candidates:
            if not isinstance(detail, dict):
                continue
            if date_from or date_to:
                started = self._parse_iso(detail.get("started_at"))
                if date_from and started and started < date_from:
                    continue
                if date_to and started and started > date_to:
                    continue
            if query_id and self._text(detail.get("query_id")) != self._text(query_id):
                continue
            if symbol and self._normalize(symbol) not in {self._normalize(value) for value in self._symbol_values(detail)}:
                continue
            if request_id and self._text(request_id) not in self._request_values(detail):
                continue
            matched.append(detail)
        return matched

    def _business_event_item(self, detail: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
        business = summary.get("business_event") if isinstance(summary.get("business_event"), dict) else {}
        session_id = self._text(detail.get("session_id"))
        if not session_id:
            return None
        business_id = self._text(business.get("id")) or session_id
        started_at = self._text(business.get("startedAt") or detail.get("started_at"))
        event_name = self._safe_text(business.get("event") or detail.get("name") or detail.get("task_id"), limit=120) or "Execution session"
        return {
            "id": f"session:{session_id}",
            "kind": "business_event",
            "timestamp": started_at or self._text(detail.get("ended_at")) or None,
            "status": self._normalize(business.get("status") or detail.get("overall_status")) or "unknown",
            "severity": self._severity(business.get("status") or detail.get("overall_status")),
            "title": event_name,
            "summary": self._safe_text(business.get("summary") or detail.get("name") or detail.get("task_id")),
            "session_id": session_id,
            "business_event_id": business_id,
            "query_id": self._compact_identifier(detail.get("query_id")),
            "request_id": self._first_request_id(detail),
            "symbol": self._first_symbol(detail),
            "phase": None,
            "category": self._safe_text(business.get("category"), limit=80),
            "provider": None,
            "model": None,
            "channel": None,
            "reason_code": self._safe_text(business.get("reason"), limit=80),
            "navigation": self._navigation(detail, business_event_id=business_id),
        }

    def _event_item(self, detail: Dict[str, Any], event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(event, dict):
            return None
        event_detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
        kind = self._event_kind(event, event_detail)
        if kind is None:
            return None
        status = self._normalize(event_detail.get("status") or event.get("status")) or "unknown"
        timeline_kinds = {"data_quality", "provider_cache_circuit", "llm_cost", "notification", "evidence_posture"}
        if kind not in timeline_kinds and status in _SUCCESS_STATUSES:
            return None
        session_id = self._text(detail.get("session_id"))
        business_id = self._business_event_id(detail)
        provider = self._safe_text(event_detail.get("provider") or event_detail.get("data_provider") or event.get("target"), limit=80)
        model = self._safe_text(event_detail.get("model") or (event.get("target") if kind == "llm_cost" else None), limit=120)
        channel = self._safe_text(event_detail.get("channel") or (provider if kind == "notification" else None), limit=80)
        reason = self._safe_text(
            event_detail.get("reason")
            or event_detail.get("errorType")
            or event_detail.get("error_type")
            or event.get("error_code"),
            limit=80,
        )
        label = self._safe_text(event_detail.get("label") or event_detail.get("name") or event.get("step"), limit=120)
        message = self._safe_text(
            event_detail.get("errorMessage")
            or event_detail.get("message")
            or event.get("message")
            or reason,
            limit=260,
        )
        return {
            "id": f"event:{session_id}:{self._text(event.get('id')) or self._text(event.get('event_at'))}",
            "kind": kind,
            "timestamp": self._text(event_detail.get("finishedAt") or event_detail.get("startedAt") or event.get("event_at")) or None,
            "status": status,
            "severity": self._severity(status),
            "title": label or kind,
            "summary": message,
            "session_id": session_id or None,
            "business_event_id": business_id,
            "query_id": self._compact_identifier(detail.get("query_id")),
            "request_id": self._first_request_id(detail),
            "symbol": self._first_symbol(detail),
            "phase": self._safe_text(event.get("phase"), limit=80),
            "category": self._safe_text(event_detail.get("category") or event_detail.get("stepCategory") or event.get("phase"), limit=80),
            "provider": provider,
            "model": model,
            "channel": channel,
            "reason_code": reason,
            "navigation": self._navigation(detail, business_event_id=business_id, event_id=self._text(event.get("id")) or None),
        }

    def _event_kind(self, event: Dict[str, Any], detail: Dict[str, Any]) -> Optional[str]:
        phase = self._normalize(event.get("phase"))
        category = self._normalize(detail.get("category") or detail.get("stepCategory"))
        name = self._normalize(detail.get("name") or event.get("step") or detail.get("event_name"))
        status = self._normalize(detail.get("status") or event.get("status"))
        if name in {"execution_started", "execution_finished"}:
            return None
        text = " ".join(
            part
            for part in (
                phase,
                category,
                name,
                self._normalize(detail.get("reason")),
                self._normalize(event.get("error_code")),
                self._normalize(detail.get("freshness_state") or detail.get("freshness_status") or detail.get("cache_state")),
            )
            if part
        )
        if "notification" in text or "channel" in text:
            return "notification"
        if phase.startswith("ai") or category in {"ai", "ai_model", "llm"} or detail.get("model"):
            return "llm_cost"
        if "evidence" in text:
            return "evidence_posture"
        if "circuit" in text or "cache" in text or "provider_quota" in text:
            return "provider_cache_circuit"
        if (
            phase.startswith("data")
            or category in {"data", "data_source", "market"}
            or any(token in text for token in ("quote", "history", "fundamental", "news", "freshness", "stale", "fallback", "missing"))
        ):
            return "data_quality"
        if status in _DEGRADED_STATUSES and (detail.get("provider") or event.get("target")):
            return "provider_cache_circuit"
        return None

    def _hooks(
        self,
        items: List[Dict[str, Any]],
        details: List[Dict[str, Any]],
        *,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> List[Dict[str, Any]]:
        data_items = [item for item in items if item.get("kind") == "data_quality"]
        provider_items = [
            item
            for item in items
            if item.get("kind") in {"data_quality", "provider_cache_circuit"} and item.get("provider")
        ]
        llm_items = [item for item in items if item.get("kind") == "llm_cost"]
        notification_items = [item for item in items if item.get("kind") == "notification"]
        evidence_items = [item for item in items if item.get("kind") == "evidence_posture"]
        circuit_state = self._current_circuit_hint(provider_items)
        ledger = self._ledger_summary(date_from=date_from, date_to=date_to)

        return [
            self._hook(
                kind="data_quality",
                items=data_items,
                status="degraded" if data_items else "not_observed",
                summary=(
                    f"{len(data_items)} degraded data-quality signals matched this lookup."
                    if data_items
                    else "No degraded data-quality signal matched this lookup."
                ),
            ),
            self._hook(
                kind="provider_cache_circuit",
                items=provider_items,
                status=circuit_state.get("status") or ("degraded" if provider_items else "not_observed"),
                summary=circuit_state.get("summary") or (
                    f"{len(provider_items)} provider/cache/circuit hints matched this lookup."
                    if provider_items
                    else "No provider/cache/circuit read-model hint matched this lookup."
                ),
                provider=circuit_state.get("provider") or self._first_item_value(provider_items, "provider"),
                reason_code=circuit_state.get("reason_code") or self._first_item_value(provider_items, "reason_code"),
            ),
            self._hook(
                kind="llm_cost",
                items=llm_items,
                status="available" if llm_items or int((ledger.get("total") or {}).get("calls") or 0) else "placeholder",
                summary=self._llm_summary(llm_items, ledger),
                provider=self._first_item_value(llm_items, "provider"),
                model=self._first_item_value(llm_items, "model"),
            ),
            self._hook(
                kind="notification",
                items=notification_items,
                status="available" if notification_items else "placeholder",
                summary=(
                    f"{len(notification_items)} notification posture signals matched this lookup."
                    if notification_items
                    else "Notification posture placeholder only; no matching notification read model was found."
                ),
                channel=self._first_item_value(notification_items, "channel"),
                reason_code=self._first_item_value(notification_items, "reason_code"),
            ),
            self._hook(
                kind="evidence_posture",
                items=evidence_items,
                status="available" if evidence_items else "placeholder",
                summary=(
                    f"{len(evidence_items)} evidence posture signals matched this lookup."
                    if evidence_items
                    else "Evidence posture placeholder only; no dedicated evidence read model was found."
                ),
            ),
        ]

    def _hook(
        self,
        *,
        kind: str,
        items: List[Dict[str, Any]],
        status: str,
        summary: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        channel: Optional[str] = None,
        reason_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "kind": kind,
            "status": status,
            "summary": summary,
            "count": len(items),
            "latest_at": max((self._text(item.get("timestamp")) for item in items), default=None) or None,
            "provider": provider,
            "model": model,
            "channel": channel,
            "reason_code": reason_code,
            "sample_session_ids": self._sample_values(items, "session_id"),
            "sample_business_event_ids": self._sample_values(items, "business_event_id"),
        }

    def _current_circuit_hint(self, items: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
        providers = [provider for provider in self._sample_values(items, "provider", limit=3) if provider]
        for provider in providers:
            reader = getattr(self.db, "list_current_provider_circuits", None)
            if not callable(reader):
                continue
            try:
                states = reader(provider=provider, limit=5)
            except Exception:
                continue
            for state in states or []:
                state_name = self._normalize((state or {}).get("state")) or "unknown"
                if state_name and state_name != "closed":
                    return {
                        "status": "degraded",
                        "provider": provider,
                        "reason_code": self._safe_text((state or {}).get("reason_bucket"), limit=80),
                        "summary": f"Provider circuit read model reports {provider} as {state_name}.",
                    }
        if providers:
            return {"status": "degraded", "provider": providers[0], "reason_code": None, "summary": None}
        return {}

    def _ledger_summary(self, *, date_from: Optional[datetime], date_to: Optional[datetime]) -> Dict[str, Any]:
        reader = getattr(self.db, "get_llm_cost_ledger_summary", None)
        if not callable(reader):
            return {"total": {"calls": 0}}
        now = datetime.now()
        try:
            return reader(
                from_dt=date_from or (now - timedelta(hours=24)),
                to_dt=date_to or now,
                limit=10,
            )
        except Exception:
            return {"total": {"calls": 0}}

    def _llm_summary(self, items: List[Dict[str, Any]], ledger: Dict[str, Any]) -> str:
        ledger_total = ledger.get("total") if isinstance(ledger.get("total"), dict) else {}
        calls = int(ledger_total.get("calls") or 0)
        cost = self._text(ledger_total.get("total_cost_usd"))
        if calls:
            return f"LLM/cost ledger hook observed {calls} calls in the selected window with total_cost_usd={cost or '0'}."
        if items:
            return f"{len(items)} LLM/model timeline signals matched this lookup; no cost ledger row matched the window."
        return "LLM/cost summary placeholder only; no matching ledger row or model event was found."

    @staticmethod
    def _sample_values(items: Iterable[Dict[str, Any]], key: str, *, limit: int = 5) -> List[str]:
        values: List[str] = []
        seen: set[str] = set()
        for item in items:
            value = str(item.get(key) or "").strip()
            if not value or value in seen:
                continue
            values.append(value)
            seen.add(value)
            if len(values) >= limit:
                break
        return values

    @staticmethod
    def _first_item_value(items: List[Dict[str, Any]], key: str) -> Optional[str]:
        for item in items:
            value = item.get(key)
            if value not in (None, ""):
                return str(value)
        return None

    def _navigation(self, detail: Dict[str, Any], *, business_event_id: Optional[str], event_id: Optional[str] = None) -> Dict[str, Any]:
        nav = {
            "session_id": self._compact_identifier(detail.get("session_id")),
            "business_event_id": self._compact_identifier(business_event_id),
            "query_id": self._compact_identifier(detail.get("query_id")),
            "analysis_history_id": detail.get("analysis_history_id"),
            "event_id": self._compact_identifier(event_id),
        }
        return {key: value for key, value in nav.items() if value not in (None, "")}

    @classmethod
    def _severity(cls, status: Any) -> str:
        token = cls._normalize(status)
        if token in {"failed", "failure", "error", "critical"}:
            return "error"
        if token in {"partial", "partial_success", "warning", "timeout", "timed_out", "skipped"}:
            return "warning"
        return "info"

    def _request_values(self, detail: Dict[str, Any]) -> set[str]:
        values = set()
        summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
        business = summary.get("business_event") if isinstance(summary.get("business_event"), dict) else {}
        meta = summary.get("meta") if isinstance(summary.get("meta"), dict) else {}
        for value in (business.get("requestId"), business.get("request_id"), meta.get("actor_request_id")):
            text = self._text(value)
            if text:
                values.add(text)
        for event in detail.get("events") if isinstance(detail.get("events"), list) else []:
            event_detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
            for value in (event_detail.get("request_id"), event_detail.get("requestId")):
                text = self._text(value)
                if text:
                    values.add(text)
        return values

    def _symbol_values(self, detail: Dict[str, Any]) -> set[str]:
        values = set()
        summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
        business = summary.get("business_event") if isinstance(summary.get("business_event"), dict) else {}
        for value in (business.get("symbol"), business.get("subject"), detail.get("code")):
            text = self._text(value)
            if text:
                values.add(text)
        return values

    def _first_request_id(self, detail: Dict[str, Any]) -> Optional[str]:
        return next(iter(sorted(self._request_values(detail))), None)

    def _first_symbol(self, detail: Dict[str, Any]) -> Optional[str]:
        return next(iter(sorted(self._symbol_values(detail))), None)

    def _business_event_id(self, detail: Dict[str, Any]) -> Optional[str]:
        summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
        business = summary.get("business_event") if isinstance(summary.get("business_event"), dict) else {}
        return self._text(business.get("id")) or self._text(detail.get("session_id")) or None


__all__ = ["AdminIncidentTimelineService"]
