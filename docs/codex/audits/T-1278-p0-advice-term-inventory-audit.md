# T-1278 P0 Advice Term Inventory Audit

Task ID: T-1278
Task title: P0 Advice term inventory audit
Mode: READ-ONLY-AUDIT with optional audit doc
Workspace: `/Users/yehengli/worktrees/t1278-p0-advice-term-inventory-audit`

## Method

- Read required guard docs: `AGENTS.md`, `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`, `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`, `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`, `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`, `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`.
- Ran repo-wide `rg` scans for the task-provided Chinese and English terms, plus adjacent identifiers such as `advice`, `recommendation`, `action`, `trading`, `position`, `entry`, `stop_loss`, `take_profit`, `target_price`, `targetPrice`, `stopLoss`, and `takeProfit`.
- Five requested subagents were spawned read-only with `gpt-5.4` and `xhigh`, but all failed before completion due stream disconnects from `https://aijh.huanmin.top/v1/responses`. This report is based on main-thread local scans.
- No source/runtime/API/frontend/provider/cache/DB/config/package files were edited.

## Decision Summary

Advice/action wording is a P0 blocker because it is still generated at the AI prompt and report-renderer layer, preserved in API/history contracts, and distributed by markdown/Discord/WeChat notification templates. Existing frontend Home/report drawers and markdown export sanitizers reduce some visible leakage, but they do not neutralize the upstream prompt, stored payload, report renderer, or notification surfaces.

The safest remediation order is source-to-sink:

1. Neutralize analyzer/agent/report-renderer generated action semantics while preserving schema compatibility.
2. Sanitize report rendering and notification/export distribution paths.
3. Finish frontend/i18n visible copy cleanup and keep existing consumer-safe projection seams.
4. Add grep/API/UI guard coverage that catches the broader P0 vocabulary, not only `buy now`/order CTAs.
5. Handle backtest/options/portfolio wording as protected-domain work: preserve math/accounting/contracts and relabel only presentation where appropriate.

## Inventory Table

