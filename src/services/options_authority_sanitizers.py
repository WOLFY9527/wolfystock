# -*- coding: utf-8 -*-
"""Pure, options-owned primitives for authority evidence sanitization."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, Mapping, Sequence


_URL_LIKE_HOST_RE = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?(?:[/?#].*)?$")


def mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def value(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def text(value: Any) -> str:
    return str(value or "").strip()


def sanitize_authority_text(
    value: Any,
    *,
    safe_chars: set[str],
    blocked_markers: Sequence[str],
    max_length: int = 120,
    redact_url_like: bool = False,
    redact_payload_brackets: bool = False,
) -> str | None:
    sanitized = text(value)
    if not sanitized:
        return None
    lowered = sanitized.lower()
    if any(marker in lowered for marker in blocked_markers):
        return "redacted"
    if redact_url_like and looks_like_url_text(sanitized):
        return "redacted"
    if redact_payload_brackets and any(marker in sanitized for marker in ("{", "}", "[", "]")):
        return "redacted"
    if len(sanitized) > max_length or any(character.lower() not in safe_chars for character in sanitized):
        return "redacted"
    return sanitized


def looks_like_url_text(value: str) -> bool:
    lowered = value.lower()
    if lowered.startswith(("http://", "https://", "www.")):
        return True
    return bool(_URL_LIKE_HOST_RE.fullmatch(lowered))


def normalized_text(value: Any, *, sanitize_text: Callable[[Any], str | None]) -> str:
    return (sanitize_text(value) or "").lower().replace("-", "_")


def coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on", "enabled"}:
            return True
        if lowered in {"0", "false", "no", "off", "disabled"}:
            return False
        return None
    return bool(value)


def sanitize_value(
    value: Any,
    *,
    sanitize_text: Callable[[Any], str | None],
    scalar_types: tuple[type[Any], ...] = (bool, int, float),
    nested_sequence_types: tuple[type[Any], ...] = (list, tuple),
) -> Any:
    if isinstance(value, Mapping):
        return sanitize_mapping(
            value,
            sanitize_text=sanitize_text,
            scalar_types=scalar_types,
            nested_sequence_types=nested_sequence_types,
        )
    if isinstance(value, nested_sequence_types) and not isinstance(value, (str, bytes, bytearray)):
        return sanitize_sequence(
            value,
            sanitize_text=sanitize_text,
            scalar_types=scalar_types,
            nested_sequence_types=nested_sequence_types,
        )
    if isinstance(value, scalar_types):
        return value
    return sanitize_text(value)


def sanitize_mapping(
    value: Any,
    *,
    sanitize_text: Callable[[Any], str | None],
    scalar_types: tuple[type[Any], ...] = (bool, int, float),
    nested_sequence_types: tuple[type[Any], ...] = (list, tuple),
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, raw in mapping(value).items():
        safe_key = sanitize_text(key)
        if safe_key is None:
            continue
        safe_value = sanitize_value(
            raw,
            sanitize_text=sanitize_text,
            scalar_types=scalar_types,
            nested_sequence_types=nested_sequence_types,
        )
        if safe_value not in (None, "", [], {}):
            sanitized[safe_key] = safe_value
    return sanitized


def sanitize_sequence(
    value: Any,
    *,
    sanitize_text: Callable[[Any], str | None],
    scalar_types: tuple[type[Any], ...] = (bool, int, float),
    nested_sequence_types: tuple[type[Any], ...] = (list, tuple),
) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    sanitized: list[Any] = []
    for item in value:
        safe_value = sanitize_value(
            item,
            sanitize_text=sanitize_text,
            scalar_types=scalar_types,
            nested_sequence_types=nested_sequence_types,
        )
        if safe_value not in (None, "", [], {}):
            sanitized.append(safe_value)
    return sanitized


def sanitize_date_range(
    value: Any,
    *,
    sanitize_text: Callable[[Any], str | None],
) -> dict[str, str] | None:
    data = mapping(value)
    start = sanitize_text(data.get("start", data.get("from")))
    end = sanitize_text(data.get("end", data.get("to")))
    if not start and not end:
        return None
    result: dict[str, str] = {}
    if start:
        result["start"] = start
    if end:
        result["end"] = end
    return result or None


def has_value(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(has_value(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(has_value(item) for item in value)
    if isinstance(value, (bool, int, float)):
        return True
    return bool(text(value))


def flatten_text(
    values: Sequence[Any],
    *,
    sanitize_text: Callable[[Any], str | None],
) -> str:
    chunks: list[str] = []
    for item in values:
        if isinstance(item, Mapping):
            chunks.append(flatten_text(list(item.values()), sanitize_text=sanitize_text))
            continue
        if isinstance(item, (list, tuple, set, frozenset)):
            chunks.append(flatten_text(list(item), sanitize_text=sanitize_text))
            continue
        normalized = normalized_text(item, sanitize_text=sanitize_text)
        if normalized:
            chunks.append(normalized)
    return " ".join(chunks)


def calendar_sla_evidence_present(
    sla_evidence: Mapping[str, Any],
    *,
    as_of: str | None,
    freshness: str | None,
) -> bool:
    has_latency_or_error_state = any(
        has_value(value(sla_evidence, *keys))
        for keys in (
            ("latencyState", "latency_state"),
            ("errorState", "error_state"),
        )
    )
    return bool(
        as_of
        and freshness
        and has_value(value(sla_evidence, "maxAgePolicy", "max_age_policy"))
        and has_value(value(sla_evidence, "providerSlaStatus", "provider_sla_status"))
        and has_value(value(sla_evidence, "freshnessSeconds", "freshness_seconds"))
        and has_value(value(sla_evidence, "freshnessState", "freshness_state"))
        and has_latency_or_error_state
    )
