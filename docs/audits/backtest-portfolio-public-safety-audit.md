# Backtest and Portfolio Public Safety Audit

Date: 2026-05-07
Branch checked: `main`
Mode: docs-only public-safety audit. No runtime code, tests, schemas,
frontend, Options, Data Pipeline, provider, cost/quota, auth/RBAC, backtest
calculation, or portfolio accounting behavior was changed.

## 1. Executive summary

Public exposure verdict for Backtest and Portfolio: **NO-GO** until the
pre-public tests in this document pass and the remaining safety blockers are
accepted.

The current codebase has useful foundations: backtest read paths expose
stored-first authority, artifact availability, readback integrity, execution
trace exports, and explicit data-source diagnostics; portfolio flows have
owner-scoped API contracts, populated-holdings QA, FX transparency, broker sync
boundaries, and portfolio write audit event patterns.

Those foundations are not enough by themselves for broad public multi-user
exposure. Backtest and Portfolio are financial safety domains. Before launch,
the project needs deterministic regression evidence, owner-isolation proof,
cache/export isolation checks, accounting invariant tests, and explicit
credential/import/replay mutation boundaries.

## 2. Scope boundary

This audit covers only public-safety readiness for:

- Backtest calculations, result disclosure, stored artifacts, and exports.
- Portfolio ownership, cash/holdings/P&L accounting, imports, broker
  credential isolation, and auditability.
- Multi-user leakage risks shared by Backtest and Portfolio.
- Required test plan before broader public exposure.

Out of scope for this audit:

- No calculation changes.
- No portfolio behavior changes.
- No runtime code, tests, schemas, frontend, provider, Options, Data Pipeline,
  cost/quota, auth/RBAC, broker execution, or order-placement changes.
- No public launch approval.

## 3. Evidence map

| Surface | Existing evidence inspected |
| --- | --- |
| Deployment readiness | `docs/audits/deployment-readiness-checklist.md` |
| Backtest service contract | `docs/backtest-system.md` |
| Backtest rendered-route audit | `docs/archive/audits/frontend/wolfystock-backtest-dom-verification.md` |
| Portfolio populated holdings QA | `docs/archive/qa/wolfystock-portfolio-populated-holdings-qa.md` |
| Standard task guard | `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md` |

## 4. Backtest safety review

| Risk area | Current posture | Public-safety blocker | Required evidence before public exposure |
| --- | --- | --- | --- |
| Calculation determinism | Rule backtest has deterministic smoke surfaces and stored-first readback diagnostics. | Determinism must be proven across repeated runs, restart/reopen, export, and comparison reads using fixed fixtures. | Golden fixtures for standard and rule backtests with stable metrics, trades, equity curve, benchmark summary, execution model, and trace exports. |
| Lookahead bias | Documentation states execution assumptions and stored `execution_model` are exposed on readback. | The public contract must prove signals use only data available before the simulated trade decision. | Fixture tests with known signal dates, next-bar execution checks, and explicit failures for same-bar future data leakage. |
| Fee/slippage assumptions | Rule run request supports `fee_bps` and `slippage_bps`; result details expose execution assumptions. | Public users must see whether reported returns include zero, default, or user-supplied fee/slippage assumptions. | Regression fixtures covering zero fee, non-zero fee, non-zero slippage, and display/API disclosure of the assumptions used. |
| Benchmark assumptions | Compare and metrics surfaces include benchmark summaries and direct-comparability diagnostics. | Benchmark mode, benchmark symbol, missing benchmark data, and fallback behavior must be explicit. | Tests for no benchmark, buy-and-hold benchmark, explicit benchmark symbol, missing benchmark data, and cross-market benchmark mismatch. |
| Date/timezone handling | Backtest docs discuss run timing, period start/end, local parquet fixtures, and source diagnostics. | Public users can misread results if date inclusivity, exchange calendar, timezone, or after-hours boundaries are ambiguous. | Fixture matrix for inclusive/exclusive date boundaries, market calendar gaps, timezone normalization, and reproducible period metadata. |
| Survivorship bias | Current docs describe source and fallback disclosure, but do not claim survivorship-bias-free universes. | Public exposure must not imply historical universe completeness where only current symbols or sampled fixtures are used. | UI/API disclosure that single-symbol and fixture/local-parquet tests do not eliminate survivorship bias; universe-level tests only after a dated constituent source exists. |
| Data freshness/source disclosure | Existing result authority, artifact availability, readback integrity, and `requested_mode / resolved_source / fallback_used` diagnostics are strong foundations. | Diagnostics must stay visible enough for public users to distinguish real, fallback, stale, rebuilt, or unavailable artifacts. | Route/API tests asserting source labels, as-of dates, fallback flags, trace availability, and readback-integrity states for fresh, stale, fallback, and legacy runs. |