| File | Line/function | Term | Surface | Consumer-visible? | Severity | Recommended task |
| --- | --- | --- | --- | --- | --- | --- |
| `src/analyzer.py` | 367 `AnalysisResult.operation_advice` | `操作建议：买入/加仓/持有/减仓/卖出/观望` | backend data model, history/report payload | Yes, via API/report/notification | P0 | Preserve field for compatibility but change generated/user-visible value set to observation states; document schema compatibility. |
| `src/analyzer.py` | 400 `buy_reason` | `买入/卖出理由` | backend model narrative | Yes, if rendered in reports | P0 | Rename presentation semantics to research rationale; avoid personalized action reason. |
| `src/analyzer.py` | 544-694 `SYSTEM_PROMPT` | `趋势交易`, `直接告诉用户做什么`, `买入信号`, `空仓者建议`, `持仓者建议`, `理想买入点`, `止损位`, `目标位`, `建议仓位`, `分批建仓`, `该买该卖`, `精确狙击点` | AI prompt/output | Yes, source of generated reports | P0 protected | Protected AI prompt/output remediation; rewrite to observation-only research packet without changing model routing. |
| `src/analyzer.py` | 1761 prompt context | `买入理由` | AI prompt context | Yes, LLM input can shape output | P0 protected | Reframe as `正向因素/风险因素`; avoid buy/sell framing. |
| `src/analyzer.py` | 1859-1867 prompt requirements | `该买/该卖/该等`, `持仓分类建议`, `买入价、止损价、目标价` | AI prompt/output | Yes | P0 protected | Replace with scenario observation, risk boundary, and confidence/freshness requirements. |
| `src/analyzer.py` | 2025-2050 retry prompt | `operation_advice`, `买入/加仓/持有/减仓/卖出/观望`, `止损价` | AI retry prompt/output | Yes | P0 protected | Update retry schema completion copy after primary prompt rewrite. |
| `src/analyzer.py` | 2254-2268 fallback parser | `买入`, `卖出`, `Buy`, `Sell` | backend fallback generation | Yes, fallback report/action | P0 protected | Map fallback to observation states; keep internal `decision_type` only if required for compatibility. |
| `src/agent/executor.py` | 117-210 prompt | `operation_advice`, `买入信号`, `空仓者建议`, `sniper_points`, `该买该卖`, `精确狙击点` | agent prompt/output | Yes if agent path is product reachable | P0 protected | Align agent prompt with analyzer observation-only contract. |
| `src/agent/orchestrator.py` | 869-873 | `suggested_position`, `entry_plan`, `止损参考` | agent-generated dashboard fallback | Yes if agent path output is surfaced | P0 protected | Replace default position/action fallback with bounded observation state. |
| `src/agent/orchestrator.py` | 1199-1204 | `入场条件`, `加仓`, `新开仓`, `减仓或退出` | agent risk override output | Yes if agent path output is surfaced | P0 protected | Reframe risk overrides as observation/coverage constraints. |
| `src/agent/orchestrator.py` | 1345-1390 | `买入`, `减仓/卖出`, `买入信号`, `分批试仓`, `加仓`, `减仓或离场` | agent action normalization/defaults | Yes if agent path output is surfaced | P0 protected | Split internal decision enum from user-visible language. |
| `src/core/pipeline.py` | 1795-1821 | `强烈买入`, `买入`, `加仓`, `减仓`, `卖出` | backend canonical action mapping | Yes via pipeline/report | P0 protected | Keep internal enum if needed; remap public language. |
| `src/core/pipeline.py` | 2516-2530 | `综合建议`, `新仓`, `仓位`, `止损` | backend dashboard post-processing | Yes | P0 protected | Replace generated public copy with research status/risk boundary wording. |
| `src/services/analysis_service.py` | 743-795 payload | `action`, `entry_price`, `stop_loss`, `take_profit` | API analysis payload | Yes via `/api/v1/analysis/analyze` | P0 protected | Add consumer-safe projection or alias fields; do not break stored/API compatibility without contract review. |
| `src/services/analysis_service.py` | 862-879 payload | `operation_advice`, `ideal_buy`, `secondary_buy`, `stop_loss`, `take_profit` | API/history report payload | Yes | P0 protected | Preserve stored fields but add sanitized public projection; retire unsafe labels from default consumers. |
| `src/services/analysis_service.py` | 1690-1770 decision trace | `action`, `entry`, `target`, `stop` | API decision trace | Potentially visible/debug/admin | P1 protected | Keep admin/internal or relabel default consumer trace; avoid default display. |
| `src/services/analysis_service.py` | 1819-1835 conflict messages | `buy/add/accumulate`, `entry`, `buy_with_invalidating_risk` | decision trace limitations/conflicts | Potentially visible/debug/admin | P1 protected | Keep internal/debug only or sanitize if consumer surfaced. |
| `api/v1/schemas/history.py` | 64, 178 | `operation_advice` description `操作建议` | API schema/history | Yes via docs/schema/API | P0 protected | Schema compatibility review; change descriptions/public docs to research view while preserving field name if necessary. |
| `api/v1/schemas/history.py` | 192-195 | `ideal_buy`, `secondary_buy`, `stop_loss`, `take_profit` descriptions | API schema/history | Yes | P0 protected | Add public projection or relabel descriptions; avoid breaking clients without version plan. |
| `api/v1/endpoints/history.py` | 343-365 | `operation_advice`, `ideal_buy`, `secondary_buy`, `stop_loss`, `take_profit` | history detail API | Yes | P0 protected | Apply public response sanitizer/projection at endpoint or service seam. |
| `src/schemas/report_schema.py` | 91-105 | `SniperPoints`, `ideal_buy`, `stop_loss`, `take_profit`, `PositionStrategy`, `entry_plan` | stored report schema | Yes via renderer/API | P0 protected | Contract migration plan; keep raw stored values internal and expose observation projection. |
| `src/services/report_renderer.py` | 575-616 price basis notes | `Entry, stop, target`, `trading plan` | standard report text | Yes in reports | P0 | Reword to price/risk/reference context. |
| `src/services/report_renderer.py` | 1478-1496 battle compact | `理想买入点`, `次优买入点`, `止损位`, `目标位`, `仓位建议` | report renderer payload | Yes | P0 | Replace renderer labels with observation-only labels. |
| `src/services/report_renderer.py` | 1552-1598 decision panel | `ideal_entry`, `backup_entry`, `stop_loss`, `target`, `position_sizing`, `build_strategy`, `no_position_advice`, `holder_advice` | standard report payload | Yes | P0 protected | Add/switch to sanitized public decision panel while preserving stored/raw compatibility. |
| `src/services/report_renderer.py` | 1704-1725 cleaner prefixes | `理想买入点`, `Stop Loss`, `Target` | report normalization | Yes | P1 | Update after label rewrite; keep compatibility for legacy payload parsing. |
| `src/services/report_renderer.py` | 3448-3630 trade setup builder | `主动买点`, `跟进`, `补第二笔`, `止损放在`, `试仓`, `仓位`, `目标`, `交易场景` | backend-generated standard report | Yes | P0 protected | Highest-risk renderer rewrite; change generated copy to non-actionable observation/risk boundaries without changing market math. |
| `src/services/report_renderer.py` | 3653-3667 battle fields | `交易场景`, `关键动作`, `理想买入点`, `止损位`, `目标位`, `仓位建议`, `建仓策略` | standard report sections | Yes | P0 | Replace default field labels and downstream tests. |
| `templates/report_markdown.j2` | 3, 7, 10-20, 241-269 | `Recommendation`, `Key Action`, `Ideal Entry`, `Advice Without Position`, `Execution Plan`, `Entry Plan`, `Execution Reminders` | markdown report/export template | Yes, distributed/exported | P0 | Template relabel/removal after renderer payload rewrite; ensure export filter is defense-in-depth. |
| `templates/report_discord.j2` | 9, 13-19 | `评分 / 建议 / 趋势`, `关键动作`, `理想买入点`, `目标位`, `空仓 / 持仓建议` | Discord notification template | Yes, distributed | P0 protected notification | Replace with observation labels and filtered values. |
| `templates/report_wechat.j2` | 46-62 | `ideal_buy`, `stop_loss`, `take_profit`, `no_position`, `has_position` | WeChat notification template | Yes, distributed | P0 protected notification | Replace or remove action-point compact block. |
| `src/notification.py` | 859-865 cleaner prefixes | `理想买入点`, `Stop Loss`, `Target` | notification report generation | Yes | P1 protected notification | Update compatibility cleaner after public labels change. |
| `src/notification.py` | 1123-1150 dashboard report | `作战计划`, `理想买入点`, `止损位`, `目标位`, `仓位建议`, `建仓策略` | notification body | Yes | P0 protected notification | Sanitize detailed report before send or render safe sections only. |
| `src/notification.py` | 1210-1215, 1326-1345, 1611-1623 | `狙击点位`, `ideal_buy`, `stop_loss`, `take_profit`, `持仓建议` | WeChat/compact notification | Yes | P0 protected notification | Remove sniper/action point distribution or relabel as observation context. |
| `src/notification_sender/discord_sender.py` | 228-256 | `评分 / 建议 / 趋势`, `买入 / 观望 / 卖出`, `理想买入点 / 次优买入点 / 止损位 / 目标位 / 仓位`, `空仓者建议`, `持仓者建议` | Discord optimizer | Yes | P0 protected notification | Update compact fallback and assertions. |
| `src/report_language.py` | 27-59 | `买入`, `Strong Buy`, `Sell`, `Reduce` translations | report localization | Yes | P0 | Public label mapping must be observation-only; keep internal enum if required. |
| `src/report_language.py` | 179, 212-219, 292-299 | `操作建议`, `作战计划`, `理想买入点`, `仓位建议`, `Entry Plan` | report labels | Yes | P0 | Replace public labels with research view/observation plan/risk boundary. |
| `src/core/export_filter.py` | 12-70 | unsafe term replacements | export sanitizer | Yes, defense-in-depth | Acceptable/P1 | Good existing guard; expand/centralize for report/notification if used beyond history markdown. |
| `api/v1/endpoints/history.py` | 533 | `sanitize_markdown_export(markdown_content)` | history markdown export | Yes | Acceptable/P1 | Existing safe seam; keep and extend tests after source rewrite. |
| `src/market_analyzer.py` | 526-589 | `Strategy Plan`, `position sizing guideline`, `仓位建议`, `建议仅供参考` | market review prompt/output | Potentially consumer-visible | P0 protected AI prompt/output | Reframe market review strategy section as regime observation/risk state; disclosure alone is insufficient. |
| `src/stock_analyzer.py` | 55-58, 785 | `BUY = 买入`, `SELL = 卖出`, `操作建议` | technical analyzer/log/legacy output | Potentially report/internal | P1 protected | Determine if consumer-facing; keep internal signal enum but sanitize public output. |
| `main.py` | 368 | `r.operation_advice` printed in CLI summary | CLI/local output | Internal/operator | P2 acceptable | Optional CLI relabel after backend public mapping; not default consumer UI. |
| `SKILL.md` | 15, 18, 61, 90 | `仓位建议`, `battle_plan`, `狙击点`, `操作建议` | product/external integration doc | Potentially public docs | P1 docs | Update docs after runtime semantics change; docs are stale and high-risk if distributed. |
| `docs/openclaw-skill-integration.md` | 59-60, 138 | `stop_loss`, `take_profit`, `operation_advice`, `ideal_buy` | external integration docs | Potentially public/docs | P1 docs | Update external integration guidance after API/report projection plan. |
| `docs/full-guide.md` | 959-1071 | `操作建议`, `止盈/止损`, `买入/加仓`, `仓位` | product docs/backtest docs | Docs only | P2 | Split historical backtest semantics from consumer advice policy; update docs after behavior rewrite. |
| `docs/data-reliability/single-stock-actionability-observation-contract.md` | 24-63, 104-115, 218-287 | forbidden actionability policy | contract docs | Internal docs | Acceptable | Existing policy supports remediation; use as source for follow-up acceptance. |
| `strategies/*.yaml` | multiple | `买入`, `卖出`, `止损`, `仓位建议` | strategy library/prompt inputs | Backend prompt source | P1 protected AI prompt | If strategy descriptions are injected into LLM output, rewrite to observational signal language; otherwise internal simulation semantics acceptable. |
| `src/core/backtest_engine.py` | 56-66 | `加仓`, `建仓`, `减仓` keyword extraction | historical evaluation/backtest parsing | Internal/backtest semantics | Acceptable protected | Do not change math/parser semantics in advice cleanup; only presentation labels if consumer-visible. |
| `src/core/rule_backtest_engine.py` | 636-707, 794-889, 994-1205, 1949-2023, 2256-2398 | `买入条件`, `卖出条件`, `止损`, `止盈`, `按计划买入` | backtest rule parser/results | Consumer-visible in backtest pages but historical simulation | P1 protected | Preserve rule semantics; ensure UI says historical simulated rule events, not recommendations. |
| `src/services/rule_backtest_service.py` | 8635-8809, 9083-9097 | `仓位行为`, `止损`, `止盈`, `分批建仓`, `分批买入`, `逐级加仓` | backtest assumptions/support | Consumer-visible support details | P1 protected | Relabel assumptions as simulation constraints only; do not change backtest execution semantics. |
| `apps/dsa-web/src/components/backtest/strategyCatalog.ts` | 89-541 | many `买入/卖出`, `Buy when...`, `sell...`, `Stop loss` | backtest templates | Yes on backtest setup | P1 protected | Keep strategy grammar but add/strengthen presentation framing: historical simulation rule, not trade recommendation. |
| `apps/dsa-web/src/pages/BacktestPage.tsx` | 1351-1352 | disclosure: buy/sell are historical rule events only | backtest page | Yes | Acceptable | Existing mitigation; verify default-visible placement and guard broad enough. |
| `apps/dsa-web/src/components/backtest/BacktestResultReport.tsx` | 237-240, 1492-1500 | `信号入场`, `止损离场`, `模拟买入事件`, `模拟卖出事件` | backtest result report | Yes, historical simulation | Acceptable/P1 | Acceptable if always framed as simulated/historical; keep negative tests. |
| `apps/dsa-web/src/components/backtest/strategyInspectability.ts` | 167-195 | `买入条件`, `卖出条件`, `Entry rule`, `Exit rule` | backtest inspectability | Yes, historical simulation | P1 protected | Relabel to simulated rule condition if needed; preserve parser semantics. |
| `apps/dsa-web/src/components/backtest/normalizeDeterministicBacktestResult.ts` | 114-121 | `买入`, `卖出`, `Buy`, `Sell` | backtest normalized trade action | Yes in result/event tables | P1 protected | Ensure render layer prefixes with simulated event; do not change stored action values blindly. |
| `apps/dsa-web/src/i18n/core.ts` | 410-411, 460-481 | `目标位`, `止损位`, `建仓区间`, `止损建议`, `动作建议`, `理想介入` | guest/home i18n | Yes | P0 frontend-only | Replace guest/default copy with observation/risk-boundary language. |
| `apps/dsa-web/src/i18n/core.ts` | 1952, 1985-1992, 2051-2099 | `操作建议`, `仓位建议`, `次优买入点`, `止损位`, `建仓策略`, `作战计划`, `持仓者建议`, `空仓者建议` | report i18n | Yes if old report surfaces use labels | P0 frontend/report | Align with `homeReportIdentity` safe labels; remove old label exports from visible surfaces. |
| `apps/dsa-web/src/i18n/core.ts` | 3404-3476, 4978-4988 | `Target`, `Stop Loss`, `Execution Strategy`, `Position Plan`, `Entry`, `Target zone`, `Secondary entry`, `Position sizing` | English UI | Yes | P0 frontend-only | Same English relabel cleanup. |
| `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx` | 146 | forbidden action text pattern | Home safety guard | Yes guard only | Acceptable | Good local guard; expand as central test fixture if possible. |
| `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx` | 1881-1912, 4483-4495 | `建仓区间`, `目标位`, `止损位` alias mapping | Home rendering/projection | Yes but mapped | P1 | Rename aliases/fallback labels to observation-only; keep sanitizer behavior. |
| `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx` | 3322-3338 | searches battle plan `entry`, `建仓`, `stop`, `止损` | Home report projection | Yes | P1 | Keep extraction but ensure only safe labels/values render. |
| `apps/dsa-web/src/utils/homeReportIdentity.ts` | 11-12, 46-79, 81-104 | broad action sanitizer | Home drawer/export sanitizer | Yes defense-in-depth | Acceptable/P1 | Existing safe seam; make shared for report/notification if frontend-only. |
| `apps/dsa-web/src/utils/homeReportIdentity.ts` | 520-585 | safe markdown export builder | drawer/export | Yes | Acceptable | Existing consumer-safe projection; add regression terms if upstream expands. |
| `apps/dsa-web/src/components/home-bento/FullDecisionReportDrawer.tsx` | 302-343 | safe labels `关键价格区间`, `风险边界`, `上方观察区`, `继续跟踪` | drawer/default UI | Yes | Acceptable | Keep as model for report templates. |
| `apps/dsa-web/src/components/report/StandardReportPanel.tsx` | 257-285 | action semantic keys include `止损`, `建仓`, `加仓`, `entry` | report UI de-dupe | Yes internal classification | Acceptable/P1 | Fine as internal classifier; ensure labels/values are sanitized. |
| `apps/dsa-web/src/components/report/StandardReportPanel.tsx` | 692-724, 1376-1410 | consumer-safe panel text/price around `stopLoss`, `target`, `positionSizing`, `buildStrategy` | report UI | Yes | Acceptable/P1 | Existing sanitizer; still depends on backend unsafe payload. |
| `apps/dsa-web/src/api/reportNormalizer.ts` | 107-164 | `hasTradingPlan`, missing field `操作建议`, `交易计划` | completeness/status UI | Yes if surfaced | P1 frontend-only | Reword completeness concepts to research packet coverage. |
| `apps/dsa-web/src/types/analysis.ts` | 259-273, 410-439 | `operationAdvice`, `idealBuy`, `stopLoss`, `positionSizing`, `noPositionAdvice` | frontend API types | Internal/API contract | P1 protected API | Type compatibility review; add safe projection types rather than broad rename. |
| `apps/dsa-web/src/pages/UserScannerPage.tsx` | 518-567, 1416-1436, 2710-2813 | `entry/buy`, `target price`, `stop loss` lookup but renders `参考区间`/`风险边界` | scanner UI | Yes | Acceptable/P1 | Keep safe labels; ensure candidate raw values are sanitized. |
| `apps/dsa-web/src/components/scanner/ScannerDisplayAtoms.tsx` | 25-31 | maps `entry/buy/target/stop` to safe display | scanner shared component | Yes | Acceptable | Existing safe projection. |
| `apps/dsa-web/src/components/watchlist/LeveragedEtfMapper.tsx` | 62-66, 91-95 | `正股/指数目标价`, `ETF 目标价`, `ETF 止损观察价`, `ETF 止盈观察价`, `target price`, `take-profit mark` | watchlist mapper tool | Yes | P1 frontend/options-like | Reword to scenario reference price/upside/risk mark; API field names protected. |
| `api/v1/schemas/leveraged_etf_mapper.py` | 49-65 | `underlyingTargetPrice`, `etfTargetPrice` | API schema | Yes/API | P1 protected API | Preserve field names; change docs/UI labels only unless versioned API change is scoped. |
| `apps/dsa-web/src/pages/OptionsLabPage.tsx` | 503, 1106, 1761 | `目标价下情景估算` | options scenario payoff | Yes | Acceptable/P1 protected options | Usually acceptable as user-supplied scenario assumption; avoid actionability elsewhere. |
| `api/v1/schemas/options.py` | 708-1136 | `targetPrice`, `action: buy/sell` | options API schema | API/protected | P1 protected options/API | Do not change without options contract task; ensure UI labels remain no-advice. |
| `apps/dsa-web/src/pages/PortfolioPage.tsx` | 760-761, 1096, 3917 | `buy`, `sell` manual ledger side labels | portfolio manual record form | Yes authenticated | Acceptable protected portfolio | Acceptable for manual bookkeeping if no broker/order semantics; maintain no-order copy. |
| `api/v1/schemas/portfolio.py` | 125, 140, 414 | `side: buy/sell` | portfolio API schema | API/protected | Acceptable protected portfolio | Portfolio accounting contract; do not alter for advice cleanup. |
| `apps/dsa-web/src/components/portfolio/PortfolioScenarioRiskPanel.tsx` | 69 | `模型结果不可作为仓位建议` | portfolio scenario risk UI | Yes | Acceptable | Good safety language; keep/expand guard. |
| `src/agent/agents/portfolio_agent.py` | 7, 63 | `Position sizing suggestions` | agent/internal portfolio analysis | Potentially surfaced | P1 protected portfolio/AI | Reframe if product reachable; otherwise internal agent prompt. |
| `src/services/portfolio_construction_service.py` | 222-225 | `estimated_trade_direction = buy/sell` | portfolio construction read model | Internal/API | P1 protected portfolio | Keep internal if not consumer-visible; ensure read model says scenario, not instruction. |
| `src/services/watchlist_service.py` | 34 | forbidden action pattern includes `买入/卖出/止损/目标价/仓位` | watchlist sanitizer | Service guard | Acceptable | Existing guard. |
| `tests/test_notification.py` | 305-335, 381-390 | asserts `操作建议`, `理想买入点`, `空仓 / 持仓建议` remain in notifications | test coverage | Test-only but locks unsafe output | P0 test debt | Update after notification remediation; current tests protect P0 leakage. |
| `tests/test_notification_sender.py` | 180-197 | fixture asserts advice labels in Discord optimizer | test coverage | Test-only but locks unsafe output | P0 test debt | Update after Discord remediation. |
| `tests/test_report_renderer.py` | 696-699, 1006 | asserts `理想买入点`, `仓位建议` renderer fields | test coverage | Test-only but locks unsafe output | P0 test debt | Rewrite renderer tests around observation labels. |
| `tests/test_analysis_history.py` | 1189-1210 | history export sanitizer negative fixture | test coverage | Test-only | Acceptable | Good export guard; expand terms and verify no unsafe markdown sections. |
| `tests/api/test_public_api_surface_safety.py` | 55-68 | forbidden advice markers only severe/order terms | API guard | Test-only | P1 gap | Expand to P0 terms for public analysis/history/report APIs. |
| `apps/dsa-web/e2e/ai-research-entry-launch.spec.ts` | 8-9, 138-141 | broad first-viewport forbidden pattern includes target/stop/position sizing | e2e guard | Test-only | Acceptable/P1 | Good launch guard; ensure report/drawer/export routes included. |
| `apps/dsa-web/e2e/consumer-copy-forbidden-vocabulary.smoke.spec.ts` | 14-29, 146-170 | backend/provider/debug vocabulary only | e2e guard | Test-only | P1 gap | Add advice/action vocabulary or centralize guard helper. |
| `apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts` | 16-17, 82-95 | order/unsafe trading pattern | e2e guard | Test-only | P1 gap | Expand beyond `buy now`/order CTAs to target/stop/position terms where route should be no-advice. |
| `apps/dsa-web/e2e/portfolio-launch-surface.spec.ts` | 9, 236 | forbidden portfolio launch labels and no-position-advice copy | e2e guard | Test-only | Acceptable | Good for portfolio launch; keep manual ledger exceptions explicit. |

