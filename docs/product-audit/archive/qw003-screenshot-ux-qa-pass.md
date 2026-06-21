# QW-003 Screenshot UX QA Pass

**Task ID:** QW-003
**Status:** READY TO LAND
**Branch:** `qwen/qw003-screenshot-ux-qa-pass`
**Execution mode:** WORKTREE-WORKER (docs-only, read-only discovery)
**Method:** Source-code static analysis (frontend dev server not running; backend port 8000 responsive)
**Base commit:** `e2a408c2` (origin/main HEAD, 2026-06-19)

---

## Executive Summary

WolfyStock's consumer UI is built on a strong defensive architecture: no-advice guards, consumer-safe copy sanitization, bilingual support, and a well-defined data-quality UX contract. However, the product currently reads more like an **internal research diagnostic console** than a **professional research cockpit for investors**. Three structural forces create this impression: (1) data is frequently unavailable or degraded due to intentional quality gates, so users encounter empty states far more often than populated ones; (2) the visual language leans terminal-density with monospace metrics, five chip variants, and 495+ chip/badge usages across 26 page files; (3) three competing design languages coexist without a unified surface grammar, making page-to-page transitions feel inconsistent.

The good news: the defensive copy layer is solid, the empty-state architecture is well-designed with forward-looking guidance, and the sanitization pipeline is multi-layered. The fixes needed are primarily **surface-level**: consolidate the visual language, reduce badge noise, improve first-run onboarding flow, resolve i18n gaps, and elevate the empty/degraded experience from "diagnostic unavailable" to "research in progress."

This report identifies 10 prioritized issues, page-by-page findings, quick wins for Qwen execution, and larger product tasks for GPT/Codex planning. No product code was edited.

---

## Top 10 UX Issues

### UX-001 P0 — Data-Poor Default Experience

**Severity:** P0 · Product-defining
**Surfaces affected:** All 12 consumer pages
**Root cause:** T-1758 lineage — intentional quality gates reject fallback/stale/proxy data, so evidence surfaces are empty by design until upstream data reliability improves.

The typical first visit to Decision Cockpit, Research Radar, Liquidity Monitor, or Rotation Radar shows an empty-state panel, a "data unavailable" notice, or a "low confidence" indicator. The user has no way to distinguish "the system is working correctly but data is insufficient" from "the system is broken." A normal user would conclude the product doesn't work.

The empty-state architecture is technically well-designed (7 cases with bilingual copy, severity levels, next-research-step guidance). But the **cumulative impression** across surfaces is one of emptiness. Users see "暂不可用" so frequently that the phrase loses meaning.

**What a normal user sees:** A research cockpit with no research.

**Recommendation:** Until T-1758 lineage data fixes land, treat empty states as the **primary product surface**, not a fallback. Every empty state needs a "what you can do right now" path that feels productive — not just a "check back later" message. See UX-007 for the onboarding dimension.

---

### UX-002 P0 — Three Competing Design Languages

**Severity:** P0 · Visual coherence
**Surfaces affected:** All consumer pages

Three distinct visual systems coexist without a unifying surface grammar:

| System | Pages using it | Character |
|--------|---------------|-----------|
| **ResearchConsole** (ConsoleBoard + ContextRail + RoughSectionCard) | Decision Cockpit, Research Radar, Stock Structure, Scenario Lab | Editorial, narrative, section-card layout |
| **DenseWorkbench** (DensePageHeader + DenseTableShell + DenseRows) | Scanner, Watchlist | Data-table, command-bar, high-density |
| **TerminalPrimitives** (TerminalGrid + TerminalPanel + TerminalChip) | Market Overview, Liquidity Monitor, Rotation Radar, Options Lab, Portfolio | Dashboard-monitor, metric cards |

A user moving from Decision Cockpit (ResearchConsole) to Scanner (DenseWorkbench) to Liquidity Monitor (Terminal) experiences three different page shells, three different heading patterns, three different chip systems, and three different information densities. The product feels like three separate tools.

**Recommendation:** Define a single consumer page shell with consistent heading, navigation breadcrumb, status strip, and section patterns. The three systems can coexist as content layout variants, but the chrome (header, nav, status, disclosure) should be unified.

