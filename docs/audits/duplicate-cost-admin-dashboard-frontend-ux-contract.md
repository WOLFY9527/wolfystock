# Duplicate-Cost Admin Dashboard Frontend UX Contract

Date: 2026-05-06
Mode: docs-only frontend UX contract. No runtime behavior changed.

## 1. Purpose

Define the future frontend UX for an admin-only duplicate-cost and cost-observability dashboard after counters and the summary API stabilize.

This contract prepares a later frontend implementation. It does not implement a route, page, API client, chart, table, style, i18n string, test, backend endpoint, metric counter, cache behavior, provider behavior, LLM behavior, or billing calculation.

## 2. Inputs and dependencies

| Dependency | Source design | Status for frontend planning | Notes |
| --- | --- | --- | --- |
| Phase 1A LLM counters | `docs/audits/llm-provider-duplicate-cost-metrics-design.md`, `docs/audits/cost-observability-implementation-roadmap.md` | Committed design; backend instrumentation may be present or in progress | LLM calls, fallbacks, integrity retries, usage persistence. |
| Phase 1B provider counters | Same cost-observability docs | Committed design; backend instrumentation may be present or in progress | Provider attempts, fallbacks, cache hit/miss, inflight join, quota-risk. |
| Phase 1C MarketCache counters | Same cost-observability docs | Committed design; backend instrumentation may be present or in progress | MarketCache hit, stale, miss, refresh, failure, cold fallback. |
| Phase 1D scanner AI counters | `docs/audits/scanner-ai-interpretation-cache-design.md`, roadmap | In progress or pending backend stabilization | Scanner AI started/completed/skipped and duplicate candidates. |
| `GET /api/v1/admin/cost/duplicate-summary` | `docs/audits/duplicate-cost-admin-summary-api-design.md` | Designed; not a stable frontend dependency yet | Read-only aggregate summary; no external calls. |
| Duplicate-cost admin summary API design | `docs/audits/duplicate-cost-admin-summary-api-design.md` | Frontend source of truth once implemented | Must expose `metadata.dataSources`, limitations, redaction, readOnly, and noExternalCalls. |
| Existing admin patterns | `AdminLogsPage.tsx`, `MarketProviderOperationsPage.tsx` | Static reference only | Read-only admin surface, sanitized links, limitations panel, Reflect-Linear density. |

The dirty working tree included cost-observability backend/test files during this docs pass. Those files were not edited.

## 3. Proposed route

Candidate route:

- `/zh/admin/cost-observability`

Alternative route:

- `/zh/admin/duplicate-cost`

Recommendation: use `/zh/admin/cost-observability` if the navigation label is broader than duplicate candidates and includes LLM, provider, MarketCache, scanner AI, limitations, and data quality. Use `/zh/admin/duplicate-cost` only if the backend contract stays narrowly scoped to duplicate-candidate reporting.

Final route and navigation naming should align with backend endpoint naming, admin IA, and existing `/zh/admin/logs` and `/zh/admin/market-providers` surfaces in a later implementation pass.

## 4. Dashboard layout

The future route should be a dense operator dashboard with aggregate-first sections:

- 总览: generatedAt, window, read-only/noExternalCalls badges, duplicate candidate count, overall limitations.
- LLM 调用: call attempts, successful reports, fallback depth, integrity retry rate, usage persistence.
- Provider / 数据源 fallback: provider attempts, fallback attempts, insufficient payload, timeout, quota-risk, provider cache efficiency.
- MarketCache 命中/过期/缺失: fresh hits, stale served, misses, refresh started/completed/failed, cold fallback.
- Scanner AI 解释: interpretation started/completed/skipped, duplicate candidate observed, skip reasons.
- Guest Preview / Report duplicate candidates: guest preview repeat candidates, report duplicate candidates, freshness and source snapshot grouping.
- 限制与数据质量: partial counters, stale/in-process state, missing areas, estimate-not-billing copy.
- Developer details collapsed: sanitized `dataSources`, label model, safe hashes, exactness, and raw debug limitations only.

No section should present raw logs, raw database rows, raw prompts, raw provider payloads, raw URLs, or exact billing claims.

## 5. Data widgets

