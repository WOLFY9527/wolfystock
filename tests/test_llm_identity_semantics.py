# -*- coding: utf-8 -*-
"""Contract tests for privacy-safe LLM identity semantics."""

from __future__ import annotations

import json
import string

from src.services.llm_identity_semantics import build_llm_identity_contract


def test_identity_is_deterministic_and_context_order_independent() -> None:
    first = build_llm_identity_contract(
        owner_user_id="owner-123",
        surface="analysis",
        prompt_version="analysis_v1",
        prompt_text="Analyze AAPL earnings momentum.",
        logical_context={
            "symbol": "AAPL",
            "language": "zh-CN",
            "report_type": "daily",
        },
        retry_attempt_index=0,
    )
    second = build_llm_identity_contract(
        owner_user_id="owner-123",
        surface="analysis",
        prompt_version="analysis_v1",
        prompt_text="Analyze AAPL earnings momentum.",
        logical_context={
            "report_type": "daily",
            "language": "zh-CN",
            "symbol": "AAPL",
        },
        retry_attempt_index=0,
    )

    assert first.owner_scope == "owner"
    assert first.retry_attempt_index == 0
    assert first.scope_subject_hash == second.scope_subject_hash
    assert first.logical_request_hash == second.logical_request_hash
    assert first.billable_attempt_hash == second.billable_attempt_hash


def test_identity_isolated_by_owner_and_guest_scope() -> None:
    owner_identity = build_llm_identity_contract(
        owner_user_id="owner-123",
        surface="analysis",
        prompt_version="analysis_v1",
        prompt_text="Analyze AAPL.",
        logical_context={"symbol": "AAPL"},
        retry_attempt_index=0,
    )
    other_owner_identity = build_llm_identity_contract(
        owner_user_id="owner-456",
        surface="analysis",
        prompt_version="analysis_v1",
        prompt_text="Analyze AAPL.",
        logical_context={"symbol": "AAPL"},
        retry_attempt_index=0,
    )
    guest_identity = build_llm_identity_contract(
        guest_bucket_hash="guest-bucket-1",
        surface="guest_preview",
        prompt_version="analysis_v1",
        prompt_text="Analyze AAPL.",
        logical_context={"symbol": "AAPL"},
        retry_attempt_index=0,
    )

    assert owner_identity.owner_scope == "owner"
    assert other_owner_identity.owner_scope == "owner"
    assert guest_identity.owner_scope == "guest"
    assert owner_identity.logical_request_hash != other_owner_identity.logical_request_hash
    assert owner_identity.logical_request_hash != guest_identity.logical_request_hash
    assert owner_identity.scope_subject_hash != other_owner_identity.scope_subject_hash
    assert owner_identity.scope_subject_hash != guest_identity.scope_subject_hash


def test_retry_attempt_distinguishes_billable_attempt_not_logical_request() -> None:
    first_attempt = build_llm_identity_contract(
        owner_user_id="owner-123",
        surface="analysis",
        prompt_version="analysis_v1",
        prompt_text="Analyze AAPL.",
        logical_context={"symbol": "AAPL", "language": "en"},
        retry_attempt_index=0,
    )
    retry_attempt = build_llm_identity_contract(
        owner_user_id="owner-123",
        surface="analysis",
        prompt_version="analysis_v1",
        prompt_text="Analyze AAPL.",
        logical_context={"symbol": "AAPL", "language": "en"},
        retry_attempt_index=1,
    )

    assert first_attempt.retry_attempt_index == 0
    assert retry_attempt.retry_attempt_index == 1
    assert first_attempt.logical_request_hash == retry_attempt.logical_request_hash
    assert first_attempt.billable_attempt_hash != retry_attempt.billable_attempt_hash


def test_prompt_version_and_surface_change_logical_request_identity() -> None:
    baseline = build_llm_identity_contract(
        owner_user_id="owner-123",
        surface="analysis",
        prompt_version="analysis_v1",
        prompt_text="Analyze AAPL.",
        logical_context={"symbol": "AAPL"},
        retry_attempt_index=0,
    )
    prompt_version_change = build_llm_identity_contract(
        owner_user_id="owner-123",
        surface="analysis",
        prompt_version="analysis_v2",
        prompt_text="Analyze AAPL.",
        logical_context={"symbol": "AAPL"},
        retry_attempt_index=0,
    )
    surface_change = build_llm_identity_contract(
        owner_user_id="owner-123",
        surface="scanner_ai",
        prompt_version="analysis_v1",
        prompt_text="Analyze AAPL.",
        logical_context={"symbol": "AAPL"},
        retry_attempt_index=0,
    )

    assert baseline.logical_request_hash != prompt_version_change.logical_request_hash
    assert baseline.logical_request_hash != surface_change.logical_request_hash


def test_identity_contract_never_leaks_raw_prompt_or_secret_values() -> None:
    raw_prompt = "Analyze AAPL with api_key=top-secret and token=very-secret"
    identity = build_llm_identity_contract(
        owner_user_id="owner-123",
        surface="analysis",
        prompt_version="analysis_v1",
        prompt_text=raw_prompt,
        logical_context={
            "symbol": "AAPL",
            "note": "Authorization: Bearer hidden-secret",
            "nested": {"cookie": "session-secret"},
        },
        retry_attempt_index=2,
    )

    payload = json.dumps(identity.to_dict(), sort_keys=True)

    assert raw_prompt not in payload
    assert "top-secret" not in payload
    assert "very-secret" not in payload
    assert "hidden-secret" not in payload
    assert "session-secret" not in payload
    assert set(identity.logical_request_hash) <= set(string.hexdigits.lower())
    assert set(identity.billable_attempt_hash) <= set(string.hexdigits.lower())
    assert len(identity.logical_request_hash) == 64
    assert len(identity.billable_attempt_hash) == 64
