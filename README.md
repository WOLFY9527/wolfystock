# WolfyStock

WolfyStock is an AI-assisted professional financial research terminal for
market operators, discretionary research, and portfolio workflows across US,
CN, and HK markets. It combines market context, scanner discovery, watchlists,
rule backtesting, portfolio tracking, provider diagnostics, admin observability,
and AI-assisted research in a Python/FastAPI + React/TypeScript codebase.

WolfyStock is not a broker, order-entry surface, retail trading game, or
unbounded LLM wrapper. The product posture is evidence-first, source-aware, and
no-advice.

## Canonical Docs

Read these first:

1. [`README.md`](README.md) - short human entrypoint.
2. [`AGENTS.md`](AGENTS.md) - AI-agent rules and protected-domain boundaries.
3. [`docs/AI_PROJECT_MANUAL.md`](docs/AI_PROJECT_MANUAL.md) - comprehensive
   generated project handbook.

[`docs/DOCS_INDEX.md`](docs/DOCS_INDEX.md) is intentionally tiny and only points
to canonical files. The historical Markdown corpus has been collapsed into the
AI project manual.

## Repository Map

- `main.py`: analysis and local automation entrypoint.
- `server.py`, `api/`: FastAPI service and `/api/v1` routes.
- `src/services/`, `src/repositories/`, `src/schemas/`: service, persistence,
  and DTO/schema boundaries.
- `data_provider/`: market-data provider adapters and fallback normalization.
- `apps/dsa-web/`: web terminal.
- `apps/dsa-desktop/`: Electron desktop wrapper.
- `bot/`: notification integrations.
- `scripts/`: local, validation, release, and evidence utilities.
- `.github/workflows/`: CI and release workflows.

## Local Development

Use the repository-owned environment command from every checkout and worktree:

```bash
./wolfy bootstrap --ensure
./wolfy lock python --check
./wolfy env verify
./wolfy exec --profile test -- python -m pytest -q tests/test_offline_network_policy.py
./wolfy qualify-env
```

`qualify-env` emits redacted environment evidence with non-null operation
identity. For baseline-delta qualification, first capture normalized findings
from an explicitly clean baseline checkout, then compare a changed checkout
using the same environment fingerprint:

```bash
./wolfy qualify-env --findings baseline-findings.json --output baseline-evidence.json
./wolfy qualify-env --baseline-commit <full-clean-baseline-sha> \
  --baseline-evidence baseline-evidence.json --findings current-findings.json
```

The comparison reports new, unchanged, and removed findings separately. It
never adds findings to a baseline automatically, and an unchanged release
blocker remains a failure.

`requirements.txt` and `requirements-dev.txt` preserve direct runtime and test
intent. `requirements-lock.json` plus the related CPython 3.11/3.12 lock files
are the reviewed install authority. Every target/profile projection exact-pins
its selected distributions and compatible artifact filenames with SHA-256
coverage. A selected source distribution also records its reviewed build
backend and exact locked build requirements. Check the contract without
installing dependencies:

```bash
./wolfy lock python --check
```

Only a deliberate dependency review may run `./wolfy lock python --update`.
That command requires resolver `uv 0.11.19`, reports direct and transitive
changes separately, and never runs from bootstrap, tests, development, CI, or
release qualification. The resolver does not install the runtime environment;
normal bootstrap remains pip-based and uses the selected lock with
`--no-deps --require-hashes`.

The reviewed target matrix is CPython 3.11 on Linux x86_64 for runtime and
development, Linux aarch64 for runtime, macOS arm64/x86_64 for runtime and
development, and Windows AMD64 for runtime and development. It also includes
CPython 3.12 on macOS arm64/x86_64 and Windows AMD64 for runtime and
development. Docker `linux/arm64` and Python-detected Linux `aarch64` normalize
to the same `manylinux_2_36_aarch64` runtime projection; Linux aarch64 does not
have a development projection. Other target/profile combinations fail before
snapshot installation. Static marker, wheel-tag, ABI, and source-build
validation is not a claim of real-platform execution.

