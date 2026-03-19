# Database

## Schema overview

The database is PostgreSQL 15+ accessed via SQLAlchemy 2.0 with the asyncpg driver. All models inherit from a shared `DeclarativeBase` in `backend/app/db/base.py` and use the SQLAlchemy 2.0 `Mapped[]` annotation style.

### Tables

| Table | Model file | Description |
|---|---|---|
| `tenants` | `models/tenant.py` | Rental business organizations. Top-level isolation unit. |
| `users` | `models/user.py` | Operator accounts with role-based access (admin, operator, viewer). |
| `assets` | `models/asset.py` | Fleet equipment (jet skis, boats, parasails). |
| `rental_sessions` | `models/rental_session.py` | Individual rental periods linking an asset to a renter. |
| `inspections` | `models/inspection.py` | Pre-rental and post-rental inspections of an asset. |
| `photos` | `models/photo.py` | Photo metadata; R2 object keys stored here, not URLs. |
| `findings` | `models/finding.py` | AI-detected damage items with confidence scores and severity. |
| `feedback` | `models/feedback.py` | Operator corrections on AI findings (true/false positive, severity adjustments). |
| `model_metrics` | `models/model_metrics.py` | Aggregated accuracy metrics per model version and time period. |
| `repair_cost_lookups` | `models/repair_cost.py` | Operator-managed repair cost estimates by asset type, damage type, severity. |

### Common columns

All domain tables include these columns via mixins defined in `backend/app/models/base.py`:

**TimestampMixin**: `created_at` (server default `now()`), `updated_at` (server default `now()`, updated on change).

**SoftDeleteMixin**: `deleted_at` (nullable timestamp; null means active, non-null means soft-deleted). Provides `is_deleted` property, `soft_delete()` method, and `restore()` method.

**TenantMixin**: `tenant_id` (UUID foreign key to `tenants.id`, indexed, non-nullable).

`model_metrics` uses `TimestampMixin` and `TenantMixin` but not `SoftDeleteMixin` (metrics snapshots are not soft-deletable).

## Relationship diagram

```
tenants
  |
  +-- users (tenant_id -> tenants.id)
  |
  +-- assets (tenant_id -> tenants.id)
  |     |
  |     +-- rental_sessions (asset_id -> assets.id)
  |     |     |
  |     |     +-- inspections (rental_session_id -> rental_sessions.id)  [optional]
  |     |     |     pre_inspection_id -> inspections.id  [optional, bidirectional]
  |     |     |     post_inspection_id -> inspections.id  [optional, bidirectional]
  |     |
  |     +-- inspections (asset_id -> assets.id)
  |           |
  |           +-- photos (inspection_id -> inspections.id)
  |           |
  |           +-- findings (inspection_id -> inspections.id)
  |                 |
  |                 +-- feedback (finding_id -> findings.id)
  |                       inspection_id -> inspections.id  [denormalized]
  |                       operator_id -> users.id
  |
  +-- repair_cost_lookups (tenant_id -> tenants.id)
  |
  +-- model_metrics (tenant_id -> tenants.id)

findings also reference:
  before_photo_id -> photos.id  [optional]
  after_photo_id -> photos.id   [optional]

inspections also reference:
  inspector_id -> users.id
```

## Key design decisions

### Rental session linking

The `rental_sessions` table has two optional foreign keys: `pre_inspection_id` and `post_inspection_id`, both pointing to `inspections.id` with `use_alter=True` (deferred FK creation to handle circular references). This allows a rental session to explicitly link to its before and after inspections.

Inspections also have a `rental_session_id` column pointing back to `rental_sessions.id`. This bidirectional link is intentional: it allows querying both "what inspections belong to this session" and "which session does this inspection belong to" without complex joins.

### Soft deletes

Every domain table uses `SoftDeleteMixin`. Records are never physically deleted via the API. The `soft_delete()` method sets `deleted_at = datetime.now(timezone.utc)`. Every query must include `Model.deleted_at.is_(None)` to exclude soft-deleted records.

This design supports:
- Audit trail for insurance and legal disputes.
- Data recovery (via the `restore()` method).
- Referential integrity (foreign keys are never broken by deletion).

### Repair cost lookups

The `repair_cost_lookups` table has a unique constraint on `(tenant_id, asset_type, damage_type, severity)`. This ensures each combination has exactly one cost entry per tenant. Costs include `min_cost`, `max_cost`, `avg_cost`, and `currency`.

Costs are not AI-generated. They are business data entered and maintained by operators. The lookup is performed in `backend/app/services/repair_cost_service.py` and returns `None` if no matching row exists.

