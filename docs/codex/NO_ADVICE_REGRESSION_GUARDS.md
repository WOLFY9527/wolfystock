# No-Advice Regression Guards

Status: task-runner index for existing no-advice, export, API, frontend, and
provider-leak guards. This is an index only; it does not define product
behavior.

Use this when a task touches consumer-safe wording, report/export text,
no-advice disclosure, observation-only copy, provider/source diagnostics, or
raw/internal payload projection.

## Fast Path

1. Pick the impacted surface below.
2. Run the focused tests for that surface.
3. Run the grep commands in this file against changed runtime/UI files.
4. Classify every hit as `blocker`, `allowed-admin`, `allowed-fixture`, or
   `allowed-internal-legacy` with a short justification.

Do not "fix" a grep hit by deleting adversarial fixture strings that are paired
with negative assertions.

## Existing Guard Tests

Report, drawer, and markdown export:

- `apps/dsa-web/src/utils/__tests__/homeReportIdentityNoAdvice.test.ts`
  guards `buildInstitutionalReportMarkdown` sanitization and raw field
  suppression.
- `apps/dsa-web/src/components/home-bento/__tests__/FullDecisionReportDrawerNoAdvice.test.tsx`
  guards drawer DOM, clipboard copy, and markdown download export.
- `apps/dsa-web/src/components/report/__tests__/StandardReportPanel.test.tsx`
  guards legacy action labels on the consumer report surface.
- `apps/dsa-web/src/components/report/__tests__/ReportMarkdown.test.tsx`
  guards report markdown rendering and collapsed technical evidence.

Frontend consumer route/default DOM guards:

- `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx`
  guards Home no-advice copy and evidence/citation adjuncts.
- `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx`
  guards Scanner default consumer surfaces against raw diagnostics.
- `apps/dsa-web/src/pages/__tests__/WatchlistPage.test.tsx`
  guards default Watchlist copy against backend diagnostics and remediation
  leakage.
- `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx`
  guards valuation lineage and raw provider fields in the consumer DOM.
- `apps/dsa-web/src/pages/__tests__/MarketOverviewPage.test.tsx`
  guards market decision/no-advice wording and raw evidence metadata exposure.
- `apps/dsa-web/src/pages/__tests__/MarketRotationRadarPage.test.tsx`
  guards rotation radar no-trade language, provider/source metadata, and raw
  diagnostics.
- `apps/dsa-web/src/pages/__tests__/LiquidityMonitorPage.test.tsx`
  guards liquidity data-quality wording and provider/source leakage.
- `apps/dsa-web/src/components/backtest/__tests__/BacktestResultReport.test.tsx`
  guards observe-only backtest report wording and raw support evidence leakage.
- `apps/dsa-web/src/components/portfolio/__tests__/PortfolioScenarioRiskPanel.test.tsx`
  guards scenario-risk warnings and advisory-only metadata.

Frontend API/projection guards:

- `apps/dsa-web/src/api/__tests__/stockEvidence.test.ts`
  guards consumer-safe fundamentals summary projection.
- `apps/dsa-web/src/api/__tests__/portfolio.test.ts`
  guards scenario-risk API normalization and execution-field suppression.
- `apps/dsa-web/src/api/__tests__/market.test.ts`
  guards fallback/demo wording rewrite and market decision semantics.
- `apps/dsa-web/src/api/__tests__/marketRotation.test.ts`
  guards rotation radar API normalization and raw provider detail suppression.
- `apps/dsa-web/src/api/__tests__/liquidityMonitor.test.ts`
  guards liquidity evidence boundary metadata normalization.
- `apps/dsa-web/src/api/__tests__/watchlist.test.ts`
  guards watchlist catalyst exposure sanitization.
- `apps/dsa-web/src/api/__tests__/consumerDataQualityViewModel.test.ts`
  guards bounded product-safe states and admin diagnostic suppression.
- `apps/dsa-web/src/utils/__tests__/evidenceDisplay.test.ts`
  guards default consumer evidence labels against raw enum/reason leakage.

Browser smoke guards:

- `apps/dsa-web/e2e/consumer-copy-regression.smoke.spec.ts`
  guards Home, Scanner, Liquidity, Watchlist, Portfolio, and Options consumer
  copy.
- `apps/dsa-web/e2e/consumer-copy-forbidden-vocabulary.smoke.spec.ts`
  guards consumer routes against backend/provider/debug vocabulary.
- `apps/dsa-web/e2e/home-scanner-evidence-browser.smoke.spec.ts`
  guards Home and Scanner evidence strips against raw/provider leakage.
- `apps/dsa-web/e2e/secondary-consumer-copy.smoke.spec.ts`
  guards secondary consumer routes and degraded/empty states.
- `apps/dsa-web/e2e/public-safety-ai-scanner-options.smoke.spec.ts`
  guards public Scanner/Options no-advice and no-trade surfaces.

Backend/API contract guards:

- `tests/api/test_options_lab.py`
  guards Options API no-recommendation and no raw provider language.
- `tests/api/test_public_api_surface_safety.py`
  guards public API launch surfaces against order/trade/advice language.
- `tests/api/test_analysis.py`
  guards Home evidence packet no-advice boundary and raw/internal suppression.
