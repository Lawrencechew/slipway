# Local development setup

1. Install Python 3.11+ and Node.js 18/20
2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install poetry
poetry config virtualenvs.create false
poetry install
```

3. Start PostgreSQL locally:

```bash
docker compose up -d
```

4. Run migrations:

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/slipway
alembic upgrade head
```

If migration startup fails with a `libpq`/`psycopg` wrapper import error on your OS, install:

```bash
python -m pip install psycopg-binary
```

5. Run backend:

```bash
python -m app.main
```

6. Frontend:

```bash
cd frontend
npm ci
npm run dev
```
