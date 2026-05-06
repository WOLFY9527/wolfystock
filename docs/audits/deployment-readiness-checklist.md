# Public Multi-user Deployment Readiness Checklist

Date: 2026-05-07
Branch checked: `main`
Mode: docs-only readiness consolidation. No runtime code, tests, schema,
frontend, providers, Options, Data Pipeline, cost/quota, or auth behavior was
changed.

## 1. Executive summary

Current public multi-user deployment verdict: **NO-GO**.

WolfyStock has several important foundations in place: stronger password KDF
storage, recent admin reauth source plus a narrow pilot, admin MFA backend
scaffold, capability-based RBAC helpers and migrated route families, durable
task/progress state, synthetic worker prototype, cost ledger foundations,
provider circuit storage/diagnostics/dry-run observation, DB index Batch A, and
fixture-backed Options/Data Pipeline improvements.

The system is still not ready for broad public multi-user exposure because the
remaining blockers are operational and safety-critical:

- MFA cannot be enforced until production TOTP secret storage, recovery codes,
  and a staged enforcement pilot exist.
- RBAC still carries coarse admin compatibility fallback and needs remaining
  route-family migration/governance before relying on least privilege.
- WS2 still needs staging multi-instance smoke evidence; process-local SSE is
  not cross-instance reliable.
- Cost/quota remains mostly observational and dry-run; live budget enforcement
  is not enabled.
- Provider circuits are visible in storage/API diagnostics, but runtime provider
  fallback/order/enforcement behavior has not changed.
- DB readiness still lacks backup/restore drills and full retention tiers for
  high-growth domains.
- Options Lab remains analysis-only with fixture/synthetic data; no real
  provider adapter or broker/order path exists.
- Data Pipeline R2 progressive enrichment is not a late async merge path yet.

## 2. Security gates

Status:

- [x] Password KDF upgrade foundation landed.
- [x] New password writes use versioned stronger PBKDF2-HMAC-SHA256 with
  600,000 iterations while preserving legacy hash verification.
- [x] Successful login, admin password unlock, settings current-password
  verification, and `POST /api/v1/auth/reauth` opportunistically upgrade
  recognized legacy hashes.
- [x] Recent admin reauth source exists.
- [x] Recent reauth is wired to the narrow admin user-security write pilot.
- [x] Admin MFA backend foundation exists.
- [x] MFA login enforcement is explicitly disabled.

Public deployment blockers:

- [ ] Approve and implement production encrypted or external secret storage for
  TOTP secrets.
- [ ] Add recovery code generation, display-once handling, hashing, and
  verification.
- [ ] Define and test the MFA-required login/session contract.
- [ ] Run an admin MFA enforcement pilot with rollback plan before requiring it
  for public admin access.
- [ ] Expand recent reauth coverage beyond the current pilot for other sensitive
  admin writes.
- [ ] Define audit fail-closed policy for security-sensitive events.

Go/no-go:

- **NO-GO** for public multi-user deployment until MFA secret storage, recovery
  codes, and enforcement pilot evidence are complete.

## 3. RBAC gates

Status:

- [x] Phase R1 compatibility/capability metadata exists.
- [x] Capability helpers and dependencies exist for route migration.
- [x] Migrated route families include admin user-security writes, admin
  portfolio read projections, admin logs, system config/provider probes, and
  notifications.
- [x] Frontend admin gates fail closed when capability fields are missing.
- [x] Auth payloads expose bounded capability summaries and convenience flags,
  not password/session/role internals.

Remaining gaps:

- [ ] Coarse admin compatibility fallback remains for existing/legacy admin
  users.
- [ ] Adjacent non-migrated admin surfaces still use coarse `require_admin_user`
  style gates.
- [ ] Role management UI and capability mutation governance are absent.
- [ ] R5 coarse fallback removal remains future work.
- [ ] Sensitive route audit/reauth/MFA policy needs to be applied consistently
  before treating capability RBAC as production least privilege.

Go/no-go:

- **NO-GO** for broad public admin exposure until coarse fallback removal or a
  written production exception is approved with compensating controls.

## 4. WS2 / task runtime gates

Status:

- [x] Durable task state foundation exists through `durable_task_states`.
- [x] Durable progress/event rows exist through
  `durable_task_progress_events`.
