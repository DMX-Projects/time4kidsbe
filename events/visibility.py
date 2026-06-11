"""Which centre events a parent login should see (class-aware)."""

from django.db.models import Q


def public_event_q() -> Q:
    """Centre-wide events for public marketing pages."""
    return Q(class_name="")


def event_visible_q(parent_profile) -> Q:
    """All-classes events plus class rows matching the parent's children."""
    from students.portal_views import _matching_target_class_names

    vis = public_event_q()
    matching_classes = _matching_target_class_names(parent_profile)
    if matching_classes:
        vis |= Q(class_name__in=matching_classes)
    return vis


def parent_events_queryset(parent_profile, *, centre=None):
    """
    All event-gallery rows for a parent's centre in one list.

    Each event includes ``class_name`` / ``audience_label`` so the parent app
    filters or groups by class on the client (no per-class API).
    """
    from events.models import Event

    if centre is None:
        from accounts.profile_access import effective_franchise_for_parent

        centre = effective_franchise_for_parent(parent_profile)
    if not parent_profile or not centre:
        return Event.objects.none()
    return (
        Event.objects.filter(franchise=centre)
        .prefetch_related("media")
        .order_by("-start_date", "-created_at")
    )