| Widget | Required API fields | Display format | Empty / error / loading state | Warning state | Privacy rule |
| --- | --- | --- | --- | --- | --- |
| Duplicate candidate count | `summary.estimatedDuplicateCandidates`, `llm.duplicateCandidates`, provider/scanner candidates | Metric tile plus trend table | `--` while loading; `暂无重复候选` when zero; sanitized API error | Partial estimate if counters missing | Use safe hashes only; no raw symbol/user/session/prompt. |
| LLM attempts per successful report | `llm.byCallType.calls`, success counts, report counts | Ratio such as `2.3x / 成功报告` | Empty if no LLM data | High multiplier warning | Bucket by callType/modelFamily only. |
| Fallback attempts | `summary.fallbackAttempts`, `llm.fallbacks`, provider fallback depth | Compact metric plus fallback-depth table | Empty fallback table | Warning when fallback depth spikes | No raw configured model list or provider URL. |
| Integrity retry rate | `summary.integrityRetries`, `llm.integrityRetries` | Percent and retry-reason buckets | `完整性重试计数不可用` | Warning when high | No raw retry prompt or failed model output. |
| Usage persisted count | `llm.byCallType`, `metadata.dataSources` | Count by call type/token bucket | Empty if `llm_usage` unavailable | Mismatch warning versus attempts | Token values bucketed. |
| Provider fallback depth | `providers.fallbackDepth` | Table by provider category/market/depth | Empty if provider counters absent | Depth above baseline | Bounded provider/category labels only. |
| Provider quota-risk events | `provider_quota_risk_observed` rollup | Warning tile and reason bucket list | Empty state if no quota-risk | Amber/red warning | No provider response bodies or credential values. |
| Provider cache hit/miss/inflight join | `providers.cacheEfficiency` | Hit-rate tile and compact table | Empty if counters absent | Low hit rate or high miss rate | Hash cache identity; no raw cache keys/params. |
| MarketCache hit/stale/miss/refresh/cold fallback | `marketCache.byPanelKey`, `staleServed`, `coldFallbacks` | Section metrics by panel key | Empty if MarketCache counters absent | Stale/cold fallback warning | No snapshot payloads or raw cache keys. |
| Scanner AI interpretation started/completed/skipped | `scannerAi.interpretations`, `scannerAi.skips` | Table by market/profile/topN/skip reason | Empty if scanner AI disabled or counters absent | Unexpected high attempted/completed | No raw candidate reasons or generated text. |
| Scanner duplicate candidate observed | `scannerAi.duplicateCandidates` | Count and safe candidate-hash table | Empty if no candidates | Warning if repeated | Candidate hashes only; no raw symbol/reasons/watch context. |

## 6. Filters

Allowed filters:

- Time window: `15m`, `1h`, `24h`, `7d`, or bounded custom `from` / `to`.
- Bucket: `hour` or `day`.
- Area: `all`, `llm`, `provider`, `market-cache`, `scanner-ai`.
- Route family: bounded endpoint/report families.
- Provider category: bounded categories such as fundamentals, quote, news, market overview.
- Model family: redacted model family or alias only.
- Market: normalized market label.
- Freshness bucket: fresh, stale, cold, unknown.
- Outcome: success, failed, partial, skipped, timeout, unknown.
- Limit: strict default and maximum from backend.

Rejected filters:

- Raw prompt search.
- Raw message/conversation/tool-argument search.
- Raw user id, full session id, guest cookie, token, or owner id search.
- Raw URL/query/provider payload search.
- API key, Authorization header, webhook URL, or secret config search.
- Arbitrary SQL-like filters.
- Unbounded windows.
- Filters that imply live provider probes, LLM calls, cache refreshes, report generation, scanner execution, or runtime mutation.

## 7. Privacy display policy

The dashboard must forbid display of:

- raw prompt
- raw messages
- raw image data
- raw uploaded file data
- raw news/provider payload
- raw URL/query
- API keys/tokens
- full user/session ids
- guest cookie values
- raw stack traces
- raw response bodies
- raw provider error payloads
- raw cache keys or snapshot payloads
- exact secret config/env values

Allowed display:

- bounded labels
- safe hashes with purpose labels
- aggregate counts
- bucketed duration/token values
- redacted model/provider labels
- limitation flags
- data-source status and exactness
- sanitized Admin Logs links when the backend provides them
- read-only/noExternalCalls metadata

