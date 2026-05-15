# -*- coding: utf-8 -*-
"""Helpers for exposing configured Agent model deployments."""

from __future__ import annotations

from typing import Any, Dict, List

from src.config import (
    get_effective_agent_models_to_try,
    get_effective_agent_primary_model,
    get_llm_model_identity_forms,
)


_PLACEHOLDER_TO_PROVIDER = {
    "__legacy_gemini__": "gemini",
    "__legacy_anthropic__": "anthropic",
    "__legacy_openai__": "openai",
    "__legacy_deepseek__": "deepseek",
}
_MANAGED_LEGACY_PROVIDERS = set(_PLACEHOLDER_TO_PROVIDER.values())


def _get_models_source(config) -> str:
    source = getattr(config, "llm_models_source", "")
    if source in {"litellm_config", "llm_channels", "legacy_env"}:
        return source
    return "legacy_env"


def _get_model_provider(model_name: str) -> str:
    if not model_name:
        return "unknown"
    if "/" in model_name:
        return model_name.split("/", 1)[0]
    return "openai"


def _provider_label(provider: str) -> str:
    return {
        "deepseek": "DeepSeek",
        "openai": "OpenAI",
        "gemini": "Gemini",
        "vertex_ai": "Gemini",
        "ollama": "Local",
        "local": "Local",
    }.get(provider, provider[:1].upper() + provider[1:])


def _has_configured_key(config, provider: str) -> bool:
    if provider in {"gemini", "vertex_ai"}:
        return any(k and len(k) >= 8 for k in (getattr(config, "gemini_api_keys", []) or []))
    if provider == "openai":
        return any(k and len(k) >= 8 for k in (getattr(config, "openai_api_keys", []) or []))
    if provider == "deepseek":
        return any(k and len(k) >= 8 for k in (getattr(config, "deepseek_api_keys", []) or []))
    return False


def _get_entry_identity_forms(entry: Dict[str, Any]) -> set[str]:
    forms: set[str] = set()
    deployment_name = str(entry.get("model_name") or "").strip()
    if deployment_name:
        forms.update(get_llm_model_identity_forms(deployment_name))
    params = entry.get("litellm_params", {}) or {}
    runtime_model = str(params.get("model") or "").strip()
    if runtime_model:
        forms.update(get_llm_model_identity_forms(runtime_model))
    return forms


def _append_unique_model(ordered_models: List[str], seen_forms: set[str], model: str) -> None:
    candidate = str(model or "").strip()
    candidate_forms = get_llm_model_identity_forms(candidate)
    if not candidate_forms or candidate_forms & seen_forms:
        return
    seen_forms.update(candidate_forms)
    ordered_models.append(candidate)


def _get_configured_primary_model(config) -> str:
    return (
        str(getattr(config, "agent_litellm_model", "") or "").strip()
        or str(getattr(config, "litellm_model", "") or "").strip()
    )


def _get_display_models(primary_model: str, fallback_models: List[str]) -> List[str]:
    ordered_models: List[str] = []
    seen_forms: set[str] = set()
    _append_unique_model(ordered_models, seen_forms, primary_model)
    for fallback_model in fallback_models or []:
        _append_unique_model(ordered_models, seen_forms, str(fallback_model or "").strip())
    return ordered_models


def _find_matching_entry_indexes(entries: List[Dict[str, Any]], model: str) -> List[int]:
    candidate_forms = get_llm_model_identity_forms(model)
    if not candidate_forms:
        return []
    matches: List[int] = []
    for index, entry in enumerate(entries):
        if _get_entry_identity_forms(entry) & candidate_forms:
            matches.append(index)
    return matches


def _get_non_legacy_role_indexes(config, entries: List[Dict[str, Any]]) -> tuple[set[int], set[int]]:
    primary_indexes: set[int] = set()
    for candidate in (
        _get_configured_primary_model(config),
        get_effective_agent_primary_model(config),
    ):
        matched_indexes = _find_matching_entry_indexes(entries, candidate)
        if matched_indexes:
            primary_indexes.update(matched_indexes)
            break

    fallback_indexes: set[int] = set()
    for candidate in _get_display_models("", getattr(config, "litellm_fallback_models", []) or []):
        for matched_index in _find_matching_entry_indexes(entries, candidate):
            if matched_index not in primary_indexes:
                fallback_indexes.add(matched_index)

    return primary_indexes, fallback_indexes


def _build_non_legacy_deployments(config) -> List[Dict[str, Any]]:
    source = _get_models_source(config)
    entries = [
        entry
        for entry in (getattr(config, "llm_model_list", []) or [])
        if str((entry.get("litellm_params", {}) or {}).get("model") or "").strip()
        and not str((entry.get("litellm_params", {}) or {}).get("model") or "").strip().startswith("__legacy_")
    ]
    primary_indexes, fallback_indexes = _get_non_legacy_role_indexes(config, entries)
    deployments: List[Dict[str, Any]] = []

    for index, entry in enumerate(entries):
        params = entry.get("litellm_params", {}) or {}
        model_name = str(params.get("model") or "").strip()
        api_base = params.get("api_base")
        deployment_name = entry.get("model_name")
        deployments.append(
            {
                "deployment_id": f"{source}:{index}",
                "model": model_name,
                "provider": _get_model_provider(model_name),
                "source": source,
                "api_base": str(api_base).strip() if api_base else None,
                "deployment_name": str(deployment_name).strip() if deployment_name else None,
                "is_primary": index in primary_indexes,
                "is_fallback": index in fallback_indexes,
            }
        )

    return deployments


