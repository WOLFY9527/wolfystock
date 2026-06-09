# Small Private Beta Release Checklist And Rollback Runbook

Status: private-beta operator checklist. This document does not approve public
launch, does not change release gates, and does not replace manual review.

Use this checklist only for a small, controlled private beta where the runtime
is already selected and the operator can verify the active process, route
identity, guest/auth behavior, consumer safety copy, admin boundary, and
rollback path.

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
| Raw leakage | Default-visible UI and accessibility text contain no raw JSON, provider payloads, diagnostics, debug/trace/schema details, `MarketCache`, or backend snake_case terms. | DOM/accessibility scan and manual spot check. |
| Advice leakage | No buy/sell/order CTA, target price, guaranteed return, personalized trading advice, or execution-ready language appears. Fallback/stale/demo data never carries high-confidence trading posture. | DOM/accessibility scan and CTA inventory. |
| Console/network/overflow | Desktop and mobile UAT have no page console errors, no unexpected failed network calls, and no horizontal overflow. | Fresh browser evidence at release/UAT viewports. |

Do not use Playwright for T-1355 validation; this section describes the beta
operator gate that must be collected by the release/UAT owner.

## 3. Validation Tiers

Use the smallest tier that matches the change and the beta decision.

### Worker Focused

Use during a bounded task before commit.

- Run focused tests for the changed route/module.
- Run changed-file lint/typecheck/build only when frontend source changed.
- For docs-only work, use `git diff --check` plus local secret scan.

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
- Run release secret scan and any release-owned auth/RBAC, market-briefing, and
  rollback evidence checks required by the operator.
- Keep public launch approval separate; private beta evidence is not public GO.

## 4. Rollback Runbook

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

## 5. Minimum Evidence Record

```text
Beta candidate HEAD:
Runtime PID/cwd/port owner:
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
Validation tier:
Rollback target:
Rollback method:
Secrets printed in evidence: no
Manual release/public launch approval claimed: no
```
