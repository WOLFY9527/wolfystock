# Development Environment

> Status: Canonical
> Scope: dependency authority, bootstrap, supported targets, local services, and configuration entrypoints
> Audience: contributors and agents preparing or changing the development/runtime environment

Repository permission and protected-domain rules are in
[`AGENTS.md`](../../AGENTS.md). Validation selection is in
[`docs/development/validation.md`](validation.md).

## Environment Authority

`./wolfy` is the only repository-owned dependency environment authority.
From any checkout or worktree:

```bash
./wolfy bootstrap --ensure
./wolfy lock python --check
./wolfy env verify
./wolfy qualify-env
```

`requirements.txt` preserves direct production-environment intent in explicit
owner sections for application runtime integrations and projection-only
lock/build tools. `requirements-dev.txt` inherits that intent and separately
owns development and test tools. Each direct declaration has one owner and an
inline reason; a package being installed transitively is not a reason to repeat
it as direct intent. For example, the application owns the direct LiteLLM
client, while its resolved `openai` dependency remains in the install closure
without becoming an application direct dependency. These files are not install
locks. `requirements-lock.json` and its CPython 3.11/3.12 lock family are the
reviewed install authority. Each target/profile projection exact-pins
distributions and compatible artifact filenames with SHA-256 coverage. Reviewed
source distributions also bind their build backend and exact build requirements.

Only an explicit dependency review may run:

```bash
./wolfy lock python --update
```

That command uses `uv 0.11.19` only as the resolver and reports direct and
transitive changes separately. Bootstrap, tests, development, CI, and release
qualification never update the lock implicitly. Runtime installation remains
pip-based with `--no-deps --require-hashes`.

PyArrow is the single reviewed Parquet read/write authority in supported
projections. Do not add a second engine or silent fallback.

## Supported Matrix

Reviewed runtime/development targets are:

- CPython 3.11 Linux x86_64: runtime and development;
- CPython 3.11 Linux aarch64: runtime only;
- CPython 3.11 macOS arm64/x86_64: runtime and development;
- CPython 3.11 Windows AMD64: runtime and development;
- CPython 3.12 macOS arm64/x86_64: runtime and development;
- CPython 3.12 Windows AMD64: runtime and development.

Docker `linux/arm64` and Python-detected Linux `aarch64` select the same
`manylinux_2_36_aarch64` runtime projection. Unsupported target/profile pairs
fail before installation. Static marker, wheel-tag, ABI, and source-build
checks are not real-platform execution evidence.

Release containers map BuildKit `amd64` and `arm64` to the reviewed CPython
3.11 Linux runtime projections. Their dependency builder uses the same lock
authority with `--no-deps --require-hashes --no-build-isolation`; requirements
intent, development locks, and uv do not enter the image install path.

## Snapshots And Offline Bootstrap

Online and offline bootstrap select the same normalized graph and artifact
projection. Offline mode requires verified snapshots and package caches:

```bash
./wolfy bootstrap --ensure --offline
```

A missing artifact fails without network fallback. Python, Web, browser, and
managed-tool snapshots are content-addressed under the OS cache root or the
explicit `WOLFYSTOCK_ENV_CACHE` override. Worktrees link to those immutable
snapshots, never another checkout's mutable `.venv` or `node_modules`.

The environment authority also provisions reviewed `rg` and the declared
Playwright Chromium revision, verifies the executable can launch, and supplies
it to Playwright. Host `PATH`, a global browser, or a system-browser fallback is
not an equivalent authority.

## Test Profile

The `test` profile removes credentials, production DSNs, admin bootstrap flags,
startup modifiers, proxy settings, and user-data paths. It allocates one
run-scoped SQLite database, cache, logs, uploads, temp files, coverage, pytest
cache, frontend output, and service metadata directory. Successful runs are
removed; a bounded number of failed runs may remain for diagnosis.

Run a command inside that profile with:

```bash
./wolfy exec --profile test -- python -m pytest -q tests/test_offline_network_policy.py
./wolfy exec --profile test -- npm --prefix apps/dsa-web run lint
```

## Environment Qualification

`./wolfy qualify-env` emits redacted environment evidence with a non-null
operation identity. A baseline comparison requires an explicitly clean
baseline checkout and the same environment fingerprint:

```bash
./wolfy qualify-env --findings baseline-findings.json --output baseline-evidence.json
./wolfy qualify-env --baseline-commit <full-clean-baseline-sha> \
  --baseline-evidence baseline-evidence.json --findings current-findings.json
```

The comparison keeps new, unchanged, and removed findings distinct. It does
not add findings to the baseline automatically, and an unchanged release
blocker remains a failure.

## Local Runtime

Start the complete local product from any directory by invoking the checkout's
`wolfy` launcher path:

```bash
/path/to/wolfystock/wolfy dev
/path/to/wolfystock/wolfy dev --stop
```

The command verifies or ensures the managed environment, resolves the checkout
from the launcher location, and starts the frontend at
`http://127.0.0.1:5173` and backend at `http://127.0.0.1:8000`. It loads the
checkout `.env` through the runtime settings authority, inherits configured
host proxy variables, keeps mutable database, cache, build, temporary, log,
upload, and service state outside immutable dependency snapshots, and does not
enable live financial providers.

Both ports are checked before either service starts. An unrelated listener is
reported and never stopped. A repeated start reports the healthy recorded
runtime, while stale metadata is removed only after recorded process identity
checks. Stop needs no run ID, verifies every recorded process before signaling,
and is idempotent.

Automation and concurrent qualification can retain isolated dynamic ports and
explicit run identity through the JSON interface:

```bash
./wolfy dev --json
./wolfy dev --stop <run-id> --json
```

The JSON start result includes environment fingerprint, run ID, URLs, process
IDs, log paths, and readiness.

Product entrypoint variants, under an explicitly configured runtime:

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

Desktop currently retains its own local build path:

```bash
cd apps/dsa-desktop
npm install
npm run build
```

This does not make Desktop a second release dependency authority.

## LiteLLM Router Configuration

`litellm_config.example.yaml` is an optional template. Reference secrets through
environment variables, keep the real config untracked, and set
`LITELLM_CONFIG` to the local configuration path. The template does not grant
provider activation or bypass the runtime provider/configuration owners.

Do not place real API keys, credentials, private service URLs, or environment
specific absolute paths in documentation or committed configuration.
