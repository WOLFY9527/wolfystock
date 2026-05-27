# -*- coding: utf-8 -*-
"""Pure contract tests for the inert options authority policy matrix."""

from __future__ import annotations

import pytest

from src.services.options_authority_policy_matrix import (
    BLOCKED_OPTIONS_AUTHORITY_SOURCE_CLASSES,
    CURRENT_KNOWN_OPTIONS_AUTHORITY_PROVIDER_IDS,
    CURRENT_KNOWN_OPTIONS_AUTHORITY_SOURCE_TYPES,
    OPTIONS_AUTHORITY_SURFACES,
    get_options_authority_policy_matrix,
    get_options_authority_surface_policy,
    is_options_authority_provider_granted,
    is_options_authority_source_blocked,
    is_options_authority_source_granted,
)


def test_all_required_options_authority_surfaces_exist() -> None:
    matrix = get_options_authority_policy_matrix()

    assert OPTIONS_AUTHORITY_SURFACES == (
        "iv_rank",
        "event_calendar",
        "expiration_calendar",
    )
    assert tuple(matrix) == OPTIONS_AUTHORITY_SURFACES


@pytest.mark.parametrize("surface", OPTIONS_AUTHORITY_SURFACES)
@pytest.mark.parametrize("source_type", BLOCKED_OPTIONS_AUTHORITY_SOURCE_CLASSES)
def test_blocked_source_classes_are_blocked_for_all_surfaces(
    surface: str,
    source_type: str,
) -> None:
    assert is_options_authority_source_blocked(surface, source_type) is True
    assert is_options_authority_source_granted(surface, source_type) is False


@pytest.mark.parametrize("surface", OPTIONS_AUTHORITY_SURFACES)
@pytest.mark.parametrize("provider_id", CURRENT_KNOWN_OPTIONS_AUTHORITY_PROVIDER_IDS)
def test_current_known_providers_do_not_receive_authority(
    surface: str,
    provider_id: str,
) -> None:
    assert is_options_authority_provider_granted(surface, provider_id) is False


@pytest.mark.parametrize("surface", OPTIONS_AUTHORITY_SURFACES)
@pytest.mark.parametrize("source_type", CURRENT_KNOWN_OPTIONS_AUTHORITY_SOURCE_TYPES)
def test_current_known_source_types_do_not_receive_authority(
    surface: str,
    source_type: str,
) -> None:
    assert is_options_authority_source_granted(surface, source_type) is False


@pytest.mark.parametrize("surface", OPTIONS_AUTHORITY_SURFACES)
def test_coverage_alone_is_not_authority(surface: str) -> None:
    policy = get_options_authority_surface_policy(surface)

    assert policy["coverage_alone_is_authority"] is False


@pytest.mark.parametrize("surface", OPTIONS_AUTHORITY_SURFACES)
def test_provider_self_claim_alone_is_not_authority(surface: str) -> None:
    policy = get_options_authority_surface_policy(surface)

    assert policy["provider_self_claim_alone_is_authority"] is False


@pytest.mark.parametrize("surface", OPTIONS_AUTHORITY_SURFACES)
def test_required_evidence_includes_authority_policy_source(surface: str) -> None:
    policy = get_options_authority_surface_policy(surface)

    assert "authorityPolicySource" in policy["required_evidence"]
    assert policy["authority_grants"]["provider_ids"] == ()
    assert policy["authority_grants"]["source_types"] == ()
    assert policy["authoritative_by_default"] is False
