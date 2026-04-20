from datetime import date

from django.db.models import Q
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFranchiseUser, IsParentUser
from accounts.profile_access import franchise_profile_for_user, parent_profile_for_user
from events.models import Event

from .models import Grade, StudentAchievement, StudentProfile
from .serializers import (
    FranchiseStudentSerializer,
    GradeSerializer,
    ParentStudentAchievementSerializer,
    StudentAchievementSerializer,
    StudentDetailSerializer,
    StudentMiniSerializer,
    StudentProfileSerializer,
)


class ParentStudentListView(generics.ListAPIView):
    """List all students for the logged-in parent"""
    serializer_class = StudentProfileSerializer
    permission_classes = [IsParentUser]

    def get_queryset(self):
        parent_profile = parent_profile_for_user(self.request.user)
        if not parent_profile:
            return StudentProfile.objects.none()
        return StudentProfile.objects.filter(
            parent=parent_profile,
            is_active=True
        ).select_related('parent', 'parent__user', 'parent__franchise')


class ParentStudentDetailView(generics.RetrieveAPIView):
    """Get detailed student profile with grades"""
    serializer_class = StudentDetailSerializer
    permission_classes = [IsParentUser]

    def get_queryset(self):
        parent_profile = parent_profile_for_user(self.request.user)
        if not parent_profile:
            return StudentProfile.objects.none()
        return StudentProfile.objects.filter(
            parent=parent_profile,
            is_active=True
        ).prefetch_related('grades')


class ParentStudentGradesView(generics.ListAPIView):
    """Get all grades for a specific student"""
    serializer_class = GradeSerializer
    permission_classes = [IsParentUser]

    def get_queryset(self):
        student_id = self.kwargs.get('student_id')
        parent_profile = parent_profile_for_user(self.request.user)
        if not parent_profile:
            return Grade.objects.none()
        
        # Verify student belongs to parent
        student = StudentProfile.objects.filter(
            id=student_id,
            parent=parent_profile,
            is_active=True
        ).first()
        
        if not student:
            return Grade.objects.none()
        
        return Grade.objects.filter(student=student).order_by('-exam_date', 'subject')


class ParentDashboardView(APIView):
    """Parent dashboard with summary statistics"""
    permission_classes = [IsParentUser]

    def get(self, request):
        parent_profile = parent_profile_for_user(request.user)
        if not parent_profile:
            return Response({"error": "Parent profile not found"}, status=404)
        
        # Get students
        students = StudentProfile.objects.filter(
            parent=parent_profile,
            is_active=True
        )
        
        # Get first student for welcome message
        first_student = students.first()
        
        # Count grades
        total_grades = Grade.objects.filter(student__parent=parent_profile).count()
        
        # Count upcoming events
        upcoming_events_count = Event.objects.filter(
            franchise=parent_profile.franchise,
            start_date__gte=date.today()
        ).count()
        
        # Prepare dashboard data
        dashboard_data = {
            "welcome_message": f"Welcome, {first_student.full_name}'s family!" if first_student else f"Welcome, {request.user.full_name}!",
            "student_summary": {
                "total_students": students.count(),
                "first_student": StudentProfileSerializer(first_student).data if first_student else None,
            },
            "grades_summary": {
                "total_records": total_grades,
                "message": f"{total_grades} Records saved" if total_grades > 0 else "No records yet"
            },
            "events_summary": {
                "upcoming_count": upcoming_events_count,
                "message": f"{upcoming_events_count} Stay updated" if upcoming_events_count > 0 else "No upcoming events"
            },
            "franchise": {
                "id": parent_profile.franchise.id,
                "name": parent_profile.franchise.name,
                "slug": parent_profile.franchise.slug,
            }
        }
        
        return Response(dashboard_data)


