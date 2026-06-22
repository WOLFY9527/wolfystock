# T-1213 Portfolio Risk Exposure Summary v1 audit

Task ID: T-1213

Task title: Portfolio Risk Exposure Summary v1 audit

Mode: READ-ONLY-AUDIT with one explicitly allowed docs artifact.

Allowed artifact:

`docs/codex/audits/T-1213-portfolio-risk-exposure-summary-audit.md`

Observed workspace:

- cwd: `C:\Users\leeyi\worktrees\t1213-portfolio-risk-exposure-summary-audit`
- branch: `codex/t1213-portfolio-risk-exposure-summary-audit`
- branch HEAD inspected before writing: `5b9567d45f03bef7c112e290f73784aff7e60b5e`
- latest observed `origin/main`: `5b9567d45f03bef7c112e290f73784aff7e60b5e`
- preflight state before writing: no staged files, no dirty tracked files, no ahead commits

Scope boundary:

- This audit inspected current Portfolio read models, API schemas/endpoints, frontend Portfolio types/UI, Portfolio research helpers, provider/source-confidence contracts, and Portfolio protected-domain rules.
- No source, config, package, API, schema, provider, cache, runtime, DB, migration, frontend, accounting, P&L, FX, cost-basis, broker sync, import, or provider files were changed.
- This report intentionally avoids rebalance recommendation, buy/sell/position-sizing, stop/target framing, personalized trading advice, or execution readiness.

## Audit verdict

Portfolio already has enough read-only inventory to build a small consumer-safe exposure summary from existing snapshot/risk/scenario fields, but it does not yet have authoritative portfolio-wide sector/theme/country/market-cap/factor/correlation metadata.

The smallest safe v1 should be a display-only "Risk Exposure Summary" that:

- reads existing Portfolio snapshot analytics and existing risk diagnostics only;
- summarizes current concentration, currency, market, account, and symbol exposure;
- optionally shows scenario shock observation from the existing caller-supplied `/api/v1/portfolio/scenario-risk` flow;
- treats sector/industry, factor/style, market-cap bucket, theme, country, and correlation cluster as missing, partial, or observation-only unless explicit future source-confidence and right-to-display gates are added;
- does not modify portfolio accounting, cash, holdings, P&L, FX conversion, cost basis, imports, sync, risk math, provider runtime, or API contracts.

## Current Portfolio inventory

### Core portfolio state and accounting surface

Current Portfolio API includes account management, broker connections, IBKR read-only sync, manual trade records, cash ledger, corporate actions, broker/CSV import parse and commit, FX read/refresh, snapshot, scenario-risk projection, and risk report routes in `api/v1/endpoints/portfolio.py:191`, `api/v1/endpoints/portfolio.py:342`, `api/v1/endpoints/portfolio.py:441`, `api/v1/endpoints/portfolio.py:476`, `api/v1/endpoints/portfolio.py:654`, `api/v1/endpoints/portfolio.py:751`, `api/v1/endpoints/portfolio.py:880`, `api/v1/endpoints/portfolio.py:1022`, `api/v1/endpoints/portfolio.py:854`, `api/v1/endpoints/portfolio.py:1043`, and `api/v1/endpoints/portfolio.py:1068`.

These are protected Portfolio domains. Future v1 work must consume their read models, not reinterpret or rewrite their semantics.

### Snapshot exposure and analytics

`PortfolioSnapshotResponse` exposes accounting-derived totals, market breakdown, FX rows, per-account snapshots, positions, analytics, risk diagnostics, evidence metadata, lineage states, and confidence cap in `api/v1/schemas/portfolio.py:381`.

Existing snapshot analytics include:

- exposure by account, currency, market, symbol, and a placeholder sector bucket: `api/v1/schemas/portfolio.py:355`.
- risk summary fields for largest position, largest currency, largest market, holding count, account count, cash percent, FX unavailable flag, and warnings: `api/v1/schemas/portfolio.py:364`.
- implementation of `by_currency`, `by_market`, `by_symbol`, largest exposure warnings, and `sector_status: unavailable` in `src/services/portfolio_service.py:4191`, `src/services/portfolio_service.py:4211`, `src/services/portfolio_service.py:4268`, `src/services/portfolio_service.py:4286`, `src/services/portfolio_service.py:4301`, `src/services/portfolio_service.py:4370`, and `src/services/portfolio_service.py:4409`.

Current authoritative snapshot exposure inventory:

| Capability | Current state | Authority posture |
| --- | --- | --- |
| Account exposure | Existing `analytics.exposure.by_account` | Safe read projection from current snapshot totals. |
| Currency exposure | Existing `analytics.exposure.by_currency` with FX status | Safe to summarize only with existing FX freshness/unavailable labels. |
| Market exposure | Existing `analytics.exposure.by_market` | Safe read projection from account/position market fields. |
| Symbol exposure | Existing `analytics.exposure.by_symbol` and largest position risk | Safe to summarize as concentration observation. |
| Sector exposure | Schema has `by_sector`, but implementation returns empty with `sector_status: unavailable` | Not authoritative in snapshot analytics today. |
| Cash percent | Existing `analytics.risk.cash_percent` | Safe as read projection; do not alter cash/accounting math. |

### Portfolio risk endpoint

`PortfolioRiskResponse` exposes thresholds, concentration, sector concentration, industry attribution, sector source provenance, drawdown, stop-loss proximity, account attribution, diagnostics, evidence, and confidence states in `api/v1/schemas/portfolio.py:513`.

`PortfolioRiskService.get_risk_report` computes:

- position concentration: `src/services/portfolio_risk_service.py:58` and `src/services/portfolio_risk_service.py:197`;
- sector concentration through CN board lookup: `src/services/portfolio_risk_service.py:63` and `src/services/portfolio_risk_service.py:237`;
- industry attribution: `src/services/portfolio_risk_service.py:68` and `src/services/portfolio_risk_service.py:270`;
- drawdown context: `src/services/portfolio_risk_service.py:77`, `src/services/portfolio_risk_service.py:83`, and `src/services/portfolio_risk_service.py:611`;
- stop-loss proximity block: `src/services/portfolio_risk_service.py:91` and `src/services/portfolio_risk_service.py:715`;
- account attribution: `src/services/portfolio_risk_service.py:92` and `src/services/portfolio_risk_service.py:670`;
- risk diagnostics: `src/services/portfolio_risk_diagnostics.py:533`.

Important non-invasive caveat:

- `_ensure_drawdown_snapshot_window` may call `get_portfolio_snapshot` for missing dates to build the drawdown window: `src/services/portfolio_risk_service.py:121`.
- Therefore, a strict non-invasive v1 should not introduce a new hidden dependency on `/portfolio/risk` if the current page does not already fetch it. If the existing Portfolio UI already has risk data in memory, v1 may summarize it; otherwise v1 should start with snapshot-only exposure and scenario-risk observation.

### Scenario shock observation

`POST /api/v1/portfolio/scenario-risk` is already a caller-supplied, account-free projection route. It deletes `current_user` after auth convention, does not instantiate `PortfolioService`, and calls only `PortfolioScenarioRiskService().build_projection`: `api/v1/endpoints/portfolio.py:1043` and `api/v1/endpoints/portfolio.py:1053`.

Contract tests assert:

- response type is `portfolio_scenario_risk_advisory_v1`;
- `advisoryOnly` is true;
- `executionReadiness` is `advisory_only_not_trade_execution`;
- no accounting mutation and no provider runtime are present;
- the endpoint does not invoke portfolio service, risk service, import service, broker sync, audit log, or FX service.

Evidence: `tests/api/test_portfolio_scenario_risk.py:132`, `tests/api/test_portfolio_scenario_risk.py:143`, `tests/api/test_portfolio_scenario_risk.py:146`, and `tests/api/test_portfolio_scenario_risk.py:227`.

