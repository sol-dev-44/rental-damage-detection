# Deployment

## Environment variables reference

All environment variables are defined in `backend/app/core/config.py` as a Pydantic `Settings` class. See `.env.example` for a copyable template with comments.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://postgres:postgres@localhost:5432/rental_damage` | PostgreSQL connection string (must use asyncpg driver) |
| `DATABASE_POOL_SIZE` | No | `10` | SQLAlchemy connection pool size per worker |
| `R2_ACCOUNT_ID` | Yes | `""` | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | Yes | `""` | R2 API token access key |
| `R2_SECRET_ACCESS_KEY` | Yes | `""` | R2 API token secret key |
| `R2_BUCKET_NAME` | No | `rental-damage-photos` | R2 bucket name |
| `R2_PUBLIC_URL` | Yes | `""` | Public URL prefix for photo access |
| `ANTHROPIC_API_KEY` | Yes | `""` | Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-20250514` | Claude model identifier |
| `JWT_SECRET_KEY` | Yes | `CHANGE-ME-IN-PRODUCTION` | JWT signing secret (must be changed in production) |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_EXPIRATION_MINUTES` | No | `1440` | JWT token lifetime in minutes |
| `MIN_CONFIDENCE_THRESHOLD` | No | `70` | Minimum AI confidence to include a finding (0-100) |
| `SIMILAR_CASES_LIMIT` | No | `5` | Max few-shot examples in prompt |
| `MAX_PHOTO_SIZE_MB` | No | `10` | Max photo upload size in MB |
| `ALLOWED_IMAGE_TYPES` | No | `["image/jpeg","image/png","image/webp","image/heic"]` | Accepted MIME types |
| `API_RATE_LIMIT_PER_MINUTE` | No | `60` | Rate limit per user per minute |

## Local development setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Git

### Step-by-step

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd rental-damage-detection
   ```

2. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your values (at minimum: DATABASE_URL, ANTHROPIC_API_KEY, JWT_SECRET_KEY)
   ```

3. Set up the database:
   ```bash
   createdb rental_damage
   ```

4. Set up the backend:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate    # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   alembic upgrade head
   ```

5. Start the backend:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. Set up the frontend (in a separate terminal):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

7. Verify:
   - Backend health: `curl http://localhost:8000/health`
   - API docs: `http://localhost:8000/api/docs`
   - Frontend: `http://localhost:5173`

## Docker Compose usage

The project includes a `docker-compose.yml` for development with all services preconfigured.

### Start all services

```bash
docker compose up -d
```

This starts PostgreSQL, Redis, the backend, and the frontend.

### View logs

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### Stop all services

```bash
docker compose down
```

### Reset database

```bash
docker compose down -v    # Remove volumes
docker compose up -d
```

### Run migrations in Docker

```bash
docker compose exec backend alembic upgrade head
```

## Production deployment considerations

### Application server

Run the backend with multiple uvicorn workers behind a reverse proxy (nginx, Caddy, or a cloud load balancer):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Alternatively, use gunicorn with uvicorn workers:

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Frontend build

Build the frontend for production:

```bash
cd frontend
npm run build
```

The output in `frontend/dist/` is a static site that can be served by nginx, Caddy, Cloudflare Pages, or any static hosting provider. Configure the reverse proxy to route `/api` requests to the backend.

### Security checklist

- Set `JWT_SECRET_KEY` to a strong random value (minimum 64 characters). Generate one with: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- Restrict CORS origins in production (currently `allow_origins=["*"]` in `backend/app/main.py`).
- Use HTTPS everywhere.
- Set `DATABASE_URL` with a non-default password and restricted network access.
- Rotate R2 API tokens periodically.
- Monitor Anthropic API spend via the structured logs that track `cost_usd` per detection call.

### Scaling considerations

- The backend is stateless. Scale horizontally by adding more uvicorn workers or container replicas.
- The database connection pool is `DATABASE_POOL_SIZE` per worker. With 4 workers at pool size 10, that is 40 connections. Size PostgreSQL's `max_connections` accordingly.
- Background detection tasks run in-process via `BackgroundTasks`. Under heavy load, these compete with request handling for CPU. If this becomes a bottleneck, extract detection into a separate worker process using arq or a similar async task queue.
- R2 has no connection pooling concerns; boto3 manages its own HTTP session pool.

## Database setup

### PostgreSQL installation

On macOS:
```bash
brew install postgresql@15
brew services start postgresql@15
```

On Ubuntu/Debian:
```bash
sudo apt install postgresql-15
sudo systemctl start postgresql
```

### Create the database

```bash
createdb rental_damage
```

For production, create a dedicated user:
```sql
CREATE USER dockguard WITH PASSWORD 'secure-password';
CREATE DATABASE rental_damage OWNER dockguard;
```

### Run migrations

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

### Verify

```bash
psql rental_damage -c "\dt"
```

## R2 bucket setup

1. Log in to the Cloudflare dashboard.
2. Navigate to R2 Object Storage.
3. Create a bucket named `rental-damage-photos` (or your chosen name).
4. Create an R2 API token with `Object Read & Write` permissions for the bucket.
5. Note the Account ID, Access Key ID, and Secret Access Key.
6. If you need public access to photos, configure a custom domain or use R2's public bucket URL.
7. Set the environment variables:
   ```
   R2_ACCOUNT_ID=<your-account-id>
   R2_ACCESS_KEY_ID=<your-access-key-id>
   R2_SECRET_ACCESS_KEY=<your-secret-access-key>
   R2_BUCKET_NAME=rental-damage-photos
   R2_PUBLIC_URL=https://your-public-bucket-url.r2.dev
   ```

### CORS configuration

If the frontend accesses R2 directly (e.g., for image display), configure CORS on the bucket:

```json
[
  {
    "AllowedOrigins": ["https://your-frontend-domain.com"],
    "AllowedMethods": ["GET"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

## Monitoring and logging

### Structured logging

The backend uses Python's `logging` module with structured `extra={}` dicts. Every significant operation logs:

- Entity IDs (inspection_id, finding_id, tenant_id)
- Operation outcomes (success, failure, skip)
- Performance data (duration_s, token counts, cost_usd)
- Quality metrics (quality_score, confidence)

To enable JSON-formatted logs for production, configure the logging setup in `backend/app/core/logging.py` to use a JSON formatter (e.g., `python-json-logger`).

### Key metrics to monitor

**API performance**: Request latency, error rates, and throughput. Use the `/health` endpoint for uptime monitoring.

**AI pipeline**: Track these fields from the detection completion logs:
- `duration_s`: Total detection pipeline time.
- `api_cost_usd`: Estimated Anthropic API cost per detection.
- `api_tokens_in` / `api_tokens_out`: Token usage per call.
- `num_findings`: Number of findings per detection.

**Database**: Monitor connection pool utilization, query latency, and table sizes. The `model_metrics` and `feedback` tables grow continuously.

**R2 storage**: Monitor bucket size and request counts. Photo uploads are the primary cost driver.

### Health check

The `/health` endpoint returns service status and database connectivity:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "ok"
}
```

Status is `degraded` if the database is unreachable. Use this endpoint for load balancer health checks and uptime monitoring.

### Error tracking

Consider integrating Sentry or a similar error tracking service. The backend's exception handling logs all errors with `exc_info=True`, providing full stack traces in the logs. The detection worker (`backend/app/workers/detection_worker.py`) has explicit error handling that logs failures and resets inspection status on error.
