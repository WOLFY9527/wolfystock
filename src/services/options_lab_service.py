# -*- coding: utf-8 -*-
"""Fixture-backed Options Lab Phase 1 service.

Phase 1 deliberately avoids live providers, LLMs, broker execution, and
portfolio mutation. The service only normalizes the synthetic TEM fixture.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from api.v1.schemas.options import (
    OptionChainResponse,
    OptionContract,
    OptionExpirationItem,
    OptionExpirationsResponse,
    OptionGreeks,
    OptionsMetadata,
    OptionUnderlyingSummaryResponse,
)


DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "options" / "tem_chain.json"
PHASE1_WARNING_CODES = [
    "synthetic_fixture_data",
    "options_are_high_risk",
    "long_options_can_lose_100_percent_premium",
    "data_may_be_delayed_or_stale",
    "analytical_only_not_investment_advice",
    "no_order_placement",
]


class OptionsLabUnsupportedSymbol(ValueError):
    """Raised when Phase 1 has no safe fixture for the requested symbol."""

    def __init__(self, symbol: str, code: str = "unsupported_symbol_or_market") -> None:
        self.symbol = symbol
        self.code = code
        super().__init__("Options Lab Phase 1 supports fixture-backed US listed equity options only.")


class OptionsLabService:
    """Read-only normalizer for synthetic Options Lab fixtures."""

    def __init__(self, fixture_path: Optional[Path] = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_FIXTURE_PATH

    def get_summary(self, symbol: str, force_refresh: bool = False) -> OptionUnderlyingSummaryResponse:
        fixture = self._fixture_for_symbol(symbol)
        metadata = self._metadata(force_refresh=force_refresh)
        underlying = self._safe_underlying(fixture)
        return OptionUnderlyingSummaryResponse(
            symbol=fixture["symbol"],
            market=fixture["market"],
            currency=fixture.get("currency", "USD"),
            underlying=underlying,
            optionsAvailability={
                "supported": True,
                "provider": "synthetic_fixture",
                "limitations": ["fixture_only", "provider_validation_required_later"],
            },
            asOf=fixture["chainAsOf"],
            source=fixture["source"],
            warnings=list(PHASE1_WARNING_CODES),
            metadata=metadata,
        )

    def get_expirations(self, symbol: str, force_refresh: bool = False) -> OptionExpirationsResponse:
        fixture = self._fixture_for_symbol(symbol)
        expirations = [
            OptionExpirationItem(
                date=str(item["date"]),
                dte=int(item["dte"]),
                type=str(item.get("type") or "unknown"),
                chainAvailable=bool(item.get("chainAvailable", True)),
                asOf=str(item.get("asOf") or fixture["chainAsOf"]),
                source=fixture["source"],
                warnings=list(item.get("warnings") or []),
            )
            for item in sorted(fixture.get("expirations") or [], key=lambda row: str(row.get("date") or ""))
        ]
        return OptionExpirationsResponse(
            symbol=fixture["symbol"],
            market=fixture["market"],
            expirations=expirations,
            asOf=fixture["chainAsOf"],
            source=fixture["source"],
            warnings=list(PHASE1_WARNING_CODES),
            metadata=self._metadata(force_refresh=force_refresh),
        )

    def get_chain(
        self,
        symbol: str,
        expiration: Optional[str] = None,
        side: str = "both",
        min_open_interest: Optional[int] = None,
        max_spread_pct: Optional[float] = None,
        include_greeks: bool = True,
        force_refresh: bool = False,
    ) -> OptionChainResponse:
        fixture = self._fixture_for_symbol(symbol)
        normalized_side = (side or "both").strip().lower()
        if normalized_side not in {"call", "put", "both"}:
            raise ValueError("side must be call, put, or both")

        contracts = list(self._contracts_for_fixture(fixture, include_greeks=include_greeks))
        if expiration:
            contracts = [contract for contract in contracts if contract.expiration == expiration]
        if min_open_interest is not None:
            contracts = [
                contract
                for contract in contracts
                if contract.open_interest is not None and contract.open_interest >= min_open_interest
            ]
        if max_spread_pct is not None:
            contracts = [
                contract
                for contract in contracts
                if contract.spread_pct is not None and contract.spread_pct <= max_spread_pct
            ]

        calls = [contract for contract in contracts if contract.side == "call" and normalized_side in {"call", "both"}]
        puts = [contract for contract in contracts if contract.side == "put" and normalized_side in {"put", "both"}]
        return OptionChainResponse(
            symbol=fixture["symbol"],
            market=fixture["market"],
            underlying=self._safe_underlying(fixture),
            expiration=expiration,
            calls=calls,
            puts=puts,
            filtersApplied={
                "expiration": expiration,
                "side": normalized_side,
                "minOpenInterest": min_open_interest,
                "maxSpreadPct": max_spread_pct,
                "includeGreeks": include_greeks,
                "forceRefresh": force_refresh,
            },
            chainAsOf=fixture["chainAsOf"],
            source=fixture["source"],
            warnings=list(PHASE1_WARNING_CODES),
            metadata=self._metadata(force_refresh=force_refresh),
        )

    def _fixture_for_symbol(self, symbol: str) -> Dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        if normalized != "TEM" or not self._is_us_equity_symbol(normalized):
            raise OptionsLabUnsupportedSymbol(normalized)
        with self.fixture_path.open("r", encoding="utf-8") as handle:
            fixture = json.load(handle)
        if str(fixture.get("symbol") or "").upper() != normalized:
            raise OptionsLabUnsupportedSymbol(normalized)
        return fixture

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return re.sub(r"\s+", "", str(symbol or "")).upper()

    @staticmethod
    def _is_us_equity_symbol(symbol: str) -> bool:
        return bool(re.fullmatch(r"[A-Z]{1,5}", symbol))

    @staticmethod
    def _metadata(force_refresh: bool = False) -> OptionsMetadata:
        return OptionsMetadata(forceRefreshIgnored=bool(force_refresh))

    @staticmethod
    def _safe_underlying(fixture: Dict[str, Any]) -> Dict[str, Any]:
        underlying = copy.deepcopy(fixture.get("underlying") or {})
        return {
            "price": underlying.get("price"),
            "changePct": underlying.get("changePct"),
            "source": "synthetic_fixture",
            "asOf": underlying.get("asOf") or fixture.get("chainAsOf"),
            "freshness": underlying.get("freshness") or "synthetic_delayed",
        }

    def _contracts_for_fixture(self, fixture: Dict[str, Any], include_greeks: bool) -> Iterable[OptionContract]:
        expiration_dte = {str(item["date"]): int(item["dte"]) for item in fixture.get("expirations") or []}
        underlying_price = float((fixture.get("underlying") or {}).get("price") or 0)
        for item in sorted(
            fixture.get("contracts") or [],
            key=lambda row: (str(row.get("expiration") or ""), str(row.get("side") or ""), float(row.get("strike") or 0)),
        ):
            bid = self._float_or_none(item.get("bid"))
            ask = self._float_or_none(item.get("ask"))
            mid = self._mid(bid, ask)
            spread_pct = self._spread_pct(bid, ask, mid)
            expiration = str(item.get("expiration") or "")
            yield OptionContract(
                symbol=fixture["symbol"],
                contractSymbol=str(item.get("contractSymbol") or ""),
                side=str(item.get("side") or "").lower(),
                expiration=expiration,
                strike=float(item.get("strike") or 0),
                bid=bid,
                ask=ask,
                mid=mid,
                last=self._float_or_none(item.get("last")),
                volume=self._int_or_none(item.get("volume")),
                openInterest=self._int_or_none(item.get("openInterest")),
                impliedVolatility=self._float_or_none(item.get("impliedVolatility")),
                greeks=OptionGreeks(**dict(item.get("greeks") or {})) if include_greeks and item.get("greeks") else None,
                dte=expiration_dte.get(expiration, 0),
                moneyness=self._moneyness(str(item.get("side") or ""), float(item.get("strike") or 0), underlying_price),
                spreadPct=spread_pct,
                liquidityBucket=self._liquidity_bucket(spread_pct, self._int_or_none(item.get("openInterest"))),
                asOf=fixture["chainAsOf"],
                source=fixture["source"],
                warnings=["synthetic_fixture_data", "delayed_or_stale_data_possible"],
            )

    @staticmethod
    def _float_or_none(value: Any) -> Optional[float]:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _int_or_none(value: Any) -> Optional[int]:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _mid(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
        if bid is None or ask is None:
            return None
        return round((bid + ask) / 2, 4)

    @staticmethod
    def _spread_pct(bid: Optional[float], ask: Optional[float], mid: Optional[float]) -> Optional[float]:
        if bid is None or ask is None or mid in (None, 0):
            return None
        return round(((ask - bid) / mid) * 100, 2)

    @staticmethod
    def _moneyness(side: str, strike: float, underlying_price: float) -> str:
        if not strike or not underlying_price:
            return "unknown"
        if abs(strike - underlying_price) / underlying_price <= 0.03:
            return "atm"
        normalized_side = side.lower()
        if normalized_side == "call":
            return "itm" if strike < underlying_price else "otm"
        if normalized_side == "put":
            return "itm" if strike > underlying_price else "otm"
        return "unknown"

    @staticmethod
    def _liquidity_bucket(spread_pct: Optional[float], open_interest: Optional[int]) -> str:
        if spread_pct is None or open_interest is None:
            return "unknown"
        if spread_pct <= 10 and open_interest >= 500:
            return "tight"
        if spread_pct <= 25 and open_interest >= 100:
            return "moderate"
        return "thin"
