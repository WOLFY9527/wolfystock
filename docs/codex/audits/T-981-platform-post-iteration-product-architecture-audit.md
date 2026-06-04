# T-981 Platform Post-Iteration Product And Architecture Audit

Task: T-981 Platform post-iteration product and architecture audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact: `docs/codex/audits/T-981-platform-post-iteration-product-architecture-audit.md`

Observed range: T-918 `65127eea` through T-980 `dd0d0682`.

Validation scope: no broad test suites were run for the audit. The audit inspected
current history, prior audit docs, product/admin docs, key frontend pages,
SourceProvenance helper-only services and tests, and Playwright smoke specs.

## Executive Summary

WolfyStock is now coherent enough for a controlled user-testing round, provided
the round uses scripted tasks, known or mocked data, and explicit research-only
framing. It is not ready for broad public beta or decision-grade live-market
claims.

The iteration wave materially improved the product architecture. Home, Market
Overview, Scanner, Options Lab, Backtest, Liquidity Monitor, Rotation Radar, and
Admin/Ops now share a clearer pattern: compact readiness/evidence strips, safer
copy, fail-closed degraded states, bounded disclosures, and smoke coverage for
the most product-critical routes. The platform no longer reads as a collection
of unrelated experiments.

The main weakness is that trust architecture is still one step behind the UI:
`SourceProvenanceV1` and the sidecars are mature as helper-only projections, but
not yet consistently wired into runtime public payloads. Runtime adoption should
start with low-risk additive seams, not with Market/Liquidity/Rotation/Options
authority paths that already own scoring, readiness, and conclusion gating.

Current platform maturity score: **78 / 100**.

This score means the platform is strong enough for controlled product feedback,
but still below a broader launch threshold because provenance runtime adoption,
Scanner workflow clarity, Home upstream evidence quality, dense internal UX, and
e2e harness maintainability remain material risks.

## Maturity Score Rationale

What has improved:

- The product language is much safer: consumer surfaces consistently avoid
  execution-grade buy/sell/order/broker framing and use research/observation
  language.
- Home now has a real evidence packet path, citation surfacing, evidence coverage
  strip, LLM evidence input adapter, and a baseline technical chart.
- Market Overview has a visible actionability/evidence frame plus core visual
  evidence cards and bounded disclosures.
- Scanner now exposes readiness, top-down context, candidate evidence, and visual
  candidate summary without changing protected rank/score/filter semantics.
- Options Lab is better framed as an analytical lab with scenario evidence,
  readiness gates, payoff/IV visuals, and no-trading boundaries.
- Backtest result inspection now has real charting and robustness/risk-control
  visualization.
- Liquidity and Rotation have moved from raw-ish internal monitors toward
  observation surfaces with explicit unavailable/degraded states.
- Admin/Ops now has a clearer L0-L4 information architecture and safer
  disclosure/drill-through posture.
- Playwright smokes increasingly test product-critical visibility, negative raw
  leakage, no unsafe trading copy, and mobile/chart visibility.

What still prevents a higher score:

- Provenance sidecars are helper-only; runtime payload adoption is still partial
  or absent.
- Several product surfaces still expose expert density rather than guided
  first-screen workflows.
- Home LLM analysis quality still depends on whether evidence is preserved all
  the way into prompt input and report assembly.
- Market has multiple verdict vocabularies: readiness, actionability, market
  direction, temperature, and visual evidence can diverge unless consolidated.
- Scanner remains table/ranking-first even after top-down context was added.
- Liquidity and Rotation visuals are valuable, but their score/provenance
  semantics are sensitive and should not be casually promoted into runtime
  authority.
- The e2e harnesses are useful now, but are approaching brittleness because some
  fixtures and negative-pattern assertions are large and multi-domain.

## Surface-By-Surface Readiness

