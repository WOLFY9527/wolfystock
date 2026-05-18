# -*- coding: utf-8 -*-
"""Pure helpers for privacy-safe LLM request identity semantics."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional


_SAFE_LABEL_RE = re.compile(r"[^a-z0-9_.:-]+")


@dataclass(frozen=True)
class LlmIdentityContract:
    """Hash-only identity contract for future LLM dedupe and billing semantics."""

    owner_scope: str
    scope_subject_hash: Optional[str]
    surface: str
    prompt_version: str
    prompt_fingerprint: str
    logical_context_hash: str
    logical_request_hash: str
    billable_attempt_hash: str
    retry_attempt_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "ownerScope": self.owner_scope,
            "scopeSubjectHash": self.scope_subject_hash,
            "surface": self.surface,
            "promptVersion": self.prompt_version,
            "promptFingerprint": self.prompt_fingerprint,
            "logicalContextHash": self.logical_context_hash,
            "logicalRequestHash": self.logical_request_hash,
            "billableAttemptHash": self.billable_attempt_hash,
            "retryAttemptIndex": self.retry_attempt_index,
        }

    def to_ledger_metadata(self) -> dict[str, Any]:
        """Return sanitizer-safe additive metadata for non-mutating ledger attachment."""
        return {
            "llm_identity": {
                "owner_scope": self.owner_scope,
                "scope_subject_hash": self.scope_subject_hash,
                "surface": self.surface,
                "version": self.prompt_version,
                "template_hash": self.prompt_fingerprint,
                "context_hash": self.logical_context_hash,
                "logical_hash": self.logical_request_hash,
                "attempt_hash": self.billable_attempt_hash,
                "retry_index": self.retry_attempt_index,
            }
        }


def build_llm_identity_contract(
    *,
    owner_user_id: Optional[str] = None,
    guest_bucket_hash: Optional[str] = None,
    surface: str,
    prompt_version: str,
    prompt_text: str,
    logical_context: Optional[Mapping[str, Any]] = None,
    retry_attempt_index: int = 0,
) -> LlmIdentityContract:
    owner_key = _normalize_optional(owner_user_id)
    guest_key = _normalize_optional(guest_bucket_hash)
    if owner_key and guest_key:
        raise ValueError("owner_user_id and guest_bucket_hash are mutually exclusive")

    owner_scope = "owner" if owner_key else "guest" if guest_key else "global"
    scope_subject_hash = _hash_text(f"{owner_scope}:{owner_key or guest_key}") if (owner_key or guest_key) else None
    normalized_surface = _safe_label(surface, default="analysis")
    normalized_prompt_version = _safe_label(prompt_version, default="unversioned")
    normalized_retry_attempt_index = max(0, int(retry_attempt_index or 0))
    prompt_fingerprint = _hash_text(str(prompt_text or ""))
    logical_context_hash = _hash_json(_normalize_value(logical_context or {}))

    logical_request_hash = _hash_json(
        {
            "schema": "llm_identity_contract_v1",
            "owner_scope": owner_scope,
            "scope_subject_hash": scope_subject_hash,
            "surface": normalized_surface,
            "prompt_version": normalized_prompt_version,
            "prompt_fingerprint": prompt_fingerprint,
            "logical_context_hash": logical_context_hash,
        }
    )
    billable_attempt_hash = _hash_json(
        {
            "schema": "llm_identity_contract_v1",
            "logical_request_hash": logical_request_hash,
            "retry_attempt_index": normalized_retry_attempt_index,
        }
    )

    return LlmIdentityContract(
        owner_scope=owner_scope,
        scope_subject_hash=scope_subject_hash,
        surface=normalized_surface,
        prompt_version=normalized_prompt_version,
        prompt_fingerprint=prompt_fingerprint,
        logical_context_hash=logical_context_hash,
        logical_request_hash=logical_request_hash,
        billable_attempt_hash=billable_attempt_hash,
        retry_attempt_index=normalized_retry_attempt_index,
    )


def _normalize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, set):
        return [_normalize_value(item) for item in sorted(value, key=lambda item: json.dumps(_normalize_value(item), sort_keys=True, ensure_ascii=True))]
    return str(value).strip()


def _normalize_optional(value: Optional[str]) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _safe_label(value: Any, *, default: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return default
    normalized = _SAFE_LABEL_RE.sub("_", text).strip("_.:-")
    return normalized or default


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def _hash_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return _hash_text(payload)
