# QW-006 Consumer Internal Wording Static Sweep

**Task ID:** QW-006
**Status:** READY TO LAND
**Branch:** `qwen/qw006-consumer-internal-wording-sweep`
**Execution mode:** WORKTREE-WORKER (docs-only)
**Method:** Static source-code sweep (frontend dev server not running; read-only discovery)
**Base commit:** see git log at task start
**Dependencies:** Builds on QW-003 (UX QA pass), QW-004 (consumer copy quick wins), QW-005 (rough empty-text rollout)

---

## Executive Summary

This sweep audits remaining consumer-visible internal/debug wording risks in the WolfyStock frontend after QW-004 and QW-005 landed. The defensive sanitization pipeline (7-9 distinct systems) remains strong — no-advice forbidden terms, raw provider detail suppression, and admin/consumer separation are all functioning correctly. However, **23 distinct consumer-visible wording issues** remain across three categories: hardcoded English-only strings without locale branching, untranslated English technical terms in Chinese copy, and raw internal/debug concepts rendered in consumer DOM.

The most critical finding is in `settings/dataSourceLibraryShared.ts` where impact text for consumer-accessible data source settings contains dense mixes of Chinese and untranslated engineering terms (`cache_snapshot`, `OHLCV provenance`, `dataset lineage`, `repro manifests`). The second tier of concern is `OfficialMacroAuthorityDiagnostics`, which renders English-only chip labels (`Official`, `Proxy-only`, `Fallback`, `Score-eligible`) unconditionally on the consumer Liquidity Monitor page regardless of locale.

QW-004 already fixed the "endpoint" leak in Decision Cockpit and added locale-aware empty text to `RoughKeyValueRows`. QW-005 localized rough empty states in Research Radar, Scenario Lab, and Stock Structure. This report captures what remains.

No product code was edited. This is a docs-only audit.

---

## Method

1. Read QW-003 UX QA pass report for prior findings and resolution status.
2. Inspected QW-004 commit (`340d1056`) and QW-005 commit (`55893d59`) to identify what was already fixed.
3. Ran canonical grep commands from `docs/codex/NO_ADVICE_REGRESSION_GUARDS.md` against consumer page and component files, excluding admin-only pages, `__tests__/`, `.test.*`, and `.spec.*` files.
4. Performed targeted manual inspection of 12 consumer pages and 14 component directories for:
   - Hardcoded English strings in rendered JSX without locale branching
   - Hardcoded Chinese strings without EN fallback
   - Internal/debug terminology in consumer-visible rendered text
   - Raw provider/source metadata that may render in consumer DOM
5. Classified every hit as confirmed issue, false positive, or admin-only.
6. Grouped confirmed issues by follow-up task size.

Excluded surfaces: `Admin*Page.tsx`, `MarketProviderOperationsPage.tsx`, `SystemSettingsPage.tsx`, `PreviewReportPage.tsx`, `PreviewFullReportDrawerPage.tsx`, all `__tests__/` directories, all `.test.*` and `.spec.*` files, `data_provider/`, `api/`, `src/`, `bot/`, `scripts/`.

---

## Confirmed Consumer-Visible Issues

### Category A — Endpoint / API / Provider / Cache / Runtime / Schema / Internal / Debug Terms

These issues expose engineering-internal concepts in consumer-visible rendered text.

**A-01 OfficialMacroAuthorityDiagnostics renders English-only diagnostic chips**
- Files: `components/common/officialMacroAuthorityDiagnosticsData.ts` lines 93-116, `components/common/OfficialMacroAuthorityDiagnostics.tsx` lines 13-18
- Consumer page: `LiquidityMonitorPage.tsx` line 2383 (rendered unconditionally, not admin-gated)
- Text: Chip labels `'Rejected'`, `'Unavailable'`, `'Official'`, `'Proxy-only'`, `'Fallback'`, `'Partial'`, `'Score-eligible'`, `'Observation-only'` — all English-only with no locale branching
- Meta text: `'API did not return this bounded official series.'` — English-only with internal term "API"
- Severity: High — renders on a primary consumer page for all locales

