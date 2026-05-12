# -*- coding: utf-8 -*-
"""Pure Yahoo/yfinance symbol helpers shared outside provider runtime."""

from __future__ import annotations

from src.utils.symbol_classification import is_bse_code, is_us_stock_code


_US_INDEX_YF_MAPPING: dict[str, tuple[str, str]] = {
    "SPX": ("^GSPC", "标普500指数"),
    "^GSPC": ("^GSPC", "标普500指数"),
    "GSPC": ("^GSPC", "标普500指数"),
    "DJI": ("^DJI", "道琼斯工业指数"),
    "^DJI": ("^DJI", "道琼斯工业指数"),
    "DJIA": ("^DJI", "道琼斯工业指数"),
    "IXIC": ("^IXIC", "纳斯达克综合指数"),
    "^IXIC": ("^IXIC", "纳斯达克综合指数"),
    "NASDAQ": ("^IXIC", "纳斯达克综合指数"),
    "NDX": ("^NDX", "纳斯达克100指数"),
    "^NDX": ("^NDX", "纳斯达克100指数"),
    "VIX": ("^VIX", "VIX恐慌指数"),
    "^VIX": ("^VIX", "VIX恐慌指数"),
    "RUT": ("^RUT", "罗素2000指数"),
    "^RUT": ("^RUT", "罗素2000指数"),
}


def get_us_index_yf_symbol(code: str | None) -> tuple[str | None, str | None]:
    """Return the Yahoo Finance symbol and label for supported US index aliases."""
    normalized = (code or "").strip().upper()
    return _US_INDEX_YF_MAPPING.get(normalized, (None, None))


def to_yfinance_symbol(stock_code: str) -> str:
    """Convert a stock/index code into the Yahoo Finance symbol expected by yfinance."""
    code = str(stock_code or "").strip().upper()

    yf_symbol, _ = get_us_index_yf_symbol(code)
    if yf_symbol:
        return yf_symbol

    if is_us_stock_code(code):
        return code

    if code.startswith("HK"):
        hk_code = code[2:].lstrip("0") or "0"
        return f"{hk_code.zfill(4)}.HK"

    if any(suffix in code for suffix in (".SS", ".SZ", ".HK", ".BJ")):
        return code

    code = code.replace(".SH", "")

    if len(code) == 6:
        if code.startswith(("51", "52", "56", "58")):
            return f"{code}.SS"
        if code.startswith(("15", "16", "18")):
            return f"{code}.SZ"

    if is_bse_code(code):
        base = code.split(".")[0] if "." in code else code
        return f"{base}.BJ"

    if code.startswith(("600", "601", "603", "688")):
        return f"{code}.SS"
    if code.startswith(("000", "002", "300")):
        return f"{code}.SZ"
    return f"{code}.SZ"
