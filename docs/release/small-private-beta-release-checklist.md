# Small Private Beta Release Checklist And Rollback Runbook

Status: private-beta operator checklist. This document does not approve public
launch, does not change release gates, and does not replace manual review.

Use this checklist only for a small, controlled private beta where the runtime
is already selected and the operator can verify the active process, route
identity, guest/auth behavior, consumer safety copy, admin boundary, and
rollback path.

Public launch remains **NO-GO**. Private-beta evidence is bounded,
authenticated, observation-first review evidence only. It must not be used as
approval for public launch, live quota/provider enforcement, global MFA/RBAC
runtime changes, production DB operations, broker/order/trade paths, external
notification sending, or auth/session/provider/quota runtime behavior changes.

## Evidence Pack Files

Use the JSON template and offline checker when the operator wants a
machine-checkable private-beta UAT record:

```bash
cp docs/release/private-beta-uat-evidence-template.json /tmp/private-beta-uat-evidence.json
# Fill /tmp/private-beta-uat-evidence.json with sanitized operator evidence.
python3 scripts/private_beta_uat_evidence_check.py --evidence /tmp/private-beta-uat-evidence.json
```

The checker validates structure, required fail-closed booleans, branch-aware
secret-scan evidence, rollback record, and public-launch NO-GO boundaries. It
does not open a browser, run Playwright, read credentials, call networks, query
runtime services, send notifications, mutate databases, or approve launch.

Template placeholders are intentionally not accepted as completed evidence. A
filled evidence record must use sanitized labels and evidence references only:
no real user, session, account, broker, provider, request, order, execution,
cookie, token, URL, stack trace, raw DOM dump, raw console dump, raw provider
payload, or private machine path.

## Candidate Scope

The private beta may review only bounded, authenticated, observation-first
surfaces that already expose sanitized, read-only, dry-run, or advisory
evidence. The operator record should identify which of these surface families
were sampled:

| Surface family | Private-beta use | Still not approved |
| --- | --- | --- |
| Guest/public preview | Confirm route identity and safe public copy. | No private product data exposure and no public launch approval. |
| Authenticated product routes | Confirm beta user route identity and observation-first product flows. | No broker/order/trade path, no personalized advice, no execution-ready claim. |
| Admin/operator routes | Confirm guest/non-admin denial and admin capability boundary. | Hidden navigation is not authorization; no auth/RBAC runtime change. |
| Provider/quota/admin diagnostics | Review sanitized advisory status and labels. | No provider runtime enforcement, no provider blocking, no live quota/global spend enforcement. |
| Storage/restore/rollback records | Record rollback target and operator runbook readiness. | No production DB migration, cleanup, restore, PITR, or retention execution. |
| Notification/cost evidence | Confirm dry-run/no-send wording where sampled. | No external notification sending from this evidence pack. |

## 1. Preflight

Record these values before UAT starts:

```bash
git fetch origin
git status --short --branch
git log --oneline -1
git log --oneline --decorate origin/main..HEAD
```

- [ ] Main baseline is clean and reviewed: no unexpected local dirty files, no
  staged files, and no merge conflicts.
- [ ] Current HEAD is recorded as the beta candidate commit.
- [ ] Runtime owner is recorded: server PID, process cwd, bound port, and the
  operator who started it.
- [ ] The port owner matches the intended beta runtime; do not reuse an unknown
  shared server as release evidence.
- [ ] Runtime topology is recorded as private-beta/single-runtime evidence when
  applicable; do not infer public ingress, multi-instance, or cross-instance
  SSE readiness from this record.
- [ ] Unauthenticated `GET /api/v1/market/market-briefing` returns 200 and any
  degraded response stays insufficient-data / observation-only.
- [ ] After login, `GET /api/v1/auth/me` returns 200 for the expected beta test
  user and does not expose secrets, cookies, raw session ids, or admin-only
  fields.

## 2. UAT Gates

All gates are fail-closed. A single fail blocks beta start until the owner either
fixes it or records an explicit manual exception.