def _build_legacy_deployments(config) -> List[Dict[str, Any]]:
    placeholder_counts = {provider: 0 for provider in _PLACEHOLDER_TO_PROVIDER.values()}
    for entry in getattr(config, "llm_model_list", []) or []:
        provider = _PLACEHOLDER_TO_PROVIDER.get(entry.get("model_name"))
        if provider:
            placeholder_counts[provider] += 1

    configured_primary_model = _get_configured_primary_model(config)
    effective_primary_model = get_effective_agent_primary_model(config)
    primary_model = configured_primary_model
    if primary_model:
        provider = _get_model_provider(primary_model)
        if provider in _MANAGED_LEGACY_PROVIDERS and placeholder_counts.get(provider, 0) <= 0:
            primary_model = effective_primary_model or primary_model
    else:
        primary_model = effective_primary_model

    ordered_models = _get_display_models(
        primary_model,
        getattr(config, "litellm_fallback_models", []) or [],
    ) or get_effective_agent_models_to_try(config)
    if not ordered_models:
        return []
    primary_model = ordered_models[0]

    deployments: List[Dict[str, Any]] = []
    seen_models = set()
    fallback_set = set(ordered_models[1:])
    for model_name in ordered_models:
        if model_name in seen_models:
            continue
        seen_models.add(model_name)

        provider = _get_model_provider(model_name)
        deployment_count = placeholder_counts.get(provider, 0)
        if deployment_count <= 0:
            # Legacy runtime still supports direct litellm calls for providers
            # whose credentials/base are resolved from environment variables
            # instead of managed placeholder deployments.
            if provider in _MANAGED_LEGACY_PROVIDERS:
                continue
            deployment_count = 1

        api_base = getattr(config, "openai_base_url", None) if provider == "openai" else None
        # Legacy runtime only load-balances the primary model via Router.
        # Fallback models call litellm directly with the first configured key,
        # so they expose at most one reachable deployment per model.
        if model_name == primary_model:
            deployment_indexes = range(deployment_count)
        else:
            deployment_indexes = range(1)

        for index in deployment_indexes:
            deployments.append(
                {
                    "deployment_id": f"legacy:{provider}:{index}:{model_name}",
                    "model": model_name,
                    "provider": provider,
                    "source": "legacy_env",
                    "api_base": api_base,
                    "deployment_name": f"legacy_{provider}_{index + 1}",
                    "is_primary": model_name == primary_model,
                    "is_fallback": model_name in fallback_set,
                }
            )

    return deployments


def list_agent_model_deployments(config) -> List[Dict[str, Any]]:
    """Return configured Agent model deployments without exposing secrets."""
    deployments = _build_non_legacy_deployments(config)
    if not deployments:
        deployments = _build_legacy_deployments(config)

    return [
        item
        for _, item in sorted(
            enumerate(deployments),
            key=lambda pair: (
                0
                if pair[1]["is_primary"]
                else 1
                if pair[1]["is_fallback"]
                else 2,
                pair[0],
            ),
        )
    ]


def list_agent_provider_health(config) -> Dict[str, Any]:
    """Return safe provider readiness metadata for the Agent UI.

    This is a configuration/readiness view only. It never probes paid APIs and
    never returns API keys, headers, or raw LiteLLM params.
    """
    deployments = list_agent_model_deployments(config)
    primary_model = get_effective_agent_primary_model(config)
    current_provider = _get_model_provider(primary_model) if primary_model else ""
    deployment_by_provider: Dict[str, Dict[str, Any]] = {}
    for deployment in deployments:
        provider = str(deployment.get("provider") or "").lower()
        if provider and (provider not in deployment_by_provider or deployment.get("is_primary")):
            deployment_by_provider[provider] = deployment

    agent_enabled = bool(config.is_agent_available())
    provider_ids = ["deepseek", "openai", "gemini", "local"]
    for provider in sorted(deployment_by_provider):
        if provider not in {"vertex_ai", "ollama"} and provider not in provider_ids:
            provider_ids.append(provider)

    providers: List[Dict[str, Any]] = []
    for provider in provider_ids:
        lookup_provider = "ollama" if provider == "local" else provider
        deployment = deployment_by_provider.get(lookup_provider) or deployment_by_provider.get(provider)
        has_key = _has_configured_key(config, lookup_provider)
        is_selected = bool(current_provider) and (
            lookup_provider == current_provider
            or (provider == "local" and current_provider in {"ollama", "local"})
        )
        if not agent_enabled:
            status = "disabled"
        elif deployment or has_key:
            status = "available"
        elif provider == "local":
            status = "offline"
        else:
            status = "not_configured"

        providers.append(
            {
                "id": provider,
                "label": _provider_label(provider),
                "status": status,
                "model": (deployment or {}).get("model") if deployment else (primary_model if is_selected else None),
                "selected": is_selected,
                "reason": None,
            }
        )

    return {
        "routing_mode": "AUTO",
        "current_provider": _provider_label(current_provider) if current_provider else None,
        "current_model": primary_model or None,
        "providers": providers,
    }
