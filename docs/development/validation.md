# Validation And Evidence

> Status: Canonical command reference
> Scope: selecting and running repository validation without changing gate policy
> Policy owner: [`AGENTS.md`](../../AGENTS.md)

`AGENTS.md` owns completion evidence tiers, protected-domain gates, Git policy,
and the distinction between passed, failed, skipped, unavailable, and not run.
This document routes contributors to the current commands. Tests, scripts,
workflows, and validation manifests remain the executable truth.

## Minimum Selection

| Change | Focused validation |
| --- | --- |
| Python | `python -m py_compile <changed_python_files>` plus the closest deterministic tests. |
| Backend integration | `./scripts/ci_gate.sh` when required by scope or owner policy. |
| Web | Managed Vitest/lint, typecheck, and production artifact build. |
| Desktop | Build Web first, then the Electron app when feasible. |
| Documentation/AI assets | Documentation checker, generator freshness, generator tests, AI asset check, and diff/secret checks. |
| Protected semantics | Exact owner tests plus adjacent producer/consumer integration evidence. |
| Browser/UAT/release | Real managed execution only when triggered and authorized; static or skipped evidence is not a pass. |

## Backend And Topology

The standard backend suite denies non-loopback sockets by default.
`scripts/ci_gate.sh` is the LAND gate and verifies the explicit domain topology.
Useful topology commands are:

```bash
python scripts/domain_test_topology.py validate-manifest
python scripts/domain_test_topology.py verify-all
python scripts/domain_test_topology.py list-backend --domain auth_security
python scripts/domain_test_topology.py list-network
python scripts/domain_test_topology.py run-backend --output-dir output/domain-test-topology --retry-failures 1
```

New backend test node IDs require reviewed ownership. A bootstrap collection can
diagnose unowned IDs, but bootstrap mode does not make them owned and does not
replace a manifest update.

Audited external-network tests are outside the normal offline/LAND tier. A run
requires marker metadata and both explicit gates:

```bash
python -m pytest -m network --allow-test-network --network-audit <audit-id>
```

## Web And Desktop

After `./wolfy bootstrap --ensure`, run Web checks through the managed
environment:

```bash
./wolfy exec --profile test -- npm --prefix apps/dsa-web run test
./wolfy exec --profile test -- npm --prefix apps/dsa-web run lint
./wolfy exec --profile test -- python scripts/web_build_artifact.py typecheck
./wolfy exec --profile test -- python scripts/web_build_artifact.py build
```

Visual, interaction, responsive, or accessibility claims require managed
browser evidence at the applicable viewports. DOM presence, source inspection,
or a skipped browser case is not equivalent.

## Runtime UAT

The local UAT harness binds evidence to the expected source identity:

```bash
./wolfy bootstrap --ensure
./wolfy exec --profile test -- python scripts/uat_runtime_harness.py --expected-sha "$(git rev-parse HEAD)"
```

It verifies a clean source tree, source SHA, immutable Web artifact, runtime
CWD, local HTTP identity, and no-live-provider isolation. It fails closed on an
unknown port owner, dependency/build failure, source mismatch, stale asset, or
non-WolfyStock HTML. Evidence under `output/runtime-verification/` is run-scoped
and is not durable documentation.

The managed UAT runtime sets `CRYPTO_REALTIME_ENABLED=false`,
`WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS=true`,
`WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED=false`, and
`WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED=false`. Those isolation settings
prove a no-live local run; they do not prove provider readiness.

Preflight and identity-bound stop commands:

```bash
python scripts/uat_runtime_harness.py --preflight --expected-sha "$(git rev-parse HEAD)" --evidence-path output/runtime-verification/<run-id>-evidence.json --json
python scripts/uat_runtime_harness.py --stop-from-evidence --evidence-path output/runtime-verification/<run-id>-evidence.json --json
```

Preparing deterministic non-production consumer accounts is explicit and
refuses production mode:

```bash
python scripts/uat_runtime_harness.py --expected-sha "$(git rev-parse HEAD)" --prepare-uat-accounts
```

The command creates only local/UAT non-admin users through the repository
seeding owner and does not print secrets.

## Documentation System

Run all documentation checks after changing Markdown, navigation, AI mirrors,
the documentation manifest, or generators:

```bash
python scripts/check_documentation.py
python scripts/build_ai_project_manual.py
python scripts/build_ai_project_manual.py --check
python -m pytest -q tests/scripts/test_build_ai_project_manual.py
python scripts/check_ai_assets.py
git diff --check
```

The checker enforces tracked-Markdown registration, root placement,
classification, canonical authority uniqueness, generated/editable status,
temporary-audit retirement metadata, relative links and anchors, stale current
path references, and durable-doc private-path rules.

## Evidence Semantics

Record the exact command, selection, environment, candidate/source identity,
and result. Preserve first attempts and retries when a protected gate requires
them. `skipped != passed`, `not evaluated != passed`, and `task accepted !=
analysis completed`. Do not turn unavailable runtime, platform, browser,
provider, broker, database, or release evidence into a success claim.
