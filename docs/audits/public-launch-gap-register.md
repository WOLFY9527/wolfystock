# Public Launch Gap Register

Date: 2026-05-07
Branch checked: `main`
Mode: docs-only public-launch consolidation. No runtime code, tests, schema,
frontend, provider config, Options, auth, Data Pipeline, cost/quota, or DB
behavior was changed.

## Source Documents

- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/audits/deployment-readiness-checklist.md`
- `docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md`
- `docs/audits/cost-system-final-qa-matrix.md`
- `docs/audits/ws2-multi-instance-smoke-test-design.md`
- `docs/audits/security-admin-mfa-backend-foundation.md`
- Supplemental current audit context:
  `docs/audits/backtest-portfolio-public-safety-audit.md`,
  `docs/audits/data-pipeline-r2-progressive-enrichment.md`,
  `docs/audits/options-provider-adapter-contract.md`,
  `docs/audits/ws2-provider-quota-circuit-breaker-policy-design.md`.

## Launch Verdict

Current public multi-user launch verdict: **NO-GO**.

The launch blocker set is concentrated in security enforcement, production data
durability, multi-instance runtime proof, live quota/provider enforcement, and
financial-domain owner isolation. Existing foundations are useful, but several
surfaces remain observational, scaffolded, fixture-only, or single-process by
default.

## Gap Register

| Area | Owner | Gap | Severity | Current status | Blocker | Recommended next task | Runtime risk | Verification required |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Security | Security/Auth | MFA secret storage | P0 | MFA backend scaffold exists; production TOTP secret storage is not approved. | No encrypted or external secret-storage model for recoverable production TOTP verification. | Implement production MFA secret storage design with tests and rollback notes. | Admin MFA cannot be safely enforced; secret mishandling could expose auth factors. | Unit/API tests for enroll/verify/disable, redaction checks, storage recovery check, no raw secret leakage. |
| Security | Security/Auth | Recovery codes | P0 | Recovery-code envelope is documented as versioned/hash-only, but launch contract still needs end-to-end acceptance. | Public admin access needs display-once, rotation, single-use consumption, fallback login contract, and recovery policy evidence. | Add recovery-code login/session contract and acceptance tests for generation, rotation, consume-once, and denial states. | Admin lockout or weak fallback path during MFA rollout. | Auth API tests, replay/consume-once tests, redaction scan, rollback runbook. |
| Security | Security/Auth | MFA enforcement pilot | P0 | Login MFA enforcement is explicitly disabled. | No staged admin MFA-required login/session pilot with rollback evidence. | Run an admin MFA enforcement pilot behind an explicit flag on a narrow admin cohort. | Public admin exposure can rely only on password plus reauth controls. | Browser/API login flows for MFA required, recovery fallback, rollback, stale session handling, audit evidence. |
| Security/RBAC | Security/RBAC | Coarse fallback removal | P0 | Coarse admin compatibility fallback remains intentional. | Capability inventory, role assignments, audit policy, MFA/reauth, frontend fail-closed evidence, and rollback are not complete. | Start `RBAC R5 inventory report only`, then observe-mode fallback telemetry before any fail-closed patch. | Least-privilege admin model is not enforceable for broad public admin exposure. | Route/frontend inventory, fallback-only grant report, sanitized deny/allow audit, pilot rollback proof. |
| Security/RBAC | Security/RBAC + Admin UX | Role management UI | P1 | No role/capability assignment UI or operational workflow. | Admin grants/revokes cannot be safely governed after coarse fallback removal. | Design role-management UI/API governance and audit workflow; implement only after approval. | Manual DB/bootstrap role changes can create lockout or overbroad admin access. | Capability-gated UI/API tests, last-super-admin guard tests, role mutation audit and denial sanitization. |
| DB/deployment | Platform/DBA | Backup/restore drill | P0 | Backup/restore drill is missing. | Encrypted backup, PITR target, restore smoke, and rollback runbook are not exercised. | Create and run an isolated PostgreSQL backup/restore drill with synthetic data. | Data loss or untested recovery during launch incident. | Restore smoke, PITR target evidence, rollback decision point, owner-isolation smoke after restore. |
| DB/deployment | Platform/DBA | Retention tiers | P1 | Admin log cleanup exists; broader high-growth retention tiers remain missing. | Task progress, terminal task state, LLM usage, scanner/backtest artifacts, provider counters, guest/cache metadata, and future Options cache retention are undefined. | Design and pilot preview-first owner/domain-aware retention tiers. | Unbounded growth, privacy retention drift, expensive operations under public load. | Dry-run cleanup reports, domain retention matrix, owner-aware deletion checks, rollback notes. |
| DB/deployment | Platform/DBA | DB Index Batch B | P1 | Index Batch A is complete; broader owner/status/time/admin drilldown coverage remains. | Remaining public-scale read paths lack accepted index coverage. | Implement DB Index Batch B for broader owner/status/time/admin drilldown paths. | Slow queries and pool pressure under public multi-user use. | Query-plan evidence, targeted DB tests, before/after timing on synthetic data. |
| DB/deployment | Release owner | Final clean `ci_gate` | P0 | Release-candidate clean gate is still required. | Current task does not run `ci_gate`; launch needs a clean candidate worktree. | Run `./scripts/ci_gate.sh` on a clean release candidate after blockers are fixed. | Hidden regression reaches launch because docs-only checks do not exercise runtime. | Full clean `ci_gate` result, clean `git status --short`, release commit hash. |
| DB/deployment | Platform/Release | Staging smoke | P0 | Staging smoke is listed as a final go/no-go requirement. | HTTPS reverse proxy, synthetic users/data, no direct public backend `:8000`, and rollback checks are not proven together. | Execute staging public-readiness smoke with synthetic users and no live secrets. | Deployment can pass local checks but fail under ingress, proxy, auth, or owner routing. | Staging smoke report, ingress/port proof, health/readiness checks, owner isolation, no-secret scan. |
| WS2/multi-instance | Runtime/Platform | Smoke implementation | P0 | Smoke design exists; script/CI/staging implementation is not present. | No executable synthetic WS2 smoke proves API A submit, worker lease, API B read, durable polling, retry, and owner isolation. | Implement `scripts/ws2_multi_instance_smoke.py` using fake provider/LLM and disposable storage only. | Multi-instance deployment can lose task visibility or leak owner state. | Local SQLite smoke, disposable PostgreSQL smoke, CI synthetic smoke, PASS/FAIL table. |
| WS2/multi-instance | Runtime/Platform | Process-local SSE limitation | P0 | `AnalysisTaskQueue` and `/api/v1/analysis/tasks/stream` SSE remain process-local. | SSE must not be represented as cross-instance reliable until external replay/cutover exists. | Add readiness/docs/smoke warnings that durable polling is the multi-instance baseline. | Users may miss progress after load-balancer route switch or reconnect. | API A/B smoke showing SSE limitation and polling replay from durable progress. |
| WS2/multi-instance | Runtime/Platform | Worker deployment model | P1 | Synthetic worker prototype exists; no production queue/broker cutover is approved. | Worker lease, heartbeat, queue depth, crash recovery, and deployment topology are not accepted for public multi-instance use. | Design staging-only API A/B plus worker deployment model with rollback to single API process. | Task execution may duplicate, stall, or corrupt terminal state under worker failure. | Lease expiry recovery, stale-worker rejection, heartbeat/queue-depth readiness, rollback smoke. |
| Cost/quota | Cost/Quota | Live enforcement pilot | P0 | Quota dry-run/reservation helpers exist; live route-boundary enforcement is disabled. | No low-risk route has proven reserve/consume/release behavior behind a flag. | Pilot live quota enforcement on one low-risk route boundary with explicit rollback. | Public usage can run without hard spend caps. | Reservation lifecycle tests, would-block behavior, rollback flag, user/admin copy showing enforcement status. |
| Cost/quota | Cost/Quota + Admin UX | Budget alerts | P1 | Budget burn-down UI and alerting remain future work. | Users/admins lack warning thresholds before daily/monthly exhaustion. | Add budget warning thresholds and read-only alert surfaces before enforcing broadly. | Spend can approach limits without actionable notice. | Threshold tests, admin/user alert rendering, no raw provider/ledger metadata exposure. |
| Cost/quota | Finance/Ops | Provider invoice reconciliation | P1 | Ledger estimates exist; provider invoice/export reconciliation remains open. | Estimated cost is not billing-authoritative without tolerance, currency, and mismatch workflow. | Compare ledger estimates against provider invoices/exports and document reconciliation policy. | Budget decisions may be based on inaccurate internal estimates. | Reconciliation report, tolerance policy, currency handling, mismatch escalation workflow. |
| Provider reliability | Provider/Ops | Provider SLA/dashboard | P1 | Provider diagnostics APIs/storage exist; frontend/dashboard surfacing remains future work. | Operators lack a launch-ready provider SLA/degraded dashboard. | Build read-only provider reliability dashboard from bounded provider/circuit state. | Provider exhaustion or degraded state may be invisible until users fail. | Dashboard/API tests, staging degraded fixture, no raw URL/payload/credential exposure. |
| Provider reliability | Provider/Ops | Circuit enforcement pilot | P0 | Circuit dry-run observer exists; no runtime provider call site enforces policy. | No approved integration for provider ordering, fallback, retry, timeout, in-flight, sufficiency, or MarketCache behavior. | Pilot provider circuit enforcement on one low-risk route without changing global fallback semantics. | Provider outages or 429s can cascade through public traffic. | Synthetic timeout/429/403/5xx buckets, fallback cap evidence, rollback switch, readiness degraded state. |
| Provider reliability | Legal/Ops | Provider data licensing | P1 | Provider entitlement/freshness/licensing is not launch-accepted for all public surfaces. | Public use needs license/entitlement proof for provider data, especially delayed/live financial data. | Create provider data licensing and entitlement acceptance matrix by route and provider. | Legal/commercial exposure or misleading data availability claims. | Provider-by-route licensing evidence, entitlement checks, user disclosure review. |
| Options | Options/Data | Real provider adapter | P1 | Options Lab is fixture-only; known live providers are disabled. | No real adapter proves entitlement, chain coverage, bid/ask, IV, Greeks, multiplier, symbology, and freshness. | Implement a mocked-provider-first real adapter contract pilot; live credentials only after approval. | Fixture analysis could be mistaken for production-grade Options decisioning. | Mocked adapter tests, data-quality downgrade tests, no raw payload/credential exposure. |
| Options | Options/Data | Live provider pilot | P1 | Public production Options decisioning is NO-GO on live data. | No staged live provider evidence for freshness, coverage, delayed data caps, and provider gaps. | Run a staged live Options provider pilot after adapter and entitlement approval. | Live Options outputs may be stale, incomplete, or overconfident. | Staging evidence for entitlement, as-of/freshness, IV/Greeks/OI coverage, conservative UI labels. |
| Options | Product/Safety | Broker/order explicitly out of scope | P0 | No live broker/order path exists and should not be added without separate safety review. | Public launch must preserve read-only, analysis-only Options posture. | Add explicit launch checklist item proving no broker/order/portfolio mutation path was introduced. | Accidental trade/order affordance creates financial and compliance risk. | Route/UI/API scan for order verbs, broker calls, portfolio mutation, no-advice wording. |
| Data Pipeline | Data Pipeline | Late async enrichment merge | P1 | R2 metadata exists; late async merge after persisted report is not implemented. | No safe owner-scoped durable merge path for optional enrichment after report completion. | Design and implement late async enrichment metadata-only merge path with durable progress. | Reports can appear complete while optional enrichment silently arrives or fails later. | Owner-scoped progress tests, metadata-only update tests, no recalculation without approval, sanitized reason codes. |
| Data Pipeline | Data/Provider Ops | Provider health dashboard | P1 | Provider health is visible in pieces but not as a public-readiness dashboard. | Data Pipeline depends on provider health without launch-ready degraded visibility. | Extend provider health/readiness dashboard for enrichment source health and stale/degraded states. | Optional enrichment failures can be misread as complete data quality. | Staging degraded fixtures, dashboard tests, bounded reason codes, no raw provider data. |
| Portfolio/backtest | Backtest + Portfolio | Public safety regressions | P0 | Public safety audit is NO-GO until pre-public tests pass. | Missing deterministic backtest fixtures, lookahead/assumption tests, portfolio accounting invariants, mutation guards, and export isolation evidence. | Add focused backtest and portfolio public-safety regression suites. | Financial analysis/accounting errors can be exposed to public users. | Golden fixtures, accounting invariant tests, mutation guard tests, export/readback integrity. |
| Portfolio/backtest | Security/Data ownership | Owner isolation | P0 | Owner-scoped foundations exist, but broad endpoint-by-endpoint proof is required. | Backtest run ids, portfolio account ids, imports, broker connections, exports, and admin reads need cross-owner denial evidence. | Add portfolio/backtest owner-isolation smoke across list/detail/export/mutate/admin read paths. | Cross-user financial data leakage. | Owner A/B authenticated tests, non-disclosing 404 behavior, admin capability gates, cache/export isolation. |
| Portfolio/backtest | Broker/Security | Broker credential redaction audit | P0 | Guardrails prohibit credential exposure; public audit remains required. | Broker connection APIs, logs, admin views, sync/import failures, and exports need redaction proof. | Audit broker credential redaction with docs/tests first; fix only confirmed leaks in a separate scoped task. | Raw broker credentials, tokens, sessions, or account secrets could leak. | API/log/admin/browser/export redaction scan, synthetic secret fixtures only, no production credential inspection. |

## Counts

- P0: 14
- P1: 13
- P2: 0

## Highest-Risk Blockers

- Admin MFA is not enforceable until production secret storage, recovery-code
  acceptance, and a staged enforcement pilot are complete.
- Public multi-instance deployment is blocked by process-local SSE semantics and
  the absence of executable WS2 smoke evidence.
- Public data durability is blocked by the missing backup/restore drill and
  missing release-candidate clean gate.
- Public financial-domain exposure is blocked by portfolio/backtest owner
  isolation, deterministic regression, accounting invariant, and broker
  redaction evidence.
- Public scale is blocked by observational-only cost/quota and provider circuit
  behavior until low-risk enforcement pilots and rollback evidence exist.

## Recommended Next Implementation Tasks

1. `Task: Security MFA production storage and recovery-code acceptance`
   Implement production TOTP secret storage, recovery-code login/session
   acceptance, redaction tests, and rollback notes without enabling broad MFA
   enforcement.
2. `Task: RBAC R5 inventory report only`
   Produce route/frontend/admin capability inventory and fallback dependence
   report before any fallback removal.
3. `Task: WS2 synthetic multi-instance smoke implementation`
   Add fake-provider/fake-LLM smoke for API A/B durable polling, worker lease
   recovery, owner isolation, and process-local SSE warnings.
4. `Task: PostgreSQL backup restore drill`
   Exercise encrypted backup/restore and rollback smoke in an isolated
   environment with synthetic data.
5. `Task: Public safety regression suite for portfolio and backtest`
   Add deterministic backtest fixtures, portfolio accounting invariants,
   owner-isolation tests, mutation guards, export isolation, and broker
   redaction checks.
6. `Task: Cost and provider low-risk enforcement pilots`
   Pilot one live quota boundary and one provider circuit enforcement boundary
   behind explicit rollback switches, with staging evidence and safe labels.

## Validation Plan

Required docs-only validation for this register:

```bash
git diff -- docs/audits/public-launch-gap-register.md docs/CHANGELOG.md
git diff --check -- docs/audits/public-launch-gap-register.md docs/CHANGELOG.md
```

`docs/CHANGELOG.md` was already dirty before this task, so this pass
intentionally does not modify it. No `ci_gate` is required for this docs-only
register.
