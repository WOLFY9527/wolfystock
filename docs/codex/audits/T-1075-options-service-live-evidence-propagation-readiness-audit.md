# T-1075 Options Service Live-Evidence Propagation Readiness Audit

Task ID: T-1075-AUDIT

Task title: Options service live-evidence propagation readiness audit

Mode: READ-ONLY-AUDIT docs-only artifact.

Allowed artifact:

`docs/codex/audits/T-1075-options-service-live-evidence-propagation-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1075-options-service-live-evidence-readiness-audit`
- branch: `codex/t1075-options-service-live-evidence-readiness-audit`
- base commit inspected: `f514728e`

Scope boundary:

- This audit inspected repository-local Options Lab service propagation readiness only.
- No source, tests, config, package, lockfile, provider/cache/runtime/API/frontend behavior, provider enablement, network calls, credential reads, options scoring/payoff/strategy/optimizer/no-advice behavior, market-structure/GEX/gamma flip/call wall/put wall implementation, broker/order, portfolio, backtest, or scanner behavior was changed.
- Current Options market-structure/GEX adoption remains deferred.

## Executive Verdict

Ready for one bounded future service-propagation write, with strict caveats.

`OptionsLabService.evaluate_decision()` is now ready to build and pass provider live evidence from existing provider snapshots because the gate layer already exposes `build_options_provider_live_evidence_from_snapshot()` and already requires missing live evidence only when an otherwise decision-grade path has no provider-authority blocker (`src/services/options_data_quality_gates.py:787`, `src/services/options_data_quality_gates.py:1385`). The service also already receives the full normalized snapshot before decision evaluation and currently passes provider authority through the same gate seam (`src/services/options_lab_service.py:440`, `src/services/options_lab_service.py:465`).

The safe write is not market-structure adoption and not provider enablement. It is only service-level propagation of a fail-closed live-evidence contract into the existing gate call. The write must preserve the current observation-only posture for `synthetic_fixture`, fixtures, dry-run, stubs, adapter-contract payloads, and current provider IDs (`tradier`, `ibkr`, `polygon`).

## Existing Snapshot Fields That Can Populate Live Evidence

The existing normalized snapshots have enough fields to populate the non-authority portions of provider live evidence without provider/runtime/API/frontend schema changes:

- Provider identity and type: `providerName`, `providerCapabilities.providerName`, `source`, and the helper's fixed `providerKind=market_data` (`src/services/options_data_quality_gates.py:820`).
- Source class and provider flags: `providerCapabilities.sourceType`, `providerCapabilities.fixtureOnly`, `providerCapabilities.liveEnabled`, `providerCapabilities.tradeableData`, plus `dataQuality.tradeable` fallback (`src/services/options_data_quality_gates.py:797`, `src/services/options_data_quality_gates.py:829`).
- Fail-closed source markers: provider id, `source`, `providerQuality`, `providerCapabilities.notes`, `dataQuality.hints`, and freshness/source text can safely identify fixture, synthetic, dry-run, stub, or adapter-contract evidence (`src/services/options_data_quality_gates.py:811`, `src/services/options_data_quality_gates.py:629`).
- Quote freshness and timestamp: `underlying.freshness`, `underlying.asOf`, or `chainAsOf` (`src/services/options_data_quality_gates.py:837`).
- Chain freshness and timestamp: `chainFreshness`, snapshot `freshness`, first contract `freshness`, `underlying.freshness`, `chainAsOf`, or first contract `asOf` (`src/services/options_data_quality_gates.py:839`).
- Expiration coverage: `expirations[].date` and `contracts[].expiration` (`src/services/options_data_quality_gates.py:845`).
- Market-field coverage: bid/ask, open interest, volume, IV, and complete Greeks from `contracts[]` (`src/services/options_data_quality_gates.py:846`).
- Provider self-claims: `providerDecisionAuthority` and `recommendationAuthority` can be passed as claims only; the live-evidence contract already turns them into ignored self-claim reason codes instead of authority (`src/services/options_data_quality_gates.py:861`, `src/services/options_data_quality_gates.py:637`).
- Optional operator fields: `providerSlaStatus` and `sandboxOrProduction` can be copied if present, otherwise left as `unknown`/`None` (`src/services/options_data_quality_gates.py:854`).

