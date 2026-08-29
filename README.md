# Vialbum API

FastAPI foundation for Vialbum's travel-memory backend.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload
```

Configure `DATABASE_URL` and a strong, private `JWT_SECRET` in `.env`. Never commit `.env`.

The API is available at `http://127.0.0.1:8000`; interactive documentation is at `/docs`.

The app does not connect to PostgreSQL during startup or for the system endpoints. Set `DATABASE_URL` before using database-backed features or running migrations.

## API

- `POST /auth/register` creates an account with an Argon2-hashed password.
- `POST /auth/login` returns a JWT bearer access token.
- `GET /auth/me` returns the authenticated user.
- `POST /journeys` creates a journey for the authenticated user.
- `GET /journeys` lists the authenticated user's journeys.
- `GET`, `PATCH`, and `DELETE /journeys/{journey_id}` are ownership-scoped.

Send authenticated requests with `Authorization: Bearer <access_token>`.

## Checks

```bash
pytest
ruff check .
ruff format --check .
alembic check
```

## Architecture

- `app/api`: HTTP routing and dependencies
- `app/core`: settings, security, and shared exceptions
- `app/db`: SQLAlchemy base and session lifecycle
- `app/models`: persistence models
- `app/schemas`: Pydantic request/response models
- `app/repositories`: database access
- `app/services`: business logic
- `alembic`: database migrations
