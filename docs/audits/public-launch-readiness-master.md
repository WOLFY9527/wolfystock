# Public Launch Readiness Master

Status: Current
Date: 2026-05-08
Branch checked: `main`
Owner domain: Release readiness
Related docs: `docs/audits/public-launch-gap-register.md`,
`docs/audits/deployment-readiness-checklist.md`,
`docs/audits/launch-acceptance-evidence-pack.md`,
`docs/audits/incident-response-audit-evidence-pack.md`,
`docs/audits/operator-evidence-real-runbook.md`,
`docs/audits/operator-evidence-dry-run-handoff.md`,
`docs/audits/operator-evidence-redaction-checklist.md`,
`docs/archive/audits/final-pre-push-audit.md`,
`docs/audits/known-test-warnings-register.md`

Mode: launch readiness summary. The current docs hygiene pass updates launch
navigation/status wording only; no runtime API behavior, production deployment
config, frontend app code, provider configuration, migrations, market-rotation
source/tests, or production data paths were changed.

## Executive verdict

Current public launch status: **NO-GO**.

The system is suitable only for reviewed non-launch integration work until the
blocking gates below are closed or explicitly accepted as production exceptions.
Existing foundations are useful, but several launch-critical surfaces remain
scaffolded, observational, fixture-only, single-process-limited, or missing
staging evidence.

Market Rotation Radar is a current read-only product capability, not a launch
blocker and not launch approval evidence. It does not change provider
entitlement, freshness, quota, security, owner-isolation, or deployment gates.

The operator evidence pack now defines the sanitized acceptance schema for the
remaining launch blockers through
`python3 scripts/launch_acceptance_evidence.py --evidence <sanitized-launch-acceptance-evidence.json>`.
The companion incident-response pack is
`python3 scripts/incident_response_evidence.py --evidence <sanitized-incident-response-evidence.json>`.
It never approves launch by itself; `releaseApproved` remains false and the
public launch verdict stays **NO-GO** unless every hard blocker has accepted
operator evidence.

The final matrix now tracks the current domain-local rehearsal evidence as
explicit release categories instead of bundling it into broad foundation notes.
This includes WS2/SSE topology limitations, admin log retention/capacity,
portfolio/backtest browser and export proof, notification delivery, user data
privacy/export/deletion, market freshness/fallback, AI guest-preview safety,
Options derivatives safety, and API abuse/request-safety evidence.

Offline validator/template coverage for API abuse/request-safety, provider,
provider SLA/licensing, notification delivery rehearsal, restore/PITR,
security MFA/RBAC, quota/budget, staging ingress, WS2/SSE, config snapshot, and
manual release review-record evidence is now consolidated into
`docs/audits/operator-evidence-real-runbook.md`. That coverage only proves the
local validators and sanitized templates exist. Real operator-produced
artifacts are still required for launch review, and final approval remains
manual. `scripts/operator_evidence_bundle_check.py` remains only an aggregation
aid for already-sanitized domain artifacts. None of these helpers grants
release approval, and `releaseApproved` remains false in machine-readable
launch evidence.

The offline operator evidence workflow is now documented as a reviewer support
path: generate sanitized templates with
`scripts/operator_evidence_template_pack.py`, fill them manually with sanitized
operator artifacts, run the category validators, create and verify checksum
metadata with `scripts/operator_evidence_manifest_check.py`, aggregate with
`scripts/operator_evidence_bundle_check.py`, and render a bounded report with
`scripts/release_review_report_render.py`. These steps improve review
traceability only. They do not create real operator evidence, satisfy missing
hard blockers, or replace the external/manual release decision.

## Master readiness view

