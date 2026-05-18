# -*- coding: utf-8 -*-
"""Contract tests for offline Alpha Factory experiment manifests."""

from __future__ import annotations

import json
import random
import subprocess
import sys

from src.services.factor_experiment_manifest import (
    FACTOR_EXPERIMENT_MANIFEST_SCHEMA_VERSION,
    FactorExperimentManifest,
    build_factor_experiment_manifest,
)


def _fingerprint(
    *,
    kind: str,
    name: str,
    fingerprint: str,
    version: str | None = None,
    as_of: str | None = None,
    rows: int | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "kind": kind,
        "name": name,
        "fingerprint": fingerprint,
    }
    if version is not None:
        payload["version"] = version
    if as_of is not None:
        payload["as_of"] = as_of
    if rows is not None:
        payload["rows"] = rows
    if extra:
        payload.update(extra)
    return payload


def _build_manifest(*, shuffled: bool = False) -> FactorExperimentManifest:
    factor_ids = [
        "Trend.Trend-Strength 20D",
        "momentum.momentum_21d",
    ]
    symbols = ["msft", "AAPL", "aapl"]
    horizons = ["10d", "1d", "5d"]
    fingerprints = [
        _fingerprint(
            kind="universe",
            name="alpha_core_us",
            fingerprint="uni:2026-05-18",
            version="v3",
            rows=125,
        ),
        _fingerprint(
            kind="observations",
            name="relative_strength_panel",
            fingerprint="obs:8f2c6fd3",
            as_of="2026-05-18",
            rows=502,
        ),
    ]
    warnings = ["missing_1d_return_tail", "partial_symbol_overlap"]

    if shuffled:
        random.Random(7).shuffle(factor_ids)
        random.Random(11).shuffle(symbols)
        random.Random(13).shuffle(horizons)
        random.Random(17).shuffle(fingerprints)
        random.Random(19).shuffle(warnings)

    return build_factor_experiment_manifest(
        factor_ids=factor_ids,
        universe_id="alpha-core-us",
        symbols=symbols,
        as_of="2026-05-18",
        window={"end": "2026-05-18", "start": "2026-05-01", "label": "1m"},
        horizons=horizons,
        neutralization_method="sector_residual",
        exposure_settings={
            "gross_limit": 1.0,
            "net_limit": 0.35,
            "hedges": ["beta", "sector"],
        },
        metrics_settings={
            "winsorize_limits": {"upper": 0.98, "lower": 0.02},
            "rank_ic": True,
        },
        input_fingerprints=fingerprints,
        created_at="2026-05-18T08:00:00Z",
        generated_at="2026-05-18T08:05:00Z",
        warnings=warnings,
    )


def test_manifest_ids_and_hashes_are_deterministic_for_same_normalized_inputs() -> None:
    first = _build_manifest(shuffled=False)
    second = _build_manifest(shuffled=True)

    assert first.schema_version == FACTOR_EXPERIMENT_MANIFEST_SCHEMA_VERSION
    assert first.experiment_id == second.experiment_id
    assert first.output_content_hash == second.output_content_hash
    assert first.to_dict() == second.to_dict()


def test_manifest_export_uses_stable_ordering_for_lists_and_nested_sections() -> None:
    manifest = _build_manifest(shuffled=True)
    exported = manifest.to_dict()

    assert exported["factor_ids"] == [
        "momentum.momentum_21d",
        "trend.trend_strength_20d",
    ]
    assert exported["symbols"] == ["AAPL", "MSFT"]
    assert exported["horizons"] == ["1d", "5d", "10d"]
    assert exported["warnings"] == [
        "missing_1d_return_tail",
        "partial_symbol_overlap",
    ]
    assert [item["name"] for item in exported["input_fingerprints"]] == [
        "alpha_core_us",
        "relative_strength_panel",
    ]
    assert list(exported["metrics_settings"]["winsorize_limits"]) == ["lower", "upper"]

    serialized = manifest.to_json()
    assert json.loads(serialized) == exported


