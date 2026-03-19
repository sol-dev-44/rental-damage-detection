"""R2 (S3-compatible) storage service for photo upload, retrieval, and deletion.

Uses boto3 under the hood. Because boto3 is synchronous, all I/O is
delegated to ``asyncio.get_running_loop().run_in_executor`` so callers
can ``await`` every operation without blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config as BotoConfig

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

@lru_cache
def _get_s3_client() -> Any:
    """Return a thread-safe boto3 S3 client pointed at Cloudflare R2."""
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=BotoConfig(
            retries={"max_attempts": 3, "mode": "adaptive"},
            signature_version="s3v4",
        ),
        # R2 does not use a traditional AWS region, but boto3 requires one.
        region_name="auto",
    )


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def _build_r2_key(tenant_id: uuid.UUID, inspection_id: uuid.UUID, filename: str) -> str:
    """Construct a deterministic object key.

    Layout: ``<tenant_id>/<inspection_id>/<uuid4>-<sanitised_filename>``
    """
    safe_name = filename.replace(" ", "_").replace("/", "_")
    unique = uuid.uuid4().hex[:12]
    return f"{tenant_id}/{inspection_id}/{unique}-{safe_name}"


def get_public_url(r2_key: str) -> str:
    """Construct the public URL for an object key using application config."""
    settings = get_settings()
    return settings.get_r2_url(r2_key)


# ---------------------------------------------------------------------------
# Async wrappers around synchronous boto3 calls
# ---------------------------------------------------------------------------

async def upload_photo(
    file_bytes: bytes,
    content_type: str,
    tenant_id: uuid.UUID,
    inspection_id: uuid.UUID,
    original_filename: str,
) -> str:
    """Upload *file_bytes* to R2 and return the resulting object key.

    The key is what gets stored in the ``photos.r2_key`` column -- never
    a full URL.
    """
    settings = get_settings()
    r2_key = _build_r2_key(tenant_id, inspection_id, original_filename)
    client = _get_s3_client()
    loop = asyncio.get_running_loop()

    await loop.run_in_executor(
        None,
        lambda: client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=r2_key,
            Body=file_bytes,
            ContentType=content_type,
        ),
    )

    logger.info(
        "Photo uploaded to R2",
        extra={"r2_key": r2_key, "size": len(file_bytes), "tenant_id": str(tenant_id)},
    )
    return r2_key


async def generate_presigned_url(r2_key: str, expires_in: int = 3600) -> str:
    """Generate a time-limited presigned GET URL for *r2_key*.

    Parameters
    ----------
    r2_key:
        The object key stored in ``photos.r2_key``.
    expires_in:
        Lifetime of the URL in seconds (default 1 hour).
    """
    settings = get_settings()
    client = _get_s3_client()
    loop = asyncio.get_running_loop()

    url: str = await loop.run_in_executor(
        None,
        lambda: client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.R2_BUCKET_NAME, "Key": r2_key},
            ExpiresIn=expires_in,
        ),
    )
    return url


async def delete_photo(r2_key: str) -> None:
    """Delete the object identified by *r2_key* from R2."""
    settings = get_settings()
    client = _get_s3_client()
    loop = asyncio.get_running_loop()

    await loop.run_in_executor(
        None,
        lambda: client.delete_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=r2_key,
        ),
    )

    logger.info("Photo deleted from R2", extra={"r2_key": r2_key})


async def download_photo(r2_key: str) -> bytes:
    """Download and return the raw bytes for the object at *r2_key*.

    Used by the detection pipeline to fetch images before sending them
    to the Claude vision API.
    """
    settings = get_settings()
    client = _get_s3_client()
    loop = asyncio.get_running_loop()

    response = await loop.run_in_executor(
        None,
        lambda: client.get_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=r2_key,
        ),
    )

    body: bytes = await loop.run_in_executor(None, response["Body"].read)
    return body
