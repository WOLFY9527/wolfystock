# -*- coding: utf-8 -*-
"""Offline bridge from Alpha Factory factor research to backtest research inputs."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any, Mapping, Sequence

from api.v1.schemas.factors import FactorObservation, normalize_factor_id
from src.services.factor_experiment_manifest import FactorExperimentManifest
from src.services.factor_research_report import FactorResearchReport


BACKTEST_FACTOR_RESEARCH_BRIDGE_CONTRACT_KIND = "backtest_factor_research_input_bridge"
BACKTEST_FACTOR_RESEARCH_BRIDGE_CONTRACT_VERSION = "v1"
DEFAULT_FACTOR_BUCKET_COUNT = 3


@dataclass(frozen=True, slots=True)
class _NormalizedObservation:
    factor_id: str
    symbol: str
    value: float
    as_of: str
    as_of_dt: datetime
    percentile: float | None
    z_score: float | None
    source_name: str
    source_type: str


def build_factor_research_backtest_inputs(
    *,
    observations: Sequence[FactorObservation | Mapping[str, Any] | object] | None = None,
    research_report: FactorResearchReport | Mapping[str, Any] | object | None = None,
    experiment_manifest: FactorExperimentManifest | Mapping[str, Any] | object | None = None,
    as_of: Any = None,
    window: Mapping[str, Any] | None = None,
    bucket_count: int = DEFAULT_FACTOR_BUCKET_COUNT,
    max_symbols: int | None = None,
) -> dict[str, Any]:
    """Build deterministic backtest research inputs without running backtests."""

    normalized_observations = [_normalize_observation(item) for item in list(observations or ())]
    report_payload = _coerce_report_payload(research_report)
    manifest_payload = _coerce_manifest_payload(experiment_manifest)
    resolved_as_of = _resolve_as_of(
        explicit_as_of=as_of,
        manifest_payload=manifest_payload,
        report_payload=report_payload,
        observations=normalized_observations,
    )
    resolved_as_of_dt = _parse_iso_datetime(resolved_as_of["value"], end_of_day=True) if resolved_as_of["value"] else None

    usable_observations, future_observations = _split_usable_observations(
        observations=normalized_observations,
        as_of_dt=resolved_as_of_dt,
    )
    latest_observations = _latest_observations(usable_observations)
    scored_by_factor = _score_observations_by_factor(latest_observations)
    ranked_symbols = _build_ranked_symbols(scored_by_factor, max_symbols=max_symbols)
    factor_buckets = _build_factor_buckets(scored_by_factor, bucket_count=bucket_count)

    missing_data_reasons = _build_missing_data_reasons(
        usable_observations=usable_observations,
        latest_observations=latest_observations,
        future_observations=future_observations,
        manifest_payload=manifest_payload,
        report_payload=report_payload,
    )
    factor_universe = _build_factor_universe(
        latest_observations=latest_observations,
        report_payload=report_payload,
        manifest_payload=manifest_payload,
    )
    window_payload = _resolve_window(
        explicit_window=window,
        manifest_payload=manifest_payload,
        report_payload=report_payload,
        observations=usable_observations,
    )
    no_lookahead_guard = _build_no_lookahead_guard(
        as_of=resolved_as_of["value"],
        input_count=len(normalized_observations),
        usable_count=len(usable_observations),
        future_count=len(future_observations),
    )
    bridge_payload = {
        "contract_kind": BACKTEST_FACTOR_RESEARCH_BRIDGE_CONTRACT_KIND,
        "contract_version": BACKTEST_FACTOR_RESEARCH_BRIDGE_CONTRACT_VERSION,
        "state": _resolve_state(ranked_symbols=ranked_symbols, missing_data_reasons=missing_data_reasons),
        "offline_only": True,
        "factor_universe": factor_universe,
        "ranked_symbols": ranked_symbols,
        "factor_buckets": factor_buckets,
        "as_of": resolved_as_of,
        "window": window_payload,
        "no_lookahead_guard": no_lookahead_guard,
        "missing_data_reasons": missing_data_reasons,
        "execution_semantics": _execution_semantics(),
        "contract_metadata": build_factor_research_backtest_bridge_metadata(),
    }
    bridge_payload["reproducibility"] = _build_reproducibility(
        observations=normalized_observations,
        report_payload=report_payload,
        manifest_payload=manifest_payload,
        ranked_symbols=ranked_symbols,
        factor_buckets=factor_buckets,
        as_of=resolved_as_of,
        window=window_payload,
        no_lookahead_guard=no_lookahead_guard,
    )
    return bridge_payload


def build_factor_research_backtest_bridge_metadata() -> dict[str, Any]:
    return {
        "contract_kind": BACKTEST_FACTOR_RESEARCH_BRIDGE_CONTRACT_KIND,
        "contract_version": BACKTEST_FACTOR_RESEARCH_BRIDGE_CONTRACT_VERSION,
        "input_source": "caller_supplied_factor_research_only",
        "ranking_policy": "average_caller_supplied_factor_scores",
        "bucket_policy": "per_factor_score_quantile_buckets",
        "no_lookahead_policy": "exclude_observations_after_as_of",
        "result_usage": "backtest_research_input_scaffold",
        "automatic_backtest_run": False,
        "optimizer_executed": False,
        "strategy_execution_count": 0,
        "engine_math_changed": False,
        "provider_behavior_changed": False,
        "database_migration_required": False,
        "api_response_shapes_changed": False,
        "frontend_runtime_wiring_changed": False,
    }


def _normalize_observation(value: FactorObservation | Mapping[str, Any] | object) -> _NormalizedObservation:
    if isinstance(value, FactorObservation):
        observation = value
    else:
        raw = value.get("observation", value) if isinstance(value, Mapping) else getattr(value, "observation", value)
        if isinstance(raw, FactorObservation):
            observation = raw
        elif isinstance(raw, Mapping):
            observation = FactorObservation.model_validate(raw)
        else:
            payload = {
                key: _field(raw, key)
                for key in (
                    "factor_id",
                    "symbol",
                    "value",
                    "source_name",
                    "source_type",
                    "as_of",
                    "observed_at",
                    "freshness_status",
                    "confidence",
                    "is_fallback",
                    "is_stale",
                    "is_partial",
                    "percentile",
                    "z_score",
                    "basis",
                    "evidences",
                )
                if _field(raw, key) is not None
            }
            observation = FactorObservation.model_validate(payload)

    return _NormalizedObservation(
        factor_id=observation.factor_id,
        symbol=observation.symbol,
        value=float(observation.value),
        as_of=observation.as_of,
        as_of_dt=_parse_iso_datetime(observation.as_of, end_of_day=False),
        percentile=float(observation.percentile) if observation.percentile is not None else None,
        z_score=float(observation.z_score) if observation.z_score is not None else None,
        source_name=observation.source_name,
        source_type=observation.source_type,
    )


def _coerce_report_payload(value: FactorResearchReport | Mapping[str, Any] | object | None) -> dict[str, Any]:
    if value is None:
        return {}
    return {
        "window": _normalize_window_like(_field(value, "window")),
        "factor_coverage": [
            _normalize_factor_coverage_item(item)
            for item in _list_from(_field(value, "factor_coverage"))
        ],
        "missing_data_reasons": [
            _normalize_missing_reason(item, source="factor_research_report")
            for item in _list_from(_field(value, "missing_data_reasons"))
        ],
        "warnings": _normalize_text_list(_field(value, "warnings")),
    }


def _coerce_manifest_payload(value: FactorExperimentManifest | Mapping[str, Any] | object | None) -> dict[str, Any]:
    if value is None:
        return {}
    raw = value.to_dict() if isinstance(value, FactorExperimentManifest) else value
    return {
        "experiment_id": _optional_text(_field(raw, "experiment_id")),
        "schema_version": _optional_text(_field(raw, "schema_version")),
        "factor_ids": _normalize_factor_ids(_list_from(_field(raw, "factor_ids"))),
        "universe_id": _optional_text(_field(raw, "universe_id")),
        "symbols": _normalize_symbols(_list_from(_field(raw, "symbols"))),
        "as_of": _optional_text(_field(raw, "as_of")),
        "window": _normalize_window_like(_field(raw, "window")),
        "input_fingerprints": _normalize_fingerprint_list(_list_from(_field(raw, "input_fingerprints"))),
        "output_content_hash": _optional_text(_field(raw, "output_content_hash")),
        "warnings": _normalize_text_list(_field(raw, "warnings")),
    }


def _split_usable_observations(
    *,
    observations: Sequence[_NormalizedObservation],
    as_of_dt: datetime | None,
) -> tuple[list[_NormalizedObservation], list[_NormalizedObservation]]:
    if as_of_dt is None:
        return list(observations), []
    usable: list[_NormalizedObservation] = []
    future: list[_NormalizedObservation] = []
    for observation in observations:
        if observation.as_of_dt <= as_of_dt:
            usable.append(observation)
        else:
            future.append(observation)
    return usable, future


def _latest_observations(observations: Sequence[_NormalizedObservation]) -> list[_NormalizedObservation]:
    latest: dict[tuple[str, str], _NormalizedObservation] = {}
    for item in sorted(
        observations,
        key=lambda row: (row.factor_id, row.symbol, row.as_of_dt, row.source_name, row.value),
    ):
        latest[(item.factor_id, item.symbol)] = item
    return sorted(latest.values(), key=lambda row: (row.factor_id, row.symbol))


def _score_observations_by_factor(
    observations: Sequence[_NormalizedObservation],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[_NormalizedObservation]] = {}
    for item in observations:
        grouped.setdefault(item.factor_id, []).append(item)

    result: dict[str, list[dict[str, Any]]] = {}
    for factor_id in sorted(grouped):
        rows = sorted(grouped[factor_id], key=lambda item: (-item.value, item.symbol, item.as_of))
        rank_scores: dict[str, float] = {}
        denominator = max(len(rows) - 1, 1)
        for index, row in enumerate(rows):
            rank_scores[row.symbol] = 1.0 if len(rows) == 1 else 1.0 - (index / denominator)

        factor_scores: list[dict[str, Any]] = []
        for row in sorted(grouped[factor_id], key=lambda item: item.symbol):
            score, basis = _observation_score(row, rank_scores.get(row.symbol, 0.0))
            factor_scores.append(
                {
                    "factor_id": factor_id,
                    "symbol": row.symbol,
                    "score": _round(score),
                    "basis": basis,
                    "as_of": row.as_of,
                    "raw_value": _round(row.value),
                }
            )
        result[factor_id] = sorted(factor_scores, key=lambda item: (-float(item["score"]), item["symbol"]))
    return result


def _observation_score(observation: _NormalizedObservation, rank_score: float) -> tuple[float, str]:
    if observation.percentile is not None:
        return _clamp(observation.percentile), "percentile"
    if observation.z_score is not None:
        return _clamp(0.5 + (observation.z_score / 6.0)), "z_score_scaled"
    return _clamp(rank_score), "value_rank"


def _build_ranked_symbols(
    scored_by_factor: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    max_symbols: int | None,
) -> list[dict[str, Any]]:
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for factor_id in sorted(scored_by_factor):
        for item in scored_by_factor[factor_id]:
            by_symbol.setdefault(str(item["symbol"]), []).append(
                {
                    "factor_id": str(item["factor_id"]),
                    "score": float(item["score"]),
                    "basis": str(item["basis"]),
                    "as_of": str(item["as_of"]),
                }
            )

    ranked: list[dict[str, Any]] = []
    for symbol, factor_scores in by_symbol.items():
        ordered_scores = sorted(factor_scores, key=lambda item: item["factor_id"])
        score = sum(item["score"] for item in ordered_scores) / len(ordered_scores)
        ranked.append(
            {
                "symbol": symbol,
                "score": _round(score),
                "factor_count": len(ordered_scores),
                "factor_scores": ordered_scores,
                "ranking_policy": "average_caller_supplied_factor_scores",
            }
        )

    ranked = sorted(ranked, key=lambda item: (-float(item["score"]), item["symbol"]))
    if max_symbols is not None:
        ranked = ranked[: max(0, int(max_symbols))]
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return [
        {
            "rank": item["rank"],
            "symbol": item["symbol"],
            "score": item["score"],
            "factor_count": item["factor_count"],
            "factor_scores": item["factor_scores"],
            "ranking_policy": item["ranking_policy"],
        }
        for item in ranked
    ]


def _build_factor_buckets(
    scored_by_factor: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    bucket_count: int,
) -> list[dict[str, Any]]:
    resolved_bucket_count = max(1, int(bucket_count or DEFAULT_FACTOR_BUCKET_COUNT))
    factor_buckets: list[dict[str, Any]] = []
    for factor_id in sorted(scored_by_factor):
        rows = sorted(scored_by_factor[factor_id], key=lambda item: (-float(item["score"]), str(item["symbol"])))
        buckets: list[list[Mapping[str, Any]]] = [[] for _ in range(resolved_bucket_count)]
        for index, row in enumerate(rows):
            bucket_index = min(resolved_bucket_count - 1, int(index * resolved_bucket_count / max(len(rows), 1)))
            buckets[bucket_index].append(row)

        factor_buckets.append(
            {
                "factor_id": factor_id,
                "bucket_count": resolved_bucket_count,
                "bucket_policy": "per_factor_score_quantile_buckets",
                "buckets": [
                    _build_bucket_payload(bucket_index=index, rows=bucket_rows, bucket_count=resolved_bucket_count)
                    for index, bucket_rows in enumerate(buckets, start=1)
                ],
            }
        )
    return factor_buckets


def _build_bucket_payload(
    *,
    bucket_index: int,
    rows: Sequence[Mapping[str, Any]],
    bucket_count: int,
) -> dict[str, Any]:
    scores = [float(row["score"]) for row in rows]
    return {
        "bucket": _bucket_label(bucket_index=bucket_index, bucket_count=bucket_count),
        "bucket_index": bucket_index,
        "symbols": [str(row["symbol"]) for row in rows],
        "count": len(rows),
        "score_range": {
            "min": _round(min(scores)) if scores else None,
            "max": _round(max(scores)) if scores else None,
        },
    }


def _build_factor_universe(
    *,
    latest_observations: Sequence[_NormalizedObservation],
    report_payload: Mapping[str, Any],
    manifest_payload: Mapping[str, Any],
) -> dict[str, Any]:
    observed_factor_ids = sorted({item.factor_id for item in latest_observations})
    report_coverage = {
        str(item.get("factor_id")): item
        for item in list(report_payload.get("factor_coverage") or [])
        if item.get("factor_id")
    }
    manifest_factor_ids = list(manifest_payload.get("factor_ids") or [])
    factor_ids = sorted({*observed_factor_ids, *report_coverage.keys(), *manifest_factor_ids})
    observed_symbols = sorted({item.symbol for item in latest_observations})
    manifest_symbols = list(manifest_payload.get("symbols") or [])
    symbols = sorted({*observed_symbols, *manifest_symbols})

    coverage: list[dict[str, Any]] = []
    observations_by_factor: dict[str, list[_NormalizedObservation]] = {}
    for item in latest_observations:
        observations_by_factor.setdefault(item.factor_id, []).append(item)
    for factor_id in factor_ids:
        items = observations_by_factor.get(factor_id, [])
        report_item = report_coverage.get(factor_id, {})
        coverage.append(
            {
                "factor_id": factor_id,
                "state": "available" if items else "metadata_only",
                "observation_count": len(items),
                "symbol_count": len({item.symbol for item in items}),
                "report_observation_count": int(report_item.get("observation_count") or 0),
                "report_symbol_count": int(report_item.get("symbol_count") or 0),
                "manifest_included": factor_id in manifest_factor_ids,
            }
        )

    return {
        "factor_ids": factor_ids,
        "factor_count": len(factor_ids),
        "symbols": symbols,
        "symbol_count": len(symbols),
        "universe_id": manifest_payload.get("universe_id"),
        "coverage": coverage,
        "source_sections": _source_sections(report_payload=report_payload, manifest_payload=manifest_payload, observations=latest_observations),
    }


def _build_missing_data_reasons(
    *,
    usable_observations: Sequence[_NormalizedObservation],
    latest_observations: Sequence[_NormalizedObservation],
    future_observations: Sequence[_NormalizedObservation],
    manifest_payload: Mapping[str, Any],
    report_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    if not usable_observations:
        reasons.append({"section": "observations", "reason": "no_usable_factor_observations"})

    for item in sorted(future_observations, key=lambda row: (row.as_of, row.factor_id, row.symbol)):
        reasons.append(
            {
                "section": "observations",
                "reason": "future_observation_excluded",
                "factor_id": item.factor_id,
                "symbol": item.symbol,
                "context": item.as_of,
            }
        )

    latest_keys = {(item.factor_id, item.symbol) for item in latest_observations}
    observations_by_factor: dict[str, set[str]] = {}
    for item in latest_observations:
        observations_by_factor.setdefault(item.factor_id, set()).add(item.symbol)

    manifest_factor_ids = list(manifest_payload.get("factor_ids") or [])
    manifest_symbols = list(manifest_payload.get("symbols") or [])
    for factor_id in manifest_factor_ids:
        if factor_id not in observations_by_factor:
            reasons.append(
                {
                    "section": "observations",
                    "reason": "manifest_factor_missing_observations",
                    "factor_id": factor_id,
                }
            )
        for symbol in manifest_symbols:
            if (factor_id, symbol) not in latest_keys:
                reasons.append(
                    {
                        "section": "observations",
                        "reason": "manifest_symbol_missing_factor_observation",
                        "factor_id": factor_id,
                        "symbol": symbol,
                    }
                )

    reasons.extend(copy.deepcopy(list(report_payload.get("missing_data_reasons") or [])))
    return _dedupe_reasons(reasons)


def _resolve_as_of(
    *,
    explicit_as_of: Any,
    manifest_payload: Mapping[str, Any],
    report_payload: Mapping[str, Any],
    observations: Sequence[_NormalizedObservation],
) -> dict[str, Any]:
    explicit = _optional_text(explicit_as_of)
    if explicit:
        return {"value": explicit, "source": "explicit"}
    manifest_as_of = _optional_text(manifest_payload.get("as_of"))
    if manifest_as_of:
        return {"value": manifest_as_of, "source": "experiment_manifest"}
    report_window = report_payload.get("window") if isinstance(report_payload.get("window"), Mapping) else {}
    report_end = _optional_text(report_window.get("end"))
    if report_end:
        return {"value": report_end, "source": "factor_research_report"}
    if observations:
        return {"value": max(observations, key=lambda item: item.as_of_dt).as_of, "source": "observations_max_as_of"}
    return {"value": None, "source": "unavailable"}


def _resolve_window(
    *,
    explicit_window: Mapping[str, Any] | None,
    manifest_payload: Mapping[str, Any],
    report_payload: Mapping[str, Any],
    observations: Sequence[_NormalizedObservation],
) -> dict[str, Any]:
    explicit = _normalize_window_like(explicit_window)
    if explicit:
        source = "explicit"
        resolved = explicit
    elif manifest_payload.get("window"):
        source = "experiment_manifest"
        resolved = dict(manifest_payload["window"])
    elif report_payload.get("window"):
        source = "factor_research_report"
        resolved = dict(report_payload["window"])
    else:
        source = "observations"
        as_ofs = sorted({item.as_of for item in observations})
        resolved = {
            "start": as_ofs[0] if as_ofs else None,
            "end": as_ofs[-1] if as_ofs else None,
        }

    return {
        "start": resolved.get("start"),
        "end": resolved.get("end"),
        "label": resolved.get("label"),
        "source": source,
        "observation_count": len(observations),
    }


def _build_no_lookahead_guard(
    *,
    as_of: str | None,
    input_count: int,
    usable_count: int,
    future_count: int,
) -> dict[str, Any]:
    if not as_of:
        state = "unresolved_as_of"
    elif future_count:
        state = "guarded_future_rows_excluded"
    else:
        state = "guarded"
    return {
        "policy": "exclude_observations_after_as_of",
        "as_of": as_of,
        "input_observation_count": input_count,
        "usable_observation_count": usable_count,
        "future_observations_excluded": future_count,
        "future_observations_used": 0,
        "lookahead_bias_state": state,
    }


def _build_reproducibility(
    *,
    observations: Sequence[_NormalizedObservation],
    report_payload: Mapping[str, Any],
    manifest_payload: Mapping[str, Any],
    ranked_symbols: Sequence[Mapping[str, Any]],
    factor_buckets: Sequence[Mapping[str, Any]],
    as_of: Mapping[str, Any],
    window: Mapping[str, Any],
    no_lookahead_guard: Mapping[str, Any],
) -> dict[str, Any]:
    input_payload = {
        "observations": [
            {
                "factor_id": item.factor_id,
                "symbol": item.symbol,
                "value": _round(item.value),
                "as_of": item.as_of,
                "percentile": _round(item.percentile) if item.percentile is not None else None,
                "z_score": _round(item.z_score) if item.z_score is not None else None,
                "source_name": item.source_name,
                "source_type": item.source_type,
            }
            for item in sorted(observations, key=lambda row: (row.factor_id, row.symbol, row.as_of, row.value))
        ],
        "factor_research_report": _json_safe(report_payload),
        "factor_experiment_manifest": _json_safe(manifest_payload),
        "as_of": dict(as_of),
        "window": dict(window),
        "no_lookahead_guard": dict(no_lookahead_guard),
    }
    fingerprints = list(manifest_payload.get("input_fingerprints") or [])
    if manifest_payload.get("output_content_hash"):
        fingerprints.append(
            {
                "kind": "factor_experiment_manifest",
                "name": manifest_payload.get("experiment_id") or "factor_experiment_manifest",
                "fingerprint": manifest_payload.get("output_content_hash"),
            }
        )
    return {
        "fingerprints": _normalize_fingerprint_list(fingerprints),
        "input_content_hash": _hash_payload(input_payload),
        "ranked_symbols_hash": _hash_payload(list(ranked_symbols)),
        "factor_buckets_hash": _hash_payload(list(factor_buckets)),
        "hash_algorithm": "sha256",
    }


def _execution_semantics() -> dict[str, Any]:
    return {
        "execution_mode": "caller_supplied_research_inputs_only",
        "strategy_execution_count": 0,
        "automatic_backtest_run": False,
        "optimizer_executed": False,
        "provider_calls_executed": False,
        "engine_math_changed": False,
        "api_response_shapes_changed": False,
        "database_migration_required": False,
        "frontend_runtime_wiring_changed": False,
    }


def _resolve_state(
    *,
    ranked_symbols: Sequence[Mapping[str, Any]],
    missing_data_reasons: Sequence[Mapping[str, Any]],
) -> str:
    if not ranked_symbols:
        return "insufficient_data"
    blocking_reasons = {
        "manifest_factor_missing_observations",
        "manifest_symbol_missing_factor_observation",
        "no_usable_factor_observations",
    }
    if any(str(item.get("reason")) in blocking_reasons for item in missing_data_reasons):
        return "ready_with_missing_data"
    return "ready"


def _normalize_factor_coverage_item(value: Any) -> dict[str, Any]:
    return {
        "factor_id": _optional_text(_field(value, "factor_id")),
        "observation_count": int(_field(value, "observation_count") or 0),
        "symbol_count": int(_field(value, "symbol_count") or 0),
        "window": _normalize_window_like(_field(value, "window")),
    }


def _normalize_missing_reason(value: Any, *, source: str) -> dict[str, Any]:
    payload = {
        "section": _optional_text(_field(value, "section")),
        "reason": _optional_text(_field(value, "reason")),
        "factor_id": _optional_text(_field(value, "factor_id")),
        "symbol": _optional_text(_field(value, "symbol")),
        "context": _optional_text(_field(value, "context")),
        "source": source,
    }
    return {key: child for key, child in payload.items() if child is not None}


def _normalize_factor_ids(values: Sequence[Any]) -> list[str]:
    result: set[str] = set()
    for value in values:
        text = _optional_text(value)
        if text:
            result.add(normalize_factor_id(text))
    return sorted(result)


def _normalize_symbols(values: Sequence[Any]) -> list[str]:
    return sorted({text.upper() for value in values if (text := _optional_text(value))})


def _normalize_window_like(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        candidate = {
            "start": _field(value, "as_of_start") or _field(value, "start"),
            "end": _field(value, "as_of_end") or _field(value, "end"),
            "label": _field(value, "label"),
        }
    else:
        candidate = dict(value)
    aliases = {
        "as_of_start": "start",
        "as_of_end": "end",
        "end_at": "end",
        "end_date": "end",
        "lookback": "label",
        "lookback_window": "label",
        "start_at": "start",
        "start_date": "start",
    }
    resolved: dict[str, Any] = {}
    for raw_key, raw_value in candidate.items():
        key = re.sub(r"[^a-z0-9]+", "_", str(raw_key or "").strip().lower()).strip("_")
        key = aliases.get(key, key)
        if key not in {"start", "end", "label"}:
            continue
        text = _optional_text(raw_value)
        if text is not None:
            resolved[key] = text
    return dict(sorted(resolved.items(), key=lambda item: item[0]))


def _normalize_fingerprint_list(values: Sequence[Any]) -> list[dict[str, Any]]:
    fingerprints: list[dict[str, Any]] = []
    for item in values:
        normalized = _normalize_mapping(item)
        if normalized:
            fingerprints.append(normalized)
    return sorted(
        fingerprints,
        key=lambda item: (
            str(item.get("kind") or ""),
            str(item.get("name") or ""),
            str(item.get("fingerprint") or ""),
            _canonical_json(item),
        ),
    )


def _normalize_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in sorted(value.items(), key=lambda item: str(item[0])):
        key = str(raw_key or "").strip()
        if not key:
            continue
        child = _json_safe(raw_value)
        if child in ({}, [], "", None):
            continue
        normalized[key] = child
    return normalized


def _normalize_text_list(value: Any) -> list[str]:
    return sorted({text for item in _list_from(value) if (text := _optional_text(item))})


def _dedupe_reasons(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        item = {key: child for key, child in value.items() if child is not None}
        fingerprint = _canonical_json(item)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(item)
    return sorted(
        deduped,
        key=lambda item: (
            str(item.get("section") or ""),
            str(item.get("reason") or ""),
            str(item.get("factor_id") or ""),
            str(item.get("symbol") or ""),
            str(item.get("context") or ""),
            str(item.get("source") or ""),
        ),
    )


def _source_sections(
    *,
    report_payload: Mapping[str, Any],
    manifest_payload: Mapping[str, Any],
    observations: Sequence[_NormalizedObservation],
) -> list[str]:
    sections: list[str] = []
    if observations:
        sections.append("observations")
    if report_payload:
        sections.append("factor_research_report")
    if manifest_payload:
        sections.append("factor_experiment_manifest")
    return sections


def _parse_iso_datetime(value: Any, *, end_of_day: bool) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("as_of must be an ISO date or datetime string")
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed_date = date.fromisoformat(normalized)
        parsed = datetime.combine(parsed_date, time.max if end_of_day else time.min)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _list_from(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Sequence):
        return list(value)
    return [value]


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _bucket_label(*, bucket_index: int, bucket_count: int) -> str:
    if bucket_count == 1:
        return "all"
    if bucket_count == 2:
        return "top" if bucket_index == 1 else "bottom"
    if bucket_count == 3:
        return ("top", "middle", "bottom")[bucket_index - 1]
    return f"bucket_{bucket_index}"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return _round(value) if math.isfinite(value) else None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        return {
            str(key): child
            for key, raw_child in sorted(value.items(), key=lambda item: str(item[0]))
            if (child := _json_safe(raw_child)) not in ({}, [], "", None)
        }
    if isinstance(value, (list, tuple, set)):
        return sorted(
            [child for item in value if (child := _json_safe(item)) not in ({}, [], "", None)],
            key=_canonical_json,
        )
    if hasattr(value, "to_dict"):
        return _json_safe(value.to_dict())
    if hasattr(value, "__dict__"):
        return _json_safe(vars(value))
    return str(value).strip()


def _hash_payload(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


__all__ = [
    "BACKTEST_FACTOR_RESEARCH_BRIDGE_CONTRACT_KIND",
    "BACKTEST_FACTOR_RESEARCH_BRIDGE_CONTRACT_VERSION",
    "DEFAULT_FACTOR_BUCKET_COUNT",
    "build_factor_research_backtest_bridge_metadata",
    "build_factor_research_backtest_inputs",
]
