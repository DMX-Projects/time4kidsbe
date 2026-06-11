"""Parse YouTube/Bunny video links embedded in event ``description`` (web franchise UI)."""

from __future__ import annotations

import json
import re
from typing import Any

MARKER_RE = re.compile(r"<!--TK_EVENT_VIDEO_LINKS:([\s\S]*?)-->")
EVENT_VIDEO_LINK_ID_PREFIX = "evl-"


def parse_event_video_links(description: str | None) -> list[dict[str, str]]:
    raw = (description or "").strip()
    match = MARKER_RE.search(raw)
    if not match or not match.group(1):
        return []
    try:
        parsed = json.loads(match.group(1))
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []

    out: list[dict[str, str]] = []
    for row in parsed:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        raw_id = str(row.get("id") or "").strip() or f"{EVENT_VIDEO_LINK_ID_PREFIX}0"
        if not raw_id.startswith(EVENT_VIDEO_LINK_ID_PREFIX):
            raw_id = f"{EVENT_VIDEO_LINK_ID_PREFIX}{raw_id}"
        item: dict[str, str] = {"id": raw_id, "url": url}
        title = str(row.get("title") or "").strip()
        if title:
            item["title"] = title
        body = str(row.get("description") or "").strip()
        if body:
            item["description"] = body
        out.append(item)
    return out


def strip_event_video_links(description: str | None) -> str:
    return MARKER_RE.sub("", description or "").strip()


def event_video_link_gallery_id(link_id: str) -> int:
    """Stable negative id (distinct from positive EventMedia pk values)."""
    h = 0
    for ch in link_id:
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
        if h >= 0x80000000:
            h -= 0x100000000
    n = abs(h) or 1
    return -n


def video_link_media_rows(description: str | None) -> list[dict[str, Any]]:
    """Shape link videos like ``EventMediaSerializer`` rows for parent/mobile clients."""
    rows: list[dict[str, Any]] = []
    for link in parse_event_video_links(description):
        link_id = link["id"]
        rows.append(
            {
                "id": event_video_link_gallery_id(link_id),
                "file": link["url"],
                "media_type": "URL",
                "caption": link.get("description") or link.get("title") or "Video",
                "uploaded_by": None,
                "uploaded_at": None,
                "is_external_url": True,
            }
        )
    return rows
