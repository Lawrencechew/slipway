# Contributing

Thanks for taking an interest in PavedPath. This project is a portfolio/demo repository intended to show platform engineering patterns.

Local setup
1. Copy `.env.example` to `.env` and fill `DATABASE_URL`.
2. Install dependencies (Poetry):

```bash
pip install poetry
poetry install
```

3. Run migrations:

```bash
alembic upgrade head
```

4. Run tests before submitting PR:

```bash
pytest -q
```

Pull request expectations
- One feature/fix per branch.
- Include tests for behavior changes.
- Keep changes focused and well-documented.

Security
- Do not commit secrets or credentials. Use `.env` (ignored) and keep `.env.example` as the template.
