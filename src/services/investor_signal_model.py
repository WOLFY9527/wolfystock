# -*- coding: utf-8 -*-
"""Pure investor-readable signal vocabulary and fail-closed consumer projection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from src.contracts.source_confidence import evaluate_market_intelligence_trust


INVESTOR_SIGNAL_CONTRACT_VERSION = "investor_signal_contract_v1"
FORBIDDEN_CONSUMER_SAFE_FIELDS = frozenset(
    {
        "source",
        "sourceLabel",
        "sourceType",
        "providerId",
        "providerName",
        "providerRouting",
        "providerBudget",
        "routeDecision",
        "routeRequest",
        "adminDiagnostics",
        "adminNotes",
        "internalReasonCodes",
        "rawPayload",
    }
)
_AMBIGUOUS_SOURCE_VALUES = {"ambiguous", "mixed", "multiple", "unknown", "various"}
_DEGRADED_FRESHNESS_VALUES = {"stale", "partial", "fallback", "synthetic", "unavailable", "unknown", "error"}


class MarketRegimeLabel(str, Enum):
    RISK_ON = "risk_on"
    BALANCED = "balanced"
    RISK_OFF = "risk_off"
    MIXED = "mixed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class CapitalFlowRegimeLabel(str, Enum):
    INFLOW = "inflow"
    BALANCED = "balanced"
    OUTFLOW = "outflow"
    MIXED = "mixed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ThemeFlowStateLabel(str, Enum):
    LEADING = "leading"
    BROADENING = "broadening"
    ROTATING = "rotating"
    CROWDED = "crowded"
    FADING = "fading"
    MIXED = "mixed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ConfidenceLabel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BLOCKED = "blocked"


class InvestorSignalReasonCode(str, Enum):
    SOURCE_AUTHORITY_MISSING = "source_authority_missing"
    SOURCE_IDENTITY_MISSING = "source_identity_missing"
    SOURCE_IDENTITY_AMBIGUOUS = "source_identity_ambiguous"
    SCORE_RIGHTS_MISSING = "score_rights_missing"
    FALLBACK_SOURCE = "fallback_source"
    STALE_SOURCE = "stale_source"
    PARTIAL_SOURCE = "partial_source"
    SYNTHETIC_SOURCE = "synthetic_source"
    UNAVAILABLE_SOURCE = "unavailable_source"
    CONFLICTING_SIGNAL_INPUTS = "conflicting_signal_inputs"
    UNSUPPORTED_SIGNAL_LABEL = "unsupported_signal_label"
    CONFIDENCE_CAPPED = "confidence_capped"
    INTERNAL_DETAIL_REDACTED = "internal_detail_redacted"


class InvestorSignalContradictionCode(str, Enum):
    MARKET_REGIME_SIGNAL_MISMATCH = "market_regime_signal_mismatch"
    CAPITAL_FLOW_SIGNAL_MISMATCH = "capital_flow_signal_mismatch"
    THEME_FLOW_STATE_SIGNAL_MISMATCH = "theme_flow_state_signal_mismatch"
    MIXED_SIGNAL_INPUTS = "mixed_signal_inputs"


MARKET_REGIME_LABEL_VALUES = frozenset(item.value for item in MarketRegimeLabel)
CAPITAL_FLOW_REGIME_LABEL_VALUES = frozenset(item.value for item in CapitalFlowRegimeLabel)
THEME_FLOW_STATE_VALUES = frozenset(item.value for item in ThemeFlowStateLabel)
CONFIDENCE_LABEL_VALUES = frozenset(item.value for item in ConfidenceLabel)
REASON_CODE_VALUES = frozenset(item.value for item in InvestorSignalReasonCode)
CONTRADICTION_CODE_VALUES = frozenset(item.value for item in InvestorSignalContradictionCode)

_MARKET_REGIME_DISPLAY = {
    MarketRegimeLabel.RISK_ON: "风险偏好回升",
    MarketRegimeLabel.BALANCED: "多空均衡观察",
    MarketRegimeLabel.RISK_OFF: "防御偏好升温",
    MarketRegimeLabel.MIXED: "信号分化",
    MarketRegimeLabel.INSUFFICIENT_EVIDENCE: "证据不足",
}
_CAPITAL_FLOW_DISPLAY = {
    CapitalFlowRegimeLabel.INFLOW: "资金净流入观察",
    CapitalFlowRegimeLabel.BALANCED: "资金均衡观察",
    CapitalFlowRegimeLabel.OUTFLOW: "资金净流出观察",
    CapitalFlowRegimeLabel.MIXED: "资金流向分化",
    CapitalFlowRegimeLabel.INSUFFICIENT_EVIDENCE: "证据不足",
}
_THEME_FLOW_DISPLAY = {
    ThemeFlowStateLabel.LEADING: "主线领涨观察",
    ThemeFlowStateLabel.BROADENING: "扩散跟涨观察",
    ThemeFlowStateLabel.ROTATING: "轮动切换观察",
    ThemeFlowStateLabel.CROWDED: "拥挤升温观察",
    ThemeFlowStateLabel.FADING: "热度回落观察",
    ThemeFlowStateLabel.MIXED: "主题分化",
    ThemeFlowStateLabel.INSUFFICIENT_EVIDENCE: "证据不足",
}
_CONFIDENCE_DISPLAY = {
    ConfidenceLabel.HIGH: "高",
    ConfidenceLabel.MEDIUM: "中",
    ConfidenceLabel.LOW: "低",
    ConfidenceLabel.BLOCKED: "禁止判断",
}
_CONFIDENCE_RANK = {
    ConfidenceLabel.BLOCKED: 0,
    ConfidenceLabel.LOW: 1,
    ConfidenceLabel.MEDIUM: 2,
    ConfidenceLabel.HIGH: 3,
}


@dataclass(frozen=True, slots=True)
class InvestorSignalContract:
    market_regime: MarketRegimeLabel
    capital_flow_regime: CapitalFlowRegimeLabel
    theme_flow_state: ThemeFlowStateLabel
    confidence_label: ConfidenceLabel
    freshness: str
    source_authority_allowed: bool
    reason_codes: tuple[str, ...]
    contradiction_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contractVersion": INVESTOR_SIGNAL_CONTRACT_VERSION,
            "diagnosticOnly": True,
            "observationOnly": True,
            "authorityGrant": False,
            "decisionGrade": False,
            "sourceAuthorityAllowed": self.source_authority_allowed,
            "scoreContributionAllowed": False,
            "marketRegime": self.market_regime.value,
            "marketRegimeLabel": _MARKET_REGIME_DISPLAY[self.market_regime],
            "capitalFlowRegime": self.capital_flow_regime.value,
            "capitalFlowLabel": _CAPITAL_FLOW_DISPLAY[self.capital_flow_regime],
            "themeFlowState": self.theme_flow_state.value,
            "themeFlowLabel": _THEME_FLOW_DISPLAY[self.theme_flow_state],
            "confidenceLabel": self.confidence_label.value,
            "confidenceText": _CONFIDENCE_DISPLAY[self.confidence_label],
            "freshness": self.freshness,
            "reasonCodes": list(self.reason_codes),
            "contradictionCodes": list(self.contradiction_codes),
        }


def build_consumer_safe_investor_signal(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return an observation-safe investor signal projection."""

    payload = dict(value or {})
    reason_codes: list[str] = _sanitize_reason_codes(payload.get("reasonCodes"))
    contradiction_codes = _sanitize_contradiction_codes(payload.get("contradictionCodes"))

    market_regime, market_invalid = _market_regime(payload.get("marketRegime"))
    capital_flow_regime, capital_invalid = _capital_flow_regime(payload.get("capitalFlowRegime"))
    theme_flow_state, theme_invalid = _theme_flow_state(payload.get("themeFlowState"))
    requested_confidence, confidence_invalid = _confidence_label(payload.get("confidenceLabel"))
    if market_invalid or capital_invalid or theme_invalid or confidence_invalid:
        _append_unique(reason_codes, InvestorSignalReasonCode.UNSUPPORTED_SIGNAL_LABEL.value)

    trust = evaluate_market_intelligence_trust(
        {
            "source": payload.get("source"),
            "sourceType": payload.get("sourceType"),
            "freshness": payload.get("freshness"),
            "isFallback": payload.get("isFallback"),
            "isStale": payload.get("isStale"),
            "isPartial": payload.get("isPartial"),
            "isSynthetic": payload.get("isSynthetic"),
            "isUnavailable": payload.get("isUnavailable"),
        }
    )
    freshness = _text(trust.get("freshness")).lower() or "unknown"

    if _bool(payload.get("isFallback")) or freshness == "fallback":
        _append_unique(reason_codes, InvestorSignalReasonCode.FALLBACK_SOURCE.value)
    if _bool(payload.get("isStale")) or freshness == "stale":
        _append_unique(reason_codes, InvestorSignalReasonCode.STALE_SOURCE.value)
    if _bool(payload.get("isPartial")) or freshness == "partial":
        _append_unique(reason_codes, InvestorSignalReasonCode.PARTIAL_SOURCE.value)
    if _bool(payload.get("isSynthetic")) or freshness == "synthetic":
        _append_unique(reason_codes, InvestorSignalReasonCode.SYNTHETIC_SOURCE.value)
    if _bool(payload.get("isUnavailable")) or freshness == "unavailable":
        _append_unique(reason_codes, InvestorSignalReasonCode.UNAVAILABLE_SOURCE.value)

    source_missing = not _text(payload.get("source"))
    source_ambiguous = _source_is_ambiguous(payload.get("source"))
    authority_explicit = payload.get("sourceAuthorityAllowed")
    score_explicit = payload.get("scoreContributionAllowed")

    if source_missing:
        _append_unique(reason_codes, InvestorSignalReasonCode.SOURCE_IDENTITY_MISSING.value)
    if source_ambiguous:
        _append_unique(reason_codes, InvestorSignalReasonCode.SOURCE_IDENTITY_AMBIGUOUS.value)
    if authority_explicit is not True:
        _append_unique(reason_codes, InvestorSignalReasonCode.SOURCE_AUTHORITY_MISSING.value)
    if score_explicit is not True:
        _append_unique(reason_codes, InvestorSignalReasonCode.SCORE_RIGHTS_MISSING.value)
    if contradiction_codes:
        _append_unique(reason_codes, InvestorSignalReasonCode.CONFLICTING_SIGNAL_INPUTS.value)

    blocked = bool(
        source_missing
        or source_ambiguous
        or authority_explicit is not True
        or score_explicit is not True
        or market_invalid
        or capital_invalid
        or theme_invalid
        or confidence_invalid
    )
    degraded = bool(
        freshness in _DEGRADED_FRESHNESS_VALUES
        or contradiction_codes
        or any(
            code in reason_codes
            for code in (
                InvestorSignalReasonCode.FALLBACK_SOURCE.value,
                InvestorSignalReasonCode.STALE_SOURCE.value,
                InvestorSignalReasonCode.PARTIAL_SOURCE.value,
                InvestorSignalReasonCode.SYNTHETIC_SOURCE.value,
                InvestorSignalReasonCode.UNAVAILABLE_SOURCE.value,
            )
        )
    )

    source_authority_allowed = bool(
        not blocked
        and not degraded
        and float(trust.get("scoreCap") or 0.0) >= 1.0
        and freshness in {"live", "fresh"}
    )
    confidence_label = _resolve_confidence_label(
        requested_confidence=requested_confidence,
        blocked=blocked,
        degraded=degraded,
    )
    if confidence_label is not requested_confidence:
        _append_unique(reason_codes, InvestorSignalReasonCode.CONFIDENCE_CAPPED.value)

    contract = InvestorSignalContract(
        market_regime=market_regime,
        capital_flow_regime=capital_flow_regime,
        theme_flow_state=theme_flow_state,
        confidence_label=confidence_label,
        freshness=freshness,
        source_authority_allowed=source_authority_allowed,
        reason_codes=tuple(reason_codes),
        contradiction_codes=tuple(contradiction_codes),
    )
    return contract.to_dict()


