# -*- coding: utf-8 -*-
"""Curated static leveraged ETF mapping metadata.

This module is intentionally data-only. It must not import provider clients,
cache layers, portfolio services, broker code, or quote/runtime services.
"""

from __future__ import annotations

from dataclasses import dataclass


CURATED_MAPPING_SOURCE_LABEL = "WolfyStock curated leveraged ETF mapping v1"
CURATED_MAPPING_EFFECTIVE_LABEL = "curated_static_v1"


@dataclass(frozen=True, slots=True)
class LeveragedEtfMapping:
    etf_symbol: str
    underlying_symbol: str
    leverage: float
    reference_type: str
    source_label: str = CURATED_MAPPING_SOURCE_LABEL
    effective_label: str = CURATED_MAPPING_EFFECTIVE_LABEL
    notes: tuple[str, ...] = ()

    def to_public_dict(self) -> dict[str, object]:
        return {
            "etfSymbol": self.etf_symbol,
            "underlyingSymbol": self.underlying_symbol,
            "leverage": self.leverage,
            "referenceType": self.reference_type,
            "sourceLabel": self.source_label,
            "effectiveLabel": self.effective_label,
            "notes": list(self.notes),
        }


CURATED_LEVERAGED_ETF_MAPPINGS: tuple[LeveragedEtfMapping, ...] = (
    LeveragedEtfMapping(
        etf_symbol="TSLL",
        underlying_symbol="TSLA",
        leverage=2.0,
        reference_type="single_stock",
        notes=("single-stock leveraged ETF relationship",),
    ),
    LeveragedEtfMapping(
        etf_symbol="NVDL",
        underlying_symbol="NVDA",
        leverage=2.0,
        reference_type="single_stock",
        notes=("single-stock leveraged ETF relationship",),
    ),
    LeveragedEtfMapping(
        etf_symbol="MSTU",
        underlying_symbol="MSTR",
        leverage=2.0,
        reference_type="single_stock",
        notes=("single-stock leveraged ETF relationship",),
    ),
    LeveragedEtfMapping(
        etf_symbol="CONL",
        underlying_symbol="COIN",
        leverage=2.0,
        reference_type="single_stock",
        notes=("single-stock leveraged ETF relationship",),
    ),
    LeveragedEtfMapping(
        etf_symbol="TQQQ",
        underlying_symbol="QQQ",
        leverage=3.0,
        reference_type="proxy_etf",
        notes=("proxy ETF reference for Nasdaq-100 exposure",),
    ),
    LeveragedEtfMapping(
        etf_symbol="SOXL",
        underlying_symbol="SOXX",
        leverage=3.0,
        reference_type="proxy_etf",
        notes=("proxy ETF reference for semiconductor exposure",),
    ),
)


CURATED_LEVERAGED_ETF_MAPPING_BY_SYMBOL: dict[str, LeveragedEtfMapping] = {
    mapping.etf_symbol: mapping for mapping in CURATED_LEVERAGED_ETF_MAPPINGS
}
