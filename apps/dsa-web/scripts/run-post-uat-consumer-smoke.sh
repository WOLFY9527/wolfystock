#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VITEST_BIN="${APP_DIR}/node_modules/.bin/vitest"

if [[ ! -x "${VITEST_BIN}" ]]; then
  echo "Vitest is unavailable. Run 'npm --prefix apps/dsa-web ci' first." >&2
  exit 127
fi

cd "${APP_DIR}"

COMMON_ARGS=(run --pool=forks --maxWorkers=1 --no-file-parallelism)
MARKET_OVERVIEW_SMOKE_PATTERN='renders bounded visual evidence cards and fail-closed unavailable copy without internal leakage|does not promote stale or fallback evidence diagnostics into the default route surface|renders a top directional summary for mixed low-confidence evidence|renders decision readiness states for ready, observation-only, and unavailable overview evidence|renders a compact observational posture panel from market decision semantics|keeps regimeSummary inside the existing evidence disclosure with consumer-safe observation wording|keeps default consumer market overview surfaces free of raw evidence metadata vocabulary|keeps data-insufficient posture conservative without trading advice language|does not show an empty state when fallback cards are still useful grouped content|keeps fallback-only cards accessible without an empty-state detour|does not show the category empty state when real cards are visible'

"${VITEST_BIN}" "${COMMON_ARGS[@]}" \
  src/test-utils/__tests__/consumerRawLeakageGuard.test.ts \
  src/components/common/__tests__/ApiErrorAlert.test.tsx \
  src/components/common/__tests__/AppErrorBoundary.test.tsx \
  src/components/common/__tests__/ConsumerResearchEmptyState.test.tsx \
  src/pages/__tests__/HomeSurfacePage.test.tsx \
  src/pages/__tests__/ResearchIaPages.test.tsx \
  src/pages/__tests__/PortfolioPage.test.tsx \
  src/pages/__tests__/OptionsLabPage.test.tsx \
  src/pages/__tests__/WatchlistPage.test.tsx \
  src/api/__tests__/marketDecisionCockpit.test.ts \
  src/api/__tests__/stocks.test.ts \
  src/__tests__/AppRoutes.test.tsx \
  src/__tests__/ProtectedRouteAuthRequired.test.tsx \
  src/pages/__tests__/NotFoundPage.test.tsx

"${VITEST_BIN}" "${COMMON_ARGS[@]}" \
  src/pages/__tests__/MarketOverviewPage.test.tsx \
  -t "${MARKET_OVERVIEW_SMOKE_PATTERN}"
