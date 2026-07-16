"""Immutable runtime settings ownership."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field, fields
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Tuple, TypeVar
from urllib.parse import urlparse

from src.report_language import (
    is_supported_report_language_value,
    normalize_report_language,
)
from src.utils.dotenv_loader import load_dotenv_file, read_dotenv_values


RECOGNIZED_SETTING_NAMES: frozenset[str] = frozenset(
    """
ADMIN_AUTH_ENABLED
ADMIN_LOGS_AUTO_CLEANUP_ENABLED
ADMIN_LOGS_CLEANUP_BATCH_SIZE
ADMIN_LOGS_CRITICAL_THRESHOLD_COUNT
ADMIN_LOGS_MIN_RETENTION_DAYS
ADMIN_LOGS_RETENTION_DAYS
ADMIN_LOGS_STORAGE_HARD_LIMIT_MB
ADMIN_LOGS_STORAGE_SOFT_LIMIT_MB
ADMIN_LOGS_WARNING_THRESHOLD_COUNT
ADMIN_LOGS_WARNING_THRESHOLD_STORAGE_BYTES
ADMIN_LOG_AUTO_CLEANUP_ENABLED
ADMIN_LOG_CLEANUP_BATCH_SIZE
ADMIN_LOG_MIN_RETENTION_DAYS
ADMIN_LOG_RETENTION_DAYS
ADMIN_LOG_STORAGE_HARD_LIMIT_MB
ADMIN_LOG_STORAGE_SOFT_LIMIT_MB
ADMIN_REAUTH_MAX_AGE_MINUTES
ADMIN_SESSION_IDLE_TIMEOUT_MINUTES
ADMIN_SESSION_MAX_AGE_HOURS
ADMIN_UNLOCK_MAX_AGE_MINUTES
AGENT_ARCH
AGENT_DEEP_RESEARCH_BUDGET
AGENT_DEEP_RESEARCH_TIMEOUT
AGENT_EVENT_ALERT_RULES_JSON
AGENT_EVENT_MONITOR_ENABLED
AGENT_EVENT_MONITOR_INTERVAL_MINUTES
AGENT_LITELLM_MODEL
AGENT_MAX_STEPS
AGENT_MEMORY_ENABLED
AGENT_MODE
AGENT_NL_ROUTING
AGENT_ORCHESTRATOR_MODE
AGENT_ORCHESTRATOR_TIMEOUT_S
AGENT_RISK_OVERRIDE
AGENT_SKILLS
AGENT_SKILL_AUTOWEIGHT
AGENT_SKILL_DIR
AGENT_SKILL_ROUTING
AGENT_STRATEGY_AUTOWEIGHT
AGENT_STRATEGY_DIR
AGENT_STRATEGY_ROUTING
AIHUBMIX_KEY
AI_BACKUP_GATEWAY
AI_BACKUP_MODEL
AI_PRIMARY_GATEWAY
AI_PRIMARY_MODEL
AKSHARE_PRIORITY
ALPACA_API_KEY_ID
ALPACA_API_SECRET_KEY
ALPACA_DATA_FEED
ALPHA_VANTAGE_API_KEY
ANALYSIS_DELAY
ANTHROPIC_API_KEY
ANTHROPIC_API_KEYS
ANTHROPIC_MAX_TOKENS
ANTHROPIC_MODEL
ANTHROPIC_TEMPERATURE
API_PORT
APP_ENV
ASTRBOT_TOKEN
ASTRBOT_URL
AUTH_ACCOUNT_RATE_LIMIT_MAX_FAILURES
AUTH_ADMIN_RATE_LIMIT_MAX_FAILURES
AUTH_RATE_LIMIT_MAX_FAILURES
AUTH_RATE_LIMIT_WINDOW_SECONDS
BACKTEST_ENABLED
BACKTEST_ENGINE_VERSION
BACKTEST_EVAL_WINDOW_DAYS
BACKTEST_LITELLM_MODEL
BACKTEST_MIN_AGE_DAYS
BACKTEST_NEUTRAL_BAND_PCT
BAOSTOCK_PRIORITY
BIAS_THRESHOLD
BOCHA_API_KEYS
BOT_ADMIN_USERS
BOT_COMMAND_PREFIX
BOT_ENABLED
BOT_RATE_LIMIT_REQUESTS
BOT_RATE_LIMIT_WINDOW
BRANCH_NAME
BRAVE_API_KEYS
CIRCUIT_BREAKER_COOLDOWN
CN_HK_CONNECT_FLOW_API_KEY
CN_HK_CONNECT_FLOW_CACHE_PATH
CN_HK_CONNECT_FLOW_PROVIDER_ENABLED
CN_MONEY_MARKET_RATES_CACHE_PATH
COMMIT_SHA
CONFIG_VALIDATE_MODE
CORS_ALLOW_ALL
CORS_ORIGINS
CRYPTO_REALTIME_ENABLED
CSRF_TRUSTED_ORIGINS
CUSTOM_DATA_SOURCE_LIBRARY
CUSTOM_WEBHOOK_BEARER_TOKEN
CUSTOM_WEBHOOK_URLS
DATABASE_PATH
DEBUG
DEEPSEEK_API_KEY
DEEPSEEK_API_KEYS
DEV
DINGTALK_APP_KEY
DINGTALK_APP_SECRET
DINGTALK_STREAM_ENABLED
DISCORD_BOT_STATUS
DISCORD_BOT_TOKEN
DISCORD_CHANNEL_ID
DISCORD_MAIN_CHANNEL_ID
DISCORD_MAX_WORDS
DISCORD_WEBHOOK_URL
DSA_ENV
DSA_WEB_SMOKE_PASSWORD
DUCKDB_DATABASE_PATH
EFINANCE_CALL_TIMEOUT
EFINANCE_PRIORITY
EMAIL_PASSWORD
EMAIL_RECEIVERS
EMAIL_SENDER
EMAIL_SENDER_NAME
ENABLE_CHIP_DISTRIBUTION
ENABLE_EASTMONEY_PATCH
ENABLE_FUNDAMENTAL_PIPELINE
ENABLE_PHASE_F_CASH_LEDGER_COMPARISON
ENABLE_PHASE_F_CORPORATE_ACTIONS_COMPARISON
ENABLE_PHASE_F_TRADES_LIST_COMPARISON
ENABLE_REALTIME_QUOTE
ENABLE_REALTIME_TECHNICAL_INDICATORS
ENVIRONMENT
ENV_FILE
FEISHU_APP_ID
FEISHU_APP_SECRET
FEISHU_ENCRYPT_KEY
FEISHU_FOLDER_TOKEN
FEISHU_MAX_BYTES
FEISHU_STREAM_ENABLED
FEISHU_VERIFICATION_TOKEN
FEISHU_WEBHOOK_URL
FINNHUB_API_KEY
FINNHUB_API_KEYS
FMP_API_KEY
FMP_API_KEYS
FRED_API_KEY
FRED_MACRO_PROVIDER_ENABLED
FUNDAMENTAL_CACHE_MAX_ENTRIES
FUNDAMENTAL_CACHE_TTL_SECONDS
FUNDAMENTAL_FETCH_TIMEOUT_SECONDS
FUNDAMENTAL_RETRY_MAX
FUNDAMENTAL_STAGE_TIMEOUT_SECONDS
GEMINI_API_KEY
GEMINI_API_KEYS
GEMINI_MAX_RETRIES
GEMINI_MODEL
GEMINI_MODEL_FALLBACK
GEMINI_REQUEST_DELAY
GEMINI_RETRY_DELAY
GEMINI_TEMPERATURE
GIT_BRANCH
GIT_COMMIT
GIT_COMMIT_TIMESTAMP
GNEWS_API_KEY
GNEWS_API_KEYS
HOME_ANALYSIS_LOG_FULL_PROMPT
HOME_QUICK_ANALYSIS_ENABLED
HOME_QUICK_ANALYSIS_MAX_OUTPUT_TOKENS
HOME_QUICK_ANALYSIS_TEMPERATURE
HTTPS_PROXY
HTTP_PROXY
LITELLM_CONFIG
LITELLM_FALLBACK_MODELS
LITELLM_MODEL
LLM_CHANNELS
LLM_DEEPSEEK_API_KEY
LLM_DEEPSEEK_BASE_URL
LLM_DEEPSEEK_MODELS
LLM_GEMINI_API_KEYS
LLM_GEMINI_MODELS
LLM_TEMPERATURE
LOCAL_US_PARQUET_DIR
LOCAL_US_QUOTE_SNAPSHOT_CACHE_PATH
LOG_DIR
LOG_LEVEL
MARKDOWN_TO_IMAGE_CHANNELS
MARKDOWN_TO_IMAGE_MAX_CHARS
MARKET_CACHE_REMOTE_BACKEND
MARKET_CACHE_REMOTE_QUEUE_SIZE
MARKET_CACHE_REMOTE_TIMEOUT_SECONDS
MARKET_CACHE_REMOTE_URL
MARKET_REVIEW_ENABLED
MARKET_REVIEW_REGION
MAX_WORKERS
MD2IMG_ENGINE
MERGE_EMAIL_NOTIFICATION
MINIMAX_API_KEYS
MODE
NEWS_MAX_AGE_DAYS
NEWS_STRATEGY_PROFILE
NO_PROXY
OPENAI_API_KEY
OPENAI_API_KEYS
OPENAI_BASE_URL
OPENAI_MODEL
OPENAI_TEMPERATURE
OPENAI_VISION_MODEL
OPTIONS_LIVE_PROVIDERS_ENABLED
OPTIONS_LIVE_PROVIDER_KEYS
OPTIONS_TRADIER_DRY_RUN_ENABLED
OPTIONS_TRADIER_ENABLED
PHASE_F_CASH_LEDGER_COMPARISON_ACCOUNT_IDS
PHASE_F_CORPORATE_ACTIONS_COMPARISON_ACCOUNT_IDS
PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS
POLYGON_API_KEY
PORTFOLIO_FX_UPDATE_ENABLED
PORTFOLIO_RISK_CONCENTRATION_ALERT_PCT
PORTFOLIO_RISK_DRAWDOWN_ALERT_PCT
PORTFOLIO_RISK_LOOKBACK_DAYS
PORTFOLIO_RISK_STOP_LOSS_ALERT_PCT
PORTFOLIO_RISK_STOP_LOSS_NEAR_RATIO
POSTGRES_PHASE_A_APPLY_SCHEMA
POSTGRES_PHASE_A_REAL_DSN
POSTGRES_PHASE_A_URL
PREFETCH_REALTIME_QUOTES
PROXY_HOST
PROXY_PORT
PUSHOVER_API_TOKEN
PUSHOVER_USER_KEY
PUSHPLUS_TOKEN
PUSHPLUS_TOPIC
PYTDX_HOST
PYTDX_PORT
PYTDX_PRIORITY
PYTDX_SERVERS
PYTHONPATH
PYTHONUNBUFFERED
PYTHONUTF8
QUANT_DUCKDB_ENABLED
QUANT_ENGINE
QUANT_MAX_BENCHMARK_SYMBOLS
QUANT_PARQUET_ROOT
REALTIME_CACHE_TTL
REALTIME_SOURCE_PRIORITY
RELEASE_SECRET_SCAN_BASE_REF
REPORT_HISTORY_COMPARE_N
REPORT_INTEGRITY_ENABLED
REPORT_INTEGRITY_RETRY
REPORT_LANGUAGE
REPORT_RENDERER_ENABLED
REPORT_SUMMARY_ONLY
REPORT_TEMPLATES_DIR
REPORT_TYPE
ROTATION_RADAR_ALPACA_PER_WINDOW_TIMEOUT_SECONDS
ROTATION_RADAR_ALPACA_PROVIDER_DEADLINE_SECONDS
ROTATION_RADAR_ALPACA_TOTAL_PROVIDER_BUDGET_SECONDS
RUN_IMMEDIATELY
SAVE_CONTEXT_SNAPSHOT
SCANNER_AI_ENABLED
SCANNER_AI_TOP_N
SCANNER_LOCAL_UNIVERSE_PATH
SCANNER_NOTIFICATION_ENABLED
SCANNER_PROFILE
SCANNER_SCHEDULE_ENABLED
SCANNER_SCHEDULE_RUN_IMMEDIATELY
SCANNER_SCHEDULE_TIME
SCANNER_UNIVERSE_LIFECYCLE_ROOT
SCHEDULE_ENABLED
SCHEDULE_RUN_IMMEDIATELY
SCHEDULE_TIME
SEARXNG_BASE_URLS
SEARXNG_PUBLIC_INSTANCES_ENABLED
SERPAPI_API_KEYS
SERVERCHAN3_SENDKEY
SHOW_RUNTIME_EXECUTION_SUMMARY
SINGLE_STOCK_NOTIFY
SLACK_BOT_TOKEN
SLACK_CHANNEL_ID
SLACK_WEBHOOK_URL
SOCIAL_SENTIMENT_API_KEY
SOCIAL_SENTIMENT_API_URL
SOURCE_COMMIT_TIMESTAMP
SOURCE_VERSION
STOCK_LIST
TAVILY_API_KEYS
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
TELEGRAM_MESSAGE_THREAD_ID
TELEGRAM_WEBHOOK_SECRET
TEST
TICKFLOW_API_KEY
TRADIER_API_TOKEN
TRADING_DAY_CHECK_ENABLED
TRUST_X_FORWARDED_FOR
TUSHARE_PRIORITY
TUSHARE_TOKEN
TWELVEDATA_API_KEY
TWELVEDATA_API_KEYS
TWELVE_DATA_API_KEY
TWELVE_DATA_API_KEYS
TZ
USE_PROXY
US_STOCK_PARQUET_DIR
VISION_MODEL
VISION_PROVIDER_PRIORITY
VITE_API_URL
VITE_WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED
WATCHLIST_SCORE_REFRESH_CN_TIME
WATCHLIST_SCORE_REFRESH_ENABLED
WATCHLIST_SCORE_REFRESH_HK_TIME
WATCHLIST_SCORE_REFRESH_MAX_SYMBOLS
WATCHLIST_SCORE_REFRESH_US_TIME
WEBHOOK_VERIFY_SSL
WEBUI_AUTO_BUILD
WEBUI_ENABLED
WEBUI_HOST
WEBUI_PORT
WECHAT_MAX_BYTES
WECHAT_MSG_TYPE
WECHAT_WEBHOOK_URL
WECOM_AGENT_ID
WECOM_CORPID
WECOM_ENCODING_AES_KEY
WECOM_TOKEN
WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED
WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED
WOLFYSTOCK_BACKUP_PITR_EXECUTION_ENABLED
WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED
WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED
WOLFYSTOCK_MFA_LOGIN_BREAK_GLASS_ENABLED
WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED
WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_SCOPE
WOLFYSTOCK_MFA_SECRET_ENCRYPTION_KEY
WOLFYSTOCK_MFA_SECRET_KEY_ID
WOLFYSTOCK_MFA_TEST_SECRET
WOLFYSTOCK_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED
WOLFYSTOCK_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENABLED
WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_ENFORCEMENT_PILOT_ENABLED
WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_OWNER_IDS
WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_PILOT_ENABLED
WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_ROLLBACK_ENABLED
WOLFYSTOCK_QUOTA_ENFORCEMENT_MODE
WOLFYSTOCK_US_OHLCV_TIER1_SYMBOLS
WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED
YFINANCE_PRIORITY
ZHIPU_API_KEY
http_proxy
https_proxy
no_proxy
""".split()
)
REDACTED_VALUE = "<redacted>"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)
_PREPARATION_LOCK = threading.RLock()
_PREPARED_SOURCES: dict[Path, dict[str, SettingSource]] = {}
_SECRET_NAME_PARTS = re.compile(
    r"(?:^|_)(?:API_?KEYS?|TOKEN|PASSWORD|SECRET|SENDKEY|DSN|CREDENTIALS?)(?:_|$)"
)


@dataclass(frozen=True)
class _AliasSpec:
    canonical_name: str
    ordered_names: tuple[str, ...]
    empty_is_set: bool = False


_ALIAS_SPECS = (
    _AliasSpec("APP_ENV", ("APP_ENV", "ENVIRONMENT", "DSA_ENV")),
    _AliasSpec(
        "TWELVE_DATA_API_KEYS",
        (
            "TWELVE_DATA_API_KEYS",
            "TWELVEDATA_API_KEYS",
            "TWELVE_DATA_API_KEY",
            "TWELVEDATA_API_KEY",
        ),
    ),
    _AliasSpec("VISION_MODEL", ("VISION_MODEL", "OPENAI_VISION_MODEL")),
    _AliasSpec(
        "DISCORD_MAIN_CHANNEL_ID",
        ("DISCORD_MAIN_CHANNEL_ID", "DISCORD_CHANNEL_ID"),
    ),
    _AliasSpec(
        "SCHEDULE_RUN_IMMEDIATELY",
        ("SCHEDULE_RUN_IMMEDIATELY", "RUN_IMMEDIATELY"),
        empty_is_set=True,
    ),
    _AliasSpec(
        "AGENT_SKILL_DIR",
        ("AGENT_SKILL_DIR", "AGENT_STRATEGY_DIR"),
    ),
    _AliasSpec(
        "AGENT_SKILL_AUTOWEIGHT",
        ("AGENT_SKILL_AUTOWEIGHT", "AGENT_STRATEGY_AUTOWEIGHT"),
    ),
    _AliasSpec(
        "AGENT_SKILL_ROUTING",
        ("AGENT_SKILL_ROUTING", "AGENT_STRATEGY_ROUTING"),
    ),
    _AliasSpec(
        "OPENAI_API_KEYS",
        ("OPENAI_API_KEYS", "AIHUBMIX_KEY", "OPENAI_API_KEY"),
    ),
    _AliasSpec(
        "LOCAL_US_PARQUET_DIR",
        ("LOCAL_US_PARQUET_DIR", "US_STOCK_PARQUET_DIR"),
    ),
    _AliasSpec("HTTP_PROXY", ("HTTP_PROXY", "http_proxy")),
    _AliasSpec("HTTPS_PROXY", ("HTTPS_PROXY", "https_proxy")),
    _AliasSpec("NO_PROXY", ("NO_PROXY", "no_proxy")),
)

_ALIAS_SPECS += tuple(
    _AliasSpec(
        f"ADMIN_LOG_{suffix}",
        (f"ADMIN_LOG_{suffix}", f"ADMIN_LOGS_{suffix}"),
    )
    for suffix in (
        "RETENTION_DAYS",
        "MIN_RETENTION_DAYS",
        "STORAGE_SOFT_LIMIT_MB",
        "STORAGE_HARD_LIMIT_MB",
        "CLEANUP_BATCH_SIZE",
        "AUTO_CLEANUP_ENABLED",
    )
)

_T = TypeVar("_T")


class _FrozenList(tuple):
    """Tuple representation that remembers an original mutable list."""


class SettingSource(str, Enum):
    DEFAULT = "default"
    ENV_FILE = "env-file"
    PROCESS_ENV = "process-env"


@dataclass(frozen=True)
class SettingProvenance:
    canonical_name: str
    source_name: str
    source: SettingSource
    env_file: Path | None = None
    is_alias: bool = False


@dataclass(frozen=True)
class SettingConflict:
    canonical_name: str
    selected_name: str
    conflicting_names: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeSettings:
    env_file: Path
    profile: str
    config_values: Mapping[str, Any] = field(repr=False)
    provenance: Mapping[str, SettingProvenance]
    conflicts: tuple[SettingConflict, ...]
    _raw_environment: Mapping[str, str] = field(repr=False)

    @classmethod
    def load(cls, *, config_type=None) -> "RuntimeSettings":
        if config_type is None:
            from src.config import Config

            config_type = Config

        process_environment = dict(os.environ)
        env_file = _resolve_env_file(process_environment.get("ENV_FILE"))
        file_values = _read_env_file(env_file)

        config = config_type._parse_environment()
        with _PREPARATION_LOCK:
            prepared_sources = dict(_PREPARED_SOURCES.get(env_file, {}))
        effective_environment = {
            name: value
            for name in RECOGNIZED_SETTING_NAMES
            if (value := os.environ.get(name)) is not None
        }
        provenance = _build_provenance(
            process_environment,
            file_values,
            effective_environment,
            env_file,
            prepared_sources,
        )
        conflicts = _detect_alias_conflicts(effective_environment)
        config_values = {
            config_field.name: _freeze(getattr(config, config_field.name))
            for config_field in fields(config_type)
            if config_field.name != "_instance"
        }
        profile = _normalize_profile(
            _selected_alias_value(effective_environment, _ALIAS_SPECS[0])[1]
        )
        return cls(
            env_file=env_file,
            profile=profile,
            config_values=MappingProxyType(config_values),
            provenance=MappingProxyType(provenance),
            conflicts=conflicts,
            _raw_environment=MappingProxyType(effective_environment),
        )

    def to_config(self, config_type: type[_T] | None = None) -> _T:
        if config_type is None:
            from src.config import Config

            config_type = Config
        config = config_type(
            **{name: _thaw(value) for name, value in self.config_values.items()}
        )
        setattr(config, "_runtime_settings_snapshot", self)
        return config

    def diagnostics(self) -> dict[str, Any]:
        safe_values = {
            name: REDACTED_VALUE if _is_secret_name(name) else value
            for name, value in sorted(self._raw_environment.items())
        }
        return {
            "envFile": str(self.env_file),
            "profile": self.profile,
            "values": safe_values,
            "provenance": {
                name: {
                    "source": detail.source.value,
                    "sourceName": detail.source_name,
                    "isAlias": detail.is_alias,
                }
                for name, detail in sorted(self.provenance.items())
            },
            "conflicts": [
                {
                    "canonicalName": conflict.canonical_name,
                    "selectedName": conflict.selected_name,
                    "conflictingNames": list(conflict.conflicting_names),
                }
                for conflict in self.conflicts
            ],
        }


def _resolve_env_file(raw_path: str | None) -> Path:
    path = Path(raw_path).expanduser() if raw_path else _REPOSITORY_ROOT / ".env"
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve(strict=False)


def setup_environment(*, override: bool = False) -> Path:
    """Load the active env file and preserve legacy proxy normalization."""
    env_file = _resolve_env_file(os.getenv("ENV_FILE"))
    before_load = dict(os.environ)
    file_values = _read_env_file(env_file)
    with _PREPARATION_LOCK:
        previous_sources = _PREPARED_SOURCES.get(env_file, {})
    load_dotenv_file(env_file, override=override)
    prepared_sources: dict[str, SettingSource] = {}
    for name, file_value in file_values.items():
        retained_file_source = (
            previous_sources.get(name) is SettingSource.ENV_FILE
            and before_load.get(name) == file_value
        )
        prepared_sources[name] = (
            SettingSource.ENV_FILE
            if override or name not in before_load or retained_file_source
            else SettingSource.PROCESS_ENV
        )
    with _PREPARATION_LOCK:
        _PREPARED_SOURCES[env_file] = prepared_sources
    _apply_legacy_proxy_environment()
    return env_file


def _apply_legacy_proxy_environment() -> None:
    from src.config import parse_env_bool

    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if (
        not http_proxy
        and os.getenv("GITHUB_ACTIONS") != "true"
        and parse_env_bool(os.getenv("USE_PROXY"), False)
    ):
        proxy_host = (os.getenv("PROXY_HOST") or "127.0.0.1").strip() or "127.0.0.1"
        proxy_port = (os.getenv("PROXY_PORT") or "10809").strip() or "10809"
        http_proxy = f"http://{proxy_host}:{proxy_port}"
        if not https_proxy:
            https_proxy = http_proxy
    if http_proxy:
        os.environ["HTTP_PROXY"] = http_proxy
        os.environ["http_proxy"] = http_proxy
    if https_proxy:
        os.environ["HTTPS_PROXY"] = https_proxy
        os.environ["https_proxy"] = https_proxy


def _read_env_file(env_file: Path) -> dict[str, str]:
    try:
        parsed = read_dotenv_values(env_file)
    except (OSError, UnicodeError):
        return {}
    return {name: str(value) for name, value in parsed.items() if value is not None}


def get_env_file_value(key: str) -> str | None:
    """Read one key from the active absolute env-file identity."""
    return _read_env_file(_resolve_env_file(os.getenv("ENV_FILE"))).get(key)


def resolve_report_language_env_value(
    preexisting_env_value: str | None,
) -> str:
    """Preserve the process-over-file REPORT_LANGUAGE compatibility rule."""
    env_file = _resolve_env_file(os.getenv("ENV_FILE"))
    file_value = _read_env_file(env_file).get("REPORT_LANGUAGE")
    if preexisting_env_value is not None:
        env_text = preexisting_env_value.strip()
        file_text = (file_value or "").strip()
        if file_text and env_text and env_text.lower() != file_text.lower():
            logger.warning(
                "REPORT_LANGUAGE environment value '%s' overrides %s ('%s')",
                preexisting_env_value,
                env_file,
                file_value,
            )
        return preexisting_env_value
    if file_value is not None:
        return file_value
    return os.getenv("REPORT_LANGUAGE") or "zh"


def _source_for_name(
    name: str,
    process_environment: Mapping[str, str],
    file_values: Mapping[str, str],
    prepared_sources: Mapping[str, SettingSource],
) -> SettingSource:
    if name in prepared_sources:
        return prepared_sources[name]
    if name in process_environment:
        return SettingSource.PROCESS_ENV
    if name in file_values:
        return SettingSource.ENV_FILE
    return SettingSource.DEFAULT


def _build_provenance(
    process_environment: Mapping[str, str],
    file_values: Mapping[str, str],
    effective_environment: Mapping[str, str],
    env_file: Path,
    prepared_sources: Mapping[str, SettingSource],
) -> dict[str, SettingProvenance]:
    provenance = {
        name: SettingProvenance(
            canonical_name=name,
            source_name=name,
            source=_source_for_name(
                name,
                process_environment,
                file_values,
                prepared_sources,
            ),
            env_file=(
                env_file
                if name == "ENV_FILE"
                or _source_for_name(
                    name,
                    process_environment,
                    file_values,
                    prepared_sources,
                )
                is SettingSource.ENV_FILE
                else None
            ),
        )
        for name in RECOGNIZED_SETTING_NAMES
    }
    for spec in _ALIAS_SPECS:
        selected_name, _ = _selected_alias_value(effective_environment, spec)
        if selected_name is None:
            continue
        source = _source_for_name(
            selected_name,
            process_environment,
            file_values,
            prepared_sources,
        )
        provenance[spec.canonical_name] = SettingProvenance(
            canonical_name=spec.canonical_name,
            source_name=selected_name,
            source=source,
            env_file=env_file if source is SettingSource.ENV_FILE else None,
            is_alias=selected_name != spec.canonical_name,
        )
    return provenance


def _selected_alias_value(
    environment: Mapping[str, str],
    spec: _AliasSpec,
) -> tuple[str | None, str | None]:
    for name in spec.ordered_names:
        if name not in environment:
            continue
        value = environment[name]
        if spec.empty_is_set or value:
            return name, value
    return None, None


def _detect_alias_conflicts(
    environment: Mapping[str, str],
) -> tuple[SettingConflict, ...]:
    conflicts: list[SettingConflict] = []
    for spec in _ALIAS_SPECS:
        selected_name, selected_value = _selected_alias_value(environment, spec)
        if selected_name is None:
            continue
        conflicting_names = tuple(
            name
            for name in spec.ordered_names
            if name != selected_name
            and name in environment
            and environment[name] != selected_value
        )[:3]
        if conflicting_names:
            conflicts.append(
                SettingConflict(
                    canonical_name=spec.canonical_name,
                    selected_name=selected_name,
                    conflicting_names=conflicting_names,
                )
            )
    return tuple(sorted(conflicts, key=lambda item: item.canonical_name))


def _normalize_profile(raw_value: str | None) -> str:
    normalized = (raw_value or "development").strip().lower()
    return {
        "dev": "development",
        "prod": "production",
        "testing": "test",
        "stage": "staging",
    }.get(normalized, normalized or "development")


def _is_secret_name(name: str) -> bool:
    upper_name = name.upper()
    return (
        bool(_SECRET_NAME_PARTS.search(upper_name))
        or upper_name.endswith(("_URL", "_URLS"))
        or any(
            marker in upper_name
            for marker in (
                "WEBHOOK_URL",
                "DATABASE_URL",
                "BASE_URL",
                "REMOTE_URL",
            )
        )
    )


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return _FrozenList(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, _FrozenList):
        return [_thaw(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_thaw(item) for item in value)
    if isinstance(value, frozenset):
        return {_thaw(item) for item in value}
    return value


def parse_runtime_config(config_type):
    """Parse all typed consumer values for one immutable runtime snapshot."""
    from src import config as config_facade

    cls = config_type
    setup_env = config_facade.setup_env
    parse_env_bool = config_facade.parse_env_bool
    parse_env_float = config_facade.parse_env_float
    parse_env_int = config_facade.parse_env_int
    parse_env_int_list = config_facade.parse_env_int_list
    get_configured_llm_models = config_facade.get_configured_llm_models
    normalize_agent_litellm_model = config_facade.normalize_agent_litellm_model
    resolve_configured_llm_model_alias = config_facade.resolve_configured_llm_model_alias

    """
    Parse consumer values for the runtime settings owner.

    加载优先级：
    1. 系统环境变量
    2. .env 文件
    3. 代码中的默认值
    """
    preexisting_report_language = os.environ.get("REPORT_LANGUAGE")

    # 确保环境变量已加载
    setup_env()

    # === 智能代理配置 (关键修复) ===
    # 如果配置了代理，自动设置 NO_PROXY 以排除国内数据源，避免行情获取失败
    http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
    if http_proxy:
        # 国内金融数据源域名列表
        domestic_domains = [
            'eastmoney.com',   # 东方财富 (Efinance/Akshare)
            'sina.com.cn',     # 新浪财经 (Akshare)
            '163.com',         # 网易财经 (Akshare)
            'tushare.pro',     # Tushare
            'baostock.com',    # Baostock
            'sse.com.cn',      # 上交所
            'szse.cn',         # 深交所
            'csindex.com.cn',  # 中证指数
            'cninfo.com.cn',   # 巨潮资讯
            'localhost',
            '127.0.0.1'
        ]

        # 获取现有的 no_proxy
        current_no_proxy = os.getenv('NO_PROXY') or os.getenv('no_proxy') or ''
        existing_domains = current_no_proxy.split(',') if current_no_proxy else []

        # 合并去重
        final_domains = list(set(existing_domains + domestic_domains))
        final_no_proxy = ','.join(filter(None, final_domains))

        # 设置环境变量 (requests/urllib3/aiohttp 都会遵守此设置)
        os.environ['NO_PROXY'] = final_no_proxy
        os.environ['no_proxy'] = final_no_proxy

        # 确保 HTTP_PROXY 也被正确设置（以防仅在 .env 中定义但未导出）
        os.environ['HTTP_PROXY'] = http_proxy
        os.environ['http_proxy'] = http_proxy

        # HTTPS_PROXY 同理
        https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        if https_proxy:
            os.environ['HTTPS_PROXY'] = https_proxy
            os.environ['https_proxy'] = https_proxy

    # 解析自选股列表（逗号分隔，统一为大写 Issue #355）
    stock_list_str = os.getenv('STOCK_LIST', '')
    stock_list = [
        (c or "").strip().upper()
        for c in stock_list_str.split(',')
        if (c or "").strip()
    ]

    # 如果没有配置，使用默认的示例股票
    if not stock_list:
        stock_list = ['600519', '000001', '300750']

    # === LiteLLM multi-key parsing ===
    # GEMINI_API_KEYS (comma-separated) > GEMINI_API_KEY (single)
    _gemini_keys_raw = os.getenv('GEMINI_API_KEYS', '')
    gemini_api_keys = [k.strip() for k in _gemini_keys_raw.split(',') if k.strip()]
    _single_gemini = os.getenv('GEMINI_API_KEY', '').strip()
    if not gemini_api_keys and _single_gemini:
        gemini_api_keys = [_single_gemini]

    # ANTHROPIC_API_KEYS > ANTHROPIC_API_KEY
    _anthropic_keys_raw = os.getenv('ANTHROPIC_API_KEYS', '')
    anthropic_api_keys = [k.strip() for k in _anthropic_keys_raw.split(',') if k.strip()]
    _single_anthropic = os.getenv('ANTHROPIC_API_KEY', '').strip()
    if not anthropic_api_keys and _single_anthropic:
        anthropic_api_keys = [_single_anthropic]

    # OPENAI_API_KEYS > AIHUBMIX_KEY > OPENAI_API_KEY
    _openai_keys_raw = os.getenv('OPENAI_API_KEYS', '')
    openai_api_keys = [k.strip() for k in _openai_keys_raw.split(',') if k.strip()]
    if not openai_api_keys:
        _aihubmix = os.getenv('AIHUBMIX_KEY', '').strip()
        _single_openai = os.getenv('OPENAI_API_KEY', '').strip()
        _fallback_key = _aihubmix or _single_openai
        if _fallback_key:
            openai_api_keys = [_fallback_key]

    # DEEPSEEK_API_KEYS > DEEPSEEK_API_KEY (independent from OpenAI-compatible layer)
    _deepseek_keys_raw = os.getenv('DEEPSEEK_API_KEYS', '')
    deepseek_api_keys = [k.strip() for k in _deepseek_keys_raw.split(',') if k.strip()]
    if not deepseek_api_keys:
        _single_deepseek = os.getenv('DEEPSEEK_API_KEY', '').strip()
        if _single_deepseek:
            deepseek_api_keys = [_single_deepseek]

    # LITELLM_MODEL: explicit config takes precedence; else infer from available keys
    litellm_model = os.getenv('LITELLM_MODEL', '').strip()
    if not litellm_model:
        _gemini_model_name = os.getenv('GEMINI_MODEL', 'gemini-3-flash-preview').strip()
        _anthropic_model_name = os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022').strip()
        _openai_model_name = os.getenv('OPENAI_MODEL', 'gpt-4o-mini').strip()
        if gemini_api_keys:
            litellm_model = f'gemini/{_gemini_model_name}'
        elif anthropic_api_keys:
            litellm_model = f'anthropic/{_anthropic_model_name}'
        elif deepseek_api_keys:
            litellm_model = 'deepseek/deepseek-chat'
        elif openai_api_keys:
            # For openai-compatible models, add prefix only if not already prefixed
            if '/' not in _openai_model_name:
                litellm_model = f'openai/{_openai_model_name}'
            else:
                litellm_model = _openai_model_name

    # LITELLM_FALLBACK_MODELS: comma-separated list of fallback models
    _fallback_str = os.getenv('LITELLM_FALLBACK_MODELS', '')
    if _fallback_str.strip():
        litellm_fallback_models = [m.strip() for m in _fallback_str.split(',') if m.strip()]
    else:
        # Backward compat: use gemini_model_fallback when primary is gemini
        _gemini_fallback = os.getenv('GEMINI_MODEL_FALLBACK', 'gemini-2.5-flash').strip()
        if litellm_model.startswith('gemini/') and _gemini_fallback:
            _fb = f'gemini/{_gemini_fallback}' if '/' not in _gemini_fallback else _gemini_fallback
            litellm_fallback_models = [_fb]
        else:
            litellm_fallback_models = []

    # Admin UI explicit AI route override (D3).
    # Keep backward compatibility: explicit AI_* keys override inferred/default routing,
    # then we still mirror final effective values into legacy fields.
    ai_primary_gateway = os.getenv('AI_PRIMARY_GATEWAY', '').strip().lower()
    ai_primary_model = os.getenv('AI_PRIMARY_MODEL', '').strip()
    ai_backup_gateway = os.getenv('AI_BACKUP_GATEWAY', '').strip().lower()
    ai_backup_model = os.getenv('AI_BACKUP_MODEL', '').strip()

    if ai_primary_model:
        litellm_model = ai_primary_model
    if ai_backup_model:
        litellm_fallback_models = [
            ai_backup_model,
            *[model for model in litellm_fallback_models if model != ai_backup_model],
        ]

    # === LLM Channels + YAML config ===
    litellm_config_path = os.getenv('LITELLM_CONFIG', '').strip() or None
    llm_models_source = "legacy_env"
    llm_channels: List[Dict[str, Any]] = []
    llm_model_list: List[Dict[str, Any]] = []

    # Priority 1: LITELLM_CONFIG (standard LiteLLM YAML config file)
    if litellm_config_path:
        llm_model_list = cls._parse_litellm_yaml(litellm_config_path)
        if llm_model_list:
            llm_models_source = "litellm_config"

    # Priority 2: LLM_CHANNELS (env var based channel config)
    if not llm_model_list:
        _channels_str = os.getenv('LLM_CHANNELS', '').strip()
        if not _channels_str and (ai_primary_gateway or ai_backup_gateway):
            _channels_str = ",".join(
                [
                    channel
                    for channel in [ai_primary_gateway, ai_backup_gateway]
                    if channel
                ]
            )
        if _channels_str:
            llm_channels = cls._parse_llm_channels(_channels_str)
            llm_model_list = cls._channels_to_model_list(llm_channels)
            if llm_model_list:
                llm_models_source = "llm_channels"

    # Priority 3: Legacy env vars → auto-build model_list (backward compatible)
    if not llm_model_list:
        llm_model_list = cls._legacy_keys_to_model_list(
            gemini_api_keys, anthropic_api_keys, openai_api_keys,
            os.getenv('OPENAI_BASE_URL') or (
                'https://aihubmix.com/v1' if os.getenv('AIHUBMIX_KEY') else None
            ),
            deepseek_api_keys,
        )
        if llm_model_list:
            llm_models_source = "legacy_env"

    # Auto-infer LITELLM_MODEL from channels when not explicitly set
    if not litellm_model and llm_channels:
        for _ch in llm_channels:
            if _ch.get('models'):
                litellm_model = _ch['models'][0]
                break

    # Auto-infer LITELLM_FALLBACK_MODELS from channels when not explicitly set
    if not litellm_fallback_models and llm_channels and litellm_model:
        _all_ch_models: List[str] = []
        for _ch in llm_channels:
            _all_ch_models.extend(_ch.get('models', []))
        _seen = {litellm_model}
        litellm_fallback_models = [
            m for m in _all_ch_models
            if m not in _seen and not _seen.add(m)  # type: ignore[func-returns-value]
        ]

    configured_router_model_set = set(get_configured_llm_models(llm_model_list))
    litellm_model = resolve_configured_llm_model_alias(
        litellm_model,
        configured_models=configured_router_model_set,
    )
    litellm_fallback_models = [
        resolve_configured_llm_model_alias(
            model,
            configured_models=configured_router_model_set,
        )
        for model in (litellm_fallback_models or [])
    ]

    agent_litellm_model = normalize_agent_litellm_model(
        os.getenv('AGENT_LITELLM_MODEL', ''),
        configured_models=configured_router_model_set,
    )

    # 解析搜索引擎 API Keys（支持多个 key，逗号分隔）
    bocha_keys_str = os.getenv('BOCHA_API_KEYS', '')
    bocha_api_keys = [k.strip() for k in bocha_keys_str.split(',') if k.strip()]

    minimax_keys_str = os.getenv('MINIMAX_API_KEYS', '')
    minimax_api_keys = [k.strip() for k in minimax_keys_str.split(',') if k.strip()]

    tavily_keys_str = os.getenv('TAVILY_API_KEYS', '')
    tavily_api_keys = [k.strip() for k in tavily_keys_str.split(',') if k.strip()]

    serpapi_keys_str = os.getenv('SERPAPI_API_KEYS', '')
    serpapi_keys = [k.strip() for k in serpapi_keys_str.split(',') if k.strip()]

    brave_keys_str = os.getenv('BRAVE_API_KEYS', '')
    brave_api_keys = [k.strip() for k in brave_keys_str.split(',') if k.strip()]

    gnews_keys_str = os.getenv('GNEWS_API_KEYS', '')
    gnews_api_keys = [k.strip() for k in gnews_keys_str.split(',') if k.strip()]
    if not gnews_api_keys:
        single_gnews = os.getenv('GNEWS_API_KEY', '').strip()
        if single_gnews:
            gnews_api_keys = [single_gnews]

    twelve_data_keys_str = os.getenv('TWELVE_DATA_API_KEYS', '') or os.getenv('TWELVEDATA_API_KEYS', '')
    twelve_data_api_keys = [k.strip() for k in twelve_data_keys_str.split(',') if k.strip()]
    single_twelve_data = (
        os.getenv('TWELVE_DATA_API_KEY', '').strip()
        or os.getenv('TWELVEDATA_API_KEY', '').strip()
    )
    if not twelve_data_api_keys and single_twelve_data:
        twelve_data_api_keys = [single_twelve_data]

    finnhub_keys_str = os.getenv('FINNHUB_API_KEYS', '')
    finnhub_api_keys = [k.strip() for k in finnhub_keys_str.split(',') if k.strip()]
    if not finnhub_api_keys:
        single_finnhub = os.getenv('FINNHUB_API_KEY', '').strip()
        if single_finnhub:
            finnhub_api_keys = [single_finnhub]

    fmp_keys_str = os.getenv('FMP_API_KEYS', '')
    fmp_api_keys = [k.strip() for k in fmp_keys_str.split(',') if k.strip()]
    if not fmp_api_keys:
        single_fmp = os.getenv('FMP_API_KEY', '').strip()
        if single_fmp:
            fmp_api_keys = [single_fmp]

    _raw_urls = [u.strip() for u in os.getenv('SEARXNG_BASE_URLS', '').split(',') if u.strip()]
    searxng_base_urls = []
    invalid_searxng_urls = []
    for u in _raw_urls:
        p = urlparse(u)
        if p.scheme in ('http', 'https') and p.netloc:
            searxng_base_urls.append(u)
        else:
            invalid_searxng_urls.append(u)
    if invalid_searxng_urls:
        logger.warning(
            "SEARXNG_BASE_URLS 中存在无效 URL，已忽略: %s",
            ", ".join(invalid_searxng_urls[:3]),
        )
    searxng_public_instances_enabled = parse_env_bool(
        os.getenv('SEARXNG_PUBLIC_INSTANCES_ENABLED'),
        default=True,
    )

    # 企微消息类型与最大字节数逻辑
    wechat_msg_type = os.getenv('WECHAT_MSG_TYPE', 'markdown')
    wechat_msg_type_lower = wechat_msg_type.lower()
    wechat_max_bytes_env = os.getenv('WECHAT_MAX_BYTES')
    if wechat_max_bytes_env not in (None, ''):
        wechat_max_bytes = parse_env_int(
            wechat_max_bytes_env,
            2048 if wechat_msg_type_lower == 'text' else 4000,
            field_name='WECHAT_MAX_BYTES',
            minimum=1,
        )
    else:
        # 未显式配置时，根据消息类型选择默认字节数
        wechat_max_bytes = 2048 if wechat_msg_type_lower == 'text' else 4000

    # Preserve historical semantics for startup flags: only an explicit
    # literal "true" enables immediate execution; empty strings stay False.
    legacy_run_immediately_env = os.getenv('RUN_IMMEDIATELY')
    legacy_run_immediately = (
        legacy_run_immediately_env.lower() == 'true'
        if legacy_run_immediately_env is not None
        else True
    )

    schedule_run_immediately_env = os.getenv('SCHEDULE_RUN_IMMEDIATELY')
    schedule_run_immediately = (
        schedule_run_immediately_env.lower() == 'true'
        if schedule_run_immediately_env is not None
        else legacy_run_immediately
    )

    report_language_raw = cls._resolve_report_language_env_value(
        preexisting_report_language
    )

    return cls(
        stock_list=stock_list,
        feishu_app_id=os.getenv('FEISHU_APP_ID'),
        feishu_app_secret=os.getenv('FEISHU_APP_SECRET'),
        feishu_folder_token=os.getenv('FEISHU_FOLDER_TOKEN'),
        tushare_token=os.getenv('TUSHARE_TOKEN'),
        tickflow_api_key=os.getenv('TICKFLOW_API_KEY'),
        fred_api_key=os.getenv('FRED_API_KEY') or None,
        twelve_data_api_keys=twelve_data_api_keys,
        twelve_data_api_key=single_twelve_data or (twelve_data_api_keys[0] if twelve_data_api_keys else None),
        alpaca_api_key_id=os.getenv('ALPACA_API_KEY_ID') or None,
        alpaca_api_secret_key=os.getenv('ALPACA_API_SECRET_KEY') or None,
        alpaca_data_feed=(os.getenv('ALPACA_DATA_FEED', 'iex').strip().lower() or 'iex'),
        litellm_model=litellm_model,
        litellm_fallback_models=litellm_fallback_models,
        llm_temperature=resolve_unified_llm_temperature(litellm_model),
        home_quick_analysis_enabled=parse_env_bool(
            os.getenv("HOME_QUICK_ANALYSIS_ENABLED"),
            default=True,
        ),
        home_quick_analysis_temperature=parse_env_float(
            os.getenv("HOME_QUICK_ANALYSIS_TEMPERATURE"),
            0.2,
            field_name="HOME_QUICK_ANALYSIS_TEMPERATURE",
            minimum=0.0,
            maximum=1.0,
        ),
        home_quick_analysis_max_output_tokens=parse_env_int(
            os.getenv("HOME_QUICK_ANALYSIS_MAX_OUTPUT_TOKENS"),
            4096,
            field_name="HOME_QUICK_ANALYSIS_MAX_OUTPUT_TOKENS",
            minimum=256,
            maximum=8192,
        ),
        home_analysis_log_full_prompt=parse_env_bool(
            os.getenv("HOME_ANALYSIS_LOG_FULL_PROMPT"),
            default=False,
        ),
        litellm_config_path=litellm_config_path,
        llm_models_source=llm_models_source,
        llm_channels=llm_channels,
        llm_model_list=llm_model_list,
        gemini_api_keys=gemini_api_keys,
        anthropic_api_keys=anthropic_api_keys,
        openai_api_keys=openai_api_keys,
        deepseek_api_keys=deepseek_api_keys,
        gemini_api_key=os.getenv('GEMINI_API_KEY'),
        gemini_model=os.getenv('GEMINI_MODEL', 'gemini-3-flash-preview'),
        gemini_model_fallback=os.getenv('GEMINI_MODEL_FALLBACK', 'gemini-2.5-flash'),
        gemini_temperature=parse_env_float(os.getenv('GEMINI_TEMPERATURE'), 0.7, field_name='GEMINI_TEMPERATURE'),
        gemini_request_delay=parse_env_float(os.getenv('GEMINI_REQUEST_DELAY'), 2.0, field_name='GEMINI_REQUEST_DELAY', minimum=0.0),
        gemini_max_retries=parse_env_int(os.getenv('GEMINI_MAX_RETRIES'), 5, field_name='GEMINI_MAX_RETRIES', minimum=0),
        gemini_retry_delay=parse_env_float(os.getenv('GEMINI_RETRY_DELAY'), 5.0, field_name='GEMINI_RETRY_DELAY', minimum=0.0),
        anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
        anthropic_model=os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022'),
        anthropic_temperature=parse_env_float(os.getenv('ANTHROPIC_TEMPERATURE'), 0.7, field_name='ANTHROPIC_TEMPERATURE'),
        anthropic_max_tokens=parse_env_int(os.getenv('ANTHROPIC_MAX_TOKENS'), 8192, field_name='ANTHROPIC_MAX_TOKENS', minimum=1),
        # AIHubmix is the preferred OpenAI-compatible provider (one key, all models, no VPN required).
        # Within the OpenAI-compatible layer: AIHUBMIX_KEY takes priority over OPENAI_API_KEY.
        # Overall provider fallback order: Gemini > Anthropic > OpenAI-compatible (incl. AIHubmix).
        # base_url is auto-set to aihubmix.com/v1 when AIHUBMIX_KEY is used and no explicit
        # OPENAI_BASE_URL override is provided.
        # Model names match upstream (e.g. gemini-3.1-pro-preview, gpt-4o, gpt-4o-free, deepseek-chat).
        openai_api_key=os.getenv('AIHUBMIX_KEY') or os.getenv('OPENAI_API_KEY') or None,
        openai_base_url=os.getenv('OPENAI_BASE_URL') or (
            'https://aihubmix.com/v1' if os.getenv('AIHUBMIX_KEY') else None
        ),  # noqa: E501
        openai_model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
        openai_vision_model=os.getenv('OPENAI_VISION_MODEL') or None,
        openai_temperature=parse_env_float(os.getenv('OPENAI_TEMPERATURE'), 0.7, field_name='OPENAI_TEMPERATURE'),
        # Vision model: VISION_MODEL > OPENAI_VISION_MODEL (alias) > default
        vision_model=(
            os.getenv('VISION_MODEL')
            or os.getenv('OPENAI_VISION_MODEL')
            or ""
        ),
        vision_provider_priority=os.getenv('VISION_PROVIDER_PRIORITY', 'gemini,anthropic,openai'),
        bocha_api_keys=bocha_api_keys,
        minimax_api_keys=minimax_api_keys,
        tavily_api_keys=tavily_api_keys,
        brave_api_keys=brave_api_keys,
        serpapi_keys=serpapi_keys,
        gnews_api_keys=gnews_api_keys,
        finnhub_api_keys=finnhub_api_keys,
        fmp_api_keys=fmp_api_keys,
        searxng_base_urls=searxng_base_urls,
        searxng_public_instances_enabled=searxng_public_instances_enabled,
        social_sentiment_api_key=os.getenv('SOCIAL_SENTIMENT_API_KEY') or None,
        social_sentiment_api_url=os.getenv('SOCIAL_SENTIMENT_API_URL', 'https://api.adanos.org').rstrip('/'),
        news_max_age_days=parse_env_int(os.getenv('NEWS_MAX_AGE_DAYS'), 3, field_name='NEWS_MAX_AGE_DAYS', minimum=1),
        news_strategy_profile=cls._parse_news_strategy_profile(
            os.getenv('NEWS_STRATEGY_PROFILE', 'short')
        ),
        bias_threshold=parse_env_float(os.getenv('BIAS_THRESHOLD'), 5.0, field_name='BIAS_THRESHOLD', minimum=1.0),
        agent_litellm_model=agent_litellm_model,
        agent_mode=os.getenv('AGENT_MODE', 'false').lower() == 'true',
        _agent_mode_explicit=os.getenv('AGENT_MODE') is not None,
        agent_max_steps=parse_env_int(os.getenv('AGENT_MAX_STEPS'), 10, field_name='AGENT_MAX_STEPS', minimum=1),
        agent_skills=[s.strip() for s in os.getenv('AGENT_SKILLS', '').split(',') if s.strip()],
        agent_skill_dir=os.getenv('AGENT_SKILL_DIR') or os.getenv('AGENT_STRATEGY_DIR'),
        agent_nl_routing=os.getenv('AGENT_NL_ROUTING', 'false').lower() == 'true',
        agent_arch=os.getenv('AGENT_ARCH', 'single').lower(),
        agent_orchestrator_mode=os.getenv('AGENT_ORCHESTRATOR_MODE', 'standard').lower(),
        agent_orchestrator_timeout_s=parse_env_int(
            os.getenv('AGENT_ORCHESTRATOR_TIMEOUT_S'),
            600,
            field_name='AGENT_ORCHESTRATOR_TIMEOUT_S',
            minimum=0,
        ),
        agent_risk_override=os.getenv('AGENT_RISK_OVERRIDE', 'true').lower() == 'true',
        agent_deep_research_budget=parse_env_int(
            os.getenv('AGENT_DEEP_RESEARCH_BUDGET'),
            30000,
            field_name='AGENT_DEEP_RESEARCH_BUDGET',
            minimum=5000,
        ),
        agent_deep_research_timeout=parse_env_int(
            os.getenv('AGENT_DEEP_RESEARCH_TIMEOUT'),
            180,
            field_name='AGENT_DEEP_RESEARCH_TIMEOUT',
            minimum=30,
        ),
        agent_memory_enabled=os.getenv('AGENT_MEMORY_ENABLED', 'false').lower() == 'true',
        agent_skill_autoweight=(
            os.getenv('AGENT_SKILL_AUTOWEIGHT')
            or os.getenv('AGENT_STRATEGY_AUTOWEIGHT', 'true')
        ).lower() == 'true',
        agent_skill_routing=(
            os.getenv('AGENT_SKILL_ROUTING')
            or os.getenv('AGENT_STRATEGY_ROUTING', 'auto')
        ).lower(),
        agent_event_monitor_enabled=os.getenv('AGENT_EVENT_MONITOR_ENABLED', 'false').lower() == 'true',
        agent_event_monitor_interval_minutes=parse_env_int(
            os.getenv('AGENT_EVENT_MONITOR_INTERVAL_MINUTES'),
            5,
            field_name='AGENT_EVENT_MONITOR_INTERVAL_MINUTES',
            minimum=1,
        ),
        agent_event_alert_rules_json=os.getenv('AGENT_EVENT_ALERT_RULES_JSON', ''),
        wechat_webhook_url=os.getenv('WECHAT_WEBHOOK_URL'),
        feishu_webhook_url=os.getenv('FEISHU_WEBHOOK_URL'),
        telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
        telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID'),
        telegram_message_thread_id=os.getenv('TELEGRAM_MESSAGE_THREAD_ID'),
        email_sender=os.getenv('EMAIL_SENDER'),
        email_sender_name=os.getenv('EMAIL_SENDER_NAME', 'WolfyStock股票分析助手'),
        email_password=os.getenv('EMAIL_PASSWORD'),
        email_receivers=[r.strip() for r in os.getenv('EMAIL_RECEIVERS', '').split(',') if r.strip()],
        stock_email_groups=cls._parse_stock_email_groups(),
        pushover_user_key=os.getenv('PUSHOVER_USER_KEY'),
        pushover_api_token=os.getenv('PUSHOVER_API_TOKEN'),
        pushplus_token=os.getenv('PUSHPLUS_TOKEN'),
        pushplus_topic=os.getenv('PUSHPLUS_TOPIC'),
        serverchan3_sendkey=os.getenv('SERVERCHAN3_SENDKEY'),
        custom_webhook_urls=[u.strip() for u in os.getenv('CUSTOM_WEBHOOK_URLS', '').split(',') if u.strip()],
        custom_webhook_bearer_token=os.getenv('CUSTOM_WEBHOOK_BEARER_TOKEN'),
        webhook_verify_ssl=os.getenv('WEBHOOK_VERIFY_SSL', 'true').lower() == 'true',
        discord_bot_token=os.getenv('DISCORD_BOT_TOKEN'),
        discord_main_channel_id=(
            os.getenv('DISCORD_MAIN_CHANNEL_ID')
            or os.getenv('DISCORD_CHANNEL_ID')
        ),
        discord_webhook_url=os.getenv('DISCORD_WEBHOOK_URL'),
        slack_webhook_url=os.getenv('SLACK_WEBHOOK_URL'),
        slack_bot_token=os.getenv('SLACK_BOT_TOKEN'),
        slack_channel_id=os.getenv('SLACK_CHANNEL_ID'),
        astrbot_url=os.getenv('ASTRBOT_URL'),
        astrbot_token=os.getenv('ASTRBOT_TOKEN'),
        single_stock_notify=os.getenv('SINGLE_STOCK_NOTIFY', 'false').lower() == 'true',
        report_type=cls._parse_report_type(os.getenv('REPORT_TYPE', 'simple')),
        report_language=cls._parse_report_language(report_language_raw),
        report_summary_only=os.getenv('REPORT_SUMMARY_ONLY', 'false').lower() == 'true',
        report_templates_dir=os.getenv('REPORT_TEMPLATES_DIR', 'templates'),
        report_renderer_enabled=os.getenv('REPORT_RENDERER_ENABLED', 'false').lower() == 'true',
        report_integrity_enabled=os.getenv('REPORT_INTEGRITY_ENABLED', 'true').lower() == 'true',
        report_integrity_retry=parse_env_int(os.getenv('REPORT_INTEGRITY_RETRY'), 1, field_name='REPORT_INTEGRITY_RETRY', minimum=0),
        report_history_compare_n=parse_env_int(os.getenv('REPORT_HISTORY_COMPARE_N'), 0, field_name='REPORT_HISTORY_COMPARE_N', minimum=0),
        analysis_delay=parse_env_float(os.getenv('ANALYSIS_DELAY'), 0.0, field_name='ANALYSIS_DELAY', minimum=0.0),
        merge_email_notification=os.getenv('MERGE_EMAIL_NOTIFICATION', 'false').lower() == 'true',
        feishu_max_bytes=parse_env_int(os.getenv('FEISHU_MAX_BYTES'), 20000, field_name='FEISHU_MAX_BYTES', minimum=1),
        wechat_max_bytes=wechat_max_bytes,
        wechat_msg_type=wechat_msg_type_lower,
        discord_max_words=parse_env_int(os.getenv('DISCORD_MAX_WORDS'), 2000, field_name='DISCORD_MAX_WORDS', minimum=1),
        markdown_to_image_channels=[
            c.strip().lower()
            for c in os.getenv('MARKDOWN_TO_IMAGE_CHANNELS', '').split(',')
            if c.strip()
        ],
        markdown_to_image_max_chars=parse_env_int(
            os.getenv('MARKDOWN_TO_IMAGE_MAX_CHARS'),
            15000,
            field_name='MARKDOWN_TO_IMAGE_MAX_CHARS',
            minimum=1,
        ),
        md2img_engine=cls._parse_md2img_engine(os.getenv('MD2IMG_ENGINE', 'wkhtmltoimage')),
        prefetch_realtime_quotes=os.getenv('PREFETCH_REALTIME_QUOTES', 'true').lower() == 'true',
        database_path=os.getenv('DATABASE_PATH', './data/stock_analysis.db'),
        postgres_phase_a_url=(os.getenv('POSTGRES_PHASE_A_URL') or '').strip() or None,
        postgres_phase_a_apply_schema=os.getenv('POSTGRES_PHASE_A_APPLY_SCHEMA', 'true').lower() == 'true',
        admin_logs_retention_days=parse_env_int(
            os.getenv('ADMIN_LOG_RETENTION_DAYS') or os.getenv('ADMIN_LOGS_RETENTION_DAYS'),
            90,
            field_name='ADMIN_LOG_RETENTION_DAYS',
            minimum=1,
        ),
        admin_logs_min_retention_days=parse_env_int(
            os.getenv('ADMIN_LOG_MIN_RETENTION_DAYS') or os.getenv('ADMIN_LOGS_MIN_RETENTION_DAYS'),
            7,
            field_name='ADMIN_LOG_MIN_RETENTION_DAYS',
            minimum=0,
        ),
        admin_logs_storage_soft_limit_mb=parse_env_int(
            os.getenv('ADMIN_LOG_STORAGE_SOFT_LIMIT_MB') or os.getenv('ADMIN_LOGS_STORAGE_SOFT_LIMIT_MB'),
            512,
            field_name='ADMIN_LOG_STORAGE_SOFT_LIMIT_MB',
            minimum=1,
        ),
        admin_logs_storage_hard_limit_mb=parse_env_int(
            os.getenv('ADMIN_LOG_STORAGE_HARD_LIMIT_MB') or os.getenv('ADMIN_LOGS_STORAGE_HARD_LIMIT_MB'),
            1024,
            field_name='ADMIN_LOG_STORAGE_HARD_LIMIT_MB',
            minimum=1,
        ),
        admin_logs_cleanup_batch_size=parse_env_int(
            os.getenv('ADMIN_LOG_CLEANUP_BATCH_SIZE') or os.getenv('ADMIN_LOGS_CLEANUP_BATCH_SIZE'),
            1000,
            field_name='ADMIN_LOG_CLEANUP_BATCH_SIZE',
            minimum=1,
        ),
        admin_logs_auto_cleanup_enabled=parse_env_bool(
            os.getenv('ADMIN_LOG_AUTO_CLEANUP_ENABLED') or os.getenv('ADMIN_LOGS_AUTO_CLEANUP_ENABLED'),
            True,
        ),
        admin_logs_warning_threshold_count=parse_env_int(
            os.getenv('ADMIN_LOGS_WARNING_THRESHOLD_COUNT'),
            50000,
            field_name='ADMIN_LOGS_WARNING_THRESHOLD_COUNT',
            minimum=1,
        ),
        admin_logs_critical_threshold_count=parse_env_int(
            os.getenv('ADMIN_LOGS_CRITICAL_THRESHOLD_COUNT'),
            100000,
            field_name='ADMIN_LOGS_CRITICAL_THRESHOLD_COUNT',
            minimum=1,
        ),
        admin_logs_warning_threshold_storage_bytes=(
            parse_env_int(
                os.getenv('ADMIN_LOGS_WARNING_THRESHOLD_STORAGE_BYTES'),
                0,
                field_name='ADMIN_LOGS_WARNING_THRESHOLD_STORAGE_BYTES',
                minimum=0,
            )
            or None
        ),
        enable_phase_f_trades_list_comparison=parse_env_bool(
            os.getenv('ENABLE_PHASE_F_TRADES_LIST_COMPARISON'),
            False,
        ),
        phase_f_trades_list_comparison_account_ids=parse_env_int_list(
            os.getenv('PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS'),
            field_name='PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS',
        ),
        enable_phase_f_cash_ledger_comparison=parse_env_bool(
            os.getenv('ENABLE_PHASE_F_CASH_LEDGER_COMPARISON'),
            False,
        ),
        phase_f_cash_ledger_comparison_account_ids=parse_env_int_list(
            os.getenv('PHASE_F_CASH_LEDGER_COMPARISON_ACCOUNT_IDS'),
            field_name='PHASE_F_CASH_LEDGER_COMPARISON_ACCOUNT_IDS',
        ),
        enable_phase_f_corporate_actions_comparison=parse_env_bool(
            os.getenv('ENABLE_PHASE_F_CORPORATE_ACTIONS_COMPARISON'),
            False,
        ),
        phase_f_corporate_actions_comparison_account_ids=parse_env_int_list(
            os.getenv('PHASE_F_CORPORATE_ACTIONS_COMPARISON_ACCOUNT_IDS'),
            field_name='PHASE_F_CORPORATE_ACTIONS_COMPARISON_ACCOUNT_IDS',
        ),
        save_context_snapshot=os.getenv('SAVE_CONTEXT_SNAPSHOT', 'true').lower() == 'true',
        backtest_enabled=os.getenv('BACKTEST_ENABLED', 'true').lower() == 'true',
        backtest_eval_window_days=parse_env_int(os.getenv('BACKTEST_EVAL_WINDOW_DAYS'), 10, field_name='BACKTEST_EVAL_WINDOW_DAYS', minimum=1),
        backtest_min_age_days=parse_env_int(os.getenv('BACKTEST_MIN_AGE_DAYS'), 14, field_name='BACKTEST_MIN_AGE_DAYS', minimum=0),
        backtest_engine_version=os.getenv('BACKTEST_ENGINE_VERSION', 'v1'),
        backtest_neutral_band_pct=parse_env_float(
            os.getenv('BACKTEST_NEUTRAL_BAND_PCT'),
            2.0,
            field_name='BACKTEST_NEUTRAL_BAND_PCT',
            minimum=0.0,
        ),
        quant_engine=os.getenv('QUANT_ENGINE', 'python'),
        duckdb_database_path=os.getenv('DUCKDB_DATABASE_PATH', 'data/quant/wolfystock.duckdb'),
        quant_parquet_root=os.getenv('QUANT_PARQUET_ROOT', 'data/quant/parquet'),
        quant_duckdb_enabled=os.getenv('QUANT_DUCKDB_ENABLED', 'false').lower() == 'true',
        quant_max_benchmark_symbols=parse_env_int(
            os.getenv('QUANT_MAX_BENCHMARK_SYMBOLS'),
            5000,
            field_name='QUANT_MAX_BENCHMARK_SYMBOLS',
            minimum=1,
        ),
        log_dir=os.getenv('LOG_DIR', './logs'),
        log_level=os.getenv('LOG_LEVEL', 'INFO'),
        max_workers=parse_env_int(os.getenv('MAX_WORKERS'), 3, field_name='MAX_WORKERS', minimum=1),
        debug=os.getenv('DEBUG', 'false').lower() == 'true',
        config_validate_mode=os.getenv('CONFIG_VALIDATE_MODE', 'warn').lower(),
        http_proxy=os.getenv('HTTP_PROXY'),
        https_proxy=os.getenv('HTTPS_PROXY'),
        schedule_enabled=os.getenv('SCHEDULE_ENABLED', 'false').lower() == 'true',
        schedule_time=os.getenv('SCHEDULE_TIME', '18:00'),
        schedule_run_immediately=schedule_run_immediately,
        scanner_profile=os.getenv('SCANNER_PROFILE', 'cn_preopen_v1'),
        scanner_local_universe_path=os.getenv('SCANNER_LOCAL_UNIVERSE_PATH', './data/scanner_cn_universe_cache.csv'),
        scanner_ai_enabled=os.getenv('SCANNER_AI_ENABLED', 'false').lower() == 'true',
        scanner_ai_top_n=parse_env_int(
            os.getenv('SCANNER_AI_TOP_N'),
            3,
            field_name='SCANNER_AI_TOP_N',
            minimum=1,
            maximum=10,
        ),
        scanner_schedule_enabled=os.getenv('SCANNER_SCHEDULE_ENABLED', 'false').lower() == 'true',
        scanner_schedule_time=os.getenv('SCANNER_SCHEDULE_TIME', '08:40'),
        scanner_schedule_run_immediately=os.getenv('SCANNER_SCHEDULE_RUN_IMMEDIATELY', 'false').lower() == 'true',
        scanner_notification_enabled=os.getenv('SCANNER_NOTIFICATION_ENABLED', 'true').lower() == 'true',
        watchlist_score_refresh_enabled=os.getenv('WATCHLIST_SCORE_REFRESH_ENABLED', 'true').lower() == 'true',
        watchlist_score_refresh_us_time=os.getenv('WATCHLIST_SCORE_REFRESH_US_TIME', '08:45'),
        watchlist_score_refresh_cn_time=os.getenv('WATCHLIST_SCORE_REFRESH_CN_TIME', '09:00'),
        watchlist_score_refresh_hk_time=os.getenv('WATCHLIST_SCORE_REFRESH_HK_TIME', '09:00'),
        watchlist_score_refresh_max_symbols=parse_env_int(
            os.getenv('WATCHLIST_SCORE_REFRESH_MAX_SYMBOLS'),
            250,
            field_name='WATCHLIST_SCORE_REFRESH_MAX_SYMBOLS',
            minimum=1,
        ),
        run_immediately=legacy_run_immediately,
        market_review_enabled=os.getenv('MARKET_REVIEW_ENABLED', 'true').lower() == 'true',
        market_review_region=cls._parse_market_review_region(
            os.getenv('MARKET_REVIEW_REGION', 'cn')
        ),
        trading_day_check_enabled=os.getenv('TRADING_DAY_CHECK_ENABLED', 'true').lower() != 'false',
        webui_enabled=os.getenv('WEBUI_ENABLED', 'false').lower() == 'true',
        webui_host=os.getenv('WEBUI_HOST', '127.0.0.1'),
        webui_port=parse_env_int(os.getenv('WEBUI_PORT'), 8000, field_name='WEBUI_PORT', minimum=1, maximum=65535),
        # 机器人配置
        bot_enabled=os.getenv('BOT_ENABLED', 'true').lower() == 'true',
        bot_command_prefix=os.getenv('BOT_COMMAND_PREFIX', '/'),
        bot_rate_limit_requests=parse_env_int(os.getenv('BOT_RATE_LIMIT_REQUESTS'), 10, field_name='BOT_RATE_LIMIT_REQUESTS', minimum=1),
        bot_rate_limit_window=parse_env_int(os.getenv('BOT_RATE_LIMIT_WINDOW'), 60, field_name='BOT_RATE_LIMIT_WINDOW', minimum=1),
        bot_admin_users=[u.strip() for u in os.getenv('BOT_ADMIN_USERS', '').split(',') if u.strip()],
        # 飞书机器人
        feishu_verification_token=os.getenv('FEISHU_VERIFICATION_TOKEN'),
        feishu_encrypt_key=os.getenv('FEISHU_ENCRYPT_KEY'),
        feishu_stream_enabled=os.getenv('FEISHU_STREAM_ENABLED', 'false').lower() == 'true',
        # 钉钉机器人
        dingtalk_app_key=os.getenv('DINGTALK_APP_KEY'),
        dingtalk_app_secret=os.getenv('DINGTALK_APP_SECRET'),
        dingtalk_stream_enabled=os.getenv('DINGTALK_STREAM_ENABLED', 'false').lower() == 'true',
        # 企业微信机器人
        wecom_corpid=os.getenv('WECOM_CORPID'),
        wecom_token=os.getenv('WECOM_TOKEN'),
        wecom_encoding_aes_key=os.getenv('WECOM_ENCODING_AES_KEY'),
        wecom_agent_id=os.getenv('WECOM_AGENT_ID'),
        # Telegram
        telegram_webhook_secret=os.getenv('TELEGRAM_WEBHOOK_SECRET'),
        # Discord 机器人扩展配置
        discord_bot_status=os.getenv('DISCORD_BOT_STATUS', 'A股智能分析 | /help'),
        # 实时行情增强数据配置
        enable_realtime_quote=os.getenv('ENABLE_REALTIME_QUOTE', 'true').lower() == 'true',
        enable_realtime_technical_indicators=os.getenv(
            'ENABLE_REALTIME_TECHNICAL_INDICATORS', 'true'
        ).lower() == 'true',
        enable_chip_distribution=os.getenv('ENABLE_CHIP_DISTRIBUTION', 'true').lower() == 'true',
        # 东财接口补丁开关
        enable_eastmoney_patch=os.getenv('ENABLE_EASTMONEY_PATCH', 'false').lower() == 'true',
        # 实时行情数据源优先级：
        # - tencent: 腾讯财经，有量比/换手率/PE/PB等，单股查询稳定（推荐）
        # - akshare_sina: 新浪财经，基本行情稳定，但无量比
        # - efinance/akshare_em: 东财全量接口，数据最全但容易被封
        # - tushare: Tushare Pro，需要2000积分，数据全面
        realtime_source_priority=cls._resolve_realtime_source_priority(),
        realtime_cache_ttl=parse_env_int(os.getenv('REALTIME_CACHE_TTL'), 600, field_name='REALTIME_CACHE_TTL', minimum=0),
        market_cache_remote_backend=(os.getenv('MARKET_CACHE_REMOTE_BACKEND') or 'disabled').strip().lower(),
        market_cache_remote_url=(os.getenv('MARKET_CACHE_REMOTE_URL') or '').strip() or None,
        market_cache_remote_timeout_seconds=parse_env_float(
            os.getenv('MARKET_CACHE_REMOTE_TIMEOUT_SECONDS'),
            0.2,
            field_name='MARKET_CACHE_REMOTE_TIMEOUT_SECONDS',
            minimum=0.001,
            maximum=5.0,
        ),
        market_cache_remote_queue_size=parse_env_int(
            os.getenv('MARKET_CACHE_REMOTE_QUEUE_SIZE'),
            256,
            field_name='MARKET_CACHE_REMOTE_QUEUE_SIZE',
            minimum=1,
        ),
        circuit_breaker_cooldown=parse_env_int(os.getenv('CIRCUIT_BREAKER_COOLDOWN'), 300, field_name='CIRCUIT_BREAKER_COOLDOWN', minimum=0),
        enable_fundamental_pipeline=os.getenv('ENABLE_FUNDAMENTAL_PIPELINE', 'true').lower() == 'true',
        fundamental_stage_timeout_seconds=parse_env_float(
            os.getenv('FUNDAMENTAL_STAGE_TIMEOUT_SECONDS'),
            1.5,
            field_name='FUNDAMENTAL_STAGE_TIMEOUT_SECONDS',
            minimum=0.0,
        ),
        fundamental_fetch_timeout_seconds=parse_env_float(
            os.getenv('FUNDAMENTAL_FETCH_TIMEOUT_SECONDS'),
            0.8,
            field_name='FUNDAMENTAL_FETCH_TIMEOUT_SECONDS',
            minimum=0.0,
        ),
        fundamental_retry_max=parse_env_int(os.getenv('FUNDAMENTAL_RETRY_MAX'), 1, field_name='FUNDAMENTAL_RETRY_MAX', minimum=0),
        fundamental_cache_ttl_seconds=parse_env_int(
            os.getenv('FUNDAMENTAL_CACHE_TTL_SECONDS'),
            120,
            field_name='FUNDAMENTAL_CACHE_TTL_SECONDS',
            minimum=0,
        ),
        fundamental_cache_max_entries=parse_env_int(
            os.getenv('FUNDAMENTAL_CACHE_MAX_ENTRIES'),
            256,
            field_name='FUNDAMENTAL_CACHE_MAX_ENTRIES',
            minimum=1,
        ),
        portfolio_risk_concentration_alert_pct=parse_env_float(
            os.getenv('PORTFOLIO_RISK_CONCENTRATION_ALERT_PCT'),
            35.0,
            field_name='PORTFOLIO_RISK_CONCENTRATION_ALERT_PCT',
            minimum=0.0,
        ),
        portfolio_risk_drawdown_alert_pct=parse_env_float(
            os.getenv('PORTFOLIO_RISK_DRAWDOWN_ALERT_PCT'),
            15.0,
            field_name='PORTFOLIO_RISK_DRAWDOWN_ALERT_PCT',
            minimum=0.0,
        ),
        portfolio_risk_stop_loss_alert_pct=parse_env_float(
            os.getenv('PORTFOLIO_RISK_STOP_LOSS_ALERT_PCT'),
            10.0,
            field_name='PORTFOLIO_RISK_STOP_LOSS_ALERT_PCT',
            minimum=0.0,
        ),
        portfolio_risk_stop_loss_near_ratio=parse_env_float(
            os.getenv('PORTFOLIO_RISK_STOP_LOSS_NEAR_RATIO'),
            0.8,
            field_name='PORTFOLIO_RISK_STOP_LOSS_NEAR_RATIO',
            minimum=0.0,
        ),
        portfolio_risk_lookback_days=parse_env_int(
            os.getenv('PORTFOLIO_RISK_LOOKBACK_DAYS'),
            180,
            field_name='PORTFOLIO_RISK_LOOKBACK_DAYS',
            minimum=1,
        ),
        portfolio_fx_update_enabled=os.getenv('PORTFOLIO_FX_UPDATE_ENABLED', 'true').lower() == 'true'
    )


def parse_litellm_yaml(config_type, config_path: str) -> List[Dict[str, Any]]:
    """Parse a standard LiteLLM config YAML file into Router model_list.

    Supports the ``os.environ/VAR_NAME`` syntax for secret references.
    Returns an empty list on any error (logged, never raises).
    """
    import logging
    _logger = logging.getLogger(__name__)
    try:
        import yaml
    except ImportError:
        _logger.warning("PyYAML not installed; LITELLM_CONFIG ignored. Install with: pip install pyyaml")
        return []

    path = Path(config_path)
    if not path.is_absolute():
        path = _REPOSITORY_ROOT / path
    if not path.exists():
        _logger.warning(f"LITELLM_CONFIG file not found: {path}")
        return []

    try:
        with open(path, encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f) or {}
    except Exception as e:
        _logger.warning(f"Failed to parse LITELLM_CONFIG: {e}")
        return []

    model_list = yaml_config.get('model_list', [])
    if not isinstance(model_list, list):
        _logger.warning("LITELLM_CONFIG: model_list must be a list")
        return []

    # Resolve os.environ/ references in string params
    for entry in model_list:
        params = entry.get('litellm_params', {})
        for key in list(params.keys()):
            val = params.get(key)
            if isinstance(val, str) and val.startswith('os.environ/'):
                env_name = val.split('/', 1)[1]
                params[key] = os.getenv(env_name, '')

    _logger.info(f"LITELLM_CONFIG: loaded {len(model_list)} model deployment(s) from {path}")
    return model_list


def resolve_unified_llm_temperature(model: str) -> float:
    """Resolve the unified temperature with the historical fallback order."""
    from src import config as config_facade

    llm_temperature_raw = os.getenv("LLM_TEMPERATURE")
    if llm_temperature_raw and llm_temperature_raw.strip():
        try:
            return float(llm_temperature_raw)
        except (ValueError, TypeError):
            pass

    provider_temperature_env = {
        "gemini": "GEMINI_TEMPERATURE",
        "vertex_ai": "GEMINI_TEMPERATURE",
        "anthropic": "ANTHROPIC_TEMPERATURE",
        "openai": "OPENAI_TEMPERATURE",
        "deepseek": "OPENAI_TEMPERATURE",
    }
    preferred_env = provider_temperature_env.get(
        config_facade._get_litellm_provider(model)
    )
    if preferred_env:
        preferred_value = os.getenv(preferred_env)
        if preferred_value and preferred_value.strip():
            try:
                return float(preferred_value)
            except (ValueError, TypeError):
                pass

    for env_name in (
        "GEMINI_TEMPERATURE",
        "ANTHROPIC_TEMPERATURE",
        "OPENAI_TEMPERATURE",
    ):
        env_value = os.getenv(env_name)
        if env_value and env_value.strip():
            try:
                return float(env_value)
            except (ValueError, TypeError):
                continue
    return 0.7


def parse_llm_channels(config_type, channels_str: str) -> List[Dict[str, Any]]:
    from src import config as config_facade
    parse_env_bool = config_facade.parse_env_bool
    resolve_llm_channel_protocol = config_facade.resolve_llm_channel_protocol
    normalize_llm_channel_model = config_facade.normalize_llm_channel_model
    canonicalize_llm_channel_protocol = config_facade.canonicalize_llm_channel_protocol
    channel_allows_empty_api_key = config_facade.channel_allows_empty_api_key
    SUPPORTED_LLM_CHANNEL_PROTOCOLS = config_facade.SUPPORTED_LLM_CHANNEL_PROTOCOLS
    """Parse LLM_CHANNELS env var and per-channel env vars.

    Format:
        LLM_CHANNELS=aihubmix,deepseek,gemini
        LLM_AIHUBMIX_PROTOCOL=openai
        LLM_AIHUBMIX_BASE_URL=https://aihubmix.com/v1
        LLM_AIHUBMIX_API_KEY=sk-xxx           (or LLM_AIHUBMIX_API_KEYS=k1,k2)
        LLM_AIHUBMIX_MODELS=gpt-4o-mini,claude-3-5-sonnet
        LLM_AIHUBMIX_ENABLED=true
    """
    import logging
    _logger = logging.getLogger(__name__)

    channels: List[Dict[str, Any]] = []
    for raw_name in channels_str.split(','):
        ch_name = raw_name.strip()
        if not ch_name:
            continue
        ch_upper = ch_name.upper()

        base_url = os.getenv(f'LLM_{ch_upper}_BASE_URL', '').strip() or None
        protocol_raw = os.getenv(f'LLM_{ch_upper}_PROTOCOL', '').strip()
        enabled = parse_env_bool(os.getenv(f'LLM_{ch_upper}_ENABLED'), default=True)

        # API keys: LLM_{NAME}_API_KEYS (multi) > LLM_{NAME}_API_KEY (single)
        api_keys_raw = os.getenv(f'LLM_{ch_upper}_API_KEYS', '')
        api_keys = [k.strip() for k in api_keys_raw.split(',') if k.strip()]
        if not api_keys:
            single_key = os.getenv(f'LLM_{ch_upper}_API_KEY', '').strip()
            if single_key:
                api_keys = [single_key]

        # Models
        models_raw = os.getenv(f'LLM_{ch_upper}_MODELS', '')
        raw_models = [m.strip() for m in models_raw.split(',') if m.strip()]
        protocol = resolve_llm_channel_protocol(protocol_raw, base_url=base_url, models=raw_models, channel_name=ch_name)
        models = [normalize_llm_channel_model(m, protocol, base_url) for m in raw_models]

        # Extra headers (JSON string, optional)
        extra_headers_raw = os.getenv(f'LLM_{ch_upper}_EXTRA_HEADERS', '').strip()
        extra_headers = None
        if extra_headers_raw:
            try:
                extra_headers = json.loads(extra_headers_raw)
            except json.JSONDecodeError:
                _logger.warning(f"LLM_{ch_upper}_EXTRA_HEADERS: invalid JSON, ignored")

        if not enabled:
            _logger.info(f"LLM channel '{ch_name}': disabled, skipped")
            continue

        if protocol_raw and canonicalize_llm_channel_protocol(protocol_raw) not in SUPPORTED_LLM_CHANNEL_PROTOCOLS:
            _logger.warning(
                "LLM_%s_PROTOCOL=%s is unsupported; auto-detected protocol=%s",
                ch_upper,
                protocol_raw,
                protocol or "unknown",
            )

        if not api_keys and channel_allows_empty_api_key(protocol, base_url):
            api_keys = [""]

        if not api_keys:
            _logger.warning(f"LLM channel '{ch_name}': no API key configured, skipped")
            continue
        if not models:
            _logger.warning(f"LLM channel '{ch_name}': no models configured, skipped")
            continue

        channels.append({
            'name': ch_name.lower(),
            'protocol': protocol,
            'enabled': enabled,
            'base_url': base_url,
            'api_keys': api_keys,
            'models': models,
            'extra_headers': extra_headers,
        })
        _logger.info(f"LLM channel '{ch_name}': {len(models)} model(s), {len(api_keys)} key(s)")

    return channels


def channels_to_model_list(config_type, channels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert parsed LLM channels to LiteLLM Router model_list format."""
    model_list: List[Dict[str, Any]] = []
    for ch in channels:
        for model_name in ch['models']:
            for api_key in ch['api_keys']:
                litellm_params: Dict[str, Any] = {
                    'model': model_name,
                }
                if api_key:
                    litellm_params['api_key'] = api_key
                if ch['base_url']:
                    litellm_params['api_base'] = ch['base_url']
                # Auto-inject aihubmix sponsored header
                headers = dict(ch.get('extra_headers') or {})
                if ch['base_url'] and 'aihubmix.com' in ch['base_url']:
                    headers.setdefault('APP-Code', 'GPIJ3886')
                if headers:
                    litellm_params['extra_headers'] = headers

                model_list.append({
                    'model_name': model_name,
                    'litellm_params': litellm_params,
                })
    return model_list