| Surface | Current readiness | Closest product value | Still weak / next step |
| --- | --- | --- | --- |
| Home | High for controlled testing | Best single-name product surface: readiness strip, evidence coverage, evidence packet, citations, LLM evidence adapter, ECharts technical chart | Runtime provenance sidecar should be attached additively from existing packet/citation/coverage fields; continue hardening LLM evidence preservation |
| Market Overview | Medium-high | Good macro/market cockpit: readiness strip, actionability frame, visual evidence strip, safe disclosure copy | Consolidate verdict vocabulary so readiness/actionability/temperature/visual cards do not compete; defer provenance runtime adoption until dedicated Market audit/write |
| Scanner | Medium | Strong power-user discovery surface: top-down context, candidate evidence, summaries, visual evidence distribution | Still ranking-table-first; needs guided top-down workflow refinement and candidate detail hierarchy without touching rank/score/filter semantics |
| Liquidity Monitor | Medium | Useful observation posture: fail-closed scoring pause, evidence quality, drivers, consumer-safe context | Trend visual is intentionally placeholder until time-series evidence exists; runtime provenance/score authority should remain helper-only for now |
| Rotation Radar | Medium | Visual matrix and family/theme flow provide real research value when relative-strength and stage data exist | Runtime authority is sensitive; do not wire provenance into score-driving rotation logic before a dedicated audit/write |
| Portfolio | Medium | Basic product surface and empty-state/read-model polish improved; reset/effect correctness was repaired | Not a primary research-evidence surface; future work should focus on stable read-model trust and narrow UX cleanup |
| Watchlist | Medium-low | Useful utility/watchboard with safer stale/error mapping and detail rail | Visual evidence is thinner than Scanner/Home; avoid overbuilding until watchlist-specific provenance and evidence task is scoped |
| Backtest | Medium-high for expert users | Real result inspection value: equity/drawdown/P&L chart, robustness lens, risk-control visualization, parameter matrix | Still expert/internal; needs controlled smoke coverage and clearer anti-overfitting/OOS evidence framing before broader testing |
| Options Lab | Medium-high for controlled analytical testing | Scenario evidence, readiness gates, payoff and IV visuals, no-order/no-broker boundaries | Dense controls and implicit auto workflow still feel internal; provenance runtime adoption should remain deferred |
| Settings/Admin/Ops | Medium for operators only | L0-L4 taxonomy, safer disclosure titles, redacted drill-through, settings/admin route smoke | Still operator-heavy and dense; fine for admin testing, not consumer product readiness |

## Architecture / Data Trust Assessment

### Evidence And Readiness Contracts

The platform now has a more coherent trust stack:

- `ResearchReadinessV1` is projected into Home, Market, Scanner, and Options
  surfaces.
- Home adds evidence coverage and a single-stock evidence packet, then surfaces
  the information in compact strips and citations.
- Market adds an actionability/evidence frame and consumer-visible market
  evidence visuals.
- Scanner adds `scannerContextFrame`, candidate evidence, candidate summaries,
  and top-down context UI while preserving rank/score/selection boundaries.
- Options adds readiness gates and scenario evidence with explicit no-trading
  boundaries.
- Source provenance now has a shared contract and sidecars for Home, Scanner,
  Market, Options, Liquidity, and Rotation.

This is the right architectural direction. The important constraint is that
these additions should remain additive, projection-only, fail-closed, and
derived from already assembled payloads unless a task explicitly scopes deeper
runtime/provider changes.

### SourceProvenanceV1 State

`SourceProvenanceV1` is mature enough as a helper-only normalizer. It has the
right contract language: source tier, authority, freshness, fallback/proxy,
observation-only, score-contribution eligibility, bounded debug refs, and
sanitized defaults. The sidecar tests also cover deterministic JSON shape,
fail-closed synthetic/fallback behavior, redaction, and no forbidden provider
imports.

It is not yet broadly ready for runtime payload adoption everywhere.

Safest first runtime integration:

1. **Home public response sidecar** derived only from existing evidence packet,
   citation, and evidence coverage fields.
2. **Scanner candidate public payload sidecar** derived only from candidate
   evidence/readiness/summary fields, with explicit rank/score/order unchanged
   tests.
3. **Admin/Ops diagnostic/readiness payloads** where the target user is an
   operator and disclosures already have L0-L4/redaction posture.

Safe after a dedicated narrow task:

- Watchlist local OHLCV / scanner-derived trust labels, if limited to
  read-model display and not ranking or account action.

Keep helper-only for now:

- Market Intelligence runtime actionability/temperature/briefing paths.
- Liquidity score-driving evidence and synthesis authority.
- Rotation score/stage/theme-flow authority.
- Options readiness/decision/scenario runtime surfaces.

Reason: those domains already contain local authority, gating, and conclusion
semantics. Adding a second provenance layer in runtime payloads can accidentally
create competing authority or promote observation/fallback evidence.

### Fail-Closed Posture

Fail-closed posture is now a visible platform strength. Missing or degraded
readiness tends to render insufficient/blocked/observe-only states rather than
ready states. The main future risk is consistency drift: as more sidecars are
runtime-wired, each surface must preserve the same conservative defaults instead
of inferring readiness from absent metadata.

## Frontend / UX / Visualization Assessment

### Information Architecture

Home and Market Overview now have the clearest first-screen hierarchy. They show
state, readiness, and evidence before deeper detail. Options and Backtest have
valuable workflows but still require expert interpretation. Scanner has added
top-down context, yet still reads as a ranking workbench first. Liquidity and
Rotation are useful research monitors, but they should remain clearly
observation-oriented.

Admin/Ops has the strongest structural IA improvement: the L0-L4 model creates
a useful operator taxonomy and prevents raw detail from dominating first
screens. The remaining risk is density, not conceptual direction.

### Visualizations With Real Research Value

High-value visuals:

- Home ECharts OHLC/volume/moving-average chart. This is a real product
  capability, especially because chart smoke checks visible chart nodes,
  timeframe/context text, fallback absence, and 390px viewport containment.
- Backtest equity/drawdown/daily P&L chart. This turns result inspection from a
  table-only experience into a useful research review.
- Options payoff and IV shape visuals. These are valuable because they map
  existing strategy/chain fields and retain no-advice/no-order framing.
- Rotation relative-strength matrix when structured stage and relative-strength
  data exist.
- Scanner visual evidence summary when used as a candidate evidence overview
  rather than a ranking authority.

Medium-value summarization visuals:

- Market Overview visual evidence cards and sparklines. Useful for scanning
  evidence posture, but not yet a deep charting surface.
- Liquidity posture, coverage, and driver panels. Useful for quickly
  understanding whether the monitor can say anything.

Decorative or placeholder risk:

- Liquidity trend panel is explicitly a placeholder until continuous time-series
  evidence exists.
- Any visual that merely restates chips or badges without adding time, shape,
  distribution, or coverage context should be deferred.

### Mobile / Narrow Viewport Risk

The wave added targeted mobile/chart smoke for Home and safer overflow patterns
in several dense surfaces. Residual risk remains on:

- Scanner ranking and candidate detail areas.
- Options SVG/payoff/IV panels with minimum widths.
- Backtest parameter and robustness tables.
- Admin/Ops tables and drill-through strips.
- Rotation matrix and theme lists when many themes are present.

Future mobile fixes should stay local: `min-w-0`, bounded internal horizontal
scroll, wrapping, and compact disclosure changes. Avoid global CSS or redesign
unless explicitly scoped.

### Card / Panel Sprawl Risk

The platform has mostly avoided uncontrolled card sprawl by using strips,
bounded disclosures, rows, matrices, and workbench sections. The highest risk
areas are Options, Scanner, Backtest, and Admin/Ops because each has naturally
dense data. The next UI iteration should reduce duplicated status panels rather
than add new ones.

