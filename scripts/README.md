# Scripts Index

This index exists to reduce helper duplication and to make evidence-related
scripts easier to find. Unless a script explicitly says otherwise, treat it as
a local operator/helper tool, not as automatic release approval.

Release/evidence scripts in this directory are designed around sanitized,
synthetic, or operator-supplied inputs. Their outputs are examples or local
checks unless a human operator attaches accepted evidence through the documented
review flow.

## Release gate / summary

- `release_gate_summary.sh`: prints a release gate summary and optional
  sanitized GO/NO-GO JSON. Informational only; does not approve a release or
  run the full gate.
- `rollback_rehearsal_evidence.py`: validates sanitized rollback dry-run
  rehearsal evidence offline. It does not approve launch, deploy, mutate git
  history, or touch databases.
- `ci_gate_fast.sh`: changed-file-focused local gate for quick iteration.
- `ci_gate_profile.sh`: profiles gate runtime; not a substitute for
  `ci_gate.sh`.
- `ci_gate.sh`: full backend local gate.
- `task_preflight.sh`: repository/branch/dirty-state preflight helper.

## Secret scan

- `release_secret_scan.sh`: release-oriented secret scan across branch, staged,
  worktree, and untracked text files.
- `security_scan.sh`: broader local security scan wrapper for secret scan,
  Bandit, optional dependency audit, and optional container scan.

## Production config readiness

- `production_config_readiness.py`: validates a sanitized production-config
  contract without reading real `.env` values or printing secrets.

## Launch acceptance evidence

- `launch_acceptance_evidence.py`: validates sanitized launch-acceptance
  evidence packs for public launch review.

## Operator evidence workflow

- `operator_evidence_template_pack.py`: generates sanitized JSON templates for
  operator evidence categories. Operators must replace placeholders with
  sanitized evidence before review; generated templates are not real evidence.
- `provider_operator_evidence_check.py`: validates sanitized provider operator
  evidence offline.
- `restore_pitr_operator_evidence_check.py`: validates sanitized real
  restore/PITR operator evidence offline; it does not execute restore commands.
- `security_operator_acceptance_check.py`: validates sanitized MFA/RBAC
  operator acceptance evidence offline.
- `quota_operator_evidence_check.py`: validates sanitized quota/budget operator
  evidence offline and does not send notifications.
- `staging_ingress_operator_evidence_check.py`: validates sanitized staging
  ingress operator evidence offline and does not make network calls.
- `ws2_sse_operator_decision_check.py`: validates sanitized WS2/SSE topology
  operator decision evidence offline.
- `config_snapshot_evidence_check.py`: validates sanitized config snapshot
  evidence offline without reading raw `.env` values.
- `manual_release_approval_evidence_check.py`: validates sanitized manual
  release review-record evidence while keeping release approval external and
  manual.
- `operator_evidence_manifest_check.py`: creates and verifies checksum
  manifests for sanitized operator artifact files without printing raw artifact
  bodies.
- `operator_evidence_bundle_check.py`: aggregates already-sanitized domain
  validator summaries for reviewer convenience. It does not replace real
  operator artifacts or approve launch.
- `release_review_report_render.py`: renders an offline Markdown review report
  from sanitized summary JSON. The report is informational only and cannot
  approve launch.
- `evidence_safety.py`: internal helper module for sanitized labels and JSON
  traversal used by offline evidence validators.

## Backup / restore / PITR

- `backup_restore_drill_check.sh`: dry-run PostgreSQL backup/restore/PITR
  preflight plus validation of optional sanitized real-restore evidence.

## Staging ingress smoke

- `staging_ingress_smoke.py`: safe-by-default staging ingress preflight; only
  performs live HTTP checks when explicitly opted in. It also accepts sanitized
  operator evidence JSON for offline validation.

## Incident response evidence

- `incident_response_evidence.py`: validates sanitized incident-response and
  auditability evidence for launch review.

## Runtime verification and support diagnostics

- `database_doctor.py`: CLI entrypoint for the database doctor bundle.
- `database_doctor_smoke.py`: smoke entrypoint for the split database doctor
  harness.
- `verify_runtime_writes.py`: local write-through verification against a
  running backend and local database; generates report artifacts.
- `check_ai_assets.py`: validates AI-governance asset relationships required by
  repo policy.
- `clean_test_history.py`: removes `analysis_history` rows marked as test data.

## Backtest and execution-trace helpers

- `auto_trace_check.py`: acceptance checks for exported deterministic execution
  traces.
- `run_execution_trace_scenarios.py`: runs deterministic backtest scenarios and
  exports acceptance tables.
- `backtest_smoke_support.py`: shared helpers for backtest smoke scripts.
- `smoke_backtest_rule.py`: canonical rule-backtest API smoke.
- `smoke_backtest_standard.py`: canonical standard-backtest API smoke.
- `seed_canonical_history_browser_check.py`: seeds a deterministic analysis
  history row for browser verification.

## Benchmarks and targeted local runners

- `benchmark_portfolio_snapshot.py`: synthetic WS2 portfolio snapshot benchmark
  harness.
- `ws1_baseline_capture.py`: reproducible WS1 baseline capture harness.
- `run_wolfystock_p2.py`: CLI wrapper for the WolfyStock P2 local-parquet
  runner.
- `run_wolfystock_p3.py`: CLI wrapper for the WolfyStock P3 local-parquet
  runner.

## Data/index utilities

- `generate_index_from_csv.py`: builds frontend stock index data from CSV.
- `generate_stock_index.py`: builds frontend stock index data from the internal
  mapping.

## Build and desktop packaging

- `build-all-macos.sh`: macOS wrapper for backend + desktop builds.
- `build-all.ps1`: Windows wrapper for backend + desktop builds.
- `build-backend-macos.sh`: macOS backend packaging flow.
- `build-backend.ps1`: Windows backend packaging flow.
- `build-desktop-macos.sh`: macOS Electron packaging flow.
- `build-desktop.ps1`: Windows Electron packaging flow.
- `run-desktop.ps1`: Windows dev-mode desktop launcher.

## Other

- `__init__.py`: package marker for importing helpers from `scripts/`.
