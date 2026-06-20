from accounts.permissions import IsDriverUser
from accounts.profile_access import driver_profile_for_user
from franchises.models import DriverProfile
from franchises.serializers import DriverProfileSerializer, DriverCreateSerializer
"""Parent portal: homework, announcements, attendance, fees, transport, support tickets."""

import re
import threading
import json
from datetime import date, timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.utils import OperationalError, ProgrammingError
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminUser, IsFranchiseUser, IsParentUser
from accounts.profile_access import (
    effective_franchise_for_parent,
    find_student_for_parent_user,
    franchise_profile_for_user,
    parents_at_franchise,
    resolved_parent_profile_for_user,
    students_at_franchise,
    user_owns_legacy_student,
)
from events.calendar_filters import exclude_showcase_placeholder_events
from events.models import Event
from events.serializers import EventSerializer
from events.video_links import strip_event_video_links
from events.visibility import parent_events_queryset

from .models import (
    Announcement,
    AnnouncementCampaign,
    AttendanceRecord,
    CentreAttendanceClosedDay,
    FeeRecord,
    FranchiseNotificationRead,
    Grade,
    HomeworkAssignment,
    ParentFeePayment,
    ParentNotificationRead,
    StudentAchievement,
    StudentProfile,
    StudentTransportAssignment,
    StudentTripStatus,
    SupportTicket,
    TransportRoute,
    TransportTrip,
    TransportTripLocation,
)
from .portal_schedule import (
    announcement_on_schedule_date_q,
    parent_visible_announcement_q,
    parent_visible_homework_q,
    portal_today,
    published_at_from_schedule_date,
)
from .serializers import (
    AdminAnnouncementCampaignSerializer,
    AnnouncementSerializer,
    AttendanceRecordSerializer,
    CentreAttendanceClosedDaySerializer,
    FranchiseAttendanceBulkSerializer,
    FranchiseAttendanceUpsertSerializer,
    FeeRecordSerializer,
    GradeSerializer,
    HomeworkAssignmentSerializer,
    ParentStudentAchievementSerializer,
    SupportTicketAdminSerializer,
    SupportTicketFranchiseSerializer,
    SupportTicketParentSerializer,
    StudentTransportAssignmentSerializer,
    ParentTransportRouteSerializer,
    serialize_parent_live_trip,
    serialize_parent_trip_location,
    serialize_parent_trip_student_status,
    TransportRouteSerializer,
    TransportTripLocationSerializer,
    TransportTripSerializer,
)


def _parent_transport_my_students(route, student_ids):
    assignments = route.student_assignments.filter(
        student_id__in=student_ids,
        is_active=True,
    ).select_related("student")
    return [
        {
            "student_id": a.student_id,
            "student_name": a.student.full_name,
            "class_name": a.student.class_name,
            "pickup_stop": a.pickup_stop or "",
            "drop_stop": a.drop_stop or "",
            "pickup_time": a.pickup_time.isoformat() if a.pickup_time else None,
            "drop_time": a.drop_time.isoformat() if a.drop_time else None,
        }
        for a in assignments
    ]


def _parent_transport_route_row(route, request, student_ids=None):
    row = ParentTransportRouteSerializer(route, context={"request": request}).data
    if student_ids is not None:
        row["my_students"] = _parent_transport_my_students(route, student_ids)
    return row


HOMEWORK_CLASS_LABELS = (
    "Play Group",
    "Nursery",
    "PP-1 / Junior KG / LKG",
    "PP-2 / Senior KG / UKG",
    "Summer Programs / Day Care",
)

_LEGACY_CLASS_YEAR_SUFFIX = re.compile(r"\s+\d{2}-\d{2}$")


def _strip_legacy_class_year(class_name: str) -> str:
    return _LEGACY_CLASS_YEAR_SUFFIX.sub("", (class_name or "").strip())


def _canonical_class_label(class_name: str) -> str | None:
    """Map legacy/import class strings (e.g. ``PP1 25-26``) to portal class labels."""
    raw = (class_name or "").strip()
    if not raw:
        return None
    if raw in HOMEWORK_CLASS_LABELS:
        return raw

    core = _strip_legacy_class_year(raw)
    norm = core.lower().replace("_", " ").replace("-", " ").strip()
    compact = re.sub(r"[^a-z0-9]", "", norm)

    if norm.startswith("play group") or compact.startswith("playgroup"):
        return "Play Group"
    if norm.startswith("nursery") or norm.startswith("refresher course nur"):
        return "Nursery"
    if re.search(r"pp\s*1", norm) or compact.startswith("pp1") or norm in ("junior kg", "lkg"):
        return "PP-1 / Junior KG / LKG"
    if re.search(r"pp\s*2", norm) or compact.startswith("pp2") or norm in ("senior kg", "ukg"):
        return "PP-2 / Senior KG / UKG"
    if (
        norm.startswith("summer camp")
        or norm.startswith("summer program")
        or "day care" in norm
        or "daycare" in norm
    ):
        return "Summer Programs / Day Care"

    core_lower = core.lower()
    for label in HOMEWORK_CLASS_LABELS:
        label_lower = label.lower()
        if label_lower in core_lower or core_lower in label_lower:
            return label
    return None


def _parent_class_target_names(parent_profile) -> set[str]:
    """Legacy and canonical class strings that should match centre-wide rows for this parent."""
    names: set[str] = set()
    for cn in StudentProfile.objects.filter(parent=parent_profile, is_active=True).values_list(
        "class_name", flat=True
    ):
        cn = (cn or "").strip()
        if not cn:
            continue
        names.add(cn)
        stripped = _strip_legacy_class_year(cn)
        if stripped:
            names.add(stripped)
        canon = _canonical_class_label(cn)
        if canon:
            names.add(canon)
    return names


def normalize_portal_class_name(class_name: str) -> str:
    """Store franchise portal class targets using canonical labels when possible."""
    raw = (class_name or "").strip()
    if not raw:
        return ""
    return _canonical_class_label(raw) or raw


def _matching_target_class_names(parent_profile) -> set[str]:
    """
    Announcement/homework ``class_name`` values visible to this parent.
    Uses the same fuzzy rules as ``_class_label_matches`` (not exact DB equality).
    """
    names: set[str] = set()
    for cn in _parent_class_target_names(parent_profile):
        candidates: set[str] = {cn}
        stripped = _strip_legacy_class_year(cn)
        if stripped:
            candidates.add(stripped)
        canon = _canonical_class_label(cn)
        if canon:
            candidates.add(canon)
        candidates.update(HOMEWORK_CLASS_LABELS)

        for candidate in candidates:
            candidate = (candidate or "").strip()
            if not candidate:
                continue
            if _class_label_matches(cn, candidate):
                names.add(candidate)
            if _class_label_matches(candidate, cn):
                names.add(candidate)
    return {n for n in names if n}


def _student_ids_visible_to_parent(parent_profile, user=None) -> set[int]:
    """Active student ids whose homework/announcements this login should see."""
    ids = set(
        StudentProfile.objects.filter(parent=parent_profile, is_active=True).values_list("pk", flat=True)
    )
    if user:
        legacy = find_student_for_parent_user(user)
        if legacy and legacy.is_active and user_owns_legacy_student(user, legacy):
            ids.add(legacy.pk)
    return ids


def _centre_class_visibility_q(parent_profile, user=None) -> Q:
    """Centre-wide or class-targeted rows visible to a parent (homework + announcements)."""
    vis = Q(student__isnull=True, class_name="")
    for student_id in _student_ids_visible_to_parent(parent_profile, user=user):
        vis |= Q(student_id=student_id)
    matching_classes = _matching_target_class_names(parent_profile)
    if matching_classes:
        vis |= Q(student__isnull=True, class_name__in=matching_classes)
    return vis


def _homework_visible_q(parent_profile, user=None):
    """Centre-wide homework plus class rows matching each child's class_name."""
    return _centre_class_visibility_q(parent_profile, user=user)


def _class_label_matches(student_class: str, target_class: str) -> bool:
    """True when a child's class should receive centre content aimed at target_class."""
    sc = (student_class or "").strip()
    tc = (target_class or "").strip()
    if not sc or not tc:
        return False

    sc_canon = _canonical_class_label(sc) or sc
    tc_canon = _canonical_class_label(tc) or tc
    if sc_canon == tc_canon:
        return True
    if sc_canon == tc or tc_canon == sc:
        return True
    if sc.lower() == tc.lower():
        return True
    return False


def _announcement_visible_q(parent_profile, user=None):
    """Centre-wide, class-targeted, or student-specific announcements for this parent."""
    return _centre_class_visibility_q(parent_profile, user=user)


def _parent_centre(parent_profile):
    return effective_franchise_for_parent(parent_profile)


def parent_profiles_for_announcement(announcement):
    """Parents who should receive an announcement (in-app and email)."""
    from franchises.models import ParentProfile

    if announcement.student_id:
        try:
            student = announcement.student
        except StudentProfile.DoesNotExist:
            return ParentProfile.objects.none()
        parent_id = student.parent_id
        if not parent_id:
            return ParentProfile.objects.none()
        return ParentProfile.objects.filter(pk=parent_id).select_related("user", "franchise")

    base = parents_at_franchise(announcement.franchise)
    target_class = normalize_portal_class_name(announcement.class_name or "")
    if target_class:
        parent_ids: set[int] = set()
        base_parent_ids = list(base.values_list("pk", flat=True))
        for student in StudentProfile.objects.filter(
            is_active=True,
            parent_id__in=base_parent_ids,
        ).only("parent_id", "class_name"):
            if _class_label_matches(student.class_name, target_class):
                parent_ids.add(student.parent_id)
        return base.filter(pk__in=parent_ids)
    return base


def _parent_student_from_request(request, parent_profile):
    """Optional ?student= or ?student_id= — one linked child for multi-child filtering."""
    if not parent_profile or request is None:
        return None
    params = getattr(request, "query_params", None) or getattr(request, "GET", None)
    if params is None:
        return None
    raw = (params.get("student") or params.get("student_id") or "").strip()
    if not raw:
        return None
    try:
        sid = int(raw)
    except (TypeError, ValueError):
        return None
    return StudentProfile.objects.filter(parent=parent_profile, is_active=True, pk=sid).first()


def _parent_focus_student(request, parent_profile):
    """
    One child for scoped parent APIs (attendance, fees on mobile).
    Uses explicit ?student= when sent; otherwise primary / only active child so
    native apps do not merge every sibling's records when the param is omitted.
    """
    explicit = _parent_student_from_request(request, parent_profile)
    if explicit is not None:
        return explicit
    if not parent_profile:
        return None
    user = getattr(request, "user", None) if request else None
    if user:
        from accounts.profile_access import primary_student_for_parent_user

        student, pp = primary_student_for_parent_user(user)
        if student and student.is_active and student.parent_id == parent_profile.pk:
            return student
    return (
        StudentProfile.objects.filter(parent=parent_profile, is_active=True)
        .order_by("first_name", "last_name", "id")
        .first()
    )


def _parent_attendance_api_payload(
    request,
    rows: list,
    focus: StudentProfile | None,
    *,
    centre=None,
) -> dict | list:
    """Mobile envelope; ``?wrap=list`` keeps bare array for legacy/web."""
    params = getattr(request, "query_params", None) or getattr(request, "GET", None)
    wrap = ((params.get("wrap") if params else None) or "").strip().lower()
    if wrap in ("list", "array"):
        return rows
    payload = {
        "attendance": rows,
        "count": len(rows),
        "student_id": focus.pk if focus else None,
        "student_name": focus.full_name if focus else "",
        "class_name": ((focus.class_name or "").strip() if focus else ""),
    }
    if focus is None and params is not None:
        payload["requires_student"] = True
    if focus is not None and centre is not None:
        from students.attendance_logic import (
            build_summaries_for_student,
            collect_holiday_map,
            holiday_dates_payload,
            month_bounds,
            resolved_attendance_row,
        )

        month_str = ((params.get("month") if params else None) or "").strip()
        if month_str:
            start, end = month_bounds(month_str)
        else:
            start, end = month_bounds(date.today().strftime("%Y-%m"))
        if start is not None and end is not None:
            holiday_map = collect_holiday_map(centre, start, end)
            payload["holiday_dates"] = holiday_dates_payload(holiday_map)
            payload["attendance_summary"] = build_summaries_for_student(
                focus,
                centre,
                months=[month_str] if month_str else None,
                records=rows,
            ).get(month_str or date.today().strftime("%Y-%m"))
            selected_day = _selected_date_from_request(request)
            if selected_day is not None:
                record = next((row for row in rows if _row_on_date(row, selected_day.isoformat())), None)
                payload["resolved_attendance"] = resolved_attendance_row(
                    focus,
                    selected_day,
                    record=record,
                    holiday_map=holiday_map,
                )
    return payload


def _homework_row_visible_for_student(row, student) -> bool:
    if row.student_id:
        return row.student_id == student.pk
    target_class = (row.class_name or "").strip()
    if target_class:
        return _class_label_matches(student.class_name, target_class)
    return True


