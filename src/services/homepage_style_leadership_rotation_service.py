# -*- coding: utf-8 -*-
"""Pure service that emits the homepage Style Leadership Rotation contract."""

from __future__ import annotations

from api.v1.schemas.homepage_style_leadership_rotation import (
    HOMEPAGE_STYLE_LEADERSHIP_ROTATION_DEFAULT_AS_OF,
    HOMEPAGE_STYLE_LEADERSHIP_ROTATION_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_STYLE_LEADERSHIP_ROTATION_SCHEMA_VERSION,
    HomepageStyleAffectedArea,
    HomepageStyleConfirmationSummary,
    HomepageStyleLeadershipRegime,
    HomepageStyleLeadershipRotationSnapshot,
    HomepageStyleRotationEntry,
    HomepageStyleRotationQualitySummary,
    HomepageStyleRotationSignal,
    HomepageStyleRotationWindow,
)


def _style_entry(
    *,
    style_group: str,
    label: str,
    state: str,
    trend: str,
    observation: str,
    confirmation: str,
) -> HomepageStyleRotationEntry:
    return HomepageStyleRotationEntry(
        styleGroup=style_group,
        label=label,
        state=state,
        trend=trend,
        observation=observation,
        confirmation=confirmation,
    )


def _signal(
    *,
    style_group: str,
    state: str,
    trend: str,
    signal_label: str,
    observation: str,
    missing_confirmation: list[str] | None = None,
) -> HomepageStyleRotationSignal:
    return HomepageStyleRotationSignal(
        styleGroup=style_group,
        state=state,
        trend=trend,
        signalLabel=signal_label,
        observation=observation,
        missingConfirmation=missing_confirmation or [],
    )


def _confirmation(
    *,
    state: str,
    label: str,
    summary: str,
    confirmed_by: list[str] | None = None,
    needs_confirmation: list[str] | None = None,
) -> HomepageStyleConfirmationSummary:
    return HomepageStyleConfirmationSummary(
        state=state,
        label=label,
        summary=summary,
        confirmedBy=confirmed_by or [],
        needsConfirmation=needs_confirmation or [],
    )


def _affected_area(*, name: str, relationship: str, state: str) -> HomepageStyleAffectedArea:
    return HomepageStyleAffectedArea(name=name, relationship=relationship, state=state)