## Test / Quality Assessment

Current smoke coverage is appropriately targeted, but close to the point where
domain splitting is necessary.

Strong coverage areas:

- Readiness strips across Home, Market, Scanner, and Options.
- Home evidence coverage/evidence packet browser checks.
- Scanner top-down blocked/insufficient contexts and candidate evidence.
- Market actionability/evidence strip and visual evidence cards.
- Options readiness/scenario/visuals with no raw or execution leakage.
- Home technical chart desktop/mobile visibility.
- Secondary consumer copy for Liquidity, Portfolio, Watchlist, and Backtest.
- Settings/Admin disclosures and shell route/admin affordance checks.

Remaining test risks:

- Large multi-domain Playwright fixtures make future edits brittle.
- Negative leakage patterns are valuable, but can overmatch legitimate boundary
  copy unless allowlists stay disciplined.
- Backtest visuals need a dedicated route/browser smoke similar to Home chart.
- Scanner visual evidence and mobile density need product-flow smoke, not just
  component assertions.
- React Doctor risk remains outside the repaired Portfolio slice, especially in
  Home, Scanner, Options, and Market/Admin pages.
- This audit did not run broad tests or browser screenshots; it is a code/docs
  inspection audit, not a full visual QA pass.

## Top 10 Remaining Risks

1. Runtime provenance adoption is still missing or deliberately deferred on most
   surfaces.
2. Home can still produce weaker analysis if upstream evidence is not preserved
   through LLM input and report generation.
3. Scanner remains ranking-table-first and not fully guided as a top-down
   research workflow.
4. Market Overview has overlapping verdict vocabularies that can drift.
5. Options Lab remains dense and workflow-heavy despite safer copy and visuals.
6. Liquidity and Rotation provenance integration could accidentally affect
   score/stage authority if done without a dedicated task.
7. Some visual blocks summarize state well but are not yet true analytical
   charts.
8. Playwright e2e harnesses are growing large and need domain-level splitting.
9. React Doctor backlog still affects key product pages after Portfolio fixes.
10. Docs now contain many audit/roadmap fragments; the platform needs one
    consolidated post-wave roadmap after the next runtime provenance slice.

## Recommended Next Task Sequence

### P0

1. **Home runtime provenance additive contract**
   - Shape: backend additive contract.
   - Scope: derive `SourceProvenanceV1` sidecar entries from existing Home
     evidence packet, citation frame, and evidence coverage frame only.
   - Must not change provider calls, cache behavior, LLM prompts, report scoring,
     or Home chart behavior.
   - Verify with API tests and no raw/internal leakage assertions.

2. **Controlled user-testing smoke pack**
   - Shape: e2e smoke.
   - Scope: scripted Home, Market Overview, Scanner, Options Lab, and Backtest
     flows with known data/mocks.
   - Include no raw leakage, no execution-grade trading copy, visible first
     screen readiness/evidence, and narrow viewport overflow checks.
   - Split by product domain if the existing readiness smoke becomes too large.

### P1

3. **Scanner candidate provenance runtime sidecar**
   - Shape: backend additive contract.
   - Scope: candidate-level sidecar from candidate evidence/readiness/summary
     only.
   - Must prove rank, score, order, filters, selection, and persisted shortlist
     are unchanged.

4. **Home and Scanner compact provenance display**
   - Shape: frontend display.
   - Scope: consume only landed runtime sidecar payloads in existing strips or
     bounded disclosures.
   - Must fail closed when payloads are missing and avoid new card sprawl.

5. **Scanner top-down workflow refinement**
   - Shape: frontend UX.
   - Scope: improve hierarchy from regime/context -> candidate evidence ->
     detail without changing ranking, scoring, filters, provider behavior, or
     cache behavior.

6. **React Doctor targeted cleanup**
   - Shape: React Doctor cleanup.
   - Scope: Scanner, Home, and Options in small batches.
   - Must avoid copy churn and broad memoization sweeps.

