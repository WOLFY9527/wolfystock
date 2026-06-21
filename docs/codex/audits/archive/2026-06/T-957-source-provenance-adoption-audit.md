# T-957 Source Provenance Adoption Audit

Task ID: T-957  
Mode: READ-ONLY-AUDIT with explicit docs-only audit artifact and local commit authorization. No source/runtime/config behavior was changed.

## Executive Verdict

`SourceProvenanceV1` should be adopted first at existing projection seams that
already expose bounded `source/sourceLabel/sourceType/freshness` metadata and
already fail closed on `sourceAuthorityAllowed` / `observationOnly`. The safest
first consumers are:

1. Home evidence packet / citation frame
2. Scanner candidate evidence/readiness/summary
3. Admin/Ops provider matrix and cost/source display surfaces

These seams are already helper-heavy, additive, and consumer-safe. They can
normalize provenance metadata without changing provider routing, score-grade
policy, cache semantics, or frontend IA during the current copy cleanup cycle.

The least safe first consumers are Market Intelligence core runtime payloads,
Liquidity/Rotation score-driving evidence, and Options authority/onboarding
tracks. Those areas already embed source-authority logic in runtime semantics.
Adopting `SourceProvenanceV1` there too early would risk duplicating authority
policy, widening contracts, or subtly changing readiness/score behavior.

## Current Safe Inventory

### Shared helper foundations already present

- `src/services/source_provenance_contract.py` is intentionally inert and
  helper-only. It normalizes `authorityTier`, `freshnessState`, `sourceTier`,
  `fallbackOrProxy`, `observationOnly`, `scoreContributionAllowed`,
  `limitations`, and `nextEvidenceNeeded` without calling providers, caches, or
  DTO runtimes.
- `src/services/market_data_source_registry.py` already canonicalizes
  `sourceType`, `sourceLabel`, and freshness-oriented display metadata across
  `authorized_licensed_feed`, `official_public`, `public_proxy`,
  `unofficial_proxy`, `cache_snapshot`, `fallback_static`, fixture, and
  missing states.

### Provenance-like fields already emitted by surface

- Home: `researchReadiness`, `evidenceCoverageFrame`,
  `singleStockEvidencePacket`, and `home_report_evidence_citation_frame`
  already carry per-domain source/freshness/authority-style metadata.
- Scanner: `scanner_candidate_evidence_v1`, `ResearchReadinessV1`,
  `scanner_candidate_research_summary_v1`, watchlist
  `ohlcv_provenance`, and `scannerContextFrame` already project bounded source
  metadata.
- Market Intelligence: market temperature / briefing / actionability /
  readiness already use `sourceType`, `sourceTier`, `freshness`,
  `sourceAuthorityAllowed`, `sourceAuthorityReason`, and route-rejection state.
- Liquidity / Rotation: evidence inputs, snapshots, and response schemas
  already expose `sourceLabel`, `sourceType`, `freshness`,
  `sourceAuthorityAllowed`, and degradation fields.
- Admin/Ops: provider operations matrix, provider readiness diagnostics, cost
  pricing policy `sourceLabel`, and sanitized provider evidence already expose
  operator-safe source metadata.
- Options: chain/underlying freshness and data quality are live in public
  schemas, while event/expiration/IV-rank source-candidate evidence and
  authority helpers already manage provenance-like evidence families separately.

## Recommended Adoption Order

### Phase 1: helper-only normalization at existing projection seams

Adopt `SourceProvenanceV1` only behind current helper outputs first:

1. Home evidence packet / citation frame
2. Scanner candidate evidence + candidate summary + watchlist `ohlcv_provenance`
3. Admin/Ops provider matrix / pricing policy source displays

Reason:

- these paths are already projection-only;
- they already consume bounded source metadata instead of provider internals;
- they do not own score/ranking/provider-order semantics;
- they can add normalized provenance sidecars with additive tests only.

### Phase 2: additive payload fields on read-only, non-score-driving APIs

After Phase 1 lands cleanly, add optional provenance sidecars to:

1. Home API public response sidecars derived from existing packet/frame
2. Scanner public candidate payload sidecars derived from existing evidence/readiness
3. Admin/Ops diagnostic/readiness payloads that already expose source metadata

