"""Map franchise location text to ParentDocument state codes."""

from __future__ import annotations

import re

from documents.models import ParentDocument


def _normalize_state_text(value: str) -> str:
    """Lowercase letters/digits only — matches 'Tamilnadu' to 'Tamil Nadu'."""
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def franchise_state_code(franchise) -> str | None:
    """Resolve a ParentDocument.State code from a Franchise row."""
    if franchise is None:
        return None
    raw = (getattr(franchise, "state", None) or getattr(franchise, "statename", None) or "").strip()
    if not raw:
        return None
    if len(raw) == 2 and raw.upper() in dict(ParentDocument.State.choices):
        return raw.upper()
    normalized = _normalize_state_text(raw)
    if not normalized:
        return None
    for code, label in ParentDocument.State.choices:
        if _normalize_state_text(label) == normalized:
            return code
    return None


def effective_holiday_state(doc: ParentDocument) -> str | None:
    if doc.state:
        return doc.state
    if doc.franchise_id and doc.franchise:
        return franchise_state_code(doc.franchise)
    return None


DEFAULT_HOLIDAY_ACADEMIC_YEAR = "AY 2026-27"


def effective_holiday_academic_year(doc: ParentDocument) -> str:
    year = (doc.academic_year or "").strip()
    return year or DEFAULT_HOLIDAY_ACADEMIC_YEAR
