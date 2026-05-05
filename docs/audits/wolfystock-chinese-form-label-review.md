# WolfyStock Chinese Form Label Review

Date: 2026-05-05 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: read-only UI copy/design audit; report only

## 1. Executive Summary

Overall status: **needs localization follow-up, no product fix attempted**.

The Chinese route chrome is broadly Chinese-first after recent UI polish, and the design guard is clean. Remaining English is concentrated in a few surfaces:

- **Highest priority:** `/zh/portfolio` manual entry forms still expose all-caps English field labels such as `SYMBOL`, `TRADE DATE`, `SIDE`, `QUANTITY`, `PRICE`, `FEE`, `TAX`, `REFERENCE`, `NOTE`, `EVENT DATE`, `DIRECTION`, `AMOUNT`, `CURRENCY`, `EFFECTIVE DATE`, `ACTION TYPE`, `DIVIDEND`, and `SPLIT RATIO`.
- **Second priority:** `/zh/backtest` scanner handoff banner shows `Run #` and `Rank #` in Chinese route chrome.
- **Second priority:** `/zh/watchlist` strategy evidence badges mix operator chrome and domain metrics, including `HIST`, `HIT`, `Sharpe`, `DD`, `Trades`, and `Result`.
- **Third priority:** `/zh/scanner` export CSV headers and generated filenames are intentionally technical/export-facing but should be reviewed as developer or artifact labels, not primary UI chrome.
- **Third priority:** `/zh/admin/logs` and `/zh/admin/notifications` correctly localize most chrome, but raw/log/debug modes still surface English technical terms. These are acceptable only when clearly operator/developer scoped and not the default primary experience.

Acceptable domain English examples observed: tickers and symbols (`NVDA`, `AAPL`, `TSLA`, `SPY`, `QQQ`, `BTC`, `ETH`), provider/model names (`OpenAI`, `DeepSeek`, `Gemini`, `AIHubMix`, `FMP API`, `IBKR`), currency codes (`USD`, `HKD`, `CNY`), market/session codes (`US`, `CN`, `HK`, `EDT`, `CST`), and technical indicators or metrics (`RSI14`, `MACD`, `MA20`, `TTM`, `EPS`, `PE`, `VWAP`, `Sharpe`).

## 2. Methodology

Commands run:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -170
./scripts/task_preflight.sh || true

cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
rg -n "\"[A-Za-z][A-Za-z0-9 _:/().,%+-]{2,}\"|'[A-Za-z][A-Za-z0-9 _:/().,%+-]{2,}'|>[A-Za-z][A-Za-z0-9 _:/().,%+-]{2,}<|aria-label=\"[A-Za-z]" src/pages src/components src/i18n src/dev src/__tests__ | head -1200

npm run check:design
npm run lint
npm run build

cd /Users/yehengli/daily_stock_analysis
python3 -m compileall -q src api
rg -n "markdownlint|mdlint|lint:md|lint.*markdown|remark.*lint" package.json apps/dsa-web/package.json .github scripts docs 2>/dev/null | head -80
```

Files inspected:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/design/wolfystock-canonical-ui-primitives.md`
- `docs/audits/wolfystock-frontend-design-conformance-audit.md`
- `docs/qa/wolfystock-workflow-qa-pass.md`
- `docs/checks/design-guard.md`
- `docs/operations/parallel-codex-playbook.md`
- `apps/dsa-web/src/pages/PortfolioPage.tsx`
- `apps/dsa-web/src/pages/SettingsPage.tsx`
- `apps/dsa-web/src/components/settings/*`
- `apps/dsa-web/src/pages/BacktestPage.tsx`
- `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx`
- `apps/dsa-web/src/components/backtest/*`
- `apps/dsa-web/src/pages/AdminLogsPage.tsx`
- `apps/dsa-web/src/pages/AdminNotificationsPage.tsx`
- `apps/dsa-web/src/pages/WatchlistPage.tsx`
- `apps/dsa-web/src/pages/MarketOverviewPage.tsx`
- `apps/dsa-web/src/pages/UserScannerPage.tsx`
- `apps/dsa-web/src/pages/ChatPage.tsx`
- `apps/dsa-web/src/pages/PreviewReportPage.tsx`
- `apps/dsa-web/src/components/report/*`
- `apps/dsa-web/src/i18n/core.ts`
- `apps/dsa-web/src/dev/reportPreviewFixture.ts`

Playwright method:

- Not run in this pass. The task is report-only and the static/source inspection was enough to classify the remaining English chrome without starting or mutating local providers.
- No real providers, LLM calls, scanner runs, portfolio writes, notifications, or DuckDB writes were triggered.

Limitations:

- This is a source and static-search audit, not a live-data browser acceptance pass.
- During the audit, `apps/dsa-web/src/pages/PortfolioPage.tsx` became dirty from outside this task. It was inspected to avoid conflicts, not edited or staged by this task.
- `npm run lint` first failed while that unrelated product file appeared to be mid-edit, then passed on rerun without any product-code change from this task.
- `./scripts/ci_gate.sh` was not run because this is a report-only audit and the requested baseline checks were sufficient after the lint rerun passed.

## 3. Classification Rules

Unacceptable UI chrome English:

- Default-visible form labels, filter labels, tab labels, button text, command bars, empty/error state copy, and accessibility names on `/zh/*` routes when a normal Chinese operator would read them as app chrome.
- English words used as operational labels where a compact Chinese equivalent exists, for example `TRADE DATE`, `DIRECTION`, `Action`, `Result`, `Run #`, or `Rank #`.
- Raw backend status tokens, schema keys, debug codes, or provider error identifiers shown as primary user-facing copy.

Acceptable domain English:

- Ticker symbols, exchange/market codes, provider names, model names, currency codes, data-source labels, file formats, and standard finance or technical-analysis metrics.
- Examples: `NVDA`, `AAPL`, `SPY`, `QQQ`, `USD`, `HKD`, `CNY`, `OpenAI`, `Gemini`, `DeepSeek`, `FMP API`, `IBKR`, `EPS`, `PE`, `RSI`, `MACD`, `MA20`, `VWAP`, `TTM`, `Sharpe`.

Developer-only English:

- Allowed only inside clearly collapsed or operator-scoped details such as `开发者细节`, `原始诊断`, raw log mode, export artifacts, trace fields, or explicit diagnostics panels.
- Developer details should not be default-open and should not expose secrets, API keys, tokens, webhook URLs, or raw JSON as the primary UI.

Raw provider/schema/debug text:

- Must not show by default.
- If needed for operations, it should be masked, localized at the summary layer, and placed inside collapsed developer or diagnostics affordances.

## 4. Findings By Route

