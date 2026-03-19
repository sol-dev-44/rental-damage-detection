"""Image quality gate -- validates photos *before* they are sent to Claude.

Running this check early avoids wasting API spend on blurry, over-exposed,
or undersized images that would produce unreliable damage detections.

All heavy lifting uses Pillow (PIL).  No OpenCV dependency.
"""

from __future__ import annotations

import io
import logging
import math
from dataclasses import dataclass, field

from PIL import Image, ImageFilter, ImageStat

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MIN_WIDTH = 640
MIN_HEIGHT = 480
ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})

# Laplacian-variance threshold below which an image is considered blurry.
# Empirically tuned -- lower values are more lenient.
BLUR_THRESHOLD = 50.0

# Brightness boundaries (0-255 mean luminance).  Images outside this range
# are flagged as too dark or overexposed.
MIN_BRIGHTNESS = 30.0
MAX_BRIGHTNESS = 235.0


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class ImageValidationResult:
    """Outcome of the image quality check."""

    is_valid: bool
    quality_score: float  # 0.0 to 1.0
    reasons: list[str] = field(default_factory=list)
    width: int = 0
    height: int = 0
    blur_score: float = 0.0
    brightness: float = 0.0


# ---------------------------------------------------------------------------
# Internal checks
# ---------------------------------------------------------------------------

def _check_content_type(content_type: str) -> str | None:
    """Return an error string if *content_type* is not acceptable."""
    if content_type not in ALLOWED_CONTENT_TYPES:
        return (
            f"Unsupported content type '{content_type}'. "
            f"Accepted: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
        )
    return None


def _check_file_size(file_bytes: bytes) -> str | None:
    """Return an error string if the file exceeds the configured maximum."""
    settings = get_settings()
    if len(file_bytes) > settings.max_photo_size_bytes:
        size_mb = len(file_bytes) / (1024 * 1024)
        return (
            f"File size {size_mb:.1f} MB exceeds "
            f"maximum {settings.MAX_PHOTO_SIZE_MB} MB"
        )
    return None


def _check_resolution(img: Image.Image) -> str | None:
    """Return an error string if the image is below minimum resolution."""
    w, h = img.size
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        return (
            f"Resolution {w}x{h} is below the minimum "
            f"{MIN_WIDTH}x{MIN_HEIGHT}"
        )
    return None


def _compute_blur_score(img: Image.Image) -> float:
    """Compute a sharpness score using the variance of a Laplacian-like filter.

    Pillow does not ship a true Laplacian kernel, so we approximate it
    using ``ImageFilter.Kernel`` with a standard 3x3 Laplacian.  The
    variance of the filtered image correlates with perceived sharpness.
    Higher values mean sharper.
    """
    grey = img.convert("L")

    # 3x3 Laplacian kernel: sum of weights = 0, so scale=1, offset=128 to
    # keep values in the unsigned byte range.
    laplacian_kernel = ImageFilter.Kernel(
        size=(3, 3),
        kernel=[0, 1, 0, 1, -4, 1, 0, 1, 0],
        scale=1,
        offset=128,
    )
    filtered = grey.filter(laplacian_kernel)
    stat = ImageStat.Stat(filtered)
    # stat.var returns a list with one entry per channel (one for greyscale).
    variance: float = stat.var[0]
    return variance


def _compute_brightness(img: Image.Image) -> float:
    """Return the mean brightness (0-255) of the image in greyscale."""
    grey = img.convert("L")
    stat = ImageStat.Stat(grey)
    return stat.mean[0]


def _brightness_quality(brightness: float) -> float:
    """Map brightness to a 0-1 quality factor. Penalise extremes."""
    if brightness < MIN_BRIGHTNESS:
        return max(0.0, brightness / MIN_BRIGHTNESS)
    if brightness > MAX_BRIGHTNESS:
        return max(0.0, 1.0 - (brightness - MAX_BRIGHTNESS) / (255.0 - MAX_BRIGHTNESS))
    return 1.0


def _blur_quality(blur_score: float) -> float:
    """Map blur variance to a 0-1 quality factor."""
    if blur_score >= BLUR_THRESHOLD:
        return 1.0
    # Linear ramp from 0 at variance=0 to 1 at threshold.
    return blur_score / BLUR_THRESHOLD


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_image(file_bytes: bytes, content_type: str) -> ImageValidationResult:
    """Run all quality checks and return a consolidated result.

    Parameters
    ----------
    file_bytes:
        Raw image bytes (as received from an upload request).
    content_type:
        MIME type declared by the client.

    Returns
    -------
    ImageValidationResult
        Contains ``is_valid``, a composite ``quality_score`` (0-1), and
        human-readable ``reasons`` for any failures.
    """
    reasons: list[str] = []

    # -- fast / cheap checks first -----------------------------------------
    ct_err = _check_content_type(content_type)
    if ct_err:
        reasons.append(ct_err)

    size_err = _check_file_size(file_bytes)
    if size_err:
        reasons.append(size_err)

    # If we cannot even open the image, bail early.
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.load()  # Force full decode to catch truncated files.
    except Exception:
        reasons.append("Unable to decode image data")
        return ImageValidationResult(
            is_valid=False,
            quality_score=0.0,
            reasons=reasons,
        )

    width, height = img.size

    # -- resolution --------------------------------------------------------
    res_err = _check_resolution(img)
    if res_err:
        reasons.append(res_err)

    # -- blur detection ----------------------------------------------------
    blur_score = _compute_blur_score(img)
    if blur_score < BLUR_THRESHOLD:
        reasons.append(
            f"Image appears blurry (sharpness score {blur_score:.1f}, "
            f"minimum {BLUR_THRESHOLD:.1f})"
        )

    # -- brightness --------------------------------------------------------
    brightness = _compute_brightness(img)
    if brightness < MIN_BRIGHTNESS:
        reasons.append(
            f"Image is too dark (brightness {brightness:.1f}, "
            f"minimum {MIN_BRIGHTNESS:.1f})"
        )
    if brightness > MAX_BRIGHTNESS:
        reasons.append(
            f"Image is overexposed (brightness {brightness:.1f}, "
            f"maximum {MAX_BRIGHTNESS:.1f})"
        )

    # -- composite quality score (0-1) -------------------------------------
    blur_q = _blur_quality(blur_score)
    bright_q = _brightness_quality(brightness)
    # Resolution factor: 1.0 if meets minimum, scaled down otherwise.
    res_q = min(1.0, (width * height) / (MIN_WIDTH * MIN_HEIGHT))

    quality_score = round(blur_q * 0.4 + bright_q * 0.3 + res_q * 0.3, 3)

    is_valid = len(reasons) == 0

    if not is_valid:
        logger.info(
            "Image failed quality validation",
            extra={"reasons": reasons, "quality_score": quality_score},
        )

    return ImageValidationResult(
        is_valid=is_valid,
        quality_score=quality_score,
        reasons=reasons,
        width=width,
        height=height,
        blur_score=blur_score,
        brightness=brightness,
    )
