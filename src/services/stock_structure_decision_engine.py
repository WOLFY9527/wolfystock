# -*- coding: utf-8 -*-
"""Pure stock structure decision engine.

The engine consumes caller-provided OHLCV bars and emits observation-only
research structure. It has no provider, cache, broker, scanner, or API runtime
dependency so future consumers can call it from stock pages or scanner rows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


STOCK_STRUCTURE_DECISION_SCHEMA_VERSION = "stock_structure_decision_engine_v1"
NO_ADVICE_DISCLOSURE = (
    "Observation-only research context; not personalized financial advice and "
    "not an instruction."
)

MIN_REQUIRED_BARS = 12
STRONG_EVIDENCE_BARS = 50
GOOD_EVIDENCE_BARS = 30
RECENT_RANGE_LOOKBACK = 20
SHORT_MA_WINDOW = 10
MID_MA_WINDOW = 20
LONG_MA_WINDOW = 50
ATR_WINDOW = 14
BREAKOUT_BUFFER_PCT = 0.01
BREAKOUT_VOLUME_RATIO = 1.35
EXTENDED_MA_DISTANCE_PCT = 0.12
EXTENDED_ATR_MULTIPLE = 4.0
CONSOLIDATION_RANGE_RATIO = 0.65
LOW_VOLATILITY_PCT = 0.025
DISTRIBUTION_VOLUME_RATIO = 1.2
BREAKDOWN_BUFFER_PCT = 0.01

STRUCTURE_STATES = {
    "uptrend",
    "breakout",
    "pullback",
    "consolidation",
    "extended",
    "distribution",
    "breakdown",
    "mixed",
    "lowConfidence",
}


def build_stock_structure_decision(
    ohlcv: Sequence[Any] | None,
    *,
    benchmark_ohlcv: Sequence[Any] | None = None,
    sector_theme: str | None = None,
    market_regime: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic stock-structure observation from normalized OHLCV."""

    bars, quality = _normalize_bars(ohlcv)
    benchmark_bars, benchmark_quality = _normalize_bars(benchmark_ohlcv)
    if len(bars) < MIN_REQUIRED_BARS or quality["validRatio"] < 0.8:
        return _low_confidence_result(bars, quality, benchmark_quality)

    metrics = _calculate_metrics(bars, benchmark_bars)
    component_scores = _component_scores(metrics, quality, benchmark_quality)
    state = _structure_state(metrics, component_scores)
    confidence = _confidence(state, component_scores, quality, metrics)

    return {
        "schemaVersion": STOCK_STRUCTURE_DECISION_SCHEMA_VERSION,
        "structureState": state,
        "confidence": confidence,
        "componentScores": component_scores,
        "explanation": _explanation(state, metrics, component_scores),
        "researchNotes": _research_notes(
            state,
            metrics,
            component_scores,
            quality,
            benchmark_quality,
            sector_theme=sector_theme,
            market_regime=market_regime,
        ),
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
    }


def _low_confidence_result(
    bars: Sequence[dict[str, Any]],
    quality: Mapping[str, Any],
    benchmark_quality: Mapping[str, Any],
) -> dict[str, Any]:
    component_scores = {
        "trend": 0,
        "relativeStrength": 50 if benchmark_quality["inputCount"] else 0,
        "volumePressure": 0,
        "volatilityCompression": 0,
        "breakoutQuality": 0,
        "pullbackHealth": 0,
        "riskExtension": 0,
        "evidenceQuality": _evidence_quality_score(len(bars), float(quality["validRatio"])),
    }
    reasons = []
    if len(bars) < MIN_REQUIRED_BARS:
        reasons.append("More complete OHLCV history is needed before structure can be described.")
    if quality["invalidCount"]:
        reasons.append("Some OHLCV rows are incomplete or non-numeric.")
    if not reasons:
        reasons.append("Current OHLCV evidence is too limited for a structure description.")

    return {
        "schemaVersion": STOCK_STRUCTURE_DECISION_SCHEMA_VERSION,
        "structureState": "lowConfidence",
        "confidence": "low",
        "componentScores": component_scores,
        "explanation": {
            "whyThisStructure": "The available OHLCV evidence is insufficient for a stable structure description.",
            "whatConfirmsIt": ["More complete, internally consistent OHLCV rows would improve evidence quality."],
            "whatInvalidatesIt": ["A longer valid OHLCV sequence may reveal a clearer structure."],
            "keyLevels": [],
        },
        "researchNotes": {
            "watchNext": ["Observe whether incoming OHLCV rows improve coverage and continuity."],
            "needsMoreEvidence": reasons,
            "riskFlags": ["Low evidence quality limits structure confidence."],
        },
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
    }


