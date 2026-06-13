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
task/progress state, synthetic worker prototype, safe offline WS2
multi-instance smoke preflight tooling, cost ledger foundations,
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
- Provider circuits are visible in storage/API diagnostics and advisory admin
  surfaces, but runtime provider fallback/order/enforcement behavior has not
  changed and target-environment degraded/SLA evidence remains missing.
- DB readiness has a local dry-run backup/restore preflight, admin-log
  retention/storage policy evidence, and a policy-only high-growth retention
  tier matrix, but still lacks an isolated PostgreSQL restore/PITR drill and
  accepted dry-run reports for non-log high-growth domains.
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
- [x] Fallback-off operator pilot evidence can be validated offline through
  `scripts/security_operator_acceptance_check.py --artifact <sanitized-security-operator-artifact.json>`;
  the artifact must include complete route inventory, explicit backend
  capability classification, frontend fail-closed gate proof, explicit allow,
  legacy/missing fail-closed denial, rollback, sanitized audit evidence, and
  `runtimeDefaultUnchanged=true`.

Remaining gaps:

- [ ] Coarse admin compatibility fallback remains for existing/legacy admin
  users.
- [ ] A real target-environment fallback-off operator pilot artifact has not
  been accepted by reviewers.
- [ ] Adjacent non-migrated admin surfaces still use coarse `require_admin_user`
  style gates.
- [ ] Role management UI and capability mutation governance are absent.
- [ ] R5 coarse fallback removal remains future work.
- [ ] Sensitive route audit/reauth/MFA policy needs to be applied consistently
  before treating capability RBAC as production least privilege.

Go/no-go:

- **NO-GO** for broad public admin exposure until coarse fallback removal or a
  written production exception is approved with compensating controls. Offline
  fallback-off evidence readiness does not flip the default and does not approve
  public launch.

## 4. WS2 / task runtime gates

Status:

- [x] Durable task state foundation exists through `durable_task_states`.
- [x] Durable progress/event rows exist through
  `durable_task_progress_events`.
- [x] Owner-scoped durable status and polling fallback exist.
- [x] Synthetic worker prototype can claim/lease fixture-backed tasks, write
  progress, retry bounded transient failures, and complete/fail safely.
- [x] Safe offline WS2 multi-instance smoke preflight exists through
  `python3 scripts/ws2_multi_instance_smoke.py --synthetic`; it uses disposable
  SQLite and synthetic durable task helpers only, does not call staging, and
  does not change API/SSE/worker semantics.
- [x] Target-environment WS2 evidence can be checked offline through
  `python3 scripts/ws2_target_environment_evidence_check.py <sanitized-ws2-target-environment-evidence.json>`;
  the template lives at
  `docs/audits/ws2-target-environment-evidence-template.json`. This checker
  validates only operator-supplied sanitized API A/B evidence and now emits a
  scoped acceptance-dimension matrix for API A submit, synthetic worker/lease
  flow, API B durable status readback, polling replay, owner-hidden
  status/polling, retry/failure safety, and explicit process-local SSE
  limitation handling. It does not run staging calls, create evidence, change
  runtime behavior, or approve launch.
- [x] Current process-local `AnalysisTaskQueue` and SSE remain the default.

Remaining blockers:

- [ ] `/api/v1/analysis/tasks/stream` SSE is process-local and must not be
  treated as cross-instance reliable.
- [ ] Current public-safe deployment assumption is still single API process, or
  sticky routing with accepted task visibility limits.
- [ ] Accepted staging multi-instance smoke evidence is required before public
  multi-user launch.
- [ ] Accepted smoke must prove API A submit, worker lease, API B durable read,
  polling replay, owner isolation, lease expiry recovery, retry/failure safety,
  and sanitized degraded readiness.
- [ ] A real sanitized WS2 target-environment artifact must be filled from the
  staging/API A+B run and accepted by reviewers; placeholder, fixture-only,
  local, or CI synthetic evidence does not close this gate.
- [ ] Each `PROFILE_WS2_ACCEPTANCE_EVIDENCE_SCOPED` acceptance dimension must
  be backed by operator-filled target-environment summaries; passing local
  synthetic evidence or the offline checker alone is not accepted staging
  readiness.
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
- [x] A default-off, owner-allowlisted sync single-stock analysis route pilot
  can block only that route on quota rejection, consume estimated route units
  after success, and release on analysis failure when explicitly enabled.
- [x] Cost-ledger reservation evidence now distinguishes the existing
  `quota_reservation_id` ledger seam from the route pilot's estimated-unit
  consume/release behavior; the current route pilot does not make actual
  provider-cost accounting billing-authoritative.

