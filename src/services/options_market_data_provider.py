# -*- coding: utf-8 -*-
"""Provider-neutral options market data contract for Options Lab.

Fixture providers remain the default. The Tradier HTTP transport is an
explicit opt-in market-data path only; it is never enabled by default and does
not grant Options Lab decision or recommendation authority.
"""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol

import requests

from src.utils.security import sanitize_message


DEFAULT_OPTIONS_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "options" / "tem_chain.json"
DEFAULT_OPTIONS_PROVIDER_NAME = "synthetic_fixture"
TRADIER_OPTIONS_DRY_RUN_SOURCE = "tradier_dry_run_fixture"
TRADIER_OPTIONS_DRY_RUN_FRESHNESS = "delayed_dry_run"
TRADIER_OPTIONS_DRY_RUN_AS_OF = "2026-05-06T13:45:00Z"
TRADIER_OPTIONS_ADAPTER_SOURCE = "tradier_adapter_contract"
TRADIER_OPTIONS_ADAPTER_FRESHNESS = "unknown"
TRADIER_OPTIONS_ADAPTER_QUALITY = "tradier_adapter_contract_not_tradeable"
TRADIER_OPTIONS_HTTP_BASE_URL = "https://api.tradier.com/v1"
TRADIER_OPTIONS_HTTP_TIMEOUT_SECONDS = 2.0
TRADIER_OPTIONS_ADAPTER_NOTES = (
    "tradier_adapter_contract",
    "mock_transport_only",
    "not_tradeable",
    "not_decision_grade",
)
TRADIER_OPTIONS_HTTP_NOTES = (
    "tradier_adapter_contract",
    "http_market_data_transport",
    "not_tradeable",
    "not_decision_grade",
)
DEFAULT_TRADIER_OPTIONS_DRY_RUN_RESPONSE: Dict[str, Any] = {
    "underlying": {
        "symbol": "TEM",
        "last": 52.4,
        "change_percentage": 1.15,
        "trade_date": TRADIER_OPTIONS_DRY_RUN_AS_OF,
    },
    "options": {
        "option": [
            {
                "symbol": "TEM260619C00050000",
                "option_type": "call",
                "expiration_date": "2026-06-19",
                "strike": 50.0,
                "bid": 4.8,
                "ask": 5.2,
                "last": 5.0,
                "volume": 320,
                "open_interest": 1480,
                "greeks": {"mid_iv": 0.62, "delta": 0.61, "gamma": 0.044, "theta": -0.072, "vega": 0.118, "rho": 0.031},
            },
            {
                "symbol": "TEM260619P00050000",
                "option_type": "put",
                "expiration_date": "2026-06-19",
                "strike": 50.0,
                "bid": 2.35,
                "ask": 2.65,
                "last": 2.5,
                "volume": 155,
                "open_interest": 710,
                "greeks": {"mid_iv": 0.64, "delta": -0.39, "gamma": 0.047, "theta": -0.061, "vega": 0.116, "rho": -0.019},
            },
            {
                "symbol": "TEM260821C00060000",
                "option_type": "call",
                "expiration_date": "2026-08-21",
                "strike": 60.0,
                "bid": 4.7,
                "ask": 5.1,
                "last": 4.9,
                "volume": 188,
                "open_interest": 1040,
                "greeks": {"mid_iv": 0.58, "delta": 0.39, "gamma": 0.028, "theta": -0.042, "vega": 0.185, "rho": 0.049},
            },
        ]
    },
}
FIXTURE_OPTIONS_PROVIDER_NAMES = frozenset(
    {
        "synthetic_fixture",
        "synthetic",
        "fixture",
        "delayed_fixture",
        "real_shaped_delayed_fixture",
        "malformed_fixture",
        "missing_greeks_fixture",
    }
)
LIVE_OPTIONS_PROVIDER_NAMES = {"tradier", "ibkr", "polygon"}
ALLOWED_OPTIONS_PROVIDER_KEYS = frozenset(FIXTURE_OPTIONS_PROVIDER_NAMES | LIVE_OPTIONS_PROVIDER_NAMES)
ALLOWED_STAGING_PROBE_ARTIFACT_KEYS = frozenset(
    {"providerId", "status", "timestamp", "timeoutSeconds", "reasonCodes"}
)
_ACCEPTED_STAGING_PROBE_STATUSES = {"accepted", "passed", "success"}
_NON_ACCEPTED_STAGING_PROBE_STATUSES = {"failed", "timeout", "error", "rejected"}
_SENSITIVE_ARTIFACT_MARKERS = (
    "api_key",
    "apikey",
    "api-token",
    "api_token",
    "authorization",
    "bearer",
    "database_url",
    "dsn",
    "password",
    "secret",
    "token",
)


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

    def __init__(
        self,
        provider_name: str,
        code: str = "options_provider_not_implemented",
        message: Optional[str] = None,
    ) -> None:
        self.provider_name = provider_name
        super().__init__(
            message or f"Options provider '{provider_name}' is disabled or not implemented.",
            code,
        )


