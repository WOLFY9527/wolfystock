# T-1212 Watchlist Research Workflow v1 audit

Task ID: T-1212
Task title: Watchlist Research Workflow v1 audit
Mode: READ-ONLY-AUDIT
Base commit inspected before report: `5b9567d4`

## Scope and method

- This audit inspected current Watchlist, Scanner, Report, Alerts, Portfolio, protected-domain, and source-confidence contracts.
- Final diff is limited to this Markdown report.
- No source, config, package, API/schema implementation, provider/cache/runtime, DB, migration, frontend behavior, notification delivery, scanner ranking, report generation, alert delivery, or portfolio accounting file was changed.
- `mcp__ace-tool__search_context` was not available in this Codex toolset, so the audit used `rg` and targeted file reads.

## Executive summary

Watchlist today is a user-owned scanner-candidate tracking surface, not a first-class research workflow state machine. It already has enough inventory to support an observation-first v1 without migration: Scanner can save candidates into Watchlist; Watchlist can show scanner score snapshots, limited scanner intelligence, latest completed backtest summary, catalyst exposure projections, in-app-only user alert rules/events, and hand off to async single-stock analysis.

The missing piece is persisted workflow authority. There is no first-class `workflow_state`, pending-validation record, alert-trigger linkage, research-completed linkage, invalidation state, archive state, or report id on the Watchlist model/API. Therefore the safest v1 is a consumer-visible derived workflow strip and route handoff that uses existing fields only, while keeping raw provider/source/debug fields collapsed or admin-only. Any durable workflow state requires a later schema/API task.

## Current capability inventory

### Backend model and API

- `UserWatchlistItem` persists `owner_id`, `symbol`, `market`, `name`, `source`, scanner lineage, score snapshot fields, `theme_id`, `universe_type`, `notes`, and timestamps. It does not persist workflow state or archive/invalidated/research linkage fields. See `src/storage.py:2061`.
- Watchlist API exposes list, add/update, delete, score refresh, and refresh status. See `api/v1/endpoints/watchlist.py:107`, `api/v1/endpoints/watchlist.py:126`, `api/v1/endpoints/watchlist.py:153`, `api/v1/endpoints/watchlist.py:177`, `api/v1/endpoints/watchlist.py:215`.
- Watchlist schema allows only `source="scanner"` on create/refresh. See `api/v1/schemas/watchlist.py:20` and `api/v1/schemas/watchlist.py:179`.
- `WatchlistService.add_item()` is owner-scoped and idempotent by `owner_id + symbol + market`; `refresh_scores()` only reuses persisted scanner candidates and marks stale when no scanner score is found. See `src/services/watchlist_service.py:614` and `src/services/watchlist_service.py:681`.
- Watchlist list responses attach derived read-only intelligence from persisted scanner candidate diagnostics and latest completed rule backtest rows. See `src/services/watchlist_service.py:384`, `src/services/watchlist_service.py:511`, and `src/services/watchlist_service.py:544`.

### Scanner linkage

- Scanner persists `MarketScannerRun` and `MarketScannerCandidate` rows with run metadata, candidate rank/score, reasons, metrics, and diagnostics. See `src/storage.py:1669` and `src/storage.py:1704`.
- Scanner exposes daily and recent scanner watchlists through `/api/v1/scanner/watchlists/today` and `/api/v1/scanner/watchlists/recent`. See `api/v1/endpoints/scanner.py:289` and `api/v1/endpoints/scanner.py:318`.
- Scanner has daily `watchlist_date` and cross-day comparison read models. See `api/v1/schemas/scanner.py:178`, `api/v1/schemas/scanner.py:405`, and `src/services/market_scanner_service.py:4501`.
- Scanner UI can save individual or batch candidates to user Watchlist through `watchlistApi.addWatchlistItem()`. See `apps/dsa-web/src/pages/UserScannerPage.tsx:2505` and `apps/dsa-web/src/pages/UserScannerPage.tsx:2559`.

