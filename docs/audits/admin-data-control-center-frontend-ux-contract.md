# Admin Data Control Center Frontend UX Contract

Date: 2026-05-06
Mode: docs-only frontend UX contract. No runtime behavior changed.

## 1. Purpose

Define the future frontend UX for the Admin Data Control Center after backend APIs stabilize.

This contract is implementation-ready for a later frontend pass, but it does not approve or implement routes, React pages, API clients, styles, i18n strings, tests, authorization changes, backend behavior, or data-access behavior. The future UI must be an admin operator workspace, not a raw database browser.

## 2. Inputs and dependencies

Required backend contracts:

| Contract | Source design | Current status for frontend planning | Notes |
| --- | --- | --- | --- |
| `GET /api/v1/admin/users` | `docs/audits/admin-user-directory-api-design.md` | Designed; future implementation required before UI | Safe paginated user directory projection. |
| `GET /api/v1/admin/users/{user_id}` | `docs/audits/admin-user-directory-api-design.md` | Designed; future implementation required before UI | Safe user detail projection with redacted session summaries. |
| `GET /api/v1/admin/users/{user_id}/activity` | `docs/audits/admin-user-activity-timeline-api-design.md` | Designed; future implementation required before UI | Per-user normalized timeline. |
| `GET /api/v1/admin/activity` | `docs/audits/admin-user-activity-timeline-api-design.md` | Designed; future implementation required before UI | Global admin activity timeline. |
| Future user portfolio summary routes | `docs/audits/admin-data-control-center-design.md` | Not implemented; future backend contract required | Read-only, aggregate-first portfolio state. |
| Future user analysis/scanner/backtest routes | `docs/audits/admin-data-control-center-design.md` | Not implemented; future backend contract required | Summary/detail links only; no scanner/backtest behavior changes. |
| Future security-control routes | `docs/audits/admin-data-control-center-design.md` | Not implemented; depends on audit and role hardening | Mutating actions need typed confirmation and audit ids. |
| Future admin audit routes | `docs/audits/admin-data-control-center-design.md` | Not implemented; audit model pending | Must record admin access to sensitive views. |

Static frontend context inspected for future alignment:

- `apps/dsa-web/src/App.tsx`: current locale-aware route tree and `AdminSurfaceRoute` gate.
- `apps/dsa-web/src/components/layout/Shell.tsx`: shell scroll/frame ownership.
- `apps/dsa-web/src/components/layout/SidebarNav.tsx`: admin-only utility navigation pattern.
- `apps/dsa-web/src/pages/AdminLogsPage.tsx`: current admin observability surface, filters, drawers, and sanitized log drilldown posture.
- `apps/dsa-web/src/pages/MarketProviderOperationsPage.tsx`: read-only admin snapshot pattern and Admin Logs drill-through.
- `apps/dsa-web/src/i18n/core.ts`: current Chinese-first route labels and admin copy ownership.

Optional `docs/audits/admin-data-governance-next-phase-design.md` was present as an untracked file during this pass, so it was intentionally not used as a clean dependency.

## 3. Route map

All routes are proposed only. Final paths must be added only after backend response contracts are stable and route/navigation ownership is approved.

