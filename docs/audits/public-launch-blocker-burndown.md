# Public Launch Blocker Burn-down Tracker

Date: 2026-05-07
Branch checked: `main`
Owner domain: Release readiness
Mode: docs-only burn-down tracker. No code, tests, scripts, frontend app files,
provider config, or changelog files were changed.

## Purpose

This tracker is the short-form view of the launch blocker register. Use it to
track what is still blocking public launch, what has already been hardened, and
what the next concrete step is for each domain.

## Completed hardening items

These items are useful launch foundations and should not be read as active
blockers:

- Password KDF hardening and MFA/RBAC foundations exist.
- Provider diagnostics, Options/Data Pipeline foundations, and data-quality
  disclosure surfaces exist.
- Cost ledger, quota dry-run helpers, and provider circuit diagnostics exist.
- Deployment health/readiness endpoints and Docker healthcheck coverage exist.
- Recent safety tests exist for backtest and portfolio areas, but launch proof
  is still incomplete.

## Active blockers

| Domain | Current state | Completed prerequisites | Remaining concrete next step | Risk level | Owner domain |
| --- | --- | --- | --- | --- | --- |
| MFA enforcement rollout | Login MFA enforcement is still disabled. | MFA backend scaffold, password hardening, and recovery-code design notes exist. | Run a narrow staged admin MFA enforcement pilot with rollback evidence. | P0 | Security/Auth |
| RBAC coarse fallback removal | Coarse admin compatibility fallback remains intentional. | Capability route inventory, RBAC docs, and partial audit coverage exist. | Produce the R5 inventory/observe report, then decide a fail-closed pilot path. | P0 | Security/RBAC |
| Real provider / live data | Public provider and Options paths are still fixture-first or observational in launch posture. | Provider diagnostics, entitlement discussions, and data-quality disclosure policy exist. | Land per-route entitlement acceptance for one real provider/live-data path with staging proof. | P1 | Provider / Data / Options |
| Provider circuit enforcement | Circuit diagnostics exist, but no runtime call site enforces policy. | Dry-run observer, circuit data model, and budget/fallback reporting exist. | Pilot one low-risk route with runtime circuit enforcement and rollback switch. | P0 | Provider reliability |
| Live quota enforcement | Quota controls are still dry-run/reservation oriented. | Cost ledger and quota helper surfaces exist. | Pilot one route-boundary live quota rule with explicit block/warn behavior. | P0 | Cost / Quota |
| Production backup/restore drill | Backup/restore evidence is still missing. | Health/readiness checks and deployment checklist exist. | Execute an isolated encrypted backup/restore drill and capture post-restore smoke evidence. | P0 | Platform / DBA |
| Frontend / design / public smoke readiness | Public-facing smoke proof is still incomplete. | Frontend safety tests and shell/layout foundations exist. | Run the public-route browser smoke set with no-secret and owner-isolation proof. | P1 | Frontend / Release readiness |

## Notes

- The blockers above are ordered by launch impact, not by implementation
  dependency.
- This tracker intentionally stays concise; the detailed evidence stays in
  `public-launch-gap-register.md`.
- When one blocker closes, move its item to completed hardening only if the
  next release posture no longer depends on it.