---

### UX-003 P1 — Badge / Chip / Pill Proliferation

**Severity:** P1 · Visual noise
**Surfaces affected:** Liquidity Monitor (50 usages), Watchlist (48), Market Rotation Radar (30), Portfolio (29), Decision Cockpit (20), Home (18)

The product uses `TerminalChip` (5 variants), `StatusBadge` (5 tones), `PillBadge`, `FieldChip`, `DataFreshnessBadge`, and evidence trust chips across every surface. Total across 26 page files: **495 chip/badge usages**. A single Scanner candidate row can display 6-8 chips: status, trust level, evidence quality, freshness, market tag, conclusion band, plus diagnostic pills.

While `maxLimitationLabels` in the evidence display system caps individual limitation lists, there is no **global** chip budget per view region. When multiple evidence sources stack their chips, the result is a diagnostic strip that requires engineering literacy to parse.

**Recommendation:** Establish a chip budget per view region (e.g., max 3 chips per row, max 5 per panel header). Consolidate redundant chips — e.g., freshness + trust + evidence quality could collapse into a single composite evidence-health indicator.

---

### UX-004 P1 — Low Contrast Accessibility Failures

**Severity:** P1 · Accessibility (WCAG AA)
**Surfaces affected:** ConsumerOnboardingCtaPanel, SidebarNav admin dropdown, multiple component section labels

Multiple UI elements use extremely low contrast text:

| Location | Style | Estimated contrast ratio |
|----------|-------|------------------------|
| Onboarding CTA section labels | `text-[10px] text-white/38` | ~2.3:1 (fails AA) |
| Admin dropdown group labels | `text-[10px] text-white/34` | ~2.0:1 (fails AA) |
| Terminal metric labels | `text-[11px] text-white/40` | ~2.5:1 (fails AA) |
| Empty state secondary text | `text-xs text-white/50` | ~3.5:1 (marginal) |

WCAG AA requires 4.5:1 for normal text and 3:1 for large text. These elements consistently fail, meaning users with low vision, aging eyes, or non-retina displays will struggle to read section headers and metric labels.

**Recommendation:** Floor all consumer-visible text opacity at `text-white/55` (approximately 4.5:1 on a dark background). Section labels at 10-11px should be `text-white/60` minimum.

---

### UX-005 P1 — Mixed CN/EN Leakage in Consumer Strings

**Severity:** P1 · Localization quality
**Surfaces affected:** Multiple pages, Options Lab, Onboarding CTA, Decision Report Drawer

Despite strong bilingual infrastructure, several categories of mixed-language copy leak through:

**Category A — English product names in Chinese sentences:**
- Onboarding CTA: `运行 Scanner` (ZH locale keeps "Scanner" in English)
- Options Lab: `Call / Put 链`, `Call / Put IV 差`, `IV / 希腊值`
- Full Decision Report Drawer: `MA alignment`, `Volume / turnover` as field labels

**Category B — Hardcoded Chinese without EN fallback:**
- `roughShellShared.tsx` line 101: `暂无可展示条目。` hardcoded in `RoughKeyValueRows` with no locale parameter
- `WatchlistPage.tsx` line 1226: `'Loading watchlist...'` hardcoded without locale branching

**Category C — Untranslated domain terms:**
- `Gamma` kept as-is in Chinese consumer status labels — most Chinese investors won't know this term
- `Crypto Beta` kept in Chinese liquidity regime labels

**Recommendation:** Fix the hardcoded strings as quick wins. For domain terms like Gamma and IV, add consumer-friendly Chinese explanations on first encounter (tooltip or inline gloss).

---

### UX-006 P1 — Options Lab Disclaimer Overload

**Severity:** P1 · First-impression friction
**Surfaces affected:** Options Lab

Options Lab displays **6+ separate boundary statements** before the user can interact:

1. "期权可能归零，IV、Theta、流动性与价差会改变到期前估值。本模块仅做只读情景分析。"
2. "仅做只读情景分析，不构成执行指令。"
3. "不构成买卖建议"
4. "不会触发外部执行"
5. "不连接外部执行通道"
6. "不改动投资组合"
7. "仅供观察，不作为结论依据"
8. "数据不足，暂不形成结论"

