# -*- coding: utf-8 -*-
"""Pure liquidity impulse synthesis from caller-supplied normalized evidence.

This module is intentionally inert: it does not import provider clients, read
configuration, call networks, mutate caches, or wire the result into runtime
Liquidity Monitor surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


LIQUIDITY_IMPULSE_SYNTHESIS_VERSION = "liquidity_impulse_synthesis_v1"

PILLARS: tuple[str, ...] = (
    "dollar_pressure",
    "rates_pressure",
    "volatility_stress",
    "crypto_liquidity_beta",
    "risk_asset_demand",
    "funding_stress",
    "equity_flow_proxy",
    "breadth_confirmation",
    "china_liquidity_context",
)

LIQUIDITY_IMPULSE_CLASSIFICATIONS: tuple[str, ...] = (
    "expanding_liquidity",
    "contracting_liquidity",
    "rates_driven_tightening",
    "dollar_squeeze",
    "risk_deleveraging",
    "crypto_beta_expansion",
    "mixed_or_transition",
    "data_insufficient",
)

_PILLAR_ALIASES = {
    "dollar": "dollar_pressure",
    "dxy": "dollar_pressure",
    "usd": "dollar_pressure",
    "fx": "dollar_pressure",
    "rates": "rates_pressure",
    "yield": "rates_pressure",
    "yields": "rates_pressure",
    "treasury": "rates_pressure",
    "vol": "volatility_stress",
    "volatility": "volatility_stress",
    "vix": "volatility_stress",
    "crypto": "crypto_liquidity_beta",
    "btc": "crypto_liquidity_beta",
    "eth": "crypto_liquidity_beta",
    "risk": "risk_asset_demand",
    "equity": "risk_asset_demand",
    "equities": "risk_asset_demand",
    "flows": "equity_flow_proxy",
    "flow": "equity_flow_proxy",
    "breadth": "breadth_confirmation",
    "market_breadth": "breadth_confirmation",
    "funding": "funding_stress",
    "china": "china_liquidity_context",
    "cn": "china_liquidity_context",
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
    "tighter",
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
    "easing",
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

_PILLAR_EXPANSION_SIGN = {
    "dollar_pressure": -1.0,
    "rates_pressure": -1.0,
    "volatility_stress": -1.0,
    "crypto_liquidity_beta": 1.0,
    "risk_asset_demand": 1.0,
    "funding_stress": -1.0,
    "equity_flow_proxy": 1.0,
    "breadth_confirmation": 1.0,
    "china_liquidity_context": 1.0,
}

_SUBTYPE_RULES: dict[str, dict[str, float]] = {
    "rates_driven_tightening": {
        "rates_pressure": 1.2,
        "dollar_pressure": 0.8,
        "funding_stress": 0.6,
        "volatility_stress": 0.35,
        "crypto_liquidity_beta": -0.7,
        "risk_asset_demand": -0.55,
        "equity_flow_proxy": -0.45,
        "breadth_confirmation": -0.35,
    },
    "dollar_squeeze": {
        "dollar_pressure": 1.2,
        "funding_stress": 0.85,
        "crypto_liquidity_beta": -0.8,
        "risk_asset_demand": -0.5,
        "rates_pressure": 0.35,
        "volatility_stress": 0.35,
        "equity_flow_proxy": -0.35,
    },
    "risk_deleveraging": {
        "volatility_stress": 1.2,
        "crypto_liquidity_beta": -0.85,
        "risk_asset_demand": -0.9,
        "breadth_confirmation": -0.7,
        "equity_flow_proxy": -0.65,
        "funding_stress": 0.45,
        "dollar_pressure": 0.25,
    },
    "crypto_beta_expansion": {
        "crypto_liquidity_beta": 1.15,
        "dollar_pressure": -0.85,
        "volatility_stress": -0.8,
        "risk_asset_demand": 0.55,
        "equity_flow_proxy": 0.45,
        "breadth_confirmation": 0.35,
        "rates_pressure": -0.25,
    },
}

_LABELS = {
    "expanding_liquidity": "Liquidity appears to be expanding",
    "contracting_liquidity": "Liquidity appears to be contracting",
    "rates_driven_tightening": "Rates-driven tightening",
    "dollar_squeeze": "Dollar-driven squeeze",
    "risk_deleveraging": "Risk deleveraging",
    "crypto_beta_expansion": "Crypto beta expansion",
    "mixed_or_transition": "Mixed or transition regime",
    "data_insufficient": "Data insufficient for a reliable liquidity call",
}


@dataclass(frozen=True, slots=True)
class LiquidityImpulseEvidenceItem:
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
    included_in_score: bool | None = None
    proxy_only: bool = False
    as_of: str | None = None
    updated_at: str | None = None
    degradation_reason: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LiquidityImpulseEvidenceItem":
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
            included_in_score=_optional_bool(_get(value, "included_in_score", "includedInScore")),
            proxy_only=_bool(_get(value, "proxy_only", "proxyOnly")),
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
            "includedInScore": self.included_in_score,
            "proxyOnly": self.proxy_only,
            "asOf": self.as_of,
            "updatedAt": self.updated_at,
            "degradationReason": self.degradation_reason,
        }


@dataclass(frozen=True, slots=True)
class LiquidityImpulseSynthesisResult:
    liquidity_impulse: str
    impulse_label: str
    subtype: str
    confidence: float
    confidence_label: str
    pillar_scores: dict[str, float]
    direction_score: float
    dominant_drivers: tuple[dict[str, Any], ...]
    counter_evidence: tuple[dict[str, Any], ...]
    data_gaps: tuple[dict[str, Any], ...]
    narrative_bullets: tuple[str, ...]
    evidence_quality: dict[str, Any]
    not_investment_advice: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "liquidityImpulse": self.liquidity_impulse,
            "impulseLabel": self.impulse_label,
            "subtype": self.subtype,
            "confidence": self.confidence,
            "confidenceLabel": self.confidence_label,
            "pillarScores": dict(self.pillar_scores),
            "directionScore": self.direction_score,
            "dominantDrivers": [dict(item) for item in self.dominant_drivers],
            "counterEvidence": [dict(item) for item in self.counter_evidence],
            "dataGaps": [dict(item) for item in self.data_gaps],
            "narrativeBullets": list(self.narrative_bullets),
            "evidenceQuality": dict(self.evidence_quality),
            "notInvestmentAdvice": self.not_investment_advice,
        }


@dataclass(frozen=True, slots=True)
class _ScoredEvidence:
    item: LiquidityImpulseEvidenceItem
    pillar: str
    signal: float
    weight: float
    raw_impact: float
    oriented_impact: float
    discount_reasons: tuple[str, ...]


class LiquidityImpulseSynthesisService:
    """Deterministic liquidity impulse classifier for normalized evidence."""

    min_scoring_pillars = 3
    min_scoring_weight = 0.45

    def synthesize(
        self,
        evidence_items: Iterable[LiquidityImpulseEvidenceItem | Mapping[str, Any]],
    ) -> LiquidityImpulseSynthesisResult:
        evidence = tuple(_coerce_evidence_item(item) for item in evidence_items)
        scored, data_gaps = self._score_evidence(evidence)
        pillar_scores = self._pillar_scores(scored)
        direction_score = self._direction_score(scored)
        subtype_scores, interactions = self._subtype_scores(pillar_scores)
        evidence_quality = self._evidence_quality(evidence, scored, data_gaps, pillar_scores)
        liquidity_impulse = self._liquidity_impulse(direction_score, subtype_scores, evidence_quality)
        subtype = self._subtype(liquidity_impulse, direction_score, subtype_scores, evidence_quality)
        counter_evidence = self._counter_evidence(liquidity_impulse, subtype, scored, pillar_scores)
        confidence = self._confidence(
            liquidity_impulse,
            subtype,
            direction_score,
            subtype_scores,
            evidence_quality,
            counter_evidence,
        )
        confidence_label = self._confidence_label(confidence, liquidity_impulse)
        dominant_drivers = self._dominant_drivers(scored)
        narrative_bullets = self._narrative_bullets(
            liquidity_impulse,
            subtype,
            direction_score,
            pillar_scores,
            dominant_drivers,
            counter_evidence,
            data_gaps,
            evidence_quality,
            interactions,
            confidence_label,
        )

        return LiquidityImpulseSynthesisResult(
            liquidity_impulse=liquidity_impulse,
            impulse_label=_LABELS[liquidity_impulse],
            subtype=subtype,
            confidence=round(confidence, 3),
            confidence_label=confidence_label,
            pillar_scores={pillar: round(pillar_scores[pillar], 3) for pillar in PILLARS},
            direction_score=round(direction_score, 3),
            dominant_drivers=dominant_drivers,
            counter_evidence=counter_evidence,
            data_gaps=tuple(data_gaps),
            narrative_bullets=narrative_bullets,
            evidence_quality=evidence_quality,
        )

    def _score_evidence(
        self,
        evidence: Sequence[LiquidityImpulseEvidenceItem],
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

            raw_impact = signal * weight
            oriented_impact = raw_impact * _PILLAR_EXPANSION_SIGN[pillar]
            scored.append(
                _ScoredEvidence(
                    item=item,
                    pillar=pillar,
                    signal=signal,
                    weight=weight,
                    raw_impact=raw_impact,
                    oriented_impact=oriented_impact,
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
    def _direction_score(scored: Sequence[_ScoredEvidence]) -> float:
        if not scored:
            return 0.0
        total_weight = sum(item.weight for item in scored)
        if total_weight <= 0:
            return 0.0
        return _clamp(sum(item.oriented_impact for item in scored) / total_weight, -1.0, 1.0)

    @staticmethod
    def _subtype_scores(pillar_scores: Mapping[str, float]) -> tuple[dict[str, float], tuple[str, ...]]:
        scores = {name: _score_candidate(rules, pillar_scores) for name, rules in _SUBTYPE_RULES.items()}
        interactions: list[str] = []

        if (
            pillar_scores["rates_pressure"] > 0.25
            and pillar_scores["dollar_pressure"] > 0.2
            and pillar_scores["crypto_liquidity_beta"] < -0.2
        ):
            scores["rates_driven_tightening"] += 0.18
            scores["dollar_squeeze"] += 0.08
            interactions.append("rates_up_dollar_up_crypto_down")

        if (
            pillar_scores["volatility_stress"] > 0.25
            and pillar_scores["crypto_liquidity_beta"] < -0.2
            and pillar_scores["risk_asset_demand"] < -0.2
        ):
            scores["risk_deleveraging"] += 0.2
            interactions.append("volatility_up_crypto_down_equities_down")

        if (
            pillar_scores["crypto_liquidity_beta"] > 0.25
            and pillar_scores["dollar_pressure"] < -0.2
            and pillar_scores["volatility_stress"] < -0.2
        ):
            scores["crypto_beta_expansion"] += 0.18
            interactions.append("crypto_up_dollar_down_volatility_down")

        if pillar_scores["breadth_confirmation"] < -0.2 and pillar_scores["rates_pressure"] > 0.2:
            scores["rates_driven_tightening"] += 0.06
            scores["risk_deleveraging"] += 0.04
            interactions.append("breadth_weak_rates_up")

        for key, value in list(scores.items()):
            scores[key] = round(_clamp(value, 0.0, 1.0), 4)
        return scores, tuple(interactions)

    @staticmethod
    def _evidence_quality(
        evidence: Sequence[LiquidityImpulseEvidenceItem],
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
        score_blocked_count = sum(
            1
            for item in evidence
            if not item.score_contribution_allowed or item.included_in_score is False
        )
        proxy_only_scoring_count = sum(1 for item in scored if item.item.proxy_only)
        real_scoring_count = len(scored) - proxy_only_scoring_count
        conflict_penalty = _cross_pillar_conflict_penalty(pillar_scores)
        return {
            "version": LIQUIDITY_IMPULSE_SYNTHESIS_VERSION,
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
            "proxyOnlyScoringCount": proxy_only_scoring_count,
            "realScoringEvidenceCount": real_scoring_count,
            "allScoringEvidenceProxyOnly": bool(scored) and real_scoring_count == 0,
            "dataGapCount": len(data_gaps),
            "conflictPenalty": round(conflict_penalty, 3),
        }

    @staticmethod
    def _liquidity_impulse(
        direction_score: float,
        subtype_scores: Mapping[str, float],
        evidence_quality: Mapping[str, Any],
    ) -> str:
        top_subtype_score = max(subtype_scores.values(), default=0.0)
        ranked = sorted(subtype_scores.values(), reverse=True)
        second_score = ranked[1] if len(ranked) > 1 else 0.0

        if (
            int(evidence_quality["scoringPillarCount"]) < LiquidityImpulseSynthesisService.min_scoring_pillars
            or float(evidence_quality["scoreContributingWeight"]) < LiquidityImpulseSynthesisService.min_scoring_weight
            or int(evidence_quality["realScoringEvidenceCount"]) == 0
        ):
            return "data_insufficient"

        if float(evidence_quality["conflictPenalty"]) > 0.42:
            return "mixed_or_transition"
        if abs(direction_score) < 0.18:
            return "mixed_or_transition"
        if top_subtype_score < 0.3 and abs(direction_score) < 0.28:
            return "mixed_or_transition"
        if top_subtype_score - second_score < 0.05 and abs(direction_score) < 0.35:
            return "mixed_or_transition"
        if bool(evidence_quality["allScoringEvidenceProxyOnly"]):
            return "data_insufficient"
        if direction_score > 0:
            return "expanding_liquidity"
        return "contracting_liquidity"

    @staticmethod
    def _subtype(
        liquidity_impulse: str,
        direction_score: float,
        subtype_scores: Mapping[str, float],
        evidence_quality: Mapping[str, Any],
    ) -> str:
        if liquidity_impulse == "data_insufficient":
            return "data_insufficient"
        if liquidity_impulse == "mixed_or_transition":
            return "mixed_or_transition"

        ranked = sorted(subtype_scores.items(), key=lambda item: item[1], reverse=True)
        top_name, top_score = ranked[0] if ranked else ("mixed_or_transition", 0.0)
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0

        if liquidity_impulse == "expanding_liquidity":
            if top_name == "crypto_beta_expansion" and top_score >= 0.34:
                return top_name
            return "mixed_or_transition" if abs(direction_score) < 0.32 else "crypto_beta_expansion"

        if top_name == "crypto_beta_expansion":
            return "mixed_or_transition"
        if top_score < 0.32:
            return "mixed_or_transition"
        if top_score - second_score < 0.05 and float(evidence_quality["conflictPenalty"]) > 0.22:
            return "mixed_or_transition"
        return top_name

    @staticmethod
    def _dominant_drivers(scored: Sequence[_ScoredEvidence]) -> tuple[dict[str, Any], ...]:
        drivers = []
        for item in sorted(scored, key=lambda value: abs(value.oriented_impact), reverse=True)[:6]:
            drivers.append(
                {
                    "key": item.item.key,
                    "label": item.item.label,
                    "pillar": item.pillar,
                    "direction": "supports_expansion" if item.oriented_impact > 0 else "supports_contraction",
                    "signal": round(item.signal, 3),
                    "weight": round(item.weight, 3),
                    "impact": round(item.oriented_impact, 3),
                    "source": item.item.source,
                    "sourceTier": item.item.source_tier,
                    "trustLevel": item.item.trust_level,
                    "freshness": item.item.freshness,
                    "observationOnly": item.item.observation_only,
                    "scoreContributionAllowed": item.item.score_contribution_allowed,
                    "includedInScore": item.item.included_in_score,
                    "proxyOnly": item.item.proxy_only,
                    "discountReasons": list(item.discount_reasons),
                }
            )
        return tuple(drivers)

    @staticmethod
    def _counter_evidence(
        liquidity_impulse: str,
        subtype: str,
        scored: Sequence[_ScoredEvidence],
        pillar_scores: Mapping[str, float],
    ) -> tuple[dict[str, Any], ...]:
        expected = _expected_pillar_directions(liquidity_impulse, subtype)
        counters: list[dict[str, Any]] = []

        for pillar, expected_sign in expected.items():
            pillar_score = pillar_scores.get(pillar, 0.0)
            if abs(pillar_score) < 0.05 or expected_sign * pillar_score >= 0:
                continue
            driver = max(
                (item for item in scored if item.pillar == pillar),
                key=lambda item: abs(item.oriented_impact),
                default=None,
            )
            counters.append(
                {
                    "key": driver.item.key if driver else f"pillar:{pillar}",
                    "label": driver.item.label if driver else pillar,
                    "pillar": pillar,
                    "signal": round(pillar_score, 3),
                    "expectedDirection": "positive" if expected_sign > 0 else "negative",
                    "reason": "conflicts_with_primary_liquidity_call",
                }
            )

        counters.extend(_structural_counter_evidence(scored, pillar_scores))
        return tuple(counters[:5])

    @staticmethod
    def _confidence(
        liquidity_impulse: str,
        subtype: str,
        direction_score: float,
        subtype_scores: Mapping[str, float],
        evidence_quality: Mapping[str, Any],
        counter_evidence: Sequence[Mapping[str, Any]],
    ) -> float:
        if liquidity_impulse == "data_insufficient":
            return _clamp(0.1 + float(evidence_quality["scoreContributingWeight"]) * 0.18, 0.05, 0.35)

        ranked = sorted(subtype_scores.values(), reverse=True)
        top = ranked[0] if ranked else 0.0
        second = ranked[1] if len(ranked) > 1 else 0.0
        separation = max(0.0, top - second)
        coverage = float(evidence_quality["coverageRatio"])
        average_weight = float(evidence_quality["averageEvidenceWeight"])
        conflict_penalty = float(evidence_quality["conflictPenalty"]) + (0.06 * len(counter_evidence))
        discount_penalty = min(0.18, 0.03 * int(evidence_quality["discountedEvidenceCount"]))
        proxy_penalty = 0.08 * int(evidence_quality["proxyOnlyScoringCount"])
        mixed_penalty = 0.1 if liquidity_impulse == "mixed_or_transition" or subtype == "mixed_or_transition" else 0.0

        score = (
            0.16
            + abs(direction_score) * 0.24
            + top * 0.22
            + coverage * 0.2
            + average_weight * 0.22
            + separation * 0.12
            - conflict_penalty * 0.26
            - discount_penalty
            - proxy_penalty
            - mixed_penalty
        )
        return _clamp(score, 0.05, 0.92)

    @staticmethod
    def _confidence_label(confidence: float, liquidity_impulse: str) -> str:
        if liquidity_impulse == "data_insufficient" or confidence < 0.35:
            return "insufficient"
        if confidence < 0.55:
            return "low"
        if confidence < 0.74:
            return "medium"
        return "high"

    @staticmethod
    def _narrative_bullets(
        liquidity_impulse: str,
        subtype: str,
        direction_score: float,
        pillar_scores: Mapping[str, float],
        dominant_drivers: Sequence[Mapping[str, Any]],
        counter_evidence: Sequence[Mapping[str, Any]],
        data_gaps: Sequence[Mapping[str, Any]],
        evidence_quality: Mapping[str, Any],
        interactions: Sequence[str],
        confidence_label: str,
    ) -> tuple[str, ...]:
        if liquidity_impulse == "data_insufficient":
            return (
                "Liquidity impulse synthesis is unavailable because score-contributing coverage is below threshold or lacks real-source evidence.",
                f"Covered pillars: {evidence_quality['scoringPillarCount']} of {len(PILLARS)}.",
                "Unavailable, rejected, stale, proxy-only, and score-blocked inputs were not promoted into a false expansion or contraction call.",
            )

        strongest = sorted(PILLARS, key=lambda pillar: abs(pillar_scores[pillar]), reverse=True)[:3]
        bullets = [
            f"Liquidity impulse is {liquidity_impulse} with subtype {subtype} at {confidence_label} confidence.",
            f"Direction score is {direction_score:+.2f}.",
            "Strongest pillars: " + ", ".join(f"{pillar}={pillar_scores[pillar]:+.2f}" for pillar in strongest) + ".",
        ]

        if interactions:
            bullets.append("Rule interactions active: " + ", ".join(interactions[:2]) + ".")
        if dominant_drivers:
            bullets.append(
                "Dominant evidence drivers: " + ", ".join(str(item["label"]) for item in dominant_drivers[:3]) + "."
            )
        if counter_evidence:
            bullets.append("Counter-evidence is present, so confidence is discounted rather than ignored.")
        if data_gaps:
            bullets.append("Data gaps remain explicit and unavailable inputs were not treated as valid liquidity proof.")
        if evidence_quality["proxyOnlyScoringCount"] or evidence_quality["observationOnlyEvidenceCount"]:
            bullets.append("Proxy-only or observation-only evidence was discounted before classification.")
        return tuple(bullets)


def synthesize_liquidity_impulse(
    evidence_items: Iterable[LiquidityImpulseEvidenceItem | Mapping[str, Any]],
) -> LiquidityImpulseSynthesisResult:
    return LiquidityImpulseSynthesisService().synthesize(evidence_items)


def _coerce_evidence_item(
    value: LiquidityImpulseEvidenceItem | Mapping[str, Any],
) -> LiquidityImpulseEvidenceItem:
    if isinstance(value, LiquidityImpulseEvidenceItem):
        return value
    return LiquidityImpulseEvidenceItem.from_dict(value)


def _score_candidate(rules: Mapping[str, float], pillar_scores: Mapping[str, float]) -> float:
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


def _quality_weight(item: LiquidityImpulseEvidenceItem) -> tuple[float, tuple[str, ...]]:
    reasons: list[str] = []
    freshness = _normal(item.freshness) or "unknown"
    degradation_reason = _normal(item.degradation_reason)
    if freshness in _UNAVAILABLE_FRESHNESS:
        return 0.0, ("freshness_unavailable",)
    if any(marker in degradation_reason for marker in _REJECTED_REASON_MARKERS):
        return 0.0, ("degradation_unavailable_or_rejected",)
    if not item.score_contribution_allowed:
        return 0.0, ("score_contribution_not_allowed",)
    if item.included_in_score is False:
        return 0.0, ("included_in_score_false",)

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
    if item.proxy_only:
        weight *= 0.55
        reasons.append("proxy_only_discount")
    if item.observation_only:
        weight *= 0.45
        reasons.append("observation_only_discount")

    if weight <= 0.0:
        return 0.0, tuple(reasons or ("unscorable_quality",))
    return round(_clamp(weight, 0.0, 1.0), 4), tuple(reasons)


def _signal_strength(item: LiquidityImpulseEvidenceItem) -> float | None:
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
        ("crypto_liquidity_beta", "volatility_stress", -1.0),
        ("crypto_liquidity_beta", "dollar_pressure", -1.0),
        ("risk_asset_demand", "breadth_confirmation", 1.0),
        ("equity_flow_proxy", "breadth_confirmation", 1.0),
        ("rates_pressure", "funding_stress", 1.0),
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


def _expected_pillar_directions(liquidity_impulse: str, subtype: str) -> dict[str, float]:
    if subtype in _SUBTYPE_RULES:
        return {pillar: (1.0 if weight > 0 else -1.0) for pillar, weight in _SUBTYPE_RULES[subtype].items()}
    if liquidity_impulse == "expanding_liquidity":
        return dict(_PILLAR_EXPANSION_SIGN)
    if liquidity_impulse == "contracting_liquidity":
        return {pillar: -sign for pillar, sign in _PILLAR_EXPANSION_SIGN.items()}
    return {}


def _structural_counter_evidence(
    scored: Sequence[_ScoredEvidence],
    pillar_scores: Mapping[str, float],
) -> list[dict[str, Any]]:
    conflict_pairs = (
        ("crypto_liquidity_beta", "volatility_stress", -1.0, "crypto_beta_conflicts_with_volatility_stress"),
        ("crypto_liquidity_beta", "dollar_pressure", -1.0, "crypto_beta_conflicts_with_dollar_pressure"),
        ("risk_asset_demand", "breadth_confirmation", 1.0, "risk_asset_demand_conflicts_with_breadth"),
        ("equity_flow_proxy", "breadth_confirmation", 1.0, "equity_flow_conflicts_with_breadth"),
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
                key=lambda item: abs(item.oriented_impact),
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


def _data_gap(
    item: LiquidityImpulseEvidenceItem,
    reason: str,
    *,
    pillar: str | None = None,
) -> dict[str, Any]:
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
        "includedInScore": item.included_in_score,
        "proxyOnly": item.proxy_only,
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


def _optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    return _bool(value)


def _normal(value: Any) -> str:
    return _text(value).lower().replace("-", "_").replace(" ", "_")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
