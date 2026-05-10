## 2026-05-10

- 📝 **Frontend Playwright invocation guardrail** — Updated
  `docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md` to standardize
  Playwright validation on WolfyStock frontend tasks: prefer
  `cd apps/dsa-web && DSA_WEB_PLAYWRIGHT_PORT=<port> npx playwright test ...`,
  allow repo-root execution only with
  `--config apps/dsa-web/playwright.config.ts`, warn against repo-root
  `npx --prefix apps/dsa-web playwright test ...` when relying on the app
  config, and reinforce isolated preview-port usage with shared `5173`
  left untouched. This is docs-only guidance: no source, test, package,
  wrapper, script, or runtime behavior changed.

- 🧹 **Admin Provider Circuit Diagnostics chip consolidation** — `/zh/admin/provider-circuits`
  now reuses the existing `TerminalChip` primitive for the page-local read-only
  and status chip pattern in `AdminProviderCircuitDiagnosticsPage`, retiring the
  local `Badge` dependency on that admin diagnostics surface. This is a
  frontend-only visual consolidation: no provider runtime behavior, provider
  health semantics, API contracts, auth/RBAC behavior, or other admin/ops
  surfaces changed.

- 🧹 **Rotation Radar evidence chip consolidation** — `/zh/market/rotation-radar`
  now reuses the existing `TerminalChip` primitive for local evidence/status
  chips in `MarketRotationRadarPage`, retiring the page-local `EvidenceBadge`
  chip implementation. This is a frontend-only visual consolidation: no
  rotation score, stage, fund-flow, data freshness semantics, API contracts,
  provider/runtime behavior, or other product surfaces changed.

- 🧹 **Market Overview visual primitive consolidation** — `/zh/market-overview`
  now reuses existing terminal panel primitives for its shared shell/card
  material and retires the duplicate page-local ghost-card bridge in
  `marketOverviewPrimitives.tsx`. This is a frontend-only visual consolidation:
  no market data fetching, API contracts, freshness semantics, scoring,
  provider/runtime behavior, route behavior, or other product surfaces changed.

- 🧹 **Market Overview content-level chip consolidation** — `/zh/market-overview`
  now reuses existing `TerminalChip` primitives for one remaining page-local
  content chip pattern in the market state strip and signal-watch rail,
  reducing duplicated local pill styling without changing data/API,
  freshness, scoring, or provider behavior.

- 🧹 **Launch readiness docs consolidation** — Retired two stale single-purpose
  release/readiness guides after confirming the current source-of-truth already
  lives in `docs/audits/README.md`,
  `docs/audits/public-launch-readiness-master.md`,
  `docs/audits/public-launch-gap-register.md`,
  `docs/audits/deployment-readiness-checklist.md`,
  `docs/audits/operator-evidence-real-runbook.md`,
  `docs/audits/release-rollback-runbook.md`, and
  `docs/audits/db-retention-backup-restore-drill-plan.md`. This is docs-only
  cleanup: launch/release/rollback semantics, current NO-GO gate posture,
  runtime behavior, scripts, tests, CI, auth/RBAC, provider logic, database
  behavior, scanner/backtest/portfolio/options behavior, and operator evidence
  approval rules are unchanged.

- 🧹 **Root analysis wrapper retirement** — Deleted the obsolete root analysis
  compatibility wrapper after confirming current runtime code, API routes, task
  queue wiring, and focused tests already use the canonical
  `src.core.pipeline.StockAnalysisPipeline`,
  `src.services.analysis_service.AnalysisService`, and
  `src.core.market_review.run_market_review` surfaces directly. Root skill and
  architecture docs now point at those canonical entrypoints. This cleanup does
  not change analysis pipeline behavior, AI prompts/routing, provider runtime,
  report rendering semantics, API contracts, scanner/backtest/portfolio/options
  behavior, auth/RBAC, MarketCache, or storage behavior.

- 🧹 **Deprecated agent strategy wrapper removal** — Deleted the legacy
  `src/agent/strategies/*` compatibility namespace and removed the hidden
  `/api/v1/agent/strategies` endpoint after confirming current in-repo tests
  and runtime imports can use the canonical `src.agent.skills.*` namespace and
  `/api/v1/agent/skills` discovery route directly. This cleanup does not
  change skill implementations, agent execution semantics, LLM prompts/routing,
  model selection, tool behavior, Options Lab strategy endpoints, provider
  runtime, MarketCache, auth/RBAC, or frontend runtime.

- 🧹 **Deprecated WebUI startup wrapper removal** — Deleted the legacy standalone
  WebUI compatibility entrypoint and removed the deprecated `main.py`
  WebUI CLI aliases after confirming the current repo already documents and uses
  the canonical `python3 main.py --serve-only` /
  `python3 main.py --serve` startup path. Focused WS7 cleanup tests and
  deployment/architecture docs now target only the canonical server entry.
  `--serve` / `--serve-only` behavior, `server.py` / `api.app` startup
  semantics, auth/RBAC, provider runtime, AI/scanner/backtest/portfolio/options
  behavior, MarketCache, and frontend runtime are unchanged.

- 🧹 **Root backtest smoke wrapper retirement** — Deleted the obsolete root
  backtest smoke wrapper after confirming
  `scripts/smoke_backtest_standard.py` and
  `scripts/smoke_backtest_rule.py` are the canonical committed smoke
  entrypoints and current docs/tests already target them. This cleanup removes
  one old entrypoint only: no backtest calculations, rule engine behavior,
  fills, costs, metrics, provider/runtime behavior, API contracts, frontend
  code, or compatibility layers changed.

- 🧹 **Phase F archive docs consolidation** — Consolidated the stale
  `docs/architecture/archive/phase-f/` review/index/handoff cluster by
  deleting duplicate Phase F historical snapshots, trimming active Phase F
  status/decision/runbook references down to the current source-of-truth
  docs, and keeping the remaining archive runbooks/plans as provenance only.
  This is docs-only cleanup with no source, runtime, frontend, backend, test,
  script, wrapper, or compatibility-layer changes.

- 🧹 **Provider readiness docs consolidation** — Consolidated the stale
  provider phase-plan cluster by deleting two duplicate provider
  reporting/validation docs, repointing retained audit indexes to
  `provider-data-freshness-reliability-guide.md`,
  `ws2-provider-circuit-data-model-plan.md`, and
  `ws2-provider-quota-circuit-breaker-policy-design.md`, and keeping this as a
  docs-only cleanup with no source, runtime, provider behavior, frontend,
  backend, test, script, wrapper, or compatibility-layer changes.

- 🧹 **Operator evidence docs consolidation** — Consolidated stale
  operator-evidence wrapper guides into the retained source-of-truth set:
  `docs/audits/operator-evidence-real-runbook.md`,
  `docs/audits/operator-evidence-dry-run-handoff.md`, and
  `docs/audits/operator-evidence-redaction-checklist.md`. Deleted the duplicate
  per-tool and per-category guide cluster, repointed current launch/readiness
  references, and kept this as docs-only cleanup with no source, runtime,
  frontend, backend, test, script, wrapper, or compatibility-layer changes.

- 🧹 **Frontend CSS audit docs cleanup** — Consolidated the completed
  WolfyStock CSS cleanup audit history by deleting the stale pass-1 CSS/DOM
  note and repointing current audit references to
  `wolfystock-css-cleanup-closure-report.md` plus the retained route-specific
  DOM proof docs. This is docs-only housekeeping: no frontend source,
  backend/runtime, tests, package files, wrappers, or compatibility layers
  changed.

- 🧭 **Admin dry-run evidence explanation preview** — `/zh/admin/evidence-workflow` now includes a compact terminal-style deterministic AI evidence dry-run explanation preview for representative Scanner、Rotation、Options、Backtest、Portfolio packets. The new admin-only block surfaces safe summary、posture、confidence cap、validation state、limitation labels、disabled-claim counts, and collapsed representative diagnostics while staying display-only. This change does not alter live AI prompts, routing, weighting, recommendations, provider/runtime behavior, scanner ranking, options recommendation semantics, backtest math, portfolio accounting, or auth/RBAC behavior.

- 🧪 **Deterministic AI evidence dry-run explanation composer** — Backend now includes additive `src/services/ai_evidence_dry_run_explanation.py` plus focused regression coverage for a deterministic display/admin-diagnostics-only explanation preview built from validated `ai_evidence_packet_v1` metadata. The composer is pure/read-only apart from optional injected `generated_at`, degrades safely on invalid or unknown packet versions, preserves fail-closed and research-grade wording across Scanner/Rotation/Options/Backtest/Portfolio evidence, and emits conservative Chinese summaries/limitation labels without exposing raw/internal terms. This change is diagnostics-only: no AI prompt changes, no AI routing/weighting/recommendation changes, no provider/runtime/network calls, no scanner scoring/selection/threshold/ranking changes, no rotation score/stage/fund-flow semantic changes, no options ranking/gate/recommendation changes, no backtest calculations/fills/costs/metrics changes, no portfolio accounting/FX/sync/import/replay changes, and no frontend/API/runtime behavior changes.

- 🧪 **Cross-engine evidence contract regressions** — Backend evidence coverage now includes focused regression tests for cross-engine `ai_evidence_packet_v1` adapter normalization, required-field contract completeness, and packet-version compatibility across Scanner, Rotation, Options, Backtest, AI analysis, and Portfolio/Risk. The suite freezes conservative confidence-cap posture for stale/fallback/proxy-only/incomplete evidence, verifies source-ref sanitization and metadata-only explainable facts, adds a valid options required-field fixture, and guards unknown Scanner/Rotation engine packet versions by degrading adapter output to caution instead of silently promoting them. This remains additive diagnostics/test hardening only: no AI prompt/routing/weighting changes, no scanner scoring/selection/threshold/ranking changes, no rotation score/stage/fund-flow semantic changes, no options ranking/gate/recommendation changes, no backtest calculation/fill/cost/metric changes, no portfolio accounting/FX/sync/import/replay changes, and no provider runtime/live-call path changes.

- 🛰️ **Admin evidence diagnostics console** — `apps/dsa-web` 现将既有 `/zh/admin/evidence-workflow` 扩展为前半段 live `Evidence Diagnostics` 诊断台、后半段保留离线 workflow 复核参考。新 console 复用 `utils/evidenceDisplay.ts` 与 `components/evidence/EvidenceChips.tsx`，只读聚合现有前端可访问的 Scanner 候选证据、Rotation 状态证据、Options data-quality/liquidity gates、Backtest professional readiness、Portfolio risk diagnostics 代表性样本，用紧凑 terminal-style summary strip 与 per-engine sections 呈现 posture / limitation labels；内部 reason codes 仅保留在折叠的操作员细节中。此变更严格前端/admin 只读：不新增 backend endpoint、不改变 backend/API contract、scanner/rotation/options/backtest/portfolio 语义、provider runtime/live-call paths、AI prompts/routing/weighting、MarketCache、auth/RBAC/security 或 notification routing。

- 🧭 **Backtest / Portfolio evidence badges** — `apps/dsa-web` 现在把既有 `evidenceDisplay` normalizer 接到 `/zh/backtest` 结果表面与 `/zh/portfolio` 账户/风险摘要，使用共享 `components/evidence/EvidenceChips.tsx` 以终端风格 chips 呈现 `professionalReadiness`、`riskDiagnostics`、`portfolioRiskEvidence`、状态字段与 `confidenceCap`。回测结果会显示 `研究级回测`、`仅供观察`、`数据口径需复核`、`交易日历待确认`、`复权/公司行动待确认`、`专业级条件未满足` 等安全中文标签；持仓页面会在紧凑 chips 中显示 `仅供风险观察`、`FX 汇率已过期/缺失`、`持仓来源待核验`、`现金流水不完整`、`基准映射暂缺`、`因子映射暂缺`，同时继续隐藏 raw reason codes、source/sync/import internals 与 English field names。此变更严格前端只读：不改变 backend/API contract、backtest calculations/fills/costs/benchmarks/stored-result semantics、portfolio accounting/cash/holdings/P&L/FX/import/sync/replay semantics、provider runtime/live-call paths、scanner/options/rotation behavior、AI prompts/routing/weighting、MarketCache、auth/RBAC/security 或 notification routing。

- 🧭 **Scanner / Rotation Radar / Options Lab evidence badges** — `apps/dsa-web` 现在把既有 `evidenceDisplay` normalizer 接到 `/zh/scanner`、`/zh/market/rotation-radar`、`/zh/options-lab` 的用户端只读证据表面，并新增共享 `components/evidence/EvidenceChips.tsx` 复用 `TerminalChip` / `TerminalDisclosure` 呈现紧凑终端风格 badges。Scanner 候选卡片与详情会显示归一化 posture / freshness / limitation chips；Rotation Radar 在带 `rotationStateEvidence` 的主题行与详情中显示 `轮动代理证据`、`分类观察`、`真实资金流暂缺` 等受控标签；Options Lab 在决策区与风险边界区显示 fail-closed gate posture 与受控限制标签，同时继续隐藏 raw reason codes / developer diagnostics。此变更严格前端只读：不改变 backend/API contract、scanner 评分/选择/阈值/排序、rotation score/stage/fund-flow semantics、options recommendation/strategy set/ranking/gate semantics、provider runtime/live-call paths、AI prompts/routing/weighting、backtest behavior、portfolio accounting、MarketCache、auth/RBAC/security 或 notification routing。

- 🧪 **AI evidence metadata adapters** — Backend now includes additive `src/services/ai_evidence_adapters.py` plus focused fixtures/tests for metadata-only normalization of existing scanner, rotation, options, backtest, and portfolio diagnostics into `ai_evidence_packet_v1` packets. The adapters are pure/offline/deterministic, sanitize unsafe admin/source metadata, synthesize safe correlation ids when engine run ids are absent, preserve proxy-only rotation wording boundaries, keep options fail-closed posture, keep backtest in research-grade wording, and honor existing portfolio FX/lineage confidence caps. This layer is inert unless explicitly imported and does not change AI prompts/routing/fallback/weighting, scanner scoring/selection/thresholds/ranking/sorting, rotation score/stage/fund-flow semantics, options recommendations/strategy set/gates, backtest calculations/fills/costs/metrics, portfolio accounting/cash/holdings/P&L/FX/sync/import/replay semantics, provider runtime/live-call paths, MarketCache behavior, auth/RBAC/security, notification routing, quota/cost enforcement, or frontend behavior.

- 🧭 **WolfyStock evidence display normalizer** — `apps/dsa-web` 新增前端只读 `evidenceDisplay` utility，用于把 scanner / rotation / options / backtest / portfolio risk 的现有 evidence/diagnostics payload 归一到一个紧凑显示结构：统一 `engine`、`posture`、中文 `displayLabel`、tone、confidence cap、freshness label、compact limitation labels、admin reason codes 与可选 admin diagnostics 透传。该层默认对普通用户隐藏 raw reason codes / debug-like diagnostics，并把 `fallback` / `dry-run` / `fixture` / `mock` / `stale` / `provider_timeout` / `gap_fade_risk` 等常见内部词汇映射为中文安全标签；管理员模式可保留 reason codes 与折叠式 diagnostics。当前阶段仅新增 utility 与 focused tests，不把 evidence 广泛接入各页面，也不改变 backend/API contract、scanner/rotation/options/backtest/portfolio 语义、provider runtime、AI/auth/RBAC/notification 或 MarketCache 行为。

- 🧪 **Portfolio/risk read-only diagnostics packet** — Portfolio snapshot and risk read endpoints now attach additive `riskDiagnostics`, `portfolioRiskEvidence`, compact state fields (`sourceAuthorityState`, `fxFreshnessState`, `holdingsLineageState`, `cashLedgerCompletenessState`, `benchmarkMappingState`, `factorMappingState`), and a diagnostic-only `confidenceCap` built from existing holdings/cash/transaction/FX/source/sync metadata. The new `src/services/portfolio_risk_diagnostics.py` helper reports holdings lineage coverage, cash ledger completeness, transaction lineage coverage, FX freshness/fallback posture, cost-basis coverage notes, source authority state, sync/import status, benchmark/factor mapping placeholders, and Chinese-first user-safe limitation labels without exposing raw broker/provider/import payloads. This is additive/read-only only: no portfolio accounting changes, no cash-ledger semantic changes, no holdings/P&L/cost-basis changes, no FX conversion math or fallback changes, no broker sync/import/replay/API mutation changes, no provider runtime/order changes, and no AI prompt/routing/decision changes.

- 🧪 **Backtest professional-readiness diagnostics** — Rule backtest single-symbol detail/status/history payloads and universe job status/diagnostics now attach additive `professionalReadiness` metadata plus compact state fields such as `adjustedDataState`, `corporateActionState`, `tradingCalendarState`, `fillModelState`, `costModelState`, `antiLeakageState`, `reproducibilityState`, `universeBiasState`, and universe `localDataCoverageState`. The current system is now explicitly labeled `overall_state=research_prototype` with `professional_quant_ready=false`, `pointInTimeUniverse=false`, `survivorshipBiasState=uncontrolled`, and `providerCalls=false`. This is diagnostics-only: no single-symbol calculation changes, no strategy math changes, no fill-timing changes, no fee/slippage math changes, no benchmark changes, no stored-result semantic changes, no live provider calls, no universe execution-order changes, and no portfolio/scanner/AI/auth/notification/MarketCache behavior changes.

- 🧪 **Options Lab gate diagnostics hardening** — `POST /api/v1/options/decision/evaluate` now attaches additive `dataQualityGates`, `liquidityGates`, `gateDecision`, `gateIssues`, `decisionGrade`, and `failClosedReasonCodes` diagnostics computed entirely from the existing normalized options fixture/contract payloads. The new `src/services/options_data_quality_gates.py` helper fails closed for missing/invalid bid-ask-mid, missing volume/open interest, weak liquidity, stale/unknown/fixture/synthetic/fallback/dry-run freshness, missing IV/Greeks/IV percentile evidence, missing contract identity/DTE, and unsupported strategies, while keeping current strategy keys unchanged and forcing `preferredStrategyKey=null` when diagnostics are not decision-grade. This is additive/read-only only: no new provider calls, no provider order/runtime changes, no broker/order/portfolio mutation, no scanner/backtest/MarketCache/LLM/auth/quota/notification changes, and no recommendation-set expansion.

- 🧭 **Rotation state evidence advisory packet** — Market rotation radar theme rows now include an additive `rotationStateEvidence` packet built only from existing radar fields and taxonomy metadata. The packet adds advisory-only state inference (`accumulation`, `breakout`, `acceleration`, `overheated`, `divergence`, `fading`, `insufficient_evidence`), compact UI-safe summaries, explicit `flowEvidenceType` / `flowLanguageAllowed` boundaries, required-data status, sanitized admin diagnostics, and a taxonomy version marker without changing existing `stage` semantics, `rotationScore` calculation, theme sorting, alert candidate ordering, provider runtime order/live-call paths, MarketCache behavior, scanner behavior, AI decision logic, or fallback/mock/synthetic live labeling. Taxonomy-only CN/HK/CRYPTO entries remain `insufficient_evidence` and never claim real fund flow.

- 🧪 **Engine data-quality required-field contracts** — Backend now includes additive `src/services/data_quality_contracts.py` and `src/services/data_quality_contract_validator.py` plus sanitized offline fixtures/tests for engine-level required-vs-optional evidence contracts across `scanner`, `rotation`, `options`, `backtest`, `ai_analysis`, and `portfolio_risk`. The new layer is registry/schema/fixture/validator only: it defines shared data-quality classes, per-engine required-field registries, pure confidence-cap effect helpers, offline source-ref sanitization, and deterministic validation for missing/fixture/synthetic required evidence without calling providers, DBs, LLMs, networks, or external services. This is inert only: no provider runtime order/live-call path changes, no MarketCache TTL/SWR/cold-start changes, no scanner scoring/selection/threshold/ranking changes, no AI prompt/routing/fallback/retry/weighting changes, no options recommendation behavior changes, no backtest calculation changes, no portfolio accounting/FX/replay changes, no auth/RBAC/security changes, no quota/cost enforcement changes, and no notification routing changes.

- 🧪 **AI evidence packet schema and offline validator** — Backend now includes additive `src/services/ai_evidence_packet.py` and `src/services/ai_evidence_packet_validator.py` for a shared `ai_evidence_packet_v1` contract plus offline-only confidence-cap validation. The schema covers engine/entity/run metadata, required vs optional evidence, freshness, quality flags, decision status, confidence caps, source refs, explainable facts, and bounded admin diagnostics. The validator enforces source attribution, rejects raw payload/request/response/header/token/cookie/prompt-like fields in source refs, and fails closed for missing required evidence or fixture/synthetic required evidence without calling providers, DBs, LLMs, networks, or external services. This is additive only: no AI prompts, AI routing/decision weighting, scanner scoring/selection/thresholds/ranking/sorting, provider runtime order/live-call paths, options recommendation behavior, backtest calculations, portfolio accounting, MarketCache behavior, auth/RBAC, quota/cost enforcement, or notification routing changed.

- 🧪 **Scanner top-N evidence packet diagnostics** — Market Scanner shortlisted candidates now carry an additive `diagnostics.evidence_packet` block derived only from existing candidate metrics, component scores, and sanitized diagnostics. The packet summarizes trend/momentum/volume/volatility/liquidity/relative-strength/theme evidence, freshness and fallback posture, missing-evidence state, Chinese-first user review labels, and bounded admin-only reason codes without exposing raw provider payloads, request/response bodies, secrets, or debug traces. This does not change scanner scoring, candidate selection, thresholds, ranking, sorting, provider runtime order/live-call paths, fallback/mock/synthetic live labeling, AI decision logic, MarketCache behavior, portfolio/backtest/accounting, auth/RBAC, or notification behavior.

- 🧭 **Scanner action button consolidation** — `/zh/scanner` now keeps one compact semantic `h1` (`扫描器`) while consolidating first-fold and candidate actions onto `TerminalButton` variants: `启动扫描` remains the only primary CTA, `更多` / `历史扫描回放` and similar control buttons use secondary styling, and candidate/detail/preview actions use compact terminal buttons instead of page-local emerald/indigo/gray button styles. Focused DOM and Playwright guards now cover the first-fold control rail, results stage, `启动扫描` visibility, and terminal button usage. This is frontend-only: no scanner scoring, selection, thresholds, ranking, sorting, request payload semantics, backend behavior, API semantics, provider runtime, MarketCache behavior, portfolio/backtest calculations, AI/auth/RBAC, or notification behavior changed.

- 🧭 **Portfolio workspace width guard** — `/zh/portfolio` now keeps the shared `TerminalPageShell` width rhythm through an explicit workspace-lane layout: holdings and risk align as the main desktop row, history/activity and manual ledger align as the secondary row, and the manual ledger remains compact/collapsed by default instead of leaving a narrow-lane/blank-workspace split on desktop. Targeted DOM and Playwright guards now cover the lane structure and desktop/mobile geometry. This is frontend-only: no backend behavior, API semantics, portfolio accounting/cash/P&L/FX calculations, provider runtime, MarketCache behavior, fallback/mock/live labeling, scanner/backtest/AI/auth/RBAC, or notification behavior changed.

- 🧭 **Market Overview terminal data-state cleanup** — `/zh/market-overview` now consolidates freshness, backup, partial-unavailable, and refresh timing into one compact top-level terminal notice instead of a louder warning block plus repeated first-fold status noise. The page shell and summary strip also align more closely with shared terminal primitives, while repeated card-level warning emphasis is reduced to quieter chips and footer/state badges. This is frontend-only: no backend behavior, API semantics, provider runtime order, MarketCache TTL/SWR/cold-start behavior, fallback/mock/synthetic live labeling, scanner/backtest/portfolio/AI/auth/RBAC, or notification behavior changed.

- 🧭 **Admin provider operations terminal hardening** — `/zh/admin/market-providers` now normalizes incomplete provider summary counts before render so missing metrics no longer emit React `NaN` warnings or leak malformed values into the DOM. The admin surface was also restructured into a Chinese-first terminal hierarchy with compact health/circuit/failure/cache/exception metrics, a provider operations matrix, focused diagnostics, collapsed raw detail disclosure, and redacted secret-like failure text. This remains frontend-only and read-only: no backend behavior, API semantics, provider runtime, provider circuit enforcement, MarketCache TTL/SWR, auth/RBAC, or provider failure visibility changed.

- 🧪 **Backtest universe diagnostics aggregation** — Rule backtest universe jobs now expose `GET /api/v1/backtest/rule/universe-jobs/{job_id}/diagnostics` for compact job-level progress, reason buckets, metric leaders, and local-data coverage summaries. The paginated results endpoint also supports status, reason, symbol prefix, inferred market, and metric/sequence/runtime sorting for bounded drill-down. This remains local-only and read-mostly: no live provider calls, `_ensure_market_history`, worker pool/concurrency, DuckDB source-of-truth reads, single-symbol calculation changes, strategy math changes, scanner behavior, portfolio/accounting, AI, notification, or auth/RBAC behavior changed.

- 🧪 **Backtest universe sequential executor** — Rule backtest universe jobs can now be run through `POST /api/v1/backtest/rule/universe-jobs/{job_id}/run` as a synchronous local-only sequential executor. It reuses the existing deterministic rule backtest engine for each locally ready symbol, preserves deterministic symbol order, writes compact per-symbol result rows and progress counters, rejects duplicate runs, and isolates per-symbol failures. The path does not call live providers, `_ensure_market_history`, provider fallback, worker pools, DuckDB source-of-truth reads, single-symbol calculation changes, strategy math changes, scanner behavior, portfolio accounting, AI, notifications, or auth/RBAC.

## 2026-05-09

- 🧭 **Market rotation multi-market taxonomy radar** — Rotation Radar now uses
  an inert local taxonomy registry for US, A股, HK, and Crypto themes. The
  `/api/v1/market/rotation-radar` endpoint accepts an optional
  `market=US|CN|HK|CRYPTO` query while preserving US as the default, and the
  frontend market tabs switch the visible theme universe. Static taxonomy-only
  markets are labeled as classification observation with local quote coverage
  pending; no live provider calls, provider routing, scanner scoring,
  backtest, portfolio, AI, notification, auth/RBAC, MarketCache, fallback/mock,
  or DuckDB behavior changed.

- 🧭 **Frontend information hygiene** — AI research, Scanner, and Chat default
  surfaces now translate developer diagnostics into plain user-facing Chinese
  data sufficiency and risk language, keeping raw provider/schema/reason-code
  details collapsed or on admin/operator pages. Backend behavior, provider
  routing, scanner scoring, backtest calculations, portfolio accounting,
  auth/RBAC, and notifications are unchanged.

- 🧪 **Backtest large-universe scaffold** — Rule backtest now has a stored local-only universe job scaffold with compact metadata rows, per-symbol readiness rows, deterministic normalized symbol ordering, a 500-symbol default cap, and paginated status/result APIs. This first slice is preflight-only: it checks existing local daily bars, marks missing symbols as `blocked_missing_local_data`, does not execute single-symbol calculations, does not call live providers, does not add worker concurrency, and does not make DuckDB a runtime source of truth.

- 🦆 **DuckDB local-RC diagnostic hardening** — Optional DuckDB quant diagnostics now avoid creating a missing DB file on enabled read-only health/coverage/benchmark checks, return sanitized unavailable reason codes for corrupt/unreadable, permission-denied, and schema-mismatched local DB files, and cap explicit payload ingest at 5,000 rows per request. DuckDB remains disabled by default and diagnostic-only; this does not connect DuckDB to scanner scoring, backtest calculations, portfolio accounting, provider routing, AI decisions, notifications, auth/RBAC, or production runtime paths.

## 2026-05-08

- 🧪 **Operator evidence workflow docs** — Release documentation and
  `scripts/README.md` now describe the offline operator evidence workflow:
  sanitized template generation, manual operator fill-in, category validation,
  checksum manifest creation/verification, bundle aggregation, and Markdown
  review-report rendering. The workflow remains review support only; generated
  templates and rendered reports are not real operator artifacts,
  `releaseApproved=false` remains required, missing evidence remains **NO-GO**,
  and final release review remains external/manual.

- 🧪 **Review evidence validator integration** — Launch acceptance evidence and
  release gate summary now include required review evidence for sanitized
  WS2/SSE operator decisions, config snapshots, and manual release review
  records, while listing the operator evidence bundle checker only as a
  review-support aggregation tool. The accepted fixture remains
  `GO-REVIEW-REQUIRED` with `releaseApproved=false`; missing/unsafe evidence
  remains **NO-GO**, and manual approval evidence cannot auto-approve release.

- 🧪 **Operator evidence validator integration** — Launch acceptance evidence and
  the release gate summary now recognize domain-local offline validators for
  provider operator evidence, real restore/PITR operator evidence, security
  MFA/RBAC operator acceptance, quota/budget operator evidence, and staging
  ingress operator evidence. The synthetic accepted fixture can reach
  `GO-REVIEW-REQUIRED` only with `releaseApproved=false`; missing or unsafe
  evidence remains **NO-GO**. This is evidence plumbing only and does not change
  runtime provider, auth/RBAC, quota, ingress, storage, scanner, AI,
  portfolio, or backtest behavior.

- 🧪 **Launch acceptance final operator matrix** — Launch acceptance evidence now
  has one explicit hard-blocker category for MFA admin pilot, RBAC fallback
  switch, provider credential dry-run, provider staging probe artifact,
  provider live probe opt-in/timeout, provider circuit enforcement, quota
  pilot, budget-alert dry-run, real PostgreSQL restore/PITR, staging ingress,
  public API/frontend no-secret safety, supply-chain/build artifacts,
  incident-response/audit evidence, WS2/SSE topology and polling fallback,
  admin log retention/capacity rehearsal, portfolio/backtest export and browser
  proof, notification delivery rehearsal, user data privacy/export/deletion,
  market freshness/fallback, AI guest-preview safety, Options derivatives
  safety, API abuse/request-safety, and final clean `ci_gate`. Fully accepted
  synthetic evidence can reach `GO-REVIEW-REQUIRED`, but `releaseApproved`
  remains `false`; missing or unsafe evidence remains **NO-GO**.

- 🧪 **Cost launch quota alert acceptance evidence** — Launch acceptance evidence
  now requires controlled quota pilot proof with an explicit owner allowlist,
  out-of-scope advisory behavior, sanitized budget-alert dry-run intent,
  advisory-only invoice reconciliation, real outbound delivery disabled by
  default, no live LLM/provider/invoice calls, and global quota enforcement
  disabled by default. Runtime quota/provider/invoice integrations and real
  notification delivery defaults remain unchanged.

- 🔐 **Auth launch operator-switch evidence** — Launch acceptance evidence now
  requires MFA admin-only scope proof, unsupported/global rollout NO-GO,
  break-glass default-off, route-inventory-gated RBAC fallback disable proof,
  explicit-capability pass proof, legacy/missing-payload fail-closed proof, and
  redaction of password, session, TOTP, recovery-code, token, and cookie
  evidence. Defaults remain unchanged: global MFA is not enabled and RBAC
  coarse fallback compatibility code remains present.

- 🧪 **Provider staging live-probe evidence contract** — Options provider
  readiness preflight now exposes an explicit operator opt-in live-probe
  contract with bounded timeout, credential presence-only evidence, and
  no-network default proof. Launch acceptance evidence now requires sanitized
  provider staging probe opt-in and timeout checks while keeping real provider
  calls disabled by default.

## 2026-05-07

- 🧭 **Market rotation radar MVP** — Added a read-only
  `/api/v1/market/rotation-radar` contract and `/zh/market/rotation-radar`
  frontend surface for theme-level rotation evidence across static AI,
  semiconductor, cybersecurity, cloud, power, cooling, and robotics baskets.
  The MVP scores relative strength, volume expansion, breadth,
  synchronization, VWAP/persistence, freshness penalties, and leadership
  concentration while clearly marking fallback/stale data, avoiding live
  provider calls by default, and preserving no-advice wording.

- 🧪 **Launch acceptance evidence pack** — Added
  `scripts/launch_acceptance_evidence.py`, stable synthetic fixtures, focused
  tests, and launch-doc references for the operator-supplied evidence required
  before public launch can move from NO-GO toward manual release review. The pack
  covers MFA pilot acceptance, RBAC fallback disable switch, provider
  credential staging dry-run, provider circuit controlled enforcement, quota
  pilot acceptance, real isolated PostgreSQL restore/PITR, staging ingress
  smoke, public API/frontend no-secret safety, and final clean full `ci_gate`.
  It is local-only, does not call external services or read real secrets/data
  paths, keeps `releaseApproved=false`, and preserves **NO-GO** unless every
  hard blocker has accepted sanitized evidence.

- 🧪 **Restore drill evidence artifact gate** — `scripts/backup_restore_drill_check.sh` now accepts an optional sanitized `--real-restore-evidence` JSON artifact that documents an externally executed isolated PostgreSQL restore/PITR drill without running restore commands itself. The validator checks `wolfystock_restore_drill_evidence_v1`, operator opt-in, isolated non-production target metadata, pass/fail post-restore checks, RPO/RTO observations, and redaction of DSNs/passwords/tokens/private keys/cookies while still reporting real restore execution as pending when no artifact is supplied. Launch docs now distinguish dry-run preflight evidence from the still-pending accepted real restore artifact, and the checker remains local-only with no production DB/network/restore action by default.

- 🧪 **Production config readiness preflight** — Added `scripts/production_config_readiness.py`, a stable JSON release preflight for sanitized production configuration contracts. The helper covers required launch flag names, explicit MFA rollout mode, RBAC coarse-fallback disable evidence, provider credential presence states, quota mode, backup/PITR execution opt-in, and staging-ingress live opt-in without reading raw `.env` files, printing secret values, changing runtime defaults, or calling external services. `scripts/release_gate_summary.sh` now lists the command while preserving the public-launch **NO-GO** posture until a real sanitized production contract is accepted.

- 🧪 **Public launch GO-NO-GO evidence aggregator** — `scripts/release_gate_summary.sh --go-no-go-json` now emits sanitized machine-checkable JSON for release review attachment, covering completed foundation evidence and hard public-launch blockers while preserving `finalStatus=NO-GO` until every blocker has explicit evidence or an accepted production exception. The helper remains local-only and does not call external services, require production credentials, read production data paths, or approve a release.

- 🧪 **PostgreSQL restore/PITR evidence preflight** — `scripts/backup_restore_drill_check.sh` now requires PostgreSQL-oriented synthetic metadata with `database_engine=postgresql`, `application_schema_version=wolfystock_ops_readiness_v1`, PITR target/window metadata, and a present WAL/archive marker before emitting launch evidence. The checker still performs no restore, network, migration, production DB, or backup-infrastructure action by default; optional DSN validation refuses all DSNs unless explicit local safe-test mode is set, rejects production-like targets, and redacts DSN/path values from evidence. Launch docs now mark synthetic PostgreSQL/PITR preflight evidence as present while keeping real isolated PostgreSQL restore execution, encrypted backup/PITR infrastructure proof, post-restore smoke, and rollback evidence as public-launch blockers.

- 🧪 **Staging ingress smoke preflight** — Added `scripts/staging_ingress_smoke.py`, a safe deployment-readiness helper that emits dry-run JSON evidence by default and only makes live ingress HTTP calls when `WOLFYSTOCK_STAGING_INGRESS_SMOKE=1` is set. The preflight checks `/api/health`, `/api/health/ready`, `/api/health/live`, unauthenticated admin fail-closed behavior, sensitive/debug payload leakage, sanitized timeout output, and attachable evidence. `scripts/release_gate_summary.sh` now lists this preflight. No production deployment config, credentials, runtime auth/provider/options/cost/portfolio/backtest/scanner behavior, migrations, or production data paths were changed.

- 🧪 **Portfolio/backtest public-safety evidence** — Strengthened public-safety regression coverage for portfolio export-like reads, broker/token redaction, cross-owner denial, admin portfolio export redaction, backtest support/export artifacts, no-advice/order-verb wording, missing provider-data disclosure, and existing golden metric stability. Launch docs now record this as improved evidence while preserving the overall public-launch NO-GO posture until broader accounting invariants, route-wide mutation guards, staged owner-isolation smoke, and release-candidate no-secret evidence are accepted. No portfolio accounting calculations, backtest formulas, scanner scoring, provider/options/cost/auth/WS2 files, frontend files, or production data paths were changed.

- 🧪 **Admin logs retention/storage launch evidence** — Admin log storage summary now exposes explicit `admin_logs_standard`, `admin_logs_minimum_protected`, and `admin_logs_storage_pressure` retention tiers backed by focused API tests. Coverage proves minimum-retention clamping, preview-only capacity planning, explicit capacity cleanup audit notification with sanitized payload, storage-size-unavailable safe fallback, secret/token/password-like metadata redaction, and warning+ default log filtering. Runtime cleanup behavior remains unchanged; the launch docs now mark admin-log-specific evidence complete while preserving broader non-log retention-tier blockers.

- 🧾 **Release launch readiness consolidation** — Consolidated the public launch readiness checklist, gap register, blocker burn-down, master readiness view, and DB retention/restore plan around the current NO-GO posture. Completed tracks are now marked as foundations rather than stale blockers: provider SLA/readiness diagnostics, MFA/RBAC readiness coverage, quota enforcement pilot-readiness preflight, backup/restore dry-run preflight, fallback/stale data-quality disclosure regressions, and secret-scan/admin harness coverage. The docs still preserve launch blockers for global MFA enforcement, coarse RBAC fallback removal, live quota/provider enforcement, isolated PostgreSQL restore/PITR drill, retention tiers, WS2 multi-instance proof, and portfolio/backtest public-safety evidence. No code, tests, scripts, configs, migrations, frontend files, or production data paths were changed.

- 🧪 **Ops backup/restore drill preflight** — `scripts/backup_restore_drill_check.sh` now runs a dry-run production-like preflight from simulated backup metadata, checking artifact presence, timestamp freshness, `backup_restore_preflight_v1` schema compatibility, safe source environment labels, and temp-only restore target isolation. Focused tests cover valid evidence output, unsafe restore targets, no file mutation, missing metadata, stale metadata, and incompatible schema; docs now distinguish this preflight from the still-required isolated PostgreSQL restore/PITR drill. No production DB, DuckDB runtime, provider/market/scanner/backtest/portfolio/auth/cost/frontend behavior, migrations, or real credentials are touched.

- 🔐 **Security MFA enforcement rollout guard** — Tightened the disabled-by-default MFA login enforcement pilot with explicit `WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ADMIN_ONLY=true` scope, sanitized `security.mfa_login_enforcement_decision` evidence for skipped/required/success decisions, and an eligibility guard that fails closed when an admin MFA state is incomplete, including missing active recovery-code state. Global MFA enforcement remains off unless `WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED=true` is explicitly configured, and no raw TOTP secrets, recovery codes, provisioning URIs, passwords, cookies, or tokens are logged.

- 🧪 **Options Tradier dry-run provider foundation** — Added a disabled-by-default Tradier Options provider dry-run adapter contract that maps provider-shaped option-chain, quote, IV, and Greeks data into the existing Options Lab provider-neutral shape without live network calls, broker/order execution, or portfolio mutation. Missing credentials and provider mapping failures return sanitized structured errors, and dry-run data remains marked delayed, non-live, and non-tradeable.

- 🔐 **Security MFA enforcement pilot contract** — Added a disabled-by-default login enforcement pilot behind `WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED=false`. When explicitly enabled for admin MFA pilots, login requires a verified TOTP code or consumes one valid recovery code; inconsistent enabled-MFA state fails closed with a generic `mfa_required` response. The break-glass recovery path is separately disabled by default behind `WOLFYSTOCK_MFA_LOGIN_BREAK_GLASS_ENABLED=false`, requires an explicit reason, and writes sanitized audit metadata without raw TOTP secrets, recovery codes, provisioning URIs, passwords, cookies, or tokens. Default login behavior remains unchanged.

- 🔐 **Security MFA secret storage hardening foundation** — Admin MFA enrollment now stores non-test TOTP secrets as a versioned AES-GCM encrypted envelope in the existing `mfa_secret_ref` field, keyed by `WOLFYSTOCK_MFA_SECRET_ENCRYPTION_KEY` with sanitized `WOLFYSTOCK_MFA_SECRET_KEY_ID` metadata. Existing `test-only:` deterministic refs and legacy plaintext TOTP refs remain readable for compatibility, while `placeholder-sha256:` stays migration-incomplete and non-verifiable. Missing/invalid secret storage config fails safely with a generic `mfa_secret_storage_unavailable` response before persisting a pending secret, and MFA login enforcement remains disabled. Tests cover encrypted store/read, legacy refs, missing-key failure, and no plaintext leakage from non-enrollment responses or enrollment-challenge repr.

- 🔐 **Security MFA secret storage hardening plan** — 新增 docs-only 生产级 MFA TOTP secret storage 方案，明确当前 `test-only:` / `placeholder-sha256:` scaffold 与登录强制 MFA 的生产缺口，比较 application-level envelope encryption、OS/keychain/KMS-backed encryption、external secret manager 与 database encrypted column 路径，并推荐先落 application-level envelope encryption + KMS/keychain-backed master key。计划覆盖 secret version/key id/timestamps metadata、enrollment/verify/rotation/disable/recovery-code lifecycle、从 scaffold 到生产存储的迁移、无 raw secret/provisioning URI 泄漏的审计规则、roundtrip/wrong-key/rotation/no-leakage/backup-restore 测试，以及 MFA enforcement 的 blockers 与 rollout sequence。本阶段不改 runtime auth/MFA code、storage/schema、tests、Options/Data Pipeline/Provider Circuit/cost/quota/scanner/backtest/portfolio 行为。

- 🧾 **DB retention and backup/restore drill plan** — 新增 docs-only 计划 `docs/audits/db-retention-backup-restore-drill-plan.md`，定义 public multi-user 前必须接受和演练的 retention tiers、PostgreSQL backup baseline、local synthetic restore、staging restore、PITR drill、post-restore verification checklist、data safety rules、rollback/failure plan 与后续 Codex prompts。该阶段不访问 DB、不修改 runtime code/schema/migrations/tests，不触碰 storage.py、provider/analysis/options/auth/cost、portfolio/scanner/backtest 行为；DB Index Batch A 已完成，Batch B indexes 与 retention implementation 仍是 future work。

- 🔐 **Admin RBAC R5 coarse fallback removal plan** — 新增 docs-only 迁移治理计划 `docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md`，明确当前 coarse admin fallback 的兼容原因、已 capability-guarded route families、剩余 coarse-admin-only 区域、移除前能力清单、角色/能力治理、observe -> warn -> dual-run -> fail-closed pilot -> remove fallback 阶段、rollback、测试矩阵、生产 blocker 与后续 implementation prompts。本阶段不改 runtime auth/RBAC、frontend nav、tests、Options、Data Pipeline、Provider Circuit、Cost/Quota 或 Security MFA/KDF runtime。

- 🧪 **Data Pipeline R2 progressive enrichment** — `dataQualityReport` now exposes safe enrichment metadata for optional news, sentiment, and detailed fundamentals: overall status, fixed source list, completed/pending/failed/skipped source buckets, sanitized reason codes, and timing fields. Home shows a compact Chinese state (`快速判断已完成`, `增强数据补充中` / `部分缺失` / `已完成`) with missing items and safe reason codes while developer details remain collapsed. Optional enrichment timeouts/failures stay non-blocking and do not change the fast decision failure path. This pass does not touch Options, cost ledger/quota/admin cost/pricing, provider circuit enforcement, scanner ranking, backtest/portfolio/accounting, global provider ordering/fallback, MarketCache TTL/SWR, or LLM prompts/routing/model fallback.

- 🔐 **Security Phase 3E admin MFA backend foundation** — 后端新增 admin MFA scaffold：`app_users` 增加 MFA 状态、secret reference、recovery-code hash placeholder 与 created/enabled/last-verified 时间戳，新增 `POST /api/v1/auth/mfa/enroll/start`、`/enroll/verify`、`/verify`、`/disable` 四个 admin-only endpoint。enrollment verify 与 disable 复用现有 recent admin reauth marker；登录仍明确不要求 MFA，响应只返回非阻断 metadata。当前仓库没有 production secret encryption service，因此本阶段仅提供 docs-backed scaffold：enrollment start 只在首次响应返回 TOTP secret，后续响应不返回 raw secret；测试使用 `WOLFYSTOCK_MFA_TEST_SECRET` 的 deterministic fake secret path；生产启用登录强制 MFA 前仍需落地 secret encryption/storage 与 recovery-code issuance。本阶段不改 RBAC route migration，也不触碰 Options/Data Pipeline/cost ledger/quota/provider runtime/MarketCache/scanner/backtest/portfolio/notification/DuckDB/broker 行为。

- 🧾 **WS2-R5 provider circuit dry-run counters** — 后端新增 `ProviderCircuitObserver` synthetic helper，将 success、timeout、provider_429、provider_403、provider_5xx、network_error、malformed_payload、insufficient_payload、auth_or_key_invalid、quota_policy_block 与 operator_disabled 观测写入 provider circuit storage 的 dry-run counters/events。普通观测更新 `provider_quota_windows`，失败/状态观测追加 `provider_circuit_events`，probe-like 观测追加 `provider_probe_events`，cooldown 观测仅写 non-enforcing `policy_dry_run` event；管理员 diagnostics API 可读这些安全聚合。本阶段不接入 live provider call site，不改变 provider enforcement/order/fallback、Data Pipeline hot-path cooldown、MarketCache TTL/SWR/cold-start/background refresh/payload shape、quota enforcement、frontend UI、Options/scanner/backtest/portfolio、LLM routing、notification、DuckDB 或 broker/order 行为。

## 2026-05-06

- 🔐 **Security Phase 3D password KDF upgrade foundation** — Auth password storage now supports self-describing versioned hashes and keeps legacy `salt_b64:hash_b64` PBKDF2 verification for existing users. New password writes use versioned PBKDF2-HMAC-SHA256 with 600,000 iterations as the interim target because Argon2id/bcrypt are not currently available in the project/runtime without adding dependencies. Successful login, admin password unlock, auth settings current-password verification, and `POST /api/v1/auth/reauth` opportunistically upgrade recognized legacy hashes, including the bootstrap-admin file plus `app_users.password_hash` mirror; wrong passwords, unsupported hashes, disabled users, and rate-limited attempts do not upgrade. This phase does not implement MFA, change RBAC route authorization, or touch Options/Data Pipeline/cost ledger/quota/provider/scanner/backtest/portfolio/notification/DuckDB/broker/order behavior.

- 🧪 **Options Decision Engine R2** — Options Lab 决策接口继续使用只读 `POST /api/v1/options/decision/evaluate`，在 R1 字段外新增 IV Rank / Percentile、Expected Move 与策略优化器输出。IV Rank 仅在 fixture/test-only proxy historical IV 存在时计算并标记低置信度来源；缺失历史 IV 时返回 unavailable 并保守降置信度。Expected Move 优先使用 ATM straddle mid，缺失时使用 IV/DTE 估算，完全不可用时不崩溃并降分。策略优化器保守比较 long call、long put、bull call spread、bear put spread 与 no-trade/observe 状态，synthetic/fixture/fallback/delayed 数据仍不能输出“有条件可交易”。本阶段不新增 live provider、broker execution、order placement、portfolio mutation、LLM 或个性化投资建议行为。
- 🧪 **Options Decision Engine R1** — Options Lab 新增只读 `POST /api/v1/options/decision/evaluate` 交易质量分析合同，并在 `/zh/options-lab` 增加紧凑“交易质量判断”区块，展示数据质量、流动性评分、IV / Greeks 就绪度、盈亏平衡压力、风险回报、系统判断、主要原因、风险警示与更优替代结构。R1 使用 normalized option-chain / strategy comparison 数据，synthetic / fallback / fixture 数据强制 `数据不足，禁止判断` 且最高 capped demo-only score，不输出“有条件可交易”；缺失 Greeks、价差过宽、volume / OI 缺失等都会保守降分或封顶。本阶段不接入 live provider，不调用 LLM，不增加 broker execution、order placement、portfolio mutation、scanner/backtest/provider fallback/MarketCache、cost ledger/quota/admin cost 行为，也不暴露 raw provider payload、API key、token、secret 或个性化投资建议。

- 🧾 **Admin model pricing policy observability** — `GET /api/v1/admin/cost/model-pricing-policies` now exposes a narrow read-only `cost:observability:read` snapshot of manually maintained model pricing policies, and `/zh/admin/cost-observability` shows a compact “模型价格策略” panel with active count, provider/model, per-1M input/cached-input/output prices, currency, effective dates, safe source label/link, active state, and collapsed developer details. The panel is capability-gated, does not edit policies, does not scrape runtime pricing, and does not change storage/schema or live enforcement.

- 🧾 **LLM Cost Ledger + Pricing Policy Foundation** — 后端新增 `model_pricing_policies` 与 `llm_cost_ledger` storage foundation、`LlmCostLedgerService` synthetic reconciliation helper，以及只读管理员汇总 `GET /api/v1/admin/cost/llm-ledger-summary`（`cost:observability:read`）。Pricing policy 支持 provider/model/effective date、cached input price、source metadata 与 unknown/inactive safe result code；ledger 支持 owner/guest、route/call type、provider/model、tokens、Decimal-safe estimated USD costs、pricing snapshot、quota reservation reference 与 sanitized metadata。本阶段仅落 cost accounting foundation，不接入 live quota enforcement，不调用 live LLM/provider，不抓取 runtime pricing，不修改 prompts、model routing/order、fallback/retry/integrity retry、provider、scanner/backtest/portfolio/Options/MarketCache/DuckDB/broker/notification 行为。

- 🧱 **WS2-R5 provider circuit storage foundation** — 后端新增 additive provider quota/circuit storage 基础：SQLite/local ORM 与 PostgreSQL baseline 同步覆盖 `provider_quota_policies`、`provider_quota_windows`、`provider_circuit_states`、`provider_circuit_events`、`provider_probe_events`，并补充 synthetic-only `DatabaseManager` helper 和 focused storage tests。该阶段仅落 storage foundation，不接入 runtime enforcement，不修改 provider ordering/fallback、MarketCache TTL/SWR/cold-start/background refresh/payload shape，不调用 live providers/LLM，也不改变 scanner/backtest/portfolio/Options/RBAC/notification/DuckDB/broker/order 行为。

- 🔐 **Security Phase 3B recent admin reauth route pilot** — 后端仅将 recent admin reauth 接入现有 admin user security write pilot：`POST /api/v1/admin/users/{user_id}/disable`、`/enable`、`/revoke-sessions` 在保留 `users:security:write`、原因、typed confirmation、self-action、last-admin 与审计脱敏/响应形状的基础上，对真实已认证 admin session 要求先通过 `POST /api/v1/auth/reauth` 建立短期 session-bound marker。auth-disabled transitional local admin 兼容路径保持可用，且 bypass 只限该 unauthenticated transitional dev 语义。本阶段不接入 system config/logs/notifications/provider routes，不实现 MFA、KDF 升级、角色管理 UI，也不改变 LLM/provider/quota/WS2/Options/scanner/backtest/portfolio/notification/DuckDB/broker/order 行为。

- 🧾 **WS2 provider circuit data model migration plan** — 新增 docs-only 计划 `docs/audits/ws2-provider-circuit-data-model-plan.md`，把 provider quota/circuit breaker policy 落到后续可迁移的数据模型边界：`provider_quota_policies`、`provider_quota_windows`、`provider_circuit_states`、`provider_circuit_events` 与 provider probe rows，覆盖索引、状态转换持久化、`QuotaPolicyService` 关系、rollout/rollback、future synthetic test plan 和后续 Codex prompt。该阶段不新增 migrations，不修改 runtime provider behavior、provider ordering/fallback、MarketCache TTL/SWR/cold-start、schema/tests/enforcement/frontend dashboard，也不调用 live providers。

- 🧾 **WS2-R4A quota dry-run/pilot integration** — 新增只读管理员诊断路径 `POST /api/v1/admin/cost/quota-dry-run`，使用 `cost:observability:read` capability 进行 quota policy dry-run / pilot 评估，返回 `allowed / wouldBlock / reasonCode / routeFamily / estimatedUnits / enforcementMode`，并可在显式 `reserve` / `consume` / `release` 操作下仅针对 synthetic quota state 走 reservation lifecycle。默认仍是 non-blocking diagnostic path，不接入任何 live LLM/provider route，不改变 prompts、model routing/order、provider fallback/retry/integrity retry、scanner AI、MarketCache、Options Lab、portfolio/backtest/scanner calculations、notification、broker/order 或 DuckDB runtime 行为；未来仍需单独完成 selected route enforcement、admin dashboard、provider quota buckets、circuit breaker policy 与 usage reconciliation。

- 🗄️ **DB Index Migration Batch A** — 后端新增首批 production-readiness additive indexes：SQLite/local 初始化与兼容迁移补齐 `app_user_sessions(user_id, revoked_at, expires_at)`、`auth_rate_limit_buckets(bucket_type, expires_at)`、`durable_task_states` owner/status/lease/idempotency/dedupe 读取路径，以及 `durable_task_progress_events` replay/owner/time 路径；Phase A PostgreSQL baseline 同步补齐 `app_users(role, is_active)`、session active/stale 与 guest lifecycle indexes。该阶段不实现 execution/admin logs index、不接入 quota enforcement、不做 retention cleanup、不改变 auth/session、durable task/progress、provider/cache、RBAC、scanner/backtest/portfolio、LLM/provider routing、notification、DuckDB 或 broker/order runtime 语义。

- 🧾 **WS2-R5 provider quota/circuit breaker policy design** — 新增 docs-only 设计 `docs/audits/ws2-provider-quota-circuit-breaker-policy-design.md`，定义 provider quota buckets、circuit breaker states、safe failure buckets、fallback/cache-only policy、future `QuotaPolicyService` integration、admin dashboard/readiness/alerting/data-model sketch 与 rollout/test plan。该阶段只做设计，不修改 runtime provider behavior、provider ordering/fallback、MarketCache TTL/SWR/cold-start、quota enforcement、schema/migrations/tests、scanner/backtest/portfolio/Options/RBAC/notification/DuckDB/broker/order 路径，也不调用 live providers。

- 🧾 **WS2-R4 quota policy foundation prerequisite** — 后端新增 quota/budget schema foundation：`quota_policy_definitions`、`quota_usage_windows`、`quota_reservations`，并新增 synthetic-only `QuotaPolicyService`，覆盖 deterministic route weights、budget-unit estimation、global kill switch、per-user daily/monthly budget、route request cap、token cap、安全 reason code、metadata sanitization 与 reservation create/consume/release/expired lifecycle。当前阶段 quota enforcement 默认关闭，且没有接入任何 live route；不调用 live LLM/provider，不修改 prompts、model routing/order、provider fallback、scanner AI、MarketCache、Options、portfolio/backtest/scanner calculations、notification、broker/order 或 DuckDB production runtime 行为。

- 🧾 **DB index migration plan for first production-readiness batch** — 新增 docs-only 计划 `docs/audits/archive/db-index-migration-plan-auth-task-log.md`，把首批生产就绪 DB index 迁移范围收束到 auth/users/sessions、durable task/progress、execution/admin logs 与 LLM usage/cost observability ledger readiness。该计划仅定义 additive index contract、rollout/query-plan 验证和后续实现 prompt，不新增 migrations，不修改 runtime code/schema/tests，不连接生产 DB，也不检查真实 DB contents。

- 🧵 **WS2-R3 durable task progress polling foundation** — 后端新增 `durable_task_progress_events` 持久化进度事件表与 owner-scoped 读取 helper，提供 `/api/v1/analysis/status/{task_id}/poll` 轮询 fallback，返回当前 durable task state、可按 `after_sequence` replay 的安全事件、latest sequence 与 terminal 标记。WS2 synthetic worker prototype 会写入 claim/progress/retry/failure/completion 事件；现有 process-local `AnalysisTaskQueue` 与 `/api/v1/analysis/tasks/stream` SSE 仍是默认路径，不做 production queue/SSE cutover，不引入 Redis/Celery/RQ/Dramatiq/Kafka、多实例部署、quota enforcement、live LLM/provider 调用、frontend 改动或 scanner/backtest/portfolio/provider 行为变化。

- 🔐 **Admin RBAC Phase R3b ops-sensitive route migration** — 后端继续只迁移窄范围高风险 admin route：`/api/v1/admin/logs` 读类、session/detail 与 storage summary 要求 `ops:logs:read`，`/api/v1/admin/logs/cleanup` 要求 `ops:logs:write`；`/api/v1/system/config` 读/schema/validate 要求 `ops:system_config:read`，config 写入、runtime cache reset 与 factory reset 要求 `ops:system_config:write`，LLM / data-source probe 要求 `ops:providers:write`；`/api/v1/admin/notification-channels` 与 `/api/v1/admin/notifications` 读类要求 `ops:notifications:read`，channel create/update/delete/test 与 notification ack 要求 `ops:notifications:write`。现有 coarse admin 继续通过 compatibility capability 通过；本阶段不改前端 nav、不迁移完整 admin surface、不接入 MFA/re-auth、不改变 provider/LLM/notification delivery、scanner/backtest/portfolio、Options Lab 或 WS2 行为。

- 🧾 **DB production readiness audit** — 新增 docs-only 审计 `docs/audits/db-production-readiness-index-retention-audit.md`，梳理 WolfyStock public multi-user 前的数据库 index、retention、backup/restore、growth control 与 observability 缺口。该审计只给出后续实施顺序和风险矩阵，不修改 runtime code、schema、migrations、tests、provider/MarketCache、scanner、backtest、portfolio、LLM、notification、Options、DuckDB、RBAC 或 WS2 runtime 行为。

- 🔐 **Admin RBAC Phase R4A backend capability summary contract** — 现有 current-user auth contract 现在返回安全、稳定的 capability 摘要：`GET /api/v1/auth/status` 的 `currentUser`、`GET /api/v1/auth/me` 与 login response 均包含排序后的 `adminCapabilities`，并派生 `canReadUsers`、`canReadUserActivity`、`canReadUserPortfolio`、`canWriteUserSecurity`、`canReadCostObservability`、`canReadOpsLogs`、`canReadProviders`、`canReadNotifications`、`canReadSystemConfig` 供未来前端 capability-aware navigation 使用。后端 route guard 仍是权威授权来源；本阶段不改前端 nav、不迁移更多 admin route、不移除 `require_admin_user()`，也不暴露 password hash、raw session、cookie、token、API key、secret、broker/provider credential、`.env` 值、raw role mapping internals 或 grant metadata。

- 🔐 **Admin RBAC Phase R3 pilot route migration** — 后端仅将小范围高风险 admin route 从 `require_admin_user()` 迁移到 R2 capability helper：`POST /api/v1/admin/users/{user_id}/disable`、`/enable`、`/revoke-sessions` 现在要求 `users:security:write`；`GET /api/v1/admin/users/{user_id}/portfolio-summary`、`/holdings`、`/portfolio-activity`、`/portfolio/accounts/{account_id}` 现在要求 `users:portfolio:read`。现有 coarse admin 通过 R1 compatibility layer 保持 super-admin-equivalent capability；保留原因、typed confirmation、self-disable、last-admin、审计脱敏与 portfolio read-only 行为。本阶段不迁移完整 admin surface，不改前端 nav，不移除 `require_admin_user()`，不改变 portfolio accounting/sync/cash/holdings/P&L/import/replay/FX/broker、scanner、backtest、LLM、provider、notification、DuckDB 或 Options 行为。

- 🧪 **Options Lab Phase 4 Defined-Risk Strategy Comparison** — 新增 backend-only、fixture-backed 的 `POST /api/v1/options/strategies/compare`，基于 synthetic `TEM` option chain 比较 long call、long put、bull call spread 与 bear put spread。输出包含 legs、net debit、max loss、max gain、breakeven、required move、target payoff、risk/reward、liquidity warnings、IV/theta notes、assumption-based suitability notes、limitations 与 no-advice disclosure；`maxPremium` 只过滤策略 net debit。该阶段明确拒绝 unsupported/naked-short/credit spread 类策略，不接入 live provider、LLM、broker execution、order placement 或 portfolio mutation，也不改变 scanner/backtest/provider/MarketCache/AI/notification/DuckDB 行为。

- 🔐 **Admin RBAC Phase R2 backend capability helpers** — 后端新增未来 capability-based admin authorization 可复用的 helper/dependency primitives：`require_admin_capability()`、`require_any_admin_capability()`、`require_sensitive_reason()`、`require_recent_admin_reauth()`、`assert_not_self_destructive_action()` 与 `assert_not_last_super_admin()`。这些 helper 继续复用 R1 的 `expand_admin_capabilities()` / `has_admin_capability()`，缺失 capability 返回脱敏 403，不泄露角色清单、password hash、raw session、cookie、token、API key、secret、broker credential 或 `.env` 值；recent reauth 在当前无明确 reauth metadata 时 fail-closed。当前阶段不迁移任何现有 admin route，不改变 `require_admin_user()` 行为，不实现 MFA/角色管理 UI，也不改变 scanner/backtest/portfolio/provider/MarketCache/AI/notification/DuckDB/Options 行为。

- 🔐 **Admin RBAC Phase R1 compatibility layer** — 后端新增只读 RBAC/capability 兼容层：SQLite 初始化创建并 seed `admin_roles`、`admin_role_capabilities`、`admin_user_roles`，内置 `super-admin`、`security-admin`、`support-admin`、`ops-admin` 与设计文档中的 capability taxonomy。现有 `role == "admin"` / `is_admin` 用户会扩展为 super-admin 等价 capability，普通用户没有 admin capability；新增 `expand_admin_capabilities()` / `has_admin_capability()` 只供未来阶段读取元数据。当前阶段不迁移路由、不改变 `require_admin_user()`、不实现 MFA/角色管理 UI，也不改变 scanner/backtest/portfolio/provider/MarketCache/AI/notification/DuckDB 行为。

- 🔐 **Security Phase 2 session/header/proxy hardening** — 后端现在对管理员会话增加 `ADMIN_SESSION_IDLE_TIMEOUT_MINUTES` 空闲超时，复用现有 `app_user_sessions.last_seen_at` 元数据并保留 `ADMIN_SESSION_MAX_AGE_HOURS` 绝对有效期；过期管理员会话在校验时撤销。FastAPI 响应新增 baseline security headers，HSTS 仅在 production + HTTPS 上下文返回。部署文档补充 HTTPS reverse proxy 模板、HSTS、body size、timeout、proxy headers、SSE/WebSocket 与不要直接公开后端 `:8000` 的生产建议。本阶段不改变密码 KDF、MFA、RBAC、scanner/backtest/portfolio/provider/MarketCache/AI/notification/DuckDB 或 Options Lab 行为。

- 🧪 **Options Lab Phase 3 Backend Scoring / Scenario Engine** — 新增 backend-only、fixture-backed 的 `POST /api/v1/options/analyze` 与 `POST /api/v1/options/scenario`，继续仅使用 synthetic `TEM` fixture，不接入 live option provider、LLM、broker execution、order placement、portfolio mutation、scanner/backtest、MarketCache、AI、notification 或 DuckDB 行为。Analyze 现在为 long call / long put 生成 0-100 bounded deterministic sub-score、grade、drivers、assumptions、data confidence 与 no-advice disclosure；Scenario 提供到期日 deterministic payoff grid、premium at risk、breakeven、required move 与 max loss，并明确 Phase 3 不提供到期前理论定价、spreads 或交易建议。

- 🧪 **Options Lab Phase 2 Frontend Shell** — 新增 `/zh/options-lab` 前端只读期权实验室壳层，包含中文情景假设、标的快照、到期日过滤、Calls/Puts 模拟链表、候选排序/策略比较/情景收益占位与显式风险披露。当前阶段使用 mocked / fixture-compatible 数据，不接入 live option provider、LLM、broker execution、portfolio mutation、order CTA、scanner/backtest、MarketCache、AI、notification 或 DuckDB 行为，也不显示 raw provider payload、request URL、API key、token、secret 或 stack trace。

- 🔐 **Public auth hardening Phase 1** — Web 登录失败现在统一返回不可枚举的 generic error，失败/限流/失败后成功登录会写入脱敏 security execution log；登录限流从进程内 IP-only 扩展为持久化 IP + account 哈希桶，生产模式强制 Secure session cookie，Cookie 认证的写请求增加 Origin/Referer 校验，生产 CORS 禁止 wildcard 并要求显式 `CORS_ORIGINS`。本阶段不改变密码 KDF、MFA、RBAC、portfolio/scanner/backtest/provider/MarketCache/AI/notification/DuckDB 行为。

- 🧪 **Options Lab Phase 1 Backend** — 新增只读、fixture-backed 的 Options Lab 后端接口：`GET /api/v1/options/underlyings/{symbol}/summary`、`/expirations`、`/chain`。当前阶段仅支持 synthetic `TEM` 期权链样例，返回安全 normalized contract / expiration / metadata / limitations，不暴露 raw provider payload、API key、token、secret 或 request URL；tests 采用本地 synthetic fixture，且不会调用 live provider、LLM、broker、portfolio mutation、scanner/backtest、MarketCache 或 notification 路径。Phase 1 仅做链路与合同打底，不包含 scoring、strategy comparison 或下单能力。

- 🔐 **Production Security Scan CI Gates** — 新增独立 `Security Scan` GitHub Actions workflow，覆盖 redacted Gitleaks secret scan、Python `pip-audit`、`apps/dsa-web` production-only `npm audit`、Bandit SAST 与本地构建镜像的 Trivy 漏洞扫描；同时新增 `scripts/security_scan.sh` 作为本地安全扫描辅助脚本，默认不安装工具、不运行依赖更新/修复、不启动服务、不推送镜像，并将本轮实现备注补充进生产安全加固审计文档。该变更仅增加 CI/开发者 guardrail，不改变 runtime、UI、API、依赖锁文件或部署目标行为。

- 🔐 **Admin Data Control Center Frontend Phase F3/F4** — `/zh/admin/users/:userId` 现已接入“组合”和“安全”标签：组合页只读展示账户数、估值、持仓、组合活动与 masked broker handle；安全页提供 disable / enable / revoke-sessions 三个 S1 控制，均要求操作原因和 typed confirmation，并在成功时展示安全的 `auditEventId`。前端不会显示 plaintext password、`password_hash`、raw session id、cookie、token、API key、broker credential、`payload_json`、`sync_metadata_json`、raw prompt/provider payload 或 stack trace；不实现 reset-password、force-password-change、unlock、RBAC，也不触发 broker sync、导入、重放、FX refresh、provider/LLM/MarketCache/scanner/backtest/portfolio accounting/notification/DuckDB 行为。

- 🔐 **Admin Security Controls Backend Phase S1** — 新增有限、管理员专用账户安全动作 API：`POST /api/v1/admin/users/{user_id}/disable`、`POST /api/v1/admin/users/{user_id}/enable`、`POST /api/v1/admin/users/{user_id}/revoke-sessions`。接口复用现有 `AppUser.is_active`、app-user session revocation、`require_admin_user()` 与 ExecutionLogService admin action 审计模式，要求 `reason`、typed confirmation，并实现 self-disable 与 last-active-admin guardrail；响应只返回安全动作状态、是否变更、`sessionsRevoked` 计数和审计事件引用，不返回 password/hash、raw session id、cookie、token、API key、secret、reset token 或 request body。该阶段不实现 reset-password、force-password-change、unlock、failed-login/lockout、RBAC/capability migration、前端安全 UI，也不改变 portfolio accounting、scanner/backtest/provider/MarketCache/AI/notification 或 DuckDB 行为。

- 🔐 **Admin Portfolio Visibility Backend Phase 1** — 新增只读、管理员专用组合可见性 API：`GET /api/v1/admin/users/{user_id}/portfolio-summary`、`GET /api/v1/admin/users/{user_id}/holdings`、`GET /api/v1/admin/users/{user_id}/portfolio-activity`、`GET /api/v1/admin/users/{user_id}/portfolio/accounts/{account_id}`。响应只返回安全投影：账户/同步/持仓/流水计数、脱敏 broker account handle、聚合金额、状态与时间戳；不返回 broker token、raw broker ref、`payload_json`、`sync_metadata_json`、导入原文件、API key、session id、cookie、password hash、raw note 或 secret-like metadata。新增最小 admin-governance audit helper，通过既有 ExecutionLogService admin action 模式记录 `admin_portfolio.*_viewed` 事件；不改变 portfolio accounting、holdings/cash/P&L/exposure/FX、broker sync/import/replay、scanner/backtest/provider/MarketCache/AI/notification 或 DuckDB 行为。

- 🔐 **Admin Data Control Center Frontend Phase F1/F2** — `apps/dsa-web` 新增只读用户治理入口与路由 `/zh/admin/users`、`/zh/admin/users/:userId`、`/zh/admin/users/:userId/activity`，接入已实现的 Admin Users / Activity API。页面提供用户目录安全搜索、角色/状态筛选、用户详情概览、脱敏会话摘要、活动时间线筛选和后续安全/组合/分析/Scanner/Backtest/管理审计占位；默认中文、复用现有 Admin glass/operator 布局，并保持原始调试/开发者细节折叠且敏感 metadata 前端再次过滤。不新增安全控制，不改变认证授权、backend API、provider/MarketCache、scanner、backtest、portfolio、AI、notification 或 DuckDB 行为。

- 🧾 **Duplicate-Cost Admin Summary Backend Phase 2** — 新增只读、管理员专用 API：`GET /api/v1/admin/cost/duplicate-summary`，聚合当前进程内 LLM、provider fallback/cache、MarketCache 与 Scanner AI instrumentation counters，并在可用时补充既有 `llm_usage` accounting summary。响应包含 `summary / llm / providers / marketCache / scannerAi / limitations / metadata`，明确 `readOnly=true`、`noExternalCalls=true`、`countersSource=process_local` 与 `exactness=observational_not_billing`；counter snapshot 不支持历史窗口时通过 limitations 明示，不伪造历史 bucket。该接口不调用 LLM/provider，不触发 MarketCache refresh、scanner/backtest/portfolio/report/notification/DuckDB 行为，也不返回 raw prompt/message/provider payload/URL/API key/token/session id/stack trace/cache key/candidate payload/report output。

- 🔐 **Admin Data Control Center Backend Phase 1/2** — 新增只读、管理员专用的用户目录、用户详情与活动时间线 API：`GET /api/v1/admin/users`、`GET /api/v1/admin/users/{user_id}`、`GET /api/v1/admin/users/{user_id}/activity`、`GET /api/v1/admin/activity`。响应只返回安全投影：用户基础字段、派生 `passwordState`、会话计数、脱敏会话 handle、活动事件的哈希 request/session/entity 引用与已脱敏 metadata；不返回 `password_hash`、原始 session id、cookie、token、API key、prompt/provider payload、request body、stack trace 或 analysis raw payload。首版活动时间线以 Execution Logs、AnalysisHistory 和 auth session snapshot 为保守来源，scanner/backtest/portfolio 深投影后续单独实现；不改变认证、授权、Portfolio accounting、Scanner 排名、Backtest 计算、provider/MarketCache、AI/LLM、notification 或 DuckDB 行为。

## 2026-05-05

- 🦆 **DuckDB Quant Engine Phase 2（可选因子验证路径）** — 可选 DuckDB quant engine 新增只读 `factor_daily` snapshot、factor path coverage validation 与 runtime context comparison 管理员接口：`/api/v1/quant/duckdb/factor-snapshot`、`validate-factor-path`、`compare-runtime-context`。响应会明确返回 `dataMode`、coverage、row count、factor dates、missing/insufficient symbols、duration 与 diagnostic labels；禁用模式继续 `QUANT_DUCKDB_ENABLED=false` 默认且不创建 DuckDB 文件。该路径只供 scanner/backtest-like symbol/date context 对照验证，不替换 scanner scoring/ranking、backtest calculation、Portfolio accounting、AI decision 或 notification routing。

## 2026-05-04

- 🔔 **Admin Notification Rules 运维视图增强** — `/admin/notifications` 新增路由覆盖摘要、规则分组、覆盖事件、最近触发/失败状态和明确的“仅解除日志路由绑定”删除文案；测试发送拆出“仅验证/试运行”和真实测试发送，试运行只校验目标配置不会发送通知。后端通知规则列表补充安全的 coverage/status/target 摘要字段，并为测试接口增加 `dry_run=true`，继续保持删除规则只移除 `log_notification_association`，不删除系统通知通道或凭据。

- 🦆 **DuckDB Quant Engine Phase 1.5（验证层）** — 可选 DuckDB quant engine 新增显式 OHLCV ingest、`StockDaily` 本地存储 bounded ingest、`factor_daily` 基础日频因子构建、coverage 报告与 richer benchmark metadata。新增 `/api/v1/quant/duckdb/ingest-ohlcv`、`build-factors`、`coverage`，并增强 `benchmark` 返回 `durationMs / rowsScanned / symbolsScanned / dataMode / topResults`。DuckDB 继续默认 `QUANT_DUCKDB_ENABLED=false`，禁用时不会创建数据库文件；PostgreSQL 仍是业务数据库，不使用 `pg_duckdb`，不改变 scanner selection、backtest 计算、Portfolio accounting、AI 决策或通知路由。

- 🦆 **DuckDB Quant Engine Phase 1（可选骨架）** — 新增只读 DuckDB quant analytics skeleton：`QuantDuckDBService` 可显式初始化 `ohlcv_daily / factor_daily`、写入小批量 OHLCV 样本、用 SQL window function 生成 MA/momentum/volatility/dollar-volume 基础因子，并通过管理员接口 `/api/v1/quant/duckdb/health|init|benchmark` 返回安全 health 与 benchmark 计数。DuckDB 默认 `QUANT_DUCKDB_ENABLED=false`、懒加载依赖且不参与 app startup；PostgreSQL 仍是业务数据库，现有 Python backtest、scanner selection、backtest 计算与 Portfolio accounting 均不接入也不改变。

- 🧼 **剩余系统页面中文界面抛光** — `/backtest/compare`、`/settings/system`、`/admin/logs` 与 `/admin/notifications` 继续清理中文 UI 里的英文标题、状态、角色与调试式 backend key。回测比较页把 `metric strip`、`comparison_highlights`、`baseline/candidate/unavailable` 等可见文案映射为中文，管理员通知把 `critical/warning/info` 渲染为中文严重级别，系统设置把 Provider/Runtime/Fallback/Quick API 等界面标签收口为服务商、运行时、备用模型与快速接口；仅调整展示文案和测试断言，不新增功能、不改变 AI 路由、数据源、回测或通知规则逻辑。

- 🧼 **中文界面抛光与调试文案收口** — `/zh`、`/chat`、`/market-overview`、`/scanner`、`/portfolio`、`/watchlist`、`/backtest` 与回测结果页统一清理中文界面中的英文状态/章节标签，Watchlist、Market Overview、Home、Portfolio、Backtest 的默认 UI 不再暴露 `SCANNER CANDIDATES`、`UNKNOWN`、`LOCAL/ERRORS`、`MARKET STATE`、`Trade Station`、`Key Metrics` 等调试式或英文 chrome。Scanner 开发者诊断仍保持折叠，保留 ticker、provider、API/格式与专业指标缩写；同时收紧卡片 padding、表格行间距和窄屏换行，不改变 scanner selection、backtest 计算、portfolio 会计公式、AI 决策算法或后端 API。

- 🧠 **Decision Desk Evidence v2** — `/chat` 检测到股票代码后新增只读 `/api/v1/agent/stock-evidence` 证据查询，合并轻量实时行情、已有本地日线技术指标和已持久化分析/行情中的基本面字段，不调用 LLM、不自动运行 scanner/backtest/analysis。数据上下文现在可显示行情价格/provider、技术 MA/RSI/支撑压力、基本面 partial/missing 字段和新闻 UNKNOWN；发送给 AgentExecutor 的 `stock_context.evidence` 改为紧凑证据摘要，并明确要求只使用 available/partial/stale/fallback 证据、UNKNOWN/MISSING 必须如实说明。回答 footer 同步展示行情、技术、基本面、持仓、观察列表、Scanner 与回测状态，不暴露 raw prompt / system prompt / API key。

- 📊 **Market Overview Relevant Depth v3** — `/market-overview` 的美股页签新增基于 Yahoo/yfinance proxy 的 sector ETF breadth proxy，展示上涨/下跌行业数、最强/最弱行业 ETF 与 RSP/SPY、IWM/SPY、QQQ/SPY 相对压力；加密页签把 Binance 公开行情扩展到 BTC/ETH/SOL/BNB，并在可用时展示 Binance Futures funding rate。稳定币流动性、dominance、真实美股 advance/decline、A股/HK 北向南向实时源仍按未接入/备用状态紧凑展示，不冒充实时数据；新增 `/api/v1/market/us-breadth` 继续复用 MarketCache、SWR 与 last-known-good snapshot 元数据。

- 🧾 **Home AI Report UX v3 身份与完整报告映射** — `/zh?fixture=analysis-trace` 的 Home AI 决策卡不再把 `待确认股票` 当作用户可见公司名；公司身份统一走 `companyName / stockName / quote / profile / fundamentals / overview / metadata / standardReport` 等字段的去重 fallback，最后只回退到 ticker 或 `--`。独立来源/动作卡彻底移除，`完整报告 / 决策来源 / 复制报告 / 重新分析` 现在位于 AI 决策卡右上动作区，紧凑来源行留在卡片内部。完整报告抽屉与 Markdown/PDF 导出补齐重要信息速览、风险警报、利好催化、当日行情、数据透视、技术透视、基本面摘要、作战计划、检查清单和数据说明，并对 provider 列表按顺序去重；Trace 抽屉继续默认折叠开发者细节且不暴露 raw prompt / system prompt / API key。

- 🧭 **Scanner 候选优先工作台 v3 收口** — `/scanner` 结果区进一步收口为 candidate-first 工作流：顶部改为紧凑扫描命令条与单行阈值预览，候选池默认提前到诊断/历史对比/策略实验之前，移动端也保持“控制 -> 摘要 -> 候选池 -> 选中候选 -> 次级面板”的顺序。候选行改为终端式结构，只保留一个主动作和 `更多` 二级动作；右侧 Inspector 改为“为什么入选 / 主要风险 / 下一步”的决策卡，并把规则诊断、数据质量、开发者字段收进默认折叠区。此次仅调整 `apps/dsa-web` 前端展示与交互层次，不改变 scanner selection logic、threshold preview 计算、strategy simulation、backtest 计算或后端 endpoint。

- 🧾 **Home AI 完整报告升级为正式投研报告与导出动作** — `/zh?fixture=analysis-trace` 的 Home AI 决策卡现在统一展示公司全称与代码（如 `Tempus AI (TEM)`），历史记录标题会去重重复 ticker；原独立来源/动作卡已移除，`完整报告 / 决策来源 / 复制报告 / 重新分析` 收进主 AI 决策卡。`完整报告` 抽屉升级为正式金融研究报告格式，覆盖投资结论、执行计划、核心证据、风险、催化、市场、技术、基本面、检查清单和数据说明，并支持 Markdown 导出与浏览器打印/PDF；`决策来源` 继续保持紧凑 trace，开发者细节默认折叠且不暴露 raw prompt / system prompt / API key。

- 💱 **Portfolio 显示货币迁移到个人设置** — `/settings` 新增“资产显示偏好 / 默认显示货币”，统一保存 CNY/USD/HKD/EUR/JPY 总资产展示偏好；`/portfolio` Hero 移除大型显示货币选择器，改为紧凑状态、设置入口、按币种资产摘要与账户币种信息。交易台新增结算货币自动推断和手动覆盖，持仓继续显示原始币种并在可用时补充偏好币种折算，不改变成本法、会计公式或后端 FX provider 行为。

- 🧠 **Home AI 判断结果改为 summary-first 报告体验** — `/` 与 `/zh` 的 Home AI 结果页移除常驻右侧重型 Decision Trace 面板，默认只展示决策摘要、执行计划、技术/基本面高亮与紧凑来源行。`完整报告` 打开大型完整判断报告抽屉，按执行摘要、重要信息速览、风险警报、利好催化、当日行情、技术透视、作战计划、检查清单和数据说明组织既有报告字段；`决策来源` 打开紧凑 trace 抽屉，开发者细节默认折叠且不暴露 raw prompt / system prompt / API key。新增 `/zh?fixture=analysis-trace&report=open` 作为无 LLM 调用的浏览器验收入口。

- 🧊 **Market Overview Last-Known-Good 快照与缓存 UX** — `/market-overview` 新增后端持久化 last-known-good panel snapshot，外部行情源超时或冷启动失败时优先返回最近成功快照并标记 `stale/isFromSnapshot/lastSuccessfulAt/refreshError`，不再用空 payload 覆盖好数据。前端新增 `wolfystock.marketOverview.lastKnownGood.v1` 本地快照，页面刷新或后端慢启动时先渲染 LOCAL CACHE，再静默刷新；卡片级错误收敛为小型 STALE/ERROR badge，顶部状态条聚合 CACHE/STALE/REFRESH FAILED 与错误数量，减少重复红色错误块和 N/A 墙。

- 🧠 **Stock Chat Phase 2 升级为 AI 决策台** — `/chat` 可见导航从“问股”收口为“决策台 / WOLFY AI 决策台”，移动端空态压缩为单个主模板与“更多模板”，控制台改为默认折叠抽屉并修复 Safari 窄屏透明遮挡。AI 引擎新增安全的 provider health 视图，只展示 DeepSeek/OpenAI/Gemini/Local 等 provider 的可用、未配置、离线或未知状态，不暴露 API key；检测到代码后只读取既有观察列表、持仓快照、scanner 历史和 rule backtest 历史证据，不自动运行 scanner/backtest/AI 分析，并把紧凑证据摘要传入 AgentExecutor 与每条回答底部证据 footer。

- 🧠 **Stock Chat Phase 1 引擎透明化与 Smart Routing** — `/chat` 问股控制台将 AI 引擎、分析视角与数据上下文拆分展示，默认以综合判断、趋势跟踪、均线系统、放量突破、箱体震荡、情绪周期、龙头策略、持仓风控、基本面质量与事件驱动等专业视角呈现，并把缠论/波浪/一阳夹三阴收进高级辅助视角。输入框新增本地 deterministic Smart Route，识别 ORCL/AAPL/600519/0700.HK 等代码、US/CN/HK 市场、买入持有/持仓管理/突破/对比/趋势/基本面/事件等意图，并只推荐视角不自动触发分析。聊天请求新增 `structured_stock_analysis_v1` 输出契约，要求结论、关键依据、关键价位、风险、操作计划与数据可信度结构化输出；数据证据面板默认明确 unknown，不冒充已使用数据；检测到单标的时提供回测、加入观察列表、查看持仓、扫描器证据和分析报告 quick actions，全部由用户点击触发。

## 2026-05-02

- 📌 **观察列表策略证据同步 Phase 1** — `/watchlist` 现在把已有 scanner 评分/入选状态、scanner theme/profile 上下文与最新已完成单标的 rule backtest 摘要同步为紧凑策略证据条，支持按扫描分数、回测收益、历史胜率、最近评分与最近回测排序，并新增有扫描证据、有回测证据、扫描入选和证据过期筛选。观察列表新增用户手动触发的“观察列表单标的回测”批量动作，复用既有 Backtest API、限并发 2、当前会话去重，并在完成后原位更新 BT/DD/Sharpe 与结果链接；页面加载不会自动重跑 scanner、strategy simulation 或 backtest，也不改变 scanner 入选/排序逻辑、策略历史模拟计算或 backtest 收益计算。

- 🧪 **Scanner 策略历史模拟 Phase 1** — `/api/v1/scanner/strategy-simulation` 新增基于已持久化 scanner runs 的轻量历史模拟，按 theme/profile/market 与 30/90/180D 窗口筛选历史扫描，并用本地历史价格计算 1/5/10/20 日 forward return、benchmark/excess return、命中率、覆盖率、run 摘要与 symbol 聚合；历史不足时返回 `insufficient_history`，不主动生成历史扫描、不调用 AI、不改变 scanner 入选/排序逻辑或 backtest 收益计算。`/scanner` 进阶工具新增默认折叠的“策略历史模拟”面板，复用当前扫描上下文发起查询，并以紧凑终端风格展示不足历史、汇总、run 表与 symbol 表。

- 🧪 **Scanner 候选单标的回测实验室** — `/scanner` 新增紧凑的 Backtest Lab，可由用户手动对官方入选、预览入选、前 5 名、当前筛选或单个候选启动“候选单标的回测”，复用既有 rule backtest API 与共享 `/backtest/results/:id` 报告路由。批量回测由前端限并发编排并在当前会话内按 symbol/config/strategy 去重，不会在扫描运行或本地阈值预览变化时自动触发，也不改变 scanner 入选/排序规则或 backtest 计算逻辑。

- 🧭 **Scanner 决策工作台渐进披露** — `/scanner` 将结果区默认视图收敛为决策摘要、核心计数、入选分析/回测/观察动作、入选卡片与候选预览；导出、复制、历史回放、策略阈值预览、历史对比、批量观察与诊断详情改为紧凑展开区，移动端按配置、决策、动作、候选、进阶工具、列表与详情顺序堆叠。此次仅调整前端展示与本地阈值预览交互，不改变 scanner backend API、入选规则、排序语义或观察名单接口。

- 🧭 **Scanner 策略预览与 Run 对比工作台** — `/scanner` 在不改变后端入选规则的前提下新增客户端阈值预览、官方/预览/淘汰/数据失败标签、候选池本地重排、上次同 profile/theme/market run 对比、Inspector 对比摘要，以及“加入全部入选 / 加入预览入选 / 加入前 5 名 / 加入当前筛选”批量观察动作。阈值预览只复用当前 run 已返回的 `candidates / score / status / failed_rules / reason` 诊断数据，不重新扫描、不触发额外行情或 provider 调用。

- 📌 **观察列表评分刷新与分析交接修复** — `/watchlist` 的分析按钮现在会把异步分析返回的 `task_id`、`symbol`、`source=watchlist` 和市场写入 Home query handoff，Home 决策页收到 watchlist 任务后以 `task_id` 为权威对象显示对应代码的 Wolfy AI 分析中骨架，不再把旧 ORCL 报告当作当前内容；任务完成后优先用该 task 的 final result 更新 WULF 等目标报告。观察列表新增轻量评分刷新接口 `/api/v1/watchlist/refresh-scores` 与状态接口，刷新只复用已持久化 Scanner 候选评分更新 score/rank/last_scored_at/stale 状态，不为每个候选启动完整 AI 报告。

- 🧭 **Scanner 主题候选诊断透明化** — `/api/v1/scanner/run` 在保留既有 `shortlist` 的基础上新增 `theme`、`summary`、`selected` 与 `candidates` 诊断载荷，主题扫描会返回完整候选池、已评估/入选/淘汰/数据失败/跳过计数、每个非入选候选的原因、失败规则、缺失字段、provider 与关键指标。主题/自定义标的扫描不再让 `detail_limit` 截断已提交的完整主题候选池；`/scanner` 结果区新增紧凑计数条和“入选 / 候选池 / 淘汰 / 数据失败 / 全部”过滤表，让 `加密矿企 · 11` 这类主题能直接解释为什么只有少数标的入选。

- ⚡ **单股分析新增配额感知数据源规划** — 分析流程为行情、基本面、财报、历史价格、技术指标、新闻与情绪建立按类别的首选 provider + lazy fallback 计划，独立类别可并发加载，同一类别不再默认并发打多个重叠 API；新增 in-process TTL cache、singleflight 请求合并、超时 fallback 与 provider/category 级临时熔断，减少 ORCL 等美股分析的重复外部调用。明显美股代码的名称解析不再回落到 Tushare / pytdx / Baostock 等 A 股名称源；Home 加载态同步展示市场识别、行情、基本面、技术、新闻与 AI 分析等紧凑阶段进度。

- 🧭 **Scanner 输入校验与 Market Overview 隐蔽滑动** — `/scanner` 自定义标的与 AI 自定义主题生成在请求前增加字段级校验反馈，覆盖主题名称、criteria prompt、候选池与明细数量、主题选择和手动补充代码数量，避免无效参数直接落到后端错误。`/market-overview` 主市场卡片轨道在桌面以下改为可横向滑动，桌面继续保持主轨 grid；全局与 WolfyStock SpaceX 主题滚动条默认隐蔽，并在滚动容器 hover/focus 时显示深空风格细滚动条。

- 🔔 **Admin Logs 复用现有通知渠道发送重要日志** — 管理员通知规则新增 `system_channel` 类型，可引用系统设置中已经配置好的 Discord、Email、WeChat、Slack 等通知渠道，不再要求在日志中心重新保存 webhook 凭据。执行日志写入 NOTICE / WARNING / ERROR / CRITICAL 时会按规则生成 `admin_logs.event` 通知事件，ERROR / CRITICAL 映射为 critical，WARNING 映射为 warning，NOTICE 映射为 info；未配置匹配规则时不会污染通知事件表。`/admin/notifications` 创建规则时默认选择已有系统渠道，并展示当前可用的系统通知渠道；删除按钮只移除日志通知规则关联，不删除系统设置中的真实通知渠道配置。

## 2026-05-01

- 🧾 **Admin Logs 增加容量配额与容量清理** — Admin Logs storage summary 现在返回 PostgreSQL 表总占用、soft/hard limit、使用率、minimum retention、capacity cleanup guidance 与 autovacuum 提示；容量清理模式会在 PostgreSQL size 可用且超过 hard limit 时按最旧可删日志分批删除，并始终保留 `ADMIN_LOG_MIN_RETENTION_DAYS` 内的近期日志。`/admin/logs` 顶部容量条改为明确展示 “当前占用 / soft limit / hard limit”、日志 sessions/events 体量、最早日志、retention/min-retention 与 retention/capacity cleanup 预览及确认操作。SQLite/非 PostgreSQL 环境继续返回 size unavailable 并保留 retention/row-count 健康检查。

- 🧾 **Admin Logs 新增保留策略与清理能力** — `/api/v1/admin/logs/storage/summary` 提供日志总量、事件数、最早/最新时间、保留天数、超过保留期数量、PostgreSQL 存储估算与健康状态，`/api/v1/admin/logs/cleanup` 支持按保留策略或显式截止时间 dry-run / 分批清理，并拒绝无截止条件的危险删除。`/admin/logs` 顶部新增紧凑 Retention / Storage 面板，展示容量与清理建议，支持预览清理和带确认的手动清理，同时保留既有日志列表、筛选与详情行为。

- 🧭 **Market Overview 摘要化与首屏层级精简** — `/market-overview` 默认视图将波动率与资金流向提前到主轨首行，顶部控制条整合市场筛选与摘要导出，市场温度、数据质量和市场解读收口为紧凑状态条；右侧轨道默认只保留分类覆盖与详细信号展开入口，减少首屏重复内容和侧栏纵向挤压。高密度行情卡默认优先展示关键 4-5 项，并保留“其余项在数据源快照中”的提示，保持数据可追溯但降低 100% zoom 下的信息噪音。

- 🧠 **Scanner AI 自定义主题扩展** — `/scanner` 的 Theme universe 面板新增 AI custom theme builder，用户可输入主题名称、criteria prompt 与可选手动补充代码，生成如 White House Stocks、AI Semiconductor Stocks、Green Energy Stocks 等运行时自定义主题，并立即查看 symbol suggestions、confidence 与 evidence。后端新增 `POST /api/v1/scanner/themes`，生成主题以 `source=ai_generated`、`is_seed_list=false`、`requires_manual_maintenance=true`、`refresh_policy=on_demand` 暴露，并继续复用既有 `universe_type=theme` 扫描路径；AI 只扩展 theme universe，不替代 deterministic scanner 排名。

- 🧾 **Admin Logs Health Summary Phase 2** — `/api/v1/admin/logs` 与原始 `/sessions` 列表在保持兼容的基础上新增可选 `health_summary`，按当前查询窗口派生 total/failed/warning/slow、failure rate、overall status、失败 category/provider/reason Top N、actor breakdown 与最近错误摘要，继续复用现有 execution log/business event 读取结果并保持错误摘要脱敏。`/admin/logs` 顶部新增紧凑健康摘要区，展示 healthy/degraded/failing、失败数量/比例、最常失败功能、provider/source 与 reason 聚合，以及最近严重错误。
- 🔐 **Settings 新增 Notification Channels 专用管理面** — `/settings/system` 现在为 Feishu、Telegram、DingTalk、Email、Discord、Slack、WeChat webhook、PushPlus、Pushover、ServerChan 与 Custom webhook 提供专用通知渠道卡片，展示配置状态、非敏感路由字段和已脱敏凭据，并通过既有系统配置保存接口保留 masked secret placeholder 语义。后端继续兼容原有 `.env` 配置读取，同时为通知渠道键补充 `managed_by=notifications`、`ui_visibility=curated` 与 `raw_editable=false` 元数据，确保这些凭据不回流到通用 raw settings 抽屉。

- 🧾 **Admin Logs 维护 triage 字段 Phase 1** — `/api/v1/admin/logs` 的业务事件响应在保持兼容的基础上新增可选 `actorType / actorLabel / contextLabel / provider / source / component / reason / errorSummary / requestId / traceId / rootCauseSummary / stepTraceAvailable` 等派生字段，优先从现有 summary、metadata、event detail 与已脱敏 raw payload 中读取，不改动 execution log 持久化格式。`/admin/logs` 列表同步改为 Time / Event / Actor / Context / Source Provider / Reason / Status / Duration / Trace / Actions，详情抽屉顶部增加 Root Cause 区块；失败但没有 step trace 的事件不再显示“成功 0 · 跳过 0 · 失败 0 · 未确认 0”，改为明确的“失败 · 无步骤明细”。

- 📌 **观察列表新增候选追踪工作台** — `apps/dsa-web` 新增 `/watchlist` / `/:locale/watchlist` 页面与主导航入口，登录用户可集中查看 scanner 保存的候选，按代码/名称搜索，按市场、来源、主题或候选范围筛选，并按最新、扫描分数、代码或市场排序。页面展示总数、覆盖市场、scanner 来源和近期新增摘要，保留 run id、rank、score、theme、universe type 等扫描上下文，并复用既有分析触发、scanner-to-backtest query handoff、复制代码和 watchlist remove API。游客访问时继续显示登录保护，不开放持久观察名单。

- 📝 **Scanner 候选加入用户观察名单** — Scanner 结果页新增用户级 `Track / 已追踪` 动作，支持把候选保存到当前登录用户自己的观察名单，并在卡片/表格/详情里同步显示已追踪状态；后端新增独立的 `/api/v1/watchlist/items` 读写接口与 `user_watchlist_items` 持久化表，继续与现有 scanner admin/system watchlist endpoints 分离。该能力仅面向已认证用户，按 `owner_id + symbol + market` 做用户内幂等保存，并在 execution logs 中记录 watchlist add/remove 审计事件。

- 🧭 **Market Scanner 主题与自定义标的池** — Scanner 新增 `/api/v1/scanner/themes` 主题池接口，手动扫描请求支持 `universe_type=theme|symbols`、`theme_id` 与自定义 `symbols`，并在运行详情/历史中返回主题、自定义代码数量与无效代码等 universe metadata。首批美股主题提供 crypto miners、memory/storage、AI semiconductors 的人工 seed list；A 股光模块/CPO、液冷、算力租赁、存储、半导体设备、机器人主题先作为未配置占位池暴露，明确要求人工维护，不冒充完整权威成分。

- 🧾 **Guest / Portfolio / Scanner 执行日志归因补齐** — 公开 Guest analysis preview 现在会写入 execution log，不再只生成非持久化分析结果；日志中会标记 `actor_type=guest`、guest session/request id，并保留 symbol code 以便 Admin Logs 搜索 ORCL/AAPL 等游客分析。Execution log actor 元数据同步扩展为 `admin / user / guest / anonymous / system`，scanner 与 market overview 公共接口会传入当前 actor 或 anonymous/system 归因；Portfolio 的买卖、资金流水与公司行为写入路径新增 portfolio audit business event，记录 account、symbol、currency、record id 与 actor。

- 🔒 **System Settings 原始编辑面 Phase 1 收口** — `/settings/system` 的高级原始配置抽屉现在只展示明确允许 raw-edit 的运行时字段，`ADMIN_AUTH_ENABLED`、AI/Data Source provider keys、通知 webhook/token/password、`DEBUG`、`HTTP_PROXY`、`WEBUI_PORT`、`WEBHOOK_VERIFY_SSL`、`LITELLM_CONFIG`、`AGENT_SKILL_DIR` 与 `CUSTOM_DATA_SOURCE_LIBRARY` 等危险、重复或已归属专用页面的字段不再作为通用原始配置暴露。后端仍保留既有 `.env` 读取、masked secret preservation 与专用设置页兼容性，只通过 `raw_editable / ui_visibility` 标记收口 UI 编辑面。

- 🧼 **Settings 全局输入与极简减法清洗** — `apps/dsa-web` 修复共享 `Input` 的前置图标输入框内边距，带 `iconType` 的原生 `<input>` 现在直接获得 `pl-12`，同时移除 Settings Drawer 里覆盖横向 padding 的作用域规则，避免密码框、API Key 框和搜索类输入出现图标与文字重叠。Settings 主操作按钮从高饱和蓝紫渐变切换为低对比 `bg-white/5 border-white/10` 幽灵态微光按钮；`/settings` 删除顶部个人偏好标题、重复语言卡和大段说明小字，`/settings/system` 删除顶部标题/副标题、导航说明和系统概览里的保姆式解释文案，仅保留核心标签与操作控件。

## 2026-04-30

- 🧊 **Market Overview 全屏 Bento 终端化重塑** — `/market-overview` 外层容器放宽到 `max-w-[1600px]`，主内容区改为 `lg:grid-cols-12` 的 8/4 非对称 Bento 轨道：核心市场温度、解读、A股/港股、情绪、加密与宏观卡留在左侧主轨，全球核心指数与 ETF 资金流向进入右侧 `max-h-[600px]` 滚动辅助轨，避免页面退化成窄屏博客式纵向堆叠。Market Overview 专用卡片统一收敛为 `bg-white/[0.02] border-white/5 rounded-xl backdrop-blur-sm p-5` 幽灵态材质，卡片标题降噪为微型大写排版，涨跌与 Sparkline 统一切到 emerald/rose 霓虹色板。此次仅调整前端布局与视觉样式，不改变 API、数据刷新、分类、拖拽排序或 fallback 行为。

- 🧪 **Backtest 工作台按钮、表单与三栏布局重塑** — `apps/dsa-web` 对 `/backtest` 执行局部 UI 修复：普通/专业模式和历史评估里的回测按钮统一切到 emerald 微光主按钮或低调幽灵按钮；输入框、下拉框和复选框统一使用幽灵表单样式与 `gap-2` 垂直字段结构，避免标签与控件遮挡；历史评估工作台改为 `lg:grid-cols-12` 的 3:4:5 三栏比例，左侧步骤、中间诊断、右侧结果记录各自占位明确。此次改动保持回测 API、策略解析、历史评估状态和结果路由不变，只调整 Backtest 前端布局与视觉样式。

- 🏷️ **前端状态 Badge 语义收敛** — `apps/dsa-web` 新增统一 `StatusBadge` 与状态归一化工具，把 `success/succeeded/completed`、`failed/error`、`running/attempting`、`pending/queued`、`partial`、`skipped/not_needed`、`unknown` 等前端状态展示语义收口到一个复用入口。`/admin/logs` 已切到统一 badge，`Settings` 数据源校验状态与 `Backtest` 的一部分纯展示状态也改为复用同一组件；`Market Overview` 的 `DataFreshnessBadge` 保持 freshness 专用，不与普通业务状态混合。回归新增 `StatusBadge.test.tsx`，并补充 Admin Logs / Settings / Backtest 相关断言，确保 skipped 不再被误渲染为成功、unknown 不会被误渲染为运行中。

- 🎛️ **Home 信号语义色与个人偏好底座重标定** — `apps/dsa-web` 为首页决策台补上了真正受 `marketColorConvention` 驱动的动态红绿语境：`DecisionCard` 的 AI 动作 Hero、`StrategyCard` 的目标价 / 止损价以及同源 tone/glow 渲染不再写死国际市场配色，`红涨绿跌` 下买入/看多会切到 `rose`，卖出/看空切到 `emerald`，彻底消除“买入显示成白色”的语义错误。与此同时，全局字号偏好基准改为更紧凑的专业终端档位（XS=10px、S=12px、M=14px、L=16px、XL=18px），默认“标准”不再按 16px 放大整站；个人设置页“界面偏好”也同步扩容为语言、市场色彩、数据展示密度、数值缩写格式与字号五组专业选项，并全部接入本地持久化状态，为后续全局 density / number-format 联动铺好底座。

- 🔐 **Phase 0 安全止血：配置与日志脱敏** — 系统配置读取默认只返回 masked secret，Settings 前端只保存脱敏占位值，masked placeholder 提交不会覆盖真实密钥。Execution/Admin Logs 写入与读取路径统一脱敏 URL、error message、metadata、raw response 中的 API key、token、secret、password；`.env.example` 改为生产默认启用 `ADMIN_AUTH_ENABLED=true`，并补充 `CORS_ALLOW_ALL` 仅限本地开发的警告。

- 🧾 **Admin Logs 抽象为通用 Business Execution Trace** — `/api/v1/admin/logs` 的默认业务事件模型扩展为 `category/type/subject/scannerId/strategyId/backtestId` 等通用字段，新增 `start_execution/start_step/finish_step_success/finish_step_failed/skip_step/finish_execution` helper，统一 success/partial/failed/skipped/running/unknown/cancelled 状态语义；fallback provider/model 未调用、missing key、熔断和不适用市场会显示为 skipped 且不计入成功，真实 403/timeout 等调用失败计入 failed，主任务结束后的 running step 收敛为 unknown。`/admin/logs` 前端同步增加扫描器、回测、数据源 tabs、通用 step timeline、成功/跳过/失败统计和 metadata 脱敏展示；原始 session/event 日志继续保留在 `/api/v1/admin/logs/sessions` 与原始日志 tab。

- ⚡ **Market Overview 加密行情升级为 SSE 准实时流** — `/api/v1/market/crypto/stream` 新增 `text/event-stream` 实时推送，后台 `CryptoRealtimeService` 通过 Binance WebSocket 聚合 BTC/ETH/BNB ticker，约 1 秒节流更新内存快照并同步写入既有 `MarketCache` 的 crypto key，保留 `/api/v1/market/crypto` REST/cache/cold-start fallback 行为。`/market-overview` 的 CryptoCard 首屏继续使用 REST 快照，挂载后订阅 SSE，断线时保留最近快照并显示轻量 `Reconnecting/Snapshot/Live` 状态；新增 `CRYPTO_REALTIME_ENABLED` 可关闭后台 WS 连接。回归覆盖 mock tick、MarketCache 写入、provider 异常隔离、SSE realtime/cache payload、stale freshness 与前端 EventSource 更新/错误/卸载/无支持 fallback。

- 🧾 **Admin Logs 改为业务事件与调用链详情** — `/admin/logs` 默认从细碎运行日志切换为业务事件列表，股票分析只展示单条 `TSLA / analysis / 用户分析 TSLA` 级记录，并支持 symbol、状态、类别、时间范围与分页筛选。后端新增 analysis execution 聚合能力，在分析流程中记录获取行情、技术指标、新闻、AI 分析、保存记录等步骤的 provider、耗时、错误与 recordId；详情接口返回完整调用链，非关键数据源失败时整次分析可标记为 `partial`。原始 session/event 日志继续保留在高级调试视图。

- 🧯 **Admin Logs 降噪与级别筛选** — `/admin/logs` 默认改为只展示 `WARNING / ERROR / CRITICAL`，新增级别、分类、搜索、时间范围与调试日志开关，并在顶部展示 ERROR、WARNING、数据源失败、慢请求和最近严重错误摘要。后端 `/api/v1/admin/logs` 与 `/sessions` 补齐 `min_level / level / category / query / since / limit / offset / page / cursor` 查询参数，兼容 `minLevel / taskId`，并对 Market cache/prewarm 成功、普通 cache hit、普通快请求等高频 INFO/DEBUG 事件降噪；Market 数据源 timeout、refresh failed、fallback/stale 与慢请求继续入库并默认可见。

- 🧊 **Market Overview 接入后端 SWR 缓存** — `/api/v1/market/*` 新增统一轻量内存缓存层，按 crypto、futures、A股指数、商品外汇、资金流、情绪、利率等数据类型使用独立 TTL；缓存命中时不再重复访问外部源，过期时先返回最近快照并标记 `isRefreshing=true` 后台刷新，刷新失败保留旧快照并返回 warning。fallback/mock 数据继续保留 `freshness=fallback/mock` 与 item-level metadata，不会被缓存包装成 live。前端仅补齐 `isRefreshing` 类型和卡片 footer 的“正在刷新快照”提示，页面结构不变。

## 2026-04-29

- 🧭 **Market Overview 补齐数据可信度治理与真实A股指数源** — `/market-overview` 现为 market overview 相关 API 响应统一补充 `sourceLabel / asOf / freshness / isFallback / isStale / delayMinutes / warning` 元数据，fallback/mock 不再被包装成实时或公共行情。A股/港股指数卡优先接入新浪财经指数报价并保留 item-level metadata，真实源失败时仍返回稳定 fallback 且明确标注“备用示例数据，不代表当前行情”。前端新增 `DataFreshnessBadge`、卡片底部数据状态/来源/行情时间/更新时间展示和顶部数据质量总览，同时按交易员查看习惯调整分类内排序；回归覆盖 freshness helper、cn-indices mixed/fallback、temperature warning、badge 全状态、数据质量统计和分类排序。
- 🌡️ **Market Overview 新增市场温度计与解释型仪表盘** — `/market-overview` 在现有分类、卡片、刷新、轮询与拖拽排序体系内新增顶部“市场温度总览”和“今日市场解读”，提供综合市场温度、美股风险偏好、A股赚钱效应、全球宏观压力、流动性环境 5 个规则评分，以及不依赖 LLM 的动态解释/风险提示。后端新增 `/api/v1/market/temperature`、`/market-briefing`、`/futures`、`/cn-short-sentiment`，均提供稳定 fallback；前端新增期货与盘前风向、A股短线情绪卡片并接入全部/美股/A股港股/全球宏观分类。回归覆盖新增 API 合约、fallback、评分范围、解释 severity、页面分类显示、新接口失败隔离和单卡刷新保留旧数据。
- 🧭 **Market Overview 升级为分类式大盘总览** — `/market-overview` 在保留三列卡片、单卡刷新、60 秒轮询与拖拽排序的基础上新增 `全部 / 美股 / A股/港股 / 全球宏观 / 加密货币` 分类视图，并按分类使用独立 `localStorage` 排序 key。后端新增 `/api/v1/market/cn-indices`、`/cn-breadth`、`/cn-flows`、`/sector-rotation`、`/rates`、`/fx-commodities`，统一返回 `source / updatedAt / items`，外部源不可用时回退到最近快照或稳定 fallback 数据，避免单接口失败导致页面空白。前端同步补齐 A股与港股指数、市场宽度、资金流向、行业主题强弱、利率债券、商品外汇卡片和中英文文案；回归覆盖新增 API fallback 与 MarketOverview 分类/失败隔离/单卡刷新/排序持久化。
- 🚀 **Market Overview 新增加密行情与实时情绪快照** — `src/services/market_overview_service.py` 新增 Binance `BTC/ETH/BNB` 行情抓取、7D 趋势线与 `CNN -> Alternative.me` 情绪快照链路，并为 `/api/v1/market/crypto`、`/api/v1/market/sentiment` 加入最近一次成功数据回退。`api/v1/endpoints/market.py` 与 `api/v1/router.py` 暴露新接口；`apps/dsa-web/src/api/market.ts`、`apps/dsa-web/src/pages/MarketOverviewPage.tsx` 与新增 `CryptoCard.tsx` 把加密卡片接入现有 `/market-overview` 三列工作区，同时为情绪卡改用实时源、启用 60 秒自动轮询、卡片拖拽排序持久化与 hover 细节展示。回归覆盖新增到 `tests/api/test_market_crypto.py`、`tests/api/test_market_sentiment.py` 与 `apps/dsa-web/src/pages/__tests__/MarketOverviewPage.test.tsx`。
- 🧨 **Market Overview 斩首全局标题并下放局部刷新** — `apps/dsa-web/src/pages/MarketOverviewPage.tsx` 删除“大市全景监控”全局 Header、说明文案、最后更新时间和“同步最新行情”大按钮，同时去掉页面内部二次 `pt/px` 包装，让三列瀑布流直接顶到 Shell 基础内边距下方。`IndexTrendsCard.tsx`、`VolatilityCard.tsx`、`MarketSentimentCard.tsx`、`FundsFlowCard.tsx`、`MacroIndicatorsCard.tsx` 与共享 `MarketOverviewCard.tsx` 统一把同步状态标签替换为卡片标题行右侧的微型 `RefreshCcw` 纯图标按钮，并改为按卡片刷新对应 panel。

- 🧱 **Market Overview 改为三列瀑布流终局版** — `apps/dsa-web/src/pages/MarketOverviewPage.tsx` 废除主工作区二维 grid，改为左列指数、中列波动率/ETF、右列情绪/宏观的三条独立 flex 列，避免长指数卡把下方卡片整体推空。`marketOverviewPrimitives.tsx` 将数据行改为固定 `w-32` 名称列、固定 `w-24` Sparkline 列与右侧 `flex-1` 等宽数值列，移除指标单位后缀并过滤 `N/A` / 空值行；相关 Market Overview 卡片同步接入过滤逻辑，回归覆盖空宏观指标隐藏。

- 📉 **Market Overview 核心指标改为高密度垂直数据行** — `apps/dsa-web/src/components/market-overview/marketOverviewPrimitives.tsx` 新增共享 `MarketOverviewDataRow`，把指数、ETF 资金流和宏观指标从横向网格胶囊改为带状态点、压缩 Sparkline、右对齐等宽数值与涨跌摘要的纵向列表。`IndexTrendsCard.tsx`、`MarketOverviewCard.tsx` 与 `VolatilityCard.tsx` 同步移除指标级实心边框容器；波动率面板将 VIX、辅助波动指标与固定 `GREED / FEAR INDEX 65.0` 行合并到同一列表，避免 VIX 右侧出现物理空缺。配套回归更新到 `apps/dsa-web/src/pages/__tests__/MarketOverviewPage.test.tsx`，并通过 focused Vitest、lint、build 与 Safari `/market-overview` 手工验收。

- 🧾 **管理员日志补齐操作级系统事件与审计筛选** — `apps/dsa-web/src/pages/AdminLogsPage.tsx` 将 `/admin/logs` 的操作类别扩展到系统操作，支持按用户筛选并在前端兜底按操作时间倒序排列；详情抽屉现在可直接展示系统操作的操作类型、操作用户、操作时间、执行结果、失败原因，并兼容 `systemFallbacks` / `finalResult` 明细字段。配套类型与中英文文案同步更新到 `apps/dsa-web/src/api/adminLogs.ts`、`apps/dsa-web/src/i18n/core.ts`，回归覆盖补到 `apps/dsa-web/src/pages/__tests__/AdminLogsPage.test.tsx`。

- 🌐 **Market Overview 页面完成中文化、全局刷新与来源标注收口** — `apps/dsa-web/src/pages/MarketOverviewPage.tsx` 为市场总览页头补上 `同步最新行情` 幽灵按钮与动态 `最后更新` 时间戳，并把五个 panel 的并发拉取统一收束到同一刷新入口。`apps/dsa-web/src/i18n/core.ts` 新增 `marketOverviewPage` 中英文本地化文案，`IndexTrendsCard.tsx`、`VolatilityCard.tsx`、`MarketSentimentCard.tsx`、`FundsFlowCard.tsx`、`MacroIndicatorsCard.tsx` 与共享 `MarketOverviewCard.tsx` / `marketOverviewPrimitives.tsx` 全面移除硬编码英文状态词和底部 `Log:` 开发残留，改为低权重数据源声明与标准化更新时间展示。配套回归更新到 `apps/dsa-web/src/pages/__tests__/MarketOverviewPage.test.tsx`，并通过 `npm run test -- src/pages/__tests__/MarketOverviewPage.test.tsx`、`npm run lint`、`npm run build` 以及 Safari 登录后 `/market-overview` 手工验收。

- 📊 **Market Overview 终轮精装：纯暗背景、指数高密度、波动率光谱与情绪仪表盘** — `apps/dsa-web/src/pages/MarketOverviewPage.tsx` 与 shell route modifier 把 `market-overview` 路由背景彻底压回 `#030303`，继续剿灭页面与壳层残留的网格/坐标纸纹理。`apps/dsa-web/src/components/market-overview/IndexTrendsCard.tsx` 从共享卡片骨架中拆出，重排为三列高密度终端扫描结构：顶部身份行使用微型大写标签 + 纯文字涨跌复合摘要，主值放大到 `text-3xl font-bold font-mono`，Sparkline 压低到 `h-8`。`VolatilityCard.tsx` 也改成专用卡片，去掉叙述式说明，改为主 VIX 数值 + `Complacent -> Panic` 热力光谱条和 supporting metrics；`MarketSentimentCard.tsx` 新增半圆 Greed/Fear 仪表盘与三项黑话化情绪/仓位指标卡。共享格式与细线 Sparkline 逻辑下沉到 `marketOverviewPrimitives.tsx`，并补了对应页面回归断言。

- 🧾 **管理员日志统一展示单股分析、市场扫描与回测操作链路** — `/api/v1/admin/logs/sessions` 在保留既有 `execution_log_sessions` / `execution_log_events` 存储兼容性的基础上，补充标准化 `operation_*` 摘要与 `operation_detail` 明细视图，按 Single Stock Analysis、Market Scanning、Backtesting 归类目标、状态、关键指标、AI 调用、数据源/API 调用、fallback、错误诊断和时间线。`apps/dsa-web/src/pages/AdminLogsPage.tsx` 同步改为统一的可展开详情布局，列表直接展示时间、目标、操作类型、状态、关键指标与 `[View Details]`，详情区提供 AI 模型调用表、数据源/API 表、执行时间线、错误诊断以及完整日志复制/JSON 导出。

- 🎛️ **Market Overview 页面去网格、恢复滚动并拆除嵌套黑卡** — `apps/dsa-web/src/pages/MarketOverviewPage.tsx` 按 WolfyStock 工作区骨架重建页面容器：移除背景网格与绝对定位遮罩，外层改为 `w-full flex-1 flex flex-col min-w-0 min-h-0 pt-8 px-6 md:px-8 xl:px-12`，主内容区改为隐藏滚动条但可自然下滑的 `flex-1 overflow-y-auto ... pb-12`，修复底部内容被截断的问题。`apps/dsa-web/src/components/market-overview/MarketOverviewCard.tsx` 同步把各 panel 外层统一收敛到标准 `GlassCard` 材质 `bg-white/[0.02] border border-white/5 rounded-[24px] p-6`，删除指标级别的小黑底/边框卡片和 `YFINANCE` 来源废话标签，将数据重排为父卡片内部的高密度无框信息块，点位采用更聚焦的 `font-mono` 主数值，涨跌幅改为无底色文本，Sparkline 压低为细线走势，整体显著降噪并减少空间浪费。

- 📈 **WolfyStock 新增独立市场总览面板** — 新增 `/market-overview` 独立路由与 `GET /api/v1/market-overview/*` 后端接口，覆盖美股/A股主要指数、波动率、情绪、资金流和宏观指标五类卡片。后端通过短 TTL 缓存减少外部行情请求，并为每次面板刷新写入 `market_overview` 执行日志，管理员可在 `/admin/logs` 审计对应 panel、endpoint、时间戳、状态与原始响应摘要。前端新增 Gemini dark Bento 面板和 focused smoke 覆盖。

- 🧠 **WolfyStock 首页 AI 决断卡品牌化与投研化重构** — `apps/dsa-web` 的 Home Bento 决断卡将分析中原位 spinner 替换为旋转发光的 WolfyStock Logo，并把完成态报告统一回收到同一张投研决断卡：Ticker 旁强制展示公司全称与 Sector，Action / Score / Direction 升级为主视觉指标，AI Insight 压缩为单段技术结论，并对泛化“综合建议”话术自动降噪为均线、量价、RSI 驱动的专业判断。配套回归已更新到 `HomeSurfacePage.test.tsx`，并通过 focused Vitest、lint、build 与 in-app browser 首页手工验收。

- 🧭 **系统设置模型库与数据源库去卡片化** — `apps/dsa-web` 的 `/settings/system` 管理控制面将 Provider Library、Data Routing 与 Data Source Library 从多列 Bento 卡片墙改为高密度纵向数据行：左侧固定名称列与状态点，中部能力/状态微型标签，右侧收拢管理操作，并按 `LLM PROVIDERS`、`MARKET DATA`、`FUNDAMENTALS`、`NEWS & SENTIMENT` 等语义标题分组，降低海量配置项的扫描成本。配套回归已更新到 Settings 相关单测，并通过 lint、build、in-app browser DOM 检查与 Safari 实机视觉验证。

- 🧠 **WolfyStock 首页分析进度改为用户态五阶段动画** — `apps/dsa-web` 的 Home Bento 分析任务视图现在只展示总进度、`LLM / Technical / Fundamental / News / Sentiment` 五阶段状态，以及完成后的最终摘要卡（BUY / SELL / NEUTRAL、评分、目标位、止损位）。首页不再渲染模型名、数据源、`standard_report`、底层错误或 backend 调试文案；进度轮询失败时保持通用 `Analysis in progress` 等待态。后端同步新增安全的任务进度契约，避免队列 `TaskInfo` 无 `updated_at` 时让 `/progress` 崩溃。配套回归覆盖已补到 `HomeSurfacePage.test.tsx`、`tests/test_analysis_api_contract.py` 与 `tests/test_system_config_service.py`，并通过 WebKit / Chromium 进度流可见验证与 Safari 实机页面冒烟检查。

- 💬 **WolfyStock 问股空态继续压缩垂直浪费并移除底部叠高** — `apps/dsa-web/src/pages/ChatPage.tsx` 进一步收紧问股空态主视图：顶部灯泡图标不再单独占一行，而是与“先提一个具体问题”并到同一条 `flex items-center justify-center gap-3` 标题线上，避免顶部裁切并回收一整行高度。空态输入舱父级同时删掉额外的 `pb-8`/`mb-*` 叠加，只保留 `w-full mt-auto pt-4`，免责声明压到 `mt-2 mb-0`，让输入框在视觉上尽可能贴近组件允许的最底端而不再被额外 padding 垫高。配套回归已更新到 `ChatPage.test.tsx`，并重新通过本地测试、构建和 Safari 新标签页验收。

- 💬 **WolfyStock 问股主视图改为上下分层骨架，修复输入舱悬空与空态滚动链路** — `apps/dsa-web/src/pages/ChatPage.tsx` 的问股空态主视图不再依赖 `mt-auto` 试图“碰运气”沉底，而是改成严格的上下分层：`main` 根容器固定为 `flex-1 flex flex-col h-full overflow-hidden`，上半区使用独立的 `flex-1 overflow-y-auto flex flex-col items-center justify-center pb-10` 承载标题、三张入口卡和快捷标签，下半区使用 `flex-none w-full pb-8 pt-4` 固定悬浮输入舱，从结构上消除输入框被顶到半空和细微高度溢出引发全局滚动条的问题。三张入口卡片内部也同步改成 `px-8 py-6`、`flex flex-col items-center justify-center text-center` 和 `gap-3` 的终端排版，避免文字贴边。配套回归已更新到 `ChatPage.test.tsx`，并重新通过本地测试、构建和 Safari 新标签页验收。

- 💬 **WolfyStock 问股主视图二次收口，重心下沉并去胶囊卡片** — `apps/dsa-web/src/pages/ChatPage.tsx` 继续收紧问股空态主视图：主面板补成 `flex flex-col h-full`，悬浮输入舱父级加上 `mt-auto` 语义并把底部间距下沉到 `mb-8`，让输入框更贴近页面底缘而不再漂浮在中段；标题、卡片和快捷标签之间的垂直节奏同步拉大到更疏朗的 `gap-12`。三张预设入口卡片也彻底废除偏胶囊的旧材质，统一回到标准 `GlassCard` 终端材质 `bg-white/[0.02] border border-white/5 rounded-2xl p-6`，并按三列等高网格对齐。输入舱外框进一步降噪为 `border-white/[0.05]`，背景微提亮到 `bg-white/[0.04] backdrop-blur-2xl shadow-2xl`，免责声明继续保持极低对比度居中放在输入框正下方。配套回归已更新到 `ChatPage.test.tsx`，并重新走本地测试与浏览器验收。

- 💬 **WolfyStock 问股主视图去廉价对话感重构** — `apps/dsa-web/src/pages/ChatPage.tsx` 的空态主视图现在改为居中玻璃陈列：三张研究入口卡片与快捷问题标签统一收口到中轴，快捷标签使用更轻的药丸玻璃材质并强制 `justify-center` 对齐，不再出现整体左偏和文字重心漂移。底部输入区同步移除旧的厚重外壳，改为独立悬浮的 Gemini 风格输入舱：placeholder 内嵌到 textarea，发送按钮内置到右下角，输入前后状态对比更清晰，底部只保留一行低对比度免责声明，主视觉区与输入舱之间也补足了安全留白。配套回归已更新到 `ChatPage.test.tsx`，并通过 Safari 新标签页在 `http://127.0.0.1:4175/chat` 做了手工验证。

## 2026-04-28

- 🧭 **WolfyStock 全局页面间距统一到 Portfolio 标准** — `apps/dsa-web` 现在把持仓页原本最舒适的页面 gutter（`pt-6 px-6 md:px-8 xl:px-12 pb-12`）上移到共享 `Shell` 的 `<main>`，Home / Guest / Portfolio / Backtest / Scanner / Chat / Settings / Admin Logs 等页面根节点不再各自重复外层 padding 或滚动 gutter，切换路由时内容左边缘与上边缘保持同一套坐标。同步清理了 Backtest 旧的 frame padding override 与 `theme-main-lane` 私有左缩进，并为 Safari readiness 增加 rAF 兜底超时，避免真实 Safari 偶发停在透明态。配套回归覆盖已更新到对应页面测试与 `Shell.test.tsx`，并通过 WebKit 几何验证确认 Home / Portfolio / Backtest / Scanner / Chat 在 1440px 视口下根内容边界一致。
- 🧠 **WolfyStock 首页异步分析卡片清除假数据与待确认态** — `apps/dsa-web` 的 Home Bento 决策/策略/技术/基本面卡片现在始终保留原位渲染，缺失、失败或僵尸历史报告只显示 `-` / `N/A`，不再用 ORCL/NVDA/TSLA 本地预设、骨架屏或 `待确认股票` 把失败 LLM 结果伪装成真实分析。手动点击分析会清空输入框并保持卡片在位；LLM 请求失败统一提示“LLM 分析失败，请稍后重试”，成功任务结果仍会在原卡片中覆盖占位值。`stockPoolStore.ts` 同步拒绝缓存带失败文本或待确认股票名的任务快照，避免本地 snapshot 回灌假数据。配套回归覆盖已补到 `HomeSurfacePage.test.tsx` 与 `stockPoolStore.test.ts`，并通过 in-app browser 验证了首页卡片可见、缺失字段中性显示、输入清空与异步结果原位更新。
- 🧮 **Portfolio 左侧面板改成无界分段控制与实时汇率引擎** — `apps/dsa-web/src/pages/PortfolioPage.tsx` 不再复用共享 `SegmentedControl` 的按钮胶囊结构，而是在 Portfolio 局部用单一 `bg-white/[0.05]` 深槽承载 `交易 / 账户 / 同步 / 汇率`、`股票买卖 / 资金划转 / 公司行为` 与历史流水切换，未选中项保持透明、选中项只用极弱 `bg-white/10` 浮层表达。汇率 tab 同步改为 `LIVE EXCHANGE ENGINE` 查询面板，提供 Base / Quote Currency 下拉选择、单行高亮汇率读数与白底黑字 `获取实时汇率 (Fetch Live Rate)` 入口，继续复用既有 `refreshFx` 数据刷新链路；左侧滚动容器补齐隐藏滚动条类，内容过长时保持可滚动但不显示原生滚动条。
- 🧮 **Portfolio 汇率黑箱拆开并清理幽灵线框** — `api/v1/portfolio/snapshot` 现在随快照返回当前 scope 实际参与估值/聚合的缓存汇率明细，`PortfolioPage.tsx` 在左侧 Trade Station 增加“汇率”分段页，集中展示 `USD/CNY`、`HKD/CNY` 等汇率、最后更新时间与刷新入口；原左栏和历史分页的 segmented controls 同步改成无边框深槽样式，并为 Portfolio 局部滚动容器补齐隐藏滚动条类，保留滚动能力但不再显示系统原生滚动条。
- 🧭 **Portfolio 持仓管理页按 WolfyStock 视觉宪法重构表单与三栏材质** — `apps/dsa-web/src/pages/PortfolioPage.tsx` 将持仓管理工作台收口为标准三列 `3 / 5 / 4` GlassCard 网格，统一使用 `bg-white/[0.02] border-white/5 rounded-[24px] p-6` 材质；交易/账户/同步和交易类型切换改为深槽 segmented control；交易、资金、公司行为、建账与 IBKR 同步表单统一补齐微型大写字段标签，并移除把字段说明塞进 placeholder 的胶囊输入风格。核心提交按钮改为高对比白底黑字 `h-12 rounded-2xl font-bold` CTA，刷新动作收敛为图标按钮，历史记录删除动作收敛为低权重垃圾桶图标，同时把移动窄视口从截断式等高面板改回自然纵向展开。本次改动只调整 Portfolio 前端表现与共享 Input/Select 的 label class 扩展，不改变 portfolio API、鉴权、账户选择、同步或删除数据流。
- 🗑️ **WolfyStock 首页历史全删链路与空态回放修复** — `api/v1/history` 新增 `delete_all` 语义，首页历史抽屉的 `Delete all` 不再只删当前可见 ID，而是会按当前用户 owner scope 清空数据库里的全部分析历史，并同步清理关联回测结果。`stockPoolStore.ts` 在删除成功后会主动清空 `selectedReport`、history snapshot cache、highlighted selection 和持久化选中项，`HomeBentoDashboardPage.tsx` 也改成在零历史时强制回到 ghost dashboard，不再保留残余 ticker、旧报告或零状态快捷股票按钮；同时手动输入股票代码后，如果数据库里还没有真实历史/真实返回，首页只会进入 loading/ghost 状态，不会再立刻用 ORCL/NVDA/TSLA 本地预设冒充分析结果。后端 `HistoryService` 同时补了历史列表/详情的占位股票名清洗，避免新记录继续显示 `待确认股票 (TSLA)` 这类假文案。配套回归覆盖已补到 `tests/test_analysis_history.py`、`HomeSurfacePage.test.tsx` 与 `stockPoolStore.test.ts`，并通过 in-app browser 手工验证了“删空 -> 刷新仍空 -> 手动输入 ORCL 不再秒出假报告 -> 新 TSLA 分析出现 -> 已删旧记录不复活”的完整路径。
- 🧹 **WolfyStock 首页清剿僵尸缓存并加入 ticker 预校验** — `apps/dsa-web` 的 Home Bento 首页不再把历史报告快照持久化到 `localStorage`；`stockPoolStore.ts` 改为仅保留会话内 snapshot bridge，并在挂载时主动清除旧的 `history / recentHistory / cachedHistory / dsa-history-report-snapshots-v1` 冗余缓存，避免“待确认股票”之类残留状态污染零状态。首页分析入口 `HomeBentoDashboardPage.tsx` 现在也改成严格的股票代码业务流：先做 `^[A-Z]{1,5}$|^\d{6}$` 格式校验，再调用新增的 `GET /api/v1/stocks/{stock_code}/validate` 做真实性预校验，只有校验通过才提交异步分析。后端同时补了 `StockService.validate_ticker_exists()` 与对应 schema/endpoint，配套回归覆盖已补到 `HomeSurfacePage.test.tsx`、`stockPoolStore.test.ts` 与新的 `tests/test_stock_service_validation.py`。
- 🧭 **Safari 交互加固与 Backtest 专业模板提示收口** — `apps/dsa-web` 为 Home / Chat / Scanner / Portfolio / Backtest 几个 WolfyStock 主工作面补了一层共享 Safari readiness/warmup 机制：首帧通过轻量延迟挂载、强制 repaint、关键按钮 warm binding、`pointer-events-auto` 与渐进 opacity 过渡来降低真实 Safari 上偶发黑屏和首击丢失的概率；共用 `Drawer`、`Button` 和 Home Bento action button 也同步做了交互稳定化。与此同时，Backtest 专业模式的完整模板目录继续保留全部内置模板，但对 `executable=false` 条目改成可点击的“载入参考模板”路径，点击后会明确提示“当前模板暂不支持直接运行，请在编辑器中修改后再执行”，而可执行模板仍保持正常载入。配套回归已补到 `BacktestPage.test.tsx`，并重跑了 `ChatPage / UserScannerPage / PortfolioPage / HomeSurfacePage / BacktestPage` 聚焦测试、`npm run build`，以及新的 `reports/ux-verification-safari-fix/` WebKit/Chromium UX 验证产物。
- 🗑️ **Home 历史抽屉补齐前端删除闭环** — `apps/dsa-web` 的首页历史抽屉现在除了继续显示北京时间、公司名与 canonical report 回放外，还补上了用户可见的删除入口：抽屉头部新增“全部删除”，每条历史记录右侧新增单条“删除记录”动作，二者都统一走已有 `DELETE /api/v1/history` 接口并通过确认弹窗防止误删。实现上继续复用现有 store 删除状态与 owner 边界，不改分析执行、report 生成或 snapshot 过渡语义；配套回归已补到 `HomeSurfacePage.test.tsx` 与 `stockPoolStore.test.ts`。
- 🕘 **WolfyStock 历史记录统一切到北京时间并清洗测试数据入口** — `analysis/history` 链路现在会把 canonical report 的 `meta.generated_at` 与 `meta.report_generated_at` 统一规范成北京时间 `UTC+8`，同时在历史元数据中补齐 `company_name` 与 `is_test`。`HomeBentoDashboardPage.tsx` 的历史抽屉改为显示“公司名 (股票代码)”并过滤 `is_test=true` 记录，点击历史项仍始终通过 `GET /api/v1/history/:id` 回放数据库 canonical report，本地 snapshot 只保留为过渡态。后端同时新增 `scripts/clean_test_history.py` 用于按 `is_test` 与时间范围清理测试/临时历史记录，`scripts/seed_canonical_history_browser_check.py` 也改为显式写入测试标记。
- 🛠️ **WolfyStock Chat / Scanner / Backtest UX 闭环修复** — `apps/dsa-web` 与 `api/v1/endpoints/backtest.py` 针对本地 UX 验证里暴露的三条断点做了严格限域修复：问股在 Gemini 429 / timeout 时不再把原始 quota trace 暴露到页面，而是统一落成“当前响应超时，请稍后刷新”，并在历史会话回放时继续做显示层归一；Scanner 全量验证脚本改为优先探测可写入的市场/profile 组合，在 CN 配置返回 `400 validation_error` 时自动回退到可执行的 US 配置，保证 `market_scanner_runs` 写库链路不断；`/api/v1/backtest/performance` 补齐了普通评估 summary、deterministic `rule_backtest_runs` 聚合 fallback 与空态 payload，避免前端 overview 因 404 中断。配套回归覆盖已补到 `tests/test_backtest_api_contract.py`、`ChatPage.test.tsx`、`agentChatStore.test.ts`、`ux-verification-helpers.test.mjs`，并重跑了 `run-full-ux-verification.mjs` 与 in-app browser 手工验收。
- 🧠 **首页历史记录恢复误判修复 + analysis detail 持久化补齐** — `HomeBentoDashboardPage.tsx` 现在不会再因为 `raw_result/context_snapshot` 里的模型 fallback 诊断文本（例如某次 Gemini 503 / high-demand 尝试失败）就把整份成功保存的历史报告误判为“不可信”并清空成 `- / N/A` 占位；历史恢复同时补强了 `one_sentence` 优先级、`RSI14 / 多头/空头排列 / 量价判断 / MACD` 等技术字段映射与 `raw_result` 兜底。后端 `AnalysisService._build_report_payload()` 以及 history detail schema/API 也同步补入 `details.analysis_result` 与 `details.raw_ai_response`，把 decision/action、score/confidence、entry/stop/target、technical/MA/RSI/MACD/volume、full_reasoning 等结构化字段稳定写入和返回。配套回归已补到 `tests/test_analysis_api_contract.py` 与 `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx`，并通过本地 `127.0.0.1:5173` 登录后真实点击 `record_id=6` 验证首页主分析区恢复为真实历史内容，而不再退回默认占位。

- 🧾 **Home 历史抽屉改为 DB canonical report 真源，并补齐持久化 `generated_at` 契约** — 后端 `analysis/history` 链路现在会在分析成功后把 canonical report 完整写回 `analysis_history.raw_result.persisted_report`，并补齐 `meta.id`、`meta.generated_at`、`meta.report_generated_at`、`meta.strategy_type` 与 `summary.strategy_summary`；`HistoryService` 的历史列表同时开始返回每条记录的 `generated_at`，前端 `HomeBentoDashboardPage.tsx` 的历史抽屉会直接展示该时间戳，并在点击历史项时始终重新调用 `GET /api/v1/history/:id` 取数据库中的 canonical report，仅把本地 snapshot 当作过渡态，不再允许它覆盖数据库真值。配套回归已补到 `tests/test_analysis_api_contract.py`、`tests/test_analysis_history.py` 与 `apps/dsa-web/src/pages/__tests__/HomeSurfacePage.test.tsx`，并通过独立 `127.0.0.1:8001 + 127.0.0.1:5174` 浏览器验证环境确认 `record_id=153` 的 `generated_at` 与 canonical 文案能在 history drawer 与首页主面板中正确写透和回放。

## 2026-04-27

- 🧠 **Home 首页改为快照驱动的历史回看，并重写 AI 失败兜底语义** — `apps/dsa-web` 的首页历史抽屉不再依赖点击时重新取远端详情来驱动主面板，而是在 `stockPoolStore` 中把已加载/任务回传的完整 `AnalysisReport` 作为快照按股票代码持久化到本地状态与 `localStorage`，随后优先通过快照直接切换首页视图，避免“查看历史”与“触发分析”混在一起。与此同时，`HomeBentoDashboardPage.tsx` 重写了技术/基本面 fallback headline 的专业金融术语映射，特别是 `MA5 / MA10 / MA20 / MA60` 不再复用同一句占位文案，而是分别输出短线动能、十日趋势支撑、中期多头排列、长线牛熊分界等不同语义；当用户主动点击“分析”而 AI 引擎不可用时，页面右上角会显式弹出红色 toast“AI 引擎服务暂不可用，已为您加载本地回溯数据”，同时决断卡片切换为友好的本地回溯提示，不再暴露底层错误代码。配套回归覆盖已补到 `HomeSurfacePage.test.tsx` 与 `stockPoolStore.test.ts`。
- 🧠 **Home 首页恢复 AI 语义卡片并精修专业 K 线表现** — `apps/dsa-web` 的首页右侧 `技术形态 / 基本面画像` 卡片不再把 `MA5`、`MA10`、`RSI14`、`总市值(最新值)` 这类原始字段值直接堆到主卡片里，而是统一通过 `HomeBentoDashboardPage.tsx` 的 payload enrichment 层转成结论型 AI 文案，同时保留原始值给下钻细节使用，避免首页主视图再次退化成数据表。缺失基本面字段现在会稳定清洗为 `-`，不再显示 `NA（字段待接入）` / `N/A (field pending)`。配套地，`HomeSignalCandlestickChart.tsx` 统一收口为更专业的暗色系 K 线配色、较小的 `pin` 突破锚点，以及更高密度的 mock/preset K 线与成交量数据，让首页迷你图重新具备连续性和交易感。回归覆盖已补到 `HomeSurfacePage.test.tsx`，并通过本地 build 与浏览器手工验证确认首页主卡片恢复 AI 语义表达。
- 📈 **Home 首页升级为带信号迷你 K 线并清洗英文动态数据** — `apps/dsa-web` 的首页左侧 `DecisionCard` 现在用新的 `HomeSignalCandlestickChart` 取代原先手写平滑折线，统一接入迷你 candlestick + volume 结构，并新增 `日K / 分时 / 周K` 与 `5D / 1D / 1M` 周期切换；底部“最近报告归因 / Latest Report Context”同步压缩成紧凑单行上下文，释放图表高度。`HomeBentoDashboardPage.tsx` 还新增了一层首页专用的报表字段净化逻辑，在英文环境下把历史报表里的中文标签、括号注释、数值单位与长段叙事转换为英文或安全回退，避免 `172.92-178.04（回踩支撑确认）`、`总市值(最新值)`、`待确认股票` 这类混排继续出现在首页卡片中。配套回归测试已补到 `HomeSurfacePage.test.tsx`，覆盖时间窗切换文案与英文环境下的报表字段清洗。
- 🧭 **Home 首页下钻抽屉改为与主卡片同源并清除占位叙事** — `apps/dsa-web` 对首页 `HomeBentoDashboardPage` 的详情抽屉做了一次严格限域的数据流修复：抽屉不再读取独立静态 `drawers` 占位 payload，而是只保留当前打开的 section key，并在渲染时从当前 `dashboardData` 派生 `Decision / Strategy / Technical / Fundamental` drill-down 内容，确保主卡片与下钻面板共享同一份活动 ticker 数据对象。`DeepReportDrawer` 现在展示的是 `value + supporting details` 结构，TSLA 等标的的技术与基本面细节会直接围绕当前主结论生成，原先那批设计期占位废话不再进入渲染路径。配套回归测试已补到 `HomeSurfacePage.test.tsx`，覆盖 recent-history 切换和 TSLA 下钻一致性。此次改动不调整分析 API、鉴权协议或其他页面信息架构，只修复首页主面板与详情抽屉的数据一致性和文案纯度。
- 🧭 **Home 首页抗闪烁状态机、联合搜索栏与演示数据降级收口** — `apps/dsa-web` 对首页决策台做了一次严格限域的交互修复：搜索框不再绑定全局 query，而是改为独立 `searchQuery` 状态，并在触发分析后立即清空，保持恒定的待输入姿态；历史入口从独立右侧占位行收回到搜索/分析控制条内，首页整体网格也被重写为左侧控制区 + 决断主卡、右侧策略/技术/基本面数据栈直接顶格开始，消除右栏顶部空耗。与此同时，首页新增本地 `isDashboardLoading` 强加载态，切换历史记录或发起分析时不再让旧卡片残留闪烁，而是先显示骨架屏；分析请求失败时也不再落回粗糙的未知 ticker 壳层，而是切换到预设演示数据并抛出轻提示 toast。此次改动不调整分析 API、任务协议或鉴权逻辑，只修复首页状态跳变、输入绑定和失败降级体验。
- 🧊 **Home 首页操作岛、搜索玻璃态与非对称 Bento 主布局收口** — `apps/dsa-web` 对首页与共享头部做了一次严格限域的视觉结构修复：`SidebarNav.tsx` 现在把顶部右侧的语言、设置、控制台与退出统一收纳进单一毛玻璃操作岛，弱化原先分散文字链的突兀感；`HomeBentoDashboardPage.tsx` 的搜索输入框、分析按钮与历史入口同步切到与下方卡片同源的低透明玻璃材质、`rounded-2xl` 圆角与统一高度；首页主体则不再维持四张标准卡片平铺，而是明确改为左侧 `AI Decision` 独占两列、右侧 `Strategy + Tech/Fundamentals` 三列堆叠的非对称 2/3 Bento 结构。配套回归测试已补到 `HomeSurfacePage.test.tsx` 与 `Shell.test.tsx`，此次改动不调整分析 API、鉴权协议、历史数据链路或其他页面信息架构，只修复首页材质一致性、顶部收纳感与首屏卡片对齐。
- 🧭 **Home 首页历史入口抽屉化、最近 ticker 状态恢复与英文排版/图表留白修正** — `apps/dsa-web` 对首页决策台做了一次严格限域的可用性精修：顶部不再平铺最近分析胶囊，而是收口为单一“历史记录”按钮并复用系统 `Drawer` 展示历史列表，点击后会加载对应 ticker 并自动收起抽屉；首页初始化时也不再写死 `NVDA`，而是优先从最近历史栈顶恢复上一次分析标的，避免页面切换后状态丢失。与此同时，`DecisionCard` 的走势图改成带独立 Y 轴/X 轴标签槽位的安全边距布局，避免英文坐标标签挤压折线区域；`StrategyCard`、`TechCard`、`FundamentalsCard` 与 `BentoCard` 统一补上 `min-w-0`、`truncate`、`break-words`、更松的 `leading-[1.7]` 段落节奏，专门修复英文长词、长数值和长段落在首页卡片中的溢出与拥挤问题。此次改动不调整分析 API、历史接口或鉴权逻辑，只修复首页历史入口、状态记忆和多语言排版表现。
- 🧭 **Guest 登录回流首页并把 Home 顶部控制台强制纳入单一 5 列网格** — `apps/dsa-web` 对 guest/auth 与 Home 首页做了一次严格限域的 P0 修复：`GuestHomePage` 现在在登录态建立后会自动跳回首页工作台，`App.tsx` 也同步把已登录访问 `/guest` / `/:locale/guest` 的路由入口收口为直接重定向到首页，避免登录后留在游客漏斗页；与此同时，`HomeBentoDashboardPage` 的搜索栏与最近分析历史被强制折叠回 `main` 下唯一的 5 列主网格，搜索区改为 `h-12`，不再通过额外网格包装器或脱离网格的顶栏破坏与下方 AI 决断双列卡片的对齐。此次改动不调整分析 API、鉴权协议或数据结构，只修复 guest 登录回流和首页主网格层级错误。
- 🧩 **Home 决策台强制回归 5 列首屏网格并压缩动态数据字号** — `apps/dsa-web` 对 `HomeBentoDashboardPage` 与 Home Bento 卡片做了一次严格限域的首页修复：搜索框与最近分析历史现在被强制放回同一个 5 列主网格首行，顶部不再脱离下方卡片网格单独漂浮；动态报告落入首页后，`甲骨文 (ORCL)` 这类标题被收口到 `text-lg`，建仓区间、总市值等长字符串指标统一压到 `text-lg font-bold` / `text-base font-bold`，说明段落统一切到 `text-[13px] leading-relaxed`，避免真实数据把卡片高度和阅读节奏撑爆；同时保留现有四张标准 Bento 卡片结构，不再额外渲染破坏一屏流的底部补丁卡片。此次改动不调整分析 API、历史查询或鉴权逻辑，只修复首页网格对齐与高密度排版失控问题。
- 🧭 **回测 `/backtest` 消除双层滚动并强制回归 WolfyStock 玻璃态规范** — `apps/dsa-web` 对回测页做了一次严格限域的交互/视觉纠偏：`ProBacktestWorkspace` 与 `DeterministicBacktestFlow` 移除了专业模式右侧 `max-h` / `overflow-y-auto` 这类内部滚动限制，改为依赖页面全局单层滚动，并让左侧能力树以 `sticky top-6` 常驻；普通模式的紫色渐变 CTA 被替换为高对比白底按钮，普通/专业表单输入、标签与配置卡片统一收口到 WolfyStock 深空玻璃 token；顶部 `普通 / 专业` 与 `确定性回测 / 历史评估` toggle 也同步改成与扫描器市场切换一致的深槽胶囊风格。此次改动不触碰回测 API、策略解析、结果路由或鉴权逻辑，只修复 `/backtest` 的嵌套滚动体验和材质语言偏航问题。
- 🧭 **Home 决策台激活动态 ticker、历史回溯与导航右侧文字链** — `apps/dsa-web` 的 Home / shared nav 这一轮不再停留在静态占位：`SidebarNav.tsx` 将 header 右侧的语言、设置、控制台、登出从胶囊按钮样式收口回纯文本 utility link；`HomeBentoDashboardPage.tsx` 把搜索框、分析按钮与最近分析 history pills 直接并入首页现有 5 列 Bento grid 首行，保证它与下方 `AI Decision` 双列卡片做严格网格对齐；首页同时引入 `activeTicker + dashboardData` 状态，并在搜索、最近分析点击与历史报告命中时切换整张仪表盘的数据源，不再固定写死 NVDA。历史回溯优先消费现有 `historyApi` / `stockPoolStore` 的最近报告；没有历史命中时则退回本地动态预设，保持页面即时反馈。此次改动不调整分析 API、鉴权模型或后台任务链路，只修复首页信息流与导航呈现。
- 🧭 **导航栏去按钮化、首页搜索归位、扫描器右侧滚动权恢复** — `apps/dsa-web` 这轮对 Home / Scanner 做了一次严格纠偏：顶部导航移除了误塞进 Header 的全局 Omnibar，`首页 / 扫描器 / 问股 / 持仓 / 回测` 回到纯文本极简链接，不再使用胶囊背景、边框和药丸样式；首页分析入口重新回到 `HomeBentoDashboardPage` 内部，在 Bento 主网格正上方恢复为独立一行的轻玻璃搜索栏，继续复用已有 `submitAnalysis` 行为；`UserScannerPage` 则把滚动权从卡片网格内部移交回右侧结果区容器本身，通过 `min-h-0 + overflow-y-auto + no-scrollbar` 恢复真实的纵向浏览能力，避免外层 flex/高度链路再次掐死滚动。此次改动不调整分析 API、路由权限或扫描业务逻辑，只纠正导航入口归属、首页搜索位置和扫描器滚动容器层级。
- 🔎 **全局 Omnibar 复活，并废除 Home / Scanner 的暴力截断链路** — `apps/dsa-web` 将已登录桌面壳层的顶部导航升级为真正的全局 Omnibar：分析入口不再只挂在首页局部 Hero 中，而是固定出现在 masthead 中部，支持随时输入代码或公司名发起分析；与此同时，`Shell`、`HomeBentoDashboardPage` 与 `UserScannerPage` 这轮停止依赖 `overflow-hidden / h-screen / scanner shell clip` 来伪造“一屏看全”，首页与扫描器重新允许页面自然向下延展。为把首屏压回合理高度，Home Bento 的卡片 padding、网格 gap、技术/基本面卡片节奏与决策图表容器都同步收紧，图表改为 `flex-1 + min-height` 的弹性结构，避免右侧数据栈或外层等高拉伸制造空白背景。此次改动不调整后端分析接口、scanner API 或权限边界，只修复全局分析入口回退与首页/扫描器的滚动截断问题。
- 🌌 **WolfyStock 视觉宪法第二、三阶段落地到核心工作区页面** — `apps/dsa-web` 继续按 `docs/architecture/wolfystock-frontend-visual-constitution-audit.md` 推进页面级收敛：`/chat` 去掉了消息流与底部控制台的居中 `max-w` 囚笼，改成真正跟随 `px-6 md:px-8 xl:px-12` 安全边距展开的三栏研究台；`/portfolio` 移除了 `max-w-[1920px]` 外层容器，并把交易/资金/公司行为、建账、IBKR 只读同步等主 CTA 统一切到高对比白底按钮；`/scanner` 则移除了 `mx-auto + max-w-[1920px]` 壳层，把运行按钮和命中徽标从装饰性绿色收回到白/indigo 体系，同时保留盈亏语义才继续使用绿色。`/settings/system`、`/admin/logs`、个人设置及共享 `Drawer / WorkspacePageHeader` 也同步切到更克制的深空玻璃材质、24px 级圆角、紧凑标题与非绿色 toggle/segment 语义。此次改动不改后端接口、路由权限和业务流程，只继续修正核心工作区的宽屏利用率、材质统一性与语义颜色纪律。
- 🧭 **WolfyStock 视觉宪法第一阶段落地到共享壳层** — `apps/dsa-web` 对共享 `Layout/Nav` 做了一次严格限域收敛：`Shell`、`PreviewShell`、`SidebarNav` 与 `index.css` 现在统一改成真正的 edge-to-edge 外层壳层，去掉共享 masthead / route frame 的居中限宽，统一只保留安全边距；顶部导航、移动抽屉、预览壳层与确认对话框同步切到更克制的深色玻璃材质、边框提亮式 hover/active 反馈和中性 CTA 色，移除旧的 SpaceX 式霓虹渐变品牌强调。配套新增 `docs/architecture/wolfystock-frontend-visual-constitution-audit.md`，把仍待处理的页面级 `mx-auto / max-w-* / 绿色误用 / 过大字号` 违宪点分阶段列清，后续页面收敛将按这份审计计划继续推进。
- ✨ **问股 `/chat` 补齐 Glassmorphism 材质并精装控制台细节** — `apps/dsa-web/src/pages/ChatPage.tsx` 继续对问股页做严格限域视觉收口：底部输入区从偏沉的纯色盒子升级为带 `backdrop-blur-3xl`、细边框、hover/focus 发光反馈的 Glass Command Center，风险提示语也内嵌回输入容器底部操作带；右侧“分析引擎与视角”改成带左分隔线和渐变背景的独立 Bento 侧栏，标题增加霓虹状态点，策略胶囊统一切到更清晰的 active/inactive 材质体系；User 消息气泡同步升级为带轻毛玻璃、边框与阴影的高密度对话气泡。此次改动不调整消息流、技能语义或接口行为，只修复 `/chat` 与主站 Glassmorphism 材质语言不对齐的问题。
- 💬 **问股 `/chat` 拆成高密度三栏工作台并把技能控制彻底右移** — `apps/dsa-web/src/pages/ChatPage.tsx` 将问股页从单列堆叠改成真正的工作台骨架：保留左侧历史对话栏，中间区域重写为独立聊天画布，右侧新增固定宽度的策略/技能控制台；原本堆在输入框上方的“通用分析 / 缠论 / 箱体震荡”等胶囊按钮已整体迁入右栏，不再挤压底部输入区。聊天滚动容器继续只负责消息流本身，内部消息画布收口到 `max-w-4xl`，并把底部安全留白改为 `pb-48`，确保最后一行回复稳定停在吸底输入框之上。与此同时，assistant Markdown 阅读节奏被强制压缩到 `text-[15px] / leading-[1.6]`，段落与列表间距同步收紧，解决此前回答文本过松、信息密度过低的问题。此次改动不调整 agent API、会话历史持久化或跟随上下文逻辑，只重构 `/chat` 的前端工作区结构与阅读密度。
- 📐 **回测 `/backtest` 破除居中限宽并重构为真通栏工作台** — `apps/dsa-web` 对回测配置页做了一次严格限域的布局骨架修复：移除 `/backtest` 路由壳层的额外横向 padding，回测页不再依赖共享 `PageChrome` 的居中 header 容器；顶部标题区改为独立全宽 section，二级导航栏（确定性回测 / 历史评估、Normal / Professional）下沉为独立 `w-full` 通栏，主体工作区统一切换到 `px-6 xl:px-10` 的全宽画布；同时把确定性回测 cockpit 的内层 `px-* / mt-* / mb-*` 收口删除，确保左侧控制台与右侧配置台真正跟随窗口横向展开。此次改动不触碰回测 API、策略解析、结果路由或历史数据逻辑，只修复 `/backtest` 的父级限宽囚笼与桌面工作区铺开问题。
- 💬 **问股 Chat 强制重排为“滚动画布 / 悬浮输入”物理分层** — `apps/dsa-web/src/pages/ChatPage.tsx` 对 `/chat` 的右侧主工作区执行了一次结构级修复：新增独立的 `chat-main-shell` 作为唯一定位上下文，顶部标题操作区、滚动画布层与底部悬浮输入层不再混在同一个滚动/定位系统里；`main#chat-scroll-container` 现在只负责消息与欢迎卡片滚动，底部输入控制台改为它的绝对定位兄弟节点，并通过新的渐变遮罩层承接策略胶囊、Textarea 与发送按钮；消息画布继续保留 `pb-56` 安全留白，避免最后一行文字被吸底输入层遮挡。此次改动不调整 agent API、会话历史或技能逻辑，只修复 `/chat` 的 DOM 层级错乱、吸底失效和底部遮挡问题。

## 2026-04-26

- 💬 **问股 Chat 彻底释放宽度并修复历史流式/滚动抖动** — `apps/dsa-web/src/pages/ChatPage.tsx` 与 `src/components/common/TypewriterText.tsx` 对 `/chat` 做了严格限域热修复：主消息流与底部控制台统一收口到更宽的 `max-w-5xl` 画布，底部策略胶囊栏改为可横向滑动且禁止 pill 被压缩截断；assistant 历史消息现在只做静态 Markdown 渲染，只有“最后一条 assistant 且当前仍在生成”的消息才使用打字机效果，避免切会话或刷新后历史消息重复打字；滚动跟随也从 `scrollIntoView({ behavior: "smooth" })` 改为直接锚定 `#chat-scroll-container.scrollTop`，消除流式输出期间的明显卡顿。此次改动不调整 agent API、会话持久化或技能语义，只修复问股页的宽度、历史恢复和滚动手感。
- 📈 **回测结果页重组为高密度研报式布局** — `apps/dsa-web` 对 `/backtest/results/:id` 做了严格限域的前端重构：顶部把运行状态、区间与核心 KPI 收口为单一的 Bento 概览带，避免原先状态卡、配置卡和 KPI 卡在首屏分散占位；中部三图联动继续保持全宽，但改为放入带玻璃边框与深色绘图板质感的 chart shell；“参数与假设”标签页顶部新增 6 列终端式参数矩阵，把关键运行参数压缩到高密度 key-value grid；概览标签页里的 Markdown 决策摘要改为带固定高度、内部滚动和“复制完整报告”按钮的控制台容器。此次调整不改变回测 API、鉴权、比较工作台、执行轨迹导出或策略解析逻辑，只重构结果页的信息层级与视觉密度。
- 🪪 **站点品牌标识与加载页切换到新 WolfyStock Logo** — `apps/dsa-web` 将站内品牌资源从旧标识替换为新的 WolfyStock 发光双彩 logo：标签页 favicon、导航品牌区与启动加载壳层现在统一引用透明底原稿资源，并把预启动 fallback 与 React `BrandedLoadingScreen` 一并收口到同一套品牌语言。加载页不再只是静态文字等待，而是改成“品牌标记 + 市场轨迹线 + 进度条”的专业交易终端风格启动动画。此次改动仅涉及 Web 前端品牌展示与启动体验，不改变路由、鉴权或业务数据逻辑。
- 💬 **问股 Chat 收口为高密度阅读 + 智能跟随流式交互** — `apps/dsa-web/src/pages/ChatPage.tsx`、`src/components/common/TypewriterText.tsx` 与 `src/stores/agentChatStore.ts` 对 `/chat` 做了一轮严格限域增强：assistant 内容区统一切到更紧凑的 `text-[15px] / leading-[1.6]` 阅读节奏，并把消息与输入主画布收口到 `max-w-5xl`；流式输出不再按机械单字推进，而是改成 1-3 字的小块式 token rhythm；消息滚动区新增“用户手动打断即停止自动跟随、接近底部再恢复”的智能粘性滚动；输入区在生成中会把发送按钮切换为显式“停止生成”控制，前端直接中断现有 SSE 流。此次改动不调整 agent API、会话历史、技能选择或路由结构，只提升问股页的阅读密度、流式手感与生成控制体验。
- 💬 **问股 Chat 改为宽画布对话流 + 三层底部控制台** — `apps/dsa-web/src/pages/ChatPage.tsx` 继续收口 `/chat` 的信息架构：消息画布从先前偏窄的 `max-w-4xl` 进一步放宽到接近主工作区宽度，避免在全宽 shell 里仍像被困在中间盒子中；底部输入区改成真正的三层控制台，上层恢复教程卡片与起手问题，中层恢复并重排默认策略/技能入口，下层保留悬浮输入框本体；策略 pill 同时改为可换行、不截断的排布，避免 `缠论` 等长标签在右侧被裁掉。此次改动保持会话历史、流式回复、追问上下文、导出/发送动作与 agent API 不变，只重构问股页面的前端信息架构与交互壳层。
- 🎯 **Scanner 改为左控制台 + 右战术情报流** — `apps/dsa-web` 重构了已登录 `/scanner` 的主骨架：废弃原先上半区左右对半的网格和右侧巨大数字 hero，改成固定宽度的左侧参数控制台加可伸缩的右侧结果流。右栏候选结果不再只是横向小卡片或虚荣计数，而是直接按 shortlist 渲染“AI 洞察 + 建仓区间 + 目标位 + 严格止损”的战术卡片，让用户优先看到筛出逻辑与执行计划。此次改动保持 scanner API、鉴权和历史抽屉边界不变，只调整前端信息架构与展示密度。
- 🌫️ **Guest surfaces unified onto the glass paywall contract** — `apps/dsa-web` tightened the anonymous-session experience across `/guest` and protected routes without widening backend scope. `PremiumPaywall` now uses the same restrained glass shell as the rest of the product instead of the old bright cyan CTA + solid dark slab treatment; guest `/scanner` no longer renders the separate preview/teaser page and now resolves directly to the shared paywall, matching `/chat`、`/portfolio`、`/backtest`; and `GuestHomePage` now uses the same low-opacity glass cards, ghost CTA treatment, and subdued placeholder tone instead of the previous cyan-heavy funnel styling. This pass changes only guest-facing route presentation and tests, not auth rules, API contracts, or signed-in scanner behavior.
- 🏠 **首页决策面板完成细节级视觉与交互修复** — `apps/dsa-web` 对已登录 Home Bento surface 做了一轮严格限域的收口：抬高标题区顶部留白，避免 `WolfyStock 决策面板` 紧贴导航；将非涨跌语义的装饰性强调从绿色切换为系统霓虹蓝，用于首页状态 badge、卡片辉光与图表提示锚点，继续保留 `看多 / +18.2% / 零轴上方金叉` 等明确看涨信号的绿色语义；“AI 决断”图表补齐了支撑/阻力虚线、价格/时间刻度与突破标注锚点，不再是漂浮的单折线占位；“执行策略”卡片修复了建仓区间换行与下半区拥挤问题；技术形态/基本面画像各自补充了 RSI、波动率、PE、机构持仓等数据；首页搜索条右侧的 `↵ Enter` 现改为真实可点击的 submit button，并带有 hover/cursor/z-index 反馈。此次改动保持首页仍为前端占位数据，不改变后端接口、认证规则或其他页面路由。
- 🛠️ **WolfyStock UX 故障修复与端到端验证补齐** — `apps/dsa-web` 修复了本轮 UX 报告中的关键前端断点：登录/引导页现在在 `authEnabled=true` 或 bootstrap `setupState` 下都能正确暴露入口；预览路由 `__preview/report` 与 `__preview/full-report` 不再只在 `import.meta.env.DEV` 下注册，生产预览构建与 WebKit/Safari 路径都能访问；Scanner / Chat / Portfolio 的页面壳层补齐了稳定的 Bento surface / hero / drawer test hook，并把 smoke 套件收口到真实页面契约，避免把不存在的 hero/drawer 结构误判成回归。同时新增 `apps/dsa-web/scripts/verify-browser-flows.mjs` 与 `scripts/verify_runtime_writes.py`，将 Chromium/WebKit 路由截图、SPA 重放结果、以及 Portfolio / Scanner / Rule Backtest / Chat 的 SQLite 持久化检查统一落到仓库内本地验证报告目录。
- 🧭 **Settings / Admin 全面收口到玻璃终端风格与抽屉编辑** — `apps/dsa-web` 对 `/settings` 与 `/settings/system` 做了一轮结构级重构：个人设置主容器现在固定在居中的 `max-w-4xl` 宽度，语言切换与运行时可见性等二元选择收口为紧凑 segmented control；系统控制面则统一切到低对比毛玻璃卡片、左侧固定分类导航、右侧状态卡片流式列表，并把数据路由、运行摘要可见性、原始兼容字段编辑继续下沉到右侧 Drawer，避免主页面继续平铺大段表单。此次调整不删减现有 AI routing、数据源库、智能导入、密码修改或日志入口能力，只重构视觉基线与交互深度。

## 2026-04-25

- 🖥️ **Web 宽屏骨架全面放宽并改为多列重排** — `apps/dsa-web` 现已对 Home、Scanner、Chat、Portfolio 的 workspace 外层和 shell 宽度上限执行定向放宽：目标页面统一切到 `max-w-[1920px]` 宽屏容器，并为首页/扫描器观察名单引入更高列数的自适应网格，而不是继续把单卡片横向拉长。`ChatPage` 改为左侧状态边栏 + 右侧居中聊天主窗的 Slack/Discord 式结构，`PortfolioPage` 改为左侧 Trade Station、中间总资产与持仓、右侧历史记录常驻的三栏终端布局；Scanner 用户页与管理页的底部 watchlist 同步扩展到 `xl:6列 / 2xl:8列`。本次调整保持既有路由、数据流、分页删除动作与后端契约不变，只重构宽屏信息密度和骨架分栏方式。
- 🧱 **Chat / Backtest 恢复原生页面滚动** — `apps/dsa-web` 放弃了 Chat 与 Backtest 先锁定整页高度、再把滚动塞进局部面板的策略，统一回归浏览器原生页面滚动。Backtest 主工作区、历史评估控制台/显示板以及相关结果卡片不再依赖 `overflow-y-auto / no-scrollbar / h-full / min-h-0` 组成的内嵌滚动链，图表与结果区会按内容自然撑开，整页作为长报告顺滑下滚；Chat 则移除了消息主区的局部滚动锁，改为整页随对话长度自然增长，同时把输入区改成底部 sticky 悬浮，避免查看长对话时输入能力丢失。此次调整不删减既有功能、数据面板与提示入口，只重置滚动所有权。
- 🧭 **Web 全系统 UI 密度重置与视口锁定收口** — `apps/dsa-web` 现已对共享 `Shell / PreviewShell / PageChrome / Input / Select`、SpaceX 主题末端覆盖层，以及高密度的 Home Bento / Portfolio / Admin Logs 页面执行统一降密：正文与标签层级整体缩小、卡片与控件间距压缩、输入高度收口到 `h-9`、表格行高下降、导航与 tab 样式改为更薄的仪表盘节奏，同时把壳层主链路改成 `h-screen + flex + min-h-0 + overflow-hidden`，将页面滚动收口到内容区内部而不是继续把整个 body 撑长。此次调整保持现有路由、数据流和后端契约不变，目标是减少首屏纵向占用和多重滚动条。
- 🗂️ **Portfolio 持仓页右侧改为持仓主面板 + 历史抽屉** — `apps/dsa-web/src/pages/PortfolioPage.tsx` 移除了右侧 `Current Holdings / Order History` tabs，右栏现在固定聚焦当前持仓，历史委托/资金流水/公司行为改为通过右上角“历史记录 ↗”按钮呼出的页面级右侧抽屉承载。该调整保持现有数据流、分页、删除动作和左侧交易/账户/同步工作台不变，只收口右侧信息密度与滚动行为。
- 🎯 **WolfyStock 品牌图标正式接入 Web 平台** — `apps/dsa-web` 新增独立 `WolfyStock` mark 资源，并把它接到顶栏品牌位、移动端品牌位、预览壳、首页 `WolfyStock` 标题旁、启动 splash fallback 与运行时 loading screen，同时把浏览器 favicon 切到该品牌图标。此次改动只更新前端品牌呈现，不改变现有路由、数据流或后端契约。
- 🧹 **后端大审计仓库收敛（文档与审计产物治理）** — 将根目录一次性审计报告 `backend-final-audit-report.*` 与 `backend-frontend-global-audit-report.*` 归档到 `docs/architecture/archive/audits/`，删除本地切片交接产物 `slice_report_*.json`，并在 `README.md` 中补充当前项目文档真源入口，减少仓库根目录噪音，降低后续维护时的检索成本。
- 🧭 **维护手册补充后端优先边界** — `docs/architecture/backend-frontend-modular-maintenance-handbook.md` 明确当前维护默认以后端/API/存储为主，前端仅用于所有权映射与兼容检查，避免在前端重构期把后端审计扩散成跨端改造。
- 🧮 **Portfolio 历史快照缓存正确性修复** — 修复了 `portfolio` 历史日期快照错误复用账号级最新 `positions/lots` 缓存的问题。现在只有“该账号当前最新快照日期”才会命中持仓缓存；历史日期快照会回退到重放计算，避免在先缓存较新日期后重读旧日期时错误显示较新的持仓数量。

# Changelog

- 🧭 **Admin console 与登出流收口** — Web 前端移除单独的管理员模式：管理员账号现在与普通用户看到相同的设置、持仓、回测、扫描器等页面，仅在导航栏额外显示 `Console` 控制台入口。登出确认后会回到 guest 首页；`/settings/system` 控制台继续复用现有系统配置 API，新增 Alpha Vantage、Finnhub、Yahoo/YFinance、FMP、GNews、Tavily 等内置数据源的安全可编辑入口，并同步清理 EN/ZH 中遗留的 Admin Mode 文案。后端、SQLite primary、Phase F/G 与 smoke 覆盖语义均未改变。
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

> For user-friendly release highlights, see the [GitHub Releases](https://github.com/ZhuLinsen/daily_stock_analysis/releases) page.

## [Unreleased]

### 修复

- 💬 **问股 Chat 全宽气泡、底部遮罩与 DOM 流式输出修复** — `apps/dsa-web/src/pages/ChatPage.tsx` 与 `src/components/common/TypewriterText.tsx` 对 `/chat` 做了一轮严格限域修复：消息流主容器收口为 `max-w-4xl` 并补上 `pb-56`，防止长回复被底部输入区吃掉；assistant/user 气泡分别改为真正的全宽左流与 `max-w-[80%]` 右对话泡，移除了旧 `prose-blockquote`/思考区 `border-l` 带来的竖线与截断感；底部输入壳层改成 `z-50` 的强渐变毛玻璃遮罩，避免正文滚到输入区下方；最新一条 assistant 回复的打字机也从 `useState + setInterval` 改为 `requestAnimationFrame + ref` 直写 DOM，减少长文本流式输出时的 React 分块卡顿。此次改动不调整 agent API、会话存储、路由或技能数据流，只修正问股页面的渲染壳层与流式表现。
- 🎛️ **Scanner 筛选面板恢复胶囊式紧凑交互** — `apps/dsa-web` 将已登录 `/scanner` 左侧条件区从宽大的标准表单收回为单选 pill 组，统一压缩选项组垂直间距，并把底部候选区在默认态下收口为按市场区分的空态说明，不再向港股/A股复用或伪造美股占位卡片。失败运行时仍保持错误态；本次改动只涉及前端页面结构与测试，不改变 scanner API、鉴权或真实运行数据契约。

- 🚪 **游客漏斗 2.0 与登出链路收口** — `apps/dsa-web` 将游客首页重构为极简漏斗：首页只保留一句核心 Slogan、单个股票输入框和一张 `AI Decision` 预览卡，不再继续渲染旧的 Bento 网格与首页毛玻璃锁层；顶部导航在 guest 会话下现统一显示 `首页 / 扫描器 / 问股 / 持仓 / 回测`，但 `/chat`、`/portfolio`、`/backtest` 等受保护页面不再重定向回首页，而是原地渲染全屏毛玻璃 `PremiumPaywall`；同时登出流改为显式清理前端会话相关 storage key 与 cookie、跳过旧的状态回刷、并在 100ms 后硬跳 `/guest`，降低退出后残留已登录壳层或路由状态回流的概率。
- 🌫️ **Web smoke script now targets the canonical smoke surface only** — `apps/dsa-web` 的 `npm run test:smoke` 现在只执行 `e2e/smoke.spec.ts`，不再把 `portfolio-ibkr-sync.spec.ts` 这类专用 e2e 一起纳入发布前 smoke。该命令同时会显式启动本地 backend + `vite preview` 后再跑 smoke，避免 `playwright webServer` 在当前环境里偶发漏起前端导致的假失败。与此同时，canonical smoke 已补齐 `/portfolio`、`/backtest` 与 `/settings -> /settings/system` 管理工具路由验证，并对本地 `authEnabled=false` 与启用认证两种登录变体保持兼容。
- 🔐 **Web 登录恢复与 AI 渠道编辑补齐** — Web 退出登录现在会先清空本地会话态，再显式跳回登录页；登录页新增“忘记密码？”入口，并提供 `/reset-password` 请求页，通过后端 reset API 返回统一的非枚举成功提示。与此同时，AI 高级渠道编辑器现已把可编辑字段统一收口到规范化 i18n 文案，支持维护附加请求头/参数（`LLM_<CHANNEL>_EXTRA_HEADERS`），删除唯一来源渠道时也会同步清理失效的 runtime model / fallback / vision 引用，避免设置页保留悬空路由配置。
- 🧭 **WebUI auto-build scope hardening + frontend smoke alignment** — `apps/dsa-web/tsconfig.app.json` 现在会把 `src/**/__tests__/**` 与 `*.test.ts(x)` 排除在生产 `tsc -b` 之外，避免 `main.py --serve-only` 启动时把测试树误当成运行时构建输入；本次同时补强了 `PortfolioPage` 中文 IBKR sync 结果等待、`Shell` 导航测试的显式 i18n/admin-mode fixture，并把 `apps/dsa-web/e2e/smoke.spec.ts` 更新为当前“个人设置 -> 打开管理工具 -> 独立控制台”的真实信息架构，减少本地与 smoke 启动链路的假失败。SQLite primary truth、Phase F comparison-only、Phase G `.env` live-source 语义均未改变。
- 🧯 **Phase F partial-Postgres fallback hardening** — 当 `broker_connections`、`portfolio_sync_states` 等 Phase F PostgreSQL 表只完成了部分建表或被跨 phase 清理移除时，portfolio metadata / latest-sync 读路径现在会安全回退到 legacy storage，而不是直接抛出 `UndefinedTable`。本次同时补充了 real-PG 回归覆盖，锁定 broker connection surface、latest sync surface，以及 cash-ledger comparison 在多用户 account scope 下的边界行为。
- 🧮 **Rule backtest fixed-amount accumulation now honors insufficient-cash policy** — `periodic_accumulation` 在 `fixed_amount` 模式下不再用剩余现金做隐式部分成交；当剩余现金低于目标金额时，现在会按既有 `skip_when_insufficient_cash / stop_when_insufficient_cash` 语义稳定跳过或停止。此次同时补上了中文按金额定投解析回归，以及 single-account small-capital 边界测试，避免 deterministic 回测结果在资金尾段悄悄漂移。
- 📊 **Rule backtest now stores Sharpe ratio and hardens custom benchmark readback** — deterministic rule backtest metrics 现在新增 `sharpe_ratio`，并随 run/detail/history/support manifest 一起稳定暴露；同时补上 `custom_code` benchmark 成功路径回归，锁定策略收益与自定义基准收益的比较载荷，避免 benchmark 只在 fallback/unavailable 路径上被测试到。

### 新功能

- 🧩 **Bento UI refinement + deep report drawer convergence (Phases 1-4)** — `apps/dsa-web` completed a bounded Bento refinement pass across the Home surface and the shared page shell. Phase 1 removed the legacy `FLOW AUTOMATION` home card, kept `技术形态 / 基本面画像` at a 1:1 split, reduced non-essential copy, and normalized larger negative-space padding. Phase 2 introduced a dedicated `DeepReportDrawer` with a glass full-height right-side shell, body scroll locking, and two-module deep-read placeholders (`Technical Analysis` with MACD / MA / main fund inflows, plus `Fundamental Profile`). Phase 3 converged the shared `PageChrome` hero shell used by Scanner / Portfolio / Backtest / Settings / Chat / GuestHome / GuestScanner onto the same pure-black, low-opacity glass, large-radius surface contract while preserving existing data flow and route behavior. Phase 4 re-ran the focused Vitest + Playwright smoke coverage and captured local screenshot artifacts for verification. Backend contracts, page routing semantics, and existing scanner / portfolio / chat workflows remain unchanged.

- 🧱 **Bento 极简风格扩展到核心工作台页面** — `apps/dsa-web` 现已把 Home / Scanner / Portfolio / Backtest / Settings / Chat 以及 guest surfaces 的 Bento 外壳统一收口到纯黑背景上的低透明度玻璃卡片：移除了包裹整页卡片的外层灰色容器，统一为更大的圆角、弱化阴影、`bg-white/[0.02] + backdrop blur` 的面板表皮，并把 glow 限制在 hero / 决策信号等核心指标上。此次改动保持现有 PageChrome、hero strip、占位数据与后端 API 契约不变，同时补齐了统一 Bento root test hook、页级单测和 1440px / 390px Playwright smoke 覆盖。
- 🧩 **首页切换为 Gemini 风格 Bento 决策面板骨架** — Web `/` 的已登录首页现已切换为新的 Gemini-inspired Bento dashboard skeleton：以深黑背景、超大圆角玻璃卡片、看多/看空 glow 文本、占位策略/技术/基本面模块，以及基于 Drawer 的渐进披露结构重新组织首页信息密度；同时保留 guest 首页、现有路由、后端接口与契约不变，并补充 smoke 覆盖首页 Bento 栅格、抽屉交互与 EN/ZH 核心文案检查。当前数据仍为前端占位值，真实数据接入留待后续迭代。
- 🖥️ **Slice 9 frontend exposure for additive portfolio/backtest fields** — Web `/portfolio` 现已把 additive 的 `portfolio_attribution`、`account_attribution`、`industry_attribution` 接成只读摘要卡；`/backtest` 配置页的 `解析确认` 区会在 `strategy_spec.risk_controls` 存在时展示止损 / 止盈 / 移动止损；`/backtest/results/:runId` 的 `参数与假设` tab 会在 run payload 含有 `robustness_analysis` 时展示最小版状态与摘要指标。此次改动只做前端可见性补齐，不改变后端 contract、deterministic engine 或既有主交互。
- ✅ **Backtest release-readiness frontend closure** — Slices 10-16 已完成 portfolio/backtest additive dashboard 的轻量可视化、统一面板整合、hover/focus linked-highlight、ARIA tooltip 语义、路由级与页面级 bundle hardening，以及生产预览回归。当前 Vite large-chunk warning 已清除；这些改动保持 frontend-only、additive/read-only，不改变 backend、schema、API、deterministic execution 或 portfolio ledger data flow。
- 🛑 **Deterministic indicator strategies now support fixed advanced-order risk controls** — `moving_average_crossover / macd_crossover / rsi_threshold` 这三类已支持的 deterministic indicator strategy 现在进一步支持最小版 `fixed stop-loss / take-profit / trailing stop` 扩展。像 `MACD金叉买入，止盈10%，移动止损8%，死叉卖出` 这类输入不再被整体判成 unsupported；解析结果会把阈值保留到 `parsed_strategy.strategy_spec.risk_controls.{stop_loss_pct,take_profit_pct,trailing_stop_pct}`，执行时统一按既有 bar-close signal / next-bar-open exit 语义触发离场。范围仍继续保持最小：单仓位、单标的、百分比阈值，不扩展到参数优化或多资产语义。
- 🧹 **P10 DatabaseManager formal-module cleanup and shim retention clarification** — 已删除 `src/experimental/` 与 `scripts/database_doctor_experimental.py` 这类历史 reference layer，并移除了 `src.database_doctor_smoke` 中残留的 legacy split alias。默认 doctor / support bundle / optional `--real-pg-bundle` / smoke path 现在统一走正式模块 `src/storage_postgres_bridge.py`、`src/storage_topology_report.py`、`src/storage_phase_g_observability.py` 与 `scripts/database_doctor_smoke.py`；运行时桥接和正式 store 之间的默认 import 也已切到 `src/postgres_*_store.py` 正式实现。`src/postgres_phase_{a..g}.py` 兼容 shim 仍暂时保留，仅用于兼容现有测试/旧 import，当前并未宣称已彻底移除。smoke wrapper 默认输出继续收口为 `tmp/database-doctor-report-smoke.*` 与 `tmp/database-real-pg-bundle-smoke.*`。SQLite primary truth、Phase F comparison-only、以及 Phase G `.env` live-source 语义继续保持不变。
- 🏁 **P9 DatabaseManager final naming integration + Real-PG validation path** — PG bridge coordination、topology/bootstrap reporting、以及 Phase G execution-log observability 现在使用正式模块路径 `src/storage_postgres_bridge.py`、`src/storage_topology_report.py`、`src/storage_phase_g_observability.py`，默认 `DatabaseManager` / doctor / support bundle / optional `--real-pg-bundle` 全路径都已切到这些正式 helper。新增 `scripts/database_doctor_smoke.py` 作为正式 smoke/reference CLI，AI handoff `files_to_read_first` 与手册/playbook 也同步切到最终模块路径。SQLite primary truth、Phase F comparison-only、以及 Phase G `.env` live-source 语义保持不变。
- 🧩 **P8 DatabaseManager formal integration of split helpers** — 默认 `DatabaseManager` 现在正式把 PG bridge init/dispose、topology/bootstrap reporting、以及 Phase G execution-log observability 委托给 split helpers，并保持 `src/storage.py` 作为运行时入口与真值 owner。默认 doctor / support bundle / optional `--real-pg-bundle` 继续输出兼容的 Markdown/JSON 结构，同时 AI handoff `files_to_read_first` 也补入这些实际默认实现文件；SQLite primary truth、Phase F comparison-only、以及 Phase G `.env` live-source 语义均保持不变。手册与 playbook 同步更新了默认路径、smoke-run/Real-PG 验证、回滚方式与 P9 后续建议边界。
- 🧪 **P7 DatabaseManager initial split smoke harness** — 新增 split helper smoke/reference 路径，用于在不改动默认运行时真值路径的前提下，试运行 `Storage.py` 的 PG bridge coordination、topology/bootstrap aggregation 与 Phase G observability 拆分。该路径会复用现有 doctor/support-bundle 输出格式，默认仍以 `src/storage.py` 和 `scripts/database_doctor.py` 为真值；维护手册与 Real-PG playbook 也同步补充了 smoke 命令、验证步骤、限制、回滚方式与后续 formal split 边界说明。
- 🩺 **Database doctor / AI support bundle entrypoint** — 新增 `python3 scripts/database_doctor.py --write` 一键数据库体检入口，会输出紧凑 Markdown/JSON support bundle，并基于现有 topology/store runtime helpers 汇总 SQLite primary 状态、PostgreSQL coexistence 初始化状态、Phase A-G store schema/bootstrap 可见性、Phase F comparison 语义、Phase G execution-log observability，以及可直接粘贴给 AI 的 handoff block。数据库维护手册与排障 playbook 也同步把 doctor 流程提升为默认入口。
- 🧪 **Disposable Real-PG support bundle mode + Phase F authority summary** — `scripts/database_doctor.py` 现在新增 `--real-pg-bundle` 模式，可读取 `POSTGRES_PHASE_A_REAL_DSN` 或显式 `--real-pg-dsn`，在隔离的临时 SQLite 路径下对 disposable DSN 执行 Phase A-G store 初始化、schema/bootstrap 可见性、Phase G `execution_sessions` / `execution_events` shadow smoke、以及 Phase F comparison flag / allowlist 摘要检查，并输出与原 doctor 一致风格的 Markdown/JSON bundle 与专用 AI handoff block。默认 doctor 同时新增 `Phase F Authority Summary`，把 trades-list / cash-ledger / corporate-actions 的 owner-scope 提醒、allowlist 语义与非空限制集合紧凑暴露出来，而不改变任何运行时真值或 enforcement。
- 🗃️ **Phase G execution-log shadow observability and real-PG runtime audit** — PostgreSQL Phase G 现在会把 legacy `execution_log_sessions / execution_log_events` 影子写入 baseline `execution_sessions / execution_events`，并新增 `describe_phase_g_execution_log_status`、Phase G execution session list/detail 诊断入口，以及覆盖 Phase A-G schema/bootstrap 状态的 real-PG runtime audit。维护手册与排障 playbook 也补上了 execution-log ownership map、serial real-PG 验证命令，以及 shared-DSN 并行验证会在 `postgres_schema_bootstrap` 上死锁的注意事项。
- 🌐 **Portfolio snapshot market breakdown aggregation** — `GET /api/v1/portfolio/snapshot` 现在新增 `market_breakdown`，会按 `cn` / `hk` / `us` 聚合当前账户或整组 portfolio 的持仓市值，并统一换算到 snapshot 的聚合货币。这样在多账户、多市场、多币种组合下，后端可以直接给出一个最小但稳定的 multi-asset 聚合摘要，而不需要客户端自己重扫所有 positions 做二次归并。
- 🧾 **Portfolio risk report now exposes account attribution** — `GET /api/v1/portfolio/risk` 现在新增 `account_attribution`，会按当前 risk report 的聚合货币，把每个账户的 `total_equity` / `total_market_value` 贡献统一换算并计算权重。这样在多账户、多币种组合下，后端可以直接指出“是哪一个账户在主导整体风险暴露”，而不需要客户端先拉 snapshot 再自己做二次归并。
- 🧩 **Portfolio attribution expansion keeps the contract additive** — `GET /api/v1/portfolio/risk` 现在进一步新增 additive 的 `industry_attribution`，按现有 board mapping / `UNCLASSIFIED` fallback 规则给出行业贡献视图；`GET /api/v1/portfolio/snapshot` 则新增 additive 的 `portfolio_attribution`，把 `account_attribution + industry_attribution` 收口到同一个组合摘要里。同时账户级 snapshot payload 会持久化最小版 `industry_attribution`，使缓存/存储路径继续保持 stored-first，而不改原有 `concentration`、`sector_concentration`、`stop_loss` 或 deterministic engine 行为。
- 🧪 **Rule backtest now exposes a minimal robustness-analysis block** — 规则回测 detail/history 读面现在新增 additive 的 `robustness_analysis`，包含最小版 `walk_forward`、`monte_carlo` 与 `stress_tests` 摘要。walk-forward 只把 rolling train/test window 当作执行上下文，不做参数再优化；Monte Carlo 采用 deterministic seed 对历史收益做轻量扰动，返回多路径聚合指标；stress tests 目前提供少量固定冲击场景并显式给出 worst-case metrics。该能力复用现有 deterministic engine 与 stored summary，不覆盖原有 baseline metrics、benchmark 或 execution trace contract。
- 🧭 **Rule backtest support export index API** — `GET /api/v1/backtest/rule/runs/{run_id}/export-index` 现在会返回单条规则回测的紧凑 export discovery/index。当前索引稳定列出四个 support bundle 导出：`support_bundle_manifest_json`、`support_bundle_reproducibility_manifest_json`、`execution_trace_json`、`execution_trace_csv`，并显式给出 `available`、`availability_reason`、`format`、`media_type`、`delivery_mode`、`endpoint_path` 与 `payload_class`。四个导出当前都对应真实的只读 API path；trace availability 仍直接按当前 resolved `execution_trace.rows` 是否可导出判断，缺失时会稳定返回 `execution_trace_rows_missing`，而不会伪造可下载路由。
- 📤 **Rule backtest support bundle manifest API export** — `GET /api/v1/backtest/rule/runs/{run_id}/support-bundle-manifest` 现在会把单条规则回测的紧凑 stored-first support bundle manifest 直接作为 JSON 返回。该接口复用既有 service-level manifest helper 与 reopen/readback 摘要，不引入新的 summary layer；当前只暴露 `run` 基本信息、`run_timing`、`run_diagnostics`、`artifact_availability`、`readback_integrity`、轻量 `result_authority.domains` 与 `artifact_counts`，用于 backend handoff、AI 调试与自动化脚本，而不会默认内联 `trades`、`equity_curve`、`audit_rows` 或完整 `execution_trace` 等 heavy payload。
- 🧪 **Rule backtest support bundle reproducibility manifest API export** — `GET /api/v1/backtest/rule/runs/{run_id}/support-bundle-reproducibility-manifest` 现在会把单条规则回测的紧凑 reproducibility manifest 直接作为 JSON 返回。该接口复用同一条运行的 `run_timing`、`run_diagnostics`、`artifact_availability` 与 `readback_integrity` 摘要，并额外提供 `execution_assumptions_fingerprint` 与压缩后的 `result_authority.domains`，用于 migration / replay / reproducibility / backend handoff 场景，而不内联完整 heavy payload。
- 🧮 **Rule backtest compare-runs delta/summary foundation** — `POST /api/v1/backtest/rule/compare` 现在在既有 raw comparable items 之上新增了 additive 的 `comparison_summary`。该摘要层固定以请求顺序中的第一条可比运行作为 baseline，额外返回 symbol/timeframe/date-range/strategy-family context，以及一组 stored-first metric delta/可比性诊断：`total_return_pct`、`annualized_return_pct`、`max_drawdown_pct`、`benchmark_return_pct`、`excess_return_vs_benchmark_pct`。当某些指标在部分运行中缺失时，响应会显式标记 `partial` / `unavailable` 并列出 `available_run_ids` / `unavailable_run_ids`，而不是静默强算 delta。
- 🧩 **Rule backtest compare parameter-set foundation** — `POST /api/v1/backtest/rule/compare` 现在进一步新增 additive 的 `parameter_comparison`，用于回答“这些运行能否被视为同一规范化 strategy family/type 下的参数集变体”。该层只使用已持久化 compare items 中的 `parsed_strategy.strategy_spec` 与 parsed-strategy authority missing diagnostics，不会重跑或重建回测；当前会返回 `same_family_comparable / different_family / partial / unavailable` 状态，以及 `shared_parameter_keys` / `differing_parameter_keys` / `missing_parameter_keys`，帮助后续 compare UI 和 AI 调试判断哪些 normalized parameter fields 真的可比。
- 📅 **Rule backtest compare-periods foundation** — `POST /api/v1/backtest/rule/compare` 现在新增 additive 的 `period_comparison`，专门回答这些已完成运行在 period 上是否“可比”。该层只消费 compare items 里已持久化的 `metadata.period_start / period_end`，不会重跑回测，也不会静默 fallback 到新计算；当前会显式返回 `identical / overlapping / disjoint / partial / unavailable` 关系、`comparable / not_comparable / limited` 状态、baseline-first pair 级 overlap/gap 信息，以及缺少 `period_start` / `period_end` 时的 diagnostics，方便 compare API 与后续 UI 在 period 语义上做稳态判断。
- 🌐 **Rule backtest compare market/code foundation** — `POST /api/v1/backtest/rule/compare` 现在新增 additive 的 `market_code_comparison`，用于回答这些已完成运行是否真的是“同一标的/同一市场”下的可直接比较对象。该层只消费 compare items 中已持久化的 `metadata.code`，按规范化代码生成 `cn / hk / us` 市场标签，不会重跑回测；当前会显式区分 `same_code / same_market_different_code / different_market / partial_metadata / unavailable_metadata`，并把只有 `same_code` 标记为 `state=direct` 与 `directly_comparable=true`。当代码缺失或市场无法从持久化代码稳定判定时，响应会返回 pair/run 级 diagnostics，而不是静默把不同市场或不完整 metadata 也当成可直接比较。
- 🧱 **Rule backtest compare robustness-summary foundation** — `POST /api/v1/backtest/rule/compare` 现在新增 additive 的 `robustness_summary`，用于把已经计算好的 `market_code_comparison`、`period_comparison`、`comparison_summary`、`parameter_comparison` 收口成一个更紧凑的 stored-first 总结层。该层不会重跑回测，也不会重新读取 compare items 以外的新数据；它只消费现有 compare layers 的状态与 diagnostics，统一返回 `highly_comparable / partially_comparable / context_limited / insufficient_context` 四档 overall state，以及 `market_code / metrics_baseline / parameter_set / periods` 四个维度各自的 `aligned / partial / divergent / unavailable` 摘要，方便前端和 AI 在不展开全部 compare 细节时先做整体判断。
- 🗂️ **Rule backtest compare profile/classification foundation** — `POST /api/v1/backtest/rule/compare` 现在新增 additive 的 `comparison_profile`，用于回答“这次 compare 请求的主比较模式到底是什么”。该层不会重跑回测，也不会重新读取 compare items 之外的新数据；它只复用 `market_code_comparison`、`period_comparison`、`parameter_comparison` 与 `robustness_summary` 四个已计算 layers，当前会在 `same_strategy_parameter_variants / same_code_different_periods / same_market_cross_code / cross_market_mixed / mixed_context / insufficient_context` 之间做 deterministic 分类，并返回 `aligned_dimensions`、`driving_dimensions`、supporting flags 与 diagnostics，方便前端和 AI 快速判断这次比较主要是在“比参数”“比区间”还是“跨代码/跨市场”。
- 🏁 **Rule backtest compare winners/highlights foundation** — `POST /api/v1/backtest/rule/compare` 现在新增 additive 的 `comparison_highlights`，用于回答“在当前 compare 上下文里，哪些 run 在最重要的 trusted metrics 上领先”。该层不会重跑回测，也不会重新读取 compare items 之外的新数据；它只复用已有的 `comparison_summary.metric_deltas`、`robustness_summary` 与 `comparison_profile`，并且当前只覆盖已经进入 trusted compare-delta 集合的指标：`total_return_pct`、`annualized_return_pct`、`max_drawdown_pct`、`benchmark_return_pct`、`excess_return_vs_benchmark_pct`。返回结果会显式区分 `winner / tie / limited_context_winner / limited_context_tie / unavailable`，避免在 period、market/code 或整体 compare context 已受限时仍把排名伪装成完全可比结论。
- 🧭 **Rule backtest compare results/workbench frontend foundation** — Web 端现已新增最小可用的 `/backtest/compare?runIds=...` compare workbench，并把结果页 `历史结果` tab 中“当前运行 + 已勾选 completed runs”的多选入口接到这一新页面。compare workbench 不会自行重算或拼装本地 side-by-side detail，而是只消费既有 `POST /api/v1/backtest/rule/compare` 的 stored-first 合约，当前会稳定展示 baseline run、`comparison_summary`、`parameter_comparison`、`period_comparison`、`market_code_comparison`、`robustness_summary`、`comparison_profile` 与 `comparison_highlights`，同时把 `partial / limited / unavailable` 状态直接显式渲染出来，作为后续 compare 产品继续扩展的 frontend foundation。
- 🧮 **Compare workbench compact metric matrix polish** — `/backtest/compare?runIds=...` 现在在既有 compare summary / highlights / robustness sections 之上新增了一块更紧凑的 metric matrix，用一张表直接并排展示 baseline 与候选 runs 在 trusted compare metrics 上的值、`delta vs baseline`、winner/highlight 状态以及 `unavailable` 情况。该矩阵不引入新后端字段，也不在前端重算 compare 结论，只复用已有的 `comparison_summary.metric_deltas`、`comparison_highlights`、`robustness_summary`、`comparison_profile` 与 compare items，目的是让用户能更快扫读“谁领先、领先多少、这个领先是否受 limited/partial context 影响”。
- 🧭 **Compare workbench selection/navigation polish** — compare workbench 的 `参与运行` 表现在会把当前比较里的 baseline / candidate runs 变成可操作行：每条 run 都可以直接跳回单条结果页，candidate 还可以在当前 `/backtest/compare?runIds=...` 会话里直接移除。该改动仍只复用既有 query-param selection 与 compare API 合约，不新增后端字段，也不改变 compare route。
- 🔀 **Compare workbench baseline switching / run ordering polish** — compare workbench 现在允许用户直接在页内把某个 candidate 提升为新的 baseline；实现方式不是新增 compare state，而是重排既有的 `runIds` query param，把目标 run 提到第一位，再继续调用同一个 compare API。前端也会按当前 `runIds` 顺序稳定渲染 compact matrix 与参与运行表，避免 baseline 切换后出现展示顺序与 compare 语义脱节。
- 🏷️ **Compare workbench metric scanability polish** — compact metric matrix 现在会把 compare 已有状态直接渲染成更紧凑的视觉 cue：summary state、winner/limited/unavailable 状态以及 `delta vs baseline` 的正负方向会分别带上 deterministic badge / tone。该改动只消费已有的 `comparison_summary.metric_deltas` 与 `comparison_highlights`，不增加任何新后端字段，也不改变 compare 语义。
- 🧭 **Compare workbench sticky section navigation polish** — compare workbench 现在会在结果区顶部渲染一块紧凑的粘性 section 导航，允许用户快速跳到 `比较摘要`、`comparison_highlights`、`compact metric matrix`、`robustness + profile`、`market / period context`、`parameter + metrics` 和 `参与运行`。该导航只复用前端现有 section 结构与锚点，不改 compare route，也不引入新的后端依赖。
- 📊 **Compare workbench lightweight chart strip** — compare workbench 现在新增了一块很轻量的 mini chart strip，用已有 compare metrics 的 trusted 子集做紧凑可视化，帮助用户先用视觉方式扫一眼 baseline 与 candidate 的关键差异和 `limited / unavailable` 状态。该视觉层仍只消费 compare API 已有数据，不改变任何后端语义。
- 🗂️ **Compare workbench density / section collapse polish** — compare workbench 现在会对较低优先级的 compare sections 提供轻量 collapse/expand 控件，当前覆盖 `comparison_highlights`、`market / period context`、`parameter + metrics` 与 `参与运行`，并保持默认展开。该改动只在前端本地减少滚动密度，不新增持久化偏好，也不改变 compare route 或后端 contract。
- 🔗 **Compare workbench export / share polish** — compare workbench 现在在比较摘要区新增了一组轻量复制动作，支持直接复制当前 compare 链接、当前 `runIds` 选择，以及基于当前已渲染 compare 数据拼出的短摘要文本。该能力只复用前端已有 route/query 与 compare summary 数据，不依赖后端新增导出接口。
- 📦 **Rule backtest stored-first artifact availability summary closure** — 规则回测现在会把结构化 `artifact_availability` 摘要稳定暴露到 status/detail/history 三个读面，并在 `summary.artifact_availability` 中保留同形读回块。该摘要只关注“持久化 artifacts 是否存在”：`has_summary`、`has_parsed_strategy`、`has_metrics`、`has_execution_model`、`has_comparison`、`has_trade_rows`、`has_equity_curve`、`has_execution_trace`、`has_run_diagnostics`、`has_run_timing`。对于旧运行缺失该摘要的情况，服务会从当前持久化事实做最小兼容回填；若 stored summary 仍声明有 trade rows 但真实持久化 trade rows 已丢失，则会显式标记 `summary.artifact_availability+live_storage_repair` / `stored_partial_repaired`，避免 reopen/debug 流程继续消费过期 availability 状态。
- 🧭 **Rule backtest stored-first readback integrity summary closure** — 规则回测现在会在 status/detail/history 三个读面统一返回结构化 `readback_integrity`，用一小块稳定字段直接说明这次 reopen 的可信度：`source`、`completeness`、`used_legacy_fallback`、`used_live_storage_repair`、`has_summary_storage_drift`、`drift_domains`、`missing_summary_fields`、`integrity_level`。它复用已有 `result_authority` 与 `artifact_availability` 信号，把“纯 stored-first / stored repaired / legacy fallback / drift repaired” 这类判断从分散字段中收口出来，便于后续 debug 和 AI-assisted triage 直接消费。
- 🩺 **Rule backtest failed/cancelled run diagnostics closure** — 规则回测的 failed / cancelled runs 现在会在 stored summary 中额外保留一份结构化 `run_diagnostics` 摘要，并在 status/detail/history 三个读面稳定回放。该摘要把已有的 `status_history`、`status_message`、`no_result_reason`、`no_result_message` 收口为更直接的 reopen 诊断信息，例如 terminal status、reason code、最近状态迁移时间以及终态前最后一个非终态 stage，减少排查时对瞬时日志的依赖。
- ⏱️ **Rule backtest stored-first lifecycle timing summary closure** — 规则回测现在会在 stored summary 中同时保留结构化 `run_timing`，并在 status/detail/history 三个读面稳定回放。该 timing 摘要聚焦生命周期时间线本身：`created_at`、`started_at`、`finished_at`、`failed_at`、`cancelled_at`、`last_updated_at` 以及 `queue_duration_seconds`、`run_duration_seconds`，帮助 reopen / debug 流程直接判断回测到底停在哪个阶段、是否真正进入执行，以及终态时间与 row-level `completed_at` 是否一致。
- 📤 **Rule backtest execution-trace JSON API export closure** — support export index 里原本只被标记为 service/file-export 的 `execution_trace_json` 现在已经落成真正可消费的只读 API export。单条规则回测可通过新的 execution-trace JSON endpoint 直接拿到 trace rows、assumptions、execution model 与 fallback 元信息，方便 AI 调试、自动化脚本、backend handoff 和迁移场景使用；export index 里的 delivery metadata 也同步改为真实的 `api` 入口。
- 📄 **Rule backtest execution-trace CSV API export closure** — support export index 里原本仍停留在 service/file-export 的 `execution_trace_csv` 现在也落成了真正可消费的只读 CSV API export。单条规则回测可直接通过新的 execution-trace CSV endpoint 拿到表格友好的 trace rows 导出，适用于 operator 检查、脚本消费、handoff 与迁移场景；当 trace rows 不存在时，该接口会和 JSON export 一样明确返回 unavailable，而不是伪装成可导出。
- 🧾 **Rule backtest reopen trade_rows provenance hardening** — 规则回测 detail/history 重开现在会对 `trade_rows` 执行 stored-first 解析，并在 `result_authority` 中新增 `trade_rows_source` / `trade_rows_completeness` / `trade_rows_missing_fields`。当已持久化 `rule_backtest_trades` 完整可用时，detail 会明确标记 `stored_rule_backtest_trades`；当历史 trade-row 辅助 JSON 缺失或损坏时，服务会返回稳定 shape 的交易明细并显式标记 `stored_rule_backtest_trades+compat_repair` / `stored_partial_repaired`；若 run row 仍声明存在交易但持久化 trade rows 已丢失，则会明确返回 `unavailable`，避免把空交易列表误判成完整重开结果。
- 📐 **Rule backtest reopen metrics provenance hardening** — 规则回测 detail/history 重开现在会对 `summary.metrics` 执行 stored-first KPI 解析，并在 `result_authority` 中新增 `metrics_completeness` / `metrics_missing_fields` 诊断字段。历史 partial metrics 会显式标记为 `summary.metrics+row_columns_fallback` 且注明哪些 KPI 由 run row columns 修补；当只有 legacy row columns 可用时，会标记为 `row_columns_fallback` / `legacy_row_columns`，不再把 stored metrics 与 row fallback 混成无来源说明的一组返回值。
- ⚙️ **Rule backtest reopen execution_model provenance hardening** — 规则回测 detail/history 重开现在会对 `execution_model` 执行 stored-first 解析，并严格优先消费 `summary.execution_model`，其次回退到已持久化的 `summary.request.execution_model`，最后才从已存 assumptions / row/request 派生兼容配置。历史 partial execution-model snapshot 会显式标记为 `summary.execution_model+repaired_fields` 或 `summary.request.execution_model+repaired_fields`，并在 `result_authority` 中新增 `execution_model_completeness` / `execution_model_missing_fields` 诊断字段；返回的 `execution_model` 负载也会被规范化为稳定字段形状，避免 reopen 时静默丢字段或无来源地重推导。
- 🧱 **Rule backtest result_authority contract normalization** — 规则回测 detail/history 的 `result_authority` 现在在保留原有扁平诊断字段的同时，新增版本化的 `contract_version` + `domains` 归一化视图。每个 `domains.<name>` 条目统一使用 `source` / `completeness` / `state` / `missing` / `missing_kind`，从而把 `missing_fields`、`missing_sections`、`missing_keys` 这类原本分散在不同顶层键里的信息折叠成更稳定的调试契约；`omitted_without_detail_read`、`unavailable`、`empty` 等状态也会被规范化为统一的 `state` 表达，方便 AI/debugger 在 detail 与 history 响应之间做一致判断。
- 🧾 **Rule backtest reopen replay/audit provenance hardening** — 规则回测 detail/history 重开现在会对 `summary.visualization.audit_rows`、`daily_return_series`、`exposure_curve` 执行 stored-first 解析，并在 `result_authority` 中新增 `replay_payload_source` / `replay_payload_completeness` / `replay_payload_missing_sections` 以及每个 replay section 的 source 诊断字段。历史运行若只存了部分 replay payload，服务会显式标记 `summary.visualization.audit_rows+repaired_sections` 或 `stored_replay_sections+derived_audit_rows`；若只有 legacy run artifacts 可回补，则会标记 `derived_from_stored_run_artifacts`；未读取 detail 或确实不可用时，也会明确返回 `omitted_without_detail_read` / `unavailable`，避免 reopen 时静默再生成 audit/replay payload 却看不出来源。
- 🧮 **Rule backtest reopen benchmark/comparison provenance hardening** — 规则回测重开现在会对 `summary.visualization.comparison` 执行 stored-first 解析，并显式区分 `summary.visualization.comparison`、`summary.visualization.comparison+repaired_sections`、`derived_from_stored_visualization_components` 与 `unavailable`。对历史 partial comparison payload，会仅从已持久化的 legacy visualization sections 补齐缺失 comparison sections，并在 `result_authority` 中新增 `comparison_completeness` / `comparison_missing_sections` 诊断字段；同时 `rows=[]` 形式的已持久化 comparison curves 不再被误判为需要回退到 legacy curves。
- 🧭 **Rule backtest reopen execution trace provenance hardening** — 规则回测明细重开现在严格优先消费已持久化的 `execution_trace`；若仅有 legacy stored audit rows，则会显式标记为 `rebuilt_from_stored_audit_rows`，并在 `result_authority` 中新增 `execution_trace_completeness` / `execution_trace_missing_fields` 诊断字段。对于只有空/部分 trace 的历史运行，服务会修补缺失元数据但不再把 `rows=[]` 误判成需要重建；若既没有持久化 trace 也没有持久化 audit rows，则会显式返回 `unavailable`，避免从 reopen 时临时回放得到的 audit rows 再次静默生成 trace。
- 📏 **WS1 基线与验证命令面落地（无优化改动）** — 新增 `scripts/ws1_baseline_capture.py`，用于在单进程 API 前提下统一采集 scanner、portfolio snapshot、analysis/search 与 backtest smoke 的可复现基线时延与结果摘要，并将结果落盘到 `reports/ws1_baseline/`。同时更新 `docs/DEPLOY.md`、`docs/DEPLOY_EN.md`、`docs/full-guide.md`、`docs/full-guide_EN.md`，收口了 clean-checkout smoke 路径（仅仓库已提交脚本）、target-host queue/SSE 单进程验证 checklist 和 WS1 专用回滚 checklist。
- 🚦 **部署前运行时加固（健康检查 / 队列关停 / 部署文档）** — API 新增 `/api/health/live` 与 `/api/health/ready`，并把 `/api/health` 收口为 readiness alias；readiness 现在会检查 `SystemConfigService`、存储 `SELECT 1`、任务队列 shutdown 状态以及当前 process-local queue/SSE 拓扑是否仍满足单进程部署假设。应用生命周期同时显式接管分析任务队列的激活与关闭，在 shutdown 时停止接受新任务并清理进程内订阅状态；Docker healthcheck 改为直接命中 `/api/health/ready`，不再用兜底成功掩盖真实故障。部署与 smoke 文档也统一切到当前 `--serve` / `--serve-only` 入口，补入 live/ready 检查与单进程 API 部署说明，并将回测 smoke 示例收口为仓库内已提交的 `scripts/smoke_backtest_standard.py` / `scripts/smoke_backtest_rule.py`。

- 🧬 **PostgreSQL Phase C market metadata baseline（opt-in）** — 在保持 OHLCV 继续留在 Parquet / 本地 / NAS 的前提下，新增 PostgreSQL Phase C 元数据适配层：`symbol_master`、`market_data_manifests`、`market_dataset_versions` 与 `market_data_usage_refs` 现在可通过现有 baseline DSN 显式登记 symbol 热元数据、dataset manifest/version 以及运行时 usage provenance。当前实现保持 metadata-only，不接管 scanner/backtest 运行时持久化，也不会改写现有本地 parquet 读取路径；同时补入了本地 US parquet manifest/version 登记 helper 与对应 real-PG / focused tests，为后续 Phase D/E 的 reproducibility anchor 做准备。
- 🗄️ **PostgreSQL Phase A identity/preferences baseline（opt-in）** — 新增受控的 `POSTGRES_PHASE_A_URL` / `POSTGRES_PHASE_A_APPLY_SCHEMA` 运行时入口；配置后，`app_users`、`app_user_sessions`、`user_preferences` 与归一化后的 `notification_targets` 会优先落到 PostgreSQL Phase A store，同时保留 auth-disabled bootstrap-admin、legacy signed-cookie 与 guest preview 不持久化语义。未配置时继续保持现有 SQLite 路径；若显式配置但 PostgreSQL 初始化失败，会在启动时直接报错，避免出现半切换状态。
- 🔎 **Scanner observability / provider diagnostics 有界增强** — Scanner run 现在会持久化并返回紧凑的 coverage summary 与 provider diagnostics：可直接看到 `input universe / liquidity-filter survivors / data-availability survivors / ranked pool / shortlist`，以及按有界理由汇总的淘汰计数，不再只能从最终 shortlist 猜测“为什么只剩这么少”。同一批 metadata 也会进入 `/admin/logs` 的 `scanner` subsystem，管理员现在能从全局 observability 里区分 scanner run、查看 run id、market/profile、providers used、fallback 次数、provider failure count 与 coverage summary；Web `/scanner` 则新增紧凑诊断面板，用于解释 shortlist 偏小到底是因为 universe 过小、过滤过严还是 provider/data availability 压缩了候选池。
- 🛡️ **Admin system control-plane 一轮有界硬化完成** — `/settings/system` 现在收口为真实的管理员全局控制面：普通用户不可进入，管理员只有在 `Admin Mode` 下才会看到完整 system/global 内容；已认证管理员进入 Admin Mode 后也不再需要额外的 system-settings unlock。危险操作改为动作级确认，本阶段只新增了有界的 runtime cache reset 维护动作，没有引入数据库清空之类的破坏性后端。与此同时，provider / data-source 表单改为按凭据 schema 渲染，现已同时支持 single-key 与 key+secret 两种形态，`TWELVE_DATA_API_KEY(S)` 与 `ALPACA_API_KEY_ID + ALPACA_API_SECRET_KEY` 都能在当前系统设置流中正确录入。
- 🧨 **Admin control-plane 第二轮有界硬化完成** — `/settings/system` 进一步去掉了个人通知/偏好式内容，重新聚焦为全局 system surface；`/admin/logs` 也从“执行会话列表”收口为更接近真实 admin observability 的全局活动流，日志摘要可区分 actor、activity type、subsystem 与 destructive admin action。与此同时，admin actions 区现在明确拆分 `runtime cache reset` 与 `factory reset / system initialization`：前者继续是安全 maintenance，后者新增为真正的有界 destructive flow，要求输入 `FACTORY RESET` 才能执行，并只清空非 bootstrap 用户、其会话、用户偏好/通知目标、分析/聊天历史，以及用户拥有的 scanner / backtest / portfolio 使用状态，保留 bootstrap admin、系统配置与 execution logs。
- 🧪 **IBKR 只读同步工作流完成一轮可信度硬化** — IBKR `/portfolio` 手动只读同步现在把缺少/过期 session、空账户、多账户歧义、缺少账户标识、映射冲突、空持仓/空现金回退以及上游 payload 不受支持等高风险路径统一收口为结构化、前端可展示的错误或 warning；同一用户的多账户同步路径也新增了有边界的覆盖，确认 repeated sync 继续替换当前 sync overlay，而不会污染另一账户或重写 Flex import 的历史 ledger 语义。Web 端同步结果卡会保留 warning 展示，仓库内也补入了一个受控的 `/portfolio` Playwright happy-path smoke 与精确手工验收 checklist，用于在受限环境无法启动浏览器时继续做真实验收。
- 🔄 **Portfolio 新增手动触发的 IBKR 只读 API 同步基础能力** — 在保留现有用户自有 broker connection、IBKR Flex XML 导入和多市场/多币种持仓模型的前提下，`/portfolio` 现已增加最小化的 IBKR Client Portal 风格只读同步入口。用户可对自己名下的 IBKR connection 提供一次性 session token 手动同步账户摘要、持仓和多币种现金状态；系统只保存非敏感的 API 默认配置与最近同步元数据，不保存 session token，也不会暴露任何下单/执行能力。重复同步会覆盖当前 sync-state，而不是无控制地新增重复持仓；历史日期快照仍继续依赖原有 ledger / 文件导入链路，因此 API sync 与 Flex 导入可互补共存。
- 💼 **Portfolio broker imports expanded to user-owned IBKR global-market support** — 持仓系统现在新增用户自有的 `broker connection` 基础模型与最小 API，可把券商连接、导入指纹与后续只读同步元数据稳定绑定到当前登录用户名下。导入层在保留现有华泰 / 中信 / 招商 CSV 路径的同时，新增通用 broker import 入口与 IBKR Flex Query XML 首版支持：可解析、预览并提交美股/港股交易、跨币种现金流水与安全可映射的拆股记录，首次导入会自动创建或复用当前用户自己的 IBKR connection，并通过文件指纹阻止同一 connection 的重复写入。组合层同时补齐 `global` 账户语义与多币种快照口径，单账户 snapshot/risk 会跟随账户 base currency，而不再默认假设 `CNY`。
- 🧱 **Post-foundation hardening: backtest isolation, guest preview session scoping, personal notification targets, and logout return flow** — 标准回测结果查询现在会对 `run_id` 做真实 owner 校验，普通用户不再通过“空列表”模糊撞到 bootstrap-admin / legacy backtest 记录；公开 `/api/v1/analysis/preview` 现在会为 guest 生成轻量匿名 session cookie，并把 preview query 链路按 guest session 隔离，同时继续保持不落 `analysis_history`；`/settings` 新增最小个人通知目标配置，注册用户现在可保存自己的 email 与 Discord webhook，单股分析通知会优先解析到这些 user-owned target，而不是继续复用 admin/system Discord 或 operator 通道；前端退出登录确认后也会显式返回 guest 首页，避免停留在受保护页面壳层里。
- 🔐 **Frontend/auth smoke verification stabilized** — `npm run test:smoke` now builds first, starts or reuses the backend at `127.0.0.1:8000`, starts `vite preview` at `127.0.0.1:4173`, probes backend auth status through the backend URL, and runs only the canonical `e2e/smoke.spec.ts`. The smoke now focuses on release-critical home, auth-route, portfolio, and `/settings/system` coverage, with Safari validation confirming Admin Mode system settings, AI provider summary visibility, and EN/ZH switching; full logout and ordinary-user denial checks remain environment-limited when local `authEnabled=false`.
- 🔌 **Scanner market-data provider 凭证模型扩展** — Provider 凭证层现在同时支持 single-key 与 key+secret 两种模式：`TWELVE_DATA_API_KEY(S)` 保持 Twelve Data 的单 Key / 多 Key 配置，`ALPACA_API_KEY_ID + ALPACA_API_SECRET_KEY` 作为 Alpaca 的成对凭证输入；系统设置校验与环境变量兼容层也已同步支持，避免继续把所有 provider 都压成单 Key 模式。
- 🇭🇰 **Market Scanner 新增 HK profile，并补强 US live market-data 路径** — Scanner 现在新增独立港股 profile：`hk_preopen_v1`，复用现有 run persistence / watchlist / diagnostics 基建，但使用单独的 HK bounded universe、`HK02800` benchmark、港股化 reasons/risk notes/watch context，并优先通过 Twelve Data 补强 HK quote / daily history。同时美股 `us_preopen_v1` 也补入了 bounded liquid seed supplement 以避免本地 universe 过薄时退化成极小样本 shortlist，并在配置完整 Alpaca 凭证时优先尝试 Alpaca 做 US quote / daily enrichment；Web `/scanner` 现已支持显式切换 `A股 / 美股 / 港股` 与对应 profile，同时在当前结果、history 与导出摘要中保留明确的 market/profile 上下文与 provider/fallback 诊断。
- 🧭 **Multi-user product surface Phase 5 landed for role-aware flow polish** — Web 端继续在已完成的 guest / user / admin 分层基础上补齐入口与拒绝态体验：登录页现在会保留并解释回跳目标，guest“创建账户”CTA 会直接进入创建模式，用户/管理员受限页面改为更贴近场景的锁定文案与下一步动作，`/login` 在已登录或禁用认证场景下也会优先回到原目标路径。管理员账户默认停留在更安全的 `User Mode`，只有显式切到 `Admin Mode` 后才会暴露 operator 页面；普通用户任务面板则隐藏原始技术 task ID，改为保留标的、阶段、进度与更新时间。同时前端 401/403 解析不再把应用内登录/权限问题误判成上游 provider 故障，系统设置入口文案与 guest 次级 teaser CTA 也做了更明确的角色导向收口。
- 🧭 **Multi-user product surface Phase 4 landed for guest / user / admin frontend split** — Web 现已形成明确的三层产品面：游客可直接进入首页与 Scanner 预览，并通过新的公开 `/api/v1/analysis/preview` 获取不落库的受限分析摘要；注册用户继续使用完整的分析、问股、回测、持仓与个人历史；管理员则通过显式 `/settings/system` 与 `/admin/logs` 入口进入系统/operator 控制面。默认 `/settings` 也已收口为个人偏好页，避免把系统级 provider/config/schedule 控制继续混在普通用户设置中。
- 🔒 **Multi-user foundation Phase 3 landed for backend authorization and access isolation** — Backend admin/system APIs now enforce real admin checks instead of relying on UI visibility or unlock tokens alone, scanner scheduled/system watchlists are explicitly admin-scoped, user-owned scanner/manual runs are explicitly owner-scoped, analysis task queue stats/deduplication now isolate by owner, and cross-user chat session access now returns stable not-found responses instead of leaking global behavior or bubbling into generic server errors.
- 🔐 **Multi-user foundation Phase 2 landed for real app-user authentication and current-user sessions** — Added persistent `app_user_sessions`, signed identity-bearing `dsa_session` cookies, `/api/v1/auth/login|logout|me` foundations, and backend current-user resolution that now distinguishes authenticated normal users, authenticated admins, and explicit transitional bootstrap mode. The legacy bootstrap admin credential file remains temporarily supported, but is now mirrored into `app_users` so admin identity resolves through the same model as normal users. User-facing modules touched in Phase 1 now receive concrete `owner_id` values from authenticated requests instead of assuming a shared global actor.
- 👥 **Multi-user foundation Phase 1 landed for user-owned storage domains** — Added a bootstrap transitional app-user model plus ownership fields/defaults across `analysis_history`, portfolio accounts, backtest artifacts, rule backtest runs, chat sessions, and mixed-scope scanner runs. Legacy single-user rows now backfill to a seeded bootstrap admin owner, manual scanner runs persist as user-scoped records, scheduled/operator scanner runs persist as system-scoped records, and repository/service queries now resolve owner-aware visibility instead of assuming globally shared product data.
- 🔎 **Market Scanner（A 股盘前扫描）首个生产版上线** — 新增独立 `Scanner` 产品能力与 `/scanner` 页面、`/api/v1/scanner/*` API、轻量 run 历史与候选详情抽屉。第一阶段聚焦 A 股盘前观察：先用受控 universe 和全市场快照做预筛，再用本地优先的日线历史做规则型评分，输出 `rank / scanner score / reason summary / key metrics / risk notes / watch context / run metadata`，并允许从 shortlist 继续进入深度分析、问股与回测。Scanner 明确保持为主动发现层，不并入 Backtest。
- ⏰ **Market Scanner P9 运营层上线** — Scanner 新增独立盘前定时任务、每日 watchlist 聚合查询（today / recent）、通知投递记录与运营状态摘要。定时运行会按 `watchlist_date` 保留 daily shortlist，并记录 `trigger_mode`、通知成功/失败、基础失败原因与空结果状态；Web `/scanner` 现在可以直接查看今日观察名单、近期 watchlists、最近定时运行和通知状态，CLI 也新增 `--scanner` / `--scanner-schedule` 入口，继续保持 Scanner 与 Backtest 的边界不变。
- 📋 **Market Scanner Route A 日常工作流增强** — `/scanner` 现在会把“今天 shortlist 了什么”继续延伸到“和前几天相比变化了什么、后来表现如何、最近是否仍有效”。页面新增跨日 watchlist 对比（新入选 / 连续入选 / 掉出名单）、候选 follow-through 结果跟踪（same-day / next-day / review window / max favorable / max adverse）、近期 quality summary（平均 shortlist 收益、hit rate、跑赢基准率、兑现/未兑现候选均分）以及紧凑 Markdown 日评导出。整套实现继续复用现有 scanner 持久化与本地 `stock_daily`，保持 Scanner 与 Backtest 的产品边界不变。
- 🤖 **Market Scanner A 股 AI 二次解读层上线（可选）** — 在不改变 A 股 `cn_preopen_v1` 规则型 `rank / score` 主排序的前提下，Scanner 现在可以对前 N 名 shortlisted candidates 追加 bounded AI interpretation：补充 `AI summary / opportunity type / AI risk interpretation / AI watch plan`，并在 review 数据就绪后生成轻量 `AI review commentary`。AI 默认通过 `SCANNER_AI_ENABLED=false` 保持关闭；即使 provider/model 不可用，Scanner 仍会继续输出原有规则型结果，并在 `/scanner` 的候选详情与运行时诊断中明确展示 `disabled / unavailable / failed / completed` 等状态与 fallback 信息。
- 🇺🇸 **Market Scanner 新增 US profile（`us_preopen_v1`）** — 在保持 A 股 `cn_preopen_v1` 和 Phase 1 AI interpretation 语义不变的前提下，Scanner 现在新增独立美股 profile：`us_preopen_v1`。首版美股 scanner 复用现有 run persistence、today/recent watchlist、review/quality、schedule、notification 与 diagnostics 基建，但使用单独的 local-first US universe（`LOCAL_US_PARQUET_DIR` 优先，`US_STOCK_PARQUET_DIR` 兼容回退，再回退本地 `stock_daily`）、独立的 deterministic liquidity/trend/momentum/benchmark-relative/gap-context scoring，以及更符合 pre-open / gap risk / open confirmation 语义的 reasons、risk notes 与 watch context。Web `/scanner` 现已支持显式切换 `A股 / 美股` 市场与对应 profile，并在当前结果、近期 history 与导出摘要里保留明确的 market/profile badge；若 live quote 不可用，美股 scanner 仍会继续工作，只在运行时诊断与风险文案中提示其更偏历史视角。

### 修复

- 🧭 **WS7 legacy strategy compatibility deprecation-only pass** — `src/agent/strategies/*` 现已在模块文案中明确标记为 deprecated compatibility wrapper，并给出 canonical `src.agent.skills.*` 替代导入路径；隐藏兼容接口 `/api/v1/agent/strategies` 继续保留原有返回体与字段，但现在会显式返回 deprecation headers，引导客户端切换到 `/api/v1/agent/skills`；`ChatRequest.skills` 也补充了 `strategies` 请求别名已弃用但仍受支持的说明，同时把少量 in-repo 注释/测试措辞从 strategy-first 收口到 skill-first 语义。
- 🧹 **WS7 有界 cleanup/deprecation 首轮收口** — `scripts/smoke_backtest_standard.py` 与 `scripts/smoke_backtest_rule.py` 不再回跳到 clean-checkout 缺失的根目录 smoke helper，而是直接使用仓库内已提交的 canonical backtest smoke 实现；`main.py` 中的 `--webui` / `--webui-only` 继续保留兼容，但 CLI help 与启动日志现在都会明确提示它们已弃用，并给出 `--serve` / `--serve-only` 替代路径；`webui.py` 也改为显式兼容入口提示，运行时直接输出当前推荐命令而不改变现有启动语义。
- 🧩 **WS6.2 设置页 advanced/domain 重复文案继续收口** — `SettingsPage` 进一步去掉了 advanced/domain 区里的重复说明：AI 域中 backtest 继承路由摘要不再重复展示两次，advanced 域“首页运行时执行摘要可见性”不再出现内外层重复标题，移动端分类抽屉也移除了与 domain 选择层重复的引导文案；所有保存、路由、Provider、destructive action 与 admin/user 语义保持不变。
- 🧭 **WS6 控制面设置页一轮减负收口** — `/settings/system` 现已把执行日志入口、运行时缓存重置和工厂重置统一收进默认折叠的“维护与日志”面板，避免低频/破坏性动作继续和日常配置并排常显；运行时缓存重置、工厂重置以及 typed confirmation 语义保持不变，同时移除了“控制台偏好”区里重复的 admin/logs 入口提示，减轻设置页结构密度但不改变现有后端语义。
- 📱 **Web 移动端导航与核心页面响应式稳定性收口** — 修复移动端共享导航抽屉在点击汉堡菜单后短暂打开又立即关闭的问题：`Shell` 现在只会在真实路由切换或断点变化时重置移动抽屉状态，并跳过首次挂载时的误关闭；移动导航抽屉同时改为显式关闭优先，不再响应 backdrop 点击，从而规避触摸设备上的 ghost click / delayed outside-click 误触。Scanner 短列表卡片也同步收口了小屏布局：分数区、CTA 按钮组和历史统计在窄屏下会自动纵向/双列重排，减少挤压与错位；Backtest 页面则补上了小屏 toggle 分组、结果页 tabs 横向滚动和 hero action 换行规则，降低移动端横向裁切和触达成本。
- 🧭 **Web 设置/持仓/管理员日志完成一轮高信号减负与移动端收口** — Settings 页现在把分类导航在移动端收进折叠面板，并把 `base / system / ai_model / data_source / notification` 这些已有高层编辑入口的原始配置项统一下沉到“原始配置与兼容层”，减少默认暴露的低价值字段；Portfolio 页把手工录入、CSV 导入和流水审计改成渐进展开区块，小屏表单同步改为单列优先，降低页面首屏噪音与长滚动负担；管理员日志页则改为响应式筛选工具栏，并去掉移动端堆叠场景下的双重滚动面板，提升窄屏可用性。
- 🛡️ **Market Scanner A 股运行时韧性修复** — Scanner 不再把 `Tushare stock_basic` 权限作为 A 股 universe 的硬依赖，新增 `SCANNER_LOCAL_UNIVERSE_PATH` 本地 universe cache，并在 `Tushare -> 本地数据库/内置映射 -> Akshare` 之间做显式 fallback。A 股全市场快照也改为保留 `Akshare(东财 -> 新浪) -> efinance -> local_history_degraded` 的尝试链路；失败运行会持久化 `tushare_permission_denied / akshare_snapshot_fetch_failed / efinance_snapshot_fetch_failed / no_realtime_snapshot_available` 等更明确的 reason code，`/scanner` 页面同步展示 universe/snapshot 来源、尝试链路和是否启用 degraded mode，不再只看到模糊的 `no_supported_fetcher`。
- ⏱️ **Intraday replay/session contracts now respect explicit caller classification** — `_build_time_context()` 在有标准化 `session_type` 入参时会优先保留调用方已确认的 `intraday_snapshot / last_completed_session` 语义，不再在回放、历史重建或测试场景里被当前墙上时钟二次改写；默认实时推导路径仍保持不变。
- 🧹 **Baseline cleanup: generated artifacts and stray helper entrypoints removed from the main repo surface** — 停止把 `backtest_outputs/` 下的生成产物、根目录审计草稿和设计参考残留继续保留在主仓默认面；Execution Trace/P3 辅助脚本统一收口到 `scripts/`，根目录不再散落一次性工具入口，减少检索噪音与误导性“看起来可直接运行”的历史残留。
- 🌐 **Proxy config path simplified to one authoritative runtime shape** — `setup_env()` 现在会统一把兼容的 `USE_PROXY/PROXY_HOST/PROXY_PORT` 归一到标准 `HTTP_PROXY/HTTPS_PROXY`，`main.py` 与 `test_env.py` 不再各自维护重复代理注入逻辑；`.env.example` 与 FAQ 也同步改为优先推荐标准代理变量。
- 🧭 **Ask Stock nav now follows actual runtime availability** — Web 侧栏不再默认永远展示 `/chat`；只有 Agent 运行时确实可用时才暴露该入口，减少“入口在、能力却未启用”的产品噪音，同时保留直接访问和已有会话场景的兼容性。
- 🧭 **Backtest P6 决策支持增强以 frontend-first 方式落地** — 在继续保持 `BacktestService` / `RuleBacktestService` 分工、现有 status/cancel/export/diagnostics 契约与 P5 结果页结构不变的前提下，Deterministic Backtest 新增了更强的比较、报告与策略迭代能力。结果页 `历史结果` tab 现在支持以当前运行为基线勾选最多 3 条已完成运行做 side-by-side comparison，并统一展示总收益、相对基准、最大回撤、交易次数、胜率、期末权益和关键策略参数，同时对日期区间、费率/滑点或 benchmark 不一致给出公平性提醒。图表工作区也继续收口为更偏决策支持的三层结构：主图保留策略/基准/买入持有，第二图优先展示回撤，第三图可在相对基准、日盈亏和仓位行为之间切换。`参数与假设` tab 新增受控 `Scenario Lab`，为已支持的 MA/MACD/RSI 等规则策略提供轻量参数变体、benchmark 模式与 fee/slippage/lookback 场景对照；`概览` tab 则新增 Markdown/HTML 决策摘要导出，并把 recent draft 与具名 preset 复用链路接回 `/backtest` 配置页，减少重复配置成本。
- 🧭 **Backtest P5 Web 可用性收口** — 在不改动 `BacktestService` / `RuleBacktestService` 现有职责与 API 契约的前提下，`/backtest` 与 `/backtest/results/:runId` 这轮主要围绕用户侧可用性做收口：规则回测结果页现在会持续展示运行状态卡，并使用轻量 `status` 轮询串起 `parsing / queued / running / summarizing / completed / cancelled / failed`；可取消阶段明确暴露取消入口，终态后继续保留 CSV / JSON 导出。结果首屏优先展示总收益、相对基准、最大回撤、交易次数、胜率与期末权益，`execution_trace` 默认改为“关键节点”视图并支持完整轨迹切换；Historical Evaluation 也把 `LocalParquet` / fallback 的含义改为更易懂的用户文案，并把 `requested_mode / resolved_source / fallback_used` 下沉到可展开的诊断区。
- 🚦 **Backtest P4 规则回测状态/取消与真实 uvicorn smoke 验证补齐** — 规则回测新增 `GET /api/v1/backtest/rule/runs/{run_id}/status` 与 `POST /api/v1/backtest/rule/runs/{run_id}/cancel`，后台任务现在会在 parsing / queued / running / summarizing 各阶段尊重取消状态，避免异步任务被取消后又继续落结果。新增根目录 `test_backtest_basic.py`、`test_backtest_rule.py` 和更新后的 `test_backtest_run.py`，统一使用临时 uvicorn、临时数据库、临时 `LOCAL_US_PARQUET_DIR` fixture 做自动 smoke，并继续验证 `execution_trace` CSV/JSON 导出。
- 🛠️ **Backtest P3 集成补线并恢复端到端可运行性** — 标准历史分析评估接口重新完整绑定到 `BacktestService`，补回 `/api/v1/backtest/samples/clear` 与 `/api/v1/backtest/results/clear` 契约；规则回测接口继续由 `RuleBacktestService` 负责，并重新接通 `execution_trace` 返回、CSV/JSON 导出、`parse_and_run_automated` / `run_backtest_automated` 自动化入口及历史运行回补 trace。与此同时，本地美股 parquet 的读取优先级已明确收口为 `LOCAL_US_PARQUET_DIR` 优先、`US_STOCK_PARQUET_DIR` 兼容回退，并补充了标准/规则 API smoke 脚本与 backtest 专项说明文档。
- 📊 **WolfyStock P3 新增本地 P2 报告生成器** — 新增 `src/services/wolfystock_p3_report.py` 与 `scripts/run_wolfystock_p3.py`，可直接读取本地 P2 产物目录中的 `runs/`、`sensitivity/`、`compare/` 与 `run_summary.json`，聚合 symbol / strategy KPI、生成自然语言总结、导出 markdown / JSON / CSV，并输出 equity curve、sensitivity heatmap、compare KPI 图表。整个流程只依赖本地 P2 输出，不访问任何外部行情源；`--dry-run` 模式会把结果写入临时目录，仅用于验证流程与日志。
- 🧪 **WolfyStock P2 新增本地 US parquet 服务器批跑器** — 新增 `src/services/wolfystock_p2_runner.py` 与 `scripts/run_wolfystock_p2.py`，用于在服务器上直接读取 `LOCAL_US_PARQUET_DIR` / `US_STOCK_PARQUET_DIR` 下已有的美股 parquet 数据，按 symbol 批量执行 deterministic baseline 回测、MA/RSI/MACD 敏感性分析、compare 聚合与 AI summary 生成，并将产物统一落到 `backtest_outputs/p2/`。流程默认只处理本地存在的 parquet 文件，缺失 symbol 会跳过并告警，不会尝试在线下载行情；同时提供 `--dry-run` 以便在无真实回测执行时验证批处理、输出路径和汇总逻辑。
- 🧾 **Deterministic backtest 新增完整 Execution Trace 导出与自动验收脚本** — 规则回测服务现在会基于已持久化的 `audit_rows`、`execution_model`、`execution_assumptions` 和解析假设，组装 stored-first 的 execution trace，并在结果详情中返回 `execution_trace`。新增的 Python 导出方法会输出中文可读的 CSV / JSON，其中包含 `买/卖/skip`、`fallback`、`assumptions/defaults`、`position`、`cash`、`total assets` 等字段；同时新增 `scripts/auto_trace_check.py`，可直接对导出的 trace 自动执行验收检查并输出 `# / 验收项 / 检查结果 / 备注` 报告。为便于 Python 自动化，还补充了 `run_backtest_automated` / `parse_and_run_automated`，在不改动现有 API 默认确认语义的前提下，允许脚本侧跳过 UI 确认流程发起 deterministic backtest。
- 🧭 **Deterministic 策略确认页与结果页的 canonical spec 文案已对齐** — `/backtest` 的确认页与 `/backtest/results/:runId` 现在会使用同一套 strategy inspectability 词汇来描述已识别策略：`策略族 / 规格来源 / 归一化 / 实际执行内容` 等核心概念不再在跑前跑后分别使用内部 code 或不同标题。结果页参数标签也新增与确认页同口径的“实际执行内容”摘要，并把原先偏原始的“策略输入与解析 / 解析警告”调整为更一致的“原始输入与解析 / 默认补全与提醒”，减少用户在确认前后阅读到不同策略说明的割裂感。
- 🔎 **Deterministic 回测前确认区改为优先展示 canonical strategy_spec 与字段级来源标记** — `/backtest` 的确定性策略确认区现在会把“实际执行内容”作为默认可见区块，直接展示当前 canonical `strategy_spec` 的 family、来源、归一化状态和关键执行字段，减少用户必须点开细节才能知道“系统到底会执行什么”的不透明感。关键执行字段还会附带轻量 provenance 标记，用来区分 `显式结构化 / 默认或推断 / 兼容 setup` 三类来源。原有 `parseWarnings` 也不再只藏在次级 disclosure 中，而是和 assumption groups 一起归到“默认补全与提醒”层，与“不支持项 / 改写建议”分开显示，更清楚地区分显式结构化字段、系统补全假设和当前不会执行的扩展部分。
- 🧩 **Deterministic strategy_spec 归一化改为优先保留显式结构化字段** — 自然语言策略解析后，周期定投与已支持的指标型策略在再次归一化时，现在会优先沿用已有 `strategy_spec` 中明确给出的 `signal / capital / order / schedule / costs` 等结构化字段，而不是被旧的 `setup` 默认值静默覆盖。同时规范化后的 `strategy_spec` 会附带统一的 `support` 元信息与 `strategy_family / max_lookback`，让 NLP 解释结果与后续 deterministic 执行之间的契约更可检查、更稳定。
- 🧱 **Deterministic strategy_spec 对已支持 family 改为输出更稳定的 canonical shape** — 当前已支持的 `periodic_accumulation / moving_average_crossover / macd_crossover / rsi_threshold` 现在会通过 family-specific payload builder 输出规范化后的 `strategy_spec`，只保留 deterministic 引擎真正支持的字段集合，并对 legacy `setup` 输入继续做兼容归一化。这让已支持 family 的结果不再依赖松散 dict 合并保留任意附加键，降低 NLP 解释层与执行层之间的结构漂移。
- 🔗 **Deterministic strategy_spec 已支持 family 契约在 API schema 与前端类型上对齐** — 规则回测 API 现在会对 `parsed_strategy.strategy_spec` 的已支持 family 使用显式 schema（`periodic_accumulation / moving_average_crossover / macd_crossover / rsi_threshold`），结果响应不再只暴露为宽泛 dict；前端共享类型也同步对齐为 family union，并继续保留 generic fallback 兼容未完全结构化或 legacy payload。
- 🧭 **Deterministic `parsed_strategy` 请求兼容归一化规则更明确** — 规则回测服务现在会在请求侧先对 `parsed_strategy.setup` 与 `parsed_strategy.strategy_spec` 的已知兼容字段做 camelCase / snake_case 归一化，再进入 family-specific 规范化；当顶层 `strategy_kind` 缺失时，也会优先参考显式 `strategy_spec.strategy_type`。对于不属于当前支持 family 的结构化输入，generic fallback 会继续保留原始自定义字段，而不是意外漂移成已支持 family 形状。
- 🕰️ **Deterministic 历史回放改为 stored-first replay，legacy fallback 显式隔离** — 规则回测历史详情与历史列表现在会优先从已持久化的 `summary.metrics`、`summary.visualization.audit_rows`、`summary.visualization.comparison` 以及已存储的日级序列中重建结果，不再让旧的 row columns 或隐式重算路径覆盖已有存储结果。只有旧运行缺少这些持久化字段时，才会进入明确命名的 legacy fallback 分支补建 audit / daily / exposure 数据，缩小 freshly completed run 与 reopened historical run 之间的口径漂移。
- 📈 **Deterministic benchmark / buy-hold 对比口径改为单一持久化 comparison payload** — 规则回测现在会把 `benchmark_curve / benchmark_summary / buy_and_hold_curve / buy_and_hold_summary` 与对应 KPI returns 一起收口到 `summary.visualization.comparison` 作为持久化真源。结果详情与历史读取在该 payload 存在时会优先使用它，避免 KPI、图表与历史回放各自从不同字段重新推导。对于外部基准不可用的场景，系统会显式持久化 `unavailable_reason` 并返回 `null` 的 benchmark KPI，而不是伪造收益值；同标的 buy-hold 仍按同一 run window、同一 close 口径保留。
- 🔌 **Deterministic 结果详情 API 统一公开 `auditRows` 字段名** — 规则回测服务内部仍以存储载荷里的 `summary.visualization.audit_rows` 作为审计台账真源，但 `/api/v1/backtest/rule/runs/{run_id}` 等 API 响应现在会把该字段稳定序列化为公开契约 `auditRows`，避免新运行在原始 JSON 中只能看到 `audit_rows`、前端再被动 camelCase 转换的隐式差异。CSV 导出与结果详情继续共用同一份已持久化 ledger。
- ⚙️ **Deterministic backtest 执行模型收口为结构化配置** — 规则回测现在会把执行语义持久化为结构化 `execution_model`，明确记录 `signal_evaluation_timing / entry_timing / exit_timing / entry_fill_price_basis / exit_fill_price_basis / fee_model / slippage_model / market_rules`，并继续派生旧的 `execution_assumptions` 兼容视图。引擎内部也改为优先围绕这份结构化配置执行与持久化，历史运行若还没有新字段则会从旧的 assumptions 回推兼容配置，避免结果解释口径漂移。
- 🧾 **Deterministic backtest audit ledger 持久化收口为单一真源** — 规则回测完成后现在会把日级 audit ledger 作为结构化结果的一部分持久化保存，字段口径统一收口为 `date / symbol_close / benchmark_close / position / shares / cash / holdings_value / total_portfolio_value / daily_pnl / daily_return / cumulative_return / benchmark_cumulative_return / buy_hold_cumulative_return / action / fill_price`，并继续保留信号摘要、手续费、滑点、drawdown 与 unavailable 原因等可审计字段。结果页读取与 CSV 导出在存在存储 ledger 时会直接复用这份持久化数据，不再走另一条临时重建路径；历史结果回放也保持与当前运行一致的 stored-ledger 读取语义。
- 🗂️ **Deterministic 结果页改为“首屏看图 + 深信息入 tabs/collapse”** — `/backtest/results/:runId` 不再把日级详情、审计表、交易表、参数快照、benchmark 说明、执行假设和历史列表继续纵向常驻堆叠在默认页面流里。结果页首屏现在只保留顶部摘要 / 操作、KPI 和统一 chart workspace；日级详情改为跟随 hover 的浮动明细卡，`审计明细 / 交易记录 / 参数与假设 / 历史结果` 则收进专门标签页，首屏回到以图表分析为中心的 JoinQuant 风格。
- 📊 **Deterministic 结果页首屏进一步压缩为 compact dashboard hero** — 结果页这次继续从“几个独立高 section 纵向堆叠”收敛为“一个紧凑主舞台”：顶部说明换成更薄的 top bar，KPI 改成更低高度的关键指标摘要（总收益 / 年化 / 最大回撤 / 夏普 / 基准 / 超额），统一 chart workspace 也把主图 / 日盈亏 / 仓位 / brush 一路压到更紧的 `220 / 72 / 56 / 40px` dense 比例，并同步缩短 panel 间距，首屏更像一个协调的 dashboard，而不是继续依赖长滚动阅读。
- 🎯 **Deterministic hover 明细改为真实跟随型 tooltip** — 结果图里的当日详情不再固定钉在右上角角落，而是继续复用同一个 `hoverIndex / hoveredRow`，并额外根据当前 hover 的图表几何实时计算 tooltip 的 `left/top`：默认贴近 hover 点右下侧，接近边缘时再左右 / 上下翻转，在 chart workspace 内以真正跟随 cursor / crosshair 的浮层展示。
- 📐 **Deterministic 结果页引入共享 density 比例系统** — `/backtest/results/:runId` 现在显式使用 `comfortable / compact / dense` 三档 density 统一驱动 header、KPI、chart panel、legend、brush、tooltip 和间距，不再让图表高度、文字大小和 tooltip 尺寸各自独立收缩，缩放到更小浏览器时也能保持整页比例协调。
- 🧾 **Deterministic hover tooltip 改成稳定的 compact chart tooltip 布局** — hover 明细不再复用通用 audit-grid，而是切到专门的 label/value 双列 tooltip 布局：主字段稳定对齐、日期与数值避免尴尬断行，长文本进入可换行的全文区，并用固定 max width / max height + 内部滚动避免内容继续溢出卡片。
- 🧭 **Deterministic Backtest 正式切成两页式产品流** — `/backtest` 不再同时长期承载参数输入、策略确认和 full-width 结果分析，而是收口为确定性回测配置页：负责普通/专业两种配置体验、策略解析确认、提交运行和历史入口。完整结果分析现统一迁到新路由 `/backtest/results/:runId`，并由结果页负责 run status / polling、KPI、全宽 chart workspace、审计表、交易表、参数快照与基准说明。
- 🔁 **Deterministic 运行与历史统一走同一个结果页路径** — 从 `/backtest` 发起 deterministic run 后会直接导航到 `/backtest/results/:runId`；配置页里的历史记录点击后也不再把大图分析回放在当前页，而是打开同一个结果页路由。当前运行和历史运行因此真正复用同一条 `fetch run -> normalize result -> render workspace` 链路，不再保留旧的 config-page chart glue。
- 🧱 **`/backtest` 确定性结果页改为 normalized-result 单一渲染架构** — Deterministic Backtest 的结果查看链路这次不再继续叠补旧 viewer，而是直接重写为 `normalizeDeterministicBacktestResult -> DeterministicBacktestChartWorkspace -> KPI / audit / trade-event tables` 的单向数据流。当前结果与历史结果共用同一个 workspace，主图、每日盈亏、仓位和底部 brush 都只读统一 `normalized rows`，避免旧 deterministic chart glue 在 hover、visible window 和空图状态之间继续漂移。
- 🧭 **`/backtest` 确定性结果图改为统一多 panel viewer** — Deterministic Backtest 的结果区不再直接挂三张独立 chart card，而是改成单一联动图表容器：内部纵向堆叠 `累计收益率 / 每日盈亏 / 仓位·买卖行为` 三个 panel，并由同一个 hover 状态、可见区间和底部 range brush 统一驱动。当前结果与历史回测记录也继续共用同一套 viewer，从存储的结构化 timeseries 与 audit rows 动态重建，而不是走分散的图表实现或静态图像。
- 🔎 **`/backtest` 结果区升级为可核查 / 可联动 / 可复盘的单一结果系统** — Deterministic Backtest 现在把日级审计账本持久化进结果记录，并用同一份结果数据驱动 KPI、联动三图、悬停当日详情、日级审计表与历史记录重建。结果区固定为 `累计收益率 / 每日盈亏 / 仓位·买卖行为` 三张联动图，新增共享 hover 检查、范围选择器（全部 / 近3个月 / 近1个月 / 自定义拖动）和 CSV 审计导出；打开历史回测记录时，也会直接从存储的结构化 timeseries 与 audit rows 动态重建图表和对账视图，而不是依赖静态图像或分散重算。
- 📊 **`/backtest` 确定性回测新增可配置基准与更清晰的三图结果区** — Deterministic Backtest 现在支持 `无基准 / 当前标的买入并持有 / 沪深300 / 中证500 / 纳指100 / QQQ / 标普500 / SPY / 自定义代码` 的基准选择，并按市场默认自动回退为更合适的对照线；结果区也固定收口为 `累计收益率 / 每日盈亏 / 仓位·买卖行为` 三张图，统一按容器宽度调整高度、刻度、marker 密度和终点标签，减少右侧结果面板在桌面缩放下的文字重叠与图表拥挤。
- 🧭 **`/backtest` 普通模式改为弹性双栏引导工作区** — Deterministic Backtest 的 `Normal Mode` 不再是旧版窄侧栏，也不再是居中的窄单栏，而是改成吃满内容区的弹性双栏：左侧是更宽的引导式主工作窗口，右侧是随步骤变化的预览 / 状态 / 结果窗口；图表与结果区会跟随右侧容器宽度自适应，基础参数、策略确认和运行阶段也重新对齐到这一套 split workspace 模型。
- 🧭 **`/backtest` 新增 Normal / Professional 双交互模式** — `/backtest` 现在默认使用 `Normal Mode`：左侧控制面板按步骤只显示一个主步骤卡片，减少一次性暴露的复杂度；切换到 `Professional Mode` 后则展开完整控制面板，保留高级用户所需的全部控制。Deterministic Backtest 与 Historical Evaluation 都沿用同一套模式切换与右侧显示板设计。
- 🧭 **`/backtest` 统一为单一 left-control / right-display 交互模型** — Deterministic Backtest 与 Historical Evaluation 现在共享同一套 Backtest V1 设计系统：左侧固定控制面板负责参数、确认与执行，右侧显示板负责解析预览、结果、图表、表格与历史。原先残留的 workbench/IDE 式分区语言被进一步收口，stepper 也改为真实驱动左侧工作流，不再只是装饰。
- 🧭 **`/backtest` 简化为更清晰的 Backtest V1 result-first 页面** — 移除过重的 rail/workbench chrome、上下文条和多区域 shell，把 `/backtest` 收口为单一主页面流：`Header -> Base Params -> Strategy Input -> Result Metrics -> 主图 -> Daily Return -> Exposure -> Inspection -> Trade Log -> History`。新的布局默认以确定性策略回测为主，图表保持全宽且不再与 summary 侧摆混排，页面整体更像一张严肃的研究/回测页，而不是半完成的 IDE。
- 🧭 **`/backtest` 重构为响应式 workstation 框架** — Backtest 路由现在使用真正的 route-scoped rail / stage workbench shell，并把 authoring、results、audit 接入可重排的响应式布局；同时移除此前主要依赖 centered max-width 的页面行为，让结果区在桌面端随视口真实扩展与重排，而不是整体像居中页面一样被浏览器缩放。
- 🧭 **`/backtest` 打磨为更完整的 in-app Backtest Workbench** — 在保留现有功能和执行语义不变的前提下，`/backtest` 继续沿用 route-scoped workbench shell，并把页面层级明确收口为 `authoring/setup -> results workspace -> audit/history`。这轮主要不是加功能，而是让结果区成为视觉中心：历史评估与确定性策略回测都新增了更清晰的 workbench section hierarchy、状态 telemetry、结果区强调和次级审计区；确定性 flow 的 step panel、改写提示和结果刷新也改为更平滑的轻量过渡，减少此前“很多卡片机械堆叠、状态硬切换”的感觉。
- 🧭 **修正 `/backtest` 的真实桌面宽度瓶颈** — 这次不再继续堆叠 Backtest 自身的 max-width hack，而是直接放宽了上层 `Shell` 中真正限制内容宽度的 `shell-content-frame`，并只对 `/backtest` 路由加上专用 modifier。此前许多 backtest 页内的“加宽”规则之所以视觉效果有限，是因为父层内容框先被 `layout-page-max` 截断；修正后，Backtest workbench 的更宽画布和下方结果区终于能够真正继承到可用桌面宽度。
- 📏 **Backtest workbench 画布与分析区进一步放宽** — `/backtest` 的专用 workbench shell 继续扩大了 desktop 下的实际可用画布，`backtest-workbench-main`、结果卡与历史卡都采用了更激进的宽度策略和更紧的横向 padding。setup/authoring 仍保持相对克制，而结果、图表、检视、trade log 和 history 明显获得更多横向空间，使页面更少像中间内容条，更接近真正的回测分析画布。
- 🧪 **`/backtest` 切换到专用 workbench page shell** — Backtest 不再继承普通页面的 `workspace-page` 文档式内容壳层，而是使用 route-scoped 的专用 workbench page shell。该 shell 为 `/backtest` 单独定义了更宽的 page-level canvas、header 区和 main workspace 区，同时保留 setup/authoring 区的可读宽度与结果区更宽的研究视图，使桌面端更接近独立回测工作站，而不会影响应用中的其他页面。
- 🛠️ **Backtest 页面回退为稳定的连续页流，并保留更宽的结果区** — 修复了此前桌面 workbench 实验带来的 step 按钮拥挤、setup 区不稳定和 boxed zones 互相抢宽度的问题。Backtest 页面现在重新使用单一连续页面流；上方 guided flow / confirmation / run 卡片回到更稳的标准宽度，而结果、图表、检视和历史区继续使用更宽的 section 级宽度策略，在不破坏控件布局的前提下保留研究工作区的横向空间。
- 📊 **确定性策略结果区升级为 full-width research layout** — Deterministic Strategy Backtest 现在把结果区重排为更接近研究终端的全宽布局：先显示核心指标，再用全宽主图展示策略 vs 同标的 buy-and-hold 的归一化净值对比，并补充两张辅助子图用于检查 `Daily Return` 与 `Exposure`。策略摘要、执行 / 基准检视和结果解读则下沉到图表下方，避免继续压缩主图宽度；Trade log 仍保留为底部审计区。
- 🎯 **确定性对比图强化策略 / 基准层级可读性** — Deterministic Strategy Backtest 的主对比图现在把 `Strategy` 线提升为更亮、更粗的主视觉层，而 `Buy & Hold` 基准线则改成更暗、更细的次级虚线；同时把图例收口为 `Strategy / Buy & Hold / Buy / Sell` 四个短标签，并为买卖点使用更容易区分的形状与终点标签，降低暗色背景下两条主线过于接近的问题。
- 🖥️ **Backtest 页面切换到更宽的 desktop research workspace** — Backtest 页面现在使用更积极的 desktop 宽度策略，明显减少大屏下两侧空白带；Deterministic result 区的 card 也单独采用更宽的 workbench 布局，让主图和子图不再像嵌在保守居中列里的“小卡片”，而更接近真正的量化研究工作区。
- 🧠 **确定性策略确认页更少退化成 generic fallback** — Deterministic Strategy Backtest 现在会优先保留已识别的核心策略意图，即使整条自然语言还不能执行，也会把 `detected_strategy_family / core_intent_summary / unsupported_extensions / interpretation_confidence` 作为结构化确认信息返回。像“均线交叉 + 止损扩展”“MACD + 参数优化”“RSI + 分批建仓”这类输入，不再主要显示成空的 `rule_conditions` 回退，而会更明确地区分“已理解的主策略”与“当前不支持的附加约束”，并据此生成当前可执行的改写建议。
- 🧭 **确定性策略确认步骤层级与改写交互进一步收口** — Deterministic Strategy Backtest 的确认页现按 `状态 -> 解析策略 -> 改写建议 -> 默认值 -> Warnings` 收口展示，减少重复解释层；当输入当前不支持时，系统会以更紧凑的方式显示 supported portion、rewrite suggestions 与 grouped assumptions。点击建议改写后会直接回填策略文本、返回策略步骤，并显示轻量“已应用建议改写”提示，方便用户重新解析继续。
- 📐 **确定性策略回测扩展到首批技术策略家族** — Deterministic Strategy Backtest 现在通过同一条 `natural language -> normalized strategy_spec -> deterministic execution` 链路正式支持 `均线交叉 / MACD 交叉 / RSI 阈值` 三类单标的、多头、单持仓策略。解析确认区会显式区分 `可执行 / 含默认假设 / 当前不支持`，并把默认参数与执行假设以结构化方式返回；后端 deterministic engine 则在不新增第二套执行管线的前提下，复用现有结果 contract 输出真实指标、权益曲线与交易明细。
- 🧭 **确定性策略确认页补齐 unsupported 诊断与改写建议** — Deterministic Strategy Backtest 的 parse/confirmation payload 现在会额外返回更清晰的 `unsupported_reason / unsupported_details / supported_portion_summary / rewrite_suggestions / assumption_groups / parse_warnings`，用于说明系统已识别了什么、当前哪一部分不支持、以及如何把自然语言改写成当前可执行的 deterministic form。前端确认步骤同步改为紧凑展示这些信息，并支持一键把改写建议回填到策略输入框中继续解析。
- 🧭 **确定性策略回测重构为 guided step flow** — Backtest 页面中的 Deterministic Strategy Backtest 现改为默认的分步工作流：`Symbol -> Capital & Date -> Strategy -> Confirmation -> Run`。确认步骤会基于归一化 `strategy_spec` 展示更紧凑的结构化摘要，并显式区分 `可执行 / 含默认假设 / 当前不支持 / 结果已过期` 等状态；结果区则收口为指标摘要、策略规格、权益曲线和交易明细，运行历史下沉为次级区域。页面同时保留低强调的 `Advanced mode` 入口，用于后续扩展更专业的编辑路径。
- 🧩 **确定性策略回测引入首版受限策略规格（strategy spec）管线** — 中文自然语言定投策略不再直接依赖零散 `setup` 字段进入执行层，而是先归一为受限的 `strategy_spec` / 规则规格对象，再经过显式校验与默认值补齐后复用原有 deterministic backtest 执行链路。当前首版规格重点覆盖单标的区间定投家族（固定股数 / 固定金额、起止日期、执行频率、成交价格基准、现金不足处理、期末平仓、手续费 / 滑点），前端解析预览与执行说明也同步改为优先展示归一化后的策略规格，减少 one-off hardcoded 模板继续外溢为长期执行契约。
- 🧠 **确定性策略回测新增中文自然语言定投 MVP** — Deterministic Strategy Backtest 现在支持把一小类中文定投指令解析成结构化草稿，并在用户确认后复用原有 deterministic backtest 执行链路返回真实汇总、权益曲线和交易明细。当前优先支持“固定股数 / 固定金额、给定起止日期、按交易日买入、现金不足时停止”的单标的区间定投表达，例如“资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止”。
- 📈 **确定性策略回测 MVP 补齐日期区间驱动的真实结果链路** — Deterministic Strategy Backtest 现在支持显式 `开始日期 / 结束日期` 输入，并把日期区间贯穿到后端规则执行、结果 contract、前端汇总区、权益曲线和交易明细中。页面不再只依赖“最近 N 根 bars”近似窗口来回答策略盈亏问题，而是可以更直接地验证“在指定区间内，这套规则到底赚了还是亏了”。
- 🔎 **Historical backtest 补齐样本日期与定价来源透明度** — Historical Analysis Evaluation 相关响应现在会额外暴露 `latest_prepared_sample_date / latest_eligible_sample_date / excluded_recent_reason / excluded_recent_message / pricing_resolved_source / pricing_fallback_used`，用于解释“为什么样本只停在更早日期”以及“本次定价究竟用了 LocalParquet 还是回退到了 Yfinance/API”。Web 回测页同步在历史评估参数区增加一条轻量说明，直接展示最新已准备样本、最新可评估样本、未纳入较新日期的原因和实际定价来源。
- 🧭 **Backtest 历史评估页做第二轮中文化与减层** — 历史分析评估页改为更直接的 5 段流程：定位说明、参数与执行、运行概览、评估结果、运行历史。页面移除了单独的 `Methodology / Definitions` 解释层，运行时数据源元数据收口到参数区轻量 chips，概览区只保留一组主 KPI；同时把主要区块标题与关键指标统一成中文，减少中英混杂与重复说明带来的视觉负担。
- 🧾 **Backtest 历史评估页改为直接消费后端数据源元数据** — Historical Analysis Evaluation 现在直接读取后端返回的 `requested_mode / resolved_source / fallback_used` 并映射到页面中的 `Requested Mode / Resolved Source / Fallback Used`，不再把结果表行级 `marketDataSources` 聚合作为 summary-level 主来源；结果表本身仍保留行级 source 展示，便于审计单条样本。
- 🧪 **Backtest 页面信息架构拆分为两条清晰模块** — Web `Backtesting` 页面现严格拆为 `Historical Analysis Evaluation` 与 `Deterministic Strategy Backtest` 两个顶层 tab：历史分析评估区新增独立的 Header、Control Panel、Methodology / Definitions、Summary Strip、Result Table、Run History，并显式声明“不是完整组合/账户回测”；确定性策略区则重排为自然语言输入、解析预览、执行控制、结果区、历史区的 MVP 骨架。历史评估页同时新增数据源透明度占位与 best-effort 标签归一化，前端会优先把运行结果中的原始 source 映射为 `LocalParquet / DatabaseCache / YfinanceFetcher / ProviderAPI / MixedFallback`，在后端尚未把 runtime source metadata 注入所有 summary/run 接口前，先保证页面上可见且不打断现有流程。
- 🧾 **研究报告生成改为渐进式草稿体验** — 首页在异步分析启动后不再停留在泛化阻塞 loading，而是立即进入结构化“研究报告草稿”状态：后端任务队列通过 SSE 新增 `task_updated` 阶段事件并透出实时 `result`/执行摘要，前端据此按 `初始化 → 市场数据 → 信号分析 → 报告组装 → 收尾` 渐进填充报告章节，在失败时保留已呈现内容并提供重试入口，最终平滑切换到正式报告视图。
- 📱 **Web 工作区响应式与抽屉交互进一步收口** — 首页移动端不再保留会挤压主内容的历史侧区预览，档案抽屉改为更高效的纵向层级与主滚动区，首页主操作按钮统一高度/宽度策略并移除重复档案入口；同时补齐移动端与桌面端断点切换时的抽屉/档案状态复位，避免 viewport 来回切换后残留遮挡层或错位框架。
- 🚀 **Web 壳层切换为严格 SpaceX 设计纪律的研究工作区** — `dsa-web` 本轮不再保留“旧 dashboard 壳层 + 新皮肤”的混搭方案：主导航改为顶部极简 masthead + 移动端抽屉，历史分析从密集侧栏列表重构为独立档案抽屉与首页轻量工作区摘要，首页首屏改成面向研究流程的 command / archive / report 布局，登录页、启动加载页、报告生成态和共享按钮/输入/抽屉统一收口到黑底 + spectral white + ghost control 的受控极简语言；同时新增本地持久化“红跌绿涨 / 红涨绿跌”市场颜色约定，并同步应用到价格、涨跌幅与图表相关指标。
- 🛰️ **Web 产品体验重构为统一设计系统** — Web 端现在以统一的 SpaceX-inspired 产品设计语言驱动整个体验：Shell、侧边导航、登录/认证入口、启动加载、状态横幅、按钮/输入/表格/弹窗等共享原语统一改为克制的黑白谱系、DIN 风格排版和低噪声交互；首页、回测、持仓、管理员日志以及共用历史/任务/报告表面同步对齐，移动端抽屉和首屏节奏也一起收口，避免“局部页面重做、整体仍然混搭”的问题。
- 🧭 **回测域语义与工作区统一收口** — Backtest 现明确拆分为“历史分析评估”和“确定性规则策略回测”两套语义：历史评估统一把 `eval_window` 解释为 trading bars、`min_age` 解释为 calendar days；规则回测新增显式执行假设、buy-and-hold / excess return、交易审计字段与异步任务状态（`parsing / queued / running / summarizing / completed / failed`）。同时新增共享的本地美股 parquet helper，`stock_service`、历史评估 warmup / fill 路径和规则回测历史加载都统一优先读取 `US_STOCK_PARQUET_DIR`，缺失或异常时保留原有 API fallback 并输出明确日志。
- 📚 **Backtest 工作区补齐历史与重置操作** — Backtest 页新增可配置的样本准备范围（支持更大的历史样本数）、回测运行历史列表、按 symbol 查看历史结果的回放入口，以及样本清理 / 结果清理 / 样本重建的显式控制。页面现在能区分“准备样本”“重跑结果”和“清空存量记录”，不再把这些动作混成一个模糊的 force rerun。
- 📦 **Backtest sample warmup flow** — Settings/Backtest 页面新增显式“准备回测样本”动作：当历史分析不足以满足成熟窗口时，可先按股票代码补写可回测的历史分析样本到 `analysis_history`，再重新运行回测。该准备动作复用本地可用的历史行情数据作为输入，并保持回测主流程仍然只读取 `analysis_history` 作为候选源。
- 📊 **Backtest run diagnostics** — `POST /api/v1/backtest/run` now returns an explicit `no_result_reason` / `no_result_message` when it writes no rows, so a 200 response no longer looks like a silent success when the candidate set is empty. The existing optional `performance` 404 handling remains unchanged; the page can now explain empty runs as “no analysis history” or “insufficient historical data” instead of showing an unexplained blank state.
- 🧭 **AI Task Routing 行式收紧 + Data Source Library 校验状态显性化** — Settings 的 AI Task Routing 由“主卡 + 右侧卡组 + 内嵌多卡”进一步收紧为单一 surface 内的 3 条任务行，Analysis 行内直接展示主路由/备用路由和 Provider 覆盖，Stock Chat / Backtesting 以更短的次级行展示继承/覆盖状态与当前生效路由，减少大块空白和 card-in-card 视觉负担。Data Source Library 卡片保留能力标签，并把状态文案拆成“未配置 / 已配置待验证 / 内置可用”；当前没有复用现成后端连通性探活接口，因此第三方数据源先展示真实的 status-only“已配置，未做连通性验证”，不伪装成网络校验成功。
- 🧭 **Settings Task Routing 压缩布局 + Data Source Library 可用性表达增强** — AI Task Routing 调整为左侧 Analysis 主卡 + 右侧 Stock Chat / Backtesting 次卡的同屏布局，减少纵向空白并保留“编辑任务路由”主入口；Data Source Library 卡片补充能力标签（行情/基本面/新闻/情绪）和状态检查行，明确区分内置可用、凭据已配置可用于当前路由、等待凭据配置三类状态。数据源状态当前为基于现有配置/内置源能力的状态检查，不伪装成真实网络连通性探活。
- 🧭 **Settings AI/Data 信息架构对齐** — AI 区域移除独立“当前生效 AI 配置”顶层摘要块，把 Analysis / Backup / Stock Chat / Backtesting 的当前生效路由直接并入“任务路由”卡片，减少“先看摘要再滚去编辑”的重复路径；数据源设置同步重排为“数据路由 + 数据源库”两层结构，上层继续编辑 market/fundamentals/news/sentiment 的主备源顺序，下层以卡片展示 Alpha Vantage / Finnhub / Yahoo / FMP / GNews / Tavily / Local Inference 等源的凭据状态、内置可用状态和当前路由使用情况，让 Data Sources 与 AI Provider Library + Task Routing 保持一致的心智模型。
- 🧭 **AI Settings 摘要可读性与 Provider 级高级配置作用域收口** — “当前生效 AI 配置”从偏表格化的三列硬布局调整为更易扫读的紧凑摘要行，保留 Analysis / Backup / Stock Chat / Backtesting 与 Provider 覆盖信息但减少机械表格感；Provider 卡片的“管理高级配置”现在会以 provider scope 打开高级渠道编辑器，只显示当前 Provider 的渠道行并锁定新增预设，避免在单 Provider 编辑时继续看到其他 Provider 的无关渠道与全局 runtime 区块。全局“打开高级设置”入口保留为低优先级全量管理入口。
- 🧭 **GLM/Zhipu 路由保存与 AI 设置渐进式编辑收口** — 前后端模型校验新增统一 canonical identity 比较：`glm-4`、`openai/glm-4` 这类“完整 ID / 后缀 ID”会先归一到同一模型身份再做渠道声明校验，修复 GLM 渠道已显式声明 `glm-4` 且测试成功，但主任务路由保存仍被最终校验误拒的问题；同时 AI Settings 主页面改成“摘要卡片 + 抽屉编辑”的渐进式交互，任务路由与 Quick Provider API Key 均默认只展示状态/当前模型，编辑操作进入侧边抽屉，高级 Provider / Channel 配置继续下沉到独立抽屉，减少长表单在主页面直接铺开造成的视觉负担。
- 🧭 **AI Settings 主页面去重降噪** — 压缩 AI 主页面的说明性文案和重复区块，移除“高级配置”卡片里的逐 Provider 汇总网格与主页面重复提示，只保留一个低优先级的“打开高级设置”入口；高级渠道数量改由各 Provider 卡片直接展示，让页面主层级更明确地收敛为 `Task Routing -> Provider Library -> Advanced Config`。
- 🧭 **AI 路由模型来源收口 + Provider 默认/显式模型模式拆分** — 任务路由模型选项改为单一可信来源规则：`Provider 预设模型 + 已启用高级渠道显式声明模型 + 仍与前两类匹配的已保存路由模型`，不再从旧 `LITELLM_*` / 全局模型集合反向回填下拉选项，避免 GLM/Zhipu 仅声明 `glm-4` 时仍出现 `glm-5` 这类 phantom model。Analysis / Stock Chat / Backtesting 的路由编辑器新增“Provider 默认 / 自动”和“显式模型 ID”两层模式，Quick Provider 仅配置 API Key 时可先走 Provider 默认模式；高级渠道声明、自定义 Base URL/协议、runtime 参数继续保留在下沉的高级配置层。
- 🧭 **AI 测试与 fallback 语义对齐（GLM/Zhipu）** — 快速 Provider 测试现在会优先复用同 Provider 的高级渠道测试模板（协议/Base URL/首个声明模型），并补充“quick test 直连路径 vs advanced channel 测试路径”说明；GLM/Zhipu 快测失败时会给出引导到高级渠道测试的可执行提示。`LLMChannelEditor` 同步收口 fallback 校验语义：该字段仅接受当前运行时可访问模型（已启用渠道或可用直连 key），跨 Provider 容灾应配置在任务层备用路由。后端 `test_llm_channel` 对 `Empty response` 增加可操作诊断（模型权限/协议不匹配/解析失败等），不再只返回泛化错误。
- 🧭 **AI 设置改为任务优先工作流（Analysis / Stock Chat / Backtesting）** — 设置页 AI 区域新增“按任务配置模型”：Analysis 继续维护主/备路由；Stock Chat 与 Backtesting 默认继承 Analysis，并支持独立覆盖保存（分别写入 `AGENT_LITELLM_MODEL` 与 `BACKTEST_LITELLM_MODEL`）。同时“快速 Provider API Key 配置”升级为 Provider Library 卡片视图（Gemini / AIHubMix / OpenAI / Anthropic / DeepSeek / GLM/Zhipu），凭据就绪后即可进入任务模型选择，不强制先建渠道；高级 Provider/Channel 配置保留为可选层并下沉。
- 🔁 **直连 API Key 兼容链路补齐（最终校验层）** — 修复 Gemini 直连 API Key 模式在“备用路由保存”阶段仍被后端按“仅渠道声明”拒绝的问题。`SystemConfigService` 现已在最终运行时模型校验中统一接受“已启用渠道模型”或“匹配的 legacy 直连 API Key”两类能力来源（适用于 `LITELLM_MODEL / LITELLM_FALLBACK_MODELS / AGENT_LITELLM_MODEL / VISION_MODEL`），从而恢复“仅配置 `GEMINI_API_KEY` 也可保存 Gemini 主/备路由”的向后兼容行为；同时前端 AI 路由保存不再保留陈旧 fallback 列表，避免历史无效模型残留导致误报。
- 🔧 **AI 路由编辑器可选网关回归修复（凭据就绪作为唯一来源）** — 修复 Settings 中主/备网关下拉被错误禁用或无可选项的问题：网关选择器可用性与选项来源改为严格基于凭据检测结果（`AIHUBMIX_KEY(S)`、`GEMINI_API_KEY(S)`、`OPENAI_API_KEY(S)`、`DEEPSEEK_API_KEY(S)`、`ANTHROPIC_API_KEY(S)`），不再依赖 `LLM_CHANNELS`。当前行为为：已就绪 provider ≥1 时主路由可选，≥2 时备用路由可选；仅有 legacy `LLM_CHANNELS` 而无凭据时保持禁用并给出明确原因。此前 primary-only 保存修复（不向 `LLM_CHANNELS` 自动注入网关）保持不变。
- 🧭 **AIHubMix 路由可用性与问股路由说明增强** — AI 路由凭据识别补充 `AIHUBMIX_API_KEY(S)`，确保 AIHubMix 在凭据就绪时可直接进入主/备路由选择；模型编辑器补充 AIHubMix 专用提示与示例（支持手动模型 ID，如 `openai/gpt-4.1-free`、`openai/gpt-4.1-mini`），并保留预设 + 自定义双模式。设置页“当前生效 AI 配置”与“默认 AI 路由”区域新增问股路由说明，明确展示问股是“与分析共用”还是“使用 AGENT_LITELLM_MODEL 独立模型路由”。
- ♻️ **AI 备用路由可清空（primary-only 回归可用）** — AI 路由编辑器新增显式“清空备用路由”操作，支持将 `Backup Gateway/Model` 一次性重置为空；清空后保存会一致写入 `AI_BACKUP_GATEWAY=''`、`AI_BACKUP_MODEL=''` 并清空 `LITELLM_FALLBACK_MODELS`，避免残留 fallback 导致 primary-only 配置被校验拦截。
- 🧪 **AI 备用路由前置兼容性校验 + 渠道配置入口增强** — AI 路由编辑器在填写备用路由时新增前置兼容性检查：若备用模型未在“已启用渠道模型声明”中出现，会在保存前显示可执行错误并提供“前往配置渠道模型”入口，同时禁用保存按钮，避免提交后才被后端拒绝。AI 路由区也新增“配置 Provider/渠道 API”直达入口，并在高级区补充“渠道/API 层 vs 路由层”说明，降低“渠道配置入口隐藏”带来的排障成本。
- 🛠️ **AI 路由保存失败修复（primary-only 合法场景）** — Settings 的 `Save routing` 不再把“仅网关选择”自动注入 `LLM_CHANNELS`，避免触发后端 `LLM_<channel>_*` 完整渠道校验导致 `System configuration validation failed`。同时新增前端路由完整性校验：主路由必须“网关+模型”同时存在，备用路由必须“同时填写或同时留空”；当保存失败时会在 AI 路由区域展示可执行错误信息。primary-only（如 `AI_PRIMARY_GATEWAY=gemini` + `AI_PRIMARY_MODEL=gemini/...`，`AI_BACKUP_*` 为空）现在可稳定保存，并保持 `AI_PRIMARY_* / AI_BACKUP_* / LITELLM_*` 兼容同步。
- 🧭 **AI 路由设置可用性收口（网关-模型一致性 + 显式模式）** — Settings 的 `Default AI Routing` 继续做聚焦修复：当主/备网关未选择时不再展示残留模型值，避免“网关未配置但模型有值”的误导；主/备两侧模型输入改为显式双模式（`预设选择` / `自定义 ID`），并补充模式优先级与网关前置提示。Gemini 与 AIHubMix 路由均保持“网关特定预设 + 始终允许手输模型 ID”（例如 `gemini/gemini-3-flash-preview` 或 AIHubMix 目录模型）。保存后成功提示会明确回显 `Primary route / Backup route / Scope`，并保持 `AI_PRIMARY_* / AI_BACKUP_* / LITELLM_*` 兼容持久化。
- 🧠 **AI 设置信息架构重排（仅 AI 区域）** — Settings 的 AI 区域重构为四层：`Current Effective AI Route`（生效主/备网关与模型、配置状态）、`Default AI Routing`（唯一主工作流，主/备网关+模型可编辑）、`Provider Readiness`（凭据状态、预设模型、推断模型、自定义模型能力）和 `Advanced / Raw Compatibility`（折叠展示 legacy/raw 字段）。同时新增“网关-模型联动 + 手动模型 ID 输入”能力，支持 AIHubMix/Gemini 等场景下按网关快速选模型并自由输入自定义模型 ID，且保持 `AI_PRIMARY_* / AI_BACKUP_* / LITELLM_*` 兼容持久化不变。
- 🛰️ **新增管理员执行日志中心（D2）** — 后端新增结构化执行日志会话与事件存储（AI/数据源/通知分层），并提供管理员解锁后可访问的 `/api/v1/admin/logs/sessions` 与 `/api/v1/admin/logs/sessions/{session_id}` 接口；Web 端新增 `/admin/logs` 管理员页面与设置页入口，可按会话查看时间线，区分 `success / partial_success / timeout_unknown / failed / not_configured` 通知终态，并保持用户侧任务/报告页面简洁不暴露原始调试细节。
- 📚 **管理员日志可读层 + AI 默认路由选择（D2.1 / D3）** — 管理员日志列表与详情新增“执行摘要 + 叙述段落 + 关键徽标”，在保留原始事件时间线的同时，提升可读性（最终模型、数据源、回退、通知终态、主要失败原因一目了然）。设置页 AI 区域补齐“主/备网关 + 主/备模型”双层路由选择并持久化 `AI_PRIMARY_* / AI_BACKUP_*`，同时兼容同步到 `LITELLM_MODEL / LITELLM_FALLBACK_MODELS / LLM_CHANNELS`，避免“API 已配置但仍显示未配置”的误导。
- 🧭 **首页执行摘要可控 + 管理员系统动作链日志（D2.2）** — 新增系统配置 `SHOW_RUNTIME_EXECUTION_SUMMARY`（设置页“系统/高级”可视化开关），用于控制首页是否显示运行时执行摘要卡片；管理员日志中心新增“系统动作时间线”语义层，事件按 `category/action/target/status` 展示网关调用、模型尝试、数据源尝试与回退切换、通知通道尝试与终态分类，提升 Aihubmix→模型、GNews→Tavily 等链路排障可读性，同时保持管理员日志页独立可见、不受首页开关影响。

- 🧾 **完整 Markdown 报告结构去重与审计升级** — `report_markdown` 渲染改为严格四层：`Decision Summary -> Execution Plan -> Evidence -> Coverage / Audit`。决策层只保留“评分/建议/趋势 + 一句话结论”，执行信息合并到单一 `Execution Plan`，`Risks & Catalysts` 收敛为四组：`Bullish Factors`、`Risk Factors`、`Catalysts / Watch Conditions`、`Market Sentiment`，移除重复的 bullish/bearish/mixed 独立块。缺失字段展示同步改造为“表格内关键字段仅显示 `NA`、非关键缺失下沉到审计区”，并在审计区提供四类归因（`integrated_unavailable / not_integrated_yet / source_not_provided / not_applicable`）与 `High/Medium/Low` 接入优先级分组，提升 API 接入排期可执行性。

- 🧭 **报告页信息架构重排为“四层决策流”并下沉冗余指标** — `StandardReportPanel` 调整为 `决策摘要 -> 图表/会话指标 -> 执行与风险 -> 深度附录`：首屏仅保留股票名/代码、最新价与涨跌、综合评分、操作建议、趋势判断和一句话结论；执行区收敛为“关键动作/关键风险/观察 Checklist”三块；大体量技术/财务表、评分拆解、催化与情绪等信息下沉到默认折叠的附录 disclosure，减少重复结论与首屏噪音，同时保持 `VITE_REPORT_LEGACY_FALLBACK=auto` 兼容路径不变。

- 🛡️ **B3 受控弃用准备：报告渲染新增 legacy fallback 开关与契约观测** — Web 报告分支新增 `VITE_REPORT_LEGACY_FALLBACK`（`on/off/auto`）受控策略，`standard_report` 作为主路径，legacy 分支降级为兼容回退；同时补齐 `legacy_only` 契约测试、switch 分支测试与 fallback 观测日志（含 `payloadVariant / standardReportSource / mode`），为后续最终移除 legacy 路径提供可回滚保障。

- 🧭 **三主题侧栏语言重构 + 壳层间距与交互动效再抛光** — Web 端新增侧栏专用 token（nav 几何、icon 容器、激活指示、分隔线、品牌块边框/阴影、rail framing），并在 `Dark Terminal / Cyberpunk / Geek(DOS)` 里分别落地为交易终端、赛博控制轨、单色 DOS 控制台三种侧栏语言，不再是同构侧栏仅换色。`Shell` 与 workspace split/chat 布局同时改为独立 `layout-shell-gap/layout-content-gap`，提高侧栏与主内容之间的结构间距，减少“贴边拥挤”感；导航项/图标容器/激活条与主区卡片的 hover/active 过渡也统一到 motion token，交互更平滑而不拖慢响应。

- 📱 **移动端问股加载失败与侧栏遮挡问题修复（含主题/交互动效细化）** — `dsa-web` 的问股链路新增流式请求兼容处理：`chatStream` 统一携带 `credentials`/SSE header，移动端不支持 `ReadableStream` 或流式端点不可用时自动回退到标准 `/agent/chat`，并在会话加载失败、策略加载失败、网络失败时给出可执行的错误指引与重试入口。首页移动端侧栏移除了重复任务队列，只保留历史面板，避免遮挡历史分析列表。交互层补充了 Drawer/ConfirmDialog 的平滑开关场动画，Cyberpunk 主题进一步压暗并降低高亮粉色占比，保持三主题在背景、圆角、字体与控件语言上的差异化。

- 🧱 **主题系统升级为“独立家族皮肤”并清理残留硬编码颜色** — Web 端进一步把 `Dark Terminal / Cyberpunk / Geek(DOS)` 收口为真正的全局主题家族：Cyberpunk 仅保留黑 + 粉 + 紫（去除可见 cyan/teal/green 残留），Geek / DOS 收敛为黑白灰单色终端。新增并对齐 `chart-toolbar / input / focus-ring` 等全局 token，状态条、历史选择框、任务队列、自动补全 market/match badge、分页、确认弹窗、内联告警、通用按钮与 loading 图标等组件全部改为 token 驱动，不再依赖 `bg-cyan` / `text-green-*` / `border-rose-*` 这类硬编码 Tailwind 色值。

- 🌌 **Cyberpunk / Geek(DOS) 主题再次重绘 + 品牌化启动加载页落地** — `dsa-web` 赛博主题不再以青色为主，而是切换为黑底 + 霓虹粉/紫主导的高对比视觉（按钮、激活 pill、导航、进度条、图表 chrome 与卡片边缘发光同步偏向 pink/purple）；Geek / DOS 主题则从绿黑终端改为近黑白灰的单色复古样式（低饱和、平面化、弱发光、mono 字体主导）。同时新增品牌化首屏加载体验：`index.html` 提供预挂载 splash fallback，React 挂载后由 `BrandedLoadingScreen` 接管，中心使用 `/image.png` logo 动画并在关键初始加载完成后平滑淡出，避免慢网环境先看到半成品页面。

- 🎨 **Web 主题系统重构为硬约束 token contract + 图表/历史滚动隔离加固** — `dsa-web` 主题切换不再依赖零散颜色覆写，新增并落地 `--bg-page / --bg-sidebar / --bg-card / --accent-* / --chart-* / --font-* / --progress-*` 等核心 token，并让 Sidebar、Hero、卡片、按钮、badge、dropdown、设置面板、任务队列、图表 toolbar/legend/candle 配色统一走 token 渲染；`Dark Terminal / Cyberpunk / Geek(DOS)` 的背景、边框、发光强度、字体与图表语义已显式拉开。History rail 与 K 线区同时加固 wheel/touch 事件消费、`passive` 监听、`overscroll-behavior` 与 `touch-action`，滚轮/拖拽在局部容器内交互时不再串联到整页滚动。

- 🧩 **History rail 在无任务场景下的真实滚动可达性修复** — Home 侧栏现在只在存在活动任务时渲染任务卡，避免空任务卡继续占用第二行并压缩历史区高度；历史卡容器同时固定为 `h-full + min-h-0` 的 bounded 区，确保 8+ 条历史记录可在同一卡片内继续滚动访问，而不是被 rail 裁剪后只显示前几条。

- 🧱 **历史分析滚动根因、字号设置与 K 线语义对齐修复** — 侧栏历史分析现在使用独立 card + 独立 viewport（`min-h-0` + bounded grid row），滚轮在历史卡内部只驱动历史列表本身，离开卡片后页面滚动恢复默认；并在列表底部继续保持 nested-scroll 场景下的 load-more 触发。设置页基础配置新增“字体大小”用户偏好（小/默认/大），持久化到本地并通过全局 CSS 变量受控生效。图表区的 range 语义也已重新对齐为 `1M=1分钟K`、`5M=5分钟K`、`1D=日K`，并补齐 `周K/月K/年K`，前后端周期参数与聚合规则保持一致，默认仍只开启 Candles + Volume。

- 🧭 **品牌位填充、独立历史卡、Key Action 提醒合并与 broker-style range defaults 再收口** — Sidebar 顶部 `WolfyStock` logo 现在会真正填满品牌图标位，避免小图悬在中间；首页左侧历史分析区重构为独立 card + 独立 viewport，鼠标滚轮进入历史卡后只驱动历史列表本身，older records 可以在 rail 内继续向下访问而不把主页面一起带动。任务队列则维持更紧凑的扫描式卡片，仅保留名称、代码、阶段、状态和创建时间，减少每个任务的垂直占用。Key Action 卡本身继续增密，并把 `Execution Reminder` 合并进同一卡片下半区，不再额外占一块竖向空间。图表默认态只显示 `Candles + Volume`，range 控件同步收敛为券商风格语义，并给 reset/zoom 控件单独留出右侧间距。

- 📈 **历史 rail 与 broker-style K 线继续收口** — 首页历史请求不再默认限制在最近 30 天，左侧 `HistoryList` 同时增加滚动阈值触发的分页加载兜底，避免在固定 rail 内滚到底后仍拿不到 Oracle 更早的记录。报告页 `ReportPriceChart` 现在把周线/月线历史拉长到 2~3 年范围，并把非分时视图的默认视窗从固定 64 根调整为整段历史，日/周/月 K 不再默认只剩约两个月；蜡烛体也改为实心填充，并降低长周期视图的最小 candle 宽度，减少密集重叠。

- 🐺 **品牌块、侧边历史 rail 与移动端密度继续收口** — Web 左上角导航品牌块改为使用新的 `WolfyStock` 图形资产与 `QUANTITATIVE SYSTEM` 副标题，替换旧的 `DSA` 名称与图标；Home 侧边 rail 继续压缩任务面板高度、收紧历史条目与列表头部间距，并移除历史请求层的 30 天截断，让更早的分析记录可以在固定高度侧栏里继续纵向滚动访问。与此同时，报告页和图表的移动端间距、时间框按钮、指标 pill、footer metrics 与 disclosure padding 继续压缩，减少空白和换行，保持 broker-style 的紧凑信息密度而不牺牲可读性。

- 🧭 **历史滚动、作战计划占位与 K 线交互继续收口** — 首页左侧 `HistoryList` 现在在 shell rail 中使用真实可收缩滚动容器，历史分析记录可以上下滚动到更早条目，不再因父层高度锁死而截断；标准报告页移除了“来源与覆盖 / 透明度”面板，让作战计划独占整行，并把顶部“关键动作”重排成左侧 bullet plan、右侧 3 条关键利好 + 3 条关键风险，减少空卡片与竖向浪费。市场图表则去掉了与十字光标重复的行情 KPI 卡片，只保留固定 inspector 与指标标线，并通过 `wheel preventDefault + stopPropagation` 配合 `overscroll-behavior: contain` / `touch-action: none` 阻止滚轮缩放时同时带动页面上下滑动，使 K 线交互更接近交易终端。

- 🧩 **统一报告 schema、UI 语言切换、任务队列与交互图表继续收口** — `report_renderer` 现在会在 `standard_report` 中额外产出 `channel_summary`，让完整 Markdown、Discord 精简通知和 brief/homepage 摘要都从同一份结构化对象读取评分、建议、趋势、结论、价格、执行位、风险/利好、最新更新与 checklist，而不是各自拼接字段；`NotificationService.generate_dashboard_report()` 也会在返回 Markdown 前预热 Discord 专用缓存，修复 Discord 明明有数据却仍回退成 `NA` 或继续发送整份长 Markdown 的问题。Web 前端新增全局中英 i18n provider 与语言切换器（默认中文并持久化），并把首页、侧栏、设置页、主题菜单、任务状态、历史列表、图表标题/按钮等首路径文本抽到资源文件；首页任务区改成保留最近任务的队列面板，支持 `queued / analyzing / generating / notifying / completed / failed` 阶段、刷新后恢复与最近完成任务保留。图表侧则修复月线 `days=730` 越界问题，移除多余说明文案，新增指标显隐、缩放、拖拽平移、tooltip 跟踪与更清晰的价格/时间/成交量分区，并让主题菜单、报告面板和测试基线与新的本地默认语言保持一致。

- 🧭 **报告顶部价格语义、金融图表与全局工作区壳层继续收口** — `report_renderer` 现在会把顶部主价明确标成 `Analysis Price`，并用 `Intraday snapshot / Last close / Regular-session close` 区分盘中快照、已收盘与扩展时段基准，避免把分析基准价误导性写成“实时当前价”；同一 bundle 内的 `Prev Close / Open / High / Low / Change` 会一起落盘，盘中场景不再额外展示语义暧昧的 `Reference Close`。Web 报告页的主摘要下方同步改为 API 驱动的金融图表：`1D / 1M / 3M / 1Y / W / M` 视图、真正按价格坐标绘制的 K 线 / 日内图、成交量副图、MA5/10/20 与支撑/压力/买点/止损/目标位标线，替代原先的大面积空白和弱线图；桌面端 Hero 改成“宽主价格区 + 紧凑状态栏”的双栏终端布局，移动端则把次级元信息折叠、让 chart 与 market stats 更早进入首屏。分析完成后的“最新报告已打开”提示则改为自动消失的 toast，不再长期占用主页面。`Shell` / `ChatPage` / `HomePage` 同步统一 desktop rail 宽度、workspace max-width 与断点间距，继续修复 Home / Query / Holdings / Backtest / Settings 路由切换时的缩进与壳层不一致问题；本轮还补上 `workspace-split-layout--main-only` 与基于实际内容宽度触发的 Hero 桌面模式，避免历史 rail 已外置到 shell 后，浏览器放大/全屏时主报告仍误落进窄 rail 列而被挤扁。Cyberpunk / Geek(DOS) 也继续在 badge、卡片、按钮、侧栏和图表上呈现明显不同的视觉语言。
- 🧭 **报告自动打开、交易计划结构化重算、移动端滚动与主题分化同步落地** — `report_renderer` 不再机械复用松散 sniper point，而是按 recent support / resistance、MA5/10/20/60、日内波动与 52 周语境重算 `理想买点 / 次优买点 / 止损 / 目标一区 / 目标二区 / 目标区间 / 仓位建议`，并把 quiet-news 场景下的 risk / catalyst / sentiment 自动补齐为“公司级 → 行业/市场级 → 技术语境”三层摘要；Web 首页在分析任务完成后会重试拉取并自动打开最新历史报告，失败时给出 `View latest report` CTA，同时把当前选中的报告 ID 持久化以便刷新后恢复；Home / Holdings / Backtest 共用统一 workspace 宽度与间距体系，移动端移除固定高度与嵌套滚动陷阱，恢复正常纵向浏览；`cyber / hacker(Geek / DOS)` 主题则升级为真正的 design-token 级切换，连同字体、圆角、按钮、输入框、卡片、历史列表和壳层背景一起改变，避免主题只剩轻微色差。
- 🎯 **分析状态自动聚焦、移动端滚动与主题表面继续收口** — Web 前端本轮没有再改后端数据逻辑，而是围绕实际产品体验补齐三处关键缺口：分析任务完成后，首页会自动定位并选中同股票的最新历史报告、滚动到结果区，并对刚生成的记录做短时高亮，避免用户手动去历史列表里寻找结果；Home/Ask 的根容器同时修正为移动端可正常纵向滚动、桌面端才使用受控滚动，不再因固定高度与 `overflow-hidden` 造成手机端下拉失效；主题系统也继续从“技术上能切换”推进到“关键表面真实响应主题”，历史列表、任务区、问股侧栏、主题菜单、实体卡片与列表项全部改为基于 theme token 渲染，配合 `terminal / cyber / hacker` 的字体、panel 和 surface token，让三套主题在实际工作台里有可读、克制但明确的视觉差异。
- 🎛️ **中段信息密度与主题系统落地继续收口** — `StandardReportPanel` 中部的“风险与催化 / Checklist 与评分”不再保留高而空的大黑块：风险、利好、最新动态、情绪摘要改成更紧凑的 2x2 信息卡，动态去重展示 2~4 条真实催化/风险和 1~3 条真实更新；Checklist 行高、状态 pill 和评分拆解也同步压缩，评分说明改成更短的 definition-grid，减少纵向空耗。与此同时，Web 主题切换不再只是菜单占位：`ThemeProvider` 现在会把主题 preset 真正写入 `document.documentElement` / `body` 和 localStorage，并通过新的 shell/sidebar/report surface token 驱动深黑终端、赛博朋克、Geek Hacker 三套可读暗色预设，让 Shell、导航、Hero、报告卡片和主要表面在切换后有真实可见差异，而不是只有按钮变色。
- 🌒 **分析状态条、主题系统与全站工作区一致性继续收口** — Web 前端本轮继续只做当前本地产品态 polish：首页在提交分析后会立即显示结构化状态条，用统一阶段映射展示“已提交 / 排队中 / 拉取数据 / 生成分析 / 已完成 / 失败”，并对 FMP 403、Gemini 503、409 重复任务等异常给出更产品化的提示；主题切换器从占位按钮升级为可持久化的深黑终端 / 赛博朋克 / Geek Hacker 三套暗色预设；Home、Ask、Portfolio、Backtest、Settings 统一改用共享 workspace header / surface / spacing 体系，减少页面之间的缩放和密度割裂；标准报告页则继续去掉设计草稿式文案，强化综合评分 / 操作建议 / 趋势判断的视觉层级，并让缺失值、source、status 在首页更克制、在完整报告里更集中。后端同时补上健壮 `.env` 加载器，兼容本地 `.env` 首行 `source ...` 这类 shell 前导语句，不再触发 `python-dotenv could not parse statement starting at line 1` 的解析报错。
- 🧭 **首页决策优先、完整报告 canonical 结构与问股工作台继续收口** — `report_renderer` 新增统一的 `decision_panel / reason_layer / coverage_notes` 结构，用同一套结论顺序同时驱动首页 structured view、完整 Markdown 报告、history detail 和 Discord compact digest：先输出评分/建议/趋势、一句话结论、当前价与涨跌，再给出买点/止损/目标/仓位、核心风险、核心利好、最新关键更新和 checklist 摘要。Web `StandardReportPanel` 也同步把首页结构改成“Hero 总览 -> 决策执行面板 -> 理由层 -> 证据层 -> 覆盖说明”，把执行位和风险/催化提前，把技术/基本面表下沉为 evidence layer；`ChatPage` 则继续收口成研究助手工作台，补齐高价值起手问题卡、结构化研究模式区和更紧凑的输入编排，减少空白与工程噪音。
- 🧩 **前端工作栏整合 + Hero 压缩 + 策略面板继续收口** — Web `Shell / SidebarNav / HomePage / HistoryList / TaskPanel / StandardReportPanel` 本轮不再推翻骨架，而是继续做版面收口：Shell 新增统一 rail 上下文，把左侧 DSA 导航、历史分析和任务列表整合成同一深黑工作栏；首页主内容最大宽度明显放开，减少桌面端左右黑边；Hero Summary 压缩成更紧凑的两列布局，把时间信息改成紧凑 row，减少评分区空白；下层模块按“行情/技术、基本面/财报、新闻/作战计划、Checklist/评分拆解”的阅读节奏重新平衡；作战计划改成真正的横向策略面板，上层四格展示关键价位，下层两列展示仓位、建仓与风控说明，并统一列表项、按钮和卡片的轻量过渡，形成更顺滑但不花哨的终端式交互。
- 🖥️ **整站壳层改成深黑 Web3 terminal，并把标准报告页重排成大矩形纵向模块** — Web `Shell / SidebarNav / HomePage / HistoryList / TaskPanel / StandardReportPanel` 继续从旧黑蓝 dashboard 骨架收口到统一的深黑石墨主题：左侧 DSA 导航、历史列表、任务面板和报告工作区全部去掉蓝色 glow 外壳，改成近黑实体面板 + 低亮边框 + 少量 cyan 强调；标准报告页也不再保留 tabs/chips/窄侧栏，而是直接重排为“顶部 Hero 总览 -> 行情/技术并排 -> 基本面/财报并排 -> 新闻/作战计划并排 -> Checklist/评分拆解/风险摘要宽卡片”的大矩形卡片序列，桌面端允许纵向滚动浏览，平板端优先主内容，手机端则按总览、行情、技术、基本面、财报、新闻/情绪、作战计划、checklist 的固定顺序单列展开，避免横向滚动和窄长条阅读。
- 🧱 **NVDA 关键口径继续收口 + Web 报告页改成大矩形终端布局** — `pipeline` / `us_fundamentals_provider` 继续把 `freeCashflow / operatingCashflow / returnOnEquity / returnOnAssets` 的来源与时间窗显式下沉到 `_meta.field_sources / field_periods`，并在汇总基本面时把 `latest_quarter`、`provider_reported_total`、`overview/context` 这类高风险口径打成 `TTM待复核`，由 `report_renderer` 统一展示为 `NA（口径冲突，待校正）`，避免把可疑 ROE/ROA/FCF 直接暴露给用户。新闻 highlights 也继续修正语义：陈旧财报复盘归入催化/业绩预期，媒体解读类内容优先路由到风险/情绪，而非伪装成“最新动态”。Web 标准报告页则进一步抛弃窄条与碎卡片，改成更接近交易终端的“左历史窄栏 + 中间大矩形主内容 + 右侧辅助栏”结构：中间主内容按总览、行情/技术、基本面/财报、新闻/作战计划纵向分层，整体去掉黑蓝外壳、弱化来源胶囊与蓝色 glow，统一成深黑石墨终端主题。
- 🎛️ **同 session 评分稳定器改为分项合成 + Web 报告页重构为深黑终端布局** — `pipeline` 不再只对 LLM 黑箱总分做事后限幅，而是显式拆成“行情/趋势分、技术分、基本面分、新闻/情绪分、风险修正项”后再合成总分，并在 `last_completed_session` 下优先锚定同一交易日/同一 session 的历史基线：当核心输入未变时严格限制单次漂移，技术指标补齐、新闻新增、provider 口径切换等场景则通过 `change_reason` 与 `score_breakdown` 解释来源。Web `StandardReportPanel` 同步放弃旧的黑蓝卡片堆叠骨架，改成更接近 [OKX Markets/Prices](https://www.okx.com/en-us/markets/prices) 的深黑 exchange terminal：顶部 summary strip、一级 tabs、二级 chips、左中右 dense table/rail 布局，以及底部新闻/作战计划区，整体减少 glow、卡片数和无效留白。
- 🧮 **NVDA 基本面 TTM 口径与新闻时效语义继续收口** — `pipeline` 对美股基本面字段新增更细的 source priority：`freeCashflow / operatingCashflow` 优先使用 statement-derived TTM（FMP quarterly statements 优先，其次 Yahoo quarterly），`returnOnEquity / returnOnAssets` 优先使用 FMP/Finnhub 的 TTM ratios，再回退其他 overview 源，避免现金流总额和 ROE/ROA 混用不同时间窗。`report_renderer` 会把这些字段的 `来源 + 口径` 一并带进基本面/财报表，并在新闻 highlights 中将“陈旧财报复盘”从 `最新动态` 降级为催化/业绩语境，避免把 2026-02-25 的财报解读伪装成 2026-03-28 的新公告。Web `StandardReportPanel` 继续去卡片化：表格来源/口径改为终端式细文本列，右侧侧栏精简为评分/风险/情绪/checklist，整体进一步靠近 [OKX Markets/Prices](https://www.okx.com/en-us/markets/prices) 的深黑 terminal 风格。
- 📉 **已收盘场景行情主口径修正 + Web 终端式结构继续收口** — `report_renderer` 不再把 `close` 当作 `prev_close` 的兜底来源；当美股处于 `last_completed_session` 且上游昨收缺失、被错误平盘化，或 `close / prev_close / change / pct` 出现互相打架时，会优先按同一套 regular close 口径重建昨收并重算涨跌，避免 NVDA 这类已收盘场景出现“收跌但昨收等于收盘、涨跌额/幅却是 0”的假平盘。`history_service` 同步在历史详情重建时修复这类污染快照，`pipeline` 的美股 fallback 也补充识别 `regularMarketPreviousClose / chartPreviousClose`。Web `StandardReportPanel` 则继续参考 [OKX Markets/Prices](https://www.okx.com/en-us/markets/prices) 收口为更像终端的结构：顶部 summary strip、一级 tabs、二级 chips、左侧高密度表格、右侧评分/风险/checklist 侧栏，减少卡片堆叠、压缩留白，并统一 badge / chip / checklist 的黑灰基调与尺寸。
- 🧭 **评分稳定器与深黑终端式报告页重做** — `pipeline` 新增分析结果稳定器：把“短线技术趋势”和“综合操作建议”显式分层，降低空头排列、MA20 下方、放量下跌、RSI 偏弱等单一技术因子对综合评分的瞬时压制；当近期历史分数存在时会对单次评分变动做限幅，并在“强基本面 + 短线偏弱”的场景下保留基本面缓冲，避免 NVDA 这类大票因补齐技术字段后直接从中性/观望跳到强烈看空。`report_renderer` 同步输出 `decision_context`（短线视角 / 综合建议 / 调整说明 / 分数变化），Web `StandardReportPanel` 则按 [OKX Markets/Prices](https://www.okx.com/en-us/markets/prices) 的信息架构重排为更克制的深黑 terminal 风格：顶部 summary strip、一级 tabs、二级 chips、左侧高密度表格、右侧评分/趋势/风险/checklist/结论框架，并统一 badge / checklist pill / 表格行高与卡片边框层级，去掉过强 cyan glow 与多余 icon 底框。
- 📡 **技术指标改为 API 优先 + Web 报告改成 OKX 风格终端布局** — `pipeline` / `us_fundamentals_provider` 新增 FMP technical indicator 接入，`MA5 / MA10 / MA20 / MA60 / RSI14` 现在优先取 FMP technical API，`VWAP` 优先取 FMP historical price；FMP 缺失时再回退 Alpha Vantage 或本地历史 OHLC 计算，避免 NVDA / TSLA / ORCL 这类大票长期落在“样本不足”。`report_renderer` 会把技术字段的 `source / status` 一并写入 `standard_report`，Web `StandardReportPanel` 同步改成更接近 OKX markets/prices 的深黑终端式布局：顶部 Hero 总览、一级 tabs、二级 chips、左侧紧凑表格、右侧信号/风险/checklist，并统一 badge / checklist / 表格视觉。
- 🛡️ **多源 fallback 防回归与历史详情保真** — `pipeline` / `history_service` / `report_renderer` 继续收紧美股行情与基本面合并规则：已有有效 quote / fundamentals 不再被 `None`、空字符串、占位 `0` 或 `0.0` 污染；`market_timestamp` 会随 fallback quote 继续透传；历史详情重建会把 `trend_score=0`、`volume_ratio=0.0`、`turnover_rate=0.0`、占位均线等假零值替换为 `context_snapshot` 中的真实值。渲染层同步把量比、换手率、趋势强度等缺失指标恢复为 `NA（原因）`，避免 TSLA 等美股报告出现“字段还在但几乎全部退化成 NA / 0.00”的回归。
- 🌑 **Web 报告页 dark terminal 质感继续收口** — `StandardReportPanel` / `Badge` 继续沿用统一 `standard_report` 数据，但把页面层级调整为更成熟的黑色 trading terminal 风格：去掉重复标题，弱化过度 glow，统一 badge / checklist pill 尺寸与居中对齐，把“时效性 / 市场时间 / 交易日 / session”下沉为次级 chip 信息，并让 Hero 区优先突出股票名、当前价、涨跌幅、评分、建议与趋势，减少“半成品 demo 感”。

- 🌌 **TSLA 等美股标准报告口径校正 + Web3 Dark Dashboard 改版** — `report_renderer` / `history_service` / `pipeline` 进一步统一行情、基本面、财报三类字段语义：常规时段涨跌额/幅继续优先按当前价与昨收重算；`market_session_date` 改为优先从真实 `market_timestamp` 推导，避免美东交易日被本地时区误写；扩展时段时间不再误复用常规时段时间；基本面表去除与财报表混口径的增长字段，并通过 `TTM / 最新值 / 一致预期 / 最新季度同比/环比` 标签显式标注口径；MA5 / MA10 / MA20 / MA60 / VWAP 缺失时继续输出 `NA（原因）`，样本不足不再伪装成 `0.00`。Web 报告详情页则改为更紧凑的 web3 dark / terminal 风格 Hero + 双栏 dashboard 布局，统一 checklist pill、badge、半透明深色卡片、紧凑表格和评分/趋势/均线位置条，同时补齐 `standard_report` snake_case -> camelCase 归一化，确保 Web 与 Discord 继续共用同一 `standard_report` 结构。
- 📘 **标准报告升级为紧凑投资简报视图** — `standard_report` 在服务层新增 `summary_panel / table_sections / visual_blocks / highlights / battle_plan_compact / checklist_items` 等结构化块，Web 端首屏改为摘要卡片、紧凑指标表、评分/价格位置条、风险机会摘要、紧凑作战计划和状态化 checklist，Discord 端则从统一 markdown 中抽取短版摘要，只保留顶部结论、核心行情、技术定位、风险/利好和作战计划，避免继续推送超长字段转储。
- 🇨🇳 **标准报告用户可见字段统一中文化，并接入美股/新闻补数 fallback** — `standard_report` 的 market / technical / fundamental / earnings / sentiment 用户可见字段标签统一由后端渲染层输出中文，避免 Web、Discord 与 history markdown 各自翻译导致口径漂移；同时为美股补充 Finnhub `quote + basic metrics + company news`、FMP `quote + profile + ratios + quarterly statements + historical price`、GNews 通用新闻兜底，优先在现有数据源缺失时补齐昨收、涨跌额/幅、振幅、成交量、52 周高低、MA5/10/20/60、VWAP、Beta、PE/PB、marketCap、shares/float、营收/净利润及新闻发布时间等字段，并继续保持 regular / extended session 分离与 `NA（原因）` 语义。
- 🧾 **标准报告字段映射补全与 Discord 推送稳态修复** — `report_renderer` 会继续沿用统一 `standard_report` 结构，但现在会补消费 `market_snapshot`、`structured_analysis`、`realtime_context`、`market_context`、`fundamental_context`、`earnings_analysis` 中已存在的行情/技术面/基本面字段，减少“上游已有数据却仍显示 `NA`”的情况，并保持 regular / extended session 分离；history 详情重建会合并 `context_snapshot` 补全 `details.standard_report`，Web 端同步兼容 `standardReport` / `standard_report` 回退；Discord 推送改为优先基于统一标准报告内容，补齐配置判定、稳定分块、逐块日志与失败原因输出，并接受任意 2xx 响应为成功，避免静默失败。
- 🧱 **标准报告数据结构下沉到服务层** — `report_renderer` 现在先构建单一 `standard_report` 数据结构，再由 Web Markdown/Discord 消息共用渲染；历史详情 API `details.standard_report` 同步暴露该结构，避免网站、通知和客户端各自重复拼字段导致口径漂移。
- 📣 **Discord 完整报告可读性与资讯价值分级修复** — 在不删字段前提下将 Discord 中的大表格转换为紧凑列表展示；重要信息区新增高价值关键词优先与低价值资讯降权，缺少高价值催化/动态时明确提示“未发现高价值新增催化/动态”。
- 🧮 **报告口径一致性与交易位校验补齐** — 在报告渲染层新增行情口径一致性重算与告警（涨跌额/涨跌幅按当前价与昨收校验），并在作战计划中新增买点类型标注（突破买点/回踩买点）及止损位风险提示，避免 Discord/Web 完整报告出现交易语义自相矛盾。
- 🧾 **Discord/Web 完整报告语义统一（NA 原因 + 北京时间 + 一致格式化）** — 报告渲染统一走同一模板链路，Discord 不再做内容压缩删减，仅按长度分块；Web 与 Discord 共享字段与 section 语义。缺失字段统一展示为 `NA（原因）`，并补齐“报告生成时间（北京时间）/市场时间（原始+北京时间）/交易日/会话类型”显示；价格与比例统一两位小数，成交量/成交额按可读单位输出。
- 🧩 **Web 报告链路缺失字段兜底语义收敛** — 前端在解析分析/任务状态/历史详情报告时新增统一归一化：当 `summary` 必填字段缺失时回填安全默认值（含 `sentiment_score=50`），并优先用顶层响应元信息补齐 `meta` 关键字段，避免因后端局部缺字段导致报告渲染异常或语义漂移。
- 🕒 **统一时间字段契约与诊断可观测性补齐** — Pipeline/API/Renderer 统一追加 `market_timestamp`、`market_session_date`、`news_published_at`、`report_generated_at`（均为 ISO 8601 且保留原始市场时区），并新增 `session_type` 标记（`intraday_snapshot` / `last_completed_session`）；`data_quality.provider_notes` 现在持续输出 provider 失败链路与时间契约快照，`diagnostic_mode` 开启时会输出完整诊断块，关闭时保持兼容默认行为。
- 🧠 **Sentiment 公司相关性过滤升级（规则版）** — 在不引入重模型前提下新增 relevance gating 与分类（`company_specific` / `industry_general` / `regulatory` / `low_relevance`），输出 `relevance_type`/`relevance_score`，并确保 `industry_general` 默认不进入个股核心结论；无高相关信息时统一降级 `no_reliable_news + low confidence`。
- 🧭 **多维分析数据质量与来源可追溯增强（美股优先）** — 新增技术指标来源追踪（`local_from_ohlcv` / `alpha_vantage_fallback`）、`data_quality` 结构化状态与告警注入（含 provider failure warnings）；当基本面/财报/情绪缺失时，报告与提示词将显式说明 partial/no_reliable_news，避免“隐性默认值”伪完整结论。
- 🇺🇸 **美股分析链路闭环修复** — 美股实时行情链路改为明确标记 `yfinance`（仅真实降级时显示“降级兜底”），并在 pipeline 统一补算 `volume_ratio`（当日成交量 / 5 日均量）；新增 Alpha Vantage `OVERVIEW` 的 `SharesOutstanding` 缓存读取并据此计算 `turnover_rate`，缺失时不再错误展示 `0%`，统一显示“数据缺失”；通知与 Markdown 报告中美股筹码改为固定文案“美股暂不支持该指标”，不再显示 A 股筹码占位缺失信息。
- 🧾 **Web 报告透明度区复制按钮层级修复**（#749）— `ReportDetails` 中“原始分析结果 / 分析快照”的复制按钮补齐可点击层级，避免被下方 JSON 内容覆盖后出现按钮可见但无法点击的问题。
- 🧾 **Web 报告详情复制提示按面板独立** — `ReportDetails` 中“原始分析结果”和“分析快照”的复制提示不再共享同一个 `copied` 状态；当两个面板同时展开时，复制其中一个只会更新对应按钮文案，避免两个按钮同时显示“已复制”的误导反馈。
- 📊 **Agent backtest tool semantics** — `get_skill_backtest_summary` 现在要求显式传入 `skill_id`，缺失时会返回明确的校验提示；当仓库尚未持久化真实 skill 级汇总时会返回明确的 unsupported/info 响应，而不再复用 overall 指标。成功返回路径会同时保留 normalized 指标和 `*_pct` 兼容字段，相关工具错误返回也改为稳定通用文案，避免向 agent 或用户暴露底层异常细节。

### 文档

- 新增 Market Scanner 中英专题文档：`docs/market-scanner.md` / `docs/market-scanner_EN.md`，明确产品边界、A 股 universe、打分逻辑、结果解释、已知限制与未来美股扩展路径；`README.md`、`docs/README_EN.md` 与 `docs/INDEX_EN.md` 也同步补上入口。
- 补充 Scanner P9 运营层文档：更新 `.env.example`、`README.md`、`docs/market-scanner.md`、`docs/market-scanner_EN.md`、`docs/full-guide.md`、`docs/full-guide_EN.md`、`docs/README_EN.md`、`docs/INDEX_EN.md`，补齐调度、daily watchlist、通知、失败/空结果语义与运行方式说明。

## [3.9.0] - 2026-03-20

### 发布亮点

- 🤖 **模型链路与报告语言更灵活** — Agent 现在可以通过 `AGENT_LITELLM_MODEL` 独立选择模型链路，普通分析与 Agent 报告也可通过 `REPORT_LANGUAGE=zh|en` 输出统一语言，减少“英文内容 + 中文壳子”这类混排问题，并允许团队分别权衡主分析与 Agent 的成本、速度和能力。
- 🔎 **首页分析体验完成一轮闭环优化** — 首页新增 A 股自动补全，支持代码、中文名、拼音和别名检索；同时 Dashboard 状态收口到统一 store，历史、报告、新闻与 Markdown 抽屉的交互更稳定，“Ask AI” 追问也会优先携带当前报告上下文。
- 💬 **通知与检索能力继续外扩** — 新增 Slack 一等通知渠道；SearXNG 在未配置自建实例时可以自动发现公共实例并按受控轮询降级；Tavily 时效新闻链路修复后，严格时效过滤不再错误丢光有效结果。
- 💼 **持仓与市场复盘链路更稳** — A 股 market review 可选接入 TickFlow 强化指数与涨跌统计；持仓账本写入改为串行化以缩小并发超卖窗口；汇率刷新入口和禁用态提示也更加清晰，减少用户误判。

### 新功能

- 🧩 **Bento UI refinement + deep report drawer convergence (Phases 1-4)** — `apps/dsa-web` completed a bounded Bento refinement pass across the Home surface and the shared page shell. Phase 1 removed the legacy `FLOW AUTOMATION` home card, kept `技术形态 / 基本面画像` at a 1:1 split, reduced non-essential copy, and normalized larger negative-space padding. Phase 2 introduced a dedicated `DeepReportDrawer` with a glass full-height right-side shell, body scroll locking, and two-module deep-read placeholders (`Technical Analysis` with MACD / MA / main fund inflows, plus `Fundamental Profile`). Phase 3 converged the shared `PageChrome` hero shell used by Scanner / Portfolio / Backtest / Settings / Chat / GuestHome / GuestScanner onto the same pure-black, low-opacity glass, large-radius surface contract while preserving existing data flow and route behavior. Phase 4 re-ran the focused Vitest + Playwright smoke coverage and captured local screenshot artifacts for verification. Backend contracts, page routing semantics, and existing scanner / portfolio / chat workflows remain unchanged.

- 🔎 **Web 股票自动补全 MVP** — 首页分析输入框新增本地索引驱动的自动补全，支持股票代码、中文名、拼音和别名匹配；选中候选后会提交 canonical code，并透传 `stock_name`、`original_query`、`selection_source` 到分析请求、任务状态和 SSE 事件；索引加载失败时自动退回旧输入模式，不阻断原有提交流程。同步补充了静态索引加载器、索引生成脚本和前后端契约测试。分阶段进行开发，第一阶段仅支持 A 股。
- 💬 **Slack 一等通知渠道** — 新增 Slack 原生通知支持，同时支持 Bot Token 和 Incoming Webhook 两种接入方式；同时配置时优先使用 Bot API，确保文本与图片发送到同一频道；Bot Token 模式支持图片上传（raw body POST，不使用 multipart）；新增 `SLACK_BOT_TOKEN`、`SLACK_CHANNEL_ID`、`SLACK_WEBHOOK_URL` 配置项，GitHub Actions 工作流同步补齐对应 Secrets 传递。
- 🌍 **报告输出语言可配置**（Issue #758）— 新增 `REPORT_LANGUAGE=zh|en`，默认 `zh`；语言设置会同步注入普通分析与 Agent Prompt，并覆盖 Markdown/Jinja 模板、通知 fallback、历史/API `report_language` 元数据及 Web 报告页固定文案，避免“英文内容 + 中文壳子”的混合输出。
- 🚀 **Agent 与普通分析模型解耦**（Issue #692）— 新增 `AGENT_LITELLM_MODEL`（留空继承 `LITELLM_MODEL`，无前缀按 `openai/<model>` 归一）；Agent 执行链路与 `/api/v1/agent/models` 的 `is_primary/is_fallback` 标记改为基于 Agent 实际模型链路；系统配置与启动期校验补齐 `AGENT_LITELLM_MODEL` 的 `unknown_model/missing_runtime_source` 检查；Web 设置页新增 Agent 主模型选择并与渠道模式运行时配置同步。
- 🔎 **SearXNG 公共实例自动发现与受控轮询**（#752）— 新增 `SEARXNG_PUBLIC_INSTANCES_ENABLED`，在未配置 `SEARXNG_BASE_URLS` 时默认从 `searx.space` 拉取公共实例列表，并按受控轮询顺序选择实例；同次请求内遇到超时、连接错误、HTTP 非 200 或无效 JSON 会自动切换到下一个实例。已配置自建实例的用户保持原有优先级与语义不变；`daily_analysis` GitHub Actions 工作流也已支持显式透传该开关并在启动日志中展示当前状态。
- 📈 **TickFlow market review enhancement** (#632) — 新增可选 `TICKFLOW_API_KEY`；配置后，A 股大盘复盘的主要指数行情优先尝试 TickFlow；若当前 TickFlow 套餐支持标的池查询，市场涨跌统计也会优先尝试 TickFlow。失败或权限不足时立即回退到现有 `AkShare / Tushare / efinance` 链路；板块涨跌榜回退顺序保持不变。接入层同时适配了真实 SDK 契约：主指数查询按单次请求上限分批拉取，并将 TickFlow 返回的比例型 `change_pct` / `amplitude` 统一转换为项目内部的百分比口径。

### 改进

- **Dashboard state slice and workspace closure** — moved Home / Dashboard state into `stockPoolStore`, consolidated history selection, report loading, task syncing, polling refresh, and markdown drawer handling under a single state slice.
- **Dashboard panel standardization** — kept the current dashboard layout contract stable while unifying history, report, news, and markdown presentation with shared tokens, standardized states, and bounded in-panel scrolling for the history list.
- **Dashboard-to-chat follow-up bridge** — routed “Ask AI” follow-ups through report-context hydration instead of direct cross-page state coupling, while keeping chat sends usable when enriched history context is still loading.
- 🧩 **Agent skill unification**（#779）— Multi-Agent runtime, API, Web chat, and config metadata now treat YAML trading profiles as a single `skill` concept; `/api/v1/agent/skills` becomes the primary discovery endpoint, `AGENT_SKILL_*` becomes the primary config surface, and legacy `strategy` names remain only as compatibility aliases.
- 🗂️ **Skill bundle alignment** — `SkillManager` now supports mainstream `SKILL.md` bundles with YAML frontmatter and supporting files, while the multi-agent runtime’s optional forked execution path is renamed to `specialist` mode to keep “skills” and “specialist sub-agents” as separate concepts.
- 🧭 **Skill metadata drives defaults** — built-in skill YAML files now declare their own aliases, default activation flags, router fallback participation, ordering priority, and market-regime tags; factory/router/Bot `/ask`/Web chat default selection no longer hardcode `bull_trend`-centric behavior in code.
- 💼 **持仓账本并发写入串行化**（#742）— 持仓源事件写入/删除现在会在 SQLite 下先获取串行化写锁，减少并发卖出把超售流水写入账本的窗口；直接持仓写接口在锁竞争时返回 `409 portfolio_busy`，CSV 导入保持逐条提交并把 busy 计入 `failed_count`。
- 💱 **持仓页汇率手动刷新入口补齐**（#748）— Web `/portfolio` 页面现在会在“汇率状态”卡片中展示“刷新汇率”按钮，直接调用现有 `POST /api/v1/portfolio/fx/refresh` 接口；刷新后会仅重载快照与风险数据，并以内联摘要反馈“已更新 / 仍 stale / 刷新失败”的结果，减少用户对 `fxStale` 长时间停留的误解。

### 修复

- 🔎 **Web 自动补全 Enter 提交语义修正** — 股票自动补全在搜索命中候选时不再默认高亮第一项；候选列表展开但用户尚未用方向键或鼠标明确选中时，按 Enter 会继续提交原始输入，避免手动输入被第一条候选静默覆盖。
- 🌍 **补齐 `REPORT_LANGUAGE` 启动解析与历史展示本地化边界** — `Config` 在启动时继续遵循“真实环境变量优先、`.env` 兜底”的既有语义，并在两者冲突时输出显式告警，减少 `REPORT_LANGUAGE` 来源不清带来的误判；同时 `/api/v1/history/{id}` 英文详情响应会同步本地化 `sentiment_label`，历史 Markdown 也会正确识别英文 `bias_status` 的风险等级 emoji，避免出现 `乐观` 或 `🚨Safe` 这类中英混排/误报展示。
- 📰 **Tavily 时效新闻检索发布时间映射修复**（#782）— Tavily 在股票新闻和严格时效的情报维度中现在会显式使用 `topic="news"`，并兼容 `published_date` / `publishedDate` 两种发布时间字段；修复了 Tavily 明明返回结果却在后续硬过滤阶段被全部记为 `drop_unknown` 丢弃的问题，同时将机构分析、业绩预期、行业分析等分析型维度恢复为宽源搜索，不再被统一压缩成新闻模式。
- 💱 **持仓页汇率刷新禁用语义修正**（#772）— 当 `PORTFOLIO_FX_UPDATE_ENABLED=false` 时，`POST /api/v1/portfolio/fx/refresh` 现在会返回显式 `refresh_enabled=false` 与 `disabled_reason`，Web `/portfolio` 页面会明确提示“汇率在线刷新已被禁用”，不再误报“当前范围无可刷新的汇率对”。
- 🤖 **Agent timeout and config hardening** — `AGENT_ORCHESTRATOR_TIMEOUT_S` now also protects the legacy single-agent ReAct loop, parallel tool batches stop waiting once the remaining budget is exhausted, and invalid numeric `.env` values fall back to safe defaults with warnings instead of crashing startup.
- 🌐 **CORS wildcard + credentials compatibility** — `CORS_ALLOW_ALL=true` no longer combines `allow_origins=["*"]` with credentialed requests, avoiding browser-side cross-origin failures in demo/development setups.
- 🧭 **Unavailable Agent settings hidden from Web UI** — Deep Research / Event Monitor controls are now treated as compatibility-only metadata in the current branch and are removed from the Settings page to avoid exposing non-functional toggles.
- 🔧 **Skill compatibility hardening** — `allowed-tools` from `SKILL.md` now stays as bundle metadata instead of leaking into runtime tool selection, `/api/v1/agent/strategies` again preserves the legacy `strategies` payload shape, explicit `skills: []` clears stale chat context, and skill-level backtest rollups stay neutral until real per-skill stats exist.
- 🎯 **显式策略选择不再叠加默认多头基线** — Agent 仅在未显式选择策略时才注入默认趋势交易基线；当用户或配置明确指定某个策略 skill 时，分析将只遵循所选策略，不再偷偷附带旧的 bull-trend 默认哲学。
- 🧭 **隐式默认策略收敛为单一多头默认值** — 当 `AGENT_SKILLS` 留空且请求未显式传入策略时，后端不再同时激活多个 `default_active=true` 的 skill，而是统一回落到主默认策略 skill（当前为 `bull_trend`），让 API / Bot / Web 对“默认策略”的理解保持一致。

### 文档

- 新增 Ollama 本地模型配置说明，同步更新 `README.md` 与 `docs/README_EN.md`（Fixes #690）
- 完善 Ollama 配置说明：`docs/full-guide.md` / `docs/full-guide_EN.md` 环境变量表与 Note 补充 `OLLAMA_API_BASE`，避免英文用户误以为 Ollama 不能作为独立配置入口；合并重复的 `OLLAMA_API_BASE` 条目为单一条目
- 明确文档同步治理边界：补充 `README.md`、专题文档、双语文档与交付说明之间的默认同步规则，减少后续文档漂移
- 调整 Agent 术语兼容文案：用户入口继续以“策略”为主称呼，README、双语文档、设置页与问股界面补充 `skill` 作为内部统一命名，降低迁移期理解成本

## [3.8.0] - 2026-03-17

### 发布亮点

- 🎨 **Web 界面完成一轮骨架升级** — 新的 App Shell、侧边导航、主题能力、登录与系统设置流程已经串成统一体验，桌面端加载背景也完成对齐。
- 📈 **分析上下文继续补强** — 美股新增社交舆情情报，A 股补齐财报与分红结构化上下文，Tushare 新接入筹码分布和行业板块涨跌数据。
- 🔒 **运行稳定性与配置兼容性提升** — 退出登录会立即让旧会话失效，定时启动兼容旧配置，运行中的 `MAX_WORKERS` 调整和新闻时效窗口反馈更清晰。
- 💼 **持仓纠错链路更完整** — 超售会被前置拦截，错误交易/资金流水/公司行为可以直接删除回滚，便于修复脏数据。

### 新功能

- 🧩 **Bento UI refinement + deep report drawer convergence (Phases 1-4)** — `apps/dsa-web` completed a bounded Bento refinement pass across the Home surface and the shared page shell. Phase 1 removed the legacy `FLOW AUTOMATION` home card, kept `技术形态 / 基本面画像` at a 1:1 split, reduced non-essential copy, and normalized larger negative-space padding. Phase 2 introduced a dedicated `DeepReportDrawer` with a glass full-height right-side shell, body scroll locking, and two-module deep-read placeholders (`Technical Analysis` with MACD / MA / main fund inflows, plus `Fundamental Profile`). Phase 3 converged the shared `PageChrome` hero shell used by Scanner / Portfolio / Backtest / Settings / Chat / GuestHome / GuestScanner onto the same pure-black, low-opacity glass, large-radius surface contract while preserving existing data flow and route behavior. Phase 4 re-ran the focused Vitest + Playwright smoke coverage and captured local screenshot artifacts for verification. Backend contracts, page routing semantics, and existing scanner / portfolio / chat workflows remain unchanged.

- 📱 **美股社交舆情情报** — 新增 Reddit / X / Polymarket 社交媒体情绪数据源，为美股分析提供实时社交热度、情绪评分和提及量等补充指标；完全可选，仅在配置 `SOCIAL_SENTIMENT_API_KEY` 后对美股生效。
- 📊 **A 股财报与分红结构化增强**（Issue #710）— `fundamental_context.earnings.data` 新增 `financial_report` 与 `dividend` 字段；分红统一按“仅现金分红、税前口径”计算，并补充 `ttm_cash_dividend_per_share` 与 `ttm_dividend_yield_pct`；分析/历史 API 的 `details` 追加 `financial_report`、`dividend_metrics` 可选字段，保持 fail-open 与向后兼容。
- 🔍 **接入 Tushare 筹码与行业板块接口** — 新增筹码分布、行业板块涨跌数据获取能力，并统一纳入配置化数据源优先级；默认按上海时间区分盘中/盘后交易日取数，优先使用 Tushare 同花顺接口，必要时降级到东财。
- 🧱 **Web UI 基础骨架升级** — 重建共享设计令牌与通用组件，新增 App Shell、Theme Provider、侧边导航，并同步调整 Electron 加载背景，为 Web / Desktop 的统一体验打底。
- 🔐 **登录与系统设置流程重做** — 重构 Login、Settings 与 Auth 管理流程，补上显式的认证 setup-state 处理，并让 Web 端与运行时认证配置 API 行为对齐。
- 🧪 **前端回归与冒烟覆盖补强** — 新增并扩展登录、首页、聊天、移动端 Shell、设置页、回测入口等关键路径的组件测试与 Playwright smoke coverage。

### 变更

- 🧭 **页面接入新 Shell 布局契约** — Home、Chat、Settings、Backtest 已统一接入新的页面容器、抽屉和滚动约定，降低 UI 迁移期间的页面行为不一致。
- 💾 **设置页状态同步更稳** — 优化草稿保留、直接保存同步与冲突处理，减少模块级保存后前后端配置状态不一致的问题。
- 🎭 **登录页视觉基线回归** — 登录页恢复到既有 `006` 分支的视觉基线，同时保留新的认证状态逻辑和统一表单交互模型。
- 🏛️ **AI 协作治理资产加固** — 收敛并加强 `AGENTS.md`、`CLAUDE.md`、Copilot 指令和校验脚本的一致性约束，降低治理资产长期漂移风险。

### Added

- **Web UI foundation refresh** — rebuilt shared design tokens and common primitives, introduced the app shell, theme provider, sidebar navigation, and Electron loading background alignment for the upgraded desktop/web experience
- **Settings and auth workflow overhaul** — rebuilt the Login, Settings, and Auth management flows, added explicit auth setup-state handling, and aligned the Web UI with the runtime auth configuration APIs
- **UI regression coverage and smoke checks** — expanded targeted frontend tests and added Playwright smoke coverage for login, home, chat, mobile shell, settings, and backtest entry flows

### Changed

- **Shell-driven page integration** — aligned Home, Chat, Settings, and Backtest with the new shell layout contract so routing, drawer behavior, and page-level scrolling are consistent during the UI migration
- **Settings state consistency** — refined draft preservation, direct-save synchronization, and conflict handling so module-level saves no longer leave the page out of sync with backend config state
- **Login visual baseline** — restored the login page visual treatment to the established `006` branch baseline while keeping the newer auth-state logic and unified form interaction model

### 修复

- ⏰ **定时启动立即执行兼容旧配置**（Issue #726）— `SCHEDULE_RUN_IMMEDIATELY` 未设置时会回退读取 `RUN_IMMEDIATELY`，修复升级后旧 `.env` 在定时模式下的兼容性问题；同时澄清 `.env.example` / README 中两个配置项的适用范围，并注明 Outlook / Exchange 强制 OAuth2 暂不支持。
- 🧵 **运行期 `MAX_WORKERS` 配置生效与可解释性增强**（#633）— 修复异步分析队列未按 `MAX_WORKERS` 同步的问题；新增任务队列并发 in-place 同步机制（空闲即时生效、繁忙延后），并在设置保存反馈与运行日志中明确输出 `profile/max/effective`，减少“参数未生效”误解。
- 🔐 **退出登录立即失效现有会话** — `POST /api/v1/auth/logout` 现在会轮换 session secret，避免旧 cookie 在退出后仍可继续访问受保护接口；同浏览器标签页和并发页面会被同步登出。认证开启时，该接口也不再属于匿名白名单，未登录请求会返回 `401`，避免匿名请求触发全局 session 失效。
- 🧮 **Tushare 板块/筹码调用限流与跨日缓存修复** — 新增的 `trade_cal`、行业板块排行、筹码分布链路统一接入 `_check_rate_limit()`；交易日历缓存改为按自然日刷新，避免服务跨天运行后继续沿用旧交易日判断取数日期。
- 💼 **持仓超售拦截与错误流水恢复**（#718）— `POST /api/v1/portfolio/trades` 现在会在写入前校验可卖数量，超售返回 `409 portfolio_oversell`；持仓页新增交易 / 资金流水 / 公司行为删除能力，删除后会同步失效仓位缓存与未来快照，便于从错误流水中直接恢复。
- 📧 **邮件中文发件人名编码**（#708）— 邮件通知现在会对包含中文的 `EMAIL_SENDER_NAME` 自动做 RFC 2047 编码，并在异常路径补充 SMTP 连接清理，修复 GitHub Actions / QQ SMTP 下 `'ascii' codec can't encode characters` 导致的发送失败。
- 🐛 **港股 Agent 实时行情去重与快速路由** — 统一 `HK01810` / `1810.HK` / `01810` 等港股代码归一规则；港股实时行情改为直接走单次 `akshare_hk` 路径，避免按 A 股 source priority 重复触发同一失败接口；Agent 运行期对显式 `retriable=false` 的工具失败增加短路缓存，减少同轮分析中的重复失败调用。
- 📰 **新闻时效硬过滤与策略分窗**（#697）— 新增 `NEWS_STRATEGY_PROFILE`（`ultra_short/short/medium/long`）并与 `NEWS_MAX_AGE_DAYS` 统一计算有效窗口；搜索结果在返回后执行发布时间硬过滤（时间未知剔除、超窗剔除、未来仅容忍 1 天），并在历史 fallback 链路追加相同约束，避免旧闻再次进入“最新动态/风险警报”。

### 文档

- ☁️ **新增云服务器 Web 界面部署与访问教程**（Fixes #686）— 补充从云端部署到外部访问的落地说明，降低远程自托管门槛。
- 🌍 **补齐英文文档索引与协作文档** — 新增英文文档索引、贡献指南、Bot 命令文档，并补充中英双语 issue / PR 模板，方便中英文协作与外部贡献者理解项目入口。
- 🏷️ **本地化 README 补充 Trendshift badge** — 在多语言 README 中同步补上新版能力入口标识，减少中英文说明面不一致。

## [3.7.0] - 2026-03-15

### 新功能

- 🧩 **Bento UI refinement + deep report drawer convergence (Phases 1-4)** — `apps/dsa-web` completed a bounded Bento refinement pass across the Home surface and the shared page shell. Phase 1 removed the legacy `FLOW AUTOMATION` home card, kept `技术形态 / 基本面画像` at a 1:1 split, reduced non-essential copy, and normalized larger negative-space padding. Phase 2 introduced a dedicated `DeepReportDrawer` with a glass full-height right-side shell, body scroll locking, and two-module deep-read placeholders (`Technical Analysis` with MACD / MA / main fund inflows, plus `Fundamental Profile`). Phase 3 converged the shared `PageChrome` hero shell used by Scanner / Portfolio / Backtest / Settings / Chat / GuestHome / GuestScanner onto the same pure-black, low-opacity glass, large-radius surface contract while preserving existing data flow and route behavior. Phase 4 re-ran the focused Vitest + Playwright smoke coverage and captured local screenshot artifacts for verification. Backend contracts, page routing semantics, and existing scanner / portfolio / chat workflows remain unchanged.

- 💼 **持仓管理 P0 全功能上线**（#677，对应 Issue #627）
  - **核心账本与快照闭环**：新增账户、交易、现金流水、企业行为、持仓缓存、每日快照等核心数据模型与 API 端点；支持 FIFO / AVG 双成本法回放；同日事件顺序固定为 `现金 → 企业行为 → 交易`；持仓快照写入采用原子事务。
  - **券商 CSV 导入**：支持华泰 / 中信 / 招商首批适配，含列名别名兼容；两阶段接口（解析预览 + 确认提交）；`trade_uid` 优先、key-field hash 兜底的幂等去重；前导零股票代码完整保留。
  - **组合风险报告**：集中度风险（Top Positions + A 股板块口径）、历史回撤监控（支持回填缺失快照）、止损接近预警；多币种统一换算 CNY 口径；汲取失败时回退最近成功汇率并标记 stale。
  - **Web 持仓页**（`/portfolio`）：组合总览、持仓明细、集中度饼图、风险摘要、全组合 / 单账户切换；手工录入交易 / 资金流水 / 企业行为；内嵌账户创建入口；CSV 解析 + 提交闭环与券商选择器。
  - **Agent 持仓工具**：新增 `get_portfolio_snapshot` 数据工具，默认紧凑摘要，可选持仓明细与风险数据。
  - **事件查询 API**：新增 `GET /portfolio/trades`、`GET /portfolio/cash-ledger`、`GET /portfolio/corporate-actions`，支持日期过滤与分页。
  - **可扩展 Parser Registry**：应用级共享注册，支持运行时注册新券商；新增 `GET /portfolio/imports/csv/brokers` 发现接口。

- 🎨 **前端设计系统与原子组件库**（#662）
  - 引入渐进式双主题架构（HSL 变量化设计令牌），清理历史 Legacy CSS；重构 Button / Card / Badge / Collapsible / Input / Select 等 20+ 核心组件；新增 `clsx` + `tailwind-merge` 类名合并工具；提升历史记录、LLM 配置等页面可读性。

- ⚡ **分析 API 异步契约与启动优化**（#656）
  - 规范 `POST /api/v1/analysis/analyze` 异步请求的返回契约；优化服务启动辅助逻辑；修复前端报告类型联合定义与后端响应对齐问题。

### 修复

- 🔔 **Discord 环境变量向后兼容**（#659）：运行时新增 `DISCORD_CHANNEL_ID` → `DISCORD_MAIN_CHANNEL_ID` 的 fallback 读取；历史配置用户无需修改即可恢复 Discord Bot 通知；全部相关文档与 `.env.example` 对齐。
- 🔧 **GitHub Actions Node 24 升级**（#665）：将所有 GitHub 官方 actions 升级至 Node 24 兼容版本，消除 CI 日志中的 Node.js 20 deprecation warning（影响 2026-06-02 强制升级窗口）。
- 📅 **持仓页默认日期本地化**：手工录入表单默认日期改用本地时间（`getFullYear/Month/Date`），修复 UTC-N 时区用户在当天晚间出现日期偏移的问题。
- 🔁 **CSV 导入去重逻辑加固**：dedup hash 纳入行序号作为区分因子，确保同字段合法分笔成交不被误折叠；同时在 `trade_uid` 存在时也持久化 hash，防止混合来源重复写入。

### 变更

- `POST /api/v1/portfolio/trades` 在同账户内 `trade_uid` 冲突时返回 `409`。
- 持仓风险响应新增 `sector_concentration` 字段（增量扩展），原有 `concentration` 字段保持不变。
- 分析 API `analyze` 接口异步行为契约文档化；前端报告类型联合更新。

### 测试

- 新增持仓核心服务测试（FIFO / AVG 部分卖出、同日事件顺序、重复 `trade_uid` 返回 409、快照 API 契约）。
- 新增 CSV 导入幂等性、合法分笔成交不误去重、去重边界、风险阈值边界、汇率降级行为测试。
- 新增 Agent `get_portfolio_snapshot` 工具调用测试。
- 新增分析 API 异步契约回归测试。

## [3.6.0] - 2026-03-14

### Added
- 📊 **Web UI Design System** — implemented dual-theme architecture and terminal-inspired atomic UI components
- 📊 **UI Components Refactoring** — integrated `clsx` and `tailwind-merge` for robust class composition across Web UI

- 🗑️ **History batch deletion** — Web UI now supports multi-selection and batch deletion of analysis history; added `POST /api/v1/history/batch-delete` endpoint and `ConfirmDialog` component.
- 🔐 **Auth settings API** — new `POST /api/v1/auth/settings` endpoint to enable or disable Web authentication at runtime and set the initial admin password when needed
- openclaw Skill 集成指南 — 新增 [docs/openclaw-skill-integration.md](openclaw-skill-integration.md)，说明如何通过 openclaw Skill 调用 DSA API
- ⚙️ **LLM channel protocol/test UX** — `.env` and Web settings now share the same channel shape (`LLM_CHANNELS` + `LLM_<NAME>_PROTOCOL/BASE_URL/API_KEY/MODELS/ENABLED`); settings page adds per-channel connection testing, primary/fallback/vision model selection, and protocol-aware model prefixing
- 🤖 **Agent architecture Phase 0+1** — shared protocols (`AgentContext`, `AgentOpinion`, `StageResult`), extracted `run_agent_loop()` runner, `AGENT_ARCH` switch (`single`/`multi`), config registry entries
- 🔍 **Bot NL routing** — two-layer natural-language routing: cheap regex pre-filter (stock codes + finance keywords) → lightweight LLM intent parsing; controlled by `AGENT_NL_ROUTING=true`; supports multi-stock and strategy extraction
- 💬 **`/ask` multi-stock analysis** — comma or `vs` separated codes (max 5), parallel thread execution with 150s timeout (preserves partial results), Markdown comparison summary table at top
- 📋 **`/history` command** — per-user session isolation via `{platform}_{user_id}:{scope}` format (colon delimiter prevents prefix collision); lists both `/chat` and `/ask` sessions; view detail or clear
- 📊 **`/strategies` command** — lists available strategy YAML files grouped by category (趋势/形态/反转/框架) with ✅/⬜ activation status
- 🔧 **Backtest summary tools** — `get_strategy_backtest_summary` and `get_stock_backtest_summary` registered as read-only Agent tools
- ⚙️ **Agent auto-detection** — `is_agent_available()` auto-detects from `LITELLM_MODEL`; explicit `AGENT_MODE=true/false` takes full precedence
- 🏗️ **Multi-Agent orchestrator (Phase 2)** — `AgentOrchestrator` with 4 modes (`quick`/`standard`/`full`/`strategy`); drop-in replacement for `AgentExecutor` via `AGENT_ARCH=multi`; `BaseAgent` ABC with tool subset filtering, cached data injection, and structured `AgentOpinion` output
- 🧩 **Specialised agents (Phase 2-4)** — `TechnicalAgent` (8 tools, trend/MA/MACD/volume/pattern analysis), `IntelAgent` (news & sentiment, risk flag propagation), `DecisionAgent` (synthesis into Decision Dashboard JSON), `RiskAgent` (7 risk categories, two-level severity with soft/hard override)
- 📈 **Strategy system (Phase 3)** — `StrategyAgent` (per-strategy evaluation from YAML skills), `StrategyRouter` (rule-based regime detection → strategy selection), `StrategyAggregator` (weighted consensus with backtest performance factor)
- 🔬 **Deep Research agent (Phase 5)** — `ResearchAgent` with 3-phase approach (decompose → research sub-questions → synthesise report); token budget tracking; new `/research` bot command with aliases (`/深研`, `/deepsearch`)
- 🧠 **Memory & calibration (Phase 6)** — `AgentMemory` with prediction accuracy tracking, confidence calibration (activates after minimum sample threshold), strategy auto-weighting based on historical win rate
- 📊 **Portfolio Agent (Phase 7)** — `PortfolioAgent` for multi-stock portfolio analysis (position sizing, sector concentration, correlation risk, cross-market linkage, rebalance suggestions)
- 🔔 **Event-driven alerts (Phase 7)** — `EventMonitor` with `PriceAlert`, `VolumeAlert`, `SentimentAlert` rules; async checking, callback notifications, serializable persistence
- ⚙️ **New config entries** — `AGENT_ORCHESTRATOR_MODE`, `AGENT_RISK_OVERRIDE`, `AGENT_DEEP_RESEARCH_BUDGET`, `AGENT_MEMORY_ENABLED`, `AGENT_STRATEGY_AUTOWEIGHT`, `AGENT_STRATEGY_ROUTING` — all registered in `config.py` + `config_registry.py` (WebUI-configurable)

### Changed
- 🔐 **Auth password state semantics** — stored password existence is now tracked independently from auth enablement; when auth is disabled, `/api/v1/auth/status` returns `passwordSet=false` while preserving the saved password for future re-enable
- 🔐 **Auth settings re-enable hardening** — re-enabling auth with a stored password now requires `currentPassword`, and failed session creation rolls back the auth toggle to avoid lockout
- ♻️ **AgentExecutor refactored** — `_run_loop` delegates to shared `runner.run_agent_loop()`; removed duplicated serialization/parsing/thinking-label code
- ♻️ **Unified agent switch** — Bot, API, and Pipeline all use `config.is_agent_available()` instead of divergent `config.agent_mode` checks
- 📖 **README.md** — expanded Bot commands section (ask/chat/strategies/history), added NL routing note, updated agent mode description
- 📖 **.env.example** — added `AGENT_ARCH` and `AGENT_NL_ROUTING` configuration documentation
- 🔌 **Analysis API async contract** — `POST /api/v1/analysis/analyze` now documents distinct async `202` payloads for single-stock vs batch requests, and `report_type=full` is treated consistently with the existing full-report behavior

### Fixed
- 🐛 **Analysis API blank-code guardrails** — `POST /api/v1/analysis/analyze` now drops whitespace-only entries before batch enqueue and returns `400` when no valid stock code remains
- 🐛 **Bare `/api` SPA fallback** — unknown API paths now return JSON `404` consistently for both `/api/...` and the exact `/api` path
- 🎮 **Discord channel env compatibility** — runtime now accepts legacy `DISCORD_CHANNEL_ID` as a fallback for `DISCORD_MAIN_CHANNEL_ID`, and the docs/examples now use the same variable name as the actual workflow/config implementation
- 🐛 **Session secret rotation on Windows** — use atomic replace so auth toggles invalidate existing sessions even when `.session_secret` already exists
- 🐛 **Auth toggle atomicity** — persist `ADMIN_AUTH_ENABLED` before rotating session secret; on rotation failure, roll back to the previous auth state
- 🔧 **LLM runtime selection guardrails** — YAML 模式下渠道编辑器不再覆盖 `LITELLM_MODEL` / fallback / Vision；系统配置校验补上全部渠道禁用后的运行时来源检查，并修复 `vertexai/...` 这类协议别名模型被重复加前缀的问题
- 🐛 **Multi-stock `/ask` follow-up regressions** — portfolio overlay now shares the same timeout budget as the per-stock phase and is skipped on timeout instead of blocking the bot reply; `/history` now stores the readable per-stock summary instead of raw dashboard JSON; condensed multi-stock output now renders numeric `sniper_points` values
- 🐛 **Decision dashboard enum compatibility** — multi-agent `DecisionAgent` now keeps `decision_type` within the legacy `buy|hold|sell` contract and normalizes stray `strong_*` outputs before risk override, pipeline conversion, and downstream统计/通知汇总
- 🛟 **Multi-Agent partial-result fallback** — `IntelAgent` now caches parsed intel for downstream reuse, shared JSON parsing tolerates lightly malformed model output, and the orchestrator preserves/synthesizes a minimal dashboard on timeout or mid-pipeline parse failure instead of always collapsing to `50/观望/未知`
- 🐛 **Shared LiteLLM routing restored** — bot NL intent parsing and `ResearchAgent` planning/synthesis now reuse the same LiteLLM adapter / Router / fallback / `api_base` injection path as the main Agent flow, so `LLM_CHANNELS` / `LITELLM_CONFIG` / OpenAI-compatible deployments behave consistently
- 🐛 **Bot chat session backward compatibility** — `/chat` now keeps using the legacy `{platform}_{user_id}` session id when old history already exists, and `/history` can still list / view / clear those pre-migration sessions alongside the new `{platform}_{user_id}:chat` format
- 🐛 **EventMonitor unsupported rule rejection** — config validation/runtime loading now reject or skip alert types the monitor cannot actually evaluate yet, so schedule mode no longer silently accepts permanent no-op rules
- 🐛 **P0 基本面聚合稳定性修复** (#614) — 修复 `get_stock_info` 板块语义回归（新增 `belong_boards` 并保留 `boards` 兼容别名）、引入基本面上下文精简返回以控制 token、为基本面缓存增加最大条目淘汰，并补齐 ETF 总体状态聚合与 NaN 板块字段过滤，保证 fail-open 与最小入侵。
- 🔧 **GitHub Actions 搜索引擎环境变量补充** — 工作流新增 `MINIMAX_API_KEYS`、`BRAVE_API_KEYS`、`SEARXNG_BASE_URLS` 环境变量映射，使 GitHub Actions 用户可配置 MiniMax、Brave、SearXNG 搜索服务（此前 v3.5.0 已添加 provider 实现但缺少工作流配置）
- 🤖 **Multi-Agent runtime consistency** — `AGENT_MAX_STEPS` now propagates to each orchestrated sub-agent; added cooperative `AGENT_ORCHESTRATOR_TIMEOUT_S` budget to stop overlong pipelines before they cascade further
- 🔌 **Multi-Agent feature wiring** — `AGENT_RISK_OVERRIDE` now actively downgrades final dashboards on hard risk findings; `AGENT_MEMORY_ENABLED` now injects recent analysis memory + confidence calibration into specialised agents; multi-stock `/ask` now runs `PortfolioAgent` to add portfolio-level allocation and concentration guidance
- 🔔 **EventMonitor runtime wiring** — schedule mode can now load alert rules from `AGENT_EVENT_ALERT_RULES_JSON`, poll them at `AGENT_EVENT_MONITOR_INTERVAL_MINUTES`, and send triggered alerts through the existing notification service
- 🛠️ **Follow-up stability fixes** — multi-stock `/ask` now falls back to usable text output when dashboard JSON parsing fails; EventMonitor skips semantically invalid rules instead of aborting schedule startup; background alert polling now runs independently of the main scheduled analysis loop
- 🧪 **Multi-Agent regression coverage** — added orchestrator execution tests for `run()`, `chat()`, critical-stage failure, graceful degradation, and timeout handling
- 🧹 **PortfolioAgent cleanup** — `post_process()` now reuses shared JSON parsing and removed stale unused imports
- 🚦 **Bot async dispatch** — `CommandDispatcher` now exposes `dispatch_async()`; NL intent parsing and default command execution are offloaded from the event loop, DingTalk stream awaits async handlers directly, and Feishu stream processing is moved off the SDK callback thread
- 🌐 **Async webhook handler** — new `handle_webhook_async()` function in `bot/handler.py` for use from async contexts (e.g. FastAPI); calls `dispatch_async()` directly without thread bridging
- 🧵 **Feishu stream ThreadPoolExecutor** — replaced unbounded per-message `Thread` spawning with a capped `ThreadPoolExecutor(max_workers=8)` to prevent thread explosion under message bursts
- 🔒 **EventMonitor safety** — `_check_volume()` now safely handles `get_daily_data` returning `None` (no tuple-unpacking crash); `on_trigger` callbacks support both sync and async callables via `asyncio.to_thread`/`await`
- 🧹 **ResearchAgent dedup** — `_filtered_registry()` now delegates to `BaseAgent._filtered_registry()` instead of duplicating the filtering logic
- 🧹 **Bot trailing whitespace cleanup** — removed W291/W293 whitespace issues across `bot/handler.py`, `bot/dispatcher.py`, `bot/commands/base.py`, `bot/platforms/feishu_stream.py`, `bot/platforms/dingtalk_stream.py`
- 🐛 **Dispatcher `_parse_intent_via_llm` safety** — replaced fragile `'raw' in dir()` with `'raw' in locals()` for undefined-variable guard in `JSONDecodeError` handler
- 🐛 **筹码结构 LLM 未填写时兜底补全** (#589) — DeepSeek 等模型未正确填写 `chip_structure` 时，自动用数据源已获取的筹码数据补全，保证各模型展示一致；普通分析与 Agent 模式均生效
- 🐛 **历史报告狙击点位显示原始文本** (#452) — 历史详情页现优先展示 `raw_result.dashboard.battle_plan.sniper_points` 中的原始字符串，避免 `analysis_history` 数值列把区间、说明文字或复杂点位压缩成单个数字；保留原有数值列作为回退
- 🐛 **Session prefix collision** — user ID `123` could see sessions of user `1234` via `startswith`; fixed with colon delimiter in session_id format
- 🐛 **NL pre-filter false positives** — `re.IGNORECASE` caused `[A-Z]{2,5}` to match common English words like "hello"; removed global flag, use inline `(?i:...)` only for English finance keywords
- 🐛 **Dotted ticker in strategy args** — `_get_strategy_args()` didn't recognize `BRK.B` as a stock code, leaving it in strategy text; now accepts `TICKER.CLASS` format
- ⏱️ **efinance 长调用挂起修复** (#660) — 为所有 efinance API 调用引入 `_ef_call_with_timeout()` 包装（默认 30 秒，可通过 `EFINANCE_CALL_TIMEOUT` 配置）；使用 `executor.shutdown(wait=False)` 确保超时后不再阻塞主线程，彻底消除 81 分钟挂起问题
- 🛡️ **类型安全内容完整性检查** (#660) — `check_content_integrity()` 现在将非字符串类型的 `operation_advice` / `analysis_summary` 视为缺失字段，避免下游 `get_emoji()` 因 `dict.strip()` 崩溃
- 📄 **报告保存与通知解耦** (#660) — `_save_local_report()` 不再依赖 `send_notification` 标志触发，`--no-notify` 模式下本地报告照常保存
- 🔄 **operation_advice 字典归一化** (#660) — Pipeline 和 BacktestEngine 现在将 LLM 返回的 `dict` 格式 `operation_advice` 通过 `decision_type`（不区分大小写）映射为标准字符串，防止因模型输出格式变化导致崩溃
- 🛡️ **runner.py usage None 防护** (#660) — `response.usage` 为 `None` 时不再抛出 `AttributeError`，回退为 0 token 计数
- 📋 **orchestrator 静默失败改为日志警告** (#660) — `IntelAgent` / `RiskAgent` 阶段失败现在记录 `WARNING` 而非静默跳过，便于诊断

### Notes
- ⚠️ **Multi-worker auth toggles** — runtime auth updates are process-local; multi-worker deployments must restart/roll workers to keep auth state consistent

## [3.5.0] - 2026-03-12

### Added
- 📊 **Web UI full report drawer** (Fixes #214) — history page adds "Full Report" button to display the complete Markdown analysis report in a side drawer; new `GET /api/v1/history/{record_id}/markdown` endpoint
- 📊 **LLM cost tracking** — all LLM calls (analysis, agent, market review) recorded in `llm_usage` table; new `GET /api/v1/usage/summary?period=today|month|all` endpoint returns aggregated token usage by call type and model
- 🔍 **SearXNG search provider** (Fixes #550) — quota-free self-hosted search fallback; priority: Bocha > Tavily > Brave > SerpAPI > MiniMax > SearXNG
- 🔍 **MiniMax web search provider** — `MiniMaxSearchProvider` with circuit breaker (3 failures → 300s cooldown) and dual time-filtering; configured via `MINIMAX_API_KEYS`
- 🤖 **Agent models discovery API** — `GET /api/v1/agent/models` returns available model deployments (primary/fallback/source/api_base) for Web UI model selector
- 🤖 **Agent chat export & send** (#495) — export conversation to .md file; send to configured notification channels; new `POST /api/v1/agent/chat/send`
- 🤖 **Agent background execution** (#495) — analysis continues when switching pages; badge notification on completion; auto-cancel in-progress stream on session switch
- 📝 **Report Engine P0** — Pydantic schema validation for LLM JSON; Jinja2 templates (markdown/wechat/brief) with legacy fallback; content integrity checks with retry; brief mode (`REPORT_TYPE=brief`); history signal comparison
- 📦 **Smart import** — multi-source import from image/CSV/Excel/clipboard; Vision LLM extracts code+name+confidence; name→code resolver (local map + pinyin + AkShare); confidence-tiered confirmation
- ⚙️ **GitHub Actions LiteLLM config** — workflow supports `LITELLM_CONFIG`/`LITELLM_CONFIG_YAML` for flexible AI provider configuration
- ⚙️ **Config engine refactor & system API** (#602) — unified config registry, validation and API exposure
- 📖 **LLM configuration guide** — new `docs/LLM_CONFIG_GUIDE.md` covering 3-tier config, quick start, Vision/Agent/troubleshooting

### Fixed
- 🐛 **analyze_trend always reports No historical data** (#600) — now fetches from DB/DataFetcher instead of broken `get_analysis_context`
- 🐛 **Chip structure fallback when LLM omits it** (#589) — auto-fills from data source chip data for consistent display across models
- 🐛 **History sniper points show raw text** (#452) — prioritizes original strings over compressed numeric values
- 🐛 **GitHub Actions ENABLE_CHIP_DISTRIBUTION configurable** (#617) — no longer hardcoded, supports vars/secrets override
- 🐛 **`.env` save preserves comments and blank lines** — Web settings no longer destroys `.env` formatting
- 🐛 **Agent model discovery fixes** — legacy mode includes LiteLLM-native providers; source detection aligned with runtime; fallback deployments no longer expanded per-key
- 🐛 **Stooq US stock previous close semantics** — no longer misuses open price as previous close
- 🐛 **Stock name prefetch regression** — prioritizes local `STOCK_NAME_MAP` before remote queries
- 🐛 **AkShare limit-up/down calculation** (#555) — fixed market analysis statistics
- 🐛 **AkShare Tencent source field index & ETF quote mapping** (#579)
- 🐛 **Pytdx stock name cache pagination** (#573) — prevents cache overflow
- 🐛 **PushPlus oversized report chunking** (#489) — auto-segments long content
- 🐛 **Agent chat cancel & switch** (#495) — cancel no longer misreports as failure; fast switch no longer overwrites stream state
- 🐛 **MiniMax search status in `/status` command** (#587)
- 🐛 **config_registry duplicate BOCHA_API_KEYS** — removed duplicate dict entry that silently overwrote config

### Changed
- 🔎 **Fetcher failure observability** — logs record start/success/failure with elapsed time, failover transitions; Efinance/Akshare include upstream endpoint and classified failure categories
- ♻️ **Data source resilience & cleanup** (#602) — fallback chain optimization
- ♻️ **Image extract API response extension** — new `items` field (code/name/confidence); `codes` preserved for backward compatibility
- ♻️ **Import parse error messages** — specific failure reasons for Excel/CSV; improved logging with file type and size

### Docs
- 📖 LLM config guide refactored for clarity (#583)
- 📖 `image-extract-prompt.md` with full prompt documentation
- 📖 AkShare fallback cache TTL documentation
## [3.4.10] - 2026-03-07

### Fixed
- 🐛 **EfinanceFetcher ETF OHLCV data** (#541, #527) — switch `_fetch_etf_data` from `ef.fund.get_quote_history` (NAV-only, no OHLCV, no `beg`/`end` params) to `ef.stock.get_quote_history`; ETFs now return proper open/high/low/close/volume/amount instead of zeros; remove obsolete NAV column mappings from `_normalize_data`
- 🐛 **tiktoken 0.12.0 `Unknown encoding cl100k_base`** (#537) — pin `tiktoken>=0.8.0,<0.12.0` in requirements.txt to avoid plugin-registration regression introduced in 0.12.0
- 🐛 **Web UI API error classification** (#540) — frontend no longer treats every HTTP 400 as the same "server/network" failure; now distinguishes Agent disabled / missing params / model-tool incompatibility / upstream LLM errors / local connection failures
- 🐛 **北交所代码识别失败** (#491, #533) — 8/4/92 开头的 6 位代码现正确识别为北交所；Tushare/Akshare/Yfinance 等数据源支持 .BJ 或 bj 前缀；Baostock/Pytdx 对北交所代码显式切换数据源；避免误判上海 B 股 900xxx
- 🐛 **狙击点位解析错误** (#488, #532) — 理想买入/二次买入等字段在无「元」字时误提取括号内技术指标数字；现先截去第一个括号后内容再提取

### Added
- **Markdown-to-image for dashboard report** (#455, #535) — 个股日报汇总支持 markdown 转图片推送（Telegram、WeChat、Custom、Email），与大盘复盘行为一致
- **markdown-to-file engine** (#455) — `MD2IMG_ENGINE=markdown-to-file` 可选，对 emoji 支持更好，需 `npm i -g markdown-to-file`
- **PREFETCH_REALTIME_QUOTES** (#455) — 设为 `false` 可禁用实时行情预取，避免 efinance/akshare_em 全市场拉取
- **Stock name prefetch** (#455) — 分析前预取股票名称，减少报告中「股票xxxxx」占位符
- 📊 **分析报告模型标记** (#528, #534) — 在分析报告 meta、报告末尾、推送内容中展示 `model_used`（完整 LLM 模型名）；Agent 多轮调用时记录并展示每轮实际使用的模型（支持 fallback 切换）

### Changed
- **Enhanced markdown-to-image failure warning** (#455) — 转图失败时提示具体依赖（wkhtmltopdf 或 m2f）
- **WeChat-only image routing optimization** (#455) — 仅配置企业微信图片时，不再对完整报告做冗余转图，避免误导性失败日志
- **Stock name prefetch lightweight mode** (#455) — 名称预取阶段跳过 realtime quote 查询，减少额外网络开销

## [3.4.9] - 2026-03-06

### Added
- 🧠 **Structured config validation** — `ConfigIssue` dataclass and `validate_structured()` with severity-aware logging; `CONFIG_VALIDATE_MODE=strict` aborts startup on errors
- 🖼️ **Vision model config** — `VISION_MODEL` and `VISION_PROVIDER_PRIORITY` for image stock extraction; provider fallback (Gemini → Anthropic → OpenAI → DeepSeek) when primary fails
- 🚀 **CLI init wizard** — `python -m dsa init` 3-step interactive bootstrap (model → data source → notification), 9 provider presets, incremental merge by default
- 🔧 **Multi-channel LLM support** with visual channel editor (#494)

### Changed
- ♻️ **Vision extraction** — migrated from gemini-3 hardcode to `litellm.completion()` with configurable model and provider fallback; `OPENAI_VISION_MODEL` deprecated in favor of `VISION_MODEL`
- ♻️ **Market analyzer** — uses `Analyzer.generate_text()` for LLM calls; fixes bypass and Anthropic `AttributeError` when using non-Router path
- ♻️ **Config validation refinements** — test_env output format syncs with `validate_structured` (severity-aware ✓/✗/⚠/·); Vision key warning when `VISION_MODEL` set but no provider API key; market_analyzer test covers `generate_market_review` fallback when `generate_text` returns None
- ⚙️ **Auto-tag workflow defaults to NO tag** — only tags when commit message explicitly contains `#patch`, `#minor`, or `#major`
- ♻️ **Formatter and notification refactor** (#516)

### Fixed
- 🐛 **STOCK_LIST not refreshed on scheduled runs** — `.env` or WebUI changes to `STOCK_LIST` now hot-reload before each scheduled analysis (#529)
- 🐛 **WebUI fails to load with MIME type error** — SPA fallback route now resolves correct `Content-Type` for JS/CSS files (#520)
- 🐛 **AstrBot sender docstring misplaced** — `import time` placed before docstring in `_send_astrbot`, causing it to become dead code
- 🐛 **Telegram Markdown link escaping** — `_convert_to_telegram_markdown` escaped `[]()` characters, breaking all Markdown links in reports
- 🐛 **Duplicate `discord_bot_status` field** in Config dataclass — second declaration silently shadowed the first
- 🧹 **Unused imports** — removed `shutil`/`subprocess` from `main.py`
- 🔧 **Config validation and Vision key check** (#525)

### Docs
- 📝 Clarified GitHub Actions non-trading-day manual run controls (`TRADING_DAY_CHECK_ENABLED` + `force_run`) for Issue #461 / PR #466

## [3.4.8] - 2026-03-02

### Fixed
- 🐛 **Desktop exe crashes on startup with `FileNotFoundError`** — PyInstaller build was missing litellm's JSON data files (e.g. `model_prices_and_context_window_backup.json`). Added `--collect-data litellm` to both Windows and macOS build scripts so the files are correctly bundled in the executable.

### CI
- 🔧 Cache Electron binaries on macOS CI runners to prevent intermittent EOF download failures when fetching `electron-vX.Y.Z-darwin-*.zip` from GitHub CDN
- 🔧 Fix macOS DMG `hdiutil Resource busy` error during desktop packaging

### Docs
- 📝 Clarify non-trading-day manual run controls for GitHub Actions (`TRADING_DAY_CHECK_ENABLED` + `force_run`) (#474)

## [3.4.7] - 2026-02-28

### Added
- 🧠 **CN/US Market Strategy Blueprint System** (#395) — market review prompt injects region-specific strategy blueprints with position sizing and risk trigger recommendations

### Fixed
- 🐛 **`TRADING_DAY_CHECK_ENABLED` env var and `--force-run` for GitHub Actions** (#466)
- 🐛 **Agent pipeline preserved resolved stock names** (#464) — placeholder names no longer leak into reports
- 🐛 **Code cleanup** (#462, Fixes #422)
- 🐛 **WebUI auto-build on startup** (#460)
- 🐛 **ARCH_ARGS unbound variable** (#458)
- 🐛 **Time zone inconsistency & right panel flash** (#439)

### Docs
- 📝 Clarify potential ambiguities in code (#343)
- 📝 ENABLE_EASTMONEY_PATCH guidance for Issue #453 (#456)

## [3.4.0] - 2026-02-27

### Added
- 📡 **LiteLLM Direct Integration + Multi API Key Support** (#454, Fixes #421 #428)
  - Removed native SDKs (google-generativeai, google-genai, anthropic); unified through `litellm>=1.80.10`
  - New config: `LITELLM_MODEL`, `LITELLM_FALLBACK_MODELS`, `GEMINI_API_KEYS`, `ANTHROPIC_API_KEYS`, `OPENAI_API_KEYS`
  - Multi-key auto-builds LiteLLM Router (simple-shuffle) with 429 cooldown
  - **Breaking**: `.env` `GEMINI_MODEL` (no prefix) only for fallback; explicit config must include provider prefix

### Changed
- ♻️ **Notification Refactoring** (#435) — extracted 10 sender classes into `src/notification_sender/`

### Fixed
- 🐛 LLM NoneType crash, history API 422, sniper points extraction
- 🐛 Auto-build frontend on WebUI startup — `WEBUI_AUTO_BUILD` env var (default `true`)
- 🐛 Docker explicit project name (#448)
- 🐛 Bocha search SSL retry (#445, #446) — transient errors retry up to 3 times
- 🐛 Gemini google-genai SDK migration (Fixes #440, #444)
- 🐛 Mobile home page scrolling (Fixes #419, #433)
- 🐛 History list scroll reset (#431)
- 🐛 Settings save button false positive (fixes #417, #430)

## [3.3.22] - 2026-02-26

### Added
- 💬 **Chat History Persistence** (Fixes #400, #414) — `/chat` page survives refresh, sidebar session list
- 🎨 Project VI Assets — logo icon set, PSD, vector, banner (#425)
- 🚀 Desktop CI Auto-Release (#426) — Windows + macOS parallel builds

### Fixed
- 🐛 Agent Reasoning 400 & LiteLLM Proxy (fixes #409, #427)
- 🐛 Discord chunked sending (#413) — `DISCORD_MAX_WORDS` config
- 🐛 yfinance shared DataFrame (#412)
- 🐛 sniper_points parsing (#408)
- 🐛 Agent framework category missing (#406)
- 🐛 Date inconsistency & query id (fixes #322, #363)

## [3.3.12] - 2026-02-24

### Added
- 📈 **Intraday Realtime Technical Indicators** (Issue #234, #397) — MA calculated from realtime price, config: `ENABLE_REALTIME_TECHNICAL_INDICATORS`
- 🤖 **Agent Strategy Chat** (#367) — full ReAct pipeline, 11 YAML strategies, SSE streaming, multi-turn chat
- 📢 PushPlus Group Push — `PUSHPLUS_TOPIC` (#402)
- 📅 Trading Day Check (Issue #373, #375) — `TRADING_DAY_CHECK_ENABLED`, `--force-run`

### Fixed
- 🐛 DeepSeek reasoning mode (Issue #379, #386)
- 🐛 Agent news intel persistence (Fixes #396, #405)
- 🐛 Bare except clauses replaced with `except Exception` (#398)
- 🐛 UUID fallback for HTTP non-secure context (fixes #377, #381)
- 🐛 Docker DNS resolution (Fixes #372, #374)
- 🐛 Agent session/strategy bugs — multiple follow-up fixes for #367
- 🐛 yfinance parallel download data filtering

### Changed
- Market review strategy consistency — unified cn/us template
- Agent test assertions updated (`6 -> 11`)


## [3.2.11] - 2026-02-23

### 修复（#patch）
- 🐛 **StockTrendAnalyzer 从未执行** (Issue #357)
  - 根因：`get_analysis_context` 仅返回 2 天数据且无 `raw_data`，pipeline 中 `raw_data in context` 始终为 False
  - 修复：Step 3 直接调用 `get_data_range` 获取 90 日历天（约 60 交易日）历史数据用于趋势分析
  - 改善：趋势分析失败时用 `logger.warning(..., exc_info=True)` 记录完整 traceback

## [3.2.10] - 2026-02-22

### 新增
- ⚙️ 支持 `RUN_IMMEDIATELY` 配置项，设为 `true` 时定时任务触发后立即执行一次分析，无需等待首个定时点

### 修复
- 🐛 修复 Web UI 页面居中问题
- 🐛 修复 Settings 返回 500 错误

## [3.2.9] - 2026-02-22

### 修复
- 🐛 **ETF 分析仅关注指数走势**（Issue #274）
  - 美股/港股 ETF（如 VOO、QQQ）与 A 股 ETF 不再纳入基金公司层面风险（诉讼、声誉等）
  - 搜索维度：ETF/指数专用 risk_check、earnings、industry 查询，避免命中基金管理人新闻
  - AI 提示：指数型标的分析约束，`risk_alerts` 不得出现基金管理人公司经营风险

## [3.2.8] - 2026-02-21

### 修复
- 🐛 **BOT 与 WEB UI 股票代码大小写统一**（Issue #355）
  - BOT `/analyze` 与 WEB UI 触发分析的股票代码统一为大写（如 `aapl` → `AAPL`）
  - 新增 `canonical_stock_code()`，在 BOT、API、Config、CLI、task_queue 入口处规范化
  - 历史记录与任务去重逻辑可正确识别同一股票（大小写不再影响）

## [3.2.7] - 2026-02-20

### 新增
- 🔐 **Web 页面密码验证**（Issue #320, #349）
  - 支持 `ADMIN_AUTH_ENABLED=true` 启用 Web 登录保护
  - 首次访问在网页设置初始密码；支持「系统设置 > 修改密码」和 CLI `python -m src.auth reset_password` 重置

## [3.2.6] - 2026-02-20
### ⚠️ 破坏性变更（Breaking Changes）

- **历史记录 API 变更 (Issue #322)**
  - 路由变更：`GET /api/v1/history/{query_id}` → `GET /api/v1/history/{record_id}`
  - 参数变更：`query_id` (字符串) → `record_id` (整数)
  - 新闻接口变更：`GET /api/v1/history/{query_id}/news` → `GET /api/v1/history/{record_id}/news`
  - 原因：`query_id` 在批量分析时可能重复，无法唯一标识单条历史记录。改用数据库主键 `id` 确保唯一性
  - 影响范围：使用旧版历史详情 API 的所有客户端需同步更新

### 修复
- 修复美股（如 ADBE）技术指标矛盾：akshare 美股复权数据异常，统一美股历史数据源为 YFinance（Issue #311）
- 🐛 **历史记录查询和显示问题 (Issue #322)**
  - 修复历史记录列表查询中日期不一致问题：使用明天作为 endDate，确保包含今天全天的数据
  - 修复服务器 UI 报告选择问题：原因是多条记录共享同一 `query_id`，导致总是显示第一条。现改用 `analysis_history.id` 作为唯一标识
  - 历史详情、新闻接口及前端组件已全面适配 `record_id`
  - 新增后台轮询（每 30s）与页面可见性变更时静默刷新历史列表，确保 CLI 发起的分析完成后前端能及时同步，使用 `silent` 模式避免触发 loading 状态
- 🐛 **美股指数实时行情与日线数据** (Issue #273)
  - 修复 SPX、DJI、IXIC、NDX、VIX、RUT 等美股指数无法获取实时行情的问题
  - 新增 `us_index_mapping` 模块，将用户输入（如 SPX）映射为 Yahoo Finance 符号（如 ^GSPC）
  - 美股指数与美股股票日线数据直接路由至 YfinanceFetcher，避免遍历不支持的数据源
  - 消除重复的美股识别逻辑，统一使用 `is_us_stock_code()` 函数

### 优化
- 🎨 **首页输入栏与 Market Sentiment 布局对齐优化**
  - 股票代码输入框左缘与历史记录 glass-card 框左对齐
  - 分析按钮右缘与 Market Sentiment 外框右对齐
  - Market Sentiment 卡片向下拉伸填满格子，消除与 STRATEGY POINTS 之间的空隙
  - 窄屏时输入栏填满宽度，响应式对齐保持一致

## [3.2.5] - 2026-02-19

### 新增
- 🌍 **大盘复盘可选区域**（Issue #299）
  - 支持 `MARKET_REVIEW_REGION` 环境变量：`cn`（A股）、`us`（美股）、`both`（两者）
  - us 模式使用 SPX/纳斯达克/道指/VIX 等指数；both 模式可同时复盘 A 股与美股
  - 默认 `cn`，保持向后兼容

## [3.2.4] - 2026-02-18

### 修复
- 🐛 **统一美股数据源为 YFinance**（Issue #311）
  - akshare 美股复权数据异常，统一美股历史数据源为 YFinance
  - 修复 ADBE 等美股股票技术指标矛盾问题

## [3.2.3] - 2026-02-18

### 修复
- 🐛 **标普500实时数据缺失**（Issue #273）
  - 修复 SPX、DJI、IXIC、NDX、VIX、RUT 等美股指数无法获取实时行情的问题
  - 新增 `us_index_mapping` 模块，将用户输入（如 SPX）映射为 Yahoo Finance 符号（如 `^GSPC`）
  - 美股指数与美股股票日线数据直接路由至 YfinanceFetcher，避免遍历不支持的数据源

## [3.2.2] - 2026-02-16

### 新增
- 📊 **PE 指标支持**（Issue #296）
  - AI System Prompt 增加 PE 估值关注
- 📰 **新闻时效性筛查**（Issue #296）
  - `NEWS_MAX_AGE_DAYS`：新闻最大时效（天），默认 3，避免使用过时信息
- 📈 **强势趋势股乖离率放宽**（Issue #296）
  - `BIAS_THRESHOLD`：乖离率阈值（%），默认 5.0，可配置
  - 强势趋势股（多头排列且趋势强度 ≥70）自动放宽乖离率到 1.5 倍

## [3.2.1] - 2026-02-16

### 新增
- 🔧 **东财接口补丁可配置开关**
  - 支持 `EFINANCE_PATCH_ENABLED` 环境变量开关东财接口补丁（默认 `true`）
  - 补丁不可用时可降级关闭，避免影响主流程

## [3.2.0] - 2026-02-15

### 新增
- 🔒 **CI 门禁统一（P0）**
  - 新增 `scripts/ci_gate.sh` 作为后端门禁单一入口
  - 主 CI 改为 `backend-gate`、`docker-build`、`web-gate` 三段式
  - CI 触发改为所有 PR，避免 Required Checks 因路径过滤缺失而卡住合并
  - `web-gate` 支持前端路径变更按需触发
  - 新增 `network-smoke` 工作流承载非阻断网络场景回归
- 📦 **发布链路收敛（P0）**
  - `docker-publish` 调整为 tag 主触发，并增加发布前门禁校验
  - 手动发布增加 `release_tag` 输入与 semver/changelog 强校验
  - 发布前新增 Docker smoke（关键模块导入）
- 📝 **PR 模板升级（P0）**
  - 增加背景、范围、验证命令与结果、回滚方案、Issue 关联等必填项
- 🤖 **AI 审查覆盖增强（P0）**
  - `pr-review` 纳入 `.github/workflows/**` 范围
  - 新增 `AI_REVIEW_STRICT` 开关，可选将 AI 审查失败升级为阻断

## [3.1.13] - 2026-02-15

### 新增
- 📊 **仅分析结果摘要**（Issue #262）
  - 支持 `REPORT_SUMMARY_ONLY` 环境变量，设为 `true` 时只推送汇总，不含个股详情
  - 默认 `false`，多股时适合快速浏览

## [3.1.12] - 2026-02-15

### 新增
- 📧 **个股与大盘复盘合并推送**（Issue #190）
  - 支持 `MERGE_EMAIL_NOTIFICATION` 环境变量，设为 `true` 时将个股分析与大盘复盘合并为一次推送
  - 默认 `false`，减少邮件数量、降低被识别为垃圾邮件的风险

## [3.1.11] - 2026-02-15

### 新增
- 🤖 **Anthropic Claude API 支持**（Issue #257）
  - 支持 `ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`、`ANTHROPIC_TEMPERATURE`、`ANTHROPIC_MAX_TOKENS`
  - AI 分析优先级：Gemini > Anthropic > OpenAI
- 📷 **从图片识别股票代码**（Issue #257）
  - 上传自选股截图，通过 Vision LLM 自动提取股票代码
  - API: `POST /api/v1/stocks/extract-from-image`；支持 JPEG/PNG/WebP/GIF，最大 5MB
  - 支持 `OPENAI_VISION_MODEL` 单独配置图片识别模型
- ⚙️ **通达信数据源手动配置**（Issue #257）
  - 支持 `PYTDX_HOST`、`PYTDX_PORT` 或 `PYTDX_SERVERS` 配置自建通达信服务器

## [3.1.10] - 2026-02-15

### 新增
- ⚙️ **立即运行配置**（Issue #332）
  - 支持 `RUN_IMMEDIATELY` 环境变量，`true` 时定时任务启动后立即执行一次
- 🐛 修复 Docker 构建问题

## [3.1.9] - 2026-02-14

### 新增
- 🔌 **东财接口补丁机制**
  - 新增 `patch/eastmoney_patch.py` 修复 efinance 上游接口变更
  - 不影响其他数据源的正常运行

## [3.1.8] - 2026-02-14

### 新增
- 🔐 **Webhook 证书校验开关**（Issue #265）
  - 支持 `WEBHOOK_VERIFY_SSL` 环境变量，可关闭 HTTPS 证书校验以支持自签名证书
  - 默认保持校验，关闭存在 MITM 风险，仅建议在可信内网使用

## [3.1.7] - 2026-02-14

### 修复
- 🐛 修复包导入错误（package import error）

## [3.1.6] - 2026-02-13

### 修复
- 🐛 修复 `news_intel` 中 `query_id` 不一致问题

## [3.1.5] - 2026-02-13

### 新增
- 📷 **Markdown 转图片通知**（Issue #289）
  - 支持 `MARKDOWN_TO_IMAGE_CHANNELS` 配置，对 Telegram、企业微信、自定义 Webhook（Discord）、邮件发送图片格式报告
  - 邮件为内联附件，增强对不支持 HTML 客户端的兼容性
  - 需安装 `wkhtmltopdf` 和 `imgkit`

## [3.1.4] - 2026-02-12

### 新增
- 📧 **股票分组发往不同邮箱**（Issue #268）
  - 支持 `STOCK_GROUP_N` + `EMAIL_GROUP_N` 配置，不同股票组报告发送到对应邮箱
  - 大盘复盘发往所有配置的邮箱

## [3.1.3] - 2026-02-12

### 修复
- 🐛 修复 Docker 内运行时通过页面修改配置报错 `[Errno 16] Device or resource busy` 的问题

## [3.1.2] - 2026-02-11

### 修复
- 🐛 修复 Docker 一致性问题，解决关键批次处理与通知 Bug

## [3.1.1] - 2026-02-11

### 变更
- ♻️ `API_HOST` → `WEBUI_HOST`：Docker Compose 配置项统一

## [3.1.0] - 2026-02-11

### 新增
- 📊 **ETF 支持增强与代码规范化**
  - 统一各数据源 ETF 代码处理逻辑
  - 新增 `canonical_stock_code()` 统一代码格式，确保数据源路由正确

## [3.0.5] - 2026-02-08

### 修复
- 🐛 修复信号 emoji 与建议不一致的问题（复合建议如"卖出/观望"未正确映射）
- 🐛 修复 `*ST` 股票名在微信/Dashboard 中 markdown 转义问题
- 🐛 修复 `idx.amount` 为 None 时大盘复盘 TypeError
- 🐛 修复分析 API 返回 `report=None` 及 ReportStrategy 类型不一致问题
- 🐛 修复 Tushare 返回类型错误（dict → UnifiedRealtimeQuote）及 API 端点指向

### 新增
- 📊 大盘复盘报告注入结构化数据（涨跌统计、指数表格、板块排名）
- 🔍 搜索结果 TTL 缓存（500 条上限，FIFO 淘汰）
- 🔧 Tushare Token 存在时自动注入实时行情优先级
- 📰 新闻摘要截断长度 50→200 字

### 优化
- ⚡ 补充行情字段请求限制为最多 1 次，减少无效请求

## [3.0.4] - 2026-02-07

### 新增
- 📈 **回测引擎** (PR #269)
  - 新增基于历史分析记录的回测系统，支持收益率、胜率、最大回撤等指标评估
  - WebUI 集成回测结果展示

## [3.0.3] - 2026-02-07

### 修复
- 🐛 修复狙击点位数据解析错误问题 (PR #271)

## [3.0.2] - 2026-02-06

### 新增
- ✉️ 可配置邮件发送者名称 (PR #272)
- 🌐 外国股票支持英文关键词搜索

## [3.0.1] - 2026-02-06

### 修复
- 🐛 修复 ETF 实时行情获取、市场数据回退、企业微信消息分块问题
- 🔧 CI 流程简化

## [3.0.0] - 2026-02-06

### 移除
- 🗑️ **移除旧版 WebUI**
  - 删除基于 `http.server.ThreadingHTTPServer` 的旧版 WebUI（`web/` 包）
  - 旧版 WebUI 的功能已完全被 FastAPI（`api/`）+ React 前端替代
  - `--webui` / `--webui-only` 命令行参数标记为弃用，自动重定向到 `--serve` / `--serve-only`
  - `WEBUI_ENABLED` / `WEBUI_HOST` / `WEBUI_PORT` 环境变量保持兼容，自动转发到 FastAPI 服务
  - `webui.py` 保留为兼容入口，启动时直接调用 FastAPI 后端
  - Docker Compose 中移除 `webui` 服务定义，统一使用 `server` 服务

### 变更
- ♻️ **服务层重构**
  - 将 `web/services.py` 中的异步任务服务迁移至 `src/services/task_service.py`
  - Bot 分析命令（`bot/commands/analyze.py`）改为使用 `src.services.task_service`
  - Docker 环境变量 `WEBUI_HOST`/`WEBUI_PORT` 更名为 `API_HOST`/`API_PORT`（旧名仍兼容）

## [2.3.0] - 2026-02-01

### 新增
- 🇺🇸 **增强美股支持** (Issue #153)
  - 实现基于 Akshare 的美股历史数据获取 (`ak.stock_us_daily()`)
  - 实现基于 Yfinance 的美股实时行情获取（优先策略）
  - 增加对不支持数据源（Tushare/Baostock/Pytdx/Efinance）的美股代码过滤和快速降级

### 修复
- 🐛 修复 AMD 等美股代码被误识别为 A 股的问题 (Issue #153)

## [2.2.5] - 2026-02-01

### 新增
- 🤖 **AstrBot 消息推送** (PR #217)
  - 新增 AstrBot 通知渠道，支持推送到 QQ 和微信
  - 支持 HMAC SHA256 签名验证，确保通信安全
  - 通过 `ASTRBOT_URL` 和 `ASTRBOT_TOKEN` 配置

## [2.2.4] - 2026-02-01

### 新增
- ⚙️ **可配置数据源优先级** (PR #215)
  - 支持通过环境变量（如 `YFINANCE_PRIORITY=0`）动态调整数据源优先级
  - 无需修改代码即可优先使用特定数据源（如 Yahoo Finance）

## [2.2.3] - 2026-01-31

### 修复
- 📦 更新 requirements.txt，增加 `lxml_html_clean` 依赖以解决兼容性问题

## [2.2.2] - 2026-01-31

### 修复
- 🐛 修复代理配置区分大小写问题 (fixes #211)

## [2.2.1] - 2026-01-31

### 修复
- 🐛 **YFinance 兼容性修复** (PR #210, fixes #209)
  - 修复新版 yfinance 返回 MultiIndex 列名导致的数据解析错误

## [2.2.0] - 2026-01-31

### 新增
- 🔄 **多源回退策略增强**
  - 实现了更健壮的数据获取回退机制 (feat: multi-source fallback strategy)
  - 优化了数据源故障时的自动切换逻辑

### 修复
- 🐛 修复 analyzer 运行后无法通过改 .env 文件的 stock_list 内容调整跟踪的股票

## [2.1.14] - 2026-01-31

### 文档
- 📝 更新 README 和优化 auto-tag 规则

## [2.1.13] - 2026-01-31

### 修复
- 🐛 **Tushare 优先级与实时行情** (Fixed #185)
  - 修复 Tushare 数据源优先级设置问题
  - 修复 Tushare 实时行情获取功能

## [2.1.12] - 2026-01-30

### 修复
- 🌐 修复代理配置在某些情况下的区分大小写问题
- 🌐 修复本地环境禁用代理的逻辑

## [2.1.11] - 2026-01-30

### 优化
- 🚀 **飞书消息流优化** (PR #192)
  - 优化飞书 Stream 模式的消息类型处理
  - 修改 Stream 消息模式默认为关闭，防止配置错误运行时报错

## [2.1.10] - 2026-01-30

### 合并
- 📦 合并 PR #154 贡献

## [2.1.9] - 2026-01-30

### 新增
- 💬 **微信文本消息支持** (PR #137)
  - 新增微信推送的纯文本消息类型支持
  - 添加 `WECHAT_MSG_TYPE` 配置项

## [2.1.8] - 2026-01-30

### 修复
- 🐛 修正日志中 API 提供商显示错误 (PR #197)

## [2.1.7] - 2026-01-30

### 修复
- 🌐 禁用本地环境的代理设置，避免网络连接问题

## [2.1.6] - 2026-01-29

### 新增
- 📡 **Pytdx 数据源 (Priority 2)**
  - 新增通达信数据源，免费无需注册
  - 多服务器自动切换
  - 支持实时行情和历史数据
- 🏷️ **多源股票名称解析**
  - DataFetcherManager 新增 `get_stock_name()` 方法
  - 新增 `batch_get_stock_names()` 批量查询
  - 自动在多数据源间回退
  - Tushare 和 Baostock 新增股票名称/列表方法
- 🔍 **增强搜索回退**
  - 新增 `search_stock_price_fallback()` 用于数据源全部失败时
  - 新增搜索维度：市场分析、行业分析
  - 最大搜索次数从 3 增加到 5
  - 改进搜索结果格式（每维度 4 条结果）

### 改进
- 更新搜索查询模板以提高相关性
- 增强 `format_intel_report()` 输出结构

## [2.1.5] - 2026-01-29

### 新增
- 📡 新增 Pytdx 数据源和多源股票名称解析功能

## [2.1.4] - 2026-01-29

### 文档
- 📝 更新赞助商信息

## [2.1.3] - 2026-01-28

### 文档
- 📝 重构 README 布局
- 🌐 新增繁体中文翻译 (README_CHT.md)

### 修复
- 🐛 修复 WebUI 无法输入美股代码问题
  - 输入框逻辑改成所有字母都转换成大写
  - 支持 `.` 的输入（如 `BRK.B`）

## [2.1.2] - 2026-01-27

### 修复
- 🐛 修复个股分析推送失败和报告路径问题 (fixes #166)
- 🐛 修改 CR 错误，确保微信消息最大字节配置生效

## [2.1.1] - 2026-01-26

### 新增
- 🔧 添加 GitHub Actions auto-tag 工作流
- 📡 添加 yfinance 兜底数据源及数据缺失警告

### 修复
- 🐳 修复 docker-compose 路径和文档命令
- 🐳 Dockerfile 补充 copy src 文件夹 (fixes #145)

## [2.1.0] - 2026-01-25

### 新增
- 🇺🇸 **美股分析支持**
  - 支持美股代码直接输入（如 `AAPL`, `TSLA`）
  - 使用 YFinance 作为美股数据源
- 📈 **MACD 和 RSI 技术指标**
  - MACD：趋势确认、金叉死叉信号（零轴上金叉⭐、金叉✅、死叉❌）
  - RSI：超买超卖判断（超卖⭐、强势✅、超买⚠️）
  - 指标信号纳入综合评分系统
- 🎮 **Discord 推送支持** (PR #124, #125, #144)
  - 支持 Discord Webhook 和 Bot API 两种方式
  - 通过 `DISCORD_WEBHOOK_URL` 或 `DISCORD_BOT_TOKEN` + `DISCORD_MAIN_CHANNEL_ID` 配置
- 🤖 **机器人命令交互**
  - 钉钉机器人支持 `/分析 股票代码` 命令触发分析
  - 支持 Stream 长连接模式
- 🌡️ **AI 温度参数可配置** (PR #142)
  - 支持自定义 AI 模型温度参数
- 🐳 **Zeabur 部署支持**
  - 添加 Zeabur 镜像部署工作流
  - 支持 commit hash 和 latest 双标签

### 重构
- 🏗️ **项目结构优化**
  - 核心代码移至 `src/` 目录，根目录更清爽
  - 文档移至 `docs/` 目录
  - Docker 配置移至 `docker/` 目录
  - 修复所有 import 路径，保持向后兼容
- 🔄 **数据源架构升级**
  - 新增数据源熔断机制，单数据源连续失败自动切换
  - 实时行情缓存优化，批量预取减少 API 调用
  - 网络代理智能分流，国内接口自动直连
- 🤖 Discord 机器人重构为平台适配器架构

### 修复
- 🌐 **网络稳定性增强**
  - 自动检测代理配置，对国内行情接口强制直连
  - 修复 EfinanceFetcher 偶发的 `ProtocolError`
  - 增加对底层网络错误的捕获和重试机制
- 📧 **邮件渲染优化**
  - 修复邮件中表格不渲染问题 (#134)
  - 优化邮件排版，更紧凑美观
- 📢 **企业微信推送修复**
  - 修复大盘复盘推送不完整问题
  - 增强消息分割逻辑，支持更多标题格式
  - 增加分批发送间隔，避免限流丢失
- 👷 **CI/CD 修复**
  - 修复 GitHub Actions 中路径引用的错误

## [2.0.0] - 2026-01-24

### 新增
- 🇺🇸 **美股分析支持**
  - 支持美股代码直接输入（如 `AAPL`, `TSLA`）
  - 使用 YFinance 作为美股数据源
- 🤖 **机器人命令交互** (PR #113)
  - 钉钉机器人支持 `/分析 股票代码` 命令触发分析
  - 支持 Stream 长连接模式
  - 支持选择精简报告或完整报告
- 🎮 **Discord 推送支持** (PR #124)
  - 支持 Discord Webhook 推送
  - 添加 Discord 环境变量到工作流

### 修复
- 🐳 修复 WebUI 在 Docker 中绑定 0.0.0.0 (fixed #118)
- 🔔 修复飞书长连接通知问题
- 🐛 修复 `analysis_delay` 未定义错误
- 🔧 启动时 config.py 检测通知渠道，修复已配置自定义渠道情况下仍然提示未配置问题

### 改进
- 🔧 优化 Tushare 优先级判断逻辑，提升封装性
- 🔧 修复 Tushare 优先级提升后仍排在 Efinance 之后的问题
- ⚙️ 配置 TUSHARE_TOKEN 时自动提升 Tushare 数据源优先级
- ⚙️ 实现 4 个用户反馈 issue (#112, #128, #38, #119)

## [1.6.0] - 2026-01-19

### 新增
- 🖥️ WebUI 管理界面及 API 支持（PR #72）
  - 全新 Web 架构：分层设计（Server/Router/Handler/Service）
  - 核心 API：支持 `/analysis` (触发分析), `/tasks` (查询进度), `/health` (健康检查)
  - 交互界面：支持页面直接输入代码并触发分析，实时展示进度
  - 运行模式：新增 `--webui-only` 模式，仅启动 Web 服务
  - 解决了 [#70](https://github.com/ZhuLinsen/daily_stock_analysis/issues/70) 的核心需求（提供触发分析的接口）
- ⚙️ GitHub Actions 配置灵活性增强（[#79](https://github.com/ZhuLinsen/daily_stock_analysis/issues/79)）
  - 支持从 Repository Variables 读取非敏感配置（如 STOCK_LIST, GEMINI_MODEL）
  - 保持对 Secrets 的向下兼容

### 修复
- 🐛 修复企业微信/飞书报告截断问题（[#73](https://github.com/ZhuLinsen/daily_stock_analysis/issues/73)）
  - 移除 notification.py 中不必要的长度硬截断逻辑
  - 依赖底层自动分片机制处理长消息
- 🐛 修复 GitHub Workflow 环境变量缺失（[#80](https://github.com/ZhuLinsen/daily_stock_analysis/issues/80)）
  - 修复 `CUSTOM_WEBHOOK_BEARER_TOKEN` 未正确传递到 Runner 的问题

## [1.5.0] - 2026-01-17

### 新增
- 📲 单股推送模式（[#55](https://github.com/ZhuLinsen/daily_stock_analysis/issues/55)）
  - 每分析完一只股票立即推送，不用等全部分析完
  - 命令行参数：`--single-notify`
  - 环境变量：`SINGLE_STOCK_NOTIFY=true`
- 🔐 自定义 Webhook Bearer Token 认证（[#51](https://github.com/ZhuLinsen/daily_stock_analysis/issues/51)）
  - 支持需要 Token 认证的 Webhook 端点
  - 环境变量：`CUSTOM_WEBHOOK_BEARER_TOKEN`

## [1.4.0] - 2026-01-17

### 新增
- 📱 Pushover 推送支持（PR #26）
  - 支持 iOS/Android 跨平台推送
  - 通过 `PUSHOVER_USER_KEY` 和 `PUSHOVER_API_TOKEN` 配置
- 🔍 博查搜索 API 集成（PR #27）
  - 中文搜索优化，支持 AI 摘要
  - 通过 `BOCHA_API_KEYS` 配置
- 📊 Efinance 数据源支持（PR #59）
  - 新增 efinance 作为数据源选项
- 🇭🇰 港股支持（PR #17）
  - 支持 5 位代码或 HK 前缀（如 `hk00700`、`hk1810`）

### 修复
- 🔧 飞书 Markdown 渲染优化（PR #34）
  - 使用交互卡片和格式化器修复渲染问题
- ♻️ 股票列表热重载（PR #42 修复）
  - 分析前自动重载 `STOCK_LIST` 配置
- 🐛 钉钉 Webhook 20KB 限制处理
  - 长消息自动分块发送，避免被截断
- 🔄 AkShare API 重试机制增强
  - 添加失败缓存，避免重复请求失败接口

### 改进
- 📝 README 精简优化
  - 高级配置移至 `docs/full-guide.md`


## [1.3.0] - 2026-01-12

### 新增
- 🔗 自定义 Webhook 支持
  - 支持任意 POST JSON 的 Webhook 端点
  - 自动识别钉钉、Discord、Slack、Bark 等常见服务格式
  - 支持配置多个 Webhook（逗号分隔）
  - 通过 `CUSTOM_WEBHOOK_URLS` 环境变量配置

### 修复
- 📝 企业微信长消息分批发送
  - 解决自选股过多时内容超过 4096 字符限制导致推送失败的问题
  - 智能按股票分析块分割，每批添加分页标记（如 1/3, 2/3）
  - 批次间隔 1 秒，避免触发频率限制

## [1.2.0] - 2026-01-11

### 新增
- 📢 多渠道推送支持
  - 企业微信 Webhook
  - 飞书 Webhook（新增）
  - 邮件 SMTP（新增）
  - 自动识别渠道类型，配置更简单

### 改进
- 统一使用 `NOTIFICATION_URL` 配置，兼容旧的 `WECHAT_WEBHOOK_URL`
- 邮件支持 Markdown 转 HTML 渲染

## [1.1.0] - 2026-01-11

### 新增
- 🤖 OpenAI 兼容 API 支持
  - 支持 DeepSeek、通义千问、Moonshot、智谱 GLM 等
  - Gemini 和 OpenAI 格式二选一
  - 自动降级重试机制

## [Unreleased]

### 修复
- 收口 `last_completed_session` 的美股已收盘口径：常规字段会优先锁定单一 EOD bundle，避免 `close / prev_close / change / pct` 被多源 fallback 混写。
- 报告评分新增显式拆解与同 session 稳定约束，减少同一交易日重复生成报告时的无解释大幅漂移。

### Web
- 重构标准报告详情页为更接近 [OKX Markets/Prices](https://www.okx.com/en-us/markets/prices) 的深黑终端布局：顶部 summary strip、表格主区、右侧信号栏、移动端紧凑 definition-list。
- 移除 standard report 页面下方重复的旧资讯区，并放宽首页报告容器，减少桌面端无效留白与顶层横向滚动。
- 主题系统增强为明显分层：`Dark Terminal` 保持克制终端风格，`Cyberpunk` 提升霓虹边界与高对比发光，`Geek / DOS` 切换为低饱和复古终端面板与方角控制。
- 新增 5 档全局字号系统（XS/S/M/L/XL），并分别控制桌面与移动端缩放比例，设置持久化到本地存储。
- 移动端密度优化：收紧页面间距、标题与图表工具条字号/间距，提升同屏信息量。
- 修复移动端 K 线交互滚动串扰：在图表内部触摸拖拽/缩放时隔离页面滚动，图表外区域保持正常页面滚动。

## [Unreleased]

### 修复
- 扫描器“历史运行记录”抽屉现在会把长 headline 收敛到可截断标题，并将历史股票代码拆成自动换行的胶囊标签，避免美股长代码串把列表项横向撑爆。

## Unreleased

### Web
- 修复首页与游客页的滚动/响应式死锁，移除首页 Bento 区域的高度锁定和 `overflow-hidden` 依赖，恢复整页向下滚动与更稳定的多断点铺排。
- 重做首页 AI 决断图，使用更接近真实交易节奏的箱体震荡 -> 回踩 -> 放量突破走势，并强化突破胶囊信号与紧凑归因说明。
- 调整游客页预览图为更真实的波动曲线，补充 AI 归因文案，并放宽容器宽度以改善缩放和窄屏可读性。
- 释放首页与游客页桌面端宽度上限，首页改为 5 列 Bento 底层网格，让 AI 决断卡在超宽屏占 2/5，右侧三张指标卡各占 1/5，并同步拉宽顶部标题与搜索区。

## [1.0.0] - 2026-01-10

### 新增
- 🎯 AI 决策仪表盘分析
  - 一句话核心结论
  - 精确买入/止损/目标点位
  - 检查清单（✅⚠️❌）
  - 分持仓建议（空仓者 vs 持仓者）
- 📊 大盘复盘功能
  - 主要指数行情
  - 涨跌统计
  - 板块涨跌榜
  - AI 生成复盘报告
- 🔍 多数据源支持
  - AkShare（主数据源，免费）
  - Tushare Pro
  - Baostock
  - YFinance
- 📰 新闻搜索服务
  - Tavily API
  - SerpAPI
- 💬 企业微信机器人推送
- ⏰ 定时任务调度
- 🐳 Docker 部署支持
- 🚀 GitHub Actions 零成本部署

### 技术特性
- Gemini AI 模型（gemini-3-flash-preview）
- 429 限流自动重试 + 模型切换
- 请求间延时防封禁
- 多 API Key 负载均衡
- SQLite 本地数据存储

---

[Unreleased]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.9.0...HEAD
[3.9.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.8.0...v3.9.0
[3.8.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.7.0...v3.8.0
[3.7.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.6.0...v3.7.0
[3.6.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.5.0...v3.6.0
[3.5.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.10...v3.5.0
[3.4.10]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.9...v3.4.10
[3.4.9]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.8...v3.4.9
[3.4.8]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.7...v3.4.8
[3.4.7]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.0...v3.4.7
[3.4.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.3.22...v3.4.0
[3.3.22]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.3.12...v3.3.22
[3.3.12]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.2.11...v3.3.12
[3.2.11]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.2.10...v3.2.11
[2.3.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.5...v2.3.0
[2.2.5]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.4...v2.2.5
[2.2.4]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.3...v2.2.4
[2.2.3]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.2...v2.2.3
[2.2.2]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.1...v2.2.2
[2.2.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.0...v2.2.1
[2.2.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.14...v2.2.0
[2.1.14]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.13...v2.1.14
[2.1.13]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.12...v2.1.13
[2.1.12]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.11...v2.1.12
[2.1.11]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.10...v2.1.11
[2.1.10]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.9...v2.1.10
[2.1.9]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.8...v2.1.9
[2.1.8]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.7...v2.1.8
[2.1.7]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.6...v2.1.7
[2.1.6]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.5...v2.1.6
[2.1.5]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.4...v2.1.5
[2.1.4]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.3...v2.1.4
[2.1.3]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.2...v2.1.3
[2.1.2]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.1...v2.1.2
[2.1.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.6.0...v2.0.0
[1.6.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/ZhuLinsen/daily_stock_analysis/releases/tag/v1.0.0