| Area | Current posture | Launch status | Blocking requirement |
| --- | --- | --- | --- |
| Security, MFA, RBAC | Password KDF hardening, encrypted MFA secret foundation, disabled-by-default MFA pilot guards, and RBAC readiness coverage exist, but global login MFA enforcement remains disabled, production key/recovery operations are not launch-accepted, recovery-code acceptance remains incomplete, and coarse admin compatibility fallback remains. | **NO-GO** | Production MFA key/recovery acceptance, staged MFA enforcement pilot, R5 RBAC fallback inventory/observe/fail-closed plan, route/capability audit, and rollback evidence. |
| Provider, Options, data quality | Provider SLA/readiness diagnostics and Options/Data Pipeline foundations exist, but Options live providers remain disabled or fixture/synthetic, provider entitlement/freshness is not launch-accepted, and data-quality caps/disclosures must stay visible. | **NO-GO** | Provider-by-route entitlement matrix, real Options adapter/staged provider evidence before live decisioning, data freshness/as-of/fallback labels, and degraded-state dashboard evidence. |
| Portfolio and backtest safety | Public-safety evidence now covers owner-scoped portfolio export-like reads, admin portfolio redaction, backtest support exports, no-advice/order-verb checks, missing-data disclosure, and golden metric fixtures. Public launch still requires broader accounting invariant, mutation-guard, and staged owner-isolation acceptance. | **NO-GO** | Complete remaining portfolio accounting invariant tests, route-wide mutation guards, staged owner-isolation smoke, and release-candidate no-secret/no-advice evidence. |
| WS2 and multi-instance runtime | Durable task/progress foundations and worker prototype exist, but process-local SSE remains the default and no accepted staging multi-instance smoke proves API A/B plus worker behavior. | **NO-GO** | Executable WS2 smoke proving API A submit, worker lease, API B durable read, polling replay, owner isolation, retry/failure safety, and explicit SSE limitation handling. |
| Cost, quota, provider circuit | Cost ledger, quota dry-run helpers, quota enforcement pilot-readiness preflight, and provider circuit diagnostics exist. A default-off, owner-allowlisted sync single-stock analysis quota pilot can block only that route when explicitly enabled, but accepted operator/staging evidence, admin visibility, owner/guest accounting acceptance, invoice reconciliation, broad quota enforcement, and provider circuit enforcement remain incomplete. | **NO-GO** | Accept sanitized evidence for the low-risk quota route pilot, then complete one provider circuit enforcement pilot behind rollback switches, with budget/status UI labels and staging degraded evidence. |
| Deployment, backup, rollback | Deployment checklist, local backup/restore dry-run preflight, release secret-scan, admin harness coverage, and a safe staging-ingress dry-run/live opt-in preflight exist, but launch still lacks accepted isolated PostgreSQL restore/PITR drill, retention tiers, real staging ingress proof, and final release-candidate gate. | **NO-GO** | Clean release-candidate gate, clean worktree, HTTPS reverse-proxy smoke with attached ingress evidence, no public backend `:8000`, backup/restore drill, retention dry runs, rollback plan, and owner-isolation smoke. |
| Final gate requirements | Docs-only checks can validate this document, but they do not prove runtime readiness. | **NO-GO** | Every item in `deployment-readiness-checklist.md` section 10 must be checked or explicitly accepted as a documented production exception. |

## Manual Release Criteria

Public launch may leave **NO-GO** only through an external/manual release
decision after all of the following are true:

- `./scripts/ci_gate.sh` is clean on the release candidate.
- `scripts/release_secret_scan.sh` is clean on the release candidate. By
  default it scans committed branch changes from the release base ref plus
  staged, unstaged, and untracked text files; it is still not a replacement for
  a full enterprise DLP or historical secret-audit program.
- `git status --short` is clean before tagging or deploying.
- Staging smoke passes through HTTPS reverse proxy with synthetic users and
  data. The available helper is
  `WOLFYSTOCK_STAGING_INGRESS_SMOKE=1 python3 scripts/staging_ingress_smoke.py --base-url "$STAGING_INGRESS_BASE_URL"`;
  without the opt-in env var it produces dry-run evidence only.
- WS2 multi-instance smoke passes, or deployment is explicitly constrained to
  single API process with documented task/SSE limitations.