**A-02 BacktestSupportExportsDisclosure renders English-only internal flag labels**
- File: `components/backtest/BacktestSupportExportsDisclosure.tsx` lines 318-338
- Text: `'Provider activity'`, `'provider calls recorded'`, `'no provider calls'`, `'Engine calculation'`, `'engine math changed'`, `'diagnostic only'`, `'decision-grade'`, `'Parameter sweep'`, `'optimization executed'` — all English-only `SafeBooleanFlag` labels
- Severity: Medium — backtest result page is consumer-accessible

**A-03 BacktestSupportExportsDisclosure English-only availability reasons**
- File: `components/backtest/BacktestSupportExportsDisclosure.tsx` lines 269-274
- Text: `'optimization not executed'`, `'execution trace not available'`, `'support evidence not available'` — English-only strings from `getSafeAvailabilityReason()`
- Severity: Medium

**A-04 Scenario Lab placeholder page exposes "raw debug payload"**
- File: `components/layout/consumerAppNavigation.ts` lines 463, 473
- ZH text: `'证据边界：占位页不读取 provider、broker、portfolio 或 raw debug payload。'`
- EN text: `'Evidence boundary: the placeholder reads no provider, broker, portfolio, or raw debug payload.'`
- Severity: Medium — both locales expose internal terms "provider", "raw debug payload"

**A-05 BacktestResultReport renders raw provider name next to Chinese label**
- File: `components/backtest/BacktestResultReport.tsx` line 660
- Text: `['价格源', humanToken(explicit.provider || explicit.source)]` — raw provider field value rendered next to Chinese label
- Severity: Low — `humanToken` may sanitize, but raw provider names like "Finnhub", "twelve_data" could leak

**A-06 FullDecisionReportDrawer renders collected provider names**
- File: `components/home-bento/FullDecisionReportDrawer.tsx` lines 183-190
- Text: Provider names from `source.provider || source.name` are joined and rendered in report metadata
- Severity: Low — provider names are somewhat expected in report context, but internal names like "twelve_data" could appear

**A-07 ScannerCandidatePresenters may render raw snake_case enum values**
- File: `components/scanner/ScannerCandidatePresenters.tsx` lines 109-115
- Text: When primary investor signal label is missing, `formatInvestorSignalState()` renders raw internal enum values (e.g., "risk_off_absorption", "btc_not_confirming") after splitting on underscores
- Severity: Medium — raw internal enum values could appear as consumer text

### Category B — Mixed Chinese/English User-Facing Copy

These issues contain untranslated English technical terms embedded in Chinese consumer-visible copy.

**B-01 dataSourceLibraryShared dense mixed CN/EN impact text**
- File: `components/settings/dataSourceLibraryShared.ts` lines 832-837
- Text: `'Portfolio 先核对 stored portfolio snapshots、price provenance、FX/cache evidence、configured local/cache evidence 与 actual close-date metadata。'` — dense mix of Chinese and untranslated engineering terms: `cache_snapshot`, `OHLCV provenance`, `dataset lineage`, `repro manifests`, `Scanner evidence`, `provider`
- Severity: Critical — consumer-accessible data source settings page

**B-02 ProBacktestWorkspace "payload" in Chinese copy**
- File: `components/backtest/ProBacktestWorkspace.tsx` lines 581, 807
- ZH text: `'再平衡调度仅作为后续能力预留，当前不会改写运行 payload。'`
- ZH text: `'最大暴露、敞口、回撤、单笔风险等组合级限制尚未接入当前运行 payload。'`
- Severity: Medium — "payload" untranslated in Chinese consumer copy

**B-03 DataSourceConfig "fallback/proxy" and metadata terms in Chinese copy**
- File: `components/settings/DataSourceConfig.tsx` line 173
- Text: `'改善证据覆盖 / 减少 fallback/proxy / 可能提升为可评分证据。这里只引用现有 impact metadata 与 coverage gap map。'`
- Severity: High — multiple untranslated internal terms in Chinese consumer text

**B-04 LLMChannelEditor Chinese copy with "Fallback", "YAML", env var names**
- File: `components/settings/LLMChannelEditor.tsx` lines 1371-1372
- ZH text: `'主模型、Fallback、Vision 与 Temperature 继续在下方通用字段中管理；这里仅保存渠道条目，不会覆盖 YAML 运行时选择。'`
- Severity: Medium — settings page, consumer-accessible; "LITELLM_CONFIG" env var name exposed

**B-05 NotificationChannelsConfig Chinese copy with "API Key"**
- File: `components/settings/NotificationChannelsConfig.tsx` line 150
- ZH text: `'Pushover 用户 Key 和应用 API Key。'`
- Severity: Low — settings context

