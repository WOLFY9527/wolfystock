# WolfyStock AI And LLM Docs

Status: current AI/LLM domain entry point.

Use this lane before changing AI decision logic, LLM provider configuration,
prompt/output cache behavior, image stock extraction prompt docs, LLM cost
instrumentation, or report language safety.

## Current Authority

- [AI Decision Engine](../ai-decision-engine.md)
- [LLM Config Guide](../LLM_CONFIG_GUIDE.md)
- [Image Extract Prompt](../image-extract-prompt.md)
- [LLM External API Cost Audit](../audits/llm-external-api-cost-audit.md)
- [LLM Instrumentation Validation Plan](../audits/llm-instrumentation-validation-plan.md)
- [LLM Provider Duplicate Cost Metrics Design](../audits/llm-provider-duplicate-cost-metrics-design.md)
- [LLM Report Output Cache Design](../audits/llm-report-output-cache-design.md)
- [Cost/Quota/Observability Index](../audits/index-cost-quota-observability.md)

## Current Rules

- Report decision language should be analytical, conditional, and no-advice.
- Raw prompts, provider/model routing, LLM traces, and retry diagnostics stay
  behind appropriate operator or developer detail.
- Cost/quota instrumentation must distinguish observational counters from exact
  billing claims.
- Prompt or report-structure changes must be checked against upstream inputs,
  downstream consumers, and notification/report rendering behavior.
