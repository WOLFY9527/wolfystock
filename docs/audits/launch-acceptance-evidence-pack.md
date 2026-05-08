# Launch Acceptance Evidence Pack

Date: 2026-05-08
Branch checked: `main`
Mode: launch acceptance final matrix integration. No runtime API behavior,
frontend code, provider runtime, auth/MFA/RBAC runtime, cost/quota runtime,
scanner/market/options/portfolio/backtest/notification behavior, production
configuration, production secrets, or production data paths are changed by this
pack.

## 1. Purpose

The launch acceptance evidence pack defines the sanitized operator-supplied
evidence required to move public launch review from **NO-GO** toward manual
release review. It does not approve launch by itself.

The checker is:

```bash
python3 scripts/launch_acceptance_evidence.py \
  --evidence <sanitized-launch-acceptance-evidence.json>
```

For review attachment while blockers are still open:

```bash
python3 scripts/launch_acceptance_evidence.py \
  --evidence <sanitized-launch-acceptance-evidence.json> \
  --allow-no-go
```

The output is stable JSON with
`schemaVersion=wolfystock_launch_acceptance_evidence_summary_v1`.
`releaseApproved` is always `false`. The checker emits `finalStatus=NO-GO`
until every hard blocker has accepted sanitized evidence. When every category is
accepted, it emits `finalStatus=GO-REVIEW-REQUIRED`, which still requires a
human release approval.

The matrix also includes domain-local operator validator categories for
provider operations, real restore/PITR, security MFA/RBAC acceptance,
quota/budget evidence, staging ingress evidence, WS2/SSE topology operator
decisions, sanitized config snapshots, and manual release review records. These
categories recognize the local validator outputs and evidence guides as review
attachments only. The launch checker does not execute those validators, make
provider/network/DB calls, or approve launch.

`scripts/operator_evidence_bundle_check.py` is a review-support aggregation
tool for already-sanitized domain artifacts. It is not counted as separate
operator evidence and cannot replace any real artifact or manual approval.

## 2. Required Evidence Categories

All categories are hard blockers. Missing, pending, rejected, unsafe, or
incomplete evidence keeps the summary at **NO-GO**.

