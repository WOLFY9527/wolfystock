from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.services.market_regime_evidence_service import (
    DEFAULT_BENCHMARK_SYMBOL,
    DEFAULT_GROWTH_PROXY_SYMBOL,
    DEFAULT_MARKET_REGIME_SYMBOLS,
    DEFAULT_REQUIRED_BARS,
    MARKET_REGIME_EVIDENCE_CONTRACT_VERSION,
    build_market_regime_evidence_pack,
)


MARKET_REGIME_READ_MODEL_CONTRACT_VERSION = "market_regime_read_model_v1"
ALLOWED_REGIME_LABELS = {
    "risk_on_confirming",
    "risk_on_fragile",
    "mixed",
    "risk_off",
    "insufficient_data",
}


def build_market_regime_read_model(
    *,
    market: str = "US",
    symbols: Sequence[str] | None = None,
    benchmark_symbol: str = DEFAULT_BENCHMARK_SYMBOL,
    growth_proxy_symbol: str = DEFAULT_GROWTH_PROXY_SYMBOL,
    required_bars: int = DEFAULT_REQUIRED_BARS,
    ohlcv_cache_dir: str | Path | None,
    quote_snapshot_cache_path: str | Path | None = None,
    require_adjusted: bool = True,
    explicit_universe: Sequence[str] | None = None,
    quote_max_age_seconds: int = 60 * 60 * 24,
) -> dict[str, Any]:
    requested_symbols = _normalize_symbols(symbols or DEFAULT_MARKET_REGIME_SYMBOLS)
    benchmark = _normalize_symbol(benchmark_symbol) or DEFAULT_BENCHMARK_SYMBOL
    growth_proxy = _normalize_symbol(growth_proxy_symbol) or DEFAULT_GROWTH_PROXY_SYMBOL
    normalized_market = "US" if str(market or "").strip().upper() == "US" else "UNKNOWN"
    try:
        source = build_market_regime_evidence_pack(
            market=market,
            symbols=requested_symbols,
            benchmark_symbol=benchmark,
            growth_proxy_symbol=growth_proxy,
            required_bars=required_bars,
            ohlcv_cache_dir=ohlcv_cache_dir,
            quote_snapshot_cache_path=quote_snapshot_cache_path,
            require_adjusted=require_adjusted,
            explicit_universe=explicit_universe,
            quote_max_age_seconds=quote_max_age_seconds,
        )
    except Exception:
        source = _failed_closed_source(
            market=normalized_market,
            symbols=requested_symbols,
            benchmark_symbol=benchmark,
            growth_proxy_symbol=growth_proxy,
            required_bars=required_bars,
            require_adjusted=require_adjusted,
        )
    return build_market_regime_read_model_from_evidence(source)


def build_market_regime_read_model_from_evidence(source: Mapping[str, Any]) -> dict[str, Any]:
    evidence = dict(source.get("evidence") or {})
    regime_summary = dict(source.get("regimeSummary") or {})
    data_quality = _build_data_quality(source)
    missing_families = list(source.get("missingDataFamilies") or [])
    blocked_surfaces = list(source.get("blockedProductSurfaces") or [])
    readiness = _readiness(source_status=str(source.get("status") or "failed_closed"), missing_families=missing_families, blocked_surfaces=blocked_surfaces)
    regime_label = _safe_regime_label(regime_summary.get("label"))
    status = _read_model_status(str(source.get("status") or "failed_closed"))
    payload = {
        "consumerSafe": True,
        "contractVersion": MARKET_REGIME_READ_MODEL_CONTRACT_VERSION,
        "status": status,
        "market": str(source.get("market") or "UNKNOWN"),
        "symbols": list(source.get("symbols") or []),
        "benchmarkSymbol": str(source.get("benchmarkSymbol") or DEFAULT_BENCHMARK_SYMBOL),
        "growthProxySymbol": str(source.get("growthProxySymbol") or DEFAULT_GROWTH_PROXY_SYMBOL),
        "regime": {
            "label": regime_label,
            "status": str(regime_summary.get("status") or status),
            "source": "deterministic_evidence_fields",
        },
        "regimeLabel": regime_label,
        "regimeStatus": str(regime_summary.get("status") or status),
        "productSummary": _product_summary(regime_label, evidence, readiness["label"]),
        "evidenceCards": _evidence_cards(source, data_quality),
        "symbolContext": _symbol_context(source),
        "dataQuality": data_quality,
        "readiness": readiness,
        "surfaceHints": _surface_hints(readiness=readiness, data_quality=data_quality),
        "sourceEvidenceContractVersion": str(
            source.get("contractVersion") or MARKET_REGIME_EVIDENCE_CONTRACT_VERSION
        ),
        "missingDataFamilies": missing_families,
        "blockedProductSurfaces": blocked_surfaces,
        "nextOperatorAction": str(source.get("nextOperatorAction") or readiness["nextOperatorAction"]),
        "noAdvice": True,
        "networkCallsEnabled": False,
        "mutationEnabled": False,
        "providerCallsEnabled": False,
    }
    return _sanitize(payload)


