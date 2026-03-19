# CLAUDE.md -- Development Context for AI Assistants

This file provides context for AI coding assistants working on the Marine Intelligence Platform (DockGuard). Read this before making changes.

## Project overview

This is an AI-powered damage detection platform for marine rental equipment (jet skis, boats, parasails). Rental operators photograph assets before and after each rental period. The system uses Claude's vision API to compare before/after photos, identify new damage, and produce structured findings with confidence scores, severity levels, and location descriptions. Operators review findings and provide feedback, which is surfaced as few-shot examples in future prompts to improve accuracy over time.

The target users are marine equipment rental businesses that need to track damage across a fleet of assets, assign repair costs, and resolve disputes about when damage occurred.

## Key architecture decisions and rationale

### Multi-tenancy from day one

Every data model includes a `tenant_id` foreign key via the `TenantMixin` in `backend/app/models/base.py`. Every database query must filter by `tenant_id`. This is not optional -- it is the primary data isolation mechanism. The tenant ID is embedded in the JWT token and extracted via `get_current_tenant` in `backend/app/api/deps.py`.

**Why:** The platform serves multiple independent rental businesses. Row-level tenant isolation is simpler to implement correctly than schema-per-tenant and avoids operational complexity.

### Soft deletes everywhere

All models use `SoftDeleteMixin` which adds a `deleted_at` timestamp column. Deletion sets this timestamp; it never removes rows. Every query must include `Model.deleted_at.is_(None)`.

**Why:** Audit trail requirements. Rental damage records may be needed for insurance claims or legal disputes months after the fact. Hard deletes would destroy evidence.

### R2 keys not URLs in the database

The `photos` table stores `r2_key` (the object key in Cloudflare R2), never a full URL. Public URLs are constructed at runtime via `Photo.url` property and `Settings.get_r2_url()`.

**Why:** URLs contain the R2 public domain, which changes between environments (dev, staging, production) and when migrating between storage providers. Storing keys keeps the database portable.

### No Celery -- BackgroundTasks instead

AI damage detection runs via FastAPI's built-in `BackgroundTasks`. The worker is in `backend/app/workers/detection_worker.py`. There is no Celery, no Redis queue, no RabbitMQ.

**Why:** The workload does not yet justify a distributed task queue. Each detection call takes 10-30 seconds (one Claude API call). BackgroundTasks is sufficient for the current scale. When we need retry semantics, scheduled tasks, or horizontal scaling of workers, we will evaluate arq or Celery at that point.

### No embeddings, no pgvector -- metadata retrieval only

Few-shot examples are retrieved by filtering on discrete metadata columns (asset_type, damage_type) in `backend/app/ml/few_shot_engine.py`. There is no CLIP embedding, no pgvector extension, no vector similarity search.

**Why:** The correction dataset is small (hundreds to low thousands of feedback records per tenant). Simple SQL filtering on asset_type and damage_type retrieves relevant examples effectively. Adding embeddings introduces complexity (model hosting, index maintenance, query latency) that is not justified until the feedback corpus is large enough that metadata filtering returns too many irrelevant results.

### No LangChain -- Jinja2 templates

Prompts are built using a Jinja2 template in `backend/app/services/prompt_builder.py`. The template is stored as an inline string constant. There is no LangChain, no prompt framework, no chain-of-thought orchestration library.

**Why:** The prompt construction logic is a single template with conditional sections for few-shot examples and accuracy context. Jinja2 handles this perfectly. LangChain would add a large dependency tree, abstraction layers, and version churn for no functional benefit.

### Repair costs from lookup tables, not AI

Repair cost estimates come from the `repair_cost_lookups` table, queried in `backend/app/services/repair_cost_service.py`. They are keyed on (tenant_id, asset_type, damage_type, severity). Operators populate this data manually.

**Why:** Repair costs are business-specific and location-dependent. An AI model cannot reliably estimate that a "moderate scratch on a jetski hull" costs $200-400 for a specific operator in a specific market. The lookup table gives operators control over their own cost data.

## Code conventions

### SQLAlchemy 2.0 Mapped[] style

All models use the SQLAlchemy 2.0 declarative style with `Mapped[]` type annotations and `mapped_column()`:

```python
class Asset(Base, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
```

Do not use the legacy `Column()` style.

### Pydantic v2 patterns

All request/response schemas use Pydantic v2 with `model_config = ConfigDict(from_attributes=True)`. Use `model_validate()` for ORM-to-schema conversion. Do not use Pydantic v1's `.from_orm()` or `class Config`.

### All queries filter by tenant_id and deleted_at

Every database query that returns user-facing data must include:
```python
Model.tenant_id == tenant_id,
Model.deleted_at.is_(None),
```

There are no exceptions. If you write a query without these filters, you are creating a data leak or returning deleted records.

### Async everywhere in the backend

All database operations, storage operations, and route handlers are async. Use `await` with all session operations. The database session is `AsyncSession` from `sqlalchemy.ext.asyncio`. Do not introduce synchronous database calls.

