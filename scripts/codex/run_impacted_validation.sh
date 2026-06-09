#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BASE_REF="${VALIDATION_BASE_REF:-origin/main}"
TIER="worker"
SOURCE_MODE="active"
PLAN_ONLY=0
RUN_MODE=0
PORT="${DSA_WEB_PLAYWRIGHT_PORT:-4187}"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "[impacted-validation] Python interpreter not found (tried python3, python)" >&2
    exit 127
  fi
fi

usage() {
  cat <<'EOF'
Usage: bash scripts/codex/run_impacted_validation.sh [options]

Plan or run a conservative impacted validation set for the current task branch.

Options:
  --tier worker|batch|release   Validation tier. Default: worker.
  --source active|branch        active = local changes if present else branch diff; branch = origin/main...HEAD only.
  --base-ref REF                Override origin/main base ref.
  --port PORT                   Playwright preview port. Default: 4187.
  --plan                        Print the plan only.
  --run                         Execute the planned commands.
  -h, --help                    Show this help text.

Notes:
  - At least one of --plan or --run is required.
  - batch/release stop on a dirty tree.
  - This helper is not a CI requirement.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --tier)
      TIER="${2:-}"
      shift 2
      ;;
    --source)
      SOURCE_MODE="${2:-}"
      shift 2
      ;;
    --base-ref)
      BASE_REF="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --plan)
      PLAN_ONLY=1
      shift
      ;;
    --run)
      RUN_MODE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[impacted-validation] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "${TIER}" in
  worker|batch|release) ;;
  *)
    echo "[impacted-validation] unsupported tier: ${TIER}" >&2
    exit 2
    ;;
esac

case "${SOURCE_MODE}" in
  active|branch) ;;
  *)
    echo "[impacted-validation] unsupported source mode: ${SOURCE_MODE}" >&2
    exit 2
    ;;
esac

if [[ "${PLAN_ONLY}" -eq 0 && "${RUN_MODE}" -eq 0 ]]; then
  echo "[impacted-validation] choose --plan, --run, or both" >&2
  exit 2
fi

cd "${ROOT_DIR}"

declare -a CHANGED_FILES=()
declare -a IMPACT_GROUPS=()
declare -a COMMAND_LABELS=()
declare -a COMMANDS=()

print_header() {
  echo "==> impacted-validation: $1"
}

add_group() {
  local group="$1"
  local existing
  for existing in "${IMPACT_GROUPS[@]:-}"; do
    if [[ "${existing}" == "${group}" ]]; then
      return 0
    fi
  done
  IMPACT_GROUPS+=("${group}")
}

add_command() {
  local label="$1"
  local command="$2"
  local i
  for i in "${!COMMANDS[@]}"; do
    if [[ "${COMMANDS[$i]}" == "${command}" ]]; then
      return 0
    fi
  done
  COMMAND_LABELS+=("${label}")
  COMMANDS+=("${command}")
}

has_group() {
  local target="$1"
  local existing
  for existing in "${IMPACT_GROUPS[@]:-}"; do
    if [[ "${existing}" == "${target}" ]]; then
      return 0
    fi
  done
  return 1
}

git_dirty_exists() {
  [[ -n "$(git status --short)" ]]
}

stop_if_merge_conflict() {
  if [[ -n "$(git diff --name-only --diff-filter=U)" ]] || [[ -n "$(git ls-files -u)" ]]; then
    echo "[impacted-validation] stop: merge conflict detected" >&2
    exit 1
  fi
}

stop_if_dirty_tree_for_high_tiers() {
  if [[ "${TIER}" == "worker" ]]; then
    return 0
  fi
  if git_dirty_exists; then
    echo "[impacted-validation] stop: dirty tree is not allowed for tier=${TIER}" >&2
    exit 1
  fi
}

collect_changed_files() {
  local mode="${SOURCE_MODE}"
  CHANGED_FILES=()
  while IFS= read -r line; do
    [[ -n "${line}" ]] || continue
    CHANGED_FILES+=("${line}")
  done < <("${PYTHON_BIN}" scripts/validation_changed_files.py --base-ref "${BASE_REF}" --mode "${mode}" --format lines)
  if [[ "${#CHANGED_FILES[@]}" -eq 0 ]]; then
    echo "[impacted-validation] no changed files found for mode=${mode}" >&2
    exit 1
  fi
}

