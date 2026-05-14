# -*- coding: utf-8 -*-
"""Raw Sina HTTP transport helpers for Market Overview CN index quotes."""

from __future__ import annotations

from typing import Dict, List, Sequence

import requests


SINA_TIMEOUT_SECONDS = 8


def fetch_sina_cn_index_rows(symbols: Sequence[str]) -> Dict[str, List[str]]:
    response = requests.get(
        "https://hq.sinajs.cn/list=" + ",".join(symbols),
        headers={"Referer": "https://finance.sina.com.cn/"},
        timeout=SINA_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "gbk"
    return parse_sina_quote_response(response.text)


def parse_sina_quote_response(text: str) -> Dict[str, List[str]]:
    rows: Dict[str, List[str]] = {}
    for line in text.splitlines():
        if "hq_str_" not in line or '="' not in line:
            continue
        prefix, raw_values = line.split('="', 1)
        symbol = prefix.rsplit("hq_str_", 1)[-1]
        values = raw_values.rstrip('";').split(",")
        if values and values[0]:
            rows[symbol] = values
    return rows
