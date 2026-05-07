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
    ],
    "hardBlockers": [
        {
            "id": "global_mfa_enforcement_not_accepted",
            "status": "blocking",
            "requiredEvidence": "accepted global or compensated MFA enforcement evidence",
        },
        {
            "id": "rbac_coarse_fallback_actual_removal_pending",
            "status": "blocking",
            "requiredEvidence": "coarse fallback removed or explicit production exception accepted",
        },
        {
            "id": "live_quota_enforcement_not_global",
            "status": "blocking",
            "requiredEvidence": "live quota enforcement pilot and global rollout/exception evidence",
        },
        {
            "id": "real_isolated_postgresql_restore_pitr_pending",
            "status": "blocking",
            "requiredEvidence": "real isolated PostgreSQL restore/PITR execution and post-restore smoke",
        },
        {
            "id": "real_provider_credentials_live_calls_circuit_enforcement_pending",
            "status": "blocking",
            "requiredEvidence": "real provider credential/live-call acceptance plus circuit enforcement evidence",
        },
        {
            "id": "final_clean_full_release_gate_required",
            "status": "blocking",
            "requiredEvidence": "clean worktree, clean full release gate, secret scan, and final diff check",
        },
        {
            "id": "production_config_contract_acceptance_pending",
            "status": "blocking",
            "requiredEvidence": "accepted production config readiness contract using sanitized names/presence states only",
        },
    ],
    "requiredFinalCommands": [
        "python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>",
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
echo "scripts/staging_ingress_smoke.py: $(script_status "scripts/staging_ingress_smoke.py")"
echo "scripts/ci_gate_fast.sh: $(script_status "scripts/ci_gate_fast.sh")"

print_step "final required commands"
cat <<'COMMANDS'
python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>
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
