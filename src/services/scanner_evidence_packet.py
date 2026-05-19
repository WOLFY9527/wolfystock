# -*- coding: utf-8 -*-
"""Additive evidence packet helpers for scanner shortlist candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence


SCANNER_EVIDENCE_VERSION = "scanner_evidence_v1"

_FALLBACK_SOURCES = {"fallback", "history_only_us_scan", "history_only_hk_scan", "mock", "synthetic"}
_SANITIZED_REASON_CODES = {
    "not_enough_history": "history_insufficient",
    "optional_news_timeout": "external_optional_unavailable",
    "fundamentals_unavailable": "fundamental_context_unavailable",
    "provider_timeout": "provider_unavailable",
    "quote_missing": "quote_context_missing",
}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _append_unique(target: List[str], value: Optional[str]) -> None:
    text = str(value or "").strip()
    if text and text not in target:
        target.append(text)


def _format_percent(value: Any, digits: int = 1) -> Optional[str]:
    number = _safe_float(value)
    if number is None:
        return None
    return f"{number:.{digits}f}%"


def _format_amount(value: Any) -> Optional[str]:
    number = _safe_float(value)
    if number is None:
        return None
    if abs(number) >= 1.0e9:
        return f"{number / 1.0e9:.2f}B"
    if abs(number) >= 1.0e8:
        return f"{number / 1.0e8:.2f}亿"
    if abs(number) >= 1.0e6:
        return f"{number / 1.0e6:.1f}M"
    return f"{number:.0f}"


@dataclass
class ScannerEvidenceIssue:
    code: str
    label: str
    severity: str = "warning"


@dataclass
class ScannerEvidenceBucket:
    state: str
    facts: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "facts": list(self.facts),
            "issues": list(self.issues),
        }


@dataclass
class ScannerEvidencePacket:
    symbol: str
    market: str
    rank: Optional[int]
    score: Optional[float]
    rawScore: Optional[float]
    finalScore: Optional[float]
    scoreConfidence: Optional[float]
    evidenceCoverage: Optional[float]
    capReason: Optional[str]
    degradationReason: Optional[str]
    evidenceVersion: str
    runId: Optional[int]
    trendEvidence: Dict[str, Any]
    momentumEvidence: Dict[str, Any]
    volumeEvidence: Dict[str, Any]
    volatilityRiskEvidence: Dict[str, Any]
    liquidityEvidence: Dict[str, Any]
    relativeStrengthEvidence: Dict[str, Any]
    sectorThemeContext: Dict[str, Any]
    dataQualityState: str
    freshnessState: str
    freshnessDetail: Dict[str, Any]
    providerObservation: Dict[str, Any] | None
    missingEvidence: List[str]
    userFacingLabels: List[str]
    warningFlags: List[str]
    adminReasonCodes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _history_state(history_diag: Dict[str, Any]) -> str:
    source = str(history_diag.get("source") or "").strip().lower()
    if history_diag.get("partial_local_fallback") or source in _FALLBACK_SOURCES:
        return "stale"
    if history_diag.get("stale"):
        return "stale"
    if history_diag.get("latest_trade_date"):
        return "complete"
    return "missing"


def _quote_state(quote_diag: Dict[str, Any]) -> str:
    source = str(quote_diag.get("source") or "").strip().lower()
    if quote_diag.get("available"):
        return "complete"
    if source in _FALLBACK_SOURCES or not source:
        return "fallback"
    return "unavailable"


def _bucket_state(*values: Any) -> str:
    present = [value for value in values if value not in (None, "", [], ())]
    if not present:
        return "missing"
    if all(value not in (None, "", [], ()) for value in values):
        return "complete"
    return "partial"


def _bucket_issue(code: str, label: str) -> Dict[str, Any]:
    return asdict(ScannerEvidenceIssue(code=code, label=label))


def _bucket(state: str, facts: Sequence[Dict[str, Any]], issues: Sequence[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    return ScannerEvidenceBucket(state=state, facts=list(facts), issues=list(issues or [])).to_dict()


def build_scanner_evidence_packet(candidate: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = dict(candidate or {})
    context_payload = dict(context or {})
    diagnostics = dict(payload.get("_diagnostics") or {})
    history_diag = dict(diagnostics.get("history") or {})
    quote_diag = dict(diagnostics.get("quote_context") or {})
    provider_observation = diagnostics.get("cn_provider_observation")
    components = dict(payload.get("_component_scores") or {})
    explainability = dict(context_payload.get("score_explainability") or diagnostics.get("score_explainability") or {})

    history_rows = int(history_diag.get("rows") or 0)
    history_state = _history_state(history_diag)
    quote_state = _quote_state(quote_diag)
    freshness_state = "fallback" if quote_state == "fallback" else "stale" if history_state == "stale" else "complete"

    trend_state = "complete" if _safe_float(components.get("trend")) not in (None, 0.0) else "insufficient"
    momentum_state = _bucket_state(payload.get("ret_5d"), payload.get("ret_20d"))
    volume_state = _bucket_state(payload.get("avg_volume_20"), payload.get("volume_expansion_20"))
    volatility_state = "complete" if _safe_float(payload.get("atr20_pct")) is not None else "insufficient"
    liquidity_state = _bucket_state(payload.get("avg_amount_20"), payload.get("amount"))
    relative_strength_state = "complete" if _safe_float(payload.get("_relative_strength_pct")) is not None else "missing"
    sector_state = "complete" if (payload.get("boards") or payload.get("_matched_sectors")) else "missing"

    missing_evidence: List[str] = []
    for name, state in (
        ("trend", trend_state),
        ("momentum", momentum_state),
        ("volume", volume_state),
        ("risk", volatility_state),
        ("liquidity", liquidity_state),
        ("relative_strength", relative_strength_state),
        ("sector_theme", sector_state),
    ):
        if state != "complete":
            missing_evidence.append(name)

    admin_reason_codes: List[str] = []
    if history_rows and history_rows < 60:
        _append_unique(admin_reason_codes, "history_insufficient")
    if history_state == "stale":
        _append_unique(admin_reason_codes, "history_stale")
    if quote_state != "complete":
        _append_unique(admin_reason_codes, "provider_unavailable")
    for raw_code in context_payload.get("internal_reason_codes") or []:
        _append_unique(admin_reason_codes, _SANITIZED_REASON_CODES.get(str(raw_code).strip(), None))

    user_labels: List[str] = []
    if "history_insufficient" in admin_reason_codes:
        _append_unique(user_labels, "历史数据不足")
    if quote_state != "complete":
        _append_unique(user_labels, "部分外部数据暂不可用")
        _append_unique(user_labels, "仅供观察")
        _append_unique(user_labels, "需人工复核")
    if history_state == "stale" or admin_reason_codes:
        _append_unique(user_labels, "依据需复核")
    if liquidity_state != "complete":
        _append_unique(user_labels, "流动性不足")
    if trend_state != "complete":
        _append_unique(user_labels, "趋势证据不足")
    if volume_state != "complete":
        _append_unique(user_labels, "成交量确认不足")
    if volatility_state != "complete":
        _append_unique(user_labels, "风险证据不足")
    if not user_labels:
        _append_unique(user_labels, "依据完整")

    warning_flags = [label for label in user_labels if label in {"仅供观察", "需人工复核", "依据需复核", "流动性不足", "趋势证据不足", "成交量确认不足", "风险证据不足"}]

    data_quality_state = "complete"
    if history_rows and history_rows < 20:
        data_quality_state = "insufficient"
    elif history_state == "missing":
        data_quality_state = "missing"
    elif history_state == "stale" or quote_state != "complete" or missing_evidence:
        data_quality_state = "partial"

    packet = ScannerEvidencePacket(
        symbol=str(payload.get("symbol") or ""),
        market=str(context_payload.get("market") or payload.get("market") or "").lower(),
        rank=int(payload["rank"]) if payload.get("rank") is not None else None,
        score=round(float(explainability.get("final_score", payload.get("score"))), 1) if explainability.get("final_score", payload.get("score")) is not None else None,
        rawScore=round(float(explainability.get("raw_score", payload.get("raw_score", payload.get("score")))), 1) if explainability.get("raw_score", payload.get("raw_score", payload.get("score"))) is not None else None,
        finalScore=round(float(explainability.get("final_score", payload.get("final_score", payload.get("score")))), 1) if explainability.get("final_score", payload.get("final_score", payload.get("score"))) is not None else None,
        scoreConfidence=_safe_float(explainability.get("score_confidence")),
        evidenceCoverage=_safe_float(explainability.get("evidence_coverage")),
        capReason=str(explainability.get("cap_reason")) if explainability.get("cap_reason") is not None else None,
        degradationReason=str(explainability.get("degradation_reason")) if explainability.get("degradation_reason") is not None else None,
        evidenceVersion=str(context_payload.get("evidence_version") or SCANNER_EVIDENCE_VERSION),
        runId=context_payload.get("run_id"),
        trendEvidence=_bucket(
            trend_state,
            [
                {"label": "趋势分", "value": round(float(components.get("trend") or 0.0), 1)},
                {"label": "理由摘要", "value": (payload.get("reasons") or [""])[0]},
            ],
            [] if trend_state == "complete" else [_bucket_issue("trend_insufficient", "趋势证据不足")],
        ),
        momentumEvidence=_bucket(
            momentum_state,
            [
                {"label": "5日动量", "value": _format_percent(payload.get("ret_5d"))},
                {"label": "20日动量", "value": _format_percent(payload.get("ret_20d"))},
            ],
        ),
        volumeEvidence=_bucket(
            volume_state,
            [
                {"label": "20日均量", "value": _format_amount(payload.get("avg_volume_20"))},
                {"label": "量能扩张", "value": _format_percent((_safe_float(payload.get("volume_expansion_20")) or 0.0) * 100.0)},
            ],
            [] if volume_state == "complete" else [_bucket_issue("volume_insufficient", "成交量确认不足")],
        ),
        volatilityRiskEvidence=_bucket(
            volatility_state,
            [
                {"label": "ATR20%", "value": _format_percent(payload.get("atr20_pct"))},
                {"label": "风险提示", "value": "；".join((payload.get("risk_notes") or [])[:2]) or None},
            ],
            [] if volatility_state == "complete" else [_bucket_issue("risk_insufficient", "风险证据不足")],
        ),
        liquidityEvidence=_bucket(
            liquidity_state,
            [
                {"label": "20日均额", "value": _format_amount(payload.get("avg_amount_20"))},
                {"label": "当日成交额", "value": _format_amount(payload.get("amount"))},
            ],
            [] if liquidity_state == "complete" else [_bucket_issue("liquidity_insufficient", "流动性不足")],
        ),
        relativeStrengthEvidence=_bucket(
            relative_strength_state,
            [
                {"label": "相对强度分位", "value": _format_percent((_safe_float(payload.get("_relative_strength_pct")) or 0.0) * 100.0)},
                {"label": "20日相对表现", "value": _format_percent(payload.get("benchmark_relative_20d"))},
            ],
        ),
        sectorThemeContext=_bucket(
            sector_state,
            [
                {"label": "板块", "value": "、".join((payload.get("boards") or [])[:3]) or None},
                {"label": "主题共振", "value": "、".join((payload.get("_matched_sectors") or [])[:3]) or None},
            ],
        ),
        dataQualityState=data_quality_state,
        freshnessState=freshness_state,
        freshnessDetail={
            "quoteState": quote_state,
            "historyState": history_state,
            "latestTradeDate": history_diag.get("latest_trade_date"),
        },
        providerObservation=provider_observation if isinstance(provider_observation, dict) else None,
        missingEvidence=missing_evidence,
        userFacingLabels=user_labels,
        warningFlags=warning_flags,
        adminReasonCodes=admin_reason_codes,
    )
    return packet.to_dict()
