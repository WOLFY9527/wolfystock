# Staging Ingress Operator Evidence Guide

Date: 2026-05-08
Scope: domain-local staging ingress operator evidence only.

This guide defines a sanitized artifact contract for offline review. It does
not approve launch, does not change ingress routing, auth/RBAC behavior,
security headers at runtime, provider routing, quota enforcement, notification
routing, scanner scoring, AI decisions, portfolio/backtest calculations,
market calculations, DuckDB/storage runtime, or production deployment
behavior.

The offline validator in `scripts/staging_ingress_operator_evidence_check.py`
checks only the shape and sanitization posture of an operator-supplied JSON
artifact. It makes no network calls and is not wired into
`scripts/launch_acceptance_evidence.py`.

## Safe Collection Workflow

1. Collect the evidence from a staging, production-like-staging, or sandbox
   operator runbook.
2. Record only sanitized labels and summaries:
   - `artifactVersion`
   - `environment`
   - `operator`
   - `observedAt`
   - `baseUrlLabel`
   - `networkCallsEnabled`
   - `checkedRoutes`
   - `authBoundaryResult`
   - `securityHeaderSummary`
   - `csrfOrStateMutationSummary`
   - `publicSurfaceSummary`
   - `rateLimitOrAbuseSummary`
   - `outcome`
   - `evidenceRedactionVersion`
   - `notes`
3. Do not include raw URLs with credentials, raw request bodies, raw response
   bodies, Authorization/Cookie/Set-Cookie values, tokens, API keys,
   passwords, session identifiers, private keys, DSNs, traceback text, debug
   payloads, launch-approved claims, or destructive command text.
4. Save the sanitized artifact as JSON.
5. Run the offline validator locally.
6. Attach only the validator output and the sanitized artifact label to the
   domain review packet.

## Accepted Example

```json
{
  "artifactVersion": "wolfystock_staging_ingress_operator_evidence_v1",
  "environment": "staging",
  "operator": "staging-ingress-ops",
  "observedAt": "2026-05-08T10:30:00Z",
  "baseUrlLabel": "staging-ingress-primary",
  "networkCallsEnabled": true,
  "checkedRoutes": [
    {
      "routeLabel": "health-ready",
      "method": "GET",
      "pathPattern": "/api/health/ready",
      "statusClass": "2xx",
      "summary": "Bounded readiness route returned sanitized health metadata."
    }
  ],
  "authBoundaryResult": {
    "status": "accepted",
    "summary": "Protected routes failed closed for unauthenticated access."
  },
  "securityHeaderSummary": {
    "status": "accepted",
    "summary": "Expected security header names were observed without values."
  },
  "csrfOrStateMutationSummary": {
    "status": "accepted",
    "summary": "No state-changing operation was attempted during evidence collection."
  },
  "publicSurfaceSummary": {
    "status": "accepted",
    "summary": "Only bounded public health surfaces were sampled."
  },
  "rateLimitOrAbuseSummary": {
    "status": "accepted",
    "summary": "Abuse-control posture was summarized with counters only."
  },
  "outcome": "accepted",
  "evidenceRedactionVersion": "staging_ingress_operator_redaction_v1",
  "notes": "Sanitized staging ingress operator artifact for later review."
}
```

## Rejected Snippets

These patterns are rejected by the validator:

```json
{
  "baseUrlLabel": "<credential-bearing-url-redacted>"
}
```

```json
{
  "notes": "<launch-approval-claim-redacted>"
}
```

```json
{
  "rawRequestBody": "<raw-request-body-omitted>"
}
```

```json
{
  "notes": "Operator ran kubectl delete deployment in production."
}
```

## Run the Validator

```bash
python3 scripts/staging_ingress_operator_evidence_check.py \
  /path/to/sanitized-staging-ingress-operator-evidence.json
```

The validator emits sanitized JSON summary output and returns non-zero when
the artifact is missing required fields, contains unsafe markers, claims
launch approval, or implies production mutation.

## Review Boundary

This artifact proves only sanitized operator evidence quality. It does not:

- approve launch;
- change runtime ingress behavior;
- alter auth/RBAC, security headers, or CSRF/state mutation handling;
- change provider routing, quota enforcement, notification routing, scanner
  scoring, AI decisions, portfolio/backtest calculations, market calculations,
  DuckDB/storage runtime, or deployment behavior.

Final launch-acceptance integration is a separate serial task. This guide is
domain-local evidence only.
