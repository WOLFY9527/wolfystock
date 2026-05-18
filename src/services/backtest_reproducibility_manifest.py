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
_MANIFEST_ID_PREFIX = "bt_repro_manifest_"
_REDACTED_TEXT = "[REDACTED_SENSITIVE_TEXT]"

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
        base_payload: dict[str, Any] = {
            "schema_version": BACKTEST_REPRODUCIBILITY_MANIFEST_SCHEMA_VERSION,
            "generated_at": _normalize_generated_at(generated_at),
            "strategy_type": str(strategy_type or ""),
            "strategy_fingerprint": strategy_fp,
            "data_window": _normalize_mapping(data_window),
            "symbols": _normalize_symbols(symbols),
            "universe": _normalize_universe(universe),
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
