"""Compress Event Gallery images so stored files stay at or under 1 MB."""

from __future__ import annotations

import io
from typing import BinaryIO

from django.core.files.uploadedfile import InMemoryUploadedFile, UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

# Stored gallery photos target (parent app / centre page).
TARGET_EVENT_GALLERY_IMAGE_BYTES = 1 * 1024 * 1024
# Raw upload ceiling before compression (iPhone / Android camera photos).
MAX_EVENT_GALLERY_UPLOAD_BYTES = 10 * 1024 * 1024

_TRY_REGISTER_HEIF = False


def _ensure_heif_support() -> None:
    """Register HEIC/HEIF openers when pillow-heif is installed (optional)."""
    global _TRY_REGISTER_HEIF
    if _TRY_REGISTER_HEIF:
        return
    _TRY_REGISTER_HEIF = True
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except Exception:
        pass


def _stem(name: str | None) -> str:
    raw = (name or "photo").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." in raw:
        raw = raw.rsplit(".", 1)[0]
    return (raw or "photo")[:180]


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGB", "L"):
        return img.convert("RGB") if img.mode == "L" else img
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return img.convert("RGB")


def _encode_jpeg(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def compress_event_gallery_image(
    uploaded: UploadedFile | BinaryIO,
    *,
    target_bytes: int = TARGET_EVENT_GALLERY_IMAGE_BYTES,
    original_name: str | None = None,
) -> InMemoryUploadedFile:
    """
    Return a JPEG InMemoryUploadedFile at or under ``target_bytes``.

    Raises ``ValueError`` with a user-facing message when the file is not a
    readable image or cannot be reduced enough.
    """
    _ensure_heif_support()

    name = original_name or getattr(uploaded, "name", None) or "photo.jpg"
    try:
        uploaded.seek(0)
    except Exception:
        pass

    try:
        img = Image.open(uploaded)
        img.load()
    except UnidentifiedImageError as exc:
        raise ValueError(
            "Could not read this image. Use JPG, PNG, WEBP, or GIF "
            "(HEIC works if converted by the phone browser)."
        ) from exc
    except OSError as exc:
        raise ValueError("Could not open this image file.") from exc

    img = ImageOps.exif_transpose(img)
    img = _to_rgb(img)

    # Progressive: lower quality, then shrink dimensions if still too big.
    max_side = max(img.size)
    side_steps = [max_side, 2560, 2048, 1600, 1280, 1024, 800, 640]
    qualities = [88, 80, 72, 65, 55, 45, 35, 28]

    best: bytes | None = None
    for side in side_steps:
        working = img
        if max(working.size) > side:
            working = working.copy()
            working.thumbnail((side, side), Image.Resampling.LANCZOS)
        for quality in qualities:
            data = _encode_jpeg(working, quality)
            if best is None or len(data) < len(best):
                best = data
            if len(data) <= target_bytes:
                out = io.BytesIO(data)
                filename = f"{_stem(name)}.jpg"
                return InMemoryUploadedFile(
                    out,
                    field_name="file",
                    name=filename,
                    content_type="image/jpeg",
                    size=len(data),
                    charset=None,
                )

    size_mb = (len(best) / (1024 * 1024)) if best else 0
    raise ValueError(
        f"Could not compress this image under 1 MB (ended at {size_mb:.2f} MB). "
        "Try a different photo."
    )
