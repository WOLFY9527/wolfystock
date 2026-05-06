# -*- coding: utf-8 -*-
"""Provider-neutral options market data contract for Options Lab.

The implementations in this module are fixture-only. Live providers such as
Tradier, IBKR, and Polygon are intentionally represented as disabled names so
future adapters have a contract without creating credentials or network paths.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol


DEFAULT_OPTIONS_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "options" / "tem_chain.json"
DEFAULT_OPTIONS_PROVIDER_NAME = "synthetic_fixture"
LIVE_OPTIONS_PROVIDER_NAMES = {"tradier", "ibkr", "polygon"}


class OptionsProviderError(ValueError):
    """Base provider contract error with a stable code."""

    def __init__(self, message: str, code: str) -> None:
        self.code = code
        super().__init__(message)


class OptionsProviderUnsupportedSymbol(OptionsProviderError):
    """Raised when a fixture provider cannot serve a symbol."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__(
            "Options Lab fixture providers support TEM US listed equity options only.",
            "unsupported_symbol_or_market",
        )


class OptionsProviderUnavailable(OptionsProviderError):
    """Raised when a provider name is known but unavailable."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        super().__init__(
            f"Options provider '{provider_name}' is disabled or not implemented.",
            "options_provider_not_implemented",
        )


@dataclass(frozen=True)
class OptionsProviderCapabilityMetadata:
    provider_name: str
    source_type: str
    fixture_only: bool
    live_enabled: bool
    delayed: bool
    tradeable_data: bool
    supports_expirations: bool = True
    supports_chain: bool = True
    supports_underlying_quote: bool = True
    supports_bid_ask: bool = True
    supports_iv: bool = True
    supports_greeks: bool = True
    supports_open_interest: bool = True
    supports_volume: bool = True
    notes: tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["providerName"] = payload.pop("provider_name")
        payload["sourceType"] = payload.pop("source_type")
        payload["fixtureOnly"] = payload.pop("fixture_only")
        payload["liveEnabled"] = payload.pop("live_enabled")
        payload["tradeableData"] = payload.pop("tradeable_data")
        payload["supportsExpirations"] = payload.pop("supports_expirations")
        payload["supportsChain"] = payload.pop("supports_chain")
        payload["supportsUnderlyingQuote"] = payload.pop("supports_underlying_quote")
        payload["supportsBidAsk"] = payload.pop("supports_bid_ask")
        payload["supportsIv"] = payload.pop("supports_iv")
        payload["supportsGreeks"] = payload.pop("supports_greeks")
        payload["supportsOpenInterest"] = payload.pop("supports_open_interest")
        payload["supportsVolume"] = payload.pop("supports_volume")
        payload["notes"] = list(self.notes)
        return payload


class OptionsMarketDataProvider(Protocol):
    """Provider-neutral interface future live adapters must implement."""

    provider_name: str
    capabilities: OptionsProviderCapabilityMetadata

    def get_expirations(self, symbol: str) -> List[Dict[str, Any]]:
        """Return normalized expiration rows for a supported underlying."""

    def get_underlying_quote(self, symbol: str) -> Dict[str, Any]:
        """Return a sanitized normalized underlying quote snapshot."""

    def get_chain(self, symbol: str, expiration: Optional[str] = None) -> Dict[str, Any]:
        """Return a sanitized normalized option-chain snapshot."""


class _FixtureOptionsProvider:
    provider_name = DEFAULT_OPTIONS_PROVIDER_NAME
    source = "synthetic_options_lab_fixture"
    freshness = "synthetic_delayed"
    provider_quality = "synthetic_demo_only"
    data_quality_tier = "synthetic_demo_only"
    contract_warning = "synthetic_fixture_data"
    force_fixture_metadata = False
    capabilities = OptionsProviderCapabilityMetadata(
        provider_name=provider_name,
        source_type="synthetic",
        fixture_only=True,
        live_enabled=False,
        delayed=True,
        tradeable_data=False,
        notes=("fixture_only", "no_external_calls", "not_decision_grade"),
    )

    def __init__(self, fixture_path: Optional[Path] = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_OPTIONS_FIXTURE_PATH

    def get_expirations(self, symbol: str) -> List[Dict[str, Any]]:
        fixture = self._fixture_for_symbol(symbol)
        return copy.deepcopy(fixture.get("expirations") or [])

    def get_underlying_quote(self, symbol: str) -> Dict[str, Any]:
        fixture = self._fixture_for_symbol(symbol)
        return copy.deepcopy(fixture.get("underlying") or {})

    def get_chain(self, symbol: str, expiration: Optional[str] = None) -> Dict[str, Any]:
        fixture = self._fixture_for_symbol(symbol)
        if expiration:
            fixture["contracts"] = [
                contract for contract in fixture.get("contracts") or [] if str(contract.get("expiration") or "") == expiration
            ]
        return fixture

    def _fixture_for_symbol(self, symbol: str) -> Dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        if normalized != "TEM" or not self._is_us_equity_symbol(normalized):
            raise OptionsProviderUnsupportedSymbol(normalized)
        with self.fixture_path.open("r", encoding="utf-8") as handle:
            fixture = json.load(handle)
        if str(fixture.get("symbol") or "").upper() != normalized:
            raise OptionsProviderUnsupportedSymbol(normalized)
        return self._decorate_fixture(fixture)

    def _decorate_fixture(self, fixture: Dict[str, Any]) -> Dict[str, Any]:
        decorated = copy.deepcopy(fixture)
        snapshot_source = self.source if self.force_fixture_metadata else str(decorated.get("source") or self.source)
        underlying = decorated.setdefault("underlying", {})
        snapshot_freshness = (
            self.freshness
            if self.force_fixture_metadata
            else str(underlying.get("freshness") or self.freshness)
        )
        decorated["providerName"] = self.provider_name
        decorated["source"] = snapshot_source
        decorated["providerQuality"] = self.provider_quality
        decorated["dataQuality"] = {
            "tier": self.data_quality_tier,
            "tradeable": False,
            "hints": list(self.capabilities.notes),
        }
        decorated["providerCapabilities"] = self.capabilities.to_dict()
        underlying["source"] = snapshot_source if self.force_fixture_metadata else underlying.get("source") or snapshot_source
        underlying["freshness"] = snapshot_freshness
        underlying["providerQuality"] = self.provider_quality
        for expiration in decorated.get("expirations") or []:
            expiration["source"] = snapshot_source if self.force_fixture_metadata else expiration.get("source") or snapshot_source
            expiration["freshness"] = snapshot_freshness
        for contract in decorated.get("contracts") or []:
            contract["source"] = snapshot_source if self.force_fixture_metadata else contract.get("source") or snapshot_source
            contract["freshness"] = snapshot_freshness
            contract["providerQuality"] = self.provider_quality
            contract["dataQuality"] = copy.deepcopy(decorated["dataQuality"])
            warnings = list(contract.get("warnings") or [])
            if self.contract_warning not in warnings:
                warnings.append(self.contract_warning)
            contract["warnings"] = warnings
        return decorated

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return re.sub(r"\s+", "", str(symbol or "")).upper()

    @staticmethod
    def _is_us_equity_symbol(symbol: str) -> bool:
        return bool(re.fullmatch(r"[A-Z]{1,5}", symbol))


class SyntheticFixtureOptionsProvider(_FixtureOptionsProvider):
    """Synthetic Options Lab fixture provider."""


class DelayedFixtureOptionsProvider(_FixtureOptionsProvider):
    """Real-shaped delayed fixture provider with no live calls."""

    provider_name = "delayed_fixture"
    source = "delayed_provider_fixture"
    freshness = "delayed"
    provider_quality = "delayed_fixture_only"
    data_quality_tier = "delayed_usable"
    contract_warning = "delayed_fixture_data_not_tradeable"
    force_fixture_metadata = True
    capabilities = OptionsProviderCapabilityMetadata(
        provider_name=provider_name,
        source_type="delayed",
        fixture_only=True,
        live_enabled=False,
        delayed=True,
        tradeable_data=False,
        notes=("real_shaped_fixture", "delayed_data", "tradeability_policy_disabled"),
    )


class MalformedGreeksFixtureOptionsProvider(_FixtureOptionsProvider):
    """Fixture provider that simulates missing IV/Greeks fields."""

    provider_name = "malformed_fixture"
    source = "malformed_missing_greeks_fixture"
    freshness = "fixture_malformed"
    provider_quality = "incomplete_fixture_only"
    data_quality_tier = "insufficient"
    contract_warning = "missing_greeks_fixture_data"
    force_fixture_metadata = True
    capabilities = OptionsProviderCapabilityMetadata(
        provider_name=provider_name,
        source_type="fixture",
        fixture_only=True,
        live_enabled=False,
        delayed=True,
        tradeable_data=False,
        supports_iv=False,
        supports_greeks=False,
        notes=("malformed_fixture", "missing_greeks", "not_decision_grade"),
    )

    def _decorate_fixture(self, fixture: Dict[str, Any]) -> Dict[str, Any]:
        decorated = super()._decorate_fixture(fixture)
        for contract in decorated.get("contracts") or []:
            contract.pop("greeks", None)
            contract["impliedVolatility"] = None
            contract["dataQuality"] = {
                "tier": "insufficient",
                "tradeable": False,
                "hints": ["missing_iv", "missing_greeks"],
            }
        return decorated


def create_options_market_data_provider(
    provider_name: str = DEFAULT_OPTIONS_PROVIDER_NAME,
    fixture_path: Optional[Path] = None,
) -> OptionsMarketDataProvider:
    """Create a fixture provider or reject disabled live providers."""

    normalized = (provider_name or DEFAULT_OPTIONS_PROVIDER_NAME).strip().lower()
    if normalized in LIVE_OPTIONS_PROVIDER_NAMES:
        raise OptionsProviderUnavailable(normalized)
    if normalized in {"synthetic_fixture", "synthetic", "fixture"}:
        return SyntheticFixtureOptionsProvider(fixture_path=fixture_path)
    if normalized in {"delayed_fixture", "real_shaped_delayed_fixture"}:
        return DelayedFixtureOptionsProvider(fixture_path=fixture_path)
    if normalized in {"malformed_fixture", "missing_greeks_fixture"}:
        return MalformedGreeksFixtureOptionsProvider(fixture_path=fixture_path)
    raise OptionsProviderUnavailable(normalized)