def _filter_homework_queryset_for_student(queryset, student):
    if student is None:
        return queryset
    ids = [row.pk for row in queryset if _homework_row_visible_for_student(row, student)]
    return queryset.filter(pk__in=ids)


def _announcement_row_visible_for_student(row, student) -> bool:
    if getattr(row, "student_id", None):
        return row.student_id == student.pk
    target_class = (row.class_name or "").strip()
    if target_class:
        return _class_label_matches(student.class_name, target_class)
    return True


def _filter_announcements_for_student(queryset, student):
    if student is None:
        return queryset
    ids = [row.pk for row in queryset if _announcement_row_visible_for_student(row, student)]
    return queryset.filter(pk__in=ids)


def _calendar_item_row(
    *,
    item_type: str,
    item_id: int,
    title: str,
    date_str: str,
    detail: str = "",
    end_date: str | None = None,
) -> dict:
    """Unified calendar row — same shape the parent web calendar uses per day."""
    row = {
        "id": f"{item_type}-{item_id}",
        "type": item_type,
        "title": (title or "").strip() or item_type.replace("_", " ").title(),
        "date": date_str,
        "detail": (detail or "").strip(),
        "source_id": item_id,
    }
    end = (end_date or date_str or "")[:10]
    if end and end != date_str:
        row["end_date"] = end
    return row


def _homework_calendar_detail(row: dict) -> str:
    cls = (row.get("class_name") or "").strip()
    if cls and cls.lower() not in ("all classes", "all"):
        return cls
    name = (row.get("student_name") or "").strip()
    if name and not name.lower().startswith("all students"):
        return name
    return cls or "All classes"


def _build_parent_calendar_items(
    events_data: list,
    homework_data: list,
    announcement_data: list,
) -> list[dict]:
    items: list[dict] = []
    for ev in events_data:
        start = str(ev.get("start_date") or ev.get("date") or "")[:10]
        if not start:
            continue
        end = str(ev.get("end_date") or start)[:10]
        detail = (
            (ev.get("audience_label") or "").strip()
            or (ev.get("class_name") or "").strip()
            or (ev.get("location") or "").strip()
        )
        items.append(
            _calendar_item_row(
                item_type="event",
                item_id=int(ev["id"]),
                title=str(ev.get("title") or "Event"),
                date_str=start,
                detail=detail,
                end_date=end,
            )
        )
    for hw in homework_data:
        date_str = str(hw.get("assigned_date") or "")[:10]
        if not date_str:
            continue
        items.append(
            _calendar_item_row(
                item_type="homework",
                item_id=int(hw["id"]),
                title=str(hw.get("title") or "Homework"),
                date_str=date_str,
                detail=_homework_calendar_detail(hw),
            )
        )
    for ann in announcement_data:
        date_str = str(ann.get("published_at") or "")[:10]
        if not date_str:
            continue
        detail = (
            (ann.get("audience_label") or "").strip()
            or (ann.get("class_name") or "").strip()
            or (ann.get("body") or "").strip()[:120]
        )
        items.append(
            _calendar_item_row(
                item_type="announcement",
                item_id=int(ann["id"]),
                title=str(ann.get("title") or "Announcement"),
                date_str=date_str,
                detail=detail,
            )
        )
    items.sort(key=lambda row: (row["date"], row["type"], row["title"].lower()))
    return items


def _parent_parental_tips_notification_qs(request, pp, focus=None):
    """Recent parental tips visible to this parent (for the notifications feed)."""
    from documents.models import DocumentCategory
    from documents.views import _parent_documents_visible_queryset

    if not pp:
        return []

    qs = _parent_documents_visible_queryset(request.user, student=focus).filter(
        category=DocumentCategory.PARENTING_TIPS,
    )
    cutoff = timezone.now() - timedelta(days=30)
    qs = qs.filter(Q(updated_at__gte=cutoff) | Q(created_at__gte=cutoff))
    return list(qs.order_by("-updated_at", "-created_at")[:50])


def _parent_parental_tips_calendar_items(request, focus) -> list[dict]:
    """Parental tip rows for parent calendar (upload / update date)."""
    from documents.models import DocumentCategory
    from documents.serializers import ParentDocumentSerializer
    from documents.views import _parent_documents_visible_queryset

    qs = _parent_documents_visible_queryset(request.user, student=focus).filter(
        category=DocumentCategory.PARENTING_TIPS,
    )
    rows = ParentDocumentSerializer(
        qs.order_by("-updated_at", "-created_at"),
        many=True,
        context={"request": request, "merge_holiday_for_parent": True},
    ).data

    items: list[dict] = []
    for row in rows:
        pk = int(row["id"])
        updated = str(row.get("updated_at") or row.get("created_at") or "")[:10]
        if not updated:
            continue
        title = str(row.get("display_title") or row.get("title") or "Parental tip")
        detail = (row.get("description") or row.get("source_label") or "").strip()
        items.append(
            _calendar_item_row(
                item_type="parental_tip",
                item_id=pk,
                title=title,
                date_str=updated,
                detail=detail,
            )
        )
    return items


def _parent_holiday_lists_payload(request, focus) -> list[dict]:
    """Grouped holiday list cards for calendar-attendance / mobile."""
    from documents.models import DocumentCategory
    from documents.parent_document_mobile import build_holiday_list_cards
    from documents.serializers import ParentDocumentSerializer
    from documents.views import _parent_documents_visible_queryset

    qs = _parent_documents_visible_queryset(request.user, student=focus).filter(
        category=DocumentCategory.HOLIDAY_LISTS,
    )
    rows = ParentDocumentSerializer(
        qs.order_by("state", "-academic_year", "-updated_at"),
        many=True,
        context={"request": request, "merge_holiday_for_parent": True},
    ).data
    return build_holiday_list_cards(rows)


def _parent_parental_tips_payload(request, focus) -> list[dict]:
    """Mobile parental tip rows for calendar-attendance."""
    from documents.models import DocumentCategory
    from documents.parent_document_mobile import parent_document_mobile_row
    from documents.serializers import ParentDocumentSerializer
    from documents.views import _parent_documents_visible_queryset

    qs = _parent_documents_visible_queryset(request.user, student=focus).filter(
        category=DocumentCategory.PARENTING_TIPS,
    )
    rows = ParentDocumentSerializer(
        qs.order_by("-updated_at", "-created_at"),
        many=True,
        context={"request": request, "merge_holiday_for_parent": True},
    ).data
    return [parent_document_mobile_row(row) for row in rows]


def _parent_newsletter_calendar_items(request, focus) -> list[dict]:
    """Newsletter rows for parent calendar (block date and upload date when they differ)."""
    from documents.models import DocumentCategory
    from documents.serializers import ParentDocumentSerializer
    from documents.views import _parent_document_category_filter, _parent_documents_visible_queryset

    qs = _parent_documents_visible_queryset(request.user, student=focus).filter(
        category__in=_parent_document_category_filter(DocumentCategory.CLASS_TIMETABLE)
    )
    rows = ParentDocumentSerializer(
        qs.order_by("-period_start", "-created_at"),
        many=True,
        context={"request": request, "merge_holiday_for_parent": True},
    ).data

    items: list[dict] = []
    for row in rows:
        pk = int(row["id"])
        block = str(row.get("period_start") or "")[:10]
        uploaded = str(row.get("created_at") or "")[:10]
        title = str(row.get("display_title") or row.get("title") or "Newsletter")
        detail = (row.get("source_label") or "").strip()
        dates: list[str] = []
        if block:
            dates.append(block)
        if uploaded and uploaded not in dates:
            dates.append(uploaded)
        if not dates:
            continue
        for day in dates:
            items.append(
                _calendar_item_row(
                    item_type="newsletter",
                    item_id=pk,
                    title=title,
                    date_str=day,
                    detail=detail,
                )
            )
    return items


def _calendar_item_on_date(item: dict, day: str) -> bool:
    """True when ``day`` (YYYY-MM-DD) falls within the item's date range."""
    d = (day or "")[:10]
    if not d:
        return False
    start = str(item.get("date") or "")[:10]
    end = str(item.get("end_date") or start)[:10]
    if not start:
        return False
    return start <= d <= end


def _event_on_date(ev: dict, day: str) -> bool:
    d = (day or "")[:10]
    start = str(ev.get("start_date") or ev.get("date") or "")[:10]
    end = str(ev.get("end_date") or start)[:10]
    if not start or not d:
        return False
    return start <= d <= end


def _row_on_date(row: dict, day: str, *, date_field: str = "date") -> bool:
    return str(row.get(date_field) or "")[:10] == (day or "")[:10]


def _selected_date_from_request(request) -> date | None:
    params = getattr(request, "query_params", None) or getattr(request, "GET", None)
    if params is None:
        return None
    raw = (params.get("date") or params.get("selected_date") or "").strip()
    if not raw:
        return None
    return parse_date(raw)


def _parent_calendar_attendance_payload(
    request,
    pp,
    centre,
    *,
    focus: StudentProfile | None,
    selected_date: date | None = None,
) -> dict:
    """Calendar + attendance for one focused child (matches parent web calendar rules)."""
    events_qs = exclude_showcase_placeholder_events(parent_events_queryset(pp, centre=centre, student=focus))
    event_ctx = {"request": request, "omit_video_links": True}
    events_data = EventSerializer(events_qs, many=True, context=event_ctx).data

    homework_qs = HomeworkAssignment.objects.none()
    announcements_qs = Announcement.objects.none()
    if centre:
        homework_qs = (
            HomeworkAssignment.objects.filter(franchise=centre)
            .filter(_homework_visible_q(pp, user=request.user))
            .filter(parent_visible_homework_q())
            .select_related("student")
            .distinct()
            .order_by("-assigned_date", "-created_at")
        )
        announcements_qs = (
            Announcement.objects.filter(franchise=centre, is_active=True, visible_to_parents=True)
            .filter(_announcement_visible_q(pp, user=request.user))
            .filter(parent_visible_announcement_q())
            .select_related("student")
            .distinct()
            .order_by("-published_at")
        )
    if focus is not None:
        homework_qs = _filter_homework_queryset_for_student(homework_qs, focus)
        announcements_qs = _filter_announcements_for_student(announcements_qs, focus)

    hw_ctx = {"request": request}
    homework_data = HomeworkAssignmentSerializer(homework_qs, many=True, context=hw_ctx).data
    announcement_data = AnnouncementSerializer(announcements_qs, many=True, context=hw_ctx).data

    attendance_qs = (
        AttendanceRecord.objects.filter(student__parent=pp, student__is_active=True)
        .select_related("student")
        .order_by("-date", "student_id")
    )
    if focus is not None:
        attendance_qs = attendance_qs.filter(student_id=focus.pk)
    attendance_rows = AttendanceRecordSerializer(attendance_qs, many=True).data
    all_attendance_rows = attendance_rows

    from students.attendance_logic import (
        build_summaries_for_student,
        collect_holiday_map,
        holiday_dates_payload,
        month_bounds,
        resolved_attendance_row,
    )

    summary_month = (selected_date or date.today()).strftime("%Y-%m")
    month_start, month_end = month_bounds(summary_month)
    holiday_map: dict[date, str] = {}
    if month_start is not None and month_end is not None and centre is not None:
        holiday_map = collect_holiday_map(centre, month_start, month_end)

    calendar_items = _build_parent_calendar_items(events_data, homework_data, announcement_data)
    calendar_items.extend(_parent_newsletter_calendar_items(request, focus))
    calendar_items.extend(_parent_parental_tips_calendar_items(request, focus))
    holiday_lists = _parent_holiday_lists_payload(request, focus)
    parental_tips = _parent_parental_tips_payload(request, focus)
    if holiday_map:
        for holiday_day, label in sorted(holiday_map.items(), key=lambda item: item[0]):
            calendar_items.append(
                {
                    "id": f"holiday-{holiday_day.isoformat()}",
                    "type": "holiday",
                    "title": label,
                    "date": holiday_day.isoformat(),
                    "detail": "Holiday",
                    "source_id": None,
                }
            )
    calendar_items.sort(key=lambda row: (row["date"], row["type"], row["title"].lower()))

    selected_day = selected_date.isoformat() if selected_date else None
    if selected_day:
        calendar_items = [row for row in calendar_items if _calendar_item_on_date(row, selected_day)]
        attendance_rows = [row for row in attendance_rows if _row_on_date(row, selected_day)]

    attendance_summary = None
    attendance_summary_by_month = None
    holiday_dates = holiday_dates_payload(holiday_map) if holiday_map else []
    resolved_attendance = None
    if focus is not None and centre is not None:
        attendance_summary_by_month = build_summaries_for_student(
            focus,
            centre,
            records=all_attendance_rows,
        )
        attendance_summary = attendance_summary_by_month.get(summary_month)
        if selected_date is not None:
            record = next((row for row in attendance_rows), None)
            resolved_attendance = resolved_attendance_row(
                focus,
                selected_date,
                record=record,
                holiday_map=holiday_map,
            )
            if resolved_attendance and not attendance_rows:
                attendance_rows = [resolved_attendance]
            elif resolved_attendance and attendance_rows:
                attendance_rows[0] = {
                    **attendance_rows[0],
                    "status": resolved_attendance["status"],
                    "resolved_status": resolved_attendance["resolved_status"],
                    "is_holiday": resolved_attendance["is_holiday"],
                    "holiday_label": resolved_attendance.get("holiday_label") or "",
                }

    # calendar_items is the canonical list for calendar UI. Omit parallel detail arrays
    # so mobile apps that merge calendar_items + calendar_events/homework/announcements
    # do not render the same row twice (e.g. "holi" shown as two cards). Use source_id
    # with GET /events/parent/, /students/parent/homework/, etc. for attachments/media.
    events_data = []
    homework_data = []
    announcement_data = []

    student_block = None
    if focus is not None:
        student_block = {
            "id": focus.pk,
            "name": focus.full_name,
            "class_name": (focus.class_name or "").strip(),
        }

    payload = {
        "student": student_block,
        "selected_date": selected_day,
        "response_mode": "day" if selected_day else "full",
        "calendar_items": calendar_items,
        "calendar_events": events_data,
        "homework": homework_data,
        "announcements": announcement_data,
        "attendance": attendance_rows,
        "attendance_count": len(attendance_rows),
        "attendance_for_date": None,
        "attendance_summary": attendance_summary,
        "attendance_summary_by_month": attendance_summary_by_month,
        "holiday_dates": holiday_dates,
        "holiday_lists": holiday_lists,
        "parental_tips": parental_tips,
        "resolved_attendance": resolved_attendance,
        "student_id": focus.pk if focus else None,
        "student_name": focus.full_name if focus else "",
        "class_name": ((focus.class_name or "").strip() if focus else ""),
    }
    if focus is None:
        multi = StudentProfile.objects.filter(parent=pp, is_active=True).count() > 1
        if multi:
            payload["requires_student"] = True
    return payload


