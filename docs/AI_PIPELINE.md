# AI Pipeline

## Overview

The damage detection pipeline is a retrieval-augmented prompting system, not a trained model. Each detection request constructs a fresh prompt that includes relevant historical corrections, sends it to Claude's vision API with before/after photos, parses the structured JSON response, and creates finding records in the database. Claude has no persistent memory between requests.

The core orchestrator is `backend/app/services/damage_detection.py`. It coordinates all stages of the pipeline.

## End-to-end detection flow

### 1. Request initiation

An operator triggers detection via `POST /api/v1/inspections/{id}/detect` with a list of before and after photo IDs. The endpoint validates inputs and enqueues a `BackgroundTasks` callback. The inspection status is set to `ANALYZING`.

### 2. Photo retrieval and validation

The pipeline loads `Photo` records from the database (scoped to the tenant), then downloads the actual image bytes from R2 via `storage_service.download_photo()`.

Each image passes through the quality gate in `backend/app/services/image_validator.py`:

- **Content type check**: Must be `image/jpeg`, `image/png`, or `image/webp`.
- **File size check**: Must not exceed `MAX_PHOTO_SIZE_MB` (default 10 MB).
- **Resolution check**: Minimum 640x480 pixels.
- **Blur detection**: Computes the variance of a Laplacian-filtered grayscale version using Pillow. Images with variance below the threshold (50.0) are flagged as blurry.
- **Brightness check**: Mean luminance of the grayscale image must be between 30 and 235 (0-255 scale). Images outside this range are flagged as too dark or overexposed.

A composite quality score (0.0-1.0) is computed as a weighted combination: 40% sharpness, 30% brightness, 30% resolution. Photos that fail any check are logged and skipped. If no valid after-photos remain, the pipeline raises a `ValueError` and aborts.

### 3. Few-shot example retrieval

`backend/app/ml/few_shot_engine.py` queries the `feedback` table for past operator corrections on the same asset type. The query joins `feedback -> finding -> inspection -> asset` and filters:

- `asset.asset_type` matches the current asset type.
- `feedback.feedback_type` is one of: `FALSE_POSITIVE`, `SEVERITY_ADJUSTED`, `LOCATION_CORRECTED` (corrections, not confirmations).
- `feedback.tenant_id` matches the current tenant.
- `feedback.deleted_at IS NULL` and `finding.deleted_at IS NULL`.

Results are ordered by recency (most recent first) and limited to `SIMILAR_CASES_LIMIT` (default 5). If specific damage types are provided, matching rows are prioritized but non-matching rows still fill remaining slots.

Each example is formatted as a dict with keys: `original_damage_type`, `original_severity`, `original_confidence`, `feedback_type`, `corrected_damage_type`, `corrected_severity`, `corrected_location`, `operator_notes`.

This is metadata-based filtering, not vector similarity search. See the Architecture doc for why pgvector is not used.

### 4. Accuracy context gathering

`backend/app/ml/metrics_tracker.py` computes aggregate accuracy statistics for the tenant, broken down by asset type. This queries the `feedback` table, counting true positives and false positives per asset type, and computes accuracy ratios.

The resulting context (e.g., `"jetski overall accuracy": "84%"`) is passed to the prompt builder so Claude can self-calibrate -- being more conservative on asset types or damage categories where past accuracy has been low.

### 5. Prompt construction with Jinja2

`backend/app/services/prompt_builder.py` renders the system prompt using a Jinja2 template. The template is stored as an inline string constant (no external template files). Key sections:

**Asset context**: Asset type, identifier, and optional metadata (year, make, model, color).

**Instructions**: Detailed task description telling Claude to compare before/after photos, identify only NEW damage, and return structured JSON. The instructions specify the response schema and emphasize conservative reporting (prefer missed damage over false positives).

**Known false-positive patterns**: Hardcoded per asset type in `_FALSE_POSITIVE_PATTERNS`. Examples for jetskis: "Water spots or salt residue that look like discoloration", "Reflection or glare on wet surfaces that resemble scratches". These patterns are derived from common operator corrections.

**Few-shot correction examples**: Retrieved by the few-shot engine. Each example shows what the AI originally reported, what the operator corrected it to, and why. These are explicitly labeled as "retrieval-augmented prompting examples, not learned behaviour" so there is no ambiguity about Claude's capabilities.

**Historical accuracy context**: Optional statistics (e.g., "scratch accuracy on jetski: 62%") to inform confidence calibration.

**Required output format**: A JSON schema specifying the expected response structure with `findings` array containing `damage_type`, `location_description`, `severity`, `confidence_score`, `ai_reasoning`, and optional `bounding_box`.

A separate user message is built by `build_user_message()`, describing how many before and after photos are attached.

### 6. Claude vision API call

`backend/app/ml/claude_client.py` handles the Anthropic API interaction:

- Images are base64-encoded and assembled into content blocks with text labels ("BEFORE photos:", "AFTER photos:").
- The request uses `anthropic.Anthropic().messages.create()` with the rendered system prompt and user message.
- The client retries up to 3 times with exponential backoff on transient errors (`RateLimitError`, `InternalServerError`, `APIConnectionError`).
- Non-retryable errors (`APIError`) fail immediately.
- Token usage and estimated cost (based on input/output token counts) are tracked in the result.
- The response text is parsed as JSON, with handling for markdown code fences that Claude occasionally wraps around the output.

The default model is `claude-sonnet-4-20250514`, configurable via `ANTHROPIC_MODEL`.

### 7. Response parsing and finding creation

The pipeline processes Claude's JSON response:

- Extracts the `findings` array.
- Filters out findings with `confidence_score` below `MIN_CONFIDENCE_THRESHOLD` (default 70).
- Maps severity strings to the `DamageSeverity` enum (`minor`, `moderate`, `major`, `severe`). Unknown values default to `MINOR` with a warning log.
- Creates `Finding` ORM objects with: `inspection_id`, `tenant_id`, `damage_type`, `location_description`, `severity`, `confidence_score`, `ai_reasoning`, `before_photo_id`, `after_photo_id`, optional `bounding_box`, and status `PENDING`.
- Flushes to the database session.

### 8. Repair cost lookup

For each created finding, `repair_cost_service.get_estimated_cost()` queries the `repair_cost_lookups` table for a match on (tenant_id, asset_type, damage_type, severity). Cost data is informational -- it is surfaced to the operator via the findings API response but does not affect the detection logic.

### 9. Status update and logging

The inspection status is set to `REVIEWED`. The pipeline logs completion with structured data including: inspection ID, number of findings, estimated API cost in USD, input/output token counts, and total duration in seconds.

## Feedback loop

When an operator reviews a finding and submits feedback (via `POST /api/v1/findings/{id}/feedback`), the feedback processor (`backend/app/services/feedback_processor.py`):

1. Creates a `Feedback` record with the feedback type, corrections, and operator notes.
2. Updates the finding's status based on feedback type:
   - `TRUE_POSITIVE` -> `CONFIRMED`
   - `FALSE_POSITIVE` -> `REJECTED`
   - `SEVERITY_ADJUSTED` -> `CONFIRMED`
   - `LOCATION_CORRECTED` -> `CONFIRMED`
3. Records the prediction outcome for accuracy tracking.

The feedback record is then available for retrieval by the few-shot engine on future detection requests. This creates a closed loop: operator corrections improve future prompt quality, which improves detection accuracy, which reduces the correction burden.

This is not model training. No weights are updated. The improvement mechanism is purely through better in-context examples in the prompt.

## Confidence calibration

Claude's confidence scores (0-100) are not inherently calibrated. A reported confidence of 80 does not necessarily mean 80% probability of correctness.

The system tracks empirical calibration in `backend/app/ml/metrics_tracker.py`:

- Predictions are bucketed into confidence bands: 0-49, 50-69, 70-84, 85-100.
- For each band, the system tracks how many predictions were confirmed as correct vs. rejected as false positives.
- The resulting calibration curve (e.g., "85-100 band: 92.5% correct") tells operators how trustworthy a given confidence level actually is.

This data is available via the metrics API and is also fed back into the prompt as accuracy context, allowing Claude to adjust its confidence reporting based on empirical results.

## Cost controls and rate limiting

**Per-request cost tracking**: Every Claude API call records input tokens, output tokens, and estimated cost in USD. This data is logged and available for monitoring.

**Confidence threshold**: Findings below `MIN_CONFIDENCE_THRESHOLD` (default 70) are discarded, reducing noise without additional API calls.

**Image quality gate**: Blurry, dark, or underexposed photos are filtered out before the API call, avoiding spend on images that would produce unreliable results.

**Retry budget**: The Claude client retries at most 3 times on transient errors. Non-transient errors fail immediately.

**Request timeout**: The Claude client enforces a 120-second timeout per request.

**API rate limiting**: The backend exposes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers. The default limit is 60 requests per minute per user.

## Image quality validation gate

The validation gate in `backend/app/services/image_validator.py` exists to prevent wasting API spend and producing unreliable results from poor-quality photos. It uses Pillow (no OpenCV dependency) and checks:

| Check | Method | Threshold | Rationale |
|---|---|---|---|
| Resolution | `Image.size` | Min 640x480 | Below this, damage details are not visible |
| Blur | Laplacian variance via `ImageFilter.Kernel` | Min variance 50.0 | Blurry images produce unreliable detection |
| Brightness | Mean grayscale luminance | 30-235 (0-255 scale) | Too dark or overexposed images hide damage |
| Content type | String check | jpeg, png, webp | HEIC is accepted for upload but not for validation |
| File size | Byte count | Configurable (default 10 MB) | Memory and bandwidth constraints |

The composite quality score is: `blur_quality * 0.4 + brightness_quality * 0.3 + resolution_quality * 0.3`.

## Future roadmap

### When to add embeddings

Consider adding CLIP or similar embeddings when:

- A tenant's feedback corpus exceeds ~5,000 corrections and metadata filtering returns too many loosely relevant examples.
- The correction dataset spans many fine-grained damage subtypes that do not map cleanly to the discrete `damage_type` column.
- A/B testing shows that semantically similar examples (by visual or textual similarity) produce measurably better detection accuracy than metadata-filtered examples.

Implementation would involve: installing pgvector, generating embeddings for feedback records (using a separate embedding model), storing vectors in a new column, and adding a similarity search path in `few_shot_engine.py` alongside the existing metadata filter.

### When vector search makes sense

Vector search is justified when the retrieval problem shifts from "find corrections for the same asset type and damage type" to "find corrections for visually or semantically similar situations." This happens when:

- The taxonomy of damage types grows beyond the current set (scratch, dent, crack, tear, discoloration, gouge, chip) and operators use free-text descriptions.
- Cross-asset-type knowledge transfer becomes valuable (e.g., a fiberglass crack on a boat hull is similar to a fiberglass crack on a jet ski hull, even though `asset_type` differs).
- The photo itself (not just metadata) should influence example retrieval.

### Other planned improvements

- **Webhook notifications**: Notify external systems when detection completes or when findings are created.
- **Batch detection**: Process multiple inspections in a single background job.
- **Photo-level finding association**: Currently, findings are associated with the first after-photo. Future work should use bounding box data to associate findings with specific photos.
- **IndexedDB photo storage**: Cache photos locally on the device for true offline inspection workflows.
- **Confidence recalibration**: Periodically adjust the confidence threshold based on observed calibration curves.
