# Data Trust Evidence OS V1 Goal Progress

Status: active goal ledger

Date: 2026-06-11

Branch: `codex/goal-data-trust-evidence-os`

## Goal

Build a private-beta display boundary for evidence, provenance, freshness,
authority, confidence caps, and safety labels across key WolfyStock product
surfaces.

This goal is display-layer and documentation work unless a later checkpoint
explicitly records otherwise. It does not approve public launch, provider
runtime/order/fallback/cache changes, scoring/ranking changes, quota
enforcement, auth/RBAC runtime changes, DB migration/cleanup/restore,
broker/order paths, or external notification sends.

## Canonical Consumer Vocabulary

V1 consumer surfaces should use these bounded states:

| State | Consumer meaning | Raw details that must stay hidden |
| --- | --- | --- |
| `authoritative` | Evidence is usable within the current consumer boundary. | Provider ids, authority internals, route choices. |
| `partial` | Some required evidence is missing or incomplete. | Missing raw field names, reason code arrays. |
| `stale` | Evidence is older than the preferred freshness window. | Cache buckets, stale row codes, refresh internals. |
| `fallback` | A replacement or lower-authority evidence path was used. | Fallback depth, provider attempt order, route rejection. |
| `fixture-demo` | Fixture, demo, dry-run, or mock data is present. | Fixture ids, mock payload details. |
| `synthetic` | Synthetic, inferred, or generated values are present. | Generation internals and raw synthetic fixture names. |
| `unavailable` | Evidence for the module is not available. | Stack traces, endpoint paths, provider payloads. |
| `insufficient` | Evidence is too limited for a stronger conclusion. | Internal blockers and snake_case reason codes. |
| `observation-only` | Output is allowed only as an observation aid. | Score/ranking mechanics or actionability internals. |
| `not-investment-advice` | The surface is not a buy/sell/order instruction. | Broker/order/trade execution internals. |

Admin/operator surfaces may show bounded diagnostics only on explicit admin
routes. Even admin surfaces must avoid secrets, raw provider payloads, raw stack
traces, and unbounded free-form runtime text.

## Existing High-Signal Assets

- `docs/architecture/trust-evidence-snapshot-v1-phase0.md` defines
  `TrustEvidenceSnapshotV1`, consumer/admin separation, badge rules, and raw
  leakage examples.
- `docs/codex/NO_ADVICE_REGRESSION_GUARDS.md` indexes no-advice, raw-provider,
  and browser smoke guards.
- `docs/frontend/validation-playbook.md` defines current frontend validation and
  app-local Playwright invocation.
- `docs/data-reliability/evidence-readiness-matrix.md` records that historical
  readiness tests do not approve provider authority, scoring changes, or broad
  runtime badge semantics.
- `apps/dsa-web/src/utils/trustEvidenceConsumerMapping.ts` maps
  `TrustEvidenceSnapshotV1`-like payloads into bounded consumer labels/badges.
- `apps/dsa-web/src/utils/evidenceDisplay.ts` normalizes scanner, rotation,
  options, backtest, and portfolio evidence summaries.
- `apps/dsa-web/src/utils/trustDisclosure.ts` maps local trust terms into
  disclosure buckets.
- `apps/dsa-web/src/test-utils/consumerRawLeakageGuard.ts` provides reusable
  consumer raw-leak detection for frontend tests.

## Audit 1: Current Display Inconsistencies

Initial audit found that the repository already has useful safe display seams,
but the vocabulary is split across several local models:

1. `TrustEvidenceSnapshotV1` has bounded availability/freshness/source fields,
   but the frontend mapping does not yet expose the full goal vocabulary as a
   shared product display model.
2. `evidenceDisplay.ts` produces posture labels such as `observe_only`,
   `review_required`, and `blocked`, while `trustDisclosure.ts` uses buckets
   such as `fallback`, `stale`, `partial`, and `non-advice`.
3. Home already renders evidence coverage and packet strips, but those strips
   carry local status labels instead of a shared v1 state list.
4. Scanner uses `EvidenceChips` for some candidates, but diagnostic rows pass
   `evidenceSummary={null}` and rely on separate data-quality/provenance strips.
5. Portfolio maps valuation, FX, and risk evidence into safe local trust chips,
   but the local labels are not generated from a shared v1 vocabulary.
6. Options Lab has local state keys such as `UPDATING`, `PARTIAL`,
   `INSUFFICIENT`, and `PAUSED`; these need a display-only bridge to the shared
   vocabulary without changing options recommendation or gate semantics.
