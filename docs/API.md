# API Reference

## Base URL and versioning

All API endpoints are prefixed with `/api/v1`. The OpenAPI spec is available at `/api/openapi.json`, Swagger UI at `/api/docs`, and ReDoc at `/api/redoc`.

```
Base URL: http://localhost:8000/api/v1
```

## Authentication

The API uses JWT bearer token authentication. Obtain a token via the login endpoint, then include it in the `Authorization` header of all subsequent requests.

### Login

```
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "operator@example.com",
  "password": "secure-password"
}
```

Response (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

The token contains claims: `sub` (user_id), `tenant_id`, `role`, `iat`, `exp`. Default expiration is 24 hours.

### Using the token

Include the token in the `Authorization` header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Register a new user (admin only)

```
POST /api/v1/auth/register
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "email": "new-user@example.com",
  "password": "secure-password",
  "full_name": "Jane Doe",
  "role": "operator"
}
```

Response (201):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "new-user@example.com",
  "full_name": "Jane Doe",
  "role": "operator",
  "tenant_id": "..."
}
```

Roles: `admin`, `operator`, `viewer`.

### Get current user

```
GET /api/v1/auth/me
Authorization: Bearer <token>
```

Response (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "operator@example.com",
  "full_name": "John Smith",
  "role": "operator",
  "tenant_id": "..."
}
```

## Assets

### Create asset

```
POST /api/v1/assets
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "WaveRunner EX",
  "asset_type": "jetski",
  "identifier": "HIN-YAM-2024-0042",
  "metadata": {
    "year": 2024,
    "make": "Yamaha",
    "model": "EX Deluxe",
    "color": "Blue/White"
  }
}
```

