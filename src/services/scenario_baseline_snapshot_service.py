# -*- coding: utf-8 -*-
"""Consumer-safe Scenario baseline snapshot service seam.

The service is deliberately pure: it normalizes caller-supplied snapshot
metadata and exposes missing/degraded category state without reading providers,
credentials, cache, or database state.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


SCENARIO_BASELINE_SNAPSHOT_SCHEMA_VERSION = "scenario_baseline_snapshot.v1"
SCENARIO_BASELINE_NO_ADVICE_DISCLOSURE = "Research planning only; not a personalized decision basis."

_CATEGORY_ORDER = (
    "market_price",
    "market_regime",
    "volatility",
    "market_flow",
    "options_greeks",
)
_CATEGORY_ALIASES = {
    "price": "market_price",
    "marketprice": "market_price",
    "market_price": "market_price",
    "quote": "market_price",
    "baselineprice": "market_price",
    "regime": "market_regime",
    "marketregime": "market_regime",
    "market_regime": "market_regime",
    "volatility": "volatility",
    "vol": "volatility",
    "flow": "market_flow",
    "marketflow": "market_flow",
    "market_flow": "market_flow",
    "positioning": "market_flow",
    "flowpositioning": "market_flow",
    "flow_positioning": "market_flow",
    "options": "options_greeks",
    "optionsgreeks": "options_greeks",
    "options_greeks": "options_greeks",
    "greeks": "options_greeks",
}
_AVAILABLE_STATES = {"available", "ready", "fresh", "complete"}
_DEGRADED_STATES = {"degraded", "partial", "stale", "limited"}
_MISSING_STATES = {"missing", "unavailable", "blocked", "no_data", "none", ""}
_SAFE_SOURCE_DATA_STATES = {"real_cached", "request_supplied", "demo_static_sample", "unavailable"}
_SAFE_FRESHNESS_STATES = {"fresh", "recent", "stale", "unavailable", "unknown", "no_evidence"}
_FORBIDDEN_TEXT_RE = re.compile(
    r"providerclass|providername|api[_ -]?key|env|token|credential|requestid|traceid|"
    r"cachekey|rawpayload|exceptionclass|exceptionchain|https?://|traceback|stack",
    re.IGNORECASE,
)
_SAFE_TEXT_RE = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff _./():+-]+")
_TIMESTAMP_RE = re.compile(r"^[0-9T:Z+\-./ ]{4,40}$")


class ScenarioBaselineSnapshotService:
    """Normalize and read Scenario baseline snapshots through a small seam."""

    def __init__(self) -> None:
        self._snapshots: dict[tuple[str, str], dict[str, Any]] = {}

    def create_snapshot(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        raw = payload if isinstance(payload, Mapping) else {}
        scope = _normalize_scope(raw.get("scope") if isinstance(raw.get("scope"), Mapping) else raw)
        created_at = _safe_timestamp(
            raw.get("createdAt") or raw.get("created_at") or raw.get("snapshotCreatedAt") or raw.get("asOf")
        )
        source = _normalize_source(raw.get("source") if isinstance(raw.get("source"), Mapping) else raw)
        categories = _normalize_categories(raw)
        snapshot_id = _safe_identifier(raw.get("snapshotId") or raw.get("snapshot_id"))
        if not snapshot_id and created_at:
            snapshot_id = _deterministic_snapshot_id(scope=scope, created_at=created_at, categories=categories)

        status, reason_code = _snapshot_status(categories=categories, source=source, snapshot_id=snapshot_id)
        labels = _safe_text_list(raw.get("labels") or raw.get("userLabels") or raw.get("tags"))
        notes = _safe_text(
            raw.get("notes") or raw.get("label") or raw.get("userNotes"),
            fallback="",
            max_length=120,
        )
        observation_only = status != "available" or bool(source["observationOnly"])
        snapshot = {
            "schemaVersion": SCENARIO_BASELINE_SNAPSHOT_SCHEMA_VERSION,
            "status": status,
            "reasonCode": reason_code,
            "snapshotId": snapshot_id,
            "scope": scope,
            "createdAt": created_at,
            "source": source,
            "availableDataCategories": categories["available"],
            "missingDataCategories": categories["missing"],
            "degradedDataCategories": categories["degraded"],
            "labels": labels,
            "notes": notes or None,
            "observationOnly": observation_only,
            "comparisonReady": status == "available" and not observation_only,
            "noAdviceDisclosure": SCENARIO_BASELINE_NO_ADVICE_DISCLOSURE,
        }
        if snapshot["notes"] is None:
            snapshot["notes"] = "Baseline snapshot note omitted."
        self._snapshots[(scope["type"], scope["value"])] = snapshot
        return dict(snapshot)

    def get_latest_snapshot(self, *, scope: Mapping[str, Any] | None = None) -> dict[str, Any]:
        normalized_scope = _normalize_scope(scope or {})
        snapshot = self._snapshots.get((normalized_scope["type"], normalized_scope["value"]))
        if snapshot is not None:
            return dict(snapshot)
        return self.missing_snapshot(scope=normalized_scope)

    def missing_snapshot(self, *, scope: Mapping[str, Any] | None = None) -> dict[str, Any]:
        normalized_scope = _normalize_scope(scope or {})
        return {
            "schemaVersion": SCENARIO_BASELINE_SNAPSHOT_SCHEMA_VERSION,
            "status": "not_available",
            "reasonCode": "baseline_missing",
            "snapshotId": None,
            "scope": normalized_scope,
            "createdAt": None,
            "source": {
                "dataState": "unavailable",
                "freshness": "unavailable",
                "asOf": None,
                "sourceAuthorityAllowed": False,
                "observationOnly": True,
            },
            "availableDataCategories": [],
            "missingDataCategories": list(_CATEGORY_ORDER),
            "degradedDataCategories": [],
            "labels": [],
            "notes": "Baseline snapshot is not available.",
            "observationOnly": True,
            "comparisonReady": False,
            "noAdviceDisclosure": SCENARIO_BASELINE_NO_ADVICE_DISCLOSURE,
        }


def _normalize_scope(raw: Mapping[str, Any]) -> dict[str, str]:
    scope_type = _normalize_token(raw.get("type") or raw.get("scopeType") or raw.get("scope_type"))
    if scope_type not in {"symbol", "market"}:
        scope_type = "symbol" if raw.get("symbol") else "market"
    value = raw.get("value") or raw.get("scopeValue") or raw.get("scope_value")
    if value is None:
        value = raw.get("symbol") if scope_type == "symbol" else raw.get("market")
    text = str(value or ("US" if scope_type == "market" else "")).strip().upper()
    if not text:
        text = "UNKNOWN"
    return {"type": scope_type, "value": text[:32]}


def _normalize_source(raw: Mapping[str, Any]) -> dict[str, Any]:
    data_state = _normalize_token(raw.get("dataState") or raw.get("data_state") or raw.get("sourceState"))
    if data_state not in _SAFE_SOURCE_DATA_STATES:
        data_state = "unavailable" if data_state in _MISSING_STATES else "request_supplied"
    freshness = _normalize_token(raw.get("freshness") or raw.get("freshnessState") or raw.get("state"))
    if freshness not in _SAFE_FRESHNESS_STATES:
        freshness = "unknown"
    source_authority_allowed = bool(
        raw.get("sourceAuthorityAllowed")
        or raw.get("scoreAuthorityAllowed")
        or raw.get("source_authority_allowed")
    )
    observation_only = (
        data_state != "real_cached"
        or freshness in {"stale", "unavailable", "no_evidence"}
        or not source_authority_allowed
    )
    volatility_snapshot = _normalize_volatility_authority_snapshot(raw.get("volatilityAuthoritySnapshot"))
    if volatility_snapshot and not volatility_snapshot["consumerEligibility"]["scenarioBaseline"]:
        observation_only = True
    source = {
        "dataState": data_state,
        "freshness": freshness,
        "asOf": _safe_timestamp(raw.get("asOf") or raw.get("as_of") or raw.get("lastUpdated")),
        "sourceAuthorityAllowed": source_authority_allowed,
        "observationOnly": observation_only,
    }
    if volatility_snapshot:
        source["volatilityAuthoritySnapshot"] = volatility_snapshot
    return source


def _normalize_volatility_authority_snapshot(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    consumer = value.get("consumerEligibility")
    score = value.get("scoreEligibility")
    return {
        "snapshotId": _safe_identifier(value.get("snapshotId")),
        "authorityState": _normalize_token(value.get("authorityState")) or "missing",
        "coverageState": _normalize_token(value.get("coverageState")) or "missing",
        "proxyFallback": bool(value.get("proxyFallback")),
        "consumerEligibility": {
            "marketOverview": bool(isinstance(consumer, Mapping) and consumer.get("marketOverview")),
            "liquidity": bool(isinstance(consumer, Mapping) and consumer.get("liquidity")),
            "scenarioBaseline": bool(isinstance(consumer, Mapping) and consumer.get("scenarioBaseline")),
        },
        "scoreEligibility": {
            "allowed": False,
            "reason": _safe_text(
                score.get("reason") if isinstance(score, Mapping) else None,
                fallback="volatility_snapshot_score_default_closed",
                max_length=80,
            ),
        },
    }


def _normalize_categories(raw: Mapping[str, Any]) -> dict[str, list[str]]:
    category_states: dict[str, str] = {}
    explicit_categories = raw.get("categories") or raw.get("dataCategories")
    if isinstance(explicit_categories, Mapping):
        for key, value in explicit_categories.items():
            category = _normalize_category(key)
            if category:
                category_states[category] = _normalize_category_state(value)

    for state_key, state in (
        ("availableDataCategories", "available"),
        ("available_data_categories", "available"),
        ("missingDataCategories", "missing"),
        ("missing_data_categories", "missing"),
        ("degradedDataCategories", "degraded"),
        ("degraded_data_categories", "degraded"),
    ):
        values = raw.get(state_key)
        if isinstance(values, (list, tuple, set)):
            for value in values:
                category = _normalize_category(value)
                if category:
                    category_states[category] = state

    available = [category for category in _CATEGORY_ORDER if category_states.get(category) == "available"]
    degraded = [category for category in _CATEGORY_ORDER if category_states.get(category) == "degraded"]
    missing = [
        category
        for category in _CATEGORY_ORDER
        if category_states.get(category) == "missing" or category not in category_states
    ]
    return {"available": available, "missing": missing, "degraded": degraded}


def _normalize_category_state(value: Any) -> str:
    if isinstance(value, Mapping):
        raw = value.get("state") or value.get("status") or value.get("freshness") or value.get("available")
    else:
        raw = value
    if raw is True:
        return "available"
    if raw is False:
        return "missing"
    state = _normalize_token(raw)
    if state in _AVAILABLE_STATES:
        return "available"
    if state in _DEGRADED_STATES:
        return "degraded"
    if state in _MISSING_STATES:
        return "missing"
    return "missing"


def _snapshot_status(
    *,
    categories: Mapping[str, list[str]],
    source: Mapping[str, Any],
    snapshot_id: str | None,
) -> tuple[str, str]:
    if not snapshot_id:
        return "not_available", "baseline_missing"
    if categories["missing"] or categories["degraded"] or source.get("observationOnly"):
        return "partial", "baseline_partial"
    return "available", "baseline_available"


def _normalize_category(value: object) -> str | None:
    normalized = _normalize_token(value)
    return _CATEGORY_ALIASES.get(normalized)


def _normalize_token(value: object) -> str:
    return re.sub(r"[^0-9a-z_]+", "", str(value or "").strip().lower())


def _safe_identifier(value: object) -> str | None:
    text = str(value or "").strip()
    if not text or _FORBIDDEN_TEXT_RE.search(text):
        return None
    safe = re.sub(r"[^0-9A-Za-z_.:-]+", "-", text).strip("-")
    return safe[:96] or None


def _safe_timestamp(value: object) -> str | None:
    text = str(value or "").strip()
    if not text or _FORBIDDEN_TEXT_RE.search(text):
        return None
    if not _TIMESTAMP_RE.match(text):
        return None
    return text[:40]


def _safe_text(value: object, *, fallback: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text or _FORBIDDEN_TEXT_RE.search(text):
        return fallback
    cleaned = _SAFE_TEXT_RE.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_length] or fallback


def _safe_text_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    labels: list[str] = []
    for item in value:
        label = _safe_text(item, fallback="", max_length=48)
        if label and label not in labels:
            labels.append(label)
    return labels[:8]


def _deterministic_snapshot_id(
    *,
    scope: Mapping[str, str],
    created_at: str,
    categories: Mapping[str, list[str]],
) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "scope": scope,
                "createdAt": created_at,
                "categories": categories,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"scenario-baseline-{digest}"


__all__ = [
    "SCENARIO_BASELINE_NO_ADVICE_DISCLOSURE",
    "SCENARIO_BASELINE_SNAPSHOT_SCHEMA_VERSION",
    "ScenarioBaselineSnapshotService",
]
