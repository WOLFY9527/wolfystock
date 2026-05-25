# WolfyStock Admin Maintenance OS

Status: current frontend IA contract for admin and maintenance-facing routes.

This document defines how WolfyStock admin surfaces translate backend
diagnostics into operator-readable maintenance workflows. It is a frontend
information architecture contract, not a backend semantics change.

## Purpose

Admin and ops pages currently expose too much developer-facing diagnostic detail
in the primary viewport. The goal of the Admin Maintenance OS contract is to
convert diagnostic payloads into administrator maintenance workflows that answer
the operational question first and defer raw evidence until the operator asks
for it.

The frontend must present a maintainable, low-noise operating surface for
routes such as Market Overview, Liquidity Monitor, Rotation Radar, Provider
Ops, and System Settings. Raw backend fields remain available, but only through
progressive disclosure.

## Core Principle

Primary UI is for operation. Diagnostics are on demand.

Default page design must assume the reader is an administrator trying to decide
whether the system is usable, what is degraded, and what action is required. It
must not assume the reader wants raw provider trees, JSON blobs, or internal
reason-code ladders in the first viewport.

## Default Page Questions

Every admin or maintenance-facing page should answer these questions in order:

1. Is the system usable?
2. What is degraded or unavailable?
3. What modules are affected?
4. What should the admin do next?

If the page cannot answer those four questions in the first viewport, the page
is too diagnostic-heavy.

## Five-Layer Information Hierarchy

### L0 Page Status

The top-most page state answers whether the route is operational right now.

- One page verdict only.
- Example outputs: `System usable`, `Usable with degraded modules`,
  `Blocked by missing provider authorization`.
- Must include a short action hint when degraded or blocked.

### L1 Module Status Strip

The next layer is a compact strip of module-level status chips.

- Use bounded labels for major modules only.
- Show which modules are live, degraded, blocked, stale, or local.
- Do not render verbose backend explanations inline in the strip.

### L2 Actionable Issue List

This layer contains the ranked list of issues that need operator action.

Each issue row should answer:

- what is affected;
- why it matters operationally;
- what the admin should do next;
- whether the issue blocks scoring, availability, or freshness only.

Issue rows should be written in operator language, not payload language.

### L3 Inspector Drawer

Detailed explanation belongs in an inspector drawer or equivalent bounded side
panel.

The drawer may include:

- per-module diagnostic summary;
- provider/source trust explanation;
- missing prerequisites;
- limited reason-code mapping;
- current recommendation and escalation path.

The drawer is the default destination for click-through investigation. It is
not the default page state.

### L4 Raw Diagnostics

Raw diagnostics are still allowed, but only at the final disclosure layer.

Examples:

- raw reason codes;
- raw provider class names;
- schema field names;
- JSON payload excerpts;
- debug traces;
- implementation-only timing or fallback metadata.

L4 must stay collapsed by default.

## Status Vocabulary

Admin surfaces should use a stable, shared status vocabulary:

- `LIVE`: usable and current enough for normal operation.
- `DEGRADED`: partial functionality or reduced confidence; route still usable.
- `BLOCKED`: required capability unavailable; action is required before normal
  operation.
- `STALE`: data available but outside freshness target.
- `PROXY`: visible through a proxy, fallback, or reduced-authority source.
- `MISSING`: expected capability or source is unavailable.
- `DISABLED`: intentionally turned off by policy, config, or safety rule.
- `LOCAL`: available only from local cache, local runtime, or non-shared
  environment state.

Status words should stay short and repeatable. Do not invent page-local status
taxonomies for the same underlying meanings.

## Human Translation Rules

Backend booleans and diagnostic flags must be translated into operator-readable
language before they reach the primary UI.

Required translations:

- `sourceAuthorityAllowed=false` -> `source is not authorized for scoring`
- `scoreContributionAllowed=false` -> `does not participate in scoring`
- `observationOnly=true` -> `observation only`

Additional translation rules:

- Prefer operational meaning over field names.
- Explain blocked scoring, degraded freshness, and missing authorization as
  outcomes, not implementation trivia.
- Avoid exposing raw snake_case fields outside the inspector drawer or raw
  diagnostics disclosure.
- If multiple backend flags explain the same operator outcome, compress them
  into one human sentence.

## Page Contract

### Provider Ops / System Settings

These pages are the canonical maintenance surfaces.

- L0 should answer whether the platform is ready for normal operation.
- L1 should summarize provider classes, auth state, key integrations, and local
  versus shared runtime boundaries.
- L2 should rank actionable setup, entitlement, freshness, and authorization
  gaps.
- L3 should explain why a provider is degraded, proxy-only, observation-only,
  or blocked from scoring.
- L4 may expose sanitized raw provider diagnostics and JSON.

These pages may be denser than product routes, but density is not permission to
show everything at once.

### Market Overview

Market Overview is not a provider debugger.

- L0 should answer whether the market state is readable and trustworthy enough
  for observation.
- L1 should summarize major macro/market modules.
- L2 should call out missing or stale macro lanes, unavailable official series,
  or observation-only proxies.
- L3 should show freshness/source reasoning for the selected lane.
- L4 may reveal raw provenance metadata and provider diagnostics.

The page should tell the admin which market lenses are degraded, not dump all
source evidence in the top viewport.

### Liquidity Monitor

- L0 should answer whether liquidity evidence is usable, degraded, or blocked.
- L1 should summarize the major liquidity modules and scoring readiness.
- L2 should highlight inputs that are proxy-only, missing authorization, or
  excluded from scoring.
- L3 should explain which requirements are fulfilled, missing, or capped.
- L4 may expose the full coverage diagnostics payload.

The primary story is operational liquidity readiness, not raw indicator field
inspection.

### Rotation Radar

- L0 should answer whether headline rotation evidence is usable.
- L1 should summarize headline lanes, observation lanes, and provider health.
- L2 should call out when only taxonomy/fallback/proxy evidence is available.
- L3 should explain why a theme is headline-ineligible, observation-only, or
  provider-blocked.
- L4 may show provider activation diagnostics and request window metadata.

The admin should understand whether the radar can support a reliable rotation
read, not just whether Alpaca or a fallback adapter produced partial payloads.

### Scanner / Watchlist

- L0 should answer whether the list is usable for observation.
- L1 should summarize candidate quality, freshness, and scoring readiness.
- L2 should highlight missing evidence families, degraded inputs, or local-only
  state that affects candidate interpretation.
- L3 should explain per-candidate trust or degradation in a bounded panel.
- L4 may expose raw reason families and provider/debug details.

Default copy should translate scoring exclusions and data gaps into observation
language instead of developer debug phrasing.

### Backtest

- L0 should answer whether the result is readable and trustworthy enough for
  evaluation.
- L1 should summarize run status, evidence quality, and result availability.
- L2 should call out missing assumptions, stale stored results, degraded helper
  evidence, or blocked support artifacts.
- L3 should explain run assumptions, evidence quality, and export readiness.
- L4 may expose trace JSON, raw support bundle metadata, and low-level helper
  diagnostics.

Backtest pages should foreground result interpretation and reliability, not raw
trace controls.

## Writing Rules For Future UI Work

- Lead with operator state, impact, and next action.
- Keep backend semantics intact while translating them into maintenance
  language.
- Move implementation-facing detail into the inspector drawer or raw disclosure.
- Prefer one clear operational sentence over multiple repeated reason fragments.
- If the first viewport reads like a developer debug console, the page violates
  this contract.
