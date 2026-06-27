# -*- coding: utf-8 -*-
"""Operator-only provider activation verifier.

The verifier is a deterministic read model. It checks local dependency,
configuration, and cache-file signals only; it never imports provider SDKs,
calls external networks, reads secret values into the response, or mutates
runtime/cache state.
"""

from __future__ import annotations

import importlib.util
import os
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROVIDER_ACTIVATION_VERIFIER_CONTRACT_VERSION = "provider_activation_verifier_v1"
SUPPORTED_STATUSES = (
    "available",
    "missing",
    "not_configured",
    "insufficient_permissions",
    "stale",
    "sample_only",
    "unavailable",
)
_TRUTHY = {"1", "true", "yes", "on"}
_DEFAULT_SCANNER_UNIVERSE_PATH = "./data/scanner_cn_universe_cache.csv"
_HISTORICAL_RUNTIME_ENV = "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED"
_YFINANCE_US_CACHE_ENV = "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED"
_SCANNER_UNIVERSE_ENV = "SCANNER_LOCAL_UNIVERSE_PATH"
_FMP_ENV_NAMES = ("FMP_API_KEYS", "FMP_API_KEY")

SpecFinder = Callable[[str], object | None]
FileMtimeReader = Callable[[Path], float | None]


class ProviderActivationVerifierService:
    """Build operator-actionable provider activation readiness."""

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        spec_finder: SpecFinder = importlib.util.find_spec,
        today: date | None = None,
        file_mtime: FileMtimeReader | None = None,
        local_checks: Mapping[str, Any] | None = None,
    ) -> None:
        self.env = dict(env or os.environ)
        self.spec_finder = spec_finder
        self.today = today or date.today()
        self.file_mtime = file_mtime or self._default_file_mtime
        self.local_checks = dict(local_checks or {})

    def verify(self) -> dict[str, Any]:
        capabilities = [
            self._akshare(),
            self._baostock(),
            self._fmp(),
            self._yfinance(),
            self._historical_ohlcv(),
            self._earnings_fundamentals(),
            self._scanner_universe(),
        ]
        counts = Counter(str(item["status"]) for item in capabilities)
        blocked_surfaces = sorted(
            {
                surface
                for item in capabilities
                if item["status"] != "available"
                for surface in item["blockedProductSurfaces"]
            }
        )
        return {
            "contractVersion": PROVIDER_ACTIVATION_VERIFIER_CONTRACT_VERSION,
            "generatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "operatorOnly": True,
            "readOnly": True,
            "externalProviderCalls": False,
            "networkCallsEnabled": False,
            "mutationEnabled": False,
            "supportedStatuses": list(SUPPORTED_STATUSES),
            "summary": {
                "totalCapabilities": len(capabilities),
                "availableCount": counts["available"],
                "missingCount": counts["missing"],
                "notConfiguredCount": counts["not_configured"],
                "insufficientPermissionsCount": counts["insufficient_permissions"],
                "staleCount": counts["stale"],
                "sampleOnlyCount": counts["sample_only"],
                "unavailableCount": counts["unavailable"],
                "blockedProductSurfaces": blocked_surfaces,
                "uatDiagnosis": (
                    "operator_actionable_provider_activation"
                    if any(item["status"] != "available" for item in capabilities)
                    else "provider_activation_checks_available"
                ),
            },
            "capabilities": capabilities,
            "metadata": {
                "source": "local_dependency_configuration_and_cache_signals",
                "readOnly": True,
                "operatorOnly": True,
                "externalProviderCalls": False,
                "networkCallsEnabled": False,
                "mutationEnabled": False,
                "sensitiveValuesIncluded": False,
                "rawProviderPayloadsIncluded": False,
                "exceptionDetailsIncluded": False,
                "providerRuntimeChanged": False,
                "consumerVisible": False,
            },
        }

    def _akshare(self) -> dict[str, Any]:
        state = self._module_state("akshare")
        status = "available" if state == "installed" else ("missing" if state == "missing" else "unavailable")
        return self._capability(
            capability_id="akshare.cn_hk_market_data",
            provider="AkShare",
            data_class="CN/HK quotes and OHLCV",
            status=status,
            impact="CN/HK Market Overview, Scanner, Stock research, and Portfolio price lineage lack AkShare activation evidence.",
            action=(
                "Install and pin the AkShare dependency, then run the existing bounded AkShare capability probe in operator mode."
                if status == "missing"
                else "Keep AkShare observation-only labels visible and validate bounded CN/HK probes before enabling dependent workflows."
            ),
            freshness_state="delayed_public_proxy" if status == "available" else "unavailable",
            validation="python -m pytest -q tests/test_akshare_capability_probe.py",
            surfaces=("Market Overview", "Scanner", "Stock Fundamentals", "Portfolio"),
        )

    def _baostock(self) -> dict[str, Any]:
        state = self._module_state("baostock")
        status = "available" if state == "installed" else ("missing" if state == "missing" else "unavailable")
        return self._capability(
            capability_id="baostock.cn_ohlcv",
            provider="BaoStock",
            data_class="CN daily OHLCV",
            status=status,
            impact="CN daily history remains unavailable for Scanner, Backtest, and Stock research activation checks.",
            action=(
                "Install the BaoStock dependency and run the bounded source contract tests before relying on CN OHLCV cache evidence."
                if status == "missing"
                else "Run a bounded BaoStock session check and keep the source labelled third-party/free and observation-only."
            ),
            freshness_state="t_plus_1_or_delayed" if status == "available" else "unavailable",
            validation="python -m pytest -q tests/test_baostock_source_contract.py",
            surfaces=("Scanner", "Backtest", "Stock Fundamentals"),
        )

    def _fmp(self) -> dict[str, Any]:
        configured = self._has_any_config(_FMP_ENV_NAMES)
        status = "insufficient_permissions" if configured else "not_configured"
        return self._capability(
            capability_id="fmp.fundamentals_earnings",
            provider="Financial Modeling Prep",
            data_class="US fundamentals, statements, earnings, and daily reference data",
            status=status,
            impact="Stock Fundamentals, Earnings, News/Catalyst enrichment, and deep single-stock research cannot prove real-data readiness.",
            action=(
                "Run a bounded FMP permission probe for one known symbol and store only sanitized entitlement evidence before promoting this capability."
                if configured
                else "Configure FMP access outside the application response path, then run a bounded permission probe without exposing key values."
            ),
            freshness_state="permission_unverified" if configured else "not_configured",
            validation="python scripts/provider_activation_verifier.py --format json",
            surfaces=("Stock Fundamentals", "Earnings", "News/Catalyst"),
        )

    def _yfinance(self) -> dict[str, Any]:
        state = self._module_state("yfinance")
        status = "available" if state == "installed" else ("missing" if state == "missing" else "unavailable")
        return self._capability(
            capability_id="yfinance.market_data",
            provider="Yahoo Finance / yfinance",
            data_class="US/HK quote, OHLCV, and fallback fundamentals",
            status=status,
            impact="US/HK quote and historical fallback checks cannot prove baseline market-data availability.",
            action=(
                "Install the yfinance dependency and run the deterministic symbol-boundary tests before using it as a bounded fallback."
                if status == "missing"
                else "Keep Yahoo/yfinance as delayed unofficial fallback and validate local cache freshness before dependent workflows."
            ),
            freshness_state="delayed_unofficial_public" if status == "available" else "unavailable",
            validation="python -m pytest -q tests/test_yfinance_symbol_boundary.py",
            surfaces=("Market Overview", "Scanner", "Backtest", "Stock Fundamentals", "Portfolio"),
        )

    def _historical_ohlcv(self) -> dict[str, Any]:
        runtime_enabled = self._env_enabled(_HISTORICAL_RUNTIME_ENV)
        us_enabled = self._env_enabled(_YFINANCE_US_CACHE_ENV)
        akshare_state = self._module_state("akshare")
        yfinance_state = self._module_state("yfinance")
        latest = self._date_from_local_check("historical_ohlcv_latest_date")
        stale = latest is not None and (self.today - latest).days > 5

        if not runtime_enabled:
            status = "not_configured"
            freshness_state = "runtime_disabled"
        elif akshare_state == "missing" and (not us_enabled or yfinance_state == "missing"):
            status = "missing"
            freshness_state = "dependency_missing"
        elif stale:
            status = "stale"
            freshness_state = f"latest_bar:{latest.isoformat()}"
        else:
            status = "available"
            freshness_state = "local_runtime_ready"

        return self._capability(
            capability_id="historical_ohlcv.runtime",
            provider="Local historical OHLCV runtime",
            data_class="Historical OHLCV cache and runtime activation",
            status=status,
            impact="Backtest, Scanner history gates, technical indicators, Market Regime, and single-stock history remain blocked or degraded.",
            action=(
                "Enable the historical OHLCV runtime and run the dry-run cache preflight for representative US/CN symbols."
                if status == "not_configured"
                else "Refresh or seed representative local OHLCV cache in the existing dry-run/explicit-seed workflow, then rerun the cache preflight."
                if status == "stale"
                else "Install the missing local history dependency and rerun the dry-run cache preflight."
                if status == "missing"
                else "Rerun the dry-run cache preflight and keep backtest inputs tied to local cache lineage."
            ),
            freshness_state=freshness_state,
            validation="GET /api/v1/admin/historical-ohlcv/cache-preflight",
            surfaces=("Scanner", "Backtest", "Stock Fundamentals", "Market Overview"),
        )

    def _earnings_fundamentals(self) -> dict[str, Any]:
        if bool(self.local_checks.get("earnings_sample_only")):
            status = "sample_only"
            freshness_state = "sample_only"
            action = "Replace sample-only earnings/fundamentals fixtures with provider-backed sanitized evidence before enabling the dependent surfaces."
        elif self._has_any_config(_FMP_ENV_NAMES):
            status = "insufficient_permissions"
            freshness_state = "permission_unverified"
            action = "Run a bounded fundamentals and earnings permission probe; keep output sanitized and store only readiness evidence."
        else:
            status = "not_configured"
            freshness_state = "not_configured"
            action = "Configure a real fundamentals/earnings provider and run a bounded readiness probe; do not use sample rows as live evidence."
        return self._capability(
            capability_id="earnings_fundamentals.readiness",
            provider="Fundamentals and earnings evidence",
            data_class="Fundamentals, statements, earnings calendar, and catalyst facts",
            status=status,
            impact="Stock Fundamentals, Earnings, News/Catalyst, and single-stock research remain evidence-limited.",
            action=action,
            freshness_state=freshness_state,
            validation="python -m pytest -q tests/services/test_earnings_calendar_readiness_contract.py tests/test_fundamental_adapter.py",
            surfaces=("Stock Fundamentals", "Earnings", "News/Catalyst"),
        )

    def _scanner_universe(self) -> dict[str, Any]:
        path = Path(self.env.get(_SCANNER_UNIVERSE_ENV) or _DEFAULT_SCANNER_UNIVERSE_PATH)
        mtime = self.file_mtime(path)
        if mtime is None:
            status = "missing"
            freshness_state = "missing_universe_cache"
            action = "Create or refresh the scanner local universe cache through the existing scanner readiness workflow before expecting candidates."
        else:
            modified = self._date_from_mtime(mtime)
            if modified is None or (self.today - modified).days > 3:
                status = "stale"
                freshness_state = f"universe_modified:{modified.isoformat() if modified else 'unknown'}"
                action = "Refresh the scanner local universe cache and rerun scanner readiness checks before using candidate generation."
            else:
                status = "available"
                freshness_state = f"universe_modified:{modified.isoformat()}"
                action = "Run scanner status/readiness checks and confirm candidate generation remains tied to the refreshed universe."
        return self._capability(
            capability_id="scanner.universe",
            provider="Scanner universe",
            data_class="Scanner local universe and candidate prerequisites",
            status=status,
            impact="Scanner pool can be empty because the universe prerequisite is missing or stale.",
            action=action,
            freshness_state=freshness_state,
            validation="GET /api/v1/scanner/status",
            surfaces=("Scanner", "Market Overview", "Backtest"),
        )

    @staticmethod
    def _capability(
        *,
        capability_id: str,
        provider: str,
        data_class: str,
        status: str,
        impact: str,
        action: str,
        freshness_state: str,
        validation: str,
        surfaces: tuple[str, ...],
    ) -> dict[str, Any]:
        return {
            "capabilityId": capability_id,
            "provider": provider,
            "dataClass": data_class,
            "status": status if status in SUPPORTED_STATUSES else "unavailable",
            "userFacingImpact": impact,
            "adminNextAction": action,
            "freshnessCacheStatus": {
                "state": freshness_state,
                "known": freshness_state not in {"unknown", "unavailable"},
            },
            "minimumValidationCheck": validation,
            "blockedProductSurfaces": list(surfaces),
        }

    def _module_state(self, module_name: str) -> str:
        try:
            return "installed" if self.spec_finder(module_name) is not None else "missing"
        except Exception:
            return "unavailable"

    def _has_any_config(self, names: tuple[str, ...]) -> bool:
        return any(bool(str(self.env.get(name) or "").strip()) for name in names)

    def _env_enabled(self, name: str) -> bool:
        return str(self.env.get(name) or "").strip().lower() in _TRUTHY

    def _date_from_local_check(self, key: str) -> date | None:
        value = self.local_checks.get(key)
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
        return None

    @staticmethod
    def _default_file_mtime(path: Path) -> float | None:
        try:
            return path.stat().st_mtime
        except OSError:
            return None

    @staticmethod
    def _date_from_mtime(value: float) -> date | None:
        try:
            if 1 <= value <= 4_000_000:
                return date.fromordinal(int(value))
            return datetime.fromtimestamp(value).date()
        except (OSError, OverflowError, ValueError):
            return None


__all__ = [
    "PROVIDER_ACTIVATION_VERIFIER_CONTRACT_VERSION",
    "ProviderActivationVerifierService",
]