Keep these additive and derived-only. No runtime recomputation. No provider
fanout. No cache reads beyond what current payloads already use.

### Phase 3: frontend display mapping only after payloads stabilize

Only after additive payload tests land:

1. map normalized provenance to existing Home/Scanner/Admin compact strips or disclosures;
2. reuse current display copy for freshness / observation-only / fallback / missing;
3. avoid new top-surface card sprawl.

## Seam Classification

| Surface / seam | Current fields / anchor | Classification | Safe adoption note |
| --- | --- | --- | --- |
| Home `single_stock_evidence_packet_v1` | domain `sourceTier`, `providerAuthority`, `freshness`, `fallbackOrProxy`, `missingReasons` | helper-only normalization | Best first seam. Derived-only per-domain `SourceProvenanceV1` entries can be built from existing packet domains. |
| Home `evidenceCoverageFrame` / citation frame | `source_tier`, `source_authority`, `freshness`, citation `authorityLabel` / `freshnessLabel` | helper-only normalization | Safe to normalize for LLM/report evidence references without changing report logic. |
| Home API response sidecar | `researchReadiness`, `evidenceCoverageFrame`, `singleStockEvidencePacket` | additive payload field | Add only after helper contract exists; derive from existing packet/frame, not raw provider data. |
| Scanner candidate evidence frame | per-domain `observationOnly`, `scoreGradeAllowed`, `freshness` | helper-only normalization | Good second seam. Keeps ranking unchanged while normalizing candidate evidence provenance. |
| Scanner candidate summary | `sourceAuthority`, `freshness`, `blockingReasons`, `nextResearchStep` | helper-only normalization | Safe read-model seam; summary already consumes evidence/readiness instead of providers. |
| Watchlist `ohlcv_provenance` | local history `source/source_type/source_label` projection | additive payload field | Safe narrow slice if kept local-OHLCV-only and derived from existing diagnostics. |
| Scanner context frame | top-down `market/liquidity/rotation` context | not safe yet | Context frame pulls from Market Intelligence / Liquidity / Rotation seams whose authority semantics are still protected. |
| Market actionability frame | evidence items with `sourceType/sourceTier/trustLevel/sourceAuthorityAllowed` | not safe yet | Already encodes authority logic. Do not add a second provenance authority layer before a dedicated Market task. |
| Market temperature / briefing runtime inputs | route rejection, authority router, score gating | not safe yet | High risk of duplicating provider-authority logic or changing conclusion gating. |
| Liquidity evidence inputs / snapshots | `sourceLabel/sourceType/freshness/sourceAuthorityAllowed` | not safe yet | These fields are score-driving and tightly coupled to degradation semantics. |
| Rotation summary / theme / member payloads | `source/sourceLabel/sourceType/sourceAuthorityAllowed/evidenceQuality` | not safe yet | Rotation ranking/evidence quality is protected; provenance adoption must not touch ranking lanes or headline eligibility. |
| Admin provider operations matrix | `sourceLabel/sourceType/sourceAuthorityAllowed/sourceFreshnessEvidence` | helper-only normalization | Safe operator seam because service is already read-only/diagnostic-only. |
| Admin pricing policy `sourceLabel` | read-only `sourceLabel` metadata | frontend display mapping | Can later map normalized provenance labels in UI without touching pricing policy semantics. |
| Options public chain/summary/scenario schemas | `source`, `freshness`, `dataQuality`, `optionsResearchReadiness` | not safe yet | Public options surfaces are active consumer-copy work and tightly tied to decision-grade/no-trade semantics. |
| Options expiration/event/IV-rank candidate evidence | provenance families, backing, SLA evidence | helper-only normalization | Safe only as a later options-specific docs/helper task; do not merge with runtime Options readiness now. |

## Field Normalization Target

Normalize the following first, because they already recur across Home,
Scanner, Market, Liquidity/Rotation, Admin, and Options:

### Canonical fields to reuse

- `sourceId`
  - derive from existing `source` or stable synthetic ids such as
    `watchlist.scanner_score_snapshot`
- `sourceLabel`
  - reuse existing display-safe labels, never raw provider payload text
- `sourceTier`
  - map from current `sourceTier` or `sourceType`
