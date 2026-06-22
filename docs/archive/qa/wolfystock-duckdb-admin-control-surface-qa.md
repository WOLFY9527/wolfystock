# WolfyStock DuckDB Admin Control Surface QA Smoke Report

Date: 2026-05-05 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: QA/audit/report only; no product code, tests, CSS, backend/API, package, config, runtime, or changelog changes

## 1. Executive Summary

Overall assessment: **PASS with follow-up items**.

Safety conclusion: the DuckDB admin control surface at `/zh/settings/system` behaves as a diagnostic-only, disabled-by-default friendly panel under static checks, targeted unit/API tests, full backend gate, and mocked Playwright desktop/mobile smoke. Disabled mode renders as optional/non-error, blocks explicit write actions in the panel, does not auto-run init/build, and did not create any `*.duckdb` or `*.duckdb.wal` file in the repository.

Top findings:

- **No P0/P1/P2 blocker found** in this smoke.
- **P3 follow-up:** add a dedicated Playwright/Vitest integration fixture for the DuckDB panel states so future browser smoke coverage is not only report-run evidence.
- **P3 follow-up:** consider adding a visible unavailable/error-state unit assertion for compact Chinese copy and collapsed developer details.

Recommended next actions:

1. Add a permanent frontend smoke fixture for disabled, enabled, and unavailable DuckDB panel states.
2. Keep DuckDB admin actions diagnostic-only and explicit; do not connect DuckDB to scanner, backtest, portfolio, market provider, AI, or notification runtime.
3. Re-run this smoke after any future changes to `DuckDBQuantPanel`, `quantApi`, or `api/v1/endpoints/quant.py`.

## 2. Methodology

Commands run:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -96
./scripts/task_preflight.sh || true

cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
npm run check:design
npm run lint
npm run build

cd /Users/yehengli/daily_stock_analysis
python3 -m py_compile api/v1/endpoints/quant.py api/v1/schemas/quant.py src/services/quant_analytics/duckdb_service.py
python3 -m pytest tests/test_quant_duckdb_service.py tests/api/test_quant_duckdb.py -q

cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
npm run test -- src/api/__tests__/quant.test.ts --run
npm run test -- src/pages/__tests__/SettingsPage.test.tsx --run
npm run test -- src/pages/__tests__/PersonalSettingsPage.test.tsx --run

cd /Users/yehengli/daily_stock_analysis
find . -name "*.duckdb" -o -name "*.duckdb.wal"
./scripts/ci_gate.sh
rg -n "markdownlint|mdlint|lint:md|lint.*markdown|remark.*lint" package.json apps/dsa-web/package.json .github scripts docs 2>/dev/null | head -80
```

Playwright/browser method:

- Browser: headless Chromium through the existing `apps/dsa-web` Playwright dependency.
- Route: `http://127.0.0.1:5175/zh/settings/system`.
- Viewports: desktop `1440x1000`; mobile/narrow `390x844`.
- Server: isolated `npm run preview -- --host 127.0.0.1 --port 5175`; stopped after smoke and confirmed free.
- Mock/live strategy: mocked authenticated admin, mocked system config, and mocked DuckDB quant endpoints. No live backend DuckDB write endpoint was called.
- No screenshots, videos, traces, or temp Playwright files were retained.

Ports:

| Port | Status before smoke | Use in this pass |
| --- | --- | --- |
| `8000` | Existing Python backend listener | Observed only; not restarted or called by Playwright. |
| `8001` | Free | Not used. |
| `5173` | Existing Vite frontend listener | Observed only; not touched. |
| `4173` | Free | Not used. |
| `5174` | Free | Not used. |
| `5175` | Free, then started isolated preview | Used for Playwright smoke; stopped after verification. |
| `5176` | Existing Node preview/browser connections | Observed only; not touched. |

Limitations:

- Browser verification used mocked API responses, not a live authenticated backend session.
- Enabled-mode browser checks did not initialize or build a real DuckDB file; they verified UI behavior and endpoint calls through mocks.
- The report relies on existing backend tests for live service disabled/no-write and enabled temp-path behavior.

## 3. Static Quality Baseline

| Check | Result | Key output | Notes |
| --- | --- | --- | --- |
| Preflight path | PASS | `/Users/yehengli/daily_stock_analysis` | Expected path. |
| Preflight branch | PASS | `main` | Expected branch. |
| Initial dirty state | PASS with caution | `M apps/dsa-web/src/index.css` | Unrelated dirty file observed at start; not touched. It was no longer dirty by report-writing time. |
| `npm run check:design` | PASS | 216 files scanned; 0 blocking; 0 warnings | Design guard clean. |
| `npm run lint` | PASS | `eslint .` exited 0 | No lint output. |
| `npm run build` | PASS with warning | 3160 modules transformed; built in 11.93s | Vite chunk warning printed. |
| Vite chunk warning | WARN | `DeterministicBacktestChartWorkspace-HEP1Z01E.js` 532.42 kB / 178.83 kB gzip | Existing large lazy chart workspace warning, not DuckDB-specific. |
| Markdown lint | Not available | Search found docs mentions only, no runnable markdown lint script | No root `package.json`; web package has no markdown lint script. |