class HomepageStyleLeadershipRotationService:
    """Build deterministic style-leadership observations without runtime dependencies."""

    def build_snapshot(self) -> HomepageStyleLeadershipRotationSnapshot:
        return HomepageStyleLeadershipRotationSnapshot(
            schemaVersion=HOMEPAGE_STYLE_LEADERSHIP_ROTATION_SCHEMA_VERSION,
            asOf=HOMEPAGE_STYLE_LEADERSHIP_ROTATION_DEFAULT_AS_OF,
            rotationWindow=HomepageStyleRotationWindow(
                windowLabel="20 trading days",
                lookbackDays=20,
                cadence="daily research sample",
                comparisonBasis="Relative style participation compared with broad index breadth.",
            ),
            leadershipRegime=HomepageStyleLeadershipRegime(
                state="proxy",
                label="Large quality growth leadership",
                summary="Leadership appears concentrated in quality, growth and large-cap styles while broader participation needs confirmation.",
                leadingStyles=["quality", "growth", "large_cap"],
                laggingStyles=["small_cap", "cyclicals"],
            ),
            styleLeaders=[
                _style_entry(
                    style_group="quality",
                    label="Quality",
                    state="confirmed",
                    trend="leading",
                    observation="Balance-sheet resilience and earnings stability are the clearest leadership observations.",
                    confirmation="Supported by breadth and lower-volatility participation in this static sample.",
                ),
                _style_entry(
                    style_group="growth",
                    label="Growth",
                    state="confirmed",
                    trend="leading",
                    observation="Growth remains part of the leadership cluster, but its rate sensitivity needs monitoring.",
                    confirmation="Confirmed by relative participation inside the deterministic style sample.",
                ),
                _style_entry(
                    style_group="large_cap",
                    label="Large cap",
                    state="confirmed",
                    trend="leading",
                    observation="Large-cap participation is stronger than smaller-cap participation in the sample.",
                    confirmation="Confirmed by concentration and breadth observations across style groups.",
                ),
            ],
            styleLaggards=[
                _style_entry(
                    style_group="small_cap",
                    label="Small cap",
                    state="unavailable",
                    trend="unavailable",
                    observation="Small-cap confirmation is not available in this standalone contract.",
                    confirmation="A direct small-cap breadth series is still missing from this contract.",
                ),
                _style_entry(
                    style_group="cyclicals",
                    label="Cyclicals",
                    state="no_evidence",
                    trend="watch",
                    observation="Cyclical style leadership is not evidenced by this static sample.",
                    confirmation="Sector participation would need additional confirmation before classification.",
                ),
            ],
            rotationSignals=[
                _signal(
                    style_group="growth",
                    state="confirmed",
                    trend="leading",
                    signal_label="Growth participation",
                    observation="Growth leadership is visible in the sample, with rate sensitivity still relevant.",
                ),
                _signal(
                    style_group="value",
                    state="proxy",
                    trend="mixed",
                    signal_label="Value participation",
                    observation="Value participation is represented by proxy observations and lacks direct confirmation.",
                    missing_confirmation=["Value factor breadth"],
                ),
                _signal(
                    style_group="quality",
                    state="confirmed",
                    trend="leading",
                    signal_label="Quality resilience",
                    observation="Quality shows the clearest leadership confirmation across the sample.",
                ),
                _signal(
                    style_group="momentum",
                    state="conflicting",
                    trend="mixed",
                    signal_label="Momentum concentration",
                    observation="Momentum remains visible but concentration creates conflicting breadth evidence.",
                    missing_confirmation=["Equal-weight momentum breadth"],
                ),
                _signal(
                    style_group="defensive",
                    state="proxy",
                    trend="watch",
                    signal_label="Defensive participation",
                    observation="Defensive participation is observable as a resilience proxy, not a confirmed regime shift.",
                    missing_confirmation=["Defensive sector breadth"],
                ),
                _signal(
                    style_group="cyclicals",
                    state="no_evidence",
                    trend="watch",
                    signal_label="Cyclical participation",
                    observation="Cyclical participation has no direct evidence in the standalone sample.",
                    missing_confirmation=["Cyclical sector participation"],
                ),
                _signal(
                    style_group="large_cap",
                    state="confirmed",
                    trend="leading",
                    signal_label="Large-cap concentration",
                    observation="Large-cap concentration confirms that leadership is not broadly distributed.",
                ),
                _signal(
                    style_group="small_cap",
                    state="unavailable",
                    trend="unavailable",
                    signal_label="Small-cap confirmation",
                    observation="Small-cap confirmation is unavailable without a dedicated breadth series.",
                    missing_confirmation=["Small-cap breadth series"],
                ),
            ],
            confirmationStatus=_confirmation(
                state="proxy",
                label="Proxy-confirmed leadership",
                summary="Leadership is observable, but direct cross-style confirmation is incomplete.",
                confirmed_by=["Quality participation", "Growth participation", "Large-cap concentration"],
                needs_confirmation=["Value breadth", "Small-cap breadth", "Cyclical participation"],
            ),
            breadthConfirmation=_confirmation(
                state="conflicting",
                label="Breadth not fully aligned",
                summary="Leadership is visible, while broader participation remains uneven across style groups.",
                confirmed_by=["Quality breadth", "Large-cap participation"],
                needs_confirmation=["Equal-weight participation", "Small-cap breadth"],
            ),
            volatilityConfirmation=_confirmation(
                state="proxy",
                label="Volatility proxy only",
                summary="Lower-volatility resilience is represented as a proxy and should not be treated as direct confirmation.",
                confirmed_by=["Quality resilience"],
                needs_confirmation=["Realized volatility dispersion", "Defensive breadth"],
            ),
            ratesSensitivity=_confirmation(
                state="conflicting",
                label="Rates sensitivity mixed",
                summary="Growth leadership can conflict with higher rate sensitivity, so confirmation needs rates context.",
                confirmed_by=["Growth participation"],
                needs_confirmation=["Long-rate trend", "Real-yield pressure"],
            ),
            affectedSectors=[
                _affected_area(
                    name="Technology",
                    relationship="Linked to growth and momentum leadership concentration.",
                    state="proxy",
                ),
                _affected_area(
                    name="Health care",
                    relationship="Linked to quality and defensive resilience observations.",
                    state="proxy",
                ),
                _affected_area(
                    name="Industrials",
                    relationship="Useful for cyclical confirmation that is not evidenced here.",
                    state="no_evidence",
                ),
                _affected_area(
                    name="Financials",
                    relationship="Useful for value and rate-sensitivity confirmation that remains incomplete.",
                    state="conflicting",
                ),
            ],
            affectedThemes=[
                _affected_area(
                    name="Quality growth",
                    relationship="Primary leadership theme in this deterministic sample.",
                    state="confirmed",
                ),
                _affected_area(
                    name="Breadth expansion",
                    relationship="Needed to determine whether leadership is spreading beyond large components.",
                    state="conflicting",
                ),
                _affected_area(
                    name="Rate-sensitive duration",
                    relationship="Relevant because growth leadership can change with rates context.",
                    state="proxy",
                ),
                _affected_area(
                    name="Small-cap participation",
                    relationship="Unavailable until dedicated breadth evidence is present.",
                    state="unavailable",
                ),
            ],
            missingEvidence=[
                "Direct value style breadth",
                "Dedicated small-cap breadth series",
                "Cyclical sector participation",
                "Realized volatility dispersion",
                "Rates context confirmation",
            ],
            watchPoints=[
                "Whether leadership broadens beyond quality growth",
                "Whether momentum concentration eases",
                "Whether value breadth improves",
                "Whether small-cap participation becomes available",
                "Whether defensive resilience strengthens",
                "Whether rates pressure changes growth confirmation",
            ],
            evidenceQuality=HomepageStyleRotationQualitySummary(
                state="proxy",
                label="Proxy research sample",
                summary="Standalone contract distinguishes confirmed, proxy, conflicting, no-evidence and unavailable states.",
            ),
            dataQuality=HomepageStyleRotationQualitySummary(
                state="static_sample",
                label="Static deterministic sample",
                summary="Static sample remains unchanged for repeatable style-rotation review.",
            ),
            noAdviceDisclosure=HOMEPAGE_STYLE_LEADERSHIP_ROTATION_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_STYLE_LEADERSHIP_ROTATION_DEFAULT_AS_OF",
    "HOMEPAGE_STYLE_LEADERSHIP_ROTATION_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_STYLE_LEADERSHIP_ROTATION_SCHEMA_VERSION",
    "HomepageStyleLeadershipRotationService",
]
