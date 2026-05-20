# -*- coding: utf-8 -*-
"""Pure market regime synthesis from caller-supplied normalized evidence.

This module is intentionally inert: it does not import provider clients, read
configuration, call networks, mutate caches, or wire the result into runtime
Market Intelligence surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


MARKET_REGIME_SYNTHESIS_VERSION = "market_regime_synthesis_v1"

PILLARS: tuple[str, ...] = (
    "risk_appetite",
    "rates_pressure",
    "dollar_pressure",
    "volatility_stress",
    "liquidity_impulse",
    "crypto_risk_beta",
    "breadth_health",
    "china_risk_appetite",
    "rotation_leadership",
)

REGIME_CANDIDATES: tuple[str, ...] = (
    "risk_on_liquidity_expansion",
    "risk_off_deleveraging",
    "rates_shock_duration_pressure",
    "dollar_squeeze",
    "credit_or_funding_stress",
    "term_premium_or_inflation_scare",
    "goldilocks_soft_landing",
    "nacho_mega_cap_defensive_rotation",
    "china_policy_divergence",
    "data_insufficient",
)

_PILLAR_ALIASES = {
    "risk": "risk_appetite",
    "risk_on": "risk_appetite",
    "equity": "risk_appetite",
    "equities": "risk_appetite",
    "spx": "risk_appetite",
    "rates": "rates_pressure",
    "yield": "rates_pressure",
    "yields": "rates_pressure",
    "treasury": "rates_pressure",
    "dollar": "dollar_pressure",
    "usd": "dollar_pressure",
    "dxy": "dollar_pressure",
    "vol": "volatility_stress",
    "volatility": "volatility_stress",
    "vix": "volatility_stress",
    "liquidity": "liquidity_impulse",
    "crypto": "crypto_risk_beta",
    "btc": "crypto_risk_beta",
    "eth": "crypto_risk_beta",
    "breadth": "breadth_health",
    "market_breadth": "breadth_health",
    "china": "china_risk_appetite",
    "cn": "china_risk_appetite",
    "hk": "china_risk_appetite",
    "rotation": "rotation_leadership",
    "leadership": "rotation_leadership",
    "small_caps": "rotation_leadership",
}

_SOURCE_TIER_WEIGHTS = {
    "official_public": 1.0,
    "exchange_public": 1.0,
    "exchange": 1.0,
    "broker_authorized": 0.95,
    "authorized": 0.95,
    "official_or_authorized": 0.9,
    "tier_1_configured": 0.9,
    "cache_snapshot": 0.72,
    "snapshot": 0.72,
    "public_proxy": 0.64,
    "unofficial_public_api": 0.52,
    "unofficial_proxy": 0.5,
    "third_party_free_api": 0.48,
    "static_fallback": 0.25,
    "fallback_static": 0.25,
    "public_web_fallback": 0.25,
    "synthetic": 0.15,
    "synthetic_fixture": 0.15,
    "delayed_fixture": 0.35,
    "malformed_fixture": 0.0,
    "disabled_live_stub": 0.0,
    "unavailable": 0.0,
    "missing": 0.0,
}

_TRUST_WEIGHTS = {
    "high": 1.0,
    "active": 1.0,
    "reliable": 1.0,
    "verified": 1.0,
    "usable": 0.82,
    "usable_with_caution": 0.72,
    "medium": 0.68,
    "partial": 0.52,
    "degraded": 0.45,
    "weak": 0.3,
    "unavailable": 0.0,
    "rejected": 0.0,
    "unknown": 0.55,
}

_FRESHNESS_WEIGHTS = {
    "live": 1.0,
    "fresh": 1.0,
    "cached": 0.84,
    "delayed": 0.75,
    "partial": 0.6,
    "stale": 0.35,
    "fallback": 0.25,
    "mock": 0.15,
    "synthetic": 0.15,
    "unavailable": 0.0,
    "error": 0.0,
    "unknown": 0.55,
}

_NEGATIVE_DIRECTIONS = {
    "down",
    "falling",
    "lower",
    "negative",
    "weak",
    "weakening",
    "contracting",
    "risk_off",
    "risk-off",
    "bearish",
    "deteriorating",
}

_POSITIVE_DIRECTIONS = {
    "up",
    "rising",
    "higher",
    "positive",
    "strong",
    "strengthening",
    "expanding",
    "risk_on",
    "risk-on",
    "bullish",
    "improving",
}

_UNAVAILABLE_FRESHNESS = {"unavailable", "error"}
_REJECTED_REASON_MARKERS = (
    "source_authority_router_rejected",
    "authority_rejected",
    "provider_unavailable",
    "unavailable",
    "missing",
    "malformed",
)

_REGIME_RULES: dict[str, dict[str, float]] = {
    "risk_on_liquidity_expansion": {
        "risk_appetite": 1.0,
        "liquidity_impulse": 1.0,
        "crypto_risk_beta": 0.9,
        "breadth_health": 0.8,
        "volatility_stress": -0.9,
        "dollar_pressure": -0.8,
        "rates_pressure": -0.45,
    },
    "risk_off_deleveraging": {
        "risk_appetite": -1.1,
        "liquidity_impulse": -0.9,
        "crypto_risk_beta": -0.75,
        "breadth_health": -0.65,
        "volatility_stress": 1.0,
        "dollar_pressure": 0.7,
        "rates_pressure": 0.45,
    },
    "rates_shock_duration_pressure": {
        "rates_pressure": 1.2,
        "volatility_stress": 0.8,
        "risk_appetite": -0.7,
        "crypto_risk_beta": -0.65,
        "dollar_pressure": 0.6,
    },
    "dollar_squeeze": {
        "dollar_pressure": 1.2,
        "liquidity_impulse": -0.75,
        "crypto_risk_beta": -0.8,
        "risk_appetite": -0.65,
        "breadth_health": -0.45,
    },
    "credit_or_funding_stress": {
        "volatility_stress": 1.0,
        "liquidity_impulse": -1.0,
        "risk_appetite": -0.8,
        "dollar_pressure": 0.55,
        "crypto_risk_beta": -0.45,
    },
    "term_premium_or_inflation_scare": {
        "rates_pressure": 1.15,
        "dollar_pressure": 0.55,
        "risk_appetite": 0.35,
        "volatility_stress": 0.35,
        "liquidity_impulse": -0.35,
    },
    "goldilocks_soft_landing": {
        "risk_appetite": 1.0,
        "breadth_health": 0.9,
        "liquidity_impulse": 0.65,
        "rates_pressure": -0.65,
        "dollar_pressure": -0.55,
        "volatility_stress": -0.75,
    },
    "nacho_mega_cap_defensive_rotation": {
        "risk_appetite": 0.8,
        "breadth_health": -1.1,
        "rotation_leadership": -1.0,
        "volatility_stress": 0.25,
        "crypto_risk_beta": -0.25,
    },
    "china_policy_divergence": {
        "china_risk_appetite": 1.2,
        "risk_appetite": -0.65,
        "volatility_stress": 0.45,
        "dollar_pressure": 0.35,
        "breadth_health": -0.35,
    },
}


@dataclass(frozen=True, slots=True)
class MarketRegimeEvidenceItem:
    key: str
    label: str
    category: str | None = None
    pillar: str | None = None
    value: float | str | None = None
    change: float | None = None
    z_score: float | None = None
    percentile: float | None = None
    direction: str | None = None
    source: str = ""
    source_tier: str = ""
    trust_level: str = "unknown"
    freshness: str = "unknown"
    observation_only: bool = False
    score_contribution_allowed: bool = True
    as_of: str | None = None
    updated_at: str | None = None
    degradation_reason: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MarketRegimeEvidenceItem":
        return cls(
            key=_text(_get(value, "key")),
            label=_text(_get(value, "label")),
            category=_optional_text(_get(value, "category")),
            pillar=_optional_text(_get(value, "pillar")),
            value=_get(value, "value"),
            change=_optional_float(_get(value, "change")),
            z_score=_optional_float(_get(value, "z_score", "zScore")),
            percentile=_optional_float(_get(value, "percentile")),
            direction=_optional_text(_get(value, "direction")),
            source=_text(_get(value, "source")),
            source_tier=_text(_get(value, "source_tier", "sourceTier")),
            trust_level=_text(_get(value, "trust_level", "trustLevel")) or "unknown",
            freshness=_text(_get(value, "freshness")) or "unknown",
            observation_only=_bool(_get(value, "observation_only", "observationOnly")),
            score_contribution_allowed=_bool(
                _get(value, "score_contribution_allowed", "scoreContributionAllowed", default=True)
            ),
            as_of=_optional_text(_get(value, "as_of", "asOf")),
            updated_at=_optional_text(_get(value, "updated_at", "updatedAt")),
            degradation_reason=_optional_text(_get(value, "degradation_reason", "degradationReason")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "category": self.category,
            "pillar": self.pillar,
            "value": self.value,
            "change": self.change,
            "zScore": self.z_score,
            "percentile": self.percentile,
            "direction": self.direction,
            "source": self.source,
            "sourceTier": self.source_tier,
            "trustLevel": self.trust_level,
            "freshness": self.freshness,
            "observationOnly": self.observation_only,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "asOf": self.as_of,
            "updatedAt": self.updated_at,
            "degradationReason": self.degradation_reason,
        }


@dataclass(frozen=True, slots=True)
class MarketRegimeSynthesisResult:
    primary_regime: str
    secondary_regimes: tuple[str, ...]
    regime_scores: dict[str, float]
    confidence: float
    confidence_label: str
    liquidity_impulse: float
    risk_appetite: float
    rates_pressure: float
    dollar_pressure: float
    volatility_stress: float
    crypto_risk_beta: float
    breadth_health: float
    china_risk_appetite: float
    rotation_quality: float
    top_drivers: tuple[dict[str, Any], ...]
    counter_evidence: tuple[dict[str, Any], ...]
    data_gaps: tuple[dict[str, Any], ...]
    narrative_bullets: tuple[str, ...]
    evidence_quality: dict[str, Any]
    not_investment_advice: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "primaryRegime": self.primary_regime,
            "secondaryRegimes": list(self.secondary_regimes),
            "regimeScores": dict(self.regime_scores),
            "confidence": self.confidence,
            "confidenceLabel": self.confidence_label,
            "liquidityImpulse": self.liquidity_impulse,
            "riskAppetite": self.risk_appetite,
            "ratesPressure": self.rates_pressure,
            "dollarPressure": self.dollar_pressure,
            "volatilityStress": self.volatility_stress,
            "cryptoRiskBeta": self.crypto_risk_beta,
            "breadthHealth": self.breadth_health,
            "chinaRiskAppetite": self.china_risk_appetite,
            "rotationQuality": self.rotation_quality,
            "topDrivers": [dict(item) for item in self.top_drivers],
            "counterEvidence": [dict(item) for item in self.counter_evidence],
            "dataGaps": [dict(item) for item in self.data_gaps],
            "narrativeBullets": list(self.narrative_bullets),
            "evidenceQuality": dict(self.evidence_quality),
            "notInvestmentAdvice": self.not_investment_advice,
        }


@dataclass(frozen=True, slots=True)
class _ScoredEvidence:
    item: MarketRegimeEvidenceItem
    pillar: str
    signal: float
    weight: float
    impact: float
    discount_reasons: tuple[str, ...]


class MarketRegimeSynthesisService:
    """Deterministic regime classifier for already-normalized evidence."""

    min_scoring_pillars = 3
    min_scoring_weight = 0.45

    def synthesize(
        self,
        evidence_items: Iterable[MarketRegimeEvidenceItem | Mapping[str, Any]],
    ) -> MarketRegimeSynthesisResult:
        evidence = tuple(_coerce_evidence_item(item) for item in evidence_items)
        scored, data_gaps = self._score_evidence(evidence)
        pillar_scores = self._pillar_scores(scored)
        regime_scores, interactions = self._regime_scores(pillar_scores)
        evidence_quality = self._evidence_quality(evidence, scored, data_gaps, pillar_scores)

        primary_regime = self._primary_regime(regime_scores, evidence_quality)
        if primary_regime == "data_insufficient":
            secondary_regimes: tuple[str, ...] = ()
        else:
            secondary_regimes = tuple(
                regime
                for regime, score in sorted(regime_scores.items(), key=lambda item: item[1], reverse=True)
                if regime not in {primary_regime, "data_insufficient"} and score >= 0.35
            )[:3]

        counter_evidence = self._counter_evidence(primary_regime, scored, pillar_scores)
        confidence = self._confidence(primary_regime, regime_scores, evidence_quality, counter_evidence)
        confidence_label = self._confidence_label(confidence, primary_regime)
        top_drivers = self._top_drivers(scored)
        narrative_bullets = self._narrative_bullets(
            primary_regime,
            secondary_regimes,
            pillar_scores,
            top_drivers,
            counter_evidence,
            data_gaps,
            evidence_quality,
            interactions,
            confidence_label,
        )

        return MarketRegimeSynthesisResult(
            primary_regime=primary_regime,
            secondary_regimes=secondary_regimes,
            regime_scores={key: round(regime_scores.get(key, 0.0), 3) for key in REGIME_CANDIDATES},
            confidence=round(confidence, 3),
            confidence_label=confidence_label,
            liquidity_impulse=round(pillar_scores["liquidity_impulse"], 3),
            risk_appetite=round(pillar_scores["risk_appetite"], 3),
            rates_pressure=round(pillar_scores["rates_pressure"], 3),
            dollar_pressure=round(pillar_scores["dollar_pressure"], 3),
            volatility_stress=round(pillar_scores["volatility_stress"], 3),
            crypto_risk_beta=round(pillar_scores["crypto_risk_beta"], 3),
            breadth_health=round(pillar_scores["breadth_health"], 3),
            china_risk_appetite=round(pillar_scores["china_risk_appetite"], 3),
            rotation_quality=round(pillar_scores["rotation_leadership"], 3),
            top_drivers=top_drivers,
            counter_evidence=counter_evidence,
            data_gaps=tuple(data_gaps),
            narrative_bullets=narrative_bullets,
            evidence_quality=evidence_quality,
        )

    def _score_evidence(
        self,
        evidence: Sequence[MarketRegimeEvidenceItem],
    ) -> tuple[tuple[_ScoredEvidence, ...], list[dict[str, Any]]]:
        scored: list[_ScoredEvidence] = []
        data_gaps: list[dict[str, Any]] = []

        for item in evidence:
            pillar = _normalize_pillar(item.pillar or item.category)
            if pillar is None:
                data_gaps.append(_data_gap(item, "unknown_pillar"))
                continue

            signal = _signal_strength(item)
            if signal is None:
                data_gaps.append(_data_gap(item, "missing_direction_or_magnitude", pillar=pillar))
                continue

            weight, discount_reasons = _quality_weight(item)
            if weight <= 0.0:
                data_gaps.append(_data_gap(item, discount_reasons[0] if discount_reasons else "unscorable", pillar=pillar))
                continue

            scored.append(
                _ScoredEvidence(
                    item=item,
                    pillar=pillar,
                    signal=signal,
                    weight=weight,
                    impact=signal * weight,
                    discount_reasons=discount_reasons,
                )
            )

        covered = {item.pillar for item in scored if abs(item.signal) >= 0.05}
        for pillar in PILLARS:
            if pillar not in covered:
                data_gaps.append(
                    {
                        "key": f"missing:{pillar}",
                        "label": f"Missing scoring evidence for {pillar}",
                        "pillar": pillar,
                        "reason": "missing_scoring_evidence",
                    }
                )

        return tuple(scored), data_gaps

    @staticmethod
    def _pillar_scores(scored: Sequence[_ScoredEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {pillar: 0.0 for pillar in PILLARS}
        weights: dict[str, float] = {pillar: 0.0 for pillar in PILLARS}
        for item in scored:
            scores[item.pillar] += item.signal * item.weight
            weights[item.pillar] += item.weight
        for pillar, weight in weights.items():
            if weight > 0.0:
                scores[pillar] = _clamp(scores[pillar] / weight, -1.0, 1.0)
        return scores

    @staticmethod
    def _regime_scores(pillar_scores: Mapping[str, float]) -> tuple[dict[str, float], tuple[str, ...]]:
        scores: dict[str, float] = {}
        for regime, rules in _REGIME_RULES.items():
            scores[regime] = _score_regime(rules, pillar_scores)

        interactions: list[str] = []
        if (
            pillar_scores["rates_pressure"] > 0.25
            and pillar_scores["crypto_risk_beta"] < -0.25
            and pillar_scores["dollar_pressure"] > 0.25
        ):
            scores["rates_shock_duration_pressure"] += 0.18
            scores["dollar_squeeze"] += 0.25
            interactions.append("rates_up_crypto_down_dollar_up")

        if (
            pillar_scores["rates_pressure"] > 0.25
            and pillar_scores["risk_appetite"] < -0.25
            and pillar_scores["volatility_stress"] > 0.25
        ):
            scores["rates_shock_duration_pressure"] += 0.14
            scores["risk_off_deleveraging"] += 0.12
            interactions.append("rates_up_equities_down_volatility_up")

        if (
            pillar_scores["risk_appetite"] > 0.2
            and pillar_scores["breadth_health"] < -0.2
            and pillar_scores["rotation_leadership"] < -0.2
        ):
            scores["nacho_mega_cap_defensive_rotation"] += 0.24
            interactions.append("large_cap_up_breadth_small_caps_weak")

        if (
            pillar_scores["crypto_risk_beta"] > 0.25
            and pillar_scores["dollar_pressure"] < -0.25
            and pillar_scores["volatility_stress"] < -0.25
        ):
            scores["risk_on_liquidity_expansion"] += 0.18
            interactions.append("crypto_up_dollar_down_volatility_down")

        if (
            pillar_scores["china_risk_appetite"] > 0.25
            and (
                pillar_scores["risk_appetite"] < -0.15
                or pillar_scores["volatility_stress"] > 0.2
                or pillar_scores["dollar_pressure"] > 0.2
            )
        ):
            scores["china_policy_divergence"] += 0.22
            interactions.append("china_up_global_risk_weak")

        for key in list(scores):
            scores[key] = round(_clamp(scores[key], 0.0, 1.0), 4)
        scores["data_insufficient"] = 0.0
        return scores, tuple(interactions)

    @staticmethod
    def _primary_regime(regime_scores: Mapping[str, float], evidence_quality: Mapping[str, Any]) -> str:
        if (
            int(evidence_quality["scoringPillarCount"]) < MarketRegimeSynthesisService.min_scoring_pillars
            or float(evidence_quality["scoreContributingWeight"]) < MarketRegimeSynthesisService.min_scoring_weight
        ):
            return "data_insufficient"
        ranked = sorted(
            ((regime, score) for regime, score in regime_scores.items() if regime != "data_insufficient"),
            key=lambda item: item[1],
            reverse=True,
        )
        if not ranked or ranked[0][1] < 0.34:
            return "data_insufficient"
        return ranked[0][0]

    @staticmethod
    def _evidence_quality(
        evidence: Sequence[MarketRegimeEvidenceItem],
        scored: Sequence[_ScoredEvidence],
        data_gaps: Sequence[Mapping[str, Any]],
        pillar_scores: Mapping[str, float],
    ) -> dict[str, Any]:
        covered = tuple(pillar for pillar in PILLARS if abs(pillar_scores[pillar]) >= 0.05)
        missing = tuple(pillar for pillar in PILLARS if pillar not in covered)
        total_weight = sum(item.weight for item in scored)
        average_weight = total_weight / len(scored) if scored else 0.0
        discounted_count = sum(1 for item in scored if item.discount_reasons)
        observation_only_count = sum(1 for item in evidence if item.observation_only)
        score_blocked_count = sum(1 for item in evidence if not item.score_contribution_allowed)
        conflict_penalty = _cross_pillar_conflict_penalty(pillar_scores)
        return {
            "version": MARKET_REGIME_SYNTHESIS_VERSION,
            "inputCount": len(evidence),
            "scoringEvidenceCount": len(scored),
            "scoringPillarCount": len(covered),
            "coveredPillars": list(covered),
            "missingPillars": list(missing),
            "coverageRatio": round(len(covered) / len(PILLARS), 3),
            "scoreContributingWeight": round(total_weight, 3),
            "averageEvidenceWeight": round(average_weight, 3),
            "discountedEvidenceCount": discounted_count,
            "observationOnlyEvidenceCount": observation_only_count,
            "scoreBlockedEvidenceCount": score_blocked_count,
            "dataGapCount": len(data_gaps),
            "conflictPenalty": round(conflict_penalty, 3),
        }

    @staticmethod
    def _top_drivers(scored: Sequence[_ScoredEvidence]) -> tuple[dict[str, Any], ...]:
        drivers = []
        for item in sorted(scored, key=lambda value: abs(value.impact), reverse=True)[:6]:
            drivers.append(
                {
                    "key": item.item.key,
                    "label": item.item.label,
                    "pillar": item.pillar,
                    "direction": "positive" if item.signal > 0 else "negative",
                    "signal": round(item.signal, 3),
                    "weight": round(item.weight, 3),
                    "impact": round(item.impact, 3),
                    "source": item.item.source,
                    "sourceTier": item.item.source_tier,
                    "trustLevel": item.item.trust_level,
                    "freshness": item.item.freshness,
                    "observationOnly": item.item.observation_only,
                    "scoreContributionAllowed": item.item.score_contribution_allowed,
                    "discountReasons": list(item.discount_reasons),
                }
            )
        return tuple(drivers)

    @staticmethod
    def _counter_evidence(
        primary_regime: str,
        scored: Sequence[_ScoredEvidence],
        pillar_scores: Mapping[str, float],
    ) -> tuple[dict[str, Any], ...]:
        if primary_regime not in _REGIME_RULES:
            return ()
        expected = _REGIME_RULES[primary_regime]
        counters: list[dict[str, Any]] = []
        for pillar, expected_sign in expected.items():
            pillar_score = pillar_scores.get(pillar, 0.0)
            if abs(pillar_score) < 0.05 or expected_sign * pillar_score >= 0:
                continue
            driver = max(
                (item for item in scored if item.pillar == pillar),
                key=lambda item: abs(item.impact),
                default=None,
            )
            counters.append(
                {
                    "key": driver.item.key if driver else f"pillar:{pillar}",
                    "label": driver.item.label if driver else pillar,
                    "pillar": pillar,
                    "signal": round(pillar_score, 3),
                    "expectedDirection": "positive" if expected_sign > 0 else "negative",
                    "reason": "conflicts_with_primary_regime",
                }
            )
        counters.extend(_structural_counter_evidence(scored, pillar_scores))
        return tuple(counters[:5])

    @staticmethod
    def _confidence(
        primary_regime: str,
        regime_scores: Mapping[str, float],
        evidence_quality: Mapping[str, Any],
        counter_evidence: Sequence[Mapping[str, Any]],
    ) -> float:
        if primary_regime == "data_insufficient":
            return _clamp(0.12 + float(evidence_quality["scoreContributingWeight"]) * 0.18, 0.05, 0.35)

        ranked = sorted(
            (score for regime, score in regime_scores.items() if regime != "data_insufficient"),
            reverse=True,
        )
        top = ranked[0] if ranked else 0.0
        second = ranked[1] if len(ranked) > 1 else 0.0
        separation = max(0.0, top - second)
        coverage = float(evidence_quality["coverageRatio"])
        average_weight = float(evidence_quality["averageEvidenceWeight"])
        conflict_penalty = float(evidence_quality["conflictPenalty"]) + (0.08 * len(counter_evidence))
        discount_penalty = min(0.18, 0.03 * int(evidence_quality["discountedEvidenceCount"]))
        score = (
            0.16
            + top * 0.33
            + coverage * 0.24
            + average_weight * 0.27
            + separation * 0.18
            - conflict_penalty * 0.26
            - discount_penalty
        )
        return _clamp(score, 0.05, 0.92)

    @staticmethod
    def _confidence_label(confidence: float, primary_regime: str) -> str:
        if primary_regime == "data_insufficient" or confidence < 0.35:
            return "insufficient"
        if confidence < 0.55:
            return "low"
        if confidence < 0.74:
            return "medium"
        return "high"

    @staticmethod
    def _narrative_bullets(
        primary_regime: str,
        secondary_regimes: Sequence[str],
        pillar_scores: Mapping[str, float],
        top_drivers: Sequence[Mapping[str, Any]],
        counter_evidence: Sequence[Mapping[str, Any]],
        data_gaps: Sequence[Mapping[str, Any]],
        evidence_quality: Mapping[str, Any],
        interactions: Sequence[str],
        confidence_label: str,
    ) -> tuple[str, ...]:
        if primary_regime == "data_insufficient":
            return (
                "Market regime synthesis is unavailable because score-contributing evidence coverage is below threshold.",
                f"Covered pillars: {evidence_quality['scoringPillarCount']} of {len(PILLARS)}.",
                "Unavailable, rejected, stale, fallback, proxy, and observation-only inputs were not promoted into strong conclusions.",
            )

        strongest_pillars = sorted(PILLARS, key=lambda pillar: abs(pillar_scores[pillar]), reverse=True)[:3]
        bullets = [
            f"Primary regime is {primary_regime} with {confidence_label} confidence.",
            "Strongest pillars: "
            + ", ".join(f"{pillar}={pillar_scores[pillar]:+.2f}" for pillar in strongest_pillars),
        ]

        if secondary_regimes:
            bullets.append("Secondary regimes to monitor: " + ", ".join(secondary_regimes[:2]) + ".")
        if interactions:
            bullets.append("Rule interactions active: " + ", ".join(interactions[:2]) + ".")
        if top_drivers:
            driver_labels = ", ".join(str(item["label"]) for item in top_drivers[:3])
            bullets.append(f"Top evidence drivers: {driver_labels}.")
        if primary_regime == "nacho_mega_cap_defensive_rotation":
            bullets.append(
                "Leadership quality is narrow: index strength is not confirmed by breadth or small-cap participation."
            )
        if counter_evidence:
            bullets.append("Counter-evidence is present, so confidence is discounted.")
        if data_gaps:
            bullets.append("Data gaps remain explicit and are not filled with synthetic availability.")
        if evidence_quality["observationOnlyEvidenceCount"] or evidence_quality["scoreBlockedEvidenceCount"]:
            bullets.append("Observation-only or score-blocked evidence was discounted before classification.")
        return tuple(bullets)


def synthesize_market_regime(
    evidence_items: Iterable[MarketRegimeEvidenceItem | Mapping[str, Any]],
) -> MarketRegimeSynthesisResult:
    return MarketRegimeSynthesisService().synthesize(evidence_items)


def _coerce_evidence_item(value: MarketRegimeEvidenceItem | Mapping[str, Any]) -> MarketRegimeEvidenceItem:
    if isinstance(value, MarketRegimeEvidenceItem):
        return value
    return MarketRegimeEvidenceItem.from_dict(value)


def _score_regime(rules: Mapping[str, float], pillar_scores: Mapping[str, float]) -> float:
    present = [(pillar, weight) for pillar, weight in rules.items() if abs(pillar_scores.get(pillar, 0.0)) >= 0.05]
    if not present:
        return 0.0

    denominator = sum(abs(weight) for _, weight in present)
    positive = 0.0
    conflict = 0.0
    for pillar, expected_weight in present:
        expected_sign = 1.0 if expected_weight > 0 else -1.0
        alignment = expected_sign * pillar_scores.get(pillar, 0.0)
        if alignment >= 0:
            positive += alignment * abs(expected_weight)
        else:
            conflict += abs(alignment) * abs(expected_weight)
    raw_score = (positive - conflict * 0.55) / denominator
    coverage_factor = min(1.0, len(present) / 3.0)
    return _clamp(raw_score * coverage_factor, 0.0, 1.0)


def _quality_weight(item: MarketRegimeEvidenceItem) -> tuple[float, tuple[str, ...]]:
    reasons: list[str] = []
    freshness = _normal(item.freshness) or "unknown"
    degradation_reason = _normal(item.degradation_reason)
    if freshness in _UNAVAILABLE_FRESHNESS:
        return 0.0, ("freshness_unavailable",)
    if any(marker in degradation_reason for marker in _REJECTED_REASON_MARKERS):
        return 0.0, ("degradation_unavailable_or_rejected",)
    if not item.score_contribution_allowed:
        return 0.0, ("score_contribution_not_allowed",)

    source_tier = _normal(item.source_tier or item.source) or "unknown"
    trust_level = _normal(item.trust_level) or "unknown"

    source_weight = _lookup_weight(source_tier, _SOURCE_TIER_WEIGHTS, default=0.6)
    trust_weight = _lookup_weight(trust_level, _TRUST_WEIGHTS, default=0.55)
    freshness_weight = _lookup_weight(freshness, _FRESHNESS_WEIGHTS, default=0.55)

    if source_weight < 0.7:
        reasons.append("source_tier_discount")
    if trust_weight < 0.7:
        reasons.append("trust_discount")
    if freshness_weight < 0.8:
        reasons.append("freshness_discount")

    weight = source_weight * trust_weight * freshness_weight
    if item.observation_only:
        weight *= 0.35
        reasons.append("observation_only_discount")

    if weight <= 0.0:
        return 0.0, tuple(reasons or ("unscorable_quality",))
    return round(_clamp(weight, 0.0, 1.0), 4), tuple(reasons)


def _signal_strength(item: MarketRegimeEvidenceItem) -> float | None:
    direction = _direction_sign(item.direction)
    raw_value: float | None = None
    if item.z_score is not None:
        raw_value = _clamp(float(item.z_score) / 2.0, -1.0, 1.0)
    elif item.percentile is not None:
        raw_value = _clamp((float(item.percentile) - 50.0) / 50.0, -1.0, 1.0)
    elif item.change is not None:
        raw_value = _clamp(float(item.change) / 3.0, -1.0, 1.0)
    elif item.value is not None:
        raw_value = _optional_float(item.value)
        if raw_value is not None:
            raw_value = _clamp(raw_value, -1.0, 1.0)

    if raw_value is None and direction is None:
        return None
    magnitude = abs(raw_value) if raw_value is not None else 0.65
    sign = direction if direction is not None else (1.0 if float(raw_value or 0.0) >= 0.0 else -1.0)
    return round(_clamp(sign * max(0.05, magnitude), -1.0, 1.0), 4)


def _direction_sign(value: str | None) -> float | None:
    normalized = _normal(value)
    if normalized in _POSITIVE_DIRECTIONS:
        return 1.0
    if normalized in _NEGATIVE_DIRECTIONS:
        return -1.0
    return None


def _normalize_pillar(value: str | None) -> str | None:
    normalized = _normal(value)
    if not normalized:
        return None
    if normalized in PILLARS:
        return normalized
    return _PILLAR_ALIASES.get(normalized)


def _cross_pillar_conflict_penalty(pillar_scores: Mapping[str, float]) -> float:
    conflict_pairs = (
        ("risk_appetite", "volatility_stress", -1.0),
        ("risk_appetite", "dollar_pressure", -1.0),
        ("crypto_risk_beta", "dollar_pressure", -1.0),
        ("risk_appetite", "breadth_health", 1.0),
        ("liquidity_impulse", "rates_pressure", -1.0),
    )
    conflicts = 0.0
    possible = 0
    for left, right, expected_relation in conflict_pairs:
        left_score = pillar_scores.get(left, 0.0)
        right_score = pillar_scores.get(right, 0.0)
        if abs(left_score) < 0.12 or abs(right_score) < 0.12:
            continue
        possible += 1
        if expected_relation * left_score * right_score < 0:
            conflicts += min(abs(left_score), abs(right_score))
    if possible == 0:
        return 0.0
    return _clamp(conflicts / possible, 0.0, 1.0)


def _structural_counter_evidence(
    scored: Sequence[_ScoredEvidence],
    pillar_scores: Mapping[str, float],
) -> list[dict[str, Any]]:
    conflict_pairs = (
        ("risk_appetite", "volatility_stress", -1.0, "risk_appetite_conflicts_with_volatility_stress"),
        ("crypto_risk_beta", "volatility_stress", -1.0, "crypto_beta_conflicts_with_volatility_stress"),
        ("crypto_risk_beta", "dollar_pressure", -1.0, "crypto_beta_conflicts_with_dollar_pressure"),
        ("risk_appetite", "breadth_health", 1.0, "index_direction_conflicts_with_breadth"),
        ("liquidity_impulse", "rates_pressure", -1.0, "liquidity_impulse_conflicts_with_rates_pressure"),
    )
    counters: list[dict[str, Any]] = []
    seen: set[str] = set()
    for left, right, expected_relation, reason in conflict_pairs:
        left_score = pillar_scores.get(left, 0.0)
        right_score = pillar_scores.get(right, 0.0)
        if abs(left_score) < 0.12 or abs(right_score) < 0.12:
            continue
        if expected_relation * left_score * right_score >= 0:
            continue
        for pillar, score in ((left, left_score), (right, right_score)):
            if pillar in seen:
                continue
            driver = max(
                (item for item in scored if item.pillar == pillar),
                key=lambda item: abs(item.impact),
                default=None,
            )
            counters.append(
                {
                    "key": driver.item.key if driver else f"pillar:{pillar}",
                    "label": driver.item.label if driver else pillar,
                    "pillar": pillar,
                    "signal": round(score, 3),
                    "expectedDirection": "opposite_pair" if expected_relation < 0 else "same_pair",
                    "reason": reason,
                }
            )
            seen.add(pillar)
    return counters


def _data_gap(item: MarketRegimeEvidenceItem, reason: str, *, pillar: str | None = None) -> dict[str, Any]:
    return {
        "key": item.key,
        "label": item.label,
        "pillar": pillar or _normalize_pillar(item.pillar or item.category),
        "reason": reason,
        "source": item.source,
        "sourceTier": item.source_tier,
        "trustLevel": item.trust_level,
        "freshness": item.freshness,
        "observationOnly": item.observation_only,
        "scoreContributionAllowed": item.score_contribution_allowed,
        "degradationReason": item.degradation_reason,
    }


def _lookup_weight(value: str, weights: Mapping[str, float], *, default: float) -> float:
    if value in weights:
        return weights[value]
    for key, weight in weights.items():
        if key and key in value:
            return weight
    return default


def _get(value: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in value:
            return value[name]
    return default


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _normal(value: Any) -> str:
    return _text(value).lower().replace("-", "_").replace(" ", "_")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
