# DATA-011 Packet Consumption Product Acceptance

## Executive Verdict

PARTIAL

The newly landed packet/readiness work materially improves the core research path. Stock, Watchlist, Scanner, Market Overview, Liquidity Monitor, Home, and Research Radar now surface compact consumer research state instead of raw diagnostics. The app is closer to a professional research terminal, but it is not a full PASS yet: Rotation Radar still exposes provider-like ETF readiness labels, and Portfolio, Options Lab, and Scenario Lab still feel more like setup/gated workbenches than immediately useful first-viewport research surfaces.

## Surface Scores

| Surface | Score 0-2 | Verdict | Evidence | Top Fix |
| --- | ---: | --- | --- | --- |
| Home / Dashboard | 2 | Useful enough for small private beta | First-read summary shows evidence boundary, usable routes, missing evidence, and next paths without raw `INSUFFICIENT` / provider / debug text (`apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx:2348`). | Keep improving default data density, but no DATA-011 blocker. |
| Market Overview | 2 | Useful research terminal first viewport | First viewport synthesizes "发生了什么 / 重要点 / 下一步看什么" with VIX, US10Y, BTC facts and hides source/provider internals (`apps/dsa-web/src/pages/__tests__/MarketOverviewPage.test.tsx:2655`). Official source readiness renders consumer labels (`apps/dsa-web/src/pages/__tests__/MarketOverviewPage.test.tsx:1961`). | No immediate blocker. |
| Liquidity Monitor | 2 | Useful enough and consumer-safe | Consumer band shows liquidity posture, next observations, key metrics, and hides provider/admin remediation CTAs (`apps/dsa-web/src/pages/__tests__/LiquidityMonitorPage.test.tsx:1094`). Official risk readiness is compact and hides raw provider fields (`apps/dsa-web/src/pages/__tests__/LiquidityMonitorPage.test.tsx:803`). | Keep admin details collapsed and secondary. |
| Rotation Radar | 1 | Improved but still not fully product-clean | ETF quote readiness is visible and compact, but labels include `Alpaca部分可用` and `回退观察` in the rendered readiness strip (`apps/dsa-web/src/api/marketRotation.ts:631`, `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1830`, `apps/dsa-web/src/pages/__tests__/MarketRotationRadarPage.test.tsx:1225`). | Replace provider/fallback wording with provider-neutral consumer labels such as `ETF 引用部分可用` and `备用观察样本`. |
| Scanner | 2 | Strong packet/readiness consumption | Empty/no-candidate states use `dataReadiness` labels like `数据待补`, `报价快照待补`, and next actions, while suppressing raw blocker buckets and `0ms` cards (`apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1684`, `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1727`). | No DATA-011 blocker. |
| Watchlist | 2 | Strong row-level packet consumption | Rows render `rowResearchPacket` as compact quote, scan, research, next action, and observation labels while suppressing raw missing/evidence/provider/no-advice fields (`apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx:797`, `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx:869`). | No DATA-011 blocker. |
| Stock Structure / Stock Detail | 2 | Strong symbol packet consumption | Stock requests the Symbol Research Packet and renders a compact `研究就绪快照` with family states, missing-data summary, and no trade instruction label while suppressing raw packet enum values (`apps/dsa-web/src/pages/__tests__/StockStructureDecisionPage.test.tsx:148`). | No DATA-011 blocker. |
| Research Radar | 2 | Useful research queue surface | Low-evidence and manual-gap queues render as `证据补缺`, explicit next paths, and safe prerequisite copy; raw `manual_gap`, provider/runtime/request IDs, and advice terms are suppressed (`apps/dsa-web/src/pages/__tests__/ResearchIaPages.test.tsx:893`). | No DATA-011 blocker. |
| Portfolio | 1 | Safe but first viewport remains setup-heavy | Empty portfolio state leads with account/holding setup copy and only becomes research-useful after holdings are added (`apps/dsa-web/src/pages/PortfolioPage.tsx:2639`). It is consumer-safe, but not yet a research-terminal first viewport for new users. | Add a compact research-state preview or explain what portfolio insight will be available from current holdings/account state. |
| Options Lab | 1 | Improved, but still gate/workbench-heavy | The hero renders research readiness and gate summary (`apps/dsa-web/src/pages/OptionsLabPage.tsx:1703`), and tests confirm old input/developer explanation copy is absent (`apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:2798`). However first viewport still emphasizes readiness gates, assumptions, and paused/limited data rather than immediately useful option research. | Make the first viewport lead with underlying context, observable structures, and risk boundary before gate internals. |
| Scenario Lab | 1 | Consumer-safe but not yet first-viewport useful enough | Scenario Lab has bounded scenario framing and sanitized unavailable state (`apps/dsa-web/src/pages/ScenarioLabPage.tsx:419`, `apps/dsa-web/src/pages/ScenarioLabPage.tsx:523`), but the first screen still reads as a constrained scenario workbench and can lead with unavailable/gated output. | Promote current market frame, scenario delta, and next evidence into a denser first-read summary. |

