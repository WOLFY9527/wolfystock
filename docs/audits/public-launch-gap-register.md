# Public Launch Gap Register

Date: 2026-05-08
Branch checked: `main`
Mode: docs-only public-launch consolidation. No runtime code, tests, schema,
frontend, provider config, market-rotation source/tests, Options, auth, Data
Pipeline, cost/quota, or DB behavior was changed.

## Source Documents

- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/audits/deployment-readiness-checklist.md`
- `docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md`
- `docs/audits/cost-system-final-qa-matrix.md`
- `docs/audits/ws2-multi-instance-smoke-test-design.md`
- `docs/audits/archive/security-admin-mfa-backend-foundation.md`
- `docs/audits/public-launch-readiness-master.md`
- `docs/audits/launch-acceptance-evidence-pack.md`
- `docs/audits/incident-response-audit-evidence-pack.md`
- `docs/audits/operator-evidence-real-runbook.md`
- `docs/audits/operator-evidence-dry-run-handoff.md`
- `docs/audits/operator-evidence-redaction-checklist.md`
- `docs/audits/public-launch-blocker-burndown.md`
- `docs/audits/data-quality-user-disclosure-policy.md`
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

## Operator Evidence Pack

`scripts/launch_acceptance_evidence.py` now validates a sanitized launch
acceptance evidence JSON contract for release review. It covers the operator
evidence required for admin-only MFA pilot acceptance, unsupported/global MFA
rollout NO-GO, break-glass default-off, RBAC fallback disable switch with
complete route inventory and fail-closed payload proof, provider credential
staging dry-run, provider staging probe artifacts, provider live probe opt-in
and bounded timeout, provider circuit controlled enforcement, quota pilot
acceptance, budget-alert dry-run acceptance, real isolated PostgreSQL
restore/PITR, staging ingress smoke, public API/frontend no-secret public
safety, supply-chain dependency/build artifact safety, incident-response/audit
evidence, WS2/SSE topology limitation with durable polling fallback, admin log
retention/capacity rehearsal, portfolio/backtest export and browser proof,
notification delivery rehearsal, user data privacy/export/deletion rehearsal,
market data freshness/fallback evidence, AI report/guest-preview safety,
Options derivatives safety, API abuse/request-safety evidence, and final clean
full `ci_gate`.

`scripts/incident_response_evidence.py` adds a companion incident-response
audit evidence contract for sanitized admin-critical actions, preview-first
cleanup, provider/notification/release failure evidence, and local
no-secret/no-network generation.

The pack is evidence-only. It does not call external services, read production
secrets, read production data paths, or change runtime behavior. Missing or
unsafe evidence keeps the summary at **NO-GO**. Even when all categories are
accepted, the checker returns `GO-REVIEW-REQUIRED` with `releaseApproved=false`;
manual release approval is still required.

Domain-local offline validators/templates for provider, restore/PITR, security
MFA/RBAC, quota/budget, staging ingress, WS2/SSE, config snapshot, and manual
release review-record evidence are now consolidated into
`docs/audits/operator-evidence-real-runbook.md`. These validators only check
sanitized operator artifacts for review. Actual launch review still requires
real operator-produced artifacts for the target environment, and final approval
remains manual.

`scripts/operator_evidence_bundle_check.py` can aggregate already-sanitized
domain validator summaries for reviewer convenience, but it is a support tool
only and does not replace any real artifact. The latest launch acceptance
matrix treats WS2/SSE decision evidence, config snapshot evidence, and manual
review-record evidence as required review items while keeping
`releaseApproved=false`; accepted fixture evidence can reach only
`GO-REVIEW-REQUIRED`.

The end-to-end offline operator workflow tooling is available for release
review support:

- `scripts/operator_evidence_template_pack.py` can generate sanitized blank
  templates for operators to fill manually.
- Category validators can check filled sanitized artifacts without runtime
  calls.
- `scripts/operator_evidence_manifest_check.py` can create and verify checksum
  metadata for the sanitized artifact files.
- `scripts/operator_evidence_bundle_check.py` can aggregate validator statuses.
- `scripts/release_review_report_render.py` can render a bounded Markdown
  review report from sanitized summaries.

This tooling availability does not mark any target-environment operator
artifact complete by itself. Missing required operator artifacts remain
**NO-GO**, and the current public launch posture remains review-gated.

## Non-blocking Product Capabilities

Market Rotation Radar is tracked as a read-only product capability, not as a
launch blocker. Its API/UI surface and no-advice/fallback-stale labeling are
product evidence, but they do not satisfy provider entitlement, freshness,
quota, security, owner-isolation, or deployment acceptance requirements.

## Gap Register

| Area | Owner | Gap | Severity | Current status | Blocker | Recommended next task | Runtime risk | Verification required |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Security | Security/Auth | MFA secret storage | P0 | Encrypted MFA secret storage foundation exists for non-test TOTP refs, but production key custody/rotation/recovery operations are not launch-accepted. | Production operators still need an accepted key-management and recovery model before broad MFA enforcement. | Complete production MFA key custody/rotation/recovery acceptance with tests and rollback notes. | Admin MFA cannot be safely enforced globally if encrypted secret operations are not recoverable and governed. | Unit/API tests for enroll/verify/disable, redaction checks, storage recovery check, no raw secret leakage, operator key-rotation evidence. |
| Security | Security/Auth | Recovery codes | P0 | Recovery-code state is part of the disabled-by-default pilot guard, but launch contract still needs end-to-end acceptance. | Public admin access needs display-once, rotation, single-use consumption, fallback login contract, and recovery policy evidence. | Add/accept recovery-code login/session contract and acceptance tests for generation, rotation, consume-once, and denial states. | Admin lockout or weak fallback path during MFA rollout. | Auth API tests, replay/consume-once tests, redaction scan, rollback runbook. |
| Security | Security/Auth | MFA enforcement pilot | P0 | Disabled-by-default admin MFA enforcement pilot contract and guard exist; `scripts/security_operator_acceptance_check.py` and the security operator guide provide an offline sanitized artifact validator/template for MFA/RBAC acceptance. Global enforcement remains off. | A real staged admin MFA-required login/session pilot has not been accepted by operators. | Run an admin MFA enforcement pilot behind an explicit flag on a narrow admin cohort and attach the sanitized operator artifact. | Public admin exposure can rely only on password plus reauth controls unless the pilot is accepted. | Browser/API login flows for MFA required, recovery fallback, rollback, stale session handling, audit evidence, no secret leakage. |
| Security/RBAC | Security/RBAC | Coarse fallback removal | P0 | Coarse admin compatibility fallback remains intentional; `scripts/security_operator_acceptance_check.py` can validate a sanitized MFA/RBAC acceptance artifact with route inventory, explicit capability payloads, fail-closed proof, rollback, and unchanged runtime defaults. | The fallback remains enabled by default and compatibility code remains present until operators apply the guarded disable switch. | Apply `WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED=false` only through the guarded operator path after route inventory stays complete; do not delete compatibility code. | Least-privilege admin model is not enforceable for broad public admin exposure until the switch is accepted and applied. | Route/frontend inventory, fallback-only grant report, sanitized deny/allow audit, pilot rollback proof. |
| Security/RBAC | Security/RBAC + Admin UX | Role management UI | P1 | No role/capability assignment UI or operational workflow. | Admin grants/revokes cannot be safely governed after coarse fallback removal. | Design role-management UI/API governance and audit workflow; implement only after approval. | Manual DB/bootstrap role changes can create lockout or overbroad admin access. | Capability-gated UI/API tests, last-super-admin guard tests, role mutation audit and denial sanitization. |
| DB/deployment | Platform/DBA | Backup/restore drill | P0 | Local dry-run preflight and `scripts/restore_pitr_operator_evidence_check.py` now provide offline validation/templates for sanitized real restore/PITR operator artifacts; real isolated PostgreSQL restore execution remains missing. | Encrypted backup, PITR execution, restore smoke, and rollback runbook are not exercised. | Create and run an isolated PostgreSQL backup/restore drill with synthetic data after the preflight passes with fresh synthetic or sanitized metadata. | Data loss or untested recovery during launch incident. | Preflight output, restore smoke, PITR target evidence, rollback decision point, owner-isolation smoke after restore. |
| DB/deployment | Platform/DBA | Retention tiers | P1 | Admin log cleanup now has explicit `admin_logs_standard`, `admin_logs_minimum_protected`, and `admin_logs_storage_pressure` policy evidence with preview-first cleanup, minimum-retention safeguard, sanitized cleanup audit event, storage-size-unavailable fallback, redaction, and warning+ default-view coverage; broader high-growth retention tiers remain missing. | Task progress, terminal task state, LLM usage, scanner/backtest artifacts, provider counters, guest/cache metadata, and future Options cache retention are undefined. | Design and pilot preview-first owner/domain-aware retention tiers for the remaining non-admin-log domains. | Unbounded growth, privacy retention drift, expensive operations under public load. | Admin-log focused pytest evidence plus dry-run cleanup reports, broader domain retention matrix, owner-aware deletion checks, rollback notes. |
| DB/deployment | Platform/DBA | DB Index Batch B | P1 | Index Batch A is complete; broader owner/status/time/admin drilldown coverage remains. | Remaining public-scale read paths lack accepted index coverage. | Implement DB Index Batch B for broader owner/status/time/admin drilldown paths. | Slow queries and pool pressure under public multi-user use. | Query-plan evidence, targeted DB tests, before/after timing on synthetic data. |
| DB/deployment | Release owner | Final clean `ci_gate` | P0 | Release-candidate clean gate is still required. | Current task does not run `ci_gate`; launch needs a clean candidate worktree. | Run `./scripts/ci_gate.sh` on a clean release candidate after blockers are fixed. | Hidden regression reaches launch because docs-only checks do not exercise runtime. | Full clean `ci_gate` result, clean `git status --short`, release commit hash. |
| DB/deployment | Platform/Release | Staging smoke | P0 | A safe dry-run/live opt-in ingress preflight and `scripts/staging_ingress_operator_evidence_check.py` now provide offline validation/templates for sanitized staging ingress operator artifacts. Real HTTPS staging evidence is still not accepted. | HTTPS reverse proxy, synthetic users/data, no direct public backend `:8000`, owner isolation, and rollback checks are not proven together in staging. | Run `WOLFYSTOCK_STAGING_INGRESS_SMOKE=1 python3 scripts/staging_ingress_smoke.py --base-url "$STAGING_INGRESS_BASE_URL"` against synthetic staging, attach JSON evidence, and validate the sanitized operator artifact offline. | Deployment can pass local checks but fail under ingress, proxy, auth, or owner routing. | Staging smoke report, ingress/port proof, health/readiness checks, protected admin 401/403, owner isolation, no-secret scan. |
| DB/deployment | Release owner | Production config contract | P0 | A safe production config/secret contract preflight now exists for required launch flag names, explicit `ADMIN_AUTH_ENABLED=true`, MFA rollout mode, RBAC fallback disable evidence, provider credential presence states, quota mode, backup/PITR opt-in, and staging ingress opt-in. `scripts/config_snapshot_evidence_check.py` also validates sanitized config snapshot summaries offline with labels and presence states only. Neither helper reads raw `.env` values. | A real production config contract and config snapshot artifact have not been accepted, and raw secret values must not be attached to release evidence. Auth-disabled config remains local/dev-only and public **NO-GO**. | Run `python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>` and `python3 scripts/config_snapshot_evidence_check.py <sanitized-config-snapshot-evidence.json>` with names/presence states only, attach JSON evidence, and keep missing required config or missing/false `ADMIN_AUTH_ENABLED` as NO-GO. | Launch reviewers can otherwise confuse defaults, missing flags, auth-disabled local mode, and credential readiness with accepted production posture. | Stable JSON output, no secret values, explicit NO-GO on missing required config, no external calls, runtime defaults unchanged. |
| WS2/multi-instance | Runtime/Platform | Staging/CI smoke acceptance | P0 | Smoke design exists and repo-local offline smoke tooling is available through `scripts/ws2_multi_instance_smoke.py` for dry-run and disposable-SQLite synthetic preflight. It does not run staging calls, prove PostgreSQL API A/B topology, or mark target-environment evidence accepted. | No accepted staging/API A/B WS2 evidence proves API A submit, worker lease, API B durable read, durable polling replay, retry/failure safety, and owner isolation. | Run/extend WS2 smoke toward CI and staging acceptance using fake provider/LLM, synthetic users, disposable storage, and sanitized operator artifacts only. | Multi-instance deployment can lose task visibility or leak owner state if offline preflight is mistaken for target-environment proof. | Offline synthetic preflight output, disposable PostgreSQL smoke if implemented, CI synthetic smoke, accepted staging API A/B artifact, PASS/FAIL table, sanitized operator review. |
| WS2/multi-instance | Runtime/Platform | Process-local SSE limitation | P0 | `AnalysisTaskQueue` and `/api/v1/analysis/tasks/stream` SSE remain process-local. `scripts/ws2_sse_operator_decision_check.py` can validate a sanitized operator decision that records polling fallback, single-instance limitation, or external-broadcast-required posture. | SSE must not be represented as cross-instance reliable until external replay/cutover exists, and a real operator decision artifact is still required for launch review. | Attach validated WS2/SSE operator decision evidence, then add readiness/docs/smoke warnings that durable polling is the multi-instance baseline. | Users may miss progress after load-balancer route switch or reconnect. | API A/B smoke showing SSE limitation and polling replay from durable progress, plus the sanitized operator decision validator output. |
| WS2/multi-instance | Runtime/Platform | Worker deployment model | P1 | Synthetic worker prototype exists; no production queue/broker cutover is approved. | Worker lease, heartbeat, queue depth, crash recovery, and deployment topology are not accepted for public multi-instance use. | Design staging-only API A/B plus worker deployment model with rollback to single API process. | Task execution may duplicate, stall, or corrupt terminal state under worker failure. | Lease expiry recovery, stale-worker rejection, heartbeat/queue-depth readiness, rollback smoke. |
| Cost/quota | Cost/Quota | Live enforcement pilot | P0 | Quota dry-run/reservation helpers, pilot-readiness preflight, and `scripts/quota_operator_evidence_check.py` now provide offline validation/templates for sanitized quota/budget operator evidence; live route-boundary enforcement remains disabled. | No low-risk route has proven reserve/consume/release behavior behind a live enforcement flag. | Pilot live quota enforcement on one low-risk route boundary with explicit rollback and attach sanitized operator evidence. | Public usage can run without hard spend caps. | Reservation lifecycle tests, would-block behavior, rollback flag, user/admin copy showing enforcement status. |
| Cost/quota | Cost/Quota + Admin UX | Budget alerts | P1 | Budget burn-down UI and alerting remain future work; the quota/budget operator validator can now check sanitized dry-run/no-outbound evidence templates. | Users/admins lack warning thresholds before daily/monthly exhaustion. | Add budget warning thresholds and read-only alert surfaces before enforcing broadly, then attach sanitized operator evidence. | Spend can approach limits without actionable notice. | Threshold tests, admin/user alert rendering, no raw provider/ledger metadata exposure. |
| Cost/quota | Finance/Ops | Provider invoice reconciliation | P1 | Ledger estimates exist; provider invoice/export reconciliation remains open. | Estimated cost is not billing-authoritative without tolerance, currency, and mismatch workflow. | Compare ledger estimates against provider invoices/exports and document reconciliation policy. | Budget decisions may be based on inaccurate internal estimates. | Reconciliation report, tolerance policy, currency handling, mismatch escalation workflow. |
| Provider reliability | Provider/Ops | Provider SLA/dashboard | P1 | Provider SLA/readiness diagnostics APIs/storage and Launch Cockpit/admin provider surfaces exist as advisory operator visibility. | Missing launch-accepted provider runtime confidence: provider entitlement, staging degraded behavior, live circuit enforcement, provider order/fallback/cache behavior, and target-environment SLA evidence are not proven. | Accept target-environment provider SLA/degraded evidence from existing advisory surfaces and sanitized staging artifacts before any launch claim. | Advisory diagnostics can be mistaken for launch approval while provider exhaustion or degraded state remains unproven under public traffic. | Dashboard/API tests, staging degraded fixture, entitlement/freshness evidence, no raw URL/payload/credential exposure, explicit no-launch-approval wording. |
| Provider reliability | Provider/Ops | Circuit enforcement pilot | P0 | Circuit dry-run observer exists; no runtime provider call site enforces policy. | No approved integration for provider ordering, fallback, retry, timeout, in-flight, sufficiency, or MarketCache behavior. | Pilot provider circuit enforcement on one low-risk route without changing global fallback semantics. | Provider outages or 429s can cascade through public traffic. | Synthetic timeout/429/403/5xx buckets, fallback cap evidence, rollback switch, readiness degraded state. |
| Provider reliability | Legal/Ops | Provider data licensing | P1 | Provider credential staging, opt-in live-probe contracts, and `scripts/provider_operator_evidence_check.py` now provide offline validation/templates for sanitized provider operator artifacts, but entitlement/freshness/licensing is not launch-accepted for all public surfaces. | Public use needs license/entitlement proof for provider data, especially delayed/live financial data. | Create provider data licensing and entitlement acceptance matrix by route and provider, then attach only sanitized staging probe summaries. | Legal/commercial exposure or misleading data availability claims. | Provider-by-route licensing evidence, entitlement checks, user disclosure review, opt-in probe timeout/no-secret proof. |
| Options | Options/Data | Real provider adapter | P1 | Options Lab is fixture-only; known live providers are disabled. | No real adapter proves entitlement, chain coverage, bid/ask, IV, Greeks, multiplier, symbology, and freshness. | Implement a mocked-provider-first real adapter contract pilot; live credentials only after approval. | Fixture analysis could be mistaken for production-grade Options decisioning. | Mocked adapter tests, data-quality downgrade tests, no raw payload/credential exposure. |
| Options | Options/Data | Live provider pilot | P1 | Public production Options decisioning is NO-GO on live data. | No staged live provider evidence for freshness, coverage, delayed data caps, and provider gaps. | Run a staged live Options provider pilot after adapter and entitlement approval. | Live Options outputs may be stale, incomplete, or overconfident. | Staging evidence for entitlement, as-of/freshness, IV/Greeks/OI coverage, conservative UI labels. |
| Options | Product/Safety | Broker/order explicitly out of scope | P0 | No live broker/order path exists and should not be added without separate safety review. | Public launch must preserve read-only, analysis-only Options posture. | Add explicit launch checklist item proving no broker/order/portfolio mutation path was introduced. | Accidental trade/order affordance creates financial and compliance risk. | Route/UI/API scan for order verbs, broker calls, portfolio mutation, no-advice wording. |
| Data Pipeline | Data Pipeline | Late async enrichment merge | P1 | R2 metadata and fallback/stale disclosure regressions exist; late async merge after persisted report is not implemented. | No safe owner-scoped durable merge path for optional enrichment after report completion. | Design and implement late async enrichment metadata-only merge path with durable progress. | Reports can appear complete while optional enrichment silently arrives or fails later. | Owner-scoped progress tests, metadata-only update tests, no recalculation without approval, sanitized reason codes. |
| Data Pipeline | Data/Provider Ops | Provider health dashboard | P1 | Provider health is visible through advisory admin provider surfaces, but not as launch-accepted Data Pipeline provider confidence. | Data Pipeline still lacks target-environment degraded/freshness evidence for enrichment source health. | Reconcile enrichment provider health into the advisory admin surfaces and attach accepted staging degraded evidence before any launch claim. | Optional enrichment failures can be misread as complete data quality if advisory diagnostics are treated as launch proof. | Staging degraded fixtures, dashboard tests, bounded reason codes, no raw provider data, explicit advisory-only status. |
| Portfolio/backtest | Backtest + Portfolio | Public safety regressions | P0 | Focused public-safety evidence now covers backtest export no-advice wording, missing-data disclosure, support export discovery, and existing golden metric fixtures; public launch remains NO-GO until broader acceptance closes. | Remaining gaps include broader portfolio accounting invariants, route-wide mutation guards, and staged release-candidate evidence. | Continue with accounting invariant and mutation-guard suites without changing calculation formulas or accounting semantics. | Financial analysis/accounting errors can be exposed to public users. | Golden fixtures, accounting invariant tests, mutation guard tests, export/readback integrity. |
| Portfolio/backtest | Security/Data ownership | Owner isolation | P0 | Owner-scoped evidence now covers portfolio export-like user reads, import denial/idempotency, broker connection boundaries, and admin target-user redaction; broad staged owner-isolation smoke is still required. | Backtest run ids and route-wide portfolio/backtest list/detail/export/mutate paths still need accepted staging proof. | Add staged portfolio/backtest owner-isolation smoke across remaining ids and export endpoints. | Cross-user financial data leakage. | Owner A/B authenticated tests, non-disclosing 404 behavior, admin capability gates, cache/export isolation. |
| Portfolio/backtest | Broker/Security | Broker credential redaction audit | P0 | Synthetic broker/token/session redaction evidence now covers user broker-connection metadata and admin portfolio export-like surfaces, plus release secret-scan coverage; browser/log coverage remains incomplete. | Broker logs, browser-visible panels, sync/import failure surfaces, and release-candidate exports still need full redaction proof. | Complete broker redaction audit across API/log/admin/browser/export surfaces; fix only confirmed leaks in separate scoped tasks. | Raw broker credentials, tokens, sessions, or account secrets could leak. | API/log/admin/browser/export redaction scan, synthetic secret fixtures only, no production credential inspection. |

## Counts

- P0: 14
- P1: 13
- P2: 0

## Highest-Risk Blockers

- Admin MFA is not enforceable until production secret storage, recovery-code
  acceptance, and a staged enforcement pilot are complete.
- Public multi-instance deployment is blocked by process-local SSE semantics and
  the absence of accepted staging/target-environment WS2 multi-instance
  evidence; repo-local offline smoke tooling exists but does not close the
  launch gate.
- Public data durability is blocked by the missing backup/restore drill and
  missing release-candidate clean gate.
- Public financial-domain exposure still depends on remaining portfolio/backtest
  accounting invariant, mutation-guard, staged owner-isolation, and full broker
  redaction acceptance despite the focused evidence now in place.
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
3. `Task: WS2 staging/CI multi-instance smoke acceptance`
   Use the existing repo-local WS2 smoke preflight as the base for
   fake-provider/fake-LLM CI and staging evidence that proves API A/B durable
   polling, worker lease recovery, owner isolation, and process-local SSE
   warnings.
4. `Task: PostgreSQL backup restore drill`
   Exercise encrypted backup/restore and rollback smoke in an isolated
   environment with synthetic data.
5. `Task: Portfolio/backtest remaining public-safety acceptance`
   Add broader accounting invariants, route-wide mutation guards, staged
   owner-isolation smoke, and full broker redaction checks without changing
   portfolio accounting or backtest formulas.
6. `Task: Cost and provider low-risk enforcement pilots`
   Pilot one live quota boundary and one provider circuit enforcement boundary
   behind explicit rollback switches, with staging evidence and safe labels.

## Validation Plan

Required docs-only validation for this register:

```bash
git diff -- docs/audits/public-launch-gap-register.md docs/CHANGELOG.md
git diff --check -- docs/audits/public-launch-gap-register.md docs/CHANGELOG.md
```

No `ci_gate` is required for this docs-only register.
