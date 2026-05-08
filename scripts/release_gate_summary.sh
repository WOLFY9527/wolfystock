#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE_REF="${RELEASE_GATE_SUMMARY_BASE_REF:-origin/main}"
ALLOW_DIRTY=0
GO_NO_GO_JSON=0

usage() {
  cat <<'USAGE'
Usage: scripts/release_gate_summary.sh [--allow-dirty] [--go-no-go-json]

Print the release gate status summary and the final pre-push commands.
This is an informational helper; it does not approve a release and does not run
the full CI gate.

--go-no-go-json prints a sanitized public launch evidence summary as JSON.
USAGE
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --allow-dirty)
      ALLOW_DIRTY=1
      ;;
    --go-no-go-json)
      GO_NO_GO_JSON=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[FAIL] Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

cd "${ROOT_DIR}"

print_step() {
  echo "==> release-gate-summary: $1"
}

ref_available() {
  git rev-parse --verify "$1" >/dev/null 2>&1
}

current_branch() {
  local branch
  branch="$(git branch --show-current)"
  if [[ -n "${branch}" ]]; then
    printf '%s\n' "${branch}"
  else
    git rev-parse --short HEAD
  fi
}

count_lines() {
  sed '/^$/d' | wc -l | tr -d ' '
}

script_status() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    echo "present"
  else
    echo "missing"
  fi
}

branch="$(current_branch)"
ahead_count="unavailable"
behind_count="unavailable"
if ref_available "${BASE_REF}"; then
  read -r behind_count ahead_count < <(git rev-list --left-right --count "${BASE_REF}...HEAD")
fi
staged_count="$(git diff --cached --name-only --diff-filter=ACMRTUXB | count_lines)"
unstaged_count="$(git diff --name-only --diff-filter=ACMRTUXB | count_lines)"
untracked_count="$(git ls-files --others --exclude-standard | count_lines)"
dirty_count=$((staged_count + unstaged_count + untracked_count))

if [[ "${GO_NO_GO_JSON}" -eq 1 ]]; then
  python3 - "${branch}" "${BASE_REF}" "${ahead_count}" "${behind_count}" "${staged_count}" "${unstaged_count}" "${untracked_count}" <<'PY'
import json
import sys


def numeric_or_text(value: str):
    try:
        return int(value)
    except ValueError:
        return value


branch, base_ref, ahead, behind, staged, unstaged, untracked = sys.argv[1:8]
dirty_total = int(staged) + int(unstaged) + int(untracked)

