# -*- coding: utf-8 -*-
"""Shared Scenario durable baseline snapshot contract constants."""

from __future__ import annotations


SCENARIO_BASELINE_DURABLE_READINESS_STATES = frozenset(
    {
        "ready",
        "partial",
        "observation_only",
        "not_available",
    }
)


def is_scenario_baseline_durable_readiness_state(value: object) -> bool:
    return str(value or "").strip() in SCENARIO_BASELINE_DURABLE_READINESS_STATES


__all__ = [
    "SCENARIO_BASELINE_DURABLE_READINESS_STATES",
    "is_scenario_baseline_durable_readiness_state",
]
