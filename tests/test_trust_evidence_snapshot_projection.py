# -*- coding: utf-8 -*-
"""Tests for the pure TrustEvidenceSnapshotV1 backend projection helper."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.schemas.trust_evidence import TrustEvidenceSnapshotV1
from src.services.trust_evidence_projection import build_trust_evidence_snapshot_v1


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "src/services/trust_evidence_projection.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "urllib3",
    "yfinance",
    "src.core",
    "src.repositories",
    "src.storage",
    "src.services.market_cache",
    "src.services.market_scanner_service",
    "src.services.provider",
    "src.services.provider_circuit_observer",
    "src.services.scanner",
)


def _base_kwargs() -> dict[str, Any]:
    return {
        "surface_key": "market_overview",
        "entity_key": "market_overview.hero",
        "generated_at": datetime(2026, 6, 9, 13, 30, tzinfo=timezone.utc),
        "as_of": datetime(2026, 6, 9, 13, 0, tzinfo=timezone.utc),
        "availability_state": "available",
        "freshness_state": "fresh",
        "source_class": "official_public",
        "has_fallback": False,
        "is_stale": False,
        "is_partial": False,
        "is_synthetic": False,
        "is_admin_only_detail": False,
        "consumer_state": "AVAILABLE",
        "consumer_message_key": "trust_evidence.available",
        "consumer_badge_keys": ["source_current"],
        "admin_diagnostic_refs": ["trust-evidence:market-overview:macro-panel"],
    }


@pytest.mark.parametrize(
    ("label", "overrides", "expected"),
    [
        (
            "available",
            {},
            {
                "availabilityState": "available",
                "freshnessState": "fresh",
                "sourceClass": "official_public",
                "consumerState": "AVAILABLE",
                "consumerMessageKey": "trust_evidence.available",
                "consumerBadgeKeys": ["source_current"],
            },
        ),
        (
            "delayed",
            {
                "availability_state": "delayed",
                "freshness_state": "delayed",
                "source_class": "licensed_authorized",
                "consumer_state": "DELAYED",
                "consumer_message_key": "trust_evidence.delayed",
                "consumer_badge_keys": ["source_delayed"],
            },
            {
                "availabilityState": "delayed",
                "freshnessState": "delayed",
                "sourceClass": "licensed_authorized",
                "consumerState": "DELAYED",
                "consumerMessageKey": "trust_evidence.delayed",
                "consumerBadgeKeys": ["source_delayed"],
            },
        ),
        (
            "partial",
            {
                "availability_state": "partial",
                "freshness_state": "partial",
                "is_partial": True,
                "consumer_state": "PARTIAL",
                "consumer_message_key": "trust_evidence.partial",
                "consumer_badge_keys": ["source_partial"],
            },
            {
                "availabilityState": "partial",
                "freshnessState": "partial",
                "sourceClass": "official_public",
                "consumerState": "PARTIAL",
                "consumerMessageKey": "trust_evidence.partial",
                "consumerBadgeKeys": ["source_partial"],
            },
        ),
        (
            "stale",
            {
                "availability_state": "delayed",
                "freshness_state": "stale",
                "source_class": "local_cache",
                "is_stale": True,
                "consumer_state": "DELAYED",
                "consumer_message_key": "trust_evidence.stale",
                "consumer_badge_keys": ["source_stale"],
            },
            {
                "availabilityState": "delayed",
                "freshnessState": "stale",
                "sourceClass": "local_cache",
                "consumerState": "DELAYED",
                "consumerMessageKey": "trust_evidence.stale",
                "consumerBadgeKeys": ["source_stale"],
            },
        ),
        (
            "fallback",
            {
                "availability_state": "partial",
                "freshness_state": "fallback",
                "source_class": "local_cache",
                "has_fallback": True,
                "consumer_state": "PARTIAL",
                "consumer_message_key": "trust_evidence.fallback",
                "consumer_badge_keys": ["source_fallback"],
            },
            {
                "availabilityState": "partial",
                "freshnessState": "fallback",
                "sourceClass": "local_cache",
                "consumerState": "PARTIAL",
                "consumerMessageKey": "trust_evidence.fallback",
                "consumerBadgeKeys": ["source_fallback"],
            },
        ),
        (
            "observation-only",
            {
                "availability_state": "observation_only",
                "freshness_state": "synthetic",
                "source_class": "synthetic",
                "is_synthetic": True,
                "consumer_state": "OBSERVATION_ONLY",
                "consumer_message_key": "trust_evidence.observation_only",
                "consumer_badge_keys": ["observation_only"],
            },
            {
                "availabilityState": "observation_only",
                "freshnessState": "synthetic",
                "sourceClass": "synthetic",
                "consumerState": "OBSERVATION_ONLY",
                "consumerMessageKey": "trust_evidence.observation_only",
                "consumerBadgeKeys": ["observation_only"],
            },
        ),
        (
            "unavailable",
            {
                "entity_key": None,
                "as_of": None,
                "availability_state": "unavailable",
                "freshness_state": "unavailable",
                "source_class": "unknown",
                "consumer_state": "UNAVAILABLE",
                "consumer_message_key": "trust_evidence.unavailable",
                "consumer_badge_keys": ["source_unavailable"],
                "admin_diagnostic_refs": [],
            },
            {
                "availabilityState": "unavailable",
                "freshnessState": "unavailable",
                "sourceClass": "unknown",
                "consumerState": "UNAVAILABLE",
                "consumerMessageKey": "trust_evidence.unavailable",
                "consumerBadgeKeys": ["source_unavailable"],
            },
        ),
    ],
)
def test_build_trust_evidence_snapshot_v1_builds_bounded_state_examples(
    label: str,
    overrides: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    kwargs = {**_base_kwargs(), **overrides}

    snapshot = build_trust_evidence_snapshot_v1(**kwargs)
    payload = snapshot.model_dump(mode="json")

    assert isinstance(snapshot, TrustEvidenceSnapshotV1), label
    assert payload["contractVersion"] == "trust_evidence_snapshot_v1"
    assert payload["surfaceKey"] == kwargs["surface_key"]
    assert payload["entityKey"] == kwargs["entity_key"]
    assert payload["generatedAt"] == "2026-06-09T13:30:00Z"
    assert payload["asOf"] == (
        None if kwargs["as_of"] is None else "2026-06-09T13:00:00Z"
    )
    for key, value in expected.items():
        assert payload[key] == value


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("availability_state", "fallback_source"),
        ("freshness_state", "cache_stale"),
        ("source_class", "yfinance_proxy"),
        ("consumer_state", "routeRejected"),
        ("consumer_message_key", "providerRuntime.cache_stale"),
        ("consumer_message_key", "trust_evidence.cache_stale"),
        ("consumer_message_key", "trust_evidence.polygon"),
        ("consumer_badge_keys", ["source_current", "polygon"]),
    ],
)
def test_build_trust_evidence_snapshot_v1_rejects_raw_provider_debug_reason_codes(
    field_name: str,
    bad_value: object,
) -> None:
    kwargs = {**_base_kwargs(), field_name: bad_value}

    with pytest.raises(ValidationError):
        build_trust_evidence_snapshot_v1(**kwargs)


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def test_trust_evidence_projection_helper_imports_stay_pure_and_inert() -> None:
    imports = _helper_imports()

    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)
