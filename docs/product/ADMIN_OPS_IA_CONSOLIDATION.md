# WolfyStock Admin/Ops IA Consolidation Blueprint

Date: 2026-06-03 Asia/Shanghai  
Task ID: T-906  
Status: docs-only IA blueprint. No runtime/UI/API behavior changed.

## 1. Goal

Produce an implementation-ready information architecture blueprint for the
existing Admin/Ops surfaces using operator decision levels:

- `L0` global trust state
- `L1` incidents and evidence
- `L2` provider / cache / data operations
- `L3` user / product support
- `L4` controlled actions and raw detail

This blueprint reorganizes discovery, grouping, disclosure, and drill-through.
It does not delete routes, add runtime calls, change admin mutations, widen
provider behavior, or expose new sensitive payloads.

## 2. Non-goals

- No frontend route rewrite in this task
- No backend endpoint or schema change
- No provider probing, cache mutation, cleanup automation, or auth change
- No route deletion or path rename
- No credential, token, broker payload, raw prompt, stack trace, or raw
  provider payload exposure in default view

## 3. Current Route Inventory

Confirmed Admin/Ops routes from `apps/dsa-web/src/App.tsx`:

| Route | Current page | Notes | Primary level |
| --- | --- | --- | --- |
| `/settings/system` | `SystemSettingsPage` | Admin settings shell; lazy-loads `SettingsPage` control plane | L0 |
| `/admin/logs` | `AdminLogsPage` | Business-event-first admin logs and incident timeline | L1 |
| `/admin/evidence-workflow` | `AdminEvidenceWorkflowPage` | Manual operator evidence review lane | L1 |
| `/admin/notifications` | `AdminNotificationsPage` | Notification routing, test, ack, and channel management | L3 |
| `/admin/market-providers` | `MarketProviderOperationsPage` | Provider operations matrix, source gaps, readiness checklist | L2 |
| `/admin/provider-circuits` | `AdminProviderCircuitDiagnosticsPage` | Circuit, quota, probe, and SLA readiness diagnostics | L2 |
| `/admin/users` | `AdminUsersPage` directory | User directory and safe support summary | L3 |
| `/admin/users/:userId` | `AdminUsersPage` detail | User detail, sessions, portfolio, security | L3 |
| `/admin/users/:userId/activity` | `AdminUsersPage` activity | User activity timeline and redacted metadata | L3 |
| `/admin/cost-observability` | `AdminCostObservabilityPage` | Cost pressure, quota dry-run, ledger, pricing, cache efficiency | L2 |

Important inventory conclusion:

- There is no standalone Admin data-readiness route today.
- Data readiness already exists as a nested read-only concern inside
  `/admin/market-providers` through readiness checks, setup checklist, and the
  provider operations matrix.

## 4. Current Page And Panel Inventory

The table below classifies every current page and its visible panel families
into `L0` to `L4`.

### 4.1 `/settings/system`

| Current panel / area | Current purpose | Level |
| --- | --- | --- |
| System risk overview header | State, focus area, next step | L0 |
| Control plane summary | Cross-domain trust and readiness summary | L0 |
| AI / data source / notification / advanced domain switching | Domain support entry | L3 |
| Curated credential surfaces | Admin support configuration context | L3 |
| Raw fields section / drawers | Raw config detail kept secondary | L4 |
| Runtime cache reset / factory reset / dangerous actions | Controlled action zone | L4 |

### 4.2 `/admin/logs`

| Current panel / area | Current purpose | Level |
| --- | --- | --- |
| Header and view tabs | Business-vs-raw log posture and scope | L0 |
| Business event health summary | System trust posture from events | L0 |
| Operator issue rollup | Repeated operator-facing incidents | L1 |
| Missing / degraded data samples | Evidence-backed data gaps | L1 |
| Scanner execution summary | Product support evidence | L3 |
| Business events table / sessions | Incident and support lookup | L1 |
| Incident timeline drawer | Cross-event evidence chain | L1 |
| Storage advisory and cleanup preview | Controlled maintenance detail | L4 |
| Raw logs / debug logs / cleanup execution | Raw and destructive detail | L4 |

### 4.3 `/admin/evidence-workflow`

| Current panel / area | Current purpose | Level |
| --- | --- | --- |
| L0 operational verdict card | Manual review gate | L0 |
| Static review status grid | Evidence release state | L0 |
| Operator evidence path | Human review workflow | L1 |
| Local workspace guard | Evidence handling boundary | L1 |
| Command snippets | Operator runbook assistance | L4 |
| Dry-run preview / diagnostics console | Rawer preview and schema detail | L4 |
| Runbook references / schema reference groups | Support reference surface | L3 |

### 4.4 `/admin/notifications`

