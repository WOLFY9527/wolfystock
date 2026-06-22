# T-1087 Portfolio pricing evidence consumer readiness audit

Task ID: T-1087-AUDIT

Task title: Portfolio pricing evidence consumer readiness audit

Mode: READ-ONLY-AUDIT with one explicitly allowed docs artifact.

Allowed artifact:

`docs/codex/audits/T-1087-portfolio-pricing-evidence-consumer-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1087-portfolio-pricing-evidence-consumer-readiness-audit`
- branch: `codex/t1087-portfolio-pricing-evidence-consumer-readiness-audit`
- branch HEAD inspected before writing: `9aeb042c`
- latest observed `origin/main`: `8f124bce`
- branch state before writing: one commit behind `origin/main`; no rebase, branch switch, or worktree switch was performed

Scope boundary:

- This audit inspected Portfolio pricing metadata, freshness metadata, evidence metadata, consumer UI rendering paths, backend API payload construction, and relevant tests.
- The live browser check reached `/zh/portfolio`, but the current route was auth-gated in the local dev session, so authenticated Portfolio content evidence relies on the existing Playwright harness.
- No source, tests, config, package, lockfile, API, provider/cache/runtime, frontend behavior, accounting, ledger, risk calculation, broker, order, auth, scanner, options, or backtest files were changed.

## Readiness verdict

Portfolio is consumer-ready enough to show stale or delayed pricing in product-safe language today. The page already maps raw quote, broker-sync, fallback, FX, confidence, and lineage states into bounded copy such as `价格快照`, `价格可能延迟`, `价格更新中`, `截至 <date>`, `置信度有限`, and one-line notices such as `部分价格数据暂不可用，已使用最近一次可用数据。`.

Do not open a narrow frontend UI implementation task yet. The smallest safe future task is tests-only: lock the current consumer boundary so raw provider/source/cache/debug/reason-code metadata can continue to flow through backend and frontend contracts without leaking into the default Portfolio consumer UI.

## Metadata inventory

Pricing metadata exists at position level:

- Backend schema exposes `price_source`, `price_source_label`, `price_as_of`, `is_price_fallback`, `price_fallback_reason`, `valuation_confidence`, and `display_fx_status` on each position: `api/v1/schemas/portfolio.py:253`.
- Frontend type mirrors these as `priceSource`, `priceSourceLabel`, `priceAsOf`, `isPriceFallback`, `priceFallbackReason`, `valuationConfidence`, and `displayFxStatus`: `apps/dsa-web/src/types/portfolio.ts:92`.
- Backend daily-close versus fallback construction happens in `_build_positions`; missing/invalid close falls back to average cost, clears `price_as_of`, sets `is_price_fallback`, and caps valuation confidence: `src/services/portfolio_service.py:3332`.
- Broker-sync snapshot positions carry `broker_sync_snapshot` metadata with a snapshot date and sync confidence: `src/services/portfolio_service.py:3184`.
- `_build_position_price_metadata` serializes source, source label, as-of, fallback flag/reason, and confidence: `src/services/portfolio_service.py:3473`.
- Backend API tests already assert fallback metadata is present on the snapshot response: `tests/test_portfolio_api.py:383`.

Freshness and FX metadata exists at snapshot/risk level:

- Snapshot response exposes `fx_stale`, `fx_rates`, `sourceAuthorityState`, `fxFreshnessState`, `valuationLineageState`, `holdingsLineageState`, `cashLedgerCompletenessState`, `benchmarkMappingState`, `factorMappingState`, and `confidenceCap`: `api/v1/schemas/portfolio.py:381`.
- Risk response exposes the same diagnostics/evidence/state fields plus `sectorSourceProvenance`: `api/v1/schemas/portfolio.py:513`.
- Snapshot assembly builds account payloads, FX rows, analytics, and then merges portfolio risk diagnostics: `src/services/portfolio_service.py:2420`.
- FX rows include `source`, `is_stale`, `updated_at`, and `source_direction`; missing pairs are represented as `source: "missing"` and stale: `src/services/portfolio_service.py:2604`.

Evidence metadata exists and is intentionally broader than consumer UI needs:

- Frontend evidence types allow diagnostics fields including `reasonCodes`, `sourceRefs.provider`, `sourceRefs.sourceClass`, `rawPayloadStored`, and `adminDiagnostics`: `apps/dsa-web/src/types/portfolio.ts:226`.
- Portfolio snapshot/risk adapters camel-case the full response payload; they do not currently clip raw fields at the adapter boundary: `apps/dsa-web/src/api/portfolio.ts:496`.
- Portfolio evidence normalization hides admin reason codes and diagnostics unless `audience: "admin"` is requested: `apps/dsa-web/src/utils/evidenceDisplay.ts:348`.
- Portfolio risk evidence packet generation includes source refs, required evidence, reason codes, confidence cap, and admin diagnostics: `src/services/portfolio_risk_diagnostics.py:533`.
- Backend diagnostic sections include operational details such as sync/import rows, FX pairs/sources, source authority, disabled claims, and reason codes that are useful for internal evidence but unsafe as default consumer copy: `src/services/portfolio_risk_diagnostics.py:739`.

## Consumer UI shown by default

Default Portfolio UI shows user-facing asset, holding, risk, valuation, activity, and ledger surfaces. Pricing/freshness evidence appears in consumer language in these places:

- Position helpers translate fallback/as-of/missing states into `价格可能延迟`, `价格快照`, and `价格更新中`: `apps/dsa-web/src/pages/PortfolioPage.tsx:212`.
- Portfolio-level notice logic maps price fallback, price updating, stale FX, unavailable FX, and limited confidence into short user-safe notices: `apps/dsa-web/src/pages/PortfolioPage.tsx:269`.
- Raw labels containing source authority, provider, cache, raw, debug, JSON, or reason-code vocabulary are dropped before trust chips are built: `apps/dsa-web/src/pages/PortfolioPage.tsx:311`.
- Portfolio derives consumer notice flags from `fxRates`, position fallback/as-of/confidence, and snapshot state fields: `apps/dsa-web/src/pages/PortfolioPage.tsx:2256`.
- Valuation and risk trust strips use sanitized evidence labels and bounded state chips: `apps/dsa-web/src/pages/PortfolioPage.tsx:2393`.
- Holding rows show price snapshot/as-of or delayed fallback explanation, plus trust chips for freshness and limited confidence: `apps/dsa-web/src/pages/PortfolioPage.tsx:2980`.
- The default valuation panel shows `估值与新鲜度`, price snapshot, FX updated time, and a short trust strip: `apps/dsa-web/src/pages/PortfolioPage.tsx:3182`.
- More detailed data notes and trust details are inside a collapsed `<details>` disclosure by default, not a diagnostic wall: `apps/dsa-web/src/pages/PortfolioPage.tsx:3242`.

Existing frontend tests already cover the most important consumer boundary:

- Delayed fallback prices render safe copy and hide raw fallback/source terms: `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx:970`.
- Quote, sync, and fallback sources compress into safe freshness states: `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx:1053`.
- Compact evidence chips hide raw sync/source-authority internals: `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx:1251`.
- Consumer-safe data-quality copy replaces provider setup/remediation wording by default: `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx:1314`.
- Valuation lineage states map to safe copy and raw state tokens stay out of the DOM: `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx:1364`.
- Nested provider/cache/admin diagnostics do not leak into consumer DOM: `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx:1386`.
- FX conversion unavailable keeps native exposure visible and shows a safe notice: `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx:1431`.

## Metadata flow matrix

