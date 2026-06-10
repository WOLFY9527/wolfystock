# Admin/Ops Launch Cockpit Goal Progress

Status: in progress
Branch: `codex/goal-admin-ops-launch-cockpit`
Mode: private-beta admin/operator cockpit. This work is read-only/advisory and
does not approve public launch.

## Goal Boundary

Build an admin-only operator cockpit that summarizes private-beta launch
readiness, available evidence tooling, missing real operator evidence, approval
requirements, NO-GO blockers, and safe next actions.

The cockpit must not introduce public launch approval, runtime enforcement,
live quota blocking, provider circuit blocking, MFA enforcement, RBAC fallback
removal, DB migration/restore/cleanup, provider live calls, notification sends,
production config changes, or frontend exposure of raw secrets, raw payloads, or
raw identifiers.

## Initial Audit Map

### Existing Admin Routes Reviewed

| Surface | Current file(s) | Safe reuse |
| --- | --- | --- |
| Admin ops status snapshot | `api/v1/endpoints/admin_ops_status.py`, `src/services/admin_ops_status_service.py`, `api/v1/schemas/admin_ops_status.py`, `tests/api/test_admin_ops_status.py` | Best backend anchor. Already requires `ops:logs:read`, returns read-only/advisory metadata, and tests no provider/runtime/quota mutation calls. |
| System settings/admin landing | `apps/dsa-web/src/pages/SystemSettingsPage.tsx` | Existing default admin landing with operator-safe L0 strip. Can link to a deeper cockpit. |
| Admin logs/evidence workflow | `apps/dsa-web/src/pages/AdminLogsPage.tsx`, `apps/dsa-web/src/pages/AdminEvidenceWorkflowPage.tsx` | Existing evidence-oriented admin UI. Cockpit should point operators here for raw event review, not duplicate logs. |
| Cost/quota observability | `apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx`, `api/v1/endpoints/admin_cost.py` | Existing observational cost UI and quota dry-run. Cockpit must keep quota live enforcement false. |
| Provider readiness/circuits | `apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx`, `apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx`, `api/v1/endpoints/market_provider_operations.py`, `api/v1/endpoints/admin_provider_circuits.py` | Existing provider readiness and advisory circuit diagnostics. Cockpit should surface sanitized status only. |
| Admin users/security | `apps/dsa-web/src/pages/AdminUsersPage.tsx`, `api/v1/endpoints/admin_users.py`, `api/v1/endpoints/admin_security.py` | Current RBAC/MFA admin surfaces remain separate. Cockpit should summarize evidence/approval state only. |
| Notification admin | `apps/dsa-web/src/pages/AdminNotificationsPage.tsx`, `api/v1/endpoints/admin_notifications.py` | Existing channel/event surfaces include dry-run/no-send coverage. Cockpit must not send notifications. |

### Existing Backend Helpers And Evidence Tools Reviewed

