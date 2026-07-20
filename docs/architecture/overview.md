# System Architecture

> Status: Canonical
> Scope: repository structure, runtime entrypoints, component ownership, and cross-module boundaries
> Audience: maintainers and agents changing backend, API, Web, Desktop, or shared contracts

Repository rules and protected-domain authorization remain in
[`AGENTS.md`](../../AGENTS.md). Data truth semantics are owned by
[`docs/contracts/data-trust.md`](../contracts/data-trust.md).

## Product Context

WolfyStock is a professional financial research terminal for market operators,
discretionary research, and portfolio workflows across US, CN, and HK markets.
It combines market context, scanner discovery, watchlists, rule backtesting,
portfolio tracking, provider diagnostics, admin observability, and AI-assisted
research in a Python/FastAPI plus React/TypeScript codebase.

The product is not a broker, order-entry surface, retail trading game, or
unconstrained LLM wrapper. Its durable posture is evidence-first,
source-aware, and no-advice.

## Repository Map

| Path | Responsibility |
| --- | --- |
| `main.py` | Analysis, automation, scheduling, and combined runtime entrypoint. |
| `server.py`, `api/app.py` | FastAPI application construction and lifecycle. |
| `api/v1/router.py`, `api/v1/endpoints/` | Versioned API routing and thin HTTP adapters. |
| `src/services/` | Domain orchestration and business semantics. |
| `src/repositories/` | Persistence boundaries and stored-state ownership. |
| `src/schemas/`, `api/v1/schemas/` | Internal and public DTO/schema contracts. |
| `src/contracts/` | Shared explicit domain contracts. |
| `data_provider/` | Provider adapters and normalized provider boundaries. |
| `bot/` | Notification integrations. |
| `apps/dsa-web/` | React/Vite research terminal. |
| `apps/dsa-desktop/` | Electron desktop wrapper. |
| `scripts/` | Environment, validation, release, migration, and evidence utilities. |
| `validation/` | Reviewed test and validation ownership manifests. |
| `.github/workflows/` | CI and release automation. |

## Ownership Boundaries

- API endpoints translate HTTP requests and responses; they do not own scanner
  ranking, provider fallback, portfolio accounting, auth policy, or report
  rendering.
- Services own domain behavior and orchestration.
- Repositories own persistence and transaction boundaries.
- Schemas and DTOs make contracts explicit across owners.
- Provider adapters remain behind provider-runtime boundaries; consumers do not
  reach into raw provider payloads or clients.
- Web pages consume API clients and presentation/read models. They do not
  reinterpret protected backend truth independently.
- Desktop supervises the existing Web/backend runtime. It is not a second
  product or dependency authority.

Consumers should call public facades, API clients, schemas, DTOs, validators,
and documented commands. Reaching into another domain's private engine,
repository, cache key, ledger mutation, or provider client creates a parallel
authority and requires an explicit architecture decision.

## Runtime Startup Truth

`main.py --serve` and `main.py --serve-only` report API startup only after
application import, FastAPI lifespan startup, and socket bind have completed.
A failure or bounded startup timeout exits the main process with code 1 before
bot clients, analysis, scheduling, or a keepalive loop starts. Desktop, Docker,
and the UAT harness observe that same process-level signal.

Frontend asset preparation is a separate degradation boundary.
`prepare_webui_frontend_assets()` returning `False` logs a warning and leaves
the API plus fallback root page available. A bound API returning readiness 503
is operationally not ready; it is not mislabeled as an import, lifespan, or
bind failure. Normal return and interactive shutdown request uvicorn shutdown
and join its managed thread.

## Public Contract Changes

Shared contracts, schemas, root configuration, CI, dependencies, auth,
provider runtime, broker/accounting behavior, DB migrations, and frontend
route-entry behavior are high-risk boundaries. They require explicit scope,
producer/consumer review, and focused validation. Prefer additive public fields
over silent renames or deletions.

Source code and tests are the executable truth. This document explains owner
boundaries; it does not override observed runtime behavior.