Remaining blockers:

- [ ] Accepted staging/operator evidence for the default-off route pilot is not
  complete, and broad/global quota enforcement remains disabled.
- [ ] A single terminal transition owner for route-pilot reservations and
  cost-ledger reconciliation has not been accepted; exact-once actual-cost
  consume remains **NO-GO**.
- [ ] Ledger writes remain observational and best-effort; failures must not
  change user-visible LLM behavior.
- [ ] Some legacy/system usage can still write null-owner rows for backward
  compatibility.
- [ ] Budget burn-down UI, policy editing, broad enforcement expansion, and
  retention/aggregation policy remain future work.
- [ ] Provider quota buckets are not yet live enforcement.

Go/no-go:

- **NO-GO** for unrestricted public usage until quotas have a staged enforcement
  pilot, admin visibility, rollback plan, owner/guest accounting acceptance,
  billing-authoritative reconciliation, and an accepted exact-once consume
  boundary.

## 6. Provider reliability gates

Status:

- [x] Provider circuit/quota storage foundation exists.
- [x] Read-only admin diagnostics API exists for circuits, events, quota
  windows, and probe events.
- [x] Provider circuit dry-run observer exists for synthetic bounded observation
  buckets.
- [x] Provider SLA/readiness diagnostics and Launch Cockpit/admin provider
  surfaces are present as bounded advisory operator visibility.
- [x] A default-off admin built-in provider validation probe pilot can block
  only the `data_source_validation/admin_provider_probe` boundary when
  explicitly enabled; rollback is a separate explicit flag.
- [x] Admin SLA readiness can expose opt-in `adminProbePilotEvidence` for the
  admin probe pilot, including default-off, rollback, selected boundary, last
  decision category, would-block/block state, and sanitized no-change markers.
- [x] Diagnostics responses omit raw provider payloads, URLs/query strings,
  credentials, cookies, raw session ids, exception text, stack traces, and
  internal storage details.

Remaining blockers:

- [ ] No public/user provider runtime call site is approved for enforcement.
- [ ] No provider ordering, fallback, retry, timeout, in-flight, sufficiency, or
  MarketCache behavior change has landed outside the narrow admin probe pilot.
- [ ] Existing Launch Cockpit/admin provider surfaces do not prove provider
  entitlement, staging degraded behavior, live circuit enforcement, provider
  order/fallback/cache behavior, or public launch readiness.
- [ ] Accepted operator/staging evidence and any broader provider circuit
  enforcement policy remain separately required.
- [ ] The opt-in admin probe evidence surface is operator visibility only; it
  does not accept target-environment evidence, approve public launch, or approve
  public/user provider runtime enforcement by itself.
- [ ] Provider SLA/degraded target-environment evidence and live-credential
  redaction proof remain missing before launch.

Go/no-go:

- **NO-GO** for public scale until provider exhaustion behavior is measured in
  staging and an approved degraded/enforcement policy exists. Launch Cockpit
  and admin diagnostics are advisory visibility only; neither they nor Mission
  Control approve launch.

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
- [x] The operator evidence runbook now separates dry-run preflight,
  externally executed isolated restore/PITR drill evidence, restore/PITR
  operator bundle evidence, and manual review so templates/checkers are not
  mistaken for completed real restore acceptance.
- [x] Admin log retention tiers are explicit and test-backed:
  `admin_logs_standard`, `admin_logs_minimum_protected`, and
  `admin_logs_storage_pressure`.
- [x] Admin log cleanup is preview-first, preserves the minimum retention floor,
  emits sanitized cleanup audit events, and keeps storage-size-unavailable
  fallback safe.
- [x] Synthetic staging-ingress smoke preflight exists:
  `python3 scripts/staging_ingress_smoke.py --base-url "$STAGING_INGRESS_BASE_URL"`.
- [x] Ingress smoke is safe by default: without
  `WOLFYSTOCK_STAGING_INGRESS_SMOKE=1` it emits dry-run JSON evidence and does
  not open network sockets.
- [x] Ingress smoke covers `/api/health`, `/api/health/ready`,
  `/api/health/live`, unauthenticated `/api/v1/admin/users` fail-closed
  behavior, sensitive/debug payload patterns, sanitized timeout/action output,
  and attachable JSON evidence.
- [ ] Isolated PostgreSQL backup/restore execution is still missing.
- [ ] Real isolated PostgreSQL restore/PITR evidence is still pending until an
  accepted sanitized artifact from a real isolated drill is supplied; generated
  templates, dry-run preflight output, and validator success alone do not close
  this blocker.