def _failed_closed_source(
    *,
    market: str,
    symbols: Sequence[str],
    benchmark_symbol: str,
    growth_proxy_symbol: str,
    required_bars: int,
    require_adjusted: bool,
) -> dict[str, Any]:
    return {
        "consumerSafe": True,
        "contractVersion": MARKET_REGIME_EVIDENCE_CONTRACT_VERSION,
        "status": "failed_closed",
        "market": market,
        "symbols": list(symbols),
        "benchmarkSymbol": benchmark_symbol,
        "growthProxySymbol": growth_proxy_symbol,
        "requiredBars": int(required_bars or DEFAULT_REQUIRED_BARS),
        "requireAdjusted": bool(require_adjusted),
        "missingDataFamilies": ["historical_ohlcv"],
        "blockedProductSurfaces": ["Scanner", "Market Overview", "Watchlist", "Research Radar"],
        "nextOperatorAction": "Provide readable local market regime evidence inputs, then rerun.",
        "evidence": {},
        "regimeSummary": {"label": "insufficient_data", "status": "failed_closed"},
        "symbolEvidence": {},
        "quoteSnapshotEvidence": {},
        "dataQuality": {
            "missingBars": {},
            "missingAdjustedData": [],
            "missingQuoteSnapshot": list(symbols),
            "staleOrUnknownFreshness": list(symbols),
            "failClosedReasons": ["source_unavailable"],
        },
        "networkCallsEnabled": False,
        "mutationEnabled": False,
        "providerCallsEnabled": False,
    }


def _read_model_status(source_status: str) -> str:
    if source_status == "ok":
        return "ok"
    if source_status == "partial":
        return "partial"
    return "failed_closed"


def _safe_regime_label(value: Any) -> str:
    label = str(value or "insufficient_data")
    return label if label in ALLOWED_REGIME_LABELS else "insufficient_data"


def _readiness(*, source_status: str, missing_families: Sequence[str], blocked_surfaces: Sequence[str]) -> dict[str, Any]:
    if source_status == "failed_closed":
        label = "failed_closed"
        status = "failed_closed"
        action = "Provide readable local evidence inputs, then rerun the read model."
    elif missing_families or blocked_surfaces:
        label = "blocked"
        status = "blocked"
        action = "Resolve missing local evidence families or blocked product surfaces, then rerun."
    elif source_status == "partial":
        label = "degraded"
        status = "partial"
        action = "Review degraded evidence coverage before exposing secondary surfaces."
    else:
        label = "product_ready"
        status = "ok"
        action = "Market regime read model is available from local evidence inputs."
    return {
        "label": label,
        "status": status,
        "missingDataFamilies": list(missing_families),
        "blockedProductSurfaces": list(blocked_surfaces),
        "nextOperatorAction": action,
    }