Response (201):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "WaveRunner EX",
  "asset_type": "jetski",
  "identifier": "HIN-YAM-2024-0042",
  "metadata": {
    "year": 2024,
    "make": "Yamaha",
    "model": "EX Deluxe",
    "color": "Blue/White"
  },
  "tenant_id": "...",
  "created_at": "2026-03-17T10:00:00Z",
  "updated_at": "2026-03-17T10:00:00Z"
}
```

Asset types: `jetski`, `boat`, `parasail`, `other`.

### List assets (paginated)

```
GET /api/v1/assets?page=1&page_size=20&asset_type=jetski&search=yamaha
Authorization: Bearer <token>
```

Query parameters:
- `page` (int, default 1): Page number (1-indexed).
- `page_size` (int, default 20, max 100): Items per page.
- `asset_type` (string, optional): Filter by asset type.
- `search` (string, optional): Search by name or identifier (case-insensitive partial match).

Response (200):
```json
{
  "items": [
    {
      "id": "...",
      "name": "WaveRunner EX",
      "asset_type": "jetski",
      "identifier": "HIN-YAM-2024-0042",
      "metadata": { "year": 2024 },
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

### Get asset

```
GET /api/v1/assets/{asset_id}
Authorization: Bearer <token>
```

### Update asset

```
PUT /api/v1/assets/{asset_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "WaveRunner EX Deluxe",
  "metadata": { "year": 2024, "color": "Red/White" }
}
```

### Delete asset (soft delete)

```
DELETE /api/v1/assets/{asset_id}
Authorization: Bearer <token>
```

Response: 204 No Content.

## Rental Sessions

### Create rental session

```
POST /api/v1/rental-sessions
Authorization: Bearer <token>
Content-Type: application/json

{
  "asset_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "renter_name": "Alice Johnson",
  "renter_contact": "alice@example.com",
  "started_at": "2026-03-17T09:00:00Z",
  "notes": "1-hour rental, waiver signed"
}
```

Response (201):
```json
{
  "id": "...",
  "asset_id": "...",
  "renter_name": "Alice Johnson",
  "renter_contact": "alice@example.com",
  "started_at": "2026-03-17T09:00:00Z",
  "ended_at": null,
  "status": "active",
  "pre_inspection_id": null,
  "post_inspection_id": null,
  "notes": "1-hour rental, waiver signed",
  "created_at": "...",
  "updated_at": "..."
}
```

Session statuses: `active`, `completed`, `disputed`.

### List rental sessions (paginated, filterable)

```
GET /api/v1/rental-sessions?page=1&page_size=20&status=active&asset_id=...&started_after=...&started_before=...
Authorization: Bearer <token>
```

### Get rental session

```
GET /api/v1/rental-sessions/{session_id}
Authorization: Bearer <token>
```

### Update rental session

```
PUT /api/v1/rental-sessions/{session_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "notes": "Extended to 2-hour rental"
}
```

### Complete rental session

```
POST /api/v1/rental-sessions/{session_id}/complete
Authorization: Bearer <token>
```

Sets `status` to `completed` and `ended_at` to the current timestamp. Returns 400 if the session is not in `active` status.

## Inspections

### Create inspection

```
POST /api/v1/inspections
Authorization: Bearer <token>
Content-Type: application/json

{
  "asset_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "rental_session_id": "...",
  "inspection_type": "post_rental",
  "location_lat": 25.7617,
  "location_lng": -80.1918,
  "notes": "Minor scuff noticed on starboard side"
}
```

Inspection types: `pre_rental`, `post_rental`.
Inspection statuses: `pending`, `analyzing`, `reviewed`, `approved`.

### Get inspection

```
GET /api/v1/inspections/{inspection_id}
Authorization: Bearer <token>
```

Returns the inspection with nested photos and findings.

### Update inspection

```
PUT /api/v1/inspections/{inspection_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "notes": "Updated notes after closer look"
}
```

### Trigger AI damage detection

```
POST /api/v1/inspections/{inspection_id}/detect
Authorization: Bearer <token>
Content-Type: application/json

{
  "before_photo_ids": [
    "photo-uuid-1",
    "photo-uuid-2"
  ],
  "after_photo_ids": [
    "photo-uuid-3",
    "photo-uuid-4"
  ]
}
```

Response (202 Accepted):
```json
{
  "inspection_id": "..."
}
```

The detection runs asynchronously. Poll the inspection endpoint to check status. Returns 400 if detection is already in progress.

## Photos

### Upload photo to inspection

```
POST /api/v1/inspections/{inspection_id}/photos
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <binary image data>
```

Constraints:
- Max file size: 10 MB (configurable via `MAX_PHOTO_SIZE_MB`).
- Allowed types: `image/jpeg`, `image/png`, `image/webp`, `image/heic`.

Response (201):
```json
{
  "id": "...",
  "inspection_id": "...",
  "r2_key": "tenants/.../inspections/.../photo-uuid.jpg",
  "sequence_order": 0,
  "original_filename": "IMG_0042.jpg",
  "content_type": "image/jpeg",
  "file_size_bytes": 2457600,
  "url": "https://pub-abc123.r2.dev/tenants/.../photo-uuid.jpg",
  "created_at": "..."
}
```

### Get photo

```
GET /api/v1/photos/{photo_id}
Authorization: Bearer <token>
```

### Delete photo (soft delete)

```
DELETE /api/v1/photos/{photo_id}
Authorization: Bearer <token>
```

Response: 204 No Content. The R2 object is retained for audit purposes.

## Findings

### Get finding

```
GET /api/v1/findings/{finding_id}
Authorization: Bearer <token>
```

Response (200):
```json
{
  "id": "...",
  "inspection_id": "...",
  "damage_type": "scratch",
  "location_description": "Starboard hull, approximately 30cm from the bow",
  "severity": "moderate",
  "confidence_score": 85,
  "ai_reasoning": "Clear linear mark visible in after photo that is not present in the before photo. Consistent with contact damage from a dock or piling.",
  "status": "pending",
  "before_photo_id": "...",
  "after_photo_id": "...",
  "bounding_box": { "x": 120, "y": 340, "width": 200, "height": 80 },
  "created_at": "..."
}
```

Finding statuses: `pending`, `confirmed`, `rejected`.
Severity levels: `minor`, `moderate`, `major`, `severe`.

### Review finding (operator)

Requires `admin` or `operator` role.

```
PUT /api/v1/findings/{finding_id}/review
Authorization: Bearer <token>
Content-Type: application/json

{
  "status": "confirmed"
}
```

Status must be `confirmed` or `rejected`. Returns 400 if the finding has already been reviewed.

### Submit feedback on finding

Requires `admin` or `operator` role.

```
POST /api/v1/findings/{finding_id}/feedback
Authorization: Bearer <token>
Content-Type: application/json

{
  "feedback_type": "severity_adjusted",
  "operator_notes": "This is a minor surface scratch, not moderate",
  "corrected_severity": "minor",
  "corrected_damage_type": null,
  "corrected_location": null
}
```

Feedback types: `true_positive`, `false_positive`, `false_negative`, `severity_adjusted`, `location_corrected`.

Response (201):
```json
{
  "id": "...",
  "finding_id": "...",
  "inspection_id": "...",
  "feedback_type": "severity_adjusted",
  "operator_notes": "This is a minor surface scratch, not moderate",
  "corrected_severity": "minor",
  "corrected_damage_type": null,
  "corrected_location": null,
  "operator_id": "...",
  "created_at": "..."
}
```

## Metrics

### Get overall accuracy

```
GET /api/v1/metrics/accuracy?model_version=claude-sonnet-4-20250514
Authorization: Bearer <token>
```

Response (200):
```json
{
  "id": "...",
  "model_version": "claude-sonnet-4-20250514",
  "period_start": "2026-03-01T00:00:00Z",
  "period_end": "2026-03-17T00:00:00Z",
  "total_inspections": 150,
  "total_findings": 320,
  "true_positives": 260,
  "false_positives": 60,
  "false_negatives": 15,
  "precision": 0.8125,
  "recall": 0.9455,
  "f1_score": 0.874,
  "avg_confidence": 78.5
}
```

### Get accuracy by asset type

```
GET /api/v1/metrics/by-asset-type
Authorization: Bearer <token>
```

### Get accuracy by damage type

```
GET /api/v1/metrics/by-damage-type
Authorization: Bearer <token>
```

## Health check

```
GET /health
```

No authentication required.

Response (200):
```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "ok"
}
```

Status is `degraded` if the database is unreachable.

## Error response format

All error responses follow a consistent format:

```json
{
  "detail": "Human-readable error message",
  "error_code": "OPTIONAL_MACHINE_CODE"
}
```

Common HTTP status codes:

| Code | Meaning |
|---|---|
| 400 | Bad request (validation error, invalid state transition) |
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (insufficient role) |
| 404 | Not found (resource does not exist or belongs to another tenant) |
| 413 | Payload too large (photo exceeds size limit) |
| 422 | Unprocessable entity (request body validation failure) |
| 500 | Internal server error |

## Rate limiting

The API returns rate limit information in response headers:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 57
X-RateLimit-Reset: 1710676800
```

Default limit: 60 requests per minute per authenticated user. The limit is configurable via the `API_RATE_LIMIT_PER_MINUTE` environment variable.

## Pagination

All list endpoints support pagination via query parameters:

- `page` (int, default 1): Page number, 1-indexed.
- `page_size` (int, default 20, max 100): Number of items per page.

Paginated responses include:

```json
{
  "items": [...],
  "total": 150,
  "page": 2,
  "page_size": 20,
  "total_pages": 8
}
```