### P2

7. **Backtest visual smoke and robustness clarity**
   - Shape: e2e smoke plus focused frontend display if needed.
   - Scope: result chart visibility, robustness/OOS/parameter-stability clarity,
     mobile overflow containment.
   - Must not change backtest engine math or strategy semantics.

8. **Consolidated post-wave roadmap doc**
   - Shape: audit/docs.
   - Scope: merge T-892, T-913, T-917, T-918, T-925, T-929, T-930, T-953, T-957,
     and T-981 into one current roadmap/status map.
   - Useful after Home/Scanner provenance runtime slices land.

### Defer

- Market/Liquidity/Rotation/Options runtime provenance adoption until each has a
  dedicated read-only audit followed by a narrow write task.
- New decorative charts without stronger data shape.
- Broad UI redesign across all surfaces.
- Broad e2e rewrite before the next controlled user-testing smoke pack proves
  which flows matter most.

## Safe Parallelization Map

Can be safely parallelized later if write scopes remain isolated:

| Parallel lane | Conditions |
| --- | --- |
| Home additive provenance payload | Does not touch Home LLM prompt/provider/cache/chart behavior |
| Scanner candidate provenance payload | Does not touch Home or shared provenance contract; proves ranking unchanged |
| Admin/Ops frontend IA polish | Uses existing Admin/Ops primitives only and avoids API/RBAC/mutation changes |
| Backtest visual smoke | Tests-only or Backtest-only display scope; no engine math |
| Portfolio/Watchlist polish | Read-model/frontend-only; no account mutation or scanner ranking |

Do not parallelize:

- Home provenance runtime integration with Home LLM evidence/prompt changes.
- Scanner provenance runtime integration with Scanner UX/ranking workflow work.
- Market actionability/provenance tasks with Market Overview verdict/copy tasks.
- Options scenario/product workflow tasks with Options provenance/readiness
  runtime work.
- Liquidity and Rotation runtime authority/provenance work.
- Admin L0/drill-through/disclosure changes that share the same admin
  primitives.
- Any task touching shared contract/schema/source-provenance core files with
  another task touching the same contract.

## Do-Not-Do-Now List

- Do not wire provenance sidecars into Market, Liquidity, Rotation, or Options
  runtime payloads as a broad sweep.
- Do not change Scanner ranking, score, shortlist order, filters, or persisted
  rank semantics while adding evidence/provenance display.
- Do not add buy/sell/order/broker recommendation language or execution CTAs.
- Do not expose raw provider payloads, raw prompts, stack traces, route internals,
  cache internals, environment names, credentials, or raw session IDs.
- Do not add new chart panels that only restate chips or copy.
- Do not run broad React Doctor memoization rewrites.
- Do not combine product UX, runtime provenance, and e2e harness splitting in one
  task.
- Do not use controlled user testing to validate live decision-grade financial
  advice.

## Final Recommendation: External UX / Design Expert Review

Wait until after the first Home and Scanner runtime provenance slices land, then
run a focused external UX/design expert review.

Reason: the current platform is coherent enough for internal and controlled
scripted user testing, but an external design review now would likely spend too
much time on trust/provenance questions that the architecture already knows are
not fully wired. The next best sequence is:

1. Land Home provenance runtime payload.
2. Land Scanner candidate provenance runtime payload.
3. Add the controlled user-testing smoke pack.
4. Run an external UX/design review focused on first-screen clarity, evidence
   comprehension, mobile density, and whether users understand the no-advice
   boundary.

The external review should not be asked to redesign the platform wholesale. It
should evaluate whether a user can answer: what state am I seeing, what evidence
is missing, what is safe to conclude, and what should I inspect next.

## Audit Closeout

No source code, test, API/DTO/schema, frontend UI, backend/provider/cache/runtime,
config/lockfile/CI, or changelog changes are part of this audit artifact.