The provider layer already decorates fixture snapshots with `providerName`, `providerQuality`, `dataQuality`, `providerCapabilities`, underlying freshness, expiration freshness, and per-contract source/freshness/data-quality fields (`src/services/options_market_data_provider.py:492`). Tradier dry-run and adapter-contract snapshots also project the same top-level shape (`src/services/options_market_data_provider.py:1029`, `src/services/options_market_data_provider.py:882`).

## Missing Or Ambiguous Required Fields

These fields must stay missing or explicitly blocked in the future write; the service must not infer authority from adjacent fields:

- `ivRankAuthority`: current service IV-rank evidence is computed from `historicalIvProxy`, and the current source is `synthetic_fixture_proxy` (`src/services/options_lab_service.py:880`). `iv_rank_status=available` is not authority. The future write should pass `None` unless a separately authorized source adds explicit authority.
- `eventCalendarAuthority`: `eventCalendar` presence can satisfy the existing event-calendar data gate, but it does not prove authorized event-calendar source authority. When `requiresEventCalendar` is true, the future write should pass `None` unless explicit authority metadata exists.
- Provider SLA authority: `providerSlaStatus` exists as an optional field in the live-evidence contract, but current snapshots generally do not provide authoritative SLA status. Defaulting to `unknown` is safe and fail-closed.
- Sandbox/production environment: `sandboxOrProduction` is optional and should not be invented. If absent, leave it absent.
- Freshness authority: `fresh`, `live`, or `realtime` strings can satisfy the live-evidence freshness check only if they already exist in the snapshot. The service must not convert stale/cached/delayed timestamps into fresh evidence. Existing `_source_type()` is deliberately conservative and classifies stale/cached/delayed as delayed before live (`src/services/options_lab_service.py:780`).

## Effect On Current Observation-Only Outcomes

Passing live evidence should not promote any current observation-only provider to decision grade.

Reasons:

- Provider authority remains a separate blocker. The internal policy keeps fixture, synthetic, dry-run, stub, adapter-contract, `tradier`, `ibkr`, and `polygon` below decision grade (`src/services/options_data_quality_gates.py:89`, `src/services/options_data_quality_gates.py:351`).
- Current provider authority issues disable the missing-live-evidence requirement branch because the gate only makes live evidence required when the base path is decision-grade and there are no provider-authority issues (`src/services/options_data_quality_gates.py:1385`).
- If live evidence is passed for current providers, it will add fail-closed `live_evidence_*` diagnostics, but it will not make `decisionGrade` true or change the observation/no-trade outcome class.

The expected observable change is diagnostic, not authority: `failClosedReasonCodes`, `gateIssues`, and derived `optionsReadiness.blockingReasons` may include additional `live_evidence_*` codes because the API response already exposes gate issues and fail-closed reason codes (`api/v1/endpoints/options.py:440`, `api/v1/schemas/options.py:1298`). That is acceptable only if the future write updates focused tests and does not change API schema, frontend rendering, or no-advice copy.

## Test Readiness

Current tests are close, but not sufficient by themselves to prove service propagation.

Already covered:

- Complete Tradier-shaped live evidence cannot override the internal observation-only policy for current provider IDs (`tests/test_options_data_quality_gates.py:104`).
- Missing freshness, missing coverage, missing IV-rank authority, and missing event-calendar authority produce live-evidence reason codes (`tests/test_options_data_quality_gates.py:129`).
- Fixture, dry-run, stub, adapter-contract, and synthetic live-evidence flags all fail closed (`tests/test_options_data_quality_gates.py:153`).
- Missing live evidence fails closed for an otherwise clean decision-grade authority path (`tests/test_options_data_quality_gates.py:240`).
- Current provider IDs remain observation-only, and because provider-authority blockers exist, they do not additionally require missing live evidence (`tests/test_options_data_quality_gates.py:337`).
- Service-level synthetic fixture, delayed fixture, Tradier dry-run, and adapter-contract paths remain non-decision-grade and do not emit `有条件可交易` (`tests/test_options_lab_service.py:682`, `tests/test_options_market_data_provider.py:309`, `tests/test_options_market_data_provider.py:905`).

