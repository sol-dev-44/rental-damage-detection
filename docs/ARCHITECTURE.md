# Architecture

## System overview

The Marine Intelligence Platform is composed of four primary components:

**FastAPI Backend** (`backend/app/`): A Python application serving a versioned REST API at `/api/v1`. It handles authentication, CRUD operations for all domain entities, photo upload orchestration, AI damage detection pipeline execution, operator feedback processing, and accuracy metrics computation. All I/O is async.

**React Frontend** (`frontend/src/`): A single-page application built with Vite, React 18, and TypeScript. It provides the operator interface for fleet management, inspection workflows (including camera integration), damage review with before/after comparison, and accuracy dashboards. The frontend communicates exclusively through the REST API and includes an offline mutation queue for field use.

**PostgreSQL Database**: The primary data store. All tables enforce multi-tenancy via `tenant_id` foreign keys. The schema is managed by Alembic migrations. The database stores all domain data including inspection records, AI findings, operator feedback, repair cost lookup tables, and aggregated accuracy metrics.

**Cloudflare R2 Object Storage**: Stores inspection photos. The database holds only the R2 object key for each photo; public URLs are constructed at runtime from application configuration. R2 is accessed via the S3-compatible API using boto3.

### Supporting modules

- `backend/app/ml/claude_client.py` -- Thin wrapper around the Anthropic Python SDK. Handles image encoding, message construction, retry with exponential backoff, JSON response parsing, and cost tracking.
- `backend/app/services/prompt_builder.py` -- Constructs system and user prompts via Jinja2 templates. Incorporates asset context, few-shot correction examples, known false-positive patterns, and historical accuracy data.
- `backend/app/ml/few_shot_engine.py` -- Retrieves past operator corrections from the `feedback` table by filtering on asset_type and damage_type. These corrections are injected into prompts as in-context examples.
- `backend/app/services/image_validator.py` -- Quality gate that checks blur (Laplacian variance), brightness, and resolution using Pillow. Photos that fail validation are excluded from the detection pipeline to avoid wasting API spend.
- `backend/app/services/repair_cost_service.py` -- Looks up repair cost estimates from the `repair_cost_lookups` table. Costs are operator-managed business data, not AI predictions.

## Data flow

### Inspection and detection flow

1. Operator creates a rental session, linking an asset to a renter.
2. Before the rental, operator creates a pre-rental inspection and uploads photos. Photos are stored in R2; only the `r2_key` is written to the `photos` table.
3. After the rental, operator creates a post-rental inspection with new photos.
4. Operator triggers damage detection via `POST /api/v1/inspections/{id}/detect`, providing before and after photo IDs.
5. The backend validates that the inspection exists and photos belong to the tenant, sets the inspection status to `ANALYZING`, and enqueues a background task.
6. The background task (in `detection_worker.py`) calls `damage_detection.detect_damage()`, which:
   a. Downloads photo bytes from R2.
   b. Validates image quality (blur, brightness, resolution). Failing photos are skipped.
   c. Retrieves few-shot correction examples from the `feedback` table via `few_shot_engine.get_similar_cases()`.
   d. Queries historical accuracy data from `metrics_tracker.get_accuracy_by_asset_type()`.
   e. Renders the system prompt using `prompt_builder.build_damage_detection_prompt()`.
   f. Sends the prompt and images to Claude via `claude_client.send_vision_request()`.
   g. Parses the structured JSON response.
   h. Creates `Finding` records for each detected damage item above the confidence threshold.
   i. Looks up estimated repair costs from the `repair_cost_lookups` table.
   j. Updates the inspection status to `REVIEWED`.
7. The frontend polls the inspection status and displays findings when ready.

### Feedback flow

1. Operator reviews AI-generated findings in the frontend.
2. For each finding, operator can confirm (true positive), reject (false positive), or correct (severity adjusted, location corrected).
3. Feedback is submitted via `POST /api/v1/findings/{id}/feedback`.
4. The backend creates a `Feedback` record, updates the finding's status, and records the prediction outcome for accuracy tracking.
5. Future detection requests for the same asset type will retrieve these corrections as few-shot examples, enabling the system to avoid repeating the same mistakes.

### Accuracy metrics flow

1. Each feedback submission is recorded by `metrics_tracker.record_prediction()`.
2. Aggregate accuracy metrics can be queried via the metrics API endpoints.
3. The `model_metrics` table stores periodic snapshots of precision, recall, F1, and confidence calibration data.
4. Historical accuracy per asset type is injected into the prompt via `accuracy_context`, allowing Claude to self-calibrate (e.g., be more conservative on damage types where past accuracy has been low).