### Photo storage pattern

The `photos` table stores `r2_key` (the object key in Cloudflare R2), not a URL. The column comment explicitly states: "Object key in R2 -- never store full URLs." The `Photo` model has a computed `url` property that constructs the full URL at runtime using `Settings.get_r2_url(self.r2_key)`.

R2 keys follow the pattern: `tenants/{tenant_id}/inspections/{inspection_id}/{photo_id}.{extension}`.

### JSONB columns

Several tables use JSONB for semi-structured data:

- `tenants.settings`: Tenant-specific configuration.
- `assets.metadata`: Equipment details (year, make, model, color). Mapped as `metadata_` in Python to avoid shadowing the SQLAlchemy `metadata` attribute.
- `photos.metadata`: Camera settings, dimensions, quality scores.
- `findings.bounding_box`: `{"x": int, "y": int, "width": int, "height": int}` in pixels.
- `model_metrics.severity_accuracy`: Per-severity accuracy breakdown.
- `model_metrics.damage_type_accuracy`: Per-damage-type accuracy breakdown.

### Enum types

PostgreSQL enum types are used for status and category columns:

| Enum name | Values | Used by |
|---|---|---|
| `user_role` | admin, operator, viewer | `users.role` |
| `asset_type` | jetski, boat, parasail, other | `assets.asset_type` |
| `rental_session_status` | active, completed, disputed | `rental_sessions.status` |
| `inspection_type` | pre_rental, post_rental | `inspections.inspection_type` |
| `inspection_status` | pending, analyzing, reviewed, approved | `inspections.status` |
| `damage_severity` | minor, moderate, major, severe | `findings.severity` |
| `finding_status` | pending, confirmed, rejected | `findings.status` |
| `feedback_type` | true_positive, false_positive, false_negative, severity_adjusted, location_corrected | `feedback.feedback_type` |

## Migration workflow

Migrations are managed by Alembic. Configuration is in `backend/alembic.ini` and the env file is at `backend/alembic/env.py`. Migration scripts are stored in `backend/alembic/versions/`.

### Generate a new migration

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
```

Always review the generated migration file. Alembic autogenerate does not catch all changes (e.g., changes to check constraints, custom indexes, or JSONB column defaults).

### Apply migrations

```bash
# Apply all pending migrations
cd backend
alembic upgrade head

# Apply a specific migration
alembic upgrade <revision_id>
```

### Roll back

```bash
# Roll back one migration
cd backend
alembic downgrade -1

# Roll back to a specific revision
alembic downgrade <revision_id>
```

### View migration history

```bash
cd backend
alembic history --verbose
alembic current
```

## Indexing strategy

### Primary keys

All tables use UUID primary keys generated by `uuid.uuid4()` in Python. UUIDs are stored as `UUID(as_uuid=True)` using the PostgreSQL native UUID type.

### Explicit indexes

The following columns have explicit indexes defined in the model declarations:

| Table | Column | Rationale |
|---|---|---|
| `tenants` | `slug` | Unique lookup by tenant slug |
| `users` | `email` | Unique lookup for login |
| `users` | `tenant_id` | Filter users by tenant |
| `assets` | `identifier` | Lookup by hull number, registration, etc. |
| `assets` | `tenant_id` | Filter assets by tenant |
| `rental_sessions` | `asset_id` | Find sessions for an asset |
| `rental_sessions` | `tenant_id` | Filter by tenant |
| `inspections` | `asset_id` | Find inspections for an asset |
| `inspections` | `rental_session_id` | Find inspections for a session |
| `inspections` | `tenant_id` | Filter by tenant |
| `photos` | `inspection_id` | Find photos for an inspection |
| `photos` | `tenant_id` | Filter by tenant |
| `findings` | `inspection_id` | Find findings for an inspection |
| `findings` | `tenant_id` | Filter by tenant |
| `feedback` | `finding_id` | Find feedback for a finding |
| `feedback` | `inspection_id` | Find feedback for an inspection |
| `feedback` | `tenant_id` | Filter by tenant |

### Composite indexes to consider

The following composite indexes are not yet defined but should be added when query patterns demand them:

- `(tenant_id, deleted_at)` on all major tables -- every query filters by both.
- `(tenant_id, asset_type, damage_type, severity)` on `repair_cost_lookups` -- this matches the unique constraint but an explicit index ensures fast lookups.
- `(tenant_id, feedback_type, created_at DESC)` on `feedback` -- used by the few-shot engine for retrieving recent corrections.
- `(tenant_id, computed_at DESC)` on `model_metrics` -- used by the metrics endpoints to find the latest snapshot.
