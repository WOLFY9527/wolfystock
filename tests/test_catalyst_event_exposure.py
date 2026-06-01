# -*- coding: utf-8 -*-
"""Focused tests for pure catalyst event exposure projection."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path

from src.services import catalyst_event_exposure
from src.services.catalyst_event_exposure import build_catalyst_event_exposures


AS_OF = datetime(2026, 5, 18, 15, 30, tzinfo=timezone.utc)


def _as_payload(items: tuple[object, ...]) -> list[dict[str, object]]:
    return [item.to_dict() for item in items]


def test_deterministic_inputs_project_to_observation_only_catalyst_exposure() -> None:
    items = build_catalyst_event_exposures(
        symbol="AAPL",
        market="us",
        as_of=AS_OF,
        fundamental_snapshot={
            "reportedPeriod": "2026Q2",
            "summary": "Quarterly revenue and margin snapshot is available.",
            "asOf": "2026-05-17T20:00:00+00:00",
            "freshness": "delayed",
            "providerPayload": {"raw": "must-not-leak"},
        },
        stored_news_items=[
            {
                "headline": "Supplier commentary mentions demand stabilization",
                "summary": "Stored article summary references a potential demand catalyst.",
                "publishedAt": "2026-05-17T13:00:00+00:00",
                "rawPayload": {"body": "must-not-leak"},
            }
        ],
        official_macro_status={
            "status": "cache_hit",
            "asOf": "2026-05-17",
            "series": [{"symbol": "CPIAUCSL", "name": "CPI"}],
            "admin": {"trace": "must-not-leak"},
        },
    )

    payload = _as_payload(items)

    assert [item["category"] for item in payload] == [
        "earnings_fundamental_snapshot",
        "stored_news_catalyst_proxy",
        "official_macro_cache_status",
    ]
    assert [item["id"] for item in payload] == [
        "catalyst:AAPL:us:fundamental",
        "catalyst:AAPL:us:news:1",
        "catalyst:AAPL:us:macro",
    ]
    for item in payload:
        assert item["observationOnly"] is True
        assert item["sourceAuthorityAllowed"] is False
        assert item["scoreContributionAllowed"] is False
        assert item["decisionGrade"] is False
        assert item["calendarClaimAllowed"] is False
        assert item["investmentAdviceAllowed"] is False
        assert "observation_only" in item["reasonCodes"]

    assert payload[0]["timeframe"] == "2026Q2"
    assert payload[1]["evidenceLabels"] == ["proxy", "unverified"]
    assert payload[2]["evidenceLabels"] == ["delayed"]
    assert "no scheduled macro calendar authority is inferred" in str(payload[2]["summary"])


def test_missing_stale_and_proxy_evidence_fail_closed() -> None:
    assert build_catalyst_event_exposures(symbol="AAPL", market="us", as_of=AS_OF) == ()

    payload = _as_payload(
        build_catalyst_event_exposures(
            symbol="AAPL",
            market="us",
            as_of=AS_OF,
            fundamental_snapshot={
                "summary": "Delayed snapshot only.",
                "stale": True,
                "asOf": "2026-04-30T20:00:00+00:00",
            },
            stored_news_items=[
                {
                    "headline": "Cached headline",
                    "summary": "Cached summary.",
                    "stale": True,
                    "publishedAt": "2026-04-29T12:00:00+00:00",
                }
            ],
            official_macro_status={
                "status": "stale",
                "asOf": "2026-04-29",
            },
        )
    )

    assert len(payload) == 3
    for item in payload:
        assert item["sourceAuthorityAllowed"] is False
        assert item["scoreContributionAllowed"] is False
        assert item["decisionGrade"] is False
        assert "stale" in item["evidenceLabels"]
        assert "stale_evidence" in item["reasonCodes"]
    assert "proxy" in payload[1]["evidenceLabels"]
    assert "proxy_evidence_not_authoritative" in payload[1]["reasonCodes"]


def test_raw_provider_news_and_admin_fields_do_not_leak() -> None:
    payload = _as_payload(
        build_catalyst_event_exposures(
            symbol="MSFT",
            market="us",
            as_of=AS_OF,
            fundamental_snapshot={
                "summary": "Fundamental summary.",
                "provider": "secret-provider-name",
                "provider_payload": {"secret": "raw-fundamental-secret"},
            },
            stored_news_items=[
                {
                    "headline": "Stored catalyst headline",
                    "summary": "Stored catalyst summary.",
                    "sourceProvider": "secret-news-provider",
                    "raw_article": "raw-news-secret",
                }
            ],
            official_macro_status={
                "status": "available",
                "debug": "macro-debug-secret",
                "adminOnly": "admin-secret",
                "rawPayload": {"value": "raw-macro-secret"},
            },
        )
    )

    serialized = json.dumps(payload, sort_keys=True)

    for forbidden in (
        "secret-provider-name",
        "raw-fundamental-secret",
        "secret-news-provider",
        "raw-news-secret",
        "macro-debug-secret",
        "admin-secret",
        "raw-macro-secret",
        "provider_payload",
        "rawPayload",
        "adminOnly",
    ):
        assert forbidden not in serialized


def test_helper_imports_no_provider_search_or_cache_call_seams() -> None:
    source_path = Path(catalyst_event_exposure.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    imported_modules: set[str] = set()
    referenced_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Name):
            referenced_names.add(node.id)

    forbidden_import_prefixes = {
        "data_provider",
        "src.search_service",
        "src.services.search_service",
        "src.services.market_cache",
        "src.services.market_cache_service",
        "requests",
        "urllib",
    }
    for module_name in imported_modules:
        assert not any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in forbidden_import_prefixes)

    assert "MarketCache" not in referenced_names
