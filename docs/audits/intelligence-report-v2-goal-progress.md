# Intelligence Report Engine v2 Goal Progress

## Goal

Upgrade WolfyStock report output from freeform text-first reports to structured, evidence-backed research packets while keeping consumer output observation-only and no-advice.

## Scope

- Backend report/evidence composition only.
- Additive DTO/report contract fields only.
- Frontend structured packet display only.
- Documentation and focused regression coverage.

Out of scope:

- Provider runtime changes.
- AI model routing, quota, or cost enforcement changes.
- Broker, order, trade, or personalized investment-advice behavior.
- Raw prompts, provider payloads, secrets, or internal debug payloads in UI/logs.

## Checkpoints

- `checkpoint(report): design evidence packet v2` - complete.
- `checkpoint(report): add safe composer tests` - complete.
- `checkpoint(report): add frontend report display` - complete.
- `checkpoint(report): add regression evidence` - in progress.
- final `feat(report): add intelligence report engine v2` - pending final validation.

## Contract

New additive contract version:

- `intelligence_report_packet_v2`

Structured packet sections:

- `thesis`
- `evidence`
- `counterEvidence`
- `missingData`
- `confidence`
- `sourceAuthority`
- `freshness`
- `scenarioRisks`
- `nextVerificationSteps`

The packet is emitted as `intelligencePacket` on:

- report top-level payload
- `report.meta`
- `report.details.analysis_result`
- `report.details.standard_report`

The API history schema also hydrates `intelligencePacket` from `details.analysis_result` to the top level and meta, matching the existing Home evidence sidecar pattern.

## Safety Rules

- `consumerActionBoundary` remains `no_advice` or stricter observation states.
- `noAdviceBoundary` is explicit.
- Unsafe conclusion text is sanitized before consumer display.
- Observation-only, stale, fallback, missing, synthetic, or non-score-grade evidence caps confidence and prevents high-confidence conclusions.
- Provider/source metadata is consumed only from existing readiness/provenance sidecars.
- The builder imports no provider clients, HTTP clients, runtime config, model routing, or LiteLLM modules.

## Frontend Display

Structured packet UI is rendered through whitelist fields, not raw Markdown:

- `StandardReportPanel` shows an Intelligence packet panel before the chart.
- `FullDecisionReportDrawer` adds a compact structured packet section to the full report.
- `reportNormalizer` camelizes and extracts `intelligencePacket` from top-level, meta, standard report, details, analysis result, raw result, persisted report, and nested report payload paths.

## Regression Evidence

Added tests cover:

- pure JSON-safe backend packet composition
- required v2 structured sections
- unsafe text and unsafe evidence cannot become high-confidence conclusions
- missing/stale/fallback evidence caps confidence
- API history schema hydration from `details.analysis_result`
- frontend normalizer snake/camel packet extraction
- frontend structured packet rendering without legacy trade-plan labels

## Remaining Quality Gaps

- Full report quality still depends on upstream evidence sidecars being populated consistently.
- The v2 packet is a normalized projection; it does not improve provider coverage or source authority by itself.
- Existing legacy strategy fields remain for compatibility and must continue to pass consumer-safe projection tests.
- Broader browser smoke is still useful after final build validation to inspect responsive layout and copy density.
