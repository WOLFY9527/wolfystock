# Scripts Index

This file documents how helper scripts are organized today without moving or
renaming them. Use it as a discoverability index first, not as a replacement
for each script's own `--help`, header comments, or workflow definition.

Unless a script explicitly says otherwise, treat it as a local operator or
developer tool. A documented script is not automatic release approval, and a
release/evidence helper does not become production-safe just because it lives
under `scripts/`.

## Taxonomy

### CI-critical

These scripts are directly referenced by blocking or policy-enforcing CI jobs,
or are invoked by scripts that CI treats as required:

- `check_ai_assets.py`: required by the `ai-governance` job in
  `.github/workflows/ci.yml`. Verifies `AGENTS.md` / `CLAUDE.md` /
  `.github/copilot-instructions.md` / `.github/instructions/*.instructions.md`
  / `.claude/skills/` relationships. Safe usage: local read-only policy check;
  it should not rewrite files.
- `ci_gate.sh`: required by the `backend-gate` job in
  `.github/workflows/ci.yml` and by `docker-publish.yml`. Runs
  `task_preflight.sh`, critical flake8 coverage, targeted `py_compile`, root
  `test.sh` deterministic checks, and `pytest -m "not network"`. Safe usage:
  full local backend gate before push/PR; expect it to execute tests, not just
  static parsing.
- `task_preflight.sh`: called by `ci_gate.sh`. Prints branch, upstream, dirty
  file summary, and recent commits so local/CI runs are easier to interpret.
  Safe usage: read-only repository state snapshot.

### Local/dev-only or iterative helpers

These scripts are primarily for local diagnosis, development loops, smoke
checks, or packaging work. Some may appear in non-blocking workflows, but they
are not the main required CI gate:

- Root `test.sh`: scenario runner for `main.py` smoke flows. It is referenced by
  `ci_gate.sh` for deterministic `code` / `yfinance` checks and by
  `.github/workflows/network-smoke.yml` for non-blocking `quick` smoke. Safe
  usage: run a named scenario only; it executes the app, so prefer targeted
  modes over `all`.
- `ci_gate_fast.sh`: faster changed-file-focused iteration gate. Safe usage:
  local feedback loop only; it explicitly does not replace `ci_gate.sh`.
- `ci_gate_profile.sh`: measures gate runtime. Safe usage: profiling helper
  only; do not use it as evidence that the real gate passed.
- `dev_start_backend.sh`: local backend launcher that prefers a repo-local
  virtualenv and can restart a busy port only when explicitly asked. Safe
  usage: developer startup helper, not a deployment entrypoint.
- `database_doctor.py` / `database_doctor_smoke.py`: local database doctor
  entrypoints.
- `verify_runtime_writes.py`: local write-through verification against a
  running backend/database.
- `clean_test_history.py`: cleans rows already marked as test data.
- Backtest, benchmark, and trace helpers such as
  `run_execution_trace_scenarios.py`, `smoke_backtest_standard.py`,
  `smoke_backtest_rule.py`, `benchmark_portfolio_snapshot.py`, and
  `ws1_baseline_capture.py`: local analysis/debug aids rather than CI policy
  gates.
- Data/index utilities such as `generate_index_from_csv.py` and
  `generate_stock_index.py`: content/build helpers for generated index data.

### Release/deploy/operator workflows

These scripts support release review, secret scanning, packaging, staging, or
sanitized operator evidence flows. They should be run deliberately and with the
relevant runbook context:

- `release_secret_scan.sh`: release-oriented secret scan across branch diff,
  staged files, worktree files, and untracked text files. Safe usage: local
  pre-release or pre-push credential check; it scans text content and exits
  non-zero on findings, but does not rewrite files.
- `security_scan.sh`: broader local security wrapper around secret scanning,
  Bandit, optional dependency audit, and optional container scanning. Note:
  `.github/workflows/security-scan.yml` currently runs GitHub-native tools
  directly and only watches this file for workflow triggers; it does not call
  `security_scan.sh` itself.
- `release_gate_summary.sh`: informational release summary and optional
  sanitized GO/NO-GO JSON. Safe usage: summarize evidence posture; it does not
  approve a release and does not run the full backend gate by default.
- `production_config_readiness.py`, `launch_acceptance_evidence.py`,
  `incident_response_evidence.py`, and the `*_operator_*` / `*_evidence_*`
  validators: offline validation of sanitized release/operator artifacts. Safe
  usage: validate externally prepared sanitized evidence only; they are not
  substitutes for human release approval.
- `staging_ingress_smoke.py`: safe-by-default staging ingress preflight with
  live HTTP checks only when explicitly enabled.
- `backup_restore_drill_check.sh` and `release_restore_rollback_drill.py`:
  restore/PITR and rollback evidence helpers; review each script's flags
  carefully before use.
