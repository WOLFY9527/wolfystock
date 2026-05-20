# Backend / Frontend Modular Maintenance Handbook

This handbook is the AI-first maintenance entrypoint for the current local codebase shape.

Scope guard for this handbook:

- backend / API / storage / data-provider maintenance first
- frontend references are allowed only for ownership mapping or compatibility checks
- when the frontend is under active redesign, prefer backend-only fixes and doc cleanup unless the task explicitly opens frontend scope

Use it to answer:

- which module owns a bug or performance issue
- which files to read first
- what the inputs/outputs are
- which invariants must not be broken
- what the default debug flow is

## Quick Triage Order

1. Identify the failing surface:
   - startup/runtime
   - analysis
   - scanner
   - portfolio
   - backtest
   - settings/admin
   - database/coexistence
2. Read the surface owner before touching helpers.
3. Reproduce with the narrowest verification command first.
4. Only then widen to repo-level gates (`./scripts/ci_gate.sh`, browser smoke, doctor bundle).

## Module Map

### 1. Runtime / startup

- Primary files:
  - `main.py`
  - `server.py`
  - `src/webui_frontend.py`
  - `src/storage.py`
- Dependencies:
  - runtime config from `src/config.py`
  - SQLite/PG topology from `src/storage.py`
  - WebUI asset preparation from `src/webui_frontend.py`
- Inputs:
  - `.env`
  - CLI flags such as `--serve-only`
  - optional PG env vars
- Outputs:
  - FastAPI server
  - static asset availability
  - database topology initialization
- Core logic:
  - backend startup boots config, logging, database manager, task queue, and optional frontend asset preparation
  - `prepare_webui_frontend_assets()` decides whether install/build is needed
- Known risks:
  - startup path is sensitive to frontend build scope drift
  - `src/storage.py` remains a large coordination owner
- AI-first files:
  - `main.py`
  - `src/webui_frontend.py`
  - `src/storage.py`
- Default debug flow:
  1. Run `python3 main.py --serve-only --host 127.0.0.1 --port 8001`
  2. If frontend fails, run `cd apps/dsa-web && npm run build`
  3. If DB fails, run `python3 scripts/database_doctor_smoke.py --write`

### 2. Auth / product surface / route ownership

- Primary files:
  - `apps/dsa-web/src/App.tsx`
  - `apps/dsa-web/src/hooks/useProductSurface.ts`
  - `apps/dsa-web/src/contexts/AuthContext.tsx`
  - `apps/dsa-web/src/contexts/UiLanguageContext.tsx`
- Dependencies:
  - auth status API
  - route localization helpers
  - shell/header state
- Inputs:
  - current auth state
  - current route
  - session-scoped admin surface mode
- Outputs:
  - guest vs user vs admin routing
  - personal settings vs system settings gate behavior
- Core logic:
  - `resolveProductSurfaceRole(...)` decides guest/user/admin
  - `setAdminSurfaceMode(...)` publishes session-scoped admin-mode state
  - `App.tsx` routes `/settings` to personal-only and `/settings/system` to admin-gated surfaces
- Known risks:
  - mock-based tests can miss live browser state propagation issues
  - admin-mode state is session-scoped and easy to desync if not re-rendered correctly
- AI-friendly notes:
  - If browser and tests disagree, inspect `useProductSurface.ts` first
  - Distinguish `isAdmin` from `isAdminMode`
- Default debug flow:
  1. Verify `/api/v1/auth/status`
  2. Open `/settings`, toggle admin mode, then verify `/settings/system`
  3. Compare live browser behavior with `AppRoutes.test.tsx` and `Shell.test.tsx`

### 3. Analysis pipeline

- Primary files:
  - `src/core/pipeline.py`
  - `src/analyzer.py`
  - `src/services/report_renderer.py`
  - `api/v1/endpoints/analysis.py`
- Dependencies:
  - data providers
  - notification senders
  - agent/LLM adapters
  - report schemas
- Inputs:
  - stock codes / names
  - runtime config
  - upstream data provider results
- Outputs:
  - analysis history
  - markdown / standard report payloads
  - async task progress
- Core logic:
  - fetch snapshot/history/news/fundamentals
  - build structured report context
  - render user-facing report payloads
- Known risks:
  - pipeline is large and multi-source
  - provider fallback and report rendering can drift separately
- AI-first files:
  - `api/v1/endpoints/analysis.py`
  - `src/core/pipeline.py`
  - `src/services/report_renderer.py`
