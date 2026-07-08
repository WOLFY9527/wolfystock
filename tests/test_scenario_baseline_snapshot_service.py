# -*- coding: utf-8 -*-
"""Contract tests for the Scenario baseline snapshot service seam."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from src.repositories.scenario_baseline_snapshot_repository import (
    ScenarioBaselineSnapshotRepository,
    ScenarioBaselineSnapshotStorageError,
)
from src.services.scenario_baseline_snapshot_service import ScenarioBaselineSnapshotService
from src.storage import DatabaseManager, ScenarioBaselineSnapshotRow


FORBIDDEN_PUBLIC_MARKERS = (
    "providerClass",
    "providerName",
    "apiKey",
    "env",
    "token",
    "credential",
    "requestId",
    "traceId",
    "cacheKey",
    "rawPayload",
    "exceptionClass",
    "exceptionChain",
)


@pytest.fixture(autouse=True)
def _reset_database_manager() -> None:
    DatabaseManager.reset_instance()
    yield
    DatabaseManager.reset_instance()


def _assert_no_forbidden_marker(payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    for marker in FORBIDDEN_PUBLIC_MARKERS:
        assert marker not in text
        assert marker.lower() not in lowered


def test_create_normalizes_baseline_snapshot_from_fixture_data() -> None:
    service = ScenarioBaselineSnapshotService()

    snapshot = service.create_snapshot(
        {
            "snapshotId": "baseline-us-open-20260615",
            "scope": {"type": "symbol", "value": " aapl "},
            "createdAt": "2026-06-15T09:30:00Z",
            "source": {
                "dataState": "real_cached",
                "freshness": "fresh",
                "asOf": "2026-06-15T09:30:00Z",
                "sourceAuthorityAllowed": True,
            },
            "categories": {
                "price": {"state": "available"},
                "volatility": {"state": "available"},
                "flowPositioning": {"state": "missing", "reason": "not_collected"},
                "optionsGreeks": {"state": "missing"},
                "marketRegime": {"state": "available"},
            },
            "labels": ["UAT baseline", "Open snapshot"],
            "notes": "Research baseline for scenario comparison.",
        }
    )

    assert snapshot["schemaVersion"] == "scenario_baseline_snapshot.v1"
    assert snapshot["status"] == "partial"
    assert snapshot["reasonCode"] == "baseline_partial"
    assert snapshot["snapshotId"] == "baseline-us-open-20260615"
    assert snapshot["scope"] == {"type": "symbol", "value": "AAPL"}
    assert snapshot["createdAt"] == "2026-06-15T09:30:00Z"
    assert snapshot["source"] == {
        "dataState": "real_cached",
        "freshness": "fresh",
        "asOf": "2026-06-15T09:30:00Z",
        "sourceAuthorityAllowed": True,
        "observationOnly": False,
    }
    assert snapshot["availableDataCategories"] == ["market_price", "market_regime", "volatility"]
    assert snapshot["missingDataCategories"] == ["market_flow", "options_greeks"]
    assert snapshot["degradedDataCategories"] == []
    assert snapshot["labels"] == ["UAT baseline", "Open snapshot"]
    assert snapshot["notes"] == "Research baseline for scenario comparison."
    assert snapshot["observationOnly"] is True
    assert snapshot["comparisonReady"] is False
    assert "baselinePrice" not in snapshot
    assert "volatilityValue" not in snapshot


def test_baseline_missing_state_is_deterministic_without_throwing() -> None:
    service = ScenarioBaselineSnapshotService()

    snapshot = service.get_latest_snapshot(scope={"type": "market", "value": "US"})

    assert snapshot["status"] == "not_available"
    assert snapshot["reasonCode"] == "baseline_missing"
    assert snapshot["snapshotId"] is None
    assert snapshot["scope"] == {"type": "market", "value": "US"}
    assert snapshot["availableDataCategories"] == []
    assert snapshot["missingDataCategories"] == [
        "market_price",
        "market_regime",
        "volatility",
        "market_flow",
        "options_greeks",
    ]
    assert snapshot["degradedDataCategories"] == []
    assert snapshot["comparisonReady"] is False
    assert snapshot["source"]["dataState"] == "unavailable"


def test_partial_snapshot_keeps_degraded_categories_explicit() -> None:
    service = ScenarioBaselineSnapshotService()

    snapshot = service.create_snapshot(
        {
            "snapshotId": "baseline-market-20260615",
            "scope": {"type": "market", "value": "US"},
            "createdAt": "2026-06-15T09:30:00Z",
            "source": {"dataState": "request_supplied", "freshness": "stale"},
            "availableDataCategories": ["marketPrice", "marketRegime"],
            "degradedDataCategories": ["volatility"],
            "missingDataCategories": ["flowPositioning", "optionsGreeks"],
        }
    )

    assert snapshot["status"] == "partial"
    assert snapshot["reasonCode"] == "baseline_partial"
    assert snapshot["source"]["observationOnly"] is True
    assert snapshot["availableDataCategories"] == ["market_price", "market_regime"]
    assert snapshot["degradedDataCategories"] == ["volatility"]
    assert snapshot["missingDataCategories"] == ["market_flow", "options_greeks"]
    assert snapshot["comparisonReady"] is False


def test_volatility_authority_snapshot_controls_scenario_baseline_eligibility() -> None:
    service = ScenarioBaselineSnapshotService()

    official_snapshot = service.create_snapshot(
        {
            "snapshotId": "baseline-vix-official",
            "scope": {"type": "market", "value": "US"},
            "createdAt": "2026-07-06T20:05:00Z",
            "source": {
                "dataState": "real_cached",
                "freshness": "delayed",
                "asOf": "2026-07-06T20:00:00Z",
                "sourceAuthorityAllowed": True,
                "volatilityAuthoritySnapshot": {
                    "snapshotId": "volatility:VIX:fred:VIXCLS:2026-07-06T20:00:00Z",
                    "authorityState": "official",
                    "coverageState": "available",
                    "proxyFallback": False,
                    "consumerEligibility": {
                        "marketOverview": True,
                        "liquidity": True,
                        "scenarioBaseline": True,
                    },
                    "scoreEligibility": {
                        "allowed": False,
                        "reason": "volatility_snapshot_score_default_closed",
                    },
                },
            },
            "categories": {
                "price": {"state": "available"},
                "marketRegime": {"state": "available"},
                "volatility": {"state": "available"},
                "flowPositioning": {"state": "available"},
                "optionsGreeks": {"state": "available"},
            },
        }
    )
    proxy_snapshot = service.create_snapshot(
        {
            "snapshotId": "baseline-vix-proxy",
            "scope": {"type": "market", "value": "US"},
            "createdAt": "2026-07-06T20:05:00Z",
            "source": {
                "dataState": "real_cached",
                "freshness": "delayed",
                "asOf": "2026-07-06T20:00:00Z",
                "sourceAuthorityAllowed": True,
                "volatilityAuthoritySnapshot": {
                    "snapshotId": "volatility:VIX:yfinance:^VIX:2026-07-06T20:00:00Z",
                    "authorityState": "proxy",
                    "coverageState": "available",
                    "proxyFallback": True,
                    "consumerEligibility": {
                        "marketOverview": True,
                        "liquidity": False,
                        "scenarioBaseline": False,
                    },
                    "scoreEligibility": {
                        "allowed": False,
                        "reason": "unofficial_proxy_not_score_grade",
                    },
                },
            },
            "categories": {
                "price": {"state": "available"},
                "marketRegime": {"state": "available"},
                "volatility": {"state": "available"},
                "flowPositioning": {"state": "available"},
                "optionsGreeks": {"state": "available"},
            },
        }
    )

    assert official_snapshot["status"] == "available"
    assert official_snapshot["comparisonReady"] is True
    assert official_snapshot["source"]["volatilityAuthoritySnapshot"] == {
        "snapshotId": "volatility:VIX:fred:VIXCLS:2026-07-06T20:00:00Z",
        "authorityState": "official",
        "coverageState": "available",
        "proxyFallback": False,
        "consumerEligibility": {
            "marketOverview": True,
            "liquidity": True,
            "scenarioBaseline": True,
        },
        "scoreEligibility": {
            "allowed": False,
            "reason": "volatility_snapshot_score_default_closed",
        },
    }
    assert proxy_snapshot["status"] == "partial"
    assert proxy_snapshot["reasonCode"] == "baseline_partial"
    assert proxy_snapshot["source"]["observationOnly"] is True
    assert proxy_snapshot["comparisonReady"] is False
    assert proxy_snapshot["source"]["volatilityAuthoritySnapshot"]["authorityState"] == "proxy"


def test_consumer_safe_response_redacts_internal_provider_and_runtime_markers() -> None:
    service = ScenarioBaselineSnapshotService()

    snapshot = service.create_snapshot(
        {
            "snapshotId": "baseline-redaction",
            "scope": {"type": "symbol", "value": "MSFT"},
            "createdAt": "2026-06-15T09:30:00Z",
            "source": {
                "providerClass": "InternalProvider",
                "providerName": "secret-provider",
                "apiKey": "secret",
                "env": "LOCAL_ENV",
                "token": "secret-token",
                "credential": "secret-credential",
                "requestId": "req-1",
                "traceId": "trace-1",
                "cacheKey": "cache-key",
                "rawPayload": {"price": 123.45},
                "exceptionClass": "ProviderError",
                "exceptionChain": ["boom"],
                "freshness": "fresh",
            },
            "categories": {"price": {"state": "available"}},
            "labels": ["providerName must not leak", "Consumer baseline"],
            "notes": "traceId req-1 providerClass rawPayload token must not leak.",
        }
    )

    _assert_no_forbidden_marker(snapshot)
    assert snapshot["labels"] == ["Consumer baseline"]
    assert snapshot["notes"] == "Baseline snapshot note omitted."
    assert set(snapshot["source"]) == {
        "dataState",
        "freshness",
        "asOf",
        "sourceAuthorityAllowed",
        "observationOnly",
    }


def test_service_module_does_not_import_network_or_provider_runtime_domains() -> None:
    source_path = Path(__file__).resolve().parents[1] / "src" / "services" / "scenario_baseline_snapshot_service.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    forbidden_prefixes = (
        "requests",
        "httpx",
        "urllib",
        "aiohttp",
        "data_provider",
        "src.providers",
        "src.services.options_market_data_provider",
        "src.services.market_cache",
        "api.deps",
        "src.auth",
    )
    assert not [
        module
        for module in imported_modules
        if module == "socket" or any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden_prefixes)
    ]


def _durable_ready_payload(*, snapshot_id: str = "baseline-durable-us-open") -> dict[str, Any]:
    return {
        "snapshotId": snapshot_id,
        "scope": {"type": "market", "value": "US"},
        "createdAt": "2026-07-07T09:31:00Z",
        "asOf": "2026-07-07T09:30:00Z",
        "source": {
            "dataState": "real_cached",
            "freshness": "fresh",
            "asOf": "2026-07-07T09:30:00Z",
            "sourceAuthorityAllowed": True,
        },
        "categories": {
            "price": {"state": "available"},
            "marketRegime": {"state": "available"},
            "volatility": {"state": "available"},
            "flowPositioning": {"state": "available"},
            "optionsGreeks": {"state": "available"},
        },
        "inputSnapshotRefs": ["market-overview:2026-07-07T09:30:00Z", "decision-cockpit:2026-07-07T09:30:00Z"],
        "sourceAuthoritySummary": {
            "state": "authoritative",
            "allowed": True,
            "reasonCodes": ["target_environment_evidence_present"],
        },
        "freshnessSummary": {
            "state": "fresh",
            "asOf": "2026-07-07T09:30:00Z",
        },
        "targetEnvironmentEvidence": {
            "state": "present",
            "evidenceRefs": ["uat-runtime:scenario-baseline"],
        },
    }


def _db(tmp_path: Path, *, name: str = "scenario-baselines.sqlite") -> DatabaseManager:
    return DatabaseManager(db_url=f"sqlite:///{tmp_path / name}")


def _repo(tmp_path: Path, *, name: str = "scenario-baselines.sqlite") -> ScenarioBaselineSnapshotRepository:
    return ScenarioBaselineSnapshotRepository(_db(tmp_path, name=name))


def _service(tmp_path: Path, *, name: str = "scenario-baselines.sqlite") -> ScenarioBaselineSnapshotService:
    return ScenarioBaselineSnapshotService(repository=_repo(tmp_path, name=name))


def test_explicit_durable_snapshot_creation_records_reproducibility_contract(tmp_path: Path) -> None:
    service = _service(tmp_path)

    snapshot = service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")

    assert snapshot["snapshotId"] == "baseline-durable-us-open"
    assert snapshot["ownerScope"] == {"type": "user", "value": "user-a"}
    assert snapshot["createdAt"] == "2026-07-07T09:31:00Z"
    assert snapshot["asOf"] == "2026-07-07T09:30:00Z"
    assert snapshot["readinessState"] == "ready"
    assert snapshot["status"] == "available"
    assert snapshot["observationOnly"] is False
    assert snapshot["comparisonReady"] is True
    assert snapshot["inputSnapshotRefs"] == [
        "market-overview:2026-07-07T09:30:00Z",
        "decision-cockpit:2026-07-07T09:30:00Z",
    ]
    assert snapshot["sourceAuthoritySummary"] == {
        "state": "authoritative",
        "allowed": True,
        "reasonCodes": ["target_environment_evidence_present"],
    }
    assert snapshot["freshnessSummary"] == {
        "state": "fresh",
        "asOf": "2026-07-07T09:30:00Z",
    }
    assert snapshot["missingInputList"] == []
    assert snapshot["contentHash"].startswith("sha256:")
    assert snapshot["contentVersionRef"] == f"scenario_baseline_snapshot.v2:{snapshot['contentHash']}"

    DatabaseManager.reset_instance()
    reloaded = ScenarioBaselineSnapshotService(repository=_repo(tmp_path))
    assert reloaded.get_durable_snapshot(snapshot["snapshotId"], owner_id="user-a") == snapshot
    assert reloaded.get_latest_durable_snapshot(scope={"type": "market", "value": "US"}, owner_id="user-a") == snapshot


def test_zero_usable_data_durable_snapshot_persists_domain_not_available_state(tmp_path: Path) -> None:
    service = _service(tmp_path)
    payload = _durable_ready_payload(snapshot_id="baseline-zero-usable")
    payload.pop("snapshotId")
    payload.pop("createdAt")
    payload.pop("asOf")
    payload["source"] = {
        "dataState": "unavailable",
        "freshness": "unavailable",
        "asOf": "2026-07-07T09:30:00Z",
        "sourceAuthorityAllowed": False,
    }
    payload["categories"] = {
        "price": {"state": "missing"},
        "marketRegime": {"state": "missing"},
        "volatility": {"state": "missing"},
        "flowPositioning": {"state": "missing"},
        "optionsGreeks": {"state": "missing"},
    }
    payload["inputSnapshotRefs"] = ["market-overview:missing:2026-07-07T09:30:00Z"]
    payload["sourceAuthoritySummary"] = {
        "state": "unavailable",
        "allowed": False,
        "reasonCodes": ["source_authority_unavailable"],
    }
    payload["freshnessSummary"] = {"state": "unavailable", "asOf": "2026-07-07T09:30:00Z"}
    payload["missingInputList"] = ["market_price", "market_regime", "volatility", "market_flow", "options_greeks"]
    payload["targetEnvironmentEvidence"] = {"state": "missing", "evidenceRefs": []}

    snapshot = service.create_durable_snapshot(payload, owner_id="user-a")

    assert snapshot["status"] == "not_available"
    assert snapshot["reasonCode"] == "baseline_missing"
    assert snapshot["readinessState"] == "not_available"
    assert snapshot["snapshotId"].startswith("scenario-baseline-")
    assert snapshot["observationOnly"] is True
    assert snapshot["comparisonReady"] is False
    assert snapshot["contentHash"].startswith("sha256:")
    assert snapshot["inputSnapshotRefs"] == ["market-overview:missing:2026-07-07T09:30:00Z"]
    assert service.get_durable_snapshot(snapshot["snapshotId"], owner_id="user-a") == snapshot


def test_durable_readback_is_side_effect_free_when_snapshot_is_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "passive.sqlite"
    engine = create_engine(f"sqlite:///{db_path}", pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = object.__new__(DatabaseManager)
    db._engine = engine
    db._SessionLocal = session_factory
    db._initialized = True
    repo = ScenarioBaselineSnapshotRepository(db)

    assert "scenario_baseline_snapshots" not in inspect(engine).get_table_names()
    service = ScenarioBaselineSnapshotService(repository=repo)
    with pytest.raises(Exception):
        service.get_latest_durable_snapshot(scope={"type": "market", "value": "US"}, owner_id="user-a")
    assert "scenario_baseline_snapshots" not in inspect(engine).get_table_names()
    engine.dispose()

    db = _db(tmp_path)
    assert "scenario_baseline_snapshots" in inspect(db._engine).get_table_names()
    service = ScenarioBaselineSnapshotService(repository=ScenarioBaselineSnapshotRepository(db))
    missing = service.get_latest_durable_snapshot(scope={"type": "market", "value": "US"}, owner_id="user-a")
    assert missing["status"] == "not_available"
    assert missing["reasonCode"] == "baseline_missing"
    assert missing["readinessState"] == "not_available"
    assert missing["ownerScope"] == {"type": "user", "value": "user-a"}
    assert missing["contentHash"] is None
    assert missing["inputSnapshotRefs"] == []


def test_durable_snapshot_readback_is_owner_isolated(tmp_path: Path) -> None:
    service = _service(tmp_path)
    snapshot = service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")

    assert service.get_durable_snapshot(snapshot["snapshotId"], owner_id="user-b") is None
    missing_latest = service.get_latest_durable_snapshot(scope={"type": "market", "value": "US"}, owner_id="user-b")
    assert missing_latest["status"] == "not_available"
    assert missing_latest["ownerScope"] == {"type": "user", "value": "user-b"}


def test_request_body_owner_scope_cannot_override_authenticated_owner(tmp_path: Path) -> None:
    service = _service(tmp_path)
    payload = _durable_ready_payload()
    payload["ownerScope"] = {"type": "user", "value": "attacker"}

    snapshot = service.create_durable_snapshot(payload, owner_id="user-a")

    assert snapshot["ownerScope"] == {"type": "user", "value": "user-a"}
    assert service.get_durable_snapshot(snapshot["snapshotId"], owner_id="attacker") is None


def test_cross_owner_same_snapshot_id_and_evidence_are_isolated(tmp_path: Path) -> None:
    db = _db(tmp_path)
    service = ScenarioBaselineSnapshotService(repository=ScenarioBaselineSnapshotRepository(db))

    user_a = service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")
    user_b = service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-b")

    assert user_a["snapshotId"] == user_b["snapshotId"]
    assert user_a["ownerScope"] == {"type": "user", "value": "user-a"}
    assert user_b["ownerScope"] == {"type": "user", "value": "user-b"}
    assert user_a["contentHash"] != user_b["contentHash"]
    assert service.get_durable_snapshot(user_a["snapshotId"], owner_id="user-a") == user_a
    assert service.get_durable_snapshot(user_b["snapshotId"], owner_id="user-b") == user_b
    with db.get_session() as session:
        assert session.query(ScenarioBaselineSnapshotRow).count() == 2


def test_durable_snapshot_rejects_same_id_with_different_content(tmp_path: Path) -> None:
    db = _db(tmp_path)
    service = ScenarioBaselineSnapshotService(repository=ScenarioBaselineSnapshotRepository(db))
    original = service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")
    changed = _durable_ready_payload()
    changed["asOf"] = "2026-07-07T09:45:00Z"
    changed["source"]["asOf"] = "2026-07-07T09:45:00Z"

    with pytest.raises(ScenarioBaselineSnapshotStorageError, match="immutable_snapshot_conflict"):
        service.create_durable_snapshot(changed, owner_id="user-a")

    assert service.get_durable_snapshot(original["snapshotId"], owner_id="user-a") == original
    with db.get_session() as session:
        assert session.query(ScenarioBaselineSnapshotRow).count() == 1


def test_same_content_create_is_idempotent(tmp_path: Path) -> None:
    service = _service(tmp_path)

    first = service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")
    second = service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")

    assert second == first


def test_repository_fails_closed_for_corrupt_or_tampered_rows(tmp_path: Path) -> None:
    db = _db(tmp_path)
    service = ScenarioBaselineSnapshotService(repository=ScenarioBaselineSnapshotRepository(db))
    snapshot = service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")

    with db.session_scope() as session:
        row = session.query(ScenarioBaselineSnapshotRow).filter_by(snapshot_id=snapshot["snapshotId"]).one()
        row.payload_json = "not-json"

    with pytest.raises(ScenarioBaselineSnapshotStorageError, match="payload_corrupt"):
        service.get_durable_snapshot(snapshot["snapshotId"], owner_id="user-a")

    with db.session_scope() as session:
        row = session.query(ScenarioBaselineSnapshotRow).filter_by(snapshot_id=snapshot["snapshotId"]).one()
        payload = copy.deepcopy(snapshot)
        payload["contentHash"] = "sha256:" + "0" * 64
        row.payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    with pytest.raises(ScenarioBaselineSnapshotStorageError, match="content_hash_mismatch"):
        service.get_durable_snapshot(snapshot["snapshotId"], owner_id="user-a")


def test_repository_fails_closed_for_missing_owner_or_timestamp(tmp_path: Path) -> None:
    db = _db(tmp_path)
    service = ScenarioBaselineSnapshotService(repository=ScenarioBaselineSnapshotRepository(db))
    snapshot = service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")

    for key, error in (("ownerScope", "owner_missing"), ("asOf", "as_of_missing"), ("createdAt", "created_at_missing")):
        with db.session_scope() as session:
            row = session.query(ScenarioBaselineSnapshotRow).filter_by(snapshot_id=snapshot["snapshotId"]).one()
            payload = copy.deepcopy(snapshot)
            payload.pop(key)
            row.payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

        with pytest.raises(ScenarioBaselineSnapshotStorageError, match=error):
            service.get_durable_snapshot(snapshot["snapshotId"], owner_id="user-a")

        with db.session_scope() as session:
            row = session.query(ScenarioBaselineSnapshotRow).filter_by(snapshot_id=snapshot["snapshotId"]).one()
            row.payload_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_repository_rejects_durable_snapshot_without_input_refs(tmp_path: Path) -> None:
    service = _service(tmp_path)
    payload = _durable_ready_payload(snapshot_id="baseline-missing-input-refs")
    payload["inputSnapshotRefs"] = []

    with pytest.raises(ScenarioBaselineSnapshotStorageError, match="input_refs_invalid"):
        service.create_durable_snapshot(payload, owner_id="user-a")


def test_repository_fails_closed_for_malformed_timestamp_or_volatility_authority(tmp_path: Path) -> None:
    db = _db(tmp_path)
    service = ScenarioBaselineSnapshotService(repository=ScenarioBaselineSnapshotRepository(db))
    payload = _durable_ready_payload(snapshot_id="baseline-vix-malformed")
    payload["source"]["volatilityAuthoritySnapshot"] = {
        "snapshotId": "volatility:VIX:fred:VIXCLS:2026-07-07T09:30:00Z",
        "authorityState": "official",
        "coverageState": "available",
        "proxyFallback": False,
        "consumerEligibility": {"marketOverview": True, "liquidity": True, "scenarioBaseline": True},
        "scoreEligibility": {"allowed": False, "reason": "volatility_snapshot_score_default_closed"},
    }
    snapshot = service.create_durable_snapshot(payload, owner_id="user-a")

    with db.session_scope() as session:
        row = session.query(ScenarioBaselineSnapshotRow).filter_by(snapshot_id=snapshot["snapshotId"]).one()
        tampered = copy.deepcopy(snapshot)
        tampered["createdAt"] = "not-a-timestamp"
        row.payload_json = json.dumps(tampered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    with pytest.raises(ScenarioBaselineSnapshotStorageError, match="created_at_invalid"):
        service.get_durable_snapshot(snapshot["snapshotId"], owner_id="user-a")

    with db.session_scope() as session:
        row = session.query(ScenarioBaselineSnapshotRow).filter_by(snapshot_id=snapshot["snapshotId"]).one()
        tampered = copy.deepcopy(snapshot)
        tampered["source"]["volatilityAuthoritySnapshot"]["consumerEligibility"]["scenarioBaseline"] = "yes"
        row.payload_json = json.dumps(tampered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    with pytest.raises(ScenarioBaselineSnapshotStorageError):
        service.get_durable_snapshot(snapshot["snapshotId"], owner_id="user-a")


def test_repository_fails_closed_for_malformed_readiness_state(tmp_path: Path) -> None:
    db = _db(tmp_path)
    service = ScenarioBaselineSnapshotService(repository=ScenarioBaselineSnapshotRepository(db))
    snapshot = service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")

    with db.session_scope() as session:
        row = session.query(ScenarioBaselineSnapshotRow).filter_by(snapshot_id=snapshot["snapshotId"]).one()
        tampered = copy.deepcopy(snapshot)
        tampered["readinessState"] = "ready_enough"
        row.payload_json = json.dumps(tampered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    with pytest.raises(ScenarioBaselineSnapshotStorageError, match="readiness_invalid"):
        service.get_durable_snapshot(snapshot["snapshotId"], owner_id="user-a")


def test_failed_write_rolls_back_without_partial_row(tmp_path: Path) -> None:
    db = _db(tmp_path)
    repo = ScenarioBaselineSnapshotRepository(db)
    service = ScenarioBaselineSnapshotService(repository=repo)
    original_session_scope = db.session_scope

    def failing_session_scope():
        context = original_session_scope()
        session = context.__enter__()

        def fail_commit():
            raise RuntimeError("forced commit failure")

        session.commit = fail_commit

        class _FailingContext:
            def __enter__(self):
                return session

            def __exit__(self, exc_type, exc, tb):
                return context.__exit__(exc_type, exc, tb)

        return _FailingContext()

    db.session_scope = failing_session_scope
    with pytest.raises(RuntimeError, match="forced commit failure"):
        service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")

    db.session_scope = original_session_scope
    assert service.get_durable_snapshot("baseline-durable-us-open", owner_id="user-a") is None


def test_latest_durable_snapshot_orders_by_as_of_then_created_and_snapshot_id(tmp_path: Path) -> None:
    service = _service(tmp_path)
    early = _durable_ready_payload(snapshot_id="baseline-early")
    early["createdAt"] = "2026-07-07T09:31:00Z"
    early["asOf"] = "2026-07-07T09:30:00Z"
    early["source"]["asOf"] = "2026-07-07T09:30:00Z"
    later = _durable_ready_payload(snapshot_id="baseline-later")
    later["createdAt"] = "2026-07-07T09:32:00Z"
    later["asOf"] = "2026-07-07T09:45:00Z"
    later["source"]["asOf"] = "2026-07-07T09:45:00Z"

    service.create_durable_snapshot(later, owner_id="user-a")
    service.create_durable_snapshot(early, owner_id="user-a")

    latest = service.get_latest_durable_snapshot(scope={"type": "market", "value": "US"}, owner_id="user-a")
    assert latest["snapshotId"] == "baseline-later"


def test_volatility_authority_snapshot_survives_durable_round_trip(tmp_path: Path) -> None:
    service = _service(tmp_path)
    payload = _durable_ready_payload(snapshot_id="baseline-vix-official-durable")
    payload["source"]["volatilityAuthoritySnapshot"] = {
        "snapshotId": "volatility:VIX:fred:VIXCLS:2026-07-07T09:30:00Z",
        "authorityState": "official",
        "coverageState": "available",
        "proxyFallback": False,
        "consumerEligibility": {"marketOverview": True, "liquidity": True, "scenarioBaseline": True},
        "scoreEligibility": {"allowed": True, "reason": "should-remain-closed"},
    }

    snapshot = service.create_durable_snapshot(payload, owner_id="user-a")
    loaded = service.get_durable_snapshot(snapshot["snapshotId"], owner_id="user-a")

    assert loaded is not None
    volatility = loaded["source"]["volatilityAuthoritySnapshot"]
    assert volatility["authorityState"] == "official"
    assert volatility["consumerEligibility"]["scenarioBaseline"] is True
    assert volatility["scoreEligibility"] == {
        "allowed": False,
        "reason": "should-remain-closed",
    }


def test_request_supplied_static_sample_or_stale_durable_baselines_remain_observation_only(tmp_path: Path) -> None:
    service = _service(tmp_path)
    payload = _durable_ready_payload(snapshot_id="baseline-request-supplied")
    payload["source"] = {
        "dataState": "request_supplied",
        "freshness": "stale",
        "asOf": "2026-07-06T09:30:00Z",
        "sourceAuthorityAllowed": True,
    }
    payload["sourceAuthoritySummary"] = {"state": "observation_only", "allowed": False}
    payload["freshnessSummary"] = {"state": "stale", "asOf": "2026-07-06T09:30:00Z"}

    snapshot = service.create_durable_snapshot(payload, owner_id="user-a")

    assert snapshot["status"] == "partial"
    assert snapshot["readinessState"] == "observation_only"
    assert snapshot["source"]["dataState"] == "request_supplied"
    assert snapshot["source"]["freshness"] == "stale"
    assert snapshot["sourceAuthoritySummary"]["state"] == "observation_only"
    assert snapshot["freshnessSummary"]["state"] == "stale"
    assert snapshot["observationOnly"] is True
    assert snapshot["comparisonReady"] is False
