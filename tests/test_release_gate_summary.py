import shutil
import subprocess
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SOURCE = REPO_ROOT / "scripts" / "release_gate_summary.sh"


def _run(cmd, cwd: Path, **kwargs):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, **kwargs)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "scripts").mkdir()
    shutil.copy2(SCRIPT_SOURCE, repo / "scripts" / "release_gate_summary.sh")
    (repo / "scripts" / "release_secret_scan.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (repo / "scripts" / "production_config_readiness.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (repo / "scripts" / "staging_ingress_smoke.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (repo / "scripts" / "ci_gate_fast.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    _run(["git", "init", "-b", "main"], repo, check=True)
    _run(["git", "config", "user.email", "codex@example.com"], repo, check=True)
    _run(["git", "config", "user.name", "Codex Test"], repo, check=True)
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    _run(["git", "add", "README.md", "scripts"], repo, check=True)
    _run(["git", "commit", "-m", "initial"], repo, check=True)
    _run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], repo, check=True)
    return repo


def _summary(repo: Path, *args: str):
    return _run(["bash", "scripts/release_gate_summary.sh", *args], repo)


def test_release_gate_summary_prints_required_fields_on_clean_repo(tmp_path):
    repo = _init_repo(tmp_path)

    result = _summary(repo)

    assert result.returncode == 0
    assert "Current branch: main" in result.stdout
    assert "Ahead/behind vs origin/main: ahead 0, behind 0" in result.stdout
    assert "Worktree dirty: no" in result.stdout
    assert "scripts/release_secret_scan.sh: present" in result.stdout
    assert "scripts/production_config_readiness.py: present" in result.stdout
    assert "scripts/staging_ingress_smoke.py: present" in result.stdout
    assert "scripts/ci_gate_fast.sh: present" in result.stdout
    assert "python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>" in result.stdout
    assert "./scripts/release_secret_scan.sh" in result.stdout
    assert "python3 scripts/staging_ingress_smoke.py --base-url <staging-ingress-base-url>" in result.stdout
    assert "./scripts/ci_gate_fast.sh" in result.stdout
    assert "./scripts/ci_gate.sh" in result.stdout
    assert "git diff --check origin/main..HEAD" in result.stdout
    assert "not a release approval tool" in result.stdout


def test_release_gate_summary_go_no_go_json_keeps_launch_blocked(tmp_path):
    repo = _init_repo(tmp_path)

    result = _summary(repo, "--go-no-go-json")

    assert result.returncode == 0
    summary = json.loads(result.stdout)
    assert summary["schemaVersion"] == "wolfystock_public_launch_go_no_go_v1"
    assert summary["finalStatus"] == "NO-GO"
    assert summary["releaseApproved"] is False
    evidence_ids = {item["id"] for item in summary["completedFoundationEvidence"]}
    assert {
        "provider_sla_live_readiness_preflight",
        "mfa_rbac_readiness_foundations",
        "quota_pilot_readiness_foundation",
        "backup_restore_dry_run_postgres_pitr_synthetic",
        "data_quality_fallback_stale_disclosure",
        "scanner_portfolio_backtest_options_no_advice_public_safety",
        "secret_scan_admin_harness_staging_ingress",
        "production_config_secret_contract_preflight",
    } <= evidence_ids
    blocker_ids = {item["id"] for item in summary["hardBlockers"]}
    assert {
        "global_mfa_enforcement_not_accepted",
        "rbac_coarse_fallback_actual_removal_pending",
        "live_quota_enforcement_not_global",
        "real_isolated_postgresql_restore_pitr_pending",
        "real_provider_credentials_live_calls_circuit_enforcement_pending",
        "final_clean_full_release_gate_required",
        "production_config_contract_acceptance_pending",
    } <= blocker_ids
    assert all(item["status"] == "blocking" for item in summary["hardBlockers"])
    assert "launch-ready" not in result.stdout


def test_release_gate_summary_fails_on_dirty_repo_without_allow_dirty(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "scratch.txt").write_text("local\n", encoding="utf-8")

    result = _summary(repo)

    assert result.returncode == 1
    assert "Untracked files: 1" in result.stdout
    assert "Worktree dirty: yes" in result.stdout
    assert "scratch.txt" in result.stdout
    assert "Worktree is dirty" in result.stderr


def test_release_gate_summary_allows_dirty_repo_with_explicit_flag(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "scratch.txt").write_text("local\n", encoding="utf-8")

    result = _summary(repo, "--allow-dirty")

    assert result.returncode == 0
    assert "Untracked files: 1" in result.stdout
    assert "Worktree dirty: yes" in result.stdout
    assert "[PASS] release gate summary completed" in result.stdout
