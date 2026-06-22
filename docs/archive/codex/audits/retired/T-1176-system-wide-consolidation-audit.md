# T-1176 System-wide consolidation and dead-code audit

Task ID: T-1176
Task title: System-wide consolidation and dead-code audit
Ledger status: REPORT READY; commit and push handled by Codex closeout
Branch: codex/t1176-system-wide-consolidation-audit
Workspace: /Users/yehengli/worktrees/t1176-system-wide-consolidation-audit
Base commit audited: dc2af89e02975d27dc8fb92d98e7b54101942e32
Audit date: 2026-06-08

## 1. Repo health score

Score: 72 / 100.

Rationale:

- Strong validation baseline: `npm --prefix apps/dsa-web run lint`, `npm --prefix apps/dsa-web run build`, `git diff --check`, and `./scripts/release_secret_scan.sh` passed during this audit.
- Strong protected-domain documentation exists and is current enough to prevent unsafe cleanup: scanner/backtest/portfolio/provider/cache/API/auth/AI/notification/storage boundaries are explicit in `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md` and `docs/data-reliability/provider-source-confidence-contract.md`.
- Main drag on health is not obvious broken code. It is accumulated surface area: very large backend services, duplicated source-confidence projection helpers, duplicated consumer-safe copy mapping, overlapping test directories, stale docs links, and incomplete unused-code tooling.
- The repo has real low-risk cleanup candidates, but most high-value cleanup touches protected runtime semantics and needs scoped follow-up audits.

## Evidence base

Required docs read:

- `AGENTS.md`
- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `docs/data-reliability/provider-source-confidence-contract.md`
- `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`

Subagents used:

- Backend auditor: completed; focused on `api`, `src/services`, repositories, schemas, bot/provider paths.
- Frontend auditor: completed; focused on routes, pages, components, hooks, utils, tests.
- Data/provider auditor: completed; focused on provider seams, fallback/proxy/cache/readiness.
- Test/CI auditor: completed; focused on pytest, Vitest, Playwright, CI, stale/overlapping tests.
- Scripts/docs/assets auditor: completed; focused on orphan scripts, stale docs, unused assets.
- Dependency/import auditor: completed; findings were cross-checked with local `rg` scans and folded into dependency/import hygiene below.
- Risk reviewer: completed; classified safe cleanup vs protected/high-risk domains.
- Recorder: spawned for final checklist review; coordinator writes this file.

Static scans and validation run:

- `git status --short --branch`
- `git rev-parse HEAD origin/main`
- TypeScript static import scan over `apps/dsa-web/src`
- Python AST import scan over runtime Python files
- repo file count by major area
- largest-file scan with `wc -l`
- route map inspection in `apps/dsa-web/src/App.tsx`
- API router inspection in `api/v1/router.py`
- repeated `rg` reference scans for assets, docs links, scripts, provider/admin endpoints, bot handlers, and consumer data-quality vocabulary
- `npm --prefix apps/dsa-web run lint`
- `npm --prefix apps/dsa-web run build`
- `git diff --check`
- `./scripts/release_secret_scan.sh`

## 2. Top 20 cleanup opportunities ranked by value/risk