Backtest public-safety position:

- Backtest may remain an analysis and research tool.
- It must not be presented as investment advice, guaranteed performance, or a
  trade recommendation engine.
- Public launch should block until deterministic fixture and bias-prevention
  tests exist for the calculation paths being exposed.

## 5. Portfolio safety review

| Risk area | Current posture | Public-safety blocker | Required evidence before public exposure |
| --- | --- | --- | --- |
| Owner isolation | Portfolio API/test/docs show owner-scoped contracts and admin read surfaces. | Every account, snapshot, trade, cash ledger, import, broker connection, and export path must reject cross-owner access. | Authenticated owner A/B tests proving 404-style non-disclosure for mismatched account/run ids and no cross-user rows in list endpoints. |
| Cash/holdings/P&L accounting | Portfolio QA covers populated holdings and analytics rendering; recent tasks intentionally avoided changing accounting. | Public exposure requires invariant tests around cash, holdings, realized P&L, unrealized P&L, fees, taxes, FX, and corporate actions. | Deterministic fixture ledger with expected balances after buys, sells, fees, taxes, dividends, splits, FX conversion, and partial closes. |
| Import/replay safety | Portfolio has import and replay-sensitive domains; broker overlay sync has separate semantics from historical imports. | Imports must be idempotent, replayable, and auditable without duplicating cash/trades/holdings. | Import idempotency tests, replay rebuild tests, duplicate-file detection, rollback/preview checks, and clear separation of historical import versus current-state broker overlay. |
| Broker credential isolation | Guardrails prohibit printing or logging broker credentials. | Credential storage, diagnostics, errors, and admin views must never expose raw tokens, session ids, account secrets, or provider payloads. | Redaction audit for broker connection APIs, logs, admin detail views, import errors, sync failures, and browser-visible developer panels. |
| No accidental mutation | Portfolio QA recorded no mutation requests during read-only route verification. | Public read views, admin read views, exports, risk views, and refresh-style operations must not mutate accounting state unless explicitly confirmed. | Mutation guard tests around all read routes plus confirmation/idempotency tests for trade, cash, corporate action, import, sync, and delete-like operations. |
| Audit logs | Existing portfolio event logging patterns cover successful writes and avoid blocking product writes on log failures. | Public exposure requires consistent actor/session/symbol/account attribution for all sensitive writes and imports. | Tests that buy/sell/cash/corporate-action/import/sync writes create sanitized execution/audit events with owner, actor, account, symbol, action, outcome, and correlation id. |

Portfolio public-safety position:

- Portfolio can be shown as a user-owned accounting surface only after owner
  isolation and accounting invariants are proven with deterministic fixtures.
- Broker sync must remain read-only/current-state overlay unless a separate
  broker execution safety review approves mutation or order placement.
- Public pages must avoid accidental trade/order language and must preserve
  no-advice posture.

## 6. Multi-user risk review

| Risk area | Why it matters | Required control |
| --- | --- | --- |
| Cross-user leakage | Backtest run ids, portfolio account ids, and admin read endpoints can leak private financial state if ownership checks are incomplete. | Owner-scoped list/detail/export tests for all user-facing ids; mismatches return non-disclosing not-found responses. |
| Stale cache leakage | Shared caches can accidentally return prior-user snapshots, source diagnostics, or exports. | Cache keys include owner/session/domain dimensions where private data is involved; stale public data is clearly marked and never mixed with private rows. |
| Export/download isolation | Backtest trace CSV/JSON and future portfolio exports can bypass UI guards if download endpoints lack owner checks. | Every export endpoint checks the same owner/admin boundary as the detail read and has tests for mismatched ids. |
| Admin read boundaries | Admin portfolio reads and logs are powerful and must not become broad debug dumps. | Capability-gated admin reads, sanitized metadata, no raw broker credentials, no raw session ids, and audit logs for sensitive admin access where policy requires it. |
| Guest/public history | Guest preview and public analysis history use different ownership semantics than authenticated users. | Guest buckets must be hashed/bounded, separated from authenticated owner ids, and excluded from portfolio/accounting state. |

## 7. Required tests before public exposure

These tests are blockers for public multi-user exposure of Backtest and
Portfolio.