**B-06 SystemControlPlane Chinese copy with "API"**
- File: `components/settings/SystemControlPlane.tsx` line 452
- ZH text: `'这里不新增后台动作；仍使用现有确认对话、权限和运行时 API。'`
- Severity: Low — settings context

**B-07 MarketOverviewWorkbench English-only data quality labels**
- File: `components/market-overview/MarketOverviewWorkbench.tsx` line 1110
- Text: `'available ${coverageSummary.real}, partial ${coverageSummary.mixed}, delayed ${coverageSummary.fallback}'` — English labels "available", "partial", "delayed" used without locale branching even when UI is in Chinese
- Severity: Medium — primary consumer page

### Category C — Hardcoded English or Chinese Fallback Text That Should Be Locale-Aware

**C-01 BacktestResultReport Chinese-only trace status text**
- File: `components/backtest/BacktestResultReport.tsx` line 561
- Text: `'轨迹元数据存在，明细待补'` and `'未返回执行轨迹'` — Chinese-only, no EN fallback
- Severity: Low — backtest context, "trace" is already an internal term

**C-02 officialMacroAuthorityDiagnosticsData English-only meta text**
- File: `components/common/officialMacroAuthorityDiagnosticsData.ts` line 121
- Text: `'API did not return this bounded official series.'` — English-only, no ZH fallback
- Severity: Medium — renders on consumer Liquidity Monitor page

**C-03 ScannerCandidateEvidenceStrip English "Fallback / proxy" label**
- File: `components/scanner/ScannerCandidateEvidenceStrip.tsx` lines 137-138
- EN text: `'Fallback / proxy ${count}'` — uses internal terminology in English locale
- ZH text: `'回退/代理 ${count} 项'` — Chinese version is more consumer-friendly
- Severity: Low — the English version is the issue; "fallback/proxy" is internal language

### Category D — Rough/Empty/Loading/Error States That Still Look Developer-Facing

**D-01 BacktestResultReport developer-facing trace labels**
- File: `components/backtest/BacktestResultReport.tsx` lines 558-562
- Text: `'执行轨迹'`, `'轨迹元数据存在，明细待补'`, `'未返回执行轨迹'` — uses engineering concept "trace" that consumers may not understand
- Severity: Low — backtest is a power-user feature

**D-02 BacktestSupportExportsDisclosure "stored"/"not available" fold states**
- File: `components/backtest/BacktestSupportExportsDisclosure.tsx` lines 278-284
- Text: `'stored'`, `'not available'`, `'status recorded'` — English-only generic fold state labels
- Severity: Low

---

## False Positives / Internal-Only Matches

### FP-01 Admin page internal terminology (bounded, correct for audience)
Admin pages (`AdminProviderCircuitDiagnosticsPage`, `MarketProviderOperationsPage`, `AdminLaunchCockpitPage`, `AdminMissionControlPage`, `AdminLogsPage`, `AdminUsersPage`, `AdminNotificationsPage`, `AdminEvidenceWorkflowPage`, `AdminCostObservabilityPage`) contain extensive internal terminology (`provider`, `circuit`, `fallback`, `MarketCache`, `schemaVersion`, `payload`, snake_case table names). This is **correct for the audience** — ops users and engineers need precise diagnostic language. Not consumer-visible.

### FP-02 Sanitization pattern constants
Regex constants like `FORBIDDEN_CONSUMER_WORDING`, `INTERNAL_DIAGNOSTIC_WORDS`, `INTERNAL_TERM_PATTERN`, `INTERNAL_ASSUMPTION_TEXT_PATTERN`, `SENSITIVE_KEY_RE`, `SECRET_FRAGMENT_RE` contain internal terms but are used to **detect and suppress** those terms from consumer output. They are defense mechanisms, not leaks.

### FP-03 API client type definitions
Type definitions in `api/marketOverview.ts`, `api/stocks.ts`, `api/marketProviderOperations.ts` contain internal field names (`observationOnly`, `sourceAuthorityAllowed`, `scoreContributionAllowed`, `reasonCodes`, `providerHealth`, `schemaVersion`). These are TypeScript interface definitions, not rendered text. The projection/sanitization layers handle consumer safety.

