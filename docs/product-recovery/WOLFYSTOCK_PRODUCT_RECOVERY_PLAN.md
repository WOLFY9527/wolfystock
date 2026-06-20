# WolfyStock Product Recovery Plan

Status: canonical product recovery plan for PR-001.

This document supersedes low-value follow-up work that keeps iterating on
gates, badges, chips, source-authority wording, observation-only explanations,
diagnostics, and empty-state modules without restoring useful market or stock
research output.

WolfyStock is not ready for private beta in its current state.

## 1. Executive summary

WolfyStock's current failure is not isolated UI copy. The product has suffered a
product value collapse caused by three forces acting together:

- data gaps and source-authority gates prevent many research surfaces from
  reaching useful conclusions;
- internal diagnostics and data-governance state are exposed too prominently on
  consumer pages;
- evidence gates and no-advice boundaries are repeated so often that they have
  become the main product experience.

The recovery direction is simple: consumer surfaces must lead with market and
stock facts, synthesized observations, and next research steps. Source,
provider, debug, fallback, proxy, score-grade, cache, runtime, schema, request,
and trace details must move to admin surfaces or secondary disclosure. Broken or
empty surfaces must be repaired, hidden, redirected, or clearly quarantined
instead of rendered as full empty shells.

Future Codex and Qwen work must stop polishing the system's inability to answer
and must instead restore useful research output along the core path:

Market Overview -> Scanner -> Watchlist / Stock page.

## 2. Current product failure mode

The product currently explains why it cannot form conclusions more than it
helps the user understand market or stock state.

The repeated visible pattern is:

1. a page opens with limited or no useful market/stock facts;
2. the first viewport is consumed by gate language, data-quality caveats,
   observation-only boundaries, diagnostic strips, badges, or chips;
3. missing data is described repeatedly at module level;
4. the user receives little synthesis about what happened, what matters, or
   what to check next.

This creates a research cockpit that feels like an internal diagnostic console.
Even when individual gates are technically correct, the aggregate experience is
not useful enough for a private beta.

## 3. Consolidated evidence from real-machine audits

The external WorkBuddy audit files named in PR-001 were not present in this
worktree. This plan therefore uses the real-machine audit facts supplied in the
task prompt plus the repository audit documents inspected for this task.

Real-machine WorkBuddy audit facts supplied for PR-001:

- 14 pages reviewed; 11 failed; 0 fully passed.
- Data source usable rate was reported around 4/17, with major degraded or
  failed sources.
- Scanner produced 0 candidates and 0ms runs.
- Liquidity Monitor and Rotation Radar were reported as 404 or unavailable in
  the QA walk.
- The product repeatedly showed "data insufficient", "observation only", and
  "evidence unavailable" instead of useful research conclusions.
- Research usefulness was scored 2.5/10.
- Root-cause audit concluded that evidence gates, compliance disclaimers, and
  system diagnostics had swallowed the product UI.

Repository evidence incorporated:

- `docs/product-audit/qw003-screenshot-ux-qa-pass.md` concluded that the UI is
  built on a strong defensive architecture but reads like an internal research
  diagnostic console. It identified data-poor defaults, three competing design
  languages, 495+ chip/badge usages across 26 page files, disclaimer overload,
  fragmented onboarding, internal wording leakage, and opaque
  observation-only language.
- `docs/product-audit/qw006-consumer-internal-wording-sweep.md` found 23
  remaining consumer-visible wording issues after quick wins, including
  provider/cache/runtime/schema/internal/debug terms on consumer-accessible
  surfaces.
- `docs/product-audit/t1758-market-data-p0-root-cause-map.md` concluded that
  endpoints are mostly wired, but consumer evidence gates correctly reject
  fallback, stale, proxy-only, taxonomy-only, unavailable, or insufficient
  coverage inputs.
- `docs/data/market-source-activation-blueprint.md` locked the first data
  activation wave as official VIX/volatility, macro/rates/Fed liquidity, then
  US index/ETF quote coverage. It also kept real funds flow, options gamma,
  CN/HK flow, and other stronger-entitlement families outside the first wave.
- `docs/data-reliability/evidence-readiness-matrix.md` warns that tests and
  contracts do not approve visible source/freshness/fallback/stale/partial
  badges, provider authority inference, runtime wiring, or consumer metadata
  exposure.
