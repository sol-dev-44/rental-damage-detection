"""Tests for the image validation service.

Covers:
  - Blur detection (sharp vs. blurry images).
  - File size limits.
  - Resolution checks (above and below minimum).
  - Content type validation.
  - Brightness checks (dark, normal, overexposed).
  - Composite quality score calculation.
"""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from PIL import Image, ImageFilter

from app.services.image_validator import (
    ALLOWED_CONTENT_TYPES,
    BLUR_THRESHOLD,
    MAX_BRIGHTNESS,
    MIN_BRIGHTNESS,
    MIN_HEIGHT,
    MIN_WIDTH,
    ImageValidationResult,
    validate_image,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg(width: int = 800, height: int = 600, color: str = "white") -> bytes:
    """Create a simple JPEG image of the given dimensions and colour."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _make_png(width: int = 800, height: int = 600, color: str = "white") -> bytes:
    """Create a simple PNG image."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_blurry_jpeg(
    width: int = 800, height: int = 600, blur_radius: int = 20
) -> bytes:
    """Create a blurry JPEG by applying a heavy Gaussian blur."""
    img = Image.new("RGB", (width, height), color="white")
    # Draw some features so we have something to blur.
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    for i in range(0, width, 20):
        draw.line([(i, 0), (i, height)], fill="black", width=2)
    for j in range(0, height, 20):
        draw.line([(0, j), (width, j)], fill="black", width=2)
    # Apply heavy blur.
    img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _make_sharp_jpeg(width: int = 800, height: int = 600) -> bytes:
    """Create a sharp JPEG with high-contrast edges."""
    img = Image.new("RGB", (width, height), color="white")
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    # High-contrast grid produces high Laplacian variance.
    for i in range(0, width, 10):
        draw.line([(i, 0), (i, height)], fill="black", width=1)
    for j in range(0, height, 10):
        draw.line([(0, j), (width, j)], fill="black", width=1)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestContentType:
    """Content type validation."""

    def test_accepts_jpeg(self):
        result = validate_image(_make_jpeg(), "image/jpeg")
        assert "content type" not in " ".join(result.reasons).lower()

    def test_accepts_png(self):
        result = validate_image(_make_png(), "image/png")
        assert "content type" not in " ".join(result.reasons).lower()

    def test_accepts_webp(self):
        img = Image.new("RGB", (800, 600), "white")
        buf = io.BytesIO()
        img.save(buf, format="WEBP")
        result = validate_image(buf.getvalue(), "image/webp")
        assert "content type" not in " ".join(result.reasons).lower()

    def test_rejects_gif(self):
        result = validate_image(_make_jpeg(), "image/gif")
        assert not result.is_valid
        assert any("content type" in r.lower() for r in result.reasons)

    def test_rejects_bmp(self):
        result = validate_image(_make_jpeg(), "image/bmp")
        assert not result.is_valid


class TestFileSize:
    """File size limit checks."""

    def test_accepts_small_file(self):
        small = _make_jpeg(200, 200)
        # Force content type to pass; the image may fail resolution check.
        result = validate_image(small, "image/jpeg")
        assert not any("size" in r.lower() for r in result.reasons)

    def test_rejects_oversized_file(self):
        # Patch max_photo_size_bytes to a very small value.
        with patch("app.services.image_validator.get_settings") as mock_settings:
            settings = mock_settings.return_value
            settings.max_photo_size_bytes = 100  # 100 bytes -- way too small.
            settings.MAX_PHOTO_SIZE_MB = 0

            result = validate_image(_make_jpeg(), "image/jpeg")
            assert not result.is_valid
            assert any("size" in r.lower() for r in result.reasons)


class TestResolution:
    """Resolution checks."""

    def test_accepts_adequate_resolution(self):
        result = validate_image(_make_jpeg(800, 600), "image/jpeg")
        assert result.width == 800
        assert result.height == 600
        assert not any("resolution" in r.lower() for r in result.reasons)

    def test_accepts_minimum_resolution(self):
        result = validate_image(
            _make_jpeg(MIN_WIDTH, MIN_HEIGHT), "image/jpeg"
        )
        assert not any("resolution" in r.lower() for r in result.reasons)

    def test_rejects_below_minimum_width(self):
        result = validate_image(_make_jpeg(100, 600), "image/jpeg")
        assert not result.is_valid
        assert any("resolution" in r.lower() for r in result.reasons)

    def test_rejects_below_minimum_height(self):
        result = validate_image(_make_jpeg(800, 100), "image/jpeg")
        assert not result.is_valid
        assert any("resolution" in r.lower() for r in result.reasons)


class TestBlurDetection:
    """Blur detection via Laplacian variance."""

    def test_sharp_image_passes(self):
        sharp = _make_sharp_jpeg()
        result = validate_image(sharp, "image/jpeg")
        assert not any("blur" in r.lower() for r in result.reasons)
        assert result.blur_score >= BLUR_THRESHOLD

    def test_blurry_image_fails(self):
        blurry = _make_blurry_jpeg(blur_radius=30)
        result = validate_image(blurry, "image/jpeg")
        assert any("blur" in r.lower() for r in result.reasons)

    def test_blur_score_is_positive(self):
        result = validate_image(_make_jpeg(), "image/jpeg")
        assert result.blur_score >= 0


class TestBrightness:
    """Brightness checks."""

    def test_normal_brightness_passes(self):
        # Mid-grey image should pass brightness check.
        result = validate_image(_make_jpeg(color="#808080"), "image/jpeg")
        assert not any("dark" in r.lower() or "overexposed" in r.lower() for r in result.reasons)

    def test_very_dark_image_fails(self):
        dark = _make_jpeg(color="#050505")
        result = validate_image(dark, "image/jpeg")
        assert any("dark" in r.lower() for r in result.reasons)

    def test_overexposed_image_fails(self):
        bright = _make_jpeg(color="#FEFEFE")
        result = validate_image(bright, "image/jpeg")
        assert any("overexposed" in r.lower() for r in result.reasons)

    def test_brightness_value_stored(self):
        result = validate_image(_make_jpeg(color="#808080"), "image/jpeg")
        assert 100 < result.brightness < 150  # Mid-grey ~ 128


class TestQualityScore:
    """Composite quality score tests."""

    def test_good_image_high_score(self):
        sharp = _make_sharp_jpeg()
        result = validate_image(sharp, "image/jpeg")
        # A sharp, well-lit, properly-sized image should score high.
        assert result.quality_score > 0.5

    def test_bad_image_low_score(self):
        # Tiny, dark image.
        dark_tiny = _make_jpeg(100, 100, color="#050505")
        result = validate_image(dark_tiny, "image/jpeg")
        assert result.quality_score < 0.5

    def test_score_between_zero_and_one(self):
        result = validate_image(_make_jpeg(), "image/jpeg")
        assert 0.0 <= result.quality_score <= 1.0


class TestCorruptedImage:
    """Handling of invalid / corrupt image data."""

    def test_corrupt_bytes(self):
        result = validate_image(b"not an image at all", "image/jpeg")
        assert not result.is_valid
        assert any("decode" in r.lower() for r in result.reasons)
        assert result.quality_score == 0.0

    def test_empty_bytes(self):
        result = validate_image(b"", "image/jpeg")
        assert not result.is_valid