@dataclass(frozen=True)
class OptionsLiveProviderConfig:
    """Provider-selection policy for disabled live adapter stubs.

    This contract intentionally carries only booleans and provider keys. It does
    not store or expose credential values; env loading classifies only sanitized
    presence/shape states.
    """

    live_providers_enabled: bool = False
    enabled_provider_keys: frozenset[str] = frozenset()
    credentialed_provider_keys: frozenset[str] = frozenset()
    malformed_credential_provider_keys: frozenset[str] = frozenset()
    partial_credential_provider_keys: frozenset[str] = frozenset()
    dry_run_provider_keys: frozenset[str] = frozenset()
    live_probe_provider_keys: frozenset[str] = frozenset()
    live_probe_timeout_seconds: float = 2.0

    def is_provider_enabled(self, provider_name: str) -> bool:
        return provider_name in self.enabled_provider_keys

    def has_credentials(self, provider_name: str) -> bool:
        return self.credential_state(provider_name) == "present"

    def credential_state(self, provider_name: str) -> str:
        normalized = str(provider_name or "").strip().lower()
        if normalized in self.malformed_credential_provider_keys:
            return "malformed"
        if normalized in self.partial_credential_provider_keys:
            return "partial"
        if normalized in self.credentialed_provider_keys:
            return "present"
        return "missing"

    def is_dry_run_enabled(self, provider_name: str) -> bool:
        return provider_name in self.dry_run_provider_keys

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "OptionsLiveProviderConfig":
        values = env or os.environ
        enabled_provider_keys = _provider_key_set(values.get("OPTIONS_LIVE_PROVIDER_KEYS"))
        dry_run_provider_keys = _provider_key_set(values.get("OPTIONS_DRY_RUN_PROVIDER_KEYS"))
        if _env_bool(values, "OPTIONS_TRADIER_ENABLED"):
            enabled_provider_keys.add("tradier")
        if _env_bool(values, "OPTIONS_TRADIER_DRY_RUN_ENABLED"):
            dry_run_provider_keys.add("tradier")
        live_probe_provider_keys = _provider_key_set(values.get("OPTIONS_LIVE_PROVIDER_PROBE_KEYS"))
        if _env_bool(values, "OPTIONS_TRADIER_LIVE_PROBE_ENABLED"):
            live_probe_provider_keys.add("tradier")
        credentialed_provider_keys: set[str] = set()
        malformed_credential_provider_keys: set[str] = set()
        tradier_credential_state = _credential_values_state(
            (values.get("TRADIER_API_TOKEN"), values.get("TRADIER_SANDBOX_API_TOKEN"))
        )
        if tradier_credential_state == "present":
            credentialed_provider_keys.add("tradier")
        elif tradier_credential_state == "malformed":
            malformed_credential_provider_keys.add("tradier")
        return cls(
            live_providers_enabled=_env_bool(values, "OPTIONS_LIVE_PROVIDERS_ENABLED"),
            enabled_provider_keys=frozenset(enabled_provider_keys),
            credentialed_provider_keys=frozenset(credentialed_provider_keys),
            malformed_credential_provider_keys=frozenset(malformed_credential_provider_keys),
            dry_run_provider_keys=frozenset(dry_run_provider_keys),
            live_probe_provider_keys=frozenset(live_probe_provider_keys),
            live_probe_timeout_seconds=_safe_probe_timeout_seconds(values.get("OPTIONS_LIVE_PROVIDER_PROBE_TIMEOUT_SECONDS")),
        )


def _env_bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    value = env.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _provider_key_set(value: Optional[str]) -> set[str]:
    return {item.strip().lower() for item in str(value or "").split(",") if item.strip()}


def _credential_values_state(values: tuple[Optional[str], ...]) -> str:
    states = [_credential_value_state(value) for value in values]
    if "present" in states:
        return "present"
    if "malformed" in states:
        return "malformed"
    return "missing"