| Future route | Purpose | Data source/API | Mode | Required permission | Audit note | Loading / empty / error / forbidden state |
| --- | --- | --- | --- | --- | --- | --- |
| `/zh/admin/users` | User directory, search, filters, risk badges | `GET /api/v1/admin/users` | Read-only | `admin`, future `users:read` | Category-level admin access event | Skeleton table; empty directory; sanitized API error; admin gate page. |
| `/zh/admin/users/:userId` | User detail shell and overview tab | `GET /api/v1/admin/users/{user_id}` | Read-only | `admin`, future `users:read` | Target-user view event | Detail skeleton; user not found; sanitized error; forbidden copy. |
| `/zh/admin/users/:userId/activity` | Per-user activity timeline | `GET /api/v1/admin/users/{user_id}/activity` | Read-only | `admin`, future `users:activity:read` | Target-user timeline view event | Timeline shimmer; no activity in window; stale/partial source notice; forbidden copy. |
| `/zh/admin/users/:userId/security` | Security state and future controls | User detail now; future security APIs later | Read-only first; actions later | Future `security-admin` or `super-admin` | View and every action audited | Read-only unavailable actions; no sessions; action failure; typed-confirm modal after backend exists. |
| `/zh/admin/users/:userId/portfolio` | Aggregate portfolio and holdings summary | Future portfolio summary/holdings/activity APIs | Read-only | Future `portfolio:admin:read` with reason if required | Every portfolio view audited | Aggregate skeleton; no accounts; redaction active; forbidden aggregate-only copy. |
| `/zh/admin/users/:userId/analysis` | Analysis history summary | Future analysis-history admin API; Admin Logs links | Read-only | Future `analysis:admin:read` | Drilldowns audited | Empty history; partial logs; raw payload unavailable. |
| `/zh/admin/users/:userId/scanner` | Scanner run summary | Future scanner-runs admin API; Admin Logs links | Read-only | Future `scanner:admin:read` | Drilldowns audited | No runs; deterministic ranking unchanged notice. |
| `/zh/admin/users/:userId/backtest` | Backtest and rule-backtest summary | Future backtests admin API; Admin Logs links | Read-only | Future `backtest:admin:read` | Drilldowns audited | No runs; strategy text collapsed/redacted. |
| `/zh/admin/audit` | Admin access/action audit | Future admin audit API or sanitized Admin Logs projection | Read-only | Future `security-admin` or `super-admin`; support-admin redacted | Viewing audit data is audited | Empty audit window; partial retention; forbidden broad-audit copy. |

## 4. Information architecture

The future workspace should use a dense operator layout:

- Left filter/search rail: query, role, active state, password state, session state, last-seen window, risk badge, and result limit. It must not include raw password/session/token/search fields.
- Main user list table: compact columns for 用户, 角色, 状态, 会话, 最近活动, 风险, 创建时间, and 操作. Rows open the detail shell.
- User detail shell: sticky compact identity header with status/risk chips, redacted session summary, and safe Admin Logs links.
- Tabs: 概览, 活动, 安全, 组合, 分析, Scanner, Backtest, 管理审计.
- Right-side risk/audit summary panel: read-only state, last admin access event, reason-required notice where applicable, redaction state, and known data limitations.
- Developer details: collapsed by default under `AdminRawDetailsDisclosure`; never show raw secrets, raw prompts, raw payloads, raw cookies, or raw stack traces.

## 5. Page contracts

### User Directory Page

Visible fields:

- User id, username, display name, role, active state, passwordState, createdAt, updatedAt, lastSeenAt, session counts, riskBadges, and safe links.

Hidden/redacted fields:

- Password hash, legacy admin password hash, raw session id, signed cookie, session secret, reset/admin-unlock token, API keys, provider tokens, broker credentials, raw user-owned payloads.

Interactions:

- Search safe user fields, filter by role/status/session state/date window, sort, paginate, open detail, open sanitized Admin Logs link.
- No edit, disable, reset, revoke, export, provider call, or live probe in Phase F1.

States:

- Loading: Reflect-Linear skeleton table and rail placeholders.
- Empty: `暂无符合条件的用户`.
- Error: sanitized `ApiErrorAlert` copy; no stack trace.
- No-data: explain that the backend has no users or filters are too narrow.
- Forbidden: existing admin gate style, Chinese-first copy.
- Audit awareness copy: `查看用户目录会记录管理员访问范围，不记录搜索原文或凭证值。`

### User Detail Overview

Visible fields:

- Safe account identity, role, active status, passwordState, created/updated timestamps, sessionSummary, recent redacted session handles, riskBadges, dataLinks, limitations.

Hidden/redacted fields:

- Raw session ids, cookie values, reset tokens, credential hashes, secret config values, raw activity rows.

Interactions:

- Switch tabs, copy safe user id, open Admin Logs with sanitized filters, refresh current safe projection.

States:

- Loading: detail header skeleton and inactive tabs.
- Empty/no-data: user exists but no sessions or derived summaries.
- Error: sanitized storage/API failure.
- Forbidden: admin-only route gate or future capability-denied panel.
- Audit awareness copy: `打开用户详情会记录目标用户和管理员身份。`

### Activity Timeline

Visible fields:

- Timestamp, actor type/label, target user label, family, action, entity label/symbol/market, status/outcome, hashed request/session handles, source kind, redactedMetadata, Admin Logs links.

Hidden/redacted fields:

- Raw request bodies, prompts, messages, provider payloads, raw session ids, raw guest cookies, raw stack traces, raw URLs/query strings.

Interactions:

- Filter by time window, family, status, entity type, actor type, safe query, include_admin, include_system; open sanitized Admin Logs details.

States:

- Loading: timeline skeleton.
- Empty: `当前时间窗口内暂无活动`.
- Error: partial-source warning or sanitized API error.
- No-data: source not implemented or not retained.
- Forbidden: future capability-denied copy.
- Audit awareness copy: `访问活动时间线会写入目标用户级审计事件。`

### Security Tab

Visible fields:

- Account status, role/capability summary when available, passwordState, session counts, redacted recent sessions, failed-login/lockout/password-change fields only when backend supports them.

Hidden/redacted fields:

- Plaintext password, password hash, password salt, session secret, signed cookie, raw token, reset token, admin unlock token.

Interactions:

- Phase F1/F2: read-only only.
- Later phases: disable/enable, revoke sessions, force password change, reset password flow metadata only; each action requires reason, typed confirmation for destructive/security-sensitive actions, and audit event id display.

States:

- Loading: state tiles skeleton.
- Empty/no-data: no active sessions or security telemetry unavailable.
- Error: sanitized failure with no auth internals.
- Forbidden: `当前权限不能查看或操作安全状态`.
- Audit awareness copy: `安全状态查看和控制操作都会被审计；响应不会返回密码或令牌。`

### Portfolio / Holdings Tab

Visible fields:

- Aggregate account count, currency totals, holdings count, market value, unrealized P&L, cash totals, latest sync/import timestamps, masked broker account refs, trade/cash/action counts.

Hidden/redacted fields:

- Broker session token, sync token, imported raw files, uploaded content, broker payload JSON, raw sync metadata, free-form notes unless classified.

Interactions:

- Read-only filters by account/market/currency, aggregate-first drilldown, Admin Logs links.
- No correction, import, sync, broker probe, FX recalculation, or mutation.

States:

- Loading: aggregate cards and holdings table skeleton.
- Empty/no-data: `该用户暂无组合账户或持仓`.
- Error: sanitized portfolio API error.
- Forbidden: support-admin aggregate-only or denied state.
- Audit awareness copy: `查看用户组合会记录管理员、目标用户、原因和结果。`

### Analysis / Scanner / Backtest Tabs

Visible fields:

- Analysis: report type, stock/symbol, market, status, createdAt, summary label, safe history id, Admin Logs link.
- Scanner: run id/hash, market/profile, status, candidate count, deterministic top ranks/scores, diagnostic coverage summary when sanitized.
- Backtest: run id/hash, type, status, symbol/window, metrics, result link, trade count.

Hidden/redacted fields:

- Raw prompt, raw messages, raw report JSON, raw news/provider payloads, raw scanner diagnostics JSON, raw strategy text unless gated and audited, raw AI summary/model output dump.

Interactions:

- Filter, sort, paginate, open existing user-facing result where permission allows, open sanitized Admin Logs links.
- No scanner execution, backtest execution, rerun, threshold change, ranking change, prompt replay, or cache mutation.

States:

- Loading: table skeleton per tab.
- Empty/no-data: no records in selected family.
- Error: sanitized family-specific failure.
- Forbidden: capability-denied panel.
- Audit awareness copy: `明细钻取只显示脱敏摘要；原始模型和数据源内容默认不可见。`

### Admin Access Log Tab

Visible fields:

- Admin actor label/role, target user/entity, action category, route family, reason bucket, outcome, timestamp, audit event id, safe request id hash.

Hidden/redacted fields:

- Secret values, raw target identifiers where lower privilege requires redaction, raw reasons if they may include sensitive free text, raw request/session ids.

Interactions:

- Filter by actor, action, outcome, time window, target category; open allowed audit event detail.

States:

- Loading: audit list skeleton.
- Empty: no admin access events for selected user/window.
- Error: sanitized audit API error.
- Forbidden: broad audit denied.
- Audit awareness copy: `查看管理审计本身也应记录访问事件。`

## 6. Sensitive data display policy

The UI must explicitly forbid display of:

- plaintext password
- password hash
- password salt or legacy credential-file contents
- raw session id
- signed cookie
- token
- API key
- broker credential
- broker/session sync token
- raw prompt/messages
- raw provider payload
- raw report JSON/model output dump
- raw uploaded image/file content
- raw stack traces
- raw URLs/query strings that can contain credentials

Allowed safe display:

- `passwordState`
- redacted session handle
- masked broker account ref
- aggregate portfolio summary
- safe hashes with purpose labels
- audit event ids
- sanitized Admin Logs links
- configured/unconfigured status without secret values
- limitation flags and data-source confidence

## 7. Visual design contract

The future UI must follow the current WolfyStock Reflect-Linear system:

- Dark finance background: route frame based on the approved Reflect-Linear
  canvas/surface ladder, not standalone OLED or pure-black page islands.
- Ghost-glass panels: transparent white/black surfaces, thin white borders, restrained blur.
- Dense but readable admin typography: compact labels, no oversized marketing hero.
- Compact badges: status/risk chips with clear tone and no loud solid-color blocks.
- Right-side audit/risk summary: visually persistent but not a card pile.
- Developer/raw details collapsed by default with Chinese labels such as `开发者字段` or `原始诊断`.
- Non-native filter controls: custom select/input/button primitives; no default browser controls.
- No solid gray blocks, no default-looking tables, no raw database-browser visual metaphor.
- Tables must be scannable with fixed action columns, `min-w-0`, truncation, and mobile-safe stacked summary rows.

## 8. Component inventory

| Future component | Responsibility | Data required | Redaction rules | Tests needed |
| --- | --- | --- | --- | --- |
| `AdminUserDirectoryTable` | Dense user rows, sorting, pagination, detail entry | List items, total, limit, offset | Never render credential/session raw fields | Row render, empty/error, no secret text in DOM. |
| `AdminUserFilterRail` | Safe filters and search | Query params, selected filters, summary counts | No raw session/token/password/prompt search | Filter serialization, reset, responsive layout. |
| `AdminUserRiskBadge` | Compact risk/attention state | Risk badge code, label, tone | Use bounded labels only | Tone mapping and unknown fallback. |
| `AdminUserDetailShell` | Header, tabs, right audit/risk rail | User detail, active tab, limitations | Only safe identity/session summaries | Route/tab render, mobile no overflow. |
| `AdminSensitiveViewNotice` | Audit and reason-required notices | Surface name, permission, reason status | No secrets in copy | Notice visible on sensitive tabs. |
| `AdminAuditTrailCard` | Recent admin access/action summary | Audit events, event ids, timestamps | Redact target ids by role | Empty/forbidden states. |
| `AdminSessionSummaryCard` | Session counts and redacted session list | Session summary and session handles | No raw session id/cookie/token | Session redaction assertions. |
| `AdminActivityTimeline` | Normalized per-user/global event feed | Activity events, filters, log links | Redacted metadata only | Filters, ordering, safe links. |
| `AdminPortfolioSummaryPanel` | Aggregate portfolio and holdings summary | Portfolio aggregate/holdings response | Mask broker refs; no raw files/tokens | Aggregate empty/error and redaction. |
| `AdminSecurityControlsPanel` | Security state and future action controls | Security state, action availability | No password/hash/token display | Disabled/read-only state, typed confirmation later. |
| `AdminRedactedField` | Consistent masked-field rendering | Label, redacted value, reason | Show mask/status, never raw value | DOM secret guard. |
| `AdminRawDetailsDisclosure` | Collapsed sanitized developer details | Safe JSON subset and limitations | Collapsed by default; omit raw payloads | Default collapsed, no unsafe keys. |

