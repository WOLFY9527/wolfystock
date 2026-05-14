# -*- coding: utf-8 -*-
"""Raw sentiment HTTP transport helpers for Market Overview."""

from __future__ import annotations

from typing import Any

import requests


SENTIMENT_TIMEOUT_SECONDS = 8


def fetch_cnn_fear_greed_payload() -> Any:
    response = requests.get(
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        timeout=SENTIMENT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def fetch_alternative_fear_greed_payload() -> Any:
    response = requests.get(
        "https://api.alternative.me/fng/",
        params={"limit": 8, "format": "json"},
        timeout=SENTIMENT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()
