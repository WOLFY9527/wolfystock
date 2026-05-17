# -*- coding: utf-8 -*-
"""Pure portfolio construction advisory projection helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from src.schemas.portfolio_construction import (
    PortfolioConstructionConstraintViolation,
    PortfolioConstructionEvidenceMetadata,
    PortfolioConstructionMetadata,
    PortfolioConstructionPositionEvidence,
    PortfolioConstructionPositionReadModel,
    PortfolioConstructionReadModel,
)


class PortfolioConstructionReadModelService:
    """Build an advisory construction projection from an existing snapshot."""

    def build_read_model(
        self,
        *,
        snapshot: Mapping[str, Any],
        target_weights: Mapping[str, float],
        drift_threshold: float = 1.0,
        max_position_weight: Optional[float] = None,
        risk_budget_notes: Optional[Mapping[str, Any]] = None,
        confidence: Optional[float] = None,
        confidence_reasons: Optional[List[str]] = None,
        target_source: str = "caller_supplied_fixture",
    ) -> PortfolioConstructionReadModel:
        total_market_value = self._float(snapshot.get("total_market_value"))
        positions = self._collect_positions(snapshot=snapshot)
        normalized_targets = {
            self._normalize_symbol(symbol): self._round_pct(weight)
            for symbol, weight in target_weights.items()
            if self._normalize_symbol(symbol)
        }
        notes = risk_budget_notes or {}

        all_symbols = sorted(
            set(positions) | set(normalized_targets),
            key=lambda symbol: (-positions.get(symbol, {}).get("market_value", 0.0), symbol),
        )
        rows = [
            self._build_position_row(
                symbol=symbol,
                position=positions.get(symbol, {}),
                target_weight=normalized_targets.get(symbol, 0.0),
                total_market_value=total_market_value,
                drift_threshold=drift_threshold,
                max_position_weight=max_position_weight,
                risk_budget_notes=self._note_list(notes.get(symbol)),
            )
            for symbol in all_symbols
        ]

        snapshot_evidence = snapshot.get("portfolioRiskEvidence") or {}
        confidence_cap = snapshot.get("confidenceCap") or {}
        resolved_confidence = (
            float(confidence)
            if confidence is not None
            else float(confidence_cap.get("max_confidence") or 0.5)
        )
        resolved_confidence_reasons = (
            list(confidence_reasons)
            if confidence_reasons is not None
            else self._note_list(confidence_cap.get("reasons"))
        )

        return PortfolioConstructionReadModel(
            asOf=self._optional_str(snapshot.get("as_of")),
            currency=str(snapshot.get("currency") or "CNY"),
            totalMarketValue=self._round_money(total_market_value),
            targetSource=target_source,
            driftThreshold=self._round_pct(drift_threshold),
            riskBudgetNotes=self._note_list(notes.get("portfolio")),
            noTradeReasons=[
                "advisory_read_model_only",
                "no_order_execution",
                "no_broker_integration",
                "no_accounting_mutation",
            ],
            positions=rows,
            metadata=PortfolioConstructionMetadata(
                confidence=resolved_confidence,
                confidenceReasons=resolved_confidence_reasons,
                evidence=PortfolioConstructionEvidenceMetadata(
                    snapshotSource=str(snapshot_evidence.get("source") or "read_only_snapshot"),
                    targetSource=target_source,
                    asOf=self._optional_str(snapshot.get("as_of")),
                ),
            ),
        )

    def _collect_positions(self, *, snapshot: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
        positions: Dict[str, Dict[str, Any]] = {}
        for account in snapshot.get("accounts") or []:
            account_id = self._optional_int(account.get("account_id"))
            for item in account.get("positions") or []:
                symbol = self._normalize_symbol(item.get("symbol"))
                if not symbol:
                    continue
                row = positions.setdefault(
                    symbol,
                    {
                        "market": item.get("market"),
                        "currency": item.get("currency"),
                        "market_value": 0.0,
                        "account_ids": [],
                    },
                )
                row["market_value"] = self._round_money(
                    row["market_value"] + self._float(item.get("market_value_base"))
                )
                if account_id is not None and account_id not in row["account_ids"]:
                    row["account_ids"].append(account_id)
        for row in positions.values():
            row["account_ids"] = sorted(row["account_ids"])
        return positions

    def _build_position_row(
        self,
        *,
        symbol: str,
        position: Mapping[str, Any],
        target_weight: float,
        total_market_value: float,
        drift_threshold: float,
        max_position_weight: Optional[float],
        risk_budget_notes: List[str],
    ) -> PortfolioConstructionPositionReadModel:
        market_value = self._float(position.get("market_value"))
        current_weight = self._round_pct((market_value / total_market_value * 100.0) if total_market_value > 0 else 0.0)
        target_weight = self._round_pct(target_weight)
        drift = self._round_pct(current_weight - target_weight)
        no_action_reasons: List[str] = []
        suggested_action = "no_action"
        if total_market_value <= 0:
            no_action_reasons.append("no_market_value")
        elif abs(drift) <= float(drift_threshold):
            no_action_reasons.append("within_drift_threshold")
        elif drift > 0:
            suggested_action = "reduce_exposure"
        else:
            suggested_action = "increase_exposure"

        if market_value <= 0 and target_weight > 0:
            evidence_source = "target_only_no_current_holding"
        elif target_weight == 0 and market_value > 0:
            evidence_source = "snapshot_holding_without_target"
        else:
            evidence_source = "snapshot_holding"

        return PortfolioConstructionPositionReadModel(
            symbol=symbol,
            market=self._optional_str(position.get("market")),
            currency=self._optional_str(position.get("currency")),
            currentWeight=current_weight,
            targetWeight=target_weight,
            drift=drift,
            suggestedAction=suggested_action,
            currentMarketValue=self._round_money(market_value),
            constraintViolations=self._constraint_violations(
                current_weight=current_weight,
                max_position_weight=max_position_weight,
            ),
            riskBudgetNotes=risk_budget_notes,
            noTradeReasons=[
                "advisory_read_model_only",
                "no_order_execution",
                "no_broker_integration",
                "no_accounting_mutation",
            ],
            noActionReasons=no_action_reasons,
            evidence=PortfolioConstructionPositionEvidence(
                source=evidence_source,
                accountIds=list(position.get("account_ids") or []),
                marketValue=self._round_money(market_value),
            ),
        )

    def _constraint_violations(
        self,
        *,
        current_weight: float,
        max_position_weight: Optional[float],
    ) -> List[PortfolioConstructionConstraintViolation]:
        if max_position_weight is None:
            return []
        cap = self._round_pct(max_position_weight)
        if current_weight <= cap:
            return []
        return [
            PortfolioConstructionConstraintViolation(
                code="max_position_weight_exceeded",
                severity="warning",
                message=f"Current weight {current_weight}% is above the {cap}% advisory cap.",
            )
        ]

    @staticmethod
    def _normalize_symbol(value: Any) -> str:
        return str(value or "").strip().upper()

    @staticmethod
    def _optional_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _optional_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _round_pct(value: Any) -> float:
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _round_money(value: Any) -> float:
        try:
            return round(float(value), 6)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _note_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [str(item) for item in value if str(item)]
        if isinstance(value, tuple):
            return [str(item) for item in value if str(item)]
        return [str(value)]