### Frontend Watchlist surface

- `/watchlist` and `/:locale/watchlist` route to `WatchlistPage`. See `apps/dsa-web/src/App.tsx:403` and `apps/dsa-web/src/App.tsx:440`.
- Watchlist frontend API supports list/add/delete/refresh/status only. See `apps/dsa-web/src/api/watchlist.ts:119`.
- Watchlist types mirror scanner lineage, score snapshot, notes, derived intelligence, catalyst exposures, and refresh status. See `apps/dsa-web/src/types/watchlist.ts:1`.
- Watchlist page can list/filter/sort tracked candidates, refresh scanner score snapshots, remove rows, copy symbols, hand off to async analysis, run existing backtest workflow, and mount the user alert rail for the active symbol. See `apps/dsa-web/src/pages/WatchlistPage.tsx:1399`, `apps/dsa-web/src/pages/WatchlistPage.tsx:1465`, `apps/dsa-web/src/pages/WatchlistPage.tsx:1530`, and `apps/dsa-web/src/pages/WatchlistPage.tsx:2197`.
- Existing UI state labels such as "保持观察" are derived display copy, not persisted workflow state. A negative search found no first-class workflow/archive/invalidated/research linkage field in Watchlist model/API/types.

### Alerts

- User alerts are owner-scoped, in-app-only, and currently limited to `watchlist_price_threshold`. See `api/v1/schemas/user_alerts.py:7`, `src/services/user_alert_service.py:18`, and `src/storage.py:2093`.
- User alert events are sanitized, owner-scoped, and in-app-only. See `src/storage.py:2116` and `src/services/user_alert_service.py:262`.
- Current alert service tests assert that alert rule/event handling does not call provider quote paths or notification delivery. See `tests/test_user_alert_service.py:103`.

### Reports and research readiness

- Home and Watchlist analysis handoff use `POST /api/v1/analysis/analyze` via `analysisApi.analyzeAsync(...)`. See `docs/ai-decision-engine.md:7` and `apps/dsa-web/src/api/analysis.ts:18`.
- Watchlist analysis handoff includes `source=watchlist` in the destination URL, but the analysis request still uses `selectionSource: "manual"`. See `apps/dsa-web/src/pages/WatchlistPage.tsx:1399` and `apps/dsa-web/src/pages/WatchlistPage.tsx:896`.
- Analysis reports already carry `researchReadiness` projections in report payloads/history. See `src/services/analysis_service.py:831`, `src/services/analysis_service.py:890`, and `api/v1/schemas/history.py:159`.
- Persisted analysis reports are attached through the existing analysis history path, not linked back to Watchlist rows. See `src/repositories/analysis_repo.py:191` and `src/services/analysis_service.py:686`.

### Portfolio

- Portfolio is a protected accounting domain. It owns holdings, cash, P&L, FX/native currency behavior, cost basis, broker sync, ledger mutations, and read projections. See `docs/architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md:62`.
- Watchlist currently does not mutate Portfolio and should remain observation-only until a separately scoped portfolio bridge task exists.

## Existing fields versus future schema/API work

### Already exists

- Candidate identity: `owner_id`, `symbol`, `market`, `name`.
- Scanner provenance: `source`, `scanner_run_id`, `scanner_rank`, `scanner_score`, `theme_id`, `universe_type`, `notes`.
- Score snapshot state: `last_scored_at`, `score_source`, `score_profile`, `score_reason`, `score_status`, `score_error`.
- Derived response-only intelligence: scanner status, local provenance, source-confidence projection, investor signal, catalyst exposures, latest completed backtest summary.
- Current-symbol alert rule/event read/write via separate user-alert API.
- Async report handoff via analysis task and URL query state.

### Missing durable fields