def _market_regime(value: Any) -> tuple[MarketRegimeLabel, bool]:
    normalized = _slug(value)
    for item in MarketRegimeLabel:
        if item.value == normalized:
            return item, False
    return MarketRegimeLabel.INSUFFICIENT_EVIDENCE, bool(normalized)


def _capital_flow_regime(value: Any) -> tuple[CapitalFlowRegimeLabel, bool]:
    normalized = _slug(value)
    for item in CapitalFlowRegimeLabel:
        if item.value == normalized:
            return item, False
    return CapitalFlowRegimeLabel.INSUFFICIENT_EVIDENCE, bool(normalized)


def _theme_flow_state(value: Any) -> tuple[ThemeFlowStateLabel, bool]:
    normalized = _slug(value)
    for item in ThemeFlowStateLabel:
        if item.value == normalized:
            return item, False
    return ThemeFlowStateLabel.INSUFFICIENT_EVIDENCE, bool(normalized)


def _confidence_label(value: Any) -> tuple[ConfidenceLabel, bool]:
    normalized = _slug(value)
    for item in ConfidenceLabel:
        if item.value == normalized:
            return item, False
    return ConfidenceLabel.BLOCKED, bool(normalized)


def _resolve_confidence_label(
    *,
    requested_confidence: ConfidenceLabel,
    blocked: bool,
    degraded: bool,
) -> ConfidenceLabel:
    if blocked:
        return ConfidenceLabel.BLOCKED
    if degraded:
        return ConfidenceLabel.LOW
    if requested_confidence is ConfidenceLabel.BLOCKED:
        return ConfidenceLabel.BLOCKED
    if _CONFIDENCE_RANK[requested_confidence] > _CONFIDENCE_RANK[ConfidenceLabel.HIGH]:
        return ConfidenceLabel.HIGH
    return requested_confidence


