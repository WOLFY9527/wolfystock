# Config Snapshot Operator Evidence Guide

This guide defines a sanitized, offline artifact for documenting production or
staging configuration readiness posture. It is advisory-only evidence for
review. It does not approve launch, does not change runtime behavior, and is
not wired into `scripts/launch_acceptance_evidence.py`.

## Scope

Use this artifact when an operator has reviewed deployment configuration in an
approved environment and needs to attach a safe summary without exposing
secrets or raw deployment state.

Allowed environments:

- `staging`
- `production-like-staging`
- `production-review`

Allowed outcomes:

- `accepted`
- `rejected`
- `needs-review`

Allowed `secretPresenceSummary` values:

- `configured`
- `missing`
- `redacted only`

## Safe Collection Rules

Operators should collect summary labels only:

- Record who reviewed the snapshot using a team or role label, not a personal
  account, email address, session id, or cookie.
- Record the observation timestamp as ISO time.
- Summarize auth, provider, quota, notification, database, logging retention,
  rollback, secret-presence, and unsafe-default posture in plain language.
- Use controlled labels such as `configured`, `missing`, and `redacted only`
  for secret presence.
- Confirm whether unsafe defaults were reviewed without copying actual
  configuration values.

Do not include:

- environment variable values;
- DSNs or credential-bearing URLs;
- passwords, tokens, API keys, cookies, sessions, private keys, or webhooks;
- raw `.env`, config, deployment, debug, request, response, or stack dumps;
- production database contents or deployment command output;
- `launch-approved`, `GO`, `production-ready`, or release approval claims.

## Offline Validator

Run:

```bash
python3 scripts/config_snapshot_evidence_check.py path/to/config-snapshot-evidence.json
```

The validator only reads the supplied JSON file and prints a sanitized
pass/fail summary. It does not read environment variables, inspect real
deployment state, call external services, mutate app config defaults, change
auth/RBAC, change provider routing, change quota behavior, alter notification
routing, or update shared launch acceptance files.

A passing result means the artifact is safe enough to attach for later review.
It does not mean production launch is approved.

## Accepted Example

```json
{
  "artifactVersion": "config-snapshot-evidence-v1",
  "environment": "production-like-staging",
  "operator": "release-ops",
  "observedAt": "2026-05-08T10:30:00Z",
  "authConfigSummary": "Admin auth enabled; MFA rollout mode reviewed; RBAC posture documented.",
  "providerConfigSummary": "Primary and fallback provider presence documented with redacted-only credential posture.",
  "quotaConfigSummary": "Quota mode and alert posture documented without thresholds or owner identifiers.",
  "notificationConfigSummary": "Notification routing posture documented without webhook URLs or tokens.",
  "databaseConfigSummary": "Database storage and backup posture documented without DSNs.",
  "loggingRetentionSummary": "Retention window and audit logging posture documented without raw logs.",
  "rollbackConfigSummary": "Rollback switches and restore expectations documented without command output.",
  "secretPresenceSummary": "redacted only",
  "unsafeDefaultsSummary": "Operator reviewed unsafe defaults; no values are included.",
  "outcome": "accepted",
  "evidenceRedactionVersion": "config_snapshot_redaction_v1"
}
```

For `outcome: accepted`, the auth, provider, quota, and database summaries must
be present and non-empty. Missing critical summaries block acceptance because
the artifact would be too weak for readiness review.

## Rejected Examples

Raw config or environment dump:

```json
{
  "artifactVersion": "config-snapshot-evidence-v1",
  "environment": "staging",
  "operator": "release-ops",
  "observedAt": "2026-05-08T10:30:00Z",
  "rawEnvDump": {
    "APP_ENV": "production"
  },
  "outcome": "needs-review",
  "evidenceRedactionVersion": "config_snapshot_redaction_v1"
}
```

Credential-bearing value:

```json
{
  "artifactVersion": "config-snapshot-evidence-v1",
  "environment": "production-review",
  "operator": "release-ops",
  "observedAt": "2026-05-08T10:30:00Z",
  "databaseConfigSummary": "<credential-bearing-DSN-redacted>",
  "outcome": "needs-review",
  "evidenceRedactionVersion": "config_snapshot_redaction_v1"
}
```

Launch approval claim:

```json
{
  "artifactVersion": "config-snapshot-evidence-v1",
  "environment": "production-review",
  "operator": "release-ops",
  "observedAt": "2026-05-08T10:30:00Z",
  "rollbackConfigSummary": "<launch-approval-claim-redacted>",
  "outcome": "accepted",
  "evidenceRedactionVersion": "config_snapshot_redaction_v1"
}
```

## Review Boundary

This evidence only documents sanitized configuration posture. It is separate
from launch acceptance, release gating, production deployment, and live service
validation. A later serial launch-readiness task may decide whether and how to
wire this artifact into shared acceptance evidence.
