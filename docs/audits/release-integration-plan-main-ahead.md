# Main Branch Release Integration Plan

> Historical evidence note
>
> Superseded for current audit navigation by `docs/audits/README.md` and for
> the current public launch verdict by
> `docs/audits/public-launch-readiness-master.md`. This file captures a
> point-in-time local-ahead integration plan and must not be treated as the
> current ahead/behind state or launch decision.

Date: 2026-05-07
Branch checked: `main`
Upstream comparison: local `main` is ahead of `origin/main` by 49 commits.
Mode: docs-only integration planning. Do not push, merge, rebase, squash, reset,
tag, alter history, or change remotes as part of this plan.

## 1. Executive summary

Recommended release posture: **stage and validate as one integrated release
candidate before any push**, then choose either a linear `main` push or a review
branch PR based on validation results and coordination needs.

The ahead commits form one long, mostly additive integration train across
RBAC/security, Options, WS2 durable task runtime, cost/quota, provider circuit
observability, Data Pipeline quality metadata, database readiness, and docs.
The release is not a public multi-user go-live. It remains a readiness
foundation with explicit blockers: MFA enforcement is disabled, provider
circuit enforcement is disabled, quota enforcement is disabled, real Options
provider coverage is missing, and multi-instance staging smoke has not been
implemented.

## 2. Commit grouping

### RBAC and security

Purpose: capability-based admin authorization foundations, sensitive-route
migration, admin reauth, password KDF upgrade, MFA backend scaffold, and browser
harness coverage.

- `684b3629` `feat(admin): migrate pilot routes to rbac capabilities`
- `23c81333` `feat(admin): expose safe rbac capability summary`
- `b3fb727d` `feat(admin): gate frontend admin surfaces by capability`
- `05a1abd1` `feat(admin): migrate ops-sensitive routes to rbac capabilities`
- `c319431d` `docs(admin): add rbac final qa report`
- `8a45f163` `feat(security): add recent admin reauth source`
- `2d5d4888` `feat(security): require reauth for admin security writes`
- `35cf5843` `test(admin): add admin auth browser harness`
- `a42621cf` `test(admin): assert admin auth harness console clean`
- `3057f6d3` `docs(security): plan password kdf upgrade`
- `e4313fa7` `feat(security): add versioned password kdf upgrade`
- `38135430` `test(app): add authenticated product route harness`
- `31bb98e8` `feat(security): add admin mfa backend foundation`
- `063e971f` `feat(security): add mfa recovery code foundation`
- `2fc48f87` `docs(admin): plan rbac coarse fallback removal`

Integration notes:

- Treat this as the highest-risk group because it touches auth/session/RBAC,
  password storage, admin capability exposure, and MFA scaffolding.
- Confirm coarse admin compatibility fallback remains intentional before push.
- Confirm MFA login enforcement is still explicitly disabled and documented as
  a blocker, even with recovery-code foundation work present.

### Options

Purpose: read-only Options Lab expansion from strategy comparison through
decision quality, IV/expected-move optimizer, and provider adapter contract.

- `25cdfad7` `feat(options): integrate strategy comparison frontend`
- `e7f764b3` `fix(options): harden options lab loading states`
- `28f1ddb1` `test(options): strengthen options lab real-auth QA`
- `2b3c894b` `fix(options): prevent options lab black screen`
- `99f09cc6` `feat(options): add trade quality decision engine`
- `255db053` `feat(options): add iv expected move strategy optimizer`
- `a43f7d21` `feat(options): add provider adapter contract`

Integration notes:

- Keep Options public messaging analysis-only and demo/fixture-capped where
  real provider evidence is absent.
- No broker execution, order placement, portfolio mutation, or personalized
  financial advice posture is part of this group.
- The real provider adapter remains a blocker before live production Options
  decisioning.

### WS2, cost, and quota

Purpose: durable task state/progress foundations, synthetic worker, quota policy
foundation, quota dry-run, LLM pricing/cost ledger, owner context propagation,
admin cost dashboards, and final cost QA matrix.

- `0561bdbd` `feat(ws2): add durable analysis task state foundation`
- `c976abcf` `feat(ws2): add durable task worker prototype`
- `79d60eb5` `feat(ws2): add durable task progress polling`
- `2de447e2` `feat(ws2): add quota policy foundation`
- `8255161f` `feat(ws2): add quota dry-run integration`
- `4cb17e1d` `feat(admin): add quota dry-run dashboard`
- `20ba904a` `feat(cost): add llm pricing and cost ledger foundation`
- `9245665e` `feat(cost): reconcile llm usage into cost ledger`
- `9feef7ab` `feat(cost): add model pricing policy import workflow`
- `86e3b213` `feat(admin): show llm cost ledger summaries`
- `e6b526fc` `feat(cost): reconcile ledger costs with quota reservations`
- `19ca8757` `feat(admin): show model pricing policies`
- `0950bf5e` `feat(cost): propagate owner context to llm ledger`
- `4cfe4eb5` `docs(ws2): design multi-instance smoke tests`
- `3237ed16` `docs(cost): add final qa matrix`