## 4. Backend Quant Verification

| Check | Result | Key output | Notes |
| --- | --- | --- | --- |
| Python compile | PASS | `python3 -m py_compile ...` exited 0 | Covered quant endpoint, schema, and service files. |
| Quant backend tests | PASS | 23 passed in 3.21s | `tests/test_quant_duckdb_service.py` and `tests/api/test_quant_duckdb.py`. |
| Disabled no-write tests | PASS | Disabled health/ingest/factor-snapshot/compare tests assert no DB file exists | Covered `tmp_path` disabled mode. |
| Generated file check | PASS | `find . -name "*.duckdb" -o -name "*.duckdb.wal"` returned no output | No generated DuckDB file in repo. |
| Full gate | PASS | 1993 passed, 3 skipped, 1 warning, 203 subtests passed in 150.65s | Startup warnings: local `flake8` and `akshare` not installed. |

## 5. Frontend Panel Verification

| State | Desktop result | Mobile result | Auto-run/write safety | Developer details | Leakage check | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Disabled health/coverage | PASS | PASS | PASS: only health/coverage reads auto-ran; init/build disabled; forced init click caused 0 init calls | Collapsed | PASS | Visible labels included `未启用`, `可选能力`, and `未写入文件`. Disabled state is optional/non-error. |
| Enabled coverage | PASS | PASS | PASS: enabled data loaded through read refresh; no init/build auto-run | Collapsed | PASS | Sanitized relative DB path, 44 OHLCV rows, 44 factor rows, 2 symbols, `2026-01-01 -> 2026-01-22`, latest factor date `2026-01-22`. |
| Benchmark | PASS | PASS | PASS: called only after explicit `小样本基准` click | Collapsed | PASS | Mocked result showed `durationMs=12.5`, 44 rows, 2 bounded symbols, `dataMode=real`, top result sample present. |
| Factor snapshot / validate / compare | PASS | PASS | PASS: each POST called only after explicit click | Collapsed | PASS | Snapshot/validation showed bounded AAPL/MSFT symbols; comparison showed `productionRuntimeChanged=false · 诊断专用`. |
| Error/unavailable | PASS | PASS | PASS: read-only mocked unavailable state | Collapsed | PASS | Compact unavailable copy; no raw stack trace, token, API key, or unsafe absolute path visible. |

Additional browser checks:

- Route rendered at `/zh/settings/system`.
- DuckDB panel was visible via `data-testid="duckdb-quant-panel"`.
- No console errors.
- No page errors.
- No horizontal overflow: desktop `0`, mobile `0`.
- No native-looking control risk from visible `select`, `input`, `button`, or `textarea` scan.
- Chinese labels remained compact.

## 6. Endpoint Behavior Observed

Mocked endpoint calls during Playwright smoke:

- `GET /api/v1/quant/duckdb/health`: 6 calls.
- `GET /api/v1/quant/duckdb/coverage`: 6 calls.
- `POST /api/v1/quant/duckdb/benchmark`: 2 calls, explicit click only.
- `POST /api/v1/quant/duckdb/factor-snapshot`: 2 calls, explicit click only.
- `POST /api/v1/quant/duckdb/validate-factor-path`: 2 calls, explicit click only.
- `POST /api/v1/quant/duckdb/compare-runtime-context`: 2 calls, explicit click only.
- `POST /api/v1/quant/duckdb/init`: 0 calls; disabled button blocked the attempted disabled-mode action.
- `POST /api/v1/quant/duckdb/build-factors`: 0 calls; not auto-run and not needed for this diagnostic UI smoke.

Supporting mocked endpoints:

- `GET /api/v1/auth/status`: 6 calls, mocked authenticated admin.
- `GET /api/v1/system/config`: 6 calls, mocked system config with `QUANT_DUCKDB_ENABLED` state switching.

No live backend DuckDB endpoint was called during browser smoke.

## 7. Issues And Follow-Up Tasks

