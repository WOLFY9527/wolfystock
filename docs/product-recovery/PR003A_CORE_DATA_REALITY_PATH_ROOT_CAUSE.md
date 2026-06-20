# PR-003A Core Data Reality Path Root-Cause Map

Task ID: PR-003A
Scope: read-only code/runtime investigation; this document is the only write.
Core path: Market Overview -> Scanner -> Watchlist / Stock page.

## 1. Executive Summary

WolfyStock's core research path is wired, but it does not currently produce useful consumer output because each step stops at a different boundary:

- Market Overview can fetch many facts, but most score-grade synthesis correctly fails closed when the inputs are unofficial, cached, fallback, stale, partial, or unavailable. The product then leads with neutral/pending/insufficient language instead of a compact set of usable facts plus next research steps.
- Scanner is a real backend job, not only a frontend placeholder, but candidate generation depends on universe, quote/history availability, profile filters, and source-confidence gates. Empty runs are persisted as real terminal states. The frontend can still make that state look like a pseudo-result, including `0ms` duration and demo-preview content.
- Watchlist loads saved user symbols, but the saved-symbol row contract is scanner/backtest lineage first. It does not enrich each row with first-class quote price, price timestamp, price freshness, or a minimum research packet.
- The canonical stock page is `StockStructureDecisionPage` at `/stocks/:stockCode/structure-decision`. It is an observation-only structure panel from daily OHLCV, not a full stock research packet. Quote, history, evidence, and structure endpoints exist separately, but the page only assembles structure-decision data.
- Liquidity Monitor and Rotation Radar are not missing frontend routes. They are public market routes with legacy redirects. If they are broken in UAT, PR-004 should quarantine them as broken/degraded surfaces, not as route-registration fixes.

Highest-value next implementation: PR-003B should repair Scanner's reality path first, because Scanner is the bridge from market context to saved symbols. Without real candidates or one honest unavailable state, Watchlist and Stock pages have no durable queue to work from.

## 2. Core Path Verdict

The path is structurally present but operationally fragmented:

1. Market Overview builds market facts and guarded synthesis through `api/v1/endpoints/market.py`, `api/v1/endpoints/market_overview.py`, `src/services/market_overview_service.py`, `apps/dsa-web/src/api/market.ts`, `apps/dsa-web/src/api/marketOverview.ts`, and `apps/dsa-web/src/pages/MarketOverviewPage.tsx`.
2. Scanner runs through `POST /api/v1/scanner/run` and `MarketScannerOperationsService.run_manual_scan`, then `MarketScannerService.run_scan`; the frontend entry is `/scanner` -> `ScannerSurfacePage` -> `UserScannerPage`.
3. Watchlist reads `GET /api/v1/watchlist/items` and the read-only overlay `GET /api/v1/watchlist/research-overlay`; the frontend page is `/watchlist` -> `WatchlistPage`.
4. Stock detail reads `/api/v1/stocks/{stock_code}/structure-decision` from `/stocks/:stockCode/structure-decision`; quote/history/evidence are separate endpoints but not assembled into one consumer packet on that page.

The main blocker is not a single missing route. It is that data-source gates are doing the right safety thing, while product projection has not yet provided a minimum useful fallback: facts that are known, facts that are missing, and the next small research step.

## 3. Market Overview Reality Map

### Feed Chain

- API routes:
  - `api/v1/endpoints/market_overview.py:30` exposes `/indices`, `/volatility`, `/sentiment`, `/funds-flow`, and `/macro`.
  - `api/v1/endpoints/market.py:72` through `api/v1/endpoints/market.py:258` exposes market cluster endpoints including `/crypto`, `/cn-indices`, `/cn-breadth`, `/cn-flows`, `/sector-rotation`, `/rotation-radar`, `/us-breadth`, `/rates`, `/fx-commodities`, `/temperature`, `/decision-cockpit`, `/daily-intelligence`, `/market-briefing`, and `/futures`.
  - The router registers `/api/v1/market-overview` and `/api/v1/market` in `api/v1/router.py:209` and `api/v1/router.py:215`.
