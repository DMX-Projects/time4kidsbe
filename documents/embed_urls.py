"""Normalize iframe / embed URLs pasted into parent document forms."""

from __future__ import annotations

import re

IFRAME_SRC_RE = re.compile(r"""<iframe[^>]+src=["']([^"']+)["']""", re.IGNORECASE)


def parse_embed_input(raw: str | None) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    match = IFRAME_SRC_RE.search(text)
    if match and match.group(1):
        return match.group(1).strip()
    src_match = re.search(r"""src=["']([^"']+)["']""", text, re.IGNORECASE)
    if src_match and src_match.group(1) and "iframe" in text.lower():
        return src_match.group(1).strip()
    return text


def normalize_parent_embed_url(raw: str | None) -> str:
    return parse_embed_input(raw)


def is_usable_embed_url(raw: str | None) -> bool:
    url = normalize_parent_embed_url(raw)
    if not url:
        return False
    lower = url.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return True
    return lower.startswith("//")


AUDIO_URL_RE = re.compile(
    r"\.(mp3|wav|m4a|ogg|aac|flac|wma|amr|opus|caf|aiff|aif|mpeg|mpg|3gp|weba)(\?|#|$)",
    re.IGNORECASE,
)


def is_audio_media_url(raw: str | None) -> bool:
    url = normalize_parent_embed_url(raw).lower()
    if not url:
        return False
    if AUDIO_URL_RE.search(url):
        return True
    return "/audio/" in url or "content-type=audio" in url
