# -*- coding: utf-8 -*-
"""Consumer-safe Scenario baseline snapshot service seam.

Non-durable normalization is deliberately pure: it normalizes caller-supplied
snapshot metadata without reading providers, credentials, cache, or database
state. Durable operations delegate to the injected canonical repository.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from src.repositories.scenario_baseline_snapshot_repository import (
    ScenarioBaselineSnapshotRepository,
    ScenarioBaselineSnapshotStorageError,
)
from src.services.scenario_baseline_snapshot_contract import (
    is_scenario_baseline_durable_readiness_state,
)


SCENARIO_BASELINE_SNAPSHOT_SCHEMA_VERSION = "scenario_baseline_snapshot.v1"
SCENARIO_BASELINE_DURABLE_SNAPSHOT_SCHEMA_VERSION = "scenario_baseline_snapshot.v2"
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
_READY_FRESHNESS_STATES = {"fresh", "recent"}
_AUTHORITY_STATES = {"authoritative", "observation_only", "unavailable"}
_TARGET_EVIDENCE_PRESENT_STATES = {"present", "ready", "available", "validated"}
_FORBIDDEN_TEXT_RE = re.compile(
    r"providerclass|providername|api[_ -]?key|\benv\b|token|credential|requestid|traceid|"
    r"cachekey|rawpayload|exceptionclass|exceptionchain|https?://|traceback|stack",
    re.IGNORECASE,
)
_SAFE_TEXT_RE = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff _./():+-]+")
_TIMESTAMP_RE = re.compile(r"^[0-9T:Z+\-./ ]{4,40}$")


class ScenarioBaselineSnapshotService:
    """Normalize and read Scenario baseline snapshots through a small seam."""

    def __init__(self, *, repository: ScenarioBaselineSnapshotRepository | None = None) -> None:
        self._snapshots: dict[tuple[str, str], dict[str, Any]] = {}
        self._repository = repository

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

    def create_durable_snapshot(
        self,
        payload: Mapping[str, Any] | None,
        *,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        if self._repository is None:
            raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_repository_required")
        snapshot = _normalize_durable_snapshot(payload, owner_id=owner_id)
        return self._repository.upsert_snapshot(snapshot)

    def get_durable_snapshot(self, snapshot_id: str, *, owner_id: str | None = None) -> dict[str, Any] | None:
        if self._repository is None:
            raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_repository_required")
        safe_snapshot_id = _safe_identifier(snapshot_id)
        if not safe_snapshot_id:
            return None
        return self._repository.get_snapshot(
            snapshot_id=safe_snapshot_id,
            owner_scope=_owner_scope(owner_id),
        )

    def get_latest_durable_snapshot(
        self,
        *,
        scope: Mapping[str, Any] | None = None,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        if self._repository is None:
            raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_repository_required")
        normalized_scope = _normalize_scope(scope or {})
        latest = self._repository.latest_for_scope(
            owner_scope=_owner_scope(owner_id),
            scope=normalized_scope,
        )
        if latest is None:
            return _missing_durable_snapshot(scope=normalized_scope, owner_id=owner_id)
        return dict(latest)


def _normalize_durable_snapshot(payload: Mapping[str, Any] | None, *, owner_id: str | None) -> dict[str, Any]:
    raw = payload if isinstance(payload, Mapping) else {}
    normalized = ScenarioBaselineSnapshotService().create_snapshot(raw)
    scope = normalized["scope"]
    source = normalized["source"]
    created_at = normalized["createdAt"] or _safe_timestamp(raw.get("createdAt") or raw.get("created_at"))
    as_of = _safe_timestamp(
        raw.get("asOf")
        or raw.get("as_of")
        or source.get("asOf")
        or raw.get("lastUpdated")
        or raw.get("snapshotAsOf")
    )
    if created_at is None:
        created_at = as_of
    input_snapshot_refs = _safe_text_list(
        raw.get("inputSnapshotRefs")
        or raw.get("input_snapshot_refs")
        or raw.get("inputSnapshots")
        or raw.get("inputRefs")
    )
    missing_input_list = _safe_text_list(
        raw.get("missingInputList")
        or raw.get("missing_input_list")
        or raw.get("missingInputs")
        or raw.get("missingDataCategories")
    )
    source_authority_summary = _source_authority_summary(raw.get("sourceAuthoritySummary"), source=source)
    freshness_summary = _freshness_summary(raw.get("freshnessSummary"), source=source, as_of=as_of)
    target_environment_evidence = _target_environment_evidence(raw.get("targetEnvironmentEvidence"))
    readiness_state = _durable_readiness_state(
        normalized=normalized,
        source_authority_summary=source_authority_summary,
        freshness_summary=freshness_summary,
        missing_input_list=missing_input_list,
        target_environment_evidence=target_environment_evidence,
    )
    if not is_scenario_baseline_durable_readiness_state(readiness_state):
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_readiness_invalid")
    observation_only = readiness_state != "ready"
    status = "available" if readiness_state == "ready" else "partial" if normalized["snapshotId"] else "not_available"
    reason_code = "baseline_available" if status == "available" else "baseline_partial" if status == "partial" else "baseline_missing"
    final_source = {**source, "observationOnly": observation_only}
    content_payload = {
        "schemaVersion": SCENARIO_BASELINE_DURABLE_SNAPSHOT_SCHEMA_VERSION,
        "snapshotId": normalized["snapshotId"],
        "ownerScope": _owner_scope(owner_id),
        "scope": scope,
        "createdAt": created_at,
        "asOf": as_of,
        "source": final_source,
        "availableDataCategories": normalized["availableDataCategories"],
        "missingDataCategories": normalized["missingDataCategories"],
        "degradedDataCategories": normalized["degradedDataCategories"],
        "inputSnapshotRefs": input_snapshot_refs,
        "sourceAuthoritySummary": source_authority_summary,
        "freshnessSummary": freshness_summary,
        "missingInputList": missing_input_list,
        "readinessState": readiness_state,
        "targetEnvironmentEvidence": target_environment_evidence,
    }
    content_hash = f"sha256:{_stable_hash(content_payload)}"
    snapshot_id = normalized["snapshotId"] or f"scenario-baseline-{content_hash.removeprefix('sha256:')[:16]}"
    content_payload["snapshotId"] = snapshot_id
    content_hash = f"sha256:{_stable_hash(content_payload)}"
    return {
        **normalized,
        "schemaVersion": SCENARIO_BASELINE_DURABLE_SNAPSHOT_SCHEMA_VERSION,
        "status": status,
        "reasonCode": reason_code,
        "snapshotId": snapshot_id,
        "ownerScope": _owner_scope(owner_id),
        "createdAt": created_at,
        "asOf": as_of,
        "source": final_source,
        "inputSnapshotRefs": input_snapshot_refs,
        "sourceAuthoritySummary": source_authority_summary,
        "freshnessSummary": freshness_summary,
        "missingInputList": missing_input_list,
        "readinessState": readiness_state,
        "targetEnvironmentEvidence": target_environment_evidence,
        "contentHash": content_hash,
        "contentVersionRef": f"{SCENARIO_BASELINE_DURABLE_SNAPSHOT_SCHEMA_VERSION}:{content_hash}",
        "observationOnly": observation_only,
        "comparisonReady": not observation_only and status == "available",
    }


def _missing_durable_snapshot(*, scope: Mapping[str, Any], owner_id: str | None) -> dict[str, Any]:
    owner_scope = _owner_scope(owner_id)
    return {
        "schemaVersion": SCENARIO_BASELINE_DURABLE_SNAPSHOT_SCHEMA_VERSION,
        "status": "not_available",
        "reasonCode": "baseline_missing",
        "snapshotId": None,
        "ownerScope": owner_scope,
        "scope": _normalize_scope(scope),
        "createdAt": None,
        "asOf": None,
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
        "inputSnapshotRefs": [],
        "sourceAuthoritySummary": {"state": "unavailable", "allowed": False, "reasonCodes": ["baseline_missing"]},
        "freshnessSummary": {"state": "unavailable", "asOf": None},
        "missingInputList": list(_CATEGORY_ORDER),
        "readinessState": "not_available",
        "targetEnvironmentEvidence": {"state": "missing", "evidenceRefs": []},
        "contentHash": None,
        "contentVersionRef": None,
        "observationOnly": True,
        "comparisonReady": False,
        "noAdviceDisclosure": SCENARIO_BASELINE_NO_ADVICE_DISCLOSURE,
    }


def _owner_scope(owner_id: str | None) -> dict[str, str]:
    text = _safe_identifier(owner_id) or "anonymous"
    return {"type": "user" if text != "anonymous" else "anonymous", "value": text}


def _source_authority_summary(value: Any, *, source: Mapping[str, Any]) -> dict[str, Any]:
    raw = value if isinstance(value, Mapping) else {}
    state = _normalize_token(raw.get("state") or raw.get("status"))
    if state not in _AUTHORITY_STATES:
        state = "authoritative" if source.get("sourceAuthorityAllowed") else "observation_only"
    allowed = bool(raw.get("allowed") if "allowed" in raw else source.get("sourceAuthorityAllowed"))
    if state != "authoritative":
        allowed = False
    return {
        "state": state,
        "allowed": allowed,
        "reasonCodes": _safe_text_list(raw.get("reasonCodes") or raw.get("reason_codes")),
    }


def _freshness_summary(value: Any, *, source: Mapping[str, Any], as_of: str | None) -> dict[str, Any]:
    raw = value if isinstance(value, Mapping) else {}
    state = _normalize_token(raw.get("state") or raw.get("freshness") or source.get("freshness"))
    if state not in _SAFE_FRESHNESS_STATES:
        state = "unknown"
    return {
        "state": state,
        "asOf": _safe_timestamp(raw.get("asOf") or raw.get("as_of") or as_of),
    }


def _target_environment_evidence(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, Mapping) else {}
    state = _normalize_token(raw.get("state") or raw.get("status"))
    if state not in {*_TARGET_EVIDENCE_PRESENT_STATES, "missing", "unavailable", "blocked"}:
        state = "missing"
    return {
        "state": state,
        "evidenceRefs": _safe_text_list(raw.get("evidenceRefs") or raw.get("evidence_refs") or raw.get("refs")),
    }


def _durable_readiness_state(
    *,
    normalized: Mapping[str, Any],
    source_authority_summary: Mapping[str, Any],
    freshness_summary: Mapping[str, Any],
    missing_input_list: list[str],
    target_environment_evidence: Mapping[str, Any],
) -> str:
    if normalized.get("status") == "not_available":
        return "not_available"
    source = normalized.get("source") if isinstance(normalized.get("source"), Mapping) else {}
    target_evidence_state = _normalize_token(target_environment_evidence.get("state"))
    target_evidence_present = target_evidence_state in _TARGET_EVIDENCE_PRESENT_STATES
    if (
        normalized.get("status") == "available"
        and source.get("dataState") == "real_cached"
        and source_authority_summary.get("state") == "authoritative"
        and source_authority_summary.get("allowed") is True
        and freshness_summary.get("state") in _READY_FRESHNESS_STATES
        and not missing_input_list
        and target_evidence_present
    ):
        return "ready"
    if source.get("dataState") in {"request_supplied", "demo_static_sample"} or freshness_summary.get("state") == "stale":
        return "observation_only"
    return "partial"


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


def _stable_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "SCENARIO_BASELINE_DURABLE_SNAPSHOT_SCHEMA_VERSION",
    "SCENARIO_BASELINE_NO_ADVICE_DISCLOSURE",
    "SCENARIO_BASELINE_SNAPSHOT_SCHEMA_VERSION",
    "ScenarioBaselineSnapshotStorageError",
    "ScenarioBaselineSnapshotService",
]