- Default debug flow:
  1. Reproduce on a single stock
  2. Check API payload shape
  3. Inspect report-renderer normalization before upstream provider logic

### 4. Scanner

- Primary files:
  - `src/services/market_scanner_service.py`
  - `src/repositories/scanner_repo.py`
  - `api/v1/endpoints/market_scanner.py`
  - `apps/dsa-web/src/pages/ScannerSurfacePage.tsx`
- Dependencies:
  - local universe cache
  - provider fallback chain
  - diagnostics summary shaping
- Inputs:
  - requested market profile
  - realtime/history provider availability
- Outputs:
  - ranked shortlist
  - watchlist payloads
  - diagnostics / coverage summaries
- Core logic:
  - build universe
  - fetch snapshots/history
  - rank and persist runs
- Known risks:
  - `market_scanner_service.py` is large
  - caching and fallback semantics are easy to regress
- AI-friendly notes:
  - search for `local_universe_cache`, `coverage_summary`, `provider_diagnostics`
  - benchmark before changing fetch/cache strategy
- Default debug flow:
  1. Inspect `ScannerSurfacePage` / API route behavior
  2. Reproduce with targeted scanner tests
  3. Only then touch provider or cache logic

### 5. Portfolio

- Primary files:
  - `src/services/portfolio_service.py`
  - `src/repositories/portfolio_repo.py`
  - `api/v1/endpoints/portfolio.py`
  - `apps/dsa-web/src/pages/PortfolioPage.tsx`
- Dependencies:
  - cached snapshot bundle
  - FX refresh path
  - IBKR sync overlay
  - Phase F coexistence helpers
- Inputs:
  - account/event mutations
  - snapshot/risk queries
  - IBKR sync request payload
- Outputs:
  - portfolio snapshot
  - risk payload
  - broker connection and sync overlay data
- Core logic:
  - aggregate account + portfolio state
  - normalize currencies and cached snapshots
  - overlay IBKR read-only sync without changing serving truth
- Known risks:
  - cache invalidation is subtle
  - FX refresh and IBKR overlay are easy to race in tests
  - UI page is large and stateful
- AI-friendly notes:
  - key debugging seams:
    - `refreshPortfolioData`
    - `handleSyncIbkr`
    - cached snapshot bundle reads/writes
  - keep Phase F comparison semantics separate from runtime serving semantics
- Default debug flow:
  1. Reproduce on `/portfolio`
  2. run focused API/service tests
  3. inspect cache invalidation before changing UI timing

### 6. Backtest

- Primary files:
  - `src/services/rule_backtest_service.py`
  - `src/services/backtest_service.py`
  - `src/repositories/rule_backtest_repo.py`
  - `src/repositories/backtest_repo.py`
  - `apps/dsa-web/src/pages/BacktestPage.tsx`
  - `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx`
- Dependencies:
  - run storage
  - result reopen/trustworthiness logic
  - support/export surfaces
- Inputs:
  - strategy spec
  - benchmark mode
  - stored run artifacts
- Outputs:
  - status/detail/history/result payloads
  - trustworthiness / provenance summaries
- Core logic:
  - execute deterministic runs
  - reopen stored results with stored-first precedence
  - expose integrity/provenance/readback summaries
- Known risks:
  - file size is extreme
  - stored-first + legacy fallback behavior is delicate
- AI-friendly notes:
  - key anchors:
    - `result_authority`
    - `artifact_availability`
    - `readback_integrity`
  - do not mix “performance cleanup” with semantic fallback changes
- Default debug flow:
  1. locate failing domain inside `rule_backtest_service.py`
  2. reproduce with one targeted test file
  3. inspect stored-first authority flags before editing calculations

### 7. Database / coexistence / doctor bundle

- Primary files:
  - `src/storage.py`
  - `src/storage_postgres_bridge.py`
  - `src/storage_topology_report.py`
  - `src/storage_phase_g_observability.py`
  - `src/database_doctor.py`
  - `src/postgres_*_store.py`
- Dependencies:
  - config
  - SQLite primary store
  - optional PG bridge DSN
- Inputs:
  - live `.env` config
  - optional disposable real-PG DSN
- Outputs:
  - topology reports
  - doctor bundle markdown/json
  - phase-store runtime descriptions
- Core logic:
  - SQLite remains primary runtime truth
  - PG stores remain bridge/shadow/comparison surfaces by phase
  - doctor bundle summarizes phase readiness and invariants
