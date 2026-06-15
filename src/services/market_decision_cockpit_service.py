# -*- coding: utf-8 -*-
"""Deterministic market decision cockpit aggregate service.

This service only composes already-normalized market regime, research radar,
and options observation payloads. It does not fetch providers, mutate caches,
rank scanners, or change any protected-domain semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from src.services.market_overview_service import MarketOverviewService
from src.services.market_regime_decision_engine import build_market_regime_decision
from src.services.options_market_structure_observation import build_options_market_structure_observation
from src.services.research_radar_candidate_engine import build_research_radar_candidate_queue


SCHEMA_VERSION = "market_decision_cockpit.v1"
NO_ADVICE_DISCLOSURE = "Decision support only; not investment advice or trading instruction."
_RESEARCH_EMPTY_REASON = "research_candidates_unavailable"
_OPTION_CHAIN_EMPTY_REASON = "option_chain_unavailable"
_MARKET_REGIME_LOW_CONFIDENCE_REASON = "market_regime_low_confidence"


class MarketDecisionCockpitService:
    """Compose market regime, research preview, and options observation."""

    def __init__(
        self,
        *,
        market_overview_service: MarketOverviewService | None = None,
        now_provider: Callable[[], str] | None = None,
    ) -> None:
        self._market_overview_service = market_overview_service or MarketOverviewService()
        self._now_provider = now_provider or self._default_now_provider

    def get_decision_cockpit(
        self,
        *,
        actor: Mapping[str, Any] | None = None,
        market_inputs: Mapping[str, Any] | None = None,
        market_regime_decision: Mapping[str, Any] | None = None,
        research_candidates: Sequence[Mapping[str, Any]] | None = None,
        option_contracts: Sequence[Any] | None = None,
        option_spot: float | int | str | None = None,
    ) -> dict[str, Any]:
        generated_at = self._now_provider()
        decision = self._build_market_regime_decision(
            actor=actor,
            market_inputs=market_inputs,
            market_regime_decision=market_regime_decision,
        )
        research_preview = self._build_research_queue_preview(
            decision,
            research_candidates=research_candidates,
        )
        options_status = self._build_options_structure_status(
            option_contracts=option_contracts,
            option_spot=option_spot,
        )
        cockpit_summary = self._build_cockpit_summary(decision, research_preview, options_status)
        data_quality = self._build_data_quality(decision, research_preview, options_status)

        return {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": generated_at,
            "marketRegimeDecision": decision,
            "researchQueuePreview": research_preview,
            "optionsStructureStatus": options_status,
            "cockpitSummary": cockpit_summary,
            "driverAttribution": self._build_driver_attribution(decision),
            "confidenceDiagnostics": self._build_confidence_diagnostics(
                decision,
                research_preview,
                options_status,
                data_quality,
            ),
            "watchTriggers": self._build_watch_triggers(decision, research_preview, options_status),
            "whatChanged": self._build_what_changed(
                generated_at,
                decision,
                research_preview,
                options_status,
            ),
            "cockpitReadiness": self._build_cockpit_readiness(
                decision,
                research_preview,
                options_status,
                data_quality,
            ),
            "scenarioHints": self._build_scenario_hints(decision),
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
            "dataQuality": data_quality,
        }

    @staticmethod
    def _default_now_provider() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _build_market_regime_decision(
        self,
        *,
        actor: Mapping[str, Any] | None,
        market_inputs: Mapping[str, Any] | None,
        market_regime_decision: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if isinstance(market_regime_decision, Mapping):
            payload = dict(market_regime_decision)
        elif isinstance(market_inputs, Mapping):
            payload = build_market_regime_decision(market_inputs)
        else:
            payload = self._market_overview_decision(actor=actor)

        payload.setdefault("invalidationConditions", _invalidation_conditions(payload))
        return payload

    def _market_overview_decision(self, *, actor: Mapping[str, Any] | None) -> dict[str, Any]:
        try:
            payload = self._market_overview_service.get_market_regime_decision(
                actor=dict(actor) if isinstance(actor, Mapping) else None
            )
            if isinstance(payload, Mapping):
                return dict(payload)
        except Exception:
            pass

        fallback = build_market_regime_decision({})
        fallback["inputSource"] = "market_decision_cockpit_fallback_inputs"
        fallback["updatedAt"] = self._default_now_provider()
        fallback["invalidationConditions"] = _invalidation_conditions(fallback)
        return fallback

    def _build_research_queue_preview(
        self,
        market_regime_decision: Mapping[str, Any],
        *,
        research_candidates: Sequence[Mapping[str, Any]] | None,
    ) -> dict[str, Any]:
        candidates = list(research_candidates or [])
        queue = build_research_radar_candidate_queue(
            candidates,
            market_regime_context=market_regime_decision,
        )
        research_queue = list(queue.get("researchQueue") or [])
        summary = queue.get("summary") if isinstance(queue.get("summary"), Mapping) else {}
        preview: dict[str, Any] = {
            "topCandidates": research_queue[:3],
            "queueQuality": summary.get("queueQuality", "thin"),
            "evidenceGaps": list(summary.get("evidenceGaps") or []),
            "previewOnly": True,
        }
        if not candidates or not research_queue:
            preview["degradedState"] = {
                "status": "empty",
                "reasonCodes": [_RESEARCH_EMPTY_REASON],
            }
        return preview

    def _build_options_structure_status(
        self,
        *,
        option_contracts: Sequence[Any] | None,
        option_spot: float | int | str | None,
    ) -> dict[str, Any]:
        contracts = list(option_contracts or [])
        prerequisites_met = bool(contracts) and option_spot is not None
        observation = build_options_market_structure_observation(
            contracts,
            spot=option_spot,
            methodology_approved=prerequisites_met,
            coverage_thresholds_defined=prerequisites_met,
            provider_authority_verified=prerequisites_met,
            redistribution_rights_verified=prerequisites_met,
            decision_use_rights_verified=prerequisites_met,
            deliverable_handling_reviewed=prerequisites_met,
        )

        observation_state = str(observation.get("observationState") or "blocked")
        if observation_state == "ready":
            gamma_status = "ready_observation"
        elif observation_state == "degraded":
            gamma_status = "degraded"
        else:
            gamma_status = "unavailable"

        blocked_reason_codes = list(observation.get("blockedReasonCodes") or [])
        if gamma_status == "unavailable" and _OPTION_CHAIN_EMPTY_REASON not in blocked_reason_codes:
            blocked_reason_codes.insert(0, _OPTION_CHAIN_EMPTY_REASON)

        return {
            "gammaEvidenceStatus": gamma_status,
            "observationOnly": bool(observation.get("observationOnly", True)),
            "decisionGrade": False,
            "missingEvidence": list(observation.get("missingEvidence") or []),
            "blockedReasonCodes": blocked_reason_codes,
        }

    def _build_cockpit_summary(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
    ) -> dict[str, Any]:
        regime = str(market_regime_decision.get("regime") or "lowConfidence")
        confidence = str(market_regime_decision.get("confidence") or "low")
        priorities = _mapping(market_regime_decision.get("researchPriorities"))
        regime_quality = _mapping(market_regime_decision.get("dataQuality"))
        evidence_gaps = list(research_preview.get("evidenceGaps") or [])
        blocked_reasons = list(options_status.get("blockedReasonCodes") or [])

        what_to_watch = list(priorities.get("watchToday") or [])
        what_to_watch.extend(priorities.get("investigateNext") or [])
        if not what_to_watch:
            what_to_watch.append("Await stronger market evidence before tightening the read.")

        confidence_limits = list(regime_quality.get("confidenceCapReasons") or [])
        confidence_limits.extend(evidence_gaps)
        confidence_limits.extend(blocked_reasons)

        return {
            "whatChanged": [
                f"Regime resolved to {regime} with {confidence} confidence.",
                f"Research preview quality is {research_preview.get('queueQuality', 'thin')}.",
            ],
            "whyItMatters": [
                "This cockpit keeps regime, research triage, and options observation in one read-only view.",
            ],
            "whatToWatch": what_to_watch,
            "confidenceLimits": _dedupe(confidence_limits),
        }

    def _build_data_quality(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
    ) -> dict[str, Any]:
        regime_quality = _mapping(market_regime_decision.get("dataQuality"))
        reason_codes = list(market_regime_decision.get("missingEvidence") or [])
        if str(market_regime_decision.get("confidence") or "").lower() == "low":
            reason_codes.append(_MARKET_REGIME_LOW_CONFIDENCE_REASON)
        if not research_preview.get("topCandidates"):
            reason_codes.append(_RESEARCH_EMPTY_REASON)
        if options_status.get("gammaEvidenceStatus") == "unavailable":
            reason_codes.append(_OPTION_CHAIN_EMPTY_REASON)
        reason_codes.append("options_observation_only")

        available_driver_count = int(regime_quality.get("availableDriverCount") or 0)
        status = "blocked" if (
            available_driver_count == 0
            and not research_preview.get("topCandidates")
            and options_status.get("gammaEvidenceStatus") == "unavailable"
        ) else "degraded"

        return {
            "status": status,
            "reasonCodes": _dedupe(reason_codes),
            "regimeEvidenceGrade": regime_quality.get("evidenceGrade"),
            "availableDriverCount": available_driver_count,
            "proxyEvidenceCount": int(regime_quality.get("proxyEvidenceCount") or 0),
        }

    def _build_driver_attribution(self, market_regime_decision: Mapping[str, Any]) -> dict[str, Any]:
        drivers = _mapping(market_regime_decision.get("driverScores"))
        driver_items = [
            _driver_item(driver_name, driver_payload)
            for driver_name, driver_payload in drivers.items()
            if isinstance(driver_payload, Mapping)
        ]
        positive = sorted(
            (
                item
                for item in driver_items
                if item["score"] > 0 and item["evidenceState"] not in {"unavailable", "blocked"}
            ),
            key=lambda item: (-item["score"], item["driver"]),
        )
        negative = sorted(
            (
                item
                for item in driver_items
                if item["score"] < 0 and item["evidenceState"] not in {"unavailable", "blocked"}
            ),
            key=lambda item: (item["score"], item["driver"]),
        )
        unavailable = sorted(
            (item for item in driver_items if item["evidenceState"] in {"unavailable", "blocked"}),
            key=lambda item: (item["evidenceState"] != "unavailable", item["driver"]),
        )

        return {
            "topPositiveDrivers": positive[:3],
            "topNegativeDrivers": negative[:3],
            "conflictingDrivers": _conflicting_driver_items(
                str(market_regime_decision.get("regime") or ""),
                positive,
                negative,
            ),
            "unavailableDrivers": unavailable,
        }

    def _build_confidence_diagnostics(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
        data_quality: Mapping[str, Any],
    ) -> dict[str, Any]:
        regime_quality = _mapping(market_regime_decision.get("dataQuality"))
        missing_evidence = list(market_regime_decision.get("missingEvidence") or [])
        reason_codes = list(data_quality.get("reasonCodes") or [])
        evidence_strength = {
            "confidence": market_regime_decision.get("confidence", "low"),
            "confidenceScore": market_regime_decision.get("confidenceScore"),
            "regimeEvidenceGrade": regime_quality.get("evidenceGrade"),
            "availableDriverCount": int(regime_quality.get("availableDriverCount") or 0),
            "scoringDriverCount": int(regime_quality.get("scoringDriverCount") or 0),
            "blockedDriverCount": int(regime_quality.get("blockedDriverCount") or 0),
            "missingDriverCount": int(regime_quality.get("missingDriverCount") or 0),
            "researchQueueQuality": research_preview.get("queueQuality", "thin"),
            "optionsGammaEvidenceStatus": options_status.get("gammaEvidenceStatus", "unavailable"),
        }

        return {
            "confidenceCaps": _dedupe(regime_quality.get("confidenceCapReasons") or []),
            "confidencePenalties": _dedupe([*missing_evidence, *reason_codes]),
            "evidenceStrength": evidence_strength,
            "missingEvidenceImpact": [
                {
                    "evidence": str(item),
                    "impact": _missing_evidence_impact(str(item)),
                }
                for item in _dedupe(missing_evidence or reason_codes)
            ],
        }

    def _build_watch_triggers(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
    ) -> list[dict[str, str]]:
        explanation = _mapping(market_regime_decision.get("explanation"))
        priorities = _mapping(market_regime_decision.get("researchPriorities"))
        confirms = _dedupe(explanation.get("whatConfirmsIt") or [])
        invalidates = _dedupe(explanation.get("whatInvalidatesIt") or [])
        watch_items = _dedupe([
            *(priorities.get("watchToday") or []),
            *(priorities.get("investigateNext") or []),
        ])
        triggers: list[dict[str, str]] = []

        for index, condition in enumerate(watch_items[:3], start=1):
            triggers.append(
                {
                    "triggerName": f"Regime watch {index}",
                    "driver": _infer_driver_name(condition),
                    "condition": str(condition),
                    "whyItMatters": "It helps confirm whether the current regime evidence remains coherent.",
                    "currentEvidence": (
                        confirms[0]
                        if confirms
                        else str(market_regime_decision.get("regime") or "lowConfidence")
                    ),
                }
            )
        if invalidates:
            triggers.append(
                {
                    "triggerName": "Regime invalidation watch",
                    "driver": "marketRegimeDecision",
                    "condition": invalidates[0],
                    "whyItMatters": "It identifies evidence that would weaken the current regime read.",
                    "currentEvidence": str(market_regime_decision.get("confidence") or "low"),
                }
            )
        if not research_preview.get("topCandidates"):
            triggers.append(
                {
                    "triggerName": "Research radar availability",
                    "driver": "researchQueuePreview",
                    "condition": "Research candidates become available with enough evidence quality.",
                    "whyItMatters": (
                        "It determines whether regime context can be paired with concrete research queue evidence."
                    ),
                    "currentEvidence": str(research_preview.get("queueQuality") or "thin"),
                }
            )
        if options_status.get("gammaEvidenceStatus") == "unavailable":
            triggers.append(
                {
                    "triggerName": "Options observation availability",
                    "driver": "optionsStructureStatus",
                    "condition": "Options structure evidence becomes available for observation only.",
                    "whyItMatters": (
                        "It separates options market structure context from decision-grade regime evidence."
                    ),
                    "currentEvidence": "unavailable",
                }
            )
        return triggers[:5]

    def _build_what_changed(
        self,
        generated_at: str,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
    ) -> dict[str, Any]:
        observations: list[dict[str, str]] = []
        updated_at = market_regime_decision.get("updatedAt")
        if updated_at:
            observations.append(
                {
                    "field": "marketRegimeDecision.updatedAt",
                    "value": str(updated_at),
                    "interpretation": "Current payload timestamp is available; no historical baseline is inferred.",
                }
            )
        observations.extend(
            [
                {
                    "field": "generatedAt",
                    "value": generated_at,
                    "interpretation": "Cockpit generation time is available; no prior cockpit snapshot is inferred.",
                },
                {
                    "field": "marketRegimeDecision.regime",
                    "value": str(market_regime_decision.get("regime") or "lowConfidence"),
                    "interpretation": "Current regime field is available without historical delta.",
                },
                {
                    "field": "researchQueuePreview.queueQuality",
                    "value": str(research_preview.get("queueQuality") or "thin"),
                    "interpretation": "Current research queue quality is available without historical delta.",
                },
                {
                    "field": "optionsStructureStatus.gammaEvidenceStatus",
                    "value": str(options_status.get("gammaEvidenceStatus") or "unavailable"),
                    "interpretation": "Current options observation status is available without historical delta.",
                },
            ]
        )
        return {
            "status": "degraded",
            "basis": "current_snapshot_only",
            "observations": observations,
            "unavailableDrivers": ["historical_baseline_unavailable"],
        }

    def _build_cockpit_readiness(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
        data_quality: Mapping[str, Any],
    ) -> dict[str, Any]:
        reasons: list[str] = []
        confidence = str(market_regime_decision.get("confidence") or "low").lower()
        regime_quality = _mapping(market_regime_decision.get("dataQuality"))
        scoring_driver_count = int(
            regime_quality.get("scoringDriverCount")
            or data_quality.get("availableDriverCount")
            or 0
        )
        research_ready = bool(research_preview.get("topCandidates"))
        options_ready = options_status.get("gammaEvidenceStatus") != "unavailable"

        if confidence == "low" or scoring_driver_count < 3:
            reasons.append("market regime evidence is insufficient")
        if not research_ready:
            reasons.append("research radar candidates are unavailable")
        if not options_ready:
            reasons.append("options structure evidence is unavailable")

        if not reasons:
            return {
                "status": "ready",
                "reasons": ["core evidence is available for read-only decision support"],
            }
        if data_quality.get("status") == "blocked" or len(reasons) >= 3:
            return {"status": "insufficient", "reasons": reasons}
        return {"status": "degraded", "reasons": reasons}

    def _build_scenario_hints(self, market_regime_decision: Mapping[str, Any]) -> list[str]:
        explanation = _mapping(market_regime_decision.get("explanation"))
        hints = [
            "Regime confidence could strengthen if more score-grade drivers align with the current read.",
            "Regime confidence could weaken if leading drivers move against the current read together.",
        ]
        if market_regime_decision.get("missingEvidence"):
            hints.append("Confidence could improve if missing evidence becomes available through approved inputs.")
        if _mapping(market_regime_decision.get("dataQuality")).get("confidenceCapReasons"):
            hints.append("Confidence remains capped until source-quality limits clear.")
        for item in explanation.get("whatConfirmsIt") or []:
            hints.append(f"Confirmation hint: {_without_numeric_details(item)}")
            break
        for item in explanation.get("whatInvalidatesIt") or []:
            hints.append(f"Invalidation hint: {_without_numeric_details(item)}")
            break
        return _dedupe(hints)[:5]


def build_market_decision_cockpit(
    *,
    actor: Mapping[str, Any] | None = None,
    market_inputs: Mapping[str, Any] | None = None,
    market_regime_decision: Mapping[str, Any] | None = None,
    research_candidates: Sequence[Mapping[str, Any]] | None = None,
    option_contracts: Sequence[Any] | None = None,
    option_spot: float | int | str | None = None,
    market_overview_service: MarketOverviewService | None = None,
    now_provider: Callable[[], str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the v1 market decision cockpit payload."""

    now = (lambda: generated_at) if generated_at is not None else now_provider
    return MarketDecisionCockpitService(
        market_overview_service=market_overview_service,
        now_provider=now,
    ).get_decision_cockpit(
        actor=actor,
        market_inputs=market_inputs,
        market_regime_decision=market_regime_decision,
        research_candidates=research_candidates,
        option_contracts=option_contracts,
        option_spot=option_spot,
    )