| Rank | Opportunity | Value | Risk | Evidence | Recommended batch |
| --- | --- | --- | --- | --- | --- |
| 1 | Consolidate consumer data-quality/source-authority vocabulary across Home, Scanner, Watchlist, Market/Liquidity/Options/Backtest surfaces | High | High, protected UI/source-confidence | Consumer UX forbids raw default vocabulary (`docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:57`); current code still contains `来源确认`, `评分级`, `观察级`, `回退/代理`, `source_authority_missing`, `score_rights_missing` in `HomeBentoDashboardPage.tsx`, `ScannerCandidateEvidenceStrip.tsx`, `ScannerCandidatePresenters.tsx`, `ScannerCandidateResearchSummary.tsx`, `WatchlistPage.tsx`, `MarketOverviewWorkbenchTopSurface.tsx`, `OptionsReadinessGateSummary.tsx` | Batch C/E |
| 2 | Decommission unused `MarketIntelligenceActionabilityStrip` component | Medium | Medium; market/source-confidence semantics | Static import scan listed `apps/dsa-web/src/components/market/MarketIntelligenceActionabilityStrip.tsx` as unimported by non-test runtime. `rg` finds only the component and tests/e2e asserting `market-intelligence-actionability-strip` is absent | Batch C |
| 3 | Merge/retire duplicate frontend test directory lanes | Medium | Medium; Options/Backtest protected behavior | Duplicate test filenames in both `src/pages/tests` and `src/pages/__tests__`: `OptionsLabPage.test.tsx`, `DeterministicBacktestResultPage.test.tsx`; duplicate `BacktestResultReport.test.tsx` under `tests` and `__tests__` | Batch B |
| 4 | Fix stale docs links to moved architecture/design archive paths | Medium | Low | `docs/architecture/postgresql-baseline-design.md` links missing `docs/architecture/multi-user-foundation-phase2.md` and `phase3.md`; `docs/ARCHIVE_INDEX.md` points to `docs/architecture/archive/multi-user-foundation/...`; `docs/frontend/README.md` references missing `docs/design/archive/` | Batch B |
| 5 | Update scripts index for new provider activation probes | Medium | Low | `scripts/README.md` documents only `diagnose_official_macro_activation.py` and `diagnose_rotation_alpaca_activation.py`; repo also has `diagnose_fed_liquidity_activation.py`, `diagnose_polygon_us_breadth_activation.py`, `diagnose_usd_pressure_activation.py`, `diagnose_polygon_market_overview_activation.py` | Batch B |
| 6 | Clean unused public/archive image assets after external URL check | Medium | Low/medium | `apps/dsa-web/index.html` and `BrandedLoadingScreen` use `/wolfystock-logo-mark.png`; `image.png` is only historical changelog text; `wolfystock-logo-mark.svg` has no runtime refs; `docs/assets/archive/bot/img_2.png` has no repo refs | Batch A |
| 7 | Bot webhook adapter cleanup: Discord and stale wrapper claims | Medium | Medium; notification routing/external webhook risk | `bot/platforms/__init__.py` registers only `DingtalkPlatform`; `bot/platforms/discord.py` defines `DiscordPlatform` with TODO signature verification returning `True`; no repo refs to `DiscordPlatform`; `bot/handler.py` has Feishu/WeCom/Telegram wrapper functions but `ALL_PLATFORMS` only supports DingTalk webhook | Batch D |
| 8 | Provider priority documentation drift | Medium | High if runtime touched; low docs-only | `data_provider/__init__.py` and `requirements.txt` still emphasize CN provider priority; `DataFetcherManager` now has lazy Alpaca/Twelve Data/TickFlow enrichment paths in `data_provider/base.py:506`, `:542` | Batch B/E |
| 9 | Admin Provider Operations dual-read surface consolidation | Medium | High, provider/admin API | `MarketProviderOperationsPage.tsx` consumes both `/api/v1/admin/market-providers/operations` and `/api/v1/admin/providers/operations-matrix`; backend routes are separate in `api/v1/endpoints/market_provider_operations.py` and `admin_provider_operations_matrix.py` | Batch E |
| 10 | Provider-fit-advisor endpoint consumer audit | Medium | High, provider/runtime/readiness | `api/v1/endpoints/market.py` exposes `/provider-fit-advisor`; local searches show backend tests/docs but no clear frontend runtime consumer | Batch E |
| 11 | Source provenance sidecar helper consolidation | High | High, protected source-confidence | Repeated `_mapping`, `_sequence`, `_text`, `_bool`, `_DEGRADED_FRESHNESS`, source-provenance mapping across `market_intelligence_evidence.py`, `ai_evidence_adapters.py`, `provider_evidence_snapshot.py`, `market_scanner_context_adapter.py`, `*_source_provenance_sidecar.py` | Batch E |
| 12 | Break up backend mega-services after behavior-locked audits | High | Very high | Largest files include `src/services/rule_backtest_service.py` 10825 lines, `src/storage.py` 10544, `src/services/market_overview_service.py` 10130, `src/services/market_scanner_service.py` 7414 | Batch E |
| 13 | Break up frontend mega-pages with no behavior change | Medium | Medium | Largest frontend files include `HomeBentoDashboardPage.tsx` 6236, `i18n/core.ts` 6048, `PortfolioPage.tsx` 3954, `UserScannerPage.tsx` 3752, `SettingsPage.tsx` 3556 | Batch C |
| 14 | Web CI coverage alignment | High | Medium, CI config | Repo has 428 pytest files, 111 Vitest files, 40 Playwright specs. `.github/workflows/ci.yml` web-gate runs lint/build, a small raw-i18n Vitest slice, then Playwright, not full Vitest | Batch E |
| 15 | Network smoke marker truth | Medium | Medium, CI config | `setup.cfg` defines `network` marker; `rg` found 0 `@pytest.mark.network` usages; `network-smoke.yml` already treats empty collect as error | Batch E |
| 16 | Desktop validation gap | Medium | Medium, CI config | `apps/dsa-desktop/package.json` only has `dev` and `build`; CI frontend path filter only watches `apps/dsa-web/**` | Batch E |
| 17 | `test:smoke` local side-effect documentation | Low | Low/medium | `apps/dsa-web/scripts/run-smoke.sh` kills listener on port 4173 before launching preview | Batch B |
| 18 | Test-only/frontend contract residue audit | Low | High if portfolio/source-confidence touched | `apps/dsa-web/src/types/portfolio.contract.ts` is unimported by runtime; `apps/dsa-web/src/api/consumerDataQualityViewModel.ts` is test-only by repo `rg`; both are contract-adjacent | Batch E |
| 19 | Dependency hygiene audit for likely unused frontend deps and missing explicit Python deps | Medium | Medium/high, package/lockfile | `@remixicon/react` and `recharts` are declared; `rg` found no runtime source imports, only a `recharts` test mock. Python code directly imports `pydantic`, `websockets`, and `dateutil`, but `requirements.txt` does not explicitly declare them | Batch E |
| 20 | MarketOverview circular import and archive/backlog truth cleanup | Medium | Medium/high for Market Overview; low docs-only for backlog | `MarketOverviewWorkbenchTopSurface.tsx` lazy-imports `MarketOverviewDecisionDebugDetails.tsx`, while debug details imports types from the top surface. Risk review also found stale docs/backlog references to already-moved/removed paths | Batch C/E |

