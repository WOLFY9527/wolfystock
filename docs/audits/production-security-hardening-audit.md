# Production Security Hardening Audit

Date: 2026-05-06
Mode: static security audit. No runtime behavior changed.

Implementation note, 2026-05-06:

- Phase 1 auth/session hardening has landed for the first blocker-reduction pass: login throttling now uses durable database-backed IP and account hash buckets, login failure responses are generic, failed/rate-limited/success-after-failure login events are written through sanitized execution-log security events, production cookies are forced Secure when production mode is detected, cookie-authenticated unsafe methods enforce trusted Origin/Referer checks, and production CORS now rejects wildcard mode or missing explicit `CORS_ORIGINS`.
- Phase 2 session/header/proxy hardening has landed for a bounded production-deployment risk reduction pass: admin sessions now enforce configurable idle expiry with existing `app_user_sessions.last_seen_at` metadata while preserving absolute max-age, stale admin sessions are revoked on validation, responses include baseline browser security headers, HSTS is emitted only when production mode sees HTTPS, and deployment docs now include a HTTPS reverse-proxy hardening template with no-direct-public-`:8000` guidance.
- This does not close the remaining public-exposure blockers: password KDF upgrade, MFA, RBAC/capability split, dependency/container scanning follow-up, and broader log/secret hardening remain separate tasks.

## 1. Executive summary

Deployment-readiness verdict: blockers before public internet exposure.

WolfyStock has meaningful admin-data safety work already in place, especially around safe admin projections, admin security actions, portfolio masking, and audit records for sensitive admin operations. It is not yet safe enough to expose directly to the public internet without additional production hardening.

Deployment classification:

| Classification | Verdict |
| --- | --- |
| Ready for local/internal only | Yes, assuming trusted operators and local network exposure only. |
| Conditionally ready for controlled private deployment | Possible only behind HTTPS, strict origin allowlists, enabled auth, restricted operators, private network controls, and non-sensitive data. |
| Blockers before public internet exposure | Yes: CSRF protection, durable login throttling, production TLS/proxy/security headers, stronger admin controls, dependency/container scanning, and log/secret hardening remain required. |

Top risks:

- Blocker: no explicit CSRF protection for cookie-authenticated state-changing API routes.
- Blocker: login throttling is process-local and IP-only, so it is not adequate against distributed brute-force or credential stuffing attacks.
- Blocker: production reverse proxy, HTTPS-only, HSTS, trusted host/proxy, and security header posture is not enforced by committed deployment config.
- High: password hashing uses salted PBKDF2-SHA256 but with a static 100,000 iteration factor and a 6-character minimum password length; this needs a public-server upgrade plan.
- High: admin authorization is currently a coarse admin/non-admin gate, with no deployed RBAC/capability split or MFA requirement for sensitive admin actions.
- High: debug/full-prompt/exception logging paths can expose sensitive analysis context if production logging is misconfigured.
- Unknown / needs runtime validation: exact production environment values, TLS termination, actual CORS origins, cookie Secure behavior through the deployed proxy, and dependency vulnerability state.

Recommended next implementation tasks:

1. Auth hardening Phase 1: durable login rate limit, failed-login audit, generic errors, and account plus IP throttling.
2. Session and cookie production hardening: enforced Secure cookies behind trusted HTTPS, admin idle timeout, and session rotation policy review.
3. CSRF/CORS production hardening for cookie-authenticated write routes.
4. Admin RBAC/capability model and admin MFA design before implementation.
5. Secret, dependency, container, and security-header CI hardening.

## 2. Scope and non-scope

Scope:

- Authentication and account bootstrap.
- Password storage and password verification.
- Session cookies and server-side session validation.
- Login brute-force and credential-stuffing controls.
- CSRF, CORS, trusted origin assumptions, and frontend API client behavior.
- Admin APIs, admin security controls, and admin authorization posture.
- Sensitive data exposure in APIs, frontend DOM assumptions, logs, and audit events.
- Secret management, deployment configuration, dependency, container, and proxy readiness.
- API abuse and resource-exhaustion risks visible through static inspection.

Non-scope:

- Full penetration test.
- Live exploit testing.
- Dependency upgrade or dependency fix.
- Production config values.
- Cloud or provider IAM.
- Broker execution security beyond static findings.
- Live server, browser, or API validation.
- Runtime, UI, test, migration, dependency, or behavior changes.

