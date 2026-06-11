# Intelligence Report Engine v2 Goal Progress

## Goal

Upgrade WolfyStock report output from freeform text-first reports to structured, evidence-backed research packets while keeping consumer output observation-only and no-advice.

## Scope

- Backend report/evidence composition only.
- Additive DTO/report contract fields only.
- History/schema hydration when a packet is already present.
- Documentation and focused backend regression coverage.

Out of scope:

- Frontend display, `reportNormalizer`, `StandardReportPanel`, and `FullDecisionReportDrawer` adoption.
- Provider runtime changes.
- AI model routing, quota, or cost enforcement changes.
- Broker, order, trade, or personalized investment-advice behavior.
- Raw prompts, provider payloads, secrets, or internal debug payloads in UI/logs.

## Checkpoints

- `checkpoint(report): design evidence packet v2` - complete.
- `checkpoint(report): add safe composer tests` - complete.
- `checkpoint(report): backend packet composer/schema/history hydration salvage` - complete.
- `checkpoint(report): add focused backend regression evidence` - complete.
- `checkpoint(report): add frontend report display` - deferred.
- final `feat(report): add intelligence report engine v2` - experimental / not merge-ready as a broad goal.

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

When the internal opt-in guard is enabled, the packet is emitted as `intelligencePacket` on:

- report top-level payload
- `report.meta`
- `report.details.analysis_result`
- `report.details.standard_report`

Runtime emission is guarded and default-off. `_build_report_payload` and normal `_build_analysis_response` behavior do not emit `intelligencePacket` unless the explicit internal opt-in guard is enabled. When opt-in is enabled, these locations receive an advisory, JSON-safe packet.

The API history schema also hydrates `intelligencePacket` from `details.analysis_result` to the top level and meta when a packet is already present, matching the existing Home evidence sidecar pattern. This hydration is additive and does not imply frontend display completion.

## Safety Rules

- `consumerActionBoundary` remains `no_advice` or stricter observation states.
- `noAdviceBoundary` is explicit.
- Unsafe conclusion text is sanitized before consumer display.
- Observation-only, stale, fallback, missing, synthetic, or non-score-grade evidence caps confidence and prevents high-confidence conclusions.
- Provider/source metadata is consumed only from existing readiness/provenance sidecars.
- Raw query IDs, raw source IDs, debug refs, prompts, provider payload refs, stack traces, secrets, and internal diagnostic tokens are not emitted in the packet fields.
- The builder imports no provider clients, HTTP clients, runtime config, model routing, or LiteLLM modules.

## Frontend Display

Deferred. No frontend completion is claimed in this backend salvage checkpoint.

Deferred frontend work includes:

- `reportNormalizer` packet extraction and normalization.
- `StandardReportPanel` structured packet display.
- `FullDecisionReportDrawer` structured packet display.
- Browser/responsive validation for any future UI adoption.

## Regression Evidence

Added tests cover:

- pure JSON-safe backend packet composition
- required v2 structured sections
- unsafe text and unsafe evidence cannot become high-confidence conclusions
- missing/stale/fallback evidence caps confidence
- default-off runtime emission from `_build_report_payload` / normal analysis responses
- explicit opt-in packet emission
- raw query/source/debug/prompt/provider-payload/stack/internal diagnostic leakage guards
- API history schema hydration from `details.analysis_result`
- legacy `IntelligenceReportPacketV2` hydration drops or rewrites `sourceId`, `source_id`,
  provider, route, debug, and internal source identifier variants before exposing hydrated
  top-level or `meta.intelligencePacket` packets

Post-fix local validation on 2026-06-11:

- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -p no:cacheprovider tests/test_intelligence_report_packet.py tests/test_analysis_api_contract.py tests/services/test_analysis_research_readiness_projection.py -q` - 67 passed
- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m py_compile src/services/intelligence_report_packet.py src/services/analysis_service.py api/v1/schemas/analysis.py api/v1/schemas/history.py api/v1/schemas/home_evidence.py` - passed

## Remaining Quality Gaps

- Full report quality still depends on upstream evidence sidecars being populated consistently.
- The v2 packet is a normalized projection; it does not improve provider coverage or source authority by itself.
- Existing legacy strategy fields remain for compatibility and must continue to pass consumer-safe projection tests.
- Frontend display remains deferred and requires a separate scoped implementation with browser smoke.
