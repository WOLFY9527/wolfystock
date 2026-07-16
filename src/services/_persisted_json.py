"""Internal persisted JSON decoding authority for decision-grade read paths."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional


class PersistedJsonState(str, Enum):
    NULL_PAYLOAD = "null_payload"
    VALID_EMPTY = "valid_empty"
    VALID_VALUE = "valid_value"
    MALFORMED = "malformed"
    INCOMPATIBLE_SHAPE = "incompatible_shape"
    SEMANTIC_INVALID = "semantic_invalid"


@dataclass(frozen=True)
class PersistedJsonDecodeResult:
    state: PersistedJsonState
    value: Any = None

    @property
    def is_valid(self) -> bool:
        return self.state in {PersistedJsonState.VALID_EMPTY, PersistedJsonState.VALID_VALUE}


def decode_persisted_json(
    raw: Any,
    *,
    expected_type: type,
    validator: Optional[Callable[[Any], bool]] = None,
) -> PersistedJsonDecodeResult:
    if raw is None:
        return PersistedJsonDecodeResult(PersistedJsonState.NULL_PAYLOAD)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, UnicodeError):
        return PersistedJsonDecodeResult(PersistedJsonState.MALFORMED)
    if not isinstance(value, expected_type):
        return PersistedJsonDecodeResult(PersistedJsonState.INCOMPATIBLE_SHAPE)
    if validator is not None:
        try:
            valid = validator(value)
        except Exception:
            valid = False
        if not valid:
            return PersistedJsonDecodeResult(PersistedJsonState.SEMANTIC_INVALID)
    state = PersistedJsonState.VALID_EMPTY if len(value) == 0 else PersistedJsonState.VALID_VALUE
    return PersistedJsonDecodeResult(state, value)
