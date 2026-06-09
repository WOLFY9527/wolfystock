# -*- coding: utf-8 -*-
"""Consumer-facing export sanitizer regression tests."""

from src.core.export_filter import sanitize_markdown_export


def test_sanitize_markdown_export_removes_legacy_full_report_advice_phrases() -> None:
    markdown = """
# Wolfy AI Equity Research: Oracle (ORCL)

## 继续跟踪 / Observation Plan
- 建仓策略: 小仓试错，第二笔在 25%-35% 仓位确认后执行。
- 风控策略: 不要强行交易，设置 stop loss and target price.
- Battle plan: sniper entry with position sizing.
"""

    sanitized = sanitize_markdown_export(markdown)

    assert "继续跟踪" in sanitized
    assert "观察" in sanitized
    forbidden_terms = (
        "小仓试错",
        "第二笔",
        "25%-35%",
        "仓位",
        "强行交易",
        "建仓",
        "买入",
        "卖出",
        "止损",
        "目标价",
        "stop loss",
        "target price",
        "position sizing",
        "battle plan",
        "sniper",
    )
    for term in forbidden_terms:
        assert term not in sanitized, term
