"""Parent portal: homework, announcements, attendance, fees, transport, support tickets."""

import threading
import json
from datetime import timedelta

from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFranchiseUser, IsParentUser
from accounts.profile_access import franchise_profile_for_user, parent_profile_for_user
from events.models import Event
from events.serializers import EventSerializer

from .models import (
    Announcement,
    AttendanceRecord,
    FeeRecord,
    Grade,
    HomeworkAssignment,
    ParentNotificationRead,
    StudentAchievement,
    StudentProfile,
    SupportTicket,
    TransportRoute,
)
from .serializers import (
    AnnouncementSerializer,
    AttendanceRecordSerializer,
    FeeRecordSerializer,
    GradeSerializer,
    HomeworkAssignmentSerializer,
    ParentStudentAchievementSerializer,
    SupportTicketFranchiseSerializer,
    SupportTicketParentSerializer,
    TransportRouteSerializer,
)


def _homework_visible_q(parent_profile):
    kids = StudentProfile.objects.filter(parent=parent_profile, is_active=True)
    vis = Q(student__isnull=True, class_name="")
    for k in kids:
        vis |= Q(student=k)
        cn = (k.class_name or "").strip()
        if cn:
            vis |= Q(student__isnull=True, class_name=cn)
    return vis


# ----- Parent (read-only / limited write) -----


class ParentHomeworkListView(generics.ListAPIView):
    permission_classes = [IsParentUser]
    serializer_class = HomeworkAssignmentSerializer
    pagination_class = None

    def get_queryset(self):
        pp = parent_profile_for_user(self.request.user)
        if not pp:
            return HomeworkAssignment.objects.none()
        return (
            HomeworkAssignment.objects.filter(franchise=pp.franchise)
            .filter(_homework_visible_q(pp))
            .select_related("student")
            .distinct()
            .order_by("-assigned_date", "-created_at")
        )


class ParentAnnouncementListView(generics.ListAPIView):
    permission_classes = [IsParentUser]
    serializer_class = AnnouncementSerializer
    pagination_class = None

    def get_queryset(self):
        pp = parent_profile_for_user(self.request.user)
        if not pp:
            return Announcement.objects.none()
        return Announcement.objects.filter(franchise=pp.franchise, is_active=True).order_by("-published_at")


class ParentAttendanceListView(generics.ListAPIView):
    permission_classes = [IsParentUser]
    serializer_class = AttendanceRecordSerializer
    pagination_class = None

    def get_queryset(self):
        pp = parent_profile_for_user(self.request.user)
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
        pp = parent_profile_for_user(request.user)
        if not pp:
            return Response({"calendar_events": [], "attendance": []})

        events_qs = Event.objects.filter(franchise=pp.franchise).order_by("-start_date", "-created_at")
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
        pp = parent_profile_for_user(self.request.user)
        if not pp:
            return FeeRecord.objects.none()
        return (
            FeeRecord.objects.filter(student__parent=pp, student__is_active=True)
            .select_related("student")
            .order_by("-due_date", "-created_at")
        )


class ParentGradeListView(generics.ListAPIView):
    permission_classes = [IsParentUser]
    serializer_class = GradeSerializer
    pagination_class = None

    def get_queryset(self):
        pp = parent_profile_for_user(self.request.user)
        if not pp:
            return Grade.objects.none()
        return (
            Grade.objects.filter(student__parent=pp, student__is_active=True)
            .select_related("student")
            .order_by("-exam_date", "subject")
        )

class ParentTransportListView(generics.ListAPIView):
    permission_classes = [IsParentUser]
    serializer_class = TransportRouteSerializer
    pagination_class = None

    def get_queryset(self):
        pp = parent_profile_for_user(self.request.user)
        if not pp:
            return TransportRoute.objects.none()
        return TransportRoute.objects.filter(franchise=pp.franchise).order_by("sort_order", "route_name")


class ParentSupportTicketListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsParentUser]
    serializer_class = SupportTicketParentSerializer
    pagination_class = None

    def get_queryset(self):
        pp = parent_profile_for_user(self.request.user)
        if not pp:
            return SupportTicket.objects.none()
        return SupportTicket.objects.filter(parent=pp).order_by("-created_at")

    def perform_create(self, serializer):
        pp = parent_profile_for_user(self.request.user)
        if not pp:
            raise PermissionDenied("Parent profile not found")
        serializer.save(parent=pp)


class ParentNotificationsView(APIView):
    """Single parent notifications payload with all parent-visible updates."""

    permission_classes = [IsParentUser]

    @staticmethod
    def _notification_key(source: str, item_id: int) -> str:
        return f"{source}-{item_id}"

    def get(self, request):
        pp = parent_profile_for_user(request.user)
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

        announcements_qs = Announcement.objects.filter(franchise=pp.franchise, is_active=True).order_by("-published_at")
        homework_qs = (
            HomeworkAssignment.objects.filter(franchise=pp.franchise)
            .filter(_homework_visible_q(pp))
            .select_related("student")
            .distinct()
            .order_by("-assigned_date", "-created_at")
        )
        fees_qs = (
            FeeRecord.objects.filter(student__parent=pp, student__is_active=True)
            .select_related("student")
            .order_by("-due_date", "-created_at")
        )
        transport_qs = TransportRoute.objects.filter(franchise=pp.franchise).order_by("sort_order", "route_name")
        events_qs = Event.objects.filter(franchise=pp.franchise).order_by("-start_date", "-created_at")
        kids = StudentProfile.objects.filter(parent=pp, is_active=True)
        achievements_qs = (
            StudentAchievement.objects.filter(franchise=pp.franchise)
            .filter(Q(student__in=kids) | Q(student__isnull=True))
            .select_related("student")
            .distinct()
            .order_by("-achieved_date", "-created_at")
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
                "transport": TransportRouteSerializer(transport_qs, many=True).data,
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
        pp = parent_profile_for_user(request.user)
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

    def get_queryset(self):
        f = franchise_profile_for_user(self.request.user)
        if not f:
            return HomeworkAssignment.objects.none()
        return HomeworkAssignment.objects.filter(franchise=f).select_related("student").order_by("-assigned_date")

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
        return Announcement.objects.filter(franchise=f).order_by("-published_at")

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
        return Announcement.objects.filter(franchise=f)


class FranchiseAttendanceListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = AttendanceRecordSerializer
    pagination_class = None

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
