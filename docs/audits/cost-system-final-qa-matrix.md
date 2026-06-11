# Cost System Final QA Matrix

Date: 2026-05-07
Mode: docs-only final QA matrix. No runtime code, frontend, schema, or test behavior changed.

## Scope boundary

This matrix covers the completed cost-system surfaces only:

- Pricing policies and local import/upsert workflow.
- LLM cost ledger calculation, summaries, owner/guest attribution, and safe zero-cost handling.
- Quota dry-run, reservation lifecycle, and ledger-to-reservation reconciliation.
- Admin cost observability dashboard panels and capability gating.
- Security posture for ledger/admin cost data.

Out of scope for this QA pass: runtime code, frontend implementation, schema changes, tests, Options, Data Pipeline, provider circuit, auth, scanner/backtest/portfolio behavior, LLM prompts, model routing, fallback, retries, provider/cache ordering, quota live enforcement, and any external pricing scrape.

## Evidence map

| Surface | Primary evidence |
| --- | --- |
| Cost architecture and staged WS2 notes | `docs/audits/ws2-multi-user-runtime-cost-control-design.md` |
| Pricing policy import/upsert | `src/services/model_pricing_policy_import_service.py`, `tests/test_model_pricing_policy_import.py` |
| LLM cost calculation and ledger reconciliation | `src/services/llm_cost_ledger_service.py`, `tests/test_llm_cost_ledger.py` |
| Quota policy and reservation lifecycle | `src/services/quota_policy_service.py`, `tests/test_quota_policy_service.py` |
| Admin cost APIs | `api/v1/endpoints/admin_cost.py`, `tests/api/test_admin_quota_dry_run.py`, `tests/api/test_admin_cost_summary.py` |
| Admin cost UI | `apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx`, `apps/dsa-web/src/pages/__tests__/AdminCostObservabilityPage.test.tsx` |

## 1. Pricing Policy Matrix

| QA item | Expected behavior | Current status | Evidence / notes |
| --- | --- | --- | --- |
| Import/upsert | Local JSON records are validated and upserted by stable `policy_key` or provider/model/effective date. Matching records are skipped; changed records update. | Covered | `ModelPricingPolicyImportService.import_records(...)` normalizes, finds existing records, and upserts through `DatabaseManager.upsert_model_pricing_policy(...)`. |
| Effective dates | Cost lookup selects active policy by provider/model and `effective_from` / `effective_until` at calculation time. Historical policy ranges can coexist. | Covered | `LlmCostLedgerService.lookup_pricing_policy(...)` delegates to effective-date storage lookup; importer preserves effective ranges unless superseded deactivation is explicitly requested. |
| Inactive policies | Inactive effective policy does not price a call as `ok`; inactive lookup returns `pricing_inactive`. | Covered | Ledger service checks inactive policy via `include_inactive=True` and returns `pricing_inactive`. |
| Unknown pricing | Missing provider/model pricing produces a safe `pricing_unknown` result. | Covered | `calculate_cost(...)` returns `_zero_result("pricing_unknown", ...)` when no effective active policy exists. |
| No runtime scraping | Pricing policy maintenance is local/import-based only. Runtime does not fetch or scrape provider pricing pages. | Covered | Import service reads local JSON and explicitly performs no HTTP request; admin pricing API metadata marks `noExternalCalls: True` and `manualMaintenance: True`. |
| Invalid prices | Negative or invalid price values are rejected with safe reason codes. | Covered | Import service rejects `negative_price`, `invalid_price`, missing provider/model/date, invalid effective dates, and invalid source URLs. |
| Cached input price optionality | If cached-input price is absent, all prompt tokens are priced as regular input tokens. | Covered | `calculate_cost(...)` treats missing `cached_input_price_per_1m` as no cached discount. |

## 2. Ledger Matrix

