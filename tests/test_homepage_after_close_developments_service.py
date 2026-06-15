# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage after-close developments contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_after_close_developments import (
    HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_DEFAULT_AS_OF,
    HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_SCHEMA_VERSION,
    HomepageAfterCloseDevelopmentsSnapshot,
)
from src.services.homepage_after_close_developments_service import (
    HomepageAfterCloseDevelopmentsService,
)


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "latestSession",
    "afterCloseDevelopments",
    "overnightContext",
    "futuresTone",
    "earningsCatalysts",
    "macroEvents",
    "geopoliticalEvents",
    "commodityMoves",
    "ratesMoves",
    "todayWatchPoints",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
]
EXPECTED_DEVELOPMENT_KEYS = {
    "index_futures_proxy",
    "megacap_earnings_watch",
    "rates_overnight_proxy",
    "energy_geopolitical_proxy",
}
QUALITY_STATES = {"sample_proxy", "no_evidence", "unavailable"}
FORBIDDEN_PUBLIC_MARKERS = (
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
    "AI推荐",
    "智能选股",
    "broker",
    "order",
    "execution",
    "trade execution",
    "trading advice",
    "investment advice",
    "financial advice",
    "buy now",
    "sell now",
    "target price",
    "stop loss",
    "take profit",
    "provider",
    "fallback",
    "internal",
    "diagnostic",
    "debug",
    "traceback",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "raw",
    "http://",
    "https://",
    "/users/",
    "/tmp/",
    "api_key",
    "apikey",
    "secret",
    "token",
    "cookie",
    "session_id",
)
FORBIDDEN_NEWS_FIELDS = {
    "url",
    "source",
    "provider",
    "headline",
    "publishedAt",
    "rawNews",
    "newsUrl",
}
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "src.providers",
    "aiohttp",
    "httpx",
    "requests",
    "urllib",
    "urllib3",
    "api.deps",
    "api.middlewares.auth",
    "src.auth",
    "src.auth_context",
    "src.admin_rbac",
    "src.services.dashboard_overview_service",
    "src.services.homepage_intelligence_service",
    "src.services.market_cache",
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_payload() -> dict[str, object]:
    return HomepageAfterCloseDevelopmentsService().build_snapshot().model_dump(mode="json")


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_after_close_developments_contract_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_NO_ADVICE_DISCLOSURE
    assert payload["evidenceQuality"]["state"] in QUALITY_STATES
    assert payload["dataQuality"]["state"] in QUALITY_STATES
    assert HomepageAfterCloseDevelopmentsSnapshot.model_validate(payload).schemaVersion == (
        HOMEPAGE_AFTER_CLOSE_DEVELOPMENTS_SCHEMA_VERSION
    )


def test_after_close_developments_output_is_deterministic() -> None:
    service = HomepageAfterCloseDevelopmentsService()

    first = service.build_snapshot().model_dump(mode="json")
    second = service.build_snapshot().model_dump(mode="json")

    assert first == second
    assert _serialized(first) == _serialized(second)


def test_after_close_developments_represent_required_sections() -> None:
    payload = _build_payload()

    assert payload["latestSession"]["regularCloseAt"]
    assert payload["latestSession"]["nextRegularOpenAt"]
    assert payload["latestSession"]["basis"] == "sample_proxy"
    assert {item["key"] for item in payload["afterCloseDevelopments"]} == (
        EXPECTED_DEVELOPMENT_KEYS
    )

    for section_name in (
        "overnightContext",
        "futuresTone",
        "earningsCatalysts",
        "macroEvents",
        "geopoliticalEvents",
        "commodityMoves",
        "ratesMoves",
    ):
        section = payload[section_name]
        assert section["state"] in QUALITY_STATES
        assert section["items"]
        assert section["summary"]
        for item in section["items"]:
            assert item["basis"] in QUALITY_STATES
            assert item["observation"]
            assert item["researchContext"]

    assert payload["todayWatchPoints"]
    assert all(item["basis"] in QUALITY_STATES for item in payload["todayWatchPoints"])


def test_after_close_developments_do_not_claim_real_news_or_live_after_hours_data() -> None:
    payload = _build_payload()

    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden_field in FORBIDDEN_NEWS_FIELDS:
        assert f'"{forbidden_field}"' not in serialized

    for item in payload["afterCloseDevelopments"]:
        assert item["basis"] in QUALITY_STATES
        assert item["evidenceState"] in QUALITY_STATES
    assert payload["dataQuality"]["state"] == "sample_proxy"
    assert "实时" not in serialized
    assert "live" not in serialized.lower()


def test_after_close_developments_exclude_advice_execution_and_internal_markers() -> None:
    serialized = _serialized(_build_payload())

    leaked = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_after_close_schema_rejects_forbidden_public_text_and_schema_drift() -> None:
    payload = _build_payload()
    payload["overnightContext"]["summary"] = "debug provider raw payload"

    with pytest.raises(ValidationError):
        HomepageAfterCloseDevelopmentsSnapshot.model_validate(payload)

    payload = _build_payload()
    payload["schemaVersion"] = "homepage_after_close_developments_v2"

    with pytest.raises(ValidationError):
        HomepageAfterCloseDevelopmentsSnapshot.model_validate(payload)


def test_after_close_service_has_no_live_provider_http_or_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_after_close_developments_service.py"
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported_modules.add(node.module)
            imported_modules.update(
                f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*"
            )

    violations = sorted(
        module
        for module in imported_modules
        if any(
            module == prefix or module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        )
    )
    assert violations == []