| route/surface | finding | visible/default or developer-only | severity | acceptable or needs localization | likely file | recommended fix task |
| --- | --- | --- | --- | --- | --- | --- |
| `/zh/portfolio` manual stock trade form | Default-visible labels use all-caps English: `SYMBOL`, `TRADE DATE`, `SIDE`, `QUANTITY`, `PRICE`, `FEE`, `TAX`, `REFERENCE`, `NOTE`; placeholders include `optional`. | Visible/default | P1 | Needs localization | `apps/dsa-web/src/pages/PortfolioPage.tsx` | Replace form labels/placeholders with existing `portfolio.*` translation keys or add focused keys. Preserve tickers and currency codes. |
| `/zh/portfolio` cash and corporate forms | Default-visible labels use `EVENT DATE`, `DIRECTION`, `AMOUNT`, `CURRENCY`, `NOTE`, `EFFECTIVE DATE`, `ACTION TYPE`, `DIVIDEND`, `SPLIT RATIO`. | Visible/default | P1 | Needs localization | `apps/dsa-web/src/pages/PortfolioPage.tsx` | Localize all manual entry labels; keep `CNY/HKD/USD` as option values. |
| `/zh/portfolio` display currency and broker details | `IBKR`, `Flex XML`, `API`, `CSV`, and `Interactive Brokers` appear in sync/import copy. | Visible/default | P3 | Acceptable domain English | `apps/dsa-web/src/i18n/core.ts`, `apps/dsa-web/src/pages/PortfolioPage.tsx` | Keep provider/file-format names; only localize surrounding chrome. |
| `/zh/settings` AI/provider settings | `API Key`, `AIHubMix`, `OpenAI`, `Gemini`, `DeepSeek`, `GLM / Zhipu`, model IDs, and gateway IDs remain English. | Visible/default | P3 | Acceptable domain English | `apps/dsa-web/src/i18n/core.ts`, `apps/dsa-web/src/components/settings/AIProviderConfig.tsx` | Keep provider/model identifiers; ensure surrounding action labels stay Chinese. |
| `/zh/settings` notification channel config | Notification channel internals define fallback English labels like `Receivers`, `Save`, and comma-separated hints, with a local zh mapping. | Visible/default if mapping regresses | P2 | Needs verification in a visible pass | `apps/dsa-web/src/components/settings/NotificationChannelsConfig.tsx` | Add route or component assertions that zh channel config never falls back to English labels. |
| `/zh/settings/system` raw compatibility fields | Raw config and compatibility keys are deliberately hidden or scoped; raw-field disclosure uses Chinese policy copy. | Developer-only/collapsed | P3 | Acceptable if collapsed | `apps/dsa-web/src/pages/SettingsPage.tsx`, `apps/dsa-web/src/components/settings/SystemControlPlane.tsx` | Keep raw fields collapsed and masked; do not expose unregistered env keys by default. |
| `/zh/backtest` scanner handoff banner | Chinese route shows `Run #{id}` and `Rank #{rank}` for scanner handoff metadata. | Visible/default when scanner handoff exists | P2 | Needs localization | `apps/dsa-web/src/pages/BacktestPage.tsx` | Change to `扫描批次 #` and `排名 #`, preserving numeric IDs. |
| `/zh/backtest` professional workspace | `Grid Search`, `Fees BP`, `Slippage BP`, `Lookback`, `QQQ / SPY / 000300`, `ORCL / AAPL / 600519` appear. | Visible/default in advanced controls | P2/P3 mixed | `Grid Search` likely needs localization; tickers/BP acceptable | `apps/dsa-web/src/components/backtest/ProBacktestWorkspace.tsx` | Localize advanced control labels while preserving tickers, BP, and strategy acronyms. |
| `/zh/backtest/results/1` result status and hero | Most buttons/tabs use `backtest.resultPage` translations; `WolfyStock`, run IDs, strategy labels, dates, and benchmark tickers are acceptable. | Visible/default | P3 | Mostly acceptable | `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx`, `apps/dsa-web/src/components/backtest/*` | Review result-table dynamically formatted labels from parsed backend keys before shipping more raw summary fields. |
| `/zh/backtest/results/1` generated labels from parsed summaries | `formatSummaryLabel()` title-cases raw keys by splitting camelCase/snake_case. If surfaced in tabs/tables, backend schema keys can become English labels. | Visible/default in parameters/audit tables | P2 | Needs localization guard | `apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx` | Add a zh label map or keep raw schema labels inside developer details. |
| `/zh/admin/logs` filter and tab chrome | Tabs, filters, search placeholders, storage summaries, and table headers are localized. `raw`, `trace`, provider/source values, and event types may appear in raw/operator views. | Default plus raw/operator mode | P3 | Acceptable when scoped | `apps/dsa-web/src/pages/AdminLogsPage.tsx` | Keep raw mode explicitly operator-scoped; localize user-facing fallback summaries from raw event/category/status values. |
| `/zh/admin/logs` storage cards | Some mixed terms are visible in Chinese mode: `PostgreSQL autovacuum`, `INFO`, provider/source labels, and `trace`. | Visible/default or raw/operator | P3 | Mostly acceptable technical/operator English | `apps/dsa-web/src/pages/AdminLogsPage.tsx` | Keep technical names, but consider Chinese wrappers such as `INFO 生命周期记录` and `trace 追踪 ID`. |
| `/zh/admin/notifications` channel form | `Webhook`, `Webhook URL`, `Bearer token`, event type examples, `SSL`, `TLS`, `DNS`, `CA`, and `HTTP` remain visible. | Visible/default | P3 | Mostly acceptable technical English | `apps/dsa-web/src/pages/AdminNotificationsPage.tsx` | Keep protocol/security terms; localize generic words like `Bearer token` only if product language wants `Bearer 令牌` consistently. |
| `/zh/admin/notifications` developer details | Raw delivery diagnostics are behind `开发者细节`; raw messages are not primary copy. | Developer-only/collapsed | P3 | Acceptable if collapsed | `apps/dsa-web/src/pages/AdminNotificationsPage.tsx` | Add tests that SSL/webhook raw diagnostics remain collapsed by default. |
| `/zh/watchlist` command/filter chrome | Filters and buttons are localized. Auto-refresh times show `US / CN / HK`, which are market codes and acceptable. | Visible/default | P3 | Acceptable | `apps/dsa-web/src/pages/WatchlistPage.tsx` | No immediate fix except preserving localized labels in future command-bar migrations. |
| `/zh/watchlist` evidence badges | Badges include `HIST`, `HIT`, `Sharpe`, `DD`, `Trades`, and `Result {id}`. These mix metric abbreviations and UI chrome. | Visible/default when data exists | P2 | Needs partial localization | `apps/dsa-web/src/pages/WatchlistPage.tsx` | Keep `Sharpe` as metric; localize `HIST/HIT/DD/Trades/Result` or add Chinese tooltip/label text. |
| `/zh/watchlist` source/context columns | Raw `item.source`, `themeId`, and `universeType` can show backend tokens. | Visible/default when data exists | P2 | Needs normalization | `apps/dsa-web/src/pages/WatchlistPage.tsx` | Map source/universe tokens to display labels; raw IDs can remain secondary/developer text. |
| `/zh/__preview/report` report content | `NVIDIA`, `NVDA`, `FMP API`, `FMP Statements`, `Reddit`, `X / Twitter`, `VWAP`, `MA20`, `RSI14`, `TTM`, `EDT`, and `CST` appear. | Visible/default | P3 | Acceptable domain English | `apps/dsa-web/src/dev/reportPreviewFixture.ts`, `apps/dsa-web/src/components/report/*` | Keep domain terms; ensure section titles and chart controls use Chinese route chrome. |
| `/zh/__preview/report` social fixture text | Fixture contains English prose such as `discussion appears elevated`, `mixed`, and English social synthesis fragments inside a Chinese report. | Visible/default in preview report content | P2 | Needs localization if treated as UI/report fixture copy | `apps/dsa-web/src/dev/reportPreviewFixture.ts` | Localize preview fixture narrative or mark it as raw source quote inside report evidence. |
| `/zh/market-overview` market status and rails | Market tabs, decision strip, fallback states, and coverage summaries are Chinese. Symbols like `VIX`, `BTC`, `ETH`, `DXY`, `US10Y`, `CSI300`, `HSI`, and futures codes are domain English. | Visible/default | P3 | Acceptable domain English | `apps/dsa-web/src/pages/MarketOverviewPage.tsx`, `apps/dsa-web/src/components/market-overview/*` | Preserve symbols; avoid localizing instrument codes. |
| `/zh/scanner` main UI | Many run states and error summaries are localized. Technical ids such as `custom_*`, `universeType`, CSV headers, and filenames are export/developer-like. | Visible/default plus export artifacts | P2/P3 mixed | Needs artifact/developer classification | `apps/dsa-web/src/pages/UserScannerPage.tsx` | Keep deterministic/domain values, but localize visible column/badge chrome and keep raw export headers documented. |
| `/zh/scanner` CSV export | CSV headers are English: `rank,symbol,name,scannerScore,entryRange,target,stop,reason,risk,universeType,theme,generatedAt,runId`; filename starts `scanner_...`. | Generated artifact | P3 | Acceptable if documented as technical export; otherwise localize | `apps/dsa-web/src/pages/UserScannerPage.tsx` | Decide whether exports are machine-oriented. If user-facing, add zh header option for zh locale. |
| `/zh/chat` console/actions | Primary chat chrome is localized; `LLM`, provider/model IDs, skill IDs, and market codes remain technical/domain terms. | Visible/default plus collapsed evidence | P3 | Acceptable domain/developer English | `apps/dsa-web/src/pages/ChatPage.tsx`, `apps/dsa-web/src/i18n/core.ts` | Keep provider/model IDs. Ensure collapsed evidence footer remains scoped and not primary chrome. |
| `/zh/chat` smart-route side effects | Watchlist note `From Stock Chat smart route` is an English stored note created by chat actions. | Generated user-visible data | P2 | Needs localization | `apps/dsa-web/src/pages/ChatPage.tsx` | Store localized note or use a neutral Chinese note when route locale is zh. |

