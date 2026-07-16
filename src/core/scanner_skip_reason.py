"""Pure scanner skip-reason normalization."""

from __future__ import annotations

from typing import Sequence


def normalize_scanner_skip_reason(
    *,
    status: object,
    reason: object,
    failed_rules: Sequence[object],
    missing_fields: Sequence[object],
) -> str:
    tokens = " ".join(
        str(item or "").strip().lower()
        for item in [status, reason, *failed_rules, *missing_fields]
        if str(item or "").strip()
    )
    if status == "selected":
        return "selected"
    if status == "data_failed" or "not_enough_history" in tokens or "missing price history" in tokens:
        return "history_coverage"
    if "history" in tokens and ("missing" in tokens or "insufficient" in tokens):
        return "history_coverage"
    if "below_score_threshold" in tokens:
        return "score_fit"
    if any(marker in tokens for marker in ("liquidity", "volume", "amount", "turnover")):
        return "liquidity"
    if "price" in tokens:
        return "price_range"
    if any(marker in tokens for marker in ("trend", "ma20", "ma60")):
        return "trend_fit"
    if "momentum" in tokens:
        return "momentum_fit"
    if any(marker in tokens for marker in ("unsupported_market", "benchmark_symbol_skipped", "duplicate_symbol")):
        return "universe_scope"
    if any(marker in tokens for marker in ("invalid_payload", "invalid", "payload")):
        return "input_validation"
    return "other"
