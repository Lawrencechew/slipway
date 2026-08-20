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

3. Start PostgreSQL locally (docker-compose):

```bash
docker-compose up -d
```

4. Run migrations:

```bash
export DATABASE_URL=postgresql://pavedpath:pavedpath@localhost:5432/pavedpath
alembic upgrade head
```

5. Run backend:

```bash
python -m app.main
```

6. Frontend:

```bash
cd frontend
npm install
npm run dev
```
