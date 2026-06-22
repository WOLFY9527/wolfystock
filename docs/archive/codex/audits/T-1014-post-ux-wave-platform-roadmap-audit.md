# T-1014 Post-UX-Wave Platform Roadmap Audit

Task: T-1014-AUDIT

Task title: Post-UX-wave platform roadmap audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/T-1014-post-ux-wave-platform-roadmap-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1014-post-ux-wave-platform-audit`
- branch: `codex/t1014-post-ux-wave-platform-audit`
- selected-branch HEAD: `b9c73186` (`T-1011: audit admin dashboard IA`)
- note: after `git fetch origin`, `origin/main` was three commits ahead at
  `27b0083c` (`T-1012: audit mobile readability`). The selected branch was not
  merged, rebased, switched, or updated.

Scope boundary:

- Source, tests, config, lockfiles, API/backend/provider/cache/auth/accounting,
  and existing audit docs were inspected, not modified.
- The only intended final diff is this audit artifact.
- Findings below distinguish current selected-branch evidence from adjacent
  follow-up branch evidence where relevant.

## Executive Summary

WolfyStock is now materially better protected than the older UX wave reports
alone imply. The strongest current improvements are:

1. P0 route/guest/admin failures are mostly converted into explicit route smoke
   and policy evidence.
2. Home and Scanner now have runtime/display provenance projections and tests
   that lock fail-closed, no-raw-leakage, and no-rank-change behavior.
3. Home chart, Scanner display panels, and smoke fixtures have been partially
   decomposed, reducing some prior maintainability pressure.
4. Admin IA is now a clearer System Settings landing model, not a missing
   dashboard problem.
5. Existing mobile-capable smokes rule out broad 390px page-breaking failures,
   but do not prove comfortable touch targets.

Current roadmap decision:

- Continue with narrow write tasks for Home state correctness and the highest
  consumer mobile friction.
- Use audit tasks before any Market/Liquidity/Rotation/Options runtime
  provenance or authority changes.
- Defer broad redesign, broad auth rewrites, broad React Doctor sweeps, and any
  provider/cache/accounting/backtest/math task that is not explicitly scoped.

## Evidence Inspected

Current selected branch:

- Required guard docs:
  `AGENTS.md`,
  `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`,
  `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`,
  `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`.
- Required audits:
  `docs/codex/audits/T-1009-auth-guard-policy-audit.md`,
  `docs/codex/audits/T-1011-admin-dashboard-ia-audit.md`.
- Roadmap/audit context:
  `T-981`, `T-987`, `T-989`, `T-990`, `T-992`, `T-995`,
  plus `T-957` where provenance boundary evidence was needed.
- Frontend route/auth/admin surfaces:
  `apps/dsa-web/src/App.tsx`,
  `apps/dsa-web/src/utils/adminCapabilities.ts`,
  `apps/dsa-web/src/components/auth/AuthGuardOverlay.tsx`.
- Current smoke and helper surfaces:
  `apps/dsa-web/e2e/ux-audit-p0-verification.smoke.spec.ts`,
  `apps/dsa-web/e2e/controlled-user-testing.smoke.spec.ts`,
  `apps/dsa-web/e2e/consumer-copy-regression.smoke.spec.ts`,
  `apps/dsa-web/e2e/home-scanner-evidence-browser.smoke.spec.ts`,
  `apps/dsa-web/e2e/fixtures/smokeEvidence.ts`.
- Current provenance/runtime evidence:
  `src/services/analysis_service.py`,
  `tests/services/test_analysis_research_readiness_projection.py`,
  `tests/test_market_scanner_service.py`,
  `tests/test_market_scanner_api_contract.py`,
  `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`,
  `apps/dsa-web/src/components/scanner/ScannerDisplayPanels.tsx`.
- Current mobile/readability code signals:
  Home, Scanner, Options, Portfolio, Watchlist, Backtest, Settings, Market, and
  Admin files referenced by compact-control and internal-scroll scans.

Adjacent follow-up signals on `origin/main`, not current selected-branch
artifacts:

- `fa9ee9fe` implements the T-1011 Admin landing copy/test clarification.
- `1b466005` adds the T-1009 route-policy smoke coverage to
  `ux-audit-p0-verification.smoke.spec.ts`.
- `27b0083c` contains
  `docs/codex/audits/T-1012-mobile-readability-touch-target-audit.md`.

## What Is Materially Improved And Protected

### Consumer Route And Guest Policy

Current route policy is explicit and mixed by design:

- guest-restricted settings/admin paths redirect to `/guest`;
- paid consumer routes use same-route overlays;
- market liquidity and rotation remain public read surfaces;
- `/options`, `/liquidity`, `/rotation`, `/admin/*` aliases resolve to
  canonical routes instead of 404-like dead ends.

Selected-branch protection:

- `App.tsx` keeps guest restricted settings/admin checks before route rendering.
- `RegisteredSurfaceRoute` renders `ConsumerProtectedFrame` for guest access to
  paid consumer routes.
- `AuthGuardOverlay` is modal, focus-managed, non-dismissible by Escape, and
  hides protected page content behind an inert backdrop.
- `ux-audit-p0-verification.smoke.spec.ts` already protects alias resolution,
  portfolio/options guest overlays, admin aliases, no generic error shell, no
  raw leakage, and no horizontal overflow for scoped routes.

Adjacent T-1009 follow-up protection:

- `1b466005` adds canonical admin guest redirect smoke, representative
  protected consumer route overlay smoke for Watchlist/Scanner/Backtest result,
  and user-activity capability denial checks.

Roadmap implication:

- Auth is now a policy-clarity and coverage problem, not a proven leakage
  blocker. Do not open a blanket redirect-to-login rewrite.

### Admin IA And Access Gates

Admin IA is materially clearer:

- `/admin` is an alias to `/settings/system`, not a separate dashboard route.
- `AdminSurfaceRoute` plus `canAccessAdminPath()` gate every canonical admin
  surface by explicit capability.
- Missing capability fields fail closed.
- `origin/main` already implements the recommended T-1011 copy/test follow-up
  on `SystemSettingsPage`, clarifying the default admin landing without adding
  a dashboard or touching backend RBAC.

Roadmap implication:

- The next admin work should be page-local mobile/touch cleanup or targeted
  capability tests only. Do not open a new dashboard or shell redesign.

### Home Evidence, Provenance, And Chart

Older T-981 language that treated Home runtime provenance as mostly future work
is now partially stale.

Current backend evidence:

- `analysis_service.py` builds and attaches `researchReadiness`,
  `evidenceCoverageFrame`, `singleStockEvidencePacket`,
  `evidenceCitationFrame`, and `sourceProvenanceFrame` into the report,
  report meta, analysis result, and public response.
- `test_analysis_research_readiness_projection.py` locks JSON-stable Home
  source provenance, public response mirroring, domain order, fail-closed
  unknown sources, provider-timeout limitations, and no secret-like raw leakage.

Current frontend evidence:

- `HomeBentoDashboardPage` extracts and renders readiness, coverage, evidence
  packet, citation, and source provenance near the conclusion-first console.
- `HomeCandlestickChartDisplay.tsx` and
  `homeCandlestickChartUtils.ts` split the chart controls/display and model
  helpers out of the formerly larger chart shell.
- Home/chart/browser and consumer-copy smokes cover visible chart/evidence
  regions, no raw leakage, no unsafe trading copy, and 390px overflow.

Remaining protection gap:

- Home route/task orchestration is still correctness-risky because the page is
  still 6207 lines and has route/task hydration state spread across effects and
  store snapshots. This is a product correctness risk, not a cosmetic issue.

### Scanner Evidence, Provenance, Ranking Boundaries

Scanner has materially improved beyond an old ranking-table-only surface:

- `candidateEvidenceFrame`, `candidateResearchReadiness`,
  `candidateResearchSummaryFrame`, and `candidateSourceProvenanceFrame` are
  present in service/API/frontend paths.
- Service tests lock additive provenance while preserving symbol order, rank,
  score, raw/final score, selected/shortlist parity, and no extra history calls.
- API contract tests lock serialization and no forbidden raw/internal/token
  leakage.
- `ScannerDisplayPanels.tsx` extracts result history, visual evidence summary,
  workflow, conclusion, and fallback display panels from the page.

Remaining protection gap:

- Scanner mobile controls and candidate actions remain P1 touch-target risks.
  Any write must preserve ranking/scoring/filtering/selection/order and
  backtest launch payloads.

### Smoke Harness And Test Assets

The smoke harness is better protected than T-990 described:

- `smokeEvidence.ts` now centralizes Home/Scanner evidence payload builders and
  consumer-safe text checks.
- The three main smoke specs are smaller than the old audit figures:
  `controlled-user-testing` 910 lines, `consumer-copy-regression` 710 lines,
  and `home-scanner-evidence-browser` 267 lines.
- Shared auth/open route helpers are already used by the current smoke specs.

Remaining protection gap:

- Smoke coverage is useful but still not a full correctness proof. It protects
  selected visible states and negative leakage patterns, not all route policies,
  all mobile tap targets, or all React state timing paths.

## Risk Classification

### Correctness / Product Risks

| Priority | Area | Risk | Classification | Next action |
| --- | --- | --- | --- | --- |
| P0 | Protected domains | Market/Liquidity/Rotation/Options runtime authority can be weakened by broad provenance or actionability rewrites. | Correctness/product and financial-safety risk | Audit first; no write without separate 5.5+xhigh task. |
| P1 | Home | Route/task hydration and pending/completed task state remain complex in a 6207-line page. | Correctness/product risk | Isolated Home orchestration write. |
| P1 | Auth | Mixed policy is intentional but still easy to misread; some coverage exists only in adjacent branch evidence. | Product/policy risk | Land/keep route-policy smoke; do not rewrite policy broadly. |
| P1 | Scanner | Mobile controls/actions are compact, but ranking and launch semantics are protected. | Product usability risk adjacent to protected ranking | Page-local UI write with rank/order invariants. |
| P1 | Options | Payoff/IV visuals use `min-w-[28rem]`, wider than 390px. | Product readability risk | Single-surface display containment write. |
| P1 | Portfolio/Watchlist | Compact actions and dense tables affect mobile use, but account/list semantics are protected. | Product risk near accounting/persistence | Defer until after higher-priority consumer research surfaces; no API/accounting changes. |
| P1 | Backtest | Result tabs/tables need mobile containment, but engine/math/schema are protected. | Product readability risk near backtest semantics | Defer or split into a display-only Backtest task. |

### Cosmetic / Maintainability Risks

| Priority | Area | Risk | Classification | Next action |
| --- | --- | --- | --- | --- |
| P1 | Mobile touch targets | Many controls are 32px to 40px or text-xs compact buttons. | Cosmetic/usability maintainability, unless on primary workflow buttons | Fix page-locally, not through shared primitive sweep. |
| P2 | Large pages | Home, Scanner, Portfolio, Watchlist, Settings, Options remain large. | Maintainability risk | Continue prop-only/display extractions; avoid behavior refactors mixed in. |
| P2 | Bundle/chunks | Route chunks remain large, but current route-lazy boundaries exist. | Maintainability/perf smell | Local page boundaries before shell/chunk config changes. |
| P2 | Admin density | Operator pages use dense tabs/disclosures. | Maintainability/readability | Page-local touch cleanup; raw detail remains folded. |
| P2 | Smoke maintainability | Fixtures are improved but still domain-coupled. | Maintainability | Extract only when duplication recurs; avoid monolithic mock router. |

## Next Tasks: Write, Audit, Or Deferred

### Recommended Write Tasks

1. **Home route/task orchestration hardening**
   - Priority: P1 correctness/product.
   - Scope: Home-local state ownership only.
   - Must not change provider/API/cache/LLM prompt/report semantics/chart data.
   - Must preserve evidence/citation/provenance render-time derivation.

2. **Home / Guest mobile hit-area pass**
   - Priority: P1 consumer UX.
   - Scope: command bar, report actions, chart controls, guest CTA.
   - Must not change Home evidence packet, chart data requests, report
     generation, consumer safety copy, or route policy.

3. **Scanner mobile controls and candidate actions**
   - Priority: P1 product UX.
   - Scope: controls, compact action hit areas, wrapping.
   - Must not change ranking, scoring, filtering, selection, result order,
     persisted shortlist, provider/cache behavior, or backtest launch payloads.

4. **Options Lab payoff/IV mobile containment**
   - Priority: P1 product readability.
   - Scope: display-only containment or mobile summary for payoff/IV visuals.
   - Must not change Options decision/risk semantics, no-trade policy,
     optimizer/ranking/gates, API shape, or order/broker boundaries.

5. **Backtest result mobile table/tab containment**
   - Priority: P1/P2, depending on whether table reading blocks controlled
     testing.
   - Scope: display-only tabs/tables/disclosures.
   - Must not change backtest engine math, fills, costs, metrics, result schema,
     stored readback, OOS/parameter semantics, or research-only copy.

### Recommended Audit Tasks

1. **Market/Liquidity/Rotation/Options authority and provenance audit**
   - Required before any runtime provenance expansion in these surfaces.
   - Must decide where existing actionability, temperature, readiness, score,
     stage, and source-authority vocabularies are authoritative.

2. **Entry-shell bundle audit**
   - Only after local Home/Scanner/Options/Market page-boundary work is measured.
   - Implementation would be high-risk because `App.tsx` and `Shell` affect all
     routes, auth, preview, and layout.

3. **Portfolio/Watchlist mobile-account boundary audit**
   - Needed before touching UI regions that could drift into accounting,
     broker sync, saved-list persistence, or scanner handoff semantics.

4. **Backtest professional-readiness audit**
   - Needed before any task that changes evidence interpretation, OOS,
     parameter stability, execution realism, or result authority.

### Deferred Tasks

Do not open these yet:

- blanket redirect-to-login or universal auth normalization;
- new `/admin/dashboard` route or cross-admin aggregation API;
- broad Market/Liquidity/Rotation/Options provenance runtime sweep;
- Scanner UX rewrite combined with provenance/ranking changes;
- Portfolio/Watchlist mobile work that touches accounting, broker, persistence,
  scanner-link payloads, or API shape;
- broad React Doctor zero-diagnostic or manual memoization sweep;
- broad `manualChunks` rewrite, entry-shell surgery, or Vite warning-limit
  increase;
- global shared button/touch-target primitive change without full affected-route
  smoke coverage;
- external UX redesign review before Home/Scanner protected evidence paths and
  mobile primary workflows are stable.

## Protected Domains Requiring Separate 5.5+xhigh Audit

Do not touch the following without a separate high-risk audit and an exact
allowed diff:

1. Auth/RBAC/security behavior, including backend auth, capability contracts,
   session semantics, and frontend route policy rewrites.
2. Provider runtime order, live-call paths, fallback semantics, freshness/live
   labeling, MarketCache TTL/SWR/cold-start behavior, cache keys, and payload
   meaning.
3. Scanner scoring, ranking, sorting, filtering, selection, thresholds,
   shortlist order, persisted rank semantics, and scanner-to-backtest payloads.
4. Portfolio accounting: cash, holdings, P&L, FX, cost basis, broker sync,
   import, replay, manual ledger, and account mutation semantics.
5. Backtest engine calculations, fills, costs, metrics, execution realism,
   OOS/walk-forward semantics, stored result authority, and result schemas.
6. Options ranking, gates, optimizer, payoff math, no-trade policy, decision
   framing, readiness authority, and API response shape.
7. Market/Liquidity/Rotation actionability, temperature, score/stage/theme-flow,
   source-authority, freshness, conclusion eligibility, and public payload
   authority.
8. AI/LLM prompts, routing, model order, fallback, retry, thresholds, raw LLM
   payload handling, and recommendation semantics.
9. Shared API/schema/contracts/stored contract versions and public DTO shape.
10. Notification routing/delivery semantics and DuckDB/PostgreSQL source of
    truth behavior.

## Recommended Next 5-Task Sequence

This sequence assumes the current T-1009 route-policy smoke, T-1011 admin
landing copy/test, and T-1012 mobile audit follow-ups are treated as current
follow-up work and not reopened as new platform tasks.

1. **T-1014-R1 WRITE: Home route/task orchestration hardening**
   - Why first: this is the highest remaining consumer correctness risk.
   - Scope: `HomeBentoDashboardPage` state transitions only, with existing Home
     lifecycle tests and Home/controlled-user smokes as gates.
   - Stop if provider/API/cache/LLM/report/chart semantics become necessary.

2. **T-1014-R2 WRITE: Home / Guest mobile hit-area pass**
   - Why second: high-impact consumer first screen, lower protected-runtime risk.
   - Scope: Home/guest/chart controls and local e2e mobile assertions only.
   - Stop if shared primitives or route/auth behavior must change.

3. **T-1014-R3 WRITE: Scanner mobile controls and candidate actions**
   - Why third: Scanner is a core research workflow and T-1012 found P1 action
     density.
   - Scope: local Scanner UI hit areas/wrapping only.
   - Required proof: rank/score/order/selection unchanged plus Scanner mobile
     smoke.

4. **T-1014-R4 WRITE: Options Lab payoff/IV mobile containment**
   - Why fourth: current chart min width exceeds a 390px viewport; it is
     consumer-visible and can be improved display-only.
   - Scope: one Options display slice only.
   - Stop if decision, readiness, optimizer, chain, ranking, or API semantics
     must change.

5. **T-1014-R5 AUDIT: Market/Liquidity/Rotation/Options authority map**
   - Why fifth: the next tempting platform feature is provenance/actionability
     expansion, but these domains are protected and semantically coupled.
   - Output: exact allowed write slices or explicit deferrals for each domain.
   - No runtime/source changes in the audit.

## Top 5 Recommendations

1. Treat auth/admin work as policy clarification and smoke hardening, not a
   license for blanket route-policy rewrites.
2. Treat Home and Scanner provenance as already partially landed protected
   contracts; future changes must preserve fail-closed and rank/order
   invariants.
3. Prioritize Home state orchestration before more Home display polish because
   it is a correctness risk.
4. Address mobile hit targets page-locally, starting with Home and Scanner.
5. Audit Market/Liquidity/Rotation/Options authority before opening any runtime
   provenance or actionability write.

## Top 5 Deferrals

1. No broad auth redirect rewrite.
2. No new admin dashboard or cross-admin aggregation API.
3. No broad provenance sweep across Market/Liquidity/Rotation/Options.
4. No global shared-button/mobile primitive sweep without a separate impact
   audit.
5. No entry-shell/manualChunks/Vite-warning change until local page-boundary
   work is measured.

## Validation Plan For This Audit Artifact

Required docs-only validation:

```bash
git diff --check
./scripts/release_secret_scan.sh
```

Expected final diff:

- `docs/codex/audits/T-1014-post-ux-wave-platform-roadmap-audit.md`

Expected final boundary:

- docs-only final diff;
- no source/test/config/lockfile/package/API/backend/provider/cache/auth/
  accounting/backtest changes;
- no modifications to existing audit docs.
