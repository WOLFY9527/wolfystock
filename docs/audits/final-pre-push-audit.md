# Final Pre-push Audit

Date: 2026-05-07
Branch checked: `main`
Mode: docs-only final audit, risk review, and markdown inventory. No production
runtime, frontend app code, tests, schema, config, or markdown files outside the
requested audit package were edited by this task.

## Executive Verdict

Final push posture: **CONDITIONALLY OK FOR A REVIEWED NON-LAUNCH PUSH**, but
**NO-GO for public multi-user launch**.

The recent train is mostly additive and well-labeled in runtime boundaries, but
it carries several intentional readiness gaps:

- coarse admin RBAC compatibility fallback still exists;
- MFA metadata/recovery-code foundation exists, but login enforcement remains
  disabled and production TOTP secret storage is still blocked;
- Options provider/live paths remain fixture, synthetic, delayed, disabled, or
  not implemented;
- cost/quota and provider circuit paths remain diagnostics, dry-run, or
  storage foundations unless explicitly operated through admin diagnostic calls;
- data quality and fallback labeling must remain visible before any
  decision-like label is trusted;
- browser harnesses are heavily mocked and are not proof of real auth/session
  behavior.

## Preflight State

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- Branch: `main`
- `git rev-list --left-right --count HEAD...origin/main` before the concurrent
  consolidation commit: `64 0`.
- During this audit, a separate commit landed on `main`:
  `a71fb349 docs(audit): plan markdown consolidation`. Current local history
  before staging this package was therefore ahead 65, before this audit commit.
- `git status --short --branch` before staging this package showed three
  unrelated dirty test files plus these two new audit docs.
- Shared ports inspected: `8000`, `8001`, `5173`, `4173`, `5174`, `5175`,
  `5176`, `4177`. `lsof` reported Python listeners on `localhost:irdmi`
  through the inspected port set; no ports were killed or restarted.
- Unrelated dirty-file safety: `tests/test_portfolio_service.py`,
  `tests/test_rule_backtest_support_bundle_e2e.py`, and
  `tests/test_scanner_strategy_simulation.py` were not modified or staged by
  this task.

## Commit Attribution Audit

| Commit | Message | Actual content | Finding |
| --- | --- | --- | --- |
| `29cb0b34` | `docs(data): compare market data provider upgrade paths` | Modified `docs/CHANGELOG.md`; added `db-retention-backup-restore-drill-plan.md` and `release-integration-plan-main-ahead.md`. | **Mismatch.** Content is DB retention/restore plus release integration, not market data provider comparison. |
| `7d83c30a` | `docs(release): plan main branch integration` | Added `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`. | **Mismatch.** Content is Codex guard, not the release integration plan. |
| `b59dfee5` | `docs(codex): add standard task guard` | Added `market-data-provider-upgrade-decision-matrix.md`, `provider-data-incident-runbook.md`, and `release-rollback-runbook.md`. | **Mismatch.** Content is provider/data/rollback docs, not the Codex guard. |
| `a072cec0` | `docs(data): compare market data provider upgrade paths` | Added `market-data-provider-upgrade-decision-matrix.md`. | **Accurate content, but not reachable from current `main`.** `git branch --contains a072cec0 --all` returned no branches. |

Similar obvious recent-history issues:

- `da54efe1 docs(db): plan retention and restore drills` is an empty commit in
  current `main` history. It likely records an intended docs step already
  represented by neighboring commits, but it carries no file changes.
- `a71fb349 docs(audit): plan markdown consolidation` is title/content accurate,
  but it landed concurrently while this audit was being prepared and overlaps
  the requested markdown-inventory output. Treat it as a coordination item, not
  an attribution error.
- The sequence `29cb0b34` -> `7d83c30a` -> `b59dfee5` appears title-shifted:
  each title describes another nearby docs payload.
- No similarly obvious message/content mismatch was found in the later sampled
  commits from `8c6f6f62` through `fb1a31b4`.

## Prompt-output Risk Audit

### Highest Risk

1. **RBAC/capability fallback remains intentional, not least-privilege final.**
   `require_admin_capability()` still depends on `require_admin_user()` and
   `expand_admin_capabilities()` still falls back to the built-in
   `super-admin` capability set for legacy admins without explicit role rows.
   This is not an accidental fail-open, but it is a public-launch blocker until
   R5 inventory, observe/warn, fail-closed pilot, and rollback evidence exist.

2. **MFA must not be described as enforced login.** MFA endpoints return
   `mfaRequiredForLogin: false`, endpoint descriptions say login enforcement
   remains disabled, and tests assert the non-enforcing behavior. Production
   TOTP secret storage remains blocked: `WOLFYSTOCK_MFA_TEST_SECRET` can create
   recoverable `test-only:` secret refs, while the default path is
   `placeholder-sha256:` and cannot support production verification.

3. **Options must remain analysis-only and fixture/synthetic capped.** The
   service still declares no live providers, no broker execution, no order
   placement, and no portfolio mutation. The frontend displays fixture/demo
   disclosures and tests assert delayed fixtures cannot emit `有条件可交易`. Do
   not market this as live tradable Options decisioning.

4. **Cost/quota and provider circuit are not live enforcement.** Provider
   circuit observer code explicitly records dry-run observations and does not
   read circuit state for enforcement. The admin quota dry-run route can mutate
   synthetic quota reservation state for `reserve`/`consume`/`release`, but the
   response metadata states `diagnosticOnly: true`, `liveEnforcement: false`,
   and `noExternalCalls: true`. Do not describe this as production spend
   enforcement.