summary = {
    "schemaVersion": "wolfystock_public_launch_go_no_go_v1",
    "tool": "scripts/release_gate_summary.sh --go-no-go-json",
    "branch": branch,
    "baseRef": base_ref,
    "aheadCount": numeric_or_text(ahead),
    "behindCount": numeric_or_text(behind),
    "worktree": {
        "stagedChanges": int(staged),
        "unstagedChanges": int(unstaged),
        "untrackedFiles": int(untracked),
        "dirty": dirty_total > 0,
    },
    "finalStatus": "NO-GO",
    "releaseApproved": False,
    "statusReason": (
        "Public launch remains blocked until every hard blocker has explicit "
        "release-candidate evidence or a documented production exception."
    ),
    "completedFoundationEvidence": [
        {
            "id": "provider_sla_live_readiness_preflight",
            "status": "foundation_evidence_present",
            "evidence": [
                "provider SLA/readiness diagnostics",
                "Options live-readiness preflight remains safe without live calls by default",
            ],
        },
        {
            "id": "mfa_rbac_readiness_foundations",
            "status": "foundation_evidence_present",
            "evidence": [
                "MFA backend/encrypted-secret foundation",
                "disabled-by-default MFA pilot guard",
                "RBAC capability readiness coverage",
            ],
        },
        {
            "id": "quota_pilot_readiness_foundation",
            "status": "foundation_evidence_present",
            "evidence": [
                "quota dry-run/reservation helpers",
                "quota enforcement pilot-readiness preflight",
            ],
        },
        {
            "id": "backup_restore_dry_run_postgres_pitr_synthetic",
            "status": "foundation_evidence_present",
            "evidence": [
                "local backup/restore dry-run preflight",
                "synthetic PostgreSQL/PITR metadata evidence",
            ],
        },
        {
            "id": "data_quality_fallback_stale_disclosure",
            "status": "foundation_evidence_present",
            "evidence": [
                "fallback/stale data-quality disclosure regressions",
                "confidence/data-quality cap evidence",
            ],
        },
        {
            "id": "scanner_portfolio_backtest_options_no_advice_public_safety",
            "status": "foundation_evidence_present",
            "evidence": [
                "scanner public-safety evidence",
                "portfolio/backtest no-advice and owner-isolation focused evidence",
                "Options read-only/no-order public-safety evidence",
            ],
        },
        {
            "id": "secret_scan_admin_harness_staging_ingress",
            "status": "foundation_evidence_present",
            "evidence": [
                "release secret scan helper",
                "admin harness evidence",
                "staging ingress dry-run/live opt-in preflight",
            ],
        },
        {
            "id": "production_config_secret_contract_preflight",
            "status": "foundation_evidence_present",
            "evidence": [
                "sanitized production config contract preflight",
                "required launch flag names and secret presence states",
                "MFA/RBAC/quota/backup/ingress opt-in posture without secret values",
            ],
        },
        {
            "id": "supply_chain_dependency_build_artifact_safety",
            "status": "foundation_evidence_present",
            "evidence": [
                "dependency manifest inspection must stay sanitized and offline",
                "build/test artifact evidence must exclude env, token, key, cookie, session, DSN, private-key, and provider credential patterns",
                "frontend build warnings remain visible and non-blocking",
                "dependency versions and lockfiles must not be rewritten by evidence capture",
            ],
        },
        {
            "id": "incident_response_audit_evidence_pack",
            "status": "foundation_evidence_present",
            "evidence": [
                "incident-response evidence checker remains local-only and no-network",
                "admin-critical action, cleanup, provider, notification, and release-failure evidence must be sanitized",
                "incident/audit evidence must exclude tokens, passwords, API keys, cookies, sessions, DSNs, provider credentials, and raw response bodies",
            ],
        },
        {
            "id": "provider_operator_evidence_validator",
            "status": "foundation_evidence_present",
            "evidence": [
                "scripts/provider_operator_evidence_check.py validates sanitized provider operator artifacts offline",
                "provider operator evidence remains advisory and review-gated",
                "validator output must not include provider calls, raw credentials, raw provider payloads, or runtime provider changes",
            ],
        },
        {
            "id": "restore_pitr_operator_evidence_validator",
            "status": "foundation_evidence_present",
            "evidence": [
                "scripts/restore_pitr_operator_evidence_check.py validates externally produced restore/PITR artifacts offline",
                "real restore/PITR evidence still requires operator-run isolated restore artifacts",
                "validator output must not include database commands run by the validator, production storage mutation, DSNs, dumps, or raw SQL",
            ],
        },
        {
            "id": "security_operator_acceptance_validator",
            "status": "foundation_evidence_present",
            "evidence": [
                "scripts/security_operator_acceptance_check.py validates sanitized MFA/RBAC operator acceptance artifacts offline",
                "security operator evidence remains manual-review gated with releaseApproved=false",
                "validator output must not include auth runtime changes, raw MFA secrets, sessions, cookies, or RBAC payload dumps",
            ],
        },
        {
            "id": "quota_budget_operator_evidence_validator",
            "status": "foundation_evidence_present",
            "evidence": [
                "scripts/quota_operator_evidence_check.py validates sanitized quota/budget operator artifacts offline",
                "quota/budget operator evidence remains advisory and does not enable enforcement",
                "validator output must not include outbound notifications, billing/provider calls, threshold mutations, or raw request/response bodies",
            ],
        },
        {
            "id": "staging_ingress_operator_evidence_validator",
            "status": "foundation_evidence_present",
            "evidence": [
                "scripts/staging_ingress_operator_evidence_check.py validates sanitized staging ingress operator artifacts offline",
                "real ingress proof still requires operator-captured staging artifacts",
                "validator output must not include network calls by the validator, credential URLs, raw bodies, headers, cookies, or ingress runtime changes",
            ],
        },
    ],
    "operatorEvidencePack": {
        "schemaVersion": "wolfystock_launch_acceptance_evidence_summary_v1",
        "requiredCategoryIds": [
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
        ],
        "finalStatus": "NO-GO",
        "releaseApproved": False,
    },
    "hardBlockers": [
        {
            "id": "mfa_pilot_acceptance",
            "status": "blocking",
            "requiredEvidence": "accepted MFA admin pilot operator evidence with recovery, rollback, unsupported rollout NO-GO, and redaction proof",
        },
        {
            "id": "rbac_fallback_disable_switch",
            "status": "blocking",
            "requiredEvidence": "accepted RBAC fallback disable switch operator evidence with route inventory, fail-closed proof, and rollback",
        },
        {
            "id": "provider_credential_staging_dry_run",
            "status": "blocking",
            "requiredEvidence": "provider credential staging dry-run evidence using presence-only credential and entitlement summaries",
        },
        {
            "id": "provider_staging_probe_artifact",
            "status": "blocking",
            "requiredEvidence": "provider staging probe artifact evidence with credential redaction, entitlement/freshness labels, and no checker live calls",
        },
        {
            "id": "provider_live_probe_opt_in_timeout",
            "status": "blocking",
            "requiredEvidence": "provider live probe opt-in and bounded-timeout evidence for a named staging provider",
        },
        {
            "id": "provider_circuit_controlled_enforcement",
            "status": "blocking",
            "requiredEvidence": "provider circuit controlled enforcement evidence with bounded route, rollback switch, and sanitized degraded state",
        },
        {
            "id": "quota_pilot_acceptance",
            "status": "blocking",
            "requiredEvidence": "quota pilot acceptance evidence with owner allowlist, advisory out-of-scope behavior, and rollback",
        },
        {
            "id": "budget_alert_dry_run_acceptance",
            "status": "blocking",
            "requiredEvidence": "budget alert dry-run acceptance evidence with outbound delivery disabled and no live LLM/provider/invoice calls",
        },
        {
            "id": "real_isolated_postgresql_restore_pitr",
            "status": "blocking",
            "requiredEvidence": "real isolated PostgreSQL restore/PITR execution and post-restore smoke evidence",
        },
        {
            "id": "staging_ingress_smoke",
            "status": "blocking",
            "requiredEvidence": "HTTPS staging ingress smoke evidence with synthetic users/data and no public backend :8000 exposure",
        },
        {
            "id": "public_api_frontend_no_secret_safety",
            "status": "blocking",
            "requiredEvidence": "public API/frontend no-secret safety evidence for API payloads, DOM, public routes, and release scan",
        },
        {
            "id": "supply_chain_dependency_build_artifact_safety",
            "status": "blocking",
            "requiredEvidence": "supply-chain and build artifact evidence with sanitized dependency/build scans and no lockfile rewrites",
        },
        {
            "id": "incident_response_audit_evidence",
            "status": "blocking",
            "requiredEvidence": "incident response/audit evidence with sanitized admin-critical, cleanup, provider, notification, and release-failure paths",
        },
        {
            "id": "ws2_sse_topology_polling_fallback",
            "status": "blocking",
            "requiredEvidence": "WS2/SSE topology evidence with process-local SSE limitation, durable polling fallback, and no runtime cutover",
        },
        {
            "id": "admin_log_retention_capacity_rehearsal",
            "status": "blocking",
            "requiredEvidence": "admin log retention/capacity rehearsal evidence with preview-first cleanup, retention guard, and sanitized audit",
        },
        {
            "id": "portfolio_backtest_export_browser_proof",
            "status": "blocking",
            "requiredEvidence": "portfolio/backtest export and browser proof with owner isolation, no-advice wording, and broker redaction",
        },
        {
            "id": "notifications_delivery_rehearsal",
            "status": "blocking",
            "requiredEvidence": "notification delivery rehearsal evidence with route/channel mapping, failure audit, and secret redaction",
        },
        {
            "id": "user_data_privacy_export_deletion_rehearsal",
            "status": "blocking",
            "requiredEvidence": "user data privacy/export/deletion rehearsal evidence with sanitized projections, deletion preview, and owner isolation",
        },
        {
            "id": "market_data_freshness_fallback_evidence",
            "status": "blocking",
            "requiredEvidence": "market data freshness/fallback evidence with as-of labels, stale/fallback disclosure, and no raw provider payloads",
        },
        {
            "id": "ai_report_guest_preview_safety",
            "status": "blocking",
            "requiredEvidence": "AI report and guest-preview safety evidence with guest isolation, no raw prompt/LLM response leakage, and no advice labels",
        },
        {
            "id": "options_derivatives_safety",
            "status": "blocking",
            "requiredEvidence": "Options derivatives safety evidence proving read-only/no-order posture, no mutation paths, and conservative data caps",
        },
        {
            "id": "api_abuse_request_safety",
            "status": "blocking",
            "requiredEvidence": "API abuse/request-safety evidence with denial audit, oversized payload safety, and no debug/request-body/traceback leakage",
        },
        {
            "id": "final_clean_full_ci_gate",
            "status": "blocking",
            "requiredEvidence": "clean worktree, full ci_gate, release secret scan, and final diff check evidence",
        },
        {
            "id": "provider_operator_evidence",
            "status": "blocking",
            "requiredEvidence": "accepted sanitized provider operator evidence from scripts/provider_operator_evidence_check.py plus guide reference, advisory gate, and unchanged runtime behavior",
        },
        {
            "id": "restore_pitr_operator_evidence",
            "status": "blocking",
            "requiredEvidence": "accepted sanitized real restore/PITR operator evidence from scripts/restore_pitr_operator_evidence_check.py plus guide reference and manual review gate",
        },
        {
            "id": "security_operator_acceptance",
            "status": "blocking",
            "requiredEvidence": "accepted sanitized MFA/RBAC operator acceptance evidence from scripts/security_operator_acceptance_check.py with releaseApproved=false and unchanged auth/RBAC runtime behavior",
        },
        {
            "id": "quota_budget_operator_evidence",
            "status": "blocking",
            "requiredEvidence": "accepted sanitized quota/budget operator evidence from scripts/quota_operator_evidence_check.py with no outbound notifications by the validator and unchanged quota runtime behavior",
        },
        {
            "id": "staging_ingress_operator_evidence",
            "status": "blocking",
            "requiredEvidence": "accepted sanitized staging ingress operator evidence from scripts/staging_ingress_operator_evidence_check.py plus guide reference and unchanged ingress runtime behavior",
        },
    ],
    "requiredFinalCommands": [
        "python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>",
        "python3 scripts/launch_acceptance_evidence.py --evidence <sanitized-launch-acceptance-evidence.json>",
        "python3 scripts/provider_operator_evidence_check.py <sanitized-provider-operator-evidence.json>",
        "python3 scripts/restore_pitr_operator_evidence_check.py --artifact <sanitized-restore-pitr-operator-evidence.json>",
        "python3 scripts/security_operator_acceptance_check.py --artifact <sanitized-security-operator-artifact.json>",
        "python3 scripts/quota_operator_evidence_check.py --evidence <sanitized-quota-budget-operator-evidence.json>",
        "python3 scripts/staging_ingress_operator_evidence_check.py <sanitized-staging-ingress-operator-evidence.json>",
        "python3 scripts/incident_response_evidence.py --evidence <sanitized-incident-response-evidence.json>",
        "./scripts/release_secret_scan.sh",
        "python3 scripts/staging_ingress_smoke.py --base-url <staging-ingress-base-url>",
        "./scripts/ci_gate_fast.sh",
        "./scripts/ci_gate.sh",
        "git diff --check origin/main..HEAD",
    ],
    "sanitization": {
        "externalServicesCalled": False,
        "productionCredentialsRequired": False,
        "secretsIncluded": False,
        "productionDataPathsRead": False,
    },
}

