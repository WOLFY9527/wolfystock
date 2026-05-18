# WolfyStock

WolfyStock is an AI-assisted quantitative stock analysis terminal for market
operators, discretionary traders, and research-driven portfolio workflows. It
combines market overview, stock screening, rule backtesting, portfolio
management, provider diagnostics, and admin observability in a modular
Python/FastAPI + React/TypeScript codebase.

It is not positioned as a generic retail stock app or a thin LLM wrapper. The
current project direction is a professional research terminal with explicit
domain boundaries, focused validation, and AI-agent-assisted engineering.

## Overview

WolfyStock covers the full research loop:

- market overview for operator context and macro status;
- scanner workflows for actionable watchlist discovery;
- rule backtesting for historical validation;
- portfolio tracking with risk and attribution surfaces;
- AI-assisted analysis and reporting;
- provider-runtime diagnostics and admin observability.

The repository still contains backend automation, notification, and deployment
paths inherited from the original project, but the current product shape is a
terminal-style research workstation rather than a simple scheduled stock-push
tool.

Useful entry points:

- `docs/DOCS_INDEX.md`: documentation navigation start page.
- `docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`: system/module/route/API handbook.
- `docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md`: AI maintenance workflow manual.
- `main.py`: analysis and local run entry.
- `server.py`: FastAPI service entry.
- `apps/dsa-web/`: WolfyStock web terminal.
- `apps/dsa-desktop/`: Electron desktop wrapper.
- `docs/architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md`: module boundary manual.
- `docs/architecture/backend-frontend-modular-maintenance-handbook.md`:
  maintenance map.
- `docs/CHANGELOG.md`: user-visible and operational change log.

## Key Features

- **Market overview**: macro, breadth, and status surfaces for daily operator
  context.
- **Scanner / stock screening**: bounded pre-open discovery for A-share, US,
  and HK workflows with shortlist persistence and handoff.
- **Rule backtesting**: deterministic backtest execution, result readback,
  compare flows, and support exports.
- **Portfolio management**: holdings, cash, transactions, imports, broker sync,
  and read models.
- **Portfolio risk attribution**: account, FX, cost-basis, and portfolio-risk
  views without weakening ledger authority.
- **Provider runtime / market data diagnostics**: fallback, freshness, provider
  health, and sanitized operator diagnostics.
- **Admin observability**: execution logs, activity views, cost surfaces,
  provider operations, and protected admin diagnostics.
- **AI-assisted analysis**: LLM-assisted research, summarization, and
  decision-support flows with bounded provider/runtime seams.
- **Terminal-style frontend UI**: a dense, calm, operator-oriented interface
  guided by WolfyStock terminal primitives and design constitution rules.

Related docs:

- [Docs Index](docs/DOCS_INDEX.md)
- [WolfyStock System Handbook](docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md)
- [WolfyStock AI Maintenance Manual](docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md)
- [Market Scanner](docs/market-scanner.md)
- [Full Guide](docs/full-guide.md)
- [FAQ](docs/FAQ.md)
- [English Docs](docs/README_EN.md)
- [Traditional Chinese Docs](docs/README_CHT.md)

## Architecture

WolfyStock is being maintained as a bounded-context system, not as a single
monolith with incidental cross-imports.

Current engineering priorities:

- modular architecture with narrow public interfaces between domains;
- subtractive refactor instead of speculative rewrites;
- explicit provider-runtime boundaries around fallback, freshness, and cache
  semantics;
- protected scanner, backtest, portfolio, auth/RBAC, and admin observability
  boundaries;
- golden contract tests, import-boundary guards, and focused route/domain
  validation instead of broad unsafe churn.

Primary reference docs:

- [WolfyStock Documentation Index](docs/DOCS_INDEX.md)
- [WolfyStock System Handbook](docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md)
- [WolfyStock AI Maintenance Manual](docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md)
- [WolfyStock Modular Architecture Manual](docs/architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md)
- [Backend / Frontend Modular Maintenance Handbook](docs/architecture/backend-frontend-modular-maintenance-handbook.md)
- [Frontend Docs](docs/frontend/README.md)
- [Frontend Validation Playbook](docs/frontend/validation-playbook.md)

## AI-Agent Assisted Development

This repository actively supports AI-agent-assisted engineering with strict
scope control.

Typical workflow roles:

- **Backend worker**: isolates one backend seam or contract change at a time.
- **Frontend worker**: handles one page/surface change at a time under the
  design constitution.
