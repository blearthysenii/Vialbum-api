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

Configure `DATABASE_URL`, a strong private `JWT_SECRET`, and the private S3-compatible storage
variables in `.env`. Never commit `.env`.

The API is available at `http://127.0.0.1:8000`; interactive documentation is at `/docs`.

The app does not connect to PostgreSQL during startup or for the system endpoints. Set `DATABASE_URL` before using database-backed features or running migrations.

## API

- `POST /auth/register` creates an account with an Argon2-hashed password.
- `POST /auth/login` returns a JWT bearer access token.
- `GET /auth/me` returns the authenticated user.
- `POST /journeys` creates a journey for the authenticated user.
- `GET /journeys` lists the authenticated user's journeys.
- `GET`, `PATCH`, and `DELETE /journeys/{journey_id}` are ownership-scoped.
- `POST /journeys/{journey_id}/media` validates and uploads a private journey photo.
- `GET /journeys/{journey_id}/media` returns metadata with short-lived read URLs.
- `DELETE /journeys/{journey_id}/media/{media_id}` deletes owned media.
- `PATCH /journeys/{journey_id}/cover/{media_id}` selects an owned photo as the cover.

Send authenticated requests with `Authorization: Bearer <access_token>`.

## Private media storage

Photo bytes are stored in a private Supabase Storage bucket through its S3-compatible API. Neon
stores only stable object keys and photo metadata. Access URLs are signed on demand and expire.
Required configuration is documented in `.env.example`; scope the S3 key to the media bucket and
never expose it to the mobile client.

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
- `app/storage`: provider-neutral object storage and the S3-compatible adapter
- `alembic`: database migrations
