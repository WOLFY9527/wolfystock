# -*- coding: utf-8 -*-
"""Contracts for the offline backtest reproducibility manifest helper."""

from __future__ import annotations

import json

import pytest

from src.services.backtest_reproducibility_manifest import (
    BACKTEST_REPRODUCIBILITY_MANIFEST_SCHEMA_VERSION,
    BacktestReproducibilityManifest,
    build_backtest_reproducibility_manifest,
    build_backtest_price_basis_contract,
)


def _verified_lineage(**overrides):
    payload = {
        "manifest_version": "backtest_dataset_reproducibility_manifest.v1",
        "dataset_id": "rule_backtest:local_us_parquet:AAPL",
        "content_identity": "fixture-content-v1",
        "source_lineage": {
            "source": "local_us_parquet",
            "authority_status": "allowed",
        },
        "price_basis": build_backtest_price_basis_contract(
            basis_id="raw_ohlc",
            benchmark_basis_id="raw_ohlc",
            strategy_price_fields=("close", "high", "low"),
            benchmark_price_fields=("close",),
            corporate_action_adjustment_mode="none",
        ),
        "calendar_identity": {
            "contract_version": "backtest_trading_calendar.v1",
            "state": "verified",
            "calendar_id": "XNYS",
            "timezone": "America/New_York",
            "session_source": "exchange_calendar",
        },
        "universe_membership_mode": "single_symbol_request",
        "pit_membership_available": True,
        "missing_bar_policy": {
            "policy": "fail_closed",
            "required_price_fields_available": True,
        },
        "date_range": {
            "requested": {"start": "2024-01-01", "end": "2024-01-31", "sessions": 21},
            "effective": {"start": "2024-01-02", "end": "2024-01-31", "sessions": 21},
        },
        "warmup_history": {
            "required_sessions": 20,
            "available_sessions": 20,
            "state": "sufficient",
        },
        "symbol_coverage": {
            "requested_symbols": ["AAPL"],
            "covered_symbols": ["AAPL"],
        },
        "freshness_as_of": "2024-01-31",
    }
    payload.update(overrides)
    return payload


def _manifest(**overrides):
    payload = {
        "generated_at": "2026-05-18T00:00:00Z",
        "strategy_type": "moving_average_crossover",
        "strategy": {
            "signal": {
                "slow_period": 20,
                "fast_period": 5,
            }
        },
        "data_window": {
            "end": "2024-12-31",
            "start": "2024-01-01",
            "bar_count": 252,
        },
        "symbols": ["MSFT", "AAPL", "AAPL"],
        "universe": {
            "universe_id": "fixture-us-tech",
            "selection_rule": "fixture_symbols_only",
        },
        "execution_cost_assumptions": {
            "slippage_bps": 5,
            "commission_bps": 1,
        },
        "walk_forward_config": {
            "test_window": 12,
            "train_window": 24,
            "step": 12,
        },
        "parameter_stability_config": {
            "parameters": {
                "slow_period": [20, 50],
                "fast_period": [5, 10],
            }
        },
        "factor_research_input": {
            "factor_set_id": "quality-v1",
            "neutralization": "sector",
        },
        "engine_contract_flags": {
            "provider_calls_executed": False,
            "engine_math_changed": False,
        },
        "warnings": ["fixture_warning"],
    }
    payload.update(overrides)
    return build_backtest_reproducibility_manifest(**payload)


def test_manifest_ids_and_hashes_are_deterministic_for_equivalent_inputs() -> None:
    first = _manifest()
    second = _manifest(
        symbols=["AAPL", "MSFT"],
        data_window={
            "bar_count": 252,
            "start": "2024-01-01",
            "end": "2024-12-31",
        },
        strategy={
            "signal": {
                "fast_period": 5,
                "slow_period": 20,
            }
        },
    )

    assert isinstance(first, BacktestReproducibilityManifest)
    assert first.to_dict()["schema_version"] == BACKTEST_REPRODUCIBILITY_MANIFEST_SCHEMA_VERSION
    assert second.to_dict()["manifest_id"] == first.to_dict()["manifest_id"]
    assert second.to_dict()["content_hash"] == first.to_dict()["content_hash"]
    assert second.to_json() == first.to_json()


def test_changed_research_inputs_change_content_hash_and_manifest_id() -> None:
    base = _manifest()
    changed = _manifest(strategy={"signal": {"fast_period": 6, "slow_period": 20}})

    assert changed.to_dict()["strategy_fingerprint"] != base.to_dict()["strategy_fingerprint"]
    assert changed.to_dict()["content_hash"] != base.to_dict()["content_hash"]
    assert changed.to_dict()["manifest_id"] != base.to_dict()["manifest_id"]