- `docs/liquidity/README.md` states that Liquidity pages should lead with
  liquidity score and signal tables, while source/risk detail belongs in a
  bounded rail or disclosure. It also says provider/cache/raw diagnostics must
  not become the default primary content.
- `docs/rotation/README.md` states that Rotation Radar should lead with ranked
  themes/sectors and selected-theme evidence, not implementation diagnostics.
  It also locks fallback/static/taxonomy-only content out of headline lanes.

## 4. Root causes

### Product value collapse, not copy polish debt

The main issue is not that labels are imperfect. The issue is that many
consumer pages lack enough useful research output, then compensate by exposing
diagnostics, limitations, and boundary text.

### Data source gaps

Core market and stock outputs depend on source families that are incomplete,
degraded, delayed, proxy-only, not entitled, cache-only, or intentionally
excluded from score contribution. Until minimum reliable quote and market
coverage exists, consumer pages will continue to fail closed.

### Evidence gates over-presented to consumers

Fail-closed evidence gates are correct as backend and governance behavior. They
are wrong as the dominant consumer information hierarchy. The current product
often makes the gate more visible than the market or stock state.

### Diagnostics promoted into product UI

Provider, source, cache, runtime, schema, fallback, proxy, score-grade, request,
and trace details appear too close to primary consumer content. These details
are useful for operators and developers, but they should not be the default
consumer experience.

### Empty modules rendered as product surface

Broken, empty, unavailable, or prerequisite-missing surfaces are still rendered
as full pages or repeated modules. This makes "nothing useful is here" feel like
the product's normal state.

### Compliance boundary repeated at the wrong level

No-advice boundaries are necessary, but the current repeated per-card pattern
competes with research content. Compliance should be concise and global or
page-level by default, with detail available secondarily.

## 5. Stop-doing list for Codex/Qwen

Future Codex and Qwen tasks must not:

- add more consumer-visible `sourceAuthority`, score-grade, observation-only,
  proxy, or fallback explanations;
- add new diagnostic panels to consumer pages;
- add more badges, chips, pills, ribbons, trust strips, or status tags as a
  substitute for research conclusions;
- expand navigation before Market Overview, Scanner, Watchlist, and Stock pages
  are useful;
- use demo, fallback, proxy, synthetic, or tutorial data to fill production
  pages unless it is clearly isolated as tutorial/demo mode;
- treat no-advice compliance as repeated per-card disclaimers instead of a
  global or page-level disclosure strategy;
- continue mocked-proof tasks unless they directly unblock a user-visible
  research output;
- polish isolated labels while pages remain empty or research-useless;
- create new empty-state modules when the correct product decision is to hide,
  collapse, quarantine, repair, or redirect the surface;
- expose internal enum names, provider names, cache/runtime/schema/request/trace
  details, debug terms, or raw backend states in primary consumer copy;
- make source-governance details look like research facts;
- tune confidence, ranking, or source-authority gates to manufacture stronger
  conclusions before data proof exists.

## 6. Product recovery principles

- First screen must answer: what happened, what matters, and what to check next.
- Data quality details belong in details/admin, not the main consumer
  hierarchy.
- When data is missing, show one compact missing-data summary, not repeated
  module-level disclaimers.
- Hide or collapse modules that have no user-useful content.
- Prefer fewer useful pages over many empty pages.
- No consumer page should be dominated by system state explanations.
- Compliance boundary should be global or page-level and concise, not repeated
  per card.
- Consumer copy must not expose internal enum names, provider names,
  cache/runtime/schema/requestId/traceId/debug terms, fallback/proxy mechanics,
  or source-governance field names.
- Fail closed in backend and admin diagnostics; fail useful in consumer
  projection.
- A page with insufficient data should still help the user understand what is
  known, what is unknown, and what concrete research step comes next.

## 7. New consumer information hierarchy

Primary consumer pages must use this hierarchy:

1. Research answer: a concise synthesis of market or stock state.
2. Supporting facts: price, trend, breadth, liquidity, valuation, event, risk,
   update time, or coverage facts available for the surface.
3. What to check next: one to three next research steps, not trade
   instructions.
4. Missing-data summary: one compact note when material data is unavailable.
5. Secondary disclosure: source, freshness, data-quality, and methodology
   details behind an expandable or admin-oriented boundary.