- Service:
  - `src/services/market_overview_service.py:1136` exposes the panel methods used by `market_overview.py`.
  - `src/services/market_overview_service.py:3522` reads through `MarketCache.get_or_refresh`, rejects fallback-only/no-usable payloads, and may return memory, persistent, fallback, or background-refresh states.
- Frontend API/hooks/components:
  - `apps/dsa-web/src/api/marketOverview.ts:23` defines the panel shape, including source-confidence and observation fields.
  - `apps/dsa-web/src/api/marketOverview.ts:134` maps the `/api/v1/market-overview/*` endpoints.
  - `apps/dsa-web/src/api/market.ts:9` normalizes market panel source labels and panel consumer copy.
  - `apps/dsa-web/src/pages/MarketOverviewPage.tsx:57` loads primary panels and `apps/dsa-web/src/pages/MarketOverviewPage.tsx:70` stages secondary panels.
  - `apps/dsa-web/src/pages/MarketOverviewPage.tsx:760` catches panel failures and preserves existing/fallback panel state.

### Facts Available Today

Available as code paths, subject to local/provider/cache state:

- Index/quote-style facts through market overview panels and market endpoints.
- Crypto, sentiment, CN indices, CN breadth, CN flows, US breadth, rates, FX/commodities, futures, market temperature, and market briefing panels.
- Official VIX overlay when FRED `VIXCLS` cache/data is available: `src/services/market_overview_service.py:5632`.
- Quote-derived ETF flow proxy for QQQ/IWM style flow observations: `src/services/market_overview_service.py:5980`.
- Persistent/fallback snapshots through the cache wrapper when fresh provider output is unavailable.

### Facts Missing Or Not Score-Eligible

- Official score-grade coverage for many US index/ETF/sector quote paths is not consistently available.
- Real funds-flow inputs are missing; quote-derived ETF flow is explicitly unofficial and observation-only.
- Liquidity and rotation source families often do not meet full source-authority and freshness requirements.
- Macro/rates/official inputs may exist as cached/local snapshots, but stale/cached/fallback status caps synthesis.

### Where Facts Are Lost

- Backend synthesis: useful facts are often present, but `src/services/market_overview_service.py:4873` rejects evidence for score reliability when `scoreContributionAllowed` is false, source authority is false, freshness is cached/delayed/fallback/stale/partial/unavailable, or proxy/fallback flags are present.
- API projection: the routes generally pass panel payloads through; the largest loss is not route registration.
- Frontend projection/copy hierarchy: Market Overview loads many panels, but top-level copy often inherits the fail-closed verdict. Consumer-safe label mapping in `apps/dsa-web/src/api/market.ts:9` hides raw provider wording but does not turn facts into a useful "known facts / missing facts / next step" hierarchy.

### Why Visible Product Becomes Neutral/Pending/Insufficient

`sourceAuthorityAllowed` and `scoreContributionAllowed` gates are designed to prevent false confidence. For example, quote-derived funds flow is projected with `observationOnly=True`, `sourceAuthorityAllowed=False`, and `scoreContributionAllowed=False` in `src/services/market_overview_service.py:5980`. When these states flow into the UI, the product often shows the gate verdict instead of leading with bounded facts.

This is correct as a data boundary. The product gap is presentation: known facts are not compressed into useful consumer observations before the fail-closed state is shown.

## 4. Scanner Reality Map

### Feed Chain

- Frontend route:
  - `/scanner` is registered in `apps/dsa-web/src/App.tsx:532`.
  - `ScannerSurfacePage` gates guest/auth state and loads `UserScannerPage`.
- API:
  - `api/v1/endpoints/scanner.py:146` handles `POST /api/v1/scanner/run`.
  - `api/v1/endpoints/scanner.py:237` lists user-scoped runs.
  - `api/v1/endpoints/scanner.py:388` exposes read-only research overlay for a run.
  - `api/v1/endpoints/scanner.py:305` and related status/watchlist endpoints are admin-only.
- Backend owner:
  - `src/services/market_scanner_ops_service.py:45` owns manual scan orchestration.
  - `src/services/market_scanner_ops_service.py:155` delegates to `MarketScannerService.run_scan`.
  - `src/services/market_scanner_service.py:823` owns CN run generation.
  - `src/services/market_scanner_service.py:2124` owns US/HK quote-market scans.
