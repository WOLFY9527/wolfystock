# Release Rollback Runbook

Date: 2026-05-07
Mode: docs-only operations runbook. No runtime code, tests, schema, frontend,
provider config, deployment scripts, data, or git history was changed.

## 1. Purpose

Use this runbook when a post-merge or staging release candidate needs a rollback
decision. The current main-branch release train is a readiness foundation, not a
public multi-user go-live: MFA enforcement, quota enforcement, provider circuit
enforcement, real Options provider decisioning, and multi-instance task-runtime
readiness still require separate approval and evidence.

Rollback must be based on commit group, data impact, feature flags, active user
impact, and schema/write behavior. Prefer `git revert` on shared branches. Do
not rewrite shared history.

Dry-run rollback rehearsal is evidence gathering only. It records the rollback
target, candidate operator steps, approval gates, and post-action verification
without running deployment commands, database actions, git history rewrites, or
production restore steps. A real rollback starts only after an operator approves
the specific action through the release process.

## 2. Rollback by Commit Group

| Group | Roll back when | Preferred first response |
| --- | --- | --- |
| Security/auth | Login, session, reauth, password KDF, MFA scaffold, or sensitive admin write behavior regresses. | Disable the exposed path or revert the smallest auth/security commit group after focused auth evidence. |
| RBAC | Capabilities, admin gates, route authorization, or compatibility fallback block valid operators or expose unauthorized access. | Use feature/UI gating where available, then revert the smallest RBAC route-family group. |
| Options | Options Lab black screen, unsafe trade-quality output, fixture/synthetic label loss, missing Greeks treated as valid, or route crash. | Withdraw Options route/UI entry first; revert Options commits if analysis-only safety cannot be restored. |
| Data Pipeline | `dataQualityReport`, required/important coverage, confidence caps, fast decision, or progressive enrichment metadata regresses. | Disable or hide affected decision surface if possible; revert Data Pipeline commits when payload interpretation is unsafe. |
| Cost/Quota | Ledger writes, pricing import, quota dry-run, owner attribution, or admin cost dashboard regresses. | Keep enforcement off; disable affected dashboard/import path; revert cost/quota group if data writes are wrong. |
| Provider Circuit | Diagnostics, dry-run counters, provider circuit storage/API/UI, or redaction regresses. | Disable diagnostics UI/probes first; revert provider circuit group if redaction or storage correctness is unsafe. |
| DB/schema | Additive indexes, table/storage foundations, migration/init behavior, or restore compatibility regresses. | Stop rollout and assess backup/restore path before reverting app commits; never roll back schema blindly. |
| Frontend-only | Route rendering, navigation, admin dashboard, Options Lab UI, or browser harness fails without backend/schema changes. | Hide route/UI entry or revert frontend-only commit group; preserve data and backend state. |
| Docs-only | Documentation is inaccurate, overclaims readiness, or conflicts with current runtime behavior. | Patch or revert docs-only commits; no runtime rollback needed. |

Rollback scope should stay as narrow as the incident allows. Do not revert an
entire release train when a feature flag, route withdrawal, or single commit
revert addresses the risk.

## 3. Pre-rollback Checks

Run these checks before choosing a rollback path:

```bash
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -40
```

Confirm:

- current branch and deployment target;
- worktree state and unrelated dirty files;
- exact commit or commit range under consideration;
- whether migrations, schema init, indexes, or storage models were touched;
- whether new data writes were introduced and whether they are reversible;
- feature flags, environment gates, route gates, or admin toggles that can
  disable exposure without deleting data;
- active sessions/users and whether logout, reauth, or session invalidation is
  required;
- whether background workers, scheduled jobs, provider probes, cost import jobs,
  or cleanup jobs are running;
- whether backup/PITR coverage exists before any DB-affecting action;
- whether incident evidence contains only safe labels and no secrets.

For DB/schema-adjacent rollbacks, stop and consult the backup/restore drill plan
before reverting application code. Application rollback and database restore
are different decisions.

## 4. Rollback Commands

Use explicit commands and review the diff before committing a rollback.

### Revert a single commit

```bash
git revert <commit_sha>
```

Then validate, inspect the generated commit, and push only through the approved
release process.

### Revert a commit range

Use this when the commits are contiguous and the whole range belongs to the same
rollback group:

```bash
git revert <oldest_commit_sha>^..<newest_commit_sha>
```

If the commits are not contiguous or include unrelated groups, revert individual
commits in a reviewed order.

### Disable a feature flag