## Confirmed Improvements

- Home / Dashboard:
  - First viewport now has a single research first-read summary, a trust strip after it, and compact next-route actions to structure, Research Radar, Market Overview, and Scenario Lab.
  - Raw packet states such as `INSUFFICIENT` / `AVAILABLE`, provider/debug/schema/raw payload text, and advice terms are covered by negative assertions.

- Stock Structure / Stock Detail:
  - Stock now requests `getResearchPacket('AAPL')` and renders the packet in a compact panel with consumer labels such as `报价可用`, `历史可用`, `结构待补`, and `基本面待接入`.
  - The page keeps structure facts visible even if the packet request fails.

- Watchlist:
  - Rows consume `rowResearchPacket` and show compact quote, scan, research, next-action, and observation states.
  - Backend raw evidence phrases such as `Missing evidence needs review`, `Price-history evidence`, `Scanner score evidence`, `evidence_gap`, `not_integrated`, and `noAdviceDisclosure` are guarded from visible row/queue output.

- Scanner:
  - Empty/no-run states now use `dataReadiness` to show user-facing blockers and next actions instead of zero-duration or raw blocker strings.
  - Candidate packet display and empty-state readiness are covered by no-raw and no-advice tests.

- Market Overview:
  - First viewport now provides an actual market first-read: what happened, what matters, and what to check next.
  - Official risk source readiness is consumerized as `官方风险源部分可用`, `VIX可用`, `利率待更新`, and `Fed流动性待补`.

- Liquidity Monitor:
  - Consumer view leads with liquidity posture, next observation, and key metrics.
  - Official source readiness is visible without provider/runtime/credential fields, and admin/technical details remain hidden by default.

- Research Radar:
  - Manual gaps are rendered as `证据补缺`.
  - API errors and unified-queue failures remain visible as stable product states without provider/runtime/request/raw leakage.

## Remaining Product Blockers

- P0 - Rotation Radar readiness still exposes provider-like language in a consumer strip.
  - Impact: This directly violates the acceptance goal that Market/Liquidity/Rotation source readiness be visible but not raw/provider-like.
  - Evidence: `Alpaca部分可用`, `Alpaca待配置`, and `回退观察` are generated in `apps/dsa-web/src/api/marketRotation.ts:631` and rendered at `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1830`.

- P1 - Portfolio empty first viewport is still onboarding/setup-first.
  - Impact: A new user sees account setup and first-holding workflow before research value; this is safe, but not yet a research terminal feel.
  - Evidence: empty-state copy is centered on creating/selecting accounts and adding/importing first records (`apps/dsa-web/src/pages/PortfolioPage.tsx:2639`).

- P1 - Options Lab first viewport still over-indexes on readiness gates and paused/limited state.
  - Impact: The page is safer and cleaner than before, but the first viewport still feels like a gated lab rather than a concise options research terminal.
  - Evidence: hero places research readiness and readiness gate summary directly under the surface label (`apps/dsa-web/src/pages/OptionsLabPage.tsx:1715`).

- P2 - Scenario Lab can still lead with unavailable/gated output instead of an immediately useful scenario summary.
  - Impact: Useful when data exists, but low-evidence states still feel like workflow constraints.
  - Evidence: unavailable state renders inside the main scenario output card (`apps/dsa-web/src/pages/ScenarioLabPage.tsx:523`).

## Raw/Internal Leakage Findings

| Surface | File | Phrase | Visible? | Severity | Suggested fix |
| --- | --- | --- | --- | --- | --- |
| Rotation Radar | `apps/dsa-web/src/api/marketRotation.ts:631` -> `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1830` | `Alpaca部分可用`, `Alpaca待配置` | Yes | P0 | Use provider-neutral labels: `ETF 引用部分可用`, `ETF 引用待补`; move provider name to admin diagnostics. |
| Rotation Radar | `apps/dsa-web/src/api/marketRotation.ts:640` -> `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx:1840` | `回退观察` | Yes | P1 | Replace fallback-like language with consumer wording such as `备用样本观察` or `引用样本有限`. |
| Options Lab | `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx:2798` | `先设定...`, `这里仅记录...`, `不直接形成执行结论` | No; negative source assertion only | None | No product fix needed for DATA-011; keep the guard. |
| Watchlist / Research Radar fixtures | `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx:827`, `apps/dsa-web/src/api/__tests__/researchRadar.test.ts:76` | `Missing evidence needs review`, `Price-history evidence`, `Scanner score evidence`, `evidence_gap` | No; fixture/negative assertion coverage | None | No product fix needed; keep regression guards. |
| API normalizers/types | `apps/dsa-web/src/api/**` | `available`, `missing`, `blocked`, `provider`, `runtime`, `credential`, `sourceAuthority`, `fallbackUsed` | Mostly not directly visible; API model/admin support fields | None for consumer surfaces | Keep API fields internal; continue page-level negative guards. |