- [ ] Real HTTPS staging ingress smoke evidence is still missing; the new
  preflight must be run against a synthetic staging URL with explicit opt-in.
- [ ] Encrypted backup infrastructure, PITR execution, restore smoke, and
  rollback runbook must be documented and exercised before public onboarding.
- [x] Policy-only high-growth retention tiers now exist in
  `docs/audits/high-growth-retention-tier-policy.md` for task progress,
  terminal task state, LLM usage, scanner/backtest artifacts, provider
  counters, guest/cache metadata, future Options cache rows, portfolio
  imports/import previews, research/report packets, frontend build artifacts,
  and CI artifacts.
- [ ] Accepted retention dry-run reports and cleanup approval are still missing
  for non-admin-log high-growth domains.
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
  it validates MFA, RBAC fallback, provider credential dry-run, provider live
  probe opt-in and bounded timeout, provider staging probe artifacts, provider
  circuit controlled enforcement, quota, budget-alert dry-run, real
  restore/PITR, staging ingress, public no-secret safety, supply-chain
  dependency/build artifact safety, incident-response/audit evidence, WS2/SSE
  topology and polling fallback, admin log retention/capacity rehearsal,
  portfolio/backtest export and browser proof, notification delivery
  rehearsal, user data privacy/export/deletion rehearsal, market freshness and
  fallback evidence, AI report/guest-preview safety, Options derivatives
  safety, API abuse/request-safety, final clean gate, and domain-local provider
  operator, restore/PITR operator, security MFA/RBAC operator, quota/budget
  operator, staging ingress operator, WS2/SSE operator decision, config
  snapshot, and manual release review-record evidence categories without
  approving launch.
- [x] Operator evidence bundle review support exists through
  `python3 scripts/operator_evidence_bundle_check.py <sanitized-operator-evidence-dir>`;
  it aggregates already-sanitized validator statuses only and does not replace
  any required operator artifact.
- [x] Domain-local offline validators/templates exist for API
  abuse/request-safety evidence, provider operator evidence, provider
  SLA/licensing and admin-probe pilot evidence, notification delivery
  rehearsal evidence, real restore/PITR operator evidence, security MFA/RBAC
  operator acceptance, quota/budget operator evidence, and staging ingress
  operator evidence. These validators are rehearsal/evidence plumbing only;
  they do not perform live provider/network/DB/notification/runtime actions or
  approve launch.
- [x] Offline validators/templates exist for WS2/SSE operator decisions,
  config snapshot evidence, and manual release review records. These are
  review plumbing only: real operator artifacts are still required, templates
  and synthetic fixtures are not accepted production evidence, and release
  approval remains external/manual.
- [x] Offline checker/template exists for WS2 target-environment evidence:
  `scripts/ws2_target_environment_evidence_check.py` and
  `docs/audits/ws2-target-environment-evidence-template.json`. Passing the
  checker is review plumbing only and keeps `publicLaunchReady=false`.
- [x] Offline operator evidence workflow tooling exists for sanitized template
  generation, per-category validation, checksum manifest creation/verification,
  bundle aggregation, and Markdown review-report rendering. The tooling is
  review support only and does not change launch acceptance status.
- [x] Production config/secret contract preflight exists through
  `python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>`;
  it consumes only synthetic or operator-sanitized flag names and secret
  presence states, emits stable JSON, and never prints secret values. A passing
  preflight means only that the sanitized contract is internally complete; it
  is not public launch approval and does not prove the target environment.
- [x] Public-deployment env flag semantics are documented for release review:
  `APP_ENV`, `VITE_API_URL`, `PUBLIC_API_ABUSE_LIMIT_*`,
  `CRYPTO_REALTIME_ENABLED`, and `SEARXNG_PUBLIC_INSTANCES_ENABLED` have an
  explicit safe/gated/ambiguous/NO-GO classification below. The matrix is
  documentation and test coverage only; it does not change runtime defaults,
  production config values, provider routing, quota enforcement, auth/RBAC
  behavior, database state, or frontend UI behavior.
- [ ] Sanitized operator templates have been filled with real
  target-environment operator artifact summaries and validated by their
  matching category validators.
- [ ] Sanitized checksum manifest has been created and verified for the
  target-environment operator artifacts through
  `python3 scripts/operator_evidence_manifest_check.py`.
- [ ] Offline review report has been rendered from sanitized bundle and
  manifest summaries through
  `python3 scripts/release_review_report_render.py` and reviewed manually.
- [ ] Sanitized config snapshot evidence is attached and accepted through
  `python3 scripts/config_snapshot_evidence_check.py <sanitized-config-snapshot-evidence.json>`
  without raw `.env` values, deployment state reads, or secret-bearing values.
- [ ] Sanitized WS2/SSE topology operator decision evidence is attached and
  accepted through
  `python3 scripts/ws2_sse_operator_decision_check.py <sanitized-ws2-sse-operator-decision.json>`
  without cross-instance SSE claims or runtime cutover.
- [ ] Sanitized WS2 target-environment API A/B evidence is attached and
  accepted through
  `python3 scripts/ws2_target_environment_evidence_check.py <sanitized-ws2-target-environment-evidence.json>`
  without raw user identifiers, URLs, credentials, payloads, stack traces,
  cross-instance SSE claims, queue/broker cutover, or public launch approval.
- [x] Incident-response audit evidence pack exists through
  `python3 scripts/incident_response_evidence.py --evidence <sanitized-incident-response-evidence.json>`;
  it validates sanitized admin-critical action evidence, preview-first cleanup,
  provider/notification/release failure evidence, and local no-secret/no-network
  generation without approving launch.
- [ ] Sanitized operator evidence pack is accepted for every hard blocker; the
  checker may move from **NO-GO** to `GO-REVIEW-REQUIRED`, but
  `releaseApproved` remains false until manual approval.
- [ ] Sanitized manual release review-record evidence is attached and validated
  through
  `python3 scripts/manual_release_approval_evidence_check.py --artifact <sanitized-manual-release-review-record.json>`;
  this validator must still emit `releaseApproved=false`.
- [ ] Real operator-produced artifacts for the domain-local validator
  categories are attached and accepted by reviewers for the target environment;
  accepted review evidence still does not approve public launch without manual
  release review.
- [ ] Staging smoke passes through HTTPS reverse proxy on synthetic users/data.
- [ ] Accepted WS2 staging multi-instance smoke passes or deployment is
  explicitly constrained to single API process with documented SSE/task
  limitations.
- [ ] Backend `:8000` is not directly exposed to the public internet.
- [ ] Public ingress exposes only 80/443, redirects HTTP to HTTPS, and forwards
  to a private/local backend port.
- [ ] Production config source (`.env`, `ENV_FILE`, or process environment)
  uses `APP_ENV=production`, `ADMIN_AUTH_ENABLED=true`, explicit
  `CORS_ALLOW_ALL=false`, explicit CORS/CSRF origins, trusted proxy
  settings only behind a trusted proxy, explicit
  `WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_SCOPE=admin_only`, explicit
  `WOLFYSTOCK_QUOTA_ENFORCEMENT_MODE`, and explicit default-off opt-in flags
  for `WOLFYSTOCK_BACKUP_PITR_EXECUTION_ENABLED` plus
  `WOLFYSTOCK_STAGING_INGRESS_SMOKE`; attach sanitized production config
  preflight JSON rather than raw env values. Missing or false
  `ADMIN_AUTH_ENABLED` remains local/dev-only and public deployment **NO-GO**.
- [ ] Secrets audit confirms no real API keys, provider credentials, cookies,
  session ids, broker credentials, webhook URLs, password hashes, raw prompts,
  raw provider payloads, or stack traces are present in logs, admin diagnostics,
  readiness output, browser DOM, or docs.
- [ ] Broker/order/trade redaction evidence confirms no raw broker account IDs,
  order IDs, request IDs, endpoint URLs, account metadata, tokens, raw broker
  payloads, execution payloads, import fingerprints, or account labels appear
  in public/member/admin-safe outputs, portfolio import preview/commit response
  artifacts, logs, reports, operator evidence, browser DOM, or
  release-candidate exports; use
  `docs/audits/broker-order-trade-redaction-release-evidence-checklist.md` as
  the review checklist and keep missing accepted evidence as **NO-GO**.
- [ ] `./scripts/release_secret_scan.sh` is clean on the release candidate.
- [ ] Admin harness/browser smoke evidence is current, with mocked harness
  coverage clearly separated from real auth/session staging proof.
- [ ] MFA enforcement prerequisites are complete or public admin access is
  blocked behind a documented compensating control.
- [ ] Backup/restore dry-run preflight passes with fresh synthetic or sanitized
  metadata and a temp-only restore target.
- [ ] Real isolated PostgreSQL backup/restore drill passes in an isolated
  environment, with accepted restore/PITR operator evidence from the real drill.