| QA item | Expected behavior | Current status | Evidence / notes |
| --- | --- | --- | --- |
| Prompt/completion/cached tokens | Ledger rows preserve prompt, cached-input, cache-miss, completion, and total token dimensions. | Covered | `reconcile_usage(...)` records `prompt_tokens`, `cached_input_tokens`, `cache_miss_input_tokens`, `completion_tokens`, and `total_tokens`. |
| Cost calculation | Estimated USD cost is Decimal-safe and split into input, cached input, output, and total costs. | Covered | `calculate_cost(...)` computes per-1M token costs with quantized Decimal math. |
| `pricing_unknown` zero-cost behavior | Unknown pricing records a ledger row with zero estimated cost and safe status rather than blocking the call. | Covered | `_zero_result(...)` sets input/cached/output/total cost to `0` for `pricing_unknown`; WS2 notes state missing pricing is observational and non-blocking. |
| `pricing_inactive` behavior | Inactive pricing policy yields zero estimated cost and a safe status. | Covered | Inactive lookup returns `pricing_inactive`, which is included in safe result codes. |
| Invalid usage behavior | Negative token values or cached tokens greater than prompt tokens return `invalid_usage` and zero cost. | Covered | `calculate_cost(...)` validates token counts before pricing. |
| Per-user summaries | Admin ledger summary returns per-user aggregate rows. Null owners are grouped as `guest_or_unknown`. | Covered | `get_llm_cost_ledger_summary(...)` rolls up by user; admin API maps missing owner to `guest_or_unknown`. |
| Provider/model summaries | Admin ledger summary returns provider/model rollups. | Covered | Admin API returns `byProviderModel` rows with provider and model dimensions. |
| Route summaries | Admin ledger summary returns route-family rollups. | Covered | Admin API returns `byRouteFamily` rows with route family dimensions. |
| Pricing snapshot | Ledger row stores the pricing policy key and sanitized pricing snapshot used for the estimate. | Covered | `reconcile_usage(...)` stores `pricing_policy_key` and `pricing_snapshot`. |
| Best-effort observer | Ledger write failure cannot change user-visible LLM success behavior. | Covered by design | WS2-R4C notes define ledger observer as best-effort after legacy `llm_usage` persistence. |

## 3. Owner Context Matrix

| QA item | Expected behavior | Current status | Evidence / notes |
| --- | --- | --- | --- |
| Authenticated analysis | Authenticated sync analysis passes `owner_user_id` into LLM usage/ledger seams. | Covered | WS2-R4D note lists authenticated sync analysis; route and pipeline call sites pass owner context. |
| Async task | Async analysis task execution passes the task owner into usage/ledger seams. | Covered | Task queue and pipeline call sites pass task owner/user context into LLM usage persistence. |
| Agent analysis | Agent analysis mode propagates owner context into LLM usage persistence. | Covered | Agent runner/executor call sites pass `owner_user_id` and optional guest bucket. |
| Agent chat/stream | Authenticated agent chat/stream execution propagates owner context. | Covered | WS2-R4D note lists authenticated agent chat/stream; executor usage calls accept owner/guest dimensions. |
| Scanner AI interpretation | Scanner AI interpretation writes ledger context with owner/guest dimensions. | Covered | `ScannerAiInterpretationService` accepts `owner_user_id` / `guest_bucket_hash` and passes them to `persist_llm_usage(...)`. |
| Guest preview hash | Guest preview uses a hashed guest bucket, not a raw guest session id. | Covered | WS2-R4D note states guest preview passes only a hash derived from the guest cookie. |
| Remaining null-owner system paths | Legacy/system paths that call `persist_llm_usage(...)` without owner context continue to write null-owner rows for compatibility. | Open, accepted compatibility gap | Known paths are CLI/scheduled/system analysis and free-form analyzer text generation outside authenticated route context. These must stay visible in admin summaries as `guest_or_unknown` until separately remediated. |

## 4. Quota Matrix

| QA item | Expected behavior | Current status | Evidence / notes |
| --- | --- | --- | --- |
| Dry-run endpoint | Admin can evaluate quota policy through a diagnostic endpoint without live route enforcement. | Covered | `POST /api/v1/admin/cost/quota-dry-run` returns `diagnosticOnly: True`, `liveEnforcement: False`, and `noExternalCalls: True`. |
| Route classification | Route family is normalized to known quota weights with a safe fallback. | Covered | `QuotaPolicyService.classify_route_family(...)` maps unknown route families to `analysis`. |
| Estimate | `estimate` evaluates budget units and would-block state without creating a reservation. | Covered | Admin endpoint calls `evaluate_quota(...)` for `operation == "estimate"`. |
| Reserve | `reserve` creates a synthetic reservation and updates daily/monthly reserved windows when enforcement mode is not disabled. | Covered | `reserve_quota(...)` writes `quota_reservations` and updates owner plus route windows. |
| Consume | `consume` moves reserved units into consumed units and marks the reservation consumed. | Covered | `consume_reservation(...)` calls `_move_reserved_units(...)` and marks status `consumed`. |
| Release | `release` subtracts reserved units and marks the reservation released without consumed burn. | Covered | `release_reservation(...)` calls `_move_reserved_units(..., consumed_units=0)` and marks status `released`. |
| Expired/missing reservation | Missing, expired, or terminal reservations return safe reason/result codes. | Covered | Quota and reconciliation helpers return safe codes such as `reservation_expired`, `reservation_missing`, and `reservation_already_terminal`. |
| Ledger reconciliation | Successful priced ledger calls consume reservations; `pricing_unknown`, `pricing_inactive`, and `invalid_usage` release instead of consume. | Covered | `QuotaReservationReconciliationHelper.reconcile(...)` consumes only `status == "ok"` and releases zero-cost/no-consume statuses. |
| No live enforcement | Existing product routes are not blocked by quota. | Covered | Quota service defaults to `enforcement_enabled=False`; WS2 notes state no live LLM/provider route enforcement. |