| ID | Severity | Evidence | Likely owner/files | Recommended fix task | Parallel? | Recommended tests/verification |
| --- | --- | --- | --- | --- | --- | --- |
| DQA-01 | P3 | Browser smoke currently lives only in this report-run evidence; no permanent Playwright fixture covers disabled/enabled/unavailable states end to end. | `apps/dsa-web/src/pages/__tests__/SettingsPage.test.tsx` or future Playwright smoke fixtures. | Add a dedicated DuckDB panel browser or component smoke fixture for disabled, enabled coverage/actions, and unavailable states. | Yes, if limited to frontend tests. | `npm run test -- src/pages/__tests__/SettingsPage.test.tsx --run`, Playwright desktop/mobile smoke. |
| DQA-02 | P3 | Existing tests cover collapsed developer details and path sanitization; unavailable/error compact-copy behavior was verified in Playwright mock only. | `apps/dsa-web/src/components/settings/DuckDBQuantPanel.tsx`, `apps/dsa-web/src/pages/__tests__/SettingsPage.test.tsx`. | Add a focused assertion for unavailable/error copy, collapsed developer details, and no raw stack/path leakage. | Yes, frontend-test only. | Targeted SettingsPage test plus design guard. |

## 8. What Passed Cleanly

- DuckDB remains optional and disabled-by-default friendly.
- Disabled mode did not create a DuckDB file in tests or repository artifact scan.
- Panel auto-load uses read-only health/coverage only.
- Init and factor build did not auto-run.
- Init/build are disabled or blocked in disabled mode.
- Benchmark, factor snapshot, validation, and runtime comparison are explicit-click diagnostics.
- Runtime comparison keeps `productionRuntimeChanged=false`.
- Desktop and mobile layouts had no horizontal overflow.
- Developer details stayed collapsed by default.
- Default visible UI did not expose raw stack traces, API keys, bearer tokens, webhook URLs, or unsafe absolute paths.
- Backend quant compile, targeted quant tests, frontend quant/settings tests, design guard, lint, build, and full `ci_gate` passed.

## 9. Non-Goals

- No product code changed.
- No tests changed.
- No CSS changed.
- No backend/API changed.
- No package files or config changed.
- No `docs/CHANGELOG.md` changed.
- No generated DuckDB files committed.
- No production runtime changed.
- No scanner scoring, selection, ranking, or thresholds changed.
- No backtest calculations changed.
- No portfolio accounting changed.
- No market provider behavior changed.
- No AI decision logic changed.
- No notification routing changed.

## 10. Appendix

Preflight summary:

```text
pwd: /Users/yehengli/daily_stock_analysis
branch: main
initial git status --short: M apps/dsa-web/src/index.css
upstream: origin/main, ahead 0 / behind 0
recent commits included:
543d6cb chore(css): remove unused glass card selectors
3f68c7c docs: define canonical ui primitives
7ae7e8b feat(quant): add duckdb admin control surface
f16428e feat(quant): add optional duckdb factor validation path
0059751 docs: add duckdb operator smoke guide
```

Static command output summary:

```text
npm run check:design
Files scanned: 216
Design guard passed. No blocking violations or warnings found.

npm run lint
eslint . exited 0

npm run build
3160 modules transformed
DeterministicBacktestChartWorkspace-HEP1Z01E.js 532.42 kB / gzip 178.83 kB
Some chunks are larger than 500 kB after minification.
built in 11.93s
```

Backend and test output summary:

```text
python3 -m py_compile api/v1/endpoints/quant.py api/v1/schemas/quant.py src/services/quant_analytics/duckdb_service.py
exited 0

python3 -m pytest tests/test_quant_duckdb_service.py tests/api/test_quant_duckdb.py -q
23 passed in 3.21s

npm run test -- src/api/__tests__/quant.test.ts --run
1 file passed, 3 tests passed

npm run test -- src/pages/__tests__/SettingsPage.test.tsx --run
1 file passed, 73 tests passed

npm run test -- src/pages/__tests__/PersonalSettingsPage.test.tsx --run
1 file passed, 4 tests passed

./scripts/ci_gate.sh
1993 passed, 3 skipped, 1 warning, 203 subtests passed in 150.65s
backend-gate completed successfully
```

Playwright route details:

```text
Route: /zh/settings/system
Base URL: http://127.0.0.1:5175
Viewports: 1440x1000, 390x844
Strategy: mocked authenticated admin + mocked system config + mocked DuckDB endpoints
Console errors: 0
Page errors: 0
Horizontal overflow: 0 on desktop, 0 on mobile
Native-control risk matches: 0
Default visible leakage matches: 0
Init calls while disabled: 0
Build calls during smoke: 0
```

Cleanup:

```text
Port 5175 isolated preview was stopped and confirmed free.
No /tmp Playwright scripts/results were created or retained.
find . -name "*.duckdb" -o -name "*.duckdb.wal" returned no output.
No generated screenshots, videos, traces, reports, coverage, sourcemaps, DuckDB files, logs, or temp files were staged.
```
