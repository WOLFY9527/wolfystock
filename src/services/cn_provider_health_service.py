# -*- coding: utf-8 -*-
"""Internal CN provider health snapshot service for pytdx and AKShare."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import threading
import time
from typing import Any, Callable, Mapping

from src.services.provider_capability_matrix import list_provider_capability_support_contracts
from src.services.source_confidence_contract import ProviderCapabilitySupportContract


ProbeCallable = Callable[[float], Mapping[str, Any]]

_SUPPORTED_PROVIDERS = ("pytdx", "akshare")
_DEFAULT_MISSING_PROVIDER_REASONS = {
    "pytdx": "pytdx_not_installed",
    "akshare": "akshare_not_installed",
}
_DEFAULT_UNAVAILABLE_REASONS = {
    "pytdx": "pytdx_provider_unavailable",
    "akshare": "akshare_provider_unavailable",
}
_DEFAULT_PROBE_FAILURE_REASONS = {
    "pytdx": "pytdx_probe_failed",
    "akshare": "akshare_probe_failed",
}
_DEFAULT_TIMEOUT_REASONS = {
    "pytdx": "pytdx_probe_timeout",
    "akshare": "akshare_probe_timeout",
}
_DEFAULT_SNAPSHOT_CACHE_TTL_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class CNProviderHealthSnapshotEntry:
    provider_name: str
    provider_id: str
    source_type: str
    source_tier: str
    trust_level: str
    freshness_expectation: str
    observation_only: bool
    score_contribution_allowed: bool
    dependency_installed: bool
    provider_available: bool
    health_status: str
    supported_capabilities: tuple[str, ...]
    unsupported_capabilities: tuple[str, ...]
    contract_capabilities: tuple[str, ...]
    degradation_reason: str | None
    missing_provider_reason: str | None
    attempted_at: str | None
    timeout_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerName": self.provider_name,
            "providerId": self.provider_id,
            "sourceType": self.source_type,
            "sourceTier": self.source_tier,
            "trustLevel": self.trust_level,
            "freshnessExpectation": self.freshness_expectation,
            "observationOnly": self.observation_only,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "dependencyInstalled": self.dependency_installed,
            "providerAvailable": self.provider_available,
            "healthStatus": self.health_status,
            "supportedCapabilities": list(self.supported_capabilities),
            "unsupportedCapabilities": list(self.unsupported_capabilities),
            "contractCapabilities": list(self.contract_capabilities),
            "degradationReason": self.degradation_reason,
            "missingProviderReason": self.missing_provider_reason,
            "attemptedAt": self.attempted_at,
            "timeoutSeconds": self.timeout_seconds,
        }


@dataclass(frozen=True, slots=True)
class _CNProviderHealthCacheEntry:
    snapshot: tuple[CNProviderHealthSnapshotEntry, ...]
    captured_at_monotonic: float


class CNProviderHealthService:
    """Aggregate CN capability contracts with optional provider health probes."""

    _snapshot_cache: dict[tuple[Any, ...], _CNProviderHealthCacheEntry] = {}
    _snapshot_cache_lock = threading.Lock()
    _refreshing_cache_keys: set[tuple[Any, ...]] = set()

    def __init__(
        self,
        *,
        pytdx_probe: ProbeCallable | None = None,
        akshare_probe: ProbeCallable | None = None,
    ) -> None:
        self._probe_by_provider: dict[str, ProbeCallable] = {
            "pytdx": pytdx_probe or self._default_pytdx_probe,
            "akshare": akshare_probe or self._default_akshare_probe,
        }

    @classmethod
    def clear_snapshot_cache(cls) -> None:
        with cls._snapshot_cache_lock:
            cls._snapshot_cache.clear()
            cls._refreshing_cache_keys.clear()

    def get_snapshot(
        self,
        timeout_seconds: float = 5.0,
        *,
        force_refresh: bool = False,
        cache_ttl_seconds: float = _DEFAULT_SNAPSHOT_CACHE_TTL_SECONDS,
    ) -> tuple[CNProviderHealthSnapshotEntry, ...]:
        cache_key = self._snapshot_cache_key(timeout_seconds)
        now_monotonic = time.monotonic()

        with self._snapshot_cache_lock:
            cached_entry = self._snapshot_cache.get(cache_key)
            if not force_refresh and _cache_entry_is_fresh(cached_entry, now_monotonic, cache_ttl_seconds):
                return cached_entry.snapshot
            if (
                not force_refresh
                and cached_entry is not None
                and cache_key in self._refreshing_cache_keys
            ):
                return cached_entry.snapshot
            self._refreshing_cache_keys.add(cache_key)

        try:
            snapshot = self._build_snapshot(timeout_seconds)
        finally:
            with self._snapshot_cache_lock:
                self._refreshing_cache_keys.discard(cache_key)

        with self._snapshot_cache_lock:
            self._snapshot_cache[cache_key] = _CNProviderHealthCacheEntry(
                snapshot=snapshot,
                captured_at_monotonic=time.monotonic(),
            )
        return snapshot

    def _build_snapshot(self, timeout_seconds: float) -> tuple[CNProviderHealthSnapshotEntry, ...]:
        return tuple(
            self._build_snapshot_entry(provider_id, timeout_seconds)
            for provider_id in _SUPPORTED_PROVIDERS
        )

    def _build_snapshot_entry(
        self,
        provider_id: str,
        timeout_seconds: float,
    ) -> CNProviderHealthSnapshotEntry:
        contracts = list_provider_capability_support_contracts(provider_id)
        if not contracts:
            raise ValueError(f"Missing CN provider capability contracts for {provider_id}")

        static_metadata = _contract_metadata(contracts)
        contract_capabilities = tuple(sorted({contract.capability for contract in contracts}))
        probe = self._safe_probe(provider_id, timeout_seconds)
        supported_capabilities = _normalize_supported_capabilities(
            probe.get("supportedCapabilities"),
            contract_capabilities,
        )
        unsupported_capabilities = _normalize_unsupported_capabilities(
            probe.get("unsupportedCapabilities"),
            supported_capabilities,
        )

        return CNProviderHealthSnapshotEntry(
            provider_name=static_metadata.provider_name,
            provider_id=static_metadata.provider_id,
            source_type=static_metadata.source_type,
            source_tier=static_metadata.source_tier,
            trust_level=static_metadata.trust_level,
            freshness_expectation=static_metadata.freshness_expectation,
            observation_only=static_metadata.observation_only,
            score_contribution_allowed=static_metadata.score_contribution_allowed,
            dependency_installed=bool(probe.get("dependencyInstalled")),
            provider_available=bool(probe.get("providerAvailable")),
            health_status=_derive_health_status(probe),
            supported_capabilities=supported_capabilities,
            unsupported_capabilities=unsupported_capabilities,
            contract_capabilities=contract_capabilities,
            degradation_reason=_optional_text(probe.get("degradationReason")),
            missing_provider_reason=_optional_text(probe.get("missingProviderReason")),
            attempted_at=_optional_text(probe.get("attemptedAt")),
            timeout_seconds=_float(probe.get("timeoutSeconds"), timeout_seconds),
        )

    def _safe_probe(self, provider_id: str, timeout_seconds: float) -> dict[str, Any]:
        attempted_at = datetime.now(timezone.utc).isoformat()
        probe_callable = self._probe_by_provider[provider_id]
        try:
            result = dict(probe_callable(timeout_seconds) or {})
        except ImportError:
            return {
                "providerId": provider_id,
                "dependencyInstalled": False,
                "providerAvailable": False,
                "degradationReason": _DEFAULT_MISSING_PROVIDER_REASONS[provider_id],
                "missingProviderReason": _DEFAULT_MISSING_PROVIDER_REASONS[provider_id],
                "attemptedAt": None,
                "timeoutSeconds": timeout_seconds,
                "healthStatus": "missing_dependency",
            }
        except TimeoutError:
            return {
                "providerId": provider_id,
                "dependencyInstalled": True,
                "providerAvailable": False,
                "degradationReason": _DEFAULT_TIMEOUT_REASONS[provider_id],
                "missingProviderReason": _DEFAULT_TIMEOUT_REASONS[provider_id],
                "attemptedAt": attempted_at,
                "timeoutSeconds": timeout_seconds,
                "healthStatus": "timeout",
            }
        except Exception:
            return {
                "providerId": provider_id,
                "dependencyInstalled": True,
                "providerAvailable": False,
                "degradationReason": _DEFAULT_PROBE_FAILURE_REASONS[provider_id],
                "missingProviderReason": _DEFAULT_PROBE_FAILURE_REASONS[provider_id],
                "attemptedAt": attempted_at,
                "timeoutSeconds": timeout_seconds,
                "healthStatus": "probe_failure",
            }

        result.setdefault("attemptedAt", attempted_at if result.get("dependencyInstalled") else None)
        result.setdefault("timeoutSeconds", timeout_seconds)
        return result

    def _snapshot_cache_key(self, timeout_seconds: float) -> tuple[Any, ...]:
        rounded_timeout = round(float(timeout_seconds), 3)
        return (
            rounded_timeout,
            tuple(
                (provider_id, id(_probe_identity(self._probe_by_provider[provider_id])))
                for provider_id in _SUPPORTED_PROVIDERS
            ),
        )

    @staticmethod
    def _default_pytdx_probe(timeout_seconds: float) -> Mapping[str, Any]:
        from data_provider.pytdx_fetcher import PytdxFetcher

        return PytdxFetcher().probe_capabilities(timeout_seconds=timeout_seconds)

    @staticmethod
    def _default_akshare_probe(timeout_seconds: float) -> Mapping[str, Any]:
        from data_provider.akshare_fetcher import AkshareFetcher

        return AkshareFetcher().probe_capabilities(timeout_seconds=timeout_seconds)


def get_cn_provider_health_snapshot(timeout_seconds: float = 5.0) -> tuple[CNProviderHealthSnapshotEntry, ...]:
    """Return the current internal CN provider health snapshot."""

    return CNProviderHealthService().get_snapshot(timeout_seconds=timeout_seconds)


def _contract_metadata(
    contracts: tuple[ProviderCapabilitySupportContract, ...],
) -> ProviderCapabilitySupportContract:
    return contracts[0]


def _derive_health_status(probe: Mapping[str, Any]) -> str:
    explicit_status = _optional_text(probe.get("healthStatus"))
    if explicit_status:
        return explicit_status
    if bool(probe.get("providerAvailable")):
        return "healthy"
    if not bool(probe.get("dependencyInstalled")):
        return "missing_dependency"

    health_hint = _optional_text(probe.get("serverHealth")) or _optional_text(probe.get("interfaceHealth"))
    degradation_reason = _optional_text(probe.get("degradationReason")) or _optional_text(
        probe.get("missingProviderReason")
    )

    if health_hint == "timeout" or (degradation_reason and degradation_reason.endswith("_timeout")):
        return "timeout"
    if health_hint in {"reachable", "ok"} and bool(probe.get("providerAvailable")):
        return "healthy"
    if health_hint in {"unreachable", "no_hosts_configured", "unavailable"}:
        return "unavailable_provider"
    if health_hint in {"error", "empty_response", "missing_probe_interface"}:
        return "probe_failure"
    if degradation_reason in _DEFAULT_PROBE_FAILURE_REASONS.values():
        return "probe_failure"
    if degradation_reason in _DEFAULT_TIMEOUT_REASONS.values():
        return "timeout"
    return "unavailable_provider"


def _normalize_supported_capabilities(
    supported_capabilities: Any,
    contract_capabilities: tuple[str, ...],
) -> tuple[str, ...]:
    supported = {_normalize_capability(item) for item in _iter_capabilities(supported_capabilities)}
    contract_capability_set = set(contract_capabilities)
    return tuple(sorted(item for item in supported if item in contract_capability_set))


def _normalize_unsupported_capabilities(
    unsupported_capabilities: Any,
    supported_capabilities: tuple[str, ...],
) -> tuple[str, ...]:
    supported_capability_set = set(supported_capabilities)
    unsupported = {_normalize_capability(item) for item in _iter_capabilities(unsupported_capabilities)}
    return tuple(sorted(item for item in unsupported if item and item not in supported_capability_set))


def _iter_capabilities(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item) for item in value if str(item or "").strip())
    return ()


def _normalize_capability(value: Any) -> str:
    return str(value or "").strip().lower()


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _cache_entry_is_fresh(
    entry: _CNProviderHealthCacheEntry | None,
    now_monotonic: float,
    ttl_seconds: float,
) -> bool:
    if entry is None:
        return False
    ttl = max(float(ttl_seconds), 0.0)
    return (now_monotonic - entry.captured_at_monotonic) <= ttl


def _probe_identity(probe: ProbeCallable) -> Any:
    return getattr(probe, "__func__", probe)


__all__ = [
    "CNProviderHealthService",
    "CNProviderHealthSnapshotEntry",
    "get_cn_provider_health_snapshot",
]