# ----- Parent (read-only / limited write) -----


class ParentHomeworkListView(generics.ListAPIView):
    permission_classes = [IsParentUser]
    serializer_class = HomeworkAssignmentSerializer
    pagination_class = None

    def get_queryset(self):
        pp = resolved_parent_profile_for_user(self.request.user)
        centre = _parent_centre(pp)
        if not pp or not centre:
            return HomeworkAssignment.objects.none()
        qs = (
            HomeworkAssignment.objects.filter(franchise=centre)
            .filter(_homework_visible_q(pp, user=self.request.user))
            .filter(parent_visible_homework_q())
            .select_related("student")
            .distinct()
            .order_by("-assigned_date", "-created_at")
        )
        focus = _parent_focus_student(self.request, pp)
        return _filter_homework_queryset_for_student(qs, focus)


def _announcement_notification_rows(rows, read_map=None):
    """Shape centre announcements for parent app notification feeds."""
    read_map = read_map or {}
    notifications = []
    for row in rows:
        ann_id = row.get("id")
        key = f"announcement-{ann_id}"
        read_at = read_map.get(key)
        body = row.get("body") or ""
        class_name = (row.get("class_name") or "").strip()
        notifications.append(
            {
                "id": key,
                "source": "announcement",
                "source_id": ann_id,
                "title": row.get("title") or "Announcement",
                "body": body,
                "message": body,
                "description": body,
                "class_name": class_name,
                "published_at": row.get("published_at"),
                "audience_label": row.get("audience_label") or "",
                "student_name": row.get("student_name") or "",
                "read": read_at is not None,
                "read_at": read_at,
            }
        )
    return notifications


def _notification_class_label(*, class_name="", student=None) -> str:
    label = (class_name or "").strip()
    if label:
        return label
    if student is not None:
        try:
            return (student.class_name or "").strip()
        except Exception:
            return ""
    return ""


class ParentAnnouncementListView(generics.ListAPIView):
    permission_classes = [IsParentUser]
    serializer_class = AnnouncementSerializer
    pagination_class = None

    def get_queryset(self):
        pp = resolved_parent_profile_for_user(self.request.user)
        centre = _parent_centre(pp)
        if not pp or not centre:
            return Announcement.objects.none()
        qs = (
            Announcement.objects.filter(franchise=centre, is_active=True, visible_to_parents=True)
            .filter(_announcement_visible_q(pp, user=self.request.user))
            .filter(parent_visible_announcement_q())
            .select_related("student")
            .distinct()
            .order_by("-published_at")
        )
        focus = _parent_student_from_request(self.request, pp)
        return _filter_announcements_for_student(qs, focus)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        rows = self.get_serializer(queryset, many=True).data
        if (request.query_params.get("format") or "").strip().lower() == "list":
            return Response(rows)

        read_map = {}
        pp = resolved_parent_profile_for_user(request.user)
        if pp:
            try:
                read_map = {
                    row["notification_key"]: row["read_at"]
                    for row in ParentNotificationRead.objects.filter(parent=pp).values(
                        "notification_key", "read_at"
                    )
                }
            except (ProgrammingError, OperationalError):
                read_map = {}

        notifications = _announcement_notification_rows(rows, read_map=read_map)
        unread_count = sum(1 for n in notifications if not n["read"])
        return Response(
            {
                "announcements": rows,
                "notifications": notifications,
                "count": len(rows),
                "unread_count": unread_count,
            }
        )


class ParentAttendanceListView(generics.ListAPIView):
    permission_classes = [IsParentUser]
    serializer_class = AttendanceRecordSerializer
    pagination_class = None

    def get_queryset(self):
        pp = resolved_parent_profile_for_user(self.request.user)
        if not pp:
            return AttendanceRecord.objects.none()
        qs = (
            AttendanceRecord.objects.filter(student__parent=pp, student__is_active=True)
            .select_related("student")
            .order_by("-date", "student_id")
        )
        focus = _parent_focus_student(self.request, pp)
        if focus is not None:
            qs = qs.filter(student_id=focus.pk)
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        pp = resolved_parent_profile_for_user(request.user)
        focus = _parent_focus_student(request, pp)
        centre = _parent_centre(pp)
        payload = _parent_attendance_api_payload(request, serializer.data, focus, centre=centre)
        if isinstance(payload, list):
            return Response(payload)
        return Response(payload)


class ParentCalendarAttendanceView(APIView):
    """
    Combined parent payload for calendar + attendance for **one focused child**.

    Pass ``?student=`` or ``?student_id=`` (id from ``/students/parent/students/``).
    Pass ``?date=YYYY-MM-DD`` (or ``?selected_date=``) to scope the response to one day —
    ``calendar_items``, ``attendance``, etc. then contain only that date (for date tap / mobile).

    Events, homework, and announcements are class-filtered like the parent web calendar —
    not every sibling's rows mixed together.

    Prefer ``calendar_items[]`` for the day/month UI; use ``calendar_events`` / ``homework``
    when you need full event media or homework attachments.
    """

    permission_classes = [IsParentUser]

    def get(self, request):
        pp = resolved_parent_profile_for_user(request.user)
        centre = _parent_centre(pp)
        if not pp or not centre:
            return Response(
                {
                    "student": None,
                    "selected_date": None,
                    "calendar_items": [],
                    "calendar_events": [],
                    "homework": [],
                    "announcements": [],
                    "attendance": [],
                    "attendance_count": 0,
                    "attendance_for_date": None,
                    "attendance_summary": None,
                    "attendance_summary_by_month": None,
                    "holiday_dates": [],
                    "holiday_lists": [],
                    "parental_tips": [],
                    "resolved_attendance": None,
                    "student_id": None,
                    "student_name": "",
                    "class_name": "",
                }
            )

        focus = _parent_focus_student(request, pp)
        selected_date = _selected_date_from_request(request)
        return Response(
            _parent_calendar_attendance_payload(
                request, pp, centre, focus=focus, selected_date=selected_date
            )
        )


class ParentFeeListView(generics.ListAPIView):
    permission_classes = [IsParentUser]
    serializer_class = FeeRecordSerializer
    pagination_class = None

    def get_queryset(self):
        pp = resolved_parent_profile_for_user(self.request.user)
        if not pp:
            return FeeRecord.objects.none()
        return (
            FeeRecord.objects.filter(student__parent=pp, student__is_active=True)
            .select_related("student")
            .order_by("-due_date", "-created_at")
        )


class ParentFeeSummaryView(APIView):
    """Parent fee view — legacy TiKES MySQL when configured, else centre-entered FeeRecord rows."""

    permission_classes = [IsParentUser]

    def get(self, request):
        from accounts.profile_access import primary_student_for_parent_user
        from students.fee_summary import build_fee_summary_from_records
        from students.legacy_fee_service import fetch_legacy_fee_summary, legacy_fee_db_configured

        def empty_summary(*, id_card_no: str = "", lookup_message: str = "") -> Response:
            payload: dict = {
                "source": "empty",
                "student": {},
                "alerts": {"dropped_out": False, "drop_reason": "", "refund_done": False},
                "lines": [],
                "totals": {
                    "total_fee": 0,
                    "discount": 0,
                    "net_payable": 0,
                    "amount_paid": 0,
                    "balance": 0,
                },
                "payments": [],
                "legacy_configured": legacy_fee_db_configured(),
            }
            if id_card_no:
                payload["lookup_id_card"] = id_card_no
            if lookup_message:
                payload["lookup_message"] = lookup_message
            return Response(payload)

        pp = resolved_parent_profile_for_user(request.user)
        student_id = (request.query_params.get("student") or request.query_params.get("student_id") or "").strip()
        student = None

        if pp:
            students_qs = StudentProfile.objects.filter(parent=pp, is_active=True).select_related(
                "parent", "parent__franchise"
            )
            if student_id:
                try:
                    sid = int(student_id)
                except (TypeError, ValueError):
                    return empty_summary(lookup_message="Invalid student id.")
                student = students_qs.filter(pk=sid).first()
                if not student:
                    return empty_summary(lookup_message="Student not found for this parent account.")

        if not student and not student_id:
            student, pp_from_primary = primary_student_for_parent_user(request.user)
            if not pp:
                pp = pp_from_primary

        id_card_no = ""
        if student:
            id_card_no = (student.Idcardno or "").strip() or (request.user.username or "").strip()
        else:
            id_card_no = (request.user.username or "").strip()

        legacy_summary = None
        legacy_lookup_error = ""
        if id_card_no and legacy_fee_db_configured():
            legacy_summary, legacy_lookup_error = fetch_legacy_fee_summary(id_card_no)

        if not student:
            if legacy_summary:
                legacy_summary["legacy_configured"] = True
                legacy_summary.setdefault("student", {})
                parent_name = (legacy_summary["student"].get("parent_name") or "").strip()
                if not parent_name:
                    parent_name = (request.user.full_name or "").strip()
                legacy_summary["student"]["parent_name"] = parent_name
                legacy_summary["lookup_id_card"] = id_card_no
                return Response(legacy_summary)

            msg = "No student is linked to this parent login."
            if id_card_no and legacy_fee_db_configured() and legacy_lookup_error:
                msg = (
                    f"No student profile found locally. TiKES lookup for ID card {id_card_no}: "
                    f"{legacy_lookup_error}"
                )
            return empty_summary(id_card_no=id_card_no, lookup_message=msg)

        centre_name = ""
        if pp and pp.franchise_id:
            centre_name = (pp.franchise.name or "").strip()
        if not centre_name:
            centre_name = (student.Centre or "").strip()

        if not id_card_no:
            id_card_no = (request.user.username or "").strip()

        summary = legacy_summary
        if not summary:
            summary = build_fee_summary_from_records(student, centre_name=centre_name)

        summary["legacy_configured"] = legacy_fee_db_configured()
        summary["student_id"] = student.id
        summary.setdefault("student", {})
        parent_name = (student.ParentName or "").strip()
        if not parent_name and pp and getattr(pp, "user", None):
            parent_name = (pp.user.full_name or "").strip()
        if not parent_name:
            parent_name = (request.user.full_name or "").strip()
        summary["student"]["parent_name"] = parent_name
        if id_card_no:
            summary["lookup_id_card"] = id_card_no
        if not summary.get("lines") and legacy_lookup_error:
            summary["lookup_message"] = legacy_lookup_error
        elif not summary.get("lines") and legacy_fee_db_configured() and id_card_no:
            summary["lookup_message"] = (
                f"TiKES is connected but fee_payment has no active records for ID card {id_card_no}."
            )
        from students.fee_summary import merge_centre_status_overrides

        summary = merge_centre_status_overrides(student, summary)
        return Response(summary)


class ParentFeePaymentConfigView(APIView):
    permission_classes = [IsParentUser]

    def get(self, request):
        from students.fee_payment import parent_fee_upi_settings

        cfg = parent_fee_upi_settings()
        return Response(
            {
                "configured": bool(cfg["upi_vpa"] or cfg["qr_image_url"]),
                "payee_name": cfg["payee_name"],
                "qr_image_url": cfg["qr_image_url"],
            }
        )