print(json.dumps(summary, indent=2, sort_keys=True))
PY
  if [[ "${dirty_count}" -gt 0 && "${ALLOW_DIRTY}" -ne 1 ]]; then
    echo "[FAIL] Worktree is dirty. Re-run with --allow-dirty to print this summary without failing." >&2
    exit 1
  fi
  exit 0
fi

print_step "branch"
echo "Current branch: ${branch}"
if [[ "${ahead_count}" != "unavailable" && "${behind_count}" != "unavailable" ]]; then
  echo "Ahead/behind vs ${BASE_REF}: ahead ${ahead_count}, behind ${behind_count}"
else
  echo "Ahead/behind vs ${BASE_REF}: unavailable (${BASE_REF} not found)"
fi

print_step "worktree"
echo "Staged changes: ${staged_count}"
echo "Unstaged changes: ${unstaged_count}"
echo "Untracked files: ${untracked_count}"
if [[ "${dirty_count}" -gt 0 ]]; then
  echo "Worktree dirty: yes"
  git status --short
else
  echo "Worktree dirty: no"
fi

print_step "helper scripts"
echo "scripts/release_secret_scan.sh: $(script_status "scripts/release_secret_scan.sh")"
echo "scripts/production_config_readiness.py: $(script_status "scripts/production_config_readiness.py")"
echo "scripts/launch_acceptance_evidence.py: $(script_status "scripts/launch_acceptance_evidence.py")"
echo "scripts/incident_response_evidence.py: $(script_status "scripts/incident_response_evidence.py")"
echo "scripts/staging_ingress_smoke.py: $(script_status "scripts/staging_ingress_smoke.py")"
echo "scripts/ci_gate_fast.sh: $(script_status "scripts/ci_gate_fast.sh")"

