# Data Coverage Matrix v1

Status: additive inert contract for future product-surface adoption.

Date: 2026-06-08

This document defines `data_coverage_matrix_v1`, a fail-closed metadata
contract for future WolfyStock product surfaces.

It is intentionally inert. It does not change provider runtime order, fallback
behavior, freshness semantics, MarketCache behavior, API shapes, frontend
surfaces, scoring, ranking, thresholds, storage, or DB behavior.

## Related Contracts

- `docs/data-reliability/provider-source-confidence-contract.md`
- `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`
- `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`

If these documents disagree, use the stricter rule and fail closed until a
future protected-domain task explicitly scopes the semantic change.

## Goal

`data_coverage_matrix_v1` answers, per surface field, what may be observed,
what may contribute to scoring, what may be displayed, and what must stay
observation-only.

The contract must keep these dimensions separate:

- provider/source descriptors
- freshness state
- degraded source state
- source authority
- score contribution
- authority grant
- decision-grade posture
- right-to-display

Provider identity, source type, source tier, freshness, fallback, coverage, or
successful observation must never grant authority by inference.

## Minimum Contract Shape

Each row should carry these fields:

- `contractVersion`
- `surfaceId`
- `routeId`
- `audience`
- `fieldKey`
- `evidenceFamily`
- `providerId`
- `providerLabel`
- `sourceId`
- `sourceLabel`
- `sourceType`
- `sourceTier`
- `freshnessState`
- degraded flags:
  `isFallback`, `isStale`, `isPartial`, `isSynthetic`, `isUnavailable`
- `sourceAuthorityAllowed`
- `scoreContributionAllowed`
- `authorityGrant`
- `decisionGrade`
- `observationOnly`
- `rightToDisplay`

The inert helper also carries these fixed guard fields:

- `diagnosticOnly: true`
- `providerRuntimeCalled: false`
- `networkCallsEnabled: false`
- `marketCacheMutation: false`

## Fail-Closed Rules

The validator must fail closed when any of these are missing or unsafe:

- missing source-authority review
- missing score-contribution review
- missing right-to-display review
- unknown freshness
- fallback source state
- stale source state
- partial coverage state
- synthetic source state
- unavailable source state

Fail-closed output means:

- `authorityGrant = false`
- `decisionGrade = false`
- `observationOnly = true`
- `scoreContributionAllowed = false` for current payload use
- `rightToDisplay` degrades to `limited` or `unavailable`
- consumer-safe projection degrades to bounded product states only

## Separation Rules

The contract must preserve these non-inference boundaries:

- provider/source descriptors do not grant authority
- freshness does not grant authority
- freshness does not grant score contribution
- freshness does not grant decision-grade use
- provider/source descriptors do not grant right-to-display
- right-to-display does not imply score contribution
- source authority does not imply decision-grade use

Any future product surface must explicitly wire those decisions later, with
separate protected-domain approval.

## Consumer-Safe Projection

This v1 helper may expose only bounded consumer product states from
`WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`:

- `AVAILABLE`
- `UPDATING`
- `DELAYED`
- `PARTIAL`
- `INSUFFICIENT`
- `PAUSED`
- `UNAVAILABLE`

Allowed short copy examples:

- `已使用最近一次可用数据。`
- `数据更新中，稍后将自动刷新。`
- `当前信号置信度较低，仅供观察。`
- `部分数据暂不可用，当前评分已暂停。`
- `本模块暂不可用，请稍后重试。`

Forbidden consumer output:

- raw provider names
- raw source tiers/types
- `sourceAuthorityAllowed`
- `scoreContributionAllowed`
- reason codes
- backend snake_case fields
- provider/runtime/cache/API details

## Non-Goals

This task does not authorize:

- wiring Market Overview, Liquidity, Rotation, Scanner, API, or frontend
- changing thresholds, scoring, ranking, provider order, fallback, or
  freshness semantics
- changing DB/storage/runtime behavior
- adding consumer badges or disclosures
- changing API or schema contracts