- Frontend client:
  - `apps/dsa-web/src/api/scanner.ts:95` calls `POST /api/v1/scanner/run`, defaulting market to `cn`.
  - `apps/dsa-web/src/pages/UserScannerPage.tsx:2446` calls `scannerApi.run` and stores the returned run detail.

### Why Scanner Produces 0 Candidates

There are real empty states in backend code:

- `MarketScannerOperationsService._run_scan_workflow` catches known empty reasons and records a terminal `status="empty"` run with empty shortlist in `src/services/market_scanner_ops_service.py:167`.
- CN runs fail before selection when the universe is empty, no realtime snapshot exists, or the detailed evaluation stage has no valid candidates: `src/services/market_scanner_service.py:823`.
- US/HK runs can also return empty when the resolved universe is absent, history cache is empty, candidate evaluation leaves no valid rows, or profile thresholds reject everything: `src/services/market_scanner_service.py:2124`.
- CN/HK theme universes are placeholders with empty `symbols=()` in `src/core/scanner_theme_registry.py:190`; a theme run can therefore be invalid unless manually supplied.
- Source-confidence gates cap candidate projection. The public projection uses `score_grade` only when score contribution is allowed; otherwise it projects limited/insufficient states in `src/services/market_scanner_service.py:1755`.

### Why 0ms Pseudo-Results Appear

The scanner job is actually called, but the frontend duration renderer can make an immediate empty terminal run look like a `0ms` pseudo-result:

- `apps/dsa-web/src/pages/UserScannerPage.tsx:464` formats durations below one second as milliseconds.
- `apps/dsa-web/src/pages/UserScannerPage.tsx:676` uses that duration for run summaries.
- If the backend records an empty terminal run quickly, or `run_at` and `completed_at` are effectively the same, the UI can show `0ms` even though the backend workflow executed and persisted an empty result.

There is also a product projection issue:

- `apps/dsa-web/src/pages/UserScannerPage.tsx:1331` builds an empty preview panel.
- The preview explicitly says it is not live scanner output, but it is still consumer-visible in the scanner surface. This conflicts with PR-001's direction: Scanner should produce real candidates or one honest unavailable state, not demo/preview modules in the core path.

### Is Scanner Job Actually Running?

Code says yes for manual scanner runs:

- User action calls `scannerApi.run` from `UserScannerPage`.
- API calls `MarketScannerOperationsService.run_manual_scan`.
- Ops service calls `scanner_service.run_scan`.
- Empty states are persisted rather than silently mocked.

What is not equally visible to a normal user:

- Admin status endpoints are protected by scanner admin capability in `api/v1/endpoints/scanner.py:305`.
- The consumer page therefore cannot always distinguish "runtime not scheduled/configured" from "runtime ran and found no selected candidates" without relying on run detail and diagnostics.

### Minimum Honest Scanner State

If real candidates cannot be generated, Scanner should show one state with:

- market/profile/universe requested;
- input universe size;
- preselected/evaluated/selected counts;
- quote/history/freshness availability in consumer-safe labels;
- exact blocker bucket: missing universe, missing snapshot/quotes, insufficient history, scoring filters rejected all, source-quality gates capped output, or runtime unavailable;
- no demo preview, no score-grade wording, no provider/fallback/proxy details in consumer copy.

## 5. Watchlist Reality Map

### Load Chain

- `api/v1/endpoints/watchlist.py:122` handles `GET /api/v1/watchlist/items`.
- It calls `WatchlistService.list_items` at `src/services/watchlist_service.py:1061`.
- The service reads `UserWatchlistItem` rows, maps them with `_row_to_dict`, then attaches scanner/backtest/catalyst intelligence.
- Frontend `watchlistApi.listWatchlistItems` calls `/api/v1/watchlist/items` in `apps/dsa-web/src/api/watchlist.ts:216`.
- `WatchlistPage` refreshes items, refresh status, and overlay together at `apps/dsa-web/src/pages/WatchlistPage.tsx:1758`.

### Why Rows Do Not Show Useful Price/Update/Research Status

The current row contract has saved-symbol and scanner/backtest fields, not first-class quote fields:

- `WatchlistService._row_to_dict` returns `symbol`, `market`, `name`, scanner score/rank/run fields, score status fields, notes, created/updated timestamps, and intelligence: `src/services/watchlist_service.py:102`.
- The frontend type mirrors that contract in `apps/dsa-web/src/types/watchlist.ts:93`; it has no `currentPrice`, `priceChangePercent`, `priceAsOf`, `priceFreshness`, or `minimumResearchPacket` field.
- Watchlist row rendering shows symbol/name/source, score status, scanner status, backtest status, observation summary, latest intelligence time, and next action at `apps/dsa-web/src/pages/WatchlistPage.tsx:2260`.
- `getLatestIntelligenceTime` uses backtest/scanner/score/update timestamps, not quote price timestamps: `apps/dsa-web/src/pages/WatchlistPage.tsx:281`.

The issue is absence of saved-symbol enrichment, not a broken list fetch. The API successfully loads saved items, but it does not attach quote/update/research-packet status to each saved symbol.

### Overlay Boundary

The read-only overlay is intentionally evidence/status oriented:

- `api/v1/endpoints/watchlist.py:141` exposes `/research-overlay`.
- `WatchlistResearchOverlayService.build_overlay` projects existing watchlist items without mutating state: `src/services/watchlist_research_overlay_service.py:37`.
- It treats missing local OHLCV, missing scanner score evidence, stale evidence, and watchlist-only context as gaps: `src/services/watchlist_research_overlay_service.py:185`.

This overlay is useful for research priority, but it is not a substitute for row-level price/update/research packet facts.

### Minimum Actionable Watchlist Row Fields

Additive minimum fields needed for one useful row:

- `symbol`, `market`, `name`;
- `lastPrice`, `changePercent`, `priceAsOf`;
- `priceFreshnessState`: fresh/delayed/cached/unavailable;
- `researchStatus`: ready/needs_refresh/no_packet/unavailable/unsupported;
- `lastReviewedAt`;
- `primaryEvidenceSummary`: one bounded sentence from scanner/structure/history;
- `missingEvidence`: short consumer-safe labels;
- `nextResearchStep`: one action such as "open structure panel", "refresh scanner", or "verify history";
- durable links to `/stocks/:symbol/structure-decision` and source route context.

These should be derived by a backend enrichment boundary. They should not be inferred by the UI from raw scanner/backtest diagnostics.

## 6. Stock Page Reality Map

### Canonical Supported Page

The canonical stock research page currently exposed in the consumer IA is Stock Structure Decision:

- `/stocks/structure-decision` entry route: `apps/dsa-web/src/App.tsx:539`.
- `/stocks/:stockCode/structure-decision` detail route: `apps/dsa-web/src/App.tsx:540`.
- Entry page explicitly says it does not call the stock API and the primary work happens after a ticker is selected: `apps/dsa-web/src/pages/StockStructureDecisionEntryPage.tsx:58`.
- Research Radar deep-links into `/stocks/:ticker/structure-decision`: `apps/dsa-web/src/pages/ResearchRadarPage.tsx:793`.

This is not a full "stock research packet" page today.

### Backend Inputs

Relevant endpoints:

- `/api/v1/stocks/{stock_code}/validate`: `api/v1/endpoints/stocks.py:316`.
- `/api/v1/stocks/{stock_code}/evidence`: `api/v1/endpoints/stocks.py:412`.
- `/api/v1/stocks/{stock_code}/structure-decision`: `api/v1/endpoints/stocks.py:461`.
- `/api/v1/stocks/{stock_code}/quote`: `api/v1/endpoints/stocks.py:501`.
- `/api/v1/stocks/{stock_code}/history`: `api/v1/endpoints/stocks.py:649`.

Structure decision service:

- Uses `validate_consumer_symbol_precheck` and fail-closes invalid/unsupported symbols: `src/services/stock_structure_decision_service.py:116`.
- Loads 90 days of daily history via `StockService.get_history_data`: `src/services/stock_structure_decision_service.py:215`.
- Builds structure decision from OHLCV bars only: `src/services/stock_structure_decision_service.py:218`.
- Peer correlation requires local peer metadata and local recent OHLCV; otherwise it returns insufficient peer evidence: `src/services/stock_structure_decision_service.py:276`.
- Final projection always remains observation-only and not decision-grade: `src/services/stock_structure_decision_service.py:421`.