print_step "final required commands"
cat <<'COMMANDS'
python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>
python3 scripts/launch_acceptance_evidence.py --evidence <sanitized-launch-acceptance-evidence.json>
python3 scripts/provider_operator_evidence_check.py <sanitized-provider-operator-evidence.json>
python3 scripts/restore_pitr_operator_evidence_check.py --artifact <sanitized-restore-pitr-operator-evidence.json>
python3 scripts/security_operator_acceptance_check.py --artifact <sanitized-security-operator-artifact.json>
python3 scripts/quota_operator_evidence_check.py --evidence <sanitized-quota-budget-operator-evidence.json>
python3 scripts/staging_ingress_operator_evidence_check.py <sanitized-staging-ingress-operator-evidence.json>
python3 scripts/incident_response_evidence.py --evidence <sanitized-incident-response-evidence.json>
./scripts/release_secret_scan.sh
python3 scripts/staging_ingress_smoke.py --base-url <staging-ingress-base-url>
# Live ingress calls require WOLFYSTOCK_STAGING_INGRESS_SMOKE=1.
./scripts/ci_gate_fast.sh
./scripts/ci_gate.sh
git diff --check origin/main..HEAD
COMMANDS

print_step "scope"
echo "Informational preflight helper only; not a release approval tool."
echo "Does not run ./scripts/ci_gate.sh by default."

if [[ "${dirty_count}" -gt 0 && "${ALLOW_DIRTY}" -ne 1 ]]; then
  echo "[FAIL] Worktree is dirty. Re-run with --allow-dirty to print this summary without failing." >&2
  exit 1
fi

echo "[PASS] release gate summary completed"
