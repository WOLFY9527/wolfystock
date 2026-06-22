# DATA-021 Real Data Value Acceptance

## Executive Verdict

PARTIAL

DATA-017 through DATA-020 move four product surfaces from "first-read copy is
safe" toward "the product can explain which real-data inputs are usable, which
are missing, and why score-grade output is or is not allowed." The accepted
scope is source/test review of repository contracts only.

This is not live provider acceptance, browser acceptance, public launch
approval, or production data-quality certification. It does not prove that the
operator environment has configured credentials, live feed entitlement, broker
sync, OPRA/options entitlement, durable scenario snapshots, or licensed breadth
and funds-flow sources.

## Acceptance Scale

- `2`: Bounded acceptance. Source/test evidence proves an additive contract or
  data packet, fail-closed authority/freshness behavior, and consumer-safe
  projection for the stated scope.
- `1`: Partial acceptance. Product value improved, but evidence still relies on
  mocked providers, fixtures, request-supplied inputs, observation-only states,
  or lacks live authority/freshness proof.
- `0`: Not accepted. Missing implementation/test evidence, raw/internal leakage,
  advice/execution implication, or weak data promoted as authoritative.

## Scope

This acceptance covers the product-value boundary added after DATA-016:

- DATA-017: Rotation Radar ETF/index quote coverage and authority readiness.
- DATA-018: Portfolio price, FX, valuation, and analytics lineage.
- DATA-019: Options Lab options-chain readiness boundary.
- DATA-020: Scenario Lab baseline snapshot readiness.

It intentionally does not cover full-site UX, Playwright/browser screenshots,
online provider calls, credential diagnostics from a target environment,
database migrations, provider runtime refactors, order/broker workflows, or new
analytics beyond the existing readiness contracts.

## Surface Scores

| Surface | Score 0-2 | Verdict | Product value now unlocked | Evidence | Remaining gap |
| --- | ---: | --- | --- | --- | --- |
| Rotation Radar | 2 | PASS for bounded quote readiness | ETF/index quote evidence now carries authority, score-contribution, family coverage, missing-symbol, and next-action state instead of only provider/fallback text. | `src/services/rotation_radar_quote_provider.py:1674`, `src/services/rotation_radar_quote_provider.py:1889`, `src/services/rotation_radar_quote_provider.py:2130`, `apps/dsa-web/src/api/marketRotation.ts:855`, `tests/test_market_rotation_radar_service.py:4007`, `tests/test_market_rotation_radar_service.py:4017` | Does not prove live credentials or entitlement in the target environment; does not make breadth, ETF holdings, or funds-flow score-grade. |
| Portfolio | 2 | PASS for snapshot lineage | Portfolio snapshot output can distinguish authoritative vs observation-only valuation based on price, FX, valuation snapshot, and analytics readiness. | `api/v1/schemas/portfolio.py:447`, `src/services/portfolio_service.py:2679`, `src/services/portfolio_service.py:2698`, `src/services/portfolio_service.py:2766`, `src/services/portfolio_service.py:2854`, `tests/test_portfolio_api.py:497`, `tests/test_portfolio_api.py:544`, `tests/test_portfolio_api.py:582`, `tests/test_portfolio_api.py:630` | Does not prove broker sync, real market-price source activation, FX provider freshness, or benchmark/factor mapping coverage in a target account. |
| Options Lab | 2 | PASS for chain readiness boundary | Options responses can classify complete authorized chains as ready and keep missing configuration, demo samples, sparse coverage, and missing IV/Greeks/OI/volume/quotes out of score-grade use. | `api/v1/schemas/options.py:413`, `api/v1/schemas/options.py:1059`, `api/v1/schemas/options.py:1080`, `api/v1/schemas/options.py:1126`, `tests/api/test_options_lab.py:790`, `tests/api/test_options_lab.py:818`, `tests/api/test_options_lab.py:838`, `tests/api/test_options_lab.py:860`, `tests/api/test_options_lab.py:897` | Does not add a live options provider, OPRA/vendor rights proof, redisplay approval, strategy ranking, GEX/vanna/charm, or trade workflow. |
| Scenario Lab | 2 | PASS for baseline readiness boundary | Scenario results now expose whether baseline snapshot, market frame, driver inputs, evidence completeness, source authority, and sample state make the scenario ready, partial, or blocked. | `src/services/market_scenario_lab_engine.py:846`, `src/services/market_scenario_lab_engine.py:894`, `src/services/market_scenario_lab_engine.py:930`, `src/services/market_scenario_lab_engine.py:1040`, `api/v1/schemas/market_scenario_lab.py:117`, `apps/dsa-web/src/api/scenarioLab.ts:31`, `tests/test_market_scenario_lab_engine.py:631`, `tests/test_market_scenario_lab_engine.py:634`, `tests/test_market_scenario_lab_engine.py:635` | Does not fetch fresh providers, persist scenario runs, or prove durable baseline snapshots exist in production. |