While each statement serves a legal/safety purpose, the cumulative effect is a **wall of disclaimers** that a normal user would interpret as "this tool is dangerous" or "I shouldn't use this." No other consumer product surfaces this many safety notices before letting the user work.

**Recommendation:** Consolidate into a single compact boundary panel with one summary sentence and a collapsible "details" disclosure. The current `TerminalDisclosure` pattern already exists for this purpose. Example: "本模块仅做只读情景观察，不生成买卖指令或执行操作。[了解边界细节]"

---

### UX-007 P1 — Fragmented First-Run Experience

**Severity:** P1 · Onboarding
**Surfaces affected:** All authenticated pages

`ConsumerOnboardingCtaPanel` appears independently on Decision Cockpit, Research Radar, Watchlist, Portfolio, and Scanner. Each instance shows route-specific CTA cards, a starter flow, a checklist, and detected conditions. But there is no **unified first-run journey** that guides the user through the product's intended workflow: Market Overview → Decision Cockpit → Scanner → Watchlist → Research Radar → Stock Structure.

The user encounters onboarding panels on 5 different pages, each with different cards and different detected conditions. A first-time user who visits Decision Cockpit, then Scanner, then Watchlist sees three separate onboarding panels that each assume the user understands the overall workflow.

**Recommendation:** Create a single "Welcome to WolfyStock" guided tour that appears once, on first visit, and walks through the research workflow in 4-5 steps. Individual page onboarding can remain but should be secondary to the initial guided tour.

---

### UX-008 P2 — Developer/Internal Wording Leakage

**Severity:** P2 · Professionalism
**Surfaces affected:** Decision Cockpit (minor), admin pages (severe but bounded)

**Consumer-visible leak:** `MarketDecisionCockpitPage.tsx` line 614 uses the word **"endpoint"** in a consumer-visible error message: `"Retry after the briefing endpoint responds again."` A normal user doesn't know what an endpoint is.

**Admin-visible leaks (bounded but high density):**
- `AdminProviderCircuitDiagnosticsPage.tsx`: `provider blocking`, `advisory-only`, `MarketCache`, `circuit 写入链路`, `observer 接入状态`, raw snake_case table names (`provider_quota_windows`, `provider_circuit_states`)
- `MarketProviderOperationsPage.tsx`: `credential required`, `cache required`, `official-public cache-only`, `score-blocked`

The sanitization pipeline has 7-9 distinct systems, each with its own pattern set. While the coverage is strong, the fragmented architecture means new internal terms could slip through gaps.

**Recommendation:** Fix the "endpoint" leak immediately (quick win). For admin pages, accept that ops-facing terminology is appropriate for the audience but consolidate the sanitization pipeline into a single shared utility.

---

### UX-009 P2 — "Observation-Only" Language is Opaque

**Severity:** P2 · Comprehension
**Surfaces affected:** All research surfaces (Decision Cockpit, Research Radar, Stock Structure, Scenario Lab)

The phrase "仅供观察" / "Research observation only" appears on every research surface as a boundary chip or disclosure. While legally and ethically important, the phrase is **opaque to normal users**. A typical investor would not understand:

- What "observation" means in this context (can I act on this?)
- What the alternative would be (if this is observation-only, where is the "real" analysis?)
- Why the tool keeps repeating this phrase

Similarly, "非判断等级" / "Not decision grade" and "不生成行动指令" / "No action instruction" are internal classification terms that describe system posture, not user benefit.

**Recommendation:** Reframe boundary language from system-centric ("observation only") to user-centric ("for your research reference — combine with your own analysis before deciding"). The no-advice intent must remain, but the wording should feel like guidance, not a system classification.

---

### UX-010 P2 — Monospace Metrics + Terminal Aesthetic

**Severity:** P2 · First-impression tone
**Surfaces affected:** All pages using TerminalPrimitives

The `TerminalMetric` component uses `font-mono tracking-tight` for all numeric values, combined with 11px muted labels and dense grid layouts. The `WolfyCommandBar` provides a command-line interaction pattern. `ConsoleBoard` and `ConsoleContextRail` borrow from IDE layouts. The overall aesthetic reads as **developer tool / Bloomberg terminal** rather than **professional research platform**.