## First-Viewport Problems

- Rotation Radar: readiness is visible, but provider-like `Alpaca...` labels make the first viewport feel partly operational rather than product-native.
- Portfolio: empty/new-account state remains setup-first and does not yet give immediate research state or data value.
- Options Lab: first viewport still foregrounds readiness gates and paused/limited data state; useful research artifacts exist lower in the page but the opening read is not strong enough.
- Scenario Lab: bounded and safe, but can still open into unavailable/gated scenario output rather than a concise scenario readout.

## Recommended Next Tasks

- DATA-012 - Rotation Radar Provider-Neutral Readiness Copy
  - Replace `Alpaca...` and fallback-like labels in the consumer strip with provider-neutral ETF quote readiness labels; keep provider/source authority only in admin diagnostics.

- DATA-013 - Portfolio First-Viewport Research State Preview
  - Add a compact first-read panel for portfolio research state: current holdings/account readiness, what can be evaluated now, what is missing, and the next useful action.

- DATA-014 - Options Lab First-Read Research Terminal Pass
  - Reorder the opening viewport so underlying context, observable structures, risk boundary, and next evidence come before gate detail.

- DATA-015 - Scenario Lab First-Read Summary Upgrade
  - Promote current market frame, scenario delta, confidence boundary, and next evidence into the first viewport; keep unavailable state secondary.

- DATA-016 - Cross-Surface Consumer Leakage Guard Consolidation
  - Add a focused shared guard list for product-visible first-viewport raw/provider/advice terms across the audited surfaces, excluding admin/settings by design.

## Validation Commands Run

- `npm --prefix apps/dsa-web run typecheck`
  - Initial outcome: failed before dependency setup with `sh: tsc: command not found`.
  - Environment prep: `npm --prefix apps/dsa-web ci` completed successfully and installed local frontend dependencies. NPM reported 16 existing audit findings; no product code was changed.
  - Final outcome: passed, exit 0.

- `npm --prefix apps/dsa-web run test -- src/pages/**tests**/StockStructureDecisionPage.test.tsx src/pages/**tests**/WatchlistPage.test.tsx src/pages/**tests**/UserScannerPage.test.tsx src/pages/**tests**/MarketOverviewPage.test.tsx src/pages/**tests**/LiquidityMonitorPage.test.tsx src/pages/**tests**/MarketRotationRadarPage.test.tsx`
  - Outcome: failed with `No test files found` because the literal `**tests**` filter does not match actual `__tests__` paths in this bash/Vitest invocation.

- `rg --files apps/dsa-web/src/pages | rg '__tests__/(StockStructureDecisionPage|WatchlistPage|UserScannerPage|MarketOverviewPage|LiquidityMonitorPage|MarketRotationRadarPage)\.test\.tsx$'`
  - Outcome: found the six concrete test files under `apps/dsa-web/src/pages/__tests__/`.

- `npm --prefix apps/dsa-web run test -- src/pages/__tests__/StockStructureDecisionPage.test.tsx src/pages/__tests__/WatchlistPage.test.tsx src/pages/__tests__/UserScannerPage.test.tsx src/pages/__tests__/MarketOverviewPage.test.tsx src/pages/__tests__/LiquidityMonitorPage.test.tsx src/pages/__tests__/MarketRotationRadarPage.test.tsx`
  - Outcome: passed, exit 0. Vitest reported 6 files passed and 303 tests passed.

- `rg -n --pcre2 -i 'available|missing|not_integrated|insufficient|blocked|observationOnly|noAdviceDisclosure|sourceAuthority|providerConfigured|fallbackUsed|scoreContributionAllowed|provider|runtime|credential|Missing evidence needs review|Price-history evidence|Scanner score evidence|evidence_gap|0ms|not personalized financial advice|not an instruction|financial advice|先设定|这里仅记录|不直接形成执行结论' apps/dsa-web/src/pages apps/dsa-web/src/components apps/dsa-web/src/api`
  - Outcome: exit 0 with many expected matches across API models, admin/settings code, fixtures, and negative assertions. Product-visible findings from the audited consumer surfaces are listed above.

- `rg -n --pcre2 -i 'Alpaca部分可用|回退观察|Missing evidence needs review|Price-history evidence|Scanner score evidence|evidence_gap|0ms|not personalized financial advice|not an instruction|financial advice|先设定|这里仅记录|不直接形成执行结论' apps/dsa-web/src/pages apps/dsa-web/src/components apps/dsa-web/src/api`
  - Outcome: exit 0. Confirmed `Alpaca部分可用` / `回退观察` as visible Rotation labels; confirmed several raw phrases are only fixtures or negative assertions.