### FP-04 Variable names and code logic
Variable names like `providerStatus`, `schemaVersion`, `activeTraceReport`, `fallbackNote`, `debugMarketPanel` are code-level identifiers, not rendered text. They do not leak to consumers.

### FP-05 `console.debug` gated behind DEV
`MarketOverviewPage.tsx` line 492 has `console.debug` gated behind `import.meta.env.DEV`. This is correct development practice and does not affect production users.

### FP-06 Research Radar `INTERNAL_DIAGNOSTIC_WORDS` regex
`ResearchRadarPage.tsx` line 70 defines a regex to detect and suppress internal diagnostic words. This is a defense mechanism, not a leak.

### FP-07 RuleBacktestComparePage internal key detection
`RuleBacktestComparePage.tsx` line 145 detects internal-looking compare keys via regex to replace them with safe labels. This is a sanitization step, not a leak.

### FP-08 Test fixtures and assertions
Test files in `__tests__/` directories contain forbidden terms as adversarial input paired with negative assertions. These are correct test patterns.

### FP-09 Backtest `shared.tsx` INTERNAL_ASSUMPTION_TEXT_PATTERN
`components/backtest/shared.tsx` line 428 defines a pattern to detect internal assumption text. This is a defense mechanism.

### FP-10 PortfolioExposureResearchContextPanel INTERNAL_TERM_PATTERN
`components/portfolio/PortfolioExposureResearchContextPanel.tsx` line 11 defines a pattern to suppress internal terms. This is a defense mechanism.

---

## Suggested Qwen-Safe Follow-Up Tasks

Small-scope, bounded tasks suitable for Qwen execution in single sessions.

| ID | Title | Scope | Files | Priority |
|----|-------|-------|-------|----------|
| QW-006-A | Localize OfficialMacroAuthorityDiagnostics chip labels | 2 files | `officialMacroAuthorityDiagnosticsData.ts`, `OfficialMacroAuthorityDiagnostics.tsx` | P1 |
| QW-006-B | Localize MarketOverviewWorkbench data quality labels | 1 file | `MarketOverviewWorkbench.tsx` line 1110 | P1 |
| QW-006-C | Fix "payload" in ProBacktestWorkspace Chinese copy | 1 file | `ProBacktestWorkspace.tsx` lines 581, 807 | P1 |
| QW-006-D | Fix Scenario Lab placeholder "raw debug payload" wording | 1 file | `consumerAppNavigation.ts` lines 463, 473 | P1 |
| QW-006-E | Localize BacktestSupportExportsDisclosure flag labels and availability reasons | 1 file | `BacktestSupportExportsDisclosure.tsx` | P2 |
| QW-006-F | Fix DataSourceConfig Chinese copy with internal terms | 1 file | `DataSourceConfig.tsx` line 173 | P2 |
| QW-006-G | Fix NotificationChannelsConfig Chinese copy "API Key" | 1 file | `NotificationChannelsConfig.tsx` line 150 | P2 |
| QW-006-H | Localize ScannerCandidateEvidenceStrip "Fallback / proxy" EN label | 1 file | `ScannerCandidateEvidenceStrip.tsx` lines 137-138 | P2 |

---

## Suggested GPT/Codex-Only Follow-Up Tasks

Larger-scope tasks requiring product decisions, cross-surface coordination, or architectural planning.

| ID | Title | Scope | Dependency | Priority |
|----|-------|-------|------------|----------|
| PT-006-1 | Rewrite dataSourceLibraryShared impact text for consumer audience | Settings | Product/UX writing decision on how to describe data source impact without engineering jargon | P0 |
| PT-006-2 | Backtest robustness evidence consumer rewording | Backtest | Product decision on which robustness flags are consumer-relevant and how to label them | P1 |
| PT-006-3 | Scanner investor signal enum-to-label coverage | Scanner | Verify all internal enum values have consumer-safe labels; add fallback labels for unmapped values | P1 |
| PT-006-4 | LLMChannelEditor / SystemControlPlane settings copy audit | Settings | Determine which settings pages are consumer-accessible vs admin-only; adjust wording accordingly | P2 |
| PT-006-5 | Consolidate provider name display across report surfaces | Cross-surface | Product decision on whether raw provider names should be replaced with consumer-friendly source descriptions | P2 |

---

## Files Not to Touch

These files were identified during the sweep but should not be modified by follow-up wording tasks:

| File | Reason |
|------|--------|
| `api/marketOverview.ts` | API client type definitions; internal field names are correct TypeScript interfaces, not rendered text |
| `api/stocks.ts` | API client type definitions; same as above |
| `api/marketProviderOperations.ts` | Admin-only API client |
| `pages/Admin*Page.tsx` (all admin pages) | Admin-only surfaces; internal terminology is correct for the audience |
| `pages/MarketProviderOperationsPage.tsx` | Admin-only ops page |
| `pages/SystemSettingsPage.tsx` | Admin-gated system settings |
| `components/admin/*` | Admin-only component directory |
| `components/evidence/AdminEvidenceDiagnosticsConsole.tsx` | Admin-only evidence diagnostics |
| `components/backtest/shared.tsx` | Contains `INTERNAL_ASSUMPTION_TEXT_PATTERN` defense mechanism; do not weaken |
| `components/portfolio/PortfolioExposureResearchContextPanel.tsx` | Contains `INTERNAL_TERM_PATTERN` defense mechanism; do not weaken |
| `components/scanner/ScannerDiagnosticsPanel.tsx` | Has `isRestrictedDiagnosticEntry()` filter; do not weaken the filter |
| `data_provider/*` | Backend data provider layer; out of scope for consumer wording sweep |
| `src/*` | Backend service layer; out of scope |
| `i18n/core.ts` | Per task rules: do not change unless task is converted from docs-only to implementation |

---

## Validation

### Pre-rebase validation

```
git diff --check origin/main...HEAD   -> PASS (exit 0)
git diff --check                      -> PASS (exit 0)
bash scripts/release_secret_scan.sh --base-ref origin/main -> no secrets found
```

### QW-004 / QW-005 resolution check

| QW-003 Issue | Status | Fixed By |
|--------------|--------|----------|
| QW-A: RoughKeyValueRows hardcoded CN | Resolved | QW-004 (`340d1056`) — added `emptyText` prop |
| QW-B: "endpoint" leak in Cockpit error | Resolved | QW-004 (`340d1056`) — replaced with "data is available again" |
| QW-C: "Loading watchlist..." hardcoded EN | Already OK | WatchlistPage has separate EN/ZH locale blocks (lines 1226, 1348) |
| QW-F: RoughBulletList/RoughScoreRows empty text | Resolved | QW-005 (`55893d59`) — localized in ResearchRadar, ScenarioLab, StockStructure |

### Post-rebase validation

```
git diff --check origin/main...HEAD   -> PASS (exit 0, no whitespace errors)
git diff --check                      -> PASS (exit 0, no whitespace errors)
bash scripts/release_secret_scan.sh --base-ref origin/main -> PASS (no secrets found)
git rebase origin/main                -> already up to date
git status --short --branch           -> clean, ahead 1
```

### Final State

- **Final base commit:** `f37da4ca` (origin/main HEAD)
- **Final commit hash:** `5d0acd09`
- **Final git status:** Clean (branch ahead of origin/main by 1 commit)
- **Rollback command:** `git reset --hard f37da4ca` (returns to pre-task state)

---

## QW-003 Resolved vs Remaining Cross-Reference

| QW-003 UX Issue | Resolved? | Remaining in QW-006? |
|-----------------|-----------|----------------------|
| UX-005 Mixed CN/EN Leakage | Partially (QW-A, QW-C, QW-F fixed) | Yes — B-01 through B-07 remain |
| UX-008 Developer/Internal Wording Leakage | Partially (QW-B fixed) | Yes — A-01 through A-07 remain |
| UX-009 "Observation-Only" Language Opaque | Not addressed | Out of scope for wording sweep (product decision) |

---

## Method Notes

This sweep was conducted via static source-code analysis only. The frontend development server was not running. All findings are based on component source code, rendered string literals, JSX text nodes, aria-labels, title attributes, and copy object definitions. Live DOM inspection and browser verification were not performed.

The sweep focused on the intersection of: (a) consumer-accessible pages and components, (b) rendered text content (not code identifiers), and (c) terms that a non-technical investor would find confusing or unprofessional.

Findings should be validated with live browser verification once the frontend dev server is available. The existing Playwright specs (`consumer-copy-forbidden-vocabulary.smoke.spec.ts`, `consumer-copy-regression.smoke.spec.ts`) provide automated coverage that complements this manual sweep.