This is a deliberate design choice that may appeal to sophisticated quant users, but it alienates the target audience of individual investors who want research support, not a trading terminal.

**Recommendation:** Reserve monospace for raw data tables and specific numeric comparisons. Use proportional fonts for summary metrics, section headers, and narrative sections. The ResearchConsole pages already use a more editorial style — extend that warmth to the Terminal pages.

---

## Page-by-Page Findings

### Home (HomeSurfacePage / HomeBentoDashboardPage)

**Route:** `/`
**Design system:** Custom bento grid
**15-second impression:** Data-dense dashboard with multiple chart types, evidence strips, and health summaries. Feels like a mission control center.

- Evidence citation domains use bilingual labels (价格历史 / Price history) — well-localized
- Citation status chips (可引/受限/待补/阻断) are clean but could benefit from tooltip explanations
- Guest market snapshot has 4 states (loading/ready/limited/unavailable) — good coverage
- Compliance filter strips trade-action words from generated reports — invisible to user, which is correct
- **Risk:** Home is not in the sidebar nav, so users may not return to it after navigating away

### Market Overview (MarketOverviewPage)

**Route:** `/market-overview`
**Design system:** TerminalPrimitives with MarketOverviewWorkbench
**15-second impression:** Professional monitoring dashboard with panel cards for indices, volatility, crypto, sentiment, and macro indicators.

- Extensive fallback system (FALLBACK_TEMPERATURE, FALLBACK_BRIEFING, etc.) — user sees stale data rather than errors, which is the right tradeoff
- Panel-level error copy is consumer-safe: "数据更新超时", "部分数据暂不可用"
- `DataFreshnessBadge` with 6 freshness labels (实时/缓存/延迟/过期/备用/异常) — 6 states may be too many for normal users to distinguish
- Auto-revalidation with max 3 attempts — invisible, which is correct
- **Risk:** The distinction between "缓存" (cached) and "备用" (fallback) is an internal concept; users should see "最近可用数据" for both

### Decision Cockpit (MarketDecisionCockpitPage)

**Route:** `/market/decision-cockpit`
**Design system:** ResearchConsole
**15-second impression:** Editorial-style research briefing with structured sections for market regime, drivers, research priorities, and evidence gaps.

- `FORBIDDEN_CONSUMER_WORDING` regex actively sanitizes advice terms — invisible, correct
- Driver labels are domain-specific but untranslated jargon: "Gamma观察", "广度参与", "波动结构" — a normal user needs context for these
- Daily Intelligence sub-section adds depth but increases page length significantly
- "endpoint" leak in error message (line 614) — see UX-008
- Section empty states ("暂未整理变化摘要", "暂未整理明确的置信边界") are well-written but repetitive when multiple sections are empty simultaneously
- **Risk:** When data is poor, the entire page becomes a list of "暂未整理..." empty states, reinforcing the "nothing works" impression

### Liquidity Monitor (LiquidityMonitorPage)

**Route:** `/market/liquidity-monitor`
**Design system:** TerminalPrimitives
**15-second impression:** Dense data-monitoring surface with regime indicators, impulse synthesis, and evidence tables.

- 50 TerminalChip usages — highest density on any consumer page
- Regime labels (充裕/支撑/中性/偏紧/紧张/不可用) are clear and well-translated
- Sub-type labels (广谱流动性扩张, Crypto Beta 扩张, 利率驱动收紧) mix professional financial language with untranslated English ("Crypto Beta")
- `OfficialMacroAuthorityDiagnostics` component name suggests internal diagnostics but the rendered content is consumer-safe
- **Risk:** The combination of regime chip + impulse chip + freshness chip + evidence chip per indicator creates a 4-chip-per-row pattern that is visually overwhelming

### Rotation Radar (MarketRotationRadarPage)

**Route:** `/market/rotation-radar`
**Design system:** TerminalPrimitives with DataWorkbenchFrame
**15-second impression:** Theme-tracking dashboard with flow-state indicators and market filters.