6. Admin diagnostics: provider, cache, runtime, schema, request, trace, fallback,
   proxy, score-grade, and gate details outside default consumer flow.

Consumer pages should not start with:

- provider/source status tables;
- diagnostic rails;
- score-grade or source-authority explanations;
- repeated observation-only disclaimers;
- empty shell modules;
- navigation to more unavailable pages.

## 8. P0 recovery backlog

### P0-1 Consumer main surface recovery

Fold diagnostics and restore first-screen research value.

- For Market Overview, Scanner, Watchlist, Stock page, Liquidity Monitor, and
  Rotation Radar, audit the first viewport and remove diagnostic dominance.
- Replace repeated module disclaimers with one page-level missing-data summary.
- Keep primary content focused on what happened, what matters, and what to check
  next.
- Move provider/source/debug/fallback/proxy/score-grade details to admin or
  secondary disclosure.

Exit criteria:

- The first viewport contains a research synthesis or a single honest
  unavailable state.
- It is not dominated by chips, badges, diagnostics, or repeated boundary copy.

### P0-2 Core data reality path

Recover the path Market Overview -> Scanner -> Watchlist / Stock page.

- Market Overview must present a usable market state from available facts.
- Scanner must either produce real candidates or a single honest unavailable
  state with the reason and recovery path.
- Watchlist must show actionable saved-symbol status, at minimum price/update
  state/research status where available.
- Stock page must show a minimum viable research packet or clearly say the
  symbol cannot be researched yet.

Exit criteria:

- A user can start from Market Overview, identify something worth checking, run
  or understand Scanner state, save/revisit a symbol, and open a stock research
  packet without being trapped in diagnostic explanations.

### P0-3 Broken surface quarantine

Hide, repair, redirect, or quarantine broken and empty surfaces.

- Scanner 0ms pseudo-runs must not appear as successful product output.
- Route/404 issues for Liquidity Monitor and Rotation Radar must be repaired or
  hidden from primary navigation.
- Empty Portfolio, Options, Scenario Lab, and similar surfaces must collapse
  into concise unavailable/onboarding states until they have user-useful
  content.
- Pages that depend on unavailable prerequisites must state the prerequisite
  once and route the user to a useful next step.

Exit criteria:

- Broken routes are not exposed as normal navigation destinations.
- Empty shells are no longer rendered as full product experiences.

### P0-4 Developer diagnostic separation

Move internal terms and diagnostic detail out of consumer pages.

- Create or use admin/details areas for provider/source/cache/runtime/schema/
  request/trace/fallback/proxy/score-grade details.
- Keep no-advice and data-quality boundaries consumer-safe and concise.
- Preserve operator visibility without making it the consumer default.

Exit criteria:

- Primary consumer pages do not expose raw internal terms listed in the
  acceptance criteria.
- Admin diagnostics remain available for debugging and operations.

### P0-5 Repeated module collapse

Remove duplicate research queue, scan, scenario, and evidence-gap repetitions.

- Collapse repeated research queue prompts into one workflow entry point.
- Collapse repeated Scanner and Watchlist evidence-gap modules into one compact
  state summary per page.
- Collapse repeated Scenario/Options/Portfolio unavailable modules until real
  content exists.

Exit criteria:

- A user sees one clear page state and one next step instead of many modules
  restating the same missing evidence.

## 9. P1 recovery backlog

### P1-1 Data source usability proof

Prove minimum delayed quote coverage for US, CN, and HK watchlist and stock
research use, without claiming stronger authority than the data supports.

- Start with a small symbol set for US, CN, and HK.
- Record update time, availability, and failure class internally.
- Consumer output should show compact availability and update status only.

### P1-2 Market Overview synthesis layer

Create 3 to 5 natural-language market observations from available facts.

- Use current index, volatility, liquidity, breadth, and macro facts where
  available.
- Avoid provider/source diagnostics in the visible synthesis.
- If facts are insufficient, show one concise missing-data summary and next
  check.

### P1-3 Stock page minimum viable research packet

Every supported stock page should attempt to show:

- price and update time;
- trend and relative movement;
- valuation or fundamentals snapshot when available;
- recent event or catalyst summary when available;
- main risk or uncertainty;
- one compact missing-data summary.

If the packet cannot be assembled, the page must clearly say the symbol cannot
be researched yet.

