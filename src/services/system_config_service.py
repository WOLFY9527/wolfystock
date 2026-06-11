# -*- coding: utf-8 -*-
"""System configuration service for `.env` based settings."""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

import requests

from src.config import (
    SUPPORTED_LLM_CHANNEL_PROTOCOLS,
    Config,
    _get_litellm_provider,
    _uses_direct_env_provider,
    canonicalize_llm_channel_protocol,
    channel_allows_empty_api_key,
    get_configured_llm_models,
    normalize_agent_litellm_model,
    normalize_news_strategy_profile,
    normalize_llm_channel_model,
    parse_env_bool,
    resolve_configured_llm_model_alias,
    resolve_news_window_days,
    resolve_llm_channel_protocol,
    setup_env,
)
from src.core.config_manager import ConfigManager
from src.core.config_registry import (
    build_schema_response,
    get_category_definitions,
    get_field_definition,
    get_registered_field_keys,
)
from src.providers.validation import normalize_provider_name, validate_provider_connection
from src.services.execution_log_service import ExecutionLogService
from src.services.provider_circuit_observer import ProviderCircuitObserver
from src.services.system_config_provider_projection import (
    mask_provider_secret,
    project_provider_result_checks,
    project_provider_result_status,
    project_twelve_data_hk_diagnostic,
    provider_validation_suggestion,
    provider_validation_summary,
)
from src.storage import get_db
from src.utils.security import is_masked_secret, is_sensitive_key, mask_secret, sanitize_message, sanitize_url

logger = logging.getLogger(__name__)

FACTORY_RESET_CONFIRMATION_PHRASE = "FACTORY RESET"
_TEXT_CONTENT_BLOCK_TYPES = {"text", "output_text", "input_text"}
_REMOTE_VALIDATION_TIMEOUT_SECONDS = 5.0
_REMOTE_VALIDATION_USER_AGENT = "WolfyStock-Provider-Validation/1.0"
_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED_ENV = "WOLFYSTOCK_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED"
_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENV = "WOLFYSTOCK_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENABLED"
_PROVIDER_CIRCUIT_ADMIN_PROBE_CATEGORY = "data_source_validation"
_PROVIDER_CIRCUIT_ADMIN_PROBE_ROUTE_FAMILY = "admin_provider_probe"


class ConfigValidationError(Exception):
    """Raised when one or more submitted fields fail validation."""

    def __init__(self, issues: List[Dict[str, Any]]):
        super().__init__("Configuration validation failed")
        self.issues = issues


class ConfigConflictError(Exception):
    """Raised when submitted config_version is stale."""

    def __init__(self, current_version: str):
        super().__init__("Configuration version conflict")
        self.current_version = current_version