def _component_scores(
    metrics: Mapping[str, Any],
    quality: Mapping[str, Any],
    benchmark_quality: Mapping[str, Any],
) -> dict[str, int]:
    trend = _trend_score(metrics)
    relative_strength = _relative_strength_score(metrics, benchmark_quality)
    volume_pressure = _volume_pressure_score(metrics)
    volatility_compression = _volatility_compression_score(metrics)
    breakout_quality = _breakout_quality_score(metrics, trend, volume_pressure)
    pullback_health = _pullback_health_score(metrics, trend, volume_pressure)
    risk_extension = _risk_extension_score(metrics)
    evidence_quality = _evidence_quality_score(int(metrics["barCount"]), float(quality["validRatio"]))
    return {
        "trend": trend,
        "relativeStrength": relative_strength,
        "volumePressure": volume_pressure,
        "volatilityCompression": volatility_compression,
        "breakoutQuality": breakout_quality,
        "pullbackHealth": pullback_health,
        "riskExtension": risk_extension,
        "evidenceQuality": evidence_quality,
    }


def _structure_state(metrics: Mapping[str, Any], scores: Mapping[str, int]) -> str:
    evidence_quality = int(scores["evidenceQuality"])
    if evidence_quality < 40:
        return "lowConfidence"

    distribution_score = _distribution_score(metrics, scores)
    breakdown_score = _breakdown_score(metrics, scores)
    if breakdown_score >= 70:
        return "breakdown"
    distribution_pressure_present = int(metrics["downHeavyCount"]) >= 2 or int(scores["volumePressure"]) <= 35
    if distribution_score >= 68 and distribution_pressure_present:
        return "distribution"

    extended_by_distance = float(metrics["distanceFromMidMaPct"]) >= EXTENDED_MA_DISTANCE_PCT
    extended_by_atr = (
        float(metrics["atrMultipleFromMidMa"]) >= EXTENDED_ATR_MULTIPLE
        and float(metrics["distanceFromMidMaPct"]) >= 0.09
    )
    if int(scores["riskExtension"]) >= 75 and (extended_by_distance or extended_by_atr):
        return "extended"

    if int(scores["breakoutQuality"]) >= 70 and bool(metrics["closeAboveRecentRange"]):
        return "breakout"
    if int(scores["volatilityCompression"]) >= 70 and int(scores["breakoutQuality"]) < 60:
        return "consolidation"
    if int(scores["pullbackHealth"]) >= 68 and int(scores["trend"]) >= 58:
        return "pullback"
    if int(scores["trend"]) >= 68:
        return "uptrend"
    if evidence_quality < 60:
        return "lowConfidence"
    return "mixed"