Still needed for the future write:

- A service-level synthetic fixture assertion that live-evidence propagation adds fail-closed `live_evidence_*` diagnostics while keeping `decision_grade=False`, `decision_label=数据不足，禁止判断`, and no preferred strategy.
- A Tradier dry-run or adapter-contract service assertion that the propagated evidence includes dry-run or adapter-contract live-evidence blockers and no network request beyond the already mocked/injected transport path.
- An optimizer/ranked-alternative assertion proving the `_optimizer_candidate()` gate seam also receives equivalent live evidence and cannot promote alternatives.
- If existing API tests become stricter because `failClosedReasonCodes` gains new values, update only the focused Options API tests to assert the new diagnostics and unchanged schema/outcome.

## Protected-Domain Warnings

The future write is near protected Options and provider domains. It must not change:

- provider global order, live-call paths, credential loading, first-good-wins fallback, cache/SWR/TTL semantics, MarketCache behavior, or fallback/mock/synthetic not-live semantics;
- Options Lab scoring, gates policy, payoff math, strategy optimizer semantics, recommendation/no-advice policy, API response shape, or stored contract versions;
- API endpoints, frontend rendering, broker/order paths, portfolio mutation, backtest, scanner, GEX, gamma flip, call wall, or put wall behavior.

The only acceptable semantic delta is that existing service gate diagnostics receive a provider live-evidence mapping derived from the already-normalized snapshot, causing additional fail-closed reason codes where appropriate.

## One Bounded Future Write

Recommendation: proceed with one service-propagation write.

Allowed files:

- `src/services/options_lab_service.py`
- `tests/test_options_lab_service.py`
- `tests/test_options_market_data_provider.py`
- `tests/api/test_options_lab.py` only if focused API response assertions need updated diagnostics while preserving schema and outcome

Implementation constraints:

- Import and use the existing `build_options_provider_live_evidence_from_snapshot()` helper; do not add a parallel live-evidence builder.
- Build evidence from the existing normalized snapshot already returned by `_fixture_for_symbol()`.
- Pass evidence into both `evaluate_options_data_quality_gates()` calls in `evaluate_decision()` and `_optimizer_candidate()`.
- Pass `iv_rank_authority=None` and `event_calendar_authority=None` unless explicit authority fields already exist in the same snapshot; do not infer authority from `iv_rank_status`, `eventCalendar`, provider name, `liveEnabled`, `tradeableData`, or provider self-claims.
- Preserve existing decision labels, no-advice disclosure, trade-quality caps, ranked alternative no-trade behavior, and current provider observation-only authority.

Forbidden files/domains:

- `src/services/options_data_quality_gates.py`
- `src/services/options_market_data_provider.py`
- `api/v1/schemas/options.py`
- `api/v1/endpoints/options.py`
- `apps/dsa-web/**`
- `data_provider/**`
- `src/services/market_cache.py` and other cache/provider runtime files
- `.env.example`, config, package, lockfile, CI, broker/order, portfolio, backtest, scanner, scoring/payoff/strategy math, GEX/gamma flip/call wall/put wall implementation

Validation plan for the future write:

```bash
python -m pytest tests/test_options_lab_service.py tests/test_options_market_data_provider.py tests/api/test_options_lab.py -q -k "options and (decision or provider or live_evidence or tradier or fixture)"
python -m py_compile src/services/options_lab_service.py
git diff --check -- src/services/options_lab_service.py tests/test_options_lab_service.py tests/test_options_market_data_provider.py tests/api/test_options_lab.py
bash scripts/release_secret_scan.sh
```

If API focused tests do not need updates, omit `tests/api/test_options_lab.py` from the write and from the `git diff --check` file list.

## Defer Items

Defer all of the following:

- live provider enablement or credential-backed provider calls;
- provider/runtime/cache/API schema/frontend changes;
- source-authority upgrades for IV rank, event calendar, or provider SLA;
- Options market-structure/GEX/gamma flip/call wall/put wall adoption;
- broker/order/portfolio/backtest/scanner integrations;
- any stronger-than-observation decision-grade promotion for current provider IDs.