class ParentAchievementListView(generics.ListAPIView):
    """Achievements visible to this parent (their children + centre-wide)."""

    permission_classes = [IsParentUser]
    serializer_class = ParentStudentAchievementSerializer
    pagination_class = None

    def get_queryset(self):
        parent_profile = parent_profile_for_user(self.request.user)
        if not parent_profile:
            return StudentAchievement.objects.none()
        kids = StudentProfile.objects.filter(parent=parent_profile, is_active=True)
        return (
            StudentAchievement.objects.filter(franchise=parent_profile.franchise)
            .filter(Q(student__in=kids) | Q(student__isnull=True))
            .select_related("student")
            .distinct()
            .order_by("-achieved_date", "-created_at")
        )


class FranchiseStudentMiniListView(generics.ListAPIView):
    """Active students at this centre (for achievement picker)."""

    permission_classes = [IsFranchiseUser]
    serializer_class = StudentMiniSerializer
    pagination_class = None

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return StudentProfile.objects.none()
        return StudentProfile.objects.filter(parent__franchise=franchise, is_active=True).select_related("parent")


class FranchiseStudentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = FranchiseStudentSerializer
    pagination_class = None

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return StudentProfile.objects.none()
        return StudentProfile.objects.filter(parent__franchise=franchise).select_related("parent")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class FranchiseStudentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = FranchiseStudentSerializer

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return StudentProfile.objects.none()
        return StudentProfile.objects.filter(parent__franchise=franchise).select_related("parent")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class FranchiseGradeListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = GradeSerializer
    pagination_class = None

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return Grade.objects.none()
        return Grade.objects.filter(student__parent__franchise=franchise).select_related("student")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_create(self, serializer):
        franchise = franchise_profile_for_user(self.request.user)
        student = serializer.validated_data["student"]
        if not franchise or student.parent.franchise_id != franchise.id:
            raise PermissionDenied("Student is not enrolled at your centre")
        serializer.save()


class FranchiseGradeDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = GradeSerializer

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return Grade.objects.none()
        return Grade.objects.filter(student__parent__franchise=franchise).select_related("student")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_update(self, serializer):
        franchise = franchise_profile_for_user(self.request.user)
        student = serializer.validated_data.get("student", serializer.instance.student)
        if not franchise or student.parent.franchise_id != franchise.id:
            raise PermissionDenied("Student is not enrolled at your centre")
        serializer.save()


class FranchiseAchievementListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = StudentAchievementSerializer
    pagination_class = None

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return StudentAchievement.objects.none()
        return StudentAchievement.objects.filter(franchise=franchise).select_related("student")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_create(self, serializer):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            raise PermissionDenied("Franchise profile not found")
        serializer.save(franchise=franchise)


class FranchiseAchievementDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = StudentAchievementSerializer

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return StudentAchievement.objects.none()
        return StudentAchievement.objects.filter(franchise=franchise).select_related("student")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


# ----- Franchise Student & Grade CRUD -----

class FranchiseStudentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = StudentProfileSerializer
    pagination_class = None

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return StudentProfile.objects.none()
        return StudentProfile.objects.filter(parent__franchise=franchise).select_related("parent", "parent__user")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_create(self, serializer):
        # Verify parent belongs to franchise
        parent = serializer.validated_data.get('parent')
        franchise = franchise_profile_for_user(self.request.user)
        if parent.franchise != franchise:
            raise PermissionDenied("Parent does not belong to your centre.")
        serializer.save()


class FranchiseStudentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = StudentProfileSerializer

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return StudentProfile.objects.none()
        return StudentProfile.objects.filter(parent__franchise=franchise).select_related("parent", "parent__user")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class FranchiseGradeListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = GradeSerializer
    pagination_class = None

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return Grade.objects.none()
        return Grade.objects.filter(student__parent__franchise=franchise).select_related("student")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx



class FranchiseGradeDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsFranchiseUser]
    serializer_class = GradeSerializer

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return Grade.objects.none()
        return Grade.objects.filter(student__parent__franchise=franchise)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx
