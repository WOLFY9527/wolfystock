import shutil
import subprocess
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SOURCE = REPO_ROOT / "scripts" / "release_gate_summary.sh"
EXPECTED_OPERATOR_CATEGORY_IDS = [
    "mfa_pilot_acceptance",
    "rbac_fallback_disable_switch",
    "provider_credential_staging_dry_run",
    "provider_staging_probe_artifact",
    "provider_live_probe_opt_in_timeout",
    "provider_circuit_controlled_enforcement",
    "quota_pilot_acceptance",
    "budget_alert_dry_run_acceptance",
    "real_isolated_postgresql_restore_pitr",
    "staging_ingress_smoke",
    "public_api_frontend_no_secret_safety",
    "supply_chain_dependency_build_artifact_safety",
    "incident_response_audit_evidence",
    "ws2_sse_topology_polling_fallback",
    "admin_log_retention_capacity_rehearsal",
    "portfolio_backtest_export_browser_proof",
    "notifications_delivery_rehearsal",
    "user_data_privacy_export_deletion_rehearsal",
    "market_data_freshness_fallback_evidence",
    "ai_report_guest_preview_safety",
    "options_derivatives_safety",
    "api_abuse_request_safety",
    "final_clean_full_ci_gate",
    "provider_operator_evidence",
    "restore_pitr_operator_evidence",
    "security_operator_acceptance",
    "quota_budget_operator_evidence",
    "staging_ingress_operator_evidence",
    "ws2_sse_operator_decision_evidence",
    "config_snapshot_evidence",
    "manual_release_approval_review_record",
]
EXPECTED_BLOCKER_CLASSIFICATIONS = {
    "mfa_pilot_acceptance": "external_manual",
    "rbac_fallback_disable_switch": "external_manual",
    "provider_credential_staging_dry_run": "external_manual",
    "provider_staging_probe_artifact": "external_manual",
    "provider_live_probe_opt_in_timeout": "external_manual",
    "provider_circuit_controlled_enforcement": "external_manual",
    "quota_pilot_acceptance": "external_manual",
    "budget_alert_dry_run_acceptance": "external_manual",
    "real_isolated_postgresql_restore_pitr": "external_manual",
    "staging_ingress_smoke": "external_manual",
    "public_api_frontend_no_secret_safety": "frontend_owned",
    "supply_chain_dependency_build_artifact_safety": "internal_validation",
    "incident_response_audit_evidence": "external_manual",
    "ws2_sse_topology_polling_fallback": "intentional_policy",
    "admin_log_retention_capacity_rehearsal": "internal_validation",
    "portfolio_backtest_export_browser_proof": "frontend_owned",
    "notifications_delivery_rehearsal": "external_manual",
    "user_data_privacy_export_deletion_rehearsal": "internal_validation",
    "market_data_freshness_fallback_evidence": "internal_validation",
    "ai_report_guest_preview_safety": "frontend_owned",
    "options_derivatives_safety": "intentional_policy",
    "api_abuse_request_safety": "internal_validation",
    "final_clean_full_ci_gate": "internal_validation",
    "provider_operator_evidence": "external_manual",
    "restore_pitr_operator_evidence": "external_manual",
    "security_operator_acceptance": "external_manual",
    "quota_budget_operator_evidence": "external_manual",
    "staging_ingress_operator_evidence": "external_manual",
    "ws2_sse_operator_decision_evidence": "intentional_policy",
    "config_snapshot_evidence": "external_manual",
    "manual_release_approval_review_record": "external_manual",
}
ALLOWED_BLOCKER_CLASSIFICATIONS = {
    "internal_validation",
    "external_manual",
    "intentional_policy",
    "frontend_owned",
    "unknown",
}
EXPECTED_COMPLETED_FOUNDATION_BLOCKER_IDS = {
    "api_abuse_request_safety",
    "admin_log_retention_capacity_rehearsal",
    "market_data_freshness_fallback_evidence",
    "user_data_privacy_export_deletion_rehearsal",
}


def _run(cmd, cwd: Path, **kwargs):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, **kwargs)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "scripts").mkdir()
    shutil.copy2(SCRIPT_SOURCE, repo / "scripts" / "release_gate_summary.sh")
    (repo / "scripts" / "release_secret_scan.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (repo / "scripts" / "production_config_readiness.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (repo / "scripts" / "launch_acceptance_evidence.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (repo / "scripts" / "incident_response_evidence.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (repo / "scripts" / "staging_ingress_smoke.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (repo / "scripts" / "ci_gate_fast.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (repo / "scripts" / "operator_evidence_bundle_check.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (repo / "scripts" / "ws2_sse_operator_decision_check.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (repo / "scripts" / "config_snapshot_evidence_check.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (repo / "scripts" / "manual_release_approval_evidence_check.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")

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
    assert "scripts/launch_acceptance_evidence.py: present" in result.stdout
    assert "scripts/incident_response_evidence.py: present" in result.stdout
    assert "scripts/staging_ingress_smoke.py: present" in result.stdout
    assert "scripts/ci_gate_fast.sh: present" in result.stdout
    assert "scripts/operator_evidence_bundle_check.py: present" in result.stdout
    assert "scripts/ws2_sse_operator_decision_check.py: present" in result.stdout
    assert "scripts/config_snapshot_evidence_check.py: present" in result.stdout
    assert "scripts/manual_release_approval_evidence_check.py: present" in result.stdout
    assert "python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>" in result.stdout
    assert "python3 scripts/launch_acceptance_evidence.py --evidence <sanitized-launch-acceptance-evidence.json>" in result.stdout
    assert "python3 scripts/incident_response_evidence.py --evidence <sanitized-incident-response-evidence.json>" in result.stdout
    assert "python3 scripts/operator_evidence_bundle_check.py <sanitized-operator-evidence-dir>" in result.stdout
    assert "python3 scripts/ws2_sse_operator_decision_check.py <sanitized-ws2-sse-operator-decision.json>" in result.stdout
    assert "python3 scripts/config_snapshot_evidence_check.py <sanitized-config-snapshot-evidence.json>" in result.stdout
    assert (
        "python3 scripts/manual_release_approval_evidence_check.py --artifact <sanitized-manual-release-review-record.json>"
        in result.stdout
    )
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
        "supply_chain_dependency_build_artifact_safety",
        "incident_response_audit_evidence_pack",
        "provider_operator_evidence_validator",
        "restore_pitr_operator_evidence_validator",
        "security_operator_acceptance_validator",
        "quota_budget_operator_evidence_validator",
        "staging_ingress_operator_evidence_validator",
        "operator_evidence_bundle_review_support",
        "ws2_sse_operator_decision_validator",
        "config_snapshot_evidence_validator",
        "manual_release_approval_review_record_validator",
    } <= evidence_ids
    support = {item["id"]: item for item in summary["completedFoundationEvidence"]}
    assert support["operator_evidence_bundle_review_support"]["status"] == "review_support_available"
    assert support["manual_release_approval_review_record_validator"]["status"] == "offline_validator_available_manual_review_required"
    blocker_ids = {item["id"] for item in summary["hardBlockers"]}
    assert set(EXPECTED_OPERATOR_CATEGORY_IDS) <= blocker_ids
    assert all(item["status"] == "blocking" for item in summary["hardBlockers"])
    assert len(summary["hardBlockers"]) == len(EXPECTED_OPERATOR_CATEGORY_IDS)
    blocker_classifications = {
        item["id"]: item["blockerClassification"] for item in summary["hardBlockers"]
    }
    assert blocker_classifications == EXPECTED_BLOCKER_CLASSIFICATIONS
    assert set(blocker_classifications.values()) <= ALLOWED_BLOCKER_CLASSIFICATIONS
    assert summary["operatorEvidencePack"] == {
        "finalStatus": "NO-GO",
        "releaseApproved": False,
        "requiredCategoryIds": EXPECTED_OPERATOR_CATEGORY_IDS,
        "schemaVersion": "wolfystock_launch_acceptance_evidence_summary_v1",
    }
    assert (
        "python3 scripts/launch_acceptance_evidence.py --evidence <sanitized-launch-acceptance-evidence.json>"
        in summary["requiredFinalCommands"]
    )
    assert (
        "python3 scripts/incident_response_evidence.py --evidence <sanitized-incident-response-evidence.json>"
        in summary["requiredFinalCommands"]
    )
    assert "python3 scripts/operator_evidence_bundle_check.py <sanitized-operator-evidence-dir>" in summary["requiredFinalCommands"]
    assert (
        "python3 scripts/manual_release_approval_evidence_check.py --artifact <sanitized-manual-release-review-record.json>"
        in summary["requiredFinalCommands"]
    )
    assert "launch-ready" not in result.stdout
    assert "launch-" + "approved" not in result.stdout.lower()
    assert "production-" + "ready" not in result.stdout.lower()


def test_release_gate_summary_completed_foundation_evidence_stays_non_approving(tmp_path):
    repo = _init_repo(tmp_path)

    result = _summary(repo, "--go-no-go-json")

    assert result.returncode == 0
    summary = json.loads(result.stdout)
    support = summary["completedFoundationEvidence"]
    support_by_blocker = {
        item["blockerId"]: item for item in support if "blockerId" in item
    }

    assert set(support_by_blocker) == EXPECTED_COMPLETED_FOUNDATION_BLOCKER_IDS

    expected_scope = {
        "api_abuse_request_safety": "request-safety regression anchors stay repo-local and offline only",
        "admin_log_retention_capacity_rehearsal": "retention/capacity rehearsal anchors stay repo-local and offline only",
        "market_data_freshness_fallback_evidence": "freshness/fallback disclosure anchors stay repo-local and offline only",
        "user_data_privacy_export_deletion_rehearsal": "privacy export/deletion rehearsal anchors stay repo-local and offline only",
    }
    for blocker_id, scope_note in expected_scope.items():
        foundation = support_by_blocker[blocker_id]
        assert foundation["id"] == blocker_id + "_completed_foundation_evidence"
        assert foundation["status"] == "completed_foundation_evidence_only"
        assert foundation["foundationStatus"] == "completed"
        assert foundation["evidenceScope"] == "repo_local_offline_only"
        assert foundation["acceptedLaunchArtifactRequired"] is True
        assert foundation["releaseApprovalEvidence"] is False
        assert foundation["releaseApproved"] is False
        assert any(scope_note == note for note in foundation["evidence"])
        assert any("accepted" in note and "launch artifact still required" in note for note in foundation["evidence"])
        assert any("no approval semantics granted" in note for note in foundation["evidence"])
        if blocker_id == "user_data_privacy_export_deletion_rehearsal":
            assert any("destructive delete remains no-write/unsupported" in note for note in foundation["evidence"])
            assert any("future runtime design changes" in note for note in foundation["evidence"])

    hard_blockers = {item["id"]: item for item in summary["hardBlockers"]}
    assert set(hard_blockers) == set(EXPECTED_OPERATOR_CATEGORY_IDS)
    for blocker_id in EXPECTED_COMPLETED_FOUNDATION_BLOCKER_IDS:
        blocker = hard_blockers[blocker_id]
        assert blocker["status"] == "blocking"
        assert blocker["blockerClassification"] == "internal_validation"

    assert summary["finalStatus"] == "NO-GO"
    assert summary["releaseApproved"] is False

    foundation_classifications = {
        blocker_id: hard_blockers[blocker_id]["blockerClassification"]
        for blocker_id in support_by_blocker
    }
    assert set(foundation_classifications.values()) == {"internal_validation"}

    unexpected_foundation_blockers = {
        item["blockerId"]: hard_blockers[item["blockerId"]]["blockerClassification"]
        for item in support
        if "blockerId" in item
        and item["blockerId"] not in EXPECTED_COMPLETED_FOUNDATION_BLOCKER_IDS
    }
    assert unexpected_foundation_blockers == {}


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