def _invalidation_conditions(payload: Mapping[str, Any]) -> list[str]:
    explanation = payload.get("explanation")
    if not isinstance(explanation, Mapping):
        return []
    return list(explanation.get("whatInvalidatesIt") or [])


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _driver_item(driver: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    score = _int_value(payload.get("score"))
    evidence_state = str(payload.get("evidenceState") or "unavailable")
    observations = _dedupe(payload.get("observations") or [])
    reasons = _dedupe(payload.get("reasons") or [])
    return {
        "driver": driver,
        "score": score,
        "evidenceState": evidence_state,
        "whyItMatters": _driver_why_it_matters(driver, score),
        "currentEvidence": observations or ["No current driver observation is available."],
        "reasonCodes": reasons,
    }


def _conflicting_driver_items(
    regime: str,
    positive: Sequence[Mapping[str, Any]],
    negative: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not positive or not negative:
        return []
    negative_regimes = {"riskOff", "downsideAccelerationRisk", "eventRisk"}
    if regime in negative_regimes:
        return [
            {
                "driver": str(item["driver"]),
                "score": int(item["score"]),
                "condition": "Positive driver conflicts with negative regime evidence.",
                "currentEvidence": list(item.get("currentEvidence") or []),
            }
            for item in positive[:2]
        ]
    return [
        {
            "driver": str(item["driver"]),
            "score": int(item["score"]),
            "condition": "Negative driver conflicts with positive regime evidence.",
            "currentEvidence": list(item.get("currentEvidence") or []),
        }
        for item in negative[:2]
    ]


def _driver_why_it_matters(driver: str, score: int) -> str:
    direction = "positive" if score > 0 else "negative" if score < 0 else "neutral"
    labels = {
        "dealerGamma": "Options structure context can cap confidence when unavailable.",
        "breadthParticipation": "Breadth shows whether participation is broad or narrow.",
        "volatilityStructure": "Volatility helps separate orderly risk from stress.",
        "ratesDollar": "Rates-dollar pressure can change market liquidity conditions.",
        "liquidityCredit": (
            "Liquidity-credit evidence shows whether funding conditions are supportive or restrictive."
        ),
        "crossAssetRisk": "Cross-asset evidence checks whether adjacent markets confirm the read.",
        "sectorThemeRotation": "Sector-theme rotation shows whether leadership is concentrated or broadening.",
        "eventCatalyst": "Event catalyst evidence flags whether scheduled or unscheduled events dominate.",
    }
    return labels.get(driver, f"{driver} is a {direction} contributor to the current regime read.")


def _missing_evidence_impact(reason: str) -> str:
    if reason.startswith("dealerGamma"):
        return "Options structure remains observation-only and cannot raise regime confidence."
    if reason.startswith("research") or reason == _RESEARCH_EMPTY_REASON:
        return "Research queue context is thinner until candidate evidence is available."
    if reason.startswith("option") or reason == _OPTION_CHAIN_EMPTY_REASON:
        return "Options market structure remains unavailable for observation context."
    if "low_confidence" in reason:
        return "The cockpit should stay degraded until more score-grade drivers align."
    if "blocked" in reason:
        return "Blocked evidence cannot contribute to the regime read."
    return "Missing evidence limits confidence in the current regime read."


def _infer_driver_name(condition: Any) -> str:
    text = str(condition).lower()
    if "breadth" in text:
        return "breadthParticipation"
    if "volatility" in text:
        return "volatilityStructure"
    if "rate" in text or "dollar" in text:
        return "ratesDollar"
    if "liquidity" in text or "credit" in text:
        return "liquidityCredit"
    if "cross-asset" in text:
        return "crossAssetRisk"
    if "sector" in text or "theme" in text or "rotation" in text:
        return "sectorThemeRotation"
    if "event" in text:
        return "eventCatalyst"
    if "gamma" in text:
        return "dealerGamma"
    return "marketRegimeDecision"


def _without_numeric_details(value: Any) -> str:
    text = str(value)
    cleaned = "".join(" " if char.isdigit() else char for char in text)
    return " ".join(cleaned.split())


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if number != number or number in {float("inf"), float("-inf")}:
        return 0
    return int(round(number))


def _dedupe(items: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


__all__ = [
    "MarketDecisionCockpitService",
    "NO_ADVICE_DISCLOSURE",
    "SCHEMA_VERSION",
    "build_market_decision_cockpit",
]