| Category id | Required operator evidence |
| --- | --- |
| `mfa_pilot_acceptance` | Accepted admin-only MFA pilot, recovery-path, rollback, unsupported/global rollout NO-GO, break-glass default-off, and sanitized audit evidence. |
| `rbac_fallback_disable_switch` | RBAC fallback disable switch or accepted production exception, complete route inventory, explicit-payload pass proof, legacy/missing-payload fail-closed proof, rollback, and sanitized audit evidence. |
| `provider_credential_staging_dry_run` | Provider credential staging dry-run, credential presence-only contract, entitlement matrix, and no checker live calls. |
| `provider_staging_probe_artifact` | Sanitized provider staging probe artifact with credential redaction, entitlement/freshness labels, operator capture metadata, and no checker live calls. |
| `provider_live_probe_opt_in_timeout` | Explicit provider live-probe opt-in for a named staging provider, bounded timeout, sanitized result evidence, and proof this checker made no live calls. |
| `provider_circuit_controlled_enforcement` | Controlled provider-circuit enforcement pilot, bounded route, rollback switch, and sanitized degraded-state evidence. This remains required even when current runtime support is not available. |
| `quota_pilot_acceptance` | Controlled quota pilot with explicit owner allowlist, out-of-scope advisory behavior, advisory-only invoice reconciliation, global enforcement disabled by default, rollback switch, and user/admin status-label evidence. |
| `budget_alert_dry_run_acceptance` | Sanitized dry-run budget alert intent, outbound delivery disabled by default, no live LLM/provider/invoice calls, and user/admin alert-label evidence. |
| `real_isolated_postgresql_restore_pitr` | Real isolated PostgreSQL restore, PITR execution, isolated target, and post-restore smoke evidence. |
| `staging_ingress_smoke` | HTTPS staging ingress smoke, backend port exposure proof, synthetic users/data, and live opt-in evidence. |
| `public_api_frontend_no_secret_safety` | Public API, frontend DOM, route payload, and release secret-scan no-secret evidence. |
| `supply_chain_dependency_build_artifact_safety` | Sanitized dependency-manifest inspection, build/test artifact scan, visible frontend build warnings, no dependency or lockfile changes, and NO-GO behavior for missing required evidence. |
| `incident_response_audit_evidence` | Sanitized incident-response evidence for admin-critical actions, preview-first cleanup, provider/notification/release failure paths, local no-network generation, and audit redaction. |
| `ws2_sse_topology_polling_fallback` | WS2 topology evidence proving process-local SSE limitation, durable polling fallback, API A/B visibility, owner isolation, and no runtime cutover. |
| `admin_log_retention_capacity_rehearsal` | Admin log retention/capacity rehearsal proving preview-first cleanup, minimum-retention guard, storage-pressure handling, sanitized audit event, and unchanged cleanup defaults. |
| `portfolio_backtest_export_browser_proof` | Portfolio/backtest export and browser proof covering no-advice wording, export/readback integrity, owner isolation, broker redaction, and no runtime mutation. |
| `notifications_delivery_rehearsal` | Notification delivery rehearsal with dry-run or synthetic delivery evidence, route/channel mapping, failure-path audit, secret redaction, and real outbound disabled unless explicitly accepted. |
| `user_data_privacy_export_deletion_rehearsal` | User data privacy rehearsal covering sanitized export projection, deletion preview, owner isolation, audit evidence, and no raw user/session/provider data exposure. |
| `market_data_freshness_fallback_evidence` | Market data freshness/fallback evidence with provider/as-of labels, stale/fallback disclosure, confidence cap behavior, no raw provider payloads, and unchanged fallback defaults. |
| `ai_report_guest_preview_safety` | AI report and guest-preview safety evidence covering preview-only mode, no raw prompt/LLM response exposure, no auto-analysis side effects, guest isolation, and safe no-advice labels. |
| `options_derivatives_safety` | Options derivatives safety evidence proving read-only/no-order posture, no broker or portfolio mutation, fixture/delayed/fallback caps, no guaranteed-return wording, and sanitized provider evidence. |
| `api_abuse_request_safety` | API abuse and request-safety evidence covering rate-limit/invalid-request handling, oversized payload safety, sanitized denial/audit output, no traceback/debug/request-body leakage, and unchanged runtime defaults. |
| `final_clean_full_ci_gate` | Clean worktree, full `ci_gate`, release secret scan, and final diff check evidence. |
| `provider_operator_evidence` | Accepted sanitized provider operator evidence from `scripts/provider_operator_evidence_check.py` and `docs/audits/provider-operator-evidence-guide.md`; advisory/review-gated, no validator provider calls, no raw provider payloads or credentials, and runtime behavior unchanged. |
| `restore_pitr_operator_evidence` | Accepted sanitized real restore/PITR operator evidence from `scripts/restore_pitr_operator_evidence_check.py` and `docs/audits/db-real-restore-pitr-operator-evidence-guide.md`; real restore artifact summary sanitized, no DB commands by the validator, production storage untouched, and manual review required. |
| `security_operator_acceptance` | Accepted sanitized MFA/RBAC operator acceptance from `scripts/security_operator_acceptance_check.py` and `docs/audits/security-operator-acceptance-evidence-guide.md`; MFA/RBAC sections accepted, `releaseApproved=false`, no auth/RBAC runtime mutation, and manual review required. |
| `quota_budget_operator_evidence` | Accepted sanitized quota/budget operator evidence from `scripts/quota_operator_evidence_check.py` and `docs/audits/quota-budget-operator-evidence-guide.md`; quota/budget sections accepted, no outbound notifications by the validator, no quota runtime mutation, and advisory review required. |
| `staging_ingress_operator_evidence` | Accepted sanitized staging ingress operator evidence from `scripts/staging_ingress_operator_evidence_check.py` and `docs/audits/staging-ingress-operator-evidence-guide.md`; artifact summary sanitized, no network calls by the validator, no ingress runtime mutation, and manual review required. |
| `ws2_sse_operator_decision_evidence` | Accepted sanitized WS2/SSE topology operator decision evidence from `scripts/ws2_sse_operator_decision_check.py` and `docs/audits/ws2-sse-operator-decision-evidence-guide.md`; process-local SSE limitation preserved, polling fallback or single-instance limitation recorded, no validator network calls, no runtime mutation, and manual review required. |
| `config_snapshot_evidence` | Accepted sanitized config snapshot evidence from `scripts/config_snapshot_evidence_check.py` and `docs/audits/config-snapshot-operator-evidence-guide.md`; auth/provider/quota/database summaries recorded, secret posture represented only as presence/redacted labels, no raw config/env values, no runtime mutation, and manual review required. |
| `manual_release_approval_review_record` | Accepted sanitized manual release review-record evidence from `scripts/manual_release_approval_evidence_check.py` and `docs/audits/manual-release-approval-evidence-guide.md`; review record sanitized, `releaseApproved=false`, `launchApproved=false`, no automatic approval derived from input, and release approval remains external/manual. |

## 3. Input Contract

Input JSON uses:

```json
{
  "schemaVersion": "wolfystock_launch_acceptance_evidence_input_v1",
  "mode": "operator_sanitized",
  "categories": {
    "mfa_pilot_acceptance": {
      "status": "accepted",
      "acceptedBy": "release-operator",
      "capturedAt": "2026-05-07T00:00:00Z",
      "evidenceRef": "mfa-admin-pilot-evidence-json",
      "checks": {
        "adminPilotPassed": true,
        "adminOnlyScopeRecorded": true,
        "unsupportedGlobalRolloutNoGo": true,
        "recoveryPathTested": true,
        "breakGlassDisabledByDefault": true,
        "rollbackPlanRecorded": true,
        "auditEvidenceSanitized": true,
        "secretEvidenceRedacted": true
      },
      "sanitization": {
        "externalServicesCalledByChecker": false,
        "realSecretsIncluded": false,
        "rawCredentialValuesIncluded": false,
        "rawProviderPayloadsIncluded": false,
        "responseBodiesIncluded": false,
        "productionDataPathsIncluded": false
      }
    }
  }
}
```