def test_price_basis_rejects_strategy_and_benchmark_basis_mismatch() -> None:
    with pytest.raises(ValueError, match="strategy and benchmark price basis must match"):
        build_backtest_price_basis_contract(
            basis_id="raw_ohlc",
            strategy_price_fields=("close",),
            benchmark_price_fields=("adjusted_close",),
            corporate_action_adjustment_mode="none",
            benchmark_basis_id="split_dividend_adjusted_close",
        )
    with pytest.raises(ValueError, match="unsupported benchmark price basis: missing"):
        build_backtest_price_basis_contract(
            basis_id="raw_ohlc",
            benchmark_basis_id="",
            strategy_price_fields=("close",),
            benchmark_price_fields=("close",),
            corporate_action_adjustment_mode="none",
        )


def test_price_basis_rejects_adjusted_field_under_raw_basis() -> None:
    with pytest.raises(ValueError, match="raw_ohlc does not allow price fields: adjusted_close"):
        build_backtest_price_basis_contract(
            basis_id="raw_ohlc",
            benchmark_basis_id="raw_ohlc",
            strategy_price_fields=("adjusted_close",),
            benchmark_price_fields=("close",),
            corporate_action_adjustment_mode="none",
        )


def test_manifest_hash_binds_price_basis_calendar_range_and_warmup_truth() -> None:
    base = _manifest(dataset_lineage=_verified_lineage()).to_dict()
    changed_price_basis = _manifest(
        dataset_lineage=_verified_lineage(
            price_basis=build_backtest_price_basis_contract(
                basis_id="split_dividend_adjusted_close",
                benchmark_basis_id="split_dividend_adjusted_close",
                strategy_price_fields=("adjusted_close",),
                benchmark_price_fields=("adjusted_close",),
                corporate_action_adjustment_mode="split_dividend_adjusted_once",
            )
        )
    ).to_dict()
    changed_calendar = _manifest(
        dataset_lineage=_verified_lineage(
            calendar_identity={
                "contract_version": "backtest_trading_calendar.v1",
                "state": "verified",
                "calendar_id": "XNAS",
                "timezone": "America/New_York",
                "session_source": "exchange_calendar",
            }
        )
    ).to_dict()
    changed_range = _manifest(
        dataset_lineage=_verified_lineage(
            date_range={
                "requested": {"start": "2024-01-01", "end": "2024-01-31", "sessions": 21},
                "effective": {"start": "2024-01-03", "end": "2024-01-31", "sessions": 20},
            }
        )
    ).to_dict()
    changed_warmup = _manifest(
        dataset_lineage=_verified_lineage(
            warmup_history={
                "required_sessions": 30,
                "available_sessions": 30,
                "state": "sufficient",
            }
        )
    ).to_dict()

    assert base["dataset_lineage"]["state"] == "available"
    assert changed_price_basis["content_hash"] != base["content_hash"]
    assert changed_calendar["content_hash"] != base["content_hash"]
    assert changed_range["content_hash"] != base["content_hash"]
    assert changed_warmup["content_hash"] != base["content_hash"]


def test_manifest_fails_closed_for_unverified_calendar_and_insufficient_warmup() -> None:
    manifest = _manifest(
        dataset_lineage=_verified_lineage(
            calendar_identity={
                "contract_version": "backtest_trading_calendar.v1",
                "state": "observed_bars_only",
                "calendar_id": "XNYS",
                "timezone": "America/New_York",
                "session_source": "observed_market_bars",
            },
            warmup_history={
                "required_sessions": 20,
                "available_sessions": 19,
                "state": "insufficient",
            },
        )
    ).to_dict()

    lineage = manifest["dataset_lineage"]
    assert lineage["state"] == "blocked_data_basis"
    assert lineage["fail_closed"] is True
    assert "calendar_identity_unverified" in lineage["reason_codes"]
    assert "warmup_history_insufficient" in lineage["reason_codes"]


def test_missing_optional_sections_are_explicit_without_placeholder_hashes() -> None:
    manifest = _manifest(
        walk_forward_config=None,
        parameter_stability_config=None,
        factor_research_input=None,
        warnings=None,
    ).to_dict()

    assert manifest["walk_forward_config_fingerprint"] == {
        "state": "not_provided",
        "hash_sha256": None,
    }
    assert manifest["parameter_stability_config_fingerprint"] == {
        "state": "not_provided",
        "hash_sha256": None,
    }
    assert manifest["factor_research_input_fingerprint"] == {
        "state": "not_provided",
        "hash_sha256": None,
    }
    assert manifest["warnings"] == []


