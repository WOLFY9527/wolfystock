# -*- coding: utf-8 -*-
"""Offline tests for the inert data coverage surface registry."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from src.services.data_coverage_surface_registry import (
    DATA_COVERAGE_SURFACE_REGISTRY,
    DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD,
    DATA_COVERAGE_SURFACE_REGISTRY_VERSION,
    AdminVisibilityIntent,
    ConsumerVisibilityIntent,
    SurfaceAudience,
    SurfaceRegistryEntry,
)


def test_registry_exports_expected_surfaces_and_known_entry_shape() -> None:
    assert DATA_COVERAGE_SURFACE_REGISTRY_VERSION == "data_coverage_surface_registry_v1"
    assert len(DATA_COVERAGE_SURFACE_REGISTRY) == 9
    assert {entry.surface_id for entry in DATA_COVERAGE_SURFACE_REGISTRY} == {
        "market_overview",
        "liquidity",
        "rotation",
        "scanner",
        "single_stock",
        "watchlist",
        "portfolio",
        "backtest",
        "options",
    }

    market_overview = DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD[("market_overview", "market_regime")]

    assert market_overview == SurfaceRegistryEntry(
        surface_id="market_overview",
        route_id="/zh/market-overview",
        audience=SurfaceAudience.CONSUMER,
        field_key="market_regime",
        evidence_family="market_regime",
        required_posture_notes=(
            "static_registry_only",
            "observation_only_until_separate_authority_review",
            "consumer_projection_must_hide_provider_diagnostics",
        ),
        consumer_visibility_intent=ConsumerVisibilityIntent.SAFE_PRODUCT_STATUS_ONLY,
        admin_visibility_intent=AdminVisibilityIntent.GATED_DIAGNOSTIC_METADATA_ALLOWED,
    )


def test_registry_is_stable_unique_and_immutable() -> None:
    keys = [(entry.surface_id, entry.field_key) for entry in DATA_COVERAGE_SURFACE_REGISTRY]

    assert len(keys) == len(set(keys))
    assert len(DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD) == len(DATA_COVERAGE_SURFACE_REGISTRY)

    for entry in DATA_COVERAGE_SURFACE_REGISTRY:
        assert isinstance(entry, SurfaceRegistryEntry)
        assert isinstance(entry.required_posture_notes, tuple)
        assert entry.required_posture_notes
        assert all(note == note.strip() for note in entry.required_posture_notes)


def test_unknown_surface_or_field_lookup_fails_closed() -> None:
    assert DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD.get(("unknown_surface", "market_regime")) is None
    assert DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD.get(("market_overview", "unknown_field")) is None
    assert DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD.get(("unknown_surface", "unknown_field")) is None


def test_module_is_pure_and_inert() -> None:
    module_path = Path("src/services/data_coverage_surface_registry.py")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")

    assert imported_modules <= {"__future__", "dataclasses", "enum", "typing"}

    script = """
import json
import sys
before = set(sys.modules)
import src.services.data_coverage_surface_registry  # noqa: F401
after = set(sys.modules) - before
blocked = sorted(
    name for name in after
    if (
        name.startswith("data_provider")
        or name.startswith("api")
        or name.startswith("apps")
        or name.startswith("requests")
        or name.startswith("sqlalchemy")
        or name.startswith("duckdb")
        or name.startswith("aiohttp")
        or name.startswith("fastapi")
    )
)
print(json.dumps(blocked))
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "[]"