Prefer this when the feature is already gated and disabling it avoids data loss:

```bash
# Example only. Use the actual approved flag/config path for the release.
export FEATURE_NAME_ENABLED=false
```

Record the flag name, previous value category, operator, time, and validation.
Do not print secret values.

### Stop using a route/UI without deleting data

For frontend-only or exposure-only incidents:

- remove or hide navigation entry points through an approved change;
- block route access behind an existing capability/flag where available;
- keep backend data, tables, ledgers, task rows, provider diagnostics, and
  artifacts intact;
- document how users can regain access after the fix.

Do not delete data to make a route disappear.

## 5. Post-rollback Validation

Run focused validation for the affected group. Full `ci_gate` may still be
required by release policy, but rollback triage should start with the smallest
reproducible checks.

| Area | Validation |
| --- | --- |
| Focused tests | Run tests for the reverted group: auth/RBAC, Options, Data Pipeline, cost/quota, provider circuit, DB/storage, or frontend route tests. |
| Browser harness | Use authenticated product/admin browser harnesses for routes that regressed in the browser. Check console cleanliness where the harness supports it. |
| Auth login/reauth | Confirm login, `/auth/me` or equivalent status, admin reauth, sensitive writes, and logout/session behavior for security/RBAC rollbacks. |
| Analysis quick decision | Confirm fast decision output respects `dataQualityReport`, required data, optional enrichment labels, and confidence caps. |
| Options Lab route | Confirm route loads, fixture/synthetic labels remain visible, missing Greeks or stale data cap decisions, and no order-placement posture appears. |
| Admin dashboards | Confirm admin logs, provider diagnostics, quota dry-run, model pricing, and cost summaries render without secrets or raw provider payloads. |
| DB/schema | Confirm app boot, migrations/init compatibility, index presence where expected, restore/read smoke where applicable, and no blind table deletion occurred. |

Minimum evidence:

```text
Rollback target:
Commit/tag:
Operator timestamp:
Gate status:
Rollback method:
Commit(s) reverted or flag/route disabled:
Data writes introduced: yes/no
Schema touched: yes/no
Backup/PITR checked: yes/no/not applicable
Focused tests:
Browser checks:
Auth/reauth checks:
Analysis/Options/Admin checks:
Remaining risk:
Secrets printed in evidence: no
```

Offline rehearsal evidence can be validated with:

```bash
python3 scripts/rollback_rehearsal_evidence.py --evidence <sanitized-rollback-rehearsal-evidence.json>
```

The helper accepts only sanitized JSON and returns `EVIDENCE-READY` for review
attachment, not release approval or launch GO. The artifact must include:

- commit and tag under review;
- operator timestamp and safe operator label;
- gate status that keeps launch approval manual;
- rollback plan with dry-run rehearsal, operator approval, diff review, data
  impact review, and verification-before-completion flags;
- focused verification steps, release secret scan, and diff check;
- explicit false values for external services, network calls, production secret
  reads, production data reads, runtime behavior changes, deployment commands,
  database actions, and git history changes.

Evidence must not include token, password, API key, session, cookie, DSN,
private-key, provider credential, credential-bearing URL, raw response, provider
payload, or raw log body values. Use stable reason codes, labels, and redacted
placeholders only.

## 6. Never Do

Do not:

- run `git reset` on a shared branch;
- run force-push, deployment, migration rollback, production restore, or
  database mutation commands from rehearsal evidence;
- delete production DB tables, rows, indexes, backups, restore points, or WAL
  history as a rollback shortcut;
- roll back schema blindly without understanding migrations, data writes,
  restore targets, and compatibility with the running app;
- print secrets, `.env` values, passwords, password hashes, TOTP secrets,
  recovery codes, API keys, provider credentials, broker credentials, webhook
  URLs, cookies, raw session ids, raw prompts, raw provider payloads, raw LLM
  responses, or production DB contents;
- hide synthetic/fallback/stale data labels to make validation pass;
- turn on MFA, quota, provider circuit, Options live-provider, or other
  enforcement behavior as part of rollback unless it is the approved rollback
  action;
- use retention cleanup as rollback;
- push rollback commits without the approved release process.

## 7. Decision Checklist

Before declaring rollback complete:

- rollback group is identified;
- chosen command or flag/route action matches the group;
- schema/data write risk is documented;
- active user/session impact is documented;
- focused validation passed or remaining blockers are listed;
- docs and release notes do not overclaim readiness;
- no runtime code, provider config, deployment script, or git history was
  changed outside the approved rollback action.
