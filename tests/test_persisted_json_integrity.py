"""Focused state-matrix tests for persisted JSON decoding."""

from __future__ import annotations

import pytest

from src.services._persisted_json import PersistedJsonState, decode_persisted_json


@pytest.mark.parametrize(
    ("raw", "expected_type", "expected_state", "expected_value"),
    [
        (None, dict, PersistedJsonState.NULL_PAYLOAD, None),
        ("{}", dict, PersistedJsonState.VALID_EMPTY, {}),
        ("[]", list, PersistedJsonState.VALID_EMPTY, []),
        ('{"value": 0}', dict, PersistedJsonState.VALID_VALUE, {"value": 0}),
        ("{", dict, PersistedJsonState.MALFORMED, None),
        ("[]", dict, PersistedJsonState.INCOMPATIBLE_SHAPE, None),
    ],
)
def test_decode_persisted_json_preserves_storage_states(
    raw: str | None,
    expected_type: type,
    expected_state: PersistedJsonState,
    expected_value: object,
) -> None:
    result = decode_persisted_json(raw, expected_type=expected_type)

    assert result.state is expected_state
    assert result.value == expected_value


def test_decode_persisted_json_reports_semantic_validation_failure() -> None:
    result = decode_persisted_json(
        '{"account_id": 7}',
        expected_type=dict,
        validator=lambda payload: payload.get("account_id") == 8,
    )

    assert result.state is PersistedJsonState.SEMANTIC_INVALID
    assert result.value is None
