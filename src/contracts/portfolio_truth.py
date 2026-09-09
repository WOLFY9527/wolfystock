"""Shared machine-readable authority for aggregate Portfolio value semantics."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class PortfolioTruth(BaseModel):
    """Machine-readable authority for interpreting aggregate portfolio values."""

    state: Literal[
        "no_account",
        "account_no_holdings",
        "valuation_unavailable",
        "valuation_partial",
        "fully_valued_zero",
        "fully_valued_nonzero",
    ]
    account_state: Literal["no_account", "no_holdings", "holdings_present"]
    valuation_state: Literal["not_applicable", "unavailable", "partial", "fully_valued"]
    value_semantics: Literal["not_applicable", "unavailable", "covered_subtotal", "authoritative_total"]
    authoritative_total: Optional[Decimal] = None
    covered_subtotal: Optional[Decimal] = None
    account_count: int = Field(ge=0)
    position_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_value_semantics(self) -> "PortfolioTruth":
        if self.value_semantics == "authoritative_total":
            if self.authoritative_total is None or self.covered_subtotal is not None:
                raise ValueError("authoritative_total semantics require only authoritative_total")
        elif self.value_semantics == "covered_subtotal":
            if self.authoritative_total is not None or self.covered_subtotal is None:
                raise ValueError("covered_subtotal semantics require only covered_subtotal")
        elif self.authoritative_total is not None or self.covered_subtotal is not None:
            raise ValueError("unavailable and not_applicable semantics cannot include numeric totals")

        expected = {
            "no_account": ("no_account", "not_applicable", "not_applicable"),
            "account_no_holdings": ("no_holdings", "fully_valued", "authoritative_total"),
            "valuation_unavailable": (None, "unavailable", "unavailable"),
            "valuation_partial": (None, "partial", "covered_subtotal"),
            "fully_valued_zero": ("holdings_present", "fully_valued", "authoritative_total"),
            "fully_valued_nonzero": ("holdings_present", "fully_valued", "authoritative_total"),
        }[self.state]
        expected_account_state, expected_valuation_state, expected_value_semantics = expected
        if expected_account_state is not None and self.account_state != expected_account_state:
            raise ValueError("portfolio truth state and account_state disagree")
        if self.valuation_state != expected_valuation_state or self.value_semantics != expected_value_semantics:
            raise ValueError("portfolio truth state and valuation semantics disagree")
        if self.state == "no_account" and (self.account_count != 0 or self.position_count != 0):
            raise ValueError("no_account truth cannot include accounts or positions")
        if self.state == "account_no_holdings" and (self.account_count == 0 or self.position_count != 0):
            raise ValueError("account_no_holdings truth requires an account with no positions")
        if self.state in {"valuation_unavailable", "valuation_partial"} and self.account_count == 0:
            raise ValueError("valuation truth requires an existing account")
        if self.state in {"fully_valued_zero", "fully_valued_nonzero"} and (
            self.account_count == 0 or self.position_count == 0
        ):
            raise ValueError("fully valued truth requires an account with positions")
        if self.state == "fully_valued_zero" and self.authoritative_total != 0:
            raise ValueError("fully_valued_zero truth requires a zero authoritative_total")
        if self.state == "fully_valued_nonzero" and self.authoritative_total == 0:
            raise ValueError("fully_valued_nonzero truth requires a nonzero authoritative_total")
        return self
