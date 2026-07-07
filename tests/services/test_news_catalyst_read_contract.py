# -*- coding: utf-8 -*-
"""Tests for the provider-neutral news/catalyst read contract foundation."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/news_catalyst_read_contract.py"

EXPECTED_FAMILIES = {
    "stock_news",
    "market_news",
    "earnings_event_calendar",
    "macro_policy_catalyst",
    "company_developments",
}

EXPECTED_STATES = {
    "NO_ITEMS",
    "FETCH_FAILED",
    "NOT_CONFIGURED",
    "STALE",
    "PARTIAL",
    "READY",
}

FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.search_service",
    "src.services.market_cache",
    "src.services.market_overview_yfinance_transport",
    "src.services.market_overview_sina_transport",
    "src.services.market_overview_sentiment_transport",
    "src.services.stock_service_provider_adapter",
)

FORBIDDEN_PUBLIC_MARKERS = (
    "apiKey",
    "api_key",
    "authorization",
    "bearer ",
    "cacheKey",
    "credential",
    "providerOrder",
    "rawPayload",
    "raw_payload",
    "requestId",
    "secret",
    "stack trace",
    "token=",
    "traceback",
)


def _load_helper_module() -> Any:
    try:
        return importlib.import_module("src.services.news_catalyst_read_contract")
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised by RED
        pytest.fail(f"news/catalyst read contract helper missing: {exc}")


def _helper_imports() -> set[str]:
    if not HELPER_PATH.exists():
        pytest.fail(f"helper file missing: {HELPER_PATH}")
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _family(payload: dict[str, Any], key: str) -> dict[str, Any]:
    return payload["families"][key]


def test_contract_defaults_fail_closed_without_source_configuration() -> None:
    helper = _load_helper_module()
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    contract = helper.build_news_catalyst_read_contract_v1(
        {"asOf": "2026-07-07T09:30:00", "timezone": "Asia/Shanghai"}
    )

    assert contract["contractVersion"] == helper.NEWS_CATALYST_READ_CONTRACT_VERSION
    assert contract["providerNeutral"] is True
    assert contract["networkCallsEnabled"] is False
    assert contract["runtimeProviderCalls"] is False
    assert contract["capabilityFamilies"] == list(helper.NEWS_CATALYST_CAPABILITY_FAMILIES)
    assert set(contract["families"]) == EXPECTED_FAMILIES
    assert contract["asOf"] == "2026-07-07T09:30:00+08:00"
    assert contract["timezone"] == "Asia/Shanghai"

    for family in contract["families"].values():
        assert family["readinessState"] == "NOT_CONFIGURED"
        assert family["freshnessState"] == "NOT_CONFIGURED"
        assert family["itemCount"] == 0
        assert family["items"] == []
        assert family["noItemState"]["isNoItems"] is False
        assert family["failureState"]["isFailed"] is False
        assert family["publicDisplay"]["rawProviderPayloadExposed"] is False


def test_no_items_fetch_failed_and_not_configured_are_distinct() -> None:
    helper = _load_helper_module()

    contract = helper.build_news_catalyst_read_contract_v1(
        {
            "asOf": "2026-07-07T12:00:00Z",
            "timezone": "UTC",
            "families": {
                "stock_news": {
                    "source": {
                        "sourceId": "licensed-news-feed",
                        "sourceType": "newswire",
                        "authority": "licensed_third_party",
                    },
                    "state": "no_items",
                    "items": [],
                    "evidenceRef": "evidence:stock-news-empty",
                },
                "market_news": {
                    "source": {
                        "sourceId": "market-news-feed",
                        "sourceType": "newswire",
                        "authority": "licensed_third_party",
                    },
                    "state": "failed",
                    "failureReason": "provider_timeout requestId=REQ-1 token=secret",
                    "items": [],
                    "rawPayload": {"stack trace": "Traceback: internal"},
                },
            },
        }
    )

    stock_news = _family(contract, "stock_news")
    market_news = _family(contract, "market_news")
    earnings = _family(contract, "earnings_event_calendar")

    assert stock_news["readinessState"] == "NO_ITEMS"
    assert stock_news["freshnessState"] == "NO_ITEMS"
    assert stock_news["noItemState"] == {
        "isNoItems": True,
        "reason": "source_returned_no_items",
    }
    assert stock_news["failureState"]["isFailed"] is False

    assert market_news["readinessState"] == "FETCH_FAILED"
    assert market_news["freshnessState"] == "FETCH_FAILED"
    assert market_news["noItemState"]["isNoItems"] is False
    assert market_news["failureState"] == {
        "isFailed": True,
        "reason": "provider_timeout",
    }

    assert earnings["readinessState"] == "NOT_CONFIGURED"
    assert {family["readinessState"] for family in contract["families"].values()} <= EXPECTED_STATES

    serialized = json.dumps(contract, ensure_ascii=False)
    for marker in FORBIDDEN_PUBLIC_MARKERS:
        assert marker not in serialized


def test_stale_partial_and_ready_states_keep_timestamp_and_timezone_evidence() -> None:
    helper = _load_helper_module()

    contract = helper.build_news_catalyst_read_contract_v1(
        {
            "asOf": "2026-07-07T12:00:00+00:00",
            "timezone": "UTC",
            "families": {
                "stock_news": {
                    "source": {
                        "sourceId": "stock-news-authority",
                        "sourceType": "newswire",
                        "authority": "licensed_third_party",
                    },
                    "maxAgeHours": 24,
                    "items": [
                        {
                            "title": "Company confirms product launch",
                            "summary": "Company-primary product launch notice.",
                            "publishedAt": "2026-07-05T00:00:00Z",
                            "eventTimestamp": "2026-07-09T13:00:00Z",
                            "timezone": "UTC",
                            "sourceId": "stock-news-authority",
                            "sourceType": "newswire",
                            "sourceAuthority": "licensed_third_party",
                            "evidenceRef": "evidence:stale-stock-news",
                        }
                    ],
                },
                "earnings_event_calendar": {
                    "source": {
                        "sourceId": "calendar-feed",
                        "sourceType": "earnings_calendar",
                        "authority": "licensed_third_party",
                    },
                    "items": [
                        {
                            "title": "Company earnings tomorrow",
                            "summary": "Provider supplied a headline but no event timestamp.",
                            "publishedAt": "2026-07-07T08:00:00Z",
                            "sourceId": "calendar-feed",
                            "sourceType": "earnings_calendar",
                            "sourceAuthority": "licensed_third_party",
                            "evidenceRef": "evidence:calendar-partial",
                        }
                    ],
                },
                "company_developments": {
                    "source": {
                        "sourceId": "company-ir",
                        "sourceType": "company_ir",
                        "authority": "company_primary",
                    },
                    "items": [
                        {
                            "title": "Company posts board-approved development update",
                            "summary": "Company IR published a bounded operational development.",
                            "publishedAt": "2026-07-07T07:30:00Z",
                            "eventTimestamp": "2026-07-07T07:30:00Z",
                            "timezone": "UTC",
                            "sourceId": "company-ir",
                            "sourceType": "company_ir",
                            "sourceAuthority": "company_primary",
                            "evidenceRef": "evidence:company-development-ready",
                        }
                    ],
                },
            },
        }
    )

    stock_news = _family(contract, "stock_news")
    earnings = _family(contract, "earnings_event_calendar")
    company = _family(contract, "company_developments")

    assert stock_news["readinessState"] == "STALE"
    assert stock_news["freshnessState"] == "STALE"
    assert stock_news["staleReason"] == "published_at_exceeds_max_age"
    assert stock_news["items"][0]["publishedAt"] == "2026-07-05T00:00:00+00:00"
    assert stock_news["items"][0]["eventTimestamp"] == "2026-07-09T13:00:00+00:00"
    assert stock_news["items"][0]["timezone"] == "UTC"

    assert earnings["readinessState"] == "PARTIAL"
    assert earnings["items"][0]["eventTimestamp"] is None
    assert "event_timestamp_missing" in earnings["items"][0]["limitations"]

    assert company["readinessState"] == "READY"
    assert company["freshnessState"] == "FRESH"
    assert company["itemCount"] == 1


def test_sample_scaffold_items_are_not_exposed_as_current_news_or_events() -> None:
    helper = _load_helper_module()

    contract = helper.build_news_catalyst_read_contract_v1(
        {
            "asOf": "2026-07-07T12:00:00Z",
            "timezone": "UTC",
            "families": {
                "macro_policy_catalyst": {
                    "source": {
                        "sourceId": "macro-policy-feed",
                        "sourceType": "government_release",
                        "authority": "official_public",
                    },
                    "items": [
                        {
                            "title": "Sample FOMC decision today",
                            "summary": "Scaffold event must not become current evidence.",
                            "publishedAt": "2026-07-07T10:00:00Z",
                            "eventTimestamp": "2026-07-07T18:00:00Z",
                            "sourceId": "macro-policy-feed",
                            "sourceType": "government_release",
                            "sourceAuthority": "official_public",
                            "evidenceRef": "fixture:macro-policy-sample",
                            "sample": True,
                        }
                    ],
                }
            },
        }
    )

    macro = _family(contract, "macro_policy_catalyst")

    assert macro["readinessState"] == "NO_ITEMS"
    assert macro["itemCount"] == 0
    assert macro["items"] == []
    assert macro["noItemState"] == {
        "isNoItems": True,
        "reason": "sample_items_filtered",
    }
    assert macro["publicDisplay"]["sampleItemsExposedAsCurrent"] is False
    assert "Sample FOMC" not in json.dumps(contract, ensure_ascii=False)


def test_contract_does_not_infer_catalysts_or_event_dates_from_missing_data() -> None:
    helper = _load_helper_module()

    contract = helper.build_news_catalyst_read_contract_v1(
        {
            "asOf": "2026-07-07T12:00:00Z",
            "timezone": "UTC",
            "families": {
                "company_developments": {
                    "source": {
                        "sourceId": "company-ir",
                        "sourceType": "company_ir",
                        "authority": "company_primary",
                    },
                    "newsContext": "Management may announce a product catalyst tomorrow.",
                    "items": [],
                }
            },
        }
    )

    company = _family(contract, "company_developments")

    assert company["readinessState"] == "NO_ITEMS"
    assert company["itemCount"] == 0
    assert company["items"] == []
    assert company["evidenceRef"] is None
    assert "tomorrow" not in json.dumps(company, ensure_ascii=False).lower()