- Stage labels (早期观察/确认轮动/延展观察/降温观察/信号较弱) are clear progression markers
- Theme flow states (领涨观察/扩散跟涨/轮动切换/拥挤观察/热度回落/信号分化/数据不足) — 7 states is a lot for a single dimension
- English theme names are actively translated: "AI Applications" → "AI 应用", "Semiconductor Real Flow" → "半导体确认信号" — good localization
- Loading timeout with fallback (5s fallback, 12s timeout) — good UX
- **Risk:** Non-US markets are taxonomy-only by design (per T-1758), so A股/港股/加密 users will consistently see limited data

### Research Radar (ResearchRadarPage)

**Route:** `/research/radar`
**Design system:** ResearchConsole
**15-second impression:** Research queue management interface with prioritized items, driver scores, and evidence freshness.

- `ConsumerResearchEmptyState` with 7 cases and next-research-step guidance — strongest empty-state pattern in the product
- Queue source labels (Watchlist/Scanner/Market/补充研究) are clear
- Priority tiers (紧急复核/持续跟进/观察) use appropriate urgency language without being alarmist
- Driver labels (相对强弱/主题匹配/市场匹配/量能支持/结构质量/事件就绪度/证据质量) are professional and well-translated
- **Risk:** The page fails closed when prerequisite scanner/watchlist evidence is absent — user sees empty state without understanding they need to run a scan first

### Stock Structure (StockStructureDecisionEntryPage + StockStructureDecisionPage)

**Route:** `/stocks/structure-decision`, `/stocks/:stockCode/structure-decision`
**Design system:** ResearchConsole
**15-second impression:** Deep analytical workspace for individual stock analysis with component scores, peer comparison, and evidence tracking.

- Component score labels (趋势/相对强弱/量能压力/波动压缩/突破质量/回撤健康度/延展风险/证据质量) are professional
- Boundary chips ("仅研究观察", "非判断等级", "不排序", "不生成行动指令") — 4 boundary chips per view is at the upper limit
- Symbol compare with peer correlation is a differentiated feature
- Entry page requires prior Research Radar context — "先打开研究雷达" is a clear redirect but could frustrate deep-link users
- `StockStructureSymbolNotFoundState` with 3 action links — good recovery path
- **Risk:** The entry page is essentially a redirect with no standalone content; deep-linking to `/stocks/structure-decision` (without a stock code) shows an empty "open research radar first" state

### Scanner (ScannerSurfacePage / UserScannerPage)

**Route:** `/scanner`
**Design system:** DenseWorkbench
**15-second impression:** High-density data table with candidate rows, diagnostic panels, evidence strips, and a history drawer.

- The largest page component (~58K tokens) — implementation complexity mirrors feature richness
- "首次使用：先运行一次扫描" / "First run: start a scan" — clear first-run CTA
- Scanner conclusion band (neutral/success/caution/danger) provides at-a-glance scan quality
- Trust summary counts (capped/fallback/proxy/stale/partial/limited) expose 6 internal trust dimensions — too many for consumer display
- PillTagGroup and FieldChip add per-candidate metadata — useful for power users, noise for casual users
- **Risk:** Scanner is the entry point to the research workflow (per T-1758), but the dense workbench aesthetic may intimidate first-time users

### Watchlist (WatchlistPage)

**Route:** `/watchlist`
**Design system:** DenseWorkbench
**15-second impression:** Managed observation list with batch operations, evidence overlays, and research queue integration.

- 48 TerminalChip usages — second highest density
- Batch failure reasons (数据不足/行情缺失/服务暂不可用/回测失败/扫描失败/超时/未知错误) — 7 failure categories is too granular for consumer display
- Workflow steps (discovered/pendingValidation/observing/alertRecorded/needsRefresh) use internal English state names in the data model but display localized labels
- Manual research symbol input is a good escape hatch for empty state
- **Risk:** Empty state copy ("当前已保存覆盖下还没有可用观察行") is a long, complex sentence that a normal user would find confusing

### Portfolio (PortfolioPage)

**Route:** `/portfolio`
**Design system:** TerminalPrimitives
**15-second impression:** Holdings management interface with trade entry, allocation view, and risk panels.

