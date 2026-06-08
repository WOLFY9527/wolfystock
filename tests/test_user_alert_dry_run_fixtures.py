# -*- coding: utf-8 -*-
"""Fixture catalog coverage for pure user alert dry-run helpers."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pytest

from src.services.user_alert_evaluation import evaluate_user_alert_dry_run
from src.services.user_alert_event_packet import build_user_alert_event_packet


FIXTURE_NOW = datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc)
BASE_RULE = {
    "rule_type": "watchlist_price_threshold",
    "symbol": "NVDA",
    "direction": "above",
    "threshold_price": 125.5,
}
BASE_INPUTS = {
    "rule": BASE_RULE,
    "observed_price": 130.0,
    "observed_at": FIXTURE_NOW,
    "freshness": {"status": "fresh"},
    "now": FIXTURE_NOW,
}

FIXTURE_CATALOG = {
    "condition_observed": {
        "inputs": BASE_INPUTS,
        "expected_title_fragment": "价格提醒已记录",
        "expected_message_fragment": "仅供观察，不会发送外部通知。",
        "expected_condition_observed": True,
        "expected_suppressed": False,
    },
    "condition_not_observed": {
        "inputs": {
            **BASE_INPUTS,
            "observed_price": 120.0,
        },
        "expected_title_fragment": "尚未触发提醒",
        "expected_message_fragment": "价格暂未达到你设定的关注条件",
        "expected_condition_observed": False,
        "expected_suppressed": False,
    },
    "blocked_insufficient_data": {
        "inputs": {
            **BASE_INPUTS,
            "observed_price": None,
        },
        "expected_title_fragment": "数据不足",
        "expected_message_fragment": "最近一次可用价格信息不足",
        "expected_condition_observed": False,
        "expected_suppressed": False,
    },
    "suppressed_muted": {
        "inputs": {
            **BASE_INPUTS,
            "suppression": {"muted": True},
        },
        "expected_title_fragment": "提醒已静默",
        "expected_message_fragment": "结果仅用于站内 dry-run 检查。",
        "expected_condition_observed": True,
        "expected_suppressed": True,
    },
    "suppressed_snoozed": {
        "inputs": {
            **BASE_INPUTS,
            "suppression": {"snoozedUntil": "2026-06-08T12:00:00Z"},
        },
        "expected_title_fragment": "提醒稍后再看",
        "expected_message_fragment": "结果仅用于站内 dry-run 检查。",
        "expected_condition_observed": True,
        "expected_suppressed": True,
    },
    "suppressed_cooldown": {
        "inputs": {
            **BASE_INPUTS,
            "suppression": {"cooldownActive": True},
        },
        "expected_title_fragment": "提醒已暂缓",
        "expected_message_fragment": "结果仅用于站内 dry-run 检查。",
        "expected_condition_observed": True,
        "expected_suppressed": True,
    },
    "suppressed_duplicate": {
        "inputs": {
            **BASE_INPUTS,
            "suppression": {"duplicateActive": True},
        },
        "expected_title_fragment": "重复提醒已折叠",
        "expected_message_fragment": "结果仅用于站内 dry-run 检查。",
        "expected_condition_observed": True,
        "expected_suppressed": True,
    },
}


def _evaluate_fixture(fixture_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    fixture = FIXTURE_CATALOG[fixture_name]
    evaluation = evaluate_user_alert_dry_run(**deepcopy(fixture["inputs"]))
    packet = build_user_alert_event_packet(result=evaluation, now=FIXTURE_NOW)
    return evaluation, packet


def test_fixture_catalog_covers_required_alert_states() -> None:
    assert set(FIXTURE_CATALOG) == {
        "condition_observed",
        "condition_not_observed",
        "blocked_insufficient_data",
        "suppressed_muted",
        "suppressed_snoozed",
        "suppressed_cooldown",
        "suppressed_duplicate",
    }


@pytest.mark.parametrize("fixture_name", list(FIXTURE_CATALOG))
def test_fixture_catalog_matches_expected_evaluation_and_packet_states(fixture_name: str) -> None:
    fixture = FIXTURE_CATALOG[fixture_name]
    evaluation, packet = _evaluate_fixture(fixture_name)

    assert evaluation["state"] == fixture_name
    assert evaluation["dryRun"] is True
    assert evaluation["outboundAttempted"] is False
    assert evaluation["liveOutbound"] is False
    assert evaluation["providerRuntimeCalled"] is False
    assert evaluation["networkCallsEnabled"] is False
    assert evaluation["marketCacheMutation"] is False
    assert evaluation["observationOnly"] is True
    assert evaluation["conditionObserved"] is fixture["expected_condition_observed"]
    assert evaluation["suppressed"] is fixture["expected_suppressed"]
    assert evaluation["title"].endswith(fixture["expected_title_fragment"])
    assert fixture["expected_message_fragment"] in evaluation["message"]

    assert packet["state"] == fixture_name
    assert packet["dryRun"] is True
    assert packet["outboundAttempted"] is False
    assert packet["liveOutbound"] is False
    assert packet["localOnly"] is True
    assert packet["title"] == evaluation["title"]
    assert packet["message"] == evaluation["message"]
    assert packet["safeMetadata"]["conditionObserved"] is fixture["expected_condition_observed"]
    assert packet["safeMetadata"]["suppressed"] is fixture["expected_suppressed"]
    assert packet["safeMetadata"]["dedupeFingerprint"] == evaluation["dedupeFingerprint"]


def test_fixture_catalog_remains_dry_run_no_send_and_local_only_in_every_state() -> None:
    for fixture_name in FIXTURE_CATALOG:
        evaluation, packet = _evaluate_fixture(fixture_name)

        assert evaluation["dryRun"] is True, fixture_name
        assert evaluation["outboundAttempted"] is False, fixture_name
        assert evaluation["liveOutbound"] is False, fixture_name
        assert evaluation["providerRuntimeCalled"] is False, fixture_name
        assert evaluation["networkCallsEnabled"] is False, fixture_name
        assert evaluation["marketCacheMutation"] is False, fixture_name
        assert evaluation["observationOnly"] is True, fixture_name

        assert packet["dryRun"] is True, fixture_name
        assert packet["outboundAttempted"] is False, fixture_name
        assert packet["liveOutbound"] is False, fixture_name
        assert packet["localOnly"] is True, fixture_name


def test_non_observed_and_blocked_states_do_not_look_suppressed() -> None:
    not_observed_evaluation, not_observed_packet = _evaluate_fixture("condition_not_observed")
    blocked_evaluation, blocked_packet = _evaluate_fixture("blocked_insufficient_data")

    assert not_observed_evaluation["conditionObserved"] is False
    assert not_observed_evaluation["suppressed"] is False
    assert not_observed_packet["safeMetadata"]["conditionObserved"] is False
    assert not_observed_packet["safeMetadata"]["suppressed"] is False

    assert blocked_evaluation["conditionObserved"] is False
    assert blocked_evaluation["suppressed"] is False
    assert blocked_packet["safeMetadata"]["conditionObserved"] is False
    assert blocked_packet["safeMetadata"]["suppressed"] is False


def test_suppressed_states_keep_observed_condition_but_do_not_send() -> None:
    for fixture_name in (
        "suppressed_muted",
        "suppressed_snoozed",
        "suppressed_cooldown",
        "suppressed_duplicate",
    ):
        evaluation, packet = _evaluate_fixture(fixture_name)

        assert evaluation["conditionObserved"] is True, fixture_name
        assert evaluation["suppressed"] is True, fixture_name
        assert packet["safeMetadata"]["conditionObserved"] is True, fixture_name
        assert packet["safeMetadata"]["suppressed"] is True, fixture_name
        assert "dry-run" in evaluation["message"], fixture_name
        assert packet["outboundAttempted"] is False, fixture_name
