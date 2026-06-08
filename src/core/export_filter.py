# -*- coding: utf-8 -*-
"""Deterministic safety filters for consumer-facing exports."""

from __future__ import annotations

import re


_SNAKE_CASE_RE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

_CHINESE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("理想买入点", "观察价位一"),
    ("次优买入点", "观察价位二"),
    ("止损位", "风险边界"),
    ("止损说明", "风险边界说明"),
    ("目标一区", "观察区间一"),
    ("目标二区", "观察区间二"),
    ("目标区间", "观察区间"),
    ("目标位", "观察区间"),
    ("空仓者建议", "未持有场景观察"),
    ("持仓者建议", "已持有场景观察"),
    ("空仓者", "未持有场景"),
    ("持仓者", "已持有场景"),
    ("建仓策略", "观察策略"),
    ("风控策略", "风险边界"),
    ("作战计划", "观察计划"),
    ("狙击点位", "关键观察位"),
    ("买点", "观察点"),
    ("买入", "观察"),
    ("卖出", "观察风险"),
    ("建议", "观察"),
    ("决策仪表盘", "研究观察摘要"),
    ("决策简报", "研究观察简报"),
    ("评分 / 建议 / 趋势", "评分 / 观察 / 趋势"),
    ("操作建议", "观察说明"),
    ("Provider口径", "数据口径"),
    ("接口未返回", "数据暂未完全覆盖"),
    ("字段待接入", "数据暂未完全覆盖"),
    ("当前数据源未提供", "数据暂未完全覆盖"),
)

_PHRASE_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bmissing\s+field\s+audit\b", re.IGNORECASE), "Research Data Boundaries"),
    (re.compile(r"\bfull\s+truth\b", re.IGNORECASE), "consumer summary"),
    (re.compile(r"\bintegrated_unavailable\b", re.IGNORECASE), "data coverage note"),
    (re.compile(r"\breason\s*code\b", re.IGNORECASE), "data coverage note"),
    (re.compile(r"\breasoncode\b", re.IGNORECASE), "data coverage note"),
    (re.compile(r"\braw\s+diagnostics?\b", re.IGNORECASE), "data coverage note"),
    (re.compile(r"\balpaca\s*fetcher\b", re.IGNORECASE), "market data"),
    (re.compile(r"\balpacafetcher\b", re.IGNORECASE), "market data"),
    (re.compile(r"\byahoo\s+finance\b", re.IGNORECASE), "market data"),
    (re.compile(r"\bfinnhub\b", re.IGNORECASE), "market data"),
    (re.compile(r"\bmarket\s+feed\b", re.IGNORECASE), "market data"),
    (re.compile(r"\bprovider\s+trace\b", re.IGNORECASE), "data source note"),
    (re.compile(r"\bprovider\s+payload\b", re.IGNORECASE), "data source note"),
    (re.compile(r"\bprovider\s+runtime\b", re.IGNORECASE), "data source note"),
    (re.compile(r"\bprovider\b", re.IGNORECASE), "data source"),
    (re.compile(r"\bposition\s+sizing\b", re.IGNORECASE), "exposure context"),
    (re.compile(r"\btarget\s+price\b", re.IGNORECASE), "observation range"),
    (re.compile(r"\btake\s+profit\b", re.IGNORECASE), "upside scenario"),
    (re.compile(r"\bstop[-\s]+loss\b", re.IGNORECASE), "risk boundary"),
    (re.compile(r"\bstrong\s+buy\b", re.IGNORECASE), "observe"),
    (re.compile(r"\bstrong\s+sell\b", re.IGNORECASE), "observe risk"),
    (re.compile(r"\bbuy(?:ing)?\b", re.IGNORECASE), "observe"),
    (re.compile(r"\bsell(?:ing)?\b", re.IGNORECASE), "observe risk"),
    (re.compile(r"\bdecision\s+dashboard\b", re.IGNORECASE), "Research Dashboard"),
    (re.compile(r"\bdecision\s+summary\b", re.IGNORECASE), "Research Summary"),
    (re.compile(r"\bscore\s*/\s*recommendation\s*/\s*trend\b", re.IGNORECASE), "Score / Research View / Trend"),
    (re.compile(r"\brecommendation\b", re.IGNORECASE), "research view"),
)


def sanitize_markdown_export(markdown: str) -> str:
    """Return a consumer-safe markdown export without changing stored reports."""
    if not markdown:
        return ""

    language = "zh" if _CJK_RE.search(markdown) else "en"
    text = _strip_unsafe_export_sections(markdown, language=language)
    text = _apply_export_replacements(text)
    text = _SNAKE_CASE_RE.sub(_data_coverage_placeholder(language), text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return f"{text}\n" if text else ""


def _strip_unsafe_export_sections(markdown: str, *, language: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    skipping: str | None = None
    inserted_boundary = False

    for line in lines:
        normalized = line.strip().lower()
        if normalized == "### execution plan":
            skipping = "execution"
            continue

        if normalized == "### coverage / audit":
            if not inserted_boundary:
                output.extend(_boundary_section(language))
                inserted_boundary = True
            skipping = "audit"
            continue

        if skipping == "execution":
            if normalized == "### evidence":
                skipping = None
                output.append(line)
            continue

        if skipping == "audit":
            if normalized == "---":
                skipping = None
                output.append(line)
            continue

        if _is_action_count_line(line):
            output.append(_observation_only_line(language))
            continue

        output.append(line)

    return "\n".join(output)


def _apply_export_replacements(text: str) -> str:
    for source, replacement in _CHINESE_REPLACEMENTS:
        text = text.replace(source, replacement)
    for pattern, replacement in _PHRASE_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


def _is_action_count_line(line: str) -> bool:
    return line.lstrip().startswith(">") and "🟢" in line and "🟡" in line and "🔴" in line


def _observation_only_line(language: str) -> str:
    if language == "zh":
        return "> 本导出为观察研究摘要；部分数据覆盖可能有限。"
    return "> This export is an observation-only research summary; data coverage may be partial."


def _boundary_section(language: str) -> list[str]:
    if language == "zh":
        return [
            "### 研究数据边界",
            "- 部分数据可能暂不可用，本导出仅保留消费级研究摘要，不包含交易指令或后台诊断。",
            "",
        ]
    return [
        "### Research Data Boundaries",
        "- Some data may be partial; this export keeps consumer research context and omits internal diagnostics.",
        "",
    ]


def _data_coverage_placeholder(language: str) -> str:
    return "数据覆盖说明" if language == "zh" else "data coverage note"
