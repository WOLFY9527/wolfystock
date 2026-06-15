# -*- coding: utf-8 -*-
"""Contract tests for bounded homepage public-copy helper tokens."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from src.services.homepage_public_copy import (
    FORBIDDEN_PUBLIC_COPY_MARKERS,
    HOMEPAGE_PUBLIC_COPY_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_PUBLIC_STATUS_LABELS,
    sanitize_public_copy,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "src" / "services" / "homepage_public_copy.py"
EXPECTED_STATUS_LABELS = (
    "正常",
    "暂无证据",
    "部分缺失",
    "数据延迟",
    "使用缓存",
    "暂不可用",
    "适合研究观察",
    "需要复核",
)
EXPECTED_FORBIDDEN_PUBLIC_COPY_MARKERS = (
    "fallback",
    "trustLevel",
    "sourceType",
    "reasonCode",
    "raw",
    "provider",
    "traceback",
    "scaffold",
    "happy-path",
    "UAT",
)
FORBIDDEN_TRADING_ADVICE_TERMS = (
    "建议买入",
    "建议卖出",
    "买入",
    "卖出",
    "下单",
    "立即交易",
    "立即买入",
    "交易建议",
    "投资建议",
    "止损",
    "止盈",
    "目标价",
    "仓位建议",
    "必买",
    "稳赚",
    "保证收益",
    "buy now",
    "sell now",
    "place order",
    "trade recommendation",
    "trading advice",
    "investment advice",
    "financial advice",
    "target price",
    "stop loss",
    "take profit",
    "guaranteed",
)
FORBIDDEN_INTERNAL_DIAGNOSTICS_OR_SECRETS = (
    "traceback",
    "provider",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "raw",
    "debug",
    "exception",
    "token",
    "session",
    "secret",
    "api_key",
    "apikey",
    "bearer ",
    "sk-",
    "cookie",
    "/users/",
    "/tmp/",
    "http://",
    "https://",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "api.v1",
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "src.auth",
    "src.services.dashboard",
    "src.services.dashboard_overview_service",
    "src.services.market_cache",
)


def _serialized(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).lower()


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"), filename=str(HELPER_PATH))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def test_public_status_labels_are_stable_and_bounded() -> None:
    assert HOMEPAGE_PUBLIC_STATUS_LABELS == EXPECTED_STATUS_LABELS
    assert len(HOMEPAGE_PUBLIC_STATUS_LABELS) == len(set(HOMEPAGE_PUBLIC_STATUS_LABELS))


def test_no_advice_disclosure_is_safe_chinese_public_copy() -> None:
    assert HOMEPAGE_PUBLIC_COPY_NO_ADVICE_DISCLOSURE == "仅供公开信息研究观察，不构成个性化决策依据或执行指令。"
    assert "研究观察" in HOMEPAGE_PUBLIC_COPY_NO_ADVICE_DISCLOSURE
    assert sanitize_public_copy(HOMEPAGE_PUBLIC_COPY_NO_ADVICE_DISCLOSURE) == HOMEPAGE_PUBLIC_COPY_NO_ADVICE_DISCLOSURE


def test_forbidden_public_copy_markers_are_stable_for_tests() -> None:
    assert FORBIDDEN_PUBLIC_COPY_MARKERS == EXPECTED_FORBIDDEN_PUBLIC_COPY_MARKERS


def test_sanitize_public_copy_removes_forbidden_markers() -> None:
    dirty = "状态 fallback trustLevel sourceType reasonCode raw provider traceback scaffold happy-path UAT 正常"

    sanitized = sanitize_public_copy(dirty)
    serialized = _serialized(sanitized)

    for marker in FORBIDDEN_PUBLIC_COPY_MARKERS:
        assert marker.lower() not in serialized
    assert sanitized == "状态 正常"


def test_sanitize_public_copy_removes_trading_advice_terms() -> None:
    dirty = "建议买入 buy now target price 止损 仅供公开信息研究观察"

    sanitized = sanitize_public_copy(dirty)
    serialized = _serialized(sanitized)

    hits = [term for term in FORBIDDEN_TRADING_ADVICE_TERMS if term.lower() in serialized]
    assert hits == []
    assert sanitized == "仅供公开信息研究观察"


def test_sanitize_public_copy_removes_internal_diagnostics_and_secrets() -> None:
    dirty = "traceback provider raw debug token sk-test http://internal.example /Users/dev/tmp 正常"

    sanitized = sanitize_public_copy(dirty)
    serialized = _serialized(sanitized)

    hits = [term for term in FORBIDDEN_INTERNAL_DIAGNOSTICS_OR_SECRETS if term.lower() in serialized]
    assert hits == []
    assert sanitized == "正常"


def test_exported_public_tokens_do_not_contain_advice_or_internal_copy() -> None:
    public_payload = {
        "labels": HOMEPAGE_PUBLIC_STATUS_LABELS,
        "disclosure": HOMEPAGE_PUBLIC_COPY_NO_ADVICE_DISCLOSURE,
    }
    serialized = _serialized(public_payload)

    advice_hits = [term for term in FORBIDDEN_TRADING_ADVICE_TERMS if term.lower() in serialized]
    internal_hits = [term for term in FORBIDDEN_INTERNAL_DIAGNOSTICS_OR_SECRETS if term.lower() in serialized]
    marker_hits = [term for term in FORBIDDEN_PUBLIC_COPY_MARKERS if term.lower() in serialized]
    assert advice_hits == []
    assert internal_hits == []
    assert marker_hits == []


def test_helper_has_no_heavy_imports() -> None:
    imported_modules = _helper_imports()

    assert imported_modules == {"__future__", "re"}
    for module in imported_modules:
        assert not module.startswith(FORBIDDEN_IMPORT_PREFIXES)
