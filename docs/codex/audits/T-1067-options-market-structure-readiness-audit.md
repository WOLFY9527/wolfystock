# T-1067 Options Market Structure Readiness Audit

Task ID: T-1067-AUDIT

Task title: Options market structure readiness audit

Mode: READ-ONLY-AUDIT docs-only artifact.

Allowed artifact:

`docs/codex/audits/T-1067-options-market-structure-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1067-options-market-structure-readiness-audit`
- branch: `codex/t1067-options-market-structure-readiness-audit`

Scope boundary:

- This audit inspects repo-local Options Lab market-structure readiness only.
- No runtime provider behavior, live calls, credentials, API schema, frontend behavior, tests, scoring math, strategy math, cache behavior, MarketCache behavior, provider ordering, broker/order path, portfolio mutation, config, lockfile, or CI behavior was changed.
- External provider claims were not refreshed in this task. The provider matrix remains useful historical context, but current provider pricing, entitlement, and field claims must be reverified before any live-provider decision.

## Executive Verdict

Defer market-structure readiness adoption.

Options Lab already has strong local guardrails for a market-structure-shaped workflow: normalized option contracts carry expiration, strike, side, multiplier, bid/ask/mid/last, volume, open interest, IV, Greeks, moneyness, spread, freshness, provider quality, and data-quality warnings (`api/v1/schemas/options.py:66`). The product docs also require readiness, data sufficiency, and no-advice framing before chain, Greeks, or strategy detail (`docs/options/README.md:19`).

The gap is not missing vocabulary. The gap is authority coupling. The repo has a live-evidence contract that can express quote freshness, chain freshness, expiration coverage, bid/ask coverage, OI, volume, IV, Greeks, IV-rank authority, event-calendar authority, SLA status, and readiness (`src/services/options_data_quality_gates.py:227`). However, current decision evaluation passes provider authority into `evaluate_options_data_quality_gates()` without passing provider live evidence (`src/services/options_lab_service.py:465`). The gate function accepts optional `provider_live_evidence`, and missing live evidence currently produces no live-evidence issue because `_provider_live_evidence_issues(None)` returns an empty list (`src/services/options_data_quality_gates.py:878`).

That means market-structure readiness should not be upgraded until the decision-grade path requires explicit live-evidence coverage. Today this is masked by a second safety layer: the internal policy keeps all current provider IDs, including `tradier`, `ibkr`, and `polygon`, at `live_observation_only` (`src/services/options_data_quality_gates.py:350`, `tests/test_options_data_quality_gates.py:323`). That safety layer is correct, but it is not a substitute for a future live-evidence requirement.

## What Counts As Market Structure Here

For this audit, "market structure" means the minimum option-chain and scenario evidence needed before any stronger-than-observation label:

- contract identity: symbol, contract symbol, side, expiration, strike, multiplier;
- chain availability and expiration coverage;
- price microstructure: bid, ask, mid, last, spread percent;
- activity and depth: volume and open interest;
- volatility and sensitivity: IV plus delta, gamma, theta, vega, rho;
- freshness: underlying quote freshness, chain freshness, as-of timestamps, stale/delayed class;
- authority: provider authority tier, provider live evidence, IV-rank authority, event-calendar authority;
- safety boundary: no broker execution, no order placement, no portfolio mutation, no trading recommendation.

This is not a request to enable a provider, fetch live chains, change score thresholds, or promote tradeability.

## Existing Ready Pieces

### 1. Provider contract shape exists

The provider adapter contract requires future adapters to implement `get_expirations()`, `get_underlying_quote()`, and `get_chain()` and to return sanitized normalized snapshots (`docs/audits/options-provider-adapter-contract.md:9`, `docs/audits/options-provider-adapter-contract.md:17`). It also names the required normalized fields for option contracts: bid/ask/mid/last, volume, OI, IV, Greeks, expiration, strike, side, multiplier, `asOf`, source, freshness, provider quality, and data quality (`docs/audits/options-provider-adapter-contract.md:21`).

The in-code provider capability metadata mirrors those requirements through support flags for expirations, chain, underlying quote, bid/ask, IV, Greeks, open interest, and volume (`src/services/options_market_data_provider.py:286`).

### 2. Fixture and disabled-live posture is explicit

The current provider implementation states that fixture providers remain default and Tradier HTTP transport is opt-in only, never enabled by default, and grants no decision or recommendation authority (`src/services/options_market_data_provider.py:2`). Fixture providers are the default provider keys, while live keys are only allowed names for fail-closed behavior (`src/services/options_market_data_provider.py:95`).

The docs are consistent: fixture providers are the only enabled providers, live stubs for `tradier`, `ibkr`, and `polygon` do not load credentials or call network APIs, and Tradier dry run remains `liveEnabled=false` plus `tradeableData=false` (`docs/audits/options-provider-adapter-contract.md:31`, `docs/audits/options-provider-adapter-contract.md:41`, `docs/audits/options-provider-adapter-contract.md:53`).

### 3. Contract and readiness schemas already expose the right user-facing boundary

`OptionsMetadata` defaults to read-only, fixture-backed, synthetic, no external calls, no LLM calls, no order placement, no broker connection, no portfolio mutation, and no trading recommendation (`api/v1/schemas/options.py:30`).

