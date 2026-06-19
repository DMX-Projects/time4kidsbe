"""Newsletter block / upload date helpers for CMS track-date and parent date filters."""

from __future__ import annotations

from django.db.models import Q


def _slice_date(value: str) -> str:
    return (value or "").strip()[:10]


def newsletter_on_date_q(day: str) -> Q:
    """
    Match newsletters visible on ``day`` (YYYY-MM-DD).

  - Block date range (period_start … period_end), including single-day rows
    when only period_start is set.
  - Upload date (created_at) when block dates are missing or differ from upload day.
    """
    if not day:
        return Q()

    period_range = Q(
        period_start__isnull=False,
        period_end__isnull=False,
        period_start__lte=day,
        period_end__gte=day,
    )
    period_start_only = Q(
        period_start=day,
        period_end__isnull=True,
    )
    period_end_only = Q(
        period_start__isnull=True,
        period_end=day,
    )
    upload_only = Q(
        period_start__isnull=True,
        period_end__isnull=True,
        created_at__date=day,
    )
    # Uploaded on ``day`` but block date stored on another day (common CMS mistake).
    upload_with_block = Q(
        period_start__isnull=False,
        created_at__date=day,
    ) & ~Q(period_start=day)

    return period_range | period_start_only | period_end_only | upload_only | upload_with_block


def newsletter_in_range_q(from_date: str, to_date: str) -> Q:
    """Match newsletters whose block range or upload date overlaps [from_date, to_date]."""
    if not from_date or not to_date:
        return Q()

    period_overlap = Q(
        period_start__isnull=False,
        period_end__isnull=False,
        period_start__lte=to_date,
        period_end__gte=from_date,
    )
    period_start_in_range = Q(
        period_start__isnull=False,
        period_end__isnull=True,
        period_start__gte=from_date,
        period_start__lte=to_date,
    )
    upload_in_range = Q(created_at__date__gte=from_date, created_at__date__lte=to_date)
    upload_only = Q(
        period_start__isnull=True,
        period_end__isnull=True,
        created_at__date__gte=from_date,
        created_at__date__lte=to_date,
    )
    return period_overlap | period_start_in_range | upload_in_range | upload_only


def filter_newsletters_by_date(qs, track_date: str = "", from_date: str = "", to_date: str = ""):
    track_date = _slice_date(track_date)
    from_date = _slice_date(from_date)
    to_date = _slice_date(to_date)

    if track_date:
        return qs.filter(newsletter_on_date_q(track_date))
    if from_date and to_date:
        return qs.filter(newsletter_in_range_q(from_date, to_date))
    return qs


def normalize_newsletter_period_attrs(attrs: dict) -> dict:
    """Ensure period_end matches period_start for single-day newsletter blocks."""
    period_start = attrs.get("period_start")
    period_end = attrs.get("period_end")
    if period_start and not period_end:
        attrs["period_end"] = period_start
    elif period_end and not period_start:
        attrs["period_start"] = period_end
    return attrs