| Flow | Producer metadata | API/type path | Consumer path | Default consumer output | Hidden/admin-only boundary |
| --- | --- | --- | --- | --- | --- |
| Position price source and fallback | Daily close, broker-sync snapshot, or average-cost fallback are converted into source, label, as-of, fallback flag/reason, and confidence in `src/services/portfolio_service.py:3332` and `src/services/portfolio_service.py:3473`. | `api/v1/schemas/portfolio.py:253`; `apps/dsa-web/src/types/portfolio.ts:92`; `apps/dsa-web/src/api/portfolio.ts:496`. | `PortfolioPage.tsx:212`, `PortfolioPage.tsx:540`, `PortfolioPage.tsx:2980`. | `价格快照`, `价格可能延迟`, `价格更新中`, `截至 <date>`, `置信度有限`. | Raw source ids, raw source labels, fallback reason ids, provider/source ranking, and authority inference must stay hidden. |
| Snapshot FX freshness | FX snapshot rows include rate/date/source/stale/direction, with missing pairs marked unavailable/stale in `src/services/portfolio_service.py:2604`. | `api/v1/schemas/portfolio.py:307`; `apps/dsa-web/src/types/portfolio.ts:139`. | `PortfolioPage.tsx:244`, `PortfolioPage.tsx:2256`, `PortfolioPage.tsx:3182`, `PortfolioPage.tsx:3308`. | `汇率已更新`, `汇率可能延迟`, `汇率暂不可用`, `折算暂不可用`. | Provider/cache/source_direction/source names and missing-pair internals should not appear by default. |
| Portfolio risk/evidence packet | Diagnostics build required evidence, source refs, confidence cap, reason codes, limitation labels, and admin diagnostics in `src/services/portfolio_risk_diagnostics.py:533`. | `api/v1/schemas/portfolio.py:381`; `apps/dsa-web/src/types/portfolio.ts:315`; `apps/dsa-web/src/utils/evidenceDisplay.ts:487`. | `PortfolioPage.tsx:2393`, `PortfolioPage.tsx:3242`. | Bounded trust chips such as observation-only, limited confidence, stale FX, missing cash, or unavailable references after sanitization. | `sourceRefs`, provider names/classes, reason codes, run IDs, admin diagnostics, raw JSON, and backend field names remain admin/internal only. |
| Valuation lineage state | Diagnostics derive valuation state from price fallback, FX stale/unavailable, and cash completeness in `src/services/portfolio_risk_diagnostics.py:895`. | `api/v1/schemas/portfolio.py:400`; `apps/dsa-web/src/types/portfolio.ts:360`. | `PortfolioPage.tsx:373`, `PortfolioPage.tsx:2256`, `PortfolioPage.tsx:3182`. | `估值已更新`, `当前估值可能存在延迟，仅供参考。`, `部分汇率数据暂不可用，估值已暂停更新。`, `现金流水不完整，估值仅供参考。` | Raw state tokens such as `price_fallback` or `fx_fallback_1_to_1` must not be rendered. |
| Collapsed data notes | Full snapshot/evidence payload stays available to page code through `toCamelCase`, then sanitized before display. | `apps/dsa-web/src/api/portfolio.ts:496`; `apps/dsa-web/src/types/portfolio.ts:226`. | `PortfolioPage.tsx:311`, `PortfolioPage.tsx:3242`, `PortfolioPage.tsx:3308`. | Optional consumer-readable notes and trust strips only after expansion. | No raw metadata badge dump, provider/source-authority inference, cache/runtime labels, or maintainer remediation instructions. |

## Product-safe stale and delayed pricing assessment

Stale or delayed pricing can be shown safely today if the UI keeps the current vocabulary and display boundary:

- Safe default language: `价格可能延迟`, `价格更新中`, `截至 <date>`, `已使用最近一次可用数据`, `置信度有限`, `当前估值可能存在延迟，仅供参考`.
- Safe UI pattern: short chip plus one short sentence, with data notes collapsed unless the user expands them.
- Unsafe UI pattern: raw provider/source/fallback badges, source-authority badges, reason-code chips, raw JSON/details, cache/runtime status, or source-quality inference.

This matches the consumer UX contract: consumer pages must use bounded product states, one-line explanations, last-updated context where useful, and must avoid provider names, provider classes, reason codes, raw diagnostics, backend field names, and maintainer remediation language by default (`docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:43`, `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:57`, `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:111`, `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md:196`).

## Browser check

Browser check was cheap enough and was attempted with a task-owned Vite dev server on `http://127.0.0.1:4187`.

| Route | Viewport | Result | Overflow | Console/page errors | Limitation |
| --- | ---: | --- | --- | --- | --- |
| `/zh/portfolio` | `1440x1000` | Auth dialog rendered: `登录后即可进入 持仓管理`. Portfolio content was not mounted. | No page-level horizontal overflow observed. | None observed. | Local live check did not authenticate the route. |
| `/zh/portfolio` | `390x900` | Same auth dialog rendered. Portfolio content was not mounted. | No page-level horizontal overflow observed. | None observed. | Local live check did not authenticate the route. |

Authenticated Portfolio content has existing Playwright coverage at the target desktop/mobile sizes:

- The route smoke defines `1440x1000` and `390x844` viewports: `apps/dsa-web/e2e/portfolio-launch-surface.spec.ts:4`.
- It renders `/zh/portfolio` with an authenticated Portfolio harness and waits for `portfolio-bento-page`: `apps/dsa-web/e2e/portfolio-launch-surface.spec.ts:44`.
- It verifies primary/secondary/activity/manual lanes, holdings/risk panels, no horizontal overflow, no console/page errors, no POST calls, and no forbidden raw/debug/provider/schema leakage: `apps/dsa-web/e2e/portfolio-launch-surface.spec.ts:57`.

## Recommended next task

Recommend exactly one follow-up task:

**T-1087-TEST1: Lock Portfolio consumer pricing and evidence boundary in tests**

Task type: tests-only.