def _sanitize_reason_codes(value: Any) -> list[str]:
    result: list[str] = []
    for item in _string_list(value):
        code = _sanitize_reason_code(item)
        if code:
            _append_unique(result, code)
    return result


def _sanitize_reason_code(value: str) -> str | None:
    normalized = _slug(value)
    if not normalized:
        return None
    if normalized in REASON_CODE_VALUES:
        return normalized
    if any(marker in normalized for marker in ("unauthorized", "authority", "entitlement", "credential")):
        return InvestorSignalReasonCode.SOURCE_AUTHORITY_MISSING.value
    if "fallback" in normalized:
        return InvestorSignalReasonCode.FALLBACK_SOURCE.value
    if "stale" in normalized:
        return InvestorSignalReasonCode.STALE_SOURCE.value
    if "partial" in normalized or "coverage" in normalized:
        return InvestorSignalReasonCode.PARTIAL_SOURCE.value
    if any(marker in normalized for marker in ("synthetic", "fixture", "mock")):
        return InvestorSignalReasonCode.SYNTHETIC_SOURCE.value
    if any(marker in normalized for marker in ("unavailable", "missing", "timeout")):
        return InvestorSignalReasonCode.UNAVAILABLE_SOURCE.value
    if any(marker in normalized for marker in ("mixed", "contradict", "conflict")):
        return InvestorSignalReasonCode.CONFLICTING_SIGNAL_INPUTS.value
    if any(marker in normalized for marker in ("internal", "admin", "provider", "route", "budget", "debug")):
        return InvestorSignalReasonCode.INTERNAL_DETAIL_REDACTED.value
    return None


