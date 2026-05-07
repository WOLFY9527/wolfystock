# Public Multi-user Deployment Readiness Checklist

Date: 2026-05-08
Branch checked: `main`
Mode: deployment readiness preflight update. No runtime API behavior, schema,
frontend app code, providers, market-rotation source/tests, Options, Data
Pipeline, cost/quota, auth behavior, production deployment config, migrations,
or production data paths were changed. The launch acceptance evidence pack is
schema/checklist only and does not approve launch.

## 1. Executive summary

Current public multi-user deployment verdict: **NO-GO**.

WolfyStock has several important foundations in place: stronger password KDF
storage, recent admin reauth source plus a narrow pilot, admin MFA backend
scaffold with encrypted-secret and disabled-by-default enforcement pilot
guards, capability-based RBAC helpers and migrated route families, durable
task/progress state, synthetic worker prototype, cost ledger foundations,
quota enforcement pilot-readiness preflight, provider circuit
storage/diagnostics/dry-run observation, DB index Batch A, local backup/restore
dry-run preflight, secret-scan/admin harness coverage, and fixture-backed
Options/Data Pipeline improvements.

Market Rotation Radar is also present as a read-only product capability. It is
not a deployment blocker and does not close any launch gate by itself.

The system is still not ready for broad public multi-user exposure because the
remaining blockers are operational and safety-critical:

- MFA cannot be globally enforced until production key/recovery operations and
  staged pilot evidence are accepted; the current enforcement path remains
  disabled unless explicitly configured for a narrow admin pilot.
- RBAC still carries coarse admin compatibility fallback and needs remaining
  route-family migration/governance before relying on least privilege.
- WS2 still needs staging multi-instance smoke evidence; process-local SSE is
  not cross-instance reliable.
- Cost/quota remains mostly observational and dry-run; live budget enforcement
  is not enabled.
- Provider circuits are visible in storage/API diagnostics, but runtime provider
  fallback/order/enforcement behavior has not changed.
- DB readiness has a local dry-run backup/restore preflight and admin-log
  retention/storage policy evidence, but still lacks an isolated PostgreSQL
  restore/PITR drill and full retention tiers for non-log high-growth domains.
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
- [x] Encrypted MFA secret storage foundation exists for non-test TOTP refs.
- [x] Disabled-by-default admin MFA login enforcement pilot contract and guard
  exist.
- [x] MFA login enforcement remains explicitly disabled unless a narrow pilot
  flag is configured.
- [x] Release secret-scan and admin browser harness coverage have improved.

Public deployment blockers:

- [ ] Approve production key custody/rotation/recovery operations for encrypted
  TOTP secret storage.
- [ ] Accept recovery code generation, display-once handling, hashing,
  verification, and break-glass policy end to end.
- [ ] Define and test the global MFA-required login/session contract.
- [ ] Run and accept an admin MFA enforcement pilot with rollback plan before
  requiring it for public admin access.
- [ ] Expand recent reauth coverage beyond the current pilot for other sensitive
  admin writes.
- [ ] Define audit fail-closed policy for security-sensitive events.

Go/no-go:

- **NO-GO** for public multi-user deployment until MFA secret storage operations,
  recovery-code acceptance, and enforcement pilot evidence are complete.

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
- [x] Quota enforcement pilot-readiness preflight exists as advisory-only
  reporting with explicit owner scope, sanitized provider/model context, and
  invoice reconciliation marked non-enforcement-wired.

Remaining blockers:

- [ ] Live route-boundary quota enforcement is not enabled.
- [ ] Ledger writes remain observational and best-effort; failures must not
  change user-visible LLM behavior.
- [ ] Some legacy/system usage can still write null-owner rows for backward
  compatibility.
- [ ] Budget burn-down UI, policy editing, live enforcement pilot, and
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
- [x] Provider SLA/readiness diagnostics are present as bounded admin/provider
  evidence.
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
- [x] Local dry-run backup/restore/PITR drill preflight exists for simulated
  metadata, artifact presence, timestamp sanity, schema compatibility,
  PITR/WAL archive metadata, sanitized evidence output, and temp-only restore
  target isolation.
- [x] A sanitized real-drill evidence artifact contract exists and is validated
  only as externally supplied evidence; the checker does not execute restore
  commands by default.
- [x] Admin log retention tiers are explicit and test-backed:
  `admin_logs_standard`, `admin_logs_minimum_protected`, and
  `admin_logs_storage_pressure`.
- [x] Admin log cleanup is preview-first, preserves the minimum retention floor,
  emits sanitized cleanup audit events, and keeps storage-size-unavailable
  fallback safe.
