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
    "provider_fixture_not_decision_grade": "fixture provider 不能作为决策级证据",
    "provider_synthetic_not_decision_grade": "synthetic provider 不能作为决策级证据",
    "provider_dry_run_not_decision_grade": "dry-run provider 不能作为决策级证据",
    "provider_stub_not_decision_grade": "stub provider 不能作为决策级证据",
    "provider_adapter_contract_not_decision_grade": "adapter contract provider 不能作为决策级证据",
    "provider_live_disabled": "provider live 模式未启用",
    "provider_tradeable_data_false": "provider 未声明 tradeable data",
    "provider_decision_authority_not_granted": "provider 未显式授予决策级权限",
}


class OptionsGateStatus(str, Enum):
    CLEAR = "clear"
    BLOCKED = "blocked"
    OBSERVE_ONLY = "observe_only"
    MANUAL_REVIEW = "manual_review"


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


def _provider_authority_granted(data: Mapping[str, Any]) -> bool:
    return any(
        _provider_authority_flag(data, key) is True
        for key in (
            "providerDecisionAuthority",
            "provider_decision_authority",
            "recommendationAuthority",
            "recommendation_authority",
        )
    )


def _provider_authority_issues(provider_authority: Mapping[str, Any] | None) -> list[OptionsGateIssue]:
    data = _coerce_mapping(provider_authority)
    if not data:
        return [_provider_authority_issue("provider_authority_missing")]

    issues: list[OptionsGateIssue] = []
    source_code = _provider_authority_source_code(data)
    if source_code is not None:
        issues.append(_provider_authority_issue(source_code))
    if _provider_authority_flag(data, "liveEnabled", "live_enabled") is not True:
        issues.append(_provider_authority_issue("provider_live_disabled"))
    if _provider_authority_flag(data, "tradeableData", "tradeable_data") is not True:
        issues.append(_provider_authority_issue("provider_tradeable_data_false"))
    if not _provider_authority_granted(data):
        issues.append(_provider_authority_issue("provider_decision_authority_not_granted"))
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
    if provider_authority_issues:
        gate_decision = "数据不足，禁止判断"
        decision_grade = False
    gate_issues = [*data_quality_issues, *liquidity_issues, *provider_authority_issues]
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
