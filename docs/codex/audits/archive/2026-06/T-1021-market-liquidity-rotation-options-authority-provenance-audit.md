# T-1021 Market/Liquidity/Rotation/Options Authority Provenance Roadmap Audit

## Metadata

- Task ID: T-1021-AUDIT
- Task title: Market Liquidity Rotation Options authority and provenance roadmap audit
- Mode: READ-ONLY-AUDIT report artifact
- Date: 2026-06-05
- Workspace: `/Users/yehengli/worktrees/t1021-authority-provenance-roadmap-audit`
- Branch: `codex/t1021-authority-provenance-roadmap-audit`
- Allowed diff: this audit document only

## Scope

This audit follows the T-1014 recommendation to inspect authority and provenance gaps before any broad
runtime provenance writes. It covers four consumer finance surfaces:

- Market Overview
- Liquidity Monitor
- Rotation Radar
- Options Lab

This is a roadmap audit, not an implementation plan for runtime metadata. It deliberately does not add
providers, change API contracts, change score math, change fallback/live semantics, or implement provenance UI.

## Executive Verdict

The four surfaces already contain meaningful authority guardrails, but their maturity differs. Rotation Radar
and Options Lab have the strongest explicit API/schema boundaries. Liquidity Monitor has strong indicator and
diagnostic models, but one service-built observation snapshot is not locked in the public response schema.
Market Overview has clear service-level fail-closed behavior and consumer readiness projection, but its
temperature endpoint remains less DTO-locked than Rotation and Options.

Future work should start with display-only translation and placement using existing fields. DTO/API work should
be opened only as narrow additive contract tasks. Provider/cache/runtime work remains protected-domain work and
must not be bundled with display cleanup.

## Per-Surface Verdict Matrix

| Surface | Current authority/provenance state | Display-only gaps | DTO/API/provider/runtime gaps | Verdict |
| --- | --- | --- | --- | --- |
| Market Overview | Service builds `marketActionabilityFrame`, `marketIntelligenceEvidenceFrame`, `regimeSummary`, and `researchReadiness`; fallback/stale states fail closed through `conclusionAllowed`, `scoreCap`, freshness, and source tier gates. | Consumer copy and rail placement can be tightened so source/freshness detail stays secondary and weak inputs do not read as live. | Temperature is still mainly a service dict projection rather than a tightly typed public DTO like Rotation/Options. Any change to `conclusionAllowed`, score caps, `regimeSummary.label`, MarketCache, provider fallback, or official macro freshness is protected backend/runtime work. | Display cleanup is safe; authority changes are protected. |
| Liquidity Monitor | Schema exposes `coverageDiagnostics`, indicator evidence, `capitalFlowSignal`, `liquidityImpulseSynthesis`, and `sourceMetadata`; `capitalFlowSignal` is explicitly observation-only and non-score-grade. | Consumer evidence selection already translates many raw diagnostics, but future cleanup can further separate consumer text from admin/source terms. | Service builds `observationEvidenceSnapshot`, while `LiquidityMonitorResponse` does not expose that snapshot in the typed response model. Any provider activation, real source allowlist, cache behavior, or score contribution change is protected work. | Display cleanup is safe; one additive DTO lock task may be warranted. |
| Rotation Radar | Strongest explicit contract. Summary lanes separate headline/rank-eligible themes from observation/taxonomy themes; `consumerEvidenceSnapshot` is whitelist-only and forbids extra fields. Provider diagnostics are separate from consumer evidence. | UI still derives some display quality when a field is absent; future work should keep that as translation only and avoid source-authority recomputation. | Any change to quote provider activation, Alpaca/yfinance fallback, cache behavior, `rankEligible`, `headlineEligible`, `rankingLane`, `sourceAuthorityAllowed`, or `scoreContributionAllowed` is protected runtime/API work. | Current boundary is mature; avoid broad writes. |
| Options Lab | Fixture/dry-run first. Metadata, research readiness, provider authority, gates, no-trading boundary, and scenario frame fail closed unless live/tradeable/decision-grade evidence is explicitly allowed. | Readiness/no-advice and data sufficiency display can be refined using existing fields; provider diagnostics should stay contained. | Any live provider enablement, `providerAuthority` upgrade, data-quality tier change, decision-grade gate change, payoff/optimizer/ranking math, broker/order path, or option-chain freshness semantic change is protected work. | Strong safety boundary; provider changes must stay separate. |

## Surface Findings

### Market Overview

Current evidence and authority state:

- `regimeSummary` on `/api/v1/market/temperature` is documented as additive and observation-only; it must not
  promote source authority, score-grade rights, or live provider status
  (`docs/market-overview/README.md:23`).
- Liquidity and Rotation observation signals may only feed bounded context and must not change the
  `regimeSummary.label`, confidence, source authority, or score contribution
  (`docs/market-overview/README.md:28`, `docs/market-overview/README.md:32`).
- Missing, stale, fallback, unavailable, or contradictory inputs must fail closed to `mixed_no_clear_edge`
  with blockers, confidence caps, and watch items (`docs/market-overview/README.md:41`).
- Freshness/source detail belongs in a rail or disclosure, and official macro rows must preserve delayed or
  stale semantics rather than being projected as realtime (`docs/market-overview/README.md:44`,
  `docs/market-overview/README.md:48`).
- The service builds temperature payloads from reliable inputs only, sets fallback/stale metadata for weak
  inputs, and attaches actionability/evidence/readiness/provider-health snapshots
  (`src/services/market_overview_service.py:1107`, `src/services/market_overview_service.py:1222`).
- `researchReadiness` is derived from `conclusionAllowed`, `scoreCap`, freshness, source tier, fallback, stale,
  synthetic, and unavailable flags (`src/services/market_overview_service.py:1273`).
- The frontend consumes normalized temperature payloads and either extracts or infers consumer research
  readiness before rendering the readiness strip (`apps/dsa-web/src/pages/MarketOverviewPage.tsx:369`,
  `apps/dsa-web/src/pages/MarketOverviewPage.tsx:927`).

Display-only gaps:

- The current frontend already normalizes consumer copy, but future display work should continue moving raw
  source/freshness detail into secondary rails and avoid primary-market language that implies a live or
  score-grade state.
- Any frontend inference must remain a consumer-safe fallback view, not a new authority source.

DTO/API/provider/runtime gaps:

- Compared with Rotation Radar and Options Lab, Market Overview temperature remains less explicitly DTO-locked.
  A future additive DTO task could lock the consumer-visible subset and preserve old payload fields.
- Any change to `conclusionAllowed`, `scoreCap`, `sourceAuthorityAllowed`, `scoreContributionAllowed`,
  `regimeSummary.label`, official macro freshness, provider routing, or MarketCache behavior is backend/runtime
  protected-domain work.

### Liquidity Monitor

Current evidence and authority state:

- Liquidity Monitor may expose additive `coverageDiagnostics` and `capitalFlowSignal` metadata
  (`docs/liquidity/README.md:25`).
- `capitalFlowSignal` is explicitly observation-only, assembled from existing cached/proxy payloads, not real
  fund-flow data, and must keep `sourceAuthorityAllowed=false` and `scoreContributionAllowed=false`
  (`docs/liquidity/README.md:30`).
- Missing, stale, fallback, synthetic, or unavailable inputs must not appear live or contribute strong score
  (`docs/liquidity/README.md:49`).
- The schema hard-codes the `LiquidityMonitorCapitalFlowSignal` as diagnostic-only, observation-only,
  non-authority, non-decision-grade, and non-score-contributing
  (`api/v1/schemas/liquidity_monitor.py:38`).
- Indicator evidence and coverage diagnostics carry source tier, freshness, fallback/stale/partial/unavailable,
  observation-only, source-authority, and score-contribution fields
  (`api/v1/schemas/liquidity_monitor.py:76`, `api/v1/schemas/liquidity_monitor.py:122`).
- The service response includes score, freshness, indicators, an `observationEvidenceSnapshot`,
  `capitalFlowSignal`, `liquidityImpulseSynthesis`, and `sourceMetadata`; `sourceMetadata` states whether
  external provider calls occurred and keeps runtime/cache mutation false
  (`src/services/liquidity_monitor_service.py:360`).
- The consumer UI filters raw terms such as provider, proxy, fallback, source, authority, cache, runtime, raw,
  JSON, diagnostics, provider names, and snake_case before showing consumer copy
  (`apps/dsa-web/src/pages/LiquidityMonitorPage.tsx:1117`).

Display-only gaps:

- Consumer display can further separate "usable for observation", "score-ready", and "temporarily unavailable"
  states with existing fields.
- Admin/operator diagnostic labels should stay in admin disclosure levels, not consumer first viewport text.

DTO/API/provider/runtime gaps:

- `observationEvidenceSnapshot` is built by the service, but `LiquidityMonitorResponse` currently lists score,
  freshness, indicators, `capitalFlowSignal`, `liquidityImpulseSynthesis`, advisory disclosure, and
  `sourceMetadata` without that snapshot (`api/v1/schemas/liquidity_monitor.py:194`). If this snapshot is meant
  to be public, it needs a narrow additive DTO lock task.
- Real-source activation, score contribution allowlists, provider class fulfillment, cache behavior, and
  liquidity score inclusion rules are protected backend/provider/cache/runtime work.

### Rotation Radar

Current evidence and authority state:

- Fallback/static, synthetic, unavailable, and taxonomy-only themes may remain visible for observation, but are
  not eligible for headline or strongest-theme ranking (`docs/rotation/README.md:21`).
- Clients must consume headline lanes only when `rankEligible=true`, `headlineEligible=true`, and
  `rankingLane="headline"` (`docs/rotation/README.md:24`).
- Alpaca activation, runtime budgets, and yfinance fallback are bounded, and fallback/static data must not be
  marked live (`docs/rotation/README.md:36`).
- `consumerEvidenceSnapshot` is documented as whitelist-only and excludes credentials, provider budgets, source
  authority router internals, admin diagnostics, score/weight breakdowns, ranking trust, and raw provider
  payloads. It must not recompute authority, score authority, ranking, headline eligibility, provider routing,
  or cache behavior (`docs/rotation/README.md:75`).
- `themeFlowSignal` and `rotationFamilyRollup` are observation-only and must not change or infer
  `rankEligible`, `headlineEligible`, `rankingLane`, `sourceAuthorityAllowed`, `scoreContributionAllowed`,
  provider routing, cache authority, or category promotion semantics (`docs/rotation/README.md:93`).
- The API schema exposes theme and summary authority flags, then provides a strict consumer snapshot with
  `extra="forbid"` and required consumer evidence in the response model
  (`api/v1/schemas/market_rotation.py:102`, `api/v1/schemas/market_rotation.py:314`,
  `api/v1/schemas/market_rotation.py:340`).
- The frontend resolves signal type and evidence-quality display from payload fields, with a fallback derivation
  when quality is absent (`apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:168`,
  `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:210`).

Display-only gaps:

- Frontend fallback derivation should be treated only as a label fallback. It must not become source authority
  or ranking logic.
- Provider diagnostics and activation details should remain outside consumer first-viewport surfaces.

DTO/API/provider/runtime gaps:

- Rotation already has a mature typed consumer evidence contract. Future DTO work should only be opened if a
  specific additive field is required and can preserve the existing strict consumer snapshot.
- Provider activation, quote-provider deadlines, fallback source selection, cache behavior, rank/headline lane
  eligibility, score contribution, and theme-flow authority semantics are protected runtime/API work.

### Options Lab

Current evidence and authority state:

- Options Lab should start with scenario readiness, data sufficiency, and no-advice framing before chain,
  Greeks, or strategy detail; provider behavior and adapter semantics are protected runtime behavior
  (`docs/options/README.md:19`, `docs/options/README.md:25`).
- Provider outputs must be sanitized normalized snapshots; raw provider payloads, request URLs, API keys, tokens,
  account identifiers, and stack traces must not be returned by APIs
  (`docs/audits/options-provider-adapter-contract.md:17`).
- Missing provider values must remain missing and degrade data quality; the service must not fabricate Greeks,
  IV, bid/ask, volume, or OI to make contracts appear usable
  (`docs/audits/options-provider-adapter-contract.md:29`).
- Fixture providers are the only enabled providers; live adapter stubs and Tradier dry-run remain disabled by
  default and do not authorize live requests, broker/order execution, portfolio mutation, scanner/backtest
  fallback changes, or score-threshold changes
  (`docs/audits/options-provider-adapter-contract.md:31`,
  `docs/audits/options-provider-adapter-contract.md:39`,
  `docs/audits/options-provider-adapter-contract.md:63`).
- The provider-neutral service docstring states fixture providers remain default and Tradier HTTP transport is an
  explicit opt-in market-data path that grants no decision or recommendation authority
  (`src/services/options_market_data_provider.py:2`).
- Options metadata defaults to read-only, fixture-backed, synthetic, no external calls, no order placement, no
  broker connection, no portfolio mutation, and no trading recommendation
  (`api/v1/schemas/options.py:30`).
- Research readiness and provider authority only become score-grade when metadata is live-enabled, tradeable,
  and decision-grade; fixtures, synthetic data, dry-run, adapter contract, and fallback paths remain
  observation-only (`api/v1/schemas/options.py:238`, `api/v1/schemas/options.py:299`).
