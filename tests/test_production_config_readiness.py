from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "production_config_readiness.py"
READY_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "release" / "production_config_readiness.ready.json"
MISSING_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "release" / "production_config_readiness.missing.json"


def _run_preflight(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def test_production_config_readiness_accepts_sanitized_contract() -> None:
    result = _run_preflight("--contract", str(READY_FIXTURE))

    assert result.returncode == 0
    evidence = _output(result)
    assert evidence["schemaVersion"] == "wolfystock_production_config_readiness_v1"
    assert evidence["finalStatus"] == "GO"
    assert evidence["sanitization"] == {
        "externalServicesCalled": False,
        "networkCallsEnabled": False,
        "realEnvFileRead": False,
        "runtimeDefaultsChanged": False,
        "secretValuesIncluded": False,
        "secretValuesRead": False,
    }
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["required_launch_config_names"]["status"] == "pass"
    assert checks["admin_auth_enabled_for_public_deploy"]["status"] == "pass"
    assert checks["admin_auth_enabled_for_public_deploy"]["evidence"] == {
        "flagName": "ADMIN_AUTH_ENABLED",
        "state": "enabled",
        "authDisabledPublicIngressSafe": False,
        "runtimeDefaultChanged": False,
        "valuesIncluded": False,
    }
    assert checks["mfa_rollout_mode_explicit"]["evidence"]["mode"] == "disabled"
    assert checks["rbac_coarse_fallback_disable_flag"]["evidence"]["state"] == "disabled"
    assert checks["quota_enforcement_mode_explicit"]["evidence"]["mode"] == "pilot"
    assert checks["backup_pitr_execution_opt_in_disabled_by_default"]["evidence"]["state"] == "disabled"
    assert checks["staging_ingress_live_opt_in_disabled_by_default"]["evidence"]["networkCallsEnabled"] is False


def test_production_config_readiness_missing_required_config_is_no_go() -> None:
    result = _run_preflight("--contract", str(MISSING_FIXTURE))

    assert result.returncode == 1
    evidence = _output(result)
    assert evidence["finalStatus"] == "NO-GO"
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["required_launch_config_names"]["status"] == "fail"
    assert "APP_ENV" in checks["required_launch_config_names"]["evidence"]["missingNames"]
    assert checks["provider_live_credential_contract"]["status"] == "fail"
    assert checks["quota_enforcement_mode_explicit"]["evidence"]["mode"] == "missing"


def test_production_config_readiness_auth_disabled_is_public_no_go(tmp_path: Path) -> None:
    contract = json.loads(READY_FIXTURE.read_text(encoding="utf-8"))
    contract["flags"]["ADMIN_AUTH_ENABLED"] = "false"
    contract_path = tmp_path / "auth-disabled-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    result = _run_preflight("--contract", str(contract_path))

    assert result.returncode == 1
    evidence = _output(result)
    assert evidence["finalStatus"] == "NO-GO"
    checks = {check["id"]: check for check in evidence["checks"]}
    assert checks["admin_auth_enabled_for_public_deploy"]["status"] == "fail"
    assert checks["admin_auth_enabled_for_public_deploy"]["evidence"] == {
        "flagName": "ADMIN_AUTH_ENABLED",
        "state": "disabled",
        "authDisabledPublicIngressSafe": False,
        "runtimeDefaultChanged": False,
        "valuesIncluded": False,
    }


def test_production_config_readiness_missing_admin_auth_is_public_no_go() -> None:
    result = _run_preflight("--contract", str(MISSING_FIXTURE))

    checks = {check["id"]: check for check in _output(result)["checks"]}
    assert checks["admin_auth_enabled_for_public_deploy"]["status"] == "fail"
    assert checks["admin_auth_enabled_for_public_deploy"]["evidence"]["state"] == "missing_or_invalid"


def test_production_config_readiness_reports_global_mfa_scope_as_fail_closed(tmp_path: Path) -> None:
    contract = json.loads(READY_FIXTURE.read_text(encoding="utf-8"))
    contract["flags"]["WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED"] = "true"
    contract["flags"]["WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_SCOPE"] = "global"
    contract_path = tmp_path / "global-mfa-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    result = _run_preflight("--contract", str(contract_path))

    assert result.returncode == 1
    checks = {check["id"]: check for check in _output(result)["checks"]}
    assert checks["mfa_rollout_mode_explicit"]["status"] == "fail"
    assert checks["mfa_rollout_mode_explicit"]["evidence"]["mode"] == "unsupported"
    assert checks["mfa_rollout_mode_explicit"]["evidence"]["unsupportedGlobalModeFailsClosedInEvidence"] is True


def test_production_config_readiness_never_prints_secret_values(tmp_path: Path) -> None:
    secret_value = "sk-" + ("A" * 40)
    contract = json.loads(READY_FIXTURE.read_text(encoding="utf-8"))
    contract["secretPresence"]["OPENAI_API_KEY"] = secret_value
    contract_path = tmp_path / "bad-secret-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    result = _run_preflight("--contract", str(contract_path))

    assert result.returncode == 1
    assert secret_value not in result.stdout
    assert secret_value not in result.stderr
    checks = {check["id"]: check for check in _output(result)["checks"]}
    assert checks["provider_live_credential_contract"]["status"] == "fail"
    assert checks["provider_live_credential_contract"]["evidence"]["contractIssues"] == [
        {"name": "OPENAI_API_KEY", "reasonCode": "secret_presence_not_boolean_or_state"}
    ]


def test_production_config_readiness_default_mode_is_safe_no_go() -> None:
    result = _run_preflight()

    assert result.returncode == 1
    evidence = _output(result)
    assert evidence["mode"] == "synthetic_empty"
    assert evidence["finalStatus"] == "NO-GO"
    assert evidence["sanitization"]["realEnvFileRead"] is False