| Gate | Pass condition | Evidence |
| --- | --- | --- |
| Route identity | Each tested URL keeps the intended canonical route, locale, and post-login redirect source. Legacy aliases may redirect only to the documented canonical route. | Final URL, route label, and redirect source. |
| Guest/public | Guest can use only public/preview surfaces; protected product routes show the intended guest overlay or redirect and do not mount private product data. | Guest route matrix and request paths. |
| Authenticated product pages | Logged-in beta user can reach the intended product pages without losing route identity. No broker/order path is exposed. | Auth route matrix after `/api/v1/auth/me` 200. |
| Admin route boundary | Guest redirects away from admin routes; logged-in non-admin sees an admin/capability gate; only admin/capability accounts see operator surfaces. Hidden navigation is not authorization. | Guest, non-admin, and admin/capability checks. |
| Raw leakage | Default-visible UI, accessibility text, and sampled exports/readback contain no raw JSON, provider payloads, prompts/responses, diagnostics, debug/trace/schema details, `MarketCache`, `/api/v1` internals, source refs, IDs, or backend snake_case terms. | DOM/accessibility scan, export/readback spot check, and manual spot check. |
| Advice leakage | No buy/sell/order CTA, target price, guaranteed return, personalized trading advice, position sizing, ideal entry, broker-ready, or execution-ready language appears. Fallback/stale/demo data never carries high-confidence trading posture. | DOM/accessibility scan and CTA inventory. |
| Console/network/overflow | Desktop and mobile UAT have no page console errors, no unexpected failed network calls, and no horizontal overflow. | Fresh browser evidence at release/UAT viewports. |