## Consumer-visible P0 Hits

- AI-generated single-stock decision dashboard: `src/analyzer.py`, `src/agent/executor.py`, `src/agent/orchestrator.py`.
- Backend report payload and standard report generation: `src/services/analysis_service.py`, `src/schemas/report_schema.py`, `src/services/report_renderer.py`.
- History/API schema and detail endpoint: `api/v1/schemas/history.py`, `api/v1/endpoints/history.py`.
- Distributed report templates and notification send paths: `templates/report_markdown.j2`, `templates/report_discord.j2`, `templates/report_wechat.j2`, `src/notification.py`, `src/notification_sender/discord_sender.py`, `src/report_language.py`.
- Frontend/i18n user copy that independently promises actionable fields after login: `apps/dsa-web/src/i18n/core.ts`.
- Market review prompt strategy plan: `src/market_analyzer.py`.

## Acceptable Internal/Admin/Test-Only Hits

- Backtest parser/execution terms such as `entry`, `exit`, `buy`, `sell`, `stop_loss`, and `take_profit` are acceptable only when they describe historical simulation rules or stored deterministic execution events. They are protected backtest semantics and should not be changed as a copy cleanup side effect.
- Portfolio `side: buy/sell` fields are acceptable for manual ledger/accounting APIs and authenticated bookkeeping UI, provided the UI continues to say it does not place orders or connect brokers.
- Existing sanitizer tests and fixtures deliberately contain unsafe terms to prove removal. These are acceptable test-only terms unless the assertions currently require unsafe output.
- Existing consumer-safe projection code in `homeReportIdentity.ts`, `FullDecisionReportDrawer.tsx`, `StandardReportPanel.tsx`, `ScannerDisplayAtoms.tsx`, and scanner page rendering is acceptable as defense-in-depth, though it cannot replace backend remediation.