## 3. Safe-delete candidates with evidence and required validation

No code file should be deleted in this goal. The table below is a roadmap only.

| Candidate | Confidence | Evidence | Required validation before deletion | Notes |
| --- | --- | --- | --- | --- |
| `docs/assets/archive/bot/img_2.png` | High | `find apps/dsa-web/public docs/assets -type f` lists it; `rg` found no repo references | `rg -n "img_2\\.png|docs/assets/archive/bot/img_2\\.png" .`; docs link check; confirm archive policy | Lowest-risk delete candidate |
| `apps/dsa-web/public/wolfystock-logo-mark.svg` | High static, medium product | Runtime and tests use `/wolfystock-logo-mark.png`; `rg` found no `.svg` references | `rg -n "wolfystock-logo-mark\\.svg" .`; `npm --prefix apps/dsa-web run build`; favicon/logo browser smoke | Public URL may have external consumers; check release notes or deployed references first |
| `apps/dsa-web/public/image.png` | Medium | Current `index.html`, `BrandLogo`, and `BrandedLoadingScreen` use `/wolfystock-logo-mark.png`; only repo hit for `/image.png` is historical `docs/CHANGELOG.md` text | `rg -n "image\\.png|/image\\.png" .`; `npm --prefix apps/dsa-web run build`; visual smoke for boot loader and favicon | Public URL/external docs caveat |
| `apps/dsa-web/src/components/market/MarketIntelligenceActionabilityStrip.tsx` | Medium/high | Static import scan marks it unimported by non-test runtime; `rg` finds no imports, only e2e/unit assertions that `market-intelligence-actionability-strip` is absent | Delete in a frontend cleanup task; `rg -n "MarketIntelligenceActionabilityStrip|market-intelligence-actionability-strip"` should show only intended test removals; run `MarketOverviewPage` tests, relevant e2e, lint, build | Source-confidence UI vocabulary is protected; deletion is safer than resurrecting it |
| `apps/dsa-web/src/pages/tests/OptionsLabPage.test.tsx` | Medium | 55-line source-string sentinel overlaps with 2281-line behavior suite in `src/pages/__tests__/OptionsLabPage.test.tsx` | First prove no unique assertion remains; run both Options suites before and after; no runtime changes | Options copy/gates are protected; remove only as test-suite consolidation |
| `bot/platforms/discord.py` | Medium | `DiscordPlatform` has no repo refs; not registered in `ALL_PLATFORMS`; signature verification TODO returns `True` | External webhook/docs check; confirm no deployment imports by string; run bot tests/py compile | Do not delete active `src/notification_sender/discord_sender.py`; notification routing is protected |
| `apps/dsa-web/src/types/portfolio.contract.ts` | High static, high business risk | Static import scan marks it unimported by runtime; docs already identify portfolio contract/accounting as protected | Confirm no external generator/docs process reads it; run portfolio type/tests if removed | Conditional only; portfolio accounting/risk contract cleanup must be separately scoped |
| `apps/dsa-web/src/api/consumerDataQualityViewModel.ts` and its test | High static, medium/high product risk | Repo `rg` finds only `consumerDataQualityViewModel.test.ts` imports; no runtime page imports | Confirm no pending route wiring; remove implementation and test together; run source-confidence/consumer-copy route tests | Test-only source-confidence projection; do not replace with raw UI copy |

