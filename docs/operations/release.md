# Release And Production Readiness

> Status: Canonical
> Scope: repository-owned production-readiness documentation, release qualification, and operational review boundaries
> Audience: release maintainers, operators, security owners, and reviewers

`.github/workflows/release.yml` and the repository validators are the
executable release authority. This document explains the evidence contract; it
does not approve a release or alter runtime defaults.

## Production Readiness Documentation Authority

Canonical owner: this document. The former deployment checklists and broad
launch-audit indexes were retired; they must not be recreated as compatibility
shims, mirrors, or alternate authorities.

Current public multi-user production posture remains **NO-GO** unless every
repository-owned required gate has accepted sanitized target-environment
evidence and manual release review.

| Production concern | Repository-owned authority | Required evidence boundary |
| --- | --- | --- |
| Production environment marker | `APP_ENV=production` must be explicit in the sanitized production config contract. | Use `python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>`; do not attach raw `.env` values. |
| Authentication enablement | `ADMIN_AUTH_ENABLED=true` is required for public deployment; missing or false remains local/dev only. | Auth-disabled public ingress is **NO-GO** and does not change runtime defaults. |
| Fail-closed production posture | Missing launch config, unsupported MFA scope, public SearXNG discovery, or unsafe CORS posture fails closed. | Output may include flag names, states, and bounded labels, never secret values or raw service URLs. |
| CORS and CSRF allowlist | `CORS_ALLOW_ALL=false`, explicit `CORS_ORIGINS`, and explicit `CSRF_TRUSTED_ORIGINS` are required for public topology review. | Prove intended HTTPS origin behavior without echoing credential-bearing origins. |
| Secret and config handling | Provider keys, sessions, DSNs, broker credentials, webhook URLs, raw provider payloads, stack traces, and raw `.env` values stay out of docs and evidence. | Use presence states, redacted summaries, and sanitized validator output. |
| Docs/OpenAPI production exposure | Docs/OpenAPI must fail closed when production mode has public ingress but auth is disabled. | Documentation preserves auth-disabled production exposure as **NO-GO**. |
| Database and persistence readiness | Local/storage checks, backup/PITR opt-in flags, restore evidence tooling, and owner-isolation smoke are bounded to implemented repository owners. | Do not claim external infrastructure ownership. |
| Runtime startup verification | `main.py` exits 1 on API import, lifespan, bind, pre-start runner exit, or bounded startup timeout; `scripts/uat_runtime_harness.py` is the local verifier. | Static preparation failure and readiness 503 remain distinct; local UAT is not launch approval. |
| Health and readiness checks | Coverage is limited to repository scripts, API/system endpoints, admin diagnostics, and release-summary validators present in the tree. | Missing target-environment evidence stays blocked, partial, or **NO-GO**. |
| Rollback and operational validation | Rollback proof binds last-good source/image, DB restore decision points, health checks, owner isolation, and sanitized evidence. | Documentation alone implies no release, rollback, or live-enforcement approval. |

Public deployment env flag matrix:

| Flag / feature | Current behavior | Classification | Required target-environment evidence |
| --- | --- | --- | --- |
| `APP_ENV` | Production security semantics require explicit `production`; other values remain local/dev. | **GATED** | Sanitized config contract and target-environment evidence without raw `.env` values. |
| `VITE_API_URL` | Same-origin by default; explicit value is for reviewed split-domain/static deployments. | **GATED** | Browser/ingress evidence for intended HTTPS API origin and matching CORS/CSRF posture. |
| `PUBLIC_API_ABUSE_LIMIT_*` | Process-local limiter knobs are clamped and sanitized in diagnostics. | **SAFE** | Sanitized limiter snapshot labeled process-local; it is not quota, billing, auth, or distributed rate-limit enforcement. |
| `CRYPTO_REALTIME_ENABLED` | Outbound realtime behavior and degradation need explicit review. | **AMBIGUOUS** | Target-environment decision and degraded-behavior evidence. |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | Public-instance discovery is unsuitable unless separately accepted. | **NO-GO** | Vetted self-hosted endpoints, explicit disablement, or accepted operator risk evidence. |

**SAFE** still requires target-environment evidence. **GATED** requires explicit
config and accepted evidence. **AMBIGUOUS** requires an operator decision.
**NO-GO** applies when required evidence is missing or a flag is used to imply
provider, quota, auth/RBAC, database, broker, notification, or other
live-enforcement approval.

## Release Candidate Qualification

`.github/workflows/release.yml` is the sole publication authority. It builds
one source/Web/multi-architecture OCI candidate, binds exact source SHA/tree,
nested environment evidence, reviewed Python lock, Web artifact identity, and
amd64/arm64 image digests, then records twelve explicit qualification gates.
Missing, skipped, cancelled, neutral, unknown, or failed gates remain NO-GO.

Promotion consumes the qualified manifest and copies the existing registry
digest. It does not rebuild or resolve dependencies. Electron Desktop remains
outside the qualified graph while its legacy scripts install independently;
Desktop publication stays disabled rather than creating a second authority.

## Operational Domains

The sections below are stable documentation anchors for operator/admin
surfaces. They describe review boundaries, not current target-environment
acceptance.

### Security And RBAC

Auth, MFA, RBAC, session, cookie, CSRF/CORS, token, password, and admin
protection remain fail-closed. Staged operator evidence and explicit approval
are required before changing enforcement or fallback behavior.

### Quota And Cost

Cost observability and quota helpers are advisory unless their exact route and
reservation lifecycle have separate approval. Evidence must not imply a live
spend cap or distributed enforcement owner that does not exist.

### Provider Reliability

Diagnostics do not authorize changes to provider order, fallback, retry,
timeout, cache, credentials, source authority, entitlement, or display rights.
Real entitlement and target-environment evidence remain required.

### Database And Restore

Repository tooling can prepare sanitized readiness and restore/PITR evidence.
Real restore execution, retention decisions, migrations, cleanup, and deletion
remain separately authorized operations. See
[`docs/operations/database.md`](database.md).

### WS2 And Async Runtime

Process-local SSE, durable polling, synthetic worker, and multi-instance
evidence stay distinct. Synthetic or single-process results do not establish a
staging multi-instance runtime.

### Portfolio And Backtest

Public readiness does not relax accounting, fills, costs, metrics, benchmark,
stored-result, owner-isolation, FX, ledger, or no-advice semantics. These remain
protected even when release tooling is otherwise green.

### Manual Release Criteria

Manual review binds candidate identity, required gate results, sanitized
target-environment artifacts, known residual risks, rollback identity, and
remote digest verification. Task acceptance, artifact creation, or individual
green checks do not complete release qualification.

### Highest-Risk Blockers

Missing real target-environment evidence, identity mismatch, auth/RBAC gaps,
unqualified provider rights, unproven restore/rollback, incomplete browser UAT,
or any required gate outside PASS remains a release blocker.

### Private Beta

A small private beta still uses the same fail-closed truth and security
boundaries. Reduced audience does not convert missing evidence into acceptance.

## Operator Evidence

Use [`docs/operations/operator-evidence.md`](operator-evidence.md) for sanitized
offline workflows. Raw evidence, local run output, browser traces, logs, and
temporary acceptance material are not durable documentation.