`OptionsResearchReadiness` exposes the current readiness core: readiness state, data-quality tier, decision-grade flag, provider authority, liquidity gate, IV/Greeks gate, spread gate, scenario coverage, no-trading boundary, blocking reasons, and next evidence needed (`api/v1/schemas/options.py:238`).

Decision-grade is intentionally narrow: data must be `live_usable`, provider authority must be `scoreGradeAllowed`, and liquidity, IV/Greeks, and spread gates must all be clear (`api/v1/schemas/options.py:556`).

### 4. Service scoring already consumes market-structure evidence

Decision evaluation uses data quality, liquidity, IV/Greeks readiness, breakeven, risk/reward, expected move, gate diagnostics, and score caps before returning a decision result (`src/services/options_lab_service.py:438`). The output carries gate decision, gate issues, decision-grade state, fail-closed reason codes, no-advice disclosure, freshness, and metadata (`src/services/options_lab_service.py:514`).

This is enough for read-only scenario observation. It is not enough for live market-structure authority.

### 5. Current tests prove the observation-only provider policy

Tests already prove complete Tradier-shaped live evidence cannot override the internal observation-only policy (`tests/test_options_data_quality_gates.py:104`). They also prove missing freshness, missing IV/Greeks coverage, missing IV-rank authority, and missing event-calendar authority are captured as live-evidence reason codes (`tests/test_options_data_quality_gates.py:129`), and that fixture, dry-run, stub, adapter-contract, and synthetic sources block live evidence readiness (`tests/test_options_data_quality_gates.py:153`).

Most importantly, current provider IDs remain below decision grade even with live-shaped inputs (`tests/test_options_data_quality_gates.py:323`).

## Readiness Gaps

### Gap 1: Live evidence is optional at the gate seam

`evaluate_options_data_quality_gates()` accepts `provider_live_evidence` (`src/services/options_data_quality_gates.py:1235`), folds live-evidence issues into the final gate (`src/services/options_data_quality_gates.py:1365`), and blocks decision grade if those issues exist (`src/services/options_data_quality_gates.py:1371`).

But missing live evidence itself is not an issue. `_provider_live_evidence_issues()` only iterates `reasonCodes` when a mapping is provided (`src/services/options_data_quality_gates.py:878`). This is safe while all current providers are observation-only, but unsafe as a future adoption path because a later provider-authority upgrade could accidentally bypass the explicit live-evidence coverage contract.

### Gap 2: `OptionsLabService.evaluate_decision()` does not build or pass live evidence

The decision service builds provider authority from fixture/provider metadata, but it does not build provider live evidence from the same snapshot before calling the gate function (`src/services/options_lab_service.py:465`). That leaves readiness based on contract-level data-quality gates plus provider authority, not on the full live-evidence contract.

### Gap 3: External authority tracks remain observation-only

The authority onboarding status says expiration calendar, event calendar, and IV-rank tracks remain observation-only and require manual external verification before source onboarding (`docs/audits/options-authority-onboarding-track-status.md:1`). IV-rank, event calendar, and expiration authority should therefore remain blockers or missing evidence, not hidden assumptions.

### Gap 4: Provider-specific market-structure proof is still manual

The adapter contract still requires proof of entitlement and field coverage for expirations, chain, bid/ask, last, volume, OI, IV, Greeks, multiplier, symbology, market-time freshness, and stale-data downgrade rules before any live adapter is enabled (`docs/audits/options-provider-adapter-contract.md:65`). That proof has not been added in this task.

## Unsafe Writes For T-1067

Do not use T-1067 to change:

- `src/services/options_market_data_provider.py`
- `src/services/options_lab_service.py`
- `src/services/options_data_quality_gates.py`
- `api/v1/schemas/options.py`
- `api/v1/endpoints/options.py`
- `apps/dsa-web/src/pages/OptionsLabPage.tsx`
- `tests/**`
- `.env.example`, config, provider credentials, network transports, MarketCache, provider routing, scanner/backtest/portfolio integrations, broker/order code, or strategy/score math

Those are protected runtime/API/test/provider domains and need a separate implementation prompt.

## One Bounded Next Write

Open a protected-domain, test-first gate-hardening task.

Allowed files for that next write:

- `src/services/options_data_quality_gates.py`
- `tests/test_options_data_quality_gates.py`

Goal:

- Make provider live evidence mandatory before any otherwise decision-grade provider-authority path can pass.
- Add a regression test where clean contract data plus decision-grade provider authority but missing `provider_live_evidence` fails closed with a new explicit reason code, for example `provider_live_evidence_missing`.
- Keep fixture, synthetic, dry-run, adapter-contract, and current provider IDs observation-only.

Forbidden in that next write:

- provider enablement;
- network calls;
- credential reads;
- API schema changes;
- frontend changes;
- Options Lab scoring, payoff, strategy, optimizer, copy, or no-advice changes;
- global provider fallback/order/cache changes.

After that gate-hardening task passes, a separate audit can decide whether `OptionsLabService.evaluate_decision()` should build `provider_live_evidence` from the current snapshot. Do not combine those two writes.

## Defer

Defer live options market-structure adoption, source authority, decision-grade readiness, and provider-specific field claims until the live-evidence mandatory gate exists and external entitlement/coverage/freshness evidence is manually verified.
