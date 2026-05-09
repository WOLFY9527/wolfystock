# -*- coding: utf-8 -*-
"""Admin-only provider usage ledger diagnostics API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import CurrentUser, require_admin_capability
from src.services.provider_usage_ledger import (
    DEFAULT_PROVIDER_USAGE_LEDGER_MAX_EVENTS,
    get_provider_usage_ledger,
)

router = APIRouter()


@router.get(
    "/provider-usage-ledger",
    summary="Get sanitized provider usage ledger diagnostics",
)
def get_provider_usage_ledger_diagnostics(
    limit: int = Query(default=100, ge=1, le=500),
    research_mode: Optional[str] = Query(default=None, alias="researchMode"),
    provider: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    window_seconds: int = Query(default=3600, ge=1, le=86400, alias="windowSeconds"),
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
):
    ledger = get_provider_usage_ledger()
    since = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    return {
        "events": ledger.snapshot(
            limit=limit,
            since=since,
            research_mode=research_mode,
            provider=provider,
            category=category,
        ),
        "summary": ledger.summarize(window_seconds=window_seconds),
        "metadata": {
            "readOnly": True,
            "durableStorage": False,
            "externalProviderCalls": False,
            "maxEvents": DEFAULT_PROVIDER_USAGE_LEDGER_MAX_EVENTS,
            "windowSeconds": window_seconds,
        },
    }