Frontend scenario panel is collapsed by default, reads visible holdings, and sends only scenario payload fields. It explicitly tells users the projection does not refresh providers, broker state, or accounting: `apps/dsa-web/src/components/portfolio/PortfolioScenarioRiskPanel.tsx:172`, `apps/dsa-web/src/components/portfolio/PortfolioScenarioRiskPanel.tsx:231`, and `apps/dsa-web/src/components/portfolio/PortfolioScenarioRiskPanel.tsx:266`.

### Advisory research helpers

Portfolio already has pure/offline research helpers, but most are not current consumer API surfaces:

| Helper | Current capability | Safety posture |
| --- | --- | --- |
| `PortfolioFactorExposureService` | Builds weighted factor exposures from supplied factor observations | Advisory-only; no accounting mutation, broker integration, or trade execution in `src/services/portfolio_factor_exposure.py:47`. |
| `PortfolioRiskAttributionService` | Builds concentration, specific-risk, factor contribution, by-position/by-sector/by-industry/by-factor summaries | Advisory-only; no accounting mutation, broker integration, or trade execution in `src/services/portfolio_risk_attribution.py:106`. |
| `PortfolioStressRiskService` | Builds stress/VaR and drawdown estimate from supplied positions, shocks, and return samples | Advisory-only; no live prices, broker sync, accounting mutation, or runtime wiring in `src/services/portfolio_stress_risk.py:71`. |
| `PortfolioConstructionReadModelService` | Builds target-weight drift, suggested delta, and advisory construction rows | Excluded from T-1213 v1 because it is too close to rebalance/position-sizing language, even though it is advisory-only. |

Tests reinforce the advisory boundary for factor, attribution, stress, scenario, and construction helpers: `tests/test_portfolio_factor_exposure_read_model.py:62`, `tests/test_portfolio_risk_attribution_read_model.py:70`, `tests/test_portfolio_stress_risk_read_model.py:47`, `tests/test_portfolio_scenario_risk_read_model.py:61`, and `tests/test_portfolio_construction_read_model.py:48`.

The Portfolio Research smoke checklist explicitly says these helpers are advisory-only, safe only from caller-supplied fixture or snapshot-style inputs, and must not create/edit/delete/replay accounting records, trigger broker sync/import, place orders, run provider fetches, call API routes, or run frontend flows: `docs/portfolio/portfolio-research-smoke-checklist.md:39` and `docs/portfolio/portfolio-research-smoke-checklist.md:44`.

## Authoritative vs observation-only data

### Authoritative enough for current Portfolio read display

These can be summarized without changing accounting math, provided v1 treats them as already-computed read-model fields:

- account, position, quantity, currency, market, last price, cost basis, market value, unrealized P&L, realized P&L, fees, taxes, cash, FX status, and total equity from `PortfolioSnapshotResponse`;
- exposure percentages already emitted by `snapshot.analytics.exposure`;
- current largest position/currency/market/cash percent warnings already emitted by `snapshot.analytics.risk`;
- current scenario-risk projection output when the user explicitly runs the existing scenario panel.

These fields are authoritative only as current Portfolio read models. They are not authorization to recalculate P&L, FX, cost basis, holdings, or accounting.

### Observation-only / diagnostic-only

These must stay observation-only unless a later protected-domain task grants authority and tests it:

- sector/industry mapping from CN board lookup and `sectorSourceProvenance`;
- factor/style exposures from supplied factor observations;
- stress/VaR and scenario shock projections;
- source-confidence/provider capability metadata;
- confidence caps, source authority states, freshness states, limitation labels, and diagnostic reason codes;
- theme, country, market-cap bucket, and correlation cluster until explicit per-field source-confidence/right-to-display contracts exist.

Sector source provenance already marks itself `diagnosticOnly: True`, `observationOnly: True`, `authorityGrant: False`, `decisionGrade: False`, `externalProviderCallsAdded: False`, and `marketCacheMutation: False`: `src/services/portfolio_risk_service.py:526`.