## Backend-Generated Remediation Required

Backend-generated P0 risk is not limited to labels. It includes prompt instructions, generated values, normalized payloads, stored schema fields, and renderer fallbacks. Required backend batches:

- Analyzer/agent prompt rewrite: observation-only output contract; no direct buy/sell/position-size/entry/exit instruction in human-readable values.
- Report renderer rewrite: `trade_setup`, `battle_fields`, `decision_panel`, and report labels must emit observation/risk-boundary language by default.
- API/history compatibility plan: preserve raw/stored fields where necessary, but expose sanitized public projections and update schema descriptions.
- Notification/export distribution: every distributed channel should render only sanitized public sections; `export_filter.py` should become defense-in-depth, not the only safe seam.

## Frontend-Only Remediation Candidates

- `apps/dsa-web/src/i18n/core.ts` guest and report labels: replace `建仓区间`, `止损建议`, `目标位`, `动作建议`, `仓位建议`, `次优买入点`, `作战计划`, `Entry`, `Stop Loss`, `Position sizing`, etc.
- `apps/dsa-web/src/api/reportNormalizer.ts` completeness copy: replace `操作建议`/`交易计划` missing field labels with research packet coverage terms.
- `apps/dsa-web/src/components/watchlist/LeveragedEtfMapper.tsx` labels: use scenario reference/upside/risk marks while leaving API field names intact.
- Backtest visible labels may be frontend-only if strictly presentation and tests prove historical simulation framing remains unchanged.