- Empty state is clear: "暂无持仓，保存持仓流水后生成盈亏与资产配置。"
- Concentration warnings ("最大持仓占 X%") are actionable and specific
- Broker CSV/XML import and IBKR sync are differentiated features
- `PortfolioTrustStrip` shows data verification status — useful for trust
- Holdings verification labels ("持仓数据待核验" / "持仓数据已核验") are clear
- **Risk:** Trade form uses broker code names (huatai, citic, cmb, ibkr) that may not be recognizable to all users — consider full broker names

### Options Lab (OptionsLabPage)

**Route:** `/options-lab`
**Design system:** TerminalPrimitives with DataWorkbenchFrame
**15-second impression:** Options analysis workspace with chain data, structure comparison, and scenario modeling.

- 6+ boundary statements — see UX-006
- Direction options (上行情景假设/下行情景假设/区间情景/波动扩张) are clear
- Risk profile (保守/均衡/进取) uses accessible language
- Demo data boundary: "演示数据：当前数据延迟，仅用于界面与情景验证，不作为结论依据。" — well-written
- Crash fallback: "期权实验室暂时无法加载，请刷新或稍后重试。" — clear and actionable
- **Risk:** The combination of disclaimers + demo data warning + readiness gate summary creates a high-friction entry experience

### Scenario Lab (ScenarioLabPage)

**Route:** `/scenario-lab`
**Design system:** ResearchConsole
**15-second impression:** Scenario analysis workspace with preset scenarios and driver evidence.

- Scenario unavailable copy block is comprehensive with state title, body, next step, boundary note, and two CTAs — well-structured
- Scenario presets (波动冲击/广度失守/流动性压力/Gamma 缺口) are vivid and specific
- Driver labels reuse Decision Cockpit labels — good consistency
- "当前页面仅用于研究观察，不构成操作结论。" — clear boundary statement
- **Risk:** When market state data is incomplete (which is frequent per T-1758), the entire page shows the unavailable block — users may never see the actual scenario analysis feature

---

## Quick Wins

These are small-scope fixes that a Qwen task can execute in a single session with minimal risk.

### QW-A: Fix hardcoded CN string in RoughKeyValueRows
**File:** `apps/dsa-web/src/pages/roughShellShared.tsx` line ~101
**Change:** Add locale parameter to `RoughKeyValueRows` and provide EN equivalent for `暂无可展示条目。`
**Scope:** Single component prop addition
**Risk:** Low — additive, no layout change

### QW-B: Fix "endpoint" leak in Decision Cockpit error message
**File:** `apps/dsa-web/src/pages/MarketDecisionCockpitPage.tsx` line ~614
**Change:** Replace `"Retry after the briefing endpoint responds again."` with `"Retry after the briefing data is available again."` / `"日度简报数据恢复后自动重试。"`
**Scope:** String replacement
**Risk:** Minimal

### QW-C: Fix hardcoded English loading strings in WatchlistPage
**File:** `apps/dsa-web/src/pages/WatchlistPage.tsx` line ~1226
**Change:** Wrap `'Loading watchlist...'` in locale conditional: `locale === 'en' ? 'Loading watchlist...' : '正在加载观察列表...'`
**Scope:** String replacement
**Risk:** Minimal

### QW-D: Floor text opacity at white/55 across consumer components
**Files:** ConsumerOnboardingCtaPanel, SidebarNav (admin dropdown), TerminalPrimitives (metric labels)
**Change:** Replace `text-white/38`, `text-white/34`, `text-white/40` with `text-white/55` minimum
**Scope:** CSS class replacements across 3-5 files
**Risk:** Low — visual only, improves accessibility

### QW-E: Add tooltip gloss for untranslated domain terms
**Surfaces:** Decision Cockpit (Gamma观察, 广度参与), Liquidity Monitor (Crypto Beta), consumer status labels (Gamma)
**Change:** Add inline tooltip or first-encounter explanation for Gamma, IV, Crypto Beta on first display
**Scope:** Small component additions
**Risk:** Low

---

## Larger Product Tasks

These require multi-session planning, design decisions, or cross-surface coordination. Better suited for GPT/Codex planning tasks.