class ParentFeePayInitView(APIView):
    """Start UPI QR payment for one fee line."""

    permission_classes = [IsParentUser]

    def post(self, request):
        import uuid
        from decimal import Decimal

        from students.fee_payment import (
            build_upi_pay_uri,
            parent_fee_upi_settings,
            resolve_payable_line,
        )
        from students.fee_summary import build_fee_summary_from_records
        from students.legacy_fee_service import fetch_legacy_fee_summary, legacy_fee_db_configured

        cfg = parent_fee_upi_settings()
        if not cfg["upi_vpa"] and not cfg["qr_image_url"]:
            return Response(
                {"detail": "Fee payment QR is not configured yet. Ask your centre to set PARENT_FEE_UPI_VPA."},
                status=503,
            )

        pp = resolved_parent_profile_for_user(request.user)
        if not pp:
            return Response({"detail": "Parent profile not found"}, status=404)

        from accounts.profile_access import primary_student_for_parent_user

        student, _ = primary_student_for_parent_user(request.user)
        if not student:
            return Response({"detail": "No student linked to this account"}, status=400)

        fee_record_id = request.data.get("fee_record_id")
        line_serial = request.data.get("line_serial")
        fee_type = (request.data.get("fee_type") or "").strip()

        id_card_no = (student.Idcardno or "").strip() or (request.user.username or "").strip()
        centre_name = (pp.franchise.name or "").strip() if pp.franchise_id else (student.Centre or "").strip()
        summary = None
        if id_card_no and legacy_fee_db_configured():
            summary, _err = fetch_legacy_fee_summary(id_card_no)
        if not summary or not summary.get("lines"):
            summary = build_fee_summary_from_records(student, centre_name=centre_name)

        from students.fee_payment import apply_paid_payments_to_summary

        summary = apply_paid_payments_to_summary(summary, student, pp)

        try:
            fr_id = int(fee_record_id) if fee_record_id is not None else None
        except (TypeError, ValueError):
            fr_id = None
        try:
            serial = int(line_serial) if line_serial is not None else None
        except (TypeError, ValueError):
            serial = None

        line, err = resolve_payable_line(
            student=student,
            parent=pp,
            summary=summary,
            fee_record_id=fr_id,
            line_serial=serial,
            fee_type=fee_type,
        )
        if not line:
            return Response({"detail": err or "Cannot pay this fee"}, status=400)

        balance = Decimal(str(line.get("balance") or 0)).quantize(Decimal("0.01"))
        if balance <= 0:
            return Response({"detail": "Nothing to pay for this line"}, status=400)

        fixed_qr_amount = cfg.get("qr_fixed_amount")
        if fixed_qr_amount is not None:
            amount = fixed_qr_amount
        else:
            amount = balance

        fee_record = None
        if line.get("fee_record_id"):
            fee_record = FeeRecord.objects.filter(pk=line["fee_record_id"], student=student).first()

        payment = ParentFeePayment.objects.create(
            parent=pp,
            student=student,
            fee_record=fee_record,
            line_serial=int(line.get("serial") or serial or 0),
            fee_type=(line.get("fee_type") or fee_type or "Fee")[:255],
            amount=amount,
            transaction_ref=uuid.uuid4().hex[:16].upper(),
        )

        note = f"Fee {payment.fee_type} {student.full_name}"[:80]
        upi_uri = ""
        if cfg["upi_vpa"]:
            upi_uri = build_upi_pay_uri(
                vpa=cfg["upi_vpa"],
                payee_name=cfg["payee_name"],
                amount=amount,
                note=note,
            )

        return Response(
            {
                "payment_id": payment.id,
                "amount": float(amount),
                "fee_type": payment.fee_type,
                "transaction_ref": payment.transaction_ref,
                "upi_uri": upi_uri,
                "payee_name": cfg["payee_name"],
                "qr_image_url": cfg["qr_image_url"],
            }
        )


class ParentFeePayConfirmView(APIView):
    """Confirm UPI payment after parent pays via QR (manual confirm until gateway webhook)."""

    permission_classes = [IsParentUser]

    def post(self, request):
        from decimal import Decimal

        from students.fee_payment import mark_fee_record_paid

        pp = resolved_parent_profile_for_user(request.user)
        if not pp:
            return Response({"detail": "Parent profile not found"}, status=404)

        try:
            payment_id = int(request.data.get("payment_id"))
        except (TypeError, ValueError):
            return Response({"detail": "payment_id is required"}, status=400)

        payment = (
            ParentFeePayment.objects.filter(pk=payment_id, parent=pp)
            .select_related("fee_record", "student")
            .first()
        )
        if not payment:
            return Response({"detail": "Payment not found"}, status=404)
        if payment.status == ParentFeePayment.Status.PAID:
            return Response(
                {
                    "success": True,
                    "payment_id": payment.id,
                    "amount": float(payment.amount),
                    "fee_type": payment.fee_type,
                    "already_paid": True,
                }
            )

        payment.status = ParentFeePayment.Status.PAID
        payment.paid_at = timezone.now()
        payment.mode_of_payment = "UPI QR"
        payment.save(update_fields=["status", "paid_at", "mode_of_payment", "updated_at"])

        if payment.fee_record_id:
            mark_fee_record_paid(payment.fee_record, Decimal(str(payment.amount)))

        return Response(
            {
                "success": True,
                "payment_id": payment.id,
                "amount": float(payment.amount),
                "fee_type": payment.fee_type,
                "student_name": payment.student.full_name,
            }
        )


class ParentFeePaymentReceiptView(APIView):
    """Payment receipt for a confirmed parent fee payment."""

    permission_classes = [IsParentUser]

    def get(self, request):
        from students.fee_payment import build_parent_fee_receipt

        pp = resolved_parent_profile_for_user(request.user)
        if not pp:
            return Response({"detail": "Parent profile not found"}, status=404)

        try:
            payment_id = int(request.query_params.get("payment_id"))
        except (TypeError, ValueError):
            return Response({"detail": "payment_id is required"}, status=400)

        payment = (
            ParentFeePayment.objects.filter(pk=payment_id, parent=pp, status=ParentFeePayment.Status.PAID)
            .select_related("student", "parent__franchise", "parent__user")
            .first()
        )
        if not payment:
            return Response({"detail": "Receipt not found"}, status=404)

        return Response(build_parent_fee_receipt(payment, pp))


class ParentGradeListView(generics.ListAPIView):
    permission_classes = [IsParentUser]
    serializer_class = GradeSerializer
    pagination_class = None

    def get_queryset(self):
        pp = resolved_parent_profile_for_user(self.request.user)
        if not pp:
            return Grade.objects.none()
        qs = (
            Grade.objects.filter(student__parent=pp, student__is_active=True)
            .select_related("student")
            .order_by("-exam_date", "subject")
        )
        focus = _parent_student_from_request(self.request, pp)
        if focus is not None:
            qs = qs.filter(student_id=focus.pk)
        return qs

def _parent_transport_routes_queryset(pp):
    """All transport routes published at the parent's centre (not only assigned routes)."""
    centre = _parent_centre(pp)
    if not centre:
        return TransportRoute.objects.none()
    return (
        TransportRoute.objects.filter(franchise=centre)
        .select_related("driver_profile__user")
        .order_by("sort_order", "route_name")
    )


class ParentTransportListView(generics.ListAPIView):
    permission_classes = [IsParentUser]
    serializer_class = ParentTransportRouteSerializer
    pagination_class = None

    def get_queryset(self):
        pp = resolved_parent_profile_for_user(self.request.user)
        if not pp:
            return TransportRoute.objects.none()
        return _parent_transport_routes_queryset(pp)

    def list(self, request, *args, **kwargs):
        pp = resolved_parent_profile_for_user(request.user)
        if not pp:
            return Response([])
        routes = list(self.get_queryset())
        student_ids = set(
            StudentProfile.objects.filter(parent=pp, is_active=True).values_list("id", flat=True)
        )
        payload = [
            _parent_transport_route_row(route, request, student_ids=student_ids)
            for route in routes
        ]
        return Response(payload)


class ParentLiveTransportView(APIView):
    """Live trips for any route at the parent's centre (parent picks a route in the app)."""

    permission_classes = [IsParentUser]

    def get(self, request):
        pp = resolved_parent_profile_for_user(request.user)
        centre = _parent_centre(pp)
        if not pp or not centre:
            return Response({"live": False, "detail": "Parent profile not found"}, status=404)

        school_location = None
        if centre.latitude and centre.longitude:
            school_location = {
                "latitude": float(centre.latitude),
                "longitude": float(centre.longitude),
            }

        students = StudentProfile.objects.filter(parent=pp, is_active=True)
        routes = _parent_transport_routes_queryset(pp)
        trips_qs = (
            TransportTrip.objects.filter(
                route__in=routes,
                status=TransportTrip.Status.LIVE,
                is_gps_active=True,
            )
            .select_related("route", "route__driver_profile__user")
            .prefetch_related("locations")
            .order_by("-started_at", "-created_at")
        )

        trips_data = []
        for trip in trips_qs:
            latest_location = trip.locations.order_by("-recorded_at").first()
            student_status = (
                trip.student_statuses.filter(student__in=students)
                .select_related("student")
                .order_by("-updated_at")
                .first()
            )
            entry = {
                "live": latest_location is not None,
                "route": ParentTransportRouteSerializer(trip.route, context={"request": request}).data,
                "trip": serialize_parent_live_trip(trip),
                "latest_location": serialize_parent_trip_location(latest_location),
            }
            status_payload = serialize_parent_trip_student_status(student_status)
            if status_payload is not None:
                entry["student_status"] = status_payload
            trips_data.append(entry)

        payload = {"live": len(trips_data) > 0, "trips": trips_data}
        if school_location:
            payload["school_location"] = school_location
        return Response(payload)


class ParentSupportTicketListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsParentUser]
    serializer_class = SupportTicketParentSerializer
    pagination_class = None

    def get_queryset(self):
        pp = resolved_parent_profile_for_user(self.request.user)
        if not pp:
            return SupportTicket.objects.none()
        qs = (
            SupportTicket.objects.filter(parent=pp)
            .select_related("student")
            .order_by("-created_at")
        )
        focus = _parent_student_from_request(self.request, pp)
        if focus is None:
            active_kids = StudentProfile.objects.filter(parent=pp, is_active=True)
            if active_kids.count() == 1:
                focus = active_kids.first()
            elif active_kids.count() > 1:
                return SupportTicket.objects.none()
        if focus is not None:
            qs = qs.filter(student_id=focus.pk)
        return qs

    def perform_create(self, serializer):
        pp = resolved_parent_profile_for_user(self.request.user)
        if not pp:
            raise PermissionDenied(
                "Parent profile not found. Your account is not linked to a centre yet — contact your preschool."
            )
        active_kids = StudentProfile.objects.filter(parent=pp, is_active=True)
        student = None
        raw_student = self.request.data.get("student")
        if raw_student not in (None, ""):
            try:
                sid = int(raw_student)
            except (TypeError, ValueError):
                raise PermissionDenied("Invalid student id.")
            student = active_kids.filter(pk=sid).first()
            if not student:
                raise PermissionDenied("Student not found for this parent account.")
        else:
            focus = _parent_student_from_request(self.request, pp) or _parent_focus_student(self.request, pp)
            if focus is not None:
                student = focus
        if active_kids.count() > 1 and student is None:
            raise PermissionDenied("Select which child this ticket is about (pass student id).")
        if active_kids.count() == 1 and student is None:
            student = active_kids.first()
        serializer.save(parent=pp, student=student)