5. **Browser harness over-mocking is a real acceptance risk.** The admin and
   product E2E harnesses route `**/api/v1/**` to mocked fixtures and are useful
   for UI smoke coverage, not real auth/session verification. The live smoke is
   opt-in via `DSA_WEB_LIVE_SMOKE=1`. Final release evidence still needs real
   auth/session checks or an explicit statement that browser proof is mocked.

### Medium Risk

- Data Pipeline R2 exposes progressive enrichment state safely, but late async
  durable merge is not implemented. Optional enrichment must not be shown as a
  fully live complete report if required/important data is missing or stale.
- The data disclosure policy is strong, but enforcement still depends on each
  surface preserving visible source/as-of/freshness/fallback labels.
- Secret scans found fake/test fixtures such as `sk-should-not-render`,
  `sk-live-secret`, and masked placeholders in tests, plus documentation
  examples. No real credential value was identified in the sampled docs/code
  search. Continue avoiding `.env` value inspection.
- `HomeBentoDashboardPage` includes a dev/test fixture route gated by
  `import.meta.env.DEV || import.meta.env.MODE === 'test'`; this should stay
  out of production builds and not be used as live analysis proof.

### Low/Controlled Risk

- Test-only recent commits (`fb1a31b4`, `f5dac4a7`, `39b65b3d`) do not appear
  to touch production runtime code, but they add or depend on mocked harnesses.
- Forbidden trading/order wording appears in policy docs and tests as negative
  examples. Runtime Options and Backtest surfaces still contain analytical
  trading terminology such as "trade quality" and backtest trade rows; no
  broker/order placement path was identified in the sampled recent Options work.

## Markdown Inventory Summary

Detailed inventory: `docs/audits/markdown-inventory.md`.

Recommendations:

- Keep standalone: standard guard, public launch gap register, deployment
  checklist, release integration plan, rollback runbook, provider/data incident
  runbook, CI/PostgreSQL triage guide, trading/no-advice policy, data quality
  disclosure policy, market data provider matrix, Options provider adapter
  contract, active RBAC/MFA/WS2/provider/cost blocker docs.
- Merge later: admin data/governance contracts, cost observability contracts,
  provider/MarketCache instrumentation docs, reuse/cache designs, CSS/DOM proof
  reports, and older frontend audit evidence.
- Archive/superseded candidates: older Options phase-zero design, Batch A DB
  plan, early RBAC capability design after status marking, historical QA
  reports, and one-off implementation summaries once domain indexes exist.
- Stale/needs status header: large design/audit docs with partial
  implementation notes, especially RBAC capability model, password KDF plan,
  production security hardening audit, DB Batch B plan, provider circuit data
  model plan, and older visual audits.
- Duplicate/possible conflict: duplicate-cost API/UI docs, overlapping admin
  data docs, overlapping provider circuit/fallback docs, and the trio of
  public-launch/deployment/release-integration docs. Keep all three launch docs
  for now, but clarify source-of-truth ownership.

Coordination note: `docs/audits/markdown-consolidation-plan.md` is now tracked
by concurrent commit `a71fb349` and overlaps this inventory. Reconcile the two
docs in a future cleanup before moving or deleting audit markdown.

## ci_gate Blocker Classification

Current task result: **ci_gate not run**. This is a docs-only audit task, and
the guard allows docs-only validation with `git diff --check`.

Known classification from current docs and sampled history:

- `public-launch-gap-register.md` and `deployment-readiness-checklist.md` treat
  final clean `./scripts/ci_gate.sh` as a P0 release-candidate requirement.
- `release-integration-plan-main-ahead.md` requires one clean full gate plus
  frontend gates and browser harness checks before push/release.
- `admin-rbac-final-qa-report.md` contains an older `ci_gate` blocker note
  attributed to an unrelated untracked quota-policy test/import worktree state;
  treat that as stale until reproduced on current `main`.
- Current working tree had unrelated dirty test files while this docs-only
  package was staged, so a final clean release gate should wait until those
  test edits are resolved or intentionally included by their owner.

Lightweight checks run for this audit:

- `git show --stat --name-status` for the named commits.
- `git log --oneline --name-status -n 25` for recent mismatch sampling.
- targeted `rg` scans for RBAC/MFA/Options/quota/provider/data-quality/secrets
  and browser harness mocking.
- no backend tests, frontend tests, browser checks, or full `ci_gate`.

## Validation

| Command | Result |
| --- | --- |
| `git diff --check -- docs/audits/final-pre-push-audit.md docs/audits/markdown-inventory.md` | PASS; no whitespace errors. |
| `rg -n "markdownlint\|markdownlint-cli2\|remark\|lint:md\|lint.*markdown\|mdlint" apps/dsa-web/package.json .github scripts docs/codex docs/audits ...` | Markdown lint search only. Found `remark-gfm` dependency and prior audit notes, but no runnable markdown lint script. |
| `git status --short --branch` | Before staging: `main...origin/main [ahead 65]`, three unrelated dirty test files, and two new audit docs. |

No backend tests, frontend tests, browser checks, or `./scripts/ci_gate.sh` were
run for this docs-only audit.

## Safety and Rollback

- Files intentionally changed by this task:
  - `docs/audits/final-pre-push-audit.md`
  - `docs/audits/markdown-inventory.md`
- Files intentionally not touched:
  - production runtime;
  - frontend app code;
  - tests;
  - existing audit docs;
  - `docs/CHANGELOG.md`;
  - `docs/audits/markdown-consolidation-plan.md`.
- Rollback for this docs-only package:

```bash
git revert <audit_commit_sha>
```
