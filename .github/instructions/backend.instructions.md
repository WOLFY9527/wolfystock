---
applyTo: "main.py,server.py,src/**/*.py,data_provider/**/*.py,api/**/*.py,bot/**/*.py,tests/**/*.py"
---

# Backend Instructions

- Follow `AGENTS.md`; use `docs/AI_PROJECT_MANUAL.md` for domain boundaries and
  protected-surface context.
- Preserve existing services, repositories, schemas, DTOs, provider adapters,
  cache/fallback semantics, and API compatibility unless the task explicitly
  scopes a change.
- Changes touching config, CLI flags, schedule semantics, API behavior, auth,
  provider runtime, report payloads, broker/accounting, or DB migrations need
  explicit scope and focused validation.
- Data-provider changes must preserve provider priority, normalization behavior,
  timeout/retry expectations, freshness/source labels, and graceful degradation.
- Prefer `./scripts/ci_gate.sh`; otherwise run `python -m py_compile` on changed
  Python files plus the closest deterministic tests.
- Do not let a single provider, notification channel, optional enrichment, or
  external dependency failure break the main analysis flow unless the requirement
  explicitly demands fail-fast behavior.
