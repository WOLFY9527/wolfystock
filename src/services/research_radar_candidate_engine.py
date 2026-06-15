# -*- coding: utf-8 -*-
"""Pure deterministic Research Radar candidate queue engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass, replace
from typing import Any, Iterable, Mapping, Sequence


RESEARCH_RADAR_CANDIDATE_ENGINE_SCHEMA_VERSION = "research_radar_candidate_engine_v1"
NO_ADVICE_DISCLOSURE = "Research-only queue entry; verify evidence gaps before further review."

_DRIVER_KEYS = (
    "relativeStrength",
    "volumeExpansion",
    "trendStructure",
    "themeAlignment",
    "regimeFit",
    "eventCatalyst",
    "liquidityTradability",
    "evidenceQuality",
)
_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
_QUALITY_LABEL_SCORES = {
    "complete": 86,
    "confirmed": 82,
    "available": 76,
    "sufficient": 72,
    "deterministic": 72,
    "partial": 54,
    "mixed": 50,
    "needs_confirmation": 46,
    "proxy_observation": 42,
    "degraded": 38,
    "missing": 18,
    "insufficient": 18,
    "unavailable": 14,
    "blocked": 10,
}
_TREND_LABEL_SCORES = {
    "breakout": 86,
    "breakout_watch": 82,
    "confirmed_uptrend": 80,
    "uptrend": 74,
    "strength_continuation": 74,
    "pullback_near_support": 66,
    "constructive_pullback": 64,
    "range": 45,
    "mixed": 45,
    "volatile": 38,
    "downtrend": 24,
    "weak": 24,
}


@dataclass(frozen=True)
class _ScoredCandidate:
    ticker: str
    priority: str
    weighted_score: float
    driver_scores: dict[str, int]
    research_bias: str
    risk_flags: list[str]
    explanation: dict[str, list[str]]
    evidence_gaps: list[str]
    themes: list[str]
    duplicate_evidence_merged: int = 0


def build_research_radar_candidate_queue(
    candidates: Sequence[Mapping[str, Any] | Any] | None,
    *,
    market_regime_context: Mapping[str, Any] | Any | None = None,
    stock_structure_context: Mapping[str, Any] | Any | None = None,
    theme_leadership_context: Mapping[str, Any] | Any | None = None,
    evidence_quality_metadata: Mapping[str, Any] | Any | None = None,
) -> dict[str, Any]:
    """Build a deterministic, research-only queue from caller-provided inputs."""

    market_context = _mapping(market_regime_context)
    structure_by_symbol = _symbol_context_map(stock_structure_context)
    evidence_by_symbol = _symbol_context_map(evidence_quality_metadata)
    global_evidence = _mapping(evidence_quality_metadata)
    theme_context = _theme_context(theme_leadership_context)

    raw_scored = [
        _score_candidate(
            candidate,
            market_context=market_context,
            structure_context=structure_by_symbol.get(_symbol_from(candidate), {}),
            theme_context=theme_context,
            evidence_context=evidence_by_symbol.get(_symbol_from(candidate), global_evidence),
        )
        for candidate in candidates or []
    ]
    scored, duplicate_evidence_merged = _dedupe_scored_candidates(raw_scored)
    scored.sort(key=_sort_key)
    scored = _apply_queue_diversity(scored)

    research_queue = [_queue_item(item) for item in scored]
    summary = _summary(
        scored,
        market_context=market_context,
        theme_context=theme_context,
        duplicate_evidence_merged=duplicate_evidence_merged,
    )

    return {
        "schemaVersion": RESEARCH_RADAR_CANDIDATE_ENGINE_SCHEMA_VERSION,
        "researchQueue": research_queue,
        "summary": summary,
    }


def _score_candidate(
    candidate_value: Mapping[str, Any] | Any,
    *,
    market_context: Mapping[str, Any],
    structure_context: Mapping[str, Any],
    theme_context: Mapping[str, Any],
    evidence_context: Mapping[str, Any],
) -> _ScoredCandidate:
    candidate = _mapping(candidate_value)
    ticker = _symbol_from(candidate)
    merged = {**candidate, **{k: v for k, v in structure_context.items() if k not in candidate}}
    themes = _themes(merged)
    evidence_payload = _merged_evidence_payload(merged, evidence_context)

    driver_scores = {
        "relativeStrength": _score_percent(_first(merged, ("relativeStrength", "relative_strength", "rsRank", "rs_rank", "_relative_strength_pct"))),
        "volumeExpansion": _score_volume_expansion(
            _first(merged, ("volumeExpansion", "volume_expansion", "volumeExpansion20", "volume_expansion_20", "volumeRatio", "volume_ratio"))
        ),
        "trendStructure": _score_trend_structure(merged),
        "themeAlignment": _score_theme_alignment(themes, theme_context),
        "eventCatalyst": _score_event_catalyst(
            _first(merged, ("eventCatalyst", "event_catalyst", "newsCatalyst", "news_catalyst", "catalyst", "events"))
        ),
        "liquidityTradability": _score_liquidity(
            _first(merged, ("avgDollarVolume", "avg_dollar_volume", "avgAmount20", "avg_amount_20", "amount", "turnover"))
        ),
        "evidenceQuality": _score_evidence_quality(evidence_payload),
    }
    driver_scores["regimeFit"] = _score_regime_fit(themes, market_context, merged, driver_scores)
    risk_flags = _risk_flags(merged, driver_scores, evidence_payload, themes, market_context)
    evidence_gaps = _evidence_gaps(evidence_payload, driver_scores)
    aligned_drivers = sum(
        1
        for key, score in driver_scores.items()
        if key not in {"regimeFit", "evidenceQuality"} and score >= 65
    )
    weighted_score = _weighted_score(driver_scores, risk_flags)
    priority = _priority(driver_scores, aligned_drivers, risk_flags)
    research_bias = _research_bias(merged, driver_scores, risk_flags)
    explanation = _explanation(driver_scores, risk_flags, evidence_gaps, themes, priority)

    return _ScoredCandidate(
        ticker=ticker,
        priority=priority,
        weighted_score=weighted_score,
        driver_scores=driver_scores,
        research_bias=research_bias,
        risk_flags=risk_flags,
        explanation=explanation,
        evidence_gaps=evidence_gaps,
        themes=themes,
    )


def _queue_item(item: _ScoredCandidate) -> dict[str, Any]:
    return {
        "ticker": item.ticker,
        "symbol": item.ticker,
        "priority": item.priority,
        "researchBias": item.research_bias,
        "driverScores": {key: item.driver_scores[key] for key in _DRIVER_KEYS},
        "explanation": item.explanation,
        "duplicateEvidenceMerged": item.duplicate_evidence_merged,
        "riskFlags": list(item.risk_flags),
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
    }


def _summary(
    scored: Sequence[_ScoredCandidate],
    *,
    market_context: Mapping[str, Any],
    theme_context: Mapping[str, Any],
    duplicate_evidence_merged: int,
) -> dict[str, Any]:
    evidence_gaps = _dedupe(
        gap
        for item in scored
        for gap in item.evidence_gaps
    )
    dominant_themes = list(theme_context.get("dominantThemes") or [])
    if not dominant_themes:
        dominant_themes = _dedupe(theme for item in scored for theme in item.themes)[:3]

    if not scored:
        market_fit = "unavailable" if market_context else "neutral"
        queue_quality = "thin"
    else:
        regime_scores = [item.driver_scores["regimeFit"] for item in scored]
        market_fit = _market_fit(regime_scores, has_context=bool(market_context))
        evidence_scores = [item.driver_scores["evidenceQuality"] for item in scored]
        if max(evidence_scores) < 45:
            queue_quality = "low_evidence"
        elif any(item.priority == "high" for item in scored):
            queue_quality = "strong" if len(scored) >= 2 else "mixed"
        elif any(item.priority == "medium" for item in scored):
            queue_quality = "mixed"
        else:
            queue_quality = "thin"

    return {
        "dominantThemes": dominant_themes[:5],
        "evidenceGaps": evidence_gaps,
        "marketContextFit": market_fit,
        "queueQuality": queue_quality,
        "duplicateEvidenceMerged": int(duplicate_evidence_merged),
        "queueDiversity": _queue_diversity(scored),
    }


def _priority(driver_scores: Mapping[str, int], aligned_drivers: int, risk_flags: Sequence[str]) -> str:
    evidence = driver_scores["evidenceQuality"]
    liquidity = driver_scores["liquidityTradability"]
    trend = driver_scores["trendStructure"]
    volume = driver_scores["volumeExpansion"]
    hard_flags = {"missing_evidence", "low_liquidity", "low_evidence_quality"}
    if evidence < 45 or liquidity < 35:
        return "low"
    if (
        aligned_drivers >= 3
        and evidence >= 60
        and liquidity >= 50
        and trend >= 72
        and (volume >= 70 or driver_scores["eventCatalyst"] >= 70)
        and "theme_regime_conflict" not in risk_flags
        and "extreme_extension" not in risk_flags
        and "mixed_regime" not in risk_flags
        and "theme_concentration" not in risk_flags
    ):
        return "high"
    if aligned_drivers >= 2 and evidence >= 45 and liquidity >= 40 and not hard_flags.intersection(risk_flags):
        return "medium"
    return "low"


def _weighted_score(driver_scores: Mapping[str, int], risk_flags: Sequence[str]) -> float:
    weights = {
        "relativeStrength": 0.16,
        "volumeExpansion": 0.13,
        "trendStructure": 0.15,
        "themeAlignment": 0.13,
        "regimeFit": 0.10,
        "eventCatalyst": 0.10,
        "liquidityTradability": 0.11,
        "evidenceQuality": 0.12,
    }
    score = sum(driver_scores[key] * weight for key, weight in weights.items())
    penalties = {
        "missing_evidence": 18,
        "low_evidence_quality": 10,
        "low_liquidity": 14,
        "theme_regime_conflict": 10,
        "mixed_regime": 8,
        "theme_concentration": 5,
        "extreme_extension": 8,
        "elevated_volatility": 6,
    }
    return round(max(0.0, score - sum(penalties.get(flag, 0) for flag in risk_flags)), 2)


def _research_bias(
    candidate: Mapping[str, Any],
    driver_scores: Mapping[str, int],
    risk_flags: Sequence[str],
) -> str:
    trend_label = _text(_first(candidate, ("trendStructure", "trend_structure", "trendState", "trend_state"))).lower()
    if "missing_evidence" in risk_flags or driver_scores["evidenceQuality"] < 45:
        return "avoidLowEvidence"
    if "elevated_volatility" in risk_flags:
        return "volatilityRisk"
    if "pullback" in trend_label:
        return "pullbackWatch"
    if driver_scores["eventCatalyst"] >= 70 and driver_scores["evidenceQuality"] >= 55:
        return "eventDriven"
    if "breakout" in trend_label or (driver_scores["trendStructure"] >= 80 and driver_scores["volumeExpansion"] >= 70):
        return "breakoutWatch"
    if driver_scores["relativeStrength"] >= 70 and driver_scores["trendStructure"] >= 65:
        return "strengthContinuation"
    return "mixed"


def _risk_flags(
    candidate: Mapping[str, Any],
    driver_scores: Mapping[str, int],
    evidence_payload: Mapping[str, Any],
    themes: Sequence[str],
    market_context: Mapping[str, Any],
) -> list[str]:
    flags: list[str] = []
    if driver_scores["liquidityTradability"] < 40:
        flags.append("low_liquidity")
    if driver_scores["evidenceQuality"] < 45 or _evidence_gaps(evidence_payload, driver_scores):
        flags.append("missing_evidence")
    if driver_scores["evidenceQuality"] < 60:
        flags.append("low_evidence_quality")
    if _has_regime_conflict(themes, market_context):
        flags.append("theme_regime_conflict")
    if _market_regime(market_context) in {"mixed", "lowconfidence", "rangebound"}:
        flags.append("mixed_regime")
    if _safe_float(_first(candidate, ("extensionPct", "extension_pct", "distanceFromMA20Pct", "distance_from_ma20_pct"))) is not None:
        extension = abs(float(_first(candidate, ("extensionPct", "extension_pct", "distanceFromMA20Pct", "distance_from_ma20_pct"))))
        if extension >= 18:
            flags.append("extreme_extension")
    volatility = _safe_float(_first(candidate, ("volatilityPct", "volatility_pct", "atr20Pct", "atr20_pct")))
    if volatility is not None and volatility >= 8:
        flags.append("elevated_volatility")
    return _dedupe(flags)


def _explanation(
    driver_scores: Mapping[str, int],
    risk_flags: Sequence[str],
    evidence_gaps: Sequence[str],
    themes: Sequence[str],
    priority: str,
) -> dict[str, list[str]]:
    leading = [label for key, label in _driver_labels().items() if driver_scores[key] >= 65]
    why = leading[:3] or ["Low-confidence watch because evidence is incomplete."]
    if themes and driver_scores["themeAlignment"] >= 65:
        why.append(f"Theme context aligns with {themes[0]}.")

    verify: list[str] = []
    if driver_scores["relativeStrength"] >= 65:
        verify.append("Verify relative strength persists versus the benchmark.")
    if driver_scores["volumeExpansion"] >= 65:
        verify.append("Verify volume expansion is not a one-session anomaly.")
    if driver_scores["themeAlignment"] >= 65:
        verify.append("Verify theme leadership with current sector breadth.")
    if driver_scores["eventCatalyst"] >= 65:
        verify.append("Verify event detail, timing, and source quality.")
    if evidence_gaps:
        verify.append(f"Close evidence gap: {evidence_gaps[0]}.")
    if not verify:
        verify.append("Verify core price, volume, structure, and evidence quality inputs.")

    why_not_higher: list[str] = []
    if priority != "high":
        if driver_scores["evidenceQuality"] < 60:
            why_not_higher.append("Evidence quality is below the strong research threshold.")
        if driver_scores["liquidityTradability"] < 50:
            why_not_higher.append("Liquidity evidence is not yet strong enough for a higher queue tier.")
        if driver_scores["trendStructure"] < 72:
            why_not_higher.append("Trend structure needs stronger confirmation.")
        if "theme_regime_conflict" in risk_flags:
            why_not_higher.append("Theme context conflicts with the current market backdrop.")
        if "mixed_regime" in risk_flags:
            why_not_higher.append("Mixed market regime lowers conviction.")
        if "theme_concentration" in risk_flags:
            why_not_higher.append("Queue diversity keeps repeated theme entries from crowding the top tier.")
        if not why_not_higher:
            why_not_higher.append("Driver alignment is not strong enough for the top research tier.")
    else:
        why_not_higher.append("Already in the top research tier; continue evidence checks.")

    invalidation = []
    if driver_scores["relativeStrength"] >= 65:
        invalidation.append("Relative strength fades below benchmark behavior.")
    if driver_scores["volumeExpansion"] >= 65:
        invalidation.append("Volume expansion fades before confirmation.")
    if "theme_regime_conflict" in risk_flags:
        invalidation.append("Market context keeps conflicting with theme leadership.")
    if "low_liquidity" in risk_flags:
        invalidation.append("Liquidity remains too thin for clean observation.")
    if "missing_evidence" in risk_flags:
        invalidation.append("Evidence gaps remain unresolved.")
    if not invalidation:
        invalidation.append("Driver alignment weakens or evidence quality deteriorates.")

    return {
        "whyOnRadar": _dedupe(why)[:4],
        "whatToVerify": _dedupe(verify)[:4],
        "whyNotHigherPriority": _dedupe(why_not_higher)[:4],
        "evidenceGaps": list(evidence_gaps)[:6],
        "invalidationObservations": _dedupe(invalidation)[:4],
    }


def _driver_labels() -> dict[str, str]:
    return {
        "relativeStrength": "Relative strength is above the research threshold.",
        "volumeExpansion": "Volume expansion is observable.",
        "trendStructure": "Trend structure is constructive.",
        "themeAlignment": "Theme or sector leadership is aligned.",
        "regimeFit": "Market context is supportive.",
        "eventCatalyst": "Event catalyst is visible.",
        "liquidityTradability": "Liquidity supports cleaner observation.",
        "evidenceQuality": "Evidence quality is acceptable.",
    }


def _score_percent(value: Any) -> int:
    number = _safe_float(value)
    if number is None:
        return 40
    if 0 <= number <= 1.5:
        number *= 100
    return _clamp_int(number)


def _score_volume_expansion(value: Any) -> int:
    number = _safe_float(value)
    if number is None:
        return 40
    if number > 5:
        return _clamp_int(number)
    if number >= 2.0:
        return 90
    if number >= 1.5:
        return 76
    if number >= 1.2:
        return 65
    if number >= 1.0:
        return 50
    if number >= 0.8:
        return 38
    return 25


def _score_trend_structure(candidate: Mapping[str, Any]) -> int:
    numeric = _safe_float(_first(candidate, ("trendScore", "trend_score")))
    if numeric is not None:
        return _clamp_int(numeric)
    label = _text(_first(candidate, ("trendStructure", "trend_structure", "trendState", "trend_state"))).lower()
    if not label:
        return 40
    for key, score in _TREND_LABEL_SCORES.items():
        if key in label:
            return score
    return 50


def _score_theme_alignment(themes: Sequence[str], theme_context: Mapping[str, Any]) -> int:
    if not themes and not theme_context:
        return 50
    if not themes:
        return 40
    dominant = {theme.lower(): score for theme, score in (theme_context.get("themeScores") or {}).items()}
    if not dominant:
        return 55
    theme_keys = {theme.lower() for theme in themes}
    matched_scores = [score for name, score in dominant.items() if name in theme_keys]
    if matched_scores:
        return _clamp_int(max(matched_scores))
    return 45


def _score_regime_fit(
    themes: Sequence[str],
    market_context: Mapping[str, Any],
    candidate: Mapping[str, Any],
    driver_scores: Mapping[str, int],
) -> int:
    if not market_context:
        return 50
    if _has_regime_conflict(themes, market_context):
        return 25
    favorable = {_text(item).lower() for item in _sequence(_first(market_context, ("favorableThemes", "favorable_themes")))}
    if favorable and {theme.lower() for theme in themes}.intersection(favorable):
        return 75
    regime = _market_regime(market_context)
    strength_or_breakout = (
        driver_scores["trendStructure"] >= 72
        and driver_scores["relativeStrength"] >= 65
    )
    volatility = _safe_float(_first(candidate, ("volatilityPct", "volatility_pct", "atr20Pct", "atr20_pct")))
    low_evidence_or_volatility = (
        driver_scores["evidenceQuality"] < 60
        or (volatility is not None and volatility >= 8)
        or "volatile" in _text(_first(candidate, ("trendStructure", "trend_structure", "trendState", "trend_state"))).lower()
    )
    if regime in {"riskon", "upsidechaserisk", "upsidechase"}:
        return 72 if strength_or_breakout else 56
    if regime in {"riskoff", "eventrisk"}:
        return 66 if low_evidence_or_volatility else 42
    if regime in {"mixed", "lowconfidence", "rangebound"}:
        return 40
    if regime in {"downsideaccelerationrisk", "volatilitycompression"}:
        return 38 if strength_or_breakout else 50
    return 50


def _score_event_catalyst(value: Any) -> int:
    if value in (None, "", False):
        return 40
    if isinstance(value, Mapping):
        state = _text(_first(value, ("state", "status", "quality"))).lower()
        if state in {"confirmed", "available", "complete"}:
            return 80
        if state in {"partial", "mixed", "needs_confirmation"}:
            return 56
        if state in {"missing", "unavailable", "blocked"}:
            return 20
        return 62 if value else 40
    if isinstance(value, (list, tuple, set)):
        return 66 if value else 40
    return 60


def _score_liquidity(value: Any) -> int:
    amount = _safe_float(value)
    if amount is None:
        return 35
    if amount >= 100_000_000:
        return 90
    if amount >= 50_000_000:
        return 80
    if amount >= 20_000_000:
        return 65
    if amount >= 5_000_000:
        return 45
    if amount > 0:
        return 25
    return 20


def _score_evidence_quality(value: Mapping[str, Any]) -> int:
    explicit_score = _safe_float(_first(value, ("score", "qualityScore", "quality_score", "confidence")))
    if explicit_score is not None:
        if 0 <= explicit_score <= 1.5:
            explicit_score *= 100
        return _clamp_int(explicit_score - _evidence_quality_penalty(value))
    state = _text(_first(value, ("state", "status", "evidenceQuality", "quality"))).lower()
    if state in _QUALITY_LABEL_SCORES:
        return _clamp_int(_QUALITY_LABEL_SCORES[state] - _evidence_quality_penalty(value))
    if not value:
        return 40
    return _clamp_int(50 - _evidence_quality_penalty(value))


def _theme_context(value: Mapping[str, Any] | Any | None) -> dict[str, Any]:
    payload = _mapping(value)
    theme_scores: dict[str, int] = {}
    dominant_names: list[str] = []
    for item in _sequence(_first(payload, ("dominantThemes", "themes", "strongestThemes", "acceleratingThemes"))):
        if isinstance(item, Mapping):
            name = _text(_first(item, ("name", "theme", "themeName", "id")))
            score = _score_percent(_first(item, ("leadershipScore", "rotationScore", "score", "confidence")))
        else:
            name = _text(item)
            score = 75
        if not name:
            continue
        dominant_names.append(name)
        theme_scores[name] = max(score, theme_scores.get(name, 0))
    return {
        "dominantThemes": _dedupe(dominant_names),
        "themeScores": theme_scores,
    }


def _merged_evidence_payload(candidate: Mapping[str, Any], evidence_context: Mapping[str, Any]) -> dict[str, Any]:
    candidate_evidence = _mapping(_first(candidate, ("evidenceQuality", "evidence_quality", "evidence")))
    if not candidate_evidence:
        raw = _first(candidate, ("evidenceQuality", "evidence_quality"))
        if raw not in (None, ""):
            candidate_evidence = {"state": raw}
    return {**_mapping(evidence_context), **candidate_evidence}


def _evidence_gaps(evidence_payload: Mapping[str, Any], driver_scores: Mapping[str, int]) -> list[str]:
    gaps = _dedupe(
        str(item)
        for item in (
            list(_sequence(_first(evidence_payload, ("missing", "missingEvidence", "evidenceGaps", "gaps"))))
        )
    )
    if _is_truthy(_first(evidence_payload, ("isStale", "is_stale", "stale"))) or _text(
        _first(evidence_payload, ("freshnessState", "freshness", "freshness_state"))
    ).lower() == "stale":
        gaps.append("staleEvidence")
    if _is_truthy(_first(evidence_payload, ("isFallback", "is_fallback", "fallback"))) or "fallback" in _text(
        _first(evidence_payload, ("sourceClass", "source_class", "source"))
    ).lower():
        gaps.append("fallbackEvidence")
    if _is_truthy(_first(evidence_payload, ("isProxy", "is_proxy", "proxy", "proxyObservation"))) or "proxy" in _text(
        _first(evidence_payload, ("sourceClass", "source_class", "source"))
    ).lower():
        gaps.append("proxyEvidence")
    if _is_truthy(_first(evidence_payload, ("sampleOnly", "sample_only", "isSampleOnly", "is_sample_only"))):
        gaps.append("sampleOnlyEvidence")
    if driver_scores["evidenceQuality"] < 45 and not gaps:
        gaps.append("evidenceQuality")
    return _dedupe(gaps)


def _dedupe_scored_candidates(scored: Sequence[_ScoredCandidate]) -> tuple[list[_ScoredCandidate], int]:
    by_symbol: dict[str, list[_ScoredCandidate]] = {}
    for item in scored:
        if not item.ticker:
            continue
        by_symbol.setdefault(item.ticker, []).append(item)

    result: list[_ScoredCandidate] = []
    duplicate_count = 0
    for symbol in sorted(by_symbol):
        items = by_symbol[symbol]
        duplicate_count += max(0, len(items) - 1)
        strongest = max(items, key=_dedupe_strength_key)
        result.append(replace(strongest, duplicate_evidence_merged=max(0, len(items) - 1)))
    return result, duplicate_count


def _dedupe_strength_key(item: _ScoredCandidate) -> tuple[int, int, float, str]:
    return (
        item.driver_scores["evidenceQuality"],
        -_PRIORITY_RANK[item.priority],
        item.weighted_score,
        item.ticker,
    )


def _sort_key(item: _ScoredCandidate) -> tuple[int, float, int, str]:
    return (
        _PRIORITY_RANK[item.priority],
        -item.weighted_score,
        -item.driver_scores["evidenceQuality"],
        item.ticker,
    )


def _apply_queue_diversity(scored: Sequence[_ScoredCandidate]) -> list[_ScoredCandidate]:
    high_items = [item for item in scored if item.priority == "high"]
    high_themes = {_primary_theme(item) for item in high_items if _primary_theme(item)}
    if len(high_themes) < 2:
        return list(scored)

    seen_high_themes: set[str] = set()
    adjusted: list[_ScoredCandidate] = []
    for item in sorted(scored, key=_sort_key):
        primary_theme = _primary_theme(item)
        if item.priority == "high" and primary_theme in seen_high_themes:
            risk_flags = _dedupe([*item.risk_flags, "theme_concentration"])
            driver_scores = dict(item.driver_scores)
            driver_scores["themeAlignment"] = max(55, driver_scores["themeAlignment"] - 10)
            priority = _priority(
                driver_scores,
                _aligned_driver_count(driver_scores),
                risk_flags,
            )
            if priority == "high":
                priority = "medium"
            explanation = _explanation(
                driver_scores,
                risk_flags,
                item.evidence_gaps,
                item.themes,
                priority,
            )
            adjusted.append(
                replace(
                    item,
                    priority=priority,
                    weighted_score=_weighted_score(driver_scores, risk_flags),
                    driver_scores=driver_scores,
                    risk_flags=risk_flags,
                    explanation=explanation,
                )
            )
            continue
        if item.priority == "high" and primary_theme:
            seen_high_themes.add(primary_theme)
        adjusted.append(item)
    adjusted.sort(key=_sort_key)
    return adjusted


def _queue_diversity(scored: Sequence[_ScoredCandidate]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in scored:
        theme = _primary_theme(item) or "unclassified"
        counts[theme] = counts.get(theme, 0) + 1
    high_theme_count = len({_primary_theme(item) for item in scored if item.priority == "high" and _primary_theme(item)})
    status = "thin"
    if len(counts) >= 2 and high_theme_count >= 2:
        status = "diversified"
    elif len(counts) >= 2:
        status = "mixed"
    elif counts:
        status = "concentrated"
    return {
        "status": status,
        "themeCounts": counts,
    }


def _primary_theme(item: _ScoredCandidate) -> str:
    return _text(item.themes[0]).lower() if item.themes else ""


def _aligned_driver_count(driver_scores: Mapping[str, int]) -> int:
    return sum(
        1
        for key, score in driver_scores.items()
        if key not in {"regimeFit", "evidenceQuality"} and score >= 65
    )


def _evidence_quality_penalty(value: Mapping[str, Any]) -> int:
    penalty = 0
    source_text = _text(_first(value, ("sourceClass", "source_class", "source"))).lower()
    freshness = _text(_first(value, ("freshnessState", "freshness", "freshness_state"))).lower()
    if _is_truthy(_first(value, ("isStale", "is_stale", "stale"))) or freshness == "stale":
        penalty += 18
    if _is_truthy(_first(value, ("isFallback", "is_fallback", "fallback"))) or "fallback" in source_text:
        penalty += 16
    if _is_truthy(_first(value, ("isProxy", "is_proxy", "proxy", "proxyObservation"))) or "proxy" in source_text:
        penalty += 14
    if _is_truthy(_first(value, ("sampleOnly", "sample_only", "isSampleOnly", "is_sample_only"))):
        penalty += 14
    return penalty


def _market_fit(regime_scores: Sequence[int], *, has_context: bool) -> str:
    if not has_context:
        return "neutral"
    supportive = sum(1 for score in regime_scores if score >= 65)
    conflicting = sum(1 for score in regime_scores if score < 40)
    if supportive and not conflicting:
        return "supportive"
    if conflicting and not supportive:
        return "conflicting"
    if supportive or conflicting:
        return "mixed"
    return "neutral"


def _has_regime_conflict(themes: Sequence[str], market_context: Mapping[str, Any]) -> bool:
    unfavorable = {_text(item).lower() for item in _sequence(_first(market_context, ("unfavorableThemes", "unfavorable_themes", "avoidThemes", "avoid_themes")))}
    return bool(unfavorable and {theme.lower() for theme in themes}.intersection(unfavorable))


def _market_regime(market_context: Mapping[str, Any]) -> str:
    raw = _text(_first(market_context, ("regime", "marketRegime", "market_regime", "decision", "label")))
    return "".join(ch for ch in raw.lower() if ch.isalnum())


def _symbol_context_map(value: Mapping[str, Any] | Any | None) -> dict[str, dict[str, Any]]:
    payload = _mapping(value)
    if not payload:
        return {}
    source = _mapping(_first(payload, ("bySymbol", "by_symbol", "symbols", "candidates"))) or payload
    result: dict[str, dict[str, Any]] = {}
    if isinstance(source, Mapping):
        for key, item in source.items():
            symbol = _normalize_symbol(key)
            mapping = _mapping(item)
            if symbol and mapping:
                result[symbol] = mapping
    return result


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _symbol_from(value: Mapping[str, Any] | Any) -> str:
    payload = _mapping(value)
    return _normalize_symbol(_first(payload, ("ticker", "symbol", "code", "stockCode", "stock_code")))


def _normalize_symbol(value: Any) -> str:
    return _text(value).upper()


def _themes(value: Mapping[str, Any]) -> list[str]:
    raw_values = []
    for key in ("themes", "theme", "sector", "sectors", "boards", "_matched_sectors"):
        raw_values.extend(_sequence(value.get(key)))
    return _dedupe(_text(item) for item in raw_values if _text(item))


def _sequence(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _first(mapping: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, "") or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "on"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _clamp_int(value: float) -> int:
    return int(round(max(0.0, min(100.0, value))))


def _dedupe(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = _text(item)
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


__all__ = [
    "NO_ADVICE_DISCLOSURE",
    "RESEARCH_RADAR_CANDIDATE_ENGINE_SCHEMA_VERSION",
    "build_research_radar_candidate_queue",
]
