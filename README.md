# WolfyStock

WolfyStock is an AI-assisted professional financial research terminal for
market operators, discretionary research, and portfolio workflows across US,
CN, and HK markets. It combines market context, scanner discovery, watchlists,
rule backtesting, portfolio tracking, provider diagnostics, admin observability,
and AI-assisted research in a Python/FastAPI plus React/TypeScript codebase.

WolfyStock is not a broker, order-entry surface, retail trading game, or
unbounded LLM wrapper. The product posture is evidence-first, source-aware, and
no-advice.

## Start Here

- Humans: use this file for orientation, then open the
  [documentation index](docs/README.md).
- AI coding tools: read [`AGENTS.md`](AGENTS.md) and then the
  [task router](docs/README.md). `CLAUDE.md` is the Claude compatibility
  symlink to the same rules.
- Source code and tests are the final executable truth. A document being
  present does not make it authoritative.

The generated [AI project manual](docs/generated/AI_PROJECT_MANUAL.md) is a
machine-built catalog of task routes, authorities, classifications, and source
hashes. It is useful for navigation but is not a second policy or domain-rule
source.

## Repository Map

- `main.py`: analysis, automation, scheduling, and combined runtime entrypoint.
- `server.py`, `api/`: FastAPI application and `/api/v1` routes.
- `src/services/`, `src/repositories/`, `src/schemas/`, `src/contracts/`:
  domain behavior, persistence, DTOs, and shared contracts.
- `data_provider/`: normalized market-data provider adapters.
- `apps/dsa-web/`: React/Vite research terminal.
- `apps/dsa-desktop/`: Electron desktop wrapper.
- `bot/`: notification integrations.
- `scripts/`: environment, validation, release, and evidence utilities.
- `validation/`: reviewed validation ownership manifests.
- `.github/workflows/`: CI and release workflows.

See [System Architecture](docs/architecture/overview.md) for ownership and
runtime boundaries.

## Quick Start

Use the repository-owned environment authority from every checkout and
worktree:

```bash
./wolfy bootstrap --ensure
./wolfy lock python --check
./wolfy env verify
./wolfy exec --profile test -- python -m pytest -q tests/test_offline_network_policy.py
```

Start isolated local services without fixed ports or live financial providers:

```bash
./wolfy dev --json
./wolfy dev --stop <run-id> --json
```

Product entrypoints, under an explicitly configured runtime:

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

Environment locks, supported targets, offline snapshots, test isolation, Web,
Desktop, and optional LiteLLM configuration are documented in
[Development Environment](docs/development/environment.md).

## Validation

Select validation by changed owner and risk. Common commands:

```bash
./scripts/ci_gate.sh
./wolfy exec --profile test -- npm --prefix apps/dsa-web run lint
./wolfy exec --profile test -- python scripts/web_build_artifact.py build
python scripts/check_documentation.py
python scripts/build_ai_project_manual.py --check
python scripts/check_ai_assets.py
```

The complete command routing and evidence semantics are in
[Validation And Evidence](docs/development/validation.md). Browser, provider,
broker, database, target-environment, and release claims require the real
applicable execution; skipped or unavailable checks are not passes.

## Documentation Changes

[`docs/documentation-manifest.json`](docs/documentation-manifest.json) is the
machine-readable document registry. Edit canonical source documents and the
manifest, then regenerate navigation outputs:

```bash
python scripts/build_ai_project_manual.py
python scripts/check_documentation.py
python scripts/check_ai_assets.py
```
