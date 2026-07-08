from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError

from src.services.scenario_baseline_snapshot_contract import (
    is_scenario_baseline_durable_readiness_state,
)
from src.storage import DatabaseManager, ScenarioBaselineSnapshotRow


SCHEMA_VERSION = "scenario_baseline_snapshot_repository.v1"
SNAPSHOT_SCHEMA_VERSION = "scenario_baseline_snapshot.v2"
_CONTENT_HASH_KEYS = (
    "schemaVersion",
    "snapshotId",
    "ownerScope",
    "scope",
    "createdAt",
    "asOf",
    "source",
    "availableDataCategories",
    "missingDataCategories",
    "degradedDataCategories",
    "inputSnapshotRefs",
    "sourceAuthoritySummary",
    "freshnessSummary",
    "missingInputList",
    "readinessState",
    "targetEnvironmentEvidence",
)


class ScenarioBaselineSnapshotStorageError(ValueError):
    """Raised when durable Scenario baseline snapshot storage is invalid."""


class ScenarioBaselineSnapshotRepository:
    """Canonical DatabaseManager-owned persistence boundary for Scenario baselines."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db = db_manager

    def upsert_snapshot(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        payload = _validated_snapshot_payload(snapshot)
        payload_json = _canonical_payload_json(payload)

        try:
            with self.db.session_scope() as session:
                existing = _existing_row(
                    session,
                    owner_scope=payload["ownerScope"],
                    snapshot_id=payload["snapshotId"],
                )
                if existing is not None:
                    existing_payload = _snapshot_from_row(existing)
                    if existing_payload.get("contentHash") != payload["contentHash"]:
                        raise ScenarioBaselineSnapshotStorageError("immutable_snapshot_conflict")
                    return existing_payload

                session.add(
                    ScenarioBaselineSnapshotRow(
                        owner_type=payload["ownerScope"]["type"],
                        owner_value=payload["ownerScope"]["value"],
                        snapshot_id=payload["snapshotId"],
                        scope_type=payload["scope"]["type"],
                        scope_value=payload["scope"]["value"],
                        created_at=payload["createdAt"],
                        as_of=payload["asOf"],
                        readiness_state=payload["readinessState"],
                        content_hash=payload["contentHash"],
                        content_version_ref=payload["contentVersionRef"],
                        payload_json=payload_json,
                    )
                )
        except IntegrityError as exc:
            existing = self.get_snapshot(
                snapshot_id=str(payload["snapshotId"]),
                owner_scope=payload["ownerScope"],
            )
            if existing is not None and existing.get("contentHash") == payload["contentHash"]:
                return existing
            raise ScenarioBaselineSnapshotStorageError("immutable_snapshot_conflict") from exc

        return dict(payload)

    def get_snapshot(self, *, snapshot_id: str, owner_scope: Mapping[str, Any]) -> dict[str, Any] | None:
        safe_snapshot_id = str(snapshot_id or "").strip()
        if not safe_snapshot_id:
            return None
        normalized_owner = _owner_scope(owner_scope)
        with self.db.get_session() as session:
            row = _existing_row(
                session,
                owner_scope=normalized_owner,
                snapshot_id=safe_snapshot_id,
            )
            return _snapshot_from_row(row) if row is not None else None

    def latest_for_scope(self, *, owner_scope: Mapping[str, Any], scope: Mapping[str, Any]) -> dict[str, Any] | None:
        normalized_owner = _owner_scope(owner_scope)
        normalized_scope = _scope(scope)
        with self.db.get_session() as session:
            row = (
                session.execute(
                    select(ScenarioBaselineSnapshotRow)
                    .where(
                        ScenarioBaselineSnapshotRow.owner_type == normalized_owner["type"],
                        ScenarioBaselineSnapshotRow.owner_value == normalized_owner["value"],
                        ScenarioBaselineSnapshotRow.scope_type == normalized_scope["type"],
                        ScenarioBaselineSnapshotRow.scope_value == normalized_scope["value"],
                    )
                    .order_by(
                        desc(ScenarioBaselineSnapshotRow.as_of),
                        desc(ScenarioBaselineSnapshotRow.created_at),
                        desc(ScenarioBaselineSnapshotRow.snapshot_id),
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            return _snapshot_from_row(row) if row is not None else None

    def migration_report(self) -> dict[str, str]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "storageOwner": "DatabaseManager",
            "schemaLifecycle": "SQLAlchemy Base.metadata.create_all",
            "table": ScenarioBaselineSnapshotRow.__tablename__,
        }


def _existing_row(session: Any, *, owner_scope: Mapping[str, str], snapshot_id: str) -> ScenarioBaselineSnapshotRow | None:
    return (
        session.execute(
            select(ScenarioBaselineSnapshotRow)
            .where(
                ScenarioBaselineSnapshotRow.owner_type == owner_scope["type"],
                ScenarioBaselineSnapshotRow.owner_value == owner_scope["value"],
                ScenarioBaselineSnapshotRow.snapshot_id == snapshot_id,
            )
            .limit(1)
        )
        .scalars()
        .first()
    )


def _snapshot_from_row(row: ScenarioBaselineSnapshotRow) -> dict[str, Any]:
    payload = _json_mapping(row.payload_json)
    snapshot = _validated_snapshot_payload(payload)
    if row.owner_type != snapshot["ownerScope"]["type"] or row.owner_value != snapshot["ownerScope"]["value"]:
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_owner_mismatch")
    if row.snapshot_id != snapshot["snapshotId"]:
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_identity_mismatch")
    if row.scope_type != snapshot["scope"]["type"] or row.scope_value != snapshot["scope"]["value"]:
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_scope_mismatch")
    if row.created_at != snapshot["createdAt"] or row.as_of != snapshot["asOf"]:
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_timestamp_mismatch")
    if row.content_hash != snapshot["contentHash"]:
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_content_hash_mismatch")
    if row.content_version_ref != snapshot["contentVersionRef"]:
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_content_version_mismatch")
    return snapshot


def _validated_snapshot_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value or {})
    if payload.get("schemaVersion") != SNAPSHOT_SCHEMA_VERSION:
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_schema_invalid")

    snapshot_id = _required_text(payload.get("snapshotId"), "snapshot_id")
    owner_scope = _owner_scope(payload.get("ownerScope"))
    scope = _scope(payload.get("scope"))
    created_at = _required_timestamp(payload.get("createdAt"), "created_at")
    as_of = _required_timestamp(payload.get("asOf"), "as_of")
    readiness_state = _required_text(payload.get("readinessState"), "readiness_state")
    if not is_scenario_baseline_durable_readiness_state(readiness_state):
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_readiness_invalid")
    input_refs = payload.get("inputSnapshotRefs")
    if not input_refs or not isinstance(input_refs, list) or not all(
        isinstance(item, str) and item.strip() for item in input_refs
    ):
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_input_refs_invalid")

    content_hash = _required_text(payload.get("contentHash"), "content_hash")
    expected_hash = _content_hash(payload)
    if content_hash != expected_hash:
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_content_hash_mismatch")
    content_version_ref = _required_text(payload.get("contentVersionRef"), "content_version_ref")
    if content_version_ref != f"{SNAPSHOT_SCHEMA_VERSION}:{content_hash}":
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_content_version_mismatch")

    target_evidence = payload.get("targetEnvironmentEvidence")
    if not isinstance(target_evidence, Mapping) or not str(target_evidence.get("state") or "").strip():
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_target_evidence_invalid")
    if not isinstance(target_evidence.get("evidenceRefs"), list):
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_target_evidence_invalid")

    source = payload.get("source")
    if not isinstance(source, Mapping):
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_source_invalid")
    _validate_volatility_authority_snapshot(source.get("volatilityAuthoritySnapshot"))

    payload["snapshotId"] = snapshot_id
    payload["ownerScope"] = owner_scope
    payload["scope"] = scope
    payload["createdAt"] = created_at
    payload["asOf"] = as_of
    payload["readinessState"] = readiness_state
    return payload


def _validate_volatility_authority_snapshot(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping):
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_volatility_authority_invalid")
    consumer = value.get("consumerEligibility")
    score = value.get("scoreEligibility")
    if not isinstance(consumer, Mapping) or not isinstance(score, Mapping):
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_volatility_authority_invalid")
    for key in ("marketOverview", "liquidity", "scenarioBaseline"):
        if not isinstance(consumer.get(key), bool):
            raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_volatility_authority_invalid")
    if not isinstance(score.get("allowed"), bool) or not str(score.get("reason") or "").strip():
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_volatility_authority_invalid")
    for key in ("authorityState", "coverageState"):
        if not str(value.get(key) or "").strip():
            raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_volatility_authority_invalid")
    if not isinstance(value.get("proxyFallback"), bool):
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_volatility_authority_invalid")


def _json_mapping(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_payload_corrupt") from exc
    if not isinstance(parsed, dict):
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_payload_not_object")
    return dict(parsed)


def _content_hash(payload: Mapping[str, Any]) -> str:
    content_payload = {key: payload.get(key) for key in _CONTENT_HASH_KEYS}
    digest = hashlib.sha256(_canonical_payload_json(content_payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _canonical_payload_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _owner_scope(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_owner_missing")
    owner_type = _required_text(value.get("type"), "owner_type")
    owner_value = _required_text(value.get("value"), "owner_value")
    return {"type": owner_type, "value": owner_value}


def _scope(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_scope_missing")
    scope_type = _required_text(value.get("type"), "scope_type")
    scope_value = _required_text(value.get("value"), "scope_value")
    if scope_type not in {"symbol", "market"}:
        raise ScenarioBaselineSnapshotStorageError("scenario_baseline_snapshot_scope_invalid")
    return {"type": scope_type, "value": scope_value}


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ScenarioBaselineSnapshotStorageError(f"scenario_baseline_snapshot_{field_name}_missing")
    return text


def _required_timestamp(value: Any, field_name: str) -> str:
    text = _required_text(value, field_name)
    if "T" not in text:
        raise ScenarioBaselineSnapshotStorageError(f"scenario_baseline_snapshot_{field_name}_invalid")
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScenarioBaselineSnapshotStorageError(f"scenario_baseline_snapshot_{field_name}_invalid") from exc
    if not any(character.isdigit() for character in text):
        raise ScenarioBaselineSnapshotStorageError(f"scenario_baseline_snapshot_{field_name}_invalid")
    return text


__all__ = [
    "SCHEMA_VERSION",
    "ScenarioBaselineSnapshotRepository",
    "ScenarioBaselineSnapshotStorageError",
]
