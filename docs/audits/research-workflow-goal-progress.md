# Research Workflow v1 Goal Progress

Date: 2026-06-11

Mode: private-beta workflow implementation. The workflow must remain read-only
and observation-only. It must not add broker/order/trade paths, portfolio
mutation, live alert delivery, provider runtime/fallback/cache changes, quota
enforcement, backtest math/fill/cost changes, options recommendation/ranking
semantic changes, auth/RBAC/session runtime changes, or DB migrations/cleanup.

## Checkpoint 1: Workflow Gap Map

Commit target: `checkpoint(research): map workflow gaps`

### Current Route Map

| Step | Route | Current state | Safe workflow role |
| --- | --- | --- | --- |
| Discovery | `/scanner` | Public scanner surface with candidate evidence, readiness strips, empty-state recovery, Watchlist save actions, and secondary links to Watchlist/Market Overview. | Start with candidate discovery and evidence sufficiency. |
| Follow-up | `/watchlist` | Protected watchboard with scanner lineage, workflow chips, stale/limited evidence labels, Backtest links, and result links. | Track candidate observation state after explicit save. |
| Exposure | `/portfolio` | Protected portfolio workspace with exposure summary, trust strips, valuation notes, and observation-only scenario risk panel. Also contains manual ledger and sync surfaces. | Show exposure awareness only through existing read-only summary/notes; do not deep-link users to mutation rails. |
| Validation | `/backtest` and `/backtest/results/:runId` | Protected backtest workspace with research boundary, scanner handoff query parsing, result inspection, and historical/rule modules. | Validate a candidate through existing backtest routes without changing engine semantics. |
| Scenario review | `/options-lab` | Protected options lab with readiness gate summary, scenario evidence, assumptions, visuals, and risk boundary copy. | Review scenario boundaries where options data permits; no strategy recommendation or execution semantics. |

### Existing Evidence And Readiness Reuse

- Scanner already builds consumer readiness and top-down context views, normalizes
  candidate evidence, and renders `ConsumerResearchReadinessStrip`,
  `ScannerCandidateEvidenceStrip`, `ScannerCandidateResearchSummary`, visual
  evidence summaries, and workflow next steps.
- Scanner already saves selected or manually recovered symbols to Watchlist with
  source `scanner`, `scannerRunId`, `scannerRank`, `scannerScore`, `themeId`,
  `universeType`, and safe notes.
- Watchlist already displays scanner lineage through `scanner_watchlist_lineage_v1`,
  workflow chips, stale/unknown/limited confidence states, and Backtest status.
- Watchlist already builds `/backtest?source=scanner&origin=watchlist&symbol=...`
  links and result links for existing backtest evidence.
- Portfolio already exposes concentration, market/currency/symbol exposure,
  FX/valuation trust strips, and a scenario risk panel that declares no broker
  sync and no accounting mutation.
- Backtest already parses scanner-origin query handoff and renders a research
  boundary that says the page does not place orders, connect to brokers, or
  change portfolio holdings.
- Options Lab already surfaces research readiness, gate summaries, scenario
  evidence, assumption lines, visuals, and visible risk boundary copy using
  observation/sample wording.

### Workflow Gaps

- Scanner's primary next-step panel has a Watchlist link, but it does not yet
  show the full private-beta research path or explain how Portfolio, Backtest,
  and Options fit after Watchlist.
- Watchlist has row-level workflow state and Backtest actions, but it does not
  yet provide a compact cross-route research path that names Portfolio exposure
  review and Options scenario review as read-only next stops.
- Portfolio has the right exposure data, but the page also contains manual
  ledger, broker import, and sync controls. Research workflow links must land on
  read-only exposure/notes context and must not promote mutation controls.
- Backtest handoff currently accepts `source=scanner` only. Watchlist builds
  `origin=watchlist`, but the visible banner still says "From scanner" and does
  not describe the Watchlist/Portfolio/Options continuation.
- Options Lab is already observation-oriented, but it does not yet accept or
  display workflow source context from Watchlist/Backtest/Portfolio.
- There is no single final route map or deferred follow-up register for the
  private-beta research workflow.

### Safe Smallest Slice

1. Add shared frontend-only workflow route helpers and labels for the five
   stops: Scanner, Watchlist, Portfolio exposure, Backtest, Options Lab.
2. Add read-only workflow panels/links where they reduce ambiguity:
   Scanner next steps, Watchlist detail/empty state, Portfolio exposure summary,
   Backtest handoff banner, and Options Lab input/hero area.
3. Use existing evidence/readiness display; do not invent new scoring,
   decisioning, provider calls, or persistence.
4. Keep admin/internal diagnostics out of consumer pages by reusing existing
   consumer-safe normalizers and adding tests for visible copy.
5. Document every skipped connection that needs runtime semantics, storage
   mutation, provider calls, or product approval.

### Approval-Required Follow-Ups

| Follow-up | Likely files | Why deferred | Approval needed |
| --- | --- | --- | --- |
| Persist workflow state across pages beyond query params | Backend API, DB schema, frontend types | Requires storage mutation and likely schema migration. | Product + backend data contract approval. |
| Add Portfolio-symbol contextual query endpoint for arbitrary candidate symbols | `api/`, `src/services/portfolio*`, frontend API | Requires backend projection contract and account scoping decisions. | Backend/API + privacy approval. |
| Trigger live Watchlist alerts from workflow | `api/userAlerts`, notification services | Would create live alert delivery path. | Product + notification safety approval. |
| Expand Backtest route to run new validation modes automatically | backtest services and frontend | Would change runtime semantics and possibly provider hydration/math behavior. | Backtest contract approval. |
| Promote Options scenario output into recommendation/ranking semantics | Options API/services/frontend | Would change options recommendation semantics and actionability. | Product + legal/safety approval. |

### Validation Plan

- Always: `git diff --check`
- Always: `./scripts/release_secret_scan.sh --local-only`
- Frontend touched: `cd apps/dsa-web && npm run typecheck && npm run build`
- Focused unit tests after frontend changes:
  - `cd apps/dsa-web && npx vitest run src/pages/__tests__/UserScannerPage.test.tsx`
  - `cd apps/dsa-web && npx vitest run src/pages/__tests__/WatchlistPage.test.tsx`
  - `cd apps/dsa-web && npx vitest run src/pages/__tests__/PortfolioPage.test.tsx`
  - `cd apps/dsa-web && npx vitest run src/pages/__tests__/BacktestPage.test.tsx`
  - `cd apps/dsa-web && npx vitest run src/pages/__tests__/OptionsLabPage.test.tsx`
- Bounded Playwright smoke when practical: a workflow route smoke covering
  Scanner, Watchlist, Portfolio, Backtest, and Options Lab with mocked data.

### Protected Domains Status

No code changes yet. No broker/order/trade path, portfolio mutation, live alert
delivery, provider runtime/fallback/cache change, quota enforcement, public
launch approval, backtest math/fill/cost change, options recommendation/ranking
semantic change, auth/RBAC/session runtime change, or DB migration/cleanup has
been added.