## 3. Current security strengths

- Already mitigated: admin user projections do not expose `password_hash`, raw password material, raw session ids, tokens, or secret fields. They expose password state and masked/session-handle summaries instead.
- Already mitigated: admin security S1 supports disable user, enable user, and revoke sessions, with reason capture and audit events.
- Already mitigated: self-disable and last-active-admin guardrails reduce accidental total admin lockout.
- Already mitigated: sensitive admin security actions are recorded through the admin governance audit service.
- Already mitigated: admin portfolio APIs avoid raw broker payload exposure, mask broker account references, and provide read-only visibility for holdings, cash, transactions, corporate actions, and risk summaries.
- Already mitigated: the admin-governance cost QA runbook documents no-secret handling and explicitly avoids raw prompt, raw provider payload, API key, session id, and password hash exposure.
- Already mitigated: the duplicate-cost dashboard/API is read-only and carries `noExternalCalls` metadata.
- Already mitigated: CORS wildcard mode disables credentials instead of combining wildcard origins with credentialed browser requests.
- Already mitigated: `.env` is ignored by git and was not inspected in this audit; `.env.example` is a template only.
- Already mitigated: auth sessions are signed with HMAC-SHA256 and validated against a server-side session table before the current user is accepted.

## 4. Password storage and cracking resistance

Static evidence:

- `src/auth.py` defines `PBKDF2_ITERATIONS = 100_000` and `MIN_PASSWORD_LEN = 6`.
- Password creation uses `secrets.token_bytes(32)` for a unique random salt and `hashlib.pbkdf2_hmac("sha256", ...)`.
- Password storage format includes algorithm, iteration count, salt, and derived hash material.
- Verification recomputes PBKDF2-SHA256 and compares with `hmac.compare_digest`.
- Password creation/update paths include bootstrap account creation, normal user creation through admin user service, password changes, and admin security temporary-password reset.
- API/admin response schemas use safe projections. Static inspection did not find admin endpoints intentionally returning password hashes.

Classification: needs improvement before public internet exposure.

Assessment:

- Positive: this is not plaintext, MD5, SHA1, or unsalted SHA256. Per-password random salt and constant-time comparison are present.
- Gap: PBKDF2-SHA256 at 100,000 iterations is weaker than preferred current public-server baselines, especially for high-value admin accounts.
- Gap: minimum password length is 6 characters, which is too weak for public deployment.
- Gap: no Argon2id, bcrypt, scrypt, pepper, breached-password check, or adaptive hash migration policy was found.

Recommendations:

- Prefer Argon2id with calibrated memory/time parameters, or bcrypt with a strong cost if Argon2id is not feasible.
- Keep unique per-password salts.
- Consider an optional pepper stored in a real secret manager, not in the database or frontend bundle.
- Add a password hash migration plan that can verify old hashes and rehash on successful login or password change.
- Raise minimum password length and block weak/common passwords.
- Add breached-password screening later if privacy and availability constraints are acceptable.

## 5. Login brute-force and credential-stuffing controls

Static evidence:

- `/api/v1/auth/login` calls `check_rate_limit`, `record_login_failure`, and `clear_rate_limit`.
- `src/auth.py` keeps `_rate_limit` in process memory with a 5-minute window and 5 failed attempts per IP.
- `get_client_ip` trusts `X-Forwarded-For` only when `TRUST_X_FORWARDED_FOR=true`; otherwise it uses the direct request client.
- Password verification and sensitive password-check flows reuse the same rate-limit helpers.
- No durable account lockout, distributed rate limiter, CAPTCHA, MFA/TOTP/WebAuthn, or persistent failed-login audit trail was found.

Findings:

- Blocker: the current limiter is process-local. It does not survive restart, does not work across multiple workers/containers, and is easy to dilute across source IPs.
- High: throttling is IP-only, not account plus IP plus subnet/device. This is weak against credential stuffing.
- High: login errors are not fully generic. Examples include separate unknown-user, inactive-user, wrong-admin-password, and wrong-password states.
- Medium: no durable failed-login security events were found for normal auth failure telemetry.
- Medium: no MFA requirement was found for admin users.

Recommendations:

- Add durable IP plus account based throttling backed by Redis, database, or another production coordination layer.
- Add progressive delay and short lockout windows for repeated failures.
- Record failed-login audit events with sanitized actor, account identifier, source IP category, user agent hash, outcome, and rate-limit decision.
- Apply stricter limits to admin login and password verification routes.
- Add optional MFA first, then require MFA for admin roles before public exposure.
- Return generic login errors while preserving detailed reasons only in internal security telemetry.

## 6. Session and cookie security

Static evidence:

- Auth cookie name is `wolfystock_session`.
- Cookie params use `httponly=True`, `samesite="lax"`, `path="/"`, and `max_age` from `ADMIN_SESSION_MAX_AGE_HOURS`, defaulting to 24 hours.
- Cookie `secure` is set only when the request scheme is HTTPS or `TRUST_X_FORWARDED_FOR=true` and `X-Forwarded-Proto=https`.
- Sessions are HMAC-signed tokens with payload fields such as user id, username, role, session id, issued-at, and expiration.
- Server-side session lookup rejects revoked or expired sessions and rejects inactive users.
- Logout revokes the current session and deletes the cookie.
- Admin security can revoke all sessions for a user.

Assessment:

- Already mitigated: `HttpOnly`, `SameSite=Lax`, server-side revocation checks, and disabled-user rejection are present.
- High: `Secure` depends on correct proxy/scheme configuration. A public deployment misconfigured as direct HTTP or missing forwarded-proto trust can issue non-Secure cookies.
- Medium: no separate short idle timeout for admin sessions was found.
- Medium: no explicit session rotation beyond creating a new session at login was identified.
- Medium: password/security-event session revocation is partial and should be reviewed for every credential-changing path.

Recommendations:

- Enforce Secure cookies in production and fail closed when production auth runs without HTTPS context.
- Keep `HttpOnly` and `SameSite=Lax` or consider `Strict` for admin-only deployments where UX permits.
- Use HTTPS only, HSTS, and trusted reverse proxy headers.
- Rotate session identifiers after login and privilege-sensitive events.
- Revoke sessions on password reset, password change, role change, disable, and suspected compromise.
- Add short idle timeout plus absolute timeout for admin sessions.
- Ensure logout always clears the browser cookie and revokes server-side state.

## 7. CSRF and CORS

Static evidence:

- `api/app.py` configures CORS through `CORSMiddleware`.
- Default origins are local development origins, with extension through `CORS_ORIGINS`.
- `CORS_ALLOW_ALL=true` switches to wildcard origins and sets `allow_credentials=False`.
- In non-wildcard mode, credentials are allowed.
- Frontend API clients use credentialed browser requests.
- No explicit CSRF token, double-submit cookie, origin verification, or referer verification middleware was found for cookie-authenticated write routes.

Findings:

- Blocker: state-changing cookie-authenticated routes lack an explicit CSRF defense.
- Medium: CORS can be safe if production origins are strict, but the actual production allowlist was not validated in this static audit.
- Medium: `SameSite=Lax` reduces some cross-site request risk but is not a complete CSRF strategy for public deployment.

Recommendations:

- Do not use wildcard origins with credentialed production flows.
- Set a strict production origin allowlist and test it through the deployed proxy.
- Add CSRF tokens or enforce same-site plus origin/referer verification for state-changing cookie-authenticated routes.
- Include admin POST/PUT/PATCH/DELETE routes in CSRF coverage.
- Keep explicit OPTIONS handling and document expected frontend origin behavior.
- Add security headers at the app or reverse-proxy layer.

## 8. Admin authorization and privilege model

Static evidence:

- `api/deps.py` provides `require_admin_user`.
- Admin endpoints under `api/v1/endpoints/admin_*.py` use the coarse admin dependency.
- Admin security endpoints implement confirmation/reason checks for disable, enable, revoke sessions, and password reset operations.
- Portfolio admin APIs are read-only and expose masked projections.
- Duplicate-cost/admin observability routes are admin-gated and documented as read-only/no-external-call surfaces.

Findings:

- Already mitigated: admin APIs are not unauthenticated; they require an admin current user.
- Already mitigated: high-impact admin security actions have reason capture, typed confirmation for disable, and guardrails for self-disable and last active admin.
- High: there is no deployed RBAC/capability model for super-admin, security-admin, support-admin, and ops-admin separation.
- High: no admin MFA requirement was found.
- Medium: audit writes appear best-effort in some services; high-sensitivity admin actions should define when audit failure must fail closed.
- Medium: reason-required read access for sensitive views is not generally enforced.

Recommendations:

- Design and implement role/capability checks before expanding admin surfaces.
- Split super-admin, security-admin, support-admin, and ops-admin responsibilities.
- Require MFA for sensitive admin roles.
- Add reason-required access and just-in-time elevation for sensitive reads where practical.
- Define fail-closed audit requirements for disable, role change, credential reset, session revocation, and sensitive export routes.
- Add stricter admin session timeout and reauthentication rules.

## 9. Sensitive data exposure review

| Surface | Sensitive risk | Current mitigation | Gap | Severity | Recommendation |
| --- | --- | --- | --- | --- | --- |
| Auth | Password hashes, session cookies, auth tokens | Hashes are not intentionally returned; cookie is HttpOnly; sessions are signed and server-validated | Login errors reveal account state; production cookie Secure depends on proxy config | High | Generic login errors, production Secure enforcement, failed-login audit |
| Admin users | Password hashes, raw session ids, email/account metadata | Safe projection exposes password state and masked session handles, not raw hashes/sessions | Coarse admin access can view broad user/account metadata | High | RBAC, reason-required reads, admin MFA |
| Admin portfolio | Broker account ids, holdings, transactions, cash, corporate actions | Broker refs are masked; raw broker payloads are not returned; API is read-only | Financial data remains sensitive even when masked | High | Capability checks, audit reads, export controls |
| Admin security | Disable/enable/revoke/reset actions | Requires admin, confirmation/reason for sensitive actions, audits successful actions | No separate security-admin role; audit failure policy should be defined | High | RBAC and fail-closed audit for critical actions |
| Admin logs | Actor/session/request metadata, business symbols, errors | Execution log service and admin activity paths sanitize metadata and hash sensitive handles | Raw exception or arbitrary metadata can still enter logs from other producers | Medium | Central log sanitizer and schema allowlist |
| Duplicate-cost dashboard/API | Provider/model/cost metadata | Read-only, `noExternalCalls`, exactness metadata, no raw prompt/provider payload by schema/docs | Cost data can still reveal usage patterns | Medium | RBAC, aggregation, retention policy |
| Scanner/analysis/chat | Prompts, reports, provider context, symbols | Some API contracts avoid raw provider payload exposure | Debug/full-prompt logs can expose sensitive context | High | Disable verbose prompt logs in prod, sanitize provider errors |
| Frontend DOM/test fixtures | Auth state, API responses, admin data | Frontend uses credentialed API clients and safe admin schemas | DOM may still display broad admin financial/user metadata to any admin | Medium | Role-based UI gating and least-privilege APIs |
| Deployment config | API keys, provider tokens, broker credentials | `.env` is ignored; `.env.example` is a placeholder template | Real production secret handling was not validated | Unknown / needs runtime validation | Secret manager, secret scanning, rotation policy |

## 10. Logging and audit safety

Static evidence:

- `ExecutionLogService` provides structured execution sessions/events and supports sanitized summaries and actor metadata.
- Admin governance audit helper records sensitive admin action events.
- `src/utils/security.py` contains masking/sanitization helpers.
- Error middleware logs unhandled exceptions and includes traceback details in logs; response detail is gated by debug mode.
- Some analysis and notification paths can log prompt previews, full prompts, provider responses, exception strings, or debug payloads depending on log level.

Assessment:

- Already mitigated: admin activity projections and execution-log metadata have dedicated sanitization paths.
- Medium: recursive metadata redaction exists in some paths but does not guarantee every logger or arbitrary metadata producer is sanitized.
- High: raw request body, prompt, provider response, stack trace, or exception-string logging can expose sensitive data if debug/error logging is sent to shared production sinks.
- Medium: failed-login audit coverage is incomplete.
- Medium: audit retention, capacity, tamper resistance, and export controls need production policy.

Recommendations:

- Add structured security events for login failures, rate-limit decisions, password changes, MFA changes, role changes, sensitive reads, and denied admin actions.
- Avoid raw request body logs and raw provider payload logs in production.
- Centralize redaction for secret-like keys and nested metadata before writing logs or audit events.
- Disable full prompt/debug payload logging in production by default.
- Harden log sinks with restricted access, retention limits, tamper resistance, and alerting.
- Define audit retention and capacity management.

## 11. Secret management and deployment config

Static review:

- `.env` exists locally and was listed path-only. Its values were not inspected, printed, copied, or committed.
- `.env` and `.env.*` are ignored by git.
- `.env.example` is committed as a template and contains environment variable names and placeholders only.
- Docker compose mounts the parent `.env` file and publishes the API port.
- Deployment docs include direct `http://server-public-IP:8000` access and optional Nginx/Certbot guidance.
- Static secret-name searches found many expected environment variable names for AI providers, market data providers, broker integration, email, webhooks, database, auth, and notification configuration. Values were not printed.

Findings:

- Medium: `.env` handling is appropriate locally, but production secret storage is not defined as a secret-manager workflow.
- High: direct public exposure of the API port is documented as a deploy path and should not be the public-server baseline.
- Unknown / needs runtime validation: whether any real secret values were ever committed historically was not exhaustively scanned in this audit.
- Unknown / needs runtime validation: production secret rotation, least-privilege DB account, backup encryption, and separation of dev/prod credentials.

Recommendations:

- Use a restricted secret manager or locked-down environment injection for production.
- Keep `.env` excluded from git and CI artifacts.
- Run secret scanning on git history; rotate any exposed keys if a scanner reports committed secrets.
- Use least-privilege database users and separate production, staging, and development credentials.
- Do not put secrets in frontend bundles or public runtime config.
- Avoid mounting broad local `.env` files into production containers when a narrower production secret set is possible.

## 12. Dependency and supply-chain risk

Static evidence:

- Python dependencies are declared in `requirements.txt` and `requirements-dev.txt`.
- Python dependency versions use broad version ranges rather than fully pinned hashes.
- Frontend dependencies are declared in `apps/dsa-web/package.json`, with `apps/dsa-web/package-lock.json` present.
- `pyproject.toml` has a Bandit configuration, but no dedicated Bandit, pip-audit, safety, npm audit, or container scan gate was confirmed in the inspected workflow files.
- Docker build workflows include build/smoke coverage, but no container vulnerability scanner was confirmed.

Assessment:

- Unknown / needs runtime validation: current dependency vulnerability status was not scanned in this audit.
- Medium: broad Python ranges reduce reproducibility.
- Medium: dependency, SAST, secret, and container scanning should be explicit public-server gates.

Recommendations:

- Add CI jobs for `pip-audit` or `safety`, `npm audit`, SAST, and secret scanning.
- Add container image scanning such as Trivy or Grype for release images.
- Use Dependabot or Renovate with review/CI requirements.
- Consider stronger dependency pinning and hash verification for production builds.
- Do not run dependency update/fix commands as part of audit-only work.

Implementation note, 2026-05-06:

- Added `.github/workflows/security-scan.yml` as a dedicated production hardening scan workflow.
- Blocking PR/push/manual gates now cover redacted Gitleaks secret scanning, `pip-audit` for Python requirements, production-only `npm audit --omit=dev --audit-level=high` for `apps/dsa-web`, Bandit SAST over committed backend/application paths, and Trivy scanning of a locally built Docker image.
- The container gate builds only a local scan image and does not push to a registry.
- Added `scripts/security_scan.sh` as an optional local helper. It does not install tools automatically; local dependency audits are opt-in with `SECURITY_SCAN_ALLOW_NETWORK=true`, and local container scanning is opt-in with `SECURITY_SCAN_CONTAINER=true`.
- No dependency update/fix commands, runtime app behavior changes, live provider calls, registry pushes, servers, or browser verification are part of this scan-gate implementation.

## 13. Reverse proxy, TLS, and security headers

Static evidence:

- No committed Nginx or Caddy production config was found in the inspected repository paths.
- `docs/deploy-webui-cloud.md` includes optional Nginx reverse proxy and Certbot HTTPS guidance.
- Docker compose publishes the API port directly.
- No application-level security-header middleware, trusted-host middleware, or proxy-header middleware was confirmed in static inspection.

Checklist:

| Item | Status | Notes |
| --- | --- | --- |
| HTTPS only | Unknown / needs runtime validation | Docs include HTTP direct access examples. |
| HSTS | Missing / not confirmed | Should be set at proxy after HTTPS is stable. |
| X-Content-Type-Options | Missing / not confirmed | Add proxy or app header. |
| Referrer-Policy | Missing / not confirmed | Add conservative policy. |
| Permissions-Policy | Missing / not confirmed | Disable unused browser features. |
| Content-Security-Policy | Missing / needs design | Feasible but needs frontend asset/API review. |
| X-Frame-Options or `frame-ancestors` | Missing / not confirmed | Prevent clickjacking. |
| Request body size limit | Missing / not confirmed | Required for upload/API abuse control. |
| Timeout limits | Missing / not confirmed | Required for slow request/resource abuse. |
| Hide internal ports | Missing / not confirmed | Public baseline should expose only proxy 443. |
| Disable debug mode | Unknown / needs runtime validation | Production env values were not inspected. |
| Trusted proxy headers | Partial | Cookie Secure/IP handling depends on explicit trust settings. |
| Compression side channels | Unknown | Avoid compressing secret-bearing personalized responses where applicable. |

Recommendations:

- Ship a production reverse-proxy template with TLS, HSTS, security headers, body size limits, and timeouts.
- Bind the app to private/internal interfaces behind the proxy for public deployments.
- Add trusted-host/proxy-header handling and document required proxy headers.
- Treat direct `http://public-ip:8000` as local smoke/testing only, not production guidance.

## 14. API abuse and resource exhaustion

Assessment:

- Auth has limited in-memory IP failure throttling.
- No global per-IP/account/user quota layer was found for API routes.
- Scanner, analysis, backtest, provider/LLM, upload/image, report, and admin observability endpoints can be expensive or data-heavy.
- Pagination and query bounds exist in some admin list endpoints, but a uniform resource policy was not confirmed.
- Task queue and provider call limits need production capacity review.

Recommendations:

- Add per-IP, per-account, and per-user quotas for expensive routes.
- Add stricter admin-only gating for costly actions and exports.
- Add queue depth limits, concurrency limits, request timeouts, and circuit breakers for provider/LLM calls.
- Add upload size/type validation for image/upload routes.
- Add pagination bounds and query limits consistently across list/search endpoints.
- Add cache size/TTL bounds and cost-budget controls for scanner/backtest/provider flows.

## 15. Production deployment readiness checklist

| Item | Status | Severity | Evidence | Required action |
| --- | --- | --- | --- | --- |
| Strong password hashing | Needs improvement | High | Salted PBKDF2-SHA256 at 100,000 iterations | Move to Argon2id/bcrypt or stronger calibrated KDF; add migration |
| Strong password policy | Needs improvement | High | Minimum length is 6 | Raise minimum, block weak/common passwords |
| Login rate limit | Not production-ready | Blocker | Process-local IP-only limiter | Durable IP plus account throttling |
| Failed-login audit | Incomplete | Medium | No durable auth-failure audit confirmed | Add structured security events |
| MFA for admin | Missing | High | No MFA/TOTP/WebAuthn found | Design and require admin MFA |
| Secure cookies | Partial | High | Secure depends on HTTPS/proxy detection | Enforce production Secure cookies |
| HttpOnly cookies | Present | Already mitigated | Cookie params include `httponly=True` | Keep enabled |
| SameSite cookies | Present | Already mitigated | Cookie params include `samesite="lax"` | Keep or tighten after CSRF design |
| CSRF protection | Missing | Blocker | No token/origin verification found | Add CSRF strategy for write routes |
| CORS locked down | Needs deployment validation | Medium | Allowlist exists; wildcard disables credentials | Enforce prod allowlist |
| Admin route protection | Partial | High | Coarse `require_admin_user` | Add RBAC/capabilities and MFA |
| Admin security controls | Partial strength | Already mitigated / High gap | Disable/enable/revoke with audit and guardrails | Add RBAC, fail-closed audit policy |
| Secret scanning | Not confirmed | High | No scanner gate confirmed | Add CI/history scanning |
| Dependency scanning | Not confirmed | Medium | No audit gate confirmed | Add pip/npm scanning |
| Container scanning | Not confirmed | Medium | Docker build exists, scanner not confirmed | Add image scan |
| HTTPS/HSTS | Not enforced | Blocker | Deploy docs include HTTP direct access | Ship proxy/TLS/header template |
| Backups/restore | Unknown | Medium | Not assessed in static files | Define backup, restore, encryption |
| DB least privilege | Unknown | Medium | Production DB values not inspected | Define least-privilege DB role |
| Monitoring/alerts | Partial/unknown | Medium | Execution logs exist, alerting not confirmed | Add security alerts |
| Audit retention | Unknown | Medium | Execution/audit logs exist | Define retention, tamper resistance |

## 16. Recommended next Codex prompts

