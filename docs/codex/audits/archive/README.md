# Codex Audit Archive

Status: cold archive for inactive Codex audit reports.

This folder preserves historical Codex audit provenance after reports no
longer need to occupy the active `docs/codex/audits/` lane. Archival means the
files are retained with their original content and Git history; it is not
deletion and does not remove the historical basis for past task decisions.

## T-1249 First Batch

The first batch moved a small set of older audit reports that were not listed
as `KEEP_ACTIVE_EVIDENCE` in
`docs/codex/audits/archive/2026-06/T-1247-docs-retention-cleanup-audit.md` and had no active
path or basename references in `AGENTS.md`, `docs`, `README.md`, `.github`, or
`.claude`.

| Archived file | Archived location | Why archived |
| --- | --- | --- |
| `T-1009-auth-guard-policy-audit.md` | `docs/codex/audits/archive/T-1009-auth-guard-policy-audit.md` | Inactive historical audit; no active references found. |
| `T-1011-admin-dashboard-ia-audit.md` | `docs/codex/audits/archive/T-1011-admin-dashboard-ia-audit.md` | Inactive historical audit; no active references found. |
| `T-1012-mobile-readability-touch-target-audit.md` | `docs/codex/audits/archive/T-1012-mobile-readability-touch-target-audit.md` | Inactive historical audit; no active references found. |
| `T-1014-post-ux-wave-platform-roadmap-audit.md` | `docs/codex/audits/archive/T-1014-post-ux-wave-platform-roadmap-audit.md` | Inactive historical audit; no active references found. |
| `T-1016-scanner-preexisting-issue-audit.md` | `docs/codex/audits/archive/T-1016-scanner-preexisting-issue-audit.md` | Inactive historical audit; no active references found. |
| `T-1017-auth-route-policy-decision-record.md` | `docs/codex/audits/archive/T-1017-auth-route-policy-decision-record.md` | Inactive historical audit; no active references found. |
| `T-1026-home-route-task-orchestration-write-readiness-audit.md` | `docs/codex/audits/archive/T-1026-home-route-task-orchestration-write-readiness-audit.md` | Inactive historical audit; no active references found. |
| `T-1027-mobile-p1-p2-polish-readiness-audit.md` | `docs/codex/audits/archive/T-1027-mobile-p1-p2-polish-readiness-audit.md` | Inactive historical audit; no active references found. |
| `T-1028-frontend-validation-flake-command-reliability-audit.md` | `docs/codex/audits/archive/T-1028-frontend-validation-flake-command-reliability-audit.md` | Inactive historical audit; no active references found. |
| `T-1039-admin-layout-sidebar-title-consistency-readiness-audit.md` | `docs/codex/audits/archive/T-1039-admin-layout-sidebar-title-consistency-readiness-audit.md` | Inactive historical audit; no active references found. |

Historical provenance is preserved: each archived report keeps its original
content, remains tracked in Git, and can be inspected with `git log --follow`.

## DOCS-003 June 2026 Bulk Collapse

This batch moved older point-in-time Codex audit, readiness, smoke, and
progress reports into `docs/codex/audits/archive/2026-06/`. The files were
retained as historical provenance, not deleted. Exact active-path references
found during the pass were updated to their archive paths.

