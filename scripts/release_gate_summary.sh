#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE_REF="${RELEASE_GATE_SUMMARY_BASE_REF:-origin/main}"
ALLOW_DIRTY=0

usage() {
  cat <<'USAGE'
Usage: scripts/release_gate_summary.sh [--allow-dirty]

Print the release gate status summary and the final pre-push commands.
This is an informational helper; it does not approve a release and does not run
the full CI gate.
USAGE
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --allow-dirty)
      ALLOW_DIRTY=1
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
staged_count="$(git diff --cached --name-only --diff-filter=ACMRTUXB | count_lines)"
unstaged_count="$(git diff --name-only --diff-filter=ACMRTUXB | count_lines)"
untracked_count="$(git ls-files --others --exclude-standard | count_lines)"
dirty_count=$((staged_count + unstaged_count + untracked_count))

print_step "branch"
echo "Current branch: ${branch}"
if ref_available "${BASE_REF}"; then
  read -r behind_count ahead_count < <(git rev-list --left-right --count "${BASE_REF}...HEAD")
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
echo "scripts/staging_ingress_smoke.py: $(script_status "scripts/staging_ingress_smoke.py")"
echo "scripts/ci_gate_fast.sh: $(script_status "scripts/ci_gate_fast.sh")"

print_step "final required commands"
cat <<'COMMANDS'
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
