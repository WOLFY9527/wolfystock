# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 配置管理模块
===================================

职责：
1. 使用单例模式管理全局配置
2. 从 .env 文件加载敏感配置
3. 提供类型安全的配置访问接口
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib.parse import urlparse
from dataclasses import dataclass, field

from src.utils.dotenv_loader import read_dotenv_values

logger = logging.getLogger(__name__)


@dataclass
class ConfigIssue:
    """Structured configuration validation issue with a severity level.

    Attributes:
        severity: One of "error", "warning", or "info".
        message:  Human-readable description of the issue.
        field:    The environment variable / config field name most relevant to
                  this issue (empty string when not applicable).
    """

    severity: Literal["error", "warning", "info"]
    message: str
    field: str = ""

    def __str__(self) -> str:  # noqa: D105
        return self.message


@dataclass
class LLMModelSelection:
    """Safe runtime resolution for a configured LLM model."""

    requested_model: str
    resolved_model: str
    available_models: List[str] = field(default_factory=list)
    resolution: Literal["empty", "direct", "configured", "normalized", "fallback", "unavailable"] = "empty"

    @property
    def is_usable(self) -> bool:
        return bool(self.resolved_model)


_MANAGED_LITELLM_KEY_PROVIDERS = {"gemini", "vertex_ai", "anthropic", "openai", "deepseek"}
SUPPORTED_LLM_CHANNEL_PROTOCOLS = ("openai", "anthropic", "gemini", "vertex_ai", "deepseek", "ollama")
_FALSEY_ENV_VALUES = {"0", "false", "no", "off"}
NEWS_STRATEGY_WINDOWS: Dict[str, int] = {
    "ultra_short": 1,
    "short": 3,
    "medium": 7,
    "long": 30,
}


def parse_env_bool(value: Optional[str], default: bool = False) -> bool:
    """Parse common truthy/falsey environment-style values."""
    if value is None:
        return default
    normalized = value.strip().lower()
    if not normalized:
        return default
    return normalized not in _FALSEY_ENV_VALUES


