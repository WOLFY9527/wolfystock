# -*- coding: utf-8 -*-
"""Inert official macro source contracts for future Market Overview wiring.

This module is metadata only. It must not import provider clients, call
networks, read credentials, affect runtime provider order, or change cache/API
behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


_SOURCE_TYPE_OFFICIAL_PUBLIC = "official_public"
_DXY_SYMBOL_GUARD_NOTE = "DXY must not be replaced by a different USD index under the same symbol."


@dataclass(frozen=True)
class OfficialMacroSourceContract:
    source_id: str
    display_name: str
    source_type: str
    cadence: str
    expected_freshness_window: str
    series_codes: tuple[str, ...]
    requires_api_key_or_config: bool
    live_eligible: bool
    delayed_eligible: bool
    observation_only: bool
    notes: tuple[str, ...]


def _notes(*extra: str) -> tuple[str, ...]:
    return (_DXY_SYMBOL_GUARD_NOTE, *extra)


_CONTRACTS = tuple(
    sorted(
        (
            OfficialMacroSourceContract(
                source_id="FRED_CREDIT_SPREAD_OPTIONAL",
                display_name="FRED Credit Spread Series (Optional)",
                source_type=_SOURCE_TYPE_OFFICIAL_PUBLIC,
                cadence="business_daily",
                expected_freshness_window="Only after an approved FRED spread series is selected; not wired by default.",
                series_codes=(),
                requires_api_key_or_config=False,
                live_eligible=False,
                delayed_eligible=False,
                observation_only=True,
                notes=_notes(
                    "Optional placeholder only; approve concrete credit-spread series codes before runtime wiring.",
                ),
            ),
            OfficialMacroSourceContract(
                source_id="FRED_DGS10",
                display_name="FRED US Treasury 10Y Constant Maturity",
                source_type=_SOURCE_TYPE_OFFICIAL_PUBLIC,
                cadence="business_daily",
                expected_freshness_window="Expect official daily publication on the next business-day refresh cycle.",
                series_codes=("DGS10",),
                requires_api_key_or_config=False,
                live_eligible=False,
                delayed_eligible=True,
                observation_only=True,
                notes=_notes(
                    "FRED relays the official Treasury daily yield series; do not treat it as intraday live rates.",
                ),
            ),
            OfficialMacroSourceContract(
                source_id="FRED_DGS2",
                display_name="FRED US Treasury 2Y Constant Maturity",
                source_type=_SOURCE_TYPE_OFFICIAL_PUBLIC,
                cadence="business_daily",
                expected_freshness_window="Expect official daily publication on the next business-day refresh cycle.",
                series_codes=("DGS2",),
                requires_api_key_or_config=False,
                live_eligible=False,
                delayed_eligible=True,
                observation_only=True,
                notes=_notes(
                    "FRED relays the official Treasury daily yield series; do not treat it as intraday live rates.",
                ),
            ),
            OfficialMacroSourceContract(
                source_id="FRED_DGS30",
                display_name="FRED US Treasury 30Y Constant Maturity",
                source_type=_SOURCE_TYPE_OFFICIAL_PUBLIC,
                cadence="business_daily",
                expected_freshness_window="Expect official daily publication on the next business-day refresh cycle.",
                series_codes=("DGS30",),
                requires_api_key_or_config=False,
                live_eligible=False,
                delayed_eligible=True,
                observation_only=True,
                notes=_notes(
                    "FRED relays the official Treasury daily yield series; do not treat it as intraday live rates.",
                ),
            ),
            OfficialMacroSourceContract(
                source_id="FRED_SOFR",
                display_name="FRED SOFR",
                source_type=_SOURCE_TYPE_OFFICIAL_PUBLIC,
                cadence="business_daily",
                expected_freshness_window="Expect next-business-day publication after the overnight reference window closes.",
                series_codes=("SOFR",),
                requires_api_key_or_config=False,
                live_eligible=False,
                delayed_eligible=True,
                observation_only=True,
                notes=_notes(
                    "FRED mirrors official SOFR history; use as a normalized relay, not as a faster-than-official feed.",
                ),
            ),
            OfficialMacroSourceContract(
                source_id="FRED_VIXCLS",
                display_name="FRED CBOE VIX Close",
                source_type=_SOURCE_TYPE_OFFICIAL_PUBLIC,
                cadence="daily_close",
                expected_freshness_window="Expect one official close per US market day after the cash-session close.",
                series_codes=("VIXCLS",),
                requires_api_key_or_config=False,
                live_eligible=False,
                delayed_eligible=True,
                observation_only=True,
                notes=_notes(
                    "Daily close only; do not present this series as an intraday live volatility feed.",
                ),
            ),
            OfficialMacroSourceContract(
                source_id="NYFED_SOFR",
                display_name="New York Fed SOFR",
                source_type=_SOURCE_TYPE_OFFICIAL_PUBLIC,
                cadence="business_daily",
                expected_freshness_window="Expect next-business-day publication after the overnight reference window closes.",
                series_codes=("SOFR",),
                requires_api_key_or_config=False,
                live_eligible=False,
                delayed_eligible=True,
                observation_only=True,
                notes=_notes(
                    "Primary official SOFR publication source for downstream reference-rate integrations.",
                ),
            ),
            OfficialMacroSourceContract(
                source_id="TREASURY_DAILY_RATES",
                display_name="US Treasury Daily Par Yield Curve Rates",
                source_type=_SOURCE_TYPE_OFFICIAL_PUBLIC,
                cadence="business_daily",
                expected_freshness_window="Expect one official Treasury publication per business day after the daily curve release.",
                series_codes=("BC_2YEAR", "BC_10YEAR", "BC_30YEAR"),
                requires_api_key_or_config=False,
                live_eligible=False,
                delayed_eligible=True,
                observation_only=True,
                notes=_notes(
                    "Use tenor-specific mappings for daily published rates; do not reinterpret unlabeled table values as live ticks.",
                ),
            ),
        ),
        key=lambda item: item.source_id,
    )
)

_CONTRACTS_BY_ID = MappingProxyType({item.source_id: item for item in _CONTRACTS})


def list_official_macro_sources() -> tuple[OfficialMacroSourceContract, ...]:
    """Return deterministic official macro source contracts."""
    return tuple(_CONTRACTS)


def get_official_macro_source(source_id: str | None) -> OfficialMacroSourceContract | None:
    """Return a single official macro source contract by id."""
    normalized = str(source_id or "").strip().upper()
    if not normalized:
        return None
    return _CONTRACTS_BY_ID.get(normalized)
