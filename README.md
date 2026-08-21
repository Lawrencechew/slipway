# PavedPath — Public v1.0

PavedPath is a portfolio reference implementation that demonstrates a Git-native golden-path for delivering services. It converts a typed ServiceSpec into a policy-validated, deterministic Plan that can be reviewed, approved, audited and handed off to a Git workflow for CI/CD.

This repository is a polished reference (Public v1.0). It is not a production SaaS control plane; integrations such as Git hosting, cloud deployment, and managed secrets are presented as boundaries or simulations unless explicitly implemented.

**What PavedPath solves**
- Express developer intent as a `ServiceSpec` (typed JSON schema)
- Validate specs against platform policies (e.g., probes, resource limits)
- Produce a deterministic `Plan` (fingerprinted) containing artifacts and diffs
- Require explicit approval bound to the plan/revision fingerprint
- Persist audit events and approvals in PostgreSQL for traceability

Key concepts
- **ServiceSpec**: a typed declaration of a desired service state.
- **Validation**: policy checks run during plan generation.
- **Deterministic planning**: identical specs produce identical fingerprints and plans.
- **Diff**: plans include artifacts and a human-reviewable diff against current state.
- **Approval**: approvals are tied to a plan fingerprint; changing the spec invalidates prior approvals.
- **Git handoff**: PavedPath emits Git-ready artifacts; actual push/integration is simulated in this repo.

Technology stack
- Python 3.13, FastAPI, SQLAlchemy
- PostgreSQL (recommended for persistence; local tests use the committed defaults)
- Alembic for migrations
- React + Vite + TypeScript frontend (demo)

Quickstart — run locally

1. Copy `.env.example` to `.env` and edit if needed. By default the app will use SQLite for local runs if `DATABASE_URL` is not set.

```bash
cp .env.example .env
# Edit .env only for Postgres usage. Do NOT commit .env.
```

2. Install dependencies and create the lock environment (Poetry):

```bash
python -m pip install --upgrade pip
pip install poetry
poetry install
```

3. Apply database migrations:

```bash
alembic upgrade head
```

4. Run the backend (development):

```bash
uvicorn app.main:app --reload
```

5. Run the frontend demo (optional):

```bash
cd frontend
npm ci
npm run dev
```

Run tests

```bash
pytest -q
```

Acceptance demo

There is a manual acceptance demo script that exercises plan creation and approval logic locally against the default persistence. Run it with Poetry so it uses the pinned dependencies:

```bash
poetry run python scripts/acceptance_demo.py
```

Current limitations
- Git handoff and cloud deployment are simulated; real integrations are outside the scope of this reference implementation.
- Secrets and production-grade auth are not implemented — use this as a reference only.

Documentation
- Architecture: `docs/architecture.md`
- Design decisions: `docs/design-decisions.md`

If you plan to publish this repository, review `SECURITY.md` and `CONTRIBUTING.md` before making it public.

Thank you for trying PavedPath — enjoy the reference implementation!