## 4. Merge/consolidation candidates and target owner modules

| Candidate | Current split | Target owner | Risk | Required proof |
| --- | --- | --- | --- | --- |
| Consumer data-quality projection | Home, Scanner, Watchlist, Market, Liquidity, Options, Backtest each maps source/freshness/authority terms separately | New or existing frontend helper that emits consumer-safe product-state vocabulary only | High | Consumer UX contract tests; route-level Vitest/e2e; no raw provider/source/reason vocabulary on consumer routes |
| Source provenance sidecars | `home_source_provenance_sidecar.py`, `market_scanner_source_provenance_sidecar.py`, `liquidity_source_provenance_sidecar.py`, `rotation_source_provenance_sidecar.py`, `options_source_provenance_sidecar.py`, `market_intelligence_source_provenance_sidecar.py` | `src/services/source_provenance_contract.py` plus narrow pure helpers | High | Contract golden tests for every sidecar; no API shape change; no authority inference |
| Freshness/degraded constants | `_DEGRADED_FRESHNESS` and equivalent checks in market intelligence/readiness modules | A protected inert constants module only if docs/tests allow | High | Provider-source-confidence audit; tests for live/fallback/stale labels |
| Admin provider operations UI | `MarketProviderOperationsService`, `ProviderOperationsMatrixService`, one frontend page with two admin endpoints | Keep as two backend contracts unless a provider-ops API design task scopes consolidation | High | Admin RBAC tests; API compatibility; provider runtime no-call proof |
| Bot webhook docs/adapters | `bot/handler.py` wrapper functions, `bot/platforms/__init__.py`, `bot/platforms/discord.py`, bot docs | `bot/platforms/__init__.py` as single webhook registry truth; docs reflect stream vs webhook support | Medium | External route/deploy check; notification dry-run tests; no active sender removal |
| Frontend duplicated tests | `src/pages/tests/**` and `src/pages/__tests__/**`, `components/backtest/tests/**` and `__tests__/**` | Existing `__tests__` suites | Medium | Move unique assertions into owner suite; run focused Vitest |
| Frontend page decomposition | `HomeBentoDashboardPage.tsx`, `UserScannerPage.tsx`, `SettingsPage.tsx`, `PortfolioPage.tsx` | Route-local component folders, existing primitives | Medium/high | Visual/browser proof, no API/behavior changes |
| Backend mega-service decomposition | `rule_backtest_service.py`, `market_overview_service.py`, `market_scanner_service.py`, `src/storage.py` | Domain submodules behind existing public methods | Very high | Golden tests for math/order/API payloads; protected-domain owner review |

## 5. Duplicate abstraction table

| Duplicate abstraction | Files | Why it matters | Classification |
| --- | --- | --- | --- |
| Consumer source-authority vocabulary mapping | `HomeBentoDashboardPage.tsx`, `ScannerCandidateEvidenceStrip.tsx`, `ScannerCandidatePresenters.tsx`, `ScannerCandidateResearchSummary.tsx`, `WatchlistPage.tsx`, `MarketOverviewWorkbenchTopSurface.tsx`, `OptionsReadinessGateSummary.tsx` | Same internal concepts are translated differently and sometimes exposed on consumer routes | Protected frontend consolidation |
| Source provenance normalization helpers | `*_source_provenance_sidecar.py`, `source_provenance_contract.py`, `market_intelligence_evidence.py`, `provider_evidence_snapshot.py` | Repeated classification/freshness/authority logic invites drift | Protected backend consolidation |
| `_mapping`, `_sequence`, `_text`, `_bool` coercion helpers | `market_intelligence_evidence.py`, `ai_evidence_adapters.py`, `provider_evidence_snapshot.py`, `market_scanner_context_adapter.py`, `backend_metrics_snapshot_service.py`, several contracts modules | Low-level helper duplication is visible, but unifying can accidentally alter payload normalization | Audit-required |
| Degraded freshness sets | `market_intelligence_evidence.py`, readiness/actionability modules | Determines stale/fallback/live interpretation | Protected |
| Consumer data-quality view-model seams | `consumerDataQualityViewModel.ts`, page-local `buildConsumerDataQualityNotice` in `MarketOverviewWorkbenchTopSurface.tsx`, Home/Scanner/Watchlist local mappers | Some projection exists only in tests while production pages keep local variants | Protected frontend consolidation |
| Admin provider readiness models | `MarketProviderOperationsService` and `ProviderOperationsMatrixService` | Same page consumes operations logs/cache and provider readiness/capability matrix | Protected API/admin consolidation |
| Backtest report evidence checklist paths | `BacktestResultReport` duplicate tests in two folders | Unique compare evidence assertions are split from owner suite | Merge tests |
| Options no-advice/copy locks | `pages/tests/OptionsLabPage.test.tsx` and `pages/__tests__/OptionsLabPage.test.tsx` | Source-string sentinel duplicates behavior suite | Merge/delete after proof |
| Data provider priority docs | `data_provider/__init__.py`, `requirements.txt`, `docs/full-guide.md`, `DataFetcherManager` comments | Docs do not fully reflect lazy Alpaca/Twelve Data/TickFlow enrichment | Docs-only truth update |

