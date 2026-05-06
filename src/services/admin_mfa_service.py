# -*- coding: utf-8 -*-
"""Admin MFA foundation helpers.

This phase intentionally keeps login enforcement disabled. TOTP secret handling
is a scaffold until a production encryption service is approved.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from urllib.parse import quote

from src.repositories.auth_repo import AuthRepository


MFA_ISSUER = "WolfyStock"
MFA_SECRET_REF_ENCRYPTED_PREFIX: Final = "$wolfystock$mfa-secret=v1$"
MFA_SECRET_REF_TEST_PREFIX = "test-only:"
MFA_SECRET_REF_PLACEHOLDER_PREFIX = "placeholder-sha256:"
MFA_RECOVERY_CODE_COUNT = 10
MFA_RECOVERY_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MFA_RECOVERY_CODES_VERSION = 1
MFA_SECRET_KEY_ENV = "WOLFYSTOCK_MFA_SECRET_ENCRYPTION_KEY"
MFA_SECRET_KEY_ID_ENV = "WOLFYSTOCK_MFA_SECRET_KEY_ID"
MFA_SECRET_ENCRYPTION_ALG = "aes-256-gcm"


@dataclass(frozen=True, repr=False)
class MfaEnrollmentChallenge:
    secret: str
    secret_ref: str
    provisioning_uri: str
    storage_mode: str


@dataclass(frozen=True)
class RecoveryCodeBatch:
    codes: list[str]
    generated_at: datetime
    remaining_count: int


@dataclass(frozen=True)
class RecoveryCodeVerification:
    verified: bool
    remaining_count: int


class MfaSecretStorageUnavailable(RuntimeError):
    """Raised when a recoverable TOTP secret cannot be stored safely."""


class MfaSecretStorageInvalid(RuntimeError):
    """Raised when encrypted MFA secret metadata cannot be resolved safely."""


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


def _normalize_recovery_code(code: str | None) -> str:
    return "".join(ch for ch in str(code or "").strip().upper() if ch.isalnum())


def _new_totp_secret() -> str:
    configured = str(os.getenv("WOLFYSTOCK_MFA_TEST_SECRET") or "").strip()
    if configured:
        return configured
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _configured_mfa_secret_key() -> tuple[bytes, str] | None:
    raw_key = str(os.getenv(MFA_SECRET_KEY_ENV) or "").strip()
    if not raw_key:
        return None
    if raw_key.startswith("base64:"):
        try:
            key = _b64url_decode(raw_key.removeprefix("base64:").strip())
        except Exception as exc:
            raise MfaSecretStorageUnavailable("mfa_secret_storage_key_invalid") from exc
    else:
        key = raw_key.encode("utf-8")
    if len(key) < 32:
        raise MfaSecretStorageUnavailable("mfa_secret_storage_key_invalid")
    key_id = str(os.getenv(MFA_SECRET_KEY_ID_ENV) or "local").strip() or "local"
    return key, key_id


def _derive_mfa_secret_key(master_key: bytes, purpose: bytes) -> bytes:
    return hmac.new(master_key, b"wolfystock:mfa-secret:" + purpose, hashlib.sha256).digest()


def _parse_secret_ref_fields(secret_ref: str) -> dict[str, str] | None:
    value = str(secret_ref or "").strip()
    if not value.startswith(MFA_SECRET_REF_ENCRYPTED_PREFIX):
        return None
    fields: dict[str, str] = {}
    for part in value.removeprefix(MFA_SECRET_REF_ENCRYPTED_PREFIX).split("$"):
        if "=" not in part:
            return None
        key, raw = part.split("=", 1)
        if not key or key in fields:
            return None
        fields[key] = raw
    return fields


def _encrypt_mfa_secret(secret: str) -> str:
    configured_key = _configured_mfa_secret_key()
    if configured_key is None:
        raise MfaSecretStorageUnavailable("mfa_secret_storage_key_missing")

    master_key, key_id = configured_key
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except Exception as exc:
        raise MfaSecretStorageUnavailable("mfa_secret_storage_crypto_unavailable") from exc

    aes_key = _derive_mfa_secret_key(master_key, b"aes-gcm-v1")
    nonce = secrets.token_bytes(12)
    kid = _b64url_encode(key_id.encode("utf-8"))
    aad = f"v=1|mode=encrypted|kid={kid}|alg={MFA_SECRET_ENCRYPTION_ALG}".encode("utf-8")
    ciphertext = AESGCM(aes_key).encrypt(nonce, secret.encode("utf-8"), aad)
    return (
        f"{MFA_SECRET_REF_ENCRYPTED_PREFIX}"
        f"mode=encrypted$kid={kid}$alg={MFA_SECRET_ENCRYPTION_ALG}"
        f"$nonce={_b64url_encode(nonce)}$ciphertext={_b64url_encode(ciphertext)}"
    )


def _decrypt_mfa_secret_ref(secret_ref: str) -> str | None:
    fields = _parse_secret_ref_fields(secret_ref)
    if fields is None:
        return None
    if fields.get("mode") != "encrypted" or fields.get("alg") != MFA_SECRET_ENCRYPTION_ALG:
        raise MfaSecretStorageInvalid("mfa_secret_storage_ref_unsupported")

    configured_key = _configured_mfa_secret_key()
    if configured_key is None:
        raise MfaSecretStorageInvalid("mfa_secret_storage_key_missing")
    master_key, key_id = configured_key
    expected_kid = _b64url_encode(key_id.encode("utf-8"))
    if not hmac.compare_digest(fields.get("kid") or "", expected_kid):
        raise MfaSecretStorageInvalid("mfa_secret_storage_key_mismatch")
    try:
        nonce = _b64url_decode(fields["nonce"])
        ciphertext = _b64url_decode(fields["ciphertext"])
    except Exception as exc:
        raise MfaSecretStorageInvalid("mfa_secret_storage_ref_malformed") from exc

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except Exception as exc:
        raise MfaSecretStorageInvalid("mfa_secret_storage_crypto_unavailable") from exc

    aes_key = _derive_mfa_secret_key(master_key, b"aes-gcm-v1")
    aad = (
        f"v=1|mode=encrypted|kid={fields['kid']}|alg={MFA_SECRET_ENCRYPTION_ALG}"
    ).encode("utf-8")
    try:
        return AESGCM(aes_key).decrypt(nonce, ciphertext, aad).decode("utf-8")
    except Exception as exc:
        raise MfaSecretStorageInvalid("mfa_secret_storage_ref_invalid") from exc


def _looks_like_legacy_plaintext_secret(value: str) -> bool:
    normalized = value.strip().replace(" ", "").upper()
    if len(normalized) < 16:
        return False
    return normalized == value.strip().upper() and _b32decode_secret(normalized) is not None


def _secret_ref_for_storage(secret: str) -> tuple[str, str]:
    configured = str(os.getenv("WOLFYSTOCK_MFA_TEST_SECRET") or "").strip()
    if configured and hmac.compare_digest(secret, configured):
        return f"{MFA_SECRET_REF_TEST_PREFIX}{secret}", "test_only_secret"
    return _encrypt_mfa_secret(secret), "encrypted_v1"


def _secret_from_ref(secret_ref: str | None) -> str | None:
    value = str(secret_ref or "").strip()
    if value.startswith(MFA_SECRET_REF_ENCRYPTED_PREFIX):
        return _decrypt_mfa_secret_ref(value)
    if value.startswith(MFA_SECRET_REF_TEST_PREFIX):
        return value.removeprefix(MFA_SECRET_REF_TEST_PREFIX)
    if value.startswith(MFA_SECRET_REF_PLACEHOLDER_PREFIX):
        return None
    if _looks_like_legacy_plaintext_secret(value):
        return value
    return None


def _hash_recovery_code(code: str) -> str:
    from src.auth import hash_password_for_storage

    return hash_password_for_storage(_normalize_recovery_code(code))


def _verify_recovery_code_hash(code: str, stored_hash: str | None) -> bool:
    from src.auth import verify_password_hash_string

    normalized = _normalize_recovery_code(code)
    if not normalized or not stored_hash:
        return False
    return verify_password_hash_string(normalized, stored_hash)


def _new_recovery_code() -> str:
    raw = "".join(secrets.choice(MFA_RECOVERY_CODE_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def _empty_recovery_envelope() -> dict:
    return {"version": MFA_RECOVERY_CODES_VERSION, "sets": []}


def _load_recovery_envelope(raw: str | None) -> dict:
    if not raw:
        return _empty_recovery_envelope()
    try:
        parsed = json.loads(str(raw))
    except Exception:
        return _empty_recovery_envelope()
    if not isinstance(parsed, dict) or parsed.get("version") != MFA_RECOVERY_CODES_VERSION:
        return _empty_recovery_envelope()
    sets = parsed.get("sets")
    if not isinstance(sets, list):
        return _empty_recovery_envelope()
    return {"version": MFA_RECOVERY_CODES_VERSION, "sets": sets}


def _dump_recovery_envelope(envelope: dict) -> str:
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"))


def _active_recovery_set(envelope: dict) -> dict | None:
    for recovery_set in reversed(envelope.get("sets") or []):
        if isinstance(recovery_set, dict) and not recovery_set.get("replaced_at"):
            return recovery_set
    return None


def _remaining_recovery_count(envelope: dict) -> int:
    active_set = _active_recovery_set(envelope)
    if not active_set:
        return 0
    codes = active_set.get("codes") or []
    return sum(1 for entry in codes if isinstance(entry, dict) and not entry.get("used_at"))


def _update_mfa_preserving_fields(*, repo: AuthRepository, user_id: str, **updates):
    row = repo.get_app_user(user_id)
    if row is None:
        return None
    values = {
        "mfa_enabled": bool(getattr(row, "mfa_enabled", False)),
        "mfa_secret_ref": getattr(row, "mfa_secret_ref", None),
        "mfa_recovery_codes_hash": getattr(row, "mfa_recovery_codes_hash", None),
        "mfa_created_at": getattr(row, "mfa_created_at", None),
        "mfa_enabled_at": getattr(row, "mfa_enabled_at", None),
        "mfa_last_verified_at": getattr(row, "mfa_last_verified_at", None),
    }
    values.update(updates)
    return repo.update_app_user_mfa(user_id=user_id, **values)


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
    try:
        secret = _secret_from_ref(secret_ref)
    except MfaSecretStorageInvalid:
        return False
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
    repo = repo or AuthRepository()
    return _update_mfa_preserving_fields(
        repo=repo,
        user_id=user_id,
        mfa_enabled=True,
        mfa_secret_ref=secret_ref,
        mfa_enabled_at=now,
        mfa_last_verified_at=now,
    )


def record_mfa_verification(*, user_id: str, secret_ref: str | None, enabled: bool, repo: AuthRepository | None = None):
    """Record successful MFA verification without changing enforcement state."""
    repo = repo or AuthRepository()
    return _update_mfa_preserving_fields(
        repo=repo,
        user_id=user_id,
        mfa_enabled=enabled,
        mfa_secret_ref=secret_ref,
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


def generate_recovery_codes(
    *,
    user_id: str,
    repo: AuthRepository | None = None,
    count: int = MFA_RECOVERY_CODE_COUNT,
) -> RecoveryCodeBatch | None:
    """Generate one-time recovery codes and persist only salted hashes."""
    repo = repo or AuthRepository()
    user_row = repo.get_app_user(user_id)
    if user_row is None or not getattr(user_row, "mfa_enabled", False):
        return None

    now = datetime.now()
    now_iso = now.isoformat()
    plaintext_codes = [_new_recovery_code() for _ in range(count)]
    envelope = _load_recovery_envelope(getattr(user_row, "mfa_recovery_codes_hash", None))
    for recovery_set in envelope["sets"]:
        if isinstance(recovery_set, dict) and not recovery_set.get("replaced_at"):
            recovery_set["replaced_at"] = now_iso
    envelope["sets"].append(
        {
            "generated_at": now_iso,
            "replaced_at": None,
            "codes": [
                {
                    "hash": _hash_recovery_code(code),
                    "generated_at": now_iso,
                    "used_at": None,
                }
                for code in plaintext_codes
            ],
        }
    )
    _update_mfa_preserving_fields(
        repo=repo,
        user_id=user_id,
        mfa_recovery_codes_hash=_dump_recovery_envelope(envelope),
    )
    return RecoveryCodeBatch(
        codes=plaintext_codes,
        generated_at=now,
        remaining_count=_remaining_recovery_count(envelope),
    )


def verify_recovery_code(
    *,
    user_id: str,
    code: str | None,
    repo: AuthRepository | None = None,
) -> RecoveryCodeVerification:
    """Verify and consume one active recovery code."""
    repo = repo or AuthRepository()
    user_row = repo.get_app_user(user_id)
    if user_row is None or not getattr(user_row, "mfa_enabled", False):
        return RecoveryCodeVerification(verified=False, remaining_count=0)

    envelope = _load_recovery_envelope(getattr(user_row, "mfa_recovery_codes_hash", None))
    active_set = _active_recovery_set(envelope)
    if not active_set:
        return RecoveryCodeVerification(verified=False, remaining_count=0)

    now_iso = datetime.now().isoformat()
    for entry in active_set.get("codes") or []:
        if not isinstance(entry, dict) or entry.get("used_at"):
            continue
        if _verify_recovery_code_hash(code or "", entry.get("hash")):
            entry["used_at"] = now_iso
            _update_mfa_preserving_fields(
                repo=repo,
                user_id=user_id,
                mfa_recovery_codes_hash=_dump_recovery_envelope(envelope),
                mfa_last_verified_at=datetime.now(),
            )
            return RecoveryCodeVerification(
                verified=True,
                remaining_count=_remaining_recovery_count(envelope),
            )
    return RecoveryCodeVerification(
        verified=False,
        remaining_count=_remaining_recovery_count(envelope),
    )