| Test family | Required coverage | Exit criteria |
| --- | --- | --- |
| Owner isolation | Backtest runs/results/status/export; portfolio accounts/snapshot/risk/trades/cash/corporate actions/imports/broker connections/admin reads. | Owner A cannot list, read, export, mutate, or infer Owner B resources. Admin reads require the documented capability boundary. |
| Deterministic fixtures | Standard backtest, rule backtest, result reopen, compare, execution trace, portfolio ledger replay, FX conversion, P&L. | Repeated runs on fixed fixtures produce stable outputs or documented, bounded timestamp-only differences. |
| Import idempotency | Portfolio broker/file imports, duplicate imports, partial failures, retry after failure, sync overlay replay. | Re-running the same import does not duplicate cash, trades, holdings, fees, taxes, or audit events beyond an idempotency marker. |
| Accounting invariants | Cash balance, position quantity, average cost, realized/unrealized P&L, fees, taxes, dividends, splits, FX, account totals. | Ledger-derived totals equal snapshot totals within documented rounding tolerance; negative or impossible states fail safely. |
| Rollback/replay safety | Backtest stored artifact reopen, portfolio replay rebuild, cancelled/failed imports, broker sync rollback, export regeneration. | Reopen/replay reads do not invent complete artifacts, and failed/cancelled operations leave either no mutation or a clearly auditable terminal state. |
| Mutation guard | Public read routes, admin read routes, exports, dashboard loads, browser QA flows. | Read-only interactions send no write requests and do not mutate storage. |
| Redaction | Broker credentials, provider payloads, tokens, sessions, cookies, stack traces, raw prompts, raw LLM payloads. | No sensitive raw values appear in API responses, logs, docs, exported artifacts, or default-visible UI. |

## 8. Public exposure blockers

Backtest blockers:

- Missing documented golden fixture suite for deterministic metrics, trades,
  equity curve, benchmark, and trace exports.
- Missing explicit lookahead-bias regression tests for signal and execution
  timing.
- Missing complete fee/slippage/benchmark/date/timezone assumption test matrix.
- Survivorship-bias limitations need to be visible wherever universe-level or
  historical-performance claims could be inferred.

Portfolio blockers:

- Missing end-to-end owner-isolation smoke across all portfolio read, write,
  import, broker, and export-like paths.
- Missing deterministic accounting invariant suite covering cash, holdings,
  P&L, fees, taxes, corporate actions, and FX.
- Missing import idempotency and rollback/replay evidence for public user data.
- Broker credential redaction must be audited across API responses, logs,
  admin views, sync failures, and import errors.

Shared blockers:

- Export/download isolation must be proven for private artifacts.
- Admin read boundaries must be capability-scoped and sanitized.
- Stale cache leakage must be ruled out for private owner-scoped data.
- Public launch copy must remain analysis-only and no-advice.

## 9. Non-goals

- Do not change backtest calculations in this audit.
- Do not change portfolio accounting, imports, broker sync, cash, holdings,
  P&L, FX, or audit behavior in this audit.
- Do not use this audit as public-launch approval.
- Do not add broker order placement, buy/sell recommendation CTAs, guaranteed
  return language, or personalized financial advice.

## 10. Recommended next prompts

Focused backtest regression suite:

```text
Task: Add a focused backtest public-safety regression suite.

Scope: tests/docs only unless a failing test exposes a confirmed bug. Cover
deterministic fixtures, lookahead-bias prevention, fee/slippage assumptions,
benchmark modes, date/timezone boundaries, source/freshness disclosure, and
stored-first reopen/export integrity. Do not change calculation behavior unless
explicitly re-scoped after test evidence.
```

Portfolio owner-isolation smoke:

```text
Task: Add a portfolio owner-isolation smoke suite.

Scope: tests/docs only unless a confirmed authorization bug is found. Cover
accounts, snapshot, risk, trades, cash ledger, corporate actions, imports,
broker connections, admin portfolio reads, and export-like endpoints. Verify
non-disclosing not-found behavior for cross-owner ids and no accidental
mutation from read paths.
```

Broker credential redaction audit:

```text
Task: Audit broker credential redaction for public multi-user readiness.

Scope: docs/tests first. Inspect broker connection APIs, import/sync errors,
execution/admin logs, frontend developer panels, and exports. Prove no raw
credential, token, session id, provider payload, stack trace, or account secret
is returned or logged. Do not change broker sync/accounting behavior unless a
confirmed leak is found and explicitly approved for fix scope.
```

## 11. Validation plan for this docs-only pass

Required validation:

```bash
git diff -- docs/audits/backtest-portfolio-public-safety-audit.md docs/CHANGELOG.md
git diff --check -- docs/audits/backtest-portfolio-public-safety-audit.md docs/CHANGELOG.md
```

No `ci_gate` is required because this pass changes documentation only.