### PT-1: Unified Consumer Page Shell
Define a single page shell component that unifies the chrome (header, breadcrumb, status strip, disclosure region) across all three design systems. Content layout can vary (console, workbench, dashboard) but the frame stays consistent. This is the highest-leverage structural change for visual coherence.

### PT-2: Chip Budget System
Implement a chip/badge budget system: max 3 chips per row, max 5 per panel header, with a composite "evidence health" chip that collapses freshness + trust + quality into a single indicator. Requires design decision on the composite chip visual grammar.

### PT-3: Progressive Onboarding Tour
Create a single first-run guided tour (4-5 steps) that walks the user through the research workflow: Market Overview → Decision Cockpit → Scanner → Watchlist → Research Radar. Use a step indicator with skip capability. Individual page onboarding panels remain as secondary support.

### PT-4: Empty State as Primary Surface
Redesign empty states to be the primary product experience until data reliability improves (T-1758 lineage). Each empty state should include: (1) what the page will show when data is available, (2) what the user can do right now on other pages, (3) a visual preview or illustration rather than just text. Consider adding "research progress" indicators that show the system is actively gathering data.

### PT-5: Disclaimer Consolidation for Options Lab
Redesign the Options Lab entry experience to consolidate 6+ boundary statements into a single compact boundary panel with progressive disclosure. The primary visible message should be one sentence; details available via expand.

### PT-6: Consumer Status Vocabulary Audit
Audit the `consumerStatusLabels.ts` and `evidenceDisplay.ts` label maps for terms that are internally accurate but consumer-opaque. Reframe system-centric labels ("observation only", "not decision grade") as user-centric guidance. This requires product/UX writing decisions.

### PT-7: Sanitization Pipeline Consolidation
Consolidate the 7-9 distinct sanitization systems into a single shared utility with a unified pattern set. Current fragmentation creates maintenance risk and potential gaps. This is a backend/util refactor with consumer-visible impact.

---

## Do Not Fix / False Positives

### DNF-1: Admin page internal terminology
Admin pages (`AdminProviderCircuitDiagnosticsPage`, `MarketProviderOperationsPage`, `AdminLogsPage`) contain extensive internal terminology (`provider`, `circuit`, `fallback`, `MarketCache`, snake_case table names). This is **correct for the audience** — ops users and engineers need precise diagnostic language. Do not sanitize admin pages to consumer standards.

### DNF-2: Admin nav mixed CN/EN labels
Admin nav group labels (`总览 / Trust`, `事件 / Evidence`) and page names (`Launch Cockpit`, `Mission Control`) mix CN/EN. This is **acceptable for admin context** where users are typically bilingual engineers/ops staff.

### DNF-3: TerminalPrimitives legacy note
Line 17 notes "Legacy-compatible names; new user-facing work should prefer components/linear." This migration is **already in progress** and does not need acceleration from a UX QA task.

### DNF-4: ResearchConsole vs TerminalPrimitives naming
The `RoughSectionCard`, `RoughSurfaceIntro` naming uses "Rough" prefix which sounds provisional. This is a **naming convention**, not a UX issue visible to users.

### DNF-5: `console.debug` in MarketOverviewPage
Line 492 has a `console.debug` statement gated behind `import.meta.env.DEV`. This is **correct development practice** and does not affect production users.

### DNF-6: No-advice disclosure repetition
The "仅供观察" / "Research observation only" disclosure appears on every research surface. While UX-009 recommends reframing the language, the **repetition itself is intentional and legally necessary**. Do not remove disclosures; improve their wording.

### DNF-7: Browser/plugin overlays
Any browser extension overlays, developer tools, or plugin chrome visible during live inspection should be excluded — these are not product code.

---

## Candidate Qwen Tasks

Small-scope, bounded tasks suitable for Qwen execution in single sessions.