- Decision responses populate readiness, scenario frame, no-trading boundary, blocking reasons, and missing
  evidence, while positive decision labels are mapped to observation framing in the consumer scenario frame
  (`api/v1/schemas/options.py:1217`, `api/v1/schemas/options.py:1337`,
  `api/v1/schemas/options.py:791`).
- The UI maps synthetic/demo/delayed data and non-decision-grade gates into observation/readiness copy
  (`apps/dsa-web/src/pages/OptionsLabPage.tsx:201`, `apps/dsa-web/src/pages/OptionsLabPage.tsx:279`,
  `apps/dsa-web/src/pages/OptionsLabPage.tsx:541`).

Display-only gaps:

- Readiness, data sufficiency, and no-advice framing can be made more consistent across top-level chips,
  scenario frame, chain quality, and detail panels using existing fields only.
- Provider diagnostics should remain in bounded disclosure areas and should not be promoted into consumer
  conclusion copy.

DTO/API/provider/runtime gaps:

- Any provider-authority upgrade, live adapter enablement, data-quality tier change, decision-grade gate change,
  option-chain freshness semantic change, optimizer/payoff/gate math change, broker/order path, or portfolio
  mutation is protected work and must be split from display tasks.

## Cross-Surface Gap Classification

### Display-only gaps

These may be opened first, provided they only consume existing fields:

- Translate raw authority and freshness states into consumer-safe status copy.
- Keep source/freshness details in rails, disclosures, drawers, or admin-only layers.
- Prevent raw provider, cache, runtime, snake_case, source-authority, and score-contribution terms from leaking
  into consumer copy.
- Keep fallback, stale, partial, synthetic, unavailable, and observation-only states visibly bounded.

### DTO/API gaps

These require narrow additive contract tasks:

- Market Overview temperature consumer-ready DTO lock for the currently rendered authority/readiness subset.
- Liquidity Monitor schema alignment if `observationEvidenceSnapshot` is intended to be a public field.
- Any new cross-surface consumer data-quality contract must be additive, backwards compatible, and tested against
  old payload subsets.

### Provider/cache/runtime protected-domain gaps

These must not be mixed with display-only work:

- Provider activation, provider order, live-call paths, retry/timeout/fallback behavior, and entitlement logic.
- MarketCache TTL, SWR, cold-start, mutation, or provenance write behavior.
- Any score math, gate threshold, rank/headline lane, score-contribution, or source-authority rule.
- Any fallback/live/stale/partial/synthetic semantics that would change whether data appears usable.

## Recommended Future Sequence

Open at most these three tasks, in this order:

1. **T-1021-R1 Display-only authority translation cleanup**
   - Scope: frontend copy/placement/tests only, using existing fields.
   - Goal: make consumer surfaces consistently show bounded states without raw provider/cache/runtime/source-authority
     language.
   - Must not change: API contracts, backend services, providers, caches, score math, or fallback/live semantics.

2. **T-1021-R2 Narrow DTO contract lock for Market temperature and Liquidity observation snapshot**
   - Scope: additive schema/contract tests only if product confirms these fields should be public.
   - Goal: lock the consumer-visible subset while preserving existing payloads.
   - Protected warning: because this touches API/schema, it needs backend contract validation and should not include
     provider/runtime changes.

3. **T-1021-R3 Protected-domain design audit for any future runtime provenance writes**
   - Scope: design/audit first, not implementation.
   - Goal: define exact provider/cache/runtime boundaries before any write path or live-source authority change.
   - Must explicitly cover MarketCache, provider activation, fallback/live semantics, Rotation ranking/headline lanes,
     Liquidity score contribution, and Options provider authority.

## Do Not Open Yet

Do not open these as implementation tasks from this audit:

- Broad provenance sweep across Market/Liquidity/Rotation/Options.
- Provider additions or live adapter enablement.
- Options broker/order/portfolio integration.
- Score math, ranking, headline eligibility, gate threshold, optimizer, or payoff changes.
- Fallback/live/stale/partial/synthetic semantic changes.
- MarketCache provenance writes, TTL/SWR/cold-start changes, or runtime cache mutation changes.
- Cross-surface contract reshaping or stored contract-version migration.

## Validation Plan

Required validation for this docs-only audit:

- `git diff --check`
- `./scripts/release_secret_scan.sh`

Expected final diff:

- `docs/codex/audits/archive/2026-06/T-1021-market-liquidity-rotation-options-authority-provenance-audit.md`