## 6. Stale/overlapping test table

| Test area | Candidate files | Evidence | Recommendation | Validation |
| --- | --- | --- | --- | --- |
| Options Lab tests | `apps/dsa-web/src/pages/tests/OptionsLabPage.test.tsx`; `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx` | Duplicate filename; 55 lines vs 2281 lines; smaller test reads source strings | Move any unique sentinel assertion into owner suite, then delete smaller file | `npm --prefix apps/dsa-web run test -- --run src/pages/__tests__/OptionsLabPage.test.tsx src/pages/tests/OptionsLabPage.test.tsx` before; owner suite after |
| Deterministic Backtest result tests | `src/pages/tests/DeterministicBacktestResultPage.test.tsx`; `src/pages/__tests__/DeterministicBacktestResultPage.test.tsx` | Smaller test appears to retain compare-evidence injection assertion | Merge unique assertion into owner suite | Focused Vitest for both result suites |
| Backtest report tests | `src/components/backtest/tests/BacktestResultReport.test.tsx`; `src/components/backtest/__tests__/BacktestResultReport.test.tsx` | Smaller suite has `parameterStabilityEvidence` checklist assertion not fully present in larger suite | Merge unique branch, then delete duplicate lane | Focused Vitest for both report suites |
| Provider usage ledger tests | `tests/test_provider_usage_ledger.py`; `tests/api/test_provider_usage_ledger.py` | Duplicate filename in top-level and API folder | Keep until API/service coverage split is reviewed | Focused pytest for both; no provider/runtime behavior change |
| Network smoke | `setup.cfg`, `.github/workflows/network-smoke.yml`, tests marker usage | `network` marker defined; no `@pytest.mark.network` usage found | Add real marker tests or reframe workflow as script smoke | `python -m pytest -m network --collect-only -q -p no:cacheprovider` |
| Web CI Vitest coverage | `.github/workflows/ci.yml` | CI runs raw-i18n sentinel subset, not all 111 Vitest files | Consider full or sharded Vitest in CI | `npm --prefix apps/dsa-web run test` |
| Opt-in E2E | `apps/dsa-web/e2e/smoke.spec.ts`, `portfolio-ibkr-sync.spec.ts` | Skips require `DSA_WEB_LIVE_SMOKE` / `DSA_WEB_PORTFOLIO_E2E` | Keep, but document separate manual/scheduled workflow | Explicit env-gated smoke with safe credentials |

## 7. Orphan/stale scripts/docs/assets table

| Area | Candidate | Evidence | Classification | Action |
| --- | --- | --- | --- | --- |
| Scripts docs | `scripts/README.md` provider activation section | Lists only official macro and rotation Alpaca diagnostics; new provider probes exist | Stale docs | Update index; do not delete scripts |
| Provider probes | `diagnose_fed_liquidity_activation.py`, `diagnose_polygon_us_breadth_activation.py`, `diagnose_usd_pressure_activation.py` | Existing files; no scripts README entry found | Undocumented operator scripts | Add bounded docs and live-call caveats |
| Tested but hidden scripts | `diagnose_polygon_market_overview_activation.py`, `local_soak_performance_smoke.py`, `smoke_market_data_authenticated.py` | Imported by tests but missing from high-level scripts index | Discoverability gap | Document as local/operator helpers |
| Security script | `scripts/security_scan.sh` | `.github/workflows/security-scan.yml` watches it in path filters but does not call it | Not orphan | Keep; docs already explain workflow behavior |
| Runtime writes helper | `scripts/verify_runtime_writes.py` | File exists and is documented in scripts README | Not missing | No cleanup |
| Frontend docs archive link | `docs/frontend/README.md` | References missing `docs/design/archive/` | Stale docs link | Point to existing archive or remove claim |
| Design docs archive link | `docs/design/README.md` | References missing local `archive/` | Stale docs link | Point to existing archive or clarify none exists |
| Architecture docs links | `docs/architecture/postgresql-baseline-design.md` | Links old phase2/phase3 paths; archive files exist under `docs/architecture/archive/multi-user-foundation/` | Broken active-doc links | Update links |
| Public asset | `apps/dsa-web/public/image.png` | Current logo code uses `/wolfystock-logo-mark.png`; only historical changelog hit | Delete candidate after external check | Batch A |
| Public asset | `apps/dsa-web/public/wolfystock-logo-mark.svg` | No repo refs | Delete candidate after external check | Batch A |
| Archive asset | `docs/assets/archive/bot/img_2.png` | No repo refs | Safe delete candidate | Batch A |
| `sources/` assets | `sources/**` | Actively referenced by docs; governance says not normal cleanup | Protected from broad cleanup | Separate asset migration task only |