- **Read-only audit**: produces architecture, QA, or cleanup evidence without
  runtime modification.
- **Integrator**: lands verified slices after focused validation and rollback
  review.

Workflow discipline:

- use Git worktrees for parallel development;
- keep worker tasks narrow and domain-local;
- validate before staging or claiming completion;
- preserve rollback paths and exact changed-file scope;
- avoid touching protected runtime semantics unless the task explicitly scopes
  them.

## Recent Refactor Highlights

- **Admin actor boundary**: extracted `AdminActorContext` to separate admin
  security/governance actions from broader service internals.
- **Market overview workbench split**: extracted and split
  `MarketOverviewWorkbench` into narrower workbench surfaces.
- **Scanner symbol classification boundary**: reduced provider normalization
  coupling around scanner-side symbol handling.
- **Portfolio symbol normalization decoupling**: isolated shared symbol
  normalization helpers from provider runtime semantics.
- **Broker import / sync symbol boundary**: reduced broker import coupling to
  provider-specific symbol logic.
- **Backtest local history seam**: isolated local-history responsibilities in
  the backtest stack.
- **Admin cost DTO decoupling**: separated admin cost view DTO construction from
  service internals.
- **Provider/runtime boundary tests**: expanded focused tests around provider
  runtime, MarketCache, DTO contracts, and import boundaries.

Recent commits around this direction include:

- `d62aa7cf` `refactor(auth): extract admin actor context boundary`
- `de4c32c1` `refactor(web): extract market overview workbench view`
- `c5470842` `refactor(web): split market overview workbench sections`
- `61587eba` `refactor(portfolio): reduce broker symbol provider coupling`
- `1ed4bd0b` `refactor(portfolio): reduce provider symbol normalization coupling`
- `31df811a` `refactor(scanner): reduce provider normalization coupling`
- `f02faddd` `refactor(backtest): isolate universe local history seam`
- `4bdc188b` `refactor(admin): decouple cost dto construction from service`
- `b74c41b9` `test(provider): add runtime marketcache boundary contracts`

## Tech Stack

- **Backend**: Python, FastAPI, service/repository/report layers under `src/`
- **Frontend**: React 19, TypeScript, Vite, Tailwind-based terminal UI in
  `apps/dsa-web/`
- **Desktop**: Electron wrapper in `apps/dsa-desktop/`
- **Testing**: pytest, Vitest, Playwright, focused contract/import-boundary
  tests
- **Runtime integrations**: LiteLLM-compatible AI routing plus multiple market
  data and search providers

## Local Development

Keep local setup grounded in repo-supported commands.

### Backend

```bash
pip install -r requirements.txt
pip install flake8 pytest
cp .env.example .env
python main.py
```

Useful variants:

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

### Web

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

### Desktop

```bash
cd apps/dsa-desktop
npm install
npm run build
```

For broader onboarding, deployment, and notification setup, see
[Full Guide](docs/full-guide.md).

## Validation & Testing

WolfyStock favors focused validation over vague "it should work" claims.

- **Backend gate**: `./scripts/ci_gate.sh`
- **Python syntax safety**: `python -m py_compile <changed_python_files>`
- **Frontend checks**: `cd apps/dsa-web && npm run lint && npm run build`
- **Frontend design guard**: `cd apps/dsa-web && npm run check:design`
- **Frontend constitution check**:
  `python3 scripts/check_frontend_design_constitution.py`
- **Focused tests**: route/domain-specific pytest or Vitest/Playwright runs
  instead of unrelated broad churn
- **Secret scan**: `bash scripts/release_secret_scan.sh`

For frontend execution tasks, follow the
[WolfyStock Frontend Validation Playbook](docs/frontend/validation-playbook.md).

## Roadmap

- continue subtractive refactors that reduce cross-domain coupling;
- expand golden contracts and import-boundary guards;
- keep provider-runtime semantics explicit and test-protected;
- strengthen scanner, backtest, portfolio, auth, and admin domain seams;
- improve operator-facing terminal workflows without diluting product identity.

## Acknowledgements

WolfyStock originally started from the open-source
[`daily_stock_analysis`](https://github.com/ZhuLinsen/daily_stock_analysis)
project by ZhuLinsen. This repository retains the upstream license and
attribution while substantially modifying, redesigning, and extending the
system into the current WolfyStock research terminal.

This repository also retains historical documentation for the inherited
automation/deployment paths where they still reflect runnable project behavior.

## License

This project is released under the [MIT License](LICENSE).

Copyright notices and license terms from the upstream project are preserved.
