# -*- coding: utf-8 -*-
"""Static inventory guards for provider credential/config categories."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_CONFIG_PATH = REPO_ROOT / "src/config.py"
RUNTIME_SETTINGS_PATH = REPO_ROOT / "src/runtime/settings.py"
CONFIG_REGISTRY_PATH = REPO_ROOT / "src/core/config_registry.py"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"
READINESS_SCRIPT_PATH = REPO_ROOT / "scripts/production_config_readiness.py"
RELEASE_SECRET_SCAN_PATH = REPO_ROOT / "scripts/release_secret_scan.sh"
SYSTEM_CONFIG_SERVICE_PATH = REPO_ROOT / "src/services/system_config_service.py"
PROVIDER_BASE_PATH = REPO_ROOT / "data_provider/base.py"
PROVIDER_CREDENTIALS_PATH = REPO_ROOT / "data_provider/provider_credentials.py"
TUSHARE_FETCHER_PATH = REPO_ROOT / "data_provider/tushare_fetcher.py"
AKSHARE_FETCHER_PATH = REPO_ROOT / "data_provider/akshare_fetcher.py"
US_FUNDAMENTALS_PROVIDER_PATH = REPO_ROOT / "data_provider/us_fundamentals_provider.py"
ALPHAVANTAGE_PROVIDER_PATH = REPO_ROOT / "data_provider/alphavantage_provider.py"
MARKET_OVERVIEW_SERVICE_PATH = REPO_ROOT / "src/services/market_overview_service.py"
SYSTEM_CONFIG_PROVIDER_PROJECTION_PATH = REPO_ROOT / "src/services/system_config_provider_projection.py"
OFFICIAL_MACRO_SOURCE_REGISTRY_PATH = REPO_ROOT / "src/services/official_macro_source_registry.py"
OFFICIAL_MACRO_TRANSPORT_PATH = REPO_ROOT / "src/services/official_macro_transport.py"

SRC_CONFIG_TEXT = SRC_CONFIG_PATH.read_text(encoding="utf-8")
RUNTIME_SETTINGS_TEXT = RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8")
CONFIG_REGISTRY_TEXT = CONFIG_REGISTRY_PATH.read_text(encoding="utf-8")
ENV_EXAMPLE_TEXT = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
READINESS_SCRIPT_TEXT = READINESS_SCRIPT_PATH.read_text(encoding="utf-8")
RELEASE_SECRET_SCAN_TEXT = RELEASE_SECRET_SCAN_PATH.read_text(encoding="utf-8")
SYSTEM_CONFIG_SERVICE_TEXT = SYSTEM_CONFIG_SERVICE_PATH.read_text(encoding="utf-8")
PROVIDER_BASE_TEXT = PROVIDER_BASE_PATH.read_text(encoding="utf-8")
PROVIDER_CREDENTIALS_TEXT = PROVIDER_CREDENTIALS_PATH.read_text(encoding="utf-8")
TUSHARE_FETCHER_TEXT = TUSHARE_FETCHER_PATH.read_text(encoding="utf-8")
AKSHARE_FETCHER_TEXT = AKSHARE_FETCHER_PATH.read_text(encoding="utf-8")
US_FUNDAMENTALS_PROVIDER_TEXT = US_FUNDAMENTALS_PROVIDER_PATH.read_text(encoding="utf-8")
ALPHAVANTAGE_PROVIDER_TEXT = ALPHAVANTAGE_PROVIDER_PATH.read_text(encoding="utf-8")
MARKET_OVERVIEW_SERVICE_TEXT = MARKET_OVERVIEW_SERVICE_PATH.read_text(encoding="utf-8")
SYSTEM_CONFIG_PROVIDER_PROJECTION_TEXT = SYSTEM_CONFIG_PROVIDER_PROJECTION_PATH.read_text(encoding="utf-8")
OFFICIAL_MACRO_SOURCE_REGISTRY_TEXT = OFFICIAL_MACRO_SOURCE_REGISTRY_PATH.read_text(encoding="utf-8")
OFFICIAL_MACRO_TRANSPORT_TEXT = OFFICIAL_MACRO_TRANSPORT_PATH.read_text(encoding="utf-8")


def test_provider_credential_inventory_freezes_configured_and_wired_sources_without_reading_values() -> None:
    configured_and_wired = {
        "tushare": {
            "env_names": ("TUSHARE_TOKEN",),
            "config_markers": ("tushare_token=os.getenv('TUSHARE_TOKEN')",),
            "runtime_markers": ("config.tushare_token", "TushareFetcher"),
        },
        "tickflow": {
            "env_names": ("TICKFLOW_API_KEY",),
            "config_markers": ("tickflow_api_key=os.getenv('TICKFLOW_API_KEY')",),
            "runtime_markers": (
                'getattr(config, "tickflow_api_key", None)',
                "project_tickflow_entitlement_health(",
            ),
        },
        "fred": {
            "env_names": ("FRED_API_KEY",),
            "config_markers": ("fred_api_key=os.getenv('FRED_API_KEY') or None",),
            "runtime_markers": (
                'return _text(getattr(Config.get_instance(), "fred_api_key", None)) or None',
                'api_key=_resolve_fred_api_key(api_key)',
                'params["api_key"] = api_key',
            ),
        },
        "twelve_data": {
            "env_names": ("TWELVE_DATA_API_KEY", "TWELVE_DATA_API_KEYS"),
            "config_markers": (
                "twelve_data_keys_str = os.getenv('TWELVE_DATA_API_KEYS', '') or os.getenv('TWELVEDATA_API_KEYS', '')",
                "os.getenv('TWELVE_DATA_API_KEY', '').strip()",
                "os.getenv('TWELVEDATA_API_KEY', '').strip()",
                "twelve_data_api_keys=twelve_data_api_keys",
                "twelve_data_api_key=single_twelve_data or (twelve_data_api_keys[0] if twelve_data_api_keys else None)",
            ),
            "runtime_markers": (
                'if normalized in {"twelve_data", "twelvedata"}',
                "TwelveDataFetcher",
                '"twelve_data": ("TWELVE_DATA_API_KEYS", "TWELVE_DATA_API_KEY", "TWELVEDATA_API_KEYS", "TWELVEDATA_API_KEY")',
            ),
        },
        "alpaca": {
            "env_names": ("ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY", "ALPACA_DATA_FEED"),
            "config_markers": (
                "alpaca_api_key_id=os.getenv('ALPACA_API_KEY_ID') or None",
                "alpaca_api_secret_key=os.getenv('ALPACA_API_SECRET_KEY') or None",
                "alpaca_data_feed=(os.getenv('ALPACA_DATA_FEED', 'iex').strip().lower() or 'iex')",
            ),
            "runtime_markers": (
                'get_provider_credentials("alpaca")',
                "Alpaca credentials require both ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY",
            ),
        },
        "fmp": {
            "env_names": ("FMP_API_KEY", "FMP_API_KEYS"),
            "config_markers": (
                "fmp_keys_str = os.getenv('FMP_API_KEYS', '')",
                "single_fmp = os.getenv('FMP_API_KEY', '').strip()",
                "fmp_api_keys=fmp_api_keys",
            ),
            "runtime_markers": (
                '"fmp": ("FMP_API_KEYS", "FMP_API_KEY")',
                '_resolve_api_key(api_key, transport, "fmp_api_keys", "fmp_api_key")',
            ),
        },
        "finnhub": {
            "env_names": ("FINNHUB_API_KEY", "FINNHUB_API_KEYS"),
            "config_markers": (
                "finnhub_keys_str = os.getenv('FINNHUB_API_KEYS', '')",
                "single_finnhub = os.getenv('FINNHUB_API_KEY', '').strip()",
                "finnhub_api_keys=finnhub_api_keys",
            ),
            "runtime_markers": (
                '"finnhub": ("FINNHUB_API_KEYS", "FINNHUB_API_KEY")',
                '_resolve_api_key(api_key, transport, "finnhub_api_keys", "finnhub_api_key")',
            ),
        },
    }

    for contract in configured_and_wired.values():
        for env_name in contract["env_names"]:
            assert env_name in CONFIG_REGISTRY_TEXT
        for marker in contract["config_markers"]:
            assert marker in RUNTIME_SETTINGS_TEXT
        for marker in contract["runtime_markers"]:
            assert (
                marker in PROVIDER_BASE_TEXT
                or marker in PROVIDER_CREDENTIALS_TEXT
                or marker in TUSHARE_FETCHER_TEXT
                or marker in AKSHARE_FETCHER_TEXT
                or marker in SYSTEM_CONFIG_SERVICE_TEXT
                or marker in SYSTEM_CONFIG_PROVIDER_PROJECTION_TEXT
                or marker in US_FUNDAMENTALS_PROVIDER_TEXT
                or marker in MARKET_OVERVIEW_SERVICE_TEXT
                or marker in OFFICIAL_MACRO_TRANSPORT_TEXT
            )


def test_provider_env_docs_and_inventory_match_active_runtime_contracts() -> None:
    documented_runtime_contracts = {
        "fred": {
            "active_runtime_env_names": ("FRED_API_KEY",),
            "env_example_markers": ("# FRED API Key", "# FRED_API_KEY="),
            "readiness_markers": ('"FRED_API_KEY"',),
            "secret_scan_provider_tokens": ("FRED",),
        },
        "finnhub": {
            "active_runtime_env_names": ("FINNHUB_API_KEY", "FINNHUB_API_KEYS"),
            "env_example_markers": ("# FINNHUB_API_KEY=", "# FINNHUB_API_KEYS=key1,key2"),
            "readiness_markers": ('"FINNHUB_API_KEY"', '"FINNHUB_API_KEYS"'),
            "secret_scan_provider_tokens": ("FINNHUB",),
        },
        "fmp": {
            "active_runtime_env_names": ("FMP_API_KEY", "FMP_API_KEYS"),
            "env_example_markers": ("# FMP_API_KEY=", "# FMP_API_KEYS=key1,key2"),
            "readiness_markers": ('"FMP_API_KEY"', '"FMP_API_KEYS"'),
            "secret_scan_provider_tokens": ("FMP",),
        },
    }

    for contract in documented_runtime_contracts.values():
        for env_name in contract["active_runtime_env_names"]:
            assert env_name in CONFIG_REGISTRY_TEXT
        for marker in contract["env_example_markers"]:
            assert marker in ENV_EXAMPLE_TEXT
        for marker in contract["readiness_markers"]:
            assert marker in READINESS_SCRIPT_TEXT
        for provider_token in contract["secret_scan_provider_tokens"]:
            assert provider_token in RELEASE_SECRET_SCAN_TEXT


def test_alpha_vantage_runtime_contract_stays_singular_while_settings_aliases_remain_diagnostics_only() -> None:
    for env_name in ("ALPHA_VANTAGE_API_KEY", "ALPHA_VANTAGE_API_KEYS"):
        assert env_name in CONFIG_REGISTRY_TEXT or env_name in SYSTEM_CONFIG_SERVICE_TEXT

    assert 'API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")' in ALPHAVANTAGE_PROVIDER_TEXT
    assert "alpha_vantage_api_key" not in SRC_CONFIG_TEXT
    assert "alpha_vantage_api_keys" not in SRC_CONFIG_TEXT
    assert "# ALPHA_VANTAGE_API_KEY=" in ENV_EXAMPLE_TEXT
    assert "ALPHA_VANTAGE_API_KEYS=key1,key2" not in ENV_EXAMPLE_TEXT
    assert '"ALPHA_VANTAGE_API_KEY"' in READINESS_SCRIPT_TEXT
    assert '"ALPHA_VANTAGE_API_KEYS"' not in READINESS_SCRIPT_TEXT
    assert 'alpha_vantage": ("ALPHA_VANTAGE_API_KEYS", "ALPHA_VANTAGE_API_KEY", "ALPHAVANTAGE_API_KEYS", "ALPHAVANTAGE_API_KEY")' in SYSTEM_CONFIG_SERVICE_TEXT
    assert "ALPHAVANTAGE_API_KEY" not in ENV_EXAMPLE_TEXT
    assert "ALPHAVANTAGE_API_KEYS" not in ENV_EXAMPLE_TEXT
    assert "ALPHAVANTAGE_API_KEY" not in READINESS_SCRIPT_TEXT
    assert "ALPHAVANTAGE_API_KEYS" not in READINESS_SCRIPT_TEXT
    assert "ALPHA" in RELEASE_SECRET_SCAN_TEXT


def test_proxy_and_public_sources_stay_no_key_or_presence_only_by_contract() -> None:
    proxy_no_key_sources = {
        "binance": {
            "runtime_markers": ('"binance": "exchange_public"', '"binance": resolve_source_label("binance")'),
            "forbidden_secret_envs": ("BINANCE_API_KEY", "BINANCE_TOKEN", "BINANCE_SECRET"),
        },
        "sina": {
            "runtime_markers": ('"sina": "public_api"', "SINA_REALTIME_ENDPOINT"),
            "forbidden_secret_envs": ("SINA_API_KEY", "SINA_TOKEN", "SINA_SECRET"),
        },
        "akshare": {
            "runtime_markers": ("AkshareFetcher", "akshare"),
            "forbidden_secret_envs": ("AKSHARE_API_KEY", "AKSHARE_TOKEN", "AKSHARE_SECRET"),
        },
        "efinance": {
            "runtime_markers": ("EfinanceFetcher", "efinance"),
            "forbidden_secret_envs": ("EFINANCE_API_KEY", "EFINANCE_TOKEN", "EFINANCE_SECRET"),
        },
        "yfinance": {
            "runtime_markers": ('"yfinance": "unofficial_public_api"', "YfinanceFetcher"),
            "forbidden_secret_envs": ("YFINANCE_API_KEY", "YFINANCE_TOKEN", "YFINANCE_SECRET"),
        },
        "fred": {
            "runtime_markers": ('"fred": "official_public"', 'source_id=f"fred:{normalized_series}"'),
            "forbidden_secret_envs": ("FRED_TOKEN", "FRED_SECRET"),
        },
        "treasury": {
            "runtime_markers": ('"treasury": "official_public"', 'source_id="treasury:daily_treasury_yield_curve"'),
            "forbidden_secret_envs": ("TREASURY_API_KEY", "TREASURY_TOKEN", "TREASURY_SECRET"),
        },
        "ny_fed": {
            "runtime_markers": ('display_name="New York Fed SOFR"',),
            "forbidden_secret_envs": ("NY_FED_API_KEY", "NY_FED_TOKEN", "NY_FED_SECRET"),
        },
    }

    for contract in proxy_no_key_sources.values():
        for marker in contract["runtime_markers"]:
            assert (
                marker in MARKET_OVERVIEW_SERVICE_TEXT
                or marker in OFFICIAL_MACRO_TRANSPORT_TEXT
                or marker in OFFICIAL_MACRO_SOURCE_REGISTRY_TEXT
                or marker in PROVIDER_BASE_TEXT
                or marker in AKSHARE_FETCHER_TEXT
            )
        for env_name in contract["forbidden_secret_envs"]:
            assert env_name not in CONFIG_REGISTRY_TEXT
            assert env_name not in SRC_CONFIG_TEXT


def test_shared_provider_credential_helper_stays_narrow_and_does_not_expand_secret_inventory() -> None:
    assert 'if normalized in {"twelve_data", "twelvedata"}' in PROVIDER_CREDENTIALS_TEXT
    assert 'if normalized == "alpaca"' in PROVIDER_CREDENTIALS_TEXT
    assert 'Unsupported provider credential lookup' in PROVIDER_CREDENTIALS_TEXT
    for provider in ("fmp", "finnhub", "alpha_vantage", "tickflow", "tushare", "binance"):
        assert f'provider="{provider}"' not in PROVIDER_CREDENTIALS_TEXT
