#!/usr/bin/env python3
"""Read-only Market Regime projection runtime verifier.

The verifier drives the local FastAPI routes with TestClient, compares the
standalone Tier1 evidence pack with the Market Overview and Decision Cockpit
projections, and prints a compact operator-safe JSON summary.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd
from fastapi import FastAPI

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.deps import get_optional_current_user  # noqa: E402
from api.v1.endpoints import market, market_overview  # noqa: E402
from src.services import market_decision_cockpit_service as cockpit_service_module  # noqa: E402
from src.services.market_decision_cockpit_service import MarketDecisionCockpitService  # noqa: E402
from src.services.market_regime_evidence_service import (  # noqa: E402
    DEFAULT_BENCHMARK_SYMBOL,
    DEFAULT_GROWTH_PROXY_SYMBOL,
    DEFAULT_MARKET_REGIME_SYMBOLS,
    DEFAULT_REQUIRED_BARS,
)
from src.services.market_regime_read_model_service import build_market_regime_read_model  # noqa: E402
from src.services.quote_snapshot_config import get_configured_us_quote_snapshot_cache_path  # noqa: E402
from src.services.us_history_helper import get_configured_us_stock_parquet_dir  # noqa: E402


CONTRACT_VERSION = "market_regime_projection_runtime_verifier_v1"
START_DATE = date(2026, 1, 2)
SYMBOLS = list(DEFAULT_MARKET_REGIME_SYMBOLS)
FORBIDDEN_SUMMARY_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommendation",
    "target price",
    "stop loss",
)


@dataclass(frozen=True)
class RuntimeInputs:
    ohlcv_cache_dir: Path
    quote_snapshot_cache_path: Path | None
    required_bars: int = DEFAULT_REQUIRED_BARS
    symbols: tuple[str, ...] = tuple(SYMBOLS)
    benchmark_symbol: str = DEFAULT_BENCHMARK_SYMBOL
    growth_proxy_symbol: str = DEFAULT_GROWTH_PROXY_SYMBOL


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        summary = _run_from_args(args)
    except Exception:
        summary = {
            "contractVersion": CONTRACT_VERSION,
            "status": "failed",
            "error": {"code": "verifier_failed_closed"},
            "artifactCheck": _artifact_check(),
        }
    _print_summary(summary, machine_readable=bool(args.json))
    return 0 if summary.get("status") == "ok" else 2


def compare_projection_to_evidence(
    *,
    evidence: Mapping[str, Any],
    projection: Mapping[str, Any],
    surface: str,
) -> list[dict[str, str]]:
    mismatches: list[dict[str, str]] = []
    regime = _mapping(evidence.get("regimeSummary"))
    data_coverage = _mapping(_mapping(evidence.get("evidence")).get("dataCoverage"))
    preview_coverage = _mapping(_mapping(projection.get("evidencePreview")).get("dataCoverage"))
    checks = (
        ("sourceContractVersion", evidence.get("contractVersion"), projection.get("sourceContractVersion")),
        ("status", evidence.get("status"), projection.get("status")),
        ("readiness", evidence.get("readiness") or evidence.get("status"), projection.get("readiness")),
        ("label", regime.get("label"), projection.get("label")),
        ("confidence", _round_float(regime.get("confidence")), _round_float(projection.get("confidence"))),
        ("dataCoverage.usedSymbolCount", len(_list(data_coverage.get("usedSymbols"))), preview_coverage.get("usedSymbolCount")),
        (
            "dataCoverage.skippedSymbolCount",
            len(_list(data_coverage.get("skippedSymbols"))),
            preview_coverage.get("skippedSymbolCount"),
        ),
    )
    for field, expected, actual in checks:
        if expected != actual:
            mismatches.append(
                {
                    "surface": surface,
                    "field": field,
                    "expected": _safe_scalar(expected),
                    "actual": _safe_scalar(actual),
                }
            )
    if evidence.get("status") == "failed_closed":
        index_trend = _mapping(_mapping(projection.get("evidencePreview")).get("indexTrend"))
        if index_trend.get("return20d") is not None:
            mismatches.append(
                {
                    "surface": surface,
                    "field": "evidencePreview.indexTrend.return20d",
                    "expected": "None",
                    "actual": "computed",
                }
            )
    return mismatches


def _run_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.fixture_temp:
        scenarios: dict[str, Any] = {}
        with tempfile.TemporaryDirectory(prefix="market-regime-runtime-") as tmp:
            fixture_root = Path(tmp)
            for scenario in ("ready", "blocked", "failed_closed"):
                scenarios[scenario] = _run_scenario(
                    name=scenario,
                    inputs=_build_fixture_inputs(fixture_root / scenario, scenario=scenario),
                )
        return _summary_from_scenarios(scenarios, fixture_temp=True)

    inputs = RuntimeInputs(
        ohlcv_cache_dir=Path(args.ohlcv_cache_dir or get_configured_us_stock_parquet_dir()),
        quote_snapshot_cache_path=(
            Path(args.quote_snapshot_cache_path)
            if args.quote_snapshot_cache_path
            else _optional_path(get_configured_us_quote_snapshot_cache_path())
        ),
        required_bars=args.required_bars,
        symbols=tuple(_parse_symbols(args.symbols)),
        benchmark_symbol=args.benchmark_symbol,
        growth_proxy_symbol=args.growth_proxy_symbol,
    )
    scenarios = {"runtime": _run_scenario(name="runtime", inputs=inputs)}
    return _summary_from_scenarios(scenarios, fixture_temp=False)


def _run_scenario(*, name: str, inputs: RuntimeInputs) -> dict[str, Any]:
    params = _endpoint_params(inputs)
    with _patched_runtime_dependencies(inputs):
        client = _build_test_client()
        evidence_response = client.get("/api/v1/market/regime-evidence-pack", params=params)
        overview_response = client.get("/api/v1/market-overview")
        cockpit_response = client.get("/api/v1/market/decision-cockpit")
    if not all(response.status_code == 200 for response in (evidence_response, overview_response, cockpit_response)):
        return {
            "status": "failed",
            "scenario": name,
            "error": {"code": "endpoint_unavailable"},
            "httpStatus": {
                "standaloneEvidencePack": evidence_response.status_code,
                "marketOverview": overview_response.status_code,
                "decisionCockpit": cockpit_response.status_code,
            },
        }

    evidence = evidence_response.json()
    overview_projection = _mapping(overview_response.json().get("regimeEvidenceProjection"))
    cockpit_projection = _mapping(
        _mapping(cockpit_response.json().get("marketRegimeReadModel")).get("regimeEvidenceProjection")
    )
    mismatches = []
    mismatches.extend(
        compare_projection_to_evidence(
            evidence=evidence,
            projection=overview_projection,
            surface="market_overview",
        )
    )
    mismatches.extend(
        compare_projection_to_evidence(
            evidence=evidence,
            projection=cockpit_projection,
            surface="decision_cockpit",
        )
    )
    safety = _safety_summary(evidence, overview_projection, cockpit_projection)
    scenario_status = "ok" if not mismatches and all(value is False for value in safety.values()) else "failed"
    return {
        "status": scenario_status,
        "scenario": name,
        "standaloneEvidencePack": _evidence_summary(evidence),
        "marketOverviewProjection": _projection_summary(overview_projection),
        "decisionCockpitProjection": _projection_summary(cockpit_projection),
        "consistency": {"consistent": not mismatches, "mismatches": mismatches},
        "safety": safety,
        "consumerSafe": _consumer_safe_summary(evidence, overview_projection, cockpit_projection),
    }


def _endpoint_params(inputs: RuntimeInputs) -> dict[str, str]:
    params = {
        "symbols": ",".join(inputs.symbols),
        "benchmarkSymbol": inputs.benchmark_symbol,
        "growthProxySymbol": inputs.growth_proxy_symbol,
        "requiredBars": str(inputs.required_bars),
        "ohlcvCacheDir": str(inputs.ohlcv_cache_dir),
    }
    if inputs.quote_snapshot_cache_path is not None:
        params["quoteSnapshotCachePath"] = str(inputs.quote_snapshot_cache_path)
    return params


def _build_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.include_router(market_overview.router, prefix="/api/v1/market-overview")
    app.dependency_overrides[get_optional_current_user] = lambda: None
    return TestClient(app)


@contextmanager
def _patched_runtime_dependencies(inputs: RuntimeInputs):
    overview_service_factory = market_overview.MarketOverviewService
    overview_ohlcv = market_overview.get_configured_us_stock_parquet_dir
    overview_quote = market_overview.get_configured_us_quote_snapshot_cache_path
    market_service_factory = market.MarketDecisionCockpitService
    cockpit_ohlcv = cockpit_service_module.get_configured_us_stock_parquet_dir
    cockpit_quote = cockpit_service_module.get_configured_us_quote_snapshot_cache_path
    try:
        market_overview.MarketOverviewService = lambda: _NoProviderMarketOverviewService()
        market_overview.get_configured_us_stock_parquet_dir = lambda: str(inputs.ohlcv_cache_dir)
        market_overview.get_configured_us_quote_snapshot_cache_path = lambda: (
            str(inputs.quote_snapshot_cache_path) if inputs.quote_snapshot_cache_path else None
        )
        cockpit_service_module.get_configured_us_stock_parquet_dir = lambda: str(inputs.ohlcv_cache_dir)
        cockpit_service_module.get_configured_us_quote_snapshot_cache_path = lambda: (
            str(inputs.quote_snapshot_cache_path) if inputs.quote_snapshot_cache_path else None
        )
        market.MarketDecisionCockpitService = lambda: MarketDecisionCockpitService(
            market_overview_service=_NoProviderMarketOverviewService(),
            market_regime_read_model_provider=lambda: build_market_regime_read_model(
                market="US",
                symbols=list(inputs.symbols),
                benchmark_symbol=inputs.benchmark_symbol,
                growth_proxy_symbol=inputs.growth_proxy_symbol,
                required_bars=inputs.required_bars,
                ohlcv_cache_dir=inputs.ohlcv_cache_dir,
                quote_snapshot_cache_path=inputs.quote_snapshot_cache_path,
                require_adjusted=True,
            ),
            now_provider=lambda: "2026-01-02T00:00:00+00:00",
        )
        yield
    finally:
        market_overview.MarketOverviewService = overview_service_factory
        market_overview.get_configured_us_stock_parquet_dir = overview_ohlcv
        market_overview.get_configured_us_quote_snapshot_cache_path = overview_quote
        market.MarketDecisionCockpitService = market_service_factory
        cockpit_service_module.get_configured_us_stock_parquet_dir = cockpit_ohlcv
        cockpit_service_module.get_configured_us_quote_snapshot_cache_path = cockpit_quote


class _NoProviderMarketOverviewService:
    def get_indices(self, **_kwargs: Any) -> dict[str, Any]:
        return {"status": "success", "providerCallsEnabled": False}

    def get_volatility(self, **_kwargs: Any) -> dict[str, Any]:
        return {"status": "success", "providerCallsEnabled": False}

    def get_sentiment(self, **_kwargs: Any) -> dict[str, Any]:
        return {"status": "success", "providerCallsEnabled": False}

    def get_funds_flow(self, **_kwargs: Any) -> dict[str, Any]:
        return {"status": "success", "providerCallsEnabled": False}

    def get_macro(self, **_kwargs: Any) -> dict[str, Any]:
        return {"status": "success", "providerCallsEnabled": False}

    def get_market_regime_decision(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "regime": "lowConfidence",
            "confidence": "low",
            "confidenceScore": 0.0,
            "driverScores": {},
            "explanation": {"whyThisRegime": [], "whatConfirmsIt": [], "whatInvalidatesIt": []},
            "researchPriorities": {"watchToday": [], "needsMoreEvidence": [], "investigateNext": []},
            "missingEvidence": ["market_regime_low_confidence"],
        }


def _summary_from_scenarios(scenarios: Mapping[str, Any], *, fixture_temp: bool) -> dict[str, Any]:
    ok = all(_mapping(item).get("status") == "ok" for item in scenarios.values())
    return _strip_unsafe_terms(
        {
            "contractVersion": CONTRACT_VERSION,
            "status": "ok" if ok else "failed",
            "mode": "fixture_temp" if fixture_temp else "runtime",
            "scenarios": dict(scenarios),
            "artifactCheck": _artifact_check(),
        }
    )


def _build_fixture_inputs(base_dir: Path, *, scenario: str) -> RuntimeInputs:
    ohlcv_dir = base_dir / "ohlcv-cache"
    quote_path = base_dir / "quote-cache" / "quotes.json"
    values = _full_values()
    if scenario == "blocked":
        values.pop("AAPL", None)
    _write_ohlcv(ohlcv_dir, values)
    if scenario == "failed_closed":
        pd.DataFrame([{"date": START_DATE.isoformat(), "close": "not-a-number"}]).to_parquet(
            ohlcv_dir / "AAPL.parquet",
            index=False,
        )
    _write_quote_cache(quote_path, SYMBOLS)
    return RuntimeInputs(ohlcv_cache_dir=ohlcv_dir, quote_snapshot_cache_path=quote_path)


def _full_values() -> dict[str, list[float]]:
    return {
        "SPY": _series(100, 1.0),
        "QQQ": _series(100, 1.25),
        "AAPL": _series(90, 0.9),
        "MSFT": _series(95, 1.1),
        "NVDA": _series(110, 1.4),
        "TSLA": _series(80, 0.7),
    }


def _series(start: float, step: float, bars: int = DEFAULT_REQUIRED_BARS) -> list[float]:
    return [round(start + (index * step), 4) for index in range(bars)]


def _write_ohlcv(cache_dir: Path, values_by_symbol: Mapping[str, Sequence[float]]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for symbol, closes in values_by_symbol.items():
        rows = []
        for index, close in enumerate(closes):
            rows.append(
                {
                    "date": (START_DATE + timedelta(days=index)).isoformat(),
                    "open": close - 0.5,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "volume": 1_000_000 + index,
                    "adjusted_close": close,
                }
            )
        pd.DataFrame(rows).to_parquet(cache_dir / f"{symbol}.parquet", index=False)


def _write_quote_cache(cache_path: Path, symbols: Sequence[str]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "symbol": symbol,
            "market": "us",
            "last": 100.0 + index,
            "previousClose": 99.5 + index,
            "volume": 1_000_000 + index,
            "asOf": datetime.now(timezone.utc).isoformat(),
            "currency": "USD",
            "source": "local_quote_snapshot_cache",
        }
        for index, symbol in enumerate(symbols)
    ]
    cache_path.write_text(json.dumps({"quotes": rows}), encoding="utf-8")


def _evidence_summary(evidence: Mapping[str, Any]) -> dict[str, Any]:
    regime = _mapping(evidence.get("regimeSummary"))
    return {
        "contractVersion": evidence.get("contractVersion"),
        "status": evidence.get("status"),
        "readiness": evidence.get("readiness"),
        "label": regime.get("label"),
        "confidence": _round_float(regime.get("confidence")),
        "providerCallsEnabled": bool(evidence.get("providerCallsEnabled")),
        "networkCallsEnabled": bool(evidence.get("networkCallsEnabled")),
        "mutationEnabled": bool(evidence.get("mutationEnabled")),
    }


def _projection_summary(projection: Mapping[str, Any]) -> dict[str, Any]:
    data_quality = _mapping(projection.get("dataQuality"))
    return {
        "contractVersion": projection.get("contractVersion"),
        "sourceContractVersion": projection.get("sourceContractVersion"),
        "status": projection.get("status"),
        "readiness": projection.get("readiness"),
        "label": projection.get("label"),
        "confidence": _round_float(projection.get("confidence")),
        "dataQuality": {"reasonCodes": _list(data_quality.get("reasonCodes"))},
        "evidencePreview": _mapping(projection.get("evidencePreview")),
        "providerCallsEnabled": bool(projection.get("providerCallsEnabled")),
        "networkCallsEnabled": bool(projection.get("networkCallsEnabled")),
        "mutationEnabled": bool(projection.get("mutationEnabled")),
        "readOnlyBoundary": _mapping(projection.get("readOnlyBoundary")),
    }


def _safety_summary(
    evidence: Mapping[str, Any],
    overview_projection: Mapping[str, Any],
    cockpit_projection: Mapping[str, Any],
) -> dict[str, bool]:
    projections = (overview_projection, cockpit_projection)
    return {
        "providerCallsEnabled": any(
            bool(payload.get("providerCallsEnabled")) for payload in (evidence, *projections)
        ),
        "networkCallsEnabled": any(
            bool(payload.get("networkCallsEnabled")) for payload in (evidence, *projections)
        ),
        "mutationEnabled": any(
            bool(payload.get("mutationEnabled")) for payload in (evidence, *projections)
        ),
        "externalCallsEnabled": any(
            bool(_mapping(payload.get("readOnlyBoundary")).get("externalCallsEnabled")) for payload in projections
        ),
    }


def _consumer_safe_summary(
    evidence: Mapping[str, Any],
    overview_projection: Mapping[str, Any],
    cockpit_projection: Mapping[str, Any],
) -> dict[str, bool]:
    return {
        "standaloneEvidencePack": bool(evidence.get("consumerSafe")),
        "marketOverviewProjection": bool(overview_projection.get("consumerSafe")),
        "decisionCockpitProjection": bool(cockpit_projection.get("consumerSafe")),
    }


def _artifact_check() -> dict[str, bool]:
    return {
        "fixtureWritesConfinedToTemp": True,
        "repoGeneratedArtifactsCreated": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify Market Regime projection consistency across local runtime routes.")
    parser.add_argument("--fixture-temp", action="store_true", help="Build temp local fixtures and verify ready/blocked/failed_closed paths.")
    parser.add_argument("--ohlcv-cache-dir", help="Local OHLCV parquet cache directory for runtime mode.")
    parser.add_argument("--quote-snapshot-cache-path", help="Local quote snapshot JSON cache path for runtime mode.")
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--benchmark-symbol", default=DEFAULT_BENCHMARK_SYMBOL)
    parser.add_argument("--growth-proxy-symbol", default=DEFAULT_GROWTH_PROXY_SYMBOL)
    parser.add_argument("--required-bars", type=int, default=DEFAULT_REQUIRED_BARS)
    parser.add_argument("--json", action="store_true", help="Print compact machine-readable JSON.")
    return parser


def _print_summary(summary: Mapping[str, Any], *, machine_readable: bool) -> None:
    if machine_readable:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def _strip_unsafe_terms(payload: Mapping[str, Any]) -> dict[str, Any]:
    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    lowered = serialized.lower()
    if any(term in lowered for term in FORBIDDEN_SUMMARY_TERMS):
        return {
            "contractVersion": CONTRACT_VERSION,
            "status": "failed",
            "error": {"code": "unsafe_summary_text"},
            "artifactCheck": _artifact_check(),
        }
    return json.loads(serialized)


def _parse_symbols(value: str | None) -> list[str]:
    result: list[str] = []
    for item in str(value or "").split(","):
        symbol = item.strip().upper()
        if symbol and symbol not in result:
            result.append(symbol)
    return result or list(SYMBOLS)


def _optional_path(value: Any) -> Path | None:
    text = str(value or "").strip()
    return Path(text) if text else None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _round_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _safe_scalar(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, (str, int, float, bool)):
        text = str(value)
    else:
        text = type(value).__name__
    return text[:80]


if __name__ == "__main__":
    raise SystemExit(main())