## 8. Dependency/import hygiene findings

Tool availability:

- Missing unused-code/dependency tools: `ts-prune`, `knip`, `depcheck`, `madge`, `dependency-cruiser`, Python `vulture`, `pipdeptree`, `pip_check`, `snakefood`.
- Available frontend tools: `eslint`, `tsc`, `vite`, `vitest`, `playwright` in `apps/dsa-web/node_modules/.bin`.
- No new packages were installed.

TypeScript static import scan:

- Scanned 377 TS/TSX files under `apps/dsa-web/src`.
- Non-test runtime unimported candidates:
  - `apps/dsa-web/src/components/market/MarketIntelligenceActionabilityStrip.tsx`
  - `apps/dsa-web/src/setupTests.ts`
  - `apps/dsa-web/src/types/portfolio.contract.ts`
- `setupTests.ts` is not dead code; it is configured by `apps/dsa-web/vitest.config.ts`.
- `portfolio.contract.ts` is a portfolio-protected audit candidate, not a direct delete.

Python AST import scan:

- Scanned 923 Python files.
- Runtime candidates with no AST import hits were limited to package/init or external entrypoint-style files: `api/__init__.py`, `bot/__init__.py`, `bot/handler.py`.
- `bot/handler.py` may be an external webhook entrypoint; do not delete without deployment route check.
- TypeScript circular import found in Market Overview:
  - `MarketOverviewWorkbenchTopSurface.tsx` lazy-imports `MarketOverviewDecisionDebugDetails.tsx`.
  - `MarketOverviewDecisionDebugDetails.tsx` imports types from `MarketOverviewWorkbenchTopSurface.tsx`.
  - This should be fixed by extracting shared types, not by deleting either file.

Dependency findings:

- `@remixicon/react` is declared in `apps/dsa-web/package.json` but no source import was found by `rg`.
- `recharts` is declared in `apps/dsa-web/package.json`; `rg` found no runtime source import, only a test mock in `PortfolioPage.test.tsx`.
- `autoprefixer`, `postcss`, `typescript`, and `@types/*` have config/toolchain roles and should not be treated as unused by source-import text search.
- Python code directly imports `pydantic`, `websockets`, and `dateutil`, while `requirements.txt` does not explicitly declare `pydantic`, `websockets`, or `python-dateutil`. These may currently arrive transitively through FastAPI/Uvicorn/other packages, but runtime-critical imports should be declared explicitly in a dependency-scope task.
- `discord.py` is declared in `requirements.txt`, while `bot/platforms/discord.py` appears orphaned. Do not remove the dependency without checking any notification sender or external bot path.
- Package/lockfile cleanup is forbidden for this goal and requires a separate dependency task.

## 9. Protected no-touch list

No source/test/config/package files were changed in this audit. Future cleanup tasks must not modify these domains unless separately scoped with focused tests:

- Scanner scoring, candidate selection, thresholds, ranking/sorting, AI influence, default universe, fallback/live labeling.
- Backtest math: fills, costs, exposure, returns, drawdown, benchmarks, stored result semantics.
- Portfolio accounting: cash ledger, holdings, lots, FX/native currency, P&L, cost basis, transactions, imports/sync.
- Provider runtime: global order, live-call paths, first-good-wins fallback, circuit semantics, fallback depth, deadline behavior.
- MarketCache: TTL, SWR, cold-start, cache keys, payload meaning, fallback/mock/synthetic live labeling.
- Provider/source-confidence/readiness/right-to-display: `data_provider/**`, `src/services/*source*`, `src/services/*readiness*`, `src/services/*data_quality*`.
- Options: ranking, gates, payoff math, recommendation policy, market data provider authority.
- Auth/RBAC/security: sessions, capabilities, admin route protection, CSRF/CORS/security middleware, passwords/tokens.
- AI prompts/routing/model/decision logic and agent strategy compatibility.
- Notification routing, retry, real-send vs dry-run boundaries.
- DuckDB/PostgreSQL/SQLite source-of-truth and storage coexistence shims.
- API response shapes and stored contract versions.
- `sources/**` asset movement unless explicitly scoped.

