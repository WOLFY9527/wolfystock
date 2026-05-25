# -*- coding: utf-8 -*-
"""Pure diagnostic reason-code vocabulary classification helpers.

This module is intentionally additive and inert. It classifies existing raw
reason codes into coarse normalized families for diagnostics only. It does not
change scoring, readiness, provider routing, cache behavior, API payloads, or
frontend behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable


REASON_CODE_FAMILIES = (
    "malformed",
    "missing",
    "unavailable",
    "fallback",
    "proxy",
    "stale",
    "partial",
    "synthetic",
    "authority_rejected",
    "reproducibility_degraded",
    "observation_only",
    "source_confidence_cap",
    "unclassified",
)


@dataclass(frozen=True, slots=True)
class ReasonCodeClassification:
    raw_code: str | None
    family: str
    scope: str | None = None


_CLASSIFICATION_RULES = MappingProxyType(
    {
        # Source-confidence canonical cap/degradation codes.
        "unavailable_source": ("unavailable", "source_confidence"),
        "synthetic_source": ("synthetic", "source_confidence"),
        "fallback_source": ("fallback", "source_confidence"),
        "stale_source": ("stale", "source_confidence"),
        "partial_coverage": ("partial", "source_confidence"),
        # Proxy and score-cap-adjacent diagnostics.
        "proxy_quote_source_capped": ("source_confidence_cap", "scanner"),
        "public_proxy_not_score_grade": ("source_confidence_cap", "scanner_evidence_packet"),
        "proxy_context_only": ("proxy", "market_overview"),
        "proxy_only_missing_real_source": ("observation_only", "liquidity_monitor"),
        # Official cache/readiness diagnostics.
        "fed_liquidity_required_series_missing_or_stale": ("observation_only", "official_cache_readiness"),
        "cn_money_market_required_series_missing_or_stale": ("observation_only", "official_cache_readiness"),
        "stale_official_release": ("stale", "official_cache_readiness"),
        "missing_cache": ("missing", "official_cache_readiness"),
        "missing_cache_config": ("missing", "official_cache_readiness"),
        "partial_official_coverage": ("partial", "official_cache_readiness"),
        "malformed_official_value": ("malformed", "official_cache_readiness"),
        "unsupported_unit": ("malformed", "official_cache_readiness"),
        "unsupported_value_format": ("malformed", "official_cache_readiness"),
        "parse_error": ("malformed", "official_cache_readiness"),
        # Broad provider and payload diagnostics.
        "malformed_payload": ("malformed", "source_confidence"),
        # Backtest authority/reproducibility diagnostics.
        "provider_forbidden_for_use_case": ("authority_rejected", "backtest_authority"),
        "proxy_source_not_reproducible": ("reproducibility_degraded", "backtest_authority"),
        "source_not_reproducible_for_backtest": ("reproducibility_degraded", "backtest_authority"),
    }
)


def classify_reason_code(code: str | None) -> ReasonCodeClassification:
    """Return normalized diagnostic family metadata for a raw reason code."""
    if code is None:
        return ReasonCodeClassification(raw_code=None, family="missing", scope=None)

    raw_code = str(code).strip()
    if not raw_code:
        return ReasonCodeClassification(raw_code=raw_code, family="missing", scope=None)

    family, scope = _CLASSIFICATION_RULES.get(raw_code.lower(), ("unclassified", None))
    return ReasonCodeClassification(raw_code=raw_code, family=family, scope=scope)


def classify_reason_codes(codes: Iterable[str | None]) -> list[ReasonCodeClassification]:
    """Classify reason codes in input order without de-duplicating duplicates."""
    return [classify_reason_code(code) for code in codes]


__all__ = [
    "REASON_CODE_FAMILIES",
    "ReasonCodeClassification",
    "classify_reason_code",
    "classify_reason_codes",
]
