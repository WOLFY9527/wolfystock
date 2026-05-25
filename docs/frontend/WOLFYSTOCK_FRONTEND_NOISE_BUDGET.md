# WolfyStock Frontend Noise Budget

Status: current noise-budget contract for admin and maintenance-facing
frontend surfaces.

This document defines the maximum default diagnostic density allowed in the
first viewport for WolfyStock admin/ops pages. It exists to prevent frontend
rewrites from regressing into developer-console layouts.

## Default Viewport Budget

Unless a task explicitly says otherwise, the default first viewport budget is:

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
- Must translate backend diagnostic meaning into operator language.
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

- chip shows status
- hover/focus shows one-line reason
- click opens inspector drawer
- raw diagnostics stay collapsed

Behavior rules:

- Hover and focus should reveal the same short explanation for pointer and
  keyboard users.
- Click should deepen context, not replace the chip label with inline noise.
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

### Example 1: scoring exclusion

Before:

`US breadth sector ETF rows carry sourceAuthorityAllowed=false and
scoreContributionAllowed=false because official_or_authorized.us_market_breadth
is not configured and the current proxy source is representative sample
observation only.`

After:

`US breadth proxy is visible for observation, but is not authorized for
scoring.`

### Example 2: provider readiness

Before:

`configuredProviderAvailable=false, realSourceAvailable=false,
requiredProviderClass=authorized.us_etf_flow, missingProviderReason=missing
credential or entitlement, proxyOnly=true`

After:

`Authorized ETF flow provider is unavailable. Proxy evidence only.`

### Example 3: stale official data

Before:

`official_public CPI YoY monthly history is insufficient for a fresh reading;
latest observation is delayed and the current lane should not be presented as
realtime.`

After:

`Inflation lane is readable, but the latest official reading is stale.`

### Example 4: backtest support artifact

Before:

`support_bundle_reproducibility_manifest_json missing from stored export set;
helper evidence incomplete for current run`

After:

`Reproducibility bundle is incomplete. Review support artifacts before relying
on this run.`

## Acceptance Checklist For Future Frontend Tasks

Use this checklist before landing any admin/maintenance frontend rewrite:

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