- [x] Synthetic staging-ingress smoke preflight exists:
  `python3 scripts/staging_ingress_smoke.py --base-url <staging-ingress-base-url>`.
- [x] Ingress smoke is safe by default: without
  `WOLFYSTOCK_STAGING_INGRESS_SMOKE=1` it emits dry-run JSON evidence and does
  not open network sockets.
- [x] Ingress smoke covers `/api/health`, `/api/health/ready`,
  `/api/health/live`, unauthenticated `/api/v1/admin/users` fail-closed
  behavior, sensitive/debug payload patterns, sanitized timeout/action output,
  and attachable JSON evidence.
- [ ] Isolated PostgreSQL backup/restore execution is still missing.
- [ ] Real isolated PostgreSQL restore/PITR evidence is still pending until an
  accepted sanitized evidence artifact is supplied.
- [ ] Real HTTPS staging ingress smoke evidence is still missing; the new
  preflight must be run against a synthetic staging URL with explicit opt-in.
- [ ] Encrypted backup infrastructure, PITR execution, restore smoke, and
  rollback runbook must be documented and exercised before public onboarding.
- [ ] Retention tiers are still missing for task progress, terminal task state,
  LLM usage, scanner/backtest artifacts, provider counters, guest/cache
  metadata, and future Options cache rows.
- [ ] Non-admin-log retention cleanup must be preview-first and
  owner/domain-aware.
- [ ] Public production should treat PostgreSQL as the durable multi-user
  baseline; SQLite remains local/dev/compatibility posture.

Go/no-go:

- **NO-GO** for broad public multi-user deployment until backup/restore drill,
  broader high-growth retention tiers, and remaining index coverage are
  accepted.

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
- [x] Fallback/stale data-quality disclosure regressions exist and must remain
  visible near decision-like labels.

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
- [x] Dry-run/live opt-in ingress smoke preflight exists and is listed by
  `scripts/release_gate_summary.sh`.
- [x] Machine-checkable public launch evidence aggregation exists through
  `scripts/release_gate_summary.sh --go-no-go-json`; it reports foundation
  evidence and hard blockers while keeping the final status **NO-GO**.
- [x] Operator evidence-pack schema/checker exists through
  `python3 scripts/launch_acceptance_evidence.py --evidence <sanitized-launch-acceptance-evidence.json>`;
  it validates MFA, RBAC fallback, provider credential dry-run, provider circuit
  controlled enforcement, quota, real restore/PITR, staging ingress, public
  no-secret safety, supply-chain dependency/build artifact safety, and final
  clean gate categories without approving launch.
- [x] Production config/secret contract preflight exists through
  `python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>`;
  it consumes only synthetic or operator-sanitized flag names and secret
  presence states, emits stable JSON, and never prints secret values.
- [x] Incident-response audit evidence pack exists through
  `python3 scripts/incident_response_evidence.py --evidence <sanitized-incident-response-evidence.json>`;
  it validates sanitized admin-critical action evidence, preview-first cleanup,
  provider/notification/release failure evidence, and local no-secret/no-network
  generation without approving launch.
- [ ] Sanitized operator evidence pack is accepted for every hard blocker; the
  checker may move from **NO-GO** to `GO-REVIEW-REQUIRED`, but
  `releaseApproved` remains false until manual approval.
- [ ] Staging smoke passes through HTTPS reverse proxy on synthetic users/data.
- [ ] WS2 multi-instance smoke passes or deployment is explicitly constrained to
  single API process with documented SSE/task limitations.
- [ ] Backend `:8000` is not directly exposed to the public internet.
- [ ] Public ingress exposes only 80/443, redirects HTTP to HTTPS, and forwards
  to a private/local backend port.
- [ ] Production `.env` uses `APP_ENV=production`, `ADMIN_AUTH_ENABLED=true`,
  explicit CORS/CSRF origins, and trusted proxy settings only behind a trusted
  proxy; attach sanitized production config preflight JSON rather than raw
  `.env` values.
- [ ] Secrets audit confirms no real API keys, provider credentials, cookies,
  session ids, broker credentials, webhook URLs, password hashes, raw prompts,
  raw provider payloads, or stack traces are present in logs, admin diagnostics,
  readiness output, browser DOM, or docs.
- [ ] `./scripts/release_secret_scan.sh` is clean on the release candidate.
- [ ] Admin harness/browser smoke evidence is current, with mocked harness
  coverage clearly separated from real auth/session staging proof.
- [ ] MFA enforcement prerequisites are complete or public admin access is
  blocked behind a documented compensating control.
- [ ] Backup/restore dry-run preflight passes with fresh synthetic or sanitized
  metadata and a temp-only restore target.
- [ ] Real isolated PostgreSQL backup/restore drill passes in an isolated
  environment.
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
