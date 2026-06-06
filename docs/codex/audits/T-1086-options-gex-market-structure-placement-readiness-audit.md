# T-1086 Options GEX Market-Structure Placement Readiness Audit

Task ID: T-1086-AUDIT

Task title: Options GEX market-structure placement readiness audit

Mode: READ-ONLY-AUDIT with task-authorized docs-only artifact, commit, and push.

Allowed artifact:

`docs/codex/audits/T-1086-options-gex-market-structure-placement-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1086-options-gex-market-structure-placement-audit`
- branch: `codex/t1086-options-gex-market-structure-placement-audit`
- base commit inspected: `9aeb042c426a451364b3e08a21afa8b680787236`

Scope boundary:

- This audit inspected repository-local Options Lab, options data-quality gates, options service and provider boundaries, options docs, Market Overview IA, admin evidence placement, and frontend Options Lab IA.
- No source, tests, config, package, lockfile, provider/cache/runtime/API/frontend behavior, provider enablement, network calls, credential reads, market-structure/GEX/gamma flip/call wall/put wall implementation, broker/order, portfolio, backtest, scanner, scoring, payoff, strategy, optimizer, or no-advice behavior was changed.
- No external vendor research was performed and no paid vendor is selected or endorsed.

## Executive Verdict

Future GEX, positive/negative gamma, call wall, put wall, and related option-market-structure indicators should live first in Options Lab as an observation-only derived evidence layer.

They should not be added to Market Overview as a primary panel, should not create a new consumer Market Structure route yet, should not be hidden only in admin evidence, and should not be pushed down into provider adapters, global provider runtime, MarketCache, or Options Lab scoring and optimizer paths.

The current repository is ready for a docs/test prerequisite task that defines an additive observation contract. It is not ready for implementation, public API fields, provider enablement, cache semantics, or decision-grade use.

## Placement Verdict

| Candidate home | Verdict | Reason |
| --- | --- | --- |
| Options Lab | Primary future home | Options docs define Options Lab as the domain entry point before changing provider adapters, option-chain readiness, Greeks display, UI, scenario/strategy copy, or no-advice policy (`docs/options/README.md:3`, `docs/options/README.md:5`). The route is already dedicated at `/options-lab` (`apps/dsa-web/src/App.tsx:405`). The frontend taxonomy classifies Options Lab as an `ExperimentConsole` whose primary region is a scenario/strategy decision board and whose secondary rail is a risk boundary rail (`docs/frontend/visual-system.md:117`, `docs/frontend/visual-system.md:121`). |
| Market Overview | Not the first home | Market Overview owns broad market state and comparative boards, with source/freshness detail secondary (`docs/frontend/visual-system.md:142`). Its current tab/module taxonomy covers indices, volatility, funds flow, sentiment, rates, breadth, rotation, macro, crypto, and related broad panels, but no options-chain market-structure module (`apps/dsa-web/src/pages/MarketOverviewTabConfig.ts:30`). Single-underlying option walls would blur Market Overview's domain unless a later aggregate, observation-only downstream summary is separately designed. |
| New Market Structure module | Defer | A separate consumer route would be premature. The current scope is single-underlying options-chain derived evidence, and Options Lab already owns the necessary assumptions, readiness, chain, scenario evidence, and no-advice boundary. A new route may be revisited only if future requirements become cross-underlying, cross-surface, or non-options-specific. |
| Admin-only evidence module | Secondary diagnostic home only | Admin evidence can store methodology provenance, source proof, dry-run validation, and operator diagnostics. It is not the consumer research placement. The current admin evidence preview treats Options evidence as blocked with disabled `options_recommendation` and `options_tradeability` claims (`apps/dsa-web/src/components/evidence/adminEvidenceDryRunPreviewData.ts:49`). |
| Provider/cache/runtime layer | Not a product home | Provider adapters should return sanitized normalized snapshots, not derived market-structure decisions (`docs/audits/options-provider-adapter-contract.md:17`). MarketCache/cache/runtime changes are protected domains and are not prerequisites for a docs/test observation contract. |

## Existing Ready Pieces

Options Lab already has the correct safety shell:

- Public metadata defaults to read-only, fixture-backed, synthetic, no external calls, no LLM calls, no order placement, no broker connection, no portfolio mutation, and no trading recommendation (`api/v1/schemas/options.py:30`).
- Contracts already carry side, expiration, strike, multiplier, bid/ask/mid/last, volume, open interest, IV, Greeks including gamma, DTE, moneyness, spread, freshness, provider quality, data quality, and warnings (`api/v1/schemas/options.py:66`).
- Readiness already separates data-quality tier, provider authority, liquidity gate, IV/Greeks gate, spread gate, scenario coverage, decision-grade, no-trading boundary, blocking reasons, and next evidence (`api/v1/schemas/options.py:238`).
- Decision-grade still requires live usable data, score-grade provider authority, clear liquidity, clear IV/Greeks, and clear spread (`api/v1/schemas/options.py:556`).
- The service now passes both provider authority and provider live evidence into the decision and optimizer gate seams (`src/services/options_lab_service.py:467`, `src/services/options_lab_service.py:1137`).
- Missing provider live evidence fails closed when otherwise required (`src/services/options_data_quality_gates.py:879`, `tests/test_options_data_quality_gates.py:240`).