- `tests/api/test_market_temperature.py`
  guards market evidence/actionability no-advice boundaries.
- `tests/api/test_scanner.py`
  guards scanner `consumerActionBoundary: no_advice` contracts.
- `tests/test_market_rotation_radar_service.py`
  guards rotation radar payload no-advice wording.
- `tests/test_backtest_golden_contracts.py`
  guards backtest/factor-lab packets against recommendation language.
- `tests/test_portfolio_construction_read_model.py`
  guards portfolio construction read-model no-trade boundaries.
- `tests/test_investor_signal_model.py`
  guards consumer-safe investor signal output against raw provider/admin fields.

Adjacent artifact/export leak checkers:

- `scripts/staging_ingress_operator_evidence_check.py`
- `scripts/ws2_sse_operator_decision_check.py`
- `scripts/quota_operator_evidence_check.py`

## Focused Test Commands

Report/export and frontend projection:

```bash
npm --prefix apps/dsa-web run test -- \
  src/utils/__tests__/homeReportIdentityNoAdvice.test.ts \
  src/components/home-bento/__tests__/FullDecisionReportDrawerNoAdvice.test.tsx \
  src/components/report/__tests__/StandardReportPanel.test.tsx \
  src/api/__tests__/stockEvidence.test.ts \
  src/utils/__tests__/evidenceDisplay.test.ts
```

Consumer route/browser copy:

```bash
npm --prefix apps/dsa-web run test:e2e -- \
  e2e/consumer-copy-regression.smoke.spec.ts \
  e2e/consumer-copy-forbidden-vocabulary.smoke.spec.ts \
  e2e/home-scanner-evidence-browser.smoke.spec.ts \
  e2e/secondary-consumer-copy.smoke.spec.ts \
  e2e/public-safety-ai-scanner-options.smoke.spec.ts
```

Backend/API no-advice contracts:

```bash
python -m pytest -q \
  tests/api/test_options_lab.py \
  tests/api/test_public_api_surface_safety.py \
  tests/api/test_analysis.py \
  tests/api/test_market_temperature.py \
  tests/api/test_scanner.py \
  tests/test_market_rotation_radar_service.py \
  tests/test_backtest_golden_contracts.py \
  tests/test_portfolio_construction_read_model.py \
  tests/test_investor_signal_model.py
```

## Canonical Grep Commands

Chinese advice/trade terms in runtime/UI surfaces:

```bash
rg -n --pcre2 '建议(买入|卖出|加仓|减仓|持有)|买入|卖出|下单|立即交易|立即买入|交易建议|投资建议|止损|止盈|目标价|目标位|目标区间|仓位建议|必买|稳赚|保证收益' \
  apps/dsa-web/src api src data_provider \
  --glob '!**/__tests__/**' \
  --glob '!**/*.test.*' \
  --glob '!**/*.spec.*'
```

English advice/trade terms in runtime/UI surfaces:

```bash
rg -n --pcre2 -i '\b(buy now|sell now|place order|submit order|trade recommendation|trading advice|investment advice|recommended trade|strategy recommendation|ai recommends you buy|best contract|guaranteed return|guaranteed|take profit|stop loss|target price|position sizing|live trading|execution ready)\b' \
  apps/dsa-web/src api src data_provider \
  --glob '!**/__tests__/**' \
  --glob '!**/*.test.*' \
  --glob '!**/*.spec.*'
```

Raw diagnostic/provider/source terms in runtime/UI surfaces:

```bash
rg -n --pcre2 -i 'sourceAuthorityAllowed|scoreContributionAllowed|observationOnly|reasonCodes?|reasonFamilies|sourceRefId|source_confidence|provider(State|Trace|Diagnostics|Route|Payload)?|raw[_ -]?(payload|diagnostics|result|ai_response)|context_snapshot|debug|trace|schemaVersion|MarketCache|fallback_static|synthetic_fixture|official_public|authorized_licensed_feed|public_proxy|unofficial_proxy|provider_timeout|provider_runtime|backend snake_case' \
  apps/dsa-web/src api src data_provider \
  --glob '!**/__tests__/**' \
  --glob '!**/*.test.*' \
  --glob '!**/*.spec.*'
```

Guard-discovery grep for future tasks:

```bash
rg -n --pcre2 -i 'no[-_ ]?advice|notInvestmentAdvice|noAdviceBoundary|noTradingRecommendation|consumerActionBoundary|forbidden(Consumer|Trading|Diagnostic|Vocabulary)|不构成(投资建议|交易指令)|仅供观察|只读情景分析' \
  apps/dsa-web/src apps/dsa-web/e2e tests
```

## False-Positive Handling

- Admin-only diagnostics are allowed only when the route/surface is explicitly
  admin/backstage and the task records that the same term is absent from
  default consumer UI.
- Test fixtures may contain forbidden terms only as adversarial input paired
  with a negative assertion proving the term does not render/export.
- Internal legacy payload fields may remain only when a projection/sanitizer
  test proves the consumer output is bounded and safe.
- Existing docs may mention forbidden terms to define boundaries. Do not treat
  docs-only policy text as runtime leakage, but cite the relevant section when
  marking it allowed.
- Unjustified hits in runtime/UI source, exports, public API payloads, or
  default-visible consumer DOM are blockers for no-advice tasks.