### Frontend Assembly

`StockStructureDecisionPage`:

- Parses the ticker from route/search: `apps/dsa-web/src/pages/StockStructureDecisionPage.tsx:605`.
- For a single symbol, validates the ticker, then calls only `stocksApi.getStructureDecision(primarySymbol)`: `apps/dsa-web/src/pages/StockStructureDecisionPage.tsx:640`.
- Renders data quality, component scores, structure explanation, research notes, peer correlation, and key levels: `apps/dsa-web/src/pages/StockStructureDecisionPage.tsx:780`.

The page does not call quote, history, or evidence endpoints directly. Therefore it cannot show a minimum research packet containing price, trend, valuation, event, and risk unless structure-decision response or a new packet endpoint supplies those fields.

### Missing Inputs Blocking Minimum Viable Research

- Price: quote endpoint exists, but structure page does not consume it. `StockService.get_realtime_quote` depends on `StockServiceProviderAdapter.get_quote_snapshot`; if adapter returns no quote, quote is 404/unavailable.
- Trend: structure engine can use daily OHLCV, but if history is unavailable, service returns empty data and `dataQuality.status="unavailable"` from `src/services/stock_service.py:221`.
- Valuation: no valuation fields are part of `StockStructureDecisionResponse` in `apps/dsa-web/src/api/stocks.ts:173`.
- Event/catalyst: stock evidence endpoint can expose evidence packets, but structure page does not assemble that endpoint into the canonical stock page.
- Risk: structure page has risk observations from structure rules, but not a broader stock research risk packet.
- Peer/relative context: requires verified local peer group metadata and local OHLCV; otherwise peer snapshot fail-closes as insufficient.

### Disabled Or Empty Controls

Observed controls are mostly data-contract limitations, not feature flags:

- Entry route intentionally makes no API call and waits for a selected ticker.
- Detail route can show symbol-not-found when validation says not found.
- Structure panel can show low confidence or missing evidence when daily OHLCV/peer inputs are unavailable.
- It is not currently wired to assemble quote + structure + evidence + research status into one first-screen packet.

### Smallest Implementation To Make One US And One CN Stock Honestly Researchable

Build an additive backend `minimumResearchPacket` projection for one US stock and one CN stock using existing boundaries:

- input: symbol and market;
- quote: from `StockService.get_realtime_quote`;
- trend: from `StockService.get_history_data(..., period="daily", days=90)` and structure-decision result;
- valuation/event: explicit unavailable/missing labels until a safe source exists;
- risk: structure risk observations plus evidence gaps;
- output: no advice, no target/stop/position sizing, no provider/raw diagnostics;
- frontend: Stock Structure page consumes this packet and renders facts first, then evidence gaps.

This should be additive and fail-closed. It must not relax source-confidence gates.

## 7. Route / Navigation Integrity Notes

Liquidity Monitor and Rotation Radar are not route/404 ownership bugs in current code:

- Public-safe path check includes `/market/liquidity-monitor` and `/market/rotation-radar`: `apps/dsa-web/src/App.tsx:270`.
- Legacy redirects exist:
  - `/liquidity` -> `/market/liquidity-monitor`: `apps/dsa-web/src/App.tsx:527`.
  - `/rotation` -> `/market/rotation-radar`: `apps/dsa-web/src/App.tsx:528`.
- Canonical routes are registered:
  - `/market/liquidity-monitor`: `apps/dsa-web/src/App.tsx:537`.
  - `/market/rotation-radar`: `apps/dsa-web/src/App.tsx:538`.
  - localized equivalents: `apps/dsa-web/src/App.tsx:586` and `apps/dsa-web/src/App.tsx:587`.
- Market Overview module cards link to both surfaces through `apps/dsa-web/src/components/layout/consumerAppNavigation.ts:281`.

Ownership:

- Route shell: `apps/dsa-web/src/App.tsx`.
- Navigation metadata: `apps/dsa-web/src/components/layout/consumerAppNavigation.ts` and `apps/dsa-web/src/components/layout/SidebarNav.tsx`.
- Liquidity page/API/service: `apps/dsa-web/src/pages/LiquidityMonitorPage.tsx`, `apps/dsa-web/src/api/liquidityMonitor.ts`, `api/v1/endpoints/liquidity_monitor.py`, `src/services/liquidity_impulse_synthesis_service.py`.
- Rotation page/API/service: `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx`, `apps/dsa-web/src/api/market.ts`, `api/v1/endpoints/market.py`, `src/services/market_rotation_radar_service.py`.

PR-004 should treat these as Broken Surface Quarantine candidates only if UAT still sees blank/unavailable/degraded pages. It should not spend time "fixing" route registration unless a specific stale build or localized routing issue is reproduced.

## 8. Data-Source And Gate Boundary Analysis

Correct fail-closed gates:

- Market Overview score reliability gate rejects fallback/stale/proxy/partial/unavailable evidence: `src/services/market_overview_service.py:4873`.
- Market Overview gate metadata explicitly derives `sourceAuthorityAllowed`, `scoreContributionAllowed`, `observationOnly`, and cap reasons: `src/services/market_overview_service.py:4902`.
- Scanner public projection maps score confidence to `score_grade`, `limited`, or `insufficient` instead of inflating weak inputs: `src/services/market_scanner_service.py:1755`.
- Scanner context frame classifies macro/liquidity/theme as blocked, insufficient, observe-only, supportive, or mixed: `src/services/market_scanner_service.py:3713`.
- Stock quote metadata marks fallback, missing timestamp, synthetic placeholder, or partial quote state: `src/services/stock_service.py:776`.
- Stock history returns unavailable or degraded local fallback state rather than pretending missing OHLCV is complete: `src/services/stock_service.py:221`.
- Watchlist overlay remains read-only, observation-only, and decisionGrade false: `src/services/watchlist_research_overlay_service.py:62`.

Do not relax these gates. The failure to fix is product projection and minimum packet assembly, not the guardrails.

Separate categories:

- Data missing:
  - scanner universe/snapshot/history unavailable;
  - stock quote adapter returns none;
  - daily OHLCV unavailable;
  - peer metadata absent;
  - official macro/liquidity/flow inputs absent.
- Data exists but is not surfaced usefully:
  - Market Overview has panel facts but leads with neutral/insufficient gate state.
  - Watchlist has saved symbols and scanner lineage but lacks price/research packet fields.
  - Stock page has quote/history/evidence endpoints elsewhere but renders only structure-decision data.
  - Scanner records empty run details but UI can show preview/duration artifacts instead of one honest runtime state.

## 9. Exact Blockers Ranked P0/P1/P2

### P0

1. Scanner does not produce a single honest consumer state for real empty runs. Backend persists empty states, but UI can show `0ms` and demo preview material instead of the actual blocker bucket.
2. Watchlist rows lack saved-symbol enrichment: no current price, price update time, quote freshness, or minimum research packet status.
3. Stock Structure page is treated as the stock research page but does not assemble quote + history + evidence + structure into a minimum packet.

### P1

1. Market Overview synthesis has usable facts but no compact "known facts / missing facts / next research step" first-screen projection.
2. Scanner admin/runtime status is not available to normal users, so consumer Scanner cannot always explain whether the job has not run, ran empty, or is blocked by upstream data.
3. Existing scanner tests show contract drift around observe-only context projection: focused pytest found `rotation_context` included in empty-run diagnostics where the test expected only coarse empty reason, and `themeFrame.state` projected `observe_only` where the test expected `insufficient`.

### P2

1. Liquidity Monitor and Rotation Radar may still be product-degraded, but current route registration is intact.
2. Watchlist contains secondary modules and manual analysis/backtest flows that do not solve row-level factual usefulness.
3. Stock peer-correlation evidence depends on local peer metadata and local OHLCV; absence should stay explicit but secondary to quote/trend packet creation.

## 10. What Not To Fix Next

Do not:

- add more badges, chips, or diagnostic panels to consumer pages;
- add more observation-only explanations as the primary fix;
- relax source authority, score contribution, confidence, fallback, stale, or proxy gates;
- turn preview/demo scanner content into apparent live results;
- create another empty-state page;
- start a broad data-layer refactor;
- add mocked-proof work unless it directly unblocks visible Scanner candidates or Stock/Watchlist minimum packets;
- make Watchlist infer price/research readiness in the frontend from raw scanner diagnostics;
- treat Liquidity Monitor / Rotation Radar as route-registration bugs without a reproduced route failure.

## 11. Recommended Next 3 Implementation Tasks

### PR-003B: Scanner Reality Runner And Honest Empty State

Highest value.

Scope:

- Backend/API: add or project one consumer-safe scanner runtime summary from existing run detail: requested market/profile/universe, counts, terminal status, blocker bucket, and no-advice boundary.
- Frontend: replace scanner demo/preview material in the real no-candidate path with one honest unavailable/no-candidates state.
- Frontend: render immediate empty runs as "completed immediately" or equivalent, not `0ms` pseudo-results.
- Tests: focused API/service/UI tests for empty run, no selected candidates, and source-gated observation-only runs.

Do not change scoring logic, provider routing, or source gates.

### PR-004: Broken Surface Quarantine For Liquidity / Rotation

Scope:

- Verify `/market/liquidity-monitor`, `/market/rotation-radar`, `/liquidity`, `/rotation`, and localized variants.
- If data is unavailable/degraded, quarantine these as market sub-surfaces with one honest unavailable/degraded state and clear links back to Market Overview/Scanner.
- Do not modify provider/cache/runtime logic.
- Do not create new consumer diagnostics.

### PR-005: Watchlist And Stock Minimum Research Packet

Scope:

- Add additive backend packet projection for saved symbols and stock detail: quote price/update/freshness, daily history/trend availability, structure state, evidence gaps, and next research step.
- Wire Watchlist row to show price/update/research status.
- Wire Stock Structure detail to show minimum facts first for one US stock and one CN stock, with valuation/event explicitly unavailable until safe sources exist.
- Keep no-advice and fail-closed gates intact.

If PR-003B discovers Scanner can reliably generate candidates after honest-state cleanup, PR-005 should prioritize Watchlist rows. If Scanner remains blocked by upstream quote/history availability, PR-005 should prioritize Stock minimum packet for direct symbols first.

## 12. File Ownership Map

| Area | Owner files | Boundary |
| --- | --- | --- |
| Market Overview API | `api/v1/endpoints/market.py`, `api/v1/endpoints/market_overview.py`, `api/v1/router.py` | Route registration and API projection |
| Market Overview service | `src/services/market_overview_service.py` | Panel fetch/cache/synthesis and source-confidence gates |
| Market Overview UI | `apps/dsa-web/src/pages/MarketOverviewPage.tsx`, `apps/dsa-web/src/api/market.ts`, `apps/dsa-web/src/api/marketOverview.ts`, `apps/dsa-web/src/components/market-overview/*` | Consumer projection and first-screen hierarchy |
| Scanner API | `api/v1/endpoints/scanner.py` | Manual run, history, detail, overlay, admin status |
| Scanner orchestration | `src/services/market_scanner_ops_service.py` | Run workflow, terminal empty/failed persistence |
| Scanner generation | `src/services/market_scanner_service.py`, `src/core/scanner_profile.py`, `src/core/scanner_theme_registry.py` | Universe, quotes/history, filters, candidate projection |
| Scanner UI | `apps/dsa-web/src/pages/ScannerSurfacePage.tsx`, `apps/dsa-web/src/pages/UserScannerPage.tsx`, `apps/dsa-web/src/api/scanner.ts`, `apps/dsa-web/src/components/scanner/*` | Run action, run detail display, empty state |
| Watchlist API | `api/v1/endpoints/watchlist.py` | Saved-symbol list, add/remove, refresh, overlay |
| Watchlist service | `src/services/watchlist_service.py`, `src/services/watchlist_research_overlay_service.py` | Persisted saved-symbol record, scanner/backtest lineage, read-only overlay |
| Watchlist UI | `apps/dsa-web/src/pages/WatchlistPage.tsx`, `apps/dsa-web/src/api/watchlist.ts`, `apps/dsa-web/src/types/watchlist.ts` | Row rendering and research queue projection |
| Stock API | `api/v1/endpoints/stocks.py` | validate/evidence/structure/quote/history endpoints |
| Stock service | `src/services/stock_service.py`, `src/services/stock_structure_decision_service.py`, `src/services/stock_structure_decision_engine.py` | Quote/history access, structure decision, fail-closed evidence |
| Stock UI | `apps/dsa-web/src/pages/StockStructureDecisionEntryPage.tsx`, `apps/dsa-web/src/pages/StockStructureDecisionPage.tsx`, `apps/dsa-web/src/api/stocks.ts` | Canonical stock page and structure-decision projection |
| Route/nav | `apps/dsa-web/src/App.tsx`, `apps/dsa-web/src/components/layout/consumerAppNavigation.ts`, `apps/dsa-web/src/components/layout/SidebarNav.tsx` | Public/protected route ownership and navigation metadata |
| Liquidity/Rotation | `docs/liquidity/README.md`, `docs/rotation/README.md`, `api/v1/endpoints/liquidity_monitor.py`, `src/services/liquidity_impulse_synthesis_service.py`, `src/services/market_rotation_radar_service.py`, `apps/dsa-web/src/pages/LiquidityMonitorPage.tsx`, `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx` | PR-004 quarantine candidates if product-degraded |