class ParentNotificationsView(APIView):
    """Single parent notifications payload with all parent-visible updates."""

    permission_classes = [IsParentUser]

    @staticmethod
    def _notification_key(source: str, item_id: int) -> str:
        return f"{source}-{item_id}"

    def get(self, request):
        pp = resolved_parent_profile_for_user(request.user)
        centre = _parent_centre(pp)
        if not pp:
            return Response(
                {
                    "announcements": [],
                    "homework": [],
                    "fees": [],
                    "transport": [],
                    "events": [],
                    "achievements": [],
                    "attendance": [],
                    "parental_tips": [],
                    "notifications": [],
                    "unread_count": 0,
                }
            )

        announcements_qs = (
            Announcement.objects.filter(franchise=centre, is_active=True, visible_to_parents=True)
            .filter(_announcement_visible_q(pp, user=request.user))
            .filter(parent_visible_announcement_q())
            .select_related("student")
            .distinct()
            .order_by("-published_at")
        ) if centre else Announcement.objects.none()
        homework_qs = (
            HomeworkAssignment.objects.filter(franchise=centre)
            .filter(_homework_visible_q(pp, user=request.user))
            .filter(parent_visible_homework_q())
            .select_related("student")
            .distinct()
            .order_by("-assigned_date", "-created_at")
        ) if centre else HomeworkAssignment.objects.none()
        fees_qs = (
            FeeRecord.objects.filter(student__parent=pp, student__is_active=True)
            .select_related("student")
            .order_by("-due_date", "-created_at")
        )
        transport_qs = (
            TransportRoute.objects.filter(franchise=centre).order_by("sort_order", "route_name")
            if centre
            else TransportRoute.objects.none()
        )
        event_focus = _parent_focus_student(request, pp)
        events_qs = (
            exclude_showcase_placeholder_events(
                parent_events_queryset(pp, centre=centre, student=event_focus)
            )
            if centre
            else Event.objects.none()
        )
        kids = StudentProfile.objects.filter(parent=pp, is_active=True)
        achievements_qs = (
            (
                StudentAchievement.objects.filter(franchise=centre)
                .filter(Q(student__in=kids) | Q(student__isnull=True))
                .select_related("student")
                .distinct()
                .order_by("-achieved_date", "-created_at")
            )
            if centre
            else StudentAchievement.objects.none()
        )
        attendance_qs = (
            AttendanceRecord.objects.filter(student__parent=pp, student__is_active=True)
            .select_related("student")
            .order_by("-date", "student_id")
        )

        focus = _parent_student_from_request(request, pp)
        attendance_focus = _parent_focus_student(request, pp)
        homework_focus = _parent_focus_student(request, pp)
        if focus is not None:
            announcements_qs = _filter_announcements_for_student(announcements_qs, focus)
            fees_qs = fees_qs.filter(student_id=focus.pk)
            achievements_qs = achievements_qs.filter(Q(student__isnull=True) | Q(student_id=focus.pk))
        if homework_focus is not None:
            homework_qs = _filter_homework_queryset_for_student(homework_qs, homework_focus)
        if attendance_focus is not None:
            attendance_qs = attendance_qs.filter(student_id=attendance_focus.pk)

        parental_tips_qs = _parent_parental_tips_notification_qs(request, pp, focus=focus)

        try:
            read_map = {
                row["notification_key"]: row["read_at"]
                for row in ParentNotificationRead.objects.filter(parent=pp).values("notification_key", "read_at")
            }
        except (ProgrammingError, OperationalError):
            # Migration not applied yet; keep notifications working without read-state.
            read_map = {}
        hide_read_before = timezone.now() - timedelta(days=1)

        notifications = []

        for item in announcements_qs:
            key = self._notification_key("announcement", item.id)
            read_at = read_map.get(key)
            notifications.append(
                {
                    "id": key,
                    "source": "announcement",
                    "source_id": item.id,
                    "title": item.title or "Announcement",
                    "body": item.body or "",
                    "class_name": _notification_class_label(class_name=item.class_name, student=item.student),
                    "published_at": item.published_at,
                    "read": read_at is not None,
                    "read_at": read_at,
                }
            )

        for item in homework_qs:
            key = self._notification_key("homework", item.id)
            read_at = read_map.get(key)
            notifications.append(
                {
                    "id": key,
                    "source": "homework",
                    "source_id": item.id,
                    "title": item.title or "Homework posted",
                    "body": item.description or "",
                    "class_name": _notification_class_label(class_name=item.class_name, student=item.student),
                    "published_at": item.assigned_date,
                    "read": read_at is not None,
                    "read_at": read_at,
                }
            )

        for item in fees_qs:
            key = self._notification_key("fees", item.id)
            read_at = read_map.get(key)
            notifications.append(
                {
                    "id": key,
                    "source": "fees",
                    "source_id": item.id,
                    "title": item.title or "Fee update",
                    "body": item.notes or "",
                    "published_at": item.due_date,
                    "read": read_at is not None,
                    "read_at": read_at,
                }
            )

        for item in transport_qs:
            key = self._notification_key("transport", item.id)
            read_at = read_map.get(key)
            notifications.append(
                {
                    "id": key,
                    "source": "transport",
                    "source_id": item.id,
                    "title": item.route_name or "Transport update",
                    "body": item.description or item.tracking_note or "",
                    "published_at": item.updated_at or item.created_at,
                    "read": read_at is not None,
                    "read_at": read_at,
                }
            )

        for item in events_qs:
            key = self._notification_key("event", item.id)
            read_at = read_map.get(key)
            notifications.append(
                {
                    "id": key,
                    "source": "event",
                    "source_id": item.id,
                    "title": item.title or "New event",
                    "body": strip_event_video_links(item.description) or "",
                    "published_at": item.start_date or item.end_date,
                    "read": read_at is not None,
                    "read_at": read_at,
                }
            )

        for item in achievements_qs:
            key = self._notification_key("achievement", item.id)
            read_at = read_map.get(key)
            notifications.append(
                {
                    "id": key,
                    "source": "achievement",
                    "source_id": item.id,
                    "title": item.title or "Achievement update",
                    "body": item.notes or "",
                    "published_at": item.achieved_date,
                    "read": read_at is not None,
                    "read_at": read_at,
                }
            )

        for item in attendance_qs:
            key = self._notification_key("attendance", item.id)
            read_at = read_map.get(key)
            notifications.append(
                {
                    "id": key,
                    "source": "attendance",
                    "source_id": item.id,
                    "title": f"Attendance: {item.status or 'Updated'}",
                    "body": item.note or "",
                    "published_at": item.date,
                    "read": read_at is not None,
                    "read_at": read_at,
                }
            )

        for item in parental_tips_qs:
            key = self._notification_key("parental_tip", item.id)
            read_at = read_map.get(key)
            targets = [str(c).strip() for c in (item.target_class_names or []) if str(c).strip()]
            class_label = ", ".join(targets) if targets else ""
            notifications.append(
                {
                    "id": key,
                    "source": "parental_tip",
                    "source_id": item.id,
                    "title": item.title or "New parental tip",
                    "body": (item.description or "").strip(),
                    "class_name": class_label or None,
                    "published_at": item.updated_at or item.created_at,
                    "read": read_at is not None,
                    "read_at": read_at,
                    "action_path": "/dashboard/parent/parental-tips",
                }
            )

        notifications = [
            n for n in notifications if (not n["read"]) or (n.get("read_at") and n["read_at"] >= hide_read_before)
        ]
        notifications.sort(
            key=lambda x: x.get("published_at").isoformat() if x.get("published_at") else "",
            reverse=True,
        )
        unread_count = sum(1 for n in notifications if not n["read"])

        from documents.serializers import ParentDocumentSerializer

        return Response(
            {
                "announcements": AnnouncementSerializer(announcements_qs, many=True).data,
                "homework": HomeworkAssignmentSerializer(homework_qs, many=True).data,
                "fees": FeeRecordSerializer(fees_qs, many=True).data,
                "transport": ParentTransportRouteSerializer(transport_qs, many=True).data,
                "events": EventSerializer(events_qs, many=True).data,
                "achievements": ParentStudentAchievementSerializer(achievements_qs, many=True).data,
                "attendance": AttendanceRecordSerializer(attendance_qs, many=True).data,
                "parental_tips": ParentDocumentSerializer(
                    parental_tips_qs,
                    many=True,
                    context={"request": request, "merge_holiday_for_parent": True},
                ).data,
                "notifications": notifications,
                "unread_count": unread_count,
            }
        )


class ParentNotificationReadView(APIView):
    """Mark a parent notification as read."""

    permission_classes = [IsParentUser]

    def post(self, request):
        pp = resolved_parent_profile_for_user(request.user)
        if not pp:
            return Response({"detail": "Parent profile not found"}, status=404)

        notification_id = ""
        # Accept JSON, form-data, or raw body to avoid 415 parser issues.
        try:
            if hasattr(request, "data") and isinstance(request.data, dict):
                notification_id = str(request.data.get("notification_id") or "").strip()
        except Exception:
            notification_id = ""

        if not notification_id:
            try:
                raw = (request.body or b"").decode("utf-8").strip()
                if raw:
                    payload = json.loads(raw)
                    if isinstance(payload, dict):
                        notification_id = str(payload.get("notification_id") or "").strip()
            except Exception:
                notification_id = ""

        if not notification_id:
            notification_id = str(request.POST.get("notification_id") or "").strip()

        if not notification_id:
            return Response({"detail": "notification_id is required"}, status=400)

        try:
            ParentNotificationRead.objects.get_or_create(
                parent=pp,
                notification_key=notification_id,
            )
        except (ProgrammingError, OperationalError):
            return Response({"ok": False, "detail": "Notification read table not ready"}, status=503)
        unread_count = 0
        try:
            payload = ParentNotificationsView().get(request).data
            if isinstance(payload, dict):
                unread_count = int(payload.get("unread_count", 0) or 0)
        except Exception:
            unread_count = 0
        return Response({"ok": True, "notification_id": notification_id, "unread_count": unread_count})


# ----- Franchise (full CRUD) -----


class FranchiseHomeworkListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = HomeworkAssignmentSerializer
    pagination_class = None
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return HomeworkAssignment.objects.none()
        qs = HomeworkAssignment.objects.filter(franchise=f).select_related("student").order_by("-assigned_date")
        date_str = (self.request.query_params.get("assigned_date") or "").strip()
        if date_str:
            parsed = parse_date(date_str)
            if parsed is not None:
                qs = qs.filter(assigned_date=parsed)
            else:
                qs = qs.none()
        return qs

    def get_serializer_context(self):
        c = super().get_serializer_context()
        c["request"] = self.request
        return c

    def perform_create(self, serializer):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            raise PermissionDenied("Franchise profile not found")
        serializer.save(franchise=f)


class FranchiseHomeworkDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = HomeworkAssignmentSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return HomeworkAssignment.objects.none()
        return HomeworkAssignment.objects.filter(franchise=f).select_related("student")

    def get_serializer_context(self):
        c = super().get_serializer_context()
        c["request"] = self.request
        return c


def _after_announcement_saved(announcement: Announcement) -> None:
    """Reset or dispatch parent emails after create/update."""
    if announcement.published_at > timezone.now():
        Announcement.objects.filter(pk=announcement.pk).update(email_dispatched_at=None)
        return
    if announcement.email_dispatched_at:
        return

    pk = announcement.pk

    def _email_parents() -> None:
        from students.emails import notify_parents_new_announcement_by_id

        notify_parents_new_announcement_by_id(pk)

    transaction.on_commit(lambda: threading.Thread(target=_email_parents, daemon=True).start())


class FranchiseAnnouncementListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = AnnouncementSerializer
    pagination_class = None

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return Announcement.objects.none()
        qs = (
            Announcement.objects.filter(franchise=f, visible_to_parents=True)
            .select_related("student", "campaign")
            .order_by("-published_at")
        )
        date_str = (self.request.query_params.get("published_date") or "").strip()
        if date_str:
            parsed = parse_date(date_str)
            if parsed is not None:
                qs = qs.filter(announcement_on_schedule_date_q(parsed))
            else:
                qs = qs.none()
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_create(self, serializer):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            raise PermissionDenied("Franchise profile not found")
        announcement = serializer.save(
            franchise=f,
            visible_to_parents=True,
            visible_to_centres=False,
        )
        _after_announcement_saved(announcement)


class FranchiseAnnouncementDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return Announcement.objects.none()
        return Announcement.objects.filter(franchise=f).select_related("student")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_update(self, serializer):
        if serializer.instance.campaign_id:
            raise PermissionDenied("Head-office notifications cannot be edited at the centre.")
        announcement = serializer.save()
        _after_announcement_saved(announcement)


class AdminAnnouncementCampaignListCreateView(generics.ListCreateAPIView):
    """Head office: publish notifications to parents and/or centre inboxes."""

    permission_classes = [IsAdminUser]
    serializer_class = AdminAnnouncementCampaignSerializer
    pagination_class = None

    def get_queryset(self):
        return AnnouncementCampaign.objects.select_related("franchise", "student").order_by("-published_at")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class AdminAnnouncementCampaignDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminAnnouncementCampaignSerializer
    queryset = AnnouncementCampaign.objects.select_related("franchise", "student")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


def _franchise_ho_inbox_announcement_qs(franchise):
    """Head-office campaigns only — not centre-authored parent notifications."""
    return (
        Announcement.objects.filter(
            franchise=franchise,
            is_active=True,
            visible_to_centres=True,
            campaign_id__isnull=False,
        )
        .filter(parent_visible_announcement_q())
        .select_related("student", "campaign")
        .order_by("-published_at")
    )


def _franchise_support_ticket_reminder_qs(franchise):
    """Tickets head office reminded this centre to action (shown in centre inbox)."""
    return (
        SupportTicket.objects.filter(
            parent__franchise=franchise,
            ho_reminded_at__isnull=False,
        )
        .exclude(status=SupportTicket.Status.CLOSED)
        .select_related("parent", "parent__user", "student")
        .order_by("-ho_reminded_at")
    )


def _franchise_inbox_unread_count(franchise, read_keys: set[str] | None = None) -> int:
    if read_keys is None:
        read_keys = set(
            FranchiseNotificationRead.objects.filter(franchise=franchise).values_list(
                "notification_key", flat=True
            )
        )

    def _key(source: str, item_id: int) -> str:
        return f"{source}-{item_id}"

    unread = 0
    for ann_id in _franchise_ho_inbox_announcement_qs(franchise).values_list("pk", flat=True):
        if _key("head_office", ann_id) not in read_keys:
            unread += 1
    for ticket_id in _franchise_support_ticket_reminder_qs(franchise).values_list("pk", flat=True):
        if _key("support_ticket", ticket_id) not in read_keys:
            unread += 1
    return unread