## 10. Recommended next tasks

### Batch A: low-risk delete cleanup

Objective: delete only files with zero repo references and low product/runtime coupling.

Allowed files:

- `docs/assets/archive/bot/img_2.png`
- `apps/dsa-web/public/wolfystock-logo-mark.svg`
- `apps/dsa-web/public/image.png`

Forbidden files:

- `apps/dsa-web/src/**`
- `apps/dsa-web/package.json`
- `apps/dsa-web/package-lock.json`
- `src/**`
- `api/**`
- `data_provider/**`
- `tests/**`
- `.github/**`
- `scripts/**`

Required validation:

- `rg -n "img_2\\.png|wolfystock-logo-mark\\.svg|image\\.png|/image\\.png" .`
- `npm --prefix apps/dsa-web run build`
- browser smoke for favicon/logo/boot loader if public assets are removed
- `git diff --check`
- `./scripts/release_secret_scan.sh`

### Batch B: tests/docs/assets cleanup

Objective: update stale docs links and merge duplicate tests without behavior changes.

Allowed files:

- `scripts/README.md`
- `docs/frontend/README.md`
- `docs/design/README.md`
- `docs/architecture/postgresql-baseline-design.md`
- `docs/ARCHIVE_INDEX.md`
- `apps/dsa-web/src/pages/tests/OptionsLabPage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/OptionsLabPage.test.tsx`
- `apps/dsa-web/src/pages/tests/DeterministicBacktestResultPage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/DeterministicBacktestResultPage.test.tsx`
- `apps/dsa-web/src/components/backtest/tests/BacktestResultReport.test.tsx`
- `apps/dsa-web/src/components/backtest/__tests__/BacktestResultReport.test.tsx`
- `tests/test_provider_usage_ledger.py`
- `tests/api/test_provider_usage_ledger.py`

Forbidden files:

- Runtime source under `src/**`, `api/**`, `data_provider/**`
- Frontend runtime source under `apps/dsa-web/src/pages/*.tsx` or `apps/dsa-web/src/components/**/*.tsx`
- package/lock/config files unless the task is explicitly widened

Required validation:

- focused Vitest for affected tests
- focused pytest for provider usage ledger if touched
- docs link `rg` checks
- `git diff --check`
- `./scripts/release_secret_scan.sh`

### Batch C: frontend consolidation

Objective: remove orphan UI and centralize consumer-safe data-quality projection.

Allowed files:

- `apps/dsa-web/src/components/market/MarketIntelligenceActionabilityStrip.tsx`
- `apps/dsa-web/src/pages/HomeBentoDashboardPage.tsx`
- `apps/dsa-web/src/pages/UserScannerPage.tsx`
- `apps/dsa-web/src/pages/WatchlistPage.tsx`
- `apps/dsa-web/src/pages/MarketOverviewPage.tsx`
- `apps/dsa-web/src/components/scanner/**`
- `apps/dsa-web/src/components/market-overview/**`
- `apps/dsa-web/src/components/options/**`
- route/component tests directly covering those files

Forbidden files:

- Backend/API/provider/cache/storage files
- scanner scoring/ranking/selection semantics
- portfolio accounting and options payoff/ranking/gates
- package/lock files

Required validation:

- focused route/component Vitest
- `npm --prefix apps/dsa-web run lint`
- `npm --prefix apps/dsa-web run build`
- route-level browser/e2e proof for consumer pages at desktop/mobile
- raw vocabulary guard: no default consumer `sourceAuthorityAllowed`, `scoreContributionAllowed`, provider names, raw JSON, reason codes, or backend snake_case field names

### Batch D: backend/service consolidation

Objective: perform narrow backend cleanup where external/runtime risk is bounded.

Allowed files for bot subtask:

- `bot/platforms/discord.py`
- `bot/platforms/__init__.py`
- `bot/handler.py`
- `bot/__init__.py`
- bot docs directly naming webhook support
- bot tests

Allowed files for source-provenance planning subtask:

- docs-only audit under `docs/codex/audits/**`
- tests that prove existing provenance behavior, if separately scoped

Forbidden files:

- `data_provider/**`
- provider order/fallback/live-call code
- `src/services/market_scanner_service.py`
- `src/services/rule_backtest_service.py`
- `src/services/portfolio_service.py`
- `src/services/options_lab_service.py`
- API response schemas unless explicitly scoped
- notification sending/routing code unless explicitly scoped

Required validation:

- external route/deployment reference check for bot handlers
- `python -m py_compile` for changed Python files
- focused pytest for bot/provenance contracts
- full protected-domain owner review before source-provenance consolidation

### Batch E: high-risk follow-up audits

Objective: produce separate audit or design tasks before touching protected runtime.

Allowed files:

- docs-only reports under `docs/codex/audits/**`
- optional progress files under `docs/codex/goals/**`

Forbidden files:

- all source/test/config/package/app files unless a follow-up task explicitly opens them

Recommended audit topics:

- Provider-fit-advisor endpoint consumer/API audit.
- Admin provider operations vs operations-matrix consolidation design.
- Source-confidence/consumer-safe projection contract implementation plan.
- Storage coexistence and PostgreSQL/SQLite source-of-truth cleanup plan.
- Scanner/MarketOverview mega-service decomposition plan.
- Backtest service split with golden math/order tests.
- Portfolio contract/type residue audit.
- Dependency/lockfile cleanup using `knip`/`depcheck` or equivalent approved tooling.
- CI coverage alignment for full/sharded Vitest, network smoke truth, desktop build gate.

## 11. Allowed/forbidden files by next task

| Next task | Allowed files | Forbidden files |
| --- | --- | --- |
| Batch A low-risk delete cleanup | `docs/assets/archive/bot/img_2.png`, `apps/dsa-web/public/wolfystock-logo-mark.svg`, `apps/dsa-web/public/image.png` | All source/test/config/package files; `.github/**`; `scripts/**` |
| Batch B tests/docs/assets cleanup | Specific docs and duplicate tests listed in Batch B | Runtime source; provider/cache/auth/accounting/backtest/scanner/options code; package/lock files |
| Batch C frontend consolidation | Listed frontend route/component files and directly coupled tests | Backend/API/provider/storage; package/lock; scoring/accounting/options math |
| Batch D backend/service consolidation | Bot files/docs/tests for bot subtask; docs-only planning for provenance subtask | Provider runtime, MarketCache, scanner/backtest/portfolio/options protected files, API schemas unless scoped |
| Batch E protected audits | `docs/codex/audits/**`, optional `docs/codex/goals/**` | All source/test/config/package/app files unless new task explicitly scopes them |

## 12. Confirmation no source/test/config/package files changed

Confirmed for the audit work through final validation:

- No source files changed.
- No test files changed.
- No config files changed.
- No package or lock files changed.
- No app/runtime files changed.
- The only intended repo write is this report: `docs/codex/audits/T-1176-system-wide-consolidation-audit.md`.

This was rechecked before commit with `git status --short --branch`, `git diff --name-only`, and explicit staging of only this report file. It must also be rechecked after commit with:

```bash
git diff --name-only HEAD~1..HEAD
git status --short --branch
```

## 13. Commit hash for the audit report branch

Git commit hashes are content-addressed, so the exact hash of the commit that contains this line cannot be embedded into the same committed file without changing the hash again.

The immutable branch commit hash for the committed audit report is therefore recorded in the Codex final closeout after commit/push. At report drafting time:

- Base/audited commit: `dc2af89e02975d27dc8fb92d98e7b54101942e32`
- Audit report branch: `codex/t1176-system-wide-consolidation-audit`
- Report file: `docs/codex/audits/T-1176-system-wide-consolidation-audit.md`

## Validation log

Commands run during audit and final validation:

| Command | Result |
| --- | --- |
| `git status --short --branch` | clean before report write; after report write only this report file was untracked |
| `git rev-parse HEAD origin/main` | both `dc2af89e02975d27dc8fb92d98e7b54101942e32` |
| `npm --prefix apps/dsa-web run lint` | passed, exit 0 |
| `npm --prefix apps/dsa-web run build` | passed, exit 0; Vite emitted chunk-size warning only |
| `git diff --check -- docs/codex/audits/T-1176-system-wide-consolidation-audit.md` | passed, exit 0 |
| `git diff --check` | passed, exit 0 |
| `./scripts/release_secret_scan.sh` | passed, exit 0 |
| TypeScript static import scan | found `MarketIntelligenceActionabilityStrip.tsx`, `setupTests.ts`, `portfolio.contract.ts` as non-test unimported candidates; `setupTests.ts` is configured by Vitest |
| Python AST import scan | found only `api/__init__.py`, `bot/__init__.py`, `bot/handler.py` as runtime candidates with no AST import hits |
