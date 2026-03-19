# Marine Intelligence Platform

Marine Intelligence Platform (codenamed DockGuard) is an AI-powered damage detection and tracking system for marine rental equipment. It enables rental operators to photograph assets before and after each rental session, then uses Claude's vision API to automatically identify new damage, estimate repair costs from operator-managed lookup tables, and build an auditable history of every scratch, dent, and crack across an entire fleet. The platform is multi-tenant from day one, designed for offline-first mobile use, and improves its accuracy over time through a structured operator feedback loop.

## Architecture overview

The system is a standard two-tier web application with a clear separation between a Python/FastAPI backend and a React/TypeScript frontend.

The backend exposes a versioned REST API (`/api/v1`) that handles authentication, CRUD for fleet assets and rental sessions, photo upload to Cloudflare R2 object storage, AI-powered damage detection via the Anthropic Claude vision API, operator feedback collection, and accuracy metrics tracking. All database access is async via SQLAlchemy 2.0 with asyncpg. Background work (damage detection) runs via FastAPI's `BackgroundTasks` -- there is no Celery or Redis-based task queue.

The frontend is a Vite-built React SPA with Tailwind CSS, React Router for navigation, TanStack Query for server state, and Zustand for client state. It includes an offline mutation queue that stores failed writes in localStorage and replays them when connectivity returns.

Photos are stored in Cloudflare R2. Only the R2 object key is persisted in the database; public URLs are constructed at runtime from configuration. This keeps the database portable across environments.

## Tech stack

**Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), asyncpg, Alembic, Pydantic v2, Anthropic SDK, boto3 (R2), Pillow, Jinja2, python-jose (JWT), passlib (bcrypt).

**Frontend:** TypeScript, React 18, Vite 6, Tailwind CSS 3, React Router 6, TanStack Query 5, React Hook Form, Zod, Zustand, Axios.

**Infrastructure:** PostgreSQL 15+, Cloudflare R2, Redis (reserved for future use).

## Prerequisites

- Python 3.11 or later
- Node.js 18 or later
- PostgreSQL 15 or later
- Redis (optional, included in docker-compose for development parity)
- A Cloudflare R2 bucket (or S3-compatible store) for photo storage
- An Anthropic API key for damage detection

## Quick start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Copy and edit environment variables
cp ../.env.example ../.env

# Create the database
createdb rental_damage

# Run migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API docs are available at `http://localhost:8000/api/docs` (Swagger) and `http://localhost:8000/api/redoc` (ReDoc).

### Frontend

```bash
cd frontend
npm install

# Start the development server (proxies /api to the backend)
npm run dev
```

The frontend runs at `http://localhost:5173` by default.

### Environment variables

See `.env.example` for a complete reference. At minimum, set:

- `DATABASE_URL` -- PostgreSQL connection string using `asyncpg`
- `ANTHROPIC_API_KEY` -- your Anthropic API key
- `JWT_SECRET_KEY` -- a strong random string for JWT signing
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` -- R2 credentials

## Project structure

```
rental-damage-detection/
  backend/
    alembic/                   # Database migration scripts
    alembic.ini
    pyproject.toml
    app/
      main.py                  # FastAPI application entry point
      core/
        config.py              # Pydantic Settings (env vars)
        security.py            # JWT creation/verification, password hashing
        logging.py             # Structured logging setup
      db/
        base.py                # SQLAlchemy DeclarativeBase
        session.py             # Async engine and session factory
      models/
        base.py                # Mixins: TimestampMixin, SoftDeleteMixin, TenantMixin
        tenant.py              # Tenant model
        user.py                # User model with roles (admin, operator, viewer)
        asset.py               # Asset model (jetski, boat, parasail, other)
        rental_session.py      # Rental session linking asset to renter
        inspection.py          # Pre/post-rental inspection
        photo.py               # Photo metadata (r2_key, not URL)
        finding.py             # AI-detected damage finding
        feedback.py            # Operator correction feedback
        model_metrics.py       # Aggregated accuracy metrics
        repair_cost.py         # Repair cost lookup table
      schemas/                 # Pydantic v2 request/response schemas
      api/
        deps.py                # Auth, tenant, pagination dependencies
        routes/
          auth.py              # Login, register, current user
          assets.py            # Asset CRUD
          rental_sessions.py   # Rental session management
          inspections.py       # Inspection CRUD + detection trigger
          photos.py            # Photo upload, retrieval, deletion
          findings.py          # Finding retrieval, review, feedback
          metrics.py           # Accuracy metrics endpoints
      services/
        damage_detection.py    # Core detection pipeline orchestrator
        storage_service.py     # R2 upload/download/presigned URLs
        image_validator.py     # Image quality gate (blur, brightness, resolution)
        prompt_builder.py      # Jinja2 prompt construction
        repair_cost_service.py # Repair cost lookup
        feedback_processor.py  # Feedback handling and accuracy tracking
      ml/
        claude_client.py       # Anthropic SDK wrapper with retry logic
        few_shot_engine.py     # Metadata-based few-shot example retrieval
        metrics_tracker.py     # Accuracy tracking per asset/damage type
      workers/
        detection_worker.py    # Background detection task runner
    tests/
      conftest.py
      test_api/
      test_services/
      test_ml/
  frontend/
    package.json
    src/
      App.tsx                  # Layout, routing, navigation
      main.tsx                 # React entry point
      lib/
        api.ts                 # Axios client with offline queue
        types.ts               # TypeScript type definitions
      stores/
        authStore.ts           # Auth state (Zustand)
        inspectionStore.ts     # Inspection flow state
      hooks/
        useCamera.ts           # Camera access hook
        useInspection.ts       # Inspection data hook
        useDamageDetection.ts  # Detection triggering hook
      components/
        common/                # Button, Card, Badge, Modal, LoadingSpinner, OfflineBanner
        camera/                # PhotoCapture, PhotoPreview
        inspection/            # InspectionFlow, BeforeAfterComparison, DamageReviewCard
        dashboard/             # FleetOverview, DamageHistory, AccuracyDashboard
```

## API overview

All endpoints are under `/api/v1`. Authentication uses JWT bearer tokens.

| Resource | Key endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/register`, `GET /auth/me` |
| Assets | `GET /assets`, `POST /assets`, `GET /assets/{id}`, `PUT /assets/{id}`, `DELETE /assets/{id}` |
| Rental Sessions | `GET /rental-sessions`, `POST /rental-sessions`, `POST /rental-sessions/{id}/complete` |
| Inspections | `GET /inspections/{id}`, `POST /inspections`, `POST /inspections/{id}/detect` |
| Photos | `POST /inspections/{id}/photos`, `GET /photos/{id}`, `DELETE /photos/{id}` |
| Findings | `GET /findings/{id}`, `PUT /findings/{id}/review`, `POST /findings/{id}/feedback` |
| Metrics | `GET /metrics/accuracy`, `GET /metrics/by-asset-type`, `GET /metrics/by-damage-type` |
| Health | `GET /health` |

See `docs/API.md` for full request/response documentation.

## Development workflow

1. Create a feature branch from `main`.
2. Make changes. The backend supports hot reload via `uvicorn --reload`. The frontend uses Vite's HMR.
3. Run linting and type checks before committing:
   ```bash
   # Backend
   cd backend && ruff check . && mypy app/

   # Frontend
   cd frontend && npm run lint && npm run type-check
   ```
4. Write tests for new functionality.
5. Open a pull request targeting `main`. CI runs linting, type checking, and tests for both backend and frontend.

## Testing

### Backend

```bash
cd backend
pip install -e ".[dev]"
pytest
```

Tests use `pytest-asyncio` with `asyncio_mode = "auto"`. The test database URL should be set via the `DATABASE_URL` environment variable pointing to a test database.

### Frontend

```bash
cd frontend
npm test           # Run tests in watch mode
npm run test:ui    # Run tests with the Vitest UI
```

Tests use Vitest with React Testing Library and jsdom.