## Acceptance Findings

### Rotation Radar

- PASS: The backend publishes an `alpacaQuoteAuthorityReadiness` packet both in
  metadata and top-level response, so consumers can inspect readiness without
  parsing raw provider diagnostics (`src/services/rotation_radar_quote_provider.py:1674`).
- PASS: Quote coverage is grouped by bounded ETF/index family and carries
  configured, available, missing, stale, score-authority, and observation-only
  counts (`src/services/rotation_radar_quote_provider.py:1889`).
- PASS: Authority state fails closed to `unavailable` or `partial` unless the
  provider is configured, coverage exists, no required symbol is missing, and
  source authority is allowed (`src/services/rotation_radar_quote_provider.py:2130`).
- PASS: Consumer API normalization preserves the readiness packet while mapping
  visible labels away from raw provider/debug wording
  (`apps/dsa-web/src/api/marketRotation.ts:855`).
- PASS: Tests prove Alpaca-covered bounded ETF spines can be score-authority
  eligible without falling through to yfinance fallback, and that fallback or
  partial conditions remain observation-only
  (`tests/test_market_rotation_radar_service.py:4007`,
  `tests/test_market_rotation_radar_service.py:4017`,
  `tests/test_market_rotation_radar_service.py:4044`).

### Portfolio

- PASS: The snapshot schema exposes additive lineage fields for price, FX,
  valuation snapshot, and analytics readiness
  (`api/v1/schemas/portfolio.py:447`).
- PASS: The service builds one lineage summary from the snapshot, then derives
  authoritative vs observation-only state from price and FX completeness rather
  than hiding fallback values (`src/services/portfolio_service.py:2679`).
- PASS: Missing price fallback downgrades valuation to observation-only, and
  missing or stale FX downgrades risk/analytics readiness without downgrading
  unrelated price lineage (`tests/test_portfolio_api.py:544`,
  `tests/test_portfolio_api.py:582`, `tests/test_portfolio_api.py:630`).
- PASS: A fully covered price plus FX snapshot becomes complete and
  authoritative in the API contract (`tests/test_portfolio_api.py:497`).
- Risk note: when FX is missing, the service can still use a 1:1 stale fallback
  for arithmetic continuity. DATA-021 accepts only that the lineage surfaces the
  fallback and observation-only state, not that such valuation is
  live-authoritative.

### Options Lab

- PASS: `optionsChainReadiness` is an explicit additive contract with overall,
  chain, configuration, data-boundary, authority, score-authority, coverage,
  blocking-reason, and next-evidence fields (`api/v1/schemas/options.py:413`).
- PASS: Missing configuration and non-authoritative providers block score-grade
  use (`api/v1/schemas/options.py:1080`, `tests/api/test_options_lab.py:818`).
- PASS: Demo/sample chain data remains available for observation but blocked
  from score-grade use (`tests/api/test_options_lab.py:838`).
- PASS: Partial IV, Greeks, open interest, volume, quote, expiration, or strike
  coverage is represented as partial with explicit blocker codes
  (`tests/api/test_options_lab.py:860`, `tests/api/test_options_lab.py:897`).
- PASS: A complete authorized provider-backed chain can become ready with no
  remaining blocking reasons or next evidence (`tests/api/test_options_lab.py:790`).
- Scope note: this is chain-readiness acceptance. It does not prove a target
  environment can currently return an authorized live or delayed options chain.

### Scenario Lab

- PASS: The deterministic engine remains request/snapshot driven; it does not
  call providers, mutate cache state, or generate personalized advice
  (`src/services/market_scenario_lab_engine.py:1`).
- PASS: Baseline readiness is included in the engine result and API schema,
  covering baseline snapshot, market frame, driver inputs, evidence
  completeness, data state, sample state, score authority, and source authority
  (`src/services/market_scenario_lab_engine.py:846`,
  `api/v1/schemas/market_scenario_lab.py:117`).
