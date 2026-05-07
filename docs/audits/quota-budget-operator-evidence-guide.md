# Quota and Budget Operator Evidence Guide

Date: 2026-05-08
Scope: domain-local quota pilot and budget-alert operator evidence.

This guide defines the sanitized artifact shape for:

- controlled quota pilot observation;
- budget-alert dry-run intent;
- owner-scope sampling;
- disabled preference suppression;
- notification no-outbound proof.

It does not approve launch, update the global launch acceptance matrix, send
notifications, change quota enforcement, change billing behavior, or change
notification routing.

## Validator

Run the local offline validator against one sanitized JSON artifact:

```bash
python3 scripts/quota_operator_evidence_check.py \
  docs/audits/examples/sanitized-quota-budget-operator-evidence.json
```

The validator:

- reads only the JSON file supplied on the command line;
- emits sanitized JSON summary output;
- makes no network calls;
- sends no outbound notifications;
- imports no quota, billing, notification, provider, auth, or storage runtime;
- returns zero only when every required section is accepted.

The summary is still local evidence only. Do not paste it into
`scripts/launch_acceptance_evidence.py` input until a separate task explicitly
integrates quota/budget operator evidence into the launch acceptance matrix.

## Required Artifact Sections

The top-level artifact must use:

```json
{
  "schemaVersion": "wolfystock_quota_operator_evidence_v1",
  "mode": "operator_sanitized"
}
```

It must include these top-level sections:

- `quotaPilot`
- `budgetAlertDryRun`
- `ownerScopeSampling`
- `disabledPreferenceSuppression`
- `notificationNoOutboundProof`

Each section must include:

- `environment`: sanitized environment label only.
- `operator`: sanitized operator label only.
- `observedAt`: ISO-8601 timestamp.
- `sampledOwnerLabels`: non-empty sanitized owner labels.
- `thresholdPolicyVersion`: bounded policy-version label.
- `dryRunOnly`: `true`.
- `outboundSent`: `false`.
- `outcome`: `accepted`, `needs-review`, or `rejected`.
- `evidenceRedactionVersion`: `quota_budget_operator_redaction_v1`.

For launch-blocker closure, every section must be `accepted` and
`outboundSent=false`.

## Safe Collection Steps

1. Run quota pilot and budget alert checks through the existing admin dry-run or
   operator rehearsal path only.
2. Record owner scope as labels such as `owner-alpha` or `pilot-owner-01`.
3. Record threshold policy identity as a version label, not a diff of raw policy
   contents.
4. Record budget alert state and notification intent as dry-run labels.
5. Confirm no outbound channel was invoked by checking dry-run status, disabled
   channel status, or no-channel delivery status.
6. Remove raw request bodies, raw response bodies, debug payloads, stack traces,
   contact data, credentials, tokens, webhook URLs, provider payloads, invoice
   data, and production data paths before saving the artifact.
7. Run the validator and attach only the validator summary plus the sanitized
   source artifact label to the operator review notes.

## Accepted Example

```json
{
  "schemaVersion": "wolfystock_quota_operator_evidence_v1",
  "mode": "operator_sanitized",
  "quotaPilot": {
    "environment": "staging-sanitized",
    "operator": "cost-ops-operator",
    "observedAt": "2026-05-08T10:30:00Z",
    "sampledOwnerLabels": ["owner-alpha", "owner-beta"],
    "thresholdPolicyVersion": "quota-budget-thresholds-v1",
    "dryRunOnly": true,
    "outboundSent": false,
    "outcome": "accepted",
    "evidenceRedactionVersion": "quota_budget_operator_redaction_v1"
  },
  "budgetAlertDryRun": {
    "environment": "staging-sanitized",
    "operator": "cost-ops-operator",
    "observedAt": "2026-05-08T10:30:00Z",
    "sampledOwnerLabels": ["owner-alpha", "owner-beta"],
    "thresholdPolicyVersion": "quota-budget-thresholds-v1",
    "dryRunOnly": true,
    "outboundSent": false,
    "outcome": "accepted",
    "evidenceRedactionVersion": "quota_budget_operator_redaction_v1"
  },
  "ownerScopeSampling": {
    "environment": "staging-sanitized",
    "operator": "cost-ops-operator",
    "observedAt": "2026-05-08T10:30:00Z",
    "sampledOwnerLabels": ["owner-alpha", "owner-beta"],
    "thresholdPolicyVersion": "quota-budget-thresholds-v1",
    "dryRunOnly": true,
    "outboundSent": false,
    "outcome": "accepted",
    "evidenceRedactionVersion": "quota_budget_operator_redaction_v1"
  },
  "disabledPreferenceSuppression": {
    "environment": "staging-sanitized",
    "operator": "cost-ops-operator",
    "observedAt": "2026-05-08T10:30:00Z",
    "sampledOwnerLabels": ["owner-alpha", "owner-beta"],
    "thresholdPolicyVersion": "quota-budget-thresholds-v1",
    "dryRunOnly": true,
    "outboundSent": false,
    "outcome": "accepted",
    "evidenceRedactionVersion": "quota_budget_operator_redaction_v1"
  },
  "notificationNoOutboundProof": {
    "environment": "staging-sanitized",
    "operator": "cost-ops-operator",
    "observedAt": "2026-05-08T10:30:00Z",
    "sampledOwnerLabels": ["owner-alpha", "owner-beta"],
    "thresholdPolicyVersion": "quota-budget-thresholds-v1",
    "dryRunOnly": true,
    "outboundSent": false,
    "outcome": "accepted",
    "evidenceRedactionVersion": "quota_budget_operator_redaction_v1"
  }
}
```

## Rejection Examples

The validator rejects artifacts that include:

- raw contact data or webhook URLs;
- token, secret, credential, cookie, session, or key material markers;
- raw request, response, debug, stack trace, or traceback payload fields;
- `outboundSent=true` in launch evidence;
- `GO`, `launch-approved`, or release-approved wording;
- missing or empty `sampledOwnerLabels`;
- `dryRunOnly=false`;
- threshold or enforcement mutation claims.

If an operator needs to record a separate non-launch outbound rehearsal, mark it
with `rehearsalScope="separate_non_launch_rehearsal"` and
`outcome="needs-review"` or `outcome="rejected"`. That artifact remains
non-acceptance evidence and cannot close the launch blocker.

## Runtime Boundary

This artifact proves only sanitized operator evidence quality. It does not:

- enable live quota enforcement;
- change budget thresholds;
- mutate invoices, cost ledger rows, quota reservations, or billing policy;
- send notification events;
- change notification routes or channel preferences;
- modify provider behavior, scanner scoring, portfolio/backtest calculations,
  auth/RBAC, DuckDB runtime, or AI decisions.
