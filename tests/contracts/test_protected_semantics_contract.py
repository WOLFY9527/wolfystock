"""Golden characterization of semantic distinctions protected by T457 W1."""

from __future__ import annotations

import pytest

from scripts.architecture import protected_semantics


MATRIX = protected_semantics.load_matrix()
CASES = tuple(MATRIX["cases"])


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_protected_semantics_match_current_owner_contract(case: dict) -> None:
    assert protected_semantics.collect_case(case["id"]) == case["expected"]
