# -*- coding: utf-8 -*-
"""Bounded public-copy helpers for homepage status text."""

from __future__ import annotations

import re

HOMEPAGE_PUBLIC_STATUS_LABELS: tuple[str, ...] = (
    "已核验",
    "暂无证据",
    "部分缺失",
    "数据延迟",
    "暂不可用",
    "适合研究观察",
    "需要复核",
)

HOMEPAGE_PUBLIC_COPY_NO_ADVICE_DISCLOSURE = "仅供公开信息研究观察，不构成个性化决策依据或执行指令。"

FORBIDDEN_PUBLIC_COPY_MARKERS: tuple[str, ...] = (
    "fallback",
    "trustLevel",
    "sourceType",
    "reasonCode",
    "reason-code",
    "reason_code",
    "raw",
    "provider",
    "traceback",
    "scaffold",
    "happy-path",
    "UAT",
    "cache",
    "schema",
)

_FORBIDDEN_PUBLIC_COPY_PATTERN = re.compile(
    "|".join(re.escape(marker) for marker in FORBIDDEN_PUBLIC_COPY_MARKERS),
    flags=re.IGNORECASE,
)
_FORBIDDEN_TRADING_ADVICE_PATTERN = re.compile(
    r"建议(?:买入|卖出|加仓|减仓|持有)|买入|卖出|下单|立即交易|立即买入|交易建议|投资建议|"
    r"止损|止盈|目标价|目标位|目标区间|仓位建议|必买|稳赚|保证收益|"
    r"\b(?:buy now|sell now|place order|submit order|trade recommendation|trading advice|"
    r"investment advice|financial advice|target price|stop loss|take profit|guaranteed return|guaranteed)\b",
    flags=re.IGNORECASE,
)
_FORBIDDEN_INTERNAL_DIAGNOSTIC_PATTERN = re.compile(
    r"api[_-]?key|secret|cookie|session|token|bearer\s+\S+|sk-[a-z0-9_-]+|"
    r"https?://\S+|/users/\S+|/tmp/\S*|debug|exception|stack trace",
    flags=re.IGNORECASE,
)
_WHITESPACE_PATTERN = re.compile(r"\s+")


def sanitize_public_copy(text: object) -> str:
    """Return bounded homepage copy with internal markers and advice terms removed."""

    sanitized = str(text or "")
    sanitized = _FORBIDDEN_PUBLIC_COPY_PATTERN.sub("", sanitized)
    sanitized = _FORBIDDEN_TRADING_ADVICE_PATTERN.sub("", sanitized)
    sanitized = _FORBIDDEN_INTERNAL_DIAGNOSTIC_PATTERN.sub("", sanitized)
    return _WHITESPACE_PATTERN.sub(" ", sanitized).strip()


__all__ = (
    "FORBIDDEN_PUBLIC_COPY_MARKERS",
    "HOMEPAGE_PUBLIC_COPY_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_PUBLIC_STATUS_LABELS",
    "sanitize_public_copy",
)
