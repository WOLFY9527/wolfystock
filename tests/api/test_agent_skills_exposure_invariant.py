# -*- coding: utf-8 -*-
"""Security invariants for the authenticated-member Agent Skills payload."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from api.v1.endpoints import agent


SAFE_RESPONSE_FIELDS = frozenset({"skills", "default_skill_id"})
SAFE_SKILL_FIELDS = frozenset({"id", "name", "description"})
UNSAFE_KEY_TOKENS = frozenset(
    {
        "prompt",
        "prompts",
        "instruction",
        "instructions",
        "tool",
        "tools",
        "entrypoint",
        "path",
        "source",
        "provider",
        "model",
        "routing",
        "environment",
        "env",
        "command",
        "credential",
        "credentials",
        "token",
        "tokens",
        "secret",
        "secrets",
    }
)


def _normalized_key_tokens(key: object) -> tuple[str, ...]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return tuple(part for part in normalized.split("_") if part)


def _assert_member_payload_has_no_unsafe_keys(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            tokens = _normalized_key_tokens(key)
            unsafe_tokens = UNSAFE_KEY_TOKENS.intersection(tokens)
            assert not unsafe_tokens, (
                f"unsafe Agent Skills key at {path}.{key}: "
                f"{', '.join(sorted(unsafe_tokens))}"
            )
            _assert_member_payload_has_no_unsafe_keys(child, path=f"{path}.{key}")
        return

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _assert_member_payload_has_no_unsafe_keys(child, path=f"{path}[{index}]")


@pytest.mark.parametrize(
    ("model_type", "payload"),
    [
        (
            agent.SkillInfo,
            {
                "id": "bull_trend",
                "name": "Bull Trend",
                "description": "Member-facing trend observation lens.",
                "instructions": "raw prompt",
            },
        ),
        (
            agent.SkillsResponse,
            {
                "skills": [],
                "default_skill_id": "",
                "provider": {"name": "internal-provider"},
            },
        ),
    ],
)
def test_member_skill_schemas_reject_extra_metadata(
    model_type: type[BaseModel],
    payload: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        model_type.model_validate(payload)


def test_member_skill_schema_is_an_explicit_positive_allowlist() -> None:
    assert set(agent.SkillInfo.model_fields) == SAFE_SKILL_FIELDS
    assert set(agent.SkillsResponse.model_fields) == SAFE_RESPONSE_FIELDS


@pytest.mark.parametrize(
    "unsafe_key",
    [
        "prompt",
        "requiredTools",
        "allowed_tools",
        "bundlePath",
        "source_path",
        "filesystem-path",
        "providerName",
        "modelRouting",
        "envVar",
        "command",
        "credential",
        "token",
        "secret",
    ],
)
def test_recursive_guard_detects_nested_unsafe_key_families(unsafe_key: str) -> None:
    payload = {"skills": [{"metadata": {"nested": {unsafe_key: "internal-value"}}}]}

    with pytest.raises(AssertionError, match="unsafe Agent Skills key"):
        _assert_member_payload_has_no_unsafe_keys(payload)


def test_member_skill_payload_keeps_safe_metadata_and_drops_nested_internal_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_manager = SimpleNamespace(
        list_skills=lambda: [
            SimpleNamespace(
                name="bull_trend",
                display_name="Bull Trend",
                description="Member-facing trend observation lens.",
                user_invocable=True,
                default_priority=10,
                default_active=True,
                prompts={"system": "raw prompt"},
                instructions="raw instructions",
                required_tools=["internal_tool"],
                allowed_tools=["internal_tool"],
                entrypoint="/private/SKILL.md",
                bundle_dir="/private",
                source="/private/SKILL.md",
                provider={"name": "internal-provider"},
                model_routing={"model": "internal-model"},
                environment={"API_TOKEN": "secret"},
                command="run-internal-agent",
            )
        ]
    )
    monkeypatch.setattr("src.agent.factory.get_skill_manager", lambda _config: skill_manager)

    payload = agent._build_skills_response(SimpleNamespace()).model_dump()

    assert set(payload) == SAFE_RESPONSE_FIELDS
    assert len(payload["skills"]) == 1
    assert set(payload["skills"][0]) == SAFE_SKILL_FIELDS
    assert payload["skills"][0] == {
        "id": "bull_trend",
        "name": "Bull Trend",
        "description": "Member-facing trend observation lens.",
    }
    assert payload["default_skill_id"] == "bull_trend"
    _assert_member_payload_has_no_unsafe_keys(payload)