Release containers use BuildKit `TARGETARCH` to select only the reviewed
CPython 3.11 Linux runtime projection: `amd64` selects Linux x86_64 and `arm64`
selects Linux aarch64. Their dependency builder reuses the same Wolfy locked
installer with `--no-deps --require-hashes --no-build-isolation`; it never
installs from the requirements intent, invokes uv, or selects a development
projection. Unsupported or missing Docker architectures fail before pip runs.

`bootstrap --ensure` is the only command that may install dependencies. Use
`./wolfy bootstrap --ensure --offline` to require verified snapshots and local
package-manager caches; an offline locked-artifact miss fails without attempting
the network. Online and offline Python bootstrap select the same normalized
target/profile graph and artifact projection and never resolve floating
requirements or rewrite lock files. Python and Web snapshots
live under the OS cache root, or the absolute
`WOLFYSTOCK_ENV_CACHE` override, as separate input and installed-content
fingerprints. `.venv` and `apps/dsa-web/node_modules` link to those verified
snapshots rather than another checkout.

The `test` profile removes credentials, production DSNs, admin bootstrap flags,
Python/Node startup modifiers, proxy settings, and user data paths. It allocates
one run-scoped SQLite database, cache, logs, uploads, temporary files, coverage,
pytest cache, frontend output, and service metadata directory. Successful runs
are removed; a bounded number of failed run directories are retained for local
diagnosis.

Start isolated local services without fixed ports or live financial providers:

```bash
./wolfy dev --json
./wolfy dev --stop <run-id> --json
```

The start command reports the environment fingerprint, run ID, URLs, process
IDs, log paths, and readiness. The stop command verifies the run identity and is
idempotent.

Product entrypoint variants, when invoked by an explicitly configured runtime:

```bash
python main.py --debug
python main.py --dry-run
python main.py --stocks 600519,hk00700,AAPL
python main.py --market-review
python main.py --schedule
python main.py --serve
python main.py --serve-only
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### Runtime startup truth

`main.py --serve` and `main.py --serve-only` report the API as started only
after the application import, FastAPI lifespan startup, and socket bind have
completed. A failure or bounded startup timeout exits the main process with
code 1 before bot clients, analysis, scheduling, or a keepalive loop starts.
This process exit is the shared failure signal observed by the Desktop child
launcher, Docker restart/health supervision, and the UAT runtime harness.

Frontend preparation remains a separate degradation boundary. When
`prepare_webui_frontend_assets()` returns `False`, startup logs a warning and
continues with the API and its fallback root page. Likewise, an API that has
bound successfully but reports readiness 503 is operationally not ready; it is
not mislabeled as an import, lifespan, or bind failure. Normal returns and
interactive shutdown request uvicorn shutdown and wait for its managed thread.

Web commands use the verified `node_modules` snapshot:

```bash
./wolfy exec --profile test -- npm --prefix apps/dsa-web run lint
```

Desktop:

```bash
cd apps/dsa-desktop
npm install
npm run build
```

## Validation

> Shell note: commands using `./scripts/*.sh` and `$(git rev-parse HEAD)`
> are POSIX-shell (bash/sh) syntax. On Windows run them from Git Bash, WSL,
> or any shell that provides a POSIX `sh`, e.g. `bash scripts/ci_gate.sh`.
> PowerShell uses the same `$(...)` subexpression syntax for
> `git rev-parse HEAD`, so the UAT commands below also work in PowerShell.

- Backend (POSIX shell): `./scripts/ci_gate.sh`, or at minimum
  `python -m py_compile <changed_python_files>` plus focused tests.
- Web: after `./wolfy bootstrap --ensure`, run Vitest/lint through managed npm;
  run typecheck and the production artifact build through
  `./wolfy exec --profile test -- python scripts/web_build_artifact.py
  <typecheck|build>`. These commands never write the immutable dependency
  snapshot or install dependencies.
- Desktop: build Web first, then build the Electron app when feasible.
- AI/docs governance: `python scripts/build_ai_project_manual.py --check` and
  `python scripts/check_ai_assets.py`.

Backend pytest runs deny non-loopback socket access by default. The authoritative
`scripts/ci_gate.sh` remains the LAND gate and now also verifies the explicit
domain manifest. Shadow topology/parity commands are:

```bash
python scripts/domain_test_topology.py verify-all
python scripts/domain_test_topology.py run-backend --output-dir output/domain-test-topology --retry-failures 1
python scripts/domain_test_topology.py list-backend --domain auth_security
python scripts/domain_test_topology.py list-network
```

Audited external-network tests are separately enumerable and never run in the
standard offline/LAND tier. Running one requires all marker metadata plus both
explicit CLI gates: `python -m pytest -m network --allow-test-network
--network-audit <audit-id>`.

Local UAT runtime (POSIX shell / Git Bash):

```bash
./wolfy bootstrap --ensure
./wolfy exec --profile test -- python scripts/uat_runtime_harness.py --expected-sha "$(git rev-parse HEAD)"
```

Local UAT runtime (PowerShell):

```powershell
./wolfy bootstrap --ensure
./wolfy exec --profile test -- python scripts/uat_runtime_harness.py --expected-sha "$(git rev-parse HEAD)"
```

This canonical local harness validates a clean source tree and expected SHA,
uses the verified Web dependency snapshot when invoked through `./wolfy`, builds `apps/dsa-web`, launches
`main.py --serve-only` from the current worktree, checks localhost with an
explicit no-proxy HTTP client, and writes run-scoped JSON evidence plus a
per-run runtime log under `output/runtime-verification/`. It fails closed on
unknown port owners, dependency install/build failure, runtime CWD/SHA mismatch,
stale frontend asset identity, or non-WolfyStock HTML. The runtime it starts uses UAT-only isolation flags:
`CRYPTO_REALTIME_ENABLED=false`, `WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS=true`,
`WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED=false`, and
`WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED=false`.

### Qualified immutable release

`.github/workflows/release.yml` is the sole publication authority. It builds
one source/Web/multi-architecture OCI candidate, binds the exact source SHA,
nested environment evidence, reviewed Python lock, Web build identity, and
amd64/arm64 image digests, then records twelve explicit qualification gates.
Missing, skipped, cancelled, neutral, unknown, or failed gates remain NO-GO.
Promotion consumes the qualified manifest and copies the existing registry
digest; it does not rebuild or resolve dependencies.

The Electron desktop build is not in this qualified graph because its current
legacy scripts still install dependencies independently. Desktop publication
must remain disabled until those inputs are owned by `./wolfy`; the release
workflow does not preserve that obsolete second dependency authority.

To verify a current run for WorkBuddy or another browser validator, use the
read-only machine-readable preflight against the run evidence:

```bash
python scripts/uat_runtime_harness.py --preflight --expected-sha "$(git rev-parse HEAD)" --evidence-path output/runtime-verification/<run-id>-evidence.json --json
```

PowerShell equivalent for the preflight:

```powershell
python scripts/uat_runtime_harness.py --preflight --expected-sha "$(git rev-parse HEAD)" --evidence-path output/runtime-verification/<run-id>-evidence.json --json
```

The preflight checks evidence status, SHA, PID liveness, PID port ownership,
CWD, served asset identity, direct no-proxy HTTP, run start timestamp, and the
run log path. Lifecycle cleanup is also evidence-bound:

```bash
python scripts/uat_runtime_harness.py --stop-from-evidence --evidence-path output/runtime-verification/<run-id>-evidence.json --json
```

The stop command refuses wrong PID/CWD identity, reports already absent runtimes,
and never kills unrelated listeners or browser processes.

To seed deterministic non-production consumer test accounts, opt in explicitly:

```bash
python scripts/uat_runtime_harness.py --expected-sha "$(git rev-parse HEAD)" --prepare-uat-accounts
```

PowerShell equivalent for account seeding:

```powershell
python scripts/uat_runtime_harness.py --expected-sha "$(git rev-parse HEAD)" --prepare-uat-accounts
```

That option writes only local/UAT non-admin app users via
`scripts/seed_uat_consumer_test_accounts.py`; it refuses production mode and
does not print secrets.

Protected domains, no-advice policy, provider/data reality boundaries, and
landing workflow are covered in `AGENTS.md` and the generated project manual.
