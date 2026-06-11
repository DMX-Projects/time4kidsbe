"""When parent-portal homework and announcements become visible (IST calendar day)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

PORTAL_TZ = ZoneInfo("Asia/Kolkata")


def portal_local_now() -> datetime:
    return timezone.now().astimezone(PORTAL_TZ)


def portal_today() -> date:
    return portal_local_now().date()


def parent_visible_homework_q() -> Q:
    """Homework is visible on its assigned date (IST) and after."""
    return Q(assigned_date__lte=portal_today())


def parent_visible_announcement_q() -> Q:
    """Announcements are visible once ``published_at`` has passed."""
    return Q(published_at__lte=timezone.now())


def published_at_from_schedule_date(schedule_date: date | str | None) -> datetime:
    """
    Map a franchise-selected calendar day to ``published_at``.
    - Today (IST) → now (immediate in-app + email).
    - Future/past day → start of that day IST (visible from midnight that day).
    """
    if schedule_date is None:
        return timezone.now()

    if isinstance(schedule_date, str):
        parsed = parse_date(schedule_date.strip())
        if parsed is None:
            return timezone.now()
        schedule_date = parsed

    if schedule_date == portal_today():
        return timezone.now()

    start_local = datetime.combine(schedule_date, time.min, tzinfo=PORTAL_TZ)
    return start_local


def announcement_on_schedule_date_q(schedule_date: date) -> Q:
    """Match announcements scheduled for a calendar day in IST (not UTC date)."""
    start_local = datetime.combine(schedule_date, time.min, tzinfo=PORTAL_TZ)
    end_local = datetime.combine(schedule_date + timedelta(days=1), time.min, tzinfo=PORTAL_TZ)
    return Q(published_at__gte=start_local, published_at__lt=end_local)
