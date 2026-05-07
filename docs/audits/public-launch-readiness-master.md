# Public Launch Readiness Master

Status: Current
Date: 2026-05-07
Branch checked: `main`
Owner domain: Release readiness
Related docs: `docs/audits/public-launch-gap-register.md`,
`docs/audits/deployment-readiness-checklist.md`,
`docs/audits/final-pre-push-audit.md`,
`docs/audits/known-test-warnings-register.md`

Mode: launch readiness summary. The current ingress update adds synthetic
deployment-readiness script/tests/docs only; no runtime API behavior, production
deployment config, frontend app code, provider configuration, migrations, or
production data paths were changed.

## Executive verdict

Current public launch status: **NO-GO**.

The system is suitable only for reviewed non-launch integration work until the
blocking gates below are closed or explicitly accepted as production exceptions.
Existing foundations are useful, but several launch-critical surfaces remain
scaffolded, observational, fixture-only, single-process-limited, or missing
staging evidence.

## Master readiness view

| Area | Current posture | Launch status | Blocking requirement |
| --- | --- | --- | --- |
| Security, MFA, RBAC | Password KDF hardening, encrypted MFA secret foundation, disabled-by-default MFA pilot guards, and RBAC readiness coverage exist, but global login MFA enforcement remains disabled, production key/recovery operations are not launch-accepted, recovery-code acceptance remains incomplete, and coarse admin compatibility fallback remains. | **NO-GO** | Production MFA key/recovery acceptance, staged MFA enforcement pilot, R5 RBAC fallback inventory/observe/fail-closed plan, route/capability audit, and rollback evidence. |
| Provider, Options, data quality | Provider SLA/readiness diagnostics and Options/Data Pipeline foundations exist, but Options live providers remain disabled or fixture/synthetic, provider entitlement/freshness is not launch-accepted, and data-quality caps/disclosures must stay visible. | **NO-GO** | Provider-by-route entitlement matrix, real Options adapter/staged provider evidence before live decisioning, data freshness/as-of/fallback labels, and degraded-state dashboard evidence. |
| Portfolio and backtest safety | Public-safety evidence now covers owner-scoped portfolio export-like reads, admin portfolio redaction, backtest support exports, no-advice/order-verb checks, missing-data disclosure, and golden metric fixtures. Public launch still requires broader accounting invariant, mutation-guard, and staged owner-isolation acceptance. | **NO-GO** | Complete remaining portfolio accounting invariant tests, route-wide mutation guards, staged owner-isolation smoke, and release-candidate no-secret/no-advice evidence. |
| WS2 and multi-instance runtime | Durable task/progress foundations and worker prototype exist, but process-local SSE remains the default and no accepted staging multi-instance smoke proves API A/B plus worker behavior. | **NO-GO** | Executable WS2 smoke proving API A submit, worker lease, API B durable read, polling replay, owner isolation, retry/failure safety, and explicit SSE limitation handling. |
| Cost, quota, provider circuit | Cost ledger, quota dry-run helpers, quota enforcement pilot-readiness preflight, and provider circuit diagnostics exist, but live quota enforcement and provider circuit enforcement are not active route-boundary controls. | **NO-GO** | One low-risk live quota enforcement pilot and one provider circuit enforcement pilot behind rollback switches, with budget/status UI labels and staging degraded evidence. |
| Deployment, backup, rollback | Deployment checklist, local backup/restore dry-run preflight, release secret-scan, admin harness coverage, and a safe staging-ingress dry-run/live opt-in preflight exist, but launch still lacks accepted isolated PostgreSQL restore/PITR drill, retention tiers, real staging ingress proof, and final release-candidate gate. | **NO-GO** | Clean release-candidate gate, clean worktree, HTTPS reverse-proxy smoke with attached ingress evidence, no public backend `:8000`, backup/restore drill, retention dry runs, rollback plan, and owner-isolation smoke. |
| Final gate requirements | Docs-only checks can validate this document, but they do not prove runtime readiness. | **NO-GO** | Every item in `deployment-readiness-checklist.md` section 10 must be checked or explicitly accepted as a documented production exception. |

## GO criteria

Public launch may move to **GO** only when all of the following are true:

- `./scripts/ci_gate.sh` is clean on the release candidate.
- `scripts/release_secret_scan.sh` is clean on the release candidate. This is a
  lightweight changed-file smoke check for obvious secrets, not a replacement
  for a full enterprise DLP or historical secret-audit program.
- `git status --short` is clean before tagging or deploying.
- Staging smoke passes through HTTPS reverse proxy with synthetic users and
  data. The available helper is
  `WOLFYSTOCK_STAGING_INGRESS_SMOKE=1 python3 scripts/staging_ingress_smoke.py --base-url <staging-ingress-base-url>`;
  without the opt-in env var it produces dry-run evidence only.
- WS2 multi-instance smoke passes, or deployment is explicitly constrained to
  single API process with documented task/SSE limitations.
- Public ingress exposes only 80/443 and does not expose backend `:8000`
  directly.
- Production `.env` posture is reviewed for production mode, auth, CORS, CSRF,
  trusted proxy, and secret handling without printing secret values.
- MFA enforcement prerequisites are complete, or public admin access is blocked
  behind a documented compensating control.
- Backup/restore drill passes in an isolated environment.
- Local backup/restore dry-run preflight passes with fresh synthetic or
  sanitized metadata before the real drill.
- Rollback plan names last-good commit/image, DB restore decision point, health
  checks, and owner-isolation smoke.
- Retention dry-run reports exist for high-growth domains.
- Cost/quota and provider circuit enforcement status is explicitly labeled so
  diagnostics are not mistaken for hard spend/provider controls.

## Warning posture

Known warnings are tracked separately in
`docs/audits/known-test-warnings-register.md`.

Current warning verdict:

- Blocking warnings: none in the current warning register.
- Resolved warnings: Pydantic backtest serializer warning.
- Isolated/non-blocking warnings: websockets/lark_oapi deprecation warning and
  Eastmoney unverified HTTPS warning.
- Still-open/non-blocking warnings: existing Vite chunk-size warning.

These warnings do not change the launch verdict. The launch verdict remains
**NO-GO** because of the readiness blockers above, not because of the currently
registered warnings.

## Source-of-truth split

- Use `public-launch-gap-register.md` as the detailed blocker register.
- Use `deployment-readiness-checklist.md` as the release-candidate checklist.
- Use this file as the concise executive master view.
- Use `known-test-warnings-register.md` for expected warnings and cleanup
  ownership.

Do not delete, move, or consolidate older audit docs as part of this master
view. Any consolidation should follow `markdown-consolidation-plan.md` in a
separate approved task.
