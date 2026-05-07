# Security / RBAC / MFA Audit Index

Status: Current
Owner domain: Security, RBAC, and MFA documentation index
Related docs: `docs/audits/public-launch-readiness-master.md`,
`docs/audits/public-launch-gap-register.md`,
`docs/audits/deployment-readiness-checklist.md`,
`docs/audits/markdown-consolidation-plan.md`,
`docs/audits/markdown-inventory.md`

Mode: docs-only navigation index. No audit files were moved, deleted,
archived, merged, or rewritten.

## Purpose

This index keeps security, RBAC, role-governance, and MFA audit documents
navigable while public launch remains **NO-GO** in
`docs/audits/public-launch-readiness-master.md`.

## Current canonical docs

- `docs/audits/public-launch-readiness-master.md`: executive launch verdict and
  master blockers for Security, MFA, and RBAC.
- `docs/audits/public-launch-gap-register.md`: detailed blocker register for
  MFA secret storage, recovery codes, MFA enforcement pilot, coarse fallback
  removal, and role management.
- `docs/audits/deployment-readiness-checklist.md`: operational security and
  RBAC gates for release-candidate readiness.
- `docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md`: active future
  R5 plan for removing coarse admin compatibility fallback.
- `docs/audits/admin-role-governance-plan.md`: target role family and
  governance contract before role mutation or fallback removal.
- `docs/audits/security-mfa-secret-storage-hardening-plan.md`: active deferred
  production MFA secret-storage, recovery-code, and enforcement rollout plan.

## Partial docs

- `docs/audits/admin-rbac-capability-model-design.md`: partial capability-model
  baseline; several route/capability phases landed, but coarse fallback remains.
- `docs/audits/admin-role-management-ui-design.md`: future UI design; useful
  once MFA, reauth, last-admin, audit, and role-mutation policies are ready.
- `docs/audits/production-security-hardening-audit.md`: partial production
  security audit; later security work reduced some risks, but launch blockers
  remain.
- `docs/audits/security-password-kdf-upgrade-plan.md`: partial KDF migration
  plan; password hardening status needs reconciliation against current runtime.

## Superseded docs

- `docs/audits/admin-rbac-final-qa-report.md`: historical QA evidence; use only
  as supporting proof until launch docs cite the accepted result.
- `docs/audits/security-admin-mfa-backend-foundation.md`: backend foundation
  summary superseded by the production secret-storage hardening plan.
- `docs/audits/wolfystock-final-admin-security-options-qa.md`: historical
  cross-domain QA; useful evidence, not the current security source of truth.

## Deferred docs

- `docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md`: deferred
  production governance migration.
- `docs/audits/security-mfa-secret-storage-hardening-plan.md`: deferred until
  production storage, recovery-code acceptance, and MFA login pilot evidence
  exist.
- `docs/audits/admin-role-management-ui-design.md`: deferred until backend
  role mutation, MFA/reauth, audit review, and rollback controls are approved.

## Launch blockers related to this domain

See `docs/audits/public-launch-readiness-master.md` and
`docs/audits/public-launch-gap-register.md`.

- Production MFA secret storage and recovery-code acceptance are not launch
  accepted.
- Login MFA enforcement remains disabled outside a future staged pilot.
- Coarse admin compatibility fallback remains intentional and blocks least
  privilege for broad public admin exposure.
- Role assignment/revocation workflow, last-admin protection, audit review, and
  rollback evidence remain incomplete.
- Sensitive route audit, recent reauth, and MFA policy need consistent coverage
  before capability RBAC can be treated as production least privilege.

## Hard-to-classify docs

- `docs/audits/security-password-kdf-upgrade-plan.md`: marked partial because
  implementation notes imply progress, but this index did not re-audit runtime
  auth code.
- `docs/audits/production-security-hardening-audit.md`: marked partial because
  it contains both older blockers and later mitigation notes.
