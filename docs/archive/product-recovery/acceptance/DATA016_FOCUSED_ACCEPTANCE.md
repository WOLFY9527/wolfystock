# DATA-016 Focused Acceptance After First-Read Recovery

## Executive Verdict

PASS

DATA-012 through DATA-015 are product-acceptable for this focused first-read acceptance scope. Source and focused test review show the four reviewed surfaces now lead with consumer-readable first-viewport research state, keep unavailable/gated states compact or secondary, and preserve no-advice/raw-diagnostic boundaries.

This was source/test review, not live browser review.

## Scope

This acceptance covers only:

- Rotation Radar
- Portfolio
- Options Lab
- Scenario Lab

It does not cover full-site UX, live provider behavior, backend data quality, browser screenshots, Playwright smoke, or new product implementation.

## Surface Scores

| Surface | Score 0-2 | Verdict | Evidence | Remaining Fix |
| --- | ---: | --- | --- | --- |
| Rotation Radar | 2 | PASS | ETF readiness now maps to `ETF引用可用`, `ETF引用部分可用`, `ETF引用待补`, and `备用样本观察` in `apps/dsa-web/src/api/marketRotation.ts:631`; the visible strip renders only that view model in `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1830`; the focused test asserts old Alpaca/fallback labels are absent in `apps/dsa-web/src/pages/__tests__/MarketRotationRadarPage.test.tsx:1200`. | None in this focused scope. |
| Portfolio | 2 | PASS | First viewport now includes `portfolio-research-state-preview` covering account, holdings, valuation, FX, risk, and next action in `apps/dsa-web/src/pages/PortfolioPage.tsx:2887`; empty-state layout places the preview next to onboarding before ledger sections in `apps/dsa-web/src/pages/PortfolioPage.tsx:3426`; tests assert no sample portfolio preview and preserved ledger controls in `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx:766`. | None in this focused scope. |
| Options Lab | 2 | PASS | First viewport leads with `期权研究首读`, current underlying, structure chips, risk boundary, and next evidence in `apps/dsa-web/src/pages/OptionsLabPage.tsx:1723`; focused tests assert the hero order and absence of old gate/developer dominance in `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:676` and `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:1235`. | None in this focused scope. |
| Scenario Lab | 2 | PASS | First viewport renders `情景摘要` with current frame, selected scenario, driver shifts, evidence boundary, and next evidence in `apps/dsa-web/src/pages/ScenarioLabPage.tsx:459`; unavailable output is rendered later as compact secondary state in `apps/dsa-web/src/pages/ScenarioLabPage.tsx:587`; tests assert ordering and raw/advice suppression in `apps/dsa-web/src/pages/__tests__/ScenarioLabPage.test.tsx:158`. | None in this focused scope. |

## Acceptance Findings

### Rotation Radar

- PASS: The consumer readiness strip is provider-neutral. `normalizeAlpacaQuoteAuthorityReadiness` now emits ETF reference labels instead of Alpaca-labeled statuses: `ETF引用可用`, `ETF引用部分可用`, `ETF引用待补`, and `来源待确认` (`apps/dsa-web/src/api/marketRotation.ts:631`).
- PASS: Limited/fallback state remains visible in consumer-safe wording through `备用样本观察` and `仅观察` (`apps/dsa-web/src/api/marketRotation.ts:640`).
- PASS: The visible production path renders the normalized label/detail/chips only (`apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1830`).
- PASS: Old visible labels are guarded absent: `Alpaca部分可用`, `Alpaca待配置`, `Alpaca可用`, `Alpaca未配置`, and `回退观察` (`apps/dsa-web/src/pages/__tests__/MarketRotationRadarPage.test.tsx:1230`).
- Source-review note: runtime code still contains internal API field names such as `sourceAuthority` and `fallbackUsed` as data-model fields, but the reviewed consumer strip maps them before rendering.

### Portfolio