Goal:

- Preserve current Portfolio behavior while strengthening regression coverage around stale/delayed pricing and evidence metadata.
- Add or tighten fixtures that include realistic position price metadata, FX stale/missing rows, `portfolioRiskEvidence.sourceRefs`, reason codes, source classes, and `adminDiagnostics`.
- Assert default Portfolio UI continues to show only consumer-safe pricing/freshness language and never raw provider/source/cache/debug/reason-code/runtime metadata.
- Assert API adapter tests preserve camel-cased metadata availability without implying the consumer UI may display raw fields.
- Do not change UI, types, adapters, backend schema, backend service, provider/cache/runtime, accounting, ledger, or risk semantics.

Recommended write files for that one task:

- `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx`
- `apps/dsa-web/src/api/__tests__/portfolio.test.ts`
- `apps/dsa-web/src/utils/__tests__/evidenceDisplay.test.ts`
- optionally `apps/dsa-web/e2e/portfolio-launch-surface.spec.ts` only if the task also asks for a 390px authenticated smoke assertion

Why not docs-only:

- The current docs contract is adequate; the risk is regression in a broad metadata pipeline, so another docs-only follow-up would not materially improve consumer safety.

Why not adapter/type lock as source:

- The adapter and types currently carry raw metadata that backend/admin consumers may still need. Clipping or narrowing them would be a contract/source change and is larger than necessary for consumer readiness.

Why not narrow frontend UI:

- The UI already has safe default pricing/freshness language, collapsed notes, sanitizer logic, and focused tests. A new UI write would risk creating raw metadata badges or changing the visual contract without a current consumer-visible gap.

## Future write boundaries

Safe future files for the recommended tests-only task:

- `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx`
- `apps/dsa-web/src/api/__tests__/portfolio.test.ts`
- `apps/dsa-web/src/utils/__tests__/evidenceDisplay.test.ts`
- `apps/dsa-web/e2e/portfolio-launch-surface.spec.ts` only if explicit browser proof is requested

Safe files for a later narrow frontend UI task only if a new gap is proven:

- `apps/dsa-web/src/pages/PortfolioPage.tsx`
- `apps/dsa-web/src/components/portfolio/PortfolioTrustStrip.tsx`
- `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx`
- `apps/dsa-web/e2e/portfolio-launch-surface.spec.ts`

Files to avoid unless a later task explicitly authorizes API/contract/backend work:

- `api/v1/schemas/portfolio.py`
- `api/v1/endpoints/portfolio.py`
- `src/services/portfolio_service.py`
- `src/services/portfolio_risk_diagnostics.py`
- `src/services/portfolio_risk_service.py`
- `src/services/fx_rate_service.py`
- `src/repositories/portfolio_repo.py`
- `apps/dsa-web/src/types/portfolio.ts`
- `apps/dsa-web/src/types/portfolio.contract.ts`
- `apps/dsa-web/src/api/portfolio.ts`
- package files, lockfiles, root config, provider/cache/runtime files, broker/order/auth files, scanner/options/backtest files

Behavior boundaries for any future task:

- Do not change portfolio accounting, cash, holdings, P&L, FX conversion, cost basis, ledger import, broker sync, order/auth, or risk calculation semantics.
- Do not infer provider authority or source superiority from evidence metadata.
- Do not dump raw metadata as badges.
- Do not expose provider names/classes, reason codes, cache/runtime/debug/admin diagnostics, raw JSON, backend snake_case field names, or maintainer remediation wording in consumer-default UI.

## Recommended validation plan

For T-1087-TEST1:

```bash
npm --prefix apps/dsa-web run test -- --no-file-parallelism "src/pages/__tests__/PortfolioPage.test.tsx" "src/api/__tests__/portfolio.test.ts" "src/utils/__tests__/evidenceDisplay.test.ts"
DSA_WEB_PLAYWRIGHT_PORT=4187 npm --prefix apps/dsa-web run test:e2e -- "e2e/portfolio-launch-surface.spec.ts"
git diff --check
./scripts/release_secret_scan.sh
```

Use the Playwright command only if the future task touches the e2e smoke or requests 390px browser proof. If the future task remains pure unit/API tests, the focused Vitest command plus final hygiene checks are sufficient.

## Audit status

- Readiness verdict: ready for product-safe stale/delayed pricing display; not ready for raw metadata display.
- Recommended next write: tests-only boundary lock.
- Recommended UI implementation: defer.
- Recommended backend/API/type implementation: defer.
- Final diff expected for this task: this docs artifact only.
