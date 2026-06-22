# Cost Observability Design Index

Date: 2026-05-06
Mode: docs-only index. No runtime behavior changed.

## 1. Purpose

This document is a navigation index for the cost-observability design set. It maps completed and pending design notes to their purpose, status, dependencies, and next implementation task so future work can stay sequenced, measurable, and narrow.

It is not a new design and does not implement counters, APIs, caches, runtime behavior, UI, tests, dashboards, provider calls, or LLM calls.

## 2. Design set status

| Document | Status | Purpose | Key constraints | Depends on | Enables |
| --- | --- | --- | --- | --- | --- |
| `docs/audits/llm-external-api-cost-audit.md` | completed, `601d770c` | Static audit of repeated LLM and external-provider cost risks. | Docs-only; no runtime, cache, provider, DuckDB, UI, test, or traffic changes. | Current codebase inspection. | Duplicate-cost metrics design and instrumentation-first sequencing. |
| `docs/audits/llm-provider-duplicate-cost-metrics-design.md` | completed, `a6ab3fa0` | Implementation-ready metric/event model for LLM, provider, MarketCache, and scanner AI duplicate-cost measurement. | Instrumentation-only first; bounded labels; safe hashes; no raw prompts, payloads, images, news, users, URLs, or secrets. | Cost audit. | LLM instrumentation Phase 1A and later provider/cache/scanner counters. |
| `docs/audits/guest-preview-reuse-design.md` | completed, `0a73b264` | Privacy-safe short-TTL guest preview reuse concept. | Future prototype only after metrics; guest-session scoped; no `force_refresh` reuse; no cross-user/session reuse. | Cost audit and metrics design. | Guest preview reuse prototype after measured repeat rate. |
| `docs/audits/duplicate-cost-admin-summary-api-design.md` | completed, `27ae2cf8` | Future admin-only read-only duplicate-cost summary API design. | No provider/LLM calls; no cache mutation; admin-only; aggregate-first; redacted. | Cost audit and metrics design; useful counters should exist first. | Backend duplicate-cost summary and later admin frontend dashboard. |
| `docs/audits/scanner-ai-interpretation-cache-design.md` | completed, `24b606d9` | Future optional cache for additive Scanner AI interpretation text. | Must not affect scanner rank, score, selection, thresholds, CSV headers, or actionability. | Metrics design and scanner AI duplicate-candidate evidence. | Scanner AI interpretation cache prototype after metrics. |
| `docs/audits/ws2-provider-quota-circuit-breaker-policy-design.md` | deferred/current, `410c5cef` | Provider quota/circuit policy design plus retained fallback-depth, quota-risk, and degraded-mode measurement constraints. | Policy/design only; no provider order, fallback, timeout, retry, circuit enforcement, MarketCache, scanner, backtest, portfolio, AI, notification, or DuckDB changes. | Cost audit, metrics design, current provider posture. | Provider fallback counters Phase 1B and later read-only provider reporting. |
| `docs/archive/audits/frontend/wolfystock-post-batch-integration-qa.md` | completed, `f4c5827d` | QA/reporting context confirming recent work and cost-observability sequencing. | QA/report only; no behavior changes intended. | Recent main-branch dashboard, staging, localization, and docs commits. | Confirms instrumentation-first, read-only summary second, cache prototypes after measurement. |
| `docs/audits/market-overview-cache-reporting-design.md` | pending parallel task; not present in this repo state | Expected future design for MarketCache hit/stale/miss and panel reporting. | Should not change MarketCache TTL, SWR, background refresh, cold-start timeout, fallback factories, snapshots, or provider behavior. | Metrics design; current MarketCache behavior. | MarketCache counters Phase 1C and read-only MarketCache reporting. |
| `docs/audits/llm-report-output-cache-design.md` | completed, `5796e66f` | Future LLM report output cache eligibility, keys, freshness, disclosure, and rollout design. | No report cache before metrics; no prompt, LLM routing, AI decision, provider behavior, report semantics, integrity retry, parser, API, UI, test, dependency, notification, DuckDB, backtest, or portfolio behavior changes. | Cost audit, metrics design, guest preview reuse design, scanner AI cache design. | LLM report output cache prototype after measured duplicate report evidence. |
| `docs/audits/cost-observability-implementation-roadmap.md` | completed locally, `aeb30a75` | Roadmap sequencing implementation phases across counters, reports, dashboard, and prototypes. | Preserve instrumentation-first; serialize shared helper/seam work; avoid bundling runtime policy changes with reporting. | Completed design notes. | Cross-task implementation sequencing and parallelization plan. |

## 3. Dependency graph

- Cost audit -> duplicate-cost metrics design -> instrumentation counters.
- Metrics design -> duplicate-cost admin summary API design.
- Metrics design -> provider fallback/quota measurement work, MarketCache reporting, scanner AI cache design, guest preview reuse, report output cache design, and implementation roadmap.
- Admin summary design -> backend API after enough counters exist.
- Cache designs -> disabled-by-default prototypes only after measured evidence.
- WS2 provider quota/circuit policy design -> provider fallback counters first, then read-only report integration.
- Scanner AI interpretation cache -> duplicate candidate counter first, then read-only evidence, then disabled-by-default cache prototype.