def legacy_keys_to_model_list(config_type, gemini_keys: List[str], anthropic_keys: List[str], openai_keys: List[str], openai_base_url: Optional[str], deepseek_keys: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Build Router model_list from legacy per-provider keys (backward compat).

    Returns a model_list where each provider's keys are expanded into
    deployments, keyed by placeholder model_name tokens.  The analyzer
    resolves actual model_names at call time from LITELLM_MODEL /
    LITELLM_FALLBACK_MODELS.
    """
    model_list: List[Dict[str, Any]] = []

    # Gemini keys
    for k in gemini_keys:
        if k and len(k) >= 8:
            model_list.append({
                'model_name': '__legacy_gemini__',
                'litellm_params': {'model': '__legacy_gemini__', 'api_key': k},
            })

    # Anthropic keys
    for k in anthropic_keys:
        if k and len(k) >= 8:
            model_list.append({
                'model_name': '__legacy_anthropic__',
                'litellm_params': {'model': '__legacy_anthropic__', 'api_key': k},
            })

    # OpenAI-compatible keys
    for k in openai_keys:
        if k and len(k) >= 8:
            params: Dict[str, Any] = {'model': '__legacy_openai__', 'api_key': k}
            if openai_base_url:
                params['api_base'] = openai_base_url
            if openai_base_url and 'aihubmix.com' in openai_base_url:
                params['extra_headers'] = {'APP-Code': 'GPIJ3886'}
            model_list.append({
                'model_name': '__legacy_openai__',
                'litellm_params': params,
            })

    # DeepSeek keys (native litellm provider — auto-resolves api_base)
    for k in (deepseek_keys or []):
        if k and len(k) >= 8:
            model_list.append({
                'model_name': '__legacy_deepseek__',
                'litellm_params': {
                    'model': '__legacy_deepseek__',
                    'api_key': k,
                },
            })

    return model_list


def parse_stock_email_groups(config_type) -> List[Tuple[List[str], List[str]]]:
    """
    Parse STOCK_GROUP_N and EMAIL_GROUP_N from environment.
    Returns [(stocks, emails), ...] ordered by group index.
    """
    groups: dict = {}
    stock_re = re.compile(r'^STOCK_GROUP_(\d+)$', re.IGNORECASE)
    email_re = re.compile(r'^EMAIL_GROUP_(\d+)$', re.IGNORECASE)
    for key in os.environ:
        m = stock_re.match(key)
        if m:
            idx = int(m.group(1))
            val = os.environ[key].strip()
            groups.setdefault(idx, {})['stocks'] = [c.strip() for c in val.split(',') if c.strip()]
        m = email_re.match(key)
        if m:
            idx = int(m.group(1))
            val = os.environ[key].strip()
            groups.setdefault(idx, {})['emails'] = [e.strip() for e in val.split(',') if e.strip()]
    result = []
    for idx in sorted(groups.keys()):
        g = groups[idx]
        if 'stocks' in g and 'emails' in g and g['stocks'] and g['emails']:
            result.append((g['stocks'], g['emails']))
    return result


def parse_report_type(config_type, value: str) -> str:
    """Parse REPORT_TYPE, fallback to simple for invalid values (supports brief)."""
    v = (value or 'simple').strip().lower()
    if v in ('simple', 'full', 'brief'):
        return v
    import logging
    logging.getLogger(__name__).warning(
        f"REPORT_TYPE '{value}' invalid, fallback to 'simple' (valid: simple/full/brief)"
    )
    return 'simple'


def parse_report_language(config_type, value: Optional[str]) -> str:
    """Parse REPORT_LANGUAGE, fallback to zh for invalid values."""
    normalized = normalize_report_language(value, default="zh")
    raw = (value or "").strip()
    if raw and not is_supported_report_language_value(raw):
        logging.getLogger(__name__).warning(
            "REPORT_LANGUAGE '%s' invalid, fallback to 'zh' (valid: zh/en)",
            value,
        )
    return normalized


def parse_news_strategy_profile(config_type, value: Optional[str]) -> str:
    from src import config as config_facade
    normalize_news_strategy_profile = config_facade.normalize_news_strategy_profile
    """Parse NEWS_STRATEGY_PROFILE, fallback to short for invalid values."""
    normalized = normalize_news_strategy_profile(value)
    raw = (value or "short").strip().lower()
    if raw != normalized:
        logging.getLogger(__name__).warning(
            "NEWS_STRATEGY_PROFILE '%s' invalid, fallback to 'short' "
            "(valid: ultra_short/short/medium/long)",
            value,
        )
    return normalized


def parse_market_review_region(config_type, value: str) -> str:
    """解析大盘复盘市场区域，非法值记录警告后回退为 cn"""
    import logging
    v = (value or 'cn').strip().lower()
    if v in ('cn', 'us', 'both'):
        return v
    logging.getLogger(__name__).warning(
        f"MARKET_REVIEW_REGION 配置值 '{value}' 无效，已回退为默认值 'cn'（合法值：cn / us / both）"
    )
    return 'cn'


def parse_md2img_engine(config_type, value: str) -> str:
    """Parse MD2IMG_ENGINE, fallback to wkhtmltoimage for invalid values (Issue #455)."""
    v = (value or 'wkhtmltoimage').strip().lower()
    if v in ('wkhtmltoimage', 'markdown-to-file'):
        return v
    if v:
        import logging
        logging.getLogger(__name__).warning(
            f"MD2IMG_ENGINE '{value}' invalid, fallback to 'wkhtmltoimage' "
            "(valid: wkhtmltoimage | markdown-to-file)"
        )
    return 'wkhtmltoimage'


def resolve_realtime_source_priority(config_type) -> str:
    """
    Resolve realtime source priority with automatic tushare injection.

    When TUSHARE_TOKEN is configured but REALTIME_SOURCE_PRIORITY is not
    explicitly set, automatically prepend 'tushare' to the default priority
    so that the paid data source is utilized for realtime quotes as well.
    """
    explicit = os.getenv('REALTIME_SOURCE_PRIORITY')
    default_priority = 'tencent,akshare_sina,efinance,akshare_em'

    if explicit:
        # User explicitly set priority, respect it
        return explicit

    tushare_token = os.getenv('TUSHARE_TOKEN', '').strip()
    if tushare_token:
        # Token configured but no explicit priority override
        # Prepend tushare so the paid source is tried first
        import logging
        logger = logging.getLogger(__name__)
        resolved = f'tushare,{default_priority}'
        logger.info(
            f"TUSHARE_TOKEN detected, auto-injecting tushare into realtime priority: {resolved}"
        )
        return resolved

    return default_priority
