# -*- coding: utf-8 -*-
"""Offline-only experiment manifest scaffold for Alpha Factory research."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from api.v1.schemas.factors import normalize_factor_id


FACTOR_EXPERIMENT_MANIFEST_SCHEMA_VERSION = "factor_experiment_manifest.v1"

_WINDOW_ALIASES = {
    "as_of_end": "end",
    "as_of_start": "start",
    "end_at": "end",
    "end_date": "end",
    "lookback": "label",
    "lookback_window": "label",
    "start_at": "start",
    "start_date": "start",
}
_FORBIDDEN_MAPPING_KEYS = {
    "authorization",
    "cookie",
    "headers",
    "provider_payload",
    "provider_response",
    "raw_payload",
    "request_body",
    "response_body",
    "runtime_dump",
    "secret",
    "stack_trace",
    "token",
    "traceback",
}


@dataclass(frozen=True)
class FactorExperimentManifest:
    experiment_id: str
    schema_version: str
    created_at: str | None
    generated_at: str | None
    factor_ids: tuple[str, ...]
    universe_id: str | None
    symbols: tuple[str, ...]
    as_of: str | None
    window: Mapping[str, Any]
    horizons: tuple[str, ...]
    neutralization_method: str | None
    exposure_settings: Mapping[str, Any]
    metrics_settings: Mapping[str, Any]
    input_fingerprints: tuple[Mapping[str, Any], ...]
    output_content_hash: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "generated_at": self.generated_at,
            "factor_ids": list(self.factor_ids),
            "universe_id": self.universe_id,
            "symbols": list(self.symbols),
            "as_of": self.as_of,
            "window": dict(self.window),
            "horizons": list(self.horizons),
            "neutralization_method": self.neutralization_method,
            "exposure_settings": dict(self.exposure_settings),
            "metrics_settings": dict(self.metrics_settings),
            "input_fingerprints": [dict(item) for item in self.input_fingerprints],
            "output_content_hash": self.output_content_hash,
            "warnings": list(self.warnings),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_factor_experiment_manifest(
    *,
    factor_ids: Sequence[Any],
    universe_id: Any = None,
    symbols: Sequence[Any] | None = None,
    as_of: Any = None,
    window: Mapping[str, Any] | None = None,
    horizons: Sequence[Any] | None = None,
    neutralization_method: Any = None,
    exposure_settings: Mapping[str, Any] | None = None,
    metrics_settings: Mapping[str, Any] | None = None,
    input_fingerprints: Sequence[Mapping[str, Any]] | None = None,
    created_at: Any = None,
    generated_at: Any = None,
    warnings: Sequence[Any] | None = None,
) -> FactorExperimentManifest:
    """Build a deterministic offline experiment manifest from normalized inputs."""
    normalized_payload = {
        "schema_version": FACTOR_EXPERIMENT_MANIFEST_SCHEMA_VERSION,
        "created_at": _optional_text(created_at),
        "generated_at": _optional_text(generated_at),
        "factor_ids": _normalize_factor_ids(factor_ids),
        "universe_id": _optional_text(universe_id),
        "symbols": _normalize_symbols(symbols or ()),
        "as_of": _optional_text(as_of),
        "window": _normalize_window(window),
        "horizons": _normalize_horizons(horizons or ()),
        "neutralization_method": _optional_text(neutralization_method),
        "exposure_settings": _normalize_mapping(exposure_settings),
        "metrics_settings": _normalize_mapping(metrics_settings),
        "input_fingerprints": _normalize_fingerprints(input_fingerprints or ()),
        "warnings": _normalize_text_list(warnings or ()),
    }
    digest = _hash_payload(normalized_payload)
    return FactorExperimentManifest(
        experiment_id=f"fxexp_{digest[:16]}",
        schema_version=FACTOR_EXPERIMENT_MANIFEST_SCHEMA_VERSION,
        created_at=normalized_payload["created_at"],
        generated_at=normalized_payload["generated_at"],
        factor_ids=tuple(normalized_payload["factor_ids"]),
        universe_id=normalized_payload["universe_id"],
        symbols=tuple(normalized_payload["symbols"]),
        as_of=normalized_payload["as_of"],
        window=normalized_payload["window"],
        horizons=tuple(normalized_payload["horizons"]),
        neutralization_method=normalized_payload["neutralization_method"],
        exposure_settings=normalized_payload["exposure_settings"],
        metrics_settings=normalized_payload["metrics_settings"],
        input_fingerprints=tuple(normalized_payload["input_fingerprints"]),
        output_content_hash=digest,
        warnings=tuple(normalized_payload["warnings"]),
    )


def _normalize_factor_ids(values: Sequence[Any]) -> list[str]:
    normalized = {normalize_factor_id(value) for value in values if _optional_text(value)}
    if not normalized:
        raise ValueError("factor_ids must contain at least one factor id")
    return sorted(normalized)


def _normalize_symbols(values: Sequence[Any]) -> list[str]:
    normalized = {text.upper() for value in values if (text := _optional_text(value))}
    return sorted(normalized)


def _normalize_horizons(values: Sequence[Any]) -> list[str]:
    return sorted(
        {text for value in values if (text := _optional_text(value))},
        key=_horizon_sort_key,
    )


def _normalize_window(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = _normalize_window_key(raw_key)
        if key not in {"end", "label", "start"}:
            continue
        text = _optional_text(raw_value)
        if text is not None:
            normalized[key] = text
    return dict(sorted(normalized.items(), key=lambda item: item[0]))


def _normalize_window_key(value: Any) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return _WINDOW_ALIASES.get(key, key)


def _normalize_fingerprints(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in values:
        normalized_item = _normalize_mapping(item)
        if normalized_item:
            normalized.append(normalized_item)
    return sorted(
        normalized,
        key=lambda item: (
            str(item.get("name") or ""),
            str(item.get("kind") or ""),
            str(item.get("fingerprint") or ""),
            _sort_key(item),
        ),
    )


def _normalize_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in sorted(value.items(), key=lambda item: str(item[0])):
        key = str(raw_key).strip()
        if not key or _is_forbidden_key(key):
            continue
        child = _normalize_json_value(raw_value)
        if child in ({}, [], ""):
            continue
        normalized[key] = child
    return normalized


def _normalize_json_value(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        return _normalize_mapping(value)
    if isinstance(value, (list, tuple, set)):
        normalized_items = []
        for item in value:
            normalized = _normalize_json_value(item)
            if normalized in ({}, [], "", None):
                continue
            normalized_items.append(normalized)
        return sorted(normalized_items, key=_sort_key)
    return str(value).strip()


def _normalize_text_list(values: Sequence[Any]) -> list[str]:
    return sorted({text for value in values if (text := _optional_text(value))})


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _horizon_sort_key(value: str) -> tuple[int, str]:
    match = re.match(r"^(\d+)", value.lower())
    return (int(match.group(1)) if match else math.inf, value)


def _hash_payload(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _sort_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _is_forbidden_key(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized in _FORBIDDEN_MAPPING_KEYS


__all__ = [
    "FACTOR_EXPERIMENT_MANIFEST_SCHEMA_VERSION",
    "FactorExperimentManifest",
    "build_factor_experiment_manifest",
]