- [ ] Restore/PITR evidence attachments include only sanitized validator output,
  manifests, and review references; raw command output, DSNs, env values, backup
  paths, SQL, row data, dumps, tracebacks, private hostnames, usernames/passwords,
  sensitive user-data paths, and launch approval claims are not attached. Accepted
  operator artifacts include isolated target, backup artifact summary, PITR target,
  restore execution summary, post-restore smoke, owner-isolation smoke, rollback
  decision point, operator approvals, and sanitized artifact references.
- [ ] Rollback plan is written, including last-good commit/image, DB restore
  decision point, health checks, and owner-isolation smoke.
- [ ] Retention dry-run reports exist for high-growth domains; the policy-only
  tier matrix does not satisfy this gate by itself.
- [ ] Cost/quota enforcement status is explicitly labeled in user/admin-facing
  docs and UI so observability is not mistaken for a spending cap.
- [ ] Deployment docs distinguish single-instance/private-beta rehearsal from
  public multi-user launch and keep the public verdict at **NO-GO** until
  isolated restore/PITR, HTTPS staging ingress, backup infra, and rollback
  proof are accepted.

## 11. Env flag launch matrix

This matrix classifies public-deployment env flags by current behavior and
evidence requirements. It is a docs/test readiness aid only: raw `.env` values,
provider credentials, URLs with embedded credentials, cookies, session ids,
tokens, database DSNs, webhook URLs, raw provider payloads, and stack traces
must not be attached to release evidence. Use flag names, presence states,
bounded labels, and redacted summaries only.

| Flag / feature | Current behavior | Classification | Required target-env evidence before public launch |
| --- | --- | --- | --- |
| `APP_ENV` | Enables production-mode security semantics when explicitly set to `production`; missing or non-production values are acceptable for local/dev only. | **GATED** | Sanitized production config contract and config snapshot evidence must show the target environment is explicitly reviewed as production/posture-ready without exposing raw env values. This does not approve auth/RBAC/MFA launch blockers by itself. |
| `VITE_API_URL` | Frontend uses same-origin API by default; an explicit value only overrides the API base URL for split-domain/static deployments. | **GATED** | Browser/ingress evidence must show the built frontend reaches the intended HTTPS API origin, CORS/CSRF origins match, and backend `:8000` is not directly public. Missing split-domain evidence keeps launch **NO-GO**. |
| `PUBLIC_API_ABUSE_LIMIT_*` | Process-local abuse burst limiter knobs are clamped and sanitized in diagnostics; they bound malformed public API bursts but are not quota, billing, auth, or distributed rate-limit enforcement. | **SAFE** | Include sanitized limiter configuration/snapshot evidence for the target topology and keep it labeled process-local. Do not present these flags as live quota enforcement or provider abuse protection. |
| `CRYPTO_REALTIME_ENABLED` | Defaults to realtime crypto SSE background connection unless explicitly disabled; disabling falls back to REST/cache behavior. | **AMBIGUOUS** | Target-env evidence must show whether outbound Binance/WebSocket access is allowed, how failures are degraded, and whether realtime is intentionally disabled. Missing evidence is not a provider-readiness approval. |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | Defaults to discovering public SearXNG instances when no self-hosted `SEARXNG_BASE_URLS` are configured. | **NO-GO** | Public launch must either use vetted self-hosted SearXNG endpoints, explicitly disable public discovery, or attach a separately accepted operator risk decision. Missing evidence keeps search/provider posture blocked. |

Launch classification rule:

- **SAFE** means the current local behavior has bounded diagnostics/tests, but
  still needs target-environment evidence before public launch.
- **GATED** means the flag can be safe only when explicitly configured and
  matched by accepted target-environment evidence.
- **AMBIGUOUS** means the current default may be acceptable for local/private
  use but requires an operator decision for public deployment.
- **NO-GO** applies to launch posture whenever required target-environment
  evidence is missing, raw secrets would be needed to prove the claim, or a
  flag is used to imply provider, quota, auth/RBAC, database, broker, or
  notification live-enforcement approval.

Final launch verdict:

- **NO-GO** until every item in this section is checked or explicitly accepted
  as a documented production exception.

## 12. Validation for this document

Required docs-only validation:

```bash
git diff -- docs/audits/deployment-readiness-checklist.md docs/CHANGELOG.md
git diff --check -- docs/audits/deployment-readiness-checklist.md docs/CHANGELOG.md
```

No `ci_gate` is required for this docs-only checklist refresh.
