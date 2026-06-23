from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "private-beta-critical-path-smoke.ps1"


def _read() -> str:
    return SMOKE_SCRIPT.read_text(encoding="utf-8")


def test_private_beta_critical_path_smoke_script_exists() -> None:
    assert SMOKE_SCRIPT.exists()


def test_default_mode_is_check_only_and_prints_required_context() -> None:
    content = _read()

    assert "Repo path" in content
    assert "Branch" in content
    assert "HEAD" in content
    assert "Backend URL" in content
    assert "Frontend URL" in content
    assert "Default mode: check-only" in content
    assert "Start-Process" not in content
    assert "npm run dev" not in content
    assert "--serve-only" not in content
    assert "uvicorn" not in content


def test_optional_preflight_seed_probe_and_output_flags_gate_side_effects() -> None:
    content = _read()

    assert "private-beta-preflight.ps1" in content
    assert "seed-uat-consumer-test-accounts.ps1" in content

    assert content.index("if ($RunPreflight)") < content.index("& $preflightScript")
    assert content.index("if ($SeedUatConsumers)") < content.index("& $seedScript")
    assert content.index("if ($ProbeBackend)") < content.index("Invoke-BoundedRequest -BaseUrl $backendUrl")
    assert content.index("if ($ProbeFrontend)") < content.index("Invoke-BoundedRequest -BaseUrl $frontendUrl")
    assert content.index("if (-not [string]::IsNullOrWhiteSpace($OutputPath))") < content.index("Set-Content -Path $resolvedOutput")


def test_backend_and_frontend_probes_only_when_ports_are_listening() -> None:
    content = _read()

    assert "Get-NetTCPConnection -State Listen -LocalPort $LocalPort" in content
    assert "$backendListeners.Count -eq 0" in content
    assert "Backend probes: skipped; backend port is not listening" in content
    assert "$frontendListeners.Count -eq 0" in content
    assert "Frontend probes: skipped; frontend port is not listening" in content
    assert "'/api/health'" in content
    assert "'/api/v1/auth/status'" in content
    assert "'/api/v1/market-overview/macro'" in content
    assert "'/api/v1/market-overview/funds-flow'" in content
    assert "'/'" in content
    assert "'/backtest'" in content
    assert "'/stock/AAPL'" in content


def test_credential_probe_and_wrong_password_check_are_explicitly_gated() -> None:
    content = _read()

    assert content.index("if ($ProbeCredentials)") < content.index("not-a-real-password")
    assert content.index("if ($ProbeCredentials)") < content.index("-ExpectInvalidLogin")
    assert "invalid_login" in content
    assert "Credential probes: skipped; pass -ProbeCredentials" in content


def test_script_keeps_output_bounded_and_avoids_privileged_or_advice_text() -> None:
    content = _read().lower()

    assert "browser-level spa redirect assertions remain playwright/uat responsibility" in content
    assert "convertto-json -depth 4 | set-content" in content
    assert "write-host $content" not in content
    assert "write-output $content" not in content
    assert "provider secret" not in content
    assert "role_admin" not in content
    assert "grant_admin" not in content
    assert "create_admin" not in content
    assert "buy" not in content
    assert "sell" not in content
    assert "hold" not in content