| Current panel / area | Current purpose | Level |
| --- | --- | --- |
| Page header and route intent | Alert routing posture | L0 |
| Route coverage summary | Current notification impact and coverage | L0 |
| Recent operational alert events | Incident ack and operator history | L1 |
| Channel setup form | Product support configuration action | L3 |
| Configured route list | Current channel ownership and safe destination summary | L3 |
| Dry-run/test results | Operational evidence for a channel | L1 |
| Developer details disclosure | Raw diagnostics kept collapsed | L4 |
| Toggle / create / test / acknowledge / unbind | Controlled actions | L4 |

### 4.5 `/admin/market-providers`

| Current panel / area | Current purpose | Level |
| --- | --- | --- |
| Page header and readability summary | Cross-surface provider trust posture | L0 |
| Source gap board | Missing provider / dependency impact | L1 |
| Provider setup checklist | Existing remediation path guidance | L2 |
| Surface focus block | Product-impact lens for provider gaps | L1 |
| Data source priority roadmap | Planned/read-only prioritization | L2 |
| Complete provider matrix disclosure | Full route-source-readiness matrix | L2 |
| Data readiness checks / grouped diagnostics | Readiness posture if present | L2 |
| Admin Logs drill links | Evidence drill-through | L1 |
| Full technical diagnostics / rawer metadata | Collapsed technical detail | L4 |

### 4.6 `/admin/provider-circuits`

| Current panel / area | Current purpose | Level |
| --- | --- | --- |
| Operational verdict card | Can production provider calls continue? | L0 |
| Summary metrics | Circuit / SLA / quota / probe trust state | L0 |
| Priority action list | What operator should handle first | L2 |
| Current circuit states | Current provider guardrail posture | L2 |
| Recent circuit events | Incident evidence | L1 |
| Quota windows | Operational pressure detail | L2 |
| Probe events | Operational evidence | L1 |
| Provider SLA / credential readiness | Data ops readiness | L2 |
| Error bucket / technical boundary disclosures | Rawer technical detail | L4 |

### 4.7 `/admin/users`, `/admin/users/:userId`, `/admin/users/:userId/activity`

| Current panel / area | Current purpose | Level |
| --- | --- | --- |
| Directory header summary | Safe support overview | L0 |
| User directory table/cards | Product support lookup | L3 |
| User detail hero | Safe per-user state and link-outs | L0 |
| Session list | User support investigation | L3 |
| Activity filters and timeline | User/product support evidence | L1 |
| Portfolio summary / holdings / activity | Product support and ownership view | L3 |
| Security status summary | Support security posture | L3 |
| Security action zone | Disable / enable / revoke sessions | L4 |
| Limitations / future-phase placeholders | Boundary disclosure | L4 |
| Redacted metadata disclosure | Raw detail kept collapsed | L4 |

### 4.8 `/admin/cost-observability`

| Current panel / area | Current purpose | Level |
| --- | --- | --- |
| Page header and top metrics | Cross-system cost trust posture | L0 |
| Main diagnostic board | Pressure, anomaly, attribution | L1 |
| Limitations and data quality | Evidence boundary and exactness | L1 |
| Filter rail | Scope control | L2 |
| Quota dry-run panel | Controlled diagnostics and operator action | L4 |
| Secondary details disclosure | Ledger, pricing, provider/cache detail | L2 |
| LLM ledger panel | Cost support detail | L3 |
| Pricing policy panel | Controlled pricing support detail | L3 |
| Provider/cache/scanner rollups | Data ops detail | L2 |
| Developer response-shape disclosures | Raw diagnostic shape | L4 |

## 5. Proposed Navigation Model

Do not remove routes. Add a shared Admin/Ops navigation taxonomy that groups the
existing routes by operator level and use case.

### 5.1 Default top-level grouping

| Group | Purpose | Routes |
| --- | --- | --- |
| `总览 / Trust` | First stop for current operational posture | `/settings/system`, filtered summaries from `/admin/logs`, `/admin/provider-circuits`, `/admin/cost-observability` |
| `事件 / Evidence` | What is broken, degraded, or awaiting review | `/admin/logs`, `/admin/evidence-workflow` |
| `数据运行 / Data Ops` | Provider, cache, readiness, quota, circuit operations | `/admin/market-providers`, `/admin/provider-circuits`, `/admin/cost-observability` |
| `用户支持 / Support` | User, product, channel, and ownership support | `/admin/users`, `/admin/notifications` |
| `受控动作 / Controlled Actions` | Dangerous actions and raw detail, always secondary | Existing L4 panels within current routes only |

### 5.2 Default left-nav proposal

1. `运营总览`
2. `事件与证据`
3. `数据源与就绪度`
4. `熔断与配额`
5. `成本观测`
6. `用户与活动`
7. `通知路由`
8. `系统设置`

Rules:

- Preserve existing route URLs and deep links.
- The nav label should describe operator intent, not implementation origin.
- `Controlled actions` do not become standalone first-level nav routes in the
  first rewrite; they stay inside the owning page under clear L4 affordances.
