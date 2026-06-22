# WolfyStock Scanner Export Label Policy

Date: 2026-05-06 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: report-only product/localization policy; no product behavior change

## 1. Executive Summary

Recommended policy: Scanner CSV exports should remain stable machine-oriented artifacts by default, including on `/zh/scanner`. The visible export chrome should be localized, but the default CSV header keys should remain English technical keys until WolfyStock explicitly adds a separate readable export mode.

The compatibility/localization tradeoff is asymmetric. Localized CSV headers improve readability for Chinese operators who open the file manually, but they also break scripts, spreadsheet templates, QA fixtures, and future imports that depend on stable field names. The current implementation and tests already treat the CSV header row as a contract: `rank,symbol,name,scannerScore,entryRange,target,stop,reason,risk,universeType,theme,generatedAt,runId`.

First implementation recommendation: keep default machine CSV unchanged, document the header contract, and only localize visible export controls and surrounding route copy. If user demand appears for Chinese-readable spreadsheets, add an explicit second export mode later, such as `Readable CSV`, with localized headers and tests that prove the machine export remains unchanged.

## 2. Current Scanner Export Inventory

| Export artifact | Current filename/header/value | User-facing or machine-oriented | Localization risk | Downstream compatibility risk |
| --- | --- | --- | --- | --- |
| Run-level export button | `导出 CSV` on zh route, `Export CSV` on en route | User-facing visible chrome | Low; already localized | Low; button label is not a data contract |
| Candidate developer export button | `导出` on zh route, `Export` on en route inside developer fields | User-facing chrome inside developer disclosure | Low; already localized | Low; action label only |
| CSV MIME type | `text/csv;charset=utf-8` | Machine-oriented artifact metadata | None | Medium; changing type can affect browser/download behavior |
| Generated filename prefix | `scanner_` | Machine-oriented but visible in download shelf and file manager | Medium; localized prefix may help readability but can create mixed encoding/automation differences | Medium; operators may sort, archive, or parse filenames by prefix |
| Generated filename market segment | lower-case market, for example `us`, `cn`, `hk` | Machine-oriented domain value | Low; market codes should remain English/domain codes | Medium; stable segment helps automated file grouping |
| Generated filename date segment | `YYYY-MM-DD` | Machine-oriented metadata | None | High; stable date format is useful for sorting and scripts |
| Generated filename run segment | `run-{id}` | Machine-oriented generated metadata | Medium; Chinese `运行-{id}` is readable but less script-stable | High; run id is a stable join key to app/API data |
| Generated filename suffix | `results` by default | Mixed: readable descriptor plus machine segment | Medium; could be localized in readable mode | Medium; default suffix should stay stable |
| CSV header row | `rank,symbol,name,scannerScore,entryRange,target,stop,reason,risk,universeType,theme,generatedAt,runId` | Both, but primarily machine-oriented | High if localized in place; users may prefer Chinese, but field identity becomes ambiguous | High; existing test asserts this exact header string |
| `rank` | Numeric candidate rank | Stable machine key | Low | High; used for sorting and Scanner -> Backtest context |
| `symbol` | Ticker/code such as `NVDA` | Stable machine key plus domain value | None; tickers should not be localized | High; primary join key |
| `name` | Company/security display name | Localized/domain display value when source provides it | Medium; source language may vary | Medium; useful but not primary identity |
| `scannerScore` | Numeric scanner score | Stable machine key | Medium; Chinese label is readable but key should stay stable | High; downstream sorting/filtering key |
| `entryRange`, `target`, `stop` | Execution planning values from candidate fields | Stable machine keys with domain values | Medium; label can be localized only in readable export | Medium; useful for manual workflow and templates |
| `reason`, `risk` | Localized narrative values built with current route language | Localized display values inside machine columns | Low; values may already be zh/en by route | Medium; free text should not be parsed as strict schema |
| `universeType` | Raw token such as `default`, `theme`, `symbols` | Stable machine key and developer/raw field | High if translated, because it is a token | High; important for grouping scanner runs |
| `theme` | Theme label or theme id | Mixed display/domain value | Medium; label may be Chinese, id may be raw | Medium; useful for human context and grouping |
| `generatedAt` | ISO-like timestamp from run detail | Generated metadata | Low; keep machine timestamp | High; important for reproducibility |
| `runId` | Numeric scanner run id | Generated metadata and join key | Low; header should stay stable | High; primary provenance key |

