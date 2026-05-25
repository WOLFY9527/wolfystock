# WolfyStock Frontend Noise Budget

Status: current noise-budget contract for consumer-facing and
admin/maintenance frontend surfaces.

This document defines the maximum default diagnostic density allowed in the
first viewport for WolfyStock consumer and admin/ops pages. It exists to
prevent frontend rewrites from regressing into either developer-console
layouts or noisy user-facing product surfaces.

## Route Split

Every frontend route must be classified before UI work starts:

- consumer-facing product route
- admin, backstage, or maintenance route

If the route is consumer-facing, follow
`docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`.

If the route is admin-facing, follow
`docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md`.

Do not mix the two disclosure models in the same default viewport.

## Consumer Default Viewport Budget

Unless a task explicitly says otherwise, the default first viewport budget for
consumer-facing pages is:

- max 1 soft status banner
- max 5 compact product status chips
- max 3 summary cards
- max 1 line of user-safe reason per unavailable module
- no raw reason code
- no JSON
- no provider trace
- no backend field names
- no internal provider names unless the page is explicitly admin-only
- no maintainer remediation instructions
- details collapsed or routed to admin-only diagnostics

Consumer interpretation rules:

- Consumer status should look like product behavior, not maintainer evidence.
- One unavailable module gets at most one short user-safe explanation line.
- If technical detail is necessary for support, route it to an admin-only path
  rather than expanding the consumer surface.
- Consumer cards should show outcome, confidence, and last updated state before
  any explanation text.

## Admin Default Viewport Budget

Unless a task explicitly says otherwise, the default first viewport budget for
admin and maintenance pages is:

- max 1 alert banner
- max 5 status chips
- max 3 summary cards
- max 2 lines of explanatory text per card
- raw reason codes hidden by default
- JSON hidden by default
- Details collapsed by default
- repeated explanations forbidden

Interpretation rules:

- If one page state requires more than one banner, compress the page into one
  dominant operational verdict plus a ranked issue list.
- If a sixth chip is needed, move lower-priority modules into the inspector
  drawer or a secondary disclosure.
- Summary cards must summarize operational state, not restate the same
  degradation message three times.
- Long diagnostic prose belongs in the inspector drawer, not inline in every
  card.
- Raw diagnostics may exist for admin pages, but they remain collapsed by
  default.

## Component Contract

### TrustStatusChip

Purpose: communicate bounded state in one short label.

- Shows one status word from the shared vocabulary.
- May include a short module label.
- Must not include multi-clause diagnostic prose.
- Color and icon reinforce status only; they do not replace readable text.

### ReasonPopover

Purpose: expose the shortest useful explanation without opening a full panel.

- Triggered from hover or focus.
- Shows one-line reason only.
- Must translate backend diagnostic meaning into either product language or
  operator language depending on the route type.
- Must not dump raw field names, JSON, or stacked reason-code lists.

### InspectorDrawer

Purpose: hold the detailed operator investigation path.

- Opens from explicit click or keyboard activation.
- Contains module detail, action guidance, and bounded diagnostic explanation.
- May include structured lists, trust summaries, source availability, and links
  to deeper raw disclosures.
- Must remain scroll-bounded and internally organized by module or issue.

### DiagnosticDisclosure

Purpose: contain the raw diagnostic layer.

- Collapsed by default.
- May contain raw reason codes, raw field names, provider payload excerpts, and
  JSON.
- Must never auto-expand on initial render.

### ProviderHealthTable

Purpose: summarize provider and integration health in row-first form.

- Rows should answer provider, status, impact, and next action.
- Repeated reasons across rows should be normalized into shared wording.
- Expanded detail belongs in row-level disclosure or drawer handoff.

### DataHealthSummaryStrip

Purpose: provide compact L1 module status across the page.

- Limit visible chips to the top five priority modules.
- Keep labels short and comparable.
- Do not attach paragraph-length helper text to the strip.

### ActionItemList

Purpose: rank the operator's next steps.

- Each item should state issue, impact, and next action.
- Items should be sortable by severity or operational priority.
- The list is the default place for "what should the admin do next".

## Hover / Focus / Click Behavior

Default interaction contract:

- consumer chip -> one-line product explanation only
- admin chip -> one-line technical reason
- admin click -> inspector drawer
- raw diagnostics stay collapsed

