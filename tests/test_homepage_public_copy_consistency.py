# -*- coding: utf-8 -*-
"""Guard serialized public homepage outputs against copy leakage."""

from __future__ import annotations

from collections.abc import Callable
import json
import re

import pytest

from src.services.homepage_capabilities_service import HomepageCapabilitiesService
from src.services.homepage_intelligence_service import HomepageIntelligenceService
from src.services.homepage_module_manifest_service import HomepageModuleManifestService
from src.services.homepage_public_copy import (
    HOMEPAGE_PUBLIC_COPY_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_PUBLIC_STATUS_LABELS,
    sanitize_public_copy,
)


FIXED_AS_OF = "2026-06-14T09:30:00Z"
ALLOWED_PUBLIC_DISCLOSURE = "本页仅用于市场观察、证据整理与研究支持，不构成个性化投资建议。"
CASE_SENSITIVE_FORBIDDEN_MARKERS = (
    "Static metadata only",
    "UAT",
    "Cache",
    "Schema",
    "AI推荐",
)
CASE_INSENSITIVE_FORBIDDEN_PATTERNS = (
    re.compile(r"\bfallback\b", re.IGNORECASE),
    re.compile(r"\btrustLevel\b", re.IGNORECASE),
    re.compile(r"\bsourceType\b", re.IGNORECASE),
    re.compile(r"\breasonCode\b", re.IGNORECASE),
    re.compile(r"\btraceback\b", re.IGNORECASE),
    re.compile(r"\bprovider\s+URL\b", re.IGNORECASE),
    re.compile(r"\braw\s+error\b", re.IGNORECASE),
    re.compile(r"\bdebug\b", re.IGNORECASE),
    re.compile(r"\binternal\b", re.IGNORECASE),
    re.compile(r"\bscaffold\b", re.IGNORECASE),
    re.compile(r"\bhappy-path\b", re.IGNORECASE),
    re.compile(r"\bnot\s+personalized\s+financial\s+advice\b", re.IGNORECASE),
    re.compile(r"\bbroker\b", re.IGNORECASE),
    re.compile(r"\border\b", re.IGNORECASE),
    re.compile(r"\btrade\s+execution\b", re.IGNORECASE),
    re.compile(r"http://", re.IGNORECASE),
    re.compile(r"https://", re.IGNORECASE),
)
FORBIDDEN_LITERAL_MARKERS = (
    "交易指令",
    "交易执行",
    "交易建议",
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "止损",
    "止盈",
    "目标价",
    "收益预测",
    "智能选股",
)


def _json_ready(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _serialize_public_output(case_name: str, build_output: Callable[[], object]) -> str:
    try:
        payload = _json_ready(build_output())
    except Exception as exc:  # pragma: no cover - exercised only on contract drift
        pytest.fail(f"{case_name} could not build a public homepage output: {type(exc).__name__}: {exc}")

    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        pytest.fail(f"{case_name} could not serialize as public JSON: {type(exc).__name__}: {exc}")


def _build_homepage_intelligence_bundle() -> object:
    return HomepageIntelligenceService().build_bundle()


def _build_homepage_capabilities_snapshot() -> object:
    return HomepageCapabilitiesService().build_snapshot()


def _build_homepage_module_manifest() -> object:
    return HomepageModuleManifestService().build_manifest(as_of=FIXED_AS_OF)


def _build_homepage_public_copy_helper_payload() -> dict[str, object]:
    return {
        "allowedDisclosureExample": ALLOWED_PUBLIC_DISCLOSURE,
        "noAdviceDisclosure": HOMEPAGE_PUBLIC_COPY_NO_ADVICE_DISCLOSURE,
        "statusLabels": list(HOMEPAGE_PUBLIC_STATUS_LABELS),
        "sanitizedDiagnosticExample": sanitize_public_copy(
            "fallback trustLevel sourceType reasonCode raw provider traceback scaffold happy-path UAT 正常"
        ),
    }


PUBLIC_HOMEPAGE_OUTPUTS: tuple[tuple[str, Callable[[], object]], ...] = (
    ("homepage_intelligence_service.build_bundle", _build_homepage_intelligence_bundle),
    ("homepage_capabilities_service.build_snapshot", _build_homepage_capabilities_snapshot),
    ("homepage_module_manifest_service.build_manifest", _build_homepage_module_manifest),
    ("homepage_public_copy_helper_payload", _build_homepage_public_copy_helper_payload),
)


@pytest.mark.parametrize(
    ("case_name", "build_output"),
    PUBLIC_HOMEPAGE_OUTPUTS,
    ids=[case_name for case_name, _ in PUBLIC_HOMEPAGE_OUTPUTS],
)
def test_serialized_public_homepage_outputs_do_not_leak_internal_or_execution_copy(
    case_name: str,
    build_output: Callable[[], object],
) -> None:
    serialized = _serialize_public_output(case_name, build_output)

    leaked = [marker for marker in CASE_SENSITIVE_FORBIDDEN_MARKERS if marker in serialized]
    leaked.extend(marker for marker in FORBIDDEN_LITERAL_MARKERS if marker in serialized)
    for pattern in CASE_INSENSITIVE_FORBIDDEN_PATTERNS:
        match = pattern.search(serialized)
        if match is not None:
            leaked.append(match.group(0))

    assert leaked == [], f"{case_name} leaked public-copy markers: {leaked}"
