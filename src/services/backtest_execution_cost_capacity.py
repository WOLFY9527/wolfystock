# -*- coding: utf-8 -*-
"""Pure execution cost and capacity modeling helpers for backtest diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ExecutionCostCapacityConfig:
    """Normalized assumptions for additive execution-cost/capacity estimates."""

    commission_bps: float = 0.0
    minimum_fee: float = 0.0
    slippage_bps: float = 0.0
    spread_bps: float = 0.0
    volume_participation_cap: Optional[float] = None
    max_notional_per_trade: Optional[float] = None

    def normalized(self) -> "ExecutionCostCapacityConfig":
        return ExecutionCostCapacityConfig(
            commission_bps=max(0.0, float(self.commission_bps or 0.0)),
            minimum_fee=max(0.0, float(self.minimum_fee or 0.0)),
            slippage_bps=max(0.0, float(self.slippage_bps or 0.0)),
            spread_bps=max(0.0, float(self.spread_bps or 0.0)),
            volume_participation_cap=(
                None
                if self.volume_participation_cap is None
                else max(0.0, float(self.volume_participation_cap))
            ),
            max_notional_per_trade=(
                None if self.max_notional_per_trade is None else max(0.0, float(self.max_notional_per_trade))
            ),
        )

    def has_costs_or_caps(self) -> bool:
        cfg = self.normalized()
        return any(
            (
                cfg.commission_bps > 0.0,
                cfg.minimum_fee > 0.0,
                cfg.slippage_bps > 0.0,
                cfg.spread_bps > 0.0,
                cfg.volume_participation_cap is not None,
                cfg.max_notional_per_trade is not None,
            )
        )

    def to_assumptions(self) -> Dict[str, Any]:
        cfg = self.normalized()
        return {
            "version": "execution_cost_capacity_v1",
            "model_scope": "additive_diagnostic_helper_only",
            "commission_model": "bps_on_filled_notional",
            "commission_bps": _round(cfg.commission_bps),
            "minimum_fee": _round(cfg.minimum_fee),
            "minimum_fee_model": "fixed_minimum_per_filled_trade" if cfg.minimum_fee > 0.0 else "not_applied",
            "slippage_model": "bps_on_filled_notional",
            "slippage_bps": _round(cfg.slippage_bps),
            "spread_model": "one_way_bps_on_filled_notional",
            "spread_bps": _round(cfg.spread_bps),
            "volume_participation_cap": _round(cfg.volume_participation_cap),
            "max_notional_per_trade": _round(cfg.max_notional_per_trade),
            "capacity_fill_policy": "min(requested_quantity, volume_cap_quantity, max_notional_quantity)",
            "missing_volume_policy": "no_fill_when_volume_cap_is_configured",
            "output_ordering": "trade_date_symbol_input_sequence",
            "input_mutation": "never",
            "default_zero_cost_preserves_backtest_math": not cfg.has_costs_or_caps(),
        }


def evaluate_execution_cost_capacity(
    trades: Sequence[Any],
    *,
    bars: Optional[Sequence[Any]] = None,
    config: Optional[ExecutionCostCapacityConfig] = None,
) -> Dict[str, Any]:
    """Return deterministic per-trade and aggregate execution cost/capacity estimates.

    This helper is intentionally pure. It reads dict-like or object-like trade
    and bar fixtures, never mutates them, and is not wired into default backtest
    math unless a caller explicitly consumes its returned diagnostics.
    """

    cfg = (config or ExecutionCostCapacityConfig()).normalized()
    volume_index = _build_volume_index(bars or [])
    trade_rows = [
        _evaluate_trade(input_sequence=index, trade=trade, volume_index=volume_index, config=cfg)
        for index, trade in enumerate(list(trades or []))
    ]
    ordered_rows = sorted(
        trade_rows,
        key=lambda row: (str(row.get("trade_date") or ""), str(row.get("symbol") or ""), int(row["input_sequence"])),
    )
    return {
        "assumptions": cfg.to_assumptions(),
        "trades": ordered_rows,
        "summary": _build_summary(ordered_rows),
    }


def _evaluate_trade(
    *,
    input_sequence: int,
    trade: Any,
    volume_index: Mapping[Tuple[str, str], Optional[float]],
    config: ExecutionCostCapacityConfig,
) -> Dict[str, Any]:
    trade_id = _text(_read(trade, "trade_id", "id", "order_id")) or str(input_sequence)
    symbol = _text(_read(trade, "symbol", "code", "ticker"))
    trade_date = _date_text(_read(trade, "date", "trade_date", "entry_date", "fill_date"))
    side = (_text(_read(trade, "side", "action")) or "buy").lower()
    price = _safe_float(_read(trade, "price", "reference_price", "fill_price", "entry_price"))
    requested_quantity, requested_notional = _requested_size(trade, price)

    fill_quantity = requested_quantity
    reason_codes: list[str] = []
    volume = _resolve_trade_volume(trade=trade, symbol=symbol, trade_date=trade_date, volume_index=volume_index)

    if price is None or price <= 0.0:
        fill_quantity = 0.0
        reason_codes.append("invalid_price")
    elif requested_quantity <= 0.0:
        fill_quantity = 0.0
        reason_codes.append("non_positive_quantity")
    else:
        if config.max_notional_per_trade is not None:
            max_quantity_by_notional = float(config.max_notional_per_trade) / float(price)
            if max_quantity_by_notional < fill_quantity:
                fill_quantity = max(0.0, max_quantity_by_notional)
                reason_codes.append("max_notional_per_trade")

        if config.volume_participation_cap is not None:
            if volume is None:
                fill_quantity = 0.0
                reason_codes.append("missing_volume")
            elif volume <= 0.0:
                fill_quantity = 0.0
                reason_codes.append("insufficient_volume")
            else:
                max_quantity_by_volume = float(volume) * float(config.volume_participation_cap)
                if max_quantity_by_volume < fill_quantity:
                    fill_quantity = max(0.0, max_quantity_by_volume)
                    reason_codes.append("volume_participation_cap")

    fill_quantity = min(max(0.0, fill_quantity), requested_quantity)
    filled_notional = fill_quantity * float(price or 0.0)
    unfilled_quantity = max(0.0, requested_quantity - fill_quantity)
    unfilled_notional = max(0.0, requested_notional - filled_notional)

    commission_cost = _bps_cost(filled_notional, config.commission_bps)
    if fill_quantity > 0.0 and config.minimum_fee > commission_cost:
        commission_cost = float(config.minimum_fee)
    slippage_cost = _bps_cost(filled_notional, config.slippage_bps)
    spread_cost = _bps_cost(filled_notional, config.spread_bps)
    total_cost = commission_cost + slippage_cost + spread_cost

    fill_status = _fill_status(fill_quantity=fill_quantity, requested_quantity=requested_quantity)
    capacity_warning_codes = _capacity_warning_codes(reason_codes)
    participation_rate = (fill_quantity / volume) if volume and volume > 0.0 else None

    cash_before_cost = filled_notional if side in {"sell", "exit", "reduce"} else -filled_notional
    cash_after_cost = (
        filled_notional - total_cost
        if side in {"sell", "exit", "reduce"}
        else -(filled_notional + total_cost)
    )

    return {
        "input_sequence": int(input_sequence),
        "trade_id": trade_id,
        "symbol": symbol,
        "trade_date": trade_date,
        "side": side,
        "reference_price": _round(price),
        "requested_quantity": _round(requested_quantity),
        "filled_quantity": _round(fill_quantity),
        "unfilled_quantity": _round(unfilled_quantity),
        "requested_notional": _round(requested_notional),
        "filled_notional": _round(filled_notional),
        "unfilled_notional": _round(unfilled_notional),
        "volume": _round(volume),
        "participation_rate": _round(participation_rate),
        "fill_status": fill_status,
        "fill_reason": "filled" if not reason_codes else "+".join(reason_codes),
        "fill_reason_codes": list(reason_codes),
        "capacity_warning_codes": capacity_warning_codes,
        "commission_cost": _round(commission_cost),
        "slippage_cost": _round(slippage_cost),
        "spread_cost": _round(spread_cost),
        "total_cost": _round(total_cost),
        "cash_effect_before_cost": _round(cash_before_cost),
        "cash_effect_after_cost": _round(cash_after_cost),
    }


def _build_summary(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    warning_trade_ids: dict[str, set[str]] = {}
    for row in rows:
        for code in row.get("capacity_warning_codes") or []:
            warning_trade_ids.setdefault(str(code), set()).add(str(row.get("trade_id") or ""))

    capacity_warnings = [
        {
            "code": code,
            "count": len(trade_ids),
            "trade_ids": sorted(trade_ids),
        }
        for code, trade_ids in sorted(warning_trade_ids.items())
    ]

    return {
        "trade_count": len(rows),
        "filled_trade_count": sum(1 for row in rows if row.get("fill_status") == "filled"),
        "partial_fill_count": sum(1 for row in rows if row.get("fill_status") == "partial"),
        "no_fill_count": sum(1 for row in rows if row.get("fill_status") == "no_fill"),
        "requested_notional": _round(sum(float(row.get("requested_notional") or 0.0) for row in rows)),
        "filled_notional": _round(sum(float(row.get("filled_notional") or 0.0) for row in rows)),
        "unfilled_notional": _round(sum(float(row.get("unfilled_notional") or 0.0) for row in rows)),
        "commission_cost": _round(sum(float(row.get("commission_cost") or 0.0) for row in rows)),
        "slippage_cost": _round(sum(float(row.get("slippage_cost") or 0.0) for row in rows)),
        "spread_cost": _round(sum(float(row.get("spread_cost") or 0.0) for row in rows)),
        "total_cost": _round(sum(float(row.get("total_cost") or 0.0) for row in rows)),
        "capacity_warnings": capacity_warnings,
    }


def _build_volume_index(bars: Iterable[Any]) -> Dict[Tuple[str, str], Optional[float]]:
    index: Dict[Tuple[str, str], Optional[float]] = {}
    for bar in bars:
        symbol = _text(_read(bar, "symbol", "code", "ticker"))
        bar_date = _date_text(_read(bar, "date", "trade_date"))
        if not symbol or not bar_date:
            continue
        index[(symbol, bar_date)] = _safe_float(_read(bar, "volume", "vol"))
    return index


def _resolve_trade_volume(
    *,
    trade: Any,
    symbol: str,
    trade_date: str,
    volume_index: Mapping[Tuple[str, str], Optional[float]],
) -> Optional[float]:
    volume = _safe_float(_read(trade, "volume", "bar_volume", "daily_volume"))
    if volume is not None:
        return volume
    return volume_index.get((symbol, trade_date))


def _requested_size(trade: Any, price: Optional[float]) -> tuple[float, float]:
    quantity = _safe_float(_read(trade, "requested_quantity", "quantity", "shares", "qty"))
    explicit_notional = _safe_float(_read(trade, "requested_notional", "notional", "target_notional"))
    if quantity is None and explicit_notional is not None and price and price > 0.0:
        quantity = explicit_notional / price
    requested_quantity = max(0.0, float(quantity or 0.0))
    if requested_quantity > 0.0 and price and price > 0.0:
        requested_notional = requested_quantity * float(price)
    else:
        requested_notional = max(0.0, float(explicit_notional or 0.0))
    return requested_quantity, requested_notional


def _read(value: Any, *keys: str) -> Any:
    if isinstance(value, Mapping):
        for key in keys:
            if key in value:
                return value[key]
        return None
    for key in keys:
        if hasattr(value, key):
            return getattr(value, key)
    return None


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return text


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _round(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 6)


def _bps_cost(notional: float, bps: float) -> float:
    return float(notional) * max(0.0, float(bps or 0.0)) / 10000.0


def _fill_status(*, fill_quantity: float, requested_quantity: float) -> str:
    if fill_quantity <= 0.0:
        return "no_fill"
    if fill_quantity < requested_quantity:
        return "partial"
    return "filled"


def _capacity_warning_codes(reason_codes: Sequence[str]) -> list[str]:
    capacity_codes = {
        "max_notional_per_trade",
        "missing_volume",
        "insufficient_volume",
        "volume_participation_cap",
    }
    return [code for code in reason_codes if code in capacity_codes]


__all__ = ["ExecutionCostCapacityConfig", "evaluate_execution_cost_capacity"]