- `freshnessState`
  - map current `freshness` / `freshnessClass` / readiness freshness
- `authorityTier`
  - derive from already-decided public state only:
    `score_grade`, `trusted_public`, `stored_snapshot`, `observation_only`,
    `fixture`, `unknown`
- `fallbackOrProxy`
  - derive from existing `isFallback`, proxy source type, or fallback labels
- `observationOnly`
  - derive from existing public flags only, never recompute provider policy
- `scoreContributionAllowed`
  - mirror existing public gating only
- `limitations`
  - translate current missing/degraded reason buckets into bounded provenance
    limitations
- `nextEvidenceNeeded`
  - reuse existing readiness/evidence next-step fields where already present

### Fields that should not be normalized in Phase 1

- raw provider ids or router snapshots
- route rejection internals
- authority basis details that can change runtime meaning
- cache keys, TTL, SWR, refresh status internals
- paid entitlement specifics or credential-derived state

## Do Not Integrate Yet

### 1. Market Intelligence runtime authority paths

Do not adopt `SourceProvenanceV1` directly inside:

- `src/services/market_overview_service.py`
- `src/services/market_decision_semantics.py`
- market briefing / temperature score-input guards
- route-rejection snapshots

Reason:

- these paths already decide `sourceAuthorityAllowed`,
  `scoreContributionAllowed`, and route rejections;
- a second provenance abstraction here is likely to duplicate or drift
  authority logic.

### 2. Liquidity / Rotation score-driving evidence

Do not adopt inside:

- `src/services/liquidity_monitor_service.py`
- `api/v1/schemas/liquidity_monitor.py`
- rotation summary/theme/member ranking payloads
- `themeFlowSignal` / `rotationFamilyRollup` scoring or headline lanes

Reason:

- these seams are part of protected scoring, readiness, and observation-only
  semantics;
- even “metadata-only” edits here can silently change consumer interpretation.

### 3. Options runtime decision/readiness surfaces

Do not adopt yet inside:

- live Options Lab public responses
- scenario / compare / decision runtime payloads
- options readiness gates and no-trading framing

Reason:

- current Options work is still stabilizing consumer-safe copy and gates;
- provenance adoption there should happen later as a dedicated options helper
  slice, not mixed into public runtime surfaces.

## Minimal Post-Cleanup Task Sequence

1. Home helper slice
   - add `SourceProvenanceV1` sidecar builder that consumes existing
     `single_stock_evidence_packet_v1` / coverage-frame inputs only
   - add additive tests
2. Scanner helper slice
   - add candidate-level provenance sidecar builder for evidence/readiness/summary
   - optionally extend watchlist local `ohlcv_provenance` mapping
   - add additive tests
3. Admin/Ops helper slice
   - normalize provider matrix / pricing-policy source display metadata into the
     same provenance vocabulary
   - add additive tests
4. Frontend display slice
   - map normalized provenance to existing compact strips/disclosures on Home,
     Scanner, and Admin only after payloads stabilize

## Later Parallelization Plan

After the current UI cleanup lands, the following tasks can run in parallel:

### Parallel-safe group A

- Home helper normalization
- Scanner helper normalization
- Admin/Ops helper normalization

These are safe in parallel because they touch different projection seams and do
not need shared provider/runtime changes if they agree on one helper contract.

### Serial-only follow-up

- any shared helper contract shape change after the first three tasks start
- any Market Intelligence runtime adoption
- any Liquidity / Rotation runtime adoption
- any Options runtime adoption

Those must serialize because they share authority vocabulary and protected
semantics.

## Guardrails For Future Writes

- Do not change provider routing or default order.
- Do not change score-grade / observation-only / conclusion gating semantics.
- Do not change cache / TTL / SWR / cold-start behavior.
- Do not widen API contracts except additively with focused tests.
- Do not add frontend churn on active consumer copy surfaces until payloads
  settle.
- Prefer derived provenance from existing public fields over new runtime source
  inspection.

## Recommended Next Task

`T-957A Home source provenance sidecar`:
implement a helper-only Home provenance projection from existing
`single_stock_evidence_packet_v1` and `evidenceCoverageFrame`, with additive
tests only and no UI/runtime/provider changes.