## 9. Permission and audit UX

- Use admin-only route gating aligned with the current `AdminSurfaceRoute` pattern.
- Future role split should distinguish `support-admin`, `security-admin`, `ops-admin`, and `super-admin`.
- `support-admin`: user directory, redacted activity, aggregate analysis/scanner/backtest, and limited portfolio aggregates when approved.
- `security-admin`: security state/actions, session revocation, account disable/enable, and security audit.
- `ops-admin`: Admin Logs, provider operations, runtime health; no portfolio/security detail by default.
- `super-admin`: broad admin data read, security controls, role management, and audit review.
- Sensitive tabs may require a reason prompt if backend requires it. The prompt must capture bounded reason categories plus optional short text with clear warning that it is audited.
- Every sensitive view should show visible audit copy near the header or side rail.
- Destructive/security actions require typed confirmation, cannot expose secret values, and must display a sanitized `auditEventId` after completion.

## 10. Frontend implementation sequence

Phase F1: directory and user detail read-only shell

- Likely files touched later: `apps/dsa-web/src/App.tsx`, future admin user pages, future API client, i18n entries, route tests.
- Tests: admin route gating, directory render, detail overview, loading/empty/error/forbidden, no secret DOM text.
- Browser verification: desktop and mobile/narrow route checks after implementation.
- Dependencies: `GET /api/v1/admin/users` and `GET /api/v1/admin/users/{user_id}` stable.

Phase F2: activity timeline

- Likely files touched later: activity page/tab component, API client, filters, tests.
- Tests: filter behavior, source links, redacted metadata, collapsed details.
- Browser verification: timeline density and mobile overflow checks.
- Dependencies: user and global activity APIs stable.

Phase F3: portfolio/analysis/scanner/backtest tabs after APIs

- Likely files touched later: tab components, family-specific adapters, i18n, tests.
- Tests: aggregate-only states, result/log links, family-specific forbidden states, no raw prompt/payload/strategy dump.
- Browser verification: desktop/mobile tab and table layout.
- Dependencies: per-family admin read APIs stable.

Phase F4: security controls after backend/audit hardening

- Likely files touched later: security tab, action modals, typed-confirm controls, tests.
- Tests: read-only state, permission matrix, typed confirmation, audit event display, no credential reveal.
- Browser verification: destructive flow modal and mobile action layout.
- Dependencies: security-control APIs, audit event persistence, role/capability model.

Phase F5: admin audit route

- Likely files touched later: admin audit page, filters, detail drawer, tests.
- Tests: broad-audit permission, target-user access log, audit self-view notice, redaction.
- Browser verification: dense audit table, drawer, mobile layout.
- Dependencies: admin audit API and retention rules stable.

## 11. Testing and verification plan

Future implementation must include:

- Admin route gating and guest/non-admin forbidden states.
- No secret text in DOM for password/hash/token/cookie/API key/session/prompt/provider payload patterns.
- Chinese labels by default on `/zh` routes.
- Desktop and mobile responsive layout with no horizontal overflow.
- Loading, empty, no-data, error, forbidden, and partial-data states.
- Collapsed raw/developer details by default.
- Visible audit notices on sensitive views and tabs.
- Safe Admin Logs links only.
- Playwright desktop/mobile checks after routes exist.
- Mocked API fixtures only; no live APIs, no provider calls, no LLM calls.

## 12. Non-goals

- No implementation now.
- No raw database browser.
- No credential reveal.
- No plaintext password or password hash display.
- No frontend before backend contracts are stable.
- No auth/authorization behavior change.
- No provider, MarketCache, scanner, backtest, portfolio, AI, notification, or DuckDB behavior change.
- No React pages, routes, API clients, tests, CSS, i18n, dependencies, dev servers, browser verification, or live API calls in this docs-only task.