def _product_summary(regime_label: str, evidence: Mapping[str, Any], readiness_label: str) -> str:
    if readiness_label == "failed_closed":
        return "Market regime evidence is not available because local source inputs failed closed."
    if readiness_label == "blocked":
        return "Market regime evidence is blocked by missing local source families or product surface blockers."
    benchmark = dict(evidence.get("benchmarkTrend") or {})
    breadth = dict(evidence.get("breadthProxy") or {})
    growth = dict(evidence.get("growthRiskProxy") or {})
    if regime_label == "risk_off":
        return (
            "Risk-off evidence is currently dominant because the benchmark is below its 20-day moving average, "
            "20-day return is negative, and breadth is weak."
        )
    if regime_label == "risk_on_confirming":
        return (
            "Risk-on confirming evidence is currently present because the benchmark is above its 20-day moving average, "
            "20-day return is positive, and breadth is broad."
        )
    if regime_label == "risk_on_fragile":
        return "Risk-on fragile evidence is present with mixed confirmation across benchmark trend, breadth, and growth proxy fields."
    if regime_label == "mixed":
        parts = []
        if benchmark.get("closeVsMa20") in {"above", "below", "at"}:
            parts.append(f"benchmark is {benchmark.get('closeVsMa20')} its 20-day moving average")
        if growth.get("relativeReturn20d") is not None:
            parts.append("growth proxy relative return is available")
        if breadth.get("percentAboveMa20") is not None:
            parts.append("breadth evidence is available")
        detail = ", ".join(parts) if parts else "available evidence is not aligned"
        return f"Market regime evidence is mixed because {detail}."
    return "Market regime evidence is insufficient for a product-ready regime label."