| ID | Title | Scope | Files | Priority |
|----|-------|-------|-------|----------|
| QW-A | Fix hardcoded CN in RoughKeyValueRows | 1 file | `roughShellShared.tsx` | P1 |
| QW-B | Fix "endpoint" leak in Cockpit error | 1 file | `MarketDecisionCockpitPage.tsx` | P1 |
| QW-C | Fix hardcoded EN loading string in Watchlist | 1 file | `WatchlistPage.tsx` | P1 |
| QW-D | Floor text opacity at white/55 | 3-5 files | Multiple components | P1 |
| QW-E | Add tooltip gloss for untranslated domain terms | 3-4 files | Cockpit, Liquidity, status labels | P2 |
| QW-F | Fix `RoughBulletList` and `RoughScoreRows` empty text locale consistency | 1 file | `roughShellShared.tsx` | P2 |
| QW-G | Simplify Watchlist empty state copy | 1 file | `WatchlistPage.tsx` | P2 |

---

## Candidate GPT/Codex Tasks

Larger-scope tasks requiring design decisions, cross-surface coordination, or architectural planning.

| ID | Title | Scope | Dependency | Priority |
|----|-------|-------|------------|----------|
| PT-1 | Unified Consumer Page Shell | Cross-surface | Design decision | P0 |
| PT-2 | Chip Budget System | Cross-surface | Design decision | P1 |
| PT-3 | Progressive Onboarding Tour | Cross-surface | UX writing | P1 |
| PT-4 | Empty State as Primary Surface | Cross-surface | T-1758 data fixes | P0 |
| PT-5 | Options Lab Disclaimer Consolidation | 1 surface | UX writing | P1 |
| PT-6 | Consumer Status Vocabulary Audit | Cross-surface | Product decision | P2 |
| PT-7 | Sanitization Pipeline Consolidation | Util refactor | Architecture decision | P2 |

---

## Artifacts Inventory

| Artifact | Path | Status |
|----------|------|--------|
| UX QA Report | `docs/product-audit/archive/qw003-screenshot-ux-qa-pass.md` | This file |
| Screenshots | None captured | Frontend dev server not running; source-code-only analysis |

## Validation

- Report exists: yes
- Required sections present: Executive Summary, Top 10 UX Issues, Page-by-page Findings, Quick Wins, Larger Product Tasks, Do Not Fix / False Positives, Candidate Qwen Tasks, Candidate GPT/Codex Tasks
- Screenshots captured: none (source-code-only method)
- Secrets in report: none
- Source files modified: none (docs-only)
- Product code touched: none
- Protected domain touched: no

## Method Notes

This QA pass was conducted via **source-code static analysis only**. The frontend development server was not running during the inspection (ports 5173 and 3000 unresponsive). The backend API server was confirmed responsive on port 8000 but no API calls were made (read-only discovery constraint). All findings are based on component source code, i18n strings, CSS classes, and architectural patterns. Live visual inspection, responsive viewport testing, and screenshot capture were not performed.

Findings should be validated with live screenshots once the frontend dev server is available. The existing Playwright spec `ux-audit-p0-verification.smoke.spec.ts` and the `consumer-copy-regression.smoke.spec.ts` / `consumer-copy-forbidden-vocabulary.smoke.spec.ts` browser smoke tests provide automated coverage that complements this manual source review.

---

## Final Report

**Status:** READY TO LAND
**Summary:** 10 UX issues identified (2 P0, 5 P1, 3 P2), 7 quick-win Qwen tasks, 7 larger GPT/Codex product tasks. All 12 consumer pages inspected via source code. No product code edited.
**Pages inspected:** 12 (Home, Market Overview, Decision Cockpit, Liquidity Monitor, Rotation Radar, Research Radar, Stock Structure Entry + Detail, Scanner, Watchlist, Portfolio, Options Lab, Scenario Lab)
**Files changed:** 1 (`docs/product-audit/archive/qw003-screenshot-ux-qa-pass.md`)
**Product code touched:** None
**Protected domain touched:** No
**Validation outputs:** `git diff --check origin/main...HEAD` PASS (exit 0); `git diff --check` PASS (exit 0); `scripts/release_secret_scan.sh --base-ref origin/main` PASS — no secrets found; `git rebase origin/main` — already up to date
**Final base commit:** `e2a408c2`
**Final commit hash:** `76ef4ffe` (after rebase onto latest origin/main)
**Final git status:** Clean (branch ahead of origin/main by 1 commit)
**Rollback command:** `git reset --hard e2a408c2` (returns to pre-task state)
