# WolfyStock Admin And Ops Docs

Status: current admin/operations domain entry point.

Use this lane before changing admin dashboards, RBAC/security/MFA docs,
operator evidence, release gates, cost/quota/observability, provider
operations dashboards, or admin frontend UX contracts.

## Current Authority

- [Operations Docs](../operations/README.md)
- [Audit Index](../audits/README.md)
- [Security/RBAC/MFA Index](../audits/index-security-rbac-mfa.md)
- [Cost/Quota/Observability Index](../audits/index-cost-quota-observability.md)
- [DB/WS2/Deployment Index](../audits/index-db-ws2-deployment.md)
- [Provider/Data/Options Index](../audits/index-provider-data-options.md)
- [Auth/RBAC Release Security Guide](../audits/auth-rbac-release-security-guide.md)
- [Admin Data Control Center Design](../audits/admin-data-control-center-design.md)
- [Admin Data Control Center Frontend UX Contract](../audits/admin-data-control-center-frontend-ux-contract.md)
- [Duplicate-Cost Admin Dashboard Frontend UX Contract](../audits/duplicate-cost-admin-dashboard-frontend-ux-contract.md)
- [Admin/Ops IA Consolidation Blueprint](../product/ADMIN_OPS_IA_CONSOLIDATION.md)

## Current Rules

- Admin/Ops pages may be dense, but they still start with operator-readable
  state, impact, recommended action, evidence, then details.
- Raw logs, cleanup, destructive maintenance, dry-run responses, schema fields,
  route internals, and raw diagnostics require explicit expansion or
  confirmation.
- Security, RBAC, MFA, and admin mutations require current audit/runbook review
  and narrow validation.
- Operator evidence must be sanitized before handoff.
- Private-beta onboarding responses may contain `initialPassword` exactly once
  with `passwordDelivery=returned_once`. Treat it as one-time secret material:
  do not log response bodies, do not store it in browser history, screenshots,
  proxy logs, CDN logs, analytics, or audit metadata, copy and hand it off only
  through the approved operator process, and discard it after use.