- PASS: The first viewport now includes a research-state preview before or next to the setup/empty workflow (`apps/dsa-web/src/pages/PortfolioPage.tsx:2963`, `apps/dsa-web/src/pages/PortfolioPage.tsx:3518`).
- PASS: The preview covers account readiness, holdings readiness, valuation readiness, FX readiness, risk readiness, and next action (`apps/dsa-web/src/pages/PortfolioPage.tsx:2887`).
- PASS: It avoids fake/sample portfolio output. The onboarding copy explicitly says no sample holdings or sample performance are generated before real data is saved (`apps/dsa-web/src/pages/PortfolioPage.tsx:3467`, `apps/dsa-web/src/pages/PortfolioPage.tsx:3479`).
- PASS: Ledger actions are preserved as account/ledger controls, not advice. The focused test keeps `持仓流水` visible, rejects trade-workbench/advice-like controls, and still verifies the ledger submit button (`apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx:798`).

### Options Lab

- PASS: The first viewport leads with `期权研究首读`, current underlying context, observable structure chips, compact readiness chips, risk boundary, and next evidence (`apps/dsa-web/src/pages/OptionsLabPage.tsx:1731`, `apps/dsa-web/src/pages/OptionsLabPage.tsx:1748`, `apps/dsa-web/src/pages/OptionsLabPage.tsx:1781`).
- PASS: Long gate/disclaimer paragraphs are no longer dominant in the hero. The focused test asserts the hero no longer contains `研究就绪度`, `门控摘要`, `当前状态：`, or the old paused-data line (`apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:691`).
- PASS: Old developer phrases are absent from the product source guard list, including `先设定...`, `这里仅记录...`, and `不直接形成执行结论` (`apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:2798`).
- PASS: Developer detail panels remain absent in the consumer DOM, and raw provider/debug markers are guarded (`apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:2424`).

### Scenario Lab

- PASS: The first viewport leads with `情景摘要` (`apps/dsa-web/src/pages/ScenarioLabPage.tsx:459`).
- PASS: It includes current frame, selected scenario, driver shifts, evidence boundary, and next evidence (`apps/dsa-web/src/pages/ScenarioLabPage.tsx:467`, `apps/dsa-web/src/pages/ScenarioLabPage.tsx:476`, `apps/dsa-web/src/pages/ScenarioLabPage.tsx:483`, `apps/dsa-web/src/pages/ScenarioLabPage.tsx:489`, `apps/dsa-web/src/pages/ScenarioLabPage.tsx:500`).
- PASS: Unavailable/gated output is secondary and compact, after the first-read summary (`apps/dsa-web/src/pages/ScenarioLabPage.tsx:587`).
- PASS: The focused test asserts the first-read summary appears before the secondary unavailable state and suppresses raw/advice terms (`apps/dsa-web/src/pages/__tests__/ScenarioLabPage.test.tsx:204`, `apps/dsa-web/src/pages/__tests__/ScenarioLabPage.test.tsx:214`, `apps/dsa-web/src/pages/__tests__/ScenarioLabPage.test.tsx:222`).

### Cross-surface raw/advice leakage

- PASS: Focused tests cover raw provider/runtime/credential/debug/sourceAuthority/fallback leakage across the reviewed surfaces:
  - Rotation strip negative assertions: `apps/dsa-web/src/pages/__tests__/MarketRotationRadarPage.test.tsx:1230`
  - Portfolio first-read negative assertions: `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx:994`
  - Options hero/developer-detail negative assertions: `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:1235`, `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:2424`
  - Scenario visible-text negative assertions: `apps/dsa-web/src/pages/__tests__/ScenarioLabPage.test.tsx:222`
- PASS: No visible trading-advice wording was found in the reviewed first-viewport acceptance paths. Portfolio ledger terms such as holdings / buy / sell / 持仓 / 买入 / 卖出 remain allowed only in ledger/account controls; the first-read preview and consumer summaries guard them from advice contexts.
- Source-review note: raw/internal terms appear in test fixtures, negative assertions, TypeScript DTO fields, and sanitizers. These are allowed internal/test uses, not reviewed consumer first-viewport copy.

## Confirmed Improvements

- DATA-012: Rotation Radar replaced provider-labeled ETF readiness with provider-neutral consumer labels and retained limited/fallback source as `备用样本观察`.
- DATA-013: Portfolio added a first-viewport research-state preview that explains account, holdings, valuation, FX, risk view, and next action before relying on setup/ledger flow.
- DATA-014: Options Lab now opens with a compact first-read terminal focused on underlying context, observable structure, risk boundary, and next evidence instead of long gate/disclaimer copy.
- DATA-015: Scenario Lab now opens with `情景摘要` and moves unavailable/gated output into a secondary compact block.