- [x] Owner-scoped durable status and polling fallback exist.
- [x] Synthetic worker prototype can claim/lease fixture-backed tasks, write
  progress, retry bounded transient failures, and complete/fail safely.
- [x] Current process-local `AnalysisTaskQueue` and SSE remain the default.

Remaining blockers:

- [ ] `/api/v1/analysis/tasks/stream` SSE is process-local and must not be
  treated as cross-instance reliable.
- [ ] Current public-safe deployment assumption is still single API process, or
  sticky routing with accepted task visibility limits.
- [ ] Staging multi-instance smoke is required before public multi-user launch.
- [ ] Smoke must prove API A submit, worker lease, API B durable read, polling
  replay, owner isolation, lease expiry recovery, retry/failure safety, and
  sanitized degraded readiness.
- [ ] External SSE replay/cutover remains future work.
- [ ] No production queue/broker cutover has been approved.

Go/no-go:

- **NO-GO** for multi-instance public deployment until the WS2 multi-instance
  smoke passes against a staging topology with synthetic data.

## 5. Cost / quota gates

Status:

- [x] LLM pricing policy foundation exists.
- [x] LLM cost ledger foundation exists.
- [x] Owner/guest context now propagates through major authenticated and guest
  LLM usage paths.
- [x] Admin read-only ledger summary exists.
- [x] Admin quota dry-run endpoint exists.
- [x] Quota reservation/reconciliation helpers exist for synthetic or explicit
  call sites.

Remaining blockers:

- [ ] Live route-boundary quota enforcement is not enabled.
- [ ] Ledger writes remain observational and best-effort; failures must not
  change user-visible LLM behavior.
- [ ] Some legacy/system usage can still write null-owner rows for backward
  compatibility.
- [ ] Budget burn-down UI, policy editing, enforcement pilot, and
  retention/aggregation policy remain future work.
- [ ] Provider quota buckets are not yet live enforcement.

Go/no-go:

- **NO-GO** for unrestricted public usage until quotas have a staged enforcement
  pilot, admin visibility, rollback plan, and owner/guest accounting acceptance.

## 6. Provider reliability gates

Status:

- [x] Provider circuit/quota storage foundation exists.
- [x] Read-only admin diagnostics API exists for circuits, events, quota
  windows, and probe events.
- [x] Provider circuit dry-run observer exists for synthetic bounded observation
  buckets.
- [x] Diagnostics responses omit raw provider payloads, URLs/query strings,
  credentials, cookies, raw session ids, exception text, stack traces, and
  internal storage details.

Remaining blockers:

- [ ] No runtime provider call site is integrated for enforcement.
- [ ] No provider ordering, fallback, retry, timeout, in-flight, sufficiency, or
  MarketCache behavior change has landed.
- [ ] Frontend provider circuit dashboard surfacing remains future work.
- [ ] Provider circuit enforcement pilot remains separately required.
- [ ] Diagnostics/counters must be validated in staging without live credential
  leakage before launch.

Go/no-go:

- **NO-GO** for public scale until provider exhaustion behavior is measured in
  staging and an approved degraded/enforcement policy exists.

## 7. DB readiness gates

Status:

- [x] Index Batch A is complete for the first production-critical read paths.
- [x] Current DB audit recognizes persisted users/sessions, RBAC metadata,
  owner-scoped analysis history, durable task state, execution logs,
  scanner/backtest tables, portfolio tables, cost observability, and PostgreSQL
  coexistence/shadow stores.
- [x] Admin log retention/capacity cleanup exists with dry-run behavior and
  storage summary.

Remaining blockers:

- [ ] Index Batch B remains for broader owner/status/time/admin drilldown paths.
- [ ] Backup/restore drill is missing.
- [ ] Encrypted backup, PITR targets, restore smoke, and rollback runbook must
  be documented and exercised before public onboarding.
- [ ] Retention tiers are missing for task progress, terminal task state, LLM
  usage, scanner/backtest artifacts, provider counters, guest/cache metadata,
  and future Options cache rows.
- [ ] Retention cleanup must be preview-first and owner/domain-aware.
- [ ] Public production should treat PostgreSQL as the durable multi-user
  baseline; SQLite remains local/dev/compatibility posture.

Go/no-go:

- **NO-GO** for broad public multi-user deployment until backup/restore drill,
  retention tiers, and remaining index coverage are accepted.

## 8. Options gates

Status:

- [x] Options Lab is read-only and analysis-only.
- [x] Fixture-backed option chain APIs and UI exist.
- [x] Decision Engine R1 exists for trade-quality analysis using normalized
  option-chain and strategy comparison data.
- [x] Decision Engine R2 exists for IV Rank/Percentile, Expected Move, and
  strategy optimizer outputs under conservative data-quality caps.
- [x] Current UI avoids order placement, broker execution, guaranteed-return,
  and personalized-advice posture.

Remaining blockers:

- [ ] Real provider adapter is still needed before production-grade Options
  decisions.
- [ ] Provider entitlement, freshness, bid/ask, volume/OI, IV, Greeks,
  multiplier, and symbology coverage must be proven.
- [ ] Fixture/synthetic/fallback/delayed data must remain capped and must not
  output tradeable recommendations.
- [ ] No live broker/order path exists and none should be added without a
  separate safety review.

Go/no-go:

- **NO-GO** for public production Options decisioning on live data until a real
  provider adapter and staged provider evidence exist. **GO** only for clearly
  labeled fixture/demo analysis.

## 9. Data Pipeline gates

Status:

- [x] Data Pipeline R1 fast decision quality path is complete.
- [x] Fast decision usability depends on required/important data through
  `requiredAvailable`, `dataQualityTier`, and `confidenceCap`.
- [x] Data Pipeline R2 progressive enrichment metadata exists for optional
  `news`, `sentiment`, and `detailed_fundamentals`.
- [x] Optional enrichment failures/timeouts remain non-blocking and use
  sanitized reason codes.

Remaining blockers:

- [ ] R2 is not a completed late async merge path after report persistence.
- [ ] Future async enrichment must write owner-scoped durable progress or report
  metadata rows.
- [ ] Future async enrichment must update only enrichment metadata unless a
  separate reviewed recalculation path exists.
- [ ] Durable polling/SSE progress should come from durable progress state, not
  process-local futures, before multi-instance public use.

Go/no-go:

- **NO-GO** for claiming complete progressive enrichment at public scale until
  late async update/merge behavior has staging evidence.

## 10. Final go/no-go checklist

The following must all be true before public multi-user deployment:

- [ ] `./scripts/ci_gate.sh` is clean on the release candidate.
- [ ] `git status --short` is clean before tagging/deploying.
- [ ] Staging smoke passes through HTTPS reverse proxy on synthetic users/data.
- [ ] WS2 multi-instance smoke passes or deployment is explicitly constrained to
  single API process with documented SSE/task limitations.
- [ ] Backend `:8000` is not directly exposed to the public internet.
- [ ] Public ingress exposes only 80/443, redirects HTTP to HTTPS, and forwards
  to a private/local backend port.
- [ ] Production `.env` uses `APP_ENV=production`, `ADMIN_AUTH_ENABLED=true`,
  explicit CORS/CSRF origins, and trusted proxy settings only behind a trusted
  proxy.
- [ ] Secrets audit confirms no real API keys, provider credentials, cookies,
  session ids, broker credentials, webhook URLs, password hashes, raw prompts,
  raw provider payloads, or stack traces are present in logs, admin diagnostics,
  readiness output, browser DOM, or docs.
- [ ] MFA enforcement prerequisites are complete or public admin access is
  blocked behind a documented compensating control.
- [ ] Backup/restore drill passes in an isolated environment.
- [ ] Rollback plan is written, including last-good commit/image, DB restore
  decision point, health checks, and owner-isolation smoke.
- [ ] Retention dry-run reports exist for high-growth domains.
- [ ] Cost/quota enforcement status is explicitly labeled in user/admin-facing
  docs and UI so observability is not mistaken for a spending cap.

Final launch verdict:

- **NO-GO** until every item in this section is checked or explicitly accepted
  as a documented production exception.

## 11. Validation for this document

Required docs-only validation:

```bash
git diff -- docs/audits/deployment-readiness-checklist.md docs/CHANGELOG.md
git diff --check -- docs/audits/deployment-readiness-checklist.md docs/CHANGELOG.md
```

No `ci_gate` is required for this docs-only checklist refresh.