class SystemConfigService:
    """Service layer for reading, validating, and updating runtime configuration."""

    _DISPLAY_KEY_ALIASES: Dict[str, Tuple[str, ...]] = {
        "AGENT_SKILL_DIR": ("AGENT_SKILL_DIR", "AGENT_STRATEGY_DIR"),
        "AGENT_SKILL_AUTOWEIGHT": ("AGENT_SKILL_AUTOWEIGHT", "AGENT_STRATEGY_AUTOWEIGHT"),
        "AGENT_SKILL_ROUTING": ("AGENT_SKILL_ROUTING", "AGENT_STRATEGY_ROUTING"),
    }
    _DISPLAY_VALUE_ALIASES: Dict[str, Dict[str, str]] = {
        "AGENT_ORCHESTRATOR_MODE": {
            "strategy": "specialist",
            "skill": "specialist",
        }
    }

    def __init__(self, manager: Optional[ConfigManager] = None):
        self._manager = manager or ConfigManager()

    def get_schema(self) -> Dict[str, Any]:
        """Return grouped schema metadata for UI rendering."""
        return build_schema_response()

    @staticmethod
    def _progress_module_status(value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"ok", "success", "completed", "succeeded"}:
            return "completed"
        if normalized in {"failed", "error", "invalid_response", "empty_result", "insufficient_fields"}:
            return "failed"
        if normalized in {"partial", "attempting", "waiting", "running", "processing"}:
            return "running"
        return "pending"

    @classmethod
    def _build_task_progress_modules(cls, task: Any) -> List[Dict[str, Any]]:
        task_status = str(getattr(task, "status", "") or "").strip().lower()
        task_message = str(getattr(task, "message", "") or "").strip() or None
        task_updated_at = (
            getattr(task, "updated_at", None)
            or getattr(task, "completed_at", None)
            or getattr(task, "started_at", None)
            or getattr(task, "created_at", None)
        )
        updated_at = task_updated_at.isoformat() if hasattr(task_updated_at, "isoformat") else task_updated_at
        execution = getattr(task, "execution", None) if isinstance(getattr(task, "execution", None), dict) else {}
        data = execution.get("data") if isinstance(execution.get("data"), dict) else {}

        def _field(block_key: str) -> Dict[str, Any]:
            block = data.get(block_key) if isinstance(data.get(block_key), dict) else {}
            return block if isinstance(block, dict) else {}

        fundamentals = _field("fundamentals")
        news = _field("news")
        sentiment = _field("sentiment")
        fundamentals_status = cls._progress_module_status(
            fundamentals.get("status") or ("completed" if task_status == "completed" else None)
        )
        news_status = cls._progress_module_status(
            news.get("status") or ("completed" if task_status == "completed" else None)
        )
        sentiment_status = cls._progress_module_status(
            sentiment.get("status") or ("completed" if task_status == "completed" else None)
        )

        llm_status = "pending"
        technical_status = "pending"
        if task_status == "failed":
            llm_status = "failed"
            technical_status = "failed"
        elif task_status == "completed":
            llm_status = "completed"
            technical_status = "completed"
        elif task_status == "processing":
            llm_status = "running"
            technical_status = "running" if int(getattr(task, "progress", 0) or 0) >= 46 else "pending"

        market = _field("market")
        market_status = cls._progress_module_status(
            market.get("status") or ("completed" if task_status == "completed" else None)
        )
        quote_status = "pending"
        if task_status == "failed":
            quote_status = "failed"
        elif task_status == "completed":
            quote_status = "completed"
        elif task_status == "processing" and int(getattr(task, "progress", 0) or 0) >= 24:
            quote_status = "running"

        return [
            {
                "key": "market",
                "name": "市场识别",
                "status": market_status,
                "detail": task_message,
                "updated_at": updated_at,
            },
            {
                "key": "quote",
                "name": "行情",
                "status": quote_status,
                "detail": task_message,
                "updated_at": updated_at,
            },
            {
                "key": "llm",
                "name": "LLM",
                "status": llm_status,
                "detail": task_message,
                "updated_at": updated_at,
            },
            {
                "key": "technical",
                "name": "技术面",
                "status": technical_status,
                "detail": task_message,
                "updated_at": updated_at,
            },
            {
                "key": "fundamental",
                "name": "基本面",
                "status": fundamentals_status,
                "detail": task_message,
                "updated_at": updated_at,
            },
            {
                "key": "news",
                "name": "新闻",
                "status": news_status,
                "detail": task_message,
                "updated_at": updated_at,
            },
            {
                "key": "sentiment",
                "name": "情绪",
                "status": sentiment_status,
                "detail": task_message,
                "updated_at": updated_at,
            },
        ]

    def get_task_progress(self, task_id: str, *, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return a task-scoped module progress payload for Home and admin tooling."""
        from src.services.task_queue import get_task_queue

        task = get_task_queue().get_task(task_id, owner_id=owner_id)
        if task is None:
            try:
                from src.storage import DatabaseManager

                state = DatabaseManager.get_instance().get_durable_task_state(
                    task_id=task_id,
                    owner_user_id=owner_id,
                )
            except Exception:
                state = None
            if not state:
                return None
            metadata = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
            from src.services.durable_runtime_contracts import normalize_durable_runtime_status

            return {
                "task_id": state.get("task_id") or task_id,
                "stock_code": metadata.get("stock_code") or "",
                "stock_name": metadata.get("stock_name"),
                "status": normalize_durable_runtime_status(state.get("status")),
                "progress": int(state.get("progress") or 0),
                "message": state.get("current_step"),
                "updated_at": state.get("updated_at"),
                "execution_session_id": None,
                "modules": [],
                "final_result": None,
            }

        task_result = task.result if isinstance(task.result, dict) else None
        updated_at = (
            getattr(task, "updated_at", None)
            or getattr(task, "completed_at", None)
            or getattr(task, "started_at", None)
            or getattr(task, "created_at", None)
        )
        task_status_value = getattr(getattr(task, "status", None), "value", getattr(task, "status", "pending"))
        final_result = None
        if task_status_value == "completed" and task_result is not None:
            final_result = dict(task_result)
            if not final_result.get("created_at"):
                completed_at = getattr(task, "completed_at", None) or updated_at
                final_result["created_at"] = (
                    completed_at.isoformat()
                    if hasattr(completed_at, "isoformat")
                    else str(completed_at or "")
                )

        return {
            "task_id": getattr(task, "task_id", task_id),
            "stock_code": getattr(task, "stock_code", ""),
            "stock_name": getattr(task, "stock_name", None),
            "status": task_status_value,
            "progress": int(getattr(task, "progress", 0) or 0),
            "message": getattr(task, "message", None),
            "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else None,
            "execution_session_id": getattr(task, "execution_session_id", None),
            "modules": self._build_task_progress_modules(task),
            "final_result": final_result,
        }

    @staticmethod
    def _reload_runtime_singletons() -> None:
        """Reset runtime singleton services after config reload."""
        from src.agent.tools.data_tools import reset_fetcher_manager
        from src.search_service import reset_search_service

        reset_fetcher_manager()
        reset_search_service()

    def reset_runtime_caches(self) -> Dict[str, Any]:
        """Reset bounded runtime caches/singletons for admin maintenance."""
        self._reload_runtime_singletons()
        return {
            "success": True,
            "action": "reset_runtime_caches",
            "message": "Runtime provider/search caches were reset",
            "cleared": ["data_fetcher_manager", "search_service"],
        }

    def factory_reset_system(
        self,
        *,
        confirmation_phrase: str,
        actor_user_id: Optional[str] = None,
        actor_display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a bounded destructive factory reset while preserving bootstrap admin access."""
        normalized_phrase = str(confirmation_phrase or "").strip()
        if normalized_phrase != FACTORY_RESET_CONFIRMATION_PHRASE:
            raise ValueError("Factory reset confirmation phrase did not match")

        db = get_db()
        result = db.factory_reset_non_bootstrap_state()
        counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
        cleared = [
            str(item)
            for item in (result.get("cleared") or [])
            if str(item or "").strip()
        ]
        preserved = [
            "bootstrap_admin_access",
            "system_configuration",
            "execution_logs",
        ]

        ExecutionLogService().record_admin_action(
            action="factory_reset_system",
            message="Factory reset completed for bounded non-bootstrap user-owned state.",
            actor={
                "user_id": actor_user_id,
                "display_name": actor_display_name,
                "role": "admin",
            },
            subsystem="system_control",
            destructive=True,
            detail={
                "cleared": cleared,
                "counts": counts,
                "preserved": preserved,
            },
            request={
                "confirmation_phrase": FACTORY_RESET_CONFIRMATION_PHRASE,
            },
            result={
                "cleared": cleared,
                "counts": counts,
                "preserved": preserved,
            },
        )

        return {
            "success": True,
            "action": "factory_reset_system",
            "message": "Factory reset completed for bounded non-bootstrap user-owned state.",
            "cleared": cleared,
            "preserved": preserved,
            "counts": counts,
            "confirmation_phrase": FACTORY_RESET_CONFIRMATION_PHRASE,
        }

    @classmethod
    def _normalize_display_value(cls, key: str, value: str) -> str:
        alias_map = cls._DISPLAY_VALUE_ALIASES.get(key.upper())
        if not alias_map:
            return value
        return alias_map.get(value.strip().lower(), value)

    @classmethod
    def _build_display_config_map(cls, raw_config_map: Dict[str, str]) -> Dict[str, str]:
        raw_upper = {key.upper(): value for key, value in raw_config_map.items()}
        aliased_keys = {
            alias
            for candidates in cls._DISPLAY_KEY_ALIASES.values()
            for alias in candidates
        }
        display_map: Dict[str, str] = {}

        for key, value in raw_upper.items():
            if key in aliased_keys:
                continue
            display_map[key] = cls._normalize_display_value(key, value)

        for canonical_key, candidates in cls._DISPLAY_KEY_ALIASES.items():
            canonical_env_key = candidates[0]
            if canonical_env_key in raw_upper:
                display_map[canonical_key] = cls._normalize_display_value(
                    canonical_key,
                    raw_upper[canonical_env_key],
                )
                continue

            selected_value: Optional[str] = None
            candidate_seen = False
            for candidate_key in candidates[1:]:
                if candidate_key not in raw_upper:
                    continue
                candidate_seen = True
                candidate_value = raw_upper[candidate_key]
                if candidate_value:
                    selected_value = candidate_value
                    break
            if candidate_seen:
                if selected_value is None:
                    for candidate_key in candidates[1:]:
                        if candidate_key in raw_upper:
                            selected_value = raw_upper[candidate_key]
                            break
                if selected_value is None:
                    selected_value = ""
                display_map[canonical_key] = cls._normalize_display_value(
                    canonical_key,
                    selected_value,
                )

        return display_map

    @staticmethod
    def _sync_phase_g_config_shadow(
        *,
        raw_config_map: Dict[str, str],
        updated_by_user_id: Optional[str] = None,
    ) -> None:
        db = get_db()
        schema_by_key: Dict[str, Dict[str, Any]] = {
            key: get_field_definition(key, raw_config_map.get(key, ""))
            for key in set(raw_config_map.keys()) | set(get_registered_field_keys())
        }
        db.sync_phase_g_runtime_config_shadow(
            raw_config_map=raw_config_map,
            field_schema_by_key=schema_by_key,
            updated_by_user_id=updated_by_user_id,
        )

    def get_config(self, include_schema: bool = True, mask_token: str = "******") -> Dict[str, Any]:
        """Return current config values with server-side secret masking."""
        raw_config_map = self._manager.read_config_map()
        self._sync_phase_g_config_shadow(raw_config_map=raw_config_map)
        config_map = self._build_display_config_map(raw_config_map)
        registered_keys = set(get_registered_field_keys())
        all_keys = set(config_map.keys()) | registered_keys

        category_orders = {
            item["category"]: item["display_order"]
            for item in get_category_definitions()
        }

        schema_by_key: Dict[str, Dict[str, Any]] = {
            key: get_field_definition(key, config_map.get(key, ""))
            for key in all_keys
        }

        items: List[Dict[str, Any]] = []
        for key in all_keys:
            raw_value = config_map.get(key, "")
            field_schema = schema_by_key[key]
            is_sensitive = bool(field_schema.get("is_sensitive", False)) or is_sensitive_key(key)
            display_value = mask_secret(raw_value) if is_sensitive and raw_value else raw_value
            item: Dict[str, Any] = {
                "key": key,
                "value": display_value,
                "raw_value_exists": bool(raw_value),
                "is_masked": bool(is_sensitive and raw_value),
                "raw_editable": bool(field_schema.get("raw_editable", True)),
                "ui_visibility": field_schema.get("ui_visibility", "raw"),
                "managed_by": field_schema.get("managed_by"),
            }
            if include_schema:
                item["schema"] = field_schema
            items.append(item)

        items.sort(
            key=lambda item: (
                category_orders.get(schema_by_key[item["key"]].get("category", "uncategorized"), 999),
                schema_by_key[item["key"]].get("display_order", 9999),
                item["key"],
            )
        )

        return {
            "config_version": self._manager.get_config_version(),
            "mask_token": mask_token,
            "items": items,
            "updated_at": self._manager.get_updated_at(),
        }

    def validate(self, items: Sequence[Dict[str, str]], mask_token: str = "******") -> Dict[str, Any]:
        """Validate submitted items without writing to `.env`."""
        issues = self._collect_issues(items=items, mask_token=mask_token)
        valid = not any(issue["severity"] == "error" for issue in issues)
        return {
            "valid": valid,
            "issues": issues,
        }

    def test_llm_channel(
        self,
        *,
        name: str,
        protocol: str,
        base_url: str,
        api_key: str,
        models: Sequence[str],
        enabled: bool = True,
        timeout_seconds: float = 20.0,
    ) -> Dict[str, Any]:
        """Run a minimal completion call against one channel definition."""
        raw_models = [str(model).strip() for model in models if str(model).strip()]
        channel_name = name.strip() or "channel"
        validation_issues = self._validate_llm_channel_definition(
            channel_name=channel_name,
            protocol_value=protocol,
            base_url_value=base_url,
            api_key_value=api_key,
            model_values=raw_models,
            enabled=enabled,
            field_prefix="test_channel",
            require_complete=True,
        )
        errors = [issue for issue in validation_issues if issue["severity"] == "error"]
        if errors:
            return {
                "success": False,
                "message": "LLM channel configuration is invalid",
                "error": errors[0]["message"],
                "resolved_protocol": None,
                "resolved_model": None,
                "latency_ms": None,
            }

        resolved_protocol = resolve_llm_channel_protocol(protocol, base_url=base_url, models=raw_models, channel_name=name)
        resolved_models = [normalize_llm_channel_model(model, resolved_protocol, base_url) for model in raw_models]
        resolved_model = resolved_models[0]
        max_tokens = 8
        if resolved_model.startswith("deepseek/deepseek-v4-"):
            max_tokens = 64
        api_keys = [segment.strip() for segment in api_key.split(",") if segment.strip()]
        selected_api_key = api_keys[0] if api_keys else ""

        call_kwargs: Dict[str, Any] = {
            "model": resolved_model,
            "messages": [{"role": "user", "content": "Reply with OK only"}],
            "temperature": 0,
            "max_tokens": max_tokens,
            "timeout": max(5.0, float(timeout_seconds)),
        }
        if selected_api_key:
            call_kwargs["api_key"] = selected_api_key
        if base_url.strip():
            call_kwargs["api_base"] = base_url.strip()

        try:
            from src.services.litellm_runtime import configure_litellm_cost_map_for_runtime

            configure_litellm_cost_map_for_runtime()
            import litellm

            started_at = time.perf_counter()
            response = litellm.completion(**call_kwargs)
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            content = self._extract_llm_response_text(response)

            if not content:
                finish_reason = ""
                if response and getattr(response, "choices", None):
                    finish_reason = str(getattr(response.choices[0], "finish_reason", "") or "").strip()
                return {
                    "success": False,
                    "message": "LLM channel returned empty content",
                    "error": self._build_llm_empty_response_hint(
                        resolved_protocol=resolved_protocol,
                        resolved_model=resolved_model,
                        finish_reason=finish_reason,
                    ),
                    "resolved_protocol": resolved_protocol or None,
                    "resolved_model": resolved_model,
                    "latency_ms": latency_ms,
                }

            return {
                "success": True,
                "message": "LLM channel test succeeded",
                "error": None,
                "resolved_protocol": resolved_protocol or None,
                "resolved_model": resolved_model,
                "latency_ms": latency_ms,
            }
        except Exception as exc:
            logger.warning("LLM channel test failed for %s: %s", channel_name, exc)
            classified_message, classified_error = self._classify_llm_test_exception(
                exc=exc,
                resolved_protocol=resolved_protocol,
                resolved_model=resolved_model,
            )
            return {
                "success": False,
                "message": classified_message,
                "error": classified_error,
                "resolved_protocol": resolved_protocol or None,
                "resolved_model": resolved_model,
                "latency_ms": None,
            }

    def test_custom_data_source(
        self,
        *,
        name: str,
        base_url: str,
        credential_schema: str,
        credential: str,
        secret: str = "",
        timeout_seconds: float = 5.0,
    ) -> Dict[str, Any]:
        """Run a bounded connectivity probe for a custom data source base URL."""
        normalized_name = str(name or "").strip() or "custom_data_source"
        normalized_url = str(base_url or "").strip()
        parsed = urlparse(normalized_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return {
                "success": False,
                "message": "Base URL format is invalid",
                "error": "Use a full http(s) URL before testing connectivity.",
                "status_code": None,
                "checked_url": normalized_url,
                "latency_ms": None,
            }

        headers = {
            "User-Agent": "WolfyStock-Config-Validation/1.0",
            "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
        }
        trimmed_credential = str(credential or "").strip()
        trimmed_secret = str(secret or "").strip()
        if credential_schema == "key_secret":
            if trimmed_credential:
                headers["X-API-Key"] = trimmed_credential
            if trimmed_secret:
                headers["X-API-Secret"] = trimmed_secret
        elif trimmed_credential:
            headers["Authorization"] = f"Bearer {trimmed_credential}"

        methods = ["HEAD", "GET"]
        for index, method in enumerate(methods):
            try:
                started_at = time.perf_counter()
                response = requests.request(
                    method,
                    normalized_url,
                    headers=headers,
                    timeout=max(2.0, float(timeout_seconds)),
                    allow_redirects=True,
                    stream=(method == "GET"),
                )
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                status_code = int(getattr(response, "status_code", 0) or 0)
                try:
                    return self._classify_custom_data_source_probe(
                        status_code=status_code,
                        checked_url=normalized_url,
                        latency_ms=latency_ms,
                    )
                finally:
                    close_fn = getattr(response, "close", None)
                    if callable(close_fn):
                        close_fn()
            except requests.exceptions.SSLError as exc:
                return {
                    "success": False,
                    "message": "TLS handshake failed while testing the endpoint",
                    "error": "The server certificate could not be verified. Check HTTPS/TLS configuration.",
                    "status_code": None,
                    "checked_url": normalized_url,
                    "latency_ms": None,
                }
            except requests.exceptions.Timeout:
                return {
                    "success": False,
                    "message": "Endpoint timed out during connectivity validation",
                    "error": "The server did not respond before the timeout window elapsed.",
                    "status_code": None,
                    "checked_url": normalized_url,
                    "latency_ms": None,
                }
            except requests.exceptions.ConnectionError as exc:
                classified = self._classify_custom_data_source_connection_error(exc)
                return {
                    "success": False,
                    "message": classified[0],
                    "error": classified[1],
                    "status_code": None,
                    "checked_url": normalized_url,
                    "latency_ms": None,
                }
            except requests.exceptions.RequestException as exc:
                logger.warning("Custom data source probe failed for %s: %s", normalized_name, exc)
                return {
                    "success": False,
                    "message": "Endpoint probe failed before a valid HTTP response was returned",
                    "error": "The request could not be completed. Check proxy, URL, and server reachability.",
                    "status_code": None,
                    "checked_url": normalized_url,
                    "latency_ms": None,
                }

            if index == 0:
                continue

        return {
            "success": False,
            "message": "Endpoint probe did not complete",
            "error": "No usable probe result was produced.",
            "status_code": None,
            "checked_url": normalized_url,
            "latency_ms": None,
        }

    def test_builtin_data_source(
        self,
        *,
        provider: str,
        symbol: str = "MSFT",
        credential: str = "",
        secret: str = "",
        timeout_seconds: float = _REMOTE_VALIDATION_TIMEOUT_SECONDS,
    ) -> Dict[str, Any]:
        """Run bounded remote validation for a built-in data provider."""
        normalized_provider = normalize_provider_name(provider)
        normalized_symbol = (symbol or "MSFT").strip().upper() or "MSFT"
        timeout = min(_REMOTE_VALIDATION_TIMEOUT_SECONDS, max(1.0, float(timeout_seconds or _REMOTE_VALIDATION_TIMEOUT_SECONDS)))
        resolved_credential = ""
        if normalized_provider in {"fmp", "finnhub", "alpha_vantage", "twelve_data", "tushare"}:
            resolved_credential = self._resolve_provider_key(normalized_provider, credential)
        circuit_decision = self._provider_circuit_admin_probe_pilot_decision(normalized_provider)
        if circuit_decision and circuit_decision["would_block_call"]:
            return self._provider_circuit_blocked_builtin_response(
                provider=normalized_provider,
                decision=circuit_decision,
            )
        if normalized_provider == "twelve_data":
            return self._test_twelve_data_hk_data_source(
                symbol=normalized_symbol,
                credential=resolved_credential,
                timeout_seconds=timeout,
            )

        provider_result = validate_provider_connection(
            normalized_provider,
            normalized_symbol,
            credential=resolved_credential,
            timeout_seconds=timeout,
        )
        checks = project_provider_result_checks(provider_result)
        status = project_provider_result_status(provider_result)
        checked_at = (
            provider_result.finishedAt.isoformat()
            if getattr(provider_result, "finishedAt", None) is not None
            else datetime.now(timezone.utc).isoformat()
        )
        return {
            "provider": normalized_provider,
            "ok": status == "success",
            "status": status,
            "checked_at": checked_at,
            "duration_ms": int(provider_result.durationMs or 0),
            "key_masked": mask_provider_secret(resolved_credential),
            "checks": checks,
            "summary": provider_validation_summary(normalized_provider, status, checks),
            "suggestion": provider_validation_suggestion(normalized_provider, status),
        }

    @staticmethod
    def _provider_circuit_admin_probe_pilot_enabled() -> bool:
        return parse_env_bool(os.getenv(_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED_ENV), default=False)

    @staticmethod
    def _provider_circuit_admin_probe_pilot_rollback_enabled() -> bool:
        return parse_env_bool(os.getenv(_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENV), default=False)

    def _provider_circuit_admin_probe_pilot_decision(self, provider: str) -> Optional[Dict[str, Any]]:
        pilot_enabled = self._provider_circuit_admin_probe_pilot_enabled()
        rollback_enabled = self._provider_circuit_admin_probe_pilot_rollback_enabled()
        if not pilot_enabled or rollback_enabled:
            return None
        return ProviderCircuitObserver().build_low_risk_enforcement_pilot_decision(
            provider=provider,
            provider_category=_PROVIDER_CIRCUIT_ADMIN_PROBE_CATEGORY,
            route_family=_PROVIDER_CIRCUIT_ADMIN_PROBE_ROUTE_FAMILY,
            pilot_enabled=pilot_enabled,
            rollback_enabled=rollback_enabled,
            controlled_provider_categories=(_PROVIDER_CIRCUIT_ADMIN_PROBE_CATEGORY,),
            controlled_route_families=(_PROVIDER_CIRCUIT_ADMIN_PROBE_ROUTE_FAMILY,),
        )

    @staticmethod
    def _provider_circuit_blocked_builtin_response(
        *,
        provider: str,
        decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        reason_code = str(decision.get("enforcement_block_reason_code") or "provider_circuit_blocked")
        message = (
            "Provider circuit admin probe pilot blocked this provider validation "
            f"before outbound work: {reason_code}."
        )
        return {
            "provider": provider,
            "ok": False,
            "status": "failed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": 0,
            "key_masked": None,
            "checks": [
                {
                    "name": "provider_circuit",
                    "endpoint": _PROVIDER_CIRCUIT_ADMIN_PROBE_ROUTE_FAMILY,
                    "ok": False,
                    "http_status": None,
                    "duration_ms": 0,
                    "error_type": "provider_circuit_blocked",
                    "message": message,
                }
            ],
            "summary": "Provider circuit admin probe pilot blocked this provider validation.",
            "suggestion": (
                "Review admin provider circuit diagnostics or disable "
                f"{_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED_ENV}; rollback is "
                f"{_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENV}=true."
            ),
        }

    @staticmethod
    def sanitize_url(url: str) -> str:
        """Mask credential-bearing query params before returning or logging URLs."""
        return sanitize_url(str(url or ""))

    @staticmethod
    def _normalize_twelve_data_hk_symbol(symbol: str) -> Optional[str]:
        text = str(symbol or "").strip().upper()
        if not text:
            return None
        if text.endswith(".HK"):
            digits = text[:-3]
        elif text.startswith("HK"):
            digits = text[2:]
        else:
            digits = text
        digits = "".join(ch for ch in digits if ch.isdigit())
        if len(digits) != 5:
            return None
        return digits[1:] if digits.startswith("0") else digits

    @staticmethod
    def _sanitize_provider_probe_message(message: Any, credential: str) -> str:
        sanitized = sanitize_message(str(message or ""))
        secret = str(credential or "").strip()
        if secret and len(secret) >= 4:
            sanitized = sanitized.replace(secret, "***")
        return sanitized

    @classmethod
    def _extract_provider_error_message(cls, payload: Any, credential: str) -> str:
        if isinstance(payload, dict):
            for key in ("message", "error", "msg", "code", "Note", "Information", "Error Message"):
                value = payload.get(key)
                if value:
                    return cls._sanitize_provider_probe_message(value, credential)
        return ""

    @staticmethod
    def _twelve_data_http_error_message(name: str, status_code: int) -> str:
        if status_code == 401:
            return f"{name} endpoint 返回 401，可能是 API key 无效或缺失。"
        if status_code == 403:
            return f"{name} endpoint 返回 403，可能是当前 key 缺少 HK quote/history entitlement。"
        if status_code == 429:
            return f"{name} endpoint 返回 429，可能已触发 provider 频率限制或额度耗尽。"
        if status_code >= 500:
            return f"{name} endpoint 返回 HTTP {status_code}，provider 当前不可用。"
        return f"{name} endpoint 返回 HTTP {status_code}，远程校验失败。"

    @classmethod
    def _classify_twelve_data_probe_failure(
        cls,
        *,
        name: str,
        http_status: Optional[int],
        payload: Any,
        credential: str,
    ) -> Tuple[str, str]:
        payload_message = cls._extract_provider_error_message(payload, credential)
        lowered = payload_message.lower()
        if http_status == 429 or any(token in lowered for token in ("quota", "rate limit", "frequency", "credits", "too many")):
            return "RateLimited", cls._twelve_data_http_error_message(name, 429)
        if http_status == 403 or any(token in lowered for token in ("permission", "premium", "subscription", "entitlement", "plan")):
            return "Forbidden", cls._twelve_data_http_error_message(name, 403)
        if http_status and http_status >= 500:
            return "ProviderError", cls._twelve_data_http_error_message(name, int(http_status))
        if payload_message:
            return "InvalidPayload", payload_message
        return "InvalidPayload", f"{name} endpoint 返回的数据结构不可用。"

    @classmethod
    def _run_twelve_data_hk_probe(
        cls,
        *,
        name: str,
        endpoint: str,
        url: str,
        params: Dict[str, Any],
        timeout_seconds: float,
        validator: Callable[[Any], bool],
    ) -> Dict[str, Any]:
        started_at = time.perf_counter()
        response = None
        try:
            response = requests.request(
                "GET",
                url,
                params=params,
                timeout=timeout_seconds,
                headers={
                    "Accept": "application/json",
                    "User-Agent": _REMOTE_VALIDATION_USER_AGENT,
                },
            )
            http_status = getattr(response, "status_code", None)
            try:
                payload = response.json()
            except Exception:
                return {
                    "name": name,
                    "endpoint": endpoint,
                    "ok": False,
                    "http_status": http_status,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "error_type": "InvalidPayload",
                    "message": f"{name} endpoint 返回非 JSON 响应。",
                }
            if http_status and int(http_status) >= 400:
                error_type, message = cls._classify_twelve_data_probe_failure(
                    name=name,
                    http_status=int(http_status),
                    payload=payload,
                    credential=str(params.get("apikey") or ""),
                )
                return {
                    "name": name,
                    "endpoint": endpoint,
                    "ok": False,
                    "http_status": int(http_status),
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "error_type": error_type,
                    "message": message,
                }
            if validator(payload):
                return {
                    "name": name,
                    "endpoint": endpoint,
                    "ok": True,
                    "http_status": int(http_status) if http_status is not None else 200,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "error_type": None,
                    "message": f"{name} endpoint 可用。",
                }
            error_type, message = cls._classify_twelve_data_probe_failure(
                name=name,
                http_status=int(http_status) if http_status is not None else None,
                payload=payload,
                credential=str(params.get("apikey") or ""),
            )
            return {
                "name": name,
                "endpoint": endpoint,
                "ok": False,
                "http_status": int(http_status) if http_status is not None else None,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
                "error_type": error_type,
                "message": message,
            }
        except requests.exceptions.Timeout:
            return {
                "name": name,
                "endpoint": endpoint,
                "ok": False,
                "http_status": None,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
                "error_type": "Timeout",
                "message": f"{name} endpoint 在 {int(timeout_seconds)} 秒内未响应。",
            }
        except requests.exceptions.RequestException:
            return {
                "name": name,
                "endpoint": endpoint,
                "ok": False,
                "http_status": None,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
                "error_type": "ProviderError",
                "message": "endpoint 请求失败，请检查网络、代理或 provider 服务状态。",
            }
        finally:
            if response is not None and hasattr(response, "close"):
                response.close()

    def _test_twelve_data_hk_data_source(
        self,
        *,
        symbol: str,
        credential: str,
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        checked_at = datetime.now(timezone.utc).isoformat()
        hk_symbol = self._normalize_twelve_data_hk_symbol(symbol)
        credential_configured = bool(str(credential or "").strip())
        checks: List[Dict[str, Any]] = []

        if credential_configured and hk_symbol:
            probe_params = {
                "symbol": hk_symbol,
                "exchange": "HKEX",
                "apikey": credential,
            }
            checks.append(
                self._run_twelve_data_hk_probe(
                    name="hk_quote",
                    endpoint="/quote",
                    url="https://api.twelvedata.com/quote",
                    params=probe_params,
                    timeout_seconds=timeout_seconds,
                    validator=lambda data: isinstance(data, dict) and str(data.get("status") or "").lower() != "error" and bool(data.get("price") or data.get("close")),
                )
            )
            history_params = {
                **probe_params,
                "interval": "1day",
                "outputsize": "5",
            }
            checks.append(
                self._run_twelve_data_hk_probe(
                    name="hk_history",
                    endpoint="/time_series",
                    url="https://api.twelvedata.com/time_series",
                    params=history_params,
                    timeout_seconds=timeout_seconds,
                    validator=lambda data: (
                        isinstance(data, dict)
                        and isinstance(data.get("values"), list)
                        and bool(data.get("values"))
                        and isinstance(data["values"][0], dict)
                        and bool(data["values"][0].get("close"))
                    ),
                )
            )

        projection = project_twelve_data_hk_diagnostic(
            credential_configured=credential_configured,
            hk_symbol_verified=bool(hk_symbol),
            checks=checks,
        )
        all_checks = [*checks, projection["diagnostic_check"]]
        return {
            "provider": "twelve_data",
            "ok": projection["status"] == "success",
            "status": projection["status"],
            "checked_at": checked_at,
            "duration_ms": sum(int(check.get("duration_ms") or 0) for check in checks),
            "key_masked": mask_provider_secret(credential),
            "checks": all_checks,
            "summary": projection["summary"],
            "suggestion": projection["suggestion"],
        }

    def _resolve_provider_key(self, provider: str, credential: str = "") -> str:
        supplied = str(credential or "").strip()
        if supplied and set(supplied) != {"*"}:
            return supplied
        values = self._manager.read_config_map()
        key_map = {
            "fmp": ("FMP_API_KEYS", "FMP_API_KEY"),
            "finnhub": ("FINNHUB_API_KEYS", "FINNHUB_API_KEY"),
            "alpha_vantage": ("ALPHA_VANTAGE_API_KEYS", "ALPHA_VANTAGE_API_KEY", "ALPHAVANTAGE_API_KEYS", "ALPHAVANTAGE_API_KEY"),
            "twelve_data": ("TWELVE_DATA_API_KEYS", "TWELVE_DATA_API_KEY", "TWELVEDATA_API_KEYS", "TWELVEDATA_API_KEY"),
            "tushare": ("TUSHARE_TOKEN",),
        }
        for key in key_map.get(provider, ()):
            raw_value = str(values.get(key, "") or "").strip()
            if raw_value:
                return next((part.strip() for part in raw_value.split(",") if part.strip()), raw_value)
        return ""

    @staticmethod
    def _extract_llm_response_text(response: Any) -> str:
        """Extract plain text content from heterogeneous LiteLLM response shapes."""
        if not response or not getattr(response, "choices", None):
            return ""
        first_choice = response.choices[0]
        message = getattr(first_choice, "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            fragments: List[str] = []
            for item in content:
                if isinstance(item, str):
                    text = item.strip()
                else:
                    if isinstance(item, dict):
                        item_type = str(item.get("type") or "").strip().lower()
                        if item_type and item_type not in _TEXT_CONTENT_BLOCK_TYPES:
                            continue
                        text = str(item.get("text") or (item.get("content") if not item_type else "") or "").strip()
                    else:
                        item_type = str(getattr(item, "type", "") or "").strip().lower()
                        if item_type and item_type not in _TEXT_CONTENT_BLOCK_TYPES:
                            continue
                        text = str(
                            getattr(item, "text", "")
                            or (getattr(item, "content", "") if not item_type else "")
                            or ""
                        ).strip()
                if text:
                    fragments.append(text)
            return " ".join(fragments).strip()
        if content is None:
            delta = getattr(first_choice, "delta", None)
            if isinstance(delta, dict):
                return str(delta.get("content") or "").strip()
            if delta is not None:
                return str(getattr(delta, "content", "") or "").strip()
        return str(content or "").strip()

    @staticmethod
    def _classify_custom_data_source_connection_error(
        exc: requests.exceptions.ConnectionError,
    ) -> Tuple[str, str]:
        raw_error = str(exc).strip().lower()
        dns_tokens = (
            "name or service not known",
            "temporary failure in name resolution",
            "nodename nor servname provided",
            "getaddrinfo failed",
            "no address associated with hostname",
        )
        if any(token in raw_error for token in dns_tokens):
            return (
                "DNS resolution failed while testing the endpoint",
                "The hostname could not be resolved. Check the Base URL host spelling and DNS availability.",
            )
        return (
            "Connection to the endpoint failed",
            "The host was reached incorrectly or refused the connection. Check host, port, firewall, and service status.",
        )

    @staticmethod
    def _classify_custom_data_source_probe(
        *,
        status_code: int,
        checked_url: str,
        latency_ms: int,
    ) -> Dict[str, Any]:
        if 200 <= status_code < 300:
            return {
                "success": True,
                "message": "Endpoint reachable and responded successfully",
                "error": None,
                "status_code": status_code,
                "checked_url": checked_url,
                "latency_ms": latency_ms,
            }
        if 300 <= status_code < 400:
            return {
                "success": True,
                "message": "Endpoint reachable and responded with a redirect",
                "error": "The URL redirected during validation. Verify that the final target is the intended API endpoint.",
                "status_code": status_code,
                "checked_url": checked_url,
                "latency_ms": latency_ms,
            }
        if status_code in {401, 403}:
            return {
                "success": False,
                "message": "Endpoint reachable, but the server rejected the supplied credentials",
                "error": "Connectivity is working, but authentication/authorization failed.",
                "status_code": status_code,
                "checked_url": checked_url,
                "latency_ms": latency_ms,
            }
        if status_code == 404:
            return {
                "success": False,
                "message": "Endpoint reachable, but the Base URL path was not found",
                "error": "The server responded with 404. Check the Base URL path and version suffix.",
                "status_code": status_code,
                "checked_url": checked_url,
                "latency_ms": latency_ms,
            }
        if status_code in {405, 501}:
            return {
                "success": True,
                "message": "Endpoint reachable, but the probe method is not supported",
                "error": "The server rejected the validation method, but network reachability is confirmed.",
                "status_code": status_code,
                "checked_url": checked_url,
                "latency_ms": latency_ms,
            }
        return {
            "success": False,
            "message": f"Endpoint responded with unexpected HTTP status {status_code}",
            "error": "The server was reachable, but the response was not usable for validation.",
            "status_code": status_code,
            "checked_url": checked_url,
            "latency_ms": latency_ms,
        }

    @staticmethod
    def _build_llm_empty_response_hint(
        *,
        resolved_protocol: str,
        resolved_model: str,
        finish_reason: str,
    ) -> str:
        """Return actionable hint for empty-content channel test failures."""
        parts = [
            (
                "Provider returned an empty response body; no content could be extracted from the test call."
            ),
            (
                "Possible causes: unsupported model, missing model entitlement, protocol mismatch, "
                "or provider response format not parseable by current adapter."
            ),
            f"Model={resolved_model or 'unknown'}, protocol={resolved_protocol or 'unknown'}.",
        ]
        if finish_reason:
            parts.append(f"finish_reason={finish_reason}.")
        parts.append("Try a known-supported model first, then verify entitlement/protocol in advanced channel testing.")
        return " ".join(parts)

    @staticmethod
    def _classify_llm_test_exception(
        *,
        exc: Exception,
        resolved_protocol: str,
        resolved_model: str,
    ) -> Tuple[str, str]:
        """Map provider errors to actionable channel-test diagnostics."""
        raw_error = str(exc).strip()
        lowered = raw_error.lower()
        if any(token in lowered for token in ["auth", "unauthorized", "invalid api key", "401", "forbidden", "permission denied"]):
            return (
                "LLM channel authentication failed",
                (
                    "Authentication failed for this provider key. "
                    "Verify API key/tenant permissions and endpoint settings."
                ),
            )
        if any(token in lowered for token in ["model not found", "unknown model", "unsupported model", "not support", "does not exist"]):
            return (
                "LLM channel model is unavailable",
                (
                    "The selected model may be unsupported for this provider/account. "
                    f"Model={resolved_model or 'unknown'} protocol={resolved_protocol or 'unknown'}. "
                    "Try a known-supported model or check model entitlement."
                ),
            )
        if any(token in lowered for token in ["empty response", "no content", "blank response"]):
            return (
                "LLM channel returned empty content",
                SystemConfigService._build_llm_empty_response_hint(
                    resolved_protocol=resolved_protocol,
                    resolved_model=resolved_model,
                    finish_reason="",
                ),
            )
        if "timeout" in lowered:
            return (
                "LLM channel test timed out",
                "Request timed out before provider returned a usable response. Retry with a smaller model or longer timeout.",
            )
        return (
            "LLM channel test failed",
            (
                "Provider call failed. Check protocol/base URL/model settings and advanced channel test details. "
                f"Raw error: {raw_error[:240]}"
            ),
        )

    def update(
        self,
        config_version: str,
        items: Sequence[Dict[str, str]],
        mask_token: str = "******",
        reload_now: bool = True,
        actor_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate and persist updates into `.env`, then reload runtime config."""
        current_version = self._manager.get_config_version()
        if current_version != config_version:
            raise ConfigConflictError(current_version=current_version)

        issues = self._collect_issues(items=items, mask_token=mask_token)
        errors = [issue for issue in issues if issue["severity"] == "error"]
        if errors:
            raise ConfigValidationError(issues=errors)

        submitted_keys: Set[str] = set()
        updates: List[Tuple[str, str]] = []
        sensitive_keys: Set[str] = set()
        for item in items:
            key = item["key"].upper()
            value = item["value"]
            submitted_keys.add(key)
            updates.append((key, value))
            field_schema = get_field_definition(key)
            if bool(field_schema.get("is_sensitive", False)) or is_sensitive_key(key):
                sensitive_keys.add(key)

        updated_keys, skipped_masked_keys, new_version = self._manager.apply_updates(
            updates=updates,
            sensitive_keys=sensitive_keys,
            mask_token=mask_token,
        )
        self._sync_phase_g_config_shadow(
            raw_config_map=self._manager.read_config_map(),
            updated_by_user_id=actor_user_id,
        )

        warnings: List[str] = []
        reload_triggered = False
        if reload_now:
            try:
                Config.reset_instance()
                self._reload_runtime_singletons()
                setup_env(override=True)
                config = Config.get_instance()
                warnings.extend(config.validate())
                reload_triggered = True
            except Exception as exc:  # pragma: no cover - defensive branch
                logger.error("Configuration reload failed: %s", exc, exc_info=True)
                warnings.append("Configuration updated but reload failed")

        warnings.extend(
            self._build_explainability_warnings(
                submitted_keys=submitted_keys,
                reload_now=reload_now,
            )
        )

        return {
            "success": True,
            "config_version": new_version,
            "applied_count": len(updated_keys),
            "skipped_masked_count": len(skipped_masked_keys),
            "reload_triggered": reload_triggered,
            "updated_keys": updated_keys,
            "warnings": warnings,
        }

    def _build_explainability_warnings(
        self,
        *,
        submitted_keys: Set[str],
        reload_now: bool,
    ) -> List[str]:
        """Append user-facing runtime explainability warnings for key settings."""
        warnings: List[str] = []
        if not submitted_keys:
            return warnings

        current_map = self._manager.read_config_map()

        if submitted_keys & {"NEWS_MAX_AGE_DAYS", "NEWS_STRATEGY_PROFILE"}:
            raw_profile = current_map.get("NEWS_STRATEGY_PROFILE", "short")
            profile = normalize_news_strategy_profile(raw_profile)
            try:
                max_age = max(1, int(current_map.get("NEWS_MAX_AGE_DAYS", "3") or "3"))
            except (TypeError, ValueError):
                max_age = 3
            effective_days = resolve_news_window_days(
                news_max_age_days=max_age,
                news_strategy_profile=profile,
            )
            warnings.append(
                (
                    "新闻窗口已按策略计算："
                    f"NEWS_STRATEGY_PROFILE={profile}, "
                    f"NEWS_MAX_AGE_DAYS={max_age}, "
                    f"effective_days={effective_days} "
                    "(effective_days=min(profile_days, NEWS_MAX_AGE_DAYS))."
                )
            )

        if "MAX_WORKERS" in submitted_keys:
            try:
                max_workers = max(1, int(current_map.get("MAX_WORKERS", "3") or "3"))
            except (TypeError, ValueError):
                max_workers = 3
            if reload_now:
                warnings.append(
                    (
                        f"MAX_WORKERS={max_workers} 已保存。任务队列空闲时会自动应用；"
                        "若当前存在运行中任务，将在队列空闲后生效。"
                    )
                )
            else:
                warnings.append(
                    (
                        f"MAX_WORKERS={max_workers} 已写入 .env，但本次未触发运行时重载"
                        "（reload_now=false）；重载后才会应用。"
                    )
                )

        return warnings

    def apply_simple_updates(
        self,
        updates: Sequence[Tuple[str, str]],
        mask_token: str = "******",
    ) -> None:
        """Apply raw key updates without validation (internal service use only)."""
        self._manager.apply_updates(
            updates=updates,
            sensitive_keys=set(),
            mask_token=mask_token,
        )
        self._sync_phase_g_config_shadow(
            raw_config_map=self._manager.read_config_map(),
        )

    def _collect_issues(self, items: Sequence[Dict[str, str]], mask_token: str) -> List[Dict[str, Any]]:
        """Collect field-level and cross-field validation issues."""
        current_map = self._manager.read_config_map()
        effective_map = dict(current_map)
        issues: List[Dict[str, Any]] = []
        updated_map: Dict[str, str] = {}

        for item in items:
            key = item["key"].upper()
            value = item["value"]
            field_schema = get_field_definition(key, value)
            is_sensitive = bool(field_schema.get("is_sensitive", False)) or is_sensitive_key(key)

            if is_sensitive and is_masked_secret(value, current_map.get(key, ""), mask_token):
                continue

            updated_map[key] = value
            effective_map[key] = value
            issues.extend(self._validate_value(key=key, value=value, field_schema=field_schema))

        issues.extend(self._validate_cross_field(effective_map=effective_map, updated_keys=set(updated_map.keys())))
        return issues

    @staticmethod
    def _validate_value(key: str, value: str, field_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate a single field value against schema metadata."""
        issues: List[Dict[str, Any]] = []
        data_type = field_schema.get("data_type", "string")
        validation = field_schema.get("validation", {}) or {}
        is_required = field_schema.get("is_required", False)

        # Empty values are valid for non-required fields (skip type validation)
        if not value.strip() and not is_required:
            return issues

        if "\n" in value:
            issues.append(
                {
                    "key": key,
                    "code": "invalid_value",
                    "message": "Value cannot contain newline characters",
                    "severity": "error",
                    "expected": "single-line value",
                    "actual": "contains newline",
                }
            )
            return issues

        if data_type == "integer":
            try:
                numeric = int(value)
            except ValueError:
                return [
                    {
                        "key": key,
                        "code": "invalid_type",
                        "message": "Value must be an integer",
                        "severity": "error",
                        "expected": "integer",
                        "actual": value,
                    }
                ]
            issues.extend(SystemConfigService._validate_numeric_range(key, numeric, validation))

        elif data_type == "number":
            try:
                numeric = float(value)
            except ValueError:
                return [
                    {
                        "key": key,
                        "code": "invalid_type",
                        "message": "Value must be a number",
                        "severity": "error",
                        "expected": "number",
                        "actual": value,
                    }
                ]
            issues.extend(SystemConfigService._validate_numeric_range(key, numeric, validation))

        elif data_type == "boolean":
            if value.strip().lower() not in {"true", "false"}:
                issues.append(
                    {
                        "key": key,
                        "code": "invalid_type",
                        "message": "Value must be true or false",
                        "severity": "error",
                        "expected": "true|false",
                        "actual": value,
                    }
                )

        elif data_type == "time":
            pattern = validation.get("pattern") or r"^([01]\d|2[0-3]):[0-5]\d$"
            if not re.match(pattern, value.strip()):
                issues.append(
                    {
                        "key": key,
                        "code": "invalid_format",
                        "message": "Value must be in HH:MM format",
                        "severity": "error",
                        "expected": "HH:MM",
                        "actual": value,
                    }
                )

        if "enum" in validation and value and value not in validation["enum"]:
            issues.append(
                {
                    "key": key,
                    "code": "invalid_enum",
                    "message": "Value is not in allowed options",
                    "severity": "error",
                    "expected": ",".join(validation["enum"]),
                    "actual": value,
                }
            )

        if validation.get("item_type") == "url":
            delimiter = validation.get("delimiter", ",")
            values = [item.strip() for item in value.split(delimiter)] if validation.get("multi_value") else [value.strip()]
            allowed_schemes = tuple(validation.get("allowed_schemes", ["http", "https"]))
            invalid_values = [
                item for item in values
                if item and not SystemConfigService._is_valid_url(item, allowed_schemes=allowed_schemes)
            ]
            if invalid_values:
                issues.append(
                    {
                        "key": key,
                        "code": "invalid_url",
                        "message": "Value must contain valid URLs with scheme and host",
                        "severity": "error",
                        "expected": ",".join(allowed_schemes) + " URL(s)",
                        "actual": ", ".join(invalid_values[:3]),
                    }
                )

        return issues

    @staticmethod
    def _validate_numeric_range(key: str, numeric_value: float, validation: Dict[str, Any]) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        min_value = validation.get("min")
        max_value = validation.get("max")

        if min_value is not None and numeric_value < min_value:
            issues.append(
                {
                    "key": key,
                    "code": "out_of_range",
                    "message": "Value is lower than minimum",
                    "severity": "error",
                    "expected": f">={min_value}",
                    "actual": str(numeric_value),
                }
            )
        if max_value is not None and numeric_value > max_value:
            issues.append(
                {
                    "key": key,
                    "code": "out_of_range",
                    "message": "Value is greater than maximum",
                    "severity": "error",
                    "expected": f"<={max_value}",
                    "actual": str(numeric_value),
                }
            )
        return issues

    @staticmethod
    def _is_valid_url(value: str, allowed_schemes: Tuple[str, ...]) -> bool:
        """Return True when *value* looks like a valid absolute URL."""
        parsed = urlparse(value)
        return parsed.scheme in allowed_schemes and bool(parsed.netloc)

    @staticmethod
    def _is_safe_base_url(value: str) -> bool:
        """Block link-local and cloud metadata addresses to prevent SSRF.

        Allows localhost / private-LAN addresses (e.g. Ollama on 192.168.x.x)
        but blocks 169.254.x.x (AWS/Azure/GCP/Alibaba instance-metadata service)
        and other known metadata hostnames.
        """
        import ipaddress

        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        if not host:
            return True
        # Known cloud metadata hostnames
        _BLOCKED_HOSTS = frozenset({
            "169.254.169.254",
            "metadata.google.internal",
            "100.100.100.200",
        })
        if host in _BLOCKED_HOSTS:
            return False
        # Numeric IPs: block link-local range (169.254.0.0/16)
        try:
            addr = ipaddress.ip_address(host)
            if addr.is_link_local:
                return False
        except ValueError:
            pass  # hostname, not an IP — already checked against blocklist above
        return True

    @staticmethod
    def _validate_cross_field(effective_map: Dict[str, str], updated_keys: Set[str]) -> List[Dict[str, Any]]:
        """Validate dependencies across multiple keys."""
        issues: List[Dict[str, Any]] = []

        token_value = (effective_map.get("TELEGRAM_BOT_TOKEN") or "").strip()
        chat_id_value = (effective_map.get("TELEGRAM_CHAT_ID") or "").strip()
        if token_value and not chat_id_value and (
            "TELEGRAM_BOT_TOKEN" in updated_keys or "TELEGRAM_CHAT_ID" in updated_keys
        ):
            issues.append(
                {
                    "key": "TELEGRAM_CHAT_ID",
                    "code": "missing_dependency",
                    "message": "TELEGRAM_CHAT_ID is required when TELEGRAM_BOT_TOKEN is set",
                    "severity": "error",
                    "expected": "non-empty TELEGRAM_CHAT_ID",
                    "actual": chat_id_value,
                }
            )

        alpaca_key_id = (effective_map.get("ALPACA_API_KEY_ID") or "").strip()
        alpaca_secret = (effective_map.get("ALPACA_API_SECRET_KEY") or "").strip()
        if (alpaca_key_id or alpaca_secret) and not (alpaca_key_id and alpaca_secret) and (
            {"ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY", "ALPACA_DATA_FEED"} & updated_keys
        ):
            missing_key = "ALPACA_API_SECRET_KEY" if alpaca_key_id and not alpaca_secret else "ALPACA_API_KEY_ID"
            issues.append(
                {
                    "key": missing_key,
                    "code": "missing_dependency",
                    "message": "Alpaca credentials require both ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY",
                    "severity": "error",
                    "expected": "complete Alpaca key ID + secret key pair",
                    "actual": "partial Alpaca credential set",
                }
            )

        issues.extend(
            SystemConfigService._validate_llm_channel_map(
                effective_map=effective_map,
                updated_keys=updated_keys,
            )
        )
        issues.extend(SystemConfigService._validate_llm_runtime_selection(effective_map=effective_map))

        return issues

    @staticmethod
    def _validate_llm_channel_map(effective_map: Dict[str, str], updated_keys: Set[str]) -> List[Dict[str, Any]]:
        """Validate channel-style LLM configuration stored in `.env`."""
        issues: List[Dict[str, Any]] = []
        if SystemConfigService._uses_litellm_yaml(effective_map):
            return issues

        raw_channels = (effective_map.get("LLM_CHANNELS") or "").strip()
        if not raw_channels:
            return issues

        normalized_names: List[str] = []
        seen_names: Set[str] = set()
        for raw_name in raw_channels.split(","):
            name = raw_name.strip()
            if not name:
                continue
            if not re.fullmatch(r"[A-Za-z0-9_]+", name):
                issues.append(
                    {
                        "key": "LLM_CHANNELS",
                        "code": "invalid_channel_name",
                        "message": f"LLM channel name '{name}' may only contain letters, numbers, and underscores",
                        "severity": "error",
                        "expected": "letters/numbers/underscores",
                        "actual": name,
                    }
                )
                continue

            normalized_upper = name.upper()
            if normalized_upper in seen_names:
                issues.append(
                    {
                        "key": "LLM_CHANNELS",
                        "code": "duplicate_channel_name",
                        "message": f"LLM channel '{name}' is declared more than once",
                        "severity": "error",
                        "expected": "unique channel names",
                        "actual": raw_channels,
                    }
                )
                continue

            seen_names.add(normalized_upper)
            normalized_names.append(name)

        for name in normalized_names:
            prefix = f"LLM_{name.upper()}"
            protocol_value = (effective_map.get(f"{prefix}_PROTOCOL") or "").strip()
            base_url_value = (effective_map.get(f"{prefix}_BASE_URL") or "").strip()
            api_key_value = (
                (effective_map.get(f"{prefix}_API_KEYS") or "").strip()
                or (effective_map.get(f"{prefix}_API_KEY") or "").strip()
            )
            models_value = [
                model.strip()
                for model in (effective_map.get(f"{prefix}_MODELS") or "").split(",")
                if model.strip()
            ]
            enabled = parse_env_bool(effective_map.get(f"{prefix}_ENABLED"), default=True)
            issues.extend(
                SystemConfigService._validate_llm_channel_definition(
                    channel_name=name,
                    protocol_value=protocol_value,
                    base_url_value=base_url_value,
                    api_key_value=api_key_value,
                    model_values=models_value,
                    enabled=enabled,
                    field_prefix=prefix,
                    require_complete=enabled,
                )
            )

        return issues

    @staticmethod
    def _collect_llm_channel_models_from_map(effective_map: Dict[str, str]) -> List[str]:
        """Collect normalized model names from channel-style env values."""
        raw_channels = (effective_map.get("LLM_CHANNELS") or "").strip()
        if not raw_channels:
            return []

        models: List[str] = []
        seen: Set[str] = set()
        for raw_name in raw_channels.split(","):
            name = raw_name.strip()
            if not name:
                continue

            prefix = f"LLM_{name.upper()}"
            enabled = parse_env_bool(effective_map.get(f"{prefix}_ENABLED"), default=True)
            if not enabled:
                continue

            base_url_value = (effective_map.get(f"{prefix}_BASE_URL") or "").strip()
            protocol_value = (effective_map.get(f"{prefix}_PROTOCOL") or "").strip()
            raw_models = [
                model.strip()
                for model in (effective_map.get(f"{prefix}_MODELS") or "").split(",")
                if model.strip()
            ]
            resolved_protocol = resolve_llm_channel_protocol(protocol_value, base_url=base_url_value, models=raw_models, channel_name=name)
            for model in raw_models:
                normalized_model = normalize_llm_channel_model(model, resolved_protocol, base_url_value)
                if not normalized_model or normalized_model in seen:
                    continue
                seen.add(normalized_model)
                models.append(normalized_model)

        return models

    @staticmethod
    def _uses_litellm_yaml(effective_map: Dict[str, str]) -> bool:
        """Return True when a valid LiteLLM YAML config takes precedence over channels."""
        config_path = (effective_map.get("LITELLM_CONFIG") or "").strip()
        if not config_path:
            return False
        return bool(Config._parse_litellm_yaml(config_path))

    @staticmethod
    def _collect_yaml_models_from_map(effective_map: Dict[str, str]) -> List[str]:
        """Collect declared router model names from LiteLLM YAML config."""
        config_path = (effective_map.get("LITELLM_CONFIG") or "").strip()
        if not config_path:
            return []
        return get_configured_llm_models(Config._parse_litellm_yaml(config_path))

    @staticmethod
    def _has_legacy_key_for_provider(provider: str, effective_map: Dict[str, str]) -> bool:
        """Return True when legacy env config can still back the provider."""
        normalized_provider = canonicalize_llm_channel_protocol(provider)
        if normalized_provider in {"gemini", "vertex_ai"}:
            return bool(
                (effective_map.get("GEMINI_API_KEYS") or "").strip()
                or (effective_map.get("GEMINI_API_KEY") or "").strip()
            )
        if normalized_provider == "anthropic":
            return bool(
                (effective_map.get("ANTHROPIC_API_KEYS") or "").strip()
                or (effective_map.get("ANTHROPIC_API_KEY") or "").strip()
            )
        if normalized_provider == "deepseek":
            return bool(
                (effective_map.get("DEEPSEEK_API_KEYS") or "").strip()
                or (effective_map.get("DEEPSEEK_API_KEY") or "").strip()
            )
        if normalized_provider == "openai":
            return bool(
                (effective_map.get("OPENAI_API_KEYS") or "").strip()
                or (effective_map.get("AIHUBMIX_KEY") or "").strip()
                or (effective_map.get("OPENAI_API_KEY") or "").strip()
            )
        return False

    @staticmethod
    def _has_runtime_source_for_model(model: str, effective_map: Dict[str, str]) -> bool:
        """Whether the selected model still has a backing runtime source."""
        if not model or _uses_direct_env_provider(model):
            return True
        provider = _get_litellm_provider(model)
        return SystemConfigService._has_legacy_key_for_provider(provider, effective_map)

    @staticmethod
    def _is_model_declared_by_channels(model: str, available_model_set: Set[str]) -> bool:
        """Compare a selected model against configured aliases using suffix-aware identity."""
        if not model:
            return False
        resolved_alias = resolve_configured_llm_model_alias(
            model,
            configured_models=available_model_set,
        )
        return resolved_alias in available_model_set

    @staticmethod
    def _validate_llm_runtime_selection(effective_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """Validate selected primary/fallback/vision models against configured channels."""
        issues: List[Dict[str, Any]] = []

        available_models = (
            SystemConfigService._collect_yaml_models_from_map(effective_map)
            or SystemConfigService._collect_llm_channel_models_from_map(effective_map)
        )
        available_model_set = set(available_models)
        if not available_model_set:
            raw_channels = (effective_map.get("LLM_CHANNELS") or "").strip()
            if not raw_channels:
                return issues

            configured_agent_model_raw = (effective_map.get("AGENT_LITELLM_MODEL") or "").strip()
            configured_agent_model = normalize_agent_litellm_model(
                configured_agent_model_raw,
                configured_models=available_model_set,
            )
            primary_model = (effective_map.get("LITELLM_MODEL") or "").strip()
            if primary_model and not SystemConfigService._has_runtime_source_for_model(primary_model, effective_map):
                issues.append(
                    {
                        "key": "LITELLM_MODEL",
                        "code": "missing_runtime_source",
                        "message": (
                            "LITELLM_MODEL is set, but there are no enabled channel models "
                            "or matching legacy API keys for it"
                        ),
                        "severity": "error",
                        "expected": "enabled channel model or matching legacy API key",
                        "actual": primary_model,
                    }
                )

            if (
                configured_agent_model_raw
                and configured_agent_model
                and not SystemConfigService._has_runtime_source_for_model(
                    configured_agent_model,
                    effective_map,
                )
            ):
                issues.append(
                    {
                        "key": "AGENT_LITELLM_MODEL",
                        "code": "missing_runtime_source",
                        "message": (
                            "AGENT_LITELLM_MODEL is set, but there are no enabled channel models "
                            "or matching legacy API keys for it"
                        ),
                        "severity": "error",
                        "expected": "enabled channel model or matching legacy API key",
                        "actual": configured_agent_model,
                    }
                )

            fallback_models = [
                model.strip()
                for model in (effective_map.get("LITELLM_FALLBACK_MODELS") or "").split(",")
                if model.strip()
            ]
            invalid_fallbacks = [
                model for model in fallback_models
                if not SystemConfigService._has_runtime_source_for_model(model, effective_map)
            ]
            if invalid_fallbacks:
                issues.append(
                    {
                        "key": "LITELLM_FALLBACK_MODELS",
                        "code": "missing_runtime_source",
                        "message": (
                            "LITELLM_FALLBACK_MODELS contains models without enabled channels "
                            "or matching legacy API keys"
                        ),
                        "severity": "error",
                        "expected": "enabled channel models or matching legacy API keys",
                        "actual": ", ".join(invalid_fallbacks[:3]),
                    }
                )

            vision_model = (effective_map.get("VISION_MODEL") or "").strip()
            if vision_model and not SystemConfigService._has_runtime_source_for_model(vision_model, effective_map):
                issues.append(
                    {
                        "key": "VISION_MODEL",
                        "code": "missing_runtime_source",
                        "message": (
                            "VISION_MODEL is set, but there are no enabled channel models "
                            "or matching legacy API keys for it"
                        ),
                        "severity": "warning",
                        "expected": "enabled channel model or matching legacy API key",
                        "actual": vision_model,
                    }
                )

            return issues

        primary_model = (effective_map.get("LITELLM_MODEL") or "").strip()
        if (
            primary_model
            and not SystemConfigService._is_model_declared_by_channels(primary_model, available_model_set)
            and not SystemConfigService._has_runtime_source_for_model(primary_model, effective_map)
        ):
            issues.append(
                {
                    "key": "LITELLM_MODEL",
                    "code": "unknown_model",
                    "message": (
                        "LITELLM_MODEL is not declared by the current enabled channels "
                        "and has no matching legacy API key. "
                        f"Available models: {', '.join(available_models[:6])}"
                    ),
                    "severity": "error",
                    "expected": "one configured channel model or matching legacy API key",
                    "actual": primary_model,
                }
            )

        configured_agent_model_raw = (effective_map.get("AGENT_LITELLM_MODEL") or "").strip()
        configured_agent_model = normalize_agent_litellm_model(
            configured_agent_model_raw,
            configured_models=available_model_set,
        )
        if (
            configured_agent_model_raw
            and configured_agent_model
            and not SystemConfigService._is_model_declared_by_channels(
                configured_agent_model,
                available_model_set,
            )
            and not SystemConfigService._has_runtime_source_for_model(
                configured_agent_model,
                effective_map,
            )
        ):
            issues.append(
                {
                    "key": "AGENT_LITELLM_MODEL",
                    "code": "unknown_model",
                    "message": (
                        "AGENT_LITELLM_MODEL is not declared by the current enabled channels "
                        "and has no matching legacy API key. "
                        f"Available models: {', '.join(available_models[:6])}"
                    ),
                    "severity": "error",
                    "expected": "one configured channel model or matching legacy API key",
                    "actual": configured_agent_model,
                }
            )

        fallback_models = [
            model.strip()
            for model in (effective_map.get("LITELLM_FALLBACK_MODELS") or "").split(",")
            if model.strip()
        ]
        invalid_fallbacks = [
            model for model in fallback_models
            if (
                not SystemConfigService._is_model_declared_by_channels(model, available_model_set)
                and not SystemConfigService._has_runtime_source_for_model(model, effective_map)
            )
        ]
        if invalid_fallbacks:
            issues.append(
                {
                    "key": "LITELLM_FALLBACK_MODELS",
                    "code": "unknown_model",
                    "message": (
                        "LITELLM_FALLBACK_MODELS contains models without enabled channels "
                        "or matching legacy API keys. This fallback field only accepts runtime-accessible models; "
                        "use task backup route for cross-provider failover."
                    ),
                    "severity": "error",
                    "expected": "configured channel models or matching legacy API keys",
                    "actual": ", ".join(invalid_fallbacks[:3]),
                }
            )

        vision_model = (effective_map.get("VISION_MODEL") or "").strip()
        if (
            vision_model
            and not SystemConfigService._is_model_declared_by_channels(vision_model, available_model_set)
            and not SystemConfigService._has_runtime_source_for_model(vision_model, effective_map)
        ):
            issues.append(
                {
                    "key": "VISION_MODEL",
                    "code": "unknown_model",
                    "message": (
                        "VISION_MODEL is not declared by the current enabled channels "
                        "and has no matching legacy API key"
                    ),
                    "severity": "warning",
                    "expected": "configured channel models or matching legacy API keys",
                    "actual": vision_model,
                }
            )

        return issues

    @staticmethod
    def _validate_llm_channel_definition(
        *,
        channel_name: str,
        protocol_value: str,
        base_url_value: str,
        api_key_value: str,
        model_values: Sequence[str],
        enabled: bool,
        field_prefix: str,
        require_complete: bool,
    ) -> List[Dict[str, Any]]:
        """Validate one normalized LLM channel definition."""
        issues: List[Dict[str, Any]] = []
        protocol_key = f"{field_prefix}_PROTOCOL" if field_prefix != "test_channel" else "protocol"
        base_url_key = f"{field_prefix}_BASE_URL" if field_prefix != "test_channel" else "base_url"
        api_key_key = f"{field_prefix}_API_KEY" if field_prefix != "test_channel" else "api_key"
        models_key = f"{field_prefix}_MODELS" if field_prefix != "test_channel" else "models"

        if not require_complete:
            return issues

        normalized_protocol = canonicalize_llm_channel_protocol(protocol_value)
        if normalized_protocol and normalized_protocol not in SUPPORTED_LLM_CHANNEL_PROTOCOLS:
            issues.append(
                {
                    "key": protocol_key,
                    "code": "invalid_protocol",
                    "message": (
                        f"Unsupported LLM channel protocol '{protocol_value}'. "
                        f"Supported: {', '.join(SUPPORTED_LLM_CHANNEL_PROTOCOLS)}"
                    ),
                    "severity": "error",
                    "expected": ",".join(SUPPORTED_LLM_CHANNEL_PROTOCOLS),
                    "actual": protocol_value,
                }
            )

        if base_url_value and not SystemConfigService._is_valid_url(base_url_value, allowed_schemes=("http", "https")):
            issues.append(
                {
                    "key": base_url_key,
                    "code": "invalid_url",
                    "message": "LLM channel base URL must be a valid absolute URL",
                    "severity": "error",
                    "expected": "http(s)://host",
                    "actual": base_url_value,
                }
            )
        elif base_url_value and not SystemConfigService._is_safe_base_url(base_url_value):
            issues.append(
                {
                    "key": base_url_key,
                    "code": "ssrf_blocked",
                    "message": "LLM channel base URL points to a restricted address (cloud metadata services are not allowed)",
                    "severity": "error",
                    "expected": "publicly reachable or local LLM endpoint",
                    "actual": base_url_value,
                }
            )

        resolved_protocol = resolve_llm_channel_protocol(protocol_value, base_url=base_url_value, models=list(model_values), channel_name=channel_name)
        # Validate parsed key segments so that inputs like "," or " , " are
        # treated as empty (they produce zero usable keys after split+strip).
        _parsed_api_keys = [seg.strip() for seg in api_key_value.split(",") if seg.strip()]
        if not _parsed_api_keys and not channel_allows_empty_api_key(resolved_protocol, base_url_value):
            issues.append(
                {
                    "key": api_key_key,
                    "code": "missing_api_key",
                    "message": f"LLM channel '{channel_name}' requires an API key",
                    "severity": "error",
                    "expected": "non-empty API key",
                    "actual": api_key_value,
                }
            )

        if not model_values:
            issues.append(
                {
                    "key": models_key,
                    "code": "missing_models",
                    "message": f"LLM channel '{channel_name}' requires at least one model",
                    "severity": "error",
                    "expected": "comma-separated model list",
                    "actual": "",
                }
            )
        elif not resolved_protocol:
            unresolved = [model for model in model_values if "/" not in model]
            if unresolved:
                issues.append(
                    {
                        "key": models_key,
                        "code": "missing_protocol",
                        "message": (
                            f"LLM channel '{channel_name}' uses bare model names. "
                            "Set PROTOCOL or add provider/model prefixes."
                        ),
                        "severity": "error",
                        "expected": "protocol or provider/model",
                        "actual": ", ".join(unresolved[:3]),
                    }
                )

        return issues