- `Data readiness` should appear as a sub-entry under `数据源与就绪度`, not as a
  new route in the first slice.

## 6. L0 Top Strip Contract

Every Admin/Ops page should begin with one consistent L0 strip before any
tables, disclosures, or controls.

### 6.1 Required fields

| Field | Meaning |
| --- | --- |
| `systemTrustState` | `healthy`, `observe`, `degraded`, `blocked`, `review_required`, `unknown` |
| `impact` | Which surfaces or users are affected, bounded and readable |
| `recommendedAction` | Single next operator action, not a long checklist |
| `evidenceRef` | Link or filter handle into the owning evidence surface |
| `lastUpdated` | Sanitized freshness marker |

### 6.2 Copy rules

- Show one operator sentence per field, not long prose.
- Use current-product language such as `继续观察`, `需要人工复核`,
  `相关 provider 生产调用应暂缓`, `仅沿既有配置路径处理`.
- Do not show raw IDs, payload fragments, URLs with tokens, or stack traces in
  the L0 strip.
- If a page is action-oriented, the action stays descriptive at L0 and the real
  control stays in L4.

### 6.3 Page-specific L0 strip targets

| Page | L0 trust question |
| --- | --- |
| System settings | Is the global admin control plane safe to operate? |
| Logs | Is there a current cross-surface incident that needs operator attention? |
| Evidence workflow | Can any review be promoted, or does it remain NO-GO? |
| Notifications | Are critical alert routes covered and acknowledged? |
| Market providers | Which product surfaces are missing or downgraded by provider gaps? |
| Provider circuits | Can production provider calls continue under current guardrails? |
| Users | Is this user/support state normal, risky, or action-required? |
| Cost observability | Is cost/quota posture stable, degraded, or likely to block? |

## 7. Disclosure And Collapse Rules

All collapsible panels must advertise what they contain before they open.

### 7.1 Required disclosure title contract

Each disclosure title must include:

1. `contents`
2. `count or impact`
3. `freshness`
4. `detail class`

Title pattern:

```text
<内容名称> · <数量/影响> · <freshness> · <detail class>
```

Examples:

- `最近熔断事件 · 6 条 · 24h · sanitized`
- `完整数据源矩阵 · 42 行 / 5 个产品面 · generated 09:12 · redacted`
- `Developer details · 1 failed webhook · now · raw-collapsed`

### 7.2 Allowed detail classes

| Label | Meaning |
| --- | --- |
| `sanitized` | Safe operator-readable detail |
| `redacted` | Sensitive fields removed or masked |
| `raw-collapsed` | Potentially technical / developer-heavy detail, collapsed by default |

### 7.3 Default-open policy

- `L0` never hides behind disclosure
- `L1` may be expanded by default only for the highest-severity current issue
- `L2` defaults open only for the top active workboard of the page
- `L3` defaults open only on user detail pages when the user explicitly entered
  that route
- `L4` always defaults collapsed unless it is an explicit action confirmation
  step

## 8. Safe Drill-through Contracts

Drill-through must stay explicit, typed, and sanitized. The goal is to move the
operator from posture to evidence without exposing raw payloads in the source
page.

### 8.1 Allowed drill-through links

| From | To | Contract |
| --- | --- | --- |
| Provider operations | Admin logs | `provider`, `surface`, `status`, `since`, `event family` |
| Provider circuits | Admin logs | `provider`, `route family`, `reason bucket`, `since` |
| Cost observability | Provider operations or logs | `route family`, `provider/cache area`, `window`, `reason code` |
| Cost observability | Notifications | `alert type`, `window`, `ack state` |
| User detail / activity | Admin logs | `target user`, `entity family`, `since` |
| Notifications | Admin logs | `channel`, `event type`, `delivery status`, `since` |
| Evidence workflow | Admin logs | `review bundle`, `artifact class`, `review stage` |
| Market providers | Evidence workflow | only when the issue requires human evidence packaging, not for routine provider health |

### 8.2 Required payload shape for any drill-through

```text
route
filter summary
safe identifiers only
time window
evidence class
```

Never pass:

- raw session IDs
- token-like strings
- webhook URLs with query params
- prompt bodies
- stack traces
- broker/account payloads
- raw provider responses

### 8.3 Navigation behavior

- Open the destination in its native page rather than embedding giant cross-page
  drawers everywhere.
- Show the applied filter summary at the top of the destination page.
- Preserve back navigation to the source page state.

## 9. Redaction And Secrets Policy

Default view must never expose:

- credentials or secret values
- tokens, cookies, session material, reset material, or webhook secrets
- raw broker/account payloads
- full prompts or raw model messages
- stack traces
- raw provider payloads

Default substitutes:

- configured / missing / disabled / dry-run states
- redacted handles or truncated identifiers
- bounded reason codes
- sanitized summary text
- evidence links into logs rather than inline raw objects

Page-specific requirements:

- `System settings`: curated credential surfaces only; raw fields remain
  secondary and redacted
- `Users`: hashed/truncated session handles only
- `Notifications`: webhook target masked in default view
- `Provider ops / circuits`: no credential values, no live probe secrets
- `Cost`: no user-level search by credentials or raw provider content
- `Evidence workflow`: local path placeholders and templates only, no real
  evidence bundle contents by default

## 10. Default Grouping Proposal By Page

This section defines how each existing page should be regrouped in the future
rewrite without changing route ownership.

### 10.1 System settings

- `L0`: global trust strip, risk summary, next action
- `L3`: domain control plane for AI, data sources, notifications, advanced
- `L4`: dangerous actions, raw fields, low-level config drawers

### 10.2 Admin logs

- `L0`: business-event trust strip
- `L1`: issue rollup, missing/degraded samples, incident timeline
- `L3`: scanner/product support summaries
- `L4`: raw logs, cleanup preview/execution, debug detail

### 10.3 Evidence workflow

- `L0`: release/no-go verdict
- `L1`: manual review status and workflow steps
- `L3`: runbook and schema references
- `L4`: command snippets, diagnostics console, raw-ish preview

### 10.4 Notifications

- `L0`: coverage and ack posture
- `L1`: recent alert failures and delivery evidence
- `L3`: channel setup and route ownership
- `L4`: test, toggle, unbind, developer diagnostics

### 10.5 Market providers

- `L0`: provider trust strip by impacted product surface
- `L1`: source gaps and impacted surfaces
- `L2`: setup checklist, readiness groups, route matrix
- `L4`: full technical matrix and rawer diagnostic disclosures

### 10.6 Provider circuits

- `L0`: can production calls continue?
- `L1`: recent circuit incidents if severity is high
- `L2`: current states, quota windows, SLA readiness, action queue
- `L4`: probe buckets, technical boundaries, raw diagnostic breakdowns

### 10.7 Users and activity

- `L0`: user trust strip and current support state
- `L1`: activity anomalies and audit evidence
- `L3`: sessions, portfolio, holdings, product ownership, safe support data
- `L4`: security actions and redacted metadata disclosures

### 10.8 Cost observability

- `L0`: cost/quota trust strip
- `L1`: pressure, anomaly, attribution, limitations
- `L2`: provider/cache/scanner rollups
- `L3`: LLM ledger and pricing support detail
- `L4`: quota dry-run action panel and developer response-shape disclosures

## 11. Implementation Rules For The Rewrite

- Keep all current routes valid.
- Add a shared Admin/Ops shell taxonomy before changing deep page internals.
- The first viewport must answer:
  - what is the trust state?
  - what is impacted?
  - what should the operator do next?
  - where is the evidence?
- Use row/table/workboard density before card sprawl.
- Raw/debug/developer content must be visually secondary and collapsed.
- `Controlled actions` must be visually isolated from summary state.
- `Evidence` drill-through must always land in a filtered evidence view, never
  in an unscoped raw dump.

## 12. Phased Execution Slices

### T-907 L0 Admin overview strip

Goal:

- Add the shared L0 strip contract to every Admin/Ops page.

Scope:

- Shared top-strip primitive
- Page-level mapping for trust state, impact, action, evidence ref, last updated
- No route deletion and no backend semantics change

### T-908 Provider Ops grouping

Goal:

- Reframe `/admin/market-providers` and `/admin/provider-circuits` around
  `L0 -> L1 -> L2 -> L4`.

Scope:

- Surface-first grouping
- Move readiness into an explicit `数据源与就绪度` sub-group
- Keep full matrix and technical detail collapsed

### T-909 Evidence / Logs drill-through

Goal:

- Normalize drill-through contracts across logs, evidence workflow, provider
  ops, cost, users, and notifications.

Scope:

- Filter-summary handoff
- Sanitized drill payload contract
- Native destination headers showing applied scope

### T-910 Admin disclosure cleanup

Goal:

- Standardize disclosure labels and collapse policy across all Admin/Ops pages.

Scope:

- Title contract with contents/count/freshness/detail-class
- Default-open rules by level
- Move raw/developer detail into consistent L4 affordances

## 13. Recommended Next-Step Summary

Recommended order:

1. `T-907` shared L0 strip
2. `T-908` provider and readiness regrouping
3. `T-909` drill-through contract unification
4. `T-910` disclosure cleanup sweep

Reason:

- The current pain is discoverability and operator comprehension, not missing
  runtime capability.
- A stable L0 strip and level taxonomy reduce rewrite risk before page-local UI
  work starts.
- Drill-through and disclosure cleanup should follow the new operator hierarchy,
  not precede it.