def _credential_value_state(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if not text:
        return "missing"
    lowered = text.lower()
    if lowered in {"placeholder", "changeme", "change_me", "example", "demo", "test", "none", "null", "todo"}:
        return "malformed"
    if any(marker in lowered for marker in ("placeholder", "must-not-leak", "redacted", "masked")):
        return "malformed"
    if len(text) < 16:
        return "malformed"
    if re.search(r"\s", text):
        return "malformed"
    return "present"


def _safe_probe_timeout_seconds(value: Optional[str]) -> float:
    if value is None:
        return 2.0
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return 2.0
    return max(0.25, min(parsed, 5.0))


def _safe_http_timeout_seconds(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return TRADIER_OPTIONS_HTTP_TIMEOUT_SECONDS
    return max(0.25, min(parsed, 5.0))


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


class TradierOptionsTransport(Protocol):
    """Small injectable transport seam for mocked Tradier payload contracts."""

    def get_quote(self, symbol: str) -> Mapping[str, Any]:
        """Return a Tradier-shaped quote payload."""

    def get_expirations(self, symbol: str) -> Mapping[str, Any]:
        """Return a Tradier-shaped expirations payload."""

    def get_chain(self, symbol: str, expiration: Optional[str] = None) -> Mapping[str, Any]:
        """Return a Tradier-shaped option-chain payload."""


class TradierOptionsHttpTransport:
    """Explicit opt-in Tradier market-data HTTP transport.

    This class only fetches Tradier-shaped market data. It never reads
    environment variables, prints credentials, submits orders, or mutates
    portfolio state. Callers must construct and inject it explicitly.
    """

    def __init__(
        self,
        *,
        api_token: str,
        base_url: str = TRADIER_OPTIONS_HTTP_BASE_URL,
        timeout_seconds: float = TRADIER_OPTIONS_HTTP_TIMEOUT_SECONDS,
        session: Optional[Any] = None,
    ) -> None:
        credential = str(api_token or "").strip()
        if not credential:
            raise OptionsProviderUnavailable(
                "tradier",
                code="options_provider_credentials_missing",
                message="Options live provider credentials are not configured.",
            )
        self._api_token = credential
        self.base_url = str(base_url or TRADIER_OPTIONS_HTTP_BASE_URL).strip().rstrip("/")
        self.timeout_seconds = _safe_http_timeout_seconds(timeout_seconds)
        self._session = session or requests.Session()

    def get_quote(self, symbol: str) -> Mapping[str, Any]:
        normalized_symbol = self._normalize_symbol(symbol)
        return self._get_json("markets/quotes", {"symbols": normalized_symbol})

    def get_expirations(self, symbol: str) -> Mapping[str, Any]:
        normalized_symbol = self._normalize_symbol(symbol)
        return self._get_json("markets/options/expirations", {"symbol": normalized_symbol})

    def get_chain(self, symbol: str, expiration: Optional[str] = None) -> Mapping[str, Any]:
        normalized_symbol = self._normalize_symbol(symbol)
        params = {"symbol": normalized_symbol, "greeks": "true"}
        if expiration:
            params["expiration"] = str(expiration)
        return self._get_json("markets/options/chains", params)

    def _get_json(self, path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        try:
            response = self._session.request(
                "GET",
                f"{self.base_url}/{path.lstrip('/')}",
                params=dict(params),
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            status_code = getattr(response, "status_code", None)
            if status_code is not None and int(status_code) >= 400:
                raise requests.HTTPError("tradier_http_status_error")
        except Exception as exc:
            raise OptionsProviderUnavailable(
                "tradier",
                code="options_provider_http_error",
                message="Tradier options market-data request failed.",
            ) from exc

        try:
            payload = response.json()
        except Exception as exc:
            raise OptionsProviderUnavailable(
                "tradier",
                code="options_provider_payload_unmappable",
                message="Options provider payload could not be mapped safely.",
            ) from exc
        if not isinstance(payload, Mapping):
            raise OptionsProviderUnavailable(
                "tradier",
                code="options_provider_payload_unmappable",
                message="Options provider payload could not be mapped safely.",
            )
        return payload

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_token}",
        }

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized_symbol = _normalize_us_symbol(symbol)
        if not _is_us_equity_symbol(normalized_symbol):
            raise OptionsProviderUnsupportedSymbol(normalized_symbol)
        return normalized_symbol


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


class _DisabledLiveOptionsProviderStub:
    """Fail-closed placeholder for future live Options Lab providers."""

    source_type = "live_stub"

    def __init__(self, provider_name: str, config: Optional[OptionsLiveProviderConfig] = None) -> None:
        self.provider_name = provider_name
        self.config = config or OptionsLiveProviderConfig()
        self.capabilities = OptionsProviderCapabilityMetadata(
            provider_name=provider_name,
            source_type=self.source_type,
            fixture_only=False,
            live_enabled=False,
            delayed=False,
            tradeable_data=False,
            notes=("live_stub", "disabled_by_default", "no_external_calls"),
        )

    def get_expirations(self, symbol: str) -> List[Dict[str, Any]]:
        self._raise_unavailable()

    def get_underlying_quote(self, symbol: str) -> Dict[str, Any]:
        self._raise_unavailable()

    def get_chain(self, symbol: str, expiration: Optional[str] = None) -> Dict[str, Any]:
        self._raise_unavailable()

    def _raise_unavailable(self) -> None:
        self._validate_live_provider_config()
        raise OptionsProviderUnavailable(
            self.provider_name,
            code="options_provider_not_enabled",
            message="Options live provider adapter has no network implementation.",
        )

    def _validate_live_provider_config(self) -> None:
        if not self.config.live_providers_enabled:
            raise OptionsProviderUnavailable(
                self.provider_name,
                code="options_provider_disabled",
                message="Options live provider adapter is disabled.",
            )
        if not self.config.is_provider_enabled(self.provider_name):
            raise OptionsProviderUnavailable(
                self.provider_name,
                code="options_provider_not_enabled",
                message="Options live provider adapter is not enabled.",
            )
        credential_state = self.config.credential_state(self.provider_name)
        if credential_state == "malformed":
            raise OptionsProviderUnavailable(
                self.provider_name,
                code="options_provider_credentials_malformed",
                message="Options live provider credential contract is malformed.",
            )
        if credential_state == "partial":
            raise OptionsProviderUnavailable(
                self.provider_name,
                code="options_provider_credentials_partial",
                message="Options live provider credential contract is partial.",
            )
        if not self.config.has_credentials(self.provider_name):
            raise OptionsProviderUnavailable(
                self.provider_name,
                code="options_provider_credentials_missing",
                message="Options live provider credentials are not configured.",
            )


class TradierOptionsProviderStub(_DisabledLiveOptionsProviderStub):
    """Disabled Tradier Options Lab adapter stub."""

    def __init__(
        self,
        config: Optional[OptionsLiveProviderConfig] = None,
        dry_run_response: Optional[Mapping[str, Any]] = None,
        transport: Optional[TradierOptionsTransport] = None,
    ) -> None:
        super().__init__("tradier", config=config)
        self.transport = transport
        self.dry_run_response = copy.deepcopy(dict(dry_run_response or DEFAULT_TRADIER_OPTIONS_DRY_RUN_RESPONSE))
        if self.config.is_dry_run_enabled(self.provider_name):
            self.capabilities = OptionsProviderCapabilityMetadata(
                provider_name=self.provider_name,
                source_type="delayed_dry_run",
                fixture_only=False,
                live_enabled=False,
                delayed=True,
                tradeable_data=False,
                notes=("tradier_dry_run", "no_external_calls", "not_tradeable"),
            )
        elif self.transport is not None:
            runtime_live_enabled = (
                isinstance(self.transport, TradierOptionsHttpTransport)
                and self.config.live_providers_enabled
                and self.config.is_provider_enabled(self.provider_name)
                and self.config.has_credentials(self.provider_name)
            )
            self.capabilities = OptionsProviderCapabilityMetadata(
                provider_name=self.provider_name,
                source_type=TRADIER_OPTIONS_ADAPTER_SOURCE,
                fixture_only=False,
                live_enabled=runtime_live_enabled,
                delayed=False,
                tradeable_data=False,
                notes=TRADIER_OPTIONS_HTTP_NOTES if runtime_live_enabled else TRADIER_OPTIONS_ADAPTER_NOTES,
            )

    def get_expirations(self, symbol: str) -> List[Dict[str, Any]]:
        if self._should_use_transport():
            return copy.deepcopy(self._transport_expirations(symbol))
        return copy.deepcopy(self._normalized_snapshot(symbol).get("expirations") or [])

    def get_underlying_quote(self, symbol: str) -> Dict[str, Any]:
        if self._should_use_transport():
            return copy.deepcopy(self._transport_underlying_quote(symbol))
        return copy.deepcopy(self._normalized_snapshot(symbol).get("underlying") or {})

    def get_chain(self, symbol: str, expiration: Optional[str] = None) -> Dict[str, Any]:
        snapshot = (
            self._transport_snapshot(symbol, expiration=expiration)
            if self._should_use_transport()
            else self._normalized_snapshot(symbol)
        )
        if expiration:
            snapshot["contracts"] = [
                contract for contract in snapshot.get("contracts") or [] if str(contract.get("expiration") or "") == expiration
            ]
        return snapshot

    def _should_use_transport(self) -> bool:
        return self.transport is not None and not self.config.is_dry_run_enabled(self.provider_name)

    def _normalized_snapshot(self, symbol: str) -> Dict[str, Any]:
        self._validate_live_provider_config()
        if not self.config.is_dry_run_enabled(self.provider_name):
            raise OptionsProviderUnavailable(
                self.provider_name,
                code="options_provider_dry_run_not_enabled",
                message="Options live provider dry run is not enabled.",
            )
        try:
            return self._map_tradier_dry_run_response(symbol, self.dry_run_response)
        except (KeyError, TypeError, ValueError) as exc:
            raise OptionsProviderUnavailable(
                self.provider_name,
                code="options_provider_payload_unmappable",
                message="Options provider payload could not be mapped safely.",
            ) from exc

    def _transport_underlying_quote(self, symbol: str) -> Dict[str, Any]:
        self._validate_live_provider_config()
        normalized_symbol = _normalize_us_symbol(symbol)
        if not _is_us_equity_symbol(normalized_symbol):
            raise OptionsProviderUnsupportedSymbol(normalized_symbol)
        try:
            return self._map_tradier_transport_quote(
                normalized_symbol,
                self._require_transport().get_quote(normalized_symbol),
            )
        except OptionsProviderError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise OptionsProviderUnavailable(
                self.provider_name,
                code="options_provider_payload_unmappable",
                message="Options provider payload could not be mapped safely.",
            ) from exc

    def _transport_expirations(self, symbol: str) -> List[Dict[str, Any]]:
        self._validate_live_provider_config()
        normalized_symbol = _normalize_us_symbol(symbol)
        if not _is_us_equity_symbol(normalized_symbol):
            raise OptionsProviderUnsupportedSymbol(normalized_symbol)
        try:
            return self._map_tradier_transport_expirations(
                normalized_symbol,
                self._require_transport().get_expirations(normalized_symbol),
                TRADIER_OPTIONS_DRY_RUN_AS_OF,
            )
        except OptionsProviderError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise OptionsProviderUnavailable(
                self.provider_name,
                code="options_provider_payload_unmappable",
                message="Options provider payload could not be mapped safely.",
            ) from exc

    def _transport_snapshot(self, symbol: str, expiration: Optional[str] = None) -> Dict[str, Any]:
        self._validate_live_provider_config()
        normalized_symbol = _normalize_us_symbol(symbol)
        if not _is_us_equity_symbol(normalized_symbol):
            raise OptionsProviderUnsupportedSymbol(normalized_symbol)
        try:
            transport = self._require_transport()
            quote_payload = transport.get_quote(normalized_symbol)
            expirations_payload = transport.get_expirations(normalized_symbol)
            chain_payload = transport.get_chain(normalized_symbol, expiration)
            return self._map_tradier_transport_response(
                normalized_symbol,
                quote_payload=quote_payload,
                expirations_payload=expirations_payload,
                chain_payload=chain_payload,
            )
        except OptionsProviderError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise OptionsProviderUnavailable(
                self.provider_name,
                code="options_provider_payload_unmappable",
                message="Options provider payload could not be mapped safely.",
            ) from exc

    def _require_transport(self) -> TradierOptionsTransport:
        if self.transport is None:
            raise OptionsProviderUnavailable(
                self.provider_name,
                code="options_provider_dry_run_not_enabled",
                message="Options live provider dry run is not enabled.",
            )
        return self.transport

    def _map_tradier_transport_response(
        self,
        symbol: str,
        *,
        quote_payload: Mapping[str, Any],
        expirations_payload: Mapping[str, Any],
        chain_payload: Mapping[str, Any],
    ) -> Dict[str, Any]:
        underlying = self._map_tradier_transport_quote(symbol, quote_payload)
        chain_as_of = str(underlying.get("asOf") or TRADIER_OPTIONS_DRY_RUN_AS_OF)
        expirations_by_date: Dict[str, Dict[str, Any]] = {
            str(item["date"]): item
            for item in self._map_tradier_transport_expirations(symbol, expirations_payload, chain_as_of)
            if item.get("date")
        }
        option_rows = _tradier_option_rows(chain_payload)
        if not option_rows:
            raise ValueError("missing option rows")

        contracts: List[Dict[str, Any]] = []
        for item in option_rows:
            expiration = str(item.get("expiration_date") or item.get("expiration") or "").strip()
            if expiration:
                expirations_by_date.setdefault(
                    expiration,
                    self._transport_expiration_row(expiration, chain_as_of),
                )
            greeks_payload = _mapping_or_empty(item.get("greeks"))
            greeks = {
                greek: _float_or_none(greeks_payload.get(greek))
                for greek in ("delta", "gamma", "theta", "vega", "rho")
                if greeks_payload.get(greek) is not None
            }
            contracts.append(
                {
                    "contractSymbol": str(item.get("symbol") or item.get("contractSymbol") or "").strip(),
                    "side": _tradier_option_side(item),
                    "expiration": expiration,
                    "strike": _float_or_none(item.get("strike")),
                    "bid": _float_or_none(item.get("bid")),
                    "ask": _float_or_none(item.get("ask")),
                    "last": _float_or_none(item.get("last")),
                    "volume": _int_or_none(item.get("volume")),
                    "openInterest": _int_or_none(
                        item.get("open_interest") if "open_interest" in item else item.get("openInterest")
                    ),
                    "impliedVolatility": _float_or_none(
                        _first_present(
                            item,
                            ("implied_volatility", "impliedVolatility"),
                            fallback=greeks_payload.get("mid_iv", greeks_payload.get("smv_vol")),
                        )
                    ),
                    "greeks": greeks,
                    "multiplier": _int_or_none(item.get("multiplier")) or 100,
                    "source": TRADIER_OPTIONS_ADAPTER_SOURCE,
                    "freshness": TRADIER_OPTIONS_ADAPTER_FRESHNESS,
                    "providerQuality": TRADIER_OPTIONS_ADAPTER_QUALITY,
                    "dataQuality": self._transport_data_quality(),
                    "warnings": ["tradier_adapter_contract_not_tradeable", "freshness_unknown"],
                }
            )

        return {
            "symbol": symbol,
            "market": "us",
            "currency": "USD",
            "underlying": underlying,
            "chainAsOf": chain_as_of,
            "source": TRADIER_OPTIONS_ADAPTER_SOURCE,
            "providerName": self.provider_name,
            "providerQuality": TRADIER_OPTIONS_ADAPTER_QUALITY,
            "dataQuality": self._transport_data_quality(),
            "providerCapabilities": self.capabilities.to_dict(),
            "expirations": [expirations_by_date[key] for key in sorted(expirations_by_date)],
            "contracts": contracts,
        }

    def _map_tradier_transport_quote(self, symbol: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        quote_payload = _tradier_quote_row(payload)
        payload_symbol = _normalize_us_symbol(str(quote_payload.get("symbol") or symbol))
        if payload_symbol != symbol:
            raise OptionsProviderUnsupportedSymbol(symbol)
        return {
            "price": _float_or_none(_first_present(quote_payload, ("last", "price", "last_price", "close"))),
            "changePct": _float_or_none(
                _first_present(
                    quote_payload,
                    ("change_percentage", "changePct", "change_percent", "changePercentage"),
                )
            ),
            "asOf": str(
                _first_present(
                    quote_payload,
                    ("trade_date", "timestamp", "as_of", "asOf"),
                    fallback=TRADIER_OPTIONS_DRY_RUN_AS_OF,
                )
            ),
            "source": TRADIER_OPTIONS_ADAPTER_SOURCE,
            "freshness": TRADIER_OPTIONS_ADAPTER_FRESHNESS,
            "providerQuality": TRADIER_OPTIONS_ADAPTER_QUALITY,
        }

    def _map_tradier_transport_expirations(
        self,
        symbol: str,
        payload: Mapping[str, Any],
        as_of: str,
    ) -> List[Dict[str, Any]]:
        del symbol
        return [self._transport_expiration_row(expiration, as_of) for expiration in _tradier_expiration_dates(payload)]

    @staticmethod
    def _transport_expiration_row(expiration: str, as_of: str) -> Dict[str, Any]:
        return {
            "date": expiration,
            "dte": _dte(expiration, as_of),
            "type": "monthly",
            "chainAvailable": True,
            "asOf": as_of,
            "source": TRADIER_OPTIONS_ADAPTER_SOURCE,
            "freshness": TRADIER_OPTIONS_ADAPTER_FRESHNESS,
            "warnings": ["tradier_adapter_contract_not_tradeable", "freshness_unknown"],
        }

    @staticmethod
    def _transport_data_quality() -> Dict[str, Any]:
        return {
            "tier": "insufficient",
            "tradeable": False,
            "hints": list(TRADIER_OPTIONS_ADAPTER_NOTES),
        }

    def _map_tradier_dry_run_response(self, symbol: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        normalized_symbol = _normalize_us_symbol(symbol)
        if not _is_us_equity_symbol(normalized_symbol):
            raise OptionsProviderUnsupportedSymbol(normalized_symbol)

        underlying_payload = dict(payload.get("underlying") or {})
        payload_symbol = _normalize_us_symbol(str(underlying_payload.get("symbol") or normalized_symbol))
        if payload_symbol != normalized_symbol:
            raise OptionsProviderUnsupportedSymbol(normalized_symbol)

        raw_options = (payload.get("options") or {}).get("option") if isinstance(payload.get("options"), Mapping) else []
        if isinstance(raw_options, Mapping):
            option_rows = [dict(raw_options)]
        else:
            option_rows = [dict(item) for item in list(raw_options or [])]
        if not option_rows:
            raise ValueError("missing option rows")

        chain_as_of = str(underlying_payload.get("trade_date") or payload.get("as_of") or TRADIER_OPTIONS_DRY_RUN_AS_OF)
        expirations_by_date: Dict[str, Dict[str, Any]] = {}
        contracts: List[Dict[str, Any]] = []
        for item in option_rows:
            expiration = str(item.get("expiration_date") or item.get("expiration") or "")
            contract_symbol = str(item.get("symbol") or "")
            side = str(item.get("option_type") or item.get("type") or "").lower()
            strike = _float_or_none(item.get("strike"))
            if not expiration or not contract_symbol or side not in {"call", "put"} or strike is None:
                raise ValueError("missing required contract fields")

            expirations_by_date.setdefault(
                expiration,
                {
                    "date": expiration,
                    "dte": _dte(expiration, chain_as_of),
                    "type": "monthly",
                    "chainAvailable": True,
                    "asOf": chain_as_of,
                    "source": TRADIER_OPTIONS_DRY_RUN_SOURCE,
                    "freshness": TRADIER_OPTIONS_DRY_RUN_FRESHNESS,
                    "warnings": ["tradier_dry_run_data_not_tradeable", "delayed_or_stale_data_possible"],
                },
            )
            greeks_payload = dict(item.get("greeks") or {})
            contracts.append(
                {
                    "contractSymbol": contract_symbol,
                    "side": side,
                    "expiration": expiration,
                    "strike": strike,
                    "bid": _float_or_none(item.get("bid")),
                    "ask": _float_or_none(item.get("ask")),
                    "last": _float_or_none(item.get("last")),
                    "volume": _int_or_none(item.get("volume")),
                    "openInterest": _int_or_none(item.get("open_interest") if "open_interest" in item else item.get("openInterest")),
                    "impliedVolatility": _float_or_none(
                        item.get("implied_volatility")
                        if "implied_volatility" in item
                        else greeks_payload.get("mid_iv", greeks_payload.get("smv_vol"))
                    ),
                    "greeks": {
                        greek: _float_or_none(greeks_payload.get(greek))
                        for greek in ("delta", "gamma", "theta", "vega", "rho")
                        if greeks_payload.get(greek) is not None
                    },
                    "multiplier": _int_or_none(item.get("multiplier")) or 100,
                    "source": TRADIER_OPTIONS_DRY_RUN_SOURCE,
                    "freshness": TRADIER_OPTIONS_DRY_RUN_FRESHNESS,
                    "providerQuality": "tradier_dry_run_not_tradeable",
                    "dataQuality": {
                        "tier": "delayed_usable",
                        "tradeable": False,
                        "hints": ["tradier_dry_run", "no_external_calls", "not_tradeable"],
                    },
                    "warnings": ["tradier_dry_run_data_not_tradeable", "delayed_or_stale_data_possible"],
                }
            )

        return {
            "symbol": normalized_symbol,
            "market": "us",
            "currency": "USD",
            "underlying": {
                "price": _float_or_none(underlying_payload.get("last") or underlying_payload.get("price")),
                "changePct": _float_or_none(
                    underlying_payload.get("change_percentage")
                    if "change_percentage" in underlying_payload
                    else underlying_payload.get("changePct")
                ),
                "asOf": chain_as_of,
                "source": TRADIER_OPTIONS_DRY_RUN_SOURCE,
                "freshness": TRADIER_OPTIONS_DRY_RUN_FRESHNESS,
                "providerQuality": "tradier_dry_run_not_tradeable",
            },
            "chainAsOf": chain_as_of,
            "source": TRADIER_OPTIONS_DRY_RUN_SOURCE,
            "providerName": self.provider_name,
            "providerQuality": "tradier_dry_run_not_tradeable",
            "dataQuality": {
                "tier": "delayed_usable",
                "tradeable": False,
                "hints": ["tradier_dry_run", "no_external_calls", "not_tradeable"],
            },
            "providerCapabilities": self.capabilities.to_dict(),
            "expirations": [expirations_by_date[key] for key in sorted(expirations_by_date)],
            "contracts": contracts,
        }


class IbkrOptionsProviderStub(_DisabledLiveOptionsProviderStub):
    """Disabled IBKR Options Lab adapter stub."""

    def __init__(self, config: Optional[OptionsLiveProviderConfig] = None) -> None:
        super().__init__("ibkr", config=config)


class PolygonOptionsProviderStub(_DisabledLiveOptionsProviderStub):
    """Disabled Polygon Options Lab adapter stub."""

    def __init__(self, config: Optional[OptionsLiveProviderConfig] = None) -> None:
        super().__init__("polygon", config=config)


def build_options_provider_live_readiness_preflight(
    provider_name: str,
    config: Optional[OptionsLiveProviderConfig] = None,
    dry_run_response: Optional[Mapping[str, Any]] = None,
    staging_probe_artifact: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Classify live-provider readiness without enabling live calls.

    This is a read-only preflight surface for tests and future operator
    evidence. It does not load credentials, call provider APIs, place orders, or
    mutate portfolio state.
    """

    normalized = (provider_name or "").strip().lower()
    if normalized not in LIVE_OPTIONS_PROVIDER_NAMES:
        raise OptionsProviderUnavailable(normalized or "unknown")

    live_config = config or OptionsLiveProviderConfig()
    provider = _create_live_options_provider_stub(
        normalized,
        config=live_config,
        dry_run_response=dry_run_response,
    )
    credential_contract = _provider_credential_contract(normalized, live_config)
    staging_probe_artifact_status = _provider_staging_probe_artifact_status(
        normalized,
        staging_probe_artifact,
    )
    preflight: Dict[str, Any] = {
        "providerName": normalized,
        "readinessState": "disabled",
        "reasonCode": "options_provider_disabled",
        "message": "Options live provider adapter is disabled.",
        "liveProvidersEnabled": live_config.live_providers_enabled,
        "providerEnabled": live_config.is_provider_enabled(normalized),
        "credentialsPresent": credential_contract["state"] == "present",
        "credentialContract": credential_contract,
        "dryRunEnabled": live_config.is_dry_run_enabled(normalized),
        "payloadMappable": None,
        "liveHttpCallsEnabled": False,
        "liveProbe": _provider_live_probe_contract(
            normalized,
            live_config,
            credential_contract,
            staging_probe_artifact_status,
        ),
        "stagingCredentialProbeArtifact": staging_probe_artifact_status,
        "brokerOrderPathEnabled": False,
        "portfolioMutationPathEnabled": False,
        "tradeableData": False,
        "providerCapabilities": provider.capabilities.to_dict(),
        "providerSlaReadiness": _empty_provider_sla_readiness(),
        "checks": {
            "disabledByDefault": not live_config.live_providers_enabled,
            "noLiveHttpCalls": True,
            "noBrokerOrders": True,
            "noPortfolioMutations": True,
            "tradeableDataBlocked": True,
            "rawPayloadReturned": False,
            "stagingProbeArtifactAccepted": staging_probe_artifact_status["status"] == "accepted",
        },
    }

    if not live_config.live_providers_enabled:
        return preflight
    if not live_config.is_provider_enabled(normalized):
        preflight.update(
            {
                "readinessState": "disabled",
                "reasonCode": "options_provider_not_enabled",
                "message": "Options live provider adapter is not enabled.",
            }
        )
        return preflight
    if credential_contract["state"] == "malformed":
        preflight.update(
            {
                "readinessState": "malformed_credentials",
                "reasonCode": "options_provider_credentials_malformed",
                "message": "Options live provider credential contract is malformed.",
            }
        )
        return preflight
    if credential_contract["state"] == "partial":
        preflight.update(
            {
                "readinessState": "partial_credentials",
                "reasonCode": "options_provider_credentials_partial",
                "message": "Options live provider credential contract is partial.",
            }
        )
        return preflight
    if credential_contract["state"] != "present":
        preflight.update(
            {
                "readinessState": "missing_credentials",
                "reasonCode": "options_provider_credentials_missing",
                "message": "Options live provider credentials are not configured.",
            }
        )
        return preflight
    if not live_config.is_dry_run_enabled(normalized):
        preflight.update(
            {
                "readinessState": "live_credentials_present_live_calls_disabled",
                "reasonCode": "options_provider_live_calls_disabled",
                "message": "Options live provider credentials are present, but live calls remain disabled.",
            }
        )
        return preflight

    try:
        snapshot = provider.get_chain("TEM")
    except OptionsProviderUnavailable as exc:
        preflight.update(
            {
                "readinessState": (
                    "malformed_provider_payload"
                    if exc.code == "options_provider_payload_unmappable"
                    else "sanitized_provider_error"
                ),
                "reasonCode": exc.code,
                "message": sanitize_message(str(exc)),
                "payloadMappable": False,
            }
        )
        return preflight
    except OptionsProviderError as exc:
        preflight.update(
            {
                "readinessState": "sanitized_provider_error",
                "reasonCode": exc.code,
                "message": sanitize_message(str(exc)),
                "payloadMappable": False,
            }
        )
        return preflight

    data_quality = dict(snapshot.get("dataQuality") or {})
    preflight.update(
        {
            "readinessState": "dry_run_enabled",
            "reasonCode": "options_provider_dry_run_enabled",
            "message": "Options provider dry-run mapping is available; live calls remain disabled.",
            "payloadMappable": True,
            "dryRunFreshness": snapshot.get("source") and snapshot.get("underlying", {}).get("freshness"),
            "dryRunDataQuality": {
                "tier": data_quality.get("tier"),
                "tradeable": bool(data_quality.get("tradeable")) is True,
            },
        }
    )
    return preflight


def _provider_credential_contract(provider_name: str, config: OptionsLiveProviderConfig) -> Dict[str, Any]:
    """Return sanitized credential readiness counts only."""
    state = config.credential_state(provider_name)
    required_count = 1 if provider_name in LIVE_OPTIONS_PROVIDER_NAMES else 0
    return {
        "state": state,
        "reasonCode": _credential_contract_reason_code(state),
        "requiredCredentialCount": required_count,
        "configuredCredentialCount": 1 if state == "present" else 0,
        "invalidCredentialCount": 1 if state == "malformed" else 0,
        "partialCredentialCount": 1 if state == "partial" else 0,
    }


def _provider_live_probe_contract(
    provider_name: str,
    config: OptionsLiveProviderConfig,
    credential_contract: Dict[str, Any],
    staging_probe_artifact_status: Dict[str, Any],
) -> Dict[str, Any]:
    """Return an operator-controlled live-probe contract without executing it."""
    explicit_opt_in = provider_name in config.live_probe_provider_keys
    artifact_accepted = staging_probe_artifact_status.get("status") == "accepted"
    enabled = bool(
        explicit_opt_in
        and config.live_providers_enabled
        and config.is_provider_enabled(provider_name)
        and credential_contract.get("state") == "present"
        and artifact_accepted
    )
    reason_code = "options_provider_live_probe_disabled_by_default"
    if explicit_opt_in and not config.live_providers_enabled:
        reason_code = "options_provider_disabled"
    elif explicit_opt_in and not config.is_provider_enabled(provider_name):
        reason_code = "options_provider_not_enabled"
    elif explicit_opt_in and credential_contract.get("state") != "present":
        reason_code = str(credential_contract.get("reasonCode") or "options_provider_credentials_missing")
    elif explicit_opt_in and not artifact_accepted:
        reason_code = str(
            (staging_probe_artifact_status.get("reasonCodes") or ["options_provider_staging_probe_artifact_missing"])[0]
        )
    elif enabled:
        reason_code = "options_provider_live_probe_operator_opt_in_ready"
    return {
        "enabled": enabled,
        "explicitOptIn": explicit_opt_in,
        "reasonCode": reason_code,
        "timeoutSeconds": _safe_probe_timeout_seconds(str(config.live_probe_timeout_seconds)),
        "httpMethod": "HEAD_OR_GET",
        "networkCallExecuted": False,
        "noDefaultLiveHttpCalls": True,
        "requiresCredentialPresenceOnly": True,
        "rawCredentialValuesIncluded": False,
        "providerPayloadValuesIncluded": False,
        "responseBodiesIncluded": False,
    }


def _provider_staging_probe_artifact_status(
    provider_name: str,
    artifact: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Validate operator-supplied staging probe evidence without retaining raw payloads."""
    base = {
        "providerId": provider_name,
        "status": "missing",
        "timestamp": None,
        "timeoutSeconds": None,
        "reasonCodes": ["options_provider_staging_probe_artifact_missing"],
    }
    if artifact is None:
        return base
    if not isinstance(artifact, Mapping):
        return {
            **base,
            "status": "malformed",
            "reasonCodes": ["options_provider_staging_probe_artifact_malformed"],
        }

    if set(artifact.keys()) - ALLOWED_STAGING_PROBE_ARTIFACT_KEYS:
        return {
            **base,
            "status": "rejected",
            "reasonCodes": ["options_provider_staging_probe_artifact_unexpected_field"],
        }
    if _artifact_contains_sensitive_value(artifact):
        return {
            **base,
            "status": "rejected",
            "reasonCodes": ["options_provider_staging_probe_artifact_sensitive_value"],
        }

    artifact_provider = str(artifact.get("providerId") or "").strip().lower()
    if artifact_provider != provider_name or artifact_provider not in LIVE_OPTIONS_PROVIDER_NAMES:
        return {
            **base,
            "status": "rejected",
            "reasonCodes": ["options_provider_staging_probe_artifact_provider_mismatch"],
        }

    status_text = str(artifact.get("status") or "").strip().lower()
    if status_text in _ACCEPTED_STAGING_PROBE_STATUSES:
        normalized_status = "accepted"
    elif status_text in _NON_ACCEPTED_STAGING_PROBE_STATUSES:
        normalized_status = status_text
    else:
        return {
            **base,
            "status": "malformed",
            "reasonCodes": ["options_provider_staging_probe_artifact_status_invalid"],
        }

    timestamp = _safe_artifact_timestamp(artifact.get("timestamp"))
    if timestamp is None:
        return {
            **base,
            "status": "malformed",
            "reasonCodes": ["options_provider_staging_probe_artifact_timestamp_invalid"],
        }
    timeout_seconds = _artifact_timeout_seconds(artifact.get("timeoutSeconds"))
    if timeout_seconds is None:
        return {
            **base,
            "status": "malformed",
            "reasonCodes": ["options_provider_staging_probe_artifact_timeout_invalid"],
        }
    reason_codes = _artifact_reason_codes(artifact.get("reasonCodes"))
    if reason_codes is None:
        return {
            **base,
            "status": "malformed",
            "reasonCodes": ["options_provider_staging_probe_artifact_reason_codes_invalid"],
        }

    return {
        "providerId": artifact_provider,
        "status": normalized_status,
        "timestamp": timestamp,
        "timeoutSeconds": timeout_seconds,
        "reasonCodes": reason_codes,
    }


def _artifact_contains_sensitive_value(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_artifact_contains_sensitive_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_artifact_contains_sensitive_value(item) for item in value)
    if not isinstance(value, str):
        return False
    text = value.strip().lower()
    if not text:
        return False
    if any(marker in text for marker in _SENSITIVE_ARTIFACT_MARKERS):
        return True
    return "://" in text or "=" in text or "{" in text or "}" in text


def _safe_artifact_timestamp(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text or len(text) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.isoformat()


def _artifact_timeout_seconds(value: Any) -> Optional[float]:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if parsed < 0.25 or parsed > 5.0:
        return None
    return parsed


def _artifact_reason_codes(value: Any) -> Optional[list[str]]:
    if not isinstance(value, (list, tuple)):
        return None
    normalized: list[str] = []
    for item in value:
        code = str(item or "").strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,80}", code):
            return None
        if _artifact_contains_sensitive_value(code):
            return None
        normalized.append(code)
    if not normalized or len(normalized) > 10:
        return None
    return normalized


def _credential_contract_reason_code(state: str) -> str:
    if state == "present":
        return "options_provider_credentials_present"
    if state == "malformed":
        return "options_provider_credentials_malformed"
    if state == "partial":
        return "options_provider_credentials_partial"
    return "options_provider_credentials_missing"


def _create_live_options_provider_stub(
    provider_name: str,
    config: OptionsLiveProviderConfig,
    dry_run_response: Optional[Mapping[str, Any]] = None,
) -> _DisabledLiveOptionsProviderStub:
    if provider_name == "tradier":
        return TradierOptionsProviderStub(config=config, dry_run_response=dry_run_response)
    if provider_name == "ibkr":
        return IbkrOptionsProviderStub(config=config)
    if provider_name == "polygon":
        return PolygonOptionsProviderStub(config=config)
    raise OptionsProviderUnavailable(provider_name)


def _tradier_api_token_from_env() -> Optional[str]:
    for env_name in ("TRADIER_API_TOKEN", "TRADIER_SANDBOX_API_TOKEN"):
        value = str(os.environ.get(env_name) or "").strip()
        if _credential_value_state(value) == "present":
            return value
    return None


def _create_tradier_runtime_transport(
    config: OptionsLiveProviderConfig,
) -> Optional[TradierOptionsHttpTransport]:
    if not config.live_providers_enabled:
        return None
    if not config.is_provider_enabled("tradier"):
        return None
    if config.is_dry_run_enabled("tradier"):
        return None
    if not config.has_credentials("tradier"):
        return None
    api_token = _tradier_api_token_from_env()
    if api_token is None:
        return None
    return TradierOptionsHttpTransport(api_token=api_token)


def _empty_provider_sla_readiness() -> Dict[str, Any]:
    """Normalized SLA fields for read-only preflight responses with no probes."""
    return {
        "latencyBucketMs": None,
        "latencyState": "unknown",
        "errorRate": None,
        "errorState": "unknown",
        "freshnessSeconds": None,
        "freshnessState": "unknown",
        "recentErrors": [],
        "readOnly": True,
        "noExternalCalls": True,
        "liveEnforcement": False,
    }


def _normalize_us_symbol(symbol: str) -> str:
    return re.sub(r"\s+", "", str(symbol or "")).upper()


def _is_us_equity_symbol(symbol: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{1,5}", symbol))


def _float_or_none(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def _int_or_none(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _mapping_or_empty(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_present(payload: Mapping[str, Any], keys: tuple[str, ...], fallback: Any = None) -> Any:
    for key in keys:
        if key in payload and payload.get(key) not in (None, ""):
            return payload.get(key)
    return fallback


def _tradier_quote_row(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if isinstance(payload.get("quotes"), Mapping):
        quote = payload["quotes"].get("quote")
        if isinstance(quote, list):
            return _mapping_or_empty(quote[0] if quote else {})
        return _mapping_or_empty(quote)
    if isinstance(payload.get("quote"), Mapping):
        return _mapping_or_empty(payload.get("quote"))
    if isinstance(payload.get("underlying"), Mapping):
        return _mapping_or_empty(payload.get("underlying"))
    return _mapping_or_empty(payload)


def _tradier_option_rows(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    raw_options = (payload.get("options") or {}).get("option") if isinstance(payload.get("options"), Mapping) else []
    if isinstance(raw_options, Mapping):
        return [dict(raw_options)]
    return [dict(item) for item in list(raw_options or []) if isinstance(item, Mapping)]


def _tradier_expiration_dates(payload: Mapping[str, Any]) -> List[str]:
    raw_expirations = payload.get("expirations")
    if isinstance(raw_expirations, Mapping):
        raw_dates = raw_expirations.get("date", raw_expirations.get("expiration"))
    else:
        raw_dates = raw_expirations
    if isinstance(raw_dates, str):
        values = [raw_dates]
    elif isinstance(raw_dates, Mapping):
        values = [raw_dates.get("date")]
    else:
        values = [
            item.get("date") if isinstance(item, Mapping) else item
            for item in list(raw_dates or [])
        ]
    return sorted({str(item).strip() for item in values if str(item or "").strip()})


def _tradier_option_side(item: Mapping[str, Any]) -> str:
    text = str(item.get("option_type") or item.get("side") or item.get("type") or "").strip().lower()
    if text in {"call", "c"}:
        return "call"
    if text in {"put", "p"}:
        return "put"
    match = re.search(r"\d{6}([CP])\d{8}$", str(item.get("symbol") or item.get("contractSymbol") or ""))
    if match:
        return "call" if match.group(1) == "C" else "put"
    return text


def _dte(expiration: str, as_of: str) -> int:
    expiration_date = date.fromisoformat(expiration)
    as_of_date = datetime.fromisoformat(as_of.replace("Z", "+00:00")).date()
    return max((expiration_date - as_of_date).days, 0)


def create_options_market_data_provider(
    provider_name: str = DEFAULT_OPTIONS_PROVIDER_NAME,
    fixture_path: Optional[Path] = None,
    live_provider_config: Optional[OptionsLiveProviderConfig] = None,
) -> OptionsMarketDataProvider:
    """Create a fixture provider or disabled live provider stub."""

    normalized = (provider_name or DEFAULT_OPTIONS_PROVIDER_NAME).strip().lower()
    if normalized in {"synthetic_fixture", "synthetic", "fixture"}:
        return SyntheticFixtureOptionsProvider(fixture_path=fixture_path)
    if normalized in {"delayed_fixture", "real_shaped_delayed_fixture"}:
        return DelayedFixtureOptionsProvider(fixture_path=fixture_path)
    if normalized in {"malformed_fixture", "missing_greeks_fixture"}:
        return MalformedGreeksFixtureOptionsProvider(fixture_path=fixture_path)
    if normalized == "tradier":
        live_config = live_provider_config or OptionsLiveProviderConfig()
        return TradierOptionsProviderStub(
            config=live_config,
            transport=_create_tradier_runtime_transport(live_config),
        )
    if normalized == "ibkr":
        return IbkrOptionsProviderStub(config=live_provider_config)
    if normalized == "polygon":
        return PolygonOptionsProviderStub(config=live_provider_config)
    raise OptionsProviderUnavailable(normalized)