class FranchiseNotificationsView(APIView):
    """Centre inbox: HO campaigns and support-ticket reminders from head office."""

    permission_classes = [IsFranchiseUser]

    @staticmethod
    def _notification_key(source: str, item_id: int) -> str:
        return f"{source}-{item_id}"

    def get(self, request):
        franchise = franchise_profile_for_user(request.user)
        if not franchise:
            return Response({"notifications": [], "unread_count": 0})

        read_map = {
            row["notification_key"]: row["read_at"]
            for row in FranchiseNotificationRead.objects.filter(franchise=franchise).values(
                "notification_key", "read_at"
            )
        }

        notifications = []
        for item in _franchise_ho_inbox_announcement_qs(franchise):
            key = self._notification_key("head_office", item.id)
            read_at = read_map.get(key)
            if item.visible_to_parents:
                action_path = "/dashboard/franchise/parent-portal/?tab=notifications"
            else:
                action_path = "/dashboard/franchise/notifications/"
            notifications.append(
                {
                    "id": item.id,
                    "source": "head_office",
                    "source_id": item.id,
                    "title": item.title or "Notification",
                    "body": item.body or "",
                    "action_path": action_path,
                    "visible_to_parents": item.visible_to_parents,
                    "read": read_at is not None,
                    "read_at": read_at,
                    "created_at": item.published_at,
                }
            )

        for ticket in _franchise_support_ticket_reminder_qs(franchise):
            key = self._notification_key("support_ticket", ticket.id)
            read_at = read_map.get(key)
            subject = (ticket.subject or "").strip() or "Parent support ticket"
            body = (ticket.ho_reminder_message or "").strip()
            if not body:
                body = "Head office has asked your centre to review and respond to this parent support ticket."
            notifications.append(
                {
                    "id": ticket.id,
                    "source": "support_ticket",
                    "source_id": ticket.id,
                    "title": f"Action required: {subject}",
                    "body": body,
                    "action_path": "/dashboard/franchise/parent-tickets/",
                    "read": read_at is not None,
                    "read_at": read_at,
                    "created_at": ticket.ho_reminded_at,
                }
            )

        notifications.sort(
            key=lambda row: (
                row.get("created_at").timestamp()
                if row.get("created_at") is not None and hasattr(row.get("created_at"), "timestamp")
                else 0
            ),
            reverse=True,
        )

        read_keys = set(read_map.keys())
        unread_count = _franchise_inbox_unread_count(franchise, read_keys)
        return Response({"notifications": notifications, "unread_count": unread_count})


class FranchiseNotificationReadView(APIView):
    permission_classes = [IsFranchiseUser]

    def post(self, request):
        franchise = franchise_profile_for_user(request.user)
        if not franchise:
            return Response({"detail": "Franchise profile not found"}, status=404)

        notification_id = request.data.get("notification_id") if isinstance(request.data, dict) else None
        source = (request.data.get("source") if isinstance(request.data, dict) else None) or "head_office"
        source = str(source).strip().lower()
        try:
            pk = int(notification_id)
        except (TypeError, ValueError):
            return Response({"detail": "notification_id is required"}, status=400)

        if source == "support_ticket":
            exists = _franchise_support_ticket_reminder_qs(franchise).filter(pk=pk).exists()
        elif source == "head_office":
            exists = _franchise_ho_inbox_announcement_qs(franchise).filter(pk=pk).exists()
        else:
            return Response({"detail": "Invalid source"}, status=400)

        if not exists:
            return Response({"detail": "Notification not found"}, status=404)

        key = FranchiseNotificationsView._notification_key(source, pk)
        FranchiseNotificationRead.objects.update_or_create(
            franchise=franchise,
            notification_key=key,
            defaults={},
        )
        read_keys = set(
            FranchiseNotificationRead.objects.filter(franchise=franchise).values_list("notification_key", flat=True)
        )
        unread_count = _franchise_inbox_unread_count(franchise, read_keys)
        return Response({"ok": True, "unread_count": unread_count})