- Workflow state: `discovered`, `pending_validation`, `observing`, `alert_triggered`, `research_completed`, `invalidated`, `archived`.
- State transition timestamps and reason codes.
- Pending-validation checklist/evidence packet.
- Alert-trigger event link to a Watchlist item.
- Research task/report link to a Watchlist item.
- Invalidation reason, invalidated-at, invalidated-by.
- Archive reason, archived-at, archived-by.
- Durable consumer-safe versus admin/debug metadata boundaries for each workflow state.

These are schema/API changes. They should not be hidden in existing `notes` because notes are free text and cannot safely carry workflow authority.

## Proposed workflow state model

Use explicit future states, but project them from existing data only until a migration is approved.

| State | Meaning | Current no-migration projection | Needs future persistence |
| --- | --- | --- | --- |
| `discovered` | Candidate came from Scanner discovery. | `source=scanner` with scanner lineage or scanner score. | Durable state and discovery evidence id. |
| `pending_validation` | Candidate lacks enough saved evidence for observing. | `score_status` stale/unknown, missing scanner lineage, or no derived intelligence. | Validation checklist and missing-evidence reasons. |
| `observing` | Candidate has enough saved context to monitor as observation-only. | Scanner evidence present and not failed; optional backtest/report evidence remains display-only. | State transition timestamp and owner intent. |
| `alert_triggered` | In-app alert event exists for the symbol. | Existing user-alert events can be shown by symbol, but no item link exists. | Watchlist item id on alert events or a join table. |
| `research_completed` | A report/research task completed for the candidate. | Route handoff can navigate to Home/report task; no Watchlist row link exists. | Analysis task/report id and completed-at on workflow event. |
| `invalidated` | Observation is no longer valid for a recorded reason. | Cannot persist safely today. Could only be shown as transient derived stale/failed state. | Invalidation state, reason, actor, timestamp. |
| `archived` | User intentionally removes from active board while retaining history. | Delete removes row today; no archive exists. | Soft archive fields or separate archive table. |

State projection must remain observation-only and fail closed. It must not infer source authority, score authority, or right-to-display from provider/source/freshness labels, per `docs/data-reliability/provider-source-confidence-contract.md`.

## What can be implemented first without DB migration

1. A derived, consumer-safe workflow strip on Watchlist rows/detail rail:
   - compute `discovered`, `pending_validation`, `observing`, and transient `alert_triggered` from existing list/alert data;
   - show only product-language labels such as `待验证`, `观察中`, `有提醒记录`, `需刷新`;
   - do not persist state and do not expose raw provider/source-confidence/debug fields.
2. A no-migration research handoff polish:
   - preserve existing analysis trigger and Home route handoff;
   - improve visible copy around "research started/completed elsewhere" without adding Watchlist row persistence;
   - keep report data owned by analysis history.
3. A user-alert rail integration polish:
   - display existing in-app alert rule/event count for the active symbol;
   - keep rule/event API unchanged and in-app-only.
4. A scanner-to-watchlist provenance display polish:
   - use existing scanner run id/rank/score/theme/universe fields;
   - keep scanner ranking/selection/order untouched.

No-migration work should not implement `invalidated` or `archived` as durable states. `invalidated` can only be a derived stale/failed display state. `archived` requires persistence because current delete loses the row.

## Consumer-visible versus admin/debug-only

### Consumer-visible

- Candidate identity, market, saved name, and saved observation note.
- Consumer-safe scanner lineage labels: scanner sourced, rank/score snapshot, score recently refreshed or stale.
- Coarse workflow labels: discovered, pending validation, observing, alert recorded, research handoff available, stale/needs refresh.
- In-app-only alert rule/event summaries without provider internals or notification delivery claims.
- Existing report readiness and evidence limitation copy, translated into user-safe language.

### Admin/debug-only or collapsed by default

- Provider id, endpoint, cache key, fallback depth, raw latency/quota/circuit data.
- Raw source-confidence fields, raw reason codes, authority flags, confidence weights, coverage ratios.
- Raw scanner diagnostics JSON, provider payloads, prompt/LLM payloads, stack traces.
- Any right-to-display or source authority review metadata.
- Alert delivery internals beyond the current in-app-only contract.