| Domain | Existing file(s) | Cockpit treatment |
| --- | --- | --- |
| Security/RBAC/MFA | `scripts/admin_rbac_route_inventory.py`, `scripts/security_mfa_operator_evidence_check.py`, `tests/api/test_auth_rbac_release_contracts.py`, `tests/test_admin_rbac_route_inventory.py`, `tests/test_security_mfa_operator_evidence_check.py` | Foundation/tooling present; real staged MFA/RBAC operator acceptance is missing; public launch remains NO-GO. |
| Quota/cost | `src/services/quota_policy_service.py`, `scripts/quota_reserve_release_operator_evidence_check.py`, `tests/test_quota_policy_service.py`, `tests/test_quota_reserve_release_operator_evidence_check.py` | Advisory helpers and validator present; live route blocking/enforcement remains disabled and not approved. |
| Provider reliability | `src/services/provider_circuit_observer.py`, `scripts/provider_sla_licensing_evidence_check.py`, `tests/api/test_admin_provider_circuit_diagnostics.py`, `tests/test_provider_sla_licensing_evidence_check.py` | Advisory circuit/readiness evidence exists; provider runtime ordering/fallback/cache must remain unchanged. |
| Storage/restore | `scripts/storage_migration_readiness_report.py`, `scripts/isolated_pg_restore_smoke.py`, `scripts/restore_pitr_operator_evidence_check.py`, `docs/audits/storage-migration-readiness.md` | Tooling exists; no migration, restore, PITR, or cleanup is run by the cockpit. Real operator evidence is still missing. |
| WS2/async | `docs/operations/background-job-queue-boundary.md`, `scripts/ws2_multi_instance_smoke.py`, `scripts/ws2_sse_operator_decision_check.py`, `tests/test_ws2_durable_task_worker.py`, `tests/test_durable_task_state.py` | Durable/synthetic evidence exists, but multi-instance public deployment remains NO-GO. |
| Notifications | `tests/api/test_notification_channels.py`, `tests/test_quota_cost_notification_release_contracts.py`, `tests/test_user_notification_preferences.py` | No-send contracts exist; cockpit should summarize dry-run/evidence state only. |
| Portfolio/backtest | `tests/api/test_portfolio_history.py`, `tests/api/test_portfolio_owner_isolation.py`, `tests/test_backtest_api_contract.py`, `docs/backtest-system.md` | Read-only/history and stored-first backtest evidence exist; broader staged owner-isolation and accounting evidence are still needed. |
| Route classification | `tests/api/test_auth_rbac_release_contracts.py`, `tests/api/test_public_api_surface_safety.py`, `tests/fixtures/auth/backend_route_capability_inventory.json` | Route inventory/freeze exists; cockpit can report classification evidence without changing auth behavior. |
| Frontend/private-beta safety | `apps/dsa-web/e2e/admin-ops-launch-surfaces.spec.ts`, `apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts`, `apps/dsa-web/src/__tests__/AppRoutes.test.tsx` | Existing admin smoke/route tests can be extended. Public/private-beta safety still requires bounded browser evidence. |

## T-1412 Through T-1429 Reconciliation

Current source search found explicit labels only for `T-1421` and `T-1422`.
The rest of the latest task outputs are present as commits/files rather than
visible `T-1412`-style filenames or document headings. This cockpit will
reconcile by file, current active docs, and recent commit scope instead of
inventing missing task labels.

| Evidence slice | Current artifact(s) | Current classification |
| --- | --- | --- |
| Route surface classification | `b013b8c1 test(auth): freeze route surface classification` | Foundation landed; evidence tooling present; no auth behavior change. |
| Storage migration readiness | `7d766ce0 feat(storage): add migration readiness report helper` | Tooling present; real production migration/restore evidence missing; approval required. |
| Provider circuit advisory-only projection | `8e869811 fix(provider): keep circuit projection advisory-only` | Foundation landed; live provider enforcement remains NO-GO. |
| MFA operator evidence validator | `25d2ca77 feat(security): add MFA operator evidence validator` | Tooling present; real MFA pilot evidence missing; approval required. |
| Market data source authority SLO | `de1e6981 feat(market-data): add source authority SLO matrix` | Foundation/tooling present; provider entitlement/freshness evidence remains missing. |
| Portfolio read-only history | `fbbec1be feat(portfolio): add read-only history endpoint` | Foundation landed; staged owner-isolation evidence still required. |
| Notification no-send contract | `8e8c2448 test(notification): add no-send contract coverage` | Evidence tooling present; no external sends approved. |
| Admin RBAC route inventory | `e559d08a feat(security): add admin RBAC route inventory` | Foundation/tooling present; RBAC fallback removal not approved. |
| Scanner/private-beta rejection projection | `ad9dbd38 feat(scanner): add consumer-safe rejection projection` | Frontend/public-safety foundation present; launch remains NO-GO. |
| T-1421 async durability boundary | `2097e637 test(async): freeze async durability no-go contracts`, `docs/operations/background-job-queue-boundary.md` | Evidence contracts present; production/multi-instance async remains NO-GO. |
| Restore smoke wrapper | `a45c5cdd feat: add isolated pg restore smoke wrapper` | Tooling present; real isolated PostgreSQL restore evidence missing. |
| Provider SLA licensing evidence | `01d21fe1 feat(provider): add SLA licensing evidence validator` | Tooling present; real entitlement/operator evidence missing. |
| Admin ops status snapshot | `7bd34abd feat(admin): add ops status snapshot endpoint` | Backend anchor landed; cockpit slice can extend this read-only surface. |
| Quota reserve/release evidence | `650cca57 feat(quota): add offline reserve release evidence validator` | Tooling present; live quota route enforcement remains NO-GO. |

