# -*- coding: utf-8 -*-
"""Pure market-stat calculations shared by the A-share provider adapters."""

from typing import Any, Dict, Optional

import pandas as pd

from src.utils.symbol_classification import is_bse_code, is_kc_cy_stock, is_st_stock
from src.utils.symbol_normalization import normalize_stock_code


def calculate_market_stats(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Calculate A-share advance, limit, and turnover statistics."""
    import numpy as np

    df = df.copy()

    # Keep the provider payload aliases and their precedence unchanged.
    code_col = next((c for c in ['代码', '股票代码', 'ts_code','stock_code'] if c in df.columns), None)
    name_col = next((c for c in ['名称', '股票名称','name','name'] if c in df.columns), None)
    close_col = next((c for c in ['最新价', '最新价', 'close','lastPrice'] if c in df.columns), None)
    pre_close_col = next((c for c in ['昨收', '昨日收盘', 'pre_close','lastClose'] if c in df.columns), None)
    amount_col = next((c for c in ['成交额', '成交额', 'amount','amount'] if c in df.columns), None)

    limit_up_count = 0
    limit_down_count = 0
    up_count = 0
    down_count = 0
    flat_count = 0

    for code, name, current_price, pre_close, amount in zip(
        df[code_col], df[name_col], df[close_col], df[pre_close_col], df[amount_col]
    ):
        if pd.isna(current_price) or pd.isna(pre_close) or current_price in ['-'] or pre_close in ['-'] or amount == 0:
            continue

        current_price = float(current_price)
        pre_close = float(pre_close)
        pure_code = normalize_stock_code(str(code))

        if is_bse_code(pure_code):
            ratio = 0.30
        elif is_kc_cy_stock(pure_code):
            ratio = 0.20
        elif is_st_stock(name):
            ratio = 0.05
        else:
            ratio = 0.10

        limit_up_price = np.floor(pre_close * (1 + ratio) * 100 + 0.5) / 100.0
        limit_down_price = np.floor(pre_close * (1 - ratio) * 100 + 0.5) / 100.0

        limit_up_price_Tolerance = round(abs(pre_close * (1 + ratio) - limit_up_price), 10)
        limit_down_price_Tolerance = round(abs(pre_close * (1 - ratio) - limit_down_price), 10)

        if current_price > 0:
            is_limit_up = (current_price > 0) and (abs(current_price - limit_up_price) <= limit_up_price_Tolerance)
            is_limit_down = (current_price > 0) and (abs(current_price - limit_down_price) <= limit_down_price_Tolerance)

            if is_limit_up:
                limit_up_count += 1
            if is_limit_down:
                limit_down_count += 1

            if current_price > pre_close:
                up_count += 1
            elif current_price < pre_close:
                down_count += 1
            else:
                flat_count += 1

    stats = {
        'up_count': up_count,
        'down_count': down_count,
        'flat_count': flat_count,
        'limit_up_count': limit_up_count,
        'limit_down_count': limit_down_count,
        'total_amount': 0.0,
    }

    if amount_col and amount_col in df.columns:
        df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
        stats['total_amount'] = (df[amount_col].sum() / 1e8)

    return stats