This is enough to anchor future market-structure as bounded evidence. It is not enough to implement or promote it.

## Required Data Inputs

Do not pick a vendor from this audit. The required inputs are provider-neutral:

| Input class | Required facts | Current state |
| --- | --- | --- |
| Chain identity | Underlying symbol/market/currency, expiration, strike, side, contract symbol, multiplier, deliverable/corporate-action handling, symbology normalization. | Basic fields exist on current contracts (`api/v1/schemas/options.py:66`). Deliverable/corporate-action proof remains a future provider requirement (`docs/audits/options-provider-adapter-contract.md:69`). |
| Chain market fields | Bid, ask, mid, last, volume, open interest, IV, full Greeks, per-field as-of/freshness, provider quality, data quality. | Current normalized contract fields exist, and the provider contract forbids fabrication of Greeks, IV, bid/ask, volume, or OI (`docs/audits/options-provider-adapter-contract.md:21`, `docs/audits/options-provider-adapter-contract.md:29`). |
| Coverage and freshness | Expiration coverage, bid/ask coverage, OI coverage, volume coverage, IV coverage, Greeks coverage, quote freshness, chain freshness, market-session max age. | Live-evidence builder can express coverage and freshness from normalized snapshots (`src/services/options_data_quality_gates.py:787`). Provider-specific freshness and entitlement proof remains missing. |
| GEX methodology | Formula, unit convention, whether exposure is per 1 percent or per 1 point move, expiration aggregation window, strike bucketing, spot reference, multiplier use, stale/OI handling, missing-Greeks handling, confidence caps. | No repository-local contract or methodology doc found for GEX, gamma flip, call wall, or put wall. |
| Positive/negative gamma semantics | Explicit assumption mode for sign convention, dealer positioning/participant positioning assumption, and whether sign is provider-supplied or model-derived. | Current contracts contain gamma, side, open interest, and multiplier, but no signed dealer-exposure or positioning authority. Positive/negative gamma must remain assumption-labeled and observation-only. |
| Call wall / put wall semantics | OI or GEX concentration rules by side/strike, tie-breakers, minimum coverage thresholds, freshness thresholds, and labels that avoid support/resistance claims. | Per-contract OI exists, but no wall summary contract or authority threshold exists. |
| Rights and authority | Entitlement, redistribution rights, decision-use rights, delayed/live plan state, production/sandbox state, and source-authority policy. | Options authority onboarding remains observation-only for expiration calendar, event calendar, and IV rank (`docs/audits/options-authority-onboarding-track-status.md:1`). |

## Observation-Only Versus Decision-Grade

Classify as observation-only:

- Any GEX, gamma regime, gamma flip, call wall, put wall, OI concentration, or strike-concentration display built from current repository data.
- Any positive/negative gamma label unless the payload explicitly carries authorized signed-exposure semantics and the methodology says how sign is determined.
- Any output derived from fixture, synthetic, delayed, dry-run, stub, adapter-contract, fallback, stale, partial, unknown freshness, missing OI, missing IV, missing Greeks, missing multiplier/deliverable proof, or missing entitlement evidence.
- Any admin evidence, source-candidate evidence, external verification worksheet, or provider self-claim before policy approval.

Classify as decision-grade: none for T-1086.

A future stronger-than-observation market-structure path would require a separate protected-domain task with additive DTO review, provider/source authority review, live-evidence proof, methodology approval, no-advice review, and focused regression tests. It must not be inferred from current contract fields.

## No-Advice And Product Safety Rules

Future UI/API wording must avoid turning market structure into a trading signal:

- Prefer labels such as `仅观察`, `观察型市场结构`, `Gamma 状态待补证`, `Call OI 密集区`, `Put OI 密集区`, `覆盖不足`, `等待证据更新`, and `人工复核`.
- Avoid labels such as `买入`, `卖出`, `立即交易`, `下单`, `best contract`, `guaranteed`, `support confirmed`, `resistance confirmed`, `must hold`, or `AI recommends you buy`.
- Do not feed GEX/walls into trade-quality score, strategy ranking, payoff math, optimizer preference, scanner ranking, backtest logic, portfolio risk, broker/order, or notification action semantics.
- Keep no-order, no-broker, no-portfolio-mutation, and no-trading-recommendation disclosure visible. Trading No-Advice policy requires Options Lab to show data quality, source, freshness, delayed/fallback/synthetic state, and missing fields before tradeability-like labels (`docs/audits/trading-no-advice-product-policy.md:99`).