Behavior rules:

- Hover and focus should reveal the same short explanation for pointer and
  keyboard users.
- Consumer hover/focus copy should stay product-safe and user-readable.
- Admin click should deepen context without replacing the chip label with
  inline noise.
- Raw diagnostics require an additional deliberate disclosure inside the
  inspector drawer or detail section.
- Users should never lose the L0/L1 operational summary when opening details.

## Compression Rules

Operational UI should compress long diagnostic text into a small, consistent
set of maintenance messages.

Preferred compression patterns:

- authorization problem -> `source is not authorized for scoring`
- scoring exclusion -> `does not participate in scoring`
- observation-only fallback -> `observation only`
- stale but readable -> `usable with stale data`
- missing provider setup -> `provider setup required`
- proxy fallback active -> `proxy evidence only`

Do not repeat the same explanation in banner, card, chip tooltip, and table row
unless each layer adds a different level of detail.

## Before / After Examples

### Example 0: same issue, different surface

Technical source state:

`configuredProviderAvailable=false, realSourceAvailable=false,
requiredProviderClass=authorized.us_etf_flow, proxyOnly=true`

Consumer-facing after:

`部分数据暂不可用，当前评分已暂停。`

Admin-facing after:

`Authorized ETF flow provider is unavailable. Proxy evidence only.`

### Example 1: scoring exclusion

Before:

`US breadth sector ETF rows carry sourceAuthorityAllowed=false and
scoreContributionAllowed=false because official_or_authorized.us_market_breadth
is not configured and the current proxy source is representative sample
observation only.`

After:

`US breadth proxy is visible for observation, but is not authorized for
scoring.`

Consumer-facing after:

`当前信号置信度较低，仅供观察。`

### Example 2: provider readiness

Before:

`configuredProviderAvailable=false, realSourceAvailable=false,
requiredProviderClass=authorized.us_etf_flow, missingProviderReason=missing
credential or entitlement, proxyOnly=true`

After:

`Authorized ETF flow provider is unavailable. Proxy evidence only.`

Admin action row:

`US ETF flow provider unavailable. Scoring blocked. Check authorization or
entitlement state.`

### Example 3: stale official data

Before:

`official_public CPI YoY monthly history is insufficient for a fresh reading;
latest observation is delayed and the current lane should not be presented as
realtime.`

After:

`Inflation lane is readable, but the latest official reading is stale.`

Consumer-facing after:

`已使用最近一次可用数据。`

### Example 4: backtest support artifact

Before:

`support_bundle_reproducibility_manifest_json missing from stored export set;
helper evidence incomplete for current run`

After:

`Reproducibility bundle is incomplete. Review support artifacts before relying
on this run.`

### Example 5: reason-code and confidence compression

Before:

`reasonFamilies=[source_confidence, score_blocked], sourceAuthorityAllowed=false,
scoreContributionAllowed=false, observationOnly=true`

Consumer-facing after:

`部分数据暂不可用，当前评分已暂停。`

Admin-facing after:

`Source is not authorized for scoring. Observation only.`

## Acceptance Checklist For Future Frontend Tasks

Use this checklist before landing a frontend rewrite:

- Does this route face consumers or admins?
- If consumer-facing, are provider names, reason codes, backend fields, and
  raw diagnostics absent by default?
- If admin-facing, are technical details progressively disclosed rather than
  dumped into the first viewport?
- Does every data-quality issue become either a graceful product state or an
  admin action item?
- Does the first viewport answer whether the system is usable?
- Does the page identify what is degraded or unavailable without raw payload
  text?
- Does the page show affected modules in a bounded strip or table?
- Does the page tell the admin what to do next?
- Is there at most one alert banner?
- Are there at most five visible status chips?
- Are there at most three summary cards?
- Does each summary card stay within two lines of explanatory text?
- Are raw reason codes hidden by default?
- Is JSON hidden by default?
- Are details collapsed by default?
- Are repeated explanations removed or consolidated?
- Does click-through move details into an inspector drawer instead of expanding
  inline noise everywhere?
- Are backend booleans translated into operator language?
- Does the page preserve backend semantics without exposing unnecessary
  developer wording?

If any answer is no, the page is not ready to replace or expand the current
frontend implementation.