## Multi-tenancy design

Tenant isolation is enforced at the data layer through three mechanisms:

1. **TenantMixin**: Every domain model inherits from `TenantMixin` (`backend/app/models/base.py`), which adds a `tenant_id` column with a foreign key to `tenants.id` and an index.

2. **Query-level filtering**: Every database query in the API layer includes `Model.tenant_id == tenant_id` in its WHERE clause. This is a manual convention enforced through code review, not an automatic row-level security policy.

3. **JWT-embedded tenant ID**: The JWT token contains the tenant_id claim (set during login in `backend/app/core/security.py`). The `get_current_tenant` dependency in `backend/app/api/deps.py` extracts it. The tenant ID used in queries always comes from the JWT, never from request parameters.

R2 storage keys are namespaced by tenant: `tenants/{tenant_id}/inspections/{inspection_id}/{photo_id}.{ext}`.

## Authentication flow

1. User submits email and password to `POST /api/v1/auth/login`.
2. The backend verifies credentials against the bcrypt hash stored in `users.hashed_password`.
3. On success, a JWT is generated containing `sub` (user_id), `tenant_id`, `role`, `iat`, and `exp` claims. The token is signed with HS256 using `JWT_SECRET_KEY`.
4. The frontend stores the token in localStorage and attaches it as a `Bearer` token in the `Authorization` header on every request (via an Axios interceptor in `frontend/src/lib/api.ts`).
5. Protected endpoints use the `get_current_user` dependency, which decodes and verifies the JWT, then loads the user from the database (confirming they are not soft-deleted).
6. Role-based access control is provided by the `require_role()` dependency factory. Roles are: `admin` (full access including user registration), `operator` (can create inspections, review findings, submit feedback), and `viewer` (read-only access).

## Offline support strategy

The frontend is designed for use on docks and marinas where connectivity may be intermittent:

1. **Offline detection**: The `OfflineBanner` component monitors `navigator.onLine` and displays a banner when the device is offline.

2. **Mutation queue**: When a write request (POST, PUT, PATCH, DELETE) fails due to being offline, the Axios response interceptor in `frontend/src/lib/api.ts` captures the request and stores it in localStorage under the key `dockguard_offline_queue`.

3. **Auto-flush**: When the browser fires the `online` event, `flushOfflineQueue()` replays queued mutations in order, removing each one on success. If any mutation fails, processing stops (the network may still be unreliable).

4. **Photo capture**: The camera components capture photos locally. In a future iteration, photos will be stored in IndexedDB when offline and uploaded when connectivity returns.

This is not a full offline-first architecture with local-first sync. It is a pragmatic queue-and-replay strategy for the most common failure mode: brief connectivity drops during field inspections.

## Why certain tools were NOT chosen

### Celery / Redis task queue

Background detection tasks run via FastAPI's `BackgroundTasks`. This is simpler to deploy and operate than Celery + Redis/RabbitMQ. The current workload is sequential (one Claude API call per detection, taking 10-30 seconds). The tradeoffs:

- No automatic retry with backoff (the worker handles this manually).
- No task persistence across server restarts (a task running when the server stops is lost).
- No horizontal scaling of workers independently of the API server.

These limitations are acceptable at current scale. When they become constraints, arq (Redis-based, async-native) is the likely replacement.

### LangChain / LlamaIndex / prompt frameworks

The prompt construction is a single Jinja2 template with conditional sections. There is no multi-step reasoning chain, no agent loop, no tool use. A prompt framework would add:

- A large dependency tree with frequent breaking changes.
- Abstraction layers that obscure the actual prompt being sent.
- Configuration complexity that is not justified by the use case.

Jinja2 is well-understood, has stable APIs, and handles the template logic cleanly.

### pgvector / vector similarity search

Few-shot examples are retrieved by filtering on `asset_type` and `damage_type` columns. This works because:

- The feedback corpus per tenant is small (hundreds to low thousands of records).
- The relevant dimensions for example retrieval are discrete categories, not continuous semantic similarity.
- Adding pgvector requires installing the extension, managing embedding generation (another model call), maintaining vector indices, and tuning similarity thresholds.

When tenants accumulate enough feedback that metadata filtering returns too many results and example quality degrades, vector similarity will be evaluated with benchmarks comparing retrieval quality against the current approach.

### Model fine-tuning

The system does not fine-tune or train any model. Claude is used as a general-purpose vision model with prompt engineering. Operator corrections are surfaced as few-shot examples in the prompt, not used for weight updates. This keeps the system simple and avoids the operational burden of managing custom model versions.