def _evidence_cards(source: Mapping[str, Any], data_quality: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence = dict(source.get("evidence") or {})
    missing_families = set(source.get("missingDataFamilies") or [])
    blocked_surfaces = list(source.get("blockedProductSurfaces") or [])
    benchmark = dict(evidence.get("benchmarkTrend") or source.get("benchmarkEvidence") or {})
    growth = dict(evidence.get("growthRiskProxy") or {})
    breadth = dict(evidence.get("breadthProxy") or {})
    volatility = dict(evidence.get("volatilityProxy") or {})
    quote = dict(source.get("quoteSnapshotEvidence") or {})
    return [
        _benchmark_card(benchmark),
        _growth_card(growth),
        _breadth_card(breadth),
        _volatility_card(volatility),
        _quote_card(quote, missing_families),
        _data_quality_card(data_quality, missing_families, blocked_surfaces),
    ]


def _benchmark_card(benchmark: Mapping[str, Any]) -> dict[str, Any]:
    return20d = _number(benchmark.get("return20d"))
    close_vs_ma20 = str(benchmark.get("closeVsMa20") or "insufficient_data")
    if return20d is None or close_vs_ma20 == "insufficient_data":
        status, severity = "unavailable", "blocker"
        headline = "Benchmark trend evidence is unavailable."
        reasons = ["Benchmark trend requires local OHLCV coverage and moving-average fields."]
    elif return20d < 0 and close_vs_ma20 == "below":
        status, severity = "negative", "warning"
        headline = "Benchmark trend evidence is negative."
        reasons = ["Benchmark 20-day return is negative.", "Benchmark is below its 20-day moving average."]
    elif return20d > 0 and close_vs_ma20 == "above":
        status, severity = "positive", "info"
        headline = "Benchmark trend evidence is positive."
        reasons = ["Benchmark 20-day return is positive.", "Benchmark is above its 20-day moving average."]
    else:
        status, severity = "neutral", "watch"
        headline = "Benchmark trend evidence is mixed."
        reasons = ["Benchmark return and moving-average fields are not aligned."]
    return _card(
        card_id="benchmark_trend",
        title="Benchmark Trend",
        status=status,
        severity=severity,
        headline=headline,
        metrics=[
            {"label": "return20d", "value": return20d},
            {"label": "closeVsMa20", "value": close_vs_ma20},
            {"label": "closeVsMa50", "value": benchmark.get("closeVsMa50")},
        ],
        reasons=reasons,
        source_fields=[
            "evidence.benchmarkTrend.return20d",
            "evidence.benchmarkTrend.closeVsMa20",
            "evidence.benchmarkTrend.closeVsMa50",
        ],
    )


def _growth_card(growth: Mapping[str, Any]) -> dict[str, Any]:
    relative20 = _number(growth.get("relativeReturn20d"))
    if relative20 is None:
        status, severity = "unavailable", "blocker"
        headline = "Growth proxy evidence is unavailable."
        reasons = ["Growth proxy requires benchmark and proxy OHLCV coverage."]
    elif relative20 < 0:
        status, severity = "negative", "watch"
        headline = "Growth proxy evidence is negative."
        reasons = ["Growth proxy 20-day relative return is negative."]
    else:
        status, severity = "positive", "info"
        headline = "Growth proxy evidence is positive."
        reasons = ["Growth proxy 20-day relative return is non-negative."]
    return _card(
        card_id="growth_risk_proxy",
        title="Growth Risk Proxy",
        status=status,
        severity=severity,
        headline=headline,
        metrics=[
            {"label": "relativeReturn20d", "value": relative20},
            {"label": "relativeReturn60d", "value": growth.get("relativeReturn60d")},
        ],
        reasons=reasons,
        source_fields=[
            "evidence.growthRiskProxy.relativeReturn20d",
            "evidence.growthRiskProxy.relativeReturn60d",
        ],
    )


def _breadth_card(breadth: Mapping[str, Any]) -> dict[str, Any]:
    percent = _number(breadth.get("percentAboveMa20"))
    if percent is None:
        status, severity = "unavailable", "blocker"
        headline = "Breadth evidence is unavailable."
        reasons = ["Breadth requires local OHLCV coverage across the bounded universe."]
    elif percent <= 0.40:
        status, severity = "negative", "warning"
        headline = "Breadth evidence is weak."
        reasons = ["The percent of symbols above the 20-day moving average is at or below 40%."]
    elif percent >= 0.60:
        status, severity = "positive", "info"
        headline = "Breadth evidence is broad."
        reasons = ["The percent of symbols above the 20-day moving average is at or above 60%."]
    else:
        status, severity = "neutral", "watch"
        headline = "Breadth evidence is mixed."
        reasons = ["The percent of symbols above the 20-day moving average is between 40% and 60%."]
    return _card(
        card_id="breadth",
        title="Breadth",
        status=status,
        severity=severity,
        headline=headline,
        metrics=[
            {"label": "percentAboveMa20", "value": percent},
            {"label": "availableCount", "value": breadth.get("availableCount")},
            {"label": "missingCount", "value": breadth.get("missingCount")},
        ],
        reasons=reasons,
        source_fields=[
            "evidence.breadthProxy.percentAboveMa20",
            "evidence.breadthProxy.availableCount",
            "evidence.breadthProxy.missingCount",
        ],
    )


def _volatility_card(volatility: Mapping[str, Any]) -> dict[str, Any]:
    state = str(volatility.get("volatilityState") or "insufficient_data")
    if state == "elevated":
        status, severity = "negative", "warning"
        headline = "Volatility evidence is elevated."
        reasons = ["Realized 20-day volatility is above the normal band."]
    elif state in {"normal", "low"}:
        status, severity = "neutral", "info"
        headline = f"Volatility evidence is {state}."
        reasons = ["Realized 20-day volatility is within the low or normal band."]
    else:
        status, severity = "unavailable", "blocker"
        headline = "Volatility evidence is unavailable."
        reasons = ["Volatility requires enough benchmark close history."]
    return _card(
        card_id="volatility",
        title="Volatility",
        status=status,
        severity=severity,
        headline=headline,
        metrics=[
            {"label": "realizedVolatility20d", "value": volatility.get("realizedVolatility20d")},
            {"label": "volatilityState", "value": state},
        ],
        reasons=reasons,
        source_fields=[
            "evidence.volatilityProxy.realizedVolatility20d",
            "evidence.volatilityProxy.volatilityState",
        ],
    )


def _quote_card(quote: Mapping[str, Any], missing_families: set[str]) -> dict[str, Any]:
    availability = str(quote.get("availabilityState") or "missing")
    freshness = str(quote.get("freshnessState") or "unknown")
    missing_symbols = list(quote.get("missingSymbols") or [])
    stale_symbols = list(quote.get("staleSymbols") or [])
    if availability == "available" and freshness not in {"stale", "missing", "unknown"}:
        status, severity = "positive", "info"
        headline = "Quote snapshot evidence is available."
        reasons = ["Quote snapshot rows are available for the bounded universe."]
    elif availability == "not_requested":
        status, severity = "neutral", "watch"
        headline = "Quote snapshot evidence was not requested."
        reasons = ["Quote snapshot cache path was not supplied for this read model run."]
    else:
        status = "unavailable" if missing_symbols else "degraded"
        severity = "blocker" if "quote_snapshot" in missing_families else "warning"
        headline = "Quote snapshot evidence is incomplete."
        reasons = ["Quote snapshot rows are missing or stale for one or more bounded symbols."]
    return _card(
        card_id="quote_snapshot",
        title="Quote Snapshot",
        status=status,
        severity=severity,
        headline=headline,
        metrics=[
            {"label": "availabilityState", "value": availability},
            {"label": "freshnessState", "value": freshness},
            {"label": "missingSymbols", "value": missing_symbols},
            {"label": "staleSymbols", "value": stale_symbols},
        ],
        reasons=reasons,
        source_fields=[
            "quoteSnapshotEvidence.availabilityState",
            "quoteSnapshotEvidence.freshnessState",
            "quoteSnapshotEvidence.missingSymbols",
            "quoteSnapshotEvidence.staleSymbols",
        ],
    )


def _data_quality_card(
    data_quality: Mapping[str, Any],
    missing_families: set[str],
    blocked_surfaces: Sequence[str],
) -> dict[str, Any]:
    if missing_families or blocked_surfaces:
        status, severity = "degraded", "blocker"
        headline = "Data quality blocks at least one product surface."
        reasons = ["Missing local evidence families or product blockers are present."]
    else:
        status, severity = "positive", "info"
        headline = "Data quality is product-ready."
        reasons = ["No missing evidence families or product blockers are present."]
    return _card(
        card_id="data_quality",
        title="Data Quality",
        status=status,
        severity=severity,
        headline=headline,
        metrics=[
            {"label": "adjustedCoverageState", "value": data_quality.get("adjustedCoverageState")},
            {"label": "ohlcvCoverageState", "value": dict(data_quality.get("ohlcvCoverage") or {}).get("state")},
            {"label": "quoteSnapshotCoverageState", "value": dict(data_quality.get("quoteSnapshotCoverage") or {}).get("state")},
            {"label": "missingDataFamilies", "value": list(missing_families)},
        ],
        reasons=reasons,
        source_fields=[
            "dataQuality.missingBars",
            "dataQuality.missingAdjustedData",
            "missingDataFamilies",
            "blockedProductSurfaces",
        ],
    )


def _card(
    *,
    card_id: str,
    title: str,
    status: str,
    severity: str,
    headline: str,
    metrics: Sequence[Mapping[str, Any]],
    reasons: Sequence[str],
    source_fields: Sequence[str],
) -> dict[str, Any]:
    return {
        "id": card_id,
        "cardId": card_id,
        "title": title,
        "status": status,
        "severity": severity,
        "headline": headline,
        "metrics": [dict(item) for item in metrics],
        "reasons": list(reasons),
        "sourceFields": list(source_fields),
        "consumerSafe": True,
    }


def _build_data_quality(source: Mapping[str, Any]) -> dict[str, Any]:
    evidence = dict(source.get("evidence") or {})
    historical = dict(evidence.get("historicalOhlcvCoverage") or {})
    quote = dict(source.get("quoteSnapshotEvidence") or {})
    source_quality = dict(source.get("dataQuality") or {})
    symbols = list(source.get("symbols") or [])
    available_ohlcv = list(historical.get("availableSymbols") or [])
    missing_ohlcv = list(historical.get("missingSymbols") or [])
    ohlcv_state = "available" if symbols and len(available_ohlcv) == len(symbols) else "partial" if available_ohlcv else "missing"
    quote_state = str(quote.get("availabilityState") or "missing")
    if quote_state == "available":
        quote_coverage_state = "available"
    elif quote_state == "stale":
        quote_coverage_state = "stale"
    elif quote_state == "not_requested":
        quote_coverage_state = "not_requested"
    elif quote.get("availableSymbols"):
        quote_coverage_state = "partial"
    else:
        quote_coverage_state = "missing"
    return {
        "adjustedCoverageState": str(historical.get("adjustedCoverageState") or "missing"),
        "ohlcvCoverage": {
            "state": ohlcv_state,
            "requiredBars": historical.get("requiredBars"),
            "availableSymbols": available_ohlcv,
            "missingSymbols": missing_ohlcv,
            "missingBars": dict(source_quality.get("missingBars") or {}),
        },
        "quoteSnapshotCoverage": {
            "state": quote_coverage_state,
            "availabilityState": quote_state,
            "freshnessState": str(quote.get("freshnessState") or "unknown"),
            "availableSymbols": list(quote.get("availableSymbols") or []),
            "missingSymbols": list(quote.get("missingSymbols") or []),
            "staleSymbols": list(quote.get("staleSymbols") or []),
        },
        "missingDataFamilies": list(source.get("missingDataFamilies") or []),
        "blockedProductSurfaces": list(source.get("blockedProductSurfaces") or []),
        "nextOperatorAction": str(source.get("nextOperatorAction") or ""),
        "failClosedReasons": list(source_quality.get("failClosedReasons") or []),
    }


def _symbol_context(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    symbol_evidence = dict(source.get("symbolEvidence") or {})
    rows: list[dict[str, Any]] = []
    for symbol in list(source.get("symbols") or []):
        item = dict(symbol_evidence.get(symbol) or {})
        coverage = dict(item.get("coverage") or {})
        trend = dict(item.get("trend") or {})
        rows.append(
            {
                "symbol": symbol,
                "coverageState": str(coverage.get("state") or "missing"),
                "latestClose": trend.get("latestClose"),
                "adjustedClose": trend.get("adjustedClose"),
                "return20d": trend.get("return20d"),
                "closeVsMa20": trend.get("closeVsMa20"),
                "closeVsMa50": trend.get("closeVsMa50"),
                "missingBars": int(coverage.get("missingBars") or 0),
                "adjustedCoverageState": str(coverage.get("adjustedCoverageState") or "missing"),
            }
        )
    return rows


def _surface_hints(
    *,
    readiness: Mapping[str, Any],
    data_quality: Mapping[str, Any],
) -> list[dict[str, Any]]:
    status_hint = _surface_status_hint(readiness=readiness, data_quality=data_quality)
    return [
        {
            "surface": "market_overview",
            "surfaceName": "Market Overview",
            "usage": "regime_summary_and_top_evidence_cards",
            "statusHint": status_hint,
            "readOnly": True,
            "routeChangeImplied": False,
        },
        {
            "surface": "research_radar",
            "surfaceName": "Research Radar",
            "usage": "full_evidence_cards_and_data_quality",
            "statusHint": status_hint,
            "readOnly": True,
            "routeChangeImplied": False,
        },
        {
            "surface": "scanner",
            "surfaceName": "Scanner",
            "usage": "readiness_only",
            "statusHint": status_hint,
            "readOnly": True,
            "candidateGenerationEnabled": False,
        },
        {
            "surface": "watchlist",
            "surfaceName": "Watchlist",
            "usage": "regime_context_only",
            "statusHint": status_hint,
            "readOnly": True,
            "rankingEnabled": False,
        },
    ]


def _surface_status_hint(*, readiness: Mapping[str, Any], data_quality: Mapping[str, Any]) -> str:
    label = str(readiness.get("label") or "").strip()
    if label == "product_ready":
        return "evidence_available"
    if label == "degraded":
        return "evidence_degraded"
    if label == "blocked":
        missing = set(data_quality.get("missingDataFamilies") or [])
        if "quote_snapshot" in missing:
            return "quote_snapshot_missing"
        if "historical_ohlcv" in missing or "adjusted_prices" in missing:
            return "local_history_missing"
        return "evidence_blocked"
    if label == "failed_closed":
        return "evidence_failed_closed"
    return "evidence_unknown"


def _number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_symbols(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        symbol = _normalize_symbol(value)
        if symbol and symbol not in result:
            result.append(symbol)
    return result


def _normalize_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if not symbol:
        return ""
    if not all(ch.isalnum() or ch in {".", "-", "_"} for ch in symbol):
        return ""
    return symbol[:16]


def _sanitize(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


__all__ = [
    "MARKET_REGIME_READ_MODEL_CONTRACT_VERSION",
    "build_market_regime_read_model",
    "build_market_regime_read_model_from_evidence",
]