The checker accepts `true` or `"pass"` for required checks. Every accepted
category must include `acceptedBy`, `capturedAt`, `evidenceRef`, all required
checks, and all sanitization fields. `evidenceRef` should be an attachable,
sanitized label or artifact id, not a secret-bearing URL, DSN, credential,
response body, provider payload, or production data path.

Synthetic examples live at:

- `tests/fixtures/release/launch_acceptance_evidence.missing.json`
- `tests/fixtures/release/launch_acceptance_evidence.accepted.json`

## 4. Safety Rules

The checker never:

- reads raw `.env` or production secret files;
- reads production data paths;
- opens network sockets or calls external services;
- executes restore commands, provider calls, auth flows, quota enforcement, or
  frontend/browser checks;
- changes runtime defaults or deployment configuration;
- prints secret values, DSNs, tokens, cookies, provider payloads, response
  bodies, API keys, session/cookie values, provider credentials, debug
  payloads, tracebacks, request bodies, or raw production paths.

Operator evidence must be summarized before it is attached. The checker rejects
secret-like strings and sensitive fields without echoing the sensitive value.

## 5. Review Use

Release review should attach:

- `scripts/release_gate_summary.sh --go-no-go-json` output.
- `scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>` output.
- `scripts/launch_acceptance_evidence.py --evidence <sanitized-launch-acceptance-evidence.json>` output for every final matrix category, including the domain-local rehearsal tracks now split into explicit blockers.
- Domain-local validator outputs for accepted operator artifacts:
  `scripts/provider_operator_evidence_check.py`,
  `scripts/restore_pitr_operator_evidence_check.py`,
  `scripts/security_operator_acceptance_check.py`,
  `scripts/quota_operator_evidence_check.py`, and
  `scripts/staging_ingress_operator_evidence_check.py`.
- Review-support bundle summary from
  `scripts/operator_evidence_bundle_check.py <sanitized-operator-evidence-dir>`.
  This summary aggregates validator statuses only and must not be treated as a
  substitute for real operator artifacts.
- WS2/SSE topology operator decision evidence from
  `scripts/ws2_sse_operator_decision_check.py <sanitized-ws2-sse-operator-decision.json>`.
- Config snapshot evidence from
  `scripts/config_snapshot_evidence_check.py <sanitized-config-snapshot-evidence.json>`.
- Manual release review-record validation from
  `scripts/manual_release_approval_evidence_check.py --artifact <sanitized-manual-release-review-record.json>`.
  A valid record still emits `releaseApproved=false` and does not approve
  launch.
- `scripts/incident_response_evidence.py --evidence <sanitized-incident-response-evidence.json>` output for incident/audit sanitization evidence.
- `scripts/backup_restore_drill_check.sh` output for synthetic preflight and,
  when available, accepted sanitized real restore/PITR evidence.
- `scripts/staging_ingress_smoke.py` dry-run or explicitly opted-in staging
  output.
- `scripts/release_secret_scan.sh`, final `./scripts/ci_gate.sh`, and
  `git diff --check` results from the clean release candidate.

Until all hard blockers are accepted, the final launch verdict remains
**NO-GO**.

## 6. Provider Staging Probe Evidence

Provider credential staging may attach a sanitized live-probe readiness summary
only when the operator explicitly opts in for a named staging provider. The
summary must prove:

- live probe opt-in was recorded for the provider and route under review;
- timeout is bounded to the accepted probe window;
- credential evidence is presence/count/state only;
- no raw credential value, env value, DSN, provider URL, response body, or raw
  provider payload or raw response body is attached;
- checker/runtime defaults still report `liveHttpCallsEnabled=false` and
  `networkCallExecuted=false` unless the operator runs a separate controlled
  staging probe outside this checker.

Default diagnostics and evidence validation must remain no-network. A provider
with missing, partial, or malformed credentials is fail-closed even when a probe
opt-in label is present.

## 7. Budget Alert and Incident Evidence

Budget-alert acceptance is a separate category from quota-pilot acceptance.
Quota evidence proves the controlled pilot boundary and rollback posture;
budget-alert evidence proves only sanitized dry-run alert intent, disabled real
outbound delivery, no live LLM/provider/invoice calls, and safe user/admin
alert labels.

Incident-response/audit evidence is represented in the launch matrix by
`incident_response_audit_evidence`. The underlying detailed attachment can be
generated by `scripts/incident_response_evidence.py`, but the launch acceptance
checker still requires an explicit accepted category in the final matrix before
the summary can move from **NO-GO** to `GO-REVIEW-REQUIRED`.