## Initial Cockpit Domain Classification

| Domain | Foundation landed | Evidence tooling present | Real evidence missing | Approval required | Public-launch status |
| --- | --- | --- | --- | --- | --- |
| Security/RBAC/MFA | Yes | Yes | Yes | Yes | NO-GO |
| Quota/cost | Yes | Yes | Yes | Yes | NO-GO |
| Provider reliability | Yes | Yes | Yes | Yes | NO-GO |
| Storage/restore | Yes | Yes | Yes | Yes | NO-GO |
| WS2/async | Partial | Yes | Yes | Yes | NO-GO |
| Notifications | Partial | Yes | Yes | Yes | NO-GO |
| Portfolio/backtest | Partial | Yes | Yes | Yes | NO-GO |
| Route classification | Yes | Yes | Some | Yes | NO-GO |
| Frontend/private-beta safety | Partial | Yes | Yes | Yes | NO-GO |

## Implementation Plan

1. Extend the existing admin ops status schema/service with an additive
   `launchCockpit` projection containing sanitized domain rows, status counts,
   blocker list, safe next actions, and follow-up proposals.
2. Keep the projection deterministic and read-only. It may reference existing
   script/doc/test names, but it must not execute validators, provider calls,
   notification sends, migrations, cleanup, restore, quota reservation calls, or
   auth/RBAC state changes.
3. Add focused backend tests proving the cockpit is admin-only, advisory-only,
   sanitized, and explicit about NO-GO/approval-required states.
4. Add an admin-only frontend page at `/admin/launch-cockpit` that consumes the
   existing ops status endpoint and renders dense operator rows with clear
   category labels: foundation landed, evidence tooling present, real evidence
   missing, approval required, and public-launch NO-GO.
5. Add frontend tests and, if practical, a bounded admin Playwright smoke using
   mocked/safe data.

## Checkpoint Log

| Checkpoint | Commit | Status | Notes |
| --- | --- | --- | --- |
| `checkpoint(admin-ops): map readiness cockpit` | `cece18b1` | Complete | Initial audit map and implementation plan. Validation: `git diff --check`; `./scripts/release_secret_scan.sh --local-only`. |
| `checkpoint(admin-ops): add sanitized status surfaces` | `8380bd1d` | Complete | Backend `launchCockpit` projection/schema/tests. Focused validation: `pytest -p no:cacheprovider tests/api/test_admin_ops_status.py`; `python -m py_compile api/v1/endpoints/admin_ops_status.py api/v1/schemas/admin_ops_status.py src/services/admin_ops_status_service.py`. |
| `checkpoint(admin-ops): add evidence and blocker view` | pending | In progress | Frontend `/admin/launch-cockpit` route/page/navigation and API client. Focused validation: `npm --prefix apps/dsa-web run test -- src/api/__tests__/adminOpsStatus.test.ts --reporter=dot`; `npm --prefix apps/dsa-web run test -- src/pages/__tests__/AdminLaunchCockpitPage.test.tsx --reporter=dot`; `npm --prefix apps/dsa-web run test -- src/__tests__/AppRoutes.test.tsx --reporter=dot`; `npm --prefix apps/dsa-web run test -- src/components/layout/__tests__/Shell.test.tsx --reporter=dot`; `npm --prefix apps/dsa-web run typecheck`. |
| `checkpoint(admin-ops): add cockpit validation` | pending | Pending | Focused validation and smoke evidence. |
| `feat(admin-ops): add private beta launch cockpit` | pending | Pending | Final squash/checkpoint closeout commit. |

## Explicit Non-Approvals

- Public launch is not approved.
- Live quota enforcement is not enabled.
- Provider circuit/runtime enforcement is not enabled.
- MFA enforcement and RBAC fallback removal are not enabled.
- Restore, PITR, migration, retention cleanup, and deletion are not run.
- Notification sends and provider live calls are not run.
- Production config is not changed.
