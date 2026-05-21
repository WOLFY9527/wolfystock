# -*- coding: utf-8 -*-
"""Pure unavailable reason-bucket parsing helpers for inert contracts."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


STANDARD_REASON_MARKER_KEYS = (
    "unavailable_reason",
    "unavailableReason",
    "reason",
    "reasonCode",
    "errorCode",
    "status",
    "credentialState",
    "credential_state",
    "message",
)

CUSTOM_SOURCE_REASON_MARKER_KEYS = (
    "unavailableReason",
    "unavailable_reason",
    "reason",
    "reasonCode",
    "errorCode",
    "status",
    "credentialState",
    "credential_state",
    "message",
)

STANDARD_REASON_BUCKET_RULES = (
    (
        "provider_not_selected",
        (
            "provider_not_selected",
            "provider not selected",
            "not_selected",
            "deferred",
        ),
    ),
    (
        "missing_credentials",
        (
            "missing_credentials",
            "credential missing",
            "missing api key",
            "not_configured",
            "api_key_missing",
            "missing token",
        ),
    ),
    (
        "permission_denied",
        (
            "permission_denied",
            "permission denied",
            "forbidden",
            "403",
            "unauthorized_scope",
        ),
    ),
    (
        "empty_payload",
        (
            "empty_payload",
            "empty response",
            "empty dataset",
            "no_data",
            "no data",
        ),
    ),
    (
        "malformed_payload",
        (
            "malformed_payload",
            "malformed",
            "invalid",
            "schema",
        ),
    ),
)

NO_PROVIDER_SELECTION_REASON_BUCKET_RULES = tuple(
    rule for rule in STANDARD_REASON_BUCKET_RULES if rule[0] != "provider_not_selected"
)

CUSTOM_SOURCE_REASON_BUCKET_RULES = (
    (
        "missing_credentials",
        (
            "missing_credentials",
            "missing api key",
            "missing token",
            "not_configured",
        ),
    ),
    (
        "permission_denied",
        (
            "permission_denied",
            "permission denied",
            "forbidden",
            "403",
        ),
    ),
    (
        "empty_payload",
        (
            "empty_payload",
            "empty response",
            "empty dataset",
            "no_data",
            "no data",
        ),
    ),
    (
        "temporarily_unavailable",
        (
            "temporarily_unavailable",
            "temporarily unavailable",
            "unavailable",
            "timeout",
        ),
    ),
    (
        "malformed_payload",
        (
            "malformed_payload",
            "malformed",
            "invalid",
            "schema",
        ),
    ),
)


def explicit_unavailable_reason_bucket(
    payload: Any,
    *,
    marker_keys: Sequence[str] = STANDARD_REASON_MARKER_KEYS,
    reason_bucket_rules: Sequence[tuple[str, Sequence[str]]] = STANDARD_REASON_BUCKET_RULES,
    include_error_markers: bool = True,
) -> str | None:
    """Extract a known unavailable reason bucket from provider-shaped payload markers."""
    if not isinstance(payload, Mapping):
        return None

    observations = payload.get("observations")
    if isinstance(observations, Sequence) and not isinstance(observations, (str, bytes)) and len(observations) == 0:
        return "empty_payload"

    markers = [payload.get(key) for key in marker_keys]
    if include_error_markers:
        error = payload.get("error")
        if isinstance(error, Mapping):
            markers.extend(
                [
                    error.get("reason"),
                    error.get("reasonCode"),
                    error.get("errorCode"),
                    error.get("status"),
                    error.get("message"),
                ]
            )
        elif error is not None:
            markers.append(error)

    normalized = " ".join(_text(marker).lower() for marker in markers if marker is not None)
    if not normalized:
        return None
    for reason_bucket, tokens in reason_bucket_rules:
        if any(token in normalized for token in tokens):
            return reason_bucket
    return None


def safe_unavailable_reason_bucket(value: Any, safe_reason_buckets: Sequence[str]) -> str:
    """Return a configured safe bucket, otherwise fail closed as malformed payload."""
    normalized = _text(value).lower()
    if normalized in safe_reason_buckets:
        return normalized
    return "malformed_payload"


def _text(value: Any) -> str:
    return str(value or "").strip()