Integration notes:

- Durable status/polling is a readiness foundation; current SSE remains
  process-local and must not be treated as cross-instance reliable.
- Cost ledger and quota paths are observational/dry-run unless a separate live
  enforcement stage is approved.
- Multi-instance staging smoke is required before claiming public multi-user
  task-runtime readiness.

### Provider circuit

Purpose: provider quota/circuit policy design, storage, diagnostics API, dry-run
observer counters, and admin diagnostics UI.

- `410c5cef` `docs(ws2): design provider quota circuit breaker policy`
- `69f2eca5` `docs(ws2): plan provider circuit data model`
- `fdca92d9` `feat(ws2): add provider circuit storage foundation`
- `39e0e4b0` `feat(admin): add provider circuit diagnostics api`
- `ec5ab7bc` `feat(ws2): add provider circuit dry-run counters`
- `48cabce4` `feat(admin): show provider circuit diagnostics`

Integration notes:

- This group must remain diagnostics/dry-run only for the release candidate.
- No provider ordering, fallback, retry, timeout, MarketCache, or live call-site
  enforcement behavior should be claimed as changed unless separately proven.
- Validate diagnostics redaction before exposing staging data.

### Data Pipeline

Purpose: fast-decision quality gating plus progressive enrichment metadata for
optional enrichment status.

- `fd0b836d` `feat(analysis): add fast decision data quality pipeline`
- `36f6d3a4` `feat(analysis): add progressive enrichment status`

Integration notes:

- Required/important data should drive fast-decision availability and confidence
  caps.
- Optional `news`, `sentiment`, and `detailed_fundamentals` enrichment must
  remain non-blocking with sanitized reason codes.
- This is medium risk because it affects analysis payload shape and frontend
  interpretation, even if it avoids provider/runtime ordering changes.

### DB and docs

Purpose: database readiness audits/plans, first production-readiness indexes,
and public deployment readiness consolidation.

- `4e641017` `docs(db): audit production index and retention readiness`
- `2e15be2e` `docs(db): plan first production index migrations`
- `17111ecd` `feat(db): add first production readiness indexes`
- `148ce095` `docs(deploy): add public readiness checklist`

Integration notes:

- Treat DB index changes as high-risk storage/schema-adjacent work even when
  additive.
- Backup/restore drill, retention tiers, and remaining index batches are not
  completed by this train.
- The deployment readiness checklist remains the go/no-go control document for
  public multi-user exposure.

## 3. Risk classification

### High risk: auth, security, storage, schema

Groups:

- RBAC and security
- DB and docs, specifically `17111ecd`
- WS2 durable task state/progress storage
- Cost/quota ledger and reservation storage
- Provider circuit storage

Why:

- These touch authentication, authorization, password storage, MFA metadata,
  durable task tables, cost/quota tables, provider circuit tables, or additive
  indexes.
- Regressions can affect login, admin access, data ownership, persistence,
  schema initialization, migration compatibility, or operational visibility.

Required release evidence:

- Clean full `./scripts/ci_gate.sh` after unrelated dirty work is resolved.
- Focused auth/RBAC/MFA tests.
- Schema/init/migration smoke for SQLite/local path and any PostgreSQL baseline
  checks already present in the repo.
- Admin login, reauth, and protected-route browser harness checks.

### Medium risk: analysis and provider

Groups:

- Data Pipeline
- Provider circuit diagnostics/dry-run
- Options decision analysis where it depends on provider-like data contracts

Why:

- These affect analysis output interpretation, diagnostics, provider-facing
  status, and data-quality decisions.
- The release must avoid overstating runtime provider enforcement or live
  Options readiness.

Required release evidence:

- Targeted Data Pipeline fast decision tests.
- Provider circuit storage/API/diagnostics tests with redaction assertions.
- Options Lab real-auth and fixture-backed decision tests.
- Browser smoke for provider diagnostics and Options Lab.

### Frontend-only or frontend-facing

Commits:

- `25cdfad7` Options Lab frontend integration
- `b3fb727d` frontend admin capability gates
- `4cb17e1d` quota dry-run dashboard
- `19ca8757` model pricing policies panel
- `48cabce4` provider circuit diagnostics UI
- Frontend portions of `36f6d3a4` progressive enrichment status

Required release evidence:

- `cd apps/dsa-web && npm run lint`
- `cd apps/dsa-web && npm run build`
- `cd apps/dsa-web && npm run check:design --if-present`
- Browser harness checks for authenticated admin/product routes.
- Manual browser spot checks for the staging surfaces listed below.

### Docs-only

Commits:

- `4e641017`
- `2e15be2e`
- `c319431d`
- `410c5cef`
- `69f2eca5`
- `4cfe4eb5`
- `3057f6d3`
- `148ce095`
- `3237ed16`
- This document

Required release evidence:

- Markdown diff review.
- `git diff --check -- <changed-doc-files>`.
- Confirm docs do not claim completed enforcement or public go-live where only
  scaffold, dry-run, fixture, or readiness work exists.

## 4. Pre-push checklist

Run these gates before any push or PR creation:

- [ ] Confirm repository and branch:
  `pwd` is `/Users/yehengli/daily_stock_analysis` and
  `git branch --show-current` is `main`.
- [ ] Resolve or intentionally isolate unrelated dirty work until
  `git status --short` is clean except for the release-plan commit being
  prepared.
- [ ] Re-check ahead state with `git rev-list --left-right --count
  origin/main...main` and `git log --oneline --reverse origin/main..main`.
- [ ] Run one clean full backend gate: `./scripts/ci_gate.sh`.
- [ ] Run frontend gates:
  `cd apps/dsa-web && npm run lint && npm run build &&
  npm run check:design --if-present`.
- [ ] Run focused auth/RBAC/security tests covering login, auth status/me,
  recent reauth, admin user-security writes, KDF upgrade, and MFA scaffold.
- [ ] Run focused Options Lab tests covering loading states, real-auth harness,
  strategy comparison, decision engine, IV/expected move, and provider adapter
  contract behavior.
- [ ] Run focused WS2/cost/quota tests covering durable task state, progress
  polling, synthetic worker, quota dry-run, cost ledger reconciliation, pricing
  policies, and owner/guest attribution.
- [ ] Run focused provider circuit tests covering storage, diagnostics API,
  dry-run counters/events, quota windows, probe events, and redaction.
- [ ] Run focused Data Pipeline tests covering fast decision data quality and
  progressive enrichment metadata.
- [ ] Run DB/init/migration/index smoke against the supported local path and any
  PostgreSQL baseline smoke available in the repo.
- [ ] Run browser harness checks for authenticated product routes and admin auth
  routes.
- [ ] Run staging/manual browser checks for the surfaces in section 6.
- [ ] Run a secrets scan on the ahead range and final diff. Minimum local gate:
  inspect `git diff origin/main..main` for accidental credentials, raw provider
  payloads, cookies, session IDs, `.env` values, webhook URLs, private keys, and
  raw LLM/provider payloads. Prefer the repo's configured scanner if one exists.
- [ ] Review `docs/CHANGELOG.md` and deployment docs for no-go wording:
  scaffolds, dry-run paths, and fixtures must not be described as live public
  enforcement.

## 5. Merge strategy

### Option A: push local `main` as linear main

Use when:

- The worktree is clean.
- Full `ci_gate`, frontend gates, targeted tests, browser harness, and staging
  smoke pass.
- The team accepts one long linear release train and does not need PR-by-PR
  review of the ahead commits.
- No blocker requires removing or rewriting a subset of commits.

Pros:

- Preserves the actual local history as already integrated.
- Avoids risky rebase/squash work on a long branch.
- Minimizes branch-management overhead.

Cons:

- Review granularity is weaker.
- Rollback must be planned by commit group rather than by a single small PR.
- A late high-risk failure may force a branch PR or targeted revert strategy.

### Option B: create a branch PR from current `main`

Use when:

- Review, CI, deployment approval, or staging evidence should happen before
  updating remote `main`.
- Any high-risk group needs human review but the integrated history should stay
  intact.
- The team wants GitHub CI/check visibility on the whole train before main is
  advanced.

Recommended shape:

- Create a branch from current local `main` only after the worktree is clean.
- Push that branch and open a PR against `origin/main`.
- Do not rebase, squash, or rewrite the existing local commit train unless a
  separate explicit history-cleanup task is approved.

### When to split PRs

Split only if validation exposes a group-specific blocker that can be isolated
without rewriting unrelated work:

- Split RBAC/security if auth, KDF, reauth, or MFA scaffold validation fails.
- Split Options if fixture/read-only behavior regresses or real-provider wording
  leaks into product UI.
- Split WS2/cost/quota if durable task or cost/quota schema/runtime tests fail.
- Split provider circuit if diagnostics redaction or storage behavior fails.
- Split Data Pipeline if fast-decision payload compatibility breaks.
- Split DB/index work if migration/init/index smoke fails.

Do not split just to make the history prettier. Splitting a 49-commit local
train adds risk unless there is a concrete failing gate or review requirement.

## 6. Staging validation checklist

Run these against a staging-like deployment with sanitized accounts and no
production secrets printed in logs:

- [ ] Auth login: normal login succeeds, disabled/invalid users fail safely, and
  auth status/me payloads expose bounded capability summaries only.
- [ ] Admin reauth: sensitive admin user-security writes require recent reauth
  and preserve self-action, last-admin, reason, confirmation, and audit
  protections.
- [ ] MFA scaffold: enroll/start, enroll/verify, verify, and disable paths work
  for the intended admin-only scaffold; login MFA enforcement remains disabled
  and clearly documented.
- [ ] Options Lab: page loads without black screen, fixture-backed chain and
  strategy comparison render, decision engine returns conservative outputs, and
  no order-placement or personalized advice CTAs appear.
- [ ] Data Pipeline fast decision: required/important data gates set
  `requiredAvailable`, `dataQualityTier`, and `confidenceCap` correctly.
- [ ] Data Pipeline progressive enrichment: optional news/sentiment/detailed
  fundamentals states render as pending/partial/complete/skipped without
  blocking fast decision.
- [ ] Admin cost dashboard: ledger summary, model pricing policies, and quota
  dry-run dashboard render only for authorized users and never imply live quota
  enforcement.
- [ ] Provider circuit diagnostics: circuit states, events, quota windows, and
  probe events are visible to authorized admins, redacted, and clearly labeled
  diagnostics/dry-run where applicable.
- [ ] Durable task status/poll: owner-scoped task status and progress polling
  replay safe events, expose terminal state, and preserve owner isolation.
- [ ] Browser harness: authenticated product/admin routes load cleanly with no
  console errors, route protection leaks, or horizontal overflow on target
  viewports.
- [ ] Multi-instance limitation: document that production remains single API
  process or sticky routing until WS2 multi-instance smoke is implemented and
  passed.

## 7. Known blockers and explicit non-goals

These are not solved by the ahead branch and must remain visible in release
notes, deployment readiness docs, and go/no-go decisions:

- MFA enforcement disabled: backend scaffold and recovery-code foundation exist,
  but production secret storage and staged enforcement are not complete.
- Provider live enforcement disabled: circuit storage, diagnostics, and dry-run
  counters exist, but no live provider call site changes enforcement/order/
  fallback behavior.
- Quota live enforcement disabled: cost ledger, pricing policy, quota
  foundation, and dry-run paths exist, but route-boundary enforcement is not
  enabled.
- Real Options provider missing: Options Lab remains read-only and
  fixture/synthetic/fallback capped until real provider entitlement, freshness,
  bid/ask, OI/volume, IV, Greeks, multiplier, and symbology evidence exists.
- Multi-instance smoke not implemented: durable status and synthetic worker
  foundations exist, but public multi-instance readiness requires staging proof
  across API A submit, worker lease, API B durable read, polling replay, owner
  isolation, lease expiry recovery, retry/failure safety, and degraded readiness.

## 8. Rollback grouping

Prefer rollback by tested commit group, not broad history rewrite.

### RBAC/security rollback

Candidate rollback group:

- `31bb98e8`, `e4313fa7`, `2d5d4888`, `8a45f163`, `05a1abd1`,
  `b3fb727d`, `23c81333`, `684b3629`, `063e971f`, `2fc48f87`, plus related
  harness/docs commits if needed.

Use if:

- Login, current-user payloads, admin route authorization, password verification,
  KDF upgrade, reauth, or MFA scaffold breaks.

Rollback notes:

- Reverting this group may conflict with later admin/cost/provider dashboards
  that rely on capability summaries. Re-test admin navigation and protected
  routes after rollback.

### Options rollback

Candidate rollback group:

- `a43f7d21`, `255db053`, `99f09cc6`, `2b3c894b`, `28f1ddb1`,
  `e7f764b3`, `25cdfad7`.

Use if:

- Options Lab fails to load, exposes unsafe trading language/CTAs, returns
  non-conservative outputs for fixture/synthetic data, or breaks route auth.

Rollback notes:

- Preserve no-advice and fixture/demo labeling if doing a partial rollback.

