# Incident Response Audit Evidence Pack

Date: 2026-05-07
Branch checked: `main`
Mode: incident-response evidence schema/checklist. No runtime API behavior,
frontend code, provider runtime, auth/MFA/RBAC runtime, cost/quota runtime,
scanner/market/options/portfolio/backtest/notification behavior, production
configuration, production secrets, or production data paths are changed by this
pack.

## 1. Purpose

This pack defines the sanitized operator evidence required to prove incident
response and auditability without exposing secrets, raw payloads, or destructive
cleanup behavior.

The checker is:

```bash
python3 scripts/incident_response_evidence.py \
  --evidence <sanitized-incident-response-evidence.json>
```

For review attachment while evidence is still incomplete:

```bash
python3 scripts/incident_response_evidence.py \
  --evidence <sanitized-incident-response-evidence.json> \
  --allow-no-go
```

The output is stable JSON with
`schemaVersion=wolfystock_incident_response_evidence_v1`.
`releaseApproved` is always `false`. The checker emits `finalStatus=NO-GO`
until every required incident-response category is satisfied. It never approves
launch by itself.

## 2. Required Evidence Categories

All categories are hard requirements for the pack.

| Category id | Required operator evidence |
| --- | --- |
| `admin_critical_actions_emit_sanitized_audit_evidence` | Admin security, cost, provider, and quota actions are represented with actor/outcome context, sanitized detail, and no raw payload or secret values. |
| `incident_pack_contains_no_secret_values` | No token/password/API key/session/cookie/DSN/provider credential values appear in the attached evidence or derived output. |
| `cleanup_and_retention_are_preview_first` | Cleanup and retention evidence is preview-first, explicit-action-only, and preserves the minimum retention floor with a sanitized audit trail. |
| `failure_paths_emit_actionable_sanitized_evidence` | Provider, notification, and release-check failure evidence uses actionable reason codes and excludes raw tracebacks or response bodies. |
| `local_evidence_generation_is_safe` | The evidence pack can be generated locally without external calls, production data paths, or production secrets. |

## 3. Safety Rules

The checker never:

- reads raw `.env` or production secret files;
- reads production data paths;
- opens network sockets or calls external services;
- prints secret values, DSNs, tokens, cookies, provider payloads, response
  bodies, raw production paths, or raw stack traces;
- changes runtime defaults or deployment configuration.

## 4. Review Use

Release review should attach:

- `python3 scripts/incident_response_evidence.py --evidence <sanitized-incident-response-evidence.json>` output.
- admin log / notification / release-failure pytest evidence proving the
  relevant runtime surfaces already sanitize audit evidence where their current
  contracts support it.

Until the pack is accepted, the incident-response evidence posture remains
**NO-GO**.
