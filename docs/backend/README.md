# WolfyStock Backend Docs

Status: current backend domain entry point.

Use this lane before changing `src/`, `api/`, `server.py`, backend schemas,
service/repository boundaries, storage coordination, auth/RBAC, report payloads,
or protected runtime semantics.

## Current Authority

- [Modular Architecture Manual](../architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md)
- [Backend / Frontend Modular Maintenance Handbook](../architecture/backend-frontend-modular-maintenance-handbook.md)
- [Backend Protected Domains](../codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md)
- [Database Component Map](../architecture/database-component-map.md)
- [Database Maintenance Handbook](../architecture/database-maintenance-handbook.md)
- [Database Troubleshooting Playbook](../architecture/database-troubleshooting-playbook.md)
- [PostgreSQL Baseline Design](../architecture/postgresql-baseline-design.md)

## Domain Boundaries

- API and route contracts live under `api/` and must stay additive unless a
  task explicitly scopes a breaking contract.
- Business orchestration belongs in `src/services/` and `src/core/`.
- Persistence ownership belongs in `src/repositories/` and storage architecture
  docs.
- Report payload structure belongs to `src/services/report_renderer.py` and
  `src/schemas/report_schema.py`.
- Do not reach around public facades to shortcut provider, scanner, portfolio,
  backtest, auth, or admin semantics.

## Validation

For backend changes, prefer `./scripts/ci_gate.sh`. At minimum, run
`python -m py_compile <changed_python_files>` when only a narrow Python change
is in scope.

Docs-only backend navigation changes do not require runtime tests, but still
need `git diff --check` and any task-requested docs/governance validation.