## 3. Field Classification

| Field or artifact | Classification | Policy |
| --- | --- | --- |
| `rank` | Stable machine key | Keep header stable in default CSV. Localized readable label can be `排名` only in an explicit readable export mode. |
| `symbol` | Stable machine key and domain value | Keep header and values stable. Never localize ticker/security codes. |
| `name` | Localized display label/value | Header stays stable in default CSV; value may reflect upstream/source language. |
| `scannerScore` | Stable machine key | Keep camelCase key stable. This is a likely downstream sort/filter field. |
| `entryRange` | Stable machine key | Keep key stable. Readable mode may label it `建仓区间`. |
| `target` | Stable machine key | Keep key stable. Readable mode may label it `目标位`. |
| `stop` | Stable machine key | Keep key stable. Readable mode may label it `止损位`. |
| `reason` | Localized display value inside stable column | Keep key stable. Values may be localized because they are narrative, not join keys. |
| `risk` | Localized display value inside stable column | Keep key stable. Values may be localized because they are narrative summaries. |
| `universeType` | Developer/raw field and stable machine key | Keep raw token and header stable in default CSV. Use localized labels only in readable mode or visible UI. |
| `theme` | Domain value, sometimes display label and sometimes raw id | Keep header stable; value can be a human theme label when available. |
| `generatedAt` | Generated metadata | Keep key and timestamp format stable for sortability and provenance. |
| `runId` | Generated metadata and stable machine join key | Keep key stable. Do not localize in default CSV. |
| `scanner_...csv` filename | Generated metadata | Keep default filename ASCII-safe and parseable. Consider localized display filenames only for readable mode. |
| Export button/menu labels | Localized display label | Localize by route, as current implementation already does. |

## 4. Policy Options

### Option A: English Stable Machine Headers Only

Pros:

- Preserves the current tested contract.
- Lowest risk for scripts, spreadsheet templates, QA fixtures, and future imports.
- Makes exported files consistent across `/scanner` and `/zh/scanner`.
- Keeps raw tokens such as `universeType` honest instead of mixing translated labels with unlocalized values.

Cons:

- Chinese users opening the CSV directly see English technical headers.
- Product localization remains incomplete if exports are treated as primary user-facing documents.

Test impact:

- Minimal. Existing header assertion remains valid.
- Add documentation or snapshot tests later if the header contract becomes formal.

User impact:

- Best for power users and operators who reuse files across tools.
- Less friendly for one-off manual spreadsheet review in Chinese.

Compatibility risk:

- Lowest.

### Option B: Chinese Localized Headers on zh Route

Pros:

- Highest immediate readability for Chinese operators opening exported CSVs manually.
- Aligns exports with Chinese route chrome if exports are classified as user-facing documents.

Cons:

- Breaks the current header contract on `/zh/scanner`.
- Creates route-dependent schemas for the same export action.
- Makes documentation, support, tests, and spreadsheet automation harder.
- Still leaves domain values such as tickers, market codes, run ids, and raw universe tokens in English-like forms.

Test impact:

- Requires route-aware CSV export tests.
- Existing header assertion must change or split by locale.
- Requires fixture updates wherever exports are referenced.

User impact:

- Better for manual reading in Chinese.
- Worse for users who switch locale or share files with English tooling.

Compatibility risk:

- High.

### Option C: Dual Header Row

Pros:

- First row can remain stable machine keys while a second row provides Chinese readable labels.
- One file carries both schema identity and user-readable labels.

Cons:

- Many CSV consumers expect exactly one header row.
- Spreadsheet tools may treat the second header row as data.
- Importers must learn to skip or detect a metadata row.
- Ambiguous if the second row should appear only in zh route or all routes.

Test impact:

- Requires new assertions for both rows and importer behavior.
- Any downstream parser would need explicit handling.

User impact:

- Potentially useful for manual spreadsheet review.
- Confusing in simple CSV workflows because the first data row is not a candidate.

Compatibility risk:

- Medium to high.

### Option D: Separate Export Modes: Machine CSV vs Readable CSV

Pros:

- Preserves the current stable machine CSV by default.
- Allows a future Chinese-readable export without breaking existing tools.
- Makes intent explicit in the UI and docs: automation vs human review.
- Can localize headers, filename suffix, and maybe explanatory metadata only in readable mode.

Cons:

- Adds UI and testing surface.
- Requires product copy to avoid overwhelming the Scanner action menu.
- Adds long-term documentation burden for two modes.

Test impact:

- Existing machine CSV test remains unchanged.
- New tests cover readable CSV headers and filename policy in zh/en.
- Fixtures should assert that readable mode never changes Scanner behavior or candidate ranking.

User impact:

- Best balance for mixed audiences.
- Chinese operators get readable exports when they explicitly choose them.
- Automation users keep a stable default.

Compatibility risk:

- Low if the machine export remains the default and unchanged.

## 5. Recommended Policy

Pick Option D as the long-term policy, with Option A as the immediate behavior.

Default export:

- Keep default Scanner CSV headers in English stable machine keys on all routes.
- Keep default filename ASCII-safe and parseable: `scanner_{market}_{YYYY-MM-DD}_run-{id}_{suffix}.csv`.
- Treat `rank`, `symbol`, `scannerScore`, `universeType`, `generatedAt`, and `runId` as compatibility-sensitive fields.
- Treat `reason`, `risk`, `theme`, and `name` as values that may carry localized or source-language text inside stable columns.

Visible route chrome:

- Localize visible controls on `/zh/scanner`, including export buttons, menus, tooltips, and any explanatory helper text.
- Keep `CSV`, ticker symbols, market codes, provider names, metric abbreviations, and raw ids where they are accepted domain/developer terms.

Readable export mode:

- Add only if user demand justifies it.
- Make it explicit, for example `导出可读 CSV` / `Export readable CSV`.
- Localize readable headers by locale.
- Use a distinct filename suffix such as `readable` or `zh-readable`, while keeping date/run id stable.
- Do not replace or silently mutate the default machine CSV.

Filenames:

- Default machine filenames should not be localized.
- Future readable exports may use a localized or semi-localized suffix, but should retain ASCII-safe market/date/run segments for sortability and support.
- Avoid fully Chinese filenames by default unless the product accepts the operational cost of non-ASCII paths in shell scripts, CI fixtures, downloaded archives, and cross-platform support.

## 6. Implementation Roadmap

Phase 1: no behavior change, document policy.

- Land this report only.
- Do not change Scanner source, tests, CSS, backend/API, package/config, runtime files, or `docs/CHANGELOG.md`.
- Treat the current default CSV header row as a compatibility-sensitive contract.

Phase 2: localize visible export chrome only.

- Audit visible `/zh/scanner` export labels, tooltips, error text, and helper text.
- Keep CSV headers and default filenames unchanged.
- Add UI tests only for visible chrome if needed.

Phase 3: optional localized readable export mode.

- Add a second explicit export action if product demand exists.
- Use localized headers for readable mode only.
- Use a distinct filename suffix and documentation so users understand the difference from machine CSV.
- Keep Scanner ranking, selection, backtest handoff, and export row values unchanged.

Phase 4: tests and fixtures.

