# High-growth Retention Tier Policy

Date: 2026-06-11
Task: T-1469
Mode: docs-only retention policy evidence. No runtime code, cleanup job,
scheduler, database migration, production data access, provider behavior, quota
behavior, auth/RBAC behavior, portfolio accounting, backtest calculation,
frontend behavior, cache TTL, or public launch approval was changed.

## 1. Status

Current policy status: **POLICY-ONLY / REVIEW-REQUIRED**.

This document classifies high-growth WolfyStock data and artifact classes into
retention tiers for public/multi-user readiness planning. It is not a legal or
compliance opinion, not a deletion authorization, not a public launch approval,
and not evidence that any destructive cleanup has run.

Any future implementation must be preview-first, owner/domain-aware, offline or
operator-sanitized where possible, and must default to `deleteAllowed=false`
until a separately approved task explicitly enables destructive behavior.

## 2. Tier Model

| Tier | Purpose | Default posture | Candidate retention | Cleanup posture |
| --- | --- | --- | --- | --- |
| R0 regulatory/accounting evidence | Security, admin, billing/accounting, backup/restore, and operator review evidence | Preserve longest; aggregate only after review | 1-7 years depending on operator/legal policy; monthly aggregates 2+ years for cost/accounting | No default delete; manual/operator policy required |
| R1 user source-of-truth | User-owned durable records such as portfolio accounting, committed imports, and user watchlists | Preserve by default until user deletion/export policy exists | Indefinite by default | No TTL cleanup by default |
| R2 generated analysis/report data | Generated reports, research packets, backtest summaries, scanner results, and reproducibility metadata | Retain summaries longer than bulky traces/raw context | 180-365 days for user-visible summaries; 1+ year for backtest run summaries and reproducibility metadata | Preview-only cleanup for bulky derived artifacts |
| R3 operational diagnostics | Debug logs, execution traces, provider probes, task progress, and verbose diagnostics | Retain enough for support and incidents, then compact | 7-180 days depending on failure/security relevance | Preview-only cleanup after terminal summary/aggregate exists |
| R4 ephemeral cache/transient preview | Guest/session/cache metadata, import previews, temporary build/test artifacts, and non-authoritative caches | Short-lived; do not treat as source-of-truth | Minutes to 7 days, except CI/build retention controlled by the external platform | Delete/expire only after source-of-truth exclusion is proven |

The tier labels are planning labels only. They do not change any existing table,
file, API response, cache behavior, scheduler, or cleanup route.

## 3. Classification Rules

Use these rules before assigning a specific artifact to a retention tier:

- Regulatory/accounting evidence includes admin/security audit events,
  quota/cost/accounting evidence, accepted operator evidence, backup/restore
  drill evidence, and pricing/accounting aggregates. It should outlive routine
  debug logs and must avoid raw secrets or provider payloads.
- Debugging logs include execution logs, provider diagnostic events, verbose
  task progress, stack-adjacent reason labels, and support traces. They are
  not accounting truth and should be compacted before they dominate storage.
- User-uploaded/imported data includes broker/import files, parsed import
  previews, and committed portfolio rows. Raw upload files and parse previews
  should not be persisted by default; committed ledger/cash/corporate-action
  rows become user source-of-truth and are preserve-by-default.
- Generated analysis/report data includes research/report packets, report
  payloads, report context snapshots, scanner outputs, backtest outputs,
  support bundles, exports, traces, and reproducibility manifests. Retention
  should separate durable summaries from bulky raw/generated artifacts.
- Ephemeral caches include guest/cache metadata, in-memory/runtime cache
  mirrors, import previews, frontend build output, and CI artifacts. These are
  not authoritative business records.

## 4. Artifact Class Matrix