@api_view(["GET"])
@permission_classes([AllowAny])
def cron_dispatch_scheduled_announcements(request):
    """Send emails for announcements whose scheduled publish time has arrived."""
    import os

    cron_secret = (os.getenv("CRON_SECRET") or "").strip()
    auth_header = (request.headers.get("Authorization") or "").strip()
    if cron_secret:
        if auth_header != f"Bearer {cron_secret}":
            return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
    elif os.getenv("DJANGO_DEBUG", "").lower() not in ("1", "true", "yes"):
        return Response({"detail": "CRON_SECRET not configured"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    from students.emails import dispatch_due_announcement_emails

    sent = dispatch_due_announcement_emails()
    return Response({"ok": True, "emails_sent": sent})


def _attendance_month_bounds(month_str: str):
    """``YYYY-MM`` → (first day, last day) inclusive."""
    from datetime import date

    parts = (month_str or "").strip().split("-")
    if len(parts) != 2:
        return None, None
    try:
        year_i = int(parts[0])
        mon_i = int(parts[1])
        if mon_i < 1 or mon_i > 12:
            return None, None
        start = date(year_i, mon_i, 1)
        if mon_i == 12:
            end = date(year_i + 1, 1, 1)
        else:
            end = date(year_i, mon_i + 1, 1)
        return start, end
    except (TypeError, ValueError):
        return None, None


def _student_matches_academic_year_filter(student, academic_year: str) -> bool:
    """True when a student belongs to the selected academic year (strict roster)."""
    ay = (academic_year or "").strip()
    if not ay or ay.lower() == "all":
        return True
    suffix_match = re.search(r"(\d{2})-(\d{2})\s*$", ay.replace("AY ", "").strip())
    if not suffix_match:
        return True
    suffix = f"{suffix_match.group(1)}-{suffix_match.group(2)}"
    cn = (student.class_name or "").strip()
    if suffix in cn:
        return True
    yr = (getattr(student, "Year", None) or "").strip()
    if not yr:
        return False
    yr_norm = yr.lower().replace(" ", "").replace("ay", "")
    ay_norm = ay.lower().replace(" ", "").replace("ay", "")
    if ay_norm and (ay_norm in yr_norm or yr_norm == ay_norm):
        return True
    y1, y2 = int(suffix_match.group(1)), int(suffix_match.group(2))
    for token in (f"{2000 + y1}-{2000 + y2}", f"{y1}-{y2}"):
        token_norm = token.lower().replace(" ", "")
        if token_norm in yr_norm or yr_norm == token_norm:
            return True
    return False


def _franchise_attendance_student_ids_for_class(
    franchise, class_name: str, academic_year: str = ""
) -> list[int]:
    """Student ids at this centre whose class + year match the attendance filters."""
    target = (class_name or "").strip()
    if not target:
        return []
    ids: list[int] = []
    for student in StudentProfile.objects.filter(parent__franchise=franchise, is_active=True).only(
        "id", "class_name", "Year"
    ):
        if not _class_label_matches(student.class_name, target):
            continue
        if not _student_matches_academic_year_filter(student, academic_year):
            continue
        ids.append(student.pk)
    return ids


class FranchiseAttendanceListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = AttendanceRecordSerializer
    pagination_class = None

    def get_serializer_class(self):
        if self.request.method == "POST":
            return FranchiseAttendanceUpsertSerializer
        return AttendanceRecordSerializer

    def create(self, request, *args, **kwargs):
        """Create or update attendance for student+date (franchise save is idempotent)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = serializer.validated_data["student"]
        date = serializer.validated_data["date"]
        record, _created = AttendanceRecord.objects.update_or_create(
            student=student,
            date=date,
            defaults={
                "status": serializer.validated_data["status"],
                "note": serializer.validated_data.get("note") or "",
            },
        )
        out = AttendanceRecordSerializer(record, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_200_OK)

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return AttendanceRecord.objects.none()

        queryset = AttendanceRecord.objects.filter(student__parent__franchise=f)

        params = self.request.query_params
        month_str = (params.get("month") or "").strip()
        from_str = (params.get("from") or "").strip()
        to_str = (params.get("to") or "").strip()
        date_str = (params.get("date") or "").strip()

        if month_str:
            month_start, month_end = _attendance_month_bounds(month_str)
            if month_start is not None and month_end is not None:
                queryset = queryset.filter(date__gte=month_start, date__lt=month_end)
            else:
                queryset = queryset.none()
        elif from_str and to_str:
            from_date = parse_date(from_str)
            to_date = parse_date(to_str)
            if from_date is not None and to_date is not None:
                queryset = queryset.filter(date__gte=from_date, date__lte=to_date)
            else:
                queryset = queryset.none()
        elif date_str:
            parsed = parse_date(date_str)
            if parsed is not None:
                queryset = queryset.filter(date=parsed)
            else:
                queryset = queryset.none()

        class_name = (params.get("class_name") or params.get("class") or "").strip()
        academic_year = (params.get("academic_year") or params.get("year") or "").strip()
        if class_name:
            student_ids = _franchise_attendance_student_ids_for_class(f, class_name, academic_year)
            queryset = queryset.filter(student_id__in=student_ids or [-1])
        elif academic_year and academic_year.lower() != "all":
            student_ids = [
                s.pk
                for s in StudentProfile.objects.filter(parent__franchise=f, is_active=True).only(
                    "id", "class_name", "Year"
                )
                if _student_matches_academic_year_filter(s, academic_year)
            ]
            queryset = queryset.filter(student_id__in=student_ids or [-1])

        return queryset.select_related("student", "student__parent").order_by("-date", "student_id")

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        rows = serializer.data
        franchise = franchise_profile_for_user(request.user)
        params = request.query_params
        date_str = (params.get("date") or "").strip()
        month_str = (params.get("month") or "").strip()
        student_id = (params.get("student_id") or params.get("student") or "").strip()

        from students.attendance_logic import (
            build_month_summary_for_student,
            collect_holiday_map,
            day_is_holiday,
            holiday_dates_payload,
            month_bounds,
        )

        payload: dict = {"attendance": rows, "count": len(rows)}

        if franchise and date_str:
            parsed = parse_date(date_str)
            if parsed is not None:
                is_holiday, label = day_is_holiday(franchise, parsed)
                payload["day_info"] = {
                    "date": date_str,
                    "is_holiday": is_holiday,
                    "holiday_label": label,
                }

        if franchise and month_str and student_id.isdigit():
            student = StudentProfile.objects.filter(
                pk=int(student_id),
                parent__franchise=franchise,
                is_active=True,
            ).first()
            if student:
                summary = build_month_summary_for_student(student, franchise, month_str)
                if summary:
                    payload["attendance_summary"] = summary
                start, end = month_bounds(month_str)
                if start is not None and end is not None:
                    payload["holiday_dates"] = holiday_dates_payload(
                        collect_holiday_map(franchise, start, end)
                    )

        if (params.get("wrap") or "").strip().lower() in ("list", "array"):
            return Response(rows)
        return Response(payload)

    def get_serializer_context(self):
        c = super().get_serializer_context()
        c["request"] = self.request
        return c


class FranchiseAttendanceBulkUpsertView(APIView):
    """Save many attendance rows in one request (create or update by student+date)."""

    permission_classes = [IsFranchiseUser]

    def post(self, request):
        serializer = FranchiseAttendanceBulkSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        rows = serializer.validated_data["records"]
        if not rows:
            return Response({"saved": 0}, status=status.HTTP_200_OK)

        student_ids = [row["student"].pk for row in rows]
        dates = {row["date"] for row in rows}
        existing_map: dict[tuple[int, object], AttendanceRecord] = {}
        if len(dates) == 1:
            only_date = next(iter(dates))
            for record in AttendanceRecord.objects.filter(student_id__in=student_ids, date=only_date):
                existing_map[(record.student_id, record.date)] = record

        to_update: list[AttendanceRecord] = []
        to_create: list[AttendanceRecord] = []
        for row in rows:
            student = row["student"]
            date = row["date"]
            status_value = row["status"]
            note = row.get("note") or ""
            key = (student.pk, date)
            existing = existing_map.get(key)
            if existing is not None:
                existing.status = status_value
                existing.note = note
                to_update.append(existing)
            else:
                to_create.append(
                    AttendanceRecord(
                        student=student,
                        date=date,
                        status=status_value,
                        note=note,
                    )
                )

        with transaction.atomic():
            if to_update:
                AttendanceRecord.objects.bulk_update(to_update, ["status", "note"])
            if to_create:
                AttendanceRecord.objects.bulk_create(to_create, ignore_conflicts=True)

        return Response({"saved": len(rows)}, status=status.HTTP_200_OK)


class FranchiseAttendanceClearDateView(APIView):
    """Remove all saved attendance rows at this centre for one date."""

    permission_classes = [IsFranchiseUser]

    def delete(self, request):
        franchise = franchise_profile_for_user(request.user)
        if not franchise:
            return Response({"detail": "Franchise profile not found"}, status=404)

        date_str = (request.query_params.get("date") or "").strip()
        parsed = parse_date(date_str)
        if parsed is None:
            return Response({"detail": "A valid date query param is required (YYYY-MM-DD)."}, status=400)

        deleted, _details = (
            AttendanceRecord.objects.filter(student__parent__franchise=franchise, date=parsed).delete()
        )
        return Response({"deleted": deleted, "date": date_str}, status=status.HTTP_200_OK)


class FranchiseAttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = AttendanceRecordSerializer

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return AttendanceRecord.objects.none()
        return AttendanceRecord.objects.filter(student__parent__franchise=f).select_related("student")

    def get_serializer_context(self):
        c = super().get_serializer_context()
        c["request"] = self.request
        return c


class FranchiseAttendanceClosedDayListCreateView(generics.ListCreateAPIView):
    """Centre-declared special holidays (rain closure, summer break, local holiday, etc.)."""

    permission_classes = [IsFranchiseUser]
    serializer_class = CentreAttendanceClosedDaySerializer
    pagination_class = None

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return CentreAttendanceClosedDay.objects.none()
        qs = CentreAttendanceClosedDay.objects.filter(franchise=franchise).order_by("-date")
        month_str = (self.request.query_params.get("month") or "").strip()
        if month_str:
            start, end = _attendance_month_bounds(month_str)
            if start is not None and end is not None:
                qs = qs.filter(date__gte=start, date__lt=end)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class FranchiseAttendanceClosedDayDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = CentreAttendanceClosedDaySerializer

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return CentreAttendanceClosedDay.objects.none()
        return CentreAttendanceClosedDay.objects.filter(franchise=franchise)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class FranchiseAttendanceHolidaysView(APIView):
    """
    Merged holiday calendar for a centre month: weekends + HO/state holiday CMS + centre CMS + special closed days.
    Used by centre Parent App calendar and attendance.
    """

    permission_classes = [IsFranchiseUser]

    def get(self, request):
        from students.attendance_logic import collect_holiday_map, holiday_dates_payload, month_bounds

        franchise = franchise_profile_for_user(request.user)
        month_str = (request.query_params.get("month") or date.today().strftime("%Y-%m")).strip()
        if not franchise:
            return Response({"month": month_str, "holiday_dates": []})

        start, end = month_bounds(month_str)
        if start is None or end is None:
            return Response(
                {"detail": "Invalid month. Use YYYY-MM."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        holiday_map = collect_holiday_map(franchise, start, end)
        return Response(
            {
                "month": month_str,
                "holiday_dates": holiday_dates_payload(holiday_map),
                "includes_weekends": True,
            }
        )


class FranchiseFeeListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = FeeRecordSerializer
    pagination_class = None

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return FeeRecord.objects.none()
        return FeeRecord.objects.filter(student__parent__franchise=f).select_related("student").order_by("-due_date")

    def get_serializer_context(self):
        c = super().get_serializer_context()
        c["request"] = self.request
        return c

    def create(self, request, *args, **kwargs):
        from students.legacy_fee_service import legacy_fee_db_configured

        if legacy_fee_db_configured():
            return Response(
                {
                    "detail": (
                        "Fee amounts are loaded from TiKES. Select a student on the Fees tab "
                        "and update status only."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)


class FranchiseFeeSummaryView(APIView):
    """Centre fee view — TiKES amounts with optional centre status overrides."""

    permission_classes = [IsFranchiseUser]

    def get(self, request):
        from students.fee_summary import build_fee_summary_from_records, merge_centre_status_overrides
        from students.legacy_fee_service import fetch_legacy_fee_summary, legacy_fee_db_configured

        franchise = franchise_profile_for_user(request.user)
        if not franchise:
            return Response({"detail": "Franchise profile not found"}, status=status.HTTP_404_NOT_FOUND)

        student_id = (request.query_params.get("student_id") or request.query_params.get("student") or "").strip()
        if not student_id:
            return Response({"detail": "student_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            sid = int(student_id)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid student_id"}, status=status.HTTP_400_BAD_REQUEST)

        student = students_at_franchise(franchise).filter(pk=sid).first()
        if not student:
            return Response({"detail": "Student not found at your centre"}, status=status.HTTP_404_NOT_FOUND)

        centre_name = (franchise.name or "").strip() or (student.Centre or "").strip()
        id_card_no = (student.Idcardno or "").strip()
        legacy_summary = None
        legacy_lookup_error = ""
        if id_card_no and legacy_fee_db_configured():
            legacy_summary, legacy_lookup_error = fetch_legacy_fee_summary(id_card_no)

        summary = legacy_summary or build_fee_summary_from_records(student, centre_name=centre_name)
        summary = merge_centre_status_overrides(student, summary)
        summary["legacy_configured"] = legacy_fee_db_configured()
        summary["student_id"] = student.id
        if legacy_lookup_error and not summary.get("lines"):
            summary["lookup_message"] = legacy_lookup_error
        elif not summary.get("lines") and legacy_fee_db_configured() and id_card_no:
            summary["lookup_message"] = (
                f"TiKES is connected but fee_payment has no active records for ID card {id_card_no}."
            )
        return Response(summary)


class FranchiseFeeLineStatusView(APIView):
    """Centre may update status (and optional paid_on / notes) for one TiKES fee line."""

    permission_classes = [IsFranchiseUser]

    def patch(self, request):
        from students.fee_summary import (
            build_fee_summary_from_records,
            fee_record_defaults_from_summary_line,
        )
        from students.legacy_fee_service import fetch_legacy_fee_summary, legacy_fee_db_configured

        franchise = franchise_profile_for_user(request.user)
        if not franchise:
            return Response({"detail": "Franchise profile not found"}, status=status.HTTP_404_NOT_FOUND)

        student_id = request.data.get("student") or request.data.get("student_id")
        line_serial = request.data.get("line_serial")
        status_val = (request.data.get("status") or "").strip().upper()
        if not student_id:
            return Response({"detail": "student is required"}, status=status.HTTP_400_BAD_REQUEST)
        if line_serial is None:
            return Response({"detail": "line_serial is required"}, status=status.HTTP_400_BAD_REQUEST)
        if status_val not in FeeRecord.Status.values:
            return Response({"detail": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sid = int(student_id)
            serial = int(line_serial)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid student or line_serial"}, status=status.HTTP_400_BAD_REQUEST)

        student = students_at_franchise(franchise).filter(pk=sid).first()
        if not student:
            return Response({"detail": "Student not found at your centre"}, status=status.HTTP_404_NOT_FOUND)

        centre_name = (franchise.name or "").strip() or (student.Centre or "").strip()
        id_card_no = (student.Idcardno or "").strip()
        summary = None
        if id_card_no and legacy_fee_db_configured():
            summary, _err = fetch_legacy_fee_summary(id_card_no)
        if not summary or not summary.get("lines"):
            summary = build_fee_summary_from_records(student, centre_name=centre_name)

        line = next(
            (row for row in (summary.get("lines") or []) if int(row.get("serial") or 0) == serial),
            None,
        )
        if not line:
            return Response({"detail": "Fee line not found for this student"}, status=status.HTTP_404_NOT_FOUND)

        defaults = fee_record_defaults_from_summary_line(student, summary, line)
        defaults["status"] = status_val
        paid_on_raw = request.data.get("paid_on")
        if paid_on_raw:
            parsed_paid = parse_date(str(paid_on_raw))
            if not parsed_paid:
                return Response({"detail": "Invalid paid_on date"}, status=status.HTTP_400_BAD_REQUEST)
            defaults["paid_on"] = parsed_paid
        elif status_val == FeeRecord.Status.PAID:
            defaults["paid_on"] = date.today()
        else:
            defaults["paid_on"] = None
        defaults["notes"] = (request.data.get("notes") or "").strip()

        record, _created = FeeRecord.objects.update_or_create(
            student=student,
            source=FeeRecord.Source.TIKES,
            line_serial=serial,
            defaults=defaults,
        )
        serializer = FeeRecordSerializer(record, context={"request": request})
        return Response(serializer.data)


class FranchiseFeeDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = FeeRecordSerializer

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return FeeRecord.objects.none()
        return FeeRecord.objects.filter(student__parent__franchise=f).select_related("student")

    def get_serializer_context(self):
        c = super().get_serializer_context()
        c["request"] = self.request
        return c

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.source == FeeRecord.Source.TIKES:
            allowed = {"status", "paid_on", "notes"}
            data = {k: v for k, v in request.data.items() if k in allowed}
            if not data:
                return Response(
                    {"detail": "TiKES fee lines only allow status, paid_on, and notes updates."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer = self.get_serializer(instance, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        return super().partial_update(request, *args, **kwargs)


class FranchiseTransportListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = TransportRouteSerializer
    pagination_class = None

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return TransportRoute.objects.none()
        return TransportRoute.objects.filter(franchise=f).order_by("sort_order", "route_name")

    def perform_create(self, serializer):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            raise PermissionDenied("Franchise profile not found")
        serializer.save(franchise=f)


class FranchiseTransportDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = TransportRouteSerializer

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return TransportRoute.objects.none()
        return TransportRoute.objects.filter(franchise=f)


class FranchiseTransportAssignmentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = StudentTransportAssignmentSerializer
    pagination_class = None

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return StudentTransportAssignment.objects.none()
        return StudentTransportAssignment.objects.filter(route__franchise=f).select_related("student", "route")

    def get_serializer_context(self):
        c = super().get_serializer_context()
        c["request"] = self.request
        return c


class FranchiseTransportAssignmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = StudentTransportAssignmentSerializer

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return StudentTransportAssignment.objects.none()
        return StudentTransportAssignment.objects.filter(route__franchise=f).select_related("student", "route")

    def get_serializer_context(self):
        c = super().get_serializer_context()
        c["request"] = self.request
        return c


class FranchiseSupportTicketListView(generics.ListAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = SupportTicketFranchiseSerializer
    pagination_class = None

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return SupportTicket.objects.none()
        return SupportTicket.objects.filter(parent__franchise=f).select_related("parent", "parent__user", "student").order_by("-created_at")


class FranchiseSupportTicketDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = SupportTicketFranchiseSerializer

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return SupportTicket.objects.none()
        qs = SupportTicket.objects.filter(parent__franchise=f).select_related("parent", "parent__user", "student")
        return qs


class AdminSupportTicketListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = SupportTicketAdminSerializer
    pagination_class = None

    def get_queryset(self):
        qs = (
            SupportTicket.objects.select_related(
                "parent",
                "parent__franchise",
                "parent__user",
                "student",
            )
            .order_by("-created_at")
        )

        franchise_id = (self.request.query_params.get("franchise") or "").strip()
        if franchise_id.isdigit():
            qs = qs.filter(parent__franchise_id=int(franchise_id))

        status = (self.request.query_params.get("status") or "").strip().upper()
        if status == "RESOLVED":
            status = SupportTicket.Status.CLOSED
        if status in (
            SupportTicket.Status.OPEN,
            SupportTicket.Status.IN_PROGRESS,
            SupportTicket.Status.CLOSED,
        ):
            qs = qs.filter(status=status)

        if (self.request.query_params.get("unresolved") or "").lower() in ("1", "true", "yes"):
            qs = qs.exclude(status=SupportTicket.Status.CLOSED)

        return qs


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_remind_support_ticket_centre(request, pk):
    ticket = get_object_or_404(
        SupportTicket.objects.select_related(
            "parent",
            "parent__franchise",
            "parent__user",
            "parent__franchise__user",
            "student",
        ),
        pk=pk,
    )

    message = ""
    if isinstance(request.data, dict):
        message = (request.data.get("message") or "").strip()

    default_message = (
        "Head office has asked your centre to review and respond to this parent support ticket."
    )
    ticket.ho_reminder_message = message or default_message
    ticket.ho_reminded_at = timezone.now()
    ticket.save(update_fields=["ho_reminder_message", "ho_reminded_at", "updated_at"])

    from students.emails import send_support_ticket_centre_reminder

    emailed = send_support_ticket_centre_reminder(ticket)

    if emailed:
        detail = "Centre notified in Centre inbox and by email."
    elif ticket.ho_reminded_at:
        detail = "Reminder saved — centre will see it in Centre inbox and Parent Support. Email was not sent (check SendGrid or centre contact email)."
    else:
        detail = "Could not notify centre."

    return Response({"detail": detail, "centre_emailed": emailed})


def _route_from_driver_token(token):
    return TransportRoute.objects.filter(driver_token=token).select_related("franchise").first()


@api_view(["GET"])
@permission_classes([AllowAny])
def driver_route_detail(request, token):
    route = _route_from_driver_token(token)
    if not route:
        return Response({"detail": "Invalid driver link"}, status=404)
    live_trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
    assignments = route.student_assignments.filter(is_active=True).select_related("student").order_by(
        "pickup_time",
        "student__first_name",
    )
    status_map = {}
    if live_trip:
        status_map = {
            row.student_id: row
            for row in live_trip.student_statuses.filter(student__in=[a.student for a in assignments]).select_related("student")
        }
    return Response(
        {
            "route": TransportRouteSerializer(route).data,
            "active_trip": TransportTripSerializer(live_trip).data if live_trip else None,
            "assigned_students": [
                {
                    "assignment_id": assignment.id,
                    "student_id": assignment.student_id,
                    "student_name": assignment.student.full_name,
                    "class_name": assignment.student.class_name,
                    "pickup_stop": assignment.pickup_stop,
                    "drop_stop": assignment.drop_stop,
                    "pickup_time": assignment.pickup_time,
                    "drop_time": assignment.drop_time,
                    "status": status_map.get(assignment.student_id).status if assignment.student_id in status_map else "WAITING",
                    "status_note": status_map.get(assignment.student_id).note if assignment.student_id in status_map else "",
                }
                for assignment in assignments
            ],
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def driver_start_trip(request, token):
    route = _route_from_driver_token(token)
    if not route:
        return Response({"detail": "Invalid driver link"}, status=404)
    trip_type = str(request.data.get("trip_type") or TransportTrip.TripType.PICKUP).upper()
    if trip_type not in TransportTrip.TripType.values:
        trip_type = TransportTrip.TripType.PICKUP

    route.trips.filter(status=TransportTrip.Status.LIVE).update(
        status=TransportTrip.Status.COMPLETED,
        completed_at=timezone.now(),
    )
    trip = TransportTrip.objects.create(
        route=route,
        trip_type=trip_type,
        status=TransportTrip.Status.LIVE,
        started_at=timezone.now(),
    )
    return Response(TransportTripSerializer(trip).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def driver_post_location(request, token):
    route = _route_from_driver_token(token)
    if not route:
        return Response({"detail": "Invalid driver link"}, status=404)
    trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
    if not trip:
        return Response({"detail": "Start a trip before sending location."}, status=400)

    try:
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        if latitude is None or longitude is None:
            raise ValueError("Missing coordinates")
        location = TransportTripLocation.objects.create(
            trip=trip,
            latitude=latitude,
            longitude=longitude,
            speed=request.data.get("speed"),
            heading=request.data.get("heading"),
            accuracy=request.data.get("accuracy"),
        )
    except Exception:
        return Response({"detail": "Valid latitude and longitude are required."}, status=400)
    return Response(TransportTripLocationSerializer(location).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def driver_complete_trip(request, token):
    route = _route_from_driver_token(token)
    if not route:
        return Response({"detail": "Invalid driver link"}, status=404)
    trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
    if not trip:
        return Response({"detail": "No live trip found."}, status=404)
    trip.status = TransportTrip.Status.COMPLETED
    trip.completed_at = timezone.now()
    trip.is_gps_active = False
    trip.save(update_fields=["status", "completed_at", "is_gps_active", "updated_at"])
    return Response(TransportTripSerializer(trip).data)


@api_view(["POST"])
@permission_classes([AllowAny])
def driver_toggle_gps(request, token):
    route = _route_from_driver_token(token)
    if not route:
        return Response({"detail": "Invalid driver link"}, status=404)
    trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
    if not trip:
        return Response({"detail": "No live trip found"}, status=400)
    
    active = request.data.get("active", True)
    trip.is_gps_active = bool(active)
    trip.save(update_fields=["is_gps_active", "updated_at"])
    return Response({"is_gps_active": trip.is_gps_active})


@api_view(["POST"])
@permission_classes([AllowAny])
def driver_update_student_status(request, token):
    try:
        print(f"DEBUG: Updating student status for token {token}")
        print(f"DEBUG: Data: {request.data}")
        
        route = _route_from_driver_token(token)
        if not route:
            return Response({"detail": "Invalid driver link"}, status=404)
            
        trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
        if not trip:
            return Response({"detail": "Start a trip before updating student status."}, status=400)

        sid = request.data.get("student_id")
        if not sid:
            return Response({"detail": "student_id is required."}, status=400)
            
        student_id = int(sid)
        assignment = route.student_assignments.filter(student_id=student_id, is_active=True).select_related("student").first()
        if not assignment:
            return Response({"detail": "Student is not assigned to this route."}, status=404)

        next_status = str(request.data.get("status") or "").upper()
        
        # Simple update or create
        status_obj, created = StudentTripStatus.objects.update_or_create(
            trip=trip,
            student=assignment.student,
            defaults={
                "status": next_status,
                "note": str(request.data.get("note") or "").strip(),
            }
        )
        
        return Response({
            "student_id": student_id,
            "student_name": assignment.student.full_name,
            "status": status_obj.status,
            "note": status_obj.note,
            "updated_at": status_obj.updated_at.isoformat() if status_obj.updated_at else None,
            "success": True
        })

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"CRITICAL ERROR: {error_trace}")
        return Response({"detail": str(e), "traceback": error_trace}, status=500)


# ----- Franchise: Driver Management -----

class FranchiseDriverListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = DriverProfileSerializer
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return DriverProfile.objects.none()
        return DriverProfile.objects.filter(franchise=f).select_related("user").order_by("user__full_name")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return DriverCreateSerializer
        return DriverProfileSerializer

    def get_serializer_context(self):
        c = super().get_serializer_context()
        c["franchise"] = franchise_profile_for_user(self.request.user)
        return c

    def perform_create(self, serializer):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            raise PermissionDenied("Franchise profile not found")
        serializer.save(franchise=f)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = DriverProfileSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class FranchiseDriverDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = DriverProfileSerializer

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return DriverProfile.objects.none()
        return DriverProfile.objects.filter(franchise=f).select_related("user")


# ----- Authenticated Driver Trip Endpoints -----

@api_view(["GET"])
@permission_classes([IsDriverUser])
def auth_driver_trip_detail(request):
    dp = driver_profile_for_user(request.user)
    if not dp:
        return Response({"detail": "Driver profile not found"}, status=404)
    
    assigned_routes = dp.assigned_routes.all().order_by("sort_order", "route_name")
    
    route_id = request.query_params.get("route_id")
    if route_id:
        route = assigned_routes.filter(id=route_id).first()
    else:
        route = assigned_routes.order_by("-updated_at").first()

    if not route:
        return Response({
            "route": None,
            "active_trip": None,
            "students": [],
            "all_routes": TransportRouteSerializer(assigned_routes, many=True).data
        })
    
    live_trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
    assignments = route.student_assignments.filter(is_active=True).select_related("student").order_by(
        "pickup_time",
        "student__first_name",
    )
    
    status_map = {}
    if live_trip:
        statuses = live_trip.student_statuses.all().select_related("student")
        status_map = {row.student_id: row for row in statuses}

    return Response({
        "route": TransportRouteSerializer(route).data,
        "active_trip": TransportTripSerializer(live_trip).data if live_trip else None,
        "students": [
            {
                "student_id": a.student_id,
                "student_name": a.student.full_name,
                "class_name": a.student.class_name,
                "pickup_stop": a.pickup_stop,
                "drop_stop": a.drop_stop,
                "pickup_time": a.pickup_time,
                "drop_time": a.drop_time,
                "status": status_map[a.student_id].status if a.student_id in status_map else "WAITING",
                "note": status_map[a.student_id].note if a.student_id in status_map else "",
            }
            for a in assignments
        ],
        "all_routes": TransportRouteSerializer(assigned_routes, many=True).data
    })

@api_view(["POST"])
@permission_classes([IsDriverUser])
def auth_driver_start_trip(request):
    dp = driver_profile_for_user(request.user)
    if not dp:
        return Response({"detail": "Driver profile not found"}, status=404)
    
    route_id = request.data.get("route_id") or request.query_params.get("route_id")
    if route_id:
        route = dp.assigned_routes.filter(id=route_id).first()
    else:
        route = dp.assigned_routes.order_by("-updated_at").first()

    if not route:
        return Response({"detail": "No route assigned to you."}, status=404)
    
    trip_type = str(request.data.get("trip_type") or "PICKUP").upper()
    
    # Close any existing live trips for this route
    route.trips.filter(status=TransportTrip.Status.LIVE).update(
        status=TransportTrip.Status.COMPLETED,
        completed_at=timezone.now()
    )
    
    trip = TransportTrip.objects.create(
        route=route,
        trip_type=trip_type,
        status=TransportTrip.Status.LIVE,
        started_at=timezone.now(),
        is_gps_active=True,
    )
    print(f"DEBUG: auth_driver_start_trip - Driver: {dp.user.email}, Route: {route.route_name}, Type: {trip_type}")
    return Response(TransportTripSerializer(trip).data)

@api_view(["POST"])
@permission_classes([IsDriverUser])
def auth_driver_post_location(request):
    dp = driver_profile_for_user(request.user)
    if not dp:
        return Response({"detail": "Driver profile not found"}, status=404)
    
    route_id = request.data.get("route_id") or request.query_params.get("route_id")
    if route_id:
        route = dp.assigned_routes.filter(id=route_id).first()
    else:
        route = dp.assigned_routes.order_by("-updated_at").first()

    if not route:
        return Response({"detail": "No route assigned to you."}, status=404)
    
    trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
    if not trip:
        return Response({"detail": "No live trip found"}, status=400)
    if not trip.is_gps_active:
        return Response({"detail": "GPS sharing is off for this trip."}, status=400)

    serializer = TransportTripLocationSerializer(data=request.data)
    if serializer.is_valid():
        location = serializer.save(trip=trip)
        print(f"DEBUG: auth_driver_post_location - Lat: {location.latitude}, Lon: {location.longitude}")
        return Response(TransportTripLocationSerializer(location).data)
    print(f"DEBUG: auth_driver_post_location ERRORS: {serializer.errors}")
    return Response(serializer.errors, status=400)

@api_view(["POST"])
@permission_classes([IsDriverUser])
def auth_driver_update_student_status(request):
    dp = driver_profile_for_user(request.user)
    if not dp:
        return Response({"detail": "Driver profile not found"}, status=404)
    
    route_id = request.data.get("route_id") or request.query_params.get("route_id")
    if route_id:
        route = dp.assigned_routes.filter(id=route_id).first()
    else:
        route = dp.assigned_routes.order_by("-updated_at").first()

    if not route:
        return Response({"detail": "No route assigned to you."}, status=404)
    
    trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
    if not trip:
        return Response({"detail": "No live trip found"}, status=400)

    try:
        sid = request.data.get("student_id")
        student_id = int(sid)
        assignment = route.student_assignments.filter(student_id=student_id, is_active=True).first()
        if not assignment:
            return Response({"detail": "Student not assigned to your route"}, status=404)
            
        next_status = str(request.data.get("status") or "").upper()
        
        status_obj, created = StudentTripStatus.objects.update_or_create(
            trip=trip,
            student_id=student_id,
            defaults={
                "status": next_status,
                "note": str(request.data.get("note") or "").strip(),
            }
        )
        print(f"DEBUG: auth_driver_update_student_status - Trip: {trip.id}, Student: {student_id}, New Status: {next_status}")
        return Response({
            "success": True, 
            "status": status_obj.status,
            "note": status_obj.note,
            "student_name": assignment.student.full_name
        })
    except Exception as e:
        return Response({"detail": str(e)}, status=500)

@api_view(["POST"])
@permission_classes([IsDriverUser])
def auth_driver_complete_trip(request):
    dp = driver_profile_for_user(request.user)
    if not dp:
        return Response({"detail": "Driver profile not found"}, status=404)
    
    route_id = request.data.get("route_id") or request.query_params.get("route_id")
    if route_id:
        route = dp.assigned_routes.filter(id=route_id).first()
    else:
        route = dp.assigned_routes.order_by("-updated_at").first()

    if not route:
        return Response({"detail": "No route assigned to you."}, status=404)
        
    trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
    if not trip:
        return Response({"detail": "No live trip to complete"}, status=400)
    
    trip.status = TransportTrip.Status.COMPLETED
    trip.completed_at = timezone.now()
    trip.is_gps_active = False
    trip.save(update_fields=["status", "completed_at", "is_gps_active", "updated_at"])
    return Response(TransportTripSerializer(trip).data)

@api_view(["POST"])
@permission_classes([IsDriverUser])
def auth_driver_toggle_gps(request):
    dp = driver_profile_for_user(request.user)
    if not dp:
        return Response({"detail": "Driver profile not found"}, status=404)
    
    route_id = request.data.get("route_id") or request.query_params.get("route_id")
    if route_id:
        route = dp.assigned_routes.filter(id=route_id).first()
    else:
        route = dp.assigned_routes.order_by("-updated_at").first()

    if not route:
        return Response({"detail": "No route assigned to you."}, status=404)
        
    trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
    if not trip:
        return Response({"detail": "No live trip found"}, status=400)
    
    active = request.data.get("active", True)
    trip.is_gps_active = bool(active)
    trip.save()
    print(f"DEBUG: auth_driver_toggle_gps - Trip: {trip.id}, Active: {trip.is_gps_active}")
    return Response({"is_gps_active": trip.is_gps_active})