Provider/source-confidence contract states that provider/source authority must never be inferred from provider name, source label, source type, freshness label, cache hit, successful response, high coverage, or low latency: `docs/data-reliability/provider-source-confidence-contract.md:29`.

## Field dependency map

| v1 field family | Existing source | Provider/source-confidence dependency | Safe v1 posture |
| --- | --- | --- | --- |
| Account exposure | `snapshot.analytics.exposure.by_account` | No new dependency | Consumer-safe summary. |
| Currency exposure | `snapshot.analytics.exposure.by_currency`, `fx_status`, `fx_rates` | FX freshness/source labels must stay bounded; provider names hidden | Consumer-safe summary with delayed/unavailable state. |
| Market exposure | `snapshot.analytics.exposure.by_market` | No new dependency beyond existing market field | Consumer-safe summary. |
| Symbol concentration | `snapshot.analytics.exposure.by_symbol`, `snapshot.analytics.risk.largest_position`, risk concentration if already fetched | No new provider dependency | Consumer-safe top concentration. |
| Sector/industry exposure | `/portfolio/risk` `sector_concentration`, `industry_attribution`, `sectorSourceProvenance` | Yes. CN board lookup provenance is diagnostic-only and non-CN is not applicable/unclassified | Collapsed/limited; do not label authoritative sector exposure. |
| Theme exposure | Existing scenario panel accepts caller-supplied `theme_proxy`; no authoritative portfolio theme map | Yes. Requires explicit taxonomy/source-confidence/right-to-display | Not in default v1; only scenario observation if user supplies label. |
| Country exposure | No current authoritative Portfolio country field | Yes | Defer. |
| Market-cap bucket | No current Portfolio market-cap bucket field; factor schema has neutralization axis `market_cap_bucket` but not Portfolio classification | Yes | Defer. |
| Factor/style exposure | `PortfolioFactorExposureService` from supplied observations; `factorMappingState` exists as diagnostic state | Yes | Admin/advanced observation only; not consumer default v1. |
| Correlation cluster | Factor schemas contain factor-correlation research structures, but no Portfolio cluster authority | Yes | Defer. |
| Drawdown context | `/portfolio/risk` drawdown; `PortfolioStressRiskService` drawdown estimate from supplied inputs | Existing risk route may backfill snapshots; stress helper is caller-supplied/offline | Use only if already present; otherwise defer from strict snapshot-only v1. |
| Scenario shock observation | `/portfolio/scenario-risk` caller-supplied endpoint and panel | No provider runtime; user-supplied mapping labels remain observation-only | Safe collapsed user-run observation. |
| Risk contribution | `PortfolioRiskAttributionService` from supplied weights/classifications/factors/risk metrics | Yes for classifications/factors/risk metrics | Defer consumer default; safe later as advisory-only if inputs are explicit. |

## Safe summary without touching accounting math

Safe v1 summary statements:

- "Top position concentration is X% of current market value."
- "Largest currency exposure is X%, with FX state shown as current/delayed/unavailable."
- "Largest market exposure is X%."
- "Cash is X% of current total equity."
- "Risk references are limited/partial/unavailable" when `factorMappingState`, `confidenceCap`, or evidence summaries require caution.
- "Scenario projection is observation-only and uses current visible holdings" when the user runs the existing scenario panel.

Unsafe v1 summary statements:

- "You should reduce/increase this position."
- "Rebalance into target weights."
- "Stop loss triggered; sell at..."
- "This sector/theme is authoritative" when based on board lookup, fallback, synthetic, partial, or missing metadata.
- "Provider X is reliable/better/live" based on source labels or freshness.
- "Risk contribution proves future loss" from advisory-only factor/stress/attribution helpers.

## Consumer vs admin display boundary

### Consumer default

Consumer v1 should show only:

- top 3 current exposure observations: largest position, largest currency, largest market/account;
- coarse status chips: `当前`, `可能延迟`, `部分缺失`, `仅供观察`, `风险参考受限`;
- one-line explanation when data is partial or unavailable;
- scenario shock observation only inside the existing collapsed panel or a collapsed summary row after user action;
- no raw provider/source/cache/debug/JSON/reason-code/backend field names.

This matches the consumer data-quality UX contract, which requires bounded status vocabulary and hides provider/source/freshness internals beyond user-safe timestamps: `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:43`, `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:136`, and `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:205`.

### Collapsed consumer detail

Collapsed detail may include:

- currency and market exposure rows;
- top symbol exposure rows;
- drawdown context if already loaded;
- scenario coverage warnings translated into consumer-safe language;
- data quality note saying sector/theme/factor/correlation context is not authoritative yet.

### Admin-only / backstage

Admin-gated views may show sanitized:

- source provenance summaries;
- coverage counts;
- reason-code counts;
- confidence cap values;
- source authority state;
- factor mapping state;
- diagnostic-only metadata;
- right-to-display review state when such a field exists.

Admin default must still exclude secrets, raw provider payloads, raw broker payloads, session IDs, credentials, and raw stack traces. Current admin Portfolio projections are explicitly read-only/safe and expose limitations such as raw broker payloads excluded and raw broker refs masked: `src/services/admin_portfolio_service.py:2`, `src/services/admin_portfolio_service.py:69`, `src/services/admin_portfolio_service.py:137`, and `api/v1/endpoints/admin_portfolio.py:86`.

## Protected-domain risk map

| Protected domain | T-1213 risk | Required guardrail |
| --- | --- | --- |
| Portfolio accounting/cash/holdings/P&L/FX/cost basis | Highest risk if v1 recalculates instead of reading existing snapshot fields | Consume existing read-model fields only; do not modify `src/services/portfolio_service.py`, `src/repositories/portfolio_repo.py`, schemas, DB, imports, sync, or FX conversion. |
| Portfolio risk calculations | Medium/high if v1 changes thresholds, drawdown, stop-loss, concentration, or sector lookup | Do not change `PortfolioRiskService`; render only existing response fields. |
| Provider runtime / MarketCache / fallback | High if v1 fetches classifications, market cap, themes, or factors live | No provider calls, no provider order changes, no cache TTL/SWR/key changes, no fallback relabeling. |
| Source-confidence/right-to-display | High if v1 turns metadata into trust badges or authority labels | Fail closed; consumer-safe copy only; raw authority fields admin-only. |
| API/schema contracts | High if v1 adds fields without compatibility review | First v1 slice should avoid backend/API/schema changes. |
| Frontend consumer UI | Medium if raw diagnostics leak | Use current Portfolio sanitizer/trust strip patterns; tests must assert no raw provider/source/debug/reason-code leakage. |
| Rebalance/trading advice | High product safety risk | Exclude construction/rebalance helper from v1; no buy/sell/reduce/increase/target/stop/position-sizing language. |

## Smallest non-invasive v1 slice

Recommended v1 scope:

1. Consumer Portfolio page adds a compact, collapsed-by-default "Risk Exposure Summary" block.
2. The block reads only existing in-memory Portfolio snapshot analytics and existing scenario-risk result state.
3. It shows:
   - largest position concentration;
   - largest currency exposure;
   - largest market exposure;
   - cash percent;
   - FX/factor/source confidence posture as coarse trust copy;
   - optional last user-run scenario shock impact as observation-only.
4. It hides/defer:
   - sector/theme/country/market-cap/factor/correlation sections unless data is already present and explicitly observation-only;
   - all raw provider/source-confidence/provenance/reason-code/admin fields;
   - all rebalance, buy/sell, position-sizing, stop/target wording.

Do not include in v1:

- new backend endpoint;
- new schema fields;
- new provider capability or source-confidence authority grant;
- PortfolioRiskService changes;
- PortfolioService accounting/FX/cost changes;
- DB migration;
- new runtime provider calls;
- construction/rebalance target-weight output.

## First safe execution task

