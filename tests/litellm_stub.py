# -*- coding: utf-8 -*-
"""
Shared test helper to ensure imports work when litellm is unavailable.
"""

import importlib
import importlib.util
import sys
import types


def _build_inert_completion_response():
    """Return a minimal LiteLLM-like response object for offline tests."""
    return types.SimpleNamespace(
        choices=[
            types.SimpleNamespace(
                message=types.SimpleNamespace(content="", tool_calls=[]),
                finish_reason="stop",
            )
        ],
        usage=types.SimpleNamespace(
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        ),
    )


def _inert_completion(**kwargs):
    """Offline no-op completion for tests that only need import-safe behavior."""
    return _build_inert_completion_response()


class _InertRouter:  # pragma: no cover
    """Minimal Router stub for collection/offline tests."""

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    def completion(self, **kwargs):
        return _inert_completion(**kwargs)


def _resolve_litellm_module():
    """Return the installed litellm module or create a test-only stub module."""
    module = sys.modules.get("litellm")
    if module is not None:
        return module

    try:
        spec = importlib.util.find_spec("litellm")
    except ValueError:
        spec = None

    if spec is None:
        module = types.ModuleType("litellm")
        sys.modules["litellm"] = module
        return module

    try:
        return importlib.import_module("litellm")
    except Exception:
        module = sys.modules.get("litellm")
        if module is None:
            module = types.ModuleType("litellm")
            sys.modules["litellm"] = module
        return module


def ensure_litellm_stub() -> None:
    """Install missing test-safe LiteLLM symbols without overriding real ones."""
    litellm_module = _resolve_litellm_module()

    if not hasattr(litellm_module, "Router"):
        litellm_module.Router = _InertRouter

    if not hasattr(litellm_module, "completion"):
        litellm_module.completion = _inert_completion