Options Lab already has the right IA slots: readiness and gate summary in the hero (`apps/dsa-web/src/pages/OptionsLabPage.tsx:1433`), scenario evidence as a bounded evidence workspace (`apps/dsa-web/src/pages/OptionsLabPage.tsx:1810`), and risk boundary rail (`apps/dsa-web/src/pages/OptionsLabPage.tsx:2055`). Future market-structure display should sit below readiness, likely as L2 scenario evidence and L4 methodology/detail disclosure, not as the route headline.

## Missing Prerequisite Matrix

| Prerequisite | Status | Required before implementation |
| --- | --- | --- |
| Observation contract | Missing | Define an additive `optionsMarketStructureObservation` contract with `observationOnly=true`, `decisionGrade=false`, methodology version, input coverage, freshness, missing evidence, no-trading boundary, and consumer-safe labels. |
| Public DTO/API slot | Missing and not recommended yet | Current endpoints cover summary, expirations, chain, analyze, decision, scenario, and strategy compare (`api/v1/endpoints/options.py:454`, `api/v1/endpoints/options.py:538`). Do not add API fields before the observation contract and tests exist. |
| Provider capability metadata | Missing for market structure | Current provider capabilities stop at expirations, chain, underlying quote, bid/ask, IV, Greeks, OI, and volume (`src/services/options_market_data_provider.py:286`). No provider should claim GEX or wall authority without a separate contract. |
| Methodology | Missing | Specify formulas, units, bucketing, sign assumptions, stale/OI policy, multiplier/deliverable handling, confidence caps, and labels. |
| Authority and rights | Missing | Prove entitlement, redistribution, decision-use rights, freshness, coverage, and source authority. No paid vendor is selected here. |
| Live-evidence gate integration | Existing, protected | Preserve current provider authority and live-evidence gates. Any future market-structure contract must consume gate state and fail closed, not bypass it (`src/services/options_data_quality_gates.py:1385`). |
| Cache/runtime semantics | Missing, protected | No options-derived cache/TTL/invalidation seam is approved. `forceRefresh` is currently metadata only and can be ignored (`src/services/options_lab_service.py:1381`). Cache/runtime design must be a separate protected-domain task. |
| Frontend IA and copy tests | Missing for market structure | Add tests before UI implementation to keep market-structure copy observation-only, hide raw provider/debug details, and prevent order/advice wording. |
| Admin evidence placement | Partial, diagnostic only | Admin may later show methodology/provenance/operator evidence, but consumer placement remains Options Lab. |

## Protected-Domain Warnings

Do not change these domains for market-structure placement:

- provider global order, live-call paths, first-good-wins fallback, retry/timeout behavior, credential loading, provider entitlement checks, provider runtime, or adapter transport;
- MarketCache TTL, SWR, cold-start fallback, cache keys, derived cache namespaces, or payload meaning;
- Options Lab scoring, gates policy, payoff math, strategy optimizer semantics, recommendation/no-advice policy, API response shape, or stored contract versions;
- broker/order paths, portfolio mutation/accounting, backtest, scanner scoring/ranking, notification routing, AI/LLM prompts, auth/RBAC/security;
- any GEX/gamma flip/call wall/put wall implementation.

Current provider posture also remains protected: fixture providers are default, live provider names are fail-closed keys, and the Tradier path is dry-run/adapter-contract only, not decision authority (`src/services/options_market_data_provider.py:1`, `docs/audits/options-provider-adapter-contract.md:39`).

## Exactly One Recommended Future Task

Open one docs/test prerequisite task:

**T-1086-R1 Options market-structure observation contract**

Goal:

- Define an Options Lab additive observation contract for `optionsMarketStructureObservation`.
- Document GEX, gamma regime, gamma flip, call wall, and put wall as observation-only terms.
- Define required inputs, missing-evidence codes, freshness/coverage fields, methodology-version fields, no-trading boundary, and consumer-safe labels.
- Add focused static/contract tests only if needed to prove no runtime imports, no provider/cache/runtime coupling, no public API schema exposure, and no trading/advice wording.

Suggested allowed files for that future task:

- `docs/options/options-market-structure-observation-contract.md`
- Optional focused tests that are static/contract-only and do not require source implementation.

Forbidden for that future task:

- source implementation;
- public API schema/endpoint changes;
- provider enablement, live calls, credential reads, vendor selection, provider/cache/runtime changes;
- Options Lab scoring, payoff, strategy, optimizer, no-advice, frontend behavior, broker/order, portfolio, backtest, scanner, or notification changes.

All implementation, DTO/API exposure, provider integration, cache/runtime design, frontend rendering, and decision-grade market-structure adoption remain deferred.

## Validation Plan For This Audit

Required docs-only validation:

```bash
git diff --check -- docs/codex/audits/T-1086-options-gex-market-structure-placement-readiness-audit.md
./scripts/release_secret_scan.sh
```

Expected final diff:

- `docs/codex/audits/T-1086-options-gex-market-structure-placement-readiness-audit.md`
