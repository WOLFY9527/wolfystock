# -*- coding: utf-8 -*-
"""Pure portfolio construction advisory projection helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from src.schemas.portfolio_construction import (
    PortfolioConstructionAdvisoryConstraints,
    PortfolioConstructionConstraintViolation,
    PortfolioConstructionEvidenceMetadata,
    PortfolioConstructionMetadata,
    PortfolioConstructionPositionEvidence,
    PortfolioConstructionPositionReadModel,
    PortfolioConstructionReadModel,
)


class PortfolioConstructionReadModelService:
    """Build an advisory construction projection from an existing snapshot."""

    MIN_PORTFOLIO_VALUE = 0.01

    def build_read_model(
        self,
        *,
        snapshot: Mapping[str, Any],
        target_weights: Mapping[str, float],
        drift_threshold: float = 1.0,
        min_trade_threshold: float = 0.0,
        max_position_weight: Optional[float] = None,
        cash_buffer_target: Optional[float] = None,
        risk_budget_notes: Optional[Mapping[str, Any]] = None,
        confidence: Optional[float] = None,
        confidence_reasons: Optional[List[str]] = None,
        target_source: str = "caller_supplied_fixture",
    ) -> PortfolioConstructionReadModel:
        total_market_value = self._float(snapshot.get("total_market_value"))
        total_cash = self._float(snapshot.get("total_cash"))
        total_equity = self._float(snapshot.get("total_equity")) or (total_market_value + total_cash)
        portfolio_value_too_small = total_market_value < self.MIN_PORTFOLIO_VALUE
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
                position_present=symbol in positions,
                target_weight=normalized_targets.get(symbol, 0.0),
                total_market_value=total_market_value,
                portfolio_value_too_small=portfolio_value_too_small,
                drift_threshold=drift_threshold,
                min_trade_threshold=min_trade_threshold,
                max_position_weight=max_position_weight,
                risk_budget_notes=self._note_list(notes.get(symbol)),
            )
            for symbol in all_symbols
        ]

        current_cash_weight = self._round_pct((total_cash / total_equity * 100.0) if total_equity > 0 else 0.0)
        target_cash_weight = self._round_pct(cash_buffer_target) if cash_buffer_target is not None else None
        cash_drift = (
            self._round_pct(current_cash_weight - target_cash_weight)
            if target_cash_weight is not None
            else None
        )
        cash_suggested_delta_weight = (
            self._round_pct(target_cash_weight - current_cash_weight)
            if target_cash_weight is not None
            else 0.0
        )
        cash_trade_direction = "hold"
        constraint_violations: List[PortfolioConstructionConstraintViolation] = []
        if target_cash_weight is not None:
            if cash_suggested_delta_weight > 0:
                cash_trade_direction = "raise_cash"
            elif cash_suggested_delta_weight < 0:
                cash_trade_direction = "deploy_cash"
            if current_cash_weight < target_cash_weight:
                constraint_violations.append(
                    PortfolioConstructionConstraintViolation(
                        code="cash_buffer_below_target",
                        severity="warning",
                        message=(
                            f"Current cash weight {current_cash_weight}% is below the "
                            f"{target_cash_weight}% advisory cash buffer target."
                        ),
                    )
                )

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
            constraints=PortfolioConstructionAdvisoryConstraints(
                minTradeThreshold=self._round_pct(min_trade_threshold),
                maxPositionWeight=self._round_pct(max_position_weight) if max_position_weight is not None else None,
                cashBufferTarget=target_cash_weight,
                noTradeBand=self._round_pct(drift_threshold),
            ),
            currentCashWeight=current_cash_weight,
            targetCashWeight=target_cash_weight,
            cashDrift=cash_drift,
            cashSuggestedDeltaWeight=cash_suggested_delta_weight,
            cashTradeDirection=cash_trade_direction,
            constraintViolations=constraint_violations,
            riskBudgetNotes=self._note_list(notes.get("portfolio")),
            noTradeReasons=[
                "advisory_read_model_only",
                "no_order_execution",
                "no_broker_integration",
                "no_accounting_mutation",
            ]
            + (["portfolio_value_too_small"] if portfolio_value_too_small else []),
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
                        "has_market_value": False,
                    },
                )
                if self._has_usable_number(item.get("market_value_base")):
                    row["has_market_value"] = True
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
        position_present: bool,
        target_weight: float,
        total_market_value: float,
        portfolio_value_too_small: bool,
        drift_threshold: float,
        min_trade_threshold: float,
        max_position_weight: Optional[float],
        risk_budget_notes: List[str],
    ) -> PortfolioConstructionPositionReadModel:
        market_value = self._float(position.get("market_value"))
        current_weight = self._round_pct(
            (market_value / total_market_value * 100.0) if total_market_value >= self.MIN_PORTFOLIO_VALUE else 0.0
        )
        target_weight = self._round_pct(target_weight)
        drift = self._round_pct(current_weight - target_weight)
        no_action_reasons: List[str] = []
        suggested_delta_weight = 0.0
        estimated_trade_direction = "hold"
        suggested_action = "no_action"
        cap = self._round_pct(max_position_weight) if max_position_weight is not None else None
        constrained_target_weight = min(target_weight, cap) if cap is not None else target_weight
        if portfolio_value_too_small:
            no_action_reasons.append("portfolio_value_too_small")
        if position_present and not bool(position.get("has_market_value")):
            no_action_reasons.append("missing_market_value")
        elif total_market_value <= 0:
            no_action_reasons.append("no_market_value")
        elif abs(drift) <= float(drift_threshold):
            no_action_reasons.append("within_drift_threshold")
        else:
            suggested_delta_weight = self._round_pct(constrained_target_weight - current_weight)
            if abs(suggested_delta_weight) < float(min_trade_threshold):
                suggested_delta_weight = 0.0
                no_action_reasons.append("below_min_trade_threshold")
            elif suggested_delta_weight > 0:
                suggested_action = "increase_exposure"
                estimated_trade_direction = "buy"
            else:
                suggested_action = "reduce_exposure"
                estimated_trade_direction = "sell"

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
            suggestedDeltaWeight=suggested_delta_weight,
            estimatedTradeDirection=estimated_trade_direction,
            suggestedAction=suggested_action,
            currentMarketValue=self._round_money(market_value),
            constraintViolations=self._constraint_violations(
                current_weight=current_weight,
                position_present=position_present,
                has_market_value=bool(position.get("has_market_value")),
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
        position_present: bool,
        has_market_value: bool,
        max_position_weight: Optional[float],
    ) -> List[PortfolioConstructionConstraintViolation]:
        violations: List[PortfolioConstructionConstraintViolation] = []
        if position_present and not has_market_value:
            violations.append(
                PortfolioConstructionConstraintViolation(
                    code="missing_market_value",
                    severity="warning",
                    message="Current holding has no usable market value in the read-only snapshot.",
                )
            )
        if max_position_weight is None:
            return violations
        cap = self._round_pct(max_position_weight)
        if current_weight <= cap:
            return violations
        violations.append(
            PortfolioConstructionConstraintViolation(
                code="max_position_weight_exceeded",
                severity="warning",
                message=f"Current weight {current_weight}% is above the {cap}% advisory cap.",
            )
        )
        return violations

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
    def _has_usable_number(value: Any) -> bool:
        if value is None or value == "":
            return False
        try:
            float(value)
        except (TypeError, ValueError):
            return False
        return True

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