### Logging

Use structured logging with `extra={}` dicts. Every log statement that involves a specific entity should include its ID:
```python
logger.info("Asset created", extra={"asset_id": asset.id, "tenant_id": tenant_id})
```

### Error handling

Route handlers raise `HTTPException` with appropriate status codes. Services raise `ValueError` for business logic errors. The caller (route handler) catches `ValueError` and converts to `HTTPException`.

## Common tasks

### Adding a new model

1. Create the model file in `backend/app/models/` inheriting from `Base`, `TimestampMixin`, `SoftDeleteMixin`, and `TenantMixin`.
2. Use `Mapped[]` type annotations with `mapped_column()`.
3. Import the model in `backend/app/models/__init__.py`.
4. Create corresponding Pydantic schemas in `backend/app/schemas/`.
5. Generate a migration: `cd backend && alembic revision --autogenerate -m "add <model_name> table"`
6. Review the generated migration, then apply: `alembic upgrade head`

### Adding a new endpoint

1. If the endpoint belongs to an existing resource, add it to the existing route file in `backend/app/api/routes/`.
2. If it is a new resource, create a new route file and register it in `backend/app/api/routes/__init__.py`.
3. Use the standard dependency pattern:
   ```python
   async def my_endpoint(
       db: Annotated[AsyncSession, Depends(get_db)],
       current_user: Annotated[User, Depends(get_current_user)],
       tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
   ) -> ResponseSchema:
   ```
4. Filter all queries by `tenant_id` and `deleted_at.is_(None)`.

### Adding a new prompt template section

1. Edit the `_SYSTEM_TEMPLATE` string in `backend/app/services/prompt_builder.py`.
2. Add the new template variable to the `build_damage_detection_prompt()` function signature.
3. Pass the variable in `backend/app/services/damage_detection.py` where the prompt is constructed.
4. Use Jinja2 conditional blocks (`{% if var %}...{% endif %}`) so the section is omitted when the variable is not provided.

## Testing approach

- Backend tests are in `backend/tests/` using pytest with `pytest-asyncio`.
- Test database configuration should use a separate database.
- Use `factory-boy` for generating test fixtures.
- Frontend tests use Vitest with React Testing Library.
- Run backend tests: `cd backend && pytest`
- Run frontend tests: `cd frontend && npm test`

## Current development state (as of 2026-03-17)

### Local environment

- **Database:** Supabase (free tier), direct connection on port 5432
- **Backend:** Python 3.13 venv at `backend/.venv`, runs on port 8000
- **Frontend:** Node 24, runs on port 3000 (not 5173)
- **Config:** `.env` lives at project root, `config.py` loads it via `env_file="../.env"`
- PostgreSQL 15 is installed via brew but STOPPED — we use Supabase instead

### Known issues fixed during setup

- `pyproject.toml` build-backend was `hatchling.backends` (wrong), changed to `hatchling.build`
- `pyproject.toml` was missing `email-validator`, changed `pydantic` to `pydantic[email]`
- `config.py` env_file was `.env` (relative to backend/), changed to `../.env`

### MVP blockers (see TODO.md for full checklist)

- No login page or auth guards in frontend
- No seed script to create initial tenant + admin user
- Detection worker `_run_detection()` is a placeholder — not wired to Claude API
- Photo upload route has R2 upload commented out as TODO
- Missing `GET /inspections` list endpoint
- Missing `POST /auth/logout` endpoint
- Frontend-backend schema mismatches on Asset, Inspection, and RentalSession models
- Frontend API client has wrong endpoint paths for photos, feedback, and detection

## What NOT to do

**Do not add LangChain.** The prompt construction is a single Jinja2 template. LangChain adds complexity without value here. If you are tempted to add it, re-read the prompt_builder.py module and confirm that Jinja2 cannot do what you need.

**Do not store URLs in the database.** Store R2 object keys only. URLs are constructed at runtime from `Settings.R2_PUBLIC_URL` + the key. This is enforced in the Photo model.

**Do not use Celery or any external task queue.** Background work uses FastAPI `BackgroundTasks`. When this becomes insufficient, the team will evaluate options and make an explicit architecture decision.

**Do not ask Claude for repair costs.** Repair costs come from the `repair_cost_lookups` table. They are business data managed by operators, not AI predictions. Never include a prompt instruction asking Claude to estimate dollar amounts.

**Do not add pgvector or embedding-based retrieval.** Few-shot examples are retrieved by metadata filtering. When the feedback corpus grows large enough to warrant semantic search, this decision will be revisited with benchmarks.

**Do not use synchronous database calls.** All database access goes through `AsyncSession`. Do not import or use synchronous `Session`.

**Do not hard-delete records.** Use `model.soft_delete()` which sets `deleted_at`. If you need to purge data, that is a separate administrative operation that does not exist yet.

**Do not skip tenant_id filtering.** Every user-facing query must be scoped to the authenticated tenant. There are no global queries in the API layer.