- Desktop packaging scripts:
  `build-all-macos.sh`, `build-backend-macos.sh`, `build-desktop-macos.sh`,
  `build-all.ps1`, `build-backend.ps1`, `build-desktop.ps1`, `run-desktop.ps1`.
  These are referenced by `.github/workflows/desktop-release.yml` for Windows
  and macOS artifact builds. Safe usage: packaging/build helpers; they install
  dependencies, build frontend assets, package the backend, and invoke Electron
  builders, so expect generated artifacts and local build output changes.

## Important Entry Points

### Backend gate stack

- `./scripts/ci_gate.sh`
  Purpose: canonical local backend gate and the same high-level check CI treats
  as blocking.
- `./scripts/task_preflight.sh`
  Purpose: repository state preflight printed at the start of the backend gate.
- `python scripts/check_ai_assets.py`
  Purpose: AI-governance policy check required by CI before backend validation.

Recommended usage order for local validation:

1. `python scripts/check_ai_assets.py`
2. `./scripts/ci_gate.sh`

### Secret and release checks

- `./scripts/release_secret_scan.sh`
  Purpose: focused credential/secret hygiene check before release or push.
- `./scripts/release_gate_summary.sh`
  Purpose: summarize release evidence posture without mutating release state.

### Frontend design and UX checks

Frontend-specific script entrypoints live under `apps/dsa-web/scripts/`, not
under this directory, but they are part of the same tooling surface:

- `npm run check:design`
  From `apps/dsa-web/package.json`, runs
  `apps/dsa-web/scripts/check-design-constitution.mjs`.
  Purpose: Node-based design constitution scan over frontend source files, with
  some checks delegated to `scripts/check_frontend_design_constitution.py`.
- `python scripts/check_frontend_design_constitution.py`
  Purpose: Python-side design constitution guard used by the frontend scanner.
- `npm run test:smoke`
  From `apps/dsa-web/package.json`, runs
  `apps/dsa-web/scripts/run-smoke.sh`.
  Purpose: build the web app, reuse or start a backend, launch a local preview,
  then run Playwright smoke flows.
- `apps/dsa-web/scripts/run-full-ux-verification.mjs` and
  `apps/dsa-web/scripts/verify-browser-flows.mjs`
  Purpose: richer browser/UX verification helpers for local investigation.

Safe usage notes:

- Design checks are policy/style guardrails, not backend correctness tests.
- Smoke/UX scripts launch local services and browsers; expect logs and temp
  artifacts.

### Desktop build flow

Desktop packaging logic is intentionally split:

- `build-all-macos.sh` -> `build-backend-macos.sh` ->
  `build-desktop-macos.sh`
- `build-all.ps1` -> `build-backend.ps1` -> `build-desktop.ps1`

This mirrors `.github/workflows/desktop-release.yml`, which uses the wrapper
scripts as the workflow entrypoint instead of calling Electron or PyInstaller
directly in YAML.

## Workflow And Package References

The fastest way to tell whether a script is "policy-critical" or "just a local
helper" is to check who calls it:

- `.github/workflows/ci.yml`
  Calls `python scripts/check_ai_assets.py` and `./scripts/ci_gate.sh`.
- `.github/workflows/network-smoke.yml`
  Calls root `./test.sh quick --no-notify` as a non-blocking smoke check.
- `.github/workflows/desktop-release.yml`
  Calls `scripts/build-all.ps1` on Windows and `scripts/build-all-macos.sh` on
  macOS.
- `apps/dsa-web/package.json`
  Exposes `npm run check:design` and `npm run test:smoke`, which point into
  `apps/dsa-web/scripts/`.
- `.github/workflows/security-scan.yml`
  Watches `scripts/security_scan.sh` in path filters but currently uses
  GitHub-native scanners directly rather than invoking the local wrapper.

## Related Helpers By Topic

### Governance and repository policy

- `check_ai_assets.py`
- `task_preflight.sh`

### Backend verification

- `ci_gate.sh`
- `ci_gate_fast.sh`
- `ci_gate_profile.sh`
- Root `test.sh`

### Frontend verification

- `scripts/check_frontend_design_constitution.py`
- `apps/dsa-web/scripts/check-design-constitution.mjs`
- `apps/dsa-web/scripts/run-smoke.sh`
- `apps/dsa-web/scripts/run-full-ux-verification.mjs`
- `apps/dsa-web/scripts/verify-browser-flows.mjs`

### Release and security

- `release_secret_scan.sh`
- `security_scan.sh`
- `release_gate_summary.sh`
- `production_config_readiness.py`
- `launch_acceptance_evidence.py`
- `incident_response_evidence.py`

### Desktop packaging

- `build-all-macos.sh`
- `build-backend-macos.sh`
- `build-desktop-macos.sh`
- `build-all.ps1`
- `build-backend.ps1`
- `build-desktop.ps1`
- `run-desktop.ps1`

## Notes

- This index intentionally does not move scripts or redefine ownership
  boundaries.
- When a script header, `--help`, or workflow definition disagrees with this
  file, trust the executable source and update this index in the same change.
- `__init__.py` remains a package marker for importing helper modules from
  `scripts/`.
