# -*- coding: utf-8 -*-
"""Deterministic market regime decision engine.

The engine is intentionally pure: callers provide already-normalized market
evidence, and this module does not call providers, read credentials, mutate
caches, or make personalized financial recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "market_regime_decision_engine.v1"
NO_ADVICE_DISCLOSURE = "Research support only; not personalized financial advice."

DRIVER_KEYS: tuple[str, ...] = (
    "dealerGamma",
    "breadthParticipation",
    "volatilityStructure",
    "ratesDollar",
    "liquidityCredit",
    "crossAssetRisk",
    "sectorThemeRotation",
    "eventCatalyst",
)

REGIMES: tuple[str, ...] = (
    "riskOn",
    "riskOff",
    "rangeBound",
    "volatilityCompression",
    "downsideAccelerationRisk",
    "upsideChaseRisk",
    "eventRisk",
    "mixed",
    "lowConfidence",
)

_BLOCKING_FRESHNESS = {"fallback", "mock", "synthetic", "unavailable", "error"}
_LIMITED_FRESHNESS = {"stale", "partial", "delayed"}
_PROXY_MARKERS = ("proxy", "sample", "fixture", "fallback", "mock", "synthetic")
_UNOFFICIAL_SOURCE_TYPES = {"unofficial_public_api", "third_party_free_api"}
_EVENT_PANELS = ("events", "eventCatalyst", "eventRisk", "macroEvents")


@dataclass(frozen=True, slots=True)
class _EvidenceQuality:
    allowed: bool
    state: str
    reasons: tuple[str, ...]
    cap_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _DriverResult:
    key: str
    score: int
    evidence_state: str
    reasons: tuple[str, ...]
    evidence_count: int
    observations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "evidenceState": self.evidence_state,
            "reasons": list(self.reasons),
            "evidenceCount": self.evidence_count,
            "observations": list(self.observations),
        }


class MarketRegimeDecisionEngine:
    """Rule-first deterministic classifier for market-condition research."""

    def decide(self, inputs: Mapping[str, Any] | None = None, **context: Any) -> dict[str, Any]:
        market_inputs: Mapping[str, Any] = inputs if isinstance(inputs, Mapping) else {}
        drivers = {
            "dealerGamma": self._dealer_gamma_driver(),
            "breadthParticipation": self._breadth_driver(market_inputs),
            "volatilityStructure": self._volatility_driver(market_inputs),
            "ratesDollar": self._rates_dollar_driver(market_inputs),
            "liquidityCredit": self._liquidity_credit_driver(market_inputs),
            "crossAssetRisk": self._cross_asset_driver(market_inputs),
            "sectorThemeRotation": self._rotation_driver(market_inputs),
            "eventCatalyst": self._event_driver(market_inputs),
        }
        cap_reasons = self._confidence_cap_reasons(market_inputs, drivers)
        regime = self._classify_regime(drivers, cap_reasons)
        if regime not in REGIMES:
            regime = "lowConfidence"
        if regime == "volatilityCompression" and drivers["dealerGamma"].evidence_state == "unavailable":
            cap_reasons = sorted(
                {
                    *cap_reasons,
                    "dealer_gamma_unavailable_caps_volatility_compression",
                }
            )
        confidence_score = self._confidence_score(regime, drivers, cap_reasons)
        confidence = self._confidence_label(confidence_score)
        missing_evidence = self._missing_evidence(drivers)
        data_quality = self._data_quality(market_inputs, drivers, cap_reasons, confidence_score)

        return {
            "schemaVersion": SCHEMA_VERSION,
            "regime": regime,
            "confidence": confidence,
            "confidenceScore": confidence_score,
            "driverScores": {key: drivers[key].to_dict() for key in DRIVER_KEYS},
            "explanation": self._explanation(regime, drivers),
            "researchPriorities": self._research_priorities(regime, drivers, missing_evidence, data_quality),
            "dataQuality": data_quality,
            "missingEvidence": missing_evidence,
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        }

    @staticmethod
    def _dealer_gamma_driver() -> _DriverResult:
        return _DriverResult(
            key="dealerGamma",
            score=0,
            evidence_state="unavailable",
            reasons=("live_gex_not_implemented_v1",),
            evidence_count=0,
            observations=("Dealer gamma is intentionally unavailable in v1.",),
        )

    def _breadth_driver(self, inputs: Mapping[str, Any]) -> _DriverResult:
        scored: list[int] = []
        observations: list[str] = []
        reasons: list[str] = []
        for item in _panel_items(inputs, "breadth", "cnBreadth", "usBreadth"):
            quality = _evidence_quality(item)
            if not quality.allowed:
                reasons.extend(quality.reasons)
                continue
            symbol = _text(item.get("symbol") or item.get("key")).upper()
            value = _number(item.get("value") or item.get("advanceRatio") or item.get("advancingPercent"))
            change = _number(item.get("changePercent") or item.get("change_pct") or item.get("change"))
            score: int | None = None
            if value is not None and ("ADV" in symbol or "BREADTH" in symbol or 0 <= value <= 100):
                score = _clamp_int((value - 50.0) * 2.0 + (change or 0.0) * 2.0)
            elif value is not None:
                score = _clamp_int(value)
            if score is not None:
                scored.append(score)
                observations.append(_observation(symbol or "breadth", value, change))
        return _driver_from_scores("breadthParticipation", scored, reasons, observations)

    def _volatility_driver(self, inputs: Mapping[str, Any]) -> _DriverResult:
        scored: list[int] = []
        observations: list[str] = []
        reasons: list[str] = []
        for item in [*_panel_items(inputs, "rates"), *_panel_items(inputs, "volatility")]:
            symbol = _text(item.get("symbol") or item.get("key")).upper()
            label = _text(item.get("label")).upper()
            if not any(token in f"{symbol} {label}" for token in ("VIX", "VOL", "MOVE")):
                continue
            quality = _evidence_quality(item)
            if not quality.allowed:
                reasons.extend(quality.reasons)
                continue
            value = _number(item.get("value") or item.get("price"))
            change = _number(item.get("changePercent") or item.get("change_pct") or item.get("change"))
            if value is None and change is None:
                continue
            if value is None:
                score = -(change or 0.0) * 6.0
            else:
                score = (20.0 - value) * 4.0 - (change or 0.0) * 3.0
            scored.append(_clamp_int(score))
            observations.append(_observation(symbol or label or "volatility", value, change))
        return _driver_from_scores("volatilityStructure", scored, reasons, observations)

    def _rates_dollar_driver(self, inputs: Mapping[str, Any]) -> _DriverResult:
        scored: list[int] = []
        observations: list[str] = []
        reasons: list[str] = []
        for item in [*_panel_items(inputs, "rates"), *_panel_items(inputs, "fx", "macro")]:
            symbol = _text(item.get("symbol") or item.get("key")).upper()
            label = _text(item.get("label")).upper()
            descriptor = f"{symbol} {label}"
            if not any(token in descriptor for token in ("US10Y", "DGS10", "DXY", "USD", "T10Y", "DOLLAR")):
                continue
            if "VIX" in descriptor:
                continue
            quality = _evidence_quality(item)
            if not quality.allowed:
                reasons.extend(quality.reasons)
                continue
            value = _number(item.get("value") or item.get("price"))
            change = _number(item.get("changePercent") or item.get("change_pct") or item.get("change"))
            score = 0.0
            if change is not None:
                score -= change * 18.0
            if value is not None:
                if any(token in descriptor for token in ("US10Y", "DGS10", "T10Y")):
                    score += (4.35 - value) * 28.0
                elif any(token in descriptor for token in ("DXY", "USD", "DOLLAR")):
                    score += (103.0 - value) * 5.0
            scored.append(_clamp_int(score))
            observations.append(_observation(symbol or label or "ratesDollar", value, change))
        return _driver_from_scores("ratesDollar", scored, reasons, observations)

    def _liquidity_credit_driver(self, inputs: Mapping[str, Any]) -> _DriverResult:
        scored: list[int] = []
        observations: list[str] = []
        reasons: list[str] = []
        signal = inputs.get("capitalFlowSignal")
        if isinstance(signal, Mapping):
            quality = _evidence_quality(signal)
            if quality.allowed:
                value = _number(signal.get("score") or signal.get("value") or signal.get("liquidityScore"))
                destination = _text(signal.get("likelyDestination"))
                if value is not None:
                    scored.append(_clamp_int(value))
                    observations.append(f"capitalFlowSignal={destination or 'observed'}")
                elif destination and destination != "no_clear_edge":
                    scored.append(35)
                    observations.append(f"capitalFlowSignal={destination}")
            else:
                reasons.extend(quality.reasons)

        for item in [*_panel_items(inputs, "flows"), *_panel_items(inputs, "rates", "macro")]:
            symbol = _text(item.get("symbol") or item.get("key")).upper()
            label = _text(item.get("label")).upper()
            descriptor = f"{symbol} {label}"
            if not any(
                token in descriptor
                for token in ("BAML", "HY", "CREDIT", "SPREAD", "RRP", "WALCL", "LIQUIDITY", "NORTHBOUND", "ETF")
            ):
                continue
            quality = _evidence_quality(item)
            if not quality.allowed:
                reasons.extend(quality.reasons)
                continue
            value = _number(item.get("value") or item.get("price"))
            change = _number(item.get("changePercent") or item.get("change_pct") or item.get("change"))
            score = 0.0
            if any(token in descriptor for token in ("BAML", "HY", "CREDIT", "SPREAD")):
                if value is not None:
                    score += (4.0 - value) * 18.0
                if change is not None:
                    score -= change * 8.0
            else:
                score = value if value is not None and -100 <= value <= 100 else (change or 0.0) * 8.0
            scored.append(_clamp_int(score))
            observations.append(_observation(symbol or label or "liquidityCredit", value, change))
        return _driver_from_scores("liquidityCredit", scored, reasons, observations)

    def _cross_asset_driver(self, inputs: Mapping[str, Any]) -> _DriverResult:
        scored: list[int] = []
        observations: list[str] = []
        reasons: list[str] = []
        for item in [*_panel_items(inputs, "futures"), *_panel_items(inputs, "crypto")]:
            quality = _evidence_quality(item)
            if not quality.allowed:
                reasons.extend(quality.reasons)
                continue
            symbol = _text(item.get("symbol") or item.get("key")).upper()
            change = _number(item.get("changePercent") or item.get("change_pct") or item.get("change"))
            if change is None:
                continue
            scored.append(_clamp_int(change * 22.0))
            observations.append(_observation(symbol or "crossAsset", _number(item.get("value") or item.get("price")), change))
        return _driver_from_scores("crossAssetRisk", scored, reasons, observations)

    def _rotation_driver(self, inputs: Mapping[str, Any]) -> _DriverResult:
        scored: list[int] = []
        observations: list[str] = []
        reasons: list[str] = []
        for item in _panel_items(inputs, "sectors", "sectorRotation", "rotationFamilyRollup"):
            quality = _evidence_quality(item)
            if not quality.allowed:
                reasons.extend(quality.reasons)
                continue
            if item.get("rankEligible") is False or item.get("headlineEligible") is False or item.get("taxonomyOnly") is True:
                reasons.append("source_authority_or_score_gate_blocked")
                continue
            value = _number(item.get("rotationScore") or item.get("value") or item.get("score"))
            change = _number(item.get("changePercent") or item.get("change_pct") or item.get("change"))
            if value is None and change is None:
                continue
            score = (value - 50.0) * 2.0 if value is not None and 0 <= value <= 100 else (value or 0.0)
            score += (change or 0.0) * 4.0
            scored.append(_clamp_int(score))
            observations.append(_observation(_text(item.get("symbol") or item.get("label") or "rotation"), value, change))
        return _driver_from_scores("sectorThemeRotation", scored, reasons, observations)

    def _event_driver(self, inputs: Mapping[str, Any]) -> _DriverResult:
        scored: list[int] = []
        observations: list[str] = []
        reasons: list[str] = []
        for item in _panel_items(inputs, *_EVENT_PANELS):
            quality = _evidence_quality(item, require_live=True)
            if not quality.allowed:
                reasons.extend(quality.reasons)
                continue
            value = _number(item.get("riskScore") or item.get("value") or item.get("score"))
            if value is None:
                continue
            scored.append(_clamp_int(-abs(value)))
            observations.append(_observation(_text(item.get("symbol") or item.get("label") or "event"), value, None))
        return _driver_from_scores("eventCatalyst", scored, reasons, observations, empty_reason="event_evidence_missing")

    @staticmethod
    def _confidence_cap_reasons(inputs: Mapping[str, Any], drivers: Mapping[str, _DriverResult]) -> list[str]:
        cap_reasons: list[str] = []
        for item in _all_evidence_items(inputs):
            quality = _evidence_quality(item)
            cap_reasons.extend(quality.cap_reasons)
        if any(driver.evidence_state == "blocked" for driver in drivers.values()):
            cap_reasons.append("source_authority_or_score_gate_blocked")
        return sorted(set(cap_reasons))

    def _classify_regime(self, drivers: Mapping[str, _DriverResult], cap_reasons: Sequence[str]) -> str:
        coverage = _scoring_driver_count(drivers)
        if coverage < 3:
            return "lowConfidence"

        breadth = drivers["breadthParticipation"].score
        vol = drivers["volatilityStructure"].score
        rates_dollar = drivers["ratesDollar"].score
        liquidity = drivers["liquidityCredit"].score
        cross_asset = drivers["crossAssetRisk"].score
        rotation = drivers["sectorThemeRotation"].score
        event = drivers["eventCatalyst"].score

        if drivers["eventCatalyst"].evidence_state == "score_grade" and event <= -60:
            return "eventRisk"

        negative_cluster = sum(score <= -35 for score in (breadth, vol, rates_dollar, liquidity, cross_asset))
        if vol <= -50 and breadth <= -35 and negative_cluster >= 3:
            return "downsideAccelerationRisk"

        positive_count = sum(score >= 30 for score in (breadth, liquidity, cross_asset, rotation))
        negative_count = sum(score <= -30 for score in (breadth, vol, rates_dollar, liquidity, cross_asset, rotation))
        if positive_count >= 2 and negative_count >= 2:
            return "mixed"

        if vol >= 55 and abs(breadth) <= 25 and abs(rates_dollar) <= 30 and abs(cross_asset) <= 30 and event > -40:
            return "volatilityCompression"

        if positive_count >= 3 and rotation >= 65 and vol <= -25:
            return "upsideChaseRisk"

        if negative_count >= 3:
            return "riskOff"

        if positive_count >= 3 and vol > -30 and rates_dollar > -30:
            return "riskOn"

        if max(abs(score) for score in (breadth, vol, rates_dollar, liquidity, cross_asset, rotation)) <= 30:
            return "rangeBound"
        return "mixed"

    @staticmethod
    def _confidence_score(regime: str, drivers: Mapping[str, _DriverResult], cap_reasons: Sequence[str]) -> float:
        coverage = _scoring_driver_count(drivers)
        if coverage >= 6:
            score = 0.78
        elif coverage == 5:
            score = 0.68
        elif coverage == 4:
            score = 0.56
        elif coverage == 3:
            score = 0.44
        else:
            score = 0.22

        if regime in {"mixed", "lowConfidence"}:
            score = min(score, 0.42)
        if regime == "eventRisk":
            score = min(score, 0.68)
        if regime == "volatilityCompression":
            score = min(score, 0.6)
            if "dealer_gamma_unavailable_caps_volatility_compression" not in cap_reasons:
                cap_reasons = [*cap_reasons, "dealer_gamma_unavailable_caps_volatility_compression"]
        if any(reason in cap_reasons for reason in ("proxy_or_sample_evidence_present", "observation_only_evidence_present")):
            score = min(score, 0.54)
        if "source_authority_or_score_gate_blocked" in cap_reasons:
            score = min(score, 0.46)
        return round(max(0.0, min(0.92, score)), 2)

    @staticmethod
    def _confidence_label(score: float) -> str:
        if score >= 0.72:
            return "high"
        if score >= 0.48:
            return "medium"
        return "low"

    @staticmethod
    def _missing_evidence(drivers: Mapping[str, _DriverResult]) -> list[str]:
        missing: list[str] = []
        for key in DRIVER_KEYS:
            driver = drivers[key]
            if driver.evidence_state == "unavailable":
                missing.append(f"{key}:unavailable")
            elif driver.evidence_state == "blocked":
                missing.append("source_authority_or_score_gate_blocked")
                missing.append(f"{key}:blocked")
        return sorted(set(missing))

    @staticmethod
    def _data_quality(
        inputs: Mapping[str, Any],
        drivers: Mapping[str, _DriverResult],
        cap_reasons: Sequence[str],
        confidence_score: float,
    ) -> dict[str, Any]:
        all_items = tuple(_all_evidence_items(inputs))
        return {
            "evidenceGrade": "score_grade" if confidence_score >= 0.72 else "capped" if confidence_score >= 0.48 else "limited",
            "availableDriverCount": sum(driver.evidence_state != "unavailable" for driver in drivers.values()),
            "scoringDriverCount": _scoring_driver_count(drivers),
            "blockedDriverCount": sum(driver.evidence_state == "blocked" for driver in drivers.values()),
            "missingDriverCount": sum(driver.evidence_state == "unavailable" for driver in drivers.values()),
            "proxyEvidenceCount": sum(1 for item in all_items if _has_proxy_marker(item)),
            "observationOnlyEvidenceCount": sum(1 for item in all_items if item.get("observationOnly") is True),
            "confidenceCapReasons": list(cap_reasons),
        }

    @staticmethod
    def _explanation(regime: str, drivers: Mapping[str, _DriverResult]) -> dict[str, list[str]]:
        ranked = sorted(
            (driver for key, driver in drivers.items() if key != "dealerGamma"),
            key=lambda driver: abs(driver.score),
            reverse=True,
        )
        top = [f"{_driver_label(driver.key)} score {driver.score}" for driver in ranked[:3] if driver.evidence_state != "unavailable"]
        if not top:
            top = ["Available evidence is insufficient for a stronger regime read."]

        confirms = [_confirmation_line(driver) for driver in ranked[:3] if driver.evidence_state == "score_grade"]
        if not confirms:
            confirms = ["More score-grade breadth, volatility, liquidity, and cross-asset evidence is needed."]

        invalidates = [
            "The read weakens if score-grade breadth, volatility, liquidity, or rates evidence moves the opposite way together.",
            "The read weakens if current drivers become proxy-only, stale, or observation-only.",
        ]

        return {
            "whyThisRegime": [f"{regime} selected from deterministic driver agreement.", *top],
            "whatConfirmsIt": confirms,
            "whatInvalidatesIt": invalidates,
            "keyTriggerLevels": _key_trigger_levels(drivers),
        }

    @staticmethod
    def _research_priorities(
        regime: str,
        drivers: Mapping[str, _DriverResult],
        missing_evidence: Sequence[str],
        data_quality: Mapping[str, Any],
    ) -> dict[str, list[str]]:
        pressure = [
            _driver_label(driver.key)
            for driver in drivers.values()
            if driver.key != "dealerGamma" and abs(driver.score) >= 45 and driver.evidence_state != "unavailable"
        ]
        watch_today = pressure[:3] or ["Breadth, volatility, rates-dollar, and cross-asset confirmation."]
        needs_more = list(missing_evidence[:4])
        if data_quality.get("confidenceCapReasons"):
            needs_more.extend(str(reason) for reason in data_quality["confidenceCapReasons"][:3])
        investigate = [
            "Confirm whether the dominant drivers persist across score-grade sources.",
            "Compare breadth participation with volatility and rates-dollar pressure.",
        ]
        if regime in {"mixed", "lowConfidence"}:
            investigate.insert(0, "Resolve conflicting or insufficient driver evidence before forming a stronger research view.")
        if "dealerGamma:unavailable" in missing_evidence:
            investigate.append("Add live dealer-gamma evidence before raising confidence in volatility-compression reads.")
        return {
            "watchToday": _dedupe(watch_today),
            "needsMoreEvidence": _dedupe(needs_more),
            "investigateNext": _dedupe(investigate),
        }


def build_market_regime_decision(inputs: Mapping[str, Any] | None = None, **context: Any) -> dict[str, Any]:
    """Build the v1 market regime decision payload from normalized evidence."""

    return MarketRegimeDecisionEngine().decide(inputs, **context)


def _panel_items(inputs: Mapping[str, Any], *panel_keys: str) -> list[Mapping[str, Any]]:
    items: list[Mapping[str, Any]] = []
    for key in panel_keys:
        value = inputs.get(key)
        if isinstance(value, Mapping):
            raw_items = value.get("items")
            if isinstance(raw_items, Sequence) and not isinstance(raw_items, (str, bytes, bytearray)):
                items.extend(item for item in raw_items if isinstance(item, Mapping))
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            items.extend(item for item in value if isinstance(item, Mapping))
    return items


def _all_evidence_items(inputs: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for value in inputs.values():
        if isinstance(value, Mapping):
            if "items" in value:
                yield from (item for item in value.get("items") or [] if isinstance(item, Mapping))
            elif any(key in value for key in ("source", "sourceType", "freshness", "scoreContributionAllowed")):
                yield value
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            yield from (item for item in value if isinstance(item, Mapping))


def _evidence_quality(item: Mapping[str, Any], *, require_live: bool = False) -> _EvidenceQuality:
    reasons: list[str] = []
    cap_reasons: list[str] = []
    freshness = _text(item.get("freshness")).lower()
    source_type = _text(item.get("sourceType") or item.get("sourceTier")).lower()

    if item.get("sourceAuthorityAllowed") is False or item.get("scoreContributionAllowed") is False:
        reasons.append("source_authority_or_score_gate_blocked")
    if item.get("observationOnly") is True:
        reasons.append("observation_only_evidence_blocked")
        cap_reasons.append("observation_only_evidence_present")
    if _has_proxy_marker(item):
        reasons.append("proxy_or_sample_evidence_blocked")
        cap_reasons.append("proxy_or_sample_evidence_present")
    if freshness in _BLOCKING_FRESHNESS:
        reasons.append(f"freshness_blocked:{freshness}")
        cap_reasons.append("non_score_grade_freshness_present")
    if require_live and freshness not in {"live", "fresh"}:
        reasons.append("live_event_evidence_required")
    if source_type in _UNOFFICIAL_SOURCE_TYPES or freshness in _LIMITED_FRESHNESS:
        cap_reasons.append("limited_source_quality_present")

    if reasons:
        return _EvidenceQuality(False, "blocked", tuple(sorted(set(reasons))), tuple(sorted(set(cap_reasons))))
    state = "limited" if cap_reasons else "score_grade"
    return _EvidenceQuality(True, state, (), tuple(sorted(set(cap_reasons))))


def _has_proxy_marker(item: Mapping[str, Any]) -> bool:
    descriptor = " ".join(
        _text(item.get(key)).lower()
        for key in ("source", "sourceType", "sourceTier", "sourceLabel", "degradationReason", "sourceAuthorityReason")
    )
    return any(marker in descriptor for marker in _PROXY_MARKERS)


def _driver_from_scores(
    key: str,
    scores: Sequence[int],
    reasons: Sequence[str],
    observations: Sequence[str],
    *,
    empty_reason: str | None = None,
) -> _DriverResult:
    unique_reasons = tuple(sorted(set(reason for reason in reasons if reason)))
    if scores:
        state = "limited" if any(reason.startswith("freshness_blocked:stale") for reason in unique_reasons) else "score_grade"
        return _DriverResult(
            key=key,
            score=_clamp_int(mean(scores)),
            evidence_state=state,
            reasons=unique_reasons,
            evidence_count=len(scores),
            observations=tuple(_dedupe(observations)),
        )
    if unique_reasons:
        return _DriverResult(
            key=key,
            score=0,
            evidence_state="blocked",
            reasons=unique_reasons,
            evidence_count=0,
            observations=tuple(_dedupe(observations)),
        )
    return _DriverResult(
        key=key,
        score=0,
        evidence_state="unavailable",
        reasons=(empty_reason or f"{key}_evidence_missing",),
        evidence_count=0,
        observations=tuple(_dedupe(observations)),
    )


def _scoring_driver_count(drivers: Mapping[str, _DriverResult]) -> int:
    return sum(
        1
        for key, driver in drivers.items()
        if key != "dealerGamma" and driver.evidence_state in {"score_grade", "limited"}
    )


def _key_trigger_levels(drivers: Mapping[str, _DriverResult]) -> list[str]:
    levels: list[str] = []
    for key in ("breadthParticipation", "volatilityStructure", "ratesDollar", "liquidityCredit", "crossAssetRisk"):
        driver = drivers[key]
        for observation in driver.observations[:2]:
            levels.append(f"{_driver_label(key)}: {observation}")
    return levels or ["No score-grade trigger levels available yet."]


def _confirmation_line(driver: _DriverResult) -> str:
    direction = "supportive" if driver.score > 0 else "pressure" if driver.score < 0 else "neutral"
    return f"{_driver_label(driver.key)} remains {direction} with score-grade evidence."


def _driver_label(key: str) -> str:
    return {
        "dealerGamma": "Dealer gamma",
        "breadthParticipation": "Breadth participation",
        "volatilityStructure": "Volatility structure",
        "ratesDollar": "Rates-dollar",
        "liquidityCredit": "Liquidity-credit",
        "crossAssetRisk": "Cross-asset risk",
        "sectorThemeRotation": "Sector-theme rotation",
        "eventCatalyst": "Event catalyst",
    }.get(key, key)


def _observation(symbol: str, value: float | None, change: float | None) -> str:
    parts = [symbol]
    if value is not None:
        parts.append(f"value={round(value, 3)}")
    if change is not None:
        parts.append(f"change={round(change, 3)}")
    return " ".join(parts)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clamp_int(value: float, lower: int = -100, upper: int = 100) -> int:
    return int(round(max(lower, min(upper, value))))