| Artifact class | Current / likely surface | Tier | Proposed policy | Must not capture / must not do |
| --- | --- | --- | --- | --- |
| Application logs | `execution_log_sessions`, `execution_log_events`, runtime log files, Phase G execution/admin log families | R3, with security/admin events elevated to R0 | Routine operational logs 90-180 days; verbose debug detail 30-90 days; security/admin audit events 365 days minimum or operator/legal policy | No raw prompts, provider payloads, stack traces, cookies, sessions, tokens, raw request/response bodies, or secrets |
| Admin/operator evidence | `operator-evidence-local/sanitized`, launch evidence summaries, restore/PITR evidence, incident-response evidence, manual review records | R0 | Preserve accepted sanitized evidence and manifests per release/operator policy; draft/rejected packets stay private and follow operator retention | Tool output must not imply `releaseApproved=true`, public launch approval, or legal/compliance approval |
| Provider diagnostics | `provider_quota_windows`, `provider_circuit_states`, `provider_circuit_events`, `provider_probe_events`, provider usage ledger diagnostics | R3, aggregates R0/R2 where used for operator review | Raw events/probes 30-90 days; daily provider/route/reason aggregates 1 year; active circuit state is not a TTL cleanup candidate | No provider runtime/order/fallback/cache changes; no raw URLs, query strings, provider payloads, credentials, exception text, or stack traces |
| Quota/cost/accounting evidence | `llm_usage`, `llm_cost_ledger`, `quota_usage_windows`, `quota_reservations`, pricing policy snapshots, quota pilot evidence | R0 for accounting/aggregates, R3 for raw attempt diagnostics | Raw usage and reservation rows 90-180 days; owner/guest/route/model monthly aggregates 2+ years; preserve referenced pricing snapshots while rows reference them | Retention is not quota enforcement, invoice truth, live blocking approval, or public launch approval |
| Durable task/progress artifacts | `durable_task_states`, `durable_task_progress_events`, process-local `AnalysisTaskQueue` mirrors | R2 for terminal summary, R3 for verbose progress | Protect active/running/leased rows; terminal task summaries 30-90 days; failed/canceled summaries 90-180 days; completed progress events 7-14 days after summary; failed/debug progress around 30 days | No stale-task repair, scheduler activation, queue cutover, SSE semantics change, or deletion of active rows |
| Portfolio imports and import previews | `/api/v1/portfolio/imports/parse`, `/api/v1/portfolio/imports/commit`, `PortfolioImportParseResponse`, committed trades/cash/corporate actions/broker metadata | R4 for raw files/previews, R1 for committed accounting rows | Do not persist raw import files or previews by default; committed accounting rows are preserve-by-default; derived import audit summaries follow R0/R3 depending on content | Do not TTL portfolio trades, cash ledger, corporate actions, holdings, positions, lots, snapshots, FX, cost basis, or replay-critical records by default |
| Backtest outputs | legacy `backtest_*`, `rule_backtest_*`, PostgreSQL `backtest_runs`, `backtest_artifacts`, support bundles, execution traces, exports | R2 summaries, R3 bulky traces/exports | Keep run summaries and reproducibility metadata 1+ year; large execution traces, exports, support bundles, and generated artifact payloads 30-180 days by size/kind | Do not alter strategy math, fills, costs, metrics, stored-first readback, replay determinism, or provider behavior |
| Research/report packets | `analysis_history`, Phase B `analysis_sessions`/`analysis_records`, report payload/context snapshot/news content, report export packets, LLM report output cache if later approved | R2, raw context R3/R4 by sensitivity | User-visible report summaries 180-365 days; raw context/news/provider-derived packets 30-180 days; any future same-owner report cache requires separate product/privacy approval | No cross-user report reuse, no raw prompts/responses in evidence, no prompt/model/routing behavior change |
| Scanner/watchlist artifacts | `market_scanner_runs`, `market_scanner_candidates`, PostgreSQL scanner/watchlist tables, user watchlist items | R2 for user-visible runs, R3 for diagnostics, R1 for watchlists | User-visible runs/candidates 180-365 days; bulky diagnostics 30-90 days; watchlist items until user deletion/archive | Do not change scoring, ranking, selection, thresholds, provider fanout, or watchlist ownership semantics |
| Guest/cache metadata | `guest_sessions`, `auth_rate_limit_buckets`, conversation/session metadata, market snapshots, future cache mirrors | R4, abuse/security aggregates may be R0/R3 | 24 hours to 7 days for guest/cache metadata unless security/abuse aggregate is needed | Do not change MarketCache TTL/SWR/cold-start/fallback semantics or mix guest with authenticated user state |
| Frontend build and CI artifacts | `apps/dsa-web/dist`, CI build/test artifacts, screenshots, coverage, package manager caches | R4 unless a sanitized release evidence artifact is accepted | Keep local build output uncommitted; follow CI provider retention for build artifacts; accepted release evidence keeps manifest/checksum summaries rather than raw logs | Do not commit generated build output, dependency caches, raw CI logs with secrets, screenshots containing private data, or node_modules |

## 5. Preview-first Checker Contract

If a future checker or dry-run report is added, it must be deterministic,
offline/non-destructive by default, and emit review evidence with at least:

- `policyVersion`
- `dryRun=true`
- `deleteAllowed=false`
- `runtimeBehaviorChanged=false`
- `productionDataTouched=false`
- `networkCallsExecuted=false`
- `matchedRowCount`
- oldest/newest candidate timestamps when safe
- estimated bytes when safe
- owner/domain scope
- protected row reasons
- leaf-table parent-join requirements
- sanitized aggregate dimensions only

Checker output must never include raw user IDs, raw owner IDs, session IDs,
cookies, tokens, headers, request/response bodies, raw prompts, raw LLM
responses, raw provider payloads, raw provider URLs/query strings, stack
traces, exception text, DSNs, file paths containing private infrastructure, or
secrets.

The existing `scripts/db_retention_preview_report.py` is the current safe
reference pattern for report-only preview evidence. This task does not add a
new checker or test because the policy matrix is sufficient and runtime
deletion remains out of scope.

## 6. Future Acceptance Checklist

Before any non-admin-log retention implementation can move beyond policy:

- Product/operator owners approve the tier, cadence, size threshold, and
  source-of-truth exclusions for the domain.
- A preview report exists with `deleteAllowed=false` and no production data
  mutation.
- Leaf tables prove owner/domain parent joins before any cleanup candidate is
  counted.
- Financial/accounting source-of-truth records are excluded unless a separate
  user data deletion/export policy explicitly authorizes them.
- Backup/restore/PITR evidence proves cleanup is not being used as rollback.
- Sanitized operator evidence is reviewed manually; tool success alone does
  not approve launch.
- Separate rollback and stop rules exist for the specific implementation.

Stop immediately if the retention work requires a DB migration, runtime delete
job, scheduler/cron activation, production data access, cache TTL/runtime
semantic change, provider/quota/auth/RBAC/session/broker/notification/frontend
behavior change, or wording that can be read as legal/compliance/public-launch
approval.
