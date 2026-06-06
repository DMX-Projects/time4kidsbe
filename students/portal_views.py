from accounts.permissions import IsDriverUser
from accounts.profile_access import driver_profile_for_user
from franchises.models import DriverProfile
from franchises.serializers import DriverProfileSerializer, DriverCreateSerializer
"""Parent portal: homework, announcements, attendance, fees, transport, support tickets."""

import re
import threading
import json
from datetime import timedelta

from django.db import transaction
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

from accounts.permissions import IsFranchiseUser, IsParentUser
from accounts.profile_access import (
    effective_franchise_for_parent,
    find_student_for_parent_user,
    franchise_profile_for_user,
    parents_at_franchise,
    resolved_parent_profile_for_user,
    user_owns_legacy_student,
)
from events.calendar_filters import exclude_showcase_placeholder_events
from events.models import Event
from events.serializers import EventSerializer

from .models import (
    Announcement,
    AttendanceRecord,
    FeeRecord,
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
from .serializers import (
    AnnouncementSerializer,
    AttendanceRecordSerializer,
    FranchiseAttendanceBulkSerializer,
    FranchiseAttendanceUpsertSerializer,
    FeeRecordSerializer,
    GradeSerializer,
    HomeworkAssignmentSerializer,
    ParentStudentAchievementSerializer,
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
        canon = _canonical_class_label(cn)
        if canon:
            names.add(canon)
    return names


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
    for cn in _parent_class_target_names(parent_profile):
        vis |= Q(student__isnull=True, class_name=cn)
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
    if sc == tc:
        return True

    sc_canon = _canonical_class_label(sc)
    tc_canon = _canonical_class_label(tc)
    if sc_canon and tc_canon:
        return sc_canon == tc_canon
    if sc_canon and sc_canon == tc:
        return True
    if tc_canon and tc_canon == sc:
        return True

    sc_lower = sc.lower()
    tc_lower = tc.lower()
    if sc_lower == tc_lower or sc_lower in tc_lower or tc_lower in sc_lower:
        return True
    for label in HOMEWORK_CLASS_LABELS:
        label_lower = label.lower()
        sc_match = label_lower in sc_lower or sc_lower in label_lower
        tc_match = label_lower in tc_lower or tc_lower in label_lower
        if sc_match and tc_match:
            return True
        if sc_match and label == tc:
            return True
        if tc_match and label == sc:
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
    target_class = (announcement.class_name or "").strip()
    if target_class:
        parent_ids: set[int] = set()
        base_parent_ids = list(base.values_list("pk", flat=True))
        for student in StudentProfile.objects.filter(
            is_active=True,
            parent_id__in=base_parent_ids,
        ).only("parent_id", "class_name", "Centre", "City"):
            if _class_label_matches(student.class_name, target_class):
                parent_ids.add(student.parent_id)
        return base.filter(pk__in=parent_ids)
    return base


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
        return (
            HomeworkAssignment.objects.filter(franchise=centre)
            .filter(_homework_visible_q(pp, user=self.request.user))
            .select_related("student")
            .distinct()
            .order_by("-assigned_date", "-created_at")
        )


def _announcement_notification_rows(rows, read_map=None):
    """Shape centre announcements for parent app notification feeds."""
    read_map = read_map or {}
    notifications = []
    for row in rows:
        ann_id = row.get("id")
        key = f"announcement-{ann_id}"
        read_at = read_map.get(key)
        body = row.get("body") or ""
        notifications.append(
            {
                "id": key,
                "source": "announcement",
                "source_id": ann_id,
                "title": row.get("title") or "Announcement",
                "body": body,
                "message": body,
                "description": body,
                "published_at": row.get("published_at"),
                "audience_label": row.get("audience_label") or "",
                "student_name": row.get("student_name") or "",
                "read": read_at is not None,
                "read_at": read_at,
            }
        )
    return notifications


class ParentAnnouncementListView(generics.ListAPIView):
    permission_classes = [IsParentUser]
    serializer_class = AnnouncementSerializer
    pagination_class = None

    def get_queryset(self):
        pp = resolved_parent_profile_for_user(self.request.user)
        centre = _parent_centre(pp)
        if not pp or not centre:
            return Announcement.objects.none()
        return (
            Announcement.objects.filter(franchise=centre, is_active=True)
            .filter(_announcement_visible_q(pp, user=self.request.user))
            .select_related("student")
            .distinct()
            .order_by("-published_at")
        )

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
        return (
            AttendanceRecord.objects.filter(student__parent=pp, student__is_active=True)
            .select_related("student")
            .order_by("-date", "student_id")
        )


class ParentCalendarAttendanceView(APIView):
    """Combined parent payload for calendar events + attendance."""

    permission_classes = [IsParentUser]

    def get(self, request):
        pp = resolved_parent_profile_for_user(request.user)
        centre = _parent_centre(pp)
        if not pp or not centre:
            return Response({"calendar_events": [], "attendance": []})

        events_qs = exclude_showcase_placeholder_events(
            Event.objects.filter(franchise=centre)
        ).order_by("-start_date", "-created_at")
        attendance_qs = (
            AttendanceRecord.objects.filter(student__parent=pp, student__is_active=True)
            .select_related("student")
            .order_by("-date", "student_id")
        )
        return Response(
            {
                "calendar_events": EventSerializer(events_qs, many=True).data,
                "attendance": AttendanceRecordSerializer(attendance_qs, many=True).data,
            }
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
        student_id = (request.query_params.get("student") or "").strip()
        student = None

        if pp:
            students_qs = StudentProfile.objects.filter(parent=pp, is_active=True).select_related(
                "parent", "parent__franchise"
            )
            if student_id:
                student = students_qs.filter(pk=student_id).first()

        if not student:
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
        return (
            Grade.objects.filter(student__parent=pp, student__is_active=True)
            .select_related("student")
            .order_by("-exam_date", "subject")
        )

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
        return SupportTicket.objects.filter(parent=pp).order_by("-created_at")

    def perform_create(self, serializer):
        pp = resolved_parent_profile_for_user(self.request.user)
        if not pp:
            raise PermissionDenied(
                "Parent profile not found. Your account is not linked to a centre yet — contact your preschool."
            )
        serializer.save(parent=pp)


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
                    "notifications": [],
                    "unread_count": 0,
                }
            )

        announcements_qs = (
            Announcement.objects.filter(franchise=centre, is_active=True)
            .filter(_announcement_visible_q(pp, user=request.user))
            .select_related("student")
            .distinct()
            .order_by("-published_at")
        ) if centre else Announcement.objects.none()
        homework_qs = (
            HomeworkAssignment.objects.filter(franchise=centre)
            .filter(_homework_visible_q(pp, user=request.user))
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
        events_qs = (
            exclude_showcase_placeholder_events(Event.objects.filter(franchise=centre)).order_by(
                "-start_date", "-created_at"
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
                    "body": item.description or "",
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

        notifications = [
            n for n in notifications if (not n["read"]) or (n.get("read_at") and n["read_at"] >= hide_read_before)
        ]
        notifications.sort(
            key=lambda x: x.get("published_at").isoformat() if x.get("published_at") else "",
            reverse=True,
        )
        unread_count = sum(1 for n in notifications if not n["read"])

        return Response(
            {
                "announcements": AnnouncementSerializer(announcements_qs, many=True).data,
                "homework": HomeworkAssignmentSerializer(homework_qs, many=True).data,
                "fees": FeeRecordSerializer(fees_qs, many=True).data,
                "transport": ParentTransportRouteSerializer(transport_qs, many=True).data,
                "events": EventSerializer(events_qs, many=True).data,
                "achievements": ParentStudentAchievementSerializer(achievements_qs, many=True).data,
                "attendance": AttendanceRecordSerializer(attendance_qs, many=True).data,
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


class FranchiseAnnouncementListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = AnnouncementSerializer
    pagination_class = None

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return Announcement.objects.none()
        qs = Announcement.objects.filter(franchise=f).select_related("student").order_by("-published_at")
        date_str = (self.request.query_params.get("published_date") or "").strip()
        if date_str:
            parsed = parse_date(date_str)
            if parsed is not None:
                qs = qs.filter(published_at__date=parsed)
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
        announcement = serializer.save(franchise=f)
        pk = announcement.pk

        def _email_parents() -> None:
            from students.emails import notify_parents_new_announcement_by_id

            notify_parents_new_announcement_by_id(pk)

        transaction.on_commit(lambda: threading.Thread(target=_email_parents, daemon=True).start())


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

        # Optional date filter (ISO YYYY-MM-DD). Raw strings can error on some DB/backends.
        date_str = (self.request.query_params.get("date") or "").strip()
        if date_str:
            parsed = parse_date(date_str)
            if parsed is not None:
                queryset = queryset.filter(date=parsed)
            else:
                queryset = queryset.none()

        return queryset.select_related("student", "student__parent").order_by("-date", "student_id")

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
        return SupportTicket.objects.filter(parent__franchise=f).select_related("parent", "parent__user").order_by("-created_at")


class FranchiseSupportTicketDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = SupportTicketFranchiseSerializer

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return SupportTicket.objects.none()
        qs = SupportTicket.objects.filter(parent__franchise=f).select_related("parent", "parent__user")
        return qs


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