## Remaining Blockers

None for this focused DATA-016 acceptance scope.

## Recommended Next Tasks

Because this focused acceptance is PASS, move from first-viewport cleanup to real data/product-value tasks:

- Activate real ETF/index quote coverage and persisted quote windows for Rotation Radar and Market Overview, keeping provider diagnostics out of consumer first-read copy.
- Advance Portfolio product value through authoritative price lineage, FX freshness, benchmark/factor mapping, and stored daily portfolio snapshots.
- Start an Options Lab data-readiness task for authorized chain, IV, OI, volume, Greeks, and methodology evidence before expanding decision surfaces.
- Connect Scenario Lab outputs to stronger stored baseline market/portfolio snapshots so scenarios can graduate from bounded summaries to useful comparative research.

## Validation Commands Run

- `npm --prefix apps/dsa-web run typecheck`
  - Initial result: FAIL, `tsc: command not found` because the worktree had no `apps/dsa-web/node_modules`.
  - Environment setup: created ignored local symlink `apps/dsa-web/node_modules -> /Users/yehengli/daily_stock_analysis/apps/dsa-web/node_modules` per the frontend worktree dependency rule.
  - Final post-rebase result: PASS, exit 0.

- `npm --prefix apps/dsa-web run test -- src/pages/**tests**/MarketRotationRadarPage.test.tsx`
  - Result: FAIL, no tests collected. Vitest did not match the literal `**tests**` filter to `src/pages/__tests__/MarketRotationRadarPage.test.tsx`.
  - Concrete equivalent run: `npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketRotationRadarPage.test.tsx` -> PASS, 1 file passed, 22 tests passed.

- `npm --prefix apps/dsa-web run test -- src/pages/**tests**/PortfolioPage.test.tsx`
  - Result: FAIL, no tests collected. Vitest did not match the literal `**tests**` filter to `src/pages/__tests__/PortfolioPage.test.tsx`.
  - Concrete equivalent run: `npm --prefix apps/dsa-web run test -- src/pages/__tests__/PortfolioPage.test.tsx` -> PASS, 1 file passed, 70 tests passed.

- `npm --prefix apps/dsa-web run test -- src/pages/**tests**/OptionsLabPage.test.tsx`
  - Result: FAIL, no tests collected. Vitest did not match the literal `**tests**` filter to `src/pages/__tests__/OptionsLabPage.test.tsx`.
  - Concrete equivalent run: `npm --prefix apps/dsa-web run test -- src/pages/__tests__/OptionsLabPage.test.tsx` -> PASS, 1 file passed, 44 tests passed.

- `npm --prefix apps/dsa-web run test -- src/pages/**tests**/ScenarioLabPage.test.tsx`
  - Result: FAIL, no tests collected. Vitest did not match the literal `**tests**` filter to `src/pages/__tests__/ScenarioLabPage.test.tsx`.
  - Concrete equivalent run: `npm --prefix apps/dsa-web run test -- src/pages/__tests__/ScenarioLabPage.test.tsx` -> PASS, 1 file passed, 2 tests passed.

- Final post-rebase concrete focused suite:
  - `npm --prefix apps/dsa-web run test -- src/pages/__tests__/MarketRotationRadarPage.test.tsx src/pages/__tests__/PortfolioPage.test.tsx src/pages/__tests__/OptionsLabPage.test.tsx src/pages/__tests__/ScenarioLabPage.test.tsx`
  - Result: PASS, 4 files passed, 138 tests passed.

- `git diff --check origin/main...HEAD`
  - Result: PASS, exit 0.

- `git diff --check`
  - Result: PASS, exit 0.

- `bash scripts/release_secret_scan.sh --base-ref origin/main`
  - Result: PASS, exit 0. No high-confidence secret patterns found in changed text files.

- Optional `npm --prefix apps/dsa-web run lint:changed`
  - Result: PASS/SKIP, exit 0. `no changed files matched the requested validation scope`.