def _sanitize_contradiction_codes(value: Any) -> list[str]:
    result: list[str] = []
    for item in _string_list(value):
        code = _sanitize_contradiction_code(item)
        if code:
            _append_unique(result, code)
    return result


def _sanitize_contradiction_code(value: str) -> str | None:
    normalized = _slug(value)
    if not normalized:
        return None
    if normalized in CONTRADICTION_CODE_VALUES:
        return normalized
    if "market" in normalized and "regime" in normalized:
        return InvestorSignalContradictionCode.MARKET_REGIME_SIGNAL_MISMATCH.value
    if "capital" in normalized and "flow" in normalized:
        return InvestorSignalContradictionCode.CAPITAL_FLOW_SIGNAL_MISMATCH.value
    if "theme" in normalized or "rotation" in normalized:
        return InvestorSignalContradictionCode.THEME_FLOW_STATE_SIGNAL_MISMATCH.value
    if any(marker in normalized for marker in ("mixed", "contradict", "conflict")):
        return InvestorSignalContradictionCode.MIXED_SIGNAL_INPUTS.value
    return None


def _source_is_ambiguous(value: Any) -> bool:
    normalized = _text(value).lower()
    if not normalized:
        return False
    if normalized in _AMBIGUOUS_SOURCE_VALUES:
        return True
    return any(separator in normalized for separator in (",", "|", "/"))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    for item in value:
        text = _text(item)
        if text:
            result.append(text)
    return result


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: Any) -> str:
    text = _text(value).lower()
    if not text:
        return ""
    return text.replace("-", "_").replace(" ", "_")