def _confidence(
    state: str,
    scores: Mapping[str, int],
    quality: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> str:
    evidence_quality = int(scores["evidenceQuality"])
    if state == "lowConfidence" or evidence_quality < 45 or quality["invalidCount"]:
        return "low"
    if state == "breakout":
        if (
            evidence_quality >= 85
            and int(scores["trend"]) >= 65
            and int(scores["breakoutQuality"]) >= 75
            and int(scores["volumePressure"]) >= 60
        ):
            return "high"
        return "medium"
    if state in {"extended", "distribution", "breakdown"}:
        if evidence_quality >= 80 and _dominant_state_score(state, scores, metrics) >= 80:
            return "high"
        return "medium"
    if evidence_quality >= 80 and _dominant_state_score(state, scores, metrics) >= 72:
        return "high"
    if evidence_quality >= 55:
        return "medium"
    return "low"


def _dominant_state_score(state: str, scores: Mapping[str, int], metrics: Mapping[str, Any]) -> int:
    if state == "breakout":
        return int(scores["breakoutQuality"])
    if state == "extended":
        return int(scores["riskExtension"])
    if state == "distribution":
        return _distribution_score(metrics, scores)
    if state == "breakdown":
        return _breakdown_score(metrics, scores)
    if state == "consolidation":
        return int(scores["volatilityCompression"])
    if state == "pullback":
        return int(scores["pullbackHealth"])
    if state == "uptrend":
        return int(scores["trend"])
    return max(int(value) for value in scores.values())


def _explanation(state: str, metrics: Mapping[str, Any], scores: Mapping[str, int]) -> dict[str, Any]:
    state_reason = {
        "uptrend": "Price is above key moving-average references and the recent slope is rising.",
        "breakout": "Price closed above the recent observed range with expanded volume and positive trend evidence.",
        "pullback": "Price has eased from the recent high while staying near moving-average references with contained volume pressure.",
        "consolidation": "Recent range and true-range behavior have narrowed while breakout evidence remains limited.",
        "extended": "Price is stretched above moving-average and true-range references.",
        "distribution": "Recent declines show heavier volume pressure and repeated failure to extend observed highs.",
        "breakdown": "Price moved below the recent observed range with weak volume-pressure evidence.",
        "mixed": "Component evidence is split, so no single structure dominates.",
        "lowConfidence": "Available OHLCV evidence is insufficient for a stable structure description.",
    }
    confirms = _confirmation_notes(state, metrics, scores)
    invalidates = _invalidation_notes(state, metrics)
    return {
        "whyThisStructure": state_reason[state],
        "whatConfirmsIt": confirms,
        "whatInvalidatesIt": invalidates,
        "keyLevels": _key_levels(metrics),
    }


def _confirmation_notes(state: str, metrics: Mapping[str, Any], scores: Mapping[str, int]) -> list[str]:
    notes = []
    if int(scores["trend"]) >= 65:
        notes.append("Trend score is supported by price location and moving-average slope.")
    if int(scores["breakoutQuality"]) >= 70:
        notes.append("Breakout quality is supported by a close above the recent range and stronger volume.")
    if int(scores["volatilityCompression"]) >= 70:
        notes.append("Volatility compression is supported by a narrower recent range.")
    if int(scores["relativeStrength"]) >= 65:
        notes.append("Relative strength is positive versus the benchmark window.")
    if int(scores["volumePressure"]) <= 35:
        notes.append("Volume pressure is weak because heavier volume appears on declining sessions.")
    if state == "extended":
        notes.append("Risk extension is elevated versus moving-average and true-range references.")
    if not notes:
        notes.append("The structure is based on the strongest available deterministic components.")
    return notes


def _invalidation_notes(state: str, metrics: Mapping[str, Any]) -> list[str]:
    notes = []
    if state in {"breakout", "uptrend", "extended"}:
        notes.append("A close back inside the recent observed range would weaken the current structure description.")
        notes.append("A flattening moving-average slope with weaker volume evidence would reduce confidence.")
    elif state == "consolidation":
        notes.append("A decisive close outside the recent observed range with expanded volume would change the structure description.")
    elif state in {"distribution", "breakdown"}:
        notes.append("Stabilization back inside the recent range with improving volume pressure would change the structure description.")
    elif state == "pullback":
        notes.append("A move below the moving-average reference with rising downside volume would weaken pullback health.")
    else:
        notes.append("More complete OHLCV evidence may change the structure description.")
    if metrics.get("benchmarkReturnPct") is None:
        notes.append("Benchmark evidence would clarify relative-strength confirmation.")
    return notes


def _key_levels(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    levels = []
    recent_high = metrics.get("recentRangeHigh")
    recent_low = metrics.get("recentRangeLow")
    mid_ma = metrics.get("midMa")
    last_close = metrics.get("lastClose")
    atr = metrics.get("atr")
    if recent_high is not None:
        levels.append(
            {
                "kind": "recentRangeHigh",
                "value": _round(float(recent_high)),
                "description": "Upper observation from recent highs.",
            }
        )
    if recent_low is not None:
        levels.append(
            {
                "kind": "recentRangeLow",
                "value": _round(float(recent_low)),
                "description": "Lower observation from recent lows.",
            }
        )
    if mid_ma is not None:
        levels.append(
            {
                "kind": "movingAverageReference",
                "value": _round(float(mid_ma)),
                "description": "Middle moving-average observation.",
            }
        )
    if last_close is not None and atr is not None:
        levels.append(
            {
                "kind": "trueRangeBand",
                "value": _round(float(last_close) - float(atr)),
                "upperValue": _round(float(last_close) + float(atr)),
                "description": "One average true-range observation around the latest close.",
            }
        )
    return levels


def _research_notes(
    state: str,
    metrics: Mapping[str, Any],
    scores: Mapping[str, int],
    quality: Mapping[str, Any],
    benchmark_quality: Mapping[str, Any],
    *,
    sector_theme: str | None,
    market_regime: Mapping[str, Any] | None,
) -> dict[str, list[str]]:
    watch_next = []
    needs_more = []
    risk_flags = []

    if state == "breakout":
        watch_next.append("Observe whether closes remain outside the prior range with continued volume confirmation.")
    elif state == "consolidation":
        watch_next.append("Observe whether range compression persists or expands into a new structure.")
    elif state == "extended":
        watch_next.append("Observe whether distance from moving-average references normalizes.")
    elif state in {"distribution", "breakdown"}:
        watch_next.append("Observe whether downside volume pressure fades or remains persistent.")
    else:
        watch_next.append("Observe whether the next OHLCV bars increase component agreement.")

    if sector_theme:
        watch_next.append(f"Observe whether sector/theme context remains aligned: {_safe_label(sector_theme)}.")
    if market_regime:
        regime_label = _safe_label(market_regime.get("regime") or market_regime.get("riskAppetite") or "")
        if regime_label:
            watch_next.append(f"Observe whether market-regime context remains consistent: {regime_label}.")

    if not benchmark_quality["inputCount"]:
        needs_more.append("Benchmark OHLCV would improve relative-strength evidence.")
    if int(quality["validCount"]) < STRONG_EVIDENCE_BARS:
        needs_more.append("Longer OHLCV history would improve trend and compression evidence.")
    if int(scores["evidenceQuality"]) < 80:
        needs_more.append("More complete OHLCV rows would improve evidence quality.")

    if int(scores["riskExtension"]) >= 70:
        risk_flags.append("Extension risk: latest close is stretched versus moving-average or true-range observations.")
    if int(scores["volumePressure"]) <= 35:
        risk_flags.append("Distribution pressure: heavier volume appears on declining sessions.")
    if state == "breakdown":
        risk_flags.append("Breakdown risk: latest close is below the recent observed range.")
    if not risk_flags:
        risk_flags.append("No dominant risk flag from deterministic OHLCV components.")

    return {
        "watchNext": _dedupe(watch_next),
        "needsMoreEvidence": _dedupe(needs_more),
        "riskFlags": _dedupe(risk_flags),
    }


def _calculate_metrics(
    bars: Sequence[Mapping[str, Any]],
    benchmark_bars: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    closes = [float(bar["close"]) for bar in bars]
    highs = [float(bar["high"]) for bar in bars]
    lows = [float(bar["low"]) for bar in bars]
    volumes = [float(bar["volume"]) for bar in bars]
    last_close = closes[-1]
    last_volume = volumes[-1]
    short_ma = _mean(closes[-SHORT_MA_WINDOW:])
    mid_ma = _mean(closes[-min(MID_MA_WINDOW, len(closes)):])
    long_ma = _mean(closes[-min(LONG_MA_WINDOW, len(closes)):])
    short_slope = _window_slope(closes, SHORT_MA_WINDOW)
    mid_slope = _window_slope(closes, min(MID_MA_WINDOW, len(closes) // 2))
    recent_lookback = min(RECENT_RANGE_LOOKBACK, len(bars) - 1)
    recent_high = max(highs[-recent_lookback - 1 : -1])
    recent_low = min(lows[-recent_lookback - 1 : -1])
    recent_range_pct = _safe_div(recent_high - recent_low, last_close)
    previous_volume_mean = _mean(volumes[-recent_lookback - 1 : -1])
    volume_ratio = _safe_div(last_volume, previous_volume_mean, default=1.0)
    true_ranges = _true_ranges(highs, lows, closes)
    atr = _mean(true_ranges[-min(ATR_WINDOW, len(true_ranges)):])
    atr_pct = _safe_div(atr, last_close)
    distance_mid_ma_pct = _safe_div(last_close - mid_ma, mid_ma)
    atr_multiple = _safe_div(last_close - mid_ma, atr, default=0.0)
    stock_return = _return_pct(closes)
    benchmark_return = _return_pct([float(bar["close"]) for bar in benchmark_bars]) if benchmark_bars else None
    relative_return = stock_return - benchmark_return if benchmark_return is not None else None
    down_heavy_count, up_heavy_count = _heavy_volume_session_counts(closes, volumes)
    recent_failed_highs = _failed_high_count(highs, closes)
    recent_down_count = sum(1 for current, previous in zip(closes[-10:], closes[-11:-1]) if current < previous)
    recent_up_count = sum(1 for current, previous in zip(closes[-10:], closes[-11:-1]) if current > previous)
    recent_range_avg = _average_bar_range_pct(highs[-10:], lows[-10:], closes[-10:])
    prior_range_avg = _average_bar_range_pct(highs[-25:-10], lows[-25:-10], closes[-25:-10])
    pullback_from_high_pct = _safe_div(recent_high - last_close, recent_high)
    close_below_recent_low = last_close < recent_low * (1 - BREAKDOWN_BUFFER_PCT)
    close_above_recent_high = last_close > recent_high * (1 + BREAKOUT_BUFFER_PCT)

    return {
        "barCount": len(bars),
        "lastClose": last_close,
        "lastVolume": last_volume,
        "shortMa": short_ma,
        "midMa": mid_ma,
        "longMa": long_ma,
        "shortSlopePct": short_slope,
        "midSlopePct": mid_slope,
        "recentRangeHigh": recent_high,
        "recentRangeLow": recent_low,
        "recentRangePct": recent_range_pct,
        "volumeRatio": volume_ratio,
        "atr": atr,
        "atrPct": atr_pct,
        "distanceFromMidMaPct": distance_mid_ma_pct,
        "atrMultipleFromMidMa": atr_multiple,
        "stockReturnPct": stock_return,
        "benchmarkReturnPct": benchmark_return,
        "relativeReturnPct": relative_return,
        "downHeavyCount": down_heavy_count,
        "upHeavyCount": up_heavy_count,
        "recentFailedHighCount": recent_failed_highs,
        "recentDownCount": recent_down_count,
        "recentUpCount": recent_up_count,
        "recentRangeAvgPct": recent_range_avg,
        "priorRangeAvgPct": prior_range_avg,
        "pullbackFromHighPct": pullback_from_high_pct,
        "closeBelowRecentRange": close_below_recent_low,
        "closeAboveRecentRange": close_above_recent_high,
    }


def _trend_score(metrics: Mapping[str, Any]) -> int:
    score = 45.0
    last_close = float(metrics["lastClose"])
    short_ma = float(metrics["shortMa"])
    mid_ma = float(metrics["midMa"])
    long_ma = float(metrics["longMa"])
    if last_close > mid_ma:
        score += 15
    if last_close > long_ma:
        score += 8
    if short_ma > mid_ma:
        score += 10
    if mid_ma >= long_ma:
        score += 8
    score += _scaled(float(metrics["shortSlopePct"]), positive=0.05, points=10)
    score += _scaled(float(metrics["midSlopePct"]), positive=0.04, points=8)
    if float(metrics["stockReturnPct"]) > 0:
        score += min(float(metrics["stockReturnPct"]) * 40, 8)
    return _clamp_score(score)


def _relative_strength_score(metrics: Mapping[str, Any], benchmark_quality: Mapping[str, Any]) -> int:
    if not benchmark_quality["inputCount"] or metrics["relativeReturnPct"] is None:
        return 50
    relative_return = float(metrics["relativeReturnPct"])
    return _clamp_score(50 + relative_return * 110)


def _volume_pressure_score(metrics: Mapping[str, Any]) -> int:
    up_heavy = int(metrics["upHeavyCount"])
    down_heavy = int(metrics["downHeavyCount"])
    score = 50.0
    score += up_heavy * 8
    score -= down_heavy * 9
    if bool(metrics["closeAboveRecentRange"]) and float(metrics["volumeRatio"]) >= BREAKOUT_VOLUME_RATIO:
        score += 18
    if bool(metrics["closeBelowRecentRange"]) and float(metrics["volumeRatio"]) >= DISTRIBUTION_VOLUME_RATIO:
        score -= 18
    if int(metrics["recentDownCount"]) > int(metrics["recentUpCount"]) + 2:
        score -= 10
    return _clamp_score(score)


def _volatility_compression_score(metrics: Mapping[str, Any]) -> int:
    recent = float(metrics["recentRangeAvgPct"])
    prior = float(metrics["priorRangeAvgPct"])
    score = 35.0
    if prior > 0 and recent <= prior * CONSOLIDATION_RANGE_RATIO:
        score += 35
    elif prior > 0 and recent <= prior * 0.8:
        score += 20
    if recent <= LOW_VOLATILITY_PCT:
        score += 20
    if float(metrics["recentRangePct"]) <= 0.06:
        score += 10
    if bool(metrics["closeAboveRecentRange"]) or bool(metrics["closeBelowRecentRange"]):
        score -= 20
    return _clamp_score(score)


def _breakout_quality_score(metrics: Mapping[str, Any], trend_score: int, volume_pressure_score: int) -> int:
    score = 30.0
    if bool(metrics["closeAboveRecentRange"]):
        score += 35
    if float(metrics["volumeRatio"]) >= BREAKOUT_VOLUME_RATIO:
        score += 20
    elif float(metrics["volumeRatio"]) >= 1.1:
        score += 10
    if trend_score >= 65:
        score += 10
    if volume_pressure_score >= 60:
        score += 8
    if float(metrics["distanceFromMidMaPct"]) >= EXTENDED_MA_DISTANCE_PCT:
        score -= 10
    return _clamp_score(score)


def _pullback_health_score(metrics: Mapping[str, Any], trend_score: int, volume_pressure_score: int) -> int:
    pullback = float(metrics["pullbackFromHighPct"])
    distance = abs(float(metrics["distanceFromMidMaPct"]))
    score = 30.0
    if trend_score >= 60:
        score += 25
    if 0.015 <= pullback <= 0.09:
        score += 22
    if distance <= 0.04:
        score += 15
    if volume_pressure_score >= 45:
        score += 8
    if bool(metrics["closeBelowRecentRange"]):
        score -= 25
    return _clamp_score(score)


def _risk_extension_score(metrics: Mapping[str, Any]) -> int:
    distance = max(0.0, float(metrics["distanceFromMidMaPct"]))
    atr_multiple = max(0.0, float(metrics["atrMultipleFromMidMa"]))
    score = 20.0
    if distance >= EXTENDED_MA_DISTANCE_PCT:
        score += 45
    elif distance >= 0.08:
        score += 25
    if atr_multiple >= EXTENDED_ATR_MULTIPLE:
        score += 30
    elif atr_multiple >= 2.5:
        score += 15
    if bool(metrics["closeAboveRecentRange"]) and float(metrics["volumeRatio"]) >= BREAKOUT_VOLUME_RATIO:
        score += 5
    return _clamp_score(score)


def _evidence_quality_score(bar_count: int, valid_ratio: float) -> int:
    if bar_count >= STRONG_EVIDENCE_BARS:
        length_score = 100
    elif bar_count >= GOOD_EVIDENCE_BARS:
        length_score = 82
    elif bar_count >= 20:
        length_score = 66
    elif bar_count >= MIN_REQUIRED_BARS:
        length_score = 52
    else:
        length_score = 20
    return _clamp_score(length_score * valid_ratio)


def _distribution_score(metrics: Mapping[str, Any], scores: Mapping[str, int]) -> int:
    score = 20.0
    score += int(metrics["downHeavyCount"]) * 14
    score += int(metrics["recentFailedHighCount"]) * 8
    if int(metrics["recentDownCount"]) > int(metrics["recentUpCount"]) + 2:
        score += 12
    if int(scores["volumePressure"]) <= 35:
        score += 20
    if bool(metrics["closeBelowRecentRange"]):
        score += 10
    return _clamp_score(score)


def _breakdown_score(metrics: Mapping[str, Any], scores: Mapping[str, int]) -> int:
    score = 20.0
    if bool(metrics["closeBelowRecentRange"]):
        score += 45
    if int(scores["volumePressure"]) <= 35:
        score += 20
    if int(scores["trend"]) <= 40:
        score += 10
    return _clamp_score(score)


def _normalize_bars(ohlcv: Sequence[Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    input_count = len(ohlcv or [])
    bars: list[dict[str, Any]] = []
    invalid_count = 0
    for index, raw in enumerate(ohlcv or []):
        normalized = _normalize_bar(raw, index)
        if normalized is None:
            invalid_count += 1
            continue
        bars.append(normalized)
    valid_ratio = _safe_div(len(bars), input_count, default=0.0) if input_count else 0.0
    return bars, {
        "inputCount": input_count,
        "validCount": len(bars),
        "invalidCount": invalid_count,
        "validRatio": valid_ratio,
    }


def _normalize_bar(raw: Any, index: int) -> dict[str, Any] | None:
    open_value = _to_float(_value(raw, "open", "Open", "o"))
    high_value = _to_float(_value(raw, "high", "High", "h"))
    low_value = _to_float(_value(raw, "low", "Low", "l"))
    close_value = _to_float(_value(raw, "close", "Close", "c"))
    volume_value = _to_float(_value(raw, "volume", "Volume", "v"))
    if None in (open_value, high_value, low_value, close_value, volume_value):
        return None
    if min(open_value, high_value, low_value, close_value) <= 0 or volume_value < 0:
        return None
    if high_value < max(open_value, close_value) or low_value > min(open_value, close_value):
        return None
    return {
        "index": index,
        "date": _text(_value(raw, "date", "datetime", "timestamp", "time")),
        "open": open_value,
        "high": high_value,
        "low": low_value,
        "close": close_value,
        "volume": volume_value,
    }


def _heavy_volume_session_counts(closes: Sequence[float], volumes: Sequence[float]) -> tuple[int, int]:
    down_heavy = 0
    up_heavy = 0
    start = max(1, len(closes) - 10)
    for index in range(start, len(closes)):
        local_mean = _mean(volumes[max(0, index - 10) : index])
        if not local_mean:
            continue
        is_heavy = volumes[index] >= local_mean * DISTRIBUTION_VOLUME_RATIO
        if not is_heavy:
            continue
        if closes[index] < closes[index - 1]:
            down_heavy += 1
        elif closes[index] > closes[index - 1]:
            up_heavy += 1
    return down_heavy, up_heavy


def _failed_high_count(highs: Sequence[float], closes: Sequence[float]) -> int:
    if len(highs) < 8:
        return 0
    prior_high = max(highs[:-6])
    failed = 0
    for high, close in zip(highs[-6:], closes[-6:]):
        if high <= prior_high * 1.003 and close < prior_high:
            failed += 1
    return failed


def _true_ranges(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]) -> list[float]:
    ranges = []
    for index, high in enumerate(highs):
        low = lows[index]
        previous_close = closes[index - 1] if index > 0 else closes[index]
        ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return ranges


def _average_bar_range_pct(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]) -> float:
    if not highs or not lows or not closes:
        return 0.0
    values = [_safe_div(high - low, close) for high, low, close in zip(highs, lows, closes)]
    return _mean(values)


def _window_slope(values: Sequence[float], window: int) -> float:
    if window <= 1 or len(values) < window * 2:
        compare = min(max(2, window // 2), len(values) // 2)
        if compare <= 1:
            return 0.0
        current = _mean(values[-compare:])
        previous = _mean(values[-compare * 2 : -compare])
        return _safe_div(current - previous, previous)
    current = _mean(values[-window:])
    previous = _mean(values[-window * 2 : -window])
    return _safe_div(current - previous, previous)


def _return_pct(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    return _safe_div(values[-1] - values[0], values[0])


def _value(raw: Any, *keys: str) -> Any:
    if isinstance(raw, Mapping):
        for key in keys:
            if key in raw:
                return raw[key]
        return None
    for key in keys:
        if hasattr(raw, key):
            return getattr(raw, key)
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in {float("inf"), float("-inf")}:
        return None
    return result


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_label(value: Any) -> str:
    text = _text(value)
    allowed = []
    for char in text:
        if char.isalnum() or char in {" ", "-", "_", "/", ":", "."}:
            allowed.append(char)
    return "".join(allowed).strip()[:80]


def _dedupe(values: Sequence[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _mean(values: Sequence[float]) -> float:
    usable = [float(value) for value in values if value is not None]
    if not usable:
        return 0.0
    return sum(usable) / len(usable)


def _safe_div(numerator: float, denominator: float, *, default: float = 0.0) -> float:
    if denominator in (0, 0.0):
        return default
    return numerator / denominator


def _scaled(value: float, *, positive: float, points: float) -> float:
    if value <= 0:
        return max(value / positive * points, -points)
    return min(value / positive * points, points)


def _clamp_score(value: float) -> int:
    return int(round(max(0.0, min(100.0, value))))


def _round(value: float) -> float:
    return round(value, 4)


__all__ = [
    "NO_ADVICE_DISCLOSURE",
    "STOCK_STRUCTURE_DECISION_SCHEMA_VERSION",
    "STRUCTURE_STATES",
    "build_stock_structure_decision",
]