## 5. Acceptable English Whitelist

Tickers and symbols:

- `NVDA`, `AAPL`, `TSLA`, `ORCL`, `SPY`, `QQQ`, `BTC`, `ETH`, `VIX`, `DXY`, `US10Y`, `CSI300`, `HSI`.

Metrics and technical indicators:

- `EPS`, `PE`, `P/E`, `RSI`, `RSI14`, `MACD`, `MA5`, `MA10`, `MA20`, `MA60`, `VWAP`, `ATR`, `OBV`, `TTM`, `Sharpe`.

Currencies and market codes:

- `USD`, `HKD`, `CNY`, `EUR`, `JPY`, `GBP`, `US`, `CN`, `HK`.

Providers, protocols, and source labels:

- `OpenAI`, `Gemini`, `DeepSeek`, `AIHubMix`, `Anthropic`, `GLM / Zhipu`, `FMP`, `FMP API`, `FMP Statements`, `IBKR`, `Interactive Brokers`, `PostgreSQL`, `DuckDB`, `Webhook`, `TLS`, `SSL`, `DNS`, `HTTP`, `API`.

Developer/model/provider details:

- Model IDs, gateway IDs, environment/config keys, trace IDs, raw event types, provider status codes, CSV headers, and generated filenames are acceptable only when they are developer details, explicit diagnostics, or machine-oriented exports.

