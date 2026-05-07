# Launch Acceptance Evidence Pack

Date: 2026-05-07
Branch checked: `main`
Mode: launch acceptance evidence schema/checklist. No runtime API behavior,
frontend code, provider runtime, auth/MFA/RBAC runtime, cost/quota runtime,
scanner/market/options/portfolio/backtest/notification behavior, production
configuration, production secrets, or production data paths are changed by this
pack.

## 1. Purpose

The launch acceptance evidence pack defines the sanitized operator-supplied
evidence required to move public launch review from **NO-GO** toward a manual
GO decision. It does not approve launch by itself.

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

## 2. Required Evidence Categories

All categories are hard blockers. Missing, pending, rejected, unsafe, or
incomplete evidence keeps the summary at **NO-GO**.

| Category id | Required operator evidence |
| --- | --- |
| `mfa_pilot_acceptance` | Accepted admin-only MFA pilot, recovery-path, rollback, unsupported/global rollout NO-GO, break-glass default-off, and sanitized audit evidence. |
| `rbac_fallback_disable_switch` | RBAC fallback disable switch or accepted production exception, complete route inventory, explicit-payload pass proof, legacy/missing-payload fail-closed proof, rollback, and sanitized audit evidence. |
| `provider_credential_staging_dry_run` | Provider credential staging dry-run, explicit opt-in live probe contract, credential presence-only contract, entitlement matrix, and no checker live calls. |
| `provider_circuit_controlled_enforcement` | Controlled provider-circuit enforcement pilot, bounded route, rollback switch, and sanitized degraded-state evidence. This remains required even when current runtime support is not available. |
| `quota_pilot_acceptance` | Controlled quota pilot with explicit owner allowlist, out-of-scope advisory behavior, sanitized dry-run budget alert intent, advisory-only invoice reconciliation, outbound delivery disabled by default, no live LLM/provider/invoice calls, rollback switch, and user/admin status-label evidence. |
| `real_isolated_postgresql_restore_pitr` | Real isolated PostgreSQL restore, PITR execution, isolated target, and post-restore smoke evidence. |
| `staging_ingress_smoke` | HTTPS staging ingress smoke, backend port exposure proof, synthetic users/data, and live opt-in evidence. |
| `public_api_frontend_no_secret_safety` | Public API, frontend DOM, route payload, and release secret-scan no-secret evidence. |
| `final_clean_full_ci_gate` | Clean worktree, full `ci_gate`, release secret scan, and final diff check evidence. |

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
  bodies, or raw production paths.

Operator evidence must be summarized before it is attached. The checker rejects
secret-like strings and sensitive fields without echoing the sensitive value.

## 5. Review Use

Release review should attach:

- `scripts/release_gate_summary.sh --go-no-go-json` output.
- `scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>` output.
- `scripts/launch_acceptance_evidence.py --evidence <sanitized-launch-acceptance-evidence.json>` output.
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
  provider payload is attached;
- checker/runtime defaults still report `liveHttpCallsEnabled=false` and
  `networkCallExecuted=false` unless the operator runs a separate controlled
  staging probe outside this checker.

Default diagnostics and evidence validation must remain no-network. A provider
with missing, partial, or malformed credentials is fail-closed even when a probe
opt-in label is present.