## 5. Admin UI Matrix

| QA item | Expected behavior | Current status | Evidence / notes |
| --- | --- | --- | --- |
| Ledger summary panel | Dashboard shows window, total tokens, estimated cost, request count, prompt/cached/completion tokens, pricing unknown/inactive badges, and user/provider/route rollups. | Covered | `LlmLedgerPanel` renders `data-testid="llm-ledger-panel"` with the listed aggregates. |
| Quota dry-run panel | Dashboard allows route family, token estimate, enforcement mode, operation, and reservation id inputs for diagnostic quota operations. | Covered | `QuotaDryRunPanel` renders `data-testid="quota-dry-run-panel"` and calls `adminCostApi.runQuotaDryRun(...)`. |
| Pricing policy panel | Dashboard lists active count, policy status, effective range, per-1M input/cached/output prices, currency, and source label/link. | Covered | `PricingPolicyPanel` renders `data-testid="model-pricing-policy-panel"`. |
| Capability gating | Cost panels are hidden unless current user has `canReadCostObservability` / `cost:observability:read`. | Covered | UI panels return `null` without the capability; admin APIs use `require_admin_capability("cost:observability:read")`. |
| Read-only posture | Dashboard copy and response metadata identify read-only, no external calls, and non-billing estimates. | Covered | Admin cost API metadata and UI badges mark read-only/no-external-call behavior. |

## 6. Security Matrix

| QA item | Expected behavior | Current status | Evidence / notes |
| --- | --- | --- | --- |
| No raw prompts | Ledger and admin UI do not expose raw prompt content. | Covered | Ledger metadata is sanitized; admin metadata redaction lists omit prompts. |
| No raw provider payloads | Ledger and UI do not store or show raw provider responses/payloads. | Covered | Cost endpoint metadata redaction lists provider payload omission; WS2 notes state observer uses normalized usage fields only. |
| No secrets | Credentials, cookies, session ids, provider secrets, and stack details are not stored or returned. | Covered | Import/ledger/quota metadata sanitizers and admin endpoint redaction lists exclude secret-like fields. |
| Guest privacy | Guest preview uses hashed guest bucket labels and does not write raw guest session ids. | Covered | WS2-R4D owner context note. |
| Sanitized metadata | Quota and ledger metadata are bounded and sanitized before storage or response. | Covered | `DatabaseManager._sanitize_llm_cost_metadata(...)` and `_sanitize_quota_metadata(...)` are used by ledger/quota services. |
| Read-only admin APIs | Admin cost reads do not trigger provider/LLM calls, refreshes, scraping, or product tasks. | Covered | Admin cost metadata includes `noExternalCalls: True`; pricing list is read-only from `model_pricing_policies`. |

## 7. Open Gaps / Blockers

These are not blockers for the current docs-only QA matrix, but they are blockers for calling the cost system production-enforcing or billing-authoritative:

| Gap | Blocker status | Required next step |
| --- | --- | --- |
| Live enforcement pilot | Partial | A default-off, owner-allowlisted sync single-stock analysis pilot can reserve before route execution, block only that route on quota rejection, consume estimated route units after success, and release on analysis failure. Public launch and global spend-cap readiness still require accepted staging/operator evidence, admin visibility, owner/guest accounting acceptance, and invoice reconciliation. |
| Provider invoice reconciliation | Open | Compare ledger estimates against provider invoices/exported usage and document tolerances, currency handling, and mismatch workflow. |
| Pricing update governance | Open | Define reviewed price-update cadence, source verification evidence, owner, and stale-policy alerts. |
| Budget alerting | Open | Add warning thresholds and admin/user-facing alerts before monthly/daily exhaustion. |
| Admin edit UI | Open | Add a gated editor for pricing policies and quota policies with audit logs, validation, rollback, and no raw secret exposure. |
| Null-owner cleanup | Open | Migrate CLI/scheduled/system/free-form analyzer paths to explicit system owner labels or documented service accounts. |

## Validation Plan For This Docs-Only QA Pass

Required validation:

```bash
git diff -- docs/audits/cost-system-final-qa-matrix.md docs/CHANGELOG.md
git diff --check -- docs/audits/cost-system-final-qa-matrix.md docs/CHANGELOG.md
```

No `ci_gate` is required because this pass changes documentation only.

`docs/CHANGELOG.md` was already dirty before this task, so this pass intentionally does not modify it.
