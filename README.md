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

Backend:

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

Web:

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

Desktop:

```bash
cd apps/dsa-desktop
npm install
npm run build
```

## Validation

- Backend: `./scripts/ci_gate.sh`, or at minimum
  `python -m py_compile <changed_python_files>` plus focused tests.
- Web: `cd apps/dsa-web && npm ci && npm run lint && npm run build`.
- Desktop: build Web first, then build the Electron app when feasible.
- AI/docs governance: `python scripts/build_ai_project_manual.py --check` and
  `python scripts/check_ai_assets.py`.

Protected domains, no-advice policy, provider/data reality boundaries, and
landing workflow are covered in `AGENTS.md` and the generated project manual.