### P1-4 Watchlist recovery path

Make saved symbols actionable instead of evidence-gap containers.

- Show price/update/research status for each saved symbol where available.
- Show which symbols can open a research packet now.
- Show one concise recovery path for symbols without enough data.

### P1-5 Portfolio onboarding reduction

Collapse demo and onboarding panels until holdings exist.

- Do not fill production portfolio pages with demo data.
- Show a concise create/import holdings path.
- Once holdings exist, show actual holdings state first and secondary education
  later.

## 10. Non-goals

This plan does not authorize:

- product runtime code changes in PR-001;
- frontend component edits in PR-001;
- backend/provider/cache/runtime edits in PR-001;
- confidence, ranking, scoring, source-authority, or provider-routing changes;
- demo/fallback data promotion into production research output;
- investment, trading, buy/sell, position sizing, target price, stop-loss, or
  execution recommendations;
- hiding material data limitations from users;
- removing admin diagnostics;
- expanding page inventory or navigation before core surfaces are useful;
- using more empty states, badges, or chips as the recovery strategy.

## 11. Acceptance criteria for recovery

Recovery is not accepted until all of these are true:

- A user can understand Market Overview's state in 10 seconds.
- Scanner produces either real candidates or a single honest unavailable state,
  not 0ms pseudo-results.
- A stock page shows a minimum viable research packet or clearly says the symbol
  cannot be researched yet.
- Watchlist shows at least price, update time, and research status for saved
  symbols, or a concise recovery path when that is not possible.
- No primary consumer page repeats "data insufficient", "observation-only", or
  equivalent wording more than once in the main viewport.
- No primary consumer page has raw internal terms such as score-grade,
  sourceAuthority, proxy-only, fallback, cache, provider, schema, runtime,
  requestId, or traceId.
- Broken routes are repaired, hidden, or redirected to a clear unavailable page.
- Admin diagnostics remain available but are not the default consumer
  experience.
- Primary navigation leads to fewer, useful surfaces instead of many empty
  shells.
- No compliance disclosure pattern overwhelms the research answer in the first
  viewport.

## 12. Task gating rules for future Codex work

Every future Codex or Qwen task that touches consumer product surfaces must pass
these gates before implementation:

1. Useful-output gate
   - State the user-visible research output this task improves.
   - If the task only adds diagnostics, badges, chips, labels, or empty-state
     copy, it is blocked unless it directly unlocks a P0/P1 recovery item.

2. Core-path gate
   - Prefer Market Overview, Scanner, Watchlist, and Stock page recovery over
     secondary surfaces.
   - Do not expand navigation or polish secondary modules while the core path is
     still research-useless.

3. Consumer hierarchy gate
   - First viewport must lead with market/stock facts, synthesized observations,
     and next research steps.
   - Internal diagnostics must be admin-only or secondary disclosure.

4. Missing-data gate
   - Missing data must be summarized once per page or primary workflow region.
   - Repeated module-level missing-data copy is blocked.

5. Broken-surface gate
   - If a surface is 404, unavailable, empty, or prerequisite-missing, the task
     must repair, hide, redirect, or quarantine it.
   - Rendering a full empty shell is not accepted.

6. Data-truth gate
   - Do not use fallback, proxy, synthetic, stale, or demo data as production
     research output unless it is clearly isolated as tutorial/demo mode.
   - Do not relax authority, score, confidence, ranking, or freshness gates to
     make output look stronger than the data supports.

7. Compliance gate
   - Keep no-advice boundaries concise and global/page-level by default.
   - Do not add repeated per-card disclaimers unless a specific legal/product
     review requires it.

8. Internal-language gate
   - Consumer copy must not expose raw internal enum names, provider names,
     source-governance field names, cache/runtime/schema/debug/request/trace
     terms, or fallback/proxy mechanics in primary hierarchy.

9. Mocked-proof gate
   - Mocked tests, fixtures, and proof artifacts are allowed only when they
     directly unblock a user-visible research output.
   - Mocked proof that only strengthens internal governance visibility is not a
     recovery task.

10. Final-report gate
    - Future tasks must report whether they improved a P0/P1 recovery item,
      whether product/runtime code was touched, whether protected domains were
      touched, and whether primary consumer hierarchy now favors research output
      over diagnostics.
