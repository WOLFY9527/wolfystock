# Provider Operator Evidence Guide

This guide defines the domain-local artifact path for sanitized real/staging provider probe evidence. It does not approve launch, does not change runtime behavior, and is not wired into launch acceptance yet.

## What to Collect

Operators may attach one JSON artifact per provider probe with sanitized metadata only:

- `providerName`: provider label, for example `tradier`, `polygon`, or `ibkr`.
- `environment`: one of `staging`, `production-like`, or `sandbox`.
- `operator`: human/team label, not a credential or session id.
- `observedAt`: ISO timestamp for the operator observation.
- `probeMode`: short label for the probe method.
- `networkCallsEnabled`: whether the operator-run probe used external network calls.
- `credentialPresence`: one of `configured`, `missing`, or `redacted`.
- `circuitState`: sanitized state/summary of circuit behavior observed by the operator.
- `fallbackState`: sanitized state/summary of fallback behavior observed by the operator.
- `outcome`: one of `accepted`, `rejected`, or `needs-review`.
- `evidenceRedactionVersion`: redaction policy label used by the operator.
- `notes`: sanitized short notes.

Do not include provider tokens, API keys, passwords, cookies, session ids, DSNs, request bodies, response bodies, provider payloads, debug payloads, tracebacks, stack traces, authorization headers, or set-cookie headers. The validator rejects artifacts containing those marker names even when values appear redacted.

## Offline Validator

Run the validator against the operator-supplied JSON:

```bash
python3 scripts/provider_operator_evidence_check.py path/to/provider-evidence.json
```

The validator only reads the JSON file and prints a sanitized pass/fail summary. It does not call external providers, read `.env`, inspect credential values, modify provider routing, change fallback behavior, or update shared launch acceptance files.

Validation success means the artifact is structurally safe to attach for later review. It remains advisory-only and does not mean launch is approved.

## Accepted Example

```json
{
  "providerName": "tradier",
  "environment": "staging",
  "operator": "provider-ops",
  "observedAt": "2026-05-08T10:30:00Z",
  "probeMode": "manual_provider_probe",
  "networkCallsEnabled": true,
  "credentialPresence": "redacted",
  "circuitState": {
    "state": "closed",
    "summary": "No forced circuit override recorded."
  },
  "fallbackState": {
    "state": "unchanged",
    "summary": "Runtime fallback policy was observed only."
  },
  "outcome": "accepted",
  "evidenceRedactionVersion": "provider_operator_redaction_v1",
  "notes": "Sanitized operator artifact for later review."
}
```

`networkCallsEnabled: true` is allowed only when the operator outcome is `accepted`. The validator still remains advisory-only and does not run any provider calls itself.

## Rejected Examples

Missing required field:

```json
{
  "providerName": "tradier",
  "environment": "staging",
  "operator": "provider-ops",
  "probeMode": "manual_provider_probe",
  "networkCallsEnabled": false,
  "credentialPresence": "redacted",
  "circuitState": "closed",
  "fallbackState": "unchanged",
  "outcome": "needs-review",
  "evidenceRedactionVersion": "provider_operator_redaction_v1",
  "notes": "Missing observedAt."
}
```

Unsafe credential/debug markers:

```json
{
  "providerName": "tradier",
  "environment": "staging",
  "operator": "provider-ops",
  "observedAt": "2026-05-08T10:30:00Z",
  "probeMode": "manual_provider_probe",
  "networkCallsEnabled": false,
  "credentialPresence": "redacted",
  "circuitState": "closed",
  "fallbackState": "unchanged",
  "outcome": "needs-review",
  "evidenceRedactionVersion": "provider_operator_redaction_v1",
  "notes": "Unsafe example.",
  "api_key": "[redacted]",
  "raw_response": {
    "status": "ok"
  }
}
```

Launch approval claim:

```json
{
  "providerName": "tradier",
  "environment": "staging",
  "operator": "provider-ops",
  "observedAt": "2026-05-08T10:30:00Z",
  "probeMode": "manual_provider_probe",
  "networkCallsEnabled": false,
  "credentialPresence": "redacted",
  "circuitState": "closed",
  "fallbackState": "unchanged",
  "outcome": "GO",
  "evidenceRedactionVersion": "provider_operator_redaction_v1",
  "notes": "launch-approved"
}
```

Provider launch remains non-GO until a later serial launch review wires accepted evidence into the shared launch acceptance process.