- Must-keep invariants:
  - SQLite primary truth unchanged
  - Phase F serving truth remains `sqlite`
  - Phase F PG role remains `comparison_only_shadow`
  - Phase G live source remains `.env`
- AI-friendly notes:
  - read these first:
    1. `src/storage.py`
    2. `src/storage_postgres_bridge.py`
    3. `src/storage_topology_report.py`
    4. `src/storage_phase_g_observability.py`
    5. `src/database_doctor.py`
  - `Phase F` authority reads already batch through `get_account_shadow_bundles(account_ids=...)`; verify regressions against `tests/test_postgres_phase_f.py` before reintroducing single-account fetch loops
  - Real-PG bundle output is intentionally normalized for deterministic diffs; keep `_normalize_real_pg_bundle_report()` redactions for temporary SQLite paths and probe session ids
- Default debug flow:
  1. `python3 scripts/database_doctor_smoke.py --write`
  2. if needed, `python3 scripts/database_doctor_smoke.py --real-pg-bundle --write`
  3. only then inspect per-phase store logic

### 8. Frontend shell / settings / admin

- Primary files:
  - `apps/dsa-web/src/components/layout/Shell.tsx`
  - `apps/dsa-web/src/components/layout/SidebarNav.tsx`
  - `apps/dsa-web/src/pages/PersonalSettingsPage.tsx`
  - `apps/dsa-web/src/pages/SettingsPage.tsx`
  - `apps/dsa-web/src/pages/SystemSettingsPage.tsx`
  - `apps/dsa-web/src/components/layout/AdminNav.tsx`
- Dependencies:
  - auth/product-surface state
  - i18n core
  - settings API/config surfaces
- Inputs:
  - current identity
  - admin surface mode
  - settings categories/config payload
- Outputs:
  - personal-only settings route
  - admin-only control-plane route
  - shell nav actions
- Core logic:
  - `/settings` is personal-only
  - `/settings/system` is admin-only and should stay distinct
  - `AdminNav.tsx` is a system-nav layer, not personal settings content
- Known risks:
  - `SettingsPage.tsx` is still large
  - auth-gated Playwright smoke still depends on a local password env var
- AI-friendly notes:
  - treat “settings vs system settings” ownership as a product invariant
  - do not merge `/settings` and `/settings/system` back together casually
  - if smoke assertions still expect `/settings` to be the system control plane, update the smoke first; do not “fix” runtime IA to satisfy stale E2E assumptions
- Default debug flow:
  1. verify `/settings`
  2. toggle admin mode in browser
  3. verify `/settings/system`
  4. compare live behavior with `Shell.test.tsx`, `AppRoutes.test.tsx`, `PersonalSettingsPage.test.tsx`

## Fast Command Matrix

### Frontend

```bash
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run test
npm --prefix apps/dsa-web run build
DSA_WEB_PLAYWRIGHT_PORT=4181 npm --prefix apps/dsa-web run test:e2e -- e2e/smoke.spec.ts --project=chromium --grep "login page renders password form"
```

Avoid repo-root `npx playwright test apps/dsa-web/e2e/...` and
`npx --prefix apps/dsa-web playwright test ...` when the test depends on
`apps/dsa-web/playwright.config.ts`.

### Backend

```bash
./scripts/ci_gate.sh
python3 -m pytest tests/test_database_doctor.py tests/test_postgres_phase_f.py tests/test_postgres_phase_g.py tests/test_postgres_runtime_real_pg.py -q
```

### Browser / startup

```bash
python3 main.py --serve-only --host 127.0.0.1 --port 8001
```

### Database doctor

```bash
python3 scripts/database_doctor_smoke.py --write
python3 scripts/database_doctor_smoke.py --real-pg-bundle --write
```

## What Not To Delete Blindly

- `src/postgres_phase_{a..g}.py`
  - compatibility shims, not confirmed-dead runtime waste
- `docs/architecture/archive/phase-f/*`
  - reviewer/audit history, not temp trash
- `apps/dsa-web/src/pages/SystemSettingsPage.tsx` and `apps/dsa-web/src/components/layout/AdminNav.tsx`
  - active route-split files for the admin control plane, not duplicate trash
- Phase F/G invariants in doctor/coexistence code
  - these are semantic boundaries, not cleanup targets

## Current Audit Snapshot

- Startup chain hardening: improved
- Frontend tests: green
- Backend gate: green
- Default doctor smoke: green
- Real-PG bundle smoke: green
- Browser smoke:
  - `/`, `/settings`, `/portfolio`, `/settings/system`, `/zh/settings/system`: green
