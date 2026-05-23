# -*- coding: utf-8 -*-
"""Tests for inert official-public CN money-market rate contracts."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src.services.cn_money_market_rates_contracts import (
    OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV,
    OFFICIAL_CN_MONEY_MARKET_RATES_CONTEXT_METRICS,
    OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
    OFFICIAL_CN_MONEY_MARKET_RATES_REQUIRED_METRICS,
    CnMoneyMarketRatesProviderUnavailable,
    build_official_cn_money_market_rates_snapshot,
    get_cn_money_market_rate_contract,
    list_cn_money_market_rate_contracts,
    read_official_cn_money_market_rates_cache,
)
from src.services.market_data_source_registry import CANONICAL_SOURCE_TYPES


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "services" / "cn_money_market_rates_contracts.py"
CN_TZ = ZoneInfo("Asia/Shanghai")
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "src.services.market_overview_service",
    "src.services.market_cache",
    "src.services.liquidity_monitor_service",
    "api.v1.endpoints.market",
)


def _official_payload(
    *,
    as_of: str,
    publication_date: str = "2026-05-23",
    trading_date: str = "2026-05-23",
    observations: list[dict[str, object]] | None = None,
    holiday_calendar_qualified: bool = True,
) -> dict[str, object]:
    return {
        "providerId": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "source": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "sourceType": "official_public",
        "sourceTier": "official_public",
        "asOf": as_of,
        "publicationDate": publication_date,
        "tradingDate": trading_date,
        "holidayCalendarQualified": holiday_calendar_qualified,
        "freshness": "delayed",
        "observations": observations
        if observations is not None
        else [
            {"symbol": "DR007", "value": 1.86, "unit": "%"},
            {"symbol": "SHIBOR", "officialSeriesId": "SHIBOR_ON", "value": 1.72, "unit": "%"},
            {"symbol": "SHIBOR_3M", "value": 1.91, "unit": "%"},
            {"symbol": "LPR_1Y", "value": 3.45, "unit": "%"},
            {"symbol": "LPR_5Y", "value": 3.95, "unit": "%"},
            {"symbol": "CN10Y", "value": 2.35, "unit": "%"},
        ],
    }


def _module_imports() -> set[str]:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def test_cn_money_market_contract_registry_keeps_required_and_context_metrics() -> None:
    contracts = list_cn_money_market_rate_contracts()

    assert [item.official_series_id for item in contracts] == [
        *OFFICIAL_CN_MONEY_MARKET_RATES_REQUIRED_METRICS,
        *OFFICIAL_CN_MONEY_MARKET_RATES_CONTEXT_METRICS,
    ]
    assert get_cn_money_market_rate_contract("shibor") is not None
    assert get_cn_money_market_rate_contract("shibor").official_series_id == "SHIBOR_ON"  # type: ignore[union-attr]
    assert get_cn_money_market_rate_contract("lpr_5y").source_class in CANONICAL_SOURCE_TYPES  # type: ignore[union-attr]


def test_valid_official_cn_money_market_cache_normalizes_required_metrics_without_scoring() -> None:
    now = datetime(2026, 5, 23, 10, 5, tzinfo=CN_TZ)
    as_of = (now - timedelta(minutes=5)).isoformat(timespec="seconds")

    snapshot = build_official_cn_money_market_rates_snapshot(
        _official_payload(as_of=as_of),
        now=now,
    )

    assert snapshot["providerId"] == OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID
    assert snapshot["source"] == OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID
    assert snapshot["sourceType"] == "official_public"
    assert snapshot["sourceTier"] == "official_public"
    assert snapshot["cacheOnly"] is True
    assert snapshot["externalProviderCalls"] is False
    assert snapshot["observationOnly"] is True
    assert snapshot["sourceAuthorityAllowed"] is True
    assert snapshot["scoreContributionAllowed"] is False
    assert snapshot["fulfilledMetrics"] == ["DR007", "SHIBOR_ON"]
    assert snapshot["missingMetrics"] == []
    assert snapshot["requiredSeries"] == ["DR007", "SHIBOR_ON"]
    assert snapshot["fulfilledSeries"] == ["DR007", "SHIBOR_ON"]
    assert snapshot["missingSeries"] == []
    assert snapshot["contextSeries"] == ["SHIBOR_3M", "LPR_1Y", "LPR_5Y", "CN10Y"]
    assert snapshot["coverageRatio"] == 1.0
    assert snapshot["publicationDate"] == "2026-05-23"
    assert snapshot["tradingDate"] == "2026-05-23"
    assert snapshot["sourceFreshnessEvidence"]["externalProviderCalls"] is False
    assert snapshot["sourceFreshnessEvidence"]["coverageRatio"] == 1.0
    assert snapshot["reasonCodes"] == ["official_cn_money_market_rates_cache_valid_diagnostic_only"]
    bundle = snapshot["cacheBundleDiagnostics"]
    assert bundle["providerId"] == OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID
    assert bundle["sourceType"] == "official_public"
    assert bundle["externalProviderCalls"] is False
    assert bundle["scoreContributionAllowed"] is False
    assert bundle["observationOnly"] is True
    assert bundle["requiredSeries"] == ["DR007", "SHIBOR_ON"]
    assert bundle["fulfilledSeries"] == ["DR007", "SHIBOR_ON"]
    assert bundle["missingSeries"] == []
    assert bundle["coverageRatio"] == 1.0
    assert bundle["contextSeries"] == ["SHIBOR_3M", "LPR_1Y", "LPR_5Y", "CN10Y"]
    assert "CN10Y" in bundle["contextOnlySeries"]

    by_series = {item["officialSeriesId"]: item for item in snapshot["items"]}
    assert by_series["DR007"]["symbol"] == "DR007"
    assert by_series["DR007"]["unit"] == "%"
    assert by_series["DR007"]["currency"] is None
    assert by_series["DR007"]["sourceAuthorityAllowed"] is True
    assert by_series["DR007"]["scoreContributionAllowed"] is False
    assert by_series["DR007"]["observationOnly"] is True
    assert by_series["SHIBOR_ON"]["symbol"] == "SHIBOR"
    assert by_series["SHIBOR_ON"]["sourceId"] == "SHIBOR_ON"
    assert "cn10y_context_only_not_yield_curve_authority" in by_series["CN10Y"]["reasonCodes"]
    assert by_series["CN10Y"]["scoreContributionAllowed"] is False


def test_cache_reader_reads_only_configured_local_json_and_redacts_path(tmp_path: Path) -> None:
    now = datetime(2026, 5, 23, 10, 5, tzinfo=CN_TZ)
    path = tmp_path / "private-cn-money-market-cache.json"
    path.write_text(
        json.dumps(
            _official_payload(as_of=(now - timedelta(minutes=5)).isoformat(timespec="seconds")),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    snapshot = read_official_cn_money_market_rates_cache(
        env={OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV: str(path)},
        now=now,
    )

    assert snapshot["externalProviderCalls"] is False
    assert snapshot["fulfilledMetrics"] == ["DR007", "SHIBOR_ON"]
    assert str(path) not in json.dumps(snapshot, ensure_ascii=False, sort_keys=True)


@pytest.mark.parametrize(
    ("payload", "expected_reasons"),
    [
        (
            _official_payload(
                as_of=datetime(2026, 5, 23, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds"),
                observations=[],
            ),
            {"empty_payload"},
        ),
        ("not-a-dict", {"malformed_payload"}),
        (
            _official_payload(
                as_of=datetime(2026, 5, 23, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds"),
                observations=[{"symbol": "DR007", "value": 1.86, "unit": "%"}],
            ),
            {"missing_required_metric", "partial_official_coverage"},
        ),
        (
            _official_payload(
                as_of=datetime(2026, 5, 10, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds"),
                publication_date="2026-05-10",
                trading_date="2026-05-10",
            ),
            {"stale_official_release"},
        ),
        (
            _official_payload(
                as_of=datetime(2026, 5, 23, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds"),
                publication_date="",
                trading_date="",
            ),
            {"missing_publication_or_trading_date"},
        ),
        (
            _official_payload(
                as_of=datetime(2026, 5, 23, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds"),
                holiday_calendar_qualified=False,
            ),
            {"holiday_calendar_unqualified_date_ambiguity"},
        ),
        (
            _official_payload(
                as_of=datetime(2026, 5, 23, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds"),
                observations=[
                    {"symbol": "DR007", "value": 1.86, "unit": "bp"},
                    {"symbol": "SHIBOR", "officialSeriesId": "SHIBOR_ON", "value": 1.72, "unit": "%"},
                ],
            ),
            {"unsupported_unit"},
        ),
        (
            _official_payload(
                as_of=datetime(2026, 5, 23, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds"),
                observations=[
                    {"symbol": "DR007", "value": "N/A", "unit": "%"},
                    {"symbol": "SHIBOR", "officialSeriesId": "SHIBOR_ON", "value": 1.72, "unit": "%"},
                ],
            ),
            {"unsupported_value_format"},
        ),
    ],
)
def test_official_cn_money_market_snapshot_fails_closed_with_sanitized_reason(
    payload: object,
    expected_reasons: set[str],
) -> None:
    now = datetime(2026, 5, 23, 10, 5, tzinfo=CN_TZ)

    with pytest.raises(CnMoneyMarketRatesProviderUnavailable) as exc:
        build_official_cn_money_market_rates_snapshot(payload, now=now)

    assert expected_reasons.issubset(set(exc.value.reason_codes))
    serialized = json.dumps(exc.value.to_dict(), ensure_ascii=False, sort_keys=True)
    assert "SECRET" not in serialized
    assert "providerPayload" not in serialized
    assert "private-cn-money-market-cache" not in serialized


def test_cache_reader_missing_and_malformed_cache_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(CnMoneyMarketRatesProviderUnavailable) as missing_config:
        read_official_cn_money_market_rates_cache(env={})
    assert missing_config.value.reason_codes == ("missing_cache_config",)

    missing_path = tmp_path / "missing.json"
    with pytest.raises(CnMoneyMarketRatesProviderUnavailable) as missing_cache:
        read_official_cn_money_market_rates_cache(
            env={OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV: str(missing_path)}
        )
    assert missing_cache.value.reason_codes == ("missing_cache",)

    malformed_path = tmp_path / "private-cn-money-market-cache.json"
    malformed_path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(CnMoneyMarketRatesProviderUnavailable) as malformed:
        read_official_cn_money_market_rates_cache(
            env={OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV: str(malformed_path)}
        )
    assert malformed.value.reason_codes == ("malformed_payload",)
    assert str(malformed_path) not in json.dumps(malformed.value.to_dict(), sort_keys=True)


def test_contract_module_stays_stdlib_only_and_out_of_provider_runtime() -> None:
    forbidden_imports = sorted(
        module
        for module in _module_imports()
        if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    assert forbidden_imports == []


def test_contract_module_import_has_no_runtime_side_effects() -> None:
    script = """
import json
import src.services.cn_money_market_rates_contracts
blocked = [
    "src.services.market_overview_service",
    "src.services.market_cache",
    "src.services.liquidity_monitor_service",
    "data_provider.tickflow_fetcher",
    "api.v1.endpoints.market",
]
print(json.dumps({name: name in __import__('sys').modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}