### WS2/cost/quota rollback

Candidate rollback group:

- `3237ed16`, `0950bf5e`, `19ca8757`, `e6b526fc`, `86e3b213`,
  `9feef7ab`, `9245665e`, `20ba904a`, `4cb17e1d`, `8255161f`,
  `2de447e2`, `79d60eb5`, `c976abcf`, `0561bdbd`, plus `4cfe4eb5`
  if the related design doc should move with the runtime train.

Use if:

- Durable task state/polling, synthetic worker, cost ledger, pricing policy,
  quota reservation/dry-run, or owner/guest attribution causes regressions.

Rollback notes:

- Durable task storage and cost/quota schema foundations may have additive DB
  artifacts. Confirm migration compatibility and whether no-op compatibility
  cleanup is safer than destructive rollback.

### Provider circuit rollback

Candidate rollback group:

- `48cabce4`, `ec5ab7bc`, `39e0e4b0`, `fdca92d9`, `69f2eca5`,
  `410c5cef`.

Use if:

- Diagnostics leak sensitive details, dry-run counters corrupt storage, provider
  circuit APIs break admin surfaces, or provider state is misrepresented as live
  enforcement.

Rollback notes:

- Because enforcement is disabled, prefer disabling UI/diagnostic exposure before
  reverting storage if a staging issue is presentation-only.

### Data Pipeline rollback

Candidate rollback group:

- `36f6d3a4`, `fd0b836d`.

Use if:

- Fast decision compatibility breaks, enrichment status blocks analysis, payload
  shape breaks frontend consumers, or reason-code sanitization fails.

Rollback notes:

- Preserve existing analysis fallback behavior and avoid provider-ordering or
  LLM-routing changes during rollback.

### DB/docs rollback

Candidate rollback group:

- `148ce095`, `17111ecd`, `2e15be2e`, `4e641017`.

Use if:

- Additive indexes break init/migration/query compatibility, or deployment docs
  create incorrect go/no-go messaging.

Rollback notes:

- Do not drop production indexes or schema artifacts without a separate DB
  rollback runbook. Docs can be corrected independently.

## 9. Recommended final pre-push Codex prompt

```text
Repo: /Users/yehengli/daily_stock_analysis
Branch: main

Task: Final pre-push verification for the long local main branch ahead of
origin/main. Do not push, merge, rebase, squash, reset, tag, or alter remotes.
Do not change runtime code unless I explicitly approve a follow-up fix.

Read first:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/audits/release-integration-plan-main-ahead.md
- docs/audits/deployment-readiness-checklist.md
- docs/CHANGELOG.md

Steps:
1. Confirm pwd, branch, git status, ahead/behind count, and exact ahead commits.
2. Stop if the worktree is not clean enough for meaningful release validation.
3. Run one full ./scripts/ci_gate.sh.
4. Run web gates: cd apps/dsa-web && npm run lint && npm run build &&
   npm run check:design --if-present.
5. Run targeted smoke tests for:
   - auth login/status/me/reauth/MFA scaffold
   - RBAC admin capability-gated routes
   - Options Lab strategy comparison and decision engine
   - Data Pipeline fast decision and progressive enrichment
   - WS2 durable task status/poll
   - cost ledger/model pricing/quota dry-run
   - provider circuit diagnostics and dry-run counters
   - DB init/migration/index paths
6. Run browser harness checks for authenticated product and admin routes.
7. Run or document the secrets scan used for the ahead range and final diff.
8. Produce a PASS/FAIL release gate report grouped by:
   RBAC/security, Options, WS2/cost/quota, provider circuit, Data Pipeline,
   DB/docs.

Final answer must include exact commands/results, blockers, risk grouping,
rollback grouping, and confirmation that no git history/remotes were changed.
```

## 10. Release decision template

Use this template after the final pre-push verification:

- Verdict: `GO`, `GO WITH EXCEPTIONS`, or `NO-GO`.
- Candidate strategy: linear `main` push or branch PR.
- Clean worktree: yes/no.
- Full `ci_gate`: pass/fail/not run.
- Frontend gates: pass/fail/not run.
- Targeted smoke tests: pass/fail/not run by group.
- Browser harness: pass/fail/not run.
- Secrets scan: pass/fail/not run.
- Known blockers carried forward: MFA enforcement, provider enforcement, quota
  enforcement, real Options provider, multi-instance smoke.
- Rollback grouping: RBAC/security, Options, WS2/cost/quota, provider circuit,
  Data Pipeline, DB/docs.
- History/remotes changed during verification: must be `no`.