## 6. Recommended Implementation Phases

Phase 1: P1/P2 visible chrome only

- Localize `/zh/portfolio` manual entry labels and `optional` placeholders.
- Localize `/zh/backtest` scanner handoff `Run #` / `Rank #`.
- Localize `/zh/watchlist` visible evidence badge chrome and raw source/universe token display.
- Localize `/zh/chat` generated watchlist note.

Phase 2: table/tooltip/accessibility labels

- Review `aria-label`, `title`, table headers, status chips, empty states, and icon-only actions on the target routes.
- Add route/component assertions for zh labels where regressions are likely.

Phase 3: developer details consistency

- Standardize collapsed labels for raw/debug/provider/schema details.
- Keep raw backend tokens, event types, provider errors, and schema keys inside developer/operator scopes.

Phase 4: tests / fixture assertions

- Add fixture tests for `/zh/portfolio`, `/zh/watchlist`, `/zh/backtest`, `/zh/__preview/report`, and `/zh/chat`.
- Add an assertion set that blocks obvious English fallback chrome while whitelisting tickers, providers, metrics, currencies, and technical indicators.

## 7. Non-Goals

- No product code changed.
- No tests changed.
- No CSS changed.
- No backend/API changed.
- No package files or config changed.
- No `docs/CHANGELOG.md` changed.
- No generated artifacts committed.
- No label fixes were attempted in this task.

## 8. Appendix

Preflight:

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- branch: `main`
- initial `git status --short`: clean
- initial upstream: `origin/main`, ahead 0 / behind 0
- `./scripts/task_preflight.sh || true`: PASS; branch `main`; dirty files `0`

Static search:

- Requested `rg` command ran under `apps/dsa-web`.
- The first 1200 matches were reviewed with targeted follow-up inspection of target route files.
- High-signal matches included portfolio all-caps labels, scanner/backtest run metadata, watchlist evidence abbreviations, preview report fixture English narrative fragments, and settings/admin technical/provider terminology.

Baseline checks:

| Command | Result | Key output |
| --- | --- | --- |
| `npm run check:design` | PASS | 216 files scanned; 0 blocking; 0 warnings. |
| `npm run lint` | PASS on rerun | First run failed on unrelated dirty `PortfolioPage.tsx` while another edit appeared incomplete; rerun exited 0 without this task changing product code. |
| `npm run build` | PASS with warning | 3160 modules transformed; large chunk warning for `DeterministicBacktestChartWorkspace-1CKEfPQC.js` at 532.42 kB. |
| `python3 -m compileall -q src api` | PASS | No output. |
| Markdown lint search | Not available | Search found prior docs mentions only; no runnable markdown lint script found. |
| `./scripts/ci_gate.sh` | Not run | Report-only task; baseline checks passed after lint rerun, and full CI was not required by the prompt. |

Key file references:

- `apps/dsa-web/src/pages/PortfolioPage.tsx`: manual entry labels around stock, cash, and corporate forms.
- `apps/dsa-web/src/pages/BacktestPage.tsx`: scanner handoff metadata banner.
- `apps/dsa-web/src/pages/WatchlistPage.tsx`: filter copy, action bar, evidence badges, source/context tokens.
- `apps/dsa-web/src/pages/UserScannerPage.tsx`: scanner status normalization, export rows, CSV headers, generated filenames.
- `apps/dsa-web/src/pages/AdminLogsPage.tsx`: localized tabs/filters plus raw/operator trace and provider details.
- `apps/dsa-web/src/pages/AdminNotificationsPage.tsx`: notification channel form, webhook/security terms, collapsed developer details.
- `apps/dsa-web/src/pages/ChatPage.tsx`: provider/model evidence footer and stored watchlist note.
- `apps/dsa-web/src/dev/reportPreviewFixture.ts`: preview report domain terms and English fixture narrative.
- `apps/dsa-web/src/i18n/core.ts`: zh/en route copy source for portfolio, backtest, scanner, report, settings, and admin logs.

Parallel safety:

- Only this report file is intended for commit.
- The unrelated dirty `apps/dsa-web/src/pages/PortfolioPage.tsx` was not edited, cleaned, staged, or committed by this task.
- `git add .` was not used.