def test_manifest_handles_missing_optional_sections_without_fabricating_runtime_state() -> None:
    manifest = build_factor_experiment_manifest(
        factor_ids=["relative_strength.relative_strength_63d"],
        symbols=["aapl"],
        created_at="2026-05-18T08:00:00Z",
    )
    exported = manifest.to_dict()

    assert exported["universe_id"] is None
    assert exported["as_of"] is None
    assert exported["window"] == {}
    assert exported["horizons"] == []
    assert exported["neutralization_method"] is None
    assert exported["exposure_settings"] == {}
    assert exported["metrics_settings"] == {}
    assert exported["input_fingerprints"] == []
    assert exported["warnings"] == []
    assert exported["output_content_hash"]


def test_changed_inputs_change_experiment_identity_and_output_hash() -> None:
    baseline = _build_manifest()
    changed = build_factor_experiment_manifest(
        factor_ids=["momentum.momentum_21d", "trend.trend_strength_20d"],
        universe_id="alpha-core-us",
        symbols=["AAPL", "MSFT"],
        as_of="2026-05-18",
        window={"start": "2026-05-01", "end": "2026-05-18", "label": "1m"},
        horizons=["1d", "5d", "20d"],
        neutralization_method="sector_residual",
        exposure_settings={"gross_limit": 1.0, "hedges": ["beta", "sector"], "net_limit": 0.35},
        metrics_settings={"rank_ic": True, "winsorize_limits": {"lower": 0.02, "upper": 0.98}},
        input_fingerprints=[
            _fingerprint(kind="universe", name="alpha_core_us", fingerprint="uni:2026-05-18", version="v3", rows=125),
            _fingerprint(
                kind="observations",
                name="relative_strength_panel",
                fingerprint="obs:8f2c6fd3",
                as_of="2026-05-18",
                rows=502,
            ),
        ],
        created_at="2026-05-18T08:00:00Z",
        generated_at="2026-05-18T08:05:00Z",
        warnings=["missing_1d_return_tail", "partial_symbol_overlap"],
    )

    assert baseline.experiment_id != changed.experiment_id
    assert baseline.output_content_hash != changed.output_content_hash


def test_manifest_strips_raw_provider_and_runtime_payload_like_fields() -> None:
    manifest = build_factor_experiment_manifest(
        factor_ids=["momentum.momentum_21d"],
        universe_id="alpha-core-us",
        symbols=["AAPL"],
        as_of="2026-05-18",
        horizons=["1d"],
        exposure_settings={
            "gross_limit": 1.0,
            "debug_payload": {"request_body": {"token": "secret"}, "safe": "kept"},
        },
        metrics_settings={
            "rank_ic": True,
            "runtime_snapshot": {"response_body": {"cookie": "leak"}, "window": "5d"},
        },
        input_fingerprints=[
            _fingerprint(
                kind="observations",
                name="panel",
                fingerprint="obs:123",
                extra={
                    "raw_payload": {"provider_response": "leak"},
                    "runtime_dump": {"stack_trace": "boom"},
                    "safe_hint": "kept",
                },
            )
        ],
        warnings=["review_needed"],
    )

    exported = manifest.to_dict()
    serialized = manifest.to_json().lower()

    assert exported["exposure_settings"] == {
        "debug_payload": {"safe": "kept"},
        "gross_limit": 1.0,
    }
    assert exported["metrics_settings"] == {
        "rank_ic": True,
        "runtime_snapshot": {"window": "5d"},
    }
    assert exported["input_fingerprints"] == [
        {
            "fingerprint": "obs:123",
            "kind": "observations",
            "name": "panel",
            "safe_hint": "kept",
        }
    ]
    for marker in ("raw_payload", "provider_response", "request_body", "response_body", "runtime_dump", "stack_trace", "token", "cookie"):
        assert marker not in serialized


def test_factor_experiment_manifest_import_has_no_scanner_backtest_or_provider_side_effects() -> None:
    script = """
import json
import src.services.factor_experiment_manifest
blocked = [
    "src.services.market_scanner_service",
    "src.services.rule_backtest_service",
    "src.services.backtest_service",
    "api.v1.endpoints.scanner",
    "data_provider",
]
print(json.dumps({name: name in __import__('sys').modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}