## 8. Visual design contract

The future dashboard must follow WolfyStock admin visual rules:

- Reflect-Linear route background from `docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md`.
- Ghost-glass metric cards with thin white borders and low-noise status glow.
- Dense admin tables with compact labels, fixed action/link columns, and no default-looking table chrome.
- Compact segmented filters using existing project primitives, not default browser controls.
- Collapsed debug/developer details by default.
- No loud generic charts, rainbow analytics colors, or marketing dashboard composition.
- No solid gray blocks and no native-looking selects/inputs.
- No visible raw/debug/provider-schema text outside collapsed sanitized details.
- Chinese UI labels by default, with accepted domain abbreviations such as LLM, Provider, MarketCache, Scanner AI.

## 9. States and limitations

Required states:

- No counters yet: show read-only shell with `计数器尚未接入` and hide ratios that would imply precision.
- Partial counters: show area-level availability, partial estimate badges, and source coverage.
- Stale data: show generatedAt/window age and stale warning.
- Summary API unavailable: sanitized error with no stack trace and no retry that calls providers.
- CI/dev-only unavailable: explain that the route needs the admin summary API and mocked tests only.
- Unsupported area: disabled filter option or empty section with dependency copy.
- Privacy redaction active: visible badge and limitations row.

Limitations panel copy must state:

- Counters are observational.
- Values are not exact billing.
- In-process counters may reset.
- Provider metrics may be approximate.
- Historical logs may be incomplete.
- High-volume success events may be intentionally absent from Admin Logs.
- No causal claims without trace/session correlation.
- Duplicate candidates suggest repeat patterns; they do not prove avoidable waste by themselves.

## 10. Implementation sequence

Phase C1: backend API contract stabilizes

- Dependency: `GET /api/v1/admin/cost/duplicate-summary` implemented with synthetic tests and privacy review.
- Frontend action: no UI route yet; update contract only if response shape changes.

Phase C2: frontend read-only dashboard shell

- Likely files touched later: `apps/dsa-web/src/App.tsx`, future admin cost page, future API client, i18n entries, navigation entry, route tests.
- Requirements: admin route gate, read-only/noExternalCalls badges, summary cards, limitations panel, loading/empty/error states.

Phase C3: charts/tables by area

- Add LLM, provider, MarketCache, scanner AI sections using mocked API fixtures only.
- Keep charts subdued and operator-grade; tables remain aggregate-first.
- Add no live calls and no cache/provider/LLM controls.

Phase C4: link to Admin Logs / Provider Operations

- Add sanitized drill-through links only when API returns safe routes/ids.
- Link to existing `/zh/admin/logs` and `/zh/admin/market-providers` patterns without exposing raw query/payload fields.

Phase C5: alerting only after measured baseline

- No alerting UI until repeated baseline windows prove stable thresholds.
- Any alert/notification proposal must be a separate design and cannot change provider/LLM/cache behavior.

## 11. Testing and verification plan

Future implementation must include:

- Admin route gating and guest/non-admin forbidden states.
- Chinese labels on `/zh` route.
- No secret text in DOM for prompt/message/image/news/provider payload/URL/API key/token/session/stack/response patterns.
- Filter behavior with mocked API only.
- Loading, empty, no-counters, partial-counters, stale-data, API-unavailable, unsupported-area, and error states.
- Collapsed developer details by default.
- Desktop and mobile viewports with no horizontal overflow.
- Read-only and noExternalCalls badges visible.
- Links use sanitized Admin Logs/Provider Operations route data only.
- No real provider calls, no real LLM calls, no browser calls to live APIs, no cache mutation, no config writes.

## 12. Non-goals

- No implementation now.
- No billing claims.
- No cache/reuse control toggles.
- No provider policy changes.
- No raw logs or payload dumps.
- No frontend route before the backend summary contract is stable.
- No changes to LLM routing, prompt logic, retry behavior, provider ordering, fallback behavior, MarketCache TTL/SWR/cold-start behavior, scanner ranking/selection, backtest, portfolio, notification, or DuckDB runtime.
- No dev server, browser verification, live API calls, CI, build, lint, tests, dependencies, CSS, API clients, i18n, routes, or React pages in this docs-only task.
