from datetime import date
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsParentUser
from events.models import Event
from .models import StudentProfile, Grade
from .serializers import StudentProfileSerializer, StudentDetailSerializer, GradeSerializer


class ParentStudentListView(generics.ListAPIView):
    """List all students for the logged-in parent"""
    serializer_class = StudentProfileSerializer
    permission_classes = [IsParentUser]

    def get_queryset(self):
        parent_profile = getattr(self.request.user, "parent_profile", None)
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
        parent_profile = getattr(self.request.user, "parent_profile", None)
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
        parent_profile = getattr(self.request.user, "parent_profile", None)
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
        parent_profile = getattr(request.user, "parent_profile", None)
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