Consumer surfaces should receive bounded product states; admin routes may expose sanitized diagnostics only when gated.

## Later connection plan

### Scanner -> Watchlist

- Scanner remains discovery and ranking owner.
- Watchlist consumes persisted scanner candidate references and displays lineage only.
- Future workflow work must not change scanner scoring, selection, thresholds, ranking, sorting, or provider/runtime semantics.

### Watchlist -> Report

- Watchlist may start or link to existing analysis tasks.
- Report/research readiness remains owned by analysis/report services.
- Future durable linkage should store task/report ids on a workflow event or join table, not in free-text notes.

### Watchlist -> Alerts

- Alerts remain in-app-only until a separately scoped notification task exists.
- Future `alert_triggered` should link alert events to a Watchlist item id or stable item identity.
- No notification sending should be added in the Watchlist workflow v1 slice.

### Watchlist -> Portfolio

- Portfolio remains protected accounting/read-model owner.
- Watchlist may later show read-only "already in portfolio" or "related holding exists" projection only after a portfolio bridge task defines consumer-safe fields.
- No portfolio mutation or accounting interpretation belongs in Watchlist v1.

## P0 implementation gaps

- No durable workflow state or transition contract.
- No Watchlist item to alert event linkage.
- No Watchlist item to analysis task/report linkage.
- No archive/soft-delete semantics.
- No invalidation reason or audit state.
- No explicit consumer/admin workflow projection contract.
- Current analysis request from Watchlist uses `selectionSource: "manual"` even though the route handoff uses `source=watchlist`; this should be reviewed before any workflow analytics rely on selection source.

## P1 implementation gaps

- No dedicated workflow event log for state transitions.
- No report completion backfill from analysis history to Watchlist.
- No alert-trigger rollup by item id.
- No workflow filters for future states.
- No state-specific tests that prove source-confidence/admin diagnostics stay out of consumer-default UI.
- No Portfolio read-only bridge for "related holding" context.

## Smallest safe v1 execution slice

Recommended first task: add a no-migration Watchlist derived workflow strip and tests.

Allowed files:

- `apps/dsa-web/src/pages/WatchlistPage.tsx`
- `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx`
- optionally `apps/dsa-web/src/types/watchlist.ts` only if type aliases are needed for local derived UI state
- optionally `docs/CHANGELOG.md` if product-visible copy/state labels are changed

Forbidden files:

- `src/storage.py`
- `api/v1/schemas/watchlist.py`
- `api/v1/endpoints/watchlist.py`
- `src/services/watchlist_service.py`
- `api/v1/schemas/user_alerts.py`
- `api/v1/endpoints/user_alerts.py`
- `src/services/user_alert_service.py`
- `src/services/market_scanner_service.py`
- `api/v1/schemas/scanner.py`
- `api/v1/endpoints/scanner.py`
- `src/services/analysis_service.py`
- `api/v1/endpoints/analysis.py`
- Portfolio services/schemas/API/client files
- provider/cache/runtime/config/package/lock/migration files

Acceptance for that first slice:

- Consumer UI shows derived state labels without persisting them.
- Existing Watchlist list/add/delete/refresh APIs are unchanged.
- Existing scanner ranking/selection/order is unchanged.
- Existing user alerts remain in-app-only.
- No report generation or notification sending is triggered by rendering the strip.
- No trading, order, or position guidance is introduced.

Suggested focused validation for that future slice:

```bash
npm --prefix apps/dsa-web run test -- src/pages/__tests__/WatchlistPage.test.tsx --run
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
git diff --check -- apps/dsa-web/src/pages/WatchlistPage.tsx apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx
./scripts/release_secret_scan.sh
```

## Audit validation

Required for this report-only task:

```bash
git diff --check
./scripts/release_secret_scan.sh
```
