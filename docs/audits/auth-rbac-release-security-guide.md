# Auth/RBAC Release Security Guide

Manual review is required before launch. This guide and the offline audit CLI
are release evidence helpers only; the audit does not approve launch and does
not replace a human security review.

## Offline Audit

Run the bounded offline audit before launch review:

```bash
python3 scripts/auth_rbac_release_audit.py --offline
```

The command emits JSON with:

- `auditStatus`
- `surfacesChecked`
- `riskyFindings`
- `manualReviewRequired`
- `networkCallsExecuted=false`

No runtime auth/RBAC behavior is changed by this audit. The script reads source
files only, performs no network calls, does not read environment values, does
not open databases, and does not update launch acceptance shared files.

Fallback-off RBAC pilot evidence is validated separately through
`python3 scripts/security_operator_acceptance_check.py --artifact <sanitized-security-operator-artifact.json>`.
That operator artifact is a manual-review input only; it does not flip
`WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED`, approve public launch, or
replace the offline audit above.

## Manual Review Scope

Review these surfaces before launch:

- Private API middleware: unauthenticated requests to non-exempt `/api/v1/*`
  routes must fail closed.
- Admin users: ordinary users must not access user directory, detail, activity,
  or security mutation routes.
- Admin logs and evidence workflow drill-through: access must remain admin or
  capability gated, and evidence workflow outputs must stay operator-reviewed.
- Cost observability: duplicate-cost, quota dry-run, LLM ledger, and pricing
  policy diagnostics must remain capability gated.
- Provider circuits: state, event, quota window, probe event, and SLA readiness
  diagnostics must remain capability gated.
- Market provider operations: the read-only operations route must remain
  admin-only.
- Public error behavior: 401, 403, and 429 responses must be bounded and safe.
- Log redaction: common auth failure paths must not persist sensitive request
  headers or bodies.

Do not include raw cookies, Authorization headers, session IDs, client IPs, request bodies, or provider payloads in release notes, screenshots, logs, operator artifacts, or audit evidence. Use route labels, status classes, reason codes, and sanitized summaries instead.

## Launch Decision Boundary

Passing tests and receiving `auditStatus=manual_review_required` means the
offline evidence is ready for manual review. It is not a GO decision, does not
enable production launch, and does not change any MFA, session, RBAC, limiter,
provider, scanner, portfolio, backtest, AI, notification, or launch acceptance
runtime behavior.
