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


def parent_event_class_filter_options() -> list[dict[str, str]]:
    """Dropdown options for parent gallery (web + mobile)."""
    from students.portal_views import HOMEWORK_CLASS_LABELS

    options: list[dict[str, str]] = [{"value": "", "label": "All classes"}]
    for label in HOMEWORK_CLASS_LABELS:
        options.append({"value": label, "label": label})
    return options


def parent_events_queryset(parent_profile, *, centre=None, student=None, class_name=None):
    """
    Event-gallery rows for a parent's centre.

    - No ``class_name`` / ``student``: all centre uploads (parent gallery browse).
    - ``?class_name=``: that class plus centre-wide rows.
    - ``student=`` (calendar / notifications): one child's class plus centre-wide.
    """
    from events.models import Event

    if centre is None:
        from accounts.profile_access import effective_franchise_for_parent

        centre = effective_franchise_for_parent(parent_profile)
    if not parent_profile or not centre:
        return Event.objects.none()
    qs = (
        Event.objects.filter(franchise=centre)
        .prefetch_related("media")
        .order_by("-start_date", "-created_at")
    )
    if class_name is not None:
        return filter_events_for_class_name(qs, class_name)
    if student is not None:
        return filter_events_for_student(qs, student)
    return qs


def event_row_visible_for_student(event, student) -> bool:
    """Centre-wide events plus class rows matching one linked child."""
    if student is None:
        return True
    target_class = (getattr(event, "class_name", None) or "").strip()
    if not target_class:
        return True
    from students.portal_views import _class_label_matches

    return _class_label_matches(student.class_name, target_class)


def _event_target_class_names_for_student(student) -> set[str]:
    """Stored ``class_name`` values that may match one child's class (DB pre-filter)."""
    from students.portal_views import (
        HOMEWORK_CLASS_LABELS,
        _canonical_class_label,
        _class_label_matches,
        _strip_legacy_class_year,
    )

    cn = (getattr(student, "class_name", None) or "").strip()
    if not cn:
        return set()

    names: set[str] = {cn}
    stripped = _strip_legacy_class_year(cn)
    if stripped:
        names.add(stripped)
    canon = _canonical_class_label(cn)
    if canon:
        names.add(canon)
    for label in HOMEWORK_CLASS_LABELS:
        if _class_label_matches(cn, label):
            names.add(label)
    return {n for n in names if n}


def filter_events_for_class_name(queryset, class_name: str):
    """Centre-wide rows plus events tagged to ``class_name`` (fuzzy class match)."""
    target = (class_name or "").strip()
    if not target or target.lower() in ("all", "all classes"):
        return queryset

    from students.portal_views import _class_label_matches, normalize_portal_class_name

    normalized = normalize_portal_class_name(target) or target
    ids = []
    for row in queryset:
        row_class = (getattr(row, "class_name", None) or "").strip()
        if not row_class:
            ids.append(row.pk)
        elif _class_label_matches(row_class, normalized) or _class_label_matches(row_class, target):
            ids.append(row.pk)
    if not ids:
        return queryset.none()
    return queryset.filter(pk__in=ids)


def filter_events_for_student(queryset, student):
    """Centre-wide rows plus class-specific rows for one linked child."""
    if student is None:
        return queryset.filter(class_name="")

    names = _event_target_class_names_for_student(student)
    if names:
        pre = queryset.filter(Q(class_name="") | Q(class_name__in=names))
    else:
        pre = queryset.filter(class_name="")

    ids = [row.pk for row in pre if event_row_visible_for_student(row, student)]
    if not ids:
        return queryset.none()
    return queryset.filter(pk__in=ids)