| Archived file | Archived location | Why archived |
| --- | --- | --- |
| `2026-06/T-892-research-os-product-gap-audit.md` | `docs/codex/audits/archive/2026-06/T-892-research-os-product-gap-audit.md` | Older Research OS point-in-time audit; retained as historical context. |
| `2026-06/T-913-scanner-topdown-data-reliability-audit.md` | `docs/codex/audits/archive/2026-06/T-913-scanner-topdown-data-reliability-audit.md` | Older scanner data-reliability audit; retained as historical context. |
| `2026-06/T-917-scanner-ranking-guardrail-audit.md` | `docs/codex/audits/archive/2026-06/T-917-scanner-ranking-guardrail-audit.md` | Older scanner guardrail audit; retained as historical context. |
| `2026-06/T-918-home-evidence-source-utilization-audit.md` | `docs/codex/audits/archive/2026-06/T-918-home-evidence-source-utilization-audit.md` | Older Home evidence audit; retained as historical context. |
| `2026-06/T-925-home-llm-evidence-input-hardening-audit.md` | `docs/codex/audits/archive/2026-06/T-925-home-llm-evidence-input-hardening-audit.md` | Older Home LLM evidence audit; retained as historical context. |
| `2026-06/T-929-market-intelligence-actionability-audit.md` | `docs/codex/audits/archive/2026-06/T-929-market-intelligence-actionability-audit.md` | Older market-intelligence audit; retained as historical context. |
| `2026-06/T-930-options-lab-productization-audit.md` | `docs/codex/audits/archive/2026-06/T-930-options-lab-productization-audit.md` | Older Options productization audit; retained as historical context. |
| `2026-06/T-935-options-lab-workflow-ia-contract.md` | `docs/codex/audits/archive/2026-06/T-935-options-lab-workflow-ia-contract.md` | Older Options workflow IA artifact; retained as historical context. |
| `2026-06/T-953-react-doctor-remaining-issues-triage.md` | `docs/codex/audits/archive/2026-06/T-953-react-doctor-remaining-issues-triage.md` | Older React Doctor triage; retained as historical context. |
| `2026-06/T-957-source-provenance-adoption-audit.md` | `docs/codex/audits/archive/2026-06/T-957-source-provenance-adoption-audit.md` | Older provenance adoption audit; retained as historical context. |
| `2026-06/T-981-platform-post-iteration-product-architecture-audit.md` | `docs/codex/audits/archive/2026-06/T-981-platform-post-iteration-product-architecture-audit.md` | Older platform architecture audit; retained as historical context. |
| `2026-06/T-987-post-wave-react-doctor-smoke-stability-audit.md` | `docs/codex/audits/archive/2026-06/T-987-post-wave-react-doctor-smoke-stability-audit.md` | Older React Doctor smoke stability report; retained as historical context. |
| `2026-06/T-989-home-state-orchestration-risk-audit.md` | `docs/codex/audits/archive/2026-06/T-989-home-state-orchestration-risk-audit.md` | Older Home orchestration risk audit; retained as historical context. |
| `2026-06/T-990-smoke-fixture-consolidation-audit.md` | `docs/codex/audits/archive/2026-06/T-990-smoke-fixture-consolidation-audit.md` | Older smoke fixture audit; retained as historical context. |
| `2026-06/T-992-large-page-decomposition-audit.md` | `docs/codex/audits/archive/2026-06/T-992-large-page-decomposition-audit.md` | Older large-page decomposition audit; retained as historical context. |
| `2026-06/T-995-bundle-codesplitting-audit.md` | `docs/codex/audits/archive/2026-06/T-995-bundle-codesplitting-audit.md` | Older bundle/code-splitting audit; retained as historical context. |
| `2026-06/WFE-001-optionslab-1440-responsive-sanity-audit.md` | `docs/codex/audits/archive/2026-06/WFE-001-optionslab-1440-responsive-sanity-audit.md` | Older frontend responsive sanity audit; retained as historical context. |
| `2026-06/WFE-002-windows-frontend-validation-parity-audit.md` | `docs/codex/audits/archive/2026-06/WFE-002-windows-frontend-validation-parity-audit.md` | Older Windows frontend validation audit; retained as historical context. |
| `2026-06/WRD-008-react-doctor-next-high-yield-domain-audit.md` | `docs/codex/audits/archive/2026-06/WRD-008-react-doctor-next-high-yield-domain-audit.md` | Older React Doctor planning audit; retained as historical context. |
| `2026-06/wrd-goal-react-doctor-100-progress.md` | `docs/codex/audits/archive/2026-06/wrd-goal-react-doctor-100-progress.md` | Older React Doctor progress ledger; retained as historical context. |
| `2026-06/T-1015-bundle-split-readiness-audit.md` | `docs/codex/audits/archive/2026-06/T-1015-bundle-split-readiness-audit.md` | Older bundle split readiness audit; retained as historical context. |
| `2026-06/T-1021-market-liquidity-rotation-options-authority-provenance-audit.md` | `docs/codex/audits/archive/2026-06/T-1021-market-liquidity-rotation-options-authority-provenance-audit.md` | Older authority/provenance roadmap audit; retained as historical context. |
| `2026-06/T-1037-ui-spacing-card-grid-taxonomy-write-readiness-audit.md` | `docs/codex/audits/archive/2026-06/T-1037-ui-spacing-card-grid-taxonomy-write-readiness-audit.md` | Older UI taxonomy readiness audit; retained as historical context. |
| `2026-06/T-1040-backtest-shell-width-layout-consistency-readiness-audit.md` | `docs/codex/audits/archive/2026-06/T-1040-backtest-shell-width-layout-consistency-readiness-audit.md` | Older Backtest layout readiness audit; retained as historical context. |
| `2026-06/T-1043-ui-postfix-visual-consistency-audit.md` | `docs/codex/audits/archive/2026-06/T-1043-ui-postfix-visual-consistency-audit.md` | Older UI consistency audit; retained as historical context. |
| `2026-06/T-1071-visual-audit-route-shell-reconciliation.md` | `docs/codex/audits/archive/2026-06/T-1071-visual-audit-route-shell-reconciliation.md` | Older visual route-shell reconciliation; retained as historical context. |
| `2026-06/T-1074-admin-system-control-rail-policy-write-readiness-audit.md` | `docs/codex/audits/archive/2026-06/T-1074-admin-system-control-rail-policy-write-readiness-audit.md` | Older admin control-rail readiness audit; retained as historical context. |
| `2026-06/T-1079-watchlist-empty-state-alerts-ia-readiness-audit.md` | `docs/codex/audits/archive/2026-06/T-1079-watchlist-empty-state-alerts-ia-readiness-audit.md` | Older Watchlist IA readiness audit; retained as historical context. |
| `2026-06/T-1082-mobile-visual-overlap-reconciliation-audit.md` | `docs/codex/audits/archive/2026-06/T-1082-mobile-visual-overlap-reconciliation-audit.md` | Older mobile visual reconciliation audit; retained as historical context. |
| `2026-06/T-1247-docs-retention-cleanup-audit.md` | `docs/codex/audits/archive/2026-06/T-1247-docs-retention-cleanup-audit.md` | Earlier retention audit superseded by this bulk collapse pass; retained as provenance. |