For route evidence, follow `docs/frontend/validation-playbook.md` and prefer
app-local Playwright commands with a task-owned port when the operator chooses
to run browser automation. Useful route-family harnesses include:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4181 npm --prefix apps/dsa-web run test:e2e -- e2e/uat-route-identity-auth-session.spec.ts --project=chromium
DSA_WEB_PLAYWRIGHT_PORT=4181 npm --prefix apps/dsa-web run test:e2e -- e2e/guest-entry-branding.smoke.spec.ts --project=chromium
DSA_WEB_PLAYWRIGHT_PORT=4181 npm --prefix apps/dsa-web run test:e2e -- e2e/route-truth-smoke-guard.spec.ts --project=chromium
DSA_WEB_PLAYWRIGHT_PORT=4181 npm --prefix apps/dsa-web run test:e2e -- e2e/shell-route-admin-affordance.smoke.spec.ts --project=chromium
DSA_WEB_PLAYWRIGHT_PORT=4181 npm --prefix apps/dsa-web run test:e2e -- e2e/admin-auth-harness.spec.ts --project=chromium
```

Playwright/live UAT is operator-run release evidence. Docs/checker maintenance
tasks do not run real UAT unless the operator explicitly requests it.

## 3. Disabled / Not-Approved Snapshot

Record these as explicit `false` / `NO-GO` fields in the evidence record:

- [ ] Public launch approved: no; public launch ready: no; public launch
  verdict: **NO-GO**.
- [ ] Live quota/global spend enforcement enabled by this pack: no.
- [ ] Provider runtime enforcement/provider blocking/provider order or fallback
  change enabled by this pack: no.
- [ ] Global MFA/RBAC/auth-session runtime behavior changed by this pack: no.
- [ ] Production DB migration, cleanup, retention, restore, or PITR executed by
  this pack: no.
- [ ] Broker/order/trade path exposed or validated by this pack: no.
- [ ] External notifications sent by this pack: no.
- [ ] Real credentials, users, sessions, accounts, broker/provider IDs, request
  IDs, URLs, stack traces, raw logs, or raw payloads included: no.

## 4. Manual Exceptions

All gates are fail-closed. If the operator records an exception, it must stay
bounded and must not override the forbidden domains above.

Minimum exception record:

```text
Gate:
Observed failure:
Why beta can proceed or why beta stays paused:
Approver role label:
Expiry / revisit condition:
Rollback trigger:
Forbidden-domain impact confirmed absent: yes/no
```

## 5. Validation Tiers

Use the smallest tier that matches the change and the beta decision.

### Worker Focused

Use during a bounded task before commit.

- Run focused tests for the changed route/module.
- Run changed-file lint/typecheck/build only when frontend source changed.
- For docs-only inner-loop work before commit, use `git diff --check` plus
  `./scripts/release_secret_scan.sh --local-only`; for branch review, batch
  landing, or release evidence, use
  `./scripts/release_secret_scan.sh --base-ref origin/main`.

### Batch Fast Gate

Use before pushing a batch of related beta-hardening commits.

- Require a clean tree.
- Validate branch diff against `origin/main`.
- Run all impacted route-family focused tests.
- Add frontend typecheck/build when frontend source changed.
- Escalate to `./scripts/ci_gate.sh` for backend auth/API, shared frontend
  infrastructure, workflow/lock changes, or protected-domain uncertainty.

### Release / UAT Gate

Use for the private beta candidate itself.

- Require a clean release candidate and recorded HEAD.
- Run full release/UAT route evidence for guest, auth, product, and admin
  boundary.
- Verify no raw leakage, no advice leakage, no console errors, no unexpected
  network failures, and no horizontal overflow.
- Run `./scripts/release_secret_scan.sh --base-ref origin/main` and any
  release-owned auth/RBAC, market-briefing, and rollback evidence checks
  required by the operator.
- Validate the filled sanitized JSON record when used:
  `python3 scripts/private_beta_uat_evidence_check.py --evidence <sanitized-private-beta-uat-evidence.json>`.
- Keep public launch approval separate; private beta evidence is not public GO.

## 6. Rollback Runbook

Rollback scope stays as narrow as the incident allows. Prefer `git revert`; do
not rewrite shared history.

### Trigger

Rollback or withdraw the beta when any of these fail after release:

- guest/public access exposes private product data;
- `/api/v1/auth/me` fails for valid beta users or exposes unsafe data;
- admin routes expose operator content to guest or non-admin users;
- raw provider/debug/schema/runtime details appear in default consumer UI;
- advice/order/execution language appears on consumer surfaces;
- `market-briefing` returns strong action language from insufficient or fallback
  inputs;
- the runtime owner, cwd, or port cannot be trusted.

### Steps

1. Record incident summary, current HEAD, runtime PID/cwd/port, and failing
   gate.
2. Revert the last beta commit or contiguous beta commit range:

```bash
git revert <beta_commit_sha>
# or, for a reviewed contiguous range:
git revert <oldest_beta_commit_sha>^..<newest_beta_commit_sha>
```

3. Restart only the intended beta runtime. Do not kill unrelated shared
   processes.
4. Verify guest/auth recovery:
   - unauthenticated `GET /api/v1/market/market-briefing` returns 200 with safe
     degraded semantics when applicable;
   - login succeeds for the beta test user;
   - authenticated `GET /api/v1/auth/me` returns 200;
   - admin boundary still gates guest and non-admin users.
5. Run the focused validation for the reverted area plus release secret scan.
6. Record rollback commit, push status, remaining risk, and whether beta remains
   paused or can resume.

## 7. Minimum Evidence Record

```text
Beta candidate HEAD:
Branch:
Clean tree / staged files absent:
Runtime PID/cwd/port owner:
Runtime topology / shared-server reuse:
Preflight status:
Unauth market-briefing 200:
Auth/me 200 after login:
Route identity:
Guest/public:
Authenticated product pages:
Admin boundary:
Raw leakage:
Advice leakage:
Console/network/horizontal overflow:
Release secret scan command and result:
Validation tier / checker result:
Rollback target:
Rollback method:
Manual exceptions / waivers:
Disabled/not-approved snapshot:
  public launch approved: no
  public launch ready: no
  live quota enforcement enabled: no
  provider runtime enforcement enabled: no
  broker/order/trade path enabled: no
  external notifications sent: no
  production DB operations executed: no
Secrets printed in evidence: no
Raw IDs/payloads/logs/URLs/stack traces in evidence: no
Manual release/public launch approval claimed: no
```