def parse_env_int(
    value: Optional[str],
    default: int,
    *,
    field_name: str,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    """Parse an integer env value with warning + fallback semantics."""
    raw_value = value
    if raw_value is None or not str(raw_value).strip():
        parsed = int(default)
    else:
        try:
            parsed = int(str(raw_value).strip())
        except (TypeError, ValueError):
            logger.warning(
                "%s=%r is not a valid integer; falling back to %s",
                field_name,
                raw_value,
                default,
            )
            parsed = int(default)

    if minimum is not None and parsed < minimum:
        logger.warning(
            "%s=%r is below minimum %s; clamping to %s",
            field_name,
            parsed,
            minimum,
            minimum,
        )
        parsed = minimum
    if maximum is not None and parsed > maximum:
        logger.warning(
            "%s=%r is above maximum %s; clamping to %s",
            field_name,
            parsed,
            maximum,
            maximum,
        )
        parsed = maximum
    return parsed


def parse_env_float(
    value: Optional[str],
    default: float,
    *,
    field_name: str,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> float:
    """Parse a float env value with warning + fallback semantics."""
    raw_value = value
    if raw_value is None or not str(raw_value).strip():
        parsed = float(default)
    else:
        try:
            parsed = float(str(raw_value).strip())
        except (TypeError, ValueError):
            logger.warning(
                "%s=%r is not a valid number; falling back to %s",
                field_name,
                raw_value,
                default,
            )
            parsed = float(default)

    if minimum is not None and parsed < minimum:
        logger.warning(
            "%s=%r is below minimum %s; clamping to %s",
            field_name,
            parsed,
            minimum,
            minimum,
        )
        parsed = minimum
    if maximum is not None and parsed > maximum:
        logger.warning(
            "%s=%r is above maximum %s; clamping to %s",
            field_name,
            parsed,
            maximum,
            maximum,
        )
        parsed = maximum
    return parsed


def parse_env_int_list(value: Optional[str], *, field_name: str) -> List[int]:
    """Parse a comma-separated integer list env value with warning + ignore semantics."""
    raw_value = str(value or "").strip()
    if not raw_value:
        return []

    parsed_values: List[int] = []
    for token in raw_value.split(","):
        raw_token = str(token or "").strip()
        if not raw_token:
            continue
        try:
            parsed_values.append(int(raw_token))
        except (TypeError, ValueError):
            logger.warning(
                "%s token %r is not a valid integer; ignoring it",
                field_name,
                raw_token,
            )
    return parsed_values


def normalize_news_strategy_profile(value: Optional[str]) -> str:
    """Normalize news strategy profile to known values."""
    candidate = (value or "short").strip().lower()
    return candidate if candidate in NEWS_STRATEGY_WINDOWS else "short"


def resolve_news_window_days(news_max_age_days: int, news_strategy_profile: Optional[str]) -> int:
    """Resolve effective news window days from profile and global max-age."""
    profile = normalize_news_strategy_profile(news_strategy_profile)
    profile_days = NEWS_STRATEGY_WINDOWS.get(profile, NEWS_STRATEGY_WINDOWS["short"])
    return max(1, min(max(1, int(news_max_age_days)), profile_days))


def canonicalize_llm_channel_protocol(value: Optional[str]) -> str:
    """Normalize a protocol label into a LiteLLM provider identifier."""
    candidate = (value or "").strip().lower().replace("-", "_")
    aliases = {
        "openai_compatible": "openai",
        "openai_compat": "openai",
        "claude": "anthropic",
        "google": "gemini",
        "vertex": "vertex_ai",
        "vertexai": "vertex_ai",
    }
    return aliases.get(candidate, candidate)


def resolve_llm_channel_protocol(
    protocol: Optional[str],
    *,
    base_url: Optional[str] = None,
    models: Optional[List[str]] = None,
    channel_name: Optional[str] = None,
) -> str:
    """Resolve the effective protocol for a channel."""
    explicit = canonicalize_llm_channel_protocol(protocol)
    if explicit in SUPPORTED_LLM_CHANNEL_PROTOCOLS:
        return explicit

    for model in models or []:
        if "/" not in model:
            continue
        prefix = canonicalize_llm_channel_protocol(model.split("/", 1)[0])
        if prefix in SUPPORTED_LLM_CHANNEL_PROTOCOLS:
            return prefix

    # Infer from channel name (e.g. "deepseek" -> deepseek, "gemini" -> gemini)
    if channel_name:
        name_protocol = canonicalize_llm_channel_protocol(channel_name)
        if name_protocol in SUPPORTED_LLM_CHANNEL_PROTOCOLS:
            return name_protocol

    if base_url:
        parsed = urlparse(base_url)
        if parsed.hostname in {"127.0.0.1", "localhost", "0.0.0.0"}:
            # Default to openai for local servers (vLLM, LM Studio, LocalAI, etc.).
            # Ollama users should set PROTOCOL=ollama explicitly or name the channel "ollama".
            return "openai"
        return "openai"

    return ""


def channel_allows_empty_api_key(protocol: Optional[str], base_url: Optional[str]) -> bool:
    """Return True when a channel can run without an API key."""
    resolved_protocol = resolve_llm_channel_protocol(protocol, base_url=base_url)
    if resolved_protocol == "ollama":
        return True
    parsed = urlparse(base_url or "")
    return parsed.hostname in {"127.0.0.1", "localhost", "0.0.0.0"}


def normalize_llm_channel_model(model: str, protocol: Optional[str], base_url: Optional[str] = None) -> str:
    """Attach a provider prefix when the model omits it."""
    normalized_model = model.strip()
    if not normalized_model:
        return normalized_model

    resolved_protocol = resolve_llm_channel_protocol(protocol, base_url=base_url, models=[normalized_model])

    if "/" in normalized_model:
        # The model already has a slash, e.g. 'deepseek-ai/DeepSeek-V3'.
        # Check if the prefix is a known LiteLLM provider; if so, keep it.
        # Otherwise (e.g. HuggingFace-style IDs on SiliconFlow), prepend
        # the resolved protocol so LiteLLM routes via the correct handler.
        raw_prefix, remainder = normalized_model.split("/", 1)
        prefix = raw_prefix.lower()
        canonical_prefix = canonicalize_llm_channel_protocol(prefix)
        known_providers = _MANAGED_LITELLM_KEY_PROVIDERS | set(SUPPORTED_LLM_CHANNEL_PROTOCOLS) | {
            "cohere", "huggingface", "bedrock", "sagemaker", "azure",
            "replicate", "together_ai", "palm", "text-completion-openai",
            "command-r", "groq", "cerebras", "fireworks_ai", "friendliai",
        }
        if prefix in known_providers:
            return normalized_model
        if canonical_prefix in known_providers:
            return f"{canonical_prefix}/{remainder}"
        # Not a real provider prefix — add one so LiteLLM routes correctly.
        if resolved_protocol:
            return f"{resolved_protocol}/{normalized_model}"
        return normalized_model

    if not resolved_protocol:
        return normalized_model
    return f"{resolved_protocol}/{normalized_model}"


def get_configured_llm_models(model_list: List[Dict[str, Any]]) -> List[str]:
    """Return non-legacy model names declared in Router model_list order.

    Uses the top-level ``model_name`` (the routing alias that users set in
    LITELLM_MODEL) rather than ``litellm_params.model`` (the wire-level
    model identifier).  For channel-built entries both are identical, but
    YAML configs may define a friendly alias that differs from the
    underlying provider/model path.
    """
    models: List[str] = []
    seen: set = set()
    for entry in model_list or []:
        # Prefer top-level model_name (router routing key); fall back to
        # litellm_params.model for entries that omit it.
        name = str(entry.get("model_name") or "").strip()
        if not name:
            params = entry.get("litellm_params", {}) or {}
            name = str(params.get("model") or "").strip()
        if not name or name.startswith("__legacy_") or name in seen:
            continue
        seen.add(name)
        models.append(name)
    return models


def get_llm_model_identity_forms(model: str) -> set[str]:
    """Return canonical comparison forms for one model ID.

    A channel may expose ``glm-4`` while protocol normalization stores
    ``openai/glm-4``.  Route/save validation should treat these as the same
    model identity when the suffix matches.
    """
    normalized_model = (model or "").strip()
    if not normalized_model:
        return set()
    forms = {normalized_model}
    if "/" in normalized_model:
        suffix = normalized_model.split("/", 1)[1].strip()
        if suffix:
            forms.add(suffix)
    else:
        forms.add(f"openai/{normalized_model}")
    return forms


def _dedupe_declared_models(models: Optional[List[str]]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for model in models or []:
        candidate = str(model or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def resolve_configured_llm_model_alias(
    model: str,
    configured_models: Optional[set[str]] = None,
) -> str:
    """Map a selected model to the configured router alias when equivalent."""
    normalized_model = (model or "").strip()
    if not normalized_model:
        return ""
    if not configured_models:
        return normalized_model

    candidate_forms = get_llm_model_identity_forms(normalized_model)
    matches = [
        configured_model
        for configured_model in configured_models
        if get_llm_model_identity_forms(configured_model) & candidate_forms
    ]
    if len(matches) == 1:
        return matches[0]
    if normalized_model in configured_models:
        return normalized_model
    return normalized_model


def _resolve_router_runtime_model(
    model: str,
    configured_models: set[str],
) -> str:
    candidate = str(model or "").strip()
    if not candidate or not configured_models:
        return ""
    resolved = resolve_configured_llm_model_alias(
        candidate,
        configured_models=configured_models,
    )
    if resolved in configured_models:
        return resolved
    return ""


def _has_runtime_source_for_model(config: "Config", model: str) -> bool:
    """Return True when the runtime can directly execute the model."""
    if not model or _uses_direct_env_provider(model):
        return True
    provider = _get_litellm_provider(model)
    if provider in {"gemini", "vertex_ai"}:
        return any(k and len(k) >= 8 for k in (getattr(config, "gemini_api_keys", []) or []))
    if provider == "anthropic":
        return any(k and len(k) >= 8 for k in (getattr(config, "anthropic_api_keys", []) or []))
    if provider == "deepseek":
        return any(k and len(k) >= 8 for k in (getattr(config, "deepseek_api_keys", []) or []))
    if provider == "openai":
        return any(k and len(k) >= 8 for k in (getattr(config, "openai_api_keys", []) or []))
    return False


def resolve_litellm_model_selection(
    config: "Config",
    *,
    requested_model: Optional[str] = None,
    fallback_models: Optional[List[str]] = None,
    allow_default_fallback: bool = False,
) -> LLMModelSelection:
    """Resolve the safest usable runtime model without mutating configured values."""
    available_models = _dedupe_declared_models(
        get_configured_llm_models(getattr(config, "llm_model_list", []) or [])
    )
    available_model_set = set(available_models)
    requested = str(
        getattr(config, "litellm_model", "")
        if requested_model is None
        else requested_model
    ).strip()

    if requested and _uses_direct_env_provider(requested):
        return LLMModelSelection(
            requested_model=requested,
            resolved_model=requested,
            available_models=available_models,
            resolution="direct",
        )

    resolved_requested = _resolve_router_runtime_model(requested, available_model_set)
    if resolved_requested:
        return LLMModelSelection(
            requested_model=requested,
            resolved_model=resolved_requested,
            available_models=available_models,
            resolution="configured" if resolved_requested == requested else "normalized",
        )
    if requested and not available_models and _has_runtime_source_for_model(config, requested):
        return LLMModelSelection(
            requested_model=requested,
            resolved_model=requested,
            available_models=available_models,
            resolution="configured",
        )

    fallback_candidates = fallback_models
    if fallback_candidates is None:
        fallback_candidates = list(getattr(config, "litellm_fallback_models", []) or [])

    for fallback_model in fallback_candidates:
        candidate = str(fallback_model or "").strip()
        if not candidate:
            continue
        if _uses_direct_env_provider(candidate):
            return LLMModelSelection(
                requested_model=requested,
                resolved_model=candidate,
                available_models=available_models,
                resolution="fallback",
            )
        resolved_fallback = _resolve_router_runtime_model(candidate, available_model_set)
        if resolved_fallback:
            return LLMModelSelection(
                requested_model=requested,
                resolved_model=resolved_fallback,
                available_models=available_models,
                resolution="fallback",
            )
        if not available_models and _has_runtime_source_for_model(config, candidate):
            return LLMModelSelection(
                requested_model=requested,
                resolved_model=candidate,
                available_models=available_models,
                resolution="fallback",
            )

    if allow_default_fallback and not requested and available_models:
        return LLMModelSelection(
            requested_model=requested,
            resolved_model=available_models[0],
            available_models=available_models,
            resolution="fallback",
        )

    return LLMModelSelection(
        requested_model=requested,
        resolved_model="",
        available_models=available_models,
        resolution="empty" if not requested else "unavailable",
    )


def get_effective_litellm_model(
    config: "Config",
    *,
    allow_default_fallback: bool = False,
) -> str:
    """Return the runtime-safe primary LiteLLM model."""
    return resolve_litellm_model_selection(
        config,
        allow_default_fallback=allow_default_fallback,
    ).resolved_model


def get_effective_litellm_models_to_try(
    config: "Config",
    *,
    allow_default_fallback: bool = False,
) -> List[str]:
    """Return primary + configured fallbacks in runtime try-order."""
    selection = resolve_litellm_model_selection(
        config,
        allow_default_fallback=allow_default_fallback,
    )
    if not selection.resolved_model:
        return []

    configured_model_set = set(selection.available_models)
    raw_models = [selection.resolved_model] + list(getattr(config, "litellm_fallback_models", []) or [])
    seen: set[str] = set()
    ordered: List[str] = []
    for raw_model in raw_models:
        candidate = str(raw_model or "").strip()
        if not candidate:
            continue
        runtime_model = candidate
        if not _uses_direct_env_provider(candidate):
            resolved = _resolve_router_runtime_model(candidate, configured_model_set)
            if resolved:
                runtime_model = resolved
        dedupe_key = runtime_model
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        ordered.append(runtime_model)
    return ordered


def resolve_unified_llm_temperature(model: str) -> float:
    """Compatibility adapter for runtime-owned temperature parsing."""
    from src.runtime.settings import resolve_unified_llm_temperature as resolve

    return resolve(model)


def _get_litellm_provider(model: str) -> str:
    """Extract the LiteLLM provider prefix from a model string."""
    if not model:
        return ""
    if "/" in model:
        return model.split("/", 1)[0]
    return "openai"


def _uses_direct_env_provider(model: str) -> bool:
    """Whether runtime handles the model via direct litellm env/provider resolution."""
    provider = _get_litellm_provider(model)
    return bool(provider) and provider not in _MANAGED_LITELLM_KEY_PROVIDERS


def normalize_agent_litellm_model(
    model: str,
    configured_models: Optional[set[str]] = None,
) -> str:
    """Normalize AGENT_LITELLM_MODEL while preserving configured router aliases."""
    normalized_model = resolve_configured_llm_model_alias(model, configured_models)
    if not normalized_model:
        return ""
    if "/" not in normalized_model:
        if configured_models and normalized_model in configured_models:
            return normalized_model
        return f"openai/{normalized_model}"
    return normalized_model


def get_effective_agent_primary_model(config: "Config") -> str:
    """Return the effective Agent primary model with fallback inheritance."""
    configured_router_models = set(
        get_configured_llm_models(getattr(config, "llm_model_list", []) or [])
    )
    configured_agent_model = str(getattr(config, "agent_litellm_model", "") or "").strip()
    if configured_agent_model:
        normalized_agent_model = normalize_agent_litellm_model(
            configured_agent_model,
            configured_models=configured_router_models,
        )
        return resolve_litellm_model_selection(
            config,
            requested_model=normalized_agent_model,
            allow_default_fallback=True,
        ).resolved_model
    return get_effective_litellm_model(config, allow_default_fallback=True)


def get_effective_agent_models_to_try(config: "Config") -> List[str]:
    """Return Agent model try-order: primary + global fallbacks (deduped)."""
    configured_router_models = set(
        get_configured_llm_models(getattr(config, "llm_model_list", []) or [])
    )
    raw_models = [get_effective_agent_primary_model(config)] + (
        getattr(config, "litellm_fallback_models", []) or []
    )
    seen = set()
    ordered_models: List[str] = []
    for model in raw_models:
        normalized_model = (model or "").strip()
        if not normalized_model:
            continue
        resolved_model = _resolve_router_runtime_model(
            normalized_model,
            configured_router_models,
        )
        dedupe_key = (
            resolved_model
            or normalize_agent_litellm_model(
                normalized_model,
                configured_models=configured_router_models,
            )
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        ordered_models.append(normalized_model)
    return ordered_models


def setup_env(override: bool = False):
    """Compatibility adapter for runtime-owned environment preparation."""
    from src.runtime.settings import setup_environment

    setup_environment(override=override)


@dataclass
class Config:
    """
    系统配置类 - 单例模式
    
    设计说明：
    - 使用 dataclass 简化配置属性定义
    - 所有配置项从环境变量读取，支持默认值
    - 类方法 get_instance() 实现单例访问
    """
    
    # === 自选股配置 ===
    stock_list: List[str] = field(default_factory=list)

    # === 飞书云文档配置 ===
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None
    feishu_folder_token: Optional[str] = None  # 目标文件夹 Token

    # === 数据源 API Token ===
    tushare_token: Optional[str] = None
    tickflow_api_key: Optional[str] = None
    fred_api_key: Optional[str] = None
    twelve_data_api_keys: List[str] = field(default_factory=list)
    twelve_data_api_key: Optional[str] = None
    alpaca_api_key_id: Optional[str] = None
    alpaca_api_secret_key: Optional[str] = None
    alpaca_data_feed: str = "iex"

    # === AI 分析配置 ===
    # LiteLLM unified model config (provider/model format, e.g. gemini/gemini-2.5-flash)
    litellm_model: str = ""  # Primary model; must include provider prefix when set explicitly
    litellm_fallback_models: List[str] = field(default_factory=list)  # Cross-model fallback list

    # Unified temperature for all LLM calls (LLM_TEMPERATURE); legacy per-provider temps are fallback only
    llm_temperature: float = 0.7
    home_quick_analysis_enabled: bool = True
    home_quick_analysis_temperature: float = 0.2
    home_quick_analysis_max_output_tokens: int = 4096
    home_analysis_log_full_prompt: bool = False

    # --- Multi-channel LLM config (new) ---
    # LITELLM_CONFIG: path to a standard litellm_config.yaml file (most powerful)
    litellm_config_path: Optional[str] = None
    # Internal metadata: which config layer actually produced llm_model_list
    llm_models_source: str = "legacy_env"
    # LLM_CHANNELS: list of channel dicts, each with name/base_url/api_keys/models
    llm_channels: List[Dict[str, Any]] = field(default_factory=list)
    # Pre-built LiteLLM Router model_list (populated from channels, YAML, or legacy keys)
    llm_model_list: List[Dict[str, Any]] = field(default_factory=list)

    # Multi-key support: each list is parsed from *_API_KEYS (comma-separated) with single-key fallback
    gemini_api_keys: List[str] = field(default_factory=list)
    anthropic_api_keys: List[str] = field(default_factory=list)
    openai_api_keys: List[str] = field(default_factory=list)
    deepseek_api_keys: List[str] = field(default_factory=list)

    # Legacy single-key fields (kept for backward compatibility; gemini_api_keys[0] when set)
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3-flash-preview"  # 主模型
    gemini_model_fallback: str = "gemini-2.5-flash"  # 备选模型
    gemini_temperature: float = 0.7  # 温度参数（0.0-2.0，控制输出随机性，默认0.7）

    # Gemini API 请求配置（防止 429 限流）
    gemini_request_delay: float = 2.0  # 请求间隔（秒）
    gemini_max_retries: int = 5  # 最大重试次数
    gemini_retry_delay: float = 5.0  # 重试基础延时（秒）

    # Anthropic Claude API（备选，当 Gemini 不可用时使用）
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"  # Claude model name
    anthropic_temperature: float = 0.7  # Anthropic temperature (0.0-1.0, default 0.7)
    anthropic_max_tokens: int = 8192  # Max tokens for Anthropic responses

    # OpenAI 兼容 API（备选，当 Gemini/Anthropic 不可用时使用）
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None  # 如: https://api.openai.com/v1
    openai_model: str = "gpt-4o-mini"  # OpenAI 兼容模型名称
    openai_vision_model: Optional[str] = None  # Deprecated: use VISION_MODEL instead
    openai_temperature: float = 0.7  # OpenAI 温度参数（0.0-2.0，默认0.7）

    # === Vision 配置 ===
    # VISION_MODEL: litellm model string used for image understanding calls.
    # Fallback chain: VISION_MODEL → OPENAI_VISION_MODEL → gemini/gemini-2.0-flash
    vision_model: str = ""
    # VISION_PROVIDER_PRIORITY: comma-separated provider order for Vision fallback.
    vision_provider_priority: str = "gemini,anthropic,openai"

    # === 搜索引擎配置（支持多 Key 负载均衡）===
    bocha_api_keys: List[str] = field(default_factory=list)  # Bocha API Keys
    minimax_api_keys: List[str] = field(default_factory=list)  # MiniMax API Keys
    tavily_api_keys: List[str] = field(default_factory=list)  # Tavily API Keys
    brave_api_keys: List[str] = field(default_factory=list)  # Brave Search API Keys
    serpapi_keys: List[str] = field(default_factory=list)  # SerpAPI Keys
    gnews_api_keys: List[str] = field(default_factory=list)  # GNews API Keys
    finnhub_api_keys: List[str] = field(default_factory=list)  # Finnhub API Keys
    fmp_api_keys: List[str] = field(default_factory=list)  # Financial Modeling Prep API Keys
    searxng_base_urls: List[str] = field(default_factory=list)  # SearXNG instance URLs (self-hosted, no quota)
    searxng_public_instances_enabled: bool = True  # Auto-discover public SearXNG instances when base URLs are absent

    # === Social Sentiment (US stocks only, api.adanos.org) ===
    social_sentiment_api_key: Optional[str] = None
    social_sentiment_api_url: str = "https://api.adanos.org"

    # === 新闻与分析筛选配置 ===
    news_max_age_days: int = 3   # 新闻最大时效（天）
    news_strategy_profile: str = "short"  # 新闻窗口策略档位：ultra_short/short/medium/long
    bias_threshold: float = 5.0  # 乖离率阈值（%），超过此值提示不追高

    # === Agent 模式配置 ===
    agent_litellm_model: str = ""  # Optional Agent-only primary model; empty inherits LITELLM_MODEL
    agent_mode: bool = False
    _agent_mode_explicit: bool = False  # True when AGENT_MODE was explicitly set in env
    agent_max_steps: int = 10
    agent_skills: List[str] = field(default_factory=list)
    agent_skill_dir: Optional[str] = None
    agent_nl_routing: bool = False  # Enable natural language routing in bot dispatcher
    agent_arch: str = "single"     # Agent architecture: 'single' (legacy) or 'multi' (orchestrator)
    agent_orchestrator_mode: str = "standard"  # Orchestrator mode: quick/standard/full/specialist
    agent_orchestrator_timeout_s: int = 600  # Cooperative timeout budget for the whole multi-agent pipeline
    agent_risk_override: bool = True  # Allow risk agent to veto buy signals
    agent_deep_research_budget: int = 30000  # Max token budget for deep research
    agent_deep_research_timeout: int = 180  # Max seconds for /research command before returning timeout
    agent_memory_enabled: bool = False  # Enable memory & calibration system
    agent_skill_autoweight: bool = True  # Auto-weight skills by backtest performance
    agent_skill_routing: str = "auto"  # Skill routing: 'auto' (regime-based) or 'manual'
    agent_event_monitor_enabled: bool = False  # Enable periodic event-driven alert checks in schedule mode
    agent_event_monitor_interval_minutes: int = 5  # Polling interval for event monitor background checks
    agent_event_alert_rules_json: str = ""  # JSON array of serialized EventMonitor rules

    # === 通知配置（可同时配置多个，全部推送）===
    
    # 企业微信 Webhook
    wechat_webhook_url: Optional[str] = None
    
    # 飞书 Webhook
    feishu_webhook_url: Optional[str] = None
    
    # Telegram 配置（需要同时配置 Bot Token 和 Chat ID）
    telegram_bot_token: Optional[str] = None  # Bot Token（@BotFather 获取）
    telegram_chat_id: Optional[str] = None  # Chat ID
    telegram_message_thread_id: Optional[str] = None  # Topic ID (Message Thread ID) for groups
    
    # 邮件配置（只需邮箱和授权码，SMTP 自动识别）
    email_sender: Optional[str] = None  # 发件人邮箱
    email_sender_name: str = "WolfyStock股票分析助手"  # 发件人显示名称
    email_password: Optional[str] = None  # 邮箱密码/授权码
    email_receivers: List[str] = field(default_factory=list)  # 收件人列表（留空则发给自己）

    # Stock-to-email group routing (Issue #268): STOCK_GROUP_N + EMAIL_GROUP_N
    # When configured, each group's report is sent to that group's emails only.
    stock_email_groups: List[Tuple[List[str], List[str]]] = field(default_factory=list)

    # Pushover 配置（手机/桌面推送通知）
    pushover_user_key: Optional[str] = None  # 用户 Key（https://pushover.net 获取）
    pushover_api_token: Optional[str] = None  # 应用 API Token
    
    # 自定义 Webhook（支持多个，逗号分隔）
    # 适用于：钉钉、Discord、Slack、自建服务等任意支持 POST JSON 的 Webhook
    custom_webhook_urls: List[str] = field(default_factory=list)
    custom_webhook_bearer_token: Optional[str] = None  # Bearer Token（用于需要认证的 Webhook）
    webhook_verify_ssl: bool = True  # Webhook HTTPS 证书校验，false 可支持自签名（有 MITM 风险）

    # Discord 通知配置
    discord_bot_token: Optional[str] = None  # Discord Bot Token
    discord_main_channel_id: Optional[str] = None  # Discord 主频道 ID
    discord_webhook_url: Optional[str] = None  # Discord Webhook URL

    # Slack 通知配置
    slack_webhook_url: Optional[str] = None  # Slack Incoming Webhook URL
    slack_bot_token: Optional[str] = None  # Slack Bot Token (xoxb-...)
    slack_channel_id: Optional[str] = None  # Slack 频道 ID (Bot 模式必填)

    # AstrBot 通知配置
    astrbot_token: Optional[str] = None
    astrbot_url: Optional[str] = None

    # 单股推送模式：每分析完一只股票立即推送，而不是汇总后推送
    single_stock_notify: bool = False

    # 报告类型：simple(精简) 或 full(完整)
    report_type: str = "simple"
    report_language: str = "zh"

    # 仅分析结果摘要：true 时只推送汇总，不含个股详情（Issue #262）
    report_summary_only: bool = False

    # Report Engine P0: Jinja2 renderer and integrity checks
    report_templates_dir: str = "templates"  # Template directory (relative to project root)
    report_renderer_enabled: bool = False  # Enable Jinja2 rendering (default off for zero regression)
    report_integrity_enabled: bool = True  # Content integrity validation after LLM output
    report_integrity_retry: int = 1  # Retry count when mandatory fields missing (0 = placeholder only)
    report_history_compare_n: int = 0  # History comparison count (0 = disabled)

    # PushPlus 推送配置
    pushplus_token: Optional[str] = None  # PushPlus Token
    pushplus_topic: Optional[str] = None  # PushPlus 群组编码（一对多推送）

    # Server酱3 推送配置
    serverchan3_sendkey: Optional[str] = None  # Server酱3 SendKey

    # 分析间隔时间（秒）- 用于避免API限流
    analysis_delay: float = 0.0  # 个股分析与大盘分析之间的延迟

    # Merge stock + market report into one notification (Issue #190)
    merge_email_notification: bool = False

    # 消息长度限制（字节）- 超长自动分批发送
    feishu_max_bytes: int = 20000  # 飞书限制约 20KB，默认 20000 字节
    wechat_max_bytes: int = 4000   # 企业微信限制 4096 字节，默认 4000 字节
    discord_max_words: int = 2000  # Discord 限制 2000 字，默认 2000 字
    wechat_msg_type: str = "markdown"  # 企业微信消息类型，默认 markdown 类型

    # Markdown 转图片（Issue #289）：对不支持 Markdown 的渠道以图片发送
    markdown_to_image_channels: List[str] = field(default_factory=list)  # 逗号分隔：telegram,wechat,custom,email
    markdown_to_image_max_chars: int = 15000  # 超过此长度不转换，避免超大图片
    md2img_engine: str = "wkhtmltoimage"  # wkhtmltoimage | markdown-to-file (Issue #455, better emoji support)

    # 实时行情预取（Issue #455）：设为 false 可禁用，避免 efinance/akshare_em 全市场拉取
    prefetch_realtime_quotes: bool = True

    # === 数据库配置 ===
    database_path: str = "./data/stock_analysis.db"
    postgres_phase_a_url: Optional[str] = None
    postgres_phase_a_apply_schema: bool = True
    admin_logs_retention_days: int = 90
    admin_logs_min_retention_days: int = 7
    admin_logs_storage_soft_limit_mb: int = 512
    admin_logs_storage_hard_limit_mb: int = 1024
    admin_logs_cleanup_batch_size: int = 1000
    admin_logs_auto_cleanup_enabled: bool = True
    admin_logs_warning_threshold_count: int = 50000
    admin_logs_critical_threshold_count: int = 100000
    admin_logs_warning_threshold_storage_bytes: Optional[int] = None
    enable_phase_f_trades_list_comparison: bool = False
    phase_f_trades_list_comparison_account_ids: List[int] = field(default_factory=list)
    enable_phase_f_cash_ledger_comparison: bool = False
    phase_f_cash_ledger_comparison_account_ids: List[int] = field(default_factory=list)
    enable_phase_f_corporate_actions_comparison: bool = False
    phase_f_corporate_actions_comparison_account_ids: List[int] = field(default_factory=list)

    # 是否保存分析上下文快照（用于历史回溯）
    save_context_snapshot: bool = True

    # === 回测配置 ===
    backtest_enabled: bool = True
    backtest_eval_window_days: int = 10
    backtest_min_age_days: int = 14
    backtest_engine_version: str = "v1"
    backtest_neutral_band_pct: float = 2.0

    # === Optional DuckDB quant analytics accelerator ===
    quant_engine: str = "python"
    duckdb_database_path: str = "data/quant/wolfystock.duckdb"
    quant_parquet_root: str = "data/quant/parquet"
    quant_duckdb_enabled: bool = False
    quant_max_benchmark_symbols: int = 5000
    
    # === 日志配置 ===
    log_dir: str = "./logs"  # 日志文件目录
    log_level: str = "INFO"  # 日志级别
    
    # === 系统配置 ===
    max_workers: int = 3  # 低并发防封禁
    debug: bool = False
    http_proxy: Optional[str] = None  # HTTP 代理 (例如: http://127.0.0.1:10809)
    https_proxy: Optional[str] = None # HTTPS 代理
    
    # === 定时任务配置 ===
    schedule_enabled: bool = False            # 是否启用定时任务
    schedule_time: str = "18:00"              # 每日推送时间（HH:MM 格式）
    schedule_run_immediately: bool = True     # 启动时是否立即执行一次
    scanner_profile: str = "cn_preopen_v1"    # 市场扫描默认 profile
    scanner_local_universe_path: str = "./data/scanner_cn_universe_cache.csv"  # Scanner 本地 universe 缓存路径
    scanner_ai_enabled: bool = False    # 是否启用 Scanner AI 二次解释层
    scanner_ai_top_n: int = 3           # 仅对前 N 名候选生成 AI 解读，控制延迟与成本
    scanner_schedule_enabled: bool = False    # 是否启用 Scanner 定时任务
    scanner_schedule_time: str = "08:40"      # Scanner 盘前执行时间（HH:MM）
    scanner_schedule_run_immediately: bool = False  # 启动时是否立即执行一次 Scanner
    scanner_notification_enabled: bool = True  # Scanner 定时运行后是否发送通知
    watchlist_score_refresh_enabled: bool = True
    watchlist_score_refresh_us_time: str = "08:45"
    watchlist_score_refresh_cn_time: str = "09:00"
    watchlist_score_refresh_hk_time: str = "09:00"
    watchlist_score_refresh_max_symbols: int = 250
    run_immediately: bool = True              # 启动时是否立即执行一次（非定时模式）
    market_review_enabled: bool = True        # 是否启用大盘复盘
    # 大盘复盘市场区域：cn(A股)、us(美股)、both(两者)，us 适合仅关注美股的用户
    market_review_region: str = "cn"
    # 交易日检查：默认启用，非交易日跳过执行；设为 false 或 --force-run 可强制执行（Issue #373）
    trading_day_check_enabled: bool = True

    # === 实时行情增强数据配置 ===
    # 实时行情开关（关闭后使用历史收盘价进行分析）
    enable_realtime_quote: bool = True
    # 盘中实时技术面：启用时用实时价计算 MA/多头排列（Issue #234）；关闭则用昨日收盘
    enable_realtime_technical_indicators: bool = True
    # 筹码分布开关（该接口不稳定，云端部署建议关闭）
    enable_chip_distribution: bool = True
    # 东财接口补丁开关
    enable_eastmoney_patch: bool = False
    # 实时行情数据源优先级（逗号分隔）
    # 推荐顺序：tencent > akshare_sina > efinance > akshare_em > tushare
    # - tencent: 腾讯财经，有量比/换手率/市盈率等，单股查询稳定（推荐）
    # - akshare_sina: 新浪财经，基本行情稳定，但无量比
    # - efinance/akshare_em: 东财全量接口，数据最全但容易被封
    # - tushare: Tushare Pro，需要2000积分，数据全面（付费用户可优先使用）
    realtime_source_priority: str = "tencent,akshare_sina,efinance,akshare_em"
    # 实时行情缓存时间（秒）
    realtime_cache_ttl: int = 600
    # MarketCache remote mirror backend: disabled by default, redis is persist-only.
    market_cache_remote_backend: str = "disabled"
    market_cache_remote_url: Optional[str] = None
    market_cache_remote_timeout_seconds: float = 0.2
    market_cache_remote_queue_size: int = 256
    # 熔断器冷却时间（秒）
    circuit_breaker_cooldown: int = 300

    # === 基本面聚合开关与降级保护 ===
    # 全局总开关；关闭时返回 not_supported 并保持主流程无变化
    enable_fundamental_pipeline: bool = True
    # 基本面阶段总预算（秒）
    fundamental_stage_timeout_seconds: float = 1.5
    # 单能力源调用超时（秒）
    fundamental_fetch_timeout_seconds: float = 0.8
    # 单能力失败重试次数（已包含首次）
    fundamental_retry_max: int = 1
    # 基本面上下文短 TTL（秒）
    fundamental_cache_ttl_seconds: int = 120
    # 基本面缓存最大条目数（避免长时间运行内存增长）
    fundamental_cache_max_entries: int = 256

    # === Portfolio PR2: import/risk/fx settings ===
    portfolio_risk_concentration_alert_pct: float = 35.0
    portfolio_risk_drawdown_alert_pct: float = 15.0
    portfolio_risk_stop_loss_alert_pct: float = 10.0
    portfolio_risk_stop_loss_near_ratio: float = 0.8
    portfolio_risk_lookback_days: int = 180
    portfolio_fx_update_enabled: bool = True

    # Discord 机器人状态
    discord_bot_status: str = "A股智能分析 | /help"

    # === 流控配置（防封禁关键参数）===
    # Akshare 请求间隔范围（秒）
    akshare_sleep_min: float = 2.0
    akshare_sleep_max: float = 5.0
    
    # Tushare 每分钟最大请求数（免费配额）
    tushare_rate_limit_per_minute: int = 80
    
    # 重试配置
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0
    
    # === WebUI 配置 ===
    webui_enabled: bool = False
    webui_host: str = "127.0.0.1"
    webui_port: int = 8000
    
    # === 机器人配置 ===
    bot_enabled: bool = True              # 是否启用机器人功能
    bot_command_prefix: str = "/"         # 命令前缀
    bot_rate_limit_requests: int = 10     # 频率限制：窗口内最大请求数
    bot_rate_limit_window: int = 60       # 频率限制：窗口时间（秒）
    bot_admin_users: List[str] = field(default_factory=list)  # 管理员用户 ID 列表
    
    # 飞书机器人（事件订阅）- 已有 feishu_app_id, feishu_app_secret
    feishu_verification_token: Optional[str] = None  # 事件订阅验证 Token
    feishu_encrypt_key: Optional[str] = None         # 消息加密密钥（可选）
    feishu_stream_enabled: bool = False              # 是否启用 Stream 长连接模式（无需公网IP）
    
    # 钉钉机器人
    dingtalk_app_key: Optional[str] = None      # 应用 AppKey
    dingtalk_app_secret: Optional[str] = None   # 应用 AppSecret
    dingtalk_stream_enabled: bool = False       # 是否启用 Stream 模式（无需公网IP）
    
    # 企业微信机器人（回调模式）
    wecom_corpid: Optional[str] = None              # 企业 ID
    wecom_token: Optional[str] = None               # 回调 Token
    wecom_encoding_aes_key: Optional[str] = None    # 消息加解密密钥
    wecom_agent_id: Optional[str] = None            # 应用 AgentId
    
    # Telegram 机器人 - 已有 telegram_bot_token, telegram_chat_id
    telegram_webhook_secret: Optional[str] = None   # Webhook 密钥

    # === 配置校验模式 ===
    # CONFIG_VALIDATE_MODE=warn (default): log all issues but always continue startup
    # CONFIG_VALIDATE_MODE=strict: exit(1) when any "error" severity issue is found
    config_validate_mode: str = "warn"

    # --- Post-init validation ---------------------------------------------------
    _VALID_AGENT_ARCH = {"single", "multi"}
    _VALID_ORCHESTRATOR_MODES = {"quick", "standard", "full", "specialist"}
    _VALID_SKILL_ROUTING = {"auto", "manual"}
    _VALID_MARKET_CACHE_REMOTE_BACKENDS = {"disabled", "redis"}

    def __post_init__(self) -> None:
        _log = logging.getLogger(__name__)
        if self.agent_arch not in self._VALID_AGENT_ARCH:
            _log.warning(
                "Invalid AGENT_ARCH=%r, falling back to 'single'. Valid: %s",
                self.agent_arch, self._VALID_AGENT_ARCH,
            )
            object.__setattr__(self, "agent_arch", "single")
        if self.agent_orchestrator_mode in {"strategy", "skill"}:
            _log.info(
                "AGENT_ORCHESTRATOR_MODE=%s is deprecated; normalizing to 'specialist'",
                self.agent_orchestrator_mode,
            )
            object.__setattr__(self, "agent_orchestrator_mode", "specialist")
        if self.agent_orchestrator_mode not in self._VALID_ORCHESTRATOR_MODES:
            _log.warning(
                "Invalid AGENT_ORCHESTRATOR_MODE=%r, falling back to 'standard'. Valid: %s",
                self.agent_orchestrator_mode, self._VALID_ORCHESTRATOR_MODES,
            )
            object.__setattr__(self, "agent_orchestrator_mode", "standard")
        if self.agent_skill_routing not in self._VALID_SKILL_ROUTING:
            _log.warning(
                "Invalid AGENT_SKILL_ROUTING=%r, falling back to 'auto'. Valid: %s",
                self.agent_skill_routing, self._VALID_SKILL_ROUTING,
            )
            object.__setattr__(self, "agent_skill_routing", "auto")
        market_cache_remote_backend = str(self.market_cache_remote_backend or "disabled").strip().lower()
        if market_cache_remote_backend not in self._VALID_MARKET_CACHE_REMOTE_BACKENDS:
            _log.warning(
                "Invalid MARKET_CACHE_REMOTE_BACKEND=%r, falling back to 'disabled'. Valid: %s",
                self.market_cache_remote_backend,
                self._VALID_MARKET_CACHE_REMOTE_BACKENDS,
            )
            market_cache_remote_backend = "disabled"
        object.__setattr__(self, "market_cache_remote_backend", market_cache_remote_backend)

    # 单例实例存储
    _instance: Optional['Config'] = None
    
    @classmethod
    def get_instance(cls) -> 'Config':
        """
        获取配置单例实例
        
        单例模式确保：
        1. 全局只有一个配置实例
        2. 配置只从环境变量加载一次
        3. 所有模块共享相同配置
        """
        if cls._instance is None:
            cls._instance = cls._load_from_env()
        return cls._instance
    
    @classmethod
    def _load_from_env(cls) -> 'Config':
        """Build the compatibility facade from the runtime settings snapshot."""
        from src.runtime.settings import RuntimeSettings

        return RuntimeSettings.load(config_type=cls).to_config(cls)

    @classmethod
    def _parse_environment(cls) -> 'Config':
        """Compatibility hook used only by the runtime settings owner."""
        from src.runtime.settings import parse_runtime_config

        return parse_runtime_config(cls)

    @property
    def runtime_settings(self):
        """Return the immutable snapshot that created this compatibility facade."""
        return getattr(self, "_runtime_settings_snapshot", None)
    
    @classmethod
    def _parse_litellm_yaml(cls, config_path: str) -> List[Dict[str, Any]]:
        from src.runtime.settings import parse_litellm_yaml

        return parse_litellm_yaml(cls, config_path)

    @classmethod
    def _parse_llm_channels(cls, channels_str: str) -> List[Dict[str, Any]]:
        from src.runtime.settings import parse_llm_channels

        return parse_llm_channels(cls, channels_str)

    @classmethod
    def _channels_to_model_list(cls, channels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        from src.runtime.settings import channels_to_model_list

        return channels_to_model_list(cls, channels)

    @classmethod
    def _legacy_keys_to_model_list(
        cls,
        gemini_keys: List[str],
        anthropic_keys: List[str],
        openai_keys: List[str],
        openai_base_url: Optional[str],
        deepseek_keys: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        from src.runtime.settings import legacy_keys_to_model_list

        return legacy_keys_to_model_list(
            cls,
            gemini_keys,
            anthropic_keys,
            openai_keys,
            openai_base_url,
            deepseek_keys,
        )

    @classmethod
    def _parse_stock_email_groups(cls) -> List[Tuple[List[str], List[str]]]:
        from src.runtime.settings import parse_stock_email_groups

        return parse_stock_email_groups(cls)

    @classmethod
    def _parse_report_type(cls, value: str) -> str:
        from src.runtime.settings import parse_report_type

        return parse_report_type(cls, value)

    @classmethod
    def _get_env_file_value(cls, key: str) -> Optional[str]:
        """Compatibility adapter for runtime-owned env-file reads."""
        from src.runtime.settings import get_env_file_value

        return get_env_file_value(key)

    @classmethod
    def _resolve_report_language_env_value(
        cls,
        preexisting_env_value: Optional[str],
    ) -> str:
        """Compatibility adapter for runtime-owned precedence resolution."""
        from src.runtime.settings import resolve_report_language_env_value

        return resolve_report_language_env_value(preexisting_env_value)

    @classmethod
    def _parse_report_language(cls, value: Optional[str]) -> str:
        from src.runtime.settings import parse_report_language

        return parse_report_language(cls, value)

    @classmethod
    def _parse_news_strategy_profile(cls, value: Optional[str]) -> str:
        from src.runtime.settings import parse_news_strategy_profile

        return parse_news_strategy_profile(cls, value)

    def get_effective_news_window_days(self) -> int:
        """Return effective news window days after profile + max-age merge."""
        return resolve_news_window_days(
            news_max_age_days=self.news_max_age_days,
            news_strategy_profile=self.news_strategy_profile,
        )

    @classmethod
    def _parse_market_review_region(cls, value: str) -> str:
        from src.runtime.settings import parse_market_review_region

        return parse_market_review_region(cls, value)

    @classmethod
    def _parse_md2img_engine(cls, value: str) -> str:
        from src.runtime.settings import parse_md2img_engine

        return parse_md2img_engine(cls, value)

    @classmethod
    def _resolve_realtime_source_priority(cls) -> str:
        from src.runtime.settings import resolve_realtime_source_priority

        return resolve_realtime_source_priority(cls)

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（主要用于测试）"""
        cls._instance = None

    def has_searxng_enabled(self) -> bool:
        """Whether SearXNG fallback is enabled via self-hosted or public mode."""
        return bool(self.searxng_base_urls) or bool(self.searxng_public_instances_enabled)

    def has_search_capability_enabled(self) -> bool:
        """Whether any search provider is configured or SearXNG fallback is enabled."""
        return bool(
            self.bocha_api_keys
            or self.minimax_api_keys
            or self.tavily_api_keys
            or self.brave_api_keys
            or self.serpapi_keys
            or self.has_searxng_enabled()
        )

    def is_agent_available(self) -> bool:
        """Check whether agent capabilities are usable.

        Decision table:

        +-----------------------+----------------------------------+---------+
        | AGENT_MODE env        | effective Agent primary model set| Result  |
        +-----------------------+----------------------------------+---------+
        | ``true``              | any                              | True    |
        | ``false`` (explicit)  | any                              | False   |
        | not set (default)     | yes                              | True    |
        | not set (default)     | no                               | False   |
        +-----------------------+----------------------------------+---------+

        This keeps backward compatibility: users who never touch
        ``AGENT_MODE`` get agent features automatically once they configure an
        Agent-effective model, while ``AGENT_MODE=false`` acts as an explicit
        kill-switch.
        """
        # Explicit AGENT_MODE takes full precedence
        if self._agent_mode_explicit:
            return self.agent_mode
        configured_router_models = set(get_configured_llm_models(self.llm_model_list))
        configured_agent_model = normalize_agent_litellm_model(
            getattr(self, "agent_litellm_model", ""),
            configured_models=configured_router_models,
        )
        if configured_agent_model:
            if _resolve_router_runtime_model(configured_agent_model, configured_router_models):
                return True
            # Keep backward compatibility for direct env style Agent model config:
            # expose Agent surfaces when an explicit Agent model is set, even if
            # runtime readiness is still invalid and will be surfaced separately
            # by config validation/provider health.
            if not configured_router_models:
                return True
        # Auto-detect inherited primary only when runtime-safe resolution exists.
        return bool(get_effective_agent_primary_model(self))

    def refresh_stock_list(self) -> None:
        """
        热读取 STOCK_LIST 环境变量并更新配置中的自选股列表
        
        支持两种配置方式：
        1. .env 文件（本地开发、定时任务模式） - 修改后下次执行自动生效
        2. 系统环境变量（GitHub Actions、Docker） - 启动时固定，运行中不变
        """
        # 优先从 .env 文件读取最新配置，这样即使在容器环境中修改了 .env 文件，
        # 也能获取到最新的股票列表配置
        env_file = os.getenv("ENV_FILE")
        env_path = Path(env_file) if env_file else (Path(__file__).parent.parent / '.env')
        stock_list_str = ''
        if env_path.exists():
            # 直接从 .env 文件读取最新的配置
            env_values = read_dotenv_values(env_path)
            stock_list_str = (env_values.get('STOCK_LIST') or '').strip()

        # 如果 .env 文件不存在或未配置，才尝试从系统环境变量读取
        if not stock_list_str:
            stock_list_str = os.getenv('STOCK_LIST', '')

        stock_list = [
            (c or "").strip().upper()
            for c in stock_list_str.split(',')
            if (c or "").strip()
        ]

        if not stock_list:
            stock_list = ['000001']

        self.stock_list = stock_list
    
    def validate_structured(self) -> List[ConfigIssue]:
        """Return structured validation issues with severity levels.

        Covers all three LLM configuration tiers introduced by PR #494:
        - LITELLM_CONFIG (YAML)
        - LLM_CHANNELS (env)
        - Legacy per-provider keys

        Returns:
            List of ConfigIssue objects, each carrying a severity
            ("error" | "warning" | "info"), a human-readable message, and the
            primary environment variable / field name it relates to.
        """
        issues: List[ConfigIssue] = []

        # --- Stock list ---
        if not self.stock_list:
            issues.append(ConfigIssue(
                severity="error",
                message="未配置自选股列表 (STOCK_LIST)",
                field="STOCK_LIST",
            ))

        # --- Data sources (informational only) ---
        if not self.tushare_token:
            issues.append(ConfigIssue(
                severity="info",
                message="未配置 Tushare Token，将使用其他数据源",
                field="TUSHARE_TOKEN",
            ))

        # --- LLM availability ---
        # llm_model_list is populated for YAML / channels / managed legacy keys.
        # Other LiteLLM-native providers (for example cohere/*) run through the
        # direct litellm env path and therefore do not populate llm_model_list.
        has_direct_env_model = bool(self.litellm_model) and _uses_direct_env_provider(self.litellm_model)
        if not self.llm_model_list and not has_direct_env_model:
            issues.append(ConfigIssue(
                severity="error",
                message=(
                    "未配置任何 LLM（LITELLM_CONFIG / LLM_CHANNELS / *_API_KEY），"
                    "AI 分析功能将不可用"
                ),
                field="LITELLM_CONFIG",
            ))
        elif not self.litellm_model:
            issues.append(ConfigIssue(
                severity="info",
                message=(
                    "LITELLM_MODEL 未配置，将自动从可用 API Key 推断模型。"
                    "建议尽早配置 LITELLM_MODEL（格式如 gemini/gemini-2.5-flash）"
                ),
                field="LITELLM_MODEL",
            ))

        available_router_models = get_configured_llm_models(self.llm_model_list)
        available_router_model_set = set(available_router_models)

        def _is_configured_router_model(model: str) -> bool:
            if not model:
                return False
            return (
                resolve_configured_llm_model_alias(
                    model,
                    configured_models=available_router_model_set,
                )
                in available_router_model_set
            )

        def _has_local_runtime_source_for_model(model: str) -> bool:
            if not model or _uses_direct_env_provider(model):
                return True
            provider = _get_litellm_provider(model)
            if provider in {"gemini", "vertex_ai"}:
                return any(k and len(k) >= 8 for k in (self.gemini_api_keys or []))
            if provider == "anthropic":
                return any(k and len(k) >= 8 for k in (self.anthropic_api_keys or []))
            if provider == "deepseek":
                return any(k and len(k) >= 8 for k in (self.deepseek_api_keys or []))
            if provider == "openai":
                return any(k and len(k) >= 8 for k in (self.openai_api_keys or []))
            return False

        configured_agent_primary_model = bool((self.agent_litellm_model or "").strip())
        effective_agent_primary_model = get_effective_agent_primary_model(self)
        requested_agent_model = normalize_agent_litellm_model(
            getattr(self, "agent_litellm_model", ""),
            configured_models=available_router_model_set,
        ) if configured_agent_primary_model else ""
        primary_model_selection = resolve_litellm_model_selection(
            self,
            allow_default_fallback=True,
        )
        agent_model_selection = resolve_litellm_model_selection(
            self,
            requested_model=requested_agent_model if configured_agent_primary_model else effective_agent_primary_model,
            allow_default_fallback=True,
        )

        if available_router_model_set:
            if (
                self.litellm_model
                and not _uses_direct_env_provider(self.litellm_model)
            ):
                if primary_model_selection.resolution == "fallback" and primary_model_selection.resolved_model:
                    issues.append(ConfigIssue(
                        severity="warning",
                        message=(
                            f"LITELLM_MODEL 已配置为 {self.litellm_model}，"
                            f"当前渠道不可用，运行时将回退到 {primary_model_selection.resolved_model}。"
                            f" 当前可用模型：{', '.join(available_router_models[:6])}"
                        ),
                        field="LITELLM_MODEL",
                    ))
                elif not primary_model_selection.is_usable and not _is_configured_router_model(self.litellm_model):
                    issues.append(ConfigIssue(
                        severity="error",
                        message=(
                            f"LITELLM_MODEL 已配置为 {self.litellm_model}，"
                            "但当前渠道/配置文件中不存在该模型。"
                            f" 当前可用模型：{', '.join(available_router_models[:6])}"
                        ),
                        field="LITELLM_MODEL",
                    ))

            if (
                configured_agent_primary_model
            ):
                if agent_model_selection.resolution == "fallback" and agent_model_selection.resolved_model:
                    issues.append(ConfigIssue(
                        severity="warning",
                        message=(
                            f"AGENT_LITELLM_MODEL 已配置为 {self.agent_litellm_model}，"
                            f"当前渠道不可用，运行时将回退到 {agent_model_selection.resolved_model}。"
                            f" 当前可用模型：{', '.join(available_router_models[:6])}"
                        ),
                        field="AGENT_LITELLM_MODEL",
                    ))
                elif not agent_model_selection.is_usable and not _is_configured_router_model(requested_agent_model):
                    issues.append(ConfigIssue(
                        severity="error",
                        message=(
                            f"AGENT_LITELLM_MODEL 已配置为 {self.agent_litellm_model}，"
                            "但当前渠道/配置文件中不存在该模型。"
                            f" 当前可用模型：{', '.join(available_router_models[:6])}"
                        ),
                        field="AGENT_LITELLM_MODEL",
                    ))

            invalid_fallbacks = [
                model for model in (self.litellm_fallback_models or [])
                if model and not _is_configured_router_model(model)
                and not _uses_direct_env_provider(model)
            ]
            if invalid_fallbacks:
                issues.append(ConfigIssue(
                    severity="warning",
                    message=(
                        "LITELLM_FALLBACK_MODELS 中包含未在当前渠道声明的模型："
                        f"{', '.join(invalid_fallbacks[:3])}"
                    ),
                    field="LITELLM_FALLBACK_MODELS",
                ))

            if (
                self.vision_model
                and not _uses_direct_env_provider(self.vision_model)
                and not _is_configured_router_model(self.vision_model)
            ):
                issues.append(ConfigIssue(
                    severity="warning",
                    message=(
                        "VISION_MODEL 未出现在当前渠道声明中。"
                        f" 当前可用模型：{', '.join(available_router_models[:6])}"
                    ),
                    field="VISION_MODEL",
                ))
        elif (
            configured_agent_primary_model
            and requested_agent_model
            and not agent_model_selection.is_usable
            and not _has_local_runtime_source_for_model(requested_agent_model)
        ):
            issues.append(ConfigIssue(
                severity="error",
                message=(
                    "AGENT_LITELLM_MODEL 已配置，但未找到可用的运行时来源"
                    "（启用渠道或匹配的 API Key）。"
                ),
                field="AGENT_LITELLM_MODEL",
            ))

        # --- Search engine (informational only) ---
        if not self.has_search_capability_enabled():
            issues.append(ConfigIssue(
                severity="info",
                message="未配置搜索引擎能力 (Bocha/MiniMax/Tavily/Brave/SerpAPI/SearXNG)，新闻搜索功能将不可用",
                field="BOCHA_API_KEYS",
            ))

        # --- Notification channels ---
        has_notification = bool(
            self.wechat_webhook_url
            or self.feishu_webhook_url
            or (self.telegram_bot_token and self.telegram_chat_id)
            or (self.email_sender and self.email_password)
            or (self.pushover_user_key and self.pushover_api_token)
            or self.pushplus_token
            or self.serverchan3_sendkey
            or self.custom_webhook_urls
            or (self.discord_bot_token and self.discord_main_channel_id)
            or self.discord_webhook_url
            or self.slack_webhook_url
            or (self.slack_bot_token and self.slack_channel_id)
        )

        if not has_notification:
            issues.append(ConfigIssue(
                severity="warning",
                message="未配置通知渠道，将不发送推送通知",
                field="WECHAT_WEBHOOK_URL",
            ))

        # --- Deprecated field migration hints ---
        if os.getenv("OPENAI_VISION_MODEL"):
            issues.append(ConfigIssue(
                severity="info",
                message=(
                    "OPENAI_VISION_MODEL 已废弃，请改用 VISION_MODEL。"
                    "当前值已自动迁移，建议更新配置文件以消除此提示。"
                ),
                field="OPENAI_VISION_MODEL",
            ))

        # --- Vision key availability ---
        # Only warn when user explicitly set VISION_MODEL (or OPENAI_VISION_MODEL alias).
        # Skipped when vision_model is empty (Vision not intentionally configured).
        if self.vision_model:
            # Maps provider prefix → the corresponding key list tracked by Config.
            # vertex_ai shares gemini keys; other LiteLLM-native providers are not
            # in this map (their keys come from env vars, which we cannot inspect here).
            _VISION_KEY_MAP = {
                "gemini": self.gemini_api_keys,
                "vertex_ai": self.gemini_api_keys,
                "anthropic": self.anthropic_api_keys,
                "openai": self.openai_api_keys,
                "deepseek": self.deepseek_api_keys,
            }
            # Derive the primary model's provider prefix so that its key is also
            # checked even when the provider is absent from VISION_PROVIDER_PRIORITY.
            _primary_prefix = (
                self.vision_model.split("/")[0]
                if "/" in self.vision_model
                else "openai"
            )
            _priority_providers = [
                p.strip().lower()
                for p in self.vision_provider_priority.split(",")
                if p.strip()
            ]
            # Union: fallback providers + primary model's own provider
            _all_providers = {_primary_prefix} | set(_priority_providers)

            # Align with get_api_keys_for_model: keys must be non-empty and len >= 8
            _has_any_key = any(
                any(k and len(k) >= 8 for k in (_VISION_KEY_MAP.get(p) or []))
                for p in _all_providers
                if p in _VISION_KEY_MAP
            )
            if not _has_any_key:
                _checked = sorted(_all_providers & _VISION_KEY_MAP.keys())
                issues.append(ConfigIssue(
                    severity="warning",
                    message=(
                        "VISION_MODEL 已配置，但未找到可用的 Vision API Key "
                        f"（已检查：{', '.join(_checked)}）。"
                        "图片股票代码提取功能将不可用，请配置对应的 API Key。"
                    ),
                    field="VISION_MODEL",
                ))

        return issues

    def validate(self) -> List[str]:
        """Return validation messages as plain strings (backward-compatible).

        Internally delegates to validate_structured().  Callers that only need
        the human-readable strings can continue to use this method unchanged.

        Returns:
            List of message strings, one per ConfigIssue.
        """
        return [issue.message for issue in self.validate_structured()]
    
    def get_db_url(self) -> str:
        """
        获取 SQLAlchemy 数据库连接 URL
        
        自动创建数据库目录（如果不存在）
        """
        db_path = Path(self.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path.absolute()}"


# === 便捷的配置访问函数 ===
def get_config() -> Config:
    """获取全局配置实例的快捷方式"""
    return Config.get_instance()


# ============================================================
# Shared LLM helpers (used by both analyzer and agent/llm_adapter)
# ============================================================

def get_api_keys_for_model(model: str, config: Config) -> List[str]:
    """Return explicitly managed API keys for a litellm model (legacy path only).

    When llm_model_list is populated (channels / YAML), the Router handles key
    selection, so this function is not needed.  Kept for backward compat when
    no Router is built and a direct litellm.completion() call is needed.
    """
    provider = _get_litellm_provider(model)
    if provider in {"gemini", "vertex_ai"}:
        return [k for k in config.gemini_api_keys if k and len(k) >= 8]
    if provider == "anthropic":
        return [k for k in config.anthropic_api_keys if k and len(k) >= 8]
    if provider == "deepseek":
        return [k for k in config.deepseek_api_keys if k and len(k) >= 8]
    if provider == "openai":
        return [k for k in config.openai_api_keys if k and len(k) >= 8]
    # Other LiteLLM-native providers – API key resolved from env vars
    return []


def extra_litellm_params(model: str, config: Config) -> Dict[str, Any]:
    """Build extra litellm params for a model (legacy path only).

    When llm_model_list is populated, the Router already carries api_base
    and headers per-deployment, so this is not called.
    """
    params: Dict[str, Any] = {}
    # deepseek/ provider: litellm auto-resolves api_base, no manual override needed
    if model.startswith("deepseek/"):
        return params
    if model.startswith("openai/") or "/" not in model:
        if config.openai_base_url:
            params["api_base"] = config.openai_base_url
        if config.openai_base_url and "aihubmix.com" in config.openai_base_url:
            params["extra_headers"] = {"APP-Code": "GPIJ3886"}
    return params


if __name__ == "__main__":
    # 测试配置加载
    config = get_config()
    print("=== 配置加载测试 ===")
    print(f"自选股列表: {config.stock_list}")
    print(f"数据库路径: {config.database_path}")
    print(f"最大并发数: {config.max_workers}")
    print(f"调试模式: {config.debug}")
    
    # 验证配置
    warnings = config.validate()
    if warnings:
        print("\n配置验证结果:")
        for w in warnings:
            print(f"  - {w}")
