# -*- coding: utf-8 -*-
"""Additive read-only diagnostics for portfolio/risk evidence quality."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping

from src.services.ai_evidence_packet import (
    AI_EVIDENCE_PACKET_VERSION,
    AiEvidenceConfidenceCap,
    AiEvidenceCriticality,
    AiEvidenceDecisionStatus,
    AiEvidenceEngine,
    AiEvidenceEntity,
    AiEvidenceFreshnessClass,
    AiEvidenceItem,
    AiEvidencePacket,
    AiEvidenceSourceClass,
    AiEvidenceSourceRef,
    AiEvidenceStatus,
)


LABEL_HOLDINGS_REVIEW = "持仓来源待核验"
LABEL_CASH_INCOMPLETE = "现金流水不完整"
LABEL_FX_STALE = "FX 汇率已过期"
LABEL_FX_MISSING = "FX 汇率缺失"
LABEL_COST_REVIEW = "成本口径需复核"
LABEL_BENCHMARK_MISSING = "基准映射暂缺"
LABEL_FACTOR_MISSING = "因子映射暂缺"
LABEL_AUTHORITY_REVIEW = "依据需复核"
LABEL_OBSERVATION_ONLY = "仅供风险观察"
LABEL_FORBIDDEN = "数据不足，禁止判断"
CONFIDENCE_POLICY_VERSION = "portfolio_risk_confidence_cap_v1"


def _normalize_currency(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text or "UNKNOWN"


def _stringify_date(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    text = str(value).strip()
    return text or None


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _append_unique(target: list[str], value: str | None) -> None:
    text = str(value or "").strip()
    if text and text not in target:
        target.append(text)


def _coverage_state(*, covered: int, total: int) -> str:
    if total <= 0:
        return "missing"
    if covered <= 0:
        return "missing"
    if covered >= total:
        return "complete"
    return "partial"


def _diagnostic_status_from_state(state: str) -> AiEvidenceStatus:
    normalized = str(state or "").strip().lower()
    if normalized in {"fresh", "complete", "manual", "broker", "import", "available"}:
        return AiEvidenceStatus.AVAILABLE
    if normalized in {"stale"}:
        return AiEvidenceStatus.STALE
    if normalized in {"partial", "mixed"}:
        return AiEvidenceStatus.PARTIAL
    return AiEvidenceStatus.MISSING


def _freshness_class_for_fx(state: str, *, has_pairs: bool, severe_stale: bool, unavailable: bool) -> AiEvidenceFreshnessClass:
    if unavailable:
        return AiEvidenceFreshnessClass.FALLBACK
    if state == "stale":
        return AiEvidenceFreshnessClass.STALE if not severe_stale else AiEvidenceFreshnessClass.STALE
    if not has_pairs:
        return AiEvidenceFreshnessClass.UNKNOWN
    return AiEvidenceFreshnessClass.FRESH


def _source_class_for_authority(state: str) -> AiEvidenceSourceClass:
    normalized = str(state or "").strip().lower()
    if normalized == "broker":
        return AiEvidenceSourceClass.DELAYED
    if normalized == "import":
        return AiEvidenceSourceClass.LOCAL_HISTORICAL
    if normalized == "manual":
        return AiEvidenceSourceClass.LOCAL
    if normalized == "mixed":
        return AiEvidenceSourceClass.FALLBACK
    return AiEvidenceSourceClass.INFERRED


@dataclass(slots=True)
class PortfolioRiskDiagnosticIssue:
    code: str
    label: str
    detail: str | None = None
    account_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "detail": self.detail,
            "account_ids": list(self.account_ids),
        }


@dataclass(slots=True)
class PortfolioRiskEvidenceSection:
    state: str
    summary: str
    issues: list[PortfolioRiskDiagnosticIssue] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "summary": self.summary,
            "issues": [item.to_dict() for item in self.issues],
            "details": dict(self.details),
        }


@dataclass(slots=True)
class PortfolioRiskConfidenceCap:
    value: int
    decision_status: str
    reason_codes: list[str] = field(default_factory=list)
    limitation_labels: list[str] = field(default_factory=list)
    disabled_claims: list[str] = field(default_factory=list)
    policy_version: str = CONFIDENCE_POLICY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": max(0, min(100, int(self.value))),
            "decision_status": self.decision_status,
            "reason_codes": list(self.reason_codes),
            "limitation_labels": list(self.limitation_labels),
            "disabled_claims": list(self.disabled_claims),
            "policy_version": self.policy_version,
        }


@dataclass(slots=True)
class PortfolioRiskDiagnostics:
    holdings_lineage: PortfolioRiskEvidenceSection
    cash_ledger_completeness: PortfolioRiskEvidenceSection
    transaction_lineage: PortfolioRiskEvidenceSection
    fx_freshness: PortfolioRiskEvidenceSection
    cost_basis_coverage: PortfolioRiskEvidenceSection
    source_authority: PortfolioRiskEvidenceSection
    benchmark_factor_mapping: PortfolioRiskEvidenceSection
    confidence_cap: PortfolioRiskConfidenceCap
    evidence_packet: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "holdingsLineage": self.holdings_lineage.to_dict(),
            "cashLedgerCompleteness": self.cash_ledger_completeness.to_dict(),
            "transactionLineage": self.transaction_lineage.to_dict(),
            "fxFreshness": self.fx_freshness.to_dict(),
            "costBasisCoverage": self.cost_basis_coverage.to_dict(),
            "sourceAuthority": self.source_authority.to_dict(),
            "benchmarkFactorMapping": self.benchmark_factor_mapping.to_dict(),
            "confidenceCap": self.confidence_cap.to_dict(),
            "evidencePacket": dict(self.evidence_packet),
        }


def _classify_account_source(
    *,
    account_snapshot: Mapping[str, Any],
    as_of: date,
    sync_state: Mapping[str, Any] | None,
    trades: Iterable[Any],
    connections: Iterable[Mapping[str, Any]],
    cash_entries: Iterable[Any],
    corporate_actions: Iterable[Any],
) -> str:
    sync_status = str((sync_state or {}).get("sync_status") or "").strip().lower()
    snapshot_date = str((sync_state or {}).get("snapshot_date") or "").strip()
    if sync_status == "success" and snapshot_date == as_of.isoformat():
        return "broker sync overlay"

    active_trades = [row for row in trades if bool(getattr(row, "is_active", True))]
    positions = list(account_snapshot.get("positions") or [])
    imported = any(str(item.get("last_imported_at") or "").strip() for item in connections if isinstance(item, Mapping))
    if positions and not active_trades and imported:
        return "import seed"
    if active_trades or cash_entries or corporate_actions:
        return "manual replay"
    if imported:
        return "import seed"
    return "unknown"


def _authority_bucket(source_classes: set[str]) -> str:
    normalized = {item.strip().lower() for item in source_classes if item}
    if not normalized:
        return "unknown"
    if normalized == {"manual replay"}:
        return "manual"
    if normalized == {"broker sync overlay"}:
        return "broker"
    if normalized == {"import seed"}:
        return "import"
    if normalized == {"unknown"}:
        return "unknown"
    return "mixed"


def _build_evidence_packet(
    *,
    account_id: int | None,
    snapshot: Mapping[str, Any],
    as_of: date,
    holdings_state: str,
    cash_state: str,
    transaction_state: str,
    fx_state: str,
    fx_has_pairs: bool,
    fx_severe_stale: bool,
    fx_unavailable: bool,
    authority_state: str,
    sync_state: str,
    confidence_cap: PortfolioRiskConfidenceCap,
    issues: list[str],
) -> dict[str, Any]:
    source_refs = [
        AiEvidenceSourceRef(
            source_ref_id="portfolio_snapshot",
            provider="portfolio_snapshot",
            category="portfolio",
            source_class=_source_class_for_authority(authority_state),
            raw_payload_stored=False,
            sanitized_reason_code="snapshot_summary_only",
        ),
        AiEvidenceSourceRef(
            source_ref_id="fx_snapshot",
            provider="fx_cache",
            category="portfolio",
            source_class=AiEvidenceSourceClass.FALLBACK if fx_unavailable else AiEvidenceSourceClass.LOCAL,
            raw_payload_stored=False,
            sanitized_reason_code="fx_summary_only",
        ),
    ]
    required_evidence = [
        AiEvidenceItem(
            key="holdings.lineage",
            criticality=AiEvidenceCriticality.REQUIRED,
            status=_diagnostic_status_from_state(holdings_state),
            value_class="metadata",
            source_ref_ids=["portfolio_snapshot"],
            as_of=as_of.isoformat(),
            freshness_class=AiEvidenceFreshnessClass.FRESH if holdings_state != "missing" else AiEvidenceFreshnessClass.MISSING,
            reason_codes=["holdings_lineage_" + holdings_state],
        ),
        AiEvidenceItem(
            key="cash.ledger",
            criticality=AiEvidenceCriticality.REQUIRED,
            status=_diagnostic_status_from_state(cash_state),
            value_class="metadata",
            source_ref_ids=["portfolio_snapshot"],
            as_of=as_of.isoformat(),
            freshness_class=AiEvidenceFreshnessClass.FRESH if cash_state == "complete" else AiEvidenceFreshnessClass.UNKNOWN,
            reason_codes=["cash_ledger_" + cash_state],
        ),
        AiEvidenceItem(
            key="transactions.lineage",
            criticality=AiEvidenceCriticality.REQUIRED,
            status=_diagnostic_status_from_state(transaction_state),
            value_class="metadata",
            source_ref_ids=["portfolio_snapshot"],
            as_of=as_of.isoformat(),
            freshness_class=AiEvidenceFreshnessClass.FRESH if transaction_state != "missing" else AiEvidenceFreshnessClass.MISSING,
            reason_codes=["transaction_lineage_" + transaction_state],
        ),
        AiEvidenceItem(
            key="fx.freshness",
            criticality=AiEvidenceCriticality.REQUIRED,
            status=_diagnostic_status_from_state(fx_state),
            value_class="metadata",
            source_ref_ids=["fx_snapshot"],
            as_of=as_of.isoformat() if fx_has_pairs else None,
            freshness_class=_freshness_class_for_fx(
                fx_state,
                has_pairs=fx_has_pairs,
                severe_stale=fx_severe_stale,
                unavailable=fx_unavailable,
            ),
            reason_codes=["fx_freshness_" + fx_state],
        ),
        AiEvidenceItem(
            key="cost_basis.method",
            criticality=AiEvidenceCriticality.REQUIRED,
            status=AiEvidenceStatus.AVAILABLE,
            value_class="categorical",
            source_ref_ids=["portfolio_snapshot"],
            as_of=as_of.isoformat(),
            freshness_class=AiEvidenceFreshnessClass.FRESH,
            reason_codes=["cost_method_" + str(snapshot.get("cost_method") or "unknown").strip().lower()],
        ),
        AiEvidenceItem(
            key="source.authority",
            criticality=AiEvidenceCriticality.REQUIRED,
            status=_diagnostic_status_from_state(authority_state),
            value_class="categorical",
            source_ref_ids=["portfolio_snapshot"],
            as_of=as_of.isoformat(),
            freshness_class=AiEvidenceFreshnessClass.FRESH if authority_state in {"manual", "broker", "import"} else AiEvidenceFreshnessClass.UNKNOWN,
            reason_codes=["source_authority_" + authority_state],
        ),
        AiEvidenceItem(
            key="sync_import.status",
            criticality=AiEvidenceCriticality.REQUIRED,
            status=_diagnostic_status_from_state(sync_state),
            value_class="metadata",
            source_ref_ids=["portfolio_snapshot"],
            as_of=as_of.isoformat(),
            freshness_class=AiEvidenceFreshnessClass.FRESH if sync_state != "missing" else AiEvidenceFreshnessClass.UNKNOWN,
            reason_codes=["sync_import_" + sync_state],
        ),
    ]
    packet = AiEvidencePacket(
        engine=AiEvidenceEngine.PORTFOLIO_RISK,
        entity=AiEvidenceEntity(
            type="account" if account_id is not None else "portfolio",
            id=str(account_id) if account_id is not None else "portfolio_all",
            market="GLOBAL",
            display_name="Portfolio Risk Diagnostics",
        ),
        run_id=f"portfolio-risk:{account_id if account_id is not None else 'all'}:{as_of.isoformat()}:{snapshot.get('cost_method')}",
        evidence_version=AI_EVIDENCE_PACKET_VERSION,
        required_evidence=required_evidence,
        optional_evidence=[],
        freshness={"as_of": as_of.isoformat()},
        quality_flags=list(issues),
        decision_status=AiEvidenceDecisionStatus.FORBIDDEN
        if confidence_cap.decision_status == AiEvidenceDecisionStatus.FORBIDDEN.value
        else AiEvidenceDecisionStatus.CAUTION
        if confidence_cap.decision_status == AiEvidenceDecisionStatus.CAUTION.value
        else AiEvidenceDecisionStatus.ALLOWED,
        confidence_cap=AiEvidenceConfidenceCap(
            value=confidence_cap.value,
            policy_version=confidence_cap.policy_version,
            reason_codes=confidence_cap.reason_codes,
        ),
        source_refs=source_refs,
        explainable_facts=[],
        admin_diagnostics={
            "raw_payload_stored": False,
            "sanitized_only": True,
            "disabled_claims": list(confidence_cap.disabled_claims),
        },
    )
    return packet.to_dict()


def build_portfolio_risk_diagnostics(
    *,
    portfolio_service: Any,
    snapshot: Mapping[str, Any],
    account_id: int | None,
    as_of: date,
    cost_method: str,
) -> dict[str, Any]:
    accounts = list(snapshot.get("accounts") or [])
    issue_codes: list[str] = []
    limitation_labels: list[str] = [LABEL_OBSERVATION_ONLY]
    reason_codes: list[str] = []
    disabled_claims: list[str] = []
    max_confidence = 100
    decision_status = AiEvidenceDecisionStatus.ALLOWED.value

    holdings_covered_accounts = 0
    holdings_missing_count = 0
    holdings_symbol_count = 0
    holdings_source_classes: set[str] = set()
    holdings_missing_accounts: list[int] = []
    cash_present_accounts = 0
    cash_currencies: set[str] = set()
    cash_missing_accounts: list[int] = []
    trade_total = 0
    trade_uid_count = 0
    trade_dedup_count = 0
    trade_voided_count = 0
    cash_entry_total = 0
    action_total = 0
    sync_status_rows: list[dict[str, Any]] = []

    for account_snapshot in accounts:
        current_account_id = int(account_snapshot.get("account_id") or 0)
        positions = list(account_snapshot.get("positions") or [])
        holdings_symbol_count += len(positions)
        sync_state = portfolio_service.get_latest_broker_sync_state(portfolio_account_id=current_account_id)
        connections = list(portfolio_service.list_broker_connections(portfolio_account_id=current_account_id))
        trades = list(portfolio_service.repo.list_trades(current_account_id, as_of, include_voided=True))
        cash_entries = list(portfolio_service.repo.list_cash_ledger(current_account_id, as_of))
        corporate_actions = list(portfolio_service.repo.list_corporate_actions(current_account_id, as_of))

        source_class = _classify_account_source(
            account_snapshot=account_snapshot,
            as_of=as_of,
            sync_state=sync_state,
            trades=trades,
            connections=connections,
            cash_entries=cash_entries,
            corporate_actions=corporate_actions,
        )
        holdings_source_classes.add(source_class)
        if source_class != "unknown":
            holdings_covered_accounts += 1
        if positions and source_class == "unknown":
            holdings_missing_count += len(positions)
            holdings_missing_accounts.append(current_account_id)

        trade_total += len([row for row in trades if bool(getattr(row, "is_active", True))])
        trade_uid_count += len([row for row in trades if str(getattr(row, "trade_uid", "") or "").strip()])
        trade_dedup_count += len([row for row in trades if str(getattr(row, "dedup_hash", "") or "").strip()])
        trade_voided_count += len([row for row in trades if not bool(getattr(row, "is_active", True))])

        cash_entry_total += len(cash_entries)
        cash_currencies.update({_normalize_currency(getattr(row, "currency", None)) for row in cash_entries})
        action_total += len(corporate_actions)

        sync_cash_balances = list((sync_state or {}).get("cash_balances") or [])
        cash_present = bool(cash_entries) or bool(sync_cash_balances) or str(source_class) == "broker sync overlay"
        if cash_present:
            cash_present_accounts += 1
        else:
            cash_missing_accounts.append(current_account_id)
        for item in sync_cash_balances:
            cash_currencies.add(_normalize_currency(item.get("currency")))

        for connection in connections:
            sync_status_rows.append(
                {
                    "account_id": current_account_id,
                    "connection_id": int(connection.get("id") or 0),
                    "broker_type": str(connection.get("broker_type") or "").strip(),
                    "import_mode": str(connection.get("import_mode") or "").strip(),
                    "status": str(connection.get("status") or "").strip(),
                    "last_imported_at": _stringify_date(connection.get("last_imported_at")),
                    "last_import_source": str(connection.get("last_import_source") or "").strip() or None,
                }
            )
        if sync_state:
            sync_status_rows.append(
                {
                    "account_id": current_account_id,
                    "sync_status": str(sync_state.get("sync_status") or "").strip() or None,
                    "snapshot_date": _stringify_date(sync_state.get("snapshot_date")),
                    "synced_at": _stringify_date(sync_state.get("synced_at")),
                }
            )

    authority_state = _authority_bucket(holdings_source_classes)
    holdings_state = "missing" if holdings_missing_count > 0 else _coverage_state(covered=holdings_covered_accounts, total=len(accounts))
    cash_state = _coverage_state(covered=cash_present_accounts, total=len(accounts))
    transaction_state = "complete" if trade_total or cash_entry_total or action_total else "missing"

    fx_rates = list(snapshot.get("fx_rates") or [])
    fx_pairs = [f"{item.get('from_currency')}/{item.get('to_currency')}" for item in fx_rates]
    fx_sources = sorted({str(item.get("source") or "missing").strip() or "missing" for item in fx_rates})
    fx_missing_pairs = [pair for pair, item in zip(fx_pairs, fx_rates) if item.get("rate") in (None, "")]
    fx_stale_pairs = [pair for pair, item in zip(fx_pairs, fx_rates) if bool(item.get("is_stale"))]
    fx_no_usable_as_of = any(not str(item.get("rate_date") or "").strip() for item in fx_rates if bool(item.get("is_stale")))
    fx_unavailable = bool(
        ((snapshot.get("analytics") or {}).get("risk") or {}).get("fx_unavailable")
        or any(str(item.get("display_fx_status") or "").strip().lower() == "unavailable" for account in accounts for item in list(account.get("positions") or []))
    )
    if fx_unavailable or fx_missing_pairs:
        fx_state = "unavailable"
    elif fx_stale_pairs or bool(snapshot.get("fx_stale")):
        fx_state = "stale"
    else:
        fx_state = "fresh"

    if holdings_state == "missing":
        max_confidence = min(max_confidence, 40)
        decision_status = AiEvidenceDecisionStatus.FORBIDDEN.value
        _append_unique(reason_codes, "holdings_lineage_missing")
        _append_unique(limitation_labels, LABEL_HOLDINGS_REVIEW)
        _append_unique(issue_codes, "required_data_missing")

    if cash_state == "missing":
        max_confidence = min(max_confidence, 40)
        decision_status = AiEvidenceDecisionStatus.FORBIDDEN.value
        _append_unique(reason_codes, "cash_ledger_missing")
        _append_unique(limitation_labels, LABEL_CASH_INCOMPLETE)
        _append_unique(issue_codes, "required_data_missing")
    elif cash_state == "partial":
        max_confidence = min(max_confidence, 60)
        if decision_status != AiEvidenceDecisionStatus.FORBIDDEN.value:
            decision_status = AiEvidenceDecisionStatus.CAUTION.value
        _append_unique(reason_codes, "cash_ledger_partial")
        _append_unique(limitation_labels, LABEL_CASH_INCOMPLETE)

    if authority_state in {"mixed", "unknown"}:
        max_confidence = min(max_confidence, 60)
        if decision_status != AiEvidenceDecisionStatus.FORBIDDEN.value:
            decision_status = AiEvidenceDecisionStatus.CAUTION.value
        _append_unique(reason_codes, f"source_authority_{authority_state}")
        _append_unique(limitation_labels, LABEL_AUTHORITY_REVIEW)

    if fx_unavailable:
        max_confidence = min(max_confidence, 40)
        if decision_status != AiEvidenceDecisionStatus.FORBIDDEN.value:
            decision_status = AiEvidenceDecisionStatus.CAUTION.value
        _append_unique(reason_codes, "fx_unavailable_fallback_1_to_1")
        _append_unique(limitation_labels, LABEL_FX_MISSING)
        _append_unique(disabled_claims, "aggregate_currency_claims_disabled")
        _append_unique(disabled_claims, "aggregate_pnl_claims_disabled")
        _append_unique(issue_codes, "required_data_missing")
    elif fx_state == "stale":
        max_confidence = min(max_confidence, 60 if fx_no_usable_as_of else 75)
        if decision_status != AiEvidenceDecisionStatus.FORBIDDEN.value:
            decision_status = AiEvidenceDecisionStatus.CAUTION.value
        _append_unique(reason_codes, "fx_stale")
        _append_unique(limitation_labels, LABEL_FX_STALE)
        _append_unique(issue_codes, "stale_required_data")

    benchmark_mapping_state = "unmapped"
    factor_mapping_state = "unmapped"
    _append_unique(disabled_claims, "benchmark_relative_claims_disabled")
    _append_unique(disabled_claims, "factor_risk_claims_disabled")
    _append_unique(limitation_labels, LABEL_BENCHMARK_MISSING)
    _append_unique(limitation_labels, LABEL_FACTOR_MISSING)

    if action_total == 0:
        _append_unique(disabled_claims, "professional_corporate_action_claims_disabled")
        _append_unique(reason_codes, "corporate_action_coverage_unverified")
        _append_unique(limitation_labels, LABEL_COST_REVIEW)

    if decision_status == AiEvidenceDecisionStatus.FORBIDDEN.value:
        _append_unique(limitation_labels, LABEL_FORBIDDEN)

    holdings_section = PortfolioRiskEvidenceSection(
        state=holdings_state,
        summary="Holdings lineage coverage derived from existing snapshot positions and source authority.",
        issues=[
            PortfolioRiskDiagnosticIssue(
                code="holdings_lineage_missing",
                label=LABEL_HOLDINGS_REVIEW,
                detail="One or more displayed holdings could not be tied to replay/import/sync source classes.",
                account_ids=sorted(set(holdings_missing_accounts)),
            )
        ]
        if holdings_missing_accounts
        else [],
        details={
            "source_classes": sorted(holdings_source_classes),
            "account_coverage": {"covered": holdings_covered_accounts, "total": len(accounts)},
            "symbol_coverage": {"positions": holdings_symbol_count},
            "missing_lineage_count": holdings_missing_count,
            "authority_state": authority_state,
        },
    )
    cash_section = PortfolioRiskEvidenceSection(
        state=cash_state,
        summary="Cash completeness derived from existing cash-ledger rows and broker-sync cash balances only.",
        issues=[
            PortfolioRiskDiagnosticIssue(
                code="cash_ledger_missing",
                label=LABEL_CASH_INCOMPLETE,
                detail="At least one account has no explicit cash-ledger or sync cash evidence.",
                account_ids=sorted(set(cash_missing_accounts)),
            )
        ]
        if cash_missing_accounts
        else [],
        details={
            "cash_entries_present": cash_entry_total,
            "currency_coverage": sorted(cash_currencies),
            "account_coverage": {"covered": cash_present_accounts, "total": len(accounts)},
        },
    )
    transaction_section = PortfolioRiskEvidenceSection(
        state=transaction_state,
        summary="Transaction lineage coverage summarizes trades, cash ledger, and corporate actions without exposing raw rows.",
        issues=[],
        details={
            "trade_count": trade_total,
            "cash_entry_count": cash_entry_total,
            "corporate_action_count": action_total,
            "voided_trade_count": trade_voided_count,
            "trade_uid_coverage": {"present": trade_uid_count, "missing": max(0, trade_total - trade_uid_count)},
            "dedup_coverage": {"present": trade_dedup_count, "missing": max(0, trade_total - trade_dedup_count)},
        },
    )
    fx_section = PortfolioRiskEvidenceSection(
        state=fx_state,
        summary="FX freshness uses existing snapshot FX rows and display fallback states only.",
        issues=[
            PortfolioRiskDiagnosticIssue(
                code="fx_unavailable_fallback_1_to_1" if fx_unavailable else "fx_stale",
                label=LABEL_FX_MISSING if fx_unavailable else LABEL_FX_STALE,
                detail="Aggregate currency exposure and P&L claims are capped when FX evidence is stale or unavailable.",
                account_ids=[],
            )
        ]
        if fx_state in {"stale", "unavailable"}
        else [],
        details={
            "pairs_used": fx_pairs,
            "rate_source_classes": fx_sources,
            "stale_pairs": fx_stale_pairs,
            "missing_pairs": fx_missing_pairs,
            "fallback_1_to_1_active": fx_unavailable,
            "no_usable_as_of": fx_no_usable_as_of,
        },
    )
    cost_section = PortfolioRiskEvidenceSection(
        state="complete",
        summary="Cost-basis coverage reports the active accounting method without changing lot or P&L semantics.",
        issues=[
            PortfolioRiskDiagnosticIssue(
                code="corporate_action_coverage_unverified",
                label=LABEL_COST_REVIEW,
                detail="Professional corporate-action-adjusted return claims stay disabled until coverage is explicitly mapped.",
                account_ids=[],
            )
        ],
        details={
            "cost_method": str(cost_method or snapshot.get("cost_method") or "").strip() or "unknown",
            "lot_availability": "expected_for_fifo" if str(cost_method).strip().lower() == "fifo" else "method_managed",
            "corporate_action_coverage": "observed" if action_total > 0 else "unverified",
        },
    )
    source_section = PortfolioRiskEvidenceSection(
        state=authority_state,
        summary="Source authority distinguishes manual replay, broker overlay, import seed, mixed, or unknown evidence posture.",
        issues=[
            PortfolioRiskDiagnosticIssue(
                code=f"source_authority_{authority_state}",
                label=LABEL_AUTHORITY_REVIEW,
                detail="Mixed or unknown source authority caps diagnostic confidence.",
                account_ids=[],
            )
        ]
        if authority_state in {"mixed", "unknown"}
        else [],
        details={
            "source_authority": authority_state,
            "sync_import_status": sync_status_rows,
            "authority_limitation_labels": [LABEL_AUTHORITY_REVIEW] if authority_state in {"mixed", "unknown"} else [],
        },
    )
    mapping_section = PortfolioRiskEvidenceSection(
        state="unmapped",
        summary="Benchmark and factor coverage placeholders are additive only; related claims remain disabled until mappings exist.",
        issues=[
            PortfolioRiskDiagnosticIssue(
                code="benchmark_mapping_missing",
                label=LABEL_BENCHMARK_MISSING,
                detail="Benchmark-relative claims are disabled.",
            ),
            PortfolioRiskDiagnosticIssue(
                code="factor_mapping_missing",
                label=LABEL_FACTOR_MISSING,
                detail="Factor-risk claims are disabled.",
            ),
        ],
        details={
            "benchmark_mapping_state": benchmark_mapping_state,
            "factor_mapping_state": factor_mapping_state,
            "disabled_claims": [
                "benchmark_relative_claims_disabled",
                "factor_risk_claims_disabled",
            ],
        },
    )

    confidence_cap = PortfolioRiskConfidenceCap(
        value=max_confidence,
        decision_status=decision_status,
        reason_codes=reason_codes,
        limitation_labels=limitation_labels,
        disabled_claims=disabled_claims,
    )
    evidence_packet = _build_evidence_packet(
        account_id=account_id,
        snapshot=snapshot,
        as_of=as_of,
        holdings_state=holdings_state,
        cash_state=cash_state,
        transaction_state=transaction_state,
        fx_state=fx_state,
        fx_has_pairs=bool(fx_pairs),
        fx_severe_stale=fx_no_usable_as_of,
        fx_unavailable=fx_unavailable,
        authority_state=authority_state,
        sync_state="complete" if sync_status_rows else "missing",
        confidence_cap=confidence_cap,
        issues=issue_codes,
    )
    diagnostics = PortfolioRiskDiagnostics(
        holdings_lineage=holdings_section,
        cash_ledger_completeness=cash_section,
        transaction_lineage=transaction_section,
        fx_freshness=fx_section,
        cost_basis_coverage=cost_section,
        source_authority=source_section,
        benchmark_factor_mapping=mapping_section,
        confidence_cap=confidence_cap,
        evidence_packet=evidence_packet,
    ).to_dict()
    return {
        "riskDiagnostics": diagnostics,
        "portfolioRiskEvidence": evidence_packet,
        "sourceAuthorityState": authority_state,
        "fxFreshnessState": fx_state,
        "holdingsLineageState": holdings_state,
        "cashLedgerCompletenessState": cash_state,
        "benchmarkMappingState": benchmark_mapping_state,
        "factorMappingState": factor_mapping_state,
        "confidenceCap": confidence_cap.to_dict(),
    }