1. Auth hardening Phase 1: implement durable login rate limiting, failed-login audit events, and generic login errors. Constraints: do not print or inspect real secrets, preserve existing login/session compatibility, add focused tests only for auth behavior, and do not change frontend UI beyond required error handling.
2. Session cookie production hardening: enforce Secure/HttpOnly/SameSite production policy, review session rotation and admin idle timeout, and verify logout/session-revoke behavior. Constraints: no secret values, preserve existing cookie name where possible, document required proxy headers.
3. Admin RBAC/capability model design before implementation: produce a design doc for super-admin, security-admin, support-admin, and ops-admin capabilities. Constraints: docs/design only, no runtime behavior change, no migration.
4. CSRF/CORS production hardening: design and implement CSRF protection for cookie-authenticated write routes and strict production CORS allowlists. Constraints: preserve local developer workflow, no wildcard credentials, include API and frontend client tests.
5. Secret/dependency/deployment scan CI: add secret scanning, pip/npm audit, SAST, and container scanning gates. Constraints: do not update dependencies or rotate secrets in this task; report findings without printing secret values.
6. Security final QA pass: run static plus runtime validation against an isolated non-production environment. Constraints: use synthetic credentials only, no live provider/broker calls, no real secrets, and report ports and teardown steps.

## 17. Appendix: static evidence

Inspected files and documents:

- `README.md`
- `docs/CHANGELOG.md`
- `docs/audits/admin-data-control-center-design.md`
- `docs/audits/admin-data-schema-inventory.md`
- `docs/audits/admin-data-governance-next-phase-design.md`
- `docs/audits/admin-governance-cost-e2e-qa-runbook.md`
- `src/auth.py`
- `src/repositories/auth_repo.py`
- `src/postgres_identity_store.py`
- `api/deps.py`
- `api/v1/endpoints/auth.py`
- `api/v1/endpoints/admin_security.py`
- `api/v1/endpoints/admin_users.py`
- `api/v1/endpoints/admin_portfolio.py`
- `api/v1/endpoints/admin_cost.py`
- `src/services/admin_security_service.py`
- `src/services/admin_governance_audit_service.py`
- `src/services/execution_log_service.py`
- `src/services/admin_user_service.py`
- `src/services/admin_portfolio_service.py`
- `src/services/admin_activity_service.py`
- `src/utils/security.py`
- `api/app.py`
- `api/v1/router.py`
- `api/middlewares/auth.py`
- `api/middlewares/error_handler.py`
- `server.py`
- `main.py`
- `src/config.py`
- `.gitignore`
- `.env.example`
- `docker/Dockerfile`
- `docker/docker-compose.yml`
- `docs/DEPLOY.md`
- `docs/deploy-webui-cloud.md`
- `.github/workflows/*`
- `requirements.txt`
- `requirements-dev.txt`
- `pyproject.toml`
- `apps/dsa-web/package.json`
- `apps/dsa-web/package-lock.json`
- `apps/dsa-web/src/api/index.ts`
- `apps/dsa-web/src/api/auth.ts`
- `apps/dsa-web/src/api/adminUsers.ts`
- `apps/dsa-web/src/contexts/AuthContext.tsx`

Safe evidence snippets, conceptually:

- Password hashing path uses PBKDF2-SHA256, random salt, stored iteration count, and constant-time comparison.
- Login path applies in-memory IP failure tracking before password verification.
- Auth cookie params include HttpOnly, SameSite Lax, path, max-age, and conditional Secure.
- Current-user resolution validates signed token, server-side session state, revocation, expiration, and inactive user status.
- Admin endpoints use `require_admin_user` and security services enforce reason/confirmation guardrails for selected sensitive actions.
- Admin projections intentionally omit password hashes, raw session ids, raw broker payloads, raw prompt/provider payloads, and raw secret fields in inspected surfaces.
- CORS allows configured origins and disables credentials when wildcard mode is enabled.
- No explicit CSRF token/origin verification middleware was found in inspected files.
- `.env` exists locally but was listed path-only and not inspected; environment variable names were reviewed without printing values.
- Dependency and container scan gates were not confirmed in inspected workflow files.

Commands intentionally not run:

- No live servers.
- No browser verification.
- No live API calls.
- No dependency update or fix commands.
- No Docker builds.
- No migrations.
- No CI gate.
- No commands that print real `.env` values or secret material.
