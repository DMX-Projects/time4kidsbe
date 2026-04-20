"""Parent portal: homework, announcements, attendance, fees, transport, support tickets."""

import threading

from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied

from accounts.permissions import IsFranchiseUser, IsParentUser
from accounts.profile_access import franchise_profile_for_user, parent_profile_for_user

from .models import (
    Announcement,
    AttendanceRecord,
    FeeRecord,
    Grade,
    HomeworkAssignment,
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