- PASS: Real cached authoritative inputs can make readiness authoritative, while
  request-supplied, missing, fixture, sample, fallback, or source-authority
  failures remain observation-only (`tests/test_market_scenario_lab_engine.py:631`,
  `tests/test_market_scenario_lab_engine.py:634`,
  `tests/test_market_scenario_lab_engine.py:635`,
  `tests/test_market_scenario_lab_engine.py:656`).
- PASS: The frontend API normalizes readiness into consumer-safe labels such as
  `baselineReady`, `baselinePartial`, `evidenceBoundary`, `demoSample`, and
  `observationOnly` without requiring UI code to inspect raw backend internals
  (`apps/dsa-web/src/api/scenarioLab.ts:76`).
- Scope note: Scenario Lab has a contract for real cached authoritative
  baselines, but DATA-021 does not prove that such baselines are durably
  produced in the target environment.

## Cross-Surface Acceptance

- PASS: The four surfaces now share the same practical product rule: score-grade
  or authoritative state must be earned by coverage, freshness/source authority,
  and completeness; otherwise the product remains observation-only.
- PASS: Missing data is not converted into sample/demo product answers. It is
  represented as missing, partial, blocked, unavailable, fallback, stale, or
  observation-only depending on the surface contract.
- PASS: The added contracts are additive and fail-closed. They do not relax
  provider, source-authority, or score-contribution gates.
- PASS: The reviewed tests include both positive ready paths and negative
  fallback/missing/demo/partial paths.

## Confirmed Improvements Since DATA-016

- DATA-017 turns Rotation Radar quote authority from copy-only readiness into a
  bounded ETF/index evidence packet with family-level coverage and score
  contribution flags.
- DATA-018 turns Portfolio valuation from a single snapshot result into an
  explainable price/FX/valuation/analytics lineage packet.
- DATA-019 turns Options Lab from first-read readiness copy into a chain
  readiness contract that blocks unauthorized, demo, sparse, or incomplete
  chains.
- DATA-020 turns Scenario Lab from bounded scenario summaries into a snapshot
  readiness contract that can separate real cached authoritative baseline inputs
  from request-supplied or sample-only inputs.

## Remaining Blockers

None for this DATA-021 source/test acceptance scope.

The following remain blockers for live product acceptance:

- Target-environment evidence for configured and entitled Alpaca ETF/index
  quotes.
- Licensed/authorized breadth, flow, ETF holdings, and market proxy sources
  beyond the bounded ETF spine.
- Real broker/account snapshot evidence, price source activation, FX freshness,
  benchmark mapping, and factor mapping for Portfolio.
- Authorized options-chain provider integration, rights/redisplay review, IV/OI/
  volume/Greeks methodology evidence, and live/delayed freshness proof.
- Durable stored Scenario Lab baseline snapshots and target-environment evidence
  that real cached inputs exist.
- Browser acceptance for the four consumer surfaces after the readiness packets
  are populated with target-environment data.

## Recommended Next Tasks

- Run a target-environment Rotation Radar quote probe and archive sanitized
  credential/feed/entitlement evidence without exposing secrets.
- Add operator evidence for Portfolio price and FX source freshness on at least
  one real non-empty account snapshot.
- Select and approve an options-chain provider before any strategy, GEX, vanna,
  charm, or execution-adjacent work.
- Persist Scenario Lab baseline snapshots or wire them to an accepted durable
  market snapshot source before treating comparisons as product-grade.
- After target data is present, add browser acceptance that verifies the visible
  surfaces show useful facts and missing-evidence boundaries without raw
  provider/runtime diagnostics or advice wording.

## Validation Commands Run

Because this is a docs-only acceptance file, code tests are not required by the
repository validation matrix.

- `git diff --check`
  - Result: PASS, exit 0.
- `git diff --check origin/main`
  - Result: PASS, exit 0.
- `git diff --check origin/main...HEAD`
  - Result: PASS, exit 0.
- `bash scripts/release_secret_scan.sh --base-ref origin/main`
  - Result: PASS, exit 0. No high-confidence secret patterns found in changed
    text files.
- Overclaiming phrase scan for launch, production-ready, live-provider,
  execution, trading-recommendation, and fully-accepted claims.
  - Result: PASS after removing the command text from this record so the scan
    does not match itself.

Not run:

- `python scripts/check_ai_assets.py`: not required because this change does not
  modify AI collaboration governance files.