Task: Add a frontend-only Portfolio Risk Exposure Summary v1 panel from existing Portfolio snapshot state.

Allowed files:

- `apps/dsa-web/src/pages/PortfolioPage.tsx`
- `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx`
- `apps/dsa-web/src/components/portfolio/PortfolioTrustStrip.tsx` only if existing trust chips need reuse wiring, not new raw badge semantics
- `apps/dsa-web/src/components/portfolio/__tests__/PortfolioScenarioRiskPanel.test.tsx` only if scenario-risk summary test coverage needs a focused assertion
- `apps/dsa-web/e2e/portfolio-launch-surface.spec.ts` only if the task explicitly asks for browser proof

Forbidden files:

- `api/v1/schemas/portfolio.py`
- `api/v1/endpoints/portfolio.py`
- `src/services/portfolio_service.py`
- `src/services/portfolio_risk_service.py`
- `src/services/portfolio_risk_diagnostics.py`
- `src/services/portfolio_scenario_risk.py`
- `src/services/portfolio_stress_risk.py`
- `src/services/portfolio_factor_exposure.py`
- `src/services/portfolio_risk_attribution.py`
- `src/services/portfolio_construction_service.py`
- `src/repositories/portfolio_repo.py`
- provider/runtime/cache files
- DB/migration files
- package/lock/config files
- docs/CHANGELOG.md unless the future task intentionally ships user-visible behavior and the repo rules require it

Acceptance criteria:

- No backend, API, schema, provider, cache, runtime, DB, accounting, FX, P&L, cost-basis, import, sync, or risk calculation files changed.
- Default consumer UI shows only bounded exposure observations and safe data quality copy.
- Raw provider/source/cache/debug/reason-code/backend field names do not appear in the default Portfolio DOM.
- Scenario shock summary, if shown, is observation-only and preserves no broker sync, no accounting mutation, no order placement, and not investment advice copy.
- No rebalance, buy/sell, position sizing, stop/target, or execution readiness wording appears.

Recommended validation for that future task:

```bash
npm --prefix apps/dsa-web run test -- --no-file-parallelism "src/pages/__tests__/PortfolioPage.test.tsx" "src/components/portfolio/__tests__/PortfolioScenarioRiskPanel.test.tsx"
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run check:design
git diff --check
./scripts/release_secret_scan.sh
```

Run the e2e Portfolio launch surface only if the future task changes route layout materially or explicitly requests browser evidence.

## Answers to audit questions

1. Current capabilities already exist for account/currency/market/symbol exposure, concentration, CN sector/industry observation, drawdown context, stop-loss proximity, account attribution, diagnostics/evidence, scenario shock observation, factor exposure helper, stress/VaR helper, and risk attribution helper.
2. Authoritative data is the existing Portfolio snapshot/read model for current holdings/accounting-derived values. Sector/factor/stress/scenario/source-confidence data is observation-only unless separately authorized.
3. Provider/source-confidence dependent fields are sector/industry provenance, theme, country, market-cap bucket, factor/style exposure, correlation cluster, provider/freshness/confidence labels, right-to-display posture, and any consumer trust badge derived from them.
4. Safe summaries are current exposure, concentration, cash percent, coarse FX/freshness posture, and observation-only scenario impact. Unsafe summaries are rebalance, buy/sell, sizing, stop/target, provider authority, or accounting reinterpretation.
5. Consumer should get bounded summary and collapsed safe notes. Admin may get gated sanitized provenance, coverage, confidence, and reason-code diagnostics, but never raw payloads or secrets.
6. The smallest v1 is frontend-only, snapshot-only, collapsed-by-default, and uses existing Portfolio data already loaded by the page.

## Audit status

- Report-only artifact created: yes.
- Source/runtime/frontend/schema/API/config changes: none.
- Recommended next write: frontend-only consumer panel from existing snapshot state, with tests.
- Backend/API/type implementation: defer.
- Portfolio accounting/P&L/FX/cost-basis changes: forbidden and not required.