stop_on_uncertain_paths() {
  local path
  for path in "${CHANGED_FILES[@]}"; do
    case "${path}" in
      docs/*|*.md|AGENTS.md|CLAUDE.md|scripts/*|tests/*|apps/dsa-web/*)
        ;;
      api/*|src/*|data_provider/*|bot/*|main.py|server.py)
        add_group "backend_auth_api"
        ;;
      *)
        echo "[impacted-validation] stop: uncertain path family: ${path}" >&2
        exit 1
        ;;
    esac
  done
}

detect_groups() {
  local path
  local docs_only=1
  for path in "${CHANGED_FILES[@]}"; do
    case "${path}" in
      docs/*|*.md)
        ;;
      scripts/*.sh|scripts/codex/*.sh)
        ;;
      *)
        docs_only=0
        ;;
    esac

    case "${path}" in
      apps/dsa-web/src/__tests__/AppRoutes.test.tsx|\
      apps/dsa-web/src/components/auth/*|apps/dsa-web/src/contexts/*Auth*|\
      apps/dsa-web/src/pages/*Guest*|apps/dsa-web/src/pages/LoginPage.tsx|\
      apps/dsa-web/src/pages/ResetPasswordPage.tsx|apps/dsa-web/e2e/guest-*|\
      apps/dsa-web/e2e/product-auth-harness.spec.ts|apps/dsa-web/e2e/viewport-route-canonicalization.smoke.spec.ts|\
      apps/dsa-web/e2e/smoke.spec.ts)
        add_group "guest_auth_router"
        ;;
    esac

    case "${path}" in
      apps/dsa-web/src/pages/Home*|apps/dsa-web/src/pages/MarketOverviewPage.tsx|\
      apps/dsa-web/src/api/*market*|apps/dsa-web/src/api/*marketOverview*|\
      apps/dsa-web/e2e/home-*|apps/dsa-web/e2e/market-overview-*|\
      apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts|\
      apps/dsa-web/e2e/market-intelligence-actionability.smoke.spec.ts|\
      apps/dsa-web/e2e/no-secret-critical-surface.smoke.spec.ts)
        add_group "market_home"
        ;;
    esac

    case "${path}" in
      apps/dsa-web/src/pages/*Scanner*|apps/dsa-web/src/pages/*Watchlist*|\
      apps/dsa-web/src/api/*scanner*|apps/dsa-web/src/api/*watchlist*|apps/dsa-web/src/api/*userAlerts*|\
      apps/dsa-web/e2e/scanner-*|apps/dsa-web/e2e/watchlist-*|\
      apps/dsa-web/e2e/home-scanner-evidence-browser.smoke.spec.ts)
        add_group "scanner_watchlist"
        ;;
    esac

    case "${path}" in
      apps/dsa-web/src/pages/*Portfolio*|apps/dsa-web/src/components/portfolio/*|\
      apps/dsa-web/src/api/*portfolio*|apps/dsa-web/e2e/portfolio-*)
        add_group "portfolio"
        ;;
    esac

    case "${path}" in
      apps/dsa-web/src/pages/*Options*|apps/dsa-web/src/api/*options*|\
      apps/dsa-web/e2e/public-safety-ai-scanner-options.smoke.spec.ts)
        add_group "options"
        ;;
    esac

    case "${path}" in
      apps/dsa-web/src/pages/*Liquidity*|apps/dsa-web/src/pages/*Rotation*|\
      apps/dsa-web/src/api/*liquidity*|apps/dsa-web/src/api/*marketRotation*|\
      apps/dsa-web/e2e/market-liquidity-monitor-degraded.spec.ts|\
      apps/dsa-web/e2e/market-rotation-observation-themes.spec.ts|\
      apps/dsa-web/e2e/rotation-radar-loading-polish.smoke.spec.ts)
        add_group "liquidity_rotation"
        ;;
    esac

    case "${path}" in
      api/*auth*|api/v1/endpoints/*|tests/test_auth_route_capability_inventory.py|apps/dsa-web/src/api/*|apps/dsa-web/src/contexts/*Auth*)
        add_group "backend_auth_api"
        ;;
    esac

    case "${path}" in
      apps/dsa-web/src/pages/*Admin*|apps/dsa-web/src/components/admin/*|\
      apps/dsa-web/src/api/*admin*|apps/dsa-web/e2e/admin-*|\
      apps/dsa-web/e2e/admin-rail-contract.smoke.spec.ts|apps/dsa-web/e2e/admin-ops-launch-surfaces.spec.ts|\
      apps/dsa-web/e2e/admin-evidence-workflow.spec.ts)
        add_group "admin_observability"
        ;;
    esac
  done

  if [[ "${docs_only}" -eq 1 ]]; then
    add_group "docs_only"
  fi
}

frontend_source_changed() {
  local path
  for path in "${CHANGED_FILES[@]}"; do
    case "${path}" in
      apps/dsa-web/src/*|apps/dsa-web/scripts/*)
        return 0
        ;;
    esac
  done
  return 1
}

release_style_frontend() {
  local path
  for path in "${CHANGED_FILES[@]}"; do
    case "${path}" in
      apps/dsa-web/src/components/*|apps/dsa-web/src/hooks/*|apps/dsa-web/src/utils/*|apps/dsa-web/src/styles/*|apps/dsa-web/src/App.tsx|apps/dsa-web/src/main.tsx)
        return 0
        ;;
    esac
  done
  return 1
}

playwright_workers() {
  if [[ "${TIER}" == "release" ]]; then
    echo 1
    return 0
  fi
  if [[ "${#IMPACT_GROUPS[@]}" -ne 1 ]]; then
    echo 1
    return 0
  fi
  if has_group "guest_auth_router" || has_group "backend_auth_api" || has_group "admin_observability"; then
    echo 1
    return 0
  fi
  echo 2
}

plan_frontend_common() {
  if ! frontend_source_changed; then
    return 0
  fi

  if [[ "${TIER}" == "release" ]] || release_style_frontend; then
    add_command "frontend lint" "npm --prefix apps/dsa-web run lint"
    add_command "frontend build" "npm --prefix apps/dsa-web run build"
  else
    add_command "frontend lint changed" "env VALIDATION_BASE_REF=${BASE_REF} npm --prefix apps/dsa-web run lint:changed"
    add_command "frontend typecheck" "npm --prefix apps/dsa-web run typecheck"
    add_command "frontend quiet build" "npm --prefix apps/dsa-web run build:quiet"
  fi
}

plan_docs_only() {
  local path
  add_command "git diff check" "git diff --check"
  for path in "${CHANGED_FILES[@]}"; do
    case "${path}" in
      *.sh)
        add_command "bash syntax ${path}" "bash -n ${path}"
        ;;
    esac
  done
}

plan_guest_auth_router() {
  local workers
  workers="$(playwright_workers)"
  add_command "vitest guest/auth/router" "npm --prefix apps/dsa-web run test -- 'src/__tests__/AppRoutes.test.tsx' 'src/components/auth/__tests__/AuthGuardOverlay.test.tsx' 'src/contexts/__tests__/AuthContext.test.tsx' 'src/pages/__tests__/GuestHomePage.test.tsx' 'src/pages/__tests__/LoginPage.test.tsx' 'src/pages/__tests__/ResetPasswordPage.test.tsx' --reporter=dot"
  add_command "playwright guest entry" "DSA_WEB_PLAYWRIGHT_PORT=${PORT} npm --prefix apps/dsa-web run test:e2e -- 'e2e/guest-entry-branding.smoke.spec.ts' --project=chromium --workers=${workers}"
  add_command "playwright auth harness" "DSA_WEB_PLAYWRIGHT_PORT=${PORT} npm --prefix apps/dsa-web run test:e2e -- 'e2e/product-auth-harness.spec.ts' --project=chromium --workers=1"
}

plan_market_home() {
  local workers
  workers="$(playwright_workers)"
  add_command "vitest market/home" "npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/HomeSurfacePage.test.tsx' 'src/pages/__tests__/MarketOverviewPage.test.tsx' 'src/api/__tests__/market.test.ts' 'src/api/__tests__/marketOverview.test.ts' 'src/api/__tests__/market-readiness.test.ts' --reporter=dot"
  add_command "playwright home chart browser" "DSA_WEB_PLAYWRIGHT_PORT=${PORT} npm --prefix apps/dsa-web run test:e2e -- 'e2e/home-chart-browser.smoke.spec.ts' --project=chromium --workers=${workers}"
  add_command "playwright home fundamentals" "DSA_WEB_PLAYWRIGHT_PORT=${PORT} npm --prefix apps/dsa-web run test:e2e -- 'e2e/home-fundamentals-summary.spec.ts' --project=chromium --workers=${workers}"
}

plan_scanner_watchlist() {
  local workers
  workers="$(playwright_workers)"
  add_command "vitest scanner/watchlist" "npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/ScannerSurfacePage.test.tsx' 'src/pages/__tests__/UserScannerPage.test.tsx' 'src/pages/__tests__/WatchlistPage.test.tsx' 'src/api/__tests__/scanner.test.ts' 'src/api/__tests__/watchlist.test.ts' 'src/api/__tests__/userAlerts.test.ts' --reporter=dot"
  add_command "playwright scanner launch" "DSA_WEB_PLAYWRIGHT_PORT=${PORT} npm --prefix apps/dsa-web run test:e2e -- 'e2e/scanner-launch-surface.spec.ts' --project=chromium --workers=${workers}"
  add_command "playwright watchlist empty state" "DSA_WEB_PLAYWRIGHT_PORT=${PORT} npm --prefix apps/dsa-web run test:e2e -- 'e2e/watchlist-empty-state-cta.spec.ts' --project=chromium --workers=${workers}"
}

plan_portfolio() {
  add_command "vitest portfolio" "npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/PortfolioPage.test.tsx' 'src/components/portfolio/__tests__/PortfolioScenarioRiskPanel.test.tsx' 'src/api/__tests__/portfolio.test.ts' --reporter=dot"
  add_command "playwright portfolio launch" "DSA_WEB_PLAYWRIGHT_PORT=${PORT} npm --prefix apps/dsa-web run test:e2e -- 'e2e/portfolio-launch-surface.spec.ts' --project=chromium --workers=1"
}

plan_options() {
  add_command "vitest options" "npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/OptionsLabPage.test.tsx' 'src/api/__tests__/optionsLab.test.ts' --reporter=dot"
  add_command "playwright options safety" "DSA_WEB_PLAYWRIGHT_PORT=${PORT} npm --prefix apps/dsa-web run test:e2e -- 'e2e/public-safety-ai-scanner-options.smoke.spec.ts' --project=chromium --workers=1"
}

plan_liquidity_rotation() {
  local workers
  workers="$(playwright_workers)"
  add_command "vitest liquidity/rotation" "npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/LiquidityMonitorPage.test.tsx' 'src/pages/__tests__/MarketRotationRadarPage.test.tsx' 'src/api/__tests__/liquidityMonitor.test.ts' 'src/api/__tests__/marketRotation.test.ts' --reporter=dot"
  add_command "playwright liquidity monitor" "DSA_WEB_PLAYWRIGHT_PORT=${PORT} npm --prefix apps/dsa-web run test:e2e -- 'e2e/market-liquidity-monitor-degraded.spec.ts' --project=chromium --workers=${workers}"
  add_command "playwright rotation radar" "DSA_WEB_PLAYWRIGHT_PORT=${PORT} npm --prefix apps/dsa-web run test:e2e -- 'e2e/market-rotation-observation-themes.spec.ts' --project=chromium --workers=${workers}"
}

plan_backend_auth_api() {
  add_command "pytest auth route capability inventory" "python3 -m pytest -q tests/test_auth_route_capability_inventory.py"
  add_command "full ci gate" "./scripts/ci_gate.sh"
}

plan_admin_observability() {
  add_command "vitest admin/observability" "npm --prefix apps/dsa-web run test -- 'src/pages/__tests__/AdminLogsPage.test.tsx' 'src/pages/__tests__/AdminEvidenceWorkflowPage.test.tsx' 'src/pages/__tests__/AdminCostObservabilityPage.test.tsx' 'src/api/__tests__/adminLogs.test.ts' 'src/api/__tests__/adminNotifications.test.ts' --reporter=dot"
  add_command "playwright admin rail contract" "DSA_WEB_PLAYWRIGHT_PORT=${PORT} npm --prefix apps/dsa-web run test:e2e -- 'e2e/admin-rail-contract.smoke.spec.ts' --project=chromium --workers=1"
}

build_plan() {
  local group
  for group in "${IMPACT_GROUPS[@]}"; do
    case "${group}" in
      docs_only) plan_docs_only ;;
      guest_auth_router) plan_guest_auth_router ;;
      market_home) plan_market_home ;;
      scanner_watchlist) plan_scanner_watchlist ;;
      portfolio) plan_portfolio ;;
      options) plan_options ;;
      liquidity_rotation) plan_liquidity_rotation ;;
      backend_auth_api) plan_backend_auth_api ;;
      admin_observability) plan_admin_observability ;;
    esac
  done

  plan_frontend_common
}

print_plan() {
  print_header "plan"
  echo "tier=${TIER}"
  echo "source=${SOURCE_MODE}"
  echo "base_ref=${BASE_REF}"
  echo "playwright_port=${PORT}"
  echo "changed_files=${#CHANGED_FILES[@]}"
  printf '%s\n' "${CHANGED_FILES[@]}" | sed 's/^/  file: /'
  echo "groups=${#IMPACT_GROUPS[@]}"
  printf '%s\n' "${IMPACT_GROUPS[@]}" | sed 's/^/  group: /'
  echo "commands=${#COMMANDS[@]}"
  local i
  for i in "${!COMMANDS[@]}"; do
    echo "  [${COMMAND_LABELS[$i]}] ${COMMANDS[$i]}"
  done
}

run_plan() {
  local i
  for i in "${!COMMANDS[@]}"; do
    print_header "${COMMAND_LABELS[$i]}"
    bash -lc "${COMMANDS[$i]}"
  done
}

stop_if_merge_conflict
stop_if_dirty_tree_for_high_tiers
collect_changed_files
stop_on_uncertain_paths
detect_groups
build_plan

if [[ "${PLAN_ONLY}" -eq 1 ]]; then
  print_plan
fi

if [[ "${RUN_MODE}" -eq 1 ]]; then
  run_plan
fi
