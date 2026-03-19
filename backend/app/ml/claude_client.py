"""Thin wrapper around the Anthropic Python SDK for vision requests.

Responsibilities:
  - Build the ``messages`` payload with text + image content blocks.
  - Parse the structured JSON response returned by Claude.
  - Track token usage and estimated cost per call.
  - Retry with exponential back-off on transient errors (max 3 attempts).
  - Enforce a per-request timeout.

This module intentionally does NOT interpret or validate the semantic
content of the response -- that is the job of ``damage_detection.py``.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cost constants (USD per token as of Claude 3.5 Sonnet pricing)
# Updated when pricing changes.  These are approximate for spend tracking,
# not for billing.
# ---------------------------------------------------------------------------
_INPUT_COST_PER_TOKEN = 3.0 / 1_000_000   # $3 per 1M input tokens
_OUTPUT_COST_PER_TOKEN = 15.0 / 1_000_000  # $15 per 1M output tokens

# ---------------------------------------------------------------------------
# Retry / timeout defaults
# ---------------------------------------------------------------------------
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
REQUEST_TIMEOUT = 120.0  # seconds


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ClaudeVisionResult:
    """Container for a Claude API response and its associated metadata."""

    parsed_json: dict[str, Any] | None = None
    raw_text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model: str = ""
    duration_seconds: float = 0.0
    error: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_image_block(image_bytes: bytes, media_type: str = "image/jpeg") -> dict[str, Any]:
    """Encode raw image bytes into an Anthropic image content block."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": b64,
        },
    }


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return round(
        input_tokens * _INPUT_COST_PER_TOKEN + output_tokens * _OUTPUT_COST_PER_TOKEN,
        6,
    )


def _parse_json_response(text: str) -> dict[str, Any] | None:
    """Attempt to extract a JSON object from *text*.

    Claude is instructed to return raw JSON, but it occasionally wraps
    the payload in markdown code fences.  This helper strips those.
    """
    cleaned = text.strip()
    # Strip optional markdown fences.
    if cleaned.startswith("```"):
        # Remove opening fence (with optional language tag) and closing fence.
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON from Claude response", extra={"raw": text[:500]})
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_vision_request(
    *,
    system_prompt: str,
    user_text: str,
    before_images: list[tuple[bytes, str]] | None = None,
    after_images: list[tuple[bytes, str]] | None = None,
    model: str | None = None,
    max_tokens: int = 4096,
) -> ClaudeVisionResult:
    """Send a multi-image vision request to Claude and return parsed results.

    Parameters
    ----------
    system_prompt:
        The system-level instruction (rendered by ``prompt_builder``).
    user_text:
        The user-level message text (rendered by ``prompt_builder``).
    before_images:
        List of ``(raw_bytes, media_type)`` tuples for *before* photos.
    after_images:
        List of ``(raw_bytes, media_type)`` tuples for *after* photos.
    model:
        Anthropic model identifier.  Falls back to config default.
    max_tokens:
        Maximum tokens in the response.

    Returns
    -------
    ClaudeVisionResult
        Always populated -- on failure the ``error`` field is set.
    """
    settings = get_settings()
    model = model or settings.ANTHROPIC_MODEL

    # -- assemble user content blocks --------------------------------------
    content_blocks: list[dict[str, Any]] = []

    if before_images:
        content_blocks.append({"type": "text", "text": "BEFORE photos:"})
        for img_bytes, media_type in before_images:
            content_blocks.append(_build_image_block(img_bytes, media_type))

    if after_images:
        content_blocks.append({"type": "text", "text": "AFTER photos:"})
        for img_bytes, media_type in after_images:
            content_blocks.append(_build_image_block(img_bytes, media_type))

    content_blocks.append({"type": "text", "text": user_text})

    messages = [{"role": "user", "content": content_blocks}]

    # -- call with retry ---------------------------------------------------
    client = anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=REQUEST_TIMEOUT,
    )

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        t0 = time.monotonic()
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )
            duration = time.monotonic() - t0

            raw_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    raw_text += block.text

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = _estimate_cost(input_tokens, output_tokens)

            parsed = _parse_json_response(raw_text)

            logger.info(
                "Claude vision request completed",
                extra={
                    "model": model,
                    "attempt": attempt,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost,
                    "duration_s": round(duration, 2),
                },
            )

            return ClaudeVisionResult(
                parsed_json=parsed,
                raw_text=raw_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost,
                model=model,
                duration_seconds=round(duration, 2),
            )

        except (
            anthropic.RateLimitError,
            anthropic.InternalServerError,
            anthropic.APIConnectionError,
        ) as exc:
            last_error = exc
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "Claude API transient error, retrying",
                extra={"attempt": attempt, "delay": delay, "error": str(exc)},
            )
            if attempt < MAX_RETRIES:
                time.sleep(delay)

        except anthropic.APIError as exc:
            # Non-transient API error (bad request, auth, etc.) -- do not retry.
            duration = time.monotonic() - t0
            logger.error("Claude API non-retryable error", extra={"error": str(exc)})
            return ClaudeVisionResult(
                error=str(exc),
                model=model,
                duration_seconds=round(duration, 2),
            )

    # All retries exhausted.
    logger.error(
        "Claude API request failed after all retries",
        extra={"retries": MAX_RETRIES, "last_error": str(last_error)},
    )
    return ClaudeVisionResult(
        error=f"All {MAX_RETRIES} retries exhausted: {last_error}",
        model=model,
    )
