#!/usr/bin/env python3
"""Sanitized production configuration readiness preflight.

This helper consumes a synthetic or operator-sanitized contract. It does not
read real .env files, print secret values, mutate runtime defaults, or call
external services.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "wolfystock_production_config_readiness_v1"
INPUT_SCHEMA_VERSION = "wolfystock_production_config_contract_input_v1"

REQUIRED_FLAG_NAMES = (
    "APP_ENV",
    "ADMIN_AUTH_ENABLED",
    "CORS_ALLOW_ALL",
    "CORS_ORIGINS",
    "CSRF_TRUSTED_ORIGINS",
    "TRUST_X_FORWARDED_FOR",
    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED",
    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_SCOPE",
    "WOLFYSTOCK_MFA_LOGIN_BREAK_GLASS_ENABLED",
    "WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED",
    "WOLFYSTOCK_QUOTA_ENFORCEMENT_MODE",
    "WOLFYSTOCK_BACKUP_PITR_EXECUTION_ENABLED",
    "WOLFYSTOCK_STAGING_INGRESS_SMOKE",
    "SEARXNG_PUBLIC_INSTANCES_ENABLED",
    "CRYPTO_REALTIME_ENABLED",
)

SECRET_GROUPS: dict[str, tuple[str, ...]] = {
    "llm_provider": (
        "GEMINI_API_KEY",
        "GEMINI_API_KEYS",
        "OPENAI_API_KEY",
        "OPENAI_API_KEYS",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_API_KEYS",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_API_KEYS",
    ),
    "market_data_provider": (
        "FMP_API_KEY",
        "FMP_API_KEYS",
        "FINNHUB_API_KEY",
        "FINNHUB_API_KEYS",
        "ALPHA_VANTAGE_API_KEY",
        "FRED_API_KEY",
        "TWELVE_DATA_API_KEY",
        "TWELVE_DATA_API_KEYS",
        "TUSHARE_TOKEN",
        "ALPACA_API_KEY_ID",
        "ALPACA_API_SECRET_KEY",
    ),
    "options_live_provider": (
        "TRADIER_API_TOKEN",
        "TRADIER_SANDBOX_API_TOKEN",
    ),
}

SECRET_STATE_VALUES = {"missing", "present", "sanitized"}
TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
FALSE_VALUES = {"0", "false", "no", "off", "disabled"}
QUOTA_MODES = {"disabled", "advisory", "pilot", "enforced"}
SANITIZED_PRESENCE_LABELS = {"configured", "redacted", "redacted only"}


def _empty_contract() -> dict[str, Any]:
    return {
        "schemaVersion": INPUT_SCHEMA_VERSION,
        "mode": "synthetic_empty",
        "flags": {},
        "secretPresence": {},
    }


def _load_contract(path: str | None) -> dict[str, Any]:
    if not path:
        return _empty_contract()
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[FAIL] Contract file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[FAIL] Contract file is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        raise SystemExit("[FAIL] Contract file must contain a JSON object")
    return payload


def _norm(value: Any) -> str:
    return str(value if value is not None else "").strip().lower()


def _flag_present(flags: dict[str, Any], name: str) -> bool:
    return name in flags and str(flags.get(name) if flags.get(name) is not None else "").strip() != ""


def _flag_bool(flags: dict[str, Any], name: str) -> bool | None:
    if not _flag_present(flags, name):
        return None
    value = _norm(flags.get(name))
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return None


def _presence_label(flags: dict[str, Any], name: str) -> str:
    if not _flag_present(flags, name):
        return "missing"
    value = _norm(flags.get(name)).replace("_", " ")
    if value in SANITIZED_PRESENCE_LABELS:
        return "configured"
    return "invalid_raw_value"


def _secret_state(raw: Any) -> tuple[str, str | None]:
    if isinstance(raw, bool):
        return ("present" if raw else "missing"), None
    normalized = _norm(raw)
    if normalized in SECRET_STATE_VALUES:
        return normalized, None
    if normalized in TRUE_VALUES:
        return "present", None
    if normalized in FALSE_VALUES or normalized == "":
        return "missing", None
    return "present", "secret_presence_not_boolean_or_state"


def _status(ok: bool) -> str:
    return "pass" if ok else "fail"


def _required_flags_check(flags: dict[str, Any]) -> dict[str, Any]:
    missing = [name for name in REQUIRED_FLAG_NAMES if not _flag_present(flags, name)]
    return {
        "id": "required_launch_config_names",
        "status": _status(not missing),
        "evidence": {
            "requiredNames": list(REQUIRED_FLAG_NAMES),
            "missingNames": missing,
            "valuesIncluded": False,
        },
    }


def _admin_auth_enabled_check(flags: dict[str, Any]) -> dict[str, Any]:
    auth_enabled = _flag_bool(flags, "ADMIN_AUTH_ENABLED")
    state = "enabled" if auth_enabled is True else "disabled" if auth_enabled is False else "missing_or_invalid"
    return {
        "id": "admin_auth_enabled_for_public_deploy",
        "status": _status(auth_enabled is True),
        "evidence": {
            "flagName": "ADMIN_AUTH_ENABLED",
            "state": state,
            "authDisabledPublicIngressSafe": False,
            "runtimeDefaultChanged": False,
            "valuesIncluded": False,
        },
    }


def _production_mode_check(flags: dict[str, Any]) -> dict[str, Any]:
    mode = _norm(flags.get("APP_ENV"))
    state = "production" if mode == "production" else "missing_or_non_production"
    return {
        "id": "production_mode_explicit",
        "status": _status(mode == "production"),
        "evidence": {
            "flagName": "APP_ENV",
            "state": state,
            "runtimeDefaultChanged": False,
            "valuesIncluded": False,
        },
    }


def _cors_csrf_posture_check(flags: dict[str, Any]) -> dict[str, Any]:
    cors_allow_all = _flag_bool(flags, "CORS_ALLOW_ALL")
    cors_state = "disabled" if cors_allow_all is False else "enabled_or_missing"
    origins_state = _presence_label(flags, "CORS_ORIGINS")
    csrf_state = _presence_label(flags, "CSRF_TRUSTED_ORIGINS")
    ok = cors_allow_all is False and origins_state == "configured" and csrf_state == "configured"
    return {
        "id": "cors_csrf_origin_posture",
        "status": _status(ok),
        "evidence": {
            "corsAllowAllState": cors_state,
            "corsOriginsState": origins_state,
            "csrfTrustedOriginsState": csrf_state,
            "rawOriginValuesIncluded": False,
            "valuesIncluded": False,
        },
    }


def _trusted_proxy_posture_check(flags: dict[str, Any]) -> dict[str, Any]:
    trust_proxy = _flag_bool(flags, "TRUST_X_FORWARDED_FOR")
    state = "missing_or_invalid"
    if trust_proxy is True:
        state = "enabled_trusted_proxy_required"
    elif trust_proxy is False:
        state = "disabled"
    return {
        "id": "trusted_proxy_posture_explicit",
        "status": _status(trust_proxy is not None),
        "evidence": {
            "flagName": "TRUST_X_FORWARDED_FOR",
            "state": state,
            "rawProxyHostIncluded": False,
            "runtimeDefaultChanged": False,
            "valuesIncluded": False,
        },
    }


def _security_posture_checks(flags: dict[str, Any]) -> list[dict[str, Any]]:
    mfa_enabled = _flag_bool(flags, "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED")
    break_glass = _flag_bool(flags, "WOLFYSTOCK_MFA_LOGIN_BREAK_GLASS_ENABLED")
    raw_scope = _norm(flags.get("WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_SCOPE")).replace("-", "_")
    scope = "admin_only" if raw_scope in {"admin", "admins", "admin_only"} else "unsupported"
    mode = "missing"
    if mfa_enabled is False:
        mode = "disabled"
    elif mfa_enabled is True and scope == "admin_only":
        mode = "admin_pilot"
    elif mfa_enabled is True:
        mode = "unsupported"
    mfa_ok = mfa_enabled is not None and break_glass is not None and scope == "admin_only" and break_glass is False

    fallback = _flag_bool(flags, "WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED")
    fallback_state = "missing"
    if fallback is True:
        fallback_state = "compatibility_enabled"
    elif fallback is False:
        fallback_state = "disabled"

    return [
        {
            "id": "mfa_rollout_mode_explicit",
            "status": _status(mfa_ok),
            "evidence": {
                "mode": mode,
                "supportedModes": ["disabled", "admin_pilot"],
                "unsupportedGlobalModeFailsClosedInEvidence": scope == "unsupported",
                "breakGlassDefault": "disabled" if break_glass is False else "enabled_or_missing",
                "valuesIncluded": False,
            },
        },
        {
            "id": "rbac_coarse_fallback_disable_flag",
            "status": _status(fallback is not None),
            "evidence": {
                "flagName": "WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED",
                "state": fallback_state,
                "runtimeDefaultChanged": False,
                "valuesIncluded": False,
            },
        },
    ]


def _provider_credential_check(secret_presence: dict[str, Any]) -> dict[str, Any]:
    group_evidence = []
    contract_issues = []
    required_groups_present = True
    for group, names in SECRET_GROUPS.items():
        states_by_name = {}
        for name in names:
            state, issue = _secret_state(secret_presence.get(name))
            states_by_name[name] = state
            if issue:
                contract_issues.append({"name": name, "reasonCode": issue})
        group_present = any(state in {"present", "sanitized"} for state in states_by_name.values())
        if group != "options_live_provider":
            required_groups_present = required_groups_present and group_present
        group_evidence.append(
            {
                "group": group,
                "state": "present" if group_present else "missing",
                "credentialNames": list(names),
                "statesByName": states_by_name,
                "valuesIncluded": False,
            }
        )
    ok = required_groups_present and not contract_issues
    return {
        "id": "provider_live_credential_contract",
        "status": _status(ok),
        "evidence": {
            "groups": group_evidence,
            "contractIssues": contract_issues,
            "rawCredentialValuesIncluded": False,
        },
    }


def _quota_check(flags: dict[str, Any]) -> dict[str, Any]:
    raw_mode = _norm(flags.get("WOLFYSTOCK_QUOTA_ENFORCEMENT_MODE"))
    aliases = {"dry_run": "advisory", "enabled": "pilot"}
    mode = aliases.get(raw_mode, raw_mode)
    return {
        "id": "quota_enforcement_mode_explicit",
        "status": _status(mode in QUOTA_MODES),
        "evidence": {
            "mode": mode or "missing",
            "supportedModes": sorted(QUOTA_MODES),
            "runtimeDefaultChanged": False,
            "valuesIncluded": False,
        },
    }


def _deployment_opt_in_checks(flags: dict[str, Any]) -> list[dict[str, Any]]:
    backup_enabled = _flag_bool(flags, "WOLFYSTOCK_BACKUP_PITR_EXECUTION_ENABLED")
    ingress_enabled = _flag_bool(flags, "WOLFYSTOCK_STAGING_INGRESS_SMOKE")
    return [
        {
            "id": "backup_pitr_execution_opt_in_disabled_by_default",
            "status": _status(backup_enabled is False),
            "evidence": {
                "flagName": "WOLFYSTOCK_BACKUP_PITR_EXECUTION_ENABLED",
                "state": "disabled" if backup_enabled is False else "enabled_or_missing",
                "runtimeDefaultChanged": False,
                "valuesIncluded": False,
            },
        },
        {
            "id": "staging_ingress_live_opt_in_disabled_by_default",
            "status": _status(ingress_enabled is False),
            "evidence": {
                "flagName": "WOLFYSTOCK_STAGING_INGRESS_SMOKE",
                "state": "disabled" if ingress_enabled is False else "enabled_or_missing",
                "networkCallsEnabled": False,
                "valuesIncluded": False,
            },
        },
    ]


def _public_instance_posture_checks(flags: dict[str, Any]) -> list[dict[str, Any]]:
    public_searxng = _flag_bool(flags, "SEARXNG_PUBLIC_INSTANCES_ENABLED")
    crypto_realtime = _flag_bool(flags, "CRYPTO_REALTIME_ENABLED")

    searxng_state = "missing_or_invalid"
    if public_searxng is True:
        searxng_state = "enabled_public_instance_no_go"
    elif public_searxng is False:
        searxng_state = "disabled"

    crypto_state = "missing_or_invalid"
    if crypto_realtime is True:
        crypto_state = "enabled_review_required"
    elif crypto_realtime is False:
        crypto_state = "disabled"

    return [
        {
            "id": "public_searxng_instance_posture",
            "status": _status(public_searxng is False),
            "evidence": {
                "flagName": "SEARXNG_PUBLIC_INSTANCES_ENABLED",
                "state": searxng_state,
                "publicInstanceLaunchApproved": False,
                "valuesIncluded": False,
            },
        },
        {
            "id": "crypto_realtime_decision_posture",
            "status": _status(crypto_realtime is not None),
            "evidence": {
                "flagName": "CRYPTO_REALTIME_ENABLED",
                "state": crypto_state,
                "externalProviderCallsByChecker": False,
                "valuesIncluded": False,
            },
        },
    ]


def build_readiness(contract: dict[str, Any]) -> dict[str, Any]:
    flags = contract.get("flags") if isinstance(contract.get("flags"), dict) else {}
    secret_presence = contract.get("secretPresence") if isinstance(contract.get("secretPresence"), dict) else {}
    checks = [
        _required_flags_check(flags),
        _production_mode_check(flags),
        _admin_auth_enabled_check(flags),
        _cors_csrf_posture_check(flags),
        _trusted_proxy_posture_check(flags),
        *_security_posture_checks(flags),
        _provider_credential_check(secret_presence),
        _quota_check(flags),
        *_deployment_opt_in_checks(flags),
        *_public_instance_posture_checks(flags),
    ]
    failed = [check["id"] for check in checks if check["status"] != "pass"]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "tool": "scripts/production_config_readiness.py",
        "inputSchemaVersion": str(contract.get("schemaVersion") or ""),
        "mode": str(contract.get("mode") or "unspecified"),
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "failedCheckIds": failed,
        },
        "finalStatus": "GO" if not failed else "NO-GO",
        "sanitization": {
            "externalServicesCalled": False,
            "networkCallsEnabled": False,
            "realEnvFileRead": False,
            "secretValuesRead": False,
            "secretValuesIncluded": False,
            "runtimeDefaultsChanged": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit sanitized production config readiness JSON.")
    parser.add_argument("--contract", help="Synthetic or sanitized JSON config contract.")
    args = parser.parse_args(argv)

    evidence = build_readiness(_load_contract(args.contract))
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["finalStatus"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
