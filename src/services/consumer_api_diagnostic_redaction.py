# -*- coding: utf-8 -*-
"""Consumer-safe projection for API diagnostic payloads.

This module is intentionally inert: it does not import runtime providers,
cache engines, storage, auth, settings, or API route objects.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


NO_ADVICE_DISCLOSURE = (
    "Observation-only research context; not personalized financial advice and not an instruction."
)
OBSERVATION_BOUNDARY = "Observation-only research context; no personalized action instruction."

FORBIDDEN_CONSUMER_DIAGNOSTIC_KEYS = frozenset(
    {
        "authoritydiagnostics",
        "activationhint",
        "apikeypresent",
        "attemptedat",
        "cabundlesource",
        "cache",
        "cachekey",
        "calendarassumption",
        "debug",
        "debugref",
        "diagnosticonly",
        "diagnosticref",
        "endpointhost",
        "exceptionchain",
        "exceptionclass",
        "fallbacksource",
        "forbiddenproviders",
        "freshnesspolicy",
        "internalroute",
        "localdb",
        "maxacceptedbusinesslagdays",
        "maxacceptedlagdays",
        "officialoverlayfailuredetails",
        "policyversion",
        "provider",
        "providerattempted",
        "providerclass",
        "providername",
        "providerobservation",
        "providertier",
        "raw",
        "rawjson",
        "rawpayload",
        "reasoncode",
        "reasoncodes",
        "requestedseries",
        "requestid",
        "requiredproviderclass",
        "runtime",
        "schemaversion",
        "scorecontributionallowed",
        "sourceauthoritydiagnostics",
        "sourceauthorityallowed",
        "sourceauthorityrouter",
        "sourceconfidence",
        "sourceref",
        "sourcerefs",
        "sourcetier",
        "sourcetype",
        "timeoutseconds",
        "trace",
        "traceid",
    }
)

_SAFE_ROOT_DEFAULTS = {
    "consumerSafeSourceLabel": "部分数据源暂不可用",
    "dataQualityState": "limited",
    "freshnessState": "limited",
    "observationBoundary": OBSERVATION_BOUNDARY,
    "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
}

_UNSAFE_VALUE_RE = re.compile(
    r"\b(?:provider(?:tier|name|runtime|trace|diagnostics|state|route|payload|_timeout)?|"
    r"request[-_ ]?id|trace[-_ ]?id|debug(?:ref)?|raw[-_ ]?(?:payload|json|diagnostics|result)?|"
    r"missing[-_ ]?api[-_ ]?key|api[-_ ]?key|credentials?|token|password|secret|private[-_ ]?key|\benv\b|"
    r"schema(?:version)?|source[-_ ]?(?:ref|type|tier|authority|authorityrouter)|"
    r"authoritydiagnostics|runtime|local_db|fallback_source|fallback_static|"
    r"official_public|authorized_licensed_feed|public_proxy|unofficial_proxy|"
    r"tier_1_configured|adapter_contract|fixture_only|fixture_proxy|not_decision_grade|"
    r"synthetic_fixture|marketcache|cache(?:[-_ ]?(?:key|hit|miss|state|payload))?)\b",
    re.IGNORECASE,
)
_UNSAFE_DIAGNOSTIC_VALUE_RE = re.compile(
    r"(?:^|_)(?:adapter_contract|authority|fixture_only|fixture_proxy|not_decision_grade)(?:_|$)|"
    r"^(?:provider|source)_",
    re.IGNORECASE,
)
_UNSAFE_PROVIDER_VALUE_FRAGMENT_RE = re.compile(
    r"(?:^|[^A-Za-z0-9])(?:delayed_fixture|fixture_only|provider_validation_required_later|"
    r"synthetic_fixture|synthetic_options_lab_fixture)(?:[^A-Za-z0-9]|$)",
    re.IGNORECASE,
)
_UNSAFE_FIELD_NAME_VALUE_RE = re.compile(
    r"\b(?:providerClass|providerName|providerAttempted|requiredProviderClass|"
    r"scoreContributionAllowed|sourceAuthorityAllowed|sourceAuthorityRouter)\b"
)
_ADVICE_RE = re.compile(
    r"\b(?:buy|sell|hold|recommend(?:ation|ed)?|target(?: price)?|stop(?: loss)?|position[-\s]?sizing)\b|"
    r"买入|卖出|持有|推荐|交易建议|投资建议|目标价|止损|止盈|仓位|下单|立即交易|必买|稳赚|保证收益",
    re.IGNORECASE,
)

_HIGH_CONFIDENCE_VALUES = {"high", "strong", "very high", "elevated"}
_SAFE_LIST_FIELDS = ("missingInputs", "staleInputs", "evidenceGaps")
_FIELD_REFERENCE_FALLBACK = "evidence"


def project_consumer_api_payload(payload: Any, *, surface: str | None = None) -> Any:
    """Return a recursively consumer-safe projection for API responses."""

    projected, context = _project_node(_model_to_plain(payload), surface=surface)
    if isinstance(projected, dict):
        _apply_context(projected, context)
    return projected


def _project_node(value: Any, *, surface: str | None = None) -> tuple[Any, dict[str, Any]]:
    context = _new_context()

    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if _is_provider_health_key(key_text):
                output[key_text] = _project_provider_health(child, surface=surface)
                continue
            if _is_allowed_surface_value(surface, key_text, child):
                output[key_text] = child
                continue
            if _is_forbidden_key(key_text):
                _collect_from_removed(key_text, child, context)
                continue
            if _is_field_reference_key(key_text) and isinstance(child, str):
                if _is_unsafe_field_name_text(child):
                    _collect_from_removed(key_text, child, context)
                    output[key_text] = _FIELD_REFERENCE_FALLBACK
                    continue

            projected_child, child_context = _project_node(child, surface=surface)
            _merge_context(context, child_context)

            if _is_allowed_surface_value(surface, key_text, projected_child):
                output[key_text] = projected_child
                continue
            if _is_reason_like_key(key_text):
                sanitized_child = _sanitize_reason_like_value(projected_child, context)
                output[key_text] = sanitized_child
                continue
            if _is_diagnostic_code_key(key_text):
                sanitized_child = _sanitize_diagnostic_code_value(projected_child, context)
                output[key_text] = sanitized_child
                continue
            if isinstance(projected_child, str) and _is_unsafe_text(projected_child):
                _collect_from_removed(key_text, projected_child, context)
                output[key_text] = _safe_text_for(projected_child)
                continue
            output[key_text] = projected_child

        _apply_context(output, context)
        return output, context

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items: list[Any] = []
        for item in value:
            projected_item, child_context = _project_node(item, surface=surface)
            _merge_context(context, child_context)
            items.append(projected_item)
        return items, context

    if isinstance(value, str) and _is_unsafe_text(value):
        _collect_from_removed("value", value, context)
        return _safe_text_for(value), context

    return value, context


def _is_allowed_surface_value(surface: str | None, key: str, value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized_key = _normalize_key(key)
    if surface == "symbol-research-packet":
        return normalized_key in {"state", "readinessstate"} and value in {"provider_unavailable"}
    if surface == "options-chain":
        return normalized_key == "providername" and value == "synthetic_fixture"
    return False


def _apply_context(output: dict[str, Any], context: dict[str, Any]) -> None:
    if _is_compact_evidence_descriptor(output):
        return

    if context["limited"]:
        for key, value in _SAFE_ROOT_DEFAULTS.items():
            output.setdefault(key, value)
        if not output.get("researchNextSteps"):
            output["researchNextSteps"] = ["Review evidence gaps before interpreting this observation."]

    for field in _SAFE_LIST_FIELDS:
        existing = list(output.get(field)) if isinstance(output.get(field), list) else []
        merged = _dedupe_preserving_items([*existing, *context[field]])
        if merged:
            output[field] = merged

    if _should_cap_confidence(output, context):
        output["confidence"] = "limited"
        output["confidenceCap"] = {
            "value": 60,
            "reason": "Evidence is limited by missing or stale inputs.",
        }


def _collect_from_removed(key: str, value: Any, context: dict[str, Any]) -> None:
    context["limited"] = True
    normalized_key = _normalize_key(key)
    if "stale" in normalized_key or "cache" in normalized_key or "fallback" in normalized_key:
        _append_unique(context["staleInputs"], "freshness constrained")
    if "provider" in normalized_key or "source" in normalized_key or "authority" in normalized_key:
        _append_unique(context["evidenceGaps"], "evidence limited")

    for text in _iter_strings(value):
        lowered = text.lower()
        if "benchmark" in lowered:
            _append_unique(context["missingInputs"], "benchmark evidence")
        if any(token in lowered for token in ("missing", "unavailable", "timeout", "provider", "source_authority")):
            _append_unique(context["evidenceGaps"], "evidence limited")
        if any(token in lowered for token in ("stale", "cached", "cache", "fallback", "delayed")):
            _append_unique(context["staleInputs"], "freshness constrained")
        if _ADVICE_RE.search(text):
            _append_unique(context["evidenceGaps"], "evidence limited")


def _is_forbidden_key(key: str) -> bool:
    normalized = _normalize_key(key)
    if normalized in {
        "providerfreshness",
        "providerneutralnextdataaction",
        "providerhealth",
    }:
        return False
    if normalized in FORBIDDEN_CONSUMER_DIAGNOSTIC_KEYS:
        return True
    if normalized.endswith("raw") or normalized.endswith("raws"):
        return True
    if normalized.endswith("reasoncode") or normalized.endswith("reasoncodes"):
        return True
    if normalized.startswith("provider"):
        return True
    if normalized.endswith("apikeypresent") or normalized.endswith("cachekey"):
        return True
    if normalized.startswith("debug") or normalized.startswith("trace") or normalized.startswith("raw"):
        return True
    if normalized.endswith("runtime") or normalized.startswith("runtime"):
        return True
    if normalized.endswith("diagnostics") and normalized != "consumerdiagnostics":
        return True
    return False


def _is_provider_health_key(key: str) -> bool:
    return _normalize_key(key) == "providerhealth"


def _project_provider_health(value: Any, *, surface: str | None = None) -> Any:
    if not isinstance(value, Mapping):
        return value

    allowed_keys = {
        "provider",
        "status",
        "asOf",
        "updatedAt",
        "latencyMs",
        "errorSummary",
        "isFallback",
        "isStale",
        "isRefreshing",
        "sourceLabel",
        "card",
    }
    projected: dict[str, Any] = {}
    for key in allowed_keys:
        if key not in value:
            continue
        child = value.get(key)
        sanitized_child, _ = _project_node(_model_to_plain(child), surface=surface)
        if isinstance(sanitized_child, str) and _is_unsafe_text(sanitized_child):
            sanitized_child = _safe_text_for(sanitized_child)
        projected[key] = sanitized_child
    return projected


def _is_reason_like_key(key: str) -> bool:
    normalized = _normalize_key(key)
    return normalized in {
        "blockingreasons",
        "capreason",
        "degradationreason",
        "disabledreason",
        "issuereasons",
        "reason",
        "unavailablereason",
    }


def _is_diagnostic_code_key(key: str) -> bool:
    normalized = _normalize_key(key)
    return normalized in {
        "blockingcode",
        "blockingcodes",
        "code",
        "codes",
        "gatecode",
        "gatecodes",
        "issuecode",
        "issuecodes",
    }


def _is_field_reference_key(key: str) -> bool:
    return _normalize_key(key) == "sourcefield"


def _sanitize_diagnostic_code_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str) and _is_internal_diagnostic_code_value(value):
        _collect_from_removed("code", value, context)
        return _safe_text_for(value)
    if isinstance(value, list):
        return [_sanitize_diagnostic_code_value(item, context) for item in value]
    if isinstance(value, dict):
        return {
            key: _sanitize_diagnostic_code_value(child, context)
            for key, child in value.items()
        }
    return value


def _is_internal_diagnostic_code_value(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return False
    if _is_unsafe_text(lowered):
        return True
    return lowered.startswith(
        (
            "benchmark_",
            "expected_move_",
            "fixture_",
            "history_",
            "iv_rank_",
            "low_or_missing_",
            "missing_",
            "provider_",
            "source_",
            "stale_",
            "synthetic_",
            "unknown_",
            "wide_",
        )
    ) or lowered.endswith(("_fixture_only", "_not_decision_grade", "_adapter_contract", "_fixture_proxy"))


def _sanitize_reason_like_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str) and _is_internal_reason_value(value):
        _collect_from_removed("reason", value, context)
        return _safe_text_for(value)
    if isinstance(value, list):
        return [_sanitize_reason_like_value(item, context) for item in value]
    if isinstance(value, dict):
        return {
            key: _sanitize_reason_like_value(child, context)
            for key, child in value.items()
        }
    return value


def _is_internal_reason_value(value: str) -> bool:
    text = value.strip()
    lowered = text.lower()
    if not text:
        return False
    if _is_unsafe_text(text):
        return True
    return bool(re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+", lowered))


def _is_unsafe_text(text: str) -> bool:
    return bool(
        _is_unsafe_field_name_text(text)
        or _UNSAFE_VALUE_RE.search(text)
        or _UNSAFE_DIAGNOSTIC_VALUE_RE.search(text)
        or _UNSAFE_PROVIDER_VALUE_FRAGMENT_RE.search(text)
        or _ADVICE_RE.search(text)
    )


def _is_unsafe_field_name_text(text: str) -> bool:
    stripped = str(text or "").strip()
    if not stripped:
        return False
    normalized = _normalize_key(stripped)
    return normalized in FORBIDDEN_CONSUMER_DIAGNOSTIC_KEYS or bool(
        _UNSAFE_FIELD_NAME_VALUE_RE.search(stripped)
    )


def sanitize_consumer_diagnostic_text(value: str) -> str:
    """Return consumer-safe text when a string contains internal diagnostic names."""

    if _is_unsafe_text(value):
        return _safe_text_for(value)
    return value


def sanitize_consumer_field_reference(value: str) -> str:
    """Return a safe field-reference label without exposing internal source fields."""

    if _is_unsafe_field_name_text(value):
        return _FIELD_REFERENCE_FALLBACK
    return value


def _safe_text_for(text: str) -> str:
    lowered = text.lower()
    if "daily_ohlcv" in lowered:
        return "Daily price history evidence"
    if "history_unavailable" in lowered:
        return "Daily price history is unavailable for this observation."
    if "benchmark_missing" in lowered:
        return "Benchmark evidence is missing for this observation."
    if "missing_contracts" in lowered:
        return "Contract evidence is missing for this observation."
    if any(token in lowered for token in ("stale", "cached", "cache", "fallback", "delayed")):
        return "Freshness is constrained for this observation."
    return "Evidence is limited for this observation."


def _should_cap_confidence(output: dict[str, Any], context: dict[str, Any]) -> bool:
    has_gap = context["limited"] or any(_safe_list(output.get(field)) for field in _SAFE_LIST_FIELDS)
    if not has_gap:
        return False
    confidence = str(output.get("confidence") or "").strip().lower()
    if confidence in _HIGH_CONFIDENCE_VALUES:
        return True
    score = output.get("score")
    try:
        return float(score) > 0.75
    except (TypeError, ValueError):
        return False


def _is_compact_evidence_descriptor(output: dict[str, Any]) -> bool:
    keys = set(output)
    return bool(
        {"label", "category"}.issubset(keys)
        and keys.issubset({"label", "category", "sourceField", "severity", "state"})
    )


def _new_context() -> dict[str, Any]:
    return {
        "limited": False,
        "missingInputs": [],
        "staleInputs": [],
        "evidenceGaps": [],
    }


def _merge_context(target: dict[str, Any], source: dict[str, Any]) -> None:
    target["limited"] = bool(target["limited"] or source["limited"])
    for field in _SAFE_LIST_FIELDS:
        for value in source[field]:
            _append_unique(target[field], value)


def _iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        strings: list[str] = []
        for key, child in value.items():
            strings.append(str(key))
            strings.extend(_iter_strings(child))
        return strings
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        strings: list[str] = []
        for item in value:
            strings.extend(_iter_strings(item))
        return strings
    return []


def _safe_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        _append_unique(deduped, item)
    return deduped


def _dedupe_preserving_items(items: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _normalize_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch.isalnum())


def _model_to_plain(payload: Any) -> Any:
    dump = getattr(payload, "model_dump", None)
    if callable(dump):
        return dump(by_alias=True, exclude_none=False)
    return payload


__all__ = [
    "FORBIDDEN_CONSUMER_DIAGNOSTIC_KEYS",
    "NO_ADVICE_DISCLOSURE",
    "OBSERVATION_BOUNDARY",
    "project_consumer_api_payload",
    "sanitize_consumer_diagnostic_text",
    "sanitize_consumer_field_reference",
]
