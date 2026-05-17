# -*- coding: utf-8 -*-
"""Provider contract for future event intelligence adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence, runtime_checkable

from api.v1.schemas.event_intelligence import EventIntelligenceItem


@runtime_checkable
class EventIntelligenceProvider(Protocol):
    def fetch_events(
        self,
        symbol: str,
        market: str,
        start: datetime | None,
        end: datetime | None,
        as_of: datetime,
    ) -> Sequence[EventIntelligenceItem]:
        """Return events visible by ``as_of`` without defining runtime provider behavior."""


__all__ = ["EventIntelligenceProvider"]