## Protected-Domain Escalation Notes

- AI prompt/output: `src/analyzer.py`, `src/agent/executor.py`, `src/agent/orchestrator.py`, `src/market_analyzer.py` are protected. Remediation must explicitly scope prompt semantics and regression tests.
- API schema/stored contracts: `api/v1/schemas/history.py`, `src/schemas/report_schema.py`, `apps/dsa-web/src/types/analysis.ts`, options/portfolio schemas require compatibility planning.
- Notification routing: `src/notification.py`, `src/notification_sender/discord_sender.py`, and channel templates are protected. Change content rendering only, not delivery routing/retry/send semantics.
- Backtest semantics: rule parser/result terms must not be globally renamed in engine/schema. Limit changes to public presentation labels and guards.
- Portfolio risk/accounting: `buy/sell` sides and scenario contribution fields are accounting/read-model semantics. Do not mutate ledger/API behavior for copy cleanup.
- Options Lab: `targetPrice` and `action: buy/sell` in options schemas are protected options contract terms. UI may relabel scenario assumptions, but API changes need separate scope.

## Ordered Remediation Batches

### P0

1. Analyzer/agent no-advice output contract
   - Scope: `src/analyzer.py`, `src/agent/executor.py`, `src/agent/orchestrator.py`, focused AI public-safety tests.
   - Goal: remove direct action wording from prompt-generated human-readable fields while preserving internal enums where needed.

2. Report renderer public projection
   - Scope: `src/services/report_renderer.py`, `src/report_language.py`, `templates/report_markdown.j2`, renderer tests.
   - Goal: default reports use `研究状态`, `关键价格区间`, `参考区间`, `风险边界`, `上方观察区`, `继续跟踪`.

3. Notification/distribution sanitizer
   - Scope: `src/notification.py`, `src/notification_sender/discord_sender.py`, `templates/report_discord.j2`, `templates/report_wechat.j2`, notification tests.
   - Goal: Discord/WeChat/email-like channels never distribute old action labels or values.

4. API/history public projection
   - Scope: `api/v1/endpoints/history.py`, `api/v1/schemas/history.py`, `src/services/analysis_service.py`, API contract/safety tests.
   - Goal: public responses expose sanitized observation projection; raw/stored fields remain internal or versioned.

5. Frontend guest/report i18n cleanup
   - Scope: `apps/dsa-web/src/i18n/core.ts`, `apps/dsa-web/src/api/reportNormalizer.ts`, report/home tests.
   - Goal: default visible frontend copy no longer promises actionable entry/stop/target/position advice.

### P1

1. Backtest presentation relabel guard
   - Preserve rule parser/math/results. Relabel only UI/template text where historical simulation framing is insufficient.