- Public ingress exposes only 80/443 and does not expose backend `:8000`
  directly.
- Production `.env` posture is reviewed for production mode, auth, CORS, CSRF,
  trusted proxy, and secret handling through
  `python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>`
  without printing raw `.env` or secret values.
- Sanitized operator acceptance evidence is attached through
  `python3 scripts/launch_acceptance_evidence.py --evidence <sanitized-launch-acceptance-evidence.json>`
  for MFA pilot acceptance, RBAC fallback disable switch, provider credential
  staging dry-run, provider staging probe artifact, provider live probe opt-in
  and bounded timeout, provider circuit controlled enforcement, quota pilot,
  budget-alert dry-run, real isolated PostgreSQL restore/PITR, staging ingress
  smoke, public API/frontend no-secret public safety, supply-chain/build
  artifact safety, incident-response/audit evidence, WS2/SSE topology
  limitation with polling fallback, admin log retention/capacity rehearsal,
  portfolio/backtest export and browser proof, notification delivery
  rehearsal, user data privacy/export/deletion rehearsal, market data
  freshness/fallback evidence, AI report/guest-preview safety, Options
  derivatives safety, API abuse/request-safety evidence, final clean full
  `ci_gate`, and the domain-local operator validator categories for API
  abuse/request-safety, provider, provider SLA/licensing, notification delivery
  rehearsal, restore/PITR, security MFA/RBAC, quota/budget, staging ingress,
  WS2/SSE operator decision, config snapshot, and manual release review-record
  evidence.
- Sanitized evidence templates may be generated through
  `python3 scripts/operator_evidence_template_pack.py <template-dir>`, then
  manually filled by operators with sanitized target-environment artifact
  summaries. Blank or placeholder templates, synthetic fixtures, local dry-run
  output, and checker success are not accepted production evidence.
- Sanitized file-integrity metadata may be created and verified through
  `python3 scripts/operator_evidence_manifest_check.py create --artifact-dir <sanitized-operator-evidence-dir> --output <manifest.json>`
  and
  `python3 scripts/operator_evidence_manifest_check.py verify --artifact-dir <sanitized-operator-evidence-dir> --manifest <manifest.json>`.
- Review-support bundle output may be attached through
  `python3 scripts/operator_evidence_bundle_check.py <sanitized-operator-evidence-dir>`,
  but it aggregates existing artifacts only and does not count as a separate
  launch artifact.
- A bounded offline review report may be rendered through
  `python3 scripts/release_review_report_render.py <bundle-summary.json> --manifest <manifest-summary.json>`;
  the report supports manual review only and cannot approve release from
  arbitrary input.
- WS2/SSE operator decision evidence is validated through
  `python3 scripts/ws2_sse_operator_decision_check.py <sanitized-ws2-sse-operator-decision.json>`
  without changing SSE or polling runtime behavior.
- Config snapshot evidence is validated through
  `python3 scripts/config_snapshot_evidence_check.py <sanitized-config-snapshot-evidence.json>`
  without reading raw `.env` values, deployment state, or secrets.
- Manual release review-record evidence is validated through
  `python3 scripts/manual_release_approval_evidence_check.py --artifact <sanitized-manual-release-review-record.json>`;
  the validator always keeps `releaseApproved=false` and cannot approve
  release from arbitrary input.
- Sanitized incident-response evidence is attached through
  `python3 scripts/incident_response_evidence.py --evidence <sanitized-incident-response-evidence.json>`
  for admin-critical audit events, preview-first cleanup, provider/notification
  failure paths, release-check failures, and local no-secret generation.
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
- Use `launch-acceptance-evidence-pack.md` as the operator-supplied evidence
  schema and review checklist.
- Use this file as the concise executive master view.
- Use `known-test-warnings-register.md` for expected warnings and cleanup
  ownership.

Do not treat archived historical audit docs as current launch control. Any
future consolidation should follow
`docs/archive/audits/markdown-consolidation-plan.md` in a separate approved
task.
