"""Human-readable download filenames for franchise hub files (not storage UUIDs)."""

from __future__ import annotations

import re
from pathlib import Path

from documents.models import FranchiseDocument

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    return cleaned or "document"


def safe_disposition_filename(raw: str | None, fallback: str) -> str:
    """Use client-provided ?name= when opening in a new tab (matches dashboard link text)."""
    candidate = (raw or "").strip()
    if not candidate or len(candidate) > 240:
        return fallback
    safe = _sanitize_filename(candidate)
    fallback_ext = Path(fallback).suffix.lower()
    if fallback_ext and not safe.lower().endswith(fallback_ext):
        safe = f"{safe}{fallback_ext}"
    return safe or fallback


def _humanize_segment(segment: str) -> str:
    return segment.replace("_", " ").replace("-", " ").strip()


def _looks_like_uuid(value: str) -> bool:
    stem = Path(value).stem
    return bool(_UUID_RE.match(stem))


def _should_append_parent_folder(parent_humanized: str) -> bool:
    p = parent_humanized.lower()
    if not p or len(p) > 36:
        return False
    if "uploads and support" in p or "social media uploads" in p:
        return False
    if "academic documents" in p or "welcome letters" in p:
        return False
    if re.match(r"^block[- ]?\d+", p, re.I):
        return True
    if re.search(r"^(nursery|pp\s?1|pp\s?2|pg|play group)\b", p, re.I):
        return True
    if "holiday" in p or "study material" in p or "refresher" in p:
        return True
    if "summer camp" in p or "summercamp" in p:
        return True
    return False


def franchise_document_download_filename(doc: FranchiseDocument) -> str:
    """
    Build a safe filename for Content-Disposition / browser downloads.
    Uses document title and original pc path — not Django storage UUID names.
    """
    source_path = (doc.source_path or "").replace("\\", "/").strip()
    stored_name = Path(doc.file.name).name if doc.file else ""

    ext = Path(source_path).suffix or Path(stored_name).suffix
    if not ext and stored_name:
        ext = Path(stored_name).suffix

    title = (doc.title or "").strip()

    if source_path:
        source_file = Path(source_path).name
        source_stem = Path(source_path).stem
        if not title or _looks_like_uuid(title) or _looks_like_uuid(source_stem):
            title = _humanize_segment(source_stem)
        elif _looks_like_uuid(Path(title).stem):
            title = _humanize_segment(source_stem)

        parts = [p for p in source_path.split("/") if p]
        if len(parts) >= 2:
            parent = _humanize_segment(parts[-2])
            skip_parents = {"pc", "uploads", "media", "franchise_documents"}
            if (
                parent.lower() not in skip_parents
                and parent.lower() not in title.lower()
                and _should_append_parent_folder(parent)
            ):
                title = f"{title} ({parent})"

    if not title:
        title = _humanize_segment(Path(stored_name).stem) if stored_name else "document"

    safe = _sanitize_filename(title)
    if ext and not safe.lower().endswith(ext.lower()):
        safe = f"{safe}{ext}"
    return safe
