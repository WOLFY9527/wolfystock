# Private Beta Goal Progress

Date: 2026-06-11
Branch: `codex/goal-private-beta-candidate`
Goal: produce a reviewable private-beta readiness pack, apply safe
product-surface fixes, and keep public launch **NO-GO**.

## Guardrails

No slice may enable public launch, live quota enforcement, reservation
consume/blocking, provider runtime enforcement, global MFA enforcement, RBAC
fallback removal, DB migration/restore/cleanup/retention execution,
broker/order/trade paths, external notification sending, durable
outbox/retry/exactly-once claims, provider order/fallback/cache/runtime
changes, or auth/session/RBAC runtime behavior changes.

No slice may expose secrets, raw provider payloads, raw request/session/user or
owner IDs, broker/account data, stack traces, or debug internals.

## Slice 1: Reconcile Readiness Evidence

Status: validated.

Files:

- `docs/audits/private-beta-readiness.md`
- `docs/audits/private-beta-goal-progress.md`

Evidence reconciled:

- validators and read-only helpers from the current commit range:
  `7bd34abd`, `5a117446`, `01d21fe1`, `a45c5cdd`, `25d2ca77`,
  `7d766ce0`;
- route classification tests from `b013b8c1`;
- advisory-only provider/quota boundaries from `8e869811`,
  `650cca57`, and `docs/audits/quota-reserve-release-operator-evidence-checklist.md`;
- no-send notification tests from `8e8c2448`;
- async durability NO-GO tests from `2097e637`;
- storage/restore evidence tooling from `a45c5cdd`,
  `scripts/restore_pitr_operator_evidence_check.py`, and
  `scripts/isolated_pg_restore_smoke.py`.

Validation:

- `git diff --check` passed with no output;
- `./scripts/release_secret_scan.sh --local-only` passed with no
  high-confidence secret patterns;
- backend/frontend tests not required for docs-only slice.

Decision:

- Private-beta candidate review may use this report as an evidence index.
- Public launch remains **NO-GO**.

## Surface Review Queue

Safe candidate fixes to inspect next:

1. Admin/operator private-beta labels:
   - likely files: `apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx`,
     `apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx`,
     `apps/dsa-web/src/pages/AdminNotificationsPage.tsx`,
     `apps/dsa-web/src/pages/AdminEvidenceWorkflowPage.tsx`,
     `apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx`;
   - safe change type: copy/tests only, using existing display layers;
   - risk: accidental implication that dry-run/advisory evidence is live
     enforcement;
   - validation: affected frontend tests plus typecheck/build if changed.

2. Consumer-facing diagnostic leakage review:
   - likely files: scanner, market overview, portfolio, backtest, and alert
     surface components/tests;
   - safe change type: copy/sanitized label display only;
   - risk: exposing raw reason codes, diagnostics, stack traces, provider fields,
     or advice-like language;
   - validation: affected frontend tests plus bounded route smoke if changed.

## Slice 2: Align Provider Circuit Safety Labels

Status: validated.

Files:

- `apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx`
- `apps/dsa-web/src/pages/__tests__/AdminProviderCircuitDiagnosticsPage.test.tsx`
- `docs/audits/private-beta-readiness.md`
- `docs/audits/private-beta-goal-progress.md`

Safe change:

- Reworded provider circuit diagnostics so private-beta admins see
  advisory-only/read-only provider readiness signals instead of wording that
  implies active provider blocking.
- Added explicit `不执行 provider blocking` and no fallback/MarketCache behavior
  change language.
- Kept diagnostics collapsed and secret/raw-provider assertions intact.

Validation:

- `npm run test -- AdminProviderCircuitDiagnosticsPage.test.tsx` passed: 1 file,
  8 tests.
- `npm run typecheck` passed.
- `npm run build` passed with the existing Vite chunk-size warning.
- `npm run test:e2e -- e2e/no-secret-critical-surface.smoke.spec.ts -g "provider diagnostics uses mocked read-only APIs without raw provider detail leakage"` passed.

Decision:

- This fix is safe for private beta because it is copy/test-only on an existing
  admin surface.
- It does not enable provider runtime enforcement, provider blocking, provider
  order/fallback/cache changes, public launch, or any external calls.

## Approval-Required Follow-Ups

These are not implemented in this goal unless explicitly approved:

| Follow-up | Likely files | Risk | Exact approval needed | Validation |
| --- | --- | --- | --- | --- |
| Live quota route enforcement | `api/v1/endpoints/analysis.py`, quota service, cost ledger tests. | Real request blocking/reservation consume. | Approve live quota enforcement and reservation consume/blocking pilot. | Focused API/service tests and staging pilot evidence. |
| Provider runtime enforcement | Provider adapters/circuit services/admin provider tests. | Runtime provider blocking or fallback/cache behavior change. | Approve provider runtime enforcement and provider blocking pilot. | Provider tests and staging degraded evidence. |
| Global MFA/RBAC hardening | Auth/session/RBAC dependencies and admin gates. | Admin lockout or compatibility break. | Approve global MFA enforcement and RBAC fallback removal. | Auth/RBAC route matrix and browser smoke. |
| DB restore/cleanup/retention execution | DB/operator scripts, retention services, evidence artifacts. | Destructive or environment-changing DB operations. | Approve isolated restore/PITR execution and retention cleanup scope. | Real isolated PostgreSQL evidence and retention dry-run reports. |
| External notification sending | Notification services/channels/operator evidence. | Real outbound delivery. | Approve recipient/channel ownership and delivery rehearsal. | No-send tests plus approved rehearsal evidence. |
| Public launch | Launch evidence pack, CI, staging, operator approvals. | Public exposure. | Manual public release approval after blockers close. | Full release-candidate gate. |

## Checkpoints

- Slice 1 commit: `aa22766c checkpoint(private-beta): reconcile readiness evidence`.
- Slice 1 push: pushed to `origin/codex/goal-private-beta-candidate`.
- Slice 2 commit: pending.
- Slice 2 push: pending.