def test_export_ordering_is_stable_and_json_compatible() -> None:
    manifest = _manifest(
        generated_at=None,
        engine_contract_flags={
            "z_flag": True,
            "a_flag": False,
        },
        warnings=["z-warning", "a-warning", "z-warning"],
    )

    payload = manifest.to_dict()
    assert list(payload) == [
        "schema_version",
        "manifest_id",
        "generated_at",
        "strategy_type",
        "strategy_fingerprint",
        "data_window",
        "symbols",
        "universe",
        "dataset_lineage",
        "execution_cost_assumptions",
        "execution_cost_assumptions_fingerprint",
        "walk_forward_config_fingerprint",
        "parameter_stability_config_fingerprint",
        "factor_research_input_fingerprint",
        "engine_contract_flags",
        "warnings",
        "content_hash",
    ]
    assert payload["symbols"] == ["AAPL", "MSFT"]
    assert list(payload["engine_contract_flags"]) == ["a_flag", "z_flag"]
    assert payload["warnings"] == ["a-warning", "z-warning"]
    assert json.loads(manifest.to_json()) == payload


def test_dataset_lineage_missing_fails_closed_without_identity() -> None:
    manifest = _manifest(dataset_lineage=None).to_dict()

    assert manifest["dataset_lineage"] == {
        "state": "unknown",
        "fail_closed": True,
        "reason_codes": ["dataset_lineage_missing"],
    }


def test_dataset_lineage_represents_no_pit_membership_without_pretending_availability() -> None:
    manifest = _manifest(
        dataset_lineage={
            "manifest_version": "backtest_dataset_reproducibility_manifest.v1",
            "dataset_id": "rule_backtest:database_cache:AAPL",
            "content_identity": "fixture-content-v1",
            "source_lineage": {"source": "database_cache", "authority_status": "allowed"},
            "adjusted_basis": {"state": "unknown"},
            "calendar_identity": {"state": "unknown", "timezone": "Asia/Shanghai"},
            "universe_membership_mode": "single_symbol_request",
            "pit_membership_available": False,
            "missing_bar_policy": {"policy": "fail_closed_for_professional_claims"},
            "date_range": {"requested_start": "2024-01-01", "requested_end": "2024-01-31"},
            "symbol_coverage": {"requested_symbols": ["AAPL"], "covered_symbols": ["AAPL"]},
            "freshness_as_of": "2024-01-31",
            "reason_codes": ["adjusted_basis_unknown", "calendar_identity_unknown"],
        },
    ).to_dict()

    lineage = manifest["dataset_lineage"]
    assert lineage["dataset_id"] == "rule_backtest:database_cache:AAPL"
    assert lineage["state"] == "blocked_unknown_lineage"
    assert lineage["pit_membership_available"] is False
    assert lineage["fail_closed"] is True
    assert lineage["missing_fields"] == ["price_basis", "warmup_history"]
    assert "price_basis_missing" in lineage["reason_codes"]
    assert "warmup_history_missing" in lineage["reason_codes"]
    assert manifest["content_hash"]


def test_sensitive_payloads_prompts_and_runtime_dumps_are_stripped() -> None:
    manifest = _manifest(
        strategy={
            "signal": {"fast_period": 5, "slow_period": 20},
            "prompt": "PROMPT_VALUE_SHOULD_NOT_LEAK",
            "raw_provider_payload": {"body": "RAW_PROVIDER_PAYLOAD_SHOULD_NOT_LEAK"},
            "notes": "TOKEN_VALUE_SHOULD_NOT_LEAK",
        },
        execution_cost_assumptions={
            "commission_bps": 1,
            "provider_payload": {"secret": "SECRET_VALUE_SHOULD_NOT_LEAK"},
            "cookie": "COOKIE_VALUE_SHOULD_NOT_LEAK",
        },
        factor_research_input={
            "factor_set_id": "quality-v1",
            "runtime_dump": {"stack": "RUNTIME_DUMP_SHOULD_NOT_LEAK"},
            "api_token": "API_TOKEN_SHOULD_NOT_LEAK",
        },
        warnings=["clean warning", "token warning should be redacted"],
    )

    serialized = manifest.to_json()
    assert "PROMPT_VALUE_SHOULD_NOT_LEAK" not in serialized
    assert "RAW_PROVIDER_PAYLOAD_SHOULD_NOT_LEAK" not in serialized
    assert "TOKEN_VALUE_SHOULD_NOT_LEAK" not in serialized
    assert "SECRET_VALUE_SHOULD_NOT_LEAK" not in serialized
    assert "COOKIE_VALUE_SHOULD_NOT_LEAK" not in serialized
    assert "RUNTIME_DUMP_SHOULD_NOT_LEAK" not in serialized
    assert "API_TOKEN_SHOULD_NOT_LEAK" not in serialized
    assert "prompt" not in serialized
    assert "provider_payload" not in serialized
    assert "runtime_dump" not in serialized
    assert manifest.to_dict()["warnings"] == ["[REDACTED_SENSITIVE_TEXT]", "clean warning"]