- Preserve an assertion for the machine header row:
  `rank,symbol,name,scannerScore,entryRange,target,stop,reason,risk,universeType,theme,generatedAt,runId`.
- Add readable-mode tests only when the mode exists.
- Add compatibility notes to Scanner docs if readable export becomes a product feature.

## 7. Non-Goals

- No code changed.
- No tests changed.
- No CSS changed.
- No backend/API changed.
- No package files or config changed.
- No `docs/CHANGELOG.md` changed.
- No scanner behavior changed.
- No export behavior changed.
- No route/browser behavior changed.

## 8. Appendix

### Commands and Results

Preflight:

| Command | Result |
| --- | --- |
| `pwd` | `/Users/yehengli/daily_stock_analysis` |
| `git branch --show-current` | `main` |
| `git status --short` | clean |
| `git status --branch --short` | `## main...origin/main` |
| `git log --oneline -180` | completed; recent head was `905b2a5 refactor(portfolio): align surface primitives` |
| `./scripts/task_preflight.sh || true` | PASS; branch `main`; upstream `origin/main` ahead 0 / behind 0; dirty files `0` |

Static investigation:

| Command | Result |
| --- | --- |
| `rg -n "CSV\|csv\|export\|download\|filename\|scanner_\|rank,symbol\|scannerScore\|entryRange\|target\|stop\|reason\|risk\|universeType\|generatedAt\|runId\|Blob\|text/csv\|encodeURIComponent" ... \| head -700` | completed; found Scanner export builders, filename builder, download helper, localized export buttons, and tests asserting the current header |

Baseline checks:

| Command | Result |
| --- | --- |
| `cd apps/dsa-web && npm run check:design` | PASS; 216 files scanned; 0 blocking violations; 0 warnings |
| `cd apps/dsa-web && npm run lint` | PASS; `eslint .` exited 0 |
| `cd apps/dsa-web && npm run build` | PASS with existing Vite chunk-size warning; `DeterministicBacktestChartWorkspace-zWaHo3tJ.js` reported at 532.42 kB |
| `python3 -m compileall -q src api` | PASS; no output |
| `./scripts/ci_gate.sh` | Not run; prompt said no full `ci_gate.sh` required for docs-only unless practical, and the requested targeted frontend/backend checks passed |
| Markdown lint search | No runnable markdown lint script found; search for markdown lint scripts returned no project script |

### Key Source References

- `apps/dsa-web/src/pages/UserScannerPage.tsx`: `ScannerExportRow`, `buildScannerExportRow`, `buildScannerCsv`, `buildScannerExportFilename`, and `downloadScannerCsv`.
- `apps/dsa-web/src/pages/UserScannerPage.tsx`: run-level `导出 CSV` / `Export CSV` action in the Scanner more-actions menu.
- `apps/dsa-web/src/pages/UserScannerPage.tsx`: candidate-level developer fields disclosure with `导出` / `Export`.
- `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx`: test `exports csv with expected scanner result headers` asserts the current English header row.
- `apps/dsa-web/src/i18n/core.ts`: Scanner route chrome contains localized export copy such as `导出 CSV` / `Export CSV`; no localized CSV header map exists.
- `docs/archive/audits/frontend/wolfystock-chinese-form-label-review.md`: classifies Scanner CSV headers and generated filenames as P3 export artifacts requiring a product decision before implementation.
- `docs/frontend/visual-system.md`: Chinese route chrome should localize except accepted domain/developer terms.
- `docs/operations/parallel-codex-playbook.md`: docs-only tasks should use targeted inspection, stage explicit paths only, and avoid unrelated files.

### Compatibility-Sensitive Fields

These fields should remain stable in default machine CSV:

- `rank`
- `symbol`
- `scannerScore`
- `entryRange`
- `target`
- `stop`
- `universeType`
- `generatedAt`
- `runId`

These fields can carry localized or source-language display values while keeping stable headers:

- `name`
- `reason`
- `risk`
- `theme`
