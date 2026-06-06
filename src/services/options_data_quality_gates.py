# -*- coding: utf-8 -*-
"""Offline-only Options Lab data-quality and liquidity gate diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


SUPPORTED_OPTIONS_STRATEGY_KEYS = frozenset(
    {"long_call", "long_put", "bull_call_spread", "bear_put_spread"}
)
_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "header",
    "password",
    "request",
    "response",
    "secret",
    "token",
)
_PROVIDER_AUTHORITY_LABELS = {
    "provider_authority_missing": "缺少 provider 决策授权元数据",
    "provider_authority_tier_missing": "缺少内部 provider authority tier",
    "provider_authority_tier_observation_only": "内部 provider authority tier 仅允许观察",
    "provider_authority_tier_analysis_only": "内部 provider authority tier 仅允许分析",
    "provider_authority_policy_not_granted": "内部 provider authority policy 未授予决策级权限",
    "provider_self_authority_ignored": "provider 自声明决策权限已忽略",
    "provider_fixture_not_decision_grade": "fixture provider 不能作为决策级证据",
    "provider_synthetic_not_decision_grade": "synthetic provider 不能作为决策级证据",
    "provider_dry_run_not_decision_grade": "dry-run provider 不能作为决策级证据",
    "provider_stub_not_decision_grade": "stub provider 不能作为决策级证据",
    "provider_adapter_contract_not_decision_grade": "adapter contract provider 不能作为决策级证据",
    "provider_live_disabled": "provider live 模式未启用",
    "provider_tradeable_data_false": "provider 未声明 tradeable data",
    "provider_decision_authority_not_granted": "provider 未显式授予决策级权限",
}
_PROVIDER_LIVE_EVIDENCE_LABELS = {
    "provider_live_evidence_missing": "缺少 provider live evidence",
    "live_evidence_live_disabled": "live provider 未启用",
    "live_evidence_fixture_blocked": "fixture 数据不能进入 live evidence ready",
    "live_evidence_synthetic_blocked": "synthetic 数据不能进入 live evidence ready",
    "live_evidence_dry_run_blocked": "dry-run 数据不能进入 live evidence ready",
    "live_evidence_stub_blocked": "stub 数据不能进入 live evidence ready",
    "live_evidence_adapter_contract_blocked": "adapter contract 数据不能进入 live evidence ready",
    "live_evidence_tradeable_data_false": "provider 未提供 tradeable data 证据",
    "live_evidence_quote_freshness_missing": "缺少 quote freshness",
    "live_evidence_quote_freshness_unknown": "quote freshness 未知",
    "live_evidence_quote_freshness_not_fresh": "quote freshness 不满足 live evidence 要求",
    "live_evidence_chain_freshness_missing": "缺少 chain freshness",
    "live_evidence_chain_freshness_unknown": "chain freshness 未知",
    "live_evidence_chain_freshness_not_fresh": "chain freshness 不满足 live evidence 要求",
    "live_evidence_expiration_coverage_missing": "缺少 expiration coverage",
    "live_evidence_expiration_coverage_partial": "expiration coverage 不完整",
    "live_evidence_bid_ask_coverage_missing": "缺少 bid/ask coverage",
    "live_evidence_bid_ask_coverage_partial": "bid/ask coverage 不完整",
    "live_evidence_open_interest_coverage_missing": "缺少 open interest coverage",
    "live_evidence_open_interest_coverage_partial": "open interest coverage 不完整",
    "live_evidence_volume_coverage_missing": "缺少 volume coverage",
    "live_evidence_volume_coverage_partial": "volume coverage 不完整",
    "live_evidence_iv_coverage_missing": "缺少 IV coverage",
    "live_evidence_iv_coverage_partial": "IV coverage 不完整",
    "live_evidence_greeks_coverage_missing": "缺少 Greeks coverage",
    "live_evidence_greeks_coverage_partial": "Greeks coverage 不完整",
    "live_evidence_iv_rank_authority_missing": "缺少 IV rank authority 证据",
    "live_evidence_event_calendar_authority_missing": "缺少 event calendar authority 证据",
    "live_evidence_provider_self_claim_ignored": "provider 自声明 readiness 已忽略",
}
_LIVE_EVIDENCE_FRESHNESS_READY = frozenset(
    {"fresh", "live", "realtime", "real_time", "real-time"}
)
_LIVE_EVIDENCE_AUTHORITY_READY = frozenset(
    {"authorized", "authorized_live", "live_authorized", "authority_present", "present", "available"}
)
_LIVE_EVIDENCE_COVERAGE_FIELDS = (
    "expiration",
    "bid_ask",
    "open_interest",
    "volume",
    "iv",
    "greeks",
)
INTERNAL_OPTIONS_PROVIDER_AUTHORITY_POLICY_SOURCE = "wolfystock_options_provider_authority_policy_v1"
_INTERNAL_PROVIDER_AUTHORITY_TIER_POLICY = {
    "synthetic_fixture": "live_observation_only",
    "synthetic": "live_observation_only",
    "fixture": "live_observation_only",
    "delayed_fixture": "live_observation_only",
    "real_shaped_delayed_fixture": "live_observation_only",
    "malformed_fixture": "live_observation_only",
    "missing_greeks_fixture": "live_observation_only",
    "tradier": "live_observation_only",
    "ibkr": "live_observation_only",
    "polygon": "live_observation_only",
}


class OptionsGateStatus(str, Enum):
    CLEAR = "clear"
    BLOCKED = "blocked"
    OBSERVE_ONLY = "observe_only"
    MANUAL_REVIEW = "manual_review"


class OptionsProviderAuthorityTier(str, Enum):
    LIVE_OBSERVATION_ONLY = "live_observation_only"
    LIVE_ANALYSIS_GRADE = "live_analysis_grade"
    DECISION_GRADE = "decision_grade"


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _coerce_text(value: Any) -> str:
    return str(value or "").strip()


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on", "enabled"}:
            return True
        if text in {"0", "false", "no", "off", "disabled"}:
            return False
        return None
    return bool(value)


def _contains_marker(*values: Any, markers: Iterable[str]) -> bool:
    text = " ".join(_coerce_text(value).lower() for value in values if value is not None)
    return any(marker in text for marker in markers)


def _flatten_authority_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(_flatten_authority_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return " ".join(_flatten_authority_text(item) for item in value)
    return _coerce_text(value).lower()


@dataclass(slots=True)
class OptionsGateIssue:
    code: str
    category: str
    status: OptionsGateStatus
    label: str
    decision_grade: bool = False
    leg_index: int | None = None
    contract_symbol: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category,
            "status": self.status.value,
            "label": self.label,
            "decisionGrade": self.decision_grade,
            "legIndex": self.leg_index,
            "contractSymbol": self.contract_symbol,
        }


@dataclass(slots=True)
class OptionsLegGateDiagnostics:
    leg_index: int
    contract_symbol: str | None
    data_quality_status: OptionsGateStatus
    liquidity_status: OptionsGateStatus
    issue_codes: list[str] = field(default_factory=list)
    decision_grade: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "legIndex": self.leg_index,
            "contractSymbol": self.contract_symbol,
            "dataQualityStatus": self.data_quality_status.value,
            "liquidityStatus": self.liquidity_status.value,
            "issueCodes": list(self.issue_codes),
            "decisionGrade": self.decision_grade,
        }


@dataclass(slots=True)
class OptionsGateBucket:
    status: OptionsGateStatus
    issue_codes: list[str] = field(default_factory=list)
    decision_grade: bool = False
    leg_diagnostics: list[OptionsLegGateDiagnostics] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "issueCodes": list(self.issue_codes),
            "decisionGrade": self.decision_grade,
            "legDiagnostics": [item.to_dict() for item in self.leg_diagnostics],
        }


@dataclass(slots=True)
class OptionsProviderLiveEvidenceContract:
    provider_id: str
    provider_kind: str
    source_type: str
    live_enabled: bool
    dry_run: bool
    fixture: bool
    synthetic: bool
    stub: bool
    adapter_contract: bool
    tradeable_data: bool
    quote_freshness: str | None
    quote_as_of: str | None
    chain_freshness: str | None
    chain_as_of: str | None
    expiration_coverage: str
    bid_ask_coverage: str
    open_interest_coverage: str
    volume_coverage: str
    iv_coverage: str
    greeks_coverage: str
    iv_rank_authority: str
    event_calendar_authority: str
    provider_sla_status: str
    sandbox_or_production: str | None
    analysis_ready: bool
    decision_ready: bool
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerId": self.provider_id,
            "providerKind": self.provider_kind,
            "sourceType": self.source_type,
            "liveEnabled": self.live_enabled,
            "dryRun": self.dry_run,
            "fixture": self.fixture,
            "synthetic": self.synthetic,
            "stub": self.stub,
            "adapterContract": self.adapter_contract,
            "tradeableData": self.tradeable_data,
            "quoteFreshness": self.quote_freshness,
            "quoteAsOf": self.quote_as_of,
            "chainFreshness": self.chain_freshness,
            "chainAsOf": self.chain_as_of,
            "expirationCoverage": self.expiration_coverage,
            "bidAskCoverage": self.bid_ask_coverage,
            "openInterestCoverage": self.open_interest_coverage,
            "volumeCoverage": self.volume_coverage,
            "ivCoverage": self.iv_coverage,
            "greeksCoverage": self.greeks_coverage,
            "ivRankAuthority": self.iv_rank_authority,
            "eventCalendarAuthority": self.event_calendar_authority,
            "providerSlaStatus": self.provider_sla_status,
            "sandboxOrProduction": self.sandbox_or_production,
            "analysisReady": self.analysis_ready,
            "decisionReady": self.decision_ready,
            "reasonCodes": list(self.reason_codes),
        }


@dataclass(slots=True)
class OptionsStrategyGateDiagnostics:
    strategy_key: str
    gate_decision: str
    decision_grade: bool
    fail_closed_reason_codes: list[str] = field(default_factory=list)
    gate_issues: list[OptionsGateIssue] = field(default_factory=list)
    leg_diagnostics: list[OptionsLegGateDiagnostics] = field(default_factory=list)
    data_quality_gates: OptionsGateBucket = field(
        default_factory=lambda: OptionsGateBucket(status=OptionsGateStatus.CLEAR, decision_grade=True)
    )
    liquidity_gates: OptionsGateBucket = field(
        default_factory=lambda: OptionsGateBucket(status=OptionsGateStatus.CLEAR, decision_grade=True)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategyKey": self.strategy_key,
            "gateDecision": self.gate_decision,
            "decisionGrade": self.decision_grade,
            "failClosedReasonCodes": list(self.fail_closed_reason_codes),
            "gateIssues": [item.to_dict() for item in self.gate_issues],
            "legDiagnostics": [item.to_dict() for item in self.leg_diagnostics],
            "dataQualityGates": self.data_quality_gates.to_dict(),
            "liquidityGates": self.liquidity_gates.to_dict(),
        }


def _issue(
    *,
    code: str,
    category: str,
    status: OptionsGateStatus,
    label: str,
    leg_index: int | None = None,
    contract_symbol: str | None = None,
) -> OptionsGateIssue:
    return OptionsGateIssue(
        code=code,
        category=category,
        status=status,
        label=label,
        decision_grade=False,
        leg_index=leg_index,
        contract_symbol=contract_symbol,
    )


def _provider_authority_issue(code: str) -> OptionsGateIssue:
    return _issue(
        code=code,
        category="provider_authority",
        status=OptionsGateStatus.BLOCKED,
        label=_PROVIDER_AUTHORITY_LABELS[code],
    )


def _normalize_provider_id(value: Any) -> str:
    return _coerce_text(value).lower().replace("-", "_")


def _internal_provider_authority_tier(
    *,
    provider_id: str,
    source_type: str,
    fixture_only: bool,
    live_enabled: bool,
    tradeable_data: bool,
    dry_run: bool,
    synthetic: bool,
    stub: bool,
    adapter_contract: bool,
) -> OptionsProviderAuthorityTier | None:
    normalized_provider = _normalize_provider_id(provider_id)
    normalized_source_type = _normalize_provider_id(source_type)
    if not normalized_provider:
        return None
    if any((fixture_only, dry_run, synthetic, stub, adapter_contract)):
        return OptionsProviderAuthorityTier.LIVE_OBSERVATION_ONLY
    if normalized_source_type in {"fixture", "synthetic", "dry_run", "delayed_dry_run", "live_stub"}:
        return OptionsProviderAuthorityTier.LIVE_OBSERVATION_ONLY
    del live_enabled, tradeable_data
    tier = _INTERNAL_PROVIDER_AUTHORITY_TIER_POLICY.get(normalized_provider)
    if tier is None:
        return None
    return OptionsProviderAuthorityTier(tier)


def build_options_provider_authority_contract(
    *,
    provider_id: str,
    source_type: str,
    fixture_only: bool,
    live_enabled: bool,
    tradeable_data: bool,
    dry_run: bool = False,
    synthetic: bool = False,
    stub: bool = False,
    adapter_contract: bool = False,
    provider_decision_authority_claim: Any = None,
    recommendation_authority_claim: Any = None,
    notes: Sequence[Any] | None = None,
    live_probe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    tier = _internal_provider_authority_tier(
        provider_id=provider_id,
        source_type=source_type,
        fixture_only=fixture_only,
        live_enabled=live_enabled,
        tradeable_data=tradeable_data,
        dry_run=dry_run,
        synthetic=synthetic,
        stub=stub,
        adapter_contract=adapter_contract,
    )
    payload: dict[str, Any] = {
        "providerId": provider_id,
        "sourceType": source_type,
        "fixtureOnly": fixture_only,
        "liveEnabled": live_enabled,
        "tradeableData": tradeable_data,
        "dryRun": dry_run,
        "synthetic": synthetic,
        "stub": stub,
        "adapterContract": adapter_contract,
        "authorityPolicySource": INTERNAL_OPTIONS_PROVIDER_AUTHORITY_POLICY_SOURCE,
        "authorityTier": tier.value if tier is not None else None,
        "providerDecisionAuthorityClaim": provider_decision_authority_claim,
        "recommendationAuthorityClaim": recommendation_authority_claim,
        "notes": list(notes or []),
    }
    if live_probe is not None:
        payload["liveProbe"] = _coerce_mapping(live_probe)
    return payload


def _provider_authority_flag(data: Mapping[str, Any], *keys: str) -> bool | None:
    for key in keys:
        if key in data:
            return _coerce_bool(data.get(key))
    return None


def _provider_authority_source_code(data: Mapping[str, Any]) -> str | None:
    text = _flatten_authority_text(data)
    if _provider_authority_flag(data, "adapterContract", "adapter_contract") is True or _contains_marker(
        text,
        markers=("adapter_contract", "adapter-contract"),
    ):
        return "provider_adapter_contract_not_decision_grade"
    if _provider_authority_flag(data, "dryRun", "dry_run") is True or _contains_marker(
        text,
        markers=("dry_run", "dry-run"),
    ):
        return "provider_dry_run_not_decision_grade"
    if _provider_authority_flag(data, "stub") is True or _contains_marker(text, markers=("stub",)):
        return "provider_stub_not_decision_grade"
    if _provider_authority_flag(data, "fixtureOnly", "fixture_only") is True or _contains_marker(
        text,
        markers=("fixture",),
    ):
        return "provider_fixture_not_decision_grade"
    if _provider_authority_flag(data, "synthetic") is True or _contains_marker(text, markers=("synthetic",)):
        return "provider_synthetic_not_decision_grade"
    return None


def _provider_self_authority_claimed(data: Mapping[str, Any]) -> bool:
    return any(
        _provider_authority_flag(data, key) is True
        for key in (
            "providerDecisionAuthority",
            "provider_decision_authority",
            "recommendationAuthority",
            "recommendation_authority",
            "providerDecisionAuthorityClaim",
            "provider_decision_authority_claim",
            "recommendationAuthorityClaim",
            "recommendation_authority_claim",
        )
    )


def _provider_authority_tier(data: Mapping[str, Any]) -> OptionsProviderAuthorityTier | None:
    if data.get("authorityPolicySource") != INTERNAL_OPTIONS_PROVIDER_AUTHORITY_POLICY_SOURCE:
        return None
    try:
        return OptionsProviderAuthorityTier(_coerce_text(data.get("authorityTier")).lower())
    except ValueError:
        return None


def _provider_authority_issues(provider_authority: Mapping[str, Any] | None) -> list[OptionsGateIssue]:
    data = _coerce_mapping(provider_authority)
    if not data:
        return [_provider_authority_issue("provider_authority_missing")]

    issues: list[OptionsGateIssue] = []
    source_code = _provider_authority_source_code(data)
    if source_code is not None:
        issues.append(_provider_authority_issue(source_code))
    if _provider_self_authority_claimed(data):
        issues.append(_provider_authority_issue("provider_self_authority_ignored"))
    if _provider_authority_flag(data, "liveEnabled", "live_enabled") is not True:
        issues.append(_provider_authority_issue("provider_live_disabled"))
    if _provider_authority_flag(data, "tradeableData", "tradeable_data") is not True:
        issues.append(_provider_authority_issue("provider_tradeable_data_false"))
    authority_tier = _provider_authority_tier(data)
    if authority_tier is None:
        issues.append(_provider_authority_issue("provider_authority_tier_missing"))
    elif authority_tier == OptionsProviderAuthorityTier.LIVE_OBSERVATION_ONLY:
        issues.append(_provider_authority_issue("provider_authority_tier_observation_only"))
    elif authority_tier == OptionsProviderAuthorityTier.LIVE_ANALYSIS_GRADE:
        issues.append(_provider_authority_issue("provider_authority_tier_analysis_only"))
    elif authority_tier != OptionsProviderAuthorityTier.DECISION_GRADE:
        issues.append(_provider_authority_issue("provider_authority_policy_not_granted"))
    return issues


def _bucket_status(issues: Sequence[OptionsGateIssue]) -> OptionsGateStatus:
    priorities = {
        OptionsGateStatus.BLOCKED: 3,
        OptionsGateStatus.OBSERVE_ONLY: 2,
        OptionsGateStatus.MANUAL_REVIEW: 1,
        OptionsGateStatus.CLEAR: 0,
    }
    return max((issue.status for issue in issues), key=lambda item: priorities[item], default=OptionsGateStatus.CLEAR)


def _dedupe_codes(issues: Sequence[OptionsGateIssue]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for issue in issues:
        if issue.code not in seen:
            seen.add(issue.code)
            ordered.append(issue.code)
    return ordered


def _dedupe_reason_codes(codes: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for code in codes:
        text = _coerce_text(code).lower()
        if text in seen:
            continue
        if text not in _PROVIDER_LIVE_EVIDENCE_LABELS:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _live_evidence_text(value: Any, default: str = "unknown") -> str:
    text = _coerce_text(value).lower().replace("-", "_")
    return text or default


def _live_evidence_optional_text(value: Any) -> str | None:
    text = _coerce_text(value)
    return text or None


def _source_marker_flags(
    provider_id: str,
    source_type: str,
    notes: Sequence[Any] | None = None,
) -> dict[str, bool]:
    source_text = " ".join(
        _coerce_text(item).lower()
        for item in (provider_id, source_type, *(notes or []))
        if item is not None
    )
    return {
        "fixture": "fixture" in source_text,
        "synthetic": "synthetic" in source_text,
        "dry_run": "dry_run" in source_text or "dry-run" in source_text,
        "stub": "stub" in source_text,
        "adapter_contract": "adapter_contract" in source_text or "adapter-contract" in source_text,
    }


def _freshness_reason_code(prefix: str, freshness: Any) -> str | None:
    normalized = _live_evidence_text(freshness, default="")
    if not normalized:
        return f"live_evidence_{prefix}_freshness_missing"
    if normalized == "unknown":
        return f"live_evidence_{prefix}_freshness_unknown"
    if normalized not in _LIVE_EVIDENCE_FRESHNESS_READY:
        return f"live_evidence_{prefix}_freshness_not_fresh"
    return None


def _coverage_reason_code(field_name: str, coverage: Any) -> str | None:
    normalized = _live_evidence_text(coverage)
    if normalized == "complete":
        return None
    suffix = "partial" if normalized == "partial" else "missing"
    return f"live_evidence_{field_name}_coverage_{suffix}"


def _authority_missing(value: Any) -> bool:
    normalized = _live_evidence_text(value)
    return normalized not in _LIVE_EVIDENCE_AUTHORITY_READY


def build_options_provider_live_evidence_contract(
    *,
    provider_id: str,
    source_type: str,
    live_enabled: bool,
    tradeable_data: bool,
    provider_kind: str = "market_data",
    dry_run: bool = False,
    fixture: bool = False,
    synthetic: bool = False,
    stub: bool = False,
    adapter_contract: bool = False,
    quote_freshness: Any = None,
    quote_as_of: Any = None,
    chain_freshness: Any = None,
    chain_as_of: Any = None,
    expiration_coverage: Any = "missing",
    bid_ask_coverage: Any = "missing",
    open_interest_coverage: Any = "missing",
    volume_coverage: Any = "missing",
    iv_coverage: Any = "missing",
    greeks_coverage: Any = "missing",
    iv_rank_authority: Any = None,
    event_calendar_authority: Any = None,
    requires_event_calendar: bool = False,
    provider_sla_status: Any = "unknown",
    sandbox_or_production: Any = None,
    provider_decision_authority_claim: Any = None,
    recommendation_authority_claim: Any = None,
    notes: Sequence[Any] | None = None,
) -> dict[str, Any]:
    normalized_provider_id = _normalize_provider_id(provider_id) or "unknown"
    normalized_source_type = _live_evidence_text(source_type)
    marker_flags = _source_marker_flags(normalized_provider_id, normalized_source_type, notes)
    fixture = fixture or marker_flags["fixture"]
    synthetic = synthetic or marker_flags["synthetic"]
    dry_run = dry_run or marker_flags["dry_run"]
    stub = stub or marker_flags["stub"]
    adapter_contract = adapter_contract or marker_flags["adapter_contract"]

    reason_codes: list[str] = []
    if _coerce_bool(provider_decision_authority_claim) is True or _coerce_bool(recommendation_authority_claim) is True:
        reason_codes.append("live_evidence_provider_self_claim_ignored")
    if not live_enabled:
        reason_codes.append("live_evidence_live_disabled")
    if fixture:
        reason_codes.append("live_evidence_fixture_blocked")
    if synthetic:
        reason_codes.append("live_evidence_synthetic_blocked")
    if dry_run:
        reason_codes.append("live_evidence_dry_run_blocked")
    if stub:
        reason_codes.append("live_evidence_stub_blocked")
    if adapter_contract:
        reason_codes.append("live_evidence_adapter_contract_blocked")
    if not tradeable_data:
        reason_codes.append("live_evidence_tradeable_data_false")

    quote_freshness_code = _freshness_reason_code("quote", quote_freshness)
    if quote_freshness_code is not None:
        reason_codes.append(quote_freshness_code)
    chain_freshness_code = _freshness_reason_code("chain", chain_freshness)
    if chain_freshness_code is not None:
        reason_codes.append(chain_freshness_code)

    coverage_values = {
        "expiration": _live_evidence_text(expiration_coverage),
        "bid_ask": _live_evidence_text(bid_ask_coverage),
        "open_interest": _live_evidence_text(open_interest_coverage),
        "volume": _live_evidence_text(volume_coverage),
        "iv": _live_evidence_text(iv_coverage),
        "greeks": _live_evidence_text(greeks_coverage),
    }
    for field_name in _LIVE_EVIDENCE_COVERAGE_FIELDS:
        coverage_code = _coverage_reason_code(field_name, coverage_values[field_name])
        if coverage_code is not None:
            reason_codes.append(coverage_code)

    iv_rank_authority_text = _live_evidence_text(iv_rank_authority, default="missing")
    event_calendar_authority_text = (
        _live_evidence_text(event_calendar_authority, default="missing")
        if requires_event_calendar
        else _live_evidence_text(event_calendar_authority, default="not_required")
    )
    if _authority_missing(iv_rank_authority_text):
        reason_codes.append("live_evidence_iv_rank_authority_missing")
    if requires_event_calendar and _authority_missing(event_calendar_authority_text):
        reason_codes.append("live_evidence_event_calendar_authority_missing")

    deduped_reason_codes = _dedupe_reason_codes(reason_codes)
    analysis_blocking_codes = [
        code
        for code in deduped_reason_codes
        if code
        not in {
            "live_evidence_iv_rank_authority_missing",
            "live_evidence_event_calendar_authority_missing",
            "live_evidence_provider_self_claim_ignored",
        }
    ]
    decision_blocking_codes = list(deduped_reason_codes)
    analysis_ready = not analysis_blocking_codes
    decision_ready = analysis_ready and not decision_blocking_codes

    return OptionsProviderLiveEvidenceContract(
        provider_id=normalized_provider_id,
        provider_kind=_live_evidence_text(provider_kind),
        source_type=normalized_source_type,
        live_enabled=bool(live_enabled),
        dry_run=bool(dry_run),
        fixture=bool(fixture),
        synthetic=bool(synthetic),
        stub=bool(stub),
        adapter_contract=bool(adapter_contract),
        tradeable_data=bool(tradeable_data),
        quote_freshness=_live_evidence_optional_text(quote_freshness),
        quote_as_of=_live_evidence_optional_text(quote_as_of),
        chain_freshness=_live_evidence_optional_text(chain_freshness),
        chain_as_of=_live_evidence_optional_text(chain_as_of),
        expiration_coverage=coverage_values["expiration"],
        bid_ask_coverage=coverage_values["bid_ask"],
        open_interest_coverage=coverage_values["open_interest"],
        volume_coverage=coverage_values["volume"],
        iv_coverage=coverage_values["iv"],
        greeks_coverage=coverage_values["greeks"],
        iv_rank_authority=iv_rank_authority_text,
        event_calendar_authority=event_calendar_authority_text,
        provider_sla_status=_live_evidence_text(provider_sla_status),
        sandbox_or_production=_live_evidence_optional_text(sandbox_or_production),
        analysis_ready=analysis_ready,
        decision_ready=decision_ready,
        reason_codes=deduped_reason_codes,
    ).to_dict()


def _mapping_value(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data.get(key) not in (None, ""):
            return data.get(key)
    return None


def _coverage_from_items(items: Sequence[Mapping[str, Any]], predicate) -> str:
    if not items:
        return "missing"
    present = sum(1 for item in items if predicate(item))
    if present == len(items):
        return "complete"
    if present == 0:
        return "missing"
    return "partial"


def _expiration_coverage(
    expirations: Sequence[Mapping[str, Any]],
    contracts: Sequence[Mapping[str, Any]],
) -> str:
    if not expirations and not contracts:
        return "missing"
    expiration_rows_complete = bool(expirations) and all(
        _mapping_value(item, "date", "expiration") for item in expirations
    )
    contract_rows_complete = bool(contracts) and all(_mapping_value(item, "expiration") for item in contracts)
    if expiration_rows_complete and contract_rows_complete:
        return "complete"
    if expiration_rows_complete or contract_rows_complete:
        return "partial"
    return "missing"


def _has_bid_ask(item: Mapping[str, Any]) -> bool:
    return _mapping_value(item, "bid") is not None and _mapping_value(item, "ask") is not None


def _has_open_interest(item: Mapping[str, Any]) -> bool:
    return _mapping_value(item, "openInterest", "open_interest") is not None


def _has_volume(item: Mapping[str, Any]) -> bool:
    return _mapping_value(item, "volume") is not None


def _has_iv(item: Mapping[str, Any]) -> bool:
    return _mapping_value(item, "impliedVolatility", "implied_volatility") is not None


def _has_complete_greeks(item: Mapping[str, Any]) -> bool:
    greeks = _coerce_mapping(item.get("greeks"))
    return all(greeks.get(name) is not None for name in ("delta", "gamma", "theta", "vega", "rho"))


def build_options_provider_live_evidence_from_snapshot(
    snapshot: Mapping[str, Any],
    *,
    iv_rank_authority: Any = None,
    event_calendar_authority: Any = None,
    requires_event_calendar: bool = False,
    provider_sla_status: Any = None,
    sandbox_or_production: Any = None,
) -> dict[str, Any]:
    data = _coerce_mapping(snapshot)
    capabilities = _coerce_mapping(data.get("providerCapabilities"))
    data_quality = _coerce_mapping(data.get("dataQuality"))
    underlying = _coerce_mapping(data.get("underlying"))
    contracts = [
        _coerce_mapping(item)
        for item in list(data.get("contracts") or [])
        if isinstance(item, Mapping)
    ]
    expirations = [
        _coerce_mapping(item)
        for item in list(data.get("expirations") or [])
        if isinstance(item, Mapping)
    ]
    source_type = _mapping_value(capabilities, "sourceType", "source_type") or data.get("source") or "unknown"
    source_notes = [
        *list(capabilities.get("notes") or []),
        *list(data_quality.get("hints") or []),
        data.get("providerQuality"),
        data.get("source"),
        underlying.get("source"),
        underlying.get("freshness"),
    ]
    first_contract = contracts[0] if contracts else {}
    return build_options_provider_live_evidence_contract(
        provider_id=str(
            data.get("providerName")
            or capabilities.get("providerName")
            or data.get("source")
            or "unknown"
        ),
        provider_kind="market_data",
        source_type=str(source_type),
        live_enabled=_coerce_bool(capabilities.get("liveEnabled")) is True,
        tradeable_data=_coerce_bool(
            _mapping_value(capabilities, "tradeableData", "tradeable_data")
            if _mapping_value(capabilities, "tradeableData", "tradeable_data") is not None
            else data_quality.get("tradeable")
        )
        is True,
        fixture=_coerce_bool(_mapping_value(capabilities, "fixtureOnly", "fixture_only")) is True,
        quote_freshness=_mapping_value(underlying, "freshness"),
        quote_as_of=_mapping_value(underlying, "asOf", "as_of") or data.get("chainAsOf"),
        chain_freshness=(
            _mapping_value(data, "chainFreshness", "freshness")
            or _mapping_value(first_contract, "freshness")
            or _mapping_value(underlying, "freshness")
        ),
        chain_as_of=_mapping_value(data, "chainAsOf", "chain_as_of") or _mapping_value(first_contract, "asOf", "as_of"),
        expiration_coverage=_expiration_coverage(expirations, contracts),
        bid_ask_coverage=_coverage_from_items(contracts, _has_bid_ask),
        open_interest_coverage=_coverage_from_items(contracts, _has_open_interest),
        volume_coverage=_coverage_from_items(contracts, _has_volume),
        iv_coverage=_coverage_from_items(contracts, _has_iv),
        greeks_coverage=_coverage_from_items(contracts, _has_complete_greeks),
        iv_rank_authority=iv_rank_authority,
        event_calendar_authority=event_calendar_authority,
        requires_event_calendar=requires_event_calendar,
        provider_sla_status=provider_sla_status
        or capabilities.get("providerSlaStatus")
        or data.get("providerSlaStatus")
        or "unknown",
        sandbox_or_production=sandbox_or_production
        or capabilities.get("sandboxOrProduction")
        or data.get("sandboxOrProduction"),
        provider_decision_authority_claim=_mapping_value(
            data,
            "providerDecisionAuthority",
            "provider_decision_authority",
        )
        if _mapping_value(data, "providerDecisionAuthority", "provider_decision_authority") is not None
        else _mapping_value(capabilities, "providerDecisionAuthority", "provider_decision_authority"),
        recommendation_authority_claim=_mapping_value(
            data,
            "recommendationAuthority",
            "recommendation_authority",
        )
        if _mapping_value(data, "recommendationAuthority", "recommendation_authority") is not None
        else _mapping_value(capabilities, "recommendationAuthority", "recommendation_authority"),
        notes=source_notes,
    )


def _provider_live_evidence_issues(
    provider_live_evidence: Mapping[str, Any] | None,
    *,
    required: bool = False,
) -> list[OptionsGateIssue]:
    data = _coerce_mapping(provider_live_evidence)
    if required and not data:
        return [
            _issue(
                code="provider_live_evidence_missing",
                category="provider_live_evidence",
                status=OptionsGateStatus.BLOCKED,
                label=_PROVIDER_LIVE_EVIDENCE_LABELS["provider_live_evidence_missing"],
            )
        ]

    reason_codes = data.get("reasonCodes") if data else []
    issues: list[OptionsGateIssue] = []
    for code in _dedupe_reason_codes(list(reason_codes or [])):
        issues.append(
            _issue(
                code=code,
                category="provider_live_evidence",
                status=OptionsGateStatus.BLOCKED,
                label=_PROVIDER_LIVE_EVIDENCE_LABELS[code],
            )
        )
    return issues


def _bucket_from_leg_diagnostics(
    issues: Sequence[OptionsGateIssue],
    leg_diagnostics: Sequence[OptionsLegGateDiagnostics],
) -> OptionsGateBucket:
    status = _bucket_status(issues)
    decision_grade = status is OptionsGateStatus.CLEAR
    return OptionsGateBucket(
        status=status,
        issue_codes=_dedupe_codes(issues),
        decision_grade=decision_grade,
        leg_diagnostics=list(leg_diagnostics),
    )


def _strategy_gate_decision(
    data_quality_status: OptionsGateStatus,
    liquidity_status: OptionsGateStatus,
) -> tuple[str, bool]:
    if OptionsGateStatus.BLOCKED in {data_quality_status, liquidity_status}:
        return "数据不足，禁止判断", False
    if OptionsGateStatus.OBSERVE_ONLY in {data_quality_status, liquidity_status}:
        return "仅观察", False
    return "需人工复核", data_quality_status is OptionsGateStatus.CLEAR and liquidity_status is OptionsGateStatus.CLEAR


def _safe_contract_symbol(contract: Any) -> str | None:
    symbol = _coerce_text(getattr(contract, "contract_symbol", None) or getattr(contract, "symbol", None))
    lowered = symbol.lower()
    if symbol and not any(marker in lowered for marker in _SECRET_MARKERS):
        return symbol
    return None


def _source_code(
    source_type: str,
    contract_source: str,
    freshness: str,
) -> str | None:
    text = " ".join(item for item in (source_type, contract_source, freshness) if item).lower()
    if "dry_run" in text or "dry-run" in text:
        return "dry_run_source_not_decision_grade"
    if "synthetic" in text:
        return "synthetic_source_not_decision_grade"
    if "fixture" in text:
        return "fixture_source_not_decision_grade"
    if "fallback" in text:
        return "fallback_source_not_decision_grade"
    if freshness == "stale" or " stale" in f" {text}":
        return "stale_freshness_not_decision_grade"
    if freshness == "unknown" or not freshness:
        return "unknown_freshness_not_decision_grade"
    return None


def _source_issue(
    source_type: str,
    contract_source: str,
    freshness: str,
    *,
    leg_index: int,
    contract_symbol: str | None,
) -> OptionsGateIssue | None:
    code = _source_code(source_type, contract_source, freshness)
    if code is None:
        if freshness == "delayed" or source_type == "delayed":
            return _issue(
                code="delayed_data_requires_manual_review",
                category="freshness",
                status=OptionsGateStatus.MANUAL_REVIEW,
                label="延迟数据需要人工复核",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        return None
    labels = {
        "synthetic_source_not_decision_grade": "合成数据不能作为决策级证据",
        "fixture_source_not_decision_grade": "样例数据不能作为决策级证据",
        "fallback_source_not_decision_grade": "fallback 数据不能作为决策级证据",
        "dry_run_source_not_decision_grade": "dry-run 数据不能作为决策级证据",
        "stale_freshness_not_decision_grade": "陈旧数据不能作为决策级证据",
        "unknown_freshness_not_decision_grade": "未知新鲜度数据不能作为决策级证据",
    }
    return _issue(
        code=code,
        category="freshness",
        status=OptionsGateStatus.BLOCKED,
        label=labels[code],
        leg_index=leg_index,
        contract_symbol=contract_symbol,
    )


def _spread_pct(contract: Any) -> float | None:
    explicit = _coerce_float(getattr(contract, "spread_pct", None))
    if explicit is not None:
        return explicit
    bid = _coerce_float(getattr(contract, "bid", None))
    ask = _coerce_float(getattr(contract, "ask", None))
    mid = _coerce_float(getattr(contract, "mid", None))
    if mid is None and bid is not None and ask is not None:
        mid = (bid + ask) / 2
    if bid is None or ask is None or mid is None or mid <= 0:
        return None
    return round(((ask - bid) / mid) * 100, 2)


def _add_contract_issues(
    *,
    strategy_key: str,
    contract: Any,
    leg_index: int,
    source_type: str,
    data_quality_issues: list[OptionsGateIssue],
    liquidity_issues: list[OptionsGateIssue],
) -> tuple[OptionsGateStatus, OptionsGateStatus]:
    contract_symbol = _safe_contract_symbol(contract)
    contract_source = _coerce_text(getattr(contract, "source", None))
    freshness = _coerce_text(getattr(contract, "freshness", None)).lower() or "unknown"

    source_issue = _source_issue(source_type, contract_source, freshness, leg_index=leg_index, contract_symbol=contract_symbol)
    if source_issue is not None:
        data_quality_issues.append(source_issue)

    contract_identity_fields = {
        "contract_symbol": contract_symbol,
        "side": _coerce_text(getattr(contract, "side", None)),
        "expiration": _coerce_text(getattr(contract, "expiration", None)),
        "strike": _coerce_float(getattr(contract, "strike", None)),
        "multiplier": _coerce_int(getattr(contract, "multiplier", None)),
    }
    if (
        not contract_identity_fields["contract_symbol"]
        or not contract_identity_fields["side"]
        or not contract_identity_fields["expiration"]
        or contract_identity_fields["strike"] is None
        or contract_identity_fields["strike"] <= 0
        or contract_identity_fields["multiplier"] is None
        or contract_identity_fields["multiplier"] <= 0
    ):
        data_quality_issues.append(
            _issue(
                code="missing_contract_identity",
                category="contract_identity",
                status=OptionsGateStatus.BLOCKED,
                label="合约身份字段不完整",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )

    dte = _coerce_int(getattr(contract, "dte", None))
    if dte is None or dte <= 0:
        data_quality_issues.append(
            _issue(
                code="missing_dte",
                category="contract_identity",
                status=OptionsGateStatus.BLOCKED,
                label="到期天数缺失或无效",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )

    bid = _coerce_float(getattr(contract, "bid", None))
    ask = _coerce_float(getattr(contract, "ask", None))
    mid = _coerce_float(getattr(contract, "mid", None))
    if bid is None or ask is None:
        liquidity_issues.append(
            _issue(
                code="missing_bid_ask",
                category="liquidity",
                status=OptionsGateStatus.BLOCKED,
                label="缺少 bid/ask",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )
    elif bid <= 0 or ask <= 0 or ask < bid:
        liquidity_issues.append(
            _issue(
                code="invalid_bid_ask",
                category="liquidity",
                status=OptionsGateStatus.BLOCKED,
                label="bid/ask 无效",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )
    if mid is None or mid <= 0:
        liquidity_issues.append(
            _issue(
                code="invalid_mid_price",
                category="liquidity",
                status=OptionsGateStatus.BLOCKED,
                label="mid 无效",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )

    spread_pct = _spread_pct(contract)
    if spread_pct is not None:
        if spread_pct > 20:
            liquidity_issues.append(
                _issue(
                    code="wide_bid_ask_spread",
                    category="liquidity",
                    status=OptionsGateStatus.BLOCKED,
                    label="价差过宽",
                    leg_index=leg_index,
                    contract_symbol=contract_symbol,
                )
            )
        elif spread_pct > 10:
            liquidity_issues.append(
                _issue(
                    code="wide_bid_ask_spread",
                    category="liquidity",
                    status=OptionsGateStatus.MANUAL_REVIEW,
                    label="价差偏宽，需要人工复核",
                    leg_index=leg_index,
                    contract_symbol=contract_symbol,
                )
            )

    volume = _coerce_int(getattr(contract, "volume", None))
    if volume is None:
        liquidity_issues.append(
            _issue(
                code="missing_volume",
                category="liquidity",
                status=OptionsGateStatus.BLOCKED,
                label="缺少成交量",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )
    elif volume < 50:
        liquidity_issues.append(
            _issue(
                code="weak_volume",
                category="liquidity",
                status=OptionsGateStatus.OBSERVE_ONLY,
                label="成交量不足，仅适合观察",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )
    elif volume < 100:
        liquidity_issues.append(
            _issue(
                code="weak_volume",
                category="liquidity",
                status=OptionsGateStatus.MANUAL_REVIEW,
                label="成交量偏弱，需要人工复核",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )

    open_interest = _coerce_int(getattr(contract, "open_interest", None))
    if open_interest is None:
        liquidity_issues.append(
            _issue(
                code="missing_open_interest",
                category="liquidity",
                status=OptionsGateStatus.BLOCKED,
                label="缺少持仓量",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )
    elif open_interest < 100:
        liquidity_issues.append(
            _issue(
                code="weak_open_interest",
                category="liquidity",
                status=OptionsGateStatus.BLOCKED,
                label="持仓量低于最低门槛",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )
    elif open_interest < 500:
        liquidity_issues.append(
            _issue(
                code="weak_open_interest",
                category="liquidity",
                status=OptionsGateStatus.MANUAL_REVIEW,
                label="持仓量偏弱，需要人工复核",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )

    implied_volatility = _coerce_float(getattr(contract, "implied_volatility", None))
    if implied_volatility is None:
        data_quality_issues.append(
            _issue(
                code="missing_iv",
                category="iv_greeks",
                status=OptionsGateStatus.BLOCKED,
                label="缺少隐含波动率",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )

    greeks = getattr(contract, "greeks", None)
    if greeks is None:
        data_quality_issues.append(
            _issue(
                code="missing_greeks",
                category="iv_greeks",
                status=OptionsGateStatus.BLOCKED,
                label="缺少 Greeks",
                leg_index=leg_index,
                contract_symbol=contract_symbol,
            )
        )
    else:
        missing = [
            name
            for name in ("delta", "gamma", "theta", "vega", "rho")
            if getattr(greeks, name, None) is None
        ]
        if missing:
            data_quality_issues.append(
                _issue(
                    code="missing_greeks",
                    category="iv_greeks",
                    status=OptionsGateStatus.BLOCKED,
                    label="Greeks 不完整",
                    leg_index=leg_index,
                    contract_symbol=contract_symbol,
                )
            )

    return _bucket_status(data_quality_issues), _bucket_status(liquidity_issues)


def evaluate_options_data_quality_gates(
    *,
    strategy_key: str,
    contracts: Sequence[Any],
    chain_as_of: str | None,
    source_type: str,
    iv_rank_status: str,
    iv_rank_source: str | None,
    iv_percentile: float | None,
    expected_move_source: str,
    event_calendar: Mapping[str, Any] | None = None,
    requires_event_calendar: bool = False,
    provider_authority: Mapping[str, Any] | None = None,
    provider_live_evidence: Mapping[str, Any] | None = None,
) -> OptionsStrategyGateDiagnostics:
    data_quality_issues: list[OptionsGateIssue] = []
    liquidity_issues: list[OptionsGateIssue] = []

    if strategy_key not in SUPPORTED_OPTIONS_STRATEGY_KEYS:
        issue = _issue(
            code="unsupported_strategy",
            category="strategy_support",
            status=OptionsGateStatus.BLOCKED,
            label="当前策略不受支持",
        )
        return OptionsStrategyGateDiagnostics(
            strategy_key=strategy_key,
            gate_decision="数据不足，禁止判断",
            decision_grade=False,
            fail_closed_reason_codes=[issue.code],
            gate_issues=[issue],
            leg_diagnostics=[],
            data_quality_gates=OptionsGateBucket(
                status=OptionsGateStatus.BLOCKED,
                issue_codes=[issue.code],
                decision_grade=False,
                leg_diagnostics=[],
            ),
            liquidity_gates=OptionsGateBucket(
                status=OptionsGateStatus.CLEAR,
                issue_codes=[],
                decision_grade=True,
                leg_diagnostics=[],
            ),
        )

    if not contracts:
        data_quality_issues.append(
            _issue(
                code="missing_contract_identity",
                category="contract_identity",
                status=OptionsGateStatus.BLOCKED,
                label="缺少策略腿信息",
            )
        )

    leg_diagnostics: list[OptionsLegGateDiagnostics] = []
    for leg_index, contract in enumerate(contracts):
        dq_before = len(data_quality_issues)
        liq_before = len(liquidity_issues)
        self_source_type = _coerce_text(source_type).lower() or "unknown"
        _add_contract_issues(
            strategy_key=strategy_key,
            contract=contract,
            leg_index=leg_index,
            source_type=self_source_type,
            data_quality_issues=data_quality_issues,
            liquidity_issues=liquidity_issues,
        )
        leg_data_quality = _bucket_status(data_quality_issues[dq_before:])
        leg_liquidity = _bucket_status(liquidity_issues[liq_before:])
        leg_diagnostics.append(
            OptionsLegGateDiagnostics(
                leg_index=leg_index,
                contract_symbol=_safe_contract_symbol(contract),
                data_quality_status=leg_data_quality,
                liquidity_status=leg_liquidity,
                issue_codes=_dedupe_codes([*data_quality_issues[dq_before:], *liquidity_issues[liq_before:]]),
                decision_grade=(
                    leg_data_quality is OptionsGateStatus.CLEAR
                    and leg_liquidity is OptionsGateStatus.CLEAR
                ),
            )
        )

    iv_rank_source_text = _coerce_text(iv_rank_source).lower()
    if iv_rank_status != "available" or iv_percentile is None:
        data_quality_issues.append(
            _issue(
                code="missing_iv_rank_or_percentile",
                category="iv_greeks",
                status=OptionsGateStatus.BLOCKED,
                label="缺少 IV Rank/Percentile",
            )
        )
    elif _contains_marker(iv_rank_source_text, markers=("fixture", "synthetic", "fallback", "dry_run", "dry-run")):
        data_quality_issues.append(
            _issue(
                code="iv_rank_not_decision_grade",
                category="iv_greeks",
                status=OptionsGateStatus.BLOCKED,
                label="IV Rank/Percentile 来源不是决策级证据",
            )
        )

    if expected_move_source == "unavailable":
        data_quality_issues.append(
            _issue(
                code="expected_move_unavailable",
                category="data_quality",
                status=OptionsGateStatus.MANUAL_REVIEW,
                label="缺少 expected move，需要人工复核",
            )
        )

    if requires_event_calendar and not event_calendar:
        data_quality_issues.append(
            _issue(
                code="missing_event_calendar",
                category="event_calendar",
                status=OptionsGateStatus.BLOCKED,
                label="缺少事件日历",
            )
        )

    data_quality_gates = _bucket_from_leg_diagnostics(
        data_quality_issues,
        leg_diagnostics,
    )
    liquidity_gates = _bucket_from_leg_diagnostics(liquidity_issues, leg_diagnostics)
    provider_authority_issues = _provider_authority_issues(provider_authority)
    gate_decision, decision_grade = _strategy_gate_decision(
        data_quality_gates.status,
        liquidity_gates.status,
    )
    provider_live_evidence_issues = _provider_live_evidence_issues(
        provider_live_evidence,
        required=decision_grade and not provider_authority_issues,
    )
    if provider_authority_issues or provider_live_evidence_issues:
        gate_decision = "数据不足，禁止判断"
        decision_grade = False
    gate_issues = [
        *data_quality_issues,
        *liquidity_issues,
        *provider_authority_issues,
        *provider_live_evidence_issues,
    ]
    return OptionsStrategyGateDiagnostics(
        strategy_key=strategy_key,
        gate_decision=gate_decision,
        decision_grade=decision_grade,
        fail_closed_reason_codes=[] if decision_grade else _dedupe_codes(gate_issues),
        gate_issues=gate_issues,
        leg_diagnostics=leg_diagnostics,
        data_quality_gates=data_quality_gates,
        liquidity_gates=liquidity_gates,
    )
