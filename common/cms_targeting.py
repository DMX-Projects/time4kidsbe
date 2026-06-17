"""Resolve franchise centres for head-office CMS publish targeting."""

from __future__ import annotations

import re
from typing import Iterable

from franchises.models import Franchise

from documents.state_utils import franchise_state_code


class PublishScope:
    PAN_INDIA = "pan_india"
    STATE = "state"
    CITY = "city"
    FRANCHISES = "franchises"
    ONE_CENTRE = "one_centre"

    CHOICES = (
        (PAN_INDIA, "Pan-India (all centres)"),
        (STATE, "State-wise centres"),
        (CITY, "City-wise centres"),
        (FRANCHISES, "Multiple selected centres"),
        (ONE_CENTRE, "One centre"),
    )


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def franchise_city_key(franchise: Franchise) -> str:
    raw = (getattr(franchise, "cityname", None) or getattr(franchise, "city", None) or "").strip()
    return _normalize_key(raw)


def franchise_matches_states(franchise: Franchise, state_codes: Iterable[str]) -> bool:
    codes = {str(c).strip().upper() for c in state_codes if str(c).strip()}
    if not codes:
        return False
    code = franchise_state_code(franchise)
    return bool(code and code in codes)


def franchise_matches_cities(franchise: Franchise, cities: Iterable[str]) -> bool:
    keys = {_normalize_key(c) for c in cities if _normalize_key(c)}
    if not keys:
        return False
    return franchise_city_key(franchise) in keys


def admin_franchise_queryset(admin_user):
    return Franchise.objects.filter(admin=admin_user, is_active=True).order_by("name")


def resolve_franchises_for_publish(
    admin_user,
    *,
    scope: str,
    franchise_id: int | None = None,
    franchise_ids: Iterable[int] | None = None,
    target_states: Iterable[str] | None = None,
    target_cities: Iterable[str] | None = None,
):
    """
    Return Franchise rows under this admin that match the publish scope.
    """
    base = list(admin_franchise_queryset(admin_user))
    if not base:
        return []

    scope = (scope or PublishScope.PAN_INDIA).strip().lower()

    if scope == PublishScope.PAN_INDIA:
        return base

    if scope == PublishScope.ONE_CENTRE:
        if not franchise_id:
            return []
        return [f for f in base if f.id == int(franchise_id)]

    if scope == PublishScope.FRANCHISES:
        ids = {int(i) for i in (franchise_ids or []) if str(i).strip().isdigit()}
        if not ids:
            return []
        return [f for f in base if f.id in ids]

    if scope == PublishScope.STATE:
        return [f for f in base if franchise_matches_states(f, target_states or [])]

    if scope == PublishScope.CITY:
        return [f for f in base if franchise_matches_cities(f, target_cities or [])]

    return base


def publish_scope_label(
    scope: str,
    *,
    franchise_name: str = "",
    franchise_count: int = 0,
    target_states: Iterable[str] | None = None,
    target_cities: Iterable[str] | None = None,
    class_name: str = "",
) -> str:
    scope = (scope or PublishScope.PAN_INDIA).strip().lower()
    class_suffix = f" · {class_name}" if (class_name or "").strip() else ""

    if scope == PublishScope.ONE_CENTRE:
        return f"{franchise_name or 'One centre'}{class_suffix}"
    if scope == PublishScope.FRANCHISES:
        n = franchise_count or len(list(target_states or []))
        return f"{n or 'Selected'} centres{class_suffix}"
    if scope == PublishScope.STATE:
        states = ", ".join(s for s in (target_states or []) if str(s).strip())
        return f"State: {states or '—'}{class_suffix}"
    if scope == PublishScope.CITY:
        cities = ", ".join(c for c in (target_cities or []) if str(c).strip())
        return f"City: {cities or '—'}{class_suffix}"
    return f"Pan-India (all centres){class_suffix}"


def parent_document_visible_to_franchise(doc, franchise) -> bool:
    """Whether a global (franchise-null) parent document is visible at a centre."""
    if doc.franchise_id:
        return doc.franchise_id == franchise.id

    scope = (getattr(doc, "publish_scope", None) or PublishScope.PAN_INDIA).strip().lower()
    if scope == PublishScope.PAN_INDIA:
        return True
    if scope == PublishScope.ONE_CENTRE:
        ids = getattr(doc, "target_franchise_ids", None) or []
        return franchise.id in {int(i) for i in ids if str(i).strip().isdigit()}
    if scope == PublishScope.FRANCHISES:
        ids = getattr(doc, "target_franchise_ids", None) or []
        return franchise.id in {int(i) for i in ids if str(i).strip().isdigit()}
    if scope == PublishScope.STATE:
        return franchise_matches_states(franchise, getattr(doc, "target_states", None) or [])
    if scope == PublishScope.CITY:
        return franchise_matches_cities(franchise, getattr(doc, "target_cities", None) or [])
    return True


def announcement_visible_to_franchise(announcement, franchise) -> bool:
    """Whether an announcement is targeted at a franchise centre."""
    if not getattr(announcement, "is_active", True):
        return False
    if announcement.franchise_id:
        return announcement.franchise_id == franchise.id

    scope = (getattr(announcement, "publish_scope", None) or PublishScope.PAN_INDIA).strip().lower()
    if scope == PublishScope.PAN_INDIA:
        return True
    if scope in (PublishScope.ONE_CENTRE, PublishScope.FRANCHISES):
        ids = getattr(announcement, "target_franchise_ids", None) or []
        return franchise.id in {int(i) for i in ids if str(i).strip().isdigit()}
    if scope == PublishScope.STATE:
        return franchise_matches_states(franchise, getattr(announcement, "target_states", None) or [])
    if scope == PublishScope.CITY:
        return franchise_matches_cities(franchise, getattr(announcement, "target_cities", None) or [])
    return True


def franchises_matching_announcement(announcement, admin_user=None):
    """Franchise rows that should receive a global (franchise-null) announcement."""
    if announcement.franchise_id:
        return [announcement.franchise]

    scope = (getattr(announcement, "publish_scope", None) or PublishScope.PAN_INDIA).strip().lower()
    franchise_ids = getattr(announcement, "target_franchise_ids", None) or []
    one_centre_id = franchise_ids[0] if scope == PublishScope.ONE_CENTRE and franchise_ids else None

    if admin_user is not None:
        return resolve_franchises_for_publish(
            admin_user,
            scope=scope,
            franchise_id=one_centre_id,
            franchise_ids=franchise_ids,
            target_states=getattr(announcement, "target_states", None) or [],
            target_cities=getattr(announcement, "target_cities", None) or [],
        )

    from franchises.models import Franchise

    base = list(Franchise.objects.filter(is_active=True).order_by("name"))
    if not base:
        return []
    if scope == PublishScope.PAN_INDIA:
        return base
    if scope == PublishScope.ONE_CENTRE:
        if not one_centre_id:
            return []
        return [f for f in base if f.id == int(one_centre_id)]
    if scope == PublishScope.FRANCHISES:
        ids = {int(i) for i in franchise_ids if str(i).strip().isdigit()}
        return [f for f in base if f.id in ids]
    if scope == PublishScope.STATE:
        return [f for f in base if franchise_matches_states(f, getattr(announcement, "target_states", None) or [])]
    if scope == PublishScope.CITY:
        return [f for f in base if franchise_matches_cities(f, getattr(announcement, "target_cities", None) or [])]
    return base