## 4. Implementation readiness

| Implementation task | Ready now? | Required preceding docs/tasks | Must serialize with | Can parallelize with | Risk level | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| LLM instrumentation Phase 1A | yes | Cost audit; metrics design | Shared metrics helper shape; any concurrent edits to LLM seams | Docs-only index/roadmap work | medium | Instrument LLM seams only; preserve prompts, routing, fallback order, integrity retry behavior, and usage persistence semantics. |
| Provider fallback counters Phase 1B | partial | Metrics design; WS2 provider quota/circuit policy design; stable helper from Phase 1A if reused | Phase 1A helper/interface decisions and concurrent provider instrumentation edits | MarketCache/scanner counter planning once helper shape is stable | medium/high | Observe provider attempts, fallback depth, quota-risk buckets, cache hits/misses, and inflight joins without changing provider behavior. |
| MarketCache counters Phase 1C | partial | Metrics design; pending Market Overview cache reporting design if available | Concurrent edits to `MarketCache` or Market Overview cache/fetch seams | Provider/scanner counter work if helper is stable and files do not overlap | medium | Count hit/stale/miss/refresh/fallback; do not change TTL, SWR, background refresh, cold-start, fallback factories, or snapshots. |
| Scanner AI duplicate candidate counter Phase 1D | yes, narrow | Metrics design; scanner AI interpretation cache design | Concurrent scanner AI service edits | Provider/MarketCache counters if helper is stable and target files differ | medium | Counter only; AI remains additive and cannot affect ranking, scoring, selection, thresholds, CSV, or actions. |
| Duplicate-cost admin summary backend | not yet | Enough Phase 1 counters; admin summary API design; privacy review of labels | Counter schema stabilization | Docs work and frontend planning | medium/high | Backend-only, admin-only, read-only; no providers, LLMs, cache refresh, config mutation, or log writes. |
| Admin frontend dashboard | not yet | Stable backend summary API contract | Backend API implementation and response naming | Docs/design review | medium | UI only after backend contract stabilizes; values must be framed as operational measurement, not billing truth. |
| Guest preview reuse prototype | not yet | Duplicate guest preview evidence; guest preview reuse design; summary/report visibility | LLM/report cache decisions and API disclosure design | Scanner AI cache prototype only if files/contracts do not overlap | high | Disabled-by-default; short TTL; guest-session scoped; freshness disclosed; bypass on `force_refresh`. |
| Scanner AI interpretation cache prototype | not yet | Scanner duplicate candidate counter; repeat-cost report evidence; scanner AI cache design | Scanner AI counter and scanner API disclosure decisions | Guest/report cache prototypes only after evidence and disjoint files | high | Cache only additive interpretation text; never ranking, score, selection, thresholds, CSV, or actionability. |
| LLM report output cache prototype | not yet | Completed report output cache design; measured duplicate report evidence; freshness/key review | Guest preview reuse and LLM prompt/routing/report schema decisions | Scanner cache prototype if independent | high | Do not prototype until key, freshness, force-refresh, prompt/model/source snapshot, and disclosure rules are approved. |

## 5. Global guardrails

- Instrumentation first.
- Read-only reports second.
- Cache prototypes only after measured evidence.
- No raw prompts, messages, images, news, provider payloads, user/session ids, URLs, stack traces, tokens, credentials, or secret values in metrics, logs, reports, or labels.
- Use bounded labels and safe hashes.
- Do not change provider ordering or fallback behavior.
- Do not change `MarketCache` TTL, stale-while-revalidate, background refresh, cold-start timeout, fallback factories, or persistent snapshot behavior.
- Do not change scanner ranking, score, selection, thresholds, candidate actionability, profile behavior, or CSV headers.
- Do not change backtest calculations or portfolio accounting.
- Do not change AI decision logic, prompt logic, LLM routing, model ordering, or report integrity policy.
- Do not change notification routing or DuckDB runtime.
- Do not call real LLM APIs, external providers, or manual connectivity probes for reporting or verification.

## 6. Recommended rolling parallel workflow

1. Keep docs-only tasks parallel when target docs differ. Do not edit dirty docs owned by another session; mark absent or dirty referenced docs as pending.
2. Run Phase 1A LLM instrumentation separately from provider and MarketCache instrumentation until the metrics helper shape is stable.
3. After Phase 1A lands, parallelize Phase 1B, Phase 1C, and Phase 1D only if the helper is stable and target files do not conflict.
4. Implement the backend duplicate-cost summary only after enough counters exist to avoid speculative duplicate-rate claims.
5. Add the admin frontend dashboard only after the backend response contract is stable.
6. Prototype guest preview reuse, scanner AI interpretation cache, or LLM report output cache only after observed hit rate justifies the behavior and disclosure is designed.

## 7. Next Codex prompts to prepare

1. Instrumentation-only backend counters Phase 1A — LLM seams only
2. Instrumentation-only provider fallback counters Phase 1B
3. Instrumentation-only MarketCache hit/stale/miss counters Phase 1C
4. Scanner AI duplicate candidate counter Phase 1D
5. Backend-only duplicate-cost summary API with synthetic tests