2. Watchlist leveraged ETF mapper label cleanup
   - Preserve API field names; change labels to scenario reference/upside/risk marks.

3. Market review strategy prompt rewrite
   - Reframe market `Strategy Plan` as regime/risk observation; keep no personalized advice.

4. Strategy library prompt-source cleanup
   - If `strategies/*.yaml` are injected into LLM prompts, rewrite from action instructions to signal observation templates.

5. Docs alignment
   - Update `SKILL.md`, `docs/openclaw-skill-integration.md`, `docs/full-guide.md` after runtime/API decisions land.

### P2

1. CLI/local output relabel
   - `main.py`, `test_env.py`, local smoke scripts can follow after public surfaces are clean.

2. Broaden guard vocabulary
   - Centralize forbidden advice/action regex and reuse in API, component, and e2e guards.

3. Audit stale docs/fixtures
   - Keep unsafe test fixtures only when they assert sanitization; remove tests that assert unsafe output is present.

## Test And Guard Gaps

- Existing API safety guard in `tests/api/test_public_api_surface_safety.py` catches order/guarantee extremes (`buy now`, `place order`, `必买`, `下单`) but not the broader P0 inventory (`目标价`, `止损`, `仓位建议`, `理想买入点`, `operation_advice`).
- Existing notification tests currently assert unsafe labels are present (`tests/test_notification.py`, `tests/test_notification_sender.py`), so they must be changed in the same P0 notification batch.
- Existing frontend route e2e has some strong guards (`ai-research-entry-launch.spec.ts`) but coverage is uneven across report drawer/export/history/notification-like surfaces.
- `src/core/export_filter.py` and Home drawer/export tests are good defense-in-depth; follow-up should verify all public markdown/download/share/export paths use an equivalent sanitizer.

## No-Write / Boundary Confirmation

- Source/runtime/API/frontend/provider/cache/DB/config/package files were not modified by this audit.
- Only this optional audit document was added.
- No git staging, commit, push, merge, rebase, branch switch, or worktree creation was performed.
