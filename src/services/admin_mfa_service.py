# -*- coding: utf-8 -*-
"""Admin MFA foundation helpers.

This phase intentionally keeps login enforcement disabled. TOTP secret handling
is a scaffold until a production encryption service is approved.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

from src.repositories.auth_repo import AuthRepository


MFA_ISSUER = "WolfyStock"
MFA_SECRET_REF_TEST_PREFIX = "test-only:"
MFA_SECRET_REF_PLACEHOLDER_PREFIX = "placeholder-sha256:"


@dataclass(frozen=True)
class MfaEnrollmentChallenge:
    secret: str
    secret_ref: str
    provisioning_uri: str
    storage_mode: str


def _b32decode_secret(secret: str) -> bytes | None:
    normalized = str(secret or "").strip().replace(" ", "").upper()
    if not normalized:
        return None
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    try:
        return base64.b32decode(normalized + padding, casefold=True)
    except Exception:
        return None


def _totp_code(secret: str, *, for_time: int | None = None, step_seconds: int = 30) -> str | None:
    key = _b32decode_secret(secret)
    if not key:
        return None
    counter = int((for_time or time.time()) // step_seconds)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset: offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def _normalize_code(code: str | None) -> str:
    return "".join(ch for ch in str(code or "").strip() if ch.isdigit())


def _new_totp_secret() -> str:
    configured = str(os.getenv("WOLFYSTOCK_MFA_TEST_SECRET") or "").strip()
    if configured:
        return configured
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _secret_ref_for_storage(secret: str) -> tuple[str, str]:
    configured = str(os.getenv("WOLFYSTOCK_MFA_TEST_SECRET") or "").strip()
    if configured and hmac.compare_digest(secret, configured):
        return f"{MFA_SECRET_REF_TEST_PREFIX}{secret}", "test_only_secret"
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    return f"{MFA_SECRET_REF_PLACEHOLDER_PREFIX}{digest}", "hash_only_scaffold"


def _secret_from_ref(secret_ref: str | None) -> str | None:
    value = str(secret_ref or "").strip()
    if value.startswith(MFA_SECRET_REF_TEST_PREFIX):
        return value.removeprefix(MFA_SECRET_REF_TEST_PREFIX)
    return None


def create_enrollment_challenge(*, username: str, repo: AuthRepository | None = None, user_id: str) -> MfaEnrollmentChallenge:
    """Create a pending enrollment challenge and persist non-response metadata."""
    secret = _new_totp_secret()
    secret_ref, storage_mode = _secret_ref_for_storage(secret)
    now = datetime.now()
    repo = repo or AuthRepository()
    repo.update_app_user_mfa(
        user_id=user_id,
        mfa_enabled=False,
        mfa_secret_ref=secret_ref,
        mfa_recovery_codes_hash=None,
        mfa_created_at=now,
        mfa_enabled_at=None,
        mfa_last_verified_at=None,
    )
    label = quote(f"{MFA_ISSUER}:{username}")
    issuer = quote(MFA_ISSUER)
    provisioning_uri = f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
    return MfaEnrollmentChallenge(
        secret=secret,
        secret_ref=secret_ref,
        provisioning_uri=provisioning_uri,
        storage_mode=storage_mode,
    )


def verify_totp_code(*, secret_ref: str | None, code: str | None) -> bool:
    """Verify a TOTP code when the scaffold has a recoverable test secret."""
    normalized_code = _normalize_code(code)
    if len(normalized_code) != 6:
        return False
    secret = _secret_from_ref(secret_ref)
    if not secret:
        return False
    current = int(time.time())
    for offset in (-30, 0, 30):
        expected = _totp_code(secret, for_time=current + offset)
        if expected and hmac.compare_digest(normalized_code, expected):
            return True
    return False


def enable_mfa(*, user_id: str, secret_ref: str | None, repo: AuthRepository | None = None):
    """Enable MFA after enrollment verification succeeds."""
    now = datetime.now()
    return (repo or AuthRepository()).update_app_user_mfa(
        user_id=user_id,
        mfa_enabled=True,
        mfa_secret_ref=secret_ref,
        mfa_recovery_codes_hash=None,
        mfa_enabled_at=now,
        mfa_last_verified_at=now,
    )


def record_mfa_verification(*, user_id: str, secret_ref: str | None, enabled: bool, repo: AuthRepository | None = None):
    """Record successful MFA verification without changing enforcement state."""
    return (repo or AuthRepository()).update_app_user_mfa(
        user_id=user_id,
        mfa_enabled=enabled,
        mfa_secret_ref=secret_ref,
        mfa_recovery_codes_hash=None,
        mfa_last_verified_at=datetime.now(),
    )


def disable_mfa(*, user_id: str, repo: AuthRepository | None = None):
    """Disable MFA and clear the scaffold secret reference."""
    return (repo or AuthRepository()).update_app_user_mfa(
        user_id=user_id,
        mfa_enabled=False,
        mfa_secret_ref=None,
        mfa_recovery_codes_hash=None,
        mfa_created_at=None,
        mfa_enabled_at=None,
        mfa_last_verified_at=None,
    )