## 13. Validation Performed

Read-only discovery:

- Reviewed recovery and Codex policy docs requested in the task.
- Inspected API route registration for market overview, scanner, watchlist, stock, liquidity, and rotation.
- Inspected scanner entrypoint and candidate-generation code.
- Inspected watchlist API payload and frontend projection.
- Inspected stock page route, data contract, and disabled/empty-state conditions.
- Inspected data reliability, rotation, and liquidity docs for source-boundary requirements.

Runtime/code probes:

- `python -m py_compile api/v1/endpoints/market_overview.py api/v1/endpoints/market.py api/v1/endpoints/scanner.py api/v1/endpoints/watchlist.py api/v1/endpoints/stocks.py src/services/market_overview_service.py src/services/market_scanner_service.py src/services/market_scanner_ops_service.py src/services/watchlist_service.py src/services/watchlist_research_overlay_service.py src/services/stock_structure_decision_service.py src/services/stock_service.py`
  - Result: passed.
- `python -m pytest ...` with the default Python failed because `/Users/yehengli/.browser-use-env/bin/python` has no `pytest`.
- `/Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -q tests/test_market_overview_api.py tests/test_market_overview_snapshot.py tests/api/test_scanner.py tests/test_market_scanner_ops_service.py tests/test_market_scanner_service.py tests/test_watchlist_api.py tests/test_watchlist_research_overlay_service.py tests/api/test_watchlist_research_overlay_endpoint.py tests/test_stock_structure_decision_service.py tests/api/test_stock_structure_decision_endpoint.py tests/test_stock_api_freshness_contract.py`
  - Result: 140 passed, 2 failed, 1 warning.
  - Failures:
    - `tests/test_market_scanner_ops_service.py::MarketScannerOperationsServiceTestCase::test_manual_us_empty_run_persists_only_coarse_empty_reason_after_local_filters` expected empty diagnostics keys `{"empty_reason", "operation"}` but actual diagnostics also included `rotation_context`.
    - `tests/test_market_scanner_service.py::MarketScannerServiceTestCase::test_get_run_detail_scanner_context_frame_fail_closes_when_context_missing` expected `themeFrame.state == "insufficient"` but actual was `"observe_only"`.
  - Interpretation: existing scanner context projection has drifted toward observe-only/rotation-context output. This supports the PR-003B recommendation; PR-003A intentionally did not fix runtime code.

Final docs-only delivery gate:

- `git fetch origin main`
  - Result: passed.
- `git rebase origin/main`
  - Result: passed; branch was already up to date with `origin/main`.
- `git diff --check origin/main...HEAD`
  - Result: passed; no output.
- `git diff --check`
  - Result: passed; no output.
- `bash scripts/release_secret_scan.sh --base-ref origin/main`
  - Result: passed; no high-confidence secret patterns found in changed text files.
