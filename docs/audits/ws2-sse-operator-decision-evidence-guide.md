# WS2/SSE Operator Decision Evidence Guide

Scope: offline WS2/SSE topology operator decision evidence only.

The validator in `scripts/ws2_sse_operator_decision_check.py` checks the shape
and sanitization posture of a human-prepared JSON artifact. It does not import
task queue code, open network connections, change SSE behavior, change polling
behavior, modify worker behavior, or integrate with
`scripts/launch_acceptance_evidence.py`.

## Safe Decision Workflow

1. Review the current WS2/SSE topology evidence and confirm that SSE remains
   process-local.
2. Choose one operator decision:
   - `polling-fallback`: official cross-instance status path is durable polling.
   - `single-instance-sse`: operator accepts a single-instance/process-local SSE
     limitation and documents the user impact.
   - `external-broadcast-required`: multi-instance SSE requires a future
     external broadcast design before it can be accepted.
   - `needs-review`: no official decision yet.
3. Create a sanitized JSON artifact. Use labels, summaries, timestamps, and
   bounded decisions only.
4. Do not include secrets, cookies, tokens, credential-bearing URLs, raw logs,
   tracebacks, stack traces, internal URLs with credentials, or launch GO claims.
5. Run the offline validator:

```bash
python3 scripts/ws2_sse_operator_decision_check.py \
  /path/to/ws2-sse-operator-decision.json
```

Passing the validator means the artifact is suitable for domain review. It does
not approve launch and it is not wired into the shared launch acceptance matrix.

## Required Fields

```json
{
  "artifactVersion": "wolfystock_ws2_sse_operator_decision_evidence_v1",
  "environment": "staging",
  "operator": "ws2-topology-ops",
  "observedAt": "2026-05-08T10:30:00Z",
  "topologyMode": "polling-fallback",
  "sseBroadcastScope": "process-local",
  "pollingFallbackAccepted": true,
  "multiInstanceRiskAccepted": false,
  "userImpactSummary": "Cross-instance status relies on durable owner-scoped polling while SSE remains process-local.",
  "rollbackOrMitigationSummary": "Keep polling fallback documented and avoid multi-instance SSE launch claims until external broadcast is designed.",
  "outcome": "accepted",
  "evidenceRedactionVersion": "ws2_sse_operator_decision_redaction_v1"
}
```

## Accepted Decision Examples

Polling fallback:

```json
{
  "artifactVersion": "wolfystock_ws2_sse_operator_decision_evidence_v1",
  "environment": "staging",
  "operator": "ws2-topology-ops",
  "observedAt": "2026-05-08T10:30:00Z",
  "topologyMode": "polling-fallback",
  "sseBroadcastScope": "process-local",
  "pollingFallbackAccepted": true,
  "multiInstanceRiskAccepted": false,
  "userImpactSummary": "Cross-instance status relies on durable owner-scoped polling while SSE remains process-local.",
  "rollbackOrMitigationSummary": "Keep polling fallback documented and avoid multi-instance SSE launch claims until external broadcast is designed.",
  "outcome": "accepted",
  "evidenceRedactionVersion": "ws2_sse_operator_decision_redaction_v1"
}
```

Single-instance limitation:

```json
{
  "artifactVersion": "wolfystock_ws2_sse_operator_decision_evidence_v1",
  "environment": "staging",
  "operator": "ws2-topology-ops",
  "observedAt": "2026-05-08T10:30:00Z",
  "topologyMode": "single-instance-sse",
  "sseBroadcastScope": "process-local",
  "pollingFallbackAccepted": false,
  "multiInstanceRiskAccepted": true,
  "userImpactSummary": "Operator accepts process-local SSE only for a single-instance topology; multi-instance broadcast is not claimed.",
  "rollbackOrMitigationSummary": "Scale down to one app instance or switch users to durable polling fallback if more than one process is required.",
  "outcome": "accepted",
  "evidenceRedactionVersion": "ws2_sse_operator_decision_redaction_v1"
}
```

## Rejection Rules

The validator rejects artifacts that:

- claim `launch-approved`, `launch-go`, `release-approved`, or bare `GO`;
- use `outcome=accepted` without an explicit valid `topologyMode`;
- claim accepted multi-instance SSE safety unless the wording clearly records
  `external-broadcast-required` or `needs-review`;
- include secrets, cookies, tokens, authorization markers, DSNs, private keys,
  raw logs, debug payloads, tracebacks, stack traces, or credential-bearing URLs;
- omit required user-impact or rollback/mitigation summaries.

## Runtime Status

This evidence guide and validator do not change runtime behavior. WS2/SSE
delivery remains process-local, and durable task polling remains the safe
cross-instance fallback path until a separate runtime change is explicitly
designed, reviewed, implemented, and wired into the launch evidence flow.
