# -*- coding: utf-8 -*-
"""Raw sentiment HTTP transport helpers for Market Overview."""

from __future__ import annotations

from typing import Any

import requests

from src.services.uat_provider_isolation import require_uat_provider_dispatch_allowed


SENTIMENT_TIMEOUT_SECONDS = 3.0


def fetch_cnn_fear_greed_payload(*, timeout: float = SENTIMENT_TIMEOUT_SECONDS) -> Any:
    require_uat_provider_dispatch_allowed(
        provider="cnn",
        capability="market_overview_sentiment",
        route="market_overview_sentiment_transport.fetch_cnn_fear_greed_payload",
    )
    response = requests.get(
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def fetch_alternative_fear_greed_payload(*, timeout: float = SENTIMENT_TIMEOUT_SECONDS) -> Any:
    require_uat_provider_dispatch_allowed(
        provider="alternative_fng",
        capability="market_overview_sentiment",
        route="market_overview_sentiment_transport.fetch_alternative_fear_greed_payload",
    )
    response = requests.get(
        "https://api.alternative.me/fng/",
        params={"limit": 8, "format": "json"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()
