from accounts.permissions import IsDriverUser
from accounts.profile_access import driver_profile_for_user
from franchises.models import DriverProfile
from franchises.serializers import DriverProfileSerializer, DriverCreateSerializer
"""Parent portal: homework, announcements, attendance, fees, transport, support tickets."""

import threading
import json
from datetime import timedelta

from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
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
    FeeRecordSerializer,
    GradeSerializer,
    HomeworkAssignmentSerializer,
    ParentStudentAchievementSerializer,
    SupportTicketFranchiseSerializer,
    SupportTicketParentSerializer,
    StudentTransportAssignmentSerializer,
    TransportRouteSerializer,
    TransportTripLocationSerializer,
    TransportTripSerializer,
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


class ParentLiveTransportView(APIView):
    """Latest live transport trip for this parent's assigned route.

    If no student assignment exists yet, falls back to the newest live trip at
    the parent's centre so early centres can trial live tracking before full
    route assignment data is entered.
    """

    permission_classes = [IsParentUser]

    def get(self, request):
        pp = parent_profile_for_user(request.user)
        if not pp:
            return Response({"live": False, "detail": "Parent profile not found"}, status=404)

        school_location = None
        if pp.franchise.latitude and pp.franchise.longitude:
            school_location = {
                "latitude": float(pp.franchise.latitude),
                "longitude": float(pp.franchise.longitude),
            }

        students = StudentProfile.objects.filter(parent=pp, is_active=True)
        assigned_routes = TransportRoute.objects.filter(
            student_assignments__student__in=students,
            student_assignments__is_active=True,
        ).distinct()

        routes = assigned_routes if assigned_routes.exists() else TransportRoute.objects.filter(franchise=pp.franchise)
        trip = (
            TransportTrip.objects.filter(route__in=routes, status=TransportTrip.Status.LIVE)
            .select_related("route")
            .prefetch_related("locations")
            .order_by("-started_at", "-created_at")
            .first()
        )
        if not trip:
            route = routes.order_by("sort_order", "route_name").first()
            return Response(
                {
                    "live": False,
                    "route": TransportRouteSerializer(route).data if route else None,
                    "trip": None,
                    "latest_location": None,
                    "student_status": None,
                    "school_location": school_location,
                }
            )

        latest_location = trip.locations.order_by("-recorded_at").first()
        student_status = (
            trip.student_statuses.filter(student__in=students)
            .select_related("student")
            .order_by("-updated_at")
            .first()
        )

        return Response(
            {
                "live": latest_location is not None,
                "route": TransportRouteSerializer(trip.route).data,
                "trip": TransportTripSerializer(trip).data,
                "latest_location": TransportTripSerializer(trip).data.get("latest_location"),
                "student_status": {
                    "student_id": student_status.student_id,
                    "student_name": student_status.student.full_name,
                    "status": student_status.status,
                    "note": student_status.note,
                    "updated_at": student_status.updated_at,
                }
                if student_status
                else None,
                "school_location": school_location,
            }
        )


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
    trip.save(update_fields=["status", "completed_at", "updated_at"])
    return Response(TransportTripSerializer(trip).data)


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
    
    # A driver might be assigned to multiple routes; pick the most recently updated one.
    route = dp.assigned_routes.order_by("-updated_at").first()
    if not route:
        return Response({"detail": "No route assigned to you."}, status=404)
    
    live_trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
    assignments = route.student_assignments.filter(is_active=True).select_related("student").order_by(
        "pickup_time",
        "student__first_name",
    )
    
    status_map = {}
    if live_trip:
        statuses = live_trip.student_statuses.all().select_related("student")
        status_map = {row.student_id: row for row in statuses}
        print(f"DEBUG: auth_driver_trip_detail - Trip: {live_trip.id}, Statuses found: {len(status_map)}")
        for sid, row in status_map.items():
             print(f"  - Student {sid}: {row.status}")

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
        ]
    })

@api_view(["POST"])
@permission_classes([IsDriverUser])
def auth_driver_start_trip(request):
    dp = driver_profile_for_user(request.user)
    if not dp:
        return Response({"detail": "Driver profile not found"}, status=404)
    
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
        started_at=timezone.now()
    )
    print(f"DEBUG: auth_driver_start_trip - Driver: {dp.user.email}, Route: {route.route_name}, Type: {trip_type}")
    return Response(TransportTripSerializer(trip).data)

@api_view(["POST"])
@permission_classes([IsDriverUser])
def auth_driver_post_location(request):
    dp = driver_profile_for_user(request.user)
    if not dp:
        return Response({"detail": "Driver profile not found"}, status=404)
    
    route = dp.assigned_routes.order_by("-updated_at").first()
    if not route:
        return Response({"detail": "No route assigned to you."}, status=404)
    
    trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
    if not trip:
        return Response({"detail": "No live trip found"}, status=400)
    
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
    
    route = dp.assigned_routes.order_by("-updated_at").first()
    if not route:
        return Response({"detail": "No route assigned to you."}, status=404)
        
    trip = route.trips.filter(status=TransportTrip.Status.LIVE).order_by("-started_at", "-created_at").first()
    if not trip:
        return Response({"detail": "No live trip to complete"}, status=400)
    
    trip.status = TransportTrip.Status.COMPLETED
    trip.completed_at = timezone.now()
    trip.save()
    return Response(TransportTripSerializer(trip).data)

@api_view(["POST"])
@permission_classes([IsDriverUser])
def auth_driver_toggle_gps(request):
    dp = driver_profile_for_user(request.user)
    if not dp:
        return Response({"detail": "Driver profile not found"}, status=404)
    
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
