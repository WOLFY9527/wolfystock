# -*- coding: utf-8 -*-
"""Focused UAT isolation boundary tests for provider and LLM dispatch."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from src.agent.llm_adapter import LLMToolAdapter
from src.services.uat_provider_isolation import (
    UatProviderIsolationError,
    check_uat_provider_dispatch,
)


def test_allowlist_preserves_explicit_uat_contract_dispatch() -> None:
    with patch.dict(
        os.environ,
        {
            "WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS": "true",
            "WOLFYSTOCK_UAT_LIVE_PROVIDER_ALLOWLIST": "alpaca:market_data:AlpacaFetcher._request_json",
        },
        clear=False,
    ):
        dispatch = check_uat_provider_dispatch(
            provider="alpaca",
            capability="market_data",
            route="AlpacaFetcher._request_json",
        )

    assert dispatch.allowed is True
    assert dispatch.reason_code == "uat_contract_allowlisted"


def test_default_production_dispatch_semantics_are_allowed_without_uat_flag() -> None:
    with patch.dict(os.environ, {}, clear=True):
        dispatch = check_uat_provider_dispatch(
            provider="yfinance",
            capability="daily_history",
            route="YfinanceFetcher._fetch_raw_data",
        )

    assert dispatch.allowed is True
    assert dispatch.reason_code == "uat_no_live_providers_disabled"


def test_llm_adapter_blocks_litellm_and_router_dispatch_under_uat() -> None:
    adapter = LLMToolAdapter.__new__(LLMToolAdapter)
    adapter._config = SimpleNamespace(llm_temperature=0.7, llm_model_list=[])
    adapter._router = Mock()
    adapter._router.completion.side_effect = AssertionError("router must not be called")
    adapter._litellm_available = True

    with patch.dict(os.environ, {"WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS": "true"}, clear=False), \
         patch("src.agent.llm_adapter.litellm.completion", side_effect=AssertionError("litellm must not be called")):
        with pytest.raises(UatProviderIsolationError):
            adapter._call_litellm_model(
                messages=[{"role": "user", "content": "ping"}],
                tools=[],
                model="openai/gpt-4o-mini",
            )

    adapter._router.completion.assert_not_called()
