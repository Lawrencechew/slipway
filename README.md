# PavedPath

PavedPath is a Git-native golden-path platform that converts developer service intent into validated, reviewable and auditable deployment changes for Azure/AKS.

One-sentence summary: turn a typed ServiceSpec into a policy-validated, deterministic Plan that can be reviewed, approved, audited and handed off to Git for CI/CD.

## Why this project
- Platform teams want consistent, auditable deployment changes.
- Developers should express intent using a ServiceSpec and avoid low-level infra details.
- PavedPath demonstrates deterministic planning, policy validation, approval binding to revisions, and auditable state persisted in PostgreSQL.

## Technology stack
- Python 3.13, FastAPI
- PostgreSQL (tested with Postgres 15)
- SQLAlchemy + Alembic
- React + Vite + TypeScript frontend
- Pytest for tests

## Repository structure
- `app/` — backend FastAPI app, models, planner, policies, auth
- `migrations/` — Alembic migrations
- `tests/` — unit and integration tests
- `frontend/` — React SPA demo
- `.github/workflows/ci.yml` — CI for backend and frontend (runs tests and build)

## Local development

1. Create a copy of `.env.example` to `.env` and fill values:

```bash
cp .env.example .env
# Edit .env and set DATABASE_URL
```

2. Install dependencies (Poetry):

```bash
python -m pip install --upgrade pip
pip install poetry
poetry install
```

3. Run migrations (requires DATABASE_URL configured for Postgres or use sqlite URL):

```bash
alembic upgrade head
```

4. Run backend:

```bash
uvicorn app.main:app --reload
```

5. Run frontend (in another terminal):

```bash
cd frontend
npm ci
npm run dev
```

6. Run tests:

```bash
pytest -q
```

## Example API workflow

1. Create a user (returns an API key):

```bash
curl -X POST http://localhost:8000/users -H 'Content-Type: application/json' -d '{"username":"alice"}'
```

2. Submit a ServiceSpec to `/specs` (use the returned API key as `Authorization: Bearer <key>`)
3. Create a Plan via `/plans` and inspect the returned plan JSON (artifacts and diffs)
4. Approve the Plan via `/plans/{plan_id}/approve` (only READY plans)

## Safety properties
- Deterministic plan generation (fingerprinting ensures reproducibility)
- Approvals are bound to a specific plan/revision
- Stale approvals are invalidated when the ServiceSpec changes
- All state transitions are auditable via persisted events

## Limitations
- Git handoff and CI/CD are represented by a mock Git adapter for the demo
- Authentication is a simple API-key mechanism for v1 (replaceable)
- Not a production-grade control plane — intended as a portfolio/demo project

## Contributing
See `CONTRIBUTING.md` for local setup and PR expectations.

## License
No license is included. Choose a license before publishing if desired.
# PavedPath (v1)

PavedPath is a Git-native golden-path platform for Azure/AKS. It accepts a strongly-typed ServiceSpec, validates it against deterministic platform policies, generates an immutable Plan containing the proposed artifacts and diffs, and requires explicit approval before producing Git changes.

This repository is PRIVATE.

See `docs/` for architecture and local setup.
