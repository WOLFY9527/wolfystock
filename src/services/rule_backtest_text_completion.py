# -*- coding: utf-8 -*-
"""Rule-backtest-local text completion facade."""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.agent.llm_adapter import LLMToolAdapter
from src.config import get_config

logger = logging.getLogger(__name__)


class RuleBacktestTextCompletion:
    """Narrow text-completion facade for rule backtest parsing and summaries."""

    def __init__(self, adapter: Any):
        self._adapter = adapter

    def call_text(
        self,
        messages,
        *,
        temperature,
        max_tokens,
    ):
        return self._adapter.call_text(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )


def create_rule_backtest_text_completion(
    adapter: Any = None,
) -> Optional[RuleBacktestTextCompletion]:
    if isinstance(adapter, RuleBacktestTextCompletion):
        return adapter
    try:
        resolved_adapter = adapter or LLMToolAdapter(get_config())
    except Exception as exc:
        logger.warning("Failed to initialize LLM adapter for rule backtest: %s", exc)
        return None
    return RuleBacktestTextCompletion(resolved_adapter)
