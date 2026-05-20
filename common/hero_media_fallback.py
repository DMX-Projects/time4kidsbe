"""
Map missing hero_slides CMS files to static marketing-site paths (files in Next `public/`).
Used when DB paths exist but uploads are not on MEDIA_ROOT (live 404 under /cms-media/).
"""
from __future__ import annotations

import os
import re

from django.conf import settings

PUBLIC_STATIC_BY_BASENAME: dict[str, str] = {
    "faq-banner-new-1.png": "/faq-banner-new-1.png",
    "faq-banner-new-2.png": "/faq-banner-new-2.png",
    "faq-sidebar-teacher.png": "/faq-sidebar-teacher.png",
    "faq-girl-image.jpg": "/faq-girl-image.jpg",
    "17.png": "/17.png",
}

PUBLIC_STATIC_BY_STEM: dict[str, str] = {
    "faq-banner-new-1": "/faq-banner-new-1.png",
    "faq-banner-new-2": "/faq-banner-new-2.png",
    "faq-sidebar-teacher": "/faq-sidebar-teacher.png",
    "faq-girl-image": "/faq-girl-image.jpg",
    "17": "/17.png",
}

_DJANGO_SUFFIX = re.compile(r"^[a-zA-Z0-9]{6,12}$")


def public_static_fallback_for_basename(basename: str) -> str | None:
    base = (basename or "").strip()
    if not base:
        return None
    exact = PUBLIC_STATIC_BY_BASENAME.get(base)
    if exact:
        return exact

    dot = base.rfind(".")
    if dot <= 0:
        return None
    stem = base[:dot]
    ext = base[dot + 1 :].lower()

    if stem in PUBLIC_STATIC_BY_STEM:
        path = PUBLIC_STATIC_BY_STEM[stem]
        if path.endswith(f".{ext}"):
            return path

    underscore = stem.rfind("_")
    if underscore > 0:
        prefix = stem[:underscore]
        suffix = stem[underscore + 1 :]
        if _DJANGO_SUFFIX.match(suffix) and prefix in PUBLIC_STATIC_BY_STEM:
            path = PUBLIC_STATIC_BY_STEM[prefix]
            if path.endswith(f".{ext}"):
                return path

    return None


def resolve_hero_slide_image_url(image_field) -> str | None:
    """Return /media/… when file exists on disk; else a /public static path if known."""
    if not image_field:
        return None

    try:
        disk_path = image_field.path
    except (AttributeError, ValueError):
        disk_path = os.path.join(settings.MEDIA_ROOT, image_field.name)

    if os.path.isfile(disk_path):
        try:
            url = image_field.url
        except (AttributeError, ValueError):
            url = ""
        if url.startswith(("http://", "https://")):
            from urllib.parse import urlparse

            return urlparse(url).path or url
        return url or f"/media/{image_field.name}"

    fallback = public_static_fallback_for_basename(os.path.basename(image_field.name))
    return fallback
