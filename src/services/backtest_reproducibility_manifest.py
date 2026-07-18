# -*- coding: utf-8 -*-
"""Offline reproducibility manifest helper for backtest research runs."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, is_dataclass, asdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence


BACKTEST_REPRODUCIBILITY_MANIFEST_SCHEMA_VERSION = "backtest_reproducibility_manifest.v1"
BACKTEST_PRICE_BASIS_CONTRACT_VERSION = "backtest_price_basis.v1"
_MANIFEST_ID_PREFIX = "bt_repro_manifest_"
_REDACTED_TEXT = "[REDACTED_SENSITIVE_TEXT]"
_PRICE_BASIS_ADJUSTMENT_MODES = {
    "raw_ohlc": ("none", 0),
    "split_dividend_adjusted_close": ("split_dividend_adjusted_once", 1),
}
_PRICE_BASIS_ALLOWED_FIELDS = {
    "raw_ohlc": frozenset({"open", "high", "low", "close"}),
    "split_dividend_adjusted_close": frozenset({"adjusted_close"}),
}

_SENSITIVE_KEY_TERMS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "password",
    "prompt",
    "provider_payload",
    "provider_response",
    "raw_payload",
    "raw_provider",
    "runtime_dump",
    "secret",
    "session",
    "token",
)
_SENSITIVE_TEXT_TERMS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "password",
    "prompt",
    "secret",
    "session",
    "token",
)
_SAFE_FINANCIAL_SESSION_KEYS = {
    "available_sessions",
    "observed_session_dates",
    "required_sessions",
    "session_source",
    "sessions",
    "verified_session_dates",
}


def build_backtest_price_basis_contract(
    *,
    basis_id: str,
    strategy_price_fields: Sequence[str],
    benchmark_price_fields: Sequence[str],
    corporate_action_adjustment_mode: str,
    benchmark_basis_id: str,
) -> dict[str, Any]:
    """Build the single strict representation used for backtest price basis."""

    strategy_basis = str(basis_id or "").strip()
    benchmark_basis = str(benchmark_basis_id or "").strip()
    if strategy_basis not in _PRICE_BASIS_ADJUSTMENT_MODES:
        raise ValueError(f"unsupported backtest price basis: {strategy_basis or 'missing'}")
    if benchmark_basis not in _PRICE_BASIS_ADJUSTMENT_MODES:
        raise ValueError(f"unsupported benchmark price basis: {benchmark_basis or 'missing'}")
    if strategy_basis != benchmark_basis:
        raise ValueError("strategy and benchmark price basis must match")

    strategy_fields = _strict_price_fields(strategy_price_fields, role="strategy")
    benchmark_fields = _strict_price_fields(benchmark_price_fields, role="benchmark")
    _require_price_fields_match_basis(strategy_fields, basis_id=strategy_basis)
    _require_price_fields_match_basis(benchmark_fields, basis_id=benchmark_basis)
    expected_mode, application_count = _PRICE_BASIS_ADJUSTMENT_MODES[strategy_basis]
    adjustment_mode = str(corporate_action_adjustment_mode or "").strip()
    if adjustment_mode != expected_mode:
        raise ValueError(
            f"price basis {strategy_basis} requires corporate-action mode {expected_mode}"
        )

    return {
        "contract_version": BACKTEST_PRICE_BASIS_CONTRACT_VERSION,
        "basis_id": strategy_basis,
        "strategy": {
            "basis_id": strategy_basis,
            "price_fields": strategy_fields,
        },
        "benchmark": {
            "basis_id": benchmark_basis,
            "price_fields": benchmark_fields,
        },
        "corporate_action_adjustment": {
            "mode": adjustment_mode,
            "application_count": application_count,
        },
        "compatible": True,
    }


def _strict_price_fields(values: Sequence[str], *, role: str) -> list[str]:
    if isinstance(values, (str, bytes, bytearray)):
        raise ValueError(f"{role} price fields must be a sequence of field names")
    fields = [str(value or "").strip() for value in values]
    if not fields or any(not field for field in fields):
        raise ValueError(f"{role} price fields must not be empty")
    if len(set(fields)) != len(fields):
        raise ValueError(f"{role} price fields must not contain duplicates")
    return fields


def _require_price_fields_match_basis(fields: Sequence[str], *, basis_id: str) -> None:
    disallowed = sorted(set(fields) - _PRICE_BASIS_ALLOWED_FIELDS[basis_id])
    if disallowed:
        raise ValueError(
            f"{basis_id} does not allow price fields: {', '.join(disallowed)}"
        )


@dataclass(frozen=True, slots=True)
class BacktestReproducibilityManifest:
    """Stable JSON-compatible backtest reproducibility manifest."""

    _payload: Mapping[str, Any]

    @classmethod
    def build(
        cls,
        *,
        generated_at: Any | None = None,
        strategy_type: str,
        data_window: Mapping[str, Any] | None = None,
        symbols: Sequence[Any] | None = None,
        universe: Mapping[str, Any] | str | None = None,
        dataset_lineage: Mapping[str, Any] | None = None,
        execution_cost_assumptions: Mapping[str, Any] | None = None,
        strategy: Any | None = None,
        strategy_fingerprint: Any | None = None,
        walk_forward_config: Mapping[str, Any] | None = None,
        parameter_stability_config: Mapping[str, Any] | None = None,
        factor_research_input: Mapping[str, Any] | None = None,
        engine_contract_flags: Mapping[str, Any] | None = None,
        warnings: Sequence[Any] | None = None,
    ) -> "BacktestReproducibilityManifest":
        strategy_fp = _strategy_fingerprint(
            strategy=strategy,
            explicit_fingerprint=strategy_fingerprint,
        )
        execution_assumptions = _normalize_mapping(execution_cost_assumptions)
        lineage_payload = _normalize_dataset_lineage(dataset_lineage)
        base_payload: dict[str, Any] = {
            "schema_version": BACKTEST_REPRODUCIBILITY_MANIFEST_SCHEMA_VERSION,
            "generated_at": _normalize_generated_at(generated_at),
            "strategy_type": str(strategy_type or ""),
            "strategy_fingerprint": strategy_fp,
            "data_window": _normalize_mapping(data_window),
            "symbols": _normalize_symbols(symbols),
            "universe": _normalize_universe(universe),
            "dataset_lineage": lineage_payload,
            "execution_cost_assumptions": execution_assumptions,
            "execution_cost_assumptions_fingerprint": _fingerprint_section(
                execution_assumptions,
                missing_state="empty",
            ),
            "walk_forward_config_fingerprint": _fingerprint_section(walk_forward_config),
            "parameter_stability_config_fingerprint": _fingerprint_section(parameter_stability_config),
            "factor_research_input_fingerprint": _fingerprint_section(factor_research_input),
            "engine_contract_flags": _normalize_mapping(engine_contract_flags),
            "warnings": _normalize_warnings(warnings),
        }
        content_payload = {
            key: value
            for key, value in base_payload.items()
            if key != "generated_at"
        }
        content_hash = _hash_payload(content_payload)
        payload = {
            "schema_version": base_payload["schema_version"],
            "manifest_id": f"{_MANIFEST_ID_PREFIX}{content_hash[:16]}",
            "generated_at": base_payload["generated_at"],
            "strategy_type": base_payload["strategy_type"],
            "strategy_fingerprint": base_payload["strategy_fingerprint"],
            "data_window": base_payload["data_window"],
            "symbols": base_payload["symbols"],
            "universe": base_payload["universe"],
            "dataset_lineage": base_payload["dataset_lineage"],
            "execution_cost_assumptions": base_payload["execution_cost_assumptions"],
            "execution_cost_assumptions_fingerprint": base_payload["execution_cost_assumptions_fingerprint"],
            "walk_forward_config_fingerprint": base_payload["walk_forward_config_fingerprint"],
            "parameter_stability_config_fingerprint": base_payload["parameter_stability_config_fingerprint"],
            "factor_research_input_fingerprint": base_payload["factor_research_input_fingerprint"],
            "engine_contract_flags": base_payload["engine_contract_flags"],
            "warnings": base_payload["warnings"],
            "content_hash": content_hash,
        }
        return cls(_payload=payload)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._payload))

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
        )


def build_backtest_reproducibility_manifest(
    *,
    generated_at: Any | None = None,
    strategy_type: str,
    data_window: Mapping[str, Any] | None = None,
    symbols: Sequence[Any] | None = None,
    universe: Mapping[str, Any] | str | None = None,
    dataset_lineage: Mapping[str, Any] | None = None,
    execution_cost_assumptions: Mapping[str, Any] | None = None,
    strategy: Any | None = None,
    strategy_fingerprint: Any | None = None,
    walk_forward_config: Mapping[str, Any] | None = None,
    parameter_stability_config: Mapping[str, Any] | None = None,
    factor_research_input: Mapping[str, Any] | None = None,
    engine_contract_flags: Mapping[str, Any] | None = None,
    warnings: Sequence[Any] | None = None,
) -> BacktestReproducibilityManifest:
    return BacktestReproducibilityManifest.build(
        generated_at=generated_at,
        strategy_type=strategy_type,
        data_window=data_window,
        symbols=symbols,
        universe=universe,
        dataset_lineage=dataset_lineage,
        execution_cost_assumptions=execution_cost_assumptions,
        strategy=strategy,
        strategy_fingerprint=strategy_fingerprint,
        walk_forward_config=walk_forward_config,
        parameter_stability_config=parameter_stability_config,
        factor_research_input=factor_research_input,
        engine_contract_flags=engine_contract_flags,
        warnings=warnings,
    )


def _strategy_fingerprint(*, strategy: Any | None, explicit_fingerprint: Any | None) -> dict[str, Any]:
    if explicit_fingerprint is not None:
        payload = _sanitize_json_safe(explicit_fingerprint)
        if isinstance(payload, str) and payload:
            return {
                "state": "provided",
                "source": "provided_strategy_fingerprint",
                "hash_sha256": payload,
            }
        return {
            "state": "provided",
            "source": "provided_strategy_fingerprint",
            "hash_sha256": _hash_payload(payload),
        }
    if strategy is None:
        return {
            "state": "not_provided",
            "source": None,
            "hash_sha256": None,
        }
    return {
        "state": "provided",
        "source": "strategy",
        "hash_sha256": _hash_payload(_sanitize_json_safe(strategy)),
    }


def _fingerprint_section(value: Any, *, missing_state: str = "not_provided") -> dict[str, Any]:
    if value is None:
        return {
            "state": missing_state,
            "hash_sha256": None,
        }
    sanitized = _sanitize_json_safe(value)
    if sanitized in ({}, [], ""):
        return {
            "state": "empty",
            "hash_sha256": None,
        }
    return {
        "state": "provided",
        "hash_sha256": _hash_payload(sanitized),
    }


def _normalize_generated_at(value: Any | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        resolved = value
        if resolved.tzinfo is None:
            resolved = resolved.replace(tzinfo=timezone.utc)
        resolved = resolved.astimezone(timezone.utc)
        return resolved.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _normalize_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("manifest section must be a mapping.")
    sanitized = _sanitize_json_safe(value)
    return dict(sanitized) if isinstance(sanitized, Mapping) else {}


def _normalize_universe(value: Mapping[str, Any] | str | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        return {"universe_id": _sanitize_string(value)}
    return _normalize_mapping(value)


def _normalize_dataset_lineage(value: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _normalize_mapping(value)
    if not payload:
        return {
            "state": "unknown",
            "fail_closed": True,
            "reason_codes": ["dataset_lineage_missing"],
        }

    required_fields = [
        "dataset_id",
        "content_identity",
        "source_lineage",
        "price_basis",
        "calendar_identity",
        "universe_membership_mode",
        "pit_membership_available",
        "missing_bar_policy",
        "date_range",
        "warmup_history",
        "symbol_coverage",
        "freshness_as_of",
        "manifest_version",
    ]
    missing_fields = [
        field
        for field in required_fields
        if payload.get(field) in (None, "", {}, [])
    ]
    if missing_fields:
        reason_codes = _dedupe_strings(payload.get("reason_codes"))
        reason_codes.extend(f"{field}_missing" for field in missing_fields)
        payload["reason_codes"] = sorted(set(reason_codes))
        payload["state"] = "blocked_unknown_lineage"
        payload["fail_closed"] = True
        payload["missing_fields"] = missing_fields
        return payload

    evidence_blockers = [
        *_price_basis_blockers(payload.get("price_basis")),
        *_calendar_identity_blockers(payload.get("calendar_identity")),
        *_date_range_blockers(payload.get("date_range")),
        *_warmup_history_blockers(payload.get("warmup_history")),
        *_missing_bar_policy_blockers(payload.get("missing_bar_policy")),
    ]
    if evidence_blockers:
        payload["reason_codes"] = sorted(
            set(_dedupe_strings(payload.get("reason_codes")) + evidence_blockers)
        )
        payload["state"] = "blocked_data_basis"
        payload["fail_closed"] = True
        payload["missing_fields"] = []
        payload["pit_membership_available"] = bool(payload.get("pit_membership_available"))
        return payload

    payload["pit_membership_available"] = bool(payload.get("pit_membership_available"))
    if payload["pit_membership_available"]:
        payload["state"] = "available"
    else:
        payload["state"] = str(payload.get("state") or "partial_no_pit_membership")
    payload["fail_closed"] = bool(payload.get("fail_closed", not payload["pit_membership_available"]))
    payload["reason_codes"] = _dedupe_strings(payload.get("reason_codes"))
    payload["missing_fields"] = []
    return payload


def _price_basis_blockers(value: Any) -> list[str]:
    payload = value if isinstance(value, Mapping) else {}
    if payload.get("contract_version") != BACKTEST_PRICE_BASIS_CONTRACT_VERSION:
        return ["price_basis_contract_invalid"]
    basis_id = payload.get("basis_id")
    strategy = payload.get("strategy") if isinstance(payload.get("strategy"), Mapping) else {}
    benchmark = payload.get("benchmark") if isinstance(payload.get("benchmark"), Mapping) else {}
    adjustment = (
        payload.get("corporate_action_adjustment")
        if isinstance(payload.get("corporate_action_adjustment"), Mapping)
        else {}
    )
    if basis_id not in _PRICE_BASIS_ADJUSTMENT_MODES:
        return ["price_basis_unsupported"]
    if strategy.get("basis_id") != basis_id or benchmark.get("basis_id") != basis_id:
        return ["price_basis_incompatible"]
    if payload.get("compatible") is not True:
        return ["price_basis_incompatible"]
    if not _valid_price_field_list(strategy.get("price_fields")):
        return ["strategy_price_fields_missing"]
    if not _valid_price_field_list(benchmark.get("price_fields")):
        return ["benchmark_price_fields_missing"]
    if not _price_fields_match_basis(strategy.get("price_fields"), basis_id=str(basis_id)):
        return ["strategy_price_fields_incompatible"]
    if not _price_fields_match_basis(benchmark.get("price_fields"), basis_id=str(basis_id)):
        return ["benchmark_price_fields_incompatible"]
    expected_mode, expected_count = _PRICE_BASIS_ADJUSTMENT_MODES[str(basis_id)]
    if adjustment.get("mode") != expected_mode:
        return ["corporate_action_adjustment_basis_invalid"]
    application_count = adjustment.get("application_count")
    if type(application_count) is not int or application_count != expected_count:
        return ["corporate_action_adjustment_count_invalid"]
    return []


def _valid_price_field_list(value: Any) -> bool:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return False
    fields = list(value)
    return (
        bool(fields)
        and len(set(fields)) == len(fields)
        and all(isinstance(field, str) and bool(field.strip()) for field in fields)
    )


def _price_fields_match_basis(value: Any, *, basis_id: str) -> bool:
    return set(value).issubset(_PRICE_BASIS_ALLOWED_FIELDS[basis_id])


def _calendar_identity_blockers(value: Any) -> list[str]:
    payload = value if isinstance(value, Mapping) else {}
    if payload.get("contract_version") != "backtest_trading_calendar.v1":
        return ["calendar_identity_contract_invalid"]
    required = ("calendar_id", "timezone", "session_source")
    if any(not isinstance(payload.get(field), str) or not str(payload.get(field)).strip() for field in required):
        return ["calendar_identity_missing"]
    if payload.get("state") != "verified":
        return ["calendar_identity_unverified"]
    return []


def _date_range_blockers(value: Any) -> list[str]:
    payload = value if isinstance(value, Mapping) else {}
    requested = payload.get("requested") if isinstance(payload.get("requested"), Mapping) else {}
    effective = payload.get("effective") if isinstance(payload.get("effective"), Mapping) else {}
    blockers: list[str] = []
    if requested.get("start") in (None, "") and requested.get("sessions") in (None, 0):
        blockers.append("requested_range_missing")
    if effective.get("start") in (None, "") or effective.get("end") in (None, ""):
        blockers.append("effective_range_missing")
    effective_sessions = effective.get("sessions")
    if type(effective_sessions) is not int or effective_sessions <= 0:
        blockers.append("effective_sessions_missing")
    return blockers


def _warmup_history_blockers(value: Any) -> list[str]:
    payload = value if isinstance(value, Mapping) else {}
    required = payload.get("required_sessions")
    available = payload.get("available_sessions")
    if not isinstance(required, int) or isinstance(required, bool) or required < 0:
        return ["warmup_history_invalid"]
    if not isinstance(available, int) or isinstance(available, bool) or available < 0:
        return ["warmup_history_invalid"]
    if available < required or payload.get("state") == "insufficient":
        return ["warmup_history_insufficient"]
    expected_state = "not_required" if required == 0 else "sufficient"
    if payload.get("state") != expected_state:
        return ["warmup_history_state_invalid"]
    return []


def _missing_bar_policy_blockers(value: Any) -> list[str]:
    payload = value if isinstance(value, Mapping) else {}
    if payload.get("required_price_fields_available") is not True:
        return ["required_price_fields_missing"]
    return []


def _dedupe_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        candidates = list(value)
    else:
        candidates = []
    seen: set[str] = set()
    result: list[str] = []
    for item in candidates:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _normalize_symbols(symbols: Sequence[Any] | None) -> list[str]:
    if symbols is None:
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for raw_symbol in list(symbols):
        symbol = str(raw_symbol or "").strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(symbol)
    return sorted(normalized)


def _normalize_warnings(warnings: Sequence[Any] | None) -> list[str]:
    if warnings is None:
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for warning in list(warnings):
        text = _sanitize_string(str(warning or "").strip())
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return sorted(normalized)


def _sanitize_json_safe(value: Any) -> Any:
    return _json_safe(_sanitize(value))


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_key in sorted(value.keys(), key=lambda item: str(item)):
            key = str(raw_key)
            if _is_sensitive_key(key):
                continue
            sanitized[key] = _sanitize(value[raw_key])
        return sanitized
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, set):
        return [_sanitize(item) for item in sorted(value, key=lambda item: str(item))]
    if isinstance(value, str):
        return _sanitize_string(value)
    return value


def _sanitize_string(value: str) -> str:
    lowered = value.lower()
    if any(term in lowered for term in _SENSITIVE_TEXT_TERMS):
        return _REDACTED_TEXT
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    if normalized in _SAFE_FINANCIAL_SESSION_KEYS:
        return False
    return any(term in normalized for term in _SENSITIVE_KEY_TERMS)


def _json_safe(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_safe(value[key]) for key in sorted(value.keys(), key=lambda item: str(item))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return [_json_safe(item) for item in sorted(value, key=lambda item: str(item))]
    if isinstance(value, datetime):
        resolved = value
        if resolved.tzinfo is None:
            resolved = resolved.replace(tzinfo=timezone.utc)
        return resolved.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return _json_safe(float(value))
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _hash_payload(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