7. Liquidity Monitor and Rotation Radar already have consumer-safe copy and
   raw-field suppression tests, but their evidence labels remain surface-local.
8. Admin evidence components can show bounded diagnostics in explicit admin
   areas. Shared components must keep `audience='user'` as the safe default.

## Highest-Impact Shared Display Path

The safest v1 path is:

1. Add a shared frontend utility that converts existing bounded metadata into a
   canonical `DataTrustEvidenceState` display model.
2. Reuse that utility from `EvidenceChips`, `TrustDisclosureChips`, and targeted
   consumer surfaces.
3. Keep all consumer output as labels, descriptions, and chips only.
4. Keep admin diagnostics opt-in and collapsed on admin routes.
5. Add leakage tests that feed adversarial raw provider/debug/reason payloads and
   assert only bounded consumer copy is rendered.

No backend runtime change is required for this path. If backend work becomes
necessary, it must be additive/read-only projection or tests only.

## Surface Review Tracker

| Surface | Current audit status | Initial safe next step |
| --- | --- | --- |
| Home | Evidence coverage/packet strips exist. | Align strip status labels to shared vocabulary and keep no-advice copy. |
| Market Overview | Local market evidence/readiness and TrustDisclosure paths exist. | Reuse shared vocabulary for visible evidence state labels only. |
| Scanner | Evidence summaries exist, but rows are uneven. | Feed existing bounded evidence summaries into a shared chip strip where available. |
| Watchlist | Existing tests guard backend diagnostic leakage. | Add shared no-advice/evidence state chip only if current payload supports bounded input. |
| Portfolio | Local trust chips cover valuation/FX/risk. | Replace duplicate labels with shared state mapping, no accounting changes. |
| Backtest | `EvidenceChips` and readiness summary are present. | Add shared safety label wording, no math or report semantics changes. |
| Options | Local readiness state exists. | Bridge local state to shared display labels, no recommendation/gate changes. |
| Liquidity | Existing consumer-safe copy and degraded tests exist. | Use shared vocabulary for state display, no scoring/provider changes. |
| Rotation | Existing observation/no-trade wording and tests exist. | Use shared vocabulary for state display, no ranking/provider changes. |
| Admin evidence/readiness | Admin-only diagnostics are allowed when bounded. | Verify consumer routes do not import/admin-render raw diagnostics by default. |

## Validation Plan

Always run for each checkpoint:

```bash
git diff --check
./scripts/release_secret_scan.sh --local-only
```

When frontend code changes:

```bash
npm --prefix apps/dsa-web run test -- \
  src/utils/__tests__/trustEvidenceConsumerMapping.test.ts \
  src/test-utils/__tests__/consumerRawLeakageGuard.test.ts \
  src/utils/__tests__/evidenceDisplay.test.ts
npm --prefix apps/dsa-web run typecheck
npm --prefix apps/dsa-web run build:quiet
```

Bounded route smoke candidates:

```bash
DSA_WEB_PLAYWRIGHT_PORT=4181 npm --prefix apps/dsa-web run test:e2e -- \
  e2e/consumer-copy-regression.smoke.spec.ts \
  e2e/consumer-copy-forbidden-vocabulary.smoke.spec.ts \
  e2e/home-scanner-evidence-browser.smoke.spec.ts \
  e2e/secondary-consumer-copy.smoke.spec.ts \
  e2e/public-safety-ai-scanner-options.smoke.spec.ts \
  --project=chromium --workers=1
```

Backend validation is only needed if backend Python files are touched.

## Approval-Required Follow-Ups

Record and continue with safe display/docs/tests work if any improvement needs:

- provider runtime/order/fallback/cache behavior changes;
- scoring, ranking, selection, or confidence-cap semantic changes;
- backtest math or stored result reinterpretation;
- options recommendation/gate semantic changes;
- portfolio accounting, FX valuation, or broker/order/trade changes;
- quota enforcement or auth/RBAC/session runtime changes;
- DB migration, cleanup, restore, or retention changes;
- public launch approval or external notification sending.

## Checkpoint Ledger

- `checkpoint(evidence): audit trust vocabulary`: this document records the
  initial current-state audit, vocabulary, validation plan, and follow-up
  boundaries.
- `checkpoint(evidence): unify shared display layer`: pending.
- `checkpoint(evidence): apply consumer evidence states`: pending.
- `checkpoint(evidence): add leakage and smoke evidence`: pending.
- `feat(evidence): add data trust evidence os v1`: pending.
